"""Roblox profile validation and manifest helpers for Wonder scenes."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lathe.paths import PathGuardError, safe_resolve

from .io import write_bytes_atomic, write_json_atomic, write_text_atomic

ROBLOX_PROFILE_VERSION = "lathe.roblox_profile.v1"
ROBLOX_MANIFEST_VERSION = "lathe.roblox_manifest.v1"
ROBLOX_EXPORT_BUNDLE_VERSION = "lathe.roblox_export_bundle.v1"
ROBLOX_IMPORT_INSTRUCTIONS_VERSION = "lathe.roblox_import_instructions.v1"
ROBLOX_ASSET_KIT_STACK_ID = "lathe.stack.roblox_asset_kit_v1"
ROBLOX_PROFILE_SCHEMA_FILENAME = "roblox_profile.schema.json"
ROBLOX_MANIFEST_SCHEMA_FILENAME = "roblox_manifest.schema.json"
ROBLOX_PROFILE_CONTRACT = "roblox_profile"
ROBLOX_MANIFEST_CONTRACT = "roblox_manifest"

ROBLOX_LOW_POLY_PROFILE: dict[str, Any] = {
    "schema_version": ROBLOX_PROFILE_VERSION,
    "profile_id": "roblox_lowpoly",
    "display_name": "Roblox Lowpoly",
    "units": {"length": "studs", "scale": 1.0},
    "budgets": {
        "max_scene_triangles": 50000,
        "max_mesh_triangles": 5000,
        "max_meshes": 64,
        "max_textures": 128,
        "max_texture_resolution": 1024,
        "max_materials": 64,
        "max_materials_per_mesh": 4,
    },
    "mesh": {
        "max_meshes_per_object": 1,
        "prefer_shared_meshes": True,
    },
    "collision": {
        "required": True,
        "required_roles": [
            "architecture",
            "hero_prop",
            "environment_structure",
            "dressing_prop",
            "navigation",
            "interactive",
            "narrative_clue",
        ],
        "allowed_modes": ["box", "hull", "mesh"],
        "max_primitives_per_object": 4,
    },
    "material": {
        "max_slots_per_mesh": 4,
        "prefer_vertex_colors": True,
        "allow_pbr_textures": True,
    },
    "naming": {
        "policy": "lower_snake_case",
        "pattern": "^[a-z][a-z0-9_]{2,63}$",
        "max_length": 64,
    },
    "pivot": {
        "required": True,
        "required_roles": [
            "architecture",
            "hero_prop",
            "environment_structure",
            "dressing_prop",
            "light_fixture",
            "navigation",
            "interactive",
            "narrative_clue",
        ],
        "allowed_modes": ["base_center", "center", "custom"],
    },
    "snap_grid": {
        "required": True,
        "size_studs": 0.5,
        "tolerance_studs": 0.000001,
        "axes": ["x", "y", "z"],
    },
    "mobile": {
        "target_fps": 60,
        "min_score": 80,
        "component_weights": {
            "triangle": 1,
            "texture": 1,
            "mesh": 1,
            "collision": 1,
            "material": 1,
            "naming": 1,
            "pivot": 1,
            "snap_grid": 1,
        },
    },
}

_SCORE_COMPONENTS = (
    "triangle",
    "texture",
    "mesh",
    "collision",
    "material",
    "naming",
    "pivot",
    "snap_grid",
)
_AXIS_INDEX = {"x": 0, "y": 1, "z": 2}


@dataclass(frozen=True)
class _Metric:
    value: Any
    path: str


@dataclass(frozen=True)
class _ReadinessState:
    required: bool
    present: bool
    mode: str | None
    path: str | None


@dataclass(frozen=True)
class _Analysis:
    objects: list[dict[str, Any]]
    diagnostics: list[dict[str, Any]]
    measured: dict[str, bool]
    totals: dict[str, int | None]


def _schema_root(filename: str) -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / "schema" / filename
        if candidate.exists():
            return candidate.parent
    raise FileNotFoundError(f"Could not locate schema/{filename}")


def get_roblox_profile_schema() -> dict[str, Any]:
    """Return the committed Roblox profile JSON Schema."""
    return json.loads(
        (_schema_root(ROBLOX_PROFILE_SCHEMA_FILENAME) / ROBLOX_PROFILE_SCHEMA_FILENAME).read_text(
            encoding="utf-8"
        )
    )


def get_roblox_manifest_schema() -> dict[str, Any]:
    """Return the committed Roblox manifest JSON Schema."""
    return json.loads(
        (_schema_root(ROBLOX_MANIFEST_SCHEMA_FILENAME) / ROBLOX_MANIFEST_SCHEMA_FILENAME).read_text(
            encoding="utf-8"
        )
    )


def _json_pointer(*parts: object) -> str:
    escaped = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(escaped) if escaped else "/"


def _diagnostic(
    code: str,
    name: str,
    path: str,
    message: str,
    *,
    severity: str = "error",
    details: dict[str, Any] | None = None,
    contract: str = ROBLOX_PROFILE_CONTRACT,
    phase: str = "roblox_profile_semantics",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "name": name,
        "severity": severity,
        "contract": contract,
        "phase": phase,
        "path": path,
        "message": message,
    }
    if details:
        payload["details"] = details
    return payload


def _schema_diagnostics(
    payload: Mapping[str, Any],
    *,
    schema: Mapping[str, Any],
    code: str,
    contract: str,
    phase: str,
) -> list[dict[str, Any]]:
    import jsonschema

    validator = jsonschema.Draft202012Validator(schema)
    diagnostics: list[dict[str, Any]] = []
    for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path)):
        diagnostics.append(
            _diagnostic(
                code,
                "schema_validation",
                _json_pointer(*error.absolute_path),
                error.message,
                contract=contract,
                phase=phase,
            )
        )
    return diagnostics


def validate_roblox_profile_payload(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return JSON-schema diagnostics for a Roblox profile payload."""
    return _schema_diagnostics(
        payload,
        schema=get_roblox_profile_schema(),
        code="ROBLOX_PROFILE_SCHEMA_VALIDATION",
        contract=ROBLOX_PROFILE_CONTRACT,
        phase="roblox_profile_schema",
    )


