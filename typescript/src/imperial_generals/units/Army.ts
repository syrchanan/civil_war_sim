import { Regiment } from './Regiment'

/**
 * Represents an army composed of regiments and other subunits.
 * 
 * @param faction - The faction or side the army belongs to.
 * 
 * @property faction - The faction or side the army belongs to.
 * @property forces - Dictionary mapping regiment names to Regiment instances.
 */
export class Army {
  public faction: string
  public forces: { [key: string]: Regiment }

  /**
   * Initialize an army.
   * @param faction - The faction or side the army belongs to.
   */
  constructor(faction: string) {
    this.faction = faction
    this.forces = {}
  }

  /**
   * Returns a human-readable summary of the army.
   */
  toString(): string {
    const forcesSummary = Object.entries(this.forces)
      .map(([name, regiment]) => `${name}: ${regiment.toString()}`)
      .join('\n')
    return `Army of faction: ${this.faction}\nForces:\n${forcesSummary}`
  }

  /**
   * Serializes the army to a JSON-compatible object.
   */
  toJSON(): object {
    const forcesJSON: { [key: string]: string } = {}
    for (const [name, regiment] of Object.entries(this.forces)) {
      forcesJSON[name] = regiment.toJSON()
    }
    return {
      faction: this.faction,
      forces: forcesJSON
    }
  }

  /**
   * Adds a regiment to the army.
   * @param name - The name of the regiment.
   * @param regiment - The Regiment instance to add.
   */
  addRegiment(name: string, regiment: Regiment): void {
    if (regiment instanceof Regiment) {
      this.forces[name] = regiment
    } else {
      throw new TypeError('regiment must be an instance of Regiment')
    }
  }
}