"""Transform program — apply a 4x4 matrix to a single kernel operand.

Per the §5.3 decomposition, every per-op program ships as one module
under ``lathe.geometry.kernel_program``. This module is the
``transform`` family: ``sop.transform`` semantic op routes through
the kernel's ``transform(handle, matrix)`` capability, with a single
result mesh and one operation record.

The pair (manifest builder, executor) is small because transform is
the simplest single-source op: no fallback paths, no exact rebuilds,
no boolean composition.
"""

from __future__ import annotations

from typing import Any

from ..kernel import GeometryKernel
from ._capabilities import (
    _kernel_capabilities,
    _require_capabilities,
    _validate_transform_operand,
    _validated_transform_matrix,
)
from ._common import _non_empty_mesh, _operation_id_fragment, _record_result_probe
from ._core import KernelOperand, KernelProgramResult, transform_operation_count
from ._face_operation import _attach_direct_face_operation_metadata
from ._records import _operand_operation_records
from ._semantic import (
    _final_semantic_operation_face_id,
    _operation_counts,
    _semantic_operation_records_from_manifest,
)
from ._semantic_handoff import _attach_kernel_program_semantic_handoff
from ._serialize import _dict_metadata, _json_safe

KERNEL_PROGRAM_VERSION = "lathe.geometry.kernel_program_v1"


def build_transform_program_manifest(
    source: KernelOperand,
    *,
    matrix: list[list[float]],
    route: str = "transform_program",
    backend: str | None = None,
    operation_limit: int | None = None,
) -> dict[str, Any]:
    """Return a deterministic, handle-free manifest for a transform program."""
    operation_records = _operand_operation_records([source])
    if not any(str(record.get("operation") or "") == "sop.transform" for record in operation_records):
        operation_records.append(
            {
                "operation_id": f"program:{_operation_id_fragment(route)}:sop_transform",
                "operation": "sop.transform",
                "repair_action": "",
                "operand_id": source.operand_id,
                "operand_index": 0,
                "part": source.part or "",
                "primitive_type": source.primitive_type or "",
                "blend_mode": source.blend_mode,
                "source": "kernel_program.transform",
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
    operation_count = transform_operation_count(source)
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
        "program_kind": "transform",
        "route": route,
        "backend": backend,
        "operation_count": operation_count,
        "kernel_call_count": operation_count,
        "operation_limit": operation_limit,
        "required_capabilities": ["transform", "to_trimesh"],
        "operand_count": 1,
        "operands": [_json_safe(source.trace_record())],
        "semantic_operation_record_count": len(operation_records),
        "semantic_operation_counts": _operation_counts(operation_records),
        "semantic_operation_records": _json_safe(operation_records),
        "matrix": _json_safe(matrix),
        "diagnostics": diagnostics,
    }


def execute_transform_program(
    kernel: GeometryKernel,
    source: KernelOperand,
    *,
    matrix: list[list[float]],
    operation_limit: int | None = None,
    route: str = "transform_program",
    backend: str | None = None,
) -> KernelProgramResult:
    """Execute a transform against one already-imported kernel operand."""
    transform_matrix = _validated_transform_matrix(matrix)
    _validate_transform_operand(source)
    operation_count = transform_operation_count(source)
    if operation_limit is not None and operation_count > operation_limit:
        raise ValueError(
            f"kernel transform operation_count={operation_count} exceeds limit={operation_limit}"
        )
    capabilities = _kernel_capabilities(kernel)
    _require_capabilities(kernel, capabilities, {"transform", "to_trimesh"})
    manifest = build_transform_program_manifest(
        source,
        matrix=transform_matrix,
        route=route,
        backend=backend,
        operation_limit=operation_limit,
    )

    transform = getattr(kernel, "transform", None)
    if not callable(transform):
        raise ValueError(f"geometry kernel {kernel.name!r} does not implement transform")
    current = transform(source.handle, transform_matrix)
    mesh = _non_empty_mesh(kernel, current)
    operation_records = _semantic_operation_records_from_manifest(manifest)
    operation_record = {
        "op": "transform",
        "source": source.operand_id,
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "matrix": transform_matrix,
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_watertight": bool(mesh.is_watertight),
        "result_body_count": kernel.body_count(current),
    }
    _record_result_probe(operation_record, kernel=kernel, result_handle=current)
    face_operation_id, final_operation_record = _final_semantic_operation_face_id(
        operation_records,
        "sop.transform",
        fallback=f"{source.operand_id}.transform",
    )
    if final_operation_record:
        operation_record["semantic_operation_record"] = dict(final_operation_record)
    (
        face_operation_ids,
        face_operation_summary,
        face_operation_attribution,
    ) = _attach_direct_face_operation_metadata(
        mesh,
        face_operation_id,
        source="kernel_program.transform.source_operand",
        method="transformed_source_face_ranges",
    )
    kernel_transform = _dict_metadata(operation_record.get("kernel_transform"))
    if not kernel_transform:
        kernel_transform = _dict_metadata(mesh.metadata.get("lathe_reference_transform"))
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
        "kernel_program_capabilities_checked": ["transform", "to_trimesh"],
        "kernel_program_watertight": kernel.is_watertight(current),
        "kernel_program_body_count": kernel.body_count(current),
        "kernel_program_operands": [source.trace_record()],
        "kernel_program_operations": [operation_record],
        "kernel_program_face_operation_attribution": face_operation_attribution,
        "face_operation_ids": face_operation_ids,
        "face_operation_summary": face_operation_summary,
        "kernel_transform": kernel_transform,
        "kernel_program_transform": kernel_transform,
        "kernel_program_transform_source_operand_id": source.operand_id,
        "transform_matrix": transform_matrix,
        "kernel_program_semantic_handoff": semantic_handoff,
    }
    return KernelProgramResult(
        mesh=mesh,
        handle=current,
        operation_count=operation_count,
        details=details,
    )


__all__ = [
    "build_transform_program_manifest",
    "execute_transform_program",
]
