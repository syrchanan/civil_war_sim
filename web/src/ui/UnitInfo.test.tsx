// @vitest-environment jsdom
// The selected unit's details under the map: what it is, how it stands, what it is doing and where.
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/preact';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { Terrain } from '../engine';
import { App } from './App';
import { createStore, type Store } from './store';
import { closeRanks } from './testing';
import { STATS_LABEL, unitInfoOf } from './UnitInfo';

beforeEach(() => localStorage.clear());
afterEach(cleanup);

const rows = (s: Store) => Object.fromEntries(unitInfoOf(s)!.rows);

function inBattle(mode: 'admin' | 'player' = 'admin'): Store {
  const s = createStore(1863, mode);
  closeRanks(s);
  s.start();
  return s;
}

describe('unitInfoOf', () => {
  it('nothing selected, nothing shown', () => {
    expect(unitInfoOf(createStore(1863))).toBeNull();
  });

  it('before the battle: the unit as drafted, with no order or status', () => {
    const s = createStore(1863);
    s.selectUnit('us_1mn');
    const v = unitInfoOf(s)!;
    expect(v.name).toBe('1st Minnesota');
    expect(v.kind).toBe('Line infantry, Union');
    expect(v.rows).toEqual([['Men', '900'], [STATS_LABEL, '6/6/1/0']]);
  });

  it('a battery: its guns and its kind of guns', () => {
    const s = createStore(1863);
    s.selectUnit('us_bat');
    expect(unitInfoOf(s)!.kind).toBe('Battery, 8 guns, Union');
    expect(rows(s)[STATS_LABEL]).toBe('5/5/0/0');
    s.updateUnit('us_bat', { guns: 1 });
    expect(unitInfoOf(s)!.kind).toBe('Battery, 1 gun, Union');
  });

  it('stats as players write them, live morale included; stats that don\'t read', () => {
    const s = createStore(1863);
    s.selectUnit('us_1mn');
    s.updateUnit('us_1mn', { stats: 'x' });
    expect(rows(s)[STATS_LABEL]).toBe('not valid');
    s.updateUnit('us_1mn', { stats: '5/5/-2/1' });
    expect(rows(s)[STATS_LABEL]).toBe('5/5/-2/1');
    s.start();
    s.battle.value!.units.get('us_1mn')!.regiment.stats = [5, 3, -2, 1];
    s.touch();
    expect(rows(s)[STATS_LABEL]).toBe('5/3/-2/1');
  });

  it('in battle: men left, morale left, and the order in one line with its target and range', () => {
    const s = inBattle();
    s.selectUnit('us_1mn');
    expect(rows(s)).toEqual({
      Men: '900 of 900', [STATS_LABEL]: '6/6/1/0', Status: 'Steady, 100% morale left',
      Order: 'Hold',
    });
    s.setOrder('us_1mn', { mode: 'ranged', target: 'cs_8al' });
    expect(rows(s).Order).toBe('Fire on 8th Alabama, 60 yd, full effect');
    s.setOrder('us_1mn', { mode: 'melee', target: 'cs_8al' });
    expect(rows(s).Order).toBe('Charge 8th Alabama, 60 yd');
  });

  it('a battery\'s ammunition', () => {
    const s = inBattle();
    s.selectUnit('us_bat');
    s.setOrder('us_bat', { mode: 'ranged', target: 'cs_8al' });
    s.setOrder('us_bat', { ammo: 'canister' });
    expect(rows(s).Order).toBe('Fire (canister) on 8th Alabama, 60 yd, full effect');
  });

  it('broken, wiped out, rallied', () => {
    const s = inBattle();
    s.selectUnit('us_1mn');
    const u = s.battle.value!.units.get('us_1mn')!;
    u.rallied = true;
    s.touch();
    expect(rows(s).Status).toBe('Rallied, steady, 100% morale left');
    u.morale.forceBreak();
    s.touch();
    expect(rows(s).Status).toBe('Broken');
    u.regiment.updateSize(0);
    s.touch();
    expect(rows(s).Status).toBe('Wiped out');
  });

  it('a player sees only what could be seen of a foe: men roughly, broken or not, what they expect of it', () => {
    const s = inBattle('player');
    s.selectUnit('cs_bat');
    expect(unitInfoOf(s)!.kind).toBe('Battery, Confederate');
    expect(rows(s)).toEqual({ Men: '~70', Status: 'Steady', Expected: rows(s).Expected });
    s.setOrder('cs_bat', { mode: 'ranged', target: 'us_1mn' });
    s.setOrder('cs_bat', { ammo: 'canister' });
    expect(rows(s).Expected).toBe('Fire on 1st Minnesota, 60 yd, full effect');
    const u = s.battle.value!.units.get('cs_bat')!;
    u.rallied = true;
    s.touch();
    expect(rows(s).Status).toBe('Steady');
    s.selectUnit('us_1mn');
    expect(rows(s)[STATS_LABEL]).toBeDefined();
    expect(rows(s).Status).toMatch(/morale left/);
  });

  it('before the battle a player sees both armies they are drafting in full', () => {
    const s = createStore(1863, 'player');
    s.selectUnit('cs_8al');
    expect(rows(s)[STATS_LABEL]).toBe('5/6/0/0');
  });

  it('an enemy whose details are hidden (a player file): men roughly, no stats', () => {
    const admin = inBattle();
    const player = createStore(1, 'player');
    player.open(admin.playerFileDownload(0).text);
    player.selectUnit('cs_bat');
    expect(rows(player).Men).toMatch(/^~\d/);
    expect(rows(player)[STATS_LABEL]).toBeUndefined();
    expect(unitInfoOf(player)!.kind).toBe('Battery, Confederate');
  });

  it('replaying a round: the orders given for it, the distance from where the units stood', () => {
    const s = inBattle();
    s.setOrder('us_1mn', { mode: 'ranged', target: 'cs_8al' });
    s.resolve();
    s.mapRound.value = 1;
    s.selectUnit('us_1mn');
    expect(rows(s).Order).toBe('Fire on 8th Alabama, 60 yd');
  });

  it('replaying a round: a unit that gave no order for it (it was already broken) shows none', () => {
    const s = inBattle();
    s.battle.value!.units.get('cs_11al')!.morale.forceBreak();
    s.resolve();
    s.mapRound.value = 1;
    s.selectUnit('cs_11al');
    expect(s.battle.value!.history[0].orders.cs_11al).toBeUndefined();
    expect(rows(s).Order).toBeUndefined();
  });

  it('a plain regiment (no kind, as a state file may hold): its details, and no picture', () => {
    const s = inBattle();
    const data = JSON.parse(s.download().text);
    const unit = data.units.find((u: { id: string }) => u.id === 'us_1mn');
    unit.type = null;
    unit.subtype = null;
    const plain = createStore(1);
    plain.open(JSON.stringify(data));
    plain.selectUnit('us_1mn');
    expect(unitInfoOf(plain)!.kind).toBe('Unknown kind, Union');
    render(<App store={plain} />);
    expect(document.querySelector('.unit-info')).not.toBeNull();
    expect(document.querySelector('.vignette')).toBeNull();
  });

  it('once the battle is over there is no order', () => {
    const s = inBattle();
    s.finish(null);
    s.selectUnit('us_1mn');
    expect(rows(s).Order).toBeUndefined();
  });

  it('the ground and height under the unit, shown only when there is terrain', () => {
    const s = inBattle();
    s.selectUnit('us_1mn');
    expect(rows(s).Ground).toBeUndefined();
    (s.battle.value! as { terrain: Terrain | null }).terrain = new Terrain({
      cell: 20, columns: 100, rows: 60, heights: Array(6000).fill(12), ground: 'r'.repeat(6000), meta: {},
    });
    s.touch();
    expect(rows(s).Ground).toBe('Rough ground, 12 yd up');
    (s.battle.value! as { terrain: Terrain | null }).terrain = new Terrain({
      cell: 20, columns: 100, rows: 60, heights: Array(6000).fill(0), ground: 'o'.repeat(6000), meta: {},
    });
    s.touch();
    expect(rows(s).Ground).toBe('Open ground'); // heights are above the lowest ground: 0 says nothing
  });
});

