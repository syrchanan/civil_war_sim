/**
 * The battlefield seen from above: a plain field in yards, each unit a block in its side's color turned to its
 * facing (front edge marked), orders drawn as arrows (fire dashed, charge solid). Drag a unit, or select it and use
 * the arrow keys, to place it before the battle or move it between rounds; drag the handle in front of it, or use
 * Q and E, to turn it. In battle, click a unit (or select it and press Enter), then an enemy, and confirm fire or
 * charge to give it that target. Once rounds are fought, any round can be replayed as it began: where units stood, their
 * men and the orders given. The selected unit's front arc is drawn out to its range; what else the map shows (NATO
 * symbols, labels, all arcs, arrows, grid) is chosen in the layers panel (mapLayers.ts).
 */

import { Component } from 'preact';
import { useEffect, useRef } from 'preact/hooks';

import defaults from '../engine/defaults.json';
import type { Terrain, TerrainData } from '../engine';
import { arcPath, bearing, FIELD, type Point, turned } from './field';
import { LAYERS, natoSymbol } from './mapLayers';
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

/** The front arc of a unit: a wedge out to its maximum range, the stretch within close range shaded darker. */
function FrontArc({ store, uid, side }: { store: Store; uid: string; side: number }) {
  const arc = store.arcOf(uid);
  if (arc === null) return null;
  return (
    <g class={`front-arc side-${side}`}>
      <path class="max-zone" d={arcPath(arc, arc.facing, arc.half, arc.max)} />
      {arc.close > 0 && <path class="close-zone" d={arcPath(arc, arc.facing, arc.half, arc.close)} />}
    </g>
  );
}

const SYMBOL = { width: 60, height: 40 }; // yards: drawn upright over the block, the same size for every unit
const ECHELON = 14; // yards the echelon bars rise above the symbol's frame

/** A NATO-style symbol: the frame in the side's colour, the arm inside, the echelon bars above. */
function NatoSymbol({ type }: { type: string | null }) {
  const { arm, echelon } = natoSymbol(type);
  const w = SYMBOL.width / 2;
  const h = SYMBOL.height / 2;
  return (
    <g class={`nato ${arm}`}>
      <rect class="nato-frame" x={-w} y={-h} width={SYMBOL.width} height={SYMBOL.height} />
      {arm !== 'artillery' && <line class="nato-arm" x1={-w} y1={h} x2={w} y2={-h} />}
      {arm === 'infantry' && <line class="nato-arm" x1={-w} y1={-h} x2={w} y2={h} />}
      {arm === 'artillery' && <circle class="nato-dot" r={h / 3} />}
      <g class="echelon">
        {Array.from({ length: echelon }, (_, i) => {
          const x = (i - (echelon - 1) / 2) * 8;
          return <line x1={x} x2={x} y1={-h - 4} y2={-h - ECHELON} />;
        })}
      </g>
    </g>
  );
}

const RELIEF_BANDS = 8;

export interface Run {
  x: number;
  y: number;
  width: number;
  band: number;
}

/**
 * The terrain's cells as runs along each row: neighbours in the same height band (`bands` from the lowest to the
 * highest ground) become one rectangle, so the relief is a few hundred shapes rather than thousands.
 */
export function reliefRuns(t: Pick<TerrainData, 'cell' | 'columns' | 'rows'> & { heights: readonly number[] },
  bands: number): Run[] {
  const lo = Math.min(...t.heights);
  const span = Math.max(...t.heights) - lo;
  const band = (h: number) => (span === 0 ? 0 : Math.min(bands - 1, Math.floor(((h - lo) / span) * bands)));
  const runs: Run[] = [];
  for (let r = 0; r < t.rows; r++) {
    for (let c = 0; c < t.columns; c++) {
      const b = band(t.heights[r * t.columns + c]);
      const last = runs[runs.length - 1];
      if (c > 0 && last.band === b) last.width += t.cell;
      else runs.push({ x: c * t.cell, y: r * t.cell, width: t.cell, band: b });
    }
  }
  return runs;
}

/** Runs of woods (f) and rough ground (r) along each row. */
export function groundRuns(t: Pick<TerrainData, 'cell' | 'columns' | 'rows' | 'ground'>):
  { x: number; y: number; width: number; code: string }[] {
  const runs: { x: number; y: number; width: number; code: string }[] = [];
  for (let r = 0; r < t.rows; r++) {
    let open = true;
    for (let c = 0; c < t.columns; c++) {
      const code = t.ground[r * t.columns + c];
      const last = runs[runs.length - 1];
      if (code === 'o') open = true;
      else if (!open && last.code === code) last.width += t.cell;
      else {
        runs.push({ x: c * t.cell, y: r * t.cell, width: t.cell, code });
        open = false;
      }
    }
  }
  return runs;
}

/** The ground, drawn once per terrain and layer choice (thousands of cells: not redrawn on every move). */
class TerrainLayer extends Component<{ terrain: Terrain; relief: boolean; woods: boolean }> {
  shouldComponentUpdate(next: { terrain: Terrain; relief: boolean; woods: boolean }): boolean {
    return next.terrain !== this.props.terrain || next.relief !== this.props.relief || next.woods !== this.props.woods;
  }

