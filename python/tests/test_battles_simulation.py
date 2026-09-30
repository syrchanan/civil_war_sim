import os
import json
import pytest
import pandas as pd
from imperial_generals.units.Regiment import Regiment
from imperial_generals.battles.Simulation import Simulation
from imperial_generals.utils import Rng
from imperial_generals.battles.morale import MoraleParams, MoraleState, break_fraction
from imperial_generals.params import BattleParams, CombatParams
from imperial_generals.config import get_config


def make_regiment(obj):
    return Regiment(obj["size"], obj["stats"])


def run_simulate_battle_case(case):
    reg1, reg2 = [make_regiment(u) for u in case['inputs']['units']]
    sim = Simulation((reg1, reg2))
    sim.run_simulation(time=case['inputs']['time'])
    df = sim.sim_output
    if "expectedOutputFields" in case:
        for col in case["expectedOutputFields"]:
            assert col in df.columns
    if "outputShouldIncludeAtLeastRows" in case:
        assert len(df) >= case["outputShouldIncludeAtLeastRows"]
    if "atLeastOneZeroIn" in case:
        last_row = df.iloc[-1]
        assert any(last_row[col] == 0 for col in case["atLeastOneZeroIn"])


GOLDEN_PATH = os.path.join(os.path.dirname(__file__), '../../test_cases/battle_simulation_basic.json')


@pytest.mark.parametrize("case", json.load(open(GOLDEN_PATH)))
def test_simulate_battle_golden(case):
    run_simulate_battle_case(case)


# =============================================================================
# Construction validation
# =============================================================================

def test_invalid_forces_raises():
    with pytest.raises(ValueError):
        Simulation((Regiment(100, '4/4/0/0'),))          # only one regiment
    with pytest.raises(ValueError):
        Simulation(Regiment(100, '4/4/0/0'))             # not a tuple
    with pytest.raises(ValueError):
        Simulation(('not', 'regiments'))                  # wrong types


# =============================================================================
# String representations
# =============================================================================

def test_str_before_simulation():
    reg1 = Regiment(1000, '4/4/0/0')
    reg2 = Regiment(800,  '3/5/0/0')
    sim = Simulation((reg1, reg2))
    s = str(sim)
    assert 'Simulation(' in s
    assert 'losses' in s


def test_repr_before_simulation():
    reg1 = Regiment(1000, '4/4/0/0')
    reg2 = Regiment(800,  '3/5/0/0')
    sim = Simulation((reg1, reg2))
    r = repr(sim)
    assert 'Simulation(' in r


def test_str_after_simulation():
    reg1 = Regiment(1000, '4/4/0/0')
    reg2 = Regiment(800,  '3/5/0/0')
    sim = Simulation((reg1, reg2))
    sim.run_simulation(time=1)
    s = str(sim)
    assert 'Simulation(' in s
    assert 'losses' in s


# =============================================================================
# _compute_rate dispatches on effective_law
# =============================================================================

def test_compute_rate_square_law():
    reg = Regiment(1000, '4/4/1/0')
    reg.set_combat_mode('ranged')   # effective_law == 'sq'
    sizes = [1000, 800]
    front_sizes = [200, 150]
    coef = [0.5, 0.4]
    rate = Simulation._compute_rate(reg, sizes, coef, front_sizes, 0)
    # square law uses total opponent size, not front_size
    assert rate == pytest.approx(-coef[1] * sizes[1])

def test_compute_rate_linear_law_uses_product_of_fronts():
    reg = Regiment(1000, '4/4/1/0', front_size=200)
    reg.set_combat_mode('melee')    # effective_law == 'ln'
    sizes = [1000, 800]
    front_sizes = [200, 150]        # effective fronts pre-computed by simulation
    coef = [0.5, 0.4]
    rate = Simulation._compute_rate(reg, sizes, coef, front_sizes, 0)
    # linear law: -coef_B * front_A * front_B
    assert rate == pytest.approx(-coef[1] * front_sizes[0] * front_sizes[1])

