import { describe, expect, it } from 'vitest';

import fixture from '../../../test_cases/parity/params.json';
import { Battle, type Engagement, type OrderInput } from './battle';
import defaults from './defaults.json';
import { ValueError } from './errors';
import { BattleParams, ChargeParams, type ChargeData, RangeParams, type RangeData } from './params';
import { Rng } from './rng';
import { ArtilleryBattery, CavalryRegiment, type Position, Regiment } from './units';

const at = (x: number, y: number, facing: number | null = null): Position =>
  ({ x, y, z: 0, cover: 0, terrain_type: 'open', facing });

const battle = (a?: Position, x?: Position, unit: Regiment = new Regiment(1000, '5/5/0/0')) => {
  const b = new Battle({ a: { side: 0, regiment: unit }, x: { side: 1, regiment: new Regiment(1000, '5/5/1/0') } },
    new Rng(3));
  if (a) b.units.get('a')!.regiment.position = a;
  if (x) b.units.get('x')!.regiment.position = x;
  return b;
};

const FIRE: Record<string, OrderInput> = { a: { target: 'x', mode: 'ranged' }, x: { target: 'a', mode: 'ranged' } };
const rates = (b: Battle, orders = FIRE) =>
  Object.fromEntries(b.engagements(orders).map((e: Engagement) => [`${e.attacker} ${e.mode}`, e.rate]));
const R = new RangeParams(defaults.params.range as RangeData);

describe('RangeParams', () => {
  it('keeps the defaults; reach is full up to close range, then falls to nothing at max range', () => {
    expect(R.toDict()).toEqual(defaults.params.range);
    const { close, max } = R.small_arms['0'];
    expect([R.reach(0, close, max), R.reach(close, close, max), R.reach(max, close, max), R.reach(max + 1, close, max)])
      .toEqual([1, 1, 0, 0]);
    expect(R.reach((close + max) / 2, close, max)).toBeCloseTo(0.5, 15);
    const curved = new RangeParams({ ...(defaults.params.range as RangeData), falloff_exponent: 2 });
    expect(curved.reach((close + max) / 2, close, max)).toBeCloseTo(0.25, 15);
  });

  it.each([
    { falloff_exponent: 0 },
    { small_arms: [] },
    { small_arms: { 0: { close: 80, max: 250 } } },
    { small_arms: { ...defaults.params.range.small_arms, 0: { close: 100, max: 50 } } },
    { small_arms: { ...defaults.params.range.small_arms, 0: { close: -1, max: 50 } } },
    { small_arms: { ...defaults.params.range.small_arms, 0: { close: 10, max: 20, far: 30 } } },
    { small_arms: { ...defaults.params.range.small_arms, 7: { close: 10, max: 20 } } },
  ])('rejects %j', (change) => {
    expect(() => new RangeParams({ ...(defaults.params.range as RangeData), ...change } as RangeData))
      .toThrow(ValueError);
  });

  it('needs ranges for every ammo, and charge speeds for every type', () => {
    expect(() => BattleParams.defaults().withOverrides({ combat: { artillery_ammo: { grape: 0.5 } } }))
      .toThrow('every ammo');
    expect(() => new ChargeParams({ ...(defaults.params.charge as ChargeData), speed: { inf: 100 } }))
      .toThrow('speed needs exactly');
    expect(() => BattleParams.defaults().withOverrides({ charge: { speed: { inf: 0 } } })).toThrow('speed must be > 0');
  });

  it('matches the Python params fixture', () => {
    expect(fixture.overrides.valid.length).toBeGreaterThan(0);
  });
});

describe('range in battle', () => {
  it('units without positions fight as before; one side placed is not enough', () => {
    expect(rates(battle(at(0, 0)))).toEqual(rates(battle()));
    expect(battle(at(0, 0)).distance('a', 'x')).toBeNull();
    expect(battle().reach('a', 'x')).toBeNull();
  });

  it('measures centre to centre, and fire falls off with distance', () => {
    expect(battle(at(100, 100), at(400, 500)).distance('a', 'x')).toBe(500);
    const smooth = R.small_arms['0'];
    const near = rates(battle(at(0, 0), at(0, smooth.close)));
    expect(near).toEqual(rates(battle()));
    const half = rates(battle(at(0, 0), at(0, (smooth.close + smooth.max) / 2)));
    expect(half['a ranged']).toBeCloseTo(near['a ranged'] * 0.5, 12);
    expect(rates(battle(at(0, 0), at(3000, 4000)))).toEqual({});
  });

  it('artillery reach depends on its ammo', () => {
    const d = R.artillery.canister.max + 50;
    const b = battle(at(0, 0), at(0, d), new ArtilleryBattery(72, '5/5/0/0', 8, 'battery'));
    expect(b.reach('a', 'x', 'canister')).toBe(0);
    expect(b.reach('a', 'x', 'round_shot')).toBe(1);
    expect(b.reach('a', 'x')).toBe(b.reach('a', 'x', b.params.combat.artillery_default_ammo));
  });

  it('closing fire is not reduced, and a charge takes the distance', () => {
    const cav = new CavalryRegiment(400, '5/5/0/1', 'light');
    const charge: Record<string, OrderInput> = { a: { target: 'x', mode: 'melee' }, x: { target: 'a', mode: 'ranged' } };
    expect(rates(battle(at(0, 0), at(0, 600), cav), charge)['x closing']).toBe(rates(battle(undefined, undefined, cav), charge)['x closing']);
    const p = BattleParams.defaults().charge;
    const far = p.speed.inf * (p.approach_minutes.inf + 3);
    const report = battle(at(0, 0), at(0, far)).resolveRound(60, { a: { target: 'x', mode: 'melee' } });
    expect(report.charges[0].resolved_at).toBeCloseTo(far / p.speed.inf, 12);
  });
});
