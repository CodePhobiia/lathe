"""Small generic utilities used across the compiler.

Mapping merging, order-preserving dedup, path helpers and other
dependency-free helpers.
"""

from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from typing import Any


def dedupe_keep_first(values: Iterable[Any]) -> list[Any]:
    """Dedupe keep first.

    Args:
        values: values argument.

    Returns:
        The result.
    """
    seen: set[str] = set()
    out: list[Any] = []
    for value in values:
        key = repr(value)
        if key not in seen:
            seen.add(key)
            out.append(value)
    return out


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Deep merge.

    Args:
        base: base argument.
        overlay: overlay argument.

    Returns:
        The result.
    """
    result = deepcopy(base)
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def get_by_path(obj: dict[str, Any], path: str) -> Any:
    """Get by path.

    Args:
        obj: obj argument.
        path: path argument.

    Returns:
        The result.
    """
    cursor: Any = obj
    for part in path.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            raise KeyError(path)
        cursor = cursor[part]
    return cursor


def has_path(obj: dict[str, Any], path: str) -> bool:
    """Has path.

    Args:
        obj: obj argument.
        path: path argument.

    Returns:
        The result.
    """
    cursor: Any = obj
    for part in path.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            return False
        cursor = cursor[part]
    return True


def set_by_path(obj: dict[str, Any], path: str, value: Any) -> None:
    """Set by path.

    Args:
        obj: obj argument.
        path: path argument.
        value: value argument.
    """
    parts = path.split(".")
    cursor: Any = obj
    for part in parts[:-1]:
        if part not in cursor or not isinstance(cursor[part], dict):
            cursor[part] = {}
        cursor = cursor[part]
    cursor[parts[-1]] = deepcopy(value)


def unset_by_path(obj: dict[str, Any], path: str) -> None:
    """Unset by path.

    Args:
        obj: obj argument.
        path: path argument.
    """
    parts = path.split(".")
    cursor: Any = obj
    for part in parts[:-1]:
        if not isinstance(cursor, dict) or part not in cursor:
            return
        cursor = cursor[part]
    if isinstance(cursor, dict):
        cursor.pop(parts[-1], None)


def append_by_path(obj: dict[str, Any], path: str, value: Any) -> None:
    """Append by path.

    Args:
        obj: obj argument.
        path: path argument.
        value: value argument.
    """
    current = get_by_path(obj, path)
    if not isinstance(current, list):
        raise TypeError(f"Path '{path}' is not a list")
    if isinstance(value, list):
        current.extend(deepcopy(value))
    else:
        current.append(deepcopy(value))


def remove_by_path(obj: dict[str, Any], path: str, value: Any) -> None:
    """Remove by path.

    Args:
        obj: obj argument.
        path: path argument.
        value: value argument.
    """
    current = get_by_path(obj, path)
    if not isinstance(current, list):
        raise TypeError(f"Path '{path}' is not a list")
    values = value if isinstance(value, list) else [value]
    filtered = [item for item in current if item not in values]
    set_by_path(obj, path, filtered)


def deep_fill_missing(target: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    """Deep fill missing.

    Args:
        target: target argument.
        defaults: defaults argument.

    Returns:
        The result.
    """
    out = deepcopy(target)
    for key, default_value in defaults.items():
        if key not in out:
            out[key] = deepcopy(default_value)
        elif isinstance(out[key], dict) and isinstance(default_value, dict):
            out[key] = deep_fill_missing(out[key], default_value)
    return out
