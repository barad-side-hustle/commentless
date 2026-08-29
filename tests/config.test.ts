import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { ConfigError, loadConfig, validateConfig } from '../src/config.js';
import { sandbox, type Sandbox } from './helpers.js';

describe('validateConfig', () => {
  it('accepts a complete configuration', () => {
    const config = validateConfig(
      {
        ext: ['ts', 'tsx'],
        ignore: ['db/generated/**'],
        ignoreFile: '.commentlessignore',
        gitignore: true,
        keep: ['https?://'],
        defaultKeep: true,
        collapseBlankLines: true,
        maxAllowed: 3,
        reporter: 'github',
        concurrency: 4,
        cache: false,
      },
      'test'
    );
    expect(config.keep).toEqual(['https?://']);
    expect(config.reporter).toBe('github');
  });

  it('rejects unknown options and names the valid ones', () => {
    expect(() => validateConfig({ nope: 1 }, 'test')).toThrow(/unknown option "nope"/);
    expect(() => validateConfig({ nope: 1 }, 'test')).toThrow(/collapseBlankLines/);
  });

  it('rejects a non-object', () => {
    expect(() => validateConfig(['ts'], 'test')).toThrow(ConfigError);
    expect(() => validateConfig(null, 'test')).toThrow(/must be a JSON object/);
  });

  it('rejects wrong types', () => {
    expect(() => validateConfig({ ext: 'ts' }, 'test')).toThrow(/"ext" must be an array/);
    expect(() => validateConfig({ gitignore: 'yes' }, 'test')).toThrow(/must be a boolean/);
    expect(() => validateConfig({ maxAllowed: -1 }, 'test')).toThrow(/non-negative integer/);
    expect(() => validateConfig({ reporter: 'xml' }, 'test')).toThrow(/must be one of/);
  });

  it('rejects an invalid keep pattern', () => {
    expect(() => validateConfig({ keep: ['('] }, 'test')).toThrow(/not a valid regular expression/);
  });
});

describe('loadConfig', () => {
  let box: Sandbox;

  beforeEach(() => {
    box = sandbox();
  });

  afterEach(() => box.cleanup());

  it('returns an empty config when nothing is found', () => {
    box.write('package.json', '{"name":"x"}');
    expect(loadConfig(box.dir)).toEqual({ config: {}, source: null });
  });

  it('reads commentless.config.json', () => {
    box.write('commentless.config.json', '{"maxAllowed": 2}');
    expect(loadConfig(box.dir).config.maxAllowed).toBe(2);
  });

  it('reads the package.json key', () => {
    box.write('package.json', '{"name":"x","commentless":{"ext":["ts"]}}');
    expect(loadConfig(box.dir).config.ext).toEqual(['ts']);
  });

  it('prefers commentless.config.json over the package.json key', () => {
    box.write('package.json', '{"name":"x","commentless":{"maxAllowed": 9}}');
    box.write('commentless.config.json', '{"maxAllowed": 1}');
    expect(loadConfig(box.dir).config.maxAllowed).toBe(1);
  });

  it('walks up to a parent directory', () => {
    box.write('commentless.config.json', '{"maxAllowed": 5}');
    box.write('packages/app/index.ts', 'export const a = 1;\n');
    expect(loadConfig(`${box.dir}/packages/app`).config.maxAllowed).toBe(5);
  });

  it('honours an explicit path', () => {
    box.write('custom.json', '{"maxAllowed": 7}');
    expect(loadConfig(box.dir, 'custom.json').config.maxAllowed).toBe(7);
  });

  it('fails on a missing explicit path', () => {
    expect(() => loadConfig(box.dir, 'missing.json')).toThrow(/config file not found/);
  });

  it('fails on invalid JSON', () => {
    box.write('commentless.config.json', '{');
    expect(() => loadConfig(box.dir)).toThrow(/invalid JSON/);
  });
});
