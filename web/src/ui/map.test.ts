import { afterEach, describe, expect, it, vi } from 'vitest';

import { ArtilleryBattery } from '../engine';
import { blockSize, FIELD } from './field';
import { createStore } from './store';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('store: the map before the battle', () => {
  it('every unit has a place, from the default layout', () => {
    const s = createStore(1863);
    const units = s.mapUnits.value;
    expect(units.map((u) => u.uid)).toEqual(s.units.value.map((u) => u.id));
    expect(units.every((u) => u.x > 0 && u.x < FIELD.width)).toBe(true);
    expect(units.find((u) => u.uid === 'us_1mn')).toMatchObject({ side: 0, y: FIELD.height * 0.75, width: 297,
      depth: 20, men: 900, broken: false, wiped: false, type: 'inf' });
    expect(units.find((u) => u.uid === 'cs_bat')!.width).toBe(120);
  });

  it('dragging moves a unit, kept on the field', () => {
    const s = createStore(1863);
    s.moveUnit('us_1mn', { x: 400.4, y: -30 });
    expect(s.mapUnits.value[0]).toMatchObject({ x: 400, y: 0 });
  });

  it('every unit faces the other side to start with, and can be turned', () => {
    const s = createStore(1863);
    expect(s.mapUnits.value.find((u) => u.uid === 'us_1mn')!.facing).toBe(0);
    expect(s.mapUnits.value.find((u) => u.uid === 'cs_8al')!.facing).toBe(180);
    s.faceUnit('us_1mn', -45);
    s.moveUnit('us_1mn', { x: 400, y: 900 });                  // moving keeps the facing
    expect(s.mapUnits.value[0]).toMatchObject({ x: 400, y: 900, facing: 315 });
  });

  it('new units get a place too', () => {
    const s = createStore(1);
    s.addUnit(1);
    expect(s.mapUnits.value.at(-1)!.y).toBe(FIELD.height * 0.25);
  });
});

describe('store: the map in battle', () => {
  const started = () => {
    const s = createStore(1863);
    s.moveUnit('us_1mn', { x: 500, y: 700 });
    s.start();
    return s;
  };

  it('starting the battle keeps the places, saved as positions on open ground', () => {
    const s = started();
    expect(s.battle.value!.units.get('us_1mn')!.regiment.position)
      .toEqual({ x: 500, y: 700, z: 0, cover: 0, terrain_type: 'open', facing: 0 });
    expect(s.battle.value!.toDict().units[3].position).toMatchObject({ facing: 180 });
    expect(s.mapUnits.value[0]).toMatchObject({ x: 500, y: 700 });
  });

  it('units move between rounds, and the move is saved', () => {
    const s = started();
    s.moveUnit('cs_8al', { x: 600, y: 600 });
    expect(s.battle.value!.units.get('cs_8al')!.regiment.position).toMatchObject({ x: 600, y: 600 });
    expect(s.mapUnits.value.find((u) => u.uid === 'cs_8al')).toMatchObject({ x: 600, y: 600 });
  });

  it('units turn between rounds, and the facing is saved', () => {
    const s = started();
    s.faceUnit('cs_8al', 90);
    expect(s.battle.value!.units.get('cs_8al')!.regiment.position).toMatchObject({ facing: 90 });
    s.moveUnit('cs_8al', { x: 600, y: 600 });
    expect(s.mapUnits.value.find((u) => u.uid === 'cs_8al')).toMatchObject({ x: 600, y: 600, facing: 90 });
    s.finish('auto');
    s.faceUnit('cs_8al', 0);                                   // not once it is over
    expect(s.mapUnits.value.find((u) => u.uid === 'cs_8al')!.facing).toBe(90);
  });

  it('blocks shrink with losses; broken and wiped-out units are marked', () => {
    const s = started();
    const battle = s.battle.value!;
    battle.units.get('us_1mn')!.regiment.updateSize(450);
    battle.units.get('cs_8al')!.morale.forceBreak();
    battle.units.get('cs_10al')!.regiment.updateSize(0);
    s.touch();
    const byId = Object.fromEntries(s.mapUnits.value.map((u) => [u.uid, u]));
    expect(byId.us_1mn).toMatchObject({ men: 450, width: 149 });
    expect(byId.cs_8al.broken).toBe(true);
    expect(byId.cs_10al.wiped).toBe(true);
  });

  it('orders are arrows: fire and charge, not hold', () => {
    const s = started();
    s.setOrder('us_1mn', { mode: 'ranged', target: 'cs_8al' });
    s.setOrder('cs_8al', { mode: 'melee', target: 'us_1mn' });
    expect(s.orderArrows.value).toEqual([
      { from: 'us_1mn', to: 'cs_8al', mode: 'ranged', side: 0 },
      { from: 'cs_8al', to: 'us_1mn', mode: 'melee', side: 1 },
    ]);
  });

  it('no moves once the battle is finished', () => {
    const s = started();
    s.finish('auto');
    s.moveUnit('us_1mn', { x: 10, y: 10 });
    expect(s.mapUnits.value[0]).toMatchObject({ x: 500, y: 700 });
    expect(s.orderArrows.value).toEqual([]);
  });

  it('a saved battle opens with its positions; units without one get the default layout', () => {
    const s = started();
    const data = s.battle.value!.toDict();
    data.units[1].position = null;
    data.units[3].position!.facing = null;                    // e.g. a Python setup that gave none
    const other = createStore(1);
    other.open(JSON.stringify(data));
    const units = other.mapUnits.value;
    expect(units[0]).toMatchObject({ x: 500, y: 700, facing: 0 });
    expect(units[1].y).toBe(FIELD.height * 0.75);
    expect(units[3].facing).toBe(180);                         // facing the other side
  });
});

