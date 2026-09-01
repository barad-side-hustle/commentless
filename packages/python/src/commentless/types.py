from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

CommentKind = Literal["comment", "docstring"]
RunMode = Literal["write", "check", "dry-run"]
DiscoveryMode = Literal["all", "staged", "changed"]


@dataclass(frozen=True, slots=True)
class Comment:
    start: int
    end: int
    line: int
    column: int
    kind: CommentKind
    text: str
    kept_by: str | None = None


@dataclass(frozen=True, slots=True)
class KeepRule:
    name: str
    test: re.Pattern[str]
    kinds: tuple[CommentKind, ...] | None = None
    max_line: int | None = None


@dataclass(frozen=True, slots=True)
class SerializedKeepRule:
    name: str
    source: str
    flags: int
    kinds: tuple[CommentKind, ...] | None = None
    max_line: int | None = None


@dataclass(frozen=True, slots=True)
class ScanOptions:
    file_name: str = "input.py"
    keep: tuple[KeepRule, ...] = ()
    docstrings: bool = False


@dataclass(frozen=True, slots=True)
class ScanResult:
    removable: list[Comment] = field(default_factory=list)
    kept: list[Comment] = field(default_factory=list)
    ignored_file: bool = False


@dataclass(frozen=True, slots=True)
class FileResult:
    file: str
    removable: list[Comment] = field(default_factory=list)
    kept_count: int = 0
    changed: bool = False
    error: str | None = None


@dataclass(frozen=True, slots=True)
class RunSummary:
    mode: RunMode
    discovered: int
    parsed: int
    cached: int
    files_with_comments: int
    comments_removed: int
    comments_kept: int
    errors: int
    duration_ms: int


@dataclass(frozen=True, slots=True)
class RunResult:
    summary: RunSummary
    files: list[FileResult]
    exit_code: int
