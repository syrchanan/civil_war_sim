# main entry point for the application

# ==============================================================================
# Imports
# ==============================================================================

import logging
from collections import Counter

from imperial_generals.config import get_config
from imperial_generals.map import MapConfig, MapGenerator, MapViewer, BiomePresets
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

    print("=== Simulation Config ===")

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

    # --------------------------------------------------------------------------
    # Map generation
    #
    # MapConfig drives the full pipeline:
    #   Stage 1 — Voronoi mesh (always)
    #   Stage 2 — Biome assignment (biome_config) or elevation-only
    #   Stage 3 — River generation  (num_rivers > 0)
    #   Stage 4 — Lakes             (num_lakes  > 0, TODO)
    #   Stage 5 — Roads             (num_roads  > 0, TODO)
    #   Stage 6 — Fences            (auto from farmland edges, TODO)
    #
    # Returns a MapResult with .voronoi, .cells, and .zone_counts.
    # --------------------------------------------------------------------------

    print("\n=== Map Generation ===")

    # Build map with terrain + rivers.
    # MapConfig gives explicit control over all pipeline stages.
    # num_rivers=2 triggers Stage 3 (RiverGenerator) after biome assignment.
    map_defaults = cfg['map']['defaults']
    biome = BiomePresets.mixed_battlefield(seed=map_defaults['seed'])
    config = MapConfig(
        width=map_defaults['width'],
        height=map_defaults['height'],
        min_distance=map_defaults['min_distance'],
        biome_config=biome,
        num_rivers=4,
    )
    result = MapGenerator(config).generate_map()

    cells = result.cells
    print(f"Generated {len(cells)} cells")

    print(f"\nZone distribution:")
    for zone, count in result.zone_counts.items():
        print(f"  {zone}: {count} cells ({count / len(cells) * 100:.1f}%)")

    terrain_counts = Counter(cell.terrain_type for cell in cells)
    print(f"\nTerrain distribution (post river generation):")
    for terrain, count in sorted(terrain_counts.items()):
        print(f"  {terrain}: {count} cells ({count / len(cells) * 100:.1f}%)")

    river_cells = [c for c in cells if c.terrain_type == 'river']
    print(f"\nRivers: {len(river_cells)} cells marked as river")

    elevations = [cell.elevation for cell in cells]
    print(f"\nElevation: min={min(elevations):.2f}  max={max(elevations):.2f}  "
          f"avg={sum(elevations)/len(elevations):.2f}")

    print(f"\nSample cells:")
    for i in [0, len(cells) // 4, len(cells) // 2, 3 * len(cells) // 4]:
        c = cells[i]
        print(f"  [{c.index}] terrain={c.terrain_type}  elev={c.elevation:.2f}  cover={c.cover_value:.2f}")

    hit = result.voronoi.get_cell_at_position(50, 50)
    if hit:
        print(f"\nCell at (50,50): terrain={hit.terrain_type}  elev={hit.elevation:.2f}  cover={hit.cover_value:.2f}")

    # --------------------------------------------------------------------------
    # Map visualisation
    #
    # MapViewer wraps a MapResult and provides three views:
    #   elevation    — continuous heatmap
    #   terrain_type — categorical, colours from config/visualization.yaml
    #                  rivers drawn in a second pass (on top) for visibility
    #   cover_value  — continuous heatmap
    #
    # viewer.view()            — open all three views then block until closed
    # viewer.view('elevation') — open a single named view and block
    # viewer.show()            — single interactive figure with ←/→ to cycle views
    # --------------------------------------------------------------------------

    print("\nOpening map views (close windows to continue)...")
    viewer = MapViewer(result)
    viewer.view()  # renders all three figures and blocks until they are closed

    # --------------------------------------------------------------------------
    # Battle simulation
    # --------------------------------------------------------------------------

    print("\n=== Battle Simulation ===")

    regA = InfantryRegiment(4000, '4/4/0/0', subtype='line')
    regB = InfantryRegiment(3500, '4/6/1/0', subtype='line')

    print(f"\n{regA}")
    print(f"{regB}")

    sim = Simulation((regA, regB))
    sim.run_simulation(time=1)
    print(f"\n{sim}")
