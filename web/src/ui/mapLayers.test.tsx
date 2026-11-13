// @vitest-environment jsdom
// Map layers (what the map shows, chosen per viewer), front arcs, and NATO unit symbols.
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/preact';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { arcPath } from './field';
import { App } from './App';
import { LAYERS, loadLayers, natoSymbol } from './mapLayers';
import { createStore } from './store';

beforeEach(() => localStorage.clear());
afterEach(cleanup);

describe('layers', () => {
  it('each has a key, a label, a group and a default; keys are unique', () => {
    expect(new Set(LAYERS.map((l) => l.key)).size).toBe(LAYERS.length);
    expect(LAYERS.map((l) => l.key))
      .toEqual(['symbols', 'labels', 'allArcs', 'arrows', 'relief', 'woods', 'grid', 'scale']);
    expect(LAYERS.filter((l) => l.default).map((l) => l.key))
      .toEqual(['symbols', 'labels', 'arrows', 'relief', 'woods', 'grid', 'scale']);
  });

  it('are remembered per viewer; unknown or broken saved values fall back to the defaults', () => {
    const s = createStore(1863);
    expect(s.layers.value.allArcs).toBe(false);
    s.setLayer('allArcs', true);
    expect(createStore(1863).layers.value.allArcs).toBe(true);
    localStorage.setItem('map-layers', '{not json');
    expect(loadLayers().allArcs).toBe(false);
    localStorage.setItem('map-layers', JSON.stringify({ allArcs: 'yes', grid: false, nonsense: true }));
    expect(loadLayers()).toMatchObject({ allArcs: false, grid: false });
    expect('nonsense' in loadLayers()).toBe(false);
  });

  it('still work when the browser blocks storage', () => {
    const real = Object.getOwnPropertyDescriptor(window, 'localStorage')!;
    Object.defineProperty(window, 'localStorage', { get: () => { throw new Error('blocked'); }, configurable: true });
    try {
      const s = createStore(1863);
      expect(s.layers.value.symbols).toBe(true);
      s.setLayer('grid', false);
      expect(s.layers.value.grid).toBe(false);
    } finally {
      Object.defineProperty(window, 'localStorage', real);
    }
  });
});

describe('front arcs', () => {
  it('a wedge from the unit: centred on its facing, out to a radius', () => {
    // facing north (towards y = 0), 120 degrees: corners at ±60 degrees
    expect(arcPath({ x: 0, y: 0 }, 0, 60, 100)).toBe('M0 0 L-86.6 -50 A100 100 0 0 1 86.6 -50 Z');
    // wider than a half turn: the long way round; a full turn: a circle (an arc can't end where it starts)
    expect(arcPath({ x: 0, y: 0 }, 180, 135, 10)).toBe('M0 0 L7.1 -7.1 A10 10 0 1 1 -7.1 -7.1 Z');
    expect(arcPath({ x: 10, y: 20 }, 90, 180, 50)).toBe('M-40 20 A50 50 0 1 1 60 20 A50 50 0 1 1 -40 20 Z');
  });

  it('the store gives the selected unit\'s arc: its facing, front arc, close and maximum range', () => {
    const s = createStore(1863);
    s.start();
    expect(s.arcOf('us_1mn')).toMatchObject({ facing: 0, half: 60, close: 150, max: 500 }); // rifled muskets
    expect(s.arcOf('us_bat')).toMatchObject({ close: 500, max: 1600 });      // round shot by default
    s.setOrder('us_bat', { mode: 'ranged', target: 'cs_8al' });
    s.setOrder('us_bat', { ammo: 'canister' });
    expect(s.arcOf('us_bat')).toMatchObject({ close: 100, max: 400 });
  });

  it('melee-only units show their arc a short way out; before the battle, from the default params', () => {
    const s = createStore(1863);
    s.updateUnit(s.units.value[0].id, { stats: '5/5/0/1' });
    expect(s.arcOf(s.units.value[0].id)).toMatchObject({ close: 0, max: 100 });
    expect(s.arcOf(s.units.value[1].id)!.max).toBe(500);
    s.updateUnit(s.units.value[1].id, { stats: 'bad' });
    expect(s.arcOf(s.units.value[1].id)).toBeNull();
  });
});

