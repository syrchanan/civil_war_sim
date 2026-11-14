// State file version 3 and the game flow: units' org, the battle's plan, deployment, opening the battle, rounds
// planned; and the player file during deployment.
import { describe, expect, it } from 'vitest';

import reference from '../../../test_cases/battle_state_v2.json';
import { Battle, type UnitSpec } from './battle';
import { RuntimeError, ValueError } from './errors';
import { inside, validateOrg, validatePlan } from './plan';
import { playerFile } from './playerFile';
import { Rng } from './rng';
import { battleFromDict, type StateData } from './state';
import { InfantryRegiment } from './units';

const ZONES = { 0: { x: 0, y: 700, w: 2000, h: 500 }, 1: { x: 0, y: 0, w: 2000, h: 500 } };

function battle(plan: unknown = { phase: 'deployment', zones: ZONES, rounds_planned: 2, start_clock: '13:00' }): Battle {
  const units: Record<string, UnitSpec> = {
    u1: { side: 0, regiment: new InfantryRegiment(900, '6/6/1/0', 'line'), name: '1st Minnesota',
      org: { corps: 'II', division: 'Gibbon', brigade: 'Harrow' } },
    u2: { side: 0, regiment: new InfantryRegiment(700, '5/5/1/0', 'line'), name: '15th Massachusetts' },
    c1: { side: 1, regiment: new InfantryRegiment(1000, '5/6/0/0', 'line'), name: '8th Alabama',
      org: { division: 'Pickett', brigade: 'Kemper' } },
  };
  return new Battle(units, new Rng(1), undefined, { sides: ['Union', 'Confederate'] }, {}, null, plan);
}

const place = (b: Battle, uid: string, x: number, y: number) => {
  b.units.get(uid)!.regiment.position = { x, y, z: 0, cover: 0, terrain_type: 'open', facing: 0 };
};

describe('org', () => {
  it('keeps the names given, in order; empty ones are left out', () => {
    expect(validateOrg({ brigade: 'Harrow', corps: 'II', division: '' })).toEqual({ corps: 'II', brigade: 'Harrow' });
    expect(validateOrg({ division: null })).toEqual({});
  });

  it.each([
    ['II', 'must be a mapping'],
    [{ regiment: 'x' }, 'Unknown org key(s) regiment'],
    [{ corps: 2 }, 'org corps must be text, got 2.'],
  ])('%j is refused', (org, message) => {
    expect(() => validateOrg(org)).toThrow(message);
  });

  it('every unit carries one; none given is none', () => {
    const b = battle();
    expect(b.units.get('u1')!.org).toEqual({ corps: 'II', division: 'Gibbon', brigade: 'Harrow' });
    expect(b.units.get('u2')!.org).toEqual({});
  });
});

describe('plan', () => {
  it('is made complete; nothing given is open-ended, in battle, with no zones', () => {
    expect(validatePlan(null)).toEqual({ rounds_planned: null, start_clock: null, phase: 'battle', zones: {} });
    expect(validatePlan({ zones: { 1: ZONES[1], 0: ZONES[0] } }).zones).toEqual({ 0: ZONES[0], 1: ZONES[1] });
  });

  it.each([
    [[], 'The plan must be a mapping.'],
    [{ turns: 3 }, 'Unknown plan key(s) turns'],
    [{ rounds_planned: 0 }, 'rounds_planned must be a whole number'],
    [{ rounds_planned: 2.5 }, 'rounds_planned must be a whole number'],
    [{ start_clock: '1pm' }, "start_clock must be a time 'HH:MM'"],
    [{ start_clock: '24:00' }, "start_clock must be a time 'HH:MM'"],
    [{ start_clock: '12:60' }, "start_clock must be a time 'HH:MM'"],
    [{ phase: 'night' }, "phase must be 'deployment' or 'battle', got 'night'."],
    [{ zones: 'all' }, 'zones must be a mapping'],
    [{ zones: { 2: ZONES[0] } }, "A deployment zone's side must be 0 or 1, got '2'."],
    [{ zones: { 0: { x: 0, y: 0 } } }, "side 0's deployment zone must be {x, y, w, h} in yards."],
    [{ zones: { 0: { x: 'a', y: 0, w: 1, h: 1 } } }, "side 0's deployment zone x must be a number of yards, got 'a'."],
    [{ zones: { 1: { x: 0, y: 0, w: 0, h: 1 } } }, "side 1's deployment zone needs a width and a height above 0."],
  ])('%j is refused', (plan, message) => {
    expect(() => validatePlan(plan)).toThrow(message);
  });

  it('a zone holds its edges', () => {
    expect([inside(ZONES[0], 0, 700), inside(ZONES[0], 2000, 1200), inside(ZONES[0], 10, 699)]).toEqual([true, true, false]);
  });
});

