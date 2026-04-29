"""Deterministic Scene Assembly IR helpers for Wonder Scene Graph JSON."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from lathe.paths import PathGuardError, safe_resolve
from lathe.scene.layout import instancing_metadata_by_object_id

SCENE_ASSEMBLY_VERSION = "lathe.scene_assembly.v1"
SCENE_ASSEMBLY_SCHEMA_FILENAME = "scene_assembly.schema.json"

_OBJECT_SOURCE_FIELDS = ("source_asset", "lathe_asset", "source_family", "source_kit", "variant")
_PLANNED_RENDER_PASSES = ("beauty", "object_id", "material_id")
_PACKAGE_PATHS = {
    "scene_graph": "graph/scene_graph.json",
    "scene_assembly": "build/scene_assembly_ir.json",
    "object_selection_payloads": "build/object_selection_payloads.json",
    "scene_assembly_proxy": "build/scene_assembly_proxy_manifest.json",
}
_UNIT_TO_METERS = {
    "meters": 1.0,
    "centimeters": 0.01,
    "millimeters": 0.001,
    "studs": 0.28,
}


def _schema_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / "schema" / SCENE_ASSEMBLY_SCHEMA_FILENAME
        if candidate.exists():
            return candidate.parent
    raise FileNotFoundError(f"Could not locate schema/{SCENE_ASSEMBLY_SCHEMA_FILENAME}")


def get_scene_assembly_schema() -> dict[str, Any]:
    """Return the committed Scene Assembly IR JSON Schema."""
    return json.loads((_schema_root() / SCENE_ASSEMBLY_SCHEMA_FILENAME).read_text(encoding="utf-8"))


def _json_pointer(*parts: object) -> str:
    escaped = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(escaped) if escaped else "/"


def _diagnostic(
    code: str,
    name: str,
    path: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "name": name,
        "severity": "error",
        "contract": "scene_assembly",
        "phase": "scene_assembly_semantics",
        "path": path,
        "message": message,
    }
    if details:
        payload["details"] = details
    return payload


def _items(payload: Mapping[str, Any], collection: str) -> Iterator[tuple[int, Mapping[str, Any]]]:
    raw = payload.get(collection, [])
    if not isinstance(raw, list):
        return
    for index, item in enumerate(raw):
        if isinstance(item, Mapping):
            yield index, item


def _string_field(item: Mapping[str, Any], field: str) -> str | None:
    value = item.get(field)
    return value if isinstance(value, str) and value else None


def _normal_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normal_json(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, list):
        return [_normal_json(item) for item in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


def transform_position(transform: Mapping[str, Any] | None) -> list[float]:
    """Return a normalized translation vector from a Scene Graph transform."""
    return _vector3_from_transform(transform, "position", fallback=[0.0, 0.0, 0.0])


def transform_scale(transform: Mapping[str, Any] | None) -> list[float]:
    """Return a normalized absolute scale vector from a Scene Graph transform."""
    return [abs(value) for value in _vector3_from_transform(transform, "scale", fallback=[1.0, 1.0, 1.0])]


def convert_vector_units(vector: list[float], *, from_units: str, to_units: str) -> list[float]:
    """Convert a vector between Lathe's supported linear unit labels."""
    if from_units not in _UNIT_TO_METERS:
        raise ValueError(f"unsupported source units {from_units!r}")
    if to_units not in _UNIT_TO_METERS:
        raise ValueError(f"unsupported target units {to_units!r}")
    factor = _UNIT_TO_METERS[from_units] / _UNIT_TO_METERS[to_units]
    return [round(float(value) * factor, 6) for value in vector]


def estimate_transform_bounds(transform: Mapping[str, Any] | None, *, base_size: list[float] | None = None) -> dict[str, Any]:
    """Estimate axis-aligned bounds for deterministic proxy assembly."""
    position = transform_position(transform)
    scale = transform_scale(transform)
    unit_size = base_size or [1.0, 1.0, 1.0]
    size = [round(abs(float(unit_size[index])) * scale[index], 6) for index in range(3)]
    return {
        "center": position,
        "size": size,
    }


