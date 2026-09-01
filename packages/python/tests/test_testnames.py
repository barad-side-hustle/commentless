from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest

from commentless.testnames import (
    DraftOptions,
    body_of,
    detect_test_framework,
    draft_test_names,
    group_comments,
    looks_like_code,
    render_test_file,
    to_class_name,
    to_identifier,
    to_test_names,
)
from commentless.types import Comment, FileResult
from helpers import write


def comment(text: str, *, line: int = 1, column: int = 1, kind: str = "comment") -> Comment:
    return Comment(start=0, end=0, line=line, column=column, kind=kind, text=text)  # type: ignore[arg-type]


class TestBodyOf:
    def test_strips_the_hash(self) -> None:
        assert body_of(comment("#  a note  ")) == "a note"

    def test_strips_repeated_hashes(self) -> None:
        assert body_of(comment("### a banner")) == "a banner"

    def test_unwraps_a_docstring(self) -> None:
        assert body_of(comment('"""A doc."""', kind="docstring")) == "A doc."

    def test_joins_docstring_lines(self) -> None:
        text = '"""First line.\n\n    Second line.\n    """'
        assert body_of(comment(text, kind="docstring")) == "First line. Second line."

    def test_drops_doctest_and_sphinx_lines(self) -> None:
        text = '"""Doc.\n\n    :param x: the x\n    >>> f(1)\n    1\n    """'
        assert body_of(comment(text, kind="docstring")) == "Doc. 1"

    def test_drops_google_section_headers(self) -> None:
        text = '"""Doc.\n\n    Args:\n        x: the x\n    """'
        assert "Args" not in body_of(comment(text, kind="docstring"))

    def test_handles_a_prefixed_docstring(self) -> None:
        assert body_of(comment('r"""Raw doc."""', kind="docstring")) == "Raw doc."


class TestLooksLikeCode:
    @pytest.mark.parametrize(
        "text",
        [
            "def helper():",
            "class Widget:",
            "import os",
            "from x import y",
            "return value",
            "x = 1",
            "self.value = 1",
            "@decorator",
            "if x:",
            "helper()",
            "https://example.com/docs",
            ">>> f(1)",
            "def f(x) -> int:",
        ],
    )
    def test_recognises_code(self, text: str) -> None:
        assert looks_like_code(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "bails out when the cache is cold",
            "this is a plain sentence",
            "we retry three times",
        ],
    )
    def test_leaves_prose_alone(self, text: str) -> None:
        assert looks_like_code(text) is False


class TestToTestNames:
    def test_turns_a_sentence_into_a_name(self) -> None:
        assert to_test_names(comment("# Bails out when the cache is cold.")) == [
            "bails out when the cache is cold"
        ]

    def test_splits_multiple_sentences(self) -> None:
        names = to_test_names(comment("# Retries twice. Then it gives up."))
        assert names == ["retries twice", "then it gives up"]

    def test_strips_a_todo_label(self) -> None:
        assert to_test_names(comment("# TODO: handle the empty case")) == ["handle the empty case"]

    def test_strips_a_fixme_label(self) -> None:
        assert to_test_names(comment("# FIXME - retry on timeout")) == ["retry on timeout"]

    def test_drops_commented_out_code(self) -> None:
        assert to_test_names(comment("# x = 1")) == []

    def test_drops_a_pure_separator(self) -> None:
        assert to_test_names(comment("# ------------")) == []

    def test_joins_a_group_of_comments(self) -> None:
        names = to_test_names(comment("# Bails out when"), comment("# the cache is cold."))
        assert names == ["bails out when the cache is cold"]

    def test_keeps_an_acronym_capitalised(self) -> None:
        assert to_test_names(comment("# HTTP errors are retried")) == ["HTTP errors are retried"]

    def test_reads_a_docstring(self) -> None:
        assert to_test_names(comment('"""Loads the config."""', kind="docstring")) == [
            "loads the config"
        ]


class TestGroupComments:
    def test_groups_a_consecutive_prose_block(self) -> None:
        comments = [
            comment("# first line", line=1, column=1),
            comment("# second line", line=2, column=1),
            comment("# third line", line=3, column=1),
        ]
        assert [len(group) for group in group_comments(comments)] == [3]

    def test_breaks_on_a_gap(self) -> None:
        comments = [comment("# a", line=1), comment("# b", line=3)]
        assert [len(group) for group in group_comments(comments)] == [1, 1]

    def test_breaks_on_a_different_column(self) -> None:
        comments = [comment("# a", line=1, column=1), comment("# b", line=2, column=5)]
        assert [len(group) for group in group_comments(comments)] == [1, 1]

    def test_breaks_on_commented_out_code(self) -> None:
        comments = [comment("# a note", line=1), comment("# x = 1", line=2)]
        assert [len(group) for group in group_comments(comments)] == [1, 1]

    def test_never_groups_a_docstring(self) -> None:
        comments = [
            comment('"""A."""', line=1, kind="docstring"),
            comment('"""B."""', line=2, kind="docstring"),
        ]
        assert [len(group) for group in group_comments(comments)] == [1, 1]


class TestIdentifiers:
    def test_builds_a_snake_case_method_name(self) -> None:
        assert to_identifier("bails out when the cache is cold") == (
            "test_bails_out_when_the_cache_is_cold"
        )

    def test_strips_punctuation(self) -> None:
        assert to_identifier("retries — twice!") == "test_retries_twice"

    def test_truncates_on_a_word_boundary(self) -> None:
        name = to_identifier("a " * 80)
        assert name.startswith("test_a_a")
        assert len(f"    def {name}(self) -> None: ...") <= 88
        assert name.isidentifier()

    def test_falls_back_when_nothing_survives(self) -> None:
        assert to_identifier("!!!") == "test_case"

    def test_builds_a_class_name_from_a_path(self) -> None:
        assert to_class_name("src/commentless/scan.py") == "TestSrcCommentlessScan"

    def test_handles_a_dotted_path(self) -> None:
        assert to_class_name("a-b/c.d.py") == "TestABCD"


