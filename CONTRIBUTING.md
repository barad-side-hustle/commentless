# Contributing

```bash
bun install
bun run test        # vitest
bun run ci          # lint, format, typecheck, test, build, selfcheck
```

`bun run build` must run before `bun run test` if you want the worker-pool tests to
execute — they are skipped when `dist/worker.js` is absent, and the single-threaded
path is covered either way.

## House rules

**If you were about to write a comment, write a test name instead.** That is the whole
premise of this project, and the repo holds itself to it — `bun run ci` ends by running
the CLI against its own source with `--check`. An edge case worth explaining is an edge
case worth asserting; see
[Why your comments belong in test names](./README.md#why-your-comments-belong-in-test-names).

Bad:

```ts
// Trailing comments must not eat the code in front of them, so we only
// consume horizontal whitespace backwards from the comment start.
```

Good:

```ts
it('removes a trailing comment without touching the code before it', ...)
```

## Adding a keep rule

Every rule lives in `src/core/keep.ts` as a `{ name, test }` pair, and every rule needs a
case in the `load-bearing comments survive` table in `tests/keep.test.ts`. Rules that only
matter in JavaScript take an `extensions` list.

A rule earns its place by being _machinery_ — something a tool reads — not by being useful
prose. `eslint-disable` is machinery. `@deprecated` is prose.

## Releasing

1. Bump `version` in `package.json` and the `VERSION` constant in `src/cli.ts`.
2. `git tag v<version> && git push --tags`.
3. The release workflow verifies the tag against `package.json` and publishes with provenance.
