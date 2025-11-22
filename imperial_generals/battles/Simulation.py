# class to handle the lanchester simulations and markov chain simulations

# base libs
import logging
from typing import Tuple

# ext libs
import numpy as np
import pandas as pd

# local imports
from imperial_generals.units import Regiment

class Simulation:
    """
    Handles Lanchester and Markov chain simulations for two opposing regiments.

    Attributes:
        forces (Tuple[Regiment, Regiment]): The two opposing Regiment instances.
        rate_funcs (Tuple[callable, callable]): Tuple of rate functions for each regiment (set after build_lanch_diffeq).
        casualties (dict[str, tuple[int, int] | np.ndarray]):
            Tracks initial sizes, current losses, and morale for both regiments.
            Keys:
                - 'initial_size': tuple[int, int]
                - 'losses': np.ndarray
                - 'morale': tuple[int, int]
        sim_output pd.DataFrame: Tracks simulation time, sizes, and morale history.
    """

    def __init__(self, forces: Tuple[Regiment, Regiment]):
        """
        Initialize the Simulation with two regiments.

        Args:
            forces (Tuple[Regiment, Regiment]): The two opposing Regiment instances.

        Sets:
            self.forces: Tuple[Regiment, Regiment]
            self.rate_funcs: Tuple[callable, callable] | None
            self.casualties: dict[str, list[int, int] | np.ndarray]
                - 'initial_size': list[int, int]
                - 'losses': np.ndarray
                - 'morale': np.ndarray
            self.sim_output: pd.DataFrame
        """
        self.forces: Tuple[Regiment, Regiment] = forces
        self.rate_funcs: Tuple[callable, callable] | None = None

        reg1, reg2 = forces
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
        losses = self.casualties['losses'] if hasattr(self, 'casualties') else 'N/A'
        return (
            f"Simulation(forces={[str(f) for f in self.forces]}, "
            f"rate_funcs={'set' if self.rate_funcs else 'unset'}, "
            f"losses={losses.tolist() if isinstance(losses, np.ndarray) else losses})"
        )

    def __repr__(self) -> str:
        losses = self.casualties['losses'] if hasattr(self, 'casualties') else 'N/A'
        return (
            f"Simulation(forces={self.forces!r}, "
            f"rate_funcs={self.rate_funcs!r}, "
            f"losses={losses.tolist() if isinstance(losses, np.ndarray) else losses})"
        )

    # Internal method to create Lanchester differential equations
    @staticmethod
    def _lanchester_diffeq(
        regiment: Regiment, opponent: Regiment
    ) -> callable:
        """
        Create a rate function for a Regiment according to its Lanchester law.

        Args:
            regiment (Regiment): The Regiment for which to compute the rate.
            opponent (Regiment): The opposing Regiment.

        Returns:
            callable: A function computing the rate of change.

        Raises:
            ValueError: If the Regiment's law type is not recognized.
        """
        logging.debug(f"Building Lanchester diffeq for {regiment} vs {opponent}")
        if regiment.law == 'ln':
            # TODO - fix equation, should be linear, so -coef * size of battle front (engaged units). 
            # will need to add front-size as attribute to Regiment to scale based on how many units are engaged
            return lambda sizes, coef, idx: -coef[1 - idx] * sizes[0] * sizes[1 - idx]
        elif regiment.law == 'sq':
            return lambda sizes, coef, idx: -coef[1 - idx] * sizes[1 - idx]
        else:
            raise ValueError(f"Unknown Lanchester law: {regiment.law}")

    # Public method to build Lanchester differential equations for the simulation
    def build_lanch_diffeq(self) -> None:
        """
        Build and store Lanchester differential equation rate functions for the two regiments.

        Raises:
            ValueError: If forces are not a tuple of two Regiment instances or missing required attributes.
        """
        logging.info("Building Lanchester differential equations for simulation.")
        if (
            not isinstance(self.forces, tuple)
            or len(self.forces) != 2
            or not all(isinstance(r, Regiment) for r in self.forces)
        ):
            raise ValueError("forces must be a tuple of two Regiment instances.")

        reg1, reg2 = self.forces

        for reg in (reg1, reg2):
            if not hasattr(reg, "law") or not hasattr(reg, "coef") or not hasattr(reg, "size"):
                raise ValueError("Each Regiment must have 'law', 'coef', and 'size' attributes.")

        self.rate_funcs = (
            Simulation._lanchester_diffeq(reg1, reg2),
            Simulation._lanchester_diffeq(reg2, reg1)
        )

    # Private method to update internal casualties value for dynamic morale tracking
    def update_morale_losses(self, delta_t: float) -> None:
        """
        ▪ Rule A: Casualties Sustained (Morale Falls):
            • Calculate loss_percentage = B_casualties_taken_this_step / previous_B_soldiers. (Handle division by zero if previous_B_soldiers is 0).
            • morale_change_for_B = morale_change_for_B - (loss_percentage * Morale_Loss_Constant_1)
            • (Rationale: A unit taking losses will experience a drop in morale. The previous_B_soldiers provides a stable baseline for this percentage calculation.)
        ▪ Rule B: Casualties Inflicted (Morale Rises):
            • Calculate infliction_percentage = R_casualties_taken_this_step / previous_R_soldiers. (Handle division by zero if previous_R_soldiers is 0).
            • morale_change_for_B = morale_change_for_B + (infliction_percentage * Morale_Gain_Constant_1)
            • (Rationale: Successfully inflicting casualties boosts morale, reflecting "High-spirited, eager" or "Patriotic exuberance!".)
        ▪ Rule C: Faster Casualties Sustained (More Morale Falls):
            • Calculate casualties_per_unit_time_taken = B_casualties_taken_this_step / delta_t. (Handle delta_t being zero or extremely small to avoid Inf or NaN; you might cap this value or add a small epsilon to delta_t).
            • morale_change_for_B = morale_change_for_B - (casualties_per_unit_time_taken * Morale_Loss_Constant_2)
            • (Rationale: Rapid, heavy losses are more demoralizing than slow attrition, even for the same total casualty count. This reflects the "shaken, shell-shocked" state.)
        ▪ Rule D: Faster Casualties Inflicted (Faster Morale Rises):
            • Calculate casualties_per_unit_time_inflicted = R_casualties_taken_this_step / delta_t. (Handle delta_t being zero or extremely small).
            • morale_change_for_B = morale_change_for_B + (casualties_per_unit_time_inflicted * Morale_Gain_Constant_2)
            • (Rationale: A rapid, successful advance or defense significantly boosts a unit's spirit.)
        """

        MORALE_LOSS_CONSTANT_A = 0.00007 # Rule A: Casualties Sustained
        MORALE_GAIN_CONSTANT_B = 0.00005 # Rule B: Casualties Inflicted
        MORALE_LOSS_CONSTANT_C = 0.0000040 # Rule C: Faster Casualties Sustained
        MORALE_GAIN_CONSTANT_D = 0.0000040 # Rule D: Faster Casualties Inflicted

        morale_changes = [0.0, 0.0]  # Initialize morale changes for both sides

        # Loop through each side to calculate morale changes
        for side in range(2):

            # indentify casualties taken and inflicted
            casualties_taken = self.casualties['losses'][side]
            casualties_inflicted = self.casualties['losses'][1 - side]

            # Rule A: Casualties Sustained (Morale Falls)
            infliction_percentage = casualties_taken / max(self.casualties['initial_size'][side], 1)  # Avoid division by zero
            morale_changes[side] -= infliction_percentage * MORALE_LOSS_CONSTANT_A

            # Rule B: Casualties Inflicted (Morale Rises)
            infliction_percentage = casualties_inflicted / max(self.casualties['initial_size'][1 - side], 1)  # Avoid division by zero
            morale_changes[side] += infliction_percentage * MORALE_GAIN_CONSTANT_B

            # Rule C: Faster Casualties Sustained (More Morale Falls)
            casualties_per_unit_time_taken = casualties_taken / (1 + delta_t) # Avoid division by zero
            morale_changes[side] -= casualties_per_unit_time_taken * MORALE_LOSS_CONSTANT_C

            # Rule D: Faster Casualties Inflicted (Faster Morale Rises)
            casualties_per_unit_time_inflicted = casualties_inflicted / (1 + delta_t)
            morale_changes[side] += casualties_per_unit_time_inflicted * MORALE_GAIN_CONSTANT_D

        # Update the morale in the casualties dictionary and Regiment instances
        for side in range(2):
            new_morale = self.casualties['morale'][side] + morale_changes[side]
            
            # Ensure morale stays within bounds [10, 100] (1-10 scale from rules, multiplied by 10)
            self.casualties['morale'][side] = max(10, min(100, new_morale))
            self.forces[side].update_raw_morale(self.casualties['morale'][side])


    def run_simulation(self, time: int) -> None:

        if self.rate_funcs is None:
            self.build_lanch_diffeq()

        # deconstruct forces
        reg1, reg2 = self.forces

        # Init local time
        t = self.sim_output.loc[0, 'time']

        while t < time:

            sizes = [reg1.size, reg2.size]
            coef = [reg1.coef, reg2.coef]

            logging.debug(f"At time {t:.2f}, sizes: {sizes}, coefs: {coef}, morale: {self.casualties['morale'].tolist()}, stats: {reg1.stats}, {reg2.stats}")

            # returns casualties on each side
            full_casualties = [self.rate_funcs[i](sizes, coef, i) for i in (0, 1)]
            
            # get amount of casualties
            casualty = [abs(d) for d in full_casualties]

            # get direction (should be negative unless reinforcements are involved)
            dir = [1 if d >= 0 else -1 for d in full_casualties]

            # `exponential` here introduces the randomness and continuous-time aspect to the Markov chain by sampling the time to the next event from an exponential distribution, where the rate of that distribution is determined by the current casualty rates calculated from the Lanchester equations -- allowing for the simulation to model the inherently unpredictable nature of combat
            clocks = [np.random.exponential(scale=1/r) for r in casualty]

            # replace any NA in clocks with infinity
            clocks = [c if c == c else float('inf') for c in clocks]

            # increment time by the minimum clock
            t += min(clocks)

            # few steps:
                #  1) figure out which side had the fastest time to trigger an event
                #  2) tabulate to get a vector of same length as init with 1 on side it occurred
                #  3) multiply the dir by that side to get directionality
                #  4) add to init vector, killing 1st man from fastest side
            tab = np.array([0, 0])
            tab[np.argmin(clocks)] = 1
            sizes = (np.array(sizes) + dir * tab).tolist()
            
            # update reg sizes in Regiment instances
            reg1.update_size(sizes[0])
            reg2.update_size(sizes[1])

            # update regiment losses - if < 0, set to 0 else add to losses
            if all(d <= 0 for d in dir):
                self.casualties['losses'] += tab

            # update coefficients for next loop iteration based on casualties taken and initial size
            # passing time - t for delta_t to get time left in step, this way as delta_t approaches 0, the faster casualty rules have more impact (since formula is casualties / (1 + delta_t))
            self.update_morale_losses(time-t)

            # log current state to sim_output by adding a new row
            new_row = {
                'time': t,
                'size_1': sizes[0],
                'size_2': sizes[1],
                'morale_1': self.casualties['morale'][0],
                'morale_2': self.casualties['morale'][1]
            }
            self.sim_output = pd.concat([self.sim_output, pd.DataFrame([new_row])], ignore_index=True)

            # short circuit if either side is wiped out
            if np.any(np.array(sizes) == 0) or np.any(self.casualties['morale'] <= 10):
                if np.any(np.array(sizes) == 0):
                    logging.info(f"Simulation ended at time {t:.2f} due to a regiment being wiped out. Final sizes: {sizes}")
                else:
                    logging.info(f"Simulation ended at time {t:.2f} due to a regiment's morale dropping to minimum. Final morale: {self.casualties['morale'].tolist()}")
                break

if __name__ == "__main__":
    reg1 = Regiment(4000, '4/4/0/0', 'sq')
    reg2 = Regiment(3500, '4/6/1/0', 'sq')

    sim = Simulation((reg1, reg2))
    sim.run_simulation(time=1)
    print(sim)
