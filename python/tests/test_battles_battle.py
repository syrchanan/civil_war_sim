import pytest

from imperial_generals.battles.battle import Battle, Engagement, Order, RoundReport
from imperial_generals.battles import Simulation
from imperial_generals.battles.morale import MoraleState
from imperial_generals.params import BattleParams, CombatParams
from imperial_generals.units import Regiment
from imperial_generals.utils import Rng

P = BattleParams()
K_R = P.combat.ranged_kill_rate
K_M = P.combat.melee_kill_rate


def coef(stats, mode):
    return P.combat.unit_coef(tuple(int(s) for s in stats.split('/')), mode)


def make_battle(spec, seed=1, params=None):
    """spec: {uid: (side, size, stats) or (side, size, stats, front_size)}"""
    units = {}
    for uid, (side, size, stats, *front) in spec.items():
        units[uid] = (side, Regiment(size, stats, front_size=front[0] if front else None))
    return Battle(units, rng=Rng(seed), params=params)


def break_unit(battle, uid):
    state = battle.units[uid].morale
    while not state.broken:
        state.take_loss(firing_back=True)


def rates(engagements):
    return {(e.attacker, e.target): e.rate for e in engagements}


# =============================================================================
# Construction
# =============================================================================

def test_units_have_sides_regiments_and_morale():
    b = make_battle({'a': (0, 500, '4/5/0/0'), 'x': (1, 400, '7/3/1/0')})
    assert b.units['a'].side == 0 and b.units['x'].side == 1
    assert b.units['a'].initial_size == 500
    assert isinstance(b.units['x'].morale, MoraleState)
    assert b.units['x'].morale.params is b.params.morale
    assert (b.time, b.round, b.history) == (0.0, 0, [])


def test_invalid_construction_raises():
    with pytest.raises(ValueError):
        Battle({'a': (2, Regiment(100, '4/5/0/0'))})
    with pytest.raises(TypeError):
        Battle({'a': (0, 'not a regiment')})
    with pytest.raises(TypeError):
        Battle({'a': (0, Regiment(100, '4/5/0/0'))}, rng=42)
    with pytest.raises(TypeError):
        Battle({'a': (0, Regiment(100, '4/5/0/0'))}, params={})


def test_default_rng_and_params():
    b = Battle({'a': (0, Regiment(100, '4/5/0/0'))})
    assert isinstance(b.rng, Rng)
    assert b.params == BattleParams()


# =============================================================================
# Orders
# =============================================================================

def test_order_validation():
    with pytest.raises(ValueError):
        Order(mode='charge')
    with pytest.raises(ValueError):
        Order(mode='ranged')                 # needs a target
    with pytest.raises(ValueError):
        Order(target='x', mode='idle')       # idle has no target
    assert Order() == Order(target=None, mode='idle')


@pytest.mark.parametrize("orders", [
    {'nobody': {'target': 'x', 'mode': 'ranged'}},     # unknown unit
    {'a': {'target': 'nobody', 'mode': 'ranged'}},     # unknown target
    {'a': {'target': 'b', 'mode': 'ranged'}},          # same side
    {'a': {'target': 'x', 'mode': 'volley'}},          # bad mode
    {'a': 'x'},                                        # not an order
])
def test_invalid_orders_raise(orders):
    b = make_battle({'a': (0, 100, '4/5/0/0'), 'b': (0, 100, '4/5/0/0'), 'x': (1, 100, '4/5/0/0')})
    with pytest.raises((ValueError, TypeError)):
        b.engagements(orders)


def test_orders_accept_order_objects_and_dicts_and_omitted_units_are_idle():
    b = make_battle({'a': (0, 100, '4/5/0/0'), 'x': (1, 100, '4/5/0/0'), 'y': (1, 100, '4/5/0/0')})
    e1 = b.engagements({'a': Order('x', 'ranged')})
    e2 = b.engagements({'a': {'target': 'x', 'mode': 'ranged'}, 'y': {'mode': 'idle'}})
    assert e1 == e2
    assert [(e.attacker, e.target) for e in e1] == [('a', 'x')]


def test_none_order_is_idle_and_orders_must_be_a_dict():
    b = make_battle({'a': (0, 100, '4/5/0/0'), 'x': (1, 100, '4/5/0/0')})
    assert Order.coerce(None) == Order()
    assert b.engagements({'a': None}) == ()
    with pytest.raises(TypeError):
        b.engagements([('a', 'x')])


