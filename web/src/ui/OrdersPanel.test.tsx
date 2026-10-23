// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/preact';
import { afterEach, describe, expect, it } from 'vitest';

import { App } from './App';
import { createStore } from './store';

afterEach(cleanup);

const started = () => {
  const store = createStore(1863);
  render(<App store={store} />);
  expect(screen.getByText('Start the battle to give orders.')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Start battle' }));
  return store;
};

describe('orders panel', () => {
  it('lists every unit holding, with nothing to preview', () => {
    started();
    const rows = within(screen.getByRole('table', { name: 'Orders' })).getAllByRole('row');
    expect(rows).toHaveLength(1 + 7);
    expect(screen.getByText('No fighting with these orders.')).toBeTruthy();
    expect(screen.getByText('Round 1, from minute 0')).toBeTruthy();
  });

  it('gives fire and charge orders and previews them', () => {
    const store = started();
    fireEvent.change(screen.getByLabelText('Battery B action'), { target: { value: 'ranged' } });
    fireEvent.change(screen.getByLabelText('Battery B target'), { target: { value: 'cs_11al' } });
    fireEvent.change(screen.getByLabelText('Battery B ammo'), { target: { value: 'canister' } });
    fireEvent.change(screen.getByLabelText('Battery B if the target breaks'), { target: { value: 'strongest' } });
    fireEvent.change(screen.getByLabelText('8th Alabama action'), { target: { value: 'melee' } });
    expect(store.orders.value.us_bat).toEqual({ mode: 'ranged', target: 'cs_11al', ammo: 'canister', on_break: 'strongest' });
    expect(store.orders.value.cs_8al).toMatchObject({ mode: 'melee', target: 'us_1mn', on_break: 'fall_back' });
    const preview = screen.getByRole('table', { name: 'Engagements' });
    const rows = within(preview).getAllByRole('row').slice(1).map((r) => r.textContent);
    expect(rows).toHaveLength(2);
    expect(rows.some((r) => r!.startsWith('1st Minnesota8th Alabamaclosing fire'))).toBe(true);
    expect(rows.some((r) => r!.startsWith("Battery B11th Alabamafire"))).toBe(true);
  });

  it('marks broken targets and drops units that can no longer act', () => {
    const store = started();
    act(() => {
      store.battle.value!.units.get('cs_8al')!.morale.forceBreak();
      store.touch();
    });
    fireEvent.change(screen.getByLabelText('1st Minnesota action'), { target: { value: 'ranged' } });
    expect(screen.getByLabelText('1st Minnesota target').textContent).toContain('8th Alabama (broken)');
    expect(screen.queryByLabelText('8th Alabama action')).toBeNull();
  });

  it('shows why orders can not be carried out', () => {
    const store = started();
    act(() => {
      store.orders.value = { ...store.orders.value, us_1mn: { mode: 'ranged', target: 'us_15ma', ammo: null, on_break: 'keep' } };
    });
    expect(screen.getByRole('alert').textContent).toMatch(/same side/);
  });

  it('sets the round length and the events toggle', () => {
    const store = started();
    fireEvent.input(screen.getByLabelText('Round length'), { target: { value: '90' } });
    fireEvent.click(screen.getByLabelText(/Record every casualty/));
    expect([store.duration.value, store.recordEvents.value]).toEqual([90, true]);
  });
});
