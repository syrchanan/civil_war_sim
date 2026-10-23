import { describe, expect, it } from 'vitest';

import { createStore } from './store';

const started = () => {
  const s = createStore(1863);
  expect(s.start()).toEqual([]);
  return s;
};

describe('store: orders', () => {
  it('everyone holds at first; the round length defaults to an hour and events are off', () => {
    const s = started();
    expect(Object.values(s.orders.value).every((o) => o.mode === 'idle')).toBe(true);
    expect(Object.keys(s.orders.value)).toEqual([...s.battle.value!.units.keys()]);
    expect([s.duration.value, s.recordEvents.value]).toEqual([60, false]);
    expect(s.preview.value).toEqual({ arrows: [], error: null });
  });

  it('firing picks the first enemy, charging keeps a target, holding clears it', () => {
    const s = started();
    s.setOrder('us_1mn', { mode: 'ranged' });
    expect(s.orders.value.us_1mn).toEqual({ mode: 'ranged', target: 'cs_8al', ammo: null, on_break: 'keep' });
    s.setOrder('us_1mn', { mode: 'melee' });
    expect(s.orders.value.us_1mn).toEqual({ mode: 'melee', target: 'cs_8al', ammo: null, on_break: 'fall_back' });
    s.setOrder('us_1mn', { target: 'cs_10al', on_break: 'pursue' });
    expect(s.orders.value.us_1mn).toMatchObject({ target: 'cs_10al', on_break: 'pursue' });
    s.setOrder('us_1mn', { mode: 'idle' });
    expect(s.orders.value.us_1mn).toEqual({ mode: 'idle', target: null, ammo: null, on_break: null });
  });

  it('batteries firing get the default ammo; other units and charges have none', () => {
    const s = started();
    s.setOrder('us_bat', { mode: 'ranged' });
    expect(s.orders.value.us_bat.ammo).toBe('round_shot');
    s.setOrder('us_bat', { ammo: 'canister' });
    expect(s.orders.value.us_bat.ammo).toBe('canister');
    s.setOrder('us_bat', { mode: 'melee' });
    expect(s.orders.value.us_bat.ammo).toBeNull();
  });

  it('previews the engagements, or says what is wrong', () => {
    const s = started();
    s.setOrder('us_1mn', { mode: 'ranged' });
    s.setOrder('cs_8al', { mode: 'melee', target: 'us_1mn' });
    const { arrows, error } = s.preview.value;
    expect(error).toBeNull();
    // cs_8al charges us_1mn, which meets it with closing fire instead of its own fire order
    expect(arrows.map((a) => `${a.attacker}>${a.target}:${a.mode}`)).toEqual(['us_1mn>cs_8al:closing']);
    s.orders.value = { ...s.orders.value, us_1mn: { mode: 'ranged', target: 'us_15ma', ammo: null, on_break: 'keep' } };
    expect(s.preview.value.error).toMatch(/same side/);
    expect(s.preview.value.arrows).toEqual([]);
  });

  it('targets: enemies not wiped out, broken ones included', () => {
    const s = started();
    const battle = s.battle.value!;
    battle.units.get('cs_8al')!.morale.forceBreak();
    battle.units.get('cs_10al')!.regiment.updateSize(0);
    s.touch();
    expect(s.targetsFor('us_1mn').map((u) => u.uid)).toEqual(['cs_8al', 'cs_11al', 'cs_bat']);
    expect(s.actingUnits.value.map((u) => u.uid)).toEqual(['us_1mn', 'us_15ma', 'us_bat', 'cs_11al', 'cs_bat']);
  });

  it('sets the round length and the events toggle', () => {
    const s = started();
    s.duration.value = 90;
    s.recordEvents.value = true;
    expect([s.duration.value, s.recordEvents.value]).toEqual([90, true]);
  });
});

describe('store: before the battle starts', () => {
  it('has no units to order and nothing to preview', () => {
    const s = createStore(1);
    expect(s.actingUnits.value).toEqual([]);
    expect(s.preview.value).toEqual({ arrows: [], error: null });
  });
});
