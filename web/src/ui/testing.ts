/**
 * Test helpers. The default layout opens with the lines 600 yards apart, out of musket range (as a real battle
 * opened); tests about orders, the preview and the rounds draw the lines up close instead, so fire tells.
 */

import type { Store } from './store';

/** Before the battle starts: the two lines 60 yards apart in the middle of the field, within close range. */
export function closeRanks(store: Store): void {
  for (const u of store.mapUnits.value) store.moveUnit(u.uid, { x: u.x, y: u.side === 0 ? 630 : 570 });
}
