#!/usr/bin/env node
import { performance } from 'node:perf_hooks';
import { rmSync } from 'node:fs';
import path from 'node:path';
import { cacheDirectory } from '../dist/index.js';
import { defaultConcurrency, discoverFiles, resolveKeepRules, run } from '../dist/index.js';

const target = path.resolve(process.argv[2] ?? '.');
const keep = resolveKeepRules({});
const extensions = ['ts', 'tsx', 'mts', 'cts', 'js', 'jsx', 'mjs', 'cjs'];

const base = {
  cwd: target,
  mode: 'dry-run',
  extensions,
  keep,
  workerEntry: new URL('../dist/worker.js', import.meta.url),
};

async function time(label, options) {
  const startedAt = performance.now();
  const result = await run({ ...base, ...options });
  const elapsed = Math.round(performance.now() - startedAt);
  console.log(
    `${label.padEnd(28)} ${String(elapsed).padStart(6)}ms   ` +
      `${result.summary.parsed} parsed, ${result.summary.cached} cached, ` +
      `${result.summary.commentsRemoved} removable`
  );
  return elapsed;
}

function dropCache() {
  try {
    rmSync(cacheDirectory(target), { recursive: true, force: true });
  } catch {
    void 0;
  }
}

const files = await discoverFiles({
  cwd: target,
  paths: ['.'],
  extensions,
  ignore: [],
  ignoreFile: '.commentlessignore',
  gitignore: true,
  mode: 'all',
});

console.log(`commentless bench — ${files.length} files under ${target}`);
console.log(`cpus available for workers: ${defaultConcurrency()}\n`);

dropCache();
await time('single thread, no cache', { cache: false, concurrency: 1, workerThreshold: 1e9 });

dropCache();
await time(`${defaultConcurrency()} workers, no cache`, { cache: false, workerThreshold: 1 });

dropCache();
await time('cold cache', { cache: true, workerThreshold: 1 });
await time('warm cache', { cache: true, workerThreshold: 1 });
dropCache();
