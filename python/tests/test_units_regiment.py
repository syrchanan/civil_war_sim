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
    # checking validity of law and stats during creation
    if case.get('shouldError'):
        with pytest.raises(Exception):
            Regiment(**case['inputs'])
    else:
        # checking attributes correctly parsed
        reg = Regiment(**case['inputs'])
        expected = case['expected']
        assert reg.size == expected['size']
        assert reg.stats == tuple(expected['stats'])
        assert reg.law == expected['law']


# ---------------------------------------------------------------------------
# Position — default (no position)
# ---------------------------------------------------------------------------

def test_regiment_position_defaults_to_none():
    reg = Regiment(500, '4/4/0/0', 'ln')
    assert reg.position is None


# ---------------------------------------------------------------------------
# Position — set at construction
# ---------------------------------------------------------------------------

def test_regiment_position_at_construction():
    pos = Position(x=10.0, y=20.0, z=5.0, cover=0.3, terrain_type='open')
    reg = Regiment(500, '4/4/0/0', 'ln', position=pos)
    assert reg.position == pos

def test_regiment_position_at_construction_all_fields():
    pos = Position(x=0.0, y=0.0, z=100.0, cover=1.0, terrain_type='hill')
    reg = Regiment(1000, '5/6/1/0', 'sq', position=pos)
    assert reg.position.terrain_type == 'hill'
    assert reg.position.z == 100.0
    assert reg.position.cover == 1.0


# ---------------------------------------------------------------------------
# Position — deploy (initial placement and movement)
# ---------------------------------------------------------------------------

def test_regiment_deploy_sets_position():
    reg = Regiment(500, '4/4/0/0', 'ln')
    pos = Position(x=5.0, y=5.0, z=0.0, cover=0.0, terrain_type='open')
    reg.deploy(pos)
    assert reg.position == pos

def test_regiment_deploy_updates_existing_position():
    pos1 = Position(x=1.0, y=1.0, z=0.0, cover=0.0, terrain_type='open')
    pos2 = Position(x=50.0, y=75.0, z=10.0, cover=0.5, terrain_type='forest')
    reg = Regiment(500, '4/4/0/0', 'ln', position=pos1)
    reg.deploy(pos2)
    assert reg.position == pos2

def test_regiment_deploy_rejects_non_position():
    reg = Regiment(500, '4/4/0/0', 'ln')
    with pytest.raises(TypeError):
        reg.deploy("not a position")


# ---------------------------------------------------------------------------
# Distance convenience methods
# ---------------------------------------------------------------------------

def _make_reg(x, y, z, law='ln'):
    reg = Regiment(500, '4/4/0/0', law)
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
    a = Regiment(500, '4/4/0/0', 'ln')
    b = _make_reg(1.0, 1.0, 0.0)
    with pytest.raises(ValueError, match="position"):
        a.flat_distance_to(b)
    with pytest.raises(ValueError, match="position"):
        a.true_distance_to(b)
    with pytest.raises(ValueError, match="position"):
        a.elevation_difference_to(b)

def test_regiment_distance_raises_if_other_not_deployed():
    a = _make_reg(0.0, 0.0, 0.0)
    b = Regiment(500, '4/4/0/0', 'ln')
    with pytest.raises(ValueError, match="position"):
        a.flat_distance_to(b)