def test_zero_width_front_produces_no_melee():
    b = make_battle({'a': (0, 100, '4/5/0/0', 0), 'x': (1, 100, '4/5/0/0')})
    assert b.engagements({'a': {'target': 'x', 'mode': 'melee'}}) == ()


def test_broken_unit_cannot_act():
    b = make_battle({'a': (0, 100, '4/5/0/0'), 'x': (1, 100, '4/5/0/0')})
    break_unit(b, 'a')
    with pytest.raises(ValueError):
        b.engagements({'a': {'target': 'x', 'mode': 'ranged'}})


def test_wiped_out_unit_cannot_be_targeted():
    b = make_battle({'a': (0, 100, '4/5/0/0'), 'x': (1, 100, '4/5/0/0')})
    b.units['x'].regiment.update_size(0)
    with pytest.raises(ValueError):
        b.engagements({'a': {'target': 'x', 'mode': 'ranged'}})


@pytest.mark.parametrize("duration", [0, -5])
def test_non_positive_duration_raises(duration):
    b = make_battle({'a': (0, 100, '4/5/0/0'), 'x': (1, 100, '4/5/0/0')})
    with pytest.raises(ValueError):
        b.resolve_round(duration, {})


# =============================================================================
# Engagements: the targeting graph and its rates (no dice)
# =============================================================================

def test_ranged_fire_is_one_way():
    b = make_battle({'a': (0, 600, '4/5/1/0'), 'x': (1, 500, '4/5/0/0'), 'y': (1, 500, '4/5/0/0')})
    r = rates(b.engagements({'a': {'target': 'x', 'mode': 'ranged'}, 'x': {'target': 'a', 'mode': 'ranged'},
                             'y': {'mode': 'idle'}}))
    assert r == {('x', 'a'): pytest.approx(K_R * coef('4/5/0/0', 'ranged') * 500),
                 ('a', 'x'): pytest.approx(K_R * coef('4/5/1/0', 'ranged') * 600)}


def test_one_target_means_no_return_fire_on_a_third_party():
    b = make_battle({'a': (0, 500, '4/5/0/0'), 'x': (1, 500, '4/5/0/0'), 'y': (1, 500, '4/5/0/0')})
    r = rates(b.engagements({'a': {'target': 'x', 'mode': 'ranged'}, 'x': {'target': 'a', 'mode': 'ranged'},
                             'y': {'target': 'a', 'mode': 'ranged'}}))
    assert set(r) == {('a', 'x'), ('x', 'a'), ('y', 'a')}     # a is hit by two, fires at one


def test_arrows_on_one_target_stack():
    b = make_battle({'a': (0, 500, '4/5/0/0'), 'b': (0, 300, '4/5/1/0'), 'x': (1, 500, '4/5/0/0')})
    r = rates(b.engagements({'a': {'target': 'x', 'mode': 'ranged'}, 'b': {'target': 'x', 'mode': 'ranged'}}))
    assert r[('a', 'x')] + r[('b', 'x')] == pytest.approx(
        K_R * (coef('4/5/0/0', 'ranged') * 500 + coef('4/5/1/0', 'ranged') * 300))


def melee_coef(stats):
    """Round-engine melee coef for a plain Regiment: default melee rating, firearm irrelevant."""
    xp, morale = (int(s) for s in stats.split('/')[:2])
    return P.combat.melee_efficiency(xp, morale, P.matchups.melee_ratings['default']) * P.matchups.melee['inf']['inf']


def test_melee_one_on_one_matches_front_times_front():
    b = make_battle({'a': (0, 500, '4/5/1/0', 200), 'x': (1, 400, '4/5/0/0', 150)})
    r = rates(b.engagements({'a': {'target': 'x', 'mode': 'melee'}}))
    assert r[('a', 'x')] == pytest.approx(K_M * melee_coef('4/5/1/0') * 200 * 150)
    assert r[('x', 'a')] == pytest.approx(K_M * melee_coef('4/5/0/0') * 150 * 200)


