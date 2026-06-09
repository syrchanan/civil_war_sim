import os
import json
import pytest
import pandas as pd
from imperial_generals.units.Regiment import Regiment
from imperial_generals.battles.Simulation import Simulation


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

def test_simulation_melee_only_vs_ranged_no_zero_division():
    # melee-only unit in ranged mode has coef=0 — must not raise ZeroDivisionError
    reg1 = Regiment(500, '4/4/0/1')   # melee-only
    reg2 = Regiment(500, '4/4/1/0')
    reg1.set_combat_mode('ranged')
    reg2.set_combat_mode('ranged')
    sim = Simulation((reg1, reg2))
    sim.run_simulation(time=1)         # would crash before fix if reg1.coef==0
    assert sim.sim_output['size_1'].iloc[-1] <= 500  # reg1 took casualties (can't fire back)
