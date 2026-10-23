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
| A7 | Unit-type matchup matrix | ✓ |
| A8 | Battle state serialization (JSON contract) | ✓ |
| A9 | Setup file + step API + CLI | ✓ |
| A10 | Tuning harness: batch runner + matchup stats | ✓ |
| A11 | Player-made validation scenarios (expectations + feedback) | ✓ |
| A13 | Tuning pass on the A10 findings | ⏸ (parked 2026-10-23; larger pass later) |
| A12 | Field holder from battle performance (`finish` 'auto') | ✓ |

### Phase B — Playable web client
| # | Item | Status |
|---|---|---|
| B1 | TypeScript port of the round engine (replaces stale v0.2 port) | ► |
| B2 | Parity fixtures: Python ↔ TS identical results | ► |
| B3 | GitHub Pages client: place units, set round length, resolve | ○ |
| B4 | Player mode (Monte Carlo estimate ranges) vs admin mode (exact) | ○ |

### Phase C — Later
| Item | Status |
|---|---|
| Between-battle morale reconciliation / cooling-off | ○ (needs design) |
| Rally override for broken units | ○ |
| Admin effect modifier | ○ |
| Commander rating: historical general by performance | ○ (needs design) |
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

**Stat weights raised (2026-10-01)**: effectiveness is computed from each unit's stats (weapon × XP × live morale),
but the old weights made an elite 10/10 unit only ~1.5× as effective as a green 1/1 unit with the same weapon.
Veterancy paid off almost entirely through staying power. The XP boost per level went 4% → 8% and morale
2% → 4%, so elite is now ~2.1× green (fire and melee). The kill rates were scaled ×1.095 so an average 5/5 unit's
casualty rates didn't move (the even-fight probe is unchanged); only the spread widened. A veteran 8/8 beating a
green 2/3 now costs the winner 10% instead of 12%. The exact weights are for A10 to fit.

Open for tuning (A10):
- In even fights the winner bleeds nearly as much as the loser. Historically the gap comes largely from rout losses
  (pursuit, prisoners), which aren't modelled yet (see A6).
- `melee_kill_rate` is a placeholder.
- **Morale gains pin nearly broken units just above the break line** (found 2026-10-01 in the A9 example). In a long
  mutual firefight or melee, each casualty a unit inflicts tops its morale back up (`gain_weight` 0.5), so two
  worn units prop each other up. In the old example, 200 seeds: 76 of 400 unit-runs broke; with `gain_weight` 0,
  200 did. The median unbroken unit ended with 8% of its morale left. Tune in A10.

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

### A7. Unit-type matchup matrix ✓
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

- **Guns captured**: a battery **overrun** (crew reaches 0: all killed, wounded or captured) loses every remaining
  gun. A battery that **breaks** takes the usual rout prisoners, then escapes with only the guns its remaining crew
  can man (`min(guns, crew // 7)`); the rest are captured. Reported as `UnitReport.guns_lost`,
  `RoundReport.guns_captured` / `Battle.guns_captured` (per side) and `BattleResult.guns_captured`.

Deferred until range exists (decided 2026-09-30):
- Infantry fire on a battery is 0.1 whatever ammo the battery uses. A battery firing canister is within musket
  range, so it could arguably be exposed more.
- Whether ammo suits the range (canister is a close-range load).

Watch in tuning: heavy cavalry at even numbers still beats fresh average line infantry.

### A8. Battle state serialization ✓
The contract between Python, TypeScript and the game site: `battle.to_json()` / `Battle.from_json(text)`
(`battles/state.py`). **Resolving the next round of a reloaded battle gives exactly the result it would have had
without saving** (tested mid-battle, including `finish()`).

- `format: "imperial-generals-battle"`, `version: 1`. Loading any other format or version raises.
- `meta`: free-form battle details (name, date, location, notes), round-tripped untouched.
- `seed` (informational) and `rng_state` (the 4 generator words: what actually matters).
- `params`: the **full** parameter set, not just overrides, so a later config change can't alter a saved battle.
- `time`, `round`, `finished`, `prisoners` and `guns_captured` per side.
- `units` (in unit order, which breaks ties): id, **name** (defaults to the id), side, type/subtype, size and
  initial size, stats and initial stats, front size, guns, raw morale, combat mode, position, live morale
  (resolve, shock, lost, broken), losses, inflicted, captured, guns lost, and free-form **meta** (player, army
  ids, ...).
