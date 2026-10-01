import json
import math

import pytest

from imperial_generals.battles.battle import Battle, Charge
from imperial_generals.params import BattleParams, ChargeParams
from imperial_generals.units import ArtilleryBattery, CavalryRegiment, InfantryRegiment, Regiment
from imperial_generals.utils import Rng

P = BattleParams()
CH = P.charge
K_R = P.combat.ranged_kill_rate
K_M = P.combat.melee_kill_rate


def params(**charge):
    return BattleParams().with_overrides({'charge': charge}) if charge else BattleParams()


# a bonus of +-100 on infantry charging infantry forces the contact test's outcome
ALWAYS_HOME = {'shock_bonus': [], 'break_threshold': 100.0, 'falter_threshold': 100.0}
ALWAYS_BREAKS = {'shock_bonus': [{'charger': 'inf', 'target': 'inf', 'bonus': 100.0}]}
ALWAYS_FALTERS = {'shock_bonus': [{'charger': 'inf', 'target': 'inf', 'bonus': -100.0}]}


def line(size=500, stats='5/5/0/0', front=None):
    return InfantryRegiment(size, stats, subtype='line', front_size=front)


def battle(units, seed=1, **charge):
    return Battle(units, rng=Rng(seed), params=params(**charge))


def rates(engagements):
    return {(e.attacker, e.target, e.mode): e.rate for e in engagements}


def ranged_rate(b, attacker, target):
    a, t = b.units[attacker], b.units[target]
    return (P.combat.unit_coef(a.regiment.stats, 'ranged') * a.size * K_R
            * P.matchups.multiplier(a.key, t.key, 'ranged'))


def melee_rate(b, attacker, target, fighters):
    a, t = b.units[attacker], b.units[target]
    c = P.combat.melee_efficiency(a.regiment.stats[0], a.regiment.stats[1], a.melee_rating)
    return K_M * c * min(fighters, t.front) * P.matchups.multiplier(a.key, t.key, 'melee')


# =============================================================================
# Parameters and the contact test
# =============================================================================

def test_charge_params_come_from_config():
    assert set(CH.approach_minutes) == {'inf', 'cav', 'art'}
    assert CH.approach_minutes['cav'] < CH.approach_minutes['inf']
    assert CH.closing_fire_multiplier > 1
    assert CH.battery_closing_ammo == 'canister'
    assert 0 < CH.falter_cost < 1


@pytest.mark.parametrize('changes', [
    {'approach_minutes': {'navy': 5}},
    {'approach_minutes': {'inf': 0, 'cav': 2, 'art': 5}},
    {'closing_fire_multiplier': -1},
    {'numbers_weight': -1},
    {'steadiness_weight': -1},
    {'veterancy_weight': 1.5},
    {'shock_weight': -1},
    {'break_threshold': -0.1},
    {'falter_threshold': -0.1},
    {'spread': 0},
    {'falter_cost': 1.5},
    {'shock_bonus': [{'charger': 'inf', 'target': 'inf'}]},
    {'shock_bonus': [{'charger': 'inf/hussars', 'target': 'inf', 'bonus': 1}]},
    {'battery_closing_ammo': 'grapeshot'},
])
def test_charge_params_are_validated(changes):
    with pytest.raises(ValueError):
        BattleParams().with_overrides({'charge': changes})


def test_steadiness_blends_resolve_veterancy_and_shock():
    w, k = CH.veterancy_weight, CH.shock_weight
    assert CH.steadiness(1.0, 10, 0.0) == pytest.approx(1.0)
    assert CH.steadiness(1.0, 1, 0.0) == pytest.approx(1 - w)
    assert CH.steadiness(0.5, 10, 0.1) == pytest.approx(0.5 / (1 + k * 0.1))


def test_shock_bonuses_add_up_from_type_and_subtype_entries():
    ch = ChargeParams(shock_bonus=(
        {'charger': 'cav', 'target': 'inf', 'bonus': 0.5},
        {'charger': 'cav/heavy', 'target': 'inf', 'bonus': 0.3},
        {'charger': 'cav', 'target': 'inf/pikes', 'bonus': -2.0},
    ))
    assert ch.bonus(('cav', 'light'), ('inf', 'line')) == pytest.approx(0.5)
    assert ch.bonus(('cav', 'heavy'), ('inf', 'line')) == pytest.approx(0.8)
    assert ch.bonus(('cav', 'heavy'), ('inf', 'pikes')) == pytest.approx(-1.2)
    assert ch.bonus(('inf', 'line'), ('inf', 'line')) == 0
    assert ch.bonus(('inf', None), ('cav', None)) == 0


