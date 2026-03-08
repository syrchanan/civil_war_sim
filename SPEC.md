# Imperial Generals — Feature Spec

> Living document. All values marked TBD are configurable via admin YAML and subject to tuning.
> Implementation rule: TDD throughout. Python prototype first, TypeScript final version second.

---

## 1. Map System

### 1.1 API Cleanup
- Simplify the `MapConfig` / `BiomePresets` surface — currently requires knowing too many internal types to get started
- Consolidate file organisation: too many small files in `/map/`; group by responsibility
- Performance: map generation should be profiled and bottlenecks documented

### 1.2 Terrain Feature Layer
A second generation pass that runs after cell biome assignment. Produces linear and discrete features that overlay the cell grid rather than replacing cell properties.

#### Rivers
- Generated source-to-sink: start at a high-elevation cell, flow downhill (greedy lowest-neighbour walk with smoothing), terminate at a lake or map edge
- Count: configurable integer input (`num_rivers`)
- Rivers may flow into one another or into a lake; they may not terminate mid-map otherwise
- Rivers may cross roads; rivers may not cross lakes
- Cell effect: cells containing a river segment get `terrain_type = 'river'`
- Gameplay: fordable — units may cross but movement cost is high (TBD multiplier)
- Weather interaction: river cells amplify fog and rain intensity modifiers (TBD values)

#### Lakes
- Generated as clusters of contiguous cells preferring low-elevation areas
- Count: configurable integer input (`num_lakes`)
- Lakes are discrete and may not touch one another
- Cell effect: cells in a lake get `terrain_type = 'lake'`
- Gameplay: impassable — units cannot enter lake cells
- Weather interaction: same amplification as rivers

#### Roads
- Generated as straight or gently curved paths between two points on the map edge
- Count: configurable integer input (`num_roads`)
- If multiple roads, they must intersect somewhere on the map (intersection point is not constrained to centre)
- Roads may cross rivers; roads may not cross lakes (must route around)
- Cell effect: cells containing a road segment get a `has_road` flag
- Gameplay: movement speed bonus for units on road cells (TBD multiplier)

#### Fences
- Auto-generated: placed on the shared edge between a farmland cell (`terrain_type = 'open'`) and any non-farmland cell
- Not manually configurable — derived from biome layout
- Cell effect: stored as a set of `fenced_edges` per cell (which edges have a fence)
- Gameplay: cover modifier — see §3.3

---

## 2. Weather System

### 2.1 Types
| Type | Code |
|---|---|
| Clear | `clear` |
| Overcast | `overcast` |
| Light Rain | `light_rain` |
| Heavy Rain | `heavy_rain` |
| Fog | `fog` |
| Storm | `storm` |
| Snow | `snow` |

### 2.2 Rules
- Weather is static for the duration of a battle (no mid-battle changes for now)
- Map-wide — no per-zone variation at this scale
- Randomised at battle setup, weighted by **season** (region weighting TBD)
- Season options: spring, summer, autumn, winter

### 2.3 Gameplay Effect
- Weather modifies **visibility** — i.e. reduces the effective maximum range of all units
- Visibility modifier is a multiplier on `max_range` (TBD per weather type, e.g. fog = 0.4×, heavy rain = 0.6×, clear = 1.0×)
- Water feature cells (river, lake) further amplify fog and rain modifiers (TBD)
- No per-weapon-type interaction for now

---

## 3. Combat Efficiency

### 3.1 Existing Factors
Current `get_combat_efficiency()` takes: `stat_xp`, `stat_morale`, `stat_weapon`, `stat_melee` → returns coefficient [0, 1].
This coefficient feeds directly into the Lanchester kill-rate equations.

### 3.2 Range & Distance Accuracy Model
Weapon has a `max_range` property (in map units). Distance is 2D Euclidean between unit positions.

| Zone | Condition | Accuracy |
|---|---|---|
| Close | `distance <= max_range * 0.5` | ~90% (TBD) |
| Effective | `distance <= max_range` | ~70% (TBD) |
| Beyond range | `distance > max_range` | Drop-off curve (TBD — likely exponential decay) |

