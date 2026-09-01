import { readFileSync, writeFileSync } from 'node:fs';
import type { FileResult, KeepRule } from '../types.js';
import { mayContainComments, scanSource } from './scan.js';
import { stripComments } from './strip.js';

export interface ProcessOptions {
  keep: readonly KeepRule[];
  collapseBlankLines: boolean;
  write: boolean;
}

export function processFile(file: string, options: ProcessOptions): FileResult {
  const clean: FileResult = { file, removable: [], keptCount: 0, changed: false };

  let source: string;
  try {
    source = readFileSync(file, 'utf8');
  } catch (error) {
    return { ...clean, error: error instanceof Error ? error.message : String(error) };
  }

  if (!mayContainComments(source)) return clean;

  let result;
  try {
    result = scanSource(source, { fileName: file, keep: options.keep });
  } catch (error) {
    return { ...clean, error: error instanceof Error ? error.message : String(error) };
  }

  if (result.ignoredFile) return clean;

  const output = stripComments(source, result.removable, {
    collapseBlankLines: options.collapseBlankLines,
  });
  const changed = output !== source;

  if (changed && options.write) {
    try {
      writeFileSync(file, output, 'utf8');
    } catch (error) {
      return {
        ...clean,
        removable: result.removable,
        keptCount: result.kept.length,
        error: error instanceof Error ? error.message : String(error),
      };
    }
  }

  return {
    file,
    removable: result.removable,
    keptCount: result.kept.length,
    changed,
  };
}
