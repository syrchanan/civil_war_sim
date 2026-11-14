/**
 * Army files: one side's units as CSV, so players can keep their army in a spreadsheet and load it instead of
 * typing it in each time. Words rather than codes (Infantry, rifled musket, yes / no); blank cells take the usual
 * values; columns may come in any order. Problems are reported by line, and nothing is loaded while there are any.
 */

import defaults from '../engine/defaults.json';
import { DEFAULT_SUBTYPE, STANDARD_BATTERY, type UnitDraft, type UnitType } from './store';

export const COLUMNS = ['name', 'type', 'subtype', 'men', 'experience', 'morale', 'weapon', 'melee_only', 'guns'];

const TYPES: Record<string, UnitType | null> = { infantry: 'inf', cavalry: 'cav', artillery: 'art', generic: null };
const TYPE_WORDS: Record<string, string> = { inf: 'Infantry', cav: 'Cavalry', art: 'Artillery' };
const SUBTYPES: Record<string, string[]> = defaults.unit_subtypes;
const weapons = (type: UnitType | null): Record<string, number> =>
  (type === 'art' ? defaults.names.artillery_weapons : defaults.names.weapons);

/** CSV rows with the line each starts on: quoted cells may hold commas, quotes ("") and line breaks. */
function readRows(text: string): { line: number; cells: string[] }[] {
  const rows: { line: number; cells: string[] }[] = [];
  let cells: string[] = [];
  let cell = '';
  let quoted = false;
  let line = 1;
  let start = 1;
  const endRow = () => {
    cells.push(cell);
    if (cells.length > 1 || cells[0] !== '') rows.push({ line: start, cells }); // blank lines skipped
    cells = [];
    cell = '';
  };
  const body = text.replace(/^﻿/, ''); // Excel writes a byte-order mark
  for (let i = 0; i < body.length; i++) {
    const ch = body[i];
    if (quoted) {
      if (ch === '"' && body[i + 1] === '"') {
        cell += '"';
        i += 1;
      } else if (ch === '"') {
        quoted = false;
      } else {
        if (ch === '\n') line += 1;
        cell += ch;
      }
    } else if (ch === '"') {
      quoted = true;
    } else if (ch === ',') {
      cells.push(cell);
      cell = '';
    } else if (ch === '\n') {
      endRow();
      line += 1;
      start = line;
    } else if (ch !== '\r') {
      cell += ch;
    }
  }
  endRow();
  return rows;
}

export const parseCsv = (text: string): string[][] => readRows(text).map((r) => r.cells);

const quote = (cell: string): string => (/[",\r\n]/.test(cell) ? `"${cell.replace(/"/g, '""')}"` : cell);

/** One side's units as CSV (CRLF line ends, as spreadsheets expect). */
export function armyToCsv(units: UnitDraft[]): string {
  const rows = units.map((u) => {
    const [xp, morale, weapon, meleeOnly] = u.stats.split('/');
    const weaponName = Object.entries(weapons(u.type)).find(([, code]) => String(code) === weapon)![0];
    return [u.name, u.type === null ? 'Generic' : TYPE_WORDS[u.type], u.subtype ?? '', String(u.size), xp, morale,
      weaponName, meleeOnly === '1' ? 'yes' : 'no', u.guns === null ? '' : String(u.guns)];
  });
  return [COLUMNS, ...rows].map((r) => r.map(quote).join(',')).join('\r\n') + '\r\n';
}

const whole = (text: string, min: number, max = Infinity): number | null => {
  const n = Number(text);
  return text !== '' && Number.isInteger(n) && n >= min && n <= max ? n : null;
};

/** One row as a unit, or what is wrong with it. */
function readUnit(get: (column: string) => string, side: 0 | 1): Omit<UnitDraft, 'id'> | string {
  const name = get('name');
  if (name === '') return 'every unit needs a name.';
  const typeWord = get('type');
  const type = typeWord === '' ? null : TYPES[typeWord.toLowerCase()];
  if (type === undefined) return `unknown type "${typeWord}" (Infantry, Cavalry, Artillery or Generic).`;
  let subtype: string | null = null;
  if (type !== null) {
    subtype = get('subtype').toLowerCase() || DEFAULT_SUBTYPE[type];
    if (!SUBTYPES[type].includes(subtype)) {
      return `unknown subtype "${get('subtype')}" for ${TYPE_WORDS[type]} (${SUBTYPES[type].join(', ')}).`;
    }
  }
  const size = whole(get('men'), 1);
  if (size === null) return 'men must be a whole number, 1 or more.';
  const xp = get('experience') === '' ? 5 : whole(get('experience'), 1, 10);
  if (xp === null) return 'experience must be a whole number from 1 to 10.';
  const morale = get('morale') === '' ? 5 : whole(get('morale'), 1, 10);
  if (morale === null) return 'morale must be a whole number from 1 to 10.';
  const table = weapons(type);
  const weaponText = get('weapon').toLowerCase();
  const byName = Object.entries(table).find(([w]) => w === weaponText);
  const byCode = Object.values(table).find((code) => String(code) === weaponText);
  const weapon = weaponText === '' ? 0 : byName?.[1] ?? byCode;
  if (weapon === undefined) return `unknown weapon "${get('weapon')}" (${Object.keys(table).join(', ')}).`;
  const melee = { '': 0, no: 0, yes: 1 }[get('melee_only').toLowerCase()];
  if (melee === undefined) return 'melee_only must be yes or no.';
  let guns: number | null = null;
  if (get('guns') !== '') {
    if (type !== 'art') return 'only artillery has guns.';
    guns = whole(get('guns'), 0);
    if (guns === null) return 'guns must be a whole number, 0 or more.';
  } else if (type === 'art') {
    guns = STANDARD_BATTERY.guns;
  }
  return { name, side, type, subtype, size, stats: `${xp}/${morale}/${weapon}/${melee}`, guns };
}

/** Read one side's units from an army file; `problems` names each line that couldn't be read. */
export function armyFromCsv(text: string, side: 0 | 1): { units: Omit<UnitDraft, 'id'>[]; problems: string[] } {
  const rows = readRows(text);
  if (rows.length === 0) return { units: [], problems: ['The file is empty.'] };
  const header = rows[0].cells.map((c) => c.trim().toLowerCase().replace(/ /g, '_'));
  const unknown = header.find((c) => !COLUMNS.includes(c));
  if (unknown !== undefined) {
    return { units: [], problems: [`Unknown column "${unknown}". Columns: ${COLUMNS.join(', ')}.`] };
  }
  if (!header.includes('name') || !header.includes('men')) {
    return { units: [], problems: ['The file needs a "name" and a "men" column.'] };
  }
  const units: Omit<UnitDraft, 'id'>[] = [];
  const problems: string[] = [];
  for (const { line, cells } of rows.slice(1)) {
    const get = (column: string) => (cells[header.indexOf(column)] ?? '').trim();
    const unit = readUnit(get, side);
    if (typeof unit === 'string') problems.push(`Line ${line}: ${unit}`);
    else units.push(unit);
  }
  return { units, problems };
}
