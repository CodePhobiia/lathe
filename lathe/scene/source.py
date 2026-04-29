"""JSON-first Scene Graph source bridge.

This module deliberately does not parse the core ``.lth`` grammar.  Phase 7
scene source is a generated bridge: a human-readable scene-shaped preview plus
an embedded Scene Graph JSON payload that remains the durable truth.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ..wonder import validate_contract
from .graph import check_scene_graph

SCENE_SOURCE_BRIDGE_VERSION = "lathe.scene_source_bridge.v1"
SCENE_GRAPH_PAYLOAD_BEGIN = "//// LATHE_SCENE_GRAPH_JSON_V1_BEGIN"
SCENE_GRAPH_PAYLOAD_END = "//// LATHE_SCENE_GRAPH_JSON_V1_END"

_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_HAND_AUTHORED_SCENE_RE = re.compile(
    r"^\s*(module|scene|style|region|object|relationship|camera|camera_intent|light|lighting_plan|curiosity_anchor|hidden_state|export)\b"
)


def source_diagnostic(
    code: str,
    name: str,
    path: str,
    message: str,
    *,
    severity: str = "error",
    details: Mapping[str, Any] | None = None,
    source_span: Mapping[str, Any] | None = None,
    repair_hint: str | None = None,
) -> dict[str, Any]:
    """Build a scene-source bridge diagnostic."""
    payload: dict[str, Any] = {
        "code": code,
        "name": name,
        "severity": severity,
        "contract": "scene_source_bridge",
        "phase": "scene_source_bridge_parse",
        "path": path,
        "message": message,
    }
    if details:
        payload["details"] = dict(details)
    if source_span:
        payload["source_span"] = dict(source_span)
    if repair_hint:
        payload["repair_hint"] = repair_hint
    return payload


def scene_graph_to_source_diagnostics(scene_graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return bridge diagnostics for data not visible in the source preview."""
    json_only_paths = _json_only_preview_paths(scene_graph)
    if not json_only_paths:
        return []
    return [
        source_diagnostic(
            "SS2001",
            "json_only_scene_source_preview_fields",
            "/",
            (
                "Generated scene source preserves these Scene Graph fields in "
                "the embedded JSON payload, but the human-readable preview does "
                "not have a first-class textual representation for them yet."
            ),
            severity="warning",
            details={
                "json_only_paths": json_only_paths,
                "field_count": len(json_only_paths),
                "bridge_format": SCENE_SOURCE_BRIDGE_VERSION,
            },
            repair_hint=(
                "Keep editing these fields in Scene Graph JSON until the full "
                "scene parser supports equivalent source syntax."
            ),
        )
    ]


