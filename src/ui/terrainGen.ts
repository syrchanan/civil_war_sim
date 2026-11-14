/**
 * The client's terrain generator (positions pass P4): the ground for a new battle, as the grid saved in the state
 * file (engine/terrain.ts reads it, in both languages). Generated once, here only; a saved battle carries its
 * terrain, so replays never regenerate it.
 *
 * Elevation follows the map pipeline (python/imperial_generals/map/elevation.py) with its presets (config/map.yaml
 * terrain_presets): fractal Brownian motion over gradient noise, normalised, raised to the preset's exponent,
 * base + (shaped − 0.5) × range feet; positions are converted from yards to map units and heights from feet to
 * yards above the lowest ground. Woods come from a second noise field (the preset's share of the field); steep open
 * ground is rough (config/terrain.yaml).
 */

import defaults from '../engine/defaults.json';
import { Rng, type TerrainData } from '../engine';
import { FIELD } from './field';

const cfg = defaults.terrain;
type Preset = keyof typeof cfg.presets;

export const TERRAIN_PRESETS: readonly string[] = Object.keys(cfg.presets);

const GRADIENTS: [number, number][] = [[1, 0], [-1, 0], [0, 1], [0, -1],
  [Math.SQRT1_2, Math.SQRT1_2], [-Math.SQRT1_2, Math.SQRT1_2], [Math.SQRT1_2, -Math.SQRT1_2], [-Math.SQRT1_2, -Math.SQRT1_2]];

const fade = (t: number): number => t * t * t * (t * (t * 6 - 15) + 10);

/** 2D gradient (Perlin) noise from a seed: smooth, about -1 to 1, 0 at whole-number points. */
export function gradientNoise(seed: number): (x: number, y: number) => number {
  const rng = new Rng(seed);
  const perm = Array.from({ length: 256 }, (_, i) => i);
  for (let i = 255; i > 0; i--) {
    const j = Math.floor(rng.random() * (i + 1));
    [perm[i], perm[j]] = [perm[j], perm[i]];
  }
  const hash = (i: number, j: number) => perm[(perm[i & 255] + j) & 255] & 7;
  const dot = (i: number, j: number, dx: number, dy: number) => {
    const [gx, gy] = GRADIENTS[hash(i, j)];
    return gx * dx + gy * dy;
  };
  return (x, y) => {
    const i = Math.floor(x);
    const j = Math.floor(y);
    const fx = x - i;
    const fy = y - j;
    const u = fade(fx);
    const v = fade(fy);
    const a = dot(i, j, fx, fy) + u * (dot(i + 1, j, fx - 1, fy) - dot(i, j, fx, fy));
    const b = dot(i, j + 1, fx, fy - 1) + u * (dot(i + 1, j + 1, fx - 1, fy - 1) - dot(i, j + 1, fx, fy - 1));
    // the largest a 2D gradient noise reaches is sqrt(1/2): scale it to about -1 to 1
    return Math.max(-1, Math.min(1, (a + v * (b - a)) * Math.SQRT2));
  };
}

interface Octaves {
  octaves: number;
  persistence: number;
  lacunarity: number;
  scale: number;
}

/** Fractal Brownian motion: octaves of noise, each finer and fainter, normalised to about -1 to 1. */
function fbm(noise: (x: number, y: number) => number, p: Octaves, x: number, y: number): number {
  let total = 0;
  let frequency = 1;
  let amplitude = 1;
  let max = 0;
  for (let k = 0; k < p.octaves; k++) {
    total += noise((x * frequency) / p.scale, (y * frequency) / p.scale) * amplitude;
    max += amplitude;
    amplitude *= p.persistence;
    frequency *= p.lacunarity;
  }
  return total / max;
}

/** The value at `share` of the way down the sorted values: that share of them is at or above it. */
export function threshold(values: number[], share: number): number {
  if (share <= 0) return Infinity;
  const sorted = [...values].sort((a, b) => b - a);
  return sorted[Math.max(0, Math.round(share * values.length) - 1)];
}

/** A new battle's ground from a preset (config/terrain.yaml presets) and a seed. */
export function generateTerrain(preset: string, seed: number): TerrainData {
  if (!(preset in cfg.presets)) throw new Error(`Unknown terrain preset ${preset}; one of ${TERRAIN_PRESETS.join(', ')}.`);
  const elevation = cfg.elevation[preset as Preset];
  const { forest_share: share } = cfg.presets[preset as Preset];
  const cell = cfg.cell;
  const columns = Math.round(FIELD.width / cell);
  const rows = Math.round(FIELD.height / cell);
  const land = gradientNoise(seed);
  const woods = gradientNoise((seed ^ 0x5bd1e995) >>> 0); // unsigned: seeds go up to 2^32 - 1
  const feet: number[] = [];
  const woodiness: number[] = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < columns; c++) {
      const x = (c + 0.5) * cell;
      const y = (r + 0.5) * cell;
      const n = fbm(land, elevation, x / cfg.yards_per_unit, y / cfg.yards_per_unit);
      const shaped = ((n + 1) / 2) ** elevation.exponent;
      feet.push(elevation.base_elevation + (shaped - 0.5) * elevation.elevation_range);
      woodiness.push(fbm(woods, { octaves: 3, persistence: 0.5, lacunarity: 2, scale: cfg.forest_scale }, x, y));
    }
  }
  const low = Math.min(...feet);
  const heights = feet.map((f) => Math.round(((f - low) / cfg.feet_per_yard) * 10) / 10);
  const cut = threshold(woodiness, share);
  const at = (c: number, r: number) => heights[r * columns + c];
  let ground = '';
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < columns; c++) {
      if (woodiness[r * columns + c] >= cut) {
        ground += 'f';
        continue;
      }
      const around = [[c - 1, r], [c + 1, r], [c, r - 1], [c, r + 1]]
        .filter(([i, j]) => i >= 0 && j >= 0 && i < columns && j < rows);
      const slope = Math.max(...around.map(([i, j]) => Math.abs(at(i, j) - at(c, r)))) / cell;
      ground += slope > cfg.rough_slope ? 'r' : 'o';
    }
  }
  return { cell, columns, rows, heights, ground, meta: { preset, seed } };
}
