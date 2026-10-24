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

describe('edge cases', () => {
  it('rejects orders that are not objects, and a unit that is not a regiment', () => {
    expect(() => makeOrder('x' as never)).toThrow(TypeError);
    expect(() => make().engagements([] as never)).toThrow(TypeError);
    expect(() => new Battle({ a: { side: 0, regiment: {} as Regiment } })).toThrow(TypeError);
  });

  it('skips idle orders', () => {
    expect(make().engagements({ a: { mode: 'idle' }, x: null })).toEqual([]);
  });

  it('a zero-width front fights no melee', () => {
    const b = new Battle({
      a: { side: 0, regiment: new Regiment(500, '5/5/0/0', { frontSize: 0 }) },
      x: { side: 1, regiment: new Regiment(500, '5/5/0/0', { frontSize: 0 }) },
    }, new Rng(1));
    b.contacts = new Set([['a', 'x'].join('\u0000')]);
    expect(b.engagements({ a: { target: 'x', mode: 'melee' } })).toEqual([]);
  });

  it('a one-man unit broken and wiped out by the same hit gives no prisoners', () => {
    const b = new Battle({
      a: { side: 0, regiment: new Regiment(2000, '8/8/1/0') },
      x: { side: 1, regiment: new Regiment(1, '1/1/0/0') },
    }, new Rng(1));
    const report = b.resolveRound(30, { a: { target: 'x', mode: 'ranged' } });
    expect([report.units.x.size, report.units.x.captured]).toEqual([0, 0]);
  });

  it('a battery wiped out by fire loses every gun', () => {
    const b = new Battle({
      a: { side: 0, regiment: new Regiment(2000, '8/8/1/0') },
      g: { side: 1, regiment: new ArtilleryBattery(1, '9/9/0/0', 4, 'battery') },
    }, new Rng(1));
    const report = b.resolveRound(30, { a: { target: 'g', mode: 'ranged' } });
    expect([report.units.g.size, report.units.g.guns_lost, report.guns_captured[0]]).toEqual([0, 4, 4]);
  });

  it('weakest picks the enemy with the fewest men × morale left', () => {
    const b = new Battle({
      a: { side: 0, regiment: new Regiment(2000, '8/8/1/0') },
      x: { side: 1, regiment: new Regiment(30, '1/1/0/0') },
      y: { side: 1, regiment: new Regiment(900, '5/5/0/0') },
      z: { side: 1, regiment: new Regiment(300, '5/5/0/0') },
      w: { side: 1, regiment: new Regiment(600, '5/5/0/0') },
    }, new Rng(2));
    const report = b.resolveRound(30, { a: { target: 'x', mode: 'ranged', on_break: 'weakest' } });
    expect(report.retargets[0].new_target).toBe('z');
  });

  it('side 1 holds the field when all of side 0 is out', () => {
    const b = make();
    for (const uid of ['a', 'g']) b.units.get(uid)!.morale.forceBreak();
    expect(b.finish().field_held_by).toBe(1);
  });

  it('saves positions and several contacts', () => {
    const position = { x: 1, y: 2, z: 0, cover: 0, terrain_type: 'open' };
    const b = new Battle({
      b2: { side: 0, regiment: new Regiment(100, '4/4/0/0', { position }) },
      a1: { side: 0, regiment: new Regiment(100, '4/4/0/0') },
      x9: { side: 1, regiment: new Regiment(100, '4/4/0/0') },
      c3: { side: 1, regiment: new Regiment(100, '4/4/0/0') },
    }, new Rng(1));
    b.contacts = new Set(['b2\u0000x9', 'a1\u0000c3', 'a1\u0000x9']);
    const data = b.toDict();
    expect(data.contacts).toEqual([['a1', 'c3'], ['a1', 'x9'], ['b2', 'x9']]);
    expect(data.units[0].position).toEqual({ ...position, facing: null }); // facing not given
    expect(Battle.fromDict(data).toDict()).toEqual(data);
  });

  it('saves a facing, and loads positions saved before facing existed', () => {
    const position = { x: 1, y: 2, z: 0, cover: 0, terrain_type: 'open', facing: 180 };
    const b = new Battle({
      a: { side: 0, regiment: new Regiment(100, '4/4/0/0', { position }) },
      x: { side: 1, regiment: new Regiment(100, '4/4/0/0') },
    }, new Rng(1));
    const data = b.toDict();
    expect(data.units[0].position).toEqual(position);
    expect(Battle.fromDict(data).units.get('a')!.regiment.position).toEqual(position);
    delete (data.units[0].position as { facing?: number }).facing;
    expect(Battle.fromDict(data).units.get('a')!.regiment.position!.facing).toBeNull();
  });
});

