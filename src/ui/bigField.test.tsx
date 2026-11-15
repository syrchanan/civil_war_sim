// @vitest-environment jsdom
// Large battles: the field's size per battle, zooming and moving the map, and the generated seventy-a-side armies.
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/preact';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { DEFAULT_FIELD, fieldOf, validatePlan } from '../engine';
import { App } from './App';
import { bigArmies, groupByOrg, UNATTACHED, unitsIn } from './bigBattle';
import { blockSize, defaultZoneDepth, FIELD_PRESETS, linesNeeded, suggestField, zoneBand } from './field';
import { SETUP_VERSION } from './setupFile';
import { createStore, fitInField, MIN_VIEW, type Store } from './store';
import { generateTerrain } from './terrainGen';

beforeEach(() => localStorage.clear());
afterEach(cleanup);

const MEDIUM = { width: 4000, height: 2400 };
const LARGE = { width: 8000, height: 4800 };

describe('the field in the plan', () => {
  it('is kept when not the default, and left out when it is', () => {
    expect(validatePlan({ field: MEDIUM }).field).toEqual(MEDIUM);
    expect(validatePlan({ field: { ...DEFAULT_FIELD } }).field).toBeUndefined();
    expect(validatePlan({ field: null }).field).toBeUndefined();
    expect(fieldOf(validatePlan({}))).toEqual(DEFAULT_FIELD);
    expect(fieldOf(validatePlan({ field: LARGE }))).toEqual(LARGE);
  });

  it('must be a width and a height, each 500 to 20000 yards', () => {
    for (const field of [3, [1, 2], { width: 4000 }, { width: 4000, height: 2400, depth: 1 }, { width: 400, height: 2400 },
      { width: 4000, height: 30000 }, { width: '4000', height: 2400 }]) {
      expect(() => validatePlan({ field })).toThrow('The field must be {width, height} in yards, each 500 to 20000.');
    }
  });
});

describe('field helpers', () => {
  it('zones and the default depth follow the field', () => {
    expect(defaultZoneDepth(DEFAULT_FIELD)).toBe(360);
    expect(defaultZoneDepth(LARGE)).toBe(1440);
    expect(zoneBand(0, 1440, LARGE)).toEqual({ x: 0, y: 3360, w: 8000, h: 1440 });
  });

  it('how many lines a side stands in, and the field suggested for two armies', () => {
    expect(linesNeeded([], DEFAULT_FIELD)).toBe(0);
    expect(linesNeeded([800, 800], DEFAULT_FIELD)).toBe(1); // 1,800 yd of room: 800 + 60 + 800
    expect(linesNeeded([800, 800, 800], DEFAULT_FIELD)).toBe(2);
    expect(suggestField([[100, 100], [100]])).toBe('Small');
    const wide = Array.from({ length: 8 }, () => 1000); // Medium: three a line (3,800 yd of room)
    expect(suggestField([wide, [100]])).toBe('Medium');
    expect(suggestField([Array.from({ length: 20 }, () => 1000), [100]])).toBe('Large'); // seven a line
    expect(suggestField([Array.from({ length: 200 }, () => 1000), [100]])).toBe('Large'); // none fits: the largest
  });

  it('a large field\'s ground keeps about a hundred cells across', () => {
    const t = generateTerrain('hills', 7, LARGE);
    expect([t.cell, t.columns, t.rows]).toEqual([80, 100, 60]);
    expect(generateTerrain('hills', 7).cell).toBe(20);
  });
});

