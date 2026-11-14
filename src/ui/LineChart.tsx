/**
 * A small line chart in plain SVG: one line per series, a point at each round's end, a legend, end labels for up
 * to four series, and a crosshair whose readout lists every series at the nearest round end (pointer or arrow
 * keys). Colors are the validated categorical slots in fixed order (--series-1 .. --series-8, style.css).
 */

import { useState } from 'preact/hooks';

import { niceTicks, type Series } from './chart';

const W = 600;
const H = 240;
const M = { left: 48, right: 136, top: 12, bottom: 28 };
const LABEL_GAP = 13; // minimum vertical gap between end labels

const color = (i: number) => `var(--series-${i + 1})`;
const fmt = (v: number) => (Number.isInteger(v) ? v.toLocaleString('en-US') : v.toFixed(1));

export function LineChart({ title, series }: { title: string; series: Series[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const xs = series[0].points.map(([x]) => x);
  const xMax = xs[xs.length - 1] || 1;
  const yTicks = niceTicks(Math.max(...series.flatMap((s) => s.points.map(([, y]) => y))));
  const yMax = yTicks[yTicks.length - 1];
  const px = (x: number) => M.left + (x / xMax) * (W - M.left - M.right);
  const py = (y: number) => H - M.bottom - (y / yMax) * (H - M.top - M.bottom);

  // end labels, nudged apart so they never overlap
  const ends = series.map((s, i) => ({ i, y: py(s.points[s.points.length - 1][1]) })).sort((a, b) => a.y - b.y);
  for (let k = 1; k < ends.length; k++) ends[k].y = Math.max(ends[k].y, ends[k - 1].y + LABEL_GAP);

  const nearest = (clientX: number, rect: DOMRect) => {
    const x = ((clientX - rect.left) / (rect.width || W)) * W;
    let best = 0;
    xs.forEach((v, k) => { if (Math.abs(px(v) - x) < Math.abs(px(xs[best]) - x)) best = k; });
    return best;
  };
  const onKey = (e: KeyboardEvent) => {
    const step = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
    if (step) setHover(Math.min(xs.length - 1, Math.max(0, (hover ?? (step > 0 ? -1 : xs.length)) + step)));
  };

  return (
    <figure class="chart">
      <figcaption>{title}</figcaption>
      {series.length > 1 && (
        <ul class="legend" aria-label={`${title} legend`}>
          {series.map((s, i) => <li><span class="swatch" style={{ background: color(i) }} />{s.name}</li>)}
        </ul>
      )}
      <div class="plot">
        <svg viewBox={`0 0 ${W} ${H}`} role="img" tabindex={0} aria-label={`${title}, by game minute; exact values in the round tables`}
          onPointerMove={(e) => setHover(nearest(e.clientX, e.currentTarget.getBoundingClientRect()))}
          onPointerLeave={() => setHover(null)} onKeyDown={onKey} onBlur={() => setHover(null)}>
          {yTicks.map((t) => (
            <g class="grid">
              <line x1={M.left} x2={W - M.right} y1={py(t)} y2={py(t)} />
              <text x={M.left - 6} y={py(t)} dy="0.32em" text-anchor="end">{fmt(t)}</text>
            </g>
          ))}
          {xs.map((x) => <text class="tick" x={px(x)} y={H - 8} text-anchor="middle">{x}</text>)}
          {hover !== null && <line class="crosshair" x1={px(xs[hover])} x2={px(xs[hover])} y1={M.top} y2={H - M.bottom} />}
          {series.map((s, i) => (
            <g class="series">
              <polyline fill="none" stroke={color(i)} stroke-width="2" stroke-linejoin="round"
                points={s.points.map(([x, y]) => `${px(x)},${py(y)}`).join(' ')} />
              {s.points.map(([x, y]) => <circle cx={px(x)} cy={py(y)} r="4" fill={color(i)} class="marker" />)}
            </g>
          ))}
          {series.length <= 4 && ends.map(({ i, y }) => (
            <text class="end-label" x={W - M.right + 8} y={y} dy="0.32em">{series[i].name}</text>
          ))}
        </svg>
        {hover !== null && (
          <div class={`tooltip${px(xs[hover]) > W / 2 ? ' flip' : ''}`} role="status"
            style={{ left: `${(px(xs[hover]) / W) * 100}%` }}>
            <strong>{xs[hover]} min</strong>
            {series.map((s, i) => (
              <div><span class="swatch" style={{ background: color(i) }} />{s.name}: {fmt(s.points[hover][1])}</div>
            ))}
          </div>
        )}
      </div>
    </figure>
  );
}
