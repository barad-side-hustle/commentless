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

Releases are automatic. Bump `version` in `package.json` **and** the `VERSION` constant in
`src/cli.ts` (the workflow fails the release if they disagree), then merge to `main`.

The release workflow asks npm whether that version already exists. If it does, it does nothing.
If it does not, it runs every gate — lint, format, typecheck, build, test, and the CLI against
its own source — then publishes with provenance and cuts a GitHub release. So a normal push to
`main` costs one `npm view` call, and a version bump costs a full release.

This needs an `NPM_TOKEN` repository secret with publish rights.
