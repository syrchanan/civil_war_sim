"""
Step API (roadmap A9): the battle engine as plain functions on JSON-safe dicts.

For callers that keep the battle as data between calls: the CLI, the game site, notebooks. Each call loads the
state, acts, and returns a new state; the input is never modified. Resuming from a state is exact (see
``battles.state``), so a chain of ``step`` calls gives the same results as one ``Battle`` resolving round after
round.

For many fast rollouts (tuning, RL), use ``Battle`` directly and skip the per-call (de)serialisation.

    state = new_battle(load_setup_file('setup.yaml'))
    state, report = step(state, 90, {'us_1mn': {'target': 'cs_26nc', 'mode': 'ranged'}})
    state, result = finish(state)

A **scenario** is a setup plus a script of rounds, so a whole battle can be replayed from one file:

    rounds:
      - duration: 90
        orders:
          us_1mn: {target: cs_26nc, mode: ranged}
          cs_26nc: {target: us_1mn, mode: ranged}
    finish: true        # settle casualties after the last round: true / auto, none, or the side holding the field

Scripted orders can't foresee random breaks, so orders that can no longer be carried out (the unit has broken or
been wiped out, or its target has been wiped out) are skipped and listed in the round's ``skipped_orders``.
Broken targets can still be attacked (pursuit).
"""

import copy
from dataclasses import asdict

from imperial_generals.battles.battle import Battle
from imperial_generals.battles.setup import SetupError, battle_from_setup
from imperial_generals.battles.state import report_to_dict, result_to_dict

ROUND_KEYS = ('duration', 'orders', 'modifiers')


def new_battle(setup: dict, seed: int | None = None) -> dict:
    """The state of a new battle built from a setup; ``seed`` overrides the setup's."""
    return battle_from_setup(setup, seed=seed).to_dict()


def step(state: dict, duration: float, orders: dict | None = None, record_events: bool = False,
         modifiers: dict | None = None) -> tuple:
    """
    Resolve one round of ``duration`` game minutes. Returns ``(new_state, report)``; units without orders idle.
    ``modifiers`` are the admin's for this round (``{uid: {'fire', 'melee', 'morale', 'note'}}``).
    """
    battle = Battle.from_dict(state)
    report = battle.resolve_round(duration, orders or {}, record_events=record_events, modifiers=modifiers)
    return battle.to_dict(), report_to_dict(report)


def preview(state: dict, orders: dict, modifiers: dict | None = None) -> list[dict]:
    """The engagements these orders (and modifiers) would create, with their current casualty rates. No dice rolled."""
    return [asdict(e) for e in Battle.from_dict(state).engagements(orders, modifiers)]


def finish(state: dict, field_held_by='auto') -> tuple:
    """End the battle and settle casualties (see ``Battle.finish``). Returns ``(new_state, result)``."""
    battle = Battle.from_dict(state)
    result = battle.finish(field_held_by)
    return battle.to_dict(), result_to_dict(result)


def _sides(scenario: dict) -> list | None:
    sides = scenario.get('sides')
    return sides if isinstance(sides, list) and len(sides) == 2 else None


def _field_holder(value, sides: list | None):
    """The ``field_held_by`` for a scenario's ``finish`` value; raises ValueError if it isn't one."""
    if value is True or value == 'auto':
        return 'auto'
    if value == 'none':
        return None
    if type(value) is int and value in (0, 1):
        return value
    if sides is not None and isinstance(value, str) and value in sides:
        return sides.index(value)
    names = f' or a side name ({", ".join(sides)})' if sides else ''
    raise ValueError(f'"finish" must be true, false, auto, none, 0, 1{names}.')


