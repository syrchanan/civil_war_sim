import { describe, expect, it } from 'vitest';

import defaults from './defaults.json';
import fixture from '../../../test_cases/parity/params.json';
import { ValueError } from './errors';
import {
  AftermathParams, type AftermathData, BattleParams, ChargeParams, type ChargeData, CombatParams, type CombatData, MatchupParams,
  type MatchupData, MoraleParams, type MoraleData, type Overrides, type ParamsData, roundHalfEven, type Unit,
} from './params';

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

describe('MoraleParams', () => {
  const data = defaults.params.morale as MoraleData;

  it('keeps the defaults', () => {
    expect(new MoraleParams(data).toDict()).toEqual(data);
  });

  it.each([
    { break_fraction_min: 0.0 }, { break_fraction_min: 0.9 }, { break_fraction_max: 1.1 },
    { experience_weight: 1.5 }, { break_point_spread: -0.1 }, { break_fraction_ceiling: 0.0 },
    { break_fraction_ceiling: 1.1 }, { break_curve: 0.0 }, { size_reference: 0.0 }, { shock_half_life: 0.0 },
    { acceleration: -1 }, { shock_weight: -1 }, { helpless_weight: -1 }, { drain_per_hour: -1 },
    { gain_weight: -1 },
  ])('rejects %j', (change) => {
    expect(() => new MoraleParams({ ...data, ...change })).toThrow(ValueError);
  });
});

describe('AftermathParams', () => {
  const data = defaults.params.aftermath as AftermathData;

  it('keeps the defaults', () => {
    expect(new AftermathParams(data).toDict()).toEqual(data);
  });

  it.each([
    { rout_capture_share: -0.1 }, { rout_capture_share: 1.1 }, { cavalry_capture_multiplier: -1 },
    { killed_share: 1.5 }, { walking_wounded_share: -0.2 }, { wounded_captured_share: 2 },
    { wounded_return_share: -0.1 }, { share_spread: 1.5 }, { field_exchange_ratio: 0.9 },
    { field_standing_ratio: 0.5 }, { field_rout_gap: -0.1 }, { field_rout_gap: 1.1 },
    { field_votes_needed: 0 }, { field_votes_needed: 4 }, { field_votes_needed: 1.5 },
  ])('rejects %j', (change) => {
    expect(() => new AftermathParams({ ...data, ...change })).toThrow(ValueError);
  });
});

/** 'inf/line' -> ['inf', 'line'], 'inf' -> ['inf', null] */
const unit = (key: string): Unit => {
  const [type, sub] = key.split('/');
  return [type, sub ?? null];
};

describe('MatchupParams', () => {
  const data = defaults.params.matchups as MatchupData;
  const matchups = new MatchupParams(data);

  it('keeps the defaults', () => {
    expect(matchups.toDict()).toEqual(data);
  });

  it.each(fixture.matchups.multiplier as [string, string, string, number][])(
    'multiplier(%s, %s, %s) = %s', (a, t, mode, expected) => {
      expect(matchups.multiplier(unit(a), unit(t), mode)).toBe(expected);
    });

  it.each(fixture.matchups.melee_rating as [string, number][])('meleeRating(%s) = %s', (key, expected) => {
    expect(matchups.meleeRating(unit(key))).toBe(expected);
  });

  const row = { inf: 1, cav: 1, art: 1 };
  it.each([
    { ranged: { inf: { inf: 1.0 } } },
    { melee: { inf: { inf: -1.0, cav: 1.0, art: 1.0 }, cav: row, art: row } },
    { melee_ratings: { 'inf/line': 0.7 } },
    { melee_ratings: { default: 0.7, 'inf/musketeers': 0.7 } },
    { melee_ratings: { default: 0.7, inf: 0.7 } },
    { melee_ratings: { default: 0.7, 'inf/line': -0.1 } },
    { overrides: [{ attacker: 'inf/pikes', target: 'cav', mode: 'charge', multiplier: 2 }] },
    { overrides: [{ attacker: 'dragon', target: 'cav', mode: 'melee', multiplier: 2 }] },
    { overrides: [{ attacker: 'inf', target: '*', mode: 'melee', multiplier: 2 }] },
    { overrides: [{ attacker: 'inf/pikes', target: 'cav', mode: 'melee', multiplier: -2 }] },
    { overrides: [{ attacker: 'inf/pikes', target: 'cav', mode: 'melee' }] },
  ])('rejects %j', (change) => {
    expect(() => new MatchupParams({ ...data, ...change } as MatchupData)).toThrow(ValueError);
  });
});

