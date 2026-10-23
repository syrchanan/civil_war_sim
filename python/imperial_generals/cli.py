"""
Command line for the battle engine (roadmap A9). Run ``python -m imperial_generals --help``.

    python -m imperial_generals new setup.yaml -o battle.json         # start a battle from a setup file
    python -m imperial_generals preview battle.json --orders o.yaml   # who would fight whom, no dice rolled
    python -m imperial_generals resolve battle.json --duration 90 --orders o.yaml
    python -m imperial_generals finish battle.json --field Union      # settle killed / wounded / captured
    python -m imperial_generals show battle.json
    python -m imperial_generals run scenario.yaml                     # setup + scripted rounds, start to end
    python -m imperial_generals batch scenario.yaml --seeds 500       # the spread of outcomes over many seeds
    python -m imperial_generals matchups grid.yaml --plot grid.png    # every unit kind against every other
    python -m imperial_generals check scenario.yaml --report r.md     # grade the engine against expectations
    python -m imperial_generals sheet-template players.xlsx           # a workbook players fill in
    python -m imperial_generals sheet-import filled.xlsx              # ... back into a scenario file
    python -m imperial_generals scenario-from-state battle.json       # a saved battle as a scenario to replay

``resolve`` and ``finish`` update the state file in place unless ``-o`` names another. ``--json`` prints the
machine-readable report instead of a table. Problems exit with code 2 and a message saying what to fix.
"""

import argparse
import json
import sys
from pathlib import Path

import yaml

from imperial_generals import api, sheets, tuning, validation
from imperial_generals.battles.setup import SetupError, load_setup_file
from imperial_generals.battles.state import FORMAT
from imperial_generals.config import get_config


class CliError(Exception):
    pass


# =============================================================================
# Files
# =============================================================================

def _load_state(path: Path) -> dict:
    data = load_setup_file(path)
    if not isinstance(data, dict) or data.get('format') != FORMAT:
        raise CliError(f'{path.name} is not a battle state file; make one with "new".')
    return data


def _load_orders(path: Path | None) -> dict:
    if path is None:
        return {}
    data = load_setup_file(path)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise CliError(f'{path.name} must map unit ids to orders.')
    return data


def _save(state: dict, path: Path) -> None:
    path.write_text(json.dumps(state, indent=2) + '\n', encoding='utf-8', newline='\n')


def _print_json(data) -> None:
    print(json.dumps(data, indent=2))


# =============================================================================
# Tables
# =============================================================================

def _table(header: list, rows: list, left: int = 2, notes: bool = True) -> str:
    """
    Left-align the first ``left`` columns (text) and, if ``notes``, the last (status notes); right-align the
    numbers between.
    """
    cells = [[str(c) for c in row] for row in [header] + rows]
    widths = [max(len(row[i]) for row in cells) for i in range(len(header))]
    lines = []
    for row in cells:
        parts = [c.ljust(w) if i < left or (notes and i == len(row) - 1) else c.rjust(w) for i, (c, w) in enumerate(zip(row, widths))]
        lines.append('  '.join(parts).rstrip())
    return '\n'.join(lines)


def _side_names(state: dict) -> list:
    return api._side_names(state)


def _names(state: dict) -> dict:
    return {u['id']: u['name'] for u in state['units']}


def _status(size: int, broken: bool, broke_at=None, guns_lost: int = 0) -> str:
    notes = []
    if size == 0:
        notes.append('wiped out')
    elif broke_at is not None:
        notes.append(f'broke at {broke_at:.0f} min')
    elif broken:
        notes.append('broken')
    if guns_lost:
        notes.append(f"{guns_lost} gun{'s' if guns_lost != 1 else ''} lost")
    return ', '.join(notes)


CHARGE_OUTCOMES = {
    'home': 'went home', 'faltered': 'faltered', 'defender_broke': 'broke the defender before contact',
    'meeting': 'met head on', 'pursuit': 'pursuit', 'charger_broke': 'charger broke on the approach',
    'target_broke': 'target broke before contact',
}


def _charge_text(c: dict, names: dict) -> str:
    text = f"{names[c['charger']]} -> {names[c['target']]}: {CHARGE_OUTCOMES[c['outcome']]} at {c['resolved_at']:.0f} min"
    if c['p_home'] is not None:
        text += f" ({c['p_home']:.0%} to go home, {c['p_falter']:.0%} falter, {c['p_defender_breaks']:.0%} break)"
    return text


