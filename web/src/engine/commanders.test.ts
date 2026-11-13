import { describe, expect, it } from 'vitest';

import battles from '../../../test_cases/parity/battles.json';
import fixture from '../../../test_cases/parity/summaries.json';
import { expectedShare, general, ratings, resultShares, unitPower } from './commanders';
import defaults from './defaults.json';
import type { StateData } from './state';
import { sideSummary, verdicts } from './summary';
import { BattleParams } from './params';

const finals = battles.cases.map((c) => c.final as unknown as StateData);
const CFG = defaults.commanders;
const P = BattleParams.defaults().aftermath;

describe('verdicts', () => {
  it.each([
    [null, 'votes', [300, 100], [1000, 1000], ['draw', 'draw']],
    [0, 'admin', [100, 150], [1000, 1000], ['victory', 'defeat']],
    [0, 'votes', [100, 250], [1000, 1000], ['decisive victory', 'decisive defeat']],
    [1, 'votes', [500, 240], [2000, 1000], ['decisive defeat', 'decisive victory']],
    [0, 'votes', [100, 249], [1000, 1000], ['victory', 'defeat']],
    [0, 'votes', [200, 399], [1000, 1000], ['victory', 'defeat']],
    [0, 'army_out', [100, 120], [1000, 1000], ['decisive victory', 'decisive defeat']],
    [0, 'votes', [300, 300], [1000, 2000], ['Pyrrhic victory', 'defeat']],
    [1, 'army_out', [260, 400], [1000, 1000], ['defeat', 'Pyrrhic victory']],
    [0, 'votes', [299, 300], [1000, 2000], ['victory', 'defeat']],
    [0, 'votes', [249, 200], [1000, 2000], ['victory', 'defeat']],
  ] as const)('holder %s by %s, casualties %j of %j: %j', (holder, by, casualties, started, expected) => {
    expect(verdicts(holder, by, [...casualties], [...started], P)).toEqual(expected);
  });
});

describe('commander ratings match the Python engine', () => {
  it.each(fixture.cases.map((c, i) => [c.name, c.seed, i] as const))('%s, seed %s', (_name, _seed, i) => {
    const expected = fixture.cases[i].commanders;
    if (expected === null) expect(() => ratings(finals[i])).toThrow('finish');
    else expect(ratings(finals[i])).toEqual(expected);
  });
});

describe('commander rating parts', () => {
  it('expected share: even when both sides are equally strong or both have nothing', () => {
    expect(expectedShare(1, 1, 1.5)).toBe(0.5);
    expect(expectedShare(0, 0, 1.5)).toBe(0.5);
    expect(expectedShare(0, 3, 1.5)).toBe(0);
    expect(expectedShare(2, 1, 1)).toBeCloseTo(2 / 3, 15);
  });

  it('result shares: casualties (guns as men), field and routs; even with nothing to share', () => {
    const side = { casualties: 0, guns_taken: 0, units_out_men: 0, started: 1000 };
    expect(resultShares([side, side], null, CFG)).toEqual([0.5, 0.5]);
    const got = resultShares([{ ...side, casualties: 100 }, { ...side, casualties: 300, units_out_men: 500 }], 0, CFG);
    expect(got[0]).toBeCloseTo(CFG.weights.casualties * 0.75 + CFG.weights.field + CFG.weights.routs, 15);
    expect(got[0] + got[1]).toBeCloseTo(1, 15);
  });

  it('the ladder: a score gets the last general it reaches, the first one below that', () => {
    const ladder = [{ name: 'Low', battle: 'x', from: -1 }, { name: 'Mid', battle: 'y', from: 0 },
      { name: 'High', battle: 'z', from: 0.3 }];
    expect([-0.5, 0, 0.29, 0.3, 0.9].map((s) => general(s, ladder).name)).toEqual(['Low', 'Mid', 'Mid', 'High', 'High']);
    expect(general(-5, ladder).name).toBe('Low');
    expect(CFG.ladder[0].from).toBe(-1);
  });
});

describe('older and generic cases', () => {
  it('a generic melee-only unit counts as infantry', () => {
    const u = { ...finals[0].units[0], type: null, subtype: null, initial_stats: '5/5/0/1' };
    expect(unitPower(u, BattleParams.defaults())).toBe(unitPower({ ...u, type: 'inf' }, BattleParams.defaults()));
  });

  it('a result saved before the field votes reads as decided by the admin', () => {
    const i = fixture.cases.findIndex((c) => c.side_summary !== null);
    const old = structuredClone(finals[i]);
    delete (old.result as Partial<NonNullable<StateData['result']>>).field_decided_by;
    expect(sideSummary(old).map((s) => s.verdict)).toEqual(
      verdicts(old.result!.field_held_by, 'admin', sideSummary(old).map((s) => s.casualties),
        sideSummary(old).map((s) => s.started), P));
  });
});
