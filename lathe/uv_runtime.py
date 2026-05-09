from __future__ import annotations

from typing import Any


def _dict_records(value: Any) -> list[dict[str, Any]]:
    return [dict(record) for record in value if isinstance(record, dict)] if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in value if str(item)] if isinstance(value, list) else []


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


_PART_LINK_KEYS = (
    "part",
    "source_part",
    "target_part",
    "template_part",
    "component_part",
    "result_part",
    "primary_part",
    "assembly_part",
    "linked_part",
)
_PART_LINK_LIST_KEYS = (
    "parts",
    "source_parts",
    "target_parts",
    "template_parts",
    "component_parts",
    "assembly_parts",
    "source_context_parts",
)
_NESTED_PART_LINK_FIELDS = (
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
            for key in _PART_LINK_KEYS:
                add(value.get(key))
            for key in _PART_LINK_LIST_KEYS:
                items = value.get(key)
                if isinstance(items, (list, tuple, set)):
                    for item in items:
                        add(item)
            for field in _NESTED_PART_LINK_FIELDS:
                nested = value.get(field)
                if nested is not None:
                    walk(nested, depth + 1)
            return
        if isinstance(value, list):
            for item in value:
                walk(item, depth + 1)

    walk(record)
    return parts


def _records_by_part(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_part: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        for part in _record_link_parts(record):
            item = dict(record)
            item.setdefault("part", part)
            item.setdefault("linked_part", part)
            by_part.setdefault(part, []).append(item)
    return by_part


def _compact_records(records: list[dict[str, Any]], *, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    seen: set[tuple[tuple[str, str], ...]] = set()
    for record in records:
        item = {key: str(record.get(key) or "") for key in keys if str(record.get(key) or "")}
        if not item:
            continue
        dedupe_key = tuple(sorted(item.items()))
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        compact.append(item)
    return compact


_KERNEL_SEMANTIC_LINKS: dict[str, tuple[str, ...]] = {
    "kernel_feature_details": (
        "operation",
        "actual_operation",
        "feature_kind",
        "method",
        "actual_method",
        "part",
        "source_part",
        "linked_part",
        "fallback",
        "actual_backend",
        "actual_geometry_backend",
        "result_face_count",
        "result_vertex_count",
    ),
    "kernel_edge_treatments": (
        "operation",
        "actual_operation",
        "treatment_kind",
        "method",
        "part",
        "source_part",
        "linked_part",
        "fallback",
        "actual_backend",
    ),
    "kernel_surface_damage": (
        "operation",
        "actual_operation",
        "damage_kind",
        "method",
        "part",
        "source_part",
        "linked_part",
        "fallback",
        "actual_backend",
    ),
    "kernel_pattern_instances": (
        "operation",
        "actual_operation",
        "pattern_kind",
        "method",
        "part",
        "source_part",
        "target_part",
        "linked_part",
        "fallback",
        "instance_count",
        "actual_backend",
    ),
    "kernel_scatters": (
        "operation",
        "actual_operation",
        "scatter_kind",
        "method",
        "part",
        "source_part",
        "target_part",
        "linked_part",
        "fallback",
        "instance_count",
        "actual_backend",
    ),
    "kernel_edge_controls": (
        "operation",
        "actual_operation",
        "edge_control_kind",
        "method",
        "part",
        "source_part",
        "linked_part",
        "fallback",
        "actual_backend",
    ),
    "kernel_deforms": (
        "operation",
        "actual_operation",
        "deform_kind",
        "axis",
        "method",
        "part",
        "source_part",
        "linked_part",
        "fallback",
        "actual_backend",
    ),
    "kernel_profile_paths": (
        "operation",
        "actual_operation",
        "profile_kind",
        "method",
        "part",
        "source_part",
        "linked_part",
        "fallback",
        "actual_backend",
    ),
    "kernel_component_assemblies": (
        "operation",
        "actual_operation",
        "assembly_kind",
        "method",
        "part",
        "source_part",
        "linked_part",
        "fallback",
        "actual_backend",
    ),
    "kernel_sdf_fields": (
        "operation",
        "actual_operation",
        "field_kind",
        "method",
        "part",
        "source_part",
        "linked_part",
        "fallback",
        "actual_backend",
    ),
    "kernel_terrain_fields": (
        "operation",
        "actual_operation",
        "terrain_kind",
        "method",
        "part",
        "source_part",
        "linked_part",
        "fallback",
        "actual_backend",
    ),
    "kernel_program_semantic_handoffs": (
        "source",
        "route",
        "program_kind",
        "operation",
        "part",
        "source_part",
        "linked_part",
        "result_face_count",
        "result_body_count",
    ),
}


def enrich_chart_manifest_with_semantics(
    chart_manifest: list[dict[str, Any]], uv_semantics: dict[str, Any]
) -> list[dict[str, Any]]:
    """Attach compact topology/kernel semantics to UV charts by part name."""
    material_by_part = _records_by_part(_dict_records(uv_semantics.get("material_zones")))
    seam_by_part = _records_by_part(_dict_records(uv_semantics.get("seam_classes")))
    hard_edge_by_part = _records_by_part(_dict_records(uv_semantics.get("hard_edge_classes")))
    operations_by_part = _records_by_part(_dict_records(uv_semantics.get("operation_records")))
    kernel_by_field = {
        field: _records_by_part(_dict_records(uv_semantics.get(field)))
        for field in _KERNEL_SEMANTIC_LINKS
    }
    enriched: list[dict[str, Any]] = []
    for chart in chart_manifest:
        if not isinstance(chart, dict):
            continue
        out = dict(chart)
        parts = [str(part) for part in out.get("parts", []) if str(part)] if isinstance(out.get("parts"), list) else []
        semantic_links: dict[str, Any] = {
            "schema": "lathe.uv.chart_semantic_links.v1",
            "source": "uv_semantics.part_records",
            "parts": parts,
        }
        material_records: list[dict[str, Any]] = []
        seam_records: list[dict[str, Any]] = []
        hard_edge_records: list[dict[str, Any]] = []
        operation_records: list[dict[str, Any]] = []
        kernel_records_by_field: dict[str, list[dict[str, Any]]] = {
            field: [] for field in _KERNEL_SEMANTIC_LINKS
        }
        for part in parts:
            material_records.extend(material_by_part.get(part, []))
            seam_records.extend(seam_by_part.get(part, []))
            hard_edge_records.extend(hard_edge_by_part.get(part, []))
            operation_records.extend(operations_by_part.get(part, []))
            for field, records_by_part in kernel_by_field.items():
                kernel_records_by_field[field].extend(records_by_part.get(part, []))
        semantic_links["material_zones"] = _compact_records(
            material_records,
            keys=("name", "part", "material_hint", "source"),
        )
        semantic_links["seam_classes"] = _compact_records(
            seam_records,
            keys=("name", "part", "operation", "source"),
        )
        semantic_links["hard_edge_classes"] = _compact_records(
            hard_edge_records,
            keys=("name", "part", "edge_class", "source"),
        )
        compact_operations = _compact_records(
            operation_records,
            keys=("operation_id", "operation", "repair_action", "field", "part", "source"),
        )
        semantic_links["operation_records"] = compact_operations
        semantic_links["operation_ids"] = [
            str(record.get("operation_id"))
            for record in compact_operations
            if str(record.get("operation_id") or "")
        ]
        semantic_links["operations"] = sorted(
            {
                str(record.get("operation"))
                for record in compact_operations
                if str(record.get("operation") or "")
            }
        )
        kernel_record_count = 0
        kernel_operations: set[str] = set()
        for field, keys in _KERNEL_SEMANTIC_LINKS.items():
            compact_kernel_records = _compact_records(kernel_records_by_field[field], keys=keys)
            semantic_links[field] = compact_kernel_records
            kernel_record_count += len(compact_kernel_records)
            kernel_operations.update(
                str(record.get("operation") or "")
                for record in compact_kernel_records
                if str(record.get("operation") or "")
            )
        semantic_links["kernel_record_count"] = kernel_record_count
        semantic_links["kernel_operations"] = sorted(kernel_operations)
        semantic_links["has_kernel_semantics"] = any(
            (
                semantic_links["material_zones"],
                semantic_links["seam_classes"],
                semantic_links["hard_edge_classes"],
                semantic_links["operation_records"],
                kernel_record_count,
            )
        )
        out["semantic_links"] = semantic_links
        enriched.append(out)
    return enriched


def derive_uv_semantics(topology_bundle: dict[str, Any], shape_bundle: dict[str, Any]) -> dict[str, Any]:
    topology_semantics = topology_bundle.get("feature_semantics", {})
    bake_groups = _dict_records(topology_bundle.get("bake_groups"))
    if not bake_groups and isinstance(topology_semantics, dict):
        bake_groups = _dict_records(topology_semantics.get("bake_groups"))
    panel_seams = _string_list(topology_bundle.get("panel_seams"))
    if not panel_seams and isinstance(topology_semantics, dict):
        panel_seams = _string_list(topology_semantics.get("panel_seams"))
    material_boundaries = [
        str(group.get("name") or group.get("part") or "")
        for group in bake_groups
        if group.get("material_boundary") and str(group.get("name") or group.get("part") or "")
    ]
    generated_uv_semantics = topology_bundle.get("generated_uv_semantics", {})
    generated_uv_atlas_hints = (
        dict(generated_uv_semantics) if isinstance(generated_uv_semantics, dict) else {}
    )
    return {
        "seam_guides": panel_seams,
        "bake_groups": bake_groups,
        "material_boundaries": material_boundaries,
        "lightmap_ready": bool(topology_bundle.get("panel_seams")),
        "feature_semantics": shape_bundle.get("shape_assessment", {}),
        "seam_classes": _dict_records(topology_bundle.get("seam_classes")),
        "hard_edge_classes": _dict_records(topology_bundle.get("hard_edge_classes")),
        "material_zones": _dict_records(topology_bundle.get("material_zones")),
        "mesh_ir_semantics": dict(topology_bundle.get("mesh_ir_semantics", {}))
        if isinstance(topology_bundle.get("mesh_ir_semantics"), dict)
        else {},
        "operation_records": _dict_records(topology_bundle.get("operation_records")),
        "kernel_feature_details": _dict_records(topology_bundle.get("kernel_feature_details")),
        "kernel_feature_detail_summary": dict(topology_bundle.get("kernel_feature_detail_summary", {}))
        if isinstance(topology_bundle.get("kernel_feature_detail_summary"), dict)
        else {},
        "kernel_edge_treatments": _dict_records(topology_bundle.get("kernel_edge_treatments")),
        "kernel_edge_treatment_summary": dict(topology_bundle.get("kernel_edge_treatment_summary", {}))
        if isinstance(topology_bundle.get("kernel_edge_treatment_summary"), dict)
        else {},
        "kernel_pattern_instances": _dict_records(topology_bundle.get("kernel_pattern_instances")),
        "kernel_pattern_instance_summary": dict(topology_bundle.get("kernel_pattern_instance_summary", {}))
        if isinstance(topology_bundle.get("kernel_pattern_instance_summary"), dict)
        else {},
        "kernel_deforms": _dict_records(topology_bundle.get("kernel_deforms")),
        "kernel_deform_summary": dict(topology_bundle.get("kernel_deform_summary", {}))
        if isinstance(topology_bundle.get("kernel_deform_summary"), dict)
        else {},
        "kernel_profile_paths": _dict_records(topology_bundle.get("kernel_profile_paths")),
        "kernel_profile_path_summary": dict(topology_bundle.get("kernel_profile_path_summary", {}))
        if isinstance(topology_bundle.get("kernel_profile_path_summary"), dict)
        else {},
        "kernel_edge_controls": _dict_records(topology_bundle.get("kernel_edge_controls")),
        "kernel_edge_control_summary": dict(topology_bundle.get("kernel_edge_control_summary", {}))
        if isinstance(topology_bundle.get("kernel_edge_control_summary"), dict)
        else {},
        "kernel_component_assemblies": _dict_records(topology_bundle.get("kernel_component_assemblies")),
        "kernel_component_assembly_summary": dict(topology_bundle.get("kernel_component_assembly_summary", {}))
        if isinstance(topology_bundle.get("kernel_component_assembly_summary"), dict)
        else {},
        "kernel_sdf_fields": _dict_records(topology_bundle.get("kernel_sdf_fields")),
        "kernel_sdf_field_summary": dict(topology_bundle.get("kernel_sdf_field_summary", {}))
        if isinstance(topology_bundle.get("kernel_sdf_field_summary"), dict)
        else {},
        "kernel_terrain_fields": _dict_records(topology_bundle.get("kernel_terrain_fields")),
        "kernel_terrain_field_summary": dict(topology_bundle.get("kernel_terrain_field_summary", {}))
        if isinstance(topology_bundle.get("kernel_terrain_field_summary"), dict)
        else {},
        "kernel_scatters": _dict_records(topology_bundle.get("kernel_scatters")),
        "kernel_scatter_summary": dict(topology_bundle.get("kernel_scatter_summary", {}))
        if isinstance(topology_bundle.get("kernel_scatter_summary"), dict)
        else {},
        "kernel_surface_damage": _dict_records(topology_bundle.get("kernel_surface_damage")),
        "kernel_surface_damage_summary": dict(topology_bundle.get("kernel_surface_damage_summary", {}))
        if isinstance(topology_bundle.get("kernel_surface_damage_summary"), dict)
        else {},
        "face_operation_summary": dict(topology_bundle.get("face_operation_summary", {}))
        if isinstance(topology_bundle.get("face_operation_summary"), dict)
        else {},
        "source_face_operation_summary": dict(
            topology_bundle.get("source_face_operation_summary", {})
        )
        if isinstance(topology_bundle.get("source_face_operation_summary"), dict)
        else {},
        "face_operation_count": _int_value(topology_bundle.get("face_operation_count")),
        "face_operation_unique_count": _int_value(
            topology_bundle.get("face_operation_unique_count")
        ),
        "face_operation_attribution": dict(topology_bundle.get("face_operation_attribution", {}))
        if isinstance(topology_bundle.get("face_operation_attribution"), dict)
        else {},
        "source_face_operation_attribution": dict(
            topology_bundle.get("source_face_operation_attribution", {})
        )
        if isinstance(topology_bundle.get("source_face_operation_attribution"), dict)
        else {},
        "kernel_program_semantic_handoffs": _dict_records(
            topology_bundle.get("kernel_program_semantic_handoffs")
        ),
        "kernel_program_semantic_handoff_count": _int_value(
            topology_bundle.get("kernel_program_semantic_handoff_count")
        ),
        "kernel_program_semantic_handoff_summary": dict(
            topology_bundle.get("kernel_program_semantic_handoff_summary", {})
        )
        if isinstance(topology_bundle.get("kernel_program_semantic_handoff_summary"), dict)
        else {},
        "semantic_preservation": dict(topology_bundle.get("semantic_preservation", {}))
        if isinstance(topology_bundle.get("semantic_preservation"), dict)
        else {},
        "generated_uv_atlas_hints": generated_uv_atlas_hints,
    }
