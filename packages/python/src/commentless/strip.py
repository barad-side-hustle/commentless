from __future__ import annotations

import re

from .types import Comment

BYTE_ORDER_MARK = "﻿"

_TRAILING_WHITESPACE = re.compile(r"[ \t]+(\r?\n)")
_BLANK_RUN = re.compile(r"(\r?\n){4,}")


def _char_at(source: str, index: int) -> str | None:
    if index < 0 or index >= len(source):
        return None
    return source[index]


def _is_horizontal_whitespace(char: str | None) -> bool:
    return char in (" ", "\t")


def _merge_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1]:
            if end > merged[-1][1]:
                merged[-1] = (merged[-1][0], end)
            continue
        merged.append((start, end))
    return merged


def _expand(source: str, start: int, end: int) -> tuple[int, int]:
    cursor_start = start
    while cursor_start > 0 and _is_horizontal_whitespace(_char_at(source, cursor_start - 1)):
        cursor_start -= 1
    consumed_leading = cursor_start < start

    at_line_start = (
        cursor_start == 0
        or _char_at(source, cursor_start - 1) == "\n"
        or (cursor_start == 1 and source[:1] == BYTE_ORDER_MARK)
    )

    cursor = end
    while _is_horizontal_whitespace(_char_at(source, cursor)):
        cursor += 1
    at_line_end = cursor >= len(source) or source[cursor] in ("\n", "\r")

    if not at_line_start:
        return (cursor_start, end) if consumed_leading else (cursor_start, cursor)

    if not at_line_end:
        return start, cursor

    stop = cursor
    if _char_at(source, stop) == "\r":
        stop += 1
    if _char_at(source, stop) == "\n":
        stop += 1
    return cursor_start, stop


def strip_comments(
    source: str,
    comments: list[Comment],
    *,
    collapse_blank_lines_option: bool = False,
) -> str:
    if not comments:
        return collapse_blank_lines(source) if collapse_blank_lines_option else source

    ranges = _merge_ranges([_expand(source, c.start, c.end) for c in comments])

    parts: list[str] = []
    cursor = 0
    for start, end in ranges:
        if start < cursor:
            continue
        parts.append(source[cursor:start])
        cursor = end
    parts.append(source[cursor:])

    out = "".join(parts)
    return collapse_blank_lines(out) if collapse_blank_lines_option else out


def collapse_blank_lines(source: str) -> str:
    return _BLANK_RUN.sub(r"\1\1\1", _TRAILING_WHITESPACE.sub(r"\1", source))
