// @vitest-environment jsdom
// Flight in the client: each round lists the units that fled, how far, and whom they got away from.
import { cleanup, fireEvent, render, screen } from '@testing-library/preact';
import { afterEach, describe, expect, it } from 'vitest';

import { App } from './App';
import { flightText } from './format';
import { createStore } from './store';

afterEach(cleanup);

describe('format', () => {
  it('flight in words', () => {
    const name = (uid: string) => ({ a: '8th Alabama', x: '1st Minnesota', y: 'Battery B' }[uid]!);
    expect(flightText({ unit: 'a', distance: 641.7, escaped_from: [] }, name)).toBe('8th Alabama fled 642 yd');
    expect(flightText({ unit: 'a', distance: 50, escaped_from: ['x', 'y'] }, name))
      .toBe('8th Alabama fled 50 yd, getting away from 1st Minnesota and Battery B');
    expect(flightText({ unit: 'a', distance: 50, escaped_from: ['x'] }, name)).toBe('8th Alabama fled 50 yd, getting away from 1st Minnesota');
  });
});

describe('the rounds panel', () => {
  it('lists the round\'s flights', () => {
    const store = createStore(1863);
    render(<App store={store} />);
    fireEvent.click(screen.getByRole('button', { name: 'Start battle' }));
    const b = store.battle.value!;
    const u = b.units.get('cs_8al')!;
    u.morale.forceBreak();
    u.brokeTime = 0;
    store.touch();
    fireEvent.click(screen.getByRole('button', { name: 'Fight round 1' }));
    expect(screen.getByRole('list', { name: 'Round 1 flights' }).textContent).toMatch(/^8th Alabama fled \d+ yd$/);
  });
});
