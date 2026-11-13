"""
Terrain (positions pass P4): the ground a battle is fought on, as a grid saved in the state file. The client generates
it; both engines only read it (height at a point, ground at a point), so every saved battle replays exactly.
"""

import pytest

from imperial_generals import api
from imperial_generals.battles.battle import Battle
from imperial_generals.battles.setup import SetupError
from imperial_generals.battles.terrain import GROUND, Terrain
from imperial_generals.units import Regiment
from imperial_generals.utils import Rng


def grid(columns=4, rows=3, cell=10.0, heights=None, ground=None):
    heights = heights if heights is not None else [float(i) for i in range(columns * rows)]
    ground = ground if ground is not None else 'o' * (columns * rows)
    return {'cell': cell, 'columns': columns, 'rows': rows, 'heights': heights, 'ground': ground,
            'meta': {'preset': 'test'}}


def test_ground_codes():
    assert GROUND == {'o': 'open', 'f': 'forest', 'r': 'rough'}


def test_heights_are_interpolated_between_cell_centres():
    # rows of heights 0..3, 4..7, 8..11; centres at 5, 15, 25, 35 (x) and 5, 15, 25 (y)
    t = Terrain.from_dict(grid())
    assert t.height_at(5, 5) == 0.0
    assert t.height_at(15, 5) == 1.0
    assert t.height_at(10, 5) == 0.5
    assert t.height_at(5, 10) == 2.0                # halfway down to the next row (+4)
    assert t.height_at(10, 10) == 2.5
    assert t.height_at(35, 25) == 11.0


def test_outside_the_centres_heights_hold_level_and_points_off_the_field_take_the_edge():
    t = Terrain.from_dict(grid())
    assert t.height_at(0, 0) == 0.0
    assert t.height_at(-50, 5) == 0.0
    assert t.height_at(40, 30) == 11.0
    assert t.height_at(1000, 1000) == 11.0


def test_ground_is_the_cell_containing_the_point():
    t = Terrain.from_dict(grid(ground='ofro' + 'oooo' + 'rrrf'))
    assert t.ground_at(0, 0) == 'open'
    assert t.ground_at(10, 0) == 'forest'          # a cell's lower edge belongs to it
    assert t.ground_at(25, 9.99) == 'rough'
    assert t.ground_at(39.9, 29.9) == 'forest'
    assert t.ground_at(40, 30) == 'forest'          # the far edge, and beyond, take the edge cell
    assert t.ground_at(-1, -1) == 'open'


def test_size_and_round_trip():
    t = Terrain.from_dict(grid())
    assert (t.width, t.height) == (40.0, 30.0)
    assert Terrain.from_dict(t.to_dict()) == t
    assert t.to_dict() == grid()


@pytest.mark.parametrize('change, message', [
    ({'cell': 0}, 'cell'),
    ({'columns': 0}, 'columns'),
    ({'rows': 1.5}, 'rows'),
    ({'heights': [0.0] * 5}, 'heights'),
    ({'heights': ['a'] * 12}, 'heights'),
    ({'heights': 'flat'}, 'heights must be a list'),
    ({'ground': 'oooo'}, 'ground'),
    ({'ground': 'x' * 12}, 'ground'),
    ({'meta': []}, 'meta'),
])
def test_bad_terrain_is_refused(change, message):
    with pytest.raises(ValueError, match=message):
        Terrain.from_dict({**grid(), **change})
    with pytest.raises(ValueError, match='missing'):
        Terrain.from_dict({k: v for k, v in grid().items() if k != 'heights'})


def test_a_battle_keeps_its_terrain_in_the_state_file():
    t = Terrain.from_dict(grid())
    b = Battle({'a': (0, Regiment(100, '5/5/0/0')), 'x': (1, Regiment(100, '5/5/0/0'))}, rng=Rng(1), terrain=t)
    data = b.to_dict()
    assert data['terrain'] == grid()
    assert Battle.from_dict(data).terrain == t
    plain = Battle({'a': (0, Regiment(100, '5/5/0/0')), 'x': (1, Regiment(100, '5/5/0/0'))}, rng=Rng(1))
    assert plain.terrain is None and plain.to_dict()['terrain'] is None
    del data['terrain']                                    # older files
    assert Battle.from_dict(data).terrain is None


SETUP = {'seed': 3, 'units': [{'id': 'us', 'side': 0, 'size': 100, 'stats': '5/5/0/0'},
                              {'id': 'cs', 'side': 1, 'size': 100, 'stats': '5/5/0/0'}]}


def test_setups_and_scenarios_carry_terrain():
    state = api.new_battle({**SETUP, 'terrain': grid()})
    assert state['terrain'] == grid()
    state, _ = api.step(state, 30, {})
    scenario = api.scenario_from_state(state)
    assert scenario['terrain'] == grid()
    replayed, _, _ = api.run_scenario(scenario)
    assert replayed == state
    assert 'terrain' not in api.scenario_from_state(api.new_battle(SETUP))


def test_bad_setup_terrain_is_reported():
    with pytest.raises(SetupError, match='terrain: cell'):
        api.new_battle({**SETUP, 'terrain': {**grid(), 'cell': -1}})
    with pytest.raises(SetupError, match='"terrain" must be a mapping'):
        api.new_battle({**SETUP, 'terrain': 'hills'})
