"""Scene-to-asset source materialization helpers for Wonder readiness."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..checker import check_program
from ..core.errors import BuildError
from ..parser import LatheParseError, PromptInjectionError, parse_file
from ..planner import build_plan
from ..resolver import ResolutionError
from .graph import load_and_check_scene_graph
from .io import write_json_atomic, write_text_atomic
from .planner import plan_scene, validate_scene_plan_payload

SCENE_MATERIALIZATION_VERSION = "lathe.scene_materialization_manifest.v1"
SCENE_MATERIALIZATION_CONTRACT = "scene_materialization_manifest"
SCENE_MATERIALIZATION_SCHEMA_FILENAME = "scene_materialization_manifest.schema.json"

_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_NON_IDENTIFIER_RE = re.compile(r"[^a-z0-9_]+")
_ARCHITECTURE_TOKENS = {
    "arch",
    "architecture",
    "bridge",
    "ceiling",
    "column",
    "environment",
    "floor",
    "platform",
    "railing",
    "rib",
    "room",
    "shell",
    "stair",
    "structure",
    "tunnel",
    "wall",
    "window",
}
_MECHANICAL_TOKENS = {
    "airlock",
    "door",
    "gear",
    "hinge",
    "lock",
    "machine",
    "mechanical",
    "mechanism",
    "motor",
    "portal",
}
_GENERATED_SOURCE_ERRORS = (
    LatheParseError,
    PromptInjectionError,
    ResolutionError,
    OSError,
    KeyError,
    TypeError,
    ValueError,
)


class SceneMaterializeError(RuntimeError):
    """Raised when scene asset materialization cannot produce valid sources."""

    def __init__(self, diagnostics: list[dict[str, Any]]) -> None:
        super().__init__("Scene asset materialization failed")
        self.diagnostics = diagnostics


def materialize_scene_assets(
    scene_graph_path: str | Path,
    out_dir: str | Path,
    *,
    mode: str = "preview",
    build_assets: bool = False,
) -> dict[str, Any]:
    """Lower a Scene Graph into deterministic Lathe asset source files."""
    source_path = Path(scene_graph_path)
    scene_graph, diagnostics = load_and_check_scene_graph(source_path)
    if diagnostics:
        raise SceneMaterializeError(diagnostics)

    scene_plan = plan_scene(scene_graph, mode=mode)
    plan_diagnostics = validate_scene_plan_payload(scene_plan)
    if _has_error_diagnostic([*scene_plan.get("diagnostics", []), *plan_diagnostics]):
        raise SceneMaterializeError([*scene_plan.get("diagnostics", []), *plan_diagnostics])

    output_root = Path(out_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    write_json_atomic(output_root / "scene_graph.json", scene_graph)
    write_json_atomic(output_root / "scene_plan.json", scene_plan)

    scene_id = str(scene_graph.get("scene_id") or "scene")
    scene_module_slug = _slug(scene_id, fallback="scene")
    object_index = _objects_by_id(scene_graph)
    material_index = _materials_by_id(scene_graph)
    entries: list[dict[str, Any]] = []
    diagnostics_out: list[dict[str, Any]] = []

    for task in scene_plan.get("asset_tasks", []):
        if not isinstance(task, Mapping):
            continue
        entry = _materialize_asset_task(
            output_root=output_root,
            scene_id=scene_id,
            scene_module_slug=scene_module_slug,
            scene_graph=scene_graph,
            task=task,
            object_index=object_index,
            material_index=material_index,
        )
        entries.append(entry)
        diagnostics_out.extend(entry["check"]["diagnostics"])
        diagnostics_out.extend(entry["plan"]["diagnostics"])

    error_diagnostics = [diagnostic for diagnostic in diagnostics_out if diagnostic.get("severity") == "error"]
    if error_diagnostics:
        raise SceneMaterializeError(error_diagnostics)

    build_results: list[dict[str, Any]] = []
    if build_assets:
        for entry in entries:
            build_payload = _build_generated_asset_source(output_root, entry)
            entry["build"] = build_payload
            _attach_build_payload_to_metadata(output_root, entry["metadata_path"], build_payload)
            build_results.append(build_payload)
            diagnostics_out.extend(build_payload["diagnostics"])

    build_failures = [build for build in build_results if not build["ok"]]
    manifest: dict[str, Any] = {
        "schema_version": SCENE_MATERIALIZATION_VERSION,
        "scene_id": scene_id,
        "mode": mode,
        "source_scene_graph": "scene_graph.json",
        "source_scene_plan": "scene_plan.json",
        "generated_source_root": "assets",
        "summary": {
            "asset_tasks": len(entries),
            "source_files": len(entries),
            "object_instances": sum(len(entry["object_ids"]) for entry in entries),
            "instance_friendly_sources": sum(1 for entry in entries if entry["instancing"]["instance_friendly"]),
            "checker_errors": sum(
                1
                for entry in entries
                for diagnostic in entry["check"]["diagnostics"]
                if diagnostic.get("severity") == "error"
            ),
            "planner_errors": sum(
                1
                for entry in entries
                for diagnostic in entry["plan"]["diagnostics"]
                if diagnostic.get("severity") == "error"
            ),
            "builds_requested": len(build_results),
            "builds_succeeded": sum(1 for build in build_results if build["ok"]),
            "builds_failed": len(build_failures),
        },
        "asset_sources": entries,
        "diagnostics": diagnostics_out,
    }
    write_json_atomic(output_root / "scene_materialization_manifest.json", manifest)
    return {
        "ok": not build_failures,
        "command": "scene.materialize",
        "contract": SCENE_MATERIALIZATION_CONTRACT,
        "path": str(source_path),
        "out": str(output_root),
        "mode": mode,
        "build_assets": build_assets,
        "manifest": manifest,
        "diagnostics": diagnostics_out,
    }


def _materialize_asset_task(
    *,
    output_root: Path,
    scene_id: str,
    scene_module_slug: str,
    scene_graph: Mapping[str, Any],
    task: Mapping[str, Any],
    object_index: Mapping[str, Mapping[str, Any]],
    material_index: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    object_ids = [str(object_id) for object_id in task.get("object_ids", []) if isinstance(object_id, str)]
    objects = [object_index[object_id] for object_id in object_ids if object_id in object_index]
    source = task.get("source") if isinstance(task.get("source"), Mapping) else {}
    source_ref = str(source.get("ref") or (object_ids[0] if object_ids else "asset"))
    asset_name = _asset_name(source_ref, str(task.get("cache_key") or source_ref))
    asset_kind = _infer_asset_kind(source_ref, objects)
    material_ids = _material_ids_for_objects(objects)
    material_declarations = [
        _material_declaration(material_id, material_index.get(material_id, {})) for material_id in material_ids
    ]
    source_text = _asset_source_text(
        scene_id=scene_id,
        scene_module_slug=scene_module_slug,
        asset_name=asset_name,
        asset_kind=asset_kind,
        source_ref=source_ref,
        source=source,
        task=task,
        objects=objects,
        material_ids=material_ids,
        material_declarations=material_declarations,
    )

    source_rel = f"assets/{asset_name}/{asset_name}.lth"
    metadata_rel = f"assets/{asset_name}/metadata.json"
    source_path = _package_path(output_root, source_rel)
    metadata_path = _package_path(output_root, metadata_rel)
    write_text_atomic(source_path, source_text)

    check_payload = _check_source(source_path)
    plan_payload = _plan_source(source_path, asset_name) if check_payload["ok"] else {"ok": False, "diagnostics": []}
    metadata = {
        "schema_version": "lathe.generated_scene_asset_metadata.v1",
        "scene_id": scene_id,
        "asset_name": asset_name,
        "asset_kind": asset_kind,
        "asset_task_id": str(task.get("task_id") or ""),
        "cache_key": str(task.get("cache_key") or ""),
        "source": dict(source),
        "object_ids": object_ids,
        "source_scene_roles": sorted({str(obj.get("role")) for obj in objects if isinstance(obj.get("role"), str)}),
        "material_ids": material_ids,
        "instancing": _instancing_metadata(task),
        "provenance": {
            "created_by": "lathe.scene.materialize",
            "created_from": "scene_graph_object_task",
            "deterministic": True,
        },
        "check": check_payload,
        "plan": plan_payload,
    }
    write_json_atomic(metadata_path, metadata)
    return {
        "asset_task_id": str(task.get("task_id") or ""),
        "asset_name": asset_name,
        "asset_kind": asset_kind,
        "cache_key": str(task.get("cache_key") or ""),
        "source": dict(source),
        "object_ids": object_ids,
        "source_path": source_rel,
        "metadata_path": metadata_rel,
        "material_ids": material_ids,
        "instancing": metadata["instancing"],
        "check": check_payload,
        "plan": plan_payload,
    }


def _asset_source_text(
    *,
    scene_id: str,
    scene_module_slug: str,
    asset_name: str,
    asset_kind: str,
    source_ref: str,
    source: Mapping[str, Any],
    task: Mapping[str, Any],
    objects: list[Mapping[str, Any]],
    material_ids: list[str],
    material_declarations: list[str],
) -> str:
    role = _asset_role(objects, source_ref)
    style = _style_tokens(objects)
    interactions = _interaction_tokens(objects)
    scale = _asset_scale(objects)
    seed = _seed_from_key(str(task.get("cache_key") or asset_name))
    parts = _asset_parts(objects)
    negatives = _negative_tokens(asset_kind)
    lines = [
        f"module wonder.generated_assets.{scene_module_slug}.{asset_name}",
        "",
        f"// Generated by Lathe {SCENE_MATERIALIZATION_VERSION}.",
        f"// Source scene: {scene_id}.",
        f"// Source asset reference: {_comment_value(source_ref)}.",
        f"// Source kind: {_comment_value(str(source.get('kind') or 'generated'))}.",
        f"// Source object IDs: {', '.join(str(obj.get('object_id')) for obj in objects)}.",
        f"// Cache key: {_comment_value(str(task.get('cache_key') or ''))}.",
        "",
    ]
    if material_declarations:
        lines.extend(material_declarations)
        lines.append("")
    lines.extend(
        [
            f"asset {asset_name}: {asset_kind} {{",
            "  intent {",
            f"    role = {_source_string(role)}",
            f"    style = {_source_array(style)}",
            f"    parts = {_source_array(parts, identifiers=True)}",
            f"    materials = {_source_array(material_ids or ['mat_scene_default'], identifiers=True)}",
            f"    negatives = {_source_array(negatives)}",
            f"    scale = {scale}m",
            f"    interactions = {_source_array(interactions, identifiers=True)}",
            "  }",
            "",
            "  build {",
            "    shape {",
            "      mode = generate",
            "      candidates = 1",
            f"      seed = {seed}",
            "    }",
            "  }",
            "}",
            "",
        ]
    )
    return "\n".join(lines)


def _material_declaration(material_id: str, material: Mapping[str, Any]) -> str:
    pbr = material.get("pbr") if isinstance(material.get("pbr"), Mapping) else {}
    basecolor = _hex_to_rgb(pbr.get("basecolor")) or [128, 128, 128]
    emissive = _hex_to_rgb(pbr.get("emissive")) or [0, 0, 0]
    metallic = _number_or_default(pbr.get("metallic"), 0.0)
    roughness = _number_or_default(pbr.get("roughness"), 0.7)
    lines = [
        f"material {material_id} {{",
        f"  basecolor = {_source_array(basecolor)}",
        f"  metallic = {metallic:g}",
        f"  roughness = {roughness:g}",
        f"  emissive = {_source_array(emissive)}",
    ]
    role = material.get("role")
    if isinstance(role, str) and _IDENTIFIER_RE.match(role):
        lines.append(f"  surface_profile = {role}")
    lines.append("}")
    return "\n".join(lines)


def validate_scene_materialization_manifest_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return schema diagnostics for a Scene Materialization Manifest payload."""
    from ..wonder import validate_contract

    return validate_contract(SCENE_MATERIALIZATION_CONTRACT, payload)


