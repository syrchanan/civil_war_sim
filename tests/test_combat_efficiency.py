import pytest
from imperial_generals.utils.combat_efficiency import get_combat_efficiency

def test_typical_ranged():
    # Standard musket, average stats, not melee
    coef = get_combat_efficiency(stat_xp=5, stat_morale=50, stat_weapon=0, stat_melee=0)
    assert 0 <= coef <= 1

def test_typical_melee():
    # Standard musket, average stats, melee
    coef_melee = get_combat_efficiency(stat_xp=5, stat_morale=50, stat_weapon=0, stat_melee=1)
    coef_ranged = get_combat_efficiency(stat_xp=5, stat_morale=50, stat_weapon=0, stat_melee=0)
    assert coef_melee < coef_ranged

def test_weapon_types():
    # Test all weapon types
    for weapon, expected in [(-2, 0.2), (-1, 0.5), (0, 1.0), (1, 1.5), (2, 2.0)]:
        coef = get_combat_efficiency(stat_xp=5, stat_morale=50, stat_weapon=weapon, stat_melee=0)
        assert 0 <= coef <= 1

def test_xp_and_morale_clamping():
    # XP and morale below and above valid range
    coef_low = get_combat_efficiency(stat_xp=-5, stat_morale=-10, stat_weapon=0, stat_melee=0)
    coef_high = get_combat_efficiency(stat_xp=100, stat_morale=1000, stat_weapon=0, stat_melee=0)
    assert 0 <= coef_low <= 1
    assert 0 <= coef_high <= 1

def test_weapon_clamping():
    # Weapon below and above valid range
    coef_low = get_combat_efficiency(stat_xp=5, stat_morale=50, stat_weapon=-10, stat_melee=0)
    coef_high = get_combat_efficiency(stat_xp=5, stat_morale=50, stat_weapon=10, stat_melee=0)
    assert 0 <= coef_low <= 1
    assert 0 <= coef_high <= 1

def test_melee_clamping():
    # Melee below and above valid range
    coef_low = get_combat_efficiency(stat_xp=5, stat_morale=50, stat_weapon=0, stat_melee=-5)
    coef_high = get_combat_efficiency(stat_xp=5, stat_morale=50, stat_weapon=0, stat_melee=5)
    assert 0 <= coef_low <= 1
    assert 0 <= coef_high <= 1

def test_minimum_and_maximum():
    # Minimum possible stats
    coef_min = get_combat_efficiency(stat_xp=1, stat_morale=1, stat_weapon=-2, stat_melee=1)
    assert round(coef_min, ndigits=4) == 0.0364
    # Maximum possible stats
    coef_max = get_combat_efficiency(stat_xp=10, stat_morale=100, stat_weapon=2, stat_melee=0)
    assert coef_max == 1

def test_invalid_types():
    # Non-integer types
    with pytest.raises(TypeError):
        get_combat_efficiency(stat_xp=5.5, stat_morale=50, stat_weapon=0, stat_melee=0)
    with pytest.raises(TypeError):
        get_combat_efficiency(stat_xp=5, stat_morale="high", stat_weapon=0, stat_melee=0)

def test_missing_arguments():
    # Missing required arguments
    with pytest.raises(ValueError):
        get_combat_efficiency(stat_xp=None, stat_morale=50, stat_weapon=0, stat_melee=0)
    with pytest.raises(ValueError):
        get_combat_efficiency(stat_xp=5, stat_morale=None, stat_weapon=0, stat_melee=0)
    with pytest.raises(ValueError):
        get_combat_efficiency(stat_xp=5, stat_morale=50, stat_weapon=None, stat_melee=0)
    with pytest.raises(ValueError):
        get_combat_efficiency(stat_xp=5, stat_morale=50, stat_weapon=0, stat_melee=None)

def test_morale_conversion():
    # Morale at 100 should convert to 10
    coef_100 = get_combat_efficiency(stat_xp=5, stat_morale=100, stat_weapon=0, stat_melee=0)
    coef_10 = get_combat_efficiency(stat_xp=5, stat_morale=10, stat_weapon=0, stat_melee=0)
    assert coef_100 >= coef_10
