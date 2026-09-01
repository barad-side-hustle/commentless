import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { createColors } from 'picocolors';
import { CONFIG_FILE_NAME, type FileConfig } from './config.js';
import type { DiscoveryMode } from './core/files.js';
import { run } from './core/run.js';
import { DEFAULT_EXTENSIONS } from './core/scan.js';
import { applyScripts, planScripts } from './scripts.js';
import type { KeepRule } from './types.js';

export type Confirm = (question: string) => Promise<boolean>;

export interface InitOptions {
  cwd: string;
  configPath?: string | undefined;
  force?: boolean;
  strict?: boolean;
  color?: boolean;
  scripts?: boolean | undefined;
  confirm?: Confirm | undefined;
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
  scriptsAdded: string[];
  output: string;
}

function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? '' : 's'}`;
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
      scriptsAdded: [],
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
      `${plural(scan.summary.discovered, 'file')} scanned, no strippable comments found.`,
      `${pc.bold('maxAllowed')} is 0 — the gate passes and stays passing.`
    );
  } else if (options.strict) {
    lines.push(
      `${plural(scan.summary.discovered, 'file')} scanned, ${plural(found, 'strippable comment')} found.`,
      `${pc.bold('maxAllowed')} is 0, so ${pc.bold('commentless --check')} fails until you run ${pc.bold('commentless --write')}.`
    );
  } else {
    lines.push(
      `${plural(scan.summary.discovered, 'file')} scanned, ${pc.bold(plural(found, 'strippable comment'))} found.`,
      `${pc.bold('maxAllowed')} is set to ${found} so the gate passes today. Ratchet it down as you`,
      `move those explanations into test names — that is the whole point.`
    );
  }

  const scriptsAdded = await maybeAddScripts(options, lines, pc);

  lines.push('', 'Next:');
  if (scriptsAdded.length > 0) {
    lines.push(`  1. run ${pc.bold('comments:check')} in CI on every pull request`);
    lines.push(`  2. run ${pc.bold('comments:remove')} when you are ready to delete them`);
  } else {
    lines.push('  1. run commentless --check in CI on every pull request');
    lines.push(`  2. run ${pc.bold('commentless --write')} when you are ready to delete them`);
  }

  return {
    file,
    existed: false,
    found,
    scanned: scan.summary.discovered,
    config,
    scriptsAdded,
    output: lines.join('\n'),
  };
}

async function maybeAddScripts(
  options: InitOptions,
  lines: string[],
  pc: ReturnType<typeof createColors>
): Promise<string[]> {
  const plan = planScripts(options.cwd);
  if (!plan) return [];

  const names = Object.keys(plan.missing);
  if (names.length === 0) {
    if (plan.present.length > 0) {
      lines.push('', pc.dim(`package.json already has ${plan.present.join(' and ')}.`));
    }
    return [];
  }

  const preview = names.map(name => `${name}: ${plan.missing[name]}`);

  if (options.scripts === false) return [];

  if (options.scripts !== true) {
    if (!options.confirm) return [];
    lines.push('', 'These scripts are missing from package.json:');
    for (const line of preview) lines.push(pc.dim(`  ${line}`));
    if (!(await options.confirm('Add them?'))) {
      lines.push(pc.dim('Skipped. Add them yourself when you want them.'));
      return [];
    }
  }

  applyScripts(plan);
  lines.push('', `${pc.green('✔')} Added to package.json:`);
  for (const line of preview) lines.push(pc.dim(`  ${line}`));
  return names;
}
