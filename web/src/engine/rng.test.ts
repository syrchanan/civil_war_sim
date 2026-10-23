import { describe, expect, it } from 'vitest';

import fixture from '../../../test_cases/parity/rng.json';
import { ValueError } from './errors';
import { Rng } from './rng';

describe('parity with the Python Rng', () => {
  it.each(fixture.cases)('seed $seed: state, u32, random, exponential and state after', (c) => {
    const rng = new Rng(c.seed);
    expect(rng.state).toEqual(c.state);
    expect(Array.from({ length: c.u32.length }, () => rng.nextU32())).toEqual(c.u32);
    expect(Array.from({ length: c.random.length }, () => rng.random())).toEqual(c.random);
    const rate = c.exponential.rate;
    expect(Array.from({ length: c.exponential.values.length }, () => rng.exponential(rate)))
      .toEqual(c.exponential.values);
    expect(rng.state).toEqual(c.state_after);
  });
});

describe('xoshiro128**', () => {
  it('matches the published reference vector', () => {
    const rng = Rng.fromState([1, 2, 3, 4]);
    expect(Array.from({ length: 5 }, () => rng.nextU32())).toEqual([11520, 0, 5927040, 70819200, 2031721883]);
  });

  it('draws in [0, 1) and in uint32 range', () => {
    const rng = new Rng(9);
    for (let i = 0; i < 1000; i++) {
      const u = rng.nextU32();
      expect(Number.isInteger(u) && u >= 0 && u < 2 ** 32).toBe(true);
      const r = rng.random();
      expect(r >= 0 && r < 1).toBe(true);
    }
  });
});

describe('seeds', () => {
  it.each([0, 1, 2 ** 32 - 1])('accepts %s', (seed) => {
    expect(new Rng(seed).seed).toBe(seed);
  });

  it.each([-1, 2 ** 32])('rejects %s as out of range', (seed) => {
    expect(() => new Rng(seed)).toThrow(ValueError);
  });

  it.each([1.5, NaN, '42', null, true])('rejects %s as not an integer', (seed) => {
    expect(() => new Rng(seed as number)).toThrow(TypeError);
  });
});

describe('state', () => {
  it('round-trips and resumes the sequence', () => {
    const rng = new Rng(5);
    for (let i = 0; i < 10; i++) rng.nextU32();
    const resumed = Rng.fromState(rng.state);
    expect(resumed.seed).toBeNull();
    expect(Array.from({ length: 20 }, () => resumed.nextU32())).toEqual(Array.from({ length: 20 }, () => rng.nextU32()));
  });

  it('is a copy', () => {
    const rng = new Rng(5);
    const state = rng.state;
    state[0] = 0;
    expect(rng.state[0]).not.toBe(0);
  });

  it.each([[[0, 0, 0, 0]], [[1, 2, 3]], [[1, 2, 3, 2 ** 32]], [[1, 2, 3, -1]], [[1, 2, 3, 1.5]]])(
    'rejects %j', (state) => {
      expect(() => Rng.fromState(state)).toThrow(ValueError);
    });
});

describe('exponential', () => {
  it.each([0, -1, Infinity, NaN])('rejects rate %s', (rate) => {
    expect(() => new Rng(1).exponential(rate)).toThrow(ValueError);
  });
});
