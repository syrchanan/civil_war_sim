// @vitest-environment jsdom
// The battle's end in the Result tab: the verdict, the butcher's bill, the generals, the regiments ranked.
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/preact';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { ratings } from '../engine';
import { App } from './App';
import { bigArmies } from './bigBattle';
import { createStore, type Store } from './store';
import { closeRanks } from './testing';

beforeEach(() => localStorage.clear());
afterEach(cleanup);

/** The example battle, a round of fire fought, then finished as the admin names it. */
function finished(holder: 0 | 1 | null | 'auto' = 'auto'): Store {
  const s = createStore(1863);
  closeRanks(s);
  s.start();
  s.setOrder('us_1mn', { mode: 'ranged', target: 'cs_8al' });
  s.setOrder('cs_8al', { mode: 'ranged', target: 'us_1mn' });
  expect(s.resolve()).toBeNull();
  s.finish(holder);
  return s;
}

const section = (name: string) => within(screen.getByRole('region', { name }));

describe('the battle\'s end', () => {
  it('at nightfall the Result tab opens, widened for this page only', () => {
    const s = createStore(1863);
    s.start();
    render(<App store={s} />);
    act(() => s.finish('auto'));
    expect(screen.getByRole('tab', { name: 'Result' }).getAttribute('aria-selected')).toBe('true');
    expect(s.sidebarWide.value).toBe(true);
    expect(localStorage.getItem('imperial-generals:sidebar-wide')).toBeNull();
  });

  it('a finished battle opened from its file opens on its result too', () => {
    const s = finished();
    const t = createStore(2);
    expect(t.open(s.download().text)).toBeNull();
    render(<App store={t} />);
    expect(screen.getByRole('tab', { name: 'Result' }).getAttribute('aria-selected')).toBe('true');
    expect(screen.getByRole('region', { name: 'Verdict' })).toBeTruthy();
  });

  it('the verdict, the butcher\'s bill and the men still in the ranks', () => {
    const s = finished(0);
    render(<App store={s} />);
    const verdict = section('Verdict');
    expect(verdict.getByText('Union holds the field')).toBeTruthy();
    expect(verdict.getByRole('heading').textContent).toMatch(/^A (Decisive |Pyrrhic )?Union Victory$/);
    expect(verdict.getByText('The field was named by the admin.')).toBeTruthy();
    const bill = within(screen.getByRole('table', { name: 'Butcher\'s bill' }));
    expect(bill.getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['', 'Union', 'Confederate']);
    expect(bill.getAllByRole('row')).toHaveLength(1 + 8);
    const summary = s.summary.value!;
    expect(section('The butcher\'s bill').getByRole('img', { name: `Union: ${Math.round((summary[0].final
      / summary[0].started) * 100)}%` })).toBeTruthy();
  });

  it('the generals: each side\'s, with the odds and the parts of its result, marked on the ladder', () => {
    const s = finished(0);
    render(<App store={s} />);
    const rated = ratings(s.battle.value!.toDict());
    const generals = section('The generals');
    expect(generals.getByText('The Union commander fought like')).toBeTruthy();
    expect(generals.getAllByText(rated[0].general.name).length).toBeGreaterThan(0);
    expect(generals.getByText('Held the field (counts 30%)')).toBeTruthy();
    expect(generals.getByText('Lost the field (counts 30%)')).toBeTruthy();
    const ladder = within(generals.getByRole('list', { name: 'The ladder of generals' }));
    expect(ladder.getAllByRole('listitem')).toHaveLength(15);
    const marked = document.querySelectorAll('.ladder li.at');
    expect(marked.length).toBeGreaterThanOrEqual(1);
    expect([...marked].map((li) => li.querySelector('.ladder-name')!.textContent))
      .toEqual(expect.arrayContaining([rated[0].general.name, rated[1].general.name]));
  });

  it('a draw: nobody held the field', () => {
    render(<App store={finished(null)} />);
    expect(section('Verdict').getByRole('heading').textContent).toBe('A Drawn Battle');
    expect(section('The generals').getAllByText('Nobody held the field (counts 30%)')).toHaveLength(2);
  });

  it('the regiments ranked, by any of four measures; a name finds the regiment on the map', () => {
    const s = finished(0);
    render(<App store={s} />);
    const ranks = section('Regiments ranked');
    expect(ranks.getAllByRole('listitem')).toHaveLength(7);
    expect(ranks.queryByText('Fared worst')).toBeNull();
    const first = () => ranks.getAllByRole('listitem')[0].querySelector('.ranked-figure')!.textContent;
    fireEvent.change(ranks.getByLabelText('Rank by'), { target: { value: 'time' } });
    expect(first()).toBe('unbroken');
    fireEvent.change(ranks.getByLabelText('Rank by'), { target: { value: 'kept' } });
    expect(first()).toMatch(/%$/);
    const name = ranks.getAllByRole('listitem')[0].querySelector('button')!;
    const uid = [...s.battle.value!.units.values()].find((u) => u.name === name.textContent)!.uid;
    fireEvent.click(name);
    expect(s.focusedUnit.value).toBe(uid);
  });

  it('seventy a side: the best five, the worst five, and all of them folded', () => {
    const s = createStore(1863);
    s.units.value = bigArmies(7).units;
    s.setField({ width: 8000, height: 4800 });
    s.start();
    s.finish('auto');
    render(<App store={s} />);
    const ranks = section('Regiments ranked');
    expect(ranks.getByText('Gave the best account of themselves')).toBeTruthy();
    expect(ranks.getByText('Fared worst')).toBeTruthy();
    expect(ranks.getByText('All 140 regiments')).toBeTruthy();
    expect(ranks.getAllByRole('listitem')).toHaveLength(5 + 5 + 140);
  });

  it('the full ledger keeps the old tables, folded', () => {
    render(<App store={finished()} />);
    const ledger = screen.getByText('The full ledger').closest('details')!;
    expect(ledger.open).toBe(false);
    expect(within(ledger).getByRole('table', { name: 'Side summary' })).toBeTruthy();
    expect(within(ledger).getByRole('table', { name: 'Casualties by unit' })).toBeTruthy();
  });
});