def _print_report(state: dict, report: dict) -> None:
    sides, names = _side_names(state), _names(state)
    side_of = {u['id']: u['side'] for u in state['units']}
    print(f"Round {report['round']} ({report['start']:.0f}-{report['end']:.0f} min)")
    rows = [
        [names[uid], sides[side_of[uid]], u['size'], u['losses'], u['captured'], u['inflicted'], f"{u['morale']:.1f}",
         _status(u['size'], u['broken'], u['broke_at'], u['guns_lost'])]
        for uid, u in report['units'].items()
    ]
    print(_table(['Unit', 'Side', 'Size', 'Lost', 'Captured', 'Inflicted', 'Morale', 'Status'], rows))
    if report['charges']:
        print('Charges: ' + '; '.join(_charge_text(c, names) for c in report['charges']))
    skipped = report.get('skipped_orders', {})
    if skipped:
        print('Skipped orders: ' + ', '.join(f'{uid} ({why})' for uid, why in skipped.items()))
    print()


FIELD_TESTS = {'exchange': 'casualty exchange', 'routs': 'routs', 'standing': 'strength standing'}


def _field_text(result: dict, sides: list) -> str:
    """Who held the field and how it was decided: the whole army out, the votes, or named by the admin."""
    holder = result['field_held_by']
    who = 'nobody, a draw' if holder is None else sides[holder]
    how = result['field_decided_by']
    if how == 'army_out':
        why = f'the whole {sides[1 - holder]} army broke'
    elif how == 'votes':
        votes = result['field_votes']
        why = 'votes: ' + ', '.join(f"{label} {'-' if votes[test] is None else sides[votes[test]]}"
                                    for test, label in FIELD_TESTS.items())
    else:
        why = 'named by the admin'
    return f'Field held by: {who} ({why})'


def _print_result(state: dict, result: dict) -> None:
    sides, names = _side_names(state), _names(state)
    units = {u['id']: u for u in state['units']}
    print(_field_text(result, sides))
    rows = []
    for uid, o in result['units'].items():
        u = units[uid]
        # captured wounded are counted once, as prisoners
        wounded = o['wounded'] - o['wounded_captured']
        prisoners = o['captured_in_rout'] + o['wounded_captured']
        rows.append([names[uid], sides[u['side']], u['initial_size'], o['killed'], wounded, prisoners,
                     o['wounded_returned'], o['final_size'], u['inflicted'], o['guns_lost'] or ''])
    print(_table(['Unit', 'Side', 'Started', 'Killed', 'Wounded', 'Prisoners', 'Returned', 'Final', 'Inflicted',
                  'Guns lost'], rows))
    print('Final = Started - Killed - Wounded - Prisoners + Returned (wounded who recover rejoin their unit).')
    _print_side_summary(state)


def _print_order_of_battle(state: dict) -> None:
    def kind(side: dict, key: str) -> str:
        k = side['by_type'].get(key)
        if k is None:
            return '-'
        guns = f", {k['guns']} guns" if 'guns' in k else ''
        return f"{k['men']:,} ({k['units']}{guns})"

    print('Order of battle (men; units in brackets)')
    rows = [[s['name'], s['units'], f"{s['men']:,}", kind(s, 'inf'), kind(s, 'cav'), kind(s, 'art'),
             f"{s['avg_experience']:.1f}", f"{s['avg_morale']:.1f}"] for s in api.order_of_battle(state)]
    print(_table(['Side', 'Units', 'Men', 'Infantry', 'Cavalry', 'Artillery', 'Avg exp', 'Avg morale'], rows,
                 left=1, notes=False))
    print()


