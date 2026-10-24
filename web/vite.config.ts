import { defineConfig } from 'vitest/config';

export default defineConfig({
  // relative asset paths: the site works under any path, e.g. GitHub Pages' /civil_war_sim/
  base: './',
  test: {
    include: ['src/**/*.test.{ts,tsx}'],
    // UI tests fight whole battles in jsdom; under coverage, in parallel, on CI they need more than the default 5 s
    testTimeout: 20_000,
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
