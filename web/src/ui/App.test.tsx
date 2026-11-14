// @vitest-environment jsdom
// The shell: header bar, the field with the unit card docked beside it, the tabbed panel, and where it stands.
import { act, cleanup, fireEvent, render, screen } from '@testing-library/preact';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

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
    expect([phaseOf(s), standingText(s)]).toEqual(['battle', 'Round 1']);
    const b = s.battle.value!;
    b.plan = { ...b.plan, rounds_planned: 3, start_clock: '13:00' };
    s.resolve();
    expect(standingText(s)).toBe('Round 2 of 3 · 2:00 pm');
    b.plan = { ...b.plan, phase: 'deployment' };
    expect([phaseOf(s), standingText(s)]).toEqual(['deployment', 'Round 0 · deployment']);
    b.plan = { ...b.plan, phase: 'battle' };
    s.finish(null);
    expect([phaseOf(s), standingText(s)]).toEqual(['end', 'Nightfall · 1 round fought']);
    s.battle.value!.round = 2;
    expect(standingText(s)).toBe('Nightfall · 2 rounds fought');
  });
});

describe('App', () => {
  it('shows the title, the field and the four panels', () => {
    render(<App />);
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Imperial Generals');
    expect(screen.getByRole('heading', { name: 'The field' })).toBeTruthy();
    expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual(['Orders', 'Armies', 'Dispatches', 'Result']);
    expect(screen.getAllByRole('tabpanel')).toHaveLength(4);
  });

  it('opens on the panel the phase needs; a tab picked stays until the phase changes', () => {
    const s = createStore(1863);
    closeRanks(s);
    render(<App store={s} />);
    expect(tab('Armies').getAttribute('aria-selected')).toBe('true');
    fireEvent.click(tab('Result'));
    expect(tab('Result').getAttribute('aria-selected')).toBe('true');
    expect(document.getElementById('panel-result')!.classList.contains('active')).toBe(true);
    expect(document.getElementById('panel-armies')!.classList.contains('active')).toBe(false);
    act(() => { s.start(); });
    expect(tab('Orders').getAttribute('aria-selected')).toBe('true');
    fireEvent.click(tab('Dispatches'));
    expect(tab('Dispatches').getAttribute('aria-selected')).toBe('true');
    act(() => s.finish(null));
    expect(tab('Result').getAttribute('aria-selected')).toBe('true');
  });

  it('names the battle and docks the selected unit\'s card beside the field', () => {
    const s: Store = createStore(1863);
    closeRanks(s);
    s.start();
    s.battle.value!.meta.name = 'The Battle of Example Ridge';
    render(<App store={s} />);
    expect(screen.getByText('The Battle of Example Ridge')).toBeTruthy();
    const dock = screen.getByRole('complementary', { name: 'Selected unit' });
    expect(dock.textContent).toContain('Select a regiment on the map');
    act(() => s.selectUnit('us_1mn'));
    expect(dock.querySelector('.unit-info')).not.toBeNull();
  });
});
