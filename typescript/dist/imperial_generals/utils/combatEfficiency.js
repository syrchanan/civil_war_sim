"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.getCombatEfficiency = getCombatEfficiency;
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
function getCombatEfficiency(statXp, statMorale, statWeapon, statMelee) {
    // =============================
    // INPUT VALIDATION
    // =============================
    const params = [
        ['statXp', statXp],
        ['statMorale', statMorale],
        ['statWeapon', statWeapon],
        ['statMelee', statMelee]
    ];
    for (const [name, value] of params) {
        if (value === undefined || value === null) {
            throw new Error(`${name} must be provided.`);
        }
        if (typeof value !== 'number' || !Number.isFinite(value) || !Number.isInteger(value)) {
            throw new TypeError(`${name} must be an integer.`);
        }
    }
    // =============================
    // CONSTANTS
    // =============================
    const weaponMultipliers = {
        '-2': 0.2, // Unarmed or Pikemen - very low effectiveness
        '-1': 0.5, // Smoothbore matchlocks - inferior
        '0': 1.0, // Smoothbore muskets - standard
        '1': 1.5, // Rifled muskets - improved
        '2': 2.5 // Needler rifles - highly advanced
    };
    const xpBoostPerLevel = 0.04; // 4% per XP above 1
    const moraleBoostPerLevel = 0.02; // 2% per morale above 1
    const meleePenaltyFactor = 0.70; // 30% reduction for melee
    // =============================
    // MAX EFFECTIVENESS CALCULATION
    // =============================
    const maxWeaponBase = Math.max(...Object.values(weaponMultipliers));
    const maxXpAdj = (10 - 1) * xpBoostPerLevel;
    const maxMoraleAdj = (10 - 1) * moraleBoostPerLevel;
    const maxPossibleRawCoef = maxWeaponBase * (1 + maxXpAdj + maxMoraleAdj);
    // =============================
    // FUNCTION LOGIC
    // =============================
    // Convert Morale (10-100) to (1-10) granularity
    let statMorale1to10 = statMorale > 10 ? Math.round(statMorale / 10) : statMorale;
    // Clamp all stats to valid range
    statMorale1to10 = Math.max(1, Math.min(10, statMorale1to10));
    statXp = Math.max(1, Math.min(10, statXp));
    statWeapon = Math.max(-2, Math.min(2, statWeapon));
    statMelee = Math.max(0, Math.min(1, statMelee));
    // XP & Morale adjustments
    const effAdj = 1 + (statXp - 1) * xpBoostPerLevel + (statMorale1to10 - 1) * moraleBoostPerLevel;
    // Raw positive efficiency
    const weaponKey = String(statWeapon);
    const rawCoef = weaponMultipliers[weaponKey] * effAdj;
    // Melee penalty, if applicable
    let coef = statMelee === 1 ? rawCoef * meleePenaltyFactor : rawCoef;
    // Scale for max possible and return result [0, 1]
    return coef / maxPossibleRawCoef;
}
//# sourceMappingURL=combatEfficiency.js.map