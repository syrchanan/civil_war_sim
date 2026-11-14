import { describe, expect, it } from 'vitest';

import { MAX_SERIES, niceTicks, seriesFor } from './chart';
import { createStore } from './store';

const fought = (rounds: number) => {
  const s = createStore(1863);
  s.start();
  s.setOrder('us_1mn', { mode: 'ranged', target: 'cs_8al' });
  s.setOrder('cs_8al', { mode: 'ranged', target: 'us_1mn' });
  for (let i = 0; i < rounds; i++) s.resolve();
  return s;
};

describe('chart data', () => {
  it('men in the ranks per unit: the start, then each round end', () => {
    const s = fought(2);
    const series = seriesFor(s.battle.value!, 0, 'men');
    expect(series.map((x) => x.name)).toEqual(['1st Minnesota', '15th Massachusetts', 'Battery B']);
    const mn = series[0].points;
    const history = s.history.value;
    expect(mn).toEqual([[0, 900], [60, history[0].units.us_1mn.size], [120, history[1].units.us_1mn.size]]);
  });

  it('morale per unit starts at its starting raw morale', () => {
    const s = fought(1);
    const series = seriesFor(s.battle.value!, 1, 'morale');
    expect(series[0].points[0]).toEqual([0, 60]);
    expect(series[0].points[1]).toEqual([60, s.history.value[0].units.cs_8al.morale]);
  });

  it('caps a side at the palette size', () => {
    const s = createStore(1);
    s.clearUnits();
    for (let i = 0; i < MAX_SERIES + 2; i++) s.addUnit(0);
    s.addUnit(1);
    s.start();
    expect(seriesFor(s.battle.value!, 0, 'men')).toHaveLength(MAX_SERIES);
  });

  it.each([
    [0, [0, 1]], [1, [0, 0.2, 0.4, 0.6, 0.8, 1]], [7, [0, 2, 4, 6, 8]], [60, [0, 20, 40, 60]], [900, [0, 200, 400, 600, 800, 1000]],
    [1672, [0, 500, 1000, 1500, 2000]], [35, [0, 10, 20, 30, 40]],
  ])('nice ticks up to %s', (max, ticks) => {
    expect(niceTicks(max)).toEqual(ticks);
  });
});
