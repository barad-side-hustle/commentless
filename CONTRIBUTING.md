# Contributing

```bash
bun install
bun run test        # vitest
bun run ci          # lint, format, typecheck, test, build, selfcheck
```

`bun run build` must run before `bun run test` if you want the worker-pool tests to
execute — they are skipped when `dist/worker.js` is absent, and the single-threaded
path is covered either way.

## Adding a keep rule

Every rule lives in `src/core/keep.ts` as a `{ name, test }` pair, and every rule needs a
case in the `load-bearing comments survive` table in `tests/keep.test.ts`. Rules that only
matter in JavaScript take an `extensions` list.

## Releasing

1. Bump `version` in `package.json` and the `VERSION` constant in `src/cli.ts`.
2. `git tag v<version> && git push --tags`.
3. The release workflow verifies the tag against `package.json` and publishes with provenance.