def _check_source(path: Path) -> dict[str, Any]:
    try:
        program = parse_file(path)
        diagnostics = check_program(program)
    except _GENERATED_SOURCE_ERRORS as exc:
        diagnostics = [
            {
                "code": "SM1901",
                "name": "generated_asset_source_check_failed",
                "severity": "error",
                "phase": "scene_materialization_check",
                "path": str(path),
                "message": str(exc),
            }
        ]
    return {"ok": not _has_error_diagnostic(diagnostics), "diagnostics": diagnostics}


def _plan_source(path: Path, asset_name: str) -> dict[str, Any]:
    try:
        program = parse_file(path)
        plan = build_plan(program, asset_name)
    except _GENERATED_SOURCE_ERRORS as exc:
        return {
            "ok": False,
            "asset": asset_name,
            "diagnostics": [
                {
                    "code": "SM1902",
                    "name": "generated_asset_plan_failed",
                    "severity": "error",
                    "phase": "scene_materialization_plan",
                    "path": str(path),
                    "message": str(exc),
                }
            ],
        }
    return {
        "ok": True,
        "asset": asset_name,
        "kind": str(plan.get("kind") or ""),
        "stages": list(plan.get("stages", [])),
        "backend_stack_id": str(plan.get("backend_stack", {}).get("id") or ""),
        "diagnostics": [],
    }


