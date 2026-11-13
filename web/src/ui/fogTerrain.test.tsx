// @vitest-environment jsdom
// Fog of war on the terrain: what one side can see past a ridge, in the player file and on the page.
import { act, cleanup, render, screen, within } from '@testing-library/preact';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { playerFile, sightings, Terrain } from '../engine';
import { App } from './App';
import { createStore, type Store } from './store';
import { unitInfoOf } from './UnitInfo';

beforeEach(() => localStorage.clear());
afterEach(cleanup);

// a ridge 40 yd high across the field at y 600-620; the Union south of it at y 900, the Confederates north at
// y 300, except the 10th Alabama and Ross's Battery, which start south of the ridge where the Union sees them
const RIDGE = (() => {
  const heights: number[] = [];
  for (let r = 0; r < 60; r++) for (let c = 0; c < 100; c++) heights.push(r === 30 ? 40 : 0);
  return { cell: 20, columns: 100, rows: 60, heights, ground: 'o'.repeat(6000), meta: {} };
})();

const ALONG: Record<string, number> = {
  us_1mn: 800, us_15ma: 1000, us_bat: 1200, cs_8al: 800, cs_10al: 1000, cs_11al: 1200, cs_bat: 1400,
};

/**
 * `rounds` fought (the 10th Alabama firing on the 15th Massachusetts, everyone else holding); then the 10th
 * Alabama pulls back behind the ridge.
 */
function overTheRidge(rounds = 1): Store {
  const s = createStore(1863);
  for (const [uid, x] of Object.entries(ALONG)) {
    const y = uid.startsWith('us') ? 900 : uid === 'cs_10al' || uid === 'cs_bat' ? 700 : 300;
    s.moveUnit(uid, { x, y });
  }
  s.start();
  (s.battle.value! as { terrain: Terrain | null }).terrain = new Terrain(RIDGE);
  s.touch();
  for (let i = 0; i < rounds; i++) {
    s.setOrder('cs_10al', { mode: 'ranged', target: 'us_15ma' });
    s.resolve();
  }
  s.moveUnit('cs_10al', { x: 1000, y: 300 });
  return s;
}

describe('sightings', () => {
  it('a unit behind the ridge is never seen; one that pulled back behind it was seen as round 1 began', () => {
    const sight = sightings(overTheRidge().battle.value!.toDict(), 0);
    expect(sight.get('cs_8al')).toEqual({ now: false, seen: new Set(), last: null });
    expect(sight.get('cs_10al')).toEqual({ now: false, seen: new Set([1]), last: 1 });
    expect(sight.get('cs_bat')).toEqual({ now: true, seen: new Set([1, 2]), last: 2 });
    expect(sight.has('us_1mn')).toBe(false);
  });

  it('the other side, looking south: the whole Union is in view of the units south of the ridge', () => {
    const sight = sightings(overTheRidge().battle.value!.toDict(), 1);
    expect([...sight.values()].every((x) => x.now)).toBe(true);
  });

  it('without terrain everything is seen', () => {
    const s = overTheRidge();
    (s.battle.value! as { terrain: Terrain | null }).terrain = null;
    expect([...sightings(s.battle.value!.toDict(), 0).values()].every((x) => x.now)).toBe(true);
  });

  it('only units still standing look; an unplaced unit sees and is seen; a plain regiment looks as infantry', () => {
    const data = overTheRidge().battle.value!.toDict();
    const union = data.units.filter((u) => u.side === 0);
    for (const u of union) u.size = 0; // all wiped out: nobody left to look
    data.history[0].units.us_1mn.size = 0;
    expect(sightings(data, 0).get('cs_bat')!.now).toBe(false);
    union[0].size = 10;
    union[0].position = null;
    union[0].type = null;
    expect(sightings(data, 0).get('cs_8al')!.now).toBe(true);
    data.units.find((u) => u.id === 'cs_8al')!.position = null;
    union[0].position = { x: 800, y: 900, z: 0, cover: 0, terrain_type: 'open', facing: 0 };
    expect(sightings(data, 0).get('cs_8al')!.now).toBe(true);
  });
});

