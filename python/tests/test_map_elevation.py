"""
Tests for elevation generation system.
"""

import pytest
from shapely.geometry import box
from imperial_generals.map import (
    Cell,
    ElevationConfig,
    ElevationGenerator,
    TerrainPresets,
    MapConfig,
    MapGenerator,
    MapResult,
)


def test_elevation_config_defaults():
    """Test ElevationConfig with default values."""
    config = ElevationConfig()
    assert config.seed == 12345
    assert config.octaves == 4
    assert config.persistence == 0.5
    assert config.lacunarity == 2.0
    assert config.scale == 50.0
    assert config.base_elevation == 50.0
    assert config.elevation_range == 100.0
    assert config.exponent == 1.0


def test_elevation_config_custom():
    """Test ElevationConfig with custom values."""
    config = ElevationConfig(
        seed=999,
        octaves=6,
        persistence=0.6,
        lacunarity=2.5,
        scale=40.0,
        base_elevation=100.0,
        elevation_range=200.0,
        exponent=1.5
    )
    assert config.seed == 999
    assert config.octaves == 6
    assert config.persistence == 0.6


def test_elevation_config_validation():
    """Test ElevationConfig parameter validation."""
    # Invalid octaves
    with pytest.raises(ValueError):
        ElevationConfig(octaves=0)
    with pytest.raises(ValueError):
        ElevationConfig(octaves=10)

    # Invalid persistence
    with pytest.raises(ValueError):
        ElevationConfig(persistence=-0.1)
    with pytest.raises(ValueError):
        ElevationConfig(persistence=1.5)

    # Invalid lacunarity
    with pytest.raises(ValueError):
        ElevationConfig(lacunarity=1.0)

    # Invalid scale
    with pytest.raises(ValueError):
        ElevationConfig(scale=-10)

    # Invalid exponent
    with pytest.raises(ValueError):
        ElevationConfig(exponent=0)


def test_terrain_presets():
    """Test that all terrain presets are valid."""
    presets = [
        TerrainPresets.flat(),
        TerrainPresets.hills(),
        TerrainPresets.mountains(),
        TerrainPresets.coastal(),
        TerrainPresets.forest(),
        TerrainPresets.badlands(),
        TerrainPresets.cliff(),
    ]

    for preset in presets:
        assert isinstance(preset, ElevationConfig)
        # Validation happens in __post_init__, so if we get here, it's valid


def test_cliff_preset_properties():
    """Test that cliff preset has appropriate steep-terrain properties."""
    cfg = TerrainPresets.cliff()
    assert isinstance(cfg, ElevationConfig)
    assert cfg.exponent >= 2.0, "cliff exponent should be >= 2.0 for steep terrain"
    assert cfg.elevation_range >= 150.0, "cliff elevation_range should be >= 150.0"


def test_terrain_presets_with_seed():
    """Test that terrain presets accept custom seeds."""
    config1 = TerrainPresets.mountains(seed=123)
    config2 = TerrainPresets.mountains(seed=456)

    assert config1.seed == 123
    assert config2.seed == 456


def test_elevation_generator_initialization():
    """Test ElevationGenerator initialization."""
    config = ElevationConfig(seed=42)
    gen = ElevationGenerator(config)

    assert gen.config == config
    assert gen.noise is not None


def test_elevation_generator_invalid_config():
    """Test ElevationGenerator with invalid config."""
    with pytest.raises(TypeError):
        ElevationGenerator("not a config")


def test_elevation_generator_deterministic():
    """Test that same seed produces same results."""
    config1 = ElevationConfig(seed=42)
    config2 = ElevationConfig(seed=42)

    gen1 = ElevationGenerator(config1)
    gen2 = ElevationGenerator(config2)

    # Test multiple points
    test_points = [(0, 0), (10, 10), (50, 50), (100, 100)]

    for x, y in test_points:
        elev1 = gen1.generate_elevation(x, y)
        elev2 = gen2.generate_elevation(x, y)
        assert abs(elev1 - elev2) < 1e-10, "Same seed should produce identical results"


def test_elevation_generator_different_seeds():
    """Test that different seeds produce different results."""
    config1 = ElevationConfig(seed=42)
    config2 = ElevationConfig(seed=999)

    gen1 = ElevationGenerator(config1)
    gen2 = ElevationGenerator(config2)

    # Test that at least some points differ
    differences = 0
    test_points = [(0, 0), (10, 10), (50, 50), (100, 100)]

    for x, y in test_points:
        elev1 = gen1.generate_elevation(x, y)
        elev2 = gen2.generate_elevation(x, y)
        if abs(elev1 - elev2) > 1e-5:
            differences += 1

    assert differences > 0, "Different seeds should produce different results"


