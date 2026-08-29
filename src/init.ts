import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { createColors } from 'picocolors';
import { CONFIG_FILE_NAME, type FileConfig } from './config.js';
import type { DiscoveryMode } from './core/files.js';
import { run } from './core/run.js';
import { DEFAULT_EXTENSIONS } from './core/scan.js';
import type { KeepRule } from './types.js';

export interface InitOptions {
  cwd: string;
  configPath?: string | undefined;
  force?: boolean;
  strict?: boolean;
  color?: boolean;
  extensions: readonly string[];
  ignore: readonly string[];
  ignoreFile: string | false;
  gitignore: boolean;
  keep: readonly KeepRule[];
  discovery?: DiscoveryMode;
}

export interface InitResult {
  file: string;
  existed: boolean;
  found: number;
  scanned: number;
  config: FileConfig;
  output: string;
}

export function defaultConfig(): FileConfig {
  return {
    ext: [...DEFAULT_EXTENSIONS],
    ignore: [],
    keep: [],
    disableKeep: [],
    collapseBlankLines: false,
    maxAllowed: 0,
    reporter: 'pretty',
  };
}

export async function init(options: InitOptions): Promise<InitResult> {
  const pc = createColors(options.color ?? false);
  const file = path.resolve(options.cwd, options.configPath ?? CONFIG_FILE_NAME);
  const shown = path.relative(options.cwd, file).split(path.sep).join('/') || file;

  if (existsSync(file) && !options.force) {
    return {
      file,
      existed: true,
      found: 0,
      scanned: 0,
      config: {},
      output: `${pc.yellow('!')} ${shown} already exists. Re-run with --force to overwrite it.`,
    };
  }

  const scan = await run({
    cwd: options.cwd,
    mode: 'dry-run',
    extensions: options.extensions,
    ignore: options.ignore,
    ignoreFile: options.ignoreFile,
    gitignore: options.gitignore,
    keep: options.keep,
    cache: false,
    ...(options.discovery ? { discovery: options.discovery } : {}),
  });

  const found = scan.summary.commentsRemoved;
  const config: FileConfig = {
    ...defaultConfig(),
    ext: [...options.extensions],
    ignore: [...options.ignore],
    maxAllowed: options.strict ? 0 : found,
  };

  mkdirSync(path.dirname(file), { recursive: true });
  writeFileSync(file, `${JSON.stringify(config, null, 2)}\n`, 'utf8');

  const lines = [`${pc.green('✔')} Wrote ${pc.bold(shown)}`, ''];

  if (found === 0) {
    lines.push(
      `${scan.summary.discovered} files scanned, no strippable comments found.`,
      `${pc.bold('maxAllowed')} is 0 — the gate passes and stays passing.`
    );
  } else if (options.strict) {
    lines.push(
      `${scan.summary.discovered} files scanned, ${found} strippable comments found.`,
      `${pc.bold('maxAllowed')} is 0, so ${pc.bold('commentless --check')} fails until you run ${pc.bold('commentless --write')}.`
    );
  } else {
    lines.push(
      `${scan.summary.discovered} files scanned, ${pc.bold(String(found))} strippable comments found.`,
      `${pc.bold('maxAllowed')} is set to ${found} so the gate passes today. Ratchet it down as you`,
      `move those explanations into test names — that is the whole point.`
    );
  }

  lines.push(
    '',
    'Next:',
    `  1. ${pc.bold('"comments:check": "commentless --check --reporter github"')} in package.json`,
    '  2. run it in CI on every pull request',
    `  3. ${pc.bold('commentless --write')} when you are ready to remove them`
  );

  return {
    file,
    existed: false,
    found,
    scanned: scan.summary.discovered,
    config,
    output: lines.join('\n'),
  };
}
