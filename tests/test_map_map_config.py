import pytest
from imperial_generals.map import MapConfig

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

def test_map_config_repr():
    config = MapConfig(1, 2, 3)
    assert repr(config) is not None