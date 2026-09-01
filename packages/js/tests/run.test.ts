import { chmodSync, existsSync, readFileSync } from 'node:fs';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { resolveKeepRules } from '../src/core/keep.js';
import { run, type RunOptions } from '../src/core/run.js';
import { sandbox, type Sandbox } from './helpers.js';

const KEEP = resolveKeepRules({});

function options(box: Sandbox, overrides: Partial<RunOptions> = {}): RunOptions {
  return {
    cwd: box.dir,
    mode: 'check',
    extensions: ['ts', 'tsx'],
    keep: KEEP,
    cache: false,
    ...overrides,
  };
}

describe('run', () => {
  let box: Sandbox;

  beforeEach(() => {
    box = sandbox();
  });

  afterEach(() => box.cleanup());

  it('passes on a clean tree', async () => {
    box.write('a.ts', 'export const a = 1;\n');
    const result = await run(options(box));
    expect(result.exitCode).toBe(0);
    expect(result.summary.commentsRemoved).toBe(0);
    expect(result.files).toEqual([]);
  });

  it('fails --check when a comment is present and writes nothing', async () => {
    const file = box.write('a.ts', '// note\nexport const a = 1;\n');
    const result = await run(options(box));
    expect(result.exitCode).toBe(1);
    expect(result.summary.commentsRemoved).toBe(1);
    expect(result.summary.filesWithComments).toBe(1);
    expect(readFileSync(file, 'utf8')).toBe('// note\nexport const a = 1;\n');
  });

  it('rewrites files in write mode', async () => {
    const file = box.write('a.ts', '// note\nexport const a = 1;\n');
    const result = await run(options(box, { mode: 'write' }));
    expect(result.exitCode).toBe(0);
    expect(readFileSync(file, 'utf8')).toBe('export const a = 1;\n');
  });

  it('reports without writing in dry-run mode', async () => {
    const file = box.write('a.ts', '// note\nexport const a = 1;\n');
    const result = await run(options(box, { mode: 'dry-run' }));
    expect(result.exitCode).toBe(0);
    expect(result.summary.commentsRemoved).toBe(1);
    expect(readFileSync(file, 'utf8')).toBe('// note\nexport const a = 1;\n');
  });

  it('counts kept comments separately', async () => {
    box.write('a.ts', '// eslint-disable-next-line no-console\nconsole.log(1);\n');
    const result = await run(options(box));
    expect(result.exitCode).toBe(0);
    expect(result.summary.commentsKept).toBe(1);
    expect(result.summary.commentsRemoved).toBe(0);
  });

  it('tolerates a baseline via maxAllowed', async () => {
    box.write('a.ts', '// one\n// two\nexport const a = 1;\n');
    expect((await run(options(box, { maxAllowed: 2 }))).exitCode).toBe(0);
    expect((await run(options(box, { maxAllowed: 1 }))).exitCode).toBe(1);
  });

  it('collapses blank lines only when asked', async () => {
    const source = 'export const a = 1;\n\n\n\n// note\nexport const b = 2;\n';
    const file = box.write('a.ts', source);
    await run(options(box, { mode: 'write' }));
    expect(readFileSync(file, 'utf8')).toBe('export const a = 1;\n\n\n\nexport const b = 2;\n');

    box.write('a.ts', source);
    await run(options(box, { mode: 'write', collapseBlankLines: true }));
    expect(readFileSync(file, 'utf8')).toBe('export const a = 1;\n\nexport const b = 2;\n');
  });

  it('is idempotent across runs', async () => {
    const file = box.write('a.ts', '// one\nexport const a = 1; // two\n');
    await run(options(box, { mode: 'write' }));
    const first = readFileSync(file, 'utf8');
    const second = await run(options(box, { mode: 'write' }));
    expect(readFileSync(file, 'utf8')).toBe(first);
    expect(second.summary.commentsRemoved).toBe(0);
  });

  it('records a per-file error without aborting the run', async () => {
    box.write('a.ts', '// note\nexport const a = 1;\n');
    const result = await run(options(box, { files: [`${box.dir}/missing.ts`, `${box.dir}/a.ts`] }));
    expect(result.summary.errors).toBe(1);
    expect(result.exitCode).toBe(1);
    expect(result.files.some(entry => entry.file.endsWith('a.ts'))).toBe(true);
  });

  it('skips files listed in the ignore file', async () => {
    box.write('.commentlessignore', 'vendor\n');
    box.write('vendor/a.ts', '// note\nexport const a = 1;\n');
    box.write('src/b.ts', 'export const b = 1;\n');
    const result = await run(options(box));
    expect(result.exitCode).toBe(0);
    expect(result.summary.discovered).toBe(1);
  });

  it('produces identical results with the worker pool disabled or enabled', async () => {
    for (let index = 0; index < 6; index += 1) {
      box.write(`file-${index}.ts`, `// note ${index}\nexport const a${index} = ${index};\n`);
    }
    const single = await run(options(box, { concurrency: 1 }));
    const parallel = await run(options(box, { concurrency: 4 }));
    expect(parallel.summary.commentsRemoved).toBe(single.summary.commentsRemoved);
    expect(parallel.files.map(entry => entry.file)).toEqual(single.files.map(entry => entry.file));
  });
});