describe('the player file', () => {
  it('holds nothing of a unit never seen', () => {
    const file = playerFile(overTheRidge().battle.value!.toDict(), 0);
    expect(file.version).toBe(2);
    expect(JSON.stringify(file)).not.toContain('cs_8al');
    expect(JSON.stringify(file)).not.toContain('8th Alabama');
  });

  it('a unit out of sight stands where it was last seen, marked with that round', () => {
    const real = overTheRidge().battle.value!.toDict();
    const file = playerFile(real, 0);
    const lost = file.state.units.find((u) => u.id === 'cs_10al')!;
    expect(lost.position).toMatchObject({ x: 1000, y: 700 });
    expect(lost.meta).toEqual({ last_seen: 1 });
    expect(lost.combat_mode).toBe('idle');
    expect(lost.size).toBe(800); // as round 1 began
    // round 1 began with it in view: its place and order then are kept
    expect(file.state.history[0].positions.cs_10al).toBeDefined();
    expect(file.state.history[0].orders.cs_10al).toBeDefined();
    expect(file.state.units.find((u) => u.id === 'cs_bat')!.meta).toEqual({});
  });

  it('how a unit ended a round shows only if it was seen as the next began; else as last seen', () => {
    const s = overTheRidge();
    s.resolve(); // round 2: the 10th Alabama behind the ridge all round
    s.moveUnit('cs_11al', { x: 1200, y: 700 }); // comes into view only now
    const real = s.battle.value!.toDict();
    real.history[1].units.cs_10al.size = 123;
    real.history[1].units.cs_10al.guns_lost = 1;
    const file = playerFile(real, 0);
    expect(file.state.history[1].units.cs_10al).toMatchObject({ size: 800, broken: false, broke_at: null, guns_lost: 0 });
    // the 11th Alabama, first seen now: earlier rounds show it as it began the battle
    expect(file.state.history[0].units.cs_11al).toMatchObject({ size: 600, broken: false, guns_lost: 0 });
    expect(file.state.history[0].positions.cs_11al).toBeUndefined();
    expect(file.state.units.find((u) => u.id === 'cs_11al')!.meta).toEqual({});
  });

  it('a unit last seen broken is shown broken, with when it broke', () => {
    const real = overTheRidge(2).battle.value!.toDict();
    real.history[0].units.cs_10al.broken = true;
    real.history[0].units.cs_10al.size = 640;
    real.units.find((u) => u.id === 'cs_10al')!.broke_time = 50;
    const file = playerFile(real, 0);
    const lost = file.state.units.find((u) => u.id === 'cs_10al')!;
    expect(lost.meta).toEqual({ last_seen: 2 });
    expect(lost.morale.broken).toBe(true);
    expect(lost.broke_time).toBe(50);
    expect(lost.size).toBe(650);
  });

  it('records naming a unit never seen are dropped: charges, engagements, flights, target switches, contacts', () => {
    const real = overTheRidge().battle.value!.toDict();
    const r = real.history[0];
    r.engagements.push({ attacker: 'us_1mn', target: 'cs_8al', mode: 'ranged' } as never);
    r.charges.push({ charger: 'us_1mn', target: 'cs_8al' } as never, { charger: 'us_1mn', target: 'cs_bat' } as never);
    r.flights.push({ unit: 'cs_8al', escaped_from: [] } as never, { unit: 'cs_bat', escaped_from: ['us_1mn', 'cs_8al'] } as never);
    r.retargets.push({ unit: 'us_1mn', old_target: 'cs_8al', new_target: 'cs_bat' } as never);
    real.contacts.push(['us_1mn', 'cs_8al'], ['us_bat', 'cs_bat'], ['us_15ma', 'cs_10al']);
    const f = playerFile(real, 0).state;
    expect(f.history[0].engagements.some((e) => e.target === 'cs_8al')).toBe(false);
    expect(f.history[0].charges.map((c) => c.target)).toEqual(['cs_bat']);
    expect(f.history[0].flights).toEqual([{ unit: 'cs_bat', escaped_from: ['us_1mn'] }]);
    expect(f.history[0].retargets).toEqual([]);
    expect(f.contacts).toEqual([['us_bat', 'cs_bat']]);  // not with a unit out of sight now
  });
});

/** The Union player's file, opened in player view. */
function asUnion(): Store {
  const admin = overTheRidge();
  const player = createStore(1, 'player');
  expect(player.open(admin.playerFileDownload(0).text)).toBeNull();
  return player;
}

