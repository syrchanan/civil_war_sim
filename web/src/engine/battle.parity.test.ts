import { describe, expect, it } from 'vitest';

import fixture from '../../../test_cases/parity/battles.json';
import { Battle, type FieldHolder, type ModifierInput, type OrderInput } from './battle';
import type { StateData } from './state';

interface Case {
  name: string;
  seed: number;
  start: StateData;
  rounds: {
    duration: number; orders: Record<string, OrderInput>; record_events: boolean;
    modifiers: Record<string, ModifierInput>;
  }[];
  finished: boolean;
  field_held_by: FieldHolder;
  final: StateData;
}

describe('whole battles replay the Python engine exactly', () => {
  it.each(fixture.cases as unknown as Case[])('$name, seed $seed', (c) => {
    const battle = Battle.fromDict(structuredClone(c.start));
    expect(battle.toDict(), 'start state round-trips').toEqual(c.start);
    c.rounds.forEach((r, i) => {
      const report = battle.resolveRound(r.duration, r.orders, r.record_events, r.modifiers);
      expect(report, `round ${i + 1}`).toEqual(c.final.history[i]);
    });
    if (c.finished) battle.finish(c.field_held_by);
    expect(battle.toDict()).toEqual(c.final);
  });

  it('saving mid-battle and resuming is exactly like never saving', () => {
    const c = (fixture.cases as unknown as Case[]).find((x) => x.name === 'charges')!;
    const straight = Battle.fromDict(structuredClone(c.start));
    straight.resolveRound(c.rounds[0].duration, c.rounds[0].orders, false, c.rounds[0].modifiers);
    const resumed = Battle.fromJson(straight.toJson());
    for (const r of c.rounds.slice(1)) {
      expect(resumed.resolveRound(r.duration, r.orders, false, r.modifiers))
        .toEqual(straight.resolveRound(r.duration, r.orders, false, r.modifiers));
    }
    expect(resumed.toDict()).toEqual(straight.toDict());
  });
});
