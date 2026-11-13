import { describe, expect, it } from 'vitest';

import fixture from '../../../test_cases/parity/terrain.json';
import battles from '../../../test_cases/parity/battles.json';
import { Battle } from './battle';
import { ValueError } from './errors';
import type { StateData } from './state';
import { Terrain, type TerrainData } from './terrain';
import { Regiment } from './units';

const data = fixture.terrain as TerrainData;

describe('terrain', () => {
  const t = new Terrain(data);

  it.each(fixture.samples as [number, number, number, string][])('at (%s, %s): height %s, ground %s', (x, y, h, g) => {
    expect(t.heightAt(x, y)).toBe(h);
    expect(t.groundAt(x, y)).toBe(g);
  });

  it('round-trips and knows its size', () => {
    expect(t.toDict()).toEqual(data);
    expect([t.width, t.height]).toEqual([300, 200]);
    expect(Terrain.fromDict(t.toDict()).toDict()).toEqual(data);
  });

  it('a single row or column holds level along it', () => {
    const one = new Terrain({ cell: 10, columns: 1, rows: 1, heights: [7], ground: 'f', meta: {} });
    expect([one.heightAt(-5, 3), one.heightAt(100, 100), one.groundAt(3, 3)]).toEqual([7, 7, 'forest']);
  });

  it.each([
    { cell: 0 }, { columns: 0 }, { rows: 1.5 }, { heights: [0] }, { heights: ['a'] }, { heights: 'flat' },
    { ground: 'o' }, { ground: 'x'.repeat(96) }, { meta: [] },
  ])('rejects %j', (change) => {
    expect(() => new Terrain({ ...data, ...change } as TerrainData)).toThrow(ValueError);
  });

  it('a missing meta is an empty one', () => {
    expect(new Terrain({ ...data, meta: undefined as never }).meta).toEqual({});
  });
});

describe('a battle with terrain', () => {
  it('keeps it in the state file, as Python saves it', () => {
    const c = battles.cases.find((x) => x.name === 'ranges')!;
    const start = c.start as unknown as StateData;
    expect(start.terrain).toEqual(data);
    const b = Battle.fromDict(structuredClone(start));
    expect(b.terrain!.toDict()).toEqual(data);
    expect(b.toDict().terrain).toEqual(data);
    const plain = new Battle({ a: { side: 0, regiment: new Regiment(10, '5/5/0/0') } });
    expect(plain.terrain).toBeNull();
    expect(plain.toDict().terrain).toBeNull();
    const old = structuredClone(start) as Partial<StateData>;
    delete old.terrain;
    expect(Battle.fromDict(old as StateData).terrain).toBeNull();
  });
});
