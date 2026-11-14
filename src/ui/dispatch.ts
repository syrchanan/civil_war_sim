/**
 * A round's dispatch: the round told as a short newspaper report. A headline from its most notable event, a few
 * sentences in the order things happened, each side's regiments (what they lost, what is left, how they stand), the
 * charges, and for a player what was seen of the enemy. Pure: the store supplies who sees what (`DispatchView`).
 */

import { roughly, type RoundReport } from '../engine';
import { CHARGE_OUTCOMES } from './format';

/** What the viewer knows: their side (null: the admin, who sees both) and what was seen of each unit. */
export interface DispatchView {
  side: 0 | 1 | null;
  sides: readonly [string, string];
  /** A unit the viewer knows of: its name, side and starting raw morale. */
  unit(uid: string): { name: string; side: number; initialMorale: number };
  /** '1:24 pm', or '84 min' when the battle has no start clock. */
  clock(minutes: number): string;
  /** Was the unit seen as the round began, and as it ended? (always, for the viewer's own) */
  seenStart(uid: string): boolean;
  seenEnd(uid: string): boolean;
}

export type UnitState = 'steady' | 'shaken' | 'wavering' | 'broken' | 'wiped out';

export interface DispatchRow {
  uid: string;
  name: string;
  lost: number;
  left: number;
  state: UnitState;
  /** Morale left, as a share of where it started; null once broken. */
  morale: number | null;
}

export interface Dispatch {
  round: number;
  span: string;
  headline: string;
  summary: string[];
  sides: { side: number; rows: DispatchRow[] }[];
  charges: string[];
  enemy: string[];
}

/** How a unit stands from its morale share: steady from 60%, shaken from 30%, then wavering, until it breaks. */
export function unitState(size: number, broken: boolean, morale: number): UnitState {
  if (size === 0) return 'wiped out';
  if (broken) return 'broken';
  if (morale >= 0.6) return 'steady';
  return morale >= 0.3 ? 'shaken' : 'wavering';
}

/** 'the 8th Alabama' (a numbered regiment takes 'the'), 'Battery B'; capitalised to open a sentence. */
export function called(name: string, opening = false): string {
  const text = /^\d/.test(name) ? `the ${name}` : name;
  return opening ? text[0].toUpperCase() + text.slice(1) : text;
}

const listed = (names: string[]): string => (names.length === 1 ? names[0]
  : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`);

const NUMBER_WORDS = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'];
const count = (n: number) => NUMBER_WORDS[n] ?? String(n);

/** An event of the round: when, how notable (lower first), a headline and a sentence. */
interface Event {
  time: number;
  rank: number;
  headline: string;
  sentence: string;
}

function chargeEvent(c: RoundReport['charges'][number], name: (uid: string) => string): Event {
  const ch = name(c.charger);
  const tg = name(c.target);
  const [rank, headline, sentence] = {
    home: [2, `${called(ch, true)}'s charge carries ${called(tg)}`, `${called(ch, true)} charged ${called(tg)} and went home.`],
    defender_broke: [2, `${called(ch, true)}'s charge breaks ${called(tg)}`,
      `${called(ch, true)} charged ${called(tg)}, which broke before the charge struck home.`],
    target_broke: [2, `${called(ch, true)}'s charge breaks ${called(tg)}`,
      `${called(ch, true)} charged ${called(tg)}, which broke before contact.`],
    meeting: [2, `${called(ch, true)} and ${called(tg)} meet head on`, `${called(ch, true)} and ${called(tg)} met head on.`],
    pursuit: [2, `${called(ch, true)} rides down ${called(tg)}`, `${called(ch, true)} pursued the broken ${tg}.`],
    faltered: [3, `${called(ch, true)}'s charge is thrown back from ${called(tg)}`,
      `${called(ch, true)} charged ${called(tg)} and faltered under its fire, falling back.`],
    charger_broke: [3, `${called(ch, true)}'s charge is thrown back from ${called(tg)}`,
      `${called(ch, true)} broke on the approach to ${called(tg)}.`],
    escaped: [4, `${called(tg, true)} slips away from ${called(ch)}`,
      `${called(tg, true)} fled too fast for ${called(ch)} to catch.`],
  }[c.outcome] as [number, string, string];
  return { time: c.resolved_at, rank, headline, sentence };
}

