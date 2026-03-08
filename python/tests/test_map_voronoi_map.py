import pytest
import numpy as np
from imperial_generals.map import VoronoiMap
from imperial_generals.map.Cell import Cell
from shapely.geometry import Polygon, box


@pytest.fixture
def simple_points():
    return [(10, 10), (90, 10), (90, 90), (10, 90)]


@pytest.fixture
def built_voronoi(simple_points):
    vm = VoronoiMap(simple_points, width=100, height=100)
    vm.generate_diagram()
    return vm


# =============================================================================
# Construction and string representations
# =============================================================================

def test_init_and_str_repr(simple_points):
    vm = VoronoiMap(simple_points, width=100, height=100)
    assert isinstance(vm.points, np.ndarray)
    assert vm.width == 100
    assert vm.height == 100
    assert str(vm) == "VoronoiMap with 4 points"
    assert "<VoronoiMap(" in repr(vm)


def test_add_points(simple_points):
    vm = VoronoiMap(simple_points, width=100, height=100)
    vm.add_points([(50, 50), (20, 80)])
    assert vm.points.shape[0] == 6


# =============================================================================
# Diagram generation
# =============================================================================

def test_generate_diagram_finite(simple_points):
    vm = VoronoiMap(simple_points, width=100, height=100)
    vm.generate_diagram()
    assert vm.diagram is not None
    assert isinstance(vm.polygons, list)
    assert all(isinstance(p, Polygon) for p in vm.polygons)
    assert len(vm.polygons) > 0


def test_generate_diagram_empty():
    vm = VoronoiMap([], width=100, height=100)
    vm.generate_diagram()
    assert vm.diagram == {}
    assert vm.polygons == []


def test_order_region():
    vm = VoronoiMap([(0, 0), (1, 1)], width=10, height=10)
    vertices = np.array([[0, 0], [1, 0], [1, 1], [0, 1]])
    ordered = vm._order_region(vertices)
    assert set(map(tuple, ordered)) == set(map(tuple, vertices))


# =============================================================================
# Cell access
# =============================================================================

def test_get_cells(built_voronoi):
    cells = built_voronoi.get_cells()
    assert cells is not None
    assert len(cells) > 0
    assert all(isinstance(c, Cell) for c in cells)


def test_get_cell_valid_index(built_voronoi):
    cell = built_voronoi.get_cell(0)
    assert cell is not None
    assert isinstance(cell, Cell)
    assert cell.index == 0


def test_get_cell_invalid_index(built_voronoi):
    assert built_voronoi.get_cell(-1) is None
    assert built_voronoi.get_cell(9999) is None


def test_get_cell_at_position_hit(built_voronoi):
    # Use the center of a known cell so we're guaranteed to hit it
    first_cell = built_voronoi.get_cells()[0]
    cx, cy = first_cell.center
    found = built_voronoi.get_cell_at_position(cx, cy)
    assert found is not None
    assert isinstance(found, Cell)


def test_get_cell_at_position_miss(built_voronoi):
    # Outside the map bounds
    cell = built_voronoi.get_cell_at_position(500, 500)
    assert cell is None


# =============================================================================
# Visualization — just verify no exceptions (Agg backend, no display)
# =============================================================================

def test_visualize_points(simple_points):
    vm = VoronoiMap(simple_points, width=100, height=100)
    vm.visualize_points()  # should not raise


def test_visualize_cells(built_voronoi):
    built_voronoi.visualize_cells()  # should not raise


def test_visualize_cells_with_metadata(built_voronoi):
    built_voronoi.visualize_cells(show_metadata=True)


def test_visualize_points_empty():
    vm = VoronoiMap([], width=100, height=100)
    vm.visualize_points()


def test_visualize_cells_empty():
    vm = VoronoiMap([(10, 10)], width=100, height=100)
    vm.visualize_cells()


def test_visualize_cell_property_numeric(built_voronoi):
    # Elevation is numeric — uses terrain colormap + colorbar path
    built_voronoi.visualize_cell_property('elevation')


def test_visualize_cell_property_string(built_voronoi):
    # terrain_type is a string — uses tab10 + legend path
    built_voronoi.visualize_cell_property('terrain_type')


def test_visualize_cell_property_missing(built_voronoi, capsys):
    built_voronoi.visualize_cell_property('nonexistent_property')
    captured = capsys.readouterr()
    assert 'nonexistent_property' in captured.out


def test_visualize_cell_property_cover(built_voronoi):
    built_voronoi.visualize_cell_property('cover_value')


def test_visualize_cell_property_no_cells(simple_points, capsys):
    vm = VoronoiMap(simple_points, width=100, height=100)
    # No generate_diagram() call — cells is empty
    vm.visualize_cell_property('elevation')
    captured = capsys.readouterr()
    assert 'cells' in captured.out.lower()


def test_visualize_cell_property_uniform_elevation(built_voronoi):
    # All cells at same elevation triggers the min==max path (normalized = [0.5] * n)
    for cell in built_voronoi.get_cells():
        cell.set_elevation(10.0)
    built_voronoi.visualize_cell_property('elevation')


def test_visualize_cell_property_varying_elevation(built_voronoi):
    # Give each cell a different elevation so max > min, exercising the normalization path
    for i, cell in enumerate(built_voronoi.get_cells()):
        cell.set_elevation(float(i))
    built_voronoi.visualize_cell_property('elevation')
