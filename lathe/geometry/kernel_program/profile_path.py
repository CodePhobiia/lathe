"""Profile path program — expose sweep/loft/profile geometry as a KernelProgram result.

Per the §5.3 decomposition, this module hosts the ``profile_path``
family — sweep, loft, polywire, helical sweep, spring, curved tube,
threaded cylinder, curve profile / sweep / loft. The operand is
already a generated mesh by the time it reaches the executor; the
executor wraps it with the standard kernel-program trace surface so
downstream stages see a uniform ``KernelProgramResult``.

Structurally similar to ``sdf_field`` and ``terrain_field`` — all
three are field-style passthroughs through ``to_trimesh`` with no
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
    _sequence_count,
)
from ._core import KernelOperand, KernelProgramResult, profile_path_operation_count
from ._face_operation import _attach_direct_face_operation_metadata
from ._records import _operand_operation_records
from ._semantic import (
    _operation_counts,
    _semantic_operation_records_from_manifest,
)
from ._semantic_handoff import _attach_kernel_program_semantic_handoff
from ._serialize import _dict_metadata, _json_safe

KERNEL_PROGRAM_VERSION = "lathe.geometry.kernel_program_v1"

_PROFILE_CURVE_NUMERIC_METADATA_KEYS = (
    "degree",
    "order",
    "input_point_count",
    "sampled_point_count",
    "weight_count",
    "knot_count",
)
_PROFILE_CURVE_BOOL_METADATA_KEYS = (
    "rational",
    "periodic",
    "custom_knots",
    "closed_polygon",
    "closed_curve",
)


def _copy_profile_curve_metadata_stats(
    stats: dict[str, Any],
    *,
    prefix: str,
    payload: Any,
) -> None:
    """Copy a single profile-curve's metadata under ``stats[prefix_*]``."""
    curve = _dict_metadata(payload)
    if not curve:
        return
    for key in ("curve_kind", "degree_source_parameter"):
        value = curve.get(key)
        if value not in (None, ""):
            stats[f"{prefix}_{key}"] = str(value)
    for key in _PROFILE_CURVE_NUMERIC_METADATA_KEYS:
        value = curve.get(key)
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            stats[f"{prefix}_{key}"] = int(value)
    for key in _PROFILE_CURVE_BOOL_METADATA_KEYS:
        if key in curve:
            stats[f"{prefix}_{key}"] = bool(curve.get(key))


def _copy_section_curve_metadata_stats(
    stats: dict[str, Any],
    *,
    payload: Any,
) -> None:
    """Summarize a list of section-curve metadata records onto ``stats``."""
    if not isinstance(payload, (list, tuple)):
        return
    kinds: list[str] = []
    degrees: list[int] = []
    orders: list[int] = []
    rational_count = 0
    periodic_count = 0
    for item in payload:
        curve = _dict_metadata(item)
        kind = str(curve.get("curve_kind") or "")
        if kind:
            kinds.append(kind)
        if curve.get("rational"):
            rational_count += 1
        if curve.get("periodic"):
            periodic_count += 1
        for key, out in (("degree", degrees), ("order", orders)):
            value = curve.get(key)
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                out.append(int(value))
    if kinds:
        unique_kinds = sorted(set(kinds))
        stats["section_curve_kinds"] = unique_kinds
        stats["section_curve_kind_count"] = len(unique_kinds)
    if degrees:
        stats["section_curve_degree_min"] = min(degrees)
        stats["section_curve_degree_max"] = max(degrees)
    if orders:
        stats["section_curve_order_min"] = min(orders)
        stats["section_curve_order_max"] = max(orders)
    if payload:
        stats["section_curve_rational_count"] = rational_count
        stats["section_curve_periodic_count"] = periodic_count


def _profile_path_source_stats(source: KernelOperand) -> dict[str, Any]:
    """Extract profile/sweep modifier audit stats from the source operand metadata."""
    metadata = _dict_metadata(source.metadata)
    semantic_metadata = _dict_metadata(metadata.get("semantic_metadata"))
    source_shape = _dict_metadata(semantic_metadata.get("source_shape_primitive"))
    v2_metadata = _dict_metadata(semantic_metadata.get("shape_ir_v2"))
    stats: dict[str, Any] = {
        "source_primitive_type": source.primitive_type or str(source_shape.get("primitive_type") or ""),
        "source_part": source.part or str(source_shape.get("part") or ""),
    }
    for key in (
        "cross_section",
        "profile_polygon",
        "profile_points",
        "sweep_path",
        "cross_sections",
        "section_centers",
    ):
        count = _sequence_count(source_shape.get(key))
        if count:
            stats[f"{key}_count"] = count
    if isinstance(source_shape.get("cross_sections"), (list, tuple)):
        section_sizes = [
            _sequence_count(section)
            for section in source_shape["cross_sections"]
            if isinstance(section, (list, tuple))
        ]
        if section_sizes:
            stats["section_profile_point_count_min"] = min(section_sizes)
            stats["section_profile_point_count_max"] = max(section_sizes)
    for numeric_key in (
        "radius",
        "height",
        "tube_radius",
        "turns",
        "segments_per_turn",
        "cross_section_segments",
        "thread_pitch",
        "actual_pitch",
        "thread_depth",
        "thread_start_clearance",
        "thread_end_clearance",
        "angle_degrees",
        "start_angle_degrees",
        "path_segments",
        "extrude_height",
        "extrude_start_scale",
        "extrude_end_scale",
        "extrude_twist_degrees",
        "extrude_segments",
        "revolve_degrees",
        "revolve_start_degrees",
    ):
        value = source_shape.get(numeric_key)
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            stats[numeric_key] = float(value)
    kernel_import = _dict_metadata(metadata.get("kernel_import"))
    _copy_kernel_import_stats(stats, kernel_import)
    for modifier_name in (
        "v2_sweep_modifier",
        "v2_polywire_modifier",
        "v2_helical_sweep_modifier",
        "v2_loft_modifier",
        "v2_spring_modifier",
        "v2_curved_tube_modifier",
        "v2_threaded_cylinder_modifier",
        "v2_curve_profile_modifier",
        "v2_curve_sweep_modifier",
        "v2_curve_loft_modifier",
    ):
        modifier = _dict_metadata(v2_metadata.get(modifier_name))
        if modifier:
            stats["source_modifier"] = modifier_name
            stats["source_modifier_method"] = str(modifier.get("method") or "")
            for count_key in (
                "cross_section_point_count",
                "sweep_path_point_count",
                "path_point_count",
                "section_count",
                "profile_point_count",
            ):
                if count_key in modifier:
                    with suppress(TypeError, ValueError):
                        stats[count_key] = int(modifier[count_key])
            _copy_profile_curve_metadata_stats(stats, prefix="profile", payload=modifier)
            for nested_key, prefix in (
                ("cross_section_curve", "cross_section"),
                ("sweep_curve", "sweep"),
                ("path_curve", "path"),
                ("section_path_curve", "section_path"),
            ):
                _copy_profile_curve_metadata_stats(
                    stats,
                    prefix=prefix,
                    payload=modifier.get(nested_key),
                )
            _copy_section_curve_metadata_stats(
                stats,
                payload=modifier.get("section_curve_metadata"),
            )
            break
    return stats


