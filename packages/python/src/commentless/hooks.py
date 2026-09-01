from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .version import VERSION

PRE_COMMIT_FILE = ".pre-commit-config.yaml"
HOOK_ID = "commentless"


@dataclass(frozen=True, slots=True)
class HookPlan:
    file: Path
    existed: bool
    present: bool
    block: str


def _hook_block(indent: str) -> str:
    lines = [
        f"{indent}- repo: local",
        f"{indent}  hooks:",
        f"{indent}    - id: {HOOK_ID}",
        f"{indent}      name: commentless",
        f"{indent}      entry: commentless --check",
        f"{indent}      language: python",
        f'{indent}      additional_dependencies: ["commentless=={VERSION}"]',
        f"{indent}      types: [python]",
    ]
    return "\n".join(lines) + "\n"


def _detect_indent(text: str) -> str:
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("- repo:"):
            return " " * (len(line) - len(stripped))
    return "  "


def plan_hook(cwd: str) -> HookPlan:
    file = Path(cwd, PRE_COMMIT_FILE)
    if not file.is_file():
        return HookPlan(file=file, existed=False, present=False, block=_hook_block("  "))

    text = file.read_text(encoding="utf-8")
    present = f"id: {HOOK_ID}" in text
    return HookPlan(
        file=file, existed=True, present=present, block=_hook_block(_detect_indent(text))
    )


def _insert_into_repos(text: str, block: str) -> str | None:
    lines = text.splitlines(keepends=True)
    start = next(
        (index for index, line in enumerate(lines) if line.rstrip() in ("repos:", "repos: []")),
        None,
    )
    if start is None:
        return None

    if lines[start].rstrip() == "repos: []":
        lines[start] = "repos:\n"

    end = len(lines)
    for index in range(start + 1, len(lines)):
        stripped = lines[index].strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not lines[index][:1].isspace() and not stripped.startswith("- "):
            end = index
            break

    while end > start + 1 and not lines[end - 1].strip():
        end -= 1

    if end > start and not lines[end - 1].endswith("\n"):
        lines[end - 1] += "\n"

    return "".join([*lines[:end], block, *lines[end:]])


def apply_hook(plan: HookPlan) -> None:
    if not plan.existed:
        plan.file.write_text(f"repos:\n{plan.block}", encoding="utf-8")
        return

    text = plan.file.read_text(encoding="utf-8")
    updated = _insert_into_repos(text, plan.block)
    if updated is None:
        separator = "" if text.endswith("\n") or not text else "\n"
        updated = f"{text}{separator}repos:\n{plan.block}"
    plan.file.write_text(updated, encoding="utf-8")
