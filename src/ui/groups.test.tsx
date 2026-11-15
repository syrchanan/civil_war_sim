// @vitest-environment jsdom
// Brigades and divisions: outlined on the map, selected, and ordered as one (each regiment at the nearest it can reach).
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/preact';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { App } from './App';
import { createStore, groupKey, groupName, groupOf, type GroupRef, loadGroups, type Store } from './store';
import { closeRanks } from './testing';

beforeEach(() => localStorage.clear());
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const HARROW: GroupRef = { side: 0, level: 'brigade', division: 'Gibbon', brigade: 'Harrow' };
const KEMPER: GroupRef = { side: 1, level: 'brigade', division: 'Pickett', brigade: 'Kemper' };
const GIBBON: GroupRef = { side: 0, level: 'division', division: 'Gibbon', brigade: null };

/** The example armies in brigades, drawn up face to face at close range. */
function organised(mode: 'admin' | 'player' = 'admin', start = true): Store {
  const s = createStore(1863, mode);
  const org: Record<string, { division: string; brigade: string }> = {
    us_1mn: { division: 'Gibbon', brigade: 'Harrow' }, us_15ma: { division: 'Gibbon', brigade: 'Harrow' },
    us_bat: { division: 'Gibbon', brigade: 'Artillery' },
    cs_8al: { division: 'Pickett', brigade: 'Kemper' }, cs_10al: { division: 'Pickett', brigade: 'Kemper' },
    cs_11al: { division: 'Pickett', brigade: 'Garnett' },
  };
  s.units.value = s.units.value.map((u) => ({ ...u, org: org[u.id] }));
  closeRanks(s);
  if (start) s.start();
  return s;
}

describe('groups', () => {
  it('a unit\'s group at each level, its key and its name', () => {
    expect(groupOf(0, { division: 'Gibbon', brigade: 'Harrow' }, 'brigade')).toEqual(HARROW);
    expect(groupOf(0, { division: 'Gibbon', brigade: 'Harrow' }, 'division')).toEqual(GIBBON);
    expect(groupOf(0, { brigade: 'Harrow' }, 'brigade')).toBeNull();
    expect(groupOf(0, { division: 'Gibbon' }, 'brigade')).toBeNull();
    expect([groupKey(HARROW), groupKey(GIBBON)]).toEqual(['0|Gibbon|Harrow', '0|Gibbon|']);
    expect([groupName(HARROW), groupName(GIBBON)]).toEqual(['Harrow', 'Gibbon']);
  });

  it('the map grouping is remembered; storage blocked or holding anything else: regiments', () => {
    const s = createStore(1863);
    s.setMapGroups('division');
    expect(loadGroups()).toBe('division');
    localStorage.setItem('imperial-generals:map-groups', 'corps');
    expect(loadGroups()).toBe('regiment');
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked'); });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked'); });
    expect(loadGroups()).toBe('regiment');
    s.setMapGroups('brigade');
    expect(s.mapGroups.value).toBe('brigade');
  });
});

