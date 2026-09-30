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
from dataclasses import dataclass, field

from imperial_generals.battles.morale import MoraleState
from imperial_generals.params import BattleParams
from imperial_generals.units import ArtilleryBattery, CavalryRegiment, Regiment
from imperial_generals.utils import Rng

MODES = frozenset({'idle', 'ranged', 'melee'})


@dataclass(frozen=True)
class Order:
    """
    One regiment's order for a round: whom it targets and how. Artillery may name its ``ammo`` (e.g. 'round_shot',
    'shell', 'canister'); it is fixed for the round, and defaults to ``artillery_default_ammo``.
    """

    target: str | None = None
    mode: str = 'idle'
    ammo: str | None = None

    def __post_init__(self) -> None:
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {sorted(MODES)}, got {self.mode!r}.")
        if self.mode == 'idle' and self.target is not None:
            raise ValueError("An idle order has no target.")
        if self.mode != 'idle' and self.target is None:
            raise ValueError(f"A {self.mode} order needs a target.")
        if self.ammo is not None and self.mode != 'ranged':
            raise ValueError("Only a ranged order can choose ammo.")

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
    losses: int                 # men hit by fire this round (killed or wounded; split in Battle.finish)
    inflicted: int
    size: int
    morale: float
    broken: bool
    broke_at: float | None      # game minute it broke, if it broke this round
    captured: int = 0           # men taken prisoner as it routed this round


@dataclass(frozen=True)
class RoundReport:
    round: int
    start: float
    end: float
    engagements: tuple          # Engagement arrows at the start of the round
    units: dict                 # uid -> UnitReport
    events: tuple = ()          # CasualtyEvent per casualty, when record_events=True
    prisoners: dict = field(default_factory=lambda: {0: 0, 1: 0})   # side -> prisoners taken this round


@dataclass(frozen=True)
class UnitOutcome:
    """One unit's casualty accounting once the battle is over."""

    hits: int                   # men hit by fire over the whole battle
    killed: int
    wounded: int
    walking_wounded: int        # losing side only: wounded who left with their unit
    wounded_captured: int       # losing side only: left-behind wounded taken by the field holder
    wounded_returned: int       # wounded who recover and rejoin (added back to strength)
    captured_in_rout: int       # taken prisoner as the unit broke
    final_size: int


@dataclass(frozen=True)
class BattleResult:
    field_held_by: int | None
    units: dict                 # uid -> UnitOutcome
    prisoners: dict             # side -> prisoners taken over the whole battle


