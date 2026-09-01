from __future__ import annotations

from collections.abc import Sequence

import pytest

from commentless.scan import (
    DEFAULT_EXTENSIONS,
    ScanError,
    line_starts,
    may_contain_comments,
    scan_source,
    script_kind_for,
)
from commentless.types import Comment
from helpers import scan_options


def texts(comments: Sequence[Comment]) -> list[str]:
    return [comment.text for comment in comments]


class TestFastPaths:
    def test_reports_nothing_for_a_file_without_a_hash(self) -> None:
        result = scan_source("x = 1\ny = 2\n", scan_options())
        assert result.removable == []
        assert result.kept == []

    def test_may_contain_comments_ignores_quotes_unless_docstrings_are_on(self) -> None:
        assert may_contain_comments('x = "no hash"') is False
        assert may_contain_comments('x = "no hash"', docstrings=True) is True
        assert may_contain_comments("x = 1  # yes") is True

    def test_marks_a_file_ignored_when_the_marker_is_present(self) -> None:
        result = scan_source("# commentless-ignore-file\n# gone\n", scan_options())
        assert result.ignored_file is True
        assert result.removable == []

    def test_line_starts_tracks_every_newline(self) -> None:
        assert line_starts("a\nbb\n\nc") == [0, 2, 5, 6]

    def test_default_extensions_cover_python_and_stubs(self) -> None:
        assert DEFAULT_EXTENSIONS == ("py", "pyi")

    @pytest.mark.parametrize(("name", "kind"), [("a.py", "py"), ("a.pyi", "pyi"), ("a", "py")])
    def test_script_kind_for(self, name: str, kind: str) -> None:
        assert script_kind_for(name) == kind


class TestComments:
    def test_finds_a_standalone_comment(self) -> None:
        result = scan_source("# a note\nx = 1\n", scan_options())
        assert texts(result.removable) == ["# a note"]
        assert result.removable[0].line == 1
        assert result.removable[0].column == 1
        assert result.removable[0].kind == "comment"

    def test_finds_a_trailing_comment_with_the_right_column(self) -> None:
        result = scan_source("x = 1  # trailing\n", scan_options())
        assert texts(result.removable) == ["# trailing"]
        assert result.removable[0].column == 8

    def test_leaves_a_hash_inside_a_string_alone(self) -> None:
        source = 'a = "# not a comment"\nb = \'#\'\nc = """multi # line"""\n'
        assert scan_source(source, scan_options()).removable == []

    def test_leaves_a_hash_inside_an_f_string_alone(self) -> None:
        source = 'name = "x"\nvalue = f"{name} # not a comment"\n'
        assert scan_source(source, scan_options()).removable == []

    def test_keeps_the_shebang(self) -> None:
        result = scan_source("#!/usr/bin/env python3\n# a note\n", scan_options())
        assert texts(result.removable) == ["# a note"]

    def test_treats_a_hash_bang_below_line_one_as_a_comment(self) -> None:
        result = scan_source("x = 1\n#!not a shebang\n", scan_options())
        assert texts(result.removable) == ["#!not a shebang"]

    def test_handles_a_byte_order_mark(self) -> None:
        source = "﻿# a note\nx = 1\n"
        result = scan_source(source, scan_options())
        comment = result.removable[0]
        assert source[comment.start : comment.end] == "# a note"

    def test_handles_crlf_line_endings(self) -> None:
        source = "x = 1\r\n# a note\r\ny = 2\r\n"
        comment = scan_source(source, scan_options()).removable[0]
        assert source[comment.start : comment.end] == "# a note"
        assert comment.line == 2

    def test_handles_non_ascii_before_a_comment(self) -> None:
        source = 'value = "héllo wörld"  # a note\n'
        comment = scan_source(source, scan_options()).removable[0]
        assert source[comment.start : comment.end] == "# a note"

    def test_raises_a_scan_error_on_an_unterminated_string(self) -> None:
        with pytest.raises(ScanError):
            scan_source('x = """open\n# a note\n', scan_options())


