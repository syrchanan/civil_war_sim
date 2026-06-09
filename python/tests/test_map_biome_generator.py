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


# =============================================================================
# Zone blending
# =============================================================================

class TestZoneBlending:
    def _make_two_zone_config(self, blend_zones=True, blend_distance=30.0, seed=42):
        """Create a simple two-zone BiomeMapConfig for blending tests."""
        zones = [
            TerrainZone(
                name='Flat',
                percentage=0.5,
                elevation_config=ElevationConfig(
                    seed=seed,
                    octaves=2,
                    persistence=0.3,
                    lacunarity=2.0,
                    scale=150.0,
                    base_elevation=50.0,
                    elevation_range=20.0,
                    exponent=1.0,
                ),
                terrain_type='open',
                cover_value=0.0,
            ),
            TerrainZone(
                name='Hills',
                percentage=0.5,
                elevation_config=ElevationConfig(
                    seed=seed,
                    octaves=4,
                    persistence=0.45,
                    lacunarity=2.0,
                    scale=70.0,
                    base_elevation=50.0,
                    elevation_range=60.0,
                    exponent=1.2,
                ),
                terrain_type='hill',
                cover_value=0.2,
            ),
        ]
        return BiomeMapConfig(
            zones=zones,
            seed=seed,
            zone_scale=60.0,
            blend_zones=blend_zones,
            blend_distance=blend_distance,
        )

    def test_blend_zones_is_applied_when_configured(self):
        """_compute_blended_elevation is callable and returns a float."""
        cfg = self._make_two_zone_config(blend_zones=True, blend_distance=30.0)
        gen = BiomeGenerator(cfg)
        result = gen._compute_blended_elevation(0.5, 50.0, 50.0)
        assert isinstance(result, float)

    def test_blend_disabled_uses_primary_zone_elevation(self):
        """With blend_zones=False, blended elevation equals primary zone elevation."""
        cfg = self._make_two_zone_config(blend_zones=False, blend_distance=30.0)
        gen = BiomeGenerator(cfg)
        noise_value = 0.3   # well within first zone (threshold=0.5)
        x, y = 50.0, 50.0
        blended = gen._compute_blended_elevation(noise_value, x, y)
        primary_zone = gen._assign_zone(noise_value)
        direct = gen.elevation_generators[primary_zone.name].generate_elevation(x, y)
        assert abs(blended - direct) < 1e-9

    def test_no_blend_zone_skips_blending(self):
        """When a zone has no_blend=True, its boundary cells are not blended."""
        seed = 42
        zones = [
            TerrainZone(
                name='Cliffs',
                percentage=0.5,
                elevation_config=ElevationConfig(
                    seed=seed, octaves=6, persistence=0.55, lacunarity=3.0,
                    scale=25.0, base_elevation=75.0, elevation_range=200.0, exponent=2.5,
                ),
                terrain_type='cliff',
                cover_value=0.4,
                no_blend=True,
            ),
            TerrainZone(
                name='Valley',
                percentage=0.5,
                elevation_config=ElevationConfig(
                    seed=seed, octaves=2, persistence=0.3, lacunarity=2.0,
                    scale=150.0, base_elevation=50.0, elevation_range=20.0, exponent=1.0,
                ),
                terrain_type='open',
                cover_value=0.0,
            ),
        ]
        cfg = BiomeMapConfig(zones=zones, seed=seed, zone_scale=60.0,
                             blend_zones=True, blend_distance=30.0)
        gen = BiomeGenerator(cfg)
        # noise_value right at boundary (0.5) — would normally blend, but Cliffs has no_blend=True
        noise_value = 0.5
        x, y = 50.0, 50.0
        blended = gen._compute_blended_elevation(noise_value, x, y)
        primary_zone = gen._assign_zone(noise_value)
        direct = gen.elevation_generators[primary_zone.name].generate_elevation(x, y)
        assert abs(blended - direct) < 1e-9

    def test_compute_blended_elevation_at_exact_boundary(self):
        """noise_value at exact zone threshold gives average of two zone elevations."""
        seed = 42
        # Two equal zones, boundary at 0.5
        zones = [
            TerrainZone(
                name='A',
                percentage=0.5,
                elevation_config=ElevationConfig(
                    seed=seed, octaves=2, persistence=0.3, lacunarity=2.0,
                    scale=150.0, base_elevation=10.0, elevation_range=0.0, exponent=1.0,
                ),
                terrain_type='open',
                cover_value=0.0,
                no_blend=False,
            ),
            TerrainZone(
                name='B',
                percentage=0.5,
                elevation_config=ElevationConfig(
                    seed=seed, octaves=2, persistence=0.3, lacunarity=2.0,
                    scale=150.0, base_elevation=100.0, elevation_range=0.0, exponent=1.0,
                ),
                terrain_type='hill',
                cover_value=0.0,
                no_blend=False,
            ),
        ]
        # Use very large blend_distance so boundary region is wide
        cfg = BiomeMapConfig(zones=zones, seed=seed, zone_scale=60.0,
                             blend_zones=True, blend_distance=60.0)
        gen = BiomeGenerator(cfg)
        # At exact threshold (0.5), both zones contribute, interpolation weight = 0.5
        noise_value = 0.5
        x, y = 50.0, 50.0
        elev_a = gen.elevation_generators['A'].generate_elevation(x, y)
        elev_b = gen.elevation_generators['B'].generate_elevation(x, y)
        blended = gen._compute_blended_elevation(noise_value, x, y)
        expected = (elev_a + elev_b) / 2.0
        assert abs(blended - expected) < 1e-6
