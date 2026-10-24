/**
 * A player file: the battle as one side sees it, for a player to plan their next orders. The admin makes one per
 * side from the real battle. The player's own units are exact; of the enemy only what could be seen from the
 * field is kept (name, type, where it stands, whether it has broken, its guns, and its men roughly). Their stats
 * are a neutral placeholder, which the player can replace with guesses. The dice state stays with the admin; the
 * real battle's tag goes along, so the player's orders file can be checked against the battle it was made from.
 */

import defaults from './defaults.json';
import { ValueError } from './errors';
import { Rng } from './rng';
import { battleTag, type StateData, type UnitData } from './state';

export const PLAYER_FORMAT = 'imperial-generals-player';
export const PLAYER_VERSION = 1;

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

/** The player file for `side` from the real battle's state; only for a battle still being fought. */
export function playerFile(real: StateData, side: 0 | 1): PlayerFile {
  if (real.finished) throw new ValueError('The battle is over: there are no more orders to give.');
  const enemy = new Set(real.units.filter((u) => u.side !== side).map((u) => u.id));
  const own = (uid: string) => !enemy.has(uid);
  const state: StateData = {
    ...structuredClone(real),
    rng_state: new Rng(0).state, // the dice stay with the admin
    units: real.units.map((u) => (own(u.id) ? structuredClone(u) : enemyUnit(u))),
    history: real.history.map((r) => ({
      ...structuredClone(r),
      units: Object.fromEntries(Object.entries(r.units).map(([uid, u]) => [uid, own(uid) ? { ...u }
        : { ...u, losses: 0, inflicted: 0, captured: 0, morale: 0, size: roughly(u.size) }])),
      engagements: r.engagements.filter((e) => own(e.attacker)),
      events: [],
      charges: r.charges.map((c) => ({ ...c, p_defender_breaks: null, p_falter: null, p_home: null })),
      retargets: r.retargets.filter((t) => own(t.unit)),
      modifiers: Object.fromEntries(Object.entries(r.modifiers).filter(([uid]) => own(uid))),
    })),
  };
  return { format: PLAYER_FORMAT, version: PLAYER_VERSION, side, tag: battleTag(real), state };
}
