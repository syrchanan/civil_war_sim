import { describe, expect, it } from 'vitest';

import { armyFromCsv, armyToCsv, parseCsv } from './armyCsv';
import { EXAMPLE_ARMIES } from './store';

const HEADER = 'name,type,subtype,men,experience,morale,weapon,melee_only,guns';

describe('CSV text', () => {
  it('reads quoted cells (commas, quotes, line breaks), CRLF, a BOM and a missing last newline', () => {
    expect(parseCsv('﻿a,"b, c","say ""hi"""\r\n"two\nlines",,x')).toEqual([['a', 'b, c', 'say "hi"'], ['two\nlines', '', 'x']]);
    expect(parseCsv('a,b\n\n')).toEqual([['a', 'b']]);                 // blank lines skipped
  });
});

describe('army files (CSV, one side)', () => {
  const union = EXAMPLE_ARMIES.units.filter((u) => u.side === 0);

  it('written with words a player can edit in a spreadsheet', () => {
    expect(armyToCsv(union).split('\r\n')).toEqual([
      HEADER,
      '1st Minnesota,Infantry,line,900,6,6,rifled musket,no,',
      '15th Massachusetts,Infantry,line,700,5,5,rifled musket,no,',
      'Battery B,Artillery,battery,72,5,5,smoothbore guns,no,8',
      '',
    ]);
    expect(armyToCsv([{ ...union[0], name: 'Smith, "Old" Guard', type: null, subtype: null, stats: '3/4/-2/1' }]))
      .toContain('"Smith, ""Old"" Guard",Generic,,900,3,4,unarmed / pikes,yes,');
  });

  it('read back exactly', () => {
    const { units, problems } = armyFromCsv(armyToCsv(union), 0);
    expect(problems).toEqual([]);
    expect(units).toEqual(union.map(({ id: _id, ...u }) => u));
  });

  it('blank cells take the usual values; words in any case; weapons by name or code', () => {
    const text = [
      HEADER,
      'Pickets,,,120,,,,,',
      'Riders,CAVALRY,,300,4,5,Smoothbore Musket,Yes,',
      'Guns,artillery,horse battery,54,6,6,1,,6',
      'Big guns,Artillery,,72,,,,,',
      'Nobody,Infantry,,,,,,,',
    ].join('\n');
    const { units, problems } = armyFromCsv(text, 1);
    expect(problems).toEqual(['Line 6: men must be a whole number, 1 or more.']);
    expect(units).toEqual([
      { name: 'Pickets', side: 1, type: null, subtype: null, size: 120, stats: '5/5/0/0', guns: null },
      { name: 'Riders', side: 1, type: 'cav', subtype: 'light', size: 300, stats: '4/5/0/1', guns: null },
      { name: 'Guns', side: 1, type: 'art', subtype: 'horse battery', size: 54, stats: '6/6/1/0', guns: 6 },
      { name: 'Big guns', side: 1, type: 'art', subtype: 'battery', size: 72, stats: '5/5/0/0', guns: 8 },
    ]);
  });

  it('columns can come in any order; unknown columns are a problem', () => {
    expect(armyFromCsv('men,name\n500,Alpha', 0).units).toEqual([
      { name: 'Alpha', side: 0, type: null, subtype: null, size: 500, stats: '5/5/0/0', guns: null },
    ]);
    expect(armyFromCsv('name,men,colour\nA,5,red', 0).problems).toEqual(
      ['Unknown column "colour". Columns: name, type, subtype, men, experience, morale, weapon, melee_only, guns.']);
    expect(armyFromCsv('type\nInfantry', 0).problems).toEqual(['The file needs a "name" and a "men" column.']);
    expect(armyFromCsv('', 0).problems).toEqual(['The file is empty.']);
  });

  it('each problem names its line', () => {
    const text = [
      HEADER,
      ',Infantry,line,100,5,5,,,',
      'A,Infantery,,100,5,5,,,',
      'B,Infantry,heavy,100,5,5,,,',
      'C,Infantry,,100,11,5,,,',
      'D,Infantry,,100,5,0,,,',
      'E,Infantry,,100,5,5,laser,,',
      'F,Infantry,,100,5,5,,maybe,',
      'G,Artillery,,72,5,5,,,-1',
      'H,Infantry,,100,5,5,,,4',
    ].join('\n');
    expect(armyFromCsv(text, 0).problems).toEqual([
      'Line 2: every unit needs a name.',
      'Line 3: unknown type "Infantery" (Infantry, Cavalry, Artillery or Generic).',
      'Line 4: unknown subtype "heavy" for Infantry (irregulars, light, line, marine, pikes).',
      'Line 5: experience must be a whole number from 1 to 10.',
      'Line 6: morale must be a whole number from 1 to 10.',
      'Line 7: unknown weapon "laser" (unarmed / pikes, matchlock, smoothbore musket, rifled musket, needle rifle).',
      'Line 8: melee_only must be yes or no.',
      'Line 9: guns must be a whole number, 0 or more.',
      'Line 10: only artillery has guns.',
    ]);
  });
});
