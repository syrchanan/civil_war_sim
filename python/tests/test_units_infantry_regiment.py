import os
import json
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
                if isinstance(v, list) and isinstance(got, tuple):
                    assert list(got) == v
                else:
                    assert got == v


def test_infantry_str():
    reg = InfantryRegiment(1000, '4/4/0/0', 'sq')
    s = str(reg)
    assert '[type: inf]' in s
    assert 'Regiment' in s


def test_infantry_repr():
    reg = InfantryRegiment(1000, '4/4/0/0', 'sq')
    r = repr(reg)
    assert '[type: inf]' in r


def test_infantry_print_type():
    reg = InfantryRegiment(1000, '4/4/0/0', 'sq')
    assert reg.print_type() == 'inf'
