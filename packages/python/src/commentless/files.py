from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import pathspec

from .types import DiscoveryMode

ALWAYS_IGNORED: tuple[str, ...] = (
    ".git/",
    "node_modules/",
    "__pycache__/",
    ".venv/",
    "venv/",
    ".tox/",
    ".nox/",
    ".eggs/",
    "*.egg-info/",
    "site-packages/",
    ".mypy_cache/",
    ".pytest_cache/",
    ".ruff_cache/",
)

PRUNED_DIRECTORIES: frozenset[str] = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        ".tox",
        ".nox",
        ".eggs",
        "site-packages",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
    }
)

BASE_CANDIDATES: tuple[str, ...] = ("origin/HEAD", "origin/main", "origin/master", "main", "master")


class DiscoveryError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class DiscoverOptions:
    cwd: str
    paths: tuple[str, ...] = (".",)
    extensions: tuple[str, ...] = ()
    ignore: tuple[str, ...] = ()
    ignore_file: str | None = ".commentlessignore"
    gitignore: bool = True
    mode: DiscoveryMode = "all"
    base: str | None = None
    always_ignored: tuple[str, ...] = field(default=ALWAYS_IGNORED)


def _git(cwd: str, args: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            check=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout


def _real_path(target: str) -> str:
    try:
        return str(Path(target).resolve(strict=True))
    except OSError:
        return str(Path(target).absolute())


def git_root(cwd: str) -> str | None:
    stdout = _git(cwd, ["rev-parse", "--show-toplevel"])
    root = (stdout or "").strip()
    return _real_path(root) if root else None


def _resolve_base(cwd: str, base: str | None) -> str | None:
    candidates = [base] if base else list(BASE_CANDIDATES)
    for candidate in candidates:
        resolved = _git(cwd, ["rev-parse", "--verify", "--quiet", f"{candidate}^{{commit}}"])
        if resolved and resolved.strip():
            merge_base = _git(cwd, ["merge-base", candidate, "HEAD"])
            return (merge_base or "").strip() or resolved.strip()
    return None


def _split_nulls(stdout: str) -> list[str]:
    return [entry for entry in stdout.split("\0") if entry]


def _list_from_git(options: DiscoverOptions, root: str | None) -> list[str] | None:
    mode = options.mode

    if root is None:
        if mode == "all":
            return None
        raise DiscoveryError(
            f"--{mode} needs a git repository, but {options.cwd} is not inside one"
        )

    if mode == "staged":
        stdout = _git(root, ["diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"])
        return None if stdout is None else _split_nulls(stdout)

    if mode == "changed":
        merge_base = _resolve_base(root, options.base)
        if not merge_base:
            raise DiscoveryError(
                f"--base {options.base} does not resolve to a commit"
                if options.base
                else "could not resolve a base ref for --changed; pass --base <ref>"
            )
        stdout = _git(root, ["diff", "--name-only", "--diff-filter=ACMR", "-z", merge_base])
        if stdout is None:
            return None
        untracked = _git(root, ["ls-files", "--others", "--exclude-standard", "-z"])
        return [*_split_nulls(stdout), *(_split_nulls(untracked) if untracked else [])]

    if not options.gitignore:
        return None
    stdout = _git(root, ["ls-files", "--cached", "--others", "--exclude-standard", "-z"])
    return None if stdout is None else _split_nulls(stdout)


def _list_from_walk(cwd: str, extensions: set[str]) -> list[str]:
    found: list[str] = []
    for directory, subdirectories, names in os.walk(cwd):
        subdirectories[:] = [
            name
            for name in subdirectories
            if name not in PRUNED_DIRECTORIES and not name.endswith(".egg-info")
        ]
        for name in names:
            if os.path.splitext(name)[1].lower() in extensions:
                found.append(os.path.join(directory, name))
    return found


def build_ignore_filter(options: DiscoverOptions) -> pathspec.GitIgnoreSpec:
    patterns = [pattern.rstrip("/") for pattern in options.always_ignored]
    if options.ignore_file:
        ignore_path = Path(_real_path(options.cwd)) / options.ignore_file
        if ignore_path.is_file():
            patterns.extend(ignore_path.read_text(encoding="utf-8").splitlines())

    patterns.extend(options.ignore)
    return pathspec.GitIgnoreSpec.from_lines(patterns)


def _matches_requested_paths(absolute: str, roots: list[str]) -> bool:
    if not roots:
        return True
    return any(absolute == root or absolute.startswith(root + os.sep) for root in roots)


def discover_files(options: DiscoverOptions) -> list[str]:
    extensions = {f".{entry.lower().lstrip('.')}" for entry in options.extensions}
    cwd = _real_path(options.cwd)
    root = git_root(cwd)

    from_git = _list_from_git(options, root)
    if from_git is not None and root is not None:
        candidates = [os.path.join(root, entry) for entry in from_git]
    else:
        candidates = _list_from_walk(cwd, extensions)

    roots = [
        os.path.normpath(os.path.join(cwd, entry))
        for entry in options.paths
        if entry not in (".", "./")
    ]

    matcher = build_ignore_filter(options)
    seen: set[str] = set()
    result: list[str] = []

    for candidate in candidates:
        absolute = os.path.normpath(candidate)
        if os.path.splitext(absolute)[1].lower() not in extensions:
            continue

        relative = os.path.relpath(absolute, cwd).replace(os.sep, "/")
        if relative in ("", ".") or relative.startswith("../"):
            continue
        if matcher.match_file(relative):
            continue
        if not _matches_requested_paths(absolute, roots):
            continue
        if absolute in seen:
            continue
        if not os.path.isfile(absolute):
            continue

        seen.add(absolute)
        result.append(os.path.normpath(os.path.join(options.cwd, relative)))

    return sorted(result)
