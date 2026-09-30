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
| A1 | Cross-language seeded RNG | ✓ |
| A2 | Morale model + time calibration (minutes) | ✓ |
| A3 | Per-battle parameter set + fast event log | ✓ |
| A4 | Round engine: N regiments per side, `resolve_round` | ✓ |
| A5 | Orders / targeting graph (merged into A4) | ✓ |
| A6 | Morale break / retreat: rout captures, wounded | ✓ |
| A7 | Unit-type matchup matrix | ► |
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
| Between-battle morale reconciliation / cooling-off | ○ (needs design) |
| Rally override for broken units | ○ |
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

### A1. Cross-language seeded RNG ✓
`utils/rng.py` (`Rng`) is injected into `Simulation(forces, rng=Rng(seed))`. There is no global randomness in combat.
Same seed + same state → **bit-identical** results in Python and JS. The spec the TS port must follow:
- **Seeding**: a 32-bit seed is expanded to 4 state words with splitmix32.
- **Core**: xoshiro128\*\* (32-bit ops only: `Math.imul`, `>>> 0`; no BigInt).
- **`random()`**: 53-bit float from two draws: `((hi >>> 5) * 2^26 + (lo >>> 6)) / 2^53`.
- **`exponential(rate)`**: `-log(1 - random()) / rate`, where `log` is `utils/fdlibm.py`, a pure-arithmetic fdlibm
  port. The Windows CRT `log` differs from V8 in the last bit (1 in 3 samples in testing). The port matched V8's
  `Math.log` on 300k random inputs with 0 mismatches.
- **`state` / `Rng.from_state`**: 4 uint32 words, for serialization (A8).
- Test goldens in `test_utils_rng.py` / `test_utils_fdlibm.py` come from JS/V8 and double as B2 parity fixtures.

### A2. Morale model + time calibration ✓
The old rules A–D are replaced. Measured before the redesign, they barely moved morale: a 4,000-man regiment
annihilated lost 0.7 of 60 raw morale, so every battle ended in annihilation. They also used cumulative losses on
every event, depended on unit size, and used time *remaining* in the round as `delta_t`. Bugs fixed separately
(`5285f24`): one-sided fire recorded no losses; negative weapon codes couldn't be entered.

**Game time is in minutes.** One round is about 60–120 min; a typical engagement (one day) is 3–5 rounds. Longer
battles are separate engagements, since armies redeploy overnight.

**Break point from veterancy + starting morale.** Each unit has a loss fraction at which pure attrition breaks it:
```
w       = α·(xp − 1)/9 + (1 − α)·(morale_stat − 1)/9        # α = weight of experience (default 0.5)
f_break = 0.15 + 0.60 · w^γ                                 # γ = 1.5 → 1/1: 15%, 5/5: ~33%, 10/10: 75%
```
Computed once at battle start from starting stats. Live morale is the **budget** being spent:
`budget = M₀ − M_break`. Same thresholds for every era for now; era-specific later.

**Per casualty on unit i** (N₀ = starting size, f = fraction lost so far):
```
ΔM = −a · (N₀/N_ref)^β · (1 + k·f) · (1 + c·S) · (1 + ψ·[not firing back]) / N₀
a  = budget / (f_break + k·f_break²/2)       # pure attrition (β=c=ψ=d=0) breaks exactly at f_break
```

| Term | Covers | "Off" |
|---|---|---|
| `(N₀/N_ref)^β` | Unit size. β < 0: big units absorb the same % better | β = 0 (default) |
| `(1 + k·f)` | Morale falls faster as the unit bleeds | k = 0 |
| `S`, shock | Per unit: +1/N₀ per loss, fades with half-life H (needs a fdlibm `exp` port) | c = 0 |
| `ψ` | Taking fire while idle or unable to reply | ψ = 0 |
| `dM/dt = −d` while engaged | Wear over time in combat, replacing a separate fatigue system; flat when idle | d = 0 |
| `+b` per fraction of enemy killed | Success lifts morale, **capped at starting morale M₀** | b = 0 |

These depend only on game time and per-unit state, so results don't depend on how the day is cut into rounds.
Tests should check this, and that the same % lost has the same effect at any size when β = 0.

**Calibration targets** (from Napoleonic / Civil War records; refine against Fox 1889, Livermore 1900, Bodart 1916):
- Day totals: loser **25–35%**, winner **12–25%**.
- Break points: morale/xp 5 → **25–35%**; 8–10 → 40–60%; 1–3 → 10–20%. Exceptional stands (1st Minnesota ~82%)
  are tail events.
