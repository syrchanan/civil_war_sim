/**
 * The battlefield seen from above: a plain field in yards, each unit a block in its side's color turned to its
 * facing (front edge marked), orders drawn as arrows (fire dashed, charge solid). Drag a unit, or select it and use
 * the arrow keys, to place it before the battle or move it between rounds; drag the handle in front of it, or use
 * Q and E, to turn it. In battle, click a unit (or select it and press Enter), then an enemy, and confirm fire or
 * charge to give it that target. Once rounds are fought, any round can be replayed as it began: where units stood, their
 * men and the orders given. Display only: the engine ignores positions and facings.
 */

import { useEffect, useRef } from 'preact/hooks';

import defaults from '../engine/defaults.json';
import { bearing, FIELD, type Point, turned } from './field';
import type { MapUnit, Store, TargetChoice } from './store';

/** Engine mode -> action word, capitalised (config/sheets.yaml: fire, charge). */
const ACTION_WORDS: Record<string, string> = Object.fromEntries(Object.entries(defaults.names.actions)
  .map(([word, mode]) => [mode, word[0].toUpperCase() + word.slice(1)]));

const GRID = 100; // yards between grid lines
const SCALE_BAR = 500; // yards
const ARROW_OFFSET = 12; // yards
const HANDLE_GAP = 18; // yards from a block's front edge to its turn handle
const TURNS: Record<string, number> = { q: -15, e: 15 }; // degrees; three times as much with Shift

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

function TargetMenu({ store, choice, at }: { store: Store; choice: TargetChoice; at: MapUnit }) {
  const first = useRef<HTMLButtonElement>(null);
  useEffect(() => first.current!.focus(), [choice.from, choice.to]);
  const name = (uid: string) => store.battle.value!.units.get(uid)!.name;
  return (
    <div class="target-menu" role="dialog" aria-label={`${name(choice.from)} against ${name(choice.to)}`}
      style={{ left: `${(at.x / FIELD.width) * 100}%`, top: `${(at.y / FIELD.height) * 100}%` }}
      onKeyDown={(e) => { if (e.key === 'Escape') store.cancelTargeting(); }}>
      {choice.actions.map((mode, i) => (
        <button ref={i === 0 ? first : undefined} class={mode === 'melee' ? 'charge' : 'fire'}
          onClick={() => store.chooseAction(mode)}>{ACTION_WORDS[mode]}</button>
      ))}
      <button onClick={() => store.cancelTargeting()}>Cancel</button>
    </div>
  );
}

function Block({ store, unit, movable, selectable, aim }:
  { store: Store; unit: MapUnit; movable: boolean; selectable: boolean; aim: '' | ' aiming' | ' can-target' }) {
  const grab = useRef<Point | null>(null);
  const dragged = useRef(false); // a drag ends in a click, which is not a click on the unit
  const turning = useRef(false);
  const svgOf = (el: Element) => el.closest('svg') as SVGSVGElement;
  const men = `${unit.rough ? 'about ' : ''}${unit.men.toLocaleString('en-US')}`;
  const label = `${unit.name}, ${men} men, at ${unit.x}, ${unit.y} yd, facing ${unit.facing}°`;
  // two text lines (name, men): below the block for side 0, above it for side 1
  const labelY = unit.side === 0 ? unit.depth / 2 + 30 : -unit.depth / 2 - 36;
  return (
    <g class={`map-unit side-${unit.side}${unit.broken ? ' broken' : ''}${unit.wiped ? ' wiped' : ''}${aim}`}
      transform={`translate(${unit.x} ${unit.y})`} role="button" aria-label={label}
      tabindex={movable || selectable ? 0 : undefined}
      onClick={() => {
        if (dragged.current) dragged.current = false;
        else store.clickUnit(unit.uid);
      }}
      onPointerDown={(e) => {
        if (!movable) return;
        const p = toYards(svgOf(e.currentTarget), e.clientX, e.clientY);
        grab.current = { x: unit.x - p.x, y: unit.y - p.y };
        e.currentTarget.setPointerCapture?.(e.pointerId);
      }}
      onPointerMove={(e) => {
        if (grab.current === null) return;
        dragged.current = true;
        const p = toYards(svgOf(e.currentTarget), e.clientX, e.clientY);
        store.moveUnit(unit.uid, { x: p.x + grab.current.x, y: p.y + grab.current.y });
      }}
      onPointerUp={() => { grab.current = null; }}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          store.clickUnit(unit.uid);
          return;
        }
        if (e.key === 'Escape') {
          store.cancelTargeting();
          return;
        }
        const step = e.shiftKey ? 50 : 10;
        const moves: Record<string, Point> = {
          ArrowLeft: { x: -step, y: 0 }, ArrowRight: { x: step, y: 0 }, ArrowUp: { x: 0, y: -step }, ArrowDown: { x: 0, y: step },
        };
        const m = moves[e.key];
        const turn = TURNS[e.key.toLowerCase()];
        if (!movable || (m === undefined && turn === undefined)) return;
        e.preventDefault();
        if (m !== undefined) store.moveUnit(unit.uid, { x: unit.x + m.x, y: unit.y + m.y });
        else store.faceUnit(unit.uid, turned(unit.facing, e.shiftKey ? 3 * turn : turn));
      }}>
      <g class="block" transform={`rotate(${unit.facing})`}>
        <rect x={-unit.width / 2} y={-unit.depth / 2} width={unit.width} height={unit.depth} rx="3" />
        <line class="front" x1={-unit.width / 2} y1={-unit.depth / 2} x2={unit.width / 2} y2={-unit.depth / 2} />
        {unit.wiped && (
          <>
            <line class="cross" x1={-unit.width / 2} y1={-unit.depth / 2} x2={unit.width / 2} y2={unit.depth / 2} />
            <line class="cross" x1={-unit.width / 2} y1={unit.depth / 2} x2={unit.width / 2} y2={-unit.depth / 2} />
          </>
        )}
        {movable && (
          <circle class="turn-handle" cx="0" cy={-unit.depth / 2 - HANDLE_GAP} r="8"
            onPointerDown={(e) => {
              e.stopPropagation(); // turning, not moving
              turning.current = true;
              e.currentTarget.setPointerCapture?.(e.pointerId);
            }}
            onPointerMove={(e) => {
              if (!turning.current) return;
              store.faceUnit(unit.uid, bearing(unit, toYards(svgOf(e.currentTarget), e.clientX, e.clientY)));
            }}
            onPointerUp={() => { turning.current = false; }} />
        )}
      </g>
      <text y={labelY} text-anchor="middle">
        <tspan class="unit-name">{unit.name}</tspan>
        <tspan class="unit-men" x="0" dy="1.1em">{men}</tspan>
      </text>
    </g>
  );
}

