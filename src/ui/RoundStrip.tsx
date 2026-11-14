/**
 * The day at a glance under the field: each round fought (click to see it on the map as it began, and its dispatch
 * in the dock), the round being ordered now, the rounds still planned, and nightfall.
 */

import { clockText } from './format';
import type { Store } from './store';

export function RoundStrip({ store }: { store: Store }) {
  store.revision.value; // a round fought, the rounds planned changed
  const b = store.battle.value;
  if (b === null) return null;
  const replaying = store.mapRound.value;
  // a round fought shows on the map as it began, with its dispatch in the dock; now closes the dispatch
  const show = (n: number | null) => {
    store.cancelTargeting();
    store.mapRound.value = n;
    store.dispatchRound.value = n;
  };
  const deploying = b.plan.phase === 'deployment';
  const planned = b.plan.rounds_planned;
  const now = b.round + 1;
  // deploying, the button is round 0 and round 1 is still to come
  const next = deploying ? 1 : now + 1;
  const later = b.finished || planned === null ? [] : Array.from({ length: Math.max(0, planned - next + 1) }, (_, i) => next + i);
  return (
    <nav class="round-strip" aria-label="The day">
      <span class="strip-title display">The day</span>
      {b.history.map((r) => {
        const clock = clockText(b.plan.start_clock, r.start);
        return (
          <button aria-pressed={replaying === r.round} class={`fought${replaying === r.round ? ' active' : ''}`}
            onClick={() => show(r.round)}>Round {r.round}{clock === null ? '' : ` · ${clock}`}</button>
        );
      })}
      {!b.finished && (
        <button aria-pressed={replaying === null} class={`now${replaying === null ? ' active' : ''}`}
          onClick={() => show(null)}>{deploying ? 'Round 0 · deployment' : `Round ${now} · orders`}</button>
      )}
      {later.map((n) => <span class="planned">Round {n}</span>)}
      {b.finished
        ? <button aria-pressed={replaying === null} class={`now${replaying === null ? ' active' : ''}`}
          onClick={() => show(null)}>Nightfall</button>
        : <span class="planned">Nightfall</span>}
    </nav>
  );
}