- Even, sustained firefight: **5–10% per hour** per side. A global kill-rate scale in `combat.yaml` sets this;
  today a 4,000 v 4,000 fight ends in about 1 time unit.

**Built:**
- `utils/fdlibm.py` `exp`: 0 mismatches vs V8 on 300k inputs.
- `battles/morale.py`: `MoraleParams`, `MoraleState`, `break_fraction`.
- `Simulation(..., morale_params=)`: time in minutes; `ranged_kill_rate` / `melee_kill_rate` in `combat.yaml`; the
  battle ends when a side breaks or is wiped out; no event can land past the time limit.

**First calibration probe** (defaults, ranged fire, 200 seeds, one 450-min day):

| Matchup | Loser | Winner | Breaks after |
|---|---|---|---|
| Even 5/5 smoothbore | 28% | 26% | ~4.3 h |
| Even 5/5 rifled | 29% | 27% | ~3 h |
| Veteran 8/8 v green 2/3 | 17% | 12% | ~2 h |
| Rifled v smoothbore | 28% | 18% | ~2.7 h |
| 1000 v 2000, even stats | 27% | 6% | ~1.8 h |
| Elite 10/10 v 10/10 | 65% | 58% | 26% of fights still undecided at nightfall |

Open for tuning (A10):
- In even fights the winner bleeds nearly as much as the loser. Historically the gap comes largely from rout losses
  (pursuit, prisoners), which aren't modelled yet (see A6).
- `melee_kill_rate` is a placeholder.

### A3. Per-battle parameter set + fast event log ✓
**Built** (`imperial_generals/params.py`):
- `BattleParams(combat=CombatParams(), morale=MoraleParams())`: frozen, validated, defaults from YAML.
- `with_overrides({'combat': {...}, 'morale': {...}})`: nested; a partial `weapon_multipliers` merges into the
  defaults; unknown keys raise. `to_dict` / `from_dict` are JSON-safe for A8.
- `Simulation(forces, rng, params=)`. Overrides never touch the global config or other regiments.
- `CombatParams.efficiency` / `unit_coef` is the single implementation of the effectiveness formula
  (`get_combat_efficiency` and `Regiment.coef` delegate to it).
- Matchup constants (A7) will join as a third section.

**Speed**: 7.5k → 42k casualty events/s; a 4,000 v 4,000 day went from 293 ms to 52 ms. Every change is exact:
- Per-event rows appended to a list, one DataFrame per run; `record_history=False` skips rows for rollouts.
- Coefficients come from the params object; before, each casualty rebuilt and re-parsed a stats string and
  re-read the config.
- The morale → stat lookup is arithmetic instead of a numpy scan, and is recomputed only when the stat changes.
- The debug log line is only formatted when debug logging is on.
- Competing clocks are sampled directly: one Exp(r₀ + r₁) draw for *when*, plus one uniform for *who*
  (P = rᵢ / (r₀ + r₁)), the same distribution as two separate clocks. Who is hit no longer depends on `log`.

Next speed lever: run battles across CPU cores in the A10 batch runner. The remaining cost is spread thinly
across Python overhead.

### A4 + A5. Round engine with orders (targeting graph) ✓
A5 is merged in: the round engine can't run without per-regiment orders.

`Battle` holds N regiments per side, the RNG, params, game time, round number and each unit's morale (which
carries across rounds). The admin/player enters every unit (what it is, its stats) and, each round, one **order**
per regiment:
```python
orders = {"reg_001": {"target": "reg_104", "mode": "ranged"},
          "reg_002": {"target": "reg_104", "mode": "melee"},
          "reg_104": {"target": "reg_001", "mode": "ranged"},
          "reg_105": {"mode": "idle"}}           # units left out of orders are idle
report = battle.resolve_round(duration=90, orders=orders)
```
- **The orders form a targeting graph.** Each unit points at most one target (one outgoing arrow) and can be
  attacked by any number of units (incoming arrows): `target[a] = b`, with "who is attacking b" derived.
- **Ranged fire is one-way along the arrow.** B only fires back if B's own order targets A. Several attackers on
  one target stack their kill rates. A unit's losses come only from arrows pointing at it.
- **Melee is mutual and forcing** (for now): a melee order creates a two-way contact, and the defender fights back
  in melee. A unit in any contact fights only in melee; its ranged order waits. Once movement exists, contact only
  forms if the charging unit actually reaches its target.
