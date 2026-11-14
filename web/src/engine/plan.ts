/**
 * State file version 3: each unit's org (corps, division and brigade names, for organising lists only) and the
 * battle's plan (rounds planned, the start clock, the phase and the deployment zones). Port of validate_org /
 * validate_plan in python/imperial_generals/battles/battle.py, which carries them through untouched; the game flow
 * that acts on them (deployment, opening the battle, rounds planned) lives here in the web engine only.
 */

import { ValueError } from './errors';

export const ORG_KEYS = ['corps', 'division', 'brigade'] as const;
export type OrgKey = (typeof ORG_KEYS)[number];
export type Org = Partial<Record<OrgKey, string>>;

export const PHASES = ['deployment', 'battle'] as const;
export type Phase = (typeof PHASES)[number];

const PLAN_KEYS = ['rounds_planned', 'start_clock', 'phase', 'zones'];
const ZONE_KEYS = ['x', 'y', 'w', 'h'] as const;

/** Where a side may deploy: a rectangle in yards. */
export interface DeployZone {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Plan {
  rounds_planned: number | null;
  start_clock: string | null;
  phase: Phase;
  zones: Record<string, DeployZone>; // '0' / '1'; a side left out may deploy anywhere
}

const isObject = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v);
const repr = (v: unknown): string => (typeof v === 'string' ? `'${v}'` : String(v));

/** A unit's corps, division and brigade names: each optional text; empty names are left out. */
export function validateOrg(org: unknown): Org {
  if (!isObject(org)) throw new ValueError('org must be a mapping of corps, division and brigade to names.');
  const unknown = Object.keys(org).filter((k) => !(ORG_KEYS as readonly string[]).includes(k)).sort();
  if (unknown.length) throw new ValueError(`Unknown org key(s) ${unknown.join(', ')}; use corps, division, brigade.`);
  const out: Org = {};
  for (const key of ORG_KEYS) {
    const value = org[key];
    if (value === undefined || value === null || value === '') continue;
    if (typeof value !== 'string') throw new ValueError(`org ${key} must be text, got ${repr(value)}.`);
    out[key] = value;
  }
  return out;
}

const isClock = (v: unknown): v is string => typeof v === 'string' && /^\d\d:\d\d$/.test(v)
  && Number(v.slice(0, 2)) < 24 && Number(v.slice(3)) < 60;

function checkZone(side: string, zone: unknown): DeployZone {
  if (!isObject(zone) || Object.keys(zone).sort().join() !== [...ZONE_KEYS].sort().join()) {
    throw new ValueError(`side ${side}'s deployment zone must be {x, y, w, h} in yards.`);
  }
  for (const key of ZONE_KEYS) {
    const value = zone[key];
    if (typeof value !== 'number' || !Number.isFinite(value)) {
      throw new ValueError(`side ${side}'s deployment zone ${key} must be a number of yards, got ${repr(value)}.`);
    }
  }
  const z = zone as unknown as DeployZone;
  if (!(z.w > 0 && z.h > 0)) throw new ValueError(`side ${side}'s deployment zone needs a width and a height above 0.`);
  return { x: z.x, y: z.y, w: z.w, h: z.h };
}

/** A battle's plan, made complete (zones keyed '0' / '1'); null or absent is open-ended, in battle, no zones. */
export function validatePlan(plan: unknown): Plan {
  const p = plan ?? {};
  if (!isObject(p)) throw new ValueError('The plan must be a mapping.');
  const unknown = Object.keys(p).filter((k) => !PLAN_KEYS.includes(k)).sort();
  if (unknown.length) throw new ValueError(`Unknown plan key(s) ${unknown.join(', ')}; use ${PLAN_KEYS.join(', ')}.`);
  const rounds = p.rounds_planned ?? null;
  if (rounds !== null && !(Number.isInteger(rounds) && (rounds as number) >= 1)) {
    throw new ValueError(`rounds_planned must be a whole number, 1 or more, or left out; got ${repr(rounds)}.`);
  }
  const clock = p.start_clock ?? null;
  if (clock !== null && !isClock(clock)) {
    throw new ValueError(`start_clock must be a time 'HH:MM' (24-hour clock), got ${repr(clock)}.`);
  }
  const phase = p.phase ?? 'battle';
  if (!(PHASES as readonly unknown[]).includes(phase)) {
    throw new ValueError(`phase must be 'deployment' or 'battle', got ${repr(phase)}.`);
  }
  const zones = p.zones ?? {};
  if (!isObject(zones)) throw new ValueError('zones must be a mapping of side to {x, y, w, h}.');
  const checked: Record<string, DeployZone> = {};
  // integer-like keys ('0', '1') come out in ascending order, as Python sorts them
  for (const [key, zone] of Object.entries(zones)) {
    if (key !== '0' && key !== '1') throw new ValueError(`A deployment zone's side must be 0 or 1, got ${repr(key)}.`);
    checked[key] = checkZone(key, zone);
  }
  return { rounds_planned: rounds as number | null, start_clock: clock as string | null, phase: phase as Phase, zones: checked };
}

/** Is the point inside the zone (edges included)? */
export const inside = (zone: DeployZone, x: number, y: number): boolean =>
  zone.x <= x && x <= zone.x + zone.w && zone.y <= y && y <= zone.y + zone.h;
