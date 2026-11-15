/**
 * Reconnaissance: everything known of both armies, found by name, brigade or division, and grouped by org. A player
 * sees their own regiments, the enemy's in sight now, and those lost from sight where they were last seen; the
 * admin sees every regiment of each side. A row clicked selects the regiment and brings it to the middle of the map.
 */

import { useState } from 'preact/hooks';

import { type BattleUnit, roughly } from '../engine';
import { groupByOrg, unitsIn } from './bigBattle';
import { unitState } from './dispatch';
import { clockText } from './format';
import type { Store } from './store';

type Filter = 'ours' | 'insight' | 'lost' | 'side0' | 'side1';

const count = (n: number) => n.toLocaleString('en-US');

export function Recon({ store }: { store: Store }) {
  store.revision.value; // rounds fought, units seen or lost
  const b = store.battle.value!;
  const fog = store.fogSide.value;
  const [search, setSearch] = useState('');
  const [picked, setPicked] = useState<Filter | null>(null);
  const known = [...b.units.values()];
  const own = (u: BattleUnit) => fog === null || u.side !== fog;
  const lost = (u: BattleUnit) => !own(u) && store.lastSeenRound(u.uid) !== null;
  const inSight = (u: BattleUnit) => !own(u) && store.seenNow(u.uid) && !lost(u);
  const chips: [Filter, string, (u: BattleUnit) => boolean][] = fog === null
    ? [['side0', store.sides.value[0], (u) => u.side === 0], ['side1', store.sides.value[1], (u) => u.side === 1]]
    : [['ours', 'Ours', own], ['insight', 'In sight', inSight], ['lost', 'Lost from sight', lost]];
  const filter = picked ?? (fog === null ? 'side0' : 'insight');
  const keep = chips.find(([key]) => key === filter)![2];
  const words = search.trim().toLowerCase();
  const matches = (u: BattleUnit) => words === ''
    || [u.name, u.org.brigade, u.org.division, u.org.corps].some((t) => t?.toLowerCase().includes(words));
  const rows = known.filter((u) => keep(u) && matches(u));
  const clock = clockText(b.plan.start_clock, b.time) ?? `minute ${Math.round(b.time)}`;

  const state = (u: BattleUnit): string => {
    if (u.size === 0) return 'wiped out';
    if (!own(u)) {
      const last = store.lastSeenRound(u.uid);
      if (last !== null) return `? last seen round ${last}${u.morale.broken ? ', broken' : ''}`;
      return `in sight, ${u.morale.broken ? 'broken' : 'standing'}`;
    }
    if (u.morale.broken) return 'broken';
    return `${unitState(u.size, false, u.morale.resolve)} · ${Math.round(u.morale.resolve * 100)}%`;
  };
  const find = (u: BattleUnit) => {
    store.selectUnit(u.uid);
    // every regiment listed is on the map: ours, in sight, or where it was last seen
    store.centreMap(store.mapUnits.value.find((m) => m.uid === u.uid)!);
  };

  return (
    <div class="recon">
      <p class="note">All you know of both armies, as of {clock}.</p>
      <label class="recon-search">Search
        <input type="search" placeholder="Regiment, brigade or division" value={search}
          onInput={(e) => setSearch(e.currentTarget.value)} />
      </label>
      <div role="group" aria-label="Show" class="chips">
        {chips.map(([key, label, test]) => (
          <button aria-pressed={key === filter} class={key === filter ? 'active' : ''} onClick={() => setPicked(key)}>
            {label} · {known.filter(test).length}
          </button>
        ))}
      </div>
      {rows.length === 0 ? <p class="note">None to show.</p> : (
        <table aria-label="Reconnaissance">
          <thead><tr><th>Regiment</th><th class="num">Men</th><th>Seen</th></tr></thead>
          <tbody>
            {groupByOrg(rows, (u) => u.org).flatMap((corps) => corps.groups.flatMap((division) => division.groups
              .map((brigade) => [division.name, brigade.name, unitsIn(brigade)] as const)))
              .map(([division, brigade, units]) => (
                <>
                  <tr class="recon-group"><td colSpan={3}>{division} · {brigade}</td></tr>
                  {units.map((u) => (
                    <tr class={`side-${u.side}${u.morale.broken || u.size === 0 ? ' down' : ''}`}>
                      <td><button class="link" onClick={() => find(u)}>{u.name}</button></td>
                      <td class="num">{own(u) ? count(u.size) : `~${count(roughly(u.size))}`}</td>
                      <td>{state(u)}</td>
                    </tr>
                  ))}
                </>
              ))}
          </tbody>
        </table>
      )}
      <p class="note">Click a regiment to find it on the map.</p>
    </div>
  );
}