describe('more of the targeting graph', () => {
  it('a unit in two contacts, two chargers on one target, and a battery with no crew to fire', () => {
    const b = new Battle({
      a: { side: 0, regiment: new Regiment(500, '5/5/0/0') },
      c: { side: 0, regiment: new Regiment(300, '5/5/0/0') },
      d: { side: 0, regiment: new Regiment(300, '5/5/0/0') },
      g: { side: 0, regiment: new ArtilleryBattery(6, '5/5/0/0', 4, 'battery') },
      x: { side: 1, regiment: new Regiment(400, '4/4/0/0') },
      y: { side: 1, regiment: new Regiment(400, '4/4/0/0') },
      z: { side: 1, regiment: new Regiment(400, '4/4/0/0') },
    }, new Rng(1));
    b.contacts = new Set(['a\u0000x', 'a\u0000y']);
    const arrows = b.engagements({
      a: { target: 'x', mode: 'melee' }, y: { target: 'a', mode: 'melee' },
      c: { target: 'z', mode: 'melee' }, d: { target: 'z', mode: 'melee' }, g: { target: 'z', mode: 'ranged' },
    });
    const keys = arrows.map((e) => `${e.attacker}>${e.target}:${e.mode}`);
    expect(keys).toEqual(expect.arrayContaining(['a>x:melee', 'a>y:melee', 'x>a:melee', 'y>a:melee',
      'z>c:closing', 'z>d:closing']));
    expect(keys.some((k) => k.startsWith('g>'))).toBe(false);          // 6 crew can't man a gun
  });

  it('sorts saved contacts by first id, then second', () => {
    const units: Record<string, { side: number; regiment: Regiment }> = {};
    for (const uid of ['p', 'q', 'r']) units[uid] = { side: 0, regiment: new Regiment(10, '4/4/0/0') };
    for (const uid of ['k', 'm', 'n']) units[uid] = { side: 1, regiment: new Regiment(10, '4/4/0/0') };
    const b = new Battle(units, new Rng(1));
    b.contacts = new Set(['r\u0000n', 'p\u0000m', 'q\u0000k', 'p\u0000k', 'r\u0000k', 'p\u0000n']);
    expect(b.toDict().contacts).toEqual([['p', 'k'], ['p', 'm'], ['p', 'n'], ['q', 'k'], ['r', 'k'], ['r', 'n']]);
  });
});

describe('surrounded', () => {
  it('a unit in contact with two attackers takes both', () => {
    const b = new Battle({
      a: { side: 0, regiment: new Regiment(300, '5/5/0/0') },
      c: { side: 0, regiment: new Regiment(300, '5/5/0/0') },
      x: { side: 1, regiment: new Regiment(400, '4/4/0/0') },
    }, new Rng(1));
    b.contacts = new Set(['a\u0000x', 'c\u0000x']);
    const arrows = b.engagements({ a: { target: 'x', mode: 'melee' }, c: { target: 'x', mode: 'melee' } });
    expect(arrows.map((e) => `${e.attacker}>${e.target}`)).toEqual(['x>a', 'x>c', 'a>x', 'c>x']);
  });
});
