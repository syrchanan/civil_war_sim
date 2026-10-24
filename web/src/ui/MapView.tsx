/**
 * The battlefield seen from above: a plain field in yards, each unit a block in its side's color, orders drawn as
 * arrows (fire dashed, charge solid). Drag a unit, or select it and use the arrow keys, to place it before the
 * battle or move it between rounds. Display only: the engine ignores positions.
 */

import { useRef } from 'preact/hooks';

import { FIELD, type Point } from './field';
import type { MapUnit, Store } from './store';

const GRID = 100; // yards between grid lines
const SCALE_BAR = 500; // yards
const ARROW_OFFSET = 12; // yards

function toYards(svg: SVGSVGElement, clientX: number, clientY: number): Point {
  const r = svg.getBoundingClientRect();
  // before layout (width 0) treat one pixel as one yard
  const sx = r.width ? FIELD.width / r.width : 1;
  const sy = r.height ? FIELD.height / r.height : 1;
  return { x: (clientX - r.left) * sx, y: (clientY - r.top) * sy };
}

function Arrow({ from, to, mode, side }: { from: MapUnit; to: MapUnit; mode: string; side: number }) {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const length = Math.hypot(dx, dy) || 1;
  // stop short of the target's block so the arrowhead stays visible
  const stop = Math.min(length / 2, to.depth / 2 + 10);
  // shifted a little to the right of its direction, so two units' arrows at each other run side by side
  const ox = (-dy / length) * ARROW_OFFSET;
  const oy = (dx / length) * ARROW_OFFSET;
  return (
    <line class={`order-arrow ${mode === 'melee' ? 'charge' : 'fire'} side-${side}`} x1={from.x + ox}
      y1={from.y + oy} x2={to.x - (dx / length) * stop + ox} y2={to.y - (dy / length) * stop + oy}
      marker-end={`url(#arrowhead-${side})`} />
  );
}

function Block({ store, unit, movable }: { store: Store; unit: MapUnit; movable: boolean }) {
  const grab = useRef<Point | null>(null);
  const svgOf = (el: Element) => el.closest('svg') as SVGSVGElement;
  const label = `${unit.name}, ${unit.men.toLocaleString('en-US')} men, at ${unit.x}, ${unit.y} yd`;
  // two text lines (name, men): below the block for side 0, above it for side 1
  const labelY = unit.side === 0 ? unit.depth / 2 + 30 : -unit.depth / 2 - 36;
  return (
    <g class={`map-unit side-${unit.side}${unit.broken ? ' broken' : ''}${unit.wiped ? ' wiped' : ''}`}
      transform={`translate(${unit.x} ${unit.y})`} role="button" aria-label={label} tabindex={movable ? 0 : undefined}
      onPointerDown={(e) => {
        if (!movable) return;
        const p = toYards(svgOf(e.currentTarget), e.clientX, e.clientY);
        grab.current = { x: unit.x - p.x, y: unit.y - p.y };
        e.currentTarget.setPointerCapture?.(e.pointerId);
      }}
      onPointerMove={(e) => {
        if (grab.current === null) return;
        const p = toYards(svgOf(e.currentTarget), e.clientX, e.clientY);
        store.moveUnit(unit.uid, { x: p.x + grab.current.x, y: p.y + grab.current.y });
      }}
      onPointerUp={() => { grab.current = null; }}
      onKeyDown={(e) => {
        const step = e.shiftKey ? 50 : 10;
        const moves: Record<string, Point> = {
          ArrowLeft: { x: -step, y: 0 }, ArrowRight: { x: step, y: 0 }, ArrowUp: { x: 0, y: -step }, ArrowDown: { x: 0, y: step },
        };
        const m = moves[e.key];
        if (!movable || m === undefined) return;
        e.preventDefault();
        store.moveUnit(unit.uid, { x: unit.x + m.x, y: unit.y + m.y });
      }}>
      <rect x={-unit.width / 2} y={-unit.depth / 2} width={unit.width} height={unit.depth} rx="3" />
      {unit.wiped && (
        <>
          <line x1={-unit.width / 2} y1={-unit.depth / 2} x2={unit.width / 2} y2={unit.depth / 2} />
          <line x1={-unit.width / 2} y1={unit.depth / 2} x2={unit.width / 2} y2={-unit.depth / 2} />
        </>
      )}
      <text y={labelY} text-anchor="middle">
        <tspan class="unit-name">{unit.name}</tspan>
        <tspan class="unit-men" x="0" dy="1.1em">{unit.men.toLocaleString('en-US')}</tspan>
      </text>
    </g>
  );
}

export function MapView({ store }: { store: Store }) {
  const units = store.mapUnits.value;
  const byId = Object.fromEntries(units.map((u) => [u.uid, u]));
  const movable = !store.battle.value?.finished;
  const gridX = Array.from({ length: FIELD.width / GRID - 1 }, (_, i) => (i + 1) * GRID);
  const gridY = Array.from({ length: FIELD.height / GRID - 1 }, (_, i) => (i + 1) * GRID);
  return (
    <div class="map">
      <svg viewBox={`0 0 ${FIELD.width} ${FIELD.height}`} role="img"
        aria-label={`Battlefield, ${FIELD.width} by ${FIELD.height} yards`}>
        <defs>
          {[0, 1].map((side) => (
            <marker id={`arrowhead-${side}`} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5"
              orient="auto-start-reverse">
              <path d="M0,0 L10,5 L0,10 z" class={`arrowhead side-${side}`} />
            </marker>
          ))}
        </defs>
        <rect class="field" width={FIELD.width} height={FIELD.height} />
        {gridX.map((x) => <line class="field-grid" x1={x} x2={x} y1={0} y2={FIELD.height} />)}
        {gridY.map((y) => <line class="field-grid" x1={0} x2={FIELD.width} y1={y} y2={y} />)}
        <g class="scale-bar" transform={`translate(40 ${FIELD.height - 40})`}>
          <line x1={0} x2={SCALE_BAR} y1={0} y2={0} />
          <text x={SCALE_BAR / 2} y={-12} text-anchor="middle">{SCALE_BAR} yards</text>
        </g>
        {store.orderArrows.value.map((a) => <Arrow from={byId[a.from]} to={byId[a.to]} mode={a.mode} side={a.side} />)}
        {units.map((u) => <Block key={u.uid} store={store} unit={u} movable={movable} />)}
      </svg>
      <p class="note">
        {movable
          ? 'Drag a unit, or select it and use the arrow keys (Shift for bigger steps), to place it. '
          : ''}
        Positions are for the picture only: the engine doesn't use distance, cover or elevation yet.
      </p>
    </div>
  );
}
