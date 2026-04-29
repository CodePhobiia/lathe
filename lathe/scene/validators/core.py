"""Composable scene-level validators for Wonder Scene Graph payloads."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lathe.paths import PathGuardError, safe_resolve

from ..diagnostics import scene_diagnostic
from ..environment import validate_environment_module_scene
from ..graph import check_scene_graph

SceneValidator = Callable[[Mapping[str, Any], "SceneValidationContext"], list[dict[str, Any]]]


@dataclass(frozen=True)
class SceneValidationContext:
    """Shared context for scene validators."""

    root: Path
    require_export_artifacts: bool = False
    platform: str | None = None


DEFAULT_VALIDATORS: tuple[str, ...] = (
    "spatial",
    "semantic",
    "style",
    "composition",
    "curiosity",
    "continuity",
    "environment",
    "export",
    "platform",
)


def _json_pointer(*parts: object) -> str:
    escaped = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(escaped) if escaped else "/"


def _items(scene_graph: Mapping[str, Any], collection: str) -> list[tuple[int, Mapping[str, Any]]]:
    raw = scene_graph.get(collection, [])
    if not isinstance(raw, list):
        return []
    return [(index, item) for index, item in enumerate(raw) if isinstance(item, Mapping)]


def _string_field(item: Mapping[str, Any], field: str) -> str | None:
    value = item.get(field)
    return value if isinstance(value, str) else None


def _transform_position(item: Mapping[str, Any]) -> list[float] | None:
    transform = item.get("transform")
    if not isinstance(transform, Mapping):
        return None
    position = transform.get("position")
    if not isinstance(position, list) or len(position) != 3:
        return None
    if not all(isinstance(value, int | float) for value in position):
        return None
    return [float(value) for value in position]


def _transform_scale(item: Mapping[str, Any]) -> list[float] | None:
    transform = item.get("transform")
    if not isinstance(transform, Mapping):
        return None
    scale = transform.get("scale")
    if not isinstance(scale, list) or len(scale) != 3:
        return None
    if not all(isinstance(value, int | float) for value in scale):
        return None
    return [float(value) for value in scale]


def _scene_refs(scene_graph: Mapping[str, Any]) -> set[str]:
    refs: set[str] = set()
    scene_id = _string_field(scene_graph, "scene_id")
    if scene_id:
        refs.add(scene_id)
    for collection, field in (
        ("regions", "region_id"),
        ("objects", "object_id"),
        ("cameras", "camera_id"),
        ("lights", "light_id"),
        ("curiosity_anchors", "anchor_id"),
        ("hidden_state", "hidden_id"),
        ("materials", "material_id"),
    ):
        for _index, item in _items(scene_graph, collection):
            value = _string_field(item, field)
            if value:
                refs.add(value)
    return refs


def _as_text_tokens(*values: object) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        if isinstance(value, list):
            tokens.update(_as_text_tokens(*value))
            continue
        text = str(value).lower()
        for token in text.replace("_", " ").replace("-", " ").split():
            if len(token) >= 3:
                tokens.add(token)
    return tokens


def _diag(
    code: str,
    name: str,
    path: str,
    message: str,
    *,
    severity: str = "warning",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    diagnostic = scene_diagnostic(code, name, path, message, details=details)
    diagnostic["severity"] = severity
    return diagnostic


def _spatial_validator(scene_graph: Mapping[str, Any], _context: SceneValidationContext) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    layout = scene_graph.get("layout")
    room_size = layout.get("room_size") if isinstance(layout, Mapping) else None
    half_x = float(room_size[0]) / 2.0 if isinstance(room_size, list) and len(room_size) == 3 else None
    half_y = float(room_size[1]) / 2.0 if isinstance(room_size, list) and len(room_size) == 3 else None
    height = float(room_size[2]) if isinstance(room_size, list) and len(room_size) == 3 else None
    occupied: dict[tuple[float, float, float], str] = {}
    for index, item in _items(scene_graph, "objects"):
        object_id = _string_field(item, "object_id")
        position = _transform_position(item)
        if position is None:
            continue
        if position[2] < -0.01:
            diagnostics.append(
                _diag(
                    "SV1001",
                    "object_below_floor",
                    _json_pointer("objects", index, "transform", "position", 2),
                    f"Object {object_id!r} is below the scene floor.",
                    severity="error",
                    details={"object_id": object_id, "z": position[2]},
                )
            )
        if half_x is not None and (abs(position[0]) > half_x or abs(position[1]) > half_y or position[2] > height):
            diagnostics.append(
                _diag(
                    "SV1002",
                    "object_outside_layout_bounds",
                    _json_pointer("objects", index, "transform", "position"),
                    f"Object {object_id!r} is outside the declared layout bounds.",
                    details={"object_id": object_id, "position": position, "room_size": room_size},
                )
            )
        rounded = tuple(round(value, 2) for value in position)
        previous = occupied.get(rounded)
        if previous is not None:
            diagnostics.append(
                _diag(
                    "SV1003",
                    "probable_object_overlap",
                    _json_pointer("objects", index, "transform", "position"),
                    f"Object {object_id!r} shares a position with {previous!r}.",
                    details={"object_id": object_id, "other_object_id": previous, "position": position},
                )
            )
        elif object_id:
            occupied[rounded] = object_id

        scale = _transform_scale(item)
        if scale is not None and any(value <= 0 for value in scale):
            diagnostics.append(
                _diag(
                    "SV1004",
                    "non_positive_object_scale",
                    _json_pointer("objects", index, "transform", "scale"),
                    f"Object {object_id!r} has a non-positive scale component.",
                    severity="error",
                    details={"object_id": object_id, "scale": scale},
                )
            )
    return diagnostics


def _semantic_validator(scene_graph: Mapping[str, Any], _context: SceneValidationContext) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    objects = _items(scene_graph, "objects")
    if len(objects) < 4:
        diagnostics.append(
            _diag(
                "SV2001",
                "scene_has_too_few_objects",
                "/objects",
                "Wonder-ready seed scenes should contain at least four meaningful objects.",
                details={"object_count": len(objects)},
            )
        )
    roles = {_string_field(item, "role") for _index, item in objects}
    if "hero_prop" not in roles and "interactive" not in roles:
        diagnostics.append(
            _diag(
                "SV2002",
                "missing_focal_role",
                "/objects",
                "Scene has no hero or interactive object to act as a focal point.",
            )
        )
    style = scene_graph.get("style_bible")
    avoid_terms = _as_text_tokens(style.get("avoid", []) if isinstance(style, Mapping) else [])
    if avoid_terms:
        object_tokens = _as_text_tokens(
            *[
                [item.get("name"), item.get("lathe_asset"), item.get("semantic_tags", [])]
                for _index, item in objects
            ]
        )
        overlap = sorted(avoid_terms & object_tokens)
        if overlap:
            diagnostics.append(
                _diag(
                    "SV2003",
                    "avoided_terms_present",
                    "/style_bible/avoid",
                    "Scene object metadata contains terms listed in the style avoid constraints.",
                    severity="error",
                    details={"terms": overlap},
                )
            )
    return diagnostics


def _style_validator(scene_graph: Mapping[str, Any], _context: SceneValidationContext) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    style = scene_graph.get("style_bible")
    if not isinstance(style, Mapping):
        return diagnostics
    for field in ("mood", "palette", "materials", "forms", "lighting"):
        values = style.get(field)
        if not isinstance(values, list) or not values:
            diagnostics.append(
                _diag(
                    "SV3001",
                    "style_field_empty",
                    _json_pointer("style_bible", field),
                    f"Style bible field {field!r} should contain at least one value.",
                    details={"field": field},
                )
            )
    materials = _items(scene_graph, "materials")
    if materials and isinstance(style.get("materials"), list):
        style_tokens = _as_text_tokens(style.get("materials", []), style.get("palette", []))
        material_tokens = _as_text_tokens(*[[item.get("name"), item.get("role"), item.get("palette_refs", [])] for _, item in materials])
        if style_tokens and material_tokens and not (style_tokens & material_tokens):
            diagnostics.append(
                _diag(
                    "SV3002",
                    "material_language_drift",
                    "/materials",
                    "Scene materials do not overlap with the declared style material or palette language.",
                    details={"style_terms": sorted(style_tokens), "material_terms": sorted(material_tokens)},
                )
            )
    return diagnostics


def _composition_validator(scene_graph: Mapping[str, Any], _context: SceneValidationContext) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    refs = _scene_refs(scene_graph)
    layout = scene_graph.get("layout")
    focal_point = layout.get("focal_point") if isinstance(layout, Mapping) else None
    if not isinstance(focal_point, str):
        diagnostics.append(
            _diag(
                "SV4001",
                "missing_focal_point",
                "/layout/focal_point",
                "Scene layout should name a focal point for reveal composition.",
            )
        )
    elif focal_point not in refs:
        diagnostics.append(
            _diag(
                "SV4002",
                "invalid_focal_point",
                "/layout/focal_point",
                f"Scene focal point {focal_point!r} does not reference a scene entity.",
                severity="error",
                details={"focal_point": focal_point},
            )
        )
    reveal_cameras = [
        item
        for _index, item in _items(scene_graph, "cameras")
        if _string_field(item, "framing") == "cinematic_wide" or "reveal" in (_string_field(item, "purpose") or "").lower()
    ]
    if not reveal_cameras:
        diagnostics.append(
            _diag(
                "SV4003",
                "missing_reveal_camera",
                "/cameras",
                "Scene should include a reveal camera for first preview renders.",
            )
        )
    return diagnostics


def _curiosity_validator(scene_graph: Mapping[str, Any], _context: SceneValidationContext) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    anchors = _items(scene_graph, "curiosity_anchors")
    if len(anchors) < 2:
        diagnostics.append(
            _diag(
                "SV5001",
                "not_enough_curiosity_anchors",
                "/curiosity_anchors",
                "Wonder-ready scenes should expose at least two curiosity anchors.",
                details={"anchor_count": len(anchors)},
            )
        )
    hidden_fact_tokens = [
        _as_text_tokens(item.get("fact"))
        for _index, item in _items(scene_graph, "hidden_state")
        if str(item.get("fact", "")).strip()
    ]
    for index, item in anchors:
        hidden_fact = str(item.get("hidden_fact", "")).strip()
        anchor_tokens = _as_text_tokens(hidden_fact)
        has_matching_hidden_state = any(len(anchor_tokens & tokens) >= 3 for tokens in hidden_fact_tokens)
        if hidden_fact and hidden_fact_tokens and not has_matching_hidden_state:
            diagnostics.append(
                _diag(
                    "SV5002",
                    "curiosity_hidden_fact_not_recorded",
                    _json_pointer("curiosity_anchors", index, "hidden_fact"),
                    "Curiosity anchor hidden fact is not mirrored in hidden_state facts.",
                    details={"anchor_id": _string_field(item, "anchor_id")},
                )
            )
    return diagnostics


def _continuity_validator(scene_graph: Mapping[str, Any], _context: SceneValidationContext) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    refs = _scene_refs(scene_graph)
    for index, event in _items(scene_graph, "memory_events"):
        affected_ids = event.get("affected_ids", [])
        if not isinstance(affected_ids, list):
            continue
        for affected_index, affected_id in enumerate(affected_ids):
            if isinstance(affected_id, str) and affected_id not in refs:
                diagnostics.append(
                    _diag(
                        "SV6001",
                        "memory_event_unknown_affected_id",
                        _json_pointer("memory_events", index, "affected_ids", affected_index),
                        f"Memory event affected_id {affected_id!r} does not reference the Scene Graph.",
                        severity="error",
                        details={"event_id": _string_field(event, "event_id"), "affected_id": affected_id},
                    )
                )
    return diagnostics


def _environment_validator(scene_graph: Mapping[str, Any], _context: SceneValidationContext) -> list[dict[str, Any]]:
    return validate_environment_module_scene(scene_graph)


def _export_validator(scene_graph: Mapping[str, Any], context: SceneValidationContext) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    exports = _items(scene_graph, "exports")
    if not exports:
        diagnostics.append(
            _diag("SV7001", "missing_export_target", "/exports", "Scene should define at least one export target.")
        )
    material_ids = {_string_field(item, "material_id") for _index, item in _items(scene_graph, "materials")}
    material_ids.discard(None)
    for object_index, item in _items(scene_graph, "objects"):
        object_id = _string_field(item, "object_id")
        bindings = item.get("material_bindings")
        if not isinstance(bindings, list):
            continue
        for binding_index, binding in enumerate(bindings):
            if not isinstance(binding, Mapping):
                continue
            material = _string_field(binding, "material")
            if material is None or material in material_ids:
                continue
            diagnostics.append(
                _diag(
                    "SV7004",
                    "export_missing_material",
                    _json_pointer("objects", object_index, "material_bindings", binding_index, "material"),
                    f"Object {object_id!r} references missing material {material!r} for export.",
                    severity="error",
                    details={
                        "object_id": object_id,
                        "slot": _string_field(binding, "slot"),
                        "material": material,
                    },
                )
            )
    for index, item in exports:
        raw_path = _string_field(item, "path")
        if raw_path is None:
            continue
        try:
            resolved = safe_resolve(context.root, raw_path)
        except PathGuardError as exc:
            diagnostics.append(
                _diag(
                    "SV7002",
                    "unsafe_export_path",
                    _json_pointer("exports", index, "path"),
                    f"Export path {raw_path!r} is not safe: {exc}",
                    severity="error",
                    details={"path": raw_path},
                )
            )
            continue
        if context.require_export_artifacts and not resolved.exists():
            diagnostics.append(
                _diag(
                    "SV7003",
                    "missing_export_artifact",
                    _json_pointer("exports", index, "path"),
                    f"Export artifact {raw_path!r} does not exist.",
                    severity="error",
                    details={"path": raw_path},
                )
            )
    return diagnostics


def _platform_validator(scene_graph: Mapping[str, Any], context: SceneValidationContext) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    targets = {str(item.get("target")) for _index, item in _items(scene_graph, "exports")}
    platform = context.platform or ("roblox" if "roblox" in targets else None)
    objects = _items(scene_graph, "objects")
    if len(objects) > 64:
        diagnostics.append(
            _diag(
                "SV8001",
                "scene_object_count_budget_warning",
                "/objects",
                "Preview scene object count is high for fast Wonder iteration.",
                details={"object_count": len(objects), "budget": 64},
            )
        )
    if platform == "roblox":
        for index, item in objects:
            lathe_asset = _string_field(item, "lathe_asset") or ""
            if not lathe_asset.replace("_", "").isalnum() or lathe_asset.lower() != lathe_asset:
                diagnostics.append(
                    _diag(
                        "SV8002",
                        "roblox_unsafe_asset_name",
                        _json_pointer("objects", index, "lathe_asset"),
                        "Roblox target assets should use lower snake-case names.",
                        details={"object_id": _string_field(item, "object_id"), "lathe_asset": lathe_asset},
                    )
                )
    return diagnostics


_VALIDATORS: dict[str, SceneValidator] = {
    "spatial": _spatial_validator,
    "semantic": _semantic_validator,
    "style": _style_validator,
    "composition": _composition_validator,
    "curiosity": _curiosity_validator,
    "continuity": _continuity_validator,
    "environment": _environment_validator,
    "export": _export_validator,
    "platform": _platform_validator,
}


def _score_for_diagnostics(diagnostics: Sequence[Mapping[str, Any]]) -> int:
    score = 100
    for diagnostic in diagnostics:
        severity = diagnostic.get("severity")
        score -= 12 if severity == "error" else 5
    return max(score, 0)


def _human_validator_name(name: str) -> str:
    return name.replace("_", " ")


def _human_summary(
    *,
    status: str,
    score: int,
    validator_reports: Sequence[Mapping[str, Any]],
    diagnostics: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    strengths = [
        f"{_human_validator_name(str(report.get('validator')))} passed"
        for report in validator_reports
        if not report.get("diagnostics")
    ]
    if not strengths:
        strengths = ["No validator passed without diagnostics."]

    needs_work = [
        f"{diagnostic.get('code')}: {diagnostic.get('message')}"
        for diagnostic in diagnostics[:6]
    ]
    if not needs_work:
        needs_work = ["No blocking scene-quality issues found."]

    return {
        "headline": f"Scene Quality: {score}/100 ({status})",
        "strengths": strengths[:6],
        "needs_work": needs_work,
    }


def run_scene_validators(
    scene_graph: Mapping[str, Any],
    *,
    root: str | Path | None = None,
    validators: Sequence[str] | None = None,
    require_export_artifacts: bool = False,
    platform: str | None = None,
) -> dict[str, Any]:
    """Run selected scene validators and return a machine-readable report."""
    context = SceneValidationContext(
        root=Path(root) if root is not None else Path.cwd(),
        require_export_artifacts=require_export_artifacts,
        platform=platform,
    )
    selected = tuple(validators or DEFAULT_VALIDATORS)
    validator_reports: list[dict[str, Any]] = []
    all_diagnostics: list[dict[str, Any]] = []
    base_diagnostics = check_scene_graph(scene_graph, root=context.root)
    if base_diagnostics:
        validator_reports.append(
            {
                "validator": "scene_graph_semantics",
                "score": _score_for_diagnostics(base_diagnostics),
                "diagnostics": base_diagnostics,
            }
        )
        all_diagnostics.extend(base_diagnostics)
    for name in selected:
        validator = _VALIDATORS.get(name)
        if validator is None:
            raise ValueError(f"unknown scene validator {name!r}")
        diagnostics = validator(scene_graph, context)
        validator_reports.append(
            {
                "validator": name,
                "score": _score_for_diagnostics(diagnostics),
                "diagnostics": diagnostics,
            }
        )
        all_diagnostics.extend(diagnostics)

    error_count = sum(1 for diagnostic in all_diagnostics if diagnostic.get("severity") == "error")
    warning_count = len(all_diagnostics) - error_count
    score = _score_for_diagnostics(all_diagnostics)
    status = "failed" if error_count else "passed_with_warnings" if warning_count else "passed"
    return {
        "schema_version": "lathe.scene_quality_report.v1",
        "scene_id": scene_graph.get("scene_id"),
        "scene_version": scene_graph.get("version"),
        "status": status,
        "score": score,
        "summary": {
            "validators": len(validator_reports),
            "diagnostics": len(all_diagnostics),
            "errors": error_count,
            "warnings": warning_count,
        },
        "human_summary": _human_summary(
            status=status,
            score=score,
            validator_reports=validator_reports,
            diagnostics=all_diagnostics,
        ),
        "validators": validator_reports,
        "diagnostics": all_diagnostics,
    }


def validate_scene_quality(scene_graph: Mapping[str, Any], *, root: str | Path | None = None) -> list[dict[str, Any]]:
    """Return flattened diagnostics for the default scene validator set."""
    report = run_scene_validators(scene_graph, root=root)
    diagnostics = report.get("diagnostics", [])
    return diagnostics if isinstance(diagnostics, list) else []
