/**
 * Per-battle tunable parameters (port of python/imperial_generals/params.py).
 *
 * Field names are snake_case on purpose: they are the battle state file's format, so `toDict` / `fromDict` need
 * no mapping. Defaults come from defaults.json, generated from config/*.yaml by the Python side.
 */

import defaults from './defaults.json';
import { ValueError } from './errors';
import { exp, log } from './fdlibm';

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

// =============================================================================
// Matchups
// =============================================================================

export const UNIT_TYPES = ['inf', 'cav', 'art'] as const;
const MATCHUP_MODES = ['ranged', 'melee'] as const;
const UNIT_SUBTYPES: Record<string, readonly string[]> = defaults.unit_subtypes;

/** (unit type, subtype | null), e.g. ['cav', 'heavy']; a plain regiment is ['inf', null]. */
export type Unit = readonly [string, string | null];

type Table = Record<string, Record<string, number>>;

export interface MatchupOverride {
  attacker: string;
  target: string;
  mode: string;
  multiplier: number;
}

export interface MatchupData {
  ranged: Table;
  melee: Table;
  overrides: MatchupOverride[];
  melee_ratings: Record<string, number>;
}

/** 'type' or 'type/subtype' (or '*' when allowed), with the subtype known for that type. */
function validUnitKey(key: string, allowAny = false): boolean {
  if (allowAny && key === '*') return true;
  const slash = key.indexOf('/');
  const type = slash < 0 ? key : key.slice(0, slash);
  const sub = slash < 0 ? '' : key.slice(slash + 1);
  if (!(UNIT_TYPES as readonly string[]).includes(type)) return false;
  return !sub || UNIT_SUBTYPES[type].includes(sub);
}

const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

/**
 * Unit-type advantage and melee strength. `ranged` / `melee`: attacker type -> target type -> multiplier on the
 * attacker's casualty rate. `overrides`: subtype-specific replacements (most specific wins, see `multiplier`).
 * `melee_ratings`: melee strength per 'type/subtype' (plus 'default'), on the weapon-multiplier scale.
 */
export class MatchupParams implements MatchupData {
  readonly ranged: Table;
  readonly melee: Table;
  readonly overrides: MatchupOverride[];
  readonly melee_ratings: Record<string, number>;
  private readonly lookup: Map<string, number>;

  constructor(data: MatchupData) {
    for (const mode of MATCHUP_MODES) {
      const table = data[mode];
      for (const a of UNIT_TYPES) {
        const row = isObject(table) ? table[a] : undefined;
        if (!isObject(row) || !sameKeys(row, UNIT_TYPES)) {
          throw new ValueError(`${mode} table needs a full ${UNIT_TYPES.join('/')} grid (row ${a}).`);
        }
        if (Object.values(row).some((v) => !((v as number) >= 0))) {
          throw new ValueError(`${mode} multipliers must be >= 0 (row ${a}).`);
        }
      }
    }

    const lookup = new Map<string, number>();
    for (const o of data.overrides) {
      if (!isObject(o) || !sameKeys(o, ['attacker', 'target', 'mode', 'multiplier'])) {
        throw new ValueError(`An override needs exactly attacker, target, mode, multiplier: ${JSON.stringify(o)}.`);
      }
      if (!(MATCHUP_MODES as readonly string[]).includes(o.mode)) {
        throw new ValueError(`Override mode must be ranged or melee: ${JSON.stringify(o)}.`);
      }
      if (!validUnitKey(o.attacker) || !validUnitKey(o.target, true)) {
        throw new ValueError(`Unknown unit type/subtype in override: ${JSON.stringify(o)}.`);
      }
      if (o.target === '*' && !o.attacker.includes('/')) {
        throw new ValueError(`target '*' needs an attacker subtype (use the type table otherwise): ${JSON.stringify(o)}.`);
      }
      if (!(o.multiplier >= 0)) throw new ValueError(`Override multiplier must be >= 0: ${JSON.stringify(o)}.`);
      lookup.set(`${o.attacker}|${o.target}|${o.mode}`, o.multiplier);
    }

    if (!('default' in data.melee_ratings)) throw new ValueError("melee_ratings needs a 'default' entry.");
    for (const [key, value] of Object.entries(data.melee_ratings)) {
      if (key !== 'default' && (!key.includes('/') || !validUnitKey(key))) {
        throw new ValueError(`Unknown melee rating key ${key} (use 'type/subtype').`);
      }
      if (!(value >= 0)) throw new ValueError(`Melee rating must be >= 0: ${key}.`);
    }

    this.ranged = structuredClone(data.ranged);
    this.melee = structuredClone(data.melee);
    this.overrides = structuredClone(data.overrides);
    this.melee_ratings = { ...data.melee_ratings };
    this.lookup = lookup;
    Object.freeze(this);
  }

  /**
   * Multiplier for `attacker` against `target` in `mode`. Most specific first: attacker subtype + target subtype,
   * attacker subtype + target type, attacker subtype + any target, attacker type + target subtype, then the type
   * table.
   */
  multiplier(attacker: Unit, target: Unit, mode: string): number {
    const [aType, aSub] = attacker;
    const [tType, tSub] = target;
    const aFull = aSub ? `${aType}/${aSub}` : null;
    const tFull = tSub ? `${tType}/${tSub}` : null;
    const candidates: [string, string | null][] = [];
    if (aFull) candidates.push([aFull, tFull], [aFull, tType], [aFull, '*']);
    candidates.push([aType, tFull]);
    for (const [a, t] of candidates) {
      const value = t === null ? undefined : this.lookup.get(`${a}|${t}|${mode}`);
      if (value !== undefined) return value;
    }
    return (mode === 'melee' ? this.melee : this.ranged)[aType][tType];
  }