describe('store: the field', () => {
  it('a new battle\'s field: zones at their default depth, saved in the plan and the setup file', () => {
    const s = createStore(1863);
    s.moveUnit(s.units.value[0].id, { x: 10, y: 10 });
    s.setField(MEDIUM);
    expect(s.field.value).toEqual(MEDIUM);
    expect(s.zoneDepth.value).toEqual([720, 720]);
    expect(s.mapUnits.value[0].y).toBeGreaterThan(1000); // drawn up afresh in the bigger zones
    s.approve(0);
    s.approve(1);
    expect(s.openDeployment()).toEqual([]);
    expect(s.battle.value!.plan.field).toEqual(MEDIUM);
    expect(s.field.value).toEqual(MEDIUM);

    const setup = JSON.parse(s.setupDownload().text);
    expect(setup.field).toEqual(MEDIUM);
    const t = createStore(1);
    expect(t.open(JSON.stringify(setup))).toBeNull();
    expect(t.fieldSize.value).toEqual(MEDIUM);
    expect(t.open(JSON.stringify({ ...setup, field: undefined }))).toBeNull(); // an older setup: the default
    expect(t.fieldSize.value).toEqual(DEFAULT_FIELD);
    expect(t.open(JSON.stringify({ ...setup, field: { width: 1 } })))
      .toBe('The field must be {width, height} in yards, each 500 to 20000.');
    expect(setup.version).toBe(SETUP_VERSION);

    // the battle file carries it
    const u = createStore(2);
    expect(u.open(s.download().text)).toBeNull();
    expect(u.field.value).toEqual(MEDIUM);
  });

  it('the zone depth can be up to half the field', () => {
    const s = createStore(1863);
    s.setField(LARGE);
    s.setZoneDepth(0, 2400);
    expect(s.setupProblems()).toEqual([]);
    s.setZoneDepth(0, 2401);
    expect(s.setupProblems()).toEqual(["Union's zone must be 1 to 2400 yards deep."]);
  });
});

describe('store: the map view', () => {
  it('a view is kept inside the field, no narrower than a brigade, in the field\'s shape', () => {
    // about the same centre
    expect(fitInField({ x: -50, y: -50, w: 100, h: 999 }, DEFAULT_FIELD)).toEqual({ x: 0, y: 329.5, w: MIN_VIEW, h: 240 });
    expect(fitInField({ x: 1900, y: 1100, w: 500, h: 300 }, DEFAULT_FIELD)).toEqual({ x: 1500, y: 900, w: 500, h: 300 });
    expect(fitInField({ x: 0, y: 0, w: 9999, h: 1 }, DEFAULT_FIELD)).toEqual({ x: 0, y: 0, w: 2000, h: 1200 });
  });

  it('zooms about a point or the middle, moves, centres on a unit, and shows the whole field again', () => {
    const s = createStore(1863);
    expect(s.view.value).toEqual({ x: 0, y: 0, w: 2000, h: 1200 });
    s.zoomMap(2);
    expect(s.view.value).toEqual({ x: 500, y: 300, w: 1000, h: 600 });
    s.zoomMap(2, { x: 500, y: 300 }); // the corner stays put
    expect(s.view.value).toEqual({ x: 500, y: 300, w: 500, h: 300 });
    s.panMap(100, -50);
    expect(s.view.value).toEqual({ x: 600, y: 250, w: 500, h: 300 });
    s.centreMap({ x: 1000, y: 600 }); // already zoomed in: the same width
    expect(s.view.value).toEqual({ x: 750, y: 450, w: 500, h: 300 });
    s.fitMap();
    s.centreMap({ x: 1000, y: 600 }); // the whole field shown: closer in
    expect(s.view.value).toEqual({ x: 400, y: 240, w: 1200, h: 720 });
    s.setField(MEDIUM); // a new field shows whole
    expect(s.view.value).toEqual({ x: 0, y: 0, w: 4000, h: 2400 });
  });
});

