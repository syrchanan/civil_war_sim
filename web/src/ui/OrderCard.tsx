/**
 * Orders given from the docked card: the selected regiment's action (fire, charge, hold, or for a broken one hold
 * or rally), its target and how far and how well fire tells, a battery's ammunition, and what to do if the target
 * breaks. Shown while a round's orders are being given, for a unit the viewer commands: the admin any, a player
 * their own (what they expect of the enemy is set in its own table).
 */

import { ArtilleryBattery, ON_BREAK } from '../engine';
import { rangeText } from './format';
import { ACTIONS, AMMO, BROKEN_ACTIONS, ON_BREAK_LABELS } from './OrdersPanel';
import type { Store } from './store';

/** The unit whose orders the card can give now, or null. */
export function orderable(store: Store): string | null {
  const uid = store.focusedUnit.value;
  const b = store.battle.value;
  if (uid === null || b === null || b.finished || b.plan.phase !== 'battle' || store.mapRound.value !== null) return null;
  const unit = b.units.get(uid);
  if (unit === undefined) return null;
  if (store.mode.value === 'player' && unit.side !== store.playerSide.value) return null;
  return store.actingUnits.value.some((u) => u.uid === uid) ? uid : null;
}

export function OrderCard({ store }: { store: Store }) {
  store.revision.value; // redraw when the battle changes
  const uid = orderable(store);
  if (uid === null) return null;
  const unit = store.battle.value!.units.get(uid)!;
  const order = store.effectiveOrders.value[uid];
  const can: string[] = store.actionsFor(uid);
  const actions = unit.morale.broken ? BROKEN_ACTIONS
    : ACTIONS.filter(([, mode]) => mode === 'idle' || mode === order.mode || can.includes(mode));
  const range = store.rangeOf(uid);
  const battery = unit.regiment instanceof ArtilleryBattery;
  return (
    <section class="order-card" aria-label={`Orders for ${unit.name}`}>
      <h3>Orders for this round</h3>
      <div role="group" aria-label="Action" class="segmented">
        {actions.map(([word, mode]) => (
          <button aria-pressed={order.mode === mode} class={order.mode === mode ? 'active' : ''}
            onClick={() => store.setOrder(uid, { mode })}>{word[0].toUpperCase() + word.slice(1)}</button>
        ))}
      </div>
      {order.target !== null && (
        <label>Target
          <select value={order.target} onChange={(e) => store.setOrder(uid, { target: e.currentTarget.value })}>
            {store.targetsFor(uid).map((t) => (
              <option value={t.uid}>{t.name}{t.morale.broken ? ' (broken)' : ''}</option>
            ))}
          </select>
        </label>
      )}
      {/* fire that can't tell, for any reason, stands out */}
      {range !== null && (
        <p class={`range-note${range.reach === 0 || !range.inArc || !range.sight ? ' problems' : ''}`}>{rangeText(range)}</p>
      )}
      {battery && order.mode === 'ranged' && (
        <label>Ammunition
          <select value={order.ammo!} onChange={(e) => store.setOrder(uid, { ammo: e.currentTarget.value })}>
            {AMMO.map(([word, ammo]) => <option value={ammo}>{word}</option>)}
          </select>
        </label>
      )}
      {order.target !== null && (
        <label>If the target breaks
          <select value={order.on_break!} onChange={(e) => store.setOrder(uid, { on_break: e.currentTarget.value })}>
            {ON_BREAK[order.mode].map((choice) => <option value={choice}>{ON_BREAK_LABELS[choice]}</option>)}
          </select>
        </label>
      )}
    </section>
  );
}
