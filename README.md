# commentless

Strip comments from JavaScript and TypeScript with a real parser, **keep the ones that do work**, and fail CI when new ones appear.

```bash
bunx commentless           # rewrite files in place
bunx commentless --check   # exit 1 if any comment would be removed
```

Some teams want their source to carry no commentary — the reasoning lives in commit messages, PR descriptions and docs, so it can't rot in place. Enforcing that by hand does not work. `commentless` enforces it, and it is careful about the comments that are not commentary.

---

## Why not `strip-comments` or `decomment`?

Both are libraries, not CLIs, both are regex/lexer based, and both have been unmaintained since 2022.

|                                            | commentless | strip-comments | decomment |
| ------------------------------------------ | :---------: | :------------: | :-------: |
| CLI (`bunx` / `npx`)                       |     ✅      |       ❌       |    ❌     |
| `--check` mode for CI                      |     ✅      |       ❌       |    ❌     |
| TypeScript / TSX / JSX aware               |     ✅      |       ❌       |    ❌     |
| Keeps `eslint-disable`, `@ts-expect-error` |     ✅      |       ❌       |    ❌     |
| Safe inside strings, regex, templates      |     ✅      |    partial     |  partial  |
| GitHub inline annotations                  |     ✅      |       ❌       |    ❌     |

`commentless` parses with the TypeScript compiler, so a `//` inside a string literal, a regex literal, a template literal, or JSX body text is text — not a comment.

```ts
const url = 'https://example.com'; //   ← the // in the string is never touched
const re = /\/\/ not a comment/;   //   ← nor this one
<div>see the // in this copy</div> //   ← nor this one
```

---

## Install

Nothing to install — run it directly:

```bash
bunx commentless --check      # bun
npx  commentless --check      # npm
pnpm dlx commentless --check  # pnpm
```

Or add it to a project:

```bash
bun add -d commentless
npm i -D commentless
```

Requires Node 20+.

---

## Comments that are kept

Deleting a directive comment is a bug, not a cleanup. These survive by default:

| Group        | Examples                                                                                                                                         |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Linters      | `eslint-disable*`, `eslint-enable`, `eslint-env`, `/* global */`, `biome-ignore`, `prettier-ignore`, `oxlint-disable`                            |
| Type checker | `@ts-expect-error`, `@ts-ignore`, `@ts-nocheck`, `/// <reference … />`                                                                           |
| Coverage     | `istanbul ignore`, `c8 ignore`, `v8 ignore`, `node:coverage`                                                                                     |
| Bundlers     | `webpackChunkName:` and friends, `@vite-ignore`, `/* @__PURE__ */`, `@__NO_SIDE_EFFECTS__`                                                       |
| Pragmas      | `@jsx`, `@jsxImportSource`, `@jsxRuntime`, `@vitest-environment`, `@jest-environment`                                                            |
| JSDoc types  | `@type`, `@satisfies`, `@typedef`, `@template`, `@overload`, `@import` — in `.js`/`.jsx`/`.mjs`/`.cjs` only, where they actually drive inference |
| Legal        | `@license`, `@preserve`, `SPDX-License-Identifier`, any `/*! … */`                                                                               |
| Shebang      | `#!/usr/bin/env node`                                                                                                                            |

Add your own with `--keep <regex>` (repeatable) or `keep` in the config file. A common pair:

```jsonc
{ "keep": ["https?://", "@(public|internal)\\b"] }
```

Disable the built-in list with `--no-default-keep`. You almost certainly do not want to.

### Inline escapes

```ts
// commentless-keep  this one comment stays
// commentless-keep-next-line
// …and so does this one
// commentless-ignore-file  ← anywhere in the first 4 KB: skip the file entirely
```

---

## CLI

```
commentless [paths...] [options]
```

**Mode**

| Flag        | Effect                                                          |
| ----------- | --------------------------------------------------------------- |
| `--check`   | Report only, never write. Exit 1 if a comment would be removed. |
| `--write`   | Rewrite files in place. The default when `--check` is absent.   |
| `--dry-run` | Report what `--write` would do, write nothing. Always exits 0.  |

**Scope**

| Flag                | Effect                                                            |
| ------------------- | ----------------------------------------------------------------- |
| `--staged`          | Only files staged in git — for a pre-commit hook.                 |
| `--changed`         | Only files changed against `--base`.                              |
| `--base <ref>`      | Base ref for `--changed`. Defaults to `origin/HEAD`, then `main`. |
| `--ext <list>`      | Comma-separated. Default `ts,tsx,mts,cts,js,jsx,mjs,cjs`.         |
| `--ignore <glob>`   | Gitignore-syntax pattern to skip. Repeatable.                     |
| `--ignore-file <p>` | Default `.commentlessignore`.                                     |
| `--no-gitignore`    | Stop honouring `.gitignore`.                                      |
| `--list-files`      | Print the resolved file list and exit — for debugging discovery.  |

