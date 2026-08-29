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

describe('init and package.json scripts', () => {
  let box: Sandbox;

  beforeEach(() => {
    box = sandbox();
    box.write('package.json', '{\n  "name": "demo"\n}\n');
  });

  afterEach(() => box.cleanup());

  const scripts = () => JSON.parse(readFileSync(`${box.dir}/package.json`, 'utf8')).scripts ?? {};

  it('asks before adding, and adds on yes', async () => {
    const asked: string[] = [];
    const result = await init(
      options(box, {
        confirm: async question => {
          asked.push(question);
          return true;
        },
      })
    );

    expect(asked).toEqual(['Add them?']);
    expect(result.scriptsAdded).toEqual(['comments:remove', 'comments:check']);
    expect(scripts()['comments:check']).toContain('--check');
    expect(result.output).toContain('Added to package.json');
  });

  it('adds nothing on no, and says so', async () => {
    const result = await init(options(box, { confirm: async () => false }));

    expect(result.scriptsAdded).toEqual([]);
    expect(scripts()).toEqual({});
    expect(result.output).toContain('Skipped');
  });

  it('shows what it is about to add before asking', async () => {
    const result = await init(options(box, { confirm: async () => false }));
    expect(result.output).toContain('These scripts are missing from package.json');
    expect(result.output).toContain('comments:remove: bunx -y commentless@');
  });

  it('adds without asking when scripts is true', async () => {
    const result = await init(options(box, { scripts: true }));
    expect(result.scriptsAdded).toHaveLength(2);
  });

  it('never asks and never adds when scripts is false', async () => {
    let asked = false;
    const result = await init(
      options(box, {
        scripts: false,
        confirm: async () => {
          asked = true;
          return true;
        },
      })
    );

    expect(asked).toBe(false);
    expect(result.scriptsAdded).toEqual([]);
    expect(scripts()).toEqual({});
  });

  it('adds nothing when there is nobody to ask', async () => {
    const result = await init(options(box));
    expect(result.scriptsAdded).toEqual([]);
    expect(scripts()).toEqual({});
  });

  it('leaves an existing script alone and only adds the missing one', async () => {
    box.write('package.json', '{"scripts":{"comments:remove":"my own thing"}}');
    const result = await init(options(box, { confirm: async () => true }));

    expect(result.scriptsAdded).toEqual(['comments:check']);
    expect(scripts()['comments:remove']).toBe('my own thing');
  });

  it('does not ask when both scripts are already there', async () => {
    box.write('package.json', '{"scripts":{"comments:remove":"a","comments:check":"b"}}');
    let asked = false;
    const result = await init(
      options(box, {
        confirm: async () => {
          asked = true;
          return true;
        },
      })
    );

    expect(asked).toBe(false);
    expect(result.scriptsAdded).toEqual([]);
    expect(result.output).toContain('already has');
  });

  it('does not fall over when there is no package.json', async () => {
    const bare = sandbox();
    try {
      const result = await init(options(bare, { confirm: async () => true }));
      expect(result.scriptsAdded).toEqual([]);
      expect(result.existed).toBe(false);
    } finally {
      bare.cleanup();
    }
  });

  it('points at the npm scripts once it has written them', async () => {
    const result = await init(options(box, { scripts: true }));
    expect(result.output).toContain('run comments:check in CI');
  });
});