def test_melee_is_mutual_and_forcing():
    # x was ordered to fire at b, but a charges x: x fights a in melee and its fire on b waits
    b = make_battle({'a': (0, 500, '4/5/0/0'), 'b': (0, 500, '4/5/0/0'), 'x': (1, 500, '4/5/0/0')})
    r = rates(b.engagements({'a': {'target': 'x', 'mode': 'melee'}, 'x': {'target': 'b', 'mode': 'ranged'}}))
    assert set(r) == {('a', 'x'), ('x', 'a')}


def test_unit_in_melee_does_not_fire_its_ranged_order():
    b = make_battle({'a': (0, 500, '4/5/0/0'), 'x': (1, 500, '4/5/0/0'), 'y': (1, 500, '4/5/0/0')})
    r = rates(b.engagements({'a': {'target': 'y', 'mode': 'ranged'}, 'x': {'target': 'a', 'mode': 'melee'}}))
    assert set(r) == {('a', 'x'), ('x', 'a')}


def test_melee_exposure_is_whole_front_and_fighting_strength_is_split():
    # d (front 400) is charged by a1 (front 300) and a2 (front 100)
    b = make_battle({'a1': (0, 300, '4/5/0/0', 300), 'a2': (0, 100, '4/5/0/0', 100), 'd': (1, 400, '4/5/0/0', 400)})
    r = rates(b.engagements({'a1': {'target': 'd', 'mode': 'melee'}, 'a2': {'target': 'd', 'mode': 'melee'}}))
    c = coef('4/5/0/0', 'melee')
    assert r[('a1', 'd')] == pytest.approx(K_M * c * 300 * 1.0 * 400)            # a1 has one contact
    assert r[('a2', 'd')] == pytest.approx(K_M * c * 100 * 1.0 * 400)
    assert r[('d', 'a1')] == pytest.approx(K_M * c * 400 * (300 / 400) * 300)    # d's fighters split 3:1
    assert r[('d', 'a2')] == pytest.approx(K_M * c * 400 * (100 / 400) * 100)


def test_surrounded_unit_takes_more_and_deals_the_same_total():
    solo = make_battle({'a1': (0, 300, '4/5/0/0'), 'a2': (0, 300, '4/5/0/0'), 'd': (1, 300, '4/5/0/0')})
    one = rates(solo.engagements({'a1': {'target': 'd', 'mode': 'melee'}}))
    two = rates(solo.engagements({'a1': {'target': 'd', 'mode': 'melee'}, 'a2': {'target': 'd', 'mode': 'melee'}}))
    taken_one = one[('a1', 'd')]
    taken_two = two[('a1', 'd')] + two[('a2', 'd')]
    assert taken_two == pytest.approx(2 * taken_one)
    assert two[('d', 'a1')] + two[('d', 'a2')] == pytest.approx(one[('d', 'a1')])


def test_melee_only_unit_cannot_fire():
    b = make_battle({'p': (0, 500, '4/5/0/1'), 'x': (1, 500, '4/5/0/0')})
    assert b.engagements({'p': {'target': 'x', 'mode': 'ranged'}}) == ()


def test_melee_only_unit_fights_in_melee_with_its_rating():
    b = make_battle({'p': (0, 500, '4/5/0/1'), 'x': (1, 500, '4/5/0/0')})
    r = rates(b.engagements({'p': {'target': 'x', 'mode': 'melee'}}))
    assert r[('p', 'x')] == pytest.approx(K_M * melee_coef('4/5/0/1') * 500 * 500)


def test_broken_unit_can_be_pursued_but_does_not_fight_back():
    b = make_battle({'a': (0, 500, '4/5/0/0'), 'c': (0, 500, '4/5/0/0'), 'x': (1, 500, '4/5/0/0')})
    break_unit(b, 'x')
    r = rates(b.engagements({'a': {'target': 'x', 'mode': 'ranged'}, 'c': {'target': 'x', 'mode': 'melee'}}))
    assert set(r) == {('a', 'x'), ('c', 'x')}


