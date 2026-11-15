// @vitest-environment jsdom
// After the large-battle browser pass: labels that would overlap give way, a brigade's label drags it, formations
// stay in the zone, a brigade charges only what it can reach in the round, and the dispatch comes before the charts.
import { act, cleanup, fireEvent, render, screen } from '@testing-library/preact';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { App } from './App';
import { bigArmies } from './bigBattle';
import { declutter, shiftInto } from './field';
import { createStore, type GroupRef, type Store } from './store';
import { closeRanks } from './testing';

beforeEach(() => localStorage.clear());
afterEach(cleanup);

const HARROW: GroupRef = { side: 0, level: 'brigade', division: 'Gibbon', brigade: 'Harrow' };
const KEMPER: GroupRef = { side: 1, level: 'brigade', division: 'Pickett', brigade: 'Kemper' };

function organised(): Store {
  const s = createStore(1863);
  const org: Record<string, { division: string; brigade: string }> = {
    us_1mn: { division: 'Gibbon', brigade: 'Harrow' }, us_15ma: { division: 'Gibbon', brigade: 'Harrow' },
    cs_8al: { division: 'Pickett', brigade: 'Kemper' }, cs_10al: { division: 'Pickett', brigade: 'Kemper' },
  };
  s.units.value = s.units.value.map((u) => ({ ...u, org: org[u.id] }));
  return s;
}

function bigBattle(): Store {
  const s = createStore(1863);
  s.units.value = bigArmies(7).units;
  s.setField({ width: 8000, height: 4800 });
  s.start();
  return s;
}

const names = () => document.querySelectorAll('.map-unit text .unit-name').length;
const groupLabels = () => document.querySelectorAll('.group text').length;

describe('field: labels and zones', () => {
  it('labels are kept in the order given, unless they overlap one already kept; touching is not overlapping', () => {
    const box = (id: string, x: number, y: number) => ({ id, x, y, w: 10, h: 10 });
    expect([...declutter([box('a', 0, 0), box('b', 5, 5), box('c', 10, 0), box('d', 0, 10)])]).toEqual(['a', 'c', 'd']);
    expect([...declutter([box('b', 5, 5), box('a', 0, 0)])]).toEqual(['b']);
    expect(declutter([]).size).toBe(0);
  });

  it('a formation is shifted as one, the least that brings it inside the zone; too big a way: centred', () => {
    const zone = { x: 0, y: 900, w: 2000, h: 300 };
    const inside = { a: { x: 100, y: 1000 }, b: { x: 300, y: 1100 } };
    expect(shiftInto(inside, zone)).toEqual(inside);
    expect(shiftInto({ a: { x: -50, y: 800 }, b: { x: 100, y: 950 } }, zone))
      .toEqual({ a: { x: 0, y: 900 }, b: { x: 150, y: 1050 } });
    expect(shiftInto({ a: { x: 1900, y: 1150 }, b: { x: 2100, y: 1300 } }, zone))
      .toEqual({ a: { x: 1800, y: 1050 }, b: { x: 2000, y: 1200 } });
    expect(shiftInto({ a: { x: 500, y: 700 }, b: { x: 500, y: 1300 } }, zone)) // 600 deep in a 300 zone
      .toEqual({ a: { x: 500, y: 750 }, b: { x: 500, y: 1350 } });
    expect(shiftInto({}, zone)).toEqual({});
  });
});

describe('the map: labels give way', () => {
  it('the example battle shows every regiment\'s label', () => {
    const s = createStore(1863);
    s.start();
    render(<App store={s} />);
    expect(names()).toBe(s.mapUnits.value.length);
  });

  it('stacked regiments show one label a side; the selected unit\'s is the one shown', () => {
    const s = createStore(1863);
    closeRanks(s);
    s.start();
    render(<App store={s} />);
    expect(names()).toBe(2);
    act(() => s.selectUnit('us_15ma'));
    expect([...document.querySelectorAll('.map-unit text .unit-name')].map((t) => t.textContent)).toContain('15th Massachusetts');
  });

  it('seventy a side: the whole field shows some labels, zoomed in more fit; the same for brigades', () => {
    const s = bigBattle();
    render(<App store={s} />);
    const whole = names();
    expect(whole).toBeGreaterThan(0);
    expect(whole).toBeLessThan(s.mapUnits.value.length);
    act(() => s.zoomMap(4));
    expect(names()).toBeGreaterThan(whole);
    act(() => {
      s.fitMap();
      s.setMapGroups('brigade');
    });
    expect(names()).toBe(0);
    const brigades = groupLabels();
    expect(brigades).toBeGreaterThan(0);
    expect(brigades).toBeLessThan(document.querySelectorAll('.group').length);
    const hidden = [...document.querySelectorAll('.group')].findIndex((g) => g.querySelector('text') === null);
    const unit = s.mapUnits.value.filter((u) => u.side === 0)[0];
    expect(hidden).toBeGreaterThanOrEqual(0);
    // the selected group's label is always shown
    const ref: GroupRef = { side: 0, level: 'brigade', division: s.battle.value!.units.get(unit.uid)!.org.division!,
      brigade: s.battle.value!.units.get(unit.uid)!.org.brigade! };
    act(() => s.selectGroup(ref));
    expect(document.querySelector('.group.selected text')).not.toBeNull();
  });

  it('labels hidden by the layers panel stay hidden', () => {
    const s = createStore(1863);
    s.setLayer('labels', false);
    render(<App store={s} />);
    expect(names()).toBe(0);
  });
});

