import pytest
from imperial_generals.units.ArtilleryBattery import ArtilleryBattery
from imperial_generals.units.Regiment import Regiment
from imperial_generals.utils import Position
from imperial_generals.utils.unit_types import UNIT_SUBTYPES


# ---------------------------------------------------------------------------
# Construction — valid
# ---------------------------------------------------------------------------

def test_artillery_unit_type():
    bat = ArtilleryBattery(size=56, stats='4/4/0/0', guns=8, subtype='battery')
    assert bat.unit_type == 'art'

def test_artillery_is_regiment():
    bat = ArtilleryBattery(size=56, stats='4/4/0/0', guns=8, subtype='battery')
    assert isinstance(bat, Regiment)

def test_artillery_attributes():
    bat = ArtilleryBattery(size=56, stats='4/4/0/0', guns=8, subtype='battery')
    assert bat.size == 56
    assert bat.guns == 8
    assert bat.stats == (4, 4, 0, 0)
    assert bat.position is None

def test_artillery_min_crew_per_gun():
    assert ArtilleryBattery.MIN_CREW_PER_GUN == 7


# ---------------------------------------------------------------------------
# Subtype
# ---------------------------------------------------------------------------

def test_artillery_subtype_valid():
    for subtype in UNIT_SUBTYPES['art']:
        bat = ArtilleryBattery(size=56, stats='4/4/0/0', guns=8, subtype=subtype)
        assert bat.subtype == subtype

def test_artillery_subtype_in_str():
    bat = ArtilleryBattery(size=56, stats='4/4/0/0', guns=8, subtype='siege battery')
    assert 'siege battery' in str(bat)

def test_artillery_invalid_subtype_raises():
    with pytest.raises(ValueError, match="subtype"):
        ArtilleryBattery(size=56, stats='4/4/0/0', guns=8, subtype='dragoons')

def test_artillery_missing_subtype_raises():
    with pytest.raises(TypeError):
        ArtilleryBattery(size=56, stats='4/4/0/0', guns=8)


# ---------------------------------------------------------------------------
# effective_guns
# ---------------------------------------------------------------------------

def test_effective_guns_fully_crewed():
    # 8 guns * 7 crew = 56 minimum, exactly crewed
    bat = ArtilleryBattery(size=56, stats='4/4/0/0', guns=8, subtype='battery')
    assert bat.effective_guns == 8

def test_effective_guns_over_crewed():
    # extra crew doesn't add guns
    bat = ArtilleryBattery(size=100, stats='4/4/0/0', guns=8, subtype='battery')
    assert bat.effective_guns == 8

def test_effective_guns_crew_limited():
    # 6 guns * 7 = 42 crew needed, only 35 (5 guns worth)
    bat = ArtilleryBattery(size=35, stats='4/4/0/0', guns=6, subtype='battery')
    assert bat.effective_guns == 5

def test_effective_guns_zero_crew():
    bat = ArtilleryBattery(size=0, stats='4/4/0/0', guns=8, subtype='battery')
    assert bat.effective_guns == 0

def test_effective_guns_zero_guns():
    bat = ArtilleryBattery(size=56, stats='4/4/0/0', guns=0, subtype='battery')
    assert bat.effective_guns == 0

def test_effective_guns_updates_when_crew_changes():
    bat = ArtilleryBattery(size=56, stats='4/4/0/0', guns=8, subtype='battery')
    assert bat.effective_guns == 8
    bat.update_size(21)  # only 3 guns worth of crew
    assert bat.effective_guns == 3

def test_effective_guns_updates_when_guns_lost():
    bat = ArtilleryBattery(size=56, stats='4/4/0/0', guns=8, subtype='battery')
    bat.update_guns(4)
    assert bat.effective_guns == 4


# ---------------------------------------------------------------------------
# update_guns
# ---------------------------------------------------------------------------

def test_update_guns_reduces():
    bat = ArtilleryBattery(size=56, stats='4/4/0/0', guns=8, subtype='battery')
    bat.update_guns(5)
    assert bat.guns == 5

def test_update_guns_zero():
    bat = ArtilleryBattery(size=56, stats='4/4/0/0', guns=8, subtype='battery')
    bat.update_guns(0)
    assert bat.guns == 0

def test_update_guns_negative_raises():
    bat = ArtilleryBattery(size=56, stats='4/4/0/0', guns=8, subtype='battery')
    with pytest.raises(ValueError, match="guns"):
        bat.update_guns(-1)

def test_update_guns_non_int_raises():
    bat = ArtilleryBattery(size=56, stats='4/4/0/0', guns=8, subtype='battery')
    with pytest.raises(TypeError, match="guns"):
        bat.update_guns(2.5)


# ---------------------------------------------------------------------------
# Construction — invalid
# ---------------------------------------------------------------------------

def test_artillery_invalid_stats_raises():
    with pytest.raises(ValueError):
        ArtilleryBattery(size=56, stats='bad/stats', guns=8, subtype='battery')

def test_artillery_negative_guns_raises():
    with pytest.raises(ValueError, match="guns"):
        ArtilleryBattery(size=56, stats='4/4/0/0', guns=-1, subtype='battery')

def test_artillery_non_int_guns_raises():
    with pytest.raises(TypeError, match="guns"):
        ArtilleryBattery(size=56, stats='4/4/0/0', guns=4.0, subtype='battery')


# ---------------------------------------------------------------------------
# str / repr
# ---------------------------------------------------------------------------

def test_artillery_str_contains_unit_type_and_guns():
    bat = ArtilleryBattery(size=56, stats='4/4/0/0', guns=8, subtype='battery')
    s = str(bat)
    assert 'art' in s
    assert '8' in s

def test_artillery_repr_contains_unit_type():
    bat = ArtilleryBattery(size=56, stats='4/4/0/0', guns=8, subtype='battery')
    assert 'art' in repr(bat)


# ---------------------------------------------------------------------------
# Position / distance (inherited)
# ---------------------------------------------------------------------------

def test_artillery_deploy():
    bat = ArtilleryBattery(size=56, stats='4/4/0/0', guns=8, subtype='battery')
    pos = Position(x=5.0, y=5.0, z=10.0, cover=0.5, terrain_type='hill')
    bat.deploy(pos)
    assert bat.position == pos

def test_artillery_position_at_construction():
    pos = Position(x=0.0, y=0.0, z=0.0, cover=0.0, terrain_type='open')
    bat = ArtilleryBattery(size=56, stats='4/4/0/0', guns=8, subtype='battery', position=pos)
    assert bat.position == pos

def test_artillery_flat_distance_to():
    a = ArtilleryBattery(size=56, stats='4/4/0/0', guns=8, subtype='battery')
    b = ArtilleryBattery(size=56, stats='4/4/0/0', guns=8, subtype='battery')
    a.deploy(Position(x=0.0, y=0.0, z=0.0, cover=0.0, terrain_type='open'))
    b.deploy(Position(x=3.0, y=4.0, z=0.0, cover=0.0, terrain_type='open'))
    assert a.flat_distance_to(b) == pytest.approx(5.0)
