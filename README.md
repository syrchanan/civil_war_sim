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
The field is on the left and one tabbed sidebar on the right; on a phone the tabs run along the bottom.

1. **Setup** (admin): the battle's name, the ground, the field's size (suggested from the armies), the first round's
   time, round length and rounds planned, and each side's deployment zone (drag its edge on the map).
2. **Armies**: each player sends an army file (CSV, with optional corps, division and brigade columns). The admin
   loads both, reviews them (problems flagged, by brigade), and approves each or sends it back with a note.
3. **Round 0, deployment**: the admin downloads a **player file** for each side. Each player places their regiments
   inside their zone (one at a time, or a brigade at a time: drawn up in line, two lines or column, and dragged as
   one) and sends their deployment back. The admin loads both and opens round 1.
4. **Each round**: the admin sends fresh player files. A player sees their own units exactly and of the enemy only
   what could be seen (men roughly; regiments lost from sight as last seen). They give orders by regiment, or to a
   whole brigade or division at once (fire, charge or hold against an enemy brigade), look things up in
   **Reconnaissance**, and send their **orders file**. The admin loads both, adjusts orders, adds **modifiers**
   (e.g. "uphill, fire -15%") and fights the round, which is told as a **dispatch**.
5. **Nightfall**: the admin finishes the battle and sends everyone the battle file (Download battle): the fog lifts.
   The Result tab tells it: the verdict, the butcher's bill, the general each commander fought like, and the
   regiments ranked.

The admin's battle file (Download battle) holds everything and resumes the battle later. Each round can be replayed
on the map ("Show on the map"). Large battles (60 to 80 regiments a side) can be shown on the map by brigade or
division.

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
