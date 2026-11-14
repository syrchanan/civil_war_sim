// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/preact';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { App } from './App';
import { armyToCsv } from './armyCsv';
import { createStore } from './store';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const CSV = 'name,type,men,weapon\nIron Brigade,Infantry,1200,rifled musket\nBuford\'s Troopers,Cavalry,500,\n';

describe('store: army files', () => {
  it('download one side as CSV, named for the side', () => {
    const s = createStore(1);
    const file = s.armyDownload(1);
    expect(file.name).toBe('army-Confederate.csv');
    expect(file.text).toBe(armyToCsv(s.units.value.filter((u) => u.side === 1)));
  });

  it('loading replaces that side\'s units, with fresh ids; the other side is kept', () => {
    const s = createStore(1);
    const confederates = s.units.value.filter((u) => u.side === 1);
    expect(s.loadArmy(0, CSV)).toEqual([]);
    const union = s.units.value.filter((u) => u.side === 0);
    expect(union.map((u) => [u.name, u.type, u.size])).toEqual([['Iron Brigade', 'inf', 1200], ["Buford's Troopers", 'cav', 500]]);
    expect(new Set(s.units.value.map((u) => u.id)).size).toBe(s.units.value.length);
    expect(s.units.value.filter((u) => u.side === 1)).toEqual(confederates);
    expect(s.units.value.map((u) => u.side)).toEqual([0, 0, 1, 1, 1, 1]);   // sides stay together
  });

  it('a file with problems, or no units, changes nothing', () => {
    const s = createStore(1);
    const before = s.units.value;
    expect(s.loadArmy(0, 'name,men\nA,0\n')).toEqual(['Line 2: men must be a whole number, 1 or more.']);
    expect(s.loadArmy(0, 'name,men\n')).toEqual(['The file has no units.']);
    expect(s.units.value).toBe(before);
  });
});

describe('army builder: army files', () => {
  it('each side has download and load buttons; problems are shown for that side', async () => {
    const saved: string[] = [];
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:x');
    vi.spyOn(URL, 'revokeObjectURL').mockReturnValue(undefined);
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      saved.push(this.download);
    });
    const store = createStore(1);
    render(<App store={store} />);
    fireEvent.click(screen.getByRole('button', { name: 'Download Union army (CSV)' }));
    expect(saved).toEqual(['army-Union.csv']);
    const input = screen.getByLabelText('Load Confederate army (CSV)');
    fireEvent.change(input, { target: { files: [new File(['name,men\nA,x\n'], 'bad.csv')] } });
    const side = screen.getByLabelText('Side 2 name').closest('.side') as HTMLElement;
    await waitFor(() => expect(within(side).getByRole('alert').textContent).toBe('bad.csv: Line 2: men must be a whole number, 1 or more.'));
    fireEvent.change(input, { target: { files: [new File([CSV], 'good.csv')] } });
    await waitFor(() => expect(store.units.value.filter((u) => u.side === 1).map((u) => u.name))
      .toEqual(['Iron Brigade', "Buford's Troopers"]));
    expect(within(side).queryByRole('alert')).toBeNull();
    fireEvent.change(input, { target: { files: [] } });                // picking nothing does nothing
    expect(store.units.value.filter((u) => u.side === 1)).toHaveLength(2);
  });
});
