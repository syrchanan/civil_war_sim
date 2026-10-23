import { describe, expect, it } from 'vitest';

import battles from '../../../test_cases/parity/battles.json';
import { Battle } from '../engine';
import { createStore } from './store';

const fought = () => {
  const s = createStore(1863);
  s.start();
  s.setOrder('us_1mn', { mode: 'ranged', target: 'cs_8al' });
  s.resolve();
  s.resolve();
  return s;
};

describe('store: saving and opening battles', () => {
  it('the download is the battle state file, named by seed and round', () => {
    const s = fought();
    const file = s.download();
    expect(file.name).toBe('battle-1863-round-2.json');
    expect(JSON.parse(file.text)).toEqual(s.battle.value!.toDict());
    s.finish('auto');
    expect(s.download().name).toBe('battle-1863-finished.json');
  });

  it('opening a saved battle resumes it exactly', () => {
    const s = fought();
    const text = s.download().text;
    const other = createStore(5);
    expect(other.open(text)).toBeNull();
    const reopened = other.battle.value!;
    expect(reopened.toDict()).toEqual(s.battle.value!.toDict());
    expect(other.history.value).toHaveLength(2);
    expect(other.seed.value).toBe(1863);
    // fighting on from the file gives the same round as fighting on without saving
    const orders = { us_1mn: { mode: 'ranged', target: 'cs_8al' } };
    expect(reopened.resolveRound(30, orders)).toEqual(s.battle.value!.resolveRound(30, orders));
  });

  it('opens a battle saved by Python, rebuilding the armies and side names', () => {
    const c = battles.cases.find((x) => x.name === 'charges')!;
    const s = createStore(1);
    expect(s.open(JSON.stringify(c.final))).toBeNull();
    expect(s.sides.value).toEqual(['Side 0', 'Side 1']);
    expect(s.units.value.map((u) => u.id)).toEqual(c.final.units.map((u) => u.id));
    const bat = s.units.value.find((u) => u.id === 'x_bat')!;
    expect(bat).toMatchObject({ type: 'art', subtype: 'battery', size: 72, guns: 8, side: 1 });
    expect(s.battle.value!.finished).toBe(true);
    expect(Object.values(s.orders.value).every((o) => o.mode === 'idle')).toBe(true);
  });

  it('named sides come back from the file', () => {
    const s = fought();
    const other = createStore(1);
    other.open(s.download().text);
    expect(other.sides.value).toEqual(['Union', 'Confederate']);
  });

  it('says what is wrong with a file that is not a battle', () => {
    const s = createStore(1);
    expect(s.open('not json')).toMatch(/^This file is not valid JSON/);
    expect(s.open('{"format": "x"}')).toBe('Not a battle state file (format "x").');
    expect(s.battle.value).toBeNull();
  });

  it('a battle with no seed keeps the current seed box', () => {
    const s = fought();
    const data = s.battle.value!.toDict();
    data.seed = null;
    const other = createStore(77);
    other.open(JSON.stringify(data));
    expect(other.seed.value).toBe(77);
    expect(Battle.fromDict(data).seed).toBeNull();
  });
});