def build_profile_path_program_manifest(
    source: KernelOperand,
    *,
    semantic_operation: str = "sop.sweep",
    profile_kind: str = "profile_path",
    route: str = "profile_path_program",
    backend: str | None = None,
    operation_limit: int | None = None,
) -> dict[str, Any]:
    """Return a deterministic, handle-free manifest for sweep/loft/profile geometry."""
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
                "source": "kernel_program.profile_path",
                "profile_kind": profile_kind,
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
    operation_count = profile_path_operation_count(source)
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
        "program_kind": "profile_path",
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
        "profile_kind": profile_kind,
        "source_primitive_type": source.primitive_type or "",
        "diagnostics": diagnostics,
    }


def execute_profile_path_program(
    kernel: GeometryKernel,
    source: KernelOperand,
    *,
    semantic_operation: str = "sop.sweep",
    profile_kind: str = "profile_path",
    operation_limit: int | None = None,
    route: str = "profile_path_program",
    backend: str | None = None,
) -> KernelProgramResult:
    """Expose sweep/loft/profile geometry as a typed KernelProgram result."""
    if source.handle is None:
        raise ValueError(f"kernel profile_path source operand {source.operand_id!r} has no handle")
    operation_count = profile_path_operation_count(source)
    if operation_limit is not None and operation_count > operation_limit:
        raise ValueError(
            f"kernel profile_path operation_count={operation_count} exceeds limit={operation_limit}"
        )
    capabilities = _kernel_capabilities(kernel)
    required = {"to_trimesh"}
    _require_capabilities(kernel, capabilities, required)
    manifest = build_profile_path_program_manifest(
        source,
        semantic_operation=semantic_operation,
        profile_kind=profile_kind,
        route=route,
        backend=backend,
        operation_limit=operation_limit,
    )
    mesh = _non_empty_mesh(kernel, source.handle)
    source_stats = _profile_path_source_stats(source)
    method = "profile_path_kernel_build_result_v1"
    if source_stats.get("kernel_import_route") == "exact_mesh.from_trimesh":
        method = "profile_path_exact_mesh_import_result_v1"
    profile_path_metadata = {
        "schema": "lathe.geometry.kernel_profile_path.v1",
        "operation": semantic_operation,
        "profile_kind": profile_kind,
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
    mesh.metadata["lathe_kernel_profile_path"] = dict(profile_path_metadata)
    operation_records = _semantic_operation_records_from_manifest(manifest)
    operation_record = {
        "op": "profile_path",
        "source": source.operand_id,
        "semantic_operation": semantic_operation,
        "profile_kind": profile_kind,
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "method": method,
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_watertight": bool(mesh.is_watertight),
        "result_body_count": kernel.body_count(source.handle),
        "kernel_profile_path": dict(profile_path_metadata),
    }
    _record_result_probe(operation_record, kernel=kernel, result_handle=source.handle)
    (
        face_operation_ids,
        face_operation_summary,
        face_operation_attribution,
    ) = _attach_direct_face_operation_metadata(
        mesh,
        f"{source.operand_id}.{_operation_id_fragment(semantic_operation)}",
        source="kernel_program.profile_path.source_operand",
        method="profile_path_source_face_ranges",
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
        "kernel_program_profile_path_source_operand_id": source.operand_id,
        "profile_path_semantic_operation": semantic_operation,
        "profile_path_kind": profile_kind,
        "profile_path_method": method,
        "profile_path_result_face_count": len(mesh.faces),
        "profile_path_result_vertex_count": len(mesh.vertices),
        "profile_path_result_watertight": bool(mesh.is_watertight),
        "kernel_profile_path": profile_path_metadata,
        "kernel_program_semantic_handoff": semantic_handoff,
    }
    return KernelProgramResult(
        mesh=mesh,
        handle=source.handle,
        operation_count=operation_count,
        details=details,
    )


__all__ = [
    "build_profile_path_program_manifest",
    "execute_profile_path_program",
]
