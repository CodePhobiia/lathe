"""Topology stage runtime helpers and the multi-part scene contract.

# Multi-part scene contract (downstream input format)

Starting with the chest-quality preservation fix, the topology stage emits a
multi-part scene rather than a single fused mesh. The contract is::

    MultiPartScene = trimesh.Scene
        # scene.geometry: dict[str, trimesh.Trimesh] keyed by part_name
        # one Trimesh per Blueprint component (body, lid_panel, foot_l, ...).
        # For a chest this is typically 18 parts.

    MultiPartManifest = list[PartManifest]
        # Parallel list with one entry per part, in scene insertion order.

    PartManifest = {
        "name": str,                       # matches scene.geometry key
        "face_count": int,
        "vertex_count": int,
        "tags": list[str],                 # seam_class tags, plank_displacement, etc.
        "parent_blueprint_component": str, # source component name from shape stage
        "transform": list[list[float]] | None,  # 4x4 row-major or null
        "metadata": dict[str, Any],        # free-form per-part metadata
    }

The stage also keeps a flattened ``RuntimeMesh`` (single Trimesh) for legacy
consumers via :func:`flatten_to_single_mesh`. New consumers (uv, surface,
optimize) should iterate ``scene.geometry`` and the manifest in lockstep so
they can apply per-part operations (per-part xatlas pack, per-part decimate
budget, plank-displacement targeting only the body part, etc.).

Bundle.json grows a top-level ``parts`` array mirroring ``MultiPartManifest``,
plus a ``part_count`` integer for fast triage. Older single-mesh tooling can
keep reading ``mesh_uri`` (still points at ``topology.glb``) — trimesh will
load the multi-part scene transparently and downstream code that calls
``trimesh.util.concatenate`` will see all parts welded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import trimesh


def _selected_candidate(shape_bundle: dict[str, Any]) -> dict[str, Any]:
    selected_id = shape_bundle.get("selected_candidate_id")
    for candidate in shape_bundle.get("candidates", []):
        if isinstance(candidate, dict) and candidate.get("candidate_id") == selected_id:
            return candidate
    return {}


def _exact_generated_uv_semantics(shape_bundle: dict[str, Any]) -> dict[str, Any]:
    candidate = _selected_candidate(shape_bundle)
    integration = candidate.get("integration_report", {}) if isinstance(candidate, dict) else {}
    if not isinstance(integration, dict):
        return {}
    if not integration.get("post_boolean_polybevel_direct_uv_assignment"):
        return {}
    strip_records = integration.get("post_boolean_polybevel_strips", [])
    if not isinstance(strip_records, list):
        strip_records = []
    return {
        "schema": "lathe.exact_solid.generated_uv_semantics.v1",
        "source": "shape.integration_report.post_boolean_polybevel",
        "method": integration.get("post_boolean_polybevel_method", ""),
        "direct_uv_assignment": bool(
            integration.get("post_boolean_polybevel_direct_uv_assignment", False)
        ),
        "generated_uv_vertex_count": int(
            integration.get("post_boolean_polybevel_generated_uv_vertex_count", 0) or 0
        ),
        "strip_count": int(integration.get("post_boolean_polybevel_strip_count", 0) or 0),
        "open_strip_count": int(
            integration.get("post_boolean_polybevel_open_strip_count", 0) or 0
        ),
        "closed_strip_count": int(
            integration.get("post_boolean_polybevel_closed_strip_count", 0) or 0
        ),
        "largest_strip_edge_count": int(
            integration.get("post_boolean_polybevel_largest_strip_edge_count", 0) or 0
        ),
        "total_strip_uv_span_cm": float(
            integration.get("post_boolean_polybevel_total_strip_uv_span_cm", 0.0) or 0.0
        ),
        "largest_strip_uv_span_cm": float(
            integration.get("post_boolean_polybevel_largest_strip_uv_span_cm", 0.0) or 0.0
        ),
        "strip_uv_source": str(integration.get("post_boolean_polybevel_strip_uv_source", "")),
        "atlas_hint": "preserve_generated_bevel_strip_uvs_when_repacking",
        "strips": [dict(record) for record in strip_records if isinstance(record, dict)],
    }


_MESH_IR_SEMANTIC_FIELDS = (
    "seam_classes",
    "hard_edge_classes",
    "bake_groups",
    "material_zones",
)
_KERNEL_PART_SEMANTIC_FIELDS = (
    "kernel_feature_details",
    "kernel_edge_treatments",
    "kernel_pattern_instances",
    "kernel_deforms",
    "kernel_profile_paths",
    "kernel_edge_controls",
    "kernel_component_assemblies",
    "kernel_sdf_fields",
    "kernel_terrain_fields",
    "kernel_scatters",
    "kernel_surface_damage",
)
_KERNEL_PART_KEYS = (
    "part",
    "source_part",
    "target_part",
    "template_part",
    "component_part",
    "result_part",
    "primary_part",
    "assembly_part",
)
_KERNEL_PART_LIST_KEYS = (
    "parts",
    "source_parts",
    "target_parts",
    "template_parts",
    "component_parts",
    "assembly_parts",
)
_KERNEL_NESTED_PART_FIELDS = (
    "features",
    "treatments",
    "damages",
    "components",
    "component_records",
    "instances",
    "instance_records",
    "operand_records",
    "operation_records",
    "source_records",
    "source_shape_primitives",
    "feature_records",
    "provenance_records",
    "children",
    "members",
)


def _selected_mesh_ir(shape_bundle: dict[str, Any]) -> dict[str, Any]:
    candidate = _selected_candidate(shape_bundle)
    mesh_ir = candidate.get("mesh_ir") if isinstance(candidate, dict) else {}
    return dict(mesh_ir) if isinstance(mesh_ir, dict) else {}


def _semantic_records(mesh_ir: dict[str, Any], field: str) -> list[dict[str, Any]]:
    records = mesh_ir.get(field, [])
    if not isinstance(records, list):
        return []
    return [dict(record) for record in records if isinstance(record, dict)]


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _record_link_parts(record: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        part = str(value or "").strip()
        if not part or part in seen:
            return
        seen.add(part)
        parts.append(part)

    def walk(value: Any, depth: int = 0) -> None:
        if depth > 4:
            return
        if isinstance(value, dict):
            for key in _KERNEL_PART_KEYS:
                add(value.get(key))
            for key in _KERNEL_PART_LIST_KEYS:
                items = value.get(key)
                if isinstance(items, (list, tuple, set)):
                    for item in items:
                        add(item)
            for field in _KERNEL_NESTED_PART_FIELDS:
                nested = value.get(field)
                if nested is not None:
                    walk(nested, depth + 1)
            return
        if isinstance(value, list):
            for item in value:
                walk(item, depth + 1)

    walk(record)
    return parts


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _semantic_operation_record(field: str, record: dict[str, Any]) -> dict[str, Any] | None:
    metadata = _dict_value(record.get("semantic_metadata"))
    v2_metadata = _dict_value(metadata.get("shape_ir_v2"))
    repair_metadata = _dict_value(metadata.get("semantic_repair"))
    operation = (
        v2_metadata.get("v2_op")
        or repair_metadata.get("lowered_operation")
        or record.get("operation")
        or metadata.get("operation")
    )
    repair_action = repair_metadata.get("action") or v2_metadata.get("repair_action")
    operation_id = (
        v2_metadata.get("operation_id")
        or repair_metadata.get("operation_id")
        or record.get("operation_id")
    )
    if not any((operation, repair_action, operation_id)):
        return None
    part = str(record.get("part") or "")
    primitive_index = record.get("primitive_index")
    if not operation_id:
        operation_id = (
            f"{field}:{part}:{primitive_index}:"
            f"{str(operation or repair_action or 'operation').replace('.', '_')}"
        )
    return {
        "operation_id": str(operation_id),
        "operation": str(operation or ""),
        "repair_action": str(repair_action or ""),
        "field": field,
        "part": part,
        "component": str(record.get("component") or ""),
        "name": str(record.get("name") or ""),
        "primitive_type": str(record.get("primitive_type") or ""),
        "primitive_index": primitive_index,
        "source": str(record.get("source") or ""),
    }


def _semantic_operation_records_from_fields(
    records_by_field: dict[str, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for field_name, field_records in records_by_field.items():
        for record in field_records:
            operation_record = _semantic_operation_record(field_name, record)
            if operation_record is None:
                continue
            key = (
                operation_record["operation_id"],
                operation_record["field"],
                operation_record["part"],
                str(operation_record.get("primitive_index")),
            )
            if key in seen:
                continue
            seen.add(key)
            records.append(operation_record)
    return records


def _dedupe_operation_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for record in records:
        key = (
            str(record.get("operation_id") or ""),
            str(record.get("operation") or record.get("repair_action") or ""),
            str(record.get("part") or ""),
            str(record.get("source") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(dict(record))
    return deduped


def _metadata_operation_record_containers(
    metadata: dict[str, Any],
    candidate: dict[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    containers: list[tuple[str, dict[str, Any]]] = [("mesh_ir.metadata", metadata)]
    index = 0
    while index < len(containers):
        source, container = containers[index]
        index += 1
        for key in ("integration_report", "exact_report"):
            nested = container.get(key)
            if isinstance(nested, dict):
                containers.append((f"{source}.{key}", nested))
    candidate_integration = candidate.get("integration_report")
    if isinstance(candidate_integration, dict):
        containers.append(("shape.selected_candidate.integration_report", candidate_integration))
        nested = candidate_integration.get("exact_report")
        if isinstance(nested, dict):
            containers.append(("shape.selected_candidate.integration_report.exact_report", nested))
    return containers


def _metadata_operation_records(
    metadata: dict[str, Any],
    candidate: dict[str, Any],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for source, container in _metadata_operation_record_containers(metadata, candidate):
        for record in _semantic_records(container, "operation_records"):
            out = dict(record)
            out.setdefault("source", source)
            out.setdefault("metadata_source", source)
            records.append(out)
    return records


def _semantic_record_key(record: dict[str, Any]) -> tuple[str, str, str, str]:
    primitive_index = record.get("primitive_index", "")
    return (
        str(record.get("source") or ""),
        str(record.get("name") or ""),
        str(record.get("part") or ""),
        str(primitive_index),
    )


def _merge_semantic_records(
    primary: list[dict[str, Any]], secondary: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for record in [*primary, *secondary]:
        if not isinstance(record, dict):
            continue
        key = _semantic_record_key(record)
        if key in seen:
            continue
        seen.add(key)
        merged.append(dict(record))
    return merged


def _semantic_name_sequence(records: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for record in records:
        name = str(record.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def _mesh_ir_semantic_handoff(
    shape_bundle: dict[str, Any], mesh_ir: dict[str, Any] | None = None
) -> dict[str, Any]:
    mesh_ir = mesh_ir if isinstance(mesh_ir, dict) else _selected_mesh_ir(shape_bundle)
    if not mesh_ir:
        return {}
    candidate = _selected_candidate(shape_bundle)
    handoff: dict[str, Any] = {
        "source": "shape.selected_candidate.mesh_ir",
        "source_candidate_id": str(candidate.get("candidate_id") or ""),
        "asset_name": str(mesh_ir.get("asset_name") or ""),
        "family": str(mesh_ir.get("family") or ""),
        "face_part_count": len(mesh_ir.get("face_parts", []))
        if isinstance(mesh_ir.get("face_parts"), list)
        else 0,
        "metadata": dict(mesh_ir.get("metadata", {}))
        if isinstance(mesh_ir.get("metadata"), dict)
        else {},
    }
    metadata = handoff["metadata"] if isinstance(handoff["metadata"], dict) else {}
    face_operation_summary = metadata.get("face_operation_summary")
    source_face_operation_summary = metadata.get("source_face_operation_summary")
    face_operation_ids = metadata.get("face_operation_ids")
    if isinstance(face_operation_summary, dict):
        handoff["face_operation_summary"] = dict(face_operation_summary)
    if isinstance(source_face_operation_summary, dict):
        handoff["source_face_operation_summary"] = dict(source_face_operation_summary)
    if isinstance(face_operation_ids, list):
        handoff["face_operation_count"] = len(face_operation_ids)
        handoff["face_operation_unique_count"] = len({str(item) for item in face_operation_ids})
    face_operation_attribution = metadata.get("face_operation_attribution")
    if isinstance(face_operation_attribution, dict):
        handoff["face_operation_attribution"] = dict(face_operation_attribution)
    source_face_operation_attribution = metadata.get("source_face_operation_attribution")
    if isinstance(source_face_operation_attribution, dict):
        handoff["source_face_operation_attribution"] = dict(source_face_operation_attribution)
    kernel_program_handoffs = _semantic_records(metadata, "kernel_program_semantic_handoffs")
    kernel_program_operation_records: list[dict[str, Any]] = []
    if kernel_program_handoffs:
        handoff["kernel_program_semantic_handoffs"] = kernel_program_handoffs
        handoff["kernel_program_semantic_handoff_count"] = len(kernel_program_handoffs)
        for kernel_program_handoff in kernel_program_handoffs:
            kernel_program_operation_records.extend(
                _semantic_records(kernel_program_handoff, "operation_records")
            )
        handoff_summary = metadata.get("kernel_program_semantic_handoff_summary")
        if isinstance(handoff_summary, dict):
            handoff["kernel_program_semantic_handoff_summary"] = dict(handoff_summary)
        else:
            handoff["kernel_program_semantic_handoff_summary"] = {
                "schema": "lathe.mesh_ir.kernel_program_semantic_handoff_summary.v1",
                "handoff_count": len(kernel_program_handoffs),
                "sources": sorted(
                    {
                        str(item.get("source") or "")
                        for item in kernel_program_handoffs
                        if str(item.get("source") or "")
                    }
                ),
                "total_operand_count": sum(
                    _int_value(item.get("operand_count")) for item in kernel_program_handoffs
                ),
                "result_face_counts": [
                    _int_value(item.get("result_face_count"))
                    for item in kernel_program_handoffs
                    if item.get("result_face_count") is not None
                ],
                "source": "shape.selected_candidate.mesh_ir.metadata.kernel_program_semantic_handoffs",
            }
    for key in (
        "kernel_feature_details",
        "kernel_feature_detail_summary",
        "kernel_edge_treatments",
        "kernel_edge_treatment_summary",
        "kernel_pattern_instances",
        "kernel_pattern_instance_summary",
        "kernel_deforms",
        "kernel_deform_summary",
        "kernel_profile_paths",
        "kernel_profile_path_summary",
        "kernel_edge_controls",
        "kernel_edge_control_summary",
        "kernel_component_assemblies",
        "kernel_component_assembly_summary",
        "kernel_sdf_fields",
        "kernel_sdf_field_summary",
        "kernel_terrain_fields",
        "kernel_terrain_field_summary",
        "kernel_scatters",
        "kernel_scatter_summary",
        "kernel_surface_damage",
        "kernel_surface_damage_summary",
        "shape_ir_v2_modifier_records",
        "shape_ir_v2_modifier_summary",
    ):
        value = metadata.get(key)
        if isinstance(value, list):
            handoff[key] = [dict(item) for item in value if isinstance(item, dict)]
        elif isinstance(value, dict):
            handoff[key] = dict(value)
    records_by_field: dict[str, list[dict[str, Any]]] = {}
    for field_name in _MESH_IR_SEMANTIC_FIELDS:
        records_by_field[field_name] = _semantic_records(mesh_ir, field_name)
        handoff[field_name] = records_by_field[field_name]
    modifier_records = _semantic_records(handoff, "shape_ir_v2_modifier_records")
    operation_source_fields = dict(records_by_field)
    if modifier_records:
        operation_source_fields["shape_ir_v2_modifier_records"] = modifier_records
    handoff["operation_records"] = _dedupe_operation_records(
        [
            *_semantic_operation_records_from_fields(operation_source_fields),
            *_metadata_operation_records(metadata, candidate),
            *kernel_program_operation_records,
        ]
    )
    return handoff


def _add_mesh_ir_semantics_to_part_index(
    index: dict[str, dict[str, Any]], mesh_ir: dict[str, Any]
) -> None:
    for field_name in _MESH_IR_SEMANTIC_FIELDS:
        for record in _semantic_records(mesh_ir, field_name):
            part = str(record.get("part") or "").strip()
            if not part:
                continue
            entry = index.setdefault(
                part,
                {"tags": [], "parent_blueprint_component": "", "metadata": {}},
            )
            metadata = entry.setdefault("metadata", {})
            by_field = metadata.setdefault("mesh_ir_semantics", {})
            by_field.setdefault(field_name, []).append(dict(record))
            record_tags = [str(tag) for tag in record.get("tags", []) if str(tag)] if isinstance(record.get("tags"), list) else []
            if record_tags:
                entry["tags"] = sorted(set(entry.get("tags", [])) | set(record_tags))
    handoff = _mesh_ir_semantic_handoff({}, mesh_ir)
    for operation in _semantic_records(handoff, "operation_records"):
        part = str(operation.get("part") or "").strip()
        if not part:
            continue
        entry = index.setdefault(
            part,
            {"tags": [], "parent_blueprint_component": "", "metadata": {}},
        )
        metadata = entry.setdefault("metadata", {})
        metadata.setdefault("operation_semantics", []).append(dict(operation))
    for field_name in _KERNEL_PART_SEMANTIC_FIELDS:
        for record in _semantic_records(handoff, field_name):
            linked_parts = _record_link_parts(record)
            for part in linked_parts:
                entry = index.setdefault(
                    part,
                    {"tags": [], "parent_blueprint_component": "", "metadata": {}},
                )
                metadata = entry.setdefault("metadata", {})
                by_field = metadata.setdefault("kernel_semantics", {})
                by_field.setdefault(field_name, []).append(dict(record))


def semantic_preservation_report(
    topology_semantics: dict[str, Any], part_names: list[str]
) -> dict[str, Any]:
    """Report whether MeshIR semantic records still target emitted parts."""
    emitted_parts = {str(part) for part in part_names if str(part)}
    mesh_ir_semantics = topology_semantics.get("mesh_ir_semantics", {})
    if not isinstance(mesh_ir_semantics, dict):
        mesh_ir_semantics = {}
    fields: dict[str, Any] = {}
    all_preserved = True
    for field_name in _MESH_IR_SEMANTIC_FIELDS:
        records = _semantic_records(mesh_ir_semantics, field_name)
        missing = [
            str(record.get("part") or "")
            for record in records
            if str(record.get("part") or "") and str(record.get("part") or "") not in emitted_parts
        ]
        missing_parts = sorted(set(missing))
        preserved_count = len(records) - len(missing)
        field_preserved = len(missing_parts) == 0
        all_preserved = all_preserved and field_preserved
        fields[field_name] = {
            "source_count": len(records),
            "preserved_count": preserved_count,
            "missing_part_count": len(missing_parts),
            "missing_parts": missing_parts,
            "preserved": field_preserved,
        }
    kernel_fields: dict[str, Any] = {}
    all_kernel_records_preserved = True
    for field_name in _KERNEL_PART_SEMANTIC_FIELDS:
        records = _semantic_records(mesh_ir_semantics, field_name)
        linked_parts: list[str] = []
        missing_parts: list[str] = []
        for record in records:
            for part in _record_link_parts(record):
                linked_parts.append(part)
                if part not in emitted_parts:
                    missing_parts.append(part)
        unique_linked_parts = sorted(set(linked_parts))
        unique_missing_parts = sorted(set(missing_parts))
        field_preserved = not unique_missing_parts
        all_kernel_records_preserved = all_kernel_records_preserved and field_preserved
        kernel_fields[field_name] = {
            "source_count": len(records),
            "linked_part_count": len(unique_linked_parts),
            "linked_parts": unique_linked_parts,
            "missing_part_count": len(unique_missing_parts),
            "missing_parts": unique_missing_parts,
            "preserved": field_preserved,
        }
    operation_records = _semantic_records(mesh_ir_semantics, "operation_records")
    missing_operations = [
        dict(record)
        for record in operation_records
        if str(record.get("part") or "") and str(record.get("part") or "") not in emitted_parts
    ]
    preserved_operations = len(operation_records) - len(missing_operations)
    all_preserved = all_preserved and not missing_operations
    all_preserved = all_preserved and all_kernel_records_preserved
    return {
        "schema": "lathe.topology.semantic_preservation_report.v1",
        "source": "shape.selected_candidate.mesh_ir",
        "emitted_part_count": len(emitted_parts),
        "emitted_parts": sorted(emitted_parts),
        "all_semantics_preserved": all_preserved,
        "fields": fields,
        "kernel_records": {
            "fields": kernel_fields,
            "all_kernel_records_preserved": all_kernel_records_preserved,
        },
        "operation_records": {
            "source_count": len(operation_records),
            "preserved_count": preserved_operations,
            "missing_count": len(missing_operations),
            "preserved_operation_ids": [
                str(record.get("operation_id"))
                for record in operation_records
                if record not in missing_operations
            ],
            "missing_operations": missing_operations,
            "preserved": not missing_operations,
        },
    }


def derive_topology_semantics(shape_bundle: dict[str, Any]) -> dict[str, Any]:
    mesh_ir = _selected_mesh_ir(shape_bundle)
    mesh_seam_classes = _semantic_records(mesh_ir, "seam_classes")
    mesh_hard_edge_classes = _semantic_records(mesh_ir, "hard_edge_classes")
    mesh_bake_groups = _semantic_records(mesh_ir, "bake_groups")
    mesh_material_zones = _semantic_records(mesh_ir, "material_zones")
    mesh_ir_semantics = _mesh_ir_semantic_handoff(shape_bundle, mesh_ir)
    shape_ir = shape_bundle.get("shape_ir", [])
    if not shape_ir:
        return {
            "hard_edge_groups": list(mesh_hard_edge_classes),
            "panel_seams": _semantic_name_sequence(mesh_seam_classes),
            "bake_groups": list(mesh_bake_groups),
            "feature_semantics": {},
            "seam_classes": list(mesh_seam_classes),
            "hard_edge_classes": list(mesh_hard_edge_classes),
            "material_zones": list(mesh_material_zones),
            "mesh_ir_semantics": mesh_ir_semantics,
            "operation_records": _semantic_records(mesh_ir_semantics, "operation_records"),
            "kernel_feature_details": _semantic_records(mesh_ir_semantics, "kernel_feature_details"),
            "kernel_feature_detail_summary": dict(mesh_ir_semantics.get("kernel_feature_detail_summary", {}))
            if isinstance(mesh_ir_semantics.get("kernel_feature_detail_summary"), dict)
            else {},
            "kernel_edge_treatments": _semantic_records(mesh_ir_semantics, "kernel_edge_treatments"),
            "kernel_edge_treatment_summary": dict(mesh_ir_semantics.get("kernel_edge_treatment_summary", {}))
            if isinstance(mesh_ir_semantics.get("kernel_edge_treatment_summary"), dict)
            else {},
            "kernel_pattern_instances": _semantic_records(mesh_ir_semantics, "kernel_pattern_instances"),
            "kernel_pattern_instance_summary": dict(mesh_ir_semantics.get("kernel_pattern_instance_summary", {}))
            if isinstance(mesh_ir_semantics.get("kernel_pattern_instance_summary"), dict)
            else {},
            "kernel_deforms": _semantic_records(mesh_ir_semantics, "kernel_deforms"),
            "kernel_deform_summary": dict(mesh_ir_semantics.get("kernel_deform_summary", {}))
            if isinstance(mesh_ir_semantics.get("kernel_deform_summary"), dict)
            else {},
            "kernel_profile_paths": _semantic_records(mesh_ir_semantics, "kernel_profile_paths"),
            "kernel_profile_path_summary": dict(mesh_ir_semantics.get("kernel_profile_path_summary", {}))
            if isinstance(mesh_ir_semantics.get("kernel_profile_path_summary"), dict)
            else {},
            "kernel_edge_controls": _semantic_records(mesh_ir_semantics, "kernel_edge_controls"),
            "kernel_edge_control_summary": dict(mesh_ir_semantics.get("kernel_edge_control_summary", {}))
            if isinstance(mesh_ir_semantics.get("kernel_edge_control_summary"), dict)
            else {},
            "kernel_component_assemblies": _semantic_records(mesh_ir_semantics, "kernel_component_assemblies"),
            "kernel_component_assembly_summary": dict(mesh_ir_semantics.get("kernel_component_assembly_summary", {}))
            if isinstance(mesh_ir_semantics.get("kernel_component_assembly_summary"), dict)
            else {},
            "kernel_sdf_fields": _semantic_records(mesh_ir_semantics, "kernel_sdf_fields"),
            "kernel_sdf_field_summary": dict(mesh_ir_semantics.get("kernel_sdf_field_summary", {}))
            if isinstance(mesh_ir_semantics.get("kernel_sdf_field_summary"), dict)
            else {},
            "kernel_terrain_fields": _semantic_records(mesh_ir_semantics, "kernel_terrain_fields"),
            "kernel_terrain_field_summary": dict(mesh_ir_semantics.get("kernel_terrain_field_summary", {}))
            if isinstance(mesh_ir_semantics.get("kernel_terrain_field_summary"), dict)
            else {},
            "kernel_scatters": _semantic_records(mesh_ir_semantics, "kernel_scatters"),
            "kernel_scatter_summary": dict(mesh_ir_semantics.get("kernel_scatter_summary", {}))
            if isinstance(mesh_ir_semantics.get("kernel_scatter_summary"), dict)
            else {},
            "kernel_surface_damage": _semantic_records(mesh_ir_semantics, "kernel_surface_damage"),
            "kernel_surface_damage_summary": dict(mesh_ir_semantics.get("kernel_surface_damage_summary", {}))
            if isinstance(mesh_ir_semantics.get("kernel_surface_damage_summary"), dict)
            else {},
            "shape_ir_v2_modifier_records": _semantic_records(
                mesh_ir_semantics, "shape_ir_v2_modifier_records"
            ),
            "shape_ir_v2_modifier_summary": dict(
                mesh_ir_semantics.get("shape_ir_v2_modifier_summary", {})
            )
            if isinstance(mesh_ir_semantics.get("shape_ir_v2_modifier_summary"), dict)
            else {},
            "face_operation_summary": dict(mesh_ir_semantics.get("face_operation_summary", {}))
            if isinstance(mesh_ir_semantics.get("face_operation_summary"), dict)
            else {},
            "source_face_operation_summary": dict(
                mesh_ir_semantics.get("source_face_operation_summary", {})
            )
            if isinstance(mesh_ir_semantics.get("source_face_operation_summary"), dict)
            else {},
            "face_operation_count": _int_value(mesh_ir_semantics.get("face_operation_count")),
            "face_operation_unique_count": _int_value(
                mesh_ir_semantics.get("face_operation_unique_count")
            ),
            "face_operation_attribution": dict(
                mesh_ir_semantics.get("face_operation_attribution", {})
            )
            if isinstance(mesh_ir_semantics.get("face_operation_attribution"), dict)
            else {},
            "source_face_operation_attribution": dict(
                mesh_ir_semantics.get("source_face_operation_attribution", {})
            )
            if isinstance(mesh_ir_semantics.get("source_face_operation_attribution"), dict)
            else {},
            "kernel_program_semantic_handoffs": _semantic_records(
                mesh_ir_semantics, "kernel_program_semantic_handoffs"
            ),
            "kernel_program_semantic_handoff_count": _int_value(
                mesh_ir_semantics.get("kernel_program_semantic_handoff_count")
            ),
            "kernel_program_semantic_handoff_summary": dict(
                mesh_ir_semantics.get("kernel_program_semantic_handoff_summary", {})
            )
            if isinstance(mesh_ir_semantics.get("kernel_program_semantic_handoff_summary"), dict)
            else {},
            "generated_uv_semantics": _exact_generated_uv_semantics(shape_bundle),
        }
    primary = shape_ir[0]
    regions = primary.get("regions", [])
    panel_seams = [
        region["name"]
        for region in regions
        if region.get("component") in {"panel", "frame", "bezel", "door", "lid"}
    ]
    hard_edge_groups = [
        {
            "name": region["name"],
            "part": region["part"],
            "edge_class": "hard_surface_feature"
            if region.get("component") not in {"vent", "grille"}
            else "grille",
        }
        for region in regions
    ]
    bake_groups = [
        {
            "name": region["name"],
            "part": region["part"],
            "material_boundary": region.get("component")
            in {"panel", "bezel", "screen_bezel", "lock_plate", "socket_plate"},
        }
        for region in regions
    ]
    seam_names = list(dict.fromkeys([*panel_seams, *_semantic_name_sequence(mesh_seam_classes)]))
    return {
        "hard_edge_groups": _merge_semantic_records(hard_edge_groups, mesh_hard_edge_classes),
        "panel_seams": seam_names,
        "bake_groups": _merge_semantic_records(bake_groups, mesh_bake_groups),
        "feature_semantics": shape_bundle.get("shape_assessment", {}),
        "seam_classes": list(mesh_seam_classes),
        "hard_edge_classes": list(mesh_hard_edge_classes),
        "material_zones": list(mesh_material_zones),
        "mesh_ir_semantics": mesh_ir_semantics,
        "operation_records": _semantic_records(mesh_ir_semantics, "operation_records"),
        "kernel_feature_details": _semantic_records(mesh_ir_semantics, "kernel_feature_details"),
        "kernel_feature_detail_summary": dict(mesh_ir_semantics.get("kernel_feature_detail_summary", {}))
        if isinstance(mesh_ir_semantics.get("kernel_feature_detail_summary"), dict)
        else {},
        "kernel_edge_treatments": _semantic_records(mesh_ir_semantics, "kernel_edge_treatments"),
        "kernel_edge_treatment_summary": dict(mesh_ir_semantics.get("kernel_edge_treatment_summary", {}))
        if isinstance(mesh_ir_semantics.get("kernel_edge_treatment_summary"), dict)
        else {},
        "kernel_pattern_instances": _semantic_records(mesh_ir_semantics, "kernel_pattern_instances"),
        "kernel_pattern_instance_summary": dict(mesh_ir_semantics.get("kernel_pattern_instance_summary", {}))
        if isinstance(mesh_ir_semantics.get("kernel_pattern_instance_summary"), dict)
        else {},
        "kernel_deforms": _semantic_records(mesh_ir_semantics, "kernel_deforms"),
        "kernel_deform_summary": dict(mesh_ir_semantics.get("kernel_deform_summary", {}))
        if isinstance(mesh_ir_semantics.get("kernel_deform_summary"), dict)
        else {},
        "kernel_profile_paths": _semantic_records(mesh_ir_semantics, "kernel_profile_paths"),
        "kernel_profile_path_summary": dict(mesh_ir_semantics.get("kernel_profile_path_summary", {}))
        if isinstance(mesh_ir_semantics.get("kernel_profile_path_summary"), dict)
        else {},
        "kernel_edge_controls": _semantic_records(mesh_ir_semantics, "kernel_edge_controls"),
        "kernel_edge_control_summary": dict(mesh_ir_semantics.get("kernel_edge_control_summary", {}))
        if isinstance(mesh_ir_semantics.get("kernel_edge_control_summary"), dict)
        else {},
        "kernel_component_assemblies": _semantic_records(mesh_ir_semantics, "kernel_component_assemblies"),
        "kernel_component_assembly_summary": dict(mesh_ir_semantics.get("kernel_component_assembly_summary", {}))
        if isinstance(mesh_ir_semantics.get("kernel_component_assembly_summary"), dict)
        else {},
        "kernel_sdf_fields": _semantic_records(mesh_ir_semantics, "kernel_sdf_fields"),
        "kernel_sdf_field_summary": dict(mesh_ir_semantics.get("kernel_sdf_field_summary", {}))
        if isinstance(mesh_ir_semantics.get("kernel_sdf_field_summary"), dict)
        else {},
        "kernel_terrain_fields": _semantic_records(mesh_ir_semantics, "kernel_terrain_fields"),
        "kernel_terrain_field_summary": dict(mesh_ir_semantics.get("kernel_terrain_field_summary", {}))
        if isinstance(mesh_ir_semantics.get("kernel_terrain_field_summary"), dict)
        else {},
        "kernel_scatters": _semantic_records(mesh_ir_semantics, "kernel_scatters"),
        "kernel_scatter_summary": dict(mesh_ir_semantics.get("kernel_scatter_summary", {}))
        if isinstance(mesh_ir_semantics.get("kernel_scatter_summary"), dict)
        else {},
        "kernel_surface_damage": _semantic_records(mesh_ir_semantics, "kernel_surface_damage"),
        "kernel_surface_damage_summary": dict(mesh_ir_semantics.get("kernel_surface_damage_summary", {}))
        if isinstance(mesh_ir_semantics.get("kernel_surface_damage_summary"), dict)
        else {},
        "shape_ir_v2_modifier_records": _semantic_records(
            mesh_ir_semantics, "shape_ir_v2_modifier_records"
        ),
        "shape_ir_v2_modifier_summary": dict(
            mesh_ir_semantics.get("shape_ir_v2_modifier_summary", {})
        )
        if isinstance(mesh_ir_semantics.get("shape_ir_v2_modifier_summary"), dict)
        else {},
        "face_operation_summary": dict(mesh_ir_semantics.get("face_operation_summary", {}))
        if isinstance(mesh_ir_semantics.get("face_operation_summary"), dict)
        else {},
        "source_face_operation_summary": dict(
            mesh_ir_semantics.get("source_face_operation_summary", {})
        )
        if isinstance(mesh_ir_semantics.get("source_face_operation_summary"), dict)
        else {},
        "face_operation_count": _int_value(mesh_ir_semantics.get("face_operation_count")),
        "face_operation_unique_count": _int_value(
            mesh_ir_semantics.get("face_operation_unique_count")
        ),
        "face_operation_attribution": dict(mesh_ir_semantics.get("face_operation_attribution", {}))
        if isinstance(mesh_ir_semantics.get("face_operation_attribution"), dict)
        else {},
        "source_face_operation_attribution": dict(
            mesh_ir_semantics.get("source_face_operation_attribution", {})
        )
        if isinstance(mesh_ir_semantics.get("source_face_operation_attribution"), dict)
        else {},
        "kernel_program_semantic_handoffs": _semantic_records(
            mesh_ir_semantics, "kernel_program_semantic_handoffs"
        ),
        "kernel_program_semantic_handoff_count": _int_value(
            mesh_ir_semantics.get("kernel_program_semantic_handoff_count")
        ),
        "kernel_program_semantic_handoff_summary": dict(
            mesh_ir_semantics.get("kernel_program_semantic_handoff_summary", {})
        )
        if isinstance(mesh_ir_semantics.get("kernel_program_semantic_handoff_summary"), dict)
        else {},
        "generated_uv_semantics": _exact_generated_uv_semantics(shape_bundle),
    }


@dataclass
class PartManifest:
    """One entry per scene part. Parallel to ``scene.geometry`` insertion order."""

    name: str
    face_count: int
    vertex_count: int
    tags: list[str] = field(default_factory=list)
    parent_blueprint_component: str = ""
    transform: list[list[float]] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    bounds_min: list[float] | None = None
    bounds_max: list[float] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "face_count": int(self.face_count),
            "vertex_count": int(self.vertex_count),
            "tags": list(self.tags),
            "parent_blueprint_component": self.parent_blueprint_component,
            "transform": self.transform,
            "metadata": dict(self.metadata),
            "bounds_min": list(self.bounds_min) if self.bounds_min is not None else None,
            "bounds_max": list(self.bounds_max) if self.bounds_max is not None else None,
        }


@dataclass
class MultiPartScene:
    """Multi-part topology output: a trimesh Scene + a parallel manifest.

    See module docstring for the contract. Use :meth:`flatten_to_single_mesh`
    to produce a legacy single-Trimesh view for tools that don't yet know
    about parts. Both views must round-trip through GLB without losing the
    part_name -> geometry mapping.
    """

    scene: trimesh.Scene
    manifest: list[PartManifest]
    units: str = "cm"

    def part_names(self) -> list[str]:
        return [p.name for p in self.manifest]

    def total_face_count(self) -> int:
        return int(sum(p.face_count for p in self.manifest))

    def total_vertex_count(self) -> int:
        return int(sum(p.vertex_count for p in self.manifest))

    def manifest_as_list(self) -> list[dict[str, Any]]:
        return [p.as_dict() for p in self.manifest]

    def flatten_to_single_mesh(self) -> tuple[trimesh.Trimesh, list[str]]:
        """Concatenate all parts into one Trimesh and return parallel face_parts.

        Returned ``face_parts`` is a flat list, one entry per face of the
        concatenated mesh, naming the source part. Use this for legacy
        single-mesh consumers that still want per-face part labels.
        """
        meshes: list[trimesh.Trimesh] = []
        face_parts: list[str] = []
        for part in self.manifest:
            geom = self.scene.geometry.get(part.name)
            if not isinstance(geom, trimesh.Trimesh):
                continue
            meshes.append(geom)
            face_parts.extend([part.name] * len(geom.faces))
        if not meshes:
            empty = trimesh.Trimesh(process=False)
            return empty, []
        if len(meshes) == 1:
            single = meshes[0].copy()
            single.merge_vertices()
            return single, list(face_parts)
        # Weld each part's submesh in isolation so duplicate vertices
        # within a single component collapse, but do NOT weld across
        # part boundaries. Welding the fused multi-part mesh would
        # collapse vertices where two parts meet (e.g. body bottom face
        # vs foot top face) into a single averaged-normal vertex,
        # flattening shading and bake outputs at every seam.
        welded_meshes: list[trimesh.Trimesh] = []
        for sub in meshes:
            sub_copy = sub.copy()
            sub_copy.merge_vertices()
            welded_meshes.append(sub_copy)
        fused = trimesh.util.concatenate(welded_meshes)
        return fused, face_parts


def export_multi_part_scene_glb(scene: MultiPartScene, path: Any) -> None:
    """Export the multi-part scene as a GLB with per-part geometry nodes.

    GLB preserves the ``scene.geometry`` dict keys as named nodes, so a
    downstream ``trimesh.load(path, force='scene')`` round-trips the part
    structure intact.
    """
    from pathlib import Path as _Path

    target = _Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(scene.scene.export(file_type="glb"))


def load_multi_part_scene_glb(path: Any, units: str = "cm") -> MultiPartScene | None:
    """Load a multi-part scene GLB written by :func:`export_multi_part_scene_glb`.

    Returns ``None`` if the file fails to parse or contains no Trimesh
    geometries. Tags / parent_component metadata are not embedded in the GLB
    itself; callers that need them should pair this loader with the
    ``parts`` array from ``bundle.json``.
    """
    try:
        loaded = trimesh.load(path, force="scene")
    except (OSError, ValueError, KeyError, AttributeError, TypeError):
        return None
    if not isinstance(loaded, trimesh.Scene):
        if isinstance(loaded, trimesh.Trimesh):
            scene = trimesh.Scene()
            scene.add_geometry(loaded, geom_name="mesh", node_name="mesh")
            manifest = [
                PartManifest(
                    name="mesh",
                    face_count=len(loaded.faces),
                    vertex_count=len(loaded.vertices),
                )
            ]
            return MultiPartScene(scene=scene, manifest=manifest, units=units)
        return None
    new_scene = trimesh.Scene()
    manifest: list[PartManifest] = []
    for name, geom in loaded.geometry.items():
        if not isinstance(geom, trimesh.Trimesh):
            continue
        new_scene.add_geometry(geom, geom_name=name, node_name=name)
        manifest.append(
            PartManifest(
                name=str(name),
                face_count=len(geom.faces),
                vertex_count=len(geom.vertices),
            )
        )
    if not manifest:
        return None
    return MultiPartScene(scene=new_scene, manifest=manifest, units=units)


def build_part_tag_index(shape_bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Build ``{part_name: {tags, parent_blueprint_component}}`` from shape bundle.

    Walks the resolved components stored on ``assembly_ir`` so each part name
    can be enriched with its blueprint tags (``plank_displacement``,
    ``oak_planks``, container/chest/lid/door/etc.) and the source component
    name. Returns an empty dict if no resolved components are reachable.
    """
    index: dict[str, dict[str, Any]] = {}

    asset_graph = shape_bundle.get("asset_graph")
    parts_iter: list[Any] = []
    if asset_graph is not None:
        if hasattr(asset_graph, "parts"):
            parts_iter = list(asset_graph.parts or [])
        elif isinstance(asset_graph, dict):
            parts_iter = list(asset_graph.get("parts") or [])

    for part in parts_iter:
        if hasattr(part, "name"):
            name = str(getattr(part, "name", "") or "")
            tags = list(getattr(part, "tags", []) or [])
        elif isinstance(part, dict):
            name = str(part.get("name", "") or "")
            tags = list(part.get("tags", []) or [])
        else:
            continue
        if not name:
            continue
        index.setdefault(name, {"tags": [], "parent_blueprint_component": "", "metadata": {}})
        index[name]["tags"] = sorted(set(index[name]["tags"]) | set(str(t) for t in tags))

    assembly_ir = shape_bundle.get("assembly_ir") or {}
    resolved_components = []
    if isinstance(assembly_ir, dict):
        resolved_components = list(assembly_ir.get("resolved_components") or [])

    for component in resolved_components:
        if not isinstance(component, dict):
            continue
        values = component.get("values", {}) if isinstance(component.get("values"), dict) else {}
        part_name = str(values.get("part") or component.get("name") or "")
        if not part_name:
            continue
        component_name = str(component.get("name") or values.get("component_name") or "")
        component_tags = list(values.get("tags") or [])
        entry = index.setdefault(
            part_name,
            {"tags": [], "parent_blueprint_component": "", "metadata": {}},
        )
        entry["tags"] = sorted(set(entry["tags"]) | set(str(t) for t in component_tags))
        if component_name and not entry.get("parent_blueprint_component"):
            entry["parent_blueprint_component"] = component_name

    _add_mesh_ir_semantics_to_part_index(index, _selected_mesh_ir(shape_bundle))
    return index


