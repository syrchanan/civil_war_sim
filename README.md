# Imperial Generals combat resolver

A battle resolver for the admin-run game [Imperial Generals](https://imperial-generals.connorhanan.com/). Admins place
units and give orders; the engine fights the battle in rounds of game time and reports casualties, morale, breaks,
prisoners and who held the field. Same seed, same battle, in Python and in the browser.

**Try it:** https://syrchanan.github.io/civil_war_sim/ (published from `main` after CI passes).

- `python/`: the engine, CLI and tuning tools (Python, the reference implementation)
- `web/`: the TypeScript port and the browser client
- `config/`: every tunable number, as YAML
- `scenarios/`: example and calibration battles
- `test_cases/`: shared fixtures that both languages must match
- `docs/ROADMAP.md`: goals, design decisions and status
- `CHANGELOG.md`: what changed

## How a battle runs on the site

The site opens in the **player view**; the admin uses **`?mode=admin`**
(https://syrchanan.github.io/civil_war_sim/?mode=admin). Everything stays in the browser: files are passed by hand.

1. The admin builds both armies (or loads each side's army file, CSV), places units on the map and starts the
   battle.
2. The admin downloads a **player file** for each side and sends it to that side's player. It shows the player's
   own units exactly, and of the enemy only what could be seen: names, types, places, broken or not, and men
   roughly.
3. Each player opens their file, gives orders (in the table, or by clicking a unit and then an enemy on the map),
   moves and turns units, and can estimate the round using their own guesses about the enemy. They download their
   **orders file** and send it back.
4. The admin loads both orders files, checks who sent orders and what came from where, adjusts any order, adds
   **modifiers** for the round (e.g. "uphill, fire -15%"), and fights the round. Orders files made from an older
   copy of the battle are refused.
5. Repeat from step 2 with fresh player files. At the end, the admin finishes the battle: killed, wounded,
   prisoners, and who held the field.

The admin's battle file (Download battle) holds everything and resumes the battle later, here or in Python. Each
round can be replayed on the map ("Show on the map").

## Python

```
python -m venv .venv
.venv/Scripts/pip install -r python/requirements.txt     # .venv/bin/pip on macOS / Linux
.venv/Scripts/python -m pytest

.venv/Scripts/python -m imperial_generals run scenarios/example_ridge.yaml
```

`python -m imperial_generals --help` lists the other commands (step-by-step battles, batches, matchup grids,
player spreadsheets). From code, `imperial_generals.api` offers the same steps on JSON-safe dicts.

A battle saved from the site replays in Python with
`python -m imperial_generals scenario-from-state battle.json`, then `run`, `batch` or `check` on the scenario.

## Web

```
cd web
npm install
npm run dev         # the battle client at http://localhost:5173
npm test            # or: npm run coverage (100% required, as in CI)
```

After changing the Python engine or `config/`, regenerate the shared fixtures and defaults with
`python -m imperial_generals.parity`; tests on both sides fail while they are stale.
