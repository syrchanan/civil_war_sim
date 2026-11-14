# Imperial Generals combat resolver

A battle resolver for the admin-run game [Imperial Generals](https://imperial-generals.connorhanan.com/). Admins place
units and give orders; the engine fights the battle in rounds of game time and reports casualties, morale, breaks,
prisoners and who held the field. Same seed, same battle, every time.

**Try it:** https://syrchanan.github.io/civil_war_sim/ (published from `main` after CI passes).

- `src/engine/`: the battle engine (TypeScript), its defaults (`defaults.json`) and golden fixtures (`fixtures/`)
- `src/ui/`: the browser client (Preact)
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

The admin's battle file (Download battle) holds everything and resumes the battle later. Each
round can be replayed on the map ("Show on the map").

## Development

Node 22 or later (`.nvmrc`).

```
npm ci
npm run dev         # the battle client at http://localhost:5173
npm test            # the tests
npm run check       # the typecheck, then the tests with 100% coverage (as CI runs it)
npm run build       # the site, in dist/
```

The engine's tunable defaults live in `src/engine/defaults.json`; edit them there. The golden fixtures in
`src/engine/fixtures/` were recorded from the former Python engine and are frozen: a change that alters battle
results has to re-record them, with a TS tool to be built when the tuning work needs it.

## Checks before pushing

CI runs only on `main` (where a pass deploys the site) and on pull requests into `main`. Work branches are checked
on your machine instead: a pre-push hook runs the same checks as CI (the web typecheck and tests at 100% coverage;
a minute or two). Turn it on once per clone:

```
git config core.hooksPath .githooks
```

`git push --no-verify` skips it for one push (e.g. a docs-only change).
