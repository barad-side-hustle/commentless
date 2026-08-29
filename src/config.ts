import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { KEEP_RULE_NAMES } from './core/keep.js';
import { REPORTERS, type ReporterName } from './reporters/index.js';

export const CONFIG_FILE_NAME = 'commentless.config.json';

export interface FileConfig {
  ext?: string[];
  ignore?: string[];
  ignoreFile?: string | false;
  gitignore?: boolean;
  keep?: string[];
  defaultKeep?: boolean;
  disableKeep?: string[];
  keepOnly?: string[];
  collapseBlankLines?: boolean;
  maxAllowed?: number;
  reporter?: ReporterName;
  concurrency?: number;
  cache?: boolean;
}

export class ConfigError extends Error {}

const KNOWN_KEYS: readonly (keyof FileConfig)[] = [
  'ext',
  'ignore',
  'ignoreFile',
  'gitignore',
  'keep',
  'defaultKeep',
  'disableKeep',
  'keepOnly',
  'collapseBlankLines',
  'maxAllowed',
  'reporter',
  'concurrency',
  'cache',
];

function fail(source: string, message: string): never {
  throw new ConfigError(`${source}: ${message}`);
}

function assertStringArray(source: string, key: string, value: unknown): string[] {
  if (!Array.isArray(value) || value.some(entry => typeof entry !== 'string')) {
    fail(source, `"${key}" must be an array of strings`);
  }
  return value as string[];
}

function assertBoolean(source: string, key: string, value: unknown): boolean {
  if (typeof value !== 'boolean') fail(source, `"${key}" must be a boolean`);
  return value;
}

function assertNonNegativeInteger(source: string, key: string, value: unknown): number {
  if (typeof value !== 'number' || !Number.isInteger(value) || value < 0) {
    fail(source, `"${key}" must be a non-negative integer`);
  }
  return value;
}

export function validateConfig(raw: unknown, source: string): FileConfig {
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) {
    fail(source, 'configuration must be a JSON object');
  }

  const input = raw as Record<string, unknown>;
  const config: FileConfig = {};

  for (const key of Object.keys(input)) {
    if (!(KNOWN_KEYS as readonly string[]).includes(key)) {
      fail(source, `unknown option "${key}". Valid options: ${KNOWN_KEYS.join(', ')}`);
    }
  }

  if (input.ext !== undefined) config.ext = assertStringArray(source, 'ext', input.ext);
  if (input.ignore !== undefined) config.ignore = assertStringArray(source, 'ignore', input.ignore);
  if (input.keep !== undefined) {
    config.keep = assertStringArray(source, 'keep', input.keep);
    for (const pattern of config.keep) {
      try {
        new RegExp(pattern);
      } catch (error) {
        fail(
          source,
          `"keep" entry ${JSON.stringify(pattern)} is not a valid regular expression (${
            error instanceof Error ? error.message : String(error)
          })`
        );
      }
    }
  }
  if (input.ignoreFile !== undefined) {
    if (typeof input.ignoreFile !== 'string' && input.ignoreFile !== false) {
      fail(source, '"ignoreFile" must be a path string or false');
    }
    config.ignoreFile = input.ignoreFile;
  }
  if (input.gitignore !== undefined) {
    config.gitignore = assertBoolean(source, 'gitignore', input.gitignore);
  }
  if (input.defaultKeep !== undefined) {
    config.defaultKeep = assertBoolean(source, 'defaultKeep', input.defaultKeep);
  }
  for (const key of ['disableKeep', 'keepOnly'] as const) {
    if (input[key] === undefined) continue;
    const names = assertStringArray(source, key, input[key]);
    const unknown = names.filter(name => !KEEP_RULE_NAMES.includes(name));
    if (unknown.length > 0) {
      fail(
        source,
        `"${key}" contains unknown keep rule${unknown.length === 1 ? '' : 's'} ` +
          `${unknown.map(name => JSON.stringify(name)).join(', ')}. ` +
          `Valid rules: ${KEEP_RULE_NAMES.join(', ')}`
      );
    }
    config[key] = names;
  }
  if (input.collapseBlankLines !== undefined) {
    config.collapseBlankLines = assertBoolean(
      source,
      'collapseBlankLines',
      input.collapseBlankLines
    );
  }
  if (input.cache !== undefined) config.cache = assertBoolean(source, 'cache', input.cache);
  if (input.maxAllowed !== undefined) {
    config.maxAllowed = assertNonNegativeInteger(source, 'maxAllowed', input.maxAllowed);
  }
  if (input.concurrency !== undefined) {
    const value = assertNonNegativeInteger(source, 'concurrency', input.concurrency);
    if (value < 1) fail(source, '"concurrency" must be at least 1');
    config.concurrency = value;
  }
  if (input.reporter !== undefined) {
    if (typeof input.reporter !== 'string' || !REPORTERS.includes(input.reporter as ReporterName)) {
      fail(source, `"reporter" must be one of: ${REPORTERS.join(', ')}`);
    }
    config.reporter = input.reporter as ReporterName;
  }

  return config;
}

function readJson(file: string): unknown {
  let text: string;
  try {
    text = readFileSync(file, 'utf8');
  } catch (error) {
    throw new ConfigError(
      `${file}: cannot be read (${error instanceof Error ? error.message : String(error)})`
    );
  }
  try {
    return JSON.parse(text);
  } catch (error) {
    throw new ConfigError(
      `${file}: invalid JSON (${error instanceof Error ? error.message : String(error)})`
    );
  }
}

export interface LoadedConfig {
  config: FileConfig;
  source: string | null;
}

export function loadConfig(cwd: string, explicitPath?: string): LoadedConfig {
  if (explicitPath) {
    const file = path.resolve(cwd, explicitPath);
    if (!existsSync(file)) throw new ConfigError(`${explicitPath}: config file not found`);
    return { config: validateConfig(readJson(file), explicitPath), source: file };
  }

  let directory = path.resolve(cwd);
  for (;;) {
    const configFile = path.join(directory, CONFIG_FILE_NAME);
    if (existsSync(configFile)) {
      return { config: validateConfig(readJson(configFile), configFile), source: configFile };
    }

    const packageFile = path.join(directory, 'package.json');
    if (existsSync(packageFile)) {
      const parsed = readJson(packageFile) as Record<string, unknown>;
      if (parsed.commentless !== undefined) {
        return {
          config: validateConfig(parsed.commentless, `${packageFile} > "commentless"`),
          source: packageFile,
        };
      }
    }

    const parent = path.dirname(directory);
    if (parent === directory) return { config: {}, source: null };
    directory = parent;
  }
}
