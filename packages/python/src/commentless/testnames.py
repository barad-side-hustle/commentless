from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from .types import Comment, FileResult

TestFramework = Literal["pytest", "unittest"]

PRINT_WIDTH = 100
MAX_IDENTIFIER = 55

LABEL = re.compile(
    r"^(?:TODO|FIXME|NOTE|HACK|XXX|WARNING|WARN|BUG|REVIEW|OPTIMIZE|DEPRECATED)\b\s*[:\-–—]?\s*"
    r"|^(?:Todo|Note|Fixme|Hack|Warning|Bug)\s*:\s*",
)

SENTENCE = re.compile(r"(?<=\w{3}[.!?])\s+")

STRING_PREFIX = re.compile(r"^[rRbBuUfF]{0,3}")

SECTION_HEADER = re.compile(
    r"^(?:Args|Arguments|Attributes|Example|Examples|Keyword Args|Note|Notes|Parameters|Raises"
    r"|Returns|See Also|Todo|Warns|Warnings|Yields)\s*:?\s*$"
)

CODE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern)
    for pattern in (
        r"^(?:async\s+)?def\s+\w",
        r"^class\s+\w",
        r"^(?:import|from)\s+[\w.]",
        r"^(?:if|elif|else|for|while|with|try|except|finally|match|case)\b.*:\s*$",
        r"^(?:return|yield|raise|assert|del|global|nonlocal|pass|break|continue|lambda)\b",
        r"^@\w",
        r"^\w[\w.\[\]\"']*\s*(?::\s*[^=]+)?[-+*/%|&^@]?=[^=]",
        r"^\w[\w.]*\([^()]*\)[;:.]?$",
        r"^https?://\S+$",
        r"^[)\]}],?$",
        r"^(?:>>>|\.\.\.)\s",
        r"^\w[\w.]*\[[^\]]*\]\s*=",
        r"[;{]$",
        r"->",
    )
)

IDENTIFIER_SEPARATOR = re.compile(r"\W+", re.UNICODE)
LEADING_JUNK = re.compile(r"^\W+", re.UNICODE)
TRAILING_JUNK = re.compile(r"[^\w?!)\]'\"]+$", re.UNICODE)
WHITESPACE = re.compile(r"\s+")

DISTRIBUTION_NAME = re.compile(r"[A-Za-z0-9._-]+")


@dataclass(frozen=True, slots=True)
class TestNameDraft:
    file: str
    line: int
    name: str


@dataclass(frozen=True, slots=True)
class DraftOptions:
    cwd: str
    framework: TestFramework = "unittest"


@dataclass(frozen=True, slots=True)
class DraftResult:
    source: str
    drafts: list[TestNameDraft] = field(default_factory=list)
    files: int = 0
    skipped: int = 0


def _unquote(text: str) -> str:
    body = STRING_PREFIX.sub("", text.strip(), count=1)
    for quote in ('"""', "'''", '"', "'"):
        if body.startswith(quote) and body.endswith(quote) and len(body) >= 2 * len(quote):
            return body[len(quote) : -len(quote)]
    return body


def body_of(comment: Comment | str, kind: str = "comment") -> str:
    if isinstance(comment, Comment):
        text, kind = comment.text, comment.kind
    else:
        text = comment

    if kind == "docstring":
        lines = []
        for raw in _unquote(text).split("\n"):
            line = raw.strip()
            if not line or line.startswith((">>>", "...", ":")) or SECTION_HEADER.match(line):
                continue
            lines.append(line)
        return WHITESPACE.sub(" ", " ".join(lines)).strip()

    return WHITESPACE.sub(" ", text.strip().lstrip("#")).strip()


def looks_like_code(text: str) -> bool:
    return any(pattern.search(text) for pattern in CODE_PATTERNS)


def _is_prose(comment: Comment) -> bool:
    body = body_of(comment)
    return any(char.isalpha() for char in body) and not looks_like_code(body)


def group_comments(comments: list[Comment]) -> list[list[Comment]]:
    groups: list[list[Comment]] = []
    for comment in comments:
        current = groups[-1] if groups else None
        previous = current[-1] if current else None
        continues = (
            previous is not None
            and previous.kind == "comment"
            and comment.kind == "comment"
            and comment.line == previous.line + 1
            and comment.column == previous.column
            and _is_prose(previous)
            and _is_prose(comment)
        )
        if continues and current is not None:
            current.append(comment)
        else:
            groups.append([comment])
    return groups


def _split_sentences(body: str) -> list[str]:
    parts = SENTENCE.split(body)
    merged: list[str] = []
    for part in parts:
        if merged and not part[:1].isupper():
            merged[-1] = f"{merged[-1]} {part}"
        else:
            merged.append(part)
    return merged


def _lower_first_word(text: str) -> str:
    space = text.find(" ")
    first = text if space == -1 else text[:space]
    core = first.replace("'", "")
    if core and core[0].isupper() and (len(core) == 1 or core[1:].islower()):
        return first.lower() + text[len(first) :]
    return text


def _tidy(sentence: str) -> str | None:
    labelled = LABEL.sub("", sentence.strip()).strip()
    if looks_like_code(labelled):
        return None

    text = TRAILING_JUNK.sub("", LEADING_JUNK.sub("", labelled)).strip().strip("_")
    if not any(char.isalpha() for char in text) or looks_like_code(text):
        return None
    return _lower_first_word(text)


