import pytest
import numpy as np
from imperial_generals.utils.closest_morale_stat import get_closest_morale_stat

def test_typical_values():
    # Test mapping for typical morale values
    assert get_closest_morale_stat(95) == 9
    assert get_closest_morale_stat(87) == 9
    assert get_closest_morale_stat(76) == 8
    assert get_closest_morale_stat(64) == 6
    assert get_closest_morale_stat(53) == 5
    assert get_closest_morale_stat(42) == 4
    assert get_closest_morale_stat(31) == 3
    assert get_closest_morale_stat(20) == 2
    assert get_closest_morale_stat(9) == 1
    assert get_closest_morale_stat(0) == 1

@pytest.mark.parametrize("morale,expected", [
    (100, 10), (99.9, 10), (90, 9), (10, 1), (0, 1)
])
def test_boundaries(morale, expected):
    assert get_closest_morale_stat(morale) == expected

@pytest.mark.parametrize("bad_type", [None, "fifty", [], {}, object()])
def test_type_error(bad_type):
    with pytest.raises(TypeError):
        get_closest_morale_stat(bad_type)

@pytest.mark.parametrize("bad_value", [-1, 101, 1000, -50])
def test_value_error(bad_value):
    with pytest.raises(ValueError):
        get_closest_morale_stat(bad_value)

def test_numpy_types():
    # Should accept numpy int and float
    assert get_closest_morale_stat(np.int32(55)) == 5
    assert get_closest_morale_stat(np.float64(45.0)) == 4
    assert get_closest_morale_stat(np.float32(10.0)) == 1

def test_rounding_behavior():
    # Test values near boundaries
    assert get_closest_morale_stat(14.9) == 1
    assert get_closest_morale_stat(15.1) == 2
    assert get_closest_morale_stat(24.9) == 2
    assert get_closest_morale_stat(25.1) == 3
