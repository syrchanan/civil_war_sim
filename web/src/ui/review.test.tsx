// @vitest-environment jsdom
// The admin's review of each army: what was left out of its file, what is wrong with it, approving it or sending it
// back with a note.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/preact';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { App } from './App';
import { glance } from './ArmyReview';
import { createStore, type Store } from './store';

beforeEach(() => localStorage.clear());
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const CSV = 'name,type,men,experience\nIron Brigade,Infantry,1200,6\nBad Line,Infantry,0,5\nBuford,Cavalry,500,11\n';
const GOOD = 'name,type,men\nIron Brigade,Infantry,1200\n';

describe('store: loading an army for review', () => {
  it('the lines that can be read load; the others are kept for the review', () => {
    const s = createStore(1);
    expect(s.loadArmy(0, CSV, 'union.csv')).toEqual([
      'Line 3: men must be a whole number, 1 or more.', 'Line 4: experience must be a whole number from 1 to 10.',
    ]);
    expect(s.units.value.filter((u) => u.side === 0).map((u) => u.name)).toEqual(['Iron Brigade']);
    expect(s.review.value[0]).toEqual({
      file: 'union.csv', lineProblems: ['Line 3: men must be a whole number, 1 or more.',
        'Line 4: experience must be a whole number from 1 to 10.'], approved: false, sentBack: false, note: '',
    });
    expect(s.loadArmy(1, GOOD)).toEqual([]);
    expect(s.review.value[1].file).toBeNull();
  });

  it('a file with no readable line, or a wrong header, changes nothing', () => {
    const s = createStore(1);
    const before = s.units.value;
    expect(s.loadArmy(0, 'name,men\nA,0\n')).toEqual(['Line 2: men must be a whole number, 1 or more.']);
    expect(s.loadArmy(0, 'rank,men\nA,5\n')[0]).toMatch(/^Unknown column "rank"/);
    expect(s.units.value).toBe(before);
    expect(s.review.value[0].file).toBeNull();
  });
});

describe('store: approving and sending back', () => {
  it('approval waits on every problem; the lines left out can be let go', () => {
    const s = createStore(1);
    s.loadArmy(0, CSV, 'union.csv');
    expect(s.approve(0)).toHaveLength(2);
    expect(s.review.value[0].approved).toBe(false);
    s.dropUnreadLines(0);
    const uid = s.units.value[0].id;
    s.updateUnit(uid, { size: NaN });
    expect(s.approve(0)).toEqual(['Iron Brigade: men must be a whole number, 1 or more.']);
    s.updateUnit(uid, { size: 900 });
    expect(s.approve(0)).toEqual([]);
    expect(s.review.value[0]).toMatchObject({ approved: true, sentBack: false, lineProblems: [] });
  });

  it('any change to a side takes its approval away; the other side keeps its own', () => {
    const s = createStore(1);
    const changes: ((s: Store) => void)[] = [
      (t) => t.addUnit(0),
      (t) => t.updateUnit(t.units.value[0].id, { size: 800 }),
      (t) => t.removeUnit(t.units.value[0].id),
      (t) => t.renameSide(0, 'North'),
      (t) => t.loadArmy(0, GOOD),
    ];
    for (const change of changes) {
      s.approve(0);
      s.approve(1);
      change(s);
      expect([s.review.value[0].approved, s.review.value[1].approved]).toEqual([false, true]);
    }
    s.approve(0);
    s.setReviewNote(1, 'note');
    s.clearUnits();
    expect(s.review.value.map((r) => [r.approved, r.note])).toEqual([[false, ''], [false, '']]);
  });

  it('sending back: what to tell the player', () => {
    const s = createStore(1);
    s.loadArmy(0, CSV, 'union.csv');
    s.approve(1);
    s.setReviewNote(0, '  Battery K is over strength.  ');
    expect(s.sendBack(0)).toBe([
      'Union army (union.csv): sent back.', '', 'Problems:', '- Line 3: men must be a whole number, 1 or more.',
      '- Line 4: experience must be a whole number from 1 to 10.', '', 'Battery K is over strength.',
    ].join('\n'));
    expect(s.review.value[0]).toMatchObject({ approved: false, sentBack: true });
    expect(s.sendBack(1)).toBe('Confederate army: sent back.');
    expect(s.review.value[1]).toMatchObject({ approved: false, sentBack: true });
    expect(s.approve(1)).toEqual([]);
    expect(s.review.value[1]).toMatchObject({ approved: true, sentBack: false });
  });

  it('the reviews are kept in the setup file', () => {
    const s = createStore(1);
    s.loadArmy(0, CSV, 'union.csv');
    s.setReviewNote(0, 'fix it');
    s.approve(1);
    const t = createStore(2);
    expect(t.open(s.setupDownload().text)).toBeNull();
    expect(t.review.value).toEqual(s.review.value);

    const data = JSON.parse(s.setupDownload().text);
    expect(t.open(JSON.stringify({ ...data, review: undefined }))).toBeNull(); // older setups: not reviewed
    expect(t.review.value.map((r) => r.approved)).toEqual([false, false]);
    expect(t.open(JSON.stringify({ ...data, review: 'x' }))).toBe("The setup's review must be a list, one per side.");
    const bad = [null, { ...data.review[0], file: 1 }, { ...data.review[0], lineProblems: 'x' },
      { ...data.review[0], lineProblems: [1] }, { ...data.review[0], approved: 'yes' },
      { ...data.review[0], sentBack: 1 }, { ...data.review[0], note: null }];
    for (const r of bad) {
      expect(t.open(JSON.stringify({ ...data, review: [r, data.review[1]] }))).toBe("A side's review is not readable.");
    }
  });
});

