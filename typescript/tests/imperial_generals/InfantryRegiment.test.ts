import { InfantryRegiment } from '../../src/imperial_generals/units/InfantryRegiment';
import * as fs from 'fs';
import * as path from 'path';

describe('InfantryRegiment Golden Path', () => {
  const goldenPath = path.resolve(__dirname, '../../../test_cases/infantry_regiment_examples.json');
  // eslint-disable-next-line
  const cases = JSON.parse(fs.readFileSync(goldenPath, 'utf8'));

  cases.forEach((testCase: any) => {
    const { description, inputs, expected, actions } = testCase;
    it(description, () => {
      const reg = new InfantryRegiment(inputs.size, inputs.stats, inputs.law);
      if (actions) {
        actions.forEach((action: any) => {
          // Convert pythonic method names to camelCase
          let method = action.method.replace(/_(\w)/g, (_, c) => c.toUpperCase());
          if (typeof (reg as any)[method] !== 'function') throw new Error(`No such method: ${method}`);
          (reg as any)[method](action.args);
        });
      }
      if (expected) {
        Object.entries(expected).forEach(([k, v]) => {
          if (k === 'stats') {
            expect(Array.from(reg.stats)).toEqual(v);
          } else if (k === 'raw_morale') {
            expect(reg.rawMorale).toBe(v);
          } else if (k === 'unit_type') {
            expect(reg.unitType).toBe(v);
          } else {
            expect((reg as any)[k]).toEqual(v);
          }
        });
      }
    });
  });
});
