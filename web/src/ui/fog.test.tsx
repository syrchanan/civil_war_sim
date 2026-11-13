// @vitest-environment jsdom
// Fog of war: a player in battle sees the enemy only from across the field, everywhere on the page.
import { act, cleanup, render, screen, within } from '@testing-library/preact';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { App } from './App';
import { createStore, type Store } from './store';
import { closeRanks } from './testing';

beforeEach(() => localStorage.clear());
afterEach(cleanup);

function practising(side: 0 | 1 = 0): Store {
  const s = createStore(1863, 'player');
  closeRanks(s);
  s.playerSide.value = side;
  s.start();
  return s;
}

describe('the fog side', () => {
  it('the enemy, for a player once the battle has begun; lifted when it is over', () => {
    const s = createStore(1863, 'player');
    expect(s.fogSide.value).toBeNull(); // drafting both armies
    s.start();
    expect(s.fogSide.value).toBe(1);
    s.playerSide.value = 1;
    expect(s.fogSide.value).toBe(0);
    s.finish(null);
    expect(s.fogSide.value).toBeNull();
  });

  it('none for the admin', () => {
    const s = createStore(1863);
    s.start();
    expect(s.fogSide.value).toBeNull();
  });

  it('from a player file, the side it hides', () => {
    const admin = createStore(1863);
    admin.start();
    const player = createStore(1, 'player');
    player.open(admin.playerFileDownload(1).text);
    expect(player.fogSide.value).toBe(0);
  });
});

describe('on the page', () => {
  it('the map shows enemy men roughly, your own exactly', () => {
    const s = practising();
    const by = Object.fromEntries(s.mapUnits.value.map((u) => [u.uid, u]));
    expect(by.cs_bat).toMatchObject({ men: 70, rough: true });
    expect(by.us_bat).toMatchObject({ men: 72, rough: false });
    render(<App store={s} />);
    expect(screen.getByRole('button', { name: /^Ross's Battery, about 70 men,/ })).toBeTruthy();
  });

  it('the order of battle: the enemy\'s men roughly, no averages or guns', () => {
    const s = practising();
    render(<App store={s} />);
    const rows = within(screen.getByRole('table', { name: 'Order of battle' })).getAllByRole('row');
    const enemy = rows.find((r) => r.textContent!.startsWith('Confederate'))!;
    expect(enemy.textContent).toContain('~2,450');
    expect(enemy.textContent).not.toMatch(/guns/);
    expect(enemy.textContent).toContain('—');
    const own = rows.find((r) => r.textContent!.startsWith('Union'))!;
    expect(own.textContent).toContain('8 guns');
  });

  it('the rounds and charts: only your own units\' figures, until the battle is over', () => {
    // rounds are fought by the admin; the same battle then seen in player mode
    const s = createStore(1863);
    closeRanks(s);
    s.start();
    s.setOrder('us_1mn', { mode: 'ranged', target: 'cs_8al' });
    s.resolve();
    s.mode.value = 'player';
    render(<App store={s} />);
    const round = screen.getByRole('table', { name: 'Round 1' });
    expect(within(round).queryByText('8th Alabama')).toBeNull();
    expect(within(round).getByText('1st Minnesota')).toBeTruthy();
    expect(screen.queryByText(/^Confederate: Men in the ranks/)).toBeNull();
    expect(screen.getByText(/^Union: Men in the ranks/)).toBeTruthy();
    act(() => s.finish(null));
    expect(within(screen.getByRole('table', { name: 'Round 1' })).getByText('8th Alabama')).toBeTruthy();
  });

  it('the estimate leaves the enemy out, and says so', () => {
    const s = practising();
    s.setOrder('us_1mn', { mode: 'ranged', target: 'cs_8al' });
    render(<App store={s} />);
    act(() => s.runEstimate(5));
    const table = screen.getByRole('table', { name: 'Estimate' });
    expect(within(table).queryByText('8th Alabama')).toBeNull();
    expect(within(table).getByText('1st Minnesota')).toBeTruthy();
    expect(screen.getByText(/Enemy units are left out/)).toBeTruthy();
  });

  it('the admin sees everything', () => {
    const s = createStore(1863);
    closeRanks(s);
    s.start();
    s.setOrder('us_1mn', { mode: 'ranged', target: 'cs_8al' });
    render(<App store={s} />);
    act(() => s.runEstimate(5));
    expect(within(screen.getByRole('table', { name: 'Estimate' })).getByText('8th Alabama')).toBeTruthy();
    expect(screen.queryByText(/Enemy units are left out/)).toBeNull();
  });
});
