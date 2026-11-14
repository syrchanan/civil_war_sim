/**
 * A round's dispatch as a newspaper report: headline, what happened, each side's regiments, the charges and what was
 * seen of the enemy. Docked beside the field after a round (with the way on to the next orders), and listed under
 * the Dispatches tab.
 */

import type { DispatchRow } from './dispatch';
import type { Store } from './store';

const STATE_WORDS: Record<DispatchRow['state'], string> = {
  steady: 'Steady', shaken: 'Shaken', wavering: 'Wavering', broken: 'Broken', 'wiped out': 'Wiped out',
};

function stateText(row: DispatchRow): string {
  return row.morale === null ? STATE_WORDS[row.state] : `${STATE_WORDS[row.state]} · ${Math.round(row.morale * 100)}%`;
}

export function DispatchCard({ store, round, docked = false }: { store: Store; round: number; docked?: boolean }) {
  store.revision.value; // a player's guesses and new rounds change what is shown
  const d = store.dispatchOf(round);
  const b = store.battle.value!;
  const viewer = store.mode.value === 'player';
  const close = () => {
    store.dispatchRound.value = null;
    store.mapRound.value = null;
  };
  return (
    <article class="dispatch" aria-label={`Dispatch, round ${round}`}>
      <p class="kicker">Dispatch · Round {round} · {d.span}</p>
      <h3>{d.headline}</h3>
      <div class="dispatch-summary">{d.summary.map((s) => <p>{s}</p>)}</div>
      {d.sides.map(({ side, rows }) => (
        <section class="dispatch-part">
          <h4>{viewer ? 'Your regiments' : store.sides.value[side]}</h4>
          <table aria-label={`Round ${round}: ${viewer ? 'your regiments' : store.sides.value[side]}`}>
            <thead><tr><th>Regiment</th><th class="num">Lost</th><th class="num">Left</th><th>State</th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr class={r.morale === null ? 'down' : undefined}>
                  <td>{r.name}</td><td class="num">{r.lost}</td><td class="num">{r.left}</td><td>{stateText(r)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}
      {d.charges.length > 0 && (
        <section class="dispatch-part">
          <h4>Charges</h4>
          <ul>{d.charges.map((c) => <li>{c}</li>)}</ul>
        </section>
      )}
      {d.enemy.length > 0 && (
        <section class="dispatch-part">
          <h4>Of the enemy</h4>
          <ul>{d.enemy.map((e) => <li>{e}</li>)}</ul>
        </section>
      )}
      <div class="dispatch-actions">
        <button onClick={() => {
          store.cancelTargeting();
          store.mapRound.value = round;
        }}>Replay on the map</button>
        {docked && (
          <button class="primary" onClick={close}>
            {b.finished || round < b.round ? 'Close' : `On to round ${round + 1} orders`}
          </button>
        )}
      </div>
    </article>
  );
}
