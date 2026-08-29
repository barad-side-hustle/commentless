import { existsSync } from 'node:fs';
import { availableParallelism } from 'node:os';
import { Worker } from 'node:worker_threads';
import type { FileResult, KeepRule, RunMode, RunResult, RunSummary } from '../types.js';
import { CleanFileCache, signatureOf } from './cache.js';
import { discoverFiles, type DiscoveryMode } from './files.js';
import { serializeKeepRules } from './keep.js';
import { processFile } from './process.js';

const WORKER_THRESHOLD = 200;
const BATCH_SIZE = 24;

export interface RunOptions {
  cwd?: string;
  paths?: readonly string[];
  mode: RunMode;
  discovery?: DiscoveryMode;
  base?: string | undefined;
  extensions: readonly string[];
  ignore?: readonly string[];
  ignoreFile?: string | false;
  gitignore?: boolean;
  keep: readonly KeepRule[];
  collapseBlankLines?: boolean;
  maxAllowed?: number;
  concurrency?: number;
  cache?: boolean;
  files?: readonly string[];
  workerThreshold?: number;
  workerEntry?: URL;
}

export function defaultConcurrency(): number {
  return Math.max(1, availableParallelism() - 1);
}

function workerEntry(): URL | null {
  for (const candidate of ['./worker.js', '../worker.js']) {
    const url = new URL(candidate, import.meta.url);
    if (existsSync(url)) return url;
  }
  return null;
}

async function runInWorkers(
  files: readonly string[],
  entry: URL,
  workerCount: number,
  init: { keep: ReturnType<typeof serializeKeepRules>; collapseBlankLines: boolean; write: boolean }
): Promise<FileResult[]> {
  const results: FileResult[] = [];
  let cursor = 0;

  const spawn = (): Promise<void> =>
    new Promise((resolve, reject) => {
      const worker = new Worker(entry, { workerData: init });
      const next = () => {
        if (cursor >= files.length) {
          worker.postMessage(null);
          void worker.terminate().then(() => resolve());
          return;
        }
        const batch = files.slice(cursor, cursor + BATCH_SIZE);
        cursor += batch.length;
        worker.postMessage(batch);
      };
      worker.on('message', (batchResults: FileResult[]) => {
        results.push(...batchResults);
        next();
      });
      worker.on('error', reject);
      next();
    });

  await Promise.all(Array.from({ length: workerCount }, spawn));
  return results;
}

export async function run(options: RunOptions): Promise<RunResult> {
  const startedAt = performance.now();
  const cwd = options.cwd ?? process.cwd();
  const write = options.mode === 'write';
  const collapseBlankLines = options.collapseBlankLines ?? false;
  const maxAllowed = options.maxAllowed ?? 0;

  const files =
    options.files ??
    (await discoverFiles({
      cwd,
      paths: options.paths ?? ['.'],
      extensions: options.extensions,
      ignore: options.ignore ?? [],
      ignoreFile: options.ignoreFile ?? '.commentlessignore',
      gitignore: options.gitignore ?? true,
      mode: options.discovery ?? 'all',
      base: options.base,
    }));

  const signature = signatureOf({
    keep: serializeKeepRules(options.keep),
    collapseBlankLines,
    extensions: [...options.extensions].sort(),
  });
  const cache =
    options.cache === false ? CleanFileCache.disabled() : CleanFileCache.load(cwd, signature);

  const pending: string[] = [];
  let cached = 0;
  for (const file of files) {
    if (cache.isClean(file)) {
      cached += 1;
      continue;
    }
    pending.push(file);
  }

  const entry = options.workerEntry ?? workerEntry();
  const workerCount = Math.min(
    options.concurrency ?? defaultConcurrency(),
    Math.ceil(pending.length / BATCH_SIZE)
  );

  const threshold = options.workerThreshold ?? WORKER_THRESHOLD;
  const results =
    entry && workerCount > 1 && pending.length >= threshold
      ? await runInWorkers(pending, entry, workerCount, {
          keep: serializeKeepRules(options.keep),
          collapseBlankLines,
          write,
        })
      : pending.map(file => processFile(file, { keep: options.keep, collapseBlankLines, write }));

  results.sort((a, b) => (a.file < b.file ? -1 : a.file > b.file ? 1 : 0));

  const offenders: FileResult[] = [];
  let commentsRemoved = 0;
  let commentsKept = 0;
  let errors = 0;

  for (const result of results) {
    commentsKept += result.keptCount;
    if (result.error) {
      errors += 1;
      offenders.push(result);
      cache.mark(result.file, false);
      continue;
    }
    if (result.changed) {
      commentsRemoved += result.removable.length;
      offenders.push(result);
      cache.mark(result.file, write);
      continue;
    }
    cache.mark(result.file, true);
  }

  cache.save();

  const summary: RunSummary = {
    mode: options.mode,
    discovered: files.length,
    parsed: pending.length,
    cached,
    filesWithComments: offenders.filter(result => result.changed).length,
    commentsRemoved,
    commentsKept,
    errors,
    durationMs: Math.round(performance.now() - startedAt),
  };

  const failed = errors > 0 || (options.mode === 'check' && commentsRemoved > maxAllowed);

  return { summary, files: offenders, exitCode: failed ? 1 : 0 };
}
