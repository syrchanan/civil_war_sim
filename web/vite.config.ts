import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['src/**/*.test.ts'],
    coverage: {
      provider: 'v8',
      include: ['src/**/*.ts'],
      exclude: ['src/**/*.test.ts'],
      // as in the Python suite: every line and branch is tested; genuinely unreachable code is marked
      // /* v8 ignore next */ with a reason
      thresholds: { statements: 100, branches: 100, functions: 100, lines: 100 },
    },
  },
});