def _build_generated_asset_source(output_root: Path, entry: Mapping[str, Any]) -> dict[str, Any]:
    source_path = _package_path(output_root, str(entry["source_path"]))
    build_rel = f"builds/{entry['asset_name']}"
    build_dir = _package_path(output_root, build_rel)
    try:
        program = parse_file(source_path)
        report = _run_build_asset(program, str(entry["asset_name"]), build_dir)
    except BuildError as exc:
        diagnostics = [
            _normalize_build_diagnostic(
                diagnostic,
                asset_name=str(entry["asset_name"]),
                source_path=str(source_path),
                message=str(exc),
            )
            for diagnostic in (exc.diagnostics or [{}])
        ]
        return {
            "requested": True,
            "ok": False,
            "asset": str(entry["asset_name"]),
            "out_dir": build_rel,
            "report_path": None,
            "certified": False,
            "diagnostics": diagnostics,
        }
    report_path = build_dir / "build_report.json"
    certified = bool(report.get("certified"))
    return {
        "requested": True,
        "ok": certified,
        "asset": str(entry["asset_name"]),
        "out_dir": build_rel,
        "report_path": f"{build_rel}/build_report.json" if report_path.is_file() else None,
        "certified": certified,
        "score": report.get("score"),
        "threshold": report.get("threshold"),
        "diagnostics": [],
    }


