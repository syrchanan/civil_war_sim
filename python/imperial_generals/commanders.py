"""
Commander rating (roadmap Phase C): each side's commander as a historical general, by how the battle's result
compares with what the armies' strength led to expect. See config/commanders.yaml for the formulas.

    ratings(state)  ->  [{'name', 'power', 'expected', 'result', 'score', 'general': {'name', 'battle', 'from'}}, ...]
"""

from imperial_generals.battles.morale import break_fraction
from imperial_generals.config import get_config
from imperial_generals.params import BattleParams
from imperial_generals.units.ArtilleryBattery import ArtilleryBattery
from imperial_generals.utils.fdlibm import exp, log


def _stats(text: str) -> tuple:
    return tuple(int(s) for s in text.split('/'))


def unit_power(unit: dict, params: BattleParams) -> float:
    """Hit rate × staying power of one unit (a state file's unit) as it began the battle."""
    c = params.combat
    stats = _stats(unit['initial_stats'])
    size = unit['initial_size']
    coef = c.unit_coef(stats, 'ranged')
    if unit['type'] == 'art':
        guns = min(unit['guns'] + unit['guns_lost'], size // ArtilleryBattery.MIN_CREW_PER_GUN)
        hit_rate = coef * guns * c.artillery_ammo[c.artillery_default_ammo]
    elif coef > 0:
        hit_rate = coef * size * c.ranged_kill_rate
    else:
        rating = params.matchups.melee_rating((unit['type'] or 'inf', unit['subtype']))
        hit_rate = c.melee_kill_rate * c.melee_efficiency(stats[0], stats[1], rating) * min(size, unit['front_size'])
    return hit_rate * break_fraction(stats[0], stats[1], params.morale)


def side_power(state: dict, side: int, params: BattleParams) -> float:
    return sum(unit_power(u, params) for u in state['units'] if u['side'] == side)


def expected_share(power: float, other: float, exponent: float) -> float:
    """
    The share of the result a side's strength leads to expect: P^k / (P^k + Q^k). Powers go through the fdlibm
    ``exp`` / ``log`` ports so the TS port agrees to the last bit.
    """
    a, b = (0.0 if p == 0 else exp(exponent * log(p)) for p in (power, other))
    return 0.5 if a + b == 0 else a / (a + b)


def _share(mine: float, theirs: float) -> float:
    return 0.5 if mine + theirs == 0 else mine / (mine + theirs)


def result_shares(sides: list, holder: int | None, cfg: dict) -> list:
    """
    Each side's share of the result from ``sides`` (per side: casualties, guns_taken, units_out_men, started) and
    the side holding the field (None for a draw).
    """
    w, gun = cfg['weights'], cfg['gun_value']
    routed = [s['units_out_men'] / s['started'] for s in sides]
    shares = []
    for me, them in ((0, 1), (1, 0)):
        damage = [sides[them]['casualties'] + gun * sides[me]['guns_taken'],
                  sides[me]['casualties'] + gun * sides[them]['guns_taken']]
        field = 0.5 if holder is None else 1.0 if holder == me else 0.0
        shares.append(w['casualties'] * _share(*damage) + w['field'] * field
                      + w['routs'] * _share(routed[them], routed[me]))
    return shares


def general(score: float, ladder: list) -> dict:
    """The last general on the ladder whose 'from' the score reaches."""
    pick = ladder[0]
    for g in ladder:
        if score >= g['from']:
            pick = g
    return dict(pick)


def ratings(state: dict, cfg: dict | None = None) -> list[dict]:
    """
    Each side's commander rating for a finished battle.

    Raises
    ------
    ValueError
        If the battle hasn't been finished.
    """
    from imperial_generals import api     # api imports the battle modules; import late to keep this one light
    cfg = cfg if cfg is not None else get_config()['commanders']
    summary = api.side_summary(state)     # raises if not finished
    params = BattleParams.from_dict(state['params'])
    power = [side_power(state, s, params) for s in (0, 1)]
    for side, s in enumerate(summary):
        s['units_out_men'] = sum(u['initial_size'] for u in state['units']
                                 if u['side'] == side and (u['morale']['broken'] or u['size'] == 0))
    results = result_shares(summary, state['result']['field_held_by'], cfg)
    out = []
    for side in (0, 1):
        expected = expected_share(power[side], power[1 - side], cfg['power_exponent'])
        score = results[side] - expected
        out.append({'name': summary[side]['name'], 'power': power[side], 'expected': expected,
                    'result': results[side], 'score': score, 'general': general(score, cfg['ladder'])})
    return out
