// @vitest-environment jsdom
// Setting up the battle: the day's plan, the deployment zones, opening round 0, and the setup file.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/preact';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { inside } from '../engine';
import { App } from './App';
import { DEFAULT_ZONE_DEPTH, defaultLayout, FIELD, zoneBand } from './field';
import { daySpan } from './SetupPanel';
import { SETUP_FORMAT, SETUP_VERSION } from './setupFile';
import { createStore } from './store';

beforeEach(() => localStorage.clear());

/** Both armies approved, as the admin does before opening round 0. */
function approved(s: ReturnType<typeof createStore>) {
  s.approve(0);
  s.approve(1);
  return s;
}
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('zones and the layout', () => {
  it('a band along each side\'s own edge', () => {
    expect(zoneBand(0, 300)).toEqual({ x: 0, y: FIELD.height - 300, w: FIELD.width, h: 300 });
    expect(zoneBand(1, 300)).toEqual({ x: 0, y: 0, w: FIELD.width, h: 300 });
  });

  it('the default zones draw the armies up where the zoneless layout did', () => {
    const units = [{ id: 'a', side: 0 as const, width: 200 }, { id: 'b', side: 1 as const, width: 200 }];
    const deep = { 0: zoneBand(0, DEFAULT_ZONE_DEPTH), 1: zoneBand(1, DEFAULT_ZONE_DEPTH) };
    expect(defaultLayout(units, deep)).toEqual(defaultLayout(units));
    expect(defaultLayout(units)).toEqual({ a: { x: 1000, y: 900 }, b: { x: 1000, y: 300 } });
  });

  it('inside a narrow, shallow zone: centred on it, the first line half way in', () => {
    const units = [{ id: 'a', side: 0 as const, width: 50 }, { id: 'b', side: 0 as const, width: 50 }];
    const layout = defaultLayout(units, { 0: { x: 100, y: 1000, w: 150, h: 40 } });
    // too narrow for both side by side: the second wraps behind the first
    expect(layout).toEqual({ a: { x: 175, y: 1020 }, b: { x: 175, y: 1140 } });
  });
});

describe('the day', () => {
  it('spans the rounds planned from the start clock', () => {
    expect(daySpan('13:00', 60, 4)).toBe('1:00 pm to 5:00 pm');
    expect(daySpan(null, 60, 4)).toBeNull();
    expect(daySpan('13:00', 60, null)).toBeNull();
    expect(daySpan('13:00', NaN, 4)).toBeNull();
  });
});

describe('store: opening round 0', () => {
  it('builds the battle deploying, with the plan, the zones and the name; each unit inside its zone', () => {
    const s = createStore(1863);
    s.battleName.value = '  Example Ridge ';
    s.setZoneDepth(1, 200);
    s.moveUnit(s.units.value[0].id, { x: 50, y: 50 }); // placed by hand: drawn up afresh
    approved(s);
    expect(s.openDeployment()).toEqual([]);
    const b = s.battle.value!;
    expect(b.meta.name).toBe('Example Ridge');
    expect(b.plan).toEqual({
      rounds_planned: 4, start_clock: '13:00', phase: 'deployment',
      zones: { 0: zoneBand(0, DEFAULT_ZONE_DEPTH), 1: zoneBand(1, 200) },
    });
    expect(b.deploymentProblems()).toEqual([]);
    for (const u of b.units.values()) {
      expect(inside(b.plan.zones[String(u.side)], u.regiment.position!.x, u.regiment.position!.y)).toBe(true);
    }
  });

  it('starting at once keeps no zones, and no name when none was given', () => {
    const s = createStore(1863);
    s.roundsPlanned.value = null;
    expect(s.start()).toEqual([]);
    expect(s.battle.value!.plan).toEqual({ rounds_planned: null, start_clock: '13:00', phase: 'battle', zones: {} });
    expect(s.battle.value!.meta.name).toBeUndefined();
  });

  it('names what stops it, and keeps the units where they were placed', () => {
    const s = createStore(1863);
    const uid = s.units.value[0].id;
    s.moveUnit(uid, { x: 50, y: 50 });
    s.seed.value = -1;
    s.duration.value = 0;
    s.roundsPlanned.value = 0;
    s.setZoneDepth(0, 0);
    s.setZoneDepth(1, FIELD.height);
    s.updateUnit(uid, { size: 0 });
    s.updateUnit(s.units.value[1].id, { stats: 'x/5/0/0' });
    s.units.value = s.units.value.filter((u) => u.side === 0);
    expect(s.openDeployment()).toEqual([
      `${s.units.value[0].name}: men must be a whole number, 1 or more.`,
      expect.stringMatching(new RegExp(`^${s.units.value[1].name}: `)),
      'Confederate has no units.',
      `The seed must be a whole number from 0 to ${2 ** 32 - 1}.`,
      'The round length must be more than 0 minutes.',
      'Rounds planned must be a whole number, 1 or more.',
      `Union's zone must be 1 to ${FIELD.height / 2} yards deep.`,
      `Confederate's zone must be 1 to ${FIELD.height / 2} yards deep.`,
      "Union's army has not been approved.",
      "Confederate's army has not been approved.",
    ]);
    expect(s.battle.value).toBeNull();
    expect(s.mapUnits.value.find((u) => u.uid === uid)).toMatchObject({ x: 50, y: 50 });
  });

  it('artillery without a whole number of guns', () => {
    const s = createStore(1863);
    const battery = s.units.value.find((u) => u.type === 'art')!;
    s.updateUnit(battery.id, { guns: 1.5 });
    expect(s.draftProblems(battery.side)).toEqual([`${battery.name}: guns must be a whole number, 0 or more.`]);
  });
});