describe('outlines on the map', () => {
  const labels = () => [...document.querySelectorAll('.group text')].map((t) => t.textContent);

  it('brigades or divisions outlined and labelled; regiment labels give way; units with no org have none', () => {
    const s = organised();
    // stacked labels give way: brigades side by side have room for theirs
    s.moveUnit('us_bat', { x: 1700, y: 630 });
    s.moveUnit('cs_11al', { x: 1700, y: 570 });
    render(<App store={s} />);
    const outline = within(screen.getByRole('group', { name: 'Outline' }));
    expect(document.querySelectorAll('.group')).toHaveLength(0);
    expect(document.querySelectorAll('.map-unit text .unit-name').length).toBe(4); // stacked: one a side, and the two moved
    fireEvent.click(outline.getByRole('button', { name: 'Brigades' }));
    expect(labels()).toEqual(['Harrow · 2 regts · 1,600', 'Artillery · 1 regt · 72', 'Kemper · 2 regts · 1,800',
      'Garnett · 1 regt · 600']);
    expect(document.querySelectorAll('.map-unit text .unit-name').length).toBe(0);
    fireEvent.click(outline.getByRole('button', { name: 'Divisions' }));
    expect(labels()).toEqual(['Gibbon · 3 regts · 1,672', 'Pickett · 3 regts · 2,400']);
    const rect = document.querySelector('.group rect')!;
    expect(Number(rect.getAttribute('width'))).toBeGreaterThan(0);
  });

  it('before the battle, from the drafts; the enemy\'s men roughly, from a player\'s view', () => {
    const s = organised('admin', false);
    s.setMapGroups('brigade');
    render(<App store={s} />);
    expect(labels()[0]).toBe('Harrow · 2 regts · 1,600');
    cleanup();
    const p = organised('player');
    p.setMapGroups('brigade');
    render(<App store={p} />);
    expect(labels()).toContain('Kemper · 2 regts · ~1,800');
  });

  it('a label selects its group (mouse or keyboard); the card opens; a regiment selected gives way', () => {
    const s = organised();
    s.setMapGroups('brigade');
    render(<App store={s} />);
    fireEvent.click(screen.getByRole('button', { name: 'Select Harrow' }));
    expect(s.selectedGroup.value).toEqual(HARROW);
    expect(document.querySelector('.group.selected text')!.textContent).toMatch(/^Harrow/);
    expect(screen.getByRole('tab', { name: 'Unit' }).getAttribute('aria-selected')).toBe('true');
    expect(screen.getByRole('region', { name: 'Harrow' })).toBeTruthy();
    fireEvent.keyDown(screen.getByRole('button', { name: 'Select Kemper' }), { key: 'Enter' });
    expect(s.selectedGroup.value).toEqual(KEMPER);
    fireEvent.keyDown(screen.getByRole('button', { name: 'Select Harrow' }), { key: ' ' });
    fireEvent.keyDown(screen.getByRole('button', { name: 'Select Kemper' }), { key: 'x' });
    expect(s.selectedGroup.value).toEqual(HARROW);
    act(() => s.selectUnit('us_1mn'));
    expect(s.selectedGroup.value).toBeNull();
    act(() => s.selectGroup(HARROW));
    act(() => s.selectGroup(null));
    expect(s.focusedUnit.value).toBeNull();
  });
});

