from __future__ import annotations

import json
from pathlib import Path

import pytest

from commentless.config import ConfigError, load_config, validate_config
from helpers import write


class TestValidateConfig:
    def test_accepts_an_empty_table(self) -> None:
        assert validate_config({}, "test").ext is None

    def test_accepts_every_known_option(self) -> None:
        config = validate_config(
            {
                "ext": ["py"],
                "ignore": ["gen/**"],
                "ignoreFile": ".myignore",
                "gitignore": False,
                "keep": ["LEGAL"],
                "defaultKeep": False,
                "disableKeep": ["noqa"],
                "keepOnly": ["type-ignore"],
                "collapseBlankLines": True,
                "docstrings": True,
                "maxAllowed": 12,
                "reporter": "github",
                "concurrency": 4,
                "cache": False,
            },
            "test",
        )
        assert config.ext == ["py"]
        assert config.docstrings is True
        assert config.reporter == "github"
        assert config.concurrency == 4

    def test_accepts_snake_case_aliases(self) -> None:
        config = validate_config(
            {"max_allowed": 3, "collapse_blank_lines": True, "disable_keep": ["noqa"]}, "test"
        )
        assert config.maxAllowed == 3
        assert config.collapseBlankLines is True
        assert config.disableKeep == ["noqa"]

    def test_rejects_a_non_table(self) -> None:
        with pytest.raises(ConfigError, match="table of options"):
            validate_config([], "test")

    def test_rejects_an_unknown_option(self) -> None:
        with pytest.raises(ConfigError, match='unknown option "nope"'):
            validate_config({"nope": 1}, "test")

    def test_rejects_a_bad_type(self) -> None:
        with pytest.raises(ConfigError, match='"ext" must be an array of strings'):
            validate_config({"ext": "py"}, "test")

    def test_rejects_a_bad_boolean(self) -> None:
        with pytest.raises(ConfigError, match='"docstrings" must be a boolean'):
            validate_config({"docstrings": "yes"}, "test")

    def test_rejects_a_negative_max_allowed(self) -> None:
        with pytest.raises(ConfigError, match="non-negative integer"):
            validate_config({"maxAllowed": -1}, "test")

    def test_rejects_a_zero_concurrency(self) -> None:
        with pytest.raises(ConfigError, match="at least 1"):
            validate_config({"concurrency": 0}, "test")

    def test_rejects_an_invalid_regex(self) -> None:
        with pytest.raises(ConfigError, match="not a valid regular expression"):
            validate_config({"keep": ["("]}, "test")

    def test_rejects_an_unknown_keep_rule(self) -> None:
        with pytest.raises(ConfigError, match="unknown keep rule"):
            validate_config({"disableKeep": ["nope"]}, "test")

    def test_rejects_an_unknown_reporter(self) -> None:
        with pytest.raises(ConfigError, match="reporter"):
            validate_config({"reporter": "xml"}, "test")

    def test_accepts_false_for_ignore_file(self) -> None:
        assert validate_config({"ignoreFile": False}, "test").ignoreFile is False


class TestLoadConfig:
    def test_returns_an_empty_config_when_nothing_is_found(self, workspace: Path) -> None:
        loaded = load_config(str(workspace))
        assert loaded.source is None
        assert loaded.config.ext is None

    def test_reads_the_json_config(self, workspace: Path) -> None:
        write(workspace, "commentless.config.json", json.dumps({"maxAllowed": 7}))
        assert load_config(str(workspace)).config.maxAllowed == 7

    def test_reads_the_pyproject_table(self, workspace: Path) -> None:
        write(
            workspace, "pyproject.toml", "[tool.commentless]\nmaxAllowed = 9\ndocstrings = true\n"
        )
        loaded = load_config(str(workspace))
        assert loaded.config.maxAllowed == 9
        assert loaded.config.docstrings is True

    def test_reads_snake_case_from_pyproject(self, workspace: Path) -> None:
        write(workspace, "pyproject.toml", "[tool.commentless]\nmax_allowed = 4\n")
        assert load_config(str(workspace)).config.maxAllowed == 4

    def test_prefers_the_json_config_over_pyproject(self, workspace: Path) -> None:
        write(workspace, "commentless.config.json", json.dumps({"maxAllowed": 1}))
        write(workspace, "pyproject.toml", "[tool.commentless]\nmaxAllowed = 2\n")
        assert load_config(str(workspace)).config.maxAllowed == 1

    def test_skips_a_pyproject_without_the_table(self, workspace: Path) -> None:
        write(workspace, "pyproject.toml", '[project]\nname = "demo"\n')
        assert load_config(str(workspace)).source is None

    def test_walks_up_to_a_parent_directory(self, workspace: Path) -> None:
        write(workspace, "commentless.config.json", json.dumps({"maxAllowed": 5}))
        nested = workspace / "a" / "b"
        nested.mkdir(parents=True)
        assert load_config(str(nested)).config.maxAllowed == 5

    def test_reads_an_explicit_path(self, workspace: Path) -> None:
        write(workspace, "custom.json", json.dumps({"maxAllowed": 3}))
        assert load_config(str(workspace), "custom.json").config.maxAllowed == 3

    def test_reads_an_explicit_toml_path(self, workspace: Path) -> None:
        write(workspace, "custom.toml", "[tool.commentless]\nmaxAllowed = 6\n")
        assert load_config(str(workspace), "custom.toml").config.maxAllowed == 6

    def test_reports_a_missing_explicit_path(self, workspace: Path) -> None:
        with pytest.raises(ConfigError, match="config file not found"):
            load_config(str(workspace), "nope.json")

    def test_reports_invalid_json(self, workspace: Path) -> None:
        write(workspace, "commentless.config.json", "{not json")
        with pytest.raises(ConfigError, match="invalid JSON"):
            load_config(str(workspace))

    def test_reports_invalid_toml(self, workspace: Path) -> None:
        write(workspace, "pyproject.toml", "[tool.commentless\n")
        with pytest.raises(ConfigError, match="invalid TOML"):
            load_config(str(workspace))
