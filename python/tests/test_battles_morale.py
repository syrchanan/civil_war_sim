import math

import pytest

from imperial_generals.battles.morale import MoraleParams, MoraleState, break_fraction
from imperial_generals.config import get_config


def pure_attrition(**overrides):
    """Params with every modifier off except the ones overridden."""
    base = dict(size_exponent=0.0, acceleration=0.0, shock_weight=0.0,
                helpless_weight=0.0, drain_per_hour=0.0, gain_weight=0.0)
    base.update(overrides)
    return MoraleParams(**base)


def lose(state, n, firing_back=True):
    for _ in range(n):
        state.take_loss(firing_back=firing_back)


# =============================================================================
# Params
# =============================================================================

def test_params_default_from_config():
    cfg = get_config()['morale']['model']
    params = MoraleParams()
    for key, value in cfg.items():
        assert getattr(params, key) == value


@pytest.mark.parametrize("overrides", [
    dict(break_fraction_min=0.8, break_fraction_max=0.7),   # min > max
    dict(break_fraction_min=0.0),                           # must be > 0
    dict(break_fraction_max=1.1),                           # must be <= 1
    dict(experience_weight=1.5),                            # must be in [0, 1]
    dict(break_curve=0.0),                                  # must be > 0
    dict(size_reference=0),                                 # must be > 0
    dict(shock_half_life=0.0),                              # must be > 0
    dict(acceleration=-1.0),                                # weights must be >= 0
    dict(shock_weight=-1.0),
    dict(helpless_weight=-1.0),
    dict(drain_per_hour=-0.1),
    dict(gain_weight=-0.1),
])
def test_invalid_params_raise(overrides):
    with pytest.raises(ValueError):
        MoraleParams(**overrides)


# =============================================================================
# Break point from veterancy + starting morale
# =============================================================================

def test_break_fraction_extremes():
    p = MoraleParams(break_fraction_min=0.15, break_fraction_max=0.75)
    assert break_fraction(1, 1, p) == pytest.approx(0.15)
    assert break_fraction(10, 10, p) == pytest.approx(0.75)


def test_break_fraction_average_unit_in_target_band():
    p = MoraleParams(break_fraction_min=0.15, break_fraction_max=0.75, experience_weight=0.5, break_curve=1.5)
    assert break_fraction(5, 5, p) == pytest.approx(0.15 + 0.60 * (4 / 9) ** 1.5)
    assert 0.25 <= break_fraction(5, 5, p) <= 0.35


def test_break_fraction_experience_weight():
    p_xp = MoraleParams(experience_weight=1.0, break_curve=1.0)
    p_mo = MoraleParams(experience_weight=0.0, break_curve=1.0)
    # veteran with poor starting morale: only experience counts at weight 1
    assert break_fraction(10, 1, p_xp) == pytest.approx(p_xp.break_fraction_max)
    assert break_fraction(10, 1, p_mo) == pytest.approx(p_mo.break_fraction_min)


def test_break_fraction_increases_with_veterancy_and_morale():
    p = MoraleParams()
    assert break_fraction(3, 5, p) < break_fraction(7, 5, p)
    assert break_fraction(5, 3, p) < break_fraction(5, 7, p)


def test_break_fraction_clamps_stats_to_1_10():
    p = MoraleParams()
    assert break_fraction(0, 0, p) == break_fraction(1, 1, p)
    assert break_fraction(12, 15, p) == break_fraction(10, 10, p)


# =============================================================================
# State basics
# =============================================================================

def test_initial_state():
    s = MoraleState(size=1000, xp=5, morale_stat=6, params=MoraleParams())
    assert s.initial_morale == 60.0
    assert s.morale == 60.0
    assert s.resolve == 1.0
    assert s.lost == 0
    assert not s.broken
    assert s.break_fraction == break_fraction(5, 6, s.params)


def test_default_params_used_when_omitted():
    assert MoraleState(size=100, xp=4, morale_stat=4).params == MoraleParams()


