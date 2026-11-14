/**
 * Terrain (port of the former Python engine's battles/terrain.py): the ground a battle is fought on, as a grid saved in
 * the state file. Heights (yards above the lowest ground) are taken at cell centres and interpolated between them;
 * ground is the letter of the containing cell (o open, f forest, r rough). Points off the grid take the nearest edge.
 */

import { ValueError } from './errors';

export const GROUND = { o: 'open', f: 'forest', r: 'rough' } as const;
export type GroundCode = keyof typeof GROUND;
export type Ground = (typeof GROUND)[GroundCode];

export interface TerrainData {
  cell: number;
  columns: number;
  rows: number;
  heights: number[];
  ground: string;
  meta: Record<string, unknown>;
}

const whole = (v: unknown): v is number => typeof v === 'number' && Number.isInteger(v);
const finite = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);

/** [lower index, share towards the next] along one axis, between cell centres; level beyond them. */
function axis(v: number, cell: number, count: number): [number, number] {
  const f = v / cell - 0.5;
  if (count === 1 || f <= 0) return [0, 0.0];
  if (f >= count - 1) return [count - 2, 1.0];
  const i = Math.floor(f);
  return [i, f - i];
}

export class Terrain {
  readonly cell: number;
  readonly columns: number;
  readonly rows: number;
  readonly heights: readonly number[];
  readonly ground: string;
  readonly meta: Record<string, unknown>;

  constructor(data: TerrainData) {
    if (!(finite(data.cell) && data.cell > 0)) throw new ValueError('cell must be a positive number of yards.');
    for (const name of ['columns', 'rows'] as const) {
      if (!(whole(data[name]) && data[name] > 0)) throw new ValueError(`${name} must be a positive whole number.`);
    }
    const n = data.columns * data.rows;
    if (!Array.isArray(data.heights) || data.heights.length !== n || !data.heights.every(finite)) {
      throw new ValueError(`heights must be ${n} numbers (columns × rows, row by row).`);
    }
    if (typeof data.ground !== 'string' || data.ground.length !== n || [...data.ground].some((c) => !(c in GROUND))) {
      throw new ValueError(`ground must be ${n} letters, each one of o, f, r (open, forest, rough).`);
    }
    const meta = data.meta ?? {};
    if (typeof meta !== 'object' || meta === null || Array.isArray(meta)) throw new ValueError('meta must be a mapping.');
    this.cell = data.cell;
    this.columns = data.columns;
    this.rows = data.rows;
    this.heights = [...data.heights];
    this.ground = data.ground;
    this.meta = structuredClone(meta);
    Object.freeze(this);
  }

  get width(): number {
    return this.columns * this.cell;
  }

  get height(): number {
    return this.rows * this.cell;
  }

  private h(column: number, row: number): number {
    return this.heights[row * this.columns + column];
  }

  /** Yards above the lowest ground at (x, y), interpolated between cell centres. */
  heightAt(x: number, y: number): number {
    const [i, tx] = axis(x, this.cell, this.columns);
    const [j, ty] = axis(y, this.cell, this.rows);
    const i1 = Math.min(i + 1, this.columns - 1);
    const j1 = Math.min(j + 1, this.rows - 1);
    const a = this.h(i, j) + (this.h(i1, j) - this.h(i, j)) * tx;
    const b = this.h(i, j1) + (this.h(i1, j1) - this.h(i, j1)) * tx;
    return a + (b - a) * ty;
  }

  /** 'open', 'forest' or 'rough': the cell containing (x, y); off the grid, the nearest edge cell. */
  groundAt(x: number, y: number): Ground {
    const column = Math.min(this.columns - 1, Math.max(0, Math.floor(x / this.cell)));
    const row = Math.min(this.rows - 1, Math.max(0, Math.floor(y / this.cell)));
    return GROUND[this.ground[row * this.columns + column] as GroundCode];
  }

  toDict(): TerrainData {
    return {
      cell: this.cell, columns: this.columns, rows: this.rows, heights: [...this.heights], ground: this.ground,
      meta: structuredClone(this.meta),
    };
  }

  static fromDict(data: TerrainData): Terrain {
    return new Terrain(data);
  }
}
