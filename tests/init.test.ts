import { readFileSync } from 'node:fs';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { defaultConfig, init } from '../src/init.js';
import { resolveKeepRules } from '../src/core/keep.js';
import { validateConfig } from '../src/config.js';
import { sandbox, type Sandbox } from './helpers.js';

const KEEP = resolveKeepRules({});

function options(box: Sandbox, overrides: Partial<Parameters<typeof init>[0]> = {}) {
  return {
    cwd: box.dir,
    extensions: ['ts', 'tsx'],
    ignore: [],
    ignoreFile: '.commentlessignore' as const,
    gitignore: true,
    keep: KEEP,
    ...overrides,
  };
}

describe('init', () => {
  let box: Sandbox;

  beforeEach(() => {
    box = sandbox();
  });

  afterEach(() => box.cleanup());

  it('writes a config file the validator accepts', async () => {
    box.write('a.ts', 'export const a = 1;\n');
    const result = await init(options(box));

    expect(result.existed).toBe(false);
    expect(result.file).toBe(`${box.dir}/commentless.config.json`);

    const written = JSON.parse(readFileSync(result.file, 'utf8'));
    expect(() => validateConfig(written, 'test')).not.toThrow();
    expect(written).toMatchObject({ ext: ['ts', 'tsx'], maxAllowed: 0, reporter: 'pretty' });
  });

  it('ends the file with a newline', async () => {
    const result = await init(options(box));
    expect(readFileSync(result.file, 'utf8').endsWith('}\n')).toBe(true);
  });

  it('baselines maxAllowed to the comments it found', async () => {
    box.write('a.ts', '// one\n// two\nexport const a = 1;\n');
    box.write('b.ts', '// three\nexport const b = 2;\n');

    const result = await init(options(box));
    expect(result.found).toBe(3);
    expect(result.config.maxAllowed).toBe(3);
    expect(result.output).toContain('Ratchet it down');
  });

  it('does not count comments the keep rules protect', async () => {
    box.write('a.ts', '// eslint-disable-next-line no-console\nconsole.log(1);\n');
    const result = await init(options(box));
    expect(result.found).toBe(0);
    expect(result.config.maxAllowed).toBe(0);
    expect(result.output).toContain('no strippable comments found');
  });

  it('sets maxAllowed to 0 under --strict', async () => {
    box.write('a.ts', '// one\nexport const a = 1;\n');
    const result = await init(options(box, { strict: true }));
    expect(result.found).toBe(1);
    expect(result.config.maxAllowed).toBe(0);
    expect(result.output).toContain('fails until you run');
  });

  it('refuses to clobber an existing config', async () => {
    box.write('commentless.config.json', '{"maxAllowed": 7}');
    const result = await init(options(box));

    expect(result.existed).toBe(true);
    expect(result.output).toContain('--force');
    expect(JSON.parse(readFileSync(result.file, 'utf8')).maxAllowed).toBe(7);
  });

  it('overwrites with --force', async () => {
    box.write('commentless.config.json', '{"maxAllowed": 7}');
    const result = await init(options(box, { force: true }));

    expect(result.existed).toBe(false);
    expect(JSON.parse(readFileSync(result.file, 'utf8')).maxAllowed).toBe(0);
  });

  it('honours a custom config path', async () => {
    const result = await init(options(box, { configPath: 'tools/cl.json' }));
    expect(result.file).toBe(`${box.dir}/tools/cl.json`);
  });

  it('carries the resolved ext and ignore into the file', async () => {
    const result = await init(
      options(box, { extensions: ['ts'], ignore: ['vendor/**', 'legacy/**'] })
    );
    expect(result.config.ext).toEqual(['ts']);
    expect(result.config.ignore).toEqual(['vendor/**', 'legacy/**']);
  });

  it('never writes to the files it scans', async () => {
    const file = box.write('a.ts', '// one\nexport const a = 1;\n');
    await init(options(box));
    expect(readFileSync(file, 'utf8')).toBe('// one\nexport const a = 1;\n');
  });

  it('produces defaults that round-trip through the validator', () => {
    expect(() => validateConfig(defaultConfig(), 'test')).not.toThrow();
  });
});