class TestKeepRules:
    @pytest.mark.parametrize(
        ("comment", "rule"),
        [
            ("# noqa", "noqa"),
            ("# noqa: E501", "noqa"),
            ("# type: ignore[arg-type]", "type-ignore"),
            ("# type: List[int]", "type-comment"),
            ("# pragma: no cover", "pragma"),
            ("# nosec", "bandit"),
            ("# fmt: off", "fmt"),
            ("# isort: skip", "isort"),
            ("# yapf: disable", "yapf"),
            ("# pylint: disable=all", "pylint"),
            ("# pyright: ignore", "pyright"),
            ("# mypy: disallow-untyped-defs", "mypy"),
            ("# ruff: isort: on", "ruff"),
            ("# pytype: disable=attribute-error", "pytype"),
            ("# noinspection PyUnresolvedReferences", "noinspection"),
            ("# SPDX-License-Identifier: MIT", "license"),
            ("# commentless-keep", "commentless"),
        ],
    )
    def test_keeps_directive_comments(self, comment: str, rule: str) -> None:
        result = scan_source(f"x = 1\n{comment}\n", scan_options())
        assert result.removable == []
        assert result.kept[0].kept_by == rule

    def test_keeps_the_encoding_cookie_only_near_the_top(self) -> None:
        top = scan_source("# -*- coding: utf-8 -*-\nx = 1\n", scan_options())
        assert top.kept[0].kept_by == "coding"

        deep = scan_source("x = 1\ny = 2\n# -*- coding: utf-8 -*-\n", scan_options())
        assert texts(deep.removable) == ["# -*- coding: utf-8 -*-"]

    def test_keeps_cython_directives(self) -> None:
        result = scan_source("# cython: language_level=3\nx = 1\n", scan_options())
        assert result.kept[0].kept_by == "cython"

    def test_keep_next_line_protects_the_following_comment(self) -> None:
        source = "# commentless-keep-next-line\n# protected\n# not protected\n"
        result = scan_source(source, scan_options())
        assert texts(result.removable) == ["# not protected"]
        assert result.kept[1].kept_by == "commentless-keep-next-line"

    def test_a_disabled_rule_stops_keeping(self) -> None:
        from commentless.keep import resolve_keep_rules

        keep = resolve_keep_rules(disable=("noqa",))
        result = scan_source("x = 1  # noqa\n", scan_options(keep=keep))
        assert texts(result.removable) == ["# noqa"]

    def test_a_user_pattern_keeps_a_comment(self) -> None:
        from commentless.keep import resolve_keep_rules

        keep = resolve_keep_rules(user_patterns=(r"\bLEGAL\b",))
        result = scan_source("# LEGAL text\n# ordinary\n", scan_options(keep=keep))
        assert texts(result.removable) == ["# ordinary"]
        assert result.kept[0].kept_by == r"config:\bLEGAL\b"


class TestDocstrings:
    SOURCE = '''"""Module docstring."""


class Widget:
    """Class docstring."""

    def method(self):
        """Method docstring."""
        return 1

    def stub(self):
        """Only statement."""


def top():
    """Top docstring."""
    return 2
'''

    def test_leaves_docstrings_alone_by_default(self) -> None:
        result = scan_source(self.SOURCE, scan_options())
        assert result.removable == []

    def test_removes_docstrings_when_asked(self) -> None:
        result = scan_source(self.SOURCE, scan_options(docstrings=True))
        assert texts(result.removable) == [
            '"""Module docstring."""',
            '"""Class docstring."""',
            '"""Method docstring."""',
            '"""Top docstring."""',
        ]

    def test_keeps_a_docstring_that_is_the_only_statement(self) -> None:
        result = scan_source(self.SOURCE, scan_options(docstrings=True))
        sole = [comment for comment in result.kept if comment.kept_by == "sole-statement"]
        assert texts(sole) == ['"""Only statement."""']

    def test_keeps_a_docstring_that_shares_its_line(self) -> None:
        source = '"""Doc."""; x = 1\ny = 2\n'
        result = scan_source(source, scan_options(docstrings=True))
        assert result.removable == []
        assert result.kept[0].kept_by == "inline"

    def test_keeps_a_docstring_with_a_doctest(self) -> None:
        source = '"""Doc.\n\n>>> 1 + 1\n2\n"""\nx = 1\n'
        result = scan_source(source, scan_options(docstrings=True))
        assert result.removable == []
        assert result.kept[0].kept_by == "doctest"

    def test_ignores_a_bare_string_that_is_not_in_docstring_position(self) -> None:
        source = "x = 1\n'not a docstring'\n"
        assert scan_source(source, scan_options(docstrings=True)).removable == []

    def test_ignores_an_f_string_in_docstring_position(self) -> None:
        source = 'def f():\n    f"""not a docstring"""\n    return 1\n'
        assert scan_source(source, scan_options(docstrings=True)).removable == []

    def test_handles_an_async_function(self) -> None:
        source = 'async def f():\n    """Doc."""\n    return 1\n'
        result = scan_source(source, scan_options(docstrings=True))
        assert texts(result.removable) == ['"""Doc."""']

    def test_handles_a_docstring_after_non_ascii_indentation_content(self) -> None:
        source = 'def f():\n    """Dôc wíth ünicode."""\n    return "ü"\n'
        result = scan_source(source, scan_options(docstrings=True))
        comment = result.removable[0]
        assert source[comment.start : comment.end] == '"""Dôc wíth ünicode."""'

    def test_raises_a_scan_error_when_the_file_cannot_be_parsed(self) -> None:
        with pytest.raises(ScanError):
            scan_source('def f(:\n    """doc"""\n', scan_options(docstrings=True))
