"""
Side modifiers: whole-battle effectiveness changes for one side (commander, supply, events), e.g. 'poor supply,
fire -10%'. Same shape as the per-round unit modifiers; they last until the admin changes them and stack with the
unit modifiers by multiplying.
"""

import pytest

from imperial_generals import api
from imperial_generals.battles.battle import Battle
from imperial_generals.battles.setup import SetupError
from imperial_generals.units import CavalryRegiment, Regiment
from imperial_generals.utils import Rng


def battle(seed=3, side_modifiers=None):
    return Battle({'a': (0, Regiment(1000, '5/5/0/0')), 'b': (0, CavalryRegiment(400, '5/5/0/0', subtype='light')),
                   'x': (1, Regiment(1000, '5/5/0/0'))}, rng=Rng(seed), side_modifiers=side_modifiers)


FIRE = {'a': {'target': 'x', 'mode': 'ranged'}, 'x': {'target': 'a', 'mode': 'ranged'}}
MELEE = {'a': {'target': 'x', 'mode': 'melee'}, 'x': {'target': 'a', 'mode': 'melee'}}


def rates(arrows):
    return {(e.attacker, e.mode): e.rate for e in arrows}


def test_side_fire_scales_every_unit_of_that_side():
    plain = rates(battle().engagements(FIRE))
    modified = rates(battle(side_modifiers={1: {'fire': -0.1}}).engagements(FIRE))
    assert modified[('x', 'ranged')] == pytest.approx(plain[('x', 'ranged')] * 0.9)
    assert modified[('a', 'ranged')] == plain[('a', 'ranged')]


def test_side_melee_scales_melee():
    b = battle(side_modifiers={0: {'melee': 0.2}})
    b.contacts = {frozenset(('a', 'x'))}
    plain = battle()
    plain.contacts = {frozenset(('a', 'x'))}
    assert rates(b.engagements(MELEE))[('a', 'melee')] == pytest.approx(rates(plain.engagements(MELEE))[('a', 'melee')] * 1.2)


def test_side_and_unit_modifiers_multiply():
    b = battle(side_modifiers={0: {'fire': 0.5}})
    plain = rates(battle().engagements(FIRE))
    both = rates(b.engagements(FIRE, {'a': {'fire': -0.5}}))
    assert both[('a', 'ranged')] == pytest.approx(plain[('a', 'ranged')] * 1.5 * 0.5)


def test_side_morale_scales_what_every_unit_spends_and_multiplies_with_the_unit_modifier():
    plain, steadier = battle(), battle(side_modifiers={1: {'morale': 0.5}})
    plain.resolve_round(60, FIRE)
    steadier.resolve_round(60, FIRE)
    assert plain.units['x'].morale.resolve < steadier.units['x'].morale.resolve
    # +100% on the side spends nothing whatever the unit modifier says
    b = battle(side_modifiers={1: {'morale': 1}})
    b.resolve_round(600, FIRE, modifiers={'x': {'morale': -0.5}})
    assert b.units['x'].morale.resolve == 1.0
    assert b.units['x'].morale.spend_factor == 1.0          # reset after the round


def test_zero_side_modifiers_change_nothing():
    plain, zero = battle(), battle(side_modifiers={0: {'fire': 0, 'melee': 0, 'morale': 0}, 1: {}})
    plain.resolve_round(60, FIRE)
    zero.resolve_round(60, FIRE)
    assert zero.to_dict()['units'] == plain.to_dict()['units']


def test_side_modifiers_last_until_changed_and_each_round_records_them():
    b = battle(side_modifiers={0: {'fire': -0.1, 'note': 'poor supply'}})
    first = b.resolve_round(30, FIRE)
    full = {0: {'fire': -0.1, 'melee': 0.0, 'morale': 0.0, 'note': 'poor supply'}}
    assert b.side_modifiers == full and first.side_modifiers == full
    assert b.resolve_round(30, FIRE).side_modifiers == full
    b.set_side_modifiers({1: {'morale': 0.2}})              # replaces them all
    third = b.resolve_round(30, FIRE)
    assert third.side_modifiers == {1: {'fire': 0.0, 'melee': 0.0, 'morale': 0.2, 'note': ''}}
    b.set_side_modifiers({})
    assert b.resolve_round(30, FIRE).side_modifiers == {}


def test_side_modifiers_round_trip_and_are_absent_in_older_files():
    b = battle(side_modifiers={1: {'melee': -0.3, 'note': 'tired'}})
    b.resolve_round(30, FIRE)
    data = b.to_dict()
    assert data['side_modifiers'] == {'1': {'fire': 0.0, 'melee': -0.3, 'morale': 0.0, 'note': 'tired'}}
    assert data['history'][0]['side_modifiers'] == data['side_modifiers']
    loaded = Battle.from_dict(data)
    assert loaded.side_modifiers == b.side_modifiers and loaded.history == b.history
    assert loaded.engagements(FIRE) == b.engagements(FIRE)
    del data['side_modifiers'], data['history'][0]['side_modifiers']
    loaded = Battle.from_dict(data)
    assert loaded.side_modifiers == {} and loaded.history[0].side_modifiers == {}


