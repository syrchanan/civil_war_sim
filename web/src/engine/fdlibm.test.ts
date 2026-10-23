import { describe, expect, it } from 'vitest';

import fixture from '../../../test_cases/parity/fdlibm.json';
import { exp, log } from './fdlibm';

// rows: [x, expected] or [x, expected, note]
const rows = (key: 'log' | 'exp') => (fixture[key] as unknown[][]).map((r) => [r[0], r[1]] as [number, number]);

describe('log', () => {
  it.each(rows('log'))('log(%s) matches V8 bit for bit', (x, expected) => {
    expect(Object.is(log(x), expected)).toBe(true);
  });

  it('handles zero, negatives, infinity and NaN', () => {
    expect(log(0)).toBe(-Infinity);
    expect(log(-1)).toBeNaN();
    expect(log(Infinity)).toBe(Infinity);
    expect(log(NaN)).toBeNaN();
  });
});

describe('exp', () => {
  it.each(rows('exp'))('exp(%s) matches V8 bit for bit', (x, expected) => {
    expect(Object.is(exp(x), expected)).toBe(true);
  });

  it('handles overflow, infinities and NaN', () => {
    expect(exp(709.8)).toBe(Infinity);
    expect(exp(Infinity)).toBe(Infinity);
    expect(exp(-Infinity)).toBe(0);
    expect(exp(NaN)).toBeNaN();
  });
});

describe('against V8 itself', () => {
  // Node runs on V8, whose Math.log / Math.exp are fdlibm: the ports must agree on any input
  const inputs = (n: number, scale: (u: number) => number) => {
    let s = 12345;
    return Array.from({ length: n }, () => {
      s = (Math.imul(s, 1103515245) + 12345) >>> 0;
      return scale(s / 2 ** 32);
    });
  };

  it('log matches Math.log on 100k inputs across magnitudes', () => {
    const xs = inputs(100_000, (u) => Math.pow(10, u * 600 - 300));
    expect(xs.filter((x) => !Object.is(log(x), Math.log(x)))).toEqual([]);
  });

  it('exp matches Math.exp on 100k inputs over its whole range', () => {
    const xs = inputs(100_000, (u) => u * 1490 - 745);
    expect(xs.filter((x) => !Object.is(exp(x), Math.exp(x)))).toEqual([]);
  });
});