describe('store: the setup file', () => {
  const setupOf = (s: ReturnType<typeof createStore>) => JSON.parse(s.setupDownload().text);

  it('saves the day, the ground, the zones and the armies, and opens again', () => {
    const s = createStore(1863);
    s.battleName.value = 'The Battle of Example Ridge!';
    s.terrainPreset.value = 'hills';
    s.duration.value = 45;
    s.roundsPlanned.value = 6;
    s.startClock.value = '09:30';
    s.setZoneDepth(0, 250);
    s.updateUnit(s.units.value[0].id, { org: { brigade: 'Harrow' } });
    const file = s.setupDownload();
    expect(file.name).toBe('setup-the-battle-of-example-ridge.json');
    const data = JSON.parse(file.text);
    expect(data).toMatchObject({
      format: SETUP_FORMAT, version: SETUP_VERSION, name: 'The Battle of Example Ridge!', seed: 1863, ground: 'hills',
      round_length: 45, rounds_planned: 6, start_clock: '09:30', zone_depth: [250, DEFAULT_ZONE_DEPTH],
    });

    const t = createStore(1);
    t.start(); // a battle open is dropped
    expect(t.open(file.text)).toBeNull();
    expect(t.battle.value).toBeNull();
    expect([t.battleName.value, t.terrainPreset.value, t.duration.value, t.roundsPlanned.value, t.startClock.value,
      t.zoneDepth.value, t.seed.value]).toEqual(['The Battle of Example Ridge!', 'hills', 45, 6, '09:30',
      [250, DEFAULT_ZONE_DEPTH], 1863]);
    expect(t.units.value).toEqual(s.units.value.map((u) => ({ ...u, org: u.org ?? {} })));
    expect(t.sides.value).toEqual(s.sides.value);
  });

  it('an unnamed battle, open-ended with no clock, on an unknown ground', () => {
    const s = createStore(1863);
    s.roundsPlanned.value = null;
    s.startClock.value = null;
    expect(s.setupDownload().name).toBe('setup-battle.json');
    const data = { ...setupOf(s), ground: 'swamp' };
    const t = createStore(1);
    expect(t.open(JSON.stringify(data))).toBeNull();
    expect([t.terrainPreset.value, t.roundsPlanned.value, t.startClock.value]).toEqual(['none', null, null]);
  });

  it('says what is wrong with a setup file', () => {
    const s = createStore(1863);
    const good = setupOf(s);
    const unit = good.units[0];
    const cases: [Record<string, unknown>, string][] = [
      [{ version: 9 }, 'Unsupported setup file version 9 (expected 1).'],
      [{ name: 3 }, 'The setup needs a name and two side names.'],
      [{ sides: 'x' }, 'The setup needs a name and two side names.'],
      [{ sides: ['a'] }, 'The setup needs a name and two side names.'],
      [{ sides: ['a', 2] }, 'The setup needs a name and two side names.'],
      [{ seed: 'x' }, 'The setup needs a seed, a ground and a round length.'],
      [{ ground: 1 }, 'The setup needs a seed, a ground and a round length.'],
      [{ round_length: null }, 'The setup needs a seed, a ground and a round length.'],
      [{ rounds_planned: '4' }, 'Rounds planned and the start clock must be a number and a time, or empty.'],
      [{ start_clock: 13 }, 'Rounds planned and the start clock must be a number and a time, or empty.'],
      [{ zone_depth: 300 }, 'The setup needs a zone depth for each side.'],
      [{ zone_depth: [300] }, 'The setup needs a zone depth for each side.'],
      [{ zone_depth: [300, 'x'] }, 'The setup needs a zone depth for each side.'],
      [{ units: {} }, 'The setup needs a list of units.'],
      [{ units: [{ ...unit, id: 1 }] }, 'unit 1 needs an id and a name.'],
      [{ units: [{ ...unit, name: null }] }, 'unit 1 needs an id and a name.'],
      [{ units: [{ ...unit, side: 2 }] }, `${unit.name}: side must be 0 or 1.`],
      [{ units: [{ ...unit, type: 'navy' }] }, `${unit.name}: unknown type navy.`],
      [{ units: [{ ...unit, subtype: 1 }] }, `${unit.name}: subtype, size, stats or guns is not readable.`],
      [{ units: [{ ...unit, size: '1' }] }, `${unit.name}: subtype, size, stats or guns is not readable.`],
      [{ units: [{ ...unit, stats: 5 }] }, `${unit.name}: subtype, size, stats or guns is not readable.`],
      [{ units: [{ ...unit, guns: 'x' }] }, `${unit.name}: subtype, size, stats or guns is not readable.`],
      [{ units: [{ ...unit, org: { regiment: 'x' } }] }, 'Unknown org key(s) regiment; use corps, division, brigade.'],
    ];
    for (const [change, error] of cases) expect(s.open(JSON.stringify({ ...good, ...change }))).toBe(error);
    // a unit without org (written by hand) has none
    const { org: _org, ...bare } = unit;
    expect(s.open(JSON.stringify({ ...good, units: [bare] }))).toBeNull();
    expect(s.units.value[0].org).toEqual({});
  });

  it('a player is told to open their player file instead', () => {
    const admin = createStore(1863);
    const player = createStore(1, 'player');
    expect(player.open(admin.setupDownload().text)).toBe("This is the admin's setup file; open your player file instead.");
  });
});

