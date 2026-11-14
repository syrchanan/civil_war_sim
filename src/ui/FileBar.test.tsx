// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/preact';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { App } from './App';
import { createStore } from './store';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('file bar', () => {
  it('downloads the battle state file once a battle has started', () => {
    const store = createStore(1863);
    render(<App store={store} />);
    const button = screen.getByRole('button', { name: 'Download battle' }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Start battle' }));

    const created: Blob[] = [];
    URL.createObjectURL = vi.fn((blob: Blob) => { created.push(blob); return 'blob:battle'; });
    URL.revokeObjectURL = vi.fn();
    const clicks: string[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      clicks.push(`${this.download} ${this.href}`);
    });
    fireEvent.click(screen.getByRole('button', { name: 'Download battle' }));
    expect(clicks).toEqual(['battle-1863-round-0.json blob:battle']);
    expect(created[0].type).toBe('application/json');
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:battle');
  });

  it('opens a saved battle', async () => {
    const saved = createStore(1863);
    saved.start();
    saved.resolve();
    const store = createStore(1);
    render(<App store={store} />);
    const file = new File([saved.download().text], 'battle.json', { type: 'application/json' });
    fireEvent.change(screen.getByLabelText('Open a saved battle'), { target: { files: [file] } });
    await waitFor(() => expect(store.history.value).toHaveLength(1));
    expect(screen.getByRole('table', { name: 'Round 1' })).toBeTruthy();
  });

  it('says what is wrong with a file that is not a battle', async () => {
    render(<App store={createStore(1)} />);
    const file = new File(['{"format": "x"}'], 'other.json');
    fireEvent.change(screen.getByLabelText('Open a saved battle'), { target: { files: [file] } });
    await waitFor(() => expect(screen.getByRole('alert').textContent).toBe('other.json: Not a battle state file (format "x").'));
  });

  it('does nothing when no file was picked', () => {
    const store = createStore(1);
    render(<App store={store} />);
    fireEvent.change(screen.getByLabelText('Open a saved battle'), { target: { files: [] } });
    expect(store.battle.value).toBeNull();
  });
});
