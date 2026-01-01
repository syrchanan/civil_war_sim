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
export function getClosestMoraleStat(morale: number): number {
  if (typeof morale !== 'number' || !Number.isFinite(morale)) {
    throw new TypeError(`morale must be a number (int or float), got ${typeof morale}`);
  }
  if (morale < 0 || morale > 100) {
    throw new RangeError(`morale must be in the range 0 to 100, got ${morale}`);
  }

  // Options are 10, 20, ..., 100
  const moraleOptions: number[] = Array.from({ length: 10 }, (_, i) => (i + 1) * 10);
  let closestMorale = moraleOptions.reduce((prev, curr) => {
    return Math.abs(curr - morale) < Math.abs(prev - morale) ? curr : prev;
  });
  return Math.floor(closestMorale / 10);
}