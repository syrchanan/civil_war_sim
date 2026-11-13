"""
Facing and flanks (positions pass P2): a unit fires only at targets within its front arc; attacks from a unit's
flank or rear hit harder and shake it more; a charge into a flank or rear presses harder. Units without a facing
(or a position) aren't affected.
"""

import math

import pytest

from imperial_generals import api
from imperial_generals.battles.battle import Battle
from imperial_generals.params import BattleParams, FlankParams
from imperial_generals.units import CavalryRegiment, Regiment
from imperial_generals.utils import Position, Rng
from imperial_generals.utils.trig import cos_deg, sin_deg


def at(x, y, facing=None):
    return Position(x, y, 0, 0, 'open', facing)


# --- trig in degrees, identical in both languages ------------------------------------------------------------

@pytest.mark.parametrize('d', [0, 1, 30, 44.5, 45, 45.5, 60, 89.9, 90, 120, 135, 180, 225, 270, 315, 359.99, 360,
                               -30, 725, 12.345])
def test_cos_and_sin_in_degrees_match_the_math_library_closely(d):
    # the library rounds degrees to radians first, so near a full turn it is the one a few 1e-16 off
    assert cos_deg(d) == pytest.approx(math.cos(math.radians(d)), abs=1e-13)
    assert sin_deg(d) == pytest.approx(math.sin(math.radians(d)), abs=1e-13)


def test_a_tiny_negative_angle_that_rounds_to_a_full_turn_is_zero():
    assert -1e-20 % 360.0 == 360.0
    assert (cos_deg(-1e-20), sin_deg(-1e-20)) == (1.0, 0.0)


def test_exact_at_the_quarter_turns():
    assert [cos_deg(d) for d in (0, 90, 180, 270)] == [1.0, 0.0, -1.0, 0.0]
    assert [sin_deg(d) for d in (0, 90, 180, 270)] == [0.0, 1.0, 0.0, -1.0]


# --- zones ---------------------------------------------------------------------------------------------------

def battle(a_place=None, x_place=None, a=None, x=None, params=None, seed=3):
    b = Battle({'a': (0, a or Regiment(1000, '5/5/0/0')), 'x': (1, x or Regiment(1000, '5/5/0/0'))},
               rng=Rng(seed), params=params)
    if a_place is not None:
        b.units['a'].regiment.deploy(a_place)
    if x_place is not None:
        b.units['x'].regiment.deploy(x_place)
    return b


@pytest.mark.parametrize('attacker, zone', [
    ((0, -100), 'front'),        # straight ahead (the target faces north, towards y = 0)
    ((80, -100), 'front'),       # 38.7 degrees off
    ((100, -50), 'flank'),       # 63.4 degrees off
    ((100, 0), 'flank'),         # 90
    ((100, 90), 'flank'),        # 132
    ((50, 100), 'rear'),         # 153
    ((0, 100), 'rear'),          # straight behind
    ((-100, 0), 'flank'),
])
def test_where_an_attacker_stands_relative_to_the_targets_facing(attacker, zone):
    b = battle(at(*attacker), at(0, 0, facing=0))
    assert b.zone('x', 'a') == zone


def test_zones_turn_with_the_facing_and_need_both_placed_and_a_facing():
    assert battle(at(100, 0), at(0, 0, facing=90)).zone('x', 'a') == 'front'     # facing east
    assert battle(at(100, 0), at(0, 0, facing=270)).zone('x', 'a') == 'rear'
    assert battle(at(100, 0), at(0, 0)).zone('x', 'a') is None                   # no facing
    assert battle(None, at(0, 0, facing=0)).zone('x', 'a') is None
    assert battle(at(0, 0), at(0, 0, facing=0)).zone('x', 'a') == 'front'       # same spot


def test_arcs_are_params():
    wide = BattleParams().with_overrides({'flanks': {'front_arc': 180}})
    assert battle(at(100, -50), at(0, 0, facing=0), params=wide).zone('x', 'a') == 'front'
    narrow_rear = BattleParams().with_overrides({'flanks': {'rear_arc': 30}})
    assert battle(at(50, 100), at(0, 0, facing=0), params=narrow_rear).zone('x', 'a') == 'flank'


@pytest.mark.parametrize('change, message', [
    ({'front_arc': 0}, 'front_arc'), ({'front_arc': 400}, 'front_arc'), ({'rear_arc': -1}, 'rear_arc'),
    ({'front_arc': 270, 'rear_arc': 120}, 'leave room'),
    ({'casualties': {'flank': -1}}, 'casualties'), ({'shock': {'rear': -0.5}}, 'shock'),
    ({'charge_bonus': {'side': 1}}, 'flank and rear'),
])
def test_bad_flank_params_are_refused(change, message):
    with pytest.raises(ValueError, match=message):
        BattleParams().with_overrides({'flanks': change})


# --- fire within the front arc -------------------------------------------------------------------------------

FIRE = {'a': {'target': 'x', 'mode': 'ranged'}, 'x': {'target': 'a', 'mode': 'ranged'}}


def rates(b, orders=FIRE):
    return {(e.attacker, e.mode): e.rate for e in b.engagements(orders)}


def test_a_unit_fires_only_at_targets_within_its_front_arc():
    # a faces north; x stands to its east, facing west at it
    b = battle(at(0, 0, facing=0), at(60, 0, facing=270))
    assert b.in_arc('a', 'x') is False and b.in_arc('x', 'a') is True
    got = rates(b)
    assert ('a', 'ranged') not in got and got[('x', 'ranged')] > 0
    assert battle(at(0, 0), at(60, 0, facing=270)).in_arc('a', 'x') is True        # no facing: any way
    assert battle().in_arc('a', 'x') is True


