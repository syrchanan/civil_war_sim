import { Regiment } from "./Regiment.js";
/**
 * Class representing an infantry regiment.
 * Extends the base Regiment class.
 *
 * @property unitType - Type of unit ('inf' for infantry).
 * @property size - Number of soldiers.
 * @property stats - Tuple of [experience, morale, weapon, melee].
 * @property rawMorale - Raw morale value calculated as morale * 10.
 * @property coef - Combat efficiency coefficient.
 * @property law - Combat law used ('ln' or 'sq').
 */
export declare class InfantryRegiment extends Regiment {
    unitType: string;
    /**
     * Initialize an infantry regiment.
     * @param size - Number of soldiers.
     * @param stats - Slash-separated string of four integers (e.g., '4/4/0/0').
     * @param law - Combat law: 'ln' (Linear) or 'sq' (Square).
     */
    constructor(size: number, stats: string, law: 'ln' | 'sq');
    /**
     * Returns a human-readable summary of the infantry regiment.
     */
    toString(): string;
    /**
     * Returns a JSON representation of the infantry regiment.
     */
    toJSON(): string;
    /**
     * Returns only the unit type string for display.
     */
    printType(): string;
}
//# sourceMappingURL=InfantryRegiment.d.ts.map