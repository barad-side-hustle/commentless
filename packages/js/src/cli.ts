import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { createInterface } from 'node:readline/promises';
import { parseArgs } from 'node:util';
import { createColors } from 'picocolors';
import { ConfigError, CONFIG_FILE_NAME, type FileConfig, loadConfig } from './config.js';
import { init } from './init.js';
import { DEFAULT_EXTENSIONS } from './core/scan.js';
import { discoverFiles, type DiscoveryMode } from './core/files.js';
import { defaultConcurrency, run } from './core/run.js';
import {
  KEEP_RULE_DESCRIPTIONS,
  KEEP_RULE_NAMES,
  resolveKeepRules,
  UnknownKeepRuleError,
} from './core/keep.js';
import { detectTestImport, draftTestNames } from './core/testnames.js';
import { report, REPORTERS, type ReporterName } from './reporters/index.js';
import type { RunMode } from './types.js';
import { VERSION } from './version.js';

const HELP = `commentless ${VERSION}

  Strip comments from JavaScript and TypeScript with an AST, keep the ones that
  do work (eslint-disable, @ts-expect-error, licences, ...), and fail CI when
  new ones appear.

Usage
  commentless [paths...] [options]
  commentless init [options]      Write a ${CONFIG_FILE_NAME} you can commit

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
  --no-keep <rule>         Turn off one built-in keep rule. Repeatable.
                           e.g. --no-keep jsdoc-type --no-keep license
  --keep-only <list>       Enable only these built-in rules, comma-separated.
                           e.g. --keep-only eslint,typescript
  --no-default-keep        Turn off every built-in rule. Same as --keep-only ''.
  --list-keep-rules        Print the built-in rules and what each one matches.
  --collapse-blank-lines   Also trim trailing whitespace and collapse 3+ blank lines.

Output
  --reporter <name>        ${REPORTERS.join(' | ')} (default: pretty).
  --max-allowed <n>        --check passes while removable comments are at or under n.
  --to-test-names <file>   Draft an it.todo(...) stub per comment into <file>, so the
                           explanations have somewhere to go. Pair it with --check to
                           look before you leap. --force overwrites an existing file.
  -q, --quiet              Summary only.
  -v, --verbose            Include kept-comment counts.
  --no-color               Disable colour.

init
  --force                  Overwrite an existing config file.
  --strict                 Set maxAllowed to 0 instead of today's comment count.
  --scripts                Add comments:remove and comments:check to package.json
                           without asking. --no-scripts never adds them.
                           Interactively, init asks.

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

const AGENT_PROMPT_URL =
  'https://github.com/barad-side-hustle/commentless#hand-the-skeleton-to-an-agent';

class UsageError extends Error {}

async function promptYesNo(question: string): Promise<boolean> {
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  try {
    const answer = (await rl.question(`\n${question} [Y/n] `)).trim().toLowerCase();
    return answer === '' || answer === 'y' || answer === 'yes';
  } finally {
    rl.close();
  }
}

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
        'no-keep': { type: 'string', multiple: true },
        'keep-only': { type: 'string' },
        'no-default-keep': { type: 'boolean' },
        'list-keep-rules': { type: 'boolean' },
        'collapse-blank-lines': { type: 'boolean' },
        reporter: { type: 'string' },
        'max-allowed': { type: 'string' },
        quiet: { type: 'boolean', short: 'q' },
        verbose: { type: 'boolean', short: 'v' },
        'no-color': { type: 'boolean' },
        concurrency: { type: 'string' },
        'no-cache': { type: 'boolean' },
        config: { type: 'string' },
        'to-test-names': { type: 'string' },
        force: { type: 'boolean' },
        strict: { type: 'boolean' },
        scripts: { type: 'boolean' },
        'no-scripts': { type: 'boolean' },
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
  if (values['list-keep-rules']) {
    const width = Math.max(...KEEP_RULE_NAMES.map(name => name.length));
    const lines = KEEP_RULE_NAMES.map(
      name => `  ${name.padEnd(width)}  ${KEEP_RULE_DESCRIPTIONS[name] ?? ''}`
    );
    process.stdout.write(`Built-in keep rules\n${lines.join('\n')}\n`);
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

    const isInit = positionals[0] === 'init';
    if (isInit && positionals.length > 1) {
      throw new UsageError(`init takes no paths, got ${positionals.slice(1).join(' ')}`);
    }
    if (isInit && values['to-test-names']) {
      throw new UsageError('--to-test-names does not apply to init');
    }

    const { config } = isInit ? { config: {} as FileConfig } : loadConfig(cwd, values.config);

    const reporterName = (values.reporter ?? config.reporter ?? 'pretty') as ReporterName;
    if (!REPORTERS.includes(reporterName)) {
      throw new UsageError(`--reporter must be one of: ${REPORTERS.join(', ')}`);
    }

    const mode: RunMode = values.check ? 'check' : values['dry-run'] ? 'dry-run' : 'write';
    const discovery: DiscoveryMode = values.staged ? 'staged' : values.changed ? 'changed' : 'all';

    const keepOnly = values['keep-only']
      ? values['keep-only']
          .split(',')
          .map(name => name.trim())
          .filter(Boolean)
      : config.keepOnly;

    const keep = resolveKeepRules({
      defaults: values['no-default-keep'] ? false : (config.defaultKeep ?? true),
      userPatterns: [...(config.keep ?? []), ...(values.keep ?? [])],
      disable: [...(config.disableKeep ?? []), ...(values['no-keep'] ?? [])],
      ...(keepOnly ? { only: keepOnly } : {}),
    });

    const testNamesFile = values['to-test-names']
      ? path.resolve(cwd, values['to-test-names'])
      : null;
    if (testNamesFile && existsSync(testNamesFile) && !values.force) {
      throw new UsageError(
        `${values['to-test-names']} already exists. Re-run with --force to overwrite it.`
      );
    }

    const paths = !isInit && positionals.length > 0 ? positionals : ['.'];
    const extensions = values.ext
      ? parseExtensions(values.ext)
      : (config.ext ?? [...DEFAULT_EXTENSIONS]);
    const ignore = [...(config.ignore ?? []), ...(values.ignore ?? [])];
    const ignoreFile = values['ignore-file'] ?? config.ignoreFile ?? '.commentlessignore';
    const gitignore = values['no-gitignore'] ? false : (config.gitignore ?? true);
    const useColor = !values['no-color'] && process.stdout.isTTY === true && !process.env.NO_COLOR;

    if (isInit) {
      if (values.scripts && values['no-scripts']) {
        throw new UsageError('--scripts and --no-scripts are mutually exclusive');
      }
      const scripts = values.scripts ? true : values['no-scripts'] ? false : undefined;
      const interactive = process.stdin.isTTY === true && process.stdout.isTTY === true;

      const result = await init({
        cwd,
        configPath: values.config,
        force: values.force ?? false,
        strict: values.strict ?? false,
        color: useColor,
        extensions,
        ignore,
        ignoreFile,
        gitignore,
        keep,
        scripts,
        ...(scripts === undefined && interactive ? { confirm: promptYesNo } : {}),
      });
      process.stdout.write(`${result.output}\n`);
      return result.existed ? 2 : 0;
    }

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
        color: useColor,
      })}\n`
    );

    if (testNamesFile) {
      const shown = path.relative(cwd, testNamesFile).split(path.sep).join('/') || testNamesFile;
      const draft = draftTestNames(result.files, { cwd, importLine: detectTestImport(cwd) });

      if (draft.drafts.length === 0) {
        process.stderr.write(`${colors.yellow('!')} No comments left to draft into ${shown}.\n`);
      } else {
        mkdirSync(path.dirname(testNamesFile), { recursive: true });
        writeFileSync(testNamesFile, draft.source, 'utf8');
        const skipped =
          draft.skipped > 0
            ? colors.dim(
                ` (${draft.skipped} comment${draft.skipped === 1 ? '' : 's'} skipped: ` +
                  'commented-out code, banners, and the like)'
              )
            : '';
        process.stderr.write(
          `${colors.green('✔')} Drafted ${draft.drafts.length} test name${
            draft.drafts.length === 1 ? '' : 's'
          } from ${draft.files} file${draft.files === 1 ? '' : 's'} into ` +
            `${colors.bold(shown)}${skipped}\n` +
            colors.dim(
              `  Next: hand ${shown} to your coding agent and have it fill in every it.todo\n` +
                '  against the source file named in its describe block. Prompt to paste:\n' +
                `  ${AGENT_PROMPT_URL}\n`
            )
        );
      }
    }

    return result.exitCode;
  } catch (error) {
    if (
      error instanceof UsageError ||
      error instanceof ConfigError ||
      error instanceof UnknownKeepRuleError
    ) {
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