describe('a brigade\'s label', () => {
  const rect = { left: 0, top: 0, width: 1000, height: 600, right: 1000, bottom: 600, x: 0, y: 0, toJSON: () => ({}) };

  it('deploying, drags the whole brigade; a click still selects it', () => {
    const s = organised();
    s.approve(0);
    s.approve(1);
    s.openDeployment();
    s.setMapGroups('brigade');
    render(<App store={s} />);
    (screen.getByRole('img', { name: /^Battlefield/ }) as unknown as SVGSVGElement).getBoundingClientRect =
      () => rect as DOMRect;
    const label = screen.getByRole('button', { name: 'Select Harrow' });
    expect(label.classList.contains('drag')).toBe(true);
    const x = s.mapUnits.value.find((u) => u.uid === 'us_15ma')!.x;
    fireEvent.pointerDown(label, { clientX: 100, clientY: 100, pointerId: 1 });
    fireEvent.pointerMove(label, { clientX: 150, clientY: 100, pointerId: 1 }); // 50 px: 100 yd
    fireEvent.pointerUp(label, { pointerId: 1 });
    expect(s.mapUnits.value.find((u) => u.uid === 'us_15ma')!.x).toBe(x + 100);
    fireEvent.pointerMove(label, { clientX: 500, clientY: 100, pointerId: 1 }); // let go: nothing
    expect(s.mapUnits.value.find((u) => u.uid === 'us_15ma')!.x).toBe(x + 100);
    fireEvent.click(screen.getByRole('button', { name: 'Select Harrow' }));
    expect(s.selectedGroup.value).toEqual(HARROW);
  });

  it('in battle, only selects', () => {
    const s = organised();
    s.start();
    s.setMapGroups('brigade');
    render(<App store={s} />);
    expect(screen.getByRole('button', { name: 'Select Harrow' }).classList.contains('drag')).toBe(false);
  });
});

describe('formations while deploying', () => {
  it('a column at the zone\'s front edge is drawn up inside the zone', () => {
    const s = organised();
    s.approve(0);
    s.approve(1);
    s.openDeployment();
    const zone = s.battle.value!.plan.zones['0']!;
    s.moveUnit('us_1mn', { x: 1000, y: zone.y + 10 });
    s.moveUnit('us_15ma', { x: 1000, y: zone.y + 10 });
    s.formGroup(HARROW, 'column');
    expect(s.outsideZone('us_1mn') || s.outsideZone('us_15ma')).toBe(false);
  });

  it('before the battle there is no zone to keep to', () => {
    const s = organised();
    s.moveUnit('us_1mn', { x: 1000, y: 40 });
    s.moveUnit('us_15ma', { x: 1000, y: 40 });
    s.formGroup(HARROW, 'column');
    expect(s.mapUnits.value.find((u) => u.uid === 'us_1mn')!.y).toBeLessThan(100);
  });
});

describe('a brigade charges only what it can reach in the round', () => {
  it('a regiment of the target brigade too far to charge in the round is not charged', () => {
    const s = organised();
    closeRanks(s);
    s.start();
    s.duration.value = 1; // a minute: infantry charge 120 yd
    act(() => s.moveUnit('cs_8al', { x: 1000, y: 100 })); // 530 yd from the Union
    expect(s.orderGroup(HARROW, 'melee', KEMPER)).toEqual({ reached: 2, of: 2 });
    expect(s.effectiveOrders.value.us_1mn.target).toBe('cs_10al');
    act(() => s.moveUnit('cs_10al', { x: 1000, y: 100 }));
    expect(s.orderGroup(HARROW, 'melee', KEMPER)).toEqual({ reached: 0, of: 2 });
    s.duration.value = 60;
    expect(s.orderGroup(HARROW, 'melee', KEMPER)).toEqual({ reached: 2, of: 2 });
  });
});

describe('the Dispatches tab', () => {
  it('the dispatches come before the strength charts', () => {
    const s = createStore(1863);
    closeRanks(s);
    s.start();
    s.setOrder('us_1mn', { mode: 'ranged', target: 'cs_8al' });
    expect(s.resolve()).toBeNull();
    render(<App store={s} />);
    const panel = document.getElementById('panel-dispatches')!;
    const dispatch = panel.querySelector('.dispatch-entry')!;
    const chart = panel.querySelector('.dispatch-entry ~ *')!;
    expect(dispatch).not.toBeNull();
    expect(chart).not.toBeNull();
    expect(dispatch.compareDocumentPosition(chart) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});

describe('a regiment\'s card', () => {
  it('opens its brigade\'s or division\'s card: the way to a group whose label gave way', () => {
    const s = organised();
    s.start();
    render(<App store={s} />);
    act(() => s.selectUnit('us_1mn'));
    fireEvent.click(screen.getByRole('button', { name: 'Harrow' }));
    expect(s.selectedGroup.value).toEqual(HARROW);
    act(() => s.selectUnit('us_1mn'));
    fireEvent.click(screen.getByRole('button', { name: 'Gibbon' }));
    expect(s.selectedGroup.value).toEqual({ side: 0, level: 'division', division: 'Gibbon', brigade: null });
  });

  it('none for a regiment without one, or before the battle', () => {
    const s = organised();
    render(<App store={s} />);
    act(() => s.selectUnit('us_1mn'));
    expect(screen.queryByRole('button', { name: 'Harrow' })).toBeNull();
    cleanup();
    const t = organised();
    t.start();
    render(<App store={t} />);
    act(() => t.selectUnit('us_bat'));
    expect(document.querySelector('.unit-org')).toBeNull();
  });
});
