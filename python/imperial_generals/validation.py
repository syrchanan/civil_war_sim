"""
Player validation scenarios (roadmap A11): say what should happen, then see how often the engine agrees.

A scenario's ``expect`` block records a player's (or a historical source's) expectations:

    expect:
      author: Jane
      source: "Gettysburg, 2 July 1863 (Fox 1889)"
      confidence: medium              # low / medium / high
      field_held_by: Union            # side name, 0, 1 or none
      breaks: [cs_8al]                # these units should break
      holds: [us_1mn]                 # these should not
      casualties:                     # killed + wounded + prisoners, share of starting strength
        Union: 10-25%                 # by side name, or for whichever side won / lost
        loser: 25-35%
      notes: free text

``check`` runs the scenario over many seeds and grades each expectation by the share of runs that agree:
'agrees', 'sometimes' or 'disagrees' (thresholds in config/validation.yaml). A run's winner is the side holding
the field; failing that, the side with the smaller share of its men in broken or wiped-out units. Runs with
neither are left out of winner / loser expectations.
"""

import hashlib
import json
import re

from imperial_generals import tuning
from imperial_generals.battles.setup import SetupError
from imperial_generals.config import get_config
from imperial_generals.params import BattleParams

EXPECT_KEYS = ('author', 'breaks', 'casualties', 'confidence', 'field_held_by', 'holds', 'notes', 'source')
CONFIDENCE = ('low', 'medium', 'high')
_BAND = re.compile(r'^\s*([<>])?\s*(\d+(?:\.\d+)?)\s*%?\s*(?:[-–—]\s*(\d+(?:\.\d+)?)\s*%?)?\s*$')


def parse_band(text) -> tuple:
    """A casualty band as (low, high) shares: '25-35%', '<10%' or '>40%' (percent of starting strength)."""
    match = _BAND.match(text) if isinstance(text, str) else None
    if match is None or (match.group(1) is None) == (match.group(3) is None):
        raise ValueError(f'not a band: {text!r}')
    a = float(match.group(2)) / 100
    if match.group(1) == '<':
        low, high = 0.0, a
    elif match.group(1) == '>':
        low, high = a, 1.0
    else:
        low, high = a, float(match.group(3)) / 100
    if not 0 <= low <= high <= 1:
        raise ValueError(f'not a band: {text!r}')
    return low, high


def _band_text(band: tuple) -> str:
    low, high = band
    if low == 0:
        return f'under {high:.0%}'
    if high == 1:
        return f'over {low:.0%}'
    return f'{low:.0%}-{high:.0%}'


def _sides(scenario: dict) -> list | None:
    sides = scenario.get('sides')
    return sides if isinstance(sides, list) and len(sides) == 2 else None


def _side_number(value, sides):
    if type(value) is int and value in (0, 1):
        return value
    if sides is not None and value in sides:
        return sides.index(value)
    return None


def read_expect(scenario: dict) -> dict | None:
    """The scenario's ``expect`` block, checked and normalised (sides as numbers, bands as shares); None if absent."""
    if 'expect' not in scenario:
        return None
    exp = scenario['expect']
    if not isinstance(exp, dict):
        raise SetupError(['expect must be a mapping (field_held_by, breaks, holds, casualties, ...).'])
    sides = _sides(scenario)
    side_names = f'a side name ({", ".join(sides)})' if sides else 'a side'
    unit_ids = {u.get('id', u.get('name')) for u in scenario.get('units', []) if isinstance(u, dict)}
    errors = [f'expect: unknown key "{k}". Allowed: {", ".join(EXPECT_KEYS)}.' for k in exp if k not in EXPECT_KEYS]
    out = {k: exp.get(k) for k in ('author', 'source', 'notes')}

    confidence = exp.get('confidence')
    if confidence is not None and str(confidence).lower() not in CONFIDENCE:
        errors.append('expect.confidence must be low, medium or high.')
    out['confidence'] = None if confidence is None else str(confidence).lower()

    out['field_held_by'] = 'unset'
    if 'field_held_by' in exp:
        value = exp['field_held_by']
        if value is None or value == 'none':
            out['field_held_by'] = None
        elif (side := _side_number(value, sides)) is not None:
            out['field_held_by'] = side
        else:
            errors.append(f'expect.field_held_by must be {side_names}, 0, 1 or none; got {value!r}.')

    for key in ('breaks', 'holds'):
        units = exp.get(key, [])
        if not isinstance(units, list):
            errors.append(f'expect.{key} must be a list of unit ids.')
            units = []
        errors.extend(f'expect.{key}: unknown unit "{u}".' for u in units if u not in unit_ids)
        out[key] = list(units)
    errors.extend(f'expect: "{u}" can\'t both break and hold.' for u in out['breaks'] if u in out['holds'])

    out['casualties'] = {}
    casualties = exp.get('casualties', {})
    if not isinstance(casualties, dict):
        errors.append('expect.casualties must map sides to bands like "25-35%".')
        casualties = {}
    for who, band in casualties.items():
        key = who if who in ('winner', 'loser') else _side_number(who, sides)
        if key is None:
            errors.append(f'expect.casualties: "{who}" must be {side_names}, winner or loser.')
            continue
        try:
            out['casualties'][key] = parse_band(band)
        except ValueError:
            errors.append(f'expect.casualties.{who}: write a band like "25-35%", "<10%" or ">40%".')
    if errors:
        raise SetupError(errors)
    return out


