import pytest
from imperial_generals.utils import Position


# ---------------------------------------------------------------------------
# Construction — valid
# ---------------------------------------------------------------------------

def test_position_basic():
    p = Position(x=10.0, y=20.0, z=5.0, cover=0.3, terrain_type='open')
    assert p.x == 10.0
    assert p.y == 20.0
    assert p.z == 5.0
    assert p.cover == 0.3
    assert p.terrain_type == 'open'

def test_position_cover_boundary_zero():
    p = Position(x=0.0, y=0.0, z=0.0, cover=0.0, terrain_type='open')
    assert p.cover == 0.0

def test_position_cover_boundary_one():
    p = Position(x=0.0, y=0.0, z=0.0, cover=1.0, terrain_type='open')
    assert p.cover == 1.0

def test_position_all_terrain_types():
    for t in Position.VALID_TERRAIN_TYPES:
        p = Position(x=0.0, y=0.0, z=0.0, cover=0.0, terrain_type=t)
        assert p.terrain_type == t

def test_position_int_coords_accepted():
    # int x/y/z should be accepted (coerced or kept)
    p = Position(x=5, y=10, z=2, cover=0.5, terrain_type='hill')
    assert p.x == 5
    assert p.y == 10
    assert p.z == 2


# ---------------------------------------------------------------------------
# Construction — invalid
# ---------------------------------------------------------------------------

def test_position_cover_below_zero():
    with pytest.raises(ValueError, match="cover"):
        Position(x=0.0, y=0.0, z=0.0, cover=-0.01, terrain_type='open')

def test_position_cover_above_one():
    with pytest.raises(ValueError, match="cover"):
        Position(x=0.0, y=0.0, z=0.0, cover=1.01, terrain_type='open')

def test_position_invalid_terrain_type():
    with pytest.raises(ValueError, match="terrain_type"):
        Position(x=0.0, y=0.0, z=0.0, cover=0.5, terrain_type='lava')

def test_position_terrain_type_case_sensitive():
    with pytest.raises(ValueError, match="terrain_type"):
        Position(x=0.0, y=0.0, z=0.0, cover=0.5, terrain_type='Open')


# ---------------------------------------------------------------------------
# __str__ and __repr__
# ---------------------------------------------------------------------------

def test_position_str_contains_key_info():
    p = Position(x=3.0, y=7.0, z=1.5, cover=0.25, terrain_type='forest')
    s = str(p)
    assert 'forest' in s
    assert '3.0' in s
    assert '7.0' in s

def test_position_repr_roundtrip_fields():
    p = Position(x=1.0, y=2.0, z=3.0, cover=0.5, terrain_type='hill')
    r = repr(p)
    assert 'Position' in r
    assert 'hill' in r


# ---------------------------------------------------------------------------
# Equality
# ---------------------------------------------------------------------------

def test_position_equality():
    a = Position(x=1.0, y=2.0, z=3.0, cover=0.5, terrain_type='open')
    b = Position(x=1.0, y=2.0, z=3.0, cover=0.5, terrain_type='open')
    assert a == b

def test_position_inequality_x():
    a = Position(x=1.0, y=2.0, z=3.0, cover=0.5, terrain_type='open')
    b = Position(x=9.0, y=2.0, z=3.0, cover=0.5, terrain_type='open')
    assert a != b

def test_position_inequality_terrain():
    a = Position(x=1.0, y=2.0, z=3.0, cover=0.5, terrain_type='open')
    b = Position(x=1.0, y=2.0, z=3.0, cover=0.5, terrain_type='forest')
    assert a != b

def test_position_eq_non_position_returns_not_implemented():
    p = Position(x=0.0, y=0.0, z=0.0, cover=0.0, terrain_type='open')
    assert p.__eq__("not a position") is NotImplemented


# ---------------------------------------------------------------------------
# Distance calculations
# ---------------------------------------------------------------------------

def test_flat_distance_same_position():
    p = Position(x=0.0, y=0.0, z=100.0, cover=0.0, terrain_type='open')
    assert p.flat_distance_to(p) == 0.0

def test_flat_distance_ignores_elevation():
    a = Position(x=0.0, y=0.0, z=0.0, cover=0.0, terrain_type='open')
    b = Position(x=0.0, y=0.0, z=999.0, cover=0.0, terrain_type='open')
    assert a.flat_distance_to(b) == 0.0

def test_flat_distance_simple():
    a = Position(x=0.0, y=0.0, z=0.0, cover=0.0, terrain_type='open')
    b = Position(x=3.0, y=4.0, z=0.0, cover=0.0, terrain_type='open')
    assert a.flat_distance_to(b) == pytest.approx(5.0)