def test_elevation_generator_apply_to_cells():
    """Test applying elevation to cells."""
    # Create some test cells
    cells = []
    for i in range(5):
        poly = box(i * 10, 0, (i + 1) * 10, 10)
        cell = Cell(index=i, center=(i * 10 + 5, 5), polygon=poly)
        cells.append(cell)

    # Apply elevation
    config = TerrainPresets.hills(seed=42)
    gen = ElevationGenerator(config)
    gen.apply_to_cells(cells)

    # Check that all cells have elevation set
    for cell in cells:
        assert cell.elevation is not None
        assert isinstance(cell.elevation, float)


def test_elevation_generator_empty_cells():
    """Test apply_to_cells with empty list."""
    config = ElevationConfig(seed=42)
    gen = ElevationGenerator(config)

    # Should not raise error
    gen.apply_to_cells([])


def test_elevation_range():
    """Test that elevation stays within expected range."""
    config = ElevationConfig(
        seed=42,
        base_elevation=50.0,
        elevation_range=100.0,
        exponent=1.0
    )
    gen = ElevationGenerator(config)

    # Sample many points
    elevations = []
    for x in range(0, 100, 5):
        for y in range(0, 100, 5):
            elev = gen.generate_elevation(x, y)
            elevations.append(elev)

    min_elev = min(elevations)
    max_elev = max(elevations)

    # Should be approximately within base ± range/2
    expected_min = config.base_elevation - config.elevation_range / 2
    expected_max = config.base_elevation + config.elevation_range / 2

    # Allow some margin due to noise
    assert min_elev >= expected_min - 10
    assert max_elev <= expected_max + 10


def test_elevation_array_generation():
    """Test generating elevation arrays."""
    config = ElevationConfig(seed=42)
    gen = ElevationGenerator(config)

    # Generate a small array
    arr = gen.generate_elevation_array(width=50, height=50, resolution=5)

    assert arr.shape == (10, 10)
    assert arr.dtype == float


def test_map_generator_with_elevation():
    """Test MapGenerator with elevation config."""
    elevation_config = TerrainPresets.hills(seed=42)
    map_config = MapConfig(
        width=100,
        height=100,
        min_distance=20,
        elevation_config=elevation_config
    )

    gen = MapGenerator(map_config)
    result = gen.generate_map()

    assert isinstance(result, MapResult)
    assert len(result.cells) > 0
    for cell in result.cells:
        assert cell.elevation is not None
        assert isinstance(cell.elevation, float)


def test_map_generator_without_elevation():
    """Test MapGenerator without elevation config produces default elevation."""
    map_config = MapConfig(width=100, height=100, min_distance=20)

    gen = MapGenerator(map_config)
    result = gen.generate_map()

    assert isinstance(result, MapResult)
    for cell in result.cells:
        assert cell.elevation == 0.0


def test_str_repr():
    """Test string representations."""
    config = ElevationConfig(seed=42)
    gen = ElevationGenerator(config)

    str_repr = str(gen)
    assert 'ElevationGenerator' in str_repr
    assert 'seed=42' in str_repr

    full_repr = repr(gen)
    assert '<ElevationGenerator' in full_repr


def test_elevation_config_negative_range_raises():
    """Test that negative elevation_range raises ValueError."""
    with pytest.raises(ValueError):
        ElevationConfig(elevation_range=-1.0)


def test_map_generator_with_biome():
    """Test MapGenerator with biome config — covers the biome branch."""
    from imperial_generals.map import BiomePresets

    biome_config = BiomePresets.mixed_battlefield(seed=42)
    map_config = MapConfig(width=50, height=50, min_distance=10, biome_config=biome_config)

    gen = MapGenerator(map_config)
    assert 'MapGenerator' in str(gen)
    assert 'MapGenerator' in repr(gen)

    result = gen.generate_map()

    assert isinstance(result, MapResult)
    assert len(result.zone_counts) > 0
    assert isinstance(result.zone_counts, dict)
    assert len(result.cells) > 0
    for cell in result.cells:
        assert cell.terrain_type != ''
