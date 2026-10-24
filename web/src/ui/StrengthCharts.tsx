/** Men in the ranks and morale over game time, one chart per side (small multiples: never two y-axes). */

import { MAX_SERIES, type Measure, seriesFor } from './chart';
import { LineChart } from './LineChart';
import type { Store } from './store';

const MEASURES: [Measure, string][] = [['men', 'Men in the ranks'], ['morale', 'Morale (raw, 10–100)']];

export function StrengthCharts({ store }: { store: Store }) {
  store.revision.value; // redraw after every round
  const battle = store.battle.value!;
  const sides = store.sides.value;
  return (
    <div class="charts">
      {MEASURES.map(([measure, label]) => [0, 1].filter((side) => side !== store.hiddenSide.value).map((side) => {
        const count = [...battle.units.values()].filter((u) => u.side === side).length;
        return (
          <div>
            <LineChart title={`${sides[side]}: ${label}`} series={seriesFor(battle, side, measure)} />
            {count > MAX_SERIES && <p class="note">Showing the first {MAX_SERIES} of {count} units; all are in the tables.</p>}
          </div>
        );
      }))}
    </div>
  );
}
