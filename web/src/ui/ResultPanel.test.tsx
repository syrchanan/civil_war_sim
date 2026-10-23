// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from '@testing-library/preact';
import { afterEach, describe, expect, it } from 'vitest';

import { App } from './App';
import { createStore } from './store';

afterEach(cleanup);

const fought = () => {
  const store = createStore(1863);
  render(<App store={store} />);
  expect(screen.getByText('Start the battle, fight its rounds, then finish it here.')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Start battle' }));
  fireEvent.change(screen.getByLabelText('1st Minnesota action'), { target: { value: 'ranged' } });
  fireEvent.change(screen.getByLabelText('8th Alabama action'), { target: { value: 'ranged' } });
  fireEvent.click(screen.getByRole('button', { name: 'Fight round 1' }));
  return store;
};

describe('result panel', () => {
  it('finishes the battle with the field decided by the engine', () => {
    const store = fought();
    fireEvent.click(screen.getByRole('button', { name: 'Finish the battle' }));
    expect(store.battle.value!.finished).toBe(true);
    expect(screen.getByText(/^Field held by: /)).toBeTruthy();
    const summary = screen.getByRole('table', { name: 'Side summary' });
    expect(within(summary).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['', 'Union', 'Confederate']);
    expect(within(summary).getByText('Exchange ratio (inflicted / taken)')).toBeTruthy();
    const units = screen.getByRole('table', { name: 'Casualties by unit' });
    expect(within(units).getAllByRole('row')).toHaveLength(1 + 7);
    expect(screen.getByText('The battle is over.')).toBeTruthy();
    expect(screen.queryByRole('table', { name: 'Orders' })).toBeNull();
  });

  it('or as the admin names it', () => {
    const store = fought();
    fireEvent.change(screen.getByLabelText('Who holds the field'), { target: { value: '1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Finish the battle' }));
    expect(store.battle.value!.result!.field_held_by).toBe(1);
    expect(screen.getByText('Field held by: Confederate (named by the admin)')).toBeTruthy();
    const won = within(screen.getByRole('table', { name: 'Side summary' })).getByText('Result').closest('tr')!;
    expect(won.textContent).toBe('Resultlostwon');
  });

  it('a draw', () => {
    fought();
    fireEvent.change(screen.getByLabelText('Who holds the field'), { target: { value: 'none' } });
    fireEvent.click(screen.getByRole('button', { name: 'Finish the battle' }));
    expect(screen.getByText('Field held by: nobody, a draw (named by the admin)')).toBeTruthy();
  });

  it('shows no exchange ratio for a side never hit', () => {
    const store = createStore(1863);
    render(<App store={store} />);
    fireEvent.click(screen.getByRole('button', { name: 'Start battle' }));
    fireEvent.change(screen.getByLabelText('1st Minnesota action'), { target: { value: 'ranged' } });
    fireEvent.click(screen.getByRole('button', { name: 'Fight round 1' }));
    fireEvent.click(screen.getByRole('button', { name: 'Finish the battle' }));
    const row = within(screen.getByRole('table', { name: 'Side summary' })).getByText(/^Exchange ratio/).closest('tr')!;
    expect(row.textContent).toMatch(/^Exchange ratio \(inflicted \/ taken\)—/);
  });
});
