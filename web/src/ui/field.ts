/**
 * The map: a plain field in yards, and how big each unit is drawn on it. Display only: the engine ignores
 * positions (no range, cover or elevation yet).
 */

/** The field, in yards. */
export const FIELD = { width: 2000, height: 1200 };

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

/**
 * Where units start: side 0 in a line across the lower part of the field, side 1 across the upper part, each
 * line centred, wrapping to a second line behind the first when it runs out of room.
 */
export function defaultLayout(units: { id: string; side: 0 | 1; width: number }[]): Record<string, Point> {
  const layout: Record<string, Point> = {};
  for (const side of [0, 1] as const) {
    const front = side === 0 ? FIELD.height * 0.75 : FIELD.height * 0.25;
    const back = side === 0 ? LINE_GAP : -LINE_GAP;
    const lines: { id: string; width: number }[][] = [[]];
    let used = 0; // yards taken in the current line
    for (const u of units.filter((u) => u.side === side)) {
      const line = lines[lines.length - 1];
      const need = line.length ? used + GAP + u.width : u.width;
      if (line.length && need > FIELD.width - 2 * MARGIN) {
        lines.push([u]);
        used = u.width;
      } else {
        line.push(u);
        used = need;
      }
    }
    lines.forEach((line, n) => {
      const total = line.reduce((s, u) => s + u.width, 0) + GAP * Math.max(0, line.length - 1);
      let left = (FIELD.width - total) / 2;
      for (const u of line) {
        layout[u.id] = { x: Math.round(left + u.width / 2), y: front + n * back }; // whole yards
        left += u.width + GAP;
      }
    });
  }
  return layout;
}

/** A point kept on the field, in whole yards. */
export function clampToField(p: Point): Point {
  return {
    x: Math.round(Math.min(FIELD.width, Math.max(0, p.x))),
    y: Math.round(Math.min(FIELD.height, Math.max(0, p.y))),
  };
}