@pytest.mark.parametrize("size", [0, -5])
def test_invalid_size_raises(size):
    with pytest.raises(ValueError):
        MoraleState(size=size, xp=4, morale_stat=4)


# =============================================================================
# Pure attrition breaks at f_break — for any size, with or without acceleration
# =============================================================================

@pytest.mark.parametrize("size", [200, 1000, 4000])
@pytest.mark.parametrize("acceleration", [0.0, 1.0, 3.0])
def test_pure_attrition_breaks_at_break_fraction(size, acceleration):
    s = MoraleState(size=size, xp=5, morale_stat=5, params=pure_attrition(acceleration=acceleration))
    while not s.broken:
        s.take_loss(firing_back=True)
    assert abs(s.lost - s.break_fraction * size) <= 1


def test_same_fraction_same_resolve_at_any_size_when_size_exponent_zero():
    small = MoraleState(size=200, xp=5, morale_stat=5, params=pure_attrition(acceleration=1.0))
    big = MoraleState(size=4000, xp=5, morale_stat=5, params=pure_attrition(acceleration=1.0))
    lose(small, 20)
    lose(big, 400)
    assert small.resolve == pytest.approx(big.resolve, abs=1e-9)


def test_size_exponent_negative_makes_big_units_steadier():
    p = pure_attrition(size_exponent=-0.2, size_reference=500)
    small = MoraleState(size=200, xp=5, morale_stat=5, params=p)
    big = MoraleState(size=4000, xp=5, morale_stat=5, params=p)
    lose(small, 20)
    lose(big, 400)
    assert big.resolve > small.resolve


def test_acceleration_makes_later_losses_cost_more():
    s = MoraleState(size=1000, xp=5, morale_stat=5, params=pure_attrition(acceleration=2.0))
    lose(s, 50)
    first = 1.0 - s.resolve
    before = s.resolve
    lose(s, 50)
    second = before - s.resolve
    assert second > first


def test_constant_rate_without_acceleration():
    s = MoraleState(size=1000, xp=5, morale_stat=5, params=pure_attrition())
    lose(s, 50)
    first = 1.0 - s.resolve
    before = s.resolve
    lose(s, 50)
    assert before - s.resolve == pytest.approx(first)


def test_morale_is_initial_times_resolve():
    s = MoraleState(size=1000, xp=5, morale_stat=8, params=pure_attrition())
    lose(s, 100)
    assert s.morale == pytest.approx(80.0 * s.resolve)


# =============================================================================
# Shock: rapid losses hurt more, fading with a half-life in game minutes
# =============================================================================

def test_rapid_losses_hurt_more_than_spread_out_losses():
    p = pure_attrition(shock_weight=5.0, shock_half_life=10.0)
    fast = MoraleState(size=1000, xp=5, morale_stat=5, params=p)
    slow = MoraleState(size=1000, xp=5, morale_stat=5, params=p)
    for _ in range(100):
        fast.advance(0.1, engaged=True)
        fast.take_loss(firing_back=True)
        slow.advance(10.0, engaged=True)
        slow.take_loss(firing_back=True)
    assert fast.resolve < slow.resolve


def test_shock_halves_after_one_half_life():
    s = MoraleState(size=100, xp=5, morale_stat=5, params=pure_attrition(shock_weight=1.0, shock_half_life=15.0))
    lose(s, 10)
    assert s.shock == pytest.approx(0.10)
    s.advance(15.0, engaged=False)
    assert s.shock == pytest.approx(0.05)


def test_shock_decay_does_not_depend_on_how_time_is_split():
    p = pure_attrition(shock_weight=1.0, shock_half_life=15.0)
    a = MoraleState(size=100, xp=5, morale_stat=5, params=p)
    b = MoraleState(size=100, xp=5, morale_stat=5, params=p)
    lose(a, 10)
    lose(b, 10)
    a.advance(60.0, engaged=False)
    for _ in range(4):
        b.advance(15.0, engaged=False)
    assert a.shock == pytest.approx(b.shock, rel=1e-12)


