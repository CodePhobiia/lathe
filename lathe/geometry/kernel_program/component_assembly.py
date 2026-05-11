"""Component assembly program — execute a list of operands as a composed asset.

Per the §5.3 decomposition, this module hosts the component_assembly
family. The executor accepts a list of kernel operands and produces
one KernelProgramResult that represents the entire composition:
when all operands have additive blend modes the result is a
mesh-concatenation, when destructive modes are present the result is
routed through the boolean executor. Source records and per-component
summaries flow through the standard handoff surface.

This module also hosts the deep-walk helpers
_compact_component_assembly_record /
_component_assembly_records_from_primitive /
_component_assembly_summary_from_records /
_component_operand_semantic_summary that
semantic_metadata_from_primitive calls to materialize assembly
metadata onto a trace.
"""

from __future__ import annotations

from contextlib import suppress
import math
from typing import Any

import numpy as np
import trimesh

from ..kernel import GeometryKernel
from ._capabilities import (
    _SUPPORTED_BLEND_MODES,
    _kernel_capabilities,
    _require_capabilities,
    _required_boolean_capabilities,
)
from ._common import (
    _non_empty_mesh,
    _operation_id_fragment,
    _record_operation_result,
    _record_result_probe,
)
from ._core import (
    KernelOperand,
    KernelProgramResult,
    boolean_kernel_call_count,
    component_assembly_operation_count,
)
from ._face_operation import (
    _attach_direct_face_operation_metadata,
    _attach_semantic_whole_result_face_metadata,
    _instance_face_operation_ids,
    _kernel_program_face_operation_summary,
)
from ._records import (
    _operand_operation_records,
    _shape_record_operation,
    _shape_record_v2_metadata,
)
from ._semantic import (
    _final_semantic_operation_record,
    _operation_counts,
    _semantic_operation_records_from_manifest,
)
from ._semantic_handoff import _attach_kernel_program_semantic_handoff
from ._serialize import _dict_metadata, _json_safe, _stable_unique_strings

KERNEL_PROGRAM_VERSION = "lathe.geometry.kernel_program_v1"

_ASSEMBLY_RECORD_COPY_KEYS = (
    "primitive_type",
    "part",
    "component",
    "region",
    "blend_mode",
    "center",
    "axis",
    "tags",
    "v2_op",
    "v2_source_op",
    "v2_purpose",
    "v2_context_aggregate",
    "v2_context_parts",
    "v2_context_record_count",
    "v2_context_primitive_types",
    "assembly_kind",
)
_ASSEMBLY_RECORD_LIMIT = 128
_ASSEMBLY_RECORD_DEPTH_LIMIT = 4


def _record_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            converted = to_dict()
        except (TypeError, ValueError, RuntimeError):
            return {}
        return converted if isinstance(converted, dict) else {}
    return {}


def _compact_component_assembly_record(
    raw_record: Any,
    *,
    depth: int = 0,
    remaining: list[int] | None = None,
) -> dict[str, Any]:
    record = _record_dict(raw_record)
    if not record or depth > _ASSEMBLY_RECORD_DEPTH_LIMIT:
        return {}
    if remaining is None:
        remaining = [_ASSEMBLY_RECORD_LIMIT]
    if remaining[0] <= 0:
        return {}
    remaining[0] -= 1

    compact: dict[str, Any] = {}
    for key in _ASSEMBLY_RECORD_COPY_KEYS:
        value = record.get(key)
        if value not in (None, "", (), [], {}):
            compact[key] = _json_safe(value)
    v2_metadata = _shape_record_v2_metadata(record)
    if v2_metadata:
        compact["semantic_metadata"] = {"shape_ir_v2": _json_safe(v2_metadata)}
    children = record.get("assembly_primitives")
    if isinstance(children, list) and depth < _ASSEMBLY_RECORD_DEPTH_LIMIT:
        compact_children = [
            child
            for child in (
                _compact_component_assembly_record(
                    item,
                    depth=depth + 1,
                    remaining=remaining,
                )
                for item in children
            )
            if child
        ]
        if compact_children:
            compact["assembly_primitives"] = compact_children
    return compact


def _component_assembly_records_from_primitive(primitive: Any) -> list[dict[str, Any]]:
    raw_records = getattr(primitive, "assembly_primitives", None)
    if not isinstance(raw_records, list):
        return []
    remaining = [_ASSEMBLY_RECORD_LIMIT]
    records = [
        compact
        for compact in (
            _compact_component_assembly_record(item, remaining=remaining)
            for item in raw_records
        )
        if compact
    ]
    return records


def _component_assembly_summary_from_records(
    primitive: Any,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    primitive_types: list[Any] = []
    components: list[Any] = []
    regions: list[Any] = []
    operations: list[Any] = []

    def walk(record: dict[str, Any]) -> None:
        primitive_types.append(record.get("primitive_type"))
        components.append(record.get("component"))
        regions.append(record.get("region"))
        operation, _operation_id, _repair_action = _shape_record_operation(record)
        if operation:
            operations.append(operation)
        for child in record.get("assembly_primitives") or []:
            if isinstance(child, dict):
                walk(child)

    for record in records:
        walk(record)
    return {
        "schema": "lathe.geometry.component_assembly_semantic_summary.v1",
        "assembly_kind": str(getattr(primitive, "assembly_kind", None) or ""),
        "component_count": len(records),
        "component_primitive_types": _stable_unique_strings(primitive_types),
        "components": _stable_unique_strings(components),
        "regions": _stable_unique_strings(regions),
        "source_operations": _stable_unique_strings(operations),
        "truncated": _ASSEMBLY_RECORD_LIMIT <= _flattened_assembly_record_count(records),
    }


def _component_operand_semantic_summary(operands: list[KernelOperand]) -> dict[str, Any]:
    components: list[Any] = []
    regions: list[Any] = []
    assembly_kinds: list[Any] = []
    component_sources: list[Any] = []
    cga_terminals: list[Any] = []
    cga_terminal_param_keys: list[Any] = []
    cga_parametric_terminal_count = 0
    nested_component_count = 0
    for operand in operands:
        metadata = _dict_metadata(operand.metadata)
        semantic_metadata = _dict_metadata(metadata.get("semantic_metadata"))
        components.append(metadata.get("component"))
        regions.append(metadata.get("region"))
        component_sources.append(semantic_metadata.get("component_source"))
        cga = _dict_metadata(semantic_metadata.get("cga_rule_component"))
        cga_terminals.append(cga.get("terminal"))
        terminal_params = _dict_metadata(cga.get("terminal_params"))
        if terminal_params:
            cga_parametric_terminal_count += 1
            cga_terminal_param_keys.extend(terminal_params.keys())
        component_assembly = _dict_metadata(metadata.get("component_assembly"))
        if component_assembly:
            assembly_kinds.append(component_assembly.get("assembly_kind"))
            with suppress(TypeError, ValueError):
                nested_component_count += int(component_assembly.get("component_count") or 0)
    component_names = _stable_unique_strings(components)
    region_names = _stable_unique_strings(regions)
    kind_names = _stable_unique_strings(assembly_kinds)
    source_names = _stable_unique_strings(component_sources)
    terminal_names = _stable_unique_strings(cga_terminals)
    payload: dict[str, Any] = {}
    if component_names:
        payload["source_components"] = component_names
        payload["source_component_counts"] = {
            component: sum(
                1
                for operand in operands
                if str(_dict_metadata(operand.metadata).get("component") or "") == component
            )
            for component in component_names
        }
    if region_names:
        payload["source_regions"] = region_names
    if kind_names:
        payload["nested_assembly_kinds"] = kind_names
    if source_names:
        payload["component_sources"] = source_names
    if terminal_names:
        payload["cga_terminals"] = terminal_names
    if cga_parametric_terminal_count:
        payload["cga_parametric_terminal_count"] = int(cga_parametric_terminal_count)
        payload["cga_terminal_param_keys"] = _stable_unique_strings(cga_terminal_param_keys)
    if nested_component_count:
        payload["nested_component_count"] = int(nested_component_count)
    return payload


def _flattened_assembly_record_count(records: list[dict[str, Any]]) -> int:
    total = 0
    for record in records:
        total += 1
        children = record.get("assembly_primitives")
        if isinstance(children, list):
            total += _flattened_assembly_record_count(
                [child for child in children if isinstance(child, dict)]
            )
    return total


def build_component_assembly_program_manifest(
    operands: list[KernelOperand],
    *,
    semantic_operation: str = "component_assembly",
    assembly_kind: str = "component_assembly",
    route: str = "component_assembly_program",
    backend: str | None = None,
    operation_limit: int | None = None,
) -> dict[str, Any]:
    """Return a deterministic, handle-free manifest for visible component assembly."""
    operation_records = _operand_operation_records(operands)
    destructive = any(
        str(operand.blend_mode or "union") in {"subtract", "intersect"}
        for operand in operands
    )
    component_blend_modes = {
        mode: sum(1 for operand in operands if str(operand.blend_mode or "union") == mode)
        for mode in sorted({str(operand.blend_mode or "union") for operand in operands})
    }
    component_semantics = _component_operand_semantic_summary(operands)
    if not any(str(record.get("operation") or "") == semantic_operation for record in operation_records):
        operation_records.append(
            {
                "operation_id": f"program:{_operation_id_fragment(route)}:{_operation_id_fragment(semantic_operation)}",
                "operation": semantic_operation,
                "repair_action": "",
                "operand_id": "",
                "operand_index": -1,
                "part": "",
                "primitive_type": "",
                "blend_mode": "union",
                "source": "kernel_program.component_assembly",
                "component_operand_count": len(operands),
                "assembly_kind": assembly_kind,
            }
        )
    missing_handle_ids = [operand.operand_id for operand in operands if operand.handle is None]
    invalid_blend_modes = sorted(
        {
            str(operand.blend_mode)
            for operand in operands
            if str(operand.blend_mode or "union") not in _SUPPORTED_BLEND_MODES
        }
    )
    diagnostics: list[dict[str, Any]] = []
    if not operands:
        diagnostics.append(
            {
                "code": "kernel_component_assembly_empty_operand_list",
                "severity": "error",
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
    if invalid_blend_modes:
        diagnostics.append(
            {
                "code": "unsupported_kernel_program_blend_mode",
                "severity": "error",
                "blend_modes": invalid_blend_modes,
            }
        )
    operation_count = component_assembly_operation_count(operands)
    required_capabilities = (
        sorted(_required_boolean_capabilities(operands))
        if destructive
        else ["from_trimesh", "to_trimesh"]
    )
    kernel_call_count = (
        boolean_kernel_call_count(operands)
        if destructive
        else len(operands) + (1 if operands else 0)
    )
    limit_count = kernel_call_count if destructive else operation_count
    if operation_limit is not None and limit_count > operation_limit:
        limit_payload_key = "kernel_call_count" if destructive else "operation_count"
        diagnostics.append(
            {
                "code": "kernel_program_operation_limit_exceeded",
                "severity": "error",
                limit_payload_key: limit_count,
                "operation_limit": operation_limit,
            }
        )
    return {
        "schema": "lathe.geometry.kernel_program_manifest.v1",
        "version": KERNEL_PROGRAM_VERSION,
        "program_kind": "component_assembly",
        "route": route,
        "backend": backend,
        "operation_count": operation_count,
        "kernel_call_count": kernel_call_count,
        "operation_limit": operation_limit,
        "required_capabilities": required_capabilities,
        "operand_count": len(operands),
        "operands": [_json_safe(operand.trace_record()) for operand in operands],
        "semantic_operation_record_count": len(operation_records),
        "semantic_operation_counts": _operation_counts(operation_records),
        "semantic_operation_records": _json_safe(operation_records),
        "semantic_operation": semantic_operation,
        "assembly_kind": assembly_kind,
        "component_blend_modes": component_blend_modes,
        **component_semantics,
        "boolean_route": bool(destructive),
        "source_primitive_types": _stable_unique_strings(
            [operand.primitive_type for operand in operands]
        ),
        "source_parts": _stable_unique_strings([operand.part for operand in operands]),
        "diagnostics": diagnostics,
    }


def execute_component_assembly_program(
    kernel: GeometryKernel,
    operands: list[KernelOperand],
    *,
    semantic_operation: str = "component_assembly",
    assembly_kind: str = "component_assembly",
    operation_limit: int | None = None,
    route: str = "component_assembly_program",
    backend: str | None = None,
) -> KernelProgramResult:
    """Execute a heterogeneous visible component assembly through the kernel seam."""
    if not operands:
        raise ValueError("kernel component_assembly program requires at least one operand")
    unsupported_blend_modes = sorted(
        {
            str(operand.blend_mode or "union")
            for operand in operands
            if str(operand.blend_mode or "union") != "union"
        }
    )
    missing_handles = [operand.operand_id for operand in operands if operand.handle is None]
    if missing_handles:
        raise ValueError(
            f"kernel component_assembly operands have no handles: {missing_handles!r}"
        )
    if unsupported_blend_modes:
        component_manifest = build_component_assembly_program_manifest(
            operands,
            semantic_operation=semantic_operation,
            assembly_kind=assembly_kind,
            route=route,
            backend=backend,
            operation_limit=operation_limit,
        )
        result = execute_boolean_program(
            kernel,
            operands,
            operation_limit=operation_limit,
            route=f"{route}_ordered_boolean",
            backend=backend,
        )
        mesh = result.mesh
        result_body_count = kernel.body_count(result.handle)
        source_face_counts = [int(operand.source_mesh_face_count) for operand in operands]
        source_vertex_counts = [
            int(len(operand.source_mesh.vertices))
            if isinstance(operand.source_mesh, trimesh.Trimesh)
            else 0
            for operand in operands
        ]
        source_body_counts = [int(operand.source_mesh_body_count) for operand in operands]
        component_parts = _stable_unique_strings([operand.part for operand in operands])
        component_primitive_types = _stable_unique_strings(
            [operand.primitive_type for operand in operands]
        )
        component_blend_modes = {
            mode: sum(1 for operand in operands if str(operand.blend_mode or "union") == mode)
            for mode in sorted({str(operand.blend_mode or "union") for operand in operands})
        }
        component_semantics = _component_operand_semantic_summary(operands)
        fallback_count = int(result.details.get("kernel_program_boolean_fallback_count") or 0)
        component_assembly_metadata = {
            "schema": "lathe.geometry.kernel_component_assembly.v1",
            "operation": semantic_operation,
            "assembly_kind": assembly_kind,
            "method": "ordered_boolean_component_assembly_program_v1",
            "attempted_backend": f"{kernel.name}.ordered_boolean",
            "actual_backend": f"{kernel.name}.ordered_boolean",
            "attempted_kernel": kernel.name,
            "actual_kernel": kernel.name,
            "actual_operation": "ordered_boolean",
            "fallback": bool(fallback_count),
            "passthrough": False,
            "operand_count": len(operands),
            "component_blend_modes": component_blend_modes,
            **component_semantics,
            "unsupported_blend_modes_routed": unsupported_blend_modes,
            "source_parts": component_parts,
            "source_primitive_types": component_primitive_types,
            "source_face_counts": source_face_counts,
            "source_vertex_counts": source_vertex_counts,
            "source_body_counts": source_body_counts,
            "source_face_count": int(sum(source_face_counts)),
            "source_vertex_count": int(sum(source_vertex_counts)),
            "source_body_count": int(sum(source_body_counts)),
            "result_face_count": len(mesh.faces),
            "result_vertex_count": len(mesh.vertices),
            "result_watertight": bool(mesh.is_watertight),
            "result_body_count": int(result_body_count),
            "boolean_operation_count": int(boolean_operation_count(operands)),
            "boolean_fallback_count": fallback_count,
        }
        mesh.metadata["lathe_kernel_component_assembly"] = dict(component_assembly_metadata)
        details = {
            **dict(result.details),
            "kernel_program_component_assembly_boolean_route": True,
            "kernel_program_component_assembly_requested_route": route,
            "kernel_program_component_assembly_actual_route": result.details.get("kernel_program_route"),
            "kernel_program_component_assembly_manifest": component_manifest,
            "component_assembly_semantic_operation": semantic_operation,
            "component_assembly_kind": assembly_kind,
            "component_assembly_method": "ordered_boolean_component_assembly_program_v1",
            "component_assembly_source_operand_count": len(operands),
            "component_assembly_source_parts": component_parts,
            "component_assembly_source_primitive_types": component_primitive_types,
            "component_assembly_component_blend_modes": component_blend_modes,
            **{
                f"component_assembly_{key}": value
                for key, value in component_semantics.items()
            },
            "component_assembly_source_face_count": int(sum(source_face_counts)),
            "component_assembly_source_vertex_count": int(sum(source_vertex_counts)),
            "component_assembly_source_body_count": int(sum(source_body_counts)),
            "component_assembly_result_face_count": len(mesh.faces),
            "component_assembly_result_vertex_count": len(mesh.vertices),
            "component_assembly_result_body_count": int(result_body_count),
            "component_assembly_result_watertight": bool(mesh.is_watertight),
            "kernel_component_assembly": component_assembly_metadata,
        }
        return KernelProgramResult(
            mesh=mesh,
            handle=result.handle,
            operation_count=result.operation_count,
            details=details,
        )
    operation_count = component_assembly_operation_count(operands)
    if operation_limit is not None and operation_count > operation_limit:
        raise ValueError(
            f"kernel component_assembly operation_count={operation_count} exceeds "
            f"limit={operation_limit}"
        )
    capabilities = _kernel_capabilities(kernel)
    required = {"from_trimesh", "to_trimesh"}
    _require_capabilities(kernel, capabilities, required)
    manifest = build_component_assembly_program_manifest(
        operands,
        semantic_operation=semantic_operation,
        assembly_kind=assembly_kind,
        route=route,
        backend=backend,
        operation_limit=operation_limit,
    )

    source_meshes = [_non_empty_mesh(kernel, operand.handle).copy() for operand in operands]
    combined = trimesh.util.concatenate([mesh.copy() for mesh in source_meshes])
    if not isinstance(combined, trimesh.Trimesh) or len(combined.faces) == 0:
        raise ValueError("kernel component_assembly program produced an empty mesh")
    combined.remove_infinite_values()
    combined.remove_unreferenced_vertices()
    try:
        combined.fix_normals()
    except (AttributeError, TypeError, ValueError, RuntimeError):
        pass

    source_body_counts: list[int] = []
    for mesh in source_meshes:
        try:
            source_body_counts.append(int(len(mesh.split(only_watertight=False))))
        except (AttributeError, TypeError, ValueError, RuntimeError):
            source_body_counts.append(0)
    source_face_counts = [len(mesh.faces) for mesh in source_meshes]
    source_vertex_counts = [len(mesh.vertices) for mesh in source_meshes]
    component_primitive_types = _stable_unique_strings(
        [operand.primitive_type for operand in operands]
    )
    component_parts = _stable_unique_strings([operand.part for operand in operands])
    component_semantics = _component_operand_semantic_summary(operands)
    component_assembly_metadata = {
        "schema": "lathe.geometry.kernel_component_assembly.v1",
        "operation": semantic_operation,
        "assembly_kind": assembly_kind,
        "method": "visible_mesh_concatenation_import_v1",
        "attempted_backend": f"{kernel.name}.from_trimesh",
        "actual_backend": f"{kernel.name}.from_trimesh",
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "actual_operation": semantic_operation,
        "fallback": False,
        "passthrough": False,
        "operand_count": len(operands),
        **component_semantics,
        "source_parts": component_parts,
        "source_primitive_types": component_primitive_types,
        "source_face_counts": source_face_counts,
        "source_vertex_counts": source_vertex_counts,
        "source_body_counts": source_body_counts,
        "source_face_count": int(sum(source_face_counts)),
        "source_vertex_count": int(sum(source_vertex_counts)),
        "source_body_count": int(sum(source_body_counts)),
        "result_face_count": len(combined.faces),
        "result_vertex_count": len(combined.vertices),
        "result_watertight": bool(combined.is_watertight),
        "result_body_count": int(len(combined.split(only_watertight=False))),
    }
    combined.metadata["lathe_kernel_component_assembly"] = dict(component_assembly_metadata)
    current = kernel.from_trimesh(combined)
    mesh = _non_empty_mesh(kernel, current)
    mesh.metadata["lathe_kernel_component_assembly"] = dict(component_assembly_metadata)

    operation_records = _semantic_operation_records_from_manifest(manifest)
    operation_record = {
        "op": "component_assembly",
        "semantic_operation": semantic_operation,
        "assembly_kind": assembly_kind,
        "inputs": [operand.operand_id for operand in operands],
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "attempted_backend": f"{kernel.name}.from_trimesh",
        "actual_backend": f"{kernel.name}.from_trimesh",
        "actual_operation": semantic_operation,
        "method": "visible_mesh_concatenation_import_v1",
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_watertight": bool(mesh.is_watertight),
        "result_body_count": kernel.body_count(current),
        "kernel_component_assembly": dict(component_assembly_metadata),
    }
    _record_result_probe(operation_record, kernel=kernel, result_handle=current)
    face_operation_ids = _instance_face_operation_ids(
        operands,
        source_meshes,
        mesh,
        assembly_method="visible_mesh_concatenation_import",
    )
    face_operation_summary: dict[str, Any] = {}
    face_operation_attribution = {
        "schema": "lathe.geometry.kernel_program_face_operation_attribution.v1",
        "source": "kernel_program.component_assembly.operands",
        "attributed": bool(face_operation_ids),
        "assembly_method": "visible_mesh_concatenation_import",
        "component_count": len(operands),
        "result_face_count": len(mesh.faces),
    }
    if face_operation_ids:
        face_operation_summary = _kernel_program_face_operation_summary(
            face_operation_ids,
            source="kernel_program.component_assembly.component_operands",
        )
        face_operation_attribution.update(
            {
                "method": "concatenated_component_face_ranges",
                "face_operation_count": len(set(face_operation_ids)),
                "face_operation_attribution_count": len(face_operation_ids),
            }
        )
        mesh.metadata["face_operation_ids"] = list(face_operation_ids)
        mesh.metadata["face_operation_summary"] = dict(face_operation_summary)
    else:
        face_operation_attribution["reason"] = (
            "kernel_result_faces_not_a_direct_component_concatenation"
        )
    mesh.metadata["lathe_kernel_program_face_operation_attribution"] = dict(
        face_operation_attribution
    )
    semantic_handoff = _attach_kernel_program_semantic_handoff(
        mesh,
        operands,
        [operation_record],
    )
    result_body_count = kernel.body_count(current)
    details = {
        "kernel_program_version": KERNEL_PROGRAM_VERSION,
        "kernel_program_route": route,
        "kernel_program_operation_count": operation_count,
        "kernel_program_operand_count": len(operands),
        "kernel_program_semantic_operation_record_count": len(operation_records),
        "kernel_program_semantic_operation_counts": _operation_counts(operation_records),
        "kernel_program_semantic_operation_records": operation_records,
        "kernel_program_kernel": kernel.name,
        "kernel_program_backend": backend,
        "kernel_program_manifest": manifest,
        "kernel_program_capabilities_checked": sorted(required),
        "kernel_program_watertight": kernel.is_watertight(current),
        "kernel_program_body_count": result_body_count,
        "kernel_program_operands": [operand.trace_record() for operand in operands],
        "kernel_program_operations": [operation_record],
        "kernel_program_face_operation_attribution": face_operation_attribution,
        "face_operation_ids": face_operation_ids,
        "face_operation_summary": face_operation_summary,
        "component_assembly_semantic_operation": semantic_operation,
        "component_assembly_kind": assembly_kind,
        "component_assembly_method": "visible_mesh_concatenation_import_v1",
        "component_assembly_source_operand_count": len(operands),
        "component_assembly_source_parts": component_parts,
        "component_assembly_source_primitive_types": component_primitive_types,
        **{
            f"component_assembly_{key}": value
            for key, value in component_semantics.items()
        },
        "component_assembly_source_face_count": int(sum(source_face_counts)),
        "component_assembly_source_vertex_count": int(sum(source_vertex_counts)),
        "component_assembly_source_body_count": int(sum(source_body_counts)),
        "component_assembly_result_face_count": len(mesh.faces),
        "component_assembly_result_vertex_count": len(mesh.vertices),
        "component_assembly_result_body_count": int(result_body_count),
        "component_assembly_result_watertight": bool(mesh.is_watertight),
        "kernel_component_assembly": component_assembly_metadata,
        "kernel_program_semantic_handoff": semantic_handoff,
    }
    return KernelProgramResult(
        mesh=mesh,
        handle=current,
        operation_count=operation_count,
        details=details,
    )


__all__ = [
    "_compact_component_assembly_record",
    "_component_assembly_records_from_primitive",
    "_component_assembly_summary_from_records",
    "_component_operand_semantic_summary",
    "_flattened_assembly_record_count",
    "_record_dict",
    "build_component_assembly_program_manifest",
    "execute_component_assembly_program",
]
