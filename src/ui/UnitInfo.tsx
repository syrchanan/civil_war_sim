/**
 * The selected unit at a glance, under the map: its pixel-art vignette, what it is, and only what matters for the
 * next order: men, quality, how it stands, what it is doing and where. A foe (the enemy, for a player in battle)
 * shows only what could be seen across the field: men roughly, broken or not, no stats. When replaying a round, as
 * that round began.
 */

import defaults from '../engine/defaults.json';
import { ArtilleryBattery, type Order, parseStats } from '../engine';
import { rangeText } from './format';
import type { Store } from './store';
import { Vignette } from './Vignette';

const ARMS: Record<string, string> = { inf: 'infantry', cav: 'cavalry' };
const invert = (names: Record<string, string | number>) => Object.fromEntries(Object.entries(names)
  .map(([word, code]) => [String(code), word]));
const ACTIONS: Record<string, string> = { ...invert(defaults.names.actions), rally: 'rally' };
const AMMO = invert(defaults.names.ammo);
const GROUNDS: Record<string, string> = { open: 'open ground', forest: 'woods', rough: 'rough ground' };

export const STATS_LABEL = 'Exp / Mor / Wpn / Melee';

const cap = (s: string) => s[0].toUpperCase() + s.slice(1);
const men = (n: number) => n.toLocaleString('en-US');

/** The order the map shows for a unit: as given for the round being replayed, else the current (effective) one. */
function orderOf(store: Store, uid: string): Order | null {
  const b = store.battle.value;
  if (b === null) return null;
  const n = store.mapRound.value;
  if (n !== null) return b.history[n - 1].orders[uid] ?? null;
  return b.finished ? null : store.effectiveOrders.value[uid];
}

export interface UnitInfoView {
  name: string;
  kind: string; // 'Line infantry, Union'
  rows: [string, string][];
}

/** The selected unit's details as label / value rows; null when nothing is selected. */
export function unitInfoOf(store: Store): UnitInfoView | null {
  const uid = store.focusedUnit.value;
  const all = store.mapUnits.value;
  const unit = all.find((u) => u.uid === uid);
  if (unit === undefined) return null;
  const b = store.battle.value;
  const live = b?.units.get(unit.uid);
  const draft = store.units.value.find((u) => u.id === unit.uid);
  const foe = store.fogSide.value === unit.side;
  const rows: [string, string][] = [];

  // every unit of a known kind has a subtype; a plain regiment (no kind) has neither
  const subtype = live !== undefined ? live.regiment.subtype : draft!.subtype;
  const guns = live !== undefined ? (live.regiment instanceof ArtilleryBattery ? live.regiment.guns : null)
    : draft!.guns;
  let kind = unit.type === null ? 'Unknown kind' : unit.type === 'art' ? cap(subtype!) : `${cap(subtype!)} ${ARMS[unit.type]}`;
  if (guns !== null && !foe) kind += `, ${guns} gun${guns === 1 ? '' : 's'}`;

  rows.push(['Men', foe ? `~${men(unit.men)}`
    : live !== undefined ? `${men(unit.men)} of ${men(live.initialSize)}` : men(unit.men)]);

  if (!foe) {
    let stats: readonly number[] | null;
    try {
      stats = live !== undefined ? live.regiment.stats : parseStats(draft!.stats);
    } catch {
      stats = null;
    }
    // the stats as players write them, experience/morale/weapon/melee only
    rows.push([STATS_LABEL, stats === null ? 'not valid' : stats.join('/')]);
  }

  if (unit.lastSeen !== null) {
    // out of sight: how it stood when last seen, and nothing it does now
    rows.push(['Status', `Out of sight; last seen as round ${unit.lastSeen} began${unit.broken ? ', broken' : ''}`]);
    return { name: unit.name, kind: `${kind}, ${store.sides.value[unit.side]}`, rows };
  }

  if (live !== undefined) {
    const steady = foe ? 'steady' : `steady, ${Math.round(live.morale.resolve * 100)}% morale left`;
    const state = unit.wiped ? 'wiped out' : unit.broken ? 'broken' : live.rallied && !foe ? `rallied, ${steady}` : steady;
    rows.push(['Status', cap(state)]);
  }

  const order = orderOf(store, unit.uid);
  if (order !== null) {
    const target = order.target === null ? undefined : all.find((u) => u.uid === order.target);
    let text = cap(ACTIONS[order.mode]);
    if (order.ammo !== null && !foe) text += ` (${AMMO[order.ammo]})`;
    if (target !== undefined) {
      const range = store.mapRound.value === null ? store.rangeOf(unit.uid) : null;
      const how = range !== null ? rangeText(range) : `${Math.round(Math.hypot(target.x - unit.x, target.y - unit.y))} yd`;
      text += ` ${order.mode === 'ranged' ? 'on ' : ''}${target.name}, ${how}`;
    }
    // a foe's order is what the player expects of it
    rows.push([foe ? 'Expected' : 'Order', text]);
  }

  const terrain = store.terrain.value;
  if (terrain !== null) {
    const height = Math.round(terrain.heightAt(unit.x, unit.y));
    // heights are above the field's lowest ground, so 0 says nothing
    rows.push(['Ground', cap(`${GROUNDS[terrain.groundAt(unit.x, unit.y)]}${height > 0 ? `, ${height} yd up` : ''}`)]);
  }
  return { name: unit.name, kind: `${kind}, ${store.sides.value[unit.side]}`, rows };
}

export function UnitInfo({ store }: { store: Store }) {
  const info = unitInfoOf(store);
  if (info === null) return null;
  return (
    <section class="unit-info" aria-label={`${info.name}: details`}>
      <Vignette store={store} />
      <div class="unit-details">
        <h3>{info.name}</h3>
        <p class="unit-kind">{info.kind}</p>
        <dl>
          {info.rows.map(([label, value]) => (
            <div><dt>{label}</dt><dd>{value}</dd></div>
          ))}
        </dl>
      </div>
    </section>
  );
}
