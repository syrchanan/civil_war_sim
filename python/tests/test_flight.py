"""
Flight (positions pass P3): a broken unit flees away from the nearest standing enemy, fast at first and slowing
(its speed halves every half_life minutes), round after round, until it is safe or reaches the field's edge. Fire on
it fades as it gets away; a pursuer stays in contact only while it is fast enough. Unplaced units don't flee.
"""

import math

import pytest

from imperial_generals import api
from imperial_generals.battles.battle import Battle, Flight
from imperial_generals.params import BattleParams, FlightParams
from imperial_generals.units import CavalryRegiment, Regiment
from imperial_generals.utils import Position, Rng


def at(x, y, facing=None):
    return Position(x, y, 0, 0, 'open', facing)


def battle(units, seed=3, params=None):
    b = Battle({uid: (side, reg) for uid, (side, reg, _) in units.items()}, rng=Rng(seed), params=params)
    for uid, (_, _, place) in units.items():
        if place is not None:
            b.units[uid].regiment.deploy(place)
    return b


def broken(b, uid, time=None):
    """Break a unit as if it had broken at ``time`` (default: now)."""
    u = b.units[uid]
    u.morale.force_break()
    u.broke_time = b.time if time is None else time
    b._sync([uid])


# --- how far ---------------------------------------------------------------------------------------------------

def test_distance_fled_is_the_integral_of_a_halving_speed():
    p = FlightParams()
    v, h = p.speed['inf'], p.half_life
    assert p.fled('inf', 0, 0) == 0
    assert p.fled('inf', 0, h) == pytest.approx(v * h / math.log(2) * 0.5)
    assert p.fled('inf', 0, 1e9) == pytest.approx(v * h / math.log(2))       # it never gets further than this
    assert p.fled('inf', 10, 20) == pytest.approx(p.fled('inf', 0, 20) - p.fled('inf', 0, 10))
    assert p.speed_at('inf', h) == pytest.approx(v / 2)
    assert p.fled('cav', 0, 5) > p.fled('inf', 0, 5) > p.fled('art', 0, 5)


@pytest.mark.parametrize('change, message', [
    ({'speed': {'inf': -1}}, 'speed'), ({'half_life': 0}, 'half_life'), ({'step_minutes': 0}, 'step_minutes'),
    ({'safe_distance': -5}, 'safe_distance'), ({'field': {'width': 0, 'height': 1200}}, 'field'),
])
def test_bad_flight_params_are_refused(change, message):
    with pytest.raises(ValueError, match=message):
        BattleParams().with_overrides({'flight': change})


def test_flight_speeds_need_every_unit_type():
    with pytest.raises(ValueError, match='speed needs exactly'):
        FlightParams(speed={'inf': 80})


# --- fleeing ---------------------------------------------------------------------------------------------------

def test_a_broken_unit_flees_directly_away_from_the_nearest_standing_enemy():
    b = battle({'a': (0, Regiment(500, '5/5/0/0'), at(1000, 300)),
                'x': (1, Regiment(500, '5/5/0/0'), at(1000, 100)),
                'far': (1, Regiment(500, '5/5/0/0'), at(1600, 300))})
    broken(b, 'a')
    report = b.resolve_round(10, {})
    pos = b.units['a'].regiment.position
    d = b.params.flight.fled('inf', 0, 10)
    assert pos.x == pytest.approx(1000) and pos.y == pytest.approx(300 + d)      # straight away from x, south
    assert report.flights == (Flight('a', pytest.approx(d), ()),)
    assert report.units['a'].broken


def test_it_keeps_fleeing_next_round_ever_slower():
    b = battle({'a': (0, Regiment(500, '5/5/0/0'), at(100, 600)), 'x': (1, Regiment(500, '5/5/0/0'), at(50, 600))},
               params=BattleParams().with_overrides({'flight': {'safe_distance': 5000}}))     # never safe here
    broken(b, 'a')
    first = b.resolve_round(15, {}).flights[0].distance
    second = b.resolve_round(15, {}).flights[0].distance
    assert second == pytest.approx(first / 2)
    assert b.units['a'].regiment.position.x == pytest.approx(100 + first + second)     # east, away from x