export function MapView({ store }: { store: Store }) {
  const units = store.mapUnits.value;
  const byId = Object.fromEntries(units.map((u) => [u.uid, u]));
  const battle = store.battle.value;
  // anything before the battle; between rounds, a player moves only their own side's units
  const replaying = store.mapRound.value;
  const canMove = (u: MapUnit) => replaying === null && (battle === null
    || (!battle.finished && (store.mode.value === 'admin' || u.side === store.playerSide.value)));
  const movable = replaying === null && !battle?.finished;
  // in battle, every unit can be selected: to aim it, or as a target
  const selectable = replaying === null && battle !== null && !battle.finished;
  const aiming = store.aiming.value;
  const targets = new Set(aiming === null ? [] : store.targetsFor(aiming).map((t) => t.uid));
  const aimOf = (uid: string) => (uid === aiming ? ' aiming' : targets.has(uid) ? ' can-target' : '');
  const choice = store.targetChoice.value;
  const gridX = Array.from({ length: FIELD.width / GRID - 1 }, (_, i) => (i + 1) * GRID);
  const gridY = Array.from({ length: FIELD.height / GRID - 1 }, (_, i) => (i + 1) * GRID);
  return (
    <div class="map">
      {store.replayRounds.value.length > 0 && (
        <label class="map-replay">
          Show on the map{' '}
          <select aria-label="Show on the map" value={replaying ?? ''}
            onChange={(e) => {
              const v = e.currentTarget.value;
              store.cancelTargeting();
              store.mapRound.value = v === '' ? null : Number(v);
            }}>
            <option value="">Now</option>
            {battle!.history.map((r) => (
              <option value={r.round}>{`Round ${r.round}, as it began (${r.start} min)`}</option>
            ))}
          </select>
        </label>
      )}
      <div class="field-scroll">
        <div class="field-wrap">
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
            {units.map((u) => (
              <Block key={u.uid} store={store} unit={u} movable={canMove(u)} selectable={selectable} aim={aimOf(u.uid)} />
            ))}
          </svg>
          {choice !== null && <TargetMenu store={store} choice={choice} at={byId[choice.to]} />}
        </div>
      </div>
      <p class="note">
        {aiming !== null ? `Pick a target for ${byId[aiming].name}: click an enemy (Escape to stop). ` : ''}
        {selectable && aiming === null ? 'Click a unit, then an enemy, to give it a target. ' : ''}
        {replaying !== null
          ? `Round ${replaying} as it began: where units stood, their men and the orders given. Pick Now to move units. `
          : ''}
        {movable
          ? 'Drag a unit, or select it and use the arrow keys, to place it; drag the handle in front of it, or use '
            + 'Q and E, to turn it (Shift for bigger steps). '
          : ''}
        Positions are for the picture only: the engine doesn't use distance, facing, cover or elevation yet.
        <span class="phone-only"> On a small screen, scroll the map sideways.</span>
      </p>
    </div>
  );
}
