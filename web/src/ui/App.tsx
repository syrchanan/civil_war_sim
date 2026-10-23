/** The battle client: build two armies, give each round's orders, resolve, and read the result. */

import { ArmyBuilder } from './ArmyBuilder';
import { OrderOfBattle } from './OrderOfBattle';
import { OrdersPanel } from './OrdersPanel';
import { createStore, type Store } from './store';

const defaultStore = createStore();

export function App({ store = defaultStore }: { store?: Store }) {
  const battle = store.battle.value;
  return (
    <div class="app">
      <header>
        <h1>Imperial Generals</h1>
        <p class="lede">Battle resolver: same seed, same battle as the Python engine.</p>
      </header>
      <main>
        <section aria-labelledby="armies">
          <h2 id="armies">Armies</h2>
          {battle === null ? <ArmyBuilder store={store} /> : (
            <>
              <OrderOfBattle sides={store.orderOfBattle.value!} />
              <button onClick={() => store.reset()}>Change the armies (starts over)</button>
            </>
          )}
        </section>
        <section aria-labelledby="orders">
          <h2 id="orders">Orders</h2>
          {battle === null ? <p class="note">Start the battle to give orders.</p> : <OrdersPanel store={store} />}
        </section>
        <section aria-labelledby="rounds">
          <h2 id="rounds">Rounds</h2>
        </section>
        <section aria-labelledby="result">
          <h2 id="result">Result</h2>
        </section>
      </main>
    </div>
  );
}
