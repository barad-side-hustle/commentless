from __future__ import annotations

import subprocess
from pathlib import Path

from commentless.keep import resolve_keep_rules
from commentless.types import KeepRule, ScanOptions


def default_keep() -> tuple[KeepRule, ...]:
    return resolve_keep_rules()


def scan_options(**overrides: object) -> ScanOptions:
    base: dict[str, object] = {"file_name": "input.py", "keep": default_keep()}
    base.update(overrides)
    return ScanOptions(**base)  # type: ignore[arg-type]


def write(root: Path, name: str, content: str) -> Path:
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout


def git_init(root: Path) -> None:
    git(root, "init", "-q", "-b", "main", ".")
    git(root, "config", "user.email", "commentless@example.com")
    git(root, "config", "user.name", "commentless")
    git(root, "config", "commit.gpgsign", "false")


def git_commit(root: Path, message: str = "snapshot") -> None:
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", message)