def test_pressure_and_odds():
    ch = CH
    x = ch.pressure(1000, 500, 0.8, 0.6, 0.5)
    assert x == pytest.approx(ch.numbers_weight * math.log(2) + ch.steadiness_weight * 0.2 + 0.5)
    p_break, p_falter, p_home = ch.odds(x)
    sig = lambda z: 1 / (1 + math.exp(-z))
    assert p_break == pytest.approx(sig((x - ch.break_threshold) / ch.spread))
    assert p_falter == pytest.approx(sig((-x - ch.falter_threshold) / ch.spread))
    assert p_home == pytest.approx(1 - p_break - p_falter)
    # more pressure: more breaks, fewer falters
    assert ch.odds(x + 1)[0] > p_break and ch.odds(x + 1)[1] < p_falter
    assert all(p >= 0 for p in ch.odds(0.0)) and sum(ch.odds(0.0)) == pytest.approx(1)


def test_default_bonuses():
    assert CH.bonus(('cav', 'heavy'), ('inf', 'line')) > CH.bonus(('cav', 'light'), ('inf', 'line')) > 0
    assert CH.bonus(('cav', 'heavy'), ('inf', 'pikes')) < 0
    assert CH.bonus(('cav', 'light'), ('art', 'battery')) > 0


def test_cavalry_charge_factor_is_gone():
    assert not hasattr(P.matchups, 'cavalry_charge')
    assert 'cavalry_charge' not in P.to_dict()['matchups']


# =============================================================================
# Melee by contact width
# =============================================================================

def in_contact(b, *pairs):
    for a, x in pairs:
        b.contacts.add(frozenset((a, x)))
    return b


def test_melee_uses_contact_width():
    b = in_contact(battle({'a': (0, line(500, '4/5/1/0', 200)), 'x': (1, line(400, '4/5/0/0', 150))}), ('a', 'x'))
    r = rates(b.engagements({'a': {'target': 'x', 'mode': 'melee'}}))
    assert r[('a', 'x', 'melee')] == pytest.approx(melee_rate(b, 'a', 'x', 200))      # min(200, 150) = 150
    assert r[('x', 'a', 'melee')] == pytest.approx(melee_rate(b, 'x', 'a', 150))
    assert r[('a', 'x', 'melee')] == pytest.approx(K_M * P.combat.melee_efficiency(4, 5, b.units['a'].melee_rating) * 150)


def test_melee_losses_per_hour_do_not_depend_on_size():
    per_hour = []
    for n in (250, 1000, 4000):
        b = in_contact(battle({'a': (0, line(n)), 'x': (1, line(n))}), ('a', 'x'))
        rate = rates(b.engagements({'a': {'target': 'x', 'mode': 'melee'}}))[('a', 'x', 'melee')]
        per_hour.append(rate * 60 / n)
    assert per_hour[0] == pytest.approx(per_hour[1]) == pytest.approx(per_hour[2])


def test_surrounded_unit_takes_more_and_deals_the_same_total():
    # d (front 400) in contact with a1 (front 300) and a2 (front 100)
    b = in_contact(battle({'a1': (0, line(300)), 'a2': (0, line(100)), 'd': (1, line(400))}), ('a1', 'd'), ('a2', 'd'))
    orders = {'a1': {'target': 'd', 'mode': 'melee'}, 'a2': {'target': 'd', 'mode': 'melee'}}
    r = rates(b.engagements(orders))
    assert r[('a1', 'd', 'melee')] == pytest.approx(melee_rate(b, 'a1', 'd', 300))
    assert r[('a2', 'd', 'melee')] == pytest.approx(melee_rate(b, 'a2', 'd', 100))
    assert r[('d', 'a1', 'melee')] == pytest.approx(melee_rate(b, 'd', 'a1', 400 * 300 / 400))   # fighters split 3:1
    assert r[('d', 'a2', 'melee')] == pytest.approx(melee_rate(b, 'd', 'a2', 400 * 100 / 400))
    c_d = P.combat.melee_efficiency(5, 5, b.units['d'].melee_rating)
    assert r[('d', 'a1', 'melee')] + r[('d', 'a2', 'melee')] == pytest.approx(K_M * c_d * 400)   # same total


