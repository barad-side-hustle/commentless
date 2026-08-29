import path from 'node:path';
import { parseArgs } from 'node:util';
import { createColors } from 'picocolors';
import { ConfigError, loadConfig } from './config.js';
import { DEFAULT_EXTENSIONS } from './core/scan.js';
import { discoverFiles, type DiscoveryMode } from './core/files.js';
import { defaultConcurrency, run } from './core/run.js';
import { resolveKeepRules } from './core/keep.js';
import { report, REPORTERS, type ReporterName } from './reporters/index.js';
import type { RunMode } from './types.js';

const VERSION = '0.1.0';

const HELP = `commentless ${VERSION}

  Strip comments from JavaScript and TypeScript with an AST, keep the ones that
  do work (eslint-disable, @ts-expect-error, licences, ...), and fail CI when
  new ones appear.

Usage
  commentless [paths...] [options]

Mode
  --check                  Report only, never write. Exit 1 if a comment would be removed.
  --write                  Rewrite files in place. Default when --check is absent.
  --dry-run                Report what --write would do, write nothing. Always exits 0.

Scope
  --staged                 Only files staged in git.
  --changed                Only files changed against --base.
  --base <ref>             Base ref for --changed (default: origin/HEAD, then main).
  --ext <list>             Comma-separated extensions (default: ${DEFAULT_EXTENSIONS.join(',')}).
  --ignore <glob>          Gitignore-syntax pattern to skip. Repeatable.
  --ignore-file <path>     Ignore file to read (default: .commentlessignore).
  --no-gitignore           Stop honouring .gitignore.
  --list-files             Print the resolved file list and exit.

Comments to keep
  --keep <regex>           Keep comments matching this pattern. Repeatable.
  --no-default-keep        Drop the built-in directive allowlist. Dangerous.
  --collapse-blank-lines   Also trim trailing whitespace and collapse 3+ blank lines.

Output
  --reporter <name>        ${REPORTERS.join(' | ')} (default: pretty).
  --max-allowed <n>        --check passes while removable comments are at or under n.
  -q, --quiet              Summary only.
  -v, --verbose            Include kept-comment counts.
  --no-color               Disable colour.

Other
  --concurrency <n>        Worker threads (default: cpus - 1).
  --no-cache               Skip the clean-file cache.
  --config <path>          Path to a commentless.config.json.
  -h, --help               Show this help.
  --version                Print the version.

Exit codes
  0  clean
  1  comments found under --check, or a file could not be processed
  2  bad usage or invalid configuration

Inline escapes
  commentless-keep             keep this comment
  commentless-keep-next-line   keep the comment that follows
  commentless-ignore-file      skip the whole file
`;

class UsageError extends Error {}

function parseExtensions(value: string): string[] {
  const extensions = value
    .split(',')
    .map(entry => entry.trim().replace(/^\./, '').toLowerCase())
    .filter(Boolean);
  if (extensions.length === 0) throw new UsageError('--ext needs at least one extension');
  return extensions;
}

function parseInteger(flag: string, value: string, minimum: number): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < minimum) {
    throw new UsageError(`${flag} must be an integer >= ${minimum}`);
  }
  return parsed;
}

