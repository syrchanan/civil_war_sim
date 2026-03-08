"""
Tests for TerrainZone, BiomeMapConfig, and BiomePresets.
"""

import pytest
from imperial_generals.map import ElevationConfig, TerrainPresets, TerrainZone, BiomeMapConfig, BiomePresets


# =============================================================================
# Helpers
# =============================================================================

def make_zone(name='Open', percentage=1.0, terrain_type='open', cover_value=0.0):
    return TerrainZone(
        name=name,
        percentage=percentage,
        elevation_config=ElevationConfig(),
        terrain_type=terrain_type,
        cover_value=cover_value,
    )


# =============================================================================
# TerrainZone validation
# =============================================================================

class TestTerrainZone:
    def test_valid_zone(self):
        zone = make_zone()
        assert zone.name == 'Open'
        assert zone.percentage == 1.0
        assert zone.terrain_type == 'open'
        assert zone.cover_value == 0.0

    def test_empty_name_raises(self):
        with pytest.raises(ValueError):
            TerrainZone(name='', percentage=1.0, elevation_config=ElevationConfig())

    def test_non_string_name_raises(self):
        with pytest.raises(ValueError):
            TerrainZone(name=123, percentage=1.0, elevation_config=ElevationConfig())

    def test_percentage_below_zero_raises(self):
        with pytest.raises(ValueError):
            TerrainZone(name='X', percentage=-0.1, elevation_config=ElevationConfig())

    def test_percentage_above_one_raises(self):
        with pytest.raises(ValueError):
            TerrainZone(name='X', percentage=1.1, elevation_config=ElevationConfig())

    def test_invalid_elevation_config_type_raises(self):
        with pytest.raises(TypeError):
            TerrainZone(name='X', percentage=0.5, elevation_config='bad')

    def test_non_string_terrain_type_raises(self):
        with pytest.raises(TypeError):
            TerrainZone(name='X', percentage=0.5, elevation_config=ElevationConfig(), terrain_type=42)

    def test_cover_value_below_zero_raises(self):
        with pytest.raises(ValueError):
            TerrainZone(name='X', percentage=0.5, elevation_config=ElevationConfig(), cover_value=-0.1)

    def test_cover_value_above_one_raises(self):
        with pytest.raises(ValueError):
            TerrainZone(name='X', percentage=0.5, elevation_config=ElevationConfig(), cover_value=1.1)


# =============================================================================
# BiomeMapConfig validation
# =============================================================================

class TestBiomeMapConfig:
    def test_valid_config(self):
        cfg = BiomeMapConfig(zones=[make_zone()])
        assert len(cfg.zones) == 1

    def test_empty_zones_raises(self):
        with pytest.raises(ValueError):
            BiomeMapConfig(zones=[])

    def test_non_terrain_zone_in_list_raises(self):
        with pytest.raises(TypeError):
            BiomeMapConfig(zones=['not a zone'])

    def test_percentages_not_summing_to_one_raises(self):
        zones = [make_zone('A', 0.3), make_zone('B', 0.3)]
        with pytest.raises(ValueError, match='sum to 1.0'):
            BiomeMapConfig(zones=zones)

    def test_zone_scale_zero_raises(self):
        with pytest.raises(ValueError):
            BiomeMapConfig(zones=[make_zone()], zone_scale=0.0)

    def test_blend_distance_negative_raises(self):
        with pytest.raises(ValueError):
            BiomeMapConfig(zones=[make_zone()], blend_distance=-1.0)

    def test_defaults_from_config(self):
        cfg = BiomeMapConfig(zones=[make_zone()])
        assert cfg.seed == 12345
        assert cfg.zone_scale == 80.0
        assert cfg.blend_zones is True
        assert cfg.blend_distance == 5.0

    def test_percentages_exactly_one(self):
        zones = [make_zone('A', 0.6), make_zone('B', 0.4)]
        cfg = BiomeMapConfig(zones=zones)
        assert abs(sum(z.percentage for z in cfg.zones) - 1.0) < 0.01


# =============================================================================
# BiomePresets
# =============================================================================

class TestBiomePresets:
    @pytest.mark.parametrize('preset_fn', [
        BiomePresets.mixed_battlefield,
        BiomePresets.mountainous_region,
        BiomePresets.coastal_landing,
        BiomePresets.open_plains,
    ])
    def test_preset_returns_valid_config(self, preset_fn):
        cfg = preset_fn(seed=42)
        assert isinstance(cfg, BiomeMapConfig)
        assert len(cfg.zones) > 0
        assert cfg.seed == 42
        total = sum(z.percentage for z in cfg.zones)
        assert abs(total - 1.0) < 0.01

    @pytest.mark.parametrize('preset_fn', [
        BiomePresets.mixed_battlefield,
        BiomePresets.mountainous_region,
        BiomePresets.coastal_landing,
        BiomePresets.open_plains,
    ])
    def test_preset_zones_have_valid_elevation_config(self, preset_fn):
        cfg = preset_fn(seed=99)
        for zone in cfg.zones:
            assert isinstance(zone.elevation_config, ElevationConfig)
            assert zone.elevation_config.seed == 99

    def test_custom_preset(self):
        zones = [
            TerrainZone('A', 0.5, ElevationConfig(), 'open', 0.0),
            TerrainZone('B', 0.5, ElevationConfig(), 'forest', 0.5),
        ]
        cfg = BiomePresets.custom(zones=zones, seed=7, zone_scale=50.0)
        assert isinstance(cfg, BiomeMapConfig)
        assert cfg.seed == 7
        assert cfg.zone_scale == 50.0
        assert len(cfg.zones) == 2
