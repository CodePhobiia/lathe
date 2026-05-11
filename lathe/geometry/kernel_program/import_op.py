"""Import program — expose a single imported operand as a typed KernelProgram result.

Per the §5.3 decomposition, this module hosts the import family
(shape.import and edge-treatment imports). The executor wraps an
already-imported kernel operand with the standard kernel-program
trace surface, applying optional edge-treatment geometry on top
(when polybevel/etc. modifiers request a width-based bevel).
"""

from __future__ import annotations

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
from ._core import (
    KernelOperand,
    KernelProgramResult,
    _required_capability_list,
    import_operation_count,
)
from ._face_operation import _attach_direct_face_operation_metadata
from ._feature_detail import (
    _apply_import_edge_treatment_geometry,
    _import_edge_treatment_requires_reimport,
    _kernel_edge_control_source_payload,
    _kernel_edge_treatment_metadata,
    _kernel_feature_detail_metadata,
    _kernel_surface_damage_metadata,
)
from ._records import _operand_operation_records
from ._semantic import (
    _final_semantic_operation_record,
    _operation_counts,
    _semantic_operation_records_from_manifest,
)
from ._semantic_handoff import _attach_kernel_program_semantic_handoff
from ._serialize import _dict_metadata, _json_safe

KERNEL_PROGRAM_VERSION = "lathe.geometry.kernel_program_v1"


def _import_required_capabilities(
    source: KernelOperand,
    semantic_operation: str = "",
) -> list[str]:
    required = ["to_trimesh"]
    metadata = _dict_metadata(source.metadata)
    kernel_import = _dict_metadata(metadata.get("kernel_import"))
    route = str(kernel_import.get("route") or "")
    if route == "exact_mesh.from_trimesh":
        required.append("from_trimesh")
    if route == "kernel.build_primitive" and source.primitive_type:
        required.append(source.primitive_type)
    if _import_edge_treatment_requires_reimport(source, semantic_operation):
        required.append("from_trimesh")
    return _required_capability_list(required)


def build_import_program_manifest(
    source: KernelOperand,
    *,
    semantic_operation: str = "shape.import",
    route: str = "import_program",
    backend: str | None = None,
    operation_limit: int | None = None,
) -> dict[str, Any]:
    """Return a deterministic, handle-free manifest for one imported source."""
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
                "source": "kernel_program.import",
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
    operation_count = import_operation_count(source)
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
        "program_kind": "import",
        "route": route,
        "backend": backend,
        "operation_count": operation_count,
        "kernel_call_count": operation_count,
        "operation_limit": operation_limit,
        "required_capabilities": _import_required_capabilities(
            source,
            semantic_operation,
        ),
        "operand_count": 1,
        "operands": [_json_safe(source.trace_record())],
        "semantic_operation_record_count": len(operation_records),
        "semantic_operation_counts": _operation_counts(operation_records),
        "semantic_operation_records": _json_safe(operation_records),
        "semantic_operation": semantic_operation,
        "diagnostics": diagnostics,
    }


