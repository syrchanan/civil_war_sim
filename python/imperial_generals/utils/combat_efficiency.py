
import numpy as np

from imperial_generals.params import CombatParams, default_combat_params


def get_combat_efficiency(
    stat_xp: int | np.integer = None,
    stat_morale: int | np.integer = None,
    stat_weapon: int | np.integer = None,
    stat_melee: int | np.integer = None,
    params: CombatParams | None = None,
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
    params : CombatParams, optional
        Per-battle constants; defaults to config (see ``imperial_generals.params``).

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
    - The formula lives in ``CombatParams.efficiency``.
    """

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

    return (params or default_combat_params()).efficiency(stat_xp, stat_morale, stat_weapon, stat_melee)


if __name__ == "__main__":  # pragma: no cover
    coef = get_combat_efficiency(stat_xp=5, stat_morale=50, stat_weapon=1, stat_melee=0)
    print(f"Combat Efficiency Coefficient: {coef:.4f}")
