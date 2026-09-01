import type { Comment, StripOptions } from '../types.js';

interface Range {
  start: number;
  end: number;
}

function mergeRanges(ranges: readonly Range[]): Range[] {
  const sorted = [...ranges].sort((a, b) => a.start - b.start || a.end - b.end);
  const merged: Range[] = [];
  for (const range of sorted) {
    const last = merged[merged.length - 1];
    if (last && range.start <= last.end) {
      if (range.end > last.end) last.end = range.end;
      continue;
    }
    merged.push({ ...range });
  }
  return merged;
}

function isHorizontalWhitespace(char: string | undefined): boolean {
  return char === ' ' || char === '\t';
}

const BYTE_ORDER_MARK = '\uFEFF';

function expand(source: string, range: Range): Range {
  let start = range.start;
  while (start > 0 && isHorizontalWhitespace(source[start - 1])) start -= 1;
  const consumedLeading = start < range.start;

  const atLineStart =
    start === 0 || source[start - 1] === '\n' || (start === 1 && source[0] === BYTE_ORDER_MARK);

  let cursor = range.end;
  while (isHorizontalWhitespace(source[cursor])) cursor += 1;
  const atLineEnd = cursor >= source.length || source[cursor] === '\n' || source[cursor] === '\r';

  if (!atLineStart) {
    return consumedLeading ? { start, end: range.end } : { start, end: cursor };
  }

  if (!atLineEnd) return { start: range.start, end: cursor };

  let end = cursor;
  if (source[end] === '\r') end += 1;
  if (source[end] === '\n') end += 1;
  return { start, end };
}

export function stripComments(
  source: string,
  comments: readonly Comment[],
  options: StripOptions = {}
): string {
  if (comments.length === 0) {
    return options.collapseBlankLines ? collapseBlankLines(source) : source;
  }

  const ranges = mergeRanges(comments.map(comment => expand(source, comment)));

  let out = '';
  let cursor = 0;
  for (const range of ranges) {
    if (range.start < cursor) continue;
    out += source.slice(cursor, range.start);
    cursor = range.end;
  }
  out += source.slice(cursor);

  return options.collapseBlankLines ? collapseBlankLines(out) : out;
}

export function collapseBlankLines(source: string): string {
  return source.replace(/[ \t]+(\r?\n)/g, '$1').replace(/(\r?\n){3,}/g, '$1$1');
}
