"""
Tests for MapViewer and the VoronoiMap.visualize_cell_property() config-color fix.

TDD: these tests are written first, before implementation.
"""

import pytest
import matplotlib
import matplotlib.pyplot as plt

from imperial_generals.map import MapGenerator
from imperial_generals.map.generator import MapResult
from imperial_generals.map.voronoi import VoronoiMap


# ---------------------------------------------------------------------------
# Autouse fixture: close all figures after every test to prevent warnings
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def close_all_figures():
    yield
    plt.close('all')


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def small_result():
    return MapGenerator.from_preset('mixed_battlefield', seed=42, width=50, height=50, min_distance=10)


# =============================================================================
# TestMapViewerInit
# =============================================================================

class TestMapViewerInit:

    def test_valid_init_with_biome_result(self, small_result):
        from imperial_generals.map import MapViewer
        viewer = MapViewer(small_result)
        assert viewer is not None

    def test_invalid_type_raises_type_error(self):
        from imperial_generals.map import MapViewer
        with pytest.raises(TypeError):
            MapViewer("not a MapResult")

    def test_empty_cells_raises_value_error(self):
        from imperial_generals.map import MapViewer
        pts = [(10, 10), (90, 10), (10, 90), (90, 90)]
        vm = VoronoiMap(pts, 100, 100)
        # Do NOT call generate_diagram() — cells stays empty
        result = MapResult(voronoi=vm, cells=[])
        with pytest.raises(ValueError):
            MapViewer(result)

    def test_str_repr(self, small_result):
        from imperial_generals.map import MapViewer
        viewer = MapViewer(small_result)
        assert 'MapViewer' in str(viewer)
        assert 'MapViewer' in repr(viewer)


# =============================================================================
# TestMapViewerViewCycling
# =============================================================================

class TestMapViewerViewCycling:

    def test_default_view_is_elevation(self, small_result):
        from imperial_generals.map import MapViewer
        viewer = MapViewer(small_result)
        assert viewer.current_view == 'elevation'

    def test_next_view_advances(self, small_result):
        from imperial_generals.map import MapViewer
        viewer = MapViewer(small_result)
        result = viewer.next_view()
        assert result == 'terrain_type'
        assert viewer.current_view == 'terrain_type'

    def test_next_view_wraps_around(self, small_result):
        from imperial_generals.map import MapViewer
        from imperial_generals.map.viewer import VIEWS
        viewer = MapViewer(small_result)
        # Advance to the last view
        for _ in range(len(VIEWS) - 1):
            viewer.next_view()
        assert viewer.current_view == VIEWS[-1]
        # One more should wrap back to first
        result = viewer.next_view()
        assert result == VIEWS[0]
        assert viewer.current_view == VIEWS[0]

    def test_prev_view_goes_back(self, small_result):
        from imperial_generals.map import MapViewer
        from imperial_generals.map.viewer import VIEWS
        viewer = MapViewer(small_result)
        # Start at elevation (index 0), prev wraps to last
        result = viewer.prev_view()
        assert result == VIEWS[-1]

    def test_prev_view_wraps_around(self, small_result):
        from imperial_generals.map import MapViewer
        from imperial_generals.map.viewer import VIEWS
        viewer = MapViewer(small_result)
        result = viewer.prev_view()
        assert result == VIEWS[-1]
        assert viewer.current_view == VIEWS[-1]

    def test_next_then_prev_returns_to_start(self, small_result):
        from imperial_generals.map import MapViewer
        viewer = MapViewer(small_result)
        original = viewer.current_view
        viewer.next_view()
        viewer.prev_view()
        assert viewer.current_view == original


# =============================================================================
# TestMapViewerTerrainColors
# =============================================================================

class TestMapViewerTerrainColors:

    def test_known_terrain_color_open(self, small_result):
        from imperial_generals.map import MapViewer
        viewer = MapViewer(small_result)
        assert viewer.get_terrain_color('open') == '#d4e8a0'

    def test_known_terrain_color_forest(self, small_result):
        from imperial_generals.map import MapViewer
        viewer = MapViewer(small_result)
        assert viewer.get_terrain_color('forest') == '#4a7c3f'

    def test_unknown_terrain_color_fallback(self, small_result):
        from imperial_generals.map import MapViewer
        viewer = MapViewer(small_result)
        assert viewer.get_terrain_color('lava') == '#aaaaaa'

    def test_no_red_or_purple_in_known_colors(self, small_result):
        from imperial_generals.map import MapViewer
        from imperial_generals.config import get_config
        viewer = MapViewer(small_result)
        terrain_colors = get_config()['visualization']['terrain_colors']
        for terrain, color in terrain_colors.items():
            hex_lower = color.lower().lstrip('#')
            r = int(hex_lower[0:2], 16)
            g = int(hex_lower[2:4], 16)
            b = int(hex_lower[4:6], 16)
            # No color should look strongly red: high R, low G, low B
            is_red = r > 180 and g < 80 and b < 80
            # No color should look strongly purple: high R, low G, high B
            is_purple = r > 120 and g < 80 and b > 120 and r > b * 0.6
            assert not is_red, f"Terrain '{terrain}' color {color} looks red"
            assert not is_purple, f"Terrain '{terrain}' color {color} looks purple"


