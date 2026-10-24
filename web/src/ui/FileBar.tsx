/**
 * Save and open battles, and pass orders between players and the admin. The battle download resumes here, and in
 * Python `python -m imperial_generals scenario-from-state battle.json` turns it into a scenario that replays it
 * exactly. A player downloads their orders file for the next round; the admin loads one per player.
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

const readAll = (input: HTMLInputElement) =>
  // a file input always has a file list (empty when nothing was picked)
  Promise.all([...input.files!].map(async (file) => ({ name: file.name, text: await file.text() })));

export function FileBar({ store }: { store: Store }) {
  const [problem, setProblem] = useState<string | null>(null);
  const battle = store.battle.value;
  const player = store.mode.value === 'player';
  const onOpen = async (input: HTMLInputElement) => {
    const [file] = await readAll(input);
    input.value = '';
    if (!file) return;
    const error = store.open(file.text);
    setProblem(error === null ? null : `${file.name}: ${error}`);
  };
  const onLoadPlans = async (input: HTMLInputElement) => {
    const files = await readAll(input);
    input.value = '';
    if (!files.length) return;
    const problems = store.loadPlans(files);
    setProblem(problems.length ? problems.join(' ') : null);
  };
  return (
    <div class="file-bar">
      {player && battle !== null && (
        <label>
          You command{' '}
          <select aria-label="You command" value={String(store.playerSide.value)}
            onChange={(e) => { store.playerSide.value = Number(e.currentTarget.value) as 0 | 1; }}>
            <option value="0">{store.sides.value[0]}</option>
            <option value="1">{store.sides.value[1]}</option>
          </select>
        </label>
      )}
      <button disabled={battle === null} onClick={() => {
        const { name, text } = store.download();
        save(name, text);
      }}>Download battle</button>
      <label class="button">
        Open a saved battle
        <input type="file" accept=".json,application/json" aria-label="Open a saved battle"
          onChange={(e) => onOpen(e.currentTarget)} />
      </label>
      {player ? (
        <button disabled={battle === null || battle.finished} onClick={() => {
          const { name, text } = store.planDownload();
          save(name, text);
        }}>Download my orders</button>
      ) : (
        <label class="button">
          Load players' orders
          <input type="file" multiple accept=".json,application/json" aria-label="Load players' orders"
            disabled={battle === null} onChange={(e) => onLoadPlans(e.currentTarget)} />
        </label>
      )}
      {problem !== null && <p role="alert" class="problems">{problem}</p>}
    </div>
  );
}