def validate_scene_graph_payload(
    scene_graph: Mapping[str, Any],
    *,
    root: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Return schema and semantic diagnostics for a Scene Graph payload."""
    diagnostics = validate_contract("scene_graph", dict(scene_graph))
    if diagnostics:
        return diagnostics
    return check_scene_graph(scene_graph, root=root)


def scene_graph_to_source(scene_graph: Mapping[str, Any]) -> str:
    """Serialize Scene Graph JSON to deterministic generated scene source."""
    json_payload = json.dumps(scene_graph, indent=2, sort_keys=False, allow_nan=False)
    commented_json_payload = "\n".join(_payload_comment_line(line) for line in json_payload.splitlines())
    sections = [
        *_source_header(scene_graph),
        "",
        *_scene_preview(scene_graph),
        "",
        "// Durable Scene Graph payload. Source-to-Scene-Graph reads this block only.",
        SCENE_GRAPH_PAYLOAD_BEGIN,
        commented_json_payload,
        SCENE_GRAPH_PAYLOAD_END,
        "",
    ]
    return "\n".join(sections)


def source_to_scene_graph(
    source_text: str,
    *,
    root: str | Path | None = None,
    source_path: str | Path | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Extract and validate the embedded Scene Graph payload from source text."""
    payload, diagnostics = extract_scene_graph_payload(source_text)
    if diagnostics:
        from .source_diagnostics import attach_source_spans

        return payload, attach_source_spans(diagnostics, source_text, source_path=source_path)
    diagnostics = validate_scene_graph_payload(payload, root=root)
    if diagnostics:
        from .source_diagnostics import attach_source_spans

        diagnostics = attach_source_spans(diagnostics, source_text, source_path=source_path)
    return payload, diagnostics


def extract_scene_graph_payload(source_text: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Extract the embedded Scene Graph JSON payload from generated source."""
    lines = source_text.splitlines()
    begin_indices = [index for index, line in enumerate(lines) if line.strip() == SCENE_GRAPH_PAYLOAD_BEGIN]
    end_indices = [index for index, line in enumerate(lines) if line.strip() == SCENE_GRAPH_PAYLOAD_END]

    if not begin_indices and not end_indices:
        return {}, [_missing_payload_diagnostic(source_text)]
    if len(begin_indices) != 1 or len(end_indices) != 1:
        return {}, [
            source_diagnostic(
                "SS1003",
                "malformed_scene_graph_payload_fence",
                "/payload",
                (
                    "Scene source must contain exactly one Scene Graph payload "
                    f"fence pair: {SCENE_GRAPH_PAYLOAD_BEGIN} and {SCENE_GRAPH_PAYLOAD_END}."
                ),
                details={"begin_count": len(begin_indices), "end_count": len(end_indices)},
            )
        ]

    begin_index = begin_indices[0]
    end_index = end_indices[0]
    if end_index <= begin_index:
        return {}, [
            source_diagnostic(
                "SS1003",
                "malformed_scene_graph_payload_fence",
                "/payload",
                "Scene Graph payload end fence must appear after the begin fence.",
                details={"begin_line": begin_index + 1, "end_line": end_index + 1},
            )
        ]

    json_text = "\n".join(_payload_json_line(line) for line in lines[begin_index + 1 : end_index])
    if not json_text.strip():
        return {}, [
            source_diagnostic(
                "SS1004",
                "empty_scene_graph_payload_json",
                "/payload",
                "Embedded Scene Graph payload is empty.",
                details={"begin_line": begin_index + 1, "end_line": end_index + 1},
            )
        ]

    try:
        raw = json.loads(json_text)
    except json.JSONDecodeError as exc:
        return {}, [
            source_diagnostic(
                "SS1004",
                "invalid_scene_graph_payload_json",
                "/payload",
                f"Embedded Scene Graph payload is invalid JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}.",
                details={
                    "payload_line": exc.lineno,
                    "payload_column": exc.colno,
                    "source_line": begin_index + exc.lineno + 1,
                },
                source_span={
                    "line": begin_index + exc.lineno + 1,
                    "column": exc.colno,
                    "end_line": begin_index + exc.lineno + 1,
                    "end_column": exc.colno + 1,
                },
                repair_hint="Fix the embedded Scene Graph JSON syntax, then rerun source conversion.",
            )
        ]
    if not isinstance(raw, dict):
        return {}, [
            source_diagnostic(
                "SS1005",
                "scene_graph_payload_root_not_object",
                "/payload",
                f"Embedded Scene Graph payload root must be a JSON object, got {type(raw).__name__}.",
            )
        ]
    return raw, []


def _payload_comment_line(line: str) -> str:
    return f"// {line}" if line else "//"


def _payload_json_line(line: str) -> str:
    stripped = line.lstrip()
    if not stripped.startswith("//"):
        return line
    payload = stripped[2:]
    if payload.startswith(" "):
        payload = payload[1:]
    return payload


def _missing_payload_diagnostic(source_text: str) -> dict[str, Any]:
    generated_bridge_source = SCENE_SOURCE_BRIDGE_VERSION in source_text
    if _looks_like_hand_authored_scene_source(source_text) and not generated_bridge_source:
        return source_diagnostic(
            "SS1002",
            "unsupported_hand_authored_scene_source",
            "/",
            (
                "This Phase 7 bridge only accepts generated scene source with an "
                "embedded Scene Graph JSON payload. Full hand-authored scene "
                "syntax parsing is deferred to the later parser implementation."
            ),
            details={"required_begin_fence": SCENE_GRAPH_PAYLOAD_BEGIN},
            repair_hint=(
                "Use generated scene source from lathe scene scene-graph-to-source, or provide Scene Graph JSON directly."
            ),
        )
    return source_diagnostic(
        "SS1001",
        "missing_scene_graph_payload",
        "/",
        (
            "Scene source does not contain an embedded Scene Graph JSON payload. "
            f"Expected a {SCENE_GRAPH_PAYLOAD_BEGIN} block."
        ),
        details={"required_begin_fence": SCENE_GRAPH_PAYLOAD_BEGIN},
        repair_hint="Add one embedded Scene Graph JSON payload block, then rerun source conversion.",
    )


def _looks_like_hand_authored_scene_source(source_text: str) -> bool:
    for line in source_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        if _HAND_AUTHORED_SCENE_RE.match(stripped):
            return True
    return False


def _source_header(scene_graph: Mapping[str, Any]) -> list[str]:
    scene_id = _identifier_or_fallback(scene_graph.get("scene_id"), "scene")
    return [
        f"// Generated by Lathe {SCENE_SOURCE_BRIDGE_VERSION}.",
        "// This is a JSON-first source bridge, not the core .lth scene parser.",
        "// The scene-shaped text is for review; the embedded JSON block preserves all v1 fields.",
        f"module wonder.generated.{scene_id}",
    ]


def _scene_preview(scene_graph: Mapping[str, Any]) -> list[str]:
    scene_id = _identifier_or_fallback(scene_graph.get("scene_id"), "scene")
    lines = [f"scene {scene_id} {{"]
    _append_assignment(lines, 1, "version", scene_graph.get("version"))
    if isinstance(scene_graph.get("brief_id"), str):
        _append_assignment(lines, 1, "brief", scene_graph["brief_id"])
    _append_assignment(lines, 1, "prompt", scene_graph.get("prompt"), force_string=True)
    lines.append("")

    style_bible = scene_graph.get("style_bible")
    if isinstance(style_bible, Mapping):
        lines.extend(_style_preview(style_bible))
        lines.append("")

    for region in _mapping_items(scene_graph, "regions"):
        lines.extend(_region_preview(region))
        lines.append("")

    for obj in _mapping_items(scene_graph, "objects"):
        lines.extend(_object_preview(obj))
        lines.append("")

    for relationship in _mapping_items(scene_graph, "relationships"):
        lines.extend(_relationship_preview(relationship))
        lines.append("")

    for light in _mapping_items(scene_graph, "lights"):
        lines.extend(_light_preview(light))
        lines.append("")

    for camera in _mapping_items(scene_graph, "cameras"):
        lines.extend(_camera_preview(camera))
        lines.append("")

    for anchor in _mapping_items(scene_graph, "curiosity_anchors"):
        lines.extend(_curiosity_anchor_preview(anchor))
        lines.append("")

    for hidden in _mapping_items(scene_graph, "hidden_state"):
        lines.extend(_hidden_state_preview(hidden))
        lines.append("")

    for export in _mapping_items(scene_graph, "exports"):
        lines.extend(_export_preview(export))
        lines.append("")

    lines.extend(_json_only_summary(scene_graph))
    lines.append("}")
    return lines


def _style_preview(style_bible: Mapping[str, Any]) -> list[str]:
    lines = ["  style scene_style {"]
    for field in ("mood", "palette", "materials", "forms", "lighting", "avoid"):
        if field in style_bible:
            _append_assignment(lines, 2, field, style_bible[field])
    lines.append("  }")
    return lines


def _region_preview(region: Mapping[str, Any]) -> list[str]:
    region_id = _identifier_or_fallback(region.get("region_id"), "region")
    region_type = _identifier_or_fallback(region.get("type"), "region_type")
    lines = [f"  region {region_id}: {region_type} {{"]
    for field in ("name", "purpose", "mood"):
        _append_assignment(lines, 2, field, region.get(field), force_string=True)
    bounds = region.get("bounds")
    if isinstance(bounds, Mapping):
        _append_assignment(lines, 2, "bounds.center", bounds.get("center"))
        _append_assignment(lines, 2, "bounds.size", bounds.get("size"))
    _append_assignment(lines, 2, "semantic_tags", region.get("semantic_tags"))
    lines.append("  }")
    return lines


def _object_preview(obj: Mapping[str, Any]) -> list[str]:
    object_id = _identifier_or_fallback(obj.get("object_id"), "obj")
    role = _identifier_or_fallback(obj.get("role"), "scene_role")
    lathe_asset = _identifier_or_fallback(obj.get("lathe_asset"), "asset")
    lines = [f"  object {object_id}: {role} from {lathe_asset} {{"]
    _append_assignment(lines, 2, "name", obj.get("name"), force_string=True)
    for field in ("region", "source_family", "source_kit", "variant"):
        if field in obj:
            _append_assignment(lines, 2, field, obj[field])
    transform = obj.get("transform")
    if isinstance(transform, Mapping):
        for field in ("position", "rotation", "scale"):
            _append_assignment(lines, 2, f"transform.{field}", transform.get(field))
    for binding in _nested_mapping_items(obj, "material_bindings"):
        slot = binding.get("slot")
        material = binding.get("material")
        if isinstance(slot, str) and _IDENTIFIER_RE.match(slot):
            _append_assignment(lines, 2, f"material_bindings.{slot}", material)
    _append_assignment(lines, 2, "semantic_tags", obj.get("semantic_tags"))
    lines.extend(_object_gameplay_preview(obj))
    state = obj.get("state")
    if isinstance(state, Mapping):
        for key, value in state.items():
            if isinstance(key, str) and _IDENTIFIER_RE.match(key):
                _append_assignment(lines, 2, f"state.{key}", value)
    lines.append("  }")
    return lines


def _object_gameplay_preview(obj: Mapping[str, Any]) -> list[str]:
    direct_gameplay = obj.get("gameplay")
    affordances = _nested_mapping_items(obj, "affordances")
    if not isinstance(direct_gameplay, Mapping) and not affordances:
        return []

    lines = ["    gameplay {"]
    if isinstance(direct_gameplay, Mapping):
        for key, value in direct_gameplay.items():
            if isinstance(key, str) and _IDENTIFIER_RE.match(key):
                _append_assignment(lines, 3, key, value)
    for affordance in affordances:
        affordance_id = _identifier_or_fallback(affordance.get("id"), "affordance")
        for field in ("action", "reveals", "requires"):
            _append_assignment(lines, 3, f"affordances.{affordance_id}.{field}", affordance.get(field))
    lines.append("    }")
    return lines


def _relationship_preview(relationship: Mapping[str, Any]) -> list[str]:
    relationship_id = _identifier_or_fallback(relationship.get("relationship_id"), "rel")
    relationship_type = _identifier_or_fallback(relationship.get("type"), "relationship_type")
    lines = [f"  relationship {relationship_id}: {relationship_type} {{"]
    for field in ("from", "to"):
        _append_assignment(lines, 2, field, relationship.get(field))
    if "description" in relationship:
        _append_assignment(lines, 2, "description", relationship["description"], force_string=True)
    lines.append("  }")
    return lines


def _light_preview(light: Mapping[str, Any]) -> list[str]:
    light_id = _identifier_or_fallback(light.get("light_id"), "light")
    light_type = _identifier_or_fallback(light.get("type"), "light_type")
    lines = [f"  lighting_plan {light_id}: {light_type} {{"]
    if "target" in light:
        _append_assignment(lines, 2, "target", light["target"])
    _append_assignment(lines, 2, "color", light.get("color"), force_string=True)
    _append_assignment(lines, 2, "intensity", light.get("intensity"))
    _append_assignment(lines, 2, "purpose", light.get("purpose"), force_string=True)
    lines.append("  }")
    return lines


def _camera_preview(camera: Mapping[str, Any]) -> list[str]:
    camera_id = _identifier_or_fallback(camera.get("camera_id"), "camera")
    framing = _identifier_or_fallback(camera.get("framing"), "framing")
    lines = [f"  camera_intent {camera_id}: {framing} {{"]
    _append_assignment(lines, 2, "target", camera.get("target"))
    _append_assignment(lines, 2, "purpose", camera.get("purpose"), force_string=True)
    transform = camera.get("transform")
    if isinstance(transform, Mapping):
        for field in ("position", "rotation", "scale"):
            _append_assignment(lines, 2, f"transform.{field}", transform.get(field))
    if "fov_degrees" in camera:
        _append_assignment(lines, 2, "fov_degrees", camera["fov_degrees"])
    lines.append("  }")
    return lines


def _curiosity_anchor_preview(anchor: Mapping[str, Any]) -> list[str]:
    anchor_id = _identifier_or_fallback(anchor.get("anchor_id"), "curiosity_anchor")
    lines = [f"  curiosity_anchor {anchor_id} {{"]
    for field in ("attached_to", "visible_clue", "hidden_fact", "suggested_user_actions"):
        _append_assignment(lines, 2, field, anchor.get(field), force_string=field in {"visible_clue", "hidden_fact"})
    for option in _nested_mapping_items(anchor, "expansion_options"):
        option_id = _identifier_or_fallback(option.get("id"), "option")
        for field in ("label", "target_scope", "required_assets", "continuity_constraints"):
            _append_assignment(
                lines,
                2,
                f"expansion_options.{option_id}.{field}",
                option.get(field),
                force_string=field == "label",
            )
    lines.append("  }")
    return lines


def _hidden_state_preview(hidden: Mapping[str, Any]) -> list[str]:
    hidden_id = _identifier_or_fallback(hidden.get("hidden_id"), "hidden_state")
    lines = [f"  hidden_state {hidden_id} {{"]
    _append_assignment(lines, 2, "attached_to", hidden.get("attached_to"))
    _append_assignment(lines, 2, "fact", hidden.get("fact"), force_string=True)
    _append_assignment(lines, 2, "reveal_condition", hidden.get("reveal_condition"), force_string=True)
    _append_assignment(lines, 2, "visible", hidden.get("visible"))
    lines.append("  }")
    return lines


def _export_preview(export: Mapping[str, Any]) -> list[str]:
    target = _identifier_or_fallback(export.get("target"), "export_target")
    lines = [f"  export {target} {{"]
    _append_assignment(lines, 2, "format", export.get("format"))
    _append_assignment(lines, 2, "path", export.get("path"), force_string=True)
    lines.append("  }")
    return lines


def _json_only_summary(scene_graph: Mapping[str, Any]) -> list[str]:
    json_only_counts = {
        "layout": 1 if isinstance(scene_graph.get("layout"), Mapping) else 0,
        "materials": len(scene_graph.get("materials", [])) if isinstance(scene_graph.get("materials"), list) else 0,
        "build_artifacts": len(scene_graph.get("build_artifacts", []))
        if isinstance(scene_graph.get("build_artifacts"), list)
        else 0,
        "memory_events": len(scene_graph.get("memory_events", []))
        if isinstance(scene_graph.get("memory_events"), list)
        else 0,
    }
    summary = ", ".join(f"{name}={count}" for name, count in json_only_counts.items())
    return [
        "  // JSON-only v1 data is preserved below, including object provenance, export",
        "  // metadata, material definitions, build artifacts, and memory.",
        f"  // Embedded payload summary: {summary}.",
    ]


def _json_only_preview_paths(scene_graph: Mapping[str, Any]) -> list[str]:
    paths: list[str] = []
    for collection in (
        "layout",
        "materials",
        "build_artifacts",
        "memory_events",
    ):
        value = scene_graph.get(collection)
        if isinstance(value, Mapping) or (isinstance(value, list) and value):
            paths.append(f"/{collection}")

    for index, obj in enumerate(_mapping_items(scene_graph, "objects")):
        if isinstance(obj.get("provenance"), Mapping):
            paths.append(f"/objects/{index}/provenance")

    for index, export in enumerate(_mapping_items(scene_graph, "exports")):
        if isinstance(export.get("metadata"), Mapping):
            paths.append(f"/exports/{index}/metadata")
    return paths


def _append_assignment(
    lines: list[str],
    indent: int,
    path: str,
    value: Any,
    *,
    force_string: bool = False,
) -> None:
    if value is None:
        return
    lines.append(f"{'  ' * indent}{path} = {_source_value(value, force_string=force_string)}")


def _source_value(value: Any, *, force_string: bool = False) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return json.dumps(value, allow_nan=False)
    if isinstance(value, str):
        if not force_string and _IDENTIFIER_RE.match(value):
            return value
        return json.dumps(value, ensure_ascii=True)
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return "[" + ", ".join(_source_value(item) for item in value) + "]"
    return json.dumps(value, ensure_ascii=True, sort_keys=False, allow_nan=False)


def _mapping_items(scene_graph: Mapping[str, Any], collection: str) -> list[Mapping[str, Any]]:
    raw = scene_graph.get(collection, [])
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, Mapping)]


def _nested_mapping_items(item: Mapping[str, Any], collection: str) -> list[Mapping[str, Any]]:
    raw = item.get(collection, [])
    if not isinstance(raw, list):
        return []
    return [child for child in raw if isinstance(child, Mapping)]


def _identifier_or_fallback(value: Any, fallback: str) -> str:
    if isinstance(value, str) and _IDENTIFIER_RE.match(value):
        return value
    return fallback


__all__ = [
    "SCENE_GRAPH_PAYLOAD_BEGIN",
    "SCENE_GRAPH_PAYLOAD_END",
    "SCENE_SOURCE_BRIDGE_VERSION",
    "extract_scene_graph_payload",
    "scene_graph_to_source",
    "scene_graph_to_source_diagnostics",
    "source_diagnostic",
    "source_to_scene_graph",
    "validate_scene_graph_payload",
]
