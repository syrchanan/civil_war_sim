"""
Per-battle tunable parameters (roadmap A3).

``BattleParams`` bundles every constant the engine uses in a battle: ``CombatParams`` (effectiveness and kill
rates) and ``MoraleParams`` (the morale model). Defaults come from config/*.yaml; overrides are applied per
battle and never touch the global config, so a tuning or RL loop can run many parameter sets in one process.

``to_dict`` / ``from_dict`` are JSON-safe, for the battle state file (A8).
"""

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

    def __post_init__(self) -> None:
        multipliers = {int(k): float(v) for k, v in self.weapon_multipliers.items()}
        if set(multipliers) != set(WEAPON_CODES):
            raise ValueError(f"weapon_multipliers must have exactly the codes {WEAPON_CODES}, got {sorted(multipliers)}.")
        if any(v <= 0 for v in multipliers.values()):
            raise ValueError("weapon multipliers must be > 0.")
        for name in ('xp_boost_per_level', 'morale_boost_per_level'):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be >= 0.")
        for name in ('melee_penalty_factor', 'ranged_kill_rate', 'melee_kill_rate'):
            if not getattr(self, name) > 0:
                raise ValueError(f"{name} must be > 0.")

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
        morale_1_10 = round(morale / self._raw_scale, ndigits=0) if morale > self._raw_scale else morale
        morale_1_10 = max(1, min(10, morale_1_10))
        xp = max(1, min(10, xp))
        weapon = max(-2, min(2, weapon))
        melee = max(0, min(1, melee))

        eff_adj = 1 + (xp - 1) * self.xp_boost_per_level + (morale_1_10 - 1) * self.morale_boost_per_level
        raw = self.weapon_multipliers[weapon] * eff_adj
        if melee == 1:
            raw *= self.melee_penalty_factor
        return raw / self._max_raw

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
        for name in ('break_curve', 'size_reference', 'shock_half_life'):
            if not getattr(self, name) > 0:
                raise ValueError(f"{name} must be > 0.")
        for name in ('acceleration', 'shock_weight', 'helpless_weight', 'drain_per_hour', 'gain_weight'):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be >= 0.")


# =============================================================================
# Battle
# =============================================================================

def _apply(section_params, overrides: dict, section: str):
    known = {f.name for f in fields(section_params)}
    unknown = set(overrides) - known
    if unknown:
        raise ValueError(f"Unknown {section} parameter(s): {sorted(unknown)}.")
    changes = dict(overrides)
    if 'weapon_multipliers' in changes:
        partial = {int(k): v for k, v in changes['weapon_multipliers'].items()}
        changes['weapon_multipliers'] = {**section_params.weapon_multipliers, **partial}
    return replace(section_params, **changes)


@dataclass(frozen=True)
class BattleParams:
    """All tunable constants for one battle."""

    combat: CombatParams = field(default_factory=CombatParams)
    morale: MoraleParams = field(default_factory=MoraleParams)

    def with_overrides(self, overrides: dict) -> 'BattleParams':
        """
        New params with nested overrides applied, e.g. ``{'combat': {'ranged_kill_rate': 0.005}}``.

        A partial ``weapon_multipliers`` dict merges into the current one. Unknown sections or keys, and invalid
        values, raise ValueError.
        """
        unknown = set(overrides) - {'combat', 'morale'}
        if unknown:
            raise ValueError(f"Unknown parameter section(s): {sorted(unknown)}.")
        return BattleParams(
            combat=_apply(self.combat, overrides.get('combat', {}), 'combat'),
            morale=_apply(self.morale, overrides.get('morale', {}), 'morale'),
        )

    def to_dict(self) -> dict:
        """JSON-safe dict of every parameter (weapon codes as string keys)."""
        combat = {f.name: getattr(self.combat, f.name) for f in fields(self.combat)}
        combat['weapon_multipliers'] = {str(k): v for k, v in sorted(combat['weapon_multipliers'].items())}
        morale = {f.name: getattr(self.morale, f.name) for f in fields(self.morale)}
        return {'combat': combat, 'morale': morale}

    @classmethod
    def from_dict(cls, data: dict) -> 'BattleParams':
        """Build params from a full or partial dict (missing values use config defaults)."""
        return cls().with_overrides(data)
