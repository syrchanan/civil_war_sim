import math

import pytest

from imperial_generals.battles.battle import Battle, BattleResult, UnitOutcome
from imperial_generals.config import get_config
from imperial_generals.params import AftermathParams, BattleParams
from imperial_generals.units import CavalryRegiment, Regiment
from imperial_generals.utils import Rng


def exact(**overrides):
    """Aftermath params with no randomness in the shares (spread 0)."""
    return BattleParams().with_overrides({'aftermath': dict(share_spread=0.0, **overrides)})


def rounded(x):
    return math.floor(x + 0.5)


def rout_battle(attacker_cls=Regiment, params=None, seed=3):
    if attacker_cls is CavalryRegiment:
        attacker = CavalryRegiment(1000, '8/8/1/0', subtype='dragoons')
    else:
        attacker = Regiment(1000, '8/8/1/0')
    b = Battle({'a': (0, attacker), 'x': (1, Regiment(400, '2/2/0/0'))}, rng=Rng(seed), params=params or exact())
    report = b.resolve_round(600, {'a': {'target': 'x', 'mode': 'ranged'}})
    return b, report


# =============================================================================
# Params
# =============================================================================

def test_aftermath_defaults_from_config():
    cfg = get_config()['aftermath']
    p = AftermathParams()
    for key, value in cfg.items():
        assert getattr(p, key) == value


@pytest.mark.parametrize("overrides", [
    dict(rout_capture_share=-0.1), dict(rout_capture_share=1.1),
    dict(cavalry_capture_multiplier=-1.0),
    dict(killed_share=1.5), dict(walking_wounded_share=-0.2),
    dict(wounded_captured_share=2.0), dict(wounded_return_share=-0.1),
    dict(share_spread=1.5),
])
def test_invalid_aftermath_params_raise(overrides):
    with pytest.raises(ValueError):
        AftermathParams(**overrides)


def test_battle_params_carry_aftermath_section():
    p = BattleParams().with_overrides({'aftermath': {'killed_share': 0.3}})
    assert p.aftermath.killed_share == 0.3
    assert BattleParams.from_dict(p.to_dict()) == p
    assert 'aftermath' in p.to_dict()


# =============================================================================
# Rout captures, at the moment a unit breaks
# =============================================================================

def test_breaking_unit_loses_a_share_of_its_remaining_men_as_prisoners():
    b, report = rout_battle()
    x = report.units['x']
    assert x.broken
    remaining_at_break = 400 - x.losses
    assert x.captured == rounded(0.10 * remaining_at_break)
    assert x.captured > 0
    assert x.size == 400 - x.losses - x.captured == b.units['x'].regiment.size


def test_prisoners_are_credited_to_the_other_side():
    b, report = rout_battle()
    assert report.prisoners == {0: report.units['x'].captured, 1: 0}
    assert b.prisoners == {0: report.units['x'].captured, 1: 0}


def test_enemy_cavalry_engaged_increases_rout_captures():
    _, plain = rout_battle(Regiment, seed=3)
    _, cav = rout_battle(CavalryRegiment, seed=3)
    remaining = 400 - cav.units['x'].losses
    assert cav.units['x'].captured == rounded(min(1.0, 0.10 * 2.0) * remaining)
    assert cav.units['x'].captured / (400 - cav.units['x'].losses) > \
        plain.units['x'].captured / (400 - plain.units['x'].losses)


def test_rout_capture_happens_once():
    b, first = rout_battle()
    second = b.resolve_round(60, {'a': {'target': 'x', 'mode': 'ranged'}})     # pursuit
    assert second.units['x'].captured == 0
    assert second.units['x'].losses > 0


def test_rout_capture_share_is_semi_random_but_seeded():
    params = BattleParams().with_overrides({'aftermath': {'share_spread': 0.5}})
    captured = {rout_battle(params=params, seed=s)[1].units['x'].captured for s in range(8)}
    assert len(captured) > 1
    assert rout_battle(params=params, seed=5)[1] == rout_battle(params=params, seed=5)[1]


def test_no_rout_capture_when_share_is_zero():
    _, report = rout_battle(params=exact(rout_capture_share=0.0))
    assert report.units['x'].broken and report.units['x'].captured == 0


# =============================================================================
# After the battle: killed / wounded / captured wounded / returned
# =============================================================================

def finished(field_held_by='auto', params=None, seed=3):
    b, report = rout_battle(params=params or exact(), seed=seed)
    sizes = {uid: u.size for uid, u in b.units.items()}
    hits = {uid: u.losses for uid, u in b.units.items()}
    return b, b.finish(field_held_by=field_held_by), sizes, hits


def test_finish_splits_hits_into_killed_and_wounded():
    b, result, _, hits = finished()
    assert isinstance(result, BattleResult)
    for uid, o in result.units.items():
        assert isinstance(o, UnitOutcome)
        assert o.hits == hits[uid]
        assert o.killed == rounded(0.22 * o.hits)
        assert o.killed + o.wounded == o.hits


def test_field_holder_is_automatic_when_one_side_is_all_broken():
    _, result, _, _ = finished()
    assert result.field_held_by == 0


def test_losing_side_has_walking_wounded_and_loses_the_rest_as_prisoners():
    _, result, _, _ = finished()
    x = result.units['x']
    assert x.walking_wounded == rounded(0.40 * x.wounded)
    left = x.wounded - x.walking_wounded
    assert x.wounded_captured == rounded(0.60 * left)
    assert x.wounded_returned == rounded(0.40 * (x.wounded - x.wounded_captured))


