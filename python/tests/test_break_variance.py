import json

import pytest

from imperial_generals.battles.battle import Battle
from imperial_generals.battles.morale import break_scale
from imperial_generals.params import BattleParams
from imperial_generals.units import Regiment
from imperial_generals.utils import Rng

P = BattleParams()
SPREAD = P.morale.break_point_spread


def units(n=4):
    return {f'u{i}': (i % 2, Regiment(1000, '5/5/0/0')) for i in range(n)}


def test_each_unit_draws_its_break_scale_from_the_seed_in_unit_order():
    b = Battle(units(), rng=Rng(7))
    rng = Rng(7)
    expected = [break_scale(rng.random(), SPREAD) for _ in range(4)]
    assert [u.morale.break_scale for u in b.units.values()] == expected
    assert len(set(expected)) == 4
    assert [u.morale.break_scale for u in Battle(units(), rng=Rng(7)).units.values()] == expected


def test_no_spread_draws_nothing():
    flat = BattleParams().with_overrides({'morale': {'break_point_spread': 0.0}})
    b = Battle(units(), rng=Rng(7), params=flat)
    assert all(u.morale.break_scale == 1.0 for u in b.units.values())
    assert b.rng.state == Rng(7).state


def test_spread_of_break_scales():
    b = Battle(units(4000), rng=Rng(1))
    scales = sorted(u.morale.break_scale for u in b.units.values())
    p10, p90 = scales[400], scales[3600]
    assert p10 == pytest.approx(9 ** -SPREAD, rel=0.05)
    assert p90 == pytest.approx(9 ** SPREAD, rel=0.05)


def test_break_scale_is_saved_and_resumes_exactly():
    b = Battle(units(), rng=Rng(3))
    orders = {'u0': {'target': 'u1', 'mode': 'ranged'}, 'u1': {'target': 'u0', 'mode': 'ranged'}}
    b.resolve_round(90, orders)
    data = json.loads(b.to_json())
    assert [u['morale']['break_scale'] for u in data['units']] == [u.morale.break_scale for u in b.units.values()]
    again = Battle.from_json(b.to_json())
    assert [u.morale.break_fraction for u in again.units.values()] == [u.morale.break_fraction for u in b.units.values()]
    assert again.rng.state == b.rng.state
    assert again.resolve_round(240, orders) == b.resolve_round(240, orders)
