// @vitest-environment jsdom
// Orders given from the docked card, and the round strip under the field.
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/preact';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { App } from './App';
import { orderable } from './OrderCard';
import { createStore, type Store } from './store';
import { closeRanks } from './testing';

beforeEach(() => localStorage.clear());
afterEach(cleanup);

function inBattle(mode: 'admin' | 'player' = 'admin'): Store {
  const s = createStore(1863, mode);
  closeRanks(s);
  s.start();
  return s;
}

const card = () => screen.getByRole('region', { name: /^Orders for / });

describe('who the card gives orders to', () => {
  it('the selected unit, while a round is being ordered', () => {
    const s = createStore(1863);
    s.selectUnit('us_1mn');
    expect(orderable(s)).toBeNull(); // no battle yet
    closeRanks(s);
    s.start();
    expect(orderable(s)).toBe('us_1mn');
    s.selectUnit(null);
    expect(orderable(s)).toBeNull();
    s.selectUnit('nobody');
    expect(orderable(s)).toBeNull();
  });

  it('not while replaying, deploying, or once the battle is over', () => {
    const s = inBattle();
    s.selectUnit('us_1mn');
    s.resolve();
    s.mapRound.value = 1;
    expect(orderable(s)).toBeNull();
    s.mapRound.value = null;
    const b = s.battle.value!;
    b.plan = { ...b.plan, phase: 'deployment' };
    expect(orderable(s)).toBeNull();
    b.plan = { ...b.plan, phase: 'battle' };
    s.finish(null);
    expect(orderable(s)).toBeNull();
  });

  it('a player orders only their own units; a broken unit that can\'t rally takes none', () => {
    const p = inBattle('player');
    p.selectUnit('cs_8al');
    expect(orderable(p)).toBeNull();
    p.selectUnit('us_1mn');
    expect(orderable(p)).toBe('us_1mn');
    const s = inBattle();
    const u = s.battle.value!.units.get('us_1mn')!;
    u.morale.forceBreak();
    u.rallyAttempts = 99;
    s.touch();
    s.selectUnit('us_1mn');
    expect(orderable(s)).toBeNull();
  });
});

describe('the card', () => {
  it('sets the action, the target, and what to do if the target breaks', () => {
    const s = inBattle();
    render(<App store={s} />);
    act(() => s.selectUnit('us_1mn'));
    const c = card();
    expect(within(c).getAllByRole('button').map((b) => b.textContent)).toEqual(['Fire', 'Charge', 'Hold']);
    fireEvent.click(within(c).getByRole('button', { name: 'Fire' }));
    expect(s.orders.value.us_1mn.mode).toBe('ranged');
    expect(within(card()).getByRole('button', { name: 'Fire' }).getAttribute('aria-pressed')).toBe('true');
    act(() => {
      s.battle.value!.units.get('cs_11al')!.morale.forceBreak();
      s.touch();
    });
    expect(within(card()).getByRole('option', { name: '11th Alabama (broken)' })).toBeTruthy();
    fireEvent.change(within(card()).getByLabelText('Target'), { target: { value: 'cs_10al' } });
    expect(s.orders.value.us_1mn.target).toBe('cs_10al');
    expect(card().querySelector('.range-note')!.textContent).toMatch(/yd/);
    fireEvent.change(within(card()).getByLabelText('If the target breaks'), { target: { value: 'weakest' } });
    expect(s.orders.value.us_1mn.on_break).toBe('weakest');
    fireEvent.click(within(card()).getByRole('button', { name: 'Hold' }));
    expect(s.orders.value.us_1mn.mode).toBe('idle');
    expect(within(card()).queryByLabelText('Target')).toBeNull();
  });

  it('a battery picks its ammunition; fire that can\'t reach is marked', () => {
    const s = inBattle();
    render(<App store={s} />);
    act(() => {
      s.selectUnit('us_bat');
      s.setOrder('us_bat', { mode: 'ranged', target: 'cs_8al' });
    });
    fireEvent.change(within(card()).getByLabelText('Ammunition'), { target: { value: 'canister' } });
    expect(s.orders.value.us_bat.ammo).toBe('canister');
    act(() => s.moveUnit('us_bat', { x: 1000, y: 1190 }));
    act(() => s.moveUnit('cs_8al', { x: 1000, y: 10 }));
    expect(card().querySelector('.range-note.problems')).not.toBeNull(); // out of range
    act(() => s.moveUnit('cs_8al', { x: 1000, y: 1000 }));
    act(() => s.faceUnit('us_bat', 180));
    expect(card().querySelector('.range-note.problems')!.textContent).toMatch(/outside its front arc/);
    act(() => s.faceUnit('us_bat', 0));
    expect(card().querySelector('.range-note.problems')).toBeNull();
  });

  it('a broken unit can hold or try to rally', () => {
    const s = inBattle();
    s.battle.value!.units.get('us_1mn')!.morale.forceBreak();
    s.touch();
    render(<App store={s} />);
    act(() => s.selectUnit('us_1mn'));
    expect(within(card()).getAllByRole('button').map((b) => b.textContent)).toEqual(['Hold', 'Rally']);
  });
});

describe('the round strip', () => {
  const strip = () => screen.getByRole('navigation', { name: 'The day' });

  it('none before the battle', () => {
    render(<App store={createStore(1863)} />);
    expect(screen.queryByRole('navigation', { name: 'The day' })).toBeNull();
  });

  it('rounds fought (shown on the map as they began), the round now, the rounds planned, nightfall', () => {
    const s = inBattle();
    const b = s.battle.value!;
    b.plan = { ...b.plan, rounds_planned: 4, start_clock: '13:00' };
    s.resolve();
    render(<App store={s} />);
    expect([...strip().children].map((e) => e.textContent)).toEqual([
      'The day', 'Round 1 · 1:00 pm', 'Round 2 · orders', 'Round 3', 'Round 4', 'Nightfall',
    ]);
    fireEvent.click(within(strip()).getByRole('button', { name: 'Round 1 · 1:00 pm' }));
    expect(s.mapRound.value).toBe(1);
    expect(within(strip()).getByRole('button', { name: 'Round 1 · 1:00 pm' }).getAttribute('aria-pressed')).toBe('true');
    fireEvent.click(within(strip()).getByRole('button', { name: 'Round 2 · orders' }));
    expect(s.mapRound.value).toBeNull();
  });

  it('with no clock or plan; deploying; at nightfall', () => {
    const s = inBattle();
    s.resolve();
    render(<App store={s} />);
    expect([...strip().children].map((e) => e.textContent)).toEqual(['The day', 'Round 1', 'Round 2 · orders', 'Nightfall']);
    act(() => {
      s.battle.value!.plan = { ...s.battle.value!.plan, phase: 'deployment' };
      s.touch();
    });
    expect(within(strip()).getByRole('button', { name: 'Round 0 · deployment' })).toBeTruthy();
    act(() => {
      s.battle.value!.plan = { ...s.battle.value!.plan, phase: 'battle', rounds_planned: 1 };
      s.finish(null);
    });
    expect([...strip().children].map((e) => e.textContent)).toEqual(['The day', 'Round 1', 'Nightfall']);
    fireEvent.click(within(strip()).getByRole('button', { name: 'Round 1' }));
    fireEvent.click(within(strip()).getByRole('button', { name: 'Nightfall' }));
    expect(s.mapRound.value).toBeNull();
  });
});
