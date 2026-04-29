"""Deterministic camera and lighting system helpers for Wonder scenes."""

from __future__ import annotations

import math
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

CAMERA_LIGHTING_PLAN_VERSION = "lathe.camera_lighting_plan.v1"
CAMERA_LIGHTING_CONTRACT = "camera_lighting_plan"

_FRAMING_DEFAULTS: dict[str, dict[str, Any]] = {
    "cinematic_wide": {"offset": [-6.0, -6.0, 3.0], "fov_degrees": 50.0},
    "inspection": {"offset": [-2.5, -2.0, 1.5], "fov_degrees": 38.0},
    "topdown": {"offset": [0.0, 0.0, 8.0], "fov_degrees": 60.0},
    "debug": {"offset": [-4.0, -4.0, 4.0], "fov_degrees": 55.0},
    "contact_sheet": {"offset": [0.0, -7.0, 4.0], "fov_degrees": 65.0},
    "before_after": {"offset": [-5.0, -5.0, 3.0], "fov_degrees": 50.0},
}


def plan_camera_lighting(
    scene_graph: Mapping[str, Any],
    *,
    layout_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return deterministic camera, lighting, and shot-link records for a Scene Graph."""
    if not isinstance(scene_graph, Mapping):
        raise ValueError("scene_graph must be a mapping")

    diagnostics: list[dict[str, Any]] = []
    positions = _entity_positions(scene_graph, layout_plan)
    cameras, camera_diagnostics = _camera_records(scene_graph, positions)
    lights, light_diagnostics = _light_records(scene_graph, positions)
    diagnostics.extend(camera_diagnostics)
    diagnostics.extend(light_diagnostics)
    return {
        "schema_version": CAMERA_LIGHTING_PLAN_VERSION,
        "scene_id": _string_value(scene_graph.get("scene_id")) or "scene",
        "generated_by": "lathe.scene.camera_lighting",
        "cameras": cameras,
        "lights": lights,
        "links": _links(cameras, lights),
        "diagnostics": diagnostics,
    }


def validate_camera_lighting(
    scene_graph: Mapping[str, Any],
    *,
    layout_plan: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return deterministic camera and lighting diagnostics for a Scene Graph."""
    return plan_camera_lighting(scene_graph, layout_plan=layout_plan)["diagnostics"]


def _diagnostic(
    code: str,
    name: str,
    path: str,
    message: str,
    *,
    severity: str = "error",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "name": name,
        "severity": severity,
        "contract": CAMERA_LIGHTING_CONTRACT,
        "phase": "camera_lighting_planning",
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


def _number_value(value: object, *, default: float) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float):
        return float(value)
    return default


def _vector3(value: object, *, default: Sequence[float]) -> list[float]:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray) and len(value) == 3:
        result: list[float] = []
        for item in value:
            if isinstance(item, bool) or not isinstance(item, int | float):
                return [float(default[0]), float(default[1]), float(default[2])]
            result.append(float(item))
        return result
    return [float(default[0]), float(default[1]), float(default[2])]


def _entity_positions(
    scene_graph: Mapping[str, Any],
    layout_plan: Mapping[str, Any] | None,
) -> dict[str, list[float]]:
    positions: dict[str, list[float]] = {}
    if isinstance(layout_plan, Mapping):
        for _index, region in _items(layout_plan, "regions"):
            region_id = _string_field(region, "region_id")
            if region_id is not None:
                positions[region_id] = _vector3(region.get("center"), default=(0, 0, 0))
        for _index, placement in _items(layout_plan, "placements"):
            object_id = _string_field(placement, "object_id")
            if object_id is not None:
                positions[object_id] = _vector3(placement.get("position"), default=(0, 0, 0))

    for _index, region in _items(scene_graph, "regions"):
        region_id = _string_field(region, "region_id")
        bounds = region.get("bounds") if isinstance(region.get("bounds"), Mapping) else {}
        if region_id is not None and region_id not in positions:
            positions[region_id] = _vector3(bounds.get("center") if isinstance(bounds, Mapping) else None, default=(0, 0, 0))
    for _index, item in _items(scene_graph, "objects"):
        object_id = _string_field(item, "object_id")
        transform = item.get("transform") if isinstance(item.get("transform"), Mapping) else {}
        if object_id is not None and object_id not in positions and isinstance(transform, Mapping):
            positions[object_id] = _vector3(transform.get("position"), default=(0, 0, 0))
    return positions


