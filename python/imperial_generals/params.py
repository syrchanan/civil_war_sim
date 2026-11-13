"""
Per-battle tunable parameters (roadmap A3).

``BattleParams`` bundles every constant the engine uses in a battle: ``CombatParams`` (effectiveness and kill
rates), ``MoraleParams`` (the morale model), ``AftermathParams`` (prisoners and casualty accounting),
``MatchupParams`` (unit-type advantages, melee ratings), ``ChargeParams`` (approach and contact test) and
``RallyParams`` (rallying broken units). Defaults come from config/*.yaml; overrides are applied per
battle and never touch the global config, so a tuning or RL loop can run many parameter sets in one process.

``to_dict`` / ``from_dict`` are JSON-safe, for the battle state file (A8).
"""

import copy
from dataclasses import dataclass, field, fields, replace
from functools import lru_cache

from imperial_generals.config import get_config

WEAPON_CODES = (-2, -1, 0, 1, 2)


def _config_default(section: str, key: str, subsection: str | None = None):
    def load():
        cfg = get_config()[section]
        return (cfg[subsection] if subsection else cfg)[key]
    return field(default_factory=load)


def _weapon_multipliers_from_config() -> dict[int, float]:
    return {int(k): float(v) for k, v in get_config()['combat']['weapon_multipliers'].items()}


# =============================================================================
# Combat
# =============================================================================

@dataclass(frozen=True)
class CombatParams:
    """Combat effectiveness and kill-rate constants; defaults from config/combat.yaml."""

    weapon_multipliers: dict = field(default_factory=_weapon_multipliers_from_config)
    xp_boost_per_level: float = _config_default('combat', 'xp_boost_per_level')
    morale_boost_per_level: float = _config_default('combat', 'morale_boost_per_level')
    melee_penalty_factor: float = _config_default('combat', 'melee_penalty_factor')
    ranged_kill_rate: float = _config_default('combat', 'ranged_kill_rate')
    melee_kill_rate: float = _config_default('combat', 'melee_kill_rate')
    broken_fire_multiplier: float = _config_default('combat', 'broken_fire_multiplier')
    broken_melee_multiplier: float = _config_default('combat', 'broken_melee_multiplier')
    artillery_ammo: dict = field(default_factory=lambda: dict(get_config()['combat']['artillery_ammo']))
    artillery_default_ammo: str = _config_default('combat', 'artillery_default_ammo')

    def __post_init__(self) -> None:
        multipliers = {int(k): float(v) for k, v in self.weapon_multipliers.items()}
        if set(multipliers) != set(WEAPON_CODES):
            raise ValueError(f"weapon_multipliers must have exactly the codes {WEAPON_CODES}, got {sorted(multipliers)}.")
        if any(v <= 0 for v in multipliers.values()):
            raise ValueError("weapon multipliers must be > 0.")
        for name in ('xp_boost_per_level', 'morale_boost_per_level', 'broken_fire_multiplier',
                     'broken_melee_multiplier'):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be >= 0.")
        for name in ('melee_penalty_factor', 'ranged_kill_rate', 'melee_kill_rate'):
            if not getattr(self, name) > 0:
                raise ValueError(f"{name} must be > 0.")
        if not self.artillery_ammo or any(not v > 0 for v in self.artillery_ammo.values()):
            raise ValueError("artillery_ammo needs at least one ammo type, each with a per-gun rate > 0.")
        if self.artillery_default_ammo not in self.artillery_ammo:
            raise ValueError(f"artillery_default_ammo {self.artillery_default_ammo!r} is not in artillery_ammo.")

        object.__setattr__(self, 'weapon_multipliers', multipliers)
        # Normaliser: the best possible unit (top weapon, xp 10, morale 10) has efficiency 1.
        max_raw = max(multipliers.values()) * (1 + 9 * self.xp_boost_per_level + 9 * self.morale_boost_per_level)
        object.__setattr__(self, '_max_raw', max_raw)
        object.__setattr__(self, '_raw_scale', get_config()['morale']['raw_scale_factor'])
        # unit_coef is a pure function of (stats, mode) for these frozen constants: memoise it
        object.__setattr__(self, '_coef_cache', {})

    def efficiency(self, xp: int, morale: float, weapon: int, melee: int = 0) -> float:
        """
        Combat efficiency coefficient in [0, 1]; same rules as ``get_combat_efficiency``.

        ``morale`` may be a 1–10 stat or a raw 10–100 value (converted when above the raw scale factor).
        Inputs are clamped: xp and morale to 1–10, weapon to -2..2, melee to 0/1.
        """
        weapon = max(-2, min(2, weapon))
        melee = max(0, min(1, melee))
        raw = self.weapon_multipliers[weapon] * self._eff_adj(xp, morale)
        if melee == 1:
            raw *= self.melee_penalty_factor
        return raw / self._max_raw

    def _eff_adj(self, xp: int, morale: float) -> float:
        """Experience and morale boost: 1 at xp 1 / morale 1. Morale may be a 1–10 stat or raw 10–100."""
        morale_1_10 = round(morale / self._raw_scale, ndigits=0) if morale > self._raw_scale else morale
        morale_1_10 = max(1, min(10, morale_1_10))
        xp = max(1, min(10, xp))
        return 1 + (xp - 1) * self.xp_boost_per_level + (morale_1_10 - 1) * self.morale_boost_per_level

    def melee_efficiency(self, xp: int, morale: float, rating: float) -> float:
        """
        Melee coefficient for the round engine: the unit's melee rating (per subtype, on the weapon-multiplier
        scale) boosted by experience and morale, on the same normalised scale as ``efficiency``. The firearm
        and the global melee penalty play no part.
        """
        key = ('melee', xp, morale, rating)
        cached = self._coef_cache.get(key)
        if cached is None:
            cached = rating * self._eff_adj(xp, morale) / self._max_raw
            self._coef_cache[key] = cached
        return cached

    def unit_coef(self, stats: tuple[int, int, int, int], combat_mode: str) -> float:
        """
        A unit's coefficient in its current combat mode.

        - Melee-only unit (stats[3] == 1) at range: 0 (it cannot fire).
        - Ranged unit in melee: efficiency × melee_penalty_factor.
        - Otherwise: base efficiency.
        """
        key = (stats, combat_mode)
        cached = self._coef_cache.get(key)
        if cached is not None:
            return cached
        melee_only = stats[3] == 1
        if melee_only and combat_mode == 'ranged':
            value = 0.0
        else:
            value = self.efficiency(stats[0], stats[1], stats[2], 0)
            if not melee_only and combat_mode == 'melee':
                value = value * self.melee_penalty_factor
        self._coef_cache[key] = value
        return value


