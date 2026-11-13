"""
Elevation and line of sight (positions pass P5): fire from higher ground tells more, uphill less; ground or woods
rising above the line between two units block fire. Without terrain nothing changes.
"""

import pytest

from imperial_generals import api
from imperial_generals.battles.battle import Battle
from imperial_generals.battles.terrain import Terrain
from imperial_generals.params import BattleParams, SightParams
from imperial_generals.units import ArtilleryBattery, CavalryRegiment, Regiment
from imperial_generals.utils import Position, Rng


def at(x, y, facing=None):
    return Position(x, y, 0, 0, 'open', facing)


def field(heights=None, ground=None, columns=40, rows=5, cell=10.0):
    """A strip 400 yards long (x) and 50 deep, flat unless ``heights(column)`` says otherwise."""
    hs = [float(heights(c)) if heights else 0.0 for _ in range(rows) for c in range(columns)]
    gs = ''.join(ground(c) if ground else 'o' for _ in range(rows) for c in range(columns))
    return Terrain(cell, columns, rows, tuple(hs), gs, {})


def battle(terrain, a_x=50.0, x_x=250.0, a=None, x=None, params=None):
    b = Battle({'a': (0, a or Regiment(1000, '5/5/0/0')), 'x': (1, x or Regiment(1000, '5/5/1/0'))},
               rng=Rng(3), params=params, terrain=terrain)
    b.units['a'].regiment.deploy(at(a_x, 25.0))
    b.units['x'].regiment.deploy(at(x_x, 25.0))
    return b


FIRE = {'a': {'target': 'x', 'mode': 'ranged'}, 'x': {'target': 'a', 'mode': 'ranged'}}


def rates(b, orders=FIRE):
    return {(e.attacker, e.mode): e.rate for e in b.engagements(orders)}


# --- line of sight ---------------------------------------------------------------------------------------------

def test_on_flat_open_ground_everyone_sees_everyone():
    b = battle(field())
    assert b.line_of_sight('a', 'x') and b.line_of_sight('x', 'a')


def test_a_ridge_between_blocks_fire_both_ways():
    ridge = field(heights=lambda c: 20 if 14 <= c <= 16 else 0)        # 20 yards high, 140-170 yards along
    b = battle(ridge)
    assert not b.line_of_sight('a', 'x') and not b.line_of_sight('x', 'a')
    assert rates(b) == {}
    low = field(heights=lambda c: 1 if 14 <= c <= 16 else 0)          # a fold lower than eye height
    assert battle(low).line_of_sight('a', 'x')


def test_from_high_ground_you_see_over_a_lower_rise():
    # the firer on a 30-yard hill, a 10-yard rise halfway, the target on the flat
    t = field(heights=lambda c: 30 if c <= 7 else 10 if 14 <= c <= 16 else 0)
    assert battle(t).line_of_sight('a', 'x')


def test_woods_between_block_but_units_at_a_wood_edge_see_out():
    woods = field(ground=lambda c: 'f' if 14 <= c <= 18 else 'o')     # trees 140-190 yards along
    assert not battle(woods).line_of_sight('a', 'x')
    edge = field(ground=lambda c: 'f' if c >= 22 else 'o')            # x stands 30 yards inside the wood's edge
    assert battle(edge, x_x=245.0).line_of_sight('a', 'x')
    deep = field(ground=lambda c: 'f' if c >= 18 else 'o')            # 65 yards in: the trees hide it
    assert not battle(deep, x_x=245.0).line_of_sight('a', 'x')


def test_without_terrain_or_positions_sight_is_never_blocked():
    b = Battle({'a': (0, Regiment(100, '5/5/0/0')), 'x': (1, Regiment(100, '5/5/0/0'))}, rng=Rng(1))
    assert b.line_of_sight('a', 'x')
    b.units['a'].regiment.deploy(at(0, 0))
    assert b.line_of_sight('a', 'x')
    t = battle(field(heights=lambda c: 20 if 14 <= c <= 16 else 0))
    t.units['x'].regiment.position = None
    assert t.line_of_sight('a', 'x')


def test_cavalry_sees_from_the_saddle():
    hedge = field(heights=lambda c: 2.2 if 14 <= c <= 16 else 0)      # a bank 2.2 yards high
    assert not battle(hedge).line_of_sight('a', 'x')                   # eye 2 yards, target 2 yards: hidden
    cav = CavalryRegiment(300, '5/5/0/0', subtype='light')
    assert battle(hedge, a=cav).line_of_sight('a', 'x')                # 3 yards up in the saddle


