/**
 * The battle's end, at nightfall: the verdict, the butcher's bill, the general each commander fought like (with the
 * odds and the ladder), and the regiments ranked. Both armies in full: the fog lifts once the battle is over.
 */

import { useState } from 'preact/hooks';

import defaults from '../engine/defaults.json';
import { ratingParts, ratings, type SideSummary } from '../engine';
import { figure, generalPhrase, METRICS, type Metric, ranked, type RegimentRow, regimentRows, verdictText } from './ending';
import type { Store } from './store';

const n = (v: number) => v.toLocaleString('en-US');
const pct = (v: number) => `${Math.round(v * 100)}%`;
const SHOWN = 5; // a large battle shows the best and worst five, the rest folded
const LADDER = defaults.commanders.ladder;
const WEIGHTS = defaults.commanders.weights;

const BILL: [string, (s: SideSummary) => string][] = [
  ['Went into battle', (s) => n(s.started)],
  ['Killed', (s) => n(s.killed)],
  ['Wounded', (s) => n(s.wounded)],
  ['Captured or missing', (s) => n(s.prisoners_lost)],
  ['Casualties', (s) => `${n(s.casualties)} · ${pct(s.casualty_share)}`],
  ['Wounded back in the ranks', (s) => n(s.returned)],
  ['Guns lost', (s) => n(s.guns_lost)],
  ['Regiments broken', (s) => `${s.units_out} of ${s.units}`],
];

function Bar({ label, share, side }: { label: string; share: number; side: number | null }) {
  return (
    <div class="end-bar">
      <span>{label}</span>
      <span class="end-bar-track" role="img" aria-label={`${label}: ${pct(share)}`}>
        <span class={`end-bar-fill${side === null ? '' : ` side-${side}`}`} style={{ width: pct(Math.min(1, share)) }} />
      </span>
      <span class="num">{pct(share)}</span>
    </div>
  );
}

type Ranked = RegimentRow & { rank: number };

function Regiments({ store, rows, metric }: { store: Store; rows: Ranked[]; metric: Metric }) {
  const find = (uid: string) => {
    store.selectUnit(uid);
    store.centreMap(store.mapUnits.value.find((m) => m.uid === uid)!);
  };
  return (
    <ol class="ranked">
      {rows.map((r) => (
        <li class={`side-${r.side}`} value={r.rank}>
          <span class="rank">{r.rank}</span>
          <span class="ranked-what">
            <button class="link" onClick={() => find(r.uid)}>{r.name}</button>
            <span class="note">{n(r.inflicted)} inflicted · {n(r.lost)} lost · {r.story}</span>
          </span>
          <span class="num ranked-figure">{figure(r, metric)}</span>
        </li>
      ))}
    </ol>
  );
}

export function BattleEnd({ store }: { store: Store }) {
  const [metric, setMetric] = useState<Metric>('ratio');
  const battle = store.battle.value!;
  const summary = store.summary.value!;
  const sides = store.sides.value;
  const verdict = verdictText(summary, battle.result!, sides);
  const state = battle.toDict();
  const rated = ratings(state);
  const parts = ratingParts(state);
  const rows = ranked(regimentRows(battle), metric).map((r, i) => ({ ...r, rank: i + 1 }));
  const big = rows.length > 2 * SHOWN;
  return (
    <div class="battle-end">
      <section class="end-verdict" aria-label="Verdict">
        <p class="end-kicker">{verdict.kicker}</p>
        <h3 class="end-headline">{verdict.headline}</h3>
        {verdict.lines.map((line) => <p>{line}</p>)}
      </section>

      <section aria-label="The butcher's bill">
        <h3>The butcher's bill</h3>
        <div class="table-wrap">
          <table aria-label="Butcher's bill">
            <thead><tr><th />{summary.map((s, i) => <th class={`num side-${i}`}>{s.name}</th>)}</tr></thead>
            <tbody>
              {BILL.map(([label, cell]) => <tr><td>{label}</td>{summary.map((s) => <td class="num">{cell(s)}</td>)}</tr>)}
            </tbody>
          </table>
        </div>
        <h4>Still in the ranks at nightfall</h4>
        {summary.map((s, i) => <Bar label={s.name} share={s.final / s.started} side={i} />)}
      </section>

      <section aria-label="The generals">
        <h3>The generals</h3>
        {rated.map((r, side) => (
          <div class={`end-general side-${side}`}>
            <p class="note">The {r.name} commander fought like</p>
            <p class="end-general-name">{r.general.name}</p>
            <p>at {r.general.battle}: {generalPhrase(r, summary[side].verdict)}</p>
            <details>
              <summary>The odds, and what came of them</summary>
              <Bar label="Expected, by the armies" share={r.expected} side={null} />
              <Bar label="Achieved on the day" share={r.result} side={side} />
              <ul class="note">
                <li>Inflicted {pct(parts[side].casualties)} of all casualties (counts {pct(WEIGHTS.casualties)})</li>
                <li>{parts[side].field === 1 ? 'Held the field' : parts[side].field === 0 ? 'Lost the field' : 'Nobody held the field'}
                  {' '}(counts {pct(WEIGHTS.field)})</li>
                <li>Routs inflicted against suffered: {pct(parts[side].routs)} (counts {pct(WEIGHTS.routs)})</li>
              </ul>
            </details>
          </div>
        ))}
        <ol class="ladder" aria-label="The ladder of generals">
          {LADDER.map((g) => {
            const here = rated.map((r, side) => (r.general.name === g.name ? side : null)).filter((s) => s !== null);
            return (
              <li class={here.map((s) => `at side-${s}`).join(' ')}>
                <span class="ladder-name">{g.name}</span>
                <span class="note">{g.battle}</span>
                {here.length > 0 && <span class="ladder-who">{here.map((s) => sides[s]).join(', ')}</span>}
              </li>
            );
          })}
        </ol>
        <p class="note">From disaster to masterpiece: each side's share of the result against the share its strength
          led to expect.</p>
      </section>

      <section aria-label="Regiments ranked">
        <h3>Regiments ranked</h3>
        <p class="note">Both armies together; the fog lifts at nightfall.</p>
        <label>Rank by{' '}
          <select aria-label="Rank by" value={metric} onChange={(e) => setMetric(e.currentTarget.value as Metric)}>
            {METRICS.map(([key, word]) => <option value={key}>{word}</option>)}
          </select>
        </label>
        {big ? (
          <>
            <h4>Gave the best account of themselves</h4>
            <Regiments store={store} rows={rows.slice(0, SHOWN)} metric={metric} />
            <h4>Fared worst</h4>
            <Regiments store={store} rows={rows.slice(-SHOWN).reverse()} metric={metric} />
            <details>
              <summary>All {rows.length} regiments</summary>
              <Regiments store={store} rows={rows} metric={metric} />
            </details>
          </>
        ) : <Regiments store={store} rows={rows} metric={metric} />}
      </section>
    </div>
  );
}
