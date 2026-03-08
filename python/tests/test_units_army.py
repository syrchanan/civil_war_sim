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
                reg = make_reg(args[-1])
                method(args[0], reg)
            else:
                method(*args)
    if 'expected' in case and 'forces' in case['expected']:
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
        assert len(army.forces) == case['expectedForcesCount']


def test_add_regiment_invalid_type_raises():
    army = Army("Union")
    with pytest.raises(TypeError, match="regiment must be an instance of Regiment"):
        army.add_regiment("bad_reg", "not a regiment")


def test_army_str():
    army = Army("Confederate")
    reg = Regiment(1000, '4/4/0/0', 'sq')
    army.add_regiment("1st VA", reg)
    s = str(army)
    assert 'Confederate' in s
    assert '1st VA' in s


def test_army_repr():
    army = Army("Union")
    r = repr(army)
    assert 'Union' in r
