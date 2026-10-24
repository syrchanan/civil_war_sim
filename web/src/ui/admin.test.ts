import { describe, expect, it } from 'vitest';

import { battleTag } from '../engine';
import { createStore } from './store';

const admin = () => {
  const s = createStore(1863);
  s.start();
  return s;
};
const player = (side: 0 | 1) => {
  const s = createStore(1863, 'player');
  s.start();
  s.playerSide.value = side;
  return s;
};

describe('the battle tag', () => {
  it('is the rounds fought and the dice state, as in Python, and changes with every round', () => {
    const s = admin();
    const data = s.battle.value!.toDict();
    expect(battleTag(data)).toBe(`0-${data.rng_state.join('-')}`);
    s.setOrder('us_1mn', { mode: 'ranged', target: 'cs_8al' });
    s.resolve();
    expect(battleTag(s.battle.value!.toDict())).not.toBe(battleTag(data));
  });

  it('orders files carry it, and files made from an older copy of the battle are refused', () => {
    const union = player(0);
    const plan = JSON.parse(union.planDownload().text);
    expect(plan.battle.tag).toBe(battleTag(union.battle.value!.toDict()));
    const s = admin();
    plan.battle.tag = '0-1-2-3-4';
    expect(s.loadPlans([{ name: 'u.json', text: JSON.stringify(plan) }]))
      .toEqual(['u.json: these orders were made from an older copy of the battle; send the player the latest.']);
    delete plan.battle.tag;                                     // files from before tags: accepted
    expect(s.loadPlans([{ name: 'u.json', text: JSON.stringify(plan) }])).toEqual([]);
  });
});

describe('admin modifiers', () => {
  it('change the preview, are fought with, recorded, and cleared for the next round', () => {
    const s = admin();
    s.setOrder('us_1mn', { mode: 'ranged', target: 'cs_8al' });
    const plain = s.preview.value.arrows.find((a) => a.attacker === 'us_1mn')!.rate;
    const key = s.estimate.value;
    s.setModifier('us_1mn', { fire: -0.5, note: 'uphill' });
    expect(s.modifiers.value).toEqual({ us_1mn: { fire: -0.5, melee: 0, morale: 0, note: 'uphill' } });
    expect(s.preview.value.arrows.find((a) => a.attacker === 'us_1mn')!.rate).toBeCloseTo(plain / 2, 12);
    s.runEstimate(5);
    s.setModifier('us_1mn', { morale: 0.1 });
    expect(s.estimate.value!.current).toBe(false);              // the modifiers changed
    expect(key).toBeNull();
    expect(s.resolve()).toBeNull();
    expect(s.battle.value!.history[0].modifiers.us_1mn).toEqual({ fire: -0.5, melee: 0, morale: 0.1, note: 'uphill' });
    expect(s.modifiers.value).toEqual({});                      // one round only
  });

  it('a modifier set back to nothing is dropped', () => {
    const s = admin();
    s.setModifier('cs_8al', { melee: 0.2 });
    s.setModifier('cs_8al', { melee: 0 });
    expect(s.modifiers.value).toEqual({});
  });

  it('a bad modifier shows as a preview problem and the round is not fought', () => {
    const s = admin();
    s.setModifier('cs_8al', { fire: 2 });
    expect(s.preview.value.error).toMatch(/between -1 and 1/);
    expect(s.resolve()).toMatch(/between -1 and 1/);
    expect(s.battle.value!.round).toBe(0);
  });
});

describe('reconciling players\' orders', () => {
  const files = () => {
    const union = player(0);
    union.setOrder('us_1mn', { mode: 'ranged', target: 'cs_8al' });
    const confed = player(1);
    confed.setOrder('cs_8al', { mode: 'melee', target: 'us_1mn' });
    return {
      union: { name: 'union.json', text: union.planDownload().text },
      confed: { name: 'confed.json', text: confed.planDownload().text },
    };
  };

  it('shows which side sent orders, where each order came from, and who has none', () => {
    const s = admin();
    const { union } = files();
    expect(s.plansLoaded.value).toEqual({});
    expect(s.loadPlans([union])).toEqual([]);
    expect(s.plansLoaded.value).toEqual({ 0: 'union.json' });
    expect(s.orderSources.value.us_1mn).toBe('union.json');
    expect(s.orderSources.value.us_15ma).toBe('union.json');   // a hold order from the file is still an order
    expect(s.withoutOrders.value.map((u) => u.uid)).toEqual(['cs_8al', 'cs_10al', 'cs_11al', 'cs_bat']);
  });

  it('an admin change to a player\'s order is marked as the admin\'s; a new round starts afresh', () => {
    const s = admin();
    const { union, confed } = files();
    s.loadPlans([union, confed]);
    expect(s.withoutOrders.value).toEqual([]);
    s.setOrder('us_1mn', { target: 'cs_10al' });
    expect(s.orderSources.value.us_1mn).toBe('admin');
    s.setOrder('cs_bat', { mode: 'ranged', target: 'us_bat' });
    expect(s.orderSources.value.cs_bat).toBe('admin');
    expect(s.resolve()).toBeNull();
    expect([s.plansLoaded.value, s.orderSources.value]).toEqual([{}, {}]);
  });

  it('loading a side again replaces its file', () => {
    const s = admin();
    const { union } = files();
    s.loadPlans([union]);
    s.loadPlans([{ ...union, name: 'union-2.json' }]);
    expect(s.plansLoaded.value).toEqual({ 0: 'union-2.json' });
    expect(s.orderSources.value.us_1mn).toBe('union-2.json');
  });

  it('opening another battle forgets the loaded files', () => {
    const s = admin();
    s.loadPlans([files().union]);
    s.open(s.battle.value!.toJson());
    expect([s.plansLoaded.value, s.orderSources.value]).toEqual([{}, {}]);
  });
});
