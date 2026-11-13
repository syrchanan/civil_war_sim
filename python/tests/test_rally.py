"""
Rally: a player can order a broken unit to rally. A roll at the start of the round decides (odds from experience,
morale and the share of men left). A rallied unit fights again from the next round with a small morale budget,
less effectively and more exposed; a unit has a limited number of tries per battle and rallies only once.
"""

import pytest

from imperial_generals import api
from imperial_generals.battles.battle import Battle, Order, Rally
from imperial_generals.params import BattleParams, RallyParams
from imperial_generals.units import Regiment
from imperial_generals.utils import Rng

CERTAIN = {'rally': {'chance_min': 1.0, 'chance_max': 1.0, 'men_exponent': 0.0}}
NEVER = {'rally': {'chance_min': 0.0, 'chance_max': 0.0}}


def battle(overrides=None, seed=5):
    params = BattleParams().with_overrides(overrides or {})
    return Battle({'a': (0, Regiment(800, '5/5/0/0')), 'b': (0, Regiment(800, '5/5/0/0')),
                   'x': (1, Regiment(1000, '5/5/0/0'))}, rng=Rng(seed), params=params)


def broken(overrides=None, seed=5):
    b = battle(overrides, seed)
    b.units['a'].morale.force_break()
    b._sync(['a'])
    b.units['a'].regiment.update_size(600)
    return b


FIRE = {'a': {'target': 'x', 'mode': 'ranged'}, 'x': {'target': 'a', 'mode': 'ranged'}}


# --- the order -------------------------------------------------------------------------------------------------

def test_a_rally_order_has_no_target_ammo_or_on_break():
    assert Order(mode='rally').target is None and Order(mode='rally').on_break is None
    with pytest.raises(ValueError, match='A rally order has no target'):
        Order(target='x', mode='rally')
    with pytest.raises(ValueError, match='ammo'):
        Order(mode='rally', ammo='canister')
    with pytest.raises(ValueError, match='A rally order has no on_break'):
        Order(mode='rally', on_break='keep')


def test_only_a_broken_unit_can_rally():
    b = battle()
    with pytest.raises(ValueError, match="'a' isn't broken"):
        b.resolve_round(30, {'a': {'mode': 'rally'}})
    b.units['a'].regiment.update_size(0)
    b.units['a'].morale.force_break()
    with pytest.raises(ValueError, match="'a' is wiped out"):
        b.resolve_round(30, {'a': {'mode': 'rally'}})
    assert b.round == 0


def test_a_broken_unit_still_cannot_fire():
    b = broken()
    with pytest.raises(ValueError, match="'a' is broken or wiped out and can't act"):
        b.resolve_round(30, FIRE)


# --- the odds --------------------------------------------------------------------------------------------------

def test_odds_grow_with_experience_and_morale_and_shrink_with_losses():
    p = RallyParams(chance_min=0.15, chance_max=0.75, experience_weight=0.5, men_exponent=1.0)
    assert p.chance(1, 1, 1.0) == pytest.approx(0.15)
    assert p.chance(10, 10, 1.0) == pytest.approx(0.75)
    assert p.chance(5, 5, 0.7) == pytest.approx((0.15 + 0.6 * 4 / 9) * 0.7)
    assert p.chance(8, 2, 1.0) == pytest.approx(0.15 + 0.6 * (0.5 * 7 / 9 + 0.5 * 1 / 9))
    assert p.chance(5, 5, 0.5) < p.chance(5, 5, 0.9) < p.chance(9, 9, 0.9)
    assert RallyParams(men_exponent=2.0).chance(5, 5, 0.5) == pytest.approx(RallyParams().chance(5, 5, 1.0) * 0.25)


@pytest.mark.parametrize('change, message', [
    ({'chance_min': -0.1}, 'chance_min'), ({'chance_max': 1.5}, 'chance_max'),
    ({'chance_min': 0.8, 'chance_max': 0.5}, 'chance_min'), ({'experience_weight': 2}, 'experience_weight'),
    ({'men_exponent': -1}, 'men_exponent'), ({'resolve': 0}, 'resolve'), ({'resolve': 1.2}, 'resolve'),
    ({'effectiveness': -0.1}, 'effectiveness'), ({'exposure': -1}, 'exposure'), ({'attempts': 0}, 'attempts'),
    ({'attempts': 1.5}, 'attempts'),
])
def test_bad_rally_params_are_refused(change, message):
    with pytest.raises(ValueError, match=message):
        RallyParams(**change)


def test_rally_params_come_from_config_and_round_trip():
    params = BattleParams()
    assert params.to_dict()['rally'] == {
        'attempts': 1, 'chance_min': 0.15, 'chance_max': 0.75, 'experience_weight': 0.5, 'men_exponent': 1.0,
        'resolve': 0.3, 'effectiveness': 0.75, 'exposure': 1.25}
    assert BattleParams.from_dict(params.to_dict()) == params


# --- the roll --------------------------------------------------------------------------------------------------

def test_a_rally_that_works_puts_the_unit_back_in_the_fight_with_a_small_budget():
    b = broken(CERTAIN)
    report = b.resolve_round(30, {'a': {'mode': 'rally'}})
    a = b.units['a']
    assert report.rallies == (Rally('a', True, 1.0),)
    assert a.active and a.rallied and a.rally_attempts == 1
    assert a.morale.resolve == pytest.approx(0.3)            # idle all round: nothing spent
    assert report.units['a'].broken is False
    assert report.orders['a'] == {'target': None, 'mode': 'rally', 'ammo': None, 'on_break': None}
    b.resolve_round(30, FIRE)                                 # and it can fight next round


