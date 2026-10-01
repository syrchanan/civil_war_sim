import json

import pytest

from imperial_generals.battles import Battle
from imperial_generals.battles.setup import SetupError, battle_from_setup, load_setup_file
from imperial_generals.params import BattleParams
from imperial_generals.units import ArtilleryBattery, CavalryRegiment, InfantryRegiment, Regiment


def setup(**changes):
    data = {
        'meta': {'name': 'Test Ridge'},
        'seed': 1863,
        'sides': ['Union', 'Confederate'],
        'units': [
            {'id': 'us_1mn', 'name': '1st Minnesota', 'side': 'Union', 'type': 'inf', 'subtype': 'line',
             'size': 900, 'stats': '6/6/1/0', 'front_size': 450, 'meta': {'player': 'p1'}},
            {'name': 'Battery B', 'side': 0, 'type': 'art', 'subtype': 'battery', 'stats': '5/5/0/0'},
            {'id': 'cs_cav', 'side': 'Confederate', 'type': 'cav', 'subtype': 'heavy', 'size': 400,
             'stats': '5/5/0/1'},
            {'id': 'cs_gun', 'side': 1, 'type': 'art', 'subtype': 'horse battery', 'size': 50, 'guns': 4,
             'stats': '4/4/0/0'},
            {'id': 'cs_mob', 'side': 1, 'size': 300, 'stats': '1/2/0/0'},
        ],
    }
    data.update(changes)
    return data


def errors_of(data) -> list[str]:
    with pytest.raises(SetupError) as info:
        battle_from_setup(data)
    return info.value.errors


# =============================================================================
# Building a battle
# =============================================================================

def test_builds_units_in_order_with_names_sides_and_meta():
    b = battle_from_setup(setup())
    assert list(b.units) == ['us_1mn', 'Battery B', 'cs_cav', 'cs_gun', 'cs_mob']   # id defaults to the name
    inf = b.units['us_1mn']
    assert (inf.name, inf.side, inf.meta) == ('1st Minnesota', 0, {'player': 'p1'})
    assert b.units['cs_cav'].name == 'cs_cav'                                          # name defaults to the id
    assert [u.side for u in b.units.values()] == [0, 0, 1, 1, 1]
    assert b.meta == {'name': 'Test Ridge', 'sides': ['Union', 'Confederate']}
    assert b.seed == 1863


def test_builds_the_right_regiment_types():
    b = battle_from_setup(setup())
    inf = b.units['us_1mn'].regiment
    assert isinstance(inf, InfantryRegiment) and inf.subtype == 'line'
    assert (inf.size, inf.stats, inf.front_size) == (900, (6, 6, 1, 0), 450)
    assert isinstance(b.units['cs_cav'].regiment, CavalryRegiment)
    gun = b.units['cs_gun'].regiment
    assert isinstance(gun, ArtilleryBattery) and (gun.size, gun.guns, gun.subtype) == (50, 4, 'horse battery')
    mob = b.units['cs_mob'].regiment
    assert type(mob) is Regiment


def test_artillery_without_size_or_guns_is_a_standard_battery():
    gun = battle_from_setup(setup()).units['Battery B'].regiment
    standard = ArtilleryBattery.standard('5/5/0/0', subtype='battery')
    assert (gun.size, gun.guns) == (standard.size, standard.guns)


def test_same_setup_and_seed_give_the_same_battle():
    orders = {'us_1mn': {'target': 'cs_mob', 'mode': 'ranged'}, 'cs_mob': {'target': 'us_1mn', 'mode': 'ranged'}}
    a = battle_from_setup(setup()).resolve_round(60, orders)
    b = battle_from_setup(setup()).resolve_round(60, orders)
    assert a == b


def test_seed_argument_overrides_the_file():
    assert battle_from_setup(setup(), seed=5).seed == 5


def test_missing_seed_picks_one_and_records_it():
    data = setup()
    del data['seed']
    b = battle_from_setup(data)
    assert isinstance(b.seed, int)
    assert json.loads(b.to_json())['seed'] == b.seed


def test_params_are_overrides_on_the_defaults():
    b = battle_from_setup(setup(params={'combat': {'ranged_kill_rate': 0.01}}))
    assert b.params.combat.ranged_kill_rate == 0.01
    assert b.params.morale == BattleParams().morale


def test_optional_sections_can_be_left_out():
    data = {'units': [{'id': 'a', 'side': 0, 'size': 100, 'stats': '5/5/0/0'},
                      {'id': 'b', 'side': 1, 'size': 100, 'stats': '5/5/0/0'}]}
    b = battle_from_setup(data)
    assert b.meta == {}
    assert b.params == BattleParams()


def test_scenario_keys_are_accepted_and_ignored_by_the_builder():
    b = battle_from_setup(setup(rounds=[{'duration': 60, 'orders': {}}], finish=True))
    assert b.round == 0


