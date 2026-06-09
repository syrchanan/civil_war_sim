import os
import json
import pytest
from imperial_generals.units.Regiment import Regiment
from imperial_generals.utils import Position


def load_regiment_golden_cases():
    path = os.path.join(os.path.dirname(__file__), '../../test_cases/regiment_examples.json')
    with open(path) as f:
        return json.load(f)


@pytest.mark.parametrize("case", load_regiment_golden_cases())
def test_regiment_golden(case):
    if case.get('shouldError'):
        with pytest.raises(Exception):
            Regiment(**case['inputs'])
    else:
        reg = Regiment(**case['inputs'])
        expected = case['expected']
        assert reg.size == expected['size']
        assert reg.stats == tuple(expected['stats'])


def test_regiment_str():
    reg = Regiment(1000, '4/4/0/0')
    s = str(reg)
    assert '1000' in s
    assert 'xp=4' in s


def test_regiment_repr():
    reg = Regiment(1000, '4/4/0/0')
    r = repr(reg)
    assert 'Regiment(' in r
    assert '1000' in r


def test_update_stats_invalid_raises():
    reg = Regiment(1000, '4/4/0/0')
    with pytest.raises(ValueError):
        reg.update_stats('4/4/0')          # too few parts
    with pytest.raises(ValueError):
        reg.update_stats('a/b/c/d')        # non-integer parts


def test_update_raw_morale_invalid_type_raises():
    reg = Regiment(1000, '4/4/0/0')
    with pytest.raises(TypeError):
        reg.update_raw_morale(50)          # int, not float
    with pytest.raises(TypeError):
        reg.update_raw_morale('50.0')


def test_update_raw_morale_valid():
    reg = Regiment(1000, '4/4/0/0')
    reg.update_raw_morale(60.0)
    assert reg.raw_morale == 60.0


def test_raw_morale_uses_config_scale_factor():
    from imperial_generals.config import get_config
    scale = get_config()['morale']['raw_scale_factor']
    reg = Regiment(1000, '5/6/0/0')
    assert reg.raw_morale == float(6 * scale)


# ---------------------------------------------------------------------------
# Position — default (no position)
# ---------------------------------------------------------------------------

def test_regiment_position_defaults_to_none():
    reg = Regiment(500, '4/4/0/0')
    assert reg.position is None


# ---------------------------------------------------------------------------
# Position — set at construction
# ---------------------------------------------------------------------------

def test_regiment_position_at_construction():
    pos = Position(x=10.0, y=20.0, z=5.0, cover=0.3, terrain_type='open')
    reg = Regiment(500, '4/4/0/0', position=pos)
    assert reg.position == pos

def test_regiment_position_at_construction_all_fields():
    pos = Position(x=0.0, y=0.0, z=100.0, cover=1.0, terrain_type='hill')
    reg = Regiment(1000, '5/6/1/0', position=pos)
    assert reg.position.terrain_type == 'hill'
    assert reg.position.z == 100.0
    assert reg.position.cover == 1.0


# ---------------------------------------------------------------------------
# Position — deploy (initial placement and movement)
# ---------------------------------------------------------------------------

def test_regiment_deploy_sets_position():
    reg = Regiment(500, '4/4/0/0')
    pos = Position(x=5.0, y=5.0, z=0.0, cover=0.0, terrain_type='open')
    reg.deploy(pos)
    assert reg.position == pos

def test_regiment_deploy_updates_existing_position():
    pos1 = Position(x=1.0, y=1.0, z=0.0, cover=0.0, terrain_type='open')
    pos2 = Position(x=50.0, y=75.0, z=10.0, cover=0.5, terrain_type='forest')
    reg = Regiment(500, '4/4/0/0', position=pos1)
    reg.deploy(pos2)
    assert reg.position == pos2

def test_regiment_deploy_rejects_non_position():
    reg = Regiment(500, '4/4/0/0')
    with pytest.raises(TypeError):
        reg.deploy("not a position")


# ---------------------------------------------------------------------------
# Distance convenience methods
# ---------------------------------------------------------------------------

def _make_reg(x, y, z):
    reg = Regiment(500, '4/4/0/0')
    reg.deploy(Position(x=x, y=y, z=z, cover=0.0, terrain_type='open'))
    return reg

def test_regiment_flat_distance_to():
    a = _make_reg(0.0, 0.0, 0.0)
    b = _make_reg(3.0, 4.0, 99.0)
    assert a.flat_distance_to(b) == pytest.approx(5.0)

