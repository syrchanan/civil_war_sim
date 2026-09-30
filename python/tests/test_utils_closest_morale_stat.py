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


# Exact behaviour on a fine grid, including ties (x5 rounds down, matching the original first-minimum scan)
@pytest.mark.parametrize("morale, expected", [
    (0, 1), (0.0, 1), (4.99, 1), (10, 1), (14.999, 1), (15, 1), (15.0001, 2),
    (25, 2), (35, 3), (54.5, 5), (55, 5), (55.5, 6), (85, 8), (94.9, 9), (95, 9), (95.1, 10), (100, 10),
])
def test_closest_stat_exact_values_and_ties(morale, expected):
    assert get_closest_morale_stat(morale) == expected


def test_closest_stat_on_a_fine_grid_matches_nearest_level_rule():
    for i in range(0, 10001):
        m = i / 100
        levels = list(range(10, 101, 10))
        nearest = min(levels, key=lambda lv: (abs(lv - m), lv))   # ties go to the lower level
        assert get_closest_morale_stat(m) == nearest // 10, m


def test_out_of_range_raises_value_error():
    with pytest.raises(ValueError):
        get_closest_morale_stat(-1)
    with pytest.raises(ValueError):
        get_closest_morale_stat(101)
