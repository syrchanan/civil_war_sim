// @vitest-environment jsdom
// The selected unit's vignette: what it shows for each order and state, the ground under it, and the picture.
import { act, cleanup, render } from '@testing-library/preact';
import { signal } from '@preact/signals';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { Terrain } from '../engine';
import { App } from './App';
import { createStore, type Store } from './store';
import { closeRanks } from './testing';
import { UNIFORMS } from './sprites/palette';
import { caption, doing, vignetteOf } from './Vignette';

beforeEach(() => localStorage.clear());
afterEach(cleanup);

function inBattle(): Store {
  const s = createStore(1863);
  closeRanks(s);
  s.start();
  return s;
}

describe('vignetteOf', () => {
  it('nothing selected, nothing shown', () => {
    expect(vignetteOf(inBattle())).toBeNull();
  });

  it('before the battle: the unit standing, on open ground', () => {
    const s = createStore(1863);
    s.selectUnit('us_bat');
    expect(vignetteOf(s)).toEqual({ name: 'Battery B', side: 0, figure: 'art', pose: 'idle', ground: 'open' });
  });

  it('follows the order: firing, charging, in melee once in contact, running once broken', () => {
    const s = inBattle();
    s.selectUnit('us_1mn');
    expect(vignetteOf(s)!.pose).toBe('idle');
    s.setOrder('us_1mn', { mode: 'ranged', target: 'cs_8al' });
    expect(vignetteOf(s)!.pose).toBe('firing');
    s.setOrder('us_1mn', { mode: 'melee', target: 'cs_8al' });
    expect(vignetteOf(s)!.pose).toBe('charging');
    s.battle.value!.contacts.add('cs_8al\u0000us_1mn');
    s.touch();
    expect(vignetteOf(s)!.pose).toBe('melee');
    s.battle.value!.units.get('us_1mn')!.morale.forceBreak();
    s.touch();
    expect(vignetteOf(s)!.pose).toBe('broken');
  });

  it('contact is checked either way round', () => {
    const s = inBattle();
    s.selectUnit('cs_8al');
    s.setOrder('cs_8al', { mode: 'melee', target: 'us_1mn' });
    s.battle.value!.contacts.add('cs_8al\u0000us_1mn');
    s.touch();
    expect(vignetteOf(s)!.pose).toBe('melee');
  });

  it('the unit picking a target is the one shown', () => {
    const s = inBattle();
    s.selectUnit('us_1mn');
    s.clickUnit('us_bat');
    expect(vignetteOf(s)!.name).toBe('Battery B');
  });

  it('the ground under the unit, from the terrain', () => {
    const s = inBattle();
    const b = s.battle.value!;
    (b as { terrain: Terrain | null }).terrain = new Terrain({
      cell: 20, columns: 100, rows: 60, heights: Array(6000).fill(0), ground: 'f'.repeat(6000), meta: {},
    });
    s.touch();
    s.selectUnit('us_1mn');
    expect(vignetteOf(s)!.ground).toBe('forest');
  });

  // states the client can't reach through its own controls: a store standing in for it
  const fake = (unit: object, arrows: object[] = [], extra: object = {}) => ({
    focusedUnit: signal('u'), mapRound: signal(null), terrain: signal(null), battle: signal(null),
    mapUnits: signal([{ uid: 'u', name: 'U', side: 1, type: 'cav', x: 0, y: 0, broken: false, wiped: false, lastSeen: null, ...unit }]),
    orderArrows: signal(arrows), ...extra,
  }) as unknown as Store;

  it('a unit wiped out, or one whose kind is hidden, shows nothing', () => {
    expect(vignetteOf(fake({ wiped: true }))).toBeNull();
    expect(vignetteOf(fake({ type: null }))).toBeNull();
    expect(vignetteOf(fake({}))!.figure).toBe('cav');
  });

  it('fire that can\'t tell (out of range, outside the arc, no line of sight) shows the unit standing', () => {
    expect(vignetteOf(fake({}, [{ from: 'u', to: 'v', mode: 'ranged', blocked: true }]))!.pose).toBe('idle');
    expect(vignetteOf(fake({}, [{ from: 'u', to: 'v', mode: 'ranged', blocked: false }]))!.pose).toBe('firing');
  });

  it('a charge with no battle, or in a round being replayed, is a charge, not melee', () => {
    const charge = [{ from: 'u', to: 'v', mode: 'melee' }];
    expect(vignetteOf(fake({}, charge))!.pose).toBe('charging');
    const battle = signal({ contacts: new Set(['u\u0000v']) });
    expect(vignetteOf(fake({}, charge, { battle, mapRound: signal(1) }))!.pose).toBe('charging');
    expect(vignetteOf(fake({}, charge, { battle }))!.pose).toBe('melee');
  });
});

describe('caption', () => {
  it('says who, what and where', () => {
    const v = { name: '1st Minnesota', side: 0 as const, figure: 'inf' as const, ground: 'forest' as const };
    expect(caption({ ...v, pose: 'firing' })).toBe('1st Minnesota: firing, in the woods');
    expect(caption({ ...v, pose: 'melee', ground: 'rough' })).toBe('1st Minnesota: in melee, on rough ground');
    expect(caption({ ...v, pose: 'broken', ground: 'open' })).toBe('1st Minnesota: broken, running, on open ground');
    expect(caption({ ...v, pose: 'idle' })).toBe('1st Minnesota: standing, in the woods');
    expect(caption({ ...v, pose: 'charging' })).toBe('1st Minnesota: charging, in the woods');
    expect(doing({ ...v, pose: 'charging' })).toBe('Charging, in the woods');
  });
});

describe('on the map', () => {
  it('appears for the selected unit, frames and all, in its side\'s uniform', () => {
    const s = inBattle();
    render(<App store={s} />);
    expect(document.querySelector('.vignette')).toBeNull();
    act(() => {
      s.setOrder('cs_8al', { mode: 'ranged', target: 'us_1mn' });
      s.selectUnit('cs_8al');
    });
    const fig = document.querySelector('.vignette')!;
    expect(fig.querySelector('figcaption')!.textContent).toBe('Firing, on open ground');
    expect(fig.querySelector('svg')!.getAttribute('aria-label')).toBe('8th Alabama: firing, on open ground');
    expect(fig.querySelectorAll('.frame.frames-4')).toHaveLength(4);
    expect(fig.querySelector(`path[fill="${UNIFORMS[1].S}"]`)).not.toBeNull();
    expect(fig.querySelector(`path[fill="${UNIFORMS[0].S}"]`)).toBeNull();
  });

  it('woods get their own sky', () => {
    const s = inBattle();
    (s.battle.value! as { terrain: Terrain | null }).terrain = new Terrain({
      cell: 20, columns: 100, rows: 60, heights: Array(6000).fill(0), ground: 'f'.repeat(6000), meta: {},
    });
    render(<App store={s} />);
    act(() => s.selectUnit('us_1mn'));
    const sky = document.querySelector('.vignette rect')!.getAttribute('fill');
    act(() => {
      (s.battle.value! as { terrain: Terrain | null }).terrain = null;
      s.touch();
    });
    expect(document.querySelector('.vignette rect')!.getAttribute('fill')).not.toBe(sky);
  });
});