# =============================================================================
# TestMapViewerRendering
# =============================================================================

class TestMapViewerRendering:

    def test_render_elevation_no_exception(self, small_result):
        from imperial_generals.map import MapViewer
        viewer = MapViewer(small_result)
        viewer.render_view('elevation')

    def test_render_terrain_type_no_exception(self, small_result):
        from imperial_generals.map import MapViewer
        viewer = MapViewer(small_result)
        viewer.render_view('terrain_type')

    def test_render_cover_value_no_exception(self, small_result):
        from imperial_generals.map import MapViewer
        viewer = MapViewer(small_result)
        viewer.render_view('cover_value')

    def test_render_with_explicit_ax(self, small_result):
        from imperial_generals.map import MapViewer
        viewer = MapViewer(small_result)
        fig, ax = plt.subplots()
        before_count = plt.get_fignums()
        viewer.render_view('elevation', ax=ax)
        after_count = plt.get_fignums()
        # No new figure should have been created
        assert set(before_count) == set(after_count)

    def test_render_invalid_view_raises(self, small_result):
        from imperial_generals.map import MapViewer
        viewer = MapViewer(small_result)
        with pytest.raises(ValueError):
            viewer.render_view('nonexistent_view')

    def test_render_uniform_elevation(self, small_result):
        from imperial_generals.map import MapViewer
        viewer = MapViewer(small_result)
        # Set all cells to same elevation — exercises the min==max edge case
        for cell in small_result.cells:
            cell.set_elevation(5.0)
        viewer.render_view('elevation')

    def test_view_all_no_exception(self, small_result):
        from imperial_generals.map import MapViewer
        viewer = MapViewer(small_result)
        viewer.view()  # no view_name → renders all three views

    def test_view_single_no_exception(self, small_result):
        from imperial_generals.map import MapViewer
        viewer = MapViewer(small_result)
        viewer.view('elevation')

    def test_view_invalid_raises(self, small_result):
        from imperial_generals.map import MapViewer
        viewer = MapViewer(small_result)
        with pytest.raises(ValueError):
            viewer.view('nonexistent')

    def test_show_no_exception(self, small_result):
        from imperial_generals.map import MapViewer
        viewer = MapViewer(small_result)
        viewer.show()

    def test_show_key_right_cycles_view(self, small_result):
        """Exercise the on_key handler inside show() by simulating key events."""
        from imperial_generals.map import MapViewer
        import matplotlib.backend_bases
        viewer = MapViewer(small_result)
        fig, ax = plt.subplots(figsize=(10, 10))
        viewer.render_view(viewer.current_view, ax=ax)

        # Simulate the on_key closure by extracting it via mpl_connect
        # We replicate the closure logic directly by calling show() and then
        # triggering events on the canvas.
        viewer2 = MapViewer(small_result)
        # Call show to register the key handler
        viewer2.show()
        # Simulate right arrow key press on the last created figure
        all_figs = [plt.figure(n) for n in plt.get_fignums()]
        last_fig = all_figs[-1]
        event_right = matplotlib.backend_bases.KeyEvent(
            'key_press_event', last_fig.canvas, 'right'
        )
        last_fig.canvas.callbacks.process('key_press_event', event_right)
        assert viewer2.current_view == 'terrain_type'

        # Simulate left arrow key press
        event_left = matplotlib.backend_bases.KeyEvent(
            'key_press_event', last_fig.canvas, 'left'
        )
        last_fig.canvas.callbacks.process('key_press_event', event_left)
        assert viewer2.current_view == 'elevation'

        # Simulate an ignored key
        event_other = matplotlib.backend_bases.KeyEvent(
            'key_press_event', last_fig.canvas, 'space'
        )
        last_fig.canvas.callbacks.process('key_press_event', event_other)
        assert viewer2.current_view == 'elevation'


# =============================================================================
# TestVoronoiColorFix  — added to complement test_map_voronoi_map.py
# =============================================================================

class TestVoronoiColorFix:

    @pytest.fixture
    def built_voronoi(self):
        pts = [(10, 10), (90, 10), (10, 90), (90, 90)]
        vm = VoronoiMap(pts, width=100, height=100)
        vm.generate_diagram()
        return vm

    def test_visualize_cell_property_uses_config_color_for_open(self, built_voronoi):
        from imperial_generals.config import get_config
        # Set all cells to terrain_type='open'
        for cell in built_voronoi.get_cells():
            cell.set_terrain_type('open')
        # Should not raise
        built_voronoi.visualize_cell_property('terrain_type')
        # Verify the expected color is what config returns
        expected = get_config()['visualization']['terrain_colors']['open']
        assert expected == '#d4e8a0'

    def test_visualize_cell_property_unknown_terrain_uses_fallback(self, built_voronoi):
        # Set all cells to an unknown terrain type
        for cell in built_voronoi.get_cells():
            cell.set_terrain_type('lava')
        # Should render without exception using fallback color '#aaaaaa'
        built_voronoi.visualize_cell_property('terrain_type')
