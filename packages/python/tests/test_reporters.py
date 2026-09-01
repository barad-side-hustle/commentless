from __future__ import annotations

import json

import pytest

from commentless.reporters import REPORTERS, ReportContext, report, summary_line
from commentless.types import Comment, FileResult, RunResult, RunSummary


def build(**overrides: object) -> RunResult:
    summary = RunSummary(
        mode="check",
        discovered=3,
        parsed=3,
        cached=0,
        files_with_comments=1,
        comments_removed=2,
        comments_kept=1,
        errors=0,
        duration_ms=12,
    )
    files = [
        FileResult(
            file="/repo/src/app.py",
            removable=[
                Comment(start=0, end=8, line=1, column=1, kind="comment", text="# a note"),
                Comment(start=20, end=32, line=4, column=5, kind="docstring", text='"""Doc."""'),
            ],
            kept_count=1,
            changed=True,
        )
    ]
    result = RunResult(summary=summary, files=files, exit_code=1)
    for key, value in overrides.items():
        object.__setattr__(result, key, value)
    return result


CONTEXT = ReportContext(cwd="/repo")


class TestSummaryLine:
    def test_reads_naturally(self) -> None:
        assert summary_line(build()) == (
            "3 files scanned · 2 comments to remove in 1 file, 1 kept · 12ms"
        )

    def test_says_removed_in_write_mode(self) -> None:
        result = build()
        object.__setattr__(result.summary, "mode", "write")
        assert "2 comments removed" in summary_line(result)

    def test_mentions_cached_and_errors(self) -> None:
        result = build()
        object.__setattr__(result.summary, "cached", 4)
        object.__setattr__(result.summary, "errors", 1)
        line = summary_line(result)
        assert "4 cached" in line
        assert "1 error" in line


class TestPretty:
    def test_lists_every_comment_with_a_location(self) -> None:
        output = report("pretty", build(), CONTEXT)
        assert "src/app.py" in output
        assert "src/app.py:1:1  # a note" in output
        assert "src/app.py:4:5" in output
        assert output.rstrip().endswith(
            "Run `commentless --write` to remove them, or keep one with `commentless-keep`."
        )

    def test_quiet_hides_the_individual_comments(self) -> None:
        output = report("pretty", build(), ReportContext(cwd="/repo", quiet=True))
        assert "src/app.py" in output
        assert "# a note" not in output

    def test_verbose_shows_the_kept_count(self) -> None:
        output = report("pretty", build(), ReportContext(cwd="/repo", verbose=True))
        assert "[1 kept]" in output

    def test_shows_an_error_line(self) -> None:
        result = build()
        object.__setattr__(
            result, "files", [FileResult(file="/repo/bad.py", error="could not tokenize")]
        )
        assert "bad.py could not tokenize" in report("pretty", result, CONTEXT)

    def test_uses_colour_only_when_asked(self) -> None:
        plain = report("pretty", build(), CONTEXT)
        coloured = report("pretty", build(), ReportContext(cwd="/repo", color=True))
        assert "\x1b[" not in plain
        assert "\x1b[" in coloured


class TestGithub:
    def test_emits_one_annotation_per_comment(self) -> None:
        lines = report("github", build(), CONTEXT).split("\n")
        assert lines[0].startswith("::error file=src/app.py,line=1,col=1,title=commentless::")
        assert "Remove this comment" in lines[0]
        assert "Remove this docstring" in lines[1]
        assert lines[-1].startswith("::notice title=commentless::")

    def test_escapes_reserved_characters(self) -> None:
        result = build()
        object.__setattr__(
            result,
            "files",
            [
                FileResult(
                    file="/repo/a.py",
                    removable=[
                        Comment(
                            start=0, end=1, line=1, column=1, kind="comment", text="# a: b%c\nd"
                        )
                    ],
                    changed=True,
                )
            ],
        )
        line = report("github", result, CONTEXT).split("\n")[0]
        assert "%3A" in line
        assert "%25" in line
        assert "\n" not in line


class TestJson:
    def test_is_machine_readable(self) -> None:
        payload = json.loads(report("json", build(), CONTEXT))
        assert payload["version"] == 1
        assert payload["language"] == "python"
        assert payload["exitCode"] == 1
        assert payload["summary"]["commentsRemoved"] == 2
        assert payload["files"][0]["file"] == "src/app.py"
        assert payload["files"][0]["comments"][1]["kind"] == "docstring"

    def test_includes_errors(self) -> None:
        result = build()
        object.__setattr__(result, "files", [FileResult(file="/repo/bad.py", error="boom")])
        payload = json.loads(report("json", result, CONTEXT))
        assert payload["files"][0]["error"] == "boom"


class TestSummaryReporter:
    def test_prints_only_the_summary_line(self) -> None:
        assert report("summary", build(), CONTEXT) == summary_line(build())


@pytest.mark.parametrize("reporter", REPORTERS)
def test_every_reporter_produces_output(reporter: str) -> None:
    assert report(reporter, build(), CONTEXT)  # type: ignore[arg-type]
