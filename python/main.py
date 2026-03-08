# main entry point for the application

# ==============================================================================
# Imports
# ==============================================================================

# base libs
import logging

# ext libs

# local modules
## map components
from imperial_generals.map import MapConfig, MapGenerator, BiomePresets

## simulation components
from imperial_generals.units import InfantryRegiment
from imperial_generals.battles import Simulation

# ==============================================================================
# Configuration
# ==============================================================================
with open("simulation.log", "w"):
    pass

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler("simulation.log"),
        logging.StreamHandler()
    ]
)

# ==============================================================================
# Main Entry Point (for now - eventually need argparse CLI)
# ==============================================================================
if __name__ == "__main__":

    # =============================================================================
    # Map generation test with biome system
    # =============================================================================

    # Choose a biome preset (try: mixed_battlefield, mountainous_region, coastal_landing, open_plains)
    biome_config = BiomePresets.mixed_battlefield(seed=42)

    map_setup = MapConfig(
        width=200,
        height=200,
        min_distance=3,
        biome_config=biome_config
    )

    map_gen = MapGenerator(map_setup)
    game_map = map_gen.generate_map()

    # Access the VoronoiMap and Cell objects
    voronoi_map = game_map['voronoi']
    cells = voronoi_map.get_cells()

    print(f"\n=== Map Generation Results ===")
    print(f"Generated {len(cells)} cells with biome terrain")

    # Terrain distribution
    from collections import Counter
    terrain_counts = Counter(cell.terrain_type for cell in cells)
    print(f"\nTerrain Distribution:")
    for terrain, count in sorted(terrain_counts.items()):
        print(f"  {terrain}: {count} cells ({count / len(cells) * 100:.1f}%)")

    # Elevation statistics
    elevations = [cell.elevation for cell in cells]
    print(f"\nElevation Statistics:")
    print(f"  Min: {min(elevations):.2f}, Max: {max(elevations):.2f}, Avg: {sum(elevations) / len(elevations):.2f}")

    # Sample a few cells to show full metadata
    if cells:
        print(f"\nSample cells:")
        sample_indices = [0, len(cells) // 4, len(cells) // 2, 3 * len(cells) // 4, len(cells) - 1]
        for i in sample_indices:
            cell = cells[i]
            print(f"  Cell {cell.index}: terrain={cell.terrain_type}, elevation={cell.elevation:.2f}, cover={cell.cover_value:.2f}")

        # Query a cell at a position
        test_cell = voronoi_map.get_cell_at_position(50, 50)
        if test_cell:
            print(f"\nCell at (50, 50): terrain={test_cell.terrain_type}, elevation={test_cell.elevation:.2f}, cover={test_cell.cover_value:.2f}")

    # Visualize terrain map
    print("\nGenerating terrain visualization...")
    voronoi_map.visualize_cell_property('elevation')
    voronoi_map.visualize_cell_property('cover_value')
    voronoi_map.visualize_cell_property('terrain_type')

    # =============================================================================
    # Simulation test
    # =============================================================================

    regA = InfantryRegiment(4000, '4/4/0/0', 'sq')
    regB = InfantryRegiment(3500, '4/6/1/0', 'sq')

    sim = Simulation((regA, regB))
    sim.run_simulation(time=1)
    print(sim)