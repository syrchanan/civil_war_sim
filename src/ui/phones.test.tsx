// @vitest-environment jsdom
// Phones and touch: the Files menu in the header, pinching the map, and dragging a deployment zone's edge.
import { cleanup, fireEvent, render, screen } from '@testing-library/preact';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { App } from './App';
import { createStore, type Store } from './store';

beforeEach(() => localStorage.clear());
afterEach(cleanup);

// the map drawn 1000 x 600 px: on the default 2,000 x 1,200 yd field, 2 yd a pixel
const rect = { left: 0, top: 0, width: 1000, height: 600, right: 1000, bottom: 600, x: 0, y: 0, toJSON: () => ({}) };
const svg = () => screen.getByRole('img', { name: /^Battlefield/ }) as unknown as SVGSVGElement;
function shown(s: Store) {
  render(<App store={s} />);
  svg().getBoundingClientRect = () => rect as DOMRect;
}

describe('the header on a phone', () => {
  it('the main action stays out; the rest fold behind Files, which opens and closes', () => {
    render(<App store={createStore(1863)} />);
    const toggle = screen.getByRole('button', { name: 'Files' });
    const more = document.getElementById('file-more')!;
    expect(more.contains(screen.getByRole('button', { name: 'Download battle' }))).toBe(true);
    expect(more.contains(screen.getByLabelText("Load players' orders"))).toBe(false);
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(toggle);
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    expect(more.classList.contains('open')).toBe(true);
    fireEvent.click(toggle);
    expect(more.classList.contains('open')).toBe(false);
  });

  it('a player\'s main action is their orders', () => {
    const s = createStore(1863, 'player');
    s.start();
    render(<App store={s} />);
    const more = document.getElementById('file-more')!;
    expect(more.contains(screen.getByRole('button', { name: 'Download my orders' }))).toBe(false);
  });
});

describe('pinching the map', () => {
  const touch = (type: 'pointerDown' | 'pointerMove' | 'pointerUp' | 'pointerCancel', target: Element, id: number,
    x = 0, y = 0) => fireEvent[type](target, { pointerId: id, clientX: x, clientY: y });

  it('two fingers zoom about their middle; fingers together do nothing; one left over neither pans nor zooms', () => {
    const s = createStore(1863);
    shown(s);
    const ground = document.querySelector('rect.field')!;
    touch('pointerDown', ground, 1, 400, 300);
    touch('pointerDown', ground, 2, 600, 300);
    touch('pointerMove', ground, 2, 800, 300); // twice as far apart: twice as close, about (600, 300) px
    expect(s.view.value).toEqual({ x: 600, y: 300, w: 1000, h: 600 });
    touch('pointerDown', ground, 4, 0, 0); // a third finger, lifted: still pinching with the two
    touch('pointerUp', ground, 4);
    touch('pointerMove', ground, 1, 800, 300); // together: no zoom
    touch('pointerMove', ground, 1, 700, 300); // from together: still none
    expect(s.view.value.w).toBe(1000);
    touch('pointerMove', ground, 1, 600, 300); // 200 px apart from 100: closer again
    expect(s.view.value.w).toBe(500);
    touch('pointerUp', ground, 2, 800, 300);
    const view = s.view.value;
    touch('pointerMove', ground, 1, 100, 100); // the finger left over: nothing
    expect(s.view.value).toEqual(view);
    touch('pointerCancel', ground, 1);
    touch('pointerMove', ground, 9, 0, 0); // a pointer never down (a mouse passing): nothing
    expect(s.view.value).toEqual(view);
    // all lifted: one finger pans again
    touch('pointerDown', ground, 3, 500, 300);
    touch('pointerMove', ground, 3, 400, 300);
    expect(s.view.value.x).toBeGreaterThan(view.x);
  });

  it('a second finger stops a unit being dragged', () => {
    const s = createStore(1863);
    shown(s);
    const block = screen.getByRole('button', { name: /^1st Minnesota,/ });
    const before = s.mapUnits.value.find((u) => u.uid === 'us_1mn')!;
    touch('pointerDown', block, 1, 100, 100);
    touch('pointerDown', document.querySelector('rect.field')!, 2, 300, 100);
    touch('pointerMove', block, 1, 150, 150);
    const after = s.mapUnits.value.find((u) => u.uid === 'us_1mn')!;
    expect([after.x, after.y]).toEqual([before.x, before.y]);
  });
});

describe('a deployment zone\'s edge', () => {
  const edge = (side: string) => screen.getByRole('slider', { name: new RegExp(`^${side} zone edge`) });

  it('dragged to set the zone\'s depth, from a yard to half the field; let go, it stays', () => {
    const s = createStore(1863);
    shown(s);
    const union = edge('Union');
    expect(union.getAttribute('aria-valuenow')).toBe('360');
    fireEvent.pointerDown(union, { pointerId: 1, clientX: 500, clientY: 420 });
    fireEvent.pointerMove(union, { pointerId: 1, clientX: 500, clientY: 400 }); // y 800: 400 yd deep
    expect(s.zoneDepth.value[0]).toBe(400);
    fireEvent.pointerMove(union, { pointerId: 1, clientX: 500, clientY: 0 });
    expect(s.zoneDepth.value[0]).toBe(600);
    fireEvent.pointerMove(union, { pointerId: 1, clientX: 500, clientY: 600 });
    expect(s.zoneDepth.value[0]).toBe(1);
    fireEvent.pointerUp(union, { pointerId: 1 });
    fireEvent.pointerMove(union, { pointerId: 1, clientX: 500, clientY: 300 });
    expect(s.zoneDepth.value[0]).toBe(1);
    const confederate = edge('Confederate');
    fireEvent.pointerDown(confederate, { pointerId: 2, clientX: 500, clientY: 180 });
    fireEvent.pointerMove(confederate, { pointerId: 2, clientX: 500, clientY: 200 }); // y 400: 400 yd deep
    expect(s.zoneDepth.value[1]).toBe(400);
  });

  it('or moved with the arrow keys, the way they point (Shift for bigger steps)', () => {
    const s = createStore(1863);
    shown(s);
    fireEvent.keyDown(edge('Union'), { key: 'ArrowUp' });
    expect(s.zoneDepth.value[0]).toBe(370);
    fireEvent.keyDown(edge('Union'), { key: 'ArrowDown', shiftKey: true });
    expect(s.zoneDepth.value[0]).toBe(320);
    fireEvent.keyDown(edge('Confederate'), { key: 'ArrowDown' });
    fireEvent.keyDown(edge('Confederate'), { key: 'ArrowUp', shiftKey: true });
    expect(s.zoneDepth.value[1]).toBe(320);
    fireEvent.keyDown(edge('Union'), { key: 'x' });
    expect(s.zoneDepth.value).toEqual([320, 320]);
  });

  it('only in setup, and only for the admin', () => {
    const player = createStore(1863, 'player');
    shown(player);
    expect(screen.queryAllByRole('slider')).toHaveLength(0);
    cleanup();
    const s = createStore(1863);
    s.approve(0);
    s.approve(1);
    s.openDeployment();
    shown(s);
    expect(screen.queryAllByRole('slider')).toHaveLength(0);
  });
});
