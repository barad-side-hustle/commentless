from __future__ import annotations

import json
from pathlib import Path

from commentless.cache import CleanFileCache, cache_directory, signature_of
from commentless.process import ProcessOptions, process_file
from commentless.run import RunOptions, default_concurrency, run
from helpers import default_keep, write


def options(root: Path, **overrides: object) -> RunOptions:
    base: dict[str, object] = {
        "cwd": str(root),
        "mode": "check",
        "extensions": ("py", "pyi"),
        "keep": default_keep(),
        "cache": False,
    }
    base.update(overrides)
    return RunOptions(**base)  # type: ignore[arg-type]


class TestProcessFile:
    def test_reports_a_clean_file(self, workspace: Path) -> None:
        target = write(workspace, "a.py", "x = 1\n")
        result = process_file(str(target), ProcessOptions(keep=default_keep()))
        assert result.changed is False
        assert result.removable == []

    def test_reports_removable_comments_without_writing(self, workspace: Path) -> None:
        target = write(workspace, "a.py", "# gone\nx = 1\n")
        result = process_file(str(target), ProcessOptions(keep=default_keep()))
        assert result.changed is True
        assert len(result.removable) == 1
        assert target.read_text() == "# gone\nx = 1\n"

    def test_writes_when_asked(self, workspace: Path) -> None:
        target = write(workspace, "a.py", "# gone\nx = 1\n")
        process_file(str(target), ProcessOptions(keep=default_keep(), write=True))
        assert target.read_text() == "x = 1\n"

    def test_counts_kept_comments(self, workspace: Path) -> None:
        target = write(workspace, "a.py", "x = 1  # noqa\n# gone\n")
        result = process_file(str(target), ProcessOptions(keep=default_keep()))
        assert result.kept_count == 1
        assert len(result.removable) == 1

    def test_reports_a_missing_file_as_an_error(self, workspace: Path) -> None:
        result = process_file(str(workspace / "nope.py"), ProcessOptions(keep=default_keep()))
        assert result.error is not None

    def test_reports_a_broken_file_as_an_error(self, workspace: Path) -> None:
        target = write(workspace, "a.py", 'x = """open\n# note\n')
        result = process_file(str(target), ProcessOptions(keep=default_keep()))
        assert result.error is not None
        assert "tokenize" in result.error

    def test_skips_a_file_with_the_ignore_marker(self, workspace: Path) -> None:
        target = write(workspace, "a.py", "# commentless-ignore-file\n# gone\n")
        result = process_file(str(target), ProcessOptions(keep=default_keep(), write=True))
        assert result.changed is False
        assert target.read_text() == "# commentless-ignore-file\n# gone\n"


class TestRun:
    def test_check_fails_when_a_comment_is_found(self, workspace: Path) -> None:
        write(workspace, "a.py", "# gone\nx = 1\n")
        result = run(options(workspace))
        assert result.exit_code == 1
        assert result.summary.comments_removed == 1
        assert result.summary.files_with_comments == 1

    def test_check_passes_under_max_allowed(self, workspace: Path) -> None:
        write(workspace, "a.py", "# one\n# two\nx = 1\n")
        assert run(options(workspace, max_allowed=2)).exit_code == 0
        assert run(options(workspace, max_allowed=1)).exit_code == 1

    def test_dry_run_never_fails_and_never_writes(self, workspace: Path) -> None:
        target = write(workspace, "a.py", "# gone\nx = 1\n")
        result = run(options(workspace, mode="dry-run"))
        assert result.exit_code == 0
        assert result.summary.comments_removed == 1
        assert target.read_text() == "# gone\nx = 1\n"

    def test_write_rewrites_the_file(self, workspace: Path) -> None:
        target = write(workspace, "a.py", "# gone\nx = 1\n")
        result = run(options(workspace, mode="write"))
        assert result.exit_code == 0
        assert target.read_text() == "x = 1\n"

    def test_docstrings_are_opt_in(self, workspace: Path) -> None:
        write(workspace, "a.py", '"""Doc."""\nx = 1\n')
        assert run(options(workspace)).summary.comments_removed == 0
        assert run(options(workspace, docstrings=True)).summary.comments_removed == 1

    def test_an_error_fails_even_in_write_mode(self, workspace: Path) -> None:
        write(workspace, "a.py", 'x = """open\n# note\n')
        result = run(options(workspace, mode="write"))
        assert result.exit_code == 1
        assert result.summary.errors == 1

    def test_an_explicit_file_list_skips_discovery(self, workspace: Path) -> None:
        target = write(workspace, "a.py", "# gone\n")
        write(workspace, "b.py", "# also gone\n")
        result = run(options(workspace, files=(str(target),)))
        assert result.summary.discovered == 1

    def test_the_worker_pool_agrees_with_the_single_process_path(self, workspace: Path) -> None:
        for index in range(60):
            write(workspace, f"pkg/mod_{index}.py", f"# note {index}\nx = {index}  # noqa\n")

        single = run(options(workspace))
        pooled = run(options(workspace, worker_threshold=1, worker_byte_threshold=0, concurrency=2))
        assert single.summary.comments_removed == pooled.summary.comments_removed == 60
        assert single.summary.comments_kept == pooled.summary.comments_kept == 60
        assert [f.file for f in single.files] == [f.file for f in pooled.files]

    def test_the_worker_pool_writes_files(self, workspace: Path) -> None:
        for index in range(30):
            write(workspace, f"pkg/mod_{index}.py", f"# note {index}\nx = {index}\n")
        run(
            options(
                workspace, mode="write", worker_threshold=1, worker_byte_threshold=0, concurrency=2
            )
        )
        assert (workspace / "pkg/mod_0.py").read_text() == "x = 0\n"

    def test_default_concurrency_is_at_least_one(self) -> None:
        assert default_concurrency() >= 1