def test_flat_distance_symmetric():
    a = Position(x=1.0, y=2.0, z=0.0, cover=0.0, terrain_type='open')
    b = Position(x=4.0, y=6.0, z=0.0, cover=0.0, terrain_type='open')
    assert a.flat_distance_to(b) == pytest.approx(b.flat_distance_to(a))


def test_true_distance_same_position():
    p = Position(x=0.0, y=0.0, z=0.0, cover=0.0, terrain_type='open')
    assert p.true_distance_to(p) == 0.0

def test_true_distance_elevation_only():
    a = Position(x=0.0, y=0.0, z=0.0, cover=0.0, terrain_type='open')
    b = Position(x=0.0, y=0.0, z=10.0, cover=0.0, terrain_type='open')
    assert a.true_distance_to(b) == pytest.approx(10.0)

def test_true_distance_3d():
    a = Position(x=0.0, y=0.0, z=0.0, cover=0.0, terrain_type='open')
    b = Position(x=2.0, y=2.0, z=1.0, cover=0.0, terrain_type='open')
    assert a.true_distance_to(b) == pytest.approx(3.0)  # sqrt(4+4+1)

def test_true_distance_symmetric():
    a = Position(x=1.0, y=2.0, z=3.0, cover=0.0, terrain_type='open')
    b = Position(x=4.0, y=6.0, z=7.0, cover=0.0, terrain_type='open')
    assert a.true_distance_to(b) == pytest.approx(b.true_distance_to(a))

def test_true_distance_gte_flat_distance():
    a = Position(x=0.0, y=0.0, z=0.0, cover=0.0, terrain_type='open')
    b = Position(x=3.0, y=4.0, z=5.0, cover=0.0, terrain_type='open')
    assert a.true_distance_to(b) >= a.flat_distance_to(b)


def test_elevation_difference_positive():
    low  = Position(x=0.0, y=0.0, z=10.0, cover=0.0, terrain_type='open')
    high = Position(x=0.0, y=0.0, z=30.0, cover=0.0, terrain_type='open')
    assert low.elevation_difference_to(high) == pytest.approx(20.0)

def test_elevation_difference_negative():
    low  = Position(x=0.0, y=0.0, z=10.0, cover=0.0, terrain_type='open')
    high = Position(x=0.0, y=0.0, z=30.0, cover=0.0, terrain_type='open')
    assert high.elevation_difference_to(low) == pytest.approx(-20.0)

def test_elevation_difference_zero():
    a = Position(x=0.0, y=0.0, z=5.0, cover=0.0, terrain_type='open')
    b = Position(x=1.0, y=1.0, z=5.0, cover=0.0, terrain_type='open')
    assert a.elevation_difference_to(b) == pytest.approx(0.0)

def test_elevation_difference_antisymmetric():
    a = Position(x=0.0, y=0.0, z=10.0, cover=0.0, terrain_type='open')
    b = Position(x=0.0, y=0.0, z=25.0, cover=0.0, terrain_type='open')
    assert a.elevation_difference_to(b) == pytest.approx(-b.elevation_difference_to(a))


# ---------------------------------------------------------------------------
# VALID_TERRAIN_TYPES — loaded from config
# ---------------------------------------------------------------------------

def test_valid_terrain_types_from_config():
    from imperial_generals.config import get_config
    expected = frozenset(get_config()['movement']['terrain_modifiers'].keys())
    assert Position.VALID_TERRAIN_TYPES == expected

def test_valid_terrain_types_contains_map_types():
    for t in ('open', 'forest', 'hill', 'rough', 'river', 'lake', 'cliff'):
        assert t in Position.VALID_TERRAIN_TYPES

def test_old_hardcoded_types_no_longer_valid():
    # 'swamp', 'urban', 'water' were in the old hardcoded set but not in map config
    for t in ('swamp', 'urban', 'water'):
        assert t not in Position.VALID_TERRAIN_TYPES


# ---------------------------------------------------------------------------
# Position.from_cell
# ---------------------------------------------------------------------------

def _make_cell():
    from shapely.geometry import box
    from imperial_generals.map.Cell import Cell
    poly = box(0, 0, 10, 10)
    c = Cell(index=0, center=(5.0, 5.0), polygon=poly,
             elevation=42.0, terrain_type='forest', cover_value=0.7)
    return c

def test_position_from_cell_coordinates():
    p = Position.from_cell(_make_cell())
    assert p.x == 5.0
    assert p.y == 5.0

def test_position_from_cell_elevation():
    p = Position.from_cell(_make_cell())
    assert p.z == 42.0

def test_position_from_cell_terrain_and_cover():
    p = Position.from_cell(_make_cell())
    assert p.terrain_type == 'forest'
    assert p.cover == 0.7

def test_position_from_cell_returns_position():
    assert isinstance(Position.from_cell(_make_cell()), Position)
