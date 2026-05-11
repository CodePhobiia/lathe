"""SDF field program — expose extracted implicit-field geometry as a KernelProgram result.

Per the §5.3 decomposition, this module hosts the ``sdf_field``
family. The implicit-field operand has already been extracted to a
trimesh by the upstream construction layer; this executor wraps that
geometry with the standard kernel-program trace surface so downstream
stages see a uniform ``KernelProgramResult``.

The pair (manifest builder, executor) is small because no boolean
composition, fallback, or kernel-side mutation happens here — the
program is essentially a passthrough plus trace.
"""

from __future__ import annotations

import math
from typing import Any

import trimesh

from ..kernel import GeometryKernel
from ._capabilities import _kernel_capabilities, _require_capabilities
from ._common import (
    _copy_kernel_import_stats,
    _non_empty_mesh,
    _operation_id_fragment,
    _record_result_probe,
    _sequence_count,
)
from ._core import KernelOperand, KernelProgramResult, sdf_field_operation_count
from ._face_operation import _attach_direct_face_operation_metadata
from ._records import _operand_operation_records
from ._semantic import (
    _operation_counts,
    _semantic_operation_records_from_manifest,
)
from ._semantic_handoff import _attach_kernel_program_semantic_handoff
from ._serialize import _dict_metadata, _json_safe

KERNEL_PROGRAM_VERSION = "lathe.geometry.kernel_program_v1"


def _sdf_field_source_stats(source: KernelOperand) -> dict[str, Any]:
    """Extract SDF-modifier audit stats from the source operand's metadata."""
    metadata = _dict_metadata(source.metadata)
    semantic_metadata = _dict_metadata(metadata.get("semantic_metadata"))
    source_shape = _dict_metadata(semantic_metadata.get("source_shape_primitive"))
    v2_metadata = _dict_metadata(semantic_metadata.get("shape_ir_v2"))
    modifier = _dict_metadata(v2_metadata.get("v2_sdf_metaball_cluster_modifier"))
    stats: dict[str, Any] = {
        "source_primitive_type": source.primitive_type or str(source_shape.get("primitive_type") or ""),
        "source_part": source.part or str(source_shape.get("part") or ""),
    }
    for key in ("mesh_vertices", "mesh_faces"):
        count = _sequence_count(source_shape.get(key))
        if count:
            stats[f"{key}_count"] = count
    kernel_import = _dict_metadata(metadata.get("kernel_import"))
    _copy_kernel_import_stats(stats, kernel_import)
    if modifier:
        stats["source_modifier"] = "v2_sdf_metaball_cluster_modifier"
        stats["source_modifier_method"] = str(modifier.get("method") or "")
        for numeric_key in (
            "blob_count",
            "radius_cm",
            "field_radius_cm",
            "smooth_radius_cm",
            "connection_distance_cm",
            "effective_spread_radius_cm",
            "result_body_count",
            "resolution",
            "bounds_radius_cm",
            "seed",
        ):
            value = modifier.get(numeric_key)
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                stats[numeric_key] = float(value)
        for text_key in (
            "requested_extraction_backend",
            "actual_extraction_backend",
            "extraction_fallback_reason",
        ):
            if modifier.get(text_key) not in (None, "", (), [], {}):
                stats[text_key] = str(modifier.get(text_key) or "")
        attempts = modifier.get("attempted_extraction_backends")
        if isinstance(attempts, list):
            stats["attempted_extraction_backends"] = [str(item) for item in attempts]
        blob_records = modifier.get("blob_records")
        if isinstance(blob_records, list):
            stats["blob_record_count"] = len(blob_records)
    return stats


def build_sdf_field_program_manifest(
    source: KernelOperand,
    *,
    semantic_operation: str = "solid.sdf_metaball_cluster",
    field_kind: str = "sdf_field",
    route: str = "sdf_field_program",
    backend: str | None = None,
    operation_limit: int | None = None,
) -> dict[str, Any]:
    """Return a deterministic, handle-free manifest for implicit-field geometry."""
    operation_records = _operand_operation_records([source])
    if not any(str(record.get("operation") or "") == semantic_operation for record in operation_records):
        operation_records.append(
            {
                "operation_id": f"program:{_operation_id_fragment(route)}:{_operation_id_fragment(semantic_operation)}",
                "operation": semantic_operation,
                "repair_action": "",
                "operand_id": source.operand_id,
                "operand_index": 0,
                "part": source.part or "",
                "primitive_type": source.primitive_type or "",
                "blend_mode": source.blend_mode,
                "source": "kernel_program.sdf_field",
                "field_kind": field_kind,
            }
        )
    diagnostics: list[dict[str, Any]] = []
    if source.handle is None:
        diagnostics.append(
            {
                "code": "missing_kernel_operand_handle",
                "severity": "error",
                "operand_ids": [source.operand_id],
            }
        )
    operation_count = sdf_field_operation_count(source)
    if operation_limit is not None and operation_count > operation_limit:
        diagnostics.append(
            {
                "code": "kernel_program_operation_limit_exceeded",
                "severity": "error",
                "operation_count": operation_count,
                "operation_limit": operation_limit,
            }
        )
    return {
        "schema": "lathe.geometry.kernel_program_manifest.v1",
        "version": KERNEL_PROGRAM_VERSION,
        "program_kind": "sdf_field",
        "route": route,
        "backend": backend,
        "operation_count": operation_count,
        "kernel_call_count": operation_count,
        "operation_limit": operation_limit,
        "required_capabilities": ["to_trimesh"],
        "operand_count": 1,
        "operands": [_json_safe(source.trace_record())],
        "semantic_operation_record_count": len(operation_records),
        "semantic_operation_counts": _operation_counts(operation_records),
        "semantic_operation_records": _json_safe(operation_records),
        "semantic_operation": semantic_operation,
        "field_kind": field_kind,
        "source_primitive_type": source.primitive_type or "",
        "diagnostics": diagnostics,
    }


