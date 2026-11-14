/**
 * Commander rating (port of the former Python engine's commanders.py): each side's commander as a historical general,
 * by how the battle's result compares with what the armies' strength led to expect. Formulas and the ladder are
 * `commanders` in defaults.json.
 */

import defaults from './defaults.json';
import { exp, log } from './fdlibm';
import { breakFraction } from './morale';
import { BattleParams, type Overrides, type Unit } from './params';
import type { StateData, UnitData } from './state';
import { sideSummary } from './summary';
import { ArtilleryBattery, parseStats } from './units';

export interface General {
  name: string;
  battle: string;
  from: number;
}

export interface CommandersConfig {
  power_exponent: number;
  gun_value: number;
  weights: { casualties: number; field: number; routs: number };
  ladder: General[];
}

export interface Rating {
  name: string;
  power: number; // hit rate × staying power, summed over the side as it began
  expected: number; // share of the result the strength led to expect
  result: number; // share of the result it took
  score: number; // result - expected: -1 to 1, 0 as expected
  general: General;
}

/** What a side brings to the result-share sum. */
export interface SideResult {
  casualties: number;
  guns_taken: number;
  units_out_men: number;
  started: number;
}

/** Hit rate × staying power of one unit (a state file's unit) as it began the battle. */
export function unitPower(unit: UnitData, params: BattleParams): number {
  const c = params.combat;
  const stats = parseStats(unit.initial_stats);
  const size = unit.initial_size;
  const coef = c.unitCoef(stats, 'ranged');
  let hitRate: number;
  if (unit.type === 'art') {
    const guns = Math.min(unit.guns! + unit.guns_lost, Math.floor(size / ArtilleryBattery.MIN_CREW_PER_GUN));
    hitRate = coef * guns * c.artillery_ammo[c.artillery_default_ammo];
  } else if (coef > 0) {
    hitRate = coef * size * c.ranged_kill_rate;
  } else {
    const key: Unit = [unit.type ?? 'inf', unit.subtype];
    hitRate = c.melee_kill_rate * c.meleeEfficiency(stats[0], stats[1], params.matchups.meleeRating(key))
      * Math.min(size, unit.front_size);
  }
  return hitRate * breakFraction(stats[0], stats[1], params.morale);
}

export function sidePower(state: StateData, side: number, params: BattleParams): number {
  let total = 0;
  for (const u of state.units) if (u.side === side) total += unitPower(u, params);
  return total;
}

const power = (x: number, k: number): number => (x === 0 ? 0.0 : exp(k * log(x)));

/** The share of the result a side's strength leads to expect: P^k / (P^k + Q^k). */
export function expectedShare(mine: number, other: number, exponent: number): number {
  const a = power(mine, exponent);
  const b = power(other, exponent);
  return a + b === 0 ? 0.5 : a / (a + b);
}

const share = (mine: number, theirs: number): number => (mine + theirs === 0 ? 0.5 : mine / (mine + theirs));

/** Each side's share of the result, from its casualties, guns taken, routed men and start, and the field holder. */
export function resultShares(sides: SideResult[], holder: number | null, cfg: CommandersConfig): number[] {
  const w = cfg.weights;
  const gun = cfg.gun_value;
  const routed = sides.map((s) => s.units_out_men / s.started);
  return [[0, 1], [1, 0]].map(([me, them]) => {
    const damage = share(sides[them].casualties + gun * sides[me].guns_taken,
      sides[me].casualties + gun * sides[them].guns_taken);
    const field = holder === null ? 0.5 : holder === me ? 1.0 : 0.0;
    return w.casualties * damage + w.field * field + w.routs * share(routed[them], routed[me]);
  });
}

/** The last general on the ladder whose 'from' the score reaches (the first if none). */
export function general(score: number, ladder: General[]): General {
  let pick = ladder[0];
  for (const g of ladder) if (score >= g.from) pick = g;
  return { ...pick };
}

/** Each side's commander rating for a finished battle; throws ValueError if it isn't finished. */
export function ratings(state: StateData, cfg: CommandersConfig = defaults.commanders): Rating[] {
  const summary = sideSummary(state); // throws if not finished
  const params = BattleParams.fromDict(state.params as unknown as Overrides);
  const powers = [0, 1].map((s) => sidePower(state, s, params));
  const sides = summary.map((s, side) => ({
    casualties: s.casualties, guns_taken: s.guns_taken, started: s.started,
    units_out_men: state.units.filter((u) => u.side === side && (u.morale.broken || u.size === 0))
      .reduce((total, u) => total + u.initial_size, 0),
  }));
  const results = resultShares(sides, state.result!.field_held_by, cfg);
  return [0, 1].map((side) => {
    const expected = expectedShare(powers[side], powers[1 - side], cfg.power_exponent);
    const score = results[side] - expected;
    return { name: summary[side].name, power: powers[side], expected, result: results[side], score,
      general: general(score, cfg.ladder) };
  });
}