describe('store: replaying rounds on the map', () => {
  const twoRounds = () => {
    const s = createStore(1863);
    s.moveUnit('us_1mn', { x: 500, y: 700 });
    s.start();
    s.setOrder('us_1mn', { mode: 'ranged', target: 'cs_8al' });
    s.setOrder('cs_bat', { mode: 'ranged', target: 'us_bat' });
    s.resolve();
    s.moveUnit('us_1mn', { x: 600, y: 650 });
    s.faceUnit('us_1mn', 30);
    s.setOrder('us_1mn', { mode: 'idle' });
    s.resolve();
    return s;
  };
  const shown = (s: ReturnType<typeof createStore>, uid: string) => s.mapUnits.value.find((u) => u.uid === uid)!;

  it('shows a round as it began: places, men, broken units and that round\'s orders', () => {
    const s = twoRounds();
    const b = s.battle.value!;
    expect(s.replayRounds.value).toEqual([1, 2]);
    s.mapRound.value = 1;
    expect(shown(s, 'us_1mn')).toMatchObject({ x: 500, y: 700, facing: 0, men: 900, broken: false });
    expect(shown(s, 'us_bat').men).toBe(72);
    expect(s.orderArrows.value).toEqual([
      { from: 'us_1mn', to: 'cs_8al', mode: 'ranged', side: 0 }, { from: 'cs_bat', to: 'us_bat', mode: 'ranged', side: 1 },
    ]);
    s.mapRound.value = 2;
    expect(shown(s, 'us_1mn')).toMatchObject({ x: 600, y: 650, facing: 30, men: b.history[0].units.us_1mn.size });
    expect(shown(s, 'us_bat').men).toBe(b.history[0].units.us_bat.size);
    expect(s.orderArrows.value.map((a) => a.from)).toEqual(['cs_bat']);
    s.mapRound.value = null;                                    // back to now
    expect(shown(s, 'us_1mn').men).toBe(b.units.get('us_1mn')!.size);
  });

  it('a battery is drawn with the guns it had then', () => {
    const s = twoRounds();
    const b = s.battle.value!;
    b.history[1].units.us_bat.guns_lost = 2;                    // say two guns were taken in round 2
    s.mapRound.value = 2;
    expect(shown(s, 'us_bat').width).toBe(blockSize('art', 0, 0, (b.units.get('us_bat')!.regiment as ArtilleryBattery).guns + 2).width);
  });

  it('units broken in an earlier round are shown broken; nothing moves while replaying', () => {
    const s = twoRounds();
    s.battle.value!.history[0].units.cs_8al.broken = true;
    s.mapRound.value = 2;
    expect(shown(s, 'cs_8al').broken).toBe(true);
    s.moveUnit('cs_8al', { x: 10, y: 10 });
    s.faceUnit('cs_8al', 90);
    s.mapRound.value = null;
    expect(shown(s, 'cs_8al')).not.toMatchObject({ x: 10, y: 10 });
    expect(shown(s, 'cs_8al').facing).toBe(180);
  });

  it('rounds saved without positions use the default layout; opening or resetting goes back to now', () => {
    const s = twoRounds();
    const data = s.battle.value!.toDict();
    data.history[0].positions = {};
    data.history[1].positions.cs_8al.facing = null;            // placed, but no facing given
    const other = createStore(1);
    other.open(JSON.stringify(data));
    other.mapRound.value = 1;
    expect(shown(other, 'us_1mn').y).toBe(FIELD.height * 0.75);
    other.mapRound.value = 2;
    expect(shown(other, 'cs_8al').facing).toBe(180);
    other.open(JSON.stringify(data));
    expect(other.mapRound.value).toBeNull();
    other.mapRound.value = 1;
    other.reset();
    expect(other.mapRound.value).toBeNull();
    expect(other.replayRounds.value).toEqual([]);
  });
});

