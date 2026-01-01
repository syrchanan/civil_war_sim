import os, json
import pytest
from imperial_generals.units.InfantryRegiment import InfantryRegiment

def load_infantry_golden_cases():
    path = os.path.join(os.path.dirname(__file__), '../../test_cases/infantry_regiment_examples.json')
    with open(path) as f:
        return json.load(f)

@pytest.mark.parametrize("case", load_infantry_golden_cases())
def test_infantry_regiment_golden(case):
    reg = InfantryRegiment(**case['inputs'])
    if 'actions' in case:
        for action in case['actions']:
            meth = getattr(reg, action['method'])
            if isinstance(action["args"], list):
                meth(*action["args"])
            else:
                meth(action["args"])
    if 'expected' in case:
        for k, v in case['expected'].items():
            if hasattr(reg, k):
                got = getattr(reg, k)
                # For stats tuple/list, need to cast for exact match
                if isinstance(v, list) and isinstance(got, tuple):
                    assert list(got) == v
                else:
                    assert got == v