describe('ChargeParams', () => {
  const data = defaults.params.charge as ChargeData;
  const charge = new ChargeParams(data);

  it('keeps the defaults', () => {
    expect(charge.toDict()).toEqual(data);
  });

  it.each(fixture.charge.steadiness)('steadiness(%s, %s, %s) = %s', (resolve, xp, shock, expected) => {
    expect(charge.steadiness(resolve, xp, shock)).toBe(expected);
  });

  it.each(fixture.charge.bonus as [string, string, number][])('bonus(%s, %s) = %s', (c, t, expected) => {
    expect(charge.bonus(unit(c), unit(t))).toBe(expected);
  });

  it.each(fixture.charge.pressure)('pressure(%s, %s, %s, %s, %s) = %s', (cm, tm, cs, ts, b, expected) => {
    expect(charge.pressure(cm, tm, cs, ts, b)).toBe(expected);
  });

  it.each(fixture.charge.odds as [number, number[]][])('odds(%s) = %j', (x, expected) => {
    expect(charge.odds(x)).toEqual(expected);
  });

  it.each([
    { approach_minutes: { navy: 5 } },
    { approach_minutes: { inf: 0, cav: 2, art: 5 } },
    { closing_fire_multiplier: -1 }, { numbers_weight: -1 }, { steadiness_weight: -1 }, { veterancy_weight: 1.5 },
    { shock_weight: -1 }, { break_threshold: -0.1 }, { falter_threshold: -0.1 }, { spread: 0 },
    { falter_cost: 1.5 },
    { shock_bonus: [{ charger: 'inf', target: 'inf' }] },
    { shock_bonus: [{ charger: 'inf/hussars', target: 'inf', bonus: 1 }] },
  ])('rejects %j', (change) => {
    expect(() => new ChargeParams({ ...data, ...change } as ChargeData)).toThrow(ValueError);
  });
});

describe('BattleParams', () => {
  const base = BattleParams.defaults();

  it('defaults come from defaults.json', () => {
    expect(base.toDict()).toEqual(defaults.params);
    expect(BattleParams.defaults()).toBe(base);
  });

  it.each(fixture.overrides.valid as unknown as [Overrides, ParamsData][])('accepts %j', (overrides, expected) => {
    expect(base.withOverrides(overrides).toDict()).toEqual(expected);
  });

  it.each(fixture.overrides.invalid as unknown as Overrides[])('rejects %j', (overrides) => {
    expect(() => base.withOverrides(overrides)).toThrow(ValueError);
  });

  it('leaves the original unchanged and round-trips through JSON', () => {
    const tuned = base.withOverrides({ combat: { weapon_multipliers: { 2: 3.0 } }, morale: { acceleration: 2.0 } });
    expect(base.toDict()).toEqual(defaults.params);
    const data = JSON.parse(JSON.stringify(tuned.toDict()));
    expect(data.combat.weapon_multipliers['2']).toBe(3.0);
    expect(BattleParams.fromDict(data).toDict()).toEqual(tuned.toDict());
  });

  it('fromDict accepts partial data', () => {
    expect(BattleParams.fromDict({ morale: { gain_weight: 0.0 } }).morale.gain_weight).toBe(0.0);
  });

  it('rejects a weapon code that is not a number', () => {
    expect(() => base.withOverrides({ combat: { weapon_multipliers: { x: 1.0 } } })).toThrow(ValueError);
  });
});

describe('MatchupParams with a missing table', () => {
  it('rejects it', () => {
    expect(() => new MatchupParams({ ...(defaults.params.matchups as MatchupData), ranged: null as never }))
      .toThrow(ValueError);
  });
});
