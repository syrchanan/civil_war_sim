"""
Tuning harness (roadmap A10): run scenarios over many seeds and summarise the spread of outcomes.

- ``run_batch``: one scenario (``api.run_scenario`` format) over a range of seeds, optionally with parameter
  overrides, spread over worker processes. Each seed is independent, so results don't depend on the number of
  workers. Every run is finished (casualties settled): with the scenario's ``finish`` if it names one, else 'auto'.
- ``summarize``: who holds the field, per-side spreads (mean, p10 / p50 / p90), and per-unit break rates.
- ``matchup_grid``: every unit kind in a list attacks every other, one on one, for a fixed set of rounds; the
  cells give win and break rates, casualty shares and exchange ratios. ``plot_matchups`` draws a heatmap.

For parameter search, call ``run_batch(scenario, seeds, overrides=...)`` and score ``summarize(batch)``.
"""

import csv
import math
import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field

from imperial_generals import api
from imperial_generals.battles.battle import MODES
from imperial_generals.battles.setup import UNIT_KEYS, SetupError, battle_from_setup

# summary fields per side, as named in the run rows (prefixed s0_ / s1_)
SIDE_FIELDS = ('units', 'units_out', 'started', 'final', 'loss_share', 'hits_taken', 'hits_inflicted',
               'exchange_ratio', 'prisoners_lost', 'prisoners_taken', 'guns_lost', 'guns_taken')


def quantile(values, q: float):
    """Linear-interpolated quantile of ``values`` (None if empty)."""
    ordered = sorted(values)
    if not ordered:
        return None
    pos = (len(ordered) - 1) * q
    low = math.floor(pos)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


def _spread(values) -> dict:
    values = list(values)
    return {
        'mean': sum(values) / len(values) if values else None,
        'p10': quantile(values, 0.1),
        'p50': quantile(values, 0.5),
        'p90': quantile(values, 0.9),
    }


def _mean(values) -> float:
    values = list(values)
    return sum(values) / len(values)


# =============================================================================
# Running seeds
# =============================================================================

def _play(scenario: dict, seed: int, overrides: dict | None) -> tuple:
    """One finished run: ``(run_row, unit_rows)``."""
    if scenario.get('finish', False) is False:
        scenario = {**scenario, 'finish': True}
    state, reports, result = api.run_scenario(scenario, seed=seed, overrides=overrides)
    broke_at = {}
    for report in reports:
        for uid, unit in report['units'].items():
            if unit['broke_at'] is not None:
                broke_at.setdefault(uid, unit['broke_at'])

    unit_rows = []
    for u in state['units']:
        unit_rows.append({
            'seed': seed, 'id': u['id'], 'name': u['name'], 'side': u['side'],
            'started': u['initial_size'], 'hits': u['losses'], 'captured': u['captured'],
            'final': u['size'], 'inflicted': u['inflicted'], 'broken': u['morale']['broken'],
            'broke_at': broke_at.get(u['id']), 'wiped_out': result['units'][u['id']]['final_size'] == 0,
        })

    charges = [c for report in reports for c in report['charges']]
    row = {'seed': seed, 'field_held_by': result['field_held_by'], 'end_time': state['time'],
           'first_charge': charges[0]['outcome'] if charges else None}
    for side, summary in enumerate(api.side_summary(state)):
        for name in SIDE_FIELDS:
            row[f's{side}_{name}'] = summary[name]
        times = [u['broke_at'] for u in unit_rows if u['side'] == side and u['broke_at'] is not None]
        row[f's{side}_first_break'] = min(times) if times else None
    return row, unit_rows


def _play_chunk(task: tuple) -> list:
    scenario, seeds, overrides = task
    return [_play(scenario, seed, overrides) for seed in seeds]


def _run_tasks(tasks: list, workers: int) -> list:
    """Run ``(scenario, seeds, overrides)`` tasks, in parallel if ``workers > 1``; results in task order."""
    workers = min(workers, len(tasks))
    if workers == 1:
        return [_play_chunk(t) for t in tasks]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_play_chunk, tasks))


def _chunks(seeds: list, n_chunks: int) -> list:
    size = max(1, math.ceil(len(seeds) / n_chunks))
    return [seeds[i:i + size] for i in range(0, len(seeds), size)]


def _check_run_args(seeds: int, workers: int) -> None:
    if not (isinstance(seeds, int) and seeds > 0):
        raise ValueError(f'seeds must be a positive whole number, got {seeds!r}.')
    if not (isinstance(workers, int) and workers > 0):
        raise ValueError(f'workers must be a positive whole number, got {workers!r}.')


