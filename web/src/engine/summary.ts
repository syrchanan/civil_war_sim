/**
 * Battle summaries from a state file (port of api.order_of_battle / api.side_summary in
 * python/imperial_generals/api.py), for the client's tables and for players' feedback.
 */

import { ValueError } from './errors';
import type { StateData, UnitData } from './state';
import { parseStats } from './units';

export interface TypeTotal {
  units: number;
  men: number;
  guns?: number;
}

export interface SideOrder {
  name: string;
  units: number;
  men: number;
  by_type: Record<string, TypeTotal>;
  avg_experience: number;
  avg_morale: number;
}

export interface SideSummary {
  name: string;
  outcome: 'won' | 'lost' | 'drawn';
  held_field: boolean;
  units: number;
  units_out: number;
  started: number;
  killed: number;
  wounded: number;
  prisoners_lost: number;
  casualties: number;
  casualty_share: number;
  returned: number;
  final: number;
  loss_share: number;
  hits_taken: number;
  hits_inflicted: number;
  exchange_ratio: number | null;
  prisoners_taken: number;
  guns_lost: number;
  guns_taken: number;
}

function sideNames(state: StateData): [string, string] {
  const sides = state.meta.sides;
  return Array.isArray(sides) && sides.length === 2 ? [String(sides[0]), String(sides[1])] : ['Side 0', 'Side 1'];
}

const sum = <T>(items: T[], f: (item: T) => number): number => items.reduce((s, item) => s + f(item), 0);
const sideUnits = (state: StateData, side: number): UnitData[] => state.units.filter((u) => u.side === side);

/**
 * Each side as the battle began: units, men, men by unit type (artillery also counts guns), and experience and
 * morale averaged over the men. Generic units count as infantry, as they do in combat.
 */
export function orderOfBattle(state: StateData): SideOrder[] {
  const names = sideNames(state);
  return [0, 1].map((side) => {
    const units = sideUnits(state, side);
    const men = sum(units, (u) => u.initial_size);
    const byType: Record<string, TypeTotal> = {};
    let xp = 0;
    let morale = 0;
    for (const u of units) {
      const kind = (byType[u.type ?? 'inf'] ??= { units: 0, men: 0 });
      kind.units += 1;
      kind.men += u.initial_size;
      if (u.guns !== undefined) kind.guns = (kind.guns ?? 0) + u.guns + u.guns_lost;
      const stats = parseStats(u.initial_stats);
      xp += stats[0] * u.initial_size;
      morale += stats[1] * u.initial_size;
    }
    return { name: names[side], units: units.length, men, by_type: byType, avg_experience: xp / men,
      avg_morale: morale / men };
  });
}

/**
 * Each side's performance over a finished battle. started - killed - wounded - prisoners_lost + returned = final,
 * where wounded excludes wounded taken prisoner. `outcome` reads the field as the result: 'won' (held the field),
 * 'lost' (the other side held it) or 'drawn' (nobody did).
 */
export function sideSummary(state: StateData): SideSummary[] {
  const result = state.result;
  if (result === null) throw new ValueError('The battle has to be finished first (finish settles killed / wounded / prisoners).');
  const names = sideNames(state);
  const holder = result.field_held_by;
  return [0, 1].map((side) => {
    const units = sideUnits(state, side);
    const outcomes = units.map((u) => result.units[u.id]);
    const started = sum(units, (u) => u.initial_size);
    const final = sum(units, (u) => u.size);
    const taken = sum(outcomes, (o) => o.hits);
    const inflicted = sum(units, (u) => u.inflicted);
    const killed = sum(outcomes, (o) => o.killed);
    const wounded = sum(outcomes, (o) => o.wounded - o.wounded_captured);
    const prisonersLost = sum(outcomes, (o) => o.captured_in_rout + o.wounded_captured);
    return {
      name: names[side],
      outcome: holder === null ? 'drawn' : holder === side ? 'won' : 'lost',
      held_field: holder === side,
      units: units.length,
      units_out: units.filter((u) => u.morale.broken || u.size === 0).length,
      started,
      killed,
      wounded,
      prisoners_lost: prisonersLost,
      casualties: killed + wounded + prisonersLost,
      casualty_share: (killed + wounded + prisonersLost) / started,
      returned: sum(outcomes, (o) => o.wounded_returned),
      final,
      loss_share: (started - final) / started,
      hits_taken: taken,
      hits_inflicted: inflicted,
      exchange_ratio: taken ? inflicted / taken : null,
      prisoners_taken: result.prisoners[String(side)],
      guns_lost: sum(outcomes, (o) => o.guns_lost),
      guns_taken: result.guns_captured[String(side)],
    };
  });
}
