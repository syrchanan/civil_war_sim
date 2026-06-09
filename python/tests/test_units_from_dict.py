import pytest
from imperial_generals.units.Regiment import Regiment
from imperial_generals.units.InfantryRegiment import InfantryRegiment
from imperial_generals.units.CavalryRegiment import CavalryRegiment
from imperial_generals.units.ArtilleryBattery import ArtilleryBattery
from imperial_generals.utils import Position


# ---------------------------------------------------------------------------
# Position.from_dict
# ---------------------------------------------------------------------------

def test_position_from_dict_basic():
    d = {'x': 1.0, 'y': 2.0, 'z': 3.0, 'cover': 0.5, 'terrain_type': 'forest'}
    p = Position.from_dict(d)
    assert p.x == 1.0
    assert p.y == 2.0
    assert p.z == 3.0
    assert p.cover == 0.5
    assert p.terrain_type == 'forest'

def test_position_from_dict_equals_direct():
    d = {'x': 0.0, 'y': 0.0, 'z': 10.0, 'cover': 0.0, 'terrain_type': 'open'}
    assert Position.from_dict(d) == Position(x=0.0, y=0.0, z=10.0, cover=0.0, terrain_type='open')

def test_position_from_dict_invalid_cover_raises():
    with pytest.raises(ValueError, match="cover"):
        Position.from_dict({'x': 0.0, 'y': 0.0, 'z': 0.0, 'cover': 2.0, 'terrain_type': 'open'})

def test_position_from_dict_invalid_terrain_raises():
    with pytest.raises(ValueError, match="terrain_type"):
        Position.from_dict({'x': 0.0, 'y': 0.0, 'z': 0.0, 'cover': 0.0, 'terrain_type': 'lava'})

def test_position_from_dict_missing_key_raises():
    with pytest.raises((KeyError, TypeError)):
        Position.from_dict({'x': 1.0, 'y': 2.0})


# ---------------------------------------------------------------------------
# Regiment.from_dict
# ---------------------------------------------------------------------------

def test_regiment_from_dict_basic():
    d = {'size': 500, 'stats': '4/4/0/0'}
    reg = Regiment.from_dict(d)
    assert reg.size == 500
    assert reg.stats == (4, 4, 0, 0)
    assert reg.position is None

def test_regiment_from_dict_with_position():
    d = {
        'size': 500, 'stats': '4/4/0/0',
        'position': {'x': 1.0, 'y': 2.0, 'z': 3.0, 'cover': 0.1, 'terrain_type': 'hill'},
    }
    reg = Regiment.from_dict(d)
    assert reg.position == Position(x=1.0, y=2.0, z=3.0, cover=0.1, terrain_type='hill')

def test_regiment_from_dict_returns_regiment_instance():
    reg = Regiment.from_dict({'size': 100, 'stats': '3/3/0/0'})
    assert isinstance(reg, Regiment)


# ---------------------------------------------------------------------------
# InfantryRegiment.from_dict
# ---------------------------------------------------------------------------

def test_infantry_from_dict_basic():
    d = {'size': 800, 'stats': '4/5/1/0', 'subtype': 'line'}
    reg = InfantryRegiment.from_dict(d)
    assert reg.size == 800
    assert reg.subtype == 'line'
    assert reg.unit_type == 'inf'
    assert reg.position is None

def test_infantry_from_dict_with_position():
    d = {
        'size': 800, 'stats': '4/5/1/0', 'subtype': 'light',
        'position': {'x': 5.0, 'y': 5.0, 'z': 0.0, 'cover': 0.0, 'terrain_type': 'open'},
    }
    reg = InfantryRegiment.from_dict(d)
    assert reg.position.terrain_type == 'open'

def test_infantry_from_dict_invalid_subtype_raises():
    with pytest.raises(ValueError, match="subtype"):
        InfantryRegiment.from_dict({'size': 500, 'stats': '4/4/0/0', 'subtype': 'dragoons'})

def test_infantry_from_dict_returns_infantry_instance():
    reg = InfantryRegiment.from_dict({'size': 500, 'stats': '4/4/0/0', 'subtype': 'marine'})
    assert isinstance(reg, InfantryRegiment)


# ---------------------------------------------------------------------------
# CavalryRegiment.from_dict
# ---------------------------------------------------------------------------

def test_cavalry_from_dict_basic():
    d = {'size': 400, 'stats': '5/5/0/1', 'subtype': 'light'}
    reg = CavalryRegiment.from_dict(d)
    assert reg.size == 400
    assert reg.subtype == 'light'
    assert reg.unit_type == 'cav'
    assert reg.position is None

def test_cavalry_from_dict_with_position():
    d = {
        'size': 300, 'stats': '6/6/0/2', 'subtype': 'heavy',
        'position': {'x': 10.0, 'y': 0.0, 'z': 5.0, 'cover': 0.2, 'terrain_type': 'open'},
    }
    reg = CavalryRegiment.from_dict(d)
    assert reg.position.z == 5.0

def test_cavalry_from_dict_invalid_subtype_raises():
    with pytest.raises(ValueError, match="subtype"):
        CavalryRegiment.from_dict({'size': 400, 'stats': '5/5/0/0', 'subtype': 'line'})

def test_cavalry_from_dict_returns_cavalry_instance():
    reg = CavalryRegiment.from_dict({'size': 400, 'stats': '5/5/0/0', 'subtype': 'dragoons'})
    assert isinstance(reg, CavalryRegiment)


# ---------------------------------------------------------------------------
# ArtilleryBattery.from_dict
# ---------------------------------------------------------------------------

def test_artillery_from_dict_basic():
    d = {'size': 56, 'stats': '4/4/0/0', 'guns': 8, 'subtype': 'battery'}
    bat = ArtilleryBattery.from_dict(d)
    assert bat.size == 56
    assert bat.guns == 8
    assert bat.subtype == 'battery'
    assert bat.unit_type == 'art'
    assert bat.position is None

def test_artillery_from_dict_with_position():
    d = {
        'size': 56, 'stats': '4/4/0/0', 'guns': 8, 'subtype': 'horse battery',
        'position': {'x': 3.0, 'y': 3.0, 'z': 0.0, 'cover': 0.0, 'terrain_type': 'open'},
    }
    bat = ArtilleryBattery.from_dict(d)
    assert bat.position.x == 3.0

def test_artillery_from_dict_invalid_subtype_raises():
    with pytest.raises(ValueError, match="subtype"):
        ArtilleryBattery.from_dict({'size': 56, 'stats': '4/4/0/0', 'guns': 8, 'subtype': 'line'})

def test_artillery_from_dict_returns_artillery_instance():
    bat = ArtilleryBattery.from_dict({'size': 56, 'stats': '4/4/0/0', 'guns': 8, 'subtype': 'siege battery'})
    assert isinstance(bat, ArtilleryBattery)

def test_artillery_from_dict_effective_guns_correct():
    bat = ArtilleryBattery.from_dict({'size': 35, 'stats': '4/4/0/0', 'guns': 6, 'subtype': 'battery'})
    assert bat.effective_guns == 5
