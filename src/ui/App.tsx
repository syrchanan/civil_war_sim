/**
 * The battle client, laid out as a map table: a header bar (the battle, where it stands, the file actions), the
 * field in the middle with the selected unit's card docked beside it, and below them a tabbed panel for the orders,
 * the armies, the dispatches (rounds fought) and the result. What the tabs open on follows the phase: setting up,
 * deploying (round 0), the battle, nightfall.
 */

import { useState } from 'preact/hooks';

import { ArmyBuilder } from './ArmyBuilder';
import { DeployPanel } from './DeployPanel';
import { DispatchCard } from './DispatchCard';
import { FileBar } from './FileBar';
import { clockText } from './format';
import { MapView } from './MapView';
import { OrderCard } from './OrderCard';
import { OrderOfBattle } from './OrderOfBattle';
import { OrdersPanel } from './OrdersPanel';
import { ResultPanel } from './ResultPanel';
import { RoundStrip } from './RoundStrip';
import { RoundsPanel } from './RoundsPanel';
import { SetupPanel } from './SetupPanel';
import { createStore, type Store } from './store';
import { UnitInfo } from './UnitInfo';

const defaultStore = createStore();

export type Phase = 'setup' | 'deployment' | 'battle' | 'end';
type Tab = 'orders' | 'armies' | 'dispatches' | 'result';

const TABS: [Tab, string][] = [['orders', 'Orders'], ['armies', 'Armies'], ['dispatches', 'Dispatches'],
  ['result', 'Result']];
const FIRST_TAB: Record<Phase, Tab> = { setup: 'armies', deployment: 'orders', battle: 'orders', end: 'result' };

/** Where the battle stands: being set up, being deployed, being fought, or over. */
export function phaseOf(store: Store): Phase {
  const b = store.battle.value;
  if (b === null) return 'setup';
  if (b.finished) return 'end';
  return b.plan.phase === 'deployment' ? 'deployment' : 'battle';
}

/** 'Round 2 of 4 · 2:00 pm', 'Round 0 · deployment', 'Nightfall · 3 rounds fought', 'Setting up'. */
export function standingText(store: Store): string {
  const b = store.battle.value;
  const phase = phaseOf(store);
  if (b === null) return 'Setting up';
  if (phase === 'deployment') return 'Round 0 · deployment';
  const fought = `${b.round} round${b.round === 1 ? '' : 's'} fought`;
  if (phase === 'end') return `Nightfall · ${fought}`;
  const planned = b.plan.rounds_planned === null ? '' : ` of ${b.plan.rounds_planned}`;
  const clock = clockText(b.plan.start_clock, b.time);
  return `Round ${b.round + 1}${planned}${clock === null ? '' : ` · ${clock}`}`;
}

function Armies({ store }: { store: Store }) {
  if (store.battle.value === null) return <ArmyBuilder store={store} />;
  return (
    <>
      <OrderOfBattle sides={store.orderOfBattle.value!} hidden={store.fogSide.value} />
      {store.playerFileInfo.value === null && (
        <button onClick={() => store.reset()}>Change the armies (starts over)</button>
      )}
    </>
  );
}

export function App({ store = defaultStore }: { store?: Store }) {
  store.revision.value; // the battle changes in place (a round fought, opened, finished)
  const battle = store.battle.value;
  const phase = phaseOf(store);
  const [picked, setPicked] = useState<{ phase: Phase; tab: Tab } | null>(null);
  // a tab picked in an earlier phase gives way to the new phase's own
  const tab = picked !== null && picked.phase === phase ? picked.tab : FIRST_TAB[phase];
  const name = typeof battle?.meta.name === 'string' ? battle.meta.name : null;
  const panels: Record<Tab, preact.JSX.Element> = {
    orders: battle === null ? <p class="note">Start the battle to give orders.</p>
      : battle.finished ? <p class="note">The battle is over.</p>
        : phase === 'deployment' ? <DeployPanel store={store} /> : <OrdersPanel store={store} />,
    armies: <Armies store={store} />,
    dispatches: battle === null ? <p class="note">No rounds fought yet.</p> : <RoundsPanel store={store} />,
    result: <ResultPanel store={store} />,
  };
  return (
    <div class={`app phase-${phase}`}>
      <header class="topbar">
        <div class="masthead">
          <h1>Imperial Generals</h1>
          {name !== null && <span class="battle-name">{name}</span>}
        </div>
        <span class="standing">{standingText(store)}</span>
        <FileBar store={store} />
      </header>
      <div class="stage">
        <section class="field-panel" aria-labelledby="map">
          <h2 id="map">The field</h2>
          <MapView store={store} />
          <RoundStrip store={store} />
        </section>
        <aside class="dock" aria-label={phase === 'setup' ? 'Setting up' : 'Selected unit'}>
          {phase === 'setup' ? <>{store.focusedUnit.value !== null && <UnitInfo store={store} />}<SetupPanel store={store} /></>
            : <>
              {store.dispatchRound.value !== null && (
                <DispatchCard store={store} round={store.dispatchRound.value} docked />
              )}
              {store.focusedUnit.value !== null ? <><UnitInfo store={store} /><OrderCard store={store} /></>
                : store.dispatchRound.value === null
                && <p class="note dock-hint">Select a regiment on the map to see it here.</p>}
            </>}
        </aside>
      </div>
      <section class="tabs-panel" aria-label="Orders, armies, dispatches and result">
        <div role="tablist" aria-label="Panels" class="tabs">
          {TABS.map(([key, label]) => (
            <button role="tab" id={`tab-${key}`} aria-selected={key === tab} aria-controls={`panel-${key}`}
              class={key === tab ? 'active' : ''} onClick={() => setPicked({ phase, tab: key })}>{label}</button>
          ))}
        </div>
        {/* every panel stays on the page (hidden by style when not chosen), so its state survives a tab change */}
        {TABS.map(([key, label]) => (
          <div role="tabpanel" id={`panel-${key}`} aria-labelledby={`tab-${key}`}
            class={`tab-panel${key === tab ? ' active' : ''}`}>
            <h2 class="panel-title">{label}</h2>
            {panels[key]}
          </div>
        ))}
      </section>
    </div>
  );
}
