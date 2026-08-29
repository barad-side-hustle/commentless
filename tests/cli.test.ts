import { readFileSync } from 'node:fs';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { main } from '../src/cli.js';
import { sandbox, type Sandbox } from './helpers.js';

interface Capture {
  stdout: string;
  stderr: string;
}

async function cli(args: string[], cwd: string): Promise<{ code: number } & Capture> {
  const capture: Capture = { stdout: '', stderr: '' };
  const originalCwd = process.cwd();
  const stdout = vi.spyOn(process.stdout, 'write').mockImplementation(chunk => {
    capture.stdout += String(chunk);
    return true;
  });
  const stderr = vi.spyOn(process.stderr, 'write').mockImplementation(chunk => {
    capture.stderr += String(chunk);
    return true;
  });
  process.chdir(cwd);
  try {
    const code = await main(args);
    return { code, ...capture };
  } finally {
    process.chdir(originalCwd);
    stdout.mockRestore();
    stderr.mockRestore();
  }
}

describe('cli', () => {
  let box: Sandbox;

  beforeEach(() => {
    box = sandbox();
    box.write('commentless.config.json', '{"cache": false}');
  });

  afterEach(() => box.cleanup());

  it('prints help and exits 0', async () => {
    const result = await cli(['--help'], box.dir);
    expect(result.code).toBe(0);
    expect(result.stdout).toContain('Usage');
    expect(result.stdout).toContain('--check');
  });

  it('prints the version', async () => {
    const result = await cli(['--version'], box.dir);
    expect(result.code).toBe(0);
    expect(result.stdout.trim()).toMatch(/^\d+\.\d+\.\d+$/);
  });

  it('exits 0 on a clean tree', async () => {
    box.write('a.ts', 'export const a = 1;\n');
    expect((await cli(['--check'], box.dir)).code).toBe(0);
  });

  it('exits 1 when --check finds a comment', async () => {
    box.write('a.ts', '// note\nexport const a = 1;\n');
    const result = await cli(['--check', '--reporter', 'summary'], box.dir);
    expect(result.code).toBe(1);
    expect(result.stdout).toContain('1 comment to remove');
  });

  it('writes by default', async () => {
    const file = box.write('a.ts', '// note\nexport const a = 1;\n');
    expect((await cli([], box.dir)).code).toBe(0);
    expect(readFileSync(file, 'utf8')).toBe('export const a = 1;\n');
  });

  it('exits 2 on an unknown flag', async () => {
    const result = await cli(['--nope'], box.dir);
    expect(result.code).toBe(2);
    expect(result.stderr).toContain('--help');
  });

  it('exits 2 when --check and --write are combined', async () => {
    const result = await cli(['--check', '--write'], box.dir);
    expect(result.code).toBe(2);
    expect(result.stderr).toContain('mutually exclusive');
  });

  it('exits 2 on an unknown reporter', async () => {
    expect((await cli(['--reporter', 'xml'], box.dir)).code).toBe(2);
  });

  it('exits 2 on an invalid config', async () => {
    box.write('commentless.config.json', '{"maxAllowed": "many"}');
    const result = await cli(['--check'], box.dir);
    expect(result.code).toBe(2);
    expect(result.stderr).toContain('non-negative integer');
  });

  it('exits 2 on a non-numeric --max-allowed', async () => {
    expect((await cli(['--check', '--max-allowed', 'lots'], box.dir)).code).toBe(2);
  });

  it('reads keep patterns from the config file', async () => {
    box.write('commentless.config.json', '{"cache": false, "keep": ["https?://"]}');
    box.write('a.ts', '// see https://example.com\nexport const a = 1;\n');
    expect((await cli(['--check'], box.dir)).code).toBe(0);
  });

  it('lets a CLI --keep flag add to the config patterns', async () => {
    box.write('a.ts', '// KEEPME\nexport const a = 1;\n');
    expect((await cli(['--check'], box.dir)).code).toBe(1);
    expect((await cli(['--check', '--keep', 'KEEPME'], box.dir)).code).toBe(0);
  });

  it('honours --no-default-keep', async () => {
    box.write('a.ts', '// eslint-disable-next-line no-console\nconsole.log(1);\n');
    expect((await cli(['--check'], box.dir)).code).toBe(0);
    expect((await cli(['--check', '--no-default-keep'], box.dir)).code).toBe(1);
  });

  it('honours --ext', async () => {
    box.write('a.js', '// note\nconst a = 1;\n');
    expect((await cli(['--check', '--ext', 'ts'], box.dir)).code).toBe(0);
    expect((await cli(['--check', '--ext', 'js'], box.dir)).code).toBe(1);
  });

  it('honours repeated --ignore flags', async () => {
    box.write('vendor/a.ts', '// note\nexport const a = 1;\n');
    box.write('legacy/b.ts', '// note\nexport const b = 1;\n');
    expect((await cli(['--check'], box.dir)).code).toBe(1);
    expect(
      (await cli(['--check', '--ignore', 'vendor/**', '--ignore', 'legacy/**'], box.dir)).code
    ).toBe(0);
  });

  it('scopes to a positional path', async () => {
    box.write('src/a.ts', 'export const a = 1;\n');
    box.write('other/b.ts', '// note\nexport const b = 1;\n');
    expect((await cli(['src', '--check'], box.dir)).code).toBe(0);
    expect((await cli(['--check'], box.dir)).code).toBe(1);
  });

  it('lists resolved files and exits without processing', async () => {
    const file = box.write('a.ts', '// note\nexport const a = 1;\n');
    const result = await cli(['--list-files'], box.dir);
    expect(result.code).toBe(0);
    expect(result.stdout.trim().split('\n')).toContain('a.ts');
    expect(readFileSync(file, 'utf8')).toContain('// note');
  });

  it('emits github annotations', async () => {
    box.write('a.ts', '// note\nexport const a = 1;\n');
    const result = await cli(['--check', '--reporter', 'github'], box.dir);
    expect(result.code).toBe(1);
    expect(result.stdout).toContain('::error file=a.ts,line=1,col=1,title=commentless::');
  });

  it('emits parseable json', async () => {
    box.write('a.ts', '// note\nexport const a = 1;\n');
    const result = await cli(['--check', '--reporter', 'json'], box.dir);
    const parsed = JSON.parse(result.stdout);
    expect(parsed.files[0].file).toBe('a.ts');
    expect(parsed.summary.commentsRemoved).toBe(1);
  });

  it('errors clearly when --changed has no resolvable base', async () => {
    box.write('a.ts', 'export const a = 1;\n');
    const result = await cli(['--check', '--changed'], box.dir);
    expect(result.code).toBe(1);
    expect(result.stderr).toContain('git repository');
  });
});
