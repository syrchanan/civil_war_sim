/**
 * A player file: the battle as one side sees it, for a player to plan their next orders. The admin makes one per
 * side from the real battle. The player's own units are exact; of the enemy only what could be seen from the
 * field is kept (name, type, where it stands, whether it has broken, its guns, and its men roughly; whether it has
 * rallied, but not its odds). The enemy side's modifiers are left out. Their stats
 * are a neutral placeholder, which the player can replace with guesses.
 *
 * Version 2, fog of war on the terrain (sight.ts): an enemy unit the side has never seen, at any round's start or
 * now, isn't in the file at all. One seen before but not now stands where it was last seen, with its men and
 * whether it was broken as seen then, marked `meta.last_seen` (that round). History keeps an enemy unit's place
 * and orders only for rounds it was seen at the start of. Version 1 files (no fog) still open. The dice state stays with the admin; the
 * real battle's tag goes along, so the player's orders file can be checked against the battle it was made from.
 */

import defaults from './defaults.json';
import { ValueError } from './errors';
import { Rng } from './rng';
import { sightings } from './sight';
import type { UnitReport } from './battle';
import { battleTag, type StateData, type UnitData } from './state';

export const PLAYER_FORMAT = 'imperial-generals-player';
export const PLAYER_VERSION = 2;

/** The stats shown for an enemy unit until the player guesses better: average experience and morale. */
export const UNKNOWN_STATS = '5/5/0/0';

export interface PlayerFile {
  format: string;
  version: number;
  side: 0 | 1;
  tag: string; // the real battle's tag (see battleTag)
  state: StateData;
}

/** Men as seen from a distance: to the nearest 10 under 100 (at least 10), else to the nearest 50; none is none. */
export function roughly(men: number): number {
  if (men === 0) return 0;
  if (men < 100) return Math.max(10, Math.round(men / 10) * 10);
  return Math.round(men / 50) * 50;
}

function enemyUnit(u: UnitData): UnitData {
  const broken = u.morale.broken;
  return {
    ...u,
    size: roughly(u.size),
    initial_size: roughly(u.initial_size),
    stats: UNKNOWN_STATS,
    initial_stats: UNKNOWN_STATS,
    front_size: roughly(u.size),
    raw_morale: broken ? 0 : Number(UNKNOWN_STATS.split('/')[1]) * defaults.morale_scale.raw_scale_factor,
    morale: { resolve: broken ? 0 : 1, shock: 0, lost: 0, broken, break_scale: 1 },
    losses: 0,
    inflicted: 0,
    captured: 0,
    meta: {},
  };
}

/** An enemy unit out of sight now: where it was last seen (round `n`'s start), its men and broken as seen then. */
function lastSeen(real: StateData, u: UnitData, n: number): UnitData {
  const before = n === 1 ? null : real.history[n - 2].units[u.id];
  const men = before === null ? u.initial_size : before.size;
  const broken = before === null ? false : before.broken;
  const seen = enemyUnit({ ...u, size: men, morale: { ...u.morale, broken } });
  return {
    ...seen, position: structuredClone(real.history[n - 1].positions[u.id]), combat_mode: 'idle',
    broke_time: broken ? u.broke_time : null, meta: { last_seen: n },
  };
}

/**
 * An enemy unit's round report as its side could know it: how it stood when last seen (the latest of `seen`, a
 * round's start), or as it began the battle if not seen yet.
 */
function frozen(real: StateData, u: UnitReport, uid: string, seen: number[]): UnitReport {
  const n = seen.length === 0 ? 1 : Math.max(...seen);
  const before = n === 1 ? null : real.history[n - 2].units[uid];
  if (before === null) {
    return { ...u, size: real.units.find((x) => x.id === uid)!.initial_size, broken: false, broke_at: null, guns_lost: 0 };
  }
  return { ...u, size: before.size, broken: before.broken, broke_at: null, guns_lost: 0 };
}

/** The player file for `side` from the real battle's state; only for a battle still being fought. */
export function playerFile(real: StateData, side: 0 | 1): PlayerFile {
  if (real.finished) throw new ValueError('The battle is over: there are no more orders to give.');
  const enemy = new Set(real.units.filter((u) => u.side !== side).map((u) => u.id));
  const own = (uid: string) => !enemy.has(uid);
  const sight = sightings(real, side);
  const never = (uid: string) => enemy.has(uid) && sight.get(uid)!.last === null;
  const known = (uid: string) => !never(uid);
  // an enemy unit's place and orders in a round only if it was seen as that round began
  const seenAt = (uid: string, n: number) => own(uid) || sight.get(uid)!.seen.has(n);
  const keep = <T>(rec: Record<string, T>, n: number) => Object.fromEntries(Object.entries(rec)
    .filter(([uid]) => seenAt(uid, n)));
  const enemyOf = (u: UnitData): UnitData => {
    const s = sight.get(u.id)!;
    return s.now ? enemyUnit(u) : lastSeen(real, u, s.last!);
  };
  // the other side's whole-battle modifiers (its commander, supply) are its own business
  const ownSide = <T>(bySide: Record<string, T>) => Object.fromEntries(Object.entries(bySide)
    .filter(([s]) => s === String(side)).map(([s, m]) => [s, structuredClone(m)]));
  const state: StateData = {
    ...structuredClone(real),
    rng_state: new Rng(0).state, // the dice stay with the admin
    side_modifiers: ownSide(real.side_modifiers),
    units: real.units.filter((u) => known(u.id)).map((u) => (own(u.id) ? structuredClone(u) : enemyOf(u))),
    contacts: real.contacts.filter((pair) => pair.every((uid) => own(uid) || sight.get(uid)!.now))
      .map((pair) => [...pair]),
    history: real.history.map((r) => ({
      ...structuredClone(r),
      orders: keep(structuredClone(r.orders), r.round),
      positions: keep(structuredClone(r.positions), r.round),
      // how a unit ended the round shows only if it was seen as the next began; else as last seen
      units: Object.fromEntries(Object.entries(r.units).filter(([uid]) => known(uid)).map(([uid, u]) => {
        if (own(uid)) return [uid, { ...u }];
        const s = sight.get(uid)!;
        const shown = s.seen.has(r.round + 1) ? u : frozen(real, u, uid, [...s.seen].filter((n) => n <= r.round));
        return [uid, { ...shown, losses: 0, inflicted: 0, captured: 0, morale: 0, size: roughly(shown.size) }];
      })),
      engagements: r.engagements.filter((e) => own(e.attacker) && known(e.target)),
      events: [],
      charges: r.charges.filter((c) => known(c.charger) && known(c.target))
        .map((c) => ({ ...c, p_defender_breaks: null, p_falter: null, p_home: null })),
      flights: r.flights.filter((f) => known(f.unit))
        .map((f) => ({ ...f, escaped_from: f.escaped_from.filter(known) })),
      retargets: r.retargets.filter((t) => own(t.unit) && known(t.old_target) && known(t.new_target)),
      modifiers: Object.fromEntries(Object.entries(r.modifiers).filter(([uid]) => own(uid))),
      side_modifiers: ownSide(r.side_modifiers),
      rallies: r.rallies.filter((x) => own(x.unit)),
    })),
  };
  return { format: PLAYER_FORMAT, version: PLAYER_VERSION, side, tag: battleTag(real), state };
}
