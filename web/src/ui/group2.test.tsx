// @vitest-environment jsdom
// Rally orders, side modifiers, verdicts and commander ratings in the client.
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/preact';
import { afterEach, describe, expect, it } from 'vitest';

import { ratings } from '../engine';
import { App } from './App';
import { rallyText } from './format';
import { createStore } from './store';
import { closeRanks } from './testing';

afterEach(cleanup);

const started = (mode: 'admin' | 'player' = 'admin') => {
  const s = createStore(1863, mode);
  closeRanks(s);
  s.start();
  return s;
};

/** Break a unit (as if it had routed last round) so it can be ordered to rally. */
const breakUnit = (s: ReturnType<typeof createStore>, uid: string) => {
  const u = s.battle.value!.units.get(uid)!;
  u.morale.forceBreak();
  u.regiment.updateRawMorale(0);
  s.touch();
};

describe('store: rally orders', () => {
  it('a broken unit that can still rally can be given orders; it rallies with no target and no arrow', () => {
    const s = started();
    breakUnit(s, 'cs_8al');
    expect(s.actingUnits.value.map((u) => u.uid)).toContain('cs_8al');
    expect(s.canRally('cs_8al')).toBe(true);
    expect(s.canRally('us_1mn')).toBe(false);
    s.setOrder('cs_8al', { mode: 'rally' });
    expect(s.orders.value.cs_8al).toEqual({ mode: 'rally', target: null, ammo: null, on_break: null });
    expect(s.orderArrows.value.some((a) => a.from === 'cs_8al')).toBe(false);
    expect(s.withoutOrders.value.some((u) => u.uid === 'cs_8al')).toBe(false);
    expect(s.preview.value.error).toBeNull();
  });

  it('the rally is rolled with the round, and does not carry into the next one', () => {
    const s = started();
    breakUnit(s, 'cs_8al');
    s.setOrder('cs_8al', { mode: 'rally' });
    expect(s.resolve()).toBeNull();
    expect(s.history.value[0].rallies.map((r) => r.unit)).toEqual(['cs_8al']);
    expect(s.orders.value.cs_8al.mode).toBe('idle');
    // one try per battle by default: no more rallying for it
    if (s.battle.value!.units.get('cs_8al')!.morale.broken) {
      expect(s.canRally('cs_8al')).toBe(false);
      expect(s.actingUnits.value.some((u) => u.uid === 'cs_8al')).toBe(false);
    }
  });

  it('a player\'s orders file carries their rally orders, and the admin fights them', () => {
    const player = started('player');
    breakUnit(player, 'us_1mn');
    player.setOrder('us_1mn', { mode: 'rally' });
    const plan = JSON.parse(player.planDownload().text);
    expect(plan.orders.us_1mn).toEqual({ mode: 'rally' });
    const admin = started();
    breakUnit(admin, 'us_1mn');
    expect(admin.loadPlans([{ name: 'union.json', text: player.planDownload().text }])).toEqual([]);
    expect(admin.resolve()).toBeNull();
    expect(admin.history.value[0].rallies[0].unit).toBe('us_1mn');
  });
});

describe('store: side modifiers', () => {
  it('the admin sets them per side; they last until changed, and all zero clears a side', () => {
    const s = started();
    s.setSideModifier(1, { fire: -0.2, note: 'short of ammunition' });
    expect(s.sideModifiers.value).toEqual({ 1: { fire: -0.2, melee: 0, morale: 0, note: 'short of ammunition' } });
    s.setOrder('cs_8al', { mode: 'ranged', target: 'us_1mn' });
    const rate = () => s.preview.value.arrows.find((a) => a.attacker === 'cs_8al')!.rate;
    const lowered = rate();
    s.setSideModifier(1, { fire: 0, note: '' });
    expect(s.sideModifiers.value).toEqual({});
    expect(rate()).toBeCloseTo(lowered / 0.8, 12);
    s.setSideModifier(0, { morale: 0.1 });
    expect(s.resolve()).toBeNull();
    expect(s.history.value[0].side_modifiers).toEqual({ 0: { fire: 0, melee: 0, morale: 0.1, note: '' } });
    expect(s.sideModifiers.value).toEqual({ 0: { fire: 0, melee: 0, morale: 0.1, note: '' } });
  });

  it('a value out of range is refused, leaving them as they were', () => {
    const s = started();
    expect(s.setSideModifier(0, { fire: 2 })).toMatch('between -1 and 1');
    expect(s.sideModifiers.value).toEqual({});
  });
});

