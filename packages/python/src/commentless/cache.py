from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any

CACHE_VERSION = 1
CACHE_FILE_NAME = "clean-python.json"


def signature_of(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha1(payload, usedforsecurity=False).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def cache_directory(cwd: str) -> str:
    return os.path.join(cwd, ".commentless-cache")


def _stamp(file: str) -> str | None:
    try:
        stats = os.stat(file)
    except OSError:
        return None
    return f"{stats.st_size}:{stats.st_mtime_ns}"


class CleanFileCache:
    def __init__(self, file: str, signature: str, entries: dict[str, str]) -> None:
        self._file = file
        self._signature = signature
        self._clean = dict(entries)
        self._dirty = False

    @classmethod
    def load(cls, cwd: str, signature: str) -> CleanFileCache:
        file = os.path.join(cache_directory(cwd), CACHE_FILE_NAME)
        try:
            parsed = json.loads(Path(file).read_text(encoding="utf-8"))
            if parsed.get("version") == CACHE_VERSION and parsed.get("signature") == signature:
                return cls(file, signature, dict(parsed.get("clean", {})))
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        return cls(file, signature, {})

    @classmethod
    def disabled(cls) -> CleanFileCache:
        return cls("", "", {})

    @property
    def enabled(self) -> bool:
        return self._file != ""

    def is_clean(self, file: str) -> bool:
        if not self.enabled:
            return False
        known = self._clean.get(file)
        return known is not None and known == _stamp(file)

    def mark(self, file: str, clean: bool) -> None:
        if not self.enabled:
            return
        if not clean:
            if self._clean.pop(file, None) is not None:
                self._dirty = True
            return
        current = _stamp(file)
        if current is None:
            return
        if self._clean.get(file) != current:
            self._clean[file] = current
            self._dirty = True

    def save(self) -> None:
        if not self.enabled or not self._dirty:
            return
        payload = {
            "version": CACHE_VERSION,
            "signature": self._signature,
            "clean": self._clean,
        }
        try:
            os.makedirs(os.path.dirname(self._file), exist_ok=True)
            Path(self._file).write_text(json.dumps(payload), encoding="utf-8")
        except OSError:
            pass
