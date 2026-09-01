from __future__ import annotations

import json
import tomllib
from pathlib import Path

from commentless.hooks import HOOK_ID, apply_hook, plan_hook
from commentless.init import InitOptions, default_config, init, render_toml_table
from helpers import default_keep, write


def options(root: Path, **overrides: object) -> InitOptions:
    base: dict[str, object] = {
        "cwd": str(root),
        "keep": default_keep(),
        "extensions": ("py", "pyi"),
        "pre_commit": False,
    }
    base.update(overrides)
    return InitOptions(**base)  # type: ignore[arg-type]


class TestInit:
    def test_writes_a_config_baselined_to_today(self, workspace: Path) -> None:
        write(workspace, "a.py", "# one\n# two\nx = 1\n")
        result = init(options(workspace))

        assert result.existed is False
        assert result.found == 2
        assert result.scanned == 1

        config = json.loads((workspace / "commentless.config.json").read_text())
        assert config["maxAllowed"] == 2
        assert config["ext"] == ["py", "pyi"]
        assert config["docstrings"] is False

    def test_strict_pins_max_allowed_to_zero(self, workspace: Path) -> None:
        write(workspace, "a.py", "# one\n")
        init(options(workspace, strict=True))
        config = json.loads((workspace / "commentless.config.json").read_text())
        assert config["maxAllowed"] == 0

    def test_counts_docstrings_when_asked(self, workspace: Path) -> None:
        write(workspace, "a.py", '"""Doc."""\nx = 1\n')
        assert init(options(workspace)).found == 0
        assert init(options(workspace, docstrings=True, force=True)).found == 1

    def test_refuses_to_overwrite(self, workspace: Path) -> None:
        write(workspace, "commentless.config.json", "{}")
        result = init(options(workspace))
        assert result.existed is True
        assert "--force" in result.output

    def test_force_overwrites(self, workspace: Path) -> None:
        write(workspace, "commentless.config.json", "{}")
        assert init(options(workspace, force=True)).existed is False

    def test_mentions_the_docstring_flag_when_it_is_off(self, workspace: Path) -> None:
        write(workspace, "a.py", "x = 1\n")
        assert "--docstrings" in init(options(workspace)).output

    def test_default_config_lists_every_documented_key(self) -> None:
        assert set(default_config()) == {
            "ext",
            "ignore",
            "keep",
            "disableKeep",
            "collapseBlankLines",
            "docstrings",
            "maxAllowed",
            "reporter",
        }


class TestInitPyproject:
    def test_creates_the_table(self, workspace: Path) -> None:
        write(workspace, "pyproject.toml", '[project]\nname = "demo"\n')
        write(workspace, "a.py", "# one\n")
        init(options(workspace, pyproject=True))

        with (workspace / "pyproject.toml").open("rb") as handle:
            parsed = tomllib.load(handle)
        assert parsed["project"]["name"] == "demo"
        assert parsed["tool"]["commentless"]["maxAllowed"] == 1

    def test_refuses_to_overwrite_an_existing_table(self, workspace: Path) -> None:
        write(workspace, "pyproject.toml", "[tool.commentless]\nmaxAllowed = 3\n")
        result = init(options(workspace, pyproject=True))
        assert result.existed is True

    def test_force_replaces_the_table_and_keeps_the_rest(self, workspace: Path) -> None:
        write(
            workspace,
            "pyproject.toml",
            '[project]\nname = "demo"\n\n[tool.commentless]\nmaxAllowed = 3\n\n'
            "[tool.ruff]\nline-length = 88\n",
        )
        write(workspace, "a.py", "# one\n")
        init(options(workspace, pyproject=True, force=True))

        with (workspace / "pyproject.toml").open("rb") as handle:
            parsed = tomllib.load(handle)
        assert parsed["project"]["name"] == "demo"
        assert parsed["tool"]["ruff"]["line-length"] == 88
        assert parsed["tool"]["commentless"]["maxAllowed"] == 1

    def test_renders_valid_toml(self) -> None:
        rendered = render_toml_table(default_config())
        assert tomllib.loads(rendered)["tool"]["commentless"]["reporter"] == "pretty"


