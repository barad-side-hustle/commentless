import { describe, expect, it } from 'vitest';
import * as api from '../src/index.js';

describe('public api', () => {
  it('exports the documented surface', () => {
    for (const name of [
      'scanSource',
      'stripComments',
      'collapseBlankLines',
      'discoverFiles',
      'processFile',
      'run',
      'report',
      'loadConfig',
      'validateConfig',
      'resolveKeepRules',
      'main',
    ] as const) {
      expect(typeof api[name], name).toBe('function');
    }
    expect(api.DEFAULT_KEEP_RULES.length).toBeGreaterThan(10);
    expect(api.DEFAULT_EXTENSIONS).toContain('tsx');
    expect(api.REPORTERS).toEqual(['pretty', 'json', 'github', 'summary']);
  });

  it('strips comments through the library entry point', () => {
    const { removable } = api.scanSource('// note\nconst a = 1;\n', {
      fileName: 'a.ts',
      keep: api.resolveKeepRules({}),
    });
    expect(api.stripComments('// note\nconst a = 1;\n', removable)).toBe('const a = 1;\n');
  });
});
