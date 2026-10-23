/** The battle client: build two armies, give each round's orders, resolve, and read the result. */
export function App() {
  return (
    <div class="app">
      <header>
        <h1>Imperial Generals</h1>
        <p class="lede">Battle resolver: same seed, same battle as the Python engine.</p>
      </header>
      <main>
        <section aria-labelledby="armies">
          <h2 id="armies">Armies</h2>
        </section>
        <section aria-labelledby="orders">
          <h2 id="orders">Orders</h2>
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
