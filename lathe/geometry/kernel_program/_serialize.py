"""Serialization helpers — convert kernel program payloads to compact dicts.

This module groups the cluster of ``_compact_*`` helpers that produce
serializable, human-readable summaries of kernel-program payloads,
semantic handoffs, source shape records, and similar metadata. They
are pure functions; no side effects; safe to extract together.

The compacted form drops opaque kernel handles, repeated raw records,
and other heavy data while keeping the audit fields that make a
trace inspectable. Lathe's package manifests and validate-stage
reports consume these compact forms.
"""

from __future__ import annotations

from contextlib import suppress
from typing import Any


def _dict_metadata(value: Any) -> dict[str, Any]:
    """Return ``value`` if it is a dict, otherwise an empty dict."""
    return value if isinstance(value, dict) else {}


def _stable_unique_strings(values: list[Any]) -> list[str]:
    """Deterministic-order deduped string projection of an arbitrary list."""
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _compact_face_operation_ids(face_operation_ids: list[Any]) -> dict[str, Any]:
    ids = [str(item) for item in face_operation_ids]
    return {
        "schema": "lathe.geometry.compacted_face_operation_ids.v1",
        "omitted": True,
        "face_count": len(ids),
        "operation_count": len(set(ids)),
        "operations": {
            operation_id: ids.count(operation_id)
            for operation_id in sorted(set(ids))
        },
    }


