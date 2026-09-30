import json
import os

import pytest

from imperial_generals.battles.battle import Battle
from imperial_generals.params import BattleParams
from imperial_generals.units import ArtilleryBattery, CavalryRegiment, InfantryRegiment, Regiment
from imperial_generals.utils import Position, Rng

ORDERS_1 = {
    'inf': {'target': 'foe', 'mode': 'ranged'},
    'gun': {'target': 'foe', 'mode': 'ranged', 'ammo': 'shell'},
    'cav': {'target': 'green', 'mode': 'melee'},
    'foe': {'target': 'inf', 'mode': 'ranged'},
}
ORDERS_2 = {
    'inf': {'target': 'foe', 'mode': 'ranged'},
    'gun': {'target': 'foe', 'mode': 'ranged', 'ammo': 'canister'},
    'cav': {'target': 'green', 'mode': 'melee'},       # pursuit if it broke
    'foe': {'target': 'gun', 'mode': 'melee'},
}


def build(seed=7, params=None):
    pos = Position(10.0, 20.0, 3.5, 0.2, 'forest')
    units = {
        'inf': {'side': 0, 'regiment': InfantryRegiment(900, '6/6/1/0', subtype='line', position=pos, front_size=450),
                'name': '1st Minnesota', 'meta': {'player': 'p1', 'army': 'Potomac'}},
        'gun': {'side': 0, 'regiment': ArtilleryBattery.standard('5/5/0/0', subtype='horse battery'),
                'name': 'Battery B'},
        'cav': (0, CavalryRegiment(400, '6/6/0/1', subtype='heavy')),
        'foe': (1, InfantryRegiment(1100, '5/5/0/0', subtype='line')),
        'green': (1, Regiment(300, '1/2/0/0')),
    }
    return Battle(units, rng=Rng(seed), params=params, meta={'name': 'Test Ridge', 'date': '1863-07-02'})


def reload(battle):
    return Battle.from_json(json.dumps(json.loads(battle.to_json())))


# =============================================================================
# Names and meta
# =============================================================================

def test_units_have_names_and_meta():
    b = build()
    assert b.units['inf'].name == '1st Minnesota'
    assert b.units['inf'].meta == {'player': 'p1', 'army': 'Potomac'}
    assert b.units['cav'].name == 'cav'           # defaults to the id
    assert b.units['cav'].meta == {}
    assert b.meta == {'name': 'Test Ridge', 'date': '1863-07-02'}
    assert b.seed == 7


def test_dict_form_unit_needs_side_and_regiment():
    with pytest.raises(ValueError):
        Battle({'a': {'regiment': Regiment(100, '4/5/0/0')}})
    with pytest.raises(ValueError):
        Battle({'a': (0, Regiment(100, '4/5/0/0'), 'extra')})


# =============================================================================
# Format
# =============================================================================

def test_to_dict_is_json_and_versioned():
    data = json.loads(build().to_json())
    assert data['format'] == 'imperial-generals-battle'
    assert data['version'] == 1
    assert [u['id'] for u in data['units']] == ['inf', 'gun', 'cav', 'foe', 'green']   # unit order kept
    inf = data['units'][0]
    assert (inf['name'], inf['type'], inf['subtype'], inf['side']) == ('1st Minnesota', 'inf', 'line', 0)
    assert data['units'][4]['type'] is None                                            # plain Regiment
    assert data['units'][1]['guns'] == 8


def test_round_trip_before_any_round():
    b = build()
    assert reload(b).to_dict() == b.to_dict()


@pytest.mark.parametrize("change", [
    {'format': 'something-else'},
    {'version': 2},
])
def test_wrong_format_or_version_raises(change):
    data = build().to_dict()
    data.update(change)
    with pytest.raises(ValueError):
        Battle.from_dict(data)


def test_unknown_unit_type_raises():
    data = build().to_dict()
    data['units'][0]['type'] = 'zeppelin'
    with pytest.raises(ValueError):
        Battle.from_dict(data)


# =============================================================================
# Exact resume
# =============================================================================

