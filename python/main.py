# main entry point for the application

# ==============================================================================
# Imports
# ==============================================================================

import logging
from collections import Counter

from imperial_generals.config import get_config
from imperial_generals.map import MapGenerator
from imperial_generals.units import InfantryRegiment
from imperial_generals.battles import Simulation

# ==============================================================================
# Logging
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
# Main
# ==============================================================================

if __name__ == "__main__":

    cfg = get_config()

    # --------------------------------------------------------------------------
    # Config summary
    # --------------------------------------------------------------------------

    print("=== Simulation Config (simulation.yaml) ===")

    combat_cfg = cfg['combat']
    print(f"\nCombat:")
    print(f"  XP boost/level:     {combat_cfg['xp_boost_per_level']}")
    print(f"  Morale boost/level: {combat_cfg['morale_boost_per_level']}")
    print(f"  Melee penalty:      {combat_cfg['melee_penalty_factor']}")
    print(f"  Weapon multipliers: { {k: v for k, v in combat_cfg['weapon_multipliers'].items()} }")

    morale_cfg = cfg['morale']
    print(f"\nMorale:")
    print(f"  Raw bounds:   [{morale_cfg['min_raw']}, {morale_cfg['max_raw']}]")
    print(f"  Scale factor: {morale_cfg['raw_scale_factor']}")
    print(f"  Loss A={morale_cfg['loss_constant_a']}  Gain B={morale_cfg['gain_constant_b']}")
    print(f"  Loss C={morale_cfg['loss_constant_c']}  Gain D={morale_cfg['gain_constant_d']}")

    map_defaults = cfg['map']['defaults']
    print(f"\nMap defaults: {map_defaults['width']}x{map_defaults['height']}, "
          f"min_distance={map_defaults['min_distance']}, seed={map_defaults['seed']}")

    # --------------------------------------------------------------------------
    # Map generation
    #
    # Two equivalent factory patterns:
    #
    #   MapGenerator.from_config(preset='mixed_battlefield')
    #       — reads width / height / min_distance / seed from simulation.yaml
    #
    #   MapGenerator.from_preset('mixed_battlefield', seed=42, width=200, height=200, min_distance=3)
    #       — explicit parameters, overrides config defaults for anything supplied
    #
    # Both return a MapResult with .voronoi, .cells, and .zone_counts.
    # --------------------------------------------------------------------------

    print("\n=== Map Generation ===")

    result = MapGenerator.from_config(preset='mixed_battlefield')

    cells       = result.cells
    voronoi_map = result.voronoi

    print(f"Generated {len(cells)} cells")

    print(f"\nZone distribution:")
    for zone, count in result.zone_counts.items():
        print(f"  {zone}: {count} cells ({count / len(cells) * 100:.1f}%)")

    terrain_counts = Counter(cell.terrain_type for cell in cells)
    print(f"\nTerrain distribution:")
    for terrain, count in sorted(terrain_counts.items()):
        print(f"  {terrain}: {count} cells ({count / len(cells) * 100:.1f}%)")

    elevations = [cell.elevation for cell in cells]
    print(f"\nElevation: min={min(elevations):.2f}  max={max(elevations):.2f}  "
          f"avg={sum(elevations)/len(elevations):.2f}")

    print(f"\nSample cells:")
    for i in [0, len(cells) // 4, len(cells) // 2, 3 * len(cells) // 4]:
        c = cells[i]
        print(f"  [{c.index}] terrain={c.terrain_type}  elev={c.elevation:.2f}  cover={c.cover_value:.2f}")

    hit = voronoi_map.get_cell_at_position(50, 50)
    if hit:
        print(f"\nCell at (50,50): terrain={hit.terrain_type}  elev={hit.elevation:.2f}  cover={hit.cover_value:.2f}")

    print("\nVisualizations (elevation / terrain_type / cover_value)...")
    voronoi_map.visualize_cell_property('elevation')
    voronoi_map.visualize_cell_property('terrain_type')
    voronoi_map.visualize_cell_property('cover_value')

    # --------------------------------------------------------------------------
    # Battle simulation
    # --------------------------------------------------------------------------

    print("\n=== Battle Simulation ===")

    regA = InfantryRegiment(4000, '4/4/0/0', 'sq')
    regB = InfantryRegiment(3500, '4/6/1/0', 'sq')

    print(f"\n{regA}")
    print(f"{regB}")

    sim = Simulation((regA, regB))
    sim.run_simulation(time=1)
    print(f"\n{sim}")