def test_side_keys_can_be_text_as_in_json():
    assert battle(side_modifiers={'0': {'fire': 0.1}}).side_modifiers == {
        0: {'fire': 0.1, 'melee': 0.0, 'morale': 0.0, 'note': ''}}


@pytest.mark.parametrize('mods, message', [
    ({2: {'fire': 0.1}}, 'side must be 0 or 1'),
    ({'Union': {'fire': 0.1}}, 'side must be 0 or 1'),
    ({0: {'range': 0.1}}, 'Unknown modifier'),
    ({0: {'fire': -1.5}}, 'between -1 and 1'),
    ({1: {'morale': 'x'}}, 'number'),
    ({1: {'note': 3}}, 'note'),
    ({0: 0.1}, 'mapping'),
    ([0], 'mapping of side'),
])
def test_bad_side_modifiers_are_refused(mods, message):
    with pytest.raises(ValueError, match=message):
        battle(side_modifiers=mods)
    b = battle(side_modifiers={0: {'fire': 0.1}})
    with pytest.raises(ValueError, match=message):
        b.set_side_modifiers(mods)
    assert b.side_modifiers[0]['fire'] == 0.1               # unchanged


SETUP = {'seed': 7, 'sides': ['Union', 'Confederate'], 'units': [
    {'id': 'us', 'side': 0, 'size': 1000, 'stats': '6/6/1/0'}, {'id': 'cs', 'side': 1, 'size': 1000, 'stats': '4/4/0/0'}]}
ORDERS = {'us': {'target': 'cs', 'mode': 'ranged'}, 'cs': {'target': 'us', 'mode': 'ranged'}}


def test_setup_sets_side_modifiers_by_number_or_name():
    state = api.new_battle({**SETUP, 'side_modifiers': {'Confederate': {'fire': -0.2, 'note': 'short of ammunition'}}})
    assert state['side_modifiers'] == {'1': {'fire': -0.2, 'melee': 0.0, 'morale': 0.0, 'note': 'short of ammunition'}}
    assert api.new_battle({**SETUP, 'side_modifiers': {0: {'morale': 0.1}}})['side_modifiers']['0']['morale'] == 0.1


@pytest.mark.parametrize('mods, message', [
    ({'Prussia': {'fire': 0.1}}, 'side_modifiers: unknown side "Prussia"'),
    ({0: {'fire': 3}}, 'between -1 and 1'),
    (['x'], '"side_modifiers" must be a mapping'),
])
def test_bad_setup_side_modifiers_are_reported(mods, message):
    with pytest.raises(SetupError, match=message):
        api.new_battle({**SETUP, 'side_modifiers': mods})


def test_api_sets_side_modifiers_between_rounds_and_scenarios_replay_them():
    state = api.new_battle(SETUP)
    state, _ = api.step(state, 30, ORDERS)
    changed = api.set_side_modifiers(state, {'1': {'fire': -0.5, 'note': 'rain'}})
    assert state['side_modifiers'] == {}                    # the input is never modified
    plain = {a['attacker']: a['rate'] for a in api.preview(state, ORDERS)}
    assert {a['attacker']: a['rate'] for a in api.preview(changed, ORDERS)}['cs'] == pytest.approx(plain['cs'] / 2)
    after, report = api.step(changed, 30, ORDERS)
    assert report['side_modifiers']['1']['note'] == 'rain'
    after, _ = api.step(after, 30, ORDERS)
    # the scenario sets them on the round where they changed, and replays exactly
    scenario = api.scenario_from_state(after)
    assert 'side_modifiers' not in scenario['rounds'][0] and 'side_modifiers' not in scenario['rounds'][2]
    assert scenario['rounds'][1]['side_modifiers'] == {'1': {'fire': -0.5, 'melee': 0.0, 'morale': 0.0, 'note': 'rain'}}
    replayed, _, _ = api.run_scenario(scenario)
    assert replayed == after


def test_scenario_clears_side_modifiers_with_an_empty_mapping():
    state = api.new_battle({**SETUP, 'side_modifiers': {0: {'fire': 0.3}}})
    state, _ = api.step(state, 30, ORDERS)
    state, _ = api.step(api.set_side_modifiers(state, {}), 30, ORDERS)
    scenario = api.scenario_from_state(state)
    assert scenario['side_modifiers'] == {'0': {'fire': 0.3, 'melee': 0.0, 'morale': 0.0, 'note': ''}}
    assert 'side_modifiers' not in scenario['rounds'][0] and scenario['rounds'][1]['side_modifiers'] == {}
    replayed, _, _ = api.run_scenario(scenario)
    assert replayed == state


def test_scenario_round_side_modifiers_are_checked():
    with pytest.raises(SetupError, match='Round 1: "side_modifiers" must be a mapping'):
        api.run_scenario({**SETUP, 'rounds': [{'duration': 30, 'side_modifiers': ['x']}]})
    with pytest.raises(SetupError, match="Round 1: A side modifier's side must be 0 or 1"):
        api.run_scenario({**SETUP, 'rounds': [{'duration': 30, 'side_modifiers': {'Prussia': {}}}]})
