import type { Comment, KeepRule, SerializedKeepRule } from '../types.js';

const JS_FAMILY = ['.js', '.jsx', '.mjs', '.cjs'] as const;

export const KEEP_MARKER = 'commentless-keep';
export const KEEP_NEXT_MARKER = 'commentless-keep-next-line';
export const IGNORE_FILE_MARKER = 'commentless-ignore-file';

export const DEFAULT_KEEP_RULES: readonly KeepRule[] = [
  { name: 'commentless', test: /\bcommentless-keep(-next-line)?\b/ },
  { name: 'eslint', test: /\beslint-(disable|enable|env)\b/ },
  { name: 'eslint-globals', test: /^\/[/*]\s*globals?\s/ },
  { name: 'typescript', test: /@ts-(expect-error|ignore|nocheck|check)\b/ },
  { name: 'triple-slash', test: /^\/\/\/\s*</ },
  { name: 'biome', test: /\bbiome-ignore\b/ },
  { name: 'prettier', test: /\bprettier-ignore(-start|-end)?\b/ },
  { name: 'oxlint', test: /\boxlint-disable\b/ },
  { name: 'coverage', test: /\b(?:istanbul|c8|v8)\s+ignore\b|\bnode:coverage\b/ },
  { name: 'bundler-magic', test: /\bwebpack[A-Za-z]+\s*:|@vite-ignore\b/ },
  { name: 'pure-annotation', test: /[@#]__(PURE|NO_SIDE_EFFECTS|KEY)__/ },
  { name: 'jsx-pragma', test: /@jsx(Runtime|ImportSource|Frag)?\b/ },
  { name: 'test-environment', test: /@(vitest|jest)-environment\b/ },
  { name: 'license', test: /@(license|preserve)\b|\bSPDX-License-Identifier\b/ },
  { name: 'bang', test: /^\/\*!/ },
  {
    name: 'jsdoc-type',
    test: /@(type|satisfies|typedef|template|overload|import)\b/,
    extensions: JS_FAMILY,
  },
];

export function serializeKeepRules(rules: readonly KeepRule[]): SerializedKeepRule[] {
  return rules.map(rule => ({
    name: rule.name,
    source: rule.test.source,
    flags: rule.test.flags,
    ...(rule.extensions ? { extensions: rule.extensions } : {}),
  }));
}

export function deserializeKeepRules(rules: readonly SerializedKeepRule[]): KeepRule[] {
  return rules.map(rule => ({
    name: rule.name,
    test: new RegExp(rule.source, rule.flags),
    ...(rule.extensions ? { extensions: rule.extensions } : {}),
  }));
}

export const KEEP_RULE_NAMES: readonly string[] = DEFAULT_KEEP_RULES.map(rule => rule.name);

export const KEEP_RULE_DESCRIPTIONS: Readonly<Record<string, string>> = {
  commentless: 'commentless-keep and commentless-keep-next-line',
  eslint: 'eslint-disable, eslint-enable, eslint-env',
  'eslint-globals': '/* global … */ and /* globals … */',
  typescript: '@ts-expect-error, @ts-ignore, @ts-nocheck, @ts-check',
  'triple-slash': '/// <reference … />',
  biome: 'biome-ignore',
  prettier: 'prettier-ignore',
  oxlint: 'oxlint-disable',
  coverage: 'istanbul / c8 / v8 ignore, node:coverage',
  'bundler-magic': 'webpackChunkName: and friends, @vite-ignore',
  'pure-annotation': '@__PURE__, @__NO_SIDE_EFFECTS__, @__KEY__',
  'jsx-pragma': '@jsx, @jsxImportSource, @jsxRuntime, @jsxFrag',
  'test-environment': '@vitest-environment, @jest-environment',
  license: '@license, @preserve, SPDX-License-Identifier',
  bang: 'any /*! … */ comment',
  'jsdoc-type': '@type, @satisfies, @typedef, @template, @overload, @import (.js family only)',
};

export class UnknownKeepRuleError extends Error {
  constructor(names: readonly string[]) {
    super(
      `unknown keep rule${names.length === 1 ? '' : 's'} ${names.map(name => `"${name}"`).join(', ')}. ` +
        `Valid rules: ${KEEP_RULE_NAMES.join(', ')}`
    );
  }
}

function assertKnown(names: readonly string[]): void {
  const unknown = names.filter(name => !KEEP_RULE_NAMES.includes(name));
  if (unknown.length > 0) throw new UnknownKeepRuleError(unknown);
}

export function resolveKeepRules(options: {
  defaults?: boolean;
  userPatterns?: readonly string[];
  disable?: readonly string[];
  only?: readonly string[];
}): KeepRule[] {
  const disable = options.disable ?? [];
  const only = options.only;
  assertKnown([...disable, ...(only ?? [])]);

  let rules: KeepRule[] = options.defaults === false ? [] : [...DEFAULT_KEEP_RULES];
  if (only) rules = rules.filter(rule => only.includes(rule.name));
  if (disable.length > 0) rules = rules.filter(rule => !disable.includes(rule.name));

  for (const pattern of options.userPatterns ?? []) {
    rules.push({ name: `config:${pattern}`, test: new RegExp(pattern) });
  }
  return rules;
}

function extensionOf(fileName: string): string {
  const dot = fileName.lastIndexOf('.');
  return dot === -1 ? '' : fileName.slice(dot).toLowerCase();
}

export function matchKeepRule(
  text: string,
  rules: readonly KeepRule[],
  fileName: string
): string | undefined {
  const extension = extensionOf(fileName);
  for (const rule of rules) {
    if (rule.extensions && !rule.extensions.includes(extension)) continue;
    if (rule.test.test(text)) return rule.name;
  }
  return undefined;
}

export function hasIgnoreFileMarker(source: string): boolean {
  const head = source.slice(0, 4096);
  return head.includes(IGNORE_FILE_MARKER);
}

export function applyKeepNextLine(comments: readonly Comment[]): Set<number> {
  const forced = new Set<number>();
  for (let i = 0; i < comments.length; i += 1) {
    const current = comments[i];
    if (!current || !current.text.includes(KEEP_NEXT_MARKER)) continue;
    const next = comments[i + 1];
    if (next) forced.add(next.start);
  }
  return forced;
}
