# Player balance scenarios

Players describe battles in a spreadsheet, say what they expect to happen, and later rate how the engine's
results felt. You turn their workbooks into graded reports with one command. Nobody needs Python except you.

## The loop

1. **Hand out the template.** `battle_template.xlsx` (in this folder) is blank. Upload it to Google Drive and
   share it as "make a copy", or send the file. To give players a ready-made battle to adjust instead:

   ```
   python -m imperial_generals sheet-template players/ridge.xlsx --from scenarios/example_ridge.yaml
   ```

2. **Players fill it in and send back the .xlsx** (Google Sheets: File > Download > Microsoft Excel). The
   "Start here" tab explains each tab to them.

3. **Grade the engine against their expectations.** Each scenario runs 200 times with different dice:

   ```
   python -m imperial_generals check players/inbox/*.xlsx --report players/results.md
   ```

   Problems in a workbook are listed with their tab and row, e.g. `Units row 3: Weapon must be one of ...`.
   Send them back to the player, or fix them yourself.

4. **Share the report** (`results.md`) with the players. It shows, for each expectation, how often the engine
   agrees and what it typically did. It also gives the engine version.

5. **Players add feedback** on the Feedback tab: how casualties and breaks felt, and whether the right side was
   favoured. They copy the engine version from the report. When they send the workbook back, `check` tallies
   the feedback and says how much of it is about an older engine version.

6. **Keep the good ones.** `sheet-import` turns a workbook into a scenario file for the repo, e.g. under
   `scenarios/players/`. Re-run `check` on them after every tuning change:

   ```
   python -m imperial_generals sheet-import players/inbox/janes_battle.xlsx -o scenarios/players/janes_battle.yaml
   ```

Needs `openpyxl` in the venv (`.venv/Scripts/pip.exe install openpyxl`).

## Message for players

> I'm tuning the battle engine and would love your help. Make a copy of the attached workbook and describe a
> battle you know well, real or from our games: the units on each side, what each unit does round by round, and
> what you think should happen (who holds the field, which regiments break, roughly what each side loses). The
> "Start here" tab explains everything. If writing the orders is a pain, describe the plan in the Notes and I'll
> write them. Send the file back and I'll run it hundreds of times and show you how often the engine agrees with
> you. Then tell me how the results felt.

## What players can't set (yet)

Front widths, free-form unit details, and engine tuning parameters. Ask for them in Notes if they matter.
"Who holds the field" currently only goes to a side when every enemy unit has broken (see roadmap A12), so
expectations about it will often disagree until that changes.
