import { describe, expect, it } from 'vitest';

import { Battle, type Engagement, type OrderInput } from './battle';
import { ValueError } from './errors';
import { estimateRound } from './estimate';
import { Rng } from './rng';
import { CavalryRegiment, Regiment } from './units';

const battle = (seed = 3) => new Battle({
  a: { side: 0, regiment: new Regiment(1000, '5/5/0/0') },
  b: { side: 0, regiment: new CavalryRegiment(400, '5/5/0/0', 'light') },
  x: { side: 1, regiment: new Regiment(1000, '5/5/0/0') },
}, new Rng(seed));

const FIRE: Record<string, OrderInput> = { a: { target: 'x', mode: 'ranged' }, x: { target: 'a', mode: 'ranged' } };
const rates = (arrows: Engagement[]) => Object.fromEntries(arrows.map((e) => [`${e.attacker} ${e.mode}`, e.rate]));

describe('admin modifiers (one round)', () => {
  it('fire scales the casualties a unit inflicts by fire, closing fire included', () => {
    const b = battle();
    const plain = rates(b.engagements(FIRE));
    const modified = rates(b.engagements(FIRE, { a: { fire: -0.25 } }));
    expect(modified['a ranged']).toBeCloseTo(plain['a ranged'] * 0.75, 12);
    expect(modified['x ranged']).toBe(plain['x ranged']);
    const charge: Record<string, OrderInput> = { b: { target: 'x', mode: 'melee' }, x: { target: 'b', mode: 'ranged' } };
    expect(rates(b.engagements(charge, { x: { fire: 0.2 } }))['x closing'])
      .toBeCloseTo(rates(b.engagements(charge))['x closing'] * 1.2, 12);
  });

  it('melee scales melee', () => {
    const b = battle();
    b.contacts = new Set(['a\u0000x']);
    const melee: Record<string, OrderInput> = { a: { target: 'x', mode: 'melee' }, x: { target: 'a', mode: 'melee' } };
    expect(rates(b.engagements(melee, { a: { melee: 0.5, fire: -1 } }))['a melee'])
      .toBeCloseTo(rates(b.engagements(melee))['a melee'] * 1.5, 12);
  });

  it('morale scales what the unit spends; +100% spends nothing', () => {
    const [plain, steadier, shakier] = [battle(), battle(), battle()];
    plain.resolveRound(60, FIRE);
    steadier.resolveRound(60, FIRE, false, { x: { morale: 0.5 } });
    shakier.resolveRound(60, FIRE, false, { x: { morale: -0.5 } });
    const resolve = (b: Battle) => b.units.get('x')!.morale.resolve;
    expect(resolve(shakier)).toBeLessThan(resolve(plain));
    expect(resolve(plain)).toBeLessThan(resolve(steadier));
    const firm = battle();
    firm.resolveRound(600, FIRE, false, { x: { morale: 1 } });
    expect(firm.units.get('x')!.morale.resolve).toBe(1);
  });

  it('last one round, are recorded in it, and round-trip (absent in older files)', () => {
    const b = battle();
    const first = b.resolveRound(30, FIRE, false, { a: { fire: -0.15, note: 'uphill' } });
    expect(first.modifiers).toEqual({ a: { fire: -0.15, melee: 0, morale: 0, note: 'uphill' } });
    expect(b.units.get('a')!.morale.spendFactor).toBe(1);
    expect(b.resolveRound(30, FIRE).modifiers).toEqual({});
    const data = b.toDict();
    expect(Battle.fromDict(data).toDict()).toEqual(data);
    delete (data.history[0] as { modifiers?: unknown }).modifiers;
    expect(Battle.fromDict(data).history[0].modifiers).toEqual({});
  });

  it('zero modifiers change nothing', () => {
    const [plain, zero] = [battle(), battle()];
    plain.resolveRound(60, FIRE);
    zero.resolveRound(60, FIRE, false, { a: { fire: 0, melee: 0, morale: 0 } });
    expect(zero.toDict().units).toEqual(plain.toDict().units);
  });

  it.each([
    [{ nobody: { fire: 0.1 } }, 'Unknown unit nobody'],
    [{ a: { range: 0.1 } }, 'Unknown modifier'],
    [{ a: { fire: -1.5 } }, 'between -1 and 1'],
    [{ a: { morale: 'x' } }, 'number'],
    [{ a: { fire: Number.NaN } }, 'between -1 and 1'],
    [{ a: { note: 3 } }, 'note'],
    [{ a: 0.1 }, 'mapping'],
    [{ a: null }, 'mapping'],
    [['a'], 'mapping of unit id'],
    [null, 'mapping of unit id'],
  ])('refuses bad modifiers before anything happens: %j', (modifiers, message) => {
    const b = battle();
    const bad = modifiers as unknown as Record<string, never>;
    expect(() => b.resolveRound(30, FIRE, false, bad)).toThrow(ValueError);
    expect(() => b.resolveRound(30, FIRE, false, bad)).toThrow(message);
    expect(b.round).toBe(0);
    expect(() => b.engagements(FIRE, bad)).toThrow(message);
  });

  it('the estimate takes them too', () => {
    const b = battle();
    const plain = estimateRound(b, FIRE, 60, 20);
    const halved = estimateRound(b, FIRE, 60, 20, { a: { fire: -0.5 } });
    expect(halved.units.x.losses.p50).toBeLessThan(plain.units.x.losses.p50);
  });
});
