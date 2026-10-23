/** Each unit's order for the next round, the round's length, and a preview of what the orders would start. */

import defaults from '../engine/defaults.json';
import { ArtilleryBattery, type Engagement, ON_BREAK } from '../engine';
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
      <p class="note">Expected rates at the start of the round; no dice rolled yet.</p>
    </div>
  );
}

export function OrdersPanel({ store }: { store: Store }) {
  const battle = store.battle.value!;
  const { arrows, error } = store.preview.value;
  return (
    <div class="orders">
      <div class="table-wrap">
        <table aria-label="Orders">
          <thead>
            <tr><th>Unit</th><th>Action</th><th>Target</th><th>Ammo</th><th>If the target breaks</th></tr>
          </thead>
          <tbody>
            {store.actingUnits.value.map((unit) => {
              const order = store.orders.value[unit.uid];
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
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div class="controls">
        <label>
          Round length (minutes){' '}
          <input aria-label="Round length" type="number" min="1" class="num" value={store.duration.value}
            onInput={(e) => { store.duration.value = Number(e.currentTarget.value); }} />
        </label>
        <label>
          <input type="checkbox" checked={store.recordEvents.value}
            onChange={(e) => { store.recordEvents.value = e.currentTarget.checked; }} />
          {' '}Record every casualty (bigger download)
        </label>
        <span class="note">Round {battle.round + 1}, from minute {battle.time}</span>
      </div>
      <h3>Preview</h3>
      {error === null ? <Preview store={store} arrows={arrows} /> : <p role="alert" class="problems">{error}</p>}
    </div>
  );
}
