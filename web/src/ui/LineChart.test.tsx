// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/preact';
import { afterEach, describe, expect, it } from 'vitest';

import type { Series } from './chart';
import { LineChart } from './LineChart';

afterEach(cleanup);

const line = (name: string, values: number[]): Series =>
  ({ uid: name, name, points: values.map((v, i) => [i * 60, v] as [number, number]) });

const rect = { left: 0, width: 600, top: 0, height: 240, right: 600, bottom: 240, x: 0, y: 0, toJSON: () => ({}) };

describe('LineChart', () => {
  it('draws one line per series with a legend and end labels', () => {
    render(<LineChart title="Union: Men" series={[line('A', [900, 850, 700]), line('B', [700, 690, 695])]} />);
    expect(screen.getByRole('img').getAttribute('aria-label')).toMatch(/^Union: Men, by game minute/);
    expect(document.querySelectorAll('polyline')).toHaveLength(2);
    expect(document.querySelectorAll('circle')).toHaveLength(6);
    expect(screen.getByRole('list', { name: 'Union: Men legend' }).textContent).toBe('AB');
    expect([...document.querySelectorAll('.end-label')].map((t) => t.textContent)).toEqual(['A', 'B']); // top to bottom
  });

  it('one series: no legend box; five or more: no end labels', () => {
    render(<LineChart title="One" series={[line('A', [10, 5])]} />);
    expect(screen.queryByRole('list')).toBeNull();
    cleanup();
    render(<LineChart title="Many" series={['A', 'B', 'C', 'D', 'E'].map((n) => line(n, [10, 5]))} />);
    expect(document.querySelectorAll('.end-label')).toHaveLength(0);
  });

  it('the crosshair readout follows the pointer and lists every series', () => {
    render(<LineChart title="T" series={[line('A', [900, 850.5]), line('B', [700, 690])]} />);
    const svg = screen.getByRole('img');
    svg.getBoundingClientRect = () => rect as DOMRect;
    fireEvent.pointerMove(svg, { clientX: 480 });
    expect(screen.getByRole('status').textContent).toBe('60 minA: 850.5B: 690');
    expect(screen.getByRole('status').classList.contains('flip')).toBe(true);     // right half: readout on the left
    fireEvent.pointerMove(svg, { clientX: 10 });
    expect(screen.getByRole('status').textContent).toBe('0 minA: 900B: 700');
    expect(screen.getByRole('status').classList.contains('flip')).toBe(false);
    fireEvent.pointerLeave(svg);
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('a chart drawn with no width yet still finds a point', () => {
    render(<LineChart title="T" series={[line('A', [9, 8])]} />);
    const svg = screen.getByRole('img');
    svg.getBoundingClientRect = () => ({ ...rect, width: 0 }) as DOMRect;
    fireEvent.pointerMove(svg, { clientX: 500 });
    expect(screen.getByRole('status').textContent).toBe('60 minA: 8');
  });

  it('arrow keys step through the round ends', () => {
    render(<LineChart title="T" series={[line('A', [3, 2, 1])]} />);
    const svg = screen.getByRole('img');
    fireEvent.keyDown(svg, { key: 'ArrowRight' });
    expect(screen.getByRole('status').textContent).toBe('0 minA: 3');
    fireEvent.keyDown(svg, { key: 'ArrowRight' });
    fireEvent.keyDown(svg, { key: 'ArrowRight' });
    fireEvent.keyDown(svg, { key: 'ArrowRight' });
    expect(screen.getByRole('status').textContent).toBe('120 minA: 1');
    fireEvent.keyDown(svg, { key: 'Enter' });
    fireEvent.keyDown(svg, { key: 'ArrowLeft' });
    expect(screen.getByRole('status').textContent).toBe('60 minA: 2');
    fireEvent.blur(svg);
    expect(screen.queryByRole('status')).toBeNull();
    fireEvent.keyDown(svg, { key: 'ArrowLeft' });
    expect(screen.getByRole('status').textContent).toBe('120 minA: 1');
  });

  it('a battle not yet fought has one point at minute 0', () => {
    render(<LineChart title="T" series={[line('A', [0])]} />);
    expect(document.querySelectorAll('circle')).toHaveLength(1);
  });
});
