/**
 * The admin's review of one side's army, beside its table: what is wrong with it (each problem linked to its row),
 * the army at a glance against the other side, and the decision: approve it, or send it back with a note for the
 * player. Round 0 opens once both are approved.
 */

import { useState } from 'preact/hooks';

import type { Store, UnitDraft } from './store';

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`;
const count = (n: number) => n.toLocaleString('en-US');

/** An army in numbers: regiments, men, each arm, guns, average experience and morale. */
export function glance(drafts: UnitDraft[]) {
  const finite = (n: number | null) => (Number.isFinite(n) ? (n as number) : 0);
  const stat = (i: number) => {
    const values = drafts.map((u) => Number(u.stats.split('/')[i])).filter(Number.isFinite);
    return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
  };
  return {
    regiments: drafts.length,
    men: drafts.reduce((sum, u) => sum + finite(u.size), 0),
    infantry: drafts.filter((u) => u.type === 'inf' || u.type === null).length,
    cavalry: drafts.filter((u) => u.type === 'cav').length,
    batteries: drafts.filter((u) => u.type === 'art').length,
    guns: drafts.reduce((sum, u) => sum + (u.type === 'art' ? finite(u.guns) : 0), 0),
    experience: stat(0),
    morale: stat(1),
  };
}

const average = (g: ReturnType<typeof glance>) => (g.experience === null || g.morale === null ? 'no stats'
  : `experience ${g.experience.toFixed(1)} · morale ${g.morale.toFixed(1)}`);

function Glance({ store, side }: { store: Store; side: 0 | 1 }) {
  const g = glance(store.units.value.filter((u) => u.side === side));
  const other = glance(store.units.value.filter((u) => u.side !== side));
  return (
    <dl class="glance">
      <div><dt>Regiments</dt><dd>{g.regiments}</dd></div>
      <div><dt>Men</dt><dd>{count(g.men)}</dd></div>
      <div><dt>By arm</dt><dd>{g.infantry} infantry · {g.cavalry} cavalry · {g.batteries}{' '}
        batter{g.batteries === 1 ? 'y' : 'ies'} ({plural(g.guns, 'gun')})</dd></div>
      <div><dt>Average</dt><dd>{average(g)}</dd></div>
      <div><dt>Against</dt><dd>{store.sides.value[1 - side]}: {count(other.men)} men, {average(other)}</dd></div>
    </dl>
  );
}

function Status({ store, side }: { store: Store; side: 0 | 1 }) {
  const r = store.review.value[side];
  const from = r.file === null ? '' : ` · ${r.file}`;
  if (r.approved) return <p class="review-status approved">✓ Approved{from}</p>;
  if (r.sentBack) return <p class="review-status sent-back">Sent back{from}</p>;
  return <p class="review-status">Not approved yet{from}</p>;
}

export function ArmyReview({ store, side }: { store: Store; side: 0 | 1 }) {
  const [sent, setSent] = useState<{ text: string; copied: boolean } | null>(null);
  const name = store.sides.value[side];
  const r = store.review.value[side];
  const drafts = store.units.value.filter((u) => u.side === side);
  const broken = drafts.flatMap((u) => {
    const problem = store.unitProblem(u);
    // in a large army, which brigade it is in helps to find it
    const where = u.org?.brigade ? ` (${u.org.brigade})` : '';
    return problem === null ? [] : [{ id: u.id, text: `${u.name}${where}: ${problem}` }];
  });
  const problems = store.sideProblems(side);
  const onSendBack = () => {
    const text = store.sendBack(side);
    setSent({ text, copied: false });
    // copied when the browser allows it; the text stays on show either way
    navigator.clipboard?.writeText(text).then(() => setSent({ text, copied: true }), () => {});
  };
  return (
    <section class="review" aria-label={`Review: ${name}`}>
      <h3>Review: {name}</h3>
      <Status store={store} side={side} />
      {problems.length > 0 && (
        <div class="review-problems">
          <p><strong>{plural(problems.length, 'problem')} to check</strong></p>
          <ul>
            {r.lineProblems.map((p) => <li>{r.file === null ? p : `${r.file}: ${p}`} (left out)</li>)}
            {broken.map((p) => <li><a href={`#unit-${p.id}`}>{p.text}</a></li>)}
            {drafts.length === 0 && <li>{name} has no units.</li>}
          </ul>
          {r.lineProblems.length > 0 && (
            <button onClick={() => store.dropUnreadLines(side)}>Go on without the lines left out</button>
          )}
        </div>
      )}
      <Glance store={store} side={side} />
      <label>Note to the {name} player
        <textarea rows={3} value={r.note} onInput={(e) => store.setReviewNote(side, e.currentTarget.value)} />
      </label>
      <div class="review-actions">
        <button onClick={onSendBack}>Send back</button>
        <button class="primary" disabled={problems.length > 0} onClick={() => store.approve(side)}>Approve</button>
      </div>
      {sent !== null && (
        <div class="sent-note">
          <p class="note">{sent.copied ? 'Copied: send it to the player.' : 'Copy this and send it to the player.'}</p>
          <textarea readOnly rows={6} aria-label={`What to send the ${name} player`} value={sent.text} />
        </div>
      )}
    </section>
  );
}
