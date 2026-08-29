import { existsSync, readFileSync } from 'node:fs';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { main } from '../src/cli.js';
import {
  detectTestImport,
  draftTestNames,
  groupComments,
  looksLikeCode,
  renderTestFile,
  toTestNames,
} from '../src/core/testnames.js';
import type { FileResult } from '../src/types.js';
import { sandbox, scan, type Sandbox } from './helpers.js';

interface Capture {
  stdout: string;
  stderr: string;
}

async function cli(args: string[], cwd: string): Promise<{ code: number } & Capture> {
  const capture: Capture = { stdout: '', stderr: '' };
  const originalCwd = process.cwd();
  const stdout = vi.spyOn(process.stdout, 'write').mockImplementation(chunk => {
    capture.stdout += String(chunk);
    return true;
  });
  const stderr = vi.spyOn(process.stderr, 'write').mockImplementation(chunk => {
    capture.stderr += String(chunk);
    return true;
  });
  process.chdir(cwd);
  try {
    const code = await main(args);
    return { code, ...capture };
  } finally {
    process.chdir(originalCwd);
    stdout.mockRestore();
    stderr.mockRestore();
  }
}

function resultFor(source: string, file = '/repo/src/a.ts'): FileResult {
  const scanned = scan(source, file);
  return {
    file,
    removable: scanned.removable,
    keptCount: scanned.kept.length,
    changed: scanned.removable.length > 0,
  };
}

describe('toTestNames', () => {
  const prose: [string, string][] = [
    ['// Returns null for a never-subscribed user.', 'returns null for a never-subscribed user'],
    ['//no space after the slashes', 'no space after the slashes'],
    ['/* the billing API answers 200 */', 'the billing API answers 200'],
    ['/** Retries twice before giving up. */', 'retries twice before giving up'],
    ['{/* renders nothing while loading */}', 'renders nothing while loading'],
    ['// TODO: handle the empty cart', 'handle the empty cart'],
    ['// FIXME \u2014 the retry budget is wrong', 'the retry budget is wrong'],
    ['// NOTE this only matters on Safari', 'this only matters on Safari'],
    ['// Note: this only matters on Safari', 'this only matters on Safari'],
    ['// ---- the cache is warmed lazily ----', 'the cache is warmed lazily'],
    ['// Is the token expired?', 'is the token expired?'],
    ['// API returns 204 now', 'API returns 204 now'],
  ];

  it.each(prose)('turns %j into one test name', (comment, expected) => {
    expect(toTestNames(comment)).toEqual([expected]);
  });

  it('joins a multi-line block comment into one sentence', () => {
    expect(toTestNames('/**\n * The billing API answers 200\n * with an empty body.\n */')).toEqual(
      ['the billing API answers 200 with an empty body']
    );
  });

  it('drops jsdoc tag lines and keeps the description', () => {
    expect(
      toTestNames('/**\n * Parses the header.\n * @param raw the header\n * @returns a map\n */')
    ).toEqual(['parses the header']);
  });

  it('gives every sentence in a block its own stub', () => {
    expect(toTestNames('// Retry once. Stripe rate-limits at 100rps.')).toEqual([
      'retry once',
      'stripe rate-limits at 100rps',
    ]);
  });

  it('drops a trailing sentence that is really commented-out code', () => {
    expect(toTestNames('// Warm the cache lazily. Legacy();')).toEqual(['warm the cache lazily']);
  });

  it('does not split on an abbreviation too short to end a sentence', () => {
    expect(toTestNames('// Only e.g. Safari needs this')).toEqual(['only e.g. Safari needs this']);
  });

  it('does not split a version number', () => {
    expect(toTestNames('// Node 20.1 dropped it')).toEqual(['node 20.1 dropped it']);
  });

  it('lowercases a leading capitalised word, proper noun or not', () => {
    expect(toTestNames('// Stripe rate-limits us')).toEqual(['stripe rate-limits us']);
    expect(toTestNames('// GitHub rate-limits us')).toEqual(['GitHub rate-limits us']);
    expect(toTestNames('// IDs are opaque')).toEqual(['IDs are opaque']);
    expect(toTestNames('// The ID is opaque')).toEqual(['the ID is opaque']);
  });

  it('keeps question and exclamation marks but drops trailing punctuation', () => {
    expect(toTestNames('// why?')).toEqual(['why?']);
    expect(toTestNames('// never!')).toEqual(['never!']);
    expect(toTestNames('// really...')).toEqual(['really']);
  });
});

