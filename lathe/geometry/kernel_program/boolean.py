"""Boolean program — ordered boolean composition of kernel operands.

Per the §5.3 decomposition, this module hosts the boolean family:
union / subtract / intersect blend modes composed in operand order
(unions first, then intersects, then subtracts so cutters never
become root bodies). The executor calls the kernel's per-op booleans
(or its batch_union capability when the kernel advertises it),
records every operation with attempted-vs-actual kernel + backend
metadata, and emits the boolean_csg_fallback /
mesh_to_levelset_repair diagnostics per the Lane A priority 5
contract.

This module also hosts the _exact_profile_cut_* summary helpers
that compact exact-rebuild boolean records into a single trace
payload, the _boolean_fallback_diagnostics builder, and the
_MESH_TO_LEVELSET_METHODS registry consumed by it.
"""

from __future__ import annotations

import contextlib
from typing import Any

from ..kernel import GeometryKernel
from ._capabilities import (
    _SUPPORTED_BLEND_MODES,
    _kernel_capabilities,
    _require_capabilities,
    _required_boolean_capabilities,
    _validate_operands,
)
from ._common import (
    _non_empty_mesh,
    _operation_id_fragment,
    _operation_record,
    _record_operation_result,
    _record_result_probe,
)
from ._core import (
    KernelOperand,
    KernelProgramResult,
    boolean_kernel_call_count,
    boolean_operation_count,
)
from ._face_operation import _attach_whole_result_face_operation_metadata
from ._feature_detail import (
    _EDGE_TREATMENT_OPERATION_KINDS,
    _FEATURE_DETAIL_OPERATION_KINDS,
    _SURFACE_DAMAGE_OPERATION_KINDS,
    _kernel_edge_treatment_metadata,
    _kernel_feature_detail_metadata,
    _kernel_surface_damage_metadata,
)
from ._records import _operand_operation_records
from ._semantic import (
    _final_semantic_operation_record,
    _operation_counts,
    _semantic_operation_for_kind,
    _semantic_operation_records_from_manifest,
)
from ._semantic_handoff import _attach_kernel_program_semantic_handoff
from ._serialize import _dict_metadata, _json_safe

KERNEL_PROGRAM_VERSION = "lathe.geometry.kernel_program_v1"

_MESH_TO_LEVELSET_METHODS: frozenset[str] = frozenset(
    {"voxel_boolean_fallback_v1"}
)


def build_boolean_program_manifest(
    operands: list[KernelOperand],
    *,
    route: str = "ordered_boolean_program",
    backend: str | None = None,
    operation_limit: int | None = None,
    batch_union_available: bool = False,
) -> dict[str, Any]:
    """Return a deterministic, handle-free manifest for a boolean program."""
    operation_records = _operand_operation_records(operands)
    union_count = sum(1 for operand in operands if operand.blend_mode == "union")
    subtract_count = sum(1 for operand in operands if operand.blend_mode == "subtract")
    intersect_count = sum(1 for operand in operands if operand.blend_mode == "intersect")
    for operation, count in (
        ("sop.boolean.union", max(0, union_count - 1)),
        ("sop.boolean.difference", subtract_count),
        ("sop.boolean.intersection", intersect_count),
    ):
        if count <= 0:
            continue
        operation_records.append(
            {
                "operation_id": f"program:{_operation_id_fragment(route)}:{_operation_id_fragment(operation)}",
                "operation": operation,
                "repair_action": "",
                "operand_id": "",
                "operand_index": -1,
                "part": "",
                "primitive_type": "",
                "blend_mode": "",
                "source": "kernel_program.boolean",
                "semantic_equivalent_operation_count": count,
            }
        )
    unsupported_blend_modes = sorted(
        {
            str(operand.blend_mode)
            for operand in operands
            if operand.blend_mode not in _SUPPORTED_BLEND_MODES
        }
    )
    missing_handle_ids = [operand.operand_id for operand in operands if operand.handle is None]
    diagnostics: list[dict[str, Any]] = []
    if unsupported_blend_modes:
        diagnostics.append(
            {
                "code": "unsupported_kernel_program_blend_mode",
                "severity": "error",
                "blend_modes": unsupported_blend_modes,
            }
        )
    if missing_handle_ids:
        diagnostics.append(
            {
                "code": "missing_kernel_operand_handle",
                "severity": "error",
                "operand_ids": missing_handle_ids,
            }
        )

    kernel_call_count = boolean_kernel_call_count(
        operands,
        batch_union_available=batch_union_available,
    )
    if operation_limit is not None and kernel_call_count > operation_limit:
        diagnostics.append(
            {
                "code": "kernel_program_operation_limit_exceeded",
                "severity": "error",
                "kernel_call_count": kernel_call_count,
                "operation_limit": operation_limit,
            }
        )

    return {
        "schema": "lathe.geometry.kernel_program_manifest.v1",
        "version": KERNEL_PROGRAM_VERSION,
        "program_kind": "boolean",
        "route": route,
        "backend": backend,
        "operation_count": boolean_operation_count(operands),
        "kernel_call_count": kernel_call_count,
        "operation_limit": operation_limit,
        "required_capabilities": sorted(
            _required_boolean_capabilities(
                operands,
                batch_union_available=batch_union_available,
            )
        ),
        "operand_count": len(operands),
        "operands": [_json_safe(operand.trace_record()) for operand in operands],
        "semantic_operation_record_count": len(operation_records),
        "semantic_operation_counts": _operation_counts(operation_records),
        "semantic_operation_records": _json_safe(operation_records),
        "diagnostics": diagnostics,
    }