def _print_side_summary(state: dict) -> None:
    sides = api.side_summary(state)

    def row(label: str, key: str, fmt=lambda v: f'{v:,}') -> list:
        return [label] + [fmt(s[key]) for s in sides]

    rows = [
        row('Result', 'outcome', str),
        row('Started', 'started'),
        row('Killed', 'killed'),
        row('Wounded', 'wounded'),
        row('Prisoners lost', 'prisoners_lost'),
        row('Wounded returned', 'returned'),
        row('Final', 'final'),
        row('Lost for good', 'loss_share', lambda v: f'{v:.0%}'),
        row('Hits taken', 'hits_taken'),
        row('Hits inflicted', 'hits_inflicted'),
        row('Exchange ratio (inflicted / taken)', 'exchange_ratio', lambda v: '-' if v is None else f'{v:.2f}'),
        row('Prisoners taken', 'prisoners_taken'),
        row('Guns lost', 'guns_lost'),
        row('Guns taken', 'guns_taken'),
        ['Units broken or wiped out'] + [f"{s['units_out']} of {s['units']}" for s in sides],
    ]
    print()
    print(_table(['Side summary'] + [s['name'] for s in sides], rows, left=1, notes=False))


def _print_state(state: dict) -> None:
    sides = _side_names(state)
    title = state['meta'].get('name', 'Battle')
    finished = ', finished' if state['finished'] else ''
    print(f"{title}: round {state['round']}, {state['time']:.0f} min{finished}")
    print()
    _print_order_of_battle(state)
    rows = []
    for u in state['units']:
        kind = '/'.join(p for p in (u['type'], u['subtype']) if p) or 'generic'
        if 'guns' in u:
            kind += f", {u['guns']} guns"
        rows.append([u['name'], sides[u['side']], kind, u['stats'], u['size'], u['initial_size'],
                     f"{u['raw_morale']:.1f}", _status(u['size'], u['morale']['broken'])])
    print(_table(['Unit', 'Side', 'Type', 'Stats', 'Size', 'Started', 'Morale', 'Status'], rows, left=4))
    if state['result'] is not None:
        _print_side_summary(state)


# =============================================================================
# Commands
# =============================================================================

def _cmd_new(args) -> None:
    state = api.new_battle(load_setup_file(args.setup), seed=args.seed)
    _save(state, args.output)
    print(f"Wrote {args.output} ({len(state['units'])} units, seed {state['seed']}).")


def _cmd_resolve(args) -> None:
    state, report = api.step(_load_state(args.state), args.duration, _load_orders(args.orders),
                             record_events=args.events)
    _save(state, args.output or args.state)
    if args.json:
        _print_json(report)
    else:
        _print_report(state, report)


def _cmd_preview(args) -> None:
    state = _load_state(args.state)
    arrows = api.preview(state, _load_orders(args.orders))
    if args.json:
        _print_json(arrows)
        return
    if not arrows:
        print('No engagements: every unit is idle.')
    names = _names(state)
    rows = [[f"{names[a['attacker']]} -> {names[a['target']]}", a['mode'], f"{a['rate']:.2f} men/min"] for a in arrows]
    if rows:
        print(_table(['Attacker -> target', 'Mode', 'Casualty rate'], rows, left=1))


def _field(value: str, state: dict):
    if value == 'auto':
        return 'auto'
    if value == 'none':
        return None
    if value in ('0', '1'):
        return int(value)
    sides = state['meta'].get('sides')
    if isinstance(sides, list) and value in sides:
        return sides.index(value)
    names = f" or a side name ({', '.join(sides)})" if isinstance(sides, list) else ''
    raise CliError(f'--field must be auto, none, 0, 1{names}; got {value!r}.')


def _cmd_finish(args) -> None:
    state = _load_state(args.state)
    state, result = api.finish(state, _field(args.field, state))
    _save(state, args.output or args.state)
    if args.json:
        _print_json(result)
    else:
        _print_result(state, result)


def _cmd_run(args) -> None:
    state, reports, result = api.run_scenario(load_setup_file(args.scenario), seed=args.seed,
                                              record_events=args.events)
    if args.output:
        _save(state, args.output)
    if args.json:
        _print_json({'state': state, 'reports': reports, 'result': result})
        return
    _print_order_of_battle(state)
    for report in reports:
        _print_report(state, report)
    if result is not None:
        _print_result(state, result)


def _load_overrides(path: Path | None) -> dict | None:
    if path is None:
        return None
    data = load_setup_file(path)
    if not isinstance(data, dict):
        raise CliError(f'{path.name} must map parameter sections to overrides.')
    return data


def _pct(v) -> str:
    return '-' if v is None else f'{v:.0%}'


def _num(v, digits: int = 2) -> str:
    return '-' if v is None else f'{v:.{digits}f}'


