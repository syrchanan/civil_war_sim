/**
 * The battlefield seen from above: a plain field in yards, each unit a block in its side's color turned to its
 * facing (front edge marked), orders drawn as arrows (fire dashed, charge solid). Drag a unit, or select it and use
 * the arrow keys, to place it before the battle or move it between rounds; drag the handle in front of it, or use
 * Q and E, to turn it. In battle, click a unit (or select it and press Enter), then an enemy, and confirm fire or
 * charge to give it that target. Once rounds are fought, any round can be replayed as it began: where units stood, their
 * men and the orders given. The selected unit's front arc is drawn out to its range; what else the map shows (NATO
 * symbols, labels, all arcs, arrows, grid) is chosen in the layers panel (mapLayers.ts).
 */

import { Component, type JSX } from 'preact';
import { useEffect, useRef } from 'preact/hooks';

import defaults from '../engine/defaults.json';
import type { Terrain, TerrainData } from '../engine';
import { arcPath, bearing, declutter, FIELD, type LabelBox, type Point, turned } from './field';
import { groupKey, groupName, groupOf, type GroupRef, type MapGroups, type MapViewBox } from './store';
import { LAYERS, natoSymbol } from './mapLayers';
import type { MapUnit, Store, TargetChoice } from './store';

/** Engine mode -> action word, capitalised (`names.actions` in defaults.json: fire, charge). */
const ACTION_WORDS: Record<string, string> = Object.fromEntries(Object.entries(defaults.names.actions)
  .map(([word, mode]) => [mode, word[0].toUpperCase() + word.slice(1)]));

const GRID = 100; // yards between grid lines
const SCALE_BAR = 500; // yards
const ARROW_OFFSET = 12; // yards
const HANDLE_GAP = 18; // yards from a block's front edge to its turn handle
const TURNS: Record<string, number> = { q: -15, e: 15 }; // degrees; three times as much with Shift

/** Where on the field (yards) a point on screen is, through the part of the field shown. */
function toYards(svg: SVGSVGElement, clientX: number, clientY: number, view: MapViewBox): Point {
  const r = svg.getBoundingClientRect();
  // before layout (width 0) treat one pixel as one yard
  const sx = r.width ? view.w / r.width : 1;
  const sy = r.height ? view.h / r.height : 1;
  return { x: view.x + (clientX - r.left) * sx, y: view.y + (clientY - r.top) * sy };
}

/** How much the map's furniture (symbols, labels, compass) is scaled to keep its size on screen: 1 on the default field. */
const furniture = (view: MapViewBox): number => view.w / FIELD.width;

function Arrow({ from, to, mode, side, blocked }:
  { from: MapUnit; to: MapUnit; mode: string; side: number; blocked: boolean }) {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const length = Math.hypot(dx, dy) || 1;
  // stop short of the target's block so the arrowhead stays visible
  const stop = Math.min(length / 2, to.depth / 2 + 10);
  // shifted a little to the right of its direction, so two units' arrows at each other run side by side
  const ox = (-dy / length) * ARROW_OFFSET;
  const oy = (dx / length) * ARROW_OFFSET;
  return (
    <line class={`order-arrow ${mode === 'melee' ? 'charge' : 'fire'} side-${side}${blocked ? ' blocked' : ''}`}
      x1={from.x + ox}
      y1={from.y + oy} x2={to.x - (dx / length) * stop + ox} y2={to.y - (dy / length) * stop + oy}
      marker-end={`url(#arrowhead-${side})`} />
  );
}