- Weather applies a multiplier to `max_range` before these zones are evaluated
- Accuracy here is a multiplier applied to the combat efficiency coefficient

### 3.3 Cover Accuracy Modifier
Cover reduces attacker accuracy. Modifiers are **additive** and applied against the attacker's efficiency.

| Cover source | Accuracy penalty (TBD) |
|---|---|
| Target in forest cell | −30% |
| Target in rough/badlands cell | −15% |
| Fence on target's cell boundary | −15% |
| Fence between attacker and target (LoS ray crosses a fenced edge) | −10% |

- Cover check uses the LoS ray (see §3.5): walk the ray, collect all fenced edges it crosses and the target's cell terrain
- All applicable penalties are summed then subtracted from base accuracy (floor: 0)

### 3.4 Elevation Accuracy Modifier
- Compute `dz = attacker_elevation − target_elevation`
- Positive `dz` = attacker has high ground → accuracy bonus
- Negative `dz` = attacker shooting uphill → accuracy penalty
- `elevation_modifier = clamp(dz / ELEVATION_SCALE, −0.15, +0.15)` where `ELEVATION_SCALE` is TBD (configurable)
- Applied as a multiplier addend on top of base accuracy (i.e. additive with cover, not multiplicative)

### 3.5 Line of Sight
- Cast a ray (line segment) from attacker position to target position
- Find all map cells whose polygons intersect that line segment
- If any intersecting cell has `elevation > max(attacker_elevation, target_elevation)` → LoS blocked, no fire possible
- Fence crossings collected here feed the cover calculation in §3.3

### 3.6 Efficiency Composition (proposed order)
```
base_coef          = get_combat_efficiency(xp, morale, weapon, melee)
effective_range    = max_range * weather_visibility_modifier
accuracy           = range_accuracy(distance, effective_range)
accuracy          += elevation_modifier
accuracy          -= cover_penalty  (floored at 0)
final_coef         = base_coef * accuracy
```
All constants configurable via admin YAML (§5).

---

## 4. Movement System

### 4.1 Model
- Turn-based
- Each unit has a `speed` stat → converts to max distance per turn (units TBD)
- Each turn a unit may move up to its speed-distance, modified by terrain

### 4.2 Terrain Cost Modifiers (all TBD, configurable)
| Terrain | Modifier |
|---|---|
| Open / farmland | 1.0× (baseline) |
| Forest | 0.6× |
| Hill | 0.7× |
| Rough / badlands | 0.5× |
| Road | 1.3× |
| River (fording) | 0.2× |
| Lake | impassable |

### 4.3 Not Yet Designed
- Flanking: unit has a `facing` direction (set by drag gesture in UI); attacks from the flank/rear get a modifier (TBD)
- Facing changes cost movement points (TBD)

---

## 5. Admin Config (YAML)

Single file (e.g. `config/simulation.yaml`) that holds **all** tunable constants across the simulation. Loaded at startup; never hardcoded in logic files.

Sections (non-exhaustive):
```yaml
combat:
  close_range_fraction: 0.5
  close_range_accuracy: 0.90
  effective_range_accuracy: 0.70
  beyond_range_decay: ...        # curve params TBD
  elevation_scale: ...
  elevation_clamp_max: 0.15
  melee_penalty_factor: 0.70
  xp_boost_per_level: 0.04
  morale_boost_per_level: 0.02
  morale_loss_constant_a: 0.00007
  morale_gain_constant_b: 0.00005
  morale_loss_constant_c: 0.0000040
  morale_gain_constant_d: 0.0000040

cover:
  forest_penalty: 0.30
  rough_penalty: 0.15
  fence_on_cell_penalty: 0.15
  fence_on_ray_penalty: 0.10

weather:
  visibility_modifiers:
    clear: 1.0
    overcast: 0.9
    light_rain: 0.75
    heavy_rain: 0.6
    fog: 0.4
    storm: 0.5
    snow: 0.65
  water_feature_amplifier: ...   # TBD

movement:
  terrain_modifiers:
    open: 1.0
    forest: 0.6
    hill: 0.7
    rough: 0.5
    road: 1.3
    river: 0.2

map:
  default_width: 200
  default_height: 200
  default_min_distance: 3
  elevation_scale: ...
```

