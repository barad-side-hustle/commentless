from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .keep import KEEP_RULE_NAMES
from .reporters import REPORTERS

CONFIG_FILE_NAME = "commentless.config.json"
PYPROJECT_FILE_NAME = "pyproject.toml"
PYPROJECT_TABLE = "tool.commentless"


class ConfigError(Exception):
    pass


@dataclass(slots=True)
class FileConfig:
    ext: list[str] | None = None
    ignore: list[str] | None = None
    ignoreFile: str | bool | None = None
    gitignore: bool | None = None
    keep: list[str] | None = None
    defaultKeep: bool | None = None
    disableKeep: list[str] | None = None
    keepOnly: list[str] | None = None
    collapseBlankLines: bool | None = None
    docstrings: bool | None = None
    maxAllowed: int | None = None
    reporter: str | None = None
    concurrency: int | None = None
    cache: bool | None = None


KNOWN_KEYS: tuple[str, ...] = (
    "ext",
    "ignore",
    "ignoreFile",
    "gitignore",
    "keep",
    "defaultKeep",
    "disableKeep",
    "keepOnly",
    "collapseBlankLines",
    "docstrings",
    "maxAllowed",
    "reporter",
    "concurrency",
    "cache",
)


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


_ALIASES: dict[str, str] = {_snake(key): key for key in KNOWN_KEYS}


def _fail(source: str, message: str) -> None:
    raise ConfigError(f"{source}: {message}")


def _assert_string_list(source: str, key: str, value: Any) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(entry, str) for entry in value):
        _fail(source, f'"{key}" must be an array of strings')
    return list(value)


def _assert_bool(source: str, key: str, value: Any) -> bool:
    if not isinstance(value, bool):
        _fail(source, f'"{key}" must be a boolean')
    return bool(value)


def _assert_non_negative_int(source: str, key: str, value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        _fail(source, f'"{key}" must be a non-negative integer')
    return int(value)


def validate_config(raw: Any, source: str) -> FileConfig:
    if not isinstance(raw, dict):
        _fail(source, "configuration must be a table of options")

    normalized: dict[str, Any] = {}
    for key, value in raw.items():
        canonical = key if key in KNOWN_KEYS else _ALIASES.get(key)
        if canonical is None:
            _fail(source, f'unknown option "{key}". Valid options: {", ".join(KNOWN_KEYS)}')
            continue
        normalized[canonical] = value

    config = FileConfig()

    if "ext" in normalized:
        config.ext = _assert_string_list(source, "ext", normalized["ext"])
    if "ignore" in normalized:
        config.ignore = _assert_string_list(source, "ignore", normalized["ignore"])
    if "keep" in normalized:
        config.keep = _assert_string_list(source, "keep", normalized["keep"])
        for pattern in config.keep:
            try:
                re.compile(pattern)
            except re.error as error:
                _fail(
                    source,
                    f'"keep" entry {json.dumps(pattern)} is not a valid '
                    f"regular expression ({error})",
                )
    if "ignoreFile" in normalized:
        value = normalized["ignoreFile"]
        if not isinstance(value, str) and value is not False:
            _fail(source, '"ignoreFile" must be a path string or false')
        config.ignoreFile = value
    if "gitignore" in normalized:
        config.gitignore = _assert_bool(source, "gitignore", normalized["gitignore"])
    if "defaultKeep" in normalized:
        config.defaultKeep = _assert_bool(source, "defaultKeep", normalized["defaultKeep"])

    for key in ("disableKeep", "keepOnly"):
        if key not in normalized:
            continue
        names = _assert_string_list(source, key, normalized[key])
        unknown = [name for name in names if name not in KEEP_RULE_NAMES]
        if unknown:
            plural = "" if len(unknown) == 1 else "s"
            listed = ", ".join(json.dumps(name) for name in unknown)
            _fail(
                source,
                f'"{key}" contains unknown keep rule{plural} {listed}. '
                f"Valid rules: {', '.join(KEEP_RULE_NAMES)}",
            )
        setattr(config, key, names)

    if "collapseBlankLines" in normalized:
        config.collapseBlankLines = _assert_bool(
            source, "collapseBlankLines", normalized["collapseBlankLines"]
        )
    if "docstrings" in normalized:
        config.docstrings = _assert_bool(source, "docstrings", normalized["docstrings"])
    if "cache" in normalized:
        config.cache = _assert_bool(source, "cache", normalized["cache"])
    if "maxAllowed" in normalized:
        config.maxAllowed = _assert_non_negative_int(source, "maxAllowed", normalized["maxAllowed"])
    if "concurrency" in normalized:
        value = _assert_non_negative_int(source, "concurrency", normalized["concurrency"])
        if value < 1:
            _fail(source, '"concurrency" must be at least 1')
        config.concurrency = value
    if "reporter" in normalized:
        value = normalized["reporter"]
        if not isinstance(value, str) or value not in REPORTERS:
            _fail(source, f'"reporter" must be one of: {", ".join(REPORTERS)}')
        config.reporter = value

    return config


def _read_json(file: Path) -> Any:
    try:
        text = file.read_text(encoding="utf-8")
    except OSError as error:
        raise ConfigError(f"{file}: cannot be read ({error})") from error
    try:
        return json.loads(text)
    except ValueError as error:
        raise ConfigError(f"{file}: invalid JSON ({error})") from error


def _read_toml(file: Path) -> dict[str, Any]:
    try:
        with file.open("rb") as handle:
            return tomllib.load(handle)
    except OSError as error:
        raise ConfigError(f"{file}: cannot be read ({error})") from error
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{file}: invalid TOML ({error})") from error


@dataclass(frozen=True, slots=True)
class LoadedConfig:
    config: FileConfig
    source: str | None


def load_config(cwd: str, explicit_path: str | None = None) -> LoadedConfig:
    if explicit_path:
        file = Path(cwd, explicit_path).resolve()
        if not file.is_file():
            raise ConfigError(f"{explicit_path}: config file not found")
        if file.suffix == ".toml":
            table = _read_toml(file).get("tool", {}).get("commentless")
            if table is None:
                raise ConfigError(f"{explicit_path}: no [{PYPROJECT_TABLE}] table")
            return LoadedConfig(
                validate_config(table, f"{explicit_path} > [{PYPROJECT_TABLE}]"), str(file)
            )
        return LoadedConfig(validate_config(_read_json(file), explicit_path), str(file))

    directory = Path(cwd).resolve()
    for candidate in (directory, *directory.parents):
        config_file = candidate / CONFIG_FILE_NAME
        if config_file.is_file():
            return LoadedConfig(
                validate_config(_read_json(config_file), str(config_file)), str(config_file)
            )

        pyproject = candidate / PYPROJECT_FILE_NAME
        if pyproject.is_file():
            table = _read_toml(pyproject).get("tool", {}).get("commentless")
            if table is not None:
                return LoadedConfig(
                    validate_config(table, f"{pyproject} > [{PYPROJECT_TABLE}]"), str(pyproject)
                )

    return LoadedConfig(FileConfig(), None)
