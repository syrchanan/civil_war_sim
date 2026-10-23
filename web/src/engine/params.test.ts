import { describe, expect, it } from 'vitest';

import defaults from './defaults.json';
import fixture from '../../../test_cases/parity/params.json';
import { ValueError } from './errors';
import { CombatParams, type CombatData, roundHalfEven } from './params';

const combatDefaults = defaults.params.combat as CombatData;

describe('roundHalfEven (Python round)', () => {
  it.each([[0.5, 0], [1.5, 2], [2.5, 2], [3.5, 4], [5.5, 6], [2.4, 2], [2.6, 3], [7, 7]])('%s -> %s', (x, r) => {
    expect(roundHalfEven(x)).toBe(r);
  });
});

describe('CombatParams', () => {
  const combat = new CombatParams(combatDefaults);

  it('keeps the defaults', () => {
    expect(combat.toDict()).toEqual(combatDefaults);
  });

  it.each(fixture.combat.efficiency)('efficiency(%s, %s, %s, %s) = %s', (xp, morale, weapon, melee, expected) => {
    expect(combat.efficiency(xp, morale, weapon, melee)).toBe(expected);
  });

  it.each(fixture.combat.unit_coef as [number[], string, number][])('unitCoef(%j, %s) = %s', (stats, mode, expected) => {
    expect(combat.unitCoef(stats as [number, number, number, number], mode)).toBe(expected);
  });

  it.each(fixture.combat.melee_efficiency)('meleeEfficiency(%s, %s, %s) = %s', (xp, morale, rating, expected) => {
    expect(combat.meleeEfficiency(xp, morale, rating)).toBe(expected);
  });

  it.each([
    { weapon_multipliers: { 0: 1.0 } },
    { weapon_multipliers: { '-2': 0.2, '-1': 0.5, 0: 0.0, 1: 1.5, 2: 2.5 } },
    { xp_boost_per_level: -0.1 },
    { morale_boost_per_level: -0.1 },
    { melee_penalty_factor: 0.0 },
    { ranged_kill_rate: 0.0 },
    { melee_kill_rate: -1.0 },
    { broken_fire_multiplier: -0.1 },
    { broken_melee_multiplier: -0.1 },
    { artillery_ammo: {} },
    { artillery_ammo: { round_shot: 0.0 } },
    { artillery_default_ammo: 'grape' },
  ])('rejects %j', (change) => {
    expect(() => new CombatParams({ ...combatDefaults, ...change } as CombatData)).toThrow(ValueError);
  });

  it('copies what it is given', () => {
    const data = structuredClone(combatDefaults);
    const p = new CombatParams(data);
    data.weapon_multipliers['0'] = 99;
    expect(p.weapon_multipliers['0']).toBe(1.0);
    expect(Object.isFrozen(p)).toBe(true);
  });
});
