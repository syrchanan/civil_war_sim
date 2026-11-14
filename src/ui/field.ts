/**
 * The map: the field in yards (its size chosen per battle), how big each unit is drawn on it, where units start,
 * and the geometry of facings and front arcs.
 */

import { DEFAULT_FIELD, type FieldSize } from '../engine';

/** The default field, in yards: a battle's own size is in its plan (fieldOf). */
export const FIELD: FieldSize = DEFAULT_FIELD;

/** The field sizes offered in setup, smallest first. */
export const FIELD_PRESETS: [string, FieldSize][] = [
  ['Small', { width: 2000, height: 1200 }],
  ['Medium', { width: 4000, height: 2400 }],
  ['Large', { width: 8000, height: 4800 }],
];

const MIN_WIDTH = 20; // yards: even a tiny unit stays visible
const GAP = 60; // yards between neighbouring units in the default layout
const LINE_GAP = 120; // yards between a side's first and second line
const MARGIN = 100; // yards kept clear at the field's edges

// Display scale, from drill-book frontages: men stand in two ranks; a file takes about 2/3 yd (infantry) or
// 1.1 yd (cavalry); a gun with its crew takes about 15 yd.
const PER_FILE: Record<string, number> = { inf: 0.66, cav: 1.1 };
const BASE_DEPTH: Record<string, number> = { inf: 20, cav: 40, art: 40 };
const PER_GUN = 15;

export interface Point {
  x: number;
  y: number;
}

/**
 * A unit's block on the field, in yards. Infantry and cavalry are as wide as their front (men in two ranks), and
 * deeper when the front is narrower than the unit; a battery is as wide as its guns.
 */
export function blockSize(type: string | null, men: number, front: number, guns: number | null):
  { width: number; depth: number } {
  const kind = type ?? 'inf';
  if (kind === 'art') return { width: Math.max(MIN_WIDTH, (guns ?? 0) * PER_GUN), depth: BASE_DEPTH.art };
  const width = Math.max(MIN_WIDTH, Math.round((front / 2) * PER_FILE[kind]));
  const depth = Math.round(BASE_DEPTH[kind] * Math.max(1, front > 0 ? men / front : 1));
  return { width, depth };
}

/** A side's deployment zone, in yards (as in the battle's plan). */
export interface ZoneRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** How far inside its zone's front edge a side's first line stands. */
export const ZONE_INSET = 60;
/** The default zone depth on the default field: its first line then stands where the zoneless layout puts it. */
export const DEFAULT_ZONE_DEPTH = 360;
/** The default zone depth on any field: the same share of its height (360 yd of 1,200). */
export const defaultZoneDepth = (field: FieldSize): number => Math.round(field.height * 0.3);

/** A band along a side's own edge of the field: side 0 the bottom, side 1 the top. */
export function zoneBand(side: 0 | 1, depth: number, field: FieldSize = FIELD): ZoneRect {
  return { x: 0, y: side === 0 ? field.height - depth : 0, w: field.width, h: depth };
}

/** How many lines a side's units would stand in across a field (the default layout's wrapping). */
export function linesNeeded(widths: number[], field: FieldSize): number {
  const room = field.width - 2 * MARGIN;
  let lines = widths.length ? 1 : 0;
  let used = 0;
  for (const w of widths) {
    const need = used ? used + GAP + w : w;
    if (used && need > room) {
      lines += 1;
      used = w;
    } else {
      used = need;
    }
  }
  return lines;
}

/** The smallest preset field on which each side's units stand in at most three lines (else the largest). */
export function suggestField(widths: [number[], number[]]): string {
  const fits = FIELD_PRESETS.find(([, f]) => widths.every((w) => linesNeeded(w, f) <= 3));
  return (fits ?? FIELD_PRESETS[FIELD_PRESETS.length - 1])[0];
}

/**
 * Where units start: side 0 in a line across the lower part of the field, side 1 across the upper part, each
 * line centred, wrapping to a second line behind the first when it runs out of room. With a side's zone, its first
 * line stands just inside the zone's edge towards the enemy, centred on the zone.
 */