def test_closing_fire_ignores_sight():
    ridge = field(heights=lambda c: 20 if 14 <= c <= 16 else 0)
    cav = CavalryRegiment(300, '5/5/0/1', subtype='light')
    b = battle(ridge, a=cav)
    got = rates(b, {'a': {'target': 'x', 'mode': 'melee'}, 'x': {'target': 'a', 'mode': 'ranged'}})
    assert ('x', 'closing') in got


def test_artillery_needs_sight_too():
    ridge = field(heights=lambda c: 20 if 14 <= c <= 16 else 0)
    gun = ArtilleryBattery(72, '5/5/0/0', 8, subtype='battery')
    assert rates(battle(ridge, a=gun), {'a': {'target': 'x', 'mode': 'ranged'}}) == {}


# --- elevation -------------------------------------------------------------------------------------------------

def test_fire_from_higher_ground_tells_more_and_uphill_less_up_to_a_limit():
    p = SightParams()
    slope = field(heights=lambda c: max(0.0, 20 - c))                 # falling from 20 yards to 0 at 200 yards
    b = battle(slope, a_x=55.0, x_x=255.0)
    dz = slope.height_at(55, 25) - slope.height_at(255, 25)
    assert b.elevation_bonus('a', 'x') == pytest.approx(min(p.elevation_max, dz / p.elevation_scale))
    assert b.elevation_bonus('x', 'a') == pytest.approx(-b.elevation_bonus('a', 'x'))
    flat = rates(battle(field(), a_x=55.0, x_x=255.0))
    got = rates(b)
    assert got[('a', 'ranged')] == pytest.approx(flat[('a', 'ranged')] * (1 + b.elevation_bonus('a', 'x')))
    assert got[('x', 'ranged')] == pytest.approx(flat[('x', 'ranged')] * (1 + b.elevation_bonus('x', 'a')))
    cliff = field(heights=lambda c: 100 if c <= 10 else 0)
    assert battle(cliff, a_x=55.0, x_x=255.0).elevation_bonus('a', 'x') == p.elevation_max
    assert battle(field()).elevation_bonus('a', 'x') == 0.0
    assert Battle({'a': (0, Regiment(9, '5/5/0/0')), 'x': (1, Regiment(9, '5/5/0/0'))}).elevation_bonus('a', 'x') == 0.0


def test_no_terrain_changes_nothing():
    plain = Battle({'a': (0, Regiment(1000, '5/5/0/0')), 'x': (1, Regiment(1000, '5/5/1/0'))}, rng=Rng(3))
    flat = battle(field())
    plain.units['a'].regiment.deploy(at(50, 25))
    plain.units['x'].regiment.deploy(at(250, 25))
    assert rates(plain) == rates(flat)


@pytest.mark.parametrize('change, message', [
    ({'eye_height': {'inf': -1}}, 'eye_height'), ({'forest_height': -1}, 'forest_height'),
    ({'sample_step': 0}, 'sample_step'), ({'edge_clear': -1}, 'edge_clear'),
    ({'elevation_scale': 0}, 'elevation_scale'), ({'elevation_max': 1.5}, 'elevation_max'),
])
def test_bad_sight_params_are_refused(change, message):
    with pytest.raises(ValueError, match=message):
        BattleParams().with_overrides({'sight': change})
    with pytest.raises(ValueError, match='eye_height needs exactly'):
        SightParams(eye_height={'inf': 2.0})


def test_a_scenario_on_terrain_replays_exactly():
    t = field(heights=lambda c: max(0.0, 20 - c), ground=lambda c: 'f' if c == 30 else 'o')
    setup = {'seed': 5, 'terrain': t.to_dict(), 'units': [
        {'id': 'us', 'side': 0, 'size': 800, 'stats': '5/5/1/0', 'position': {'x': 60, 'y': 25, 'facing': 90}},
        {'id': 'cs', 'side': 1, 'size': 800, 'stats': '5/5/1/0', 'position': {'x': 300, 'y': 25, 'facing': 270}}]}
    fire = {'us': {'target': 'cs', 'mode': 'ranged'}, 'cs': {'target': 'us', 'mode': 'ranged'}}
    state, _, _ = api.run_scenario({**setup, 'rounds': [{'duration': 60, 'orders': fire}]})
    replayed, _, _ = api.run_scenario(api.scenario_from_state(state))
    assert replayed == state