def _validate_scenario(scenario: dict, overrides: dict | None) -> None:
    """Raise SetupError for setup, script or override problems before any work is sent out."""
    battle_from_setup(scenario, seed=0, overrides=overrides)
    errors = api._check_script(scenario)
    if errors:
        raise SetupError(errors)


@dataclass
class Batch:
    name: str
    sides: list
    seeds: list
    runs: list = field(default_factory=list)          # one row per seed (see _play)
    unit_runs: list = field(default_factory=list)     # one row per seed per unit


def run_batch(scenario: dict, seeds: int = 100, seed_start: int = 0, overrides: dict | None = None,
              workers: int = 1) -> Batch:
    """
    Run ``scenario`` once per seed in ``seed_start .. seed_start + seeds - 1``.

    Raises
    ------
    SetupError
        For problems in the scenario or the overrides, before anything runs.
    ValueError
        If seeds or workers isn't a positive whole number.
    """
    _check_run_args(seeds, workers)
    _validate_scenario(scenario, overrides)
    seed_list = list(range(seed_start, seed_start + seeds))
    tasks = [(scenario, chunk, overrides) for chunk in _chunks(seed_list, workers * 4)]
    batch = Batch(name=scenario.get('meta', {}).get('name', 'Scenario'), sides=api._side_names(
        {'meta': {'sides': scenario.get('sides')}}), seeds=seed_list)
    for chunk in _run_tasks(tasks, workers):
        for row, unit_rows in chunk:
            batch.runs.append(row)
            batch.unit_runs.extend(unit_rows)
    return batch


def summarize(batch: Batch) -> dict:
    """The spread of outcomes over a batch: field holder shares, per-side spreads, per-unit break rates."""
    runs, n = batch.runs, len(batch.runs)
    holders = {name: sum(r['field_held_by'] == side for r in runs) / n for side, name in enumerate(batch.sides)}
    holders['nobody'] = sum(r['field_held_by'] is None for r in runs) / n

    sides = []
    for side, name in enumerate(batch.sides):
        p = f's{side}_'
        breaks = [r[p + 'first_break'] for r in runs if r[p + 'first_break'] is not None]
        sides.append({
            'name': name,
            'units': runs[0][p + 'units'],
            'loss_share': _spread(r[p + 'loss_share'] for r in runs),
            'exchange_ratio': _spread(r[p + 'exchange_ratio'] for r in runs if r[p + 'exchange_ratio'] is not None),
            'units_out_mean': _mean(r[p + 'units_out'] for r in runs),
            'first_break': {'share': len(breaks) / n, 'p50': quantile(breaks, 0.5)},
            'prisoners_taken_mean': _mean(r[p + 'prisoners_taken'] for r in runs),
            'guns_taken_mean': _mean(r[p + 'guns_taken'] for r in runs),
        })

    units = []
    for first in (u for u in batch.unit_runs if u['seed'] == batch.seeds[0]):
        rows = [u for u in batch.unit_runs if u['id'] == first['id']]
        units.append({
            'id': first['id'], 'name': first['name'], 'side': first['side'],
            'break_share': sum(u['broken'] for u in rows) / n,
            'broke_at_p50': quantile([u['broke_at'] for u in rows if u['broke_at'] is not None], 0.5),
            'hit_share': _spread(u['hits'] / u['started'] for u in rows),
            'inflicted_mean': _mean(u['inflicted'] for u in rows),
        })
    return {'name': batch.name, 'seeds': n, 'field': holders, 'sides': sides, 'units': units}


def write_csv(rows: list, path) -> None:
    """Write rows (dicts with the same keys) as CSV, e.g. ``batch.runs`` or ``grid.rows()``."""
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


# =============================================================================
# Matchup grid
# =============================================================================

GRID_KEYS = ('name', 'params', 'rounds', 'seeds', 'units')
GRID_UNIT_KEYS = tuple(sorted(set(UNIT_KEYS) - {'id', 'name', 'side'} | {'attack', 'defend'}))
ORDER_KEYS = {'mode', 'ammo'}


def _order(value) -> dict | None:
    """The order dict for an attack/defend value, or None if it isn't valid."""
    if isinstance(value, str):
        value = {'mode': value}
    if isinstance(value, dict) and set(value) <= ORDER_KEYS and value.get('mode') in MODES:
        return dict(value)
    return None