@lru_cache(maxsize=1)
def default_combat_params() -> CombatParams:
    """Config-default CombatParams, built once. Config is loaded once per process and never changes at runtime."""
    return CombatParams()


# =============================================================================
# Morale
# =============================================================================

@dataclass(frozen=True)
class MoraleParams:
    """Tunable morale constants; defaults come from ``morale.model`` in config/morale.yaml."""

    break_fraction_min: float = _config_default('morale', 'break_fraction_min', 'model')
    break_fraction_max: float = _config_default('morale', 'break_fraction_max', 'model')
    experience_weight: float = _config_default('morale', 'experience_weight', 'model')
    break_curve: float = _config_default('morale', 'break_curve', 'model')
    break_point_spread: float = _config_default('morale', 'break_point_spread', 'model')
    break_fraction_ceiling: float = _config_default('morale', 'break_fraction_ceiling', 'model')
    size_reference: float = _config_default('morale', 'size_reference', 'model')
    size_exponent: float = _config_default('morale', 'size_exponent', 'model')
    acceleration: float = _config_default('morale', 'acceleration', 'model')
    shock_weight: float = _config_default('morale', 'shock_weight', 'model')
    shock_half_life: float = _config_default('morale', 'shock_half_life', 'model')
    helpless_weight: float = _config_default('morale', 'helpless_weight', 'model')
    drain_per_hour: float = _config_default('morale', 'drain_per_hour', 'model')
    gain_weight: float = _config_default('morale', 'gain_weight', 'model')

    def __post_init__(self) -> None:
        if not 0 < self.break_fraction_min <= self.break_fraction_max <= 1:
            raise ValueError("Need 0 < break_fraction_min <= break_fraction_max <= 1.")
        if not 0 <= self.experience_weight <= 1:
            raise ValueError("experience_weight must be in [0, 1].")
        if not self.break_point_spread >= 0:
            raise ValueError("break_point_spread must be >= 0.")
        if not 0 < self.break_fraction_ceiling <= 1:
            raise ValueError("break_fraction_ceiling must be in (0, 1].")
        for name in ('break_curve', 'size_reference', 'shock_half_life'):
            if not getattr(self, name) > 0:
                raise ValueError(f"{name} must be > 0.")
        for name in ('acceleration', 'shock_weight', 'helpless_weight', 'drain_per_hour', 'gain_weight'):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be >= 0.")


