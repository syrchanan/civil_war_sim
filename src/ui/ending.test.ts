// The battle's end in words and rankings: the verdict, each commander's phrase, the regiments ranked.
import { describe, expect, it } from 'vitest';

import type { Battle, BattleResult, Rating, SideSummary } from '../engine';
import { figure, generalPhrase, METRICS, ranked, type RegimentRow, regimentRows, verdictText } from './ending';

const SIDES = ['Union', 'Confederate'];
const side = (name: string, casualties: number, share: number, verdict: SideSummary['verdict']) =>
  ({ name, casualties, casualty_share: share, verdict }) as SideSummary;
const result = (holder: number | null, by: string, votes: Record<string, number | null> = {}) =>
  ({ field_held_by: holder, field_decided_by: by, field_votes: votes }) as BattleResult;

describe('the verdict', () => {
  it('the winner\'s verdict as a headline; the toll; the whole army broke', () => {
    const v = verdictText([side('Union', 332, 0.2, 'decisive victory'), side('Confederate', 710, 0.29, 'decisive defeat')],
      result(0, 'army_out'), SIDES);
    expect(v).toEqual({ kicker: 'Union holds the field', headline: 'A Decisive Union Victory', lines: [
      'Casualties: Union 332 (20%), Confederate 710 (29%).', 'The whole Confederate army broke.'] });
  });

  it('decided by the votes, one of them for neither; Pyrrhic or plain victories', () => {
    const v = verdictText([side('Union', 900, 0.5, 'defeat'), side('Confederate', 1200, 0.4, 'Pyrrhic victory')],
      result(1, 'votes', { exchange: 0, routs: null, standing: 1 }), SIDES);
    expect(v.headline).toBe('A Pyrrhic Confederate Victory');
    expect(v.lines[1]).toBe('Decided on the day\'s count: casualty exchange to Union, routs to neither, '
      + 'strength standing to Confederate.');
    expect(verdictText([side('Union', 1, 0, 'victory'), side('Confederate', 2, 0, 'defeat')], result(0, 'admin'), SIDES))
      .toMatchObject({ headline: 'A Union Victory', lines: ['Casualties: Union 1 (0%), Confederate 2 (0%).',
        'The field was named by the admin.'] });
  });

  it('nobody holds the field: a drawn battle', () => {
    expect(verdictText([side('Union', 1, 0, 'draw'), side('Confederate', 2, 0, 'draw')], result(null, 'admin'), SIDES))
      .toMatchObject({ kicker: 'Nobody holds the field', headline: 'A Drawn Battle' });
  });
});

describe('the generals', () => {
  const rating = (expected: number) => ({ expected }) as Rating;
  it('the odds the commander faced, and how it went', () => {
    expect(generalPhrase(rating(0.3), 'decisive victory')).toBe('the weaker army, and won it outright');
    expect(generalPhrase(rating(0.7), 'decisive defeat')).toBe('the stronger army, and was ruined');
    expect(generalPhrase(rating(0.5), 'draw')).toBe('evenly matched, and fought to a draw');
    expect(['victory', 'Pyrrhic victory', 'defeat'].map((v) => generalPhrase(rating(0.5), v as SideSummary['verdict'])))
      .toEqual(['evenly matched, and won', 'evenly matched, and won at a ruinous price', 'evenly matched, and was beaten']);
  });
});

