import { describe, expect, it } from 'vitest';

import battles from '../../../test_cases/parity/battles.json';
import fixture from '../../../test_cases/parity/summaries.json';
import { Battle } from './battle';
import type { StateData } from './state';
import { orderOfBattle, sideSummary } from './summary';

const finals = battles.cases.map((c) => c.final as unknown as StateData);

describe('summaries match the Python step API', () => {
  it.each(fixture.cases.map((c, i) => [c.name, c.seed, i] as const))('%s, seed %s', (_name, _seed, i) => {
    const expected = fixture.cases[i];
    expect(orderOfBattle(finals[i])).toEqual(expected.order_of_battle);
    if (expected.side_summary === null) expect(() => sideSummary(finals[i])).toThrow('finish');
    else expect(sideSummary(finals[i])).toEqual(expected.side_summary);
  });

  it('names the sides Side 0 / Side 1 when the setup gave none', () => {
    const state = { ...finals[0], meta: {} };
    expect(orderOfBattle(state).map((s) => s.name)).toEqual(['Side 0', 'Side 1']);
  });

  it('exchange ratio is null for a side never hit', () => {
    const b = Battle.fromDict(structuredClone(finals[0]));
    const state = b.toDict();
    for (const u of state.units) if (u.side === 0) u.losses = 0;
    for (const o of Object.values(state.result!.units)) o.hits = 0;
    expect(sideSummary(state)[0].exchange_ratio).toBeNull();
  });
});

describe('sideSummary', () => {
  it('needs a finished battle', () => {
    expect(() => sideSummary({ ...finals[0], result: null })).toThrow('finish');
  });
});