describe('NATO symbols', () => {
  it('a frame with the arm (infantry X, cavalry diagonal, artillery dot) and the echelon', () => {
    expect(natoSymbol('inf')).toEqual({ arm: 'infantry', echelon: 3 });
    expect(natoSymbol('cav')).toEqual({ arm: 'cavalry', echelon: 3 });
    expect(natoSymbol('art')).toEqual({ arm: 'artillery', echelon: 1 });
    expect(natoSymbol(null)).toEqual({ arm: 'infantry', echelon: 3 });
  });
});

describe('the map', () => {
  const view = () => {
    const store = createStore(1863);
    render(<App store={store} />);
    return store;
  };
  const unit = (name: string) => screen.getByRole('button', { name: new RegExp(`^${name},`) });

  it('shows NATO symbols and labels, and hides them when their layers are off', () => {
    view();
    expect(unit('1st Minnesota').querySelector('.nato.infantry')).not.toBeNull();
    expect(unit('Battery B').querySelector('.nato.artillery')).not.toBeNull();
    expect(unit('1st Minnesota').querySelectorAll('.nato .echelon line')).toHaveLength(3);
    const layers = screen.getByRole('group', { name: 'Map layers' });
    fireEvent.click(within(layers).getByLabelText('NATO symbols'));
    expect(document.querySelector('.nato')).toBeNull();
    fireEvent.click(within(layers).getByLabelText('Names and men'));
    expect(unit('1st Minnesota').querySelector('text')).toBeNull();
    fireEvent.click(within(layers).getByLabelText('Grid'));
    expect(document.querySelector('.field-grid')).toBeNull();
    fireEvent.click(within(layers).getByLabelText('Scale bar'));
    expect(document.querySelector('.scale-bar')).toBeNull();
  });

  it('draws the selected unit\'s front arc; all arcs with the layer on', () => {
    view();
    expect(document.querySelectorAll('.front-arc')).toHaveLength(0);
    act(() => unit('1st Minnesota').focus());
    fireEvent.focus(unit('1st Minnesota'));
    expect(document.querySelectorAll('.front-arc')).toHaveLength(1);
    expect(document.querySelectorAll('.front-arc .close-zone')).toHaveLength(1);
    fireEvent.keyDown(unit('1st Minnesota'), { key: 'Escape' });
    expect(document.querySelectorAll('.front-arc')).toHaveLength(0);
    fireEvent.click(within(screen.getByRole('group', { name: 'Map layers' })).getByLabelText('Front arcs of all units'));
    expect(document.querySelectorAll('.front-arc')).toHaveLength(7);
  });

  it('skips the arc of a unit draft whose stats can\'t be read yet', () => {
    const store = view();
    store.setLayer('allArcs', true);
    act(() => store.updateUnit('us_1mn', { stats: 'half typed' }));
    expect(document.querySelectorAll('.front-arc')).toHaveLength(6);
  });

  it('order arrows have their own layer', () => {
    const store = view();
    fireEvent.click(screen.getByRole('button', { name: 'Start battle' }));
    store.setOrder('us_1mn', { mode: 'ranged', target: 'cs_8al' });
    act(() => store.touch());
    expect(document.querySelectorAll('.order-arrow')).toHaveLength(1);
    fireEvent.click(within(screen.getByRole('group', { name: 'Map layers' })).getByLabelText('Order arrows'));
    expect(document.querySelectorAll('.order-arrow')).toHaveLength(0);
  });

  it('no longer says the engine ignores positions', () => {
    view();
    expect(document.querySelector('.map')!.textContent).not.toMatch(/doesn't use distance/);
    expect(document.querySelector('.map')!.textContent).toMatch(/front arc/);
  });
});