def execute_import_program(
    kernel: GeometryKernel,
    source: KernelOperand,
    *,
    semantic_operation: str = "shape.import",
    operation_limit: int | None = None,
    route: str = "import_program",
    backend: str | None = None,
) -> KernelProgramResult:
    """Expose a single imported operand as a traced KernelProgram result."""
    if source.handle is None:
        raise ValueError(f"kernel import source operand {source.operand_id!r} has no handle")
    operation_count = import_operation_count(source)
    if operation_limit is not None and operation_count > operation_limit:
        raise ValueError(
            f"kernel import operation_count={operation_count} exceeds limit={operation_limit}"
        )
    capabilities = _kernel_capabilities(kernel)
    required = set(_import_required_capabilities(source, semantic_operation))
    _require_capabilities(kernel, capabilities, required)
    manifest = build_import_program_manifest(
        source,
        semantic_operation=semantic_operation,
        route=route,
        backend=backend,
        operation_limit=operation_limit,
    )
    result_handle = source.handle
    mesh = _non_empty_mesh(kernel, result_handle)
    mesh, result_handle, edge_treatment_geometry = _apply_import_edge_treatment_geometry(
        kernel,
        mesh,
        result_handle,
        [source],
        semantic_operation=semantic_operation,
    )
    operation_records = _semantic_operation_records_from_manifest(manifest)
    final_operation_record = _final_semantic_operation_record(
        operation_records,
        semantic_operation,
    )
    operation_record = {
        "op": "import",
        "source": source.operand_id,
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "semantic_operation": semantic_operation,
        "primitive_type": source.primitive_type,
        "part": source.part,
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_watertight": bool(mesh.is_watertight),
        "result_body_count": kernel.body_count(result_handle),
    }
    if final_operation_record:
        operation_record["semantic_operation_record"] = dict(final_operation_record)
    if edge_treatment_geometry:
        operation_record["kernel_edge_treatment_geometry"] = dict(edge_treatment_geometry)
    kernel_import = _dict_metadata(_dict_metadata(source.metadata).get("kernel_import"))
    if kernel_import:
        kernel_import_stats: dict[str, Any] = {}
        _copy_kernel_import_stats(kernel_import_stats, kernel_import)
        operation_record["import_route"] = str(kernel_import.get("route") or "")
        operation_record["import_primitive_type"] = str(kernel_import.get("primitive_type") or "")
        operation_record["attempted_backend"] = str(kernel_import.get("route") or "")
        operation_record["actual_backend"] = str(kernel_import.get("backend") or "")
        operation_record["actual_operation"] = str(
            kernel_import.get("method")
            or kernel_import.get("route")
            or "kernel_import"
        )
        operation_record.update(kernel_import_stats)
    face_operation_id = source.operand_id
    if final_operation_record:
        face_operation_id = str(final_operation_record.get("operation_id") or face_operation_id)
    elif operation_records:
        face_operation_id = str(operation_records[0].get("operation_id") or face_operation_id)
    (
        face_operation_ids,
        face_operation_summary,
        face_operation_attribution,
    ) = _attach_direct_face_operation_metadata(
        mesh,
        face_operation_id,
        source="kernel_program.import.source_operand",
        method="imported_source_face_ranges",
    )
    edge_control_kind, edge_control_payload = _kernel_edge_control_source_payload(source)
    kernel_edge_control: dict[str, Any] = {}
    if semantic_operation in {"op.weighted_normals", "op.mark_hard_edge"} or edge_control_kind:
        edge_control_kind = edge_control_kind or (
            "weighted_normals"
            if semantic_operation == "op.weighted_normals"
            else "mark_hard_edge"
        )
        kernel_edge_control = {
            "schema": "lathe.geometry.kernel_edge_control.v1",
            "operation": semantic_operation,
            "edge_control_kind": edge_control_kind,
            "method": f"{edge_control_kind}_source_preserving_kernel_program_v1",
            "attempted_backend": kernel.name,
            "actual_backend": kernel.name,
            "attempted_kernel": kernel.name,
            "actual_kernel": kernel.name,
            "actual_operation": semantic_operation,
            "fallback": False,
            "passthrough": False,
            "source_operand_id": source.operand_id,
            "source_part": source.part or "",
            "source_primitive_type": source.primitive_type or "",
            "edge_control_payload": _json_safe(edge_control_payload),
            "result_face_count": len(mesh.faces),
            "result_vertex_count": len(mesh.vertices),
            "result_body_count": kernel.body_count(result_handle),
            "result_watertight": bool(mesh.is_watertight),
            "face_operation_attributed": bool(face_operation_ids),
        }
        mesh.metadata["lathe_kernel_edge_control"] = dict(kernel_edge_control)
    kernel_edge_treatment = _kernel_edge_treatment_metadata(
        kernel,
        mesh,
        result_handle,
        [source],
        semantic_operation=semantic_operation,
        method_suffix="source_preserving_kernel_program_v1",
        fallback=bool(edge_treatment_geometry.get("edge_treatment_geometry_fallback")),
        extra={
            "face_operation_attributed": bool(face_operation_ids),
            **edge_treatment_geometry,
        },
    )
    if kernel_edge_treatment:
        mesh.metadata["lathe_kernel_edge_treatment"] = dict(kernel_edge_treatment)
        operation_record["kernel_edge_treatment"] = dict(kernel_edge_treatment)
    kernel_feature_detail = _kernel_feature_detail_metadata(
        kernel,
        mesh,
        result_handle,
        [source],
        semantic_operation=semantic_operation,
        method_suffix="source_preserving_kernel_program_v1",
        face_operation_attributed=bool(face_operation_ids),
    )
    if kernel_feature_detail:
        mesh.metadata["lathe_kernel_feature_detail"] = dict(kernel_feature_detail)
    kernel_surface_damage = _kernel_surface_damage_metadata(
        kernel,
        mesh,
        result_handle,
        [source],
        semantic_operation=semantic_operation,
        method_suffix="source_preserving_kernel_program_v1",
        extra={"face_operation_attributed": bool(face_operation_ids)},
    )
    if kernel_surface_damage:
        mesh.metadata["lathe_kernel_surface_damage"] = dict(kernel_surface_damage)
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
        "kernel_program_watertight": kernel.is_watertight(result_handle),
        "kernel_program_body_count": kernel.body_count(result_handle),
        "kernel_program_operands": [source.trace_record()],
        "kernel_program_operations": [operation_record],
        "kernel_program_face_operation_attribution": face_operation_attribution,
        "face_operation_ids": face_operation_ids,
        "face_operation_summary": face_operation_summary,
        "kernel_program_import_source_operand_id": source.operand_id,
        "import_semantic_operation": semantic_operation,
        "kernel_edge_control": kernel_edge_control,
        "kernel_program_edge_control": kernel_edge_control,
        "kernel_edge_treatment": kernel_edge_treatment,
        "kernel_program_edge_treatment": kernel_edge_treatment,
        "kernel_edge_treatment_geometry": edge_treatment_geometry,
        "kernel_program_edge_treatment_geometry": edge_treatment_geometry,
        "kernel_feature_detail": kernel_feature_detail,
        "kernel_program_feature_detail": kernel_feature_detail,
        "kernel_surface_damage": kernel_surface_damage,
        "kernel_program_surface_damage": kernel_surface_damage,
        "kernel_program_semantic_handoff": semantic_handoff,
    }
    return KernelProgramResult(
        mesh=mesh,
        handle=result_handle,
        operation_count=operation_count,
        details=details,
    )


__all__ = [
    "build_import_program_manifest",
    "execute_import_program",
]
