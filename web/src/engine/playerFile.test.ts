import { describe, expect, it } from 'vitest';

import fixture from '../../../test_cases/parity/battles.json';
import { Battle } from './battle';
import { ValueError } from './errors';
import { PLAYER_FORMAT, playerFile, roughly } from './playerFile';
import { battleTag, type StateData } from './state';

/** A battle two rounds in, with charges, modifiers and placed units. */
function fought(): Battle {
  const c = (fixture.cases as unknown as { name: string; seed: number; final: StateData }[])
    .find((x) => x.name === 'charges' && x.seed === 1)!;
  const data = structuredClone(c.final);
  data.finished = false;
  data.result = null;
  const b = Battle.fromDict(data);
  b.units.get('a_line')!.regiment.position = { x: 500, y: 800, z: 0, cover: 0, terrain_type: 'open', facing: 0 };
  b.units.get('x_line')!.regiment.position = { x: 520, y: 300, z: 0, cover: 0, terrain_type: 'open', facing: 180 };
  return b;
}

describe('rough numbers', () => {
  it('to the nearest 10 under 100 men (at least 10), else to the nearest 50; none stays none', () => {
    expect([0, 3, 14, 15, 96, 100, 124, 125, 812, 1974].map(roughly)).toEqual([0, 10, 10, 20, 100, 100, 100, 150, 800, 1950]);
  });
});

describe('a player file: the battle as one side sees it', () => {
  it('keeps the side, the real battle\'s tag, and its own units exactly', () => {
    const b = fought();
    const real = b.toDict();
    const file = playerFile(real, 0);
    expect(file).toMatchObject({ format: PLAYER_FORMAT, version: 1, side: 0, tag: battleTag(real) });
    const own = (d: StateData) => d.units.filter((u) => u.side === 0);
    expect(own(file.state)).toEqual(own(real));
    expect(file.state.seed).toBe(real.seed);
    expect(file.state.round).toBe(real.round);
    expect(file.state.rng_state).not.toEqual(real.rng_state);   // the dice stay with the admin
  });

  it('enemy units: name, type, place, broken or not, guns, and men roughly; nothing else', () => {
    const real = fought().toDict();
    const file = playerFile(real, 0);
    const enemy = file.state.units.find((u) => u.id === 'x_line')!;
    const truth = real.units.find((u) => u.id === 'x_line')!;
    expect(enemy).toMatchObject({
      name: truth.name, type: 'inf', subtype: 'line', size: roughly(truth.size), initial_size: roughly(truth.initial_size),
      stats: '5/5/0/0', initial_stats: '5/5/0/0', front_size: roughly(truth.size), position: truth.position,
      losses: 0, inflicted: 0, captured: 0, meta: {},
    });
    expect(enemy.morale).toEqual({ resolve: truth.morale.broken ? 0 : 1, shock: 0, lost: 0, broken: truth.morale.broken,
      break_scale: 1 });
    const battery = file.state.units.find((u) => u.id === 'x_bat')!;
    const realBattery = real.units.find((u) => u.id === 'x_bat')!;
    expect([battery.guns, battery.guns_lost]).toEqual([realBattery.guns, realBattery.guns_lost]);
    const broken = file.state.units.find((u) => u.side === 1 && u.morale.broken);
    expect(broken!.raw_morale).toBe(0);
  });

  it('the rounds keep what could be seen; enemy numbers, odds, events and modifiers are gone', () => {
    const real = fought().toDict();
    const file = playerFile(real, 0);
    const enemyIds = new Set(real.units.filter((u) => u.side === 1).map((u) => u.id));
    file.state.history.forEach((r, i) => {
      const truth = real.history[i];
      expect(r.orders).toEqual(truth.orders);
      expect(r.positions).toEqual(truth.positions);
      expect(r.events).toEqual([]);
      expect(r.engagements.every((e) => !enemyIds.has(e.attacker))).toBe(true);
      expect(r.retargets.every((t) => !enemyIds.has(t.unit))).toBe(true);
      expect(Object.keys(r.modifiers).every((uid) => !enemyIds.has(uid))).toBe(true);
      expect(r.charges.map((c) => [c.charger, c.outcome])).toEqual(truth.charges.map((c) => [c.charger, c.outcome]));
      expect(r.charges.every((c) => c.p_home === null && c.p_falter === null && c.p_defender_breaks === null)).toBe(true);
      for (const uid of enemyIds) {
        expect(r.units[uid]).toEqual({ ...truth.units[uid], losses: 0, inflicted: 0, captured: 0, morale: 0,
          size: roughly(truth.units[uid].size) });
      }
      expect(r.units.a_line).toEqual(truth.units.a_line);
    });
    expect(real.history[0].modifiers.x_bat).toBeDefined();         // there were enemy modifiers to hide
    expect(file.state.history[0].modifiers.a_line).toEqual(real.history[0].modifiers.a_line);
  });

  it('loads as a battle the player can plan on', () => {
    const start = (fixture.cases as unknown as { name: string; start: StateData }[]).find((x) => x.name === 'charges')!.start;
    const file = playerFile(start, 1);
    const b = Battle.fromDict(file.state);
    expect(b.units.get('a_line')!.regiment.stats).toEqual([5, 5, 0, 0]);
    const mine = [...b.units.values()].find((u) => u.side === 1 && u.active)!;
    const theirs = [...b.units.values()].find((u) => u.side === 0 && u.size > 0)!;
    expect(b.engagements({ [mine.uid]: { target: theirs.uid, mode: 'ranged' } }).length).toBeGreaterThan(0);
  });

  it('only for a battle still being fought', () => {
    const b = fought();
    b.finish('auto');
    expect(() => playerFile(b.toDict(), 0)).toThrow(ValueError);
  });
});

describe('target switches in a player file', () => {
  it('only the player\'s own units\' switches are kept', () => {
    const real = fought().toDict();
    real.history[0].retargets = [
      { unit: 'a_line', old_target: 'x_line', new_target: 'x_irr', time: 10 },
      { unit: 'x_line', old_target: 'a_line', new_target: 'a_drag', time: 12 },
    ];
    expect(playerFile(real, 0).state.history[0].retargets.map((t) => t.unit)).toEqual(['a_line']);
  });
});