def test_battle_from_setup_classmethod():
    assert list(Battle.from_setup(setup()).units) == list(battle_from_setup(setup()).units)


# =============================================================================
# Validation: every problem reported at once, with where it is
# =============================================================================

def test_setup_must_be_a_mapping_with_units():
    assert errors_of([]) == ['The setup must be a mapping with a "units" list.']
    assert errors_of({'meta': {}}) == ['"units" is missing: list the units in the battle.']
    assert errors_of({'units': []}) == ['"units" must be a non-empty list.']


def test_unknown_top_level_key_is_reported():
    errors = errors_of(setup(unit=[]))
    assert errors == ['Unknown key "unit". Allowed: expect, feedback, finish, meta, params, rounds, seed, sides, '
                      'units.']


def test_top_level_value_types_are_checked():
    errors = errors_of(setup(meta='x', seed='abc', sides=['A'], params=[]))
    assert errors[:4] == [
        '"meta" must be a mapping.',
        '"seed" must be a whole number from 0 to 4294967295.',
        '"sides" must be a list of two names.',
        '"params" must be a mapping.',
    ]


def test_problems_across_units_are_collected():
    data = setup()
    data['units'][0]['stats'] = '6/6/x/0'
    data['units'][2]['subtype'] = 'cuirassiers'
    data['units'][4]['size'] = -5
    errors = errors_of(data)
    assert len(errors) == 3
    assert errors[0].startswith('Unit 1 (us_1mn): stats')
    assert errors[1].startswith("Unit 3 (cs_cav): subtype 'cuirassiers' is not valid for cavalry")
    assert errors[2] == 'Unit 5 (cs_mob): size must be a positive whole number.'
    assert 'Unit 3' in str(SetupError(errors))


@pytest.mark.parametrize('unit, message', [
    ('x', 'Unit 1: must be a mapping.'),
    ({'side': 0, 'size': 10, 'stats': '5/5/0/0'}, 'Unit 1: needs an "id" or a "name".'),
    ({'id': 3, 'side': 0, 'size': 10, 'stats': '5/5/0/0'}, 'Unit 1: "id" must be text.'),
    ({'id': 'a', 'name': 3, 'side': 0, 'size': 10, 'stats': '5/5/0/0'}, 'Unit 1 (a): "name" must be text.'),
    ({'id': 'a', 'size': 10, 'stats': '5/5/0/0'}, 'Unit 1 (a): "side" is missing.'),
    ({'id': 'a', 'side': 2, 'size': 10, 'stats': '5/5/0/0'},
     'Unit 1 (a): side must be 0, 1 or a name from "sides" (Union, Confederate); got 2.'),
    ({'id': 'a', 'side': 'Rebels', 'size': 10, 'stats': '5/5/0/0'},
     "Unit 1 (a): side must be 0, 1 or a name from \"sides\" (Union, Confederate); got 'Rebels'."),
    ({'id': 'a', 'side': True, 'size': 10, 'stats': '5/5/0/0'},
     'Unit 1 (a): side must be 0, 1 or a name from "sides" (Union, Confederate); got True.'),
    ({'id': 'a', 'side': 0, 'stats': '5/5/0/0'}, 'Unit 1 (a): "size" is missing.'),
    ({'id': 'a', 'side': 0, 'size': 10.5, 'stats': '5/5/0/0'}, 'Unit 1 (a): size must be a positive whole number.'),
    ({'id': 'a', 'side': 0, 'size': 10}, 'Unit 1 (a): "stats" is missing (e.g. "5/5/0/0").'),
    ({'id': 'a', 'side': 0, 'size': 10, 'stats': 5}, 'Unit 1 (a): stats must be text like "5/5/0/0".'),
    ({'id': 'a', 'side': 0, 'type': 'infantry', 'subtype': 'line', 'size': 10, 'stats': '5/5/0/0'},
     "Unit 1 (a): type must be one of art, cav, inf (or left out); got 'infantry'."),
    ({'id': 'a', 'side': 0, 'type': 'inf', 'size': 10, 'stats': '5/5/0/0'},
     'Unit 1 (a): "subtype" is missing; for inf one of irregulars, light, line, marine, pikes.'),
    ({'id': 'a', 'side': 0, 'subtype': 'line', 'size': 10, 'stats': '5/5/0/0'},
     'Unit 1 (a): "subtype" needs a "type".'),
    ({'id': 'a', 'side': 0, 'size': 10, 'guns': 2, 'stats': '5/5/0/0'},
     'Unit 1 (a): only artillery has "guns".'),
    ({'id': 'a', 'side': 0, 'type': 'art', 'subtype': 'battery', 'size': 40, 'stats': '5/5/0/0'},
     'Unit 1 (a): artillery needs both "size" (crew) and "guns", or neither for a standard battery.'),
    ({'id': 'a', 'side': 0, 'type': 'art', 'subtype': 'battery', 'size': 40, 'guns': -1, 'stats': '5/5/0/0'},
     'Unit 1 (a): guns must be a whole number, 0 or more.'),
    ({'id': 'a', 'side': 0, 'size': 10, 'front_size': 'wide', 'stats': '5/5/0/0'},
     'Unit 1 (a): front_size must be a positive whole number.'),
    ({'id': 'a', 'side': 0, 'size': 10, 'stats': '5/5/0/0', 'meta': 'p1'}, 'Unit 1 (a): "meta" must be a mapping.'),
    ({'id': 'a', 'side': 0, 'size': 10, 'stats': '5/5/0/0', 'sise': 3},
     'Unit 1 (a): unknown key "sise". Allowed: front_size, guns, id, meta, name, side, size, stats, subtype, type.'),
])
def test_unit_problems(unit, message):
    data = setup()
    data['units'] = [unit] + data['units'][1:]
    assert errors_of(data)[0] == message