# =============================================================================
# Aftermath
# =============================================================================

@dataclass(frozen=True)
class AftermathParams:
    """Rout captures and end-of-battle casualty accounting; defaults from config/aftermath.yaml."""

    rout_capture_share: float = _config_default('aftermath', 'rout_capture_share')
    cavalry_capture_multiplier: float = _config_default('aftermath', 'cavalry_capture_multiplier')
    killed_share: float = _config_default('aftermath', 'killed_share')
    walking_wounded_share: float = _config_default('aftermath', 'walking_wounded_share')
    wounded_captured_share: float = _config_default('aftermath', 'wounded_captured_share')
    wounded_return_share: float = _config_default('aftermath', 'wounded_return_share')
    share_spread: float = _config_default('aftermath', 'share_spread')
    field_exchange_ratio: float = _config_default('aftermath', 'field_exchange_ratio')
    field_rout_gap: float = _config_default('aftermath', 'field_rout_gap')
    field_standing_ratio: float = _config_default('aftermath', 'field_standing_ratio')
    field_votes_needed: int = _config_default('aftermath', 'field_votes_needed')
    decisive_ratio: float = _config_default('aftermath', 'decisive_ratio')
    decisive_share: float = _config_default('aftermath', 'decisive_share')
    pyrrhic_share: float = _config_default('aftermath', 'pyrrhic_share')
    pyrrhic_ratio: float = _config_default('aftermath', 'pyrrhic_ratio')

    def __post_init__(self) -> None:
        for name in ('rout_capture_share', 'killed_share', 'walking_wounded_share', 'wounded_captured_share',
                     'wounded_return_share', 'share_spread'):
            if not 0 <= getattr(self, name) <= 1:
                raise ValueError(f"{name} must be in [0, 1].")
        if self.cavalry_capture_multiplier < 0:
            raise ValueError("cavalry_capture_multiplier must be >= 0.")
        for name in ('field_exchange_ratio', 'field_standing_ratio'):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be >= 1.")
        if not 0 <= self.field_rout_gap <= 1:
            raise ValueError("field_rout_gap must be in [0, 1].")
        if type(self.field_votes_needed) is not int or not 1 <= self.field_votes_needed <= 3:
            raise ValueError("field_votes_needed must be a whole number from 1 to 3.")
        if self.decisive_ratio < 1:
            raise ValueError("decisive_ratio must be >= 1.")
        for name in ('decisive_share', 'pyrrhic_share'):
            if not 0 <= getattr(self, name) <= 1:
                raise ValueError(f"{name} must be in [0, 1].")
        if self.pyrrhic_ratio < 0:
            raise ValueError("pyrrhic_ratio must be >= 0.")


# =============================================================================
# Matchups
# =============================================================================

UNIT_TYPES = ('inf', 'cav', 'art')
_MATCHUP_MODES = ('ranged', 'melee')


def _matchups_default(key: str):
    return field(default_factory=lambda: copy.deepcopy(get_config()['matchups'][key]))


def _valid_unit_key(key: str, allow_any: bool = False) -> bool:
    """'type' or 'type/subtype' (or '*' when allowed), with the subtype known for that type."""
    from imperial_generals.utils.unit_types import UNIT_SUBTYPES   # lazy: utils imports this module
    if allow_any and key == '*':
        return True
    unit_type, _, subtype = key.partition('/')
    if unit_type not in UNIT_TYPES:
        return False
    return not subtype or subtype in UNIT_SUBTYPES[unit_type]


