"""
Round-based battle engine with per-regiment orders (roadmap A4 + A5).

Each round every regiment gets one order: a target and a mode (ranged / melee / idle). Orders form a targeting
graph: at most one outgoing arrow per unit (its target), any number of incoming arrows (its attackers).

- Ranged fire is one-way along the arrow.
- Melee is mutual and forcing: a contact is two-way, and a unit in any contact fights only in melee (its ranged
  order waits).
- In melee, exposure is the whole front and fighting strength is divided: each attacker hits the defender's full
  front, while a unit's own fighters are split across its contacts in proportion to their fronts.

- A melee order on a unit not already in contact is a charge: the charger crosses the last stretch under the
  target's close-range fire, then a contact test decides whether it goes home, falters, or the defender breaks
  before contact. Contact persists across rounds while either unit keeps a melee order on the other.
- Melee casualties scale with the width in contact: min(attacker's men facing the target, target's front).
- An admin can give units modifiers for one round (e.g. 'uphill, fire -15%'): fire and melee scale the casualties
  the unit inflicts (closing fire counts as fire), morale scales what it spends from its morale budget.

All arrows run in one continuous-time Markov chain: the next casualty arrives after Exp(sum of rates), and the
arrow that caused it is chosen by a uniform draw weighted by rate. Approaches end at fixed times; the chain
simply restarts there (it is memoryless). Arrows are ordered by (target, attacker) in unit order, so a
one-on-one ranged battle draws exactly like ``Simulation``.
"""

import json
import secrets
from dataclasses import dataclass, field, replace

from imperial_generals.battles.morale import MoraleState, break_scale
from imperial_generals.params import BattleParams
from imperial_generals.units import ArtilleryBattery, CavalryRegiment, Regiment
from imperial_generals.utils import Rng

MODES = frozenset({'idle', 'ranged', 'melee'})
ORDER_KEYS = frozenset({'target', 'mode', 'ammo', 'on_break'})
# What a unit does when its target breaks, by mode; the first is the default.
ON_BREAK = {'ranged': ('keep', 'strongest', 'weakest'), 'melee': ('fall_back', 'pursue')}


@dataclass(frozen=True)
class Order:
    """
    One regiment's order for a round: whom it targets and how. Artillery may name its ``ammo`` (e.g. 'round_shot',
    'shell', 'canister'); it is fixed for the round, and defaults to ``artillery_default_ammo``.

    ``on_break`` says what the unit does when its target breaks (or is wiped out) during the round:
    - fire: 'keep' (default) firing on the broken unit; or switch to the 'strongest' / 'weakest' active enemy unit
      (men × share of morale budget left).
    - melee: 'fall_back' (default), leaving the broken unit; or 'pursue' it, staying in contact.
    """

    target: str | None = None
    mode: str = 'idle'
    ammo: str | None = None
    on_break: str | None = None

    def __post_init__(self) -> None:
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {sorted(MODES)}, got {self.mode!r}.")
        if self.mode == 'idle' and self.target is not None:
            raise ValueError("An idle order has no target.")
        if self.mode != 'idle' and self.target is None:
            raise ValueError(f"A {self.mode} order needs a target.")
        if self.ammo is not None and self.mode != 'ranged':
            raise ValueError("Only a ranged order can choose ammo.")
        if self.mode == 'idle':
            if self.on_break is not None:
                raise ValueError("An idle order has no on_break.")
        elif self.on_break is None:
            object.__setattr__(self, 'on_break', ON_BREAK[self.mode][0])
        elif self.on_break not in ON_BREAK[self.mode]:
            raise ValueError(f"on_break for a {self.mode} order must be one of {list(ON_BREAK[self.mode])}, "
                             f"got {self.on_break!r}.")

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
class Charge:
    """
    A melee order on a unit not already in contact, and how it ended.

    ``outcome``: 'home' (contact), 'faltered' (the charger stood down, shaken), 'defender_broke' (before contact),
    'meeting' (two units charging each other: contact, no test), 'pursuit' (the target was already broken:
    contact at once), 'charger_broke' / 'target_broke' (on the approach, from fire). The odds are those of the
    contact test, when one was rolled.
    """

    charger: str
    target: str
    start: float
    resolved_at: float
    outcome: str
    p_defender_breaks: float | None = None
    p_falter: float | None = None
    p_home: float | None = None


