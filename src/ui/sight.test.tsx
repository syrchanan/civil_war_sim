// @vitest-environment jsdom
// Line of sight and elevation in the client: the orders table says so; fire that can't tell is drawn faded.
import { act, cleanup, render } from '@testing-library/preact';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { Terrain } from '../engine';
import { App } from './App';
import { rangeText } from './format';
import { createStore } from './store';

beforeEach(() => localStorage.clear());
afterEach(cleanup);

const base = { distance: 200, reach: 1, inArc: true, zone: 'front' as const, sight: true, elevation: 0 };

describe('format', () => {
  it('no line of sight, and the elevation bonus or penalty', () => {
    expect(rangeText({ ...base, sight: false })).toBe('200 yd, no line of sight');
    expect(rangeText({ ...base, inArc: false, sight: false })).toBe('200 yd, outside its front arc');
    expect(rangeText({ ...base, elevation: 0.14 })).toBe('200 yd, full effect, +14% from higher ground');
    expect(rangeText({ ...base, elevation: -0.06, zone: 'flank' })).toBe('200 yd, full effect, on its flank, -6% uphill');
    expect(rangeText({ ...base, elevation: 0.004 })).toBe('200 yd, full effect');
    expect(rangeText({ ...base, reach: 0, elevation: 0.1 })).toBe('200 yd, out of range');
  });
});

/** The example armies on a ridge: Union fire on 8th Alabama is hidden behind it. */
function onRidge() {
  const s = createStore(1863);
  s.start();
  const b = s.battle.value!;
  const cell = 20;
  const columns = 100;
  const rows = 60;
  const heights: number[] = [];
  for (let r = 0; r < rows; r++) for (let c = 0; c < columns; c++) heights.push(r === 30 ? 40 : 0);
  (b as { terrain: Terrain | null }).terrain = new Terrain({ cell, columns, rows, heights, ground: 'o'.repeat(6000), meta: {} });
  s.touch();
  return s;
}

describe('store and map', () => {
  it('a firing unit\'s range says whether it can see its target and its height advantage', () => {
    const s = onRidge();
    s.setOrder('us_bat', { mode: 'ranged', target: 'cs_8al' });
    const r = s.rangeOf('us_bat')!;
    const b = s.battle.value!;
    expect(r.sight).toBe(false);
    expect(r.sight).toBe(b.lineOfSight('us_bat', 'cs_8al'));
    expect(r.elevation).toBe(b.elevationBonus('us_bat', 'cs_8al'));
  });

  it('order arrows for fire that can\'t tell (out of range, outside the arc, no sight) are drawn faded', () => {
    const s = onRidge();
    s.setOrder('us_bat', { mode: 'ranged', target: 'cs_8al' });
    s.setOrder('us_1mn', { mode: 'melee', target: 'cs_8al' });
    render(<App store={s} />);
    act(() => s.touch());
    expect(s.orderArrows.value.find((a) => a.from === 'us_bat')!.blocked).toBe(true);
    expect(s.orderArrows.value.find((a) => a.from === 'us_1mn')!.blocked).toBe(false);   // a charge goes anyway
    expect(document.querySelectorAll('.order-arrow.blocked')).toHaveLength(1);
  });
});

describe('replaying a round', () => {
  it('draws no arrow for a rally order (it has no target)', () => {
    const s = createStore(1863);
    s.start();
    const u = s.battle.value!.units.get('cs_8al')!;
    u.morale.forceBreak();
    s.touch();
    s.setOrder('cs_8al', { mode: 'rally' });
    expect(s.resolve()).toBeNull();
    s.mapRound.value = 1;
    expect(s.orderArrows.value.some((a) => a.from === 'cs_8al')).toBe(false);
  });
});
