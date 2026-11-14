import { describe, expect, it } from 'vitest';

import { createStore, EXAMPLE_ARMIES, type UnitDraft } from './store';

const draft = (over: Partial<UnitDraft> = {}): UnitDraft => ({
  id: 'u', name: 'A unit', side: 0, type: 'inf', subtype: 'line', size: 500, stats: '5/5/0/0', guns: null, ...over,
});

describe('store: armies', () => {
  it('starts with the example armies, named sides and a seed', () => {
    const s = createStore(7);
    expect(s.units.value).toEqual(EXAMPLE_ARMIES.units);
    expect(s.sides.value).toEqual(EXAMPLE_ARMIES.sides);
    expect(s.seed.value).toBe(7);
    expect(s.battle.value).toBeNull();
  });

  it('adds units with fresh ids, edits and removes them', () => {
    const s = createStore(1);
    s.clearUnits();
    s.addUnit(0);
    s.addUnit(1);
    s.addUnit(0);
    expect(s.units.value.map((u) => [u.id, u.side])).toEqual([['u1', 0], ['u2', 1], ['u3', 0]]);
    s.updateUnit('u2', { type: 'cav', subtype: 'heavy', size: 300 });
    expect(s.units.value[1]).toMatchObject({ type: 'cav', subtype: 'heavy', size: 300 });
    s.updateUnit('u2', { type: 'art' });                 // changing type picks that type's first subtype, guns
    expect(s.units.value[1]).toMatchObject({ type: 'art', subtype: 'battery', guns: 8, size: 72 });
    s.updateUnit('u2', { type: 'inf' });
    expect(s.units.value[1]).toMatchObject({ type: 'inf', subtype: 'line', guns: null });
    s.removeUnit('u1');
    expect(s.units.value.map((u) => u.id)).toEqual(['u2', 'u3']);
  });

  it('new ids skip ones already in use', () => {
    const s = createStore(1);
    s.clearUnits();
    s.units.value = [draft({ id: 'u1' })];
    s.addUnit(1);
    expect(s.units.value[1].id).toBe('u2');
  });

  it('renames sides and draws a new seed', () => {
    const s = createStore(1);
    s.renameSide(1, 'Rebels');
    expect(s.sides.value).toEqual([EXAMPLE_ARMIES.sides[0], 'Rebels']);
    s.newSeed(() => 0.5);
    expect(s.seed.value).toBe(2 ** 31);
  });
});

describe('store: starting the battle', () => {
  it('builds the battle from the drafts and shows the order of battle', () => {
    const s = createStore(1863);
    expect(s.orderOfBattle.value).toBeNull();
    expect(s.start()).toEqual([]);
    const battle = s.battle.value!;
    expect([...battle.units.keys()]).toEqual(EXAMPLE_ARMIES.units.map((u) => u.id));
    expect(battle.seed).toBe(1863);
    expect(battle.meta.sides).toEqual(EXAMPLE_ARMIES.sides);
    expect(s.orderOfBattle.value!.map((o) => o.name)).toEqual(EXAMPLE_ARMIES.sides);
  });

  it('builds each kind of unit', () => {
    const s = createStore(1);
    s.units.value = [
      draft({ id: 'a' }), draft({ id: 'b', type: 'cav', subtype: 'light' }),
      draft({ id: 'c', side: 1, type: 'art', subtype: 'battery', size: 72, guns: 8 }),
      draft({ id: 'd', side: 1, type: null, subtype: null }),
    ];
    expect(s.start()).toEqual([]);
    const kinds = [...s.battle.value!.units.values()].map((u) => u.key);
    expect(kinds).toEqual([['inf', 'line'], ['cav', 'light'], ['art', 'battery'], ['inf', null]]);
  });

  it('reports every problem, naming the unit, and does not start', () => {
    const s = createStore(1);
    s.units.value = [
      draft({ id: 'a', name: 'Bad stats', stats: '5/5' }),
      draft({ id: 'b', name: 'Bad size', size: 0 }),
      draft({ id: 'c', name: 'Bad guns', type: 'art', subtype: 'battery', guns: null }),
      draft({ id: 'd', name: 'Fine', side: 1 }),
    ];
    const problems = s.start();
    expect(problems).toHaveLength(3);
    expect(problems[0]).toMatch(/^Bad stats: Stats must be/);
    expect(problems[1]).toBe('Bad size: men must be a whole number, 1 or more.');
    expect(problems[2]).toBe('Bad guns: guns must be a whole number, 0 or more.');
    expect(s.battle.value).toBeNull();
  });

  it('needs units on both sides', () => {
    const s = createStore(1);
    s.units.value = [draft({ id: 'a' })];
    expect(s.start()).toEqual([`${EXAMPLE_ARMIES.sides[1]} has no units.`]);
  });

  it('can go back to editing the armies', () => {
    const s = createStore(1);
    s.start();
    s.reset();
    expect(s.battle.value).toBeNull();
  });
});

describe('store: seed', () => {
  it.each([NaN, -1, 1.5, 2 ** 32])('rejects seed %s', (seed) => {
    const s = createStore(1);
    s.seed.value = seed;
    expect(s.start()).toEqual(['The seed must be a whole number from 0 to 4294967295.']);
  });
});
