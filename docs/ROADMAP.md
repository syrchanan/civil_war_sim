# Imperial Generals — Roadmap

> Single source of truth for goals, priorities, and design decisions.
> Status: ✓ done · ► next · ○ backlog · ⏸ parked

---

## What we're optimising for

This project replaces the battle resolution in the admin-run game at
[imperial-generals.connorhanan.com](https://imperial-generals.connorhanan.com/). Today admins invent casualty numbers
with no formula. The goal is a **combat resolver** that admins trust:

- Admins/players **place units interactively**; the engine does **not** handle movement.
- A battle is a sequence of **rounds of fixed game time**. The admin picks the round length and the number of rounds
  based on the battle's scale.
- Each round, the engine resolves combat between the engaged units and reports casualties and morale.
- The Lanchester structure is correct. The work is to **tune it** so each stat and unit-type combination performs
  sensibly, including rock-paper-scissors advantages between unit types.

Two audiences, two languages:

| Audience | Surface | Language |
|---|---|---|
| Developer tuning the math (RL / parameter search) | Plain step API + CLI | Python |
| Players and admins trying it out | Static client-side page on GitHub Pages | TypeScript |

Long term the whole battle system lives in TypeScript, with a **player mode** (fuzzy estimates) and an **admin mode**
(exact seeded result).

Out of scope for now: movement, terrain effects, line of sight, weather. Battles are assumed to be on flat, open ground
with unlimited line of sight. The map pipeline is kept but parked.

---

## Status Summary

### Phase A — Tunable Python core
| # | Item | Status |
|---|---|---|
| A1 | Cross-language seeded RNG | ► |
| A2 | Morale formula fixes | ○ |
| A3 | Per-battle parameter set + fast event log | ○ |
| A4 | Round engine: N regiments per side, `resolve_round` | ○ |
| A5 | Engagements / brigade targeting (pairwise Lanchester) | ○ |
| A6 | Morale break / retreat | ○ |
| A7 | Unit-type matchup matrix | ○ |
| A8 | Battle state serialization (JSON contract) | ○ |
| A9 | Step API + CLI | ○ |
| A10 | Tuning harness: batch runner + matchup stats | ○ |

### Phase B — Playable web client
| # | Item | Status |
|---|---|---|
| B1 | TypeScript port of the round engine (replaces stale v0.2 port) | ○ |
| B2 | Parity fixtures: Python ↔ TS identical results | ○ |
| B3 | GitHub Pages client: place units, set round length, resolve | ○ |
| B4 | Player mode (Monte Carlo estimate ranges) vs admin mode (exact) | ○ |

### Phase C — Later
| Item | Status |
|---|---|
| Admin effect modifier | ○ |
| Weapon range stat + range/distance accuracy | ○ |
| Map in the web client (port of map pipeline) | ○ |
| Terrain effects: elevation, cover, fences, LoS, flanking | ⏸ |
| Weather | ⏸ |
| Lakes, river→lake termination, roads, fences (map stages 4–6) | ⏸ |
| Movement system | ⏸ (admins place units instead) |
| Streamlit prototype UI | ⏸ (first version works; frozen) |

### Done
| Item | Status |
|---|---|
| Admin YAML config (`ConfigLoader`) | ✓ |
| Units: Infantry/Cavalry/Artillery, Army, Position, subtypes | ✓ |
| Regiment combat modes (idle / ranged / melee, Lanchester law dispatch) | ✓ |
| Map pipeline stages 1–3 (Voronoi, biome/elevation, rivers) | ✓ |
| Streamlit prototype v1 (`streamlit run streamlit/app.py`) | ✓ |

---

## Phase A — Tunable Python core

### A1. Cross-language seeded RNG ►
`Simulation` currently draws from the global `np.random`, so battles can't be reproduced.

- Inject an RNG object into the engine; no global randomness anywhere.
- Implement a **small, specified PRNG** (e.g. PCG32 or xoshiro128\*\*) plus an inverse-CDF exponential sampler, in
  pure Python, and later identically in TypeScript. Same seed + same state → **bit-identical** results in both
  languages. (numpy's generators can't be reproduced in JS, so we can't use them for this.)
- Unlocks: fair A/B tuning comparisons, replays, admin/player result agreement, Python↔TS parity tests (B2).

### A2. Morale formula fixes ○
Found in `Simulation.update_morale_losses`; fix these before tuning, or tuning will fit the bugs:
- Rules A–D apply **cumulative** losses on every event, although the docstring specifies casualties *this step*.
  Morale therefore falls faster the longer a fight runs.
- Rules C/D use `time - t` (time *remaining*) as `delta_t` instead of the elapsed step length.
- Confirm the intended semantics, write failing tests, then fix.

### A3. Per-battle parameter set + fast event log ○
- A `BattleParams` object (combat + morale + matchup constants) built from YAML defaults and passed to the engine.
  Overrides go per battle, so an RL/parameter search can run many parameter sets in one process without mutating
  the global config.
- Replace the per-event `pd.concat` (quadratic) with list appends / preallocated arrays; build a DataFrame only on
  request. Rollout speed matters for tuning.

### A4. Round engine ○
- `Battle` holds N regiments per side (`Army`), round number, RNG state, params.
- `resolve_round(duration, engagements)` runs the continuous-time Markov/Lanchester process for `duration` game
  time, then returns a round report (casualties, morale, broken units per regiment).
- Round length is arbitrary and admin-chosen. The engine never assumes a unit of time beyond "game time".

### A5. Engagements / brigade targeting ○
No movement, so the admin supplies the engagements for each round:
```
engagements = [ {attacker: "reg_001", target: "reg_104", mode: "ranged"}, ... ]
```
- All pairs resolve simultaneously via per-pair Lanchester rates.
- Several attackers on one target: their kill rates stack against it.
- A unit's losses come only from units engaging it.
- Open design points: a unit splitting fire across targets; defaults for units with no engagement (idle).

### A6. Morale break / retreat ○
- Morale below a configurable **break threshold** → the regiment is broken and stops fighting for the rest of the round.
- Units rout before annihilation, which is the historical reality.
- Open: whether broken units can recover in later rounds (admin decision vs timed rule). Thresholds live in
  `morale.yaml` / `BattleParams`.

### A7. Unit-type matchup matrix ○
Most remaining design work goes here. Stats (xp / morale / weapon / melee) are complete; types carry the variety.
- A `type × type × mode` multiplier matrix (infantry / cavalry / artillery, later subtypes) applied to the attacker's
  coef against a given target. Rock-paper-scissors style: e.g. cavalry strong vs artillery in melee, weak vs
  infantry at range.
- Config-driven, so it's tunable in A10.
- Open: should subtypes do more than change the matrix (e.g. cavalry charge bonus in the first round of melee)?

### A8. Battle state serialization ○
This is the contract between Python, TypeScript, and the admin site. Fully deterministic: same state + seed → same result.
```json
{
  "version": "1.0",
  "seed": 42,
  "round": 0,
  "params_overrides": {},
  "units": [
    { "id": "reg_001", "side": 0, "type": "infantry", "subtype": null,
      "size": 4000, "stats": "4/4/0/0", "morale_raw": 40.0, "broken": false,
      "position": [102.4, 87.3] }
  ],
  "history": [
    { "round": 1, "duration": 30, "engagements": [], "report": {} }
  ]
}
```
Positions are stored for display only. They don't affect combat until range/terrain effects return.

### A9. Step API + CLI ○
- Plain Python API; no Gymnasium/PettingZoo dependency:
  `Battle.from_state(json)`, `battle.resolve_round(duration, engagements)`, `battle.to_state()`.
- CLI: `python -m imperial_generals resolve state.json --duration 30 --engagements e.json` → new state + report;
  plus a batch mode for tuning runs.

### A10. Tuning harness ○
- Batch runner: many seeded battles across stat / type / size combinations → outcome tables (win rate, casualty
  ratio, rounds-to-break, variance).
- Matchup heatmaps to spot dominant or useless combinations.
- The user's own RL / parameter-search loop sits on top of A9 + A10.

---

## Phase B — Playable web client

### B1. TypeScript port ○
Port the Phase A engine (RNG, params, round engine, engagements, morale, matchups, serialization) to TypeScript. The
existing `typescript/` directory is a stale v0.2 port of the old 1-v-1 `Simulation` and gets replaced.

### B2. Parity fixtures ○
Shared JSON fixtures (state + seed + round inputs → expected report) generated by Python, asserted in both test
suites. The TS port must match the Python engine exactly.

### B3. GitHub Pages client ○
A static client-side page. No backend. Build armies, drop units on a plain field, pick round length, set engagements,
resolve, and see casualties and morale per round. Import/export state JSON.

### B4. Player vs admin mode ○
- **Admin mode**: exact seeded result.
- **Player mode**: fuzzy estimate, e.g. Monte Carlo over N seeds, shown as ranges/quantiles rather than exact
  numbers.

---

## Phase C — Later / parked

### Admin effect modifier ○
Per-side scalar on combat efficiency at battle setup (commander quality, supply, events). Default 1.0; range TBD
(e.g. 0.7–1.3). Applied last. Cheap, and it fits the admin-run game, so it may move up.

### Weapon range + range/distance accuracy ○
Only relevant once position matters. Possible extra weapon stat.
| Zone | Condition | Accuracy |
|---|---|---|
| Close | `distance ≤ max_range × 0.5` | ~90% (TBD) |
| Effective | `distance ≤ max_range` | ~70% (TBD) |
| Beyond | `distance > max_range` | Exponential decay (TBD) |

### Terrain effects ⏸
Kept for when the map returns to combat. Spatial queries use nearest centroid / `get_cell_at_position`, Euclidean
distance, and ray-cast LoS (no neighbour graph).
- **Elevation modifier**: `clamp((attacker_elev − target_elev) / ELEVATION_SCALE, −0.15, +0.15)`, additive.
- **Cover penalty** (additive, floored at 0): target in forest −30%, rough/badlands −15%, fence on target's cell
  boundary −15%, fence crossed by LoS ray −10%.
- **Line of sight**: any cell on the ray with `elevation > max(attacker, target)` blocks fire.
- **Flanking / field of view** (needs design): front width → FOV angle θ; attacks from outside θ get a coef boost.
  Open: formula for θ; boost scaling; does high ground negate a flank?
- **Full composition**:
  ```
  final_coef = base_coef × matchup × accuracy(range, weather) (+ elevation − cover) × flanking × admin_modifier
  ```

### Weather ⏸
Static, map-wide, randomised by season (weights in `weather.yaml`). Multiplies `max_range`: clear 1.0, overcast 0.9,
light rain 0.75, heavy rain 0.6, fog 0.4, storm 0.5, snow 0.65. River/lake cells amplify fog/rain (TBD).

### Map stages 4–6 ⏸
`MapGenerator.generate_map()` runs stages in order, mutating cells in place. Stages 1–3 are done.
- **Lakes**: contiguous low-elevation clusters; `num_lakes`; lakes don't touch; `terrain_type='lake'`, impassable.
  Then update `RiverGenerator` to terminate at lake cells.
- **Roads**: edge-to-edge paths; `num_roads`; multiple roads intersect; route around lakes; `Cell.has_road`.
- **Fences**: auto-generated on edges between `open` and non-open cells; `Cell.fenced_edges`; feeds cover.

Map API:
```python
MapGenerator.from_config(preset='mixed_battlefield')
MapGenerator.from_preset('mixed_battlefield', seed=42, width=200, height=200, min_distance=3)
MapGenerator(MapConfig(...)).generate_map()
```

### Movement ⏸
Superseded by admins placing units. Terrain speed modifiers kept in `movement.yaml` for reference.

### Streamlit prototype ⏸
`streamlit run streamlit/app.py`: Setup + Results pages, map layers, army builder, 1-v-1 sim plots. Frozen. The
Python side is API/CLI-first and the web client replaces it for players.
