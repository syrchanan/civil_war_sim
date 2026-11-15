/**
 * Large battles: two armies of about seventy regiments, organised in corps, divisions and brigades, for tests and
 * for trying the client at the size the admins play (seeded, so the same every time); and grouping any list of
 * units by their org for the rosters, the reconnaissance and the map.
 */

import { type Org, Rng } from '../engine';
import type { UnitDraft } from './store';

const STATES: [string[], string[]] = [
  ['Minnesota', 'Massachusetts', 'Maine', 'New York', 'Pennsylvania', 'Ohio', 'Michigan', 'Wisconsin', 'Indiana',
    'Vermont', 'New Jersey', 'Connecticut'],
  ['Alabama', 'Virginia', 'Georgia', 'Mississippi', 'North Carolina', 'South Carolina', 'Tennessee', 'Texas',
    'Louisiana', 'Arkansas', 'Florida', 'Kentucky'],
];
const COMMANDERS: [string[], string[]] = [
  ['Gibbon', 'Hays', 'Caldwell', 'Harrow', 'Webb', 'Hall', 'Carroll', 'Smyth', 'Willard', 'Cross', 'Kelly', 'Zook',
    'Brooke', 'Ward', 'Graham', 'De Trobriand', 'Burling'],
  ['Pickett', 'Heth', 'Pender', 'Kemper', 'Garnett', 'Armistead', 'Pettigrew', 'Brockenbrough', 'Davis', 'Archer',
    'Lane', 'Scales', 'Perrin', 'Thomas', 'Wilcox', 'Wright', 'Perry'],
];
const ORDINAL = (n: number) => `${n}${n % 100 >= 11 && n % 100 <= 13 ? 'th' : ['th', 'st', 'nd', 'rd'][n % 10] ?? 'th'}`;

/**
 * Two armies of a corps each: three divisions of four brigades of five regiments, a battery pair per division and a
 * cavalry brigade, about seventy units a side. Each regiment is named for a state, numbered in turn.
 */
export function bigArmies(seed: number): { sides: [string, string]; units: UnitDraft[] } {
  const rng = new Rng(seed);
  const pick = (lo: number, hi: number) => lo + Math.floor(rng.random() * (hi - lo + 1));
  const units: UnitDraft[] = [];
  for (const side of [0, 1] as const) {
    const numbers: Record<string, number> = {};
    const named = (state: string) => {
      numbers[state] = (numbers[state] ?? 0) + pick(1, 4);
      return `${ORDINAL(numbers[state])} ${state}`;
    };
    const commanders = [...COMMANDERS[side]];
    const corps = side === 0 ? 'II Corps' : 'Longstreet\'s Corps';
    const add = (u: Omit<UnitDraft, 'id' | 'side'>) => units.push({ ...u, id: `s${side}u${units.length + 1}`, side });
    for (let d = 0; d < 3; d++) {
      const division = `${commanders.shift()}'s Division`;
      for (let b = 0; b < 4; b++) {
        const org: Org = { corps, division, brigade: `${commanders.shift()}'s Brigade` };
        for (let r = 0; r < 5; r++) {
          const state = STATES[side][pick(0, STATES[side].length - 1)];
          add({ name: named(state), type: 'inf', subtype: 'line', size: pick(18, 50) * 10,
            stats: `${pick(3, 8)}/${pick(3, 8)}/${pick(0, 1)}/0`, guns: null, org });
        }
      }
      for (let g = 0; g < 2; g++) {
        add({ name: `${division.split("'")[0]}'s Battery ${'AB'[g]}`, type: 'art', subtype: 'battery', size: 72,
          stats: `${pick(4, 7)}/${pick(4, 7)}/${pick(0, 1)}/0`, guns: 6, org: { corps, division, brigade: 'Artillery' } });
      }
    }
    for (let c = 0; c < 4; c++) {
      add({ name: `${ORDINAL(c + 1)} ${side === 0 ? 'U.S.' : 'C.S.'} Cavalry`, type: 'cav', subtype: 'light',
        size: pick(25, 45) * 10, stats: `${pick(4, 8)}/${pick(4, 8)}/0/0`, guns: null,
        org: { corps, division: 'Cavalry', brigade: `${side === 0 ? 'Buford' : 'Stuart'}'s Brigade` } });
    }
  }
  return { sides: ['Union', 'Confederate'], units };
}

/** A group of units under one name at one level (a corps, a division, a brigade), with its subgroups. */
export interface OrgGroup<T> {
  level: 'corps' | 'division' | 'brigade';
  name: string;
  groups: OrgGroup<T>[];
  units: T[]; // the brigade's units (at the corps and division levels, none directly)
}

export const UNATTACHED = 'Unattached';
const LEVELS = ['corps', 'division', 'brigade'] as const;

/** Units grouped corps › division › brigade, in the order each group first appears; no org: 'Unattached'. */
export function groupByOrg<T>(units: T[], orgOf: (u: T) => Org | undefined): OrgGroup<T>[] {
  const top: OrgGroup<T>[] = [];
  for (const u of units) {
    const org = orgOf(u) ?? {};
    let level: OrgGroup<T>[] = top;
    let group: OrgGroup<T> | undefined;
    for (const key of LEVELS) {
      const name = org[key] ?? UNATTACHED;
      group = level.find((g) => g.name === name);
      if (group === undefined) {
        group = { level: key, name, groups: [], units: [] };
        level.push(group);
      }
      level = group.groups;
    }
    group!.units.push(u);
  }
  return top;
}

/** Every unit in a group, its subgroups' included. */
export function unitsIn<T>(group: OrgGroup<T>): T[] {
  return [...group.units, ...group.groups.flatMap((g) => unitsIn(g))];
}