def _attach_build_payload_to_metadata(output_root: Path, metadata_path: str, build_payload: Mapping[str, Any]) -> None:
    path = _package_path(output_root, metadata_path)
    metadata = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        metadata = {}
    metadata["build"] = dict(build_payload)
    write_json_atomic(path, metadata)


def _run_build_asset(program: dict[str, Any], asset_name: str, build_dir: Path) -> dict[str, Any]:
    from ..executor import build_asset

    return build_asset(program, asset_name, build_dir)


def _normalize_build_diagnostic(
    diagnostic: Any,
    *,
    asset_name: str,
    source_path: str,
    message: str,
) -> dict[str, Any]:
    if isinstance(diagnostic, Mapping):
        payload = dict(diagnostic)
    else:
        payload = {}
    payload.setdefault("code", "SM1904")
    payload.setdefault("name", "generated_asset_build_failed")
    payload["severity"] = payload.get("severity") if payload.get("severity") in {"warning", "error"} else "error"
    payload.setdefault("phase", "scene_materialization_build")
    payload.setdefault("path", source_path)
    payload.setdefault("asset", asset_name)
    payload.setdefault("message", message or "Generated asset build failed.")
    return payload


def _objects_by_id(scene_graph: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(item["object_id"]): item
        for item in scene_graph.get("objects", [])
        if isinstance(item, Mapping) and isinstance(item.get("object_id"), str)
    }


