import os
import json
import pytest
from imperial_generals.units.Army import Army
from imperial_generals.units.Regiment import Regiment

def load_army_golden_cases():
    path = os.path.join(os.path.dirname(__file__), '../../test_cases/army_examples.json')
    with open(path) as f:
        return json.load(f)

def make_reg(obj):
    return Regiment(obj["size"], obj["stats"], obj["law"])

@pytest.mark.parametrize("case", load_army_golden_cases())
def test_army_golden(case):
    army = Army(**case['inputs'])
    if 'actions' in case:
        for action in case['actions']:
            method = getattr(army, action['method'])
            args = action['args']
            if isinstance(args[-1], dict):
                # assume regiment creation
                reg = make_reg(args[-1])
                method(args[0], reg)
            else:
                method(*args)
    if 'expected' in case and 'forces' in case['expected']:
        # checking populated forces match expected forces
        for k, v in case['expected']['forces'].items():
            assert k in army.forces
            reg = army.forces[k]
            for key2, val2 in v.items():
                got = getattr(reg, key2)
                if isinstance(val2, list):
                    assert list(got) == val2
                else:
                    assert got == val2
    if case.get('expectedForcesCount', None) is not None:
        # checking the count of forces
        assert len(army.forces) == case['expectedForcesCount']
