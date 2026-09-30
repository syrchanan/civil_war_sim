"""
Per-unit morale model (roadmap A2).

A unit's live morale is ``initial_morale × resolve``, where ``resolve`` is the share of its morale budget left
(1 = fresh, 0 = broken). The budget is sized so that pure attrition breaks a unit at ``break_fraction`` of its
starting strength, a point set by veterancy and starting morale (15%–75% by default). Shock, fighting without
replying, and time in combat spend it faster; inflicting casualties restores it, capped at the starting value.

State changes depend only on game time (minutes) and per-unit events, so results don't depend on how a battle is
split into rounds. Powers go through the fdlibm ``exp``/``log`` ports to stay bit-identical with the TS port.
"""

from dataclasses import dataclass, field

from imperial_generals.config import get_config
from imperial_generals.utils.fdlibm import exp, log

_LN2 = 0.6931471805599453
# Floating-point slack when deciding a unit has spent its budget
_BREAK_EPSILON = 1e-9


def _model_default(key: str):
    return field(default_factory=lambda: get_config()['morale']['model'][key])


def _power(base: float, exponent: float) -> float:
    """base ** exponent for base > 0, via fdlibm so every platform agrees."""
    return exp(exponent * log(base))


@dataclass(frozen=True)
class MoraleParams:
    """Tunable morale constants; defaults come from ``morale.model`` in config/morale.yaml."""

    break_fraction_min: float = _model_default('break_fraction_min')
    break_fraction_max: float = _model_default('break_fraction_max')
    experience_weight: float = _model_default('experience_weight')
    break_curve: float = _model_default('break_curve')
    size_reference: float = _model_default('size_reference')
    size_exponent: float = _model_default('size_exponent')
    acceleration: float = _model_default('acceleration')
    shock_weight: float = _model_default('shock_weight')
    shock_half_life: float = _model_default('shock_half_life')
    helpless_weight: float = _model_default('helpless_weight')
    drain_per_hour: float = _model_default('drain_per_hour')
    gain_weight: float = _model_default('gain_weight')

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


def break_fraction(xp: int, morale_stat: int, params: MoraleParams) -> float:
    """
    Fraction of starting strength at which pure attrition breaks a unit.

    Blends experience and starting morale (both 1–10, clamped) into ``w`` in [0, 1], then maps
    ``w ** break_curve`` onto [break_fraction_min, break_fraction_max].
    """
    xp_norm = (max(1, min(10, xp)) - 1) / 9
    morale_norm = (max(1, min(10, morale_stat)) - 1) / 9
    w = params.experience_weight * xp_norm + (1 - params.experience_weight) * morale_norm
    curved = _power(w, params.break_curve) if w > 0 else 0.0
    return params.break_fraction_min + (params.break_fraction_max - params.break_fraction_min) * curved


class MoraleState:
    """
    Live morale of one unit for one engagement.

    Parameters
    ----------
    size : int
        Starting strength (N0).
    xp : int
        Experience stat (1–10).
    morale_stat : int
        Starting morale stat (1–10); starting raw morale is ``morale_stat × raw_scale_factor``.
    params : MoraleParams, optional
        Model constants; defaults to config.

    Raises
    ------
    ValueError
        If size is not positive.
    """

    def __init__(self, size: int, xp: int, morale_stat: int, params: MoraleParams | None = None) -> None:
        if size <= 0:
            raise ValueError(f"size must be positive, got {size}.")
        self.params: MoraleParams = params if params is not None else MoraleParams()
        self.initial_size: int = size
        self.initial_morale: float = float(morale_stat * get_config()['morale']['raw_scale_factor'])
        self.break_fraction: float = break_fraction(xp, morale_stat, self.params)
        self.resolve: float = 1.0
        self.shock: float = 0.0
        self.lost: int = 0
        self.broken: bool = False

        p = self.params
        fb = self.break_fraction
        # Pure attrition with acceleration k spends a*(f + k*f^2/2) by fraction f lost; the budget is 1 at f_break.
        self._cost_scale: float = (
            _power(size / p.size_reference, p.size_exponent)
            / (size * (fb + p.acceleration * fb * fb / 2))
        )

    @property
    def morale(self) -> float:
        """Live raw morale (0 when broken, at most initial_morale)."""
        return self.initial_morale * self.resolve

    def advance(self, minutes: float, engaged: bool) -> None:
        """
        Let game time pass: shock fades, and morale drains if the unit is engaged.

        Raises
        ------
        ValueError
            If minutes is negative.
        """
        if minutes < 0:
            raise ValueError(f"minutes must be >= 0, got {minutes}.")
        self.shock *= exp(-minutes * _LN2 / self.params.shock_half_life)
        if engaged and not self.broken:
            self._spend(self.params.drain_per_hour * minutes / 60)

    def take_loss(self, firing_back: bool) -> None:
        """Record one casualty; ``firing_back`` is False when the unit can't or doesn't reply."""
        p = self.params
        fraction_mid = (self.lost + 0.5) / self.initial_size
        cost = (
            self._cost_scale
            * (1 + p.acceleration * fraction_mid)
            * (1 + p.shock_weight * self.shock)
            * (1 + (0.0 if firing_back else p.helpless_weight))
        )
        self.lost += 1
        self.shock += 1 / self.initial_size
        if not self.broken:
            self._spend(cost)

    def inflict_loss(self, enemy_initial_size: int) -> None:
        """Record one casualty inflicted on an enemy unit of the given starting size."""
        if not self.broken:
            self.resolve = min(1.0, self.resolve + self.params.gain_weight / enemy_initial_size)

    def _spend(self, amount: float) -> None:
        self.resolve -= amount
        if self.resolve <= _BREAK_EPSILON:
            self.resolve = 0.0
            self.broken = True