UI admin panel (TypeScript) should expose all values as editable fields with validation.

---

## 6. Battle State Serialization

All battle state is serializable to a single JSON document. Shareable and fully reproducible given the same document.

Top-level schema (non-exhaustive):
```json
{
  "version": "1.0",
  "map": {
    "seed": 42,
    "width": 200,
    "height": 200,
    "min_distance": 3,
    "biome_preset": "mixed_battlefield",
    "num_rivers": 2,
    "num_lakes": 1,
    "num_roads": 1,
    "weather": "light_rain",
    "season": "autumn"
  },
  "config_overrides": { ... },
  "units": [
    {
      "id": "reg_001",
      "side": 0,
      "type": "infantry",
      "size": 4000,
      "stats": "4/4/0/0",
      "law": "sq",
      "position": [102.4, 87.3],
      "facing": 270
    }
  ],
  "turn": 0
}
```

- Import/export available from both Python CLI and TypeScript UI
- Seed + all map parameters → exact same map every time
- Config overrides allow per-battle tuning without changing global YAML

---

## 7. Visualization

### 7.1 Map Views
Navigable via keyboard (←/→) or Positron click-through. All views share the same cell polygon geometry.

| View | Property visualised |
|---|---|
| Elevation | `cell.elevation` — continuous heatmap |
| Terrain type | `cell.terrain_type` — categorical, sensible colours |
| Cover | `cell.cover_value` — continuous heatmap |
| Biome zones | Zone assignment — categorical |
| Weather overlay | Visibility radius / weather type indicator |
| Feature layer | Roads, rivers, lakes, fences drawn over terrain |
| Smooth (TBD) | Interpolated view without cell boundaries — aesthetic player-facing view |

### 7.2 Unit Pins
- Superimposed on any view
- Show unit side (colour), facing direction (arrow), and a label (unit id / size)
- Rendered after the map layer so always visible

### 7.3 Colour Palette
Terrain type categorical map — no red, no purple. Approximate targets:

| Terrain | Colour |
|---|---|
| open / farmland | Light yellow-green |
| forest | Medium green |
| hill | Tan / khaki |
| rough / badlands | Dark brown |
| mountain | Grey |
| beach / sand | Sandy yellow |
| river | Steel blue |
| lake | Deep blue |
| road | Dark grey / brown |
| fence | (edge overlay, not fill) dark brown line |

---

## 8. TypeScript UI (Final Version)

Admin-facing single-page application. Python prototype comes first; UI is the final delivery target.

### 8.1 Screens / Panels
1. **Map Builder** — biome preset, dimensions, seed, num rivers/lakes/roads, weather, season → generate map → view in any layer
2. **Army Roster Builder** — create units, assign stats (size, XP, morale, weapon, law), group into sides
3. **Deployment** — map view with unit pins; click cell to place unit from roster; drag to set facing
4. **Battle Execution** — turn-by-turn; each turn: move units (up to speed), issue fire orders, run Lanchester step, show results
5. **Admin Config** — editable form over `simulation.yaml` values with validation and save/load
6. **Import / Export** — load or save full battle state JSON

### 8.2 Constraints
- All map and battle settings must round-trip through the serialization format (§6)
- Seed must reproduce the exact same map
- No multiplayer for now — one admin controls both sides

---

## 9. Implementation Order

> Python TDD first. TypeScript port after Python is stable.

1. Admin YAML config loader + schema
2. Map API cleanup + file reorganisation
3. River generation (source-to-sink)
4. Lake generation (low-elevation cluster)
5. Road generation (edge-to-edge with intersection rule)
6. Fence auto-generation (farmland boundary detection)
7. Visualization colour fixes + view toggler + feature layer
8. Weather system (type, season weighting, visibility modifier)
9. LoS ray cast (cell intersection + elevation check)
10. Cover calculation (cell terrain + fence edge check)
11. Range/distance accuracy model
12. Elevation accuracy modifier
13. Compose full combat efficiency pipeline
14. Movement system (speed stat + terrain cost)
15. Battle state serialization (import/export)
16. TypeScript UI
