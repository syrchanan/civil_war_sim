/**
 * Per-battle tunable parameters (port of python/imperial_generals/params.py).
 *
 * Field names are snake_case on purpose: they are the battle state file's format, so `toDict` / `fromDict` need
 * no mapping. Defaults come from defaults.json, generated from config/*.yaml by the Python side.
 */

import defaults from './defaults.json';
import { ValueError } from './errors';

export const WEAPON_CODES = ['-2', '-1', '0', '1', '2'] as const;

const RAW_SCALE: number = defaults.morale_scale.raw_scale_factor;

const clamp = (lo: number, hi: number, x: number): number => Math.max(lo, Math.min(hi, x));

/** Python's round(x): to the nearest integer, exact halves to the even one. */
export function roundHalfEven(x: number): number {
  const r = Math.round(x);
  return Math.abs(x % 1) === 0.5 ? 2 * Math.round(x / 2) : r;
}

const sameKeys = (obj: object, keys: readonly string[]): boolean => {
  const own = Object.keys(obj);
  return own.length === keys.length && keys.every((k) => own.includes(k));
};

// =============================================================================
// Combat
// =============================================================================

export interface CombatData {
  weapon_multipliers: Record<string, number>;
  xp_boost_per_level: number;
  morale_boost_per_level: number;
  melee_penalty_factor: number;
  ranged_kill_rate: number;
  melee_kill_rate: number;
  broken_fire_multiplier: number;
  broken_melee_multiplier: number;
  artillery_ammo: Record<string, number>;
  artillery_default_ammo: string;
}

export type Stats = readonly [number, number, number, number];

/** Combat effectiveness and kill-rate constants. */
export class CombatParams implements CombatData {
  readonly weapon_multipliers: Record<string, number>;
  readonly xp_boost_per_level: number;
  readonly morale_boost_per_level: number;
  readonly melee_penalty_factor: number;
  readonly ranged_kill_rate: number;
  readonly melee_kill_rate: number;
  readonly broken_fire_multiplier: number;
  readonly broken_melee_multiplier: number;
  readonly artillery_ammo: Record<string, number>;
  readonly artillery_default_ammo: string;
  private readonly maxRaw: number;

  constructor(data: CombatData) {
    const multipliers = { ...data.weapon_multipliers };
    if (!sameKeys(multipliers, WEAPON_CODES)) {
      throw new ValueError(`weapon_multipliers must have exactly the codes ${WEAPON_CODES.join(', ')}, `
        + `got ${Object.keys(multipliers).join(', ')}.`);
    }
    if (Object.values(multipliers).some((v) => !(v > 0))) throw new ValueError('weapon multipliers must be > 0.');
    for (const name of ['xp_boost_per_level', 'morale_boost_per_level', 'broken_fire_multiplier',
      'broken_melee_multiplier'] as const) {
      if (data[name] < 0) throw new ValueError(`${name} must be >= 0.`);
    }
    for (const name of ['melee_penalty_factor', 'ranged_kill_rate', 'melee_kill_rate'] as const) {
      if (!(data[name] > 0)) throw new ValueError(`${name} must be > 0.`);
    }
    const ammo = { ...data.artillery_ammo };
    if (Object.keys(ammo).length === 0 || Object.values(ammo).some((v) => !(v > 0))) {
      throw new ValueError('artillery_ammo needs at least one ammo type, each with a per-gun rate > 0.');
    }
    if (!(data.artillery_default_ammo in ammo)) {
      throw new ValueError(`artillery_default_ammo ${data.artillery_default_ammo} is not in artillery_ammo.`);
    }

    this.weapon_multipliers = Object.freeze(multipliers);
    this.xp_boost_per_level = data.xp_boost_per_level;
    this.morale_boost_per_level = data.morale_boost_per_level;
    this.melee_penalty_factor = data.melee_penalty_factor;
    this.ranged_kill_rate = data.ranged_kill_rate;
    this.melee_kill_rate = data.melee_kill_rate;
    this.broken_fire_multiplier = data.broken_fire_multiplier;
    this.broken_melee_multiplier = data.broken_melee_multiplier;
    this.artillery_ammo = Object.freeze(ammo);
    this.artillery_default_ammo = data.artillery_default_ammo;
    // Normaliser: the best possible unit (top weapon, xp 10, morale 10) has efficiency 1.
    this.maxRaw = Math.max(...Object.values(multipliers))
      * (1 + 9 * this.xp_boost_per_level + 9 * this.morale_boost_per_level);
    Object.freeze(this);
  }

  /**
   * Combat efficiency coefficient in [0, 1]. `morale` may be a 1-10 stat or a raw 10-100 value (converted when
   * above the raw scale factor). Inputs are clamped: xp and morale to 1-10, weapon to -2..2, melee to 0/1.
   */
  efficiency(xp: number, morale: number, weapon: number, melee = 0): number {
    const w = clamp(-2, 2, weapon);
    let raw = this.weapon_multipliers[String(w)] * this.effAdj(xp, morale);
    if (clamp(0, 1, melee) === 1) raw *= this.melee_penalty_factor;
    return raw / this.maxRaw;
  }

