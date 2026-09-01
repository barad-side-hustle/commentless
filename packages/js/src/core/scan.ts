import ts from 'typescript';
import type { Comment, ScanOptions, ScanResult } from '../types.js';
import { applyKeepNextLine, hasIgnoreFileMarker, matchKeepRule } from './keep.js';

export const DEFAULT_EXTENSIONS = ['ts', 'tsx', 'mts', 'cts', 'js', 'jsx', 'mjs', 'cjs'] as const;

const SCRIPT_KINDS: Record<string, ts.ScriptKind> = {
  '.ts': ts.ScriptKind.TS,
  '.mts': ts.ScriptKind.TS,
  '.cts': ts.ScriptKind.TS,
  '.tsx': ts.ScriptKind.TSX,
  '.js': ts.ScriptKind.JS,
  '.mjs': ts.ScriptKind.JS,
  '.cjs': ts.ScriptKind.JS,
  '.jsx': ts.ScriptKind.JSX,
};

export function scriptKindFor(fileName: string): ts.ScriptKind {
  const dot = fileName.lastIndexOf('.');
  const extension = dot === -1 ? '' : fileName.slice(dot).toLowerCase();
  return SCRIPT_KINDS[extension] ?? ts.ScriptKind.TS;
}

export function mayContainComments(source: string): boolean {
  return source.includes('//') || source.includes('/*');
}

interface Span {
  start: number;
  end: number;
}

function withinAnySpan(position: number, spans: readonly Span[]): boolean {
  let low = 0;
  let high = spans.length - 1;
  while (low <= high) {
    const mid = (low + high) >> 1;
    const span = spans[mid];
    if (!span) break;
    if (position < span.start) high = mid - 1;
    else if (position >= span.end) low = mid + 1;
    else return true;
  }
  return false;
}

export function scanSource(source: string, options: ScanOptions = {}): ScanResult {
  const fileName = options.fileName ?? 'input.ts';
  const empty: ScanResult = { removable: [], kept: [], ignoredFile: false };

  if (!mayContainComments(source)) return empty;
  if (hasIgnoreFileMarker(source)) return { ...empty, ignoredFile: true };

  const sourceFile = ts.createSourceFile(
    fileName,
    source,
    ts.ScriptTarget.Latest,
    false,
    scriptKindFor(fileName)
  );

  const found = new Map<number, Comment>();
  const jsxTextSpans: Span[] = [];
  const shebangLength = ts.getShebang(source)?.length ?? 0;

  const record = (start: number, end: number, kind: Comment['kind']) => {
    if (start < shebangLength) return;
    const existing = found.get(start);
    if (existing && existing.end >= end) return;
    const { line, character } = ts.getLineAndCharacterOfPosition(sourceFile, start);
    found.set(start, {
      start,
      end,
      line: line + 1,
      column: character + 1,
      kind,
      text: source.slice(start, end),
    });
  };

  const collectTrivia = (ranges: readonly ts.CommentRange[] | undefined) => {
    if (!ranges) return;
    for (const range of ranges) {
      record(
        range.pos,
        range.end,
        range.kind === ts.SyntaxKind.SingleLineCommentTrivia ? 'line' : 'block'
      );
    }
  };

  const visit = (node: ts.Node): void => {
    if (node.kind === ts.SyntaxKind.JsxText) {
      jsxTextSpans.push({ start: node.pos, end: node.end });
    } else {
      collectTrivia(ts.getLeadingCommentRanges(source, node.pos));
      collectTrivia(ts.getTrailingCommentRanges(source, node.end));
    }

    if (ts.isJsxExpression(node) && node.expression === undefined) {
      const start = source.indexOf('{', node.pos);
      if (start !== -1 && start < node.end) {
        const inner = source.slice(start, node.end);
        if (/^\{\s*\/[/*]/.test(inner)) record(start, node.end, 'jsx');
      }
    }

    ts.forEachChild(node, visit);
  };

  visit(sourceFile);
  collectTrivia(ts.getLeadingCommentRanges(source, sourceFile.endOfFileToken.pos));

  jsxTextSpans.sort((a, b) => a.start - b.start);

  const comments = [...found.values()]
    .filter(comment => comment.kind === 'jsx' || !withinAnySpan(comment.start, jsxTextSpans))
    .sort((a, b) => a.start - b.start);

  const forcedKeep = applyKeepNextLine(comments);
  const removable: Comment[] = [];
  const kept: Comment[] = [];

  for (const comment of comments) {
    const keptBy = forcedKeep.has(comment.start)
      ? 'commentless-keep-next-line'
      : matchKeepRule(comment.text, options.keep ?? [], fileName);
    if (keptBy) kept.push({ ...comment, keptBy });
    else removable.push(comment);
  }

  return { removable, kept, ignoredFile: false };
}
