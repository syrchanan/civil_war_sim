/**
 * Every round fought so far: its dispatch, and under it the full report (per unit losses, inflicted, men left,
 * morale and breaks; charges, target switches, modifiers, flights and rallies). The dispatch just fought or picked
 * on the round strip comes first, with the way on to the next orders; then the rest, latest first.
 */

import type { RoundReport } from '../engine';
import { DispatchCard } from './DispatchCard';
import { chargeText, flightText, modifierText, rallyText, status } from './format';
import type { Store } from './store';
import { StrengthCharts } from './StrengthCharts';

function Round({ store, report }: { store: Store; report: RoundReport }) {
  const units = store.battle.value!.units;
  const name = (uid: string) => units.get(uid)!.name;
  // a player sees only their own units' figures (fog of war)
  const rows = Object.entries(report.units).filter(([uid]) => units.get(uid)!.side !== store.fogSide.value);
  return (
    <details class="full-report">
      <summary>The full report: Round {report.round} ({report.start.toFixed(0)}–{report.end.toFixed(0)} min)</summary>
      <div class="table-wrap">
        <table aria-label={`Round ${report.round}`}>
          <thead>
            <tr>
              <th>Unit</th><th class="num">Lost</th><th class="num">Taken prisoner</th><th class="num">Inflicted</th>
              <th class="num">Men left</th><th class="num">Morale</th><th>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([uid, u]) => (
              <tr class={`side-${units.get(uid)!.side}`}>
                <td>{name(uid)}</td>
                <td class="num">{u.losses}</td>
                <td class="num">{u.captured}</td>
                <td class="num">{u.inflicted}</td>
                <td class="num">{u.size}</td>
                <td class="num">{u.morale.toFixed(1)}</td>
                <td>{status(u.size, u.broken, u.broke_at, u.guns_lost)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {report.charges.length > 0 && (
        <ul aria-label={`Round ${report.round} charges`}>
          {report.charges.map((c) => <li>{chargeText(c, name)}</li>)}
        </ul>
      )}
      {report.retargets.length > 0 && (
        <ul aria-label={`Round ${report.round} target switches`}>
          {report.retargets.map((r) => (
            <li>{name(r.unit)} switched from {name(r.old_target)} to {name(r.new_target)} at {r.time.toFixed(0)} min</li>
          ))}
        </ul>
      )}
      {Object.keys(report.modifiers).length > 0 && (
        <ul aria-label={`Round ${report.round} modifiers`}>
          {Object.entries(report.modifiers).map(([uid, m]) => <li>{name(uid)}: {modifierText(m)}</li>)}
        </ul>
      )}
      {report.flights.length > 0 && (
        <ul aria-label={`Round ${report.round} flights`}>
          {report.flights.map((f) => <li>{flightText(f, name)}</li>)}
        </ul>
      )}
      {report.rallies.length > 0 && (
        <ul aria-label={`Round ${report.round} rallies`}>
          {report.rallies.map((r) => <li>{rallyText(r, name)}</li>)}
        </ul>
      )}
      {Object.keys(report.side_modifiers).length > 0 && (
        <ul aria-label={`Round ${report.round} side modifiers`}>
          {Object.entries(report.side_modifiers).map(([side, m]) => (
            <li>{store.sides.value[Number(side)]}: {modifierText(m)}</li>
          ))}
        </ul>
      )}
      {report.events.length > 0 && <p class="note">{report.events.length} casualties recorded one by one.</p>}
    </details>
  );
}

export function RoundsPanel({ store }: { store: Store }) {
  const history = store.history.value;
  if (history.length === 0) return <p class="note">No rounds fought yet.</p>;
  const picked = store.dispatchRound.value;
  const rounds = [...history].reverse().sort((a, b) => Number(b.round === picked) - Number(a.round === picked));
  return (
    <div class="rounds">
      <StrengthCharts store={store} />
      {rounds.map((report) => (
        <div class={`dispatch-entry${report.round === picked ? ' picked' : ''}`}>
          <DispatchCard store={store} round={report.round} docked={report.round === picked} />
          <Round store={store} report={report} />
        </div>
      ))}
    </div>
  );
}
