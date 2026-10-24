// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/preact';
import { afterEach, describe, expect, it } from 'vitest';

import { App } from './App';
import { modifierText } from './format';
import { createStore } from './store';

afterEach(cleanup);

const adminView = () => {
  const store = createStore(1863);
  render(<App store={store} />);
  fireEvent.click(screen.getByRole('button', { name: 'Start battle' }));
  return store;
};

describe('admin: players\' orders received', () => {
  it('shows each side\'s file, where each order came from, and who has no orders', async () => {
    const union = createStore(1863, 'player');
    union.start();
    union.setOrder('us_1mn', { mode: 'ranged', target: 'cs_8al' });
    const store = adminView();
    const received = () => screen.getByRole('list', { name: 'Orders received' });
    expect(received().textContent).toBe('Union: no orders file yetConfederate: no orders file yet');
    fireEvent.change(screen.getByLabelText("Load players' orders"),
      { target: { files: [new File([union.planDownload().text], 'union.json')] } });
    await waitFor(() => expect(received().textContent).toContain('Union: union.json'));
    const row = (name: string) => [...screen.getByRole('table', { name: 'Orders' }).querySelectorAll('tbody tr')]
      .find((tr) => tr.firstElementChild!.textContent === name)!;
    expect(row('1st Minnesota').lastElementChild!.textContent).toBe('union.json');
    expect(row('8th Alabama').lastElementChild!.textContent).toBe('—');
    expect(screen.getByText(/Without orders \(they will hold\)/).textContent)
      .toBe('Without orders (they will hold): 8th Alabama, 10th Alabama, 11th Alabama, Ross\'s Battery');
    fireEvent.change(screen.getByLabelText('1st Minnesota target'), { target: { value: 'cs_10al' } });
    expect(row('1st Minnesota').lastElementChild!.textContent).toBe('admin');
    expect(store.orderSources.value.us_1mn).toBe('admin');
  });

  it('says so when every unit has orders', () => {
    const store = adminView();
    expect(screen.getByText(/Without orders/)).toBeTruthy();
    act(() => {
      for (const u of store.actingUnits.value) store.setOrder(u.uid, { mode: 'idle' });
    });
    expect(screen.queryByText(/Without orders/)).toBeNull();
  });
});

describe('admin: modifiers for this round', () => {
  it('set per unit in percent, with a note; shown in the preview and recorded with the round', () => {
    const store = adminView();
    fireEvent.change(screen.getByLabelText('1st Minnesota action'), { target: { value: 'ranged' } });
    const summary = () => screen.getByText(/^Modifiers for this round/);
    expect(summary().textContent).toBe('Modifiers for this round (none set)');
    fireEvent.input(screen.getByLabelText('1st Minnesota fire %'), { target: { value: '-15' } });
    fireEvent.input(screen.getByLabelText('1st Minnesota note'), { target: { value: 'uphill' } });
    fireEvent.input(screen.getByLabelText('8th Alabama morale %'), { target: { value: '10' } });
    fireEvent.input(screen.getByLabelText('8th Alabama melee %'), { target: { value: '' } });   // empty: 0
    expect(store.modifiers.value).toEqual({
      us_1mn: { fire: -0.15, melee: 0, morale: 0, note: 'uphill' },
      cs_8al: { fire: 0, melee: 0, morale: 0.1, note: '' },
    });
    expect(summary().textContent).toBe('Modifiers for this round (2 set)');
    expect((screen.getByLabelText('1st Minnesota fire %') as HTMLInputElement).value).toBe('-15');
    fireEvent.click(screen.getByRole('button', { name: 'Fight round 1' }));
    expect(store.modifiers.value).toEqual({});
    const list = screen.getByRole('list', { name: 'Round 1 modifiers' });
    expect(list.textContent).toBe('1st Minnesota: fire -15% (uphill)8th Alabama: morale +10%');
  });

  it('a modifier out of range is shown as a problem and stops the round', () => {
    adminView();
    fireEvent.input(screen.getByLabelText('1st Minnesota fire %'), { target: { value: '150' } });
    expect(screen.getAllByRole('alert').some((a) => /between -1 and 1/.test(a.textContent!))).toBe(true);
    expect((screen.getByRole('button', { name: 'Fight round 1' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('players see no modifiers', () => {
    const store = createStore(1863, 'player');
    render(<App store={store} />);
    fireEvent.click(screen.getByRole('button', { name: 'Start battle' }));
    expect(screen.queryByText(/^Modifiers for this round/)).toBeNull();
    expect(screen.queryByRole('list', { name: 'Orders received' })).toBeNull();
  });
});

describe('modifier wording', () => {
  it('only what is set, signed, with the note', () => {
    expect(modifierText({ fire: 0.2, melee: -0.05, morale: 0, note: '' })).toBe('fire +20%, melee -5%');
    expect(modifierText({ fire: 0, melee: 0, morale: 0, note: 'rain' })).toBe('(rain)');
  });
});

describe('orders table: only what a unit can do', () => {
  it('a melee-only unit is offered hold and charge; an order it already has stays listed', () => {
    const store = createStore(1863);
    store.updateUnit('cs_11al', { stats: '3/4/0/1' });
    render(<App store={store} />);
    fireEvent.click(screen.getByRole('button', { name: 'Start battle' }));
    const options = () => [...(screen.getByLabelText('11th Alabama action') as HTMLSelectElement).options].map((o) => o.value);
    expect(options()).toEqual(['melee', 'idle']);
    expect([...(screen.getByLabelText('1st Minnesota action') as HTMLSelectElement).options].map((o) => o.value))
      .toEqual(['ranged', 'melee', 'idle']);
    act(() => store.setOrder('cs_11al', { mode: 'ranged', target: 'us_1mn' }));  // e.g. from an orders file
    expect(options()).toEqual(['ranged', 'melee', 'idle']);
  });
});
