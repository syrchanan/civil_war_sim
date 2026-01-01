import os
import json
import pytest
from imperial_generals.units.Regiment import Regiment

def load_regiment_golden_cases():
    path = os.path.join(os.path.dirname(__file__), '../../test_cases/regiment_examples.json')
    with open(path) as f:
        return json.load(f)

@pytest.mark.parametrize("case", load_regiment_golden_cases())
def test_regiment_golden(case):
    # checking validity of law and stats during creation
    if case.get('shouldError'):
        with pytest.raises(Exception):
            Regiment(**case['inputs'])
    else:
        # checking attributes correctly parsed
        reg = Regiment(**case['inputs'])
        expected = case['expected']
        assert reg.size == expected['size']
        assert reg.stats == tuple(expected['stats'])
        assert reg.law == expected['law']