describe('the map, zoomed', () => {
  const rect = { left: 0, top: 0, width: 1000, height: 600, right: 1000, bottom: 600, x: 0, y: 0, toJSON: () => ({}) };
  const svg = () => screen.getByRole('img', { name: /^Battlefield/ }) as unknown as SVGSVGElement;
  function shown(s: Store) {
    render(<App store={s} />);
    svg().getBoundingClientRect = () => rect as DOMRect;
  }

  it('the buttons zoom in and out and show the whole field', () => {
    const s = createStore(1863);
    shown(s);
    const zoom = within(screen.getByRole('group', { name: 'Zoom' }));
    expect((zoom.getByRole('button', { name: 'Zoom out' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(zoom.getByRole('button', { name: 'Zoom in' }));
    expect(svg().getAttribute('viewBox')).toBe('333.33333333333337 200 1333.3333333333333 800');
    fireEvent.click(zoom.getByRole('button', { name: 'Zoom out' }));
    expect(s.view.value.w).toBeCloseTo(2000);
    fireEvent.click(zoom.getByRole('button', { name: 'Zoom in' }));
    fireEvent.click(zoom.getByRole('button', { name: 'Show the whole field' }));
    expect(svg().getAttribute('viewBox')).toBe('0 0 2000 1200');
  });

  it('the wheel zooms about the pointer; dragging open ground moves the map', () => {
    const s = createStore(1863);
    shown(s);
    fireEvent.wheel(svg(), { deltaY: -100, clientX: 0, clientY: 0 });
    expect(s.view.value).toEqual({ x: 0, y: 0, w: 1600, h: 960 });
    fireEvent.wheel(svg(), { deltaY: 100, clientX: 0, clientY: 0 });
    expect(s.view.value.w).toBeCloseTo(2000);
    act(() => s.zoomMap(4));
    const ground = document.querySelector('rect.field')!;
    fireEvent.pointerDown(ground, { clientX: 500, clientY: 300, pointerId: 1 });
    fireEvent.pointerMove(ground, { clientX: 500, clientY: 300, pointerId: 1 }); // not moved yet
    fireEvent.pointerMove(ground, { clientX: 400, clientY: 300, pointerId: 1 });
    expect(s.view.value.x).toBeCloseTo(750 + 50); // 100 px is 50 yd at this zoom
    fireEvent.pointerUp(ground, { pointerId: 1 });
    fireEvent.pointerMove(ground, { clientX: 0, clientY: 0, pointerId: 1 }); // released: nothing
    expect(s.view.value.x).toBeCloseTo(800);
  });

  it('dragging a unit moves the unit, not the map; symbols and labels keep their size on screen', () => {
    const s = createStore(1863);
    s.setField(LARGE);
    shown(s);
    expect(svg().style.getPropertyValue('--k')).toBe('4');
    const block = screen.getByRole('button', { name: /^1st Minnesota,/ });
    expect(block.querySelector('g[transform="scale(4)"]')).not.toBeNull();
    const before = s.view.value;
    fireEvent.pointerDown(block, { clientX: 100, clientY: 100, pointerId: 1 });
    fireEvent.pointerMove(block, { clientX: 120, clientY: 100, pointerId: 1 });
    expect(s.view.value).toEqual(before);
    expect(document.querySelector('.scale-bar text')!.textContent).toBe('2,000 yards');
  });

  it('the target menu stands by its target wherever the map is', () => {
    const s = createStore(1863);
    s.start();
    shown(s);
    act(() => {
      s.zoomMap(2);
      s.clickUnit('us_1mn');
      s.clickUnit('cs_8al');
    });
    const at = s.mapUnits.value.find((u) => u.uid === 'cs_8al')!;
    const menu = screen.getByRole('dialog') as HTMLElement;
    expect(menu.style.left).toBe(`${((at.x - 500) / 1000) * 100}%`);
  });
});

describe('the field in setup', () => {
  const panel = () => within(document.getElementById('panel-setup')!);

  it('a preset or a custom size, and the size these armies need', () => {
    const s = createStore(1863);
    render(<App store={s} />);
    expect(panel().getByText('Right for these armies: each side draws up in three lines or fewer.')).toBeTruthy();
    fireEvent.change(panel().getByLabelText('Field size'), { target: { value: 'Large' } });
    expect(s.fieldSize.value).toEqual(LARGE);
    expect(panel().getByText(/^For these armies: Small/)).toBeTruthy();
    fireEvent.click(panel().getByRole('button', { name: 'Use Small' }));
    expect(s.fieldSize.value).toEqual(DEFAULT_FIELD);
    fireEvent.change(panel().getByLabelText('Field size'), { target: { value: 'Custom' } });
    expect(s.fieldSize.value).toEqual(DEFAULT_FIELD); // the same size, now to edit
    fireEvent.change(panel().getByLabelText('Width (yd)'), { target: { value: '3000' } });
    fireEvent.change(panel().getByLabelText('Height (yd)'), { target: { value: '1800' } });
    expect(s.fieldSize.value).toEqual({ width: 3000, height: 1800 });
    fireEvent.change(panel().getByLabelText('Width (yd)'), { target: { value: '' } });
    fireEvent.change(panel().getByLabelText('Height (yd)'), { target: { value: '' } });
    expect(s.fieldSize.value).toEqual({ width: 3000, height: 1800 }); // emptied: kept
    fireEvent.change(panel().getByLabelText('Field size'), { target: { value: 'Medium' } });
    expect(s.fieldSize.value).toEqual(MEDIUM);
    expect(panel().queryByLabelText('Width (yd)')).toBeNull();
  });

  it('a size from a setup file that is no preset shows as custom', () => {
    const s = createStore(1863);
    s.setField({ width: 3000, height: 1800 });
    render(<App store={s} />);
    expect((panel().getByLabelText('Field size') as HTMLSelectElement).value).toBe('Custom');
    expect((panel().getByLabelText('Width (yd)') as HTMLInputElement).value).toBe('3000');
  });

  it('seventy regiments a side suggest a larger field', () => {
    const s = createStore(1863);
    const big = bigArmies(7);
    s.units.value = big.units;
    s.units.value = s.units.value.map((u, i) => (i === 0 ? { ...u, size: NaN } : u)); // an unreadable size counts as none
    render(<App store={s} />);
    const want = suggestField([0, 1].map((side) => big.units.filter((u) => u.side === side)
      .map((u) => blockSize(u.type, u.size, u.size, u.guns).width)) as [number[], number[]]);
    expect(want).not.toBe('Small');
    fireEvent.click(panel().getByRole('button', { name: `Use ${want}` }));
    expect(s.fieldSize.value).toEqual(FIELD_PRESETS.find(([n]) => n === want)![1]);
  });
});

describe('seventy regiments a side', () => {
  it('the same armies for the same seed: a corps of three divisions, cavalry and batteries, every unit organised', () => {
    const a = bigArmies(7);
    expect(bigArmies(7)).toEqual(a);
    expect(bigArmies(8)).not.toEqual(a);
    for (const side of [0, 1]) {
      const units = a.units.filter((u) => u.side === side);
      expect(units).toHaveLength(70);
      expect(units.every((u) => u.org?.corps && u.org.division && u.org.brigade)).toBe(true);
      expect(new Set(units.map((u) => u.name)).size).toBe(70);
      expect(units.filter((u) => u.type === 'art')).toHaveLength(6);
      expect(units.filter((u) => u.type === 'cav')).toHaveLength(4);
    }
    expect(new Set(a.units.map((u) => u.id)).size).toBe(140);
    expect(a.units.find((u) => u.side === 0)!.name).toMatch(/^\d+(st|nd|rd|th) /);
    const s = createStore(1863);
    s.units.value = a.units;
    expect(s.start()).toEqual([]); // every unit can be built
  });

  it('grouped corps › division › brigade, in the order first seen; units with no org are unattached', () => {
    const units = [
      { n: 'a', org: { corps: 'I', division: 'D1', brigade: 'B1' } },
      { n: 'b', org: { corps: 'I', division: 'D2', brigade: 'B3' } },
      { n: 'c', org: { corps: 'I', division: 'D1', brigade: 'B1' } },
      { n: 'd', org: { corps: 'I', division: 'D1', brigade: 'B2' } },
      { n: 'e', org: undefined },
      { n: 'f', org: { brigade: 'B9' } },
    ];
    const groups = groupByOrg(units, (u) => u.org);
    expect(groups.map((g) => [g.level, g.name])).toEqual([['corps', 'I'], ['corps', UNATTACHED]]);
    const d1 = groups[0].groups[0];
    expect([d1.level, d1.name, d1.groups.map((g) => g.name)]).toEqual(['division', 'D1', ['B1', 'B2']]);
    expect(d1.groups[0].units.map((u) => u.n)).toEqual(['a', 'c']);
    expect(unitsIn(groups[0]).map((u) => u.n)).toEqual(['a', 'c', 'd', 'b']);
    const loose = groups[1].groups[0];
    expect([loose.name, loose.groups.map((g) => g.name)]).toEqual([UNATTACHED, [UNATTACHED, 'B9']]);
  });
});