def _boolean_fallback_diagnostics(
    fallback_records: list[dict[str, Any]],
    *,
    code: str = "boolean_csg_fallback",
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for index, record in enumerate(fallback_records):
        fallback = _dict_metadata(record.get("kernel_fallback"))
        method = str(fallback.get("method") or "")
        reason = str(
            method
            or fallback.get("reason")
            or record.get("fallback_reason")
            or "passthrough_fallback_suspected"
        )
        diagnostic = {
            "code": code,
            "severity": "warning",
            "operation_index": index,
            "operation": str(record.get("op") or ""),
            "reason": reason,
            "attempted_kernel": str(record.get("attempted_kernel") or ""),
            "actual_kernel": str(record.get("actual_kernel") or ""),
            "attempted_backend": str(
                fallback.get("attempted_backend")
                or record.get("attempted_backend")
                or ""
            ),
            "actual_backend": str(
                fallback.get("actual_backend")
                or record.get("actual_backend")
                or ""
            ),
            "actual_operation": str(
                fallback.get("actual_operation")
                or record.get("actual_operation")
                or ""
            ),
            "passthrough_fallback_suspected": bool(
                record.get("passthrough_fallback_suspected")
            ),
        }
        if method:
            diagnostic["fallback_method"] = method
        diagnostics.append(diagnostic)
        if method in _MESH_TO_LEVELSET_METHODS:
            # Last-resort mesh-to-levelset (voxel) repair is lossy by
            # construction: it samples the input meshes onto a regular
            # grid, performs the boolean in voxel space, and extracts
            # the result via marching cubes. Surface fidelity, seams,
            # and topology cannot be guaranteed. Emit a separate
            # ``mesh_to_levelset_repair`` diagnostic with severity
            # ``degraded`` so certification can refuse hero-quality
            # claims for output produced this way.
            diagnostics.append({
                "code": "mesh_to_levelset_repair",
                "severity": "degraded",
                "operation_index": index,
                "operation": str(record.get("op") or ""),
                "reason": reason,
                "fallback_method": method,
                "attempted_backend": str(
                    fallback.get("attempted_backend")
                    or record.get("attempted_backend")
                    or ""
                ),
                "actual_backend": str(
                    fallback.get("actual_backend")
                    or record.get("actual_backend")
                    or ""
                ),
                "pitch_cm": float(fallback.get("pitch_cm") or 0.0),
                "result_voxel_count": int(fallback.get("result_voxel_count") or 0),
                "lossy": True,
                "certification_blocking": True,
            })
    return diagnostics


def _manifest_with_runtime_diagnostics(
    manifest: dict[str, Any],
    diagnostics: list[dict[str, Any]],
) -> dict[str, Any]:
    if not diagnostics:
        return manifest
    updated = dict(manifest)
    existing = updated.get("diagnostics")
    updated["diagnostics"] = [
        *([dict(item) for item in existing if isinstance(item, dict)] if isinstance(existing, list) else []),
        *diagnostics,
    ]
    return updated


def _exact_profile_cut_record(
    exact_boolean: Any,
    *,
    operation_index: int,
) -> dict[str, Any] | None:
    if not isinstance(exact_boolean, dict):
        return None
    method = str(exact_boolean.get("method") or "")
    profile_cut_count = exact_boolean.get("profile_cut_count")
    if "profile" not in method and profile_cut_count in (None, 0, "0"):
        return None
    record: dict[str, Any] = {
        "operation_index": int(operation_index),
        "method": method,
        "profile_cut_count": int(profile_cut_count or 0),
        "cutter_part": str(exact_boolean.get("cutter_part") or ""),
        "result_face_count": int(exact_boolean.get("result_face_count") or 0),
        "result_vertex_count": int(exact_boolean.get("result_vertex_count") or 0),
        "result_body_count": int(exact_boolean.get("result_body_count") or 0),
        "result_watertight": bool(exact_boolean.get("result_watertight", False)),
    }
    for key in (
        "profile_cut_kinds",
        "profile_styles",
    ):
        value = exact_boolean.get(key)
        if isinstance(value, list):
            record[key] = [str(item) for item in value]
    for key in (
        "bore_wall_face_count",
        "bevel_face_count",
        "bevel_segments",
        "shoulder_face_count",
        "chamfer_face_count",
        "ring_count",
        "radial_section_count",
        "cut_count",
        "extruded_cut_count",
        "revolved_cut_count",
    ):
        value = exact_boolean.get(key)
        if value not in (None, "", (), [], {}):
            with contextlib.suppress(TypeError, ValueError):
                record[key] = int(value)
    return record


def _exact_profile_cut_records(trace_operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for operation_index, operation in enumerate(trace_operations):
        direct = _exact_profile_cut_record(
            operation.get("kernel_exact_boolean"),
            operation_index=operation_index,
        )
        if direct is not None:
            records.append(direct)
        nested = operation.get("kernel_nested_exact_booleans")
        if isinstance(nested, list):
            for item in nested:
                nested_record = _exact_profile_cut_record(
                    item,
                    operation_index=operation_index,
                )
                if nested_record is not None:
                    records.append(nested_record)
    return records


def _exact_profile_cut_summary(trace_operations: list[dict[str, Any]]) -> dict[str, Any]:
    records = _exact_profile_cut_records(trace_operations)
    if not records:
        return {}
    final_record = dict(records[-1])
    final_chamfer_face_count = int(final_record.get("chamfer_face_count") or 0)
    final_bevel_face_count = int(final_record.get("bevel_face_count") or 0)
    return {
        "kernel_program_exact_profile_cut_operation_count": len(records),
        "kernel_program_exact_profile_cut_methods": sorted(
            {str(record.get("method") or "") for record in records if record.get("method")}
        ),
        "kernel_program_exact_profile_cut_final": final_record,
        "kernel_program_exact_profile_cut_final_cut_count": int(
            final_record.get("profile_cut_count") or 0
        ),
        "kernel_program_exact_profile_cut_final_chamfer_face_count": final_chamfer_face_count,
        "kernel_program_exact_profile_cut_final_bevel_face_count": final_bevel_face_count,
        "kernel_program_exact_profile_cut_final_rim_face_count": final_chamfer_face_count + final_bevel_face_count,
        "kernel_program_exact_profile_cut_final_bore_wall_face_count": int(
            final_record.get("bore_wall_face_count") or 0
        ),
    }


def execute_boolean_program(
    kernel: GeometryKernel,
    operands: list[KernelOperand],
    *,
    operation_limit: int | None = None,
    route: str = "ordered_boolean_program",
    backend: str | None = None,
) -> KernelProgramResult:
    """Execute an ordered boolean program against ``kernel``.

    The first union operand is the base when any unions are present; otherwise
    the first intersection operand becomes the base. Subtract operands are
    applied last so cutters do not accidentally become the root body.
    """
    _validate_operands(operands)
    operation_count = boolean_operation_count(operands)
    capabilities = _kernel_capabilities(kernel)
    batch_union = getattr(kernel, "batch_union", None)
    batch_union_available = (
        sum(1 for operand in operands if operand.blend_mode == "union") > 1
        and capabilities.get("batch_union") is True
        and callable(batch_union)
    )
    required_capabilities = _required_boolean_capabilities(
        operands,
        batch_union_available=batch_union_available,
    )
    _require_capabilities(kernel, capabilities, required_capabilities)
    kernel_call_count = boolean_kernel_call_count(
        operands,
        batch_union_available=batch_union_available,
    )
    manifest = build_boolean_program_manifest(
        operands,
        route=route,
        backend=backend,
        operation_limit=operation_limit,
        batch_union_available=batch_union_available,
    )
    if operation_limit is not None and kernel_call_count > operation_limit:
        raise ValueError(
            f"kernel program kernel_call_count={kernel_call_count} exceeds limit={operation_limit} "
            f"(semantic_operation_count={operation_count})"
        )

    union_operands = [operand for operand in operands if operand.blend_mode == "union"]
    subtract_operands = [operand for operand in operands if operand.blend_mode == "subtract"]
    intersect_operands = [operand for operand in operands if operand.blend_mode == "intersect"]
    trace_operations: list[dict[str, Any]] = []

    if union_operands:
        if batch_union_available:
            record = {
                "op": "batch_union",
                "inputs": [operand.operand_id for operand in union_operands],
                "attempted_kernel": kernel.name,
                "actual_kernel": kernel.name,
                "semantic_equivalent_operation_count": max(0, len(union_operands) - 1),
            }
            current = batch_union([operand.handle for operand in union_operands])
            _record_result_probe(record, kernel=kernel, result_handle=current)
            trace_operations.append(record)
            current_id = f"batch_union({','.join(record['inputs'])})"
        else:
            current = union_operands[0].handle
            current_id = union_operands[0].operand_id
            for operand in union_operands[1:]:
                record = _operation_record(op="union", left=current_id, right=operand.operand_id, kernel=kernel)
                previous = current
                current = kernel.union(previous, operand.handle)
                _record_operation_result(record, kernel=kernel, result_handle=current, left_handle=previous)
                trace_operations.append(record)
                current_id = f"union({current_id},{operand.operand_id})"
        remaining_intersections = intersect_operands
    elif intersect_operands:
        current = intersect_operands[0].handle
        current_id = intersect_operands[0].operand_id
        remaining_intersections = intersect_operands[1:]
    else:
        raise ValueError("kernel boolean program requires a union or intersect base operand")

    for operand in remaining_intersections:
        record = _operation_record(op="intersect", left=current_id, right=operand.operand_id, kernel=kernel)
        previous = current
        current = kernel.intersection(previous, operand.handle)
        _record_operation_result(record, kernel=kernel, result_handle=current, left_handle=previous)
        trace_operations.append(record)
        current_id = f"intersect({current_id},{operand.operand_id})"

    for operand in subtract_operands:
        record = _operation_record(op="subtract", left=current_id, right=operand.operand_id, kernel=kernel)
        previous = current
        current = kernel.difference(previous, operand.handle)
        _record_operation_result(record, kernel=kernel, result_handle=current, left_handle=previous)
        trace_operations.append(record)
        current_id = f"subtract({current_id},{operand.operand_id})"

    mesh = _non_empty_mesh(kernel, current)
    operation_records = _semantic_operation_records_from_manifest(manifest)
    fallback_records = [
        dict(record)
        for record in trace_operations
        if isinstance(record.get("kernel_fallback"), dict)
        or bool(record.get("passthrough_fallback_suspected"))
    ]
    runtime_diagnostics = _boolean_fallback_diagnostics(fallback_records)
    manifest = _manifest_with_runtime_diagnostics(manifest, runtime_diagnostics)
    exact_profile_cut_summary = _exact_profile_cut_summary(trace_operations)
    semantic_handoff = _attach_kernel_program_semantic_handoff(
        mesh,
        operands,
        trace_operations,
    )
    operation_names = [
        str(record.get("operation") or "")
        for record in operation_records
        if isinstance(record, dict) and record.get("operation")
    ]
    semantic_operation = (
        operation_names[0]
        if operation_names and len(set(operation_names)) == 1
        else ""
    )
    feature_semantic_operation = _semantic_operation_for_kind(
        operation_records,
        _FEATURE_DETAIL_OPERATION_KINDS,
        fallback=semantic_operation,
    )
    edge_treatment_semantic_operation = _semantic_operation_for_kind(
        operation_records,
        _EDGE_TREATMENT_OPERATION_KINDS,
        fallback=semantic_operation,
    )
    surface_damage_semantic_operation = _semantic_operation_for_kind(
        operation_records,
        _SURFACE_DAMAGE_OPERATION_KINDS,
        fallback=semantic_operation,
    )
    face_semantic_operation = (
        feature_semantic_operation
        or edge_treatment_semantic_operation
        or surface_damage_semantic_operation
        or semantic_operation
    )
    face_operation_record = _final_semantic_operation_record(
        operation_records,
        face_semantic_operation,
    )
    face_operation_ids: list[str] = []
    face_operation_summary: dict[str, Any] = {}
    face_operation_attribution: dict[str, Any] = {
        "schema": "lathe.geometry.kernel_program_face_operation_attribution.v1",
        "source": "kernel_program.boolean",
        "attributed": False,
        "method": "boolean_kernel_face_ranges_unavailable",
        "result_face_count": len(mesh.faces),
        "reason": "boolean_kernel_did_not_preserve_source_face_ranges",
    }
    if face_operation_record:
        face_operation_id = str(face_operation_record.get("operation_id") or "")
        if face_operation_id:
            (
                face_operation_ids,
                face_operation_summary,
                face_operation_attribution,
            ) = _attach_whole_result_face_operation_metadata(
                mesh,
                face_operation_id,
                source="kernel_program.boolean.whole_result_semantic_operation",
                method="whole_result_semantic_operation_range",
                reason="boolean_kernel_did_not_preserve_source_face_ranges",
            )
    else:
        mesh.metadata["lathe_kernel_program_face_operation_attribution"] = dict(
            face_operation_attribution
        )
    kernel_feature_detail = _kernel_feature_detail_metadata(
        kernel,
        mesh,
        current,
        operands,
        semantic_operation=feature_semantic_operation,
        method_suffix="boolean_kernel_program_v1",
        fallback=bool(fallback_records),
        face_operation_attributed=bool(face_operation_ids),
        extra={
            "operand_count": len(operands),
            "boolean_fallback_count": len(fallback_records),
            "kernel_call_count": kernel_call_count,
            "batch_union": bool(batch_union_available),
        },
    )
    if kernel_feature_detail:
        mesh.metadata["lathe_kernel_feature_detail"] = dict(kernel_feature_detail)
    kernel_edge_treatment = _kernel_edge_treatment_metadata(
        kernel,
        mesh,
        current,
        operands,
        semantic_operation=edge_treatment_semantic_operation,
        method_suffix="boolean_kernel_program_v1",
        fallback=bool(fallback_records),
        extra={
            "operand_count": len(operands),
            "boolean_fallback_count": len(fallback_records),
            "kernel_call_count": kernel_call_count,
            "batch_union": bool(batch_union_available),
        },
    )
    if kernel_edge_treatment:
        mesh.metadata["lathe_kernel_edge_treatment"] = dict(kernel_edge_treatment)
    kernel_surface_damage = _kernel_surface_damage_metadata(
        kernel,
        mesh,
        current,
        operands,
        semantic_operation=surface_damage_semantic_operation,
        method_suffix="boolean_kernel_program_v1",
        fallback=bool(fallback_records),
        extra={
            "operand_count": len(operands),
            "boolean_fallback_count": len(fallback_records),
            "kernel_call_count": kernel_call_count,
            "batch_union": bool(batch_union_available),
        },
    )
    if kernel_surface_damage:
        mesh.metadata["lathe_kernel_surface_damage"] = dict(kernel_surface_damage)
    details = {
        "kernel_program_version": KERNEL_PROGRAM_VERSION,
        "kernel_program_route": route,
        "kernel_program_operation_count": operation_count,
        "kernel_program_kernel_call_count": kernel_call_count,
        "kernel_program_operand_count": len(operands),
        "kernel_program_semantic_operation_record_count": len(operation_records),
        "kernel_program_semantic_operation_counts": _operation_counts(operation_records),
        "kernel_program_semantic_operation_records": operation_records,
        "kernel_program_kernel": kernel.name,
        "kernel_program_backend": backend,
        "kernel_program_manifest": manifest,
        "kernel_program_diagnostics": list(manifest.get("diagnostics") or []),
        "kernel_program_capabilities_checked": sorted(required_capabilities),
        "kernel_program_watertight": kernel.is_watertight(current),
        "kernel_program_body_count": kernel.body_count(current),
        "kernel_program_operands": [operand.trace_record() for operand in operands],
        "kernel_program_operations": trace_operations,
        "kernel_program_face_operation_attribution": face_operation_attribution,
        "face_operation_ids": face_operation_ids,
        "face_operation_summary": face_operation_summary,
        "kernel_program_boolean_fallback_count": len(fallback_records),
        "kernel_program_boolean_fallback_records": fallback_records,
        "kernel_feature_detail": kernel_feature_detail,
        "kernel_program_feature_detail": kernel_feature_detail,
        "kernel_edge_treatment": kernel_edge_treatment,
        "kernel_program_edge_treatment": kernel_edge_treatment,
        "kernel_surface_damage": kernel_surface_damage,
        "kernel_program_surface_damage": kernel_surface_damage,
        "kernel_program_semantic_handoff": semantic_handoff,
        **exact_profile_cut_summary,
    }
    return KernelProgramResult(
        mesh=mesh,
        handle=current,
        operation_count=operation_count,
        details=details,
    )


__all__ = [
    "_MESH_TO_LEVELSET_METHODS",
    "_boolean_fallback_diagnostics",
    "_exact_profile_cut_record",
    "_exact_profile_cut_records",
    "_exact_profile_cut_summary",
    "_manifest_with_runtime_diagnostics",
    "build_boolean_program_manifest",
    "execute_boolean_program",
]
