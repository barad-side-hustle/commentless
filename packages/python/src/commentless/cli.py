from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from .colors import Colors, create_colors
from .config import CONFIG_FILE_NAME, ConfigError, FileConfig, load_config
from .files import DiscoverOptions, DiscoveryError, discover_files
from .init import InitOptions, init
from .keep import (
    KEEP_RULE_DESCRIPTIONS,
    KEEP_RULE_NAMES,
    UnknownKeepRuleError,
    resolve_keep_rules,
)
from .reporters import REPORTERS, ReportContext, ReporterName, report
from .run import RunOptions, default_concurrency, run
from .scan import DEFAULT_EXTENSIONS
from .testnames import DraftOptions, detect_test_framework, draft_test_names
from .types import DiscoveryMode, RunMode, RunResult
from .version import VERSION

AGENT_PROMPT_URL = "https://github.com/barad-side-hustle/commentless#hand-the-skeleton-to-an-agent"

HELP = f"""commentless {VERSION}

  Strip comments from Python with a real tokenizer, keep the ones that do work
  (noqa, type: ignore, pragma: no cover, licences, ...), and fail CI when new
  ones appear.

Usage
  commentless [paths...] [options]
  commentless init [options]      Write a {CONFIG_FILE_NAME} you can commit

Mode
  --check                  Report only, never write. Exit 1 if a comment would be removed.
  --write                  Rewrite files in place. Default when --check is absent.
  --dry-run                Report what --write would do, write nothing. Always exits 0.

Scope
  --staged                 Only files staged in git.
  --changed                Only files changed against --base.
  --base <ref>             Base ref for --changed (default: origin/HEAD, then main).
  --ext <list>             Comma-separated extensions (default: {",".join(DEFAULT_EXTENSIONS)}).
  --ignore <glob>          Gitignore-syntax pattern to skip. Repeatable.
  --ignore-file <path>     Ignore file to read (default: .commentlessignore).
  --no-gitignore           Stop honouring .gitignore.
  --list-files             Print the resolved file list and exit.

Docstrings
  --docstrings             Also strip module, class and function docstrings. Off by default,
                           because a docstring is a runtime value: __doc__, doctests, Sphinx
                           and FastAPI all read it. A docstring that is the only statement in
                           its body is always kept — removing it would not parse.

Comments to keep
  --keep <regex>           Keep comments matching this pattern. Repeatable.
  --no-keep <rule>         Turn off one built-in keep rule. Repeatable.
                           e.g. --no-keep noqa --no-keep license
  --keep-only <list>       Enable only these built-in rules, comma-separated.
                           e.g. --keep-only noqa,type-ignore
  --no-default-keep        Turn off every built-in rule. Same as --keep-only ''.
  --list-keep-rules        Print the built-in rules and what each one matches.
  --collapse-blank-lines   Also trim trailing whitespace and collapse 3+ blank lines.

Output
  --reporter <name>        {" | ".join(REPORTERS)} (default: pretty).
  --max-allowed <n>        --check passes while removable comments are at or under n.
  --to-test-names <file>   Draft a skipped test stub per comment into <file>, so the
                           explanations have somewhere to go. Pair it with --check to
                           look before you leap. --force overwrites an existing file.
  -q, --quiet              Summary only.
  -v, --verbose            Include kept-comment counts.
  --no-color               Disable colour.

init
  --force                  Overwrite an existing config file.
  --strict                 Set maxAllowed to 0 instead of today's comment count.
  --pyproject              Write [tool.commentless] into pyproject.toml instead.
  --pre-commit             Add a commentless hook to .pre-commit-config.yaml without
                           asking. --no-pre-commit never adds it. Interactively, init asks.

Other
  --concurrency <n>        Worker processes (default: cpus - 1).
  --no-cache               Skip the clean-file cache.
  --config <path>          Path to a commentless.config.json or pyproject.toml.
  -h, --help               Show this help.
  --version                Print the version.

Exit codes
  0  clean
  1  comments found under --check, or a file could not be processed
  2  bad usage or invalid configuration

Inline escapes
  # commentless-keep             keep this comment
  # commentless-keep-next-line   keep the comment that follows
  # commentless-ignore-file      skip the whole file
"""


class UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # type: ignore[override]
        raise UsageError(message)

    def exit(self, status: int = 0, message: str | None = None) -> None:  # type: ignore[override]
        if status:
            raise UsageError(message or "invalid usage")