def _check_script(scenario: dict) -> list[str]:
    errors = []
    finish = scenario.get('finish', False)
    if finish is not False:
        try:
            _field_holder(finish, _sides(scenario))
        except ValueError as exc:
            errors.append(str(exc))
    rounds = scenario.get('rounds', [])
    if not isinstance(rounds, list):
        return errors + ['"rounds" must be a list of rounds, each with a "duration".']
    for n, rnd in enumerate(rounds, start=1):
        if not isinstance(rnd, dict):
            errors.append(f'Round {n}: must be a mapping with a "duration".')
            continue
        errors.extend(f'Round {n}: unknown key "{key}". Allowed: {", ".join(ROUND_KEYS)}.'
                      for key in rnd if key not in ROUND_KEYS)
        duration = rnd.get('duration')
        if duration is None:
            errors.append(f'Round {n}: "duration" is missing (game minutes, e.g. 90).')
        elif isinstance(duration, bool) or not isinstance(duration, (int, float)) or not duration > 0:
            errors.append(f'Round {n}: duration must be a positive number of minutes.')
        if not isinstance(rnd.get('orders', {}), dict):
            errors.append(f'Round {n}: "orders" must be a mapping of unit id to order.')
        if not isinstance(rnd.get('modifiers', {}), dict):
            errors.append(f'Round {n}: "modifiers" must be a mapping of unit id to modifiers.')
    return errors


def _playable(battle: Battle, orders: dict) -> tuple:
    """Split scripted orders into those that can still be carried out and those skipped (uid -> why)."""
    keep, skipped = {}, {}
    for uid, order in orders.items():
        unit = battle.units.get(uid)
        target = battle.units.get(order.get('target')) if isinstance(order, dict) else None
        if unit is not None and not unit.active:
            skipped[uid] = f'{uid} is {"wiped out" if unit.size == 0 else "broken"}'
        elif target is not None and target.size == 0:
            skipped[uid] = f"target {order['target']} is wiped out"
        else:
            keep[uid] = order
    return keep, skipped


def run_scenario(scenario: dict, seed: int | None = None, record_events: bool = False,
                 overrides: dict | None = None) -> tuple:
    """
    Build the battle and play the scenario's rounds in order, then finish it if ``finish`` says so.

    Orders that can no longer be carried out are skipped and listed in each report's ``skipped_orders``.

    Returns ``(state, reports, result)``; ``result`` is None if the battle wasn't finished. ``overrides`` are
    parameter overrides applied on top of the scenario's own (for tuning runs).

    Raises
    ------
    SetupError
        For problems in the setup or the round script (all reported before anything runs), or an order that
        can't be carried out (naming the round).
    """
    battle = battle_from_setup(scenario, seed=seed, overrides=overrides)
    errors = _check_script(scenario)
    if errors:
        raise SetupError(errors)
    reports = []
    for n, rnd in enumerate(scenario.get('rounds', []), start=1):
        orders, skipped = _playable(battle, rnd.get('orders', {}))
        try:
            report = battle.resolve_round(rnd['duration'], orders, record_events=record_events,
                                          modifiers=rnd.get('modifiers'))
        except (ValueError, TypeError) as exc:
            raise SetupError([f'Round {n}: {exc}']) from None
        reports.append({**report_to_dict(report), 'skipped_orders': skipped})
    finish = scenario.get('finish', False)
    result = None if finish is False else result_to_dict(battle.finish(_field_holder(finish, _sides(scenario))))
    return battle.to_dict(), reports, result


PLAN_FORMAT = 'imperial-generals-orders'
PLAN_VERSION = 1


def battle_tag(state: dict) -> str:
    """
    A tag for a battle state as it stands between rounds: the rounds fought and the dice generator's state. It
    changes with every round fought, so an orders file made from an older copy of the battle can be refused.
    """
    return '-'.join(str(n) for n in [state['round'], *state['rng_state']])


