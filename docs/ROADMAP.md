# Imperial Generals — Roadmap

> Single source of truth for features, design decisions, and implementation order.
> Python TDD prototype first; JavaScript library port after Python is stable.
> Status: ✓ done · ► next · ○ backlog

---

## Status Summary

| # | Feature | Status |
|---|---|---|
| 1 | Admin YAML config | ✓ |
| 2 | Map API cleanup + file reorganisation | ✓ |
| 3 | River generation | ✓ |
| 4 | Streamlit prototype UI | ► |
| 5 | Lake generation | ○ |
| 6 | River→Lake termination update | ○ |
| 7 | Road generation | ○ |
| 8 | Fence auto-generation | ○ |
| 9 | Weather system | ○ |
| 10 | Morale break / retreat | ○ |
| 11 | LoS ray cast + flanking design | ○ |
| 12 | Cover calculation | ○ |
| 13 | Range/distance accuracy model | ○ |
| 14 | Elevation accuracy modifier | ○ |
| 15 | Brigade-level targeting | ○ |
| 16 | Full combat efficiency pipeline | ○ |
| 17 | Movement system | ○ |
| 18 | Battle state serialization | ○ |
| 19 | Admin effect modifier | ○ |
| 20 | JavaScript library port | ○ |

---

## 1. Admin YAML Config ✓
All tunable constants live in `config/` (8 YAML files). `ConfigLoader` singleton merges them at startup. Nothing hardcoded in logic files — all defaults use `field(default_factory=lambda: get_config()[...])`.

Files: `combat.yaml`, `morale.yaml`, `map.yaml`, `cover.yaml`, `weather.yaml`, `movement.yaml`, `visualization.yaml`, `unit_subtypes.yaml`

---

## 2. Map System ✓

### Pipeline
`MapGenerator.generate_map()` runs stages in order, each mutating cells in place:

| Stage | Feature | Status |
|---|---|---|
| 1 | Voronoi mesh (Poisson disc → diagram → clipped cells) | ✓ |
| 2 | Biome / elevation assignment | ✓ |
| 3 | River generation | ✓ |
| 4 | Lake generation | ○ |
| 5 | Road generation | ○ |
| 6 | Fence auto-generation | ○ |

### API
```python
MapGenerator.from_config(preset='mixed_battlefield')          # reads config defaults
MapGenerator.from_preset('mixed_battlefield', seed=42, ...)   # explicit dims
MapGenerator(MapConfig(...)).generate_map()                    # full custom config
```

