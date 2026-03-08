"""
Tests for BiomeGenerator.
"""

import pytest
from shapely.geometry import box
from imperial_generals.map import Cell, BiomeGenerator, BiomePresets, BiomeMapConfig, TerrainZone, ElevationConfig


# =============================================================================
# Helpers
# =============================================================================

def make_cells(n=25, grid_size=5):
    """Create a grid of n cells for testing."""
    cells = []
    for i in range(grid_size):
        for j in range(grid_size):
            x, y = i * 10, j * 10
            poly = box(x, y, x + 10, y + 10)
            cells.append(Cell(index=len(cells), center=(x + 5, y + 5), polygon=poly))
    return cells[:n]


def simple_config(seed=42):
    return BiomePresets.mixed_battlefield(seed=seed)


# =============================================================================
# Construction
# =============================================================================

class TestBiomeGeneratorInit:
    def test_valid_init(self):
        cfg = simple_config()
        gen = BiomeGenerator(cfg)
        assert gen is not None
        assert gen.config is cfg

    def test_invalid_config_type_raises(self):
        with pytest.raises(TypeError):
            BiomeGenerator('not a config')

    def test_elevation_generators_created_per_zone(self):
        cfg = simple_config()
        gen = BiomeGenerator(cfg)
        assert len(gen.elevation_generators) == len(cfg.zones)
        for zone in cfg.zones:
            assert zone.name in gen.elevation_generators

    def test_str_repr(self):
        gen = BiomeGenerator(simple_config())
        assert 'BiomeGenerator' in str(gen)
        assert 'BiomeGenerator' in repr(gen)


# =============================================================================
# Zone assignment
# =============================================================================

class TestZoneAssignment:
    def test_noise_value_in_range(self):
        gen = BiomeGenerator(simple_config())
        for x, y in [(0, 0), (50, 50), (100, 100), (200, 200)]:
            val = gen._get_zone_noise_value(x, y)
            assert 0.0 <= val <= 1.0

    def test_assign_zone_returns_terrain_zone(self):
        gen = BiomeGenerator(simple_config())
        zone = gen._assign_zone(0.5)
        assert isinstance(zone, TerrainZone)

    def test_assign_zone_covers_all_values(self):
        gen = BiomeGenerator(simple_config())
        # Edge values should not raise
        gen._assign_zone(0.0)
        gen._assign_zone(1.0)

    def test_get_zone_at_position(self):
        gen = BiomeGenerator(simple_config())
        zone = gen.get_zone_at_position(50, 50)
        assert isinstance(zone, TerrainZone)
        assert zone.name in [z.name for z in gen.config.zones]


# =============================================================================
# apply_to_cells
# =============================================================================

class TestApplyToCells:
    def test_applies_terrain_to_all_cells(self):
        gen = BiomeGenerator(simple_config())
        cells = make_cells()
        gen.apply_to_cells(cells)
        for cell in cells:
            assert cell.terrain_type != ''
            assert isinstance(cell.elevation, float)
            assert 0.0 <= cell.cover_value <= 1.0

    def test_returns_zone_counts(self):
        gen = BiomeGenerator(simple_config())
        cells = make_cells()
        counts = gen.apply_to_cells(cells)
        assert isinstance(counts, dict)
        assert set(counts.keys()) == {z.name for z in gen.config.zones}
        assert sum(counts.values()) == len(cells)

    def test_empty_cells_returns_empty_dict(self):
        gen = BiomeGenerator(simple_config())
        result = gen.apply_to_cells([])
        assert result == {}

    def test_deterministic_with_same_seed(self):
        cfg1 = simple_config(seed=7)
        cfg2 = simple_config(seed=7)
        gen1 = BiomeGenerator(cfg1)
        gen2 = BiomeGenerator(cfg2)
        cells1 = make_cells()
        cells2 = make_cells()
        gen1.apply_to_cells(cells1)
        gen2.apply_to_cells(cells2)
        for c1, c2 in zip(cells1, cells2):
            assert c1.terrain_type == c2.terrain_type
            assert abs(c1.elevation - c2.elevation) < 1e-9

    def test_different_seeds_produce_different_zones(self):
        gen1 = BiomeGenerator(simple_config(seed=1))
        gen2 = BiomeGenerator(simple_config(seed=999))
        cells1 = make_cells(n=100, grid_size=10)
        cells2 = make_cells(n=100, grid_size=10)
        gen1.apply_to_cells(cells1)
        gen2.apply_to_cells(cells2)
        terrains1 = [c.terrain_type for c in cells1]
        terrains2 = [c.terrain_type for c in cells2]
        assert terrains1 != terrains2


# =============================================================================
# generate_zone_map_array
# =============================================================================

class TestZoneMapArray:
    def test_returns_correct_shape(self):
        gen = BiomeGenerator(simple_config())
        arr = gen.generate_zone_map_array(width=50, height=40, resolution=1)
        assert arr.shape == (40, 50)

    def test_values_are_valid_zone_indices(self):
        gen = BiomeGenerator(simple_config())
        arr = gen.generate_zone_map_array(width=30, height=30, resolution=5)
        n_zones = len(gen.config.zones)
        assert arr.min() >= 0
        assert arr.max() < n_zones

    def test_resolution_reduces_size(self):
        gen = BiomeGenerator(simple_config())
        arr = gen.generate_zone_map_array(width=100, height=100, resolution=10)
        assert arr.shape == (10, 10)
