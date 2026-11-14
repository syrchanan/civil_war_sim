/**
 * The vignette as layers of pixels: the ground behind, the figures (one or more animation frames), and anything
 * in front of them (a trunk, a rock). Each layer becomes one SVG path per colour, so the art stays crisp at any
 * scale and needs no canvas.
 */

import type { Ground } from '../../engine';
import {
  CARBINE, FLASH, GRASS, GROUND_TOP, GUN, GUNNER, type Grid, HEIGHT, HORSE_GALLOP, HORSE_STAND, LEAVES, PEBBLES,
  RIDER, ROCK, SABRE_CUT, SABRE_POINT, SABRE_SLOPE, SABRE_UP, SMOKE_GUN, SMOKE_LARGE, SMOKE_SMALL, SOLDIER_AIM,
  SOLDIER_CHARGE, SOLDIER_IDLE, SOLDIER_RUN, SOLDIER_THRUST, SPARK, TREE, TRUNK, WIDTH,
} from './art';

export type Pose = 'idle' | 'firing' | 'charging' | 'melee' | 'broken';
export type Figure = 'inf' | 'cav' | 'art';

interface Place {
  grid: Grid;
  x: number;
  y: number;
  flip?: boolean;
}

/** One colour of a painted layer: the palette letter and the path of its pixels. */
export interface Paint {
  color: string;
  d: string;
}

export interface Scene {
  back: Paint[];
  frames: Paint[][];
  front: Paint[];
}

const widthOf = (grid: Grid): number => Math.max(...grid.map((row) => row.length));

const flipped = (grid: Grid): Grid => {
  const w = widthOf(grid);
  return grid.map((row) => row.padEnd(w, '.').split('').reverse().join(''));
};

/** Places on the ground: the grid's bottom row stands on the row above the ground. */
const stand = (grid: Grid, x: number, flip = false): Place => ({ grid, x, y: GROUND_TOP - grid.length, flip });

/** Paints places in order (later ones over earlier), clipped to the scene; runs of one colour merge. */
export function paint(places: Place[]): Paint[] {
  const cells: string[] = Array(WIDTH * HEIGHT).fill('.');
  for (const p of places) {
    const grid = p.flip ? flipped(p.grid) : p.grid;
    grid.forEach((row, dy) => {
      const y = p.y + dy;
      for (let dx = 0; dx < row.length; dx++) {
        const x = p.x + dx;
        if (row[dx] !== '.' && x >= 0 && x < WIDTH && y >= 0 && y < HEIGHT) cells[y * WIDTH + x] = row[dx];
      }
    });
  }
  const paths = new Map<string, string>();
  for (let y = 0; y < HEIGHT; y++) {
    let x = 0;
    while (x < WIDTH) {
      const c = cells[y * WIDTH + x];
      let n = 1;
      while (x + n < WIDTH && cells[y * WIDTH + x + n] === c) n++;
      if (c !== '.') paths.set(c, `${paths.get(c) ?? ''}M${x} ${y}h${n}v1h-${n}z`);
      x += n;
    }
  }
  return [...paths].map(([color, d]) => ({ color, d }));
}

// a rolling volley: each figure is a frame further along than the one before
const VOLLEY = ['aim', 'flash', 'smoke', 'aim'] as const;
const FILE = [2, 16, 30]; // where the infantry stand, left to right
const MOUNTS = [1, 24]; // where the horses stand

function infantry(pose: Pose): Place[][] {
  const idle = SOLDIER_IDLE;
  const top = GROUND_TOP - SOLDIER_AIM.length;
  switch (pose) {
    case 'idle':
      return [FILE.map((x) => stand(idle, x))];
    case 'firing':
      // each man drawn after the smoke of the man to his left, so the smoke drifts behind him
      return VOLLEY.map((_, f) => FILE.flatMap((x, k): Place[] => {
        const man = stand(SOLDIER_AIM, x);
        const phase = VOLLEY[(f + k) % VOLLEY.length];
        if (phase === 'flash') return [man, { grid: FLASH, x: x + 14, y: top + 4 }];
        if (phase === 'smoke') return [man, { grid: SMOKE_LARGE, x: x + 13, y: top + 2 }];
        return [man];
      }));
    case 'charging':
      return [0, 1].map((f) => FILE.map((x, k) => stand(SOLDIER_CHARGE[(f + k) % 2], x)));
    case 'melee':
      return [0, 1].map((f) => FILE.flatMap((x, k): Place[] => {
        const lunge = (f + k) % 2 === 0;
        const man = stand(SOLDIER_THRUST, lunge ? x + 2 : x);
        return lunge ? [man, { grid: SPARK, x: x + 16, y: man.y + 7 }] : [man];
      }));
    case 'broken':
      return [0, 1].map((f) => FILE.map((x, k) => stand(SOLDIER_RUN[(f + k) % 2], WIDTH - x - 15, true)));
  }
}