describe('toTestNames returns nothing', () => {
  const skipped = [
    '//',
    '// ----------------',
    '/* ***** */',
    '// const previous = cache.get(key);',
    '// return null;',
    '// if (!body) {',
    '// }',
    '// });',
    '// export function old() {',
    '// import { old } from "./old.js";',
    '// items.map(item => item.id)',
    '// doTheThing();',
    '// total = total + 1',
    '// <LegacyButton />',
    '// https://example.com/spec#section-4',
    '/** @deprecated */',
  ];

  it.each(skipped)('for %j, which is not prose', comment => {
    expect(toTestNames(comment)).toEqual([]);
  });

  it('does not mistake prose that merely starts with a keyword for code', () => {
    expect(toTestNames('// if the user has no plan we fall back to the free tier')).toEqual([
      'if the user has no plan we fall back to the free tier',
    ]);
    expect(toTestNames('// return null when the cart is empty')).toEqual([
      'return null when the cart is empty',
    ]);
  });

  it('does not mistake a parenthetical for a call', () => {
    expect(toTestNames('// note (see the spec) that ids are opaque')).toEqual([
      'note (see the spec) that ids are opaque',
    ]);
  });
});

describe('looksLikeCode', () => {
  it('recognises an arrow function anywhere in the line', () => {
    expect(looksLikeCode('onClick={() => close()}')).toBe(true);
  });

  it('leaves ordinary prose alone', () => {
    expect(looksLikeCode('the retry budget resets every minute')).toBe(false);
  });
});

describe('groupComments', () => {
  it('merges a run of line comments at the same indent into one stub', () => {
    const result = resultFor('// the billing API\n// answers 200\nexport const a = 1;\n');
    expect(groupComments(result.removable)).toHaveLength(1);
    expect(toTestNames(...result.removable.map(comment => comment.text))).toEqual([
      'the billing API answers 200',
    ]);
  });

  it('does not merge across a blank line', () => {
    const result = resultFor('// one\n\n// two\nexport const a = 1;\n');
    expect(groupComments(result.removable)).toHaveLength(2);
  });

  it('does not merge comments at different indents', () => {
    const result = resultFor('function f() {\n// one\n  // two\n  return 1;\n}\n');
    expect(groupComments(result.removable)).toHaveLength(2);
  });

  it('splits a prose line from the commented-out code directly under it', () => {
    const result = resultFor(
      '// keep the old path around\n// return legacy(input);\nexport const a = 1;\n'
    );
    const groups = groupComments(result.removable);
    expect(groups).toHaveLength(2);
    expect(toTestNames(...groups[0]!.map(comment => comment.text))).toEqual([
      'keep the old path around',
    ]);
    expect(toTestNames(...groups[1]!.map(comment => comment.text))).toEqual([]);
  });

  it('never merges block comments', () => {
    const result = resultFor('/* one */\n/* two */\nexport const a = 1;\n');
    expect(groupComments(result.removable)).toHaveLength(2);
  });
});