describe('format', () => {
  it('rallies in words', () => {
    const name = (uid: string) => ({ a: '8th Alabama' }[uid]!);
    expect(rallyText({ unit: 'a', rallied: true, chance: 0.29 }, name)).toBe('8th Alabama rallied (29% chance)');
    expect(rallyText({ unit: 'a', rallied: false, chance: 0.3 }, name)).toBe('8th Alabama failed to rally (30% chance)');
  });
});

describe('the client', () => {
  const view = () => {
    const store = createStore(1863);
    render(<App store={store} />);
    closeRanks(store);
    fireEvent.click(screen.getByRole('button', { name: 'Start battle' }));
    return store;
  };

  it('offers hold or rally for a broken unit, and fire / charge / hold for the others', () => {
    const store = view();
    act(() => breakUnit(store, 'cs_8al'));
    const options = (label: string) => [...(screen.getByLabelText(label) as HTMLSelectElement).options].map((o) => o.value);
    expect(options('8th Alabama action')).toEqual(['idle', 'rally']);
    expect(options('1st Minnesota action')).not.toContain('rally');
    fireEvent.change(screen.getByLabelText('8th Alabama action'), { target: { value: 'rally' } });
    expect(store.orders.value.cs_8al.mode).toBe('rally');
    const row = [...screen.getByRole('table', { name: 'Orders' }).querySelectorAll('tbody tr')]
      .find((tr) => tr.firstElementChild!.textContent === '8th Alabama')!;
    expect(within(row as HTMLElement).queryByLabelText('8th Alabama target')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Fight round 1' }));
    expect(screen.getByRole('list', { name: 'Round 1 rallies' }).textContent).toMatch(/^8th Alabama (rallied|failed)/);
  });

  it('the admin edits side modifiers in percent, and each round lists those in force', () => {
    const store = view();
    fireEvent.input(screen.getByLabelText('Confederate fire % (whole battle)'), { target: { value: '-20' } });
    fireEvent.input(screen.getByLabelText('Confederate note (whole battle)'), { target: { value: 'rain' } });
    expect(store.sideModifiers.value[1]).toEqual({ fire: -0.2, melee: 0, morale: 0, note: 'rain' });
    fireEvent.input(screen.getByLabelText('Union morale % (whole battle)'), { target: { value: '500' } });
    expect(screen.getByRole('alert').textContent).toMatch('between -1 and 1');
    fireEvent.click(screen.getByRole('button', { name: 'Fight round 1' }));
    expect(screen.getByRole('list', { name: 'Round 1 side modifiers' }).textContent).toBe('Confederate: fire -20% (rain)');
  });

  it('the result shows each side\'s verdict and its commander rated as a historical general', () => {
    const store = view();
    fireEvent.change(screen.getByLabelText('1st Minnesota action'), { target: { value: 'ranged' } });
    fireEvent.change(screen.getByLabelText('8th Alabama action'), { target: { value: 'ranged' } });
    fireEvent.click(screen.getByRole('button', { name: 'Fight round 1' }));
    fireEvent.click(screen.getByRole('button', { name: 'Finish the battle' }));
    const summary = screen.getByRole('table', { name: 'Side summary' });
    const row = (label: string) => [...within(summary).getByText(label).parentElement!.children].slice(1)
      .map((td) => td.textContent);
    expect(row('Verdict')).toEqual(store.summary.value!.map((s) => s.verdict));
    const rated = ratings(store.battle.value!.toDict());
    expect(row('Commander rated as')).toEqual(rated.map((r) => `${r.general.name} (${r.general.battle})`));
    expect(row('Expected share / result')).toEqual(
      rated.map((r) => `${Math.round(r.expected * 100)}% / ${Math.round(r.result * 100)}%`));
  });
});
