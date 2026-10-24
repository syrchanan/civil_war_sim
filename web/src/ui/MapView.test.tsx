// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/preact';
import { afterEach, describe, expect, it } from 'vitest';

import { App } from './App';
import { createStore } from './store';

afterEach(cleanup);

// the field is 2000 × 1200 yd; draw it 1000 × 600 px so one pixel is two yards
const rect = { left: 0, top: 0, width: 1000, height: 600, right: 1000, bottom: 600, x: 0, y: 0, toJSON: () => ({}) };
const setup = () => {
  const store = createStore(1863);
  render(<App store={store} />);
  (screen.getByRole('img', { name: /^Battlefield/ }) as unknown as SVGSVGElement).getBoundingClientRect = () => rect as DOMRect;
  return store;
};
const unit = (name: string) => screen.getByRole('button', { name: new RegExp(`^${name},`) });

describe('map', () => {
  it('draws every unit as a block, labelled with its men', () => {
    setup();
    expect(document.querySelectorAll('.map-unit')).toHaveLength(7);
    expect(unit('1st Minnesota').getAttribute('aria-label')).toMatch(/^1st Minnesota, 900 men, at \d+, 900 yd/);
    expect(unit('1st Minnesota').textContent).toBe('1st Minnesota900');
    // SVG attribute names are case-sensitive: browsers only focus with a lowercase tabindex
    expect(unit('1st Minnesota').getAttribute('tabindex')).toBe('0');
  });

  it('drags a unit to a new place', () => {
    const store = setup();
    const block = unit('1st Minnesota');
    const start = store.mapUnits.value[0];
    fireEvent.pointerDown(block, { clientX: start.x / 2, clientY: start.y / 2, pointerId: 1 });
    fireEvent.pointerMove(block, { clientX: start.x / 2 + 50, clientY: start.y / 2 - 25, pointerId: 1 });
    fireEvent.pointerUp(block, { pointerId: 1 });
    expect(store.mapUnits.value[0]).toMatchObject({ x: start.x + 100, y: start.y - 50 });
    // moving the pointer after letting go does nothing
    fireEvent.pointerMove(block, { clientX: 0, clientY: 0, pointerId: 1 });
    expect(store.mapUnits.value[0]).toMatchObject({ x: start.x + 100, y: start.y - 50 });
  });

  it('arrow keys nudge the selected unit: 10 yd, 50 with Shift', () => {
    const store = setup();
    const start = store.mapUnits.value[0];
    fireEvent.keyDown(unit('1st Minnesota'), { key: 'ArrowLeft' });
    fireEvent.keyDown(unit('1st Minnesota'), { key: 'ArrowUp', shiftKey: true });
    fireEvent.keyDown(unit('1st Minnesota'), { key: 'ArrowRight' });
    fireEvent.keyDown(unit('1st Minnesota'), { key: 'ArrowDown' });
    fireEvent.keyDown(unit('1st Minnesota'), { key: 'Enter' });
    expect(store.mapUnits.value[0]).toMatchObject({ x: start.x, y: start.y - 40 });
  });

  it('blocks are turned to their facing, front edge marked; labels stay upright', () => {
    setup();
    expect(unit('1st Minnesota').getAttribute('aria-label')).toMatch(/at \d+, 900 yd, facing 0°$/);
    expect(unit('8th Alabama').querySelector('.block')!.getAttribute('transform')).toBe('rotate(180)');
    expect(unit('8th Alabama').querySelector('.front')).not.toBeNull();
    expect(unit('8th Alabama').querySelector('text')!.closest('.block')).toBeNull();
  });

  it('Q and E turn the selected unit: 15°, 45° with Shift', () => {
    const store = setup();
    fireEvent.keyDown(unit('1st Minnesota'), { key: 'e' });
    fireEvent.keyDown(unit('1st Minnesota'), { key: 'E', shiftKey: true });
    expect(store.mapUnits.value[0].facing).toBe(60);
    fireEvent.keyDown(unit('1st Minnesota'), { key: 'q' });
    fireEvent.keyDown(unit('1st Minnesota'), { key: 'Q', shiftKey: true });
    fireEvent.keyDown(unit('1st Minnesota'), { key: 'q', shiftKey: true });
    expect(store.mapUnits.value[0].facing).toBe(315);
  });

  it('dragging the handle in front of a unit turns it towards the pointer', () => {
    const store = setup();
    const start = store.mapUnits.value[0];
    const handle = unit('1st Minnesota').querySelector('.turn-handle')!;
    fireEvent.pointerDown(handle, { clientX: start.x / 2, clientY: start.y / 2 - 20, pointerId: 1 });
    fireEvent.pointerMove(handle, { clientX: start.x / 2 + 50, clientY: start.y / 2, pointerId: 1 });
    fireEvent.pointerUp(handle, { pointerId: 1 });
    expect(store.mapUnits.value[0]).toMatchObject({ x: start.x, y: start.y, facing: 90 });
    fireEvent.pointerMove(handle, { clientX: 0, clientY: start.y / 2, pointerId: 1 });
    expect(store.mapUnits.value[0].facing).toBe(90);          // let go: no more turning
  });

  it('shows orders as arrows: fire dashed, charge solid', () => {
    setup();
    fireEvent.click(screen.getByRole('button', { name: 'Start battle' }));
    fireEvent.change(screen.getByLabelText('1st Minnesota action'), { target: { value: 'ranged' } });
    fireEvent.change(screen.getByLabelText('8th Alabama action'), { target: { value: 'melee' } });
    const arrows = [...document.querySelectorAll('.order-arrow')];
    expect(arrows.map((a) => a.getAttribute('class'))).toEqual(['order-arrow fire side-0', 'order-arrow charge side-1']);
  });

  it('an arrow between two units on the same spot is still drawn', () => {
    const store = setup();
    fireEvent.click(screen.getByRole('button', { name: 'Start battle' }));
    act(() => {
      store.moveUnit('us_1mn', { x: 900, y: 600 });
      store.moveUnit('cs_8al', { x: 900, y: 600 });
    });
    fireEvent.change(screen.getByLabelText('1st Minnesota action'), { target: { value: 'ranged' } });
    const arrow = document.querySelector('.order-arrow')!;
    expect([arrow.getAttribute('x1'), arrow.getAttribute('x2')]).toEqual(['900', '900']);
  });

  it('marks broken and wiped-out units, and nothing moves once the battle is over', () => {
    const store = setup();
    fireEvent.click(screen.getByRole('button', { name: 'Start battle' }));
    act(() => {
      store.battle.value!.units.get('cs_8al')!.morale.forceBreak();
      store.battle.value!.units.get('cs_10al')!.regiment.updateSize(0);
      store.touch();
    });
    expect(unit('8th Alabama').classList.contains('broken')).toBe(true);
    expect(unit('10th Alabama').classList.contains('wiped')).toBe(true);
    expect(unit('10th Alabama').querySelectorAll('.cross')).toHaveLength(2);
    fireEvent.click(screen.getByRole('button', { name: 'Finish the battle' }));
    const before = store.mapUnits.value[0];
    fireEvent.pointerDown(unit('1st Minnesota'), { clientX: 10, clientY: 10, pointerId: 1 });
    fireEvent.pointerMove(unit('1st Minnesota'), { clientX: 100, clientY: 100, pointerId: 1 });
    fireEvent.keyDown(unit('1st Minnesota'), { key: 'ArrowLeft' });
    fireEvent.keyDown(unit('1st Minnesota'), { key: 'e' });
    expect(store.mapUnits.value[0]).toMatchObject({ x: before.x, y: before.y, facing: before.facing });
    expect(unit('1st Minnesota').querySelector('.turn-handle')).toBeNull();
    expect(unit('1st Minnesota').getAttribute('tabindex')).toBeNull();
  });

  it('a field drawn with no width yet still converts the pointer', () => {
    const store = setup();
    (screen.getByRole('img', { name: /^Battlefield/ }) as unknown as SVGSVGElement).getBoundingClientRect =
      () => ({ ...rect, width: 0, height: 0 }) as DOMRect;
    const start = store.mapUnits.value[0];
    fireEvent.pointerDown(unit('1st Minnesota'), { clientX: 0, clientY: 0, pointerId: 1 });
    fireEvent.pointerMove(unit('1st Minnesota'), { clientX: 10, clientY: 0, pointerId: 1 });
    expect(store.mapUnits.value[0].x).toBe(start.x + 10);
  });
});

describe('map arrows', () => {
  it('two units ordered at each other get arrows side by side, not on top of each other', () => {
    const store = setup();
    fireEvent.click(screen.getByRole('button', { name: 'Start battle' }));
    act(() => {
      store.moveUnit('us_1mn', { x: 500, y: 800 });
      store.moveUnit('cs_8al', { x: 500, y: 400 });
    });
    fireEvent.change(screen.getByLabelText('1st Minnesota action'), { target: { value: 'ranged' } });
    fireEvent.change(screen.getByLabelText('8th Alabama action'), { target: { value: 'melee' } });
    const xs = [...document.querySelectorAll('.order-arrow')].map((a) => Number(a.getAttribute('x1')));
    expect(xs).toEqual([512, 488]);
  });
});
