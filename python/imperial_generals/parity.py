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


def _morale_script(rng: Rng, steps: int) -> list:
    """A random but recorded sequence of morale operations (the port replays the list, not the draws)."""
    ops = []
    for _ in range(steps):
        u = rng.random()
        if u < 0.45:
            ops.append(['take_loss', rng.random() < 0.7])
        elif u < 0.65:
            ops.append(['advance', round(rng.random() * 12, 3), rng.random() < 0.8])
        elif u < 0.9:
            ops.append(['inflict_loss', 100 + int(rng.random() * 1900)])
        elif u < 0.97:
            ops.append(['advance', 0.0, True])
        else:
            ops.append(['shake', 0.15])
    return ops


def _morale_case(size: int, xp: int, morale_stat: int, scale: float, seed: int, steps: int,
                 overrides: dict | None = None, force_break_at: int | None = None) -> dict:
    from imperial_generals.battles.morale import MoraleState
    params = BattleParams().with_overrides({'morale': overrides or {}}).morale
    state = MoraleState(size, xp, morale_stat, params=params, break_scale=scale)
    ops = _morale_script(Rng(seed), steps)
    if force_break_at is not None:
        ops.insert(force_break_at, ['force_break'])
    after = []
    for op in ops:
        getattr(state, op[0])(*op[1:])
        after.append([state.resolve, state.shock, state.lost, state.broken, state.morale])
    return {'size': size, 'xp': xp, 'morale_stat': morale_stat, 'break_scale': scale, 'overrides': overrides or {},
            'break_fraction': state.break_fraction, 'ops': ops, 'after': after}


def morale_fixture() -> dict:
    from imperial_generals.battles.morale import break_fraction, break_scale
    p = BattleParams().morale
    fractions = [[xp, m, break_fraction(xp, m, p)] for xp in range(0, 12) for m in range(0, 12)]
    curve = BattleParams().with_overrides({'morale': {'break_curve': 0.7, 'experience_weight': 0.2}}).morale
    fractions += [[xp, m, break_fraction(xp, m, curve), 'curve'] for xp in (1, 3, 7, 10) for m in (1, 4, 10)]
    scales = [[u, s, break_scale(u, s)] for u in (0.0, 1e-15, 0.01, 0.25, 0.5, 0.73, 0.99, 1.0) for s in (0.0, 0.12, 1.0)]
    cases = [
        _morale_case(500, 5, 5, 1.0, 1, 300),
        _morale_case(1000, 8, 9, 1.17, 2, 400),
        _morale_case(120, 2, 2, 0.83, 3, 200),
        _morale_case(800, 5, 6, 1.0, 4, 300, overrides={'size_exponent': 0.3, 'acceleration': 0.0,
                                                        'helpless_weight': 1.2}),
        _morale_case(300, 6, 4, 1.05, 5, 150, force_break_at=60),
    ]
    return {'description': "MoraleState: each case replays 'ops' in order and records "
                           "[resolve, shock, lost, broken, morale] after each; plus break_fraction "
                           "[xp, morale, value(, 'curve': break_curve 0.7, experience_weight 0.2)] and "
                           "break_scale [u, spread, value].",
            'break_fraction': fractions, 'break_scale': scales, 'cases': cases}


STATS_VALID = ['4/4/0/0', '10/10/2/1', '1/1/-2/0', '3/7/-1/1', '0/0/0/0', '12/15/3/2', '04/5/0/0']
STATS_INVALID = ['4/4/0', '4/4/0/0/0', '4/-4/0/0', '-4/4/0/0', '4/4/0/-1', 'a/4/0/0', '4.5/4/0/0', ' 4/4/0/0',
                 '4/4/0/0 ', '', '4//0/0', '4/4/+1/0']


def units_fixture() -> dict:
    from imperial_generals.units import ArtilleryBattery, Regiment
    from imperial_generals.utils import get_closest_morale_stat
    raws = sorted({i / 4 for i in range(0, 401)} | {14.999999999999998, 15.000000000000002, 55.0, 95.0})
    closest = [[m, get_closest_morale_stat(m)] for m in raws]
    stats = [[s, list(Regiment(10, s).stats)] for s in STATS_VALID]
    min_crew = ArtilleryBattery.MIN_CREW_PER_GUN
    guns = [[g, crew, ArtilleryBattery(crew, '4/4/0/0', g, subtype='battery').effective_guns]
            for g in (0, 1, 6, 8, 12) for crew in (0, 6, 7, 13, 14, 55, 56, 72, 100)]
    return {'description': 'Units: closest morale stat [raw, stat]; stats strings that parse [text, stats] or '
                           'are rejected; manned guns [guns, crew, effective_guns].',
            'closest_morale_stat': closest, 'stats_valid': stats, 'stats_invalid': STATS_INVALID,
            'min_crew_per_gun': min_crew, 'effective_guns': guns}


