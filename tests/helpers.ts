import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { resolveKeepRules } from '../src/core/keep.js';
import { scanSource } from '../src/core/scan.js';
import { stripComments } from '../src/core/strip.js';
import type { StripOptions } from '../src/types.js';

export const defaultKeep = resolveKeepRules({});

export function strip(
  source: string,
  fileName = 'input.ts',
  options: StripOptions = {},
  keep = defaultKeep
): string {
  const result = scanSource(source, { fileName, keep });
  return result.ignoredFile ? source : stripComments(source, result.removable, options);
}

export function scan(source: string, fileName = 'input.ts', keep = defaultKeep) {
  return scanSource(source, { fileName, keep });
}

export interface Sandbox {
  dir: string;
  write(relative: string, content: string): string;
  cleanup(): void;
}

export function sandbox(): Sandbox {
  const dir = mkdtempSync(path.join(tmpdir(), 'commentless-'));
  return {
    dir,
    write(relative, content) {
      const file = path.join(dir, relative);
      mkdirSync(path.dirname(file), { recursive: true });
      writeFileSync(file, content, 'utf8');
      return file;
    },
    cleanup() {
      rmSync(dir, { recursive: true, force: true });
    },
  };
}
