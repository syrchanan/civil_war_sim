import { Regiment } from '../units/Regiment';

// Helper function for exponential random
function randomExponential(lambda: number): number {
  // TODO - replace with a library implementation for exponential distribution if needed
  return -Math.log(1 - Math.random()) / lambda;
}


export class Simulation {
  public forces: [Regiment, Regiment]
  public rate_funcs: [((sizes: number[], coef: number[], idx: number) => number), ((sizes: number[], coef: number[], idx: number) => number)] | null = null
  public casualties: {
    initial_size: [number, number]
    losses: [number, number]
    morale: [number, number]
  }
  public sim_output: Array<{ time: number, size_1: number, size_2: number, morale_1: number, morale_2: number }>

  /**
   * Simulation constructor
   * @param forces Tuple of two Regiment instances representing opposing forces
   */
  constructor(forces: [Regiment, Regiment]) {
    if (!Array.isArray(forces) || forces.length !== 2 || !(forces[0] instanceof Regiment && forces[1] instanceof Regiment)) {
      throw new Error('forces must be a tuple of two Regiment instances.')
    }
    this.forces = forces
    const [reg1, reg2] = forces
    this.casualties = {
      initial_size: [reg1.size, reg2.size],
      losses: [0, 0],
      morale: [reg1.rawMorale, reg2.rawMorale],
    }
    this.sim_output = [
      {
        time: 0,
        size_1: reg1.size,
        size_2: reg2.size,
        morale_1: reg1.rawMorale,
        morale_2: reg2.rawMorale,
      },
    ]
    console.info(`Initialized Simulation with forces: ${this.forces}`)
  }

  /**
   * String representation of Simulation
   * @returns string String representation
   */
  toString(): string {
    const losses = this.casualties.losses || 'N/A';
    return `Simulation(forces=[${this.forces.map(f => String(f))}], rate_funcs=${this.rate_funcs ? 'set' : 'unset'}, losses=${Array.isArray(losses) ? JSON.stringify(losses) : losses})`
  }

  /**
   * Convert Simulation to JSON representation
   * @returns Object JSON representation of the Simulation
   */
  toJSON(): object {
    return {
      forces: this.forces.map(f => f.toJSON()),
      casualties: this.casualties,
      sim_output: this.sim_output,
    }
  }

  // Internal method to create Lanchester differential equations
  private static _lanchester_diffeq(regiment: Regiment, opponent: Regiment): (sizes: number[], coef: number[], idx: number) => number {
    // Note: JS lambdas do not capture types, all arrays by reference
    // Directly ports Python's lambdas
    console.debug(`Building Lanchester diffeq for ${regiment} vs ${opponent}`);
    if (regiment.law === 'ln') {
      // TODO - fix equation, should be linear, so -coef * size of battle front (engaged units). Front-size not currently modeled.
      return (sizes: number[], coef: number[], idx: number) => -coef[1 - idx] * sizes[0] * sizes[1 - idx];
    } else if (regiment.law === 'sq') {
      return (sizes: number[], coef: number[], idx: number) => -coef[1 - idx] * sizes[1 - idx];
    } else {
      throw new Error(`Unknown Lanchester law: ${regiment.law}`);
    }
  }

  // Build Lanchester differential equation rate functions
  build_lanch_diffeq(): void {
    console.info('Building Lanchester differential equations for simulation.');
    if (!Array.isArray(this.forces) || this.forces.length !== 2 || !(this.forces[0] instanceof Regiment && this.forces[1] instanceof Regiment)) {
      throw new Error('forces must be a tuple of two Regiment instances.');
    }
    const [reg1, reg2] = this.forces;
    for (const reg of [reg1, reg2]) {
      if (!(reg && 'law' in reg && 'coef' in reg && 'size' in reg)) {
        throw new Error('Each Regiment must have "law", "coef", and "size" attributes.');
      }
    }
    this.rate_funcs = [
      Simulation._lanchester_diffeq(reg1, reg2),
      Simulation._lanchester_diffeq(reg2, reg1),
    ];
  }

