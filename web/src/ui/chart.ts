/** Chart data: each unit's men in the ranks or morale over game time, from the battle's round history. */

import type { Battle } from '../engine';

/** Series per chart: the palette has eight categorical hues, never cycled. */
export const MAX_SERIES = 8;

export type Measure = 'men' | 'morale';
export interface Series {
  uid: string;
  name: string;
  points: [number, number][]; // [game minute, value]
}

/** One series per unit of `side` (the first MAX_SERIES): its value at the start and at each round's end. */
export function seriesFor(battle: Battle, side: number, measure: Measure): Series[] {
  const units = [...battle.units.values()].filter((u) => u.side === side).slice(0, MAX_SERIES);
  return units.map((u) => ({
    uid: u.uid,
    name: u.name,
    points: [
      [0, measure === 'men' ? u.initialSize : u.morale.initialMorale],
      ...battle.history.map((r): [number, number] => [r.end, measure === 'men' ? r.units[u.uid].size : r.units[u.uid].morale]),
    ],
  }));
}

/** Round axis ticks from 0 to at least `max`: the smallest step of 1, 2 or 5 × a power of ten that needs at most
 * five intervals. */
export function niceTicks(max: number): number[] {
  if (max <= 0) return [0, 1];
  const power = 10 ** Math.floor(Math.log10(max / 5));
  const step = [1, 2, 5, 10].map((m) => m * power).find((s) => max / s <= 5)!;
  const top = Math.ceil(max / step) * step;
  const ticks: number[] = [];
  for (let i = 0; i <= Math.round(top / step); i++) ticks.push(Number((i * step).toPrecision(12)));
  return ticks;
}
