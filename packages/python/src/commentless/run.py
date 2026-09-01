from __future__ import annotations

import os
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

from .cache import CleanFileCache, signature_of
from .files import DiscoverOptions, discover_files
from .keep import deserialize_keep_rules, serialize_keep_rules, signature_of_keep_rules
from .process import ProcessOptions, process_file
from .types import DiscoveryMode, FileResult, KeepRule, RunMode, RunResult, RunSummary

WORKER_THRESHOLD = 200
WORKER_BYTE_THRESHOLD = 1_000_000
BATCH_SIZE = 24

_WORKER_OPTIONS: ProcessOptions | None = None


@dataclass(frozen=True, slots=True)
class RunOptions:
    mode: RunMode
    keep: tuple[KeepRule, ...] = ()
    cwd: str | None = None
    paths: tuple[str, ...] = (".",)
    discovery: DiscoveryMode = "all"
    base: str | None = None
    extensions: tuple[str, ...] = ()
    ignore: tuple[str, ...] = ()
    ignore_file: str | None = ".commentlessignore"
    gitignore: bool = True
    collapse_blank_lines: bool = False
    docstrings: bool = False
    max_allowed: int = 0
    concurrency: int | None = None
    cache: bool = True
    files: tuple[str, ...] | None = None
    worker_threshold: int | None = None
    worker_byte_threshold: int | None = None


def default_concurrency() -> int:
    return max(1, (os.cpu_count() or 2) - 1)


def _init_worker(payload: tuple[object, ...]) -> None:
    global _WORKER_OPTIONS
    serialized, collapse, write, docstrings = payload
    _WORKER_OPTIONS = ProcessOptions(
        keep=deserialize_keep_rules(serialized),  # type: ignore[arg-type]
        collapse_blank_lines=bool(collapse),
        write=bool(write),
        docstrings=bool(docstrings),
    )


def _process_batch(batch: tuple[str, ...]) -> list[FileResult]:
    options = _WORKER_OPTIONS
    if options is None:
        raise RuntimeError("commentless worker was started without options")
    return [process_file(file, options) for file in batch]


def _total_bytes(files: list[str]) -> int:
    total = 0
    for file in files:
        try:
            total += os.path.getsize(file)
        except OSError:
            continue
    return total


def _batched(files: list[str], size: int) -> list[tuple[str, ...]]:
    return [tuple(files[index : index + size]) for index in range(0, len(files), size)]


def _run_in_workers(
    files: list[str], worker_count: int, options: ProcessOptions
) -> list[FileResult]:
    payload = (
        serialize_keep_rules(options.keep),
        options.collapse_blank_lines,
        options.write,
        options.docstrings,
    )
    results: list[FileResult] = []
    with ProcessPoolExecutor(
        max_workers=worker_count, initializer=_init_worker, initargs=(payload,)
    ) as pool:
        for batch in pool.map(_process_batch, _batched(files, BATCH_SIZE)):
            results.extend(batch)
    return results


def run(options: RunOptions) -> RunResult:
    started_at = time.perf_counter()
    cwd = options.cwd or os.getcwd()
    write = options.mode == "write"

    files = (
        list(options.files)
        if options.files is not None
        else discover_files(
            DiscoverOptions(
                cwd=cwd,
                paths=options.paths,
                extensions=options.extensions,
                ignore=options.ignore,
                ignore_file=options.ignore_file,
                gitignore=options.gitignore,
                mode=options.discovery,
                base=options.base,
            )
        )
    )

    signature = signature_of(
        {
            "keep": signature_of_keep_rules(options.keep),
            "collapseBlankLines": options.collapse_blank_lines,
            "docstrings": options.docstrings,
            "extensions": sorted(options.extensions),
        }
    )
    cache = CleanFileCache.disabled() if not options.cache else CleanFileCache.load(cwd, signature)

    pending: list[str] = []
    cached = 0
    for file in files:
        if cache.is_clean(file):
            cached += 1
            continue
        pending.append(file)

    process_options = ProcessOptions(
        keep=options.keep,
        collapse_blank_lines=options.collapse_blank_lines,
        write=write,
        docstrings=options.docstrings,
    )

    threshold = (
        options.worker_threshold if options.worker_threshold is not None else WORKER_THRESHOLD
    )
    byte_threshold = (
        options.worker_byte_threshold
        if options.worker_byte_threshold is not None
        else WORKER_BYTE_THRESHOLD
    )
    worker_count = min(
        options.concurrency if options.concurrency is not None else default_concurrency(),
        max(1, -(-len(pending) // BATCH_SIZE)),
    )

    worth_it = (
        worker_count > 1 and len(pending) >= threshold and _total_bytes(pending) >= byte_threshold
    )

    if worth_it:
        results = _run_in_workers(pending, worker_count, process_options)
    else:
        results = [process_file(file, process_options) for file in pending]

    results.sort(key=lambda result: result.file)

    offenders: list[FileResult] = []
    comments_removed = 0
    comments_kept = 0
    errors = 0

    for result in results:
        comments_kept += result.kept_count
        if result.error:
            errors += 1
            offenders.append(result)
            cache.mark(result.file, False)
            continue
        if result.changed:
            comments_removed += len(result.removable)
            offenders.append(result)
            cache.mark(result.file, write)
            continue
        cache.mark(result.file, True)

    cache.save()

    summary = RunSummary(
        mode=options.mode,
        discovered=len(files),
        parsed=len(pending),
        cached=cached,
        files_with_comments=sum(1 for result in offenders if result.changed),
        comments_removed=comments_removed,
        comments_kept=comments_kept,
        errors=errors,
        duration_ms=round((time.perf_counter() - started_at) * 1000),
    )

    failed = errors > 0 or (options.mode == "check" and comments_removed > options.max_allowed)
    return RunResult(summary=summary, files=offenders, exit_code=1 if failed else 0)
