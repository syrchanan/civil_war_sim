/**
 * Test helpers. The default layout opens with the lines 600 yards apart, out of musket range (as a real battle
 * opened), and spread across the field, so units far to one side are outside each other's front arc. Tests about
 * orders, the preview and the rounds draw the armies up close instead, so fire tells.
 */

import type { Store } from './store';

/**
 * Before the battle starts: each side stacked at one point, 60 yards apart and face to face, so every unit is
 * within close range and the front arc of every enemy.
 */
export function closeRanks(store: Store): void {
  for (const u of store.mapUnits.value) store.moveUnit(u.uid, { x: 1000, y: u.side === 0 ? 630 : 570 });
}
