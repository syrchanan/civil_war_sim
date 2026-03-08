"""
Terrain zone configuration for multi-biome map generation.
"""

from dataclasses import dataclass
from typing import List, Optional
from imperial_generals.map.ElevationConfig import ElevationConfig


@dataclass
class TerrainZone:
    """
    Defines a terrain zone/biome with its characteristics.

    A terrain zone represents a region of the map with consistent characteristics
    like elevation, terrain type, and cover values.

    Attributes:
        name (str): Display name for this zone (e.g., "Mountains", "Farmland").
        percentage (float): Target percentage of map to cover (0.0 to 1.0).
        elevation_config (ElevationConfig): Elevation generation parameters for this zone.
        terrain_type (str): Terrain classification for cells in this zone.
        cover_value (float): Default cover value for cells in this zone (0.0 to 1.0).
    """
    name: str
    percentage: float
    elevation_config: ElevationConfig
    terrain_type: str = 'open'
    cover_value: float = 0.0

    def __post_init__(self):
        """Validate zone parameters."""
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("name must be a non-empty string")
        if not 0.0 <= self.percentage <= 1.0:
            raise ValueError(f"percentage must be between 0 and 1, got {self.percentage}")
        if not isinstance(self.elevation_config, ElevationConfig):
            raise TypeError("elevation_config must be an ElevationConfig instance")
        if not isinstance(self.terrain_type, str):
            raise TypeError("terrain_type must be a string")
        if not 0.0 <= self.cover_value <= 1.0:
            raise ValueError(f"cover_value must be between 0 and 1, got {self.cover_value}")


@dataclass
class BiomeMapConfig:
    """
    Configuration for generating maps with multiple terrain zones.

    Defines how different terrain types are distributed across the map using
    noise-based zone generation for natural-looking terrain clustering.

    Attributes:
        zones (List[TerrainZone]): List of terrain zones to distribute.
        seed (int): Random seed for deterministic zone distribution.
        zone_scale (float): Scale of zone noise (larger = bigger zones). Default: 80.0.
        blend_zones (bool): Whether to blend elevation at zone boundaries. Default: True.
        blend_distance (float): Distance over which to blend zones (in map units). Default: 5.0.
    """
    zones: List[TerrainZone]
    seed: int = 12345
    zone_scale: float = 80.0
    blend_zones: bool = True
    blend_distance: float = 5.0

    def __post_init__(self):
        """Validate biome map configuration."""
        if not self.zones:
            raise ValueError("zones list cannot be empty")
        if not all(isinstance(z, TerrainZone) for z in self.zones):
            raise TypeError("All zones must be TerrainZone instances")

        # Check that percentages sum to approximately 1.0
        total_percentage = sum(z.percentage for z in self.zones)
        if not (0.99 <= total_percentage <= 1.01):
            raise ValueError(
                f"Zone percentages must sum to 1.0, got {total_percentage:.3f}. "
                f"Current: {', '.join(f'{z.name}={z.percentage:.2%}' for z in self.zones)}"
            )

        if self.zone_scale <= 0:
            raise ValueError(f"zone_scale must be positive, got {self.zone_scale}")
        if self.blend_distance < 0:
            raise ValueError(f"blend_distance must be non-negative, got {self.blend_distance}")


