# Contributing

This repo holds one `commentless` implementation per language under `packages/`. They are
separate packages on separate registries with separate release cadences. What they share is a
convention: the same flags, the same config schema, the same keep-rule vocabulary, the same four
reporters and the same three exit codes.

```
packages/js/       commentless on npm     — JavaScript / TypeScript
packages/python/   commentless on PyPI    — Python
```

## Working on the JavaScript / TypeScript package

```bash
bun install                       # from the repo root — it is a bun workspace
bun run --cwd packages/js test    # vitest
bun run ci:js                     # lint, typecheck, test, build, selfcheck
```

`bun run --cwd packages/js build` must run before the tests if you want the worker-pool tests to
execute — they are skipped when `dist/worker.js` is absent, and the single-threaded path is
covered either way.

## Working on the Python package

```bash
cd packages/python
uv sync
uv run pytest tests        # 373 tests
uv run ruff check . && uv run ruff format --check .
uv run mypy src tests
uv run commentless . --check --docstrings   # selfcheck
```

## Everything at once

```bash
bun run ci        # prettier over the repo, then ci:js, then ci:python
```

`ci:python` needs `uv` on your PATH.

## House rules

**If you were about to write a comment, write a test name instead.** That is the whole premise of
this project, and the repo holds itself to it — both CI jobs end by running the CLI against their
own source with `--check`. The Python job passes `--docstrings` too, so that package has no
docstrings either. An edge case worth explaining is an edge case worth asserting; see
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

```python
def test_removes_a_trailing_comment_and_the_space_before_it(self) -> None: ...
```

## Keeping the two implementations honest

If you add a flag, a config key, a reporter, an exit code or an inline escape to one package, open
an issue for the other. Drift is the failure mode this layout exists to prevent.

Deliberate divergences are allowed, but they must be documented in both READMEs. The ones that
exist today:

| Divergence                                                                                            | Why                                                             |
| ----------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| Python has `--docstrings`, off by default                                                             | A docstring is a runtime value; a `#` comment is not.           |
| Python's `--collapse-blank-lines` stops at two blank lines                                            | PEP 8 wants two between top-level definitions.                  |
| Python's `init` offers a pre-commit hook, JS offers npm scripts                                       | There is no `package.json` to write into.                       |
| Python reads `[tool.commentless]` from `pyproject.toml`, JS reads `"commentless"` from `package.json` | Each language's native config home.                             |
| Python drafts `@pytest.mark.skip` / `@unittest.skip`, JS drafts `it.todo`                             | Python has no `it.todo`, and test names must be identifiers.    |
| Python reaches for a process pool later than JS reaches for worker threads                            | `tokenize` is pure Python and processes cost more than threads. |

## Adding a keep rule

**JavaScript:** rules live in `packages/js/src/core/keep.ts` as a `{ name, test }` pair, and every
rule needs a case in the `load-bearing comments survive` table in `packages/js/tests/keep.test.ts`.
Rules that only matter in JavaScript take an `extensions` list.

**Python:** rules live in `packages/python/src/commentless/keep.py` as a `KeepRule`, need an entry
in `KEEP_RULE_DESCRIPTIONS`, and need a case in the parametrised
`test_keeps_directive_comments` table in `packages/python/tests/test_keep.py`. A rule can be
restricted to a comment kind with `kinds=("docstring",)` or to the top of the file with
`max_line=2`.

A rule earns its place by being _machinery_ — something a tool reads — not by being useful prose.
`eslint-disable` and `# type: ignore` are machinery. `@deprecated` and `# HACK` are prose.

## Releasing

Releases are automatic and independent per package.

**npm.** Bump `version` in `packages/js/package.json` **and** `VERSION` in
`packages/js/src/version.ts` (the workflow fails the release if they disagree), then merge to
`main`. `release-js.yml` asks npm whether that version exists; if it does not, it runs every gate
and publishes with provenance, then cuts a `v<version>` GitHub release. Needs an `NPM_TOKEN`
repository secret with publish rights.

**PyPI.** Bump `version` in `packages/python/pyproject.toml` **and** `VERSION` in
`packages/python/src/commentless/version.py` (same check), then merge to `main`.
`release-python.yml` asks PyPI whether that version exists; if it does not, it runs every gate,
builds with `uv build` and publishes, then cuts a `python-v<version>` GitHub release.

So a normal push to `main` costs two registry lookups, and a version bump costs one full release.

### PyPI auth is OIDC, and it is name-matched

There is no PyPI secret. Publishing uses
[trusted publishing](https://docs.pypi.org/trusted-publishers/), and PyPI matches five values
against the OIDC claim GitHub mints for the job:

|               |                      |
| ------------- | -------------------- |
| Owner         | `barad-side-hustle`  |
| Repository    | `commentless`        |
| Workflow file | `release-python.yml` |
| Environment   | `pypi`               |
| Project       | `commentless`        |

**Renaming any of them breaks publishing**, with an error that does not say so clearly. If you
rename the workflow file, move the repo or rename the environment, update the trusted publisher
at <https://pypi.org/manage/project/commentless/settings/publishing/> in the same change.

The `pypi` GitHub environment is restricted to the `main` branch, so a workflow file altered on a
feature branch cannot reach the publish step even via `workflow_dispatch`.
