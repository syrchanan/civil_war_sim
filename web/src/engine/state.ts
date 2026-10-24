/**
 * Battle state file (port of python/imperial_generals/battles/state.py): the full state of a battle as JSON, so a
 * battle can be saved after any round and resumed later, in either language, with exactly the same results.
 *
 * Version 2: melee contacts, charges in the round history, charge params.
 */

import { Battle, BattleUnit, type BattleResult, type BySide, type RoundReport, type UnitSpec } from './battle';
import { ValueError } from './errors';
import { MoraleState } from './morale';
import { BattleParams, type Overrides, type ParamsData, type Stats } from './params';
import { Rng } from './rng';
import { ArtilleryBattery, CavalryRegiment, InfantryRegiment, type Position, Regiment } from './units';

export const FORMAT = 'imperial-generals-battle';
export const VERSION = 2;

export interface UnitData {
  id: string;
  name: string;
  side: number;
  type: string | null;
  subtype: string | null;
  size: number;
  initial_size: number;
  stats: string;
  initial_stats: string;
  front_size: number;
  raw_morale: number;
  combat_mode: string;
  position: Position | null;
  morale: { resolve: number; shock: number; lost: number; broken: boolean; break_scale: number };
  losses: number;
  inflicted: number;
  captured: number;
  guns_lost: number;
  meta: Record<string, unknown>;
  guns?: number;
}

export interface StateData {
  format: string;
  version: number;
  meta: Record<string, unknown>;
  seed: number | null;
  rng_state: number[];
  params: ParamsData;
  time: number;
  round: number;
  finished: boolean;
  prisoners: BySide;
  guns_captured: BySide;
  units: UnitData[];
  contacts: string[][];
  history: RoundReport[];
  result: BattleResult | null;
}

const statsText = (stats: Stats): string => stats.join('/');

/**
 * A tag for a battle as it stands between rounds: the rounds fought and the dice generator's state (as Python's
 * api.battle_tag). It changes with every round fought, so an orders file made from an older copy can be refused.
 */
export function battleTag(data: { round: number; rng_state: number[] }): string {
  return [data.round, ...data.rng_state].join('-');
}

// =============================================================================
// Saving
// =============================================================================

function unitToDict(unit: BattleUnit): UnitData {
  const reg = unit.regiment;
  const data: UnitData = {
    id: unit.uid,
    name: unit.name,
    side: unit.side,
    type: reg.unitType,
    subtype: reg.subtype,
    size: reg.size,
    initial_size: unit.initialSize,
    stats: statsText(reg.stats),
    initial_stats: statsText(unit.initialStats),
    front_size: reg.frontSize,
    raw_morale: reg.rawMorale,
    combat_mode: reg.combatMode,
    position: reg.position === null ? null : { ...reg.position, facing: reg.position.facing ?? null },
    morale: {
      resolve: unit.morale.resolve,
      shock: unit.morale.shock,
      lost: unit.morale.lost,
      broken: unit.morale.broken,
      break_scale: unit.morale.breakScale,
    },
    losses: unit.losses,
    inflicted: unit.inflicted,
    captured: unit.captured,
    guns_lost: unit.gunsLost,
    meta: structuredClone(unit.meta),
  };
  if (reg instanceof ArtilleryBattery) data.guns = reg.guns;
  return data;
}

export function battleToDict(battle: Battle): StateData {
  const index = (uid: string) => battle.units.get(uid)!.index;
  // each pair in unit order, then the pairs sorted (as Python sorts lists of strings)
  const contacts = [...battle.contacts].map((key) => key.split('\u0000').sort((a, b) => index(a) - index(b)));
  // pairs are unique: when the first ids match the second ones differ
  contacts.sort((a, b) => (a[0] !== b[0] ? (a[0] < b[0] ? -1 : 1) : (a[1] < b[1] ? -1 : 1)));
  return {
    format: FORMAT,
    version: VERSION,
    meta: structuredClone(battle.meta),
    seed: battle.seed,
    rng_state: battle.rng.state,
    params: battle.params.toDict(),
    time: battle.time,
    round: battle.round,
    finished: battle.finished,
    prisoners: { ...battle.prisoners },
    guns_captured: { ...battle.gunsCaptured },
    units: [...battle.units.values()].map(unitToDict),
    contacts,
    history: structuredClone(battle.history),
    result: structuredClone(battle.result),
  };
}

