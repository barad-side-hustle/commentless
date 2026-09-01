from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .colors import create_colors
from .config import CONFIG_FILE_NAME, PYPROJECT_FILE_NAME, PYPROJECT_TABLE
from .hooks import apply_hook, plan_hook
from .run import RunOptions, run
from .scan import DEFAULT_EXTENSIONS
from .types import DiscoveryMode, KeepRule

Confirm = Callable[[str], bool]


@dataclass(frozen=True, slots=True)
class InitOptions:
    cwd: str
    keep: tuple[KeepRule, ...] = ()
    extensions: tuple[str, ...] = DEFAULT_EXTENSIONS
    ignore: tuple[str, ...] = ()
    ignore_file: str | None = ".commentlessignore"
    gitignore: bool = True
    config_path: str | None = None
    pyproject: bool = False
    force: bool = False
    strict: bool = False
    docstrings: bool = False
    color: bool = False
    pre_commit: bool | None = None
    confirm: Confirm | None = None
    discovery: DiscoveryMode | None = None


@dataclass(frozen=True, slots=True)
class InitResult:
    file: str
    existed: bool
    found: int
    scanned: int
    config: dict[str, Any] = field(default_factory=dict)
    hook_added: bool = False
    output: str = ""


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def default_config() -> dict[str, Any]:
    return {
        "ext": list(DEFAULT_EXTENSIONS),
        "ignore": [],
        "keep": [],
        "disableKeep": [],
        "collapseBlankLines": False,
        "docstrings": False,
        "maxAllowed": 0,
        "reporter": "pretty",
    }


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(json.dumps(entry) for entry in value) + "]"
    return json.dumps(value)


def render_toml_table(config: dict[str, Any]) -> str:
    lines = [f"[{PYPROJECT_TABLE}]"]
    lines.extend(f"{key} = {_toml_value(value)}" for key, value in config.items())
    return "\n".join(lines) + "\n"


def init(options: InitOptions) -> InitResult:
    pc = create_colors(options.color)

    if options.pyproject and options.config_path:
        target = Path(options.cwd, options.config_path)
    elif options.pyproject:
        target = Path(options.cwd, PYPROJECT_FILE_NAME)
    else:
        target = Path(options.cwd, options.config_path or CONFIG_FILE_NAME)

    file = target.resolve()
    try:
        shown = str(file.relative_to(Path(options.cwd).resolve()))
    except ValueError:
        shown = str(file)

    already = (
        f"[{PYPROJECT_TABLE}]" in file.read_text(encoding="utf-8")
        if options.pyproject and file.is_file()
        else file.is_file() and not options.pyproject
    )
    if already and not options.force:
        what = (
            f"{shown} already has [{PYPROJECT_TABLE}]"
            if options.pyproject
            else f"{shown} already exists"
        )
        return InitResult(
            file=str(file),
            existed=True,
            found=0,
            scanned=0,
            output=f"{pc.yellow('!')} {what}. Re-run with --force to overwrite it.",
        )

    scan = run(
        RunOptions(
            cwd=options.cwd,
            mode="dry-run",
            extensions=options.extensions,
            ignore=options.ignore,
            ignore_file=options.ignore_file,
            gitignore=options.gitignore,
            keep=options.keep,
            docstrings=options.docstrings,
            cache=False,
            discovery=options.discovery or "all",
        )
    )

    found = scan.summary.comments_removed
    config = {
        **default_config(),
        "ext": list(options.extensions),
        "ignore": list(options.ignore),
        "docstrings": options.docstrings,
        "maxAllowed": 0 if options.strict else found,
    }

    file.parent.mkdir(parents=True, exist_ok=True)
    if options.pyproject:
        existing = file.read_text(encoding="utf-8") if file.is_file() else ""
        if f"[{PYPROJECT_TABLE}]" in existing:
            head, _, tail = existing.partition(f"[{PYPROJECT_TABLE}]")
            rest = tail.split("\n[", 1)
            existing = head + ("[" + rest[1] if len(rest) > 1 else "")
        if not existing or existing.endswith("\n\n"):
            separator = ""
        elif existing.endswith("\n"):
            separator = "\n"
        else:
            separator = "\n\n"
        file.write_text(existing + separator + render_toml_table(config), encoding="utf-8")
    else:
        file.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    lines = [f"{pc.green('✔')} Wrote {pc.bold(shown)}", ""]

    if found == 0:
        lines += [
            f"{_plural(scan.summary.discovered, 'file')} scanned, no strippable comments found.",
            f"{pc.bold('maxAllowed')} is 0 — the gate passes and stays passing.",
        ]
    elif options.strict:
        lines += [
            f"{_plural(scan.summary.discovered, 'file')} scanned, "
            f"{_plural(found, 'strippable comment')} found.",
            f"{pc.bold('maxAllowed')} is 0, so {pc.bold('commentless --check')} fails until you "
            f"run {pc.bold('commentless --write')}.",
        ]
    else:
        lines += [
            f"{_plural(scan.summary.discovered, 'file')} scanned, "
            f"{pc.bold(_plural(found, 'strippable comment'))} found.",
            f"{pc.bold('maxAllowed')} is set to {found} so the gate passes today. Ratchet it down "
            f"as you",
            "move those explanations into test names — that is the whole point.",
        ]

    if not options.docstrings:
        lines += [
            "",
            pc.dim("Docstrings were left alone. Add --docstrings to count and strip those too."),
        ]

    hook_added = _maybe_add_hook(options, lines, pc)

    lines += ["", "Next:"]
    if hook_added:
        lines.append(f"  1. run {pc.bold('pre-commit install')} so the gate runs on every commit")
        lines.append(f"  2. run {pc.bold('commentless --write')} when you are ready to delete them")
    else:
        lines.append("  1. run commentless --check in CI on every pull request")
        lines.append(f"  2. run {pc.bold('commentless --write')} when you are ready to delete them")

    return InitResult(
        file=str(file),
        existed=False,
        found=found,
        scanned=scan.summary.discovered,
        config=config,
        hook_added=hook_added,
        output="\n".join(lines),
    )


def _maybe_add_hook(options: InitOptions, lines: list[str], pc: Any) -> bool:
    if options.pre_commit is False:
        return False

    plan = plan_hook(options.cwd)
    if plan.present:
        lines += ["", pc.dim(f"{plan.file.name} already has a commentless hook.")]
        return False

    preview = plan.block.rstrip("\n").split("\n")

    if options.pre_commit is not True:
        if options.confirm is None:
            return False
        verb = "is missing a commentless hook" if plan.existed else "does not exist yet"
        lines += ["", f"{plan.file.name} {verb}. This is what would be added:"]
        lines += [pc.dim(f"  {line}") for line in preview]
        if not options.confirm("Add it?"):
            lines.append(pc.dim("Skipped. Add it yourself when you want it."))
            return False

    apply_hook(plan)
    lines += ["", f"{pc.green('✔')} Added to {plan.file.name}:"]
    lines += [pc.dim(f"  {line}") for line in preview]
    return True
