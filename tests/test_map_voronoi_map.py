import pytest
import numpy as np
from imperial_generals.map import VoronoiMap
from shapely.geometry import Polygon
from unittest.mock import patch

@pytest.fixture
def simple_points():
    # 4 points in a square
    return [(10, 10), (90, 10), (90, 90), (10, 90)]

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

def test_generate_diagram_finite(simple_points):
    vm = VoronoiMap(simple_points, width=100, height=100)
    vm.generate_diagram()
    assert vm.diagram is not None
    assert isinstance(vm.polygons, list)
    assert all(isinstance(p, Polygon) for p in vm.polygons)
    # Should have at least as many polygons as points (may be clipped)
    assert len(vm.polygons) > 0

def test_generate_diagram_empty():
    vm = VoronoiMap([], width=100, height=100)
    vm.generate_diagram()
    assert vm.diagram == {}
    assert vm.polygons == []

def test_get_cells(simple_points):
    vm = VoronoiMap(simple_points, width=100, height=100)
    vm.generate_diagram()
    cells = vm.get_cells()
    assert cells is not None

def test_order_region():
    # Test ordering of vertices
    vm = VoronoiMap([(0, 0), (1, 1)], width=10, height=10)
    vertices = np.array([[0, 0], [1, 0], [1, 1], [0, 1]])
    ordered = vm._order_region(vertices)
    assert set(map(tuple, ordered)) == set(map(tuple, vertices))

@patch("imperial_generals.map.VoronoiMap.plt.show")
def test_visualize_points(mock_show, simple_points):
    vm = VoronoiMap(simple_points, width=100, height=100)
    vm.visualize_points()
    mock_show.assert_called_once()

@patch("imperial_generals.map.VoronoiMap.plt.show")
def test_visualize_cells(mock_show, simple_points):
    vm = VoronoiMap(simple_points, width=100, height=100)
    vm.generate_diagram()
    vm.visualize_cells()
    mock_show.assert_called_once()

def test_visualize_points_empty():
    vm = VoronoiMap([], width=100, height=100)
    # Should not raise, but print warning
    vm.visualize_points()

def test_visualize_cells_empty():
    vm = VoronoiMap([(10, 10)], width=100, height=100)
    # No diagram generated yet
    vm.visualize_cells()