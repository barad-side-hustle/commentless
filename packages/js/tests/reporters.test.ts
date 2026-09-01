import { describe, expect, it } from 'vitest';
import { report } from '../src/reporters/index.js';
import type { RunResult } from '../src/types.js';

const RESULT: RunResult = {
  summary: {
    mode: 'check',
    discovered: 12,
    parsed: 10,
    cached: 2,
    filesWithComments: 1,
    commentsRemoved: 2,
    commentsKept: 3,
    errors: 0,
    durationMs: 42,
  },
  files: [
    {
      file: '/repo/src/a.ts',
      changed: true,
      keptCount: 3,
      removable: [
        { start: 0, end: 7, line: 1, column: 1, kind: 'line', text: '// note' },
        { start: 30, end: 42, line: 4, column: 3, kind: 'block', text: '/* second */' },
      ],
    },
  ],
  exitCode: 1,
};

const CONTEXT = { cwd: '/repo', quiet: false, verbose: false, color: false };

describe('reporters', () => {
  it('pretty lists every offending comment with a location', () => {
    const output = report('pretty', RESULT, CONTEXT);
    expect(output).toContain('src/a.ts');
    expect(output).toContain('src/a.ts:1:1');
    expect(output).toContain('src/a.ts:4:3');
    expect(output).toContain('2 comments to remove in 1 file');
    expect(output).toContain('commentless --write');
  });

  it('pretty in quiet mode omits individual comments', () => {
    const output = report('pretty', RESULT, { ...CONTEXT, quiet: true });
    expect(output).toContain('src/a.ts');
    expect(output).not.toContain('src/a.ts:1:1');
  });

  it('summary is a single line', () => {
    const output = report('summary', RESULT, CONTEXT);
    expect(output.split('\n')).toHaveLength(1);
    expect(output).toContain('12 files scanned, 2 cached');
    expect(output).toContain('3 kept');
  });

  it('github emits one annotation per comment plus a notice', () => {
    const lines = report('github', RESULT, CONTEXT).split('\n');
    expect(lines[0]).toBe(
      '::error file=src/a.ts,line=1,col=1,title=commentless::Remove this comment%3A // note'
    );
    expect(lines[1]).toContain('file=src/a.ts,line=4,col=3');
    expect(lines[2]).toMatch(/^::notice title=commentless::/);
  });

  it('github escapes newlines and percent signs in the message', () => {
    const output = report(
      'github',
      {
        ...RESULT,
        files: [
          {
            file: '/repo/src/b.ts',
            changed: true,
            keptCount: 0,
            removable: [
              { start: 0, end: 20, line: 1, column: 1, kind: 'block', text: '/* 50%\nof it */' },
            ],
          },
        ],
      },
      CONTEXT
    );
    expect(output).toContain('%25');
    expect(output).not.toMatch(/::error[^\n]*\n[^:]/);
  });

  it('json is stable and machine readable', () => {
    const parsed = JSON.parse(report('json', RESULT, CONTEXT));
    expect(parsed).toMatchObject({
      version: 1,
      exitCode: 1,
      summary: { mode: 'check', commentsRemoved: 2, commentsKept: 3 },
      files: [
        {
          file: 'src/a.ts',
          changed: true,
          keptCount: 3,
          comments: [
            { line: 1, column: 1, kind: 'line', text: '// note' },
            { line: 4, column: 3, kind: 'block', text: '/* second */' },
          ],
        },
      ],
    });
  });

  it('reports errors in every reporter', () => {
    const failing: RunResult = {
      summary: { ...RESULT.summary, errors: 1, commentsRemoved: 0, filesWithComments: 0 },
      files: [
        { file: '/repo/src/c.ts', changed: false, keptCount: 0, removable: [], error: 'EACCES' },
      ],
      exitCode: 1,
    };
    expect(report('pretty', failing, CONTEXT)).toContain('EACCES');
    expect(report('github', failing, CONTEXT)).toContain('::error file=src/c.ts::EACCES');
    expect(JSON.parse(report('json', failing, CONTEXT)).files[0].error).toBe('EACCES');
    expect(report('summary', failing, CONTEXT)).toContain('1 error');
  });
});