def test_it_stops_when_safe_or_at_the_field_edge():
    far = battle({'a': (0, Regiment(500, '5/5/0/0'), at(1000, 600)), 'x': (1, Regiment(500, '5/5/0/0'), at(1000, 0))},
                 params=BattleParams().with_overrides({'flight': {'safe_distance': 500}}))
    broken(far, 'a')
    assert far.resolve_round(30, {}).flights == ()
    assert far.units['a'].regiment.position.y == 600
    edge = battle({'a': (0, CavalryRegiment(300, '5/5/0/0', subtype='light'), at(1000, 1150)),
                   'x': (1, Regiment(500, '5/5/0/0'), at(1000, 1000))})
    broken(edge, 'a')
    edge.resolve_round(30, {})
    assert edge.units['a'].regiment.position.y == 1200                      # the field is 1200 yards deep
    assert edge.resolve_round(30, {}).flights == ()                          # nowhere left to go


def test_with_no_enemy_standing_it_stays_put_and_unplaced_units_never_flee():
    b = battle({'a': (0, Regiment(500, '5/5/0/0'), at(1000, 600)), 'x': (1, Regiment(500, '5/5/0/0'), at(1000, 400))})
    broken(b, 'a')
    broken(b, 'x')
    assert b.resolve_round(10, {}).flights == ()
    plain = battle({'a': (0, Regiment(500, '5/5/0/0'), None), 'x': (1, Regiment(500, '5/5/0/0'), None)})
    broken(plain, 'a')
    assert plain.resolve_round(10, {}).flights == ()


def test_on_the_same_spot_as_the_enemy_it_flees_towards_its_own_side():
    b = battle({'a': (0, Regiment(500, '5/5/0/0'), at(1000, 600)), 'x': (1, Regiment(500, '5/5/0/0'), at(1000, 600)),
                'b': (1, Regiment(500, '5/5/0/0'), at(1000, 600))})
    broken(b, 'b')
    b.resolve_round(5, {})
    assert b.units['b'].regiment.position.y < 600                            # side 1 falls back north


def test_a_unit_that_breaks_during_the_round_starts_fleeing_then():
    b = battle({'a': (0, Regiment(200, '1/1/0/0'), at(1000, 600, 0)), 'x': (1, Regiment(2000, '9/9/1/0'), at(1000, 540, 180))})
    report = b.resolve_round(120, {'x': {'target': 'a', 'mode': 'ranged'}})
    broke = report.units['a'].broke_at
    assert broke is not None
    assert b.units['a'].broke_time == broke
    assert report.flights[0].unit == 'a' and report.flights[0].distance > 0
    assert b.units['a'].regiment.position.y > 600


def test_fire_on_a_fleeing_unit_fades_as_it_gets_away():
    b = battle({'a': (0, Regiment(800, '5/5/0/0'), at(1000, 600)), 'x': (1, Regiment(800, '5/5/1/0'), at(1000, 500))})
    broken(b, 'a')
    report = b.resolve_round(30, {'x': {'target': 'a', 'mode': 'ranged'}}, record_events=True)
    times = [e.time for e in report.events]
    early = sum(1 for t in times if t < 10)
    late = sum(1 for t in times if t >= 20)
    assert early > late                                                      # out of rifle range by then


# --- pursuit ---------------------------------------------------------------------------------------------------

def test_a_pursuer_fast_enough_stays_in_contact_and_moves_with_its_quarry():
    b = battle({'a': (0, Regiment(500, '5/5/0/0'), at(1000, 600)),
                'x': (1, CavalryRegiment(400, '6/6/0/1', subtype='heavy'), at(1000, 580))})
    broken(b, 'a')
    report = b.resolve_round(10, {'x': {'target': 'a', 'mode': 'melee', 'on_break': 'pursue'}})
    assert report.charges[0].outcome == 'pursuit'
    assert report.flights[0].escaped_from == ()
    ya, yx = b.units['a'].regiment.position.y, b.units['x'].regiment.position.y
    assert ya - yx == pytest.approx(20)                                       # still on its heels
    assert frozenset(('a', 'x')) in b.contacts or not b.units['a'].active or b.units['a'].size == 0


