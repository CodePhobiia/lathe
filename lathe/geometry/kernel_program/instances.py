"""Instances program — place source operands at a list of 4x4 transforms.

Per the §5.3 decomposition, this module hosts the instances family
covering op.repeat, op.distribute, op.mirror,
sop.copy_to_points, and sop.scatter_on_surface. The executor
applies each transform to the source operand and composes the
results — additive blend modes produce a mesh concatenation;
destructive modes route through the boolean executor with visible-
preservation fallbacks if the boolean fails.
"""

from __future__ import annotations

from typing import Any

import trimesh

from ..kernel import GeometryKernel
from ._capabilities import (
    _kernel_capabilities,
    _require_capabilities,
    _validate_transform_operand,
    _validated_transform_matrix,
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
    instances_operation_count,
)
from ._face_operation import (
    _attach_whole_result_face_operation_metadata,
    _instance_face_operation_ids,
    _kernel_program_face_operation_summary,
)
from ._feature_detail import (
    _PATTERN_INSTANCE_MODIFIER_KINDS,
    _PATTERN_INSTANCE_OPERATION_KINDS,
    _kernel_feature_detail_metadata,
    _kernel_modifier_payload,
)
from ._records import _operand_operation_records
from ._semantic import (
    _final_semantic_operation_record,
    _operation_counts,
    _semantic_operation_records_from_manifest,
)
from ._semantic_handoff import _attach_kernel_program_semantic_handoff
from ._serialize import _dict_metadata, _json_safe
from .boolean import (
    _boolean_fallback_diagnostics,
    _manifest_with_runtime_diagnostics,
)

KERNEL_PROGRAM_VERSION = "lathe.geometry.kernel_program_v1"


def _validated_transform_matrices(matrices: list[list[list[float]]]) -> list[list[list[float]]]:
    """Validate a list of 4x4 transform matrices for the instances program."""
    if not isinstance(matrices, list) or not matrices:
        raise ValueError("kernel instances requires at least one transform matrix")
    return [_validated_transform_matrix(matrix) for matrix in matrices]


def _mesh_bounds_overlap(a: trimesh.Trimesh, b: trimesh.Trimesh, *, epsilon: float = 1e-7) -> bool:
    """Return True iff the AABBs of ``a`` and ``b`` overlap within ``epsilon``."""
    try:
        a_min, a_max = a.bounds
        b_min, b_max = b.bounds
    except (AttributeError, TypeError, ValueError, IndexError):
        return True
    for axis in range(3):
        if float(a_max[axis]) < float(b_min[axis]) - epsilon:
            return False
        if float(b_max[axis]) < float(a_min[axis]) - epsilon:
            return False
    return True


