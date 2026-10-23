import { describe, expect, it } from 'vitest';

import { fieldText } from './format';
import { createStore } from './store';

const fought = () => {
  const s = createStore(1863);
  s.start();
  s.setOrder('us_1mn', { mode: 'ranged', target: 'cs_8al' });
  s.setOrder('cs_8al', { mode: 'ranged', target: 'us_1mn' });
  s.resolve();
  return s;
};

describe('store: finishing the battle', () => {
  it('settles casualties, decided by the engine by default', () => {
    const s = fought();
    expect(s.summary.value).toBeNull();
    s.finish('auto');
    const battle = s.battle.value!;
    expect(battle.finished).toBe(true);
    expect(battle.result!.field_decided_by).not.toBe('admin');
    expect(s.summary.value!.map((x) => x.name)).toEqual(['Union', 'Confederate']);
  });

  it('or as the admin names it', () => {
    const s = fought();
    s.finish(1);
    expect(s.battle.value!.result).toMatchObject({ field_held_by: 1, field_decided_by: 'admin' });
    expect(s.summary.value!.map((x) => x.outcome)).toEqual(['lost', 'won']);
  });

  it('has no summary before the battle', () => {
    expect(createStore(1).summary.value).toBeNull();
  });
});

describe('fieldText (as the CLI words it)', () => {
  const sides = ['Union', 'Confederate'];
  it.each([
    [{ field_held_by: 0, field_decided_by: 'army_out', field_votes: {} }, 'Field held by: Union (the whole Confederate army broke)'],
    [{ field_held_by: 1, field_decided_by: 'votes', field_votes: { exchange: 1, routs: null, standing: 1 } },
      'Field held by: Confederate (votes: casualty exchange Confederate, routs -, strength standing Confederate)'],
    [{ field_held_by: null, field_decided_by: 'votes', field_votes: { exchange: 0, routs: 1, standing: 0 } },
      'Field held by: nobody, a draw (votes: casualty exchange Union, routs Confederate, strength standing Union)'],
    [{ field_held_by: 0, field_decided_by: 'admin', field_votes: {} }, 'Field held by: Union (named by the admin)'],
    [{ field_held_by: null, field_decided_by: 'admin', field_votes: {} }, 'Field held by: nobody, a draw (named by the admin)'],
  ])('%j', (result, text) => {
    expect(fieldText(result, sides)).toBe(text);
  });
});
