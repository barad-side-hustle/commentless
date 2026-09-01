from __future__ import annotations

import json
from pathlib import Path

import pytest

import commentless
from commentless.cli import main
from helpers import write


def run_cli(*argv: str, capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


class TestMeta:
    def test_help_exits_zero(self, capsys: pytest.CaptureFixture[str]) -> None:
        code, out, _ = run_cli("--help", capsys=capsys)
        assert code == 0
        assert "Strip comments from Python" in out
        assert "--docstrings" in out

    def test_version_prints_the_version(self, capsys: pytest.CaptureFixture[str]) -> None:
        from commentless.version import VERSION

        code, out, _ = run_cli("--version", capsys=capsys)
        assert code == 0
        assert out.strip() == VERSION

    def test_list_keep_rules_describes_every_rule(self, capsys: pytest.CaptureFixture[str]) -> None:
        from commentless.keep import KEEP_RULE_NAMES

        code, out, _ = run_cli("--list-keep-rules", capsys=capsys)
        assert code == 0
        for name in KEEP_RULE_NAMES:
            assert name in out

    def test_an_unknown_flag_is_a_usage_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        code, _, err = run_cli("--nope", capsys=capsys)
        assert code == 2
        assert "commentless --help" in err

    def test_the_public_api_is_importable(self) -> None:
        for name in commentless.__all__:
            assert hasattr(commentless, name), name


class TestUsageErrors:
    def test_check_and_write_conflict(
        self, chdir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code, _, err = run_cli("--check", "--write", capsys=capsys)
        assert code == 2
        assert "mutually exclusive" in err

    def test_staged_and_changed_conflict(
        self, chdir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code, _, _err = run_cli("--staged", "--changed", capsys=capsys)
        assert code == 2

    def test_init_takes_no_paths(self, chdir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        code, _, err = run_cli("init", "src", capsys=capsys)
        assert code == 2
        assert "init takes no paths" in err

    def test_an_unknown_keep_rule_is_reported(
        self, chdir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code, _, err = run_cli("--check", "--no-keep", "nope", capsys=capsys)
        assert code == 2
        assert "unknown keep rule" in err

    def test_an_unknown_reporter_is_reported(
        self, chdir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code, _, _err = run_cli("--check", "--reporter", "xml", capsys=capsys)
        assert code == 2

    def test_a_bad_max_allowed_is_reported(
        self, chdir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code, _, err = run_cli("--check", "--max-allowed", "-3", capsys=capsys)
        assert code == 2
        assert "--max-allowed" in err

    def test_an_empty_ext_list_is_reported(
        self, chdir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code, _, _err = run_cli("--check", "--ext", " , ", capsys=capsys)
        assert code == 2

    def test_an_invalid_config_is_reported(
        self, chdir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write(chdir, "commentless.config.json", json.dumps({"nope": 1}))
        code, _, err = run_cli("--check", capsys=capsys)
        assert code == 2
        assert "unknown option" in err

    def test_a_git_only_mode_outside_git_is_reported(
        self, chdir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code, _, _err = run_cli("--check", "--staged", capsys=capsys)
        assert code in (1, 2)


class TestRunning:
    def test_check_reports_and_fails(self, chdir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        write(chdir, "a.py", "# gone\nx = 1\n")
        code, out, _ = run_cli("--check", capsys=capsys)
        assert code == 1
        assert "a.py:1:1" in out

    def test_write_rewrites_and_passes(
        self, chdir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        target = write(chdir, "a.py", "# gone\nx = 1\n")
        code, _, _ = run_cli(capsys=capsys)
        assert code == 0
        assert target.read_text() == "x = 1\n"

    def test_dry_run_always_passes(self, chdir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        target = write(chdir, "a.py", "# gone\nx = 1\n")
        code, _, _ = run_cli("--dry-run", capsys=capsys)
        assert code == 0
        assert target.read_text() == "# gone\nx = 1\n"

    def test_docstrings_is_opt_in(self, chdir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        write(chdir, "a.py", '"""Doc."""\nx = 1\n')
        assert run_cli("--check", capsys=capsys)[0] == 0
        assert run_cli("--check", "--docstrings", capsys=capsys)[0] == 1

    def test_max_allowed_ratchets(self, chdir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        write(chdir, "a.py", "# one\n# two\n")
        assert run_cli("--check", "--max-allowed", "2", capsys=capsys)[0] == 0
        assert run_cli("--check", "--max-allowed", "1", capsys=capsys)[0] == 1

    def test_a_path_limits_the_scope(self, chdir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        write(chdir, "keep/a.py", "# gone\n")
        write(chdir, "skip/b.py", "# gone\n")
        code, out, _ = run_cli("--check", "keep", capsys=capsys)
        assert code == 1
        assert "keep/a.py" in out
        assert "skip/b.py" not in out

    def test_list_files_prints_the_resolved_list(
        self, chdir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write(chdir, "a.py", "x = 1\n")
        write(chdir, "pkg/b.py", "x = 1\n")
        code, out, _ = run_cli("--list-files", capsys=capsys)
        assert code == 0
        assert out.split() == ["a.py", "pkg/b.py"]

    def test_the_json_reporter_is_parseable(
        self, chdir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write(chdir, "a.py", "# gone\n")
        code, out, _ = run_cli("--check", "--reporter", "json", capsys=capsys)
        assert code == 1
        assert json.loads(out)["summary"]["commentsRemoved"] == 1

    def test_the_github_reporter_annotates(
        self, chdir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write(chdir, "a.py", "# gone\n")
        _, out, _ = run_cli("--check", "--reporter", "github", capsys=capsys)
        assert out.startswith("::error file=a.py,line=1,col=1")

    def test_no_keep_turns_a_rule_off(
        self, chdir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write(chdir, "a.py", "x = 1  # noqa\n")
        assert run_cli("--check", capsys=capsys)[0] == 0
        assert run_cli("--check", "--no-keep", "noqa", capsys=capsys)[0] == 1

    def test_keep_only_narrows_the_allowlist(
        self, chdir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write(chdir, "a.py", "x = 1  # noqa\ny = 2  # nosec\n")
        code, out, _ = run_cli("--check", "--keep-only", "noqa", capsys=capsys)
        assert code == 1
        assert "# nosec" in out
        assert "# noqa" not in out

    def test_a_user_keep_pattern_is_honoured(
        self, chdir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write(chdir, "a.py", "# LEGAL notice\n# ordinary\n")
        code, out, _ = run_cli("--check", "--keep", r"\bLEGAL\b", capsys=capsys)
        assert code == 1
        assert "LEGAL" not in out
        assert "# ordinary" in out

    def test_ignore_skips_a_directory(
        self, chdir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write(chdir, "gen/a.py", "# gone\n")
        assert run_cli("--check", "--ignore", "gen/**", capsys=capsys)[0] == 0

    def test_the_config_file_is_honoured(
        self, chdir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write(chdir, "a.py", "# one\n# two\n")
        write(chdir, "commentless.config.json", json.dumps({"maxAllowed": 2}))
        assert run_cli("--check", capsys=capsys)[0] == 0

    def test_pyproject_config_is_honoured(
        self, chdir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write(chdir, "a.py", '"""Doc."""\nx = 1\n')
        write(chdir, "pyproject.toml", "[tool.commentless]\ndocstrings = true\n")
        assert run_cli("--check", capsys=capsys)[0] == 1

    def test_quiet_hides_the_detail(self, chdir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        write(chdir, "a.py", "# gone\n")
        _, out, _ = run_cli("--check", "--quiet", capsys=capsys)
        assert "# gone" not in out

    def test_collapse_blank_lines_tidies_up(
        self, chdir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        target = write(chdir, "a.py", "x = 1\n\n\n\n\n# gone\ny = 2\n")
        run_cli("--collapse-blank-lines", capsys=capsys)
        assert target.read_text() == "x = 1\n\n\ny = 2\n"

    def test_a_broken_file_exits_one(self, chdir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        write(chdir, "a.py", 'x = """open\n# note\n')
        code, out, _ = run_cli("--check", capsys=capsys)
        assert code == 1
        assert "✗" in out


class TestToTestNames:
    def test_drafts_stubs_and_reports_them(
        self, chdir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write(chdir, "a.py", "# Bails out when the cache is cold.\nx = 1\n")
        code, _, err = run_cli("--check", "--to-test-names", "tests/test_todo.py", capsys=capsys)

        assert code == 1
        assert "Drafted 1 test name" in err
        source = (chdir / "tests/test_todo.py").read_text()
        assert "bails_out_when_the_cache_is_cold" in source
        compile(source, "drafted.py", "exec")

    def test_uses_pytest_when_the_project_does(
        self, chdir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write(chdir, "pyproject.toml", '[project]\ndependencies = ["pytest"]\n')
        write(chdir, "a.py", "# Bails out early.\n")
        run_cli("--check", "--to-test-names", "test_todo.py", capsys=capsys)
        assert (chdir / "test_todo.py").read_text().startswith("import pytest")

    def test_refuses_to_overwrite_without_force(
        self, chdir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write(chdir, "test_todo.py", "")
        write(chdir, "a.py", "# A note.\n")
        code, _, err = run_cli("--check", "--to-test-names", "test_todo.py", capsys=capsys)
        assert code == 2
        assert "--force" in err

    def test_force_overwrites(self, chdir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        write(chdir, "test_todo.py", "stale = True\n")
        write(chdir, "a.py", "# A note.\n")
        code, _, _ = run_cli("--check", "--to-test-names", "test_todo.py", "--force", capsys=capsys)
        assert code == 1
        assert "stale" not in (chdir / "test_todo.py").read_text()

    def test_says_so_when_there_is_nothing_to_draft(
        self, chdir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write(chdir, "a.py", "x = 1\n")
        code, _, err = run_cli("--check", "--to-test-names", "test_todo.py", capsys=capsys)
        assert code == 0
        assert "No comments left to draft" in err

    def test_does_not_apply_to_init(self, chdir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        code, _, err = run_cli("init", "--to-test-names", "x.py", capsys=capsys)
        assert code == 2
        assert "does not apply to init" in err


class TestInitCommand:
    def test_writes_a_config(self, chdir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        write(chdir, "a.py", "# one\n")
        code, out, _ = run_cli("init", "--no-pre-commit", capsys=capsys)
        assert code == 0
        assert "Wrote commentless.config.json" in out
        assert json.loads((chdir / "commentless.config.json").read_text())["maxAllowed"] == 1

    def test_refuses_to_overwrite(self, chdir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        write(chdir, "commentless.config.json", "{}")
        code, out, _ = run_cli("init", "--no-pre-commit", capsys=capsys)
        assert code == 2
        assert "already exists" in out

    def test_pre_commit_flags_conflict(
        self, chdir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code, _, err = run_cli("init", "--pre-commit", "--no-pre-commit", capsys=capsys)
        assert code == 2
        assert "mutually exclusive" in err

    def test_pyproject_writes_the_table(
        self, chdir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write(chdir, "pyproject.toml", '[project]\nname = "demo"\n')
        code, _, _ = run_cli("init", "--pyproject", "--no-pre-commit", capsys=capsys)
        assert code == 0
        assert "[tool.commentless]" in (chdir / "pyproject.toml").read_text()
