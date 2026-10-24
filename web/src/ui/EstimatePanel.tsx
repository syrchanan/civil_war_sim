/** The next round fought 200 times: typical outcome and an 8-in-10 range per unit, and how charges tend to end. */

import type { Range } from '../engine';
import { CHARGE_OUTCOMES } from './format';
import type { Store } from './store';

const n = (v: number) => v.toLocaleString('en-US');
const spread = (r: Range) => `${n(r.p10)}–${n(r.p90)}`;
const pct = (v: number) => `${Math.round(v * 100)}%`;

export function EstimatePanel({ store, disabled }: { store: Store; disabled: boolean }) {
  const estimate = store.estimate.value;
  const units = store.battle.value!.units;
  const name = (uid: string) => units.get(uid)!.name;
  return (
    <div class="estimate">
      <h3>Estimate</h3>
      <div class="controls">
        <button disabled={disabled} onClick={() => store.runEstimate()}>Estimate the next round</button>
        {estimate !== null && !estimate.current && (
          <span class="note warn">This estimate is out of date: the orders, round length or battle changed.</span>
        )}
      </div>
      {estimate !== null && (
        <>
          <div class="table-wrap">
            <table aria-label="Estimate">
              <thead>
                <tr>
                  <th>Unit</th><th class="num">Losses, typical</th><th class="num">8 in 10</th>
                  <th class="num">Men left, typical</th><th class="num">8 in 10</th><th class="num">Breaks</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(estimate.result.units).map(([uid, u]) => (
                  <tr class={`side-${units.get(uid)!.side}`}>
                    <td>{name(uid)}</td>
                    <td class="num">{n(u.losses.p50)}</td>
                    <td class="num">{spread(u.losses)}</td>
                    <td class="num">{n(u.size.p50)}</td>
                    <td class="num">{spread(u.size)}</td>
                    <td class="num">{pct(u.breakChance)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {estimate.result.charges.length > 0 && (
            <ul aria-label="Charges in the estimate">
              {estimate.result.charges.map((c) => (
                <li>
                  {name(c.charger)} -&gt; {name(c.target)}:{' '}
                  {Object.entries(c.outcomes).map(([o, share]) => `${CHARGE_OUTCOMES[o]} ${pct(share)}`).join(', ')}
                </li>
              ))}
            </ul>
          )}
          <p class="note">
            From {estimate.result.runs} runs of the round with different dice. Typical: the middle run; 8 in 10:
            the range 8 runs in 10 fall in. Breaks: how often the unit ends the round broken.
          </p>
        </>
      )}
    </div>
  );
}
