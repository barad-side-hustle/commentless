<a id="readme-top"></a>

<!-- PROJECT SHIELDS -->

[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]
[![npm][npm-shield]][npm-url]

<!-- PROJECT LOGO -->
<br />
<div align="center">

<h1 align="center">commentless</h1>

  <p align="center">
    Your code does not need a narrator.
    <br />
    Strip comments from JavaScript and TypeScript with a real parser, keep the ones that
    actually do work, and fail CI when someone sneaks a new one in.
    <br />
    <br />
    <a href="#usage"><strong>Explore the flags »</strong></a>
    <br />
    <br />
    <a href="#why-your-comments-belong-in-test-names">The philosophy</a>
    &middot;
    <a href="https://github.com/barad-side-hustle/commentless/issues/new?labels=bug">Report Bug</a>
    &middot;
    <a href="https://github.com/barad-side-hustle/commentless/issues/new?labels=enhancement">Request Feature</a>
  </p>
</div>

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
        <li><a href="#configuration">Configuration</a></li>
        <li><a href="#in-ci">In CI</a></li>
        <li><a href="#performance">Performance</a></li>
        <li><a href="#programmatic-api">Programmatic API</a></li>
      </ul>
    </li>
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

Four dependencies, deliberately. `bunx` cold start is the product, and nobody wants to download a
dependency tree to delete some slashes.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- GETTING STARTED -->

## Getting Started

### Prerequisites

Node 20 or newer. That is the entire list.

```sh
node --version
```

### Installation

There is nothing to install. Point it at your repo and find out how bad it is:

```sh
bunx commentless --check      # bun
npx  commentless --check      # npm
pnpm dlx commentless --check  # pnpm
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

### In CI

`--reporter github` emits workflow annotations, so every offending comment shows up inline on the
PR diff, right where its author can feel something about it.

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
- [ ] `--to-test-names` — draft `it(...)` stubs from the comments it is about to delete
- [ ] Vue SFC and Svelte support
- [ ] An ESLint rule, for teams that want the squiggle in the editor

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

```sh
bun install
bun run test   # 137 tests
bun run ci     # lint, format, typecheck, test, build, and the tool run against its own source
```

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

[contributors-shield]: https://img.shields.io/github/contributors/barad-side-hustle/commentless.svg?style=for-the-badge
[contributors-url]: https://github.com/barad-side-hustle/commentless/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/barad-side-hustle/commentless.svg?style=for-the-badge
[forks-url]: https://github.com/barad-side-hustle/commentless/network/members
[stars-shield]: https://img.shields.io/github/stars/barad-side-hustle/commentless.svg?style=for-the-badge
[stars-url]: https://github.com/barad-side-hustle/commentless/stargazers
[issues-shield]: https://img.shields.io/github/issues/barad-side-hustle/commentless.svg?style=for-the-badge
[issues-url]: https://github.com/barad-side-hustle/commentless/issues
[license-shield]: https://img.shields.io/github/license/barad-side-hustle/commentless.svg?style=for-the-badge
[license-url]: https://github.com/barad-side-hustle/commentless/blob/main/LICENSE
[npm-shield]: https://img.shields.io/npm/v/commentless.svg?style=for-the-badge
[npm-url]: https://www.npmjs.com/package/commentless
[typescript-shield]: https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white
[typescript-url]: https://www.typescriptlang.org/
[node-shield]: https://img.shields.io/badge/Node.js-5FA04E?style=for-the-badge&logo=nodedotjs&logoColor=white
[node-url]: https://nodejs.org/
[vitest-shield]: https://img.shields.io/badge/Vitest-6E9F18?style=for-the-badge&logo=vitest&logoColor=white
[vitest-url]: https://vitest.dev/
[bun-shield]: https://img.shields.io/badge/Bun-000000?style=for-the-badge&logo=bun&logoColor=white
[bun-url]: https://bun.sh/
