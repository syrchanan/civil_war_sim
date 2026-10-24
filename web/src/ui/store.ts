/**
 * The client's state, as signals: like ObservableJS cells, anything that reads a signal (a component, or a
 * `computed`) updates when the signal changes.
 *
 * The engine's Battle mutates in place as rounds are fought, so `revision` is bumped after every change to it,
 * and everything derived from the battle reads it.
 */

import { computed, signal } from '@preact/signals';

import {
  ArtilleryBattery, Battle, type BattleUnit, CavalryRegiment, type Engagement, type FieldHolder, InfantryRegiment, ON_BREAK, type Order,
  orderOfBattle, Regiment, Rng, type RoundReport, sideSummary, type SideSummary, type UnitSpec,
} from '../engine';
import { blockSize, clampToField, defaultLayout, type Point } from './field';

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

/** A unit as drawn on the map: where it stands (yards), how big its block is, and how it fares. */
export interface MapUnit {
  uid: string;
  name: string;
  side: 0 | 1;
  type: string | null;
  men: number;
  x: number;
  y: number;
  width: number;
  depth: number;
  broken: boolean;
  wiped: boolean;
}

export interface OrderArrow {
  from: string;
  to: string;
  mode: string;
  side: number;
}

const finite = (n: number | null): number => (Number.isFinite(n) ? (n as number) : 0);
const onOpenGround = (p: Point) => ({ x: p.x, y: p.y, z: 0, cover: 0, terrain_type: 'open' });

const IDLE: Order = { mode: 'idle', target: null, ammo: null, on_break: null };

