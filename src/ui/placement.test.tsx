// @vitest-environment jsdom
// Placing brigades while deploying: drawn up in a formation, dragged as a whole, listed with where they stand.
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/preact';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { App } from './App';
import { formation } from './field';
import { createStore, type GroupRef, type Store } from './store';

beforeEach(() => localStorage.clear());
afterEach(cleanup);

const HARROW: GroupRef = { side: 0, level: 'brigade', division: 'Gibbon', brigade: 'Harrow' };
const KEMPER: GroupRef = { side: 1, level: 'brigade', division: 'Pickett', brigade: 'Kemper' };

/** The example armies in brigades. */
function organised(mode: 'admin' | 'player' = 'admin'): Store {
  const s = createStore(1863, mode);
  const org: Record<string, { division: string; brigade: string }> = {
    us_1mn: { division: 'Gibbon', brigade: 'Harrow' }, us_15ma: { division: 'Gibbon', brigade: 'Harrow' },
    cs_8al: { division: 'Pickett', brigade: 'Kemper' }, cs_10al: { division: 'Pickett', brigade: 'Kemper' },
  };
  s.units.value = s.units.value.map((u) => ({ ...u, org: org[u.id] }));
  return s;
}

/** Deploying, both armies approved. */
function deploying(mode: 'admin' | 'player' = 'admin'): Store {
  const s = organised();
  s.approve(0);
  s.approve(1);
  s.openDeployment();
  if (mode === 'admin') return s;
  const p = createStore(1, 'player');
  p.open(s.playerFileDownload(0).text);
  return p;
}

const at = (s: Store, uid: string) => {
  const m = s.mapUnits.value.find((u) => u.uid === uid)!;
  return { x: m.x, y: m.y, facing: m.facing };
};

describe('formations', () => {
  const units = [{ id: 'a', width: 100, depth: 20 }, { id: 'b', width: 100, depth: 20 }, { id: 'c', width: 200, depth: 40 }];

  it('one line, side by side, centred', () => {
    expect(formation(units, { x: 1000, y: 900 }, 0, 'line')).toEqual({
      a: { x: 790, y: 900 }, b: { x: 950, y: 900 }, c: { x: 1160, y: 900 } });
  });

  it('two lines: the first half in front, towards the enemy', () => {
    expect(formation(units, { x: 1000, y: 900 }, 0, 'lines')).toEqual({
      a: { x: 920, y: 840 }, b: { x: 1080, y: 840 }, c: { x: 1000, y: 960 } });
    expect(formation(units, { x: 1000, y: 300 }, 1, 'lines').a.y).toBe(360); // side 1 faces down the map
  });

  it('a column, its head towards the enemy', () => {
    expect(formation(units, { x: 1000, y: 900 }, 0, 'column')).toEqual({
      a: { x: 1000, y: 830 }, b: { x: 1000, y: 890 }, c: { x: 1000, y: 960 } }); // 40 yd between
    expect(formation(units, { x: 1000, y: 300 }, 1, 'column').a.y).toBe(370);
  });
});

describe('store: a group placed as a whole', () => {
  it('moved by some yards, each keeping its facing, kept on the field; before the battle too', () => {
    const s = organised();
    s.faceUnit('us_1mn', 30);
    const before = [at(s, 'us_1mn'), at(s, 'us_15ma')];
    s.moveGroup(HARROW, 100, -50);
    expect([at(s, 'us_1mn'), at(s, 'us_15ma')]).toEqual(before.map((p) => ({ ...p, x: p.x + 100, y: p.y - 50 })));
    expect(at(s, 'us_bat')).toEqual(at(createStore(1863), 'us_bat')); // not in the brigade
    s.moveGroup(HARROW, 99999, 99999);
    expect(at(s, 'us_1mn')).toMatchObject({ x: 2000, y: 1200 });
    expect(s.groupMembers(HARROW)).toEqual(['us_1mn', 'us_15ma']);
  });

  it('drawn up in a formation around where it stands, facing the enemy', () => {
    const s = deploying();
    s.faceUnit('cs_8al', 90);
    s.formGroup(KEMPER, 'column');
    const a = at(s, 'cs_8al');
    const b = at(s, 'cs_10al');
    expect([a.x, a.facing, b.facing]).toEqual([b.x, 180, 180]);
    expect(b.y).toBeLessThan(a.y); // side 1: the column's head (the 8th) towards the Union
    s.formGroup(KEMPER, 'line');
    expect(at(s, 'cs_8al').y).toBe(at(s, 'cs_10al').y);
    s.formGroup(KEMPER, 'lines');
    expect(at(s, 'cs_8al').y).toBeGreaterThan(at(s, 'cs_10al').y);
    expect(s.battle.value!.units.get('cs_8al')!.regiment.position!.facing).toBe(180);
  });
});