@dataclass(frozen=True)
class Retarget:
    """A firing unit switched to a new target (on_break 'strongest' / 'weakest') when its target broke or was wiped out."""

    unit: str
    old_target: str
    new_target: str
    time: float


MODIFIER_KEYS = ('fire', 'melee', 'morale')


def validate_modifiers(modifiers, units) -> dict:
    """
    Check one round's admin modifiers, ``{uid: {'fire', 'melee', 'morale', 'note'}}``: each a fraction from -1 to 1
    (-0.15 is -15%), all optional, plus a free-text note. Returns them complete (missing values 0, note '').

    Raises
    ------
    ValueError
        Naming the unit and what is wrong.
    """
    if not isinstance(modifiers, dict):
        raise ValueError(f"modifiers must be a mapping of unit id to modifiers, got {type(modifiers).__name__}.")
    checked = {}
    for uid, mod in modifiers.items():
        if uid not in units:
            raise ValueError(f"Unknown unit {uid} in modifiers.")
        if not isinstance(mod, dict):
            raise ValueError(f"{uid}: modifiers must be a mapping (fire, melee, morale, note).")
        unknown = sorted(k for k in mod if k not in (*MODIFIER_KEYS, 'note'))
        if unknown:
            raise ValueError(f"Unknown modifier(s) {unknown} for {uid}; use fire, melee, morale, note.")
        out = {}
        for key in MODIFIER_KEYS:
            value = mod.get(key, 0.0)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{uid}: {key} must be a number (a fraction, -0.15 for -15%), got {value!r}.")
            if not -1 <= value <= 1:
                raise ValueError(f"{uid}: {key} must be between -1 and 1 (-100% to +100%), got {value}.")
            out[key] = float(value)
        note = mod.get('note', '')
        if not isinstance(note, str):
            raise ValueError(f"{uid}: the note must be text, got {note!r}.")
        out['note'] = note
        checked[uid] = out
    return checked


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
    guns_lost: int = 0          # artillery: guns captured this round (overrun, or abandoned on breaking)


@dataclass(frozen=True)
class RoundReport:
    round: int
    start: float
    end: float
    engagements: tuple          # Engagement arrows at the start of the round
    units: dict                 # uid -> UnitReport
    events: tuple = ()          # CasualtyEvent per casualty, when record_events=True
    prisoners: dict = field(default_factory=lambda: {0: 0, 1: 0})   # side -> prisoners taken this round
    guns_captured: dict = field(default_factory=lambda: {0: 0, 1: 0})   # side -> enemy guns taken this round
    orders: dict = field(default_factory=dict)   # uid -> {'target', 'mode', 'ammo'} for units that acted
    charges: tuple = ()         # Charge per charge made this round
    retargets: tuple = ()       # Retarget per switch of target this round
    positions: dict = field(default_factory=dict)   # uid -> position (as saved) as the round began, for placed units
    modifiers: dict = field(default_factory=dict)   # uid -> admin modifiers for this round (fire, melee, morale, note)


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
    guns_lost: int = 0          # artillery: guns captured over the whole battle