describe('on the map', () => {
  it('shows the selected unit\'s picture and details', () => {
    const s = inBattle();
    render(<App store={s} />);
    expect(document.querySelector('.unit-info')).toBeNull();
    act(() => s.selectUnit('us_1mn'));
    const box = screen.getByRole('region', { name: '1st Minnesota: details' });
    expect(within(box).getByRole('heading', { name: '1st Minnesota' })).toBeTruthy();
    expect(within(box).getByText('Line infantry, Union')).toBeTruthy();
    expect(within(box).getByText(STATS_LABEL)).toBeTruthy();
    expect(within(box).getByText('6/6/1/0')).toBeTruthy();
    expect(within(box).getByRole('img', { name: '1st Minnesota: standing, on open ground' })).toBeTruthy();
  });

  it('after giving an order on the map, the unit given it stays selected, not its target', () => {
    const s = inBattle();
    render(<App store={s} />);
    const block = (name: RegExp) => screen.getByRole('button', { name });
    const mine = block(/^1st Minnesota,/);
    const enemy = block(/^8th Alabama,/);
    act(() => {
      fireEvent.focus(mine);
      fireEvent.click(mine);
    });
    act(() => {
      fireEvent.focus(enemy); // clicking a unit focuses it first
      fireEvent.click(enemy);
    });
    act(() => { fireEvent.click(screen.getByRole('button', { name: 'Fire' })); });
    expect(s.focusedUnit.value).toBe('us_1mn');
    expect(screen.getByRole('region', { name: '1st Minnesota: details' })).toBeTruthy();

    // the same when the choice is cancelled
    act(() => {
      fireEvent.click(mine);
      fireEvent.focus(enemy);
      fireEvent.click(enemy);
    });
    act(() => { fireEvent.click(screen.getByRole('button', { name: 'Cancel' })); });
    expect(s.focusedUnit.value).toBe('us_1mn');
  });
});
