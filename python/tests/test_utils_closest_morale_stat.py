import os, json
import pytest
from imperial_generals.utils.closest_morale_stat import get_closest_morale_stat

GOLDEN_PATH = os.path.join(os.path.dirname(__file__), '../../test_cases/closest_morale_stat.json')

@pytest.mark.parametrize("case", json.load(open(GOLDEN_PATH)))
def test_get_closest_morale_stat_golden(case):
    if "expected" in case:
        # checking that morale update is properly flooring and truncating
        assert get_closest_morale_stat(case["inputs"]) == case["expected"]