class TestPreCommitHook:
    def test_creates_the_file_when_missing(self, workspace: Path) -> None:
        write(workspace, "a.py", "x = 1\n")
        result = init(options(workspace, pre_commit=True))
        assert result.hook_added is True

        text = (workspace / ".pre-commit-config.yaml").read_text()
        assert text.startswith("repos:\n")
        assert f"- id: {HOOK_ID}" in text

    def test_appends_to_an_existing_repos_list(self, workspace: Path) -> None:
        write(
            workspace,
            ".pre-commit-config.yaml",
            "repos:\n  - repo: https://github.com/psf/black\n    rev: 24.1.0\n"
            "    hooks:\n      - id: black\n",
        )
        write(workspace, "a.py", "x = 1\n")
        init(options(workspace, pre_commit=True))

        text = (workspace / ".pre-commit-config.yaml").read_text()
        assert "- id: black" in text
        assert f"- id: {HOOK_ID}" in text
        assert text.index("black") < text.index(HOOK_ID)

    def test_inserts_before_a_trailing_top_level_key(self, workspace: Path) -> None:
        write(
            workspace,
            ".pre-commit-config.yaml",
            "repos:\n  - repo: local\n    hooks:\n      - id: other\n\nci:\n  autofix_prs: true\n",
        )
        write(workspace, "a.py", "x = 1\n")
        init(options(workspace, pre_commit=True))

        text = (workspace / ".pre-commit-config.yaml").read_text()
        assert text.index(HOOK_ID) < text.index("autofix_prs")

    def test_is_a_no_op_when_the_hook_is_already_there(self, workspace: Path) -> None:
        write(
            workspace,
            ".pre-commit-config.yaml",
            f"repos:\n  - repo: local\n    hooks:\n      - id: {HOOK_ID}\n",
        )
        write(workspace, "a.py", "x = 1\n")
        result = init(options(workspace, pre_commit=True))
        assert result.hook_added is False
        assert "already has a commentless hook" in result.output

    def test_no_pre_commit_never_writes(self, workspace: Path) -> None:
        write(workspace, "a.py", "x = 1\n")
        init(options(workspace, pre_commit=False))
        assert not (workspace / ".pre-commit-config.yaml").exists()

    def test_asks_before_writing(self, workspace: Path) -> None:
        write(workspace, "a.py", "x = 1\n")
        asked: list[str] = []

        def confirm(question: str) -> bool:
            asked.append(question)
            return True

        result = init(options(workspace, pre_commit=None, confirm=confirm))
        assert asked == ["Add it?"]
        assert result.hook_added is True

    def test_a_declined_prompt_writes_nothing(self, workspace: Path) -> None:
        write(workspace, "a.py", "x = 1\n")
        result = init(options(workspace, pre_commit=None, confirm=lambda _: False))
        assert result.hook_added is False
        assert not (workspace / ".pre-commit-config.yaml").exists()

    def test_plan_detects_the_existing_indent(self, workspace: Path) -> None:
        write(workspace, ".pre-commit-config.yaml", "repos:\n- repo: local\n  hooks:\n  - id: x\n")
        plan = plan_hook(str(workspace))
        assert plan.block.startswith("- repo: local")

    def test_apply_appends_repos_when_the_key_is_missing(self, workspace: Path) -> None:
        write(workspace, ".pre-commit-config.yaml", "ci:\n  autofix_prs: true\n")
        apply_hook(plan_hook(str(workspace)))
        text = (workspace / ".pre-commit-config.yaml").read_text()
        assert "autofix_prs" in text
        assert "repos:" in text
        assert HOOK_ID in text


class TestHookYamlIsValid:
    def test_a_fresh_file_parses_and_registers_the_hook(self, workspace: Path) -> None:
        import yaml

        write(workspace, "a.py", "x = 1\n")
        init(options(workspace, pre_commit=True))
        parsed = yaml.safe_load((workspace / ".pre-commit-config.yaml").read_text())

        assert [hook["id"] for repo in parsed["repos"] for hook in repo["hooks"]] == [HOOK_ID]
        hook = parsed["repos"][0]["hooks"][0]
        assert hook["language"] == "python"
        assert hook["types"] == ["python"]
        assert hook["additional_dependencies"][0].startswith("commentless==")

    def test_an_appended_hook_parses_alongside_the_others(self, workspace: Path) -> None:
        import yaml

        write(
            workspace,
            ".pre-commit-config.yaml",
            "repos:\n  - repo: https://github.com/psf/black\n    rev: 24.1.0\n"
            "    hooks:\n      - id: black\n\nci:\n  autofix_prs: true\n",
        )
        write(workspace, "a.py", "x = 1\n")
        init(options(workspace, pre_commit=True))
        parsed = yaml.safe_load((workspace / ".pre-commit-config.yaml").read_text())

        ids = [hook["id"] for repo in parsed["repos"] for hook in repo["hooks"]]
        assert ids == ["black", HOOK_ID]
        assert parsed["ci"]["autofix_prs"] is True

    def test_a_zero_indent_file_still_parses(self, workspace: Path) -> None:
        import yaml

        write(
            workspace,
            ".pre-commit-config.yaml",
            "repos:\n- repo: local\n  hooks:\n  - id: other\n    name: other\n"
            "    entry: true\n    language: system\n",
        )
        write(workspace, "a.py", "x = 1\n")
        init(options(workspace, pre_commit=True))
        parsed = yaml.safe_load((workspace / ".pre-commit-config.yaml").read_text())

        ids = [hook["id"] for repo in parsed["repos"] for hook in repo["hooks"]]
        assert ids == ["other", HOOK_ID]