def execute_sdf_field_program(
    kernel: GeometryKernel,
    source: KernelOperand,
    *,
    semantic_operation: str = "solid.sdf_metaball_cluster",
    field_kind: str = "sdf_field",
    operation_limit: int | None = None,
    route: str = "sdf_field_program",
    backend: str | None = None,
) -> KernelProgramResult:
    """Expose extracted implicit-field geometry as a typed KernelProgram result."""
    if source.handle is None:
        raise ValueError(f"kernel sdf_field source operand {source.operand_id!r} has no handle")
    operation_count = sdf_field_operation_count(source)
    if operation_limit is not None and operation_count > operation_limit:
        raise ValueError(
            f"kernel sdf_field operation_count={operation_count} exceeds limit={operation_limit}"
        )
    capabilities = _kernel_capabilities(kernel)
    required = {"to_trimesh"}
    _require_capabilities(kernel, capabilities, required)
    manifest = build_sdf_field_program_manifest(
        source,
        semantic_operation=semantic_operation,
        field_kind=field_kind,
        route=route,
        backend=backend,
        operation_limit=operation_limit,
    )
    mesh = _non_empty_mesh(kernel, source.handle)
    source_stats = _sdf_field_source_stats(source)
    method = "sdf_field_kernel_build_result_v1"
    if source_stats.get("kernel_import_route") == "exact_mesh.from_trimesh":
        method = "sdf_field_extracted_mesh_import_result_v1"
    sdf_field_metadata = {
        "schema": "lathe.geometry.kernel_sdf_field.v1",
        "operation": semantic_operation,
        "field_kind": field_kind,
        "method": method,
        "attempted_backend": str(source_stats.get("kernel_import_route") or kernel.name),
        "actual_backend": str(source_stats.get("kernel_import_backend") or kernel.name),
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "actual_operation": semantic_operation,
        "fallback": False,
        "passthrough": False,
        "source_face_count": source.source_mesh_face_count or len(mesh.faces),
        "source_vertex_count": len(source.source_mesh.vertices)
        if isinstance(source.source_mesh, trimesh.Trimesh)
        else len(mesh.vertices),
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_watertight": bool(mesh.is_watertight),
        "result_body_count": kernel.body_count(source.handle),
        **source_stats,
    }
    mesh.metadata["lathe_kernel_sdf_field"] = dict(sdf_field_metadata)
    operation_records = _semantic_operation_records_from_manifest(manifest)
    operation_record = {
        "op": "sdf_field",
        "source": source.operand_id,
        "semantic_operation": semantic_operation,
        "field_kind": field_kind,
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "method": method,
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_watertight": bool(mesh.is_watertight),
        "result_body_count": kernel.body_count(source.handle),
        "kernel_sdf_field": dict(sdf_field_metadata),
    }
    _record_result_probe(operation_record, kernel=kernel, result_handle=source.handle)
    (
        face_operation_ids,
        face_operation_summary,
        face_operation_attribution,
    ) = _attach_direct_face_operation_metadata(
        mesh,
        f"{source.operand_id}.{_operation_id_fragment(semantic_operation)}",
        source="kernel_program.sdf_field.source_operand",
        method="sdf_field_source_face_ranges",
    )
    semantic_handoff = _attach_kernel_program_semantic_handoff(
        mesh,
        [source],
        [operation_record],
    )
    details = {
        "kernel_program_version": KERNEL_PROGRAM_VERSION,
        "kernel_program_route": route,
        "kernel_program_operation_count": operation_count,
        "kernel_program_operand_count": 1,
        "kernel_program_semantic_operation_record_count": len(operation_records),
        "kernel_program_semantic_operation_counts": _operation_counts(operation_records),
        "kernel_program_semantic_operation_records": operation_records,
        "kernel_program_kernel": kernel.name,
        "kernel_program_backend": backend,
        "kernel_program_manifest": manifest,
        "kernel_program_capabilities_checked": sorted(required),
        "kernel_program_watertight": kernel.is_watertight(source.handle),
        "kernel_program_body_count": kernel.body_count(source.handle),
        "kernel_program_operands": [source.trace_record()],
        "kernel_program_operations": [operation_record],
        "kernel_program_face_operation_attribution": face_operation_attribution,
        "face_operation_ids": face_operation_ids,
        "face_operation_summary": face_operation_summary,
        "kernel_program_sdf_field_source_operand_id": source.operand_id,
        "sdf_field_semantic_operation": semantic_operation,
        "sdf_field_kind": field_kind,
        "sdf_field_method": method,
        "sdf_field_result_face_count": len(mesh.faces),
        "sdf_field_result_vertex_count": len(mesh.vertices),
        "sdf_field_result_watertight": bool(mesh.is_watertight),
        "kernel_sdf_field": sdf_field_metadata,
        "kernel_program_semantic_handoff": semantic_handoff,
    }
    return KernelProgramResult(
        mesh=mesh,
        handle=source.handle,
        operation_count=operation_count,
        details=details,
    )


__all__ = [
    "build_sdf_field_program_manifest",
    "execute_sdf_field_program",
]
