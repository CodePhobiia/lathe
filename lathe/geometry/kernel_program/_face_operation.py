"""Face-operation attribution helpers shared by every per-op executor.

Kernel programs produce a result mesh whose faces must be attributable
to the semantic operations that produced them. Per-op executors
(``execute_boolean_program``, ``execute_hull_program``, etc.) call
into this module to:

  - Summarize per-face operation IDs into a count/source dict.
  - Propagate face-operation IDs through assembly/concat results.
  - Attach attribution metadata onto a result trimesh + return the
    structured attribution dict for the kernel-program trace.

Two small companion helpers live here too: ``_metadata_list`` (safe
list-of-dicts coercion) and ``_copy_source_context_summary`` (merges
``v2_context_*`` aggregates from a source record onto a target record).
They sit alongside the face-operation cluster because they share the
"aggregate-records-into-summary" idiom.

Every helper here is pure or mesh-metadata-only — no kernel calls.
"""

from __future__ import annotations

from contextlib import suppress
from typing import Any

import trimesh

from ._core import KernelOperand
from ._semantic import _final_semantic_operation_record
from ._serialize import _dict_metadata, _json_safe, _stable_unique_strings


def _metadata_list(value: Any) -> list[dict[str, Any]]:
    """Coerce ``value`` into a list of dicts; non-list/non-dict items are dropped."""
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _copy_source_context_summary(
    record: dict[str, Any],
    context_source: Any,
) -> None:
    """Merge ``v2_context_*`` aggregates from ``context_source`` onto ``record``.

    Reads count, part, and primitive-type aggregates from the source
    (under either ``v2_context_*`` or legacy ``context_*`` keys), and
    layers them onto the destination record's ``source_context_*``
    fields. No-op when the source has no context aggregate.
    """
    source = _dict_metadata(context_source)
    if not source:
        return
    raw_count = (
        source.get("v2_context_record_count")
        or source.get("context_record_count")
        or 0
    )
    has_context = bool(
        source.get("v2_context_aggregate")
        or source.get("context_aggregate")
        or raw_count
    )
    if not has_context:
        return
    with suppress(TypeError, ValueError):
        record.setdefault("source_context_record_count", int(raw_count or 1))
    context_parts = _stable_unique_strings(
        source.get("v2_context_parts") or source.get("context_parts") or []
    )
    if context_parts:
        existing_parts = record.get("source_context_parts") or []
        record["source_context_parts"] = _stable_unique_strings(
            [*existing_parts, *context_parts]
        )
    context_primitive_types = _stable_unique_strings(
        source.get("v2_context_primitive_types")
        or source.get("context_primitive_types")
        or []
    )
    if context_primitive_types:
        existing_types = record.get("source_context_primitive_types") or []
        record["source_context_primitive_types"] = _stable_unique_strings(
            [*existing_types, *context_primitive_types]
        )


def _kernel_program_face_operation_summary(
    face_operation_ids: list[str],
    *,
    source: str,
) -> dict[str, Any]:
    """Summarize a per-face operation-id list into a count/source dict."""
    operations = {
        operation_id: face_operation_ids.count(operation_id)
        for operation_id in sorted(set(face_operation_ids))
    }
    return {
        "schema": "lathe.mesh_ir.face_operation_summary.v1",
        "face_count": len(face_operation_ids),
        "operation_count": len(operations),
        "operations": operations,
        "source": source,
    }


def _instance_face_operation_ids(
    instance_operands: list[KernelOperand],
    instance_meshes: list[trimesh.Trimesh],
    result_mesh: trimesh.Trimesh,
    *,
    assembly_method: str,
) -> list[str]:
    """Build a per-face operation-id list for a single-transform/concat result.

    Returns an empty list when the assembly method is not one the
    propagation rules cover, when any source instance lacks face
    coverage, or when the result's face count does not match the
    summed source counts (the safety check that catches surface-
    altering booleans which invalidate per-face attribution).
    """
    if not instance_operands:
        return []
    method = str(assembly_method or "")
    if method != "single_transform" and "mesh_concatenation" not in method:
        return []
    face_operation_ids: list[str] = []
    for operand, instance_mesh in zip(instance_operands, instance_meshes, strict=False):
        if not isinstance(instance_mesh, trimesh.Trimesh):
            return []
        metadata = getattr(instance_mesh, "metadata", None)
        source_face_operation_ids = (
            metadata.get("face_operation_ids")
            if isinstance(metadata, dict)
            else None
        )
        if (
            isinstance(source_face_operation_ids, list)
            and len(source_face_operation_ids) == len(instance_mesh.faces)
        ):
            face_operation_ids.extend(
                str(operation_id) for operation_id in source_face_operation_ids
            )
            continue
        face_operation_ids.extend([operand.operand_id] * len(instance_mesh.faces))
    if len(face_operation_ids) != len(result_mesh.faces):
        return []
    return face_operation_ids


