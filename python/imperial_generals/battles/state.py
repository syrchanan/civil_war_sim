"""
Battle state file (roadmap A8): the JSON contract between the Python engine, the TypeScript port and the game site.

Everything needed to resume exactly is saved: the RNG state words, the full parameter set (not just overrides, so
a later config change can't alter a saved battle), unit order, each unit's regiment and live morale, and the
running totals. Resolving the next round of a reloaded battle gives the same result as if it had never been saved.
Round history (orders, engagements, per-unit reports, events) is kept for replays and UIs.

``meta`` (battle and per unit) is free-form and round-tripped untouched.
"""

from dataclasses import asdict

from imperial_generals.battles.battle import (
    Battle, CasualtyEvent, Engagement, RoundReport, UnitReport,
)
from imperial_generals.params import BattleParams
from imperial_generals.units import ArtilleryBattery, CavalryRegiment, InfantryRegiment, Regiment
from imperial_generals.utils import Position, Rng

FORMAT = 'imperial-generals-battle'
VERSION = 1


def _stats(stats: tuple) -> str:
    return '/'.join(str(s) for s in stats)


def _by_side(d: dict) -> dict:
    return {str(side): n for side, n in d.items()}


def _from_sides(d: dict) -> dict:
    return {int(side): n for side, n in d.items()}


def _position(position: Position | None) -> dict | None:
    if position is None:
        return None
    return {'x': position.x, 'y': position.y, 'z': position.z, 'cover': position.cover,
            'terrain_type': position.terrain_type}


# =============================================================================
# Saving
# =============================================================================

def _unit_to_dict(unit) -> dict:
    reg = unit.regiment
    data = {
        'id': unit.uid,
        'name': unit.name,
        'side': unit.side,
        'type': getattr(reg, 'unit_type', None),
        'subtype': getattr(reg, 'subtype', None),
        'size': reg.size,
        'initial_size': unit.initial_size,
        'stats': _stats(reg.stats),
        'initial_stats': _stats(unit.initial_stats),
        'front_size': reg.front_size,
        'raw_morale': reg.raw_morale,
        'combat_mode': reg.combat_mode,
        'position': _position(reg.position),
        'morale': {
            'resolve': unit.morale.resolve,
            'shock': unit.morale.shock,
            'lost': unit.morale.lost,
            'broken': unit.morale.broken,
        },
        'losses': unit.losses,
        'inflicted': unit.inflicted,
        'captured': unit.captured,
        'guns_lost': unit.guns_lost,
        'meta': unit.meta,
    }
    if isinstance(reg, ArtilleryBattery):
        data['guns'] = reg.guns
    return data


def _report_to_dict(report: RoundReport) -> dict:
    return {
        'round': report.round,
        'start': report.start,
        'end': report.end,
        'orders': report.orders,
        'engagements': [asdict(e) for e in report.engagements],
        'units': {uid: asdict(u) for uid, u in report.units.items()},
        'events': [asdict(e) for e in report.events],
        'prisoners': _by_side(report.prisoners),
        'guns_captured': _by_side(report.guns_captured),
    }


def battle_to_dict(battle: Battle) -> dict:
    return {
        'format': FORMAT,
        'version': VERSION,
        'meta': battle.meta,
        'seed': battle.seed,
        'rng_state': battle.rng.state,
        'params': battle.params.to_dict(),
        'time': battle.time,
        'round': battle.round,
        'finished': battle.finished,
        'prisoners': _by_side(battle.prisoners),
        'guns_captured': _by_side(battle.guns_captured),
        'units': [_unit_to_dict(u) for u in battle.units.values()],
        'history': [_report_to_dict(r) for r in battle.history],
    }


# =============================================================================
# Loading
# =============================================================================

def _build_regiment(data: dict) -> Regiment:
    """The regiment as it started the battle (initial size and stats); live state is restored afterwards."""
    size, stats, kind, subtype = data['initial_size'], data['initial_stats'], data['type'], data['subtype']
    if kind is None:
        return Regiment(size, stats)
    if kind == 'inf':
        return InfantryRegiment(size, stats, subtype=subtype)
    if kind == 'cav':
        return CavalryRegiment(size, stats, subtype=subtype)
    if kind == 'art':
        return ArtilleryBattery(size, stats, data['guns'], subtype=subtype)
    raise ValueError(f"Unknown unit type {kind!r} for {data['id']!r}.")


def _restore_unit(unit, data: dict) -> None:
    reg = unit.regiment
    reg.update_size(data['size'])
    reg.update_stats(data['stats'])
    reg.raw_morale = data['raw_morale']
    reg.set_front_size(data['front_size'])
    reg.set_combat_mode(data['combat_mode'])
    if data['position'] is not None:
        reg.deploy(Position.from_dict(data['position']))
    morale = unit.morale
    morale.resolve = data['morale']['resolve']
    morale.shock = data['morale']['shock']
    morale.lost = data['morale']['lost']
    morale.broken = data['morale']['broken']
    unit.losses, unit.inflicted = data['losses'], data['inflicted']
    unit.captured, unit.guns_lost = data['captured'], data['guns_lost']


def _report_from_dict(data: dict) -> RoundReport:
    return RoundReport(
        round=data['round'],
        start=data['start'],
        end=data['end'],
        engagements=tuple(Engagement(**e) for e in data['engagements']),
        units={uid: UnitReport(**u) for uid, u in data['units'].items()},
        events=tuple(CasualtyEvent(**e) for e in data['events']),
        prisoners=_from_sides(data['prisoners']),
        guns_captured=_from_sides(data['guns_captured']),
        orders=data['orders'],
    )


def battle_from_dict(data: dict) -> Battle:
    if data.get('format') != FORMAT:
        raise ValueError(f"Not a battle state file (format {data.get('format')!r}).")
    if data.get('version') != VERSION:
        raise ValueError(f"Unsupported battle state version {data.get('version')!r} (expected {VERSION}).")

    units = {
        u['id']: {'side': u['side'], 'regiment': _build_regiment(u), 'name': u['name'], 'meta': u['meta']}
        for u in data['units']
    }
    battle = Battle(units, rng=Rng.from_state(data['rng_state']), params=BattleParams.from_dict(data['params']),
                    meta=data['meta'])
    for u in data['units']:
        _restore_unit(battle.units[u['id']], u)

    battle.seed = data['seed']
    battle.time = data['time']
    battle.round = data['round']
    battle.finished = data['finished']
    battle.prisoners = _from_sides(data['prisoners'])
    battle.guns_captured = _from_sides(data['guns_captured'])
    battle.history = [_report_from_dict(r) for r in data['history']]
    return battle
