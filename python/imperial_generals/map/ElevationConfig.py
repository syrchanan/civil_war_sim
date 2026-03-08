"""
Configuration for elevation generation with support for terrain presets.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ElevationConfig:
    """
    Configuration parameters for elevation generation using fractal noise.

    These parameters control the character of the terrain. Different combinations
    create different terrain types (mountains, hills, coastal, etc.).

    Attributes:
        seed (int): Random seed for deterministic generation.
        octaves (int): Number of noise layers to combine. More octaves = more detail.
                      Range: 1-8. Default: 4.
        persistence (float): How much each octave contributes relative to the previous.
                            Lower = smoother, Higher = rougher.
                            Range: 0.0-1.0. Default: 0.5.
        lacunarity (float): Frequency multiplier between octaves. How quickly detail scales.
                           Higher = more varied terrain at different scales.
                           Range: 1.5-4.0. Default: 2.0.
        scale (float): Overall feature size in map units. Larger = broader features.
                      Range: 10.0-200.0. Default: 50.0.
        base_elevation (float): Starting elevation value before noise is applied.
                               Default: 50.0.
        elevation_range (float): Total range of elevation values (max - min).
                                Default: 100.0 (range of 0-100).
        exponent (float): Power to raise normalized noise to. Values > 1 create plateaus,
                         values < 1 create more peaks. Default: 1.0 (linear).
    """

    seed: int = 12345
    octaves: int = 4
    persistence: float = 0.5
    lacunarity: float = 2.0
    scale: float = 50.0
    base_elevation: float = 50.0
    elevation_range: float = 100.0
    exponent: float = 1.0

    def __post_init__(self):
        """Validate configuration parameters."""
        if not 1 <= self.octaves <= 8:
            raise ValueError(f"octaves must be between 1 and 8, got {self.octaves}")
        if not 0.0 <= self.persistence <= 1.0:
            raise ValueError(f"persistence must be between 0 and 1, got {self.persistence}")
        if not 1.5 <= self.lacunarity <= 4.0:
            raise ValueError(f"lacunarity must be between 1.5 and 4.0, got {self.lacunarity}")
        if self.scale <= 0:
            raise ValueError(f"scale must be positive, got {self.scale}")
        if self.elevation_range < 0:
            raise ValueError(f"elevation_range must be non-negative, got {self.elevation_range}")
        if self.exponent <= 0:
            raise ValueError(f"exponent must be positive, got {self.exponent}")


# Terrain Presets - can be expanded in the future
class TerrainPresets:
    """
    Predefined elevation configurations for common terrain types.

    Usage:
        config = TerrainPresets.mountains(seed=12345)
        config = TerrainPresets.hills()
        config = TerrainPresets.coastal(seed=9999)
    """

    @staticmethod
    def flat(seed: int = 12345) -> ElevationConfig:
        """
        Flat terrain with minimal elevation change.
        Good for: plains, deserts, farmland.
        """
        return ElevationConfig(
            seed=seed,
            octaves=2,
            persistence=0.3,
            lacunarity=2.0,
            scale=100.0,
            base_elevation=50.0,
            elevation_range=20.0,
            exponent=1.0
        )

    @staticmethod
    def hills(seed: int = 12345) -> ElevationConfig:
        """
        Rolling hills with moderate elevation changes.
        Good for: temperate regions, farming valleys.
        """
        return ElevationConfig(
            seed=seed,
            octaves=4,
            persistence=0.5,
            lacunarity=2.0,
            scale=50.0,
            base_elevation=50.0,
            elevation_range=60.0,
            exponent=1.2
        )

    @staticmethod
    def mountains(seed: int = 12345) -> ElevationConfig:
        """
        Dramatic mountainous terrain with high peaks.
        Good for: alpine regions, dramatic battlefields.
        """
        return ElevationConfig(
            seed=seed,
            octaves=6,
            persistence=0.6,
            lacunarity=2.5,
            scale=40.0,
            base_elevation=50.0,
            elevation_range=150.0,
            exponent=1.8
        )

    @staticmethod
    def coastal(seed: int = 12345) -> ElevationConfig:
        """
        Coastal terrain with gradual elevation from sea level.
        Creates natural coastlines. Negative values represent water.
        """
        return ElevationConfig(
            seed=seed,
            octaves=3,
            persistence=0.4,
            lacunarity=2.0,
            scale=60.0,
            base_elevation=25.0,
            elevation_range=80.0,
            exponent=0.8
        )

    @staticmethod
    def forest(seed: int = 12345) -> ElevationConfig:
        """
        Forest terrain with gentle elevation changes.
        Good for: wooded areas, light vegetation cover.
        """
        return ElevationConfig(
            seed=seed,
            octaves=3,
            persistence=0.45,
            lacunarity=2.0,
            scale=55.0,
            base_elevation=50.0,
            elevation_range=40.0,
            exponent=1.0
        )

    @staticmethod
    def badlands(seed: int = 12345) -> ElevationConfig:
        """
        Rough, eroded terrain with sharp elevation changes.
        Good for: arid regions, canyons, rough terrain.
        """
        return ElevationConfig(
            seed=seed,
            octaves=5,
            persistence=0.7,
            lacunarity=3.0,
            scale=35.0,
            base_elevation=50.0,
            elevation_range=100.0,
            exponent=2.2
        )


if __name__ == "__main__":
    # Example usage
    print("=== Terrain Preset Examples ===\n")

    presets = [
        ("Flat", TerrainPresets.flat()),
        ("Hills", TerrainPresets.hills()),
        ("Mountains", TerrainPresets.mountains()),
        ("Coastal", TerrainPresets.coastal()),
        ("Forest", TerrainPresets.forest()),
        ("Badlands", TerrainPresets.badlands())
    ]

    for name, config in presets:
        print(f"{name}:")
        print(f"  Octaves: {config.octaves}, Persistence: {config.persistence}")
        print(f"  Scale: {config.scale}, Range: {config.elevation_range}")
        print(f"  Exponent: {config.exponent}\n")
