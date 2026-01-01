import { getClosestMoraleStat } from '../../src/imperial_generals/utils/closestMoraleStat';
import * as fs from 'fs';
import * as path from 'path';

describe('getClosestMoraleStat Golden Path', () => {
  const goldenPath = path.resolve(__dirname, '../../../test_cases/closest_morale_stat.json');
  const cases = JSON.parse(fs.readFileSync(goldenPath, 'utf8'));

  cases.forEach((testCase: any) => {
    it(testCase.description, () => {
      expect(getClosestMoraleStat(testCase.inputs)).toBe(testCase.expected);
    });
  });
});