- `history`: every round's report, now including the **orders given**, engagements, per-unit results, prisoners,
  guns and (if recorded) events.

Units are built with names and meta via the dict form:
`Battle({'reg_001': {'side': 0, 'regiment': ..., 'name': '1st Minnesota', 'meta': {...}}}, meta={...})`.
Reference file: `test_cases/battle_state_v2.json` (version 2 since A13: contacts, charges, charge params). A test
checks it round-trips unchanged, so format changes are
deliberate; it's also the starting fixture for the TypeScript parity tests (B2). Positions are stored but don't
affect combat until range/terrain effects return.

### A9. Setup file + step API + CLI ✓
**Setup file** (`battles/setup.py`, `Battle.from_setup`): how a new battle is described by hand. The A8 state file
is for saving and resuming; it holds RNG words and live morale that nobody should write by hand.
- **YAML or JSON** (`load_setup_file`; JSON if the name ends in `.json`). YAML is easier to write by hand, and its
  dates stay as text so the state stays plain JSON.
- Keys: `meta` (free-form), `seed` (optional; picked at random and recorded if left out), `sides` (optional names,
  e.g. `[Union, Confederate]`; units can then use them as their side), `params` (overrides on the defaults), and
  `units`. Each unit has `id` and/or `name` (each defaults to the other), `side`, `type` (`inf` / `cav` / `art`, or
  left out for a generic unit), `subtype`, `size`, `stats` (as in the game), and optional `guns`, `front_size` and
  `meta`. Artillery without size and guns is a standard battery.
- **Validation reports every problem at once, each with where it is**, e.g.
  `Unit 3 (cs_cav): subtype 'cuirassiers' is not valid for cavalry. Must be one of: [...]`. Unknown keys are errors,
  so typos don't pass silently.
- **Scenario** = setup + `rounds` (each a `duration` and `orders`) + optional `finish: true`. It replays a whole
  battle from one file. Example: `scenarios/example_ridge.yaml`.

**Step API** (`imperial_generals/api.py`): plain functions on JSON-safe dicts, for callers that keep the battle as
data (CLI, game site, notebooks). The input state is never modified, and chained steps give exactly the results of
one `Battle`.
`new_battle(setup, seed=)`, `step(state, duration, orders, record_events=) → (state, report)`,
`preview(state, orders) → engagements`, `finish(state, field_held_by=) → (state, result)`,
`run_scenario(scenario, seed=) → (state, reports, result)`. For fast rollouts (tuning, RL), use `Battle` directly
and skip the (de)serialisation.

**CLI** (`python -m imperial_generals`): `new`, `preview`, `resolve`, `finish`, `show`, `run`. `resolve` and
`finish` update the state file in place unless `-o` is given. `--json` prints machine-readable output instead of
tables. Problems exit with code 2 and a readable message. Batch runs across seeds are A10.

**Reports**: `run` prints an **order of battle** (per side: units, men by type, guns, men-weighted average
experience and morale), each round's table, the final per-unit table (columns reconcile:
`Final = Started - Killed - Wounded - Prisoners + Returned`, wounded taken prisoner counted once, as prisoners),
and a **side summary**: casualties, wounded returned, share lost for good, hits taken and inflicted, exchange ratio
(enemy men hit per own man hit), prisoners and guns lost and taken, and units broken. `api.order_of_battle(state)`
and `api.side_summary(state)` return the same as dicts for the site.

**Scripted orders meet random breaks**: in a scenario run, an order for a unit that has broken or been wiped out,
or aimed at a wiped-out target, is skipped and listed in the round's `skipped_orders`, instead of failing the run
on some seeds. `finish` takes `true` / `auto`, `none`, `0` / `1` or a side name. The interactive `step` / `resolve`
stay strict.

