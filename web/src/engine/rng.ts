/**
 * Seeded generator shared with the Python engine (port of python/imperial_generals/utils/rng.py).
 *
 * - Seeding: a 32-bit seed is expanded to four state words with splitmix32.
 * - Core: xoshiro128** (32-bit operations only: Math.imul and >>> 0).
 * - random(): 53-bit float in [0, 1) built from two 32-bit draws.
 * - exponential(rate): inverse CDF, -log(1 - u) / rate, using the fdlibm log port.
 */

import { log } from './fdlibm';

const isU32 = (value: unknown): value is number =>
  Number.isInteger(value) && (value as number) >= 0 && (value as number) <= 0xffffffff;

const rotl = (x: number, k: number): number => ((x << k) | (x >>> (32 - k))) >>> 0;

function splitmix32(seed: number): number[] {
  let a = seed;
  const words = [];
  for (let i = 0; i < 4; i++) {
    a = (a + 0x9e3779b9) >>> 0;
    let t = a ^ (a >>> 16);
    t = Math.imul(t, 0x21f0aaad);
    t ^= t >>> 15;
    t = Math.imul(t, 0x735a2d97);
    t ^= t >>> 15;
    words.push(t >>> 0);
  }
  return words;
}

export class Rng {
  /** Informational; the state words are what matter. Null when restored from a state. */
  seed: number | null;
  private s: number[];

  /** @param seed integer in [0, 2**32) */
  constructor(seed: number) {
    if (typeof seed !== 'number' || !Number.isInteger(seed)) {
      throw new TypeError(`seed must be an integer, got ${String(seed)}.`);
    }
    if (!isU32(seed)) throw new RangeError(`seed must be in [0, 2**32), got ${seed}.`);
    this.s = splitmix32(seed);
    this.seed = seed;
  }

  /** Restore a generator from a saved state: four 32-bit unsigned ints, not all zero. */
  static fromState(state: readonly number[]): Rng {
    if (state.length !== 4 || !state.every(isU32) || state.every((v) => v === 0)) {
      throw new RangeError(`state must be four 32-bit unsigned ints, not all zero, got [${state.join(', ')}].`);
    }
    const rng = Object.create(Rng.prototype) as Rng;
    rng.s = [...state];
    rng.seed = null;
    return rng;
  }

  /** Copy of the four internal state words (for serialization). */
  get state(): number[] {
    return [...this.s];
  }

  /** Next 32-bit unsigned integer. */
  nextU32(): number {
    const s = this.s;
    const result = Math.imul(rotl(Math.imul(s[1], 5) >>> 0, 7), 9) >>> 0;
    const t = (s[1] << 9) >>> 0;
    s[2] = (s[2] ^ s[0]) >>> 0;
    s[3] = (s[3] ^ s[1]) >>> 0;
    s[1] = (s[1] ^ s[2]) >>> 0;
    s[0] = (s[0] ^ s[3]) >>> 0;
    s[2] = (s[2] ^ t) >>> 0;
    s[3] = rotl(s[3], 11);
    return result;
  }

  /** Uniform float in [0, 1) with 53 bits of precision. */
  random(): number {
    const hi = this.nextU32() >>> 5;
    const lo = this.nextU32() >>> 6;
    return (hi * 67108864 + lo) / 9007199254740992;
  }

  /** Exponentially distributed sample with the given rate (mean 1 / rate). */
  exponential(rate: number): number {
    if (!(Number.isFinite(rate) && rate > 0)) throw new RangeError(`rate must be finite and > 0, got ${rate}.`);
    return -log(1.0 - this.random()) / rate;
  }
}
