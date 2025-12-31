
import numpy as np

def get_combat_efficiency(
    stat_xp: int | np.integer = None,
    stat_morale: int | np.integer = None, 
    stat_weapon: int | np.integer = None, 
    stat_melee: int | np.integer = None
) -> float:
    """
    Calculate the combat efficiency coefficient for a regiment based on experience, morale, weapon, and melee status.

    The function normalizes and clamps input stats, applies weapon multipliers, experience and morale boosts, and a melee penalty if applicable.
    The result is a coefficient between 0 and 1, representing the relative combat effectiveness of the unit.

    Parameters
    ----------
    stat_xp : int
        Experience level of the unit (1-10). Must be provided and an integer.
    stat_morale : int
        Morale value of the unit (0-100, will be converted to 1-10 scale). Must be provided and an integer.
    stat_weapon : int
        Weapon type code:
            -2: Unarmed/Pikemen
            -1: Smoothbore matchlocks
             0: Smoothbore muskets
             1: Rifled muskets
             2: Needler rifles
        Must be provided and an integer.
    stat_melee : int
        Whether the unit is in melee combat (0 = no, 1 = yes). Must be provided and an integer.

    Returns
    -------
    float
        Combat efficiency coefficient (0 to 1).

    Raises
    ------
    ValueError
        If any parameter is not provided.
    TypeError
        If any parameter is not an integer.

    Notes
    -----
    - Morale is converted from a 10-100 scale to 1-10 for calculations.
    - Inputs are clamped to valid ranges.
    - Melee combat applies a penalty to effectiveness.

    """

    # ===========================================
    # INPUT VALIDATION
    # ===========================================

    for name, value in [
        ("stat_xp", stat_xp),
        ("stat_morale", stat_morale),
        ("stat_weapon", stat_weapon),
        ("stat_melee", stat_melee),
    ]:
        if value is None:
            raise ValueError(f"{name} must be provided.")
        if not isinstance(value, (int, np.integer)):
            raise TypeError(f"{name} must be an integer.")

    # ===========================================
    # CONSTANTS
    # ===========================================
    
    # Base effectiveness of a regiment's primary weapon
    weapon_multipliers = {
        '-2': 0.2, # Unarmed or Pikemen - very low effectiveness
        '-1': 0.5, # Smoothbore matchlocks - inferior
        '0': 1.0,  # Smoothbore muskets - standard/old for new regiments
        '1': 1.5,  # Rifled muskets - significant improvement
        '2': 2.5   # Needler rifles - highly advanced, major advantage
    }

    # Incremental effectiveness boosts based on training and morale
    xp_boost_per_level = 0.04 # 4% increase in effectiveness per XP level above 1
    morale_boost_per_level = 0.02 # 2% increase in effectiveness per morale level above 1

    # Melee combat penalty (less effective than aimed fire)
    melee_penalty_factor = 0.70 # 30% reduction in effectiveness for melee combat

    # ===========================================
    # MAX EFFECTIVENESS CALCULATION
    # ===========================================
    
    # Fixed value ensures the final coefficient is between 0 and 1, where 1 is highest possible effectiveness (one shot, one kill principle)
    max_weapon_base = max(weapon_multipliers.values())
    max_xp_adj = (10 - 1) * xp_boost_per_level
    max_morale_adj = (10 - 1) * morale_boost_per_level
    max_possible_raw_coefficient = max_weapon_base * (1 + max_xp_adj + max_morale_adj)

    # ===========================================
    # FUNCTION LOGIC
    # ===========================================

    # Morale conversion - dynamic morale system tracks granular morale 10-100, which needs to be converted back to 1-10 for coefficient calcs
    stat_morale_1_10 = round(stat_morale/10, ndigits=0) if stat_morale > 10 else stat_morale

    # Input clamping to ensure within valid range
    stat_morale_1_10 = max(1, min(10, stat_morale_1_10))
    stat_xp = max(1, min(10, stat_xp))
    stat_weapon = max(-2, min(2, stat_weapon))
    stat_melee = max(0, min(1, stat_melee))

    # XP & Morale adjustments
    eff_adj = 1 + (stat_xp - 1) * xp_boost_per_level + (stat_morale_1_10 - 1) * morale_boost_per_level

    # Final positive efficiency
    raw_coef = weapon_multipliers.get(str(stat_weapon)) * eff_adj

    # Apply melee penalty if needed
    coef = raw_coef * melee_penalty_factor if stat_melee == 1 else raw_coef

    # Scale and return result
    return coef / max_possible_raw_coefficient

if __name__ == "__main__":
    coef = get_combat_efficiency(stat_xp=5, stat_morale=50, stat_weapon=1, stat_melee=0)
    print(f"Combat Efficiency Coefficient: {coef:.4f}")
