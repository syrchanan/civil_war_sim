import { describe, expect, it } from 'vitest';

import { bearing, blockSize, clampToField, defaultFacing, defaultLayout, FIELD, turned } from './field';

describe('block size (yards)', () => {
  it('infantry: two ranks, about two thirds of a yard per file', () => {
    expect(blockSize('inf', 900, 900, null)).toEqual({ width: 297, depth: 20 });
  });

  it('a narrower front makes a narrower, deeper block', () => {
    expect(blockSize('inf', 900, 300, null)).toEqual({ width: 99, depth: 60 });
  });

  it('cavalry needs more room per file; a generic unit is infantry', () => {
    expect(blockSize('cav', 400, 400, null)).toEqual({ width: 220, depth: 40 });
    expect(blockSize(null, 900, 900, null)).toEqual(blockSize('inf', 900, 900, null));
  });

  it('a battery is about fifteen yards per gun', () => {
    expect(blockSize('art', 72, 72, 8)).toEqual({ width: 120, depth: 40 });
  });

  it('a unit with no front left is drawn at the minimum width, one block deep', () => {
    expect(blockSize('inf', 100, 0, null)).toEqual({ width: 20, depth: 20 });
  });

  it('never vanishes: a minimum size', () => {
    expect(blockSize('inf', 3, 3, null).width).toBe(20);
    expect(blockSize('art', 0, 0, 0).width).toBe(20);
    expect(blockSize('art', 72, 72, null).width).toBe(20);     // no gun count given
  });
});

describe('default layout', () => {
  it('side 0 lines up at the bottom, side 1 at the top, each centred', () => {
    const units = [
      { id: 'a', side: 0 as const, width: 300 }, { id: 'b', side: 0 as const, width: 200 },
      { id: 'x', side: 1 as const, width: 400 },
    ];
    const layout = defaultLayout(units);
    expect(layout.a.y).toBe(FIELD.height * 0.75);
    expect(layout.x.y).toBe(FIELD.height * 0.25);
    // a and b side by side with a 60 yd gap, the pair centred on the field
    expect(layout.b.x - layout.a.x).toBe(300 / 2 + 60 + 200 / 2);
    expect((layout.a.x - 150 + layout.b.x + 100) / 2).toBeCloseTo(FIELD.width / 2, -0.5);   // within a yard
    expect(Object.values(layout).every((p) => Number.isInteger(p.x))).toBe(true);
    expect(layout.x.x).toBe(FIELD.width / 2);
  });

  it('a long line wraps to a second line behind the first', () => {
    const units = Array.from({ length: 8 }, (_, i) => ({ id: `u${i}`, side: 0 as const, width: 300 }));
    const layout = defaultLayout(units);
    const ys = new Set(Object.values(layout).map((p) => p.y));
    expect(ys.size).toBe(2);
    expect(Math.max(...ys)).toBe(FIELD.height * 0.75 + 120);
  });
});

describe('clamp to the field', () => {
  it('keeps a point on the field', () => {
    expect(clampToField({ x: -50, y: 5000 })).toEqual({ x: 0, y: FIELD.height });
    expect(clampToField({ x: 10.4, y: 20.6 })).toEqual({ x: 10, y: 21 });
  });
});

describe('facing (compass degrees, clockwise from the top of the map)', () => {
  it('each side starts facing the other: side 0 up the map, side 1 down it', () => {
    expect([defaultFacing(0), defaultFacing(1)]).toEqual([0, 180]);
  });

  it('turning stays within one turn', () => {
    expect(turned(350, 20)).toBe(10);
    expect(turned(10, -20)).toBe(350);
    expect(turned(90, 360)).toBe(90);
  });

  it('the bearing from one point to another, in whole degrees', () => {
    const at = { x: 100, y: 100 };
    expect(bearing(at, { x: 100, y: 0 })).toBe(0);
    expect(bearing(at, { x: 200, y: 100 })).toBe(90);
    expect(bearing(at, { x: 100, y: 200 })).toBe(180);
    expect(bearing(at, { x: 0, y: 100 })).toBe(270);
    expect(bearing(at, { x: 102, y: 0 })).toBe(1);
    expect(bearing(at, { x: 99.9, y: 0 })).toBe(0);           // 359.94 rounds to a full turn: 0
  });
});
