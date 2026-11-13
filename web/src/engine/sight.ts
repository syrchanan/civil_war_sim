/**
 * Line of sight between two points on the terrain, and which enemy units one side can see: now, and as each round
 * began. A player file keeps only what its side has seen (playerFile.ts); the client hides the rest.
 */

import { BattleParams, type SightData } from './params';
import type { StateData } from './state';
import { Terrain } from './terrain';

interface Point {
  x: number;
  y: number;
}

/**
 * Can an eye at `p` (a unit of type `typeA`) see one at `q` (type `typeB`): no ground or woods rise above the line
 * between them. The first and last `edge_clear` yards aren't checked, so a unit at a wood's edge sees out.
 */
export function sightBetween(t: Terrain, sp: Readonly<SightData>, p: Point, typeA: string, q: Point, typeB: string): boolean {
  const dx = p.x - q.x;
  const dy = p.y - q.y;
  const d = Math.sqrt(dx * dx + dy * dy);
  const za = t.heightAt(p.x, p.y) + sp.eye_height[typeA];
  const zb = t.heightAt(q.x, q.y) + sp.eye_height[typeB];
  const steps = Math.floor(d / sp.sample_step);
  for (let k = 1; k <= steps; k++) {
    const s = k * sp.sample_step;
    if (s < sp.edge_clear || d - s < sp.edge_clear) continue;
    const f = s / d;
    const x = p.x + (q.x - p.x) * f;
    const y = p.y + (q.y - p.y) * f;
    let ground = t.heightAt(x, y);
    if (t.groundAt(x, y) === 'forest') ground = ground + sp.forest_height;
    if (ground > za + (zb - za) * f) return false;
  }
  return true;
}

/** When one enemy unit was seen: at which moments (round n's start is n; now is the round after the last). */
export interface Sighting {
  now: boolean;
  seen: Set<number>;
  last: number | null; // the latest moment it was seen; null: never
}

/**
 * Which of the enemy's units `side` can see, at the start of each round fought (from the saved positions) and now.
 * A viewer is any unit of `side` not wiped out at that moment. An unplaced unit, on either side, is seen and sees
 * everything, and without terrain everything is seen, as for fire (Battle.lineOfSight).
 */
export function sightings(state: StateData, side: number): Map<string, Sighting> {
  const terrain = state.terrain === null ? null : new Terrain(state.terrain);
  const sp = BattleParams.fromDict(state.params as never).sight;
  const kind = new Map(state.units.map((u) => [u.id, u.type ?? 'inf']));
  const now = state.history.length + 1;
  const moments: { n: number; at: (uid: string) => Point | null; standing: (uid: string) => boolean }[] = [];
  state.history.forEach((r, i) => {
    const before = i === 0 ? null : state.history[i - 1];
    moments.push({
      n: r.round,
      at: (uid) => r.positions[uid] ?? null,
      standing: (uid) => before === null || before.units[uid].size > 0,
    });
  });
  const current = new Map(state.units.map((u) => [u.id, u]));
  moments.push({ n: now, at: (uid) => current.get(uid)!.position, standing: (uid) => current.get(uid)!.size > 0 });

  const own = state.units.filter((u) => u.side === side).map((u) => u.id);
  const result = new Map<string, Sighting>();
  for (const enemy of state.units.filter((u) => u.side !== side)) {
    const seen = new Set<number>();
    for (const m of moments) {
      const q = m.at(enemy.id);
      const visible = terrain === null || q === null || own.some((uid) => {
        if (!m.standing(uid)) return false;
        const p = m.at(uid);
        return p === null || sightBetween(terrain, sp, p, kind.get(uid)!, q, kind.get(enemy.id)!);
      });
      if (visible) seen.add(m.n);
    }
    result.set(enemy.id, { now: seen.has(now), seen, last: seen.size === 0 ? null : Math.max(...seen) });
  }
  return result;
}