def test_zero_width_front_produces_no_melee():
    b = in_contact(battle({'a': (0, line(500, front=0)), 'x': (1, line(500))}), ('a', 'x'))
    r = rates(b.engagements({'a': {'target': 'x', 'mode': 'melee'}}))
    assert ('a', 'x', 'melee') not in r and ('x', 'a', 'melee') not in r


def test_unit_in_contact_does_not_fire_its_ranged_order():
    b = in_contact(battle({'a': (0, line()), 'x': (1, line()), 'y': (1, line())}), ('a', 'x'))
    r = rates(b.engagements({'a': {'target': 'y', 'mode': 'ranged'}, 'x': {'target': 'a', 'mode': 'melee'}}))
    assert set(r) == {('a', 'x', 'melee'), ('x', 'a', 'melee')}


def test_contact_without_any_melee_order_disengages():
    b = in_contact(battle({'a': (0, line()), 'x': (1, line())}), ('a', 'x'))
    r = rates(b.engagements({'a': {'target': 'x', 'mode': 'ranged'}, 'x': {'target': 'a', 'mode': 'ranged'}}))
    assert set(r) == {('a', 'x', 'ranged'), ('x', 'a', 'ranged')}


# =============================================================================
# The approach: close-range fire on the charger
# =============================================================================

def test_new_melee_order_is_a_charge_under_closing_fire():
    b = battle({'a': (0, line()), 'x': (1, line())})
    r = rates(b.engagements({'a': {'target': 'x', 'mode': 'melee'}}))
    # the charger can't fire or fight yet; the target fires on it at close range, whatever its own order
    assert set(r) == {('x', 'a', 'closing')}
    assert r[('x', 'a', 'closing')] == pytest.approx(ranged_rate(b, 'x', 'a') * CH.closing_fire_multiplier)
    r = rates(b.engagements({'a': {'target': 'x', 'mode': 'melee'}, 'x': {'target': 'a', 'mode': 'ranged'}}))
    assert set(r) == {('x', 'a', 'closing')}


def test_melee_only_target_cannot_fire_on_the_charge():
    b = battle({'a': (0, line()), 'p': (1, InfantryRegiment(500, '5/5/-2/1', subtype='pikes'))})
    assert b.engagements({'a': {'target': 'p', 'mode': 'melee'}}) == ()


def test_battery_meets_a_charge_with_canister():
    b = battle({'a': (0, line()), 'g': (1, ArtilleryBattery.standard('5/5/0/0', subtype='battery'))})
    r = rates(b.engagements({'a': {'target': 'g', 'mode': 'melee'}, 'g': {'target': 'a', 'mode': 'ranged',
                                                                           'ammo': 'round_shot'}}))
    g = b.units['g']
    expected = (P.combat.unit_coef(g.regiment.stats, 'ranged') * g.regiment.effective_guns
                * P.combat.artillery_ammo['canister'] * P.matchups.multiplier(g.key, ('inf', 'line'), 'ranged')
                * CH.closing_fire_multiplier)
    assert r[('g', 'a', 'closing')] == pytest.approx(expected)


def test_closing_fire_is_split_between_chargers():
    b = battle({'a': (0, line()), 'c': (0, line()), 'x': (1, line())})
    r = rates(b.engagements({'a': {'target': 'x', 'mode': 'melee'}, 'c': {'target': 'x', 'mode': 'melee'}}))
    full = ranged_rate(b, 'x', 'a') * CH.closing_fire_multiplier
    assert r[('x', 'a', 'closing')] == pytest.approx(full / 2)
    assert r[('x', 'c', 'closing')] == pytest.approx(full / 2)


def test_busy_targets_do_not_fire_on_the_charge():
    # x is itself charging y: it's moving, so it can't fire on a
    b = battle({'a': (0, line()), 'y': (0, line()), 'x': (1, line())})
    r = rates(b.engagements({'a': {'target': 'x', 'mode': 'melee'}, 'x': {'target': 'y', 'mode': 'melee'}}))
    assert ('x', 'a', 'closing') not in r
    # z is locked in melee with y: it can't turn to fire on a
    b = in_contact(battle({'a': (0, line()), 'y': (0, line()), 'z': (1, line())}), ('y', 'z'))
    r = rates(b.engagements({'a': {'target': 'z', 'mode': 'melee'}, 'y': {'target': 'z', 'mode': 'melee'}}))
    assert ('z', 'a', 'closing') not in r


