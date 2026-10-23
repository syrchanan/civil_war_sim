import { describe, expect, it } from 'vitest';

import fixture from '../../../test_cases/parity/morale.json';
import { ValueError } from './errors';
import { breakFraction, breakScale, MoraleState } from './morale';
import { BattleParams, type Overrides } from './params';

const base = BattleParams.defaults();
const curve = base.withOverrides({ morale: { break_curve: 0.7, experience_weight: 0.2 } }).morale;

describe('breakFraction', () => {
  it.each(fixture.break_fraction as (number | string)[][])('(%s, %s) = %s %s', (xp, m, expected, which) => {
    const params = which === 'curve' ? curve : base.morale;
    expect(breakFraction(xp as number, m as number, params)).toBe(expected);
  });
});

describe('breakScale', () => {
  it.each(fixture.break_scale)('(%s, %s) = %s', (u, spread, expected) => {
    expect(breakScale(u, spread)).toBe(expected);
  });
});

type Op = [string, ...(number | boolean)[]];

describe('MoraleState replays the Python runs', () => {
  it.each(fixture.cases)('$size men, $xp/$morale_stat, scale $break_scale', (c) => {
    const params = base.withOverrides({ morale: c.overrides } as Overrides).morale;
    const state = new MoraleState(c.size, c.xp, c.morale_stat, params, c.break_scale);
    expect(state.breakFraction).toBe(c.break_fraction);
    (c.ops as Op[]).forEach((op, i) => {
      const [name, ...args] = op;
      if (name === 'take_loss') state.takeLoss(args[0] as boolean);
      else if (name === 'advance') state.advance(args[0] as number, args[1] as boolean);
      else if (name === 'inflict_loss') state.inflictLoss(args[0] as number);
      else if (name === 'shake') state.shake(args[0] as number);
      else if (name === 'force_break') state.forceBreak();
      else throw new Error(`unknown op ${name}`);
      expect([state.resolve, state.shock, state.lost, state.broken, state.morale], `after op ${i} ${name}`)
        .toEqual(c.after[i]);
    });
  });
});

describe('MoraleState', () => {
  it('starts fresh', () => {
    const s = new MoraleState(500, 5, 6, base.morale);
    expect([s.resolve, s.shock, s.lost, s.broken, s.morale, s.initialMorale]).toEqual([1, 0, 0, false, 60, 60]);
  });

  it('defaults to the config params and an unscaled break point', () => {
    const s = new MoraleState(500, 5, 6);
    expect(s.params).toBe(base.morale);
    expect(s.breakScale).toBe(1.0);
  });

  it('rejects a non-positive size and negative time', () => {
    expect(() => new MoraleState(0, 5, 5)).toThrow(ValueError);
    expect(() => new MoraleState(10, 5, 5).advance(-1, true)).toThrow(ValueError);
  });
});
