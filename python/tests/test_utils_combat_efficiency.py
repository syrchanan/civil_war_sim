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


def test_none_input_raises_value_error():
    with pytest.raises(ValueError, match="stat_xp must be provided"):
        get_combat_efficiency(stat_xp=None, stat_morale=50, stat_weapon=0, stat_melee=0)


def test_non_integer_input_raises_type_error():
    with pytest.raises(TypeError, match="stat_xp must be an integer"):
        get_combat_efficiency(stat_xp=5.5, stat_morale=50, stat_weapon=0, stat_melee=0)
