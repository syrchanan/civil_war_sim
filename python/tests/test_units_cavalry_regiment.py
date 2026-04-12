import pytest
from imperial_generals.units.CavalryRegiment import CavalryRegiment
from imperial_generals.units.Regiment import Regiment
from imperial_generals.utils import Position
from imperial_generals.utils.unit_types import UNIT_SUBTYPES


# ---------------------------------------------------------------------------
# Subtype
# ---------------------------------------------------------------------------

def test_cavalry_subtype_valid():
    for subtype in UNIT_SUBTYPES['cav']:
        reg = CavalryRegiment(400, '5/5/0/0', 'ln', subtype=subtype)
        assert reg.subtype == subtype

def test_cavalry_subtype_in_str():
    reg = CavalryRegiment(400, '5/5/0/0', 'ln', subtype='dragoons')
    assert 'dragoons' in str(reg)

def test_cavalry_invalid_subtype_raises():
    with pytest.raises(ValueError, match="subtype"):
        CavalryRegiment(400, '5/5/0/0', 'ln', subtype='line')

def test_cavalry_missing_subtype_raises():
    with pytest.raises(TypeError):
        CavalryRegiment(400, '5/5/0/0', 'ln')


# ---------------------------------------------------------------------------
# unit_type and inheritance
# ---------------------------------------------------------------------------

def test_cavalry_unit_type():
    reg = CavalryRegiment(400, '5/5/0/0', 'ln', subtype='light')
    assert reg.unit_type == 'cav'

def test_cavalry_is_regiment():
    reg = CavalryRegiment(400, '5/5/0/0', 'ln', subtype='light')
    assert isinstance(reg, Regiment)

def test_cavalry_inherits_regiment_attributes():
    reg = CavalryRegiment(400, '5/5/1/1', 'sq', subtype='heavy')
    assert reg.size == 400
    assert reg.stats == (5, 5, 1, 1)
    assert reg.law == 'sq'
    assert reg.position is None

def test_cavalry_invalid_law_raises():
    with pytest.raises(ValueError):
        CavalryRegiment(400, '5/5/0/0', 'xx', subtype='light')

def test_cavalry_invalid_stats_raises():
    with pytest.raises(ValueError):
        CavalryRegiment(400, 'bad/stats', 'ln', subtype='light')


# ---------------------------------------------------------------------------
# str / repr
# ---------------------------------------------------------------------------

def test_cavalry_str_contains_unit_type():
    reg = CavalryRegiment(400, '5/5/0/0', 'ln', subtype='light')
    assert 'cav' in str(reg)

def test_cavalry_repr_contains_unit_type():
    reg = CavalryRegiment(400, '5/5/0/0', 'ln', subtype='light')
    assert 'cav' in repr(reg)


# ---------------------------------------------------------------------------
# Position / deploy (inherited)
# ---------------------------------------------------------------------------

def test_cavalry_deploy():
    reg = CavalryRegiment(400, '5/5/0/0', 'ln', subtype='light')
    pos = Position(x=10.0, y=20.0, z=5.0, cover=0.1, terrain_type='open')
    reg.deploy(pos)
    assert reg.position == pos

def test_cavalry_position_at_construction():
    pos = Position(x=1.0, y=2.0, z=0.0, cover=0.0, terrain_type='hill')
    reg = CavalryRegiment(400, '5/5/0/0', 'ln', subtype='light', position=pos)
    assert reg.position == pos


# ---------------------------------------------------------------------------
# Distance methods (inherited)
# ---------------------------------------------------------------------------

def test_cavalry_flat_distance_to():
    a = CavalryRegiment(400, '5/5/0/0', 'ln', subtype='light')
    b = CavalryRegiment(400, '5/5/0/0', 'ln', subtype='light')
    a.deploy(Position(x=0.0, y=0.0, z=0.0, cover=0.0, terrain_type='open'))
    b.deploy(Position(x=3.0, y=4.0, z=0.0, cover=0.0, terrain_type='open'))
    assert a.flat_distance_to(b) == pytest.approx(5.0)
