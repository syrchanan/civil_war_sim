import dataclasses
import json
import itertools

import pytest

from imperial_generals.config import get_config
from imperial_generals.params import BattleParams, CombatParams, MoraleParams
from imperial_generals.utils.combat_efficiency import get_combat_efficiency


# =============================================================================
# CombatParams
# =============================================================================

def test_combat_defaults_come_from_config():
    cfg = get_config()['combat']
    p = CombatParams()
    assert p.weapon_multipliers == {int(k): v for k, v in cfg['weapon_multipliers'].items()}
    for key in ['xp_boost_per_level', 'morale_boost_per_level', 'melee_penalty_factor',
                'ranged_kill_rate', 'melee_kill_rate']:
        assert getattr(p, key) == cfg[key]


@pytest.mark.parametrize("xp, morale, weapon, melee",
                         list(itertools.product([1, 4, 10], [1, 6, 10, 55, 100], [-2, -1, 0, 1, 2], [0, 1])))
def test_efficiency_matches_get_combat_efficiency(xp, morale, weapon, melee):
    assert CombatParams().efficiency(xp, morale, weapon, melee) == get_combat_efficiency(xp, morale, weapon, melee)


def test_get_combat_efficiency_accepts_params():
    p = CombatParams(weapon_multipliers={-2: 0.2, -1: 0.5, 0: 1.0, 1: 2.4, 2: 2.5})
    assert get_combat_efficiency(5, 5, 1, 0, params=p) == p.efficiency(5, 5, 1, 0)
    assert get_combat_efficiency(5, 5, 1, 0, params=p) > get_combat_efficiency(5, 5, 1, 0)


def test_unit_coef_modes():
    p = CombatParams()
    base = p.efficiency(4, 5, 0, 0)
    assert p.unit_coef((4, 5, 0, 0), 'ranged') == base
    assert p.unit_coef((4, 5, 0, 0), 'idle') == base
    assert p.unit_coef((4, 5, 0, 0), 'melee') == base * p.melee_penalty_factor
    assert p.unit_coef((4, 5, 0, 1), 'ranged') == 0.0          # melee-only can't fire
    assert p.unit_coef((4, 5, 0, 1), 'melee') == base            # no penalty in its own element


@pytest.mark.parametrize("overrides", [
    dict(weapon_multipliers={0: 1.0}),                                   # missing weapon codes
    dict(weapon_multipliers={-2: 0.2, -1: 0.5, 0: 0.0, 1: 1.5, 2: 2.5}),  # non-positive multiplier
    dict(xp_boost_per_level=-0.1),
    dict(morale_boost_per_level=-0.1),
    dict(melee_penalty_factor=0.0),
    dict(ranged_kill_rate=0.0),
    dict(melee_kill_rate=-1.0),
])
def test_invalid_combat_params_raise(overrides):
    with pytest.raises(ValueError):
        CombatParams(**overrides)


def test_combat_params_are_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        CombatParams().ranged_kill_rate = 1.0


def test_combat_params_copy_the_multiplier_dict():
    source = {-2: 0.2, -1: 0.5, 0: 1.0, 1: 1.5, 2: 2.5}
    p = CombatParams(weapon_multipliers=source)
    source[0] = 99.0
    assert p.weapon_multipliers[0] == 1.0


# =============================================================================
# MoraleParams lives in params (and is still importable from battles.morale)
# =============================================================================

def test_morale_params_reexported_from_morale_module():
    from imperial_generals.battles.morale import MoraleParams as FromMorale
    assert FromMorale is MoraleParams


# =============================================================================
# BattleParams
# =============================================================================

def test_battle_params_defaults():
    p = BattleParams()
    assert p.combat == CombatParams()
    assert p.morale == MoraleParams()


def test_with_overrides_is_nested_and_leaves_original_unchanged():
    base = BattleParams()
    tuned = base.with_overrides({'combat': {'ranged_kill_rate': 0.01}, 'morale': {'shock_weight': 0.0}})
    assert tuned.combat.ranged_kill_rate == 0.01
    assert tuned.morale.shock_weight == 0.0
    assert tuned.morale.drain_per_hour == base.morale.drain_per_hour
    assert base.combat.ranged_kill_rate == get_config()['combat']['ranged_kill_rate']


def test_partial_weapon_override_merges_with_defaults():
    tuned = BattleParams().with_overrides({'combat': {'weapon_multipliers': {'1': 1.8}}})
    expected = {**CombatParams().weapon_multipliers, 1: 1.8}
    assert tuned.combat.weapon_multipliers == expected


def test_empty_overrides_equal_defaults():
    assert BattleParams().with_overrides({}) == BattleParams()


@pytest.mark.parametrize("overrides", [
    {'weather': {}},                                  # unknown section
    {'combat': {'not_a_key': 1}},                     # unknown key
    {'morale': {'breakfraction_min': 0.2}},           # typo
    {'combat': {'weapon_multipliers': {'7': 1.0}}},   # unknown weapon code
])
def test_unknown_override_raises(overrides):
    with pytest.raises(ValueError):
        BattleParams().with_overrides(overrides)


def test_invalid_override_value_raises():
    with pytest.raises(ValueError):
        BattleParams().with_overrides({'morale': {'break_fraction_min': 0.9}})


def test_to_dict_is_json_safe_and_round_trips():
    tuned = BattleParams().with_overrides({'combat': {'weapon_multipliers': {'2': 3.0}}, 'morale': {'acceleration': 2.0}})
    data = json.loads(json.dumps(tuned.to_dict()))
    assert set(data) == {'combat', 'morale', 'aftermath', 'matchups'}
    assert data['combat']['weapon_multipliers']['2'] == 3.0
    assert BattleParams.from_dict(data) == tuned


def test_from_dict_accepts_partial_data():
    p = BattleParams.from_dict({'morale': {'gain_weight': 0.0}})
    assert p == BattleParams().with_overrides({'morale': {'gain_weight': 0.0}})


def test_battle_params_are_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        BattleParams().combat = CombatParams()
