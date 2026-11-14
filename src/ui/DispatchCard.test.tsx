// @vitest-environment jsdom
// The dispatch in the dock after a round, from the round strip, and for a player opening their new file.
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/preact';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { App } from './App';
import { createStore, type Store } from './store';
import { closeRanks } from './testing';

beforeEach(() => localStorage.clear());
afterEach(cleanup);

/** The admin's battle with one round fought: the 8th Alabama charges the 1st Minnesota. */
function fought(clock: string | null = '13:00'): Store {
  const s = createStore(1863);
  s.startClock.value = clock;
  closeRanks(s);
  s.start();
  s.setOrder('cs_8al', { mode: 'melee', target: 'us_1mn' });
  s.setOrder('us_1mn', { mode: 'ranged', target: 'cs_8al' });
  expect(s.resolve()).toBeNull();
  return s;
}

const docked = () => within(screen.getByRole('complementary', { name: 'Selected unit' }));
const card = () => docked().getByRole('article', { name: 'Dispatch, round 1' });

describe('the dispatch in the dock', () => {
  it('opens after a round is fought, with both sides for the admin, and closes on to the next orders', () => {
    const s = fought();
    render(<App store={s} />);
    const c = within(card());
    expect(c.getByText('Dispatch · Round 1 · 1:00 pm to 2:00 pm')).toBeTruthy();
    expect(c.getByRole('heading', { level: 3 }).textContent).not.toBe('');
    expect(c.getByRole('table', { name: 'Round 1: Union' })).toBeTruthy();
    expect(c.getByRole('table', { name: 'Round 1: Confederate' })).toBeTruthy();
    expect(c.getByText(/^8th Alabama on 1st Minnesota: .+ at \d+:\d\d pm$/)).toBeTruthy();
    expect(document.querySelectorAll('.dock .dispatch td:last-child')[0].textContent).toMatch(/^(Steady|Shaken|Wavering) · \d+%$|^Broken$/);
    expect(screen.queryByText('Select a regiment on the map to see it here.')).toBeNull();

    fireEvent.click(c.getByRole('button', { name: 'Replay on the map' }));
    expect(s.mapRound.value).toBe(1);
    fireEvent.click(c.getByRole('button', { name: 'On to round 2 orders' }));
    expect([s.dispatchRound.value, s.mapRound.value]).toEqual([null, null]);
    expect(screen.getByText('Select a regiment on the map to see it here.')).toBeTruthy();
  });

  it('stays above the unit card when a regiment is selected; without a clock, minutes', () => {
    const s = fought(null);
    render(<App store={s} />);
    act(() => s.selectUnit('us_1mn'));
    expect(within(card()).getByText('Dispatch · Round 1 · 0 min to 60 min')).toBeTruthy();
    expect(docked().getByRole('region', { name: /^Orders for / })).toBeTruthy();
  });

  it('the round strip opens a past round\'s dispatch, and the round being ordered closes it', () => {
    const s = fought();
    act(() => {
      s.resolve();
    });
    render(<App store={s} />);
    expect(docked().getByRole('article', { name: 'Dispatch, round 2' })).toBeTruthy();
    const strip = within(screen.getByRole('navigation', { name: 'The day' }));
    fireEvent.click(strip.getByRole('button', { name: /^Round 1/ }));
    expect([s.dispatchRound.value, s.mapRound.value]).toEqual([1, 1]);
    fireEvent.click(within(card()).getByRole('button', { name: 'Close' })); // not the latest round
    expect(s.dispatchRound.value).toBeNull();
    fireEvent.click(strip.getByRole('button', { name: /^Round 1/ }));
    fireEvent.click(strip.getByRole('button', { name: /^Round 3/ }));
    expect([s.dispatchRound.value, s.mapRound.value]).toEqual([null, null]);
  });

  it('at nightfall it closes; starting over drops it', () => {
    const s = fought();
    act(() => s.finish(null));
    render(<App store={s} />);
    expect(within(card()).getByRole('button', { name: 'Close' })).toBeTruthy();
    act(() => s.reset());
    expect(s.dispatchRound.value).toBeNull();
  });
});

describe('a player\'s dispatch', () => {
  it('opening the new player file shows what happened: their own regiments and what was seen of the enemy', () => {
    const admin = fought();
    const player = createStore(1, 'player');
    expect(player.open(admin.playerFileDownload(0).text)).toBeNull();
    expect(player.dispatchRound.value).toBe(1);
    render(<App store={player} />);
    const c = within(card());
    expect(c.getByRole('table', { name: 'Round 1: your regiments' })).toBeTruthy();
    expect(c.queryByRole('table', { name: 'Round 1: Confederate' })).toBeNull();
    const own = c.getAllByRole('row').slice(1).map((r) => r.firstElementChild!.textContent);
    expect(own).toEqual(['1st Minnesota', '15th Massachusetts', 'Battery B']);
  });

  it('an earlier round, read after a later one, sees the enemy as the next round began', () => {
    const admin = fought();
    admin.resolve();
    const player = createStore(1, 'player');
    player.open(admin.playerFileDownload(0).text);
    expect(player.dispatchRound.value).toBe(2);
    expect(player.dispatchOf(1).round).toBe(1);
  });

  it('a file with no rounds fought opens on the orders', () => {
    const admin = createStore(1863);
    closeRanks(admin);
    admin.start();
    const player = createStore(1, 'player');
    player.open(admin.playerFileDownload(1).text);
    expect(player.dispatchRound.value).toBeNull();
  });
});

describe('the Dispatches tab', () => {
  it('a card per round, with the way to replay it but not to close it', () => {
    const s = fought();
    render(<App store={s} />);
    const tab = within(document.getElementById('panel-dispatches')!);
    const c = within(tab.getByRole('article', { name: 'Dispatch, round 1' }));
    expect(c.getByRole('button', { name: 'Replay on the map' })).toBeTruthy();
    expect(c.queryByRole('button', { name: 'On to round 2 orders' })).toBeNull();
  });
});
