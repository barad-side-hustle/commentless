import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import type { Comment, FileResult } from '../types.js';

const LABEL =
  /^(?:TODO|FIXME|NOTE|HACK|XXX|WARNING|WARN|BUG|REVIEW|OPTIMIZE|DEPRECATED)\b\s*[:\-–—]?\s*|^(?:Todo|Note|Fixme|Hack|Warning|Bug)\s*:\s*/;

const SENTENCE = /(?<=[\p{L}\p{N}]{3}[.!?])\s+(?=\p{Lu})/u;

const CODE_PATTERNS: readonly RegExp[] = [
  /^(?:const|let|var)\s+[\w${[]/,
  /^(?:function|class|interface|enum|namespace|declare|module)\s+[\w$*]/,
  /^(?:import|export)\s+[\w${*]/,
  /^(?:if|for|while|switch|catch)\s*\(/,
  /^(?:public|private|protected|static|readonly)\s+[\w$]/,
  /^[\w$][\w$.?![\]]*\([^)]*\)[;.]?$/,
  /^[\w$][\w$.[\]]*\s*[-+*/%|&^]?=[^=>]/,
  /^\}\s*(?:else|catch|finally|\)|$)/,
  /^[)\]];?$/,
  /^<\/?[A-Za-z]/,
  /^https?:\/\/\S+$/,
  /^@\w+/,
  /=>/,
  /[;{]$/,
];

export interface TestNameDraft {
  file: string;
  line: number;
  name: string;
}

export interface DraftOptions {
  cwd: string;
  importLine?: string | null;
}

export interface DraftResult {
  source: string;
  drafts: TestNameDraft[];
  files: number;
  skipped: number;
}

function isProse(comment: Comment): boolean {
  const body = bodyOf(comment.text);
  return /\p{L}/u.test(body) && !looksLikeCode(body);
}

export function groupComments(comments: readonly Comment[]): Comment[][] {
  const groups: Comment[][] = [];
  for (const comment of comments) {
    const current = groups[groups.length - 1];
    const previous = current?.[current.length - 1];
    const continues =
      previous !== undefined &&
      previous.kind === 'line' &&
      comment.kind === 'line' &&
      comment.line === previous.line + 1 &&
      comment.column === previous.column &&
      isProse(previous) &&
      isProse(comment);
    if (continues && current) current.push(comment);
    else groups.push([comment]);
  }
  return groups;
}

function bodyOf(text: string): string {
  let body = text.trim();
  if (body.startsWith('{') && body.endsWith('}')) body = body.slice(1, -1).trim();

  if (body.startsWith('/*')) {
    return body
      .slice(2)
      .replace(/\*+\/$/, '')
      .split('\n')
      .map(line => line.replace(/^\s*\*+\s?/, '').trim())
      .filter(line => !line.startsWith('@'))
      .join(' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  return body.replace(/^\/+/, '').replace(/\s+/g, ' ').trim();
}

export function looksLikeCode(text: string): boolean {
  return CODE_PATTERNS.some(pattern => pattern.test(text));
}

function tidy(sentence: string): string | null {
  const labelled = sentence.replace(LABEL, '').trim();
  if (looksLikeCode(labelled)) return null;

  const text = labelled
    .replace(/^[^\p{L}\p{N}]+/u, '')
    .replace(/[^\p{L}\p{N}?!)\]'"]+$/u, '')
    .trim();
  if (!/\p{L}/u.test(text) || looksLikeCode(text)) return null;

  const space = text.indexOf(' ');
  const first = space === -1 ? text : text.slice(0, space);
  return /^\p{Lu}[\p{Ll}']*$/u.test(first) ? first.toLowerCase() + text.slice(first.length) : text;
}

export function toTestNames(...texts: readonly string[]): string[] {
  const body = texts
    .map(bodyOf)
    .filter(Boolean)
    .join(' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(LABEL, '')
    .trim();

  if (!/\p{L}/u.test(body)) return [];

  return body.split(SENTENCE).flatMap(sentence => {
    const name = tidy(sentence);
    return name ? [name] : [];
  });
}

function escape(value: string): string {
  return value.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}

function relative(cwd: string, file: string): string {
  return path.relative(cwd, file).split(path.sep).join('/') || file;
}

const PRINT_WIDTH = 100;

function stub(name: string): string {
  const single = `  it.todo('${escape(name)}');`;
  return single.length <= PRINT_WIDTH ? single : `  it.todo(\n    '${escape(name)}'\n  );`;
}

export function renderTestFile(
  groups: readonly { file: string; names: readonly string[] }[],
  importLine?: string | null
): string {
  const blocks = groups.map(group => {
    const body = group.names.map(stub).join('\n');
    return `describe('${escape(group.file)}', () => {\n${body}\n});`;
  });
  return `${importLine ? `${importLine}\n\n` : ''}${blocks.join('\n\n')}\n`;
}

export function detectTestImport(cwd: string): string | null {
  const packageFile = path.join(cwd, 'package.json');
  if (!existsSync(packageFile)) return null;

  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(readFileSync(packageFile, 'utf8')) as Record<string, unknown>;
  } catch {
    return null;
  }

  const deps = {
    ...((parsed.dependencies as Record<string, string>) ?? {}),
    ...((parsed.devDependencies as Record<string, string>) ?? {}),
  };

  if (Object.hasOwn(deps, 'vitest')) return "import { describe, it } from 'vitest';";
  if (Object.hasOwn(deps, '@jest/globals')) return "import { describe, it } from '@jest/globals';";
  if (Object.hasOwn(deps, 'jest')) return null;
  if (Object.hasOwn(deps, '@types/bun') || Object.hasOwn(deps, 'bun-types')) {
    return "import { describe, it } from 'bun:test';";
  }
  return null;
}

export function draftTestNames(files: readonly FileResult[], options: DraftOptions): DraftResult {
  const groups: { file: string; names: string[] }[] = [];
  const drafts: TestNameDraft[] = [];
  let skipped = 0;

  for (const result of files) {
    if (result.error) continue;

    const name = relative(options.cwd, result.file);
    const seen = new Set<string>();
    const names: string[] = [];

    for (const group of groupComments(result.removable)) {
      const drafted = toTestNames(...group.map(comment => comment.text));
      if (drafted.length === 0) {
        skipped += 1;
        continue;
      }
      for (const entry of drafted) {
        if (seen.has(entry)) continue;
        seen.add(entry);
        names.push(entry);
        drafts.push({ file: name, line: group[0]?.line ?? 1, name: entry });
      }
    }

    if (names.length > 0) groups.push({ file: name, names });
  }

  return {
    source: groups.length > 0 ? renderTestFile(groups, options.importLine) : '',
    drafts,
    files: groups.length,
    skipped,
  };
}
