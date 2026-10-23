/** How the client words a battle: the same phrases as the Python CLI (python/imperial_generals/cli.py). */

import type { Charge } from '../engine';

export const CHARGE_OUTCOMES: Record<string, string> = {
  home: 'went home', faltered: 'faltered', defender_broke: 'broke the defender before contact',
  meeting: 'met head on', pursuit: 'pursuit', charger_broke: 'charger broke on the approach',
  target_broke: 'target broke before contact',
};

const pct = (x: number): string => `${Math.round(x * 100)}%`;

/** 'wiped out', 'broke at 34 min', 'broken', plus guns lost. */
export function status(size: number, broken: boolean, brokeAt: number | null, gunsLost = 0): string {
  const notes: string[] = [];
  if (size === 0) notes.push('wiped out');
  else if (brokeAt !== null) notes.push(`broke at ${brokeAt.toFixed(0)} min`);
  else if (broken) notes.push('broken');
  if (gunsLost) notes.push(`${gunsLost} gun${gunsLost === 1 ? '' : 's'} lost`);
  return notes.join(', ');
}

/** '8th Alabama -> 1st Minnesota: went home at 65 min (61% to go home, 27% falter, 12% break)'. */
export function chargeText(c: Charge, name: (uid: string) => string): string {
  let text = `${name(c.charger)} -> ${name(c.target)}: ${CHARGE_OUTCOMES[c.outcome]} at ${c.resolved_at.toFixed(0)} min`;
  if (c.p_home !== null) {
    text += ` (${pct(c.p_home)} to go home, ${pct(c.p_falter!)} falter, ${pct(c.p_defender_breaks!)} break)`;
  }
  return text;
}