describe('deploying by brigade', () => {
  it('the Deploy tab lists the brigades and where they stand; one picked opens its card to draw it up', () => {
    const s = deploying();
    render(<App store={s} />);
    const union = within(screen.getByRole('list', { name: 'Union brigades' }));
    expect(union.getAllByRole('listitem').map((li) => li.textContent)).toEqual(['Harrow (Gibbon) · 2 regiments · ✓ in the zone']);
    expect(screen.getByRole('list', { name: 'Confederate brigades' })).toBeTruthy();
    act(() => s.moveUnit('us_1mn', { x: 1000, y: 100 }));
    expect(union.getByText('1 outside the zone')).toBeTruthy();
    fireEvent.click(union.getByRole('button', { name: 'Harrow' }));
    const card = within(screen.getByRole('region', { name: 'Harrow' }));
    expect(card.getByText(/^1 outside the zone\./)).toBeTruthy();
    expect(card.queryByRole('button', { name: 'Fire' })).toBeNull();
    fireEvent.click(card.getByRole('button', { name: 'One line' }));
    expect(at(s, 'us_1mn').y).toBe(at(s, 'us_15ma').y);
    fireEvent.click(card.getByRole('button', { name: 'Two lines' }));
    fireEvent.click(card.getByRole('button', { name: 'Column' }));
    expect(at(s, 'us_1mn').x).toBe(at(s, 'us_15ma').x);
  });

  it('a player sees their own brigades, and draws up only their own', () => {
    const p = deploying('player');
    render(<App store={p} />);
    expect(screen.getByRole('list', { name: 'Union brigades' })).toBeTruthy();
    expect(screen.queryByRole('list', { name: 'Confederate brigades' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Harrow' }));
    expect(within(screen.getByRole('region', { name: 'Harrow' })).getByText(/^All inside the zone\./)).toBeTruthy();
  });

  it('an army without brigades lists none', () => {
    const s = createStore(1863);
    s.approve(0);
    s.approve(1);
    s.openDeployment();
    render(<App store={s} />);
    expect(screen.queryByRole('list', { name: 'Union brigades' })).toBeNull();
  });
});

describe('dragging an outline', () => {
  const rect = { left: 0, top: 0, width: 1000, height: 600, right: 1000, bottom: 600, x: 0, y: 0, toJSON: () => ({}) };
  const shown = (s: Store) => {
    s.setMapGroups('brigade');
    render(<App store={s} />);
    (screen.getByRole('img', { name: /^Battlefield/ }) as unknown as SVGSVGElement).getBoundingClientRect =
      () => rect as DOMRect;
  };

  it('deploying, the whole brigade moves with it; the map does not', () => {
    const s = deploying();
    shown(s);
    const outline = document.querySelectorAll('.group rect.drag')[0];
    const before = at(s, 'us_1mn');
    const view = s.view.value;
    fireEvent.pointerDown(outline, { clientX: 100, clientY: 100, pointerId: 1 });
    fireEvent.pointerMove(outline, { clientX: 150, clientY: 100, pointerId: 1 }); // 50 px: 100 yd
    expect(at(s, 'us_1mn').x).toBe(before.x + 100);
    expect(s.view.value).toEqual(view);
    fireEvent.pointerUp(outline, { pointerId: 1 });
    fireEvent.pointerMove(outline, { clientX: 500, clientY: 500, pointerId: 1 }); // let go: nothing
    expect(at(s, 'us_1mn').x).toBe(before.x + 100);
  });

  it('only while placing, and a player only their own', () => {
    const p = deploying('player');
    shown(p);
    expect(document.querySelectorAll('.group rect.drag')).toHaveLength(1); // the Union's; the enemy is not seen
    cleanup();
    const s = organised();
    s.start();
    shown(s);
    expect(document.querySelectorAll('.group rect.drag')).toHaveLength(0); // in battle, units move one by one
    cleanup();
    const setup = organised();
    shown(setup);
    expect(document.querySelectorAll('.group rect.drag')).toHaveLength(2); // before the battle, the admin
  });
});