describe('store: picking targets on the map', () => {
  const started = (mode: 'admin' | 'player' = 'admin') => {
    const s = createStore(1863, mode);
    s.updateUnit('cs_11al', { stats: '3/4/0/1' });              // melee only
    s.start();
    return s;
  };

  it('what a unit can do: fire if it has a ranged weapon, charge if it can fight hand to hand', () => {
    const s = started();
    expect(s.actionsFor('us_1mn')).toEqual(['ranged', 'melee']);
    expect(s.actionsFor('cs_11al')).toEqual(['melee']);
  });

  it('click a unit, then an enemy, then confirm how to attack it', () => {
    const s = started();
    s.clickUnit('us_1mn');
    expect(s.aiming.value).toBe('us_1mn');
    s.clickUnit('us_15ma');                                    // not a target: aim with that unit instead
    expect(s.aiming.value).toBe('us_15ma');
    s.clickUnit('cs_8al');
    expect(s.targetChoice.value).toEqual({ from: 'us_15ma', to: 'cs_8al', actions: ['ranged', 'melee'] });
    expect(s.orders.value.us_15ma.mode).toBe('idle');          // nothing changes until confirmed
    s.chooseAction('melee');
    expect(s.orders.value.us_15ma).toMatchObject({ mode: 'melee', target: 'cs_8al' });
    expect([s.aiming.value, s.targetChoice.value]).toEqual([null, null]);
  });

  it('a new target keeps the action; a unit that only fights hand to hand is only offered a charge', () => {
    const s = started();
    s.setOrder('us_bat', { mode: 'ranged', target: 'cs_8al' });
    s.setOrder('us_bat', { ammo: 'canister' });
    s.clickUnit('us_bat');
    s.clickUnit('cs_bat');
    s.chooseAction('ranged');
    expect(s.orders.value.us_bat).toMatchObject({ mode: 'ranged', target: 'cs_bat', ammo: 'canister' });
    s.clickUnit('cs_11al');
    s.clickUnit('us_1mn');
    expect(s.targetChoice.value!.actions).toEqual(['melee']);
  });

  it('clicking the aiming unit again, or cancelling, stops aiming', () => {
    const s = started();
    s.clickUnit('us_1mn');
    s.clickUnit('us_1mn');
    expect(s.aiming.value).toBeNull();
    s.clickUnit('us_1mn');
    s.clickUnit('cs_8al');
    s.cancelTargeting();
    expect([s.aiming.value, s.targetChoice.value]).toEqual([null, null]);
    expect(s.orders.value.us_1mn.mode).toBe('idle');
  });

  it('broken, wiped-out and can\'t-fight units don\'t aim; broken enemies can still be targeted', () => {
    const s = started();
    const b = s.battle.value!;
    b.units.get('cs_8al')!.morale.forceBreak();
    b.units.get('us_15ma')!.regiment.updateSize(0);
    s.touch();
    s.clickUnit('cs_8al');
    s.clickUnit('us_15ma');
    expect(s.aiming.value).toBeNull();
    s.clickUnit('us_1mn');
    s.clickUnit('us_15ma');                                    // wiped out: neither aims nor is a target
    expect(s.aiming.value).toBe('us_1mn');
    s.clickUnit('cs_8al');
    expect(s.targetChoice.value).toMatchObject({ from: 'us_1mn', to: 'cs_8al' });
  });

  it('a unit with nothing it can do doesn\'t aim', () => {
    const s = started();
    b_noActions(s);
    s.clickUnit('us_1mn');
    expect(s.aiming.value).toBeNull();
  });

  it('nothing to aim before the battle, once it is over, or while replaying', () => {
    const before = createStore(1863);
    before.clickUnit('us_1mn');
    expect(before.aiming.value).toBeNull();
    const s = started();
    s.resolve();
    s.mapRound.value = 1;
    s.clickUnit('us_1mn');
    expect(s.aiming.value).toBeNull();
    s.mapRound.value = null;
    s.finish('auto');
    s.clickUnit('us_1mn');
    expect(s.aiming.value).toBeNull();
  });

  it('a player aims their own units (orders) and enemy units (what they expect)', () => {
    const s = started('player');
    s.clickUnit('cs_8al');
    s.clickUnit('us_1mn');
    s.chooseAction('ranged');
    expect(s.isAssumed('cs_8al')).toBe(true);
    expect(s.effectiveOrders.value.cs_8al).toMatchObject({ mode: 'ranged', target: 'us_1mn' });
    expect(s.orders.value.cs_8al.mode).toBe('idle');
  });
});

/** Make every unit unable to fire or fight (all combat coefficients 0). */
function b_noActions(s: ReturnType<typeof createStore>) {
  vi.spyOn(Object.getPrototypeOf(s.battle.value!.params.combat), 'unitCoef').mockReturnValue(0);
}
