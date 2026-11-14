import { describe, expect, it } from 'vitest';

import { Battle } from './battle';
import defaults from './defaults.json';
import { ValueError } from './errors';
import { BattleParams, FlightParams, type FlightData, type Overrides } from './params';
import { Rng } from './rng';
import { CavalryRegiment, type Position, Regiment } from './units';

const at = (x: number, y: number, facing: number | null = null): Position =>
  ({ x, y, z: 0, cover: 0, terrain_type: 'open', facing });

const battle = (units: Record<string, [number, Regiment, Position | null]>, overrides: Overrides = {}) => {
  const b = new Battle(Object.fromEntries(Object.entries(units).map(([uid, [side, regiment]]) => [uid, { side, regiment }])),
    new Rng(3), BattleParams.defaults().withOverrides(overrides));
  for (const [uid, [, , place]] of Object.entries(units)) b.units.get(uid)!.regiment.position = place;
  return b;
};

const broken = (b: Battle, uid: string, time = b.time) => {
  const u = b.units.get(uid)!;
  u.morale.forceBreak();
  u.brokeTime = time;
  u.regiment.updateRawMorale(0);
};

describe('FlightParams', () => {
  const data = defaults.params.flight as FlightData;
  const p = new FlightParams(data);

  it('keeps the defaults; the distance fled is the integral of a halving speed', () => {
    expect(p.toDict()).toEqual(data);
    const { inf } = p.speed;
    expect(p.fled('inf', 0, p.half_life)).toBeCloseTo((inf * p.half_life / Math.LN2) * 0.5, 9);
    expect(p.speedAt('inf', p.half_life)).toBeCloseTo(inf / 2, 12);
  });

  it.each([
    { speed: { inf: -1, cav: 1, art: 1 } }, { speed: { inf: 1 } }, { half_life: 0 }, { step_minutes: 0 },
    { safe_distance: -1 }, { field: { width: 0, height: 10 } }, { field: { width: 10 } },
  ])('rejects %j', (change) => {
    expect(() => new FlightParams({ ...data, ...change } as FlightData)).toThrow(ValueError);
  });
});