def _u(uid, side, type_, subtype, size, stats, **extra):
    return {'id': uid, 'side': side, 'type': type_, 'subtype': subtype, 'size': size, 'stats': stats, **extra}


def _fire(target, **extra):
    return {'target': target, 'mode': 'ranged', **extra}


def _melee(target, **extra):
    return {'target': target, 'mode': 'melee', **extra}


# Synthetic battles for what the scenario files rarely reach
SYNTHETIC = {
    'charges': {
        'units': [_u('a_line', 0, 'inf', 'line', 900, '6/6/1/0'), _u('a_heavy', 0, 'cav', 'heavy', 400, '7/7/0/1'),
                  _u('a_drag', 0, 'cav', 'dragoons', 350, '5/5/1/0'), _u('a_pikes', 0, 'inf', 'pikes', 600, '5/6/-2/1'),
                  _u('x_line', 1, 'inf', 'line', 800, '4/5/0/0'), _u('x_light', 1, 'cav', 'light', 300, '5/5/0/1'),
                  _u('x_bat', 1, 'art', 'battery', 72, '5/5/0/0', guns=8), _u('x_irr', 1, 'inf', 'irregulars', 500, '2/3/-1/0')],
        'rounds': [
            {'duration': 45, 'orders': {'a_line': _fire('x_line'), 'a_heavy': _melee('x_irr'), 'a_drag': _fire('x_bat'),
                                        'a_pikes': _melee('x_light'), 'x_light': _melee('a_pikes'),
                                        'x_bat': _fire('a_heavy', ammo='canister'), 'x_line': _fire('a_line')}},
            {'duration': 60, 'orders': {'a_line': _melee('x_line'), 'a_heavy': _melee('x_bat', on_break='pursue'),
                                        'a_drag': _fire('x_irr', on_break='strongest'), 'a_pikes': _melee('x_light'),
                                        'x_line': _melee('a_line'), 'x_bat': _fire('a_line', ammo='shell'),
                                        'x_irr': _fire('a_drag')}},
            {'duration': 90, 'orders': {'a_line': _melee('x_line', on_break='pursue'), 'a_heavy': _melee('x_irr'),
                                        'a_drag': _melee('x_bat'), 'x_line': _fire('a_line', on_break='weakest')}},
        ],
        'finish': True,
    },
    'falter_and_fire': {
        'params': {'charge': {'falter_threshold': 0.0, 'break_threshold': 3.0}},
        'units': [_u('a_inf', 0, 'inf', 'light', 300, '2/2/0/0'), _u('a_cav', 0, 'cav', 'light', 200, '3/3/0/1'),
                  _u('x_inf', 1, 'inf', 'line', 1200, '8/8/1/0'), _u('x_bat', 1, 'art', 'horse battery', 54, '6/6/0/0', guns=6),
                  _u('x_rifle', 1, 'inf', 'light', 400, '6/6/1/0')],
        'rounds': [
            {'duration': 60, 'orders': {'a_inf': _melee('x_inf'), 'a_cav': _melee('x_rifle'),
                                        'x_bat': _fire('a_inf', ammo='round_shot'), 'x_rifle': _fire('a_inf'),
                                        'x_inf': _fire('a_cav')}},
            {'duration': 60, 'orders': {'a_inf': _fire('x_inf'), 'a_cav': _melee('x_bat'),
                                        'x_bat': _fire('a_cav', ammo='canister'), 'x_inf': _fire('a_inf', on_break='weakest'),
                                        'x_rifle': _fire('a_cav', on_break='strongest')}},
        ],
        'finish': 'none',
    },
    'wipe_out_and_drain': {
        'params': {'morale': {'drain_per_hour': 0.6, 'break_point_spread': 0.0}},
        'units': [_u('big', 0, 'inf', 'line', 3000, '9/9/2/0'), _u('mid', 0, 'inf', 'marine', 600, '5/5/0/0'),
                  _u('tiny', 1, 'inf', 'line', 8, '1/1/-1/0'), _u('gun', 1, 'art', 'siege battery', 15, '3/3/0/0', guns=4),
                  {'id': 'plain', 'side': 1, 'size': 400, 'stats': '4/4/0/0'}],
        'rounds': [
            {'duration': 30, 'orders': {'big': _fire('gun', on_break='strongest'), 'mid': _fire('tiny'),
                                        'gun': _fire('mid'), 'plain': _fire('mid')}},
            {'duration': 120, 'orders': {'big': _fire('plain'), 'mid': _melee('gun'), 'plain': _fire('big')}},
        ],
        'finish': 0,
    },
    'broken_on_approach': {
        'units': [_u('s1', 0, 'inf', 'line', 3000, '9/9/2/0'), _u('s2', 0, 'inf', 'line', 3000, '9/9/2/0'),
                  _u('slow', 0, 'inf', 'line', 500, '5/5/0/0'), _u('weak', 1, 'inf', 'irregulars', 200, '1/1/-1/0'),
                  _u('other', 1, 'inf', 'line', 900, '5/5/0/0')],
        'rounds': [
            {'duration': 20, 'orders': {'s1': _fire('weak'), 's2': _fire('weak', on_break='weakest'),
                                        'slow': _melee('weak'), 'other': _fire('slow')}},
            {'duration': 30, 'orders': {'s1': _fire('other'), 'slow': _melee('weak', on_break='pursue'),
                                        'other': _melee('slow')}},
        ],
        'finish': 1,
    },
}

