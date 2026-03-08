import os
import json
import pytest
from imperial_generals.utils.closest_morale_stat import get_closest_morale_stat

GOLDEN_PATH = os.path.join(os.path.dirname(__file__), '../../test_cases/closest_morale_stat.json')


@pytest.mark.parametrize("case", json.load(open(GOLDEN_PATH)))
def test_get_closest_morale_stat_golden(case):
    if "expected" in case:
        assert get_closest_morale_stat(case["inputs"]) == case["expected"]


def test_non_numeric_raises_type_error():
    with pytest.raises(TypeError):
        get_closest_morale_stat("high")
    with pytest.raises(TypeError):
        get_closest_morale_stat([50])
    with pytest.raises(TypeError):
        get_closest_morale_stat(None)


def test_out_of_range_raises_value_error():
    with pytest.raises(ValueError):
        get_closest_morale_stat(-1)
    with pytest.raises(ValueError):
        get_closest_morale_stat(101)
