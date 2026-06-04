"""Mesh finalize: produce the authoritative downstream mesh.

Cleans, welds and normalizes fused geometry so topology, UV and
surface stages can assume a canonical manifold input.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import trimesh

from .mesh_ir import MeshIR
from .shape_ir import ShapeIR

# Default dihedral threshold for render-only hard-edge splitting.
# Authoritative MeshIR keeps welded vertices so topology, validation, and
# package stages can trust watertightness. Shading/export paths can still
# derive split normals from ``hard_edge_classes`` without mutating the
# canonical mesh handoff.
_HARD_EDGE_ANGLE_DEG = 60.0

# Components whose surfaces should remain visually soft (smooth shading
# everywhere). Vents and grilles are typical candidates: their micro-detail
# benefits from interpolation rather than per-face faceting.
_SOFT_COMPONENTS = frozenset({"vent", "grille"})
_MATERIAL_COMPONENTS = frozenset(
    {"screen_bezel", "panel", "bezel", "lock_plate", "socket_plate", "material_zone", "wear_zone", "decal_zone"}
)


def _region_material_boundary(region: Any) -> bool:
    component = str(getattr(region, "component", "") or "")
    tags = {str(tag) for tag in getattr(region, "tags", []) if str(tag)}
    return (
        component in _MATERIAL_COMPONENTS
        or "material_zone" in tags
        or "wear_zone" in tags
        or "decal_zone" in tags
    )


def _sharp_parts(shape_ir: ShapeIR) -> set[str]:
    """Set of ``region.part`` names whose faces should keep sharp edges.

    A part is considered sharp if any region tagged with that part has a
    sharp component. Soft-only parts (e.g. a vent that is the sole region
    for its part) stay smooth.
    """
    parts: set[str] = set()
    for region in shape_ir.regions:
        if region.component not in _SOFT_COMPONENTS:
            parts.add(region.part)
    return parts


def _split_hard_edges(
    mesh: trimesh.Trimesh,
    face_parts: list[str],
    sharp_parts: set[str],
    angle_threshold_deg: float = _HARD_EDGE_ANGLE_DEG,
) -> tuple[trimesh.Trimesh, list[str]]:
    """Duplicate vertices along edges that should render as hard.

    An edge is hard when its dihedral angle exceeds the threshold and
    either both adjacent face_parts are in ``sharp_parts`` or the two
    face_parts differ (a cross-part seam — always sharp). At every vertex
    incident to at least one hard edge, each adjacent face gets its own
    copy of the vertex so smooth-shading no longer averages normals across
    the seam. Smooth (sub-threshold) regions stay shared so curvature
    keeps interpolating naturally.

    Returns the original mesh and ``face_parts`` unchanged when there is
    nothing to split (no sharp parts, no adjacency, etc.).
    """
    if len(mesh.faces) == 0 or not sharp_parts:
        return mesh, face_parts

    face_adj = np.asarray(mesh.face_adjacency, dtype=np.int64)
    if face_adj.shape[0] == 0:
        return mesh, face_parts

    adj_edges = np.asarray(mesh.face_adjacency_edges, dtype=np.int64)
    adj_angles = np.asarray(mesh.face_adjacency_angles, dtype=np.float64)
    threshold = np.radians(angle_threshold_deg)

    # Vertices that touch any hard edge — these need per-face copies so
    # that no face contributes to a smooth-averaged normal across a seam.
    hard_vertices: set[int] = set()
    for (fa, fb), (va, vb), angle in zip(face_adj, adj_edges, adj_angles, strict=False):
        if angle < threshold:
            continue
        pa = face_parts[int(fa)]
        pb = face_parts[int(fb)]
        if pa == pb and pa not in sharp_parts:
            continue
        hard_vertices.add(int(va))
        hard_vertices.add(int(vb))

    if not hard_vertices:
        return mesh, face_parts

    # For each hard vertex, give every face that touches it its own copy
    # except the first one we see (which keeps the original index).
    verts_list = np.asarray(mesh.vertices, dtype=np.float64).tolist()
    faces = np.asarray(mesh.faces, dtype=np.int64).copy()
    seen_first_face: dict[int, int] = {}  # orig_vert -> face that keeps it
    face_vertex_remap: dict[tuple[int, int], int] = {}  # (face_idx, orig) -> new

    for face_idx in range(faces.shape[0]):
        for j in range(3):
            orig_v = int(faces[face_idx, j])
            if orig_v not in hard_vertices:
                continue
            if orig_v not in seen_first_face:
                seen_first_face[orig_v] = face_idx
                continue
            if seen_first_face[orig_v] == face_idx:
                continue
            key = (face_idx, orig_v)
            new_idx = face_vertex_remap.get(key)
            if new_idx is None:
                new_idx = len(verts_list)
                verts_list.append(list(verts_list[orig_v]))
                face_vertex_remap[key] = new_idx
            faces[face_idx, j] = new_idx

    new_mesh = trimesh.Trimesh(
        vertices=np.asarray(verts_list, dtype=np.float64),
        faces=faces,
        process=False,
    )
    return new_mesh, face_parts


def _primitive_component(primitive: Any) -> str:
    return str(primitive.component or primitive.region or primitive.primitive_type or "primitive")


def _primitive_name(prefix: str, primitive: Any, index: int) -> str:
    part = str(primitive.part or "mesh")
    return f"{prefix}_{index:03d}_{part}"


def _semantic_payload(primitive: Any) -> dict[str, Any]:
    payload = getattr(primitive, "semantic_metadata", None)
    return dict(payload) if isinstance(payload, dict) and payload else {}


def _semantic_material_hint(metadata: dict[str, Any], fallback: str) -> str:
    containers = [metadata]
    for value in (
        metadata.get("shape_ir_v2"),
        metadata.get("source_shape_primitive"),
    ):
        if isinstance(value, dict):
            containers.append(value)
            nested = value.get("semantic_metadata")
            if isinstance(nested, dict):
                containers.append(nested)
    for container in containers:
        for key in ("material_hint", "material_zone", "material", "zone"):
            value = container.get(key)
            if value in (None, "", (), [], {}):
                continue
            if isinstance(value, dict):
                for nested_key in ("material_hint", "material", "name", "zone"):
                    nested = value.get(nested_key)
                    if nested not in (None, "", (), [], {}):
                        return str(nested)
                continue
            return str(value)
    return fallback


def _dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str, str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for record in records:
        primitive_index = record.get("primitive_index")
        group_index = record.get("group_index")
        key = (
            str(record.get("source") or ""),
            str(record.get("name") or ""),
            str(record.get("part") or ""),
            str(record.get("operand_id") or ""),
            str(record.get("instance_id") or ""),
            "" if primitive_index is None else str(primitive_index),
            "" if group_index is None else str(group_index),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(record)
    return out


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _metadata_safe_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _metadata_safe_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_metadata_safe_value(item) for item in value]
    if isinstance(value, list):
        return [_metadata_safe_value(item) for item in value]
    if isinstance(value, np.ndarray):
        return _metadata_safe_value(value.tolist())
    if isinstance(value, np.generic):
        return value.item()
    return value


def _kernel_semantic_handoff_from_metadata(mesh_metadata: dict[str, Any]) -> dict[str, Any]:
    for container in (
        mesh_metadata,
        mesh_metadata.get("integration_report"),
        mesh_metadata.get("exact_report"),
    ):
        if not isinstance(container, dict):
            continue
        handoff = container.get("kernel_program_semantic_handoff")
        if isinstance(handoff, dict):
            return handoff
    return {}


def _append_kernel_semantic_handoff_payload(
    handoff: dict[str, Any],
    *,
    seam_classes: list[dict[str, Any]],
    hard_edge_classes: list[dict[str, Any]],
    material_zones: list[dict[str, Any]],
    source: str,
) -> None:
    if not handoff:
        return
    for index, record in enumerate(_list_of_dicts(handoff.get("seam_records"))):
        seam_classes.append(
            {
                **record,
                "name": str(record.get("name") or f"kernel_semantic_seam_{index:03d}"),
                "part": str(record.get("part") or ""),
                "source": f"{source}.seam_records",
            }
        )
    for index, record in enumerate(_list_of_dicts(handoff.get("hard_edge_records"))):
        hard_edge_classes.append(
            {
                **record,
                "name": str(record.get("name") or f"kernel_semantic_hard_edge_{index:03d}"),
                "part": str(record.get("part") or ""),
                "sharp": bool(record.get("sharp", True)),
                "source": f"{source}.hard_edge_records",
            }
        )
    for index, record in enumerate(_list_of_dicts(handoff.get("material_zone_candidates"))):
        material_zones.append(
            {
                **record,
                "name": str(record.get("name") or f"kernel_semantic_material_{index:03d}"),
                "part": str(record.get("part") or ""),
                "material_hint": str(record.get("material_hint") or record.get("component") or "material"),
                "source": f"{source}.material_zone_candidates",
            }
        )


def _append_kernel_semantic_handoff_records(
    mesh_metadata: dict[str, Any],
    *,
    seam_classes: list[dict[str, Any]],
    hard_edge_classes: list[dict[str, Any]],
    material_zones: list[dict[str, Any]],
) -> None:
    _append_kernel_semantic_handoff_payload(
        _kernel_semantic_handoff_from_metadata(mesh_metadata),
        seam_classes=seam_classes,
        hard_edge_classes=hard_edge_classes,
        material_zones=material_zones,
        source="kernel_program_semantic_handoff",
    )


def _metadata_candidate_containers(
    mesh_metadata: dict[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    containers: list[tuple[str, dict[str, Any]]] = [("mesh_metadata", mesh_metadata)]
    for key in ("integration_report", "exact_report"):
        value = mesh_metadata.get(key)
        if isinstance(value, dict):
            containers.append((key, value))
            nested = value.get("exact_report")
            if isinstance(nested, dict):
                containers.append((f"{key}.exact_report", nested))
    return containers


def _append_material_zone_candidates_from_metadata(
    mesh_metadata: dict[str, Any],
    *,
    material_zones: list[dict[str, Any]],
) -> None:
    for source, container in _metadata_candidate_containers(mesh_metadata):
        for index, record in enumerate(_list_of_dicts(container.get("material_zone_candidates"))):
            material_zones.append(
                {
                    **record,
                    "name": str(record.get("name") or f"exact_semantic_material_{index:03d}"),
                    "part": str(record.get("part") or ""),
                    "material_hint": str(
                        record.get("material_hint")
                        or record.get("component")
                        or "material"
                    ),
                    "source": f"{source}.material_zone_candidates",
                }
            )


def _append_shape_ir_v2_modifier_semantic_classes(
    mesh_metadata: dict[str, Any],
    *,
    seam_classes: list[dict[str, Any]],
    hard_edge_classes: list[dict[str, Any]],
) -> None:
    for index, record in enumerate(_list_of_dicts(mesh_metadata.get("shape_ir_v2_modifier_records"))):
        modifier_name = str(record.get("name") or "")
        if not modifier_name:
            continue
        part = str(record.get("part") or record.get("source_part") or "")
        component = str(record.get("component") or record.get("operation") or modifier_name)
        base_name = str(record.get("operation_id") or record.get("name") or f"modifier_{index:03d}")
        if modifier_name == "v2_polybevel_modifier":
            seam_classes.append(
                {
                    "name": f"{base_name}_polybevel_seam",
                    "part": part,
                    "component": component,
                    "tags": ["shape_ir_v2_modifier", "polybevel", "edge_treatment"],
                    "source": "shape_ir_v2_modifier_record",
                    "operation": str(record.get("operation") or "sop.polybevel"),
                    "modifier_name": modifier_name,
                }
            )
        elif modifier_name in {"v2_mark_hard_edge_modifier", "v2_weighted_normals_modifier"}:
            weighted = modifier_name == "v2_weighted_normals_modifier"
            hard_edge_classes.append(
                {
                    "name": f"{base_name}_{'weighted_normals' if weighted else 'hard_edge'}",
                    "part": part,
                    "component": component,
                    "source": "shape_ir_v2_modifier_record",
                    "operation": str(
                        record.get("operation")
                        or ("op.weighted_normals" if weighted else "op.mark_hard_edge")
                    ),
                    "modifier_name": modifier_name,
                    "sharp": not weighted,
                    "weighted_normals": weighted,
                }
            )


def _direct_modifier_name_from_metadata(
    source_key: str,
    record: dict[str, Any],
) -> str:
    explicit = str(record.get("modifier_name") or "")
    if explicit.startswith("v2_") and explicit.endswith("_modifier"):
        return explicit
    explicit_name = str(record.get("name") or "")
    if explicit_name.startswith("v2_") and explicit_name.endswith("_modifier"):
        return explicit_name
    prefix = "lathe_v2_direct_"
    if source_key.startswith(prefix) and source_key.endswith("_modifier"):
        return f"v2_{source_key[len(prefix):]}"
    if source_key in {"lathe_v2_transform_modifier", "lathe_v2_instance_transform_modifier"}:
        return "v2_transform_modifier"
    return ""


def _copy_shape_ir_v2_modifier_metadata(mesh_metadata: dict[str, Any]) -> None:
    records: list[dict[str, Any]] = []
    sources: set[str] = set()
    for source, container in _metadata_candidate_containers(mesh_metadata):
        for record in _list_of_dicts(container.get("shape_ir_v2_modifier_records")):
            out = dict(record)
            out.setdefault("source", f"{source}.shape_ir_v2_modifier_records")
            records.append(out)
            sources.add(source)
        exact_modifiers = container.get("lathe_shape_ir_v2_modifiers")
        if isinstance(exact_modifiers, dict):
            for record in _list_of_dicts(exact_modifiers.get("modifier_records")):
                out = dict(record)
                out.setdefault("source", f"{source}.lathe_shape_ir_v2_modifiers")
                records.append(out)
                sources.add(f"{source}.lathe_shape_ir_v2_modifiers")
        for key, value in container.items():
            if not isinstance(value, dict):
                continue
            modifier_name = _direct_modifier_name_from_metadata(str(key), value)
            if not modifier_name:
                continue
            out = {
                "name": modifier_name,
                "operation": str(value.get("operation") or ""),
                "semantic_state": "direct_modifier_execution_recorded",
                "geometry_application": str(value.get("geometry_application") or ""),
                "geometry_applied": bool(value.get("geometry_applied")),
                "payload": _metadata_safe_value(value),
                "source": f"{source}.{key}",
            }
            for copy_key in (
                "method",
                "actual_method",
                "actual_backend",
                "actual_geometry_backend",
                "result_face_count",
                "result_vertex_count",
                "result_watertight",
                "result_body_count",
                "fallback",
                "fallback_reason",
            ):
                if copy_key in value:
                    out[copy_key] = value[copy_key]
            records.append(out)
            sources.add(f"{source}.{key}")

    if not records:
        return

    combined = _dedupe_records(
        [
            *_list_of_dicts(mesh_metadata.get("shape_ir_v2_modifier_records")),
            *records,
        ]
    )
    modifier_names = sorted(
        {
            str(record.get("name") or "")
            for record in combined
            if str(record.get("name") or "")
        }
    )
    operations = sorted(
        {
            str(record.get("operation") or "")
            for record in combined
            if str(record.get("operation") or "")
        }
    )
    geometry_application_counts: dict[str, int] = {}
    for record in combined:
        application = str(record.get("geometry_application") or "")
        if not application:
            continue
        geometry_application_counts[application] = geometry_application_counts.get(application, 0) + 1
    mesh_metadata["shape_ir_v2_modifier_records"] = combined
    mesh_metadata["shape_ir_v2_modifier_summary"] = {
        "schema": "lathe.mesh_ir.shape_ir_v2_modifier_summary.v1",
        "record_count": len(combined),
        "modifier_names": modifier_names,
        "operations": operations,
        "geometry_applied_count": sum(1 for record in combined if bool(record.get("geometry_applied"))),
        "geometry_application_counts": dict(sorted(geometry_application_counts.items())),
        "generic_modifier_names": [
            name
            for name in modifier_names
            if any(
                bool(record.get("generic")) and str(record.get("name") or "") == name
                for record in combined
            )
        ],
        "semantic_state": "metadata_preserved",
        "geometry_application": "modifier_specific_metadata_or_downstream_stage",
        "sources": sorted(sources),
    }


def _primitive_kernel_result_metadata_records(shape_ir: ShapeIR) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for primitive in shape_ir.primitives:
        metadata = _semantic_payload(primitive)
        kernel_result = metadata.get("kernel_result_metadata")
        if isinstance(kernel_result, dict):
            records.append(kernel_result)
        v2_metadata = metadata.get("shape_ir_v2")
        if not isinstance(v2_metadata, dict):
            continue
        for value in v2_metadata.values():
            if not isinstance(value, dict):
                continue
            kernel_program = value.get("kernel_program")
            if isinstance(kernel_program, dict):
                records.append(kernel_program)
    return records


def _primitive_kernel_semantic_handoffs(shape_ir: ShapeIR) -> list[dict[str, Any]]:
    handoffs: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, tuple[str, ...]]] = set()
    for kernel_result in _primitive_kernel_result_metadata_records(shape_ir):
        for key in (
            "lathe_kernel_program_semantic_handoff",
            "kernel_program_semantic_handoff",
        ):
            handoff = kernel_result.get(key)
            if isinstance(handoff, dict):
                operand_ids = tuple(
                    str(record.get("operand_id") or record.get("source_index") or "")
                    for record in _list_of_dicts(handoff.get("operand_records"))
                )
                dedupe_key = (
                    str(handoff.get("schema") or ""),
                    str(handoff.get("source") or ""),
                    str(handoff.get("operand_count") or ""),
                    str(handoff.get("result_face_count") or ""),
                    operand_ids,
                )
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                handoffs.append(handoff)
    return handoffs


def _copy_primitive_kernel_semantic_handoff_metadata(
    mesh_metadata: dict[str, Any],
    shape_ir: ShapeIR,
) -> None:
    primitive_handoffs = _primitive_kernel_semantic_handoffs(shape_ir)
    if not primitive_handoffs:
        return
    existing_handoffs = _list_of_dicts(
        mesh_metadata.get("kernel_program_semantic_handoffs")
    )
    combined = [
        *existing_handoffs,
        *(dict(handoff) for handoff in primitive_handoffs),
    ]
    mesh_metadata["kernel_program_semantic_handoffs"] = combined
    mesh_metadata["kernel_program_semantic_handoff_summary"] = {
        "schema": "lathe.mesh_ir.kernel_program_semantic_handoff_summary.v1",
        "handoff_count": len(combined),
        "sources": sorted(
            {
                str(handoff.get("source") or "")
                for handoff in combined
                if str(handoff.get("source") or "")
            }
        ),
        "total_operand_count": sum(int(handoff.get("operand_count") or 0) for handoff in combined),
        "result_face_counts": [
            int(handoff.get("result_face_count") or 0)
            for handoff in combined
            if handoff.get("result_face_count") is not None
        ],
        "source": "shape_ir.primitive.kernel_result_metadata_or_shape_ir_v2",
    }


def _primitive_kernel_feature_details(shape_ir: ShapeIR) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for kernel_result in _primitive_kernel_result_metadata_records(shape_ir):
        for key in (
            "lathe_kernel_feature_detail",
            "kernel_feature_detail",
            "kernel_program_feature_detail",
        ):
            detail = kernel_result.get(key)
            if not isinstance(detail, dict):
                continue
            dedupe_key = (
                str(detail.get("schema") or ""),
                str(detail.get("operation") or ""),
                str(detail.get("feature_kind") or ""),
                repr(detail.get("features") or ()),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            details.append(dict(detail))
    return details


def _copy_primitive_kernel_feature_detail_metadata(
    mesh_metadata: dict[str, Any],
    shape_ir: ShapeIR,
) -> None:
    feature_details = _primitive_kernel_feature_details(shape_ir)
    if not feature_details:
        return
    existing = _list_of_dicts(mesh_metadata.get("kernel_feature_details"))
    combined = [*existing, *feature_details]
    mesh_metadata["kernel_feature_details"] = combined
    mesh_metadata["kernel_feature_detail_summary"] = {
        "schema": "lathe.mesh_ir.kernel_feature_detail_summary.v1",
        "feature_detail_count": len(combined),
        "feature_kinds": sorted(
            {
                str(detail.get("feature_kind") or "")
                for detail in combined
                if str(detail.get("feature_kind") or "")
            }
        ),
        "operations": sorted(
            {
                str(detail.get("operation") or "")
                for detail in combined
                if str(detail.get("operation") or "")
            }
        ),
        "methods": sorted(
            {
                str(detail.get("method") or "")
                for detail in combined
                if str(detail.get("method") or "")
            }
        ),
        "actual_backends": sorted(
            {
                str(detail.get("actual_backend") or "")
                for detail in combined
                if str(detail.get("actual_backend") or "")
            }
        ),
        "actual_geometry_backends": sorted(
            {
                str(detail.get("actual_geometry_backend") or "")
                for detail in combined
                if str(detail.get("actual_geometry_backend") or "")
            }
        ),
        "fallback_count": sum(1 for detail in combined if bool(detail.get("fallback"))),
        "result_face_counts": [
            int(detail.get("result_face_count") or 0)
            for detail in combined
            if detail.get("result_face_count") is not None
        ],
        "result_vertex_counts": [
            int(detail.get("result_vertex_count") or 0)
            for detail in combined
            if detail.get("result_vertex_count") is not None
        ],
        "source": "shape_ir.primitive.kernel_result_metadata",
    }


def _primitive_kernel_edge_treatments(shape_ir: ShapeIR) -> list[dict[str, Any]]:
    treatments: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for kernel_result in _primitive_kernel_result_metadata_records(shape_ir):
        for key in (
            "lathe_kernel_edge_treatment",
            "kernel_edge_treatment",
            "kernel_program_edge_treatment",
        ):
            treatment = kernel_result.get(key)
            if not isinstance(treatment, dict):
                continue
            dedupe_key = (
                str(treatment.get("schema") or ""),
                str(treatment.get("operation") or ""),
                str(treatment.get("treatment_kind") or ""),
                repr(treatment.get("treatments") or ()),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            treatments.append(dict(treatment))
    return treatments


def _copy_primitive_kernel_edge_treatment_metadata(
    mesh_metadata: dict[str, Any],
    shape_ir: ShapeIR,
) -> None:
    edge_treatments = _primitive_kernel_edge_treatments(shape_ir)
    if not edge_treatments:
        return
    existing = _list_of_dicts(mesh_metadata.get("kernel_edge_treatments"))
    combined = [*existing, *edge_treatments]
    mesh_metadata["kernel_edge_treatments"] = combined
    mesh_metadata["kernel_edge_treatment_summary"] = {
        "schema": "lathe.mesh_ir.kernel_edge_treatment_summary.v1",
        "edge_treatment_count": len(combined),
        "treatment_kinds": sorted(
            {
                str(treatment.get("treatment_kind") or "")
                for treatment in combined
                if str(treatment.get("treatment_kind") or "")
            }
        ),
        "operations": sorted(
            {
                str(treatment.get("operation") or "")
                for treatment in combined
                if str(treatment.get("operation") or "")
            }
        ),
        "source": "shape_ir.primitive.kernel_result_metadata",
    }


def _primitive_kernel_pattern_instances(shape_ir: ShapeIR) -> list[dict[str, Any]]:
    patterns: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for kernel_result in _primitive_kernel_result_metadata_records(shape_ir):
        for key in (
            "lathe_kernel_pattern_instances",
            "kernel_pattern_instances",
            "kernel_program_pattern_instances",
        ):
            pattern = kernel_result.get(key)
            if not isinstance(pattern, dict):
                continue
            dedupe_key = (
                str(pattern.get("schema") or ""),
                str(pattern.get("operation") or ""),
                str(pattern.get("pattern_kind") or ""),
                repr(pattern.get("pattern_payload") or ()),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            patterns.append(dict(pattern))
    return patterns


def _copy_primitive_kernel_pattern_instance_metadata(
    mesh_metadata: dict[str, Any],
    shape_ir: ShapeIR,
) -> None:
    pattern_instances = _primitive_kernel_pattern_instances(shape_ir)
    if not pattern_instances:
        return
    existing = _list_of_dicts(mesh_metadata.get("kernel_pattern_instances"))
    combined = [*existing, *pattern_instances]
    mesh_metadata["kernel_pattern_instances"] = combined
    mesh_metadata["kernel_pattern_instance_summary"] = {
        "schema": "lathe.mesh_ir.kernel_pattern_instance_summary.v1",
        "pattern_instance_count": len(combined),
        "pattern_kinds": sorted(
            {
                str(pattern.get("pattern_kind") or "")
                for pattern in combined
                if str(pattern.get("pattern_kind") or "")
            }
        ),
        "operations": sorted(
            {
                str(pattern.get("operation") or "")
                for pattern in combined
                if str(pattern.get("operation") or "")
            }
        ),
        "source": "shape_ir.primitive.kernel_result_metadata",
    }


def _primitive_kernel_deforms(shape_ir: ShapeIR) -> list[dict[str, Any]]:
    deforms: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for kernel_result in _primitive_kernel_result_metadata_records(shape_ir):
        for key in (
            "lathe_kernel_deform",
            "kernel_deform",
            "kernel_program_deform",
        ):
            deform = kernel_result.get(key)
            if not isinstance(deform, dict):
                continue
            dedupe_key = (
                str(deform.get("schema") or ""),
                str(deform.get("operation") or ""),
                str(deform.get("axis") or ""),
                str(deform.get("method") or ""),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            deforms.append(dict(deform))
    return deforms


def _copy_primitive_kernel_deform_metadata(
    mesh_metadata: dict[str, Any],
    shape_ir: ShapeIR,
) -> None:
    deforms = _primitive_kernel_deforms(shape_ir)
    if not deforms:
        return
    existing = _list_of_dicts(mesh_metadata.get("kernel_deforms"))
    combined = [*existing, *deforms]
    mesh_metadata["kernel_deforms"] = combined
    mesh_metadata["kernel_deform_summary"] = {
        "schema": "lathe.mesh_ir.kernel_deform_summary.v1",
        "deform_count": len(combined),
        "operations": sorted(
            {
                str(deform.get("operation") or "")
                for deform in combined
                if str(deform.get("operation") or "")
            }
        ),
        "axes": sorted(
            {
                str(deform.get("axis") or "")
                for deform in combined
                if str(deform.get("axis") or "")
            }
        ),
        "source": "shape_ir.primitive.kernel_result_metadata",
    }


def _primitive_kernel_profile_paths(shape_ir: ShapeIR) -> list[dict[str, Any]]:
    profile_paths: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for kernel_result in _primitive_kernel_result_metadata_records(shape_ir):
        for key in (
            "lathe_kernel_profile_path",
            "kernel_profile_path",
            "kernel_program_profile_path",
        ):
            profile_path = kernel_result.get(key)
            if not isinstance(profile_path, dict):
                continue
            dedupe_key = (
                str(profile_path.get("schema") or ""),
                str(profile_path.get("operation") or ""),
                str(profile_path.get("profile_kind") or ""),
                str(profile_path.get("method") or ""),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            profile_paths.append(dict(profile_path))
    return profile_paths


def _copy_primitive_kernel_profile_path_metadata(
    mesh_metadata: dict[str, Any],
    shape_ir: ShapeIR,
) -> None:
    profile_paths = _primitive_kernel_profile_paths(shape_ir)
    if not profile_paths:
        return
    existing = _list_of_dicts(mesh_metadata.get("kernel_profile_paths"))
    combined = [*existing, *profile_paths]
    mesh_metadata["kernel_profile_paths"] = combined
    mesh_metadata["kernel_profile_path_summary"] = {
        "schema": "lathe.mesh_ir.kernel_profile_path_summary.v1",
        "profile_path_count": len(combined),
        "operations": sorted(
            {
                str(profile_path.get("operation") or "")
                for profile_path in combined
                if str(profile_path.get("operation") or "")
            }
        ),
        "profile_kinds": sorted(
            {
                str(profile_path.get("profile_kind") or "")
                for profile_path in combined
                if str(profile_path.get("profile_kind") or "")
            }
        ),
        "source": "shape_ir.primitive.kernel_result_metadata",
    }


def _primitive_named_kernel_records(
    shape_ir: ShapeIR,
    *,
    metadata_keys: tuple[str, ...],
    dedupe_fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for kernel_result in _primitive_kernel_result_metadata_records(shape_ir):
        for key in metadata_keys:
            record = kernel_result.get(key)
            if not isinstance(record, dict):
                continue
            dedupe_key = tuple(str(record.get(field) or "") for field in dedupe_fields)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            records.append(dict(record))
    return records


def _copy_primitive_named_kernel_records(
    mesh_metadata: dict[str, Any],
    shape_ir: ShapeIR,
    *,
    metadata_keys: tuple[str, ...],
    output_key: str,
    summary_key: str,
    summary_schema: str,
    count_key: str,
    kind_key: str,
) -> None:
    records = _primitive_named_kernel_records(
        shape_ir,
        metadata_keys=metadata_keys,
        dedupe_fields=("schema", "operation", kind_key, "method"),
    )
    if not records:
        return
    existing = _list_of_dicts(mesh_metadata.get(output_key))
    combined = [*existing, *records]
    mesh_metadata[output_key] = combined
    mesh_metadata[summary_key] = {
        "schema": summary_schema,
        count_key: len(combined),
        "operations": sorted(
            {
                str(record.get("operation") or "")
                for record in combined
                if str(record.get("operation") or "")
            }
        ),
        f"{kind_key}s": sorted(
            {
                str(record.get(kind_key) or "")
                for record in combined
                if str(record.get(kind_key) or "")
            }
        ),
        "source": "shape_ir.primitive.kernel_result_metadata",
    }


def _primitive_kernel_surface_damage(shape_ir: ShapeIR) -> list[dict[str, Any]]:
    damages: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for kernel_result in _primitive_kernel_result_metadata_records(shape_ir):
        for key in (
            "lathe_kernel_surface_damage",
            "kernel_surface_damage",
            "kernel_program_surface_damage",
        ):
            damage = kernel_result.get(key)
            if not isinstance(damage, dict):
                continue
            dedupe_key = (
                str(damage.get("schema") or ""),
                str(damage.get("operation") or ""),
                str(damage.get("damage_kind") or ""),
                repr(damage.get("damages") or ()),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            damages.append(dict(damage))
    damages.extend(_primitive_shape_ir_v2_surface_damage(shape_ir, seen))
    return damages


_SHAPE_IR_V2_DAMAGE_MODIFIERS = {
    "v2_dent_mask_modifier": "dent",
    "v2_chip_edges_modifier": "edge_chip",
    "v2_scratch_mask_modifier": "scratch",
    "v2_grime_mask_modifier": "grime",
}


def _primitive_shape_ir_v2_surface_damage(
    shape_ir: ShapeIR,
    seen: set[tuple[str, str, str, str]],
) -> list[dict[str, Any]]:
    damages: list[dict[str, Any]] = []
    for primitive in shape_ir.primitives:
        metadata = _semantic_payload(primitive)
        v2_metadata = metadata.get("shape_ir_v2")
        if not isinstance(v2_metadata, dict):
            continue
        for modifier_name, damage_kind in _SHAPE_IR_V2_DAMAGE_MODIFIERS.items():
            modifier = v2_metadata.get(modifier_name)
            if not isinstance(modifier, dict):
                continue
            operation = str(v2_metadata.get("v2_op") or metadata.get("operation") or damage_kind)
            centers = (
                modifier.get("dent_centers")
                or modifier.get("patch_centers")
                or modifier.get("corner_signs")
                or []
            )
            damage_record = {
                "schema": "lathe.mesh_ir.shape_ir_v2_surface_damage.v1",
                "source": "shape_ir.primitive.shape_ir_v2",
                "operation": operation,
                "damage_kind": damage_kind,
                "source_part": primitive.part,
                "source_primitive_type": primitive.primitive_type,
                "modifier_name": modifier_name,
                "method": str(modifier.get("method") or ""),
                "geometry_applied": primitive.primitive_type
                in {"dent_mask_set", "edge_chip_set", "surface_patch_set"},
                "damages": [
                    {
                        "part": primitive.part,
                        "damage_kind": damage_kind,
                        "modifier_name": modifier_name,
                        "count": int(modifier.get("count") or 1),
                        "amount": modifier.get("amount"),
                        "radius_cm": modifier.get("radius_cm"),
                        "length_cm": modifier.get("length_cm"),
                        "width_cm": modifier.get("width_cm"),
                        "depth_cm": modifier.get("depth_cm"),
                        "normal_axis": modifier.get("normal_axis"),
                        "side": modifier.get("side"),
                        "centers": centers,
                    }
                ],
            }
            dedupe_key = (
                str(damage_record.get("schema") or ""),
                str(damage_record.get("operation") or ""),
                str(damage_record.get("damage_kind") or ""),
                repr(damage_record.get("damages") or ()),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            damages.append(damage_record)
    return damages


def _copy_primitive_kernel_surface_damage_metadata(
    mesh_metadata: dict[str, Any],
    shape_ir: ShapeIR,
) -> None:
    surface_damage = _primitive_kernel_surface_damage(shape_ir)
    if not surface_damage:
        return
    existing = _list_of_dicts(mesh_metadata.get("kernel_surface_damage"))
    combined = [*existing, *surface_damage]
    mesh_metadata["kernel_surface_damage"] = combined
    mesh_metadata["kernel_surface_damage_summary"] = {
        "schema": "lathe.mesh_ir.kernel_surface_damage_summary.v1",
        "surface_damage_count": len(combined),
        "damage_kinds": sorted(
            {
                str(damage.get("damage_kind") or "")
                for damage in combined
                if str(damage.get("damage_kind") or "")
            }
        ),
        "operations": sorted(
            {
                str(damage.get("operation") or "")
                for damage in combined
                if str(damage.get("operation") or "")
            }
        ),
        "source": "shape_ir.primitive.kernel_result_metadata",
    }


def _copy_primitive_face_operation_metadata(
    mesh_metadata: dict[str, Any],
    shape_ir: ShapeIR,
    *,
    face_count: int,
) -> None:
    if "face_operation_ids" in mesh_metadata:
        return
    for kernel_result in _primitive_kernel_result_metadata_records(shape_ir):
        face_operation_ids = kernel_result.get("face_operation_ids")
        if not isinstance(face_operation_ids, list) or len(face_operation_ids) != face_count:
            continue
        mesh_metadata["face_operation_ids"] = [str(item) for item in face_operation_ids]
        face_operation_summary = kernel_result.get("face_operation_summary")
        if isinstance(face_operation_summary, dict):
            mesh_metadata["face_operation_summary"] = dict(face_operation_summary)
        source_face_operation_summary = kernel_result.get("source_face_operation_summary")
        if isinstance(source_face_operation_summary, dict):
            mesh_metadata["source_face_operation_summary"] = dict(source_face_operation_summary)
        attribution = (
            kernel_result.get("lathe_kernel_program_face_operation_attribution")
            or kernel_result.get("kernel_program_face_operation_attribution")
        )
        if isinstance(attribution, dict):
            mesh_metadata["face_operation_attribution"] = dict(attribution)
        source_attribution = (
            kernel_result.get("lathe_kernel_program_source_face_operation_attribution")
            or kernel_result.get("kernel_program_source_face_operation_attribution")
        )
        if isinstance(source_attribution, dict):
            mesh_metadata["source_face_operation_attribution"] = dict(source_attribution)
        return


def _append_primitive_kernel_semantic_handoff_records(
    shape_ir: ShapeIR,
    *,
    seam_classes: list[dict[str, Any]],
    hard_edge_classes: list[dict[str, Any]],
    material_zones: list[dict[str, Any]],
) -> None:
    for handoff in _primitive_kernel_semantic_handoffs(shape_ir):
        _append_kernel_semantic_handoff_payload(
            handoff,
            seam_classes=seam_classes,
            hard_edge_classes=hard_edge_classes,
            material_zones=material_zones,
            source="shape_ir.primitive.kernel_program_semantic_handoff",
        )


def _append_primitive_mesh_ir_records(
    shape_ir: ShapeIR,
    *,
    seam_classes: list[dict[str, Any]],
    hard_edge_classes: list[dict[str, Any]],
    bake_groups: list[dict[str, Any]],
    material_zones: list[dict[str, Any]],
) -> None:
    for index, primitive in enumerate(shape_ir.primitives):
        blend_mode = primitive.blend_mode or "union"
        component = _primitive_component(primitive)
        tags = [str(tag) for tag in primitive.tags if str(tag)]
        semantic_metadata = _semantic_payload(primitive)

        for group_index, group in enumerate(primitive.boolean_seam_groups):
            if not isinstance(group, dict):
                continue
            seam_classes.append(
                {
                    "name": str(group.get("name") or _primitive_name("boolean_seam", primitive, index)),
                    "part": primitive.part,
                    "component": component,
                    "primitive_type": primitive.primitive_type,
                    "primitive_index": index,
                    "source": "primitive_boolean_seam_group",
                    "operation": str(group.get("operation") or blend_mode),
                    "target": str(group.get("target") or primitive.part),
                    "group_index": group_index,
                    "tags": tags,
                    **({"semantic_metadata": semantic_metadata} if semantic_metadata else {}),
                }
            )

        for group_index, group in enumerate(primitive.bevel_seam_groups):
            if not isinstance(group, dict):
                continue
            name = str(group.get("name") or _primitive_name("bevel_seam", primitive, index))
            target_groups = [
                str(item)
                for item in group.get("target_seam_groups", [])
                if str(item)
            ]
            seam_classes.append(
                {
                    "name": name,
                    "part": primitive.part,
                    "component": component,
                    "primitive_type": primitive.primitive_type,
                    "primitive_index": index,
                    "source": "primitive_bevel_seam_group",
                    "target_seam_groups": target_groups,
                    "group_index": group_index,
                    "tags": tags,
                    **({"semantic_metadata": semantic_metadata} if semantic_metadata else {}),
                }
            )
            hard_edge_classes.append(
                {
                    "name": name,
                    "part": primitive.part,
                    "component": component,
                    "primitive_type": primitive.primitive_type,
                    "primitive_index": index,
                    "source": "primitive_bevel_seam_group",
                    "sharp": True,
                    "target_seam_groups": target_groups,
                    "width_cm": group.get("width_cm") or group.get("radius_cm"),
                    "segments": group.get("segments"),
                }
            )

        for group_index, group in enumerate(primitive.hard_edge_groups):
            if not isinstance(group, dict):
                continue
            hard_edge_classes.append(
                {
                    "name": str(group.get("name") or _primitive_name("hard_edge", primitive, index)),
                    "part": primitive.part,
                    "component": component,
                    "primitive_type": primitive.primitive_type,
                    "primitive_index": index,
                    "source": "primitive_hard_edge_group",
                    "sharp": True,
                    "group_index": group_index,
                    "tags": tags,
                    **({"semantic_metadata": semantic_metadata} if semantic_metadata else {}),
                }
            )

        if primitive.v2_mark_hard_edge_modifier:
            hard_edge_classes.append(
                {
                    "name": _primitive_name("mark_hard_edge", primitive, index),
                    "part": primitive.part,
                    "component": component,
                    "primitive_type": primitive.primitive_type,
                    "primitive_index": index,
                    "source": "v2_mark_hard_edge_modifier",
                    "sharp": True,
                    "modifier": dict(primitive.v2_mark_hard_edge_modifier),
                }
            )
        if primitive.v2_weighted_normals_modifier:
            hard_edge_classes.append(
                {
                    "name": _primitive_name("weighted_normals", primitive, index),
                    "part": primitive.part,
                    "component": component,
                    "primitive_type": primitive.primitive_type,
                    "primitive_index": index,
                    "source": "v2_weighted_normals_modifier",
                    "sharp": False,
                    "weighted_normals": True,
                    "modifier": dict(primitive.v2_weighted_normals_modifier),
                }
            )

        if blend_mode == "subtract":
            continue

        bake_entry = {
            "name": _primitive_name("primitive", primitive, index),
            "part": primitive.part,
            "component": component,
            "primitive_type": primitive.primitive_type,
            "primitive_index": index,
            "bake_group": primitive.part,
            "source": "primitive",
            "tags": tags,
            "material_boundary": component in _MATERIAL_COMPONENTS
            or "material_zone" in tags
            or "wear_zone" in tags,
        }
        if semantic_metadata:
            bake_entry["semantic_metadata"] = semantic_metadata
        bake_groups.append(bake_entry)

        if component in _MATERIAL_COMPONENTS or "material_zone" in tags or "wear_zone" in tags:
            material_hint = _semantic_material_hint(semantic_metadata, component)
            material_zones.append(
                {
                    "name": _primitive_name("material", primitive, index),
                    "part": primitive.part,
                    "material_hint": material_hint,
                    "primitive_type": primitive.primitive_type,
                    "primitive_index": index,
                    "source": "primitive",
                    "tags": tags,
                    **({"semantic_metadata": semantic_metadata} if semantic_metadata else {}),
                }
            )


def finalize_mesh_ir(
    mesh: trimesh.Trimesh, shape_ir: ShapeIR, face_parts: list[str], *, metadata: dict[str, Any] | None = None
) -> MeshIR:
    """Finalize mesh ir.

    Args:
        mesh: mesh argument.
        shape_ir: shape_ir argument.
        face_parts: face_parts argument.
        metadata: metadata argument.

    Returns:
        The result.
    """
    face_parts = (
        list(face_parts)
        if len(face_parts) == len(mesh.faces)
        else [shape_ir.regions[0].part if shape_ir.regions else "mesh"] * len(mesh.faces)
    )
    mesh_metadata = dict(metadata or {})
    integration_report = (
        mesh_metadata.get("integration_report")
        if isinstance(mesh_metadata.get("integration_report"), dict)
        else {}
    )
    _copy_primitive_face_operation_metadata(
        mesh_metadata,
        shape_ir,
        face_count=len(mesh.faces),
    )
    _copy_shape_ir_v2_modifier_metadata(mesh_metadata)
    _copy_primitive_kernel_semantic_handoff_metadata(mesh_metadata, shape_ir)
    _copy_primitive_kernel_feature_detail_metadata(mesh_metadata, shape_ir)
    _copy_primitive_kernel_edge_treatment_metadata(mesh_metadata, shape_ir)
    _copy_primitive_kernel_pattern_instance_metadata(mesh_metadata, shape_ir)
    _copy_primitive_kernel_deform_metadata(mesh_metadata, shape_ir)
    _copy_primitive_kernel_profile_path_metadata(mesh_metadata, shape_ir)
    _copy_primitive_named_kernel_records(
        mesh_metadata,
        shape_ir,
        metadata_keys=("lathe_kernel_edge_control", "kernel_edge_control", "kernel_program_edge_control"),
        output_key="kernel_edge_controls",
        summary_key="kernel_edge_control_summary",
        summary_schema="lathe.mesh_ir.kernel_edge_control_summary.v1",
        count_key="edge_control_count",
        kind_key="edge_control_kind",
    )
    _copy_primitive_named_kernel_records(
        mesh_metadata,
        shape_ir,
        metadata_keys=(
            "lathe_kernel_component_assembly",
            "kernel_component_assembly",
            "kernel_program_component_assembly",
        ),
        output_key="kernel_component_assemblies",
        summary_key="kernel_component_assembly_summary",
        summary_schema="lathe.mesh_ir.kernel_component_assembly_summary.v1",
        count_key="component_assembly_count",
        kind_key="assembly_kind",
    )
    _copy_primitive_named_kernel_records(
        mesh_metadata,
        shape_ir,
        metadata_keys=("lathe_kernel_sdf_field", "kernel_sdf_field", "kernel_program_sdf_field"),
        output_key="kernel_sdf_fields",
        summary_key="kernel_sdf_field_summary",
        summary_schema="lathe.mesh_ir.kernel_sdf_field_summary.v1",
        count_key="sdf_field_count",
        kind_key="field_kind",
    )
    _copy_primitive_named_kernel_records(
        mesh_metadata,
        shape_ir,
        metadata_keys=("lathe_kernel_terrain_field", "kernel_terrain_field", "kernel_program_terrain_field"),
        output_key="kernel_terrain_fields",
        summary_key="kernel_terrain_field_summary",
        summary_schema="lathe.mesh_ir.kernel_terrain_field_summary.v1",
        count_key="terrain_field_count",
        kind_key="terrain_kind",
    )
    _copy_primitive_named_kernel_records(
        mesh_metadata,
        shape_ir,
        metadata_keys=("lathe_kernel_scatter", "kernel_scatter", "kernel_program_scatter"),
        output_key="kernel_scatters",
        summary_key="kernel_scatter_summary",
        summary_schema="lathe.mesh_ir.kernel_scatter_summary.v1",
        count_key="scatter_count",
        kind_key="scatter_kind",
    )
    _copy_primitive_kernel_surface_damage_metadata(mesh_metadata, shape_ir)
    raw_face_operation_ids = mesh_metadata.get("face_operation_ids") or integration_report.get("face_operation_ids")
    if isinstance(raw_face_operation_ids, list) and len(raw_face_operation_ids) == len(mesh.faces):
        face_operation_ids = [str(item) for item in raw_face_operation_ids]
        raw_face_operation_summary = mesh_metadata.get("face_operation_summary")
        summary_source = "mesh.metadata.face_operation_ids"
        if isinstance(raw_face_operation_summary, dict):
            summary_source = str(
                raw_face_operation_summary.get("source") or summary_source
            )
        mesh_metadata["face_operation_ids"] = face_operation_ids
        mesh_metadata["face_operation_summary"] = {
            "schema": "lathe.mesh_ir.face_operation_summary.v1",
            "face_count": len(face_operation_ids),
            "operation_count": len(set(face_operation_ids)),
            "operations": dict(sorted((operation, face_operation_ids.count(operation)) for operation in set(face_operation_ids))),
            "source": summary_source,
        }
    seam_classes = [
        {
            "name": region.name,
            "part": region.part,
            "component": region.component,
            "tags": list(region.tags),
            "source": "region",
        }
        for region in shape_ir.regions
        if region.component in {"panel", "frame", "bezel", "door", "lid", "screen_bezel"}
    ]
    hard_edge_classes = [
        {
            "name": region.name,
            "part": region.part,
            "component": region.component,
            "sharp": region.component not in _SOFT_COMPONENTS,
            "source": "region",
        }
        for region in shape_ir.regions
    ]
    bake_groups = [
        {
            "name": region.name,
            "part": region.part,
            "component": region.component,
            "bake_group": region.part,
            "source": "region",
            "material_boundary": _region_material_boundary(region),
        }
        for region in shape_ir.regions
    ]
    material_zones = []
    for region in shape_ir.regions:
        tags = [str(tag) for tag in region.tags if str(tag)]
        if _region_material_boundary(region):
            material_zones.append(
                {
                    "name": region.name,
                    "part": region.part,
                    "material_hint": region.component,
                    "source": "region",
                    "tags": tags,
                }
            )
    _append_primitive_mesh_ir_records(
        shape_ir,
        seam_classes=seam_classes,
        hard_edge_classes=hard_edge_classes,
        bake_groups=bake_groups,
        material_zones=material_zones,
    )
    _append_shape_ir_v2_modifier_semantic_classes(
        mesh_metadata,
        seam_classes=seam_classes,
        hard_edge_classes=hard_edge_classes,
    )
    _append_kernel_semantic_handoff_records(
        mesh_metadata,
        seam_classes=seam_classes,
        hard_edge_classes=hard_edge_classes,
        material_zones=material_zones,
    )
    _append_material_zone_candidates_from_metadata(
        mesh_metadata,
        material_zones=material_zones,
    )
    _append_primitive_kernel_semantic_handoff_records(
        shape_ir,
        seam_classes=seam_classes,
        hard_edge_classes=hard_edge_classes,
        material_zones=material_zones,
    )
    return MeshIR(
        asset_name=shape_ir.asset_name,
        family=shape_ir.family,
        vertices=np.asarray(mesh.vertices, dtype=np.float64).round(6).tolist(),
        faces=np.asarray(mesh.faces, dtype=np.int64).tolist(),
        face_parts=face_parts,
        material_zones=_dedupe_records(material_zones),
        seam_classes=_dedupe_records(seam_classes),
        hard_edge_classes=_dedupe_records(hard_edge_classes),
        bake_groups=_dedupe_records(bake_groups),
        metadata=mesh_metadata,
    )