def test_field_holder_loses_no_wounded_as_prisoners():
    _, result, _, _ = finished()
    a = result.units['a']
    assert a.walking_wounded == 0 and a.wounded_captured == 0
    assert a.wounded_returned == rounded(0.40 * a.wounded)


def test_no_field_holder_means_no_wounded_captured():
    _, result, _, _ = finished(field_held_by=None)
    assert result.field_held_by is None
    assert all(o.wounded_captured == 0 for o in result.units.values())


def test_returned_wounded_restore_strength():
    b, result, sizes, _ = finished()
    for uid, o in result.units.items():
        assert o.final_size == sizes[uid] + o.wounded_returned == b.units[uid].regiment.size


def test_rout_captures_and_wounded_captured_add_up_in_prisoners():
    b, result, _, _ = finished()
    x = result.units['x']
    assert x.captured_in_rout > 0
    assert result.prisoners == {0: x.captured_in_rout + x.wounded_captured, 1: 0}


def test_explicit_field_holder():
    _, result, _, _ = finished(field_held_by=1)
    assert result.field_held_by == 1
    assert result.units['x'].wounded_captured == 0


@pytest.mark.parametrize("holder", [2, -1, 'union'])
def test_invalid_field_holder_raises(holder):
    b, _ = rout_battle()
    with pytest.raises(ValueError):
        b.finish(field_held_by=holder)


def test_battle_is_over_after_finish():
    b, _, _, _ = finished()
    with pytest.raises(RuntimeError):
        b.resolve_round(60, {})
    with pytest.raises(RuntimeError):
        b.finish()


def test_finish_is_seeded():
    params = BattleParams().with_overrides({'aftermath': {'share_spread': 0.5}})
    r1 = finished(params=params, seed=9)[1]
    r2 = finished(params=params, seed=9)[1]
    assert r1 == r2


# =============================================================================
# Guns captured: overrun (no crew left) or abandoned when a battery breaks
# =============================================================================

def charged_battery(crew=72, guns=8, seed=3, params=None):
    from imperial_generals.units import ArtilleryBattery
    battery = ArtilleryBattery(crew, '4/4/0/0', guns, subtype='battery')
    b = Battle({'c': (0, CavalryRegiment(1000, '6/6/0/1', subtype='heavy')), 'g': (1, battery)},
               rng=Rng(seed), params=params or exact())
    report = b.resolve_round(600, {'c': {'target': 'g', 'mode': 'melee'}})
    return b, battery, report


def test_broken_battery_escapes_only_with_guns_it_can_crew():
    b, battery, report = charged_battery()
    g = report.units['g']
    assert g.broken and g.size > 0
    kept = min(8, g.size // 7)
    assert battery.guns == kept
    assert g.guns_lost == 8 - kept > 0
    assert report.guns_captured == {0: 8 - kept, 1: 0}
    assert b.guns_captured == {0: 8 - kept, 1: 0}


def test_overrun_battery_loses_every_gun():
    b, battery, report = charged_battery(crew=1)
    g = report.units['g']
    assert g.size == 0
    assert battery.guns == 0
    assert g.guns_lost == 8
    assert b.guns_captured[0] == 8


def test_pursued_broken_battery_overrun_later_loses_the_rest():
    b, battery, first = charged_battery(crew=40, guns=8)     # can crew 5 guns
    assert first.units['g'].broken
    kept = battery.guns
    lost_first = first.units['g'].guns_lost
    while battery.size > 0:
        b.resolve_round(600, {'c': {'target': 'g', 'mode': 'melee'}})
    assert battery.guns == 0
    assert b.guns_captured[0] == lost_first + kept == 8


def test_battery_with_enough_crew_keeps_all_guns_when_it_breaks():
    b, battery, report = charged_battery(crew=200, guns=4)
    assert report.units['g'].broken and battery.size >= 28      # enough crew left for all 4 guns
    assert battery.guns == 4 and report.units['g'].guns_lost == 0


def test_non_artillery_never_loses_guns():
    _, report = rout_battle()
    assert all(u.guns_lost == 0 for u in report.units.values())
    assert report.guns_captured == {0: 0, 1: 0}


def test_battle_result_reports_guns_captured():
    b, battery, _ = charged_battery()
    result = b.finish()
    assert result.guns_captured == b.guns_captured
    assert result.units['g'].guns_lost == 8 - battery.guns


def test_auto_holder_can_be_side_1():
    b = Battle({'x': (0, Regiment(400, '2/2/0/0')), 'a': (1, Regiment(1000, '8/8/1/0'))}, rng=Rng(3), params=exact())
    b.resolve_round(600, {'a': {'target': 'x', 'mode': 'ranged'}})
    result = b.finish()
    assert result.field_held_by == 1
    assert result.prisoners[1] > 0 and result.prisoners[0] == 0


def test_auto_holder_is_none_when_both_sides_still_stand():
    b = Battle({'a': (0, Regiment(500, '5/5/0/0')), 'x': (1, Regiment(500, '5/5/0/0'))}, rng=Rng(1), params=exact())
    b.resolve_round(30, {'a': {'target': 'x', 'mode': 'ranged'}, 'x': {'target': 'a', 'mode': 'ranged'}})
    assert b.finish().field_held_by is None