BATTLE_SEEDS = (1, 2, 3)


def _battle_case(name: str, scenario: dict, seed: int, record_events: bool = False) -> dict:
    from imperial_generals import api
    from imperial_generals.battles.setup import battle_from_setup
    battle = battle_from_setup(scenario, seed=seed)
    start = battle.to_dict()
    rounds = []
    for rnd in scenario.get('rounds', []):
        orders, _ = api._playable(battle, rnd.get('orders', {}))
        battle.resolve_round(rnd['duration'], orders, record_events=record_events)
        rounds.append({'duration': rnd['duration'], 'orders': orders, 'record_events': record_events})
    finish = scenario.get('finish', False)
    holder = None if finish is False else api._field_holder(finish, api._sides(scenario))
    if finish is not False:
        battle.finish(holder)
    return {'name': name, 'seed': seed, 'start': start, 'rounds': rounds, 'finished': finish is not False,
            'field_held_by': holder, 'final': battle.to_dict()}


def battles_fixture() -> dict:
    from imperial_generals.battles.setup import load_setup_file
    scenarios = ROOT / 'scenarios'
    files = {'example_ridge': scenarios / 'example_ridge.yaml',
             'day_even_firefight': scenarios / 'calibration' / 'day_even_firefight.yaml',
             'day_assault': scenarios / 'calibration' / 'day_assault.yaml'}
    cases = []
    for name, path in files.items():
        scenario = load_setup_file(path)
        cases += [_battle_case(name, scenario, seed) for seed in BATTLE_SEEDS]
    for name, scenario in SYNTHETIC.items():
        cases += [_battle_case(name, scenario, seed) for seed in BATTLE_SEEDS]
    cases.append(_battle_case('example_ridge (events)', load_setup_file(files['example_ridge']), 7, record_events=True))
    return {'description': "Whole battles: load 'start' (a state file), resolve each round's orders, then finish "
                           "with field_held_by ('auto', 0, 1 or null) if 'finished'; the state file must equal "
                           "'final'.",
            'cases': cases}


def summaries_fixture() -> dict:
    from imperial_generals import api
    cases = []
    for case in battles_fixture()['cases']:
        final = case['final']
        cases.append({'name': case['name'], 'seed': case['seed'], 'order_of_battle': api.order_of_battle(final),
                      'side_summary': api.side_summary(final) if final['result'] is not None else None})
    return {'description': "api.order_of_battle and api.side_summary (finished battles only) of each battle in "
                           "battles.json, from its 'final' state.",
            'cases': cases}


FIXTURES = {
    'rng': rng_fixture,
    'params': params_fixture,
    'morale': morale_fixture,
    'units': units_fixture,
    'battles': battles_fixture,
    'summaries': summaries_fixture,
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
