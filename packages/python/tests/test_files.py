from __future__ import annotations

from pathlib import Path

import pytest

from commentless.files import (
    DiscoverOptions,
    DiscoveryError,
    build_ignore_filter,
    discover_files,
    git_root,
)
from helpers import git, git_commit, git_init, write


def options(root: Path, **overrides: object) -> DiscoverOptions:
    base: dict[str, object] = {
        "cwd": str(root),
        "paths": (".",),
        "extensions": ("py", "pyi"),
        "ignore": (),
        "ignore_file": ".commentlessignore",
        "gitignore": True,
        "mode": "all",
        "base": None,
    }
    base.update(overrides)
    return DiscoverOptions(**base)  # type: ignore[arg-type]


def names(root: Path, found: list[str]) -> list[str]:
    resolved = Path(root).resolve()
    return sorted(str(Path(entry).resolve().relative_to(resolved)) for entry in found)


class TestOutsideGit:
    def test_walks_the_tree(self, workspace: Path) -> None:
        write(workspace, "a.py", "x = 1\n")
        write(workspace, "pkg/b.py", "x = 1\n")
        write(workspace, "pkg/c.txt", "not python\n")
        assert names(workspace, discover_files(options(workspace))) == ["a.py", "pkg/b.py"]

    def test_honours_the_extension_list(self, workspace: Path) -> None:
        write(workspace, "a.py", "x = 1\n")
        write(workspace, "a.pyi", "x: int\n")
        found = discover_files(options(workspace, extensions=("pyi",)))
        assert names(workspace, found) == ["a.pyi"]

    def test_prunes_virtualenvs_and_caches(self, workspace: Path) -> None:
        write(workspace, "a.py", "x = 1\n")
        write(workspace, ".venv/lib/dep.py", "x = 1\n")
        write(workspace, "__pycache__/stale.py", "x = 1\n")
        write(workspace, "node_modules/pkg/x.py", "x = 1\n")
        assert names(workspace, discover_files(options(workspace))) == ["a.py"]

    def test_honours_an_ignore_pattern(self, workspace: Path) -> None:
        write(workspace, "a.py", "x = 1\n")
        write(workspace, "gen/b.py", "x = 1\n")
        found = discover_files(options(workspace, ignore=("gen/**",)))
        assert names(workspace, found) == ["a.py"]

    def test_honours_the_ignore_file(self, workspace: Path) -> None:
        write(workspace, "a.py", "x = 1\n")
        write(workspace, "vendor/b.py", "x = 1\n")
        write(workspace, ".commentlessignore", "vendor/\n")
        assert names(workspace, discover_files(options(workspace))) == ["a.py"]

    def test_ignore_file_can_be_switched_off(self, workspace: Path) -> None:
        write(workspace, "a.py", "x = 1\n")
        write(workspace, "vendor/b.py", "x = 1\n")
        write(workspace, ".commentlessignore", "vendor/\n")
        found = discover_files(options(workspace, ignore_file=None))
        assert names(workspace, found) == ["a.py", "vendor/b.py"]

    def test_limits_results_to_the_requested_paths(self, workspace: Path) -> None:
        write(workspace, "a.py", "x = 1\n")
        write(workspace, "pkg/b.py", "x = 1\n")
        found = discover_files(options(workspace, paths=("pkg",)))
        assert names(workspace, found) == ["pkg/b.py"]

    def test_a_git_only_mode_fails_outside_a_repository(self, workspace: Path) -> None:
        with pytest.raises(DiscoveryError, match="needs a git repository"):
            discover_files(options(workspace, mode="staged"))

    def test_build_ignore_filter_always_blocks_dot_git(self, workspace: Path) -> None:
        matcher = build_ignore_filter(options(workspace))
        assert matcher.match_file(".git/config") is True
        assert matcher.match_file("a.py") is False


class TestInsideGit:
    def test_honours_gitignore(self, workspace: Path) -> None:
        git_init(workspace)
        write(workspace, "a.py", "x = 1\n")
        write(workspace, "build/b.py", "x = 1\n")
        write(workspace, ".gitignore", "build/\n")
        assert names(workspace, discover_files(options(workspace))) == ["a.py"]

    def test_sees_gitignored_files_when_gitignore_is_off(self, workspace: Path) -> None:
        git_init(workspace)
        write(workspace, "a.py", "x = 1\n")
        write(workspace, "build/b.py", "x = 1\n")
        write(workspace, ".gitignore", "build/\n")
        found = discover_files(options(workspace, gitignore=False))
        assert names(workspace, found) == ["a.py", "build/b.py"]

    def test_includes_untracked_files(self, workspace: Path) -> None:
        git_init(workspace)
        write(workspace, "a.py", "x = 1\n")
        git_commit(workspace)
        write(workspace, "b.py", "x = 1\n")
        assert names(workspace, discover_files(options(workspace))) == ["a.py", "b.py"]

    def test_staged_limits_to_the_index(self, workspace: Path) -> None:
        git_init(workspace)
        write(workspace, "a.py", "x = 1\n")
        write(workspace, "b.py", "x = 1\n")
        git_commit(workspace)
        write(workspace, "a.py", "x = 2\n")
        git(workspace, "add", "a.py")
        write(workspace, "b.py", "x = 2\n")
        found = discover_files(options(workspace, mode="staged"))
        assert names(workspace, found) == ["a.py"]

    def test_changed_limits_to_the_diff_against_a_base(self, workspace: Path) -> None:
        git_init(workspace)
        write(workspace, "a.py", "x = 1\n")
        write(workspace, "b.py", "x = 1\n")
        git_commit(workspace)
        git(workspace, "checkout", "-q", "-b", "feature")
        write(workspace, "b.py", "x = 2\n")
        git_commit(workspace, "change b")
        found = discover_files(options(workspace, mode="changed", base="main"))
        assert names(workspace, found) == ["b.py"]

    def test_changed_reports_a_bad_base(self, workspace: Path) -> None:
        git_init(workspace)
        write(workspace, "a.py", "x = 1\n")
        git_commit(workspace)
        with pytest.raises(DiscoveryError, match="does not resolve"):
            discover_files(options(workspace, mode="changed", base="nope"))

    def test_resolves_paths_from_a_subdirectory(self, workspace: Path) -> None:
        git_init(workspace)
        write(workspace, "pkg/a.py", "x = 1\n")
        write(workspace, "other/b.py", "x = 1\n")
        git_commit(workspace)
        found = discover_files(options(workspace / "pkg"))
        assert names(workspace / "pkg", found) == ["a.py"]

    def test_git_root_finds_the_top_level(self, workspace: Path) -> None:
        git_init(workspace)
        write(workspace, "pkg/a.py", "x = 1\n")
        assert Path(git_root(str(workspace / "pkg")) or "") == workspace.resolve()