  render() {
    const { terrain: t, relief, woods } = this.props;
    return (
      <g class="terrain">
        {relief && (
          <g class="relief">
            {reliefRuns(t, RELIEF_BANDS).map((r) => (
              <rect class={`band-${r.band}`} x={r.x} y={r.y} width={r.width} height={t.cell} />
            ))}
          </g>
        )}
        {woods && (
          <g class="woods">
            {groundRuns(t).map((r) => (
              <rect class={r.code === 'f' ? 'forest' : 'rough'} x={r.x} y={r.y} width={r.width} height={t.cell} />
            ))}
          </g>
        )}
      </g>
    );
  }
}

function Block({ store, unit, movable, selectable, aim }:
  { store: Store; unit: MapUnit; movable: boolean; selectable: boolean; aim: '' | ' aiming' | ' can-target' }) {
  const layers = store.layers.value;
  const grab = useRef<Point | null>(null);
  const dragged = useRef(false); // a drag ends in a click, which is not a click on the unit
  const turning = useRef(false);
  const svgOf = (el: Element) => el.closest('svg') as SVGSVGElement;
  const men = `${unit.rough ? 'about ' : ''}${unit.men.toLocaleString('en-US')}`;
  const ground = store.terrain.value;
  const standing = ground === null ? ''
    : `, ${Math.round(ground.heightAt(unit.x, unit.y))} yd up on ${ground.groundAt(unit.x, unit.y)} ground`;
  const label = `${unit.name}, ${men} men, at ${unit.x}, ${unit.y} yd, facing ${unit.facing}°${standing}`;
  // two text lines (name, men): below the block for side 0, above it for side 1
  // labels and the turn handle stay clear of the symbol (drawn upright, echelon bars on top) when it is shown
  const below = Math.max(unit.depth / 2, layers.symbols ? SYMBOL.height / 2 : 0);
  const above = Math.max(unit.depth / 2, layers.symbols ? SYMBOL.height / 2 + ECHELON : 0);
  const labelY = unit.side === 0 ? below + 30 : -above - 36;
  // the handle turns with the block: out past the symbol's corner whichever way it faces
  const handle = layers.symbols ? Math.max(unit.depth / 2, Math.hypot(SYMBOL.width / 2, SYMBOL.height / 2 + ECHELON))
    : unit.depth / 2;
  return (
    <g class={`map-unit side-${unit.side}${unit.broken ? ' broken' : ''}${unit.wiped ? ' wiped' : ''}${aim}`}
      transform={`translate(${unit.x} ${unit.y})`} role="button" aria-label={label}
      tabindex={movable || selectable ? 0 : undefined}
      onFocus={() => store.selectUnit(unit.uid)}
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
          store.selectUnit(null);
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
          <circle class="turn-handle" cx="0" cy={-handle - HANDLE_GAP} r="8"
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
      {layers.symbols && <NatoSymbol type={unit.type} />}
      {layers.labels && (
        <text y={labelY} text-anchor="middle">
          <tspan class="unit-name">{unit.name}</tspan>
          <tspan class="unit-men" x="0" dy="1.1em">{men}</tspan>
        </text>
      )}
    </g>
  );
}

/** The layers panel: one checkbox per layer, grouped; one place for every map option. */
function LayersPanel({ store }: { store: Store }) {
  const layers = store.layers.value;
  const groups = [...new Set(LAYERS.map((l) => l.group))];
  return (
    <details class="map-layers">
      <summary>Map layers</summary>
      <div role="group" aria-label="Map layers" class="layer-groups">
        {groups.map((group) => (
          <fieldset>
            <legend>{group}</legend>
            {LAYERS.filter((l) => l.group === group).map((l) => (
              <label>
                <input type="checkbox" checked={layers[l.key]}
                  onChange={(e) => store.setLayer(l.key, e.currentTarget.checked)} />
                {' '}{l.label}
              </label>
            ))}
          </fieldset>
        ))}
      </div>
    </details>
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
  const layers = store.layers.value;
  const focused = store.focusedUnit.value;
  const arcs = layers.allArcs ? units.filter((u) => !u.wiped).map((u) => u.uid)
    : focused !== null && byId[focused] !== undefined ? [focused] : [];
  return (
    <div class="map">
      <LayersPanel store={store} />
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
            {store.terrain.value !== null && (
              <TerrainLayer terrain={store.terrain.value} relief={layers.relief} woods={layers.woods} />
            )}
            {layers.grid && gridX.map((x) => <line class="field-grid" x1={x} x2={x} y1={0} y2={FIELD.height} />)}
            {layers.grid && gridY.map((y) => <line class="field-grid" x1={0} x2={FIELD.width} y1={y} y2={y} />)}
            {layers.scale && (
              <g class="scale-bar" transform={`translate(40 ${FIELD.height - 40})`}>
                <line x1={0} x2={SCALE_BAR} y1={0} y2={0} />
                <text x={SCALE_BAR / 2} y={-12} text-anchor="middle">{SCALE_BAR} yards</text>
              </g>
            )}
            {arcs.map((uid) => <FrontArc store={store} uid={uid} side={byId[uid].side} />)}
            {layers.arrows && store.orderArrows.value
              .map((a) => <Arrow from={byId[a.from]} to={byId[a.to]} mode={a.mode} side={a.side} />)}
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
        In battle, fire falls off with distance and a unit fires only within its front arc (drawn for the selected
        unit, out to its range: darker where fire tells in full); flank and rear attacks hit harder.
        <span class="phone-only"> On a small screen, scroll the map sideways.</span>
      </p>
    </div>
  );
}