def test_compute_rate_linear_law_shrinking_front_reduces_rate():
    # as front_A shrinks (casualties), rate drops proportionally
    reg = Regiment(1000, '4/4/1/0', front_size=200)
    reg.set_combat_mode('melee')
    coef = [0.5, 0.4]
    rate_full = Simulation._compute_rate(reg, [1000, 800], coef, [200, 150], 0)
    rate_half = Simulation._compute_rate(reg, [500, 800], coef, [100, 150], 0)
    assert abs(rate_half) == pytest.approx(abs(rate_full) / 2)

def test_compute_rate_melee_only_ranged_is_zero_coef():
    reg = Regiment(500, '4/4/0/1')
    reg.set_combat_mode('ranged')   # melee-only can't fire
    sizes = [500, 400]
    front_sizes = [500, 400]
    coef = [reg.coef, 0.3]         # coef == 0.0 for melee-only in ranged
    rate = Simulation._compute_rate(reg, sizes, coef, front_sizes, 0)
    # Rate uses coef[1-0]=coef[1], independent of this regiment's coef
    assert rate == pytest.approx(-coef[1] * sizes[1])

# =============================================================================
# Seeded RNG — reproducible battles
# =============================================================================

def _run_seeded(seed):
    sim = Simulation((Regiment(300, '4/4/0/0'), Regiment(250, '3/5/0/0')), rng=Rng(seed))
    sim.run_simulation(time=60)
    return sim.sim_output

def test_same_seed_reproduces_battle():
    pd.testing.assert_frame_equal(_run_seeded(42), _run_seeded(42))

def test_different_seed_changes_battle():
    assert not _run_seeded(1).equals(_run_seeded(2))

def test_simulation_does_not_use_global_numpy_random(monkeypatch):
    import numpy as np
    def boom(*args, **kwargs):
        raise AssertionError("global np.random used")
    monkeypatch.setattr(np.random, 'exponential', boom)
    _run_seeded(3)

def test_default_rng_is_created_when_not_given():
    sim = Simulation((Regiment(100, '4/4/0/0'), Regiment(100, '4/4/0/0')))
    assert isinstance(sim.rng, Rng)

def test_invalid_rng_raises():
    with pytest.raises(TypeError):
        Simulation((Regiment(100, '4/4/0/0'), Regiment(100, '4/4/0/0')), rng=42)


def _one_sided(seed=4):
    victim = Regiment(300, '4/6/0/1')    # melee-only in ranged mode: cannot fire back
    shooter = Regiment(300, '4/6/0/0')
    victim.set_combat_mode('ranged')
    shooter.set_combat_mode('ranged')
    sim = Simulation((victim, shooter), rng=Rng(seed))
    sim.run_simulation(time=60)
    return sim

def test_one_sided_fire_records_losses():
    # regression: the non-firing side's rate is -0.0, which was misread as "reinforcement"
    # and stopped any losses being recorded
    sim = _one_sided()
    assert sim.casualties['losses'][0] == 300 - sim.forces[0].size
    assert sim.casualties['losses'][0] > 0
    assert sim.casualties['losses'][1] == 0

def test_one_sided_fire_lowers_victim_morale():
    sim = _one_sided()
    assert sim.casualties['morale'][0] < 60.0


# =============================================================================
# Morale model + game time in minutes (roadmap A2)
# =============================================================================

def _firefight(size=1000, stats=('4/5/0/0', '4/5/0/0'), minutes=60, seed=0, params=None, record_history=True):
    reg1, reg2 = Regiment(size, stats[0]), Regiment(size, stats[1])
    reg1.set_combat_mode('ranged')
    reg2.set_combat_mode('ranged')
    sim = Simulation((reg1, reg2), rng=Rng(seed), params=params)
    sim.run_simulation(time=minutes, record_history=record_history)
    return sim

def test_each_side_has_a_morale_state():
    sim = Simulation((Regiment(500, '4/5/0/0'), Regiment(400, '7/3/1/0')), rng=Rng(1))
    s1, s2 = sim.morale_states
    assert isinstance(s1, MoraleState) and isinstance(s2, MoraleState)
    assert (s1.initial_size, s2.initial_size) == (500, 400)
    assert s1.break_fraction == break_fraction(4, 5, s1.params)
    assert s2.break_fraction == break_fraction(7, 3, s2.params)

