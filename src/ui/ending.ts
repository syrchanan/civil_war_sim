/**
 * The battle's end in words and rankings (pure): the verdict, how each commander fought, and the regiments ranked
 * by how well they did. The Result tab draws them (BattleEnd.tsx).
 */

import type { Battle, BattleResult, Rating, SideSummary, Verdict } from '../engine';
import { unitState } from './dispatch';
import { FIELD_TESTS } from './format';

const n = (v: number) => v.toLocaleString('en-US');
const pct = (v: number) => `${Math.round(v * 100)}%`;

export interface VerdictView {
  kicker: string; // 'Union holds the field'
  headline: string; // 'A Decisive Union Victory'
  lines: string[];
}

const KIND: Partial<Record<Verdict, string>> = { 'decisive victory': 'Decisive ', 'Pyrrhic victory': 'Pyrrhic ' };

/** The verdict banner: who holds the field, the winner's verdict as a headline, the toll and why. */
export function verdictText(summary: SideSummary[], result: BattleResult, sides: readonly string[]): VerdictView {
  const holder = result.field_held_by;
  const toll = `Casualties: ${summary.map((s) => `${s.name} ${n(s.casualties)} (${pct(s.casualty_share)})`).join(', ')}.`;
  let why: string;
  if (result.field_decided_by === 'army_out') {
    why = `The whole ${sides[1 - holder!]} army broke.`;
  } else if (result.field_decided_by === 'votes') {
    const votes = result.field_votes as Record<string, number | null>;
    why = `Decided on the day's count: ${FIELD_TESTS.map(([test, label]) => `${label} to ${votes[test] === null
      ? 'neither' : sides[votes[test]!]}`).join(', ')}.`;
  } else {
    why = 'The field was named by the admin.';
  }
  if (holder === null) return { kicker: 'Nobody holds the field', headline: 'A Drawn Battle', lines: [toll, why] };
  const kind = KIND[summary[holder].verdict] ?? '';
  return { kicker: `${sides[holder]} holds the field`, headline: `A ${kind}${sides[holder]} Victory`, lines: [toll, why] };
}

const OUTCOME: Record<Verdict, string> = {
  'decisive victory': 'won it outright', victory: 'won', 'Pyrrhic victory': 'won at a ruinous price',
  draw: 'fought to a draw', defeat: 'was beaten', 'decisive defeat': 'was ruined',
};

/** How a commander fought, for after the general's name: 'outnumbered, and won it outright'. */
export function generalPhrase(rating: Rating, verdict: Verdict): string {
  const odds = rating.expected < 0.45 ? 'the weaker army' : rating.expected > 0.55 ? 'the stronger army' : 'evenly matched';
  return `${odds}, and ${OUTCOME[verdict]}`;
}

export type Metric = 'ratio' | 'inflicted' | 'kept' | 'time';

export const METRICS: [Metric, string][] = [
  ['ratio', 'Casualties inflicted per man lost'], ['inflicted', 'Casualties inflicted'], ['kept', 'Share of men kept'],
  ['time', 'Time before breaking'],
];

export interface RegimentRow {
  uid: string;
  name: string;
  side: 0 | 1;
  inflicted: number;
  lost: number; // killed, wounded and taken
  kept: number; // share of its men in the ranks at nightfall
  minutes: number | null; // until it first broke; null: never
  story: string; // 'Broke in round 2, rallied'
}

/** Each regiment of a finished battle: what it did and lost, and its day in a few words. */
export function regimentRows(battle: Battle): RegimentRow[] {
  const result = battle.result!;
  const start = battle.history.length ? battle.history[0].start : 0;
  return [...battle.units.values()].map((u) => {
    const o = result.units[u.uid];
    const broke = battle.history.filter((r) => r.units[u.uid].broke_at !== null);
    const wipedIn = battle.history.find((r) => r.units[u.uid].size === 0);
    let story: string;
    if (wipedIn !== undefined) story = `Wiped out in round ${wipedIn.round}`;
    else if (broke.length === 0) story = `${cap(unitState(u.size, false, u.morale.resolve))} at nightfall`;
    else {
      story = `Broke in round${broke.length > 1 ? 's' : ''} ${listed(broke.map((r) => String(r.round)))}`;
      if (!u.morale.broken) story += ', rallied';
    }
    return {
      uid: u.uid, name: u.name, side: u.side as 0 | 1, inflicted: u.inflicted,
      lost: o.killed + o.wounded + o.captured_in_rout, kept: o.final_size / u.initialSize,
      minutes: broke.length ? broke[0].units[u.uid].broke_at! - start : null, story,
    };
  });
}

/** A row's figure for a metric, as a number to rank by (higher is better). */
function score(row: RegimentRow, metric: Metric): number {
  // none lost counts as one, so a regiment that never fought ranks with those that did little
  if (metric === 'ratio') return row.inflicted / Math.max(row.lost, 1);
  if (metric === 'inflicted') return row.inflicted;
  if (metric === 'kept') return row.kept;
  return row.minutes ?? Infinity;
}

/** A row's figure for a metric, in words: '2.09', '205', '80%', '35 min'. */
export function figure(row: RegimentRow, metric: Metric): string {
  if (metric === 'ratio') return row.lost > 0 ? (row.inflicted / row.lost).toFixed(2) : row.inflicted > 0 ? 'none lost' : '—';
  if (metric === 'inflicted') return n(row.inflicted);
  if (metric === 'kept') return pct(row.kept);
  return row.minutes === null ? 'unbroken' : `${n(row.minutes)} min`;
}

/** The rows best first by a metric; ties go to the one that inflicted more, then keep the battle's order. */
export function ranked(rows: RegimentRow[], metric: Metric): RegimentRow[] {
  return rows.map((row, i) => ({ row, i })).sort((a, b) => {
    const [x, y] = [score(a.row, metric), score(b.row, metric)];
    if (x !== y) return y - x;
    return a.row.inflicted === b.row.inflicted ? a.i - b.i : b.row.inflicted - a.row.inflicted;
  }).map(({ row }) => row);
}

const cap = (s: string) => s[0].toUpperCase() + s.slice(1);
const listed = (items: string[]) => (items.length === 1 ? items[0]
  : `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`);
