// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from '@testing-library/preact';
import { afterEach, describe, expect, it } from 'vitest';

import { App } from './App';
import { createStore } from './store';

afterEach(cleanup);

const setup = () => {
  const store = createStore(1863);
  render(<App store={store} />);
  return store;
};

describe('army builder', () => {
  it('shows each side with its units', () => {
    setup();
    const union = screen.getByRole('table', { name: 'Union units' });
    expect(within(union).getAllByRole('row')).toHaveLength(1 + 3);
    expect((screen.getByLabelText('1st Minnesota men') as HTMLInputElement).value).toBe('900');
    expect((screen.getByLabelText('Battery B guns') as HTMLInputElement).value).toBe('8');
    expect((screen.getByLabelText('1st Minnesota weapon') as HTMLSelectElement).value).toBe('1');
    expect(screen.getByLabelText('Battery B weapon').textContent).toContain('smoothbore guns');
  });

  it('edits a unit field by field', () => {
    const store = setup();
    fireEvent.input(screen.getByLabelText('1st Minnesota men'), { target: { value: '850' } });
    fireEvent.input(screen.getByLabelText('1st Minnesota experience'), { target: { value: '7' } });
    fireEvent.input(screen.getByLabelText('1st Minnesota morale'), { target: { value: '8' } });
    fireEvent.change(screen.getByLabelText('1st Minnesota weapon'), { target: { value: '2' } });
    fireEvent.click(screen.getByLabelText('1st Minnesota melee only'));
    fireEvent.change(screen.getByLabelText('1st Minnesota subtype'), { target: { value: 'light' } });
    fireEvent.input(screen.getByLabelText('1st Minnesota name'), { target: { value: '1st MN' } });
    expect(store.units.value[0]).toMatchObject({ name: '1st MN', size: 850, stats: '7/8/2/1', subtype: 'light' });
    fireEvent.click(screen.getByLabelText('1st MN melee only'));
    expect(store.units.value[0].stats).toBe('7/8/2/0');
  });

  it('changes type: artillery gets guns, a generic unit has no subtype', () => {
    const store = setup();
    fireEvent.change(screen.getByLabelText('15th Massachusetts type'), { target: { value: 'art' } });
    fireEvent.input(screen.getByLabelText('15th Massachusetts guns'), { target: { value: '6' } });
    expect(store.units.value[1]).toMatchObject({ type: 'art', subtype: 'battery', guns: 6 });
    fireEvent.input(screen.getByLabelText('15th Massachusetts guns'), { target: { value: '' } });
    expect(store.units.value[1].guns).toBeNaN();
    expect((screen.getByLabelText('15th Massachusetts guns') as HTMLInputElement).value).toBe('');
    fireEvent.change(screen.getByLabelText('15th Massachusetts type'), { target: { value: '' } });
    expect(store.units.value[1]).toMatchObject({ type: null, subtype: null, guns: null });
    expect(screen.queryByLabelText('15th Massachusetts subtype')).toBeNull();
  });

  it('adds, removes and clears units, and renames sides', () => {
    const store = setup();
    fireEvent.click(screen.getByRole('button', { name: 'Add unit to Confederate' }));
    expect(store.units.value.at(-1)).toMatchObject({ side: 1, name: 'Unit 1' });
    fireEvent.click(screen.getByRole('button', { name: 'Remove Unit 1' }));
    expect(store.units.value).toHaveLength(7);
    fireEvent.input(screen.getByLabelText('Side 2 name'), { target: { value: 'Rebels' } });
    expect(screen.getByRole('table', { name: 'Rebels units' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Clear all units' }));
    expect(store.units.value).toEqual([]);
  });

  it('sets or draws a seed', () => {
    const store = setup();
    fireEvent.input(screen.getByLabelText('Seed'), { target: { value: '42' } });
    expect(store.seed.value).toBe(42);
    fireEvent.click(screen.getByRole('button', { name: 'New seed' }));
    expect(store.seed.value).not.toBe(42);
  });

  it('lists the problems instead of starting', () => {
    setup();
    fireEvent.input(screen.getByLabelText('1st Minnesota men'), { target: { value: '0' } });
    fireEvent.click(screen.getByRole('button', { name: 'Start battle' }));
    expect(screen.getByRole('alert').textContent).toContain('1st Minnesota: men must be a whole number');
  });

  it('starts the battle: the order of battle replaces the builder, and can go back', () => {
    const store = setup();
    fireEvent.click(screen.getByRole('button', { name: 'Start battle' }));
    const oob = screen.getByRole('table', { name: 'Order of battle' });
    const union = within(oob).getAllByRole('row')[1];
    expect(union.textContent).toContain('Union');
    expect(union.textContent).toContain('1,672');
    expect(union.textContent).toContain('72 (1, 8 guns)');
    expect(union.textContent).toContain('—'); // no cavalry
    fireEvent.click(screen.getByRole('button', { name: /Change the armies/ }));
    expect(store.battle.value).toBeNull();
    expect(screen.getByRole('table', { name: 'Union units' })).toBeTruthy();
  });
});
