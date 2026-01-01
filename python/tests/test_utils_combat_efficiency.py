import os
import json
import pytest
from imperial_generals.utils.combat_efficiency import get_combat_efficiency

GOLDEN_PATH = os.path.join(os.path.dirname(__file__), '../../test_cases/combat_efficiency.json')

@pytest.mark.parametrize("case", json.load(open(GOLDEN_PATH)))
def test_get_combat_efficiency_golden(case):
    result = get_combat_efficiency(**case["inputs"])
    if "expected" in case:
        # checking that value is expected (for each extreme)
        assert round(result, 4) == case["expected"]
    elif "expectedRange" in case:
        # checking that result is within range
        lo, hi = case["expectedRange"]
        assert lo <= result <= hi
