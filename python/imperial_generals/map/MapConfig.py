from typing import Optional


class MapConfig:
    """
    Holds configuration for map generation.

    Attributes:
        width (int): Width of the map in units.
        height (int): Height of the map in units.
        min_distance (int): Minimum distance between Voronoi seed points.
        elevation_config (Optional[ElevationConfig]): Configuration for uniform elevation generation.
                                                       Use for single-terrain maps.
        biome_config (Optional[BiomeMapConfig]): Configuration for multi-terrain generation.
                                                  Use for maps with mixed terrain zones.

    Note: Specify either elevation_config OR biome_config, not both. If both are None,
          cells will have default elevation (0.0).
    """
    def __init__(
        self,
        width: int,
        height: int,
        min_distance: int,
        elevation_config = None,
        biome_config = None
    ):
        # Import here to avoid circular imports
        from imperial_generals.map.ElevationConfig import ElevationConfig
        from imperial_generals.map.TerrainZone import BiomeMapConfig

        if not isinstance(width, int):
            raise TypeError("width must be an int")
        if not isinstance(height, int):
            raise TypeError("height must be an int")
        if not isinstance(min_distance, int):
            raise TypeError("min_distance must be an int")
        if elevation_config is not None and not isinstance(elevation_config, ElevationConfig):
            raise TypeError("elevation_config must be an ElevationConfig instance or None")
        if biome_config is not None and not isinstance(biome_config, BiomeMapConfig):
            raise TypeError("biome_config must be a BiomeMapConfig instance or None")

        # Cannot specify both
        if elevation_config is not None and biome_config is not None:
            raise ValueError("Cannot specify both elevation_config and biome_config. Choose one.")

        self.width = width
        self.height = height
        self.min_distance = min_distance
        self.elevation_config = elevation_config
        self.biome_config = biome_config