// =============================================================================
// Loading
// =============================================================================

/** The regiment as it started the battle (initial size and stats); live state is restored afterwards. */
function buildRegiment(data: UnitData): Regiment {
  const size = data.initial_size;
  const stats = data.initial_stats;
  if (data.type === null) return new Regiment(size, stats);
  if (data.type === 'inf') return new InfantryRegiment(size, stats, data.subtype!);
  if (data.type === 'cav') return new CavalryRegiment(size, stats, data.subtype!);
  if (data.type === 'art') return new ArtilleryBattery(size, stats, data.guns!, data.subtype!);
  throw new ValueError(`Unknown unit type ${data.type} for ${data.id}.`);
}

function restoreUnit(unit: BattleUnit, data: UnitData, params: BattleParams): void {
  const reg = unit.regiment;
  // the break point was drawn when the battle began: rebuild the morale state with the saved draw
  const stats = unit.initialStats;
  unit.morale = new MoraleState(unit.initialSize, stats[0], stats[1], params.morale, data.morale.break_scale);
  reg.updateSize(data.size);
  reg.updateStats(data.stats);
  reg.rawMorale = data.raw_morale;
  reg.setFrontSize(data.front_size);
  reg.setCombatMode(data.combat_mode);
  // facing is absent in files saved before it existed
  if (data.position !== null) reg.position = { ...data.position, facing: data.position.facing ?? null };
  const morale = unit.morale;
  morale.resolve = data.morale.resolve;
  morale.shock = data.morale.shock;
  morale.lost = data.morale.lost;
  morale.broken = data.morale.broken;
  unit.losses = data.losses;
  unit.inflicted = data.inflicted;
  unit.captured = data.captured;
  unit.gunsLost = data.guns_lost;
}

export function battleFromDict(data: StateData): Battle {
  if (data.format !== FORMAT) throw new ValueError(`Not a battle state file (format ${JSON.stringify(data.format)}).`);
  if (data.version !== VERSION) {
    throw new ValueError(`Unsupported battle state version ${JSON.stringify(data.version)} (expected ${VERSION}).`);
  }
  const units: Record<string, UnitSpec> = {};
  for (const u of data.units) units[u.id] = { side: u.side, regiment: buildRegiment(u), name: u.name, meta: u.meta };
  const battle = new Battle(units, Rng.fromState(data.rng_state),
    BattleParams.fromDict(data.params as unknown as Overrides), data.meta);
  for (const u of data.units) restoreUnit(battle.units.get(u.id)!, u, battle.params);
  battle.rng = Rng.fromState(data.rng_state); // building the units drew break points: rewind

  battle.seed = data.seed;
  battle.time = data.time;
  battle.round = data.round;
  battle.finished = data.finished;
  battle.prisoners = { ...data.prisoners };
  battle.gunsCaptured = { ...data.guns_captured };
  // retargets, round positions and modifiers are absent in files saved before they existed
  battle.history = structuredClone(data.history)
    .map((r) => ({ ...r, retargets: r.retargets ?? [], positions: r.positions ?? {}, modifiers: r.modifiers ?? {} }));
  battle.contacts = new Set(data.contacts.map(([a, b]) => (a < b ? `${a}\u0000${b}` : `${b}\u0000${a}`)));
  battle.result = data.result === null ? null : {
    ...structuredClone(data.result),
    // absent in files finished before the field votes
    field_decided_by: data.result.field_decided_by ?? 'admin',
    field_votes: data.result.field_votes ?? {},
  };
  return battle;
}
