"""State file version 3: each unit's org (corps, division, brigade) and the battle's plan, carried for the web
client's game flow; the engine never acts on them."""

import json

import pytest

from imperial_generals import api
from imperial_generals.battles.battle import Battle, validate_org, validate_plan
from imperial_generals.battles.setup import SetupError, battle_from_setup
from imperial_generals.units import InfantryRegiment


def setup(**extra):
    units = [{'id': 'a', 'side': 0, 'type': 'inf', 'subtype': 'line', 'size': 500, 'stats': '5/5/0/0',
              'org': {'corps': 'II', 'division': 'Gibbon', 'brigade': 'Harrow'}},
             {'id': 'b', 'side': 1, 'type': 'inf', 'subtype': 'line', 'size': 500, 'stats': '5/5/0/0'}]
    return {'seed': 1, 'units': units, **extra}


PLAN = {'rounds_planned': 4, 'start_clock': '13:00', 'phase': 'deployment',
        'zones': {'0': {'x': 0, 'y': 800, 'w': 2000, 'h': 400}}}


def test_org_names_are_kept_in_order_and_empty_ones_dropped():
    assert validate_org({'brigade': 'Harrow', 'corps': 'II', 'division': ''}) == {'corps': 'II', 'brigade': 'Harrow'}
    assert validate_org({'division': None}) == {}


@pytest.mark.parametrize('org, message', [
    ('II', 'must be a mapping'),
    ({'regiment': 'x'}, "Unknown org key(s) ['regiment']"),
    ({'corps': 2}, 'org corps must be text'),
])
def test_bad_org(org, message):
    with pytest.raises(ValueError, match=message.replace('(', r'\(').replace(')', r'\)').replace('[', r'\[')):
        validate_org(org)


def test_a_plan_is_made_complete_with_zones_keyed_by_side():
    assert validate_plan(None) == {'rounds_planned': None, 'start_clock': None, 'phase': 'battle', 'zones': {}}
    assert validate_plan(PLAN) == {**PLAN, 'zones': {0: PLAN['zones']['0']}}
    assert validate_plan({'zones': None})['zones'] == {}


@pytest.mark.parametrize('plan, message', [
    ([], 'must be a mapping'),
    ({'turns': 3}, 'Unknown plan key'),
    ({'rounds_planned': 0}, 'rounds_planned must be a whole number'),
    ({'rounds_planned': True}, 'rounds_planned must be a whole number'),
    ({'rounds_planned': 2.5}, 'rounds_planned must be a whole number'),
    ({'start_clock': '1pm'}, 'start_clock must be'),
    ({'start_clock': '24:00'}, 'start_clock must be'),
    ({'start_clock': '12:60'}, 'start_clock must be'),
    ({'start_clock': 1300}, 'start_clock must be'),
    ({'phase': 'night'}, 'phase must be'),
    ({'zones': 'all'}, 'zones must be a mapping'),
    ({'zones': {2: {'x': 0, 'y': 0, 'w': 1, 'h': 1}}}, "zone's side must be 0 or 1"),
    ({'zones': {True: {'x': 0, 'y': 0, 'w': 1, 'h': 1}}}, "zone's side must be 0 or 1"),
    ({'zones': {0: {'x': 0, 'y': 0}}}, 'must be {x, y, w, h}'),
    ({'zones': {0: 'all'}}, 'must be {x, y, w, h}'),
    ({'zones': {0: {'x': 'a', 'y': 0, 'w': 1, 'h': 1}}}, 'zone x must be a number'),
    ({'zones': {0: {'x': True, 'y': 0, 'w': 1, 'h': 1}}}, 'zone x must be a number'),
    ({'zones': {0: {'x': float('inf'), 'y': 0, 'w': 1, 'h': 1}}}, 'zone x must be a number'),
    ({'zones': {1: {'x': 0, 'y': 0, 'w': 0, 'h': 1}}}, 'width and a height above 0'),
])
def test_bad_plan(plan, message):
    with pytest.raises(ValueError, match=message.replace('{', r'\{').replace('}', r'\}')):
        validate_plan(plan)


def test_setup_carries_org_and_plan_into_the_state():
    state = battle_from_setup(setup(plan=PLAN)).to_dict()
    assert state['version'] == 3
    assert state['units'][0]['org'] == {'corps': 'II', 'division': 'Gibbon', 'brigade': 'Harrow'}
    assert state['units'][1]['org'] == {}
    assert state['plan'] == PLAN
    assert Battle.from_dict(json.loads(json.dumps(state))).to_dict() == state


def test_setup_reports_bad_org_and_plan():
    data = setup(plan={'phase': 'night'})
    data['units'][1]['org'] = {'corps': 3}
    with pytest.raises(SetupError) as info:
        battle_from_setup(data)
    assert info.value.errors == ['Unit 2 (b): org corps must be text, got 3.',
                                 "plan: phase must be 'deployment' or 'battle', got 'night'."]


def test_a_battle_built_in_code_has_no_org_unless_given():
    b = Battle({'a': (0, InfantryRegiment(100, '5/5/0/0', subtype='line')),
                'b': {'side': 1, 'regiment': InfantryRegiment(100, '5/5/0/0', subtype='line'), 'org': {'brigade': 'X'}}})
    assert b.units['a'].org == {} and b.units['b'].org == {'brigade': 'X'}


def test_scenario_from_state_keeps_org_and_a_plan_that_says_anything():
    plain = api.scenario_from_state(battle_from_setup(setup()).to_dict())
    assert 'plan' not in plain and plain['units'][0]['org']['brigade'] == 'Harrow' and 'org' not in plain['units'][1]
    planned = api.scenario_from_state(battle_from_setup(setup(plan=PLAN)).to_dict())
    assert planned['plan'] == PLAN