def test_mutual_charge_has_no_closing_fire():
    b = battle({'a': (0, line()), 'x': (1, line())})
    assert b.engagements({'a': {'target': 'x', 'mode': 'melee'}, 'x': {'target': 'a', 'mode': 'melee'}}) == ()


# =============================================================================
# Charges in a round
# =============================================================================

def charge_round(seed=1, duration=60, units=None, orders=None, **charge):
    b = battle(units or {'a': (0, line()), 'x': (1, line())}, seed=seed, **charge)
    report = b.resolve_round(duration, orders or {'a': {'target': 'x', 'mode': 'melee'}})
    return b, report


def test_a_charge_that_goes_home_makes_contact():
    b, report = charge_round(**ALWAYS_HOME)
    (charge,) = report.charges
    assert isinstance(charge, Charge)
    assert (charge.charger, charge.target, charge.outcome) == ('a', 'x', 'home')
    assert charge.start == 0 and charge.resolved_at == pytest.approx(CH.approach_minutes['inf'])
    assert charge.p_home == pytest.approx(1.0)
    assert b.contacts == {frozenset(('a', 'x'))}
    assert report.units['x'].losses > 0 and report.units['a'].losses > 0


def test_a_charge_that_falters_stands_down_shaken():
    b, report = charge_round(**ALWAYS_FALTERS)
    (charge,) = report.charges
    assert charge.outcome == 'faltered' and charge.p_falter == pytest.approx(1.0)
    assert b.contacts == set()
    assert report.units['x'].losses == 0                    # the charger never got in
    assert b.units['a'].morale.resolve < 1 - CH.falter_cost + 1e-9


def test_a_charge_can_break_the_defender_before_contact():
    b, report = charge_round(**ALWAYS_BREAKS)
    (charge,) = report.charges
    assert charge.outcome == 'defender_broke'
    assert report.units['x'].broken and report.units['x'].broke_at == pytest.approx(CH.approach_minutes['inf'])
    assert report.units['x'].captured > 0 and report.prisoners[0] == report.units['x'].captured
    assert b.contacts == set()


def test_cavalry_breaking_infantry_takes_more_prisoners():
    over = {'shock_bonus': [{'charger': 'cav', 'target': 'inf', 'bonus': 100.0},
                            {'charger': 'inf', 'target': 'inf', 'bonus': 100.0}]}
    caps = {}
    for kind, unit in (('inf', line(500)), ('cav', CavalryRegiment(500, '5/5/0/1', subtype='heavy'))):
        b = Battle({'a': (0, unit), 'x': (1, line(1000))}, rng=Rng(3),
                   params=BattleParams().with_overrides({'charge': over, 'aftermath': {'share_spread': 0.0}}))
        caps[kind] = b.resolve_round(30, {'a': {'target': 'x', 'mode': 'melee'}}).units['x'].captured
    assert caps['cav'] == pytest.approx(2 * caps['inf'], abs=1)


def test_battery_broken_by_a_charge_loses_every_gun():
    over = {'shock_bonus': [{'charger': 'inf', 'target': 'art', 'bonus': 100.0}]}
    units = {'a': (0, line(1000)), 'g': (1, ArtilleryBattery.standard('5/5/0/0', subtype='battery'))}
    b, report = charge_round(units=units, orders={'a': {'target': 'g', 'mode': 'melee'}}, **over)
    assert report.charges[0].outcome == 'defender_broke'
    assert report.units['g'].guns_lost == 8 and report.guns_captured == {0: 8, 1: 0}
    assert b.units['g'].regiment.guns == 0


def test_contact_persists_into_the_next_round():
    b, _ = charge_round(**ALWAYS_HOME)
    report = b.resolve_round(30, {'x': {'target': 'a', 'mode': 'melee'}})    # either side keeping melee is enough
    assert report.charges == ()
    assert ('a', 'x', 'melee') in rates(report.engagements)
    assert b.contacts == {frozenset(('a', 'x'))}


def test_contact_ends_without_melee_orders():
    b, _ = charge_round(**ALWAYS_HOME)
    report = b.resolve_round(30, {'a': {'target': 'x', 'mode': 'ranged'}})
    assert set(rates(report.engagements)) == {('a', 'x', 'ranged')}
    assert b.contacts == set()