def contact_hints_for_bounds(bounds: Mapping[str, Any]) -> dict[str, Any]:
    """Return conservative floor-contact hints from estimated bounds."""
    center = bounds.get("center")
    size = bounds.get("size")
    center_z = float(center[2]) if isinstance(center, list) and len(center) == 3 else 0.0
    size_z = float(size[2]) if isinstance(size, list) and len(size) == 3 else 1.0
    bottom_z = round(center_z - (size_z / 2.0), 6)
    return {
        "estimated_bottom_z": bottom_z,
        "floor_clearance": bottom_z,
        "rests_on_floor": bottom_z <= 0.25,
        "nearest_resting_surface": "floor" if bottom_z <= 0.25 else "unresolved",
    }


def _vector3_from_transform(
    transform: Mapping[str, Any] | None,
    field: str,
    *,
    fallback: list[float],
) -> list[float]:
    value = transform.get(field) if isinstance(transform, Mapping) else None
    if not isinstance(value, list) or len(value) != 3:
        return list(fallback)
    normalized: list[float] = []
    for index, fallback_value in enumerate(fallback):
        item = value[index]
        normalized.append(round(float(item), 6) if isinstance(item, int | float) else fallback_value)
    return normalized


def _string_list(value: Any) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _source_metadata(item: Mapping[str, Any]) -> dict[str, Any]:
    return {field: item[field] for field in _OBJECT_SOURCE_FIELDS if isinstance(item.get(field), str)}


def _object_artifact_paths(object_id: str) -> dict[str, str]:
    object_dir = f"build/objects/{object_id}"
    return {
        "asset_proxy": f"{object_dir}/asset_proxy_manifest.json",
        "assembly_proxy": f"{object_dir}/assembly_proxy_manifest.json",
        "selection_payload": f"build/selection/{object_id}.json",
    }


def _render_id(camera_id: str, render_pass: str) -> str:
    return f"render_{camera_id}_{render_pass}"


def _render_path(camera_id: str, render_pass: str) -> str:
    return f"renders/{camera_id}/{render_pass}.proxy.json"


def _export_artifact_path(source_index: int, target: str, export_format: str) -> str:
    return f"exports/{source_index:03d}_{target}_{export_format}.proxy.json"


