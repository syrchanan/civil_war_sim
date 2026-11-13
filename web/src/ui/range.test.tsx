// @vitest-environment jsdom
// Range in the client: the orders table says how far each target is and how much of the fire tells.
import { cleanup, fireEvent, render, screen } from '@testing-library/preact';
import { afterEach, describe, expect, it } from 'vitest';

import { App } from './App';
import { rangeText } from './format';
import { createStore } from './store';
import { closeRanks } from './testing';

afterEach(cleanup);

describe('format', () => {
  it('range in words', () => {
    const base = { inArc: true, zone: 'front' as const, sight: true, elevation: 0 };
    expect(rangeText({ ...base, distance: 612.4, reach: 0 })).toBe('612 yd, out of range');
    expect(rangeText({ ...base, distance: 160, reach: 0.4567 })).toBe('160 yd, 46% effect');
    expect(rangeText({ ...base, distance: 60, reach: 1 })).toBe('60 yd, full effect');
    expect(rangeText({ ...base, distance: 60, reach: 1, zone: 'flank' })).toBe('60 yd, full effect, on its flank');
    expect(rangeText({ ...base, distance: 60, reach: 0.5, zone: 'rear' })).toBe('60 yd, 50% effect, from its rear');
    expect(rangeText({ ...base, distance: 60, reach: 1, zone: null })).toBe('60 yd, full effect');
    expect(rangeText({ ...base, distance: 60, reach: 1, inArc: false })).toBe('60 yd, outside its front arc');
  });
});

describe('store: range of an order', () => {
  it('distance and reach of a unit\'s fire on its target; nothing for hold, charges and unplaced units', () => {
    const s = createStore(1863);
    s.start();
    expect(s.rangeOf('us_1mn')).toBeNull(); // holding
    s.setOrder('us_1mn', { mode: 'ranged', target: 'cs_8al' });
    const b = s.battle.value!;
    expect(s.rangeOf('us_1mn')).toEqual({ distance: b.distance('us_1mn', 'cs_8al'), reach: 0, inArc: true,
      zone: b.zone('cs_8al', 'us_1mn'), sight: true, elevation: 0 }); // 600 yd apart, an open field
    b.units.get('us_1mn')!.regiment.position!.facing = 90; // turned away east
    s.touch();
    expect(s.rangeOf('us_1mn')!.inArc).toBe(b.inArc('us_1mn', 'cs_8al'));
    s.setOrder('us_bat', { mode: 'ranged', target: 'cs_8al' });
    expect(s.rangeOf('us_bat')!.reach).toBe(b.reach('us_bat', 'cs_8al', 'round_shot'));
    s.setOrder('us_bat', { ammo: 'canister' });
    expect(s.rangeOf('us_bat')!.reach).toBe(0);
    s.setOrder('us_15ma', { mode: 'melee', target: 'cs_8al' });
    expect(s.rangeOf('us_15ma')).toBeNull();
    b.units.get('us_1mn')!.regiment.position = null;
    expect(s.rangeOf('us_1mn')).toBeNull();
  });
});

describe('the orders table', () => {
  it('shows each firing unit\'s range', () => {
    const store = createStore(1863);
    render(<App store={store} />);
    fireEvent.click(screen.getByRole('button', { name: 'Start battle' }));
    fireEvent.change(screen.getByLabelText('1st Minnesota action'), { target: { value: 'ranged' } });
    expect(screen.getByLabelText('1st Minnesota range').textContent).toMatch(/^\d+ yd, out of range$/);
    cleanup();
    const close = createStore(1863);
    render(<App store={close} />);
    closeRanks(close);
    fireEvent.click(screen.getByRole('button', { name: 'Start battle' }));
    fireEvent.change(screen.getByLabelText('1st Minnesota action'), { target: { value: 'ranged' } });
    expect(screen.getByLabelText('1st Minnesota range').textContent).toMatch(/^\d+ yd, (full|\d+%) effect$/);
  });
});
