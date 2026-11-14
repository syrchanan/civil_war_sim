/**
 * Each side as the battle begins: men by arm, average experience and morale. A side in the fog of war (the enemy,
 * for a player in battle) shows its men roughly ('~2,450') and no averages or guns.
 */

import { roughly, type SideOrder } from '../engine';

const ARMS: [string, string][] = [['inf', 'Infantry'], ['cav', 'Cavalry'], ['art', 'Artillery']];

function arm(side: SideOrder, key: string, about: string): string {
  const k = side.by_type[key];
  if (k === undefined) return '—';
  const guns = k.guns === undefined || about ? '' : `, ${k.guns} guns`;
  return `${about}${(about ? roughly(k.men) : k.men).toLocaleString('en-US')} (${k.units}${guns})`;
}

export function OrderOfBattle({ sides, hidden = null }: { sides: SideOrder[]; hidden?: number | null }) {
  return (
    <div class="table-wrap">
      <table aria-label="Order of battle">
        <thead>
          <tr>
            <th>Side</th><th class="num">Units</th><th class="num">Men</th>
            {ARMS.map(([, label]) => <th class="num">{label}</th>)}
            <th class="num">Avg exp</th><th class="num">Avg morale</th>
          </tr>
        </thead>
        <tbody>
          {sides.map((s, i) => {
            const about = i === hidden ? '~' : '';
            return (
              <tr class={`side-${i}`}>
                <td>{s.name}</td>
                <td class="num">{s.units}</td>
                <td class="num">{about}{(about ? roughly(s.men) : s.men).toLocaleString('en-US')}</td>
                {ARMS.map(([key]) => <td class="num">{arm(s, key, about)}</td>)}
                <td class="num">{about ? '—' : s.avg_experience.toFixed(1)}</td>
                <td class="num">{about ? '—' : s.avg_morale.toFixed(1)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p class="note">Men in brackets: units, and guns for artillery.{hidden !== null && ' The enemy: only the units you have seen.'}</p>
    </div>
  );
}
