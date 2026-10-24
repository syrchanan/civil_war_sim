// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/preact';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { App } from './App';
import { createStore } from './store';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

/** The admin's battle a round in; the player's view of one side, opened from the admin's player file. */
const setup = (side: 0 | 1 = 0) => {
  const admin = createStore(1863);
  admin.start();
  admin.setOrder('us_1mn', { mode: 'ranged', target: 'cs_8al' });
  admin.setOrder('cs_8al', { mode: 'ranged', target: 'us_1mn' });
  admin.resolve();
  const player = createStore(1, 'player');
  player.open(admin.playerFileDownload(side).text);
  render(<App store={player} />);
  return { admin, player };
};

describe('admin: downloading player files', () => {
  it('one button per side, while the battle is being fought', () => {
    const saved: string[] = [];
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:x');
    vi.spyOn(URL, 'revokeObjectURL').mockReturnValue(undefined);
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      saved.push(this.download);
    });
    const store = createStore(1863);
    render(<App store={store} />);
    const button = (side: string) => screen.getByRole('button', { name: `Player file: ${side}` }) as HTMLButtonElement;
    expect(button('Union').disabled).toBe(true);                       // no battle yet
    fireEvent.click(screen.getByRole('button', { name: 'Start battle' }));
    fireEvent.click(button('Union'));
    fireEvent.click(button('Confederate'));
    expect(saved).toEqual(['player-1863-round-1-Union.json', 'player-1863-round-1-Confederate.json']);
    fireEvent.click(screen.getByRole('button', { name: 'Finish the battle' }));
    expect(button('Union').disabled).toBe(true);
  });
});

describe('player: planning from their file', () => {
  it('commands their side only: no side to pick, no battle download, no player-file buttons, no army changes', () => {
    setup(1);
    expect(screen.queryByRole('button', { name: /^Change the armies/ })).toBeNull();
    expect(screen.queryByLabelText('You command')).toBeNull();
    expect(screen.getByText('You command: Confederate')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Download battle' })).toBeNull();
    expect(screen.queryByRole('button', { name: /^Player file/ })).toBeNull();
  });

  it('enemy units on the map: men roughly', () => {
    const { admin } = setup(0);
    const real = admin.battle.value!.units.get('cs_8al')!.size;
    const block = screen.getByRole('button', { name: /^8th Alabama,/ });
    expect(block.getAttribute('aria-label')).toMatch(/^8th Alabama, about \d[\d,]* men/);
    expect(block.querySelector('.unit-men')!.textContent).toMatch(/^about /);
    expect(real % 50).not.toBe(0);                                     // so the rough number differs
  });

  it('the order of battle hides the enemy\'s exact men and averages', () => {
    setup(0);
    const rows = within(screen.getByRole('table', { name: 'Order of battle' })).getAllByRole('row');
    const enemy = rows[2].textContent!;
    expect(enemy).toContain('about');
    expect(rows[2].querySelectorAll('td')[6].textContent).toBe('—');
    expect(rows[1].querySelectorAll('td')[6].textContent).not.toBe('—');
  });

  it('the rounds show only their own units, and charts only their side', () => {
    setup(0);
    const round = within(screen.getByRole('table', { name: 'Round 1' }));
    expect(round.getByText('1st Minnesota')).toBeTruthy();
    expect(round.queryByText('8th Alabama')).toBeNull();
    expect(screen.queryByRole('img', { name: /^Confederate:/ })).toBeNull();
    expect(screen.getAllByRole('img', { name: /^Union:/ }).length).toBeGreaterThan(0);
  });

  it('guesses about the enemy: men and stats, used by the preview and the estimate', () => {
    const { player } = setup(0);
    const table = screen.getByRole('table', { name: 'Your guesses about the enemy' });
    const men = within(table).getByLabelText('8th Alabama men (guess)') as HTMLInputElement;
    expect(Number(men.value)).toBe(player.battle.value!.units.get('cs_8al')!.size);
    fireEvent.change(men, { target: { value: '1100' } });
    expect(player.battle.value!.units.get('cs_8al')!.size).toBe(1100);
    fireEvent.change(within(table).getByLabelText('8th Alabama stats (guess)'), { target: { value: 'x' } });
    expect(within(table).getByRole('alert').textContent).toMatch(/^8th Alabama: Stats must be/);
    fireEvent.change(within(table).getByLabelText('8th Alabama stats (guess)'), { target: { value: '7/7/1/0' } });
    expect(within(table).queryByRole('alert')).toBeNull();
    expect(player.guesses.value.cs_8al).toEqual({ size: 1100, stats: '7/7/1/0' });
  });

  it('the estimate marks enemy figures as guesses', async () => {
    setup(0);
    fireEvent.click(screen.getByRole('button', { name: 'Estimate the next round' }));
    const estimate = await waitFor(() => screen.getByRole('table', { name: 'Estimate' }));
    expect(within(estimate).getByText('8th Alabama (guess)')).toBeTruthy();
    expect(within(estimate).getByText('1st Minnesota')).toBeTruthy();
    expect(screen.getByText(/Enemy figures come from your guesses/)).toBeTruthy();
  });
});
