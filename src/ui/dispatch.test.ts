// A round told as a dispatch: headlines by what mattered most, the sentences, the regiments' state, the enemy seen.
import { describe, expect, it } from 'vitest';

import type { Charge, RoundReport, UnitReport } from '../engine';
import { called, dispatch, type DispatchView, unitState } from './dispatch';

const UNITS: Record<string, { name: string; side: number }> = {
  mn: { name: '1st Minnesota', side: 0 }, ma: { name: '15th Massachusetts', side: 0 }, bat: { name: 'Battery B', side: 0 },
  al8: { name: '8th Alabama', side: 1 }, al10: { name: '10th Alabama', side: 1 }, ross: { name: "Ross's Battery", side: 1 },
};

const unit = (change: Partial<UnitReport> = {}): UnitReport => ({
  losses: 0, inflicted: 0, size: 500, morale: 50, broken: false, broke_at: null, captured: 0, guns_lost: 0, ...change,
});

function report(change: Partial<RoundReport> = {}, units: Record<string, Partial<UnitReport>> = {}): RoundReport {
  return {
    round: 1, start: 0, end: 60, orders: {}, engagements: [], events: [], prisoners: { 0: 0, 1: 0 },
    guns_captured: { 0: 0, 1: 0 }, charges: [], retargets: [], positions: {}, modifiers: {}, side_modifiers: {},
    rallies: [], flights: [],
    units: Object.fromEntries(Object.keys(UNITS).map((uid) => [uid, unit(units[uid])])),
    ...change,
  } as RoundReport;
}

const charge = (charger: string, target: string, outcome: string, at = 24): Charge => ({
  charger, target, outcome, start: at - 5, resolved_at: at, p_home: null, p_falter: null, p_defender_breaks: null,
});

function view(change: Partial<DispatchView> = {}): DispatchView {
  return {
    side: null, sides: ['Union', 'Confederate'],
    unit: (uid) => ({ ...UNITS[uid], initialMorale: 100 }),
    clock: (m) => `${m} min`, seenStart: () => true, seenEnd: () => true, ...change,
  };
}

describe('words', () => {
  it('a numbered regiment takes "the"', () => {
    expect([called('8th Alabama'), called('8th Alabama', true), called('Battery B'), called("Ross's Battery", true)])
      .toEqual(['the 8th Alabama', 'The 8th Alabama', 'Battery B', "Ross's Battery"]);
  });

  it('how a unit stands, from its morale share', () => {
    expect([unitState(500, false, 0.6), unitState(500, false, 0.59), unitState(500, false, 0.3),
      unitState(500, false, 0.29), unitState(500, true, 0.9), unitState(0, true, 0)])
      .toEqual(['steady', 'shaken', 'shaken', 'wavering', 'broken', 'wiped out']);
  });
});

