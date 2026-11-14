/**
 * The admin's setup, docked beside the field before the battle: the day (name, start, round length, rounds
 * planned), the ground, the deployment zones and the armies; then open round 0 for the players to deploy, or start
 * the battle at once with the units where the admin placed them.
 */

import { useState } from 'preact/hooks';

import { numberText, toNumber } from './ArmyBuilder';
import { save } from './FileBar';
import { FIELD } from './field';
import { clockText } from './format';
import type { Store } from './store';
import { TERRAIN_PRESETS } from './terrainGen';

const presetName = (p: string) => p[0].toUpperCase() + p.slice(1);

/** '1:00 to 5:00 pm' for the rounds planned; null without a start clock or a fixed number of rounds. */
export function daySpan(clock: string | null, roundLength: number, rounds: number | null): string | null {
  if (clock === null || rounds === null || !(roundLength > 0)) return null;
  return `${clockText(clock, 0)} to ${clockText(clock, roundLength * rounds)}`;
}

function TheDay({ store }: { store: Store }) {
  const rounds = store.roundsPlanned.value;
  const span = daySpan(store.startClock.value, store.duration.value, rounds);
  const setRounds = (n: number | null) => { store.roundsPlanned.value = n; };
  return (
    <section class="setup-card">
      <h3>The day</h3>
      <label>Battle name
        <input value={store.battleName.value} onInput={(e) => { store.battleName.value = e.currentTarget.value; }} />
      </label>
      <div class="pair">
        <label>First round starts
          <input type="time" value={store.startClock.value ?? ''}
            onInput={(e) => { store.startClock.value = e.currentTarget.value || null; }} />
        </label>
        <label>Round length (min)
          <input type="number" min="1" value={numberText(store.duration.value)}
            onInput={(e) => { store.duration.value = toNumber(e.currentTarget.value); }} />
        </label>
      </div>
      <div class="stepper-row">
        <span id="rounds-planned">Rounds planned</span>
        <div class="stepper" role="group" aria-labelledby="rounds-planned">
          <button aria-label="One round fewer" disabled={rounds === null || rounds <= 1}
            onClick={() => setRounds(rounds! - 1)}>−</button>
          <span class="stepper-value">{rounds ?? 'open'}</span>
          <button aria-label="One round more" onClick={() => setRounds((rounds ?? 0) + 1)}>+</button>
        </div>
        <label class="inline">
          <input type="checkbox" checked={rounds === null} onChange={(e) => setRounds(e.currentTarget.checked ? null : 4)} />
          {' '}Open-ended
        </label>
      </div>
      <p class="note">{span === null ? '' : `${span}; `}more rounds can be added during the battle.</p>
    </section>
  );
}

function TheGround({ store }: { store: Store }) {
  return (
    <section class="setup-card">
      <h3>The ground</h3>
      <label>Ground
        <select aria-label="Ground" value={store.terrainPreset.value} onChange={(e) => { store.terrainPreset.value = e.currentTarget.value; }}>
          <option value="none">Open field</option>
          {TERRAIN_PRESETS.map((p) => <option value={p}>{presetName(p)}</option>)}
        </select>
      </label>
      <div class="pair">
        <label>Seed
          <input aria-label="Seed" type="number" min="0" class="num" value={numberText(store.seed.value)}
            onInput={(e) => { store.seed.value = toNumber(e.currentTarget.value); }} />
        </label>
        <button onClick={() => store.newSeed()}>New seed</button>
      </div>
      <p class="note">The seed draws the ground and the battle's dice.</p>
    </section>
  );
}

function Zones({ store }: { store: Store }) {
  return (
    <section class="setup-card">
      <h3>Deployment zones</h3>
      <div class="pair">
        {([0, 1] as const).map((side) => (
          <label>{store.sides.value[side]} (yd deep)
            <input type="number" min="1" max={FIELD.height / 2} class="num" value={numberText(store.zoneDepth.value[side])}
              aria-label={`${store.sides.value[side]} zone depth (yards)`}
              onInput={(e) => store.setZoneDepth(side, toNumber(e.currentTarget.value))} />
          </label>
        ))}
      </div>
      <p class="note">Each side deploys in a band along its own edge of the field.</p>
    </section>
  );
}

function Armies({ store }: { store: Store }) {
  return (
    <section class="setup-card">
      <h3>The armies</h3>
      <ul class="army-status">
        {([0, 1] as const).map((side) => {
          const drafts = store.units.value.filter((u) => u.side === side);
          const men = drafts.reduce((sum, u) => sum + (Number.isFinite(u.size) ? u.size : 0), 0);
          const problems = store.sideProblems(side).length;
          const r = store.review.value[side];
          return (
            <li class={`side-${side}`}>
              <strong>{store.sides.value[side]}</strong>
              <span class="note">{drafts.length} regiment{drafts.length === 1 ? '' : 's'}, {men.toLocaleString('en-US')} men</span>
              {problems > 0 && <span class="note warn">{problems} problem{problems === 1 ? '' : 's'} to check</span>}
              <span class="note">{r.approved ? '✓ Approved' : r.sentBack ? 'Sent back' : 'Not approved yet'}</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/** A player before any battle: how to send an army, and a practice battle against the other side's table. */
function PlayerSetup({ store }: { store: Store }) {
  const [problems, setProblems] = useState<string[]>([]);
  return (
    <div class="setup-panel">
      <p class="note dock-hint">Build your army under Armies, download it (CSV) and send it to the admin. Once both
        armies are approved, the admin sends you a file to deploy them.</p>
      <TheGround store={store} />
      <div class="setup-actions">
        <button onClick={() => setProblems(store.start())}>Start battle</button>
      </div>
      <p class="note">Start battle fights a practice battle here, against the other side's table.</p>
      {problems.length > 0 && <ul role="alert" class="problems">{problems.map((p) => <li>{p}</li>)}</ul>}
    </div>
  );
}

export function SetupPanel({ store }: { store: Store }) {
  const [problems, setProblems] = useState<string[]>([]);
  if (store.mode.value === 'player') return <PlayerSetup store={store} />;
  return (
    <div class="setup-panel">
      <TheDay store={store} />
      <TheGround store={store} />
      <Zones store={store} />
      <Armies store={store} />
      <div class="setup-actions">
        <button class="primary" onClick={() => setProblems(store.openDeployment())}>Open round 0: deployment</button>
        <button onClick={() => setProblems(store.start())}>Start battle</button>
        <button onClick={() => {
          const { name, text } = store.setupDownload();
          save(name, text);
        }}>Save setup</button>
      </div>
      <p class="note">Round 0 has the players place their own regiments; Start battle fights at once, each unit where
        it stands on the map. Approve each army under Armies first.</p>
      {problems.length > 0 && <ul role="alert" class="problems">{problems.map((p) => <li>{p}</li>)}</ul>}
    </div>
  );
}