- **Melee with several contacts: exposure is the whole front, fighting strength is divided.** Each attacker hits
  the defender's full front, while a unit's own fighters are split across its contacts in proportion to their
  fronts. A surrounded unit takes more damage and deals the same total, spread thinner. One-on-one it reduces to
  the old front × front rule.
  ```
  melee  a→v:  melee_kill_rate · coef_a(melee) · front_a · share_a(v) · front_v,   share_a(v) = front_v / Σ fronts of a's contacts
  ranged a→v:  ranged_kill_rate · coef_a(ranged) · size_a
  ```
- **A target breaks or is wiped out mid-round** → its attackers go idle for the rest of the round; the admin
  re-orders next round. Later, a player option per unit: pursue / idle / engage closest.
- **Broken units can be targeted** (pursued) but can't fight back or act. Range will matter once positions do.
- One event loop over all arrows: `dt ~ Exp(Σ rates)`, then pick the arrow by a uniform draw weighted by rate.
  Arrows are ordered by (target, attacker) in unit order, so a 1-v-1 battle draws exactly like `Simulation`.
- A unit is **engaged** (morale drains) if it has an active arrow in or out; it's **helpless** (morale cost ×
  (1 + ψ)) when hit with no active fire of its own.
- `battle.engagements(orders)` previews the arrows and their current rates without rolling any dice (for UIs and
  tests).
- Round length is admin-chosen, in minutes (typically 60–120).

**Built** (`battles/battle.py`):
- `Battle(units={'id': (side, Regiment)}, rng, params)` with `Order`, `Engagement`, `RoundReport`, `UnitReport`.
- `RoundReport` gives per-unit losses, inflicted, size, morale, broken and `broke_at`; `record_events=True` adds a
  per-casualty event log.
- Bit-identical to `Simulation` in a 1-v-1 ranged fight (tested over 5 seeds). `Simulation` stays as the legacy
  1-v-1 used by Streamlit and `main.py`, and can be retired once nothing uses it.
- A break from the in-combat drain alone is detected at the next casualty or at the round's end. The exact moment
  between events isn't solved for.

