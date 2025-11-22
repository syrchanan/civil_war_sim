# main entry point for the application

# ==============================================================================
# Imports
# ==============================================================================

# base libs
import logging

# ext libs

# local modules
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
    regA = InfantryRegiment(4000, '4/4/0/0', 'sq')
    regB = InfantryRegiment(3500, '4/6/1/0', 'sq')

    sim = Simulation((regA, regB))
    sim.run_simulation(time=1)
    print(sim)