def _build_parser() -> _Parser:
    parser = _Parser(add_help=False, allow_abbrev=False)
    parser.add_argument("positionals", nargs="*")

    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--changed", action="store_true")
    parser.add_argument("--base")
    parser.add_argument("--ext")
    parser.add_argument("--ignore", action="append")
    parser.add_argument("--ignore-file")
    parser.add_argument("--no-gitignore", action="store_true")
    parser.add_argument("--list-files", action="store_true")
    parser.add_argument("--docstrings", action="store_true")
    parser.add_argument("--keep", action="append")
    parser.add_argument("--no-keep", action="append")
    parser.add_argument("--keep-only")
    parser.add_argument("--no-default-keep", action="store_true")
    parser.add_argument("--list-keep-rules", action="store_true")
    parser.add_argument("--collapse-blank-lines", action="store_true")
    parser.add_argument("--reporter")
    parser.add_argument("--max-allowed")
    parser.add_argument("-q", "--quiet", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--concurrency")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--config")
    parser.add_argument("--to-test-names")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--pyproject", action="store_true")
    parser.add_argument("--pre-commit", action="store_true")
    parser.add_argument("--no-pre-commit", action="store_true")
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("--version", action="store_true")
    return parser


def _prompt_yes_no(question: str) -> bool:
    try:
        answer = input(f"\n{question} [Y/n] ").strip().lower()
    except EOFError:
        return False
    return answer in ("", "y", "yes")


def _parse_extensions(value: str) -> tuple[str, ...]:
    extensions = tuple(
        entry.strip().lstrip(".").lower() for entry in value.split(",") if entry.strip().lstrip(".")
    )
    if not extensions:
        raise UsageError("--ext needs at least one extension")
    return extensions


def _parse_integer(flag: str, value: str, minimum: int) -> int:
    try:
        parsed = int(value, 10)
    except ValueError:
        raise UsageError(f"{flag} must be an integer >= {minimum}") from None
    if parsed < minimum:
        raise UsageError(f"{flag} must be an integer >= {minimum}")
    return parsed


def _use_color(no_color: bool, stream: object) -> bool:
    isatty = getattr(stream, "isatty", None)
    return not no_color and bool(isatty and isatty()) and not os.environ.get("NO_COLOR")


def main(argv: Sequence[str]) -> int:
    parser = _build_parser()
    try:
        values = parser.parse_args(list(argv))
    except UsageError as error:
        sys.stderr.write(f"{error}\n")
        sys.stderr.write("Run `commentless --help` for usage.\n")
        return 2

    if values.help:
        sys.stdout.write(HELP)
        return 0
    if values.version:
        sys.stdout.write(f"{VERSION}\n")
        return 0
    if values.list_keep_rules:
        width = max(len(name) for name in KEEP_RULE_NAMES)
        listed = "\n".join(
            f"  {name.ljust(width)}  {KEEP_RULE_DESCRIPTIONS.get(name, '')}"
            for name in KEEP_RULE_NAMES
        )
        sys.stdout.write(f"Built-in keep rules\n{listed}\n")
        return 0

    cwd = os.getcwd()
    colors = create_colors(_use_color(values.no_color, sys.stderr))

    try:
        return _dispatch(values, cwd, colors)
    except (UsageError, ConfigError, UnknownKeepRuleError) as error:
        sys.stderr.write(f"{colors.red('error')} {error}\n")
        return 2
    except DiscoveryError as error:
        sys.stderr.write(f"{colors.red('error')} {error}\n")
        return 2
    except Exception as error:
        sys.stderr.write(f"{colors.red('error')} {error!r}\n")
        return 1


