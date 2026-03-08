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
    if case.get('shouldError'):
        with pytest.raises(Exception):
            Regiment(**case['inputs'])
    else:
        reg = Regiment(**case['inputs'])
        expected = case['expected']
        assert reg.size == expected['size']
        assert reg.stats == tuple(expected['stats'])
        assert reg.law == expected['law']


def test_regiment_str():
    reg = Regiment(1000, '4/4/0/0', 'sq')
    s = str(reg)
    assert '1000' in s
    assert 'xp=4' in s


def test_regiment_repr():
    reg = Regiment(1000, '4/4/0/0', 'sq')
    r = repr(reg)
    assert 'Regiment(' in r
    assert '1000' in r


def test_update_stats_invalid_raises():
    reg = Regiment(1000, '4/4/0/0', 'sq')
    with pytest.raises(ValueError):
        reg.update_stats('4/4/0')          # too few parts
    with pytest.raises(ValueError):
        reg.update_stats('a/b/c/d')        # non-integer parts


def test_update_raw_morale_invalid_type_raises():
    reg = Regiment(1000, '4/4/0/0', 'sq')
    with pytest.raises(TypeError):
        reg.update_raw_morale(50)          # int, not float
    with pytest.raises(TypeError):
        reg.update_raw_morale('50.0')


def test_update_raw_morale_valid():
    reg = Regiment(1000, '4/4/0/0', 'sq')
    reg.update_raw_morale(60.0)
    assert reg.raw_morale == 60.0


def test_raw_morale_uses_config_scale_factor():
    from imperial_generals.config import get_config
    scale = get_config()['morale']['raw_scale_factor']
    reg = Regiment(1000, '5/6/0/0', 'sq')
    assert reg.raw_morale == float(6 * scale)