def _materials_by_id(scene_graph: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(item["material_id"]): item
        for item in scene_graph.get("materials", [])
        if isinstance(item, Mapping) and isinstance(item.get("material_id"), str)
    }


def _material_ids_for_objects(objects: list[Mapping[str, Any]]) -> list[str]:
    material_ids: set[str] = set()
    for obj in objects:
        for binding in obj.get("material_bindings", []):
            if isinstance(binding, Mapping) and isinstance(binding.get("material"), str):
                material_ids.add(binding["material"])
    return sorted(material_ids)


def _infer_asset_kind(source_ref: str, objects: list[Mapping[str, Any]]) -> str:
    tokens = _classification_tokens(source_ref, objects)
    roles = {str(obj.get("role", "")).lower() for obj in objects}
    if roles & {"hero_prop", "narrative_clue"}:
        return "hard_surface_prop"
    if tokens & _ARCHITECTURE_TOKENS:
        return "env_module"
    if tokens & _MECHANICAL_TOKENS:
        return "mechanical_assembly"
    return "hard_surface_prop"


def _classification_tokens(source_ref: str, objects: list[Mapping[str, Any]]) -> set[str]:
    raw_parts: list[str] = [source_ref]
    for obj in objects:
        for field in ("object_id", "name", "role", "lathe_asset", "source_family", "source_kit"):
            value = obj.get(field)
            if isinstance(value, str):
                raw_parts.append(value)
    tokens: set[str] = set()
    for part in raw_parts:
        tokens.update(token for token in _NON_IDENTIFIER_RE.sub("_", part.lower()).split("_") if token)
    return tokens


def _asset_role(objects: list[Mapping[str, Any]], source_ref: str) -> str:
    roles = [str(obj.get("role")) for obj in objects if isinstance(obj.get("role"), str)]
    if len(set(roles)) == 1:
        name = objects[0].get("name") if objects and isinstance(objects[0].get("name"), str) else source_ref
        return f"{roles[0].replace('_', ' ')} generated from scene object {name}"
    if roles:
        return "shared scene asset for " + ", ".join(sorted(set(roles)))
    return f"generated scene asset for {source_ref}"


def _style_tokens(objects: list[Mapping[str, Any]]) -> list[str]:
    tags: set[str] = {"scene_ready"}
    for obj in objects:
        for tag in obj.get("semantic_tags", []):
            if isinstance(tag, str):
                tags.add(_slug(tag, fallback="tag"))
        role = obj.get("role")
        if isinstance(role, str):
            tags.add(_slug(role, fallback="role"))
    return sorted(tags)


def _interaction_tokens(objects: list[Mapping[str, Any]]) -> list[str]:
    interactions: set[str] = {"place_in_world"}
    for obj in objects:
        for affordance in obj.get("affordances", []):
            if isinstance(affordance, Mapping) and isinstance(affordance.get("action"), str):
                interactions.add(_slug(affordance["action"], fallback="interact"))
    return sorted(interactions)


def _asset_parts(objects: list[Mapping[str, Any]]) -> list[str]:
    parts = {"body"}
    for obj in objects:
        for binding in obj.get("material_bindings", []):
            if isinstance(binding, Mapping) and isinstance(binding.get("slot"), str):
                parts.add(_slug(binding["slot"], fallback="part"))
    return sorted(parts)


