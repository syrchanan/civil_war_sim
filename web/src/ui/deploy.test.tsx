// @vitest-environment jsdom
// Round 0: each player places their own regiments in their zone and sends the file; the admin loads both and opens
// round 1.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/preact';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { App, standingText } from './App';
import { PLAN_FORMAT, createStore, type Store } from './store';

beforeEach(() => localStorage.clear());
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

/** The admin's battle, deploying: both armies approved and round 0 opened. */
function deploying(): Store {
  const admin = createStore(1863);
  admin.approve(0);
  admin.approve(1);
  expect(admin.openDeployment()).toEqual([]);
  return admin;
}

/** A player's view of the deployment, from the player file the admin sent. */
function playerOf(admin: Store, side: 0 | 1): Store {
  const player = createStore(1, 'player');
  expect(player.open(admin.playerFileDownload(side).text)).toBeNull();
  return player;
}

const ownUnit = (s: Store, side: 0 | 1) => [...s.battle.value!.units.values()].find((u) => u.side === side)!.uid;

describe('store: round 0', () => {
  it('players send their places, the admin loads them and opens round 1', () => {
    const admin = deploying();
    expect(admin.playerFileDownload(0).name).toBe('player-1863-round-0-Union.json');
    const union = playerOf(admin, 0);
    const confederates = playerOf(admin, 1);
    expect([...union.battle.value!.units.values()].every((u) => u.side === 0)).toBe(true); // no enemy yet

    const uid = ownUnit(union, 0);
    union.moveUnit(uid, { x: 400, y: 1000 });
    union.faceUnit(uid, 30);
    const file = union.planDownload();
    expect(file.name).toBe('deployment-1863-Union.json');
    const plan = JSON.parse(file.text);
    expect(plan).toMatchObject({ format: PLAN_FORMAT, battle: { seed: 1863, round: 0 }, side: 0, orders: {} });
    expect(plan.positions[uid]).toEqual({ x: 400, y: 1000, facing: 30 });

    expect(admin.loadPlans([file, confederates.planDownload()])).toEqual([]);
    expect(admin.plansLoaded.value).toEqual({ 0: 'deployment-1863-Union.json', 1: 'deployment-1863-Confederate.json' });
    expect(admin.battle.value!.units.get(uid)!.regiment.position).toMatchObject({ x: 400, y: 1000, facing: 30 });
    expect(admin.openBattle()).toBeNull();
    expect(admin.battle.value!.plan.phase).toBe('battle');
    expect(admin.plansLoaded.value).toEqual({});
    expect(standingText(admin)).toBe('Round 1 of 4 · 1:00 pm');
    expect(admin.playerFileDownload(0).name).toBe('player-1863-round-1-Union.json');
  });

  it('a regiment left outside its zone keeps the battle closed until it is moved in', () => {
    const admin = deploying();
    const uid = ownUnit(admin, 1);
    expect(admin.outsideZone(uid)).toBe(false);
    admin.moveUnit(uid, { x: 1000, y: 1100 }); // in the Union's zone
    expect(admin.outsideZone(uid)).toBe(true);
    const name = admin.battle.value!.units.get(uid)!.name;
    expect(admin.openBattle()).toBe(`${name} stands outside its side's deployment zone.`);
    expect(admin.battle.value!.plan.phase).toBe('deployment');
    admin.moveUnit(uid, { x: 1000, y: 100 });
    expect(admin.openBattle()).toBeNull();
    expect(admin.outsideZone(uid)).toBe(false); // no zones once the battle is open
    expect(createStore(1).outsideZone('us_1mn')).toBe(false); // nor before there is a battle
  });

  it('what is wrong with an orders file around round 0', () => {
    const admin = deploying();
    const union = playerOf(admin, 0);
    const deployment = union.planDownload();

    const withOrders = JSON.parse(deployment.text);
    withOrders.orders = { [ownUnit(union, 0)]: { mode: 'idle' } };
    expect(admin.loadPlans([{ name: 'o.json', text: JSON.stringify(withOrders) }]))
      .toEqual(['o.json: a deployment gives no orders, only places.']);
    const early = { ...JSON.parse(deployment.text), battle: { ...withOrders.battle, round: 1 } };
    expect(admin.loadPlans([{ name: 'r1.json', text: JSON.stringify(early) }]))
      .toEqual(['r1.json: these orders are for round 1; the armies are still deploying (round 0).']);

    admin.openBattle();
    expect(admin.loadPlans([deployment]))
      .toEqual(['deployment-1863-Union.json: these orders are for round 0; the next round is 1.']);
  });

  it('nothing is aimed while deploying', () => {
    const admin = deploying();
    const uid = ownUnit(admin, 0);
    admin.clickUnit(uid);
    expect(admin.aiming.value).toBeNull();
  });
});