describe('an army at a glance', () => {
  it('counts each arm, the guns, and averages the stats it can read', () => {
    const s = createStore(1);
    const union = s.units.value.filter((u) => u.side === 0);
    const g = glance([...union, { ...union[0], id: 'g', type: null, stats: 'x/y/0/0' }]);
    expect(g).toMatchObject({ regiments: union.length + 1, infantry: union.filter((u) => u.type === 'inf').length + 1 });
    expect(glance([{ ...union[0], size: NaN, stats: 'x/y' }])).toMatchObject({ men: 0, experience: null, morale: null });
    expect(glance([{ ...union[0], type: 'art', guns: NaN }]).guns).toBe(0);
  });
});

describe('the review under each army', () => {
  const review = (name: string) => within(screen.getByRole('region', { name: `Review: ${name}` }));

  it('lists the problems, linked to their rows, and lets the lines left out go', async () => {
    const s = createStore(1);
    render(<App store={s} />);
    act(() => {
      s.loadArmy(0, CSV, 'union.csv');
      s.updateUnit(s.units.value[0].id, { size: NaN });
    });
    const r = review('Union');
    expect(r.getByText('3 problems to check')).toBeTruthy();
    expect(r.getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      'union.csv: Line 3: men must be a whole number, 1 or more. (left out)',
      'union.csv: Line 4: experience must be a whole number from 1 to 10. (left out)',
      'Iron Brigade: men must be a whole number, 1 or more.',
    ]);
    const uid = s.units.value[0].id;
    expect(r.getByRole('link').getAttribute('href')).toBe(`#unit-${uid}`);
    expect(document.getElementById(`unit-${uid}`)!.classList.contains('has-problem')).toBe(true);
    expect((r.getByRole('button', { name: 'Approve' }) as HTMLButtonElement).disabled).toBe(true);
    expect(r.getByText('Not approved yet · union.csv')).toBeTruthy();
    fireEvent.click(r.getByRole('button', { name: 'Go on without the lines left out' }));
    expect(r.getByText('1 problem to check')).toBeTruthy();
    expect(r.queryByRole('button', { name: 'Go on without the lines left out' })).toBeNull();
  });

  it('an empty side, and lines left out without a file name', () => {
    const s = createStore(1);
    render(<App store={s} />);
    act(() => {
      s.loadArmy(1, 'name,men\nA,5\nB,0\n');
      s.units.value = s.units.value.filter((u) => u.side === 1);
    });
    expect(review('Union').getByText('Union has no units.')).toBeTruthy();
    expect(review('Confederate').getByText('Line 3: men must be a whole number, 1 or more. (left out)')).toBeTruthy();
  });

  it('shows the army at a glance against the other side', () => {
    const s = createStore(1);
    render(<App store={s} />);
    act(() => {
      s.units.value = [
        { id: 'a', name: 'A', side: 0, type: 'inf', subtype: 'line', size: 1000, stats: '6/4/0/0', guns: null },
        { id: 'b', name: 'B', side: 0, type: 'art', subtype: 'battery', size: 72, stats: '5/5/0/0', guns: 8 },
        { id: 'c', name: 'C', side: 1, type: 'cav', subtype: 'light', size: 500, stats: '5/5/0/0', guns: null },
      ];
    });
    const terms = review('Union').getAllByRole('definition').map((d) => d.textContent);
    expect(terms).toEqual(['2', '1,072', '1 infantry · 0 cavalry · 1 battery (8 guns)',
      'experience 5.5 · morale 4.5', 'Confederate: 500 men, experience 5.0 · morale 5.0']);
    expect(review('Confederate').getAllByRole('definition')[2].textContent).toBe('0 infantry · 1 cavalry · 0 batteries (0 guns)');
    act(() => {
      s.units.value = [{ ...s.units.value[0], stats: 'x/y/0/0' }];
    });
    expect(review('Union').getAllByRole('definition')[3].textContent).toBe('no stats');
  });

  it('approves an army', () => {
    const s = createStore(1);
    render(<App store={s} />);
    const r = review('Union');
    fireEvent.click(r.getByRole('button', { name: 'Approve' }));
    expect(r.getByText('✓ Approved')).toBeTruthy();
    expect(s.review.value[0].approved).toBe(true);
  });

  it('sends an army back: the note is copied when the browser allows it, and shown either way', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText } });
    const s = createStore(1);
    render(<App store={s} />);
    const r = review('Confederate');
    fireEvent.input(r.getByLabelText('Note to the Confederate player'), { target: { value: 'Too few guns.' } });
    expect(s.review.value[1].note).toBe('Too few guns.');
    fireEvent.click(r.getByRole('button', { name: 'Send back' }));
    const text = 'Confederate army: sent back.\n\nToo few guns.';
    expect(writeText).toHaveBeenCalledWith(text);
    await waitFor(() => expect(r.getByText('Copied: send it to the player.')).toBeTruthy());
    expect((r.getByLabelText('What to send the Confederate player') as HTMLTextAreaElement).value).toBe(text);
    expect(r.getByText('Sent back')).toBeTruthy();

    writeText.mockRejectedValue(new Error('denied'));
    fireEvent.click(r.getByRole('button', { name: 'Send back' }));
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(2));
    expect(r.getByText('Copy this and send it to the player.')).toBeTruthy();
  });

  it('without a clipboard, the note is shown to copy', () => {
    vi.stubGlobal('navigator', { ...navigator, clipboard: undefined });
    render(<App store={createStore(1)} />);
    fireEvent.click(review('Union').getByRole('button', { name: 'Send back' }));
    expect(review('Union').getByText('Copy this and send it to the player.')).toBeTruthy();
  });
});