class TestCache:
    def test_a_clean_file_is_cached_and_skipped(self, workspace: Path) -> None:
        write(workspace, "a.py", "x = 1\n")
        first = run(options(workspace, cache=True))
        assert first.summary.parsed == 1
        assert first.summary.cached == 0

        second = run(options(workspace, cache=True))
        assert second.summary.parsed == 0
        assert second.summary.cached == 1

    def test_a_dirty_file_is_not_cached_under_check(self, workspace: Path) -> None:
        write(workspace, "a.py", "# gone\n")
        run(options(workspace, cache=True))
        assert run(options(workspace, cache=True)).summary.cached == 0

    def test_a_written_file_is_cached(self, workspace: Path) -> None:
        write(workspace, "a.py", "# gone\nx = 1\n")
        run(options(workspace, mode="write", cache=True))
        assert run(options(workspace, cache=True)).summary.cached == 1

    def test_changing_the_signature_invalidates_the_cache(self, workspace: Path) -> None:
        write(workspace, "a.py", "x = 1\n")
        run(options(workspace, cache=True))
        assert run(options(workspace, cache=True, docstrings=True)).summary.cached == 0

    def test_editing_a_file_invalidates_its_entry(self, workspace: Path) -> None:
        target = write(workspace, "a.py", "x = 1\n")
        run(options(workspace, cache=True))
        target.write_text("x = 2\n")
        assert run(options(workspace, cache=True)).summary.cached == 0

    def test_the_cache_lives_under_the_project(self, workspace: Path) -> None:
        assert cache_directory(str(workspace)).endswith(".commentless-cache")

    def test_a_disabled_cache_never_reports_clean(self, workspace: Path) -> None:
        cache = CleanFileCache.disabled()
        assert cache.enabled is False
        cache.mark("a.py", True)
        assert cache.is_clean("a.py") is False

    def test_a_corrupt_cache_file_is_ignored(self, workspace: Path) -> None:
        target = write(workspace, "a.py", "x = 1\n")
        directory = Path(cache_directory(str(workspace)))
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "clean-python.json").write_text("{ not json")
        assert run(options(workspace, cache=True)).summary.parsed == 1
        assert target.exists()

    def test_signature_of_is_stable(self) -> None:
        assert signature_of({"a": 1, "b": 2}) == signature_of({"b": 2, "a": 1})
        assert signature_of({"a": 1}) != signature_of({"a": 2})

    def test_the_cache_file_is_json(self, workspace: Path) -> None:
        write(workspace, "a.py", "x = 1\n")
        run(options(workspace, cache=True))
        payload = json.loads(
            (Path(cache_directory(str(workspace))) / "clean-python.json").read_text()
        )
        assert payload["version"] == 1
        assert len(payload["clean"]) == 1