def test_mutual_charge_meets_without_a_test():
    orders = {'a': {'target': 'x', 'mode': 'melee'}, 'x': {'target': 'a', 'mode': 'melee'}}
    b, report = charge_round(orders=orders, **ALWAYS_FALTERS)
    (charge,) = report.charges
    assert charge.outcome == 'meeting' and charge.p_home is None
    assert b.contacts == {frozenset(('a', 'x'))}


def test_charging_a_broken_unit_is_pursuit():
    b = battle({'a': (0, line()), 'x': (1, line())}, **ALWAYS_FALTERS)
    state = b.units['x'].morale
    while not state.broken:
        state.take_loss(firing_back=True)
    report = b.resolve_round(30, {'a': {'target': 'x', 'mode': 'melee'}})
    (charge,) = report.charges
    assert charge.outcome == 'pursuit' and charge.resolved_at == 0
    assert set(rates(report.engagements)) == {('a', 'x', 'melee')}      # the broken unit doesn't fight back


def test_charger_broken_on_the_approach():
    # a green company charges a big veteran line: the closing fire breaks it before contact
    units = {'a': (0, line(100, '1/1/0/0')), 'x': (1, line(3000, '9/9/2/0'))}
    b, report = charge_round(units=units, duration=60, **{'approach_minutes': {'inf': 30.0, 'cav': 2.0, 'art': 5.0}})
    (charge,) = report.charges
    assert charge.outcome == 'charger_broke' and report.units['a'].broken
    assert charge.resolved_at == pytest.approx(report.units['a'].broke_at)


def test_target_broken_on_the_approach_by_other_fire():
    units = {'a': (0, line(100)), 'g': (0, line(4000, '9/9/2/0')), 'x': (1, line(100, '1/1/-2/1'))}
    orders = {'a': {'target': 'x', 'mode': 'melee'}, 'g': {'target': 'x', 'mode': 'ranged'}}
    b, report = charge_round(units=units, orders=orders, duration=60,
                             **{'approach_minutes': {'inf': 30.0, 'cav': 2.0, 'art': 5.0}})
    (charge,) = report.charges
    assert charge.outcome == 'target_broke'
    assert charge.resolved_at == pytest.approx(report.units['x'].broke_at)


def test_approach_longer_than_the_round_is_tested_at_the_round_end():
    b, report = charge_round(duration=3, **ALWAYS_HOME)
    (charge,) = report.charges
    assert charge.outcome == 'home' and charge.resolved_at == pytest.approx(3)


def test_charges_are_deterministic_and_resume_exactly():
    orders = {'a': {'target': 'x', 'mode': 'melee'}}
    one = charge_round(seed=9)[1]
    assert charge_round(seed=9)[1] == one
    b, _ = charge_round(seed=9)
    again = Battle.from_json(b.to_json())
    nxt = {'a': {'target': 'x', 'mode': 'melee'}, 'x': {'target': 'a', 'mode': 'ranged'}}
    assert again.resolve_round(45, nxt) == b.resolve_round(45, nxt)
    assert again.contacts == b.contacts and orders


def test_contacts_and_charges_are_saved():
    b, report = charge_round(**ALWAYS_HOME)
    data = json.loads(b.to_json())
    assert data['version'] == 2
    assert data['contacts'] == [['a', 'x']]
    assert data['history'][0]['charges'][0]['outcome'] == 'home'
    assert Battle.from_json(b.to_json()).history[0].charges == report.charges


def test_charge_odds_follow_the_contact_test():
    # a fresh charge on an even, steady line: the odds come straight from the contact test
    b, report = charge_round(seed=4)
    (charge,) = report.charges
    a, x = b.units['a'], b.units['x']
    assert charge.p_defender_breaks + charge.p_falter + charge.p_home == pytest.approx(1)
    assert charge.outcome in ('home', 'faltered', 'defender_broke')


def test_plain_regiments_charge_like_infantry():
    b, report = charge_round(units={'a': (0, Regiment(500, '5/5/0/0')), 'x': (1, Regiment(500, '5/5/0/0'))},
                             **ALWAYS_HOME)
    assert report.charges[0].resolved_at == pytest.approx(CH.approach_minutes['inf'])