class TestRenderTestFile:
    GROUPS: ClassVar[list[tuple[str, list[str]]]] = [
        ("src/app.py", ["bails out when the cache is cold", "retries twice"])
    ]

    def test_renders_pytest_stubs(self) -> None:
        source = render_test_file(self.GROUPS, "pytest")
        assert source.startswith("import pytest\n\n\nclass TestSrcApp:\n")
        assert '@pytest.mark.skip(reason="todo: retries twice")' in source
        assert "def test_retries_twice(self) -> None:" in source
        compile(source, "drafted.py", "exec")

    def test_renders_unittest_stubs(self) -> None:
        source = render_test_file(self.GROUPS, "unittest")
        assert "class TestSrcApp(unittest.TestCase):" in source
        assert '@unittest.skip("todo: retries twice")' in source
        compile(source, "drafted.py", "exec")

    def test_wraps_a_very_long_reason(self) -> None:
        long_name = "it " + "keeps going and going " * 6
        source = render_test_file([("a.py", [long_name.strip()])], "pytest")
        assert "@pytest.mark.skip(\n" in source
        compile(source, "drafted.py", "exec")

    def test_escapes_quotes_and_backslashes(self) -> None:
        source = render_test_file([("a.py", ['it handles "quotes" and \\ slashes'])], "pytest")
        compile(source, "drafted.py", "exec")

    def test_deduplicates_colliding_method_names(self) -> None:
        source = render_test_file([("a.py", ["retries twice", "retries, twice"])], "pytest")
        assert source.count("def test_retries_twice(") == 1
        assert "def test_retries_twice_2(" in source
        compile(source, "drafted.py", "exec")

    def test_deduplicates_colliding_class_names(self) -> None:
        source = render_test_file([("a/b.py", ["one"]), ("a-b.py", ["two"])], "pytest")
        assert "class TestAB:" in source
        assert "class TestAB2:" in source
        compile(source, "drafted.py", "exec")


class TestDetectTestFramework:
    def test_finds_pytest_in_project_dependencies(self, workspace: Path) -> None:
        write(workspace, "pyproject.toml", '[project]\ndependencies = ["pytest>=8"]\n')
        assert detect_test_framework(str(workspace)) == "pytest"

    def test_finds_pytest_in_a_dependency_group(self, workspace: Path) -> None:
        write(workspace, "pyproject.toml", '[dependency-groups]\ndev = ["pytest"]\n')
        assert detect_test_framework(str(workspace)) == "pytest"

    def test_finds_the_pytest_config_table(self, workspace: Path) -> None:
        write(workspace, "pyproject.toml", '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n')
        assert detect_test_framework(str(workspace)) == "pytest"

    def test_finds_poetry_dev_dependencies(self, workspace: Path) -> None:
        write(
            workspace,
            "pyproject.toml",
            '[tool.poetry.group.dev.dependencies]\npytest = "^8.0"\n',
        )
        assert detect_test_framework(str(workspace)) == "pytest"

    def test_finds_a_conftest(self, workspace: Path) -> None:
        write(workspace, "conftest.py", "")
        assert detect_test_framework(str(workspace)) == "pytest"

    def test_finds_pytest_in_requirements(self, workspace: Path) -> None:
        write(workspace, "requirements-dev.txt", "pytest==8.0.0\n")
        assert detect_test_framework(str(workspace)) == "pytest"

    def test_falls_back_to_unittest(self, workspace: Path) -> None:
        write(workspace, "pyproject.toml", '[project]\nname = "demo"\n')
        assert detect_test_framework(str(workspace)) == "unittest"


class TestDraftTestNames:
    def test_drafts_a_file_per_source(self, workspace: Path) -> None:
        files = [
            FileResult(
                file=str(workspace / "src/app.py"),
                removable=[
                    comment("# Bails out when the cache is cold.", line=3),
                    comment("# x = 1", line=8),
                ],
                changed=True,
            )
        ]
        draft = draft_test_names(files, DraftOptions(cwd=str(workspace), framework="pytest"))
        assert draft.files == 1
        assert draft.skipped == 1
        assert [entry.name for entry in draft.drafts] == ["bails out when the cache is cold"]
        assert draft.drafts[0].file == "src/app.py"
        assert draft.drafts[0].line == 3
        compile(draft.source, "drafted.py", "exec")

    def test_skips_files_that_errored(self, workspace: Path) -> None:
        files = [FileResult(file=str(workspace / "bad.py"), error="boom")]
        assert draft_test_names(files, DraftOptions(cwd=str(workspace))).files == 0

    def test_deduplicates_repeated_sentences(self, workspace: Path) -> None:
        files = [
            FileResult(
                file=str(workspace / "a.py"),
                removable=[comment("# Same note.", line=1), comment("# Same note.", line=9)],
                changed=True,
            )
        ]
        draft = draft_test_names(files, DraftOptions(cwd=str(workspace)))
        assert len(draft.drafts) == 1

    def test_returns_nothing_when_no_prose_survives(self, workspace: Path) -> None:
        files = [
            FileResult(file=str(workspace / "a.py"), removable=[comment("# x = 1")], changed=True)
        ]
        draft = draft_test_names(files, DraftOptions(cwd=str(workspace)))
        assert draft.source == ""
        assert draft.drafts == []