# =============================================================================
# Helplessness: taking fire without replying
# =============================================================================

def test_losses_while_not_firing_back_cost_more():
    p = pure_attrition(helpless_weight=0.5)
    replying = MoraleState(size=1000, xp=5, morale_stat=5, params=p)
    helpless = MoraleState(size=1000, xp=5, morale_stat=5, params=p)
    lose(replying, 10, firing_back=True)
    lose(helpless, 10, firing_back=False)
    assert (1.0 - helpless.resolve) == pytest.approx(1.5 * (1.0 - replying.resolve))


# =============================================================================
# Drain: morale wears down over time in combat, static when idle
# =============================================================================

def test_drain_while_engaged():
    s = MoraleState(size=1000, xp=5, morale_stat=5, params=pure_attrition(drain_per_hour=0.05))
    s.advance(60.0, engaged=True)
    assert s.resolve == pytest.approx(0.95)


def test_no_drain_while_idle():
    s = MoraleState(size=1000, xp=5, morale_stat=5, params=pure_attrition(drain_per_hour=0.05))
    s.advance(600.0, engaged=False)
    assert s.resolve == 1.0


def test_drain_does_not_depend_on_how_time_is_split():
    p = pure_attrition(drain_per_hour=0.05)
    a = MoraleState(size=1000, xp=5, morale_stat=5, params=p)
    b = MoraleState(size=1000, xp=5, morale_stat=5, params=p)
    a.advance(120.0, engaged=True)
    for _ in range(8):
        b.advance(15.0, engaged=True)
    assert a.resolve == pytest.approx(b.resolve)


def test_drain_alone_can_break_a_unit():
    s = MoraleState(size=1000, xp=5, morale_stat=5, params=pure_attrition(drain_per_hour=0.5))
    s.advance(180.0, engaged=True)
    assert s.broken
    assert s.resolve == 0.0


def test_negative_time_raises():
    with pytest.raises(ValueError):
        MoraleState(size=100, xp=5, morale_stat=5).advance(-1.0, engaged=True)


# =============================================================================
# Gains from inflicting casualties, capped at starting morale
# =============================================================================

def test_inflicting_losses_restores_resolve():
    s = MoraleState(size=1000, xp=5, morale_stat=5, params=pure_attrition(gain_weight=0.5))
    lose(s, 100)
    before = s.resolve
    for _ in range(100):
        s.inflict_loss(enemy_initial_size=1000)   # 10% of the enemy
    assert s.resolve == pytest.approx(before + 0.05)


def test_gains_are_capped_at_starting_morale():
    s = MoraleState(size=1000, xp=5, morale_stat=5, params=pure_attrition(gain_weight=0.5))
    for _ in range(500):
        s.inflict_loss(enemy_initial_size=1000)
    assert s.resolve == 1.0
    assert s.morale == s.initial_morale


# =============================================================================
# Breaking is permanent for the engagement
# =============================================================================

def test_broken_is_sticky():
    s = MoraleState(size=100, xp=1, morale_stat=1, params=pure_attrition(gain_weight=1.0, drain_per_hour=0.1))
    while not s.broken:
        s.take_loss(firing_back=True)
    for _ in range(50):
        s.inflict_loss(enemy_initial_size=100)
    s.advance(60.0, engaged=True)
    assert s.broken
    assert s.resolve == 0.0
    assert s.morale == 0.0


def test_green_unit_breaks_well_before_veteran():
    green = MoraleState(size=1000, xp=1, morale_stat=2, params=pure_attrition())
    veteran = MoraleState(size=1000, xp=9, morale_stat=8, params=pure_attrition())
    lose(green, 200)
    lose(veteran, 200)
    assert green.broken
    assert not veteran.broken