export function createStore(seed: number = Math.floor(Math.random() * 2 ** 32)) {
  const units = signal<UnitDraft[]>(structuredClone(EXAMPLE_ARMIES.units));
  const sides = signal<[string, string]>([...EXAMPLE_ARMIES.sides]);
  const seedSignal = signal(seed);
  const battle = signal<Battle | null>(null);
  const revision = signal(0);
  const orders = signal<Record<string, Order>>({});
  const duration = signal(60);
  const recordEvents = signal(false);

  const history = computed<RoundReport[]>(() => {
    revision.value;
    return battle.value === null ? [] : [...battle.value.history];
  });

  /** Each side's performance, once the battle is finished. */
  const summary = computed<SideSummary[] | null>(() => {
    revision.value;
    return battle.value?.finished ? sideSummary(battle.value.toDict()) : null;
  });

  /** Units that can still be given orders. */
  const actingUnits = computed<BattleUnit[]>(() => {
    revision.value;
    return battle.value === null ? [] : [...battle.value.units.values()].filter((u) => u.active);
  });

  /** The engagements these orders would create now, with no dice rolled; or why the orders can't be carried out. */
  const preview = computed<{ arrows: Engagement[]; error: string | null }>(() => {
    revision.value;
    if (battle.value === null) return { arrows: [], error: null };
    try {
      return { arrows: battle.value.engagements(orders.value), error: null };
    } catch (error) {
      return { arrows: [], error: (error as Error).message };
    }
  });

  const orderOfBattleView = computed(() => {
    revision.value;
    return battle.value === null ? null : orderOfBattle(battle.value.toDict());
  });

  const positions = signal<Record<string, Point>>({}); // places given before the battle starts

  /** Every unit on the map; any without a place yet stands where the default layout puts it. */
  const mapUnits = computed<MapUnit[]>(() => {
    revision.value;
    const b = battle.value;
    const shown = b === null
      ? units.value.map((u) => ({
        uid: u.id, name: u.name, side: u.side, type: u.type, men: finite(u.size), front: finite(u.size),
        guns: u.guns === null ? null : finite(u.guns), broken: false, wiped: false, place: positions.value[u.id],
      }))
      : [...b.units.values()].map((u) => ({
        uid: u.uid, name: u.name, side: u.side as 0 | 1, type: u.regiment.unitType, men: u.size, front: u.front,
        guns: u.regiment instanceof ArtilleryBattery ? u.regiment.guns : null, broken: u.morale.broken,
        wiped: u.size === 0, place: u.regiment.position ?? undefined,
      }));
    const sized = shown.map((u) => ({ ...u, ...blockSize(u.type, u.men, u.front, u.guns) }));
    const layout = defaultLayout(sized.map((u) => ({ id: u.uid, side: u.side, width: u.width })));
    return sized.map(({ front: _front, guns: _guns, place, ...u }) => {
      const { x, y } = place ?? layout[u.uid];
      return { ...u, x, y };
    });
  });

  /** The current fire and charge orders, as arrows on the map. */
  const orderArrows = computed<OrderArrow[]>(() => {
    revision.value;
    if (battle.value === null || battle.value.finished) return [];
    return actingUnits.value
      .filter((u) => orders.value[u.uid].mode !== 'idle')
      .map((u) => ({ from: u.uid, to: orders.value[u.uid].target!, mode: orders.value[u.uid].mode, side: u.side }));
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

  /** Enemy units a unit can target: any not wiped out (broken ones can still be fired on or pursued). */
  function targetsFor(uid: string): BattleUnit[] {
    const units = [...battle.value!.units.values()];
    const side = battle.value!.units.get(uid)!.side;
    return units.filter((u) => u.side !== side && u.size > 0);
  }

  /** Change one unit's order; a new mode gets a target, its default on-break choice, and ammo for batteries. */
  function setOrder(uid: string, change: Partial<Order>): void {
    const current = orders.value[uid];
    let next: Order = { ...current, ...change };
    if (change.mode !== undefined && change.mode !== current.mode) {
      if (change.mode === 'idle') {
        next = IDLE;
      } else {
        const battery = battle.value!.units.get(uid)!.regiment instanceof ArtilleryBattery;
        next = {
          mode: change.mode,
          target: change.target ?? current.target ?? targetsFor(uid)[0].uid,
          ammo: change.mode === 'ranged' && battery ? battle.value!.params.combat.artillery_default_ammo : null,
          on_break: change.on_break ?? ON_BREAK[change.mode][0],
        };
      }
    }
    orders.value = { ...orders.value, [uid]: next };
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
    for (const u of mapUnits.value) specs[u.uid].regiment.position = onOpenGround(u);
    battle.value = new Battle(specs, new Rng(seedSignal.value), undefined, { sides: [...sides.value] });
    orders.value = Object.fromEntries([...battle.value.units.keys()].map((uid) => [uid, IDLE]));
    touch();
    return [];
  }

  /**
   * Fight the next round with the current orders; returns why it couldn't be fought, or null. Orders carry into
   * the next round, except those that can no longer be carried out (the unit broke or was wiped out, or its
   * target was wiped out).
   */
  function resolve(): string | null {
    if (!(duration.value > 0)) return 'The round length must be more than 0 minutes.';
    const b = battle.value!;
    try {
      b.resolveRound(duration.value, orders.value, recordEvents.value);
    } catch (error) {
      return (error as Error).message;
    }
    orders.value = Object.fromEntries(Object.entries(orders.value).map(([uid, o]) => {
      const keep = o.mode !== 'idle' && b.units.get(uid)!.active && b.units.get(o.target!)!.size > 0;
      return [uid, keep ? o : IDLE];
    }));
    touch();
    return null;
  }

  /** The battle state file to download: everything needed to resume it, or replay it in Python. */
  function download(): { name: string; text: string } {
    const b = battle.value!;
    const when = b.finished ? 'finished' : `round-${b.round}`;
    return { name: `battle-${b.seed}-${when}.json`, text: b.toJson(2) };
  }

  /** Open a saved battle (from this client or the Python engine); returns what is wrong with it, or null. */
  function open(text: string): string | null {
    let b: Battle;
    try {
      b = Battle.fromJson(text);
    } catch (error) {
      return error instanceof SyntaxError ? `This file is not valid JSON: ${error.message}` : (error as Error).message;
    }
    const data = b.toDict();
    const named = b.meta.sides;
    sides.value = Array.isArray(named) && named.length === 2 ? [String(named[0]), String(named[1])] : ['Side 0', 'Side 1'];
    if (b.seed !== null) seedSignal.value = b.seed;
    units.value = data.units.map((u) => ({
      id: u.id, name: u.name, side: u.side as 0 | 1, type: u.type as UnitType | null, subtype: u.subtype,
      size: u.initial_size, stats: u.initial_stats, guns: u.guns === undefined ? null : u.guns + u.guns_lost,
    }));
    battle.value = b;
    orders.value = Object.fromEntries([...b.units.keys()].map((uid) => [uid, IDLE]));
    touch();
    return null;
  }

  /** Move a unit on the map (kept on the field): before the battle, or between rounds; not once it is over. */
  function moveUnit(uid: string, point: Point): void {
    const place = clampToField(point);
    const b = battle.value;
    if (b === null) {
      positions.value = { ...positions.value, [uid]: place };
    } else if (!b.finished) {
      b.units.get(uid)!.regiment.position = onOpenGround(place);
      touch();
    }
  }

  /** End the battle: settle killed, wounded and prisoners; `holder` 'auto' lets the engine decide the field. */
  function finish(holder: FieldHolder): void {
    battle.value!.finish(holder);
    touch();
  }

  /** Back to editing the armies (the battle is dropped). */
  function reset(): void {
    battle.value = null;
    touch();
  }

  return {
    units, sides, seed: seedSignal, battle, revision, orderOfBattle: orderOfBattleView,
    orders, duration, recordEvents, actingUnits, preview, history, resolve, summary, finish, download, open,
    mapUnits, orderArrows, moveUnit,
    addUnit, updateUnit, removeUnit, clearUnits, renameSide, newSeed, start, reset, touch, targetsFor, setOrder,
  };
}

export type Store = ReturnType<typeof createStore>;
