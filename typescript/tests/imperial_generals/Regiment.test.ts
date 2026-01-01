import { Regiment } from '../../src/imperial_generals/units'
import * as fs from 'fs'
import * as path from 'path'

describe('Regiment golden tests', () => {
  const goldenPath = path.resolve(__dirname, '../../../test_cases/regiment_examples.json')
  const goldenCases = JSON.parse(fs.readFileSync(goldenPath, 'utf8'))

  for (const testCase of goldenCases) {
    const { description, inputs, expected, shouldError } = testCase
    it(description, () => {
      if (shouldError) {
        expect(() => new Regiment(inputs.size, inputs.stats, inputs.law)).toThrow()
      } else {
        const reg = new Regiment(inputs.size, inputs.stats, inputs.law)
        expect(reg.size).toBe(expected.size)
        expect(Array.from(reg.stats)).toEqual(expected.stats)
        expect(reg.law).toBe(expected.law)
      }
    })
  }
})
