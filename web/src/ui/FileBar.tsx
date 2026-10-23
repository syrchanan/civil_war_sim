/**
 * Save and open battles. The download is the battle state file: it resumes here, and in Python
 * `python -m imperial_generals scenario-from-state battle.json` turns it into a scenario that replays it exactly.
 */

import { useState } from 'preact/hooks';

import type { Store } from './store';

function save(name: string, text: string): void {
  const url = URL.createObjectURL(new Blob([text], { type: 'application/json' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

export function FileBar({ store }: { store: Store }) {
  const [problem, setProblem] = useState<string | null>(null);
  const onOpen = async (input: HTMLInputElement) => {
    const file = input.files?.[0];
    if (!file) return;
    const error = store.open(await file.text());
    setProblem(error === null ? null : `${file.name}: ${error}`);
    input.value = '';
  };
  return (
    <div class="file-bar">
      <button disabled={store.battle.value === null} onClick={() => {
        const { name, text } = store.download();
        save(name, text);
      }}>Download battle</button>
      <label class="button">
        Open a saved battle
        <input type="file" accept=".json,application/json" aria-label="Open a saved battle"
          onChange={(e) => onOpen(e.currentTarget)} />
      </label>
      <span class="note">The download replays in Python: scenario-from-state</span>
      {problem !== null && <p role="alert" class="problems">{problem}</p>}
    </div>
  );
}
