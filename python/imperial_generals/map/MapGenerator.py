
"""
MapGenerator: Generates a set of points using Poisson disc sampling and creates Voronoi cells from them.
"""

from imperial_generals.map import PoissonDiscSampler, VoronoiMap
from imperial_generals.map.ElevationGenerator import ElevationGenerator
from imperial_generals.map.BiomeGenerator import BiomeGenerator
from typing import Any, Dict
import logging

# Configure logging for this module
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class MapGenerator:
    """
    Generates a map using Poisson disc sampling and Voronoi diagrams.
    """
    def __init__(self, config: Any) -> None:
        """
        Initialize MapGenerator with configuration.

        Args:
            config (object): Configuration object with attributes:
                - width (int): Width of the map.
                - height (int): Height of the map.
                - min_distance (float): Minimum distance between points.
        """
        self.config: Any = config
        logger.info(f"MapGenerator initialized with width={config.width}, height={config.height}, min_distance={config.min_distance}")

    def __str__(self) -> str:
        """String representation of MapGenerator."""
        return (
            f"MapGenerator(width={self.config.width}, "
            f"height={self.config.height}, "
            f"min_distance={self.config.min_distance})"
        )

    def __repr__(self) -> str:
        """Detailed representation of MapGenerator."""
        return (
            f"<MapGenerator(config={self.config!r})>"
        )

    def generate_map(self) -> Dict[str, Any]:
        """
        Generates Poisson disc points and computes Voronoi cells.
        Optionally generates terrain based on elevation_config or biome_config.

        Returns:
            dict: {
                'points': List of (x, y) tuples,
                'voronoi': VoronoiMap object,
                'elevation_generator': ElevationGenerator (if elevation_config provided),
                'biome_generator': BiomeGenerator (if biome_config provided),
                'zone_counts': Dict[str, int] (if biome_config provided)
            }
        """
        # Generate points using Poisson disc sampling
        points = PoissonDiscSampler.generate(
            self.config.width, self.config.height, self.config.min_distance
        )
        logger.info(f"Generated {len(points)} Poisson disc points.")

        # Create Voronoi diagram from points
        voronoi = VoronoiMap(points, self.config.width, self.config.height)
        voronoi.generate_diagram()
        logger.info("Voronoi diagram generated.")

        result = {'points': points, 'voronoi': voronoi}

        # Generate terrain based on config
        if self.config.biome_config is not None:
            # Multi-terrain biome generation
            logger.info("Generating multi-terrain biomes...")
            biome_gen = BiomeGenerator(self.config.biome_config)
            zone_counts = biome_gen.apply_to_cells(voronoi.get_cells())
            result['biome_generator'] = biome_gen
            result['zone_counts'] = zone_counts
            logger.info("Biome generation complete.")

        elif self.config.elevation_config is not None:
            # Uniform elevation generation
            logger.info("Generating uniform elevation for cells...")
            elevation_gen = ElevationGenerator(self.config.elevation_config)
            elevation_gen.apply_to_cells(voronoi.get_cells())
            result['elevation_generator'] = elevation_gen
            logger.info("Elevation generation complete.")

        return result


if __name__ == "__main__":
    # Example usage
    from imperial_generals.map import MapConfig

    config = MapConfig(
        width=100,
        height=100,
        min_distance=5
    )
    map_gen = MapGenerator(config)
    game_map = map_gen.generate_map()
    print("Map generated successfully!")
    print(f"Number of points: {len(game_map['points'])}")
    # Visualize the Voronoi cells
    game_map['voronoi'].visualize_cells()