describe('ordering a group', () => {
  it('fire: each regiment at the nearest of the target brigade it can reach; charge; hold', () => {
    const s = organised();
    expect(s.enemyBrigades(HARROW).map(groupName)).toEqual(['Kemper', 'Garnett']);
    expect(s.orderGroup(HARROW, 'ranged', KEMPER)).toEqual({ reached: 2, of: 2 });
    expect(['us_1mn', 'us_15ma'].map((u) => [s.effectiveOrders.value[u].mode, s.effectiveOrders.value[u].target]))
      .toEqual([['ranged', 'cs_8al'], ['ranged', 'cs_8al']]);
    expect(s.orderGroup(GIBBON, 'melee', KEMPER)).toEqual({ reached: 3, of: 3 });
    expect(s.effectiveOrders.value.us_bat.mode).toBe('melee');
    expect(s.orderGroup(HARROW, 'idle', null)).toEqual({ reached: 0, of: 2 });
    expect(s.effectiveOrders.value.us_1mn.mode).toBe('idle');
  });

  it('a regiment that can\'t reach, or can\'t fire at all, holds; broken ones are left alone', () => {
    const s = organised();
    s.moveUnit('us_15ma', { x: 100, y: 1150 }); // far out of range
    s.battle.value!.units.get('us_bat')!.morale.forceBreak();
    s.touch();
    expect(s.orderGroup(HARROW, 'ranged', KEMPER)).toEqual({ reached: 1, of: 2 });
    expect(s.effectiveOrders.value.us_15ma.mode).toBe('idle');
    expect(s.orderGroup(GIBBON, 'ranged', KEMPER)).toEqual({ reached: 1, of: 2 }); // the broken battery not counted
    const b = s.battle.value!;
    b.units.get('us_1mn')!.regiment.updateStats('5/5/0/1'); // melee only: can't fire
    s.touch();
    expect(s.orderGroup(HARROW, 'ranged', KEMPER)).toEqual({ reached: 0, of: 2 });
  });

  it('the card: against a brigade in sight, the order\'s reach, and those changed by hand since', () => {
    const s = organised();
    render(<App store={s} />);
    act(() => s.selectGroup(HARROW));
    const card = within(screen.getByRole('region', { name: 'Harrow' }));
    expect(card.getByText('Gibbon · 2 regiments · 1,600 of 1,600 men, 2 standing')).toBeTruthy();
    fireEvent.change(card.getByLabelText('Against'), { target: { value: groupKey({ ...KEMPER, brigade: 'Garnett' }) } });
    fireEvent.click(card.getByRole('button', { name: 'Fire' }));
    expect(card.getByRole('status').textContent).toBe('2 of 2 in range; the rest hold.');
    expect(s.effectiveOrders.value.us_1mn.target).toBe('cs_11al');
    act(() => s.setOrder('us_1mn', { target: 'cs_8al' }));
    expect(card.getByText('1 changed by hand since.')).toBeTruthy();
    fireEvent.click(card.getByRole('button', { name: 'Charge' }));
    expect(card.getByRole('status').textContent).toBe('2 of 2 charging; the rest hold.');
    fireEvent.click(card.getByRole('button', { name: 'Hold' }));
    expect(card.getByRole('status').textContent).toBe('All 2 holding.');
    act(() => s.selectGroup(GIBBON));
    expect(within(screen.getByRole('region', { name: 'Gibbon' })).getByText(/^3 regiments · /)).toBeTruthy();
    expect(screen.queryByRole('status')).toBeNull(); // the last result was another group's
    fireEvent.click(within(screen.getByRole('region', { name: 'Gibbon' })).getByRole('button', { name: 'Battery B' }));
    expect([s.focusedUnit.value, s.selectedGroup.value]).toEqual(['us_bat', null]);
  });

  it('a player orders their own; a battery alone is one regiment; an enemy group counts only what was seen', () => {
    const p = organised('player');
    render(<App store={p} />);
    act(() => p.selectGroup(HARROW));
    expect(within(screen.getByRole('region', { name: 'Harrow' })).getByRole('button', { name: 'Fire' })).toBeTruthy();
    act(() => p.selectGroup({ ...HARROW, brigade: 'Artillery' }));
    expect(screen.getByText(/^Gibbon · 1 regiment · /)).toBeTruthy();
    // the 10th Alabama only last seen, the 8th not seen at all
    vi.spyOn(p, 'seenNow').mockImplementation((uid) => uid !== 'cs_8al' && uid !== 'cs_10al');
    vi.spyOn(p, 'lastSeenRound').mockImplementation((uid) => (uid === 'cs_10al' ? 1 : null));
    act(() => p.selectGroup(KEMPER));
    expect(screen.getByText(/^Pickett · 1 regiment · ~800 men$/)).toBeTruthy();
  });

  it('regiments not placed: none is out of reach, and all are as near', () => {
    const s = organised();
    s.battle.value!.units.get('cs_8al')!.regiment.position = null;
    s.battle.value!.units.get('us_1mn')!.regiment.position = null;
    s.touch();
    expect(s.orderGroup(HARROW, 'ranged', KEMPER)).toEqual({ reached: 2, of: 2 });
    expect(s.orderGroup(HARROW, 'melee', KEMPER)).toEqual({ reached: 2, of: 2 });
  });

  it('no order: an enemy group, nothing in sight, while deploying or replaying, or once the battle is over', () => {
    const p = organised('player');
    render(<App store={p} />);
    act(() => p.selectGroup(KEMPER));
    const enemy = within(screen.getByRole('region', { name: 'Kemper' }));
    expect(enemy.getByText(/~1,800 men$/)).toBeTruthy();
    expect(enemy.queryByRole('button', { name: 'Fire' })).toBeNull();
    cleanup();

    const s = organised();
    for (const u of ['cs_8al', 'cs_10al', 'cs_11al', 'cs_bat']) s.battle.value!.units.get(u)!.regiment.updateSize(0);
    s.touch();
    render(<App store={s} />);
    act(() => s.selectGroup(HARROW));
    expect(screen.getByText('No enemy brigade in sight to order against.')).toBeTruthy();
    cleanup();

    const r = organised();
    r.resolve();
    render(<App store={r} />);
    act(() => {
      r.selectGroup(HARROW);
      r.mapRound.value = 1;
    });
    expect(screen.queryByRole('button', { name: 'Fire' })).toBeNull();
    cleanup();

    const f = organised();
    f.finish(null);
    render(<App store={f} />);
    act(() => f.selectGroup(HARROW));
    expect(screen.queryByRole('button', { name: 'Fire' })).toBeNull();
    cleanup();

    const d = organised('admin', false);
    d.approve(0);
    d.approve(1);
    d.openDeployment();
    render(<App store={d} />);
    act(() => d.selectGroup(HARROW));
    expect(screen.getByRole('region', { name: 'Harrow' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Fire' })).toBeNull();
  });
});