**Comments to keep**

| Flag                     | Effect                                                     |
| ------------------------ | ---------------------------------------------------------- |
| `--keep <regex>`         | Keep comments matching this pattern. Repeatable.           |
| `--no-default-keep`      | Drop the built-in directive allowlist.                     |
| `--collapse-blank-lines` | Also trim trailing whitespace and collapse 3+ blank lines. |

**Output**

| Flag                | Effect                                                         |
| ------------------- | -------------------------------------------------------------- |
| `--reporter <name>` | `pretty` (default), `json`, `github`, `summary`.               |
| `--max-allowed <n>` | `--check` passes while removable comments are at or under `n`. |
| `-q, --quiet`       | Summary only.                                                  |
| `--no-color`        | Disable colour.                                                |

**Other**

| Flag                | Effect                               |
| ------------------- | ------------------------------------ |
| `--concurrency <n>` | Worker threads. Default `cpus - 1`.  |
| `--no-cache`        | Skip the clean-file cache.           |
| `--config <path>`   | Path to a `commentless.config.json`. |

**Exit codes**

| Code | Meaning                                                           |
| ---- | ----------------------------------------------------------------- |
| `0`  | Clean.                                                            |
| `1`  | Comments found under `--check`, or a file could not be processed. |
| `2`  | Bad usage or invalid configuration.                               |

---

## Config

`commentless.config.json` in the project root (or any ancestor), or a `"commentless"` key in `package.json`. Every CLI flag overrides the file.

```json
{
  "ext": ["ts", "tsx"],
  "ignore": ["db/generated/**", ".storybook/**"],
  "keep": ["https?://", "@(public|internal)\\b"],
  "collapseBlankLines": true,
  "maxAllowed": 0,
  "reporter": "pretty"
}
```

The config is JSON on purpose. A `.ts` config would be a file this tool strips comments out of.

---

## In CI

`--reporter github` emits workflow annotations, so every offending comment shows up inline on the PR diff.

```yaml
- uses: oven-sh/setup-bun@v2
- run: bunx commentless@0.1.0 . --check --reporter github
```

Scope it to the PR diff instead of the whole repo (needs `fetch-depth: 0`):

```yaml
- uses: actions/checkout@v4
  with: { fetch-depth: 0 }
- run: bunx commentless@0.1.0 . --check --changed --base origin/main --reporter github
```

Adopting on a repo that already has comments? Set a ceiling and ratchet it down:

```bash
commentless --check --max-allowed 240
```

### Pre-commit

```bash
commentless --staged --write
```

---

## Performance

Measured on a 2 225-file Next.js repository, M-series Mac, 10 worker threads:

| Run                     | Time     |
| ----------------------- | -------- |
| single thread, no cache | 1 012 ms |
| 10 workers, no cache    | 530 ms   |
| 10 workers, warm cache  | 321 ms   |

Where the time does not go:

- **Discovery** uses `git ls-files --cached --others --exclude-standard` inside a repository, so `.gitignore` is honoured for free and `node_modules` is never walked.
- **A substring pre-filter** skips the parser entirely for any file with no `//` or `/*` — which is most files once the tool has done its job.
- **One AST walk** collects trivia and JSX comment nodes in a single pass.
- **A clean-file cache** under `node_modules/.cache/commentless` keys on size + mtime, so unchanged files are skipped outright. Cache with `actions/cache` in CI, or disable it with `--no-cache`.

---

## Programmatic API

```ts
import { scanSource, stripComments, resolveKeepRules, run } from 'commentless';

const keep = resolveKeepRules({ userPatterns: ['https?://'] });
const { removable, kept } = scanSource(source, { fileName: 'a.tsx', keep });
const output = stripComments(source, removable);

const result = await run({ cwd: process.cwd(), mode: 'check', extensions: ['ts', 'tsx'], keep });
process.exitCode = result.exitCode;
```

---

## What it does to your diff

Removing a comment removes the whitespace it owned, and nothing else:

```diff
-// a note
 const a = 1;
-const b = 2; // trailing
+const b = 2;
```

A comment alone on its line takes the line with it. A trailing comment takes the space in front of it. Every other line stays byte-identical — CRLF endings, BOM, and existing blank runs included — unless you ask for `--collapse-blank-lines`. Running it twice is a no-op.

---

## Licence

MIT
