// @vitest-environment jsdom
// Reconnaissance: what is known of both armies, by filter and search, grouped by org; a row finds its regiment.
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/preact';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { Terrain } from '../engine';
import { App } from './App';
import { createStore, type Store } from './store';
import { closeRanks } from './testing';

beforeEach(() => localStorage.clear());
afterEach(cleanup);

// a ridge across the field, as in the fog-of-war tests: the 10th Alabama fires over it, then pulls back behind it
const RIDGE = (() => {
  const heights: number[] = [];
  for (let r = 0; r < 60; r++) for (let c = 0; c < 100; c++) heights.push(r === 30 ? 40 : 0);
  return { cell: 20, columns: 100, rows: 60, heights, ground: 'o'.repeat(6000), meta: {} };
})();
const ALONG: Record<string, number> = {
  us_1mn: 800, us_15ma: 1000, us_bat: 1200, cs_8al: 800, cs_10al: 1000, cs_11al: 1200, cs_bat: 1400,
};
function overTheRidge(): Store {
  const s = createStore(1863);
  for (const [uid, x] of Object.entries(ALONG)) {
    s.moveUnit(uid, { x, y: uid.startsWith('us') ? 900 : uid === 'cs_10al' || uid === 'cs_bat' ? 700 : 300 });
  }
  s.start();
  (s.battle.value! as { terrain: Terrain | null }).terrain = new Terrain(RIDGE);
  s.touch();
  s.setOrder('cs_10al', { mode: 'ranged', target: 'us_15ma' });
  s.resolve();
  s.moveUnit('cs_10al', { x: 1000, y: 300 });
  return s;
}

const recon = () => within(document.getElementById('panel-recon')!);
const chip = (name: RegExp) => recon().getByRole('button', { name });
const rows = () => recon().queryAllByRole('row').slice(1).map((r) => r.textContent);

describe('reconnaissance', () => {
  it('the admin sees each side whole, by brigade, and finds a regiment on the map', () => {
    const s = createStore(1863);
    closeRanks(s);
    s.start();
    s.battle.value!.units.get('us_1mn')!.org = { division: 'Gibbon', brigade: 'Harrow' };
    s.touch();
    render(<App store={s} />);
    fireEvent.click(screen.getByRole('tab', { name: 'Recon' }));
    expect(recon().getByText('All you know of both armies, as of 1:00 pm.')).toBeTruthy();
    expect(recon().getAllByRole('button').filter((b) => b.closest('.chips')).map((b) => b.textContent))
      .toEqual(['Union · 3', 'Confederate · 4']);
    expect(rows()).toEqual(['Gibbon · Harrow', '1st Minnesota900steady · 100%', 'Unattached · Unattached',
      '15th Massachusetts700steady · 100%', 'Battery B72steady · 100%']);
    fireEvent.click(chip(/^Confederate/));
    expect(rows()).toHaveLength(5);
    act(() => {
      s.battle.value!.units.get('cs_8al')!.morale.forceBreak();
      s.battle.value!.units.get('cs_10al')!.regiment.updateSize(0);
      s.touch();
    });
    expect(rows()).toContain('8th Alabama1,000broken');
    expect(rows()).toContain('10th Alabama0wiped out');

    fireEvent.click(recon().getByRole('button', { name: "Ross's Battery" }));
    expect(s.focusedUnit.value).toBe('cs_bat');
    expect(screen.getByRole('tab', { name: 'Unit' }).getAttribute('aria-selected')).toBe('true');
    expect(s.view.value.w).toBeLessThan(2000); // brought to the middle, closer in
  });

  it('search finds by regiment, brigade or division; nothing found says so', () => {
    const s = createStore(1863);
    closeRanks(s);
    s.startClock.value = null;
    s.start();
    s.battle.value!.units.get('us_15ma')!.org = { division: 'Gibbon', brigade: 'Harrow' };
    s.touch();
    render(<App store={s} />);
    expect(recon().getByText('All you know of both armies, as of minute 0.')).toBeTruthy();
    const search = recon().getByLabelText('Search');
    fireEvent.input(search, { target: { value: 'harr' } });
    expect(rows()).toEqual(['Gibbon · Harrow', '15th Massachusetts700steady · 100%']);
    fireEvent.input(search, { target: { value: 'gibbon' } });
    expect(rows()).toHaveLength(2);
    fireEvent.input(search, { target: { value: 'minnesota' } });
    expect(rows()).toEqual(['Unattached · Unattached', '1st Minnesota900steady · 100%']);
    fireEvent.input(search, { target: { value: 'nobody' } });
    expect(recon().getByText('None to show.')).toBeTruthy();
  });

  it('a player sees their own, the enemy in sight, and the enemy lost from sight as last seen', () => {
    const admin = overTheRidge();
    admin.battle.value!.units.get('cs_bat')!.morale.forceBreak();
    const player = createStore(1, 'player');
    expect(player.open(admin.playerFileDownload(0).text)).toBeNull();
    render(<App store={player} />);
    fireEvent.click(screen.getByRole('tab', { name: 'Recon' }));
    expect(recon().getAllByRole('button').filter((b) => b.closest('.chips')).map((b) => b.textContent))
      .toEqual(['Ours · 3', 'In sight · 1', 'Lost from sight · 1']);
    expect(rows()).toEqual(['Unattached · Unattached', "Ross's Battery~70in sight, broken"]);
    fireEvent.click(chip(/^Lost from sight/));
    expect(rows()).toEqual(['Unattached · Unattached', '10th Alabama~800? last seen round 1']);
    fireEvent.click(chip(/^Ours/));
    expect(rows()).toHaveLength(4);
    expect(rows()[1]).toMatch(/^1st Minnesota900(steady|shaken|wavering) · \d+%$/);
  });

  it('a regiment lost from sight while broken says both; one in sight standing', () => {
    const admin = overTheRidge();
    const player = createStore(1, 'player');
    player.open(admin.playerFileDownload(0).text);
    // as last seen broken (the file holds it as it was when last seen)
    player.battle.value!.units.get('cs_10al')!.morale.forceBreak();
    render(<App store={player} />);
    fireEvent.click(chip(/^Lost from sight/));
    expect(rows()[1]).toBe('10th Alabama~800? last seen round 1, broken');
    fireEvent.click(chip(/^In sight/));
    expect(rows()[1]).toBe("Ross's Battery~70in sight, standing");
  });
});
