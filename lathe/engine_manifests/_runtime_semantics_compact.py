"""Shared compact-summary computation for engine runtime_semantics.

The package stage produces ``runtime_semantics`` with shape::

    {
        "schema": "lathe.engine_runtime_semantics.v1",
        "systems": {
            "<system_name>": {
                "schema": "...",                # optional per-system IR schema
                "source": "build.execution",
                "active": bool,
                "active_fields": [str, ...],
                "counts": {field: int, ...},
                "ids": {field: [id, ...], ...},
            },
            ...
        },
    }

Each engine adapter (Unity YAML, Godot ``.tres``, Unreal JSON sidecar) needs
the same normalized iteration shape, so the canonical reduction lives here.
"""

from __future__ import annotations

from typing import Any


SCHEMA_FALLBACK = "lathe.engine_runtime_semantics.v1"


def runtime_semantics_summary(semantics: Any) -> dict[str, Any] | None:
    """Return ``{schema, systems: [normalized_system, ...]}`` or ``None``.

    The systems list preserves dict iteration order from the source so that
    sidecars stay stable across runs (Python dicts are insertion-ordered, and
    the package stage builds them deterministically).
    """
    if not isinstance(semantics, dict):
        return None
    systems = semantics.get("systems")
    if not isinstance(systems, dict):
        return None
    normalized: list[dict[str, Any]] = []
    for name, system in systems.items():
        if not isinstance(name, str) or not isinstance(system, dict):
            continue
        normalized.append(_normalize_system(name, system))
    return {
        "schema": str(semantics.get("schema") or SCHEMA_FALLBACK),
        "systems": normalized,
    }


def _normalize_system(name: str, system: dict[str, Any]) -> dict[str, Any]:
    active_fields_raw = system.get("active_fields")
    active_fields: list[str] = []
    if isinstance(active_fields_raw, list):
        active_fields = [str(f) for f in active_fields_raw if isinstance(f, str)]

    counts_raw = system.get("counts")
    counts: dict[str, int] = {}
    if isinstance(counts_raw, dict):
        for field, count in counts_raw.items():
            if isinstance(field, str) and isinstance(count, int):
                counts[field] = count

    ids_raw = system.get("ids")
    ids: dict[str, list[str]] = {}
    if isinstance(ids_raw, dict):
        for field, values in ids_raw.items():
            if not isinstance(field, str) or not isinstance(values, list):
                continue
            ids[field] = [str(v) for v in values if v is not None]

    source = system.get("source")
    schema = system.get("schema")
    return {
        "name": name,
        "active": bool(system.get("active")),
        "source": str(source) if isinstance(source, str) and source else None,
        "schema": str(schema) if isinstance(schema, str) and schema else None,
        "active_fields": active_fields,
        "counts": counts,
        "ids": ids,
    }
