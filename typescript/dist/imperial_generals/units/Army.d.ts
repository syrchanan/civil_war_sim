import { Regiment } from './Regiment.js';
/**
 * Represents an army composed of regiments and other subunits.
 *
 * @param faction - The faction or side the army belongs to.
 *
 * @property faction - The faction or side the army belongs to.
 * @property forces - Dictionary mapping regiment names to Regiment instances.
 */
export declare class Army {
    faction: string;
    forces: {
        [key: string]: Regiment;
    };
    /**
     * Initialize an army.
     * @param faction - The faction or side the army belongs to.
     */
    constructor(faction: string);
    /**
     * Returns a human-readable summary of the army.
     */
    toString(): string;
    /**
     * Serializes the army to a JSON-compatible object.
     */
    toJSON(): object;
    /**
     * Adds a regiment to the army.
     * @param name - The name of the regiment.
     * @param regiment - The Regiment instance to add.
     */
    addRegiment(name: string, regiment: Regiment): void;
}
//# sourceMappingURL=Army.d.ts.map