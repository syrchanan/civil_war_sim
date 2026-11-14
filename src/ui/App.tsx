/**
 * The battle client, laid out as a map table: a header bar (the battle, where it stands, the file actions), then
 * the field on the left at the height of the window and one tabbed sidebar on the right. Each tab scrolls on its
 * own, so selecting a unit or reading a dispatch never moves the map. Which tabs there are, and the one it opens on,
 * follow the phase: setting up, deploying (round 0), the battle, nightfall. A unit selected opens the Unit tab; a
 * round fought opens its dispatch.
 */

import { ArmyBuilder } from './ArmyBuilder';
import { DeployPanel } from './DeployPanel';
import { FileBar } from './FileBar';
import { clockText } from './format';
import { MapView } from './MapView';
import { OrderCard } from './OrderCard';
import { OrderOfBattle } from './OrderOfBattle';
import { OrdersPanel } from './OrdersPanel';
import { ResultPanel } from './ResultPanel';
import { Rosters } from './Rosters';
import { RoundStrip } from './RoundStrip';
import { RoundsPanel } from './RoundsPanel';
import { SetupPanel } from './SetupPanel';
import { createStore, PHASE_TABS, type Phase, type Store, type Tab } from './store';
import { UnitInfo } from './UnitInfo';

const defaultStore = createStore();

export type { Phase } from './store';

const TAB_LABELS: Record<Tab, string> = {
  setup: 'Setup', deploy: 'Deploy', unit: 'Unit', orders: 'Orders', armies: 'Armies', dispatches: 'Dispatches',
  result: 'Result',
};

/** Where the battle stands: being set up, being deployed, being fought, or over. */
export const phaseOf = (store: Store): Phase => store.phase.value;

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
      <Rosters store={store} />
      {store.playerFileInfo.value === null && (
        <button onClick={() => store.reset()}>Change the armies (starts over)</button>
      )}
    </>
  );
}

function UnitTab({ store }: { store: Store }) {
  if (store.focusedUnit.value === null) {
    return <p class="note dock-hint">Select a regiment on the map to see it here.</p>;
  }
  return <><UnitInfo store={store} /><OrderCard store={store} /></>;
}

export function App({ store = defaultStore }: { store?: Store }) {
  store.revision.value; // the battle changes in place (a round fought, opened, finished)
  const battle = store.battle.value;
  const phase = phaseOf(store);
  const tabs = PHASE_TABS[phase];
  const tab = store.sidebarTab.value;
  const wide = store.sidebarWide.value;
  const name = typeof battle?.meta.name === 'string' ? battle.meta.name : null;
  // only the tabs of this phase are built; within a phase each stays on the page (hidden by style when not
  // chosen), so its state survives a tab change
  const panel = (key: Tab): preact.JSX.Element => ({
    setup: () => <SetupPanel store={store} />,
    deploy: () => <DeployPanel store={store} />,
    unit: () => <UnitTab store={store} />,
    orders: () => <OrdersPanel store={store} />,
    armies: () => <Armies store={store} />,
    dispatches: () => <RoundsPanel store={store} />,
    result: () => <ResultPanel store={store} />,
  })[key]();
  return (
    <div class={`app phase-${phase}${wide ? ' wide' : ''}`}>
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
        <aside class="sidebar" aria-label="Sidebar">
          <div class="tab-bar">
            <div role="tablist" aria-label="Panels" class="tabs">
              {tabs.map((key) => (
                <button role="tab" id={`tab-${key}`} aria-selected={key === tab} aria-controls={`panel-${key}`}
                  class={key === tab ? 'active' : ''} onClick={() => store.setTab(key)}>{TAB_LABELS[key]}</button>
              ))}
            </div>
            <button class="widen" aria-pressed={wide} onClick={() => store.setWide(!wide)}>
              {wide ? 'Narrow' : 'Widen'}
            </button>
          </div>
          {tabs.map((key) => (
            <div role="tabpanel" id={`panel-${key}`} aria-labelledby={`tab-${key}`}
              class={`tab-panel${key === tab ? ' active' : ''}`}>
              <h2 class="panel-title">{TAB_LABELS[key]}</h2>
              {panel(key)}
            </div>
          ))}
        </aside>
      </div>
    </div>
  );
}