def to_test_names(*comments: Comment | str) -> list[str]:
    body = WHITESPACE.sub(" ", " ".join(filter(None, (body_of(c) for c in comments)))).strip()
    body = LABEL.sub("", body).strip()

    if not any(char.isalpha() for char in body):
        return []

    names: list[str] = []
    for sentence in _split_sentences(body):
        name = _tidy(sentence)
        if name:
            names.append(name)
    return names


def to_identifier(name: str) -> str:
    slug = IDENTIFIER_SEPARATOR.sub("_", name.strip().lower()).strip("_")
    if len(slug) > MAX_IDENTIFIER:
        head = slug[:MAX_IDENTIFIER]
        slug = head.rsplit("_", 1)[0] if "_" in head else head
    slug = slug.strip("_")
    if not slug:
        slug = "case"
    identifier = f"test_{slug}"
    return identifier if identifier.isidentifier() else "test_case"


def to_class_name(file: str) -> str:
    stem = re.sub(r"\.[^.]+$", "", file)
    parts = [part for part in IDENTIFIER_SEPARATOR.split(stem) if part]
    name = "Test" + "".join(part[:1].upper() + part[1:] for part in parts)
    return name if name.isidentifier() else "TestSource"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _stub(name: str, framework: TestFramework) -> list[str]:
    reason = f'"todo: {_escape(name)}"'
    decorator = (
        f"    @pytest.mark.skip(reason={reason})"
        if framework == "pytest"
        else f"    @unittest.skip({reason})"
    )
    lines = [decorator]
    if len(decorator) > PRINT_WIDTH:
        opener = "    @pytest.mark.skip(" if framework == "pytest" else "    @unittest.skip("
        keyword = "reason=" if framework == "pytest" else ""
        lines = [opener, f"        {keyword}{reason}", "    )"]
    lines.append(f"    def {to_identifier(name)}(self) -> None: ...")
    return lines


def render_test_file(
    groups: list[tuple[str, list[str]]], framework: TestFramework = "unittest"
) -> str:
    header = "import pytest" if framework == "pytest" else "import unittest"
    base = "" if framework == "pytest" else "(unittest.TestCase)"

    seen_classes: set[str] = set()
    blocks: list[str] = []

    for file, names in groups:
        class_name = to_class_name(file)
        suffix = 2
        while class_name in seen_classes:
            class_name = f"{to_class_name(file)}{suffix}"
            suffix += 1
        seen_classes.add(class_name)

        seen_methods: set[str] = set()
        body: list[str] = []
        for name in names:
            identifier = to_identifier(name)
            unique = name
            counter = 2
            while identifier in seen_methods:
                unique = f"{name} {counter}"
                identifier = to_identifier(unique)
                counter += 1
            seen_methods.add(identifier)
            body.extend(_stub(unique, framework))
            body.append("")

        while body and body[-1] == "":
            body.pop()
        blocks.append(f"class {class_name}{base}:\n" + "\n".join(body))

    return f"{header}\n\n\n" + "\n\n\n".join(blocks) + "\n"


def _pyproject_mentions_pytest(file: Path) -> bool:
    try:
        with file.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return False

    if "pytest" in data.get("tool", {}):
        return True

    buckets: list[object] = [
        data.get("project", {}).get("dependencies", []),
        *data.get("project", {}).get("optional-dependencies", {}).values(),
        *data.get("dependency-groups", {}).values(),
    ]
    poetry = data.get("tool", {}).get("poetry", {})
    for group in poetry.get("group", {}).values():
        buckets.append(list(group.get("dependencies", {})))
    buckets.append(list(poetry.get("dev-dependencies", {})))

    for bucket in buckets:
        if not isinstance(bucket, list):
            continue
        for entry in bucket:
            if not isinstance(entry, str):
                continue
            match = DISTRIBUTION_NAME.match(entry.strip())
            if match is None:
                continue
            name = match.group().lower().replace("_", "-")
            if name == "pytest" or name.startswith("pytest-"):
                return True
    return False


def detect_test_framework(cwd: str) -> TestFramework:
    root = Path(cwd)

    pyproject = root / "pyproject.toml"
    if pyproject.is_file() and _pyproject_mentions_pytest(pyproject):
        return "pytest"

    for name in ("pytest.ini", "conftest.py", "tests/conftest.py"):
        if (root / name).exists():
            return "pytest"

    for name in ("setup.cfg", "tox.ini"):
        candidate = root / name
        if candidate.is_file() and "pytest" in candidate.read_text(
            encoding="utf-8", errors="replace"
        ):
            return "pytest"

    for candidate in root.glob("requirements*.txt"):
        if "pytest" in candidate.read_text(encoding="utf-8", errors="replace"):
            return "pytest"

    return "unittest"


def draft_test_names(files: list[FileResult], options: DraftOptions) -> DraftResult:
    groups: list[tuple[str, list[str]]] = []
    drafts: list[TestNameDraft] = []
    skipped = 0

    for result in files:
        if result.error:
            continue

        name = os.path.relpath(result.file, options.cwd).replace(os.sep, "/") or result.file
        seen: set[str] = set()
        names: list[str] = []

        for group in group_comments(result.removable):
            drafted = to_test_names(*group)
            if not drafted:
                skipped += 1
                continue
            for entry in drafted:
                if entry in seen:
                    continue
                seen.add(entry)
                names.append(entry)
                drafts.append(TestNameDraft(file=name, line=group[0].line, name=entry))

        if names:
            groups.append((name, names))

    return DraftResult(
        source=render_test_file(groups, options.framework) if groups else "",
        drafts=drafts,
        files=len(groups),
        skipped=skipped,
    )