def _camera_records(
    scene_graph: Mapping[str, Any],
    positions: Mapping[str, Sequence[float]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for source_index, camera in sorted(
        _items(scene_graph, "cameras"),
        key=lambda item: (_string_field(item[1], "camera_id") or "", item[0]),
    ):
        camera_id = _string_field(camera, "camera_id")
        if camera_id is None:
            continue
        framing = _string_field(camera, "framing") or "inspection"
        target = _string_field(camera, "target")
        target_position = positions.get(target or "")
        if target is not None and target_position is None:
            diagnostics.append(
                _diagnostic(
                    "CL1001",
                    "camera_target_position_missing",
                    _json_pointer("cameras", source_index, "target"),
                    f"Camera {camera_id!r} target {target!r} has no known position.",
                    details={"camera_id": camera_id, "target": target},
                )
            )
        resolved_target = list(target_position) if target_position is not None else [0.0, 0.0, 0.0]
        authored_transform = camera.get("transform") if isinstance(camera.get("transform"), Mapping) else {}
        has_authored_position = isinstance(authored_transform, Mapping) and "position" in authored_transform
        position = _camera_position(authored_transform, framing, resolved_target)
        if not has_authored_position:
            diagnostics.append(
                _diagnostic(
                    "CL1002",
                    "camera_transform_missing",
                    _json_pointer("cameras", source_index, "transform"),
                    f"Camera {camera_id!r} has no authored position; using framing defaults.",
                    severity="warning",
                    details={"camera_id": camera_id, "framing": framing},
                )
            )
        fov = _camera_fov(camera, framing)
        if fov <= 0 or fov > 120:
            diagnostics.append(
                _diagnostic(
                    "CL2001",
                    "camera_fov_outside_readiness_range",
                    _json_pointer("cameras", source_index, "fov_degrees"),
                    f"Camera {camera_id!r} FOV {fov:g} is outside the readiness range (0, 120].",
                    details={"camera_id": camera_id, "fov_degrees": fov},
                )
            )
        records.append(
            {
                "camera_id": camera_id,
                "target": target,
                "framing": framing,
                "purpose": _string_field(camera, "purpose") or camera_id,
                "position": position,
                "target_position": resolved_target,
                "view_vector": _unit_vector(position, resolved_target),
                "distance_to_target": round(_distance(position, resolved_target), 6),
                "fov_degrees": fov,
                "authored_transform": has_authored_position,
                "source_index": source_index,
            }
        )
    return records, diagnostics


def _camera_position(
    transform: object,
    framing: str,
    target_position: Sequence[float],
) -> list[float]:
    if isinstance(transform, Mapping) and "position" in transform:
        return _vector3(transform.get("position"), default=(0, 0, 0))
    defaults = _FRAMING_DEFAULTS.get(framing, _FRAMING_DEFAULTS["inspection"])
    offset = defaults["offset"]
    return [round(float(target_position[index]) + float(offset[index]), 6) for index in range(3)]


def _camera_fov(camera: Mapping[str, Any], framing: str) -> float:
    defaults = _FRAMING_DEFAULTS.get(framing, _FRAMING_DEFAULTS["inspection"])
    return _number_value(camera.get("fov_degrees"), default=float(defaults["fov_degrees"]))


def _light_records(
    scene_graph: Mapping[str, Any],
    positions: Mapping[str, Sequence[float]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    scene_center = _scene_center(positions)
    for source_index, light in sorted(
        _items(scene_graph, "lights"),
        key=lambda item: (_string_field(item[1], "light_id") or "", item[0]),
    ):
        light_id = _string_field(light, "light_id")
        if light_id is None:
            continue
        target = _string_field(light, "target")
        target_position = positions.get(target or "")
        if target is not None and target_position is None:
            diagnostics.append(
                _diagnostic(
                    "CL1003",
                    "light_target_position_missing",
                    _json_pointer("lights", source_index, "target"),
                    f"Light {light_id!r} target {target!r} has no known position.",
                    details={"light_id": light_id, "target": target},
                )
            )
        intensity = _number_value(light.get("intensity"), default=1.0)
        if intensity <= 0:
            diagnostics.append(
                _diagnostic(
                    "CL2002",
                    "light_intensity_not_positive",
                    _json_pointer("lights", source_index, "intensity"),
                    f"Light {light_id!r} has non-positive intensity.",
                    severity="warning",
                    details={"light_id": light_id, "intensity": intensity},
                )
            )
        light_type = _string_field(light, "type") or "point"
        records.append(
            {
                "light_id": light_id,
                "type": light_type,
                "role": _light_role(light_type, intensity),
                "target": target,
                "target_position": list(target_position) if target_position is not None else scene_center,
                "color": _string_field(light, "color") or "white",
                "intensity": intensity,
                "effective_radius": _effective_radius(light_type, intensity),
                "purpose": _string_field(light, "purpose") or light_id,
                "source_index": source_index,
            }
        )
    return records, diagnostics


def _scene_center(positions: Mapping[str, Sequence[float]]) -> list[float]:
    if not positions:
        return [0.0, 0.0, 0.0]
    values = list(positions.values())
    return [round(sum(float(position[index]) for position in values) / len(values), 6) for index in range(3)]


def _light_role(light_type: str, intensity: float) -> str:
    if light_type in {"directional", "moonbeam"} or intensity >= 0.7:
        return "key"
    if light_type in {"area", "spot"}:
        return "fill"
    if light_type in {"point", "emissive_practical", "candle_cluster"}:
        return "practical"
    return "accent"


def _effective_radius(light_type: str, intensity: float) -> float | None:
    if light_type in {"directional", "moonbeam"}:
        return None
    return round(math.sqrt(max(intensity, 0.0)) * 8.0, 6)


def _links(cameras: Sequence[Mapping[str, Any]], lights: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for camera in cameras:
        target = camera.get("target")
        linked = sorted(
            str(light["light_id"]) for light in lights if light.get("target") in {target, None}
        )
        records.append(
            {
                "camera_id": camera["camera_id"],
                "target": target,
                "light_ids": linked,
            }
        )
    return records


def _unit_vector(position: Sequence[float], target: Sequence[float]) -> list[float]:
    delta = [float(target[index]) - float(position[index]) for index in range(3)]
    length = math.sqrt(sum(component * component for component in delta))
    if length == 0:
        return [0.0, 0.0, 0.0]
    return [round(component / length, 6) for component in delta]


def _distance(left: Sequence[float], right: Sequence[float]) -> float:
    return math.sqrt(sum((float(left[index]) - float(right[index])) ** 2 for index in range(3)))


__all__ = [
    "CAMERA_LIGHTING_CONTRACT",
    "CAMERA_LIGHTING_PLAN_VERSION",
    "plan_camera_lighting",
    "validate_camera_lighting",
]
