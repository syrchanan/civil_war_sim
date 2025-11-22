# filepath: mapgen/src/main.py

from mapgen.src.config import Config
from mapgen.src.map_generator import MapGenerator
from mapgen.src.voronoi import VoronoiDiagram

def main():
    # Example: set config values directly or load from a file
    config = Config(width=100, height=100, min_distance=10.0)
    map_gen = MapGenerator(config)
    game_map = map_gen.generate_map()
    VoronoiDiagram.visualize_points(game_map['points'])
    print("Map generated successfully!")

if __name__ == "__main__":
    main()
