import { describe, expect, it } from 'vitest';

import { Battle, type Engagement, type OrderInput, validateSideModifiers } from './battle';
import { ValueError } from './errors';
import { Rng } from './rng';
import { CavalryRegiment, Regiment } from './units';

const battle = (sideModifiers: Record<string, unknown> = {}, seed = 3) => new Battle({
  a: { side: 0, regiment: new Regiment(1000, '5/5/0/0') },
  b: { side: 0, regiment: new CavalryRegiment(400, '5/5/0/0', 'light') },
  x: { side: 1, regiment: new Regiment(1000, '5/5/0/0') },
}, new Rng(seed), undefined, undefined, sideModifiers);

const FIRE: Record<string, OrderInput> = { a: { target: 'x', mode: 'ranged' }, x: { target: 'a', mode: 'ranged' } };
const MELEE: Record<string, OrderInput> = { a: { target: 'x', mode: 'melee' }, x: { target: 'a', mode: 'melee' } };
const rates = (arrows: Engagement[]) => Object.fromEntries(arrows.map((e) => [`${e.attacker} ${e.mode}`, e.rate]));

describe('side modifiers (whole battle)', () => {
  it('fire scales every unit of that side, melee scales melee', () => {
    const plain = rates(battle().engagements(FIRE));
    const modified = rates(battle({ 1: { fire: -0.1 } }).engagements(FIRE));
    expect(modified['x ranged']).toBeCloseTo(plain['x ranged'] * 0.9, 12);
    expect(modified['a ranged']).toBe(plain['a ranged']);
    const [b, p] = [battle({ 0: { melee: 0.2 } }), battle()];
    b.contacts = new Set(['a\u0000x']);
    p.contacts = new Set(['a\u0000x']);
    expect(rates(b.engagements(MELEE))['a melee']).toBeCloseTo(rates(p.engagements(MELEE))['a melee'] * 1.2, 12);
  });

  it('multiplies with the unit modifiers', () => {
    const both = rates(battle({ 0: { fire: 0.5 } }).engagements(FIRE, { a: { fire: -0.5 } }));
    expect(both['a ranged']).toBeCloseTo(rates(battle().engagements(FIRE))['a ranged'] * 1.5 * 0.5, 12);
  });

  it('morale scales what every unit of the side spends; +100% spends nothing whatever the unit modifier', () => {
    const [plain, steadier] = [battle(), battle({ 1: { morale: 0.5 } })];
    plain.resolveRound(60, FIRE);
    steadier.resolveRound(60, FIRE);
    expect(plain.units.get('x')!.morale.resolve).toBeLessThan(steadier.units.get('x')!.morale.resolve);
    const firm = battle({ 1: { morale: 1 } });
    firm.resolveRound(600, FIRE, false, { x: { morale: -0.5 } });
    expect(firm.units.get('x')!.morale.resolve).toBe(1);
    expect(firm.units.get('x')!.morale.spendFactor).toBe(1);
  });

  it('zero side modifiers change nothing', () => {
    const [plain, zero] = [battle(), battle({ 0: { fire: 0, melee: 0, morale: 0 }, 1: {} })];
    plain.resolveRound(60, FIRE);
    zero.resolveRound(60, FIRE);
    expect(zero.toDict().units).toEqual(plain.toDict().units);
  });

  it('last until changed, and each round records them', () => {
    const b = battle({ 0: { fire: -0.1, note: 'poor supply' } });
    const full = { 0: { fire: -0.1, melee: 0, morale: 0, note: 'poor supply' } };
    expect(b.resolveRound(30, FIRE).side_modifiers).toEqual(full);
    expect(b.sideModifiers).toEqual(full);
    b.setSideModifiers({ 1: { morale: 0.2 } });
    expect(b.resolveRound(30, FIRE).side_modifiers).toEqual({ 1: { fire: 0, melee: 0, morale: 0.2, note: '' } });
    b.setSideModifiers({});
    expect(b.resolveRound(30, FIRE).side_modifiers).toEqual({});
  });

  it('round-trip through the state file, and are absent in older files', () => {
    const b = battle({ 1: { melee: -0.3, note: 'tired' } });
    b.resolveRound(30, FIRE);
    const data = b.toDict();
    expect(data.side_modifiers).toEqual({ 1: { fire: 0, melee: -0.3, morale: 0, note: 'tired' } });
    expect(data.history[0].side_modifiers).toEqual(data.side_modifiers);
    const loaded = Battle.fromDict(structuredClone(data));
    expect(loaded.sideModifiers).toEqual(b.sideModifiers);
    expect(loaded.engagements(FIRE)).toEqual(b.engagements(FIRE));
    const old = structuredClone(data) as Partial<typeof data>;
    delete old.side_modifiers;
    delete (old.history![0] as Partial<(typeof data.history)[0]>).side_modifiers;
    const reloaded = Battle.fromDict(old as typeof data);
    expect(reloaded.sideModifiers).toEqual({});
    expect(reloaded.history[0].side_modifiers).toEqual({});
  });

  it.each([
    [{ 2: { fire: 0.1 } }, 'side must be 0 or 1'],
    [{ Union: { fire: 0.1 } }, 'side must be 0 or 1'],
    [{ 0: { range: 0.1 } }, 'Unknown modifier'],
    [{ 0: { fire: -1.5 } }, 'between -1 and 1'],
    [{ 1: { morale: 'x' } }, 'number'],
    [{ 1: { note: 3 } }, 'note'],
    [{ 0: 0.1 }, 'mapping'],
    [[0], 'mapping of side'],
  ])('refuses %j', (mods, message) => {
    expect(() => validateSideModifiers(mods)).toThrow(ValueError);
    expect(() => battle(mods as Record<string, unknown>)).toThrow(message);
    const b = battle({ 0: { fire: 0.1 } });
    expect(() => b.setSideModifiers(mods as Record<string, unknown>)).toThrow(message);
    expect(b.sideModifiers[0].fire).toBe(0.1);
  });
});