def _disjoint_mesh_group_count(meshes: list[trimesh.Trimesh]) -> int:
    """Count connected components by AABB overlap (union-find over mesh list)."""
    non_empty = [mesh for mesh in meshes if isinstance(mesh, trimesh.Trimesh) and len(mesh.faces) > 0]
    if not non_empty:
        return 0
    parent = list(range(len(non_empty)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for left in range(len(non_empty)):
        for right in range(left + 1, len(non_empty)):
            if _mesh_bounds_overlap(non_empty[left], non_empty[right]):
                union(left, right)
    return len({find(index) for index in range(len(non_empty))})


def build_instances_program_manifest(
    source: KernelOperand,
    *,
    matrices: list[list[list[float]]],
    semantic_operation: str = "sop.copy_to_points",
    route: str = "instances_program",
    backend: str | None = None,
    operation_limit: int | None = None,
    batch_union_available: bool = False,
) -> dict[str, Any]:
    """Return a deterministic, handle-free manifest for an instancing program."""
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
                "source": "kernel_program.instances",
                "instance_count": len(matrices),
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
    if not matrices:
        diagnostics.append(
            {
                "code": "kernel_instances_empty_matrix_list",
                "severity": "error",
            }
        )
    operation_count = instances_operation_count(source, matrices)
    if operation_limit is not None and operation_count > operation_limit:
        diagnostics.append(
            {
                "code": "kernel_program_operation_limit_exceeded",
                "severity": "error",
                "operation_count": operation_count,
                "operation_limit": operation_limit,
            }
        )
    required_capabilities = ["transform", "to_trimesh", "from_trimesh"]
    if len(matrices) > 1:
        required_capabilities.append("batch_union" if batch_union_available else "union")
    return {
        "schema": "lathe.geometry.kernel_program_manifest.v1",
        "version": KERNEL_PROGRAM_VERSION,
        "program_kind": "instances",
        "route": route,
        "backend": backend,
        "operation_count": operation_count,
        "kernel_call_count": operation_count,
        "operation_limit": operation_limit,
        "required_capabilities": required_capabilities,
        "operand_count": 1,
        "operands": [_json_safe(source.trace_record())],
        "semantic_operation_record_count": len(operation_records),
        "semantic_operation_counts": _operation_counts(operation_records),
        "semantic_operation_records": _json_safe(operation_records),
        "semantic_operation": semantic_operation,
        "instance_count": len(matrices),
        "matrices": _json_safe(matrices),
        "diagnostics": diagnostics,
    }


def _kernel_scatter_source_payload(source: KernelOperand) -> tuple[str, dict[str, Any]]:
    metadata = _dict_metadata(source.metadata)
    semantic_metadata = _dict_metadata(metadata.get("semantic_metadata"))
    point_scatter = _dict_metadata(semantic_metadata.get("point_scatter"))
    if point_scatter:
        return "point_scatter", point_scatter
    surface_scatter = _dict_metadata(semantic_metadata.get("surface_scatter"))
    if surface_scatter:
        return "surface_scatter", surface_scatter
    copy_to_points = _kernel_modifier_payload(metadata, "v2_copy_to_points_modifier")
    if copy_to_points:
        return "point_scatter", copy_to_points
    surface_modifier = _kernel_modifier_payload(metadata, "v2_surface_scatter_modifier")
    if surface_modifier:
        return "surface_scatter", surface_modifier
    return "", {}


def _kernel_pattern_instance_source_payload(source: KernelOperand) -> tuple[str, dict[str, Any]]:
    metadata = _dict_metadata(source.metadata)
    for modifier_name, pattern_kind in _PATTERN_INSTANCE_MODIFIER_KINDS.items():
        payload = _kernel_modifier_payload(metadata, modifier_name)
        if payload:
            return pattern_kind, payload
    return "", {}


def execute_instances_program(
    kernel: GeometryKernel,
    source: KernelOperand,
    *,
    matrices: list[list[list[float]]],
    semantic_operation: str = "sop.copy_to_points",
    instance_pattern: str | None = None,
    instance_pattern_payload: dict[str, Any] | None = None,
    operation_limit: int | None = None,
    route: str = "instances_program",
    backend: str | None = None,
) -> KernelProgramResult:
    """Execute repeated transformed instances of one source operand."""
    transform_matrices = _validated_transform_matrices(matrices)
    _validate_transform_operand(source)
    operation_count = instances_operation_count(source, transform_matrices)
    if operation_limit is not None and operation_count > operation_limit:
        raise ValueError(
            f"kernel instances operation_count={operation_count} exceeds limit={operation_limit}"
        )
    capabilities = _kernel_capabilities(kernel)
    batch_union = getattr(kernel, "batch_union", None)
    batch_union_available = (
        len(transform_matrices) > 1
        and capabilities.get("batch_union") is True
        and callable(batch_union)
    )
    required = {"transform", "to_trimesh", "from_trimesh"}
    if len(transform_matrices) > 1:
        required.add("batch_union" if batch_union_available else "union")
    _require_capabilities(kernel, capabilities, required)
    transform = getattr(kernel, "transform", None)
    if not callable(transform):
        raise ValueError(f"geometry kernel {kernel.name!r} does not implement transform")
    manifest = build_instances_program_manifest(
        source,
        matrices=transform_matrices,
        semantic_operation=semantic_operation,
        route=route,
        backend=backend,
        operation_limit=operation_limit,
        batch_union_available=batch_union_available,
    )

    trace_operations: list[dict[str, Any]] = []
    transformed_handles: list[Any] = []
    transformed_ids: list[str] = []
    for index, matrix in enumerate(transform_matrices):
        handle = transform(source.handle, matrix)
        record = {
            "op": "transform",
            "source": source.operand_id,
            "instance_id": f"{source.operand_id}.instance_{index:04d}",
            "instance_index": index,
            "attempted_kernel": kernel.name,
            "actual_kernel": kernel.name,
            "matrix": matrix,
        }
        _record_result_probe(record, kernel=kernel, result_handle=handle)
        trace_operations.append(record)
        transformed_handles.append(handle)
        transformed_ids.append(str(record["instance_id"]))

    if not transformed_handles:
        raise ValueError("kernel instances program produced no instance handles")
    if len(transformed_handles) == 1:
        current = transformed_handles[0]
        current_id = transformed_ids[0]
    elif batch_union_available:
        record = {
            "op": "batch_union",
            "inputs": list(transformed_ids),
            "actual_kernel": kernel.name,
            "semantic_equivalent_operation_count": len(transformed_handles) - 1,
        }
        current = batch_union(transformed_handles)
        _record_result_probe(record, kernel=kernel, result_handle=current)
        trace_operations.append(record)
        current_id = f"batch_union({','.join(transformed_ids)})"
    else:
        current = transformed_handles[0]
        current_id = transformed_ids[0]
        for index, handle in enumerate(transformed_handles[1:], start=1):
            record = _operation_record(
                op="union",
                left=current_id,
                right=transformed_ids[index],
                kernel=kernel,
            )
            previous = current
            current = kernel.union(previous, handle)
            _record_operation_result(record, kernel=kernel, result_handle=current, left_handle=previous)
            trace_operations.append(record)
            current_id = f"union({current_id},{transformed_ids[index]})"

    mesh = _non_empty_mesh(kernel, current)
    attempted_result_face_count = len(mesh.faces)
    transformed_meshes = [_non_empty_mesh(kernel, handle) for handle in transformed_handles]
    instance_operands: list[KernelOperand] = []
    source_metadata = _dict_metadata(source.metadata)
    for index, (handle, instance_mesh) in enumerate(zip(transformed_handles, transformed_meshes, strict=False)):
        try:
            instance_body_count = kernel.body_count(handle)
        except (AttributeError, TypeError, ValueError, RuntimeError):
            instance_body_count = len(instance_mesh.split(only_watertight=False))
        instance_metadata = dict(source_metadata)
        instance_metadata.update(
            {
                "source_operand_id": source.operand_id,
                "instance_index": index,
                "instance_id": transformed_ids[index],
                "instance_matrix": transform_matrices[index],
            }
        )
        instance_operands.append(
            KernelOperand(
                operand_id=transformed_ids[index],
                handle=handle,
                source_mesh=instance_mesh,
                blend_mode=source.blend_mode,
                part=source.part,
                primitive_type=source.primitive_type,
                source_index=source.source_index,
                tags=source.tags,
                source_mesh_face_count=len(instance_mesh.faces),
                source_mesh_watertight=bool(instance_mesh.is_watertight),
                source_mesh_body_count=int(instance_body_count),
                source_mesh_repaired=source.source_mesh_repaired,
                metadata=instance_metadata,
            )
        )
    expected_disjoint_groups = _disjoint_mesh_group_count(transformed_meshes)
    attempted_result_body_count = kernel.body_count(current)
    attempted_batch_union = _dict_metadata(mesh.metadata.get("lathe_reference_batch_union"))
    attempted_batch_union_method = str(attempted_batch_union.get("method") or "")
    disjoint_instances_preserve_face_ranges = (
        len(transformed_meshes) > 1
        and expected_disjoint_groups == len(transformed_meshes)
        and "mesh_concatenation" not in attempted_batch_union_method
    )
    visible_preservation_fallback: dict[str, Any] | None = None
    if (
        len(transformed_meshes) > 1
        and expected_disjoint_groups > 1
        and (
            attempted_result_body_count < expected_disjoint_groups
            or disjoint_instances_preserve_face_ranges
        )
    ):
        if attempted_result_body_count < expected_disjoint_groups:
            preservation_reason = "kernel_instance_union_collapsed_disjoint_instances"
        else:
            preservation_reason = "kernel_instance_union_lacked_direct_disjoint_face_ranges"
        preserved_mesh = trimesh.util.concatenate([mesh.copy() for mesh in transformed_meshes])
        preserved_mesh.remove_unreferenced_vertices()
        preserved_mesh.fix_normals()
        current = kernel.from_trimesh(preserved_mesh)
        mesh = preserved_mesh
        current_id = f"visible_mesh_concatenation({','.join(transformed_ids)})"
        visible_preservation_fallback = {
            "schema": "lathe.geometry.instances_visible_preservation_fallback.v1",
            "reason": preservation_reason,
            "attempted_body_count": int(attempted_result_body_count),
            "expected_disjoint_group_count": int(expected_disjoint_groups),
            "instance_count": len(transformed_meshes),
            "attempted_face_count": attempted_result_face_count,
            "preserved_face_count": len(mesh.faces),
            "preserved_body_count": kernel.body_count(current),
            "actual_method": "visible_mesh_concatenation_import",
            "attempted_batch_union_method": attempted_batch_union_method,
        }
        trace_operations.append(
            {
                "op": "visible_mesh_concatenation_import",
                "inputs": list(transformed_ids),
                "actual_kernel": kernel.name,
                "reason": visible_preservation_fallback["reason"],
                "expected_disjoint_group_count": expected_disjoint_groups,
                "result_face_count": len(mesh.faces),
                "result_watertight": bool(mesh.is_watertight),
                "result_body_count": kernel.body_count(current),
                "kernel_fallback": dict(visible_preservation_fallback),
                "passthrough_fallback_suspected": False,
            }
        )
    operation_records = _semantic_operation_records_from_manifest(manifest)
    final_operation_record = _final_semantic_operation_record(
        operation_records,
        semantic_operation,
    )
    fallback_records = [
        dict(record)
        for record in trace_operations
        if isinstance(record.get("kernel_fallback"), dict)
        or bool(record.get("passthrough_fallback_suspected"))
    ]
    batch_union_record = next(
        (
            record
            for record in reversed(trace_operations)
            if record.get("op") == "batch_union"
        ),
        {},
    )
    batch_union_metadata = _dict_metadata(batch_union_record.get("kernel_batch_union"))
    if visible_preservation_fallback is not None:
        assembly_method = "visible_mesh_concatenation_import"
    elif batch_union_metadata:
        assembly_method = str(batch_union_metadata.get("method") or "batch_union")
    elif len(transformed_handles) == 1:
        assembly_method = "single_transform"
    elif batch_union_available:
        assembly_method = "batch_union"
    else:
        assembly_method = "pairwise_union"
    result_body_count = kernel.body_count(current)
    face_operation_ids = _instance_face_operation_ids(
        instance_operands,
        transformed_meshes,
        mesh,
        assembly_method=assembly_method,
    )
    face_operation_summary: dict[str, Any] = {}
    face_operation_attribution = {
        "schema": "lathe.geometry.kernel_program_face_operation_attribution.v1",
        "source": "kernel_program.instances",
        "attributed": bool(face_operation_ids),
        "assembly_method": assembly_method,
        "instance_count": len(instance_operands),
        "result_face_count": len(mesh.faces),
    }
    if face_operation_ids:
        face_operation_summary = _kernel_program_face_operation_summary(
            face_operation_ids,
            source="kernel_program.instances.instance_operands",
        )
        face_operation_attribution.update(
            {
                "method": "concatenated_instance_face_ranges",
                "face_operation_count": len(set(face_operation_ids)),
                "face_operation_attribution_count": len(face_operation_ids),
            }
        )
        mesh.metadata["face_operation_ids"] = list(face_operation_ids)
        mesh.metadata["face_operation_summary"] = dict(face_operation_summary)
    else:
        face_operation_attribution["reason"] = (
            "kernel_result_faces_not_a_direct_instance_concatenation"
        )
    mesh.metadata["lathe_kernel_program_face_operation_attribution"] = dict(
        face_operation_attribution
    )
    source_face_operation_summary = dict(face_operation_summary)
    source_face_operation_attribution = dict(face_operation_attribution)
    if source_face_operation_summary:
        mesh.metadata["source_face_operation_summary"] = dict(source_face_operation_summary)
        mesh.metadata["lathe_kernel_program_source_face_operation_attribution"] = dict(
            source_face_operation_attribution
        )
    if final_operation_record:
        final_operation_id = str(final_operation_record.get("operation_id") or "")
        if final_operation_id:
            (
                face_operation_ids,
                face_operation_summary,
                face_operation_attribution,
            ) = _attach_whole_result_face_operation_metadata(
                mesh,
                final_operation_id,
                source="kernel_program.instances.whole_result_semantic_operation",
                method="whole_result_instances_semantic_operation_range",
                reason="instances_preserve_source_face_ranges_separately",
                source_face_ranges_preserved=bool(source_face_operation_summary),
                extra={
                    "source_face_operation_summary": source_face_operation_summary,
                    "source_face_operation_attribution": source_face_operation_attribution,
                },
            )
    scatter_kind, scatter_payload = _kernel_scatter_source_payload(source)
    kernel_scatter: dict[str, Any] = {}
    if semantic_operation in {"sop.copy_to_points", "sop.scatter_on_surface"} or scatter_kind:
        scatter_kind = scatter_kind or (
            "surface_scatter"
            if semantic_operation == "sop.scatter_on_surface"
            else "point_scatter"
        )
        kernel_scatter = {
            "schema": "lathe.geometry.kernel_scatter.v1",
            "operation": semantic_operation,
            "scatter_kind": scatter_kind,
            "method": f"{scatter_kind}_instances_kernel_program_v1",
            "attempted_backend": kernel.name,
            "actual_backend": kernel.name,
            "attempted_kernel": kernel.name,
            "actual_kernel": kernel.name,
            "actual_operation": semantic_operation,
            "fallback": visible_preservation_fallback is not None,
            "passthrough": False,
            "instance_count": len(transform_matrices),
            "source_operand_id": source.operand_id,
            "source_part": source.part or "",
            "source_primitive_type": source.primitive_type or "",
            "source_scatter_payload": _json_safe(scatter_payload),
            "batch_union": bool(batch_union_available),
            "actual_assembly_method": assembly_method,
            "expected_disjoint_group_count": int(expected_disjoint_groups),
            "attempted_body_count": int(attempted_result_body_count),
            "result_face_count": len(mesh.faces),
            "result_vertex_count": len(mesh.vertices),
            "result_body_count": int(result_body_count),
            "result_watertight": bool(mesh.is_watertight),
            "face_operation_attributed": bool(face_operation_ids),
        }
        for key in (
            "point_count",
            "emitted_count",
            "density_per_m2",
            "surface_area_m2",
            "seed",
            "jitter_cm",
            "orientation_mode",
            "orientation_applied",
            "align_to_normal",
            "surface_anchor",
            "target",
            "target_part",
            "target_primitive_type",
            "source_context_record_count",
            "source_context_parts",
            "source_context_primitive_types",
            "source_parts",
            "source_primitive_types",
            "template_primitive_type",
            "template_primitive_count",
            "template_part",
        ):
            if key in scatter_payload:
                kernel_scatter[key] = _json_safe(scatter_payload[key])
        mesh.metadata["lathe_kernel_scatter"] = dict(kernel_scatter)
    pattern_kind, pattern_payload = _kernel_pattern_instance_source_payload(source)
    explicit_pattern_payload = (
        dict(instance_pattern_payload)
        if isinstance(instance_pattern_payload, dict)
        else {}
    )
    if explicit_pattern_payload:
        pattern_payload = explicit_pattern_payload
    pattern_kind = str(instance_pattern or pattern_kind or "").strip()
    if not pattern_kind:
        pattern_kind = _PATTERN_INSTANCE_OPERATION_KINDS.get(semantic_operation, "")
    kernel_pattern_instances: dict[str, Any] = {}
    if pattern_kind:
        kernel_pattern_instances = {
            "schema": "lathe.geometry.kernel_pattern_instances.v1",
            "operation": semantic_operation,
            "pattern_kind": pattern_kind,
            "method": f"{pattern_kind}_pattern_instances_kernel_program_v1",
            "attempted_backend": kernel.name,
            "actual_backend": kernel.name,
            "attempted_kernel": kernel.name,
            "actual_kernel": kernel.name,
            "actual_operation": semantic_operation,
            "fallback": visible_preservation_fallback is not None,
            "passthrough": False,
            "instance_count": len(transform_matrices),
            "source_operand_id": source.operand_id,
            "source_part": source.part or "",
            "source_primitive_type": source.primitive_type or "",
            "pattern_payload": _json_safe(pattern_payload),
            "batch_union": bool(batch_union_available),
            "actual_assembly_method": assembly_method,
            "expected_disjoint_group_count": int(expected_disjoint_groups),
            "attempted_body_count": int(attempted_result_body_count),
            "result_face_count": len(mesh.faces),
            "result_vertex_count": len(mesh.vertices),
            "result_body_count": int(result_body_count),
            "result_watertight": bool(mesh.is_watertight),
            "face_operation_attributed": bool(face_operation_ids),
        }
        for key in (
            "axis",
            "count",
            "spacing_cm",
            "pattern",
            "include_source",
            "origin_cm",
            "seed",
            "jitter_cm",
            "snap_to_grid_cm",
            "source_axis",
            "orientation_mode",
            "orientation_applied",
            "instance_transform_count",
            "instance_transform_record_count",
            "source_context_record_count",
            "source_context_parts",
            "source_context_primitive_types",
            "source_parts",
            "source_primitive_types",
            "template_part",
            "template_primitive_type",
            "template_primitive_count",
            "source_record_expansion_count",
            "source_record_expansion_route",
        ):
            if key in pattern_payload:
                kernel_pattern_instances[key] = _json_safe(pattern_payload[key])
        mesh.metadata["lathe_kernel_pattern_instances"] = dict(kernel_pattern_instances)
    kernel_feature_detail = _kernel_feature_detail_metadata(
        kernel,
        mesh,
        current,
        [source],
        semantic_operation=semantic_operation,
        method_suffix="instances_kernel_program_v1",
        fallback=visible_preservation_fallback is not None,
        face_operation_attributed=bool(face_operation_ids),
        extra={
            "instance_count": len(transform_matrices),
            "actual_assembly_method": assembly_method,
            "batch_union": bool(batch_union_available),
            "expected_disjoint_group_count": int(expected_disjoint_groups),
        },
    )
    if kernel_feature_detail:
        mesh.metadata["lathe_kernel_feature_detail"] = dict(kernel_feature_detail)
    runtime_diagnostics = _boolean_fallback_diagnostics(
        fallback_records,
        code="instances_boolean_csg_fallback",
    )
    manifest = _manifest_with_runtime_diagnostics(manifest, runtime_diagnostics)
    handoff_trace_operations = list(trace_operations)
    if final_operation_record:
        handoff_trace_operations.append(
            {
                "op": "instances_semantic_operation",
                "semantic_operation": semantic_operation,
                "semantic_operation_record": dict(final_operation_record),
            }
        )
    semantic_handoff = _attach_kernel_program_semantic_handoff(
        mesh,
        instance_operands,
        handoff_trace_operations,
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
        "kernel_program_diagnostics": list(manifest.get("diagnostics") or []),
        "kernel_program_capabilities_checked": sorted(required),
        "kernel_program_watertight": kernel.is_watertight(current),
        "kernel_program_body_count": result_body_count,
        "kernel_program_operands": [source.trace_record()],
        "kernel_program_instance_operands": [
            operand.trace_record() for operand in instance_operands
        ],
        "kernel_program_operations": trace_operations,
        "kernel_program_face_operation_attribution": face_operation_attribution,
        "face_operation_ids": face_operation_ids,
        "face_operation_summary": face_operation_summary,
        "source_face_operation_summary": source_face_operation_summary,
        "kernel_program_source_face_operation_attribution": source_face_operation_attribution,
        "kernel_program_instances_source_operand_id": source.operand_id,
        "instances_semantic_operation": semantic_operation,
        "instances_count": len(transform_matrices),
        "instances_semantic_operand_count": len(instance_operands),
        "instances_batch_union": bool(batch_union_available),
        "instances_batch_union_method": str(batch_union_metadata.get("method") or ""),
        "instances_batch_union_metadata": dict(batch_union_metadata),
        "instances_actual_assembly_method": assembly_method,
        "instances_expected_disjoint_group_count": int(expected_disjoint_groups),
        "instances_attempted_body_count": int(attempted_result_body_count),
        "instances_result_face_count": len(mesh.faces),
        "instances_result_body_count": int(result_body_count),
        "instances_result_watertight": bool(mesh.is_watertight),
        "instances_visible_preservation_fallback": visible_preservation_fallback,
        "instances_visible_preservation_fallback_applied": visible_preservation_fallback is not None,
        "instances_boolean_fallback_count": len(fallback_records),
        "instances_boolean_fallback_records": fallback_records,
        "kernel_scatter": kernel_scatter,
        "kernel_program_scatter": kernel_scatter,
        "kernel_pattern_instances": kernel_pattern_instances,
        "kernel_program_pattern_instances": kernel_pattern_instances,
        "kernel_feature_detail": kernel_feature_detail,
        "kernel_program_feature_detail": kernel_feature_detail,
        "kernel_program_semantic_handoff": semantic_handoff,
    }
    return KernelProgramResult(
        mesh=mesh,
        handle=current,
        operation_count=operation_count,
        details=details,
    )


__all__ = [
    "build_instances_program_manifest",
    "execute_instances_program",
]