def test_a_slow_pursuer_in_contact_loses_it():
    b = battle({'a': (0, CavalryRegiment(300, '5/5/0/0', subtype='light'), at(1000, 600)),
                'x': (1, Regiment(800, '6/6/0/0'), at(1000, 580))})
    broken(b, 'a')
    b.contacts = {frozenset(('a', 'x'))}          # locked in melee as it broke
    report = b.resolve_round(10, {'x': {'target': 'a', 'mode': 'melee', 'on_break': 'pursue'}})
    assert report.flights[0].escaped_from == ('x',)
    assert b.units['x'].regiment.position.y == 580                            # left behind
    assert frozenset(('a', 'x')) not in b.contacts


# --- saving and replaying --------------------------------------------------------------------------------------

def test_flight_state_round_trips_and_is_absent_in_older_files():
    b = battle({'a': (0, Regiment(500, '5/5/0/0'), at(1000, 600)), 'x': (1, Regiment(500, '5/5/0/0'), at(1000, 450))})
    broken(b, 'a', time=0.0)
    b.resolve_round(10, {})
    data = b.to_dict()
    assert data['units'][0]['broke_time'] == 0.0 and data['units'][1]['broke_time'] is None
    assert data['history'][0]['flights'] == [{'unit': 'a', 'distance': data['history'][0]['flights'][0]['distance'],
                                              'escaped_from': []}]
    loaded = Battle.from_dict(data)
    assert loaded.history == b.history
    assert loaded.resolve_round(10, {}) == b.resolve_round(10, {})
    for u in data['units']:
        del u['broke_time']
    del data['history'][0]['flights']
    old = Battle.from_dict(data)
    assert old.units['a'].broke_time is None and old.history[0].flights == ()


def test_a_rallied_unit_stops_fleeing():
    b = battle({'a': (0, Regiment(500, '5/5/0/0'), at(1000, 600)), 'x': (1, Regiment(500, '5/5/0/0'), at(1000, 450))},
               params=BattleParams().with_overrides({'rally': {'chance_min': 1, 'chance_max': 1, 'men_exponent': 0}}))
    broken(b, 'a')
    report = b.resolve_round(10, {'a': {'mode': 'rally'}})
    assert report.flights == () and b.units['a'].broke_time is None


def test_scenarios_with_flight_replay_exactly():
    setup = {'seed': 2, 'units': [
        {'id': 'us', 'side': 0, 'size': 300, 'stats': '1/1/0/0', 'position': {'x': 1000, 'y': 600, 'facing': 0}},
        {'id': 'cs', 'side': 1, 'size': 1500, 'stats': '8/8/1/0', 'position': {'x': 1000, 'y': 520, 'facing': 180}}]}
    fire = {'cs': {'target': 'us', 'mode': 'ranged'}}
    state, reports, _ = api.run_scenario({**setup, 'rounds': [{'duration': 90, 'orders': fire},
                                                             {'duration': 30, 'orders': fire}]})
    assert any(r['flights'] for r in reports)
    replayed, _, _ = api.run_scenario(api.scenario_from_state(state))
    assert replayed == state


def test_a_pursuit_charge_by_a_slower_unit_never_makes_contact():
    b = battle({'a': (0, CavalryRegiment(300, '5/5/0/0', subtype='light'), at(1000, 600)),
                'x': (1, Regiment(800, '6/6/0/0'), at(1000, 580))})
    broken(b, 'a')
    report = b.resolve_round(10, {'x': {'target': 'a', 'mode': 'melee'}})
    assert report.charges[0].outcome == 'escaped'
    assert not b.contacts
    # once it has slowed enough, the pursuit catches it
    b.units['a'].broke_time = -100.0
    assert b.resolve_round(10, {'x': {'target': 'a', 'mode': 'melee'}}).charges[0].outcome == 'pursuit'
