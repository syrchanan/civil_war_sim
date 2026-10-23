"""
Parity fixtures for the TypeScript port (roadmap B2).

Each fixture is JSON the port must reproduce exactly: inputs plus the Python engine's outputs. They are committed
under ``test_cases/parity/`` and a test fails if one is out of date, so regenerate after changing the engine:

    python -m imperial_generals.parity

``fdlibm.json`` in the same folder is not generated: it holds V8's ``Math.log`` / ``Math.exp`` results, the
reference both languages are checked against.

The same command writes ``web/src/engine/defaults.json``, the engine defaults the port runs on: ``config/*.yaml``
stays the one source.
"""

import json
from pathlib import Path

from imperial_generals.config import get_config
from imperial_generals.params import BattleParams
from imperial_generals.utils import Rng
from imperial_generals.utils.unit_types import UNIT_SUBTYPES

ROOT = Path(__file__).resolve().parents[2]
PARITY_DIR = ROOT / 'test_cases' / 'parity'
DEFAULTS_PATH = ROOT / 'web' / 'src' / 'engine' / 'defaults.json'

DRAWS = 8


def _rng_case(seed: int, rate: float) -> dict:
    """One generator, drawn in order: u32s, then uniforms, then exponentials, then its state."""
    rng = Rng(seed)
    state = rng.state
    u32 = [rng.next_u32() for _ in range(DRAWS)]
    uniform = [rng.random() for _ in range(DRAWS)]
    exponential = [rng.exponential(rate) for _ in range(DRAWS)]
    return {'seed': seed, 'state': state, 'u32': u32, 'random': uniform,
            'exponential': {'rate': rate, 'values': exponential}, 'state_after': rng.state}


def rng_fixture() -> dict:
    cases = [(0, 1.0), (1, 0.37), (42, 12.5), (123456789, 0.004), (2**32 - 1, 250.0)]
    return {'description': 'Rng(seed): state, then in order next_u32 x8, random x8, exponential(rate) x8, '
                           'and the state after.',
            'cases': [_rng_case(seed, rate) for seed, rate in cases]}


def _unit_keys() -> list:
    """Every (type, subtype | None) the engine can meet."""
    return [(t, s) for t in ('inf', 'cav', 'art') for s in [None] + sorted(UNIT_SUBTYPES[t])]


def _key(unit: tuple) -> str:
    return unit[0] if unit[1] is None else f'{unit[0]}/{unit[1]}'


# Overrides the port must accept (with the resulting params) or reject
VALID_OVERRIDES = [
    {},
    {'combat': {'ranged_kill_rate': 0.01, 'weapon_multipliers': {'1': 1.8}}},
    {'morale': {'shock_weight': 0.0, 'break_fraction_min': 0.2}},
    {'aftermath': {'field_votes_needed': 3}},
    {'matchups': {'ranged': {'inf': {'cav': 1.5}}, 'melee_ratings': {'inf/line': 0.9},
                  'overrides': [{'attacker': 'cav/heavy', 'target': 'inf', 'mode': 'melee', 'multiplier': 1.3}]}},
    {'charge': {'approach_minutes': {'cav': 3.0}, 'shock_bonus': []}},
]
INVALID_OVERRIDES = [
    {'weather': {}},
    {'combat': {'not_a_key': 1}},
    {'combat': {'weapon_multipliers': {'7': 1.0}}},
    {'combat': {'ranged_kill_rate': 0.0}},
    {'combat': {'artillery_default_ammo': 'grape'}},
    {'morale': {'break_fraction_min': 0.9}},
    {'aftermath': {'field_votes_needed': 4}},
    {'aftermath': {'field_votes_needed': 1.5}},
    {'matchups': {'ranged': {'inf': {'cav': -1.0}}}},
    {'matchups': {'overrides': [{'attacker': 'inf/hussars', 'target': 'cav', 'mode': 'melee', 'multiplier': 1.0}]}},
    {'matchups': {'melee_ratings': {'inf': 1.0}}},
    {'charge': {'spread': 0.0}},
    {'charge': {'approach_minutes': {'navy': 1.0}}},
    {'charge': {'shock_bonus': [{'charger': 'cav', 'target': 'inf'}]}},
    {'charge': {'battery_closing_ammo': 'grape'}},
]


