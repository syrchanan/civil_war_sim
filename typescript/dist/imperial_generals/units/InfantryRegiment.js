"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.InfantryRegiment = void 0;
const Regiment_1 = require("./Regiment");
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
class InfantryRegiment extends Regiment_1.Regiment {
    // TODO - restrict unitType to 'inf' | 'cav' | 'art'
    /**
     * Initialize an infantry regiment.
     * @param size - Number of soldiers.
     * @param stats - Slash-separated string of four integers (e.g., '4/4/0/0').
     * @param law - Combat law: 'ln' (Linear) or 'sq' (Square).
     */
    constructor(size, stats, law) {
        super(size, stats, law);
        this.unitType = 'inf';
    }
    /**
     * Returns a human-readable summary of the infantry regiment.
     */
    toString() {
        return `Infantry | ${super.toString()}`;
    }
    /**
     * Returns a JSON representation of the infantry regiment.
     */
    toJSON() {
        return `InfantryRegiment(size=${this.size}, stats=[${this.stats.join(', ')}], law='${this.law}')`;
    }
    /**
     * Returns only the unit type string for display.
     */
    printType() {
        // TODO remove here and in Python
        return this.unitType;
    }
}
exports.InfantryRegiment = InfantryRegiment;
//# sourceMappingURL=InfantryRegiment.js.map