def _round_list(value) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(r, (int, float)) and not isinstance(r, bool) and r > 0 for r in value)


def _facet_rounds(spec: dict, mode: str) -> list:
    """Round lengths for one grid: ``rounds`` is a list for every grid, or a mapping with a 'default'."""
    rounds = spec['rounds']
    return list(rounds.get(mode, rounds['default']) if isinstance(rounds, dict) else rounds)


def _check_grid(spec) -> None:
    if not isinstance(spec, dict):
        raise SetupError(['The matchup file must be a mapping with "units" and "rounds".'])
    errors = [f'Unknown key "{k}". Allowed: {", ".join(GRID_KEYS)}.' for k in spec if k not in GRID_KEYS]
    rounds = spec.get('rounds')
    if isinstance(rounds, dict):
        if 'default' not in rounds:
            errors.append('"rounds" by grid needs a "default" list, e.g. {default: [90], charge: [30]}.')
        errors.extend(f'"rounds": unknown grid "{k}"; use default or {", ".join(MATCHUP_MODES)}.'
                      for k in rounds if k != 'default' and k not in MATCHUP_MODES)
        errors.extend(f'"rounds" for {k} must be a list of round lengths in minutes, e.g. [90, 90].'
                      for k, v in rounds.items() if not _round_list(v))
    elif not _round_list(rounds):
        errors.append('"rounds" must be a list of round lengths in minutes, e.g. [90, 90].')
    seeds = spec.get('seeds', 100)
    if not (isinstance(seeds, int) and not isinstance(seeds, bool) and seeds > 0):
        errors.append('"seeds" must be a positive whole number.')
    units = spec.get('units')
    if not (isinstance(units, dict) and units):
        errors.append('"units" must map names to unit specs (type, subtype, size, stats, attack, defend).')
        units = {}
    for key, unit in units.items():
        where = f'units.{key}'
        if not isinstance(unit, dict):
            errors.append(f'{where}: must be a mapping.')
            continue
        unknown = [k for k in unit if k not in GRID_UNIT_KEYS]
        errors.extend(f'{where}: unknown key "{k}". Allowed: {", ".join(GRID_UNIT_KEYS)}.' for k in unknown)
        for role in ('attack', 'defend'):
            if role in unit and _order(unit[role]) is None:
                errors.append(f'{where}: {role} must be ranged, melee, idle or {{mode, ammo}}; got {unit[role]!r}.')
        build = {k: v for k, v in unit.items() if k in UNIT_KEYS}
        try:
            battle_from_setup({'units': [{'id': 'x', 'side': 0, **build},
                                         {'id': 'y', 'side': 1, 'size': 10, 'stats': '5/5/0/0'}]}, seed=0)
        except SetupError as exc:
            errors.extend(f"{where}: {e.removeprefix('Unit 1 (x): ')}" for e in exc.errors)
    if isinstance(spec.get('params', {}), dict):
        try:
            battle_from_setup({'units': [{'id': 'x', 'side': 0, 'size': 10, 'stats': '5/5/0/0'},
                                         {'id': 'y', 'side': 1, 'size': 10, 'stats': '5/5/0/0'}],
                               'params': spec.get('params', {})}, seed=0)
        except SetupError as exc:
            errors.extend(exc.errors)
    if errors:
        raise SetupError(errors)


MATCHUP_MODES = ('orders', 'ranged', 'melee', 'charge', 'artillery')


def _facet(order: dict, mode: str) -> dict:
    """An attack / defend order forced to ``mode``: ranged keeps any artillery ammo, melee drops it."""
    if mode == 'orders':
        return order
    if mode in ('ranged', 'artillery'):
        return {'mode': 'ranged', **({'ammo': order['ammo']} if 'ammo' in order else {})}
    return {'mode': 'melee'}


def _is_artillery(spec: dict, key: str) -> bool:
    return spec['units'][key].get('type') == 'art'


