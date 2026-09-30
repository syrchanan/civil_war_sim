"""
Round-based battle engine with per-regiment orders (roadmap A4 + A5).

Each round every regiment gets one order: a target and a mode (ranged / melee / idle). Orders form a targeting
graph: at most one outgoing arrow per unit (its target), any number of incoming arrows (its attackers).

- Ranged fire is one-way along the arrow.
- Melee is mutual and forcing: a melee order creates a two-way contact, and a unit in any contact fights only in
  melee (its ranged order waits).
- In melee, exposure is the whole front and fighting strength is divided: each attacker hits the defender's full
  front, while a unit's own fighters are split across its contacts in proportion to their fronts.

All arrows run in one continuous-time Markov chain: the next casualty arrives after Exp(sum of rates), and the
arrow that caused it is chosen by a uniform draw weighted by rate. Arrows are ordered by (target, attacker) in
unit order, so a one-on-one battle draws exactly like ``Simulation``.
"""

import secrets
from dataclasses import dataclass

from imperial_generals.battles.morale import MoraleState
from imperial_generals.params import BattleParams
from imperial_generals.units import Regiment
from imperial_generals.utils import Rng

MODES = frozenset({'idle', 'ranged', 'melee'})


@dataclass(frozen=True)
class Order:
    """One regiment's order for a round: whom it targets and how."""

    target: str | None = None
    mode: str = 'idle'

    def __post_init__(self) -> None:
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {sorted(MODES)}, got {self.mode!r}.")
        if self.mode == 'idle' and self.target is not None:
            raise ValueError("An idle order has no target.")
        if self.mode != 'idle' and self.target is None:
            raise ValueError(f"A {self.mode} order needs a target.")

    @classmethod
    def coerce(cls, value) -> 'Order':
        """Accept an Order, a dict like ``{'target': 'x', 'mode': 'ranged'}``, or None (idle)."""
        if isinstance(value, Order):
            return value
        if value is None:
            return cls()
        if isinstance(value, dict):
            return cls(**value)
        raise TypeError(f"An order must be an Order, dict or None, got {type(value).__name__}.")


@dataclass(frozen=True)
class Engagement:
    """One arrow of the targeting graph with its current casualty rate (casualties per minute on the target)."""

    attacker: str
    target: str
    mode: str
    rate: float


@dataclass(frozen=True)
class CasualtyEvent:
    time: float
    attacker: str
    target: str


@dataclass(frozen=True)
class UnitReport:
    losses: int
    inflicted: int
    size: int
    morale: float
    broken: bool
    broke_at: float | None      # game minute it broke, if it broke this round


@dataclass(frozen=True)
class RoundReport:
    round: int
    start: float
    end: float
    engagements: tuple          # Engagement arrows at the start of the round
    units: dict                 # uid -> UnitReport
    events: tuple = ()          # CasualtyEvent per casualty, when record_events=True


@dataclass
class BattleUnit:
    uid: str
    side: int
    regiment: Regiment
    morale: MoraleState
    initial_size: int
    index: int
    losses: int = 0
    inflicted: int = 0

    @property
    def size(self) -> int:
        return self.regiment.size

    @property
    def front(self) -> int:
        return min(self.regiment.size, self.regiment.front_size)

    @property
    def active(self) -> bool:
        """Can act: not broken and not wiped out."""
        return self.regiment.size > 0 and not self.morale.broken


