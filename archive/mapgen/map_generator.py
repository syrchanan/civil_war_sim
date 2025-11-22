"""
MapGenerator: Generates a set of points using Poisson disc sampling and creates Voronoi cells from them.
"""

from mapgen.src.poisson_disc import PoissonDiscSampler
from mapgen.src.voronoi import VoronoiMap

class MapGenerator:
    """
    Generates a map using Poisson disc sampling and Voronoi diagrams.
    """
    def __init__(self, config):
        """
        Args:
            config (object): Configuration object with attributes:
                - width (int): Width of the map.
                - height (int): Height of the map.
                - min_distance (float): Minimum distance between points.
        """
        self.config = config

    def __str__(self):
        return (
            f"MapGenerator(width={self.config.width}, "
            f"height={self.config.height}, "
            f"min_distance={self.config.min_distance})"
        )

    def __repr__(self):
        return (
            f"<MapGenerator(config={self.config!r})>"
        )

    def generate_map(self):
        """
        Generates Poisson disc points and computes Voronoi cells.

        Returns:
            dict: {
                'points': List of (x, y) tuples,
                'voronoi': Voronoi diagram object (see voronoi.py)
            }
        """
        points = PoissonDiscSampler.generate(
            self.config.width, self.config.height, self.config.min_distance
        )
        voronoi = VoronoiMap(points, self.config.width, self.config.height)
        voronoi.generate_diagram()
        return {'points': points, 'voronoi': voronoi}

if __name__ == "__main__":
    # Example usage
    class Config:
        width = 500
        height = 500
        min_distance = 20.0

    config = Config()
    map_gen = MapGenerator(config)
    game_map = map_gen.generate_map()
    print("Map generated successfully!")
    print(f"Number of points: {len(game_map['points'])}")
    game_map['voronoi'].visualize_cells()
