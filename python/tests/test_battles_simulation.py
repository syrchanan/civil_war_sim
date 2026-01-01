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
        # checking that expected columns are in the output
        for col in case["expectedOutputFields"]:
            assert col in df.columns
    if "outputShouldIncludeAtLeastRows" in case:
        # checking that at least N rows are in the output
        assert len(df) >= case["outputShouldIncludeAtLeastRows"]
    if "atLeastOneZeroIn" in case:
        # checking that at least one of the sides ends with 0 troops
        last_row = df.iloc[-1]
        assert any(last_row[col] == 0 for col in case["atLeastOneZeroIn"])

GOLDEN_PATH = os.path.join(os.path.dirname(__file__), '../../test_cases/battle_simulation_basic.json')

@pytest.mark.parametrize("case", json.load(open(GOLDEN_PATH)))
def test_simulate_battle_golden(case):
    run_simulate_battle_case(case)
