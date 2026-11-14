// @vitest-environment jsdom
// The shell: header bar, the field with the unit card docked beside it, the tabbed panel, and where it stands.
import { act, cleanup, fireEvent, render, screen } from '@testing-library/preact';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { App, phaseOf, standingText } from './App';
import { clockText } from './format';
import { createStore, type Store } from './store';
import { closeRanks } from './testing';

beforeEach(() => localStorage.clear());
afterEach(cleanup);

const tab = (name: string) => screen.getByRole('tab', { name });

describe('the clock', () => {
  it('reads the start plus the minutes fought, on a 12-hour clock', () => {
    expect(clockText(null, 60)).toBeNull();
    expect(clockText('13:00', 0)).toBe('1:00 pm');
    expect(clockText('11:30', 45)).toBe('12:15 pm');
    expect(clockText('00:05', 0)).toBe('12:05 am');
    expect(clockText('23:30', 60)).toBe('12:30 am');
    expect(clockText('09:00', 90.4)).toBe('10:30 am');
  });
});

describe('where the battle stands', () => {
  it('setting up, deploying, round by round, nightfall', () => {
    const s = createStore(1863);
    expect([phaseOf(s), standingText(s)]).toEqual(['setup', 'Setting up']);
    closeRanks(s);
    s.start();
    // the day's plan set up before the battle (the defaults: four rounds from 1 pm)
    expect([phaseOf(s), standingText(s)]).toEqual(['battle', 'Round 1 of 4 · 1:00 pm']);
    const b = s.battle.value!;
    b.plan = { ...b.plan, rounds_planned: 3, start_clock: '13:00' };
    s.resolve();
    expect(standingText(s)).toBe('Round 2 of 3 · 2:00 pm');
    b.plan = { ...b.plan, phase: 'deployment' };
    s.touch(); // the battle changes in place: the store is told
    expect([phaseOf(s), standingText(s)]).toEqual(['deployment', 'Round 0 · deployment']);
    b.plan = { ...b.plan, phase: 'battle' };
    s.touch();
    s.finish(null);
    expect([phaseOf(s), standingText(s)]).toEqual(['end', 'Nightfall · 1 round fought']);
    s.battle.value!.round = 2;
    expect(standingText(s)).toBe('Nightfall · 2 rounds fought');
  });
});

describe('App', () => {
  const tabs = () => screen.getAllByRole('tab').map((t) => t.textContent);
  const open = () => screen.getAllByRole('tab').find((t) => t.getAttribute('aria-selected') === 'true')!.textContent;

  it('shows the title, the field and a sidebar with the setup tabs', () => {
    render(<App />);
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Imperial Generals');
    expect(screen.getByRole('heading', { name: 'The field' })).toBeTruthy();
    expect(screen.getByRole('complementary', { name: 'Sidebar' })).toBeTruthy();
    expect(tabs()).toEqual(['Setup', 'Armies', 'Unit']);
    expect(screen.getAllByRole('tabpanel')).toHaveLength(3);
  });

  it('each phase has its tabs and opens on the one it needs; a tab picked stays until the phase changes', () => {
    const s = createStore(1863);
    s.approve(0);
    s.approve(1);
    render(<App store={s} />);
    expect(open()).toBe('Setup');
    fireEvent.click(tab('Armies'));
    expect(open()).toBe('Armies');
    expect(document.getElementById('panel-armies')!.classList.contains('active')).toBe(true);
    expect(document.getElementById('panel-setup')!.classList.contains('active')).toBe(false);
    act(() => { s.openDeployment(); });
    expect([tabs(), open()]).toEqual([['Deploy', 'Unit', 'Armies'], 'Deploy']);
    act(() => {
      s.battle.value!.openBattle();
      s.touch();
    });
    expect([tabs(), open()]).toEqual([['Unit', 'Orders', 'Recon', 'Armies', 'Dispatches', 'Result'], 'Unit']);
    fireEvent.click(tab('Orders'));
    expect(open()).toBe('Orders');
    act(() => s.finish(null));
    expect([tabs(), open()]).toEqual([['Result', 'Dispatches', 'Recon', 'Armies', 'Unit'], 'Result']);
  });

  it('a unit selected opens the Unit tab; a round fought opens its dispatch', () => {
    const s: Store = createStore(1863);
    closeRanks(s);
    s.start();
    s.battle.value!.meta.name = 'The Battle of Example Ridge';
    render(<App store={s} />);
    expect(screen.getByText('The Battle of Example Ridge')).toBeTruthy();
    const unit = document.getElementById('panel-unit')!;
    expect(unit.textContent).toContain('Select a regiment on the map');
    fireEvent.click(tab('Orders'));
    act(() => s.selectUnit('us_1mn'));
    expect(open()).toBe('Unit');
    expect(unit.querySelector('.unit-info')).not.toBeNull();
    act(() => s.selectUnit(null));
    expect(open()).toBe('Unit');
    fireEvent.click(tab('Orders'));
    act(() => { s.resolve(); });
    expect(open()).toBe('Dispatches');
  });

  it('the sidebar widens and narrows, remembered per viewer', () => {
    render(<App store={createStore(1863)} />);
    const widen = screen.getByRole('button', { name: 'Widen' });
    fireEvent.click(widen);
    expect(document.querySelector('.app')!.classList.contains('wide')).toBe(true);
    expect(localStorage.getItem('imperial-generals:sidebar-wide')).toBe('true');
    cleanup();
    render(<App store={createStore(1863)} />);
    fireEvent.click(screen.getByRole('button', { name: 'Narrow' }));
    expect(document.querySelector('.app')!.classList.contains('wide')).toBe(false);
  });

  it('storage that is blocked: the sidebar starts narrow and the choice lasts for the page', () => {
    const get = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked'); });
    const set = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked'); });
    const s = createStore(1863);
    expect(s.sidebarWide.value).toBe(false);
    s.setWide(true);
    expect(s.sidebarWide.value).toBe(true);
    get.mockRestore();
    set.mockRestore();
  });
});