export async function main(argv: readonly string[]): Promise<number> {
  let parsed;
  try {
    parsed = parseArgs({
      args: [...argv],
      allowPositionals: true,
      strict: true,
      options: {
        check: { type: 'boolean' },
        write: { type: 'boolean' },
        'dry-run': { type: 'boolean' },
        staged: { type: 'boolean' },
        changed: { type: 'boolean' },
        base: { type: 'string' },
        ext: { type: 'string' },
        ignore: { type: 'string', multiple: true },
        'ignore-file': { type: 'string' },
        'no-gitignore': { type: 'boolean' },
        'list-files': { type: 'boolean' },
        keep: { type: 'string', multiple: true },
        'no-default-keep': { type: 'boolean' },
        'collapse-blank-lines': { type: 'boolean' },
        reporter: { type: 'string' },
        'max-allowed': { type: 'string' },
        quiet: { type: 'boolean', short: 'q' },
        verbose: { type: 'boolean', short: 'v' },
        'no-color': { type: 'boolean' },
        concurrency: { type: 'string' },
        'no-cache': { type: 'boolean' },
        config: { type: 'string' },
        help: { type: 'boolean', short: 'h' },
        version: { type: 'boolean' },
      },
    });
  } catch (error) {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.stderr.write('Run `commentless --help` for usage.\n');
    return 2;
  }

  const { values, positionals } = parsed;

  if (values.help) {
    process.stdout.write(HELP);
    return 0;
  }
  if (values.version) {
    process.stdout.write(`${VERSION}\n`);
    return 0;
  }

  const cwd = process.cwd();
  const colors = createColors(
    !values['no-color'] && process.stderr.isTTY === true && !process.env.NO_COLOR
  );

  try {
    if (values.check && values.write) {
      throw new UsageError('--check and --write are mutually exclusive');
    }
    if (values.staged && values.changed) {
      throw new UsageError('--staged and --changed are mutually exclusive');
    }

    const { config } = loadConfig(cwd, values.config);

    const reporterName = (values.reporter ?? config.reporter ?? 'pretty') as ReporterName;
    if (!REPORTERS.includes(reporterName)) {
      throw new UsageError(`--reporter must be one of: ${REPORTERS.join(', ')}`);
    }

    const mode: RunMode = values.check ? 'check' : values['dry-run'] ? 'dry-run' : 'write';
    const discovery: DiscoveryMode = values.staged ? 'staged' : values.changed ? 'changed' : 'all';

    const keep = resolveKeepRules({
      defaults: values['no-default-keep'] ? false : (config.defaultKeep ?? true),
      userPatterns: [...(config.keep ?? []), ...(values.keep ?? [])],
    });

    const paths = positionals.length > 0 ? positionals : ['.'];
    const extensions = values.ext
      ? parseExtensions(values.ext)
      : (config.ext ?? [...DEFAULT_EXTENSIONS]);
    const ignore = [...(config.ignore ?? []), ...(values.ignore ?? [])];
    const ignoreFile = values['ignore-file'] ?? config.ignoreFile ?? '.commentlessignore';
    const gitignore = values['no-gitignore'] ? false : (config.gitignore ?? true);

    if (values['list-files']) {
      const files = await discoverFiles({
        cwd,
        paths,
        extensions,
        ignore,
        ignoreFile,
        gitignore,
        mode: discovery,
        base: values.base,
      });
      const listed = files.map(file => path.relative(cwd, file).split(path.sep).join('/'));
      process.stdout.write(listed.length > 0 ? `${listed.join('\n')}\n` : '');
      return 0;
    }

    const result = await run({
      cwd,
      paths,
      mode,
      discovery,
      base: values.base,
      extensions,
      ignore,
      ignoreFile,
      gitignore,
      keep,
      collapseBlankLines: values['collapse-blank-lines'] ?? config.collapseBlankLines ?? false,
      maxAllowed: values['max-allowed']
        ? parseInteger('--max-allowed', values['max-allowed'], 0)
        : (config.maxAllowed ?? 0),
      concurrency: values.concurrency
        ? parseInteger('--concurrency', values.concurrency, 1)
        : (config.concurrency ?? defaultConcurrency()),
      cache: values['no-cache'] ? false : (config.cache ?? true),
    });

    process.stdout.write(
      `${report(reporterName, result, {
        cwd,
        quiet: values.quiet ?? false,
        verbose: values.verbose ?? false,
        color: !values['no-color'] && process.stdout.isTTY === true && !process.env.NO_COLOR,
      })}\n`
    );

    return result.exitCode;
  } catch (error) {
    if (error instanceof UsageError || error instanceof ConfigError) {
      process.stderr.write(`${colors.red('error')} ${error.message}\n`);
      return 2;
    }
    process.stderr.write(
      `${colors.red('error')} ${
        error instanceof Error ? (error.stack ?? error.message) : String(error)
      }\n`
    );
    return 1;
  }
}
