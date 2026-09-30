import { getClosestMoraleStat, getCombatEfficiency } from '../utils/index.js'

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
  public size: number
  public stats: [number, number, number, number]
  public rawMorale: number
  public coef: number
  public law: 'ln' | 'sq'

  /**
  * Initialize a regiment.
  * @param size - Number of soldiers.
  * @param stats - Slash-separated string of four integers (e.g., '4/4/0/0').
  * @param law - Combat law: 'ln' (Linear) or 'sq' (Square).
  * @throws {Error} If `law` is not 'ln' or 'sq', or if stats is not four integers.
  */
  constructor(
    size: number,
    stats: string,
    law: 'ln' | 'sq'
  ) {
    // checks
    if (!['ln', 'sq'].includes(law)) {
      throw new TypeError("Law must be either 'ln' (Linear) or 'sq' (Square).")
    }
    const statsSplit = stats.split('/')
    if (statsSplit.length !== 4 || !statsSplit.every(s => /^\d+$/.test(s))) {
      throw new Error("Stats must be a slash-separated string of four integers (e.g., '4/4/0/0').")
    }
    // inits
    this.size = size
    this.stats = statsSplit.map(Number) as [number, number, number, number]
    this.coef = getCombatEfficiency(...this.stats)
    this.rawMorale = this.stats[1] * 10 // second num of stats
    this.law = law
  }

  /**
   * Returns a human-readable summary of the regiment.
   */
  toString(): string {
    return (
      `Regiment: ${this.size} men | ` +
      `Stats: xp=${this.stats[0]}, morale=${this.stats[1]}, weapon=${this.stats[2]}, melee=${this.stats[3]} | ` +
      `Raw Morale=${this.rawMorale} | ` +
      `Coef=${this.coef.toFixed(4)} | Law=${this.law}`
    );
  }

  /**
   * Returns a code-friendly string representation of the regiment.
   */
  toJSON(): string {
    return `Regiment(size=${this.size}, stats=[${this.stats.join(', ')}], law='${this.law}')`;
  }

  /**
   * Update the regiment's size.
   * @param newSize - The new size of the regiment.
   */
  updateSize(newSize: number): void {
    this.size = newSize
  }

  /**
   * Update the regiment's stats and recalculate combat efficiency coefficient.
   * @param newStats - Slash-separated string of four integers (e.g., '5/6/1/0').
   * @throws {Error} If newStats is not four integers.
   */
  updateStats(newStats: string): void {
    const statsSplit = newStats.split('/');
    if (statsSplit.length !== 4 || !statsSplit.every(s => /^\d+$/.test(s))) {
      throw new Error("New stats must be a slash-separated string of four integers (e.g., '5/6/1/0').");
    }
    this.stats = statsSplit.map(Number) as [number, number, number, number];
    this.coef = getCombatEfficiency(...this.stats);
  }

  /**
   * Update the regiment's raw morale and update stats accordingly.
   * @param newMorale - The new raw morale value.
   * @throws {TypeError} If newMorale is not a number.
   */
  updateRawMorale(newMorale: number): void {
    if (typeof newMorale !== 'number') {
      throw new TypeError('newMorale must be a number.');
    }
    this.rawMorale = newMorale;
    const newStat = getClosestMoraleStat(newMorale);
    this.updateStats(`${this.stats[0]}/${newStat}/${this.stats[2]}/${this.stats[3]}`);
  }

}