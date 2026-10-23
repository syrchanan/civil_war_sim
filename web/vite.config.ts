import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['src/**/*.test.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      // main.tsx only mounts the app in the page
      exclude: ['src/**/*.test.{ts,tsx}', 'src/ui/main.tsx'],
      // as in the Python suite: every line and branch is tested; genuinely unreachable code is marked
      // /* v8 ignore next */ with a reason
      thresholds: { statements: 100, branches: 100, functions: 100, lines: 100 },
    },
  },
});
