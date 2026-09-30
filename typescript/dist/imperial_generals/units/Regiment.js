import { getClosestMoraleStat, getCombatEfficiency } from '../utils/index.js';
/**
 * Represents a discrete regiment unit on the battlefield.
 *
 * @param size - The number of soldiers in the regiment.
 * @param stats - Slash-separated string of four integers: experience/morale/weapon/melee.
 * @param law - Combat law, either 'ln' (Linear) or 'sq' (Square).
 *
 * @property size - Number of soldiers.
 * @property stats - Tuple of [experience, morale, weapon, melee].
 * @property rawMorale - Raw morale value calculated as morale * 10.
 * @property coef - Combat efficiency coefficient.
 * @property law - Combat law used ('ln' or 'sq').
 *
 */
export class Regiment {
    /**
    * Initialize a regiment.
    * @param size - Number of soldiers.
    * @param stats - Slash-separated string of four integers (e.g., '4/4/0/0').
    * @param law - Combat law: 'ln' (Linear) or 'sq' (Square).
    * @throws {Error} If `law` is not 'ln' or 'sq', or if stats is not four integers.
    */
    constructor(size, stats, law) {
        // checks
        if (!['ln', 'sq'].includes(law)) {
            throw new TypeError("Law must be either 'ln' (Linear) or 'sq' (Square).");
        }
        const statsSplit = stats.split('/');
        if (statsSplit.length !== 4 || !statsSplit.every(s => /^\d+$/.test(s))) {
            throw new Error("Stats must be a slash-separated string of four integers (e.g., '4/4/0/0').");
        }
        // inits
        this.size = size;
        this.stats = statsSplit.map(Number);
        this.coef = getCombatEfficiency(...this.stats);
        this.rawMorale = this.stats[1] * 10; // second num of stats
        this.law = law;
    }
    /**
     * Returns a human-readable summary of the regiment.
     */
    toString() {
        return (`Regiment: ${this.size} men | ` +
            `Stats: xp=${this.stats[0]}, morale=${this.stats[1]}, weapon=${this.stats[2]}, melee=${this.stats[3]} | ` +
            `Raw Morale=${this.rawMorale} | ` +
            `Coef=${this.coef.toFixed(4)} | Law=${this.law}`);
    }
    /**
     * Returns a code-friendly string representation of the regiment.
     */
    toJSON() {
        return `Regiment(size=${this.size}, stats=[${this.stats.join(', ')}], law='${this.law}')`;
    }
    /**
     * Update the regiment's size.
     * @param newSize - The new size of the regiment.
     */
    updateSize(newSize) {
        this.size = newSize;
    }
    /**
     * Update the regiment's stats and recalculate combat efficiency coefficient.
     * @param newStats - Slash-separated string of four integers (e.g., '5/6/1/0').
     * @throws {Error} If newStats is not four integers.
     */
    updateStats(newStats) {
        const statsSplit = newStats.split('/');
        if (statsSplit.length !== 4 || !statsSplit.every(s => /^\d+$/.test(s))) {
            throw new Error("New stats must be a slash-separated string of four integers (e.g., '5/6/1/0').");
        }
        this.stats = statsSplit.map(Number);
        this.coef = getCombatEfficiency(...this.stats);
    }
    /**
     * Update the regiment's raw morale and update stats accordingly.
     * @param newMorale - The new raw morale value.
     * @throws {TypeError} If newMorale is not a number.
     */
    updateRawMorale(newMorale) {
        if (typeof newMorale !== 'number') {
            throw new TypeError('newMorale must be a number.');
        }
        this.rawMorale = newMorale;
        const newStat = getClosestMoraleStat(newMorale);
        this.updateStats(`${this.stats[0]}/${newStat}/${this.stats[2]}/${this.stats[3]}`);
    }
}
//# sourceMappingURL=Regiment.js.map