class Battle:
    """
    A battle between two sides, fought in rounds.

    Parameters
    ----------
    units : dict[str, tuple[int, Regiment]]
        Unit id -> (side 0 or 1, regiment). Dict order is the unit order used for tie-breaking and draws.
    rng : Rng, optional
        Seeded generator; defaults to a randomly seeded Rng.
    params : BattleParams, optional
        Per-battle constants; defaults to config.
    """

    def __init__(self, units: dict, rng: Rng | None = None, params: BattleParams | None = None) -> None:
        if rng is not None and not isinstance(rng, Rng):
            raise TypeError(f"rng must be an Rng instance, got {type(rng).__name__}.")
        if params is not None and not isinstance(params, BattleParams):
            raise TypeError(f"params must be a BattleParams instance, got {type(params).__name__}.")
        self.rng: Rng = rng if rng is not None else Rng(secrets.randbits(32))
        self.params: BattleParams = params if params is not None else BattleParams()

        self.units: dict[str, BattleUnit] = {}
        for index, (uid, (side, regiment)) in enumerate(units.items()):
            if side not in (0, 1):
                raise ValueError(f"side must be 0 or 1, got {side!r} for {uid!r}.")
            if not isinstance(regiment, Regiment):
                raise TypeError(f"{uid!r} must be a Regiment, got {type(regiment).__name__}.")
            morale = MoraleState(size=regiment.size, xp=regiment.stats[0], morale_stat=regiment.stats[1],
                                 params=self.params.morale)
            self.units[uid] = BattleUnit(uid, side, regiment, morale, regiment.size, index)

        self.time: float = 0.0
        self.round: int = 0
        self.history: list[RoundReport] = []
        self._broken_before_round: set[str] = set()

    # -------------------------------------------------------------------------
    # Orders and the targeting graph
    # -------------------------------------------------------------------------

    def _validate_orders(self, orders: dict) -> dict[str, Order]:
        if not isinstance(orders, dict):
            raise TypeError(f"orders must be a dict, got {type(orders).__name__}.")
        valid = {}
        for uid, value in orders.items():
            if uid not in self.units:
                raise ValueError(f"Unknown unit {uid!r} in orders.")
            order = Order.coerce(value)
            if order.mode == 'idle':
                continue
            unit = self.units[uid]
            if not unit.active:
                raise ValueError(f"{uid!r} is broken or wiped out and can't act.")
            if order.target not in self.units:
                raise ValueError(f"{uid!r} targets unknown unit {order.target!r}.")
            target = self.units[order.target]
            if target.side == unit.side:
                raise ValueError(f"{uid!r} can't target {order.target!r}: same side.")
            if target.size == 0:
                raise ValueError(f"{uid!r} targets {order.target!r}, which is wiped out.")
            valid[uid] = order
        return valid

    def _plan(self, orders: dict[str, Order], cancelled: set) -> tuple:
        """
        The arrow structure for validated orders, minus attackers stood down this round.

        Returns ``(slots, contacts)``: ``slots`` are ``(attacker, target, mode)`` sorted by (target, attacker) in
        unit order; ``contacts`` maps each unit in melee to its contact partners. The structure only changes when a
        unit breaks or is wiped out, so the round loop rebuilds it then and otherwise just recomputes rates.
        """
        units = self.units
        combat = self.params.combat
        live = {
            uid: order for uid, order in orders.items()
            if uid not in cancelled and units[uid].active and units[order.target].size > 0
        }

        # melee contacts are mutual: a charge puts both units in contact with each other
        contacts: dict[str, list[str]] = {}
        for uid, order in live.items():
            if order.mode == 'melee':
                for a, b in ((uid, order.target), (order.target, uid)):
                    partners = contacts.setdefault(a, [])
                    if b not in partners:
                        partners.append(b)

        slots = []
        for uid, partners in contacts.items():
            unit = units[uid]
            # a broken unit in contact doesn't fight back; coef > 0 in melee for every valid unit
            if unit.active and combat.unit_coef(unit.regiment.stats, 'melee') > 0:
                slots.extend((uid, p, 'melee') for p in partners)
        for uid, order in live.items():
            # a unit in melee doesn't fire its ranged order; a melee-only unit can't fire at all
            if order.mode == 'ranged' and uid not in contacts \
                    and combat.unit_coef(units[uid].regiment.stats, 'ranged') > 0:
                slots.append((uid, order.target, 'ranged'))

        slots.sort(key=lambda s: (units[s[1]].index, units[s[0]].index))
        return slots, contacts

    def _rates(self, slots: list, contacts: dict) -> list:
        """Current ``(attacker, target, mode, rate)`` for each slot with a positive rate."""
        units = self.units
        combat = self.params.combat
        total_fronts = {uid: sum(units[p].front for p in partners) for uid, partners in contacts.items()}
        arrows = []
        for attacker, target, mode in slots:
            unit = units[attacker]
            c = combat.unit_coef(unit.regiment.stats, mode)
            if mode == 'melee':
                total_front = total_fronts[attacker]
                if total_front <= 0:
                    continue
                front_t = units[target].front
                # fighters split in proportion to contact fronts; the target is exposed along its whole front
                rate = combat.melee_kill_rate * c * unit.front * (front_t / total_front) * front_t
            else:
                # (coef * size) * kill_rate: same operation order as Simulation, for bit-identical 1-v-1 draws
                rate = c * unit.size * combat.ranged_kill_rate
            if rate > 0:
                arrows.append((attacker, target, mode, rate))
        return arrows

    def engagements(self, orders: dict) -> tuple:
        """Preview the arrows and their current casualty rates for these orders (no dice rolled)."""
        return tuple(Engagement(*a) for a in self._rates(*self._plan(self._validate_orders(orders), set())))

    # -------------------------------------------------------------------------
    # Rounds
    # -------------------------------------------------------------------------

    def _advance(self, minutes: float, engaged: set) -> None:
        for uid, unit in self.units.items():
            unit.morale.advance(minutes, engaged=uid in engaged)

    def _sync(self, uids) -> None:
        for uid in uids:
            unit = self.units[uid]
            unit.regiment.update_raw_morale(float(unit.morale.morale))

    def _newly_broken(self, candidates, broke_at: dict, t: float) -> set:
        """Units among ``candidates`` that broke since last checked; records when in ``broke_at``."""
        gone = set()
        for uid in candidates:
            if uid not in broke_at and uid not in self._broken_before_round and self.units[uid].morale.broken:
                broke_at[uid] = t
                gone.add(uid)
        return gone

    def resolve_round(self, duration: float, orders: dict, record_events: bool = False) -> RoundReport:
        """
        Fight one round of ``duration`` game minutes under ``orders`` and return its report.

        Units left out of ``orders`` are idle. When a unit breaks or is wiped out, the units targeting it stand down
        for the rest of the round. Broken units can be targeted (pursued) but don't fight back.
        """
        if not duration > 0:
            raise ValueError(f"duration must be > 0, got {duration}.")
        valid = self._validate_orders(orders)

        self.round += 1
        start = self.time
        end = start + duration
        before = {uid: (u.losses, u.inflicted) for uid, u in self.units.items()}
        self._broken_before_round = {uid for uid, u in self.units.items() if u.morale.broken}
        broke_at: dict[str, float] = {}
        cancelled: set[str] = set()
        events = []
        slots, contacts = self._plan(valid, cancelled)
        opening = tuple(Engagement(*a) for a in self._rates(slots, contacts))

        t = start
        while t < end:
            arrows = self._rates(slots, contacts)
            total_rate = 0.0
            engaged = set()
            attackers = set()
            for attacker_id, target_id, _, rate in arrows:
                total_rate += rate
                attackers.add(attacker_id)
                engaged.add(attacker_id)
                engaged.add(target_id)

            if total_rate == 0:
                self._advance(end - t, engaged)
                t = end
                break

            dt = self.rng.exponential(total_rate)
            if t + dt >= end:
                self._advance(end - t, engaged)
                self._sync(engaged)
                t = end
                self._newly_broken(engaged, broke_at, t)
                break

            # weighted pick of the arrow that caused this casualty
            pick = self.rng.random() * total_rate
            cumulative = 0.0
            chosen = arrows[-1]
            for arrow in arrows:
                cumulative += arrow[3]
                if pick < cumulative:
                    chosen = arrow
                    break

            t += dt
            self._advance(dt, engaged)

            victim = self.units[chosen[1]]
            attacker = self.units[chosen[0]]
            victim.regiment.update_size(victim.size - 1)
            victim.losses += 1
            attacker.inflicted += 1
            victim.morale.take_loss(firing_back=victim.uid in attackers)
            attacker.morale.inflict_loss(enemy_initial_size=victim.initial_size)
            self._sync(engaged)

            if record_events:
                events.append(CasualtyEvent(t, attacker.uid, victim.uid))

            # a unit can break from its losses or from the in-combat drain; either way (or if wiped out)
            # its attackers stand down and the arrow structure is rebuilt
            gone = self._newly_broken(engaged, broke_at, t)
            if victim.size == 0:
                gone.add(victim.uid)
            if gone:
                cancelled.update(uid for uid, order in valid.items() if order.target in gone)
                slots, contacts = self._plan(valid, cancelled)

        self.time = end
        report = RoundReport(
            round=self.round,
            start=start,
            end=end,
            engagements=opening,
            units={
                uid: UnitReport(
                    losses=u.losses - before[uid][0],
                    inflicted=u.inflicted - before[uid][1],
                    size=u.size,
                    morale=float(u.morale.morale),
                    broken=u.morale.broken,
                    broke_at=broke_at.get(uid),
                )
                for uid, u in self.units.items()
            },
            events=tuple(events),
        )
        self.history.append(report)
        return report
