"""
Tests for the Cell class.
"""

import pytest
from shapely.geometry import box, Polygon
from imperial_generals.map import Cell


def test_cell_initialization():
    """Test basic Cell initialization."""
    poly = box(0, 0, 10, 10)
    cell = Cell(index=0, center=(5.0, 5.0), polygon=poly)

    assert cell.index == 0
    assert cell.center == (5.0, 5.0)
    assert cell.polygon == poly
    assert cell.elevation == 0.0
    assert cell.terrain_type == 'open'
    assert cell.cover_value == 0.0
    assert cell.neighbors == []


def test_cell_with_metadata():
    """Test Cell initialization with metadata."""
    poly = box(0, 0, 10, 10)
    cell = Cell(
        index=1,
        center=(5.0, 5.0),
        polygon=poly,
        elevation=15.5,
        terrain_type='forest',
        cover_value=0.7
    )

    assert cell.elevation == 15.5
    assert cell.terrain_type == 'forest'
    assert cell.cover_value == 0.7


def test_add_neighbor():
    """Test adding neighbors to a cell."""
    poly = box(0, 0, 10, 10)
    cell = Cell(index=0, center=(5.0, 5.0), polygon=poly)

    cell.add_neighbor(1)
    cell.add_neighbor(2)
    cell.add_neighbor(1)  # Duplicate should not be added

    assert len(cell.neighbors) == 2
    assert 1 in cell.neighbors
    assert 2 in cell.neighbors


def test_set_elevation():
    """Test setting elevation."""
    poly = box(0, 0, 10, 10)
    cell = Cell(index=0, center=(5.0, 5.0), polygon=poly)

    cell.set_elevation(20.5)
    assert cell.elevation == 20.5


def test_set_terrain_type():
    """Test setting terrain type."""
    poly = box(0, 0, 10, 10)
    cell = Cell(index=0, center=(5.0, 5.0), polygon=poly)

    cell.set_terrain_type('hill')
    assert cell.terrain_type == 'hill'


def test_set_cover_value():
    """Test setting cover value."""
    poly = box(0, 0, 10, 10)
    cell = Cell(index=0, center=(5.0, 5.0), polygon=poly)

    cell.set_cover_value(0.8)
    assert cell.cover_value == 0.8

    # Test invalid cover values
    with pytest.raises(ValueError):
        cell.set_cover_value(1.5)

    with pytest.raises(ValueError):
        cell.set_cover_value(-0.1)


def test_distance_to():
    """Test distance calculation between cells."""
    poly1 = box(0, 0, 10, 10)
    poly2 = box(10, 0, 20, 10)

    cell1 = Cell(index=0, center=(5.0, 5.0), polygon=poly1)
    cell2 = Cell(index=1, center=(15.0, 5.0), polygon=poly2)

    distance = cell1.distance_to(cell2)
    assert abs(distance - 10.0) < 1e-6


def test_cell_type_errors():
    """Test type validation in Cell initialization."""
    poly = box(0, 0, 10, 10)

    # Invalid index
    with pytest.raises(TypeError):
        Cell(index="0", center=(5.0, 5.0), polygon=poly)

    # Invalid center
    with pytest.raises(TypeError):
        Cell(index=0, center=(5.0,), polygon=poly)

    # Invalid polygon
    with pytest.raises(TypeError):
        Cell(index=0, center=(5.0, 5.0), polygon="not a polygon")

    # Invalid elevation
    with pytest.raises(TypeError):
        Cell(index=0, center=(5.0, 5.0), polygon=poly, elevation="high")

    # Invalid cover_value
    with pytest.raises(ValueError):
        Cell(index=0, center=(5.0, 5.0), polygon=poly, cover_value=2.0)


def test_cell_str_repr():
    """Test string representations of Cell."""
    poly = box(0, 0, 10, 10)
    cell = Cell(index=0, center=(5.0, 5.0), polygon=poly, elevation=10.5, terrain_type='forest')

    str_repr = str(cell)
    assert 'index=0' in str_repr
    assert 'terrain=forest' in str_repr
    assert 'elevation=10.50' in str_repr

    full_repr = repr(cell)
    assert '<Cell' in full_repr
    assert 'index=0' in full_repr
