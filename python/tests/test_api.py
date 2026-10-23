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
    ({'finish': 'yes'}, '"finish" must be true, false, auto, none, 0, 1 or a side name (Union, Confederate).'),
    ({'finish': 2}, '"finish" must be true, false, auto, none, 0, 1 or a side name (Union, Confederate).'),
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
    assert info.value.errors == ["Round 1: Unknown order key(s) ['aim'] for 'us'; use target, mode, ammo, on_break."]


def test_setup_problems_come_before_running():
    with pytest.raises(SetupError):
        api.run_scenario({**SCENARIO, 'units': []})


# =============================================================================
# Scripted orders meet random breaks: impossible orders are skipped, not fatal
# =============================================================================

ROUT = {
    'seed': 1,
    'units': [
        {'id': 'us', 'side': 0, 'size': 3000, 'stats': '6/6/1/0'},
        {'id': 'cs', 'side': 1, 'size': 100, 'stats': '1/1/0/0'},
        {'id': 'cs2', 'side': 1, 'size': 500, 'stats': '5/5/0/0'},
    ],
    'rounds': [
        {'duration': 10, 'orders': {'us': {'target': 'cs', 'mode': 'ranged'}, 'cs': {'target': 'us', 'mode': 'ranged'}}},
        {'duration': 600, 'orders': {'us': {'target': 'cs', 'mode': 'ranged'}, 'cs': {'target': 'us', 'mode': 'ranged'}}},
        {'duration': 30, 'orders': {'us': {'target': 'cs', 'mode': 'ranged'}, 'cs2': {'target': 'us', 'mode': 'ranged'}}},
    ],
}


def test_scenario_skips_orders_that_can_no_longer_be_carried_out():
    state, reports, _ = api.run_scenario(ROUT)
    assert reports[0]['units']['cs']['broken'] and reports[0]['skipped_orders'] == {}
    # round 2: the broken unit can't fire back, but it can still be pursued
    assert reports[1]['skipped_orders'] == {'cs': 'cs is broken'}
    assert 'us' in reports[1]['orders']
    assert reports[1]['units']['cs']['size'] == 0
    # round 3: nothing left to shoot at
    assert reports[2]['skipped_orders'] == {'us': 'target cs is wiped out'}
    assert reports[2]['orders'] == {'cs2': {'target': 'us', 'mode': 'ranged', 'ammo': None, 'on_break': 'keep'}}


def test_scenario_finish_can_name_the_field_holder():
    base = {**SETUP, 'rounds': [{'duration': 30, 'orders': FIRE}]}
    assert api.run_scenario({**base, 'finish': 'Confederate'})[2]['field_held_by'] == 1
    assert api.run_scenario({**base, 'finish': 0})[2]['field_held_by'] == 0
    assert api.run_scenario({**base, 'finish': 'none'})[2]['field_held_by'] is None
    assert api.run_scenario({**base, 'finish': 'auto'})[2]['field_held_by'] is None
    rout_only = {**ROUT, 'units': ROUT['units'][:2], 'rounds': ROUT['rounds'][:2], 'finish': True}
    assert api.run_scenario(rout_only)[2]['field_held_by'] == 0                 # auto: side 1 is all out
    assert api.run_scenario({**base, 'finish': False})[2] is None


# =============================================================================
# Side summaries: order of battle before, performance after
# =============================================================================

def example():
    from imperial_generals.battles.setup import load_setup_file
    import os
    return load_setup_file(os.path.join(os.path.dirname(__file__), '../../scenarios/example_ridge.yaml'))


def test_order_of_battle_counts_men_by_kind():
    union, confed = api.order_of_battle(api.new_battle(example()))
    assert union['name'] == 'Union' and confed['name'] == 'Confederate'
    assert (union['units'], union['men']) == (3, 900 + 700 + 72)
    assert union['by_type'] == {'inf': {'units': 2, 'men': 1600}, 'art': {'units': 1, 'men': 72, 'guns': 8}}
    assert confed['by_type']['inf'] == {'units': 3, 'men': 2400}
    # averages weighted by men: (900*6 + 700*5 + 72*5) / 1672
    assert union['avg_experience'] == pytest.approx((900 * 6 + 700 * 5 + 72 * 5) / 1672)
    assert union['avg_morale'] == pytest.approx((900 * 6 + 700 * 5 + 72 * 5) / 1672)


def test_order_of_battle_uses_starting_strength_and_names_unnamed_sides():
    state, _, _ = api.run_scenario(example())
    assert api.order_of_battle(state) == api.order_of_battle(api.new_battle(example()))   # as the battle began
    plain = api.new_battle({'units': [{'id': 'a', 'side': 0, 'size': 10, 'stats': '5/5/0/0'},
                                      {'id': 'b', 'side': 1, 'type': 'cav', 'subtype': 'light', 'size': 20,
                                       'stats': '5/5/0/1'}]})
    a, b = api.order_of_battle(plain)
    assert (a['name'], b['name']) == ('Side 0', 'Side 1')
    assert a['by_type'] == {'inf': {'units': 1, 'men': 10}}                   # generic units count as infantry
    assert b['by_type'] == {'cav': {'units': 1, 'men': 20}}


def test_side_summary_adds_up():
    state, _, result = api.run_scenario(example())
    sides = api.side_summary(state)
    for side, s in enumerate(sides):
        units = [u for u in state['units'] if u['side'] == side]
        assert s['started'] == sum(u['initial_size'] for u in units)
        assert s['final'] == sum(u['size'] for u in units)
        assert s['started'] - s['killed'] - s['wounded'] - s['prisoners_lost'] + s['returned'] == s['final']
        assert s['hits_taken'] == s['killed'] + s['wounded'] + sum(
            result['units'][u['id']]['wounded_captured'] for u in units)
        assert s['loss_share'] == pytest.approx((s['started'] - s['final']) / s['started'])
        assert s['exchange_ratio'] == pytest.approx(s['hits_inflicted'] / s['hits_taken'])
        assert s['units_out'] == sum(u['morale']['broken'] or u['size'] == 0 for u in units)
    union, confed = sides
    assert union['hits_inflicted'] == confed['hits_taken']
    assert union['prisoners_taken'] == confed['prisoners_lost']
    assert confed['prisoners_taken'] == union['prisoners_lost']
    assert union['guns_lost'] == confed['guns_taken'] == 2


def test_side_summary_needs_a_finished_battle():
    with pytest.raises(ValueError, match='finish'):
        api.side_summary(api.new_battle(example()))


def test_exchange_ratio_without_losses_is_none():
    state, _, _ = api.run_scenario({**SETUP, 'rounds': [{'duration': 60, 'orders': {
        'us': {'target': 'cs', 'mode': 'ranged'}}}], 'finish': True})
    union, confed = api.side_summary(state)
    assert union['hits_taken'] == 0 and union['exchange_ratio'] is None
    assert confed['exchange_ratio'] == 0


def test_run_scenario_takes_parameter_overrides():
    state, _, _ = api.run_scenario(SCENARIO, overrides={'combat': {'ranged_kill_rate': 1e-9}})
    assert state['params']['combat']['ranged_kill_rate'] == 1e-9
    assert all(u['losses'] == 0 for u in state['units'])
