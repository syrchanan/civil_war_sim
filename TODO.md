# Imperial Generals — TODO

Tracks progress against SPEC.md. Items are in implementation order.
Python TDD first; TypeScript port follows after Python is stable.

---

## Done

- [x] **Admin YAML config** — `config/simulation.yaml` holds all constants; `ConfigLoader` singleton; every class reads from config. 100% test coverage.
- [x] **Map API cleanup + file reorganisation** — 9 files → 5 (`elevation.py`, `biome.py`, `voronoi.py`, `generator.py`, `Cell.py`). `MapResult` replaces raw dict return. `MapGenerator.from_preset()` / `from_config()` factory methods. `MapConfig` extended with `num_rivers`, `num_lakes`, `num_roads` stubs. 100% test coverage.
- [x] **Split config into per-section files** — `simulation.yaml` → 7 dedicated files (`combat.yaml`, `morale.yaml`, `map.yaml`, `cover.yaml`, `weather.yaml`, `movement.yaml`, `visualization.yaml`). `ConfigLoader` now supports directory loading (merges all `.yaml` files). API unchanged. 100% test coverage.
- [x] **Smoother elevation** — Implemented zone blending (`blend_zones=True` was configured but never executed). `BiomeGenerator._compute_blended_elevation()` linearly interpolates elevation across zone boundaries. `blend_distance` raised to 15.0. Terrain preset scales tuned (flat 150, hills 70, forest 75, coastal 85). 100% test coverage.
- [x] **Cliff biome** — New `cliff` terrain preset (scale=25, elevation_range=200, exponent=2.5) and `cliffs_and_valleys` biome preset. `TerrainPresets.cliff()` / `BiomePresets.cliffs_and_valleys()` factory methods. `no_blend: bool` flag on `TerrainZone` prevents boundary smoothing on cliff edges. Cliff added to movement modifiers (0.3×) and visualization colours. 100% test coverage.
- [x] **Visualization colour fixes + view toggler** (SPEC §7) — `MapViewer` class in `map/viewer.py`: three views (elevation heatmap, terrain_type categorical, cover_value heatmap) toggled with ←/→ keyboard shortcuts. Terrain colours read from `visualization.yaml` — no red/purple. Fixed `VoronoiMap.visualize_cell_property()` to use config colours instead of `tab10`. All views share the same polygon geometry. Feature layer overlay deferred until rivers/lakes/roads/fences are generated. 100% test coverage.

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

- [ ] **Weather system** (SPEC §2)
  - 7 weather types: clear, overcast, light_rain, heavy_rain, fog, storm, snow
  - Randomised at battle setup, weighted by season (spring/summer/autumn/winter)
  - Weather static for entire battle; map-wide
  - Water feature cells (river, lake) amplify fog/rain modifiers
  - All weights and modifiers already in `weather.yaml`

- [ ] **Line of Sight (LoS) ray cast** (SPEC §3.5)
  - Cast a line segment from attacker position to target position
  - Find all cells whose polygons intersect the segment
  - LoS blocked if any intersecting cell has elevation > max(attacker_elev, target_elev)
  - Collect fenced edges crossed by ray (feeds cover calculation)

- [ ] **Cover calculation** (SPEC §3.3)
  - Accuracy penalty against attacker, additive
  - Sources: target in forest (−30%), rough (−15%), fence on target cell (−15%), fence on LoS ray (−10%)
  - All penalty values in `cover.yaml`

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
  - Terrain cost modifiers (already in `movement.yaml`)
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