@dataclass(frozen=True)
class MatchupParams:
    """
    Unit-type advantage and melee strength; defaults from config/matchups.yaml.

    ``ranged`` / ``melee``: attacker type → target type → multiplier on the attacker's casualty rate.
    ``overrides``: subtype-specific replacements (most specific match wins, see ``multiplier``).
    ``melee_ratings``: melee strength per 'type/subtype' (plus 'default'), on the weapon-multiplier scale.
    """

    ranged: dict = _matchups_default('ranged')
    melee: dict = _matchups_default('melee')
    overrides: tuple = _matchups_default('overrides')
    melee_ratings: dict = _matchups_default('melee_ratings')

    def __post_init__(self) -> None:
        for mode in _MATCHUP_MODES:
            table = getattr(self, mode)
            for a in UNIT_TYPES:
                row = table.get(a) if isinstance(table, dict) else None
                if not isinstance(row, dict) or set(row) != set(UNIT_TYPES):
                    raise ValueError(f"{mode} table needs a full {UNIT_TYPES} x {UNIT_TYPES} grid (row {a!r}).")
                if any(not v >= 0 for v in row.values()):
                    raise ValueError(f"{mode} multipliers must be >= 0 (row {a!r}).")

        lookup = {}
        for o in self.overrides:
            if not isinstance(o, dict) or set(o) != {'attacker', 'target', 'mode', 'multiplier'}:
                raise ValueError(f"An override needs exactly attacker, target, mode, multiplier: {o!r}.")
            if o['mode'] not in _MATCHUP_MODES:
                raise ValueError(f"Override mode must be ranged or melee: {o!r}.")
            if not _valid_unit_key(o['attacker']) or not _valid_unit_key(o['target'], allow_any=True):
                raise ValueError(f"Unknown unit type/subtype in override: {o!r}.")
            if o['target'] == '*' and '/' not in o['attacker']:
                raise ValueError(f"target '*' needs an attacker subtype (use the type table otherwise): {o!r}.")
            if not o['multiplier'] >= 0:
                raise ValueError(f"Override multiplier must be >= 0: {o!r}.")
            lookup[(o['attacker'], o['target'], o['mode'])] = float(o['multiplier'])

        if 'default' not in self.melee_ratings:
            raise ValueError("melee_ratings needs a 'default' entry.")
        for key, value in self.melee_ratings.items():
            if key != 'default' and ('/' not in key or not _valid_unit_key(key)):
                raise ValueError(f"Unknown melee rating key {key!r} (use 'type/subtype').")
            if not value >= 0:
                raise ValueError(f"Melee rating must be >= 0: {key!r}.")

        object.__setattr__(self, 'overrides', tuple(dict(o) for o in self.overrides))
        object.__setattr__(self, '_lookup', lookup)
        object.__setattr__(self, '_cache', {})

    def multiplier(self, attacker: tuple, target: tuple, mode: str) -> float:
        """
        Multiplier for ``attacker`` (type, subtype | None) against ``target`` in ``mode``. Most specific first:
        attacker subtype + target subtype, attacker subtype + target type, attacker subtype + any target,
        attacker type + target subtype, then the type table.
        """
        key = (attacker, target, mode)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        a_type, a_sub = attacker
        t_type, t_sub = target
        a_full = f"{a_type}/{a_sub}" if a_sub else None
        t_full = f"{t_type}/{t_sub}" if t_sub else None
        candidates = []
        if a_full:
            candidates += [(a_full, t_full), (a_full, t_type), (a_full, '*')]
        candidates.append((a_type, t_full))
        value = next(
            (self._lookup[(a, t, mode)] for a, t in candidates if t is not None and (a, t, mode) in self._lookup),
            getattr(self, mode)[a_type][t_type],
        )
        self._cache[key] = value
        return value

    def melee_rating(self, unit: tuple) -> float:
        """Melee rating for (type, subtype | None); units without a listed subtype use 'default'."""
        unit_type, subtype = unit
        return self.melee_ratings.get(f"{unit_type}/{subtype}", self.melee_ratings['default'])


# =============================================================================
# Charges
# =============================================================================

def _charge_default(key: str):
    return field(default_factory=lambda: copy.deepcopy(get_config()['charge'][key]))


def _sigmoid(z: float) -> float:
    from imperial_generals.utils.fdlibm import exp   # lazy: utils imports this module
    return 1.0 / (1.0 + exp(-z))


