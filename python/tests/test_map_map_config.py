import pytest
from imperial_generals.map import MapConfig, ElevationConfig, BiomeMapConfig, TerrainZone, BiomePresets


def make_biome_config():
    return BiomePresets.mixed_battlefield(seed=1)


def test_map_config_initialization():
    config = MapConfig(width=100, height=200, min_distance=10)
    assert config.width == 100
    assert config.height == 200
    assert config.min_distance == 10


@pytest.mark.parametrize("width, height, min_distance", [
    (0, 0, 0),
    (1, 1, 1),
    (9999, 8888, 777),
])
def test_map_config_various_values(width, height, min_distance):
    config = MapConfig(width, height, min_distance)
    assert config.width == width
    assert config.height == height
    assert config.min_distance == min_distance


def test_map_config_negative_values():
    config = MapConfig(width=-10, height=-20, min_distance=-5)
    assert config.width == -10
    assert config.height == -20
    assert config.min_distance == -5


def test_map_config_types():
    with pytest.raises(TypeError):
        MapConfig(width="100", height=200, min_distance=10)
    with pytest.raises(TypeError):
        MapConfig(width=100, height=None, min_distance=10)
    with pytest.raises(TypeError):
        MapConfig(width=100, height=200, min_distance=[10])


def test_map_config_invalid_elevation_config_type():
    with pytest.raises(TypeError):
        MapConfig(width=100, height=100, min_distance=5, elevation_config='bad')


def test_map_config_invalid_biome_config_type():
    with pytest.raises(TypeError):
        MapConfig(width=100, height=100, min_distance=5, biome_config='bad')


def test_map_config_both_configs_raises():
    elev = ElevationConfig()
    biome = make_biome_config()
    with pytest.raises(ValueError, match='Cannot specify both'):
        MapConfig(width=100, height=100, min_distance=5,
                  elevation_config=elev, biome_config=biome)


def test_map_config_with_elevation_config():
    elev = ElevationConfig()
    config = MapConfig(width=100, height=100, min_distance=5, elevation_config=elev)
    assert config.elevation_config is elev
    assert config.biome_config is None


def test_map_config_with_biome_config():
    biome = make_biome_config()
    config = MapConfig(width=100, height=100, min_distance=5, biome_config=biome)
    assert config.biome_config is biome
    assert config.elevation_config is None


def test_map_config_repr():
    config = MapConfig(1, 2, 3)
    assert repr(config) is not None