describe('the setup panel', () => {
  const panel = () => screen.getByRole('complementary', { name: 'Setting up' });

  it('sets the day, the ground and the zones', () => {
    const s = createStore(1863);
    render(<App store={s} />);
    const p = within(panel());
    fireEvent.input(p.getByLabelText('Battle name'), { target: { value: 'Example Ridge' } });
    fireEvent.input(p.getByLabelText('First round starts'), { target: { value: '10:00' } });
    fireEvent.input(p.getByLabelText('Round length (min)'), { target: { value: '90' } });
    expect([s.battleName.value, s.startClock.value, s.duration.value]).toEqual(['Example Ridge', '10:00', 90]);
    expect(p.getByText(/^10:00 am to 4:00 pm; /)).toBeTruthy();
    fireEvent.click(p.getByRole('button', { name: 'One round more' }));
    expect(s.roundsPlanned.value).toBe(5);
    fireEvent.click(p.getByRole('button', { name: 'One round fewer' }));
    expect(s.roundsPlanned.value).toBe(4);
    fireEvent.click(p.getByLabelText('Open-ended'));
    expect(s.roundsPlanned.value).toBeNull();
    expect((p.getByRole('button', { name: 'One round fewer' }) as HTMLButtonElement).disabled).toBe(true);
    expect(p.getByText('open')).toBeTruthy();
    expect(p.getByText(/^more rounds can be added/)).toBeTruthy();
    fireEvent.click(p.getByRole('button', { name: 'One round more' }));
    expect(s.roundsPlanned.value).toBe(1);
    expect((p.getByRole('button', { name: 'One round fewer' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(p.getByLabelText('Open-ended'));
    fireEvent.click(p.getByLabelText('Open-ended'));
    expect(s.roundsPlanned.value).toBe(4);
    fireEvent.input(p.getByLabelText('First round starts'), { target: { value: '' } });
    expect(s.startClock.value).toBeNull();
    fireEvent.input(p.getByLabelText('Union zone depth (yards)'), { target: { value: '250' } });
    fireEvent.input(p.getByLabelText('Confederate zone depth (yards)'), { target: { value: '' } });
    expect(s.zoneDepth.value).toEqual([250, NaN]);
    expect((p.getByLabelText('Confederate zone depth (yards)') as HTMLInputElement).value).toBe('');
  });

  it('shows each army\'s size and problems', () => {
    const s = createStore(1863);
    render(<App store={s} />);
    const items = () => within(panel()).getAllByRole('listitem').map((li) => li.textContent);
    expect(items()[0]).toMatch(/^Union\d+ regiments, [\d,]+ menNot approved yet$/);
    act(() => {
      s.approve(0);
      s.sendBack(1);
    });
    expect(items().map((t) => t.replace(/^.*men/, ''))).toEqual(['✓ Approved', 'Sent back']);
    act(() => {
      s.units.value = [{ ...s.units.value[0], size: NaN }];
    });
    // set directly (no edit through the store), so the review stands
    expect(items()).toEqual(['Union1 regiment, 0 men1 problem to check✓ Approved',
      'Confederate0 regiments, 0 men1 problem to checkSent back']);
    act(() => {
      s.units.value = [{ ...s.units.value[0], size: NaN, stats: 'x/5/0/0' }, { ...s.units.value[0], id: 'x', size: NaN }];
    });
    expect(items()[0]).toBe('Union2 regiments, 0 men2 problems to check✓ Approved');
  });

  it('opens round 0, or names what stops it', () => {
    const s = approved(createStore(1863));
    render(<App store={s} />);
    fireEvent.input(screen.getByLabelText('Seed'), { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: 'Open round 0: deployment' }));
    expect(screen.getByRole('alert').textContent).toMatch(/^The seed must be/);
    fireEvent.input(screen.getByLabelText('Seed'), { target: { value: '7' } });
    fireEvent.click(screen.getByRole('button', { name: 'Open round 0: deployment' }));
    expect(s.battle.value!.plan.phase).toBe('deployment');
    expect(document.querySelector('.standing')!.textContent).toBe('Round 0 · deployment');
    expect(screen.queryByRole('complementary', { name: 'Setting up' })).toBeNull();
  });

  it('saves the setup', async () => {
    const saved: string[] = [];
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:x');
    vi.spyOn(URL, 'revokeObjectURL').mockReturnValue(undefined);
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      saved.push(this.download);
    });
    render(<App store={createStore(1863)} />);
    fireEvent.click(screen.getByRole('button', { name: 'Save setup' }));
    await waitFor(() => expect(saved).toEqual(['setup-battle.json']));
  });

  it('a player is told how to send their army, and can practise', () => {
    const s = createStore(1863, 'player');
    render(<App store={s} />);
    expect(within(panel()).getByText(/^Build your army under Armies/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Open round 0: deployment' })).toBeNull();
    s.seed.value = -1;
    fireEvent.click(screen.getByRole('button', { name: 'Start battle' }));
    expect(screen.getByRole('alert').textContent).toMatch(/^The seed must be/);
    s.seed.value = 1;
    fireEvent.click(screen.getByRole('button', { name: 'Start battle' }));
    expect(s.battle.value).not.toBeNull();
  });
});

describe('the zones on the map', () => {
  const zoneLabels = () => [...document.querySelectorAll('.zone text')].map((t) => t.textContent);

  it('both while setting up and, for the admin, deploying; none once the battle is open', () => {
    const s = createStore(1863);
    render(<App store={s} />);
    expect(zoneLabels()).toEqual(['Union deployment zone', 'Confederate deployment zone']);
    act(() => {
      approved(s).openDeployment();
    });
    expect(zoneLabels()).toEqual(['Union deployment zone', 'Confederate deployment zone']);
    act(() => {
      s.battle.value!.openBattle();
      s.touch();
    });
    expect(zoneLabels()).toEqual([]);
  });

  it('a player deploying sees only their own zone', () => {
    const admin = approved(createStore(1863));
    admin.openDeployment();
    const player = createStore(1, 'player');
    player.open(admin.playerFileDownload(1).text);
    render(<App store={player} />);
    expect(zoneLabels()).toEqual(['Confederate deployment zone']);
  });
});

describe('the army tables', () => {
  it('give each unit its corps, division and brigade', () => {
    const s = createStore(1863);
    render(<App store={s} />);
    const name = s.units.value[0].name;
    fireEvent.input(screen.getByLabelText(`${name} brigade`), { target: { value: 'Harrow' } });
    fireEvent.input(screen.getByLabelText(`${name} corps`), { target: { value: 'II' } });
    expect(s.units.value[0].org).toEqual({ brigade: 'Harrow', corps: 'II' });
    fireEvent.input(screen.getByLabelText(`${name} brigade`), { target: { value: '' } });
    expect(s.units.value[0].org).toEqual({ corps: 'II' });
  });
});
