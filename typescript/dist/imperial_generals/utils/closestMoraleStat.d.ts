/**
 * Find the closest morale stat (1-10 scale) to a given morale value (0-100 scale).
 *
 * The function finds the nearest multiple of 10 to the input morale value, then converts it to a 1-10 scale by dividing by 10.
 * Avoids harsh penalties for small morale losses by rounding to the nearest level.
 *
 * @param morale - The current morale value (0-100).
 * @returns The closest morale stat as an integer on a 1-10 scale.
 * @throws {TypeError} If morale is not a number.
 * @throws {RangeError} If morale is not between 0 and 100 (inclusive).
 */
export declare function getClosestMoraleStat(morale: number): number;
//# sourceMappingURL=closestMoraleStat.d.ts.map