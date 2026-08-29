import { describe, expect, it } from 'vitest';
import { resolveKeepRules } from '../src/core/keep.js';
import { scan, strip } from './helpers.js';

function keptBy(source: string, fileName = 'input.ts'): string[] {
  return scan(source, fileName).kept.map(comment => comment.keptBy ?? '');
}

describe('load-bearing comments survive', () => {
  const cases: Array<[string, string]> = [
    ['eslint', '// eslint-disable-next-line @typescript-eslint/no-explicit-any'],
    ['eslint', '/* eslint-disable no-console */'],
    ['eslint', '// eslint-enable no-console'],
    ['eslint', '/* eslint-env browser */'],
    ['eslint-globals', '/* global describe, it */'],
    ['typescript', '// @ts-expect-error stale types'],
    ['typescript', '// @ts-ignore'],
    ['typescript', '// @ts-nocheck'],
    ['triple-slash', '/// <reference types="node" />'],
    ['biome', '// biome-ignore lint/style/noVar: legacy'],
    ['prettier', '// prettier-ignore'],
    ['oxlint', '// oxlint-disable-next-line no-debugger'],
    ['coverage', '/* istanbul ignore next */'],
    ['coverage', '/* c8 ignore start */'],
    ['coverage', '/* v8 ignore next */'],
    ['bundler-magic', '/* webpackChunkName: "admin" */'],
    ['bundler-magic', '/* @vite-ignore */'],
    ['pure-annotation', '/* @__PURE__ */'],
    ['jsx-pragma', '/** @jsxImportSource @emotion/react */'],
    ['test-environment', `// @vitest-${'environment'} jsdom`],
    ['license', '/** @license MIT */'],
    ['license', '// SPDX-License-Identifier: MIT'],
    ['bang', '/*! keep me */'],
    ['commentless', '// commentless-keep deliberate note'],
  ];

  it.each(cases)('keeps %s comments', (rule, comment) => {
    const source = `${comment}\nconst a = 1;\n`;
    expect(strip(source)).toBe(source);
    expect(keptBy(source)).toEqual([rule]);
  });
});

describe('jsdoc type directives', () => {
  const comment = '/** @type {number} */';

  it('are load-bearing in JavaScript', () => {
    const source = `${comment}\nconst a = 1;\n`;
    expect(strip(source, 'a.js')).toBe(source);
    expect(keptBy(source, 'a.js')).toEqual(['jsdoc-type']);
  });

  it('are just prose in TypeScript', () => {
    expect(strip(`${comment}\nconst a = 1;\n`, 'a.ts')).toBe('const a = 1;\n');
  });
});

describe('inline escapes', () => {
  it('keeps the comment that follows keep-next-line', () => {
    const source = '// commentless-keep-next-line\n// a deliberate note\nconst a = 1;\n';
    expect(strip(source)).toBe(source);
  });

  it('skips the whole file on commentless-ignore-file', () => {
    const source = '// commentless-ignore-file\n// everything here stays\nconst a = 1;\n';
    const result = scan(source);
    expect(result.ignoredFile).toBe(true);
    expect(strip(source)).toBe(source);
  });

  it('does not keep an ordinary comment two lines after keep-next-line', () => {
    const source = '// commentless-keep-next-line\n// kept\nconst a = 1;\n// gone\n';
    expect(strip(source)).toBe('// commentless-keep-next-line\n// kept\nconst a = 1;\n');
  });
});

describe('user patterns', () => {
  const keep = resolveKeepRules({ userPatterns: ['https?://', '@(public|internal)\\b'] });

  it('keeps comments matching a configured pattern', () => {
    const source = '// see https://example.com/docs\nconst a = 1;\n';
    expect(strip(source, 'input.ts', {}, keep)).toBe(source);
  });

  it('keeps knip-style tool tags', () => {
    const source = '/** @public */\nexport const a = 1;\n';
    expect(strip(source, 'input.ts', {}, keep)).toBe(source);
  });

  it('still removes everything else', () => {
    expect(strip('// plain note\nconst a = 1;\n', 'input.ts', {}, keep)).toBe('const a = 1;\n');
  });
});

describe('--no-default-keep', () => {
  it('removes directives when the allowlist is disabled', () => {
    const bare = resolveKeepRules({ defaults: false });
    const source = '// eslint-disable-next-line no-console\nconsole.log(1);\n';
    expect(strip(source, 'input.ts', {}, bare)).toBe('console.log(1);\n');
  });
});

describe('shebang', () => {
  it('is never treated as a comment', () => {
    const source = '#!/usr/bin/env node\n// gone\nconst a = 1;\n';
    expect(strip(source, 'bin.js')).toBe('#!/usr/bin/env node\nconst a = 1;\n');
  });
});