def test_engagements_are_ordered_by_target_then_attacker():
    b = make_battle({'a': (0, 100, '4/5/0/0'), 'b': (0, 100, '4/5/0/0'), 'x': (1, 100, '4/5/0/0'),
                     'y': (1, 100, '4/5/0/0')})
    e = b.engagements({'y': {'target': 'a', 'mode': 'ranged'}, 'b': {'target': 'x', 'mode': 'ranged'},
                       'x': {'target': 'a', 'mode': 'ranged'}, 'a': {'target': 'x', 'mode': 'ranged'}})
    assert [(x.attacker, x.target) for x in e] == [('x', 'a'), ('y', 'a'), ('a', 'x'), ('b', 'x')]
    assert all(isinstance(x, Engagement) for x in e)


# =============================================================================
# Resolving rounds
# =============================================================================

def firefight(seed=1, duration=90):
    b = make_battle({'a': (0, 800, '5/5/0/0'), 'b': (0, 600, '5/5/1/0'), 'x': (1, 900, '5/5/0/0'),
                     'y': (1, 700, '5/5/0/0')}, seed=seed)
    orders = {'a': {'target': 'x', 'mode': 'ranged'}, 'b': {'target': 'x', 'mode': 'ranged'},
              'x': {'target': 'a', 'mode': 'ranged'}, 'y': {'target': 'a', 'mode': 'ranged'}}
    return b, b.resolve_round(duration, orders)


def test_round_advances_time_and_history():
    b, report = firefight()
    assert isinstance(report, RoundReport)
    assert (report.round, report.start, report.end) == (1, 0.0, 90.0)
    assert (b.round, b.time) == (1, 90.0)
    assert b.history == [report]
    report2 = b.resolve_round(60, {})
    assert (report2.round, report2.start, report2.end) == (2, 90.0, 150.0)


def test_losses_are_conserved_and_sizes_updated():
    b, report = firefight()
    units = report.units
    assert sum(u.losses for u in units.values()) == sum(u.inflicted for u in units.values()) > 0
    for uid, u in units.items():
        assert u.size == b.units[uid].initial_size - u.losses - u.captured == b.units[uid].regiment.size
    assert units['y'].losses == 0          # nobody targets y


def test_report_morale_matches_unit_state_and_regiment():
    b, report = firefight()
    for uid, u in report.units.items():
        assert u.morale == b.units[uid].morale.morale == b.units[uid].regiment.raw_morale
        assert u.broken == b.units[uid].morale.broken


def test_unengaged_unit_is_untouched():
    b = make_battle({'a': (0, 500, '4/5/0/0'), 'x': (1, 500, '4/5/0/0'), 'z': (1, 500, '4/5/0/0')})
    report = b.resolve_round(90, {'a': {'target': 'x', 'mode': 'ranged'}, 'x': {'target': 'a', 'mode': 'ranged'}})
    assert report.units['z'].losses == 0 and report.units['z'].inflicted == 0
    assert report.units['z'].morale == b.units['z'].morale.initial_morale


def test_same_seed_same_round_different_seed_different_round():
    assert firefight(seed=5)[1] == firefight(seed=5)[1]
    assert firefight(seed=5)[1] != firefight(seed=6)[1]


def test_who_is_hit_is_proportional_to_arrow_rates():
    # two shooters (rifled 1.5x) on one huge target over a short window: kills split ~1.5 : 1
    kills = {'r': 0, 's': 0}
    for seed in range(10):
        b = make_battle({'r': (0, 20_000, '4/5/1/0'), 's': (0, 20_000, '4/5/0/0'), 't': (1, 50_000, '4/5/0/0')}, seed)
        report = b.resolve_round(3, {'r': {'target': 't', 'mode': 'ranged'}, 's': {'target': 't', 'mode': 'ranged'}})
        kills['r'] += report.units['r'].inflicted
        kills['s'] += report.units['s'].inflicted
    assert kills['r'] / kills['s'] == pytest.approx(1.5, rel=0.05)


def test_matches_simulation_exactly_one_on_one():
    for seed in range(5):
        r1, r2 = Regiment(600, '4/5/0/0'), Regiment(500, '3/4/1/0')
        r1.set_combat_mode('ranged')
        r2.set_combat_mode('ranged')
        sim = Simulation((r1, r2), rng=Rng(seed))
        sim.run_simulation(time=600)

        b = make_battle({'a': (0, 600, '4/5/0/0'), 'x': (1, 500, '3/4/1/0')}, seed=seed)
        report = b.resolve_round(600, {'a': {'target': 'x', 'mode': 'ranged'}, 'x': {'target': 'a', 'mode': 'ranged'}})

        assert [report.units['a'].losses, report.units['x'].losses] == sim.casualties['losses'].tolist()
        assert [report.units['a'].morale, report.units['x'].morale] == [s.morale for s in sim.morale_states]
        assert [report.units['a'].broken, report.units['x'].broken] == [s.broken for s in sim.morale_states]


