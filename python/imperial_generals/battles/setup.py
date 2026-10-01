"""
Battle setup file (roadmap A9): how a new battle is described by hand.

A setup lists the units and, optionally, the seed, side names, parameter overrides and free-form battle details.
It is written by admins and players, so it is YAML or JSON, and validation reports every problem at once, each
with where it is ("Unit 3 (cs_cav): ...").

    meta: {name: Test Ridge, date: 1863-07-02}     # free-form, kept in the state file
    seed: 1863                                     # optional; picked at random (and recorded) if left out
    sides: [Union, Confederate]                    # optional names; units can then use them as their side
    params: {combat: {ranged_kill_rate: 0.005}}    # optional overrides on the defaults
    units:
      - id: us_1mn                                 # id and name default to each other
        name: 1st Minnesota
        side: Union                                # 0, 1 or a name from sides
        type: inf                                  # inf, cav or art; leave out for a generic unit
        subtype: line
        size: 900                                  # artillery: crew; with guns, or neither for a standard battery
        stats: 6/6/1/0                             # experience/morale/weapon/melee-only
        front_size: 450                            # optional
        meta: {player: p1}                         # optional, free-form

A scenario is a setup plus a script of ``rounds`` (and optionally ``finish``); see ``imperial_generals.api``.
The builder accepts those keys and leaves them to the runner.
"""

import json
import secrets
from pathlib import Path

import yaml

from imperial_generals.battles.battle import Battle
from imperial_generals.params import BattleParams
from imperial_generals.units import ArtilleryBattery, CavalryRegiment, InfantryRegiment, Regiment
from imperial_generals.units.Regiment import _parse_stats
from imperial_generals.utils import Rng
from imperial_generals.utils.unit_types import UNIT_SUBTYPES

TOP_KEYS = ('finish', 'meta', 'params', 'rounds', 'seed', 'sides', 'units')
UNIT_KEYS = ('front_size', 'guns', 'id', 'meta', 'name', 'side', 'size', 'stats', 'subtype', 'type')
MAX_SEED = 2 ** 32 - 1


class _TextDatesLoader(yaml.SafeLoader):
    """Safe YAML without timestamps: ``date: 1863-07-02`` stays text, so the state stays plain JSON."""


