/**
 * The client's state, as signals: like ObservableJS cells, anything that reads a signal (a component, or a
 * `computed`) updates when the signal changes.
 *
 * The engine's Battle mutates in place as rounds are fought, so `revision` is bumped after every change to it,
 * and everything derived from the battle reads it.
 */

import { computed, signal } from '@preact/signals';

import {
  ArtilleryBattery, Battle, CavalryRegiment, InfantryRegiment, orderOfBattle, Regiment, Rng, type UnitSpec,
} from '../engine';

export type UnitType = 'inf' | 'cav' | 'art';

/** A unit as typed into the army builder (checked when the battle starts). */
export interface UnitDraft {
  id: string;
  name: string;
  side: 0 | 1;
  type: UnitType | null; // null: a generic unit, fighting as default infantry
  subtype: string | null;
  size: number; // artillery: crew
  stats: string; // experience/morale/weapon/melee-only
  guns: number | null; // artillery only
}

/** The usual subtype when a unit's type is picked. */
export const DEFAULT_SUBTYPE: Record<UnitType, string> = { inf: 'line', cav: 'light', art: 'battery' };
export const STANDARD_BATTERY = { size: 72, guns: 8 };

/** The Example Ridge armies (scenarios/example_ridge.yaml), so a first visit can go straight to the orders. */
export const EXAMPLE_ARMIES: { sides: [string, string]; units: UnitDraft[] } = {
  sides: ['Union', 'Confederate'],
  units: [
    { id: 'us_1mn', name: '1st Minnesota', side: 0, type: 'inf', subtype: 'line', size: 900, stats: '6/6/1/0', guns: null },
    { id: 'us_15ma', name: '15th Massachusetts', side: 0, type: 'inf', subtype: 'line', size: 700, stats: '5/5/1/0', guns: null },
    { id: 'us_bat', name: 'Battery B', side: 0, type: 'art', subtype: 'battery', size: 72, stats: '5/5/0/0', guns: 8 },
    { id: 'cs_8al', name: '8th Alabama', side: 1, type: 'inf', subtype: 'line', size: 1000, stats: '5/6/0/0', guns: null },
    { id: 'cs_10al', name: '10th Alabama', side: 1, type: 'inf', subtype: 'line', size: 800, stats: '4/5/0/0', guns: null },
    { id: 'cs_11al', name: '11th Alabama', side: 1, type: 'inf', subtype: 'line', size: 600, stats: '3/4/0/0', guns: null },
    { id: 'cs_bat', name: "Ross's Battery", side: 1, type: 'art', subtype: 'battery', size: 72, stats: '5/5/0/0', guns: 8 },
  ],
};

const wholeAtLeast = (n: number | null, min: number): n is number => Number.isInteger(n) && (n as number) >= min;

function buildRegiment(u: UnitDraft): Regiment {
  if (u.type === 'inf') return new InfantryRegiment(u.size, u.stats, u.subtype!);
  if (u.type === 'cav') return new CavalryRegiment(u.size, u.stats, u.subtype!);
  if (u.type === 'art') return new ArtilleryBattery(u.size, u.stats, u.guns!, u.subtype!);
  return new Regiment(u.size, u.stats);
}

export function createStore(seed: number = Math.floor(Math.random() * 2 ** 32)) {
  const units = signal<UnitDraft[]>(structuredClone(EXAMPLE_ARMIES.units));
  const sides = signal<[string, string]>([...EXAMPLE_ARMIES.sides]);
  const seedSignal = signal(seed);
  const battle = signal<Battle | null>(null);
  const revision = signal(0);

  const orderOfBattleView = computed(() => {
    revision.value;
    return battle.value === null ? null : orderOfBattle(battle.value.toDict());
  });

  const touch = () => {
    revision.value += 1;
  };

  function addUnit(side: 0 | 1): void {
    const used = new Set(units.value.map((u) => u.id));
    let n = 1;
    while (used.has(`u${n}`)) n += 1;
    units.value = [...units.value, {
      id: `u${n}`, name: `Unit ${n}`, side, type: 'inf', subtype: 'line', size: 500, stats: '5/5/0/0', guns: null,
    }];
  }

  function updateUnit(id: string, change: Partial<UnitDraft>): void {
    units.value = units.value.map((u) => {
      if (u.id !== id) return u;
      const next = { ...u, ...change };
      if (change.type !== undefined && change.type !== u.type) {
        // a new type: its usual subtype (unless one was given), and a standard battery for artillery
        if (change.subtype === undefined) next.subtype = change.type === null ? null : DEFAULT_SUBTYPE[change.type];
        if (change.type === 'art') Object.assign(next, STANDARD_BATTERY, change);
        else next.guns = null;
      }
      return next;
    });
  }

  function removeUnit(id: string): void {
    units.value = units.value.filter((u) => u.id !== id);
  }

  function clearUnits(): void {
    units.value = [];
  }

  function renameSide(side: 0 | 1, name: string): void {
    const next: [string, string] = [...sides.value];
    next[side] = name;
    sides.value = next;
  }

  function newSeed(random: () => number = Math.random): void {
    seedSignal.value = Math.floor(random() * 2 ** 32);
  }

  /** Build the battle from the drafts; returns the problems found (none: the battle has started). */
  function start(): string[] {
    const problems: string[] = [];
    const specs: Record<string, UnitSpec> = {};
    for (const u of units.value) {
      if (!wholeAtLeast(u.size, 1)) {
        problems.push(`${u.name}: men must be a whole number, 1 or more.`);
        continue;
      }
      if (u.type === 'art' && !wholeAtLeast(u.guns, 0)) {
        problems.push(`${u.name}: guns must be a whole number, 0 or more.`);
        continue;
      }
      try {
        specs[u.id] = { side: u.side, regiment: buildRegiment(u), name: u.name };
      } catch (error) {
        problems.push(`${u.name}: ${(error as Error).message}`);
      }
    }
    for (const side of [0, 1] as const) {
      if (!units.value.some((u) => u.side === side)) problems.push(`${sides.value[side]} has no units.`);
    }
    const s = seedSignal.value;
    if (!(Number.isInteger(s) && s >= 0 && s < 2 ** 32)) {
      problems.push(`The seed must be a whole number from 0 to ${2 ** 32 - 1}.`);
    }
    if (problems.length) return problems;
    battle.value = new Battle(specs, new Rng(seedSignal.value), undefined, { sides: [...sides.value] });
    touch();
    return [];
  }

  /** Back to editing the armies (the battle is dropped). */
  function reset(): void {
    battle.value = null;
    touch();
  }

  return {
    units, sides, seed: seedSignal, battle, revision, orderOfBattle: orderOfBattleView,
    addUnit, updateUnit, removeUnit, clearUnits, renameSide, newSeed, start, reset, touch,
  };
}

export type Store = ReturnType<typeof createStore>;
