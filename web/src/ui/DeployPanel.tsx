/**
 * Round 0, the deployment, under the Orders tab. A player places their own regiments inside their zone and sends
 * the file; the admin loads both sides' files, sees what still stands outside its zone, and opens round 1.
 */

import { useState } from 'preact/hooks';

import type { Store } from './store';

function Outside({ store, uids }: { store: Store; uids: string[] }) {
  const b = store.battle.value!;
  if (uids.length === 0) return null;
  return (
    <div class="review-problems">
      <p><strong>Outside the zone</strong></p>
      <ul>
        {uids.map((uid) => (
          <li><button class="link" onClick={() => store.selectUnit(uid)}>{b.units.get(uid)!.name}</button></li>
        ))}
      </ul>
    </div>
  );
}

// each reads the revision itself: with signals, a child whose props are unchanged re-renders only on its own reads
function PlayerDeploy({ store }: { store: Store }) {
  store.revision.value; // units placed
  const b = store.battle.value!;
  const side = store.playerSide.value;
  const own = [...b.units.values()].filter((u) => u.side === side && u.size > 0);
  const outside = own.filter((u) => store.outsideZone(u.uid)).map((u) => u.uid);
  return (
    <div class="deploy-panel">
      <h3>Round 0: draw up your lines</h3>
      <p>{own.length - outside.length} of {own.length} regiments inside your zone.</p>
      <Outside store={store} uids={outside} />
      <p class="note">Drag each regiment into your zone and turn it to face the enemy, who is not seen until round 1.
        Then Send deployment, and send the file to the admin.</p>
    </div>
  );
}

function AdminDeploy({ store }: { store: Store }) {
  const [problem, setProblem] = useState<string | null>(null);
  store.revision.value; // units placed, deployments loaded
  const b = store.battle.value!;
  const outside = [...b.units.values()].filter((u) => u.size > 0 && store.outsideZone(u.uid)).map((u) => u.uid);
  return (
    <div class="deploy-panel">
      <h3>Round 0: deployment</h3>
      <p class="note">Send each player their player file, then load both deployments (Load players' orders).</p>
      <ul class="army-status">
        {([0, 1] as const).map((side) => {
          const file = store.plansLoaded.value[side];
          return (
            <li class={`side-${side}`}>
              <strong>{store.sides.value[side]}</strong>
              <span class="note">{file === undefined ? 'Waiting for the deployment' : `Deployed: ${file}`}</span>
            </li>
          );
        })}
      </ul>
      <Outside store={store} uids={outside} />
      <button class="primary" disabled={outside.length > 0} onClick={() => setProblem(store.openBattle())}>
        Open round 1
      </button>
      {problem !== null && <p role="alert" class="problems">{problem}</p>}
    </div>
  );
}

export function DeployPanel({ store }: { store: Store }) {
  return store.mode.value === 'player' ? <PlayerDeploy store={store} /> : <AdminDeploy store={store} />;
}
