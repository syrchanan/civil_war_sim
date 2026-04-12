import os
import json
import pytest
from imperial_generals.units.InfantryRegiment import InfantryRegiment
from imperial_generals.utils.unit_types import UNIT_SUBTYPES

def load_infantry_golden_cases():
    path = os.path.join(os.path.dirname(__file__), '../../test_cases/infantry_regiment_examples.json')
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Subtype
# ---------------------------------------------------------------------------

def test_infantry_subtype_valid():
    for subtype in UNIT_SUBTYPES['inf']:
        reg = InfantryRegiment(500, '4/4/0/0', 'ln', subtype=subtype)
        assert reg.subtype == subtype

def test_infantry_subtype_in_str():
    reg = InfantryRegiment(500, '4/4/0/0', 'ln', subtype='line')
    assert 'line' in str(reg)

def test_infantry_invalid_subtype_raises():
    with pytest.raises(ValueError, match="subtype"):
        InfantryRegiment(500, '4/4/0/0', 'ln', subtype='cuirassier')

def test_infantry_missing_subtype_raises():
    with pytest.raises(TypeError):
        InfantryRegiment(500, '4/4/0/0', 'ln')


# ---------------------------------------------------------------------------
# Golden cases
# ---------------------------------------------------------------------------

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
