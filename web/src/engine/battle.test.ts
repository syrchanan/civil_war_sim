import { describe, expect, it } from 'vitest';

import fixture from '../../../test_cases/parity/battles.json';
import { Battle, makeOrder } from './battle';
import { RuntimeError, ValueError } from './errors';
import { Rng } from './rng';
import type { StateData } from './state';
import { ArtilleryBattery, Regiment } from './units';

const make = () => new Battle({
  a: { side: 0, regiment: new Regiment(500, '5/5/0/0') },
  g: { side: 0, regiment: new ArtilleryBattery(72, '5/5/0/0', 8, 'battery') },
  x: { side: 1, regiment: new Regiment(400, '4/4/0/0'), name: 'Exes', meta: { player: 'p2' } },
}, new Rng(1));

describe('orders', () => {
  it('default on_break by mode', () => {
    expect(makeOrder({ target: 'x', mode: 'ranged' }).on_break).toBe('keep');
    expect(makeOrder({ target: 'x', mode: 'melee' }).on_break).toBe('fall_back');
    expect(makeOrder(null)).toEqual({ target: null, mode: 'idle', ammo: null, on_break: null });
  });

  it.each([
    { mode: 'charge', target: 'x' }, { mode: 'ranged' }, { target: 'x' }, { mode: 'melee', target: 'x', ammo: 'shell' },
    { mode: 'idle', on_break: 'keep' }, { mode: 'ranged', target: 'x', on_break: 'pursue' },
    { mode: 'melee', target: 'x', on_break: 'strongest' },
  ])('rejects %j', (order) => {
    expect(() => makeOrder(order)).toThrow(ValueError);
  });

  it.each([
    [{ nobody: { target: 'x', mode: 'ranged' } }, 'Unknown unit nobody'],
    [{ a: { target: 'nobody', mode: 'ranged' } }, 'targets unknown unit'],
    [{ a: { target: 'g', mode: 'ranged' } }, 'same side'],
    [{ a: { aim: 'x', mode: 'ranged' } }, "Unknown order key(s) [aim] for a; use target, mode, ammo, on_break."],
    [{ a: { target: 'x', mode: 'ranged', ammo: 'shell' } }, "isn't artillery"],
    [{ g: { target: 'x', mode: 'ranged', ammo: 'grape' } }, 'unknown ammo grape'],
  ])('battle rejects %j', (orders, message) => {
    expect(() => make().engagements(orders)).toThrow(message);
  });

  it('a broken unit cannot act and a wiped-out one cannot be targeted', () => {
    const b = make();
    b.units.get('x')!.morale.forceBreak();
    expect(() => b.engagements({ x: { target: 'a', mode: 'ranged' } })).toThrow("can't act");
    b.units.get('x')!.regiment.updateSize(0);
    expect(() => b.engagements({ a: { target: 'x', mode: 'ranged' } })).toThrow('wiped out');
  });
});

describe('preview and rounds', () => {
  it('engagements previews arrows without rolling dice', () => {
    const b = make();
    const state = b.rng.state;
    const arrows = b.engagements({ a: { target: 'x', mode: 'ranged' }, x: { target: 'g', mode: 'melee' } });
    expect(arrows.map((e) => [e.attacker, e.target, e.mode])).toEqual([['a', 'x', 'ranged'], ['g', 'x', 'closing']]);
    expect(b.rng.state).toEqual(state);
  });

  it('rejects a non-positive duration and rounds after the finish', () => {
    const b = make();
    expect(() => b.resolveRound(0, {})).toThrow(ValueError);
    b.finish();
    expect(() => b.resolveRound(10, {})).toThrow(RuntimeError);
    expect(() => b.finish()).toThrow(RuntimeError);
  });

  it('rejects an unknown field holder', () => {
    expect(() => make().finish(2 as 0)).toThrow(ValueError);
  });

  it('keeps names and meta through the state file', () => {
    const b = Battle.fromJson(make().toJson());
    expect(b.units.get('x')!.name).toBe('Exes');
    expect(b.units.get('x')!.meta).toEqual({ player: 'p2' });
  });

  it('rejects bad sides', () => {
    expect(() => new Battle({ a: { side: 2, regiment: new Regiment(10, '4/4/0/0') } })).toThrow(ValueError);
  });
});

describe('state file', () => {
  const start = (fixture.cases[0] as unknown as { start: StateData }).start;

  it('rejects other formats and versions', () => {
    expect(() => Battle.fromDict({ ...start, format: 'x' })).toThrow(ValueError);
    expect(() => Battle.fromDict({ ...start, version: 1 })).toThrow(ValueError);
    const units = structuredClone(start.units);
    units[0].type = 'navy';
    expect(() => Battle.fromDict({ ...start, units })).toThrow(ValueError);
  });

  it('loads files saved before retargets and field votes', () => {
    const c = fixture.cases.find((x) => x.final.result !== null)!;
    const old = structuredClone(c.final) as unknown as StateData;
    for (const r of old.history) delete (r as Partial<typeof r>).retargets;
    const result = old.result as unknown as Record<string, unknown>;
    delete result.field_decided_by;
    delete result.field_votes;
    const b = Battle.fromDict(old);
    expect(b.history.every((r) => Array.isArray(r.retargets))).toBe(true);
    expect([b.result!.field_decided_by, b.result!.field_votes]).toEqual(['admin', {}]);
  });
});