@dataclass(frozen=True)
class ChargeParams:
    """
    Charges: the approach under close-range fire and the contact test; defaults from config/charge.yaml.

    ``odds(pressure(...))`` gives (defender breaks, charge falters, goes home); see the config for the formulas.
    """

    approach_minutes: dict = _charge_default('approach_minutes')
    closing_fire_multiplier: float = _charge_default('closing_fire_multiplier')
    battery_closing_ammo: str = _charge_default('battery_closing_ammo')
    numbers_weight: float = _charge_default('numbers_weight')
    steadiness_weight: float = _charge_default('steadiness_weight')
    veterancy_weight: float = _charge_default('veterancy_weight')
    shock_weight: float = _charge_default('shock_weight')
    break_threshold: float = _charge_default('break_threshold')
    falter_threshold: float = _charge_default('falter_threshold')
    spread: float = _charge_default('spread')
    falter_cost: float = _charge_default('falter_cost')
    shock_bonus: tuple = _charge_default('shock_bonus')
    speed: dict = _charge_default('speed')

    def __post_init__(self) -> None:
        for name in ('approach_minutes', 'speed'):
            table = getattr(self, name)
            if not isinstance(table, dict) or set(table) != set(UNIT_TYPES):
                raise ValueError(f"{name} needs exactly {list(UNIT_TYPES)}.")
            if any(not v > 0 for v in table.values()):
                raise ValueError(f"{name} must be > 0.")
        for name in ('closing_fire_multiplier', 'numbers_weight', 'steadiness_weight', 'shock_weight',
                     'break_threshold', 'falter_threshold'):
            if not getattr(self, name) >= 0:
                raise ValueError(f"{name} must be >= 0.")
        if not self.spread > 0:
            raise ValueError("spread must be > 0.")
        for name in ('veterancy_weight', 'falter_cost'):
            if not 0 <= getattr(self, name) <= 1:
                raise ValueError(f"{name} must be in [0, 1].")
        for b in self.shock_bonus:
            if not isinstance(b, dict) or set(b) != {'charger', 'target', 'bonus'}:
                raise ValueError(f"A shock bonus needs exactly charger, target, bonus: {b!r}.")
            if not _valid_unit_key(b['charger']) or not _valid_unit_key(b['target']):
                raise ValueError(f"Unknown unit type/subtype in shock bonus: {b!r}.")
        object.__setattr__(self, 'shock_bonus', tuple(dict(b) for b in self.shock_bonus))

    def steadiness(self, resolve: float, xp: int, shock: float) -> float:
        """How well a unit holds together: resolve, steadied by veterancy, shaken by recent losses."""
        xp_norm = (max(1, min(10, xp)) - 1) / 9
        w = self.veterancy_weight
        return resolve * (1 - w + w * xp_norm) / (1 + self.shock_weight * shock)

    def bonus(self, charger: tuple, target: tuple) -> float:
        """Sum of the shock bonuses matching (type, subtype | None) of the charger and the target."""
        def keys(unit):
            kind, sub = unit
            return {kind, f"{kind}/{sub}"} if sub else {kind}
        c_keys, t_keys = keys(charger), keys(target)
        return sum(b['bonus'] for b in self.shock_bonus if b['charger'] in c_keys and b['target'] in t_keys)

    def pressure(self, charger_men: int, target_men: int, charger_steadiness: float, target_steadiness: float,
                 bonus: float) -> float:
        from imperial_generals.utils.fdlibm import log   # lazy: utils imports this module
        return (self.numbers_weight * log(charger_men / target_men)
                + self.steadiness_weight * (charger_steadiness - target_steadiness) + bonus)

    def odds(self, x: float) -> tuple:
        """(defender breaks, charge falters, goes home) for pressure ``x``."""
        p_break = _sigmoid((x - self.break_threshold) / self.spread)
        p_falter = _sigmoid((-x - self.falter_threshold) / self.spread)
        return p_break, p_falter, max(0.0, 1.0 - p_break - p_falter)


# =============================================================================
# Range
# =============================================================================

def _range_default(key: str):
    return field(default_factory=lambda: copy.deepcopy(get_config()['range'][key]))