def matchup_scenario(spec: dict, attacker: str, defender: str, mode: str = 'orders') -> dict:
    """
    The one-on-one scenario for one grid cell. With ``mode='orders'`` the attacker uses its attack order and the
    defender its defend reply; 'ranged' makes both fire (melee-only units can't, so they inflict nothing) and
    'melee' makes both fight hand to hand (they meet head on). 'charge' has the attacker charge while the
    defender stands and fires (if it can): the approach and contact test decide. 'artillery' is a battery firing at long range: only another battery
    can reply, so against anything else the fire is unreturned.
    """
    def unit(key: str, uid: str, side: int) -> dict:
        body = {k: v for k, v in spec['units'][key].items() if k not in ('attack', 'defend')}
        return {'id': uid, 'name': key, 'side': side, **body}

    attack_mode, defend_mode = ('melee', 'ranged') if mode == 'charge' else (mode, mode)
    orders = {'attacker': {'target': 'defender',
                           **_facet(_order(spec['units'][attacker].get('attack', 'ranged')), attack_mode)}}
    defend = _facet(_order(spec['units'][defender].get('defend', 'ranged')), defend_mode)
    out_of_reach = mode == 'artillery' and not _is_artillery(spec, defender)
    if defend['mode'] != 'idle' and not out_of_reach:
        orders['defender'] = {'target': 'attacker', **defend}
    scenario = {
        'meta': {'name': f'{attacker} attacks {defender}'},
        'units': [unit(attacker, 'attacker', 0), unit(defender, 'defender', 1)],
        'rounds': [{'duration': d, 'orders': orders} for d in _facet_rounds(spec, mode)],
    }
    if spec.get('params'):
        scenario['params'] = spec['params']
    return scenario


@dataclass
class MatchupGrid:
    name: str
    keys: list
    seeds: int
    rounds: list
    cells: dict          # (attacker, defender) -> outcome shares and rates
    mode: str = 'orders'     # 'orders' (from the file), 'ranged', 'melee' or 'artillery'
    attackers: list = field(default_factory=list)   # row units: every unit, or only batteries (artillery)

    def rows(self) -> list:
        return [{'mode': self.mode, 'attacker': a, 'defender': d, **self.cells[(a, d)]}
                for a in self.attackers for d in self.keys]


def _cell(results: list) -> dict:
    """Outcome of one grid cell over its seeds."""
    n = len(results)
    rows = [row for row, _ in results]
    attacker_out = [r['s0_units_out'] == 1 for r in rows]
    defender_out = [r['s1_units_out'] == 1 for r in rows]
    taken = sum(r['s0_hits_taken'] for r in rows)
    inflicted = sum(r['s0_hits_inflicted'] for r in rows)
    attacker_wins = sum(d and not a for a, d in zip(attacker_out, defender_out)) / n
    defender_wins = sum(a and not d for a, d in zip(attacker_out, defender_out)) / n
    return {
        'attacker_wins': attacker_wins,
        'defender_wins': defender_wins,
        'advantage': attacker_wins - defender_wins,
        'attacker_breaks': sum(attacker_out) / n,
        'defender_breaks': sum(defender_out) / n,
        'attacker_hit_share': _mean(r['s0_hits_taken'] / r['s0_started'] for r in rows),
        'defender_hit_share': _mean(r['s1_hits_taken'] / r['s1_started'] for r in rows),
        'exchange_ratio': inflicted / taken if taken else None,
        # how the cell's charge ended (0 when nobody charged)
        'charge_home': sum(r['first_charge'] == 'home' for r in rows) / n,
        'charge_faltered': sum(r['first_charge'] == 'faltered' for r in rows) / n,
        'charge_broke_defender': sum(r['first_charge'] == 'defender_broke' for r in rows) / n,
    }


