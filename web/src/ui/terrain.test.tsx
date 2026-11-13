// @vitest-environment jsdom
// Terrain in the client: chosen before the battle, generated from the seed, saved with the battle, drawn as layers.
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/preact';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { App } from './App';
import { groundRuns, reliefRuns } from './MapView';
import { createStore } from './store';
import { generateTerrain, threshold } from './terrainGen';

beforeEach(() => localStorage.clear());
afterEach(cleanup);

describe('store: terrain', () => {
  it('an open field by default; a preset generates ground from the seed, shown before the battle', () => {
    const s = createStore(1863);
    expect(s.terrainPreset.value).toBe('none');
    expect(s.terrain.value).toBeNull();
    s.terrainPreset.value = 'hills';
    expect(s.terrain.value!.toDict()).toEqual(generateTerrain('hills', 1863));
    s.seed.value = 7;
    expect(s.terrain.value!.meta.seed).toBe(7);
  });

  it('the battle starts on that ground, saves it, and opening a battle shows its own', () => {
    const s = createStore(1863);
    s.terrainPreset.value = 'forest';
    s.start();
    expect(s.battle.value!.terrain!.toDict()).toEqual(generateTerrain('forest', 1863));
    expect(s.terrain.value).toBe(s.battle.value!.terrain);
    const saved = s.download().text;
    const other = createStore(1);
    expect(other.open(saved)).toBeNull();
    expect(other.terrain.value!.toDict()).toEqual(generateTerrain('forest', 1863));
    expect(other.terrainPreset.value).toBe('forest');
  });

  it('a battle without terrain opens as an open field', () => {
    const s = createStore(1863);
    s.start();
    const other = createStore(1);
    other.terrainPreset.value = 'hills';
    other.open(s.download().text);
    expect(other.terrain.value).toBeNull();
    expect(other.terrainPreset.value).toBe('none');
  });
});

describe('relief runs', () => {
  it('merge neighbouring cells of a row that fall in the same height band', () => {
    const t = { cell: 10, columns: 4, rows: 2, heights: [0, 1, 9, 10, 10, 10, 10, 0], ground: 'oooooooo', meta: {} };
    // 0..10 in 5 bands of 2 yards: bands 0 0 4 4 / 4 4 4 0 (the top of the range is in the top band)
    expect(reliefRuns(t, 5)).toEqual([
      { x: 0, y: 0, width: 20, band: 0 }, { x: 20, y: 0, width: 20, band: 4 },
      { x: 0, y: 10, width: 30, band: 4 }, { x: 30, y: 10, width: 10, band: 0 },
    ]);
    const flat = { ...t, heights: Array(8).fill(3) };
    expect(reliefRuns(flat, 5)).toEqual([{ x: 0, y: 0, width: 40, band: 0 }, { x: 0, y: 10, width: 40, band: 0 }]);
  });
});

describe('ground runs and the woods threshold', () => {
  it('runs of the same ground along a row; open ground breaks them, and so does a change of ground', () => {
    const t = { cell: 10, columns: 5, rows: 1, ground: 'ffrro' };
    expect(groundRuns(t)).toEqual([{ x: 0, y: 0, width: 20, code: 'f' }, { x: 20, y: 0, width: 20, code: 'r' }]);
    expect(groundRuns({ ...t, ground: 'fofoo' })).toEqual([{ x: 0, y: 0, width: 10, code: 'f' },
      { x: 20, y: 0, width: 10, code: 'f' }]);
  });

  it('the share of values at or above the threshold; none at a share of 0', () => {
    expect(threshold([5, 1, 4, 2, 3], 0.4)).toBe(4);
    expect(threshold([5, 1, 4, 2, 3], 0)).toBe(Infinity);
    expect(threshold([5, 1], 0.1)).toBe(5);
  });
});

describe('the client', () => {
  it('picks the ground before the battle, and draws relief and woods as layers', () => {
    const store = createStore(1863);
    render(<App store={store} />);
    expect(document.querySelector('.terrain')).toBeNull();
    fireEvent.change(screen.getByLabelText('Ground'), { target: { value: 'forest' } });
    expect(store.terrainPreset.value).toBe('forest');
    expect(document.querySelectorAll('.relief rect').length).toBeGreaterThan(0);
    expect(document.querySelectorAll('.woods rect').length).toBeGreaterThan(0);
    fireEvent.change(screen.getByLabelText('Ground'), { target: { value: 'mountains' } });
    expect(document.querySelectorAll('.woods .rough').length).toBeGreaterThan(0);
    const layers = screen.getByRole('group', { name: 'Map layers' });
    fireEvent.click(within(layers).getByLabelText('Relief'));
    expect(document.querySelector('.relief')).toBeNull();
    fireEvent.click(within(layers).getByLabelText('Woods and rough ground'));
    expect(document.querySelector('.woods')).toBeNull();
    act(() => { store.setLayer('relief', true); });
    fireEvent.click(screen.getByRole('button', { name: 'Start battle' }));
    expect(screen.queryByLabelText('Ground')).toBeNull();               // fixed once the battle starts
    expect(document.querySelectorAll('.relief rect').length).toBeGreaterThan(0);
  });

  it('a unit\'s label says the height and ground it stands on', () => {
    const store = createStore(1863);
    store.terrainPreset.value = 'hills';
    render(<App store={store} />);
    const t = store.terrain.value!;
    const u = store.mapUnits.value[0];
    const label = screen.getByRole('button', { name: /^1st Minnesota,/ }).getAttribute('aria-label')!;
    expect(label).toContain(`, ${Math.round(t.heightAt(u.x, u.y))} yd up on ${t.groundAt(u.x, u.y)} ground`);
  });
});