def params_fixture() -> dict:
    p = BattleParams()
    combat, matchups, charge = p.combat, p.matchups, p.charge
    # raw morale halves (25, 35, ...) catch Python's round-half-to-even
    morales = [1, 5, 6, 10, 11, 15, 25, 35, 45, 55, 65, 75, 85, 95, 100]
    efficiency = [[xp, m, w, melee, combat.efficiency(xp, m, w, melee)]
                  for xp in (1, 4, 10, 12, 0) for m in morales for w in (-2, -1, 0, 1, 2, 3) for melee in (0, 1)]
    stats = [(5, 5, 0, 0), (8, 8, 1, 0), (2, 2, -1, 0), (4, 5, -2, 1), (10, 10, 2, 0), (3, 7, 0, 1)]
    unit_coef = [[list(s), mode, combat.unit_coef(s, mode)] for s in stats for mode in ('idle', 'ranged', 'melee')]
    melee_efficiency = [[xp, m, r, combat.melee_efficiency(xp, m, r)]
                        for xp in (1, 5, 10) for m in (1, 5, 10, 25, 55) for r in (0.25, 0.7, 1.4)]
    keys = _unit_keys()
    multiplier = [[_key(a), _key(t), mode, matchups.multiplier(a, t, mode)]
                  for a in keys for t in keys for mode in ('ranged', 'melee')]
    melee_rating = [[_key(u), matchups.melee_rating(u)] for u in keys]
    steadiness = [[r, xp, s, charge.steadiness(r, xp, s)]
                  for r in (1.0, 0.5, 0.1) for xp in (1, 5, 10, 0, 11) for s in (0.0, 0.3, 2.0)]
    bonus = [[_key(a), _key(t), charge.bonus(a, t)] for a in keys for t in keys]
    pressure = [[cm, tm, cs, ts, b, charge.pressure(cm, tm, cs, ts, b)]
                for cm, tm in ((500, 500), (1000, 400), (300, 900)) for cs, ts in ((0.8, 0.8), (0.9, 0.3))
                for b in (0.0, 0.5, -2.0)]
    odds = [[x, list(charge.odds(x))] for x in (-4.0, -1.5, -0.5, 0.0, 0.37, 1.0, 2.5, 6.0)]
    return {
        'description': 'BattleParams: defaults (see web/src/engine/defaults.json) and what each section computes; '
                       'overrides that are accepted (with the resulting params) or rejected.',
        'combat': {'efficiency': efficiency, 'unit_coef': unit_coef, 'melee_efficiency': melee_efficiency},
        'matchups': {'multiplier': multiplier, 'melee_rating': melee_rating},
        'charge': {'steadiness': steadiness, 'bonus': bonus, 'pressure': pressure, 'odds': odds},
        'overrides': {'valid': [[o, p.with_overrides(o).to_dict()] for o in VALID_OVERRIDES],
                      'invalid': INVALID_OVERRIDES},
    }


FIXTURES = {
    'rng': rng_fixture,
    'params': params_fixture,
}


def defaults() -> dict:
    """Everything the engine reads from config: battle params, the morale scale, unit subtypes, the battery template."""
    cfg = get_config()
    return {
        'description': 'Engine defaults from config/*.yaml. Generated: python -m imperial_generals.parity',
        'params': BattleParams().to_dict(),
        'morale_scale': {k: cfg['morale'][k] for k in ('min_raw', 'max_raw', 'raw_scale_factor')},
        'unit_subtypes': {unit_type: sorted(subtypes) for unit_type, subtypes in UNIT_SUBTYPES.items()},
        'artillery': dict(cfg['artillery']),
    }


def build(name: str) -> dict:
    """The fixture ``name`` as the Python engine computes it now."""
    return FIXTURES[name]()


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8', newline='\n')


def write_all(directory: Path = PARITY_DIR, defaults_path: Path = DEFAULTS_PATH) -> None:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name in FIXTURES:
        _write_json(directory / f'{name}.json', build(name))
    _write_json(Path(defaults_path), defaults())


if __name__ == '__main__':  # pragma: no cover
    write_all()
