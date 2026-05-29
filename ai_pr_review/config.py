from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

from ai_pr_review.models import PRContext, Severity


class ConfigError(ValueError):
    """Raised when the review configuration file is invalid."""


@dataclass(frozen=True)
class ReviewConfig:
    language: str = "zh"
    model: str | None = None
    max_files: int | None = None
    patch_budget_per_file: int = 3500
    total_budget: int = 12000
    include_patterns: list[str] = field(default_factory=list)
    ignore_patterns: list[str] = field(default_factory=list)
    enabled_rules: list[str] | None = None
    min_severity: Severity = Severity.LOW
    enable_ai: bool = True


def load_config(path: str | Path | None = None, *, cwd: str | Path | None = None) -> ReviewConfig:
    config_path = _resolve_config_path(path, cwd)
    if config_path is None:
        return ReviewConfig()

    try:
        data = json.loads(config_path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise ConfigError(f"Cannot read config file {config_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Config file {config_path} is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError("Config file must contain a JSON object.")
    return _config_from_mapping(data)


def apply_file_filters(context: PRContext, config: ReviewConfig) -> PRContext:
    files = [
        file
        for file in context.files
        if _matches_includes(file.filename, config.include_patterns)
        and not _matches_any(file.filename, config.ignore_patterns)
    ]
    if config.max_files is not None:
        files = files[: config.max_files]
    return replace(context, files=files)


def _resolve_config_path(path: str | Path | None, cwd: str | Path | None) -> Path | None:
    if path is not None:
        return Path(path)
    root = Path(cwd) if cwd is not None else Path.cwd()
    candidate = root / ".ai-pr-review.json"
    return candidate if candidate.exists() else None


def _config_from_mapping(data: dict[str, Any]) -> ReviewConfig:
    return ReviewConfig(
        language=_string_value(data, "language", "zh"),
        model=_optional_string_value(data, "model"),
        max_files=_optional_int_value(data, "max_files"),
        patch_budget_per_file=_int_value(data, "patch_budget_per_file", 3500),
        total_budget=_int_value(data, "total_budget", 12000),
        include_patterns=_string_list_value(data, "include_patterns"),
        ignore_patterns=_string_list_value(data, "ignore_patterns"),
        enabled_rules=_optional_string_list_value(data, "enabled_rules"),
        min_severity=_severity_value(data, "min_severity", Severity.LOW),
        enable_ai=_bool_value(data, "enable_ai", True),
    )


def _matches_includes(filename: str, patterns: list[str]) -> bool:
    return not patterns or _matches_any(filename, patterns)


def _matches_any(filename: str, patterns: list[str]) -> bool:
    normalized = _normalize_path(filename)
    return any(fnmatchcase(normalized, _normalize_path(pattern)) for pattern in patterns)


def _normalize_path(value: str) -> str:
    return value.replace("\\", "/")


def _string_value(data: dict[str, Any], key: str, default: str) -> str:
    value = data.get(key, default)
    if not isinstance(value, str):
        raise ConfigError(f"Config key '{key}' must be a string.")
    return value


def _optional_string_value(data: dict[str, Any], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(f"Config key '{key}' must be a string or null.")
    return value


def _int_value(data: dict[str, Any], key: str, default: int) -> int:
    value = data.get(key, default)
    if not isinstance(value, int) or value < 0:
        raise ConfigError(f"Config key '{key}' must be a non-negative integer.")
    return value


def _optional_int_value(data: dict[str, Any], key: str) -> int | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, int) or value < 0:
        raise ConfigError(f"Config key '{key}' must be a non-negative integer or null.")
    return value


def _bool_value(data: dict[str, Any], key: str, default: bool) -> bool:
    value = data.get(key, default)
    if not isinstance(value, bool):
        raise ConfigError(f"Config key '{key}' must be a boolean.")
    return value


def _string_list_value(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f"Config key '{key}' must be a list of strings.")
    return value


def _optional_string_list_value(data: dict[str, Any], key: str) -> list[str] | None:
    if key not in data or data[key] is None:
        return None
    return _string_list_value(data, key)


def _severity_value(data: dict[str, Any], key: str, default: Severity) -> Severity:
    raw = data.get(key, default.value)
    if not isinstance(raw, str):
        raise ConfigError(f"Config key '{key}' must be one of: low, medium, high.")
    try:
        return Severity(raw.lower())
    except ValueError as exc:
        raise ConfigError(f"Config key '{key}' must be one of: low, medium, high.") from exc
