import { describe, expect, it } from 'vitest';

import defaults from './defaults.json';
import fixture from '../../../test_cases/parity/units.json';
import { ValueError } from './errors';
import {
  ArtilleryBattery, CavalryRegiment, closestMoraleStat, InfantryRegiment, parseStats, Regiment,
} from './units';

describe('closestMoraleStat', () => {
  it.each(fixture.closest_morale_stat)('%s -> %s', (raw, stat) => {
    expect(closestMoraleStat(raw)).toBe(stat);
  });

  it.each([-1, 100.5, NaN])('rejects %s', (raw) => {
    expect(() => closestMoraleStat(raw)).toThrow(ValueError);
  });
});

describe('parseStats', () => {
  it.each(fixture.stats_valid as [string, number[]][])('%s', (text, stats) => {
    expect(parseStats(text)).toEqual(stats);
  });

  it.each(fixture.stats_invalid)('rejects %j', (text) => {
    expect(() => parseStats(text)).toThrow(ValueError);
  });
});

describe('Regiment', () => {
  it('holds size, stats, front and raw morale', () => {
    const r = new Regiment(1000, '4/6/1/0');
    expect([r.size, r.stats, r.frontSize, r.rawMorale, r.combatMode, r.position]).toEqual(
      [1000, [4, 6, 1, 0], 1000, 60, 'idle', null]);
    expect([r.unitType, r.subtype, r.isMeleeOnly]).toEqual([null, null, false]);
    expect(new Regiment(500, '4/4/0/1', { frontSize: 200 }).frontSize).toBe(200);
    expect(new Regiment(500, '4/4/0/1').isMeleeOnly).toBe(true);
  });

  it('updates size, stats, front and combat mode', () => {
    const r = new Regiment(1000, '4/6/1/0');
    r.updateSize(800);
    r.updateStats('5/5/0/1');
    r.setFrontSize(0);
    r.setCombatMode('melee');
    expect([r.size, r.stats, r.frontSize, r.combatMode, r.isMeleeOnly]).toEqual([800, [5, 5, 0, 1], 0, 'melee', true]);
  });

  it('raw morale moves the morale stat to the closest level', () => {
    const r = new Regiment(1000, '4/6/1/0');
    r.updateRawMorale(44.0);
    expect([r.rawMorale, r.stats]).toEqual([44, [4, 4, 1, 0]]);
    r.updateRawMorale(45.0);                 // exact half goes down
    expect(r.stats).toEqual([4, 4, 1, 0]);
  });

  it('rejects bad values', () => {
    expect(() => new Regiment(10, '4/4/0')).toThrow(ValueError);
    expect(() => new Regiment(10, '4/4/0/0', { frontSize: -1 })).toThrow(ValueError);
    expect(() => new Regiment(10, '4/4/0/0', { frontSize: 1.5 })).toThrow(TypeError);
    expect(() => new Regiment(10, '4/4/0/0').setFrontSize(-1)).toThrow(ValueError);
    expect(() => new Regiment(10, '4/4/0/0').setCombatMode('charge')).toThrow(ValueError);
    expect(() => new Regiment(10, '4/4/0/0').updateStats('x')).toThrow(ValueError);
  });

  it('keeps a position as plain data (positions are parked)', () => {
    const position = { x: 1, y: 2, z: 3, cover: 0.5, terrain_type: 'forest' };
    expect(new Regiment(10, '4/4/0/0', { position }).position).toEqual(position);
  });
});

describe('typed units', () => {
  it.each([
    ['inf', (s: string) => new InfantryRegiment(500, '4/4/0/0', s)],
    ['cav', (s: string) => new CavalryRegiment(500, '4/4/0/0', s)],
    ['art', (s: string) => new ArtilleryBattery(72, '4/4/0/0', 8, s)],
  ] as const)('%s checks its subtype', (type, make) => {
    for (const subtype of (defaults.unit_subtypes as Record<string, string[]>)[type]) {
      const unit = make(subtype);
      expect([unit.unitType, unit.subtype]).toEqual([type, subtype]);
    }
    expect(() => make('hussars')).toThrow(ValueError);
  });
});

describe('ArtilleryBattery', () => {
  it.each(fixture.effective_guns)('%s guns, %s crew -> %s manned', (guns, crew, manned) => {
    expect(new ArtilleryBattery(crew, '4/4/0/0', guns, 'battery').effectiveGuns).toBe(manned);
  });

  it('standard battery is the config template', () => {
    const b = ArtilleryBattery.standard('4/4/0/0', 'battery');
    const { guns, crew_per_gun: crew } = defaults.artillery;
    expect([b.guns, b.size]).toEqual([guns, guns * crew]);
    expect(ArtilleryBattery.MIN_CREW_PER_GUN).toBe(fixture.min_crew_per_gun);
  });

  it('updates and checks guns', () => {
    const b = new ArtilleryBattery(72, '4/4/0/0', 8, 'battery');
    b.updateGuns(3);
    expect(b.guns).toBe(3);
    expect(() => b.updateGuns(-1)).toThrow(ValueError);
    expect(() => b.updateGuns(1.5)).toThrow(TypeError);
    expect(() => new ArtilleryBattery(72, '4/4/0/0', -1, 'battery')).toThrow(ValueError);
  });
});