def _attach_direct_face_operation_metadata(
    mesh: trimesh.Trimesh,
    operation_id: str,
    *,
    source: str,
    method: str,
) -> tuple[list[str], dict[str, Any], dict[str, Any]]:
    """Attribute every face of ``mesh`` to a single ``operation_id`` and stamp metadata.

    Used by per-op executors that produce one semantic operation per
    program. Returns the face-id list, the summary dict, and the
    structured attribution dict (also written onto ``mesh.metadata``
    alongside the raw ``face_operation_ids`` / ``face_operation_summary``).
    """
    face_operation_ids = [str(operation_id)] * len(mesh.faces)
    face_operation_summary = _kernel_program_face_operation_summary(
        face_operation_ids,
        source=source,
    )
    face_operation_attribution = {
        "schema": "lathe.geometry.kernel_program_face_operation_attribution.v1",
        "source": source,
        "attributed": True,
        "method": method,
        "result_face_count": len(mesh.faces),
        "face_operation_count": 1 if face_operation_ids else 0,
        "face_operation_attribution_count": len(face_operation_ids),
    }
    mesh.metadata["face_operation_ids"] = list(face_operation_ids)
    mesh.metadata["face_operation_summary"] = dict(face_operation_summary)
    mesh.metadata["lathe_kernel_program_face_operation_attribution"] = dict(
        face_operation_attribution
    )
    return face_operation_ids, face_operation_summary, face_operation_attribution


def _attach_whole_result_face_operation_metadata(
    mesh: trimesh.Trimesh,
    operation_id: str,
    *,
    source: str,
    method: str,
    reason: str,
    source_face_ranges_preserved: bool = False,
    extra: dict[str, Any] | None = None,
) -> tuple[list[str], dict[str, Any], dict[str, Any]]:
    """Attribute every face to ``operation_id`` and tag with whole-result scope.

    Used when the executor cannot preserve source-face ranges through
    its boolean/refine/etc. — the entire result is attributed to the
    final semantic operation, with ``attribution_scope`` and
    ``reason`` recording why per-face attribution was not possible.
    """
    face_operation_ids, face_operation_summary, face_operation_attribution = (
        _attach_direct_face_operation_metadata(
            mesh,
            operation_id,
            source=source,
            method=method,
        )
    )
    face_operation_attribution = {
        **dict(face_operation_attribution),
        "attribution_scope": "whole_result_operation",
        "source_face_ranges_preserved": bool(source_face_ranges_preserved),
        "reason": reason,
    }
    if extra:
        face_operation_attribution.update(_json_safe(extra))
    mesh.metadata["lathe_kernel_program_face_operation_attribution"] = dict(
        face_operation_attribution
    )
    return face_operation_ids, face_operation_summary, face_operation_attribution


def _attach_semantic_whole_result_face_metadata(
    mesh: trimesh.Trimesh,
    operation_records: list[dict[str, Any]],
    semantic_operation: str,
    *,
    source: str,
    method: str,
    reason: str,
    extra: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[str], dict[str, Any], dict[str, Any]]:
    """Attribute the result to the last record matching ``semantic_operation``.

    Looks up the final record from ``operation_records`` whose
    ``operation`` matches ``semantic_operation`` (falling back to the
    last record overall). Attributes every face to that operation_id
    if one exists, otherwise records the un-attributed reason on the
    mesh metadata.
    """
    final_operation_record = _final_semantic_operation_record(
        operation_records,
        semantic_operation,
    )
    face_operation_ids: list[str] = []
    face_operation_summary: dict[str, Any] = {}
    face_operation_attribution: dict[str, Any] = {
        "schema": "lathe.geometry.kernel_program_face_operation_attribution.v1",
        "source": source,
        "attributed": False,
        "method": method,
        "result_face_count": len(mesh.faces),
        "reason": reason,
    }
    final_operation_id = str(final_operation_record.get("operation_id") or "")
    if final_operation_id:
        (
            face_operation_ids,
            face_operation_summary,
            face_operation_attribution,
        ) = _attach_whole_result_face_operation_metadata(
            mesh,
            final_operation_id,
            source=source,
            method=method,
            reason=reason,
            extra=extra,
        )
    else:
        if extra:
            face_operation_attribution.update(_json_safe(extra))
        mesh.metadata["lathe_kernel_program_face_operation_attribution"] = dict(
            face_operation_attribution
        )
    return (
        final_operation_record,
        face_operation_ids,
        face_operation_summary,
        face_operation_attribution,
    )


__all__ = [
    "_attach_direct_face_operation_metadata",
    "_attach_semantic_whole_result_face_metadata",
    "_attach_whole_result_face_operation_metadata",
    "_copy_source_context_summary",
    "_instance_face_operation_ids",
    "_kernel_program_face_operation_summary",
    "_metadata_list",
]
