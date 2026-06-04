"""Semantic-operation record helpers shared by every kernel-program executor.

This module groups the small cluster of helpers that read, dedupe,
filter, and select semantic-operation records from kernel-program
manifests and trace operations. Every per-op executor
(``execute_boolean_program``, ``execute_hull_program``, etc.) needs
this surface, so isolating it keeps the per-op modules thin and the
package import graph acyclic.

Every helper here is pure — given the same inputs, returns the same
output. They are intentionally narrow: they manipulate record dicts,
they do not touch a kernel or a manifest builder.
"""

from __future__ import annotations

from typing import Any


def _operation_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    """Tally semantic operations grouped by ``operation`` name.

    Records without an ``operation`` (or ``repair_action`` fallback)
    field are skipped — they do not contribute to the count. The
    returned mapping is sorted alphabetically so manifest output is
    deterministic.
    """
    counts: dict[str, int] = {}
    for record in records:
        operation = str(record.get("operation") or record.get("repair_action") or "")
        if not operation:
            continue
        counts[operation] = counts.get(operation, 0) + 1
    return dict(sorted(counts.items()))


def _semantic_operation_records_from_manifest(
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return a copy of the manifest's ``semantic_operation_records`` list.

    Returns an empty list if the manifest field is missing or not a
    list. Each contained record is shallow-copied so callers cannot
    accidentally mutate the manifest through the returned reference.
    """
    records = manifest.get("semantic_operation_records")
    if not isinstance(records, list):
        return []
    return [dict(record) for record in records if isinstance(record, dict)]


def _dedupe_operation_records(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """De-duplicate records by ``(operation_id, operation, operand_id, source)``.

    Multiple trace passes can emit the same logical record. The dedupe
    key captures the four fields that uniquely identify a semantic
    operation — anything that matches all four is the same operation,
    regardless of payload differences.
    """
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for record in records:
        key = (
            str(record.get("operation_id") or ""),
            str(record.get("operation") or ""),
            str(record.get("operand_id") or ""),
            str(record.get("source") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(dict(record))
    return deduped


def _final_semantic_operation_record(
    records: list[dict[str, Any]],
    semantic_operation: str,
) -> dict[str, Any]:
    """Return the last record matching ``semantic_operation``, or the last record overall.

    When ``semantic_operation`` is empty or no record matches, falls
    back to the last record in the list (since that represents the
    most recent operation in the trace). Returns an empty dict if the
    list itself is empty.
    """
    clean_records = [dict(record) for record in records if isinstance(record, dict)]
    operation = str(semantic_operation or "")
    if operation:
        for record in reversed(clean_records):
            if str(record.get("operation") or "") == operation:
                return record
    return clean_records[-1] if clean_records else {}


def _final_semantic_operation_face_id(
    records: list[dict[str, Any]],
    semantic_operation: str,
    *,
    fallback: str,
) -> tuple[str, dict[str, Any]]:
    """Return ``(operation_id, record)`` for the trace's final matching op.

    ``operation_id`` comes from the matched record's ``operation_id``
    field, falling back to the explicit ``fallback`` string when the
    record has no id. The record is returned alongside so callers can
    reuse it for attribution metadata.
    """
    record = _final_semantic_operation_record(records, semantic_operation)
    operation_id = str(record.get("operation_id") or "")
    return operation_id or str(fallback), record


def _semantic_operation_for_kind(
    records: list[dict[str, Any]],
    operation_kinds: dict[str, str],
    *,
    fallback: str = "",
) -> str:
    """Pick the most recent record whose operation belongs to ``operation_kinds``.

    ``operation_kinds`` is a name → category map: only operations
    appearing as a key match. The ``fallback`` is returned when no
    record matches and is also accepted as a valid match when it
    happens to be one of the kinds itself.
    """
    fallback_text = str(fallback or "")
    if fallback_text in operation_kinds:
        return fallback_text
    for record in reversed(records):
        operation = str(record.get("operation") or "")
        if operation in operation_kinds:
            return operation
    return fallback_text


def _trace_semantic_operation_records(
    trace_operations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Extract per-operation ``semantic_operation_record`` blobs from a trace.

    Each trace operation may carry a nested record describing the
    semantic op it executed. This helper flattens those into a single
    list with ``source`` and ``trace_operation_index`` tags so
    downstream code can route them to the unified record stream.
    """
    records: list[dict[str, Any]] = []
    for operation_index, operation in enumerate(trace_operations):
        if not isinstance(operation, dict):
            continue
        record = operation.get("semantic_operation_record")
        if not isinstance(record, dict):
            continue
        copied = dict(record)
        copied.setdefault("source", "kernel_program.trace_operation")
        copied.setdefault("trace_operation_index", int(operation_index))
        records.append(copied)
    return records


__all__ = [
    "_dedupe_operation_records",
    "_final_semantic_operation_face_id",
    "_final_semantic_operation_record",
    "_operation_counts",
    "_semantic_operation_for_kind",
    "_semantic_operation_records_from_manifest",
    "_trace_semantic_operation_records",
]
