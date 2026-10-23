import { describe, expect, it } from 'vitest';

import battles from '../../../test_cases/parity/battles.json';
import { chargeText, status } from './format';
import { createStore } from './store';

const started = () => {
  const s = createStore(1863);
  s.start();
  return s;
};

describe('store: resolving a round', () => {
  it('fights the round with the orders, length and events toggle, like the engine', () => {
    const s = started();
    s.setOrder('us_1mn', { mode: 'ranged', target: 'cs_8al' });
    s.setOrder('cs_8al', { mode: 'ranged', target: 'us_1mn' });
    s.duration.value = 45;
    s.recordEvents.value = true;
    expect(s.resolve()).toBeNull();
    const report = s.history.value[0];
    expect([report.round, report.start, report.end]).toEqual([1, 0, 45]);
    expect(report.events.length).toBe(report.units.us_1mn.losses + report.units.cs_8al.losses);
    expect(s.battle.value!.time).toBe(45);
  });

  it('carries orders into the next round, dropping ones that can no longer be carried out', () => {
    const s = started();
    s.setOrder('us_1mn', { mode: 'ranged', target: 'cs_11al' });
    s.setOrder('us_15ma', { mode: 'ranged', target: 'cs_10al' });
    s.setOrder('cs_11al', { mode: 'ranged', target: 'us_1mn' });
    const battle = s.battle.value!;
    battle.units.get('cs_10al')!.regiment.updateSize(1);    // will be wiped out
    battle.units.get('cs_11al')!.morale.forceBreak();      // broken: can't act, can still be fired on
    s.orders.value = { ...s.orders.value, cs_11al: { mode: 'idle', target: null, ammo: null, on_break: null } };
    s.duration.value = 120;
    expect(s.resolve()).toBeNull();
    expect(battle.units.get('cs_10al')!.size).toBe(0);
    expect(s.orders.value.us_1mn).toMatchObject({ mode: 'ranged', target: 'cs_11al' });
    expect(s.orders.value.us_15ma.mode).toBe('idle');
  });

  it('says why a round can not be fought, and fights nothing', () => {
    const s = started();
    s.duration.value = 0;
    expect(s.resolve()).toBe('The round length must be more than 0 minutes.');
    s.duration.value = 30;
    s.orders.value = { ...s.orders.value, us_1mn: { mode: 'ranged', target: 'us_15ma', ammo: null, on_break: 'keep' } };
    expect(s.resolve()).toMatch(/same side/);
    expect(s.history.value).toEqual([]);
  });

  it('has no history before the battle', () => {
    expect(createStore(1).history.value).toEqual([]);
  });
});

describe('format', () => {
  it('says how a unit stands', () => {
    expect(status(0, true, 12)).toBe('wiped out');
    expect(status(10, true, 12.4)).toBe('broke at 12 min');
    expect(status(10, true, null)).toBe('broken');
    expect(status(10, false, null, 1)).toBe('1 gun lost');
    expect(status(10, true, 30, 3)).toBe('broke at 30 min, 3 guns lost');
    expect(status(10, false, null)).toBe('');
  });

  it('describes charges as the CLI does', () => {
    const names = (uid: string) => uid.toUpperCase();
    const all = battles.cases.flatMap((c) => c.final.history.flatMap((r) => r.charges));
    const tested = all.find((c) => c.p_home !== null)!;
    expect(chargeText(tested, names)).toMatch(/^[A-Z_0-9]+ -> [A-Z_0-9]+: .+ at \d+ min \(\d+% to go home, \d+% falter, \d+% break\)$/);
    const pursuit = all.find((c) => c.outcome === 'pursuit')!;
    expect(chargeText(pursuit, names)).toMatch(/: pursuit at \d+ min$/);
  });
});
