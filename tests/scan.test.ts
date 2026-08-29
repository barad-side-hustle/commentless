import { describe, expect, it } from 'vitest';
import { scan, strip } from './helpers.js';

describe('comment detection', () => {
  it('removes line and block comments', () => {
    expect(strip('// gone\nconst a = 1;\n')).toBe('const a = 1;\n');
    expect(strip('/* gone */\nconst a = 1;\n')).toBe('const a = 1;\n');
  });

  it('removes a trailing comment without touching the code before it', () => {
    expect(strip('const a = 1; // gone\n')).toBe('const a = 1;\n');
  });

  it('keeps indentation when a block comment sits before code on the same line', () => {
    expect(strip('  /* gone */ call();\n')).toBe('  call();\n');
  });

  it('reports position and kind', () => {
    const { removable } = scan('const a = 1;\n  // note\n');
    expect(removable).toHaveLength(1);
    expect(removable[0]).toMatchObject({ line: 2, column: 3, kind: 'line', text: '// note' });
  });

  it('finds a comment at end of file with no trailing newline', () => {
    expect(strip('const a = 1;\n// last')).toBe('const a = 1;\n');
  });

  it('handles a file that is only a comment', () => {
    expect(strip('// alone\n')).toBe('');
    expect(strip('// alone')).toBe('');
  });

  it('short-circuits files with no comment markers', () => {
    expect(scan('const a = 1;\n').removable).toEqual([]);
  });
});

describe('comments that are not comments', () => {
  it('leaves // inside a string literal alone', () => {
    const source = 'const url = "http_//not a comment";\nconst s = \'// nope\';\n';
    expect(strip(source)).toBe(source);
  });

  it('leaves // inside a regex literal alone', () => {
    const source = 'const re = /\\/\\/ not a comment/g;\nexport { re };\n';
    expect(strip(source)).toBe(source);
  });

  it('leaves comment markers inside a template literal alone', () => {
    const source = 'const t = `line // not\n/* not */ still text`;\n';
    expect(strip(source)).toBe(source);
  });

  it('removes a real comment inside a template substitution', () => {
    expect(strip('const t = `${/* gone */ value}`;\n')).toBe('const t = `${value}`;\n');
  });

  it('leaves // inside JSX text alone', () => {
    const source = 'export const A = (\n  <div>\n    // this is copy, not code\n  </div>\n);\n';
    expect(strip(source, 'a.tsx')).toBe(source);
  });

  it('leaves a slash-slash sequence after a JSX expression alone', () => {
    const source = 'export const A = <div>{x} // literal text</div>;\n';
    expect(strip(source, 'a.tsx')).toBe(source);
  });
});

describe('jsx comments', () => {
  it('removes the braces along with the comment', () => {
    const source = 'export const A = (\n  <div>\n    {/* gone */}\n    <span />\n  </div>\n);\n';
    expect(strip(source, 'a.tsx')).toBe(
      'export const A = (\n  <div>\n    <span />\n  </div>\n);\n'
    );
  });

  it('removes a multi-line jsx comment', () => {
    const source = '<div>\n  {/*\n    gone\n  */}\n  <b />\n</div>;\n';
    expect(strip(source, 'a.tsx')).toBe('<div>\n  <b />\n</div>;\n');
  });

  it('leaves an empty expression container alone', () => {
    const source = 'export const A = <div>{}</div>;\n';
    expect(strip(source, 'a.tsx')).toBe(source);
  });

  it('marks jsx comments with the jsx kind', () => {
    const { removable } = scan('<div>{/* x */}</div>;\n', 'a.tsx');
    expect(removable.map(comment => comment.kind)).toEqual(['jsx']);
  });
});

describe('language coverage', () => {
  const cases: Array<[string, string]> = [
    ['a.ts', 'const a: number = 1;'],
    ['a.tsx', 'export const A = () => <div />;'],
    ['a.mts', 'export const a = 1;'],
    ['a.cts', 'export const a = 1;'],
    ['a.js', 'const a = 1;'],
    ['a.jsx', 'export const A = () => <div />;'],
    ['a.mjs', 'export const a = 1;'],
    ['a.cjs', 'const a = 1;'],
  ];

  it.each(cases)('strips comments from %s', (fileName, code) => {
    expect(strip(`// gone\n${code}\n`, fileName)).toBe(`${code}\n`);
  });

  it('parses modern syntax without losing comments', () => {
    const source = [
      '// gone',
      'const config = { a: 1 } satisfies Record<string, number>;',
      'class Box {',
      '  accessor value = 1;',
      '}',
      'export { config, Box };',
      '',
    ].join('\n');
    expect(strip(source)).toBe(source.replace('// gone\n', ''));
  });
});

describe('whitespace fidelity', () => {
  it('preserves CRLF line endings', () => {
    expect(strip('// gone\r\nconst a = 1;\r\n')).toBe('const a = 1;\r\n');
    expect(strip('const a = 1; // gone\r\nconst b = 2;\r\n')).toBe(
      'const a = 1;\r\nconst b = 2;\r\n'
    );
  });

  it('preserves a byte order mark', () => {
    expect(strip('﻿// gone\nconst a = 1;\n')).toBe('﻿const a = 1;\n');
  });

  it('leaves untouched lines byte-identical by default', () => {
    const source = 'const a = 1;   \n\n\n\n// gone\nconst b = 2;\n';
    expect(strip(source)).toBe('const a = 1;   \n\n\n\nconst b = 2;\n');
  });

  it('tidies whitespace only when asked', () => {
    const source = 'const a = 1;   \n\n\n\n// gone\nconst b = 2;\n';
    expect(strip(source, 'input.ts', { collapseBlankLines: true })).toBe(
      'const a = 1;\n\nconst b = 2;\n'
    );
  });

  it('is idempotent', () => {
    const source = '// one\nconst a = 1; // two\n\n/* three */\nconst b = 2;\n';
    const once = strip(source);
    expect(strip(once)).toBe(once);
  });
});