def _three(spread: dict, fmt) -> str:
    return ' / '.join(fmt(spread[k]) for k in ('p10', 'p50', 'p90'))


def _print_batch(summary: dict, batch) -> None:
    print(f"{summary['name']}: {summary['seeds']} seeds ({batch.seeds[0]}-{batch.seeds[-1]})")
    print('Field held: ' + ', '.join(f'{name} {share:.0%}' for name, share in summary['field'].items()))
    print()
    sides = summary['sides']
    rows = [
        ['Lost for good, p10 / p50 / p90'] + [_three(s['loss_share'], _pct) for s in sides],
        ['Exchange ratio, p10 / p50 / p90'] + [_three(s['exchange_ratio'], _num) for s in sides],
        ['Units broken or wiped out (mean)'] + [f"{s['units_out_mean']:.1f} of {s['units']}" for s in sides],
        ['A unit broke'] + [_pct(s['first_break']['share']) for s in sides],
        ['First break (median)'] + [_num(s['first_break']['p50'], 0) + ' min' for s in sides],
        ['Prisoners taken (mean)'] + [f"{s['prisoners_taken_mean']:.0f}" for s in sides],
        ['Guns taken (mean)'] + [f"{s['guns_taken_mean']:.1f}" for s in sides],
    ]
    print(_table([''] + [s['name'] for s in sides], rows, left=1, notes=False))
    print()
    names = [s['name'] for s in sides]
    rows = [[u['name'], names[u['side']], _pct(u['break_share']), _num(u['broke_at_p50'], 0),
             _three(u['hit_share'], _pct), f"{u['inflicted_mean']:.0f}"] for u in summary['units']]
    print(_table(['Unit', 'Side', 'Breaks', 'Broke at (median min)', 'Hit share p10 / p50 / p90',
                  'Inflicted (mean)'], rows, notes=False))


def _cmd_batch(args) -> None:
    batch = tuning.run_batch(load_setup_file(args.scenario), seeds=args.seeds, seed_start=args.seed_start,
                             overrides=_load_overrides(args.params), workers=args.workers or tuning.default_workers())
    summary = tuning.summarize(batch)
    if args.csv:
        tuning.write_csv(batch.runs, args.csv)
    if args.units_csv:
        tuning.write_csv(batch.unit_runs, args.units_csv)
    if args.json:
        _print_json(summary)
    else:
        _print_batch(summary, batch)


def _print_matrix(title: str, grid, metric: str, fmt) -> None:
    print(title)
    rows = [[a] + [fmt(grid.cells[(a, d)][metric]) for d in grid.keys] for a in grid.attackers]
    print(_table(['attacker \\ defender'] + grid.keys, rows, left=1, notes=False))
    print()


FACET_TITLES = {'orders': 'orders from the file', 'ranged': 'ranged', 'melee': 'melee',
                'charge': 'charge into standing fire', 'artillery': 'artillery at long range'}


def _cmd_matchups(args) -> None:
    spec = load_setup_file(args.grid)
    overrides = _load_overrides(args.params)
    modes = [args.mode]
    if args.mode == 'all':
        modes = ['ranged', 'melee', 'charge']
        if any(isinstance(u, dict) and u.get('type') == 'art' for u in (spec or {}).get('units', {}).values()):
            modes.append('artillery')
    grids = [tuning.matchup_grid(spec, seeds=args.seeds, overrides=overrides, mode=mode,
                                 workers=args.workers or tuning.default_workers()) for mode in modes]
    if args.csv:
        tuning.write_csv([row for grid in grids for row in grid.rows()], args.csv)
    if args.plot:
        for grid in grids:
            path = args.plot
            if len(grids) > 1:
                path = args.plot.with_name(f'{args.plot.stem}_{grid.mode}{args.plot.suffix}')
            tuning.plot_matchups(grid, path, metric=args.metric)
    if args.json:
        _print_json([row for grid in grids for row in grid.rows()])
        return
    for grid in grids:
        rounds = ' + '.join(f'{r:g}' for r in grid.rounds)
        print(f'{grid.name} ({FACET_TITLES[grid.mode]}): {grid.seeds} seeds per cell, rounds {rounds} min')
        print()
        _print_matrix('Attacker advantage (attacker wins - defender wins)', grid, 'advantage',
                      lambda v: f'{v:+.0%}')
        _print_matrix('Defender breaks', grid, 'defender_breaks', _pct)
        _print_matrix('Defender men hit (share of its strength)', grid, 'defender_hit_share', _pct)
        _print_matrix('Exchange ratio (defender men hit per attacker man hit)', grid, 'exchange_ratio', _num)
        if grid.mode == 'charge':
            print('Charges: went home / faltered / broke the defender')
            rows = [[a] + ['/'.join(f"{grid.cells[(a, d)][k]:.0%}".rstrip('%')
                                    for k in ('charge_home', 'charge_faltered', 'charge_broke_defender'))
                           for d in grid.keys] for a in grid.attackers]
            print(_table(['attacker \\ defender'] + grid.keys, rows, left=1, notes=False))
            print()


