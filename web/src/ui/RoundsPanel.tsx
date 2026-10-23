/** Every round fought so far: per unit losses, inflicted, men left, morale and breaks; charges and target switches. */

import type { RoundReport } from '../engine';
import { chargeText, status } from './format';
import type { Store } from './store';
import { StrengthCharts } from './StrengthCharts';

function Round({ store, report, open }: { store: Store; report: RoundReport; open: boolean }) {
  const units = store.battle.value!.units;
  const name = (uid: string) => units.get(uid)!.name;
  return (
    <details open={open}>
      <summary>Round {report.round} ({report.start.toFixed(0)}–{report.end.toFixed(0)} min)</summary>
      <div class="table-wrap">
        <table aria-label={`Round ${report.round}`}>
          <thead>
            <tr>
              <th>Unit</th><th class="num">Lost</th><th class="num">Taken prisoner</th><th class="num">Inflicted</th>
              <th class="num">Men left</th><th class="num">Morale</th><th>Status</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(report.units).map(([uid, u]) => (
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
      {report.events.length > 0 && <p class="note">{report.events.length} casualties recorded one by one.</p>}
    </details>
  );
}

export function RoundsPanel({ store }: { store: Store }) {
  const history = store.history.value;
  if (history.length === 0) return <p class="note">No rounds fought yet.</p>;
  return (
    <div class="rounds">
      <StrengthCharts store={store} />
      {history.map((report, i) => <Round store={store} report={report} open={i === history.length - 1} />)}
    </div>
  );
}