def _check_plan(state: dict, plan: dict, units: dict) -> None:
    """A plan file must be for this battle and its next round, and only move and order its own side's units."""
    if plan.get('version') != PLAN_VERSION:
        raise ValueError(f"Unsupported orders file version {plan.get('version')!r} (expected {PLAN_VERSION}).")
    battle = plan['battle']
    if battle['seed'] != state['seed']:
        raise ValueError(f"These orders are for another battle (seed {battle['seed']}, this one {state['seed']}).")
    if battle['round'] != state['round'] + 1:
        raise ValueError(f"These orders are for round {battle['round']}; the next round is {state['round'] + 1}.")
    if 'tag' in battle and battle['tag'] != battle_tag(state):
        raise ValueError('These orders were made from an older copy of the battle; ask the admin for the latest.')
    side = plan['side']
    for uid in [*plan['orders'], *plan.get('positions', {})]:
        if uid not in units:
            raise ValueError(f'The orders name an unknown unit {uid}.')
        if units[uid]['side'] != side:
            raise ValueError(f"{uid} is not on {_side_names(state)[side]}'s side.")


def merge_plans(state: dict, plans: list) -> tuple:
    """
    Merge orders files into one round's orders: ``(state with the plans' moves applied, orders)``.

    Each item is either a plan file submitted by a player (``format`` 'imperial-generals-orders': the orders and
    moves for one side, for this battle's next round) or a plain mapping of unit id to order. A unit with orders in
    two files is refused, as is a plan for another battle or round, or one touching the other side's units.
    Moves are positions on open ground (elevation 0, no cover); a move without a facing keeps the unit's old one.
    The given state is left unchanged.

    Raises
    ------
    ValueError
        Naming what is wrong.
    """
    state = copy.deepcopy(state)
    units = {u['id']: u for u in state['units']}
    orders: dict = {}
    for plan in plans:
        is_plan = isinstance(plan, dict) and plan.get('format') == PLAN_FORMAT
        if is_plan:
            _check_plan(state, plan, units)
            for uid, place in plan.get('positions', {}).items():
                old = units[uid]['position'] or {}
                units[uid]['position'] = {'x': place['x'], 'y': place['y'], 'z': 0, 'cover': 0, 'terrain_type': 'open',
                                          'facing': place.get('facing', old.get('facing'))}
        for uid, order in (plan['orders'] if is_plan else plan).items():
            if uid in orders:
                raise ValueError(f'{uid} has orders in two files.')
            orders[uid] = order
    return state, orders


def scenario_from_state(state: dict) -> dict:
    """
    The scenario (setup + scripted rounds + finish) that replays a saved battle exactly, e.g. one downloaded from
    the web client: ``run_scenario`` on it gives the same state again, and ``batch`` / ``check`` can rerun it over
    other seeds or parameter overrides for tuning.

    Each round's length is recovered as ``end - start``, exact for whole minutes. A field holder named in
    ``finish`` replays as named; one decided by the engine replays as 'auto'.

    Raises
    ------
    ValueError
        If the state has no seed (it was built from a bare generator state, so its start can't be replayed).
    """
    if state['seed'] is None:
        raise ValueError("This battle has no seed, so its start can't be replayed.")
    meta = dict(state['meta'])
    sides = meta.pop('sides', None)
    units = []
    for u in state['units']:
        unit = {'id': u['id'], 'name': u['name'], 'side': u['side']}
        if u['type'] is not None:
            unit['type'], unit['subtype'] = u['type'], u['subtype']
        unit['size'] = u['initial_size']
        if 'guns' in u:
            unit['guns'] = u['guns'] + u['guns_lost']
        unit['stats'] = u['initial_stats']
        unit['front_size'] = u['front_size']
        if u['meta']:
            unit['meta'] = u['meta']
        units.append(unit)
    rounds = []
    for r in state['history']:
        orders = {uid: {k: v for k, v in o.items() if v is not None} for uid, o in r['orders'].items()}
        rnd = {'duration': r['end'] - r['start'], 'orders': orders}
        if r.get('modifiers'):
            rnd['modifiers'] = r['modifiers']
        rounds.append(rnd)
    result = state['result']
    if result is None:
        finish = False
    elif result.get('field_decided_by', 'admin') != 'admin':
        finish = True
    else:
        finish = 'none' if result['field_held_by'] is None else result['field_held_by']
    scenario = {'meta': meta}
    if sides is not None:
        scenario['sides'] = sides
    scenario.update({'seed': state['seed'], 'params': state['params'], 'units': units, 'rounds': rounds,
                     'finish': finish})
    return scenario


