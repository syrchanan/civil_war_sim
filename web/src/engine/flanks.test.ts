import { describe, expect, it } from 'vitest';

import fixture from '../../../test_cases/parity/params.json';
import { Battle, type Engagement, type OrderInput } from './battle';
import defaults from './defaults.json';
import { ValueError } from './errors';
import { MoraleState } from './morale';
import { BattleParams, FlankParams, type FlankData } from './params';
import { Rng } from './rng';
import { cosDeg, sinDeg } from './trig';
import { CavalryRegiment, type Position, Regiment } from './units';

const at = (x: number, y: number, facing: number | null = null): Position =>
  ({ x, y, z: 0, cover: 0, terrain_type: 'open', facing });

describe('trig in degrees', () => {
  it.each(fixture.trig as [number, number, number][])('cosDeg / sinDeg(%s) match Python exactly', (d, c, s) => {
    expect(cosDeg(d)).toBe(c);
    expect(sinDeg(d)).toBe(s);
  });
});

const battle = (a?: Position, x?: Position, unitA?: Regiment, unitX?: Regiment) => {
  const b = new Battle({
    a: { side: 0, regiment: unitA ?? new Regiment(1000, '5/5/0/0') },
    x: { side: 1, regiment: unitX ?? new Regiment(1000, '5/5/0/0') },
  }, new Rng(3));
  if (a) b.units.get('a')!.regiment.position = a;
  if (x) b.units.get('x')!.regiment.position = x;
  return b;
};
const FIRE: Record<string, OrderInput> = { a: { target: 'x', mode: 'ranged' }, x: { target: 'a', mode: 'ranged' } };
const rates = (b: Battle, orders = FIRE) =>
  Object.fromEntries(b.engagements(orders).map((e: Engagement) => [`${e.attacker} ${e.mode}`, e.rate]));

describe('FlankParams', () => {
  const data = defaults.params.flanks as FlankData;

  it('keeps the defaults', () => {
    expect(new FlankParams(data).toDict()).toEqual(data);
  });

  it.each([
    { front_arc: 0 }, { front_arc: 400 }, { rear_arc: -1 }, { rear_arc: 360 }, { front_arc: 270, rear_arc: 120 },
    { casualties: { flank: -1, rear: 2 } }, { shock: { flank: 1, rear: -0.5 } },
    { charge_bonus: { flank: 1, rear: 2, side: 1 } }, { casualties: [] },
  ])('rejects %j', (change) => {
    expect(() => new FlankParams({ ...data, ...change } as FlankData)).toThrow(ValueError);
  });
});

describe('zones and arcs', () => {
  it.each([
    [[0, -100], 'front'], [[80, -100], 'front'], [[100, -50], 'flank'], [[100, 0], 'flank'], [[100, 90], 'flank'],
    [[50, 100], 'rear'], [[0, 100], 'rear'], [[-100, 0], 'flank'],
  ] as [[number, number], string][])('an attacker at %j is on the %s', ([x, y], zone) => {
    expect(battle(at(x, y), at(0, 0, 0)).zone('x', 'a')).toBe(zone);
  });

  it('needs both placed and a facing; the same spot is the front', () => {
    expect(battle(at(100, 0), at(0, 0)).zone('x', 'a')).toBeNull();
    expect(battle(undefined, at(0, 0, 0)).zone('x', 'a')).toBeNull();
    expect(battle(at(0, 0), at(0, 0, 0)).zone('x', 'a')).toBe('front');
    expect(battle(at(100, 0), at(0, 0, 90)).zone('x', 'a')).toBe('front');
  });

  it('a unit fires only within its front arc; flank and rear fire hits harder', () => {
    const b = battle(at(0, 0, 0), at(60, 0, 270));
    expect([b.inArc('a', 'x'), b.inArc('x', 'a')]).toEqual([false, true]);
    expect(rates(b)['a ranged']).toBeUndefined();
    const p = BattleParams.defaults().flanks;
    const front = rates(battle(at(0, -60, 180), at(0, 0, 0)))['a ranged'];
    expect(rates(battle(at(60, 0, 270), at(0, 0, 0)))['a ranged']).toBeCloseTo(front * p.casualties.flank, 12);
    expect(rates(battle(at(0, 60, 0), at(0, 0, 0)))['a ranged']).toBeCloseTo(front * p.casualties.rear, 12);
  });

  it('closing fire needs the charger in the front arc', () => {
    const charge: Record<string, OrderInput> = { a: { target: 'x', mode: 'melee' }, x: { target: 'a', mode: 'ranged' } };
    const cav = () => new CavalryRegiment(400, '5/5/0/1', 'light');
    expect(rates(battle(at(0, -200, 180), at(0, 0, 0), cav()), charge)['x closing']).toBeGreaterThan(0);
    expect(rates(battle(at(0, 200, 0), at(0, 0, 0), cav()), charge)['x closing']).toBeUndefined();
  });

  it('a loss from the flank costs more morale', () => {
    const [plain, shaken] = [new MoraleState(500, 5, 5), new MoraleState(500, 5, 5)];
    plain.takeLoss(true);
    shaken.takeLoss(true, 2.0);
    expect(1 - shaken.resolve).toBeCloseTo(2 * (1 - plain.resolve), 15);
  });
});
