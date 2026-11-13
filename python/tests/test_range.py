"""
Range (positions pass P1): fire falls off with distance, from full effect at a weapon's close range to nothing at its
maximum range; a charge's approach takes as long as the distance needs. Units without a position fight as before.
"""

import pytest

from imperial_generals import api
from imperial_generals.battles.battle import Battle
from imperial_generals.params import BattleParams, RangeParams
from imperial_generals.units import ArtilleryBattery, CavalryRegiment, Regiment
from imperial_generals.utils import Position, Rng


def at(x, y, facing=None):
    return Position(x, y, 0, 0, 'open', facing)


def battle(a_place=None, x_place=None, params=None, seed=3, a=None):
    units = {'a': (0, a or Regiment(1000, '5/5/0/0')), 'x': (1, Regiment(1000, '5/5/1/0'))}
    b = Battle(units, rng=Rng(seed), params=params)
    if a_place is not None:
        b.units['a'].regiment.deploy(a_place)
    if x_place is not None:
        b.units['x'].regiment.deploy(x_place)
    return b


FIRE = {'a': {'target': 'x', 'mode': 'ranged'}, 'x': {'target': 'a', 'mode': 'ranged'}}


def rates(b, orders=FIRE):
    return {(e.attacker, e.mode): e.rate for e in b.engagements(orders)}


# --- the falloff ---------------------------------------------------------------------------------------------

def test_reach_is_full_up_to_close_range_then_falls_to_nothing_at_max_range():
    r = RangeParams()
    close, far = r.small_arms['0']['close'], r.small_arms['0']['max']
    assert r.reach(0.0, close, far) == 1.0
    assert r.reach(close, close, far) == 1.0
    assert r.reach((close + far) / 2, close, far) == pytest.approx(0.5)
    assert r.reach(far, close, far) == 0.0
    assert r.reach(far + 100, close, far) == 0.0
    curved = RangeParams(falloff_exponent=2.0)
    assert curved.reach((close + far) / 2, close, far) == pytest.approx(0.25)


def test_each_weapon_and_ammo_has_its_ranges():
    r = RangeParams()
    assert set(r.small_arms) == {'-2', '-1', '0', '1', '2'}
    assert set(r.artillery) == {'round_shot', 'shell', 'canister'}
    assert r.small_arms['1']['max'] > r.small_arms['0']['max']          # rifles reach further than smoothbores
    assert r.artillery['canister']['max'] < r.artillery['round_shot']['max']


@pytest.mark.parametrize('change, message', [
    ({'falloff_exponent': 0}, 'falloff_exponent'),
    ({'small_arms': {'0': {'close': 100, 'max': 50}}}, 'close'),
    ({'small_arms': {'0': {'close': -1, 'max': 50}}}, 'close'),
    ({'small_arms': {'0': {'close': 10, 'max': 20, 'far': 30}}}, 'close and max'),
    ({'small_arms': {'7': {'close': 10, 'max': 20}}}, 'weapon code'),
    ({'artillery': {'grape': {'close': 10, 'max': 20}}}, 'ammo'),
])
def test_bad_range_params_are_refused(change, message):
    with pytest.raises(ValueError, match=message):
        BattleParams().with_overrides({'range': change})


def test_range_tables_must_be_complete_mappings():
    with pytest.raises(ValueError, match='must be a mapping'):
        RangeParams(small_arms=[])
    with pytest.raises(ValueError, match='needs every weapon code'):
        RangeParams(small_arms={'0': {'close': 80, 'max': 250}})


def test_artillery_ranges_must_cover_every_ammo():
    with pytest.raises(ValueError, match='every ammo'):
        BattleParams().with_overrides({'combat': {'artillery_ammo': {'grape': 0.5}}})


# --- in battle -----------------------------------------------------------------------------------------------

def test_units_without_positions_fight_as_before():
    assert rates(battle()) == rates(battle(at(0, 0)))         # one side placed is not enough to measure
    plain, placed = battle(), battle()
    plain.resolve_round(60, FIRE)
    placed.resolve_round(60, FIRE)
    assert plain.to_dict()['units'] == placed.to_dict()['units']


