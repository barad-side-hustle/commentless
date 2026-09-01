import path from 'node:path';
import { createColors } from 'picocolors';
import type { Comment, RunResult } from '../types.js';

export type ReporterName = 'pretty' | 'json' | 'github' | 'summary';

export const REPORTERS: readonly ReporterName[] = ['pretty', 'json', 'github', 'summary'];

export interface ReportContext {
  cwd: string;
  quiet: boolean;
  verbose: boolean;
  color: boolean;
}

function relative(cwd: string, file: string): string {
  return path.relative(cwd, file).split(path.sep).join('/') || file;
}

function preview(comment: Comment): string {
  const flat = comment.text.replace(/\s+/g, ' ').trim();
  return flat.length > 72 ? `${flat.slice(0, 69)}...` : flat;
}

function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? '' : 's'}`;
}

function summaryLine(result: RunResult): string {
  const { summary } = result;
  const scope = `${plural(summary.discovered, 'file')} scanned`;
  const cached = summary.cached > 0 ? `, ${summary.cached} cached` : '';
  const kept = summary.commentsKept > 0 ? `, ${summary.commentsKept} kept` : '';
  const verb = summary.mode === 'write' ? 'removed' : 'to remove';
  const errors = summary.errors > 0 ? `, ${plural(summary.errors, 'error')}` : '';
  return `${scope}${cached} · ${plural(summary.commentsRemoved, 'comment')} ${verb} in ${plural(
    summary.filesWithComments,
    'file'
  )}${kept}${errors} · ${summary.durationMs}ms`;
}

function pretty(result: RunResult, context: ReportContext): string {
  const pc = createColors(context.color);
  const lines: string[] = [];

  for (const file of result.files) {
    const name = relative(context.cwd, file.file);
    if (file.error) {
      lines.push(`${pc.red('✗')} ${name} ${pc.dim(file.error)}`);
      continue;
    }
    const verb = result.summary.mode === 'write' ? 'removed' : 'found';
    lines.push(
      `${pc.yellow('•')} ${pc.bold(name)} ${pc.dim(`(${plural(file.removable.length, 'comment')} ${verb})`)}`
    );
    if (context.quiet) continue;
    for (const comment of file.removable) {
      lines.push(`  ${pc.dim(`${name}:${comment.line}:${comment.column}`)}  ${preview(comment)}`);
    }
  }

  if (lines.length > 0) lines.push('');

  const line = summaryLine(result);
  lines.push(result.exitCode === 0 ? `${pc.green('✔')} ${line}` : `${pc.red('✖')} ${line}`);

  if (result.exitCode !== 0 && result.summary.mode === 'check') {
    lines.push(
      pc.dim('  Run `commentless --write` to remove them, or keep one with `commentless-keep`.')
    );
  }

  return lines.join('\n');
}

function escapeProperty(value: string): string {
  return value.replace(/%/g, '%25').replace(/\r/g, '%0D').replace(/\n/g, '%0A');
}

function escapeData(value: string): string {
  return value
    .replace(/%/g, '%25')
    .replace(/\r/g, '%0D')
    .replace(/\n/g, '%0A')
    .replace(/:/g, '%3A');
}

function github(result: RunResult, context: ReportContext): string {
  const lines: string[] = [];

  for (const file of result.files) {
    const name = escapeProperty(relative(context.cwd, file.file));
    if (file.error) {
      lines.push(`::error file=${name}::${escapeData(file.error)}`);
      continue;
    }
    for (const comment of file.removable) {
      lines.push(
        `::error file=${name},line=${comment.line},col=${comment.column},title=commentless::${escapeData(
          `Remove this comment: ${preview(comment)}`
        )}`
      );
    }
  }

  lines.push(`::notice title=commentless::${escapeData(summaryLine(result))}`);
  return lines.join('\n');
}

function json(result: RunResult, context: ReportContext): string {
  return JSON.stringify(
    {
      version: 1,
      summary: result.summary,
      exitCode: result.exitCode,
      files: result.files.map(file => ({
        file: relative(context.cwd, file.file),
        changed: file.changed,
        keptCount: file.keptCount,
        ...(file.error ? { error: file.error } : {}),
        comments: file.removable.map(comment => ({
          line: comment.line,
          column: comment.column,
          kind: comment.kind,
          text: comment.text,
        })),
      })),
    },
    null,
    2
  );
}

export function report(reporter: ReporterName, result: RunResult, context: ReportContext): string {
  switch (reporter) {
    case 'json':
      return json(result, context);
    case 'github':
      return github(result, context);
    case 'summary':
      return summaryLine(result);
    default:
      return pretty(result, context);
  }
}
