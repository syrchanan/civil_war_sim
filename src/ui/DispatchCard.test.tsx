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

const docked = () => within(document.getElementById('panel-dispatches')!);
const card = () => docked().getByRole('article', { name: 'Dispatch, round 1' });
const tab = (name: string) => screen.getByRole('tab', { name });
const openTab = () => screen.getAllByRole('tab').find((t) => t.getAttribute('aria-selected') === 'true')!.textContent;

describe('the dispatch just fought', () => {
  it('opens the Dispatches tab, both sides for the admin, and closes on to the next orders', () => {
    const s = fought();
    render(<App store={s} />);
    const c = within(card());
    expect(c.getByText('Dispatch · Round 1 · 1:00 pm to 2:00 pm')).toBeTruthy();
    expect(c.getByRole('heading', { level: 3 }).textContent).not.toBe('');
    expect(c.getByRole('table', { name: 'Round 1: Union' })).toBeTruthy();
    expect(c.getByRole('table', { name: 'Round 1: Confederate' })).toBeTruthy();
    expect(c.getByText(/^8th Alabama on 1st Minnesota: .+ at \d+:\d\d pm$/)).toBeTruthy();
    expect(document.querySelectorAll('#panel-dispatches .dispatch td:last-child')[0].textContent)
      .toMatch(/^(Steady|Shaken|Wavering) · \d+%$|^Broken$/);
    expect(openTab()).toBe('Dispatches');

    fireEvent.click(c.getByRole('button', { name: 'Replay on the map' }));
    expect(s.mapRound.value).toBe(1);
    fireEvent.click(c.getByRole('button', { name: 'On to round 2 orders' }));
    expect([s.dispatchRound.value, s.mapRound.value]).toEqual([null, null]);
    expect(openTab()).toBe('Unit');
    // closed, it stays in the list without the way on
    expect(within(card()).queryByRole('button', { name: 'On to round 2 orders' })).toBeNull();
  });

  it('stays open in its tab when a regiment is selected; without a clock, minutes', () => {
    const s = fought(null);
    render(<App store={s} />);
    act(() => s.selectUnit('us_1mn'));
    expect(openTab()).toBe('Unit');
    expect(within(document.getElementById('panel-unit')!).getByRole('region', { name: /^Orders for / })).toBeTruthy();
    expect(within(card()).getByText('Dispatch · Round 1 · 0 min to 60 min')).toBeTruthy();
    expect(within(card()).getByRole('button', { name: 'On to round 2 orders' })).toBeTruthy();
  });

  it('the round strip opens a past round\'s dispatch, and the round being ordered closes it', () => {
    const s = fought();
    act(() => {
      s.resolve();
    });
    render(<App store={s} />);
    expect(docked().getByRole('article', { name: 'Dispatch, round 2' })).toBeTruthy();
    const strip = within(screen.getByRole('navigation', { name: 'The day' }));
    fireEvent.click(tab('Orders'));
    fireEvent.click(strip.getByRole('button', { name: /^Round 1/ }));
    expect([s.dispatchRound.value, s.mapRound.value, openTab()]).toEqual([1, 1, 'Dispatches']);
    // the picked round comes first
    expect(document.querySelector('#panel-dispatches .dispatch')!.getAttribute('aria-label')).toBe('Dispatch, round 1');
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

describe('the unit card while replaying', () => {
  it('gives morale as the round began, not as it is now', () => {
    const s = fought();
    s.setOrder('cs_8al', { mode: 'melee', target: 'us_1mn' });
    s.resolve();
    const b = s.battle.value!;
    const al = b.units.get('cs_8al')!;
    render(<App store={s} />);
    const status = () => [...document.querySelectorAll('#panel-unit .unit-info dd')].map((d) => d.textContent)
      .find((t) => /morale left|^Broken|^Wiped/.test(t!));
    act(() => s.selectUnit('cs_8al'));
    act(() => {
      s.mapRound.value = 1;
    });
    expect(status()).toBe('Steady, 100% morale left');
    act(() => {
      s.mapRound.value = 2;
    });
    const began = b.history[0].units.cs_8al;
    expect(status()).toBe(began.broken ? 'Broken'
      : `Steady, ${Math.round((began.morale / al.morale.initialMorale) * 100)}% morale left`);
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
  it('a card per round: the one just fought first with the way on, the others only to replay', () => {
    const s = fought();
    act(() => {
      s.resolve();
    });
    render(<App store={s} />);
    const panel = within(document.getElementById('panel-dispatches')!);
    const cards = panel.getAllByRole('article').map((a) => a.getAttribute('aria-label'));
    expect(cards).toEqual(['Dispatch, round 2', 'Dispatch, round 1']);
    const first = within(panel.getByRole('article', { name: 'Dispatch, round 1' }));
    expect(first.getByRole('button', { name: 'Replay on the map' })).toBeTruthy();
    expect(first.queryByRole('button', { name: 'Close' })).toBeNull();
    expect(within(panel.getByRole('article', { name: 'Dispatch, round 2' }))
      .getByRole('button', { name: 'On to round 3 orders' })).toBeTruthy();
  });
});