def test_morale_params_are_passed_to_both_sides():
    params = BattleParams(morale=MoraleParams(drain_per_hour=0.2))
    sim = Simulation((Regiment(100, '4/5/0/0'), Regiment(100, '4/5/0/0')), rng=Rng(1), params=params)
    assert all(s.params is params.morale for s in sim.morale_states)


# =============================================================================
# Per-battle parameters (roadmap A3)
# =============================================================================

def test_default_params_when_omitted():
    sim = Simulation((Regiment(100, '4/5/0/0'), Regiment(100, '4/5/0/0')), rng=Rng(1))
    assert sim.params == BattleParams()

def test_invalid_params_type_raises():
    with pytest.raises(TypeError):
        Simulation((Regiment(100, '4/5/0/0'), Regiment(100, '4/5/0/0')), params={'combat': {}})

def _mean_losses(params, stats=('4/5/0/0', '4/5/0/0'), seeds=range(20), minutes=60):
    totals = [0, 0]
    for seed in seeds:
        sim = _firefight(stats=stats, minutes=minutes, seed=seed, params=params)
        totals[0] += sim.casualties['losses'][0]
        totals[1] += sim.casualties['losses'][1]
    return [t / len(seeds) for t in totals]

def test_kill_rate_override_scales_casualties():
    base = BattleParams()
    doubled = base.with_overrides({'combat': {'ranged_kill_rate': base.combat.ranged_kill_rate * 2}})
    ratio = sum(_mean_losses(doubled)) / sum(_mean_losses(base))
    assert 1.7 < ratio < 2.3

def test_weapon_override_changes_who_wins_the_firefight():
    stats = ('4/5/1/0', '4/5/0/0')      # rifled v smoothbore
    assert _mean_losses(BattleParams(), stats)[1] > _mean_losses(BattleParams(), stats)[0]
    weak_rifles = BattleParams().with_overrides({'combat': {'weapon_multipliers': {'1': 0.3}}})
    losses = _mean_losses(weak_rifles, stats)
    assert losses[0] > losses[1]

def test_overrides_do_not_leak_into_global_config_or_regiments():
    before = get_config()['combat']['ranged_kill_rate']
    tuned = BattleParams().with_overrides({'combat': {'ranged_kill_rate': 0.05, 'weapon_multipliers': {'0': 2.0}}})
    sim = _firefight(params=tuned)
    assert get_config()['combat']['ranged_kill_rate'] == before
    reg = Regiment(100, '4/5/0/0')
    assert reg.coef == CombatParams().efficiency(4, 5, 0, 0)

def test_regiment_coef_with_params():
    reg = Regiment(100, '4/5/1/0')
    reg.set_combat_mode('melee')
    p = CombatParams(melee_penalty_factor=0.5)
    assert reg.coef_with(p) == p.efficiency(4, 5, 1, 0) * 0.5
    assert reg.coef == reg.coef_with(CombatParams())

def test_who_gets_hit_is_proportional_to_casualty_rates():
    # huge units over a short window: sizes barely change, so rates stay ~fixed.
    # Side 1 (smoothbore) suffers the rifled side's rate, 1.5x what side 0 suffers.
    losses = [0, 0]
    for seed in range(10):
        sim = _firefight(size=20_000, stats=('4/5/1/0', '4/5/0/0'), minutes=5, seed=seed, record_history=False)
        losses[0] += sim.casualties['losses'][0]
        losses[1] += sim.casualties['losses'][1]
    assert losses[1] / losses[0] == pytest.approx(1.5, rel=0.05)

def test_each_casualty_uses_one_exponential_and_one_uniform_draw(monkeypatch):
    calls = {'exponential': 0}
    original = Rng.exponential
    def counting(self, rate):
        calls['exponential'] += 1
        return original(self, rate)
    monkeypatch.setattr(Rng, 'exponential', counting)
    sim = _firefight(minutes=30, seed=2, record_history=False)
    events = int(sim.casualties['losses'].sum())
    assert calls['exponential'] == events + 1     # +1: the draw that lands past the time limit

