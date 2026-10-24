/**
 * Each unit's order for the next round, the round's length, and a preview of what the orders would start.
 * Admin view: one table of everyone's orders, and the round is fought here. Player view: your orders, and what
 * you expect the enemy to do (used for the preview and the estimate, never sent to the admin).
 */

import { useState } from 'preact/hooks';

import defaults from '../engine/defaults.json';
import { ArtilleryBattery, type BattleUnit, type Engagement, ON_BREAK } from '../engine';
import { EstimatePanel } from './EstimatePanel';
import type { Store } from './store';

/** Action word -> engine mode (config/sheets.yaml: fire, charge, hold). */
const ACTIONS = Object.entries(defaults.names.actions) as [string, string][];
const AMMO = Object.entries(defaults.names.ammo) as [string, string][];
const ON_BREAK_LABELS: Record<string, string> = {
  keep: 'keep firing', strongest: 'switch to the strongest', weakest: 'switch to the weakest',
  fall_back: 'fall back', pursue: 'pursue',
};
const KIND_LABELS: Record<string, string> = { ranged: 'fire', melee: 'melee', closing: 'closing fire' };

function Preview({ store, arrows }: { store: Store; arrows: Engagement[] }) {
  const name = (uid: string) => store.battle.value!.units.get(uid)!.name;
  if (arrows.length === 0) return <p class="note">No fighting with these orders.</p>;
  return (
    <div class="table-wrap">
      <table aria-label="Engagements">
        <thead>
          <tr><th>Attacker</th><th>Target</th><th>Kind</th><th class="num">Casualties / hour</th></tr>
        </thead>
        <tbody>
          {arrows.map((a) => (
            <tr>
              <td>{name(a.attacker)}</td>
              <td>{name(a.target)}</td>
              <td>{KIND_LABELS[a.mode]}</td>
              <td class="num">{(a.rate * 60).toFixed(1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p class="note">Expected rates at the start of the round; no dice rolled yet. Closing fire lasts only while a
        charge approaches (a few minutes).</p>
    </div>
  );
}

function OrderRow({ store, unit, expected, admin }:
  { store: Store; unit: BattleUnit; expected: boolean; admin: boolean }) {
  const order = store.effectiveOrders.value[unit.uid];
  const battery = unit.regiment instanceof ArtilleryBattery;
  const label = (what: string) => `${unit.name} ${what}`;
  return (
    <tr class={`side-${unit.side}`}>
      <td>{unit.name}</td>
      <td>
        <select aria-label={label('action')} value={order.mode}
          onChange={(e) => store.setOrder(unit.uid, { mode: e.currentTarget.value })}>
          {ACTIONS.map(([word, mode]) => <option value={mode}>{word}</option>)}
        </select>
      </td>
      <td>
        {order.mode === 'idle' ? '—' : (
          <select aria-label={label('target')} value={order.target!}
            onChange={(e) => store.setOrder(unit.uid, { target: e.currentTarget.value })}>
            {store.targetsFor(unit.uid).map((t) => (
              <option value={t.uid}>{t.name}{t.morale.broken ? ' (broken)' : ''}</option>
            ))}
          </select>
        )}
      </td>
      <td>
        {battery && order.mode === 'ranged' ? (
          <select aria-label={label('ammo')} value={order.ammo!}
            onChange={(e) => store.setOrder(unit.uid, { ammo: e.currentTarget.value })}>
            {AMMO.map(([word, ammo]) => <option value={ammo}>{word}</option>)}
          </select>
        ) : '—'}
      </td>
      <td>
        {order.mode === 'idle' ? '—' : (
          <select aria-label={label('if the target breaks')} value={order.on_break!}
            onChange={(e) => store.setOrder(unit.uid, { on_break: e.currentTarget.value })}>
            {ON_BREAK[order.mode].map((choice) => <option value={choice}>{ON_BREAK_LABELS[choice]}</option>)}
          </select>
        )}
      </td>
      {expected && (
        <td>
          {store.isAssumed(unit.uid)
            ? <button aria-label={`Reset ${unit.name} to the default`} onClick={() => store.resetAssumption(unit.uid)}>
              reset</button>
            : <span class="note">default: {order.mode === 'idle' ? 'holds' : 'returns fire'}</span>}
        </td>
      )}
      {admin && <td>{store.orderSources.value[unit.uid] ?? '—'}</td>}
    </tr>
  );
}

function OrdersTable({ store, units, title, expected, admin = false }:
  { store: Store; units: BattleUnit[]; title: string; expected: boolean; admin?: boolean }) {
  return (
    <div class="table-wrap">
      <table aria-label={title}>
        <thead>
          <tr>
            <th>Unit</th><th>Action</th><th>Target</th><th>Ammo</th><th>If the target breaks</th>
            {expected && <th />}
            {admin && <th>From</th>}
          </tr>
        </thead>
        <tbody>{units.map((u) => <OrderRow store={store} unit={u} expected={expected} admin={admin} />)}</tbody>
      </table>
    </div>
  );
}

/** Player, from a player file: their guesses about each enemy unit's men and stats (otherwise unknown). */
function Guesses({ store }: { store: Store }) {
  const [problem, setProblem] = useState<string | null>(null);
  const enemy = [...store.battle.value!.units.values()].filter((u) => u.side === store.hiddenSide.value && u.size > 0);
  const guess = (uid: string, name: string, change: { size?: number; stats?: string }) => {
    const error = store.setGuess(uid, change);
    setProblem(error === null ? null : `${name}: ${error}`);
  };
  return (
    <>
      <h3>Your guesses about the enemy</h3>
      <p class="note">You see the enemy's men only roughly, and not their experience, morale or weapons. Your guesses
        drive the preview and the estimate; they never leave this page.</p>
      <div class="table-wrap">
        <table aria-label="Your guesses about the enemy">
          <thead><tr><th>Unit</th><th class="num">Men</th><th>Stats (exp/morale/weapon/melee only)</th></tr></thead>
          <tbody>
            {enemy.map((u) => (
              <tr class={`side-${u.side}`}>
                <td>{u.name}</td>
                <td class="num">
                  <input type="number" min="1" class="num" aria-label={`${u.name} men (guess)`} value={u.size}
                    onChange={(e) => guess(u.uid, u.name, { size: Number(e.currentTarget.value) })} />
                </td>
                <td>
                  <input type="text" aria-label={`${u.name} stats (guess)`} value={u.regiment.stats.join('/')}
                    onChange={(e) => guess(u.uid, u.name, { stats: e.currentTarget.value })} />
                </td>
              </tr>
            ))}
          </tbody>
          {problem !== null && <tfoot><tr><td colSpan={3} role="alert" class="problems">{problem}</td></tr></tfoot>}
        </table>
      </div>
    </>
  );
}

/** Admin: which side's orders file is loaded, and the units that would hold for want of orders. */
function Received({ store }: { store: Store }) {
  const sides = store.sides.value;
  const loaded = store.plansLoaded.value;
  const missing = store.withoutOrders.value;
  return (
    <>
      <h3>Players' orders</h3>
      <ul aria-label="Orders received">
        {([0, 1] as const).map((side) => <li>{sides[side]}: {loaded[side] ?? 'no orders file yet'}</li>)}
      </ul>
      {missing.length > 0 && (
        <p class="note">Without orders (they will hold): {missing.map((u) => u.name).join(', ')}</p>
      )}
    </>
  );
}

const percent = (v: number) => (v === 0 ? '' : String(Math.round(v * 100)));

/** Admin: this round's modifiers per unit, in percent, with a note. */
function Modifiers({ store }: { store: Store }) {
  const mods = store.modifiers.value;
  const units = [...store.battle.value!.units.values()].filter((u) => u.size > 0);
  const count = Object.keys(mods).length;
  // a number input reads '' while empty or half typed (a lone '-'), which counts as 0
  const setPercent = (uid: string, key: 'fire' | 'melee' | 'morale', text: string) =>
    store.setModifier(uid, { [key]: Number(text) / 100 });
  return (
    <details class="modifiers">
      <summary>Modifiers for this round ({count === 0 ? 'none set' : `${count} set`})</summary>
      <p class="note">Percent changes for the next round only, e.g. fire -15 for a unit firing uphill. Fire and
        melee change the casualties the unit inflicts (closing fire counts as fire); morale changes how fast it
        loses morale (+10: 10% slower). From -100 to +100.</p>
      <div class="table-wrap">
        <table aria-label="Modifiers">
          <thead>
            <tr><th>Unit</th><th class="num">Fire %</th><th class="num">Melee %</th><th class="num">Morale %</th>
              <th>Note</th></tr>
          </thead>
          <tbody>
            {units.map((u) => (
              <tr class={`side-${u.side}`}>
                <td>{u.name}</td>
                {(['fire', 'melee', 'morale'] as const).map((key) => (
                  <td class="num">
                    <input type="number" step="5" class="num" aria-label={`${u.name} ${key} %`}
                      value={percent(mods[u.uid]?.[key] ?? 0)}
                      onInput={(e) => setPercent(u.uid, key, e.currentTarget.value)} />
                  </td>
                ))}
                <td>
                  <input type="text" aria-label={`${u.name} note`} value={mods[u.uid]?.note ?? ''}
                    onInput={(e) => store.setModifier(u.uid, { note: e.currentTarget.value })} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

export function OrdersPanel({ store }: { store: Store }) {
  const battle = store.battle.value!;
  const { arrows, error } = store.preview.value;
  const [problem, setProblem] = useState<string | null>(null);
  const player = store.mode.value === 'player';
  const acting = store.actingUnits.value;
  const side = store.playerSide.value;
  return (
    <div class="orders">
      {player ? (
        <>
          <h3>Your orders</h3>
          <OrdersTable store={store} units={acting.filter((u) => u.side === side)} title="Your orders" expected={false} />
          <h3>What you expect the enemy to do</h3>
          <p class="note">Only for the preview and the estimate; your orders file never includes it.</p>
          <OrdersTable store={store} units={acting.filter((u) => u.side !== side)}
            title="What you expect the enemy to do" expected />
          {store.hiddenSide.value !== null && <Guesses store={store} />}
        </>
      ) : (
        <>
          <Received store={store} />
          <OrdersTable store={store} units={acting} title="Orders" expected={false} admin />
          <Modifiers store={store} />
        </>
      )}
      <div class="controls">
        <label>
          Round length (minutes){' '}
          <input aria-label="Round length" type="number" min="1" class="num" value={store.duration.value}
            onInput={(e) => { store.duration.value = Number(e.currentTarget.value); }} />
        </label>
        <span class="note">Round {battle.round + 1}, from minute {battle.time}</span>
        {player ? <span class="note">The admin fights the rounds and finishes the battle.</span> : (
          <>
            <label>
              <input type="checkbox" checked={store.recordEvents.value}
                onChange={(e) => { store.recordEvents.value = e.currentTarget.checked; }} />
              {' '}Record every casualty (bigger download)
            </label>
            <button class="primary" disabled={error !== null} onClick={() => setProblem(store.resolve())}>
              Fight round {battle.round + 1}
            </button>
          </>
        )}
      </div>
      {problem !== null && <p role="alert" class="problems">{problem}</p>}
      <h3>Preview</h3>
      {error === null ? <Preview store={store} arrows={arrows} /> : <p role="alert" class="problems">{error}</p>}
      <EstimatePanel store={store} disabled={error !== null} />
    </div>
  );
}