export function defaultLayout(units: { id: string; side: 0 | 1; width: number }[],
  zones: Partial<Record<string, ZoneRect>> = {}, field: FieldSize = FIELD): Record<string, Point> {
  const layout: Record<string, Point> = {};
  for (const side of [0, 1] as const) {
    const zone = zones[String(side)] ?? zoneBand(side, defaultZoneDepth(field), field);
    const inset = Math.min(ZONE_INSET, zone.h / 2);
    const front = side === 0 ? zone.y + inset : zone.y + zone.h - inset;
    const back = side === 0 ? LINE_GAP : -LINE_GAP;
    const room = zone.w > 2 * MARGIN ? zone.w - 2 * MARGIN : zone.w;
    const lines: { id: string; width: number }[][] = [[]];
    let used = 0; // yards taken in the current line
    for (const u of units.filter((u) => u.side === side)) {
      const line = lines[lines.length - 1];
      const need = line.length ? used + GAP + u.width : u.width;
      if (line.length && need > room) {
        lines.push([u]);
        used = u.width;
      } else {
        line.push(u);
        used = need;
      }
    }
    lines.forEach((line, n) => {
      const total = line.reduce((s, u) => s + u.width, 0) + GAP * Math.max(0, line.length - 1);
      let left = zone.x + (zone.w - total) / 2;
      for (const u of line) {
        layout[u.id] = { x: Math.round(left + u.width / 2), y: front + n * back }; // whole yards
        left += u.width + GAP;
      }
    });
  }
  return layout;
}

/** A point kept on the field, in whole yards. */
export function clampToField(p: Point, field: FieldSize = FIELD): Point {
  return {
    x: Math.round(Math.min(field.width, Math.max(0, p.x))),
    y: Math.round(Math.min(field.height, Math.max(0, p.y))),
  };
}

/** A unit's place on the map: where it stands (yards) and which way its front faces. */
export interface Place extends Point {
  facing: number;
}

/**
 * Facings are compass degrees, clockwise from the top of the map (towards y = 0), in [0, 360). Each side starts
 * facing the other: side 0 up the map, side 1 down it.
 */
export const defaultFacing = (side: 0 | 1): number => (side === 0 ? 0 : 180);

/** A facing turned by some degrees (negative: anticlockwise), kept within one turn. */
export const turned = (facing: number, by: number): number => (((facing + by) % 360) + 360) % 360;

/** The facing that points from one point towards another, in whole degrees. */
export const bearing = (from: Point, to: Point): number =>
  turned(Math.round((Math.atan2(to.x - from.x, from.y - to.y) * 180) / Math.PI), 0);

const tenth = (v: number): number => Math.round(v * 10) / 10 + 0; // + 0: no '-0'

/**
 * An SVG path for a unit's front arc: a wedge from `at`, centred on `facing` (compass degrees), `half` degrees
 * either side, out to `radius` yards. A full turn is a circle.
 */
export function arcPath(at: Point, facing: number, half: number, radius: number): string {
  const r = tenth(radius);
  if (half >= 180) {
    return `M${tenth(at.x - radius)} ${tenth(at.y)} A${r} ${r} 0 1 1 ${tenth(at.x + radius)} ${tenth(at.y)} `
      + `A${r} ${r} 0 1 1 ${tenth(at.x - radius)} ${tenth(at.y)} Z`;
  }
  const corner = (deg: number) => {
    const rad = (deg * Math.PI) / 180;
    return `${tenth(at.x + Math.sin(rad) * radius)} ${tenth(at.y - Math.cos(rad) * radius)}`;
  };
  return `M${tenth(at.x)} ${tenth(at.y)} L${corner(facing - half)} A${r} ${r} 0 ${half > 90 ? 1 : 0} 1 `
    + `${corner(facing + half)} Z`;
}

export type Formation = 'line' | 'lines' | 'column';

/**
 * Where a group's regiments stand drawn up around a point, facing the enemy (side 0 up the map, side 1 down it):
 * in one line, side by side; in two lines, the second behind the first; or in column, one behind another.
 */
export function formation(units: { id: string; width: number; depth: number }[], centre: Point, side: 0 | 1,
  kind: Formation): Record<string, Point> {
  const back = side === 0 ? 1 : -1; // towards the side's own edge
  const row = (members: typeof units, y: number): Record<string, Point> => {
    const total = members.reduce((s, u) => s + u.width, 0) + GAP * Math.max(0, members.length - 1);
    let left = centre.x - total / 2;
    return Object.fromEntries(members.map((u) => {
      const at = { x: Math.round(left + u.width / 2), y: Math.round(y) };
      left += u.width + GAP;
      return [u.id, at];
    }));
  };
  if (kind === 'line') return row(units, centre.y);
  if (kind === 'lines') {
    const first = Math.ceil(units.length / 2);
    return { ...row(units.slice(0, first), centre.y - (back * LINE_GAP) / 2),
      ...row(units.slice(first), centre.y + (back * LINE_GAP) / 2) };
  }
  // a column, its head towards the enemy
  const length = units.reduce((s, u) => s + u.depth, 0) + 40 * Math.max(0, units.length - 1);
  let at = centre.y - (back * length) / 2;
  return Object.fromEntries(units.map((u) => {
    const y = at + (back * u.depth) / 2;
    at += back * (u.depth + 40);
    return [u.id, { x: Math.round(centre.x), y: Math.round(y) }];
  }));
}
