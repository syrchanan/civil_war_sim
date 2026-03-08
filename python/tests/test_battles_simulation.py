import os
import json
import pytest
import pandas as pd
from imperial_generals.units.Regiment import Regiment
from imperial_generals.battles.Simulation import Simulation


def make_regiment(obj):
    return Regiment(obj["size"], obj["stats"], obj["law"])


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
        Simulation((Regiment(100, '4/4/0/0', 'sq'),))          # only one regiment
    with pytest.raises(ValueError):
        Simulation(Regiment(100, '4/4/0/0', 'sq'))             # not a tuple
    with pytest.raises(ValueError):
        Simulation(('not', 'regiments'))                        # wrong types


# =============================================================================
# String representations
# =============================================================================

def test_str_before_simulation():
    reg1 = Regiment(1000, '4/4/0/0', 'sq')
    reg2 = Regiment(800,  '3/5/0/0', 'sq')
    sim = Simulation((reg1, reg2))
    s = str(sim)
    assert 'Simulation(' in s
    assert 'unset' in s         # rate_funcs not built yet
    assert 'losses' in s


def test_repr_before_simulation():
    reg1 = Regiment(1000, '4/4/0/0', 'sq')
    reg2 = Regiment(800,  '3/5/0/0', 'sq')
    sim = Simulation((reg1, reg2))
    r = repr(sim)
    assert 'Simulation(' in r


def test_str_after_simulation():
    reg1 = Regiment(1000, '4/4/0/0', 'sq')
    reg2 = Regiment(800,  '3/5/0/0', 'sq')
    sim = Simulation((reg1, reg2))
    sim.run_simulation(time=1)
    s = str(sim)
    assert 'set' in s           # rate_funcs built
    assert 'losses' in s


# =============================================================================
# build_lanch_diffeq validation
# =============================================================================

def test_build_lanch_diffeq_unknown_law():
    reg1 = Regiment(1000, '4/4/0/0', 'sq')
    reg2 = Regiment(800,  '3/5/0/0', 'sq')
    sim = Simulation((reg1, reg2))
    reg1.law = 'bad_law'
    with pytest.raises(ValueError, match='Unknown Lanchester law'):
        sim.build_lanch_diffeq()