def test_duplicate_ids_are_reported():
    data = setup()
    data['units'][2]['id'] = 'us_1mn'
    assert errors_of(data) == ['Unit 3 (us_1mn): id "us_1mn" is already used by unit 1.']


def test_each_side_needs_a_unit():
    data = {'units': [{'id': 'a', 'side': 0, 'size': 100, 'stats': '5/5/0/0'}]}
    assert errors_of(data) == ['Side 1 has no units.']


def test_bad_params_are_reported():
    errors = errors_of(setup(params={'combat': {'ranged_kil_rate': 0.01}}))
    assert errors == ["params: Unknown combat parameter(s): ['ranged_kil_rate']."]


def test_numeric_sides_need_no_side_names():
    data = setup()
    del data['sides']
    data['units'][0]['side'] = 'Union'
    assert errors_of(data)[0] == "Unit 1 (us_1mn): side must be 0 or 1; got 'Union'."


# =============================================================================
# Files: YAML (friendlier to write by hand) or JSON
# =============================================================================

YAML_SETUP = """\
# a hand-written setup
meta:
  name: Test Ridge
seed: 7
sides: [Union, Confederate]
units:
  - id: us_1mn
    name: 1st Minnesota
    side: Union
    type: inf
    subtype: line
    size: 900
    stats: 6/6/1/0
  - id: cs_26nc
    side: Confederate
    type: inf
    subtype: line
    size: 1100
    stats: 5/5/0/0
"""


def test_load_yaml_file(tmp_path):
    path = tmp_path / 'setup.yaml'
    path.write_text(YAML_SETUP, encoding='utf-8')
    data = load_setup_file(path)
    assert data['units'][0]['stats'] == '6/6/1/0'
    assert list(battle_from_setup(data).units) == ['us_1mn', 'cs_26nc']


def test_load_json_file(tmp_path):
    path = tmp_path / 'setup.json'
    path.write_text(json.dumps(setup()), encoding='utf-8')
    assert load_setup_file(path) == setup()


def test_load_file_reports_syntax_errors_readably(tmp_path):
    bad_yaml = tmp_path / 'bad.yaml'
    bad_yaml.write_text('units:\n  - id: a\n   side: 0\n', encoding='utf-8')
    with pytest.raises(SetupError) as info:
        load_setup_file(bad_yaml)
    assert info.value.errors[0].startswith('bad.yaml is not valid YAML')
    bad_json = tmp_path / 'bad.json'
    bad_json.write_text('{"units": [}', encoding='utf-8')
    with pytest.raises(SetupError) as info:
        load_setup_file(bad_json)
    assert info.value.errors[0].startswith('bad.json is not valid JSON (line 1')


def test_yaml_dates_stay_text_so_the_state_is_json(tmp_path):
    path = tmp_path / 'setup.yaml'
    path.write_text('meta:\n  date: 1863-07-02\n  when: 2001-12-14t21:59:43.10-05:00\n' + YAML_SETUP.split('\n', 3)[3],
                    encoding='utf-8')
    data = load_setup_file(path)
    assert data['meta']['date'] == '1863-07-02'
    assert data['meta']['when'] == '2001-12-14t21:59:43.10-05:00'
    json.dumps(battle_from_setup(data).to_dict())


def test_overrides_apply_on_top_of_the_setup_params():
    data = setup(params={'combat': {'ranged_kill_rate': 0.01, 'melee_kill_rate': 0.5}})
    b = battle_from_setup(data, overrides={'combat': {'ranged_kill_rate': 0.02}, 'morale': {'gain_weight': 0.0}})
    assert b.params.combat.ranged_kill_rate == 0.02
    assert b.params.combat.melee_kill_rate == 0.5                 # the setup's own override survives
    assert b.params.morale.gain_weight == 0.0
    with pytest.raises(SetupError) as info:
        battle_from_setup(setup(), overrides={'combat': {'nope': 1}})
    assert info.value.errors == ["overrides: Unknown combat parameter(s): ['nope']."]