def test_resume_mid_battle_is_exactly_like_never_saving():
    straight = build()
    straight.resolve_round(90, ORDERS_1, record_events=True)
    saved = reload(straight)

    r_straight = straight.resolve_round(90, ORDERS_2, record_events=True)
    r_saved = saved.resolve_round(90, ORDERS_2, record_events=True)

    assert r_saved == r_straight
    assert saved.to_dict() == straight.to_dict()
    assert saved.finish() == straight.finish()


def test_history_round_trips_with_orders_and_events():
    b = build()
    b.resolve_round(90, ORDERS_1, record_events=True)
    report = b.history[0]
    assert report.orders == {'inf': {'target': 'foe', 'mode': 'ranged', 'ammo': None},
                             'gun': {'target': 'foe', 'mode': 'ranged', 'ammo': 'shell'},
                             'cav': {'target': 'green', 'mode': 'melee', 'ammo': None},
                             'foe': {'target': 'inf', 'mode': 'ranged', 'ammo': None}}
    assert reload(b).history == b.history
    assert len(report.events) > 0


def test_live_state_survives_the_round_trip():
    b = build()
    b.resolve_round(120, ORDERS_1)
    r = reload(b)
    assert (r.time, r.round, r.prisoners, r.guns_captured) == (b.time, b.round, b.prisoners, b.guns_captured)
    assert r.rng.state == b.rng.state
    assert r.params == b.params
    for uid, u in b.units.items():
        v = r.units[uid]
        assert (v.side, v.name, v.meta, v.initial_size, v.index) == (u.side, u.name, u.meta, u.initial_size, u.index)
        assert (v.losses, v.inflicted, v.captured, v.guns_lost) == (u.losses, u.inflicted, u.captured, u.guns_lost)
        assert (v.regiment.size, v.regiment.stats, v.regiment.front_size, v.regiment.raw_morale) == \
               (u.regiment.size, u.regiment.stats, u.regiment.front_size, u.regiment.raw_morale)
        assert type(v.regiment) is type(u.regiment)
        assert getattr(v.regiment, 'subtype', None) == getattr(u.regiment, 'subtype', None)
        m, n = v.morale, u.morale
        assert (m.resolve, m.shock, m.lost, m.broken, m.break_fraction, m.initial_morale) == \
               (n.resolve, n.shock, n.lost, n.broken, n.break_fraction, n.initial_morale)
    assert r.units['inf'].regiment.position == b.units['inf'].regiment.position
    assert r.units['gun'].regiment.guns == b.units['gun'].regiment.guns


def test_params_are_saved_in_full():
    tuned = BattleParams().with_overrides({'combat': {'ranged_kill_rate': 0.006},
                                           'matchups': {'melee': {'cav': {'inf': 0.8}}}})
    b = build(params=tuned)
    assert reload(b).params == tuned


def test_finished_battle_stays_finished():
    b = build()
    b.resolve_round(60, ORDERS_1)
    b.finish()
    r = reload(b)
    assert r.finished
    with pytest.raises(RuntimeError):
        r.resolve_round(60, {})


EXAMPLE = os.path.join(os.path.dirname(__file__), '../../test_cases/battle_state_v1.json')


def test_reference_file_loads_and_round_trips_unchanged():
    # the committed example is the format reference (and a starting fixture for the TS port):
    # any accidental format change fails here
    with open(EXAMPLE, encoding='utf-8') as f:
        data = json.load(f)
    b = Battle.from_dict(data)
    assert b.to_dict() == data
    assert b.units['us_1mn'].name == '1st Minnesota'
    assert b.round == 1 and len(b.history) == 1


def test_reference_file_resumes_deterministically():
    with open(EXAMPLE, encoding='utf-8') as f:
        text = f.read()
    orders = {'us_1mn': {'target': 'cs_26nc', 'mode': 'ranged'}, 'cs_26nc': {'target': 'us_1mn', 'mode': 'ranged'}}
    assert Battle.from_json(text).resolve_round(90, orders) == Battle.from_json(text).resolve_round(90, orders)


def test_seed_is_informational_when_battle_built_from_state():
    b = Battle({'a': (0, Regiment(100, '4/5/0/0'))}, rng=Rng.from_state([1, 2, 3, 4]))
    assert b.seed is None
    assert reload(b).seed is None
