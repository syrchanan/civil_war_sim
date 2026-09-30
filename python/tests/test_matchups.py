import json

import pytest

from imperial_generals.battles.battle import Battle
from imperial_generals.config import get_config
from imperial_generals.params import BattleParams, MatchupParams
from imperial_generals.units import ArtilleryBattery, CavalryRegiment, InfantryRegiment, Regiment
from imperial_generals.utils import Rng

P = BattleParams()
C = P.combat
M = P.matchups


def rates(engagements):
    return {(e.attacker, e.target): e.rate for e in engagements}


def battle(units, params=None):
    return Battle(units, rng=Rng(1), params=params)


# =============================================================================
# MatchupParams: defaults, lookups, validation
# =============================================================================

def test_defaults_from_config():
    cfg = get_config()['matchups']
    assert M.ranged == cfg['ranged']
    assert M.melee == cfg['melee']
    assert M.melee_ratings == cfg['melee_ratings']
    assert list(M.overrides) == cfg['overrides']


def test_type_table_lookup():
    assert M.multiplier(('inf', 'line'), ('cav', 'light'), 'ranged') == M.ranged['inf']['cav']
    assert M.multiplier(('cav', 'heavy'), ('art', 'battery'), 'melee') == M.melee['cav']['art']


def test_override_precedence_most_specific_wins():
    m = MatchupParams(overrides=[
        {'attacker': 'cav/dragoons', 'target': '*', 'mode': 'ranged', 'multiplier': 0.9},
        {'attacker': 'cav/dragoons', 'target': 'art', 'mode': 'ranged', 'multiplier': 0.75},
        {'attacker': 'cav/dragoons', 'target': 'art/siege battery', 'mode': 'ranged', 'multiplier': 0.5},
        {'attacker': 'inf', 'target': 'cav/heavy', 'mode': 'ranged', 'multiplier': 1.4},
    ])
    assert m.multiplier(('cav', 'dragoons'), ('art', 'siege battery'), 'ranged') == 0.5   # sub + sub
    assert m.multiplier(('cav', 'dragoons'), ('art', 'battery'), 'ranged') == 0.75        # sub + type
    assert m.multiplier(('cav', 'dragoons'), ('inf', 'line'), 'ranged') == 0.9            # sub + any
    assert m.multiplier(('inf', 'line'), ('cav', 'heavy'), 'ranged') == 1.4               # type + sub
    assert m.multiplier(('inf', 'line'), ('cav', 'light'), 'ranged') == m.ranged['inf']['cav']
    assert m.multiplier(('cav', 'dragoons'), ('inf', 'line'), 'melee') == m.melee['cav']['inf']   # other mode


def test_units_without_subtype_use_type_level():
    assert M.multiplier(('inf', None), ('cav', None), 'melee') == M.melee['inf']['cav']


def test_melee_ratings_by_subtype_with_default():
    assert M.melee_rating(('inf', 'pikes')) == M.melee_ratings['inf/pikes']
    assert M.melee_rating(('inf', None)) == M.melee_ratings['default']


@pytest.mark.parametrize("overrides", [
    {'ranged': {'inf': {'inf': 1.0}}},                                     # incomplete table
    {'melee': {'inf': {'inf': -1.0, 'cav': 1.0, 'art': 1.0},
               'cav': {'inf': 1, 'cav': 1, 'art': 1}, 'art': {'inf': 1, 'cav': 1, 'art': 1}}},   # negative
    {'melee_ratings': {'inf/line': 0.7}},                                  # no default
    {'melee_ratings': {'default': 0.7, 'inf/musketeers': 0.7}},            # unknown subtype
    {'melee_ratings': {'default': 0.7, 'inf/line': -0.1}},                 # negative rating
    {'overrides': [{'attacker': 'inf/pikes', 'target': 'cav', 'mode': 'charge', 'multiplier': 2}]},   # bad mode
    {'overrides': [{'attacker': 'dragon', 'target': 'cav', 'mode': 'melee', 'multiplier': 2}]},       # bad key
    {'overrides': [{'attacker': 'inf', 'target': '*', 'mode': 'melee', 'multiplier': 2}]},            # '*' needs subtype
    {'overrides': [{'attacker': 'inf/pikes', 'target': 'cav', 'mode': 'melee', 'multiplier': -2}]},   # negative
    {'overrides': [{'attacker': 'inf/pikes', 'target': 'cav', 'mode': 'melee'}]},                     # missing field
])
def test_invalid_matchups_raise(overrides):
    with pytest.raises(ValueError):
        MatchupParams(**overrides)


