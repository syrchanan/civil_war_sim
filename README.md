# Imperial Generals combat resolver

A battle resolver for the admin-run game [Imperial Generals](https://imperial-generals.connorhanan.com/). Admins place
units and give orders; the engine fights the battle in rounds of game time and reports casualties, morale, breaks,
prisoners and who held the field. Same seed, same battle, in Python and (soon) in the browser.

- `python/`: the engine, CLI and tuning tools (Python, the reference implementation)
- `web/`: the TypeScript port and browser client (in progress)
- `config/`: every tunable number, as YAML
- `scenarios/`: example and calibration battles
- `test_cases/`: shared fixtures that both languages must match
- `docs/ROADMAP.md`: goals, design decisions and status
- `CHANGELOG.md`: what changed

## Python

```
python -m venv .venv
.venv/Scripts/pip install -r python/requirements.txt     # .venv/bin/pip on macOS / Linux
.venv/Scripts/python -m pytest

.venv/Scripts/python -m imperial_generals run scenarios/example_ridge.yaml
```

`python -m imperial_generals --help` lists the other commands (step-by-step battles, batches, matchup grids,
player spreadsheets). From code, `imperial_generals.api` offers the same steps on JSON-safe dicts.

## Web

```
cd web
npm install
npm test
```