### Rivers ✓
- Source-to-sink greedy downhill walk (STRtree-accelerated neighbour graph, BFS fallback)
- Terminates at map edge, or at a lake cell once lakes exist (see #6)
- `terrain_type = 'river'`; fordable, movement penalty (TBD multiplier)
- River cells amplify fog/rain weather modifiers (TBD)

### Lakes ○
- Contiguous cell clusters seeded at low-elevation areas
- `num_lakes` drives count; lakes may not touch each other
- `terrain_type = 'lake'`; impassable, same weather amplification as rivers

### Roads ○
- Edge-to-edge paths (straight or gently curved)
- `num_roads` drives count; multiple roads must intersect somewhere on the map
- Routes around lakes; may cross rivers
- `has_road = True` flag on `Cell`; movement speed bonus (TBD multiplier)

### Fences ○
- Auto-generated on shared edges between `terrain_type = 'open'` and any non-open cell
- Not player-configurable — derived from biome layout
- `fenced_edges: set` per `Cell` (which edges carry a fence)
- Cover modifier — see §Combat

### River→Lake Termination Update ○
After lakes are generated, update `RiverGenerator` so the downhill walk terminates when it reaches a lake cell rather than continuing to the map edge.

---

## 3. Streamlit Prototype UI ►
Local-only app for development, testing, and demonstration. **Replaces `MapViewer`** (which is deleted). Grows alongside new Python features — each new capability gets a UI surface as it is implemented.

Run: `streamlit run app.py`

### Tab 1 — Setup
- Map config: biome preset, seed, width/height, min_distance, num_rivers/lakes/roads, weather, season
- Army builder: two sides; each side has one or more regiments (type, size, stats string, law, position)
- **Run** button → generates map + runs simulation → populates Tab 2

### Tab 2 — Results
- Map view: static matplotlib figure (terrain layer default; elevation/cover selectable)
- Per-regiment plots: size over time, morale over time, combat efficiency over time
- Battle outcome: winner, final sizes, turn count
- Export button: download current setup as serialization JSON (§Battle State)

### Constraints
- Static map render — no keyboard shortcuts; matplotlib figure saved to buffer → `st.image()`
- Local only; no auth, no deployment

---

## 4. Weather System ○

| Type | Code | Visibility modifier |
|---|---|---|
| Clear | `clear` | 1.0× |
| Overcast | `overcast` | 0.9× |
| Light Rain | `light_rain` | 0.75× |
| Heavy Rain | `heavy_rain` | 0.6× |
| Fog | `fog` | 0.4× |
| Storm | `storm` | 0.5× |
| Snow | `snow` | 0.65× |

- Static for the full battle; map-wide (no per-zone variation)
- Randomised at battle setup, weighted by season (spring/summer/autumn/winter); weights in `weather.yaml`
- Visibility modifier is a multiplier on each unit's `max_range`
- River and lake cells further amplify fog/rain modifiers (TBD value in `weather.yaml`)

---

## 5. Morale & Retreat ○

### Morale Drop
Losses each Lanchester step cause a morale drop proportional to fractional casualties. Rate constant in `morale.yaml`.

### Morale Break
- Morale below a configurable **break threshold** → regiment exits combat immediately
- Simulates historical reality: units rout before annihilation
- Broken regiment may not re-engage (or requires a recovery period — TBD)
- Threshold and recovery rules in `morale.yaml`

---

## 6. Combat Efficiency ○

### Existing ✓
`get_combat_efficiency(stat_xp, stat_morale, stat_weapon, stat_melee)` → coefficient [0, 1], feeds Lanchester kill-rate equations.

### Range & Distance Accuracy
| Zone | Condition | Accuracy |
|---|---|---|
| Close | `distance ≤ max_range × 0.5` | ~90% (TBD) |
| Effective | `distance ≤ max_range` | ~70% (TBD) |
| Beyond | `distance > max_range` | Exponential decay (TBD) |

Weather visibility modifier applied to `max_range` before zone evaluation.

### Cover Accuracy Penalty (additive, floored at 0)
| Source | Penalty |
|---|---|
| Target in forest | −30% |
| Target in rough/badlands | −15% |
| Fence on target's cell boundary | −15% |
| Fence crossed by LoS ray | −10% |

### Elevation Accuracy Modifier
`dz = attacker_elevation − target_elevation`
`elevation_modifier = clamp(dz / ELEVATION_SCALE, −0.15, +0.15)` — additive with cover.

### Line of Sight
- Ray from attacker position → target position
- Any intersecting cell with `elevation > max(attacker_elev, target_elev)` blocks LoS → no fire
- Fence crossings on the ray feed the cover penalty

### Flanking / Field-of-View ○ (needs design)
Front width → field-of-view angle θ (smaller front = smaller θ). Attacks arriving outside θ are flanking attacks — attacker receives a coef boost (TBD). The front-arc may double as the LoS cone for ranged fire.

Design needed: formula mapping front_width → θ; coef scaling function.

### Full Efficiency Composition
```
base_coef       = get_combat_efficiency(xp, morale, weapon, melee)
effective_range = max_range × weather_visibility_modifier
accuracy        = range_accuracy(distance, effective_range)
accuracy       += elevation_modifier
accuracy       -= cover_penalty  (floor 0)
flanking_mult   = flanking_modifier(attacker_bearing, target_facing, front_width)
final_coef      = base_coef × accuracy × flanking_mult
```

---

## 7. Brigade-Level Targeting ○
Each regiment is assigned a **target regiment** each turn. All (attacker → target) pairs resolve simultaneously via per-pair Lanchester equations.

- Multiple attackers targeting the same regiment: kill rates stack against that regiment
- Each attacker's losses come only from regiment(s) targeting it back
- Assignments set once per turn (player-controlled or AI-assigned)
- Needs design: idle regiments (no target), AI targeting priority, multi-target-one fairness

---

## 8. Movement System ○
Turn-based. Each unit has a `speed` stat → max distance per turn, modified by terrain.

| Terrain | Modifier |
|---|---|
| Open / farmland | 1.0× |
| Forest | 0.6× |
| Hill | 0.7× |
| Rough / badlands | 0.5× |
| Road | 1.3× |
| River (fording) | 0.2× |
| Lake | impassable |

Facing direction TBD — changes cost movement points.

---

## 9. Battle State Serialization ○
Single JSON document. Fully deterministic: same seed + params → identical map and unit state every time. Intended for collaborative play — users share/upload state files to resume the same battle.

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
  "config_overrides": {},
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

All random elements derive from seed. Config overrides allow per-battle tuning without changing global YAML.

---

## 10. Admin Effect Modifier ○
Scalar multiplier applied to one side's overall combat efficiency at run time. Accounts for unmodelled factors (commander quality, supply, events). Applied last, after all other efficiency calculations.

- Per-side at battle setup (not per-regiment); default 1.0; range TBD (e.g. 0.7–1.3)
- **Lowest priority** — implement after all other combat factors

---

## 11. JavaScript Library ○
After Python is stable and fully tested: port simulation logic to a JavaScript library for embedding in a web application.

- Exposes: map generation, battle simulation, state serialization/deserialization
- Web UI (separate repo) consumes the library
- All state round-trips through the serialization format (§9)
- Seed reproduces exact same map