class BiomePresets:
    """
    Predefined biome configurations for common map types.

    Usage:
        config = BiomePresets.mixed_battlefield(seed=42)
        config = BiomePresets.mountainous_region(seed=123)
    """

    @staticmethod
    def mixed_battlefield(seed: int = 12345) -> BiomeMapConfig:
        """
        Balanced battlefield with varied terrain.
        Good for: Tactical battles with diverse terrain features.
        """
        from imperial_generals.map.ElevationConfig import TerrainPresets

        return BiomeMapConfig(
            seed=seed,
            zone_scale=60.0,
            zones=[
                TerrainZone(
                    name="Farmland",
                    percentage=0.40,
                    elevation_config=TerrainPresets.flat(seed=seed),
                    terrain_type='open',
                    cover_value=0.0
                ),
                TerrainZone(
                    name="Forest",
                    percentage=0.30,
                    elevation_config=TerrainPresets.forest(seed=seed),
                    terrain_type='forest',
                    cover_value=0.7
                ),
                TerrainZone(
                    name="Hills",
                    percentage=0.25,
                    elevation_config=TerrainPresets.hills(seed=seed),
                    terrain_type='hill',
                    cover_value=0.2
                ),
                TerrainZone(
                    name="Rough",
                    percentage=0.05,
                    elevation_config=TerrainPresets.badlands(seed=seed),
                    terrain_type='rough',
                    cover_value=0.3
                ),
            ]
        )

    @staticmethod
    def mountainous_region(seed: int = 12345) -> BiomeMapConfig:
        """
        Primarily mountainous with some valleys.
        Good for: Alpine warfare, defensive positions.
        """
        from imperial_generals.map.ElevationConfig import TerrainPresets

        return BiomeMapConfig(
            seed=seed,
            zone_scale=70.0,
            zones=[
                TerrainZone(
                    name="Mountains",
                    percentage=0.45,
                    elevation_config=TerrainPresets.mountains(seed=seed),
                    terrain_type='mountain',
                    cover_value=0.4
                ),
                TerrainZone(
                    name="Hills",
                    percentage=0.35,
                    elevation_config=TerrainPresets.hills(seed=seed),
                    terrain_type='hill',
                    cover_value=0.2
                ),
                TerrainZone(
                    name="Valleys",
                    percentage=0.20,
                    elevation_config=TerrainPresets.flat(seed=seed),
                    terrain_type='open',
                    cover_value=0.0
                ),
            ]
        )

    @staticmethod
    def coastal_landing(seed: int = 12345) -> BiomeMapConfig:
        """
        Coastal terrain with beaches, dunes, and inland areas.
        Good for: Amphibious operations, beach landings.
        """
        from imperial_generals.map.ElevationConfig import TerrainPresets

        return BiomeMapConfig(
            seed=seed,
            zone_scale=50.0,
            zones=[
                TerrainZone(
                    name="Beach",
                    percentage=0.25,
                    elevation_config=TerrainPresets.coastal(seed=seed),
                    terrain_type='beach',
                    cover_value=0.0
                ),
                TerrainZone(
                    name="Dunes",
                    percentage=0.20,
                    elevation_config=TerrainPresets.hills(seed=seed),
                    terrain_type='sand',
                    cover_value=0.1
                ),
                TerrainZone(
                    name="Grassland",
                    percentage=0.35,
                    elevation_config=TerrainPresets.flat(seed=seed),
                    terrain_type='open',
                    cover_value=0.0
                ),
                TerrainZone(
                    name="Forest",
                    percentage=0.20,
                    elevation_config=TerrainPresets.forest(seed=seed),
                    terrain_type='forest',
                    cover_value=0.7
                ),
            ]
        )

    @staticmethod
    def open_plains(seed: int = 12345) -> BiomeMapConfig:
        """
        Mostly flat terrain with minimal cover.
        Good for: Cavalry battles, open field engagements.
        """
        from imperial_generals.map.ElevationConfig import TerrainPresets

        return BiomeMapConfig(
            seed=seed,
            zone_scale=100.0,
            zones=[
                TerrainZone(
                    name="Farmland",
                    percentage=0.70,
                    elevation_config=TerrainPresets.flat(seed=seed),
                    terrain_type='open',
                    cover_value=0.0
                ),
                TerrainZone(
                    name="Light Woods",
                    percentage=0.20,
                    elevation_config=TerrainPresets.forest(seed=seed),
                    terrain_type='forest',
                    cover_value=0.5
                ),
                TerrainZone(
                    name="Hills",
                    percentage=0.10,
                    elevation_config=TerrainPresets.hills(seed=seed),
                    terrain_type='hill',
                    cover_value=0.1
                ),
            ]
        )

    @staticmethod
    def custom(zones: List[TerrainZone], seed: int = 12345, zone_scale: float = 70.0) -> BiomeMapConfig:
        """
        Create a custom biome configuration.

        Args:
            zones (List[TerrainZone]): Custom terrain zones (percentages must sum to 1.0).
            seed (int): Random seed.
            zone_scale (float): Scale of zones (larger = bigger regions).

        Returns:
            BiomeMapConfig: Custom biome configuration.
        """
        return BiomeMapConfig(
            seed=seed,
            zone_scale=zone_scale,
            zones=zones
        )


if __name__ == "__main__":
    # Example usage
    print("=== Biome Preset Examples ===\n")

    presets = [
        ("Mixed Battlefield", BiomePresets.mixed_battlefield()),
        ("Mountainous Region", BiomePresets.mountainous_region()),
        ("Coastal Landing", BiomePresets.coastal_landing()),
        ("Open Plains", BiomePresets.open_plains()),
    ]

    for name, config in presets:
        print(f"{name}:")
        print(f"  Zones: {len(config.zones)}")
        for zone in config.zones:
            print(f"    - {zone.name}: {zone.percentage:.0%} ({zone.terrain_type}, cover={zone.cover_value})")
        print()
