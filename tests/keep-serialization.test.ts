import { describe, expect, it } from 'vitest';
import { deserializeKeepRules, resolveKeepRules, serializeKeepRules } from '../src/core/keep.js';

describe('keep rule serialization', () => {
  it('survives a round trip through structured clone', () => {
    const original = resolveKeepRules({ userPatterns: ['https?://', 'TODO'] });
    const restored = deserializeKeepRules(structuredClone(serializeKeepRules(original)));

    expect(restored).toHaveLength(original.length);
    expect(restored.map(rule => rule.name)).toEqual(original.map(rule => rule.name));
    expect(restored.map(rule => rule.test.source)).toEqual(original.map(rule => rule.test.source));

    const jsdoc = restored.find(rule => rule.name === 'jsdoc-type');
    expect(jsdoc?.extensions).toEqual(['.js', '.jsx', '.mjs', '.cjs']);
  });
});
