<a id="readme-top"></a>

<!-- PROJECT LOGO -->
<br />
<div align="center">

<h1 align="center">commentless</h1>

  <p align="center">
    <strong>Your code does not need a narrator.</strong>
    <br />
    Strip comments with a real parser, keep the ones that actually do work,
    and fail CI when someone sneaks a new one in.
  </p>

<!-- PROJECT SHIELDS -->

[![npm version][npm-shield]][npm-url]
[![PyPI version][pypi-shield]][pypi-url]
[![npm downloads][downloads-shield]][downloads-url]
[![CI][build-shield]][build-url]
[![Node][node-version-shield]][node-version-url]
[![Python][python-version-shield]][python-version-url]
[![License][license-shield]][license-url]
[![Stars][stars-shield]][stars-url]

  <p align="center">
    <a href="#usage"><strong>Explore the flags »</strong></a>
    <br />
    <br />
    <a href="#see-it-work">See it work</a>
    &middot;
    <a href="#why-your-comments-belong-in-test-names">The philosophy</a>
    &middot;
    <a href="#python">Python</a>
    &middot;
    <a href="#faq">FAQ</a>
    &middot;
    <a href="https://github.com/barad-side-hustle/commentless/issues/new?labels=bug">Report Bug</a>
    &middot;
    <a href="https://github.com/barad-side-hustle/commentless/issues/new?labels=enhancement">Request Feature</a>
  </p>
</div>

<!-- LANGUAGES -->

## Two implementations, one convention

`commentless` ships one implementation per language. They are separate packages on separate
registries, but they share a keep-rule vocabulary, a config schema, a flag surface, four
reporters and three exit codes — so a polyglot repo gets one gate, not two dialects.