describe('the deployment panel', () => {
  it('a player sees how many stand in their zone, finds those outside, and sends the file', async () => {
    const saved: string[] = [];
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:x');
    vi.spyOn(URL, 'revokeObjectURL').mockReturnValue(undefined);
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      saved.push(this.download);
    });
    const union = playerOf(deploying(), 0);
    render(<App store={union} />);
    expect(screen.getByRole('tab', { name: 'Orders' }).getAttribute('aria-selected')).toBe('true');
    const panel = within(document.getElementById('panel-orders')!);
    const total = [...union.battle.value!.units.values()].length;
    expect(panel.getByText(`${total} of ${total} regiments inside your zone.`)).toBeTruthy();
    const uid = ownUnit(union, 0);
    act(() => union.moveUnit(uid, { x: 1000, y: 100 }));
    expect(panel.getByText(`${total - 1} of ${total} regiments inside your zone.`)).toBeTruthy();
    expect(document.querySelectorAll('.map-unit.outside')).toHaveLength(1);
    const name = union.battle.value!.units.get(uid)!.name;
    fireEvent.click(panel.getByRole('button', { name }));
    expect(union.focusedUnit.value).toBe(uid);
    fireEvent.click(screen.getByRole('button', { name: 'Send deployment' }));
    await waitFor(() => expect(saved).toEqual(['deployment-1863-Union.json']));
  });

  it('the admin sees whose deployment is in, and opens round 1', () => {
    const admin = deploying();
    const union = playerOf(admin, 0);
    render(<App store={admin} />);
    const panel = within(document.getElementById('panel-orders')!);
    const statuses = () => panel.getAllByRole('listitem').map((li) => li.textContent);
    expect(statuses()).toEqual(['UnionWaiting for the deployment', 'ConfederateWaiting for the deployment']);
    act(() => {
      admin.loadPlans([union.planDownload()]);
    });
    expect(statuses()).toEqual(['UnionDeployed: deployment-1863-Union.json', 'ConfederateWaiting for the deployment']);

    const uid = ownUnit(admin, 0);
    act(() => admin.moveUnit(uid, { x: 1000, y: 100 }));
    const open = panel.getByRole('button', { name: 'Open round 1' }) as HTMLButtonElement;
    expect(open.disabled).toBe(true);
    act(() => admin.moveUnit(uid, { x: 1000, y: 1000 }));
    expect(open.disabled).toBe(false);

    // a unit with no place at all (from a hand-made file) is named when opening
    act(() => {
      admin.battle.value!.units.get(uid)!.regiment.position = null;
      admin.touch();
    });
    fireEvent.click(open);
    expect(panel.getByRole('alert').textContent).toMatch(/has not been placed\.$/);
    act(() => admin.moveUnit(uid, { x: 1000, y: 1000 }));
    fireEvent.click(panel.getByRole('button', { name: 'Open round 1' }));
    expect(admin.battle.value!.plan.phase).toBe('battle');
    expect(document.querySelector('.standing')!.textContent).toBe('Round 1 of 4 · 1:00 pm');
    expect(screen.queryByRole('button', { name: 'Open round 1' })).toBeNull();
  });
});
