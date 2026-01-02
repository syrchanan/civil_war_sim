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
export declare class Regiment {
    size: number;
    stats: [number, number, number, number];
    rawMorale: number;
    coef: number;
    law: 'ln' | 'sq';
    /**
    * Initialize a regiment.
    * @param size - Number of soldiers.
    * @param stats - Slash-separated string of four integers (e.g., '4/4/0/0').
    * @param law - Combat law: 'ln' (Linear) or 'sq' (Square).
    * @throws {Error} If `law` is not 'ln' or 'sq', or if stats is not four integers.
    */
    constructor(size: number, stats: string, law: 'ln' | 'sq');
    /**
     * Returns a human-readable summary of the regiment.
     */
    toString(): string;
    /**
     * Returns a code-friendly string representation of the regiment.
     */
    toJSON(): string;
    /**
     * Update the regiment's size.
     * @param newSize - The new size of the regiment.
     */
    updateSize(newSize: number): void;
    /**
     * Update the regiment's stats and recalculate combat efficiency coefficient.
     * @param newStats - Slash-separated string of four integers (e.g., '5/6/1/0').
     * @throws {Error} If newStats is not four integers.
     */
    updateStats(newStats: string): void;
    /**
     * Update the regiment's raw morale and update stats accordingly.
     * @param newMorale - The new raw morale value.
     * @throws {TypeError} If newMorale is not a number.
     */
    updateRawMorale(newMorale: number): void;
}
//# sourceMappingURL=Regiment.d.ts.map