def test_a_rally_that_fails_leaves_the_unit_broken_and_uses_its_try():
    b = broken(NEVER)
    report = b.resolve_round(30, {'a': {'mode': 'rally'}})
    assert report.rallies == (Rally('a', False, 0.0),)
    assert b.units['a'].morale.broken and b.units['a'].rally_attempts == 1 and not b.units['a'].rallied
    with pytest.raises(ValueError, match="'a' has no rally attempts left"):
        b.resolve_round(30, {'a': {'mode': 'rally'}})


def test_more_tries_when_the_params_allow_but_only_one_rally():
    b = broken({'rally': {'chance_min': 0.0, 'chance_max': 0.0, 'attempts': 3}})
    b.resolve_round(30, {'a': {'mode': 'rally'}})
    b.params = BattleParams().with_overrides({'rally': {'attempts': 3, 'chance_min': 1.0, 'chance_max': 1.0}})
    assert b.resolve_round(30, {'a': {'mode': 'rally'}}).rallies[0].rallied
    b.units['a'].morale.force_break()
    with pytest.raises(ValueError, match="'a' has already rallied once"):
        b.resolve_round(30, {'a': {'mode': 'rally'}})


def test_the_roll_is_one_draw_per_rally_in_unit_order_at_the_start_of_the_round():
    b = broken(seed=11)
    b.units['b'].morale.force_break()
    b._sync(['b'])
    chance = b.params.rally.chance(5, 5, 600 / 800)
    rng = Rng.from_state(b.rng.state)
    draws = [rng.random(), rng.random()]
    report = b.resolve_round(30, {'b': {'mode': 'rally'}, 'a': {'mode': 'rally'}})
    assert [r.unit for r in report.rallies] == ['a', 'b']
    assert [r.rallied for r in report.rallies] == [draws[0] < chance, draws[1] < b.params.rally.chance(5, 5, 1.0)]
    assert report.rallies[0].chance == chance


def test_odds_use_the_starting_stats_not_the_live_morale():
    b = broken(seed=1)
    assert b.units['a'].regiment.stats[1] == 1                  # live morale stat collapsed on breaking
    report = b.resolve_round(30, {'a': {'mode': 'rally'}})
    assert report.rallies[0].chance == pytest.approx(b.params.rally.chance(5, 5, 0.75))


# --- after rallying --------------------------------------------------------------------------------------------

def rates(arrows):
    return {(e.attacker, e.mode): e.rate for e in arrows}


def test_a_rallied_unit_hits_less_hard_and_is_hit_harder():
    plain = battle()
    rallied = broken(CERTAIN)
    rallied.resolve_round(30, {'a': {'mode': 'rally'}})
    rallied.units['a'].regiment.update_size(800)               # same men as the plain battle, to compare
    rallied.units['a'].morale.resolve = 1.0
    rallied._sync(['a'])
    before, after = rates(plain.engagements(FIRE)), rates(rallied.engagements(FIRE))
    assert after[('a', 'ranged')] == pytest.approx(before[('a', 'ranged')] * 0.75)
    assert after[('x', 'ranged')] == pytest.approx(before[('x', 'ranged')] * 1.25)


def test_a_rallied_unit_can_break_again_and_is_routed_again():
    b = broken(CERTAIN)
    b.resolve_round(30, {'a': {'mode': 'rally'}})
    size = b.units['a'].size
    report = b.resolve_round(600, FIRE)
    assert report.units['a'].broken and report.units['a'].captured > 0
    assert b.units['a'].size < size


def test_rally_state_round_trips_and_is_absent_in_older_files():
    b = broken(CERTAIN)
    b.resolve_round(30, {'a': {'mode': 'rally'}})
    data = b.to_dict()
    assert data['units'][0]['rally'] == {'attempts': 1, 'rallied': True}
    assert data['history'][0]['rallies'] == [{'unit': 'a', 'rallied': True, 'chance': 1.0}]
    loaded = Battle.from_dict(data)
    assert loaded.history == b.history and loaded.units['a'].rallied
    assert loaded.engagements(FIRE) == b.engagements(FIRE)
    for u in data['units']:
        del u['rally']
    del data['history'][0]['rallies']
    old = Battle.from_dict(data)
    assert old.units['a'].rally_attempts == 0 and not old.units['a'].rallied and old.history[0].rallies == ()


# --- scenarios -------------------------------------------------------------------------------------------------

SETUP = {'seed': 3, 'params': CERTAIN, 'units': [
    {'id': 'us', 'side': 0, 'size': 400, 'stats': '2/2/0/0'}, {'id': 'cs', 'side': 1, 'size': 1500, 'stats': '8/8/1/0'}]}


def test_scripted_rallies_are_skipped_when_the_unit_is_not_broken_and_replay_exactly():
    fire = {'us': {'target': 'cs', 'mode': 'ranged'}, 'cs': {'target': 'us', 'mode': 'ranged'}}
    scenario = {**SETUP, 'rounds': [{'duration': 30, 'orders': {'us': {'mode': 'rally'}}},
                                    {'duration': 60, 'orders': fire},
                                    {'duration': 30, 'orders': {'us': {'mode': 'rally'}}}]}
    state, reports, _ = api.run_scenario(scenario)
    assert reports[0]['skipped_orders'] == {'us': "us isn't broken"}
    assert reports[1]['units']['us']['broken']
    assert reports[2]['rallies'] == [{'unit': 'us', 'rallied': True, 'chance': 1.0}]
    replayed, _, _ = api.run_scenario(api.scenario_from_state(state))
    assert replayed == state
