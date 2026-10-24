import { describe, expect, it } from 'vitest';

import { createStore, modeFromUrl, PLAN_FORMAT } from './store';

const player = (side: 0 | 1 = 0) => {
  const s = createStore(1863, 'player');
  s.start();
  s.playerSide.value = side;
  return s;
};

describe('mode from the link', () => {
  it.each([['', 'player'], ['?mode=admin', 'admin'], ['?x=1&mode=admin', 'admin'], ['?mode=player', 'player'],
    ['?mode=nonsense', 'player']])('%j -> %s', (search, mode) => {
    expect(modeFromUrl(search)).toBe(mode);
  });

  it('the store defaults to admin (the page passes the mode)', () => {
    expect(createStore(1).mode.value).toBe('admin');
  });
});

describe('player mode: orders and expectations', () => {
  it('enemy units return fire on whoever targets them, unless the player says otherwise', () => {
    const s = player(0);
    s.setOrder('us_1mn', { mode: 'ranged', target: 'cs_8al' });
    s.setOrder('us_bat', { mode: 'melee', target: 'cs_bat' });
    const eff = s.effectiveOrders.value;
    expect(eff.cs_8al).toEqual({ mode: 'ranged', target: 'us_1mn', ammo: null, on_break: 'keep' });
    expect(eff.cs_bat).toEqual({ mode: 'ranged', target: 'us_bat', ammo: 'round_shot', on_break: 'keep' });
    expect(eff.cs_10al.mode).toBe('idle');
    // the player's expectation for an enemy unit is not a real order
    s.setOrder('cs_10al', { mode: 'ranged', target: 'us_15ma' });
    expect(s.effectiveOrders.value.cs_10al).toMatchObject({ mode: 'ranged', target: 'us_15ma' });
    expect(s.orders.value.cs_10al.mode).toBe('idle');
    expect(s.isAssumed('cs_10al')).toBe(true);
    s.resetAssumption('cs_10al');
    expect(s.isAssumed('cs_10al')).toBe(false);
    expect(s.effectiveOrders.value.cs_10al.mode).toBe('idle');
  });

  it("a melee-only enemy can't return fire, so it holds", () => {
    const s = createStore(1863, 'player');
    s.updateUnit('cs_8al', { stats: '5/6/0/1' });
    s.start();
    s.setOrder('us_1mn', { mode: 'ranged', target: 'cs_8al' });
    expect(s.effectiveOrders.value.cs_8al.mode).toBe('idle');
  });

  it('the other side is the enemy when the player commands side 1', () => {
    const s = player(1);
    s.setOrder('cs_8al', { mode: 'ranged', target: 'us_1mn' });
    expect(s.orders.value.cs_8al.mode).toBe('ranged');
    expect(s.effectiveOrders.value.us_1mn).toMatchObject({ mode: 'ranged', target: 'cs_8al' });
  });

  it('the preview uses the expectations; admin mode uses the real orders only', () => {
    const s = player(0);
    s.setOrder('us_1mn', { mode: 'ranged', target: 'cs_8al' });
    expect(s.preview.value.arrows.map((a) => a.attacker)).toEqual(['cs_8al', 'us_1mn']);
    s.mode.value = 'admin';
    expect(s.preview.value.arrows.map((a) => a.attacker)).toEqual(['us_1mn']);
    expect(s.effectiveOrders.value).toEqual(s.orders.value);
  });

  it('players can not fight rounds', () => {
    const s = player(0);
    expect(s.resolve()).toBe('Rounds are fought in admin mode.');
    expect(s.history.value).toEqual([]);
  });
});

describe('player mode: the estimate', () => {
  it('estimates the next round with the effective orders, and knows when it is out of date', () => {
    const s = player(0);
    expect(s.estimate.value).toBeNull();
    s.setOrder('us_1mn', { mode: 'ranged', target: 'cs_8al' });
    s.runEstimate(20);
    const est = s.estimate.value!;
    expect(est.result.runs).toBe(20);
    expect(est.result.units.us_1mn.losses.p90).toBeGreaterThan(0);        // the 8th Alabama is expected to reply
    expect(est.current).toBe(true);
    s.duration.value = 30;
    expect(s.estimate.value!.current).toBe(false);
    s.duration.value = 60;
    expect(s.estimate.value!.current).toBe(true);
    s.setOrder('us_15ma', { mode: 'ranged', target: 'cs_10al' });
    expect(s.estimate.value!.current).toBe(false);
  });

  it('runs 200 times by default', () => {
    const s = player(0);
    s.runEstimate();
    expect(s.estimate.value!.result.runs).toBe(200);
  });
});