|                 | JavaScript / TypeScript                                           | Python                                                         |
| --------------- | ----------------------------------------------------------------- | -------------------------------------------------------------- |
| Package         | [`commentless`](https://www.npmjs.com/package/commentless) on npm | [`commentless`](https://pypi.org/project/commentless/) on PyPI |
| Source          | [`packages/js`](packages/js)                                      | [`packages/python`](packages/python)                           |
| Run it          | `bunx commentless`                                                | `uvx commentless`                                              |
| Parser          | the TypeScript compiler                                           | `tokenize` + `ast`                                             |
| Extensions      | `.ts .tsx .mts .cts .js .jsx .mjs .cjs`                           | `.py .pyi`                                                     |
| Keep rules      | 16                                                                | 19                                                             |
| Drafts tests as | `it.todo(...)`                                                    | `@pytest.mark.skip` / `@unittest.skip`                         |
| Docs            | this page                                                         | [`packages/python/README.md`](packages/python/README.md)       |

Everything below is the JavaScript/TypeScript story. **[Jump to Python →](#python)**

<!-- TL;DR -->

## TL;DR

```sh
bunx commentless init     # write a config baselined to today's comment count
bunx commentless --check  # exit 1 if a comment sneaks in — this is your CI gate
bunx commentless          # delete them
```

- **It deletes comments.** Not with a regex — with the TypeScript compiler, so a `//` inside a
  string, a regex literal, a template literal or JSX body text is text, not a casualty.
- **It keeps the ones that do work.** `eslint-disable`, `@ts-expect-error`, `biome-ignore`,
  `istanbul ignore`, `webpackChunkName:`, `@license`, shebangs. All 16 rules are named and
  individually switchable — `--no-keep jsdoc-type`, `--keep-only eslint,typescript`.
- **It fails CI.** `--check --reporter github` annotates every offending comment inline on the PR
  diff. `--max-allowed <n>` lets you adopt gradually instead of in one 4 000-line PR.
- **The point isn't tidiness.** A comment explaining an edge case is an unverified claim that
  nothing breaks when it goes stale. Write it as an `it(...)` name instead: same sentence, but it
  runs, it goes red when it stops being true, and you can't write it without covering the branch.
  Coverage goes up, source files get denser, and every agent that reads your repo stops paying
  tokens for prose nobody checks. → [the long version](#why-your-comments-belong-in-test-names)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- SEE IT WORK -->

## See it work

A file with two explanatory comments, one trailing note, and one directive that is actually load
bearing:

```ts
// The billing API answers 200 with an empty body when the user has never
// subscribed, so we have to null-check before parsing.
export async function getPlan(userId: string) {
  const res = await fetch(`https://api.example.com/billing/${userId}`);
  const body = await res.text(); // trailing note nobody reads
  if (!body) return null;
  /* eslint-disable-next-line no-eval */
  return JSON.parse(body);
}
```

`--check` tells you where they are and exits `1`, which is the whole CI story:

```console
$ bunx commentless . --check
• src/billing.ts (3 comments found)
  src/billing.ts:1:1  // The billing API answers 200 with an empty body when the user has n...
  src/billing.ts:2:1  // subscribed, so we have to null-check before parsing.
  src/billing.ts:5:34  // trailing note nobody reads

✖ 1 file scanned · 3 comments to remove in 1 file, 1 kept · 31ms

$ echo $?
1
```

Three removed, **one kept** — note the count. `--write` gives you this, and the
`eslint-disable-next-line` is still there, because deleting it would have handed a broken build to
ESLint:

```ts
export async function getPlan(userId: string) {
  const res = await fetch(`https://api.example.com/billing/${userId}`);
  const body = await res.text();
  if (!body) return null;
  /* eslint-disable-next-line no-eval */
  return JSON.parse(body);
}
```

And the part a regex gets wrong. Only the last line here is a comment, and only the last line goes:

```diff
 const url = 'https://example.com';
 const re = /\/\/ not a comment/;
 const tpl = `path // still text`;
 export const El = () => <div>see the // in this copy</div>;
-// this one is not safe
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#why-your-comments-belong-in-test-names">Why your comments belong in test names</a></li>
        <li><a href="#why-not-strip-comments-or-decomment">Why not strip-comments or decomment</a></li>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li><a href="#tldr">TL;DR</a></li>
    <li><a href="#see-it-work">See it work</a></li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
        <li><a href="#commentless-init">commentless init</a></li>
      </ul>
    </li>
    <li>
      <a href="#usage">Usage</a>
      <ul>
        <li><a href="#comments-that-survive">Comments that survive</a></li>
        <li><a href="#from-comments-to-test-names">From comments to test names</a></li>
        <li><a href="#configuration">Configuration</a></li>
        <li><a href="#reporters">Reporters</a></li>
        <li><a href="#in-ci">In CI</a></li>
        <li><a href="#performance">Performance</a></li>
        <li><a href="#programmatic-api">Programmatic API</a></li>
      </ul>
    </li>
    <li><a href="#faq">FAQ</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>

<!-- ABOUT THE PROJECT -->

## About The Project

Every codebase has one. The comment that says `// increment i by 1` above `i++`. The block that
confidently describes a function that was rewritten in 2023. The `// TODO: fix this properly`
signed by someone who left the company before your onboarding call.

Comments are the only part of your repo that nothing verifies. They compile whether or not they
are true, they survive every refactor that invalidates them, and the linter will never tell you
that the paragraph above `parseUser` now describes a function called `parseOrder`.

Some teams decide the honest fix is to have none of them. The reasoning goes in commit messages,
PR descriptions, docs, and — the good part — **test names**. Enforcing that by hand does not work,
because "delete your comments" is the single most ignorable code review note ever written.

`commentless` enforces it. And, unlike a regex, it knows the difference between a comment and a
comment-shaped thing:

```ts
const url = 'https://example.com'; //   ← the // in the string is safe
const re = /\/\/ not a comment/;   //   ← so is this one
<div>see the // in this copy</div> //   ← and this one
// this one is not safe            //   ← correct
```

It parses with the TypeScript compiler, so string literals, regex literals, template literals and
JSX body text are text. Not comments. Not casualties.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Why your comments belong in test names

This is the part that is actually a design philosophy and not a CLI flag.

When you write a comment explaining an edge case, you are writing a **claim**:

```ts
// The billing API answers 200 with an empty body when the user has never
// subscribed, so we have to null-check before parsing.
if (!body) return null;
```

That claim is unverified prose. Nothing breaks when it becomes false. Nobody is paged when the API
starts returning 204. It sits there, technically a lie, indefinitely, and the next engineer
believes it because it is written down in the same file as the code.

Write the exact same sentence as a test name and it stops being a claim and starts being a
**guarantee**:

```ts
it('returns null when billing answers 200 with an empty body for a never-subscribed user', ...)
```

Same words. Same reader. But now:

- **It runs.** If the behaviour changes, the sentence goes red. A stale test name is a failing
  build; a stale comment is a Tuesday.
- **It is discoverable.** `bun run test` prints your entire edge-case catalogue, in order, for
  free. No `grep -r "// NOTE"`.
- **It drags coverage up behind it.** You cannot name an edge case in a test without writing the
  test. Every comment you migrate is a branch you now cover. This is the cheapest coverage
  strategy in existence: stop explaining edge cases and start asserting them.
- **It survives.** Comments get deleted in refactors because they look like decoration. Deleting
  a test is a decision someone has to defend in review.

#### The token argument, since you are going to ask

Your codebase is read by agents now. Constantly. Every context window, every review, every
"where is this handled", every retrieval hit. Comments are the part of that payload with the
worst ratio in the whole repo: **you pay tokens for them on every single read, forever, and they
buy zero verification.**

An 8-line block comment explaining a race condition costs the same tokens whether it is accurate
or three refactors out of date. Multiply by every file, every read, every agent, every day.

The same 8 lines as four `it(...)` names cost tokens too — but they live in a file the model
usually is not reading, they are _executable_, and they make the source file the agent _is_
reading smaller and denser. Less noise per token. A source file that is 100% code reads like an
API; a source file that is 40% prose reads like a wiki someone abandoned.

So the trade is:

|                                               | comment | test name |
| --------------------------------------------- | ------- | --------- |
| Explains the edge case                        | ✅      | ✅        |
| Can be wrong forever                          | ✅      | ❌        |
| Runs in CI                                    | ❌      | ✅        |
| Improves coverage                             | ❌      | ✅        |
| Costs tokens on every read of the source file | ✅      | ❌        |
| Survives a refactor                           | 🤷      | ✅        |

If a piece of code is complicated enough to need a paragraph, it is complicated enough to need a
test. Write the test. Name it the paragraph. Delete the paragraph.

`commentless` is the thing that makes sure you actually did.

> [!NOTE]
> This is a policy, not a religion. Some comments are load-bearing machinery, not prose —
> `eslint-disable`, `@ts-expect-error`, licence headers. Those are kept by default. See
> [Comments that survive](#comments-that-survive). And when you genuinely need one, mark it
> `// commentless-keep` and move on with your life.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Why not strip-comments or decomment

Both are libraries, not CLIs, both are regex/lexer based, and both have been unmaintained since 2022. Nobody has shipped the thing that actually matters — a check mode.

|                                            |    commentless    | strip-comments | decomment |
| ------------------------------------------ | :---------------: | :------------: | :-------: |
| Runs as a CLI (`bunx` / `npx`)             |        ✅         |       ❌       |    ❌     |
| `--check` mode that fails CI               |        ✅         |       ❌       |    ❌     |
| TypeScript / TSX / JSX aware               |        ✅         |       ❌       |    ❌     |
| Keeps `eslint-disable`, `@ts-expect-error` | ✅ per-rule flags |       ❌       |    ❌     |
| Safe inside strings, regex, templates      |        ✅         |    partial     |  partial  |
| GitHub inline PR annotations               |        ✅         |       ❌       |    ❌     |
| Maintained this decade                     |        ✅         |       ❌       |    ❌     |

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Built With

[![TypeScript][typescript-shield]][typescript-url]
[![Node.js][node-shield]][node-url]
[![Vitest][vitest-shield]][vitest-url]
[![Bun][bun-shield]][bun-url]
[![Python][python-shield]][python-url]
[![uv][uv-shield]][uv-url]
[![Ruff][ruff-shield]][ruff-url]

Four direct dependencies, six in the whole tree, deliberately. `bunx` cold start is the product,
and nobody wants to download a dependency graph to delete some slashes.

|                     |                                                                    |
| ------------------- | ------------------------------------------------------------------ |
| Published tarball   | 37 kB                                                              |
| Unpacked            | 119 kB across 9 files, 62 kB of it `dist/`                         |
| Direct dependencies | `typescript`, `tinyglobby`, `ignore`, `picocolors`                 |
| Node                | 20 or newer                                                        |
| Types               | bundled, no `@types/` package                                      |
| Provenance          | every release is published from CI with `npm publish --provenance` |

`typescript` is the big one and it is not negotiable — it is the parser, and it is the entire
reason a `//` inside a template literal survives.

[The Python package](#python) is leaner still — `pathspec` is its only runtime dependency, because
`tokenize`, `ast` and `tomllib` are all in the standard library.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- GETTING STARTED -->

## Getting Started

### Prerequisites

Node 20 or newer for the JavaScript/TypeScript package. Python 3.11 or newer for
[the Python one](#python). That is the entire list.

```sh
node --version
```

### Installation

There is nothing to install. Point it at your repo and find out how bad it is:

```sh
bunx commentless --check      # bun
npx  commentless --check      # npm
pnpm dlx commentless --check  # pnpm
uvx  commentless --check      # Python codebases
```

Ready to commit to the bit:

```sh
bun add -d commentless
npm  i  -D commentless
```

Then, in `package.json`:

```jsonc
{
  "scripts": {
    "comments:remove": "commentless --write",
    "comments:check": "commentless --check --reporter github",
  },
}
```

### commentless init

Do not hand-write the config. `init` scans the repo, writes a `commentless.config.json`, and
**baselines `maxAllowed` to the number of comments you have right now** — so the gate you just
added passes on the very first run, and you ratchet it down at your own pace instead of opening a
4 000-line PR nobody will review.

```console
$ commentless init
✔ Wrote commentless.config.json

312 files scanned, 41 strippable comments found.
maxAllowed is set to 41 so the gate passes today. Ratchet it down as you
move those explanations into test names — that is the whole point.

These scripts are missing from package.json:
  comments:remove: bunx -y commentless@0.2.0 --write
  comments:check: bunx -y commentless@0.2.0 --check --reporter github

Add them? [Y/n] y

✔ Added to package.json:
  comments:remove: bunx -y commentless@0.2.0 --write
  comments:check: bunx -y commentless@0.2.0 --check --reporter github

Next:
  1. run comments:check in CI on every pull request
  2. run comments:remove when you are ready to delete them
```

It asks before touching `package.json`, shows you the exact lines first, never overwrites a script
you already have, and keeps your indentation. If `commentless` is a devDependency it writes the
bare binary; if you ran it through `bunx` it writes a pinned `bunx` command, because that is the
one that will actually work.

| Flag              | Effect                                                                        |
| ----------------- | ----------------------------------------------------------------------------- |
| `--strict`        | Set `maxAllowed` to `0` instead of today's count. For greenfield repos.       |
| `--force`         | Overwrite an existing config. Without it, `init` exits 2 and touches nothing. |
| `--config <path>` | Write somewhere other than `./commentless.config.json`.                       |
| `--scripts`       | Add the npm scripts without asking. Use this in a script or a Dockerfile.     |
| `--no-scripts`    | Never add them. Also the default when there is no TTY to ask on.              |

`--ext` and `--ignore` are carried into the written file, so
`commentless init --ext ts,tsx --ignore 'db/generated/**'` gets you something you can commit as-is.
It never writes to your source files — only to the config.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- USAGE EXAMPLES -->

## Usage

```
commentless [paths...] [options]
commentless init [options]
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

| Flag                     | Effect                                                                 |
| ------------------------ | ---------------------------------------------------------------------- |
| `--keep <regex>`         | Keep comments matching this pattern. Repeatable.                       |
| `--no-keep <rule>`       | Turn off one built-in rule. Repeatable. e.g. `--no-keep jsdoc-type`    |
| `--keep-only <list>`     | Enable only these built-in rules. e.g. `--keep-only eslint,typescript` |
| `--no-default-keep`      | Turn off every built-in rule. Live dangerously.                        |
| `--list-keep-rules`      | Print every built-in rule and what it matches, then exit.              |
| `--collapse-blank-lines` | Also trim trailing whitespace and collapse 3+ blank lines.             |

**Output**

| Flag                     | Effect                                                         |
| ------------------------ | -------------------------------------------------------------- |
| `--reporter <name>`      | `pretty` (default), `json`, `github`, `summary`.               |
| `--max-allowed <n>`      | `--check` passes while removable comments are at or under `n`. |
| `--to-test-names <file>` | Draft an `it.todo(...)` per comment into `<file>`. See below.  |
| `-q, --quiet`            | Summary only.                                                  |
| `--no-color`             | Disable colour.                                                |

**Other**

| Flag                | Effect                                                     |
| ------------------- | ---------------------------------------------------------- |
| `--concurrency <n>` | Worker threads. Default `cpus - 1`.                        |
| `--no-cache`        | Skip the clean-file cache.                                 |
| `--config <path>`   | Path to a `commentless.config.json`.                       |
| `--force`           | Overwrite the `--to-test-names` file if it already exists. |

**Exit codes**

| Code | Meaning                                                           |
| ---- | ----------------------------------------------------------------- |
| `0`  | Clean.                                                            |
| `1`  | Comments found under `--check`, or a file could not be processed. |
| `2`  | Bad usage or invalid configuration.                               |

### Comments that survive

Deleting a directive is a bug, not a cleanup. A tool that strips your `// eslint-disable-next-line`
and then hands the build to ESLint is not a tool, it is a practical joke. These are kept by
default:

Every one of these is a named rule you can switch off individually — run `commentless --list-keep-rules` to print this table straight from the binary.

| Rule               | Matches                                                                                                                                       |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `commentless`      | `commentless-keep`, `commentless-keep-next-line`                                                                                              |
| `eslint`           | `eslint-disable*`, `eslint-enable`, `eslint-env`                                                                                              |
| `eslint-globals`   | `/* global … */`, `/* globals … */`                                                                                                           |
| `typescript`       | `@ts-expect-error`, `@ts-ignore`, `@ts-nocheck`, `@ts-check`                                                                                  |
| `triple-slash`     | `/// <reference … />`                                                                                                                         |
| `biome`            | `biome-ignore`                                                                                                                                |
| `prettier`         | `prettier-ignore`                                                                                                                             |
| `oxlint`           | `oxlint-disable`                                                                                                                              |
| `coverage`         | `istanbul ignore`, `c8 ignore`, `v8 ignore`, `node:coverage`                                                                                  |
| `bundler-magic`    | `webpackChunkName:` and friends, `@vite-ignore`                                                                                               |
| `pure-annotation`  | `/* @__PURE__ */`, `@__NO_SIDE_EFFECTS__`, `@__KEY__`                                                                                         |
| `jsx-pragma`       | `@jsx`, `@jsxImportSource`, `@jsxRuntime`, `@jsxFrag`                                                                                         |
| `test-environment` | `@vitest-environment`, `@jest-environment`                                                                                                    |
| `license`          | `@license`, `@preserve`, `SPDX-License-Identifier`                                                                                            |
| `bang`             | any `/*! … */` comment                                                                                                                        |
| `jsdoc-type`       | `@type`, `@satisfies`, `@typedef`, `@template`, `@overload`, `@import` — `.js`/`.jsx`/`.mjs`/`.cjs` only, where they actually drive inference |

Shebangs (`#!/usr/bin/env node`) are not comments in the first place and are always safe.

Disagree with one of them? Every rule is individually switchable, in increasing order of confidence
in your own judgement:

```sh
commentless --no-keep jsdoc-type                   # one rule off
commentless --no-keep eslint --no-keep typescript  # a couple
commentless --keep-only eslint,typescript          # only these two on
commentless --no-default-keep                      # good luck
```

Or in the config, which is where it belongs once you have actually decided:

```json
{ "disableKeep": ["jsdoc-type"] }
```

```json
{ "keepOnly": ["eslint", "typescript"] }
```

A typo in a rule name is a hard error that lists the valid ones, so a fat finger cannot quietly
switch your whole allowlist off.

Add your own with `--keep <regex>` (repeatable) or `keep` in the config. A common pair — "a link is
allowed, an essay is not":

```jsonc
{ "keep": ["https?://", "@(public|internal)\\b"] }
```

**Inline escapes**, for the three comments a year that earn their place:

```ts
// commentless-keep  this one stays, and you will justify it in review
// commentless-keep-next-line
// …and so does this one
// commentless-ignore-file  ← anywhere in the first 4 KB: skip the file entirely
```

### From comments to test names

`--to-test-names <file>` is the migration tool for
[the philosophy](#why-your-comments-belong-in-test-names). It takes every comment it is about to
delete and drafts it as an `it.todo(...)`, grouped into one `describe` per source file, so the
explanations have somewhere to land before the deletion lands.

Pair it with `--check` to look before you leap — nothing under `src/` is touched:

```sh
commentless --check --to-test-names tests/comments.todo.test.ts
```

Given this:

```ts
/**
 * Looks up the current subscription.
 * @param id the user id
 */
export async function plan(id: string) {
  // The billing API answers 200 with an empty body when the user has never
  // subscribed, so we have to null-check before parsing.
  const body = await fetchUser(id);
  if (!body) return null;

  // TODO: handle the grandfathered enterprise tier
  // const legacy = LEGACY_TIERS[body.tier];

  // ----------------------------------------------------------
  // Retry once. Stripe rate-limits at 100rps and we burst past
  // it during the nightly reconcile.
  // ----------------------------------------------------------
  return body.plan;
}
```

you get this:

```ts
import { describe, it } from 'vitest';

describe('src/billing.ts', () => {
  it.todo('looks up the current subscription');
  it.todo(
    'the billing API answers 200 with an empty body when the user has never subscribed, so we have to null-check before parsing'
  );
  it.todo('handle the grandfathered enterprise tier');
  it.todo('retry once');
  it.todo('stripe rate-limits at 100rps and we burst past it during the nightly reconcile');
});
```

Note what happened on the way:

- **Wrapped line comments are rejoined.** A run of `//` lines at the same indent is one claim, so
  it becomes one stub, not five.
- **Sentences are split.** A paragraph explaining three things becomes three stubs, because it was
  always three tests.
- **Prose is trimmed into a test name.** `TODO:`/`FIXME:`/`NOTE:` labels, banner rules, jsdoc
  `@param`/`@returns` lines and the trailing full stop all come off, and a leading capital is
  lowercased so it reads after `it(`.
- **Commented-out code is skipped**, not drafted. `// const legacy = …` is not an edge case
  anybody needs a test for. The summary line tells you how many were dropped.

Then do the actual work: turn each `it.todo` into a real test, deleting the ones that were never
claims worth keeping. When the file is honest, run `commentless --write` and the comments go.

#### Hand the skeleton to an agent

Filling in a hundred `it.todo` stubs is exactly the work you should not be doing by hand, and
[for the reasons in the philosophy](#the-token-argument-since-you-are-going-to-ask) it is work an
agent is unusually good at: every stub names one behaviour, and the file it belongs to is written
on the `describe` above it. Point your coding agent at the draft and paste this:

```text
tests/comments.todo.test.ts is a generated skeleton. Every it.todo in it is a
sentence that used to be a comment in the file named by its describe block.

Work through the skeleton one describe at a time:

1. Read the source file named in the describe block.
2. For each it.todo, decide what it actually claims about that file's
   behaviour, then replace it with a real test that would fail if the claim
   stopped being true. Keep the name — it is the explanation. Reword it only
   to match what you actually asserted.
3. If a stub is not a testable claim about the code (a note to a past
   colleague, a stale aside, a fact about some other system), delete it and
   tell me which ones you deleted and why. Do not invent a test to justify
   keeping one.
4. Do not add explanatory comments to the tests or back into the source. The
   test name is the explanation. That is the whole point of the exercise.

Then run the suite and show me the failures. Do not run `commentless --write`
— I will do that once the tests are green.
```

The last line matters. The stubs are the only surviving copy of those explanations until the tests
are real, and `--write` deletes the originals. Let the agent draft; you decide when the prose is
safe to lose.

The draft is written to the path you name — it will not clobber an existing file without
`--force`, and the check happens _before_ anything is rewritten, so a typo cannot cost you a
`--write`. The import line is picked from your `package.json`: `vitest`, `@jest/globals`,
`bun:test`, or nothing at all when jest globals are in play. Everything else — the report — still
goes to stdout, so `--reporter json` stays parseable; the drafting summary goes to stderr.

> [!TIP]
> There is deliberately no config key for this. It is a one-shot migration aid, not a setting you
> leave on.

### Configuration

`commentless.config.json` in the project root (or any ancestor), or a `"commentless"` key in
`package.json`. Every CLI flag overrides the file.

```json
{
  "ext": ["ts", "tsx"],
  "ignore": ["db/generated/**", ".storybook/**"],
  "keep": ["https?://", "@(public|internal)\\b"],
  "disableKeep": ["jsdoc-type"],
  "collapseBlankLines": true,
  "maxAllowed": 0,
  "reporter": "pretty"
}
```

`keepOnly` is the other half of the pair: `disableKeep` is a subtraction from the built-in set,
`keepOnly` replaces it. Both reject unknown rule names.

The config is JSON on purpose. A `.ts` config would be a file this tool strips the comments out
of, which is the kind of recursion that ruins an afternoon.

### Reporters

Four of them, because a human at a terminal, a CI annotator and a script piping into `jq` want
very different things.

`pretty` (default) — file, line, column, and the head of the offending comment:

```console
• src/billing.ts (3 comments found)
  src/billing.ts:1:1  // The billing API answers 200 with an empty body when the user has n...
  src/billing.ts:5:34  // trailing note nobody reads

✖ 1 file scanned · 3 comments to remove in 1 file, 1 kept · 31ms
```

`github` — workflow commands, so each one lands inline on the PR diff:

```console
::error file=src/billing.ts,line=1,col=1,title=commentless::Remove this comment%3A // The billing…
::notice title=commentless::1 file scanned · 3 comments to remove in 1 file, 1 kept · 123ms
```

`summary` — one line, for a pre-commit hook that should not shout:

```console
1 file scanned · 3 comments to remove in 1 file, 1 kept · 61ms
```

`json` — a versioned, stable shape for scripts and dashboards:

```json
{
  "version": 1,
  "summary": {
    "mode": "check",
    "discovered": 1,
    "parsed": 1,
    "cached": 0,
    "filesWithComments": 1,
    "commentsRemoved": 3,
    "commentsKept": 1,
    "errors": 0,
    "durationMs": 96
  },
  "exitCode": 1,
  "files": [
    {
      "file": "src/billing.ts",
      "changed": true,
      "keptCount": 1,
      "comments": [
        { "line": 1, "column": 1, "kind": "line", "text": "// The billing API answers…" }
      ]
    }
  ]
}
```

The `version` field is there so you can pin against it:
`commentless --check --reporter json | jq '.summary.commentsRemoved'`.

### In CI

`--reporter github` emits workflow annotations, so every offending comment shows up inline on the
PR diff, right where its author can feel something about it.

```yaml
- uses: oven-sh/setup-bun@v2
- run: bunx commentless@0.2.0 . --check --reporter github
```

Scope it to the PR diff instead of the whole repo (needs `fetch-depth: 0`):

```yaml
- uses: actions/checkout@v4
  with: { fetch-depth: 0 }
- run: bunx commentless@0.2.0 . --check --changed --base origin/main --reporter github
```

Adopting on a repo with 2 000 existing comments? Do not fix them in one PR — nobody will review
that. Set a ceiling and ratchet it down:

```sh
commentless --check --max-allowed 2000   # today
commentless --check --max-allowed 1500   # next sprint, after the migration to test names
commentless --check --max-allowed 0      # eventually
```

**Pre-commit:**

```sh
commentless --staged --write
```

### Performance

Measured on a 2 225-file Next.js repository, M-series Mac, 10 worker threads:

| Run                     | Time     |
| ----------------------- | -------- |
| single thread, no cache | 1 012 ms |
| 10 workers, no cache    | 530 ms   |
| 10 workers, warm cache  | 321 ms   |

Where the time does not go:

- **Discovery** uses `git ls-files --cached --others --exclude-standard` inside a repository, so
  `.gitignore` is honoured for free and `node_modules` is never walked.
- **A substring pre-filter** skips the parser entirely for any file with no `//` or `/*` — which
  is most of them, once the tool has done its job.
- **One AST walk** collects comment trivia and JSX comment nodes in a single pass.
- **A clean-file cache** under `node_modules/.cache/commentless` keys on size + mtime, so
  unchanged files are skipped outright. Cache it with `actions/cache`, or disable with
  `--no-cache`.

### Programmatic API

```ts
import { scanSource, stripComments, resolveKeepRules, run } from 'commentless';

const keep = resolveKeepRules({ userPatterns: ['https?://'] });
const { removable, kept } = scanSource(source, { fileName: 'a.tsx', keep });
const output = stripComments(source, removable);

const result = await run({ cwd: process.cwd(), mode: 'check', extensions: ['ts', 'tsx'], keep });
process.exitCode = result.exitCode;
```

### What it does to your diff

Removing a comment removes the whitespace it owned, and nothing else:

```diff
-// a note
 const a = 1;
-const b = 2; // trailing
+const b = 2;
```

A comment alone on its line takes the line with it. A trailing comment takes the space in front of
it. Every other line stays byte-identical — CRLF endings, BOM and existing blank runs included —
unless you ask for `--collapse-blank-lines`. Running it twice is a no-op. Your reviewer will
thank you by saying nothing, which is how reviewers say thank you.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- FAQ -->

## FAQ

**Does it delete my JSDoc?**
In `.ts`/`.tsx`, yes — prose JSDoc is prose, and your types are already in the signature. In the
`.js` family, `@type`, `@typedef`, `@satisfies`, `@template`, `@overload` and `@import` survive,
because there they genuinely drive inference. That is the `jsdoc-type` rule; switch it off with
`--no-keep jsdoc-type` if you want it gone everywhere, or add
`--keep '@(param|returns)'` if you want more of it kept.

**What about `// TODO`?**
Deleted. A TODO in source is a task nobody is assigned to and no board is tracking. Move it to an
issue, where it has an owner — or to an `it.todo(...)`, which is what
[`--to-test-names`](#from-comments-to-test-names) drafts for you. If you disagree, `--keep 'TODO'`
— it is one flag and no hard
feelings.

**Is it safe to run twice?**
Yes. The second run is a no-op, and the clean-file cache makes it a fast one:

```console
$ commentless . --write
✔ 4 files scanned · 4 comments removed in 4 files · 83ms
$ commentless . --write
✔ 4 files scanned, 4 cached · 0 comments removed in 0 files · 34ms
```

**Will it wreck my line endings, or my BOM?**
No. CRLF stays CRLF, a BOM stays a BOM, and every line that did not own a comment comes out
byte-identical. Blank runs are left alone unless you ask for `--collapse-blank-lines`.

**Can I adopt it on a repo with 2 000 comments?**
That is what `commentless init` and `--max-allowed` are for. `init` baselines the gate to today's
count so it passes on the first run, then you ratchet it down. Nobody has to review a 4 000-line
deletion PR.

**Does it work in a monorepo?**
Yes. Config resolves from the working directory upward, so a package inherits the root
`commentless.config.json` unless it ships its own. Point it at paths (`commentless packages/api`)
to scope a run.

**How do I keep one specific comment?**
`// commentless-keep` on the comment, or `// commentless-keep-next-line` above it. To skip an
entire file, put `// commentless-ignore-file` anywhere in its first 4 KB.

**Does it need a `tsconfig.json`?**
No. It parses each file standalone with the TypeScript compiler — no program, no type-checking, no
project graph. That is why it is fast and why it works on a loose script.

**Is it an ESLint plugin?**
Not yet — [it is on the roadmap](#roadmap). Today it is a CLI and a small programmatic API, which
is what you want in CI anyway.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- PYTHON -->

## Python

Same tool, same convention, a separate package on PyPI.

```sh
uvx commentless init     # or: pipx install commentless
uvx commentless --check
uvx commentless
```

Every flag on this page works there: `--check`, `--write`, `--dry-run`, `--staged`, `--changed`,
`--base`, `--ext`, `--ignore`, `--ignore-file`, `--no-gitignore`, `--list-files`, `--keep`,
`--no-keep`, `--keep-only`, `--no-default-keep`, `--list-keep-rules`, `--collapse-blank-lines`,
`--reporter`, `--max-allowed`, `--to-test-names`, `--quiet`, `--verbose`, `--no-color`,
`--concurrency`, `--no-cache`, `--config`, and `init --force --strict`. Same four reporters, same
three exit codes, same `commentless-keep` / `commentless-keep-next-line` / `commentless-ignore-file`
escapes.

**Full reference: [`packages/python/README.md`](packages/python/README.md).** What follows is only
what is _different_, because Python is not JavaScript.

### Docstrings are opt-in

A `#` comment is inert. A docstring is a runtime value — `doctest` runs the `>>>` examples,
FastAPI turns it into an OpenAPI description, Sphinx and `help()` render it, `argparse` uses a
module docstring as its epilog. So `commentless` never touches docstrings unless you pass
`--docstrings` (or set `docstrings = true`).

When you do opt in, three safety rules still hold the line:

| Rule             | What it protects                                                                                                                                                                  |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `sole-statement` | A docstring that is the only statement in a class or function body — `Protocol` methods, `@overload` stubs, abstract methods. Deleting it would leave a body that does not parse. |
| `inline`         | A docstring sharing its line with other code, like `"""Doc."""; x = 1`.                                                                                                           |
| `doctest`        | Any docstring containing a `>>>` example. Deleting it would delete a test.                                                                                                        |

The output is always still valid Python. That invariant is a test, not a hope.

### A Python keep-rule vocabulary

19 rules instead of 16, because Python's directive comments are its own:

| Rule           | Matches                                                 |
| -------------- | ------------------------------------------------------- |
| `commentless`  | `# commentless-keep`, `# commentless-keep-next-line`    |
| `noqa`         | `# noqa`, `# noqa: E501` — flake8, ruff, vulture        |
| `ruff`         | `# ruff: isort: on` and friends                         |
| `mypy`         | `# mypy: disallow-untyped-defs`                         |
| `type-ignore`  | `# type: ignore`, `# type: ignore[arg-type]`            |
| `type-comment` | PEP 484 type comments — `# type: List[int]`             |
| `pyright`      | `# pyright: ignore`, `# pyright: strict`                |
| `pylint`       | `# pylint: disable`, `enable`, `skip-file`              |
| `pytype`       | `# pytype: disable`, `skip-file`                        |
| `pragma`       | `# pragma: no cover`, `no branch`, `allowlist secret`   |
| `bandit`       | `# nosec`                                               |
| `fmt`          | `# fmt: off`, `# fmt: on`, `# fmt: skip`                |
| `isort`        | `# isort: skip`, `skip_file`, `off`, `on`, `split`      |
| `yapf`         | `# yapf: disable`, `# yapf: enable`                     |
| `coding`       | PEP 263 encoding cookie, on line 1 or 2 only            |
| `cython`       | `# cython:` and `# distutils:` build directives         |
| `license`      | `@license`, `@preserve`, `SPDX-License-Identifier`      |
| `noinspection` | `# noinspection` (PyCharm)                              |
| `doctest`      | Docstrings containing a `>>>` example (docstrings only) |

Shebangs are handled structurally, not by a rule, so they are never at risk.

### `--collapse-blank-lines` stops at two

PEP 8 wants two blank lines between top-level definitions. The JS implementation collapses runs of
three-or-more newlines down to one blank line; the Python one stops at two, so it will not fight
`black` or `ruff format`.

### Test stubs are pytest or unittest

`--to-test-names` has no `it.todo` to lean on, so it drafts a class per source file and a skipped
test per sentence:

```python
import pytest


class TestSrcCache:
    @pytest.mark.skip(reason="todo: bails out when the cache is cold")
    def test_bails_out_when_the_cache_is_cold(self) -> None: ...
```

The sentence lives in both the method name and the skip reason, so `pytest -rs` prints it back to
you. If the project does not use pytest — checked against `pyproject.toml`, `pytest.ini`,
`tox.ini`, `setup.cfg`, `conftest.py` and `requirements*.txt` — it falls back to
`unittest.TestCase` with `@unittest.skip`, which runs anywhere.

### Config lives in `pyproject.toml` too

`commentless.config.json` works exactly as it does in JS, and is checked first. Failing that,
`[tool.commentless]` in `pyproject.toml` is read instead:

```toml
[tool.commentless]
ignore = ["migrations/**"]
docstrings = false
maxAllowed = 0
```

Keys are camelCase so one schema covers both languages, but snake_case aliases (`max_allowed`,
`collapse_blank_lines`, …) are accepted.

### `init` offers a pre-commit hook, not npm scripts

There is no `package.json` to write scripts into, so `commentless init` offers the Python
equivalent — a hook in `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: commentless
        name: commentless
        entry: commentless --check
        language: python
        additional_dependencies: ['commentless==0.1.0']
        types: [python]
```

`--pre-commit` adds it without asking, `--no-pre-commit` never does, and interactively it asks.
`init --pyproject` writes the config as `[tool.commentless]` instead of a JSON file.

### The pool threshold is different

`tokenize` is pure Python and process startup is not free, so the Python implementation only
reaches for a process pool at 200+ files **and** 1 MB+ of pending source. Below that, one process
is faster. The JS implementation uses worker threads, which are cheap enough to spin up on file
count alone.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- ROADMAP -->

## Roadmap

- [x] AST-accurate detection for the whole JS/TS family
- [x] Directive allowlist so CI does not eat itself
- [x] `--check` mode with GitHub inline annotations
- [x] Worker pool + clean-file cache
- [x] `--max-allowed` ratchet for gradual adoption
- [x] Per-rule `--no-keep` / `--keep-only` control over the built-in allowlist
- [x] `commentless init` — a config baselined to the repo's current comment count
- [x] Publish to npm automatically on every version bump landing on `main`
- [x] `--to-test-names` — draft `it(...)` stubs from the comments it is about to delete
- [x] A Python implementation on PyPI, sharing the config schema and the flag surface
- [ ] Vue SFC and Svelte support
- [ ] An ESLint rule, for teams that want the squiggle in the editor
- [ ] A published pre-commit hook repo, so the Python hook is not a `repo: local` block
- [ ] Go and Rust, once the shared convention has proven itself across two languages

See the [open issues][issues-url] for the full list of proposed features and known issues.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CONTRIBUTING -->

## Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and
create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull
request. You can also simply open an issue with the tag "enhancement".

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'feat: add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

The repo holds one package per language under `packages/`. They share a README, an issue tracker
and a convention — nothing else. Pick the one you are changing.

```sh
bun install                # JavaScript / TypeScript, from the repo root
bun run --cwd packages/js test    # 272 tests
bun run ci:js              # lint, typecheck, test, build, and the tool run against its own source
```

```sh
cd packages/python         # Python
uv sync
uv run pytest tests        # 373 tests
uv run ruff check . && uv run ruff format --check .
uv run mypy src tests
uv run commentless . --check --docstrings
```

`bun run ci` from the repo root runs both, plus `prettier --check` over everything.

If you add a flag, a keep rule or a config key to one implementation, open an issue for the other
one. Drift between them is the failure mode this layout exists to prevent.

Two house rules, both self-explanatory given the above:

- **New behaviour needs a test whose name is the explanation.** If you were about to write a
  comment about it, that sentence is the test name. See
  [the philosophy](#why-your-comments-belong-in-test-names).
- **New keep rules go in `src/core/keep.ts`** and get a row in the `load-bearing comments survive`
  table in `tests/keep.test.ts`. Rules that only matter in JavaScript take an `extensions` list.

Yes, the repo passes its own `--check`. It would be a bit much otherwise.

### Top contributors

<a href="https://github.com/barad-side-hustle/commentless/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=barad-side-hustle/commentless" alt="contrib.rocks image" />
</a>

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- LICENSE -->

## License

Distributed under the MIT License. See `LICENSE` for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CONTACT -->

## Contact

Alon Barad — [@alon710](https://github.com/alon710)

Project Link: [https://github.com/barad-side-hustle/commentless](https://github.com/barad-side-hustle/commentless)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- ACKNOWLEDGMENTS -->

## Acknowledgments

- [TypeScript Compiler API](https://github.com/microsoft/TypeScript/wiki/Using-the-Compiler-API) — for knowing what a comment is
- [tinyglobby](https://github.com/SuperchupuDev/tinyglobby)
- [ignore](https://github.com/kaelzhang/node-ignore)
- [picocolors](https://github.com/alexeyraspopov/picocolors)
- [Best-README-Template](https://github.com/othneildrew/Best-README-Template)
- Every comment that said `// this should never happen` immediately above the thing that happened

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->

[npm-shield]: https://img.shields.io/npm/v/commentless.svg?style=flat-square&color=CB3837&logo=npm&logoColor=white
[npm-url]: https://www.npmjs.com/package/commentless
[downloads-shield]: https://img.shields.io/npm/dm/commentless.svg?style=flat-square&color=CB3837&label=downloads%2Fmonth
[downloads-url]: https://www.npmjs.com/package/commentless
[build-shield]: https://img.shields.io/github/actions/workflow/status/barad-side-hustle/commentless/ci.yml?branch=main&style=flat-square&label=CI
[build-url]: https://github.com/barad-side-hustle/commentless/actions/workflows/ci.yml
[size-shield]: https://img.shields.io/npm/unpacked-size/commentless?style=flat-square&color=4c1&label=unpacked
[size-url]: https://www.npmjs.com/package/commentless?activeTab=code
[node-version-shield]: https://img.shields.io/node/v/commentless?style=flat-square&color=5FA04E&logo=nodedotjs&logoColor=white
[node-version-url]: https://nodejs.org/
[pypi-shield]: https://img.shields.io/pypi/v/commentless.svg?style=flat-square&color=3775A9&logo=pypi&logoColor=white&label=PyPI
[pypi-url]: https://pypi.org/project/commentless/
[python-version-shield]: https://img.shields.io/pypi/pyversions/commentless?style=flat-square&color=3775A9&logo=python&logoColor=white
[python-version-url]: https://www.python.org/
[python-shield]: https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white
[python-url]: https://www.python.org/
[uv-shield]: https://img.shields.io/badge/uv-DE5FE9?style=for-the-badge&logo=uv&logoColor=white
[uv-url]: https://docs.astral.sh/uv/
[ruff-shield]: https://img.shields.io/badge/Ruff-D7FF64?style=for-the-badge&logo=ruff&logoColor=black
[ruff-url]: https://docs.astral.sh/ruff/
[license-shield]: https://img.shields.io/github/license/barad-side-hustle/commentless.svg?style=flat-square
[license-url]: https://github.com/barad-side-hustle/commentless/blob/main/LICENSE
[stars-shield]: https://img.shields.io/github/stars/barad-side-hustle/commentless.svg?style=flat-square&logo=github
[stars-url]: https://github.com/barad-side-hustle/commentless/stargazers
[issues-url]: https://github.com/barad-side-hustle/commentless/issues
[typescript-shield]: https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white
[typescript-url]: https://www.typescriptlang.org/
[node-shield]: https://img.shields.io/badge/Node.js-5FA04E?style=for-the-badge&logo=nodedotjs&logoColor=white
[node-url]: https://nodejs.org/
[vitest-shield]: https://img.shields.io/badge/Vitest-6E9F18?style=for-the-badge&logo=vitest&logoColor=white
[vitest-url]: https://vitest.dev/
[bun-shield]: https://img.shields.io/badge/Bun-000000?style=for-the-badge&logo=bun&logoColor=white
[bun-url]: https://bun.sh/