**Also changed**:
- `Battle.finish()` stores its result as `battle.result`, and the state file gains a `result` key (null until
  finished). Files without the key still load.
- Orders with unknown keys (`{'aim': ...}`) now raise a clear error naming the unit.

### A10. Tuning harness ✓
**Built** (`imperial_generals/tuning.py`):
- `run_batch(scenario, seeds, seed_start=, overrides=, workers=)` runs a scenario once per seed, spread over
  worker processes. Results are identical for any number of workers, since each seed is independent. Every run
  is finished: with the scenario's `finish` if it names one, else 'auto'. `batch.runs` has one row per seed
  (field holder, end time, and per side every side-summary figure plus the first break); `batch.unit_runs` has
  one row per seed per unit (hits, captured, inflicted, broken, broke at).
- `summarize(batch)`: field-holder shares; per side the spread (mean, p10 / p50 / p90) of losses and exchange
  ratio, units out, how often and when the first unit breaks, prisoners and guns taken; per unit the break rate,
  median break time, hit share and inflicted.
- `matchup_grid(spec, seeds=, workers=, overrides=)`: every unit in a grid file attacks every unit, one on one.
  Each has an `attack` order and a `defend` reply (ranged / melee / idle, or `{mode, ammo}`). Cells give attacker
  and defender win rates, **advantage** (attacker wins − defender wins), break rates, hit shares and exchange
  ratio. `plot_matchups` saves a heatmap (diverging red–gray–blue for advantage). Starter grid:
  `scenarios/matchups_basic.yaml`.
- `run_scenario` / `battle_from_setup` take `overrides=` on top of the scenario's own params, so a parameter
  search can score candidates: `summarize(run_batch(scenario, 500, overrides=candidate))`.
- CLI: `batch SCENARIO --seeds 500 [--params over.yaml] [--csv runs.csv] [--units-csv units.csv] [--json]` and
  `matchups GRID [--seeds] [--plot grid.png] [--metric ...] [--csv] [--json]`. Both use every CPU by default.

**Speed** (32 cores): 1,000 seeds of the 7-unit example in 13 s; the 8 × 8 starter grid (12,800 battles) in 21 s.

**First findings** (starter grid: 1000 infantry / 500 cavalry / standard battery, all 5/5, one 90-min round,
200 seeds; example: 1,000 seeds). These are the A13 tuning targets:
1. **Pikes win everything, even attacked by a firing line** (+100% against all infantry). A melee order is
   instant contact (no approach under fire until movement exists), and the pikes' melee reply turns any ranged
   attack into a melee they win (rating 1.2 v 0.7). Melee needs an approach cost or slower rates.