def test_regiment_true_distance_to():
    a = _make_reg(0.0, 0.0, 0.0)
    b = _make_reg(2.0, 2.0, 1.0)
    assert a.true_distance_to(b) == pytest.approx(3.0)

def test_regiment_elevation_difference_to():
    a = _make_reg(0.0, 0.0, 10.0)
    b = _make_reg(0.0, 0.0, 30.0)
    assert a.elevation_difference_to(b) == pytest.approx(20.0)

def test_regiment_distance_raises_if_not_deployed():
    a = Regiment(500, '4/4/0/0')
    b = _make_reg(1.0, 1.0, 0.0)
    with pytest.raises(ValueError, match="position"):
        a.flat_distance_to(b)
    with pytest.raises(ValueError, match="position"):
        a.true_distance_to(b)
    with pytest.raises(ValueError, match="position"):
        a.elevation_difference_to(b)

def test_regiment_distance_raises_if_other_not_deployed():
    a = _make_reg(0.0, 0.0, 0.0)
    b = Regiment(500, '4/4/0/0')
    with pytest.raises(ValueError, match="position"):
        a.flat_distance_to(b)


# ---------------------------------------------------------------------------
# Regiment.deploy_to_cell
# ---------------------------------------------------------------------------

def _make_cell_for_deploy():
    from shapely.geometry import box
    from imperial_generals.map.Cell import Cell
    poly = box(0, 0, 20, 20)
    return Cell(index=0, center=(10.0, 10.0), polygon=poly,
                elevation=15.0, terrain_type='hill', cover_value=0.2)

def test_regiment_deploy_to_cell_sets_position():
    reg = Regiment(500, '4/4/0/0')
    reg.deploy_to_cell(_make_cell_for_deploy())
    assert reg.position is not None
    assert reg.position.x == 10.0
    assert reg.position.y == 10.0
    assert reg.position.z == 15.0
    assert reg.position.terrain_type == 'hill'
    assert reg.position.cover == 0.2

def test_regiment_deploy_to_cell_replaces_existing():
    reg = Regiment(500, '4/4/0/0')
    reg.deploy(Position(x=1.0, y=1.0, z=0.0, cover=0.0, terrain_type='open'))
    reg.deploy_to_cell(_make_cell_for_deploy())
    assert reg.position.terrain_type == 'hill'


# ---------------------------------------------------------------------------
# combat_mode
# ---------------------------------------------------------------------------

def test_regiment_combat_mode_default_idle():
    reg = Regiment(500, '4/4/0/0')
    assert reg.combat_mode == 'idle'

def test_regiment_set_combat_mode_ranged():
    reg = Regiment(500, '4/4/0/0')
    reg.set_combat_mode('ranged')
    assert reg.combat_mode == 'ranged'

def test_regiment_set_combat_mode_melee():
    reg = Regiment(500, '4/4/0/0')
    reg.set_combat_mode('melee')
    assert reg.combat_mode == 'melee'

def test_regiment_set_combat_mode_idle():
    reg = Regiment(500, '4/4/0/0')
    reg.set_combat_mode('melee')
    reg.set_combat_mode('idle')
    assert reg.combat_mode == 'idle'

def test_regiment_set_combat_mode_invalid_raises():
    reg = Regiment(500, '4/4/0/0')
    with pytest.raises(ValueError, match="combat_mode"):
        reg.set_combat_mode('charging')

def test_regiment_valid_combat_modes():
    assert Regiment.VALID_COMBAT_MODES == frozenset({'idle', 'ranged', 'melee'})

def test_regiment_combat_mode_in_str():
    reg = Regiment(500, '4/4/0/0')
    reg.set_combat_mode('melee')
    assert 'melee' in str(reg)


# ---------------------------------------------------------------------------
# is_melee_only
# ---------------------------------------------------------------------------

def test_regiment_is_melee_only_false():
    reg = Regiment(500, '4/4/0/0')   # stats[3] == 0
    assert reg.is_melee_only is False

def test_regiment_is_melee_only_true():
    reg = Regiment(500, '4/4/0/1')   # stats[3] == 1
    assert reg.is_melee_only is True

def test_regiment_is_melee_only_updates_with_stats():
    reg = Regiment(500, '4/4/0/0')
    assert reg.is_melee_only is False
    reg.update_stats('4/4/0/1')
    assert reg.is_melee_only is True


# ---------------------------------------------------------------------------
# effective_law
# ---------------------------------------------------------------------------

def test_regiment_effective_law_default_idle_is_sq():
    reg = Regiment(500, '4/4/0/0')
    assert reg.effective_law == 'sq'

