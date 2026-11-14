/**
 * A little pixel-art picture of the selected unit doing what it has been ordered to: firing, charging, in melee,
 * standing, or running if broken, on the ground it stands on. Just for fun; the map and tables carry the numbers.
 */

import type { Ground } from '../engine';
import { PALETTE, SKY, SKY_WOODS, UNIFORMS } from './sprites/palette';
import { type Figure, type Paint, type Pose, scene } from './sprites/render';
import { HEIGHT, WIDTH } from './sprites/art';
import type { Store } from './store';

export interface VignetteState {
  name: string;
  side: 0 | 1;
  figure: Figure;
  pose: Pose;
  ground: Ground;
}

const DOING: Record<Pose, string> = {
  idle: 'standing', firing: 'firing', charging: 'charging', melee: 'in melee', broken: 'broken, running',
};
const ON: Record<Ground, string> = { open: 'on open ground', forest: 'in the woods', rough: 'on rough ground' };

/** 'Firing, in the woods'. */
export const doing = (v: VignetteState): string => `${DOING[v.pose][0].toUpperCase()}${DOING[v.pose].slice(1)}, ${ON[v.ground]}`;
export const caption = (v: VignetteState): string => `${v.name}: ${DOING[v.pose]}, ${ON[v.ground]}`;

/** What the selected unit is doing, or null when nothing is selected, it is gone, or its kind is hidden. */
export function vignetteOf(store: Store): VignetteState | null {
  const uid = store.focusedUnit.value;
  const unit = store.mapUnits.value.find((u) => u.uid === uid);
  // nothing to picture for a unit out of sight (only where it was last seen is known)
  if (unit === undefined || unit.wiped || unit.type === null || unit.lastSeen !== null) return null;
  const order = store.orderArrows.value.find((a) => a.from === unit.uid);
  const battle = store.battle.value;
  // contact is known only as the battle stands now, not for a round being replayed
  const inContact = (other: string) => battle !== null && store.mapRound.value === null
    && battle.contacts.has(unit.uid < other ? `${unit.uid}\u0000${other}` : `${other}\u0000${unit.uid}`);
  const pose: Pose = unit.broken ? 'broken'
    : order === undefined ? 'idle'
    // fire that can't tell (out of range, outside the front arc, no line of sight) isn't firing: it stands
    : order.mode === 'ranged' ? (order.blocked ? 'idle' : 'firing')
    : inContact(order.to) ? 'melee' : 'charging';
  return {
    name: unit.name,
    side: unit.side,
    figure: unit.type as Figure,
    pose,
    ground: store.terrain.value?.groundAt(unit.x, unit.y) ?? 'open',
  };
}

function Layer({ paints, side }: { paints: Paint[]; side: 0 | 1 }) {
  return <>{paints.map((p) => <path d={p.d} fill={UNIFORMS[side][p.color] ?? PALETTE[p.color]} />)}</>;
}

export function Vignette({ store }: { store: Store }) {
  const v = vignetteOf(store);
  if (v === null) return null;
  const s = scene(v.figure, v.pose, v.ground);
  const text = caption(v);
  return (
    <figure class="vignette">
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={text} shape-rendering="crispEdges">
        <rect width={WIDTH} height={HEIGHT} fill={v.ground === 'forest' ? SKY_WOODS : SKY} />
        <Layer paints={s.back} side={v.side} />
        {s.frames.map((paints, i) => (
          <g class={`frame frames-${s.frames.length}`} style={{ '--i': i }}>
            <Layer paints={paints} side={v.side} />
          </g>
        ))}
        <Layer paints={s.front} side={v.side} />
      </svg>
      <figcaption>{doing(v)}</figcaption>
    </figure>
  );
}
