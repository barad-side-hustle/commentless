import { defineConfig } from 'tsdown';

export default defineConfig({
  entry: ['src/index.ts', 'src/bin.ts', 'src/worker.ts'],
  format: ['esm'],
  platform: 'node',
  target: 'node20',
  dts: { entry: 'src/index.ts' },
  outExtensions: () => ({ js: '.js', dts: '.d.ts' }),
  clean: true,
  treeshake: true,
  external: ['typescript', 'tinyglobby', 'ignore', 'picocolors'],
});
