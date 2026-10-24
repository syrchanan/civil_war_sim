import { describe, expect, it } from 'vitest';

import battles from '../../../test_cases/parity/battles.json';
import { Battle } from './battle';
import { estimateRound, quantile } from './estimate';
import type { StateData } from './state';

const ridge = () => Battle.fromDict(structuredClone(
  battles.cases.find((c) => c.name === 'example_ridge')!.start as unknown as StateData));

const ORDERS = {
  us_1mn: { target: 'cs_8al', mode: 'ranged' },
  cs_8al: { target: 'us_1mn', mode: 'melee' },
  us_bat: { target: 'cs_11al', mode: 'ranged', ammo: 'canister' },
  cs_10al: { target: 'us_15ma', mode: 'ranged' },
};

describe('quantile (nearest rank)', () => {
  it.each([[0.1, 1], [0.5, 5], [0.9, 9], [0, 1], [1, 10]])('%s of 1..10 is %s', (q, v) => {
    expect(quantile([10, 3, 1, 2, 9, 4, 8, 5, 7, 6], q)).toBe(v);
  });
});

describe('estimateRound', () => {
  it('runs the round many times without touching the battle', () => {
    const b = ridge();
    const before = b.toDict();
    const est = estimateRound(b, ORDERS, 60, 50);
    expect(est.runs).toBe(50);
    expect(b.toDict()).toEqual(before);
  });

  it('per unit: losses and men left (p10 / p50 / p90) and the chance to break', () => {
    const est = estimateRound(ridge(), ORDERS, 60, 100);
    const mn = est.units.us_1mn;
    expect(mn.losses.p10).toBeLessThanOrEqual(mn.losses.p50);
    expect(mn.losses.p50).toBeLessThanOrEqual(mn.losses.p90);
    // men left can't exceed the start, nor fall below the worst losses and prisoners combined
    expect(mn.size.p90).toBeLessThanOrEqual(900);
    expect(mn.size.p10).toBeGreaterThanOrEqual(900 - mn.losses.p90 - mn.captured.p90);
    expect(mn.breakChance).toBeGreaterThanOrEqual(0);
    expect(mn.breakChance).toBeLessThanOrEqual(1);
    expect(est.units.cs_11al.losses.p90).toBeGreaterThan(0);          // under canister
    expect(est.units.cs_bat).toMatchObject({ losses: { p10: 0, p50: 0, p90: 0 }, breakChance: 0 }); // nobody fires on it
  });

  it('per charge: how often it goes home, falters, or breaks the defender first', () => {
    const est = estimateRound(ridge(), ORDERS, 60, 100);
    const charge = est.charges[0];
    expect([charge.charger, charge.target]).toEqual(['cs_8al', 'us_1mn']);
    const total = Object.values(charge.outcomes).reduce((s, p) => s + p, 0);
    expect(total).toBeCloseTo(1, 10);
  });

  it('is the same every time for the same battle and orders', () => {
    expect(estimateRound(ridge(), ORDERS, 60, 30)).toEqual(estimateRound(ridge(), ORDERS, 60, 30));
  });

  it('differs from run to run of the dice, so ranges are real', () => {
    const est = estimateRound(ridge(), ORDERS, 60, 100);
    expect(est.units.us_15ma.losses.p90).toBeGreaterThan(est.units.us_15ma.losses.p10);
  });
});