# =============================================================================
# Side summaries
# =============================================================================

def _side_names(state: dict) -> list:
    sides = state['meta'].get('sides')
    return sides if isinstance(sides, list) and len(sides) == 2 else ['Side 0', 'Side 1']


def order_of_battle(state: dict) -> list[dict]:
    """
    Each side as the battle began: units, men, men by unit type (artillery also counts guns), and experience and
    morale averaged over the men. Generic units count as infantry, as they do in combat.
    """
    names = _side_names(state)
    sides = []
    for side in (0, 1):
        units = [u for u in state['units'] if u['side'] == side]
        men = sum(u['initial_size'] for u in units)
        by_type: dict = {}
        xp = morale = 0
        for u in units:
            kind = by_type.setdefault(u['type'] or 'inf', {'units': 0, 'men': 0})
            kind['units'] += 1
            kind['men'] += u['initial_size']
            if 'guns' in u:
                kind['guns'] = kind.get('guns', 0) + u['guns'] + u['guns_lost']
            stats = [int(x) for x in u['initial_stats'].split('/')]
            xp += stats[0] * u['initial_size']
            morale += stats[1] * u['initial_size']
        sides.append({'name': names[side], 'units': len(units), 'men': men, 'by_type': by_type,
                      'avg_experience': xp / men, 'avg_morale': morale / men})
    return sides


def side_summary(state: dict) -> list[dict]:
    """
    Each side's performance over a finished battle.

    ``started - killed - wounded - prisoners_lost + returned = final``, where ``wounded`` excludes wounded taken
    prisoner (they count once, as prisoners). ``casualties`` = killed + wounded + prisoners lost (the battle's
    toll before any wounded return), ``casualty_share`` its share of starting strength. Hits are men hit by fire or in melee; ``exchange_ratio`` is enemy
    men hit per own man hit (None if the side was never hit). ``loss_share`` is the share of starting strength
    not in the ranks at the end. ``outcome`` reads the field as the result, as it was read at the time: 'won' (held
    the field), 'lost' (the other side held it) or 'drawn' (nobody did; the fight can go on the next day).

    Raises
    ------
    ValueError
        If the battle hasn't been finished (casualties aren't settled yet).
    """
    result = state.get('result')
    if result is None:
        raise ValueError('The battle has to be finished first (finish settles killed / wounded / prisoners).')
    names = _side_names(state)
    holder = result['field_held_by']
    sides = []
    for side in (0, 1):
        units = [u for u in state['units'] if u['side'] == side]
        outcomes = [result['units'][u['id']] for u in units]
        started = sum(u['initial_size'] for u in units)
        final = sum(u['size'] for u in units)
        taken = sum(o['hits'] for o in outcomes)
        inflicted = sum(u['inflicted'] for u in units)
        killed = sum(o['killed'] for o in outcomes)
        wounded = sum(o['wounded'] - o['wounded_captured'] for o in outcomes)
        prisoners_lost = sum(o['captured_in_rout'] + o['wounded_captured'] for o in outcomes)
        sides.append({
            'name': names[side],
            'outcome': 'drawn' if holder is None else 'won' if holder == side else 'lost',
            'held_field': holder == side,
            'units': len(units),
            'units_out': sum(1 for u in units if u['morale']['broken'] or u['size'] == 0),
            'started': started,
            'killed': killed,
            'wounded': wounded,
            'prisoners_lost': prisoners_lost,
            'casualties': killed + wounded + prisoners_lost,
            'casualty_share': (killed + wounded + prisoners_lost) / started,
            'returned': sum(o['wounded_returned'] for o in outcomes),
            'final': final,
            'loss_share': (started - final) / started,
            'hits_taken': taken,
            'hits_inflicted': inflicted,
            'exchange_ratio': inflicted / taken if taken else None,
            'prisoners_taken': result['prisoners'][str(side)],
            'guns_lost': sum(o['guns_lost'] for o in outcomes),
            'guns_taken': result['guns_captured'][str(side)],
        })
    return sides
