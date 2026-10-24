/** Finishing the battle, then the result: who held the field and why, each side's toll, each unit's casualties. */

import { useState } from 'preact/hooks';

import type { FieldHolder, SideSummary } from '../engine';
import { fieldText } from './format';
import type { Store } from './store';

const n = (v: number) => v.toLocaleString('en-US');
const pct = (v: number) => `${(v * 100).toFixed(0)}%`;

const SUMMARY_ROWS: [string, (s: SideSummary) => string][] = [
  ['Result', (s) => s.outcome],
  ['Started', (s) => n(s.started)],
  ['Killed', (s) => n(s.killed)],
  ['Wounded', (s) => n(s.wounded)],
  ['Prisoners lost', (s) => n(s.prisoners_lost)],
  ['Casualties', (s) => `${n(s.casualties)} (${pct(s.casualty_share)})`],
  ['Wounded returned', (s) => n(s.returned)],
  ['Final', (s) => n(s.final)],
  ['Lost for good', (s) => pct(s.loss_share)],
  ['Hits taken', (s) => n(s.hits_taken)],
  ['Hits inflicted', (s) => n(s.hits_inflicted)],
  ['Exchange ratio (inflicted / taken)', (s) => (s.exchange_ratio === null ? '—' : s.exchange_ratio.toFixed(2))],
  ['Prisoners taken', (s) => n(s.prisoners_taken)],
  ['Guns lost', (s) => n(s.guns_lost)],
  ['Guns taken', (s) => n(s.guns_taken)],
  ['Units broken or wiped out', (s) => `${s.units_out} of ${s.units}`],
];

function FinishControls({ store }: { store: Store }) {
  const [holder, setHolder] = useState('auto');
  const sides = store.sides.value;
  const value = (): FieldHolder => (holder === 'auto' ? 'auto' : holder === 'none' ? null : (Number(holder) as 0 | 1));
  return (
    <div class="controls">
      <label>
        Who holds the field{' '}
        <select aria-label="Who holds the field" value={holder} onChange={(e) => setHolder(e.currentTarget.value)}>
          <option value="auto">decided by the engine</option>
          <option value="0">{sides[0]}</option>
          <option value="1">{sides[1]}</option>
          <option value="none">nobody (a draw)</option>
        </select>
      </label>
      <button class="primary" onClick={() => store.finish(value())}>Finish the battle</button>
      <span class="note">Settles killed, wounded and prisoners; no more rounds after this.</span>
    </div>
  );
}

export function ResultPanel({ store }: { store: Store }) {
  const battle = store.battle.value;
  if (battle === null) return <p class="note">Start the battle, fight its rounds, then finish it here.</p>;
  const summary = store.summary.value;
  if (summary === null) {
    return store.mode.value === 'player' ? <p class="note">Not finished yet.</p> : <FinishControls store={store} />;
  }
  const result = battle.result!;
  return (
    <div class="result">
      <p class="field">{fieldText(result, store.sides.value)}</p>
      <div class="table-wrap">
        <table aria-label="Side summary">
          <thead><tr><th />{summary.map((s) => <th class="num">{s.name}</th>)}</tr></thead>
          <tbody>
            {SUMMARY_ROWS.map(([label, cell]) => (
              <tr><td>{label}</td>{summary.map((s) => <td class="num">{cell(s)}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
      <h3>Casualties by unit</h3>
      <div class="table-wrap">
        <table aria-label="Casualties by unit">
          <thead>
            <tr>
              <th>Unit</th><th class="num">Started</th><th class="num">Killed</th><th class="num">Wounded</th>
              <th class="num">Prisoners</th><th class="num">Returned</th><th class="num">Final</th>
              <th class="num">Inflicted</th><th class="num">Guns lost</th>
            </tr>
          </thead>
          <tbody>
            {[...battle.units.values()].map((u) => {
              const o = result.units[u.uid];
              return (
                <tr class={`side-${u.side}`}>
                  <td>{u.name}</td>
                  <td class="num">{n(u.initialSize)}</td>
                  <td class="num">{n(o.killed)}</td>
                  <td class="num">{n(o.wounded - o.wounded_captured)}</td>
                  <td class="num">{n(o.captured_in_rout + o.wounded_captured)}</td>
                  <td class="num">{n(o.wounded_returned)}</td>
                  <td class="num">{n(o.final_size)}</td>
                  <td class="num">{n(u.inflicted)}</td>
                  <td class="num">{o.guns_lost || ''}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p class="note">Final = Started − Killed − Wounded − Prisoners + Returned (wounded who recover rejoin).</p>
    </div>
  );
}
