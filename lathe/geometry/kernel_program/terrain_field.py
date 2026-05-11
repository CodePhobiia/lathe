"""Terrain field program — expose generated heightfield terrain as a KernelProgram result.

Per the §5.3 decomposition, this module hosts the ``terrain_field``
family. The terrain operand has already been generated and imported
to a trimesh by the upstream construction layer; this executor wraps
that geometry with the standard kernel-program trace surface so
downstream stages see a uniform ``KernelProgramResult``.

Structurally identical to ``sdf_field`` — both are field primitives
that route through the standard ``to_trimesh`` capability with no
boolean composition or kernel-side mutation.
"""

from __future__ import annotations

from contextlib import suppress
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
)
from ._core import KernelOperand, KernelProgramResult, terrain_field_operation_count
from ._face_operation import _attach_direct_face_operation_metadata
from ._records import _operand_operation_records
from ._semantic import (
    _operation_counts,
    _semantic_operation_records_from_manifest,
)
from ._semantic_handoff import _attach_kernel_program_semantic_handoff
from ._serialize import _dict_metadata, _json_safe

KERNEL_PROGRAM_VERSION = "lathe.geometry.kernel_program_v1"


def _terrain_field_source_stats(source: KernelOperand) -> dict[str, Any]:
    """Extract terrain-modifier audit stats from the source operand's metadata."""
    metadata = _dict_metadata(source.metadata)
    semantic_metadata = _dict_metadata(metadata.get("semantic_metadata"))
    source_shape = _dict_metadata(semantic_metadata.get("source_shape_primitive"))
    v2_metadata = _dict_metadata(semantic_metadata.get("shape_ir_v2"))
    modifier = _dict_metadata(v2_metadata.get("v2_terrain_patch_modifier"))
    stats: dict[str, Any] = {
        "source_primitive_type": source.primitive_type or str(source_shape.get("primitive_type") or ""),
        "source_part": source.part or str(source_shape.get("part") or ""),
    }
    resolution = source_shape.get("resolution")
    if isinstance(resolution, (list, tuple)) and len(resolution) >= 2:
        with suppress(TypeError, ValueError):
            stats["heightfield_resolution"] = [int(resolution[0]), int(resolution[1])]
    height_data = source_shape.get("height_data")
    if isinstance(height_data, list) and height_data:
        row_count = len(height_data)
        column_count = max(
            (
                len(row)
                for row in height_data
                if isinstance(row, (list, tuple))
            ),
            default=0,
        )
        stats["height_data_row_count"] = int(row_count)
        stats["height_data_column_count"] = int(column_count)
        heights: list[float] = []
        for row in height_data:
            if not isinstance(row, (list, tuple)):
                continue
            for value in row:
                with suppress(TypeError, ValueError):
                    numeric = float(value)
                    if math.isfinite(numeric):
                        heights.append(numeric)
        if heights:
            stats["height_min"] = min(heights)
            stats["height_max"] = max(heights)
            stats["height_span"] = max(heights) - min(heights)
    bounds_xy = source_shape.get("bounds_xy")
    if isinstance(bounds_xy, (list, tuple)) and len(bounds_xy) == 4:
        with suppress(TypeError, ValueError):
            stats["bounds_xy"] = [float(value) for value in bounds_xy]
    vertical_scale = source_shape.get("vertical_scale")
    if isinstance(vertical_scale, (int, float)) and math.isfinite(float(vertical_scale)):
        stats["vertical_scale_cm"] = float(vertical_scale)
    kernel_import = _dict_metadata(metadata.get("kernel_import"))
    if kernel_import:
        _copy_kernel_import_stats(stats, kernel_import)
        if bool(kernel_import.get("surface_primitive_solidified")):
            stats["surface_primitive_solidified"] = True
            stats["solidification_method"] = str(kernel_import.get("method") or "")
    if modifier:
        stats["source_modifier"] = "v2_terrain_patch_modifier"
        stats["source_modifier_method"] = str(modifier.get("method") or "")
        for numeric_key in (
            "width_cm",
            "depth_cm",
            "height_cm",
            "resolution",
            "seed",
            "roughness",
            "octaves",
            "border_taper",
            "terrace_count",
            "terrace_strength",
            "erosion_strength",
        ):
            value = modifier.get(numeric_key)
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                stats[numeric_key] = float(value)
        if modifier.get("biome") not in (None, "", (), [], {}):
            stats["biome"] = str(modifier.get("biome") or "")
    return stats