@dataclass
class BattleUnit:
    uid: str
    side: int
    regiment: Regiment
    morale: MoraleState
    initial_size: int
    index: int
    key: tuple = ('inf', None)       # (unit type, subtype | None) for matchups; plain Regiment = infantry
    melee_rating: float = 0.0
    losses: int = 0
    inflicted: int = 0
    captured: int = 0

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
            key = (getattr(regiment, 'unit_type', 'inf'), getattr(regiment, 'subtype', None))
            self.units[uid] = BattleUnit(uid, side, regiment, morale, regiment.size, index, key=key,
                                         melee_rating=self.params.matchups.melee_rating(key))

        self.time: float = 0.0
        self.round: int = 0
        self.history: list[RoundReport] = []
        self.prisoners: dict[int, int] = {0: 0, 1: 0}
        self.finished: bool = False
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
            if order.ammo is not None:
                if not isinstance(unit.regiment, ArtilleryBattery):
                    raise ValueError(f"{uid!r} isn't artillery and can't choose ammo.")
                if order.ammo not in self.params.combat.artillery_ammo:
                    raise ValueError(f"{uid!r}: unknown ammo {order.ammo!r}; "
                                     f"one of {sorted(self.params.combat.artillery_ammo)}.")
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

        matchups = self.params.matchups
        slots = []
        for uid, partners in contacts.items():
            unit = units[uid]
            # a broken unit in contact doesn't fight back
            if unit.active and unit.melee_rating > 0:
                order = live.get(uid)
                for p in partners:
                    # a cavalry charge: cavalry whose own melee order targets this infantry unit
                    charge = (unit.key[0] == 'cav' and units[p].key[0] == 'inf'
                              and order is not None and order.mode == 'melee' and order.target == p)
                    slots.append((uid, p, 'melee', matchups.multiplier(unit.key, units[p].key, 'melee'),
                                  charge, None))
        for uid, order in live.items():
            # a unit in melee doesn't fire its ranged order; a melee-only unit (stats flag) can't fire at all
            if order.mode == 'ranged' and uid not in contacts \
                    and combat.unit_coef(units[uid].regiment.stats, 'ranged') > 0:
                # artillery: per-gun rate of the ordered ammo, fixed for the round
                gun_rate = None
                if isinstance(units[uid].regiment, ArtilleryBattery):
                    gun_rate = combat.artillery_ammo[order.ammo or combat.artillery_default_ammo]
                slots.append((uid, order.target, 'ranged',
                              matchups.multiplier(units[uid].key, units[order.target].key, 'ranged'),
                              False, gun_rate))

        slots.sort(key=lambda s: (units[s[1]].index, units[s[0]].index))
        return slots, contacts

    def _rates(self, slots: list, contacts: dict) -> list:
        """Current ``(attacker, target, mode, rate)`` for each slot with a positive rate."""
        units = self.units
        combat = self.params.combat
        total_fronts = {uid: sum(units[p].front for p in partners) for uid, partners in contacts.items()}
        arrows = []
        for attacker, target, mode, matchup, charge, gun_rate in slots:
            unit = units[attacker]
            stats = unit.regiment.stats
            if mode == 'melee':
                total_front = total_fronts[attacker]
                if total_front <= 0:
                    continue
                # melee strength from the subtype's rating, not the firearm
                c = combat.melee_efficiency(stats[0], stats[1], unit.melee_rating)
                if charge:
                    # depends on the infantry's current resolve, shock and numbers, so evaluated per event
                    inf = units[target]
                    matchup = matchup * self.params.matchups.charge_factor(
                        unit.size, inf.size, inf.morale.resolve, inf.regiment.stats[0], inf.morale.shock)
                front_t = units[target].front
                # fighters split in proportion to contact fronts; the target is exposed along its whole front
                rate = combat.melee_kill_rate * c * unit.front * (front_t / total_front) * front_t * matchup
            elif gun_rate is not None:
                # artillery fires per manned gun, at the rate of the ammo it was ordered to use
                c = combat.unit_coef(stats, 'ranged')
                rate = c * unit.regiment.effective_guns * gun_rate * matchup
            else:
                c = combat.unit_coef(stats, 'ranged')
                # (coef * size) * kill_rate first: same operation order as Simulation, for bit-identical
                # 1-v-1 draws (the infantry-v-infantry matchup is 1.0, an exact multiply)
                rate = c * unit.size * combat.ranged_kill_rate * matchup
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

    def _draw_count(self, mean_share: float, n: int) -> int:
        """
        Semi-random whole-number share of ``n`` men: share = mean × (1 ± share_spread) from one uniform draw,
        clamped to [0, 1], then rounded half up.
        """
        spread = self.params.aftermath.share_spread
        share = mean_share * (1 + spread * (2 * self.rng.random() - 1))
        share = min(1.0, max(0.0, share))
        return int(share * n + 0.5)

    def _rout(self, gone: set, arrows: list, prisoners: dict) -> None:
        """Take prisoners from units that just broke (more if enemy cavalry is attacking them)."""
        after = self.params.aftermath
        for uid in sorted(gone, key=lambda u: self.units[u].index):
            unit = self.units[uid]
            if not unit.morale.broken or unit.size == 0:
                continue
            cavalry = any(a[1] == uid and isinstance(self.units[a[0]].regiment, CavalryRegiment) for a in arrows)
            mean = min(1.0, after.rout_capture_share * (after.cavalry_capture_multiplier if cavalry else 1.0))
            taken = self._draw_count(mean, unit.size)
            unit.regiment.update_size(unit.size - taken)
            unit.captured += taken
            prisoners[1 - unit.side] += taken
            self.prisoners[1 - unit.side] += taken

    def resolve_round(self, duration: float, orders: dict, record_events: bool = False) -> RoundReport:
        """
        Fight one round of ``duration`` game minutes under ``orders`` and return its report.

        Units left out of ``orders`` are idle. When a unit breaks or is wiped out, the units targeting it stand down
        for the rest of the round. A unit that breaks loses a share of its remaining men as prisoners (more if
        enemy cavalry is attacking it). Broken units can be targeted (pursued) but don't fight back.
        """
        if self.finished:
            raise RuntimeError("This battle is finished.")
        if not duration > 0:
            raise ValueError(f"duration must be > 0, got {duration}.")
        valid = self._validate_orders(orders)

        self.round += 1
        start = self.time
        end = start + duration
        before = {uid: (u.losses, u.inflicted, u.captured) for uid, u in self.units.items()}
        prisoners = {0: 0, 1: 0}
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
                self._rout(self._newly_broken(engaged, broke_at, t), arrows, prisoners)
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
            self._rout(gone, arrows, prisoners)
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
                    captured=u.captured - before[uid][2],
                )
                for uid, u in self.units.items()
            },
            events=tuple(events),
            prisoners=prisoners,
        )
        self.history.append(report)
        return report

    # -------------------------------------------------------------------------
    # After the battle
    # -------------------------------------------------------------------------

    def _auto_field_holder(self) -> int | None:
        """The side still standing when every unit of the other side is broken or wiped out; else None."""
        out = {side: all(not u.active for u in self.units.values() if u.side == side) for side in (0, 1)}
        if out[1] and not out[0]:
            return 0
        if out[0] and not out[1]:
            return 1
        return None

    def finish(self, field_held_by='auto') -> BattleResult:
        """
        End the battle and settle its casualties.

        Men hit by fire split into killed and wounded. On the side that lost the field, some wounded leave with
        their unit (walking wounded) and a share of the rest are captured by the side holding it. A share of the
        wounded who weren't captured recover and rejoin, restoring the unit's strength. All shares are semi-random
        draws from the battle's seed.

        Parameters
        ----------
        field_held_by : 0, 1, None or 'auto'
            Side holding the field at the end. 'auto' picks the side still standing when the other is entirely
            broken or wiped out, else None (no wounded captured).

        Raises
        ------
        RuntimeError
            If the battle is already finished.
        ValueError
            If field_held_by is not 0, 1, None or 'auto'.
        """
        if self.finished:
            raise RuntimeError("This battle is already finished.")
        if field_held_by == 'auto':
            holder = self._auto_field_holder()
        elif field_held_by is None or (type(field_held_by) is int and field_held_by in (0, 1)):
            holder = field_held_by
        else:
            raise ValueError(f"field_held_by must be 0, 1, None or 'auto', got {field_held_by!r}.")

        after = self.params.aftermath
        outcomes = {}
        for uid, unit in self.units.items():
            hits = unit.losses
            killed = self._draw_count(after.killed_share, hits)
            wounded = hits - killed
            walking = captured = 0
            if holder is not None and unit.side != holder:
                walking = self._draw_count(after.walking_wounded_share, wounded)
                captured = self._draw_count(after.wounded_captured_share, wounded - walking)
                self.prisoners[holder] += captured
            returned = self._draw_count(after.wounded_return_share, wounded - captured)
            unit.regiment.update_size(unit.size + returned)
            outcomes[uid] = UnitOutcome(
                hits=hits, killed=killed, wounded=wounded, walking_wounded=walking, wounded_captured=captured,
                wounded_returned=returned, captured_in_rout=unit.captured, final_size=unit.size,
            )

        self.finished = True
        return BattleResult(field_held_by=holder, units=outcomes, prisoners=dict(self.prisoners))
