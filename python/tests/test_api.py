import json

import pytest

from imperial_generals import api
from imperial_generals.battles import Battle
from imperial_generals.battles.setup import SetupError

SETUP = {
    'meta': {'name': 'Test Ridge'},
    'seed': 7,
    'sides': ['Union', 'Confederate'],
    'units': [
        {'id': 'us', 'side': 'Union', 'type': 'inf', 'subtype': 'line', 'size': 1000, 'stats': '6/6/1/0'},
        {'id': 'cs', 'side': 'Confederate', 'type': 'inf', 'subtype': 'line', 'size': 1000, 'stats': '4/4/0/0'},
    ],
}
FIRE = {'us': {'target': 'cs', 'mode': 'ranged'}, 'cs': {'target': 'us', 'mode': 'ranged'}}


def test_new_battle_returns_a_json_safe_state():
    state = api.new_battle(SETUP)
    assert json.loads(json.dumps(state)) == state
    assert state['format'] == 'imperial-generals-battle'
    assert state['round'] == 0 and state['seed'] == 7
    assert api.new_battle(SETUP, seed=9)['seed'] == 9


def test_step_matches_the_battle_engine_and_leaves_the_input_alone():
    state = api.new_battle(SETUP)
    before = json.dumps(state)
    new_state, report = api.step(state, 90, FIRE)
    assert json.dumps(state) == before
    expected = Battle.from_setup(SETUP).resolve_round(90, FIRE)
    assert report['units']['cs']['losses'] == expected.units['cs'].losses
    assert report['round'] == 1 and new_state['round'] == 1
    assert json.loads(json.dumps(report)) == report
    assert report['events'] == []
    assert api.step(state, 90, FIRE, record_events=True)[1]['events']


def test_steps_chain_exactly_like_one_battle():
    state = api.new_battle(SETUP)
    state, _ = api.step(state, 60, FIRE)
    state, second = api.step(state, 60, FIRE)
    b = Battle.from_setup(SETUP)
    b.resolve_round(60, FIRE)
    assert second['units']['us']['losses'] == b.resolve_round(60, FIRE).units['us'].losses


def test_step_without_orders_is_all_idle():
    _, report = api.step(api.new_battle(SETUP), 30)
    assert report['engagements'] == [] and report['orders'] == {}


def test_preview_rolls_no_dice():
    state = api.new_battle(SETUP)
    arrows = api.preview(state, FIRE)
    assert [(a['attacker'], a['target'], a['mode']) for a in arrows] == [('cs', 'us', 'ranged'), ('us', 'cs', 'ranged')]
    assert all(a['rate'] > 0 for a in arrows)
    assert api.step(state, 60, FIRE)[1] == api.step(state, 60, FIRE)[1]


def test_finish_returns_the_settlement_and_a_finished_state():
    state, _ = api.step(api.new_battle(SETUP), 90, FIRE)
    final, result = api.finish(state)
    assert final['finished'] and final['result'] == result
    assert set(result['units']) == {'us', 'cs'}
    assert set(result['units']['us']) >= {'killed', 'wounded', 'wounded_returned', 'captured_in_rout', 'final_size'}
    assert api.finish(state, field_held_by=1)[1]['field_held_by'] == 1


def test_unit_names_and_side_names_come_with_the_state():
    state = api.new_battle(SETUP)
    assert state['meta']['sides'] == ['Union', 'Confederate']


# =============================================================================
# Scenarios: a setup plus a script of rounds
# =============================================================================

SCENARIO = {**SETUP, 'rounds': [{'duration': 90, 'orders': FIRE}, {'duration': 60, 'orders': FIRE}], 'finish': True}


def test_run_scenario_plays_every_round_then_finishes():
    state, reports, result = api.run_scenario(SCENARIO)
    assert [r['round'] for r in reports] == [1, 2]
    assert state['finished'] and state['result'] == result
    b = Battle.from_setup(SETUP)
    b.resolve_round(90, FIRE)
    b.resolve_round(60, FIRE)
    assert result['units']['cs']['hits'] == b.units['cs'].losses


def test_run_scenario_without_finish_leaves_the_battle_open():
    state, reports, result = api.run_scenario({**SCENARIO, 'finish': False})
    assert not state['finished'] and result is None and len(reports) == 2
    state, reports, result = api.run_scenario(SETUP)                  # no rounds at all
    assert reports == [] and result is None and state['round'] == 0


def test_run_scenario_seed_override():
    assert api.run_scenario(SCENARIO, seed=3)[0]['seed'] == 3


def test_round_without_orders_is_idle():
    state, reports, _ = api.run_scenario({**SETUP, 'rounds': [{'duration': 30}]})
    assert reports[0]['orders'] == {}


@pytest.mark.parametrize('changes, message', [
    ({'rounds': {'duration': 60}}, '"rounds" must be a list of rounds, each with a "duration".'),
    ({'rounds': ['x']}, 'Round 1: must be a mapping with a "duration".'),
    ({'rounds': [{'orders': FIRE}]}, 'Round 1: "duration" is missing (game minutes, e.g. 90).'),
    ({'rounds': [{'duration': 0}]}, 'Round 1: duration must be a positive number of minutes.'),
    ({'rounds': [{'duration': True}]}, 'Round 1: duration must be a positive number of minutes.'),
    ({'rounds': [{'duration': 60, 'orders': []}]}, 'Round 1: "orders" must be a mapping of unit id to order.'),
    ({'rounds': [{'duration': 60, 'order': FIRE}]}, 'Round 1: unknown key "order". Allowed: duration, orders.'),
    ({'finish': 'yes'}, '"finish" must be true or false.'),
])
def test_scenario_problems_are_reported(changes, message):
    with pytest.raises(SetupError) as info:
        api.run_scenario({**SETUP, **changes})
    assert info.value.errors == [message]


def test_bad_orders_say_which_round():
    rounds = [{'duration': 60, 'orders': FIRE}, {'duration': 60, 'orders': {'us': {'target': 'nobody', 'mode': 'ranged'}}}]
    with pytest.raises(SetupError) as info:
        api.run_scenario({**SETUP, 'rounds': rounds})
    assert info.value.errors == ["Round 2: 'us' targets unknown unit 'nobody'."]
    with pytest.raises(SetupError) as info:
        api.run_scenario({**SETUP, 'rounds': [{'duration': 60, 'orders': {'us': {'mode': 'charge'}}}]})
    assert info.value.errors[0].startswith('Round 1: mode must be one of')
    with pytest.raises(SetupError) as info:
        api.run_scenario({**SETUP, 'rounds': [{'duration': 60, 'orders': {'us': {'aim': 'cs'}}}]})
    assert info.value.errors == ["Round 1: Unknown order key(s) ['aim'] for 'us'; use target, mode, ammo."]


def test_setup_problems_come_before_running():
    with pytest.raises(SetupError):
        api.run_scenario({**SCENARIO, 'units': []})