def test_flank_and_rear_fire_hits_harder():
    p = FlankParams()
    front = rates(battle(at(0, -60, facing=180), at(0, 0, facing=0)))[('a', 'ranged')]
    flank = rates(battle(at(60, 0, facing=270), at(0, 0, facing=0)))[('a', 'ranged')]
    rear = rates(battle(at(0, 60, facing=0), at(0, 0, facing=0)))[('a', 'ranged')]
    assert flank == pytest.approx(front * p.casualties['flank'])
    assert rear == pytest.approx(front * p.casualties['rear'])
    assert front == rates(battle())[('a', 'ranged')]


def test_flank_losses_shake_a_unit_more():
    def resolve_after(attacker_place):
        b = battle(attacker_place, at(0, 0, facing=0))
        b.resolve_round(30, {'a': {'target': 'x', 'mode': 'ranged'}})
        x = b.units['x']
        return x.losses, x.morale.resolve

    front_losses, front_resolve = resolve_after(at(0, -60, facing=180))
    rear_losses, rear_resolve = resolve_after(at(0, 60, facing=0))
    # more losses, and each costs more: far less resolve left per man lost
    assert rear_losses > front_losses
    assert (1 - rear_resolve) / rear_losses > (1 - front_resolve) / front_losses


def test_shock_factor_scales_the_cost_of_a_loss():
    from imperial_generals.battles.morale import MoraleState
    plain, shaken = MoraleState(500, 5, 5), MoraleState(500, 5, 5)
    plain.take_loss(firing_back=True)
    shaken.take_loss(firing_back=True, exposure=2.0)
    assert 1 - shaken.resolve == pytest.approx(2 * (1 - plain.resolve))


def test_melee_from_the_flank_hits_harder_too():
    melee = {'a': {'target': 'x', 'mode': 'melee'}, 'x': {'target': 'a', 'mode': 'melee'}}
    front, flank = battle(at(0, -20, facing=180), at(0, 0, facing=0)), battle(at(20, 0, facing=270), at(0, 0, facing=0))
    for b in (front, flank):
        b.contacts = {frozenset(('a', 'x'))}
    assert rates(flank, melee)[('a', 'melee')] == pytest.approx(
        rates(front, melee)[('a', 'melee')] * FlankParams().casualties['flank'])


def test_closing_fire_needs_the_charger_in_the_front_arc():
    def cav():      # a fresh regiment per battle: placing one moves it
        return CavalryRegiment(400, '5/5/0/1', subtype='light')
    charge = {'a': {'target': 'x', 'mode': 'melee'}, 'x': {'target': 'a', 'mode': 'ranged'}}
    from_front = battle(at(0, -200, facing=180), at(0, 0, facing=0), a=cav())
    from_rear = battle(at(0, 200, facing=0), at(0, 0, facing=0), a=cav())
    assert ('x', 'closing') in rates(from_front, charge)
    assert ('x', 'closing') not in rates(from_rear, charge)


def test_a_charge_into_the_flank_or_rear_presses_harder():
    p = BattleParams()
    charge = {'a': {'target': 'x', 'mode': 'melee'}}

    def pair(place, x_place, params=None):
        # fresh regiments per battle (placing one moves it); the target is melee-only, so no closing fire and only
        # the bonus differs
        return battle(place, x_place, a=CavalryRegiment(400, '5/5/0/1', subtype='light'),
                      x=Regiment(1000, '5/5/0/1'), params=params)

    def odds(place):
        b = pair(place, at(0, 0, facing=0))
        c = b.resolve_round(10, charge).charges[0]
        return c.p_defender_breaks

    front, flank, rear = odds(at(0, -100, facing=180)), odds(at(100, 0, facing=270)), odds(at(0, 100, facing=0))
    assert front < flank < rear
    # the bonus adds to the pressure: the same as a shock bonus of that size
    bonus = BattleParams().with_overrides({'charge': {'shock_bonus': [
        *p.charge.shock_bonus, {'charger': 'cav', 'target': 'inf', 'bonus': p.flanks.charge_bonus['rear']}]}})
    b = pair(at(0, -100, facing=180), at(0, 0, facing=0), params=bonus)
    assert b.resolve_round(10, charge).charges[0].p_defender_breaks == pytest.approx(rear)


def test_units_without_facings_fight_as_before():
    plain, placed = battle(), battle(at(0, 0), at(0, 60))
    plain.resolve_round(60, FIRE)
    placed.resolve_round(60, FIRE)
    def fought(b):
        return [{k: v for k, v in u.items() if k != 'position'} for u in b.to_dict()['units']]
    assert fought(plain) == fought(placed)


def test_a_scenario_with_facings_replays_exactly():
    setup = {'seed': 4, 'units': [
        {'id': 'us', 'side': 0, 'size': 800, 'stats': '5/5/0/0', 'position': {'x': 0, 'y': 0, 'facing': 90}},
        {'id': 'cs', 'side': 1, 'size': 800, 'stats': '5/5/0/0', 'position': {'x': 100, 'y': 0, 'facing': 0}}]}
    state, _, _ = api.run_scenario({**setup, 'rounds': [{'duration': 30, 'orders': {
        'us': {'target': 'cs', 'mode': 'ranged'}, 'cs': {'target': 'us', 'mode': 'ranged'}}}]})
    losses = {u['id']: u['losses'] for u in state['units']}
    assert losses['cs'] > 0 and losses['us'] == 0           # cs faces away: it can't reply, and is hit in the flank
    replayed, _, _ = api.run_scenario(api.scenario_from_state(state))
    assert replayed == state
