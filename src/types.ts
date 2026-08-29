export type CommentKind = 'line' | 'block' | 'jsx';

export interface Comment {
  start: number;
  end: number;
  line: number;
  column: number;
  kind: CommentKind;
  text: string;
  keptBy?: string;
}

export interface KeepRule {
  name: string;
  test: RegExp;
  extensions?: readonly string[];
}

export interface SerializedKeepRule {
  name: string;
  source: string;
  flags: string;
  extensions?: readonly string[];
}

export interface StripOptions {
  collapseBlankLines?: boolean;
}

export interface ScanOptions {
  fileName?: string;
  keep?: readonly KeepRule[];
}

export interface ScanResult {
  removable: Comment[];
  kept: Comment[];
  ignoredFile: boolean;
}

export interface FileResult {
  file: string;
  removable: Comment[];
  keptCount: number;
  changed: boolean;
  error?: string;
}

export type RunMode = 'write' | 'check' | 'dry-run';

export interface RunSummary {
  mode: RunMode;
  discovered: number;
  parsed: number;
  cached: number;
  filesWithComments: number;
  commentsRemoved: number;
  commentsKept: number;
  errors: number;
  durationMs: number;
}

export interface RunResult {
  summary: RunSummary;
  files: FileResult[];
  exitCode: number;
}
