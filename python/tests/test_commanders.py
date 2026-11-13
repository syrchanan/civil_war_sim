"""
Commander rating: each side's commander as a historical general, by how the result compares with what the
armies' strength led to expect (roadmap Phase C).
"""

import pytest

from imperial_generals import api, commanders
from imperial_generals.battles.morale import break_fraction
from imperial_generals.config import get_config
from imperial_generals.params import BattleParams

CFG = get_config()['commanders']


def unit(uid, side, size, stats, type_=None, subtype=None, **extra):
    u = {'id': uid, 'side': side, 'size': size, 'stats': stats, **extra}
    if type_:
        u['type'], u['subtype'] = type_, subtype
    return u


# --- strength --------------------------------------------------------------------------------------------------

def test_power_is_hit_rate_times_staying_power():
    p = BattleParams()
    state = api.new_battle({'seed': 1, 'units': [
        unit('line', 0, 800, '6/5/1/0', 'inf', 'line'), unit('pikes', 0, 600, '5/5/-2/1', 'inf', 'pikes'),
        unit('guns', 1, 72, '5/6/0/0', 'art', 'battery', guns=8), unit('cav', 1, 300, '4/4/0/1', 'cav', 'light')]})
    powers = {u['id']: commanders.unit_power(u, p) for u in state['units']}
    c = p.combat
    assert powers['line'] == pytest.approx(
        c.unit_coef((6, 5, 1, 0), 'ranged') * 800 * c.ranged_kill_rate * break_fraction(6, 5, p.morale))
    # melee-only: melee strength over its front
    front = next(u['front_size'] for u in state['units'] if u['id'] == 'pikes')
    assert powers['pikes'] == pytest.approx(
        c.melee_kill_rate * c.melee_efficiency(5, 5, p.matchups.melee_rating(('inf', 'pikes'))) * min(600, front)
        * break_fraction(5, 5, p.morale))
    # artillery: per manned gun at the default ammo
    assert powers['guns'] == pytest.approx(
        c.unit_coef((5, 6, 0, 0), 'ranged') * 8 * c.artillery_ammo[c.artillery_default_ammo]
        * break_fraction(5, 6, p.morale))
    assert powers['cav'] > 0


def test_power_counts_the_army_as_it_began():
    setup = {'seed': 4, 'units': [unit('a', 0, 1000, '5/5/0/0'), unit('b', 1, 1000, '5/5/0/0'),
                                  unit('g', 1, 72, '5/5/0/0', 'art', 'battery', guns=8)]}
    start = api.new_battle(setup)
    fire = {'a': {'target': 'g', 'mode': 'ranged'}, 'b': {'target': 'a', 'mode': 'ranged'}}
    state, _ = api.step(start, 600, fire)
    p = BattleParams()
    assert [commanders.side_power(state, s, p) for s in (0, 1)] == [commanders.side_power(start, s, p) for s in (0, 1)]


def test_expected_share_grows_with_strength():
    assert commanders.expected_share(1.0, 1.0, 1.5) == 0.5
    assert commanders.expected_share(2.0, 1.0, 1.0) == pytest.approx(2 / 3)
    assert commanders.expected_share(2.0, 1.0, 1.5) == pytest.approx(2 ** 1.5 / (2 ** 1.5 + 1))
    assert commanders.expected_share(0.0, 0.0, 1.5) == 0.5


# --- the result ------------------------------------------------------------------------------------------------

def sides(**changes):
    base = [{'casualties': 200, 'guns_taken': 0, 'held_field': False, 'units_out_men': 0, 'started': 1000},
            {'casualties': 200, 'guns_taken': 0, 'held_field': False, 'units_out_men': 0, 'started': 1000}]
    for key, (a, b) in changes.items():
        base[0][key], base[1][key] = a, b
    return base


def test_result_share_weighs_casualties_field_and_routs():
    w = CFG['weights']
    even = commanders.result_shares(sides(), None, CFG)
    assert even == pytest.approx([0.5, 0.5])
    # side 0 inflicted 300 of 400 casualties, held the field, routed half the enemy and lost none
    s = sides(casualties=(100, 300), units_out_men=(0, 500))
    got = commanders.result_shares(s, 0, CFG)
    assert got[0] == pytest.approx(w['casualties'] * 0.75 + w['field'] * 1 + w['routs'] * 1)
    assert sum(got) == pytest.approx(1.0)


