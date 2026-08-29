import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { discoverFiles, type DiscoverOptions } from '../src/core/files.js';
import { sandbox, type Sandbox } from './helpers.js';

const BASE: Omit<DiscoverOptions, 'cwd'> = {
  paths: ['.'],
  extensions: ['ts', 'tsx', 'js'],
  ignore: [],
  ignoreFile: '.commentlessignore',
  gitignore: true,
  mode: 'all',
};

function relatives(cwd: string, files: string[]): string[] {
  return files.map(file => path.relative(cwd, file).split(path.sep).join('/')).sort();
}

describe('discoverFiles', () => {
  let box: Sandbox;

  beforeEach(() => {
    box = sandbox();
    box.write('src/a.ts', 'export const a = 1;\n');
    box.write('src/b.tsx', 'export const B = () => null;\n');
    box.write('src/c.css', 'body { color: red; }\n');
    box.write('vendor/d.ts', 'export const d = 1;\n');
    box.write('node_modules/pkg/e.ts', 'export const e = 1;\n');
    box.write('dist/f.ts', 'export const f = 1;\n');
  });

  afterEach(() => box.cleanup());

  it('filters by extension and always skips node_modules', async () => {
    const files = await discoverFiles({ ...BASE, cwd: box.dir });
    expect(relatives(box.dir, files)).toEqual([
      'dist/f.ts',
      'src/a.ts',
      'src/b.tsx',
      'vendor/d.ts',
    ]);
  });

  it('honours --ignore globs', async () => {
    const files = await discoverFiles({ ...BASE, cwd: box.dir, ignore: ['vendor/**', 'dist/**'] });
    expect(relatives(box.dir, files)).toEqual(['src/a.ts', 'src/b.tsx']);
  });

  it('honours the ignore file', async () => {
    box.write('.commentlessignore', 'vendor\ndist\n');
    const files = await discoverFiles({ ...BASE, cwd: box.dir });
    expect(relatives(box.dir, files)).toEqual(['src/a.ts', 'src/b.tsx']);
  });

  it('ignores the ignore file when it is disabled', async () => {
    box.write('.commentlessignore', 'vendor\n');
    const files = await discoverFiles({ ...BASE, cwd: box.dir, ignoreFile: false });
    expect(relatives(box.dir, files)).toContain('vendor/d.ts');
  });

  it('scopes to explicit positional paths', async () => {
    const files = await discoverFiles({ ...BASE, cwd: box.dir, paths: ['src'] });
    expect(relatives(box.dir, files)).toEqual(['src/a.ts', 'src/b.tsx']);
  });

  it('accepts a single file as a positional path', async () => {
    const files = await discoverFiles({ ...BASE, cwd: box.dir, paths: ['src/a.ts'] });
    expect(relatives(box.dir, files)).toEqual(['src/a.ts']);
  });
});

describe('discoverFiles in a git repository', () => {
  let box: Sandbox;

  const git = (...args: string[]) => execFileSync('git', args, { cwd: box.dir, stdio: 'pipe' });
  let defaultBranch = 'main';

  beforeEach(() => {
    box = sandbox();
    git('init', '-q');
    git('config', 'user.email', 'test@example.com');
    git('config', 'user.name', 'test');
    box.write('.gitignore', 'generated/\n');
    box.write('src/a.ts', 'export const a = 1;\n');
    box.write('generated/schema.ts', 'export const s = 1;\n');
    git('add', '-A');
    git('commit', '-qm', 'init');
    defaultBranch = git('rev-parse', '--abbrev-ref', 'HEAD').toString().trim();
  });

  afterEach(() => box.cleanup());

  it('honours .gitignore', async () => {
    const files = await discoverFiles({ ...BASE, cwd: box.dir });
    expect(relatives(box.dir, files)).toEqual(['src/a.ts']);
  });

  it('sees gitignored files when gitignore is disabled', async () => {
    const files = await discoverFiles({ ...BASE, cwd: box.dir, gitignore: false });
    expect(relatives(box.dir, files)).toContain('generated/schema.ts');
  });

  it('includes untracked files', async () => {
    box.write('src/new.ts', 'export const n = 1;\n');
    const files = await discoverFiles({ ...BASE, cwd: box.dir });
    expect(relatives(box.dir, files)).toEqual(['src/a.ts', 'src/new.ts']);
  });

  it('limits --staged to the index', async () => {
    box.write('src/new.ts', 'export const n = 1;\n');
    box.write('src/other.ts', 'export const o = 1;\n');
    git('add', 'src/new.ts');
    const files = await discoverFiles({ ...BASE, cwd: box.dir, mode: 'staged' });
    expect(relatives(box.dir, files)).toEqual(['src/new.ts']);
  });

  it('limits --changed to the diff against a base ref', async () => {
    git('checkout', '-qb', 'feature');
    box.write('src/changed.ts', 'export const c = 1;\n');
    git('add', '-A');
    git('commit', '-qm', 'change');
    const files = await discoverFiles({
      ...BASE,
      cwd: box.dir,
      mode: 'changed',
      base: defaultBranch,
    });
    expect(relatives(box.dir, files)).toEqual(['src/changed.ts']);
  });

  it('resolves paths relative to the repository root from a subdirectory', async () => {
    const files = await discoverFiles({ ...BASE, cwd: path.join(box.dir, 'src') });
    expect(relatives(path.join(box.dir, 'src'), files)).toEqual(['a.ts']);
  });
});
