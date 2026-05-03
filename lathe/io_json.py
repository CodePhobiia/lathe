"""Shared JSON-loading helpers with structured error wrapping.

The conservative pattern in :mod:`lathe.asset_quality.certification` —
catching ``json.JSONDecodeError`` only — leaks raw ``OSError`` and
``UnicodeDecodeError`` tracebacks to CLI users when bundle files are
missing or corrupt. This module promotes that pattern to a single helper
that catches all three classes and surfaces a typed Lathe error.

The helper is intentionally narrow: it only handles the "load a JSON
object from a path" shape, which is what every offending callsite was
doing. Callers that need different error types pass an ``error_cls``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import BuildError, LatheError

__all__ = ["load_json_dict"]


def load_json_dict(
    path: Path,
    *,
    error_cls: type[LatheError] = BuildError,
    label: str | None = None,
) -> dict[str, Any]:
    """Load ``path`` as a JSON object, raising ``error_cls`` on failure.

    Args:
        path: File to read.
        error_cls: Lathe exception class to raise on read/decode/typecheck
            failure. Defaults to :class:`BuildError` since most callers
            today live in the build pipeline.
        label: Optional human-readable label for error messages (defaults
            to the path).

    Returns:
        The parsed top-level JSON object.

    Raises:
        ``error_cls``: When the file cannot be read, is not valid UTF-8,
            is not valid JSON, or the top-level value is not a JSON
            object.
    """
    name = label or str(path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise error_cls(f"could not read {name}: {exc}") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise error_cls(f"{name} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise error_cls(f"{name} top-level JSON value must be an object")
    return payload