describe('the clean-file cache', () => {
  let box: Sandbox;

  beforeEach(() => {
    box = sandbox();
  });

  afterEach(() => box.cleanup());

  it('skips unchanged clean files on the second run', async () => {
    box.write('a.ts', 'export const a = 1;\n');
    const first = await run(options(box, { cache: true }));
    expect(first.summary.parsed).toBe(1);
    expect(first.summary.cached).toBe(0);

    const second = await run(options(box, { cache: true }));
    expect(second.summary.parsed).toBe(0);
    expect(second.summary.cached).toBe(1);
    expect(second.exitCode).toBe(0);
  });

  it('re-checks a file after it changes', async () => {
    box.write('a.ts', 'export const a = 1;\n');
    await run(options(box, { cache: true }));
    await new Promise(resolve => setTimeout(resolve, 12));
    box.write('a.ts', '// added later\nexport const a = 1;\n');

    const result = await run(options(box, { cache: true }));
    expect(result.summary.parsed).toBe(1);
    expect(result.exitCode).toBe(1);
  });

  it('invalidates when the keep rules change', async () => {
    box.write('a.ts', 'export const a = 1;\n');
    await run(options(box, { cache: true }));
    const result = await run(
      options(box, { cache: true, keep: resolveKeepRules({ userPatterns: ['x'] }) })
    );
    expect(result.summary.cached).toBe(0);
  });
});

describe('the worker pool', () => {
  let box: Sandbox;

  beforeEach(() => {
    box = sandbox();
  });

  afterEach(() => box.cleanup());

  const entry = new URL('../dist/worker.js', import.meta.url);
  const built = existsSync(entry);

  it.runIf(built)('produces the same results as the single-threaded path', async () => {
    for (let index = 0; index < 40; index += 1) {
      box.write(
        `file-${index}.ts`,
        `// note ${index}\n// eslint-disable-next-line no-console\nexport const a${index} = ${index};\n`
      );
    }

    const inline = await run(options(box, { concurrency: 1, workerThreshold: 10_000 }));
    const pooled = await run(
      options(box, { concurrency: 4, workerThreshold: 1, workerEntry: entry })
    );

    expect(pooled.summary.commentsRemoved).toBe(40);
    expect(pooled.summary.commentsKept).toBe(40);
    expect(pooled.summary.commentsRemoved).toBe(inline.summary.commentsRemoved);
    expect(pooled.files.map(entry => entry.file)).toEqual(inline.files.map(entry => entry.file));
  });

  it.runIf(built)('writes through workers', async () => {
    const files = Array.from({ length: 12 }, (_, index) =>
      box.write(`file-${index}.ts`, `// note\nexport const a${index} = ${index};\n`)
    );
    await run(
      options(box, { mode: 'write', concurrency: 3, workerThreshold: 1, workerEntry: entry })
    );
    for (const [index, file] of files.entries()) {
      expect(readFileSync(file, 'utf8')).toBe(`export const a${index} = ${index};\n`);
    }
  });
});

describe('unreadable and unwritable files', () => {
  let box: Sandbox;

  beforeEach(() => {
    box = sandbox();
  });

  afterEach(() => {
    chmodSync(box.dir, 0o700);
    box.cleanup();
  });

  it('reports a write failure without throwing', async () => {
    const file = box.write('a.ts', '// note\nexport const a = 1;\n');
    chmodSync(file, 0o444);
    const result = await run(options(box, { mode: 'write' }));
    chmodSync(file, 0o644);
    expect(result.summary.errors).toBe(1);
    expect(result.exitCode).toBe(1);
    expect(result.files[0]?.error).toBeTruthy();
  });
});