def engine_stamp(params: BattleParams | None = None) -> str:
    """A short fingerprint of the engine's tuning, so feedback can say which version it was about."""
    data = (params or BattleParams()).to_dict()
    return hashlib.sha1(json.dumps(data, sort_keys=True).encode()).hexdigest()[:8]


def verdict(share: float | None) -> str:
    if share is None:
        return 'undecided'
    cfg = get_config()['validation']
    if share >= cfg['agrees_at']:
        return 'agrees'
    if share >= cfg['sometimes_at']:
        return 'sometimes'
    return 'disagrees'


def _winner(run: dict):
    """The side that won a run: the field holder, else the side with fewer of its men broken; None if neither."""
    if run['field_held_by'] is not None:
        return run['field_held_by']
    out0, out1 = run['s0_men_out'], run['s1_men_out']
    if out0 == out1:
        return None
    return 0 if out0 < out1 else 1


def _spread_text(values: list) -> str:
    q = tuning.quantile
    return f'typically {q(values, .5):.0%} (8 in 10 runs: {q(values, .1):.0%}-{q(values, .9):.0%})'


def check(scenario: dict, seeds: int | None = None, seed_start: int = 0, workers: int = 1,
          overrides: dict | None = None) -> dict:
    """
    Run ``scenario`` over many seeds and grade each of its expectations.

    Returns a dict with the scenario ``name``, ``seeds``, the ``engine`` stamp, the expectation's ``author``,
    ``source`` and ``confidence``, and ``expectations``: one entry per expectation with its ``text``, the
    ``share`` of runs that agree (None if no run could be graded), a ``verdict`` and what the ``engine`` typically
    did. ``agree`` / ``total`` count the graded expectations.

    Raises
    ------
    SetupError
        For problems in the scenario or its expect block, or if it has none.
    """
    exp = read_expect(scenario)
    if exp is None:
        raise SetupError(['This scenario has no "expect" block: say what should happen.'])
    seeds = seeds or get_config()['validation']['default_seeds']
    batch = tuning.run_batch(scenario, seeds=seeds, seed_start=seed_start, overrides=overrides, workers=workers)
    runs, n = batch.runs, len(batch.runs)
    names = batch.sides
    unit_names = {u['id']: u['name'] for u in batch.unit_runs if u['seed'] == batch.seeds[0]}
    results = []

    def add(kind, text, share, engine):
        results.append({'kind': kind, 'text': text, 'share': share, 'verdict': verdict(share), 'engine': engine})

    if exp['field_held_by'] != 'unset':
        want = exp['field_held_by']
        who = 'Nobody holds' if want is None else f'{names[want]} holds'
        held = {name: sum(r['field_held_by'] == side for r in runs) / n for side, name in enumerate(names)}
        held['nobody'] = sum(r['field_held_by'] is None for r in runs) / n
        add('field_held_by', f'{who} the field', sum(r['field_held_by'] == want for r in runs) / n,
            ', '.join(f'{k} {v:.0%}' for k, v in held.items()))

    for key, should_break in (('breaks', True), ('holds', False)):
        for uid in exp[key]:
            rows = [u for u in batch.unit_runs if u['id'] == uid]
            out = [u['broken'] or u['wiped_out'] for u in rows]
            share = sum(o == should_break for o in out) / n
            times = [u['broke_at'] for u in rows if u['broke_at'] is not None]
            when = f' (typically at {tuning.quantile(times, .5):.0f} min)' if times else ''
            text = f'{unit_names[uid]} breaks' if should_break else f'{unit_names[uid]} holds'
            add(key, text, share, f'breaks in {sum(out) / n:.0%} of runs{when}')

    for who, band in exp['casualties'].items():
        if who in ('winner', 'loser'):
            values = []
            for r in runs:
                winner = _winner(r)
                if winner is not None:
                    side = winner if who == 'winner' else 1 - winner
                    values.append(r[f's{side}_casualty_share'])
            label = who.capitalize()
        else:
            values = [r[f's{who}_casualty_share'] for r in runs]
            label = names[who]
        text = f'{label} casualties {_band_text(band)}'
        if not values:
            add('casualties', text, None, 'no run had a clear winner')
            continue
        share = sum(band[0] <= v <= band[1] for v in values) / len(values)
        add('casualties', text, share, _spread_text(values))

    graded = [r for r in results if r['share'] is not None]
    return {
        'name': batch.name, 'seeds': n, 'engine': engine_stamp(), 'author': exp['author'],
        'source': exp['source'], 'confidence': exp['confidence'], 'notes': exp['notes'],
        'expectations': results, 'agree': sum(r['verdict'] == 'agrees' for r in graded), 'total': len(graded),
        'feedback': list(scenario.get('feedback') or []),
    }
