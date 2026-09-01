<div align="center">

<h1 align="center">commentless</h1>

  <p align="center">
    <strong>Your code does not need a narrator.</strong>
    <br />
    Strip comments from Python with a real tokenizer, keep the ones that
    actually do work, and fail CI when someone sneaks a new one in.
  </p>

[![PyPI version](https://img.shields.io/pypi/v/commentless?style=for-the-badge&logo=pypi&logoColor=white&color=3775A9)](https://pypi.org/project/commentless/)
[![Python](https://img.shields.io/pypi/pyversions/commentless?style=for-the-badge&logo=python&logoColor=white)](https://pypi.org/project/commentless/)
[![CI](https://img.shields.io/github/actions/workflow/status/barad-side-hustle/commentless/ci.yml?style=for-the-badge&label=CI)](https://github.com/barad-side-hustle/commentless/actions/workflows/ci.yml)
[![License](https://img.shields.io/pypi/l/commentless?style=for-the-badge)](https://github.com/barad-side-hustle/commentless/blob/main/LICENSE)

</div>

## TL;DR

```sh
uvx commentless init     # write a config baselined to today's comment count
uvx commentless --check  # exit 1 if a comment sneaks in — this is your CI gate
uvx commentless          # delete them
```

- **It deletes comments.** Not with a regex — with `tokenize`, so a `#` inside a string, an
  f-string, or a triple-quoted block is text, not a casualty.
- **It keeps the ones that do work.** `# noqa`, `# type: ignore`, `# pragma: no cover`,
  `# fmt: off`, `# nosec`, PEP 263 encoding cookies, shebangs, SPDX headers. All 19 rules are
  named and individually switchable — `--no-keep noqa`, `--keep-only noqa,type-ignore`.
- **It leaves docstrings alone until you ask.** A docstring is a runtime value. `--docstrings`
  opts in; see [Docstrings](#docstrings).
- **It fails CI.** `--check --reporter github` annotates every offending comment inline on the PR
  diff. `--max-allowed <n>` lets you adopt gradually instead of in one 4 000-line PR.
- **The point isn't tidiness.** A comment explaining an edge case is an unverified claim that
  nothing breaks when it goes stale. Write it as a test name instead: same sentence, but it runs.
  `--to-test-names` drafts the stubs for you.

This is the Python implementation. There is a
[JavaScript/TypeScript one](https://github.com/barad-side-hustle/commentless/tree/main/packages/js)
in the same repo, with the same flags, the same config schema and the same exit codes.

## Install

```sh
uv tool install commentless     # or: pipx install commentless
uvx commentless --help          # or run it without installing
```

Requires Python 3.11+ to *run*. It reads any Python your interpreter can tokenize, so run it on a
recent interpreter if your codebase uses recent syntax.

## See it work

```python
# src/cache.py

#!/usr/bin/env python3
"""In-memory cache with a cold-start guard."""
import time  # noqa: F401


# Bails out when the cache is cold. Redis returns None on a miss, not an
# error, so we cannot tell "empty" from "down" without the extra probe.
def get(key):
    """Return the cached value, or None."""
    # TODO: collapse these two round trips
    value = redis.get(key)          # pragma: no cover
    if value is None:
        return None
    return value
```

```sh
$ commentless --check
• src/cache.py (3 comments found)
  src/cache.py:6:1   # Bails out when the cache is cold. Redis returns None on a miss, ...
  src/cache.py:10:5  # TODO: collapse these two round trips

✖ 1 file scanned · 3 comments to remove in 1 file, 3 kept · 11ms
  Run `commentless --write` to remove them, or keep one with `commentless-keep`.
```

The shebang, the encoding cookie, `# noqa: F401` and `# pragma: no cover` all survive. So does
every docstring, because `--docstrings` was not passed.

## Docstrings

A `#` comment is inert. A docstring is not — it is a string expression bound to `__doc__`, and
things read it at runtime:

- `doctest` executes the `>>>` examples in it
- FastAPI turns it into the OpenAPI `description` for an endpoint
- Sphinx, `pydoc` and `help()` render it
- `argparse` uses a module docstring as its epilog
- Some libraries dispatch on it

So `commentless` never touches docstrings unless you pass `--docstrings` (or set
`docstrings = true` in config). When you do, three safety rules still apply:

| Rule | What it protects |
| --- | --- |
| `sole-statement` | A docstring that is the *only* statement in a class or function body. Deleting it would leave a body that does not parse, so it stays. This is what covers `Protocol` methods, `@overload` stubs and abstract methods. |
| `inline` | A docstring that shares its line with other code — `"""Doc."""; x = 1`. Removing it would leave a fragment. |
| `doctest` | Any docstring containing a `>>>` example. Deleting it would delete a test. |

Everything else — module, class and function docstrings with a real body after them — is fair
game. The output is always still valid Python; that invariant is covered by tests.

## Usage

```
commentless [paths...] [options]
commentless init [options]
```

### Mode

| Flag | Effect |
| --- | --- |
| `--check` | Report only, never write. Exit 1 if a comment would be removed. |
| `--write` | Rewrite files in place. The default when `--check` is absent. |
| `--dry-run` | Report what `--write` would do, write nothing. Always exits 0. |

### Scope

| Flag | Effect |
| --- | --- |
| `--staged` | Only files staged in git. |
| `--changed` | Only files changed against `--base`. |
| `--base <ref>` | Base ref for `--changed` (default: `origin/HEAD`, then `main`). |
| `--ext <list>` | Comma-separated extensions (default: `py,pyi`). |
| `--ignore <glob>` | Gitignore-syntax pattern to skip. Repeatable. |
| `--ignore-file <path>` | Ignore file to read (default: `.commentlessignore`). |
| `--no-gitignore` | Stop honouring `.gitignore`. |
| `--list-files` | Print the resolved file list and exit. |

`.git`, `node_modules`, `__pycache__`, `.venv`, `venv`, `.tox`, `.nox`, `.eggs`, `site-packages`
and the `.mypy_cache` / `.pytest_cache` / `.ruff_cache` directories are always skipped.

### Comments to keep

| Flag | Effect |
| --- | --- |
| `--keep <regex>` | Keep comments matching this pattern. Repeatable. |
| `--no-keep <rule>` | Turn off one built-in rule. Repeatable. |
| `--keep-only <list>` | Enable only these built-in rules, comma-separated. |
| `--no-default-keep` | Turn off every built-in rule. |
| `--list-keep-rules` | Print the built-in rules and what each one matches. |
| `--collapse-blank-lines` | Trim trailing whitespace and collapse runs of 3+ blank lines to 2. |

`--collapse-blank-lines` stops at **two** blank lines, not one, because that is what PEP 8 wants
between top-level definitions. It will not fight `black` or `ruff format`.

### Output

| Flag | Effect |
| --- | --- |
| `--reporter <name>` | `pretty` \| `json` \| `github` \| `summary` (default: `pretty`). |
| `--max-allowed <n>` | `--check` passes while removable comments are at or under `n`. |
| `--to-test-names <file>` | Draft a skipped test stub per comment into `<file>`. |
| `-q, --quiet` | Summary only. |
| `-v, --verbose` | Include kept-comment counts. |
| `--no-color` | Disable colour. |

### Other

| Flag | Effect |
| --- | --- |
| `--docstrings` | Also strip module, class and function docstrings. |
| `--concurrency <n>` | Worker processes (default: cpus − 1). |
| `--no-cache` | Skip the clean-file cache. |
| `--config <path>` | Path to a `commentless.config.json` or a `pyproject.toml`. |

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Clean. |
| `1` | Comments found under `--check`, or a file could not be processed. |
| `2` | Bad usage or invalid configuration. |

## Comments that survive

```sh
$ commentless --list-keep-rules
```

| Rule | Matches |
| --- | --- |
| `commentless` | `# commentless-keep`, `# commentless-keep-next-line` |
| `noqa` | `# noqa`, `# noqa: E501` — flake8, ruff, vulture |
| `ruff` | `# ruff: isort: on` and friends |
| `mypy` | `# mypy: disallow-untyped-defs` |
| `type-ignore` | `# type: ignore`, `# type: ignore[arg-type]` |
| `type-comment` | PEP 484 type comments — `# type: List[int]` |
| `pyright` | `# pyright: ignore`, `# pyright: strict` |
| `pylint` | `# pylint: disable`, `enable`, `skip-file` |
| `pytype` | `# pytype: disable`, `skip-file` |
| `pragma` | `# pragma: no cover`, `no branch`, `allowlist secret` |
| `bandit` | `# nosec` |
| `fmt` | `# fmt: off`, `# fmt: on`, `# fmt: skip` |
| `isort` | `# isort: skip`, `skip_file`, `off`, `on`, `split` |
| `yapf` | `# yapf: disable`, `# yapf: enable` |
| `coding` | PEP 263 encoding cookie, on line 1 or 2 only |
| `cython` | `# cython:` and `# distutils:` build directives |
| `license` | `@license`, `@preserve`, `SPDX-License-Identifier` |
| `noinspection` | `# noinspection` (PyCharm) |
| `doctest` | Docstrings containing a `>>>` example (docstrings only) |

Shebangs are never touched — they are handled structurally, not by a rule.

Turn one off when it gets in the way:

```sh
commentless --no-keep noinspection --no-keep license
commentless --keep-only noqa,type-ignore,type-comment
commentless --keep '\bLEGAL\b' --keep 'Copyright \d{4}'
```

### Inline escapes

```python
x = compute()  # commentless-keep
               # this one really does need prose

# commentless-keep-next-line
# and so does this one

# commentless-ignore-file
```

## From comments to test names

The comment you are about to delete usually says something true and untested. `--to-test-names`
turns each one into a skipped test stub so the sentence has somewhere to go:

```sh
commentless --check --to-test-names tests/test_drafted.py
```

```python
import pytest


class TestSrcCache:
    @pytest.mark.skip(reason="todo: bails out when the cache is cold")
    def test_bails_out_when_the_cache_is_cold(self) -> None: ...

    @pytest.mark.skip(reason="todo: redis returns none on a miss, not an error")
    def test_redis_returns_none_on_a_miss_not_an_error(self) -> None: ...
```

One class per source file, one stub per sentence. It splits multi-sentence comments, strips
`TODO:` / `FIXME:` labels, joins wrapped comment blocks, and skips commented-out code and banners
rather than turning them into nonsense test names.

If your project uses pytest — detected from `pyproject.toml`, `pytest.ini`, `tox.ini`,
`setup.cfg`, `conftest.py` or a `requirements*.txt` — it emits `@pytest.mark.skip`. Otherwise it
falls back to `unittest.TestCase` with `@unittest.skip`, which runs anywhere.

Pair it with `--check` so you see the draft before anything is deleted.

## Configuration

`commentless init` writes a `commentless.config.json` baselined to your current comment count:

```sh
commentless init            # maxAllowed = today's count, so the gate passes now
commentless init --strict   # maxAllowed = 0, so the gate fails until you clean up
commentless init --pyproject  # write [tool.commentless] into pyproject.toml instead
```

Config is read from, in order, walking up from the working directory:

1. `commentless.config.json`
2. `pyproject.toml` under `[tool.commentless]`

```toml
[tool.commentless]
ext = ["py", "pyi"]
ignore = ["migrations/**", "**/generated_pb2.py"]
disableKeep = ["noinspection"]
docstrings = false
collapseBlankLines = true
maxAllowed = 0
reporter = "pretty"
```

Key names are camelCase so one schema covers both implementations, but snake_case aliases
(`max_allowed`, `collapse_blank_lines`, `disable_keep`, …) are accepted everywhere.

| Key | Type | Default |
| --- | --- | --- |
| `ext` | `list[str]` | `["py", "pyi"]` |
| `ignore` | `list[str]` | `[]` |
| `ignoreFile` | `str \| false` | `".commentlessignore"` |
| `gitignore` | `bool` | `true` |
| `keep` | `list[str]` (regexes) | `[]` |
| `defaultKeep` | `bool` | `true` |
| `disableKeep` | `list[str]` | `[]` |
| `keepOnly` | `list[str]` | unset |
| `collapseBlankLines` | `bool` | `false` |
| `docstrings` | `bool` | `false` |
| `maxAllowed` | `int` | `0` |
| `reporter` | `str` | `"pretty"` |
| `concurrency` | `int` | cpus − 1 |
| `cache` | `bool` | `true` |

## In CI

### pre-commit

`commentless init` offers to add this for you:

```yaml
repos:
  - repo: local
    hooks:
      - id: commentless
        name: commentless
        entry: commentless --check
        language: python
        additional_dependencies: ["commentless==0.1.0"]
        types: [python]
```

### GitHub Actions

```yaml
- uses: astral-sh/setup-uv@v5
- run: uvx commentless --check --reporter github
```

`--reporter github` emits `::error file=…,line=…,col=…` annotations, so every comment shows up
inline on the pull request diff.

Adopt gradually with `--max-allowed`, or gate only what the PR touches:

```sh
commentless --check --changed --base origin/main
```

## Reporters

| Name | Shape |
| --- | --- |
| `pretty` | Human output, one line per comment, colour on a TTY. |
| `github` | `::error` / `::notice` workflow commands for inline PR annotations. |
| `json` | `{"version": 1, "language": "python", "summary": {…}, "files": [{…}]}` |
| `summary` | The one-line summary and nothing else. |

## Performance

Files are tokenized in a process pool once the run is big enough to pay for the pool — currently
200+ files *and* 1 MB+ of pending source, since `tokenize` is pure Python and process startup is
not free. Below that it stays in one process, which is faster for small runs.

A clean-file cache in `.commentless-cache/` keys on size + mtime and on a signature of your keep
rules, so a second run over an unchanged tree does almost no work. `--no-cache` turns it off.

## Programmatic API

```python
from commentless import resolve_keep_rules, scan_source, strip_comments
from commentless.types import ScanOptions

source = open("app.py").read()
result = scan_source(source, ScanOptions(file_name="app.py", keep=resolve_keep_rules()))

print(len(result.removable), "to remove,", len(result.kept), "kept")
print(strip_comments(source, result.removable))
```

`run()`, `discover_files()`, `process_file()`, `report()`, `draft_test_names()` and `init()` are
all exported too — see `commentless.__all__`.

## FAQ

**Does it break my code?**
It removes `#` comments, which are inert, and — only when asked — docstrings that are safe to
remove. The output is parsed in the test suite for every combination of flags. If you find a case
where it does not, that is a bug worth an issue.

**Why not just `ruff` / a formatter?**
Formatters deliberately preserve comments. There is no `--strip-comments` in `black` or `ruff
format`, and there should not be — formatting and deletion are different jobs.

**Why not a regex?**
Because `url = "https://x#y"`, `f"{a} # b"` and `'''a # b'''` all contain a `#` that is not a
comment. `tokenize` knows the difference; a regex does not.

**I want to keep my docstrings.**
That is the default. Do nothing.

**What about `# type:` comments?**
Kept. They are type annotations in comment clothing, and deleting them changes what `mypy` sees.

**Does the cache go stale?**
It keys on size, mtime *and* a hash of your resolved keep rules, so changing `--no-keep` or
`--docstrings` invalidates it. `--no-cache` if you do not trust it.

## Contributing

See [CONTRIBUTING.md](https://github.com/barad-side-hustle/commentless/blob/main/CONTRIBUTING.md).

```sh
cd packages/python
uv sync
uv run pytest tests
uv run ruff check . && uv run ruff format --check .
uv run mypy src tests
uv run commentless . --check --docstrings   # it eats its own dog food
```

## License

MIT. See [LICENSE](https://github.com/barad-side-hustle/commentless/blob/main/LICENSE).