def test_captured_guns_count_as_men_and_routs_are_shares_of_each_army():
    gun = CFG['gun_value']
    s = sides(casualties=(100, 100), guns_taken=(2, 0))
    assert commanders.result_shares(s, None, CFG)[0] == pytest.approx(
        CFG['weights']['casualties'] * (100 + 2 * gun) / (200 + 2 * gun) + (1 - CFG['weights']['casualties']) * 0.5)
    # a quarter of a small army routed against a quarter of a big one: even
    s = sides(started=(400, 4000), units_out_men=(100, 1000))
    assert commanders.result_shares(s, None, CFG) == pytest.approx([0.5, 0.5])
    s = sides(casualties=(0, 0))
    assert commanders.result_shares(s, None, CFG) == pytest.approx([0.5, 0.5])


# --- the ladder ------------------------------------------------------------------------------------------------

def test_the_ladder_runs_from_disaster_to_masterpiece_and_needs_a_floor():
    ladder = CFG['ladder']
    assert ladder[0]['from'] == -1 and len(ladder) >= 12
    assert [g['from'] for g in ladder] == sorted(g['from'] for g in ladder)
    assert commanders.general(-1.0, ladder)['name'] == ladder[0]['name']
    assert commanders.general(1.0, ladder)['name'] == ladder[-1]['name']
    mid = commanders.general(0.0, ladder)
    assert ladder[0]['from'] < mid['from'] <= 0.0


def test_a_score_gets_the_highest_general_it_reaches():
    ladder = [{'name': 'Low', 'battle': 'x', 'from': -1}, {'name': 'Mid', 'battle': 'y', 'from': 0.0},
              {'name': 'High', 'battle': 'z', 'from': 0.3}]
    assert [commanders.general(s, ladder)['name'] for s in (-0.5, 0.0, 0.29, 0.3, 0.9)] == \
        ['Low', 'Mid', 'Mid', 'High', 'High']


# --- the rating ------------------------------------------------------------------------------------------------

SETUP = {'seed': 7, 'sides': ['Union', 'Confederate'], 'units': [
    unit('us', 0, 1000, '6/6/1/0'), unit('cs', 1, 1000, '4/4/0/0')]}
FIRE = {'us': {'target': 'cs', 'mode': 'ranged'}, 'cs': {'target': 'us', 'mode': 'ranged'}}


def test_ratings_compare_the_result_with_the_odds():
    state, _, _ = api.run_scenario({**SETUP, 'rounds': [{'duration': 600, 'orders': FIRE}], 'finish': True})
    union, confed = commanders.ratings(state)
    assert union['name'] == 'Union' and confed['name'] == 'Confederate'
    assert union['expected'] > 0.5                          # the better unit
    assert union['expected'] + confed['expected'] == pytest.approx(1)
    assert union['result'] + confed['result'] == pytest.approx(1)
    assert union['score'] == pytest.approx(union['result'] - union['expected'])
    assert confed['score'] == pytest.approx(-union['score'])
    assert union['general'] == commanders.general(union['score'], CFG['ladder'])
    assert set(union) == {'name', 'power', 'expected', 'result', 'score', 'general'}


def test_the_same_result_rates_higher_against_a_bigger_army():
    small = {**SETUP, 'units': [unit('us', 0, 1000, '6/6/1/0'), unit('cs', 1, 600, '4/4/0/0')]}
    big = {**SETUP, 'units': [unit('us', 0, 1000, '6/6/1/0'), unit('cs', 1, 1600, '4/4/0/0')]}
    plays = {name: api.run_scenario({**s, 'rounds': [{'duration': 30, 'orders': FIRE}], 'finish': 'none'})[0]
             for name, s in (('small', small), ('big', big))}
    odds = {name: commanders.ratings(state)[0] for name, state in plays.items()}
    # the score is result - expected, so the same result scores higher against the bigger army
    assert odds['big']['expected'] < odds['small']['expected']


def test_ratings_need_a_finished_battle():
    with pytest.raises(ValueError, match='finish'):
        commanders.ratings(api.new_battle(SETUP))
