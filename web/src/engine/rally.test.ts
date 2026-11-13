import { describe, expect, it } from 'vitest';

import { Battle, type Engagement, makeOrder, type OrderInput } from './battle';
import { ValueError } from './errors';
import { BattleParams, type Overrides } from './params';
import { Rng } from './rng';
import { Regiment } from './units';

const CERTAIN: Overrides = { rally: { chance_min: 1.0, chance_max: 1.0, men_exponent: 0.0 } };
const NEVER: Overrides = { rally: { chance_min: 0.0, chance_max: 0.0 } };

const battle = (overrides: Overrides = {}, seed = 5) => new Battle({
  a: { side: 0, regiment: new Regiment(800, '5/5/0/0') },
  b: { side: 0, regiment: new Regiment(800, '5/5/0/0') },
  x: { side: 1, regiment: new Regiment(1000, '5/5/0/0') },
}, new Rng(seed), BattleParams.defaults().withOverrides(overrides));

/** Unit a broken, with 600 of its 800 men left. */
const broken = (overrides: Overrides = {}, seed = 5) => {
  const b = battle(overrides, seed);
  const a = b.units.get('a')!;
  a.morale.forceBreak();
  a.regiment.updateRawMorale(a.morale.morale);
  a.regiment.updateSize(600);
  return b;
};

const FIRE: Record<string, OrderInput> = { a: { target: 'x', mode: 'ranged' }, x: { target: 'a', mode: 'ranged' } };
const RALLY: Record<string, OrderInput> = { a: { mode: 'rally' } };
const rates = (arrows: Engagement[]) => Object.fromEntries(arrows.map((e) => [`${e.attacker} ${e.mode}`, e.rate]));

describe('rally orders', () => {
  it('have no target, ammo or on_break', () => {
    expect(makeOrder({ mode: 'rally' })).toEqual({ target: null, mode: 'rally', ammo: null, on_break: null });
    expect(() => makeOrder({ target: 'x', mode: 'rally' })).toThrow('A rally order has no target');
    expect(() => makeOrder({ mode: 'rally', ammo: 'canister' })).toThrow('ammo');
    expect(() => makeOrder({ mode: 'rally', on_break: 'keep' })).toThrow('A rally order has no on_break');
  });

  it('are only for broken units, while tries are left', () => {
    const b = battle();
    expect(() => b.resolveRound(30, RALLY)).toThrow("a isn't broken");
    const gone = battle();
    gone.units.get('a')!.regiment.updateSize(0);
    gone.units.get('a')!.morale.forceBreak();
    expect(() => gone.resolveRound(30, RALLY)).toThrow('a is wiped out');
    expect(gone.round).toBe(0);
    expect(() => broken().resolveRound(30, FIRE)).toThrow("a is broken or wiped out and can't act");
  });
});

describe('the rally roll', () => {
  it('that works puts the unit back in the fight with a small budget', () => {
    const b = broken(CERTAIN);
    const report = b.resolveRound(30, RALLY);
    const a = b.units.get('a')!;
    expect(report.rallies).toEqual([{ unit: 'a', rallied: true, chance: 1 }]);
    expect(a.active && a.rallied && a.rallyAttempts === 1).toBe(true);
    expect(a.morale.resolve).toBeCloseTo(0.3, 12);
    expect(report.units.a.broken).toBe(false);
    expect(report.orders.a).toEqual({ target: null, mode: 'rally', ammo: null, on_break: null });
    expect(() => b.resolveRound(30, FIRE)).not.toThrow();
  });

  it('that fails leaves the unit broken and uses its try', () => {
    const b = broken(NEVER);
    expect(b.resolveRound(30, RALLY).rallies).toEqual([{ unit: 'a', rallied: false, chance: 0 }]);
    expect(b.units.get('a')!.morale.broken).toBe(true);
    expect(() => b.resolveRound(30, RALLY)).toThrow('a has no rally attempts left');
  });

  it('allows more tries when the params say so, but only one rally', () => {
    const b = new Battle({
      a: { side: 0, regiment: new Regiment(800, '5/5/0/0') },
      x: { side: 1, regiment: new Regiment(1000, '5/5/0/0') },
    }, new Rng(5), BattleParams.defaults().withOverrides({ rally: { ...CERTAIN.rally, attempts: 3 } }));
    b.units.get('a')!.morale.forceBreak();
    expect(b.resolveRound(30, RALLY).rallies[0].rallied).toBe(true);
    b.units.get('a')!.morale.forceBreak();
    expect(() => b.resolveRound(30, RALLY)).toThrow('a has already rallied once');
  });

  it('is one draw per rally, in unit order, at the start of the round, on the starting stats', () => {
    const b = broken({}, 11);
    b.units.get('b')!.morale.forceBreak();
    b.units.get('b')!.regiment.updateRawMorale(0);
    expect(b.units.get('a')!.regiment.stats[1]).toBe(1);
    const rng = Rng.fromState(b.rng.state);
    const draws = [rng.random(), rng.random()];
    const report = b.resolveRound(30, { b: { mode: 'rally' }, a: { mode: 'rally' } });
    const chance = b.params.rally.chance(5, 5, 600 / 800);
    expect(report.rallies.map((r) => r.unit)).toEqual(['a', 'b']);
    expect(report.rallies.map((r) => r.rallied)).toEqual([draws[0] < chance, draws[1] < b.params.rally.chance(5, 5, 1)]);
    expect(report.rallies[0].chance).toBe(chance);
  });
});

describe('a rallied unit', () => {
  it('hits less hard and is hit harder', () => {
    const plain = battle();
    const rallied = broken(CERTAIN);
    rallied.resolveRound(30, RALLY);
    const a = rallied.units.get('a')!;
    a.regiment.updateSize(800);
    a.morale.resolve = 1;
    a.regiment.updateRawMorale(a.morale.morale);
    const [before, after] = [rates(plain.engagements(FIRE)), rates(rallied.engagements(FIRE))];
    expect(after['a ranged']).toBeCloseTo(before['a ranged'] * 0.75, 12);
    expect(after['x ranged']).toBeCloseTo(before['x ranged'] * 1.25, 12);
  });

  it('can break again and is routed again', () => {
    const b = broken(CERTAIN);
    b.resolveRound(30, RALLY);
    const report = b.resolveRound(600, FIRE);
    expect(report.units.a.broken).toBe(true);
    expect(report.units.a.captured).toBeGreaterThan(0);
  });

  it('round-trips through the state file; older files have no rallies', () => {
    const b = broken(CERTAIN);
    b.resolveRound(30, RALLY);
    const data = b.toDict();
    expect(data.units[0].rally).toEqual({ attempts: 1, rallied: true });
    expect(data.history[0].rallies).toEqual([{ unit: 'a', rallied: true, chance: 1 }]);
    const loaded = Battle.fromDict(structuredClone(data));
    expect(loaded.units.get('a')!.rallied).toBe(true);
    expect(loaded.engagements(FIRE)).toEqual(b.engagements(FIRE));
    const old = structuredClone(data);
    for (const u of old.units) delete (u as Partial<typeof u>).rally;
    delete (old.history[0] as Partial<(typeof old.history)[0]>).rallies;
    const reloaded = Battle.fromDict(old);
    expect(reloaded.units.get('a')!.rallyAttempts).toBe(0);
    expect(reloaded.units.get('a')!.rallied).toBe(false);
    expect(reloaded.history[0].rallies).toEqual([]);
  });

  it('error types match the Python engine', () => {
    expect(() => battle().resolveRound(30, RALLY)).toThrow(ValueError);
  });
});