def _check_ranges(name: str, table, keys, what: str) -> None:
    if not isinstance(table, dict):
        raise ValueError(f"{name} must be a mapping of {what} to {{close, max}}.")
    for key, r in table.items():
        if key not in keys:
            raise ValueError(f"{name}: unknown {what} {key!r}; one of {sorted(keys)}.")
        if not isinstance(r, dict) or set(r) != {'close', 'max'}:
            raise ValueError(f"{name} {key}: needs exactly close and max (yards).")
        if not 0 <= r['close'] < r['max']:
            raise ValueError(f"{name} {key}: close must be >= 0 and below max.")


@dataclass(frozen=True)
class RangeParams:
    """Fire falling off with distance (yards); defaults from config/range.yaml."""

    falloff_exponent: float = _range_default('falloff_exponent')
    small_arms: dict = _range_default('small_arms')
    artillery: dict = _range_default('artillery')

    def __post_init__(self) -> None:
        if not self.falloff_exponent > 0:
            raise ValueError("falloff_exponent must be > 0.")
        _check_ranges('small_arms', self.small_arms, {str(c) for c in WEAPON_CODES}, 'weapon code')
        if set(self.small_arms) != {str(c) for c in WEAPON_CODES}:
            raise ValueError(f"small_arms needs every weapon code {[str(c) for c in WEAPON_CODES]}.")
        _check_ranges('artillery', self.artillery, set(self.artillery), 'ammo')

    def reach(self, distance: float, close: float, far: float) -> float:
        """Share of full effect at ``distance``: 1 up to ``close``, falling to 0 at ``far``."""
        if distance <= close:
            return 1.0
        if distance >= far:
            return 0.0
        left = 1 - (distance - close) / (far - close)
        if self.falloff_exponent == 1:
            return left
        from imperial_generals.utils.fdlibm import exp, log   # lazy: utils imports this module
        return exp(self.falloff_exponent * log(left))


# =============================================================================
# Facing and flanks
# =============================================================================

def _flank_default(key: str):
    return field(default_factory=lambda: copy.deepcopy(get_config()['flanks'][key]))


@dataclass(frozen=True)
class FlankParams:
    """Front, flank and rear: arcs (degrees) and what attacks from the flank or rear do; config/flanks.yaml."""

    front_arc: float = _flank_default('front_arc')
    rear_arc: float = _flank_default('rear_arc')
    casualties: dict = _flank_default('casualties')
    shock: dict = _flank_default('shock')
    charge_bonus: dict = _flank_default('charge_bonus')

    def __post_init__(self) -> None:
        if not 0 < self.front_arc <= 360:
            raise ValueError("front_arc must be in (0, 360] degrees.")
        if not 0 <= self.rear_arc < 360:
            raise ValueError("rear_arc must be in [0, 360) degrees.")
        if self.front_arc + self.rear_arc > 360:
            raise ValueError("front_arc + rear_arc must leave room for the flanks (at most 360 degrees).")
        for name in ('casualties', 'shock', 'charge_bonus'):
            table = getattr(self, name)
            if not isinstance(table, dict) or set(table) != {'flank', 'rear'}:
                raise ValueError(f"{name} needs exactly flank and rear.")
            if name != 'charge_bonus' and any(not v >= 0 for v in table.values()):
                raise ValueError(f"{name} multipliers must be >= 0.")


# =============================================================================
# Rally
# =============================================================================

def _rally_default(key: str):
    return field(default_factory=lambda: get_config()['rally'][key])


