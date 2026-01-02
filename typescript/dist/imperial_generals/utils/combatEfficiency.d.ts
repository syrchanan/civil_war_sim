/**
 * Calculate the combat efficiency coefficient for a regiment based on experience, morale, weapon, and melee status.
 *
 * The function normalizes and clamps input stats, applies weapon multipliers, experience and morale boosts, and a melee penalty if applicable.
 * The result is a coefficient between 0 and 1, representing the relative combat effectiveness of the unit.
 *
 * @param statXp - Experience level of the unit (1-10). Must be provided and an integer.
 * @param statMorale - Morale value of the unit (0-100, will be converted to 1-10 scale). Must be provided and an integer.
 * @param statWeapon - Weapon type code: -2: Unarmed/Pikemen, -1: Smoothbore matchlocks, 0: Smoothbore muskets, 1: Rifled muskets, 2: Needler rifles.
 * @param statMelee - Whether the unit is in melee combat (0 = no, 1 = yes). Must be provided and an integer.
 * @returns Combat efficiency coefficient (0 to 1).
 * @throws Error if any parameter is not provided or not an integer.
 *
 * Notes:
 * - Morale is converted from a 10-100 scale to 1-10 for calculations.
 * - Inputs are clamped to valid ranges.
 * - Melee combat applies a penalty to effectiveness.
 */
export declare function getCombatEfficiency(statXp: number, statMorale: number, statWeapon: number, statMelee: number): number;
//# sourceMappingURL=combatEfficiency.d.ts.map