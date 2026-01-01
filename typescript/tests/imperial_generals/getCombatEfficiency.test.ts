import { getCombatEfficiency } from '../../src/imperial_generals/utils/combatEfficiency';
import * as fs from 'fs';
import * as path from 'path';

describe('getCombatEfficiency Golden Path', () => {
  const goldenPath = path.resolve(__dirname, '../../../test_cases/combat_efficiency.json');
  const cases = JSON.parse(fs.readFileSync(goldenPath, 'utf8'));

  cases.forEach((testCase: any) => {
    it(testCase.description, () => {
      const { stat_xp, stat_morale, stat_weapon, stat_melee } = testCase.inputs || {};
      const v = getCombatEfficiency(stat_xp, stat_morale, stat_weapon, stat_melee);
      if (testCase.hasOwnProperty('expected')) {
        // Floating point, 4 decimals
        expect(+v.toFixed(4)).toBe(+testCase.expected.toFixed(4));
      } else if (testCase.hasOwnProperty('expectedRange')) {
        expect(v).toBeGreaterThanOrEqual(testCase.expectedRange[0]);
        expect(v).toBeLessThanOrEqual(testCase.expectedRange[1]);
      }
    });
  });
});