  /** Experience and morale boost: 1 at xp 1 / morale 1. Morale may be a 1-10 stat or raw 10-100. */
  private effAdj(xp: number, morale: number): number {
    const stat = clamp(1, 10, morale > RAW_SCALE ? roundHalfEven(morale / RAW_SCALE) : morale);
    return 1 + (clamp(1, 10, xp) - 1) * this.xp_boost_per_level + (stat - 1) * this.morale_boost_per_level;
  }

  /** Melee coefficient: the unit's melee rating boosted by experience and morale (firearm plays no part). */
  meleeEfficiency(xp: number, morale: number, rating: number): number {
    return rating * this.effAdj(xp, morale) / this.maxRaw;
  }

  /**
   * A unit's coefficient in its combat mode: a melee-only unit (stats[3] == 1) can't fire (0); a ranged unit in
   * melee fights at efficiency × melee_penalty_factor; otherwise the base efficiency.
   */
  unitCoef(stats: Stats, mode: string): number {
    const meleeOnly = stats[3] === 1;
    if (meleeOnly && mode === 'ranged') return 0;
    const value = this.efficiency(stats[0], stats[1], stats[2], 0);
    return !meleeOnly && mode === 'melee' ? value * this.melee_penalty_factor : value;
  }

  toDict(): CombatData {
    return {
      weapon_multipliers: { ...this.weapon_multipliers },
      xp_boost_per_level: this.xp_boost_per_level,
      morale_boost_per_level: this.morale_boost_per_level,
      melee_penalty_factor: this.melee_penalty_factor,
      ranged_kill_rate: this.ranged_kill_rate,
      melee_kill_rate: this.melee_kill_rate,
      broken_fire_multiplier: this.broken_fire_multiplier,
      broken_melee_multiplier: this.broken_melee_multiplier,
      artillery_ammo: { ...this.artillery_ammo },
      artillery_default_ammo: this.artillery_default_ammo,
    };
  }
}

// =============================================================================
// Morale
// =============================================================================

export interface MoraleData {
  break_fraction_min: number;
  break_fraction_max: number;
  experience_weight: number;
  break_curve: number;
  break_point_spread: number;
  break_fraction_ceiling: number;
  size_reference: number;
  size_exponent: number;
  acceleration: number;
  shock_weight: number;
  shock_half_life: number;
  helpless_weight: number;
  drain_per_hour: number;
  gain_weight: number;
}

export interface MoraleParams extends Readonly<MoraleData> {}

/** Tunable morale constants (the model is in morale.ts). */
export class MoraleParams {
  constructor(data: MoraleData) {
    if (!(0 < data.break_fraction_min && data.break_fraction_min <= data.break_fraction_max
      && data.break_fraction_max <= 1)) {
      throw new ValueError('Need 0 < break_fraction_min <= break_fraction_max <= 1.');
    }
    if (!(0 <= data.experience_weight && data.experience_weight <= 1)) {
      throw new ValueError('experience_weight must be in [0, 1].');
    }
    if (!(data.break_point_spread >= 0)) throw new ValueError('break_point_spread must be >= 0.');
    if (!(0 < data.break_fraction_ceiling && data.break_fraction_ceiling <= 1)) {
      throw new ValueError('break_fraction_ceiling must be in (0, 1].');
    }
    for (const name of ['break_curve', 'size_reference', 'shock_half_life'] as const) {
      if (!(data[name] > 0)) throw new ValueError(`${name} must be > 0.`);
    }
    for (const name of ['acceleration', 'shock_weight', 'helpless_weight', 'drain_per_hour', 'gain_weight'] as const) {
      if (data[name] < 0) throw new ValueError(`${name} must be >= 0.`);
    }
    Object.assign(this, data);
    Object.freeze(this);
  }

  toDict(): MoraleData {
    return { ...this };
  }
}

// =============================================================================
// Aftermath
// =============================================================================

export interface AftermathData {
  rout_capture_share: number;
  cavalry_capture_multiplier: number;
  killed_share: number;
  walking_wounded_share: number;
  wounded_captured_share: number;
  wounded_return_share: number;
  share_spread: number;
  field_exchange_ratio: number;
  field_rout_gap: number;
  field_standing_ratio: number;
  field_votes_needed: number;
}

export interface AftermathParams extends Readonly<AftermathData> {}

/** Rout captures, end-of-battle casualty accounting, and the field-holder votes. */
export class AftermathParams {
  constructor(data: AftermathData) {
    for (const name of ['rout_capture_share', 'killed_share', 'walking_wounded_share', 'wounded_captured_share',
      'wounded_return_share', 'share_spread'] as const) {
      if (!(0 <= data[name] && data[name] <= 1)) throw new ValueError(`${name} must be in [0, 1].`);
    }
    if (data.cavalry_capture_multiplier < 0) throw new ValueError('cavalry_capture_multiplier must be >= 0.');
    for (const name of ['field_exchange_ratio', 'field_standing_ratio'] as const) {
      if (data[name] < 1) throw new ValueError(`${name} must be >= 1.`);
    }
    if (!(0 <= data.field_rout_gap && data.field_rout_gap <= 1)) {
      throw new ValueError('field_rout_gap must be in [0, 1].');
    }
    if (!Number.isInteger(data.field_votes_needed) || data.field_votes_needed < 1 || data.field_votes_needed > 3) {
      throw new ValueError('field_votes_needed must be a whole number from 1 to 3.');
    }
    Object.assign(this, data);
    Object.freeze(this);
  }

  toDict(): AftermathData {
    return { ...this };
  }
}
