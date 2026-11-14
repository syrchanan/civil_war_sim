// The vignette's pixel art: every grid is drawable, layers paint to merged paths, every scene has its frames.
import { describe, expect, it } from 'vitest';

import * as art from './art';
import { PALETTE, UNIFORMS } from './palette';
import { type Figure, paint, type Pose, scene } from './render';

const grids = Object.entries(art).flatMap(([name, v]): [string, string[]][] => {
  if (!Array.isArray(v)) return [];
  return typeof v[0] === 'string' ? [[name, v as string[]]] : (v as string[][]).map((grid, i) => [`${name}[${i}]`, grid]);
});

describe('art', () => {
  it.each(grids)('%s uses only palette letters and fits the scene', (_, grid) => {
    for (const row of grid) for (const c of row) expect(c === '.' || c in UNIFORMS[0] || c in PALETTE, c).toBe(true);
    expect(grid.length).toBeLessThanOrEqual(art.HEIGHT);
    expect(Math.max(...grid.map((r) => r.length))).toBeLessThanOrEqual(art.WIDTH);
  });

  it('each side\'s uniform has the same pieces, none of them a palette letter', () => {
    expect(Object.keys(UNIFORMS[1])).toEqual(Object.keys(UNIFORMS[0]));
    for (const c of Object.keys(UNIFORMS[0])) expect(c in PALETTE).toBe(false);
  });

  it('a gunner is a soldier with a rammer', () => {
    expect(art.GUNNER.join('')).not.toContain('m');
    expect(art.GUNNER).toHaveLength(art.SOLDIER_IDLE.length);
  });
});

describe('paint', () => {
  it('merges runs of one colour into one path per colour', () => {
    expect(paint([{ grid: ['kkf', '.k.'], x: 1, y: 2 }])).toEqual([
      { color: 'k', d: 'M1 2h2v1h-2zM2 3h1v1h-1z' },
      { color: 'f', d: 'M3 2h1v1h-1z' },
    ]);
  });

  it('paints later places over earlier ones; clear pixels let what is under show', () => {
    expect(paint([{ grid: ['kk'], x: 0, y: 0 }, { grid: ['.f'], x: 0, y: 0 }]))
      .toEqual([{ color: 'k', d: 'M0 0h1v1h-1z' }, { color: 'f', d: 'M1 0h1v1h-1z' }]);
  });

  it('flips a place left to right, ragged rows included', () => {
    expect(paint([{ grid: ['kf', 'm'], x: 0, y: 0, flip: true }])).toEqual([
      { color: 'f', d: 'M0 0h1v1h-1z' },
      { color: 'k', d: 'M1 0h1v1h-1z' },
      { color: 'm', d: 'M1 1h1v1h-1z' },
    ]);
  });

  it('clips what falls outside the scene', () => {
    expect(paint([{ grid: ['kk'], x: -1, y: 0 }, { grid: ['k'], x: art.WIDTH, y: 0 }, { grid: ['k'], x: 0, y: -1 },
      { grid: ['k'], x: 0, y: art.HEIGHT }])).toEqual([{ color: 'k', d: 'M0 0h1v1h-1z' }]);
  });
});

describe('scene', () => {
  const frames: Record<Figure, Record<Pose, number>> = {
    inf: { idle: 1, firing: 4, charging: 2, melee: 2, broken: 2 },
    cav: { idle: 1, firing: 4, charging: 2, melee: 2, broken: 2 },
    art: { idle: 1, firing: 4, charging: 1, melee: 1, broken: 2 },
  };
  const cases = Object.entries(frames).flatMap(([figure, poses]) => Object.entries(poses)
    .flatMap(([pose, n]) => (['open', 'forest', 'rough'] as const).map((ground) => [figure, pose, ground, n] as const)));

  it.each(cases)('%s %s on %s ground: %i frames, each drawn, the ground behind', (figure, pose, ground, n) => {
    const s = scene(figure as Figure, pose as Pose, ground);
    expect(s.frames).toHaveLength(n);
    for (const f of s.frames) expect(f.some((p) => p.color === 'S')).toBe(true);
    expect(s.back.some((p) => p.color === 'l')).toBe(true);
    expect(s.front.length > 0).toBe(ground !== 'open');
  });

  it('animated frames differ from one another', () => {
    for (const [figure, poses] of Object.entries(frames)) {
      for (const pose of Object.keys(poses)) {
        const s = scene(figure as Figure, pose as Pose, 'open');
        expect(new Set(s.frames.map((f) => JSON.stringify(f))).size, `${figure} ${pose}`).toBe(s.frames.length);
      }
    }
  });

  it('a battery has no charge: it shows the crew standing to the gun', () => {
    expect(scene('art', 'charging', 'open')).toEqual(scene('art', 'idle', 'open'));
    expect(scene('art', 'melee', 'open')).toEqual(scene('art', 'idle', 'open'));
  });
});