  /** Melee rating for a unit; units without a listed subtype use 'default'. */
  meleeRating(unit: Unit): number {
    return this.melee_ratings[`${unit[0]}/${unit[1]}`] ?? this.melee_ratings.default;
  }

  toDict(): MatchupData {
    return {
      ranged: structuredClone(this.ranged),
      melee: structuredClone(this.melee),
      overrides: structuredClone(this.overrides),
      melee_ratings: { ...this.melee_ratings },
    };
  }
}

// =============================================================================
// Charges
// =============================================================================

export interface ShockBonus {
  charger: string;
  target: string;
  bonus: number;
}

export interface ChargeData {
  approach_minutes: Record<string, number>;
  closing_fire_multiplier: number;
  battery_closing_ammo: string;
  numbers_weight: number;
  steadiness_weight: number;
  veterancy_weight: number;
  shock_weight: number;
  break_threshold: number;
  falter_threshold: number;
  spread: number;
  falter_cost: number;
  shock_bonus: ShockBonus[];
}

const sigmoid = (z: number): number => 1.0 / (1.0 + exp(-z));

/** Charges: the approach under close-range fire and the contact test (formulas in config/charge.yaml). */
export class ChargeParams implements ChargeData {
  readonly approach_minutes: Record<string, number>;
  readonly closing_fire_multiplier: number;
  readonly battery_closing_ammo: string;
  readonly numbers_weight: number;
  readonly steadiness_weight: number;
  readonly veterancy_weight: number;
  readonly shock_weight: number;
  readonly break_threshold: number;
  readonly falter_threshold: number;
  readonly spread: number;
  readonly falter_cost: number;
  readonly shock_bonus: ShockBonus[];

  constructor(data: ChargeData) {
    if (!isObject(data.approach_minutes) || !sameKeys(data.approach_minutes, UNIT_TYPES)) {
      throw new ValueError(`approach_minutes needs exactly ${UNIT_TYPES.join(', ')}.`);
    }
    if (Object.values(data.approach_minutes).some((v) => !(v > 0))) {
      throw new ValueError('approach_minutes must be > 0.');
    }
    for (const name of ['closing_fire_multiplier', 'numbers_weight', 'steadiness_weight', 'shock_weight',
      'break_threshold', 'falter_threshold'] as const) {
      if (!(data[name] >= 0)) throw new ValueError(`${name} must be >= 0.`);
    }
    if (!(data.spread > 0)) throw new ValueError('spread must be > 0.');
    for (const name of ['veterancy_weight', 'falter_cost'] as const) {
      if (!(0 <= data[name] && data[name] <= 1)) throw new ValueError(`${name} must be in [0, 1].`);
    }
    for (const b of data.shock_bonus) {
      if (!isObject(b) || !sameKeys(b, ['charger', 'target', 'bonus'])) {
        throw new ValueError(`A shock bonus needs exactly charger, target, bonus: ${JSON.stringify(b)}.`);
      }
      if (!validUnitKey(b.charger) || !validUnitKey(b.target)) {
        throw new ValueError(`Unknown unit type/subtype in shock bonus: ${JSON.stringify(b)}.`);
      }
    }
    this.approach_minutes = { ...data.approach_minutes };
    this.closing_fire_multiplier = data.closing_fire_multiplier;
    this.battery_closing_ammo = data.battery_closing_ammo;
    this.numbers_weight = data.numbers_weight;
    this.steadiness_weight = data.steadiness_weight;
    this.veterancy_weight = data.veterancy_weight;
    this.shock_weight = data.shock_weight;
    this.break_threshold = data.break_threshold;
    this.falter_threshold = data.falter_threshold;
    this.spread = data.spread;
    this.falter_cost = data.falter_cost;
    this.shock_bonus = structuredClone(data.shock_bonus);
    Object.freeze(this);
  }

  /** How well a unit holds together: resolve, steadied by veterancy, shaken by recent losses. */
  steadiness(resolve: number, xp: number, shock: number): number {
    const xpNorm = (clamp(1, 10, xp) - 1) / 9;
    const w = this.veterancy_weight;
    return resolve * (1 - w + w * xpNorm) / (1 + this.shock_weight * shock);
  }

  /** Sum of the shock bonuses matching the charger's and the target's type and subtype. */
  bonus(charger: Unit, target: Unit): number {
    const keys = ([kind, sub]: Unit) => (sub ? [kind, `${kind}/${sub}`] : [kind]);
    const c = keys(charger);
    const t = keys(target);
    let sum = 0;
    for (const b of this.shock_bonus) if (c.includes(b.charger) && t.includes(b.target)) sum += b.bonus;
    return sum;
  }

  pressure(chargerMen: number, targetMen: number, chargerSteadiness: number, targetSteadiness: number,
    bonus: number): number {
    return this.numbers_weight * log(chargerMen / targetMen)
      + this.steadiness_weight * (chargerSteadiness - targetSteadiness) + bonus;
  }

  /** [defender breaks, charge falters, goes home] for pressure `x`. */
  odds(x: number): [number, number, number] {
    const pBreak = sigmoid((x - this.break_threshold) / this.spread);
    const pFalter = sigmoid((-x - this.falter_threshold) / this.spread);
    return [pBreak, pFalter, Math.max(0.0, 1.0 - pBreak - pFalter)];
  }

  toDict(): ChargeData {
    return { ...this, approach_minutes: { ...this.approach_minutes }, shock_bonus: structuredClone(this.shock_bonus) };
  }
}
