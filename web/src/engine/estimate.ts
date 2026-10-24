/**
 * Player mode's estimate: the next round fought many times from the current state with different dice, summed up
 * as ranges. The battle itself is never touched. Runs use fixed seeds (1, 2, ...), so the same battle and orders
 * always give the same estimate, and two plans are compared on the same dice.
 */

import { Battle, type OrderInput } from './battle';
import { Rng } from './rng';

export interface Range {
  p10: number;
  p50: number;
  p90: number;
}

export interface UnitEstimate {
  losses: Range; // men hit this round
  captured: Range; // men taken prisoner as the unit routed
  size: Range; // men left at the end of the round
  breakChance: number; // share of runs in which the unit ends the round broken
}

export interface ChargeEstimate {
  charger: string;
  target: string;
  outcomes: Record<string, number>; // outcome -> share of the runs in which this charge was made
}

export interface RoundEstimate {
  runs: number;
  units: Record<string, UnitEstimate>;
  charges: ChargeEstimate[];
}

/** The q-quantile of `values` by nearest rank: an actual value from the runs, never an interpolated one. */
export function quantile(values: number[], q: number): number {
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.min(sorted.length - 1, Math.max(0, Math.ceil(q * sorted.length) - 1));
  return sorted[index];
}

const range = (values: number[]): Range => ({ p10: quantile(values, 0.1), p50: quantile(values, 0.5), p90: quantile(values, 0.9) });

/** Fight the next round `runs` times with `orders` and summarise what happened. */
export function estimateRound(battle: Battle, orders: Record<string, OrderInput | null>, duration: number,
  runs = 200): RoundEstimate {
  const start = battle.toDict();
  const uids = [...battle.units.keys()];
  const per: Record<string, { losses: number[]; captured: number[]; size: number[]; broken: number }> = {};
  for (const uid of uids) per[uid] = { losses: [], captured: [], size: [], broken: 0 };
  const charges = new Map<string, { charger: string; target: string; counts: Record<string, number>; made: number }>();

  for (let run = 1; run <= runs; run++) {
    const copy = Battle.fromDict(start);
    copy.rng = new Rng(run);
    const report = copy.resolveRound(duration, orders);
    for (const uid of uids) {
      const u = report.units[uid];
      per[uid].losses.push(u.losses);
      per[uid].captured.push(u.captured);
      per[uid].size.push(u.size);
      if (u.broken) per[uid].broken += 1;
    }
    for (const c of report.charges) {
      const key = `${c.charger}>${c.target}`;
      if (!charges.has(key)) charges.set(key, { charger: c.charger, target: c.target, counts: {}, made: 0 });
      const entry = charges.get(key)!;
      entry.made += 1;
      entry.counts[c.outcome] = (entry.counts[c.outcome] ?? 0) + 1;
    }
  }

  const units: Record<string, UnitEstimate> = {};
  for (const uid of uids) {
    const p = per[uid];
    units[uid] = { losses: range(p.losses), captured: range(p.captured), size: range(p.size), breakChance: p.broken / runs };
  }
  return {
    runs,
    units,
    charges: [...charges.values()].map(({ charger, target, counts, made }) => ({
      charger, target, outcomes: Object.fromEntries(Object.entries(counts).map(([o, n]) => [o, n / made])),
    })),
  };
}
