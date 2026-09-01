from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .scan import may_contain_comments, scan_source
from .strip import strip_comments
from .types import FileResult, KeepRule, ScanOptions


@dataclass(frozen=True, slots=True)
class ProcessOptions:
    keep: tuple[KeepRule, ...] = ()
    collapse_blank_lines: bool = False
    write: bool = False
    docstrings: bool = False


def process_file(file: str, options: ProcessOptions) -> FileResult:
    try:
        source = Path(file).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        return FileResult(file=file, error=str(error))

    if not may_contain_comments(source, docstrings=options.docstrings):
        return FileResult(file=file)

    try:
        result = scan_source(
            source,
            ScanOptions(file_name=file, keep=options.keep, docstrings=options.docstrings),
        )
    except Exception as error:
        return FileResult(file=file, error=str(error))

    if result.ignored_file:
        return FileResult(file=file)

    output = strip_comments(
        source,
        result.removable,
        collapse_blank_lines_option=options.collapse_blank_lines,
    )
    changed = output != source

    if changed and options.write:
        try:
            Path(file).write_text(output, encoding="utf-8")
        except OSError as error:
            return FileResult(
                file=file,
                removable=result.removable,
                kept_count=len(result.kept),
                error=str(error),
            )

    return FileResult(
        file=file,
        removable=result.removable,
        kept_count=len(result.kept),
        changed=changed,
    )
