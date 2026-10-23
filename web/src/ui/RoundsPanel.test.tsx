// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/preact';
import { afterEach, describe, expect, it } from 'vitest';

import { App } from './App';
import { createStore } from './store';

afterEach(cleanup);

const started = () => {
  const store = createStore(1863);
  render(<App store={store} />);
  fireEvent.click(screen.getByRole('button', { name: 'Start battle' }));
  return store;
};

const order = (unit: string, action: string, target?: string) => {
  fireEvent.change(screen.getByLabelText(`${unit} action`), { target: { value: action } });
  if (target) fireEvent.change(screen.getByLabelText(`${unit} target`), { target: { value: target } });
};

describe('rounds panel', () => {
  it('fights rounds and shows each one, the latest open', () => {
    const store = started();
    expect(screen.getAllByText('No rounds fought yet.')).toHaveLength(1);
    order('1st Minnesota', 'ranged', 'cs_8al');
    order('8th Alabama', 'melee', 'us_1mn');
    order('Battery B', 'ranged', 'cs_11al');
    fireEvent.change(screen.getByLabelText('Battery B if the target breaks'), { target: { value: 'strongest' } });
    order("Ross's Battery", 'ranged', 'us_bat');
    order('11th Alabama', 'ranged', 'us_bat');
    fireEvent.click(screen.getByLabelText(/Record every casualty/));
    fireEvent.input(screen.getByLabelText('Round length'), { target: { value: '120' } });
    fireEvent.click(screen.getByRole('button', { name: 'Fight round 1' }));

    const table = screen.getByRole('table', { name: 'Round 1' });
    expect(within(table).getAllByRole('row')).toHaveLength(1 + 7);
    expect(screen.getByText('Round 1 (0–120 min)')).toBeTruthy();
    expect(within(screen.getByRole('list', { name: 'Round 1 charges' })).getByText(/^8th Alabama -> 1st Minnesota: /))
      .toBeTruthy();
    expect(screen.getByText(/casualties recorded one by one/)).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Fight round 2' })).toBeTruthy();

    fireEvent.click(screen.getByLabelText(/Record every casualty/));
    fireEvent.click(screen.getByRole('button', { name: 'Fight round 2' }));
    const details = document.querySelectorAll('details');
    expect([...details].map((d) => d.open)).toEqual([false, true]);
    expect(store.history.value).toHaveLength(2);
  });

  it('lists target switches', () => {
    const store = started();
    act(() => {
      store.battle.value!.units.get('cs_11al')!.regiment.updateSize(5);
      store.battle.value!.units.get('cs_11al')!.morale.resolve = 0.01;
      store.touch();
    });
    order('Battery B', 'ranged', 'cs_11al');
    fireEvent.change(screen.getByLabelText('Battery B if the target breaks'), { target: { value: 'strongest' } });
    fireEvent.click(screen.getByRole('button', { name: 'Fight round 1' }));
    const switches = screen.getByRole('list', { name: 'Round 1 target switches' });
    expect(switches.textContent).toMatch(/^Battery B switched from 11th Alabama to .+ at \d+ min$/);
  });

  it('shows why a round was not fought', () => {
    started();
    fireEvent.input(screen.getByLabelText('Round length'), { target: { value: '0' } });
    fireEvent.click(screen.getByRole('button', { name: 'Fight round 1' }));
    expect(screen.getByRole('alert').textContent).toBe('The round length must be more than 0 minutes.');
  });
});

describe('strength charts', () => {
  it('show men and morale for each side after a round', () => {
    started();
    fireEvent.click(screen.getByRole('button', { name: 'Fight round 1' }));
    const titles = [...document.querySelectorAll('figcaption')].map((f) => f.textContent);
    expect(titles).toEqual(['Union: Men in the ranks', 'Confederate: Men in the ranks', 'Union: Morale (raw, 10–100)',
      'Confederate: Morale (raw, 10–100)']);
  });

  it('say when a side has more units than the palette', () => {
    const store = createStore(1);
    store.clearUnits();
    for (let i = 0; i < 9; i++) store.addUnit(0);
    store.addUnit(1);
    render(<App store={store} />);
    fireEvent.click(screen.getByRole('button', { name: 'Start battle' }));
    fireEvent.click(screen.getByRole('button', { name: 'Fight round 1' }));
    expect(screen.getAllByText('Showing the first 8 of 9 units; all are in the tables.')).toHaveLength(2);
  });
});

