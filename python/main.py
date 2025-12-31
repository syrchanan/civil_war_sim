# main entry point for the application

# ==============================================================================
# Imports
# ==============================================================================

# base libs
import logging

# ext libs

# local modules
## map components
from imperial_generals.map import MapConfig, MapGenerator

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
    # Map generation test
    # =============================================================================

    map_setup = MapConfig(
        width=100,
        height=100,
        min_distance=5
    )

    map_gen = MapGenerator(map_setup)
    game_map = map_gen.generate_map()
    game_map['voronoi'].visualize_cells()

    # =============================================================================
    # Simulation test
    # =============================================================================

    regA = InfantryRegiment(4000, '4/4/0/0', 'sq')
    regB = InfantryRegiment(3500, '4/6/1/0', 'sq')

    sim = Simulation((regA, regB))
    sim.run_simulation(time=1)
    print(sim)