def test_battle_params_deep_merge_matchup_overrides():
    tuned = P.with_overrides({'matchups': {'melee': {'cav': {'inf': 1.3}}, 'melee_ratings': {'inf/line': 0.8}}})
    assert tuned.matchups.melee['cav']['inf'] == 1.3
    assert tuned.matchups.melee['cav']['art'] == M.melee['cav']['art']
    assert tuned.matchups.melee_ratings['inf/line'] == 0.8
    assert tuned.matchups.melee_ratings['inf/pikes'] == M.melee_ratings['inf/pikes']
    assert M.melee['cav']['inf'] == get_config()['matchups']['melee']['cav']['inf']     # original untouched
    assert get_config()['matchups']['melee']['cav']['inf'] != 1.3


def test_matchups_round_trip_through_json():
    tuned = P.with_overrides({'matchups': {'overrides': [
        {'attacker': 'inf/pikes', 'target': 'cav', 'mode': 'melee', 'multiplier': 2.5}]}})
    data = json.loads(json.dumps(tuned.to_dict()))
    assert BattleParams.from_dict(data) == tuned


def test_artillery_kill_rate_from_config():
    assert C.artillery_kill_rate_per_gun == get_config()['combat']['artillery_kill_rate_per_gun']


# =============================================================================
# The round engine uses matchups, melee ratings and per-gun artillery
# =============================================================================

def test_ranged_rate_includes_type_matchup():
    b = battle({'i': (0, InfantryRegiment(500, '4/5/0/0', subtype='line')),
                'c': (1, CavalryRegiment(500, '4/5/0/1', subtype='heavy'))})
    r = rates(b.engagements({'i': {'target': 'c', 'mode': 'ranged'}}))
    assert r[('i', 'c')] == pytest.approx(C.unit_coef((4, 5, 0, 0), 'ranged') * 500 * C.ranged_kill_rate
                                          * M.ranged['inf']['cav'])


def test_dragoons_fire_better_than_other_cavalry():
    b = battle({'d': (0, CavalryRegiment(500, '4/5/0/0', subtype='dragoons')),
                'l': (0, CavalryRegiment(500, '4/5/0/0', subtype='light')),
                'x': (1, InfantryRegiment(500, '4/5/0/0', subtype='line'))})
    r = rates(b.engagements({'d': {'target': 'x', 'mode': 'ranged'}, 'l': {'target': 'x', 'mode': 'ranged'}}))
    assert r[('d', 'x')] / r[('l', 'x')] == pytest.approx(
        M.multiplier(('cav', 'dragoons'), ('inf', 'line'), 'ranged') / M.ranged['cav']['inf'])
    assert r[('d', 'x')] > r[('l', 'x')]


def melee_coef(stats, rating):
    xp, morale = int(stats.split('/')[0]), int(stats.split('/')[1])
    return C.melee_efficiency(xp, morale, rating)


def test_melee_uses_subtype_rating_not_firearm():
    # rifled and smoothbore line infantry fight equally hand-to-hand
    b = battle({'r': (0, InfantryRegiment(500, '4/5/1/0', subtype='line')),
                's': (0, InfantryRegiment(500, '4/5/0/0', subtype='line')),
                'x': (1, InfantryRegiment(500, '4/5/0/0', subtype='line')),
                'y': (1, InfantryRegiment(500, '4/5/0/0', subtype='line'))})
    r = rates(b.engagements({'r': {'target': 'x', 'mode': 'melee'}, 's': {'target': 'y', 'mode': 'melee'}}))
    assert r[('r', 'x')] == r[('s', 'y')]
    assert r[('r', 'x')] == pytest.approx(
        C.melee_kill_rate * melee_coef('4/5/1/0', M.melee_ratings['inf/line']) * 500 * 500 * M.melee['inf']['inf'])


def test_pikes_are_strong_in_melee_and_stronger_against_cavalry():
    b = battle({'p': (0, InfantryRegiment(500, '4/5/-2/1', subtype='pikes')),
                'c': (1, CavalryRegiment(500, '4/5/0/1', subtype='heavy')),
                'i': (1, InfantryRegiment(500, '4/5/0/0', subtype='line'))})
    vs_cav = rates(b.engagements({'p': {'target': 'c', 'mode': 'melee'}}))[('p', 'c')]
    vs_inf = rates(b.engagements({'p': {'target': 'i', 'mode': 'melee'}}))[('p', 'i')]
    base = C.melee_kill_rate * melee_coef('4/5/-2/1', M.melee_ratings['inf/pikes']) * 500 * 500
    assert vs_cav == pytest.approx(base * M.multiplier(('inf', 'pikes'), ('cav', 'heavy'), 'melee'))
    assert vs_inf == pytest.approx(base * M.melee['inf']['inf'])
    assert vs_cav > vs_inf
    assert M.melee_ratings['inf/pikes'] > M.melee_ratings['inf/line']


def test_pikes_still_cannot_fire_with_the_melee_only_flag():
    b = battle({'p': (0, InfantryRegiment(500, '4/5/-2/1', subtype='pikes')),
                'x': (1, InfantryRegiment(500, '4/5/0/0', subtype='line'))})
    assert b.engagements({'p': {'target': 'x', 'mode': 'ranged'}}) == ()


def test_stats_flag_decides_firing_not_subtype():
    # players pick arms: a heavy cavalry regiment carrying carbines (flag 0) can fire
    b = battle({'c': (0, CavalryRegiment(500, '4/5/0/0', subtype='heavy')),
                'x': (1, InfantryRegiment(500, '4/5/0/0', subtype='line'))})
    assert len(b.engagements({'c': {'target': 'x', 'mode': 'ranged'}})) == 1


def test_artillery_fires_per_manned_gun():
    guns = ArtilleryBattery(120, '4/5/0/0', guns=6, subtype='battery')
    b = battle({'g': (0, guns), 'x': (1, InfantryRegiment(800, '4/5/0/0', subtype='line'))})
    r = rates(b.engagements({'g': {'target': 'x', 'mode': 'ranged'}}))
    assert r[('g', 'x')] == pytest.approx(C.unit_coef((4, 5, 0, 0), 'ranged') * 6 * C.artillery_kill_rate_per_gun
                                          * M.ranged['art']['inf'])


def test_losing_crew_silences_guns():
    guns = ArtilleryBattery(120, '4/5/0/0', guns=6, subtype='battery')
    b = battle({'g': (0, guns), 'x': (1, InfantryRegiment(800, '4/5/0/0', subtype='line'))})
    full = rates(b.engagements({'g': {'target': 'x', 'mode': 'ranged'}}))[('g', 'x')]
    guns.update_size(21)                               # crew for 3 guns
    assert guns.effective_guns == 3
    half = rates(b.engagements({'g': {'target': 'x', 'mode': 'ranged'}}))[('g', 'x')]
    assert half == pytest.approx(full / 2)


def test_artillery_crews_fight_poorly_in_melee():
    b = battle({'c': (0, CavalryRegiment(120, '4/5/0/1', subtype='light')),
                'g': (1, ArtilleryBattery(120, '4/5/0/0', guns=6, subtype='battery'))})
    r = rates(b.engagements({'c': {'target': 'g', 'mode': 'melee'}}))
    assert r[('g', 'c')] == pytest.approx(
        C.melee_kill_rate * melee_coef('4/5/0/0', M.melee_ratings['art/battery']) * 120 * 120 * M.melee['art']['cav'])
    assert r[('c', 'g')] > 5 * r[('g', 'c')]


def test_plain_regiment_counts_as_default_infantry():
    b = battle({'a': (0, Regiment(500, '4/5/0/0')), 'c': (1, CavalryRegiment(500, '4/5/0/1', subtype='light'))})
    r = rates(b.engagements({'a': {'target': 'c', 'mode': 'melee'}}))
    assert r[('a', 'c')] == pytest.approx(
        C.melee_kill_rate * melee_coef('4/5/0/0', M.melee_ratings['default']) * 500 * 500 * M.melee['inf']['cav'])


def test_matchup_overrides_change_battle_rates():
    tuned = P.with_overrides({'matchups': {'ranged': {'inf': {'cav': 3.0}}}})
    units = lambda: {'i': (0, InfantryRegiment(500, '4/5/0/0', subtype='line')),
                     'c': (1, CavalryRegiment(500, '4/5/0/1', subtype='heavy'))}
    base = rates(battle(units()).engagements({'i': {'target': 'c', 'mode': 'ranged'}}))[('i', 'c')]
    boosted = rates(battle(units(), tuned).engagements({'i': {'target': 'c', 'mode': 'ranged'}}))[('i', 'c')]
    assert boosted == pytest.approx(base * 3.0 / M.ranged['inf']['cav'])
