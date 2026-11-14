/**
 * Each side's regiments as its order of battle reads: corps › division › brigade, each group with its regiments and
 * men, folding open to its regiments and how they stand. The enemy as far as it is known: in the fog of war, only
 * the regiments seen (or last seen), their men roughly, and no state but broken.
 */

import { type BattleUnit, roughly } from '../engine';
import { groupByOrg, type OrgGroup, unitsIn } from './bigBattle';
import { unitState } from './dispatch';
import type { Store } from './store';

const count = (n: number) => n.toLocaleString('en-US');

function Group({ store, group, foe }: { store: Store; group: OrgGroup<BattleUnit>; foe: boolean }) {
  const units = unitsIn(group);
  const men = units.reduce((sum, u) => sum + u.size, 0);
  const started = units.reduce((sum, u) => sum + u.initialSize, 0);
  const strength = foe ? `~${count(roughly(men))} men` : `${count(men)} of ${count(started)} men`;
  return (
    <details class={`roster-group ${group.level}`} open={group.level !== 'brigade'}>
      <summary>
        <span class="roster-name">{group.name}</span>
        <span class="note"> · {units.length} regiment{units.length === 1 ? '' : 's'} · {strength}</span>
      </summary>
      {group.groups.map((g) => <Group store={store} group={g} foe={foe} />)}
      {group.units.length > 0 && (
        <ul class="roster-units">
          {group.units.map((u) => {
            const last = foe ? store.lastSeenRound(u.uid) : null;
            const state = u.size === 0 ? 'wiped out' : u.morale.broken ? 'broken'
              : foe ? (last === null ? 'in sight' : `last seen round ${last}`)
                : `${unitState(u.size, false, u.morale.resolve)} · ${Math.round(u.morale.resolve * 100)}%`;
            return (
              <li>
                <button class="link" onClick={() => store.selectUnit(u.uid)}>{u.name}</button>
                <span class="note"> {foe ? `~${count(roughly(u.size))}` : count(u.size)} men, {state}</span>
              </li>
            );
          })}
        </ul>
      )}
    </details>
  );
}

export function Rosters({ store }: { store: Store }) {
  store.revision.value; // rounds fought, units broken
  const b = store.battle.value!;
  const fog = store.fogSide.value;
  return (
    <div class="rosters">
      {([0, 1] as const).map((side) => {
        const foe = side === fog;
        // the enemy as far as it is known: seen now, or where it was last seen
        const units = [...b.units.values()].filter((u) => u.side === side
          && (!foe || store.seenNow(u.uid) || store.lastSeenRound(u.uid) !== null));
        return (
          <section class={`roster side-${side}`} aria-label={`${store.sides.value[side]} roster`}>
            <h3>{store.sides.value[side]}{foe ? ', as far as you know' : ''}</h3>
            {units.length === 0 ? <p class="note">None seen yet.</p>
              : groupByOrg(units, (u) => u.org).map((g) => <Group store={store} group={g} foe={foe} />)}
          </section>
        );
      })}
    </div>
  );
}
