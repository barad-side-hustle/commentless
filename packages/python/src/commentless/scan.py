from __future__ import annotations

import ast
import io
import os
import tokenize
from dataclasses import replace

from .keep import (
    apply_keep_next_line,
    has_ignore_file_marker,
    match_keep_rule,
)
from .types import Comment, ScanOptions, ScanResult

DEFAULT_EXTENSIONS: tuple[str, ...] = ("py", "pyi")

BYTE_ORDER_MARK = "﻿"

SOLE_STATEMENT_RULE = "sole-statement"
INLINE_RULE = "inline"

_DOCSTRING_OWNERS = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


class ScanError(Exception):
    pass


def may_contain_comments(source: str, *, docstrings: bool = False) -> bool:
    if "#" in source:
        return True
    return docstrings and ('"' in source or "'" in source)


def line_starts(source: str) -> list[int]:
    starts = [0]
    index = source.find("\n")
    while index != -1:
        starts.append(index + 1)
        index = source.find("\n", index + 1)
    return starts


def _line_end(source: str, start: int) -> int:
    index = source.find("\n", start)
    return len(source) if index == -1 else index


def script_kind_for(file_name: str) -> str:
    return os.path.splitext(file_name)[1].lower().lstrip(".") or "py"


def _collect_comments(body: str, starts: list[int]) -> list[Comment]:
    found: list[Comment] = []
    reader = io.StringIO(body).readline
    try:
        for token in tokenize.generate_tokens(reader):
            if token.type != tokenize.COMMENT:
                continue
            row, col = token.start
            if row == 1 and col == 0 and body.startswith("#!"):
                continue
            start = starts[row - 1] + col
            found.append(
                Comment(
                    start=start,
                    end=start + len(token.string),
                    line=row,
                    column=col + 1,
                    kind="comment",
                    text=token.string,
                )
            )
    except tokenize.TokenError as error:
        raise ScanError(f"could not tokenize: {error.args[0]}") from error
    except SyntaxError as error:
        where = f" (line {error.lineno})" if error.lineno else ""
        raise ScanError(f"could not tokenize: {error.msg}{where}") from error
    return found


def _byte_column_to_offset(body: str, starts: list[int], row: int, byte_col: int) -> int:
    line_start = starts[row - 1]
    line = body[line_start : _line_end(body, line_start)]
    prefix = line.encode("utf-8")[:byte_col].decode("utf-8", "replace")
    return line_start + len(prefix)


def _occupies_own_lines(body: str, starts: list[int], start: int, end: int, row: int) -> bool:
    before = body[starts[row - 1] : start]
    if before.strip():
        return False
    after = body[end : _line_end(body, end)]
    stripped = after.strip()
    return not stripped or stripped.startswith("#")


def _collect_docstrings(body: str, starts: list[int]) -> list[tuple[Comment, str | None]]:
    try:
        tree = ast.parse(body)
    except SyntaxError as error:
        where = f" (line {error.lineno})" if error.lineno else ""
        raise ScanError(f"could not parse: {error.msg}{where}") from error

    found: list[tuple[Comment, str | None]] = []
    for node in ast.walk(tree):
        if not isinstance(node, _DOCSTRING_OWNERS):
            continue
        if not node.body:
            continue
        first = node.body[0]
        if not isinstance(first, ast.Expr):
            continue
        literal = first.value
        if not isinstance(literal, ast.Constant) or not isinstance(literal.value, str):
            continue
        if literal.end_lineno is None or literal.end_col_offset is None:
            continue

        start = _byte_column_to_offset(body, starts, literal.lineno, literal.col_offset)
        end = _byte_column_to_offset(body, starts, literal.end_lineno, literal.end_col_offset)

        forced: str | None = None
        if len(node.body) == 1 and not isinstance(node, ast.Module):
            forced = SOLE_STATEMENT_RULE
        elif not _occupies_own_lines(body, starts, start, end, literal.lineno):
            forced = INLINE_RULE

        found.append(
            (
                Comment(
                    start=start,
                    end=end,
                    line=literal.lineno,
                    column=literal.col_offset + 1,
                    kind="docstring",
                    text=body[start:end],
                ),
                forced,
            )
        )
    return found


def scan_source(source: str, options: ScanOptions | None = None) -> ScanResult:
    options = options or ScanOptions()

    if not may_contain_comments(source, docstrings=options.docstrings):
        return ScanResult()
    if has_ignore_file_marker(source):
        return ScanResult(ignored_file=True)

    shift = 1 if source.startswith(BYTE_ORDER_MARK) else 0
    body = source[shift:]
    starts = line_starts(body)

    forced_rules: dict[int, str] = {}
    found = _collect_comments(body, starts)

    if options.docstrings:
        for comment, forced in _collect_docstrings(body, starts):
            found.append(comment)
            if forced:
                forced_rules[comment.start] = forced

    found.sort(key=lambda comment: comment.start)

    forced_next = apply_keep_next_line(found)
    removable: list[Comment] = []
    kept: list[Comment] = []

    for comment in found:
        kept_by = forced_rules.get(comment.start)
        if kept_by is None and comment.start in forced_next:
            kept_by = "commentless-keep-next-line"
        if kept_by is None:
            kept_by = match_keep_rule(comment, options.keep)

        shifted = replace(comment, start=comment.start + shift, end=comment.end + shift)
        if kept_by:
            kept.append(replace(shifted, kept_by=kept_by))
        else:
            removable.append(shifted)

    return ScanResult(removable=removable, kept=kept, ignored_file=False)