def _check_heading(report: dict) -> str:
    by = f" by {report['author']}" if report['author'] else ''
    details = [f"confidence {report['confidence']}" if report['confidence'] else None,
               f"source: {report['source']}" if report['source'] else None]
    details = '; '.join(d for d in details if d)
    return f"{report['name']}: expectations{by}" + (f' ({details})' if details else '')


def _feedback_lines(report: dict) -> list:
    """Players' feedback, tallied: a heading line, then one line per question."""
    entries = report['feedback']
    if not entries:
        return []
    older = sum(e.get('engine') != report['engine'] for e in entries)
    note = f'; {older} about an older engine version' if older else ''
    lines = [f'Player feedback ({len(entries)} responses{note}):']
    for key, label in (('casualties', 'casualties'), ('breaks', 'breaks'),
                       ('right_side_favoured', 'right side favoured')):
        counts: dict = {}
        for e in entries:
            if e.get(key):
                counts[e[key]] = counts.get(e[key], 0) + 1
        if counts:
            lines.append(f'  {label}: ' + ', '.join(f'{k} {v}' for k, v in counts.items()))
    return lines


def _range(q: dict) -> str:
    """'19% (8 in 10 runs: 14%-26%)' from p10/p50/p90 shares."""
    return f"{q['p50']:.0%} (8 in 10: {q['p10']:.0%}-{q['p90']:.0%})"


def _side_rows(report: dict) -> tuple:
    sides = report['sides']
    rows = [
        ['Men at the start'] + [f"{s['men']:,}" for s in sides],
        ['Casualties (killed, wounded, captured)'] + [_range(s['casualties']) for s in sides],
        ['Units broken (average)'] + [f"{s['units_out_mean']:.1f} of {s['units']}" for s in sides],
        ['Prisoners taken (typical)'] + [f"{s['prisoners_taken_p50']:,.0f}" for s in sides],
        ['Guns captured (average)'] + [f"{s['guns_taken_mean']:.1f}" for s in sides],
        ['Held the field'] + [_pct(s['field_held']) for s in sides],
    ]
    return [''] + [s['name'] for s in sides], rows


def _unit_rows(report: dict) -> tuple:
    rows = [[u['name'], u['side'], f"{u['started']:,}", _pct(u['break_share']),
             '-' if u['broke_at_p50'] is None else f"{u['broke_at_p50']:.0f} min", _range(u['casualties']),
             f"{u['inflicted_p50']:,.0f}"] for u in report['units']]
    return ['Unit', 'Side', 'Men', 'Broke', 'Typically broke at', 'Casualties', 'Inflicted'], rows


def _charge_rows(report: dict) -> tuple:
    names = {u['id']: u['name'] for u in report['units']}
    rows = [[f"{names[c['charger']]} -> {names[c['target']]}", f"round {c['round']}", _pct(c['made']),
             ', '.join(f"{CHARGE_OUTCOMES[o]} {'<1%' if c['outcomes'][o] < 0.01 else format(c['outcomes'][o], '.0%')}"
                       for o in CHARGE_OUTCOMES if o in c['outcomes'])]
            for c in report['charges']]
    return ['Charge', 'When', 'Made in', 'How it ended'], rows


