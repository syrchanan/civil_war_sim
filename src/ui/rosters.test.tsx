// @vitest-environment jsdom
// The rosters under Armies: each side by corps, division and brigade; the enemy only as far as it is known.
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/preact';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { App } from './App';
import { bigArmies } from './bigBattle';
import { createStore, type Store } from './store';
import { closeRanks } from './testing';

beforeEach(() => localStorage.clear());
afterEach(cleanup);

const roster = (name: string) => within(screen.getByRole('region', { name: `${name} roster` }));

function bigBattle(mode: 'admin' | 'player' = 'admin'): Store {
  const s = createStore(1863, mode);
  const a = bigArmies(7);
  s.units.value = a.units;
  s.setField({ width: 8000, height: 4800 });
  s.start();
  return s;
}

describe('rosters', () => {
  it('the admin sees both sides by corps, division and brigade, with men and how each regiment stands', () => {
    const s = bigBattle();
    render(<App store={s} />);
    const union = roster('Union');
    const corps = union.getAllByRole('group').filter((d) => d.classList.contains('corps'));
    expect(corps.map((d) => d.querySelector('summary')!.textContent)).toEqual([
      'II Corps · 70 regiments · ' + `${[...s.battle.value!.units.values()].filter((u) => u.side === 0)
        .reduce((a, u) => a + u.size, 0).toLocaleString('en-US')} of ${[...s.battle.value!.units.values()]
        .filter((u) => u.side === 0).reduce((a, u) => a + u.initialSize, 0).toLocaleString('en-US')} men`]);
    const brigade = union.getAllByRole('group').find((d) => d.classList.contains('brigade')) as HTMLDetailsElement;
    expect(brigade.open).toBe(false);
    expect(within(brigade).getAllByRole('listitem')[0].textContent).toMatch(/^\d+\w\w \w+.* [\d,]+ men, steady · 100%$/);
    expect(roster('Confederate').getAllByRole('group').length).toBeGreaterThan(10);
  });

  it('a regiment clicked is selected; broken and wiped-out regiments say so', () => {
    const s = createStore(1863);
    closeRanks(s);
    s.start();
    const b = s.battle.value!;
    b.units.get('cs_8al')!.morale.forceBreak();
    render(<App store={s} />);
    expect(roster('Confederate').getByText('8th Alabama').closest('li')!.textContent).toMatch(/, broken$/);
    fireEvent.click(roster('Union').getByRole('button', { name: '1st Minnesota' }));
    expect(s.focusedUnit.value).toBe('us_1mn');
    // regiments with no org stand under 'Unattached'
    expect(roster('Union').getAllByText('Unattached').length).toBeGreaterThan(0);
  });

  it('a wiped-out regiment', () => {
    const s = createStore(1863);
    closeRanks(s);
    s.start();
    act(() => {
      const u = s.battle.value!.units.get('us_bat')!;
      u.regiment.updateSize(0);
      s.touch();
    });
    render(<App store={s} />);
    expect(roster('Union').getByText('Battery B').closest('li')!.textContent).toMatch(/, wiped out$/);
  });

  it('a player sees the enemy only as far as known: roughly, in sight or last seen; none seen yet', () => {
    const admin = bigBattle();
    const player = createStore(1, 'player');
    expect(player.open(admin.playerFileDownload(0).text)).toBeNull();
    render(<App store={player} />);
    expect(screen.getByRole('heading', { name: 'Confederate, as far as you know' })).toBeTruthy();
    const seen = [...admin.battle.value!.units.values()].filter((u) => u.side === 1 && player.battle.value!.units.has(u.uid));
    const items = roster('Confederate').queryAllByRole('listitem');
    expect(items).toHaveLength(seen.length);
    if (items.length) expect(items[0].textContent).toMatch(/ ~[\d,]+ men, (in sight|last seen round \d+|broken)$/);
    cleanup();

    // deploying, nothing of the enemy is known yet
    const deploying = createStore(1863);
    deploying.approve(0);
    deploying.approve(1);
    deploying.openDeployment();
    const p = createStore(1, 'player');
    p.open(deploying.playerFileDownload(0).text);
    render(<App store={p} />);
    expect(roster('Confederate').getByText('None seen yet.')).toBeTruthy();
  });
});
