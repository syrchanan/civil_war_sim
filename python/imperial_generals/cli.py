"""
Command line for the battle engine (roadmap A9). Run ``python -m imperial_generals --help``.

    python -m imperial_generals new setup.yaml -o battle.json         # start a battle from a setup file
    python -m imperial_generals preview battle.json --orders o.yaml   # who would fight whom, no dice rolled
    python -m imperial_generals resolve battle.json --duration 90 --orders o.yaml
    python -m imperial_generals finish battle.json --field Union      # settle killed / wounded / captured
    python -m imperial_generals show battle.json
    python -m imperial_generals run scenario.yaml                     # setup + scripted rounds, start to end

``resolve`` and ``finish`` update the state file in place unless ``-o`` names another. ``--json`` prints the
machine-readable report instead of a table. Problems exit with code 2 and a message saying what to fix.
"""

import argparse
import json
import sys
from pathlib import Path

from imperial_generals import api
from imperial_generals.battles.setup import SetupError, load_setup_file
from imperial_generals.battles.state import FORMAT


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

def _table(header: list, rows: list, left: int = 2) -> str:
    """Left-align the first ``left`` columns (text) and the last (status notes); right-align the numbers between."""
    cells = [[str(c) for c in row] for row in [header] + rows]
    widths = [max(len(row[i]) for row in cells) for i in range(len(header))]
    lines = []
    for row in cells:
        parts = [c.ljust(w) if i < left or i == len(row) - 1 else c.rjust(w) for i, (c, w) in enumerate(zip(row, widths))]
        lines.append('  '.join(parts).rstrip())
    return '\n'.join(lines)


def _side_names(state: dict) -> list:
    sides = state['meta'].get('sides')
    return sides if isinstance(sides, list) and len(sides) == 2 else ['Side 0', 'Side 1']


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
        notes.append(f'{guns_lost} guns lost')
    return ', '.join(notes)


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
    print()


def _print_result(state: dict, result: dict) -> None:
    sides, names = _side_names(state), _names(state)
    side_of = {u['id']: u['side'] for u in state['units']}
    holder = result['field_held_by']
    print(f"Field held by: {'nobody' if holder is None else sides[holder]}")
    rows = [
        [names[uid], sides[side_of[uid]], o['hits'], o['killed'], o['wounded'], o['wounded_returned'],
         o['captured_in_rout'] + o['wounded_captured'], o['final_size'], o['guns_lost'] or '']
        for uid, o in result['units'].items()
    ]
    print(_table(['Unit', 'Side', 'Hits', 'Killed', 'Wounded', 'Returned', 'Captured', 'Final size', 'Guns lost'],
                 rows))


def _print_state(state: dict) -> None:
    sides = _side_names(state)
    title = state['meta'].get('name', 'Battle')
    finished = ', finished' if state['finished'] else ''
    print(f"{title}: round {state['round']}, {state['time']:.0f} min{finished}")
    rows = []
    for u in state['units']:
        kind = '/'.join(p for p in (u['type'], u['subtype']) if p) or 'generic'
        if 'guns' in u:
            kind += f", {u['guns']} guns"
        rows.append([u['name'], sides[u['side']], kind, u['stats'], u['size'], u['initial_size'],
                     f"{u['raw_morale']:.1f}", _status(u['size'], u['morale']['broken'])])
    print(_table(['Unit', 'Side', 'Type', 'Stats', 'Size', 'Started', 'Morale', 'Status'], rows, left=4))


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
    for report in reports:
        _print_report(state, report)
    if result is not None:
        _print_result(state, result)


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
    p.add_argument('--orders', type=Path, help='orders file: unit id -> {target, mode, ammo}; others idle')
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

    p = commands.add_parser('show', help='summarise a state file')
    p.add_argument('state', type=Path)
    p.set_defaults(run=_cmd_show)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    source = getattr(args, 'setup', None) or getattr(args, 'scenario', None)
    try:
        args.run(args)
    except SetupError as exc:
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