def _asset_scale(objects: list[Mapping[str, Any]]) -> str:
    scales: list[float] = []
    for obj in objects:
        transform = obj.get("transform")
        if not isinstance(transform, Mapping):
            continue
        raw_scale = transform.get("scale")
        if isinstance(raw_scale, list):
            scales.extend(float(value) for value in raw_scale if isinstance(value, int | float) and value > 0)
    if not scales:
        return "1"
    return f"{max(scales):.3f}".rstrip("0").rstrip(".")


def _negative_tokens(asset_kind: str) -> list[str]:
    if asset_kind == "env_module":
        return ["free_floating", "single_prop_only"]
    if asset_kind == "mechanical_assembly":
        return ["nonfunctional_shape", "ambiguous_mechanism"]
    return ["unscaled", "unplaceable"]


def _instancing_metadata(task: Mapping[str, Any]) -> dict[str, Any]:
    object_ids = [str(object_id) for object_id in task.get("object_ids", []) if isinstance(object_id, str)]
    return {
        "instance_friendly": len(object_ids) > 1 and not bool(task.get("requires_unique_build", False)),
        "object_count": len(object_ids),
        "requires_unique_build": bool(task.get("requires_unique_build", False)),
        "uniqueness_reasons": list(task.get("uniqueness_reasons", []))
        if isinstance(task.get("uniqueness_reasons"), list)
        else [],
    }


def _asset_name(source_ref: str, cache_key: str) -> str:
    return f"{_slug(source_ref, fallback='scene_asset')}_{_fingerprint(cache_key, size=8)}"


def _slug(value: str, *, fallback: str) -> str:
    slug = _NON_IDENTIFIER_RE.sub("_", value.lower()).strip("_")
    slug = re.sub(r"_+", "_", slug)
    if not slug:
        slug = fallback
    if not slug[0].isalpha():
        slug = f"{fallback}_{slug}"
    return slug[:72].rstrip("_") or fallback


def _fingerprint(value: str, *, size: int = 12) -> str:
    return hashlib.sha256(value.encode("utf-8"), usedforsecurity=False).hexdigest()[:size]


def _seed_from_key(value: str) -> int:
    return int(_fingerprint(value, size=8), 16)


def _source_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def _source_array(values: list[Any], *, identifiers: bool = False) -> str:
    items: list[str] = []
    for value in values:
        if identifiers and isinstance(value, str) and _IDENTIFIER_RE.match(value):
            items.append(value)
        else:
            items.append(json.dumps(value, ensure_ascii=True))
    return "[" + ", ".join(items) + "]"


def _hex_to_rgb(value: Any) -> list[int] | None:
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return None
    return [int(value[index : index + 2], 16) for index in (1, 3, 5)]


def _number_or_default(value: Any, default: float) -> float:
    if isinstance(value, int | float):
        return float(value)
    return default


def _comment_value(value: str) -> str:
    return value.replace("\n", " ").replace("\r", " ")


def _package_path(root: Path, relative_path: str) -> Path:
    target = (root / relative_path).resolve(strict=False)
    root_resolved = root.resolve(strict=False)
    if target != root_resolved and root_resolved not in target.parents:
        raise SceneMaterializeError(
            [
                {
                    "code": "SM1903",
                    "name": "generated_asset_path_escape",
                    "severity": "error",
                    "phase": "scene_materialization_write",
                    "path": relative_path,
                    "message": "Generated asset source path escapes the materialization output directory.",
                }
            ]
        )
    return target


def _has_error_diagnostic(diagnostics: list[dict[str, Any]]) -> bool:
    return any(diagnostic.get("severity") == "error" for diagnostic in diagnostics)


__all__ = [
    "SCENE_MATERIALIZATION_CONTRACT",
    "SCENE_MATERIALIZATION_SCHEMA_FILENAME",
    "SCENE_MATERIALIZATION_VERSION",
    "SceneMaterializeError",
    "materialize_scene_assets",
    "validate_scene_materialization_manifest_payload",
]
