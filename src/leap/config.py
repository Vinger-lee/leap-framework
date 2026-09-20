"""Configuration loading for the LEAP runtime.

Every parameter in ``config/default.yaml`` is an engineering heuristic and may
be overridden by the Pedagogical Policy engine at runtime. This module only
handles *loading* and *lookup*, never policy decisions.
"""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any, Iterator, Mapping

import yaml

__all__ = ["Config", "load_config", "REPO_ROOT", "DEFAULT_CONFIG_PATH"]

# src/leap/config.py -> src/leap -> src -> <repo root>
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "default.yaml"

_ENV_PREFIX = "LEAP__"


def _deep_merge(base: dict, override: Mapping[str, Any]) -> dict:
    """Recursively merge ``override`` into ``base`` (override wins)."""
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(base.get(key), Mapping):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _env_overrides() -> dict:
    """Read ``LEAP__section__key=value`` environment overrides.

    Nested keys use a double underscore, e.g. ``LEAP__BKT__P_INIT=0.25``.
    Values are parsed as YAML scalars so numbers and booleans work naturally.
    """
    result: dict = {}
    for raw_key, raw_value in os.environ.items():
        if not raw_key.startswith(_ENV_PREFIX):
            continue
        path = [p.lower() for p in raw_key[len(_ENV_PREFIX):].split("__") if p]
        if not path:
            continue
        cursor = result
        for part in path[:-1]:
            cursor = cursor.setdefault(part, {})
        try:
            cursor[path[-1]] = yaml.safe_load(raw_value)
        except yaml.YAMLError:
            cursor[path[-1]] = raw_value
    return result


class Config:
    """Read-only, dotted-path view over the merged configuration mapping."""

    def __init__(self, data: Mapping[str, Any], source: Path | None = None) -> None:
        self._data: dict = copy.deepcopy(dict(data))
        self.source = source

    # -- access ------------------------------------------------------------
    def get(self, dotted_key: str, default: Any = None) -> Any:
        cursor: Any = self._data
        for part in dotted_key.split("."):
            if not isinstance(cursor, Mapping) or part not in cursor:
                return default
            cursor = cursor[part]
        return cursor

    def section(self, name: str) -> dict:
        value = self.get(name, {})
        return dict(value) if isinstance(value, Mapping) else {}

    def require(self, dotted_key: str) -> Any:
        sentinel = object()
        value = self.get(dotted_key, sentinel)
        if value is sentinel:
            raise KeyError(f"missing required configuration key: {dotted_key}")
        return value

    def as_dict(self) -> dict:
        return copy.deepcopy(self._data)

    def __getitem__(self, dotted_key: str) -> Any:
        return self.require(dotted_key)

    def __contains__(self, dotted_key: str) -> bool:
        return self.get(dotted_key, None) is not None

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"Config(source={self.source}, keys={len(self._data)})"


def load_config(
    path: str | Path | None = None,
    overrides: Mapping[str, Any] | None = None,
    use_env: bool = True,
) -> Config:
    """Load configuration from YAML, then apply overrides.

    Precedence (lowest to highest): file -> environment -> explicit overrides.
    """
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    data: dict = {}
    if config_path.exists():
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, Mapping):
            raise ValueError(f"configuration root must be a mapping: {config_path}")
        data = dict(loaded)
    elif path is not None:
        raise FileNotFoundError(f"configuration file not found: {config_path}")

    if use_env:
        _deep_merge(data, _env_overrides())
    if overrides:
        _deep_merge(data, overrides)

    return Config(data, source=config_path if config_path.exists() else None)
