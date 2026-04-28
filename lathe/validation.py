"""Trust-boundary JSON validation helper.

Plan 07 Phase 1 / BL-19. Central entry point for every JSON payload crossing a
trust boundary into Lathe: user-supplied runtime configs, network-sourced
provider responses, etc. Loads a schema by id from ``schema/<id>.schema.json``,
validates with ``jsonschema.Draft202012Validator``, and returns the parsed
payload.

Callers should use :func:`validate_json` (file on disk) or
:func:`validate_json_bytes` (already-buffered bytes/str, e.g. an HTTP response
body).
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any

import jsonschema

from .errors import LatheConfigError


class JSONValidationError(LatheConfigError):
    """Raised when a trust-boundary JSON payload fails schema validation."""

    def __init__(
        self,
        source: str,
        schema_id: str,
        pointer: str,
        message: str,
        *,
        snippet: str | None = None,
    ) -> None:
        detail = f" (value={snippet})" if snippet else ""
        super().__init__(
            f"{schema_id} payload from {source} failed schema validation at {pointer}: {message}{detail}"
        )
        self.source = source
        self.schema_id = schema_id
        self.pointer = pointer


_SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"
_VALIDATOR_CACHE: dict[str, jsonschema.Draft202012Validator] = {}
_SCHEMA_CACHE: dict[str, dict[str, Any]] = {}

DEFAULT_MAX_BYTES = 256 * 1024


def _load_validator(schema_id: str) -> tuple[jsonschema.Draft202012Validator, dict[str, Any]]:
    if schema_id in _VALIDATOR_CACHE:
        return _VALIDATOR_CACHE[schema_id], _SCHEMA_CACHE[schema_id]
    schema_path = _SCHEMA_DIR / f"{schema_id}.schema.json"
    try:
        schema_text = schema_path.read_text(encoding="utf-8")
        schema = json.loads(schema_text)
    except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LatheConfigError(
            f"JSON schema '{schema_id}' at {schema_path} could not be loaded: {exc}"
        ) from exc
    validator = jsonschema.Draft202012Validator(schema)
    _VALIDATOR_CACHE[schema_id] = validator
    _SCHEMA_CACHE[schema_id] = schema
    return validator, schema


def _format_pointer(path_deque: Any) -> str:
    parts = [str(p) for p in path_deque]
    return "/" + "/".join(parts) if parts else "/"


def _collect_unknown_keys(raw: Any, schema: Any, prefix: str = "") -> list[str]:
    unknown: list[str] = []
    if not isinstance(raw, dict) or not isinstance(schema, dict):
        return unknown
    properties = schema.get("properties") or {}
    if properties:
        for key, value in raw.items():
            path = f"{prefix}/{key}" if prefix else f"/{key}"
            if key not in properties:
                unknown.append(path)
            else:
                unknown.extend(_collect_unknown_keys(value, properties[key], path))
    else:
        for key, value in raw.items():
            path = f"{prefix}/{key}" if prefix else f"/{key}"
            unknown.extend(_collect_unknown_keys(value, {}, path))
    return unknown


def _run_validator(
    raw: Any,
    schema_id: str,
    source: str,
) -> Any:
    validator, schema = _load_validator(schema_id)
    errors = sorted(validator.iter_errors(raw), key=lambda e: list(e.absolute_path))
    if errors:
        first = errors[0]
        pointer = _format_pointer(first.absolute_path)
        snippet = repr(first.instance)
        if len(snippet) > 120:
            snippet = snippet[:117] + "..."
        raise JSONValidationError(
            source=source,
            schema_id=schema_id,
            pointer=pointer,
            message=first.message,
            snippet=snippet,
        )
    unknown_keys = _collect_unknown_keys(raw, schema)
    if unknown_keys:
        warnings.warn(
            f"{schema_id} payload from {source} contains unknown keys "
            f"(accepted, will become errors in a future release): "
            f"{', '.join(unknown_keys)}",
            stacklevel=3,
        )
    return raw


def validate_json(
    path: str | Path,
    schema_id: str,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> Any:
    """Read ``path``, enforce a size cap, parse as JSON, validate against ``schema_id``.

    ``schema_id`` resolves to ``schema/<schema_id>.schema.json`` at repo root.
    Raises :class:`JSONValidationError` on schema failure; re-raises
    :class:`LatheConfigError` for I/O or parse failures.
    """
    source = str(path)
    file_path = Path(path)
    try:
        stat_result = file_path.stat()
    except FileNotFoundError as exc:
        raise LatheConfigError(f"JSON file not found: {source}") from exc
    except OSError as exc:
        raise LatheConfigError(f"JSON file could not be stat'd ({source}): {exc}") from exc
    if stat_result.st_size > max_bytes:
        raise LatheConfigError(f"JSON file exceeds {max_bytes} bytes ({stat_result.st_size} bytes): {source}")
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise LatheConfigError(f"JSON file is not valid UTF-8 ({source}): {exc}") from exc
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LatheConfigError(
            f"JSON file contains invalid JSON ({source}): {exc.msg} at line {exc.lineno}, column {exc.colno}"
        ) from exc
    return _run_validator(raw, schema_id, source)


def validate_json_bytes(
    body: str | bytes,
    schema_id: str,
    *,
    source: str,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> Any:
    """Validate an already-buffered JSON payload (HTTP response, pipe, etc.).

    ``source`` is a human-readable label (e.g. a URL) used in error messages.
    """
    if isinstance(body, bytes):
        if len(body) > max_bytes:
            raise LatheConfigError(
                f"JSON payload from {source} exceeds {max_bytes} bytes ({len(body)} bytes)"
            )
        try:
            text = body.decode("utf-8", errors="replace")
        except UnicodeDecodeError as exc:
            raise LatheConfigError(f"JSON payload from {source} is not valid UTF-8: {exc}") from exc
    else:
        if len(body.encode("utf-8", errors="replace")) > max_bytes:
            raise LatheConfigError(f"JSON payload from {source} exceeds {max_bytes} bytes")
        text = body
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LatheConfigError(
            f"JSON payload from {source} is not valid JSON: "
            f"{exc.msg} at line {exc.lineno}, column {exc.colno}"
        ) from exc
    return _run_validator(raw, schema_id, source)


__all__ = [
    "DEFAULT_MAX_BYTES",
    "JSONValidationError",
    "validate_json",
    "validate_json_bytes",
]