def test_attackers_go_idle_when_their_target_breaks():
    b = make_battle({'a': (0, 1000, '8/8/1/0'), 'c': (0, 1000, '8/8/1/0'), 'x': (1, 400, '2/2/0/0')}, seed=3)
    report = b.resolve_round(600, {'a': {'target': 'x', 'mode': 'ranged'}, 'c': {'target': 'x', 'mode': 'ranged'}},
                             record_events=True)
    x = report.units['x']
    assert x.broken and x.broke_at is not None
    assert x.broke_at < report.end
    assert all(ev.time <= x.broke_at for ev in report.events)     # no fire after the break
    assert report.events[-1].target == 'x' and report.events[-1].time == x.broke_at


def test_unit_broken_by_drain_alone_stands_its_attackers_down():
    # extreme in-combat drain: both engaged units spend their budget in seconds, before much fire lands
    drain = BattleParams().with_overrides({'morale': {'drain_per_hour': 600.0}})
    b = make_battle({'a': (0, 1000, '8/8/1/0'), 'x': (1, 400, '2/2/0/0')}, seed=1, params=drain)
    report = b.resolve_round(90, {'a': {'target': 'x', 'mode': 'ranged'}}, record_events=True)
    assert report.units['a'].broken and report.units['x'].broken
    assert report.units['a'].broke_at is not None and report.units['x'].broke_at is not None
    broke = max(report.units['a'].broke_at, report.units['x'].broke_at)
    assert all(ev.time <= broke for ev in report.events)        # nothing fires after the break is detected
    assert report.units['a'].inflicted < 10


def test_break_by_drain_at_the_round_limit_is_recorded():
    drain = BattleParams().with_overrides({'morale': {'drain_per_hour': 60.0}})
    b = make_battle({'a': (0, 10, '4/5/0/0'), 'x': (1, 10, '4/5/0/0')}, seed=2, params=drain)
    # 10-man units at range rarely hit anything in a minute; the drain breaks both at 60 min (end of round)
    report = b.resolve_round(60, {'a': {'target': 'x', 'mode': 'ranged'}, 'x': {'target': 'a', 'mode': 'ranged'}})
    assert report.units['a'].broken and report.units['x'].broken
    assert report.units['a'].broke_at is not None


def test_broken_unit_can_be_pursued_next_round():
    b = make_battle({'a': (0, 1000, '8/8/1/0'), 'x': (1, 400, '2/2/0/0')}, seed=3)
    b.resolve_round(600, {'a': {'target': 'x', 'mode': 'ranged'}})
    assert b.units['x'].morale.broken
    size_before = b.units['x'].regiment.size
    report = b.resolve_round(60, {'a': {'target': 'x', 'mode': 'ranged'}})
    assert report.units['x'].losses > 0
    assert report.units['x'].inflicted == 0
    assert report.units['x'].size == size_before - report.units['x'].losses
    assert report.units['x'].broke_at is None          # it broke in an earlier round


def test_wiped_out_target_stops_its_attackers():
    b = make_battle({'a': (0, 1000, '8/8/1/0'), 'x': (1, 1, '10/10/0/0')}, seed=4)
    report = b.resolve_round(600, {'a': {'target': 'x', 'mode': 'ranged'}}, record_events=True)
    assert report.units['x'].size == 0
    assert len(report.events) == 1


def test_events_not_recorded_by_default():
    assert firefight()[1].events == ()


def test_rates_use_battle_params():
    fast = BattleParams().with_overrides({'combat': {'ranged_kill_rate': K_R * 3}})
    b = make_battle({'a': (0, 500, '4/5/0/0'), 'x': (1, 500, '4/5/0/0')}, params=fast)
    r = rates(b.engagements({'a': {'target': 'x', 'mode': 'ranged'}}))
    assert r[('a', 'x')] == pytest.approx(3 * K_R * coef('4/5/0/0', 'ranged') * 500)