function cavalry(pose: Pose): Place[][] {
  const hy = GROUND_TOP - HORSE_STAND.length;
  const mounted = (horse: Grid, hx: number, arms: (rx: number, ry: number) => Place[]): Place[] => {
    const rx = hx + 6;
    const ry = hy - 3;
    return [{ grid: horse, x: hx, y: hy }, { grid: RIDER, x: rx, y: ry }, ...arms(rx, ry)];
  };
  switch (pose) {
    case 'idle':
      return [MOUNTS.flatMap((hx) => mounted(HORSE_STAND, hx, (rx, ry) => [{ grid: SABRE_SLOPE, x: rx + 5, y: ry + 4 }]))];
    case 'firing':
      return VOLLEY.map((_, f) => MOUNTS.flatMap((hx, k) => mounted(HORSE_STAND, hx, (rx, ry) => {
        const phase = VOLLEY[(f + 2 * k) % VOLLEY.length];
        const carbine = { grid: CARBINE, x: rx + 3, y: ry + 4 };
        if (phase === 'flash') return [carbine, { grid: FLASH, x: rx + 12, y: ry + 3 }];
        if (phase === 'smoke') return [carbine, { grid: SMOKE_SMALL, x: rx + 12, y: ry + 3 }];
        return [carbine];
      })));
    case 'charging':
      return [0, 1].map((f) => MOUNTS.flatMap((hx, k) => mounted(HORSE_GALLOP[(f + k) % 2], hx,
        (rx, ry) => [{ grid: SABRE_POINT, x: rx + 4, y: ry + 6 }])));
    case 'melee':
      return [0, 1].map((f) => MOUNTS.flatMap((hx, k) => mounted(HORSE_GALLOP[1], hx, (rx, ry) => ((f + k) % 2 === 0
        ? [{ grid: SABRE_UP, x: rx + 6, y: ry + 1 }]
        : [{ grid: SABRE_CUT, x: rx + 4, y: ry + 6 }, { grid: SPARK, x: rx + 11, y: ry + 8 }]))));
    case 'broken':
      // the whole troop turned about: each piece flipped and mirrored across the scene
      return [0, 1].map((f) => MOUNTS.flatMap((hx, k) => mounted(HORSE_GALLOP[(f + k) % 2], hx, () => []))
        .map((p) => ({ ...p, flip: true, x: WIDTH - p.x - widthOf(p.grid) })));
  }
}

function artillery(pose: Pose): Place[][] {
  const gx = 20;
  const gy = GROUND_TOP - GUN.length;
  const crew = [stand(GUNNER, 2), stand(GUNNER, 11)];
  switch (pose) {
    case 'firing':
      return [
        [...crew, { grid: GUN, x: gx, y: gy }],
        [...crew, { grid: GUN, x: gx - 2, y: gy }, { grid: FLASH, x: gx + 19, y: gy + 2 }],
        [...crew, { grid: GUN, x: gx - 2, y: gy }, { grid: SMOKE_GUN, x: gx + 17, y: gy - 2 }],
        [...crew, { grid: GUN, x: gx, y: gy }, { grid: SMOKE_LARGE, x: gx + 19, y: gy - 1 }],
      ];
    case 'broken':
      // the gun left standing, its crew running for the rear
      return [0, 1].map((f) => [
        { grid: GUN, x: gx, y: gy },
        stand(SOLDIER_RUN[f], 0, true), stand(SOLDIER_RUN[1 - f], 9, true),
      ]);
    default:
      // a battery doesn't charge; in melee its crew stand to the gun
      return [[...crew, { grid: GUN, x: gx, y: gy }]];
  }
}

const grass: Place = { grid: GRASS, x: 0, y: GROUND_TOP };

const BACK: Record<Ground, Place[]> = {
  open: [grass],
  rough: [grass, { grid: ROCK, x: 8, y: GROUND_TOP - 2 }, { grid: ROCK, x: 27, y: GROUND_TOP - 1 },
    { grid: PEBBLES, x: 18, y: GROUND_TOP + 1 }, { grid: PEBBLES, x: 38, y: GROUND_TOP + 2 }],
  forest: [grass, { grid: TREE, x: 8, y: 0 }, { grid: TREE, x: 24, y: 0 }, { grid: TREE, x: 38, y: 0 }],
};

const FRONT: Record<Ground, Place[]> = {
  open: [],
  rough: [{ grid: ROCK, x: 43, y: GROUND_TOP - 1 }, { grid: PEBBLES, x: 2, y: GROUND_TOP + 2 }],
  forest: [{ grid: LEAVES, x: 0, y: 0 }, { grid: TRUNK, x: 0, y: 0 }, { grid: TRUNK, x: WIDTH - 3, y: 0 }],
};

const FIGURES: Record<Figure, (pose: Pose) => Place[][]> = { inf: infantry, cav: cavalry, art: artillery };

/** The vignette for a kind of unit doing something on some ground. */
export function scene(figure: Figure, pose: Pose, ground: Ground): Scene {
  return { back: paint(BACK[ground]), frames: FIGURES[figure](pose).map(paint), front: paint(FRONT[ground]) };
}