def build_terrain_field_program_manifest(
    source: KernelOperand,
    *,
    semantic_operation: str = "solid.terrain_patch",
    terrain_kind: str = "terrain_patch",
    route: str = "terrain_field_program",
    backend: str | None = None,
    operation_limit: int | None = None,
) -> dict[str, Any]:
    """Return a deterministic, handle-free manifest for terrain heightfield geometry."""
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
                "source": "kernel_program.terrain_field",
                "terrain_kind": terrain_kind,
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
    operation_count = terrain_field_operation_count(source)
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
        "program_kind": "terrain_field",
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
        "terrain_kind": terrain_kind,
        "source_primitive_type": source.primitive_type or "",
        "diagnostics": diagnostics,
    }


def execute_terrain_field_program(
    kernel: GeometryKernel,
    source: KernelOperand,
    *,
    semantic_operation: str = "solid.terrain_patch",
    terrain_kind: str = "terrain_patch",
    operation_limit: int | None = None,
    route: str = "terrain_field_program",
    backend: str | None = None,
) -> KernelProgramResult:
    """Expose generated heightfield terrain as a typed KernelProgram result."""
    if source.handle is None:
        raise ValueError(f"kernel terrain_field source operand {source.operand_id!r} has no handle")
    operation_count = terrain_field_operation_count(source)
    if operation_limit is not None and operation_count > operation_limit:
        raise ValueError(
            f"kernel terrain_field operation_count={operation_count} exceeds limit={operation_limit}"
        )
    capabilities = _kernel_capabilities(kernel)
    required = {"to_trimesh"}
    _require_capabilities(kernel, capabilities, required)
    manifest = build_terrain_field_program_manifest(
        source,
        semantic_operation=semantic_operation,
        terrain_kind=terrain_kind,
        route=route,
        backend=backend,
        operation_limit=operation_limit,
    )
    mesh = _non_empty_mesh(kernel, source.handle)
    source_stats = _terrain_field_source_stats(source)
    method = "terrain_field_kernel_build_result_v1"
    if bool(source_stats.get("surface_primitive_solidified")):
        method = "terrain_heightfield_solidified_kernel_result_v1"
    elif source_stats.get("kernel_import_route") == "exact_mesh.from_trimesh":
        method = "terrain_heightfield_exact_mesh_import_result_v1"
    terrain_field_metadata = {
        "schema": "lathe.geometry.kernel_terrain_field.v1",
        "operation": semantic_operation,
        "terrain_kind": terrain_kind,
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
    mesh.metadata["lathe_kernel_terrain_field"] = dict(terrain_field_metadata)
    operation_records = _semantic_operation_records_from_manifest(manifest)
    operation_record = {
        "op": "terrain_field",
        "source": source.operand_id,
        "semantic_operation": semantic_operation,
        "terrain_kind": terrain_kind,
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "method": method,
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_watertight": bool(mesh.is_watertight),
        "result_body_count": kernel.body_count(source.handle),
        "kernel_terrain_field": dict(terrain_field_metadata),
    }
    _record_result_probe(operation_record, kernel=kernel, result_handle=source.handle)
    (
        face_operation_ids,
        face_operation_summary,
        face_operation_attribution,
    ) = _attach_direct_face_operation_metadata(
        mesh,
        f"{source.operand_id}.{_operation_id_fragment(semantic_operation)}",
        source="kernel_program.terrain_field.source_operand",
        method="terrain_field_source_face_ranges",
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
        "kernel_program_terrain_field_source_operand_id": source.operand_id,
        "terrain_field_semantic_operation": semantic_operation,
        "terrain_field_kind": terrain_kind,
        "terrain_field_method": method,
        "terrain_field_result_face_count": len(mesh.faces),
        "terrain_field_result_vertex_count": len(mesh.vertices),
        "terrain_field_result_watertight": bool(mesh.is_watertight),
        "kernel_terrain_field": terrain_field_metadata,
        "kernel_program_semantic_handoff": semantic_handoff,
    }
    return KernelProgramResult(
        mesh=mesh,
        handle=source.handle,
        operation_count=operation_count,
        details=details,
    )


__all__ = [
    "build_terrain_field_program_manifest",
    "execute_terrain_field_program",
]