def _regions(scene_graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for source_index, region in sorted(
        _items(scene_graph, "regions"),
        key=lambda item: (_string_field(item[1], "region_id") or "", item[0]),
    ):
        region_id = _string_field(region, "region_id")
        if region_id is None:
            continue
        records.append(
            {
                "region_id": region_id,
                "name": _string_field(region, "name") or region_id,
                "type": _string_field(region, "type") or "debug",
                "purpose": _string_field(region, "purpose") or "",
                "mood": _string_field(region, "mood") or "",
                "bounds": _normal_json(region.get("bounds", {})),
                "semantic_tags": _string_list(region.get("semantic_tags")),
                "source_index": source_index,
            }
        )
    return records


def _materials(scene_graph: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    records: list[dict[str, Any]] = []
    index_by_material_id: dict[str, int] = {}
    for material_index, (source_index, material) in enumerate(
        sorted(
            _items(scene_graph, "materials"),
            key=lambda item: (_string_field(item[1], "material_id") or "", item[0]),
        ),
        start=1,
    ):
        material_id = _string_field(material, "material_id")
        if material_id is None:
            continue
        index_by_material_id[material_id] = material_index
        records.append(
            {
                "material_id": material_id,
                "material_index": material_index,
                "name": _string_field(material, "name") or material_id,
                "role": _string_field(material, "role") or "material",
                "palette_refs": _string_list(material.get("palette_refs")),
                "pbr": _normal_json(material.get("pbr", {})),
                "source_index": source_index,
            }
        )
    return records, index_by_material_id


def _material_assignments(
    item: Mapping[str, Any],
    *,
    index_by_material_id: Mapping[str, int],
) -> list[dict[str, Any]]:
    raw_bindings = item.get("material_bindings", [])
    if not isinstance(raw_bindings, list):
        return []
    assignments: list[dict[str, Any]] = []
    for source_index, binding in enumerate(raw_bindings):
        if not isinstance(binding, Mapping):
            continue
        material_id = _string_field(binding, "material")
        if material_id is None:
            continue
        assignments.append(
            {
                "slot": _string_field(binding, "slot") or "default",
                "material_id": material_id,
                "material_index": index_by_material_id.get(material_id),
                "source_index": source_index,
            }
        )
    return assignments


def _primary_material_index(assignments: list[Mapping[str, Any]]) -> int | None:
    indices = [item.get("material_index") for item in assignments]
    typed_indices = [index for index in indices if isinstance(index, int)]
    return min(typed_indices) if typed_indices else None


def _objects(
    scene_graph: Mapping[str, Any],
    *,
    index_by_material_id: Mapping[str, int],
    instancing_by_object_id: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, list[str]]]:
    records: list[dict[str, Any]] = []
    object_index: list[dict[str, Any]] = []
    selection_payloads: list[dict[str, Any]] = []
    object_ids_by_region: dict[str, list[str]] = {}
    for render_index, (source_index, item) in enumerate(
        sorted(
            _items(scene_graph, "objects"),
            key=lambda entry: (_string_field(entry[1], "object_id") or "", entry[0]),
        ),
        start=1,
    ):
        object_id = _string_field(item, "object_id")
        if object_id is None:
            continue
        region_id = _string_field(item, "region") or "region_unassigned"
        assignments = _material_assignments(item, index_by_material_id=index_by_material_id)
        material_indices = sorted(
            {
                assignment["material_index"]
                for assignment in assignments
                if isinstance(assignment.get("material_index"), int)
            }
        )
        material_ids = [str(assignment["material_id"]) for assignment in assignments]
        primary_material_index = _primary_material_index(assignments)
        planned_artifacts = _object_artifact_paths(object_id)
        transform = _normal_json(item.get("transform", {}))
        bounds = estimate_transform_bounds(transform if isinstance(transform, Mapping) else None)
        contact_hints = contact_hints_for_bounds(bounds)
        object_ids_by_region.setdefault(region_id, []).append(object_id)
        metadata = {
            "object_id": object_id,
            "region_id": region_id,
            "name": _string_field(item, "name") or object_id,
            "role": _string_field(item, "role") or "dressing_prop",
            "source": _source_metadata(item),
            "semantic_tags": _string_list(item.get("semantic_tags")),
            "state": _normal_json(item.get("state", {})),
            "surface_overrides": _normal_json(item.get("surface_overrides", {})),
            "affordances": _normal_json(item.get("affordances", [])),
            "provenance": _normal_json(item.get("provenance", {})),
            "material_ids": material_ids,
            "instancing": _normal_json(instancing_by_object_id.get(object_id, {})),
        }
        records.append(
            {
                "object_id": object_id,
                "region_id": region_id,
                "collection_id": region_id,
                "render_index": render_index,
                "transform": transform,
                "bounds": bounds,
                "contact_hints": contact_hints,
                "metadata": metadata,
                "material_assignments": assignments,
                "planned_artifacts": planned_artifacts,
                "source_index": source_index,
            }
        )
        object_index.append(
            {
                "object_id": object_id,
                "region_id": region_id,
                "collection_id": region_id,
                "render_index": render_index,
                "material_indices": material_indices,
                "primary_material_index": primary_material_index,
                "selection_payload_path": planned_artifacts["selection_payload"],
            }
        )
        selection_payloads.append(
            {
                "object_id": object_id,
                "render_index": render_index,
                "material_index": primary_material_index,
                "material_indices": material_indices,
                "payload_path": planned_artifacts["selection_payload"],
                "metadata": {
                    "object_id": object_id,
                    "region_id": region_id,
                    "material_ids": material_ids,
                },
            }
        )
    for object_ids in object_ids_by_region.values():
        object_ids.sort()
    return records, object_index, selection_payloads, object_ids_by_region


def _collections(regions: list[Mapping[str, Any]], object_ids_by_region: Mapping[str, list[str]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for region in regions:
        region_id = _string_field(region, "region_id")
        if region_id is None:
            continue
        records.append(
            {
                "collection_id": region_id,
                "collection_type": "region",
                "region_id": region_id,
                "object_ids": list(object_ids_by_region.get(region_id, [])),
            }
        )
    return records


def _cameras(scene_graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    render_sequence = 1
    for source_index, camera in sorted(
        _items(scene_graph, "cameras"),
        key=lambda item: (_string_field(item[1], "camera_id") or "", item[0]),
    ):
        camera_id = _string_field(camera, "camera_id")
        if camera_id is None:
            continue
        planned_renders: list[dict[str, Any]] = []
        for render_pass in _PLANNED_RENDER_PASSES:
            planned_renders.append(
                {
                    "render_id": _render_id(camera_id, render_pass),
                    "render_pass": render_pass,
                    "render_sequence": render_sequence,
                    "path": _render_path(camera_id, render_pass),
                }
            )
            render_sequence += 1
        records.append(
            {
                "camera_id": camera_id,
                "target": _string_field(camera, "target"),
                "framing": _string_field(camera, "framing"),
                "purpose": _string_field(camera, "purpose") or "",
                "transform": _normal_json(camera.get("transform")),
                "fov_degrees": camera.get("fov_degrees"),
                "planned_renders": planned_renders,
                "source_index": source_index,
            }
        )
    return records


def _lights(scene_graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for source_index, light in sorted(
        _items(scene_graph, "lights"),
        key=lambda item: (_string_field(item[1], "light_id") or "", item[0]),
    ):
        light_id = _string_field(light, "light_id")
        if light_id is None:
            continue
        records.append(
            {
                "light_id": light_id,
                "type": _string_field(light, "type") or "point",
                "target": _string_field(light, "target"),
                "color": _string_field(light, "color") or "",
                "intensity": light.get("intensity"),
                "purpose": _string_field(light, "purpose") or "",
                "source_index": source_index,
            }
        )
    return records


def _exports(scene_graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    export_items = sorted(
        _items(scene_graph, "exports"),
        key=lambda item: (
            _string_field(item[1], "target") or "",
            _string_field(item[1], "format") or "",
            _string_field(item[1], "path") or "",
            item[0],
        ),
    )
    for source_index, item in export_items:
        target = _string_field(item, "target") or "scene_package"
        export_format = _string_field(item, "format") or target
        records.append(
            {
                "target": target,
                "format": export_format,
                "declared_path": _string_field(item, "path"),
                "planned_artifact_path": _export_artifact_path(source_index, target, export_format),
                "metadata": _normal_json(item.get("metadata", {})),
                "source_index": source_index,
            }
        )
    return records


def assemble_scene(scene_graph: Mapping[str, Any]) -> dict[str, Any]:
    """Build deterministic Scene Assembly IR from existing Scene Graph JSON."""
    scene_id = _string_field(scene_graph, "scene_id") or "scene"
    regions = _regions(scene_graph)
    materials, index_by_material_id = _materials(scene_graph)
    instancing_by_object_id = instancing_metadata_by_object_id(scene_graph)
    objects, object_index, selection_payloads, object_ids_by_region = _objects(
        scene_graph,
        index_by_material_id=index_by_material_id,
        instancing_by_object_id=instancing_by_object_id,
    )
    collections = _collections(regions, object_ids_by_region)
    cameras = _cameras(scene_graph)
    lights = _lights(scene_graph)
    exports = _exports(scene_graph)
    planned_render_count = sum(len(camera["planned_renders"]) for camera in cameras)
    return {
        "schema_version": SCENE_ASSEMBLY_VERSION,
        "scene_id": scene_id,
        "scene_version": scene_graph.get("version"),
        "metadata": {
            "assembler": "lathe.scene.assembly",
            "assembler_version": 1,
            "source_schema_version": scene_graph.get("schema_version"),
            "runtime": "deferred_proxy",
            "units": {
                "scene": "meters",
                "supported_linear_units": sorted(_UNIT_TO_METERS),
            },
            "counts": {
                "regions": len(regions),
                "collections": len(collections),
                "objects": len(objects),
                "materials": len(materials),
                "cameras": len(cameras),
                "lights": len(lights),
                "object_selection_payloads": len(selection_payloads),
                "planned_renders": planned_render_count,
                "exports": len(exports),
            },
        },
        "package_paths": dict(_PACKAGE_PATHS),
        "regions": regions,
        "collections": collections,
        "materials": materials,
        "objects": objects,
        "cameras": cameras,
        "lights": lights,
        "object_index": object_index,
        "object_selection_payloads": selection_payloads,
        "exports": exports,
    }


def load_and_assemble_scene_graph(path: str | Path) -> dict[str, Any]:
    """Load a Scene Graph JSON file and return deterministic Scene Assembly IR."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"Scene Graph root must be a JSON object: {path}")
    return assemble_scene(payload)


def _check_duplicate_values(
    items: list[tuple[int, Mapping[str, Any]]],
    *,
    field: str,
    collection: str,
    code: str,
    name: str,
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    seen: dict[Any, str] = {}
    for index, item in items:
        value = item.get(field)
        if value is None:
            continue
        path = _json_pointer(collection, index, field)
        first_path = seen.get(value)
        if first_path is None:
            seen[value] = path
            continue
        diagnostics.append(
            _diagnostic(
                code,
                name,
                path,
                f"Scene Assembly {field} {value!r} duplicates the value at {first_path}.",
                details={field: value, "first_path": first_path},
            )
        )
    return diagnostics


def _index_by(items: list[tuple[int, Mapping[str, Any]]], field: str) -> dict[Any, Mapping[str, Any]]:
    indexed: dict[Any, Mapping[str, Any]] = {}
    for _index, item in items:
        value = item.get(field)
        if value is not None and value not in indexed:
            indexed[value] = item
    return indexed


def _check_identity_duplicates(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    checks = (
        ("regions", "region_id", "SA1001", "duplicate_region_id"),
        ("objects", "object_id", "SA1002", "duplicate_object_id"),
        ("materials", "material_id", "SA1003", "duplicate_material_id"),
        ("cameras", "camera_id", "SA1004", "duplicate_camera_id"),
        ("lights", "light_id", "SA1005", "duplicate_light_id"),
        ("object_index", "object_id", "SA1006", "duplicate_object_index_object_id"),
        ("object_selection_payloads", "object_id", "SA1007", "duplicate_selection_payload_object_id"),
    )
    for collection, field, code, name in checks:
        diagnostics.extend(
            _check_duplicate_values(
                list(_items(payload, collection)),
                field=field,
                collection=collection,
                code=code,
                name=name,
            )
        )
    return diagnostics


def _check_index_uniqueness(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    diagnostics.extend(
        _check_duplicate_values(
            list(_items(payload, "object_index")),
            field="render_index",
            collection="object_index",
            code="SA3001",
            name="duplicate_object_render_index",
        )
    )
    diagnostics.extend(
        _check_duplicate_values(
            list(_items(payload, "materials")),
            field="material_index",
            collection="materials",
            code="SA3002",
            name="duplicate_material_index",
        )
    )

    render_records: list[tuple[int, Mapping[str, Any]]] = []
    path_by_record_index: dict[int, str] = {}
    record_index = 0
    for camera_index, camera in _items(payload, "cameras"):
        planned_renders = camera.get("planned_renders", [])
        if not isinstance(planned_renders, list):
            continue
        for planned_render_index, planned_render in enumerate(planned_renders):
            if not isinstance(planned_render, Mapping):
                continue
            render_records.append((record_index, planned_render))
            path_by_record_index[record_index] = _json_pointer(
                "cameras",
                camera_index,
                "planned_renders",
                planned_render_index,
                "render_id",
            )
            record_index += 1

    seen_render_ids: dict[Any, str] = {}
    for index, planned_render in render_records:
        render_id = planned_render.get("render_id")
        if render_id is None:
            continue
        path = path_by_record_index[index]
        first_path = seen_render_ids.get(render_id)
        if first_path is None:
            seen_render_ids[render_id] = path
            continue
        diagnostics.append(
            _diagnostic(
                "SA3003",
                "duplicate_render_id",
                path,
                f"Scene Assembly render_id {render_id!r} duplicates the render at {first_path}.",
                details={"render_id": render_id, "first_path": first_path},
            )
        )
    return diagnostics


def _check_object_links(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    region_ids = {item.get("region_id") for _index, item in _items(payload, "regions")}
    object_ids = {item.get("object_id") for _index, item in _items(payload, "objects")}
    material_ids = {item.get("material_id") for _index, item in _items(payload, "materials")}
    material_id_by_index = {
        item.get("material_index"): item.get("material_id")
        for _index, item in _items(payload, "materials")
        if item.get("material_index") is not None
    }
    object_index_by_id = _index_by(list(_items(payload, "object_index")), "object_id")
    for object_list_index, item in _items(payload, "objects"):
        object_id = item.get("object_id")
        region_id = item.get("region_id")
        if region_id not in region_ids:
            diagnostics.append(
                _diagnostic(
                    "SA2001",
                    "object_region_missing",
                    _json_pointer("objects", object_list_index, "region_id"),
                    f"Object {object_id!r} references missing region_id {region_id!r}.",
                    details={"object_id": object_id, "region_id": region_id},
                )
            )
        indexed = object_index_by_id.get(object_id)
        if indexed is None:
            diagnostics.append(
                _diagnostic(
                    "SA2002",
                    "object_missing_from_index",
                    _json_pointer("objects", object_list_index, "object_id"),
                    f"Object {object_id!r} is missing from object_index.",
                    details={"object_id": object_id},
                )
            )
        elif indexed.get("render_index") != item.get("render_index"):
            diagnostics.append(
                _diagnostic(
                    "SA2003",
                    "object_index_render_index_mismatch",
                    _json_pointer("objects", object_list_index, "render_index"),
                    f"Object {object_id!r} render_index does not match object_index.",
                    details={
                        "object_id": object_id,
                        "object_render_index": item.get("render_index"),
                        "index_render_index": indexed.get("render_index"),
                    },
                )
            )
        assignments = item.get("material_assignments", [])
        if not isinstance(assignments, list):
            continue
        for assignment_index, assignment in enumerate(assignments):
            if not isinstance(assignment, Mapping):
                continue
            material_id = assignment.get("material_id")
            material_index = assignment.get("material_index")
            if material_id not in material_ids:
                diagnostics.append(
                    _diagnostic(
                        "SA2004",
                        "material_assignment_unknown_material",
                        _json_pointer("objects", object_list_index, "material_assignments", assignment_index, "material_id"),
                        f"Object {object_id!r} assigns unknown material_id {material_id!r}.",
                        details={"object_id": object_id, "material_id": material_id},
                    )
                )
            elif material_id_by_index.get(material_index) != material_id:
                diagnostics.append(
                    _diagnostic(
                        "SA2005",
                        "material_assignment_index_mismatch",
                        _json_pointer("objects", object_list_index, "material_assignments", assignment_index, "material_index"),
                        f"Object {object_id!r} material_index does not match material_id {material_id!r}.",
                        details={
                            "object_id": object_id,
                            "material_id": material_id,
                            "material_index": material_index,
                        },
                    )
                )
    for index_list_index, indexed in _items(payload, "object_index"):
        object_id = indexed.get("object_id")
        if object_id not in object_ids:
            diagnostics.append(
                _diagnostic(
                    "SA2006",
                    "object_index_unknown_object",
                    _json_pointer("object_index", index_list_index, "object_id"),
                    f"Object index references unknown object_id {object_id!r}.",
                    details={"object_id": object_id},
                )
            )
    return diagnostics


def _check_selection_payloads(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    index_by_object_id = _index_by(list(_items(payload, "object_index")), "object_id")
    for selection_index, selection in _items(payload, "object_selection_payloads"):
        object_id = selection.get("object_id")
        indexed = index_by_object_id.get(object_id)
        if indexed is None:
            diagnostics.append(
                _diagnostic(
                    "SA2010",
                    "selection_payload_unknown_object",
                    _json_pointer("object_selection_payloads", selection_index, "object_id"),
                    f"Object selection payload references unknown object_id {object_id!r}.",
                    details={"object_id": object_id},
                )
            )
            continue
        if selection.get("render_index") != indexed.get("render_index"):
            diagnostics.append(
                _diagnostic(
                    "SA2011",
                    "selection_payload_render_index_mismatch",
                    _json_pointer("object_selection_payloads", selection_index, "render_index"),
                    f"Object selection payload for {object_id!r} does not match object_index render_index.",
                    details={
                        "object_id": object_id,
                        "selection_render_index": selection.get("render_index"),
                        "index_render_index": indexed.get("render_index"),
                    },
                )
            )
        if selection.get("material_index") != indexed.get("primary_material_index"):
            diagnostics.append(
                _diagnostic(
                    "SA2012",
                    "selection_payload_material_index_mismatch",
                    _json_pointer("object_selection_payloads", selection_index, "material_index"),
                    f"Object selection payload for {object_id!r} does not match object_index material_index.",
                    details={
                        "object_id": object_id,
                        "selection_material_index": selection.get("material_index"),
                        "index_material_index": indexed.get("primary_material_index"),
                    },
                )
            )
    return diagnostics


def _scene_refs(payload: Mapping[str, Any]) -> set[Any]:
    refs: set[Any] = set()
    for collection, field in (
        ("regions", "region_id"),
        ("objects", "object_id"),
        ("cameras", "camera_id"),
        ("lights", "light_id"),
    ):
        refs.update(item.get(field) for _index, item in _items(payload, collection) if item.get(field) is not None)
    return refs


def _check_target_refs(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    refs = _scene_refs(payload)
    for collection, field, id_field, code, name in (
        ("cameras", "target", "camera_id", "SA2020", "camera_target_missing"),
        ("lights", "target", "light_id", "SA2021", "light_target_missing"),
    ):
        for index, item in _items(payload, collection):
            target = item.get(field)
            if target is None or target in refs:
                continue
            diagnostics.append(
                _diagnostic(
                    code,
                    name,
                    _json_pointer(collection, index, field),
                    f"{collection[:-1].title()} target {target!r} does not reference an assembly entity.",
                    details={id_field: item.get(id_field), "target": target},
                )
            )
    return diagnostics


def _iter_package_paths(payload: Mapping[str, Any]) -> Iterator[tuple[str, str]]:
    package_paths = payload.get("package_paths")
    if isinstance(package_paths, Mapping):
        for key, value in package_paths.items():
            if isinstance(value, str):
                yield _json_pointer("package_paths", key), value

    for object_index, item in _items(payload, "objects"):
        planned_artifacts = item.get("planned_artifacts")
        if not isinstance(planned_artifacts, Mapping):
            continue
        for key, value in planned_artifacts.items():
            if isinstance(value, str):
                yield _json_pointer("objects", object_index, "planned_artifacts", key), value

    for selection_index, item in _items(payload, "object_selection_payloads"):
        value = item.get("payload_path")
        if isinstance(value, str):
            yield _json_pointer("object_selection_payloads", selection_index, "payload_path"), value

    for index_list_index, item in _items(payload, "object_index"):
        value = item.get("selection_payload_path")
        if isinstance(value, str):
            yield _json_pointer("object_index", index_list_index, "selection_payload_path"), value

    for camera_index, camera in _items(payload, "cameras"):
        planned_renders = camera.get("planned_renders", [])
        if not isinstance(planned_renders, list):
            continue
        for render_index, planned_render in enumerate(planned_renders):
            if isinstance(planned_render, Mapping) and isinstance(planned_render.get("path"), str):
                yield _json_pointer("cameras", camera_index, "planned_renders", render_index, "path"), planned_render["path"]

    for export_index, item in _items(payload, "exports"):
        value = item.get("planned_artifact_path")
        if isinstance(value, str):
            yield _json_pointer("exports", export_index, "planned_artifact_path"), value


def _check_package_paths(payload: Mapping[str, Any], *, package_root: str | Path | None) -> list[dict[str, Any]]:
    root = Path(package_root) if package_root is not None else Path.cwd()
    diagnostics: list[dict[str, Any]] = []
    for pointer, raw_path in _iter_package_paths(payload):
        try:
            safe_resolve(root, raw_path)
        except PathGuardError as exc:
            diagnostics.append(
                _diagnostic(
                    "SA4001",
                    "unsafe_assembly_package_path",
                    pointer,
                    f"Scene Assembly package path {raw_path!r} is not safe: {exc}",
                    details={"path": raw_path, "root": str(root)},
                )
            )
    return diagnostics


def check_scene_assembly_ir(
    payload: Mapping[str, Any],
    *,
    package_root: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Return semantic diagnostics for a Scene Assembly IR payload."""
    diagnostics: list[dict[str, Any]] = []
    diagnostics.extend(_check_identity_duplicates(payload))
    diagnostics.extend(_check_index_uniqueness(payload))
    diagnostics.extend(_check_object_links(payload))
    diagnostics.extend(_check_selection_payloads(payload))
    diagnostics.extend(_check_target_refs(payload))
    diagnostics.extend(_check_package_paths(payload, package_root=package_root))
    return diagnostics


def validate_scene_assembly_payload(
    payload: dict[str, Any],
    *,
    package_root: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Return JSON-schema and semantic diagnostics for a Scene Assembly IR payload."""
    import jsonschema

    validator = jsonschema.Draft202012Validator(get_scene_assembly_schema())
    diagnostics: list[dict[str, Any]] = []
    for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path)):
        diagnostics.append(
            {
                "code": "SCENE_ASSEMBLY_SCHEMA_VALIDATION",
                "severity": "error",
                "contract": "scene_assembly",
                "path": _json_pointer(*error.absolute_path),
                "message": error.message,
            }
        )
    diagnostics.extend(check_scene_assembly_ir(payload, package_root=package_root))
    return diagnostics


__all__ = [
    "SCENE_ASSEMBLY_SCHEMA_FILENAME",
    "SCENE_ASSEMBLY_VERSION",
    "assemble_scene",
    "check_scene_assembly_ir",
    "contact_hints_for_bounds",
    "convert_vector_units",
    "estimate_transform_bounds",
    "get_scene_assembly_schema",
    "load_and_assemble_scene_graph",
    "transform_position",
    "transform_scale",
    "validate_scene_assembly_payload",
]
