/**
 * Units on the field (port of python/imperial_generals/units).
 *
 * Only what the round engine and the state file use: Python's legacy 1-v-1 coefficient helpers and the distance
 * methods are not ported. A position is carried as plain data so state files round-trip; the map draws it, but no
 * combat rule uses it yet.
 */

import defaults from './defaults.json';
import { ValueError } from './errors';
import type { Stats } from './params';

const MORALE = defaults.morale_scale;
const UNIT_SUBTYPES: Record<string, readonly string[]> = defaults.unit_subtypes;
const COMBAT_MODES = ['idle', 'ranged', 'melee'] as const;

// experience/morale/weapon/melee; only weapon may be negative (-2 unarmed/pikes, -1 matchlock)
const STATS_PATTERN = /^(\d+)\/(\d+)\/(-?\d+)\/(\d+)$/;

/** '4/5/0/0' -> [4, 5, 0, 0]. */
export function parseStats(text: string): Stats {
  const match = STATS_PATTERN.exec(text);
  if (match === null) {
    throw new ValueError("Stats must be a slash-separated string of four integers (e.g., '4/4/0/0'); "
      + 'only the weapon code may be negative.');
  }
  return [Number(match[1]), Number(match[2]), Number(match[3]), Number(match[4])];
}

/**
 * The 1-10 morale stat closest to a raw morale value: rounds to the nearest level (min_raw, min_raw + scale, ...,
 * max_raw), exact ties to the lower level.
 */
export function closestMoraleStat(raw: number): number {
  const { min_raw: minRaw, max_raw: maxRaw, raw_scale_factor: scale } = MORALE;
  if (Number.isNaN(raw) || raw < 0 || raw > maxRaw) throw new ValueError(`morale must be in the range 0 to ${maxRaw}, got ${raw}`);
  const lastIndex = Math.floor((maxRaw - minRaw) / scale);
  // ceil(x - 0.5) sends exact halves down
  const index = Math.max(0, Math.min(lastIndex, Math.ceil((raw - minRaw) / scale - 0.5)));
  return Math.floor((minRaw + index * scale) / scale);
}

/** Battlefield position, kept as data (drawn on the map; no combat rule uses it yet). */
export interface Position {
  x: number;
  y: number;
  z: number;
  cover: number;
  terrain_type: string;
  /** Compass degrees clockwise from map north (towards y = 0), in [0, 360); null when not given. Display only. */
  facing?: number | null;
}

export interface RegimentOptions {
  frontSize?: number;
  position?: Position | null;
}

function checkFront(front: number): number {
  if (!Number.isInteger(front)) throw new TypeError(`front_size must be an int, got ${front}.`);
  if (front < 0) throw new ValueError(`front_size must be non-negative, got ${front}.`);
  return front;
}

function checkSubtype(type: string, subtype: string, label: string): void {
  if (!UNIT_SUBTYPES[type].includes(subtype)) {
    throw new ValueError(`subtype '${subtype}' is not valid for ${label}. `
      + `Must be one of: ${[...UNIT_SUBTYPES[type]].sort().join(', ')}.`);
  }
}

/** A regiment: men, stats (experience/morale/weapon/melee), the men forming its front, its live raw morale. */
export class Regiment {
  /** null for a plain regiment (fights as default infantry). */
  readonly unitType: string | null = null;
  readonly subtype: string | null = null;
  size: number;
  stats: Stats;
  frontSize: number;
  rawMorale: number;
  combatMode: string = 'idle';
  position: Position | null;

  constructor(size: number, stats: string, options: RegimentOptions = {}) {
    this.stats = parseStats(stats);
    this.frontSize = checkFront(options.frontSize ?? size);
    this.size = size;
    this.rawMorale = this.stats[1] * MORALE.raw_scale_factor;
    this.position = options.position ?? null;
  }

  /** True if this unit can only fight in melee (stats[3] == 1). */
  get isMeleeOnly(): boolean {
    return this.stats[3] === 1;
  }

  updateSize(size: number): void {
    this.size = size;
  }

  updateStats(stats: string): void {
    this.stats = parseStats(stats);
  }

  /** Live raw morale; the morale stat follows it to the closest level. */
  updateRawMorale(raw: number): void {
    this.rawMorale = raw;
    const stat = closestMoraleStat(raw);
    if (stat !== this.stats[1]) this.stats = [this.stats[0], stat, this.stats[2], this.stats[3]];
  }

  setFrontSize(front: number): void {
    this.frontSize = checkFront(front);
  }

  setCombatMode(mode: string): void {
    if (!(COMBAT_MODES as readonly string[]).includes(mode)) {
      throw new ValueError(`combat_mode '${mode}' is not valid. Must be one of: ${[...COMBAT_MODES].sort().join(', ')}.`);
    }
    this.combatMode = mode;
  }
}

export class InfantryRegiment extends Regiment {
  override readonly unitType = 'inf';
  override readonly subtype: string;

  constructor(size: number, stats: string, subtype: string, options: RegimentOptions = {}) {
    checkSubtype('inf', subtype, 'infantry');
    super(size, stats, options);
    this.subtype = subtype;
  }
}

export class CavalryRegiment extends Regiment {
  override readonly unitType = 'cav';
  override readonly subtype: string;

  constructor(size: number, stats: string, subtype: string, options: RegimentOptions = {}) {
    checkSubtype('cav', subtype, 'cavalry');
    super(size, stats, options);
    this.subtype = subtype;
  }
}

function checkGuns(guns: number): number {
  if (!Number.isInteger(guns)) throw new TypeError(`guns must be an int, got ${guns}.`);
  if (guns < 0) throw new ValueError(`guns must be >= 0, got ${guns}.`);
  return guns;
}

/**
 * An artillery battery: size is its crew, guns are tracked separately. Firepower is limited by whichever runs
 * out first, guns or the crew to man them.
 */
export class ArtilleryBattery extends Regiment {
  static readonly MIN_CREW_PER_GUN: number = defaults.artillery.min_crew_per_gun;
  override readonly unitType = 'art';
  override readonly subtype: string;
  guns: number;

  constructor(size: number, stats: string, guns: number, subtype: string, options: RegimentOptions = {}) {
    checkGuns(guns);
    checkSubtype('art', subtype, 'artillery');
    super(size, stats, options);
    this.guns = guns;
    this.subtype = subtype;
  }

  /** A battery from the standard template in config/artillery.yaml (8 guns × 9 crew). */
  static standard(stats: string, subtype: string, options: RegimentOptions = {}): ArtilleryBattery {
    const { guns, crew_per_gun: crew } = defaults.artillery;
    return new ArtilleryBattery(guns * crew, stats, guns, subtype, options);
  }

  /** Guns that can actually be manned with the current crew. */
  get effectiveGuns(): number {
    return Math.min(this.guns, Math.floor(this.size / ArtilleryBattery.MIN_CREW_PER_GUN));
  }

  updateGuns(guns: number): void {
    this.guns = checkGuns(guns);
  }
}