describe('the headline: the most notable thing first', () => {
  const headline = (r: RoundReport, v = view()) => dispatch(r, null, v).headline;

  it('a battery overrun or a regiment wiped out comes before everything', () => {
    const charged = [charge('al8', 'mn', 'home')];
    expect(headline(report({ charges: charged }, { bat: { guns_lost: 2, broken: true } }))).toBe('Battery B is overrun');
    expect(headline(report({ charges: charged }, { ma: { size: 0, losses: 300, broken: true } })))
      .toBe('The 15th Massachusetts is wiped out');
  });

  it('then the charges, by how they ended', () => {
    const cases: [string, string][] = [
      ['home', "The 8th Alabama's charge carries the 1st Minnesota"],
      ['defender_broke', "The 8th Alabama's charge breaks the 1st Minnesota"],
      ['target_broke', "The 8th Alabama's charge breaks the 1st Minnesota"],
      ['meeting', 'The 8th Alabama and the 1st Minnesota meet head on'],
      ['pursuit', 'The 8th Alabama rides down the 1st Minnesota'],
      ['faltered', "The 8th Alabama's charge is thrown back from the 1st Minnesota"],
      ['charger_broke', "The 8th Alabama's charge is thrown back from the 1st Minnesota"],
      ['escaped', 'The 1st Minnesota slips away from the 8th Alabama'],
    ];
    for (const [outcome, text] of cases) expect(headline(report({ charges: [charge('al8', 'mn', outcome)] }))).toBe(text);
    // a charge that went home outranks one thrown back, whatever the order
    expect(headline(report({ charges: [charge('al10', 'ma', 'faltered', 10), charge('al8', 'mn', 'home', 30)] })))
      .toBe("The 8th Alabama's charge carries the 1st Minnesota");
  });

  it('then breaks: one, two, or how many', () => {
    expect(headline(report({}, { mn: { broken: true, broke_at: 30 } }))).toBe('The 1st Minnesota breaks');
    expect(headline(report({}, { mn: { broken: true, broke_at: 30 }, bat: { broken: true, broke_at: 40 } })))
      .toBe('The 1st Minnesota and Battery B break');
    expect(headline(report({}, {
      mn: { broken: true, broke_at: 30 }, bat: { broken: true, broke_at: 40 }, al8: { broken: true, broke_at: 50 },
    }))).toBe('Three regiments break');
  });

  it('two charges alike: the earlier leads; past ten breaks, figures', () => {
    expect(headline(report({ charges: [charge('al10', 'ma', 'home', 40), charge('al8', 'mn', 'home', 20)] })))
      .toBe("The 8th Alabama's charge carries the 1st Minnesota");
    const many = Array.from({ length: 11 }, (_, i) => `u${i}`);
    const r = report({ units: Object.fromEntries(many.map((uid) => [uid, unit({ broken: true, broke_at: 30 })])) });
    expect(headline(r, view({ unit: (uid) => ({ name: uid, side: 0, initialMorale: 100 }) }))).toBe('11 regiments break');
  });

  it('then a rally; else how many fell', () => {
    expect(headline(report({ rallies: [{ unit: 'al8', rallied: true, chance: 0.3 },
      { unit: 'mn', rallied: false, chance: 0.3 }] }))).toBe('The 8th Alabama rallies');
    expect(headline(report({}, { mn: { losses: 200 }, al8: { losses: 150 } }))).toBe('A hard round: 350 men fall');
    expect(headline(report({}, { mn: { losses: 20 } }))).toBe('A steady exchange of fire: 20 men fall');
    expect(headline(report())).toBe('A quiet round along the line');
  });

  it('a player counts only their own losses and breaks', () => {
    const player = view({ side: 0 });
    expect(headline(report({}, { al8: { broken: true, broke_at: 30, losses: 400 } }), player))
      .toBe('A quiet round along the line');
    expect(headline(report({}, { al8: { losses: 400 }, mn: { losses: 40 } }), player))
      .toBe('A steady exchange of fire: 40 men fall');
  });
});

