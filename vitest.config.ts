import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['tests/**/*.test.ts'],
    environment: 'node',
    coverage: {
      provider: 'v8',
      include: ['src/**/*.ts'],
      exclude: ['src/worker.ts', 'src/bin.ts', 'src/types.ts'],
      thresholds: { lines: 95, functions: 95, branches: 85, statements: 95 },
    },
  },
});