@dataclass(frozen=True)
class RallyParams:
    """Rallying broken units: the odds, tries per battle and the penalties after; defaults from config/rally.yaml."""

    attempts: int = _rally_default('attempts')
    chance_min: float = _rally_default('chance_min')
    chance_max: float = _rally_default('chance_max')
    experience_weight: float = _rally_default('experience_weight')
    men_exponent: float = _rally_default('men_exponent')
    resolve: float = _rally_default('resolve')
    effectiveness: float = _rally_default('effectiveness')
    exposure: float = _rally_default('exposure')

    def __post_init__(self) -> None:
        if isinstance(self.attempts, bool) or not isinstance(self.attempts, int) or self.attempts < 1:
            raise ValueError("attempts must be a whole number >= 1.")
        if not 0 <= self.chance_max <= 1:
            raise ValueError("chance_max must be in [0, 1].")
        if not 0 <= self.chance_min <= self.chance_max:
            raise ValueError("chance_min must be in [0, chance_max].")
        if not 0 <= self.experience_weight <= 1:
            raise ValueError("experience_weight must be in [0, 1].")
        if not self.men_exponent >= 0:
            raise ValueError("men_exponent must be >= 0.")
        if not 0 < self.resolve <= 1:
            raise ValueError("resolve must be in (0, 1].")
        for name in ('effectiveness', 'exposure'):
            if not getattr(self, name) >= 0:
                raise ValueError(f"{name} must be >= 0.")

    def chance(self, xp: int, morale_stat: int, men_left: float) -> float:
        """Chance a rally works, from starting experience and morale (1–10) and the share of men left."""
        from imperial_generals.utils.fdlibm import exp, log   # lazy: utils imports this module
        xp_norm = (max(1, min(10, xp)) - 1) / 9
        morale_norm = (max(1, min(10, morale_stat)) - 1) / 9
        w = self.experience_weight * xp_norm + (1 - self.experience_weight) * morale_norm
        base = self.chance_min + (self.chance_max - self.chance_min) * w
        # men_left > 0: a wiped-out unit can't rally
        return base * exp(self.men_exponent * log(men_left))


# =============================================================================
# Battle
# =============================================================================

def _deep_merge(base: dict, changes: dict) -> dict:
    merged = dict(base)
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _apply(section_params, overrides: dict, section: str):
    known = {f.name for f in fields(section_params)}
    unknown = set(overrides) - known
    if unknown:
        raise ValueError(f"Unknown {section} parameter(s): {sorted(unknown)}.")
    changes = dict(overrides)
    for name, value in overrides.items():
        current = getattr(section_params, name)
        if name == 'weapon_multipliers':
            changes[name] = {**current, **{int(k): v for k, v in value.items()}}
        elif isinstance(current, dict) and isinstance(value, dict):
            changes[name] = _deep_merge(current, value)      # partial table / rating overrides merge in
    return replace(section_params, **changes)


@dataclass(frozen=True)
class BattleParams:
    """All tunable constants for one battle."""

    combat: CombatParams = field(default_factory=CombatParams)
    morale: MoraleParams = field(default_factory=MoraleParams)
    aftermath: AftermathParams = field(default_factory=AftermathParams)
    matchups: MatchupParams = field(default_factory=MatchupParams)
    charge: ChargeParams = field(default_factory=ChargeParams)
    rally: RallyParams = field(default_factory=RallyParams)
    range: RangeParams = field(default_factory=RangeParams)
    flanks: FlankParams = field(default_factory=FlankParams)

    def __post_init__(self) -> None:
        if set(self.range.artillery) != set(self.combat.artillery_ammo):
            raise ValueError(f"range.artillery needs every ammo: {sorted(self.combat.artillery_ammo)}.")
        if self.charge.battery_closing_ammo not in self.combat.artillery_ammo:
            raise ValueError(f"charge.battery_closing_ammo must be one of {sorted(self.combat.artillery_ammo)}.")

    def with_overrides(self, overrides: dict) -> 'BattleParams':
        """
        New params with nested overrides applied, e.g. ``{'combat': {'ranged_kill_rate': 0.005}}``.

        A partial ``weapon_multipliers`` dict merges into the current one. Unknown sections or keys, and invalid
        values, raise ValueError.
        """
        sections = {f.name for f in fields(self)}
        unknown = set(overrides) - sections
        if unknown:
            raise ValueError(f"Unknown parameter section(s): {sorted(unknown)}.")
        return BattleParams(**{
            name: _apply(getattr(self, name), overrides.get(name, {}), name) for name in sections
        })

    def to_dict(self) -> dict:
        """JSON-safe dict of every parameter (weapon codes as string keys)."""
        data = {
            f.name: {g.name: copy.deepcopy(getattr(getattr(self, f.name), g.name)) for g in fields(getattr(self, f.name))}
            for f in fields(self)
        }
        data['combat']['weapon_multipliers'] = {
            str(k): v for k, v in sorted(data['combat']['weapon_multipliers'].items())
        }
        data['matchups']['overrides'] = list(data['matchups']['overrides'])
        data['charge']['shock_bonus'] = list(data['charge']['shock_bonus'])
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'BattleParams':
        """Build params from a full or partial dict (missing values use config defaults)."""
        return cls().with_overrides(data)
