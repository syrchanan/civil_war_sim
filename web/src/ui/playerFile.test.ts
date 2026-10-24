import { describe, expect, it } from 'vitest';

import { battleTag, PLAYER_FORMAT, roughly } from '../engine';
import { createStore } from './store';

/** The admin's battle, a round in, and the player file for one side. */
const fromAdmin = (side: 0 | 1 = 0) => {
  const admin = createStore(1863);
  admin.start();
  admin.setOrder('us_1mn', { mode: 'ranged', target: 'cs_8al' });
  admin.setOrder('cs_8al', { mode: 'ranged', target: 'us_1mn' });
  admin.resolve();
  return { admin, file: admin.playerFileDownload(side) };
};
const opened = (side: 0 | 1 = 0) => {
  const { admin, file } = fromAdmin(side);
  const player = createStore(1, 'player');
  expect(player.open(file.text)).toBeNull();
  return { admin, player };
};

describe('admin: a player file for each side', () => {
  it('is the battle as that side sees it, named for the side and the next round', () => {
    const { admin, file } = fromAdmin(1);
    expect(file.name).toBe('player-1863-round-2-Confederate.json');
    const data = JSON.parse(file.text);
    expect(data).toMatchObject({ format: PLAYER_FORMAT, side: 1, tag: battleTag(admin.battle.value!.toDict()) });
    expect(data.state.units.find((u: { id: string }) => u.id === 'us_1mn').stats).toBe('5/5/0/0');
  });

  it('an admin can\'t open a player file by mistake', () => {
    const { admin, file } = fromAdmin(0);
    expect(admin.open(file.text)).toBe('This is the Union player\'s file; open the full battle file instead.');
  });
});

describe('player: planning from their file', () => {
  it('opens locked to its side; enemy units are rough and hidden', () => {
    const { admin, player } = opened(1);
    expect(player.playerFileInfo.value).toEqual({ side: 1, tag: battleTag(admin.battle.value!.toDict()) });
    expect(player.playerSide.value).toBe(1);
    expect(player.hiddenSide.value).toBe(0);
    const us = player.mapUnits.value.find((u) => u.uid === 'us_1mn')!;
    expect(us).toMatchObject({ rough: true, men: roughly(admin.battle.value!.units.get('us_1mn')!.size) });
    expect(player.mapUnits.value.find((u) => u.uid === 'cs_8al')!.rough).toBe(false);
  });

  it('their orders file carries the real battle\'s tag, so the admin accepts it', () => {
    const { admin, player } = opened(0);
    player.setOrder('us_15ma', { mode: 'ranged', target: 'cs_10al' });
    player.moveUnit('us_15ma', { x: 700, y: 850 });
    const plan = player.planDownload();
    expect(JSON.parse(plan.text).battle.tag).toBe(battleTag(admin.battle.value!.toDict()));
    expect(admin.loadPlans([plan])).toEqual([]);
    expect(admin.orders.value.us_15ma).toMatchObject({ mode: 'ranged', target: 'cs_10al' });
    expect(admin.mapUnits.value.find((u) => u.uid === 'us_15ma')).toMatchObject({ x: 700, y: 850 });
  });

  it('guesses about an enemy unit replace its unknowns, and the preview follows', () => {
    const { player } = opened(0);
    player.setOrder('us_1mn', { mode: 'ranged', target: 'cs_10al' });
    player.setOrder('cs_10al', { mode: 'ranged', target: 'us_1mn' });
    const rate = () => player.preview.value.arrows.find((a) => a.attacker === 'cs_10al')!.rate;
    const before = rate();
    expect(player.setGuess('cs_10al', { size: 1200, stats: '8/8/1/0' })).toBeNull();
    expect(player.guesses.value).toEqual({ cs_10al: { size: 1200, stats: '8/8/1/0' } });
    const unit = player.battle.value!.units.get('cs_10al')!;
    expect([unit.size, unit.front, unit.regiment.stats]).toEqual([1200, 1200, [8, 8, 1, 0]]);
    expect(unit.morale.initialMorale).toBe(80);
    expect(rate()).toBeGreaterThan(before);
    expect(player.mapUnits.value.find((u) => u.uid === 'cs_10al')!.men).toBe(1200);
  });

  it('bad guesses are refused, with why', () => {
    const { player } = opened(0);
    expect(player.setGuess('cs_10al', { size: 0 })).toBe('Men must be a whole number, 1 or more.');
    expect(player.setGuess('cs_10al', { stats: 'brave' })).toMatch(/slash-separated/);
    expect(player.guesses.value).toEqual({});
  });

  it('a broken enemy stays broken whatever the guess', () => {
    const { player } = opened(0);
    const b = player.battle.value!;
    b.units.get('cs_11al')!.morale.forceBreak();
    expect(player.setGuess('cs_11al', { size: 500 })).toBeNull();
    expect(b.units.get('cs_11al')!.morale.broken).toBe(true);
  });

  it('opening a full battle file afterwards unlocks the side', () => {
    const { admin, player } = opened(0);
    player.setGuess('cs_10al', { size: 900 });
    expect(player.open(admin.battle.value!.toJson())).toBeNull();
    expect([player.playerFileInfo.value, player.hiddenSide.value, player.guesses.value]).toEqual([null, null, {}]);
  });

  it('a player file of another version is refused', () => {
    const { file } = fromAdmin(0);
    const data = JSON.parse(file.text);
    data.version = 9;
    expect(createStore(1, 'player').open(JSON.stringify(data))).toBe('Unsupported player file version 9 (expected 1).');
  });
});
