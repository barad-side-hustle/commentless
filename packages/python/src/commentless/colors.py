from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Colors:
    enabled: bool

    def _paint(self, open_code: str, close_code: str, value: str) -> str:
        if not self.enabled or not value:
            return value
        return f"\x1b[{open_code}m{value}\x1b[{close_code}m"

    def red(self, value: str) -> str:
        return self._paint("31", "39", value)

    def green(self, value: str) -> str:
        return self._paint("32", "39", value)

    def yellow(self, value: str) -> str:
        return self._paint("33", "39", value)

    def bold(self, value: str) -> str:
        return self._paint("1", "22", value)

    def dim(self, value: str) -> str:
        return self._paint("2", "22", value)


def create_colors(enabled: bool) -> Colors:
    return Colors(enabled)
