from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Literal, get_args

from .colors import create_colors
from .types import Comment, RunResult

ReporterName = Literal["pretty", "json", "github", "summary"]

REPORTERS: tuple[ReporterName, ...] = get_args(ReporterName)

_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class ReportContext:
    cwd: str
    quiet: bool = False
    verbose: bool = False
    color: bool = False


def _relative(cwd: str, file: str) -> str:
    try:
        return os.path.relpath(file, cwd).replace(os.sep, "/") or file
    except ValueError:
        return file


def _preview(comment: Comment) -> str:
    flat = _WHITESPACE.sub(" ", comment.text).strip()
    return f"{flat[:69]}..." if len(flat) > 72 else flat


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def summary_line(result: RunResult) -> str:
    summary = result.summary
    scope = f"{_plural(summary.discovered, 'file')} scanned"
    cached = f", {summary.cached} cached" if summary.cached > 0 else ""
    kept = f", {summary.comments_kept} kept" if summary.comments_kept > 0 else ""
    verb = "removed" if summary.mode == "write" else "to remove"
    errors = f", {_plural(summary.errors, 'error')}" if summary.errors > 0 else ""
    return (
        f"{scope}{cached} · {_plural(summary.comments_removed, 'comment')} {verb} in "
        f"{_plural(summary.files_with_comments, 'file')}{kept}{errors} · {summary.duration_ms}ms"
    )


def _pretty(result: RunResult, context: ReportContext) -> str:
    pc = create_colors(context.color)
    lines: list[str] = []

    for file in result.files:
        name = _relative(context.cwd, file.file)
        if file.error:
            lines.append(f"{pc.red('✗')} {name} {pc.dim(file.error)}")
            continue
        verb = "removed" if result.summary.mode == "write" else "found"
        detail = pc.dim(f"({_plural(len(file.removable), 'comment')} {verb})")
        kept = pc.dim(f" [{file.kept_count} kept]") if context.verbose and file.kept_count else ""
        lines.append(f"{pc.yellow('•')} {pc.bold(name)} {detail}{kept}")
        if context.quiet:
            continue
        for comment in file.removable:
            location = pc.dim(f"{name}:{comment.line}:{comment.column}")
            lines.append(f"  {location}  {_preview(comment)}")

    if lines:
        lines.append("")

    line = summary_line(result)
    lines.append(f"{pc.green('✔')} {line}" if result.exit_code == 0 else f"{pc.red('✖')} {line}")

    if result.exit_code != 0 and result.summary.mode == "check":
        lines.append(
            pc.dim(
                "  Run `commentless --write` to remove them, or keep one with `commentless-keep`."
            )
        )

    return "\n".join(lines)


def _escape_property(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_data(value: str) -> str:
    return _escape_property(value).replace(":", "%3A")


def _github(result: RunResult, context: ReportContext) -> str:
    lines: list[str] = []

    for file in result.files:
        name = _escape_property(_relative(context.cwd, file.file))
        if file.error:
            lines.append(f"::error file={name}::{_escape_data(file.error)}")
            continue
        for comment in file.removable:
            body = _escape_data(f"Remove this {comment.kind}: {_preview(comment)}")
            lines.append(
                f"::error file={name},line={comment.line},col={comment.column},"
                f"title=commentless::{body}"
            )

    lines.append(f"::notice title=commentless::{_escape_data(summary_line(result))}")
    return "\n".join(lines)


def _json(result: RunResult, context: ReportContext) -> str:
    summary = result.summary
    return json.dumps(
        {
            "version": 1,
            "language": "python",
            "summary": {
                "mode": summary.mode,
                "discovered": summary.discovered,
                "parsed": summary.parsed,
                "cached": summary.cached,
                "filesWithComments": summary.files_with_comments,
                "commentsRemoved": summary.comments_removed,
                "commentsKept": summary.comments_kept,
                "errors": summary.errors,
                "durationMs": summary.duration_ms,
            },
            "exitCode": result.exit_code,
            "files": [
                {
                    "file": _relative(context.cwd, file.file),
                    "changed": file.changed,
                    "keptCount": file.kept_count,
                    **({"error": file.error} if file.error else {}),
                    "comments": [
                        {
                            "line": comment.line,
                            "column": comment.column,
                            "kind": comment.kind,
                            "text": comment.text,
                        }
                        for comment in file.removable
                    ],
                }
                for file in result.files
            ],
        },
        indent=2,
    )


def report(reporter: ReporterName, result: RunResult, context: ReportContext) -> str:
    if reporter == "json":
        return _json(result, context)
    if reporter == "github":
        return _github(result, context)
    if reporter == "summary":
        return summary_line(result)
    return _pretty(result, context)
