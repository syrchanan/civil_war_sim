# class to handle the lanchester simulations and markov chain simulations

# base libs
import logging
import secrets
from typing import Tuple

# ext libs
import numpy as np
import pandas as pd

# local imports
from imperial_generals.units import Regiment
from imperial_generals.config import get_config
from imperial_generals.utils import Rng
from imperial_generals.battles.morale import MoraleParams, MoraleState

class Simulation:
    """
    Handles Lanchester and Markov chain simulations for two opposing regiments.

    Attributes:
        forces (Tuple[Regiment, Regiment]): The two opposing Regiment instances.
        casualties (dict[str, tuple[int, int] | np.ndarray]):
            Tracks initial sizes, current losses, and morale for both regiments.
            Keys:
                - 'initial_size': tuple[int, int]
                - 'losses': np.ndarray
                - 'morale': tuple[int, int]
        sim_output pd.DataFrame: Tracks simulation time, sizes, and morale history.
    """

    def __init__(self, forces: Tuple[Regiment, Regiment], rng: Rng | None = None,
                 morale_params: MoraleParams | None = None):
        """
        Initialize the Simulation with two regiments.

        Args:
            forces (Tuple[Regiment, Regiment]): The two opposing Regiment instances.
            rng (Rng | None): Seeded generator for all randomness. Pass Rng(seed) for a
                reproducible battle; defaults to a randomly seeded Rng.
            morale_params (MoraleParams | None): Morale model constants for both sides;
                defaults to config.

        Sets:
            self.forces: Tuple[Regiment, Regiment]
            self.rng: Rng
            self.morale_states: Tuple[MoraleState, MoraleState]
            self.casualties: dict[str, list[int, int] | np.ndarray]
                - 'initial_size': list[int, int]
                - 'losses': np.ndarray
                - 'morale': np.ndarray
            self.sim_output: pd.DataFrame
        """
        if not isinstance(forces, tuple) or not all(isinstance(r, Regiment) for r in forces) or len(forces) != 2:
            raise ValueError("forces must be a tuple of two Regiment instances.")

        if rng is not None and not isinstance(rng, Rng):
            raise TypeError(f"rng must be an Rng instance, got {type(rng).__name__}.")

        self.forces: Tuple[Regiment, Regiment] = forces
        self.rng: Rng = rng if rng is not None else Rng(secrets.randbits(32))

        reg1, reg2 = forces
        self.morale_states: Tuple[MoraleState, MoraleState] = tuple(
            MoraleState(size=reg.size, xp=reg.stats[0], morale_stat=reg.stats[1], params=morale_params)
            for reg in forces
        )
        self.casualties: dict[str, list[int, int] | np.ndarray] = {
            'initial_size': [reg1.size, reg2.size],
            'losses': np.array([0, 0]),
            'morale': np.array([reg1.raw_morale, reg2.raw_morale])
        }

        self.sim_output = pd.DataFrame({
            'time': [0],
            'size_1': [reg1.size],
            'size_2': [reg2.size],
            'morale_1': [reg1.raw_morale],
            'morale_2': [reg2.raw_morale]
        })

        logging.info(f"Initialized Simulation with forces: {self.forces}")

    def __str__(self) -> str:
        losses = self.casualties['losses']
        return (
            f"Simulation(forces={[str(f) for f in self.forces]}, "
            f"losses={losses.tolist()})"
        )

    def __repr__(self) -> str:
        losses = self.casualties['losses']
        return (
            f"Simulation(forces={self.forces!r}, "
            f"losses={losses.tolist()})"
        )

    @staticmethod
    def _compute_rate(regiment: Regiment, sizes: list, coef: list, front_sizes: list, idx: int) -> float:
        """
        Compute the casualty rate for the regiment at position idx.

        Dispatches to the appropriate Lanchester law based on regiment.effective_law:
          'ln' (melee/linear): -coef_B * front_A * front_B — both engaged fronts drive the rate.
          'sq' (ranged/square): -coef_B * B_total — all opponents fire independently.

        Args:
            regiment: The regiment whose casualties are being computed.
            sizes: Current [size_0, size_1].
            coef: Combat efficiency [coef_0, coef_1].
            front_sizes: Effective front [min(size,front_size)_0, min(size,front_size)_1].
            idx: Index of this regiment (0 or 1).

        Returns:
            float: Rate of change (negative = casualties).
        """
        if regiment.effective_law == 'ln':
            return -coef[1 - idx] * front_sizes[idx] * front_sizes[1 - idx]
        else:
            return -coef[1 - idx] * sizes[1 - idx]

    def _sync_morale(self, side: int) -> None:
        """Push a side's live morale into the casualty log and the Regiment (which updates its coef)."""
        morale = float(self.morale_states[side].morale)
        self.casualties['morale'][side] = morale
        self.forces[side].update_raw_morale(morale)

    def _row(self, t: float) -> dict:
        return {
            'time': t,
            'size_1': self.forces[0].size,
            'size_2': self.forces[1].size,
            'morale_1': self.casualties['morale'][0],
            'morale_2': self.casualties['morale'][1],
        }

    def run_simulation(self, time: float) -> None:
        """
        Run the battle until game time ``time`` (minutes), a side breaks or is wiped out, or nobody can fire.

        Continuous-time Markov chain: each side's casualty rate comes from the Lanchester law for its combat
        mode, scaled to casualties per minute by the kill rates in combat.yaml. The next casualty time is drawn
        from an exponential per side; the earliest one happens. Morale advances through the elapsed time
        (shock fades, engaged units drain), then the casualty is applied to both sides' morale.
        """
        combat_cfg = get_config()['combat']
        kill_rate = {'sq': combat_cfg['ranged_kill_rate'], 'ln': combat_cfg['melee_kill_rate']}

        t = float(self.sim_output['time'].iloc[-1])
        rows = []

        while t < time:
            sizes = [reg.size for reg in self.forces]
            coef = [reg.coef for reg in self.forces]
            front_sizes = [min(reg.size, reg.front_size) for reg in self.forces]

            logging.debug(f"At time {t:.2f}, sizes: {sizes}, fronts: {front_sizes}, coefs: {coef}, morale: {self.casualties['morale'].tolist()}")

            # casualties per minute suffered by each side (non-negative)
            casualty = [
                abs(Simulation._compute_rate(self.forces[i], sizes, coef, front_sizes, i))
                * kill_rate[self.forces[i].effective_law]
                for i in (0, 1)
            ]

            # rate 0 means the other side cannot inflict casualties (e.g. melee-only unit at range)
            clocks = [self.rng.exponential(r) if r > 0 else float('inf') for r in casualty]

            # a side is engaged if it is firing (the enemy is taking casualties) or under fire
            engaged = [casualty[i] > 0 or casualty[1 - i] > 0 for i in (0, 1)]

            # neither side can inflict casualties: nothing more will happen
            if min(clocks) == float('inf'):
                break

            # the next casualty falls after the time limit: let morale run to the limit and stop
            if t + min(clocks) >= time:
                for i in (0, 1):
                    self.morale_states[i].advance(time - t, engaged=engaged[i])
                    self._sync_morale(i)
                t = time
                rows.append(self._row(t))
                break

            dt = min(clocks)
            t += dt
            victim = int(np.argmin(clocks))

            for i in (0, 1):
                self.morale_states[i].advance(dt, engaged=engaged[i])

            self.forces[victim].update_size(sizes[victim] - 1)
            self.casualties['losses'][victim] += 1
            self.morale_states[victim].take_loss(firing_back=casualty[1 - victim] > 0)
            self.morale_states[1 - victim].inflict_loss(enemy_initial_size=self.casualties['initial_size'][victim])

            for i in (0, 1):
                self._sync_morale(i)
            rows.append(self._row(t))

            if self.forces[victim].size == 0:
                logging.info(f"Simulation ended at {t:.1f} min: a regiment was wiped out. Final sizes: {[r.size for r in self.forces]}")
                break
            if any(state.broken for state in self.morale_states):
                logging.info(f"Simulation ended at {t:.1f} min: a regiment broke. Final sizes: {[r.size for r in self.forces]}")
                break

        if rows:
            self.sim_output = pd.concat([self.sim_output, pd.DataFrame(rows)], ignore_index=True)

if __name__ == "__main__":  # pragma: no cover
    reg1 = Regiment(4000, '4/4/0/0')
    reg2 = Regiment(3500, '4/6/1/0')

    sim = Simulation((reg1, reg2), rng=Rng(42))
    sim.run_simulation(time=90)
    print(sim)