def _print_check(report: dict) -> None:
    print(_check_heading(report))
    print(f"{report['seeds']} seeds, engine {report['engine']}")
    print()
    rows = [[f"[{e['verdict']}]", _pct(e['share']), e['text'], e['engine']] for e in report['expectations']]
    print(_table(['Verdict', 'Agrees', 'Expectation', 'What the engine did'], rows, left=1))
    print()
    print(f"{report['agree']} of {report['total']} expectations agree.")
    for line in _feedback_lines(report):
        print(line)
    print()
    print('How the battle usually went')
    print(_table(*_side_rows(report), left=1, notes=False))
    print()
    print('Unit by unit')
    print(_table(*_unit_rows(report), left=2, notes=False))
    print()
    if report['charges']:
        print('Charges')
        print(_table(*_charge_rows(report), left=2))
        print()


def _md_table(header: list, rows: list) -> list:
    return (['| ' + ' | '.join(header) + ' |', '|' + '---|' * len(header)]
            + ['| ' + ' | '.join(str(c) for c in row) + ' |' for row in rows])


def _md_typical(report: dict) -> list:
    typical = report['typical']
    names = typical['units']
    sides = [s['name'] for s in report['sides']]
    lines = [f"One run close to the usual outcome (dice seed {typical['seed']}), round by round.", '']
    for rnd in typical['rounds']:
        lines += [f"**Round {rnd['round']}** ({rnd['start']:.0f}-{rnd['end']:.0f} min)", '']
        rows = [[names[uid], sides[_side_index(report, uid)], f"{u['size']:,}", u['losses'], u['captured'],
                 _status(u['size'], u['broken'], u['broke_at'], u['guns_lost']) or '-']
                for uid, u in rnd['units'].items()]
        lines += _md_table(['Unit', 'Side', 'Men left', 'Hit this round', 'Captured', 'Status'], rows)
        if rnd['charges']:
            lines += ['', 'Charges: ' + '; '.join(_charge_text(c, names) for c in rnd['charges'])]
        lines.append('')
    holder = typical['field_held_by']
    lines += [f"Field held by: {'nobody' if holder is None else sides[holder]}. Casualties: "
              + ', '.join(f"{s['name']} {s['casualty_share']:.0%}" for s in typical['result']) + '.', '']
    return lines


def _side_index(report: dict, uid: str) -> int:
    side = next(u['side'] for u in report['units'] if u['id'] == uid)
    return [s['name'] for s in report['sides']].index(side)


def _markdown(reports: list) -> str:
    cfg = get_config()['validation']
    lines = ['# Engine check', '', '## Reading this report', '',
             'Each battle was fought many times with different dice. For each expectation, "Engine agrees" is the '
             f"share of those runs that matched it: **agrees** means at least {cfg['agrees_at']:.0%}, "
             f"**sometimes** at least {cfg['sometimes_at']:.0%}, **disagrees** less. "
             'Casualties are killed + wounded + captured, as a share of the men a unit or side started with. '
             '"8 in 10" is the range the middle 80% of runs fell in. The winner of a run is the side holding the '
             'field, or failing that the side that lost fewer of its men to broken units.', '']
    for r in reports:
        lines += [f"## {r['name']}", '', _check_heading(r) + '.', '',
                  f"{r['seeds']} runs with different dice; engine version `{r['engine']}`. "
                  f"**{r['agree']} of {r['total']}** expectations agree.", '']
        if r['notes']:
            lines += [f"Notes: {r['notes']}", '']
        lines += ['### How it was graded', '']
        lines += _md_table(['Expectation', 'Engine agrees', 'Verdict', 'What the engine did'],
                           [[e['text'], _pct(e['share']), e['verdict'], e['engine']] for e in r['expectations']])
        lines.append('')
        feedback = _feedback_lines(r)
        if feedback:
            lines += [feedback[0], ''] + [f'- {line.strip()}' for line in feedback[1:]]
            lines += [f"- {e['author'] or 'Someone'}: {e['comments']}" for e in r['feedback'] if e.get('comments')]
            lines.append('')
        lines += ['### How the battle usually went', ''] + _md_table(*_side_rows(r)) + ['']
        lines += ['### Unit by unit', ''] + _md_table(*_unit_rows(r)) + ['']
        if r['charges']:
            lines += ['### Charges', ''] + _md_table(*_charge_rows(r)) + ['']
        lines += ['### A typical run', ''] + _md_typical(r)
    return '\n'.join(lines)