describe('orders files', () => {
  it('a player downloads their side: orders for units that can act, and where their units stand', () => {
    const s = player(0);
    s.setOrder('us_1mn', { mode: 'ranged', target: 'cs_8al' });
    s.moveUnit('us_1mn', { x: 500, y: 850 });
    s.setOrder('cs_8al', { mode: 'melee', target: 'us_1mn' });            // an expectation: not in the file
    const file = s.planDownload();
    expect(file.name).toBe('orders-1863-round-1-Union.json');
    const plan = JSON.parse(file.text);
    expect(plan).toMatchObject({ format: PLAN_FORMAT, version: 1, battle: { seed: 1863, round: 1, time: 0 }, side: 0,
      side_name: 'Union' });
    expect(Object.keys(plan.orders)).toEqual(['us_1mn', 'us_15ma', 'us_bat']);
    expect(plan.orders.us_1mn).toEqual({ target: 'cs_8al', mode: 'ranged', on_break: 'keep' });
    expect(plan.orders.us_15ma).toEqual({ mode: 'idle' });
    expect(plan.positions.us_1mn).toEqual({ x: 500, y: 850, facing: 0 });
    expect(Object.keys(plan.positions)).toEqual(['us_1mn', 'us_15ma', 'us_bat']);
  });

  it('the admin loads both sides\' files: orders merge and moves apply', () => {
    const union = player(0);
    union.setOrder('us_1mn', { mode: 'ranged', target: 'cs_8al' });
    union.moveUnit('us_1mn', { x: 500, y: 850 });
    union.faceUnit('us_1mn', 30);
    const confed = player(1);
    confed.setOrder('cs_8al', { mode: 'melee', target: 'us_1mn', on_break: 'pursue' });
    const admin = createStore(1863);
    admin.start();
    expect(admin.loadPlans([
      { name: 'u.json', text: union.planDownload().text }, { name: 'c.json', text: confed.planDownload().text },
    ])).toEqual([]);
    expect(admin.orders.value.us_1mn).toMatchObject({ mode: 'ranged', target: 'cs_8al' });
    expect(admin.orders.value.cs_8al).toMatchObject({ mode: 'melee', on_break: 'pursue' });
    expect(admin.mapUnits.value[0]).toMatchObject({ x: 500, y: 850, facing: 30 });
    expect(admin.resolve()).toBeNull();
  });

  it('a move without a facing (an older orders file) keeps the unit\'s facing', () => {
    const union = player(0);
    const plan = JSON.parse(union.planDownload().text);
    plan.positions = { us_1mn: { x: 450, y: 850 } };
    const admin = createStore(1863);
    admin.start();
    admin.faceUnit('us_1mn', 20);
    expect(admin.loadPlans([{ name: 'u.json', text: JSON.stringify(plan) }])).toEqual([]);
    expect(admin.mapUnits.value[0]).toMatchObject({ x: 450, y: 850, facing: 20 });
  });

  it('refuses files for another battle, round or side, or not orders at all, naming the file', () => {
    const s = player(0);
    const plan = JSON.parse(s.planDownload().text);
    const admin = createStore(1863);
    admin.start();
    const bad = (change: (p: Record<string, unknown>) => void) => {
      const p = structuredClone(plan);
      change(p);
      return { name: 'f.json', text: JSON.stringify(p) };
    };
    const problems = admin.loadPlans([
      { name: 'x.json', text: 'nope' },
      { name: 'y.json', text: '{"format": "other"}' },
      bad((p) => { p.version = 2; }),
      bad((p) => { (p.battle as Record<string, number>).seed = 1; }),
      bad((p) => { (p.battle as Record<string, number>).round = 3; }),
      bad((p) => { p.orders = { cs_8al: { mode: 'idle' } }; }),
      bad((p) => { p.positions = { nobody: { x: 1, y: 1 } }; }),
    ]);
    expect(problems).toEqual([
      expect.stringMatching(/^x\.json: not valid JSON/),
      'y.json: not an orders file.',
      'f.json: unsupported orders file version 2 (expected 1).',
      'f.json: these orders are for another battle (seed 1, this one 1863).',
      'f.json: these orders are for round 3; the next round is 1.',
      "f.json: cs_8al is not on Union's side.",
      'f.json: the orders name an unknown unit nobody.',
    ]);
    expect(Object.values(admin.orders.value).every((o) => o.mode === 'idle')).toBe(true);
  });

  it('refuses a unit ordered in two files', () => {
    const s = player(0);
    const text = s.planDownload().text;
    const admin = createStore(1863);
    admin.start();
    expect(admin.loadPlans([{ name: 'a.json', text }, { name: 'b.json', text }]))
      .toEqual(['b.json: us_1mn has orders in two files.']);
  });
});

describe('player mode: edge cases', () => {
  it('a broken enemy unit is expected to hold', () => {
    const s = player(0);
    s.battle.value!.units.get('cs_8al')!.morale.forceBreak();
    s.touch();
    s.setOrder('us_1mn', { mode: 'ranged', target: 'cs_8al' });
    expect(s.effectiveOrders.value.cs_8al.mode).toBe('idle');
  });

  it('an orders file without moves loads (as one written by hand)', () => {
    const admin = createStore(1863);
    admin.start();
    const plan = { format: PLAN_FORMAT, version: 1, battle: { seed: 1863, round: 1, time: 0 }, side: 0,
      orders: { us_1mn: { target: 'cs_8al', mode: 'ranged' } } };
    expect(admin.loadPlans([{ name: 'hand.json', text: JSON.stringify(plan) }])).toEqual([]);
    expect(admin.orders.value.us_1mn.mode).toBe('ranged');
  });
});

describe('the orders file format is shared with Python', () => {
  it('the client still writes test_cases/parity/plan_example.json exactly', async () => {
    const battles = (await import('../../../test_cases/parity/battles.json')).default;
    const expected = (await import('../../../test_cases/parity/plan_example.json')).default;
    const c = battles.cases.find((x) => x.name === 'example_ridge' && x.seed === 1)!;
    const s = createStore(1, 'player');
    s.open(JSON.stringify(c.start));
    s.playerSide.value = 1;
    s.setOrder('cs_8al', { mode: 'melee', target: 'us_1mn', on_break: 'pursue' });
    s.setOrder('cs_bat', { mode: 'ranged', target: 'us_bat' });
    s.setOrder('cs_bat', { ammo: 'shell' });
    s.moveUnit('cs_8al', { x: 700, y: 520 });
    s.faceUnit('cs_8al', 200);
    expect(JSON.parse(s.planDownload().text)).toEqual(expected);
  });
});
