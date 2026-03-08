"""
Tests for MapConfig (feature count fields), MapResult, and MapGenerator factory methods.

The generate_map() pipeline and basic MapConfig/MapGenerator behaviour are covered by
test_map_map_config.py and test_map_elevation.py; this file focuses on the new surface.
"""

import pytest
from imperial_generals.map import (
    MapConfig, MapResult, MapGenerator, VoronoiMap, BiomePresets, ElevationConfig, Cell
)


# =============================================================================
# MapConfig — feature count fields
# =============================================================================

def test_map_config_feature_count_defaults():
    config = MapConfig(width=50, height=50, min_distance=10)
    assert config.num_rivers == 0
    assert config.num_lakes == 0
    assert config.num_roads == 0


def test_map_config_feature_counts_set():
    config = MapConfig(width=50, height=50, min_distance=10,
                       num_rivers=2, num_lakes=1, num_roads=3)
    assert config.num_rivers == 2
    assert config.num_lakes == 1
    assert config.num_roads == 3


def test_map_config_feature_count_non_int_raises():
    with pytest.raises(TypeError):
        MapConfig(width=50, height=50, min_distance=10, num_rivers='2')
    with pytest.raises(TypeError):
        MapConfig(width=50, height=50, min_distance=10, num_lakes=1.5)
    with pytest.raises(TypeError):
        MapConfig(width=50, height=50, min_distance=10, num_roads=None)


def test_map_config_feature_count_negative_raises():
    with pytest.raises(ValueError):
        MapConfig(width=50, height=50, min_distance=10, num_rivers=-1)
    with pytest.raises(ValueError):
        MapConfig(width=50, height=50, min_distance=10, num_lakes=-1)
    with pytest.raises(ValueError):
        MapConfig(width=50, height=50, min_distance=10, num_roads=-1)


# =============================================================================
# MapResult structure
# =============================================================================

def test_map_result_has_required_fields():
    config = MapConfig(width=50, height=50, min_distance=15)
    result = MapGenerator(config).generate_map()
    assert isinstance(result, MapResult)
    assert isinstance(result.voronoi, VoronoiMap)
    assert isinstance(result.cells, list)
    assert all(isinstance(c, Cell) for c in result.cells)
    assert isinstance(result.zone_counts, dict)


def test_map_result_cells_match_voronoi():
    config = MapConfig(width=50, height=50, min_distance=15)
    result = MapGenerator(config).generate_map()
    assert result.cells is result.voronoi.get_cells()


def test_map_result_zone_counts_empty_without_biome():
    config = MapConfig(width=50, height=50, min_distance=15)
    result = MapGenerator(config).generate_map()
    assert result.zone_counts == {}


def test_map_result_zone_counts_populated_with_biome():
    biome = BiomePresets.mixed_battlefield(seed=42)
    config = MapConfig(width=50, height=50, min_distance=15, biome_config=biome)
    result = MapGenerator(config).generate_map()
    assert len(result.zone_counts) > 0
    assert all(isinstance(v, int) for v in result.zone_counts.values())


def test_map_result_str_repr():
    config = MapConfig(width=50, height=50, min_distance=15)
    result = MapGenerator(config).generate_map()
    assert 'MapResult' in str(result)
    assert 'MapResult' in repr(result)


# =============================================================================
# MapGenerator.from_preset
# =============================================================================

def test_from_preset_returns_map_result():
    result = MapGenerator.from_preset('mixed_battlefield', seed=42,
                                      width=50, height=50, min_distance=15)
    assert isinstance(result, MapResult)


def test_from_preset_uses_config_defaults_for_omitted_dims():
    # Width/height/min_distance should fall back to simulation.yaml defaults (200x200, md=3)
    result = MapGenerator.from_preset('mixed_battlefield', seed=42,
                                      width=50, height=50, min_distance=15)
    assert result.voronoi.width == 50
    assert result.voronoi.height == 50


def test_from_preset_has_terrain():
    result = MapGenerator.from_preset('mixed_battlefield', seed=42,
                                      width=50, height=50, min_distance=15)
    assert len(result.zone_counts) > 0
    assert len(result.cells) > 0


def test_from_preset_all_named_presets():
    for preset in ('mixed_battlefield', 'mountainous_region', 'coastal_landing', 'open_plains'):
        result = MapGenerator.from_preset(preset, seed=1,
                                          width=40, height=40, min_distance=15)
        assert isinstance(result, MapResult)
        assert len(result.cells) > 0


def test_from_preset_invalid_name_raises():
    with pytest.raises(KeyError):
        MapGenerator.from_preset('nonexistent_preset', seed=42,
                                  width=40, height=40, min_distance=15)



# =============================================================================
# MapGenerator.from_config
# =============================================================================

def test_from_config_returns_map_result():
    result = MapGenerator.from_config(width=50, height=50, min_distance=15)
    assert isinstance(result, MapResult)
    assert len(result.cells) > 0


def test_from_config_with_preset_override():
    result = MapGenerator.from_config(preset='open_plains',
                                      width=50, height=50, min_distance=15)
    assert isinstance(result, MapResult)
    assert len(result.zone_counts) > 0
