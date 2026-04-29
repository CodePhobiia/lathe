"""Source-span helpers for generated Wonder scene source diagnostics."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .source import SCENE_GRAPH_PAYLOAD_BEGIN, SCENE_GRAPH_PAYLOAD_END


def attach_source_spans(
    diagnostics: Sequence[Mapping[str, Any]],
    source_text: str,
    *,
    source_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Attach truthful source spans and repair hints where the generated source maps cleanly."""
    return [
        _diagnostic_with_source_context(diagnostic, source_text, source_path=source_path)
        for diagnostic in diagnostics
    ]


def source_span_for_json_pointer(
    source_text: str,
    pointer: str,
    *,
    source_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """Return the generated source location for a JSON pointer if it can be mapped."""
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        return None
    block = _embedded_json_block(source_text)
    if block is None:
        return _first_content_span(source_text, source_path=source_path)
    begin_line_index, json_lines = block
    try:
        payload = json.loads("\n".join(json_lines))
    except json.JSONDecodeError:
        return None

    found, value = _value_at_pointer(payload, pointer)
    if not found:
        return None
    needle = _needle_for_pointer(pointer, value)
    if needle is None:
        return None
    for offset, line in enumerate(json_lines):
        column = line.find(needle)
        if column < 0:
            continue
        source_line = begin_line_index + offset + 2
        span: dict[str, Any] = {
            "line": source_line,
            "column": column + 1,
            "end_line": source_line,
            "end_column": column + len(needle) + 1,
        }
        if source_path is not None:
            span["file"] = str(source_path)
        return span
    return None


def repair_hint_for_diagnostic(diagnostic: Mapping[str, Any]) -> str:
    """Return a deterministic repair hint suitable for LLM-facing diagnostics."""
    code = str(diagnostic.get("code") or "")
    path = str(diagnostic.get("path") or diagnostic.get("json_pointer") or "/")
    message = str(diagnostic.get("message") or "")
    if code in {"SS1001", "SS1002", "SS1003", "SS1004", "SS1005"}:
        return "Use generated scene source with one embedded Scene Graph JSON payload, then rerun source conversion."
    if code == "WONDER_SCHEMA_VALIDATION" and "does not match" in message:
        return "Use a schema-valid stable ID at the indicated source span, then validate the Scene Graph again."
    if code == "WONDER_SCHEMA_VALIDATION" and "required property" in message:
        return "Add the missing required field at the indicated JSON pointer, then validate again."
    if code.startswith("S10"):
        return "Choose an existing stable Scene Graph reference or add the referenced entity before validating again."
    if code.startswith("SP"):
        return "Keep the Scene Plan deterministic and rerun validation after the smallest schema-valid edit."
    return f"Fix the value at {path} and rerun the relevant validator."


def _diagnostic_with_source_context(
    diagnostic: Mapping[str, Any],
    source_text: str,
    *,
    source_path: str | Path | None,
) -> dict[str, Any]:
    updated = copy.deepcopy(dict(diagnostic))
    if "source_span" not in updated:
        pointer = str(updated.get("path") or updated.get("json_pointer") or "/")
        span = source_span_for_json_pointer(source_text, pointer, source_path=source_path)
        if span is not None:
            updated["source_span"] = span
    updated.setdefault("repair_hint", repair_hint_for_diagnostic(updated))
    return updated


def _embedded_json_block(source_text: str) -> tuple[int, list[str]] | None:
    lines = source_text.splitlines()
    begin = next((index for index, line in enumerate(lines) if line.strip() == SCENE_GRAPH_PAYLOAD_BEGIN), None)
    end = next((index for index, line in enumerate(lines) if line.strip() == SCENE_GRAPH_PAYLOAD_END), None)
    if begin is None or end is None or end <= begin:
        return None
    return begin, lines[begin + 1 : end]


def _first_content_span(source_text: str, *, source_path: str | Path | None) -> dict[str, Any] | None:
    for index, line in enumerate(source_text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        column = line.find(stripped) + 1
        span: dict[str, Any] = {
            "line": index,
            "column": column,
            "end_line": index,
            "end_column": column + len(stripped),
        }
        if source_path is not None:
            span["file"] = str(source_path)
        return span
    return None


def _decode_pointer(pointer: str) -> list[str]:
    if pointer in {"", "/"}:
        return []
    return [part.replace("~1", "/").replace("~0", "~") for part in pointer.lstrip("/").split("/")]


def _value_at_pointer(payload: Any, pointer: str) -> tuple[bool, Any]:
    current = payload
    for part in _decode_pointer(pointer):
        if isinstance(current, list):
            if not part.isdigit():
                return False, None
            index = int(part)
            if index >= len(current):
                return False, None
            current = current[index]
            continue
        if isinstance(current, Mapping):
            if part not in current:
                return False, None
            current = current[part]
            continue
        return False, None
    return True, current


def _needle_for_pointer(pointer: str, value: Any) -> str | None:
    parts = _decode_pointer(pointer)
    if not parts:
        return None
    key = parts[-1]
    if not key.isdigit():
        return f"{json.dumps(key)}: {json.dumps(value, ensure_ascii=False, sort_keys=True)}"
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


__all__ = [
    "attach_source_spans",
    "repair_hint_for_diagnostic",
    "source_span_for_json_pointer",
]