def manifest_from_part_index(
    part_names: list[str],
    face_counts: list[int],
    vertex_counts: list[int],
    part_index: dict[str, dict[str, Any]],
) -> list[PartManifest]:
    """Combine part names + face/vertex counts + tag index into a manifest list."""
    manifest: list[PartManifest] = []
    for name, faces, verts in zip(part_names, face_counts, vertex_counts, strict=False):
        info = part_index.get(name, {})
        manifest.append(
            PartManifest(
                name=name,
                face_count=int(faces),
                vertex_count=int(verts),
                tags=list(info.get("tags") or []),
                parent_blueprint_component=str(info.get("parent_blueprint_component") or ""),
                transform=None,
                metadata=dict(info.get("metadata") or {}),
            )
        )
    return manifest


def should_preserve_integrated_shape(
    shape_bundle: dict[str, Any], runtime_config: dict[str, Any] | None = None
) -> bool:
    topology_cfg = (runtime_config or {}).get("topology", {})
    if topology_cfg.get("adapter") not in {None, "", "auto"}:
        return False
    candidate = _selected_candidate(shape_bundle)
    if not candidate:
        return False
    integration = candidate.get("integration_report", {})
    mode = integration.get("mode")
    exact_report = integration.get("exact_report") if isinstance(integration, dict) else None
    if mode in {
        "mesh_program_explicit_surface",
        "procedural_synthesizer_explicit_surface",
    } and isinstance(exact_report, dict):
        mode = exact_report.get("mode") or mode
    if mode in {"sdf_voxel_fusion", "exact_component_assembly", "exact_part_preserving_union"}:
        return True
    if mode in {
        "exact_boolean_union",
        "exact_boolean_union_clustered",
        "exact_boolean_difference",
        "exact_boolean_intersection",
        "exact_boolean_mixed",
        "exact_boolean_kernel_program",
        "exact_boolean_manifold_kernel",
        "exact_boolean_manifold_kernel_after_local_failure",
        "exact_kernel_program_single_body_import",
    }:
        return bool((candidate.get("mesh_stats") or {}).get("watertight"))
    return False