/** The dispatch for one round, as the viewer sees it; `previous` is the round before (null for the first). */
export function dispatch(report: RoundReport, previous: RoundReport | null, view: DispatchView): Dispatch {
  const name = (uid: string) => view.unit(uid).name;
  const sideOf = (uid: string) => view.unit(uid).side;
  const own = (uid: string) => view.side === null || sideOf(uid) === view.side;
  const units = Object.entries(report.units);
  const wasBroken = (uid: string) => previous?.units[uid]?.broken ?? false;

  const events: Event[] = report.charges.map((c) => chargeEvent(c, name));
  // a unit broken by a charge is told with the charge
  const chargedDown = new Set(report.charges
    .filter((c) => ['defender_broke', 'target_broke', 'pursuit'].includes(c.outcome)).map((c) => c.target));
  const broke: { uid: string; time: number }[] = [];
  for (const [uid, u] of units) {
    if (!own(uid)) continue;
    if (u.guns_lost > 0) {
      events.push({ time: report.end, rank: 1, headline: `${called(name(uid), true)} is overrun`,
        sentence: `${called(name(uid), true)} was overrun, losing ${u.guns_lost} gun${u.guns_lost === 1 ? '' : 's'}.` });
    } else if (u.size === 0 && u.losses > 0) {
      events.push({ time: report.end, rank: 1, headline: `${called(name(uid), true)} is wiped out`,
        sentence: `${called(name(uid), true)} was wiped out.` });
    } else if (u.broke_at !== null && !chargedDown.has(uid)) {
      broke.push({ uid, time: u.broke_at });
    }
  }
  if (broke.length) {
    const names = broke.map((b) => called(name(b.uid)));
    const headline = broke.length <= 2 ? `${listed(names)} break${broke.length === 1 ? 's' : ''}`
      : `${count(broke.length)} regiments break`;
    events.push({ time: broke[0].time, rank: 4, headline: headline[0].toUpperCase() + headline.slice(1),
      sentence: '' });
    for (const b of broke) {
      events.push({ time: b.time, rank: 9, headline: '',
        sentence: `${called(name(b.uid), true)} broke at ${view.clock(b.time)}.` });
    }
  }
  for (const r of report.rallies.filter((x) => x.rallied)) {
    events.push({ time: report.start, rank: 5, headline: `${called(name(r.unit), true)} rallies`,
      sentence: `${called(name(r.unit), true)} rallied.` });
  }
  for (const f of report.flights) {
    events.push({ time: report.end, rank: 9, headline: '',
      sentence: `${called(name(f.unit), true)} fled ${Math.round(f.distance)} yards.` });
  }

  const rows = (side: number): DispatchRow[] => units.filter(([uid]) => sideOf(uid) === side).map(([uid, u]) => {
    const share = u.morale / view.unit(uid).initialMorale;
    const state = unitState(u.size, u.broken, share);
    return { uid, name: name(uid), lost: u.losses, left: u.size, state,
      morale: state === 'broken' || state === 'wiped out' ? null : share };
  });
  const sides = (view.side === null ? [0, 1] : [view.side]).map((side) => ({ side, rows: rows(side) }));

  const lead = events.filter((e) => e.headline !== '').sort((a, b) => a.rank - b.rank || a.time - b.time)[0];
  const fallen = sides.flatMap((s) => s.rows).reduce((sum, r) => sum + r.lost, 0);
  const headline = lead?.headline ?? (fallen >= 300 ? `A hard round: ${fallen.toLocaleString('en-US')} men fall`
    : fallen > 0 ? `A steady exchange of fire: ${fallen.toLocaleString('en-US')} men fall`
      : 'A quiet round along the line');
  const told = events.filter((e) => e.sentence !== '').sort((a, b) => a.time - b.time || a.rank - b.rank);
  const summary = told.length ? told.slice(0, 3).map((e) => e.sentence)
    : ['No charge went in, and no regiment broke.'];

  const charges = report.charges.map((c) => `${name(c.charger)} on ${name(c.target)}: ${CHARGE_OUTCOMES[c.outcome]} at `
    + view.clock(c.resolved_at));

  const enemy: string[] = [];
  if (view.side !== null) {
    const taken = report.prisoners[String(view.side)] ?? 0;
    if (taken > 0) enemy.push(`Took about ${roughly(taken).toLocaleString('en-US')} prisoners.`);
    for (const [uid, u] of units) {
      if (own(uid)) continue;
      if (u.broken && !wasBroken(uid) && view.seenEnd(uid)) enemy.push(`${called(name(uid), true)} was seen to break.`);
      if (view.seenStart(uid) && !view.seenEnd(uid)) enemy.push(`${called(name(uid), true)} moved out of sight.`);
    }
  }

  const clockSpan = `${view.clock(report.start)} to ${view.clock(report.end)}`;
  return { round: report.round, span: clockSpan, headline, summary, sides, charges, enemy };
}
