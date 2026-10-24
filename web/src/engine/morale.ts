/**
 * Per-unit morale model (port of python/imperial_generals/battles/morale.py).
 *
 * A unit's live morale is `initialMorale × resolve`, where `resolve` is the share of its morale budget left
 * (1 = fresh, 0 = broken). The budget is sized so that pure attrition breaks a unit at `breakFraction` of its
 * starting strength, a point set by veterancy and starting morale. Shock, fighting without replying, and time in
 * combat spend it faster; inflicting casualties restores it, capped at the starting value.
 *
 * Powers go through the fdlibm ports, and every formula keeps Python's operation order, so results are
 * bit-identical with the Python engine.
 */

import defaults from './defaults.json';
import { ValueError } from './errors';
import { exp, log } from './fdlibm';
import { BattleParams, type MoraleParams } from './params';

const LN2 = 0.6931471805599453;
// Floating-point slack when deciding a unit has spent its budget
const BREAK_EPSILON = 1e-9;
const RAW_SCALE: number = defaults.morale_scale.raw_scale_factor;

const clamp = (lo: number, hi: number, x: number): number => Math.max(lo, Math.min(hi, x));

/** base ** exponent for base > 0, via fdlibm so every platform agrees. */
const power = (base: number, exponent: number): number => exp(exponent * log(base));

/**
 * Fraction of starting strength at which pure attrition breaks a unit: experience and starting morale (both 1-10,
 * clamped) blend into w in [0, 1], and w ** break_curve maps onto [break_fraction_min, break_fraction_max].
 */
export function breakFraction(xp: number, moraleStat: number, params: MoraleParams): number {
  const xpNorm = (clamp(1, 10, xp) - 1) / 9;
  const moraleNorm = (clamp(1, 10, moraleStat) - 1) / 9;
  const w = params.experience_weight * xpNorm + (1 - params.experience_weight) * moraleNorm;
  const curved = w > 0 ? power(w, params.break_curve) : 0.0;
  return params.break_fraction_min + (params.break_fraction_max - params.break_fraction_min) * curved;
}

/** A unit's break-point multiplier from a uniform draw `u`: (u / (1 - u)) ** spread, median 1. */
export function breakScale(u: number, spread: number): number {
  if (spread === 0) return 1.0;
  const v = Math.min(Math.max(u, 1e-12), 1 - 1e-12);
  return power(v / (1 - v), spread);
}

/** Live morale of one unit for one engagement. */
export class MoraleState {
  readonly params: MoraleParams;
  readonly initialSize: number;
  readonly initialMorale: number;
  readonly breakScale: number;
  readonly breakFraction: number;
  resolve = 1.0;
  shock = 0.0;
  lost = 0;
  broken = false;
  private readonly costScale: number;

  /**
   * @param size starting strength
   * @param xp experience stat (1-10)
   * @param moraleStat starting morale stat (1-10); starting raw morale is moraleStat × raw_scale_factor
   * @param params model constants (defaults to config)
   * @param scale multiplier on this unit's break point (drawn per unit at battle start; see breakScale)
   */
  /** An admin's morale modifier for the current round scales everything spent (1 - modifier); 1 otherwise. */
  spendFactor = 1.0;

  constructor(size: number, xp: number, moraleStat: number, params?: MoraleParams, scale = 1.0) {
    if (size <= 0) throw new ValueError(`size must be positive, got ${size}.`);
    this.params = params ?? BattleParams.defaults().morale;
    this.initialSize = size;
    this.initialMorale = moraleStat * RAW_SCALE;
    this.breakScale = scale;
    this.breakFraction = Math.min(this.params.break_fraction_ceiling,
      breakFraction(xp, moraleStat, this.params) * scale);
    const p = this.params;
    const fb = this.breakFraction;
    // Pure attrition with acceleration k spends a*(f + k*f^2/2) by fraction f lost; the budget is 1 at f_break.
    this.costScale = power(size / p.size_reference, p.size_exponent)
      / (size * (fb + p.acceleration * fb * fb / 2));
  }

  /** Live raw morale (0 when broken, at most initialMorale). */
  get morale(): number {
    return this.initialMorale * this.resolve;
  }

  /** Let game time pass: shock fades, and morale drains if the unit is engaged. */
  advance(minutes: number, engaged: boolean): void {
    if (minutes < 0) throw new ValueError(`minutes must be >= 0, got ${minutes}.`);
    if (this.shock) this.shock *= exp(-minutes * LN2 / this.params.shock_half_life); // nothing to fade otherwise
    if (engaged && !this.broken) this.spend(this.params.drain_per_hour * minutes / 60);
  }

  /** Record one casualty; `firingBack` is false when the unit can't or doesn't reply. */
  takeLoss(firingBack: boolean): void {
    const p = this.params;
    const fractionMid = (this.lost + 0.5) / this.initialSize;
    const cost = this.costScale
      * (1 + p.acceleration * fractionMid)
      * (1 + p.shock_weight * this.shock)
      * (1 + (firingBack ? 0.0 : p.helpless_weight));
    this.lost += 1;
    this.shock += 1 / this.initialSize;
    if (!this.broken) this.spend(cost);
  }

  /** Record one casualty inflicted on an enemy unit of the given starting size. */
  inflictLoss(enemyInitialSize: number): void {
    if (!this.broken) this.resolve = Math.min(1.0, this.resolve + this.params.gain_weight / enemyInitialSize);
  }

  /** Spend `cost` of the morale budget at once (e.g. a charge that falters). */
  shake(cost: number): void {
    if (!this.broken) this.spend(cost);
  }

  /** Break at once (e.g. routed by a charge before contact). */
  forceBreak(): void {
    this.resolve = 0.0;
    this.broken = true;
  }

  private spend(amount: number): void {
    this.resolve -= amount * this.spendFactor;
    if (this.resolve <= BREAK_EPSILON) {
      this.resolve = 0.0;
      this.broken = true;
    }
  }
}