**Speed**, all exact: the arrow structure is rebuilt only when a unit breaks or is wiped out, and rates are
recomputed per event from it; coefficients are memoised per (stats, mode); the shock-decay `exp` is computed once
per event (every unit shares `dt` and half-life); the morale lookup reads its config once. 20 v 20 went from
2.2k to ≥4.6k events/s (a 4-round 20 v 20 battle takes ~1.7 s); 1 v 1 about 28k/s. The remaining cost is O(units)
Python work per event (advancing and syncing every engaged unit's morale). Next levers: parallel batches (A10),
and lazy morale updates (bring a unit up to date only when it's touched). Lazy updates would change floating-point
rounding slightly, so they'd need a parity decision first.

### A6. Morale break / retreat ✓
- Morale reaches the break line (budget spent; see A2 `f_break`) → the regiment is broken and stops fighting.
- Units rout before annihilation, which is the historical reality.
- **No recovery within a battle.** A broken unit stays broken for all remaining rounds of that engagement.
- Later (Phase C): the user can force a broken unit back into the fight, at a penalty: lower effectiveness and
  higher casualty rate.
- Thresholds live in `morale.yaml` / `BattleParams`.
- Break detection is done (A2). What's left for the round engine: the broken unit leaves its engagements, and other
  units' targets update.
- **Rout losses (captured)**: when a unit breaks it takes a one-off loss of a tunable fraction of its remaining men
  as prisoners, increased if enemy cavalry is engaged with it. This is most of why losers historically lost more
  than winners (the probe shows even-fight winners bleeding almost as much as losers without it).
- **Wounded recovered after the battle**: once the engagement ends, a semi-random share of each unit's casualties
  returns as wounded who recover. Seeded like everything else (drawn from the battle's `Rng`), with the share
  tunable. Captured men do not return. Reports should split casualties into killed, wounded (returned) and captured.
- **Wounded can be captured too**: some wounded are taken by whoever holds the field at the end of the battle.
  Others are "walking wounded" who leave with their unit when it breaks.
- **Pursuit**: broken units can be targeted in later rounds (A4). Range will matter here once positions do.

**Built** (defaults in `config/aftermath.yaml`, tunable as `BattleParams.aftermath`):
- **At the break**: the unit loses `rout_capture_share` (10%) of its remaining men as prisoners, ×2 if enemy
  cavalry is attacking it at that moment. `UnitReport.captured` and `RoundReport.prisoners` report it; the
  running total is `Battle.prisoners`.
- **`battle.finish(field_held_by='auto')`**: `'auto'` means the side still standing when the other is entirely
  broken or wiped out, else nobody. It returns a `BattleResult` with per-unit `UnitOutcome`:
  - hits split into killed (22%) and wounded;
  - on the losing side, walking wounded (40%) leave with their unit, and 60% of the rest are captured by the
    field holder;
  - 40% of uncaptured wounded return, and are added back to strength.

  The battle is closed afterwards.
- Every share is `mean × (1 ± share_spread)` from one uniform draw of the battle's `Rng`, rounded half up.

**Probe** (one day, 5 × 90 min, 1000 v 1000, 200 seeds, no pursuit of broken units):

| Matchup | Loser total (k + w + captured) | Loser prisoners | Winner total |
|---|---|---|---|
| Even 5/5 | 35% | 15% | 26% |
| Rifled v smoothbore | 35% | 15% | 18% |
| Veteran 8/8 v green 2/3 | 25% | 13% | 12% |
| Dragoons v infantry | 39% | 19% | 26% |

Even fights now have a loser/winner gap, and it comes from prisoners. Losers sit at the top of the 25–35% band,
and prisoners are about 40% of loser casualties, which may be high. Tune in A10. Pursuing broken units for hours
(admin choice) pushes loser totals past 50%.

### A7. Unit-type matchup matrix ►
Most remaining design work goes here. Stats (xp / morale / weapon / melee) are complete; types carry the variety.
- A `type × type × mode` multiplier matrix (infantry / cavalry / artillery, later subtypes) applied to the attacker's
  coef against a given target. Rock-paper-scissors style: e.g. cavalry strong vs artillery in melee, weak vs
  infantry at range.
- Config-driven, so it's tunable in A10.
- Open: should subtypes do more than change the matrix (e.g. cavalry charge bonus in the first round of melee)?
- **Watch melee effectiveness closely.** Two kinds of unit:
  - **Melee-only** (pikes, light cavalry): effectiveness is 0 until they close to melee, so at range they can only
    take fire (and pay the helplessness morale cost).
  - **Dual-mode** (line infantry, dragoons): fire at range, and also fight in melee at a penalty that should
    differ by type (dragoons dismount or charge; line infantry uses the bayonet).

  Today that's `stats[3]` (melee-only flag) plus one global `melee_penalty_factor`, and `melee_kill_rate` is a
  placeholder. The matchup matrix should carry per-type melee strength, and A10 should report melee outcomes
  separately.

**Decisions** (2026-09-30):
- **Ranged strength = the unit's arms. Melee strength = its subtype. Matchups = situational advantage.**
  - Ranged: weapon stat as today. The stats melee-only flag (`stats[3]`) still decides whether a unit can fire at
    all. It stays because players choose each unit's arms; types and subtypes are approximations.
  - Melee: a per-subtype **melee rating** replaces the firearm multiplier and the global melee penalty in the round
    engine. Fixes a bug where pikes (weapon −2 → 0.2×) fought hand-to-hand at 20% strength. The legacy 1-v-1
    `Simulation` keeps the old penalty.
  - Matchups: a **type table** (inf / cav / art × target type, per mode) plus **subtype overrides** where a subtype
    really differs. Lookup, most specific first: attacker subtype + target subtype → attacker subtype + target type
    → attacker subtype + any target → attacker type + target subtype → type table.
- **Artillery fires per manned gun**: `coef × effective_guns × artillery_kill_rate_per_gun × matchup`. Losing crew
  below 7 per gun silences guns. Range bands (canister v round shot) come with positions.
- Plain `Regiment` (no type) counts as infantry with the default melee rating.

First-draft numbers (to tune; artillery's melee weakness lives in its rating, so its melee row is neutral):

| Attacker → target | Infantry | Cavalry | Artillery |
|---|---|---|---|
| Infantry, ranged | 1.0 | 1.2 | 0.8 |
| Infantry, melee | 1.0 | 0.7 (pikes 2.0) | 1.2 |
| Cavalry, ranged | 0.6 (dragoons 0.9) | 0.6 (dragoons 0.9) | 0.5 (dragoons 0.75) |
| Cavalry, melee | 1.5 | 1.0 | 2.0 |
| Artillery, ranged | 1.0 | 1.2 | 0.6 |
| Artillery, melee | 1.0 | 1.0 | 1.0 |

Melee ratings (same scale as weapon multipliers; line infantry 0.7 matches the old smoothbore × 0.7 penalty):
line 0.7, light 0.6, marine 0.8, pikes 1.2, irregulars 0.5; light cav 1.0, heavy cav 1.4, dragoons 0.9;
battery 0.25, horse battery 0.3, siege battery 0.2; default 0.7.

Still open: a cavalry charge bonus (extra shock at the start of a melee), and guns captured when a battery is
overrun.

**Built**:
- `config/matchups.yaml` → `BattleParams.matchups` (`MatchupParams`: type tables, validated subtype overrides,
  melee ratings; partial overrides deep-merge).
- `CombatParams.melee_efficiency` and `artillery_kill_rate_per_gun` (placeholder 0.12 ≈ 30 muskets per gun).
- The round engine applies matchups per arrow, uses melee ratings, and fires artillery per manned gun.

**First probe** (one 90-min round, 1000 men or a 6-gun / 120-man battery, 200 seeds):

| Round | Attacker lost | Defender lost | |
|---|---|---|---|
| Line v line firefight | 11% | 11% | ✓ |
| Rifles v muskets | 11% | 16% | ✓ |
| Battery v line firefight | 33%, breaks | 0.7% | ✗ artillery hopeless without range |
| Heavy cav charges line | 6% | 40%, breaks | ✗ too strong (4.3× stacked edge) |
| Heavy cav charges pikes | 33%, breaks 92% | 24% | ✓ |
| Light cav charges battery | 0.4% | 40%, breaks | ✓ |
| Heavy v light cav | 19% | 42%, breaks | ✓ |

**Decided and built** (2026-09-30, after that probe):
- **Standard battery = 8 guns × 9 crew (72)** (`config/artillery.yaml`, `ArtilleryBattery.standard`); players adjust
  from there. A gun needs 7 crew, and crew pool across guns: manned guns = min(guns, crew // 7).
- **Ammo is part of the battery's order**, fixed for the round; the engine never switches ammo by itself.
  `{'mode': 'ranged', 'target': ..., 'ammo': 'canister'}`. Per-gun rates: round shot 0.15, shell 0.25, canister
  0.45 (≈40 / 60 / 110 muskets); round shot if unspecified. Until positions exist, the admin judges whether the
  range suits the ammo.
- **Infantry fire on batteries cut to 0.1** (cavalry 0.1, dragoons 0.15): dispersed crews, beyond effective musket
  range. The way to silence guns is to charge them.
- **Cavalry charge factor** (cavalry charging infantry with its own melee order), recomputed per event:
  `(cav/inf numbers)^1 × (1 + 1.5 × (1 − steadiness))`, clamped to [0.25, 3], where steadiness blends the
  infantry's resolve, veterancy and recent shock. The static cavalry → infantry melee value is 0.5 and
  infantry → cavalry 1.0. Cohesive infantry repels a charge; outnumbered cavalry loses; shaken or green infantry
  is ridden down.

**Probe after** (one 90-min round, 200 seeds):

| Round | Attacker lost | Defender lost |
|---|---|---|
| Battery (round shot) v line firefight | 16% (breaks 3%) | 3% |
| Battery (canister) v line firefight | 15% | 10% |
| Line charges battery | 0.6% | 34%, breaks |
| 500 heavy cav charge 1000 line | 34%, breaks | 9% |
| 1000 heavy cav charge 1000 line | 13% | 40%, breaks |
| 1000 heavy cav charge 1000 veteran line | 34%, breaks 62% | 47%, breaks 38% |
| 500 heavy cav charge line after 60 min of rifle fire | 20% | 26%, breaks 90% |
| 500 light cav charge 1000 line | 34%, breaks | 6% |
| 500 heavy cav charge 1000 pikes | 32%, breaks | 2% |

Open:
- Infantry fire on a battery is 0.1 whatever ammo the battery uses. A battery firing canister is within musket
  range, so it could arguably be exposed more. Revisit when ranges exist, or tie it to the ordered ammo.
- Heavy cavalry at even numbers still beats fresh average line infantry.
- Guns captured when a battery is overrun.

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

### Between-battle morale reconciliation ○ (needs design)
After an engagement ends, a unit's morale must be settled before its next battle. For example, recovery toward
baseline over rest days, and a "cooling-off period" so back-to-back battles are harder. Open: recovery rate, whether
winners and losers recover differently, and how this is stored in the game's unit records.

### Rally override for broken units ○
The user can force a broken unit back into combat. It fights at reduced effectiveness and takes more casualties
(penalties TBD, config-driven).

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
- **Before porting the map to TS**: `voronoi.py` still uses global `np.random`, and `river.py` uses `random.Random`. Move both to `Rng`.

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