def _cmd_check(args) -> None:
    overrides = _load_overrides(args.params)
    reports = []
    for path in args.scenarios:
        args.current = path
        scenario = sheets.read_workbook(path) if path.suffix.lower() == '.xlsx' else load_setup_file(path)
        reports.append(validation.check(scenario, seeds=args.seeds, overrides=overrides,
                                        workers=args.workers or tuning.default_workers()))
    if args.report:
        args.report.write_text(_markdown(reports), encoding='utf-8', newline='\n')
    if args.json:
        _print_json(reports)
        return
    for report in reports:
        _print_check(report)
    if len(reports) > 1:
        print('Summary')
        print(_table(['Scenario', 'Agree'], [[r['name'], f"{r['agree']} of {r['total']}"] for r in reports],
                     left=1, notes=False))


def _cmd_sheet_template(args) -> None:
    scenario = load_setup_file(args.source) if args.source else None
    sheets.write_template(args.output, scenario=scenario)
    filled = f', filled from {args.source.name}' if args.source else ''
    print(f'Wrote {args.output}{filled}. Players fill it in (Google Sheets or Excel) and send back the .xlsx.')


def _cmd_sheet_import(args) -> None:
    args.current = args.workbook
    scenario = sheets.read_workbook(args.workbook)
    output = args.output or args.workbook.with_suffix('.yaml')
    header = f'# Imported from {args.workbook.name}. Check it with: python -m imperial_generals check {output.name}\n'
    output.write_text(header + yaml.safe_dump(scenario, sort_keys=False, allow_unicode=True, width=120),
                      encoding='utf-8', newline='\n')
    print(f"Wrote {output} ({len(scenario['units'])} units, {len(scenario['rounds'])} rounds).")


def _cmd_scenario_from_state(args) -> None:
    scenario = api.scenario_from_state(_load_state(args.state))
    output = args.output or args.state.with_suffix('.yaml')
    header = (f'# Replays {args.state.name} exactly: python -m imperial_generals run {output.name}\n'
              f'# Rerun it over other seeds or parameters with batch / check.\n')
    output.write_text(header + yaml.safe_dump(scenario, sort_keys=False, allow_unicode=True, width=120),
                      encoding='utf-8', newline='\n')
    n = len(scenario['rounds'])
    print(f"Wrote {output} ({len(scenario['units'])} units, {n} round{'' if n == 1 else 's'}).")