def validate_roblox_manifest_payload(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return JSON-schema diagnostics for a Roblox manifest payload."""
    return _schema_diagnostics(
        payload,
        schema=get_roblox_manifest_schema(),
        code="ROBLOX_MANIFEST_SCHEMA_VALIDATION",
        contract=ROBLOX_MANIFEST_CONTRACT,
        phase="roblox_manifest_schema",
    )


def _items(scene_graph: Mapping[str, Any], collection: str) -> Iterator[tuple[int, Mapping[str, Any]]]:
    raw = scene_graph.get(collection, [])
    if not isinstance(raw, list):
        return
    for index, item in enumerate(raw):
        if isinstance(item, Mapping):
            yield index, item


def _string_field(item: Mapping[str, Any], field: str) -> str | None:
    value = item.get(field)
    return value if isinstance(value, str) and value else None


def _mapping_field(item: Mapping[str, Any], field: str) -> Mapping[str, Any]:
    value = item.get(field)
    return value if isinstance(value, Mapping) else {}


def _int_field(item: Mapping[str, Any], field: str, default: int) -> int:
    value = item.get(field)
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return default


def _float_field(item: Mapping[str, Any], field: str, default: float) -> float:
    value = item.get(field)
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float):
        return float(value)
    return default


def _string_list(item: Mapping[str, Any], field: str) -> list[str]:
    value = item.get(field)
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, str)]


def _profile_section(profile: Mapping[str, Any], section: str) -> Mapping[str, Any]:
    value = profile.get(section)
    return value if isinstance(value, Mapping) else {}


def _metric_sources(index: int, item: Mapping[str, Any]) -> Iterator[tuple[str, Mapping[str, Any]]]:
    for field in ("metadata", "roblox", "state"):
        value = item.get(field)
        if not isinstance(value, Mapping):
            continue
        yield _json_pointer("objects", index, field), value
        nested = value.get("roblox")
        if isinstance(nested, Mapping):
            yield _json_pointer("objects", index, field, "roblox"), nested


def _metric(index: int, item: Mapping[str, Any], keys: Sequence[str]) -> _Metric | None:
    for base_path, source in _metric_sources(index, item):
        for key in keys:
            if key in source:
                return _Metric(source[key], f"{base_path}/{key}")
    return None


def _non_negative_int(metric: _Metric | None) -> int | None:
    if metric is None or isinstance(metric.value, bool):
        return None
    if isinstance(metric.value, int) and metric.value >= 0:
        return metric.value
    if isinstance(metric.value, float) and metric.value.is_integer() and metric.value >= 0:
        return int(metric.value)
    return None


def _bool_or_mode_state(
    metric: _Metric | None, mode_metric: _Metric | None
) -> tuple[bool, str | None, str | None]:
    if mode_metric is not None and isinstance(mode_metric.value, str):
        mode = mode_metric.value.strip().lower()
        return mode not in {"", "none", "false", "off"}, mode or None, mode_metric.path
    if metric is None:
        return False, None, None
    value = metric.value
    if isinstance(value, bool):
        return value, None, metric.path
    if isinstance(value, str):
        mode = value.strip().lower()
        return mode not in {"", "none", "false", "off"}, mode or None, metric.path
    return False, None, metric.path


def _role_requires(profile_section: Mapping[str, Any], role: str | None) -> bool:
    if profile_section.get("required") is not True:
        return False
    required_roles = _string_list(profile_section, "required_roles")
    if not required_roles:
        return True
    return role in required_roles


def _collision_state(profile: Mapping[str, Any], index: int, item: Mapping[str, Any]) -> _ReadinessState:
    section = _profile_section(profile, "collision")
    role = _string_field(item, "role")
    metric = _metric(index, item, ("collision", "has_collision", "collision_present"))
    mode_metric = _metric(index, item, ("collision_mode", "collision_shape"))
    present, mode, path = _bool_or_mode_state(metric, mode_metric)
    return _ReadinessState(required=_role_requires(section, role), present=present, mode=mode, path=path)


def _pivot_state(profile: Mapping[str, Any], index: int, item: Mapping[str, Any]) -> _ReadinessState:
    section = _profile_section(profile, "pivot")
    role = _string_field(item, "role")
    metric = _metric(index, item, ("pivot", "has_pivot", "pivot_present"))
    mode_metric = _metric(index, item, ("pivot_mode",))
    present, mode, path = _bool_or_mode_state(metric, mode_metric)
    return _ReadinessState(required=_role_requires(section, role), present=present, mode=mode, path=path)


def _position(item: Mapping[str, Any]) -> list[float] | None:
    transform = item.get("transform")
    if not isinstance(transform, Mapping):
        return None
    position = transform.get("position")
    if not isinstance(position, list) or len(position) != 3:
        return None
    if not all(isinstance(value, int | float) and not isinstance(value, bool) for value in position):
        return None
    return [float(value) for value in position]


def _is_on_grid(value: float, grid: float, tolerance: float) -> bool:
    if grid <= 0:
        return True
    nearest = round(value / grid) * grid
    return abs(value - nearest) <= tolerance


def _snap_grid_state(profile: Mapping[str, Any], item: Mapping[str, Any]) -> dict[str, Any]:
    section = _profile_section(profile, "snap_grid")
    required = section.get("required") is True
    grid_size = _float_field(section, "size_studs", 0.5)
    tolerance = _float_field(section, "tolerance_studs", 0.000001)
    axes = [axis for axis in _string_list(section, "axes") if axis in _AXIS_INDEX]
    position = _position(item)
    off_grid_axes: list[str] = []
    if position is not None:
        for axis in axes:
            axis_index = _AXIS_INDEX[axis]
            if not _is_on_grid(position[axis_index], grid_size, tolerance):
                off_grid_axes.append(axis)
    return {
        "required": required,
        "grid_size_studs": grid_size,
        "tolerance_studs": tolerance,
        "axes": axes,
        "on_grid": not off_grid_axes,
        "off_grid_axes": off_grid_axes,
    }


def _source_name(index: int, item: Mapping[str, Any]) -> str:
    return (
        _string_field(item, "lathe_asset")
        or _string_field(item, "source_asset")
        or _string_field(item, "object_id")
        or f"object_{index:03d}"
    )


def _safe_name_pattern(profile: Mapping[str, Any]) -> re.Pattern[str]:
    naming = _profile_section(profile, "naming")
    pattern = _string_field(naming, "pattern") or r"^[a-z][a-z0-9_]{2,63}$"
    return re.compile(pattern)


def _material_slot_count(item: Mapping[str, Any], index: int) -> tuple[int, str]:
    metric = _metric(index, item, ("material_slots", "material_slot_count", "roblox_material_slots"))
    value = _non_negative_int(metric)
    if value is not None:
        return value, metric.path if metric is not None else _json_pointer("objects", index)
    bindings = item.get("material_bindings")
    if isinstance(bindings, list):
        return sum(1 for binding in bindings if isinstance(binding, Mapping)), _json_pointer(
            "objects", index, "material_bindings"
        )
    return 0, _json_pointer("objects", index, "material_bindings")


def _budget_diagnostic(
    code: str,
    name: str,
    path: str,
    message: str,
    *,
    component: str,
    details: dict[str, Any],
) -> dict[str, Any]:
    return _diagnostic(code, name, path, message, details={**details, "score_component": component})


def _object_metrics(index: int, item: Mapping[str, Any]) -> dict[str, Any]:
    triangle_metric = _metric(index, item, ("triangle_count", "triangles", "roblox_triangle_count"))
    mesh_metric = _metric(index, item, ("mesh_count", "meshes", "roblox_mesh_count"))
    texture_metric = _metric(index, item, ("texture_count", "textures", "roblox_texture_count"))
    resolution_metric = _metric(
        index,
        item,
        ("max_texture_resolution", "texture_resolution", "roblox_texture_resolution"),
    )
    material_slots, material_slots_path = _material_slot_count(item, index)
    return {
        "triangle_count": _non_negative_int(triangle_metric),
        "triangle_path": triangle_metric.path if triangle_metric is not None else None,
        "mesh_count": _non_negative_int(mesh_metric),
        "mesh_path": mesh_metric.path if mesh_metric is not None else None,
        "texture_count": _non_negative_int(texture_metric),
        "texture_path": texture_metric.path if texture_metric is not None else None,
        "max_texture_resolution": _non_negative_int(resolution_metric),
        "texture_resolution_path": resolution_metric.path if resolution_metric is not None else None,
        "material_slots": material_slots,
        "material_slots_path": material_slots_path,
    }


def _check_object_budget(
    *,
    index: int,
    item: Mapping[str, Any],
    profile: Mapping[str, Any],
    metrics: Mapping[str, Any],
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    object_id = _string_field(item, "object_id")
    budgets = _profile_section(profile, "budgets")
    mesh = _profile_section(profile, "mesh")
    max_mesh_triangles = _int_field(budgets, "max_mesh_triangles", 5000)
    max_meshes_per_object = _int_field(mesh, "max_meshes_per_object", 1)
    max_texture_resolution = _int_field(budgets, "max_texture_resolution", 1024)
    max_materials_per_mesh = _int_field(budgets, "max_materials_per_mesh", 4)

    triangle_count = metrics.get("triangle_count")
    if isinstance(triangle_count, int) and triangle_count > max_mesh_triangles:
        diagnostics.append(
            _budget_diagnostic(
                "RB2001",
                "mesh_triangle_budget_exceeded",
                str(metrics.get("triangle_path") or _json_pointer("objects", index)),
                f"Object {object_id!r} has {triangle_count} triangles, above the Roblox mesh budget.",
                component="triangle",
                details={
                    "object_id": object_id,
                    "triangle_count": triangle_count,
                    "max_mesh_triangles": max_mesh_triangles,
                },
            )
        )

    mesh_count = metrics.get("mesh_count")
    if isinstance(mesh_count, int) and mesh_count > max_meshes_per_object:
        diagnostics.append(
            _budget_diagnostic(
                "RB2003",
                "object_mesh_budget_exceeded",
                str(metrics.get("mesh_path") or _json_pointer("objects", index)),
                f"Object {object_id!r} uses {mesh_count} meshes, above the per-object Roblox mesh budget.",
                component="mesh",
                details={
                    "object_id": object_id,
                    "mesh_count": mesh_count,
                    "max_meshes_per_object": max_meshes_per_object,
                },
            )
        )

    texture_resolution = metrics.get("max_texture_resolution")
    if isinstance(texture_resolution, int) and texture_resolution > max_texture_resolution:
        diagnostics.append(
            _budget_diagnostic(
                "RB2005",
                "texture_resolution_budget_exceeded",
                str(metrics.get("texture_resolution_path") or _json_pointer("objects", index)),
                f"Object {object_id!r} uses {texture_resolution}px textures, above the Roblox texture budget.",
                component="texture",
                details={
                    "object_id": object_id,
                    "texture_resolution": texture_resolution,
                    "max_texture_resolution": max_texture_resolution,
                },
            )
        )

    material_slots = metrics.get("material_slots")
    if isinstance(material_slots, int) and material_slots > max_materials_per_mesh:
        diagnostics.append(
            _budget_diagnostic(
                "RB2006",
                "material_slot_budget_exceeded",
                str(metrics.get("material_slots_path") or _json_pointer("objects", index)),
                f"Object {object_id!r} uses {material_slots} material slots, above the Roblox material budget.",
                component="material",
                details={
                    "object_id": object_id,
                    "material_slots": material_slots,
                    "max_materials_per_mesh": max_materials_per_mesh,
                },
            )
        )

    return diagnostics


def _check_readiness(
    *,
    index: int,
    item: Mapping[str, Any],
    profile: Mapping[str, Any],
    collision: _ReadinessState,
    pivot: _ReadinessState,
    snap_grid: Mapping[str, Any],
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    object_id = _string_field(item, "object_id")
    role = _string_field(item, "role")
    allowed_collision_modes = set(_string_list(_profile_section(profile, "collision"), "allowed_modes"))
    allowed_pivot_modes = set(_string_list(_profile_section(profile, "pivot"), "allowed_modes"))

    if collision.required and not collision.present:
        diagnostics.append(
            _diagnostic(
                "RB3001",
                "missing_required_collision",
                collision.path or _json_pointer("objects", index),
                f"Object {object_id!r} requires Roblox game-readiness collision metadata.",
                details={"object_id": object_id, "role": role, "score_component": "collision"},
            )
        )
    if (
        collision.present
        and collision.mode is not None
        and allowed_collision_modes
        and collision.mode not in allowed_collision_modes
    ):
        diagnostics.append(
            _diagnostic(
                "RB3002",
                "unsupported_collision_mode",
                collision.path or _json_pointer("objects", index),
                f"Object {object_id!r} uses unsupported Roblox collision mode {collision.mode!r}.",
                details={
                    "object_id": object_id,
                    "mode": collision.mode,
                    "allowed_modes": sorted(allowed_collision_modes),
                    "score_component": "collision",
                },
            )
        )

    if pivot.required and not pivot.present:
        diagnostics.append(
            _diagnostic(
                "RB4001",
                "missing_required_pivot",
                pivot.path or _json_pointer("objects", index),
                f"Object {object_id!r} requires Roblox pivot metadata.",
                details={"object_id": object_id, "role": role, "score_component": "pivot"},
            )
        )
    if (
        pivot.present
        and pivot.mode is not None
        and allowed_pivot_modes
        and pivot.mode not in allowed_pivot_modes
    ):
        diagnostics.append(
            _diagnostic(
                "RB4002",
                "unsupported_pivot_mode",
                pivot.path or _json_pointer("objects", index),
                f"Object {object_id!r} uses unsupported Roblox pivot mode {pivot.mode!r}.",
                details={
                    "object_id": object_id,
                    "mode": pivot.mode,
                    "allowed_modes": sorted(allowed_pivot_modes),
                    "score_component": "pivot",
                },
            )
        )

    if snap_grid.get("required") is True and snap_grid.get("off_grid_axes"):
        diagnostics.append(
            _diagnostic(
                "RB5001",
                "snap_grid_mismatch",
                _json_pointer("objects", index, "transform", "position"),
                f"Object {object_id!r} transform position is off the Roblox snap grid.",
                details={
                    "object_id": object_id,
                    "position": _position(item),
                    "grid_size_studs": snap_grid.get("grid_size_studs"),
                    "off_grid_axes": list(snap_grid.get("off_grid_axes", [])),
                    "score_component": "snap_grid",
                },
            )
        )

    return diagnostics


def _object_manifest_record(
    *,
    index: int,
    item: Mapping[str, Any],
    profile: Mapping[str, Any],
    metrics: Mapping[str, Any],
    collision: _ReadinessState,
    pivot: _ReadinessState,
    snap_grid: Mapping[str, Any],
) -> dict[str, Any]:
    position = _position(item)
    return {
        "object_id": _string_field(item, "object_id") or f"obj_missing_{index:03d}",
        "name": _string_field(item, "name"),
        "role": _string_field(item, "role"),
        "region": _string_field(item, "region"),
        "lathe_asset": _string_field(item, "lathe_asset"),
        "roblox_name": _source_name(index, item),
        "transform": {"position": position},
        "mesh": {
            "mesh_count": metrics.get("mesh_count"),
            "triangle_count": metrics.get("triangle_count"),
        },
        "textures": {
            "texture_count": metrics.get("texture_count"),
            "max_resolution": metrics.get("max_texture_resolution"),
        },
        "materials": {
            "slot_count": metrics.get("material_slots"),
            "max_slots_per_mesh": _int_field(
                _profile_section(profile, "budgets"), "max_materials_per_mesh", 4
            ),
        },
        "collision": {
            "required": collision.required,
            "present": collision.present,
            "mode": collision.mode,
        },
        "pivot": {
            "required": pivot.required,
            "present": pivot.present,
            "mode": pivot.mode,
        },
        "snap_grid": {
            "required": bool(snap_grid.get("required")),
            "grid_size_studs": snap_grid.get("grid_size_studs"),
            "on_grid": bool(snap_grid.get("on_grid")),
            "off_grid_axes": list(snap_grid.get("off_grid_axes", [])),
        },
    }


def _check_naming(
    *,
    index: int,
    item: Mapping[str, Any],
    profile: Mapping[str, Any],
    pattern: re.Pattern[str],
) -> list[dict[str, Any]]:
    source_name = _source_name(index, item)
    max_length = _int_field(_profile_section(profile, "naming"), "max_length", 64)
    if pattern.fullmatch(source_name) is not None and len(source_name) <= max_length:
        return []
    return [
        _diagnostic(
            "RB1001",
            "unsafe_roblox_name",
            _json_pointer(
                "objects", index, "lathe_asset" if _string_field(item, "lathe_asset") else "object_id"
            ),
            f"Object export name {source_name!r} does not satisfy the Roblox naming policy.",
            details={
                "object_id": _string_field(item, "object_id"),
                "roblox_name": source_name,
                "pattern": pattern.pattern,
                "max_length": max_length,
                "score_component": "naming",
            },
        )
    ]


def _scene_totals(objects: Sequence[Mapping[str, Any]], material_count: int) -> dict[str, int | None]:
    def total_for(field: str) -> int | None:
        values = [item.get(field) for item in objects]
        known = [value for value in values if isinstance(value, int)]
        return sum(known) if known else None

    return {
        "triangle_count": total_for("triangle_count"),
        "mesh_count": total_for("mesh_count"),
        "texture_count": total_for("texture_count"),
        "material_count": material_count,
    }


def _check_scene_budgets(
    scene_graph: Mapping[str, Any],
    profile: Mapping[str, Any],
    totals: Mapping[str, int | None],
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    budgets = _profile_section(profile, "budgets")
    checks = (
        ("triangle_count", "max_scene_triangles", "RB2002", "scene_triangle_budget_exceeded", "triangle"),
        ("mesh_count", "max_meshes", "RB2004", "scene_mesh_budget_exceeded", "mesh"),
        ("texture_count", "max_textures", "RB2007", "scene_texture_budget_exceeded", "texture"),
        ("material_count", "max_materials", "RB2008", "scene_material_budget_exceeded", "material"),
    )
    for total_field, budget_field, code, name, component in checks:
        total = totals.get(total_field)
        if not isinstance(total, int):
            continue
        budget = _int_field(budgets, budget_field, 0)
        if budget <= 0 or total <= budget:
            continue
        diagnostics.append(
            _budget_diagnostic(
                code,
                name,
                "/",
                f"Scene {scene_graph.get('scene_id')!r} {total_field} {total} exceeds Roblox budget {budget}.",
                component=component,
                details={
                    "scene_id": scene_graph.get("scene_id"),
                    total_field: total,
                    budget_field: budget,
                },
            )
        )
    return diagnostics


def _analyze_scene(scene_graph: Mapping[str, Any], profile: Mapping[str, Any]) -> _Analysis:
    pattern = _safe_name_pattern(profile)
    object_records: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    raw_metric_records: list[dict[str, Any]] = []

    for index, item in _items(scene_graph, "objects"):
        metrics = _object_metrics(index, item)
        collision = _collision_state(profile, index, item)
        pivot = _pivot_state(profile, index, item)
        snap_grid = _snap_grid_state(profile, item)
        diagnostics.extend(_check_naming(index=index, item=item, profile=profile, pattern=pattern))
        diagnostics.extend(_check_object_budget(index=index, item=item, profile=profile, metrics=metrics))
        diagnostics.extend(
            _check_readiness(
                index=index,
                item=item,
                profile=profile,
                collision=collision,
                pivot=pivot,
                snap_grid=snap_grid,
            )
        )
        object_records.append(
            _object_manifest_record(
                index=index,
                item=item,
                profile=profile,
                metrics=metrics,
                collision=collision,
                pivot=pivot,
                snap_grid=snap_grid,
            )
        )
        raw_metric_records.append(metrics)

    material_count = sum(1 for _index, _item in _items(scene_graph, "materials"))
    totals = _scene_totals(raw_metric_records, material_count)
    diagnostics.extend(_check_scene_budgets(scene_graph, profile, totals))
    measured = {
        "triangle": any(isinstance(item.get("triangle_count"), int) for item in raw_metric_records),
        "texture": any(
            isinstance(item.get("texture_count"), int) or isinstance(item.get("max_texture_resolution"), int)
            for item in raw_metric_records
        ),
        "mesh": any(isinstance(item.get("mesh_count"), int) for item in raw_metric_records),
        "collision": True,
        "material": True,
        "naming": True,
        "pivot": True,
        "snap_grid": True,
    }
    return _Analysis(objects=object_records, diagnostics=diagnostics, measured=measured, totals=totals)


def validate_roblox_profile(
    scene_graph: Mapping[str, Any], profile: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Return deterministic Roblox profile diagnostics for a Scene Graph payload."""
    profile_diagnostics = validate_roblox_profile_payload(profile)
    if profile_diagnostics:
        return profile_diagnostics
    return _analyze_scene(scene_graph, profile).diagnostics


def _score_for_component(
    diagnostics: Sequence[Mapping[str, Any]],
    component: str,
    *,
    measured: bool,
) -> dict[str, Any]:
    if not measured:
        return {"score": None, "status": "not_measured"}
    component_diagnostics = [
        diagnostic
        for diagnostic in diagnostics
        if isinstance(diagnostic.get("details"), Mapping)
        and diagnostic["details"].get("score_component") == component
    ]
    errors = sum(1 for diagnostic in component_diagnostics if diagnostic.get("severity") == "error")
    warnings = len(component_diagnostics) - errors
    score = max(0, 100 - errors * 35 - warnings * 15)
    status = "failed" if errors else "warning" if warnings else "passed"
    return {"score": score, "status": status}


def _mobile_score(
    component_scores: Mapping[str, Mapping[str, Any]],
    diagnostics: Sequence[Mapping[str, Any]],
    profile: Mapping[str, Any],
) -> dict[str, Any]:
    weights = _profile_section(_profile_section(profile, "mobile"), "component_weights")
    weighted_total = 0
    total_weight = 0
    measured_components = 0
    for component, score_item in component_scores.items():
        if component not in _SCORE_COMPONENTS or not isinstance(score_item.get("score"), int):
            continue
        weight = _int_field(weights, component, 1)
        if weight <= 0:
            continue
        weighted_total += int(score_item["score"]) * weight
        total_weight += weight
        measured_components += 1
    score = weighted_total // total_weight if total_weight else 0
    min_score = _int_field(_profile_section(profile, "mobile"), "min_score", 80)
    has_errors = any(diagnostic.get("severity") == "error" for diagnostic in diagnostics)
    has_unmeasured = any(
        score_item.get("status") == "not_measured" for score_item in component_scores.values()
    )
    if has_errors or score < min_score:
        status = "failed"
    elif has_unmeasured:
        status = "warning"
    else:
        status = "passed"
    return {
        "score": score,
        "status": status,
        "min_score": min_score,
        "measured_components": measured_components,
    }


def _summary(
    analysis: _Analysis,
    diagnostics: Sequence[Mapping[str, Any]],
    profile: Mapping[str, Any],
) -> dict[str, Any]:
    scores = {
        component: _score_for_component(
            diagnostics, component, measured=analysis.measured.get(component, False)
        )
        for component in _SCORE_COMPONENTS
    }
    scores["mobile"] = _mobile_score(scores, diagnostics, profile)
    errors = sum(1 for diagnostic in diagnostics if diagnostic.get("severity") == "error")
    warnings = len(diagnostics) - errors
    return {
        "objects": len(analysis.objects),
        "triangles": analysis.totals.get("triangle_count"),
        "meshes": analysis.totals.get("mesh_count"),
        "textures": analysis.totals.get("texture_count"),
        "materials": analysis.totals.get("material_count"),
        "diagnostics": len(diagnostics),
        "errors": errors,
        "warnings": warnings,
        "scores": scores,
    }


def build_roblox_manifest(scene_graph: Mapping[str, Any], profile: Mapping[str, Any]) -> dict[str, Any]:
    """Build a deterministic Roblox export-lane manifest from a Scene Graph payload."""
    profile_diagnostics = validate_roblox_profile_payload(profile)
    if profile_diagnostics:
        analysis = _Analysis(
            objects=[],
            diagnostics=[],
            measured={component: False for component in _SCORE_COMPONENTS},
            totals={
                "triangle_count": None,
                "mesh_count": None,
                "texture_count": None,
                "material_count": None,
            },
        )
        diagnostics = profile_diagnostics
    else:
        analysis = _analyze_scene(scene_graph, profile)
        diagnostics = analysis.diagnostics

    profile_id = _string_field(profile, "profile_id") or "invalid_profile"
    scene_id = _string_field(scene_graph, "scene_id") or "scene"
    units = _profile_section(profile, "units")
    length_unit = _string_field(units, "length") or "studs"
    return {
        "schema_version": ROBLOX_MANIFEST_VERSION,
        "manifest_id": f"{scene_id}_{profile_id}_manifest",
        "scene_id": scene_id,
        "profile_id": profile_id,
        "units": {"length": length_unit},
        "budgets": dict(_profile_section(profile, "budgets")),
        "summary": _summary(analysis, diagnostics, profile),
        "objects": analysis.objects,
        "diagnostics": list(diagnostics),
    }


def export_roblox_asset_kit(
    scene_graph: Mapping[str, Any],
    package_dir: str | Path,
    *,
    profile: Mapping[str, Any] | None = None,
    mode: str = "preview",
    include_collision_nodes: bool = True,
) -> dict[str, Any]:
    """Export a deterministic Roblox-facing asset-kit folder.

    The bundle writes a real proxy GLB, schema-valid Roblox manifest,
    thumbnail PNGs, and import instructions. FBX and Studio import remain an
    explicit handoff lane because Lathe does not own a native FBX or `.rbxmx`
    writer in the current contract.
    """
    from .artifacts import export_scene_glbs

    package_root = Path(package_dir)
    scene_id = _string_field(scene_graph, "scene_id") or "scene"
    resolved_profile = ROBLOX_LOW_POLY_PROFILE if profile is None else profile
    manifest = build_roblox_manifest(scene_graph, resolved_profile)
    diagnostics = list(validate_roblox_manifest_payload(manifest))
    diagnostics.extend(item for item in manifest.get("diagnostics", []) if isinstance(item, dict))

    export_root = _safe_package_path(package_root, "exports/roblox")
    manifest_path = _safe_package_path(package_root, "exports/roblox/roblox_manifest.json")
    report_path = _safe_package_path(package_root, "reports/roblox_export_bundle.json")
    fbx_status_path = _safe_package_path(package_root, "exports/roblox/fbx/fbx_handoff.json")
    fbx_readme_path = _safe_package_path(package_root, "exports/roblox/fbx/README.md")
    instructions_path = _safe_package_path(package_root, "exports/roblox/import_instructions.md")
    export_root.mkdir(parents=True, exist_ok=True)
    _write_json(manifest_path, manifest)

    glb_report: dict[str, Any] | None = None
    thumbnail_report: dict[str, Any] | None = None
    if not diagnostics:
        fbx_handoff = _fbx_handoff_payload(scene_graph, manifest)
        _write_json(fbx_status_path, fbx_handoff)
        _write_text(fbx_readme_path, _fbx_handoff_markdown(scene_graph, fbx_handoff))
        _write_text(instructions_path, _roblox_import_instructions(scene_graph, manifest))
        glb_report = export_scene_glbs(
            scene_graph,
            package_root,
            mode=mode,  # type: ignore[arg-type]
            export_tasks=[
                {
                    "task_id": "export_task_roblox_asset_kit_glb",
                    "target": "glb",
                    "format": "glb",
                    "path": f"exports/roblox/glb/{scene_id}_roblox_asset_kit.glb",
                }
            ],
            include_collision_nodes=include_collision_nodes,
        )
        thumbnail_report = _write_roblox_thumbnails(scene_graph, package_root, mode=mode)
    else:
        _cleanup_roblox_generated_artifacts(package_root, scene_id)

    artifacts = [
        {
            "target": "roblox_manifest",
            "format": "json",
            "path": _relative_to(package_root, manifest_path),
            "status": "built" if not diagnostics else "failed",
        },
    ]
    if not diagnostics:
        artifacts.extend(
            [
                {
                    "target": "roblox_import_instructions",
                    "format": "markdown",
                    "path": _relative_to(package_root, instructions_path),
                    "status": "built",
                },
                {
                    "target": "fbx_handoff",
                    "format": "json",
                    "path": _relative_to(package_root, fbx_status_path),
                    "status": "handoff_required",
                },
                {
                    "target": "fbx_handoff_readme",
                    "format": "markdown",
                    "path": _relative_to(package_root, fbx_readme_path),
                    "status": "handoff_required",
                },
            ]
        )
    if glb_report is not None:
        artifacts.extend(glb_report.get("artifacts", []))
    if thumbnail_report is not None:
        artifacts.extend(thumbnail_report.get("artifacts", []))

    report = {
        "schema_version": ROBLOX_EXPORT_BUNDLE_VERSION,
        "stack_id": ROBLOX_ASSET_KIT_STACK_ID,
        "scene_id": scene_id,
        "profile_id": manifest.get("profile_id"),
        "mode": mode,
        "status": "built" if not diagnostics else "failed",
        "paths": {
            "root": _relative_to(package_root, export_root),
            "manifest": _relative_to(package_root, manifest_path),
            "glb_folder": "exports/roblox/glb",
            "fbx_folder": "exports/roblox/fbx",
            "thumbnails": "exports/roblox/thumbnails",
            "import_instructions": _relative_to(package_root, instructions_path),
        },
        "formats": {
            "glb": {"status": "built" if glb_report is not None else "not_built"},
            "fbx": {
                "status": "handoff_required" if not diagnostics else "not_built",
                "reason": (
                    "Lathe v0.3 writes a Roblox-ready GLB asset-kit bundle and "
                    "records FBX conversion instructions for downstream Blender or Studio tooling."
                ),
                "handoff_manifest": _relative_to(package_root, fbx_status_path) if not diagnostics else None,
            },
        },
        "manifest_summary": manifest.get("summary", {}),
        "artifacts": artifacts,
        "diagnostics": diagnostics,
    }
    _write_json(report_path, report)
    report["report_path"] = _relative_to(package_root, report_path)
    return report


def _write_roblox_thumbnails(
    scene_graph: Mapping[str, Any],
    package_root: Path,
    *,
    mode: str,
) -> dict[str, Any]:
    from .artifacts import render_scene_graph

    render_report = render_scene_graph(
        scene_graph,
        package_root,
        mode=mode,  # type: ignore[arg-type]
        camera_id=_preferred_camera_id(scene_graph),
        passes=("beauty",),
        resolution=(512, 512),
        include_topdown=False,
        include_contact_sheet=True,
    )
    artifacts: list[dict[str, Any]] = []
    beauty_artifact = next(
        (
            item
            for item in render_report.get("artifacts", [])
            if isinstance(item, Mapping) and item.get("render_pass") == "beauty"
        ),
        None,
    )
    if isinstance(beauty_artifact, Mapping) and isinstance(beauty_artifact.get("path"), str):
        source_path = package_root / beauty_artifact["path"]
        target_path = _safe_package_path(package_root, "exports/roblox/thumbnails/scene_thumbnail.png")
        _write_bytes(target_path, source_path.read_bytes())
        artifacts.append(
            {
                "target": "roblox_thumbnail",
                "format": "png",
                "path": _relative_to(package_root, target_path),
                "status": "built",
                "width": 512,
                "height": 512,
                "source": beauty_artifact["path"],
            }
        )

    contact_artifact = next(
        (
            item
            for item in render_report.get("artifacts", [])
            if isinstance(item, Mapping) and item.get("kind") == "object_contact_sheet"
        ),
        None,
    )
    if isinstance(contact_artifact, Mapping) and isinstance(contact_artifact.get("path"), str):
        source_path = package_root / contact_artifact["path"]
        target_path = _safe_package_path(package_root, "exports/roblox/thumbnails/object_contact_sheet.png")
        _write_bytes(target_path, source_path.read_bytes())
        artifacts.append(
            {
                "target": "roblox_object_contact_sheet",
                "format": "png",
                "path": _relative_to(package_root, target_path),
                "status": "built",
                "width": contact_artifact.get("width"),
                "height": contact_artifact.get("height"),
                "source": contact_artifact["path"],
            }
        )

    return {
        "schema_version": "lathe.roblox_thumbnail_bundle.v1",
        "scene_id": _string_field(scene_graph, "scene_id") or "scene",
        "renderer": render_report.get("renderer"),
        "artifacts": artifacts,
        "render_report_path": render_report.get("report_path"),
    }


def _preferred_camera_id(scene_graph: Mapping[str, Any]) -> str | None:
    cameras = scene_graph.get("cameras")
    if not isinstance(cameras, list):
        return None
    first: str | None = None
    for item in cameras:
        if not isinstance(item, Mapping):
            continue
        camera_id = _string_field(item, "camera_id")
        if camera_id is None:
            continue
        if first is None:
            first = camera_id
        if camera_id == "camera_reveal":
            return camera_id
    return first


def _fbx_handoff_payload(scene_graph: Mapping[str, Any], manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "lathe.roblox_fbx_handoff.v1",
        "stack_id": ROBLOX_ASSET_KIT_STACK_ID,
        "scene_id": _string_field(scene_graph, "scene_id") or "scene",
        "status": "handoff_required",
        "source_glb": f"../glb/{_string_field(scene_graph, 'scene_id') or 'scene'}_roblox_asset_kit.glb",
        "roblox_manifest": "../roblox_manifest.json",
        "recommended_tool": "Blender or Roblox Studio import tooling",
        "units": manifest.get("units", {"length": "studs"}),
        "identity_requirement": "Preserve object names and Lathe object IDs from the Roblox manifest.",
    }


def _roblox_import_instructions(
    scene_graph: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> str:
    scene_id = _string_field(scene_graph, "scene_id") or "scene"
    return "\n".join(
        [
            "# Roblox Asset Kit Import",
            "",
            f"Scene: `{scene_id}`",
            f"Stack: `{ROBLOX_ASSET_KIT_STACK_ID}`",
            "",
            "## Files",
            "",
            "- `roblox_manifest.json` contains names, budgets, object IDs, pivots, collision modes, and mobile score.",
            f"- `glb/{scene_id}_roblox_asset_kit.glb` is the deterministic Lathe proxy GLB for import.",
            "- `thumbnails/scene_thumbnail.png` is a square preview thumbnail.",
            "- `thumbnails/object_contact_sheet.png` is the object review sheet.",
            "- `fbx/fbx_handoff.json` records the downstream FBX conversion handoff.",
            "",
            "## Import Steps",
            "",
            "1. Import the GLB into Roblox Studio or a Blender conversion workflow.",
            "2. Use `roblox_manifest.json` to preserve object names, pivots, collision policy, and stable IDs.",
            "3. Keep units in `studs`; do not rescale unless the manifest profile changes.",
            "4. Use simple collision for architecture, hero props, navigation, and interactive objects.",
            "5. Review the mobile score and diagnostics before publishing or uploading assets.",
            "",
            "## Current Scope",
            "",
            "Lathe does not write `.rbxmx` or call Roblox APIs in this lane. Studio automation remains a downstream integration.",
            "",
            f"Manifest status: `{manifest.get('summary', {}).get('scores', {}).get('mobile', {}).get('status', 'unknown')}`",
            "",
        ]
    )


def _fbx_handoff_markdown(scene_graph: Mapping[str, Any], handoff: Mapping[str, Any]) -> str:
    scene_id = _string_field(scene_graph, "scene_id") or "scene"
    return "\n".join(
        [
            "# FBX Handoff",
            "",
            f"Scene: `{scene_id}`",
            "",
            "Lathe has produced the Roblox asset-kit GLB and manifest. Convert the GLB to FBX with a downstream tool if that format is required.",
            "",
            f"- Source GLB: `{handoff.get('source_glb')}`",
            f"- Manifest: `{handoff.get('roblox_manifest')}`",
            "- Preserve object names and Lathe object IDs during conversion.",
            "- Keep units in studs.",
            "",
        ]
    )


def _cleanup_roblox_generated_artifacts(package_root: Path, scene_id: str) -> None:
    for relative_path in (
        f"exports/roblox/glb/{scene_id}_roblox_asset_kit.glb",
        f"exports/roblox/glb/{scene_id}_roblox_asset_kit.object_index.json",
        "exports/roblox/thumbnails/scene_thumbnail.png",
        "exports/roblox/thumbnails/object_contact_sheet.png",
        "exports/roblox/fbx/fbx_handoff.json",
        "exports/roblox/fbx/README.md",
        "exports/roblox/import_instructions.md",
    ):
        path = _safe_package_path(package_root, relative_path)
        if path.exists() and path.is_file():
            path.unlink()


def _safe_package_path(package_dir: Path, relative_path: str) -> Path:
    try:
        return safe_resolve(package_dir, relative_path)
    except PathGuardError as exc:
        from .artifacts import SceneArtifactError

        raise SceneArtifactError(
            "Roblox asset-kit export package path is unsafe.",
            diagnostics=[
                _diagnostic(
                    "RBX9001",
                    "unsafe_roblox_export_path",
                    f"/package/{relative_path}",
                    f"Roblox export path {relative_path!r} is unsafe: {exc}",
                    contract="roblox_export",
                    phase="roblox_export",
                    details={"path": relative_path, "package_dir": str(package_dir)},
                )
            ],
        ) from exc


def _relative_to(root: Path, path: Path) -> str:
    return path.resolve(strict=False).relative_to(root.resolve(strict=False)).as_posix()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    write_json_atomic(path, payload)


def _write_text(path: Path, text: str) -> None:
    write_text_atomic(path, text)


def _write_bytes(path: Path, payload: bytes) -> None:
    write_bytes_atomic(path, payload)


__all__ = [
    "ROBLOX_ASSET_KIT_STACK_ID",
    "ROBLOX_EXPORT_BUNDLE_VERSION",
    "ROBLOX_IMPORT_INSTRUCTIONS_VERSION",
    "ROBLOX_LOW_POLY_PROFILE",
    "ROBLOX_MANIFEST_CONTRACT",
    "ROBLOX_MANIFEST_SCHEMA_FILENAME",
    "ROBLOX_MANIFEST_VERSION",
    "ROBLOX_PROFILE_CONTRACT",
    "ROBLOX_PROFILE_SCHEMA_FILENAME",
    "ROBLOX_PROFILE_VERSION",
    "build_roblox_manifest",
    "export_roblox_asset_kit",
    "get_roblox_manifest_schema",
    "get_roblox_profile_schema",
    "validate_roblox_manifest_payload",
    "validate_roblox_profile",
    "validate_roblox_profile_payload",
]
