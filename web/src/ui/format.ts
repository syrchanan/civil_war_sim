/** How the client words a battle: the same phrases as the Python CLI (python/imperial_generals/cli.py). */

import type { BattleResult, Charge, Modifier } from '../engine';

export const CHARGE_OUTCOMES: Record<string, string> = {
  home: 'went home', faltered: 'faltered', defender_broke: 'broke the defender before contact',
  meeting: 'met head on', pursuit: 'pursuit', charger_broke: 'charger broke on the approach',
  target_broke: 'target broke before contact',
};

/** An admin's modifiers in words: 'fire -15%, morale +10% (uphill)'; only what is set. */
export function modifierText(mod: Modifier): string {
  const changes = (['fire', 'melee', 'morale'] as const).filter((key) => mod[key] !== 0)
    .map((key) => `${key} ${mod[key] > 0 ? '+' : ''}${Math.round(mod[key] * 100)}%`).join(', ');
  return [changes, mod.note ? `(${mod.note})` : ''].filter(Boolean).join(' ');
}

const FIELD_TESTS: [string, string][] = [['exchange', 'casualty exchange'], ['routs', 'routs'],
  ['standing', 'strength standing']];

/** Who held the field and how it was decided: the whole army out, the votes, or named by the admin. */
export function fieldText(result: Pick<BattleResult, 'field_held_by' | 'field_decided_by' | 'field_votes'>,
  sides: readonly string[]): string {
  const holder = result.field_held_by;
  const who = holder === null ? 'nobody, a draw' : sides[holder];
  let why: string;
  if (result.field_decided_by === 'army_out') {
    why = `the whole ${sides[1 - holder!]} army broke`;
  } else if (result.field_decided_by === 'votes') {
    const votes = result.field_votes as Record<string, number | null>;
    why = 'votes: ' + FIELD_TESTS.map(([test, label]) => `${label} ${votes[test] === null ? '-' : sides[votes[test]!]}`)
      .join(', ');
  } else {
    why = 'named by the admin';
  }
  return `Field held by: ${who} (${why})`;
}

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