def test_fire_falls_off_with_distance():
    r = RangeParams()
    smooth, rifle = r.small_arms['0'], r.small_arms['1']
    near = rates(battle(at(0, 0), at(0, smooth['close'])))
    assert near == rates(battle())                             # within close range: full effect
    mid = (smooth['close'] + smooth['max']) / 2
    half = rates(battle(at(0, 0), at(0, mid)))
    assert half[('a', 'ranged')] == pytest.approx(near[('a', 'ranged')] * 0.5)
    # the rifles opposite still reach further
    t = (mid - rifle['close']) / (rifle['max'] - rifle['close'])
    assert half[('x', 'ranged')] == pytest.approx(near[('x', 'ranged')] * min(1.0, 1 - t))


def test_beyond_max_range_there_is_no_fire_and_no_one_is_engaged():
    b = battle(at(0, 0), at(3000, 4000))                      # 5000 yards apart
    assert rates(b) == {}
    b.resolve_round(60, FIRE)
    assert b.units['a'].losses == b.units['x'].losses == 0
    assert b.units['a'].morale.resolve == 1.0                 # not engaged: no drain


def test_distance_is_measured_centre_to_centre_on_the_flat():
    b = battle(at(100, 100), at(400, 500))
    assert b.distance('a', 'x') == 500.0
    assert battle(at(0, 0)).distance('a', 'x') is None


def test_artillery_reach_depends_on_its_ammo():
    gun = ArtilleryBattery(72, '5/5/0/0', 8, subtype='battery')
    r = RangeParams()
    d = r.artillery['canister']['max'] + 50                   # too far for canister, fine for round shot
    b = battle(at(0, 0), at(0, d), a=gun)
    canister = rates(b, {'a': {'target': 'x', 'mode': 'ranged', 'ammo': 'canister'}})
    shot = rates(b, {'a': {'target': 'x', 'mode': 'ranged', 'ammo': 'round_shot'}})
    assert ('a', 'ranged') not in canister and shot[('a', 'ranged')] > 0
    assert b.reach('a', 'x', 'canister') == 0.0 and b.reach('a', 'x', 'round_shot') == 1.0
    assert b.reach('a', 'x') == b.reach('a', 'x', b.params.combat.artillery_default_ammo)


def test_reach_for_small_arms_uses_the_weapon_and_ignores_ammo():
    b = battle(at(0, 0), at(0, 10))
    assert b.reach('a', 'x') == 1.0
    assert battle().reach('a', 'x') is None


def test_closing_fire_on_a_charge_is_not_reduced_by_distance():
    cav = CavalryRegiment(400, '5/5/0/1', subtype='light')
    charge = {'a': {'target': 'x', 'mode': 'melee'}, 'x': {'target': 'a', 'mode': 'ranged'}}
    far = battle(at(0, 0), at(0, 600), a=cav)
    assert rates(far, charge)[('x', 'closing')] == rates(battle(a=cav), charge)[('x', 'closing')]


# --- charges -------------------------------------------------------------------------------------------------

def approach_end(b, orders, duration=60):
    report = b.resolve_round(duration, orders)
    return report.charges[0].resolved_at


def test_a_charge_takes_as_long_as_the_distance_needs_but_never_less_than_the_approach():
    p = BattleParams()
    speed, minimum = p.charge.speed['inf'], p.charge.approach_minutes['inf']
    charge = {'a': {'target': 'x', 'mode': 'melee'}}
    assert approach_end(battle(at(0, 0), at(0, 10)), charge) == minimum
    far = speed * (minimum + 3)
    assert approach_end(battle(at(0, 0), at(0, far)), charge) == pytest.approx(far / speed)
    assert approach_end(battle(), charge) == minimum
    # an approach longer than the round ends with the round
    assert approach_end(battle(at(0, 0), at(0, speed * 100)), charge, duration=20) == 20


def test_two_units_charging_each_other_close_the_gap_together():
    p = BattleParams()
    s = p.charge.speed['inf']
    d = 2 * s * 8
    both = {'a': {'target': 'x', 'mode': 'melee'}, 'x': {'target': 'a', 'mode': 'melee'}}
    assert approach_end(battle(at(0, 0), at(0, d)), both) == pytest.approx(d / (2 * s))


