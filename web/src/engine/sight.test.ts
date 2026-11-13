import { describe, expect, it } from 'vitest';

import { Battle, type Engagement, type OrderInput } from './battle';
import defaults from './defaults.json';
import { ValueError } from './errors';
import { SightParams, type SightData } from './params';
import { Rng } from './rng';
import { Terrain } from './terrain';
import { CavalryRegiment, type Position, Regiment } from './units';

const at = (x: number, y: number): Position => ({ x, y, z: 0, cover: 0, terrain_type: 'open', facing: null });

/** A strip 400 yards long and 50 deep: flat and open unless told otherwise, by column. */
const field = (height: (c: number) => number = () => 0, ground: (c: number) => string = () => 'o') => {
  const columns = 40;
  const rows = 5;
  const heights: number[] = [];
  let g = '';
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < columns; c++) {
      heights.push(height(c));
      g += ground(c);
    }
  }
  return new Terrain({ cell: 10, columns, rows, heights, ground: g, meta: {} });
};

const battle = (terrain: Terrain | null, ax = 50, xx = 250, a: Regiment = new Regiment(1000, '5/5/0/0')) => {
  const b = new Battle({ a: { side: 0, regiment: a }, x: { side: 1, regiment: new Regiment(1000, '5/5/1/0') } },
    new Rng(3), undefined, undefined, {}, terrain);
  b.units.get('a')!.regiment.position = at(ax, 25);
  b.units.get('x')!.regiment.position = at(xx, 25);
  return b;
};

const FIRE: Record<string, OrderInput> = { a: { target: 'x', mode: 'ranged' }, x: { target: 'a', mode: 'ranged' } };
const rates = (b: Battle, orders = FIRE) =>
  Object.fromEntries(b.engagements(orders).map((e: Engagement) => [`${e.attacker} ${e.mode}`, e.rate]));

describe('line of sight', () => {
  const ridge = field((c) => (c >= 14 && c <= 16 ? 20 : 0));

  it('a ridge blocks fire both ways; a fold lower than eye height does not', () => {
    const b = battle(ridge);
    expect([b.lineOfSight('a', 'x'), b.lineOfSight('x', 'a')]).toEqual([false, false]);
    expect(rates(b)).toEqual({});
    expect(battle(field((c) => (c >= 14 && c <= 16 ? 1 : 0))).lineOfSight('a', 'x')).toBe(true);
  });

  it('woods between hide; a unit at a wood edge sees out', () => {
    expect(battle(field(undefined, (c) => (c >= 14 && c <= 18 ? 'f' : 'o'))).lineOfSight('a', 'x')).toBe(false);
    expect(battle(field(undefined, (c) => (c >= 22 ? 'f' : 'o')), 50, 245).lineOfSight('a', 'x')).toBe(true);
    expect(battle(field(undefined, (c) => (c >= 18 ? 'f' : 'o')), 50, 245).lineOfSight('a', 'x')).toBe(false);
  });

  it('riders see over a bank that hides men on foot; closing fire ignores sight', () => {
    const bank = field((c) => (c >= 14 && c <= 16 ? 2.2 : 0));
    expect(battle(bank).lineOfSight('a', 'x')).toBe(false);
    expect(battle(bank, 50, 250, new CavalryRegiment(300, '5/5/0/0', 'light')).lineOfSight('a', 'x')).toBe(true);
    const charge = battle(ridge, 50, 250, new CavalryRegiment(300, '5/5/0/1', 'light'));
    expect(rates(charge, { a: { target: 'x', mode: 'melee' }, x: { target: 'a', mode: 'ranged' } })['x closing'])
      .toBeGreaterThan(0);
  });

  it('never blocked without terrain or positions', () => {
    expect(battle(null).lineOfSight('a', 'x')).toBe(true);
    const b = battle(ridge);
    b.units.get('x')!.regiment.position = null;
    expect(b.lineOfSight('a', 'x')).toBe(true);
    expect(b.elevationBonus('a', 'x')).toBe(0);
  });
});

describe('elevation', () => {
  it('fire from higher ground tells more, uphill less, up to the limit', () => {
    const p = new SightParams(defaults.params.sight as SightData);
    const slope = field((c) => Math.max(0, 20 - c));
    const b = battle(slope, 55, 255);
    expect(b.elevationBonus('a', 'x')).toBe(p.bonus(slope.heightAt(55, 25) - slope.heightAt(255, 25)));
    expect(b.elevationBonus('x', 'a')).toBe(-b.elevationBonus('a', 'x'));
    const flat = rates(battle(field(), 55, 255));
    expect(rates(b)['a ranged']).toBeCloseTo(flat['a ranged'] * (1 + b.elevationBonus('a', 'x')), 12);
    expect(battle(field((c) => (c <= 10 ? 100 : 0)), 55, 255).elevationBonus('a', 'x')).toBe(p.elevation_max);
    expect(battle(null).elevationBonus('a', 'x')).toBe(0);
  });
});

describe('SightParams', () => {
  const data = defaults.params.sight as SightData;

  it('keeps the defaults', () => {
    expect(new SightParams(data).toDict()).toEqual(data);
  });

  it.each([
    { eye_height: { inf: -1, cav: 3, art: 2 } }, { eye_height: { inf: 2 } }, { forest_height: -1 }, { sample_step: 0 },
    { edge_clear: -1 }, { elevation_scale: 0 }, { elevation_max: 1.5 },
  ])('rejects %j', (change) => {
    expect(() => new SightParams({ ...data, ...change } as SightData)).toThrow(ValueError);
  });
});
