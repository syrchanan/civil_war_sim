// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/preact';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { App } from './App';
import { createStore } from './store';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const playerView = (side: '0' | '1' = '0') => {
  const store = createStore(1863, 'player');
  render(<App store={store} />);
  fireEvent.click(screen.getByRole('button', { name: 'Start battle' }));
  fireEvent.change(screen.getByLabelText('You command'), { target: { value: side } });
  return store;
};

describe('player view', () => {
  it('splits orders into yours and what you expect of the enemy', () => {
    const store = playerView('0');
    const yours = screen.getByRole('table', { name: 'Your orders' });
    const theirs = screen.getByRole('table', { name: 'What you expect the enemy to do' });
    expect(within(yours).getAllByRole('row')).toHaveLength(1 + 3);
    expect(within(theirs).getAllByRole('row')).toHaveLength(1 + 4);
    fireEvent.change(screen.getByLabelText('1st Minnesota action'), { target: { value: 'ranged' } });
    expect(within(theirs).getByText('8th Alabama').closest('tr')!.textContent).toContain('returns fire');
    fireEvent.change(screen.getByLabelText('10th Alabama action'), { target: { value: 'ranged' } });
    expect(store.isAssumed('cs_10al')).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Reset 10th Alabama to the default' }));
    expect(store.isAssumed('cs_10al')).toBe(false);
  });

  it('switching sides swaps the tables', () => {
    playerView('1');
    expect(within(screen.getByRole('table', { name: 'Your orders' })).getAllByRole('row')).toHaveLength(1 + 4);
  });

  it('has no fight or finish buttons; it estimates instead', () => {
    playerView();
    expect(screen.queryByRole('button', { name: /^Fight round/ })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Finish the battle' })).toBeNull();
    expect(screen.getByText('The admin fights the rounds and finishes the battle.')).toBeTruthy();
    fireEvent.change(screen.getByLabelText('1st Minnesota action'), { target: { value: 'ranged' } });
    fireEvent.click(screen.getByRole('button', { name: 'Estimate the next round' }));
    const table = screen.getByRole('table', { name: 'Estimate' });
    const mn = within(table).getByText('1st Minnesota').closest('tr')!;
    expect(mn.textContent).toMatch(/^1st Minnesota\d+\d+–\d+\d+\d+–\d+\d+%$/);
    expect(screen.getByText(/^From 200 runs of the round/)).toBeTruthy();
    fireEvent.input(screen.getByLabelText('Round length'), { target: { value: '90' } });
    expect(screen.getByText(/out of date/)).toBeTruthy();
  });

  it('shows how often each charge goes each way', () => {
    playerView();
    fireEvent.change(screen.getByLabelText('1st Minnesota action'), { target: { value: 'melee' } });
    fireEvent.click(screen.getByRole('button', { name: 'Estimate the next round' }));
    const charges = screen.getByRole('list', { name: 'Charges in the estimate' });
    expect(charges.textContent).toMatch(/^1st Minnesota -> 8th Alabama: /);
    expect(charges.textContent).toMatch(/went home \d+%/);
  });

  it('downloads my orders', () => {
    playerView();
    URL.createObjectURL = vi.fn(() => 'blob:orders');
    URL.revokeObjectURL = vi.fn();
    const names: string[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      names.push(this.download);
    });
    fireEvent.click(screen.getByRole('button', { name: 'Download my orders' }));
    expect(names).toEqual(['orders-1863-round-1-Union.json']);
  });

  it('can only move its own units once the battle has started', () => {
    playerView('0');
    expect(screen.getByRole('button', { name: /^1st Minnesota,/ }).getAttribute('tabindex')).toBe('0');
    expect(screen.getByRole('button', { name: /^8th Alabama,/ }).getAttribute('tabindex')).toBeNull();
  });

  it('before the battle there are no orders to download and no side to pick yet', () => {
    render(<App store={createStore(1, 'player')} />);
    expect((screen.getByRole('button', { name: 'Download my orders' }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByLabelText('You command')).toBeNull();
  });
});

describe('admin view', () => {
  it('loads players\' orders files', async () => {
    const union = createStore(1863, 'player');
    union.start();
    union.setOrder('us_1mn', { mode: 'ranged', target: 'cs_8al' });
    const admin = createStore(1863);
    render(<App store={admin} />);
    fireEvent.click(screen.getByRole('button', { name: 'Start battle' }));
    const good = new File([union.planDownload().text], 'union.json');
    const bad = new File(['{}'], 'bad.json');
    fireEvent.change(screen.getByLabelText("Load players' orders"), { target: { files: [good, bad] } });
    await waitFor(() => expect(admin.orders.value.us_1mn.mode).toBe('ranged'));
    expect(screen.getByRole('alert').textContent).toBe('bad.json: not an orders file.');
    expect(screen.queryByLabelText('You command')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Download my orders' })).toBeNull();
  });

  it('loading good files clears an earlier problem; picking nothing does nothing', async () => {
    const union = createStore(1863, 'player');
    union.start();
    const admin = createStore(1863);
    render(<App store={admin} />);
    fireEvent.click(screen.getByRole('button', { name: 'Start battle' }));
    const input = screen.getByLabelText("Load players' orders");
    fireEvent.change(input, { target: { files: [new File(['{}'], 'bad.json')] } });
    await waitFor(() => expect(screen.getByRole('alert')).toBeTruthy());
    fireEvent.change(input, { target: { files: [new File([union.planDownload().text], 'u.json')] } });
    await waitFor(() => expect(screen.queryByRole('alert')).toBeNull());
    fireEvent.change(input, { target: { files: [] } });
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('can estimate too, and still fights rounds', () => {
    render(<App store={createStore(1863)} />);
    fireEvent.click(screen.getByRole('button', { name: 'Start battle' }));
    fireEvent.click(screen.getByRole('button', { name: 'Estimate the next round' }));
    expect(screen.getByRole('table', { name: 'Estimate' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Fight round 1' })).toBeTruthy();
  });
});