describe('draftTestNames', () => {
  const cwd = '/repo';

  it('renders one describe block per file and one it.todo per comment', () => {
    const draft = draftTestNames(
      [
        resultFor('// caches the token\nexport const a = 1;\n', '/repo/src/a.ts'),
        resultFor('// retries twice\nexport const b = 2;\n', '/repo/src/b.ts'),
      ],
      { cwd }
    );

    expect(draft.files).toBe(2);
    expect(draft.drafts).toHaveLength(2);
    expect(draft.source).toBe(
      [
        "describe('src/a.ts', () => {",
        "  it.todo('caches the token');",
        '});',
        '',
        "describe('src/b.ts', () => {",
        "  it.todo('retries twice');",
        '});',
        '',
      ].join('\n')
    );
  });

  it('counts the comments it refused to draft', () => {
    const draft = draftTestNames(
      [resultFor('// caches the token\n// return null;\n// ----\nexport const a = 1;\n')],
      { cwd }
    );
    expect(draft.drafts).toHaveLength(1);
    expect(draft.skipped).toBe(2);
  });

  it('emits no source at all when nothing is draftable', () => {
    const draft = draftTestNames([resultFor('// doTheThing();\nexport const a = 1;\n')], { cwd });
    expect(draft.source).toBe('');
    expect(draft.drafts).toHaveLength(0);
  });

  it('drops a repeated comment rather than writing the same stub twice', () => {
    const draft = draftTestNames(
      [resultFor('// caches the token\nconst a = 1;\n\n// caches the token\nconst b = 2;\n')],
      { cwd }
    );
    expect(draft.drafts).toHaveLength(1);
  });

  it('records the line the comment came from', () => {
    const draft = draftTestNames([resultFor('const a = 1;\n\n// caches the token\n')], { cwd });
    expect(draft.drafts[0]).toMatchObject({ file: 'src/a.ts', line: 3 });
  });

  it('skips files that failed to process', () => {
    const draft = draftTestNames([{ ...resultFor('// a\n'), error: 'EACCES' }], { cwd });
    expect(draft.drafts).toHaveLength(0);
  });

  it('escapes an apostrophe so the generated file still parses', () => {
    const draft = draftTestNames([resultFor("// the user's plan can be null\n")], { cwd });
    expect(draft.source).toContain("it.todo('the user\\'s plan can be null');");
  });

  it('wraps a stub the way prettier would when it runs past the print width', () => {
    const long = 'a'.repeat(120);
    const source = renderTestFile([{ file: 'a.ts', names: [long] }]);
    expect(source).toContain(`  it.todo(\n    '${long}'\n  );`);
  });

  it('puts the framework import at the top when it is given one', () => {
    const source = renderTestFile([{ file: 'a.ts', names: ['works'] }], "import { it } from 'x';");
    expect(source.startsWith("import { it } from 'x';\n\ndescribe(")).toBe(true);
  });
});

describe('detectTestImport', () => {
  let box: Sandbox;

  beforeEach(() => {
    box = sandbox();
  });

  afterEach(() => box.cleanup());

  it('imports from vitest when vitest is a dependency', () => {
    box.write('package.json', '{"devDependencies": {"vitest": "^3.0.0"}}');
    expect(detectTestImport(box.dir)).toBe("import { describe, it } from 'vitest';");
  });

  it('imports from bun:test for a bun project', () => {
    box.write('package.json', '{"devDependencies": {"@types/bun": "^1.0.0"}}');
    expect(detectTestImport(box.dir)).toBe("import { describe, it } from 'bun:test';");
  });

  it('relies on globals for jest', () => {
    box.write('package.json', '{"devDependencies": {"jest": "^29.0.0"}}');
    expect(detectTestImport(box.dir)).toBeNull();
  });

  it('imports from @jest/globals when jest is configured without globals', () => {
    box.write('package.json', '{"devDependencies": {"@jest/globals": "^29.0.0"}}');
    expect(detectTestImport(box.dir)).toBe("import { describe, it } from '@jest/globals';");
  });

  it('relies on globals when there is no package.json to read', () => {
    expect(detectTestImport(box.dir)).toBeNull();
  });

  it('relies on globals when package.json is not valid JSON', () => {
    box.write('package.json', '{ not json');
    expect(detectTestImport(box.dir)).toBeNull();
  });
});