  // Private method to update internal casualties value for dynamic morale tracking
  private _update_morale_losses(delta_t: number): void {
    // Morale rules/coefficients
    const MORALE_LOSS_CONSTANT_A = 0.00007;
    const MORALE_GAIN_CONSTANT_B = 0.00005;
    const MORALE_LOSS_CONSTANT_C = 0.0000040;
    const MORALE_GAIN_CONSTANT_D = 0.0000040;
    const morale_changes = [0.0, 0.0];
    for (let side = 0; side < 2; side++) {
      const casualties_taken = this.casualties.losses[side];
      const casualties_inflicted = this.casualties.losses[1 - side];
      // Rule A: Casualties Sustained (Morale Falls)
      const infliction_pct = casualties_taken / Math.max(this.casualties.initial_size[side], 1);
      morale_changes[side] -= infliction_pct * MORALE_LOSS_CONSTANT_A;
      // Rule B: Casualties Inflicted (Morale Rises)
      const infliction_pct_inflicted = casualties_inflicted / Math.max(this.casualties.initial_size[1 - side], 1);
      morale_changes[side] += infliction_pct_inflicted * MORALE_GAIN_CONSTANT_B;
      // Rule C: Faster Casualties Sustained (More Morale Falls)
      const casualties_per_unit_time_taken = casualties_taken / (1 + delta_t);
      morale_changes[side] -= casualties_per_unit_time_taken * MORALE_LOSS_CONSTANT_C;
      // Rule D: Faster Casualties Inflicted (Faster Morale Rises)
      const casualties_per_unit_time_inflicted = casualties_inflicted / (1 + delta_t);
      morale_changes[side] += casualties_per_unit_time_inflicted * MORALE_GAIN_CONSTANT_D;
    }
    for (let side = 0; side < 2; side++) {
      let new_morale = this.casualties.morale[side] + morale_changes[side];
      // Clamp: [10, 100]
      new_morale = Math.max(10, Math.min(100, new_morale));
      this.casualties.morale[side] = new_morale;
      this.forces[side].updateRawMorale(new_morale);
    }
  }

  run_simulation(time: number): void {
    if (this.rate_funcs === null) {
      this.build_lanch_diffeq();
    }
    const [reg1, reg2] = this.forces;
    let t = this.sim_output[0].time;
    while (t < time) {
      const sizes = [reg1.size, reg2.size];
      const coef = [reg1.coef, reg2.coef];
      console.debug(`At time ${t.toFixed(2)}, sizes: ${sizes}, coefs: ${coef}, morale: ${JSON.stringify(this.casualties.morale)}, stats: ${JSON.stringify(reg1.stats)}, ${JSON.stringify(reg2.stats)}`);
      // casualties on each side
      const full_casualties = [this.rate_funcs![0](sizes, coef, 0), this.rate_funcs![1](sizes, coef, 1)];
      const casualty = full_casualties.map(Math.abs);
      const dir = full_casualties.map(d => d >= 0 ? 1 : -1);
      // Random clocks, replace NA with Infinity
      const clocks = casualty.map(r => isFinite(r) && r > 0 ? randomExponential(r) : Infinity);
      t += Math.min(...clocks);
      const minIdx = clocks.indexOf(Math.min(...clocks));
      const tab = [0, 0] as [number, number];
      tab[minIdx] = 1;
      const new_sizes = sizes.map((sz, i) => sz + dir[i] * tab[i]);
      reg1.updateSize(new_sizes[0]);
      reg2.updateSize(new_sizes[1]);
      // update losses if both directions negative
      if (dir[0] <= 0 && dir[1] <= 0) {
        this.casualties.losses = [this.casualties.losses[0] + tab[0], this.casualties.losses[1] + tab[1]];
      }
      this._update_morale_losses(time - t);
      this.sim_output.push({
        time: t,
        size_1: new_sizes[0],
        size_2: new_sizes[1],
        morale_1: this.casualties.morale[0],
        morale_2: this.casualties.morale[1]
      });
      if (new_sizes.includes(0) || this.casualties.morale.some(m => m <= 10)) {
        if (new_sizes.includes(0)) {
          console.info(`Simulation ended at time ${t.toFixed(2)} due to a regiment being wiped out. Final sizes: ${new_sizes}`);
        } else {
          console.info(`Simulation ended at time ${t.toFixed(2)} due to a regiment's morale dropping to minimum. Final morale: ${JSON.stringify(this.casualties.morale)}`);
        }
        break;
      }
    }
  }
}