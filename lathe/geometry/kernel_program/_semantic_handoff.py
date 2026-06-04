"""Kernel-program semantic handoff payload builder.

Every ``execute_*_program`` call wraps its result mesh with a
"semantic handoff" payload that downstream stages consume to:

  - Attribute result faces back to source operations.
  - Track seam groups, hard-edge groups, and material-zone candidates
    inferred from operand metadata.
  - Surface boolean-backend lineage (SDF / exact / backend / fallback
    records) so validation can inspect how the boolean composition ran.
  - Carry source-component / region / CGA-terminal metadata onto the
    result mesh so the surface and validate stages can preserve
    component context.

The builder is large because it consolidates *everything* a per-op
executor would otherwise need to assemble inline. Per the §5.3
decomposition plan, isolating the handoff into a dedicated module
lets each per-op executor stay focused on its own boolean/refine/etc.
work and import a single function to attach the handoff.

This module also hosts ``_sdf_lineage_stats`` — the SDF-specific
recursion helper the handoff uses to summarize SDF boolean trees.
"""

from __future__ import annotations

from contextlib import suppress
from typing import Any

import trimesh

from ._core import KernelOperand
from ._face_operation import _metadata_list
from ._records import _operand_operation_records, _operand_semantic_records
from ._semantic import (
    _dedupe_operation_records,
    _operation_counts,
    _trace_semantic_operation_records,
)
from ._serialize import _dict_metadata, _json_safe, _stable_unique_strings


def _sdf_lineage_stats(metadata: dict[str, Any]) -> dict[str, Any]:
    """Summarize an SDF boolean tree: counts, smooth-ops, blend widths, leaf types.

    Walks the ``source`` / ``cutter`` children recursively. Each
    ``sdf_boolean`` node increments ``operation_count``; ``smooth_boolean``
    or non-zero ``blend_width_cm`` adds to ``smooth_operation_count``
    and updates ``max_blend_width_cm``. Non-boolean nodes are recorded
    as leaf primitive types.
    """
    operation_count = 0
    smooth_operation_count = 0
    max_blend_width = 0.0
    leaf_types: list[str] = []
    boolean_ops: list[str] = []

    def walk(node: Any) -> None:
        nonlocal operation_count, smooth_operation_count, max_blend_width
        if not isinstance(node, dict):
            return
        primitive_type = str(node.get("primitive_type") or "")
        op = str(node.get("op") or "")
        if primitive_type == "sdf_boolean":
            operation_count += 1
            if op:
                boolean_ops.append(op)
            try:
                blend_width = float(node.get("blend_width_cm") or 0.0)
            except (TypeError, ValueError):
                blend_width = 0.0
            if bool(node.get("smooth_boolean")) or blend_width > 0.0:
                smooth_operation_count += 1
                max_blend_width = max(max_blend_width, blend_width)
            walk(node.get("source"))
            walk(node.get("cutter"))
            return
        if primitive_type:
            leaf_types.append(primitive_type)

    operation_count = 1
    if metadata.get("op"):
        boolean_ops.append(str(metadata.get("op") or ""))
    try:
        root_blend_width = float(metadata.get("blend_width_cm") or 0.0)
    except (TypeError, ValueError):
        root_blend_width = 0.0
    if bool(metadata.get("smooth_boolean")) or root_blend_width > 0.0:
        smooth_operation_count += 1
        max_blend_width = max(max_blend_width, root_blend_width)
    walk(metadata.get("source"))
    walk(metadata.get("cutter"))
    return {
        "operation_count": int(operation_count),
        "smooth_operation_count": int(smooth_operation_count),
        "max_blend_width_cm": round(float(max_blend_width), 6),
        "boolean_ops": _stable_unique_strings(boolean_ops),
        "leaf_primitive_types": _stable_unique_strings(leaf_types),
    }


def _kernel_program_semantic_handoff(
    operands: list[KernelOperand],
    trace_operations: list[dict[str, Any]],
    result_mesh: trimesh.Trimesh,
) -> dict[str, Any]:
    """Build the structured handoff payload attached to every kernel-program result.

    Combines:
      - Per-operand semantic records (``_operand_semantic_records``).
      - Deduped operation records (operand metadata + trace operations).
      - Seam / hard-edge / material-zone candidate aggregation from
        operand metadata.
      - SDF / exact / backend / fallback boolean trace summaries.
      - Source-context aggregates (parts, primitive types, components,
        regions, CGA terminals).
      - Result-mesh metadata (face count, watertightness, SDF lineage).
    """
    operand_records = [
        _operand_semantic_records(operand, index)
        for index, operand in enumerate(operands)
    ]
    operation_records = _dedupe_operation_records(
        [
            *_operand_operation_records(operands),
            *_trace_semantic_operation_records(trace_operations),
        ]
    )
    seam_records: list[dict[str, Any]] = []
    hard_edge_records: list[dict[str, Any]] = []
    material_zone_candidates: list[dict[str, Any]] = []
    for operand_record in operand_records:
        part = str(operand_record.get("part") or "")
        component = str(operand_record.get("component") or "")
        primitive_type = str(operand_record.get("primitive_type") or "")
        tags = [str(tag) for tag in operand_record.get("tags", []) if str(tag)]
        operand_lineage = {
            "operand_id": str(operand_record.get("operand_id") or ""),
            "operand_index": int(operand_record.get("operand_index") or 0),
            **(
                {"source_index": int(operand_record["source_index"])}
                if operand_record.get("source_index") is not None
                else {}
            ),
            **(
                {"instance_index": int(operand_record["instance_index"])}
                if operand_record.get("instance_index") is not None
                else {}
            ),
            **(
                {"instance_id": str(operand_record.get("instance_id") or "")}
                if operand_record.get("instance_id")
                else {}
            ),
        }
        for field, target in (
            ("boolean_seam_groups", seam_records),
            ("bevel_seam_groups", seam_records),
        ):
            for index, group in enumerate(_metadata_list(operand_record.get(field))):
                target.append(
                    {
                        **group,
                        "part": part,
                        "component": component,
                        "primitive_type": primitive_type,
                        "source": f"kernel_operand.{field}",
                        "group_index": int(index),
                        **operand_lineage,
                    }
                )
        for index, group in enumerate(_metadata_list(operand_record.get("hard_edge_groups"))):
            hard_edge_records.append(
                {
                    **group,
                    "part": part,
                    "component": component,
                    "primitive_type": primitive_type,
                    "source": "kernel_operand.hard_edge_groups",
                    "group_index": int(index),
                    **operand_lineage,
                }
            )
        semantic_metadata = _dict_metadata(operand_record.get("semantic_metadata"))
        material_hint = (
            semantic_metadata.get("material_hint")
            or semantic_metadata.get("material_zone")
            or component
        )
        if (
            operand_record.get("blend_mode") != "subtract"
            and ("material_zone" in tags or "wear_zone" in tags or material_hint)
        ):
            material_zone_candidates.append(
                {
                    "name": f"kernel_material_{len(material_zone_candidates):03d}_{part or 'mesh'}",
                    "part": part,
                    "component": component,
                    "primitive_type": primitive_type,
                    "material_hint": str(material_hint or primitive_type or "material"),
                    "source": "kernel_operand.semantic_handoff",
                    "tags": tags,
                    **operand_lineage,
                }
            )

    sdf_records: list[dict[str, Any]] = []
    exact_records: list[dict[str, Any]] = []
    backend_records: list[dict[str, Any]] = []
    fallback_records: list[dict[str, Any]] = []
    for operation_index, operation in enumerate(trace_operations):
        if not isinstance(operation, dict):
            continue
        sdf = operation.get("kernel_sdf_boolean")
        if isinstance(sdf, dict):
            sdf_records.append(
                {
                    "operation_index": int(operation_index),
                    "op": str(operation.get("op") or sdf.get("op") or ""),
                    "method": str(sdf.get("method") or ""),
                    "backend": str(sdf.get("backend") or ""),
                    "source_primitive_type": str(sdf.get("source_primitive_type") or ""),
                    "cutter_primitive_type": str(sdf.get("cutter_primitive_type") or ""),
                    "result_face_count": int(sdf.get("result_face_count") or 0),
                    "result_watertight": bool(sdf.get("result_watertight", False)),
                    "lineage": _sdf_lineage_stats(sdf),
                }
            )
        exact = operation.get("kernel_exact_boolean")
        if isinstance(exact, dict):
            exact_records.append({"operation_index": int(operation_index), **dict(exact)})
        backend = operation.get("kernel_boolean_backend")
        if isinstance(backend, dict):
            backend_records.append({"operation_index": int(operation_index), **dict(backend)})
        fallback = operation.get("kernel_fallback")
        if isinstance(fallback, dict):
            fallback_records.append({"operation_index": int(operation_index), **dict(fallback)})

    part_names = _stable_unique_strings([record.get("part") for record in operand_records])
    component_names = _stable_unique_strings(
        [record.get("component") for record in operand_records]
    )
    region_names = _stable_unique_strings(
        [record.get("region") for record in operand_records]
    )
    component_source_names = _stable_unique_strings(
        [
            _dict_metadata(record.get("semantic_metadata")).get("component_source")
            for record in operand_records
        ]
    )
    cga_terminal_names = _stable_unique_strings(
        [
            _dict_metadata(
                _dict_metadata(record.get("semantic_metadata")).get("cga_rule_component")
            ).get("terminal")
            for record in operand_records
        ]
    )
    cga_param_records = [
        _dict_metadata(
            _dict_metadata(
                _dict_metadata(record.get("semantic_metadata")).get("cga_rule_component")
            ).get("terminal_params")
        )
        for record in operand_records
    ]
    cga_terminal_param_keys = _stable_unique_strings(
        key
        for params in cga_param_records
        if params
        for key in params
    )
    context_record_count = 0
    for record in operand_records:
        with suppress(TypeError, ValueError):
            context_record_count += int(record.get("source_context_record_count") or 0)
    context_part_names = _stable_unique_strings(
        part
        for record in operand_records
        for part in record.get("source_context_parts", [])
    )
    context_primitive_types = _stable_unique_strings(
        primitive_type
        for record in operand_records
        for primitive_type in record.get("source_context_primitive_types", [])
    )
    result_metadata = result_mesh.metadata if isinstance(result_mesh.metadata, dict) else {}
    result_sdf = result_metadata.get("lathe_reference_sdf_boolean")
    return _json_safe(
        {
            "schema": "lathe.geometry.kernel_program_semantic_handoff.v1",
            "source": "kernel_program.operands_and_operation_trace",
            "operand_count": len(operand_records),
            "source_part_count": len(part_names),
            "source_parts": part_names,
            "source_primitive_types": _stable_unique_strings(
                [record.get("primitive_type") for record in operand_records]
            ),
            "source_context_record_count": context_record_count,
            "source_context_parts": context_part_names,
            "source_context_primitive_types": context_primitive_types,
            "source_components": component_names,
            "source_regions": region_names,
            "component_sources": component_source_names,
            "cga_terminals": cga_terminal_names,
            "cga_parametric_terminal_count": sum(1 for params in cga_param_records if params),
            "cga_terminal_param_keys": cga_terminal_param_keys,
            "operand_records": operand_records,
            "operation_records": operation_records,
            "operation_record_count": len(operation_records),
            "operation_counts": _operation_counts(operation_records),
            "seam_records": seam_records,
            "seam_record_count": len(seam_records),
            "hard_edge_records": hard_edge_records,
            "hard_edge_record_count": len(hard_edge_records),
            "material_zone_candidates": material_zone_candidates,
            "material_zone_candidate_count": len(material_zone_candidates),
            "sdf_boolean_records": sdf_records,
            "sdf_boolean_count": len(sdf_records),
            "exact_boolean_count": len(exact_records),
            "backend_boolean_count": len(backend_records),
            "fallback_count": len(fallback_records),
            "exact_boolean_records": exact_records,
            "backend_boolean_records": backend_records,
            "fallback_records": fallback_records,
            "result_sdf_lineage": (
                _sdf_lineage_stats(result_sdf)
                if isinstance(result_sdf, dict)
                else {}
            ),
            "result_face_count": len(result_mesh.faces),
            "result_watertight": bool(result_mesh.is_watertight),
        }
    )


def _attach_kernel_program_semantic_handoff(
    mesh: trimesh.Trimesh,
    operands: list[KernelOperand],
    trace_operations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Attach source-operation lineage to a kernel-program result mesh.

    Builds the handoff payload via ``_kernel_program_semantic_handoff``
    and stores it on ``mesh.metadata["lathe_kernel_program_semantic_handoff"]``.
    Returns the payload so the caller can also embed it in the
    kernel-program trace details.
    """
    semantic_handoff = _kernel_program_semantic_handoff(
        operands,
        trace_operations,
        mesh,
    )
    mesh.metadata["lathe_kernel_program_semantic_handoff"] = semantic_handoff
    return semantic_handoff


__all__ = [
    "_attach_kernel_program_semantic_handoff",
    "_kernel_program_semantic_handoff",
    "_sdf_lineage_stats",
]