def test_debug_logging_emits_per_event_state(caplog):
    import logging
    with caplog.at_level(logging.DEBUG):
        _firefight(size=50, minutes=30, seed=1)
    assert any('sizes:' in r.getMessage() for r in caplog.records if r.levelno == logging.DEBUG)

def test_record_history_off_gives_identical_outcome():
    with_history = _firefight(minutes=240, seed=11)
    without = _firefight(minutes=240, seed=11, record_history=False)
    assert without.casualties['losses'].tolist() == with_history.casualties['losses'].tolist()
    assert [s.morale for s in without.morale_states] == [s.morale for s in with_history.morale_states]
    assert [r.size for r in without.forces] == [r.size for r in with_history.forces]
    assert len(without.sim_output) == 1          # only the starting row
    assert len(with_history.sim_output) > 100

def test_even_firefight_costs_5_to_10_percent_per_hour():
    fractions = []
    for seed in range(20):
        sim = _firefight(seed=seed)
        fractions.extend(loss / 1000 for loss in sim.casualties['losses'])
    mean = sum(fractions) / len(fractions)
    assert 0.05 <= mean <= 0.10

def test_no_events_after_time_limit_and_clock_ends_at_limit():
    sim = _firefight(minutes=45)
    assert sim.sim_output['time'].max() == 45
    assert sim.sim_output['time'].iloc[-1] == 45

def test_output_morale_matches_morale_states_and_regiments():
    sim = _firefight(minutes=90, seed=3)
    last = sim.sim_output.iloc[-1]
    for i, state in enumerate(sim.morale_states):
        assert last[f'morale_{i + 1}'] == state.morale
        assert sim.forces[i].raw_morale == state.morale
        assert sim.casualties['morale'][i] == state.morale

def test_morale_falls_during_a_firefight():
    sim = _firefight(minutes=120, seed=5)
    assert all(state.morale < state.initial_morale for state in sim.morale_states)

def test_helpless_unit_breaks_before_annihilation():
    victim = Regiment(300, '4/5/0/1')     # melee-only in ranged mode: cannot fire back
    shooter = Regiment(300, '4/5/0/0')
    victim.set_combat_mode('ranged')
    shooter.set_combat_mode('ranged')
    sim = Simulation((victim, shooter), rng=Rng(2))
    sim.run_simulation(time=100_000)
    assert sim.morale_states[0].broken
    assert 0 < victim.size < 300
    assert sim.sim_output['time'].iloc[-1] < 100_000     # ended early on the break

def test_green_unit_breaks_before_veteran_in_even_fire():
    sim = _firefight(stats=('1/2/0/0', '9/8/0/0'), minutes=100_000, seed=7)
    assert sim.morale_states[0].broken
    assert not sim.morale_states[1].broken


def test_no_casualties_when_neither_side_can_fire():
    # both melee-only in ranged mode: every clock is inf, nothing should happen
    reg1, reg2 = Regiment(300, '4/6/0/1'), Regiment(300, '4/6/0/1')
    reg1.set_combat_mode('ranged')
    reg2.set_combat_mode('ranged')
    sim = Simulation((reg1, reg2), rng=Rng(1))
    sim.run_simulation(time=1)
    assert (reg1.size, reg2.size) == (300, 300)
    assert sim.casualties['losses'].tolist() == [0, 0]
    assert len(sim.sim_output) == 1


def test_simulation_melee_only_vs_ranged_no_zero_division():
    # melee-only unit in ranged mode has coef=0 — must not raise ZeroDivisionError
    reg1 = Regiment(500, '4/4/0/1')   # melee-only
    reg2 = Regiment(500, '4/4/1/0')
    reg1.set_combat_mode('ranged')
    reg2.set_combat_mode('ranged')
    sim = Simulation((reg1, reg2))
    sim.run_simulation(time=1)         # would crash before fix if reg1.coef==0
    assert sim.sim_output['size_1'].iloc[-1] <= 500  # reg1 took casualties (can't fire back)
