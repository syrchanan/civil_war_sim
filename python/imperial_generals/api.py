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
    finish: true        # settle casualties (killed / wounded / captured) after the last round
"""

from dataclasses import asdict

from imperial_generals.battles.battle import Battle
from imperial_generals.battles.setup import SetupError, battle_from_setup
from imperial_generals.battles.state import report_to_dict, result_to_dict

ROUND_KEYS = ('duration', 'orders')


def new_battle(setup: dict, seed: int | None = None) -> dict:
    """The state of a new battle built from a setup; ``seed`` overrides the setup's."""
    return battle_from_setup(setup, seed=seed).to_dict()


def step(state: dict, duration: float, orders: dict | None = None, record_events: bool = False) -> tuple:
    """Resolve one round of ``duration`` game minutes. Returns ``(new_state, report)``; units without orders idle."""
    battle = Battle.from_dict(state)
    report = battle.resolve_round(duration, orders or {}, record_events=record_events)
    return battle.to_dict(), report_to_dict(report)


def preview(state: dict, orders: dict) -> list[dict]:
    """The engagements these orders would create, with their current casualty rates. No dice are rolled."""
    return [asdict(e) for e in Battle.from_dict(state).engagements(orders)]


def finish(state: dict, field_held_by='auto') -> tuple:
    """End the battle and settle casualties (see ``Battle.finish``). Returns ``(new_state, result)``."""
    battle = Battle.from_dict(state)
    result = battle.finish(field_held_by)
    return battle.to_dict(), result_to_dict(result)


def _check_script(scenario: dict) -> list[str]:
    errors = []
    if not isinstance(scenario.get('finish', False), bool):
        errors.append('"finish" must be true or false.')
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
    return errors


def run_scenario(scenario: dict, seed: int | None = None, record_events: bool = False) -> tuple:
    """
    Build the battle and play the scenario's rounds in order, then finish it if ``finish: true``.

    Returns ``(state, reports, result)``; ``result`` is None if the battle wasn't finished.

    Raises
    ------
    SetupError
        For problems in the setup or the round script (all reported before anything runs), or an order that
        can't be carried out (naming the round).
    """
    battle = battle_from_setup(scenario, seed=seed)
    errors = _check_script(scenario)
    if errors:
        raise SetupError(errors)
    reports = []
    for n, rnd in enumerate(scenario.get('rounds', []), start=1):
        try:
            report = battle.resolve_round(rnd['duration'], rnd.get('orders', {}), record_events=record_events)
        except (ValueError, TypeError) as exc:
            raise SetupError([f'Round {n}: {exc}']) from None
        reports.append(report_to_dict(report))
    result = result_to_dict(battle.finish()) if scenario.get('finish', False) else None
    return battle.to_dict(), reports, result