def test_regiment_effective_law_ranged_is_sq():
    reg = Regiment(500, '4/4/0/0')
    reg.set_combat_mode('ranged')
    assert reg.effective_law == 'sq'

def test_regiment_effective_law_melee_is_ln():
    reg = Regiment(500, '4/4/0/0')
    reg.set_combat_mode('melee')
    assert reg.effective_law == 'ln'

def test_regiment_effective_law_in_str():
    reg = Regiment(500, '4/4/0/0')
    reg.set_combat_mode('melee')
    assert 'EffectiveLaw' in str(reg)
    assert 'ln' in str(reg)


# ---------------------------------------------------------------------------
# coef — dynamic based on combat_mode and is_melee_only
# ---------------------------------------------------------------------------

def test_regiment_coef_ranged_unit_idle():
    from imperial_generals.utils.combat_efficiency import get_combat_efficiency
    reg = Regiment(500, '4/4/1/0')
    assert reg.coef == pytest.approx(reg._base_coef)

def test_regiment_coef_ranged_unit_in_ranged():
    reg = Regiment(500, '4/4/1/0')
    reg.set_combat_mode('ranged')
    assert reg.coef == pytest.approx(reg._base_coef)

def test_regiment_coef_ranged_unit_in_melee_has_penalty():
    from imperial_generals.config import get_config
    reg = Regiment(500, '4/4/1/0')
    reg.set_combat_mode('melee')
    factor = get_config()['combat']['melee_penalty_factor']
    assert reg.coef == pytest.approx(reg._base_coef * factor)

def test_regiment_coef_melee_only_unit_in_ranged_is_zero():
    reg = Regiment(500, '4/4/0/1')   # melee-only
    reg.set_combat_mode('ranged')
    assert reg.coef == 0.0

def test_regiment_coef_melee_only_unit_in_melee_no_penalty():
    reg = Regiment(500, '4/4/0/1')   # melee-only
    reg.set_combat_mode('melee')
    assert reg.coef == pytest.approx(reg._base_coef)

def test_regiment_coef_melee_only_unit_idle():
    reg = Regiment(500, '4/4/0/1')   # melee-only
    assert reg.coef == pytest.approx(reg._base_coef)

def test_regiment_coef_updates_after_stats_change():
    reg = Regiment(500, '4/4/1/0')
    old_coef = reg.coef
    reg.update_stats('6/6/2/0')
    assert reg.coef != pytest.approx(old_coef)


# ---------------------------------------------------------------------------
# front_size
# ---------------------------------------------------------------------------

def test_regiment_front_size_defaults_to_size():
    reg = Regiment(500, '4/4/0/0')
    assert reg.front_size == 500

def test_regiment_front_size_set_at_construction():
    reg = Regiment(500, '4/4/0/0', front_size=100)
    assert reg.front_size == 100

def test_regiment_front_size_in_str():
    reg = Regiment(500, '4/4/0/0', front_size=80)
    assert 'FrontSize=80' in str(reg)

def test_regiment_front_size_non_int_raises():
    with pytest.raises(TypeError):
        Regiment(500, '4/4/0/0', front_size=50.0)

def test_regiment_front_size_zero_allowed():
    reg = Regiment(0, '4/4/0/0', front_size=0)
    assert reg.front_size == 0

def test_regiment_front_size_negative_raises():
    with pytest.raises(ValueError):
        Regiment(500, '4/4/0/0', front_size=-1)

def test_regiment_set_front_size_updates():
    reg = Regiment(500, '4/4/0/0', front_size=100)
    reg.set_front_size(200)
    assert reg.front_size == 200

def test_regiment_set_front_size_non_int_raises():
    reg = Regiment(500, '4/4/0/0')
    with pytest.raises(TypeError):
        reg.set_front_size(50.5)

def test_regiment_set_front_size_zero_allowed():
    reg = Regiment(500, '4/4/0/0')
    reg.set_front_size(0)
    assert reg.front_size == 0

def test_regiment_set_front_size_negative_raises():
    reg = Regiment(500, '4/4/0/0')
    with pytest.raises(ValueError):
        reg.set_front_size(-1)

def test_regiment_front_size_in_from_dict():
    reg = Regiment.from_dict({'size': 500, 'stats': '4/4/0/0', 'front_size': 120})
    assert reg.front_size == 120

def test_regiment_front_size_from_dict_defaults_to_size():
    reg = Regiment.from_dict({'size': 500, 'stats': '4/4/0/0'})
    assert reg.front_size == 500
