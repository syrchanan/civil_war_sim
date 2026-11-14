/**
 * A brigade or division selected on the map: its regiments and men, and, for the viewer's own while a round is
 * being ordered, one order for all of it: fire on or charge an enemy brigade (each regiment at the nearest of its
 * regiments it can reach), or hold. Each regiment can still be ordered on its own; the card counts those changed.
 */

import { useState } from 'preact/hooks';

import { roughly } from '../engine';
import { type GroupRef, groupKey, groupName, type Store } from './store';

const count = (n: number) => n.toLocaleString('en-US');
const MODES: ['ranged' | 'melee' | 'idle', string][] = [['ranged', 'Fire'], ['melee', 'Charge'], ['idle', 'Hold']];

export function GroupCard({ store, group }: { store: Store; group: GroupRef }) {
  store.revision.value; // rounds fought, regiments broken
  const [result, setResult] = useState<{ key: string; mode: string; reached: number; of: number } | null>(null);
  const b = store.battle.value!;
  const foe = store.fogSide.value === group.side;
  // the enemy only as far as known
  const units = store.unitsOfGroup(group)
    .filter((u) => !foe || store.seenNow(u.uid) || store.lastSeenRound(u.uid) !== null);
  const men = units.reduce((sum, u) => sum + u.size, 0);
  const started = units.reduce((sum, u) => sum + u.initialSize, 0);
  const standing = units.filter((u) => u.active).length;
  const ordering = !foe && !b.finished && b.plan.phase === 'battle' && store.mapRound.value === null
    && (store.mode.value === 'admin' || group.side === store.playerSide.value);
  const targets = ordering ? store.enemyBrigades(group) : [];
  const [target, setTarget] = useState<string | null>(null);
  const aim = targets.find((t) => groupKey(t) === target) ?? targets[0] ?? null;
  const key = groupKey(group);
  const changed = ordering ? store.changedByHand(group) : 0;
  const give = (mode: 'ranged' | 'melee' | 'idle') => {
    const r = store.orderGroup(group, mode, mode === 'idle' ? null : aim);
    setResult({ key, mode, ...r });
  };
  const shown = result !== null && result.key === key ? result : null;
  return (
    <section class="group-card" aria-label={groupName(group)}>
      <h3>{groupName(group)}</h3>
      <p class="note">
        {group.level === 'brigade' ? `${group.division} · ` : ''}{units.length} regiment{units.length === 1 ? '' : 's'}
        {' · '}{foe ? `~${count(roughly(men))} men` : `${count(men)} of ${count(started)} men, ${standing} standing`}
      </p>
      {ordering && (targets.length === 0 ? <p class="note">No enemy brigade in sight to order against.</p> : (
        <>
          <label>Against
            <select aria-label="Against" value={groupKey(aim!)}
              onChange={(e) => setTarget(e.currentTarget.value)}>
              {targets.map((t) => <option value={groupKey(t)}>{t.brigade} ({t.division})</option>)}
            </select>
          </label>
          <div class="segmented" role="group" aria-label={`Order ${groupName(group)}`}>
            {MODES.map(([mode, word]) => <button onClick={() => give(mode)}>{word}</button>)}
          </div>
        </>
      ))}
      {shown !== null && (
        <p class="note" role="status">
          {shown.mode === 'idle' ? `All ${shown.of} holding.`
            : `${shown.reached} of ${shown.of} ${shown.mode === 'ranged' ? 'in range' : 'charging'}; the rest hold.`}
        </p>
      )}
      {changed > 0 && <p class="note">{changed} changed by hand since.</p>}
      <ul class="roster-units">
        {units.map((u) => (
          <li><button class="link" onClick={() => store.selectUnit(u.uid)}>{u.name}</button></li>
        ))}
      </ul>
    </section>
  );
}
