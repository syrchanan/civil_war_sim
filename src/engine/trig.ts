/**
 * Cosine and sine of an angle in degrees, bit-identical with the former Python engine's utils/trig.py.
 *
 * Library Math.sin / Math.cos may differ in the last bit between engines, so these use only + - * /: the angle is
 * reduced exactly to [-45, 45] degrees, turned into radians, and fed to fixed-order Taylor polynomials, in the
 * same operation order as Python.
 */

const RAD = 0.017453292519943295; // pi / 180

const S = [-1 / 6, 1 / 120, -1 / 5040, 1 / 362880, -1 / 39916800, 1 / 6227020800, -1 / 1307674368000];
const C = [-1 / 2, 1 / 24, -1 / 720, 1 / 40320, -1 / 3628800, 1 / 479001600, -1 / 87178291200, 1 / 20922789888000];

/** sin of r radians, |r| <= pi/4. */
function sinSmall(r: number): number {
  const z = r * r;
  let p = S[6];
  for (let i = 5; i >= 0; i--) p = S[i] + z * p;
  return r + r * (z * p);
}

/** cos of r radians, |r| <= pi/4. */
function cosSmall(r: number): number {
  const z = r * r;
  let p = C[7];
  for (let i = 6; i >= 0; i--) p = C[i] + z * p;
  return 1.0 + z * p;
}

/** [quarter turn 0-3, angle in [0, 90)] for any angle in degrees (Python's % semantics). */
function reduce(degrees: number): [number, number] {
  let d = degrees % 360.0;
  if (d < 0) d += 360.0;
  let quarter = 0;
  while (d >= 90.0 && quarter < 3) {
    d -= 90.0;
    quarter += 1;
  }
  if (d >= 90.0) return [0, 0.0]; // rounding at the very top of the turn
  return [quarter, d];
}

/** [cos, sin] of d degrees, 0 <= d < 90. */
function firstQuarter(d: number): [number, number] {
  if (d > 45.0) {
    const r = (90.0 - d) * RAD;
    return [sinSmall(r), cosSmall(r)];
  }
  const r = d * RAD;
  return [cosSmall(r), sinSmall(r)];
}

export function cosDeg(degrees: number): number {
  const [quarter, d] = reduce(degrees);
  const [c, s] = firstQuarter(d);
  return [c, -s, -c, s][quarter] + 0.0; // + 0.0: no negative zero
}

export function sinDeg(degrees: number): number {
  const [quarter, d] = reduce(degrees);
  const [c, s] = firstQuarter(d);
  return [s, c, -s, -c][quarter] + 0.0;
}
