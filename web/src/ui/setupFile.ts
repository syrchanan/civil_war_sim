/**
 * The setup file: a battle being set up, saved before round 0 opens (the admins may wait days for the armies). It
 * holds the day's plan, the ground, the zones and both armies as drafts. Web only: the Python engine never reads
 * it; from round 0 on, the battle state file takes over.
 */

import { validateOrg } from '../engine';
import type { UnitDraft, UnitType } from './store';

export const SETUP_FORMAT = 'imperial-generals-setup';
export const SETUP_VERSION = 1;

export interface Setup {
  name: string;
  sides: [string, string];
  seed: number;
  ground: string; // 'none' (an open field) or a terrain preset
  round_length: number; // minutes
  rounds_planned: number | null;
  start_clock: string | null;
  zone_depth: [number, number]; // yards from each side's own edge
  units: UnitDraft[];
}

const TYPES: (UnitType | null)[] = ['inf', 'cav', 'art', null];
const isNumber = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);
const isText = (v: unknown): v is string => typeof v === 'string';

function readUnit(u: Record<string, unknown>, n: number): UnitDraft {
  const where = `unit ${n + 1}`;
  if (!isText(u.id) || !isText(u.name)) throw new Error(`${where} needs an id and a name.`);
  if (u.side !== 0 && u.side !== 1) throw new Error(`${u.name}: side must be 0 or 1.`);
  if (!TYPES.includes(u.type as UnitType | null)) throw new Error(`${u.name}: unknown type ${String(u.type)}.`);
  if (!(u.subtype === null || isText(u.subtype)) || !isNumber(u.size) || !isText(u.stats)
    || !(u.guns === null || isNumber(u.guns))) {
    throw new Error(`${u.name}: subtype, size, stats or guns is not readable.`);
  }
  return {
    id: u.id, name: u.name, side: u.side, type: u.type as UnitType | null, subtype: u.subtype, size: u.size,
    stats: u.stats, guns: u.guns, org: validateOrg(u.org ?? {}),
  };
}

/** Read a setup file's contents (already parsed); throws what is wrong with it. */
export function readSetup(data: Record<string, unknown>): Setup {
  if (data.version !== SETUP_VERSION) {
    throw new Error(`Unsupported setup file version ${String(data.version)} (expected ${SETUP_VERSION}).`);
  }
  const { name, sides, seed, ground, round_length: length, rounds_planned: rounds, start_clock: clock,
    zone_depth: depth, units } = data;
  if (!isText(name) || !Array.isArray(sides) || sides.length !== 2 || !sides.every(isText)) {
    throw new Error('The setup needs a name and two side names.');
  }
  if (!isNumber(seed) || !isText(ground) || !isNumber(length)) {
    throw new Error('The setup needs a seed, a ground and a round length.');
  }
  if (!(rounds === null || isNumber(rounds)) || !(clock === null || isText(clock))) {
    throw new Error('Rounds planned and the start clock must be a number and a time, or empty.');
  }
  if (!Array.isArray(depth) || depth.length !== 2 || !depth.every(isNumber)) {
    throw new Error('The setup needs a zone depth for each side.');
  }
  if (!Array.isArray(units)) throw new Error('The setup needs a list of units.');
  return {
    name, sides: [sides[0], sides[1]], seed, ground, round_length: length, rounds_planned: rounds, start_clock: clock,
    zone_depth: [depth[0], depth[1]], units: units.map((u, n) => readUnit(u as Record<string, unknown>, n)),
  };
}