@dataclass(frozen=True)
class BattleResult:
    field_held_by: int | None
    units: dict                 # uid -> UnitOutcome
    prisoners: dict             # side -> prisoners taken over the whole battle
    guns_captured: dict = field(default_factory=lambda: {0: 0, 1: 0})   # side -> enemy guns taken
    field_decided_by: str = 'admin'     # 'army_out' (a whole army broken), 'votes' or 'admin' (named in finish)
    field_votes: dict = field(default_factory=dict)     # test ('exchange', 'routs', 'standing') -> side or None


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
    name: str = ''
    meta: dict = field(default_factory=dict)     # free-form, round-tripped untouched (player, army ids, ...)
    initial_stats: tuple = ()
    losses: int = 0
    inflicted: int = 0
    captured: int = 0
    guns_lost: int = 0

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
    units : dict[str, tuple | dict]
        Unit id -> ``(side, regiment)`` or ``{'side', 'regiment', 'name'?, 'meta'?}``. Side is 0 or 1; name
        defaults to the id; meta is free-form and round-tripped untouched. Dict order is the unit order used for
        tie-breaking and draws.
    rng : Rng, optional
        Seeded generator; defaults to a randomly seeded Rng.
    params : BattleParams, optional
        Per-battle constants; defaults to config.
    meta : dict, optional
        Free-form battle details (name, date, location, ...), round-tripped untouched.
    """

    def __init__(self, units: dict, rng: Rng | None = None, params: BattleParams | None = None,
                 meta: dict | None = None) -> None:
        if rng is not None and not isinstance(rng, Rng):
            raise TypeError(f"rng must be an Rng instance, got {type(rng).__name__}.")
        if params is not None and not isinstance(params, BattleParams):
            raise TypeError(f"params must be a BattleParams instance, got {type(params).__name__}.")
        self.rng: Rng = rng if rng is not None else Rng(secrets.randbits(32))
        self.seed: int | None = self.rng.seed
        self.params: BattleParams = params if params is not None else BattleParams()
        self.meta: dict = dict(meta or {})

        self.units: dict[str, BattleUnit] = {}
        for index, (uid, spec) in enumerate(units.items()):
            if isinstance(spec, dict):
                if 'side' not in spec or 'regiment' not in spec:
                    raise ValueError(f"{uid!r} needs 'side' and 'regiment'.")
                side, regiment = spec['side'], spec['regiment']
                name, unit_meta = spec.get('name', uid), dict(spec.get('meta', {}))
            else:
                if len(spec) != 2:
                    raise ValueError(f"{uid!r} must be (side, regiment) or a dict.")
                (side, regiment), name, unit_meta = spec, uid, {}
            if side not in (0, 1):
                raise ValueError(f"side must be 0 or 1, got {side!r} for {uid!r}.")
            if not isinstance(regiment, Regiment):
                raise TypeError(f"{uid!r} must be a Regiment, got {type(regiment).__name__}.")
            # units differ: each draws a multiplier on its break point from the seed, in unit order
            spread = self.params.morale.break_point_spread
            scale = break_scale(self.rng.random(), spread) if spread > 0 else 1.0
            morale = MoraleState(size=regiment.size, xp=regiment.stats[0], morale_stat=regiment.stats[1],
                                 params=self.params.morale, break_scale=scale)
            key = (getattr(regiment, 'unit_type', 'inf'), getattr(regiment, 'subtype', None))
            self.units[uid] = BattleUnit(uid, side, regiment, morale, regiment.size, index, key=key,
                                         melee_rating=self.params.matchups.melee_rating(key),
                                         name=name, meta=unit_meta, initial_stats=regiment.stats)

        self.time: float = 0.0
        self.round: int = 0
        self.history: list[RoundReport] = []
        self.prisoners: dict[int, int] = {0: 0, 1: 0}
        self.guns_captured: dict[int, int] = {0: 0, 1: 0}
        self.finished: bool = False
        self.contacts: set[frozenset] = set()       # pairs of unit ids locked in melee, carried across rounds
        self.result: BattleResult | None = None      # set by finish()
        self._broken_before_round: set[str] = set()
        self._modifiers: dict = {}                   # this round's admin modifiers, while it is fought or previewed

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
            if isinstance(value, dict) and not set(value) <= ORDER_KEYS:
                raise ValueError(f"Unknown order key(s) {sorted(set(value) - ORDER_KEYS)} for {uid!r}; "
                                 f"use target, mode, ammo, on_break.")
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

    def _can_fire(self, unit: BattleUnit) -> bool:
        """Has firearms (the stats melee-only flag decides, not the subtype)."""
        return self.params.combat.unit_coef(unit.regiment.stats, 'ranged') > 0

    def _round_contacts(self, orders: dict[str, Order]) -> set:
        """Contacts carried into this round: pairs still joined by a melee order, either way round."""
        melee = {frozenset((uid, o.target)) for uid, o in orders.items() if o.mode == 'melee'}
        return {pair for pair in self.contacts if pair in melee}

    def _new_charges(self, orders: dict[str, Order], contacts: set, start: float, duration: float) -> tuple:
        """
        Charges made by melee orders on units not already in contact: ``(pending, immediate)``.

        ``pending`` approaches end with a contact test (or, for two units charging each other, a meeting).
        Charging a broken unit is pursuit: contact at once, recorded in ``immediate`` and added to ``contacts``.
        """
        units = self.units
        approach = self.params.charge.approach_minutes
        pending, immediate, seen = [], [], set()
        for uid in sorted(orders, key=lambda u: units[u].index):
            order = orders[uid]
            pair = frozenset((uid, order.target))
            if order.mode != 'melee' or pair in contacts or pair in seen:
                continue
            seen.add(pair)
            target = units[order.target]
            if not target.active:
                contacts.add(pair)
                immediate.append(Charge(uid, order.target, start, start, 'pursuit'))
                continue
            reply = orders.get(order.target)
            meeting = reply is not None and reply.mode == 'melee' and reply.target == uid
            minutes = approach[units[uid].key[0]]
            if meeting:
                minutes = min(minutes, approach[target.key[0]])
            pending.append({'charger': uid, 'target': order.target, 'end': start + min(minutes, duration),
                            'meeting': meeting})
        return pending, immediate

    def _plan(self, orders: dict[str, Order], cancelled: set, contacts: set, pending: list,
              withdrawn: frozenset = frozenset()) -> tuple:
        """
        The arrow structure for this moment of the round.

        Returns ``(slots, partners)``: ``slots`` are ``(attacker, target, mode, matchup, share, gun_rate)`` sorted
        by (target, attacker) in unit order; ``partners`` maps each unit in melee contact to its contacts.
        - Melee: both ways along every contact (a broken unit doesn't fight back).
        - Closing fire: a target fires on the units charging it (split between them) unless it is itself charging,
          locked in melee, or can't fire. Batteries switch to the closing ammo.
        - Ranged: units not in contact, not charging and not meeting a charge fire their orders. Units in
          ``withdrawn`` (a charge that faltered fell back beyond musket range) can only be reached by artillery.
        The structure only changes when a unit breaks or is wiped out, or a charge is decided, so the round loop
        rebuilds it then and otherwise just recomputes rates.
        """
        units = self.units
        combat = self.params.combat
        matchups = self.params.matchups
        order_key = lambda u: units[u].index     # noqa: E731

        partners: dict[str, list[str]] = {}
        for pair in contacts:
            a, b = sorted(pair, key=order_key)
            partners.setdefault(a, []).append(b)
            partners.setdefault(b, []).append(a)
        for p in partners.values():
            p.sort(key=order_key)

        slots = []
        for uid, ps in partners.items():
            unit = units[uid]
            if unit.active and unit.melee_rating > 0:
                for p in ps:
                    slots.append((uid, p, 'melee', matchups.multiplier(unit.key, units[p].key, 'melee'), 1.0, None))

        charging = {c['charger'] for c in pending}
        closing_on: dict[str, list[str]] = {}
        for c in pending:
            if not c['meeting']:
                closing_on.setdefault(c['target'], []).append(c['charger'])
        for target_id, chargers in closing_on.items():
            target = units[target_id]
            if target.active and target_id not in partners and target_id not in charging and self._can_fire(target):
                gun_rate = None
                if isinstance(target.regiment, ArtilleryBattery):
                    gun_rate = combat.artillery_ammo[self.params.charge.battery_closing_ammo]
                for charger in chargers:
                    slots.append((target_id, charger, 'closing',
                                  matchups.multiplier(target.key, units[charger].key, 'ranged'),
                                  1.0 / len(chargers), gun_rate))

        for uid, order in orders.items():
            unit = units[uid]
            out_of_reach = order.target in withdrawn and not isinstance(unit.regiment, ArtilleryBattery)
            if (order.mode == 'ranged' and uid not in cancelled and unit.active and units[order.target].size > 0
                    and uid not in partners and uid not in charging and uid not in closing_on
                    and not out_of_reach and self._can_fire(unit)):
                # artillery: per-gun rate of the ordered ammo, fixed for the round
                gun_rate = None
                if isinstance(unit.regiment, ArtilleryBattery):
                    gun_rate = combat.artillery_ammo[order.ammo or combat.artillery_default_ammo]
                slots.append((uid, order.target, 'ranged',
                              matchups.multiplier(unit.key, units[order.target].key, 'ranged'), 1.0, gun_rate))

        slots.sort(key=lambda s: (units[s[1]].index, units[s[0]].index))
        return slots, partners

    def _rates(self, slots: list, partners: dict) -> list:
        """Current ``(attacker, target, mode, rate)`` for each slot with a positive rate."""
        units = self.units
        combat = self.params.combat
        closing = self.params.charge.closing_fire_multiplier
        modifiers = self._modifiers
        total_fronts = {uid: sum(units[p].front for p in ps) for uid, ps in partners.items()}
        arrows = []
        for attacker, target, mode, matchup, share, gun_rate in slots:
            unit = units[attacker]
            stats = unit.regiment.stats
            if mode == 'melee':
                total_front = total_fronts[attacker]
                if total_front <= 0:
                    continue
                # melee strength from the subtype's rating, not the firearm
                c = combat.melee_efficiency(stats[0], stats[1], unit.melee_rating)
                front_t = units[target].front
                # fighters split in proportion to contact fronts; casualties scale with the width in contact
                fighters = unit.front * (front_t / total_front)
                rate = combat.melee_kill_rate * c * min(fighters, front_t) * matchup
            elif gun_rate is not None:
                # artillery fires per manned gun, at the rate of its ammo
                c = combat.unit_coef(stats, 'ranged')
                rate = c * unit.regiment.effective_guns * gun_rate * matchup
            else:
                c = combat.unit_coef(stats, 'ranged')
                # (coef * size) * kill_rate first: same operation order as Simulation, for bit-identical
                # 1-v-1 draws (the infantry-v-infantry matchup is 1.0, an exact multiply)
                rate = c * unit.size * combat.ranged_kill_rate * matchup
            mod = modifiers.get(attacker)
            if mod is not None:
                rate = rate * (1 + (mod['melee'] if mode == 'melee' else mod['fire']))
            if mode == 'closing':
                rate = rate * closing * share
            if units[target].morale.broken:
                # a broken unit scatters: harder to hit by fire, and by pursuit
                rate = rate * (combat.broken_melee_multiplier if mode == 'melee' else combat.broken_fire_multiplier)
            if rate > 0:
                arrows.append((attacker, target, mode, rate))
        return arrows

    def engagements(self, orders: dict, modifiers: dict | None = None) -> tuple:
        """
        Preview the arrows and their current casualty rates for these orders (and admin modifiers) at the start of a
        round (no dice rolled): melee along existing contacts, closing fire on new charges, ranged fire.
        """
        valid = self._validate_orders(orders)
        checked = validate_modifiers(modifiers or {}, self.units)
        self._modifiers = checked
        try:
            return self._engagements(valid)
        finally:
            self._modifiers = {}

    def _engagements(self, valid: dict) -> tuple:
        contacts = self._round_contacts(valid)
        pending, _ = self._new_charges(valid, contacts, self.time, float('inf'))
        return tuple(Engagement(*a) for a in self._rates(*self._plan(valid, set(), contacts, pending)))

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

    def _lose_guns(self, unit: BattleUnit, keep: int, guns: dict) -> None:
        """A battery keeps ``keep`` guns; the rest are captured by the other side."""
        battery = unit.regiment
        lost = battery.guns - keep
        if lost > 0:
            battery.update_guns(keep)
            unit.guns_lost += lost
            guns[1 - unit.side] += lost
            self.guns_captured[1 - unit.side] += lost

    def _rout(self, gone: set, arrows: list, prisoners: dict, guns: dict, cavalry_charged: set = frozenset()) -> None:
        """
        Take prisoners from units that just broke (more if enemy cavalry is attacking them, or broke them with a
        charge). A breaking battery escapes with only the guns its remaining crew can man; the rest are captured.
        """
        after = self.params.aftermath
        for uid in sorted(gone, key=lambda u: self.units[u].index):
            unit = self.units[uid]
            if not unit.morale.broken or unit.size == 0:
                continue
            cavalry = uid in cavalry_charged or any(
                a[1] == uid and isinstance(self.units[a[0]].regiment, CavalryRegiment) for a in arrows)
            mean = min(1.0, after.rout_capture_share * (after.cavalry_capture_multiplier if cavalry else 1.0))
            taken = self._draw_count(mean, unit.size)
            unit.regiment.update_size(unit.size - taken)
            unit.captured += taken
            prisoners[1 - unit.side] += taken
            self.prisoners[1 - unit.side] += taken
            if isinstance(unit.regiment, ArtilleryBattery):
                self._lose_guns(unit, unit.regiment.effective_guns, guns)

    def _contact_test(self, charge: dict) -> tuple:
        """Roll the contact test for a charge at the end of its approach: ``(outcome, odds)``."""
        ch = self.params.charge
        a, x = self.units[charge['charger']], self.units[charge['target']]
        s_a = ch.steadiness(a.morale.resolve, a.regiment.stats[0], a.morale.shock)
        s_x = ch.steadiness(x.morale.resolve, x.regiment.stats[0], x.morale.shock)
        odds = ch.odds(ch.pressure(a.size, x.size, s_a, s_x, ch.bonus(a.key, x.key)))
        u = self.rng.random()
        if u < odds[0]:
            return 'defender_broke', odds
        if u < odds[0] + odds[1]:
            return 'faltered', odds
        return 'home', odds

    def resolve_round(self, duration: float, orders: dict, record_events: bool = False,
                      modifiers: dict | None = None) -> RoundReport:
        """
        Fight one round of ``duration`` game minutes under ``orders`` and return its report.

        Units left out of ``orders`` are idle. A melee order on a unit not already in contact is a charge: an
        approach under the target's close-range fire, then a contact test (goes home, falters, or the defender
        breaks); see ``config/charge.yaml``. A charge that falters falls back beyond musket range for the rest of
        the round: only artillery can still reach it. Contact persists into later rounds while either unit keeps
        a melee order on the other. When a unit breaks or is wiped out, the units targeting it stand down for the
        rest of the round. A unit that breaks loses a share of its remaining men as prisoners (more if enemy cavalry
        is attacking it). Broken units can be attacked (pursued) but don't fight back; they are scattering, so
        fire and pursuit on them use ``broken_fire_multiplier`` / ``broken_melee_multiplier``.

        ``modifiers`` are the admin's for this round only (see ``validate_modifiers``), recorded in the report.
        """
        if self.finished:
            raise RuntimeError("This battle is finished.")
        if not duration > 0:
            raise ValueError(f"duration must be > 0, got {duration}.")
        valid = self._validate_orders(orders)
        checked = validate_modifiers(modifiers or {}, self.units)
        self._modifiers = checked
        for uid, mod in checked.items():
            self.units[uid].morale.spend_factor = 1 - mod['morale']
        try:
            return self._resolve_round(duration, valid, record_events, checked)
        finally:
            self._modifiers = {}
            for uid in checked:
                self.units[uid].morale.spend_factor = 1.0

    def _resolve_round(self, duration: float, valid: dict, record_events: bool, checked: dict) -> RoundReport:
        live = dict(valid)               # orders as they stand: a retarget changes the target here, not in valid

        self.round += 1
        start = self.time
        end = start + duration
        before = {uid: (u.losses, u.inflicted, u.captured, u.guns_lost) for uid, u in self.units.items()}
        placed = {uid: u.regiment.position.to_dict() for uid, u in self.units.items() if u.regiment.position is not None}
        prisoners = {0: 0, 1: 0}
        guns = {0: 0, 1: 0}
        self._broken_before_round = {uid for uid, u in self.units.items() if u.morale.broken}
        broke_at: dict[str, float] = {}
        cancelled: set[str] = set()
        withdrawn: set[str] = set()      # faltered chargers, fallen back beyond musket range for the round
        events = []
        contacts = self._round_contacts(valid)
        pending, immediate = self._new_charges(valid, contacts, start, duration)
        charges = list(immediate)
        retargets = []
        slots, partners = self._plan(live, cancelled, contacts, pending, frozenset(withdrawn))
        opening = tuple(Engagement(*a) for a in self._rates(slots, partners))

        def stand_down(gone: set, t: float) -> None:
            """
            Units that broke or were wiped out: contacts and approaches end; melee attackers fall back, and fire on a
            wiped-out unit stands down. Fire on a broken unit keeps going (on_break 'keep'), and a melee unit in
            contact with it stays in contact if its order says 'pursue'.
            """
            units = self.units
            for uid in sorted(live, key=lambda u: units[u].index):
                order, unit = live[uid], units[uid]
                if (order.target in gone and order.on_break in ('strongest', 'weakest') and unit.active
                        and uid not in cancelled):
                    # strength: men × share of morale budget left; ties go to the first unit
                    candidates = [u for u in units.values() if u.side != unit.side and u.active]
                    if candidates:
                        pick = max if order.on_break == 'strongest' else min
                        new = pick(candidates, key=lambda u: u.size * u.morale.resolve)
                        live[uid] = replace(order, target=new.uid)
                        retargets.append(Retarget(uid, order.target, new.uid, t))
            pursuit = {frozenset((uid, order.target)) for uid, order in live.items()
                       if order.target in gone and order.on_break == 'pursue' and units[uid].active
                       and units[order.target].size > 0}
            pursuit &= contacts
            cancelled.update(uid for uid, order in live.items()
                             if order.target in gone and frozenset((uid, order.target)) not in pursuit
                             and (order.mode == 'melee' or units[order.target].size == 0))
            contacts.difference_update([pair for pair in contacts if pair & gone and pair not in pursuit])
            for c in [c for c in pending if c['charger'] in gone or c['target'] in gone]:
                pending.remove(c)
                outcome = 'charger_broke' if c['charger'] in gone else 'target_broke'
                charges.append(Charge(c['charger'], c['target'], start, t, outcome))

        t = start
        while t < end:
            arrows = self._rates(slots, partners)
            total_rate = 0.0
            engaged = set()
            attackers = set()
            for attacker_id, target_id, mode, rate in arrows:
                total_rate += rate
                attackers.add(attacker_id)
                engaged.add(attacker_id)
                engaged.add(target_id)

            # the next scheduled moment: the round's end, or the end of an approach
            horizon = min([end] + [c['end'] for c in pending])
            dt = self.rng.exponential(total_rate) if total_rate > 0 else None
            if dt is None or t + dt >= horizon:
                self._advance(horizon - t, engaged)
                if dt is not None:
                    self._sync(engaged)
                t = horizon
                gone = self._newly_broken(engaged, broke_at, t)
                self._rout(gone, arrows, prisoners, guns)
                if gone:
                    stand_down(gone, t)
                due = [c for c in pending if c['end'] <= t]
                for c in due:
                    pending.remove(c)
                    pair = frozenset((c['charger'], c['target']))
                    if c['meeting']:
                        contacts.add(pair)
                        charges.append(Charge(c['charger'], c['target'], start, t, 'meeting'))
                        continue
                    outcome, odds = self._contact_test(c)
                    charges.append(Charge(c['charger'], c['target'], start, t, outcome, *odds))
                    charger, target = self.units[c['charger']], self.units[c['target']]
                    cavalry_charged = set()
                    if outcome == 'home':
                        contacts.add(pair)
                    elif outcome == 'faltered':
                        cancelled.add(charger.uid)
                        withdrawn.add(charger.uid)
                        charger.morale.shake(self.params.charge.falter_cost)
                    else:
                        target.morale.force_break()
                        if isinstance(charger.regiment, CavalryRegiment):
                            cavalry_charged.add(target.uid)
                    self._sync((charger.uid, target.uid))
                    gone = self._newly_broken((charger.uid, target.uid), broke_at, t)
                    self._rout(gone, arrows, prisoners, guns, cavalry_charged)
                    if outcome == 'defender_broke' and isinstance(target.regiment, ArtilleryBattery):
                        self._lose_guns(target, 0, guns)        # overrun where it stands: no time to limber up
                    if gone:
                        stand_down(gone, t)
                if gone or due:
                    slots, partners = self._plan(live, cancelled, contacts, pending, frozenset(withdrawn))
                continue

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
            self._rout(gone, arrows, prisoners, guns)
            if victim.size == 0:
                gone.add(victim.uid)
                if isinstance(victim.regiment, ArtilleryBattery):
                    self._lose_guns(victim, 0, guns)            # overrun: no crew left, every gun is taken
            if gone:
                stand_down(gone, t)
                slots, partners = self._plan(live, cancelled, contacts, pending, frozenset(withdrawn))

        # contacts carry over only between units that are both still standing
        self.contacts = {pair for pair in contacts if all(self.units[u].active for u in pair)}
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
                    guns_lost=u.guns_lost - before[uid][3],
                )
                for uid, u in self.units.items()
            },
            events=tuple(events),
            prisoners=prisoners,
            guns_captured=guns,
            orders={uid: {'target': o.target, 'mode': o.mode, 'ammo': o.ammo, 'on_break': o.on_break}
                    for uid, o in valid.items()},
            charges=tuple(charges),
            positions=placed,
            modifiers=checked,
            retargets=tuple(retargets),
        )
        self.history.append(report)
        return report

    # -------------------------------------------------------------------------
    # Saving and loading (battle state file, roadmap A8)
    # -------------------------------------------------------------------------

    def to_dict(self) -> dict:
        """The full battle state as a JSON-safe dict; see ``battles.state``."""
        from imperial_generals.battles.state import battle_to_dict
        return battle_to_dict(self)

    def to_json(self, indent: int | None = None) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict) -> 'Battle':
        """Rebuild a battle saved with ``to_dict``; resolving on from it gives exactly the same results."""
        from imperial_generals.battles.state import battle_from_dict
        return battle_from_dict(data)

    @classmethod
    def from_json(cls, text: str) -> 'Battle':
        return cls.from_dict(json.loads(text))

    @classmethod
    def from_setup(cls, data: dict, seed: int | None = None) -> 'Battle':
        """A new battle from a hand-written setup (units, seed, side names, overrides); see ``battles.setup``."""
        from imperial_generals.battles.setup import battle_from_setup
        return battle_from_setup(data, seed=seed)

    # -------------------------------------------------------------------------
    # After the battle
    # -------------------------------------------------------------------------

    def _army_out_holder(self) -> int | None:
        """The side still standing when every unit of the other side is broken or wiped out; else None."""
        out = {side: all(not u.active for u in self.units.values() if u.side == side) for side in (0, 1)}
        if out[1] and not out[0]:
            return 0
        if out[0] and not out[1]:
            return 1
        return None

    def _field_votes(self) -> dict:
        """
        Each test's vote for the side that is decisively ahead, or None:
        - 'exchange': inflicted at least ``field_exchange_ratio`` × the men hit it took (and hit someone);
        - 'routs': the starting strength of its broken or wiped-out units, as a share of its starting total, is
          at least ``field_rout_gap`` lower than the other side's;
        - 'standing': at least ``field_standing_ratio`` × the other side's men in unbroken units.
        """
        after = self.params.aftermath
        sides = {side: [u for u in self.units.values() if u.side == side] for side in (0, 1)}
        taken = {s: sum(u.losses for u in us) for s, us in sides.items()}
        inflicted = {s: sum(u.inflicted for u in us) for s, us in sides.items()}
        routed = {s: sum(u.initial_size for u in us if not u.active) / sum(u.initial_size for u in us)
                  for s, us in sides.items()}
        standing = {s: sum(u.size for u in us if u.active) for s, us in sides.items()}

        def vote(ahead) -> int | None:
            return next((s for s in (0, 1) if ahead(s, 1 - s)), None)

        return {
            'exchange': vote(lambda s, o: inflicted[s] > 0 and inflicted[s] >= after.field_exchange_ratio * taken[s]),
            'routs': vote(lambda s, o: routed[o] - routed[s] >= after.field_rout_gap),
            'standing': vote(lambda s, o: standing[s] > 0 and standing[s] >= after.field_standing_ratio * standing[o]),
        }

    def _voted_holder(self, votes: dict) -> int | None:
        """The side with at least ``field_votes_needed`` votes and none against; else None (a draw)."""
        count = {side: sum(v == side for v in votes.values()) for side in (0, 1)}
        for side in (0, 1):
            if count[side] >= self.params.aftermath.field_votes_needed and count[1 - side] == 0:
                return side
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
            broken or wiped out; otherwise the side the field tests vote for (``_field_votes``), or None, a draw
            (no wounded captured). The result records how it was decided and the votes.

        Raises
        ------
        RuntimeError
            If the battle is already finished.
        ValueError
            If field_held_by is not 0, 1, None or 'auto'.
        """
        if self.finished:
            raise RuntimeError("This battle is already finished.")
        votes = self._field_votes()
        if field_held_by == 'auto':
            holder = self._army_out_holder()
            decided_by = 'votes' if holder is None else 'army_out'
            if holder is None:
                holder = self._voted_holder(votes)
        elif field_held_by is None or (type(field_held_by) is int and field_held_by in (0, 1)):
            holder, decided_by = field_held_by, 'admin'
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
                guns_lost=unit.guns_lost,
            )

        self.finished = True
        self.result = BattleResult(field_held_by=holder, units=outcomes, prisoners=dict(self.prisoners),
                                   guns_captured=dict(self.guns_captured), field_decided_by=decided_by,
                                   field_votes=votes)
        return self.result
