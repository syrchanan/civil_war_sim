# Imperial Generals — TODO

Tracks progress against SPEC.md. Items are in implementation order.
Python TDD first; TypeScript port follows after Python is stable.

---

## Done

- [x] **Admin YAML config** — `config/simulation.yaml` holds all constants; `ConfigLoader` singleton; every class reads from config. 100% test coverage.
- [x] **Map API cleanup + file reorganisation** — 9 files → 5 (`elevation.py`, `biome.py`, `voronoi.py`, `generator.py`, `Cell.py`). `MapResult` replaces raw dict return. `MapGenerator.from_preset()` / `from_config()` factory methods. `MapConfig` extended with `num_rivers`, `num_lakes`, `num_roads` stubs. 100% test coverage.

---

## Up Next

- [ ] **River generation** (SPEC §1.2)
  - Source-to-sink: start at high-elevation cell, flow downhill to lake or map edge
  - Count driven by `MapConfig.num_rivers`
  - Rivers may merge; may cross roads; may not cross lakes
  - Cells on river path → `terrain_type = 'river'`
  - Stage 3 in `MapGenerator.generate_map()` pipeline

- [ ] **Lake generation** (SPEC §1.2)
  - Clusters of contiguous cells preferring low-elevation areas
  - Count driven by `MapConfig.num_lakes`
  - Lakes may not touch one another
  - Cells in lake → `terrain_type = 'lake'`
  - Stage 4 in `MapGenerator.generate_map()` pipeline

- [ ] **Road generation** (SPEC §1.2)
  - Edge-to-edge straight/gently curved paths
  - Count driven by `MapConfig.num_roads`; multiple roads must intersect on the map
  - Roads may cross rivers; must route around lakes
  - Cells on road → `has_road = True` flag on `Cell`
  - Stage 5 in `MapGenerator.generate_map()` pipeline

- [ ] **Fence auto-generation** (SPEC §1.2)
  - Placed on shared edges between `terrain_type = 'open'` and any non-open cell
  - Not user-configurable — derived from biome layout
  - Stored as `fenced_edges` set per `Cell`
  - Stage 6 in `MapGenerator.generate_map()` pipeline

---

## Backlog

- [ ] **Visualization colour fixes + view toggler** (SPEC §7)
  - Colour palette per terrain type (no red/purple — see §7.3 for targets)
  - All views share one polygon geometry; toggle with ←/→ or click
  - Feature layer overlay (roads, rivers, lakes, fences) on top of terrain

- [ ] **Weather system** (SPEC §2)
  - 7 weather types: clear, overcast, light_rain, heavy_rain, fog, storm, snow
  - Randomised at battle setup, weighted by season (spring/summer/autumn/winter)
  - Weather static for entire battle; map-wide
  - Water feature cells (river, lake) amplify fog/rain modifiers
  - All weights and modifiers already in `simulation.yaml`

- [ ] **Line of Sight (LoS) ray cast** (SPEC §3.5)
  - Cast a line segment from attacker position to target position
  - Find all cells whose polygons intersect the segment
  - LoS blocked if any intersecting cell has elevation > max(attacker_elev, target_elev)
  - Collect fenced edges crossed by ray (feeds cover calculation)

- [ ] **Cover calculation** (SPEC §3.3)
  - Accuracy penalty against attacker, additive
  - Sources: target in forest (−30%), rough (−15%), fence on target cell (−15%), fence on LoS ray (−10%)
  - All penalty values in `simulation.yaml` under `cover:`

- [ ] **Range / distance accuracy model** (SPEC §3.2)
  - Weapon has `max_range` property (map units)
  - Zones: close (≤ 0.5× range ~90%), effective (≤ range ~70%), beyond (exponential decay)
  - Weather visibility modifier applied to `max_range` before zone evaluation

- [ ] **Elevation accuracy modifier** (SPEC §3.4)
  - `dz = attacker_elevation − target_elevation`
  - `elevation_modifier = clamp(dz / ELEVATION_SCALE, −0.15, +0.15)`
  - Additive with cover penalty

- [ ] **Compose full combat efficiency pipeline** (SPEC §3.6)
  ```
  base_coef       = get_combat_efficiency(xp, morale, weapon, melee)
  effective_range = max_range × weather_visibility_modifier
  accuracy        = range_accuracy(distance, effective_range)
  accuracy       += elevation_modifier
  accuracy       -= cover_penalty  (floor 0)
  final_coef      = base_coef × accuracy
  ```

- [ ] **Movement system** (SPEC §4)
  - Turn-based; unit `speed` stat → max distance per turn
  - Terrain cost modifiers (already in `simulation.yaml` under `movement:`)
  - Lakes impassable; rivers fordable at 0.2× speed; roads 1.3×

- [ ] **Battle state serialization** (SPEC §6)
  - Full battle state → single JSON document (reproducible from seed + params)
  - Schema: map params, config overrides, unit list with positions/facing, turn number
  - Import/export from Python CLI and TypeScript UI

- [ ] **TypeScript UI** (SPEC §8)
  - Screens: Map Builder, Army Roster, Deployment, Battle Execution, Admin Config, Import/Export
  - All state round-trips through serialization format
  - Seed reproduces exact same map
  - Port Python logic after Python is stable and fully tested
