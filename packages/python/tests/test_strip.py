from __future__ import annotations

import ast
from typing import ClassVar

import pytest

from commentless.scan import scan_source
from commentless.strip import collapse_blank_lines, strip_comments
from helpers import scan_options


def clean(source: str, *, docstrings: bool = False, collapse: bool = False) -> str:
    result = scan_source(source, scan_options(docstrings=docstrings))
    return strip_comments(source, result.removable, collapse_blank_lines_option=collapse)


class TestStripComments:
    def test_returns_the_source_untouched_when_nothing_is_removable(self) -> None:
        source = "x = 1\n"
        assert strip_comments(source, []) == source

    def test_removes_a_whole_comment_line_including_the_newline(self) -> None:
        assert clean("x = 1\n# gone\ny = 2\n") == "x = 1\ny = 2\n"

    def test_removes_a_trailing_comment_and_the_space_before_it(self) -> None:
        assert clean("x = 1  # gone\n") == "x = 1\n"

    def test_removes_an_indented_comment_line_entirely(self) -> None:
        assert clean("def f():\n    # gone\n    return 1\n") == "def f():\n    return 1\n"

    def test_preserves_crlf_line_endings(self) -> None:
        assert clean("x = 1\r\n# gone\r\ny = 2\r\n") == "x = 1\r\ny = 2\r\n"

    def test_preserves_a_byte_order_mark(self) -> None:
        assert clean("﻿# gone\nx = 1\n") == "﻿x = 1\n"

    def test_removes_a_comment_at_end_of_file_without_a_newline(self) -> None:
        assert clean("x = 1\n# gone") == "x = 1\n"

    def test_handles_consecutive_comment_lines(self) -> None:
        assert clean("# a\n# b\n# c\nx = 1\n") == "x = 1\n"

    def test_leaves_a_body_that_would_not_parse(self) -> None:
        source = "def f():\n    # only a comment\n    pass\n"
        assert clean(source) == "def f():\n    pass\n"


class TestCollapseBlankLines:
    def test_trims_trailing_whitespace(self) -> None:
        assert collapse_blank_lines("x = 1   \ny = 2\t\n") == "x = 1\ny = 2\n"

    def test_collapses_three_or_more_blank_lines_to_two(self) -> None:
        assert collapse_blank_lines("a\n\n\n\n\n\nb\n") == "a\n\n\nb\n"

    def test_leaves_the_two_blank_lines_pep8_wants_between_definitions(self) -> None:
        source = "def a():\n    pass\n\n\ndef b():\n    pass\n"
        assert collapse_blank_lines(source) == source

    def test_leaves_one_blank_line_alone(self) -> None:
        source = "a\n\nb\n"
        assert collapse_blank_lines(source) == source

    def test_works_with_crlf(self) -> None:
        assert collapse_blank_lines("a\r\n\r\n\r\n\r\n\r\nb\r\n") == "a\r\n\r\n\r\nb\r\n"


class TestOutputStaysValidPython:
    SOURCES: ClassVar[list[str]] = [
        '#!/usr/bin/env python3\n"""Doc."""\nimport os  # noqa\n\n\n# note\ndef f():\n    """Doc."""\n    # note\n    return os\n',
        'class A:\n    """Doc."""\n\n    def m(self):\n        """Only."""\n',
        "def f():\n    x = 1  # note\n    if x:  # note\n        return x  # note\n    return 0\n",
        "match 1:\n    case 1:  # note\n        pass\n    case _:\n        pass\n",
        'async def f():\n    """Doc."""\n    async with open(\'x\') as fh:  # note\n        return await fh.read()\n',
        'from typing import Protocol\n\n\nclass P(Protocol):\n    """Doc."""\n\n    def m(self) -> int:\n        """Only."""\n',
        "values = [\n    1,  # one\n    2,  # two\n]\n",
        "x = (\n    1  # note\n    + 2\n)\n",
        '@decorator  # note\ndef f():\n    """Doc."""\n    return 1\n',
        'def outer():\n    """Doc."""\n\n    def inner():\n        """Only."""\n\n    return inner\n',
        "if (n := 10) > 5:  # note\n    print(n)  # note\n",
        "total = sum(\n    v  # note\n    for v in range(3)\n)\n",
        "def f():\n    global _cache  # note\n    _cache = 1\n    return lambda x: x  # note\n",
        "try:  # note\n    pass\nexcept ValueError:  # note\n    raise\nfinally:  # note\n    pass\n",
        'class A:\n    """Doc."""\n\n    x: int = 1  # note\n\n    @property\n    def y(self) -> int:\n        """Only."""\n',
        '"""Module doc."""\n\nfrom __future__ import annotations  # note\n\nx = 1\n',
        'def f(\n    a,  # note\n    b,\n):\n    """Doc."""\n    return a + b\n',
        "s = f\"{'a'} # not a comment\"  # a real one\n",
        'def f():\n    """Doc.\n\n    >>> f()\n    1\n    """\n    return 1  # note\n',
    ]

    @pytest.mark.parametrize("source", SOURCES)
    @pytest.mark.parametrize("docstrings", [False, True])
    @pytest.mark.parametrize("collapse", [False, True])
    def test_stripped_output_still_parses(
        self, source: str, docstrings: bool, collapse: bool
    ) -> None:
        output = clean(source, docstrings=docstrings, collapse=collapse)
        ast.parse(output)
