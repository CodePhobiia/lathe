"""Semantic checks for schema-valid Wonder Scene Graph payloads."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from lathe.paths import PathGuardError, safe_resolve

from .diagnostics import scene_diagnostic

SCENE_REF_COLLECTIONS: dict[str, str] = {
    "regions": "region_id",
    "objects": "object_id",
    "lights": "light_id",
    "cameras": "camera_id",
    "curiosity_anchors": "anchor_id",
    "hidden_state": "hidden_id",
}

DUPLICATE_ID_CHECKS: tuple[tuple[str, str, str, str], ...] = (
    ("objects", "object_id", "S1001", "duplicate_object_id"),
    ("regions", "region_id", "S1006", "duplicate_region_id"),
    ("cameras", "camera_id", "S1007", "duplicate_camera_id"),
    ("lights", "light_id", "S1008", "duplicate_light_id"),
    ("materials", "material_id", "S1009", "duplicate_material_id"),
    ("curiosity_anchors", "anchor_id", "S1010", "duplicate_curiosity_anchor_id"),
    ("hidden_state", "hidden_id", "S1011", "duplicate_hidden_id"),
)

SUMMARY_COLLECTIONS: tuple[str, ...] = (
    "regions",
    "objects",
    "relationships",
    "materials",
    "lights",
    "cameras",
    "curiosity_anchors",
    "hidden_state",
    "memory_events",
)


def _json_pointer(*parts: object) -> str:
    escaped = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(escaped) if escaped else "/"


def _items(scene_graph: Mapping[str, Any], collection: str) -> Iterator[tuple[int, Mapping[str, Any]]]:
    raw = scene_graph.get(collection, [])
    if not isinstance(raw, list):
        return
    for index, item in enumerate(raw):
        if isinstance(item, Mapping):
            yield index, item


def _child_items(item: Mapping[str, Any], collection: str) -> Iterator[tuple[int, Mapping[str, Any]]]:
    raw = item.get(collection, [])
    if not isinstance(raw, list):
        return
    for index, child in enumerate(raw):
        if isinstance(child, Mapping):
            yield index, child


def _string_field(item: Mapping[str, Any], field: str) -> str | None:
    value = item.get(field)
    return value if isinstance(value, str) else None


def _id_locations(scene_graph: Mapping[str, Any], collection: str, field: str) -> dict[str, str]:
    locations: dict[str, str] = {}
    for index, item in _items(scene_graph, collection):
        value = _string_field(item, field)
        if value is not None and value not in locations:
            locations[value] = _json_pointer(collection, index, field)
    return locations


def _scene_ref_locations(scene_graph: Mapping[str, Any]) -> dict[str, str]:
    locations: dict[str, str] = {}
    for collection, field in SCENE_REF_COLLECTIONS.items():
        locations.update(_id_locations(scene_graph, collection, field))
    return locations


def _check_duplicate_ids(scene_graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for collection, field, code, name in DUPLICATE_ID_CHECKS:
        seen: dict[str, str] = {}
        for index, item in _items(scene_graph, collection):
            value = _string_field(item, field)
            if value is None:
                continue
            path = _json_pointer(collection, index, field)
            first_path = seen.get(value)
            if first_path is None:
                seen[value] = path
                continue
            diagnostics.append(
                scene_diagnostic(
                    code,
                    name,
                    path,
                    f"Duplicate {field} {value!r}; first seen at {first_path}.",
                    details={field: value, "first_path": first_path},
                )
            )
    return diagnostics


def _check_object_regions(scene_graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    region_ids = set(_id_locations(scene_graph, "regions", "region_id"))
    for index, item in _items(scene_graph, "objects"):
        region = _string_field(item, "region")
        if region is None or region in region_ids:
            continue
        object_id = _string_field(item, "object_id")
        diagnostics.append(
            scene_diagnostic(
                "S1002",
                "missing_object_region",
                _json_pointer("objects", index, "region"),
                f"Object region {region!r} does not match any region_id.",
                details={"object_id": object_id, "region": region},
            )
        )
    return diagnostics


def _check_object_materials(scene_graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    material_ids = set(_id_locations(scene_graph, "materials", "material_id"))
    for object_index, item in _items(scene_graph, "objects"):
        object_id = _string_field(item, "object_id")
        for binding_index, binding in _child_items(item, "material_bindings"):
            material = _string_field(binding, "material")
            if material is None or material in material_ids:
                continue
            slot = _string_field(binding, "slot")
            diagnostics.append(
                scene_diagnostic(
                    "S1012",
                    "missing_object_material",
                    _json_pointer("objects", object_index, "material_bindings", binding_index, "material"),
                    f"Object material {material!r} does not match any material_id.",
                    details={"object_id": object_id, "slot": slot, "material": material},
                )
            )
    return diagnostics


def _check_relationship_endpoints(scene_graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    scene_refs = set(_scene_ref_locations(scene_graph))
    for index, item in _items(scene_graph, "relationships"):
        relationship_id = _string_field(item, "relationship_id")
        for field in ("from", "to"):
            endpoint = _string_field(item, field)
            if endpoint is None or endpoint in scene_refs:
                continue
            diagnostics.append(
                scene_diagnostic(
                    "S1003",
                    "invalid_relationship_endpoint",
                    _json_pointer("relationships", index, field),
                    f"Relationship endpoint {endpoint!r} does not reference a scene entity.",
                    details={
                        "relationship_id": relationship_id,
                        "field": field,
                        "endpoint": endpoint,
                    },
                )
            )
    return diagnostics


def _check_scene_ref_field(
    scene_graph: Mapping[str, Any],
    *,
    collection: str,
    field: str,
    code: str,
    name: str,
    subject: str,
    id_field: str,
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    scene_refs = set(_scene_ref_locations(scene_graph))
    for index, item in _items(scene_graph, collection):
        target = _string_field(item, field)
        if target is None or target in scene_refs:
            continue
        diagnostics.append(
            scene_diagnostic(
                code,
                name,
                _json_pointer(collection, index, field),
                f"{subject} {target!r} does not reference a scene entity.",
                details={
                    id_field: _string_field(item, id_field),
                    "field": field,
                    "target": target,
                },
            )
        )
    return diagnostics


def _check_camera_targets(scene_graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    return _check_scene_ref_field(
        scene_graph,
        collection="cameras",
        field="target",
        code="S1013",
        name="invalid_camera_target",
        subject="Camera target",
        id_field="camera_id",
    )


def _check_light_targets(scene_graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    return _check_scene_ref_field(
        scene_graph,
        collection="lights",
        field="target",
        code="S1014",
        name="invalid_light_target",
        subject="Light target",
        id_field="light_id",
    )


def _check_curiosity_attachments(scene_graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    return _check_scene_ref_field(
        scene_graph,
        collection="curiosity_anchors",
        field="attached_to",
        code="S1015",
        name="invalid_curiosity_attachment",
        subject="Curiosity attachment",
        id_field="anchor_id",
    )


def _check_hidden_attachments(scene_graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    return _check_scene_ref_field(
        scene_graph,
        collection="hidden_state",
        field="attached_to",
        code="S1016",
        name="invalid_hidden_attachment",
        subject="Hidden state attachment",
        id_field="hidden_id",
    )


def _check_affordance_reveals(scene_graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    scene_refs = set(_scene_ref_locations(scene_graph))
    for object_index, item in _items(scene_graph, "objects"):
        object_id = _string_field(item, "object_id")
        for affordance_index, affordance in _child_items(item, "affordances"):
            reveals = _string_field(affordance, "reveals")
            if reveals is None or reveals in scene_refs:
                continue
            diagnostics.append(
                scene_diagnostic(
                    "S1017",
                    "invalid_affordance_reveal",
                    _json_pointer("objects", object_index, "affordances", affordance_index, "reveals"),
                    f"Affordance reveal {reveals!r} does not reference a scene entity.",
                    details={
                        "object_id": object_id,
                        "affordance_id": _string_field(affordance, "id"),
                        "reveals": reveals,
                    },
                )
            )
    return diagnostics


def _check_layout_refs(scene_graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    layout = scene_graph.get("layout")
    if not isinstance(layout, Mapping):
        return diagnostics
    scene_refs = set(_scene_ref_locations(scene_graph))
    focal_point = _string_field(layout, "focal_point")
    if focal_point is not None and focal_point not in scene_refs:
        diagnostics.append(
            scene_diagnostic(
                "S1018",
                "invalid_layout_focal_point",
                "/layout/focal_point",
                f"Layout focal_point {focal_point!r} does not reference a scene entity.",
                details={"focal_point": focal_point},
            )
        )
    main_path = layout.get("main_path")
    if isinstance(main_path, Mapping):
        for field in ("from", "to"):
            endpoint = _string_field(main_path, field)
            if endpoint is None or endpoint in scene_refs:
                continue
            diagnostics.append(
                scene_diagnostic(
                    "S1019",
                    "invalid_layout_main_path_endpoint",
                    _json_pointer("layout", "main_path", field),
                    f"Layout main_path endpoint {endpoint!r} does not reference a scene entity.",
                    details={"field": field, "endpoint": endpoint},
                )
            )
    modular_walls = layout.get("modular_walls")
    if isinstance(modular_walls, Mapping):
        region_ids = set(_id_locations(scene_graph, "regions", "region_id"))
        regions = modular_walls.get("regions", [])
        if isinstance(regions, list):
            for index, region_id in enumerate(regions):
                if not isinstance(region_id, str) or region_id in region_ids:
                    continue
                diagnostics.append(
                    scene_diagnostic(
                        "S1022",
                        "invalid_modular_wall_region",
                        _json_pointer("layout", "modular_walls", "regions", index),
                        f"Modular wall region {region_id!r} does not reference a scene region.",
                        details={"region_id": region_id},
                    )
                )
    return diagnostics


def _check_curiosity_expansion_targets(scene_graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    scene_refs = set(_scene_ref_locations(scene_graph))
    for anchor_index, anchor in _items(scene_graph, "curiosity_anchors"):
        anchor_id = _string_field(anchor, "anchor_id")
        for option_index, option in _child_items(anchor, "expansion_options"):
            target = _string_field(option, "target_scope")
            if target is None or target in scene_refs:
                continue
            diagnostics.append(
                scene_diagnostic(
                    "S1020",
                    "invalid_curiosity_expansion_target",
                    _json_pointer("curiosity_anchors", anchor_index, "expansion_options", option_index, "target_scope"),
                    f"Curiosity expansion target_scope {target!r} does not reference a scene entity.",
                    details={"anchor_id": anchor_id, "target_scope": target},
                )
            )
    return diagnostics


def _check_memory_event_affected_ids(scene_graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    scene_refs = set(_scene_ref_locations(scene_graph))
    for event_index, event in _items(scene_graph, "memory_events"):
        event_id = _string_field(event, "event_id")
        affected_ids = event.get("affected_ids", [])
        if not isinstance(affected_ids, list):
            continue
        for affected_index, affected_id in enumerate(affected_ids):
            if not isinstance(affected_id, str) or affected_id in scene_refs:
                continue
            diagnostics.append(
                scene_diagnostic(
                    "S1021",
                    "invalid_memory_event_affected_id",
                    _json_pointer("memory_events", event_index, "affected_ids", affected_index),
                    f"Memory event affected_id {affected_id!r} does not reference a scene entity.",
                    details={"event_id": event_id, "affected_id": affected_id},
                )
            )
    return diagnostics


def _check_paths(scene_graph: Mapping[str, Any], root: Path) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    path_checks = (
        ("exports", "S1004", "unsafe_export_path"),
        ("build_artifacts", "S1005", "unsafe_build_artifact_path"),
    )
    for collection, code, name in path_checks:
        for index, item in _items(scene_graph, collection):
            raw_path = _string_field(item, "path")
            if raw_path is None:
                continue
            try:
                safe_resolve(root, raw_path)
            except PathGuardError as exc:
                diagnostics.append(
                    scene_diagnostic(
                        code,
                        name,
                        _json_pointer(collection, index, "path"),
                        f"{collection} path {raw_path!r} is not a safe relative path: {exc}",
                        details={"path": raw_path, "root": str(root)},
                    )
                )
    return diagnostics


def check_scene_graph(scene_graph: Mapping[str, Any], *, root: str | Path | None = None) -> list[dict[str, Any]]:
    """Return semantic diagnostics for a Scene Graph payload."""
    path_root = Path(root) if root is not None else Path.cwd()
    diagnostics: list[dict[str, Any]] = []
    diagnostics.extend(_check_duplicate_ids(scene_graph))
    diagnostics.extend(_check_object_regions(scene_graph))
    diagnostics.extend(_check_object_materials(scene_graph))
    diagnostics.extend(_check_relationship_endpoints(scene_graph))
    diagnostics.extend(_check_camera_targets(scene_graph))
    diagnostics.extend(_check_light_targets(scene_graph))
    diagnostics.extend(_check_curiosity_attachments(scene_graph))
    diagnostics.extend(_check_hidden_attachments(scene_graph))
    diagnostics.extend(_check_affordance_reveals(scene_graph))
    diagnostics.extend(_check_layout_refs(scene_graph))
    diagnostics.extend(_check_curiosity_expansion_targets(scene_graph))
    diagnostics.extend(_check_memory_event_affected_ids(scene_graph))
    diagnostics.extend(_check_paths(scene_graph, path_root))
    return diagnostics


def scene_graph_validation_summary(
    scene_graph: Mapping[str, Any],
    diagnostics: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return a compact human-readable summary for Scene Graph semantic checks."""
    scene_id = _string_field(scene_graph, "scene_id") or "unknown_scene"
    counts = {
        collection: len(scene_graph.get(collection, [])) if isinstance(scene_graph.get(collection), list) else 0
        for collection in SUMMARY_COLLECTIONS
    }
    error_count = sum(1 for diagnostic in diagnostics if diagnostic.get("severity") == "error")
    warning_count = sum(1 for diagnostic in diagnostics if diagnostic.get("severity") == "warning")
    status = "passed" if error_count == 0 else "failed"
    if error_count:
        first_error = next(
            (diagnostic for diagnostic in diagnostics if diagnostic.get("severity") == "error"),
            diagnostics[0] if diagnostics else {},
        )
        code = first_error.get("code", "unknown")
        path = first_error.get("path", "/")
        message = first_error.get("message", "No diagnostic message.")
        text = (
            f"Scene Graph {scene_id} failed semantic validation with {error_count} error(s) "
            f"and {warning_count} warning(s); first error {code} at {path}: {message}"
        )
    else:
        text = (
            f"Scene Graph {scene_id} passed semantic validation with {counts['objects']} object(s), "
            f"{counts['regions']} region(s), {counts['cameras']} camera(s), {counts['lights']} light(s), "
            f"and {counts['curiosity_anchors']} curiosity anchor(s)."
        )
    return {
        "status": status,
        "scene_id": scene_id,
        "counts": counts,
        "errors": error_count,
        "warnings": warning_count,
        "text": text,
    }


def load_and_check_scene_graph(path: str | Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Load a Scene Graph file and return schema plus semantic diagnostics."""
    from lathe.wonder import load_and_validate_contract

    file_path = Path(path)
    payload, diagnostics = load_and_validate_contract("scene_graph", file_path)
    if diagnostics:
        return payload, diagnostics
    diagnostics.extend(check_scene_graph(payload, root=file_path.parent))
    return payload, diagnostics


__all__ = [
    "SCENE_REF_COLLECTIONS",
    "check_scene_graph",
    "load_and_check_scene_graph",
    "scene_graph_validation_summary",
]
