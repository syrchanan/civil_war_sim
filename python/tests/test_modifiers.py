"""Admin modifiers: per-unit, one-round effectiveness changes (fire, melee, morale), e.g. 'uphill, fire -15%'."""

import pytest

from imperial_generals import api
from imperial_generals.battles.battle import Battle
from imperial_generals.units import CavalryRegiment, Regiment
from imperial_generals.utils import Rng


def battle(seed=3):
    return Battle({'a': (0, Regiment(1000, '5/5/0/0')), 'b': (0, CavalryRegiment(400, '5/5/0/0', subtype='light')),
                   'x': (1, Regiment(1000, '5/5/0/0'))}, rng=Rng(seed))


FIRE = {'a': {'target': 'x', 'mode': 'ranged'}, 'x': {'target': 'a', 'mode': 'ranged'}}


def rates(arrows):
    return {(e.attacker, e.mode): e.rate for e in arrows}


def test_fire_scales_the_casualties_a_unit_inflicts_by_fire():
    b = battle()
    plain = rates(b.engagements(FIRE))
    modified = rates(b.engagements(FIRE, {'a': {'fire': -0.25}}))
    assert modified[('a', 'ranged')] == pytest.approx(plain[('a', 'ranged')] * 0.75)
    assert modified[('x', 'ranged')] == plain[('x', 'ranged')]           # only the modified unit


def test_melee_scales_melee_but_not_fire():
    b = battle()
    b.contacts = {frozenset(('a', 'x'))}
    melee = {'a': {'target': 'x', 'mode': 'melee'}, 'x': {'target': 'a', 'mode': 'melee'}}
    plain = rates(b.engagements(melee))
    modified = rates(b.engagements(melee, {'a': {'melee': 0.5, 'fire': -1}}))
    assert modified[('a', 'melee')] == pytest.approx(plain[('a', 'melee')] * 1.5)


def test_closing_fire_on_a_charge_counts_as_fire():
    b = battle()
    orders = {'b': {'target': 'x', 'mode': 'melee'}, 'x': {'target': 'b', 'mode': 'ranged'}}
    plain = rates(b.engagements(orders))
    modified = rates(b.engagements(orders, {'x': {'fire': 0.2}}))
    assert modified[('x', 'closing')] == pytest.approx(plain[('x', 'closing')] * 1.2)


def test_morale_scales_what_the_unit_spends_from_its_morale():
    plain, steadier, shakier = battle(), battle(), battle()
    plain.resolve_round(60, FIRE)
    steadier.resolve_round(60, FIRE, modifiers={'x': {'morale': 0.5}})
    shakier.resolve_round(60, FIRE, modifiers={'x': {'morale': -0.5}})
    # the budget is spent slower or faster (morale feeds back into fire, so casualties differ a little too)
    assert shakier.units['x'].morale.resolve < plain.units['x'].morale.resolve < steadier.units['x'].morale.resolve


def test_morale_plus_100_percent_spends_nothing():
    b = battle()
    b.resolve_round(600, FIRE, modifiers={'x': {'morale': 1}})
    assert not b.units['x'].morale.broken and b.units['x'].morale.resolve == 1.0


def test_modifiers_last_one_round_and_are_recorded_in_it():
    b = battle()
    first = b.resolve_round(30, FIRE, modifiers={'a': {'fire': -0.15, 'note': 'uphill'}})
    assert first.modifiers == {'a': {'fire': -0.15, 'melee': 0.0, 'morale': 0.0, 'note': 'uphill'}}
    assert b.units['a'].morale.spend_factor == 1.0
    second = b.resolve_round(30, FIRE)
    assert second.modifiers == {}
    assert b.engagements(FIRE) == Battle.from_dict(b.to_dict()).engagements(FIRE)


def test_no_modifiers_or_zero_modifiers_change_nothing():
    plain, zero = battle(), battle()
    plain.resolve_round(60, FIRE)
    zero.resolve_round(60, FIRE, modifiers={'a': {'fire': 0, 'melee': 0, 'morale': 0}})
    assert zero.to_dict()['units'] == plain.to_dict()['units']


def test_modifiers_round_trip_and_are_absent_in_older_files():
    b = battle()
    b.resolve_round(30, FIRE, modifiers={'x': {'morale': -0.2, 'note': 'flanked'}})
    data = b.to_dict()
    assert data['history'][0]['modifiers'] == {'x': {'fire': 0.0, 'melee': 0.0, 'morale': -0.2, 'note': 'flanked'}}
    assert Battle.from_dict(data).history == b.history
    del data['history'][0]['modifiers']
    assert Battle.from_dict(data).history[0].modifiers == {}


@pytest.mark.parametrize('modifiers, message', [
    ({'nobody': {'fire': 0.1}}, 'Unknown unit nobody'),
    ({'a': {'range': 0.1}}, 'Unknown modifier'),
    ({'a': {'fire': -1.5}}, 'between -1 and 1'),
    ({'a': {'melee': 2}}, 'between -1 and 1'),
    ({'a': {'morale': 'x'}}, 'number'),
    ({'a': {'fire': True}}, 'number'),
    ({'a': {'note': 3}}, 'note'),
    ({'a': 0.1}, 'mapping'),
    (['a'], 'mapping of unit id'),
])
def test_bad_modifiers_are_refused_before_anything_happens(modifiers, message):
    b = battle()
    with pytest.raises(ValueError, match=message):
        b.resolve_round(30, FIRE, modifiers=modifiers)
    assert b.round == 0
    with pytest.raises(ValueError, match=message):
        b.engagements(FIRE, modifiers)


def test_api_step_preview_and_scenarios_take_modifiers():
    setup = {'seed': 7, 'sides': ['Union', 'Confederate'], 'units': [
        {'id': 'us', 'side': 0, 'size': 1000, 'stats': '6/6/1/0'}, {'id': 'cs', 'side': 1, 'size': 1000, 'stats': '4/4/0/0'}]}
    orders = {'us': {'target': 'cs', 'mode': 'ranged'}, 'cs': {'target': 'us', 'mode': 'ranged'}}
    mods = {'us': {'fire': -0.5, 'note': 'in the woods'}}
    state = api.new_battle(setup)
    plain = {a['attacker']: a['rate'] for a in api.preview(state, orders)}
    assert {a['attacker']: a['rate'] for a in api.preview(state, orders, mods)}['us'] == pytest.approx(plain['us'] / 2)
    after, report = api.step(state, 60, orders, modifiers=mods)
    assert report['modifiers']['us']['note'] == 'in the woods'
    # a saved battle with modifiers replays exactly from its scenario
    scenario = api.scenario_from_state(after)
    assert scenario['rounds'][0]['modifiers'] == {'us': {'fire': -0.5, 'melee': 0.0, 'morale': 0.0, 'note': 'in the woods'}}
    replayed, _, _ = api.run_scenario(scenario)
    assert replayed == after
    plain_after, _ = api.step(state, 60, orders)
    assert 'modifiers' not in api.scenario_from_state(plain_after)['rounds'][0]


def test_scenario_modifiers_must_be_a_mapping():
    from imperial_generals.battles.setup import SetupError
    setup = {'seed': 7, 'units': [{'id': 'us', 'side': 0, 'size': 100, 'stats': '5/5/0/0'},
                                  {'id': 'cs', 'side': 1, 'size': 100, 'stats': '5/5/0/0'}],
             'rounds': [{'duration': 30, 'modifiers': ['us']}]}
    with pytest.raises(SetupError, match='"modifiers" must be a mapping'):
        api.run_scenario(setup)