/** A finished battle, as much of it as the rankings read. */
function battle(): Battle {
  const unit = (uid: string, side: number, inflicted: number, size: number, broken: boolean, resolve: number) =>
    [uid, { uid, name: uid.toUpperCase(), side, inflicted, initialSize: 400, size, morale: { broken, resolve } }] as const;
  const report = (round: number, start: number, units: Record<string, { broke_at?: number; size?: number }>) => ({
    round, start,
    units: Object.fromEntries(['a', 'b', 'c', 'd', 'e'].map((uid) => [uid,
      { broke_at: units[uid]?.broke_at ?? null, size: units[uid]?.size ?? 300 }])),
  });
  const outcome = (killed: number, wounded: number, captured: number, final: number) =>
    ({ killed, wounded, captured_in_rout: captured, final_size: final });
  return {
    units: new Map([
      unit('a', 0, 200, 380, false, 0.9), // steady, no losses but 20
      unit('b', 0, 50, 300, false, 0.4), // shaken
      unit('c', 1, 90, 200, true, 0), // broke in round 2
      unit('d', 1, 10, 150, false, 0.7), // broke in rounds 1 and 2, rallied
      unit('e', 1, 0, 0, true, 0), // wiped out in round 2
    ]),
    history: [report(1, 60, { d: { broke_at: 80 } }), report(2, 120, { c: { broke_at: 130 }, d: { broke_at: 150 },
      e: { broke_at: 125, size: 0 } })],
    result: { units: { a: outcome(0, 0, 0, 400), b: outcome(40, 60, 0, 300), c: outcome(50, 100, 50, 200),
      d: outcome(100, 100, 50, 150), e: outcome(100, 200, 100, 0) } },
  } as unknown as Battle;
}

describe('the regiments', () => {
  it('each regiment: what it did and lost, its men kept, minutes until it first broke, its day in words', () => {
    expect(regimentRows(battle())).toEqual([
      { uid: 'a', name: 'A', side: 0, inflicted: 200, lost: 0, kept: 1, minutes: null, story: 'Steady at nightfall' },
      { uid: 'b', name: 'B', side: 0, inflicted: 50, lost: 100, kept: 0.75, minutes: null, story: 'Shaken at nightfall' },
      { uid: 'c', name: 'C', side: 1, inflicted: 90, lost: 200, kept: 0.5, minutes: 70, story: 'Broke in round 2' },
      { uid: 'd', name: 'D', side: 1, inflicted: 10, lost: 250, kept: 0.375, minutes: 20,
        story: 'Broke in rounds 1 and 2, rallied' },
      { uid: 'e', name: 'E', side: 1, inflicted: 0, lost: 400, kept: 0, minutes: 65, story: 'Wiped out in round 2' },
    ]);
  });

  it('a battle finished before any round: everyone steady, the clock from 0', () => {
    const b = battle();
    (b as unknown as { history: unknown[] }).history = [];
    expect(regimentRows(b).map((r) => r.minutes)).toEqual([null, null, null, null, null]);
  });

  it('ranked best first by each metric, never broken best; ties to the one that inflicted more; in words', () => {
    const rows = regimentRows(battle());
    const order = (metric: (typeof METRICS)[number][0]) => ranked(rows, metric).map((r) => r.uid).join('');
    expect(METRICS.map(([m]) => order(m))).toEqual(['abcde', 'acbde', 'abcde', 'abced']);
    const tie: RegimentRow[] = [{ ...rows[0], uid: 'x' }, { ...rows[0], uid: 'y' }];
    expect(ranked(tie, 'inflicted').map((r) => r.uid)).toEqual(['x', 'y']);
    // never fought (none inflicted, none lost): last by the ratio; level on men kept, behind one that fought
    const idle: RegimentRow = { ...rows[0], uid: 'idle', inflicted: 0 };
    expect(ranked([idle, rows[4]], 'ratio').map((r) => r.uid)).toEqual(['idle', 'e']); // 0 and 0: the battle's order
    expect(ranked([idle, rows[0]], 'kept').map((r) => r.uid)).toEqual(['a', 'idle']);
    expect(figure(idle, 'ratio')).toBe('—');
    expect(METRICS.map(([m]) => figure(rows[0], m))).toEqual(['none lost', '200', '100%', 'unbroken']);
    expect(METRICS.map(([m]) => figure(rows[2], m))).toEqual(['0.45', '90', '50%', '70 min']);
  });
});
