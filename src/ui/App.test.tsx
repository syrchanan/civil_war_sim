// @vitest-environment jsdom
import { render, screen } from '@testing-library/preact';
import { describe, expect, it } from 'vitest';

import { App } from './App';

describe('App', () => {
  it('shows the title and the steps of a battle', () => {
    render(<App />);
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Imperial Generals');
    for (const step of ['Armies', 'Orders', 'Rounds', 'Result']) {
      expect(screen.getByRole('heading', { name: step })).toBeTruthy();
    }
  });
});