describe('on the page, from a player file', () => {
  it('the map leaves out what was never seen and marks what is out of sight with a question mark', () => {
    const s = asUnion();
    render(<App store={s} />);
    expect(screen.queryByRole('button', { name: /^8th Alabama,/ })).toBeNull();
    const lost = screen.getByRole('button', { name: /^10th Alabama, about 800 men, last seen as round 1 began,/ });
    expect(lost.classList.contains('lost')).toBe(true);
    expect(lost.querySelector('.lost-mark')!.textContent).toBe('?');
    expect(lost.querySelector('.unit-men')!.textContent).toBe('~800, last seen round 1');
    expect(screen.getByRole('button', { name: /^Ross's Battery,/ }).classList.contains('lost')).toBe(false);
  });

  it('a unit out of sight can\'t be targeted, has no front arc, and nothing is expected of it', () => {
    const s = asUnion();
    expect(s.targetsFor('us_1mn').map((u) => u.uid)).toEqual(['cs_bat']);
    expect(s.effectiveOrders.value.cs_10al.mode).toBe('idle');
    s.setLayer('allArcs', true);
    render(<App store={s} />);
    expect(document.querySelectorAll('.front-arc.side-1')).toHaveLength(1);
    const expected = screen.getByRole('table', { name: 'What you expect the enemy to do' });
    expect(within(expected).queryByText('10th Alabama')).toBeNull();
    expect(within(expected).getByText("Ross's Battery")).toBeTruthy();
  });

  it('the unit card says where it was last seen, and draws no picture', () => {
    const s = asUnion();
    s.selectUnit('cs_10al');
    expect(Object.fromEntries(unitInfoOf(s)!.rows)).toEqual({
      Men: '~800', Status: 'Out of sight; last seen as round 1 began',
    });
    render(<App store={s} />);
    expect(document.querySelector('.vignette')).toBeNull();
  });

  it('a unit last seen broken says so', () => {
    const admin = overTheRidge();
    const data = JSON.parse(admin.playerFileDownload(0).text);
    data.state.units.find((u: { id: string }) => u.id === 'cs_10al').morale.broken = true;
    const s = createStore(1, 'player');
    s.open(JSON.stringify(data));
    s.selectUnit('cs_10al');
    expect(Object.fromEntries(unitInfoOf(s)!.rows).Status).toBe('Out of sight; last seen as round 1 began, broken');
  });

  it('replaying round 1 shows the units seen as it began', () => {
    const s = asUnion();
    s.mapRound.value = 1;
    const shown = s.mapUnits.value.map((u) => u.uid);
    expect(shown).toContain('cs_10al');
    expect(shown).not.toContain('cs_8al');
    expect(s.mapUnits.value.find((u) => u.uid === 'cs_10al')!.lastSeen).toBeNull();
  });

  it('an enemy unit never placed on the map is always seen, in replays too', () => {
    const real = overTheRidge().battle.value!.toDict();
    real.units.find((u) => u.id === 'cs_11al')!.position = null;
    delete real.history[0].positions.cs_11al;
    const s = createStore(1, 'player');
    s.open(JSON.stringify(playerFile(real, 0)));
    s.mapRound.value = 1;
    expect(s.mapUnits.value.map((u) => u.uid)).toContain('cs_11al');
  });

  it('the order of battle counts only the units seen, and says so', () => {
    const s = asUnion();
    render(<App store={s} />);
    expect(screen.getByText(/only the units you have seen/)).toBeTruthy();
    const enemy = within(screen.getByRole('table', { name: 'Order of battle' })).getAllByRole('row')
      .find((r) => r.textContent!.startsWith('Confederate'))!;
    expect(enemy.textContent).toMatch(/^Confederate2/); // the 10th Alabama and Ross's Battery
  });

  it('a version 1 player file (before this fog) still opens', () => {
    const admin = overTheRidge();
    const data = JSON.parse(admin.playerFileDownload(0).text);
    data.version = 1;
    expect(createStore(1, 'player').open(JSON.stringify(data))).toBeNull();
  });
});

describe('practising in player view', () => {
  function practising(): Store {
    const s = createStore(1863, 'player');
    for (const [uid, x] of Object.entries(ALONG)) s.moveUnit(uid, { x, y: uid.startsWith('us') ? 900 : uid === 'cs_bat' ? 700 : 300 });
    s.start();
    (s.battle.value! as { terrain: Terrain | null }).terrain = new Terrain(RIDGE);
    s.touch();
    return s;
  }

  it('only what the line of sight shows: no marker, no target, no arrow to what is hidden', () => {
    const s = practising();
    expect(s.mapUnits.value.filter((u) => u.side === 1).map((u) => u.uid)).toEqual(['cs_bat']);
    expect(s.targetsFor('us_1mn').map((u) => u.uid)).toEqual(['cs_bat']);
    const from1mn = () => s.orderArrows.value.filter((a) => a.from === 'us_1mn').map((a) => a.to);
    s.setOrder('us_1mn', { mode: 'melee', target: 'cs_8al' });
    expect(from1mn()).toEqual([]);
    expect(s.orderArrows.value.some((a) => a.from === 'cs_8al' || a.to === 'cs_8al')).toBe(false);
    s.setOrder('us_1mn', { mode: 'melee', target: 'cs_bat' });
    expect(from1mn()).toEqual(['cs_bat']);
    expect(s.orderOfBattle.value![1].units).toBe(1);
  });

  it('replaying a round: the units seen as it began', () => {
    const s = createStore(1863);
    for (const [uid, x] of Object.entries(ALONG)) s.moveUnit(uid, { x, y: uid.startsWith('us') ? 900 : uid === 'cs_bat' ? 700 : 300 });
    s.start();
    (s.battle.value! as { terrain: Terrain | null }).terrain = new Terrain(RIDGE);
    s.resolve();
    s.mode.value = 'player';
    act(() => { s.mapRound.value = 1; });
    expect(s.mapUnits.value.filter((u) => u.side === 1).map((u) => u.uid)).toEqual(['cs_bat']);
  });
});
