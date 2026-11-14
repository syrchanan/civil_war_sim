import { describe, expect, it } from 'vitest';

import defaults from '../engine/defaults.json';
import { Terrain } from '../engine';
import { FIELD } from './field';
import { generateTerrain, gradientNoise, TERRAIN_PRESETS } from './terrainGen';

const cfg = defaults.terrain;

describe('gradient noise', () => {
  it('is smooth, bounded, zero on the lattice, and the same for the same seed', () => {
    const a = gradientNoise(7);
    const b = gradientNoise(7);
    const c = gradientNoise(8);
    const points = Array.from({ length: 200 }, (_, i) => [i * 0.137, i * 0.291]);
    expect(points.map(([x, y]) => a(x, y))).toEqual(points.map(([x, y]) => b(x, y)));
    expect(points.some(([x, y]) => a(x, y) !== c(x, y))).toBe(true);
    for (const [x, y] of points) expect(Math.abs(a(x, y))).toBeLessThanOrEqual(1);
    expect(a(3, 5)).toBe(0);
    expect(Math.abs(a(1.5, 2.5) - a(1.501, 2.5))).toBeLessThan(0.01);
  });
});

describe('generated terrain', () => {
  it('offers the presets from config, in order', () => {
    expect(TERRAIN_PRESETS).toEqual(Object.keys(cfg.presets));
    expect(TERRAIN_PRESETS).toContain('hills');
  });

  it('covers the field in cells, heights from 0 at the lowest ground, and loads as a Terrain', () => {
    const data = generateTerrain('hills', 1863);
    expect([data.columns * data.cell, data.rows * data.cell]).toEqual([FIELD.width, FIELD.height]);
    expect(Math.min(...data.heights)).toBe(0);
    expect(data.meta).toEqual({ preset: 'hills', seed: 1863 });
    expect(new Terrain(data).toDict()).toEqual(data);
    expect(data.heights.every((h) => Math.round(h * 10) / 10 === h)).toBe(true);       // a tenth of a yard
  });

  it('is the same for the same preset and seed, and differs otherwise', () => {
    expect(generateTerrain('hills', 5)).toEqual(generateTerrain('hills', 5));
    expect(generateTerrain('hills', 6).heights).not.toEqual(generateTerrain('hills', 5).heights);
  });

  it('flat ground has gentle relief, mountains steep; woods take about their share', () => {
    const relief = (p: string) => Math.max(...generateTerrain(p, 11).heights);
    expect(relief('flat')).toBeLessThan(relief('hills'));
    expect(relief('hills')).toBeLessThan(relief('mountains'));
    for (const preset of TERRAIN_PRESETS) {
      const t = generateTerrain(preset, 11);
      const forest = [...t.ground].filter((g) => g === 'f').length / t.ground.length;
      expect(forest).toBeCloseTo(cfg.presets[preset as keyof typeof cfg.presets].forest_share, 2);
    }
  });

  it('marks steep open ground rough, and only that', () => {
    const t = generateTerrain('mountains', 3);
    const at = (c: number, r: number) => t.heights[r * t.columns + c];
    let rough = 0;
    for (let r = 0; r < t.rows; r++) {
      for (let c = 0; c < t.columns; c++) {
        const g = t.ground[r * t.columns + c];
        const neighbours = [[c - 1, r], [c + 1, r], [c, r - 1], [c, r + 1]]
          .filter(([i, j]) => i >= 0 && j >= 0 && i < t.columns && j < t.rows);
        const slope = Math.max(...neighbours.map(([i, j]) => Math.abs(at(i, j) - at(c, r)))) / t.cell;
        if (g === 'r') {
          rough += 1;
          expect(slope).toBeGreaterThan(cfg.rough_slope);
        } else if (g === 'o') {
          expect(slope).toBeLessThanOrEqual(cfg.rough_slope);
        }
      }
    }
    expect(rough).toBeGreaterThan(0);
  });

  it('refuses an unknown preset', () => {
    expect(() => generateTerrain('swamp', 1)).toThrow('Unknown terrain preset swamp');
  });
});