function TargetMenu({ store, choice, at }: { store: Store; choice: TargetChoice; at: MapUnit }) {
  const first = useRef<HTMLButtonElement>(null);
  useEffect(() => first.current!.focus(), [choice.from, choice.to]);
  const name = (uid: string) => store.battle.value!.units.get(uid)!.name;
  const v = store.view.value;
  return (
    <div class="target-menu" role="dialog" aria-label={`${name(choice.from)} against ${name(choice.to)}`}
      style={{ left: `${((at.x - v.x) / v.w) * 100}%`, top: `${((at.y - v.y) / v.h) * 100}%` }}
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

const EM = 0.5; // a label glyph's rough width, in ems: enough to tell which labels would overlap
/** A unit's second label line: its men ('~' when rough), and when it was last seen. */
const menText = (unit: MapUnit): string => `${unit.rough ? '~' : ''}${unit.men.toLocaleString('en-US')}`
  + `${unit.lastSeen === null ? '' : `, last seen round ${unit.lastSeen}`}`;

/**
 * Where a unit's two label lines (name, men) start, from its centre: below the block for side 0, above it for side
 * 1, clear of the symbol (drawn upright, echelon bars on top) when it is shown.
 */
function labelY(unit: MapUnit, symbols: boolean, k: number): number {
  const below = Math.max(unit.depth / 2, symbols ? (SYMBOL.height / 2) * k : 0);
  const above = Math.max(unit.depth / 2, symbols ? (SYMBOL.height / 2 + ECHELON) * k : 0);
  return unit.side === 0 ? below + 30 * k : -above - 36 * k;
}

/** The box a unit's label takes on the map (22 px name over 18 px men, at the furniture scale). */
function unitLabelBox(unit: MapUnit, symbols: boolean, k: number): LabelBox {
  const w = Math.max(unit.name.length * 22, menText(unit).length * 18) * EM * k;
  return { id: unit.uid, x: unit.x - w / 2, y: unit.y + labelY(unit, symbols, k) - 18 * k, w, h: 42 * k };
}

function Block({ store, unit, movable, selectable, aim, labelled }:
  { store: Store; unit: MapUnit; movable: boolean; selectable: boolean; aim: '' | ' aiming' | ' can-target'; labelled: boolean }) {
  const layers = store.layers.value;
  const view = store.view.value;
  const k = furniture(view);
  const grab = useRef<Point | null>(null);
  const dragged = useRef(false); // a drag ends in a click, which is not a click on the unit
  const turning = useRef(false);
  const svgOf = (el: Element) => el.closest('svg') as SVGSVGElement;
  // rough numbers read '~800' on the map and 'about 800' to a screen reader
  const men = `${unit.rough ? 'about ' : ''}${unit.men.toLocaleString('en-US')}`;
  const ground = store.terrain.value;
  const standing = ground === null ? ''
    : `, ${Math.round(ground.heightAt(unit.x, unit.y))} yd up on ${ground.groundAt(unit.x, unit.y)} ground`;
  const seen = unit.lastSeen === null ? '' : `, last seen as round ${unit.lastSeen} began`;
  const label = `${unit.name}, ${men} men${seen}, at ${unit.x}, ${unit.y} yd, facing ${unit.facing}°${standing}`;
  // the handle turns with the block: out past the symbol's corner whichever way it faces
  const handle = layers.symbols
    ? Math.max(unit.depth / 2, Math.hypot(SYMBOL.width / 2, SYMBOL.height / 2 + ECHELON) * k) : unit.depth / 2;
  return (
    <g class={`map-unit side-${unit.side}${unit.broken ? ' broken' : ''}${unit.wiped ? ' wiped' : ''}${unit.lastSeen !== null ? ' lost' : ''}${store.outsideZone(unit.uid) ? ' outside' : ''}${aim}`}
      transform={`translate(${unit.x} ${unit.y})`} role="button" aria-label={label}
      tabindex={movable || selectable ? 0 : undefined}
      onFocus={() => store.selectUnit(unit.uid)}
      onClick={() => {
        if (dragged.current) dragged.current = false;
        else store.clickUnit(unit.uid);
      }}
      onPointerDown={(e) => {
        if (!movable) return;
        e.stopPropagation(); // moving the unit, not the map
        const p = toYards(svgOf(e.currentTarget), e.clientX, e.clientY, view);
        grab.current = { x: unit.x - p.x, y: unit.y - p.y };
        e.currentTarget.setPointerCapture?.(e.pointerId);
      }}
      onPointerMove={(e) => {
        if (grab.current === null) return;
        dragged.current = true;
        const p = toYards(svgOf(e.currentTarget), e.clientX, e.clientY, view);
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
          <circle class="turn-handle" cx="0" cy={-handle - HANDLE_GAP * k} r={8 * k}
            onPointerDown={(e) => {
              e.stopPropagation(); // turning, not moving
              turning.current = true;
              e.currentTarget.setPointerCapture?.(e.pointerId);
            }}
            onPointerMove={(e) => {
              if (!turning.current) return;
              store.faceUnit(unit.uid, bearing(unit, toYards(svgOf(e.currentTarget), e.clientX, e.clientY, view)));
            }}
            onPointerUp={() => { turning.current = false; }} />
        )}
      </g>
      {layers.symbols && <g transform={`scale(${k})`}><NatoSymbol type={unit.type} /></g>}
      {/* out of sight: drawn where it was last seen, marked with a question mark */}
      {unit.lastSeen !== null && <text class="lost-mark" text-anchor="middle" dominant-baseline="central">?</text>}
      {labelled && (
        <text y={labelY(unit, layers.symbols, k)} text-anchor="middle">
          <tspan class="unit-name">{unit.name}</tspan>
          <tspan class="unit-men" x="0" dy="1.1em">{menText(unit)}</tspan>
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

/** Where each side deploys: while setting up (both) and deploying (with the fog on, only the viewer's own). */
const GROUP_PAD = 30; // yards between a group's regiments and its outline

/** Brigades or divisions outlined around their regiments (those shown), each labelled; a label selects its group. */
function GroupLayer({ store, level }: { store: Store; level: 'brigade' | 'division' }) {
  const b = store.battle.value;
  const k = furniture(store.view.value);
  const orgOf = (uid: string) => (b === null ? store.units.value.find((u) => u.id === uid)!.org ?? {}
    : b.units.get(uid)!.org);
  const groups = new Map<string, { ref: GroupRef; units: MapUnit[] }>();
  for (const u of store.mapUnits.value) {
    const ref = groupOf(u.side, orgOf(u.uid), level);
    if (ref === null) continue;
    const key = groupKey(ref);
    groups.set(key, { ref, units: [...(groups.get(key)?.units ?? []), u] });
  }
  const picked = store.selectedGroup.value;
  const view = store.view.value;
  // before the battle, or deploying: a group's outline drags the whole group (a player's own only)
  const placing = (b === null || (b.plan.phase === 'deployment' && store.mapRound.value === null));
  const canDrag = (ref: GroupRef) => placing && (store.mode.value === 'admin' || ref.side === store.playerSide.value);
  // each block's extent along x and y, turned as it faces
  const ext = (u: MapUnit) => {
    const r = (u.facing * Math.PI) / 180;
    const [c, s] = [Math.abs(Math.cos(r)), Math.abs(Math.sin(r))];
    return { x: (c * u.width + s * u.depth) / 2, y: (s * u.width + c * u.depth) / 2 };
  };
  const drawn = [...groups.entries()].map(([key, { ref, units }]) => {
    const x0 = Math.min(...units.map((u) => u.x - ext(u).x)) - GROUP_PAD;
    const x1 = Math.max(...units.map((u) => u.x + ext(u).x)) + GROUP_PAD;
    const y0 = Math.min(...units.map((u) => u.y - ext(u).y)) - GROUP_PAD;
    const y1 = Math.max(...units.map((u) => u.y + ext(u).y)) + GROUP_PAD;
    const men = units.reduce((sum, u) => sum + u.men, 0);
    const rough = units.some((u) => u.rough);
    const text = `${groupName(ref)} · ${units.length} regt${units.length === 1 ? '' : 's'} · ${rough ? '~' : ''}`
      + men.toLocaleString('en-US');
    return { key, ref, men, text, box: { x: x0, y: y0, w: x1 - x0, h: y1 - y0 } };
  });
  // labels that would overlap give way: the selected group's first, then the biggest; zoomed in, more fit
  const isPicked = (key: string) => picked !== null && groupKey(picked) === key;
  const labelled = declutter([...drawn]
    .sort((a, b) => Number(isPicked(b.key)) - Number(isPicked(a.key)) || b.men - a.men)
    .map((g) => ({ id: g.key, x: g.box.x, y: g.box.y - 26 * k, w: g.text.length * 22 * 0.55 * k, h: 24 * k })));
  return (
    <g class="groups">
      {drawn.map(({ key, ref, text, box }) => {
        const select = () => store.selectGroup(ref);
        return (
          <g class={`group side-${ref.side}${isPicked(key) ? ' selected' : ''}`}>
            <GroupDrag store={store} ref_={ref} drag={canDrag(ref)} view={view}>
              {(handlers) => <rect class={handlers ? 'drag' : undefined} x={box.x} y={box.y} width={box.w} height={box.h}
                {...handlers} />}
            </GroupDrag>
            {labelled.has(key) && (
              <GroupDrag store={store} ref_={ref} drag={canDrag(ref)} view={view}>
                {(handlers) => (
                  <text class={handlers ? 'drag' : undefined} x={box.x} y={box.y - 8 * k} role="button" tabindex={0}
                    aria-label={`Select ${groupName(ref)}`} {...handlers}
                    onClick={select} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') select(); }}>{text}</text>
                )}
              </GroupDrag>
            )}
          </g>
        );
      })}
    </g>
  );
}

type DragHandlers = Pick<JSX.HTMLAttributes<SVGElement>, 'onPointerDown' | 'onPointerMove' | 'onPointerUp'>;

/**
 * While placing, a group's outline and its label drag the whole group (the label too, as the regiments drawn over
 * the outline leave little of it to grab); otherwise no handlers.
 */
function GroupDrag({ store, ref_, drag, view, children }: {
  store: Store; ref_: GroupRef; drag: boolean; view: MapViewBox; children: (handlers: DragHandlers | null) => JSX.Element;
}) {
  const from = useRef<Point | null>(null);
  if (!drag) return children(null);
  const at = (e: PointerEvent) => toYards((e.currentTarget as Element).closest('svg') as SVGSVGElement, e.clientX, e.clientY, view);
  return children({
    onPointerDown: (e) => {
      e.stopPropagation(); // the group, not the map
      from.current = at(e);
      (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
    },
    onPointerMove: (e) => {
      if (from.current === null) return;
      const p = at(e);
      store.moveGroup(ref_, p.x - from.current.x, p.y - from.current.y);
      from.current = p;
    },
    onPointerUp: () => { from.current = null; },
  });
}

const GROUPINGS: [MapGroups, string][] = [['regiment', 'Regiments'], ['brigade', 'Brigades'], ['division', 'Divisions']];

const EDGE = 60; // yards (at the furniture scale): how thick a zone's draggable edge is to grab, a finger's width on a phone

/**
 * A zone's inner edge (side 0's top, side 1's bottom), dragged or moved with the arrow keys to set how deep the
 * zone is: in setup, for the admin, from 1 yard to half the field.
 */
function ZoneEdge({ store, side, zone }: { store: Store; side: 0 | 1; zone: { x: number; y: number; w: number; h: number } }) {
  const dragging = useRef(false);
  const view = store.view.value;
  const k = furniture(view);
  const height = store.field.value.height;
  const set = (depth: number) => store.setZoneDepth(side, Math.round(Math.min(height / 2, Math.max(1, depth))));
  const y = side === 0 ? zone.y : zone.y + zone.h;
  const name = `${store.sides.value[side]} zone edge, ${zone.h} yards deep`;
  return (
    <rect class="zone-edge" x={zone.x} y={y - (EDGE * k) / 2} width={zone.w} height={EDGE * k} role="slider" tabindex={0}
      aria-label={name} aria-valuenow={zone.h} aria-valuemin={1} aria-valuemax={height / 2} aria-orientation="vertical"
      onPointerDown={(e) => {
        e.stopPropagation(); // the zone, not the map
        dragging.current = true;
        e.currentTarget.setPointerCapture?.(e.pointerId);
      }}
      onPointerMove={(e) => {
        if (!dragging.current) return;
        const at = toYards(e.currentTarget.closest('svg') as SVGSVGElement, e.clientX, e.clientY, view);
        set(side === 0 ? height - at.y : at.y);
      }}
      onPointerUp={() => { dragging.current = false; }}
      onKeyDown={(e) => {
        const step = e.shiftKey ? 50 : 10;
        // the edge moves the way the arrow points: up the map deepens side 0's zone, down deepens side 1's
        const by = { ArrowUp: side === 0 ? step : -step, ArrowDown: side === 0 ? -step : step }[e.key];
        if (by === undefined) return;
        e.preventDefault();
        set(zone.h + by);
      }} />
  );
}

function ZoneLayer({ store }: { store: Store }) {
  store.revision.value; // the battle opens in place
  const b = store.battle.value;
  if (b !== null && b.plan.phase !== 'deployment') return null;
  const zones = b === null ? store.zones.value : b.plan.zones;
  const hidden = store.fogSide.value;
  // before the battle the admin sets how deep each zone is; once deploying, they are the battle's
  const editable = b === null && store.mode.value === 'admin';
  return (
    <g class="zones">
      {Object.entries(zones).filter(([side]) => Number(side) !== hidden).map(([side, z]) => (
        <g class={`zone side-${side}`}>
          <rect x={z.x} y={z.y} width={z.w} height={z.h} />
          <text x={z.x + 24} y={side === '0' ? z.y + z.h - 24 : z.y + 44}>
            {store.sides.value[Number(side)]} deployment zone
          </text>
          {editable && <ZoneEdge store={store} side={Number(side) as 0 | 1} zone={z} />}
        </g>
      ))}
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
  const field = store.field.value;
  const view = store.view.value;
  const k = furniture(view);
  // zoomed out over a large field, a coarser grid and a longer scale bar
  const grid = GRID * (k >= 2 ? 5 : 1);
  const bar = SCALE_BAR * (k >= 2 ? 4 : 1);
  const gridX = Array.from({ length: Math.ceil(field.width / grid) - 1 }, (_, i) => (i + 1) * grid);
  const gridY = Array.from({ length: Math.ceil(field.height / grid) - 1 }, (_, i) => (i + 1) * grid);
  const pan = useRef<{ x: number; y: number; moved: boolean } | null>(null);
  // fingers on the map: two pinch it; until all are lifted, a finger left over does nothing
  const touches = useRef(new Map<number, Point>());
  const pinch = useRef<{ distance: number } | null>(null);
  const pinched = useRef(false);
  const spread = () => {
    const [a, b] = [...touches.current.values()];
    return { distance: Math.hypot(a.x - b.x, a.y - b.y), mid: { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 } };
  };
  const lift = (id: number) => {
    touches.current.delete(id);
    if (touches.current.size < 2) pinch.current = null;
    if (touches.current.size === 0) pinched.current = false;
  };
  const layers = store.layers.value;
  const focused = store.focusedUnit.value;
  // no arc for a unit only last seen: where it faces now is unknown
  // regiment labels that would overlap give way (the selected unit's first); zoomed in, more fit
  const labelled = layers.labels && store.mapGroups.value === 'regiment'
    ? declutter([...units].sort((a, b) => Number(b.uid === focused) - Number(a.uid === focused))
      .map((u) => unitLabelBox(u, layers.symbols, k)))
    : new Set<string>();
  const arcs = (layers.allArcs ? units.filter((u) => !u.wiped).map((u) => u.uid)
    : focused !== null && byId[focused] !== undefined ? [focused] : []).filter((uid) => byId[uid].lastSeen === null);
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
          <div class="map-zoom" role="group" aria-label="Zoom">
            <button aria-label="Zoom in" onClick={() => store.zoomMap(1.5)}>+</button>
            <button aria-label="Zoom out" disabled={view.w >= field.width} onClick={() => store.zoomMap(1 / 1.5)}>−</button>
            <button aria-label="Show the whole field" disabled={view.w >= field.width} onClick={() => store.fitMap()}>
              Whole field</button>
          </div>
          <div class="map-groups" role="group" aria-label="Outline">
            {GROUPINGS.map(([key, label]) => (
              <button aria-pressed={store.mapGroups.value === key} class={store.mapGroups.value === key ? 'active' : ''}
                onClick={() => store.setMapGroups(key)}>{label}</button>
            ))}
          </div>
          <svg viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`} role="img" style={{ '--k': k }}
            aria-label={`Battlefield, ${field.width} by ${field.height} yards`}
            onPointerDownCapture={(e) => {
              touches.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
              if (touches.current.size < 2) return;
              // a second finger: pinching, not panning or moving a unit
              e.stopPropagation();
              pan.current = null;
              pinched.current = true;
              pinch.current = { distance: spread().distance };
            }}
            onPointerMoveCapture={(e) => {
              if (!touches.current.has(e.pointerId)) return;
              touches.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
              if (!pinched.current) return;
              e.stopPropagation();
              if (touches.current.size < 2) return;
              const { distance, mid } = spread();
              if (distance > 0 && pinch.current!.distance > 0) {
                store.zoomMap(distance / pinch.current!.distance, toYards(e.currentTarget, mid.x, mid.y, view));
              }
              pinch.current = { distance };
            }}
            onPointerUpCapture={(e) => lift(e.pointerId)}
            onPointerCancelCapture={(e) => lift(e.pointerId)}
            onWheel={(e) => {
              e.preventDefault();
              store.zoomMap(e.deltaY < 0 ? 1.25 : 1 / 1.25, toYards(e.currentTarget, e.clientX, e.clientY, view));
            }}>
            <defs>
              {[0, 1].map((side) => (
                <marker id={`arrowhead-${side}`} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5"
                  orient="auto-start-reverse">
                  <path d="M0,0 L10,5 L0,10 z" class={`arrowhead side-${side}`} />
                </marker>
              ))}
            </defs>
            {/* drag the open ground to move the map */}
            <rect class="field" width={field.width} height={field.height}
              onPointerDown={(e) => {
                pan.current = { x: e.clientX, y: e.clientY, moved: false };
                e.currentTarget.setPointerCapture?.(e.pointerId);
              }}
              onPointerMove={(e) => {
                const p = pan.current;
                if (p === null) return;
                const svg = e.currentTarget.closest('svg') as SVGSVGElement;
                const a = toYards(svg, p.x, p.y, view);
                const b = toYards(svg, e.clientX, e.clientY, view);
                if (a.x === b.x && a.y === b.y) return;
                pan.current = { x: e.clientX, y: e.clientY, moved: true };
                store.panMap(a.x - b.x, a.y - b.y);
              }}
              onPointerUp={() => { pan.current = null; }} />
            {store.terrain.value !== null && (
              <TerrainLayer terrain={store.terrain.value} relief={layers.relief} woods={layers.woods} />
            )}
            {layers.grid && gridX.map((x) => <line class="field-grid" x1={x} x2={x} y1={0} y2={field.height} />)}
            {layers.grid && gridY.map((y) => <line class="field-grid" x1={0} x2={field.width} y1={y} y2={y} />)}
            <ZoneLayer store={store} />
            {store.mapGroups.value !== 'regiment' && <GroupLayer store={store} level={store.mapGroups.value} />}
            {/* a compass rose: north is the top of the map */}
            <g class="compass" aria-hidden="true"
              transform={`translate(${view.x + view.w - 70 * k} ${view.y + 80 * k}) scale(${k})`}>
              <circle r="34" />
              <path class="needle" d="M0 -28 L 8 0 L 0 28 L -8 0 Z" />
              <text y="-42" text-anchor="middle">N</text>
            </g>
            {layers.scale && (
              <g class="scale-bar" transform={`translate(${view.x + 40 * k} ${view.y + view.h - 40 * k})`}>
                <line x1={0} x2={bar} y1={0} y2={0} />
                <text x={bar / 2} y={-12 * k} text-anchor="middle">{bar.toLocaleString('en-US')} yards</text>
              </g>
            )}
            {arcs.map((uid) => <FrontArc store={store} uid={uid} side={byId[uid].side} />)}
            {layers.arrows && store.orderArrows.value
              .map((a) => <Arrow from={byId[a.from]} to={byId[a.to]} mode={a.mode} side={a.side} blocked={a.blocked} />)}
            {units.map((u) => (
              <Block key={u.uid} store={store} unit={u} movable={canMove(u)} selectable={selectable} aim={aimOf(u.uid)}
                labelled={labelled.has(u.uid)} />
            ))}
          </svg>
          {choice !== null && <TargetMenu store={store} choice={choice} at={byId[choice.to]} />}
        </div>
      </div>
      <p class="note map-hint">
        {aiming !== null ? `Pick a target for ${byId[aiming].name}: click an enemy (Escape to stop). ` : ''}
        {selectable && aiming === null && battle.plan.phase !== 'deployment'
          ? 'Click a unit, then an enemy, to give it a target. ' : ''}
        {battle !== null && battle.plan.phase === 'deployment' && replaying === null
          ? 'Round 0: place each regiment inside its side\'s deployment zone. ' : ''}
        {replaying !== null
          ? `Round ${replaying} as it began: where units stood, their men and the orders given. Pick Now to move units. `
          : ''}
        Scroll, pinch or use + and − to zoom; drag open ground to move the map.{' '}
        {movable
          ? 'Drag a unit, or select it and use the arrow keys, to place it; drag the handle in front of it, or use '
            + 'Q and E, to turn it (Shift for bigger steps). '
          : ''}
        In battle, fire falls off with distance, a unit fires only within its front arc (drawn for the selected
        unit, out to its range: darker where fire tells in full) and only at what it can see; higher ground helps,
        and flank and rear attacks hit harder. Faded arrows are fire that can't tell from where the units stand.
      </p>
    </div>
  );
}