def test_charge_speeds_are_params():
    from dataclasses import replace
    with pytest.raises(ValueError, match='speed'):
        BattleParams().with_overrides({'charge': {'speed': {'inf': 0}}})
    with pytest.raises(ValueError, match='speed needs exactly'):
        replace(BattleParams().charge, speed={'inf': 100})


def test_scenarios_replay_units_moved_between_rounds():
    state = api.new_battle(SETUP)
    state, _ = api.step(state, 30, {'us': {'target': 'cs', 'mode': 'ranged'}})
    moved, _ = api.merge_plans(state, [{'format': 'imperial-generals-orders', 'version': 1, 'side': 1,
                                        'battle': {'seed': 7, 'round': 2},
                                        'orders': {}, 'positions': {'cs': {'x': 0, 'y': 150, 'facing': 180}}}])
    after, report = api.step(moved, 30, {'us': {'target': 'cs', 'mode': 'ranged'},
                                         'cs': {'target': 'us', 'mode': 'ranged'}})
    assert report['units']['cs']['losses'] > 0                # now within range
    scenario = api.scenario_from_state(after)
    assert scenario['units'][1]['position'] == {'x': 0, 'y': 2000, 'facing': None}
    assert 'positions' not in scenario['rounds'][0]
    assert scenario['rounds'][1]['positions'] == {'cs': {'x': 0, 'y': 150, 'facing': 180}}
    replayed, _, _ = api.run_scenario(scenario)
    assert replayed == after


def test_scenario_round_positions_are_checked():
    from imperial_generals.battles.setup import SetupError
    with pytest.raises(SetupError, match='Round 1: "positions" must be a mapping'):
        api.run_scenario({**SETUP, 'rounds': [{'duration': 30, 'positions': ['us']}]})
    with pytest.raises(SetupError, match='Round 1: unknown unit nobody in positions'):
        api.run_scenario({**SETUP, 'rounds': [{'duration': 30, 'positions': {'nobody': {'x': 0, 'y': 0}}}]})
    with pytest.raises(SetupError, match='Round 1: us: position needs x and y'):
        api.run_scenario({**SETUP, 'rounds': [{'duration': 30, 'positions': {'us': {'x': 0}}}]})


# --- setup files ---------------------------------------------------------------------------------------------

SETUP = {'seed': 7, 'units': [
    {'id': 'us', 'side': 0, 'size': 1000, 'stats': '5/5/0/0', 'position': {'x': 0, 'y': 0, 'facing': 0}},
    {'id': 'cs', 'side': 1, 'size': 1000, 'stats': '5/5/0/0', 'position': {'x': 0, 'y': 2000}}]}


def test_setup_places_units_on_open_ground():
    state = api.new_battle(SETUP)
    assert state['units'][0]['position'] == {'x': 0, 'y': 0, 'z': 0, 'cover': 0, 'terrain_type': 'open', 'facing': 0}
    assert state['units'][1]['position']['facing'] is None
    after, _ = api.step(state, 60, {'us': {'target': 'cs', 'mode': 'ranged'}})
    assert all(u['losses'] == 0 for u in after['units'])     # 2000 yards: out of musket range
    replayed, _, _ = api.run_scenario(api.scenario_from_state(after))
    assert replayed == after


@pytest.mark.parametrize('position, message', [
    ([0, 0], 'position must be a mapping'),
    ({'x': 0}, 'position needs x and y'),
    ({'x': 'a', 'y': 0}, 'x and y must be numbers'),
    ({'x': 0, 'y': 0, 'facing': 'north'}, 'facing must be a number'),
    ({'x': 0, 'y': 0, 'z': 5}, 'unknown position key'),
])
def test_bad_setup_positions_are_reported(position, message):
    from imperial_generals.battles.setup import SetupError
    bad = {**SETUP, 'units': [{**SETUP['units'][0], 'position': position}, SETUP['units'][1]]}
    with pytest.raises(SetupError, match=message):
        api.new_battle(bad)