2. **Melee decides in minutes; firefights don't decide in 90 min.** Infantry v infantry never breaks within a
   round (consistent with A2's ~3–4 h firefights); every melee cell ends at ±100%.
3. **Dragoons never break anything** (0% in their row) and lose to all infantry at range.
4. **Cavalry charging infantry always loses at 500 v 1000** (by design: outnumbered cavalry loses). An
   equal-numbers grid is needed before judging the charge factor.
5. **Artillery**: a battery attacking infantry is roughly even (−2% to −24%) and hits ~3–5 men per man lost;
   battery v battery is even.
6. **Example scenario**: the Union never holds the field (A12 would change that); Battery B breaks in every
   seed (median 50 min) under counter-battery shell. 1st Minnesota breaks only 14% of the time with 31% hit,
   which may be the morale-gain pinning noted under A2.

### A13. Tuning pass ⏸
**Harness facets** (2026-10-01): `matchups` runs several grids. Each answers a different question:
- **ranged**: everyone fires. Melee-only units (stats flag `x/x/x/1`, not the subtype) inflict nothing.
- **melee**: everyone fights hand to hand. Both sides hold melee orders, so they meet head on.
- **charge**: the attacker charges while the defender stands and fires.
- **artillery**: batteries at long range, where only another battery can reply. Fire on anything else goes
  unreturned.
- **orders**: each unit's own `attack` / `defend` from the file.

The tables add the defender's hit share.

**Melee and charges (decided 2026-10-01, built)**:
- **Contact width**: melee casualties on v = `melee_kill_rate × coef × min(attacker's men facing v, v's front)
  × matchup`. Losses per hour no longer grow with unit size: before, 250 v 250 lost 8%/h and 2000 v 2000 lost 63%/h.
  A surrounded unit still takes more and deals the same total. `melee_kill_rate` 0.01564: line in contact hits
  2.5× its firing rate (~19%/h each in full contact).
- **A melee order on a unit not in contact is a charge** (`config/charge.yaml`, `BattleParams.charge`):
  - **Approach**: 5 min (infantry, artillery) or 2 min (cavalry). The target fires at 3× its normal rate,
    batteries with canister, split if several units charge it. The charger can't fire. A target that is itself
    charging, locked in melee, or melee-only can't fire.
  - **Contact test**: `x = ln(men ratio) + 3 × (steadiness difference) + shock bonus`, where steadiness blends
    resolve, veterancy and shock. The defender breaks with `σ((x − 1)/0.5)` and the charge falters with
    `σ((−x − 0.5)/0.5)`; otherwise it goes home. An even fresh charge gives ~12% / 27% / 61%. Losses on the
    approach lower the charger's steadiness.
  - **Outcomes**: a faltered charger stands down for the round and loses 15% of its morale budget. A defender
    broken by the charge routs (prisoners ×2 if cavalry charged). A battery broken by a charge is overrun and
    loses every gun.
  - **Shock bonuses** add up from type and subtype entries: cavalry v infantry +0.5 (heavy +0.3 more),
    cavalry v pikes −2, cavalry v artillery +1, infantry v artillery +0.5.
  - Units charging each other **meet head on** (contact, no test). **Charging a broken unit is pursuit**:
    contact at once.
- **Contact persists** across rounds while either unit keeps a melee order on the other. It ends when a unit
  breaks. Saved as `contacts` in the state file (version 2). `RoundReport.charges` records each charge with its
  outcome and odds, and the CLI prints them.
- The **cavalry charge factor is gone**; cavalry's edge over infantry is now shock in the contact test, matching
  the user's view that cavalry v infantry is a short shock action, not hours of fighting. **Pikes'** melee
  rating went 1.2 → 1.0.

**Grids after** (8 kinds, one 90-min round, 200 seeds):
- **Melee head on**: no longer all ±100%. Line v line loses ~22% each and nobody breaks. Pikes still win v
  musket infantry (+93%), which is plausible once in contact.
- **Charge into standing fire**:
  - Line charging line +6%; charging rifles −46% (closing fire, then a faltered charger left standing under
    fire).
  - Pikes charging line +50%, charging rifles −5%.
  - Cavalry charging formed infantry fails (−31% to −68%) and never breaks pikes; it takes an unsupported
    battery every time.
- **Artillery at long range**: 90 min of unreturned shell hits a 1000-man unit 6% and never breaks it.
- **Example**: the Confederate assault fails. The 8th and 10th Alabama break in 94–96% of seeds; the Union trades
  1.6:1.

**Since then** (2026-10-01):
- **A charge that falters falls back** beyond musket range for the rest of the round: only artillery can still
  reach it.
- **Grid round lengths can differ per grid**: `rounds: {default: [90], charge: [30]}`. A charge is a short
  action. The charge grid also reports how each charge ended (went home / faltered / broke the defender).
  - Infantry charging line: 48 / 46 / 6.
  - Charging rifles: 42 / 52 / 6.
  - Cavalry charging pikes: falters 95%.
  - Infantry charging stationary cavalry at 2:1 numbers: breaks it 36%.
  - Every infantry kind charges identically: the test sees only numbers, steadiness and the type bonus.
- **Artillery at long range** (6% of a unit hit in 90 min, unreturned) and **melee pace** (~19%/h): about
  right for now, tune later.

**Morale investigation** (2026-10-01; firefights of 1000-man line, 300 seeds):
- **Firefight pace on target**: an even 5/5 firefight costs 7.1% in the first hour (target 5–10%).
- **Break points on target** for a unit losing a firefight against twice its numbers:

  | Stats | Lost at break | Target |
  |---|---|---|
  | 1/1 | 13% | 10–20% |
  | 2/3 | 16% | 10–20% |
  | 5/5 | 26% | 25–35% |
  | 8/8 | 43% | 40–60% |
  | 10/10 | 55% | 40–60% |

  These sit below the designed `f_break` because shock and the in-combat drain spend morale too.
- **The morale gain isn't pinning units.** Raising `gain_weight` from 0 to 0.5 moves the even-fight break point
  from 25% to 28% (melee 26% → 29%) and delays the break by 15–30 min. The "units stuck just above breaking"
  seen earlier was scripted battles ending shortly before those units broke.
- **Break points have almost no variance**: p10 = p50 = p90. Every unit of given stats breaks at the same share
  lost. Historically it varies widely, with tails like the 1st Minnesota's ~82%.
- **Built: break-point variance.** At battle start each unit's break point is multiplied by
  `(u / (1 − u))^0.12`, with u drawn from the battle's seed in unit order. That is a logistic draw in log space:
  heavier tails than a normal, and it needs only fdlibm `log` / `exp`. It is saved per unit in the state file
  (`morale.break_scale`) and capped at 95%; `break_point_spread: 0` turns it off. Share of starting men hit
  when the unit broke (losing a firefight against twice its numbers, 400 seeds):

  | Stats | p10 | p50 | p90 | p99 |
  |---|---|---|---|---|
  | 1/1 | 10% | 13% | 17% | 23% |
  | 5/5 | 20% | 27% | 35% | 47% |
  | 8/8 | 33% | 44% | 58% | 71% |
  | 10/10 | 44% | 57% | 71% | 72% |

  "Lost at break" means men killed or wounded, as a share of starting strength, by the moment the unit breaks.
  Rout prisoners come on top: 10% of the men left, ×2 with cavalry. Open (user, 2026-10-01): is 40–60% too
  high for elites? `break_fraction_max` (0.75) sets it.

**Next in A13**:
- Elite break target (above).
- Dragoons skirmish from horseback (decided 2026-10-01): tune them with everything else.
- Equal-numbers grids, so cavalry isn't judged at half the infantry's size.
- Day totals with `batch`: loser 25–35%, winner 12–25%.

### A11. Player-made validation scenarios ✓
Players describe battles and expectations in a **spreadsheet** (decided 2026-10-01: no accounts or installs, and
familiar to them). The admin grades the engine against their expectations with one command. Admin guide and a
message for players: `players/README.md`. Blank template: `players/battle_template.xlsx`.

**Built**:
- **`expect` block** in scenarios (`imperial_generals/validation.py`): `field_held_by`, `breaks` / `holds` (unit
  ids), `casualties` bands (`25-35%`, `<10%`, `>40%`) by side or for `winner` / `loser`, plus `author`, `source`,
  `confidence` and `notes`. Casualties here are killed + wounded + prisoners, as a share of starting strength.
  Scenarios can also carry players' `feedback`.
- **`check`** runs each scenario over many seeds (200 by default) and grades every expectation by the share of
  runs that agree: agrees ≥ 60%, sometimes ≥ 30%, otherwise disagrees (`config/validation.yaml`). It also says
  what the engine typically did, e.g. "typically 23% (8 in 10 runs: 17%-31%)".
  - A run's winner is the field holder; failing that, the side with the smaller share of its men in broken units.
  - Each report carries an **engine version**: a fingerprint of the tuning, so feedback can say which version it
    was about.
  - `check *.xlsx --report results.md` writes a Markdown report to share. For players it also explains how the
    battle usually went (2026-10-01, at the user's request):
    - **by side**: casualties (typical and 8-in-10 range), units broken, prisoners, guns, field held;
    - **unit by unit**: how often each broke and when, casualties, inflicted;
    - **each scripted charge**: how often it was made and how it ended;
    - **a typical run** (the usual field holder, casualties closest to the usual) replayed round by round;
    - a "Reading this report" note.

    Batches record every charge (`batch.charge_runs`).
- **Spreadsheet** (`imperial_generals/sheets.py`, words in `config/sheets.yaml`).
  - Tabs: Start here, Battle, Units, Orders, Feedback. Dropdowns for side, type, subtype, weapon (by name),
    action (fire / charge / hold) and ammo.
  - Experience and morale are separate 1-10 columns.
  - "Should it break?" (yes / no / blank) gives `breaks` / `holds`.
  - The Feedback tab rates casualties (far too light … far too heavy), break timing (far too early … far too
    late) and whether the right side was favoured, with comments.
  - `sheet-template` writes a blank workbook, or one filled from a scenario. `sheet-import` writes a scenario
    file. Problems point to the tab and row. `check` reads workbooks directly and tallies feedback.
  - Not carried: front widths, unit meta, tuning parameters.

**Day totals** (calibration scenarios in `scenarios/calibration/`, 300 seeds; target loser 25–35%, winner 12–25%):

| Scenario | Loser | Winner |
|---|---|---|
| Even firefight, 7.5 h | 47% | 34% |
| Assault | 51% | 16% ✓ |
| Example Ridge | 23% | 19% ✓ |

- **Why the first two run high**: their scripted orders keep firing on units that have already broken. That
  adds 14% (firefight) and 20% (assault) of the loser's strength. In the assault, 19% are prisoners, mostly
  wounded captured on the held field.
- **Decided (2026-10-23)**: falling back out of range waits for positions. Instead, a broken unit is scattering, so
  it is harder to hit:
  - **Broken-target multipliers** (`config/combat.yaml`): fire (muskets, rifles, guns) on a broken unit ×0.5
    (`broken_fire_multiplier`), melee pursuit ×0.75 (`broken_melee_multiplier`). Placeholders. Firing distance
    will get its own multiplier for every unit once positions exist.
  - **`on_break` in each order**, what a unit does when its target breaks or is wiped out mid-round:
    - fire: `keep` (default) firing on the broken unit; or switch to the `strongest` / `weakest` active enemy
      unit, measured as men × share of morale budget left (ties go to the first unit). No active enemy left: keep
      firing on the broken unit (a wiped-out one: stand down). Switches are listed in `RoundReport.retargets` and
      saved in the state history. `closest` / `farthest` wait for positions.
    - melee: `fall_back` (default), leaving it; or `pursue`, staying in contact for the rest of the round. A charge
      whose target breaks before contact just ends. A melee order on an already-broken unit is pursuit, as before.
  - Engine and API only; the player sheets don't carry `on_break` (they are due to be replaced by scenarios built
    on the site).
  - **Day totals after** (`check`, 300 seeds): even firefight loser 47% → 41%, winner 34% → 33%; assault loser
    51% → 47%, winner 16%. Still high: fire keeps going on broken units, at half rate. Left for the tuning pass.
- **Field holder**: decided by votes since A12 (below).

### A12. Field holder from battle performance ✓
`finish(field_held_by='auto')` used to give the field to a side only if every enemy unit had broken or been wiped
out (7% of seeds in the A9 example); otherwise nobody held it and no wounded were captured. Battles are usually
decided before one side is entirely gone. Built 2026-10-23 from the user's idea (2026-10-01):

- A whole army broken or wiped out still decides first (`field_decided_by: 'army_out'`).
- Otherwise three tests each vote for a side that is decisively ahead (`config/aftermath.yaml`, placeholders):
  - **Casualty exchange**: inflicted ≥ 1.5× the men hit it took (`field_exchange_ratio`).
  - **Routs**: the starting strength of its broken or wiped-out units, as a share of its starting total, is
    ≥ 25 points lower than the other side's (`field_rout_gap`).
  - **Strength still standing**: ≥ 1.5× the other's men in unbroken units (`field_standing_ratio`).
- A side holds the field with **≥ 2 votes and none against** (`field_votes_needed`); otherwise nobody does
  (`'votes'`). The admin can still name a holder (`'admin'`).
- `BattleResult` records `field_decided_by` and `field_votes`; both are saved in the state file. Results finished
  before A12 load as decided by the admin, with no votes. The CLI says how the field was decided.
- **The side summary reads the field as the result**, as it was read at the time: `outcome` won / lost / drawn
  and `held_field`. A draw is fine and common: both armies still stand, which pushes the players towards a
  continuation the next day (user, 2026-10-23). Later: finer outcomes such as a Pyrrhic victory.

**Field held** (300 seeds), before → after:

| Scenario | Before | After |
|---|---|---|
| Example Ridge | nobody 97% | Union 26%, Confederate 24%, nobody 51% |
| Even firefight | nobody 100% | North 37%, South 34%, nobody 30% |
| Assault | Attack 72%, nobody 28% | Attack 90%, nobody 10% |

Casualty totals don't change (captured wounded were already counted once, as casualties).

---

## Phase B — Playable web client

### B1. TypeScript port ►
Port the Phase A engine (RNG, params, round engine, engagements, morale, matchups, serialization) to TypeScript,
built together with B2: each piece lands with its parity fixture. The stale v0.2 `typescript/` port is deleted.

**Set up (2026-10-23)**: one Vite project in `web/`, with the engine in `web/src/engine/` (no DOM) and later the
client in `web/src/ui/` (B3). Vitest for tests, `tsc --noEmit` for types. Pinned to releases at least two weeks old
(vite 8.3.4, vitest 5.0.3, typescript 7.0.2). `web/.npmrc` sets `legacy-peer-deps`, because npm 10 crashes on
vite 8's optional devtools peers.

**Ported**: fdlibm `log` / `exp` (shared V8 goldens, plus 200k random inputs against V8's own `Math.log` /
`Math.exp`), `Rng`.
**Next**: engine defaults as generated JSON (decided: Python writes `BattleParams().to_dict()` and the unit tables;
YAML stays the one source), then params, morale, units, the round engine, state file.

### B2. Parity fixtures ►
Shared JSON in `test_cases/parity/`, asserted in both test suites. `imperial_generals.parity` builds them from the
Python engine (`python -m imperial_generals.parity` rewrites them), and a Python test fails if a committed fixture
is stale, so CI catches drift. `fdlibm.json` is the exception: V8 reference values, not generated.
Done: `rng`, `fdlibm`. Coming: state + seed + round inputs → expected report.

**CI** (`.github/workflows/ci.yml`): pytest with 100% coverage required, and web typecheck + Vitest, on every push
and PR. CD for `main` comes later.

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

### Commander rating ○ (needs design)
For fun: after a battle, rate each side's commander as a historical general, the way Civilization turns a score
into a historical leader. Better performance means a better general. **Ancient world up to the American Civil
War; nobody later.**
- **Score** from the side summary: exchange ratio, share lost for good, holding the field, prisoners and guns
  taken, enemy units broken. It should be **adjusted for the odds**: holding even against a bigger or more
  veteran army (order-of-battle men, average experience and morale) scores higher than winning with the bigger
  battalions. Rating against the expected result (a Monte Carlo baseline from A10) does that.
- **Ladder** from disasters to masterpieces, e.g. Varro (Cannae), Crassus (Carrhae), Mack (Ulm), Burnside
  (Fredericksburg) at the bottom; solid commanders (Meade, Wellington, Marlborough, Scipio) in the middle;
  Hannibal, Alexander, Napoleon, Subutai, Khalid ibn al-Walid at the top. A config list, so it can be extended.
- Per battle first; a career rating (average over a player's battles) once the game site stores results.

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

**Broken units' flight** (user, 2026-10-23), once positions exist: a broken unit moves away and can be reached by
units with the range to target it until it is out of range, and by melee pursuit fast enough to catch it. Its
flight slows down over time, round after round, so pursuit catches up later.

### Streamlit prototype ⏸
`streamlit run streamlit/app.py`: Setup + Results pages, map layers, army builder, 1-v-1 sim plots. Frozen. The
Python side is API/CLI-first and the web client replaces it for players.