def _compact_kernel_semantic_handoff(handoff: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key in (
        "schema",
        "source",
        "operand_count",
        "source_part_count",
        "source_parts",
        "source_primitive_types",
        "source_context_record_count",
        "source_context_parts",
        "source_context_primitive_types",
        "source_components",
        "source_regions",
        "component_sources",
        "cga_terminals",
        "cga_parametric_terminal_count",
        "cga_terminal_param_keys",
        "operation_record_count",
        "operation_counts",
        "seam_record_count",
        "hard_edge_record_count",
        "material_zone_candidate_count",
        "sdf_boolean_count",
        "exact_boolean_count",
        "backend_boolean_count",
        "fallback_count",
        "result_face_count",
        "result_watertight",
    ):
        value = handoff.get(key)
        if value not in (None, "", (), [], {}):
            compact[key] = _compact_kernel_handoff_value(value)
    operation_records = handoff.get("operation_records")
    if isinstance(operation_records, list):
        compact["operation_records"] = [
            _compact_kernel_handoff_value(record)
            for record in operation_records
            if isinstance(record, dict)
        ]
        compact["operation_record_count"] = len(compact["operation_records"])
    compact["compacted"] = True
    compact["omitted_fields"] = [
        key
        for key in (
            "operand_records",
            "seam_records",
            "hard_edge_records",
            "material_zone_candidates",
            "sdf_boolean_records",
            "exact_boolean_records",
            "backend_boolean_records",
            "fallback_records",
        )
        if key in handoff
    ]
    return compact


def _compact_kernel_result_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key in (
        "kernel_program_route",
        "kernel_program_kernel",
        "kernel_program_backend",
        "kernel_program_operation_count",
        "kernel_program_semantic_operation_record_count",
        "kernel_program_semantic_operation_counts",
        "kernel_program_capabilities_checked",
        "kernel_program_watertight",
        "face_operation_summary",
        "source_face_operation_summary",
        "kernel_program_face_operation_attribution",
        "lathe_kernel_program_face_operation_attribution",
        "kernel_program_source_face_operation_attribution",
        "lathe_kernel_program_source_face_operation_attribution",
        "result_face_count",
        "result_vertex_count",
        "result_watertight",
        "shape_ir_asset_name",
        "shape_ir_blueprint_id",
        "shape_ir_family",
        "shape_ir_primitive_count",
    ):
        value = metadata.get(key)
        if value not in (None, "", (), [], {}):
            compact[key] = _compact_kernel_handoff_value(value)
    for key in (
        "kernel_program_semantic_operation_records",
        "operation_records",
    ):
        records = metadata.get(key)
        if isinstance(records, list):
            compact[key] = [
                _compact_kernel_handoff_value(record)
                for record in records
                if isinstance(record, dict)
            ]
    for key in (
        "kernel_program_semantic_handoff",
        "lathe_kernel_program_semantic_handoff",
    ):
        handoff = metadata.get(key)
        if isinstance(handoff, dict):
            compact[key] = _compact_kernel_semantic_handoff(handoff)
    compact["compacted"] = True
    return compact


def _compact_kernel_program_payload(payload: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key in (
        "kernel_program_version",
        "kernel_program_route",
        "kernel_program_kernel",
        "kernel_program_backend",
        "kernel_program_operation_count",
        "kernel_program_operand_count",
        "kernel_program_semantic_operation_record_count",
        "kernel_program_semantic_operation_counts",
        "kernel_program_capabilities_checked",
        "kernel_program_watertight",
        "kernel_program_face_operation_attribution",
        "face_operation_summary",
        "source_face_operation_summary",
        "kernel_program_source_face_operation_attribution",
        "result_face_count",
        "result_vertex_count",
        "result_body_count",
        "result_watertight",
        "instances_count",
        "instances_semantic_operation",
        "instances_semantic_operand_count",
        "instances_batch_union",
        "instances_actual_assembly_method",
    ):
        value = payload.get(key)
        if value not in (None, "", (), [], {}):
            compact[key] = _compact_kernel_handoff_value(value)
    records = payload.get("kernel_program_semantic_operation_records")
    if isinstance(records, list):
        compact["kernel_program_semantic_operation_records"] = [
            _compact_kernel_handoff_value(record)
            for record in records
            if isinstance(record, dict)
        ]
    handoff = payload.get("kernel_program_semantic_handoff")
    if isinstance(handoff, dict):
        compact["kernel_program_semantic_handoff"] = _compact_kernel_semantic_handoff(handoff)
    compact["compacted"] = True
    compact["omitted_fields"] = [
        key
        for key in (
            "kernel_program_manifest",
            "kernel_program_operands",
            "kernel_program_instance_operands",
            "kernel_feature_detail",
            "kernel_program_feature_detail",
            "kernel_program_operations",
        )
        if key in payload
    ]
    return compact


def _compact_semantic_metadata_record(metadata: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key in (
        "component",
        "region",
        "feature",
        "operation",
        "operation_id",
        "material_hint",
        "component_source",
        "assembly_component",
        "cga_rule_component",
    ):
        value = metadata.get(key)
        if value not in (None, "", (), [], {}):
            compact[key] = _compact_kernel_handoff_value(value)
    shape_ir_v2 = metadata.get("shape_ir_v2")
    if isinstance(shape_ir_v2, dict):
        v2_compact: dict[str, Any] = {}
        for key, value in shape_ir_v2.items():
            text_key = str(key)
            if text_key in {
                "source_shape_primitive",
                "source_shape_primitives",
                "kernel_result_metadata",
            }:
                continue
            if value not in (None, "", (), [], {}):
                v2_compact[text_key] = _compact_kernel_handoff_value(value)
        if v2_compact:
            compact["shape_ir_v2"] = v2_compact
    semantic_repair = metadata.get("semantic_repair")
    if isinstance(semantic_repair, dict) and semantic_repair:
        compact["semantic_repair"] = _compact_kernel_handoff_value(semantic_repair)
    baked_modifiers = metadata.get("shape_ir_v2_baked_source_modifiers")
    if isinstance(baked_modifiers, dict) and baked_modifiers:
        compact["shape_ir_v2_baked_source_modifiers"] = _compact_kernel_handoff_value(
            baked_modifiers
        )
    source_shape = metadata.get("source_shape_primitive")
    if isinstance(source_shape, dict) and source_shape:
        compact["source_shape_primitive"] = _compact_source_shape_record(source_shape)
    source_shapes = metadata.get("source_shape_primitives")
    if isinstance(source_shapes, list) and source_shapes:
        compact["source_shape_primitives"] = [
            _compact_source_shape_record(record)
            for record in source_shapes
            if isinstance(record, dict)
        ]
    kernel_result = metadata.get("kernel_result_metadata")
    if isinstance(kernel_result, dict) and kernel_result:
        compact["kernel_result_metadata"] = _compact_kernel_result_metadata(kernel_result)
    return compact


def _compact_source_shape_record(record: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key, value in record.items():
        text_key = str(key)
        if text_key == "semantic_metadata" and isinstance(value, dict):
            semantic = _compact_semantic_metadata_record(value)
            if semantic:
                compact[text_key] = semantic
            continue
        if text_key in {
            "kernel_result_metadata",
            "source_shape_primitive",
            "source_shape_primitives",
        }:
            continue
        if (
            text_key.startswith("v2_")
            or text_key
            in {
                "schema",
                "primitive_type",
                "part",
                "component",
                "region",
                "blend_mode",
                "center",
                "extents",
                "radius",
                "height",
                "width",
                "depth",
                "thickness",
                "axis",
                "rounding",
                "operation",
                "operation_id",
                "tags",
            }
        ):
            compact[text_key] = _compact_kernel_handoff_value(value)
    return compact


def _compact_shape_record_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    context_counts: list[int] = []
    context_parts: list[Any] = []
    context_primitive_types: list[Any] = []
    for record in records:
        if record.get("v2_context_aggregate") or record.get("v2_context_record_count"):
            with suppress(TypeError, ValueError):
                context_counts.append(int(record.get("v2_context_record_count") or 1))
            context_parts.extend(record.get("v2_context_parts") or [])
            context_primitive_types.extend(record.get("v2_context_primitive_types") or [])
    payload = {
        "schema": "lathe.geometry.compact_shape_record_summary.v1",
        "record_count": len(records),
        "primitive_types": _stable_unique_strings(
            [record.get("primitive_type") for record in records]
        ),
        "parts": _stable_unique_strings([record.get("part") for record in records]),
        "components": _stable_unique_strings(
            [record.get("component") for record in records]
        ),
        "regions": _stable_unique_strings([record.get("region") for record in records]),
        "operations": _stable_unique_strings(
            [
                record.get("v2_op")
                or _dict_metadata(
                    _dict_metadata(record.get("semantic_metadata")).get("shape_ir_v2")
                ).get("v2_op")
                or _dict_metadata(record.get("semantic_metadata")).get("operation")
                for record in records
            ]
        ),
    }
    if context_counts:
        payload["context_record_count"] = sum(max(1, count) for count in context_counts)
    if context_parts:
        payload["context_parts"] = _stable_unique_strings(context_parts)
    if context_primitive_types:
        payload["context_primitive_types"] = _stable_unique_strings(
            context_primitive_types
        )
    return payload


def _compact_kernel_handoff_value(value: Any) -> Any:
    if isinstance(value, dict):
        compact: dict[str, Any] = {}
        for key, item in value.items():
            text_key = str(key)
            if text_key == "face_operation_ids" and isinstance(item, list):
                compact["face_operation_ids_compacted"] = _compact_face_operation_ids(item)
                continue
            if text_key in {
                "kernel_program_semantic_handoff",
                "lathe_kernel_program_semantic_handoff",
            } and isinstance(item, dict):
                compact[text_key] = _compact_kernel_semantic_handoff(item)
                continue
            if text_key == "kernel_program" and isinstance(item, dict):
                compact[text_key] = _compact_kernel_program_payload(item)
                continue
            if text_key == "kernel_result_metadata" and isinstance(item, dict):
                compact[text_key] = _compact_kernel_result_metadata(item)
                continue
            if text_key == "semantic_metadata" and isinstance(item, dict):
                compact[text_key] = _compact_semantic_metadata_record(item)
                continue
            if text_key == "source_shape_primitive" and isinstance(item, dict):
                compact[text_key] = _compact_source_shape_record(item)
                continue
            if text_key == "source_shape_primitives" and isinstance(item, list):
                compact[text_key] = [
                    _compact_source_shape_record(record)
                    for record in item
                    if isinstance(record, dict)
                ]
                continue
            compact[text_key] = _compact_kernel_handoff_value(item)
        return compact
    if isinstance(value, list):
        return [_compact_kernel_handoff_value(item) for item in value]
    return value


__all__ = [
    "_compact_face_operation_ids",
    "_compact_kernel_handoff_value",
    "_compact_kernel_program_payload",
    "_compact_kernel_result_metadata",
    "_compact_kernel_semantic_handoff",
    "_compact_semantic_metadata_record",
    "_compact_shape_record_summary",
    "_compact_source_shape_record",
    "_dict_metadata",
    "_stable_unique_strings",
]