describe('the game flow', () => {
  it('no round is fought while the armies deploy', () => {
    expect(() => battle().resolveRound(60, {})).toThrow(RuntimeError);
  });

  it('opening the battle needs every unit placed inside its side\'s zone', () => {
    const b = battle();
    place(b, 'u1', 800, 900);
    place(b, 'u2', 1000, 300); // in the enemy's zone
    expect(b.inZone('u1')).toBe(true);
    expect(b.inZone('c1')).toBe(true); // not placed yet: not outside
    expect(b.deploymentProblems()).toEqual([
      "15th Massachusetts stands outside its side's deployment zone.", '8th Alabama has not been placed.',
    ]);
    expect(() => b.openBattle()).toThrow("15th Massachusetts stands outside its side's deployment zone. 8th Alabama "
      + 'has not been placed.');
    place(b, 'u2', 1000, 900);
    place(b, 'c1', 900, 300);
    b.openBattle();
    expect(b.plan.phase).toBe('battle');
    expect(() => b.openBattle()).toThrow('already open');
    b.resolveRound(60, {});
  });

  it('a unit wiped out need not be placed; a side with no zone may stand anywhere', () => {
    const b = battle({ phase: 'deployment', zones: { 1: ZONES[1] } });
    b.units.get('u2')!.regiment.updateSize(0);
    place(b, 'u1', 1000, 100);
    place(b, 'c1', 1000, 100);
    expect(b.deploymentProblems()).toEqual([]);
  });

  it('rounds planned can be raised, never below the rounds fought', () => {
    const b = battle({ rounds_planned: 1 });
    b.resolveRound(30, {});
    b.resolveRound(30, {});
    expect(() => b.setRoundsPlanned(1)).toThrow('at least 2');
    expect(() => b.setRoundsPlanned(2.5)).toThrow(ValueError);
    b.setRoundsPlanned(4);
    expect(b.plan.rounds_planned).toBe(4);
    b.setRoundsPlanned(null);
    expect(b.plan.rounds_planned).toBeNull();
    expect(() => battle().setRoundsPlanned(0)).toThrow('at least 1');
  });
});

describe('the state file', () => {
  it('version 3 saves org and the plan, and loads them back', () => {
    const data = battle().toDict();
    expect(data.version).toBe(3);
    expect(data.units[0].org).toEqual({ corps: 'II', division: 'Gibbon', brigade: 'Harrow' });
    expect(data.plan).toEqual({ rounds_planned: 2, start_clock: '13:00', phase: 'deployment', zones: ZONES });
    expect(battleFromDict(JSON.parse(JSON.stringify(data))).toDict()).toEqual(data);
  });

  it('version 2 still loads: no org, an open plan', () => {
    const b = battleFromDict(reference as unknown as StateData);
    expect(b.plan).toEqual({ rounds_planned: null, start_clock: null, phase: 'battle', zones: {} });
    expect([...b.units.values()].every((u) => Object.keys(u.org).length === 0)).toBe(true);
    expect(() => battleFromDict({ ...(reference as unknown as StateData), version: 4 })).toThrow('expected 2 or 3');
  });
});

describe('the player file', () => {
  it('while deploying holds no enemy unit; own units keep their org', () => {
    const file = playerFile(battle().toDict(), 0);
    expect(file.state.units.map((u) => u.id)).toEqual(['u1', 'u2']);
    expect(file.state.units[0].org).toEqual({ corps: 'II', division: 'Gibbon', brigade: 'Harrow' });
    expect(JSON.stringify(file)).not.toContain('8th Alabama');
  });

  it('in battle, a seen enemy unit keeps its org', () => {
    const file = playerFile(battle(null).toDict(), 0);
    expect(file.state.units.find((u) => u.id === 'c1')!.org).toEqual({ division: 'Pickett', brigade: 'Kemper' });
  });
});
