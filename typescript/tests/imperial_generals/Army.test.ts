import { Army } from '../../src/imperial_generals/units/Army';
import { Regiment } from '../../src/imperial_generals/units/Regiment';
import * as fs from 'fs';
import * as path from 'path';

describe('Army Golden Path', () => {
  const goldenPath = path.resolve(__dirname, '../../../test_cases/army_examples.json');
  const cases = JSON.parse(fs.readFileSync(goldenPath, 'utf8'));

  cases.forEach((testCase: any) => {
    it(testCase.description, () => {
      const army = new Army(testCase.inputs.faction);
      if (testCase.actions) {
        testCase.actions.forEach((action: any) => {
          if (action.method === 'add_regiment') {
            // args: [name, {size, stats, law}]
            const [regName, regProps] = action.args;
            const regiment = new Regiment(regProps.size, regProps.stats, regProps.law);
            army.addRegiment(regName, regiment);
          } else {
            throw new Error('Unknown method for Army test: ' + action.method);
          }
        });
      }
      if (testCase.expected) {
        expect(army.faction).toBe(testCase.expected.faction);
        for (const [regName, regProps] of Object.entries(testCase.expected.forces)) {
          expect(army.forces).toHaveProperty(regName);
          const reg = army.forces[regName];
          expect(reg.size).toBe(regProps.size);
          expect(Array.from(reg.stats)).toEqual(regProps.stats);
          expect(reg.law).toBe(regProps.law);
        }
      }
      if (testCase.expectedForcesCount !== undefined) {
        expect(Object.keys(army.forces).length).toBe(testCase.expectedForcesCount);
      }
    });
  });
});
