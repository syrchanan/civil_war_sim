import { Simulation } from '../../src/imperial_generals/battles/Simulation';
import { Regiment } from '../../src/imperial_generals/units/Regiment';
import * as fs from 'fs';
import * as path from 'path';

describe('Simulation Golden Path', () => {
  const goldenPath = path.resolve(__dirname, '../../../test_cases/battle_simulation_basic.json');
  // eslint-disable-next-line
  const cases = JSON.parse(fs.readFileSync(goldenPath, 'utf8'));

  cases.forEach((testCase: any) => {
    const { description, inputs, expectedOutputFields, outputShouldIncludeAtLeastRows, atLeastOneZeroIn } = testCase;
    it(description, () => {
      const reg1 = new Regiment(inputs.units[0].size, inputs.units[0].stats, inputs.units[0].law);
      const reg2 = new Regiment(inputs.units[1].size, inputs.units[1].stats, inputs.units[1].law);
      const sim = new Simulation([reg1, reg2]);
      sim.run_simulation(inputs.time);
      const output = sim.sim_output;
      // Check for expected fields (as keys of the first output row)
      if (expectedOutputFields) {
        expectedOutputFields.forEach((field: string) => {
          expect(field in output[0]).toBe(true);
        });
      }
      // Check minimum number of rows in output
      if (outputShouldIncludeAtLeastRows) {
        expect(output.length).toBeGreaterThanOrEqual(outputShouldIncludeAtLeastRows);
      }
      // Check zero in key columns of last row
      if (atLeastOneZeroIn) {
        const lastRow = output[output.length - 1];
        const anyZero = atLeastOneZeroIn.some((key: string) => lastRow[key] === 0);
        expect(anyZero).toBe(true);
      }
    });
  });
});