def _dispatch(values: argparse.Namespace, cwd: str, pc: Colors) -> int:

    if values.check and values.write:
        raise UsageError("--check and --write are mutually exclusive")
    if values.staged and values.changed:
        raise UsageError("--staged and --changed are mutually exclusive")

    positionals: list[str] = list(values.positionals)
    is_init = bool(positionals) and positionals[0] == "init"
    if is_init and len(positionals) > 1:
        raise UsageError(f"init takes no paths, got {' '.join(positionals[1:])}")
    if is_init and values.to_test_names:
        raise UsageError("--to-test-names does not apply to init")

    config = FileConfig() if is_init else load_config(cwd, values.config).config

    reporter_name = values.reporter or config.reporter or "pretty"
    if reporter_name not in REPORTERS:
        raise UsageError(f"--reporter must be one of: {', '.join(REPORTERS)}")

    mode: RunMode = "check" if values.check else "dry-run" if values.dry_run else "write"
    discovery: DiscoveryMode = "staged" if values.staged else "changed" if values.changed else "all"

    if values.keep_only is not None:
        keep_only: tuple[str, ...] | None = tuple(
            name.strip() for name in values.keep_only.split(",") if name.strip()
        )
    elif config.keepOnly is not None:
        keep_only = tuple(config.keepOnly)
    else:
        keep_only = None

    keep = resolve_keep_rules(
        defaults=False if values.no_default_keep else (config.defaultKeep is not False),
        user_patterns=(*(config.keep or ()), *(values.keep or ())),
        disable=(*(config.disableKeep or ()), *(values.no_keep or ())),
        only=keep_only,
    )

    test_names_file = Path(cwd, values.to_test_names).resolve() if values.to_test_names else None
    if test_names_file and test_names_file.exists() and not values.force:
        raise UsageError(
            f"{values.to_test_names} already exists. Re-run with --force to overwrite it."
        )

    paths = tuple(positionals) if not is_init and positionals else (".",)
    extensions = (
        _parse_extensions(values.ext)
        if values.ext
        else tuple(config.ext)
        if config.ext
        else DEFAULT_EXTENSIONS
    )
    ignore = (*(config.ignore or ()), *(values.ignore or ()))
    raw_ignore_file = (
        values.ignore_file
        if values.ignore_file is not None
        else config.ignoreFile
        if config.ignoreFile is not None
        else ".commentlessignore"
    )
    ignore_file = None if raw_ignore_file is False else str(raw_ignore_file)
    gitignore = False if values.no_gitignore else (config.gitignore is not False)
    docstrings = values.docstrings or bool(config.docstrings)
    use_color = _use_color(values.no_color, sys.stdout)

    if is_init:
        if values.pre_commit and values.no_pre_commit:
            raise UsageError("--pre-commit and --no-pre-commit are mutually exclusive")
        pre_commit = True if values.pre_commit else False if values.no_pre_commit else None
        interactive = sys.stdin.isatty() and sys.stdout.isatty()

        init_result = init(
            InitOptions(
                cwd=cwd,
                config_path=values.config,
                pyproject=values.pyproject,
                force=values.force,
                strict=values.strict,
                docstrings=docstrings,
                color=use_color,
                extensions=extensions,
                ignore=ignore,
                ignore_file=ignore_file,
                gitignore=gitignore,
                keep=keep,
                pre_commit=pre_commit,
                confirm=_prompt_yes_no if pre_commit is None and interactive else None,
            )
        )
        sys.stdout.write(f"{init_result.output}\n")
        return 2 if init_result.existed else 0

    if values.list_files:
        files = discover_files(
            DiscoverOptions(
                cwd=cwd,
                paths=paths,
                extensions=extensions,
                ignore=ignore,
                ignore_file=ignore_file,
                gitignore=gitignore,
                mode=discovery,
                base=values.base,
            )
        )
        listed = [os.path.relpath(file, cwd).replace(os.sep, "/") for file in files]
        sys.stdout.write("\n".join(listed) + "\n" if listed else "")
        return 0

    result = run(
        RunOptions(
            cwd=cwd,
            paths=paths,
            mode=mode,
            discovery=discovery,
            base=values.base,
            extensions=extensions,
            ignore=ignore,
            ignore_file=ignore_file,
            gitignore=gitignore,
            keep=keep,
            collapse_blank_lines=values.collapse_blank_lines or bool(config.collapseBlankLines),
            docstrings=docstrings,
            max_allowed=(
                _parse_integer("--max-allowed", values.max_allowed, 0)
                if values.max_allowed
                else (config.maxAllowed or 0)
            ),
            concurrency=(
                _parse_integer("--concurrency", values.concurrency, 1)
                if values.concurrency
                else (config.concurrency or default_concurrency())
            ),
            cache=False if values.no_cache else (config.cache is not False),
        )
    )

    sys.stdout.write(
        report(
            cast(ReporterName, reporter_name),
            result,
            ReportContext(cwd=cwd, quiet=values.quiet, verbose=values.verbose, color=use_color),
        )
        + "\n"
    )

    if test_names_file:
        _write_test_names(test_names_file, cwd, result, pc)

    return result.exit_code


def _write_test_names(test_names_file: Path, cwd: str, result: RunResult, pc: Colors) -> None:
    shown = os.path.relpath(test_names_file, cwd).replace(os.sep, "/") or str(test_names_file)
    framework = detect_test_framework(cwd)
    draft = draft_test_names(result.files, DraftOptions(cwd=cwd, framework=framework))

    if not draft.drafts:
        sys.stderr.write(f"{pc.yellow('!')} No comments left to draft into {shown}.\n")
        return

    test_names_file.parent.mkdir(parents=True, exist_ok=True)
    test_names_file.write_text(draft.source, encoding="utf-8")

    skipped = (
        pc.dim(
            f" ({draft.skipped} comment{'' if draft.skipped == 1 else 's'} skipped: "
            "commented-out code, banners, and the like)"
        )
        if draft.skipped
        else ""
    )
    drafted = len(draft.drafts)
    sys.stderr.write(
        f"{pc.green('✔')} Drafted {drafted} test name{'' if drafted == 1 else 's'} from "
        f"{draft.files} file{'' if draft.files == 1 else 's'} into "
        f"{pc.bold(shown)}{skipped}\n"
        + pc.dim(
            f"  Next: hand {shown} to your coding agent and have it fill in every stub\n"
            "  against the source file named in its class. Prompt to paste:\n"
            f"  {AGENT_PROMPT_URL}\n"
        )
    )


def entry() -> None:
    sys.exit(main(sys.argv[1:]))