def _cmd_show(args) -> None:
    _print_state(_load_state(args.state))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='python -m imperial_generals',
                                     description='Imperial Generals battle engine: resolve battles round by round.')
    commands = parser.add_subparsers(dest='command', required=True)

    p = commands.add_parser('new', help='start a battle from a setup file (YAML or JSON)')
    p.add_argument('setup', type=Path)
    p.add_argument('-o', '--output', type=Path, required=True, help='state file to write')
    p.add_argument('--seed', type=int, help="overrides the setup's seed")
    p.set_defaults(run=_cmd_new)

    p = commands.add_parser('resolve', help='fight one round')
    p.add_argument('state', type=Path)
    p.add_argument('--duration', type=float, required=True, help='round length in game minutes')
    p.add_argument('--orders', type=Path, help='orders file: unit id -> {target, mode, ammo, on_break}; others idle')
    p.add_argument('-o', '--output', type=Path, help='write the new state here instead of updating STATE')
    p.add_argument('--events', action='store_true', help='record every casualty in the report')
    p.add_argument('--json', action='store_true', help='print the report as JSON')
    p.set_defaults(run=_cmd_resolve)

    p = commands.add_parser('preview', help='show the engagements some orders would create (no dice rolled)')
    p.add_argument('state', type=Path)
    p.add_argument('--orders', type=Path)
    p.add_argument('--json', action='store_true')
    p.set_defaults(run=_cmd_preview)

    p = commands.add_parser('finish', help='end the battle and settle killed / wounded / captured')
    p.add_argument('state', type=Path)
    p.add_argument('--field', default='auto',
                   help='side holding the field: auto (default), none, 0, 1 or a side name')
    p.add_argument('-o', '--output', type=Path)
    p.add_argument('--json', action='store_true')
    p.set_defaults(run=_cmd_finish)

    p = commands.add_parser('run', help='play a scenario file (setup + rounds) from start to end')
    p.add_argument('scenario', type=Path)
    p.add_argument('-o', '--output', type=Path, help='state file to write')
    p.add_argument('--seed', type=int)
    p.add_argument('--events', action='store_true')
    p.add_argument('--json', action='store_true')
    p.set_defaults(run=_cmd_run)

    p = commands.add_parser('batch', help='run a scenario over many seeds and summarise the outcomes')
    p.add_argument('scenario', type=Path)
    p.add_argument('--seeds', type=int, default=200, help='number of seeds (default 200)')
    p.add_argument('--seed-start', type=int, default=0)
    p.add_argument('--workers', type=int, help='worker processes (default: one per CPU)')
    p.add_argument('--params', type=Path, help='parameter overrides file, e.g. {combat: {ranged_kill_rate: 0.005}}')
    p.add_argument('--csv', type=Path, help='write one row per seed')
    p.add_argument('--units-csv', type=Path, help='write one row per seed per unit')
    p.add_argument('--json', action='store_true', help='print the summary as JSON')
    p.set_defaults(run=_cmd_batch)

    p = commands.add_parser('matchups', help='every unit kind in a grid file attacks every other, one on one')
    p.add_argument('grid', type=Path)
    p.add_argument('--seeds', type=int, help="seeds per cell (default: the file's, else 100)")
    p.add_argument('--workers', type=int, help='worker processes (default: one per CPU)')
    p.add_argument('--params', type=Path, help='parameter overrides file')
    p.add_argument('--csv', type=Path, help='write one row per cell')
    p.add_argument('--plot', type=Path, help='save a heatmap image')
    p.add_argument('--metric', default='advantage',
                   choices=['advantage', 'attacker_wins', 'defender_wins', 'attacker_breaks', 'defender_breaks',
                            'attacker_hit_share', 'defender_hit_share'],
                   help='heatmap metric (default advantage)')
    p.add_argument('--mode', default='all', choices=['all', 'ranged', 'melee', 'charge', 'artillery', 'orders'],
                   help='all (default): ranged, melee, charge and (with artillery in the file) artillery at long '
                        'range; '
                        'or one of them; orders: the attack / defend orders from the file')
    p.add_argument('--json', action='store_true', help='print the cells as JSON')
    p.set_defaults(run=_cmd_matchups)

    p = commands.add_parser('check', help='grade the engine against scenarios\' expect blocks')
    p.add_argument('scenarios', type=Path, nargs='+')
    p.add_argument('--seeds', type=int, help='runs per scenario (default from config/validation.yaml)')
    p.add_argument('--workers', type=int, help='worker processes (default: one per CPU)')
    p.add_argument('--params', type=Path, help='parameter overrides file')
    p.add_argument('--report', type=Path, help='write a Markdown report (to share with players)')
    p.add_argument('--json', action='store_true')
    p.set_defaults(run=_cmd_check)

    p = commands.add_parser('sheet-template', help='write a workbook for players to describe a battle')
    p.add_argument('output', type=Path)
    p.add_argument('--from', dest='source', type=Path, help='fill it from this scenario file')
    p.set_defaults(run=_cmd_sheet_template)

    p = commands.add_parser('sheet-import', help='turn a filled-in workbook into a scenario file')
    p.add_argument('workbook', type=Path)
    p.add_argument('-o', '--output', type=Path, help='scenario file to write (default: next to the workbook)')
    p.set_defaults(run=_cmd_sheet_import)

    p = commands.add_parser('scenario-from-state',
                            help='turn a saved battle (e.g. downloaded from the site) into a scenario that replays it')
    p.add_argument('state', type=Path)
    p.add_argument('-o', '--output', type=Path, help='scenario file to write (default: next to the state file)')
    p.set_defaults(run=_cmd_scenario_from_state)

    p = commands.add_parser('show', help='summarise a state file')
    p.add_argument('state', type=Path)
    p.set_defaults(run=_cmd_show)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        args.run(args)
    except SetupError as exc:
        source = (getattr(args, 'setup', None) or getattr(args, 'scenario', None) or getattr(args, 'grid', None)
                  or getattr(args, 'current', None))
        where = f' {source.name}' if source is not None else ''
        print(f'Problems in{where}:', file=sys.stderr)
        for error in exc.errors:
            print(f'  - {error}', file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: can't open {exc.filename}: {exc.strerror}.", file=sys.stderr)
        return 2
    except (CliError, ValueError, TypeError, RuntimeError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2
    return 0