describe('cli --to-test-names', () => {
  let box: Sandbox;

  beforeEach(() => {
    box = sandbox();
    box.write('commentless.config.json', '{"cache": false}');
  });

  afterEach(() => box.cleanup());

  it('writes a draft alongside --check without touching the source', () => {
    box.write('a.ts', '// caches the token\nexport const a = 1;\n');
    return cli(['--check', '--to-test-names', 'drafts.test.ts'], box.dir).then(result => {
      expect(result.code).toBe(1);
      expect(readFileSync(`${box.dir}/a.ts`, 'utf8')).toContain('// caches the token');
      expect(readFileSync(`${box.dir}/drafts.test.ts`, 'utf8')).toContain(
        "it.todo('caches the token');"
      );
    });
  });

  it('reports what it drafted on stderr so stdout stays machine-readable', async () => {
    box.write('a.ts', '// caches the token\nexport const a = 1;\n');
    const result = await cli(
      ['--check', '--reporter', 'json', '--to-test-names', 'drafts.test.ts'],
      box.dir
    );
    expect(() => JSON.parse(result.stdout)).not.toThrow();
    expect(result.stderr).toContain('Drafted 1 test name from 1 file');
  });

  it('points at the prompt for handing the skeleton to an agent', async () => {
    box.write('a.ts', '// caches the token\nexport const a = 1;\n');
    const result = await cli(['--check', '--to-test-names', 'drafts.test.ts'], box.dir);
    expect(result.stderr).toContain('hand drafts.test.ts to your coding agent');
    expect(result.stderr).toContain('#hand-the-skeleton-to-an-agent');
  });

  it('says how many comments it refused to draft', async () => {
    box.write('a.ts', '// caches the token\n// return null;\nexport const a = 1;\n');
    const result = await cli(['--check', '--to-test-names', 'drafts.test.ts'], box.dir);
    expect(result.stderr).toContain('1 comment skipped');
  });

  it('creates the directories leading to the draft file', async () => {
    box.write('a.ts', '// caches the token\nexport const a = 1;\n');
    await cli(['--check', '--to-test-names', 'tests/drafts/comments.test.ts'], box.dir);
    expect(existsSync(`${box.dir}/tests/drafts/comments.test.ts`)).toBe(true);
  });

  it('refuses to overwrite an existing draft before it rewrites anything', async () => {
    box.write('a.ts', '// caches the token\nexport const a = 1;\n');
    box.write('drafts.test.ts', 'export const mine = 1;\n');

    const result = await cli(['--write', '--to-test-names', 'drafts.test.ts'], box.dir);
    expect(result.code).toBe(2);
    expect(result.stderr).toContain('Re-run with --force');
    expect(readFileSync(`${box.dir}/drafts.test.ts`, 'utf8')).toBe('export const mine = 1;\n');
    expect(readFileSync(`${box.dir}/a.ts`, 'utf8')).toContain('// caches the token');
  });

  it('overwrites the draft when --force says so', async () => {
    box.write('a.ts', '// caches the token\nexport const a = 1;\n');
    box.write('drafts.test.ts', 'export const mine = 1;\n');

    const result = await cli(['--check', '--force', '--to-test-names', 'drafts.test.ts'], box.dir);
    expect(result.code).toBe(1);
    expect(readFileSync(`${box.dir}/drafts.test.ts`, 'utf8')).toContain('it.todo(');
  });

  it('writes nothing and says so when there is no comment to draft', async () => {
    box.write('a.ts', 'export const a = 1;\n');
    const result = await cli(['--check', '--to-test-names', 'drafts.test.ts'], box.dir);
    expect(result.code).toBe(0);
    expect(existsSync(`${box.dir}/drafts.test.ts`)).toBe(false);
    expect(result.stderr).toContain('No comments left to draft');
  });

  it('drafts from the comments it removed under --write', async () => {
    box.write('a.ts', '// caches the token\nexport const a = 1;\n');
    const result = await cli(['--write', '--to-test-names', 'drafts.test.ts'], box.dir);
    expect(result.code).toBe(0);
    expect(readFileSync(`${box.dir}/a.ts`, 'utf8')).toBe('export const a = 1;\n');
    expect(readFileSync(`${box.dir}/drafts.test.ts`, 'utf8')).toContain(
      "it.todo('caches the token');"
    );
  });

  it('rejects --to-test-names on init, which has no comments to draft', async () => {
    const result = await cli(['init', '--to-test-names', 'drafts.test.ts'], box.dir);
    expect(result.code).toBe(2);
    expect(result.stderr).toContain('does not apply to init');
  });
});