_TextDatesLoader.yaml_implicit_resolvers = {
    first: [(tag, regexp) for tag, regexp in resolvers if tag != 'tag:yaml.org,2002:timestamp']
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


class SetupError(ValueError):
    """A setup (or scenario) with problems; ``errors`` lists each one."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__('\n'.join(errors))
        self.errors = errors


def _whole(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _positive(value) -> bool:
    return _whole(value) and value > 0


def _side(value, sides: list | None):
    """The side number for ``value``, or None if it isn't one."""
    if _whole(value) and value in (0, 1):
        return value
    if sides is not None and isinstance(value, str) and value in sides:
        return sides.index(value)
    return None


def _build_unit(unit: dict, problems: list[str]) -> Regiment | None:
    """The unit's regiment, or None with ``problems`` filled in."""
    kind, subtype = unit.get('type'), unit.get('subtype')
    if kind is not None and kind not in UNIT_SUBTYPES:
        problems.append(f"type must be one of {', '.join(sorted(UNIT_SUBTYPES))} (or left out); got {kind!r}.")
    elif kind is not None and subtype is None:
        problems.append(f'"subtype" is missing; for {kind} one of {", ".join(sorted(UNIT_SUBTYPES[kind]))}.')
    elif kind is None and subtype is not None:
        problems.append('"subtype" needs a "type".')

    size, guns = unit.get('size'), unit.get('guns')
    if kind == 'art':
        if (size is None) != (guns is None):
            problems.append('artillery needs both "size" (crew) and "guns", or neither for a standard battery.')
        elif guns is not None and not (_whole(guns) and guns >= 0):
            problems.append('guns must be a whole number, 0 or more.')
    elif guns is not None:
        problems.append('only artillery has "guns".')
    if size is None and kind != 'art':
        problems.append('"size" is missing.')
    elif size is not None and not _positive(size):
        problems.append('size must be a positive whole number.')

    stats = unit.get('stats')
    if stats is None:
        problems.append('"stats" is missing (e.g. "5/5/0/0").')
    elif not isinstance(stats, str):
        problems.append('stats must be text like "5/5/0/0".')
    else:
        try:
            _parse_stats(stats)
        except ValueError:
            problems.append(f'stats must be four whole numbers like "5/5/0/0" '
                            f'(experience/morale/weapon/melee-only); got {stats!r}.')

    front = unit.get('front_size')
    if front is not None and not _positive(front):
        problems.append('front_size must be a positive whole number.')
    if not isinstance(unit.get('meta', {}), dict):
        problems.append('"meta" must be a mapping.')
    if problems:
        return None

    try:
        if kind is None:
            regiment = Regiment(size, stats)
        elif kind == 'inf':
            regiment = InfantryRegiment(size, stats, subtype=subtype)
        elif kind == 'cav':
            regiment = CavalryRegiment(size, stats, subtype=subtype)
        elif size is None:
            regiment = ArtilleryBattery.standard(stats, subtype=subtype)
        else:
            regiment = ArtilleryBattery(size, stats, guns, subtype=subtype)
    except ValueError as exc:
        problems.append(str(exc))
        return None
    if front is not None:
        regiment.set_front_size(front)
    return regiment


def _check_top(data: dict, errors: list[str]) -> None:
    for key in data:
        if key not in TOP_KEYS:
            errors.append(f'Unknown key "{key}". Allowed: {", ".join(TOP_KEYS)}.')
    if not isinstance(data.get('meta', {}), dict):
        errors.append('"meta" must be a mapping.')
    seed = data.get('seed')
    if seed is not None and not (_whole(seed) and 0 <= seed <= MAX_SEED):
        errors.append(f'"seed" must be a whole number from 0 to {MAX_SEED}.')
    sides = data.get('sides')
    if sides is not None and not (isinstance(sides, list) and len(sides) == 2
                                  and all(isinstance(s, str) for s in sides) and sides[0] != sides[1]):
        errors.append('"sides" must be a list of two names.')
    if not isinstance(data.get('params', {}), dict):
        errors.append('"params" must be a mapping.')


def battle_from_setup(data, seed: int | None = None) -> Battle:
    """
    Build a new battle from a setup dict (see the module docstring).

    Parameters
    ----------
    data : dict
        The setup, e.g. from ``load_setup_file``.
    seed : int, optional
        Overrides the setup's seed.

    Raises
    ------
    SetupError
        Listing every problem found.
    """
    if not isinstance(data, dict):
        raise SetupError(['The setup must be a mapping with a "units" list.'])
    if 'units' not in data:
        raise SetupError(['"units" is missing: list the units in the battle.'])
    if not isinstance(data['units'], list) or not data['units']:
        raise SetupError(['"units" must be a non-empty list.'])

    errors: list[str] = []
    _check_top(data, errors)
    sides = data.get('sides') if not any(e.startswith('"sides"') for e in errors) else None

    units: dict = {}
    first_index: dict[str, int] = {}
    for n, unit in enumerate(data['units'], start=1):
        if not isinstance(unit, dict):
            errors.append(f'Unit {n}: must be a mapping.')
            continue
        uid = unit.get('id', unit.get('name'))
        if uid is None:
            errors.append(f'Unit {n}: needs an "id" or a "name".')
            continue
        if not isinstance(uid, str):
            errors.append(f'Unit {n}: "id" must be text.')
            continue
        where = f'Unit {n} ({uid})'
        problems: list[str] = []
        for key in unit:
            if key not in UNIT_KEYS:
                problems.append(f'unknown key "{key}". Allowed: {", ".join(UNIT_KEYS)}.')
        name = unit.get('name', uid)
        if not isinstance(name, str):
            problems.append('"name" must be text.')
        if uid in first_index:
            problems.append(f'id "{uid}" is already used by unit {first_index[uid]}.')
        else:
            first_index[uid] = n
        if 'side' not in unit:
            problems.append('"side" is missing.')
        side = _side(unit.get('side'), sides)
        if 'side' in unit and side is None:
            options = f'0, 1 or a name from "sides" ({", ".join(sides)})' if sides else '0 or 1'
            problems.append(f"side must be {options}; got {unit['side']!r}.")
        regiment = _build_unit(unit, problems)
        if problems:
            errors.extend(f'{where}: {p}' for p in problems)
            continue
        units[uid] = {'side': side, 'regiment': regiment, 'name': name, 'meta': dict(unit.get('meta', {}))}

    params = BattleParams()
    if isinstance(data.get('params', {}), dict):
        try:
            params = params.with_overrides(data.get('params', {}))
        except ValueError as exc:
            errors.append(f'params: {exc}')

    if not errors:
        for side in (0, 1):
            if not any(u['side'] == side for u in units.values()):
                errors.append(f'Side {side} has no units.')
    if errors:
        raise SetupError(errors)

    if seed is None:
        seed = data.get('seed')
    if seed is None:
        seed = secrets.randbits(32)
    meta = dict(data.get('meta', {}))
    if sides is not None:
        meta['sides'] = list(sides)
    return Battle(units, rng=Rng(seed), params=params, meta=meta)


def load_setup_file(path) -> dict:
    """
    Read a setup or scenario file: JSON if it ends in .json, else YAML (easier to write by hand).

    Raises
    ------
    SetupError
        If the file isn't valid JSON / YAML, saying where.
    """
    path = Path(path)
    text = path.read_text(encoding='utf-8')
    if path.suffix.lower() == '.json':
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise SetupError([f'{path.name} is not valid JSON (line {exc.lineno}, column {exc.colno}): '
                              f'{exc.msg}.']) from None
    try:
        return yaml.load(text, Loader=_TextDatesLoader)
    except yaml.YAMLError as exc:
        mark = getattr(exc, 'problem_mark', None)
        where = f' (line {mark.line + 1}, column {mark.column + 1})' if mark is not None else ''
        problem = getattr(exc, 'problem', None) or str(exc)
        raise SetupError([f'{path.name} is not valid YAML{where}: {problem}.']) from None