describe('the summary', () => {
  it('tells up to three things in the order they happened', () => {
    const d = dispatch(report({
      charges: [charge('al8', 'mn', 'faltered', 24), charge('al10', 'ma', 'defender_broke', 40)],
      rallies: [{ unit: 'ross', rallied: true, chance: 0.4 }],
      flights: [{ unit: 'ma', distance: 412.4, escaped_from: [] }],
    }, { ma: { broken: true, broke_at: 40 }, bat: { broken: true, broke_at: 30 } }), null, view());
    expect(d.summary).toEqual([
      "Ross's Battery rallied.",
      'The 8th Alabama charged the 1st Minnesota and faltered under its fire, falling back.',
      'Battery B broke at 30 min.',
    ]);
  });

  it('each kind of charge, a break by itself, and a flight', () => {
    const say = (outcome: string) => dispatch(report({ charges: [charge('al8', 'mn', outcome)] }), null, view()).summary[0];
    expect(say('home')).toBe('The 8th Alabama charged the 1st Minnesota and went home.');
    expect(say('defender_broke')).toBe('The 8th Alabama charged the 1st Minnesota, which broke before the charge struck home.');
    expect(say('target_broke')).toBe('The 8th Alabama charged the 1st Minnesota, which broke before contact.');
    expect(say('meeting')).toBe('The 8th Alabama and the 1st Minnesota met head on.');
    expect(say('pursuit')).toBe('The 8th Alabama pursued the broken 1st Minnesota.');
    expect(say('charger_broke')).toBe('The 8th Alabama broke on the approach to the 1st Minnesota.');
    expect(say('escaped')).toBe('The 1st Minnesota fled too fast for the 8th Alabama to catch.');
    const fled = dispatch(report({ flights: [{ unit: 'mn', distance: 300, escaped_from: [] }] }), null, view());
    expect(fled.summary).toEqual(['The 1st Minnesota fled 300 yards.']);
    expect(dispatch(report(), null, view()).summary).toEqual(['No charge went in, and no regiment broke.']);
  });

  it('a unit broken by a charge is told with the charge, not twice', () => {
    const d = dispatch(report({ charges: [charge('al8', 'mn', 'defender_broke', 24)] },
      { mn: { broken: true, broke_at: 24 } }), null, view());
    expect(d.summary).toEqual(['The 8th Alabama charged the 1st Minnesota, which broke before the charge struck home.']);
  });
});

describe('the regiments, the charges and the enemy', () => {
  it('the admin sees both sides; a player only their own', () => {
    const r = report({}, { mn: { losses: 38, size: 862, morale: 82 }, bat: { broken: true, losses: 19, size: 53 } });
    const both = dispatch(r, null, view());
    expect(both.sides.map((s) => s.side)).toEqual([0, 1]);
    expect(both.sides[0].rows.slice(0, 1)).toEqual([
      { uid: 'mn', name: '1st Minnesota', lost: 38, left: 862, state: 'steady', morale: 0.82 }]);
    expect(both.sides[0].rows[2]).toMatchObject({ name: 'Battery B', state: 'broken', morale: null });
    expect(dispatch(r, null, view({ side: 1 })).sides.map((s) => s.side)).toEqual([1]);
  });

  it('the charges with their clock, and the span', () => {
    const d = dispatch(report({ start: 60, end: 120, charges: [charge('al8', 'mn', 'faltered', 84)] }), null, view());
    expect(d.charges).toEqual(['8th Alabama on 1st Minnesota: faltered at 84 min']);
    expect(d.span).toBe('60 min to 120 min');
    expect(d.round).toBe(1);
  });

  it('a player hears of prisoners, the enemy seen to break, and the enemy lost from sight', () => {
    const before = report({}, { al10: { broken: true } });
    const r = report({ round: 2, prisoners: { 0: 63, 1: 0 } },
      { al8: { broken: true }, al10: { broken: true }, ross: { broken: true } });
    const seen = new Set(['mn', 'ma', 'bat', 'al8', 'al10']);
    const d = dispatch(r, before, view({ side: 0, seenStart: () => true, seenEnd: (uid) => seen.has(uid) }));
    expect(d.enemy).toEqual(['Took about 60 prisoners.', 'The 8th Alabama was seen to break.',
      "Ross's Battery moved out of sight."]);
    expect(dispatch(r, null, view({ side: 1 })).enemy).toEqual([]);
    expect(dispatch(report({ prisoners: {} }), null, view({ side: 0 })).enemy).toEqual([]);
    expect(dispatch(r, null, view()).enemy).toEqual([]); // the admin has the full report instead
  });

  it('overruns and wipe-outs count only units that lost men or guns this round', () => {
    const d = dispatch(report({}, { mn: { size: 0, losses: 0, broken: true }, bat: { guns_lost: 1 } }), null, view());
    expect(d.summary).toEqual(['Battery B was overrun, losing 1 gun.']);
  });
});