describe('flight', () => {
  const inf = () => new Regiment(500, '5/5/0/0');

  it('a broken unit flees directly away from the nearest standing enemy, round after round, ever slower', () => {
    const b = battle({ a: [0, inf(), at(100, 600)], x: [1, inf(), at(50, 600)] }, { flight: { safe_distance: 5000 } });
    broken(b, 'a');
    const first = b.resolveRound(15, {}).flights[0];
    const second = b.resolveRound(15, {}).flights[0];
    expect(first.unit).toBe('a');
    expect(second.distance).toBeCloseTo(first.distance / 2, 9);
    expect(b.units.get('a')!.regiment.position!.x).toBeCloseTo(100 + first.distance + second.distance, 9);
  });

  it('stops when safe, at the field edge, with no enemy standing, and never without a position', () => {
    const safe = battle({ a: [0, inf(), at(1000, 600)], x: [1, inf(), at(1000, 0)] }, { flight: { safe_distance: 500 } });
    broken(safe, 'a');
    expect(safe.resolveRound(30, {}).flights).toEqual([]);
    const edge = battle({ a: [0, new CavalryRegiment(300, '5/5/0/0', 'light'), at(1000, 1150)], x: [1, inf(), at(1000, 1000)] });
    broken(edge, 'a');
    edge.resolveRound(30, {});
    expect(edge.units.get('a')!.regiment.position!.y).toBe(1200);
    const alone = battle({ a: [0, inf(), at(1000, 600)], x: [1, inf(), at(1000, 400)] });
    broken(alone, 'a');
    broken(alone, 'x');
    expect(alone.resolveRound(10, {}).flights).toEqual([]);
    const unplaced = battle({ a: [0, inf(), null], x: [1, inf(), null] });
    broken(unplaced, 'a');
    expect(unplaced.resolveRound(10, {}).flights).toEqual([]);
  });

  it('on the same spot as the enemy it falls back towards its own side', () => {
    const b = battle({ a: [0, inf(), at(1000, 600)], b: [1, inf(), at(1000, 600)] });
    broken(b, 'b');
    b.resolveRound(5, {});
    expect(b.units.get('b')!.regiment.position!.y).toBeLessThan(600);
    const c = battle({ a: [0, inf(), at(1000, 600)], b: [1, inf(), at(1000, 600)] });
    broken(c, 'a');
    c.resolveRound(5, {});
    expect(c.units.get('a')!.regiment.position!.y).toBeGreaterThan(600);
  });

  it('pursuers: a fast one keeps up and moves along, a slow one loses contact, a slow pursuit charge never connects', () => {
    const fast = battle({ a: [0, inf(), at(1000, 600)], x: [1, new CavalryRegiment(400, '6/6/0/1', 'heavy'), at(1000, 580)] });
    broken(fast, 'a');
    const r = fast.resolveRound(10, { x: { target: 'a', mode: 'melee', on_break: 'pursue' } });
    expect(r.charges[0].outcome).toBe('pursuit');
    expect(fast.units.get('a')!.regiment.position!.y - fast.units.get('x')!.regiment.position!.y).toBeCloseTo(20, 9);
    const slow = battle({ a: [0, new CavalryRegiment(300, '5/5/0/0', 'light'), at(1000, 600)], x: [1, inf(), at(1000, 580)] });
    broken(slow, 'a');
    slow.contacts = new Set(['a\u0000x']);
    expect(slow.resolveRound(10, { x: { target: 'a', mode: 'melee', on_break: 'pursue' } }).flights[0].escaped_from)
      .toEqual(['x']);
    const two = battle({ a: [0, new CavalryRegiment(300, '5/5/0/0', 'light'), at(1000, 600)], x: [1, inf(), at(1000, 580)],
      y: [1, inf(), at(1020, 600)] });
    broken(two, 'a');
    two.contacts = new Set(['a\u0000x', 'a\u0000y']);
    const pursue = { target: 'a', mode: 'melee', on_break: 'pursue' };
    expect(two.resolveRound(5, { x: pursue, y: pursue }).flights[0].escaped_from).toEqual(['x', 'y']);
    const charge = battle({ a: [0, new CavalryRegiment(300, '5/5/0/0', 'light'), at(1000, 600)], x: [1, inf(), at(1000, 580)] });
    broken(charge, 'a');
    expect(charge.resolveRound(10, { x: { target: 'a', mode: 'melee' } }).charges[0].outcome).toBe('escaped');
  });

  it('a pursuer without a position keeps contact but stays put', () => {
    const b = battle({ a: [0, inf(), at(1000, 600)], x: [1, new CavalryRegiment(400, '6/6/0/1', 'heavy'), null],
      y: [1, inf(), at(1000, 500)] });
    broken(b, 'a');
    b.contacts = new Set(['a\u0000x']);
    b.resolveRound(5, { x: { target: 'a', mode: 'melee', on_break: 'pursue' } });
    expect(b.units.get('x')!.regiment.position).toBeNull();
  });

  it('break times and flights round-trip; older files have none; a rallied unit stops fleeing', () => {
    const b = battle({ a: [0, inf(), at(1000, 600)], x: [1, inf(), at(1000, 450)] });
    broken(b, 'a', 0);
    b.resolveRound(10, {});
    const data = b.toDict();
    expect(data.units[0].broke_time).toBe(0);
    expect(data.history[0].flights[0].escaped_from).toEqual([]);
    expect(Battle.fromDict(structuredClone(data)).resolveRound(10, {})).toEqual(b.resolveRound(10, {}));
    const old = structuredClone(data);
    for (const u of old.units) delete (u as Partial<typeof u>).broke_time;
    delete (old.history[0] as Partial<(typeof old.history)[0]>).flights;
    const loaded = Battle.fromDict(old);
    expect(loaded.units.get('a')!.brokeTime).toBeNull();
    expect(loaded.history[0].flights).toEqual([]);
    const rally = battle({ a: [0, inf(), at(1000, 600)], x: [1, inf(), at(1000, 450)] },
      { rally: { chance_min: 1, chance_max: 1, men_exponent: 0 } });
    broken(rally, 'a');
    expect(rally.resolveRound(10, { a: { mode: 'rally' } }).flights).toEqual([]);
    expect(rally.units.get('a')!.brokeTime).toBeNull();
  });
});