def matchup_grid(spec: dict, seeds: int | None = None, workers: int = 1, overrides: dict | None = None,
                 mode: str = 'orders') -> MatchupGrid:
    """
    Every unit in ``spec['units']`` attacks every unit (itself included), one on one, for ``spec['rounds']``
    (a list, or a mapping by grid with a 'default', e.g. ``{default: [90], charge: [30]}``).
    ``mode`` facets the grid: 'orders' uses each unit's attack / defend from the file, 'ranged' makes every
    unit fire, 'melee' makes every unit fight hand to hand, 'charge' has every unit charge into the defender's
    fire; 'artillery' has only the batteries attack, at long
    range, where only batteries can reply (see ``matchup_scenario``).

    A side wins a cell's run when the other unit broke or was wiped out and it didn't. ``advantage`` is the
    attacker's win share minus the defender's; ``exchange_ratio`` is defender men hit per attacker man hit.

    Raises
    ------
    SetupError
        For problems in the spec or the overrides, before anything runs.
    """
    if mode not in MATCHUP_MODES:
        raise ValueError(f"mode must be one of {', '.join(MATCHUP_MODES)}, got {mode!r}.")
    _check_grid(spec)
    seeds = seeds if seeds is not None else spec.get('seeds', 100)
    _check_run_args(seeds, workers)
    keys = list(spec['units'])
    attackers = [k for k in keys if _is_artillery(spec, k)] if mode == 'artillery' else keys
    if not attackers:
        raise ValueError('The artillery grid needs at least one artillery unit (type: art).')
    pairs = [(a, d) for a in attackers for d in keys]
    _validate_scenario(matchup_scenario(spec, attackers[0], keys[0], mode), overrides)
    per_cell = max(1, workers * 4 // len(pairs))
    tasks, owners = [], []
    for pair in pairs:
        scenario = matchup_scenario(spec, *pair, mode)
        for chunk in _chunks(list(range(seeds)), per_cell):
            tasks.append((scenario, chunk, overrides))
            owners.append(pair)
    results: dict = {pair: [] for pair in pairs}
    for pair, chunk in zip(owners, _run_tasks(tasks, workers)):
        results[pair].extend(chunk)
    return MatchupGrid(name=spec.get('name', 'Matchups'), keys=keys, seeds=seeds, rounds=_facet_rounds(spec, mode),
                       cells={pair: _cell(results[pair]) for pair in pairs}, mode=mode, attackers=attackers)


# =============================================================================
# Heatmap
# =============================================================================

# diverging red (defender ahead) - neutral gray - blue (attacker ahead); sequential light gray to blue
_RED, _NEUTRAL, _BLUE, _DEEP_BLUE = '#e34948', '#f0efec', '#2a78d6', '#163e70'
_INK, _MUTED, _SURFACE = '#1f1f1e', '#6b6a66', '#fcfcfb'


def plot_matchups(grid: MatchupGrid, path, metric: str = 'advantage') -> None:
    """
    Save a heatmap of one cell metric (rows: attacker, columns: defender) as an image.

    ``advantage`` uses a diverging scale from -100% (defender always wins) to +100% (attacker always wins);
    share metrics (wins, breaks, hit shares) use a sequential 0-100% scale.
    """
    from matplotlib.colors import LinearSegmentedColormap
    from matplotlib.figure import Figure
    from matplotlib.ticker import PercentFormatter

    keys, rows = grid.keys, grid.attackers
    values = [[grid.cells[(a, d)][metric] for d in keys] for a in rows]
    if metric == 'advantage':
        cmap = LinearSegmentedColormap.from_list('advantage', [_RED, _NEUTRAL, _BLUE])
        vmin, vmax = -1, 1
    else:
        cmap = LinearSegmentedColormap.from_list('share', [_NEUTRAL, _BLUE, _DEEP_BLUE])
        vmin, vmax = 0, 1

    width = 1.0 + 0.9 * len(keys)
    fig = Figure(figsize=(width + 1.6, 2.2 + 0.9 * len(rows)), facecolor=_SURFACE)
    ax = fig.add_subplot()
    ax.set_facecolor(_SURFACE)
    mesh = ax.pcolormesh(values, cmap=cmap, vmin=vmin, vmax=vmax, edgecolors=_SURFACE, linewidth=2)
    ax.invert_yaxis()
    ax.set_xticks([i + 0.5 for i in range(len(keys))], keys, rotation=30, ha='right', color=_INK)
    ax.set_yticks([i + 0.5 for i in range(len(rows))], rows, color=_INK)
    ax.set_xlabel('Defender', color=_MUTED)
    ax.set_ylabel('Attacker', color=_MUTED)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    for i, row in enumerate(values):
        for j, v in enumerate(row):
            # the cell value is the table view; light text only on the darkest cells
            dark = abs(v) > 0.6 if metric == 'advantage' else v > 0.6
            ax.text(j + 0.5, i + 0.5, f'{v:+.0%}' if metric == 'advantage' else f'{v:.0%}',
                    ha='center', va='center', fontsize=9, color=_SURFACE if dark else _INK)
    bar = fig.colorbar(mesh, ax=ax, fraction=0.05, pad=0.03)
    bar.outline.set_visible(False)
    bar.ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    bar.ax.tick_params(colors=_MUTED, length=0)
    label = 'attacker wins - defender wins' if metric == 'advantage' else metric.replace('_', ' ')
    bar.set_label(label, color=_MUTED)
    rounds = ' + '.join(f'{r:g}' for r in grid.rounds)
    ax.set_title(f'{grid.name} ({grid.mode}): {label}\n{grid.seeds} seeds per cell, rounds {rounds} min', color=_INK,
                 fontsize=10, loc='left')
    fig.tight_layout()
    fig.savefig(path, dpi=150)


def default_workers() -> int:
    return os.cpu_count() or 1
