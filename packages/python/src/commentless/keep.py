from __future__ import annotations

import re

from .types import Comment, KeepRule, SerializedKeepRule

KEEP_MARKER = "commentless-keep"
KEEP_NEXT_MARKER = "commentless-keep-next-line"
IGNORE_FILE_MARKER = "commentless-ignore-file"

SOLE_STATEMENT_RULE = "sole-statement"

DEFAULT_KEEP_RULES: tuple[KeepRule, ...] = (
    KeepRule("commentless", re.compile(r"\bcommentless-keep(-next-line)?\b")),
    KeepRule("noqa", re.compile(r"\bnoqa\b", re.IGNORECASE)),
    KeepRule("ruff", re.compile(r"\bruff\s*:\s*\w")),
    KeepRule("mypy", re.compile(r"\bmypy\s*:\s*\w")),
    KeepRule("type-ignore", re.compile(r"#\s*type:\s*ignore\b")),
    KeepRule("type-comment", re.compile(r"#\s*type:\s*(?!ignore\b)\S")),
    KeepRule("pyright", re.compile(r"\bpyright\s*:\s*\w")),
    KeepRule("pylint", re.compile(r"\bpylint\s*:\s*(disable|enable|skip-file)")),
    KeepRule("pytype", re.compile(r"\bpytype\s*:\s*(disable|skip-file)")),
    KeepRule("pragma", re.compile(r"\bpragma\s*:\s*\w")),
    KeepRule("bandit", re.compile(r"\bnosec\b")),
    KeepRule("fmt", re.compile(r"\bfmt\s*:\s*(off|on|skip)\b")),
    KeepRule("isort", re.compile(r"\bisort\s*:\s*(skip_file|skip|off|on|split|dont-add-imports)")),
    KeepRule("yapf", re.compile(r"\byapf\s*:\s*(disable|enable)\b")),
    KeepRule(
        "coding",
        re.compile(r"^#[ \t\f]*(?:-\*-.*?)?coding[:=][ \t]*[-_.a-zA-Z0-9]+"),
        max_line=2,
    ),
    KeepRule("cython", re.compile(r"^#\s*(cython|distutils)\s*:")),
    KeepRule("license", re.compile(r"@(license|preserve)\b|\bSPDX-License-Identifier\b")),
    KeepRule("noinspection", re.compile(r"\bnoinspection\b")),
    KeepRule(
        "doctest",
        re.compile(r"""(?m)^[ \t]*(?:["']{1,3})?[ \t]*>>>[ \t]"""),
        kinds=("docstring",),
    ),
)

KEEP_RULE_NAMES: tuple[str, ...] = tuple(rule.name for rule in DEFAULT_KEEP_RULES)

KEEP_RULE_DESCRIPTIONS: dict[str, str] = {
    "commentless": "commentless-keep and commentless-keep-next-line",
    "noqa": "# noqa and # noqa: E501 (flake8, ruff, vulture)",
    "ruff": "# ruff: isort: on and friends",
    "mypy": "# mypy: disallow-untyped-defs",
    "type-ignore": "# type: ignore and # type: ignore[arg-type]",
    "type-comment": "PEP 484 type comments — # type: List[int]",
    "pyright": "# pyright: ignore, # pyright: strict",
    "pylint": "# pylint: disable, enable, skip-file",
    "pytype": "# pytype: disable, skip-file",
    "pragma": "# pragma: no cover, no branch, allowlist secret",
    "bandit": "# nosec",
    "fmt": "# fmt: off, # fmt: on, # fmt: skip (black, ruff format)",
    "isort": "# isort: skip, skip_file, off, on, split",
    "yapf": "# yapf: disable, # yapf: enable",
    "coding": "PEP 263 encoding cookie on line 1 or 2",
    "cython": "# cython: and # distutils: build directives",
    "license": "@license, @preserve, SPDX-License-Identifier",
    "noinspection": "# noinspection (PyCharm)",
    "doctest": "docstrings containing a >>> example (docstrings only)",
}


def serialize_keep_rules(rules: tuple[KeepRule, ...]) -> tuple[SerializedKeepRule, ...]:
    return tuple(
        SerializedKeepRule(
            name=rule.name,
            source=rule.test.pattern,
            flags=rule.test.flags,
            kinds=rule.kinds,
            max_line=rule.max_line,
        )
        for rule in rules
    )


def deserialize_keep_rules(rules: tuple[SerializedKeepRule, ...]) -> tuple[KeepRule, ...]:
    return tuple(
        KeepRule(
            name=rule.name,
            test=re.compile(rule.source, rule.flags),
            kinds=rule.kinds,
            max_line=rule.max_line,
        )
        for rule in rules
    )


def signature_of_keep_rules(rules: tuple[KeepRule, ...]) -> list[list[object]]:
    return [
        [rule.name, rule.test.pattern, rule.test.flags, list(rule.kinds or ()), rule.max_line]
        for rule in rules
    ]


class UnknownKeepRuleError(Exception):
    def __init__(self, names: list[str]) -> None:
        plural = "" if len(names) == 1 else "s"
        listed = ", ".join(f'"{name}"' for name in names)
        super().__init__(
            f"unknown keep rule{plural} {listed}. Valid rules: {', '.join(KEEP_RULE_NAMES)}"
        )


def _assert_known(names: list[str]) -> None:
    unknown = [name for name in names if name not in KEEP_RULE_NAMES]
    if unknown:
        raise UnknownKeepRuleError(unknown)


def resolve_keep_rules(
    *,
    defaults: bool = True,
    user_patterns: tuple[str, ...] = (),
    disable: tuple[str, ...] = (),
    only: tuple[str, ...] | None = None,
) -> tuple[KeepRule, ...]:
    _assert_known([*disable, *(only or ())])

    rules = list(DEFAULT_KEEP_RULES) if defaults else []
    if only is not None:
        rules = [rule for rule in rules if rule.name in only]
    if disable:
        rules = [rule for rule in rules if rule.name not in disable]

    for pattern in user_patterns:
        rules.append(KeepRule(f"config:{pattern}", re.compile(pattern)))
    return tuple(rules)


def match_keep_rule(comment: Comment, rules: tuple[KeepRule, ...]) -> str | None:
    for rule in rules:
        if rule.kinds is not None and comment.kind not in rule.kinds:
            continue
        if rule.max_line is not None and comment.line > rule.max_line:
            continue
        if rule.test.search(comment.text):
            return rule.name
    return None


def has_ignore_file_marker(source: str) -> bool:
    return IGNORE_FILE_MARKER in source[:4096]


def apply_keep_next_line(comments: list[Comment]) -> set[int]:
    forced: set[int] = set()
    for index, current in enumerate(comments):
        if KEEP_NEXT_MARKER not in current.text:
            continue
        if index + 1 < len(comments):
            forced.add(comments[index + 1].start)
    return forced
