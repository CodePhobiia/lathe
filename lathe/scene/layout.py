"""Deterministic layout planning and instance reuse helpers for Wonder scenes."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

LAYOUT_PLAN_VERSION = "lathe.layout_plan.v1"
LAYOUT_PLAN_SCHEMA_FILENAME = "layout_plan.schema.json"
LAYOUT_PLAN_CONTRACT = "layout_plan"

_SOURCE_FIELDS = ("source_asset", "lathe_asset", "source_family", "source_kit")
_DEFAULT_ASSET_SIGNATURE_FIELDS = (
    "source_asset",
    "lathe_asset",
    "source_family",
    "source_kit",
    "variant",
    "material_bindings",
)
_DEFAULT_INSTANCE_OVERRIDE_FIELDS = (
    "name",
    "role",
    "region",
    "transform",
    "semantic_tags",
    "state",
    "surface_overrides",
    "affordances",
    "provenance",
)
_ALLOWED_REUSE_FIELDS = set(_DEFAULT_ASSET_SIGNATURE_FIELDS) | set(_DEFAULT_INSTANCE_OVERRIDE_FIELDS) | {"state"}


def _schema_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / "schema" / LAYOUT_PLAN_SCHEMA_FILENAME
        if candidate.exists():
            return candidate.parent
    raise FileNotFoundError(f"Could not locate schema/{LAYOUT_PLAN_SCHEMA_FILENAME}")


def get_layout_plan_schema() -> dict[str, Any]:
    """Return the committed Layout Plan JSON Schema."""
    return json.loads((_schema_root() / LAYOUT_PLAN_SCHEMA_FILENAME).read_text(encoding="utf-8"))


def validate_layout_plan_payload(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return schema and semantic diagnostics for a Layout Plan payload."""
    import jsonschema

    validator = jsonschema.Draft202012Validator(get_layout_plan_schema())
    diagnostics: list[dict[str, Any]] = []
    for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path)):
        diagnostics.append(
            _diagnostic(
                "LAYOUT_PLAN_SCHEMA_VALIDATION",
                "schema_validation",
                _json_pointer(*error.absolute_path),
                error.message,
                phase="layout_plan_schema",
            )
        )
    diagnostics.extend(_check_unique_placements(payload))
    return diagnostics


def plan_layout(
    scene_graph: Mapping[str, Any],
    *,
    style_pack: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic Layout Plan for a Scene Graph mapping."""
    if not isinstance(scene_graph, Mapping):
        raise ValueError("scene_graph must be a mapping")

    diagnostics: list[dict[str, Any]] = []
    regions = _region_plans(scene_graph)
    regions_by_id = {region["region_id"]: region for region in regions}
    layout_contract = _layout_contract(scene_graph, regions)
    placements, placement_diagnostics = _placements(scene_graph, regions_by_id)
    diagnostics.extend(placement_diagnostics)
    intersections = _intersections(placements)
    if layout_contract["avoid_intersections"]:
        diagnostics.extend(_intersection_diagnostics(intersections))
    path_plan = _path_plan(scene_graph, layout_contract, regions_by_id, placements)
    if layout_contract["avoid_intersections"] and path_plan["blocked_by"]:
        diagnostics.append(
            _diagnostic(
                "LP2003",
                "main_path_blocked",
                "/path_plan/blocked_by",
                "Main path corridor intersects one or more object footprints.",
                details={"blocked_by": list(path_plan["blocked_by"])},
            )
        )
    wall_segments, wall_diagnostics = _wall_segments(layout_contract, regions_by_id)
    diagnostics.extend(wall_diagnostics)

    return {
        "schema_version": LAYOUT_PLAN_VERSION,
        "scene_id": _string_value(scene_graph.get("scene_id")) or "scene",
        "scene_version": _scene_version(scene_graph),
        "generated_by": "lathe.scene.layout",
        "layout": layout_contract,
        "regions": regions,
        "placements": placements,
        "path_plan": path_plan,
        "reuse_groups": plan_instance_reuse(scene_graph, style_pack=style_pack),
        "intersections": intersections,
        "wall_segments": wall_segments,
        "diagnostics": diagnostics,
    }


def plan_instance_reuse(
    scene_graph: Mapping[str, Any],
    *,
    style_pack: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Group scene objects by shareable asset signatures and instance overrides."""
    asset_fields, instance_fields, allow_shared = _reuse_policy(style_pack)
    groups: dict[str, dict[str, Any]] = {}
    object_records = sorted(
        _items(scene_graph, "objects"),
        key=lambda item: (_string_field(item[1], "object_id") is None, _string_field(item[1], "object_id") or item[0]),
    )
    for index, item in object_records:
        object_id = _string_field(item, "object_id") or f"obj_unidentified_{index:03d}"
        source = _object_source(object_id, item)
        asset_payload = _field_payload(item, asset_fields)
        asset_payload["source"] = source
        if source["kind"] == "generated_fallback":
            asset_payload["generated_object_id"] = object_id
        asset_fingerprint = _fingerprint(asset_payload)
        asset_signature = (
            f"scene_instance.v1:{_slug(str(source['kind']))}:{_slug(str(source['ref']))}:{asset_fingerprint}"
        )
        instance_payload = _field_payload(item, instance_fields)
        group = groups.setdefault(
            asset_signature,
            {
                "group_id": f"reuse_group_{_slug(str(source['ref']), max_length=48)}_{asset_fingerprint[:10]}",
                "asset_signature": asset_signature,
                "source": source,
                "variant": _string_field(item, "variant"),
                "object_ids": [],
                "shared_asset": False,
                "asset_fields": list(asset_fields),
                "instance_override_fields": list(instance_fields),
                "asset_fingerprint": asset_fingerprint,
                "instance_fingerprints": [],
                "_generated": source["kind"] == "generated_fallback",
            },
        )
        group["object_ids"].append(object_id)
        group["instance_fingerprints"].append(
            {
                "object_id": object_id,
                "fingerprint": _fingerprint(instance_payload),
                "fields": sorted(instance_payload),
            }
        )

    records: list[dict[str, Any]] = []
    for group in sorted(groups.values(), key=lambda item: (item["object_ids"][0], item["asset_signature"])):
        object_ids = sorted(str(object_id) for object_id in group["object_ids"])
        instance_fingerprints = sorted(
            group["instance_fingerprints"], key=lambda item: (str(item["object_id"]), str(item["fingerprint"]))
        )
        generated = bool(group.pop("_generated"))
        group["object_ids"] = object_ids
        group["instance_fingerprints"] = instance_fingerprints
        group["shared_asset"] = allow_shared and not generated and len(object_ids) > 1
        records.append(group)
    return records


def instancing_metadata_by_object_id(
    scene_graph: Mapping[str, Any],
    *,
    style_pack: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Return exporter-friendly instancing metadata keyed by stable object ID."""
    records: dict[str, dict[str, Any]] = {}
    for group in plan_instance_reuse(scene_graph, style_pack=style_pack):
        instance_by_id = {
            str(item["object_id"]): item
            for item in group.get("instance_fingerprints", [])
            if isinstance(item, Mapping) and isinstance(item.get("object_id"), str)
        }
        for object_id in group.get("object_ids", []):
            if not isinstance(object_id, str):
                continue
            instance = instance_by_id.get(object_id, {})
            records[object_id] = {
                "schema_version": "lathe.scene_instancing_metadata.v1",
                "reuse_group_id": str(group.get("group_id") or ""),
                "asset_signature": str(group.get("asset_signature") or ""),
                "source": _normal_json(group.get("source", {})),
                "variant": group.get("variant") if isinstance(group.get("variant"), str) else None,
                "shared_asset": bool(group.get("shared_asset")),
                "group_object_ids": [str(item) for item in group.get("object_ids", []) if isinstance(item, str)],
                "asset_fields": [str(item) for item in group.get("asset_fields", []) if isinstance(item, str)],
                "instance_override_fields": [
                    str(item) for item in group.get("instance_override_fields", []) if isinstance(item, str)
                ],
                "asset_fingerprint": str(group.get("asset_fingerprint") or ""),
                "instance_fingerprint": str(instance.get("fingerprint") or ""),
                "instance_fields": [str(item) for item in instance.get("fields", []) if isinstance(item, str)],
            }
    return records


def load_and_plan_layout(
    path: str | Path,
    *,
    style_pack: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Load a Scene Graph JSON file and return its deterministic Layout Plan."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"Scene Graph root must be a JSON object: {path}")
    return plan_layout(payload, style_pack=style_pack)


def _diagnostic(
    code: str,
    name: str,
    path: str,
    message: str,
    *,
    severity: str = "error",
    details: dict[str, Any] | None = None,
    phase: str = "layout_planning",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "name": name,
        "severity": severity,
        "contract": LAYOUT_PLAN_CONTRACT,
        "phase": phase,
        "path": path,
        "message": message,
    }
    if details:
        payload["details"] = details
    return payload


def _json_pointer(*parts: object) -> str:
    escaped = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(escaped) if escaped else "/"


def _items(payload: Mapping[str, Any], collection: str) -> Iterator[tuple[int, Mapping[str, Any]]]:
    raw = payload.get(collection, [])
    if not isinstance(raw, list):
        return
    for index, item in enumerate(raw):
        if isinstance(item, Mapping):
            yield index, item


def _string_value(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _string_field(item: Mapping[str, Any], field: str) -> str | None:
    return _string_value(item.get(field))


def _scene_version(scene_graph: Mapping[str, Any]) -> int:
    version = scene_graph.get("version")
    if isinstance(version, int) and not isinstance(version, bool) and version > 0:
        return version
    return 1


def _normal_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normal_json(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, list):
        return [_normal_json(item) for item in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(_normal_json(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fingerprint(value: Any, *, size: int = 16) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8"), usedforsecurity=False).hexdigest()[:size]


def _slug(value: object, *, max_length: int = 72) -> str:
    raw = str(value).strip().lower().replace("&", " and ")
    slug = "".join(char if "a" <= char <= "z" or "0" <= char <= "9" else "_" for char in raw)
    while "__" in slug:
        slug = slug.replace("__", "_")
    slug = slug.strip("_")
    if not slug:
        slug = "item"
    if not slug[0].isalpha():
        slug = f"x_{slug}"
    if len(slug) < 3:
        slug = f"{slug}_item"
    return slug[:max_length].rstrip("_") or "item"


def _vector3(value: object, *, default: Sequence[float]) -> list[float]:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray) and len(value) == 3:
        result: list[float] = []
        for item in value:
            if isinstance(item, bool) or not isinstance(item, int | float):
                return [float(default[0]), float(default[1]), float(default[2])]
            result.append(float(item))
        return result
    return [float(default[0]), float(default[1]), float(default[2])]


def _region_plans(scene_graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for source_index, region in sorted(
        _items(scene_graph, "regions"),
        key=lambda item: (_string_field(item[1], "region_id") or "", item[0]),
    ):
        region_id = _string_field(region, "region_id")
        if region_id is None:
            continue
        bounds = region.get("bounds") if isinstance(region.get("bounds"), Mapping) else {}
        center = _vector3(bounds.get("center") if isinstance(bounds, Mapping) else None, default=(0, 0, 0))
        size = _positive_vector3(bounds.get("size") if isinstance(bounds, Mapping) else None, default=(1, 1, 1))
        minimum, maximum = _bounds_min_max(center, size)
        records.append(
            {
                "region_id": region_id,
                "center": center,
                "size": size,
                "min": minimum,
                "max": maximum,
                "source_index": source_index,
            }
        )
    return records


def _positive_vector3(value: object, *, default: Sequence[float]) -> list[float]:
    vector = _vector3(value, default=default)
    return [component if component > 0 else float(default[index]) for index, component in enumerate(vector)]


def _bounds_min_max(center: Sequence[float], size: Sequence[float]) -> tuple[list[float], list[float]]:
    half = [component / 2 for component in size]
    minimum = [round(center[index] - half[index], 6) for index in range(3)]
    maximum = [round(center[index] + half[index], 6) for index in range(3)]
    return minimum, maximum


def _layout_contract(scene_graph: Mapping[str, Any], regions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    raw = scene_graph.get("layout") if isinstance(scene_graph.get("layout"), Mapping) else {}
    room_size_default = _room_size_from_regions(regions)
    main_path_raw = raw.get("main_path") if isinstance(raw, Mapping) and isinstance(raw.get("main_path"), Mapping) else {}
    modular_walls_raw = (
        raw.get("modular_walls") if isinstance(raw, Mapping) and isinstance(raw.get("modular_walls"), Mapping) else {}
    )
    return {
        "room_size": _positive_vector3(raw.get("room_size") if isinstance(raw, Mapping) else None, default=room_size_default),
        "density": _density(raw.get("density") if isinstance(raw, Mapping) else None),
        "avoid_intersections": raw.get("avoid_intersections") if isinstance(raw.get("avoid_intersections"), bool) else True,
        "focal_point": _string_value(raw.get("focal_point")) if isinstance(raw, Mapping) else None,
        "main_path": {
            "from": _string_value(main_path_raw.get("from")) if isinstance(main_path_raw, Mapping) else None,
            "to": _string_value(main_path_raw.get("to")) if isinstance(main_path_raw, Mapping) else None,
            "width": _positive_number(main_path_raw.get("width") if isinstance(main_path_raw, Mapping) else None, 1.0),
        },
        "modular_walls": _modular_wall_contract(modular_walls_raw, regions),
    }


def _modular_wall_contract(raw: Mapping[str, Any], regions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    enabled = raw.get("enabled") if isinstance(raw.get("enabled"), bool) else bool(raw)
    region_ids = _modular_wall_region_ids(raw.get("regions"), regions=regions, enabled=enabled)
    sides = _modular_wall_sides(raw.get("sides"), enabled=enabled)
    return {
        "enabled": enabled,
        "regions": region_ids,
        "sides": sides,
        "module_length": _positive_number(raw.get("module_length"), 2.0),
        "snap_grid": _positive_number(raw.get("snap_grid"), 1.0),
        "height": _positive_number(raw.get("height"), 3.0),
        "thickness": _positive_number(raw.get("thickness"), 0.2),
    }


def _modular_wall_region_ids(value: object, *, regions: Sequence[Mapping[str, Any]], enabled: bool) -> list[str]:
    if not enabled:
        return []
    if isinstance(value, list):
        seen: set[str] = set()
        region_ids: list[str] = []
        for item in value:
            if isinstance(item, str) and item.startswith("region_") and item not in seen:
                seen.add(item)
                region_ids.append(item)
        if region_ids:
            return sorted(region_ids)
    return sorted(str(region["region_id"]) for region in regions if isinstance(region.get("region_id"), str))


def _modular_wall_sides(value: object, *, enabled: bool) -> list[str]:
    if not enabled:
        return []
    allowed = ("north", "south", "east", "west")
    if isinstance(value, list):
        sides = [item for item in allowed if item in value]
        if sides:
            return sides
    return list(allowed)


def _room_size_from_regions(regions: Sequence[Mapping[str, Any]]) -> tuple[float, float, float]:
    if not regions:
        return (1.0, 1.0, 1.0)
    min_values = [min(float(region["min"][axis]) for region in regions) for axis in range(3)]
    max_values = [max(float(region["max"][axis]) for region in regions) for axis in range(3)]
    return tuple(max(max_values[axis] - min_values[axis], 1.0) for axis in range(3))


def _density(value: object) -> str:
    return value if value in {"sparse", "medium", "dense"} else "medium"


def _positive_number(value: object, default: float) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float) and value > 0:
        return float(value)
    return default


def _placements(
    scene_graph: Mapping[str, Any],
    regions_by_id: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for source_index, item in sorted(
        _items(scene_graph, "objects"),
        key=lambda entry: (_string_field(entry[1], "object_id") or "", entry[0]),
    ):
        object_id = _string_field(item, "object_id")
        if object_id is None:
            continue
        region_id = _string_field(item, "region") or "region_unassigned"
        region = regions_by_id.get(region_id)
        transform = item.get("transform") if isinstance(item.get("transform"), Mapping) else {}
        anchor = "authored_transform"
        if not isinstance(transform, Mapping) or "position" not in transform:
            anchor = "region_center_fallback" if region is not None else "origin_fallback"
            diagnostics.append(
                _diagnostic(
                    "LP1001",
                    "object_transform_missing",
                    _json_pointer("objects", source_index, "transform"),
                    f"Object {object_id!r} has no authored transform; using a deterministic fallback.",
                    severity="warning",
                    details={"object_id": object_id},
                )
            )
        fallback_position = region["center"] if region is not None else (0, 0, 0)
        position = _vector3(transform.get("position") if isinstance(transform, Mapping) else None, default=fallback_position)
        rotation = _vector3(transform.get("rotation") if isinstance(transform, Mapping) else None, default=(0, 0, 0))
        scale = _positive_vector3(transform.get("scale") if isinstance(transform, Mapping) else None, default=(1, 1, 1))
        footprint = _footprint(scale)
        bounds_min, bounds_max = _bounds_min_max(position, footprint)
        inside_region = region is not None and _bounds_inside(bounds_min, bounds_max, region)
        if region is None:
            diagnostics.append(
                _diagnostic(
                    "LP1002",
                    "object_region_missing",
                    _json_pointer("objects", source_index, "region"),
                    f"Object {object_id!r} does not reference a known region.",
                    details={"object_id": object_id, "region_id": region_id},
                )
            )
        elif not inside_region:
            diagnostics.append(
                _diagnostic(
                    "LP2001",
                    "object_outside_region_bounds",
                    _json_pointer("objects", source_index, "transform", "position"),
                    f"Object {object_id!r} footprint is outside region {region_id!r} bounds.",
                    details={"object_id": object_id, "region_id": region_id},
                )
            )
        records.append(
            {
                "object_id": object_id,
                "region_id": region_id,
                "position": position,
                "rotation": rotation,
                "scale": scale,
                "footprint": footprint,
                "bounds": {"min": bounds_min, "max": bounds_max},
                "anchor": anchor,
                "inside_region": inside_region,
                "source_index": source_index,
            }
        )
    return records, diagnostics


def _footprint(scale: Sequence[float]) -> list[float]:
    return [round(max(abs(float(component)), 0.25), 6) for component in scale]


def _bounds_inside(minimum: Sequence[float], maximum: Sequence[float], region: Mapping[str, Any]) -> bool:
    region_min = region["min"]
    region_max = region["max"]
    return all(float(minimum[index]) >= float(region_min[index]) for index in range(3)) and all(
        float(maximum[index]) <= float(region_max[index]) for index in range(3)
    )


def _wall_segments(
    layout_contract: Mapping[str, Any],
    regions_by_id: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    wall_contract = layout_contract.get("modular_walls")
    if not isinstance(wall_contract, Mapping) or not wall_contract.get("enabled"):
        return [], []

    segments: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for region_id in wall_contract.get("regions", []):
        if not isinstance(region_id, str):
            continue
        region = regions_by_id.get(region_id)
        if region is None:
            diagnostics.append(
                _diagnostic(
                    "LP2004",
                    "modular_wall_region_missing",
                    "/layout/modular_walls/regions",
                    f"Modular wall region {region_id!r} does not reference a known region.",
                    details={"region_id": region_id},
                )
            )
            continue
        for side in wall_contract.get("sides", []):
            if not isinstance(side, str):
                continue
            new_segments = _wall_segments_for_side(region=region, side=side, wall_contract=wall_contract)
            segments.extend(new_segments)
            diagnostics.extend(_wall_alignment_diagnostics(new_segments))
    return segments, diagnostics


def _wall_segments_for_side(
    *,
    region: Mapping[str, Any],
    side: str,
    wall_contract: Mapping[str, Any],
) -> list[dict[str, Any]]:
    region_id = str(region["region_id"])
    region_min = region["min"]
    length_axis = 0 if side in {"north", "south"} else 1
    side_length = max(float(region["size"][length_axis]), 0.25)
    module_length = min(float(wall_contract["module_length"]), side_length)
    module_count = max(1, math.floor(side_length / module_length))
    covered_length = module_count * module_length
    start = -covered_length / 2 + module_length / 2
    center_z = round(float(region_min[2]) + float(wall_contract["height"]) / 2, 6)
    segments: list[dict[str, Any]] = []
    for module_index in range(module_count):
        offset = start + module_index * module_length
        center = _wall_segment_center(region=region, side=side, offset=offset, z=center_z)
        length = round(module_length, 6)
        thickness = round(float(wall_contract["thickness"]), 6)
        height = round(float(wall_contract["height"]), 6)
        bounds = _wall_segment_bounds(
            center=center,
            side=side,
            length=length,
            height=height,
            thickness=thickness,
        )
        segments.append(
            {
                "segment_id": f"wall_{_slug(region_id.removeprefix('region_'), max_length=56)}_{side}_{module_index:03d}",
                "region_id": region_id,
                "side": side,
                "module_index": module_index,
                "center": center,
                "rotation": [0.0, 0.0, 90.0] if side in {"east", "west"} else [0.0, 0.0, 0.0],
                "length": length,
                "height": height,
                "thickness": thickness,
                "snap_grid": round(float(wall_contract["snap_grid"]), 6),
                "bounds": bounds,
                "aligned_to_grid": _wall_segment_aligned_to_grid(center=center, length=length, grid=float(wall_contract["snap_grid"])),
                "source": "layout.modular_walls",
            }
        )
    return segments


def _wall_segment_center(*, region: Mapping[str, Any], side: str, offset: float, z: float) -> list[float]:
    center = region["center"]
    region_min = region["min"]
    region_max = region["max"]
    if side == "north":
        return [round(float(center[0]) + offset, 6), round(float(region_max[1]), 6), z]
    if side == "south":
        return [round(float(center[0]) + offset, 6), round(float(region_min[1]), 6), z]
    if side == "east":
        return [round(float(region_max[0]), 6), round(float(center[1]) + offset, 6), z]
    return [round(float(region_min[0]), 6), round(float(center[1]) + offset, 6), z]


def _wall_segment_bounds(
    *,
    center: Sequence[float],
    side: str,
    length: float,
    height: float,
    thickness: float,
) -> dict[str, list[float]]:
    half_length = length / 2
    half_thickness = thickness / 2
    if side in {"north", "south"}:
        minimum = [float(center[0]) - half_length, float(center[1]) - half_thickness, float(center[2]) - height / 2]
        maximum = [float(center[0]) + half_length, float(center[1]) + half_thickness, float(center[2]) + height / 2]
    else:
        minimum = [float(center[0]) - half_thickness, float(center[1]) - half_length, float(center[2]) - height / 2]
        maximum = [float(center[0]) + half_thickness, float(center[1]) + half_length, float(center[2]) + height / 2]
    return {
        "min": [round(value, 6) for value in minimum],
        "max": [round(value, 6) for value in maximum],
    }


def _wall_segment_aligned_to_grid(*, center: Sequence[float], length: float, grid: float) -> bool:
    return _is_on_grid(float(center[0]), grid) and _is_on_grid(float(center[1]), grid) and _is_on_grid(length, grid)


def _is_on_grid(value: float, grid: float) -> bool:
    if grid <= 0:
        return False
    nearest = round(value / grid) * grid
    return math.isclose(value, nearest, abs_tol=1e-6)


def _wall_alignment_diagnostics(segments: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for segment in segments:
        if segment.get("aligned_to_grid"):
            continue
        diagnostics.append(
            _diagnostic(
                "LP2005",
                "modular_wall_segment_off_grid",
                "/wall_segments",
                f"Modular wall segment {segment['segment_id']!r} is not aligned to its snap grid.",
                severity="warning",
                details={
                    "segment_id": str(segment["segment_id"]),
                    "region_id": str(segment["region_id"]),
                    "side": str(segment["side"]),
                    "snap_grid": segment.get("snap_grid"),
                },
            )
        )
    return diagnostics


def _intersections(placements: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for left_index, left in enumerate(placements):
        for right in placements[left_index + 1 :]:
            if left["region_id"] != right["region_id"]:
                continue
            overlap = _xy_overlap(left["bounds"], right["bounds"])
            if overlap is None:
                continue
            records.append(
                {
                    "object_a": left["object_id"],
                    "object_b": right["object_id"],
                    "region_id": left["region_id"],
                    "overlap": overlap,
                }
            )
    return records


def _xy_overlap(left_bounds: Mapping[str, Any], right_bounds: Mapping[str, Any]) -> list[float] | None:
    left_min = left_bounds["min"]
    left_max = left_bounds["max"]
    right_min = right_bounds["min"]
    right_max = right_bounds["max"]
    overlap_x = min(float(left_max[0]), float(right_max[0])) - max(float(left_min[0]), float(right_min[0]))
    overlap_y = min(float(left_max[1]), float(right_max[1])) - max(float(left_min[1]), float(right_min[1]))
    if overlap_x <= 0 or overlap_y <= 0:
        return None
    return [round(overlap_x, 6), round(overlap_y, 6)]


def _intersection_diagnostics(intersections: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        _diagnostic(
            "LP2002",
            "object_footprints_intersect",
            "/intersections",
            f"Object footprints {item['object_a']!r} and {item['object_b']!r} intersect.",
            details={
                "object_a": str(item["object_a"]),
                "object_b": str(item["object_b"]),
                "region_id": str(item["region_id"]),
                "overlap": list(item["overlap"]),
            },
        )
        for item in intersections
    ]


def _path_plan(
    scene_graph: Mapping[str, Any],
    layout_contract: Mapping[str, Any],
    regions_by_id: Mapping[str, Mapping[str, Any]],
    placements: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    main_path = layout_contract["main_path"]
    start_ref = main_path["from"]
    end_ref = main_path["to"] or layout_contract.get("focal_point")
    positions = _entity_positions(scene_graph, regions_by_id, placements)
    start = positions.get(start_ref)
    end = positions.get(end_ref)
    waypoints = [start, end] if start is not None and end is not None else []
    blocked_by = _path_blockers(placements, start, end, float(main_path["width"]), {start_ref, end_ref})
    return {
        "from": start_ref,
        "to": end_ref,
        "width": main_path["width"],
        "waypoints": waypoints,
        "blocked_by": blocked_by,
    }


def _entity_positions(
    scene_graph: Mapping[str, Any],
    regions_by_id: Mapping[str, Mapping[str, Any]],
    placements: Sequence[Mapping[str, Any]],
) -> dict[str | None, list[float]]:
    positions: dict[str | None, list[float]] = {region_id: list(region["center"]) for region_id, region in regions_by_id.items()}
    for placement in placements:
        positions[str(placement["object_id"])] = list(placement["position"])
    for _index, camera in _items(scene_graph, "cameras"):
        camera_id = _string_field(camera, "camera_id")
        transform = camera.get("transform") if isinstance(camera.get("transform"), Mapping) else {}
        if camera_id is not None and isinstance(transform, Mapping) and "position" in transform:
            positions[camera_id] = _vector3(transform.get("position"), default=(0, 0, 0))
    for _index, light in _items(scene_graph, "lights"):
        light_id = _string_field(light, "light_id")
        if light_id is not None:
            target = _string_field(light, "target")
            positions[light_id] = list(positions.get(target, (0, 0, 0)))
    return positions


def _path_blockers(
    placements: Sequence[Mapping[str, Any]],
    start: Sequence[float] | None,
    end: Sequence[float] | None,
    width: float,
    endpoints: set[str | None],
) -> list[str]:
    if start is None or end is None:
        return []
    blocked: list[str] = []
    for placement in placements:
        object_id = str(placement["object_id"])
        if object_id in endpoints:
            continue
        radius = max(float(placement["footprint"][0]), float(placement["footprint"][1])) / 2
        distance = _point_segment_distance_xy(placement["position"], start, end)
        if distance <= width / 2 + radius:
            blocked.append(object_id)
    return sorted(blocked)


def _point_segment_distance_xy(point: Sequence[float], start: Sequence[float], end: Sequence[float]) -> float:
    px, py = float(point[0]), float(point[1])
    ax, ay = float(start[0]), float(start[1])
    bx, by = float(end[0]), float(end[1])
    dx = bx - ax
    dy = by - ay
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    closest_x = ax + t * dx
    closest_y = ay + t * dy
    return math.hypot(px - closest_x, py - closest_y)


def _object_source(object_id: str, item: Mapping[str, Any]) -> dict[str, Any]:
    for field in _SOURCE_FIELDS:
        value = _string_field(item, field)
        if value is not None:
            return {
                "kind": field,
                "ref": value,
                "generated": False,
            }
    return {
        "kind": "generated_fallback",
        "ref": object_id,
        "generated": True,
    }


def _field_payload(item: Mapping[str, Any], fields: Sequence[str]) -> dict[str, Any]:
    return {field: _normal_json(item[field]) for field in fields if field in item}


def _reuse_policy(style_pack: Mapping[str, Any] | None) -> tuple[tuple[str, ...], tuple[str, ...], bool]:
    if not isinstance(style_pack, Mapping):
        return _DEFAULT_ASSET_SIGNATURE_FIELDS, _DEFAULT_INSTANCE_OVERRIDE_FIELDS, True
    raw = style_pack.get("reuse_policy")
    if not isinstance(raw, Mapping):
        return _DEFAULT_ASSET_SIGNATURE_FIELDS, _DEFAULT_INSTANCE_OVERRIDE_FIELDS, True
    asset_fields = _field_list(raw.get("asset_signature_fields"), fallback=_DEFAULT_ASSET_SIGNATURE_FIELDS)
    instance_fields = _field_list(raw.get("instance_override_fields"), fallback=_DEFAULT_INSTANCE_OVERRIDE_FIELDS)
    allow_shared = raw.get("allow_shared_assets") if isinstance(raw.get("allow_shared_assets"), bool) else True
    return asset_fields, instance_fields, allow_shared


def _field_list(value: object, *, fallback: Sequence[str]) -> tuple[str, ...]:
    if not isinstance(value, list):
        return tuple(fallback)
    fields: list[str] = []
    for item in value:
        if isinstance(item, str) and item in _ALLOWED_REUSE_FIELDS and item not in fields:
            fields.append(item)
    return tuple(fields or fallback)


def _check_unique_placements(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    placements = payload.get("placements", [])
    if not isinstance(placements, list):
        return diagnostics
    for index, placement in enumerate(placements):
        if not isinstance(placement, Mapping):
            continue
        object_id = _string_field(placement, "object_id")
        if object_id is None:
            continue
        path = _json_pointer("placements", index, "object_id")
        first_path = seen.get(object_id)
        if first_path is None:
            seen[object_id] = path
            continue
        diagnostics.append(
            _diagnostic(
                "LP3001",
                "duplicate_layout_plan_object_id",
                path,
                f"Layout Plan placement object_id {object_id!r} duplicates the placement at {first_path}.",
                details={"object_id": object_id, "first_path": first_path},
            )
        )
    return diagnostics


__all__ = [
    "LAYOUT_PLAN_CONTRACT",
    "LAYOUT_PLAN_SCHEMA_FILENAME",
    "LAYOUT_PLAN_VERSION",
    "get_layout_plan_schema",
    "instancing_metadata_by_object_id",
    "load_and_plan_layout",
    "plan_instance_reuse",
    "plan_layout",
    "validate_layout_plan_payload",
]
