import { execFile } from 'node:child_process';
import { existsSync, readFileSync, realpathSync } from 'node:fs';
import path from 'node:path';
import { promisify } from 'node:util';
import ignore, { type Ignore } from 'ignore';
import { glob } from 'tinyglobby';

const run = promisify(execFile);

export type DiscoveryMode = 'all' | 'staged' | 'changed';

export interface DiscoverOptions {
  cwd: string;
  paths: readonly string[];
  extensions: readonly string[];
  ignore: readonly string[];
  ignoreFile: string | false;
  gitignore: boolean;
  mode: DiscoveryMode;
  base?: string | undefined;
}

const ALWAYS_IGNORED = ['.git/**', 'node_modules/**'];

async function git(cwd: string, args: readonly string[]): Promise<string | null> {
  try {
    const { stdout } = await run('git', [...args], { cwd, maxBuffer: 128 * 1024 * 1024 });
    return stdout;
  } catch {
    return null;
  }
}

export class DiscoveryError extends Error {}

function realPath(target: string): string {
  try {
    return realpathSync(target);
  } catch {
    return path.resolve(target);
  }
}

export async function gitRoot(cwd: string): Promise<string | null> {
  const stdout = await git(cwd, ['rev-parse', '--show-toplevel']);
  const root = stdout?.trim();
  return root ? realPath(root) : null;
}

async function resolveBase(cwd: string, base: string | undefined): Promise<string | null> {
  const candidates = base
    ? [base]
    : ['origin/HEAD', 'origin/main', 'origin/master', 'main', 'master'];
  for (const candidate of candidates) {
    const resolved = await git(cwd, ['rev-parse', '--verify', '--quiet', `${candidate}^{commit}`]);
    if (resolved?.trim()) {
      const mergeBase = await git(cwd, ['merge-base', candidate, 'HEAD']);
      return mergeBase?.trim() || resolved.trim();
    }
  }
  return null;
}

function splitNulls(stdout: string): string[] {
  return stdout.split('\0').filter(Boolean);
}

async function listFromGit(options: DiscoverOptions, cwd: string | null): Promise<string[] | null> {
  const { mode, base } = options;

  if (cwd === null) {
    if (mode === 'all') return null;
    throw new DiscoveryError(
      `--${mode} needs a git repository, but ${options.cwd} is not inside one`
    );
  }

  if (mode === 'staged') {
    const stdout = await git(cwd, ['diff', '--cached', '--name-only', '--diff-filter=ACMR', '-z']);
    return stdout === null ? null : splitNulls(stdout);
  }

  if (mode === 'changed') {
    const mergeBase = await resolveBase(cwd, base);
    if (!mergeBase) {
      throw new DiscoveryError(
        base
          ? `--base ${base} does not resolve to a commit`
          : 'could not resolve a base ref for --changed; pass --base <ref>'
      );
    }
    const stdout = await git(cwd, ['diff', '--name-only', '--diff-filter=ACMR', '-z', mergeBase]);
    if (stdout === null) return null;
    const untracked = await git(cwd, ['ls-files', '--others', '--exclude-standard', '-z']);
    return [...splitNulls(stdout), ...(untracked ? splitNulls(untracked) : [])];
  }

  if (!options.gitignore) return null;
  const stdout = await git(cwd, ['ls-files', '--cached', '--others', '--exclude-standard', '-z']);
  return stdout === null ? null : splitNulls(stdout);
}

async function listFromGlob(options: DiscoverOptions, cwd: string): Promise<string[]> {
  const patterns = options.extensions.map(extension => `**/*.${extension}`);
  return glob(patterns, { cwd, dot: true, absolute: true, ignore: ALWAYS_IGNORED });
}

export function buildIgnoreFilter(options: DiscoverOptions): Ignore {
  const matcher = ignore().add(ALWAYS_IGNORED.map(pattern => pattern.replace(/\/\*\*$/, '')));
  if (options.ignoreFile) {
    const filePath = path.resolve(realPath(options.cwd), options.ignoreFile);
    if (existsSync(filePath)) matcher.add(readFileSync(filePath, 'utf8'));
  }
  if (options.ignore.length > 0) matcher.add([...options.ignore]);
  return matcher;
}

function matchesRequestedPaths(absolute: string, roots: readonly string[]): boolean {
  if (roots.length === 0) return true;
  return roots.some(root => absolute === root || absolute.startsWith(`${root}${path.sep}`));
}

export async function discoverFiles(options: DiscoverOptions): Promise<string[]> {
  const extensions = new Set(options.extensions.map(extension => `.${extension.toLowerCase()}`));
  const cwd = realPath(options.cwd);
  const root = await gitRoot(cwd);

  const fromGit = await listFromGit(options, root);
  const candidates = fromGit
    ? fromGit.map(entry => path.resolve(root as string, entry))
    : (await listFromGlob(options, cwd)).map(entry => path.resolve(cwd, entry));

  const roots = options.paths
    .filter(entry => entry !== '.' && entry !== './')
    .map(entry => path.resolve(cwd, entry));

  const matcher = buildIgnoreFilter(options);
  const seen = new Set<string>();
  const result: string[] = [];

  for (const absolute of candidates) {
    if (!extensions.has(path.extname(absolute).toLowerCase())) continue;

    const relative = path.relative(cwd, absolute).split(path.sep).join('/');
    if (relative === '' || relative.startsWith('../')) continue;
    if (matcher.ignores(relative)) continue;
    if (!matchesRequestedPaths(absolute, roots)) continue;
    if (seen.has(absolute)) continue;
    if (!existsSync(absolute)) continue;

    seen.add(absolute);
    result.push(path.resolve(options.cwd, relative));
  }

  return result.sort();
}
