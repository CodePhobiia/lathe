"""Offline Scene Graph package builder for Phase 10 preview builds."""

from __future__ import annotations

import copy
import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from lathe.errors import LatheConfigError, LatheError, RuntimeConfigError
from lathe.paths import PathGuardError, safe_resolve
from lathe.runtime_config import apply_cli_overrides, load_runtime_config

from .graph import load_and_check_scene_graph
from .history import normalized_scene_graph
from .io import write_json_atomic, write_text_atomic
from .memory import create_world_memory, validate_world_memory
from .package import (
    SCENE_PACKAGE_MANIFEST_FILENAME,
    check_scene_package_manifest,
    init_scene_package,
)
from .planner import ScenePlanMode, plan_scene, validate_scene_plan_payload
from .validators import run_scene_validators

SceneBuildMode = Literal["preview", "final"]

_SCENE_MANIFEST_PATH = "reports/scene_manifest.json"
_SCENE_GRAPH_PATH = "graph/scene_graph.json"
_SCENE_GRAPH_NORMALIZED_PATH = "graph/scene_graph.normalized.json"
_WORLD_MEMORY_PATH = "graph/world_memory.json"
_SCENE_PLAN_PATH = "reports/scene_plan.json"
_SCENE_BUILD_REPORT_PATH = "reports/build_report.json"
_SCENE_QUALITY_REPORT_PATH = "reports/scene_quality_report.json"
_VALIDATION_REPORT_PATH = "reports/validation_report.json"
_WONDER_REPORT_PATH = "reports/wonder_report.json"
_SCENE_BUILD_PROXY_PATH = "build/scene_build_proxy_manifest.json"
_SCENE_ASSEMBLY_PATH = "build/scene_assembly_ir.json"
_OBJECT_SELECTION_PAYLOADS_PATH = "build/object_selection_payloads.json"
_SCENE_RENDER_ARTIFACTS_PATH = "reports/scene_render_artifacts.json"
_SCENE_EXPORT_ARTIFACTS_PATH = "reports/scene_export_artifacts.json"
_ASSET_REUSE_REPORT_PATH = "cache/asset_reuse_report.json"
_SCENE_MATERIALIZATION_ROOT = "source/materialized_assets"
_SCENE_MATERIALIZATION_MANIFEST_PATH = f"{_SCENE_MATERIALIZATION_ROOT}/scene_materialization_manifest.json"
_SCENE_BUILD_OPTIONS_VERSION = "lathe.scene_build_options.v1"
_SCENE_EXECUTOR_ID = "lathe.scene.executor.offline_proxy_v1"
_SAFE_BUILD_NAME_RE = re.compile(r"[^a-z0-9_]+")


class SceneBuildError(LatheConfigError):
    """Raised when the offline scene package build cannot complete."""

    def __init__(self, message: str, *, diagnostics: list[dict[str, Any]]) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics


def _diagnostic(
    code: str,
    name: str,
    path: str,
    message: str,
    *,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "name": name,
        "severity": "error",
        "contract": "scene_build",
        "phase": "scene_build",
        "path": path,
        "message": message,
    }
    if details is not None:
        payload["details"] = dict(details)
    return payload


def _raise_build_error(message: str, diagnostics: list[dict[str, Any]]) -> None:
    raise SceneBuildError(message, diagnostics=diagnostics)


def _has_error_diagnostic(diagnostics: list[dict[str, Any]]) -> bool:
    return any(diagnostic.get("severity") == "error" for diagnostic in diagnostics)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    write_json_atomic(path, payload)


def _read_json_object(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_text(path: Path, text: str) -> None:
    write_text_atomic(path, text)


def _contains_parent_traversal(path: Path) -> bool:
    return any(part == ".." for part in path.parts)


def _resolve_output_root(out_dir: str | Path) -> Path:
    raw = os.fspath(out_dir)
    path = Path(raw)
    if _contains_parent_traversal(path):
        _raise_build_error(
            "Scene build output path is unsafe.",
            [
                _diagnostic(
                    "SB1004",
                    "unsafe_scene_build_output_path",
                    "/out",
                    f"Scene build output path must not contain parent traversal: {raw!r}.",
                    details={"path": raw},
                )
            ],
        )
    root = path.parent if path.parent != Path() else Path.cwd()
    user = path.name or "."
    try:
        resolved = safe_resolve(root, user)
    except PathGuardError as exc:
        _raise_build_error(
            "Scene build output path is unsafe.",
            [
                _diagnostic(
                    "SB1004",
                    "unsafe_scene_build_output_path",
                    "/out",
                    f"Scene build output path is unsafe: {exc}",
                    details={"path": raw},
                )
            ],
        )
    if resolved.exists() and not resolved.is_dir():
        _raise_build_error(
            "Scene build output path is not a directory.",
            [
                _diagnostic(
                    "SB1005",
                    "scene_build_output_not_directory",
                    "/out",
                    f"Scene build output path must be a directory or missing path: {resolved}",
                    details={"path": str(resolved)},
                )
            ],
        )
    return resolved


def _resolve_runtime_config_path(raw_path: str | Path) -> Path:
    raw = os.fspath(raw_path)
    path = Path(raw)
    if _contains_parent_traversal(path):
        _raise_build_error(
            "Scene build runtime config path is unsafe.",
            [
                _diagnostic(
                    "SB1009",
                    "unsafe_scene_runtime_config_path",
                    "/runtime_config",
                    f"Scene build runtime config path must not contain parent traversal: {raw!r}.",
                    details={"path": raw},
                )
            ],
        )
    root = path.parent if path.parent != Path() else Path.cwd()
    user = path.name
    if not user:
        _raise_build_error(
            "Scene build runtime config path is invalid.",
            [
                _diagnostic(
                    "SB1009",
                    "unsafe_scene_runtime_config_path",
                    "/runtime_config",
                    f"Scene build runtime config path must point to a JSON file: {raw!r}.",
                    details={"path": raw},
                )
            ],
        )
    try:
        return safe_resolve(root, user)
    except PathGuardError as exc:
        _raise_build_error(
            "Scene build runtime config path is unsafe.",
            [
                _diagnostic(
                    "SB1009",
                    "unsafe_scene_runtime_config_path",
                    "/runtime_config",
                    f"Scene build runtime config path is unsafe: {exc}",
                    details={"path": raw},
                )
            ],
        )


def _load_scene_runtime_config(
    runtime_config_path: str | Path | None,
    runtime_config: Mapping[str, Any] | None,
    *,
    strict: bool,
    allow_fallback: bool,
) -> tuple[dict[str, Any], Path | None]:
    resolved_path: Path | None = None
    try:
        if runtime_config_path is not None:
            resolved_path = _resolve_runtime_config_path(runtime_config_path)
            loaded = load_runtime_config(resolved_path)
        elif runtime_config is not None:
            loaded = copy.deepcopy(dict(runtime_config))
        else:
            loaded = load_runtime_config(None)
    except (RuntimeConfigError, OSError) as exc:
        _raise_build_error(
            "Scene build runtime config could not be loaded.",
            [
                _diagnostic(
                    "SB1010",
                    "scene_runtime_config_load_failed",
                    "/runtime_config",
                    str(exc),
                    details={"path": str(runtime_config_path) if runtime_config_path is not None else None},
                )
            ],
        )
    return (
        apply_cli_overrides(
            loaded,
            shape_strict=True if strict else None,
            allow_fallback=True if allow_fallback else None,
        ),
        resolved_path,
    )


def _safe_package_path(package_dir: Path, relative_path: str) -> Path:
    try:
        return safe_resolve(package_dir, relative_path)
    except PathGuardError as exc:
        _raise_build_error(
            "Scene package path is unsafe.",
            [
                _diagnostic(
                    "SB1006",
                    "unsafe_scene_package_path",
                    f"/package/{relative_path}",
                    f"Scene package path {relative_path!r} is unsafe: {exc}",
                    details={"path": relative_path, "package_dir": str(package_dir)},
                )
            ],
        )


def _safe_build_name(value: str) -> str:
    name = _SAFE_BUILD_NAME_RE.sub("_", value.lower()).strip("_")
    return name[:120].rstrip("_") or "scene_build_item"


def _scene_id(scene_graph: Mapping[str, Any]) -> str:
    value = scene_graph.get("scene_id")
    return value if isinstance(value, str) else "scene"


def _collection(scene_graph: Mapping[str, Any], name: str) -> list[Mapping[str, Any]]:
    value = scene_graph.get(name, [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _object_ids(scene_graph: Mapping[str, Any]) -> list[str]:
    ids = [item.get("object_id") for item in _collection(scene_graph, "objects")]
    return sorted(item for item in ids if isinstance(item, str))


def _default_region_id(scene_graph: Mapping[str, Any]) -> str:
    first_region = next(iter(_collection(scene_graph, "regions")), {})
    region_id = first_region.get("region_id") if isinstance(first_region, Mapping) else None
    return region_id if isinstance(region_id, str) and region_id else "region_unassigned"


def _memory_scope_for_event(event: Mapping[str, Any], scene_graph: Mapping[str, Any]) -> str:
    affected_ids = event.get("affected_ids", [])
    if not isinstance(affected_ids, list) or not affected_ids:
        return "scene"
    first = next((item for item in affected_ids if isinstance(item, str)), None)
    if first is None or first == _scene_id(scene_graph):
        return "scene"
    if first.startswith("region_"):
        return "region"
    if first.startswith("obj_"):
        return "object"
    if first.startswith("camera_"):
        return "camera"
    if first.startswith("mat_"):
        return "material"
    if first.startswith("light_"):
        return "light"
    if first.startswith("curiosity_"):
        return "curiosity_anchor"
    if first.startswith("hidden_"):
        return "hidden_state"
    if first.startswith("rel_"):
        return "relationship"
    return "scene"


def _world_memory_events(scene_graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for event in _collection(scene_graph, "memory_events"):
        normalized = copy.deepcopy(dict(event))
        normalized.setdefault("scope", _memory_scope_for_event(normalized, scene_graph))
        normalized.setdefault("branch_id", "main")
        events.append(normalized)
    return events


def _asset_proxy_path(task: Mapping[str, Any]) -> str:
    return f"build/{_safe_build_name(str(task.get('task_id', 'asset_task')))}/asset_proxy_manifest.json"


def _scene_graph_with_plan_composition_instances(
    scene_graph: Mapping[str, Any],
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a runtime graph with synthetic setpiece instances from composition tasks."""
    asset_tasks = {
        str(task.get("task_id") or ""): task
        for task in plan.get("asset_tasks", [])
        if isinstance(task, Mapping) and str(task.get("task_id") or "")
    }
    existing_object_ids = set(_object_ids(scene_graph))
    additions: list[dict[str, Any]] = []
    for task in plan.get("assembly_tasks", []):
        if not isinstance(task, Mapping):
            continue
        instance_overrides = task.get("instance_overrides")
        if not isinstance(instance_overrides, Mapping):
            continue
        provenance = instance_overrides.get("provenance")
        if not isinstance(provenance, Mapping) or provenance.get("created_from") != "scene_composition_group":
            continue
        object_id = task.get("object_id")
        if not isinstance(object_id, str) or object_id in existing_object_ids:
            continue
        asset_task = asset_tasks.get(str(task.get("asset_task_id") or ""))
        source = asset_task.get("source") if isinstance(asset_task, Mapping) and isinstance(asset_task.get("source"), Mapping) else {}
        group_id = str(provenance.get("composition_group") or "")
        material_bindings: list[dict[str, str]] = []
        additions.append(
            {
                "object_id": object_id,
                "name": str(instance_overrides.get("name") or object_id),
                "role": str(instance_overrides.get("role") or "environment_structure"),
                "region": str(task.get("region") or _default_region_id(scene_graph)),
                "lathe_asset": str(source.get("ref") or object_id.removeprefix("obj_")),
                "source_family": str(source.get("source_family") or "procedural_setpiece"),
                "transform": copy.deepcopy(task.get("transform") if isinstance(task.get("transform"), Mapping) else {}),
                "material_bindings": material_bindings,
                "semantic_tags": [
                    tag for tag in instance_overrides.get("semantic_tags", []) if isinstance(tag, str)
                ]
                if isinstance(instance_overrides.get("semantic_tags"), list)
                else ["scene_composition", "generated_setpiece"],
                "state": {
                    "synthetic_scene_composition_instance": True,
                    "scene_composition_group": group_id,
                    "composition_member_object_ids": [
                        item
                        for item in provenance.get("member_object_ids", [])
                        if isinstance(item, str)
                    ]
                    if isinstance(provenance.get("member_object_ids"), list)
                    else [],
                },
                "provenance": copy.deepcopy(dict(provenance)),
            }
        )
        existing_object_ids.add(object_id)
    if not additions:
        return copy.deepcopy(dict(scene_graph))
    runtime_graph = copy.deepcopy(dict(scene_graph))
    objects = list(runtime_graph.get("objects", [])) if isinstance(runtime_graph.get("objects"), list) else []
    runtime_graph["objects"] = [
        *objects,
        *sorted(additions, key=lambda item: str(item.get("object_id") or "")),
    ]
    return runtime_graph


def _asset_proxy_manifest(
    task: Mapping[str, Any],
    *,
    mode: SceneBuildMode,
    build_options: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "lathe.scene_asset_proxy_manifest.v1",
        "task_id": task.get("task_id"),
        "task_type": "asset_build",
        "mode": mode,
        "build_options": copy.deepcopy(dict(build_options)),
        "status": "planned",
        "offline_proxy": True,
        "object_ids": list(task.get("object_ids", [])) if isinstance(task.get("object_ids"), list) else [],
        "cache_key": task.get("cache_key"),
        "source": copy.deepcopy(task.get("source", {})),
        "variant": task.get("variant"),
        "message": "No asset compiler, Blender, mesh, render, or export artifact was produced in this offline preview build.",
    }


def _asset_proxy_reuse_fingerprint(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": payload.get("schema_version"),
        "task_id": payload.get("task_id"),
        "mode": payload.get("mode"),
        "build_options": copy.deepcopy(payload.get("build_options")),
        "object_ids": copy.deepcopy(payload.get("object_ids")),
        "cache_key": payload.get("cache_key"),
        "source": copy.deepcopy(payload.get("source")),
        "variant": payload.get("variant"),
    }


def _write_asset_proxy_manifest(
    package_dir: Path,
    relative_path: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    path = _safe_package_path(package_dir, relative_path)
    existing = _read_json_object(path) if path.exists() else None
    reused = (
        existing is not None
        and _asset_proxy_reuse_fingerprint(existing) == _asset_proxy_reuse_fingerprint(payload)
    )
    if not reused:
        _write_json(path, payload)
    return {
        "task_id": payload.get("task_id"),
        "path": relative_path,
        "cache_key": payload.get("cache_key"),
        "object_ids": copy.deepcopy(payload.get("object_ids", [])),
        "source": copy.deepcopy(payload.get("source", {})),
        "status": "reused" if reused else "built",
        "reused": reused,
        "reuse_reason": "cache_key_match" if reused else "cache_miss_or_input_change",
    }


def _verify_asset_build_artifacts(package_dir: Path, asset_proxy_paths: Mapping[str, str]) -> None:
    missing = [
        {"task_id": task_id, "path": relative_path}
        for task_id, relative_path in sorted(asset_proxy_paths.items())
        if not _safe_package_path(package_dir, relative_path).is_file()
    ]
    if not missing:
        return
    _raise_build_error(
        "Scene asset build artifact is missing.",
        [
            _diagnostic(
                "SB1013",
                "missing_asset_build_artifact",
                "/build/asset_tasks",
                "Scene build expected per-asset build artifacts that were not written.",
                details={"missing": missing},
            )
        ],
    )


def _asset_reuse_report(
    scene_graph: Mapping[str, Any],
    cache_records: list[dict[str, Any]],
    *,
    mode: SceneBuildMode,
) -> dict[str, Any]:
    reused = [record for record in cache_records if record.get("reused") is True]
    return {
        "schema_version": "lathe.scene_asset_reuse_report.v1",
        "scene_id": _scene_id(scene_graph),
        "mode": mode,
        "asset_tasks": copy.deepcopy(cache_records),
        "summary": {
            "asset_tasks": len(cache_records),
            "reused_assets": len(reused),
            "built_assets": len(cache_records) - len(reused),
        },
    }


def _materialize_missing_scene_assets(
    scene_graph_path: str | Path,
    package_dir: Path,
    *,
    mode: SceneBuildMode,
) -> dict[str, Any]:
    from .materialize import SceneMaterializeError, materialize_scene_assets

    try:
        return materialize_scene_assets(
            scene_graph_path,
            _safe_package_path(package_dir, _SCENE_MATERIALIZATION_ROOT),
            mode=mode,
            build_assets=True,
        )
    except SceneMaterializeError as exc:
        _raise_build_error(
            "Scene asset materialization failed.",
            [
                _diagnostic(
                    "SB1015",
                    "scene_asset_materialization_failed",
                    f"/{_SCENE_MATERIALIZATION_ROOT}",
                    "Scene asset materialization failed before generated asset builds could complete.",
                    details={"mode": mode},
                ),
                *copy.deepcopy(exc.diagnostics),
            ],
        )


def _asset_materialization_summary(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {
            "requested": False,
            "manifest_path": None,
            "source_files": 0,
            "nested_source_files": 0,
            "nested_assembly_files": 0,
            "parent_builds_requested": 0,
            "parent_builds_succeeded": 0,
            "parent_builds_failed": 0,
            "nested_builds_requested": 0,
            "nested_builds_succeeded": 0,
            "nested_builds_failed": 0,
            "builds_requested": 0,
            "builds_succeeded": 0,
            "builds_failed": 0,
        }
    manifest = payload.get("manifest") if isinstance(payload.get("manifest"), Mapping) else {}
    summary = manifest.get("summary") if isinstance(manifest.get("summary"), Mapping) else {}
    return {
        "requested": True,
        "manifest_path": _SCENE_MATERIALIZATION_MANIFEST_PATH,
        "source_files": int(summary.get("source_files", 0) or 0),
        "nested_source_files": int(summary.get("nested_source_files", 0) or 0),
        "nested_assembly_files": int(summary.get("nested_assembly_files", 0) or 0),
        "parent_builds_requested": int(summary.get("parent_builds_requested", 0) or 0),
        "parent_builds_succeeded": int(summary.get("parent_builds_succeeded", 0) or 0),
        "parent_builds_failed": int(summary.get("parent_builds_failed", 0) or 0),
        "nested_builds_requested": int(summary.get("nested_builds_requested", 0) or 0),
        "nested_builds_succeeded": int(summary.get("nested_builds_succeeded", 0) or 0),
        "nested_builds_failed": int(summary.get("nested_builds_failed", 0) or 0),
        "builds_requested": int(summary.get("builds_requested", 0) or 0),
        "builds_succeeded": int(summary.get("builds_succeeded", 0) or 0),
        "builds_failed": int(summary.get("builds_failed", 0) or 0),
    }


def _raise_asset_materialization_failure(payload: Mapping[str, Any]) -> None:
    diagnostics = payload.get("diagnostics") if isinstance(payload.get("diagnostics"), list) else []
    _raise_build_error(
        "Scene asset materialization build failed.",
        [
            _diagnostic(
                "SB1014",
                "scene_asset_materialization_build_failed",
                f"/{_SCENE_MATERIALIZATION_MANIFEST_PATH}",
                "One or more generated asset sources failed the Lathe asset build pipeline.",
                details=_asset_materialization_summary(payload),
            ),
            *copy.deepcopy(diagnostics),
        ],
    )


def _provider_fallback_trace(build_options: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "runtime": copy.deepcopy(build_options.get("runtime", {})),
        "effective_runtime": copy.deepcopy(build_options.get("effective_runtime", {})),
        "fallbacks": copy.deepcopy(build_options.get("fallbacks", {})),
        "diagnostic_policy": copy.deepcopy(build_options.get("diagnostic_policy", {})),
    }


def _scene_build_report(
    scene_graph: Mapping[str, Any],
    plan: Mapping[str, Any],
    quality_report: Mapping[str, Any],
    asset_reuse_report: Mapping[str, Any],
    *,
    mode: SceneBuildMode,
    build_options: Mapping[str, Any],
    render_report: Mapping[str, Any],
    export_report: Mapping[str, Any],
    asset_materialization: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    materialization_summary = _asset_materialization_summary(asset_materialization)
    artifacts = {
        "scene_graph": _SCENE_GRAPH_PATH,
        "scene_graph_normalized": _SCENE_GRAPH_NORMALIZED_PATH,
        "world_memory": _WORLD_MEMORY_PATH,
        "scene_plan": _SCENE_PLAN_PATH,
        "validation_report": _VALIDATION_REPORT_PATH,
        "scene_quality_report": _SCENE_QUALITY_REPORT_PATH,
        "wonder_report": _WONDER_REPORT_PATH,
        "scene_manifest": _SCENE_MANIFEST_PATH,
        "scene_package_manifest": SCENE_PACKAGE_MANIFEST_FILENAME,
        "scene_build_proxy": _SCENE_BUILD_PROXY_PATH,
        "asset_reuse_report": _ASSET_REUSE_REPORT_PATH,
        "scene_assembly": _SCENE_ASSEMBLY_PATH,
        "object_selection_payloads": _OBJECT_SELECTION_PAYLOADS_PATH,
        "scene_render_artifacts": _SCENE_RENDER_ARTIFACTS_PATH,
        "scene_export_artifacts": _SCENE_EXPORT_ARTIFACTS_PATH,
    }
    if materialization_summary["requested"]:
        artifacts["scene_materialization_manifest"] = _SCENE_MATERIALIZATION_MANIFEST_PATH
    return {
        "schema_version": "lathe.scene_build_report.v1",
        "scene_id": _scene_id(scene_graph),
        "scene_version": scene_graph.get("version"),
        "mode": mode,
        "status": "proxy_scene_package_built",
        "build_options": copy.deepcopy(dict(build_options)),
        "artifacts": artifacts,
        "counts": {
            "asset_tasks": len(plan.get("asset_tasks", [])) if isinstance(plan.get("asset_tasks"), list) else 0,
            "assembly_tasks": len(plan.get("assembly_tasks", [])) if isinstance(plan.get("assembly_tasks"), list) else 0,
            "render_tasks": len(plan.get("render_tasks", [])) if isinstance(plan.get("render_tasks"), list) else 0,
            "export_tasks": len(plan.get("export_tasks", [])) if isinstance(plan.get("export_tasks"), list) else 0,
            "render_artifacts": len(render_report.get("artifacts", []))
            if isinstance(render_report.get("artifacts"), list)
            else 0,
            "export_artifacts": len(export_report.get("artifacts", []))
            if isinstance(export_report.get("artifacts"), list)
            else 0,
            "asset_builds_requested": materialization_summary["builds_requested"],
            "asset_builds_succeeded": materialization_summary["builds_succeeded"],
            "asset_builds_failed": materialization_summary["builds_failed"],
            "nested_source_files": materialization_summary["nested_source_files"],
            "nested_assembly_files": materialization_summary["nested_assembly_files"],
            "nested_asset_builds_requested": materialization_summary["nested_builds_requested"],
            "nested_asset_builds_succeeded": materialization_summary["nested_builds_succeeded"],
            "nested_asset_builds_failed": materialization_summary["nested_builds_failed"],
        },
        "quality": {
            "status": quality_report.get("status"),
            "score": quality_report.get("score"),
            "summary": copy.deepcopy(quality_report.get("summary", {})),
        },
        "asset_build_reports": copy.deepcopy(asset_reuse_report.get("asset_tasks", [])),
        "cache_reuse": copy.deepcopy(asset_reuse_report.get("summary", {})),
        "asset_materialization": materialization_summary,
        "provider_fallback_trace": _provider_fallback_trace(build_options),
        "diagnostics": copy.deepcopy(plan.get("diagnostics", [])),
    }


def _scene_build_proxy_manifest(
    plan: Mapping[str, Any],
    *,
    mode: SceneBuildMode,
    build_options: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "lathe.scene_build_proxy_manifest.v1",
        "scene_id": plan.get("scene_id"),
        "mode": mode,
        "build_options": copy.deepcopy(dict(build_options)),
        "status": "planned",
        "offline_proxy": True,
        "assembly_task_ids": [task.get("task_id") for task in plan.get("assembly_tasks", []) if isinstance(task, Mapping)],
        "render_task_ids": [task.get("task_id") for task in plan.get("render_tasks", []) if isinstance(task, Mapping)],
        "export_task_ids": [task.get("task_id") for task in plan.get("export_tasks", []) if isinstance(task, Mapping)],
        "message": "Scene assembly is represented by deterministic plan records only; runtime assembly is deferred.",
    }


def _build_manifest_entries(
    plan: Mapping[str, Any],
    asset_proxy_paths: Mapping[str, str],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = [
        {"kind": "scene_build", "path": _SCENE_BUILD_PROXY_PATH, "status": "planned"}
    ]
    for task in plan.get("asset_tasks", []):
        if not isinstance(task, Mapping):
            continue
        task_id = str(task.get("task_id", ""))
        entry: dict[str, Any] = {
            "kind": "asset_build",
            "path": asset_proxy_paths[task_id],
            "status": "planned",
        }
        object_ids = task.get("object_ids", [])
        if isinstance(object_ids, list) and len(object_ids) == 1 and isinstance(object_ids[0], str):
            entry["object_id"] = object_ids[0]
        entries.append(entry)
    return entries


def _nested_assembly_source_entries(asset_materialization: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(asset_materialization, Mapping):
        return []
    manifest = asset_materialization.get("manifest")
    if not isinstance(manifest, Mapping):
        return []
    entries: list[dict[str, Any]] = []
    for source in manifest.get("asset_sources", []) or []:
        if not isinstance(source, Mapping):
            continue
        nested_assets = source.get("nested_assets")
        if not isinstance(nested_assets, Mapping):
            continue
        assembly = nested_assets.get("assembly")
        if not isinstance(assembly, Mapping) or not isinstance(assembly.get("path"), str):
            continue
        entries.append(
            {
                "kind": "lathe_source",
                "path": f"{_SCENE_MATERIALIZATION_ROOT}/{assembly['path']}",
                "description": f"Nested asset assembly manifest for {source.get('asset_name', 'generated asset')}.",
            }
        )
    return entries


def _nested_assembly_export_payloads(
    asset_materialization: Mapping[str, Any] | None,
    package_dir: Path,
) -> list[dict[str, Any]]:
    if not isinstance(asset_materialization, Mapping):
        return []
    manifest = asset_materialization.get("manifest")
    if not isinstance(manifest, Mapping):
        return []
    payloads: list[dict[str, Any]] = []
    for source in manifest.get("asset_sources", []) or []:
        if not isinstance(source, Mapping):
            continue
        nested_assets = source.get("nested_assets")
        if not isinstance(nested_assets, Mapping):
            continue
        assembly_ref = nested_assets.get("assembly")
        if not isinstance(assembly_ref, Mapping) or not isinstance(assembly_ref.get("path"), str):
            continue
        assembly_path = _safe_package_path(package_dir, f"{_SCENE_MATERIALIZATION_ROOT}/{assembly_ref['path']}")
        try:
            assembly = json.loads(assembly_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeError):
            continue
        if not isinstance(assembly, dict):
            continue
        assembly["scene_object_ids"] = list(source.get("object_ids") or [])
        assembly["scene_object_id"] = assembly["scene_object_ids"][0] if assembly["scene_object_ids"] else ""
        assembly["materialization_root"] = _SCENE_MATERIALIZATION_ROOT
        assembly["package_path"] = f"{_SCENE_MATERIALIZATION_ROOT}/{assembly_ref['path']}"
        payloads.append(assembly)
    return payloads


def _render_manifest_entries(render_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for artifact in render_report.get("artifacts", []):
        if not isinstance(artifact, Mapping):
            continue
        path = artifact.get("path")
        render_pass = artifact.get("render_pass")
        if not isinstance(path, str) or not isinstance(render_pass, str):
            continue
        entry: dict[str, Any] = {
            "camera_id": artifact.get("camera_id"),
            "path": path,
            "passes": [render_pass],
            "status": "built",
        }
        entries.append(entry)
    return entries


def _export_manifest_entries(export_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for artifact in export_report.get("artifacts", []):
        if not isinstance(artifact, Mapping):
            continue
        target = artifact.get("target")
        path = artifact.get("path")
        if target != "glb" or not isinstance(path, str):
            continue
        entries.append({"target": "glb", "path": path, "status": "built"})
    return entries


def _built_render_records(render_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "camera_id": artifact.get("camera_id"),
            "render_pass": artifact.get("render_pass"),
            "status": artifact.get("status", "built"),
            "artifact_path": artifact.get("path"),
            "renderer": artifact.get("renderer"),
            "resolution": [artifact.get("width"), artifact.get("height")],
        }
        for artifact in render_report.get("artifacts", [])
        if isinstance(artifact, Mapping)
    ]


def _built_export_records(export_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "target": artifact.get("target"),
            "format": artifact.get("format"),
            "status": artifact.get("status", "built"),
            "artifact_path": artifact.get("path"),
            "object_count": artifact.get("object_count"),
            "identity": copy.deepcopy(artifact.get("identity", {})),
        }
        for artifact in export_report.get("artifacts", [])
        if isinstance(artifact, Mapping)
    ]


def _scene_manifest(
    scene_graph: Mapping[str, Any],
    plan: Mapping[str, Any],
    quality_report: Mapping[str, Any],
    *,
    mode: SceneBuildMode,
    build_options: Mapping[str, Any],
    asset_proxy_paths: Mapping[str, str],
    render_report: Mapping[str, Any],
    export_report: Mapping[str, Any],
) -> dict[str, Any]:
    asset_paths_by_object: dict[str, str] = {}
    for task in plan.get("asset_tasks", []):
        if not isinstance(task, Mapping):
            continue
        task_id = str(task.get("task_id", ""))
        object_ids = task.get("object_ids", [])
        if not isinstance(object_ids, list):
            continue
        for object_id in object_ids:
            if isinstance(object_id, str):
                asset_paths_by_object[object_id] = asset_proxy_paths[task_id]

    objects = [
        {
            "object_id": object_id,
            "asset_proxy_path": asset_paths_by_object.get(object_id),
            "status": "planned",
        }
        for object_id in _object_ids(scene_graph)
    ]
    return {
        "schema_version": "lathe.scene_manifest.v1",
        "scene_id": _scene_id(scene_graph),
        "scene_version": scene_graph.get("version"),
        "mode": mode,
        "status": "offline_preview_package",
        "offline": True,
        "build_options": copy.deepcopy(dict(build_options)),
        "package_paths": {
            "scene_graph": _SCENE_GRAPH_PATH,
            "scene_graph_normalized": _SCENE_GRAPH_NORMALIZED_PATH,
            "world_memory": _WORLD_MEMORY_PATH,
            "scene_plan": _SCENE_PLAN_PATH,
            "build_report": _SCENE_BUILD_REPORT_PATH,
            "validation_report": _VALIDATION_REPORT_PATH,
            "scene_quality_report": _SCENE_QUALITY_REPORT_PATH,
            "wonder_report": _WONDER_REPORT_PATH,
            "scene_manifest": _SCENE_MANIFEST_PATH,
            "scene_build_proxy": _SCENE_BUILD_PROXY_PATH,
            "asset_reuse_report": _ASSET_REUSE_REPORT_PATH,
            "scene_assembly": _SCENE_ASSEMBLY_PATH,
            "object_selection_payloads": _OBJECT_SELECTION_PAYLOADS_PATH,
            "scene_render_artifacts": _SCENE_RENDER_ARTIFACTS_PATH,
            "scene_export_artifacts": _SCENE_EXPORT_ARTIFACTS_PATH,
        },
        "objects": objects,
        "planned_renders": [
            {
                "task_id": task.get("task_id"),
                "camera_id": task.get("camera_id"),
                "status": "planned",
                "artifact_path": None,
                "passes": list(task.get("passes", [])) if isinstance(task.get("passes"), list) else [],
            }
            for task in plan.get("render_tasks", [])
            if isinstance(task, Mapping)
        ],
        "built_renders": _built_render_records(render_report),
        "planned_exports": [
            {
                "task_id": task.get("task_id"),
                "target": task.get("target"),
                "format": task.get("format"),
                "declared_path": task.get("path"),
                "status": "planned",
                "artifact_path": None,
            }
            for task in plan.get("export_tasks", [])
            if isinstance(task, Mapping)
        ],
        "built_exports": _built_export_records(export_report),
        "quality": {
            "status": quality_report.get("status"),
            "score": quality_report.get("score"),
            "summary": copy.deepcopy(quality_report.get("summary", {})),
        },
    }


def _wonder_report(
    scene_graph: Mapping[str, Any],
    plan: Mapping[str, Any],
    quality_report: Mapping[str, Any],
    *,
    mode: SceneBuildMode,
    build_options: Mapping[str, Any],
    render_report: Mapping[str, Any],
    export_report: Mapping[str, Any],
    asset_materialization: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    counts = plan.get("metadata", {}).get("counts", {}) if isinstance(plan.get("metadata"), Mapping) else {}
    built_renders = len(render_report.get("artifacts", [])) if isinstance(render_report.get("artifacts"), list) else 0
    built_exports = [
        artifact for artifact in export_report.get("artifacts", []) if isinstance(artifact, Mapping) and artifact.get("target") == "glb"
    ]
    materialization_summary = _asset_materialization_summary(asset_materialization)
    artifacts = {
        "scene_graph": _SCENE_GRAPH_PATH,
        "scene_graph_normalized": _SCENE_GRAPH_NORMALIZED_PATH,
        "world_memory": _WORLD_MEMORY_PATH,
        "scene_plan": _SCENE_PLAN_PATH,
        "build_report": _SCENE_BUILD_REPORT_PATH,
        "validation_report": _VALIDATION_REPORT_PATH,
        "scene_quality_report": _SCENE_QUALITY_REPORT_PATH,
        "scene_manifest": _SCENE_MANIFEST_PATH,
        "scene_package_manifest": SCENE_PACKAGE_MANIFEST_FILENAME,
        "asset_reuse_report": _ASSET_REUSE_REPORT_PATH,
        "scene_render_artifacts": _SCENE_RENDER_ARTIFACTS_PATH,
        "scene_export_artifacts": _SCENE_EXPORT_ARTIFACTS_PATH,
    }
    if materialization_summary["requested"]:
        artifacts["scene_materialization_manifest"] = _SCENE_MATERIALIZATION_MANIFEST_PATH
    notes = [
        "No Blender process was launched; render artifacts are deterministic proxy PNGs.",
        "GLB export is a deterministic proxy scene export with object IDs preserved as node/geometry names and sidecar metadata.",
    ]
    if materialization_summary["requested"]:
        notes.append(
            "Generated Lathe asset sources were materialized and built through the asset build pipeline; scene render/export artifacts still use deterministic proxy geometry."
        )
    else:
        notes.append("No provider-backed asset compiler was launched; object geometry is deterministic proxy geometry.")
    return {
        "schema_version": "lathe.wonder_report.v1",
        "scene_id": _scene_id(scene_graph),
        "scene_version": scene_graph.get("version"),
        "mode": mode,
        "status": "proxy_scene_package_built",
        "build_options": copy.deepcopy(dict(build_options)),
        "summary": (
            f"Built deterministic {mode} scene package for {_scene_id(scene_graph)!r} "
            "from Scene Graph JSON with proxy render and GLB export artifacts."
        ),
        "counts": copy.deepcopy(counts),
        "artifact_counts": {
            "render_files": built_renders,
            "glb_exports": len(built_exports),
            "asset_builds_requested": materialization_summary["builds_requested"],
            "asset_builds_succeeded": materialization_summary["builds_succeeded"],
            "asset_builds_failed": materialization_summary["builds_failed"],
            "nested_source_files": materialization_summary["nested_source_files"],
            "nested_assembly_files": materialization_summary["nested_assembly_files"],
            "nested_asset_builds_requested": materialization_summary["nested_builds_requested"],
            "nested_asset_builds_succeeded": materialization_summary["nested_builds_succeeded"],
            "nested_asset_builds_failed": materialization_summary["nested_builds_failed"],
        },
        "quality": {
            "status": quality_report.get("status"),
            "score": quality_report.get("score"),
            "diagnostics": copy.deepcopy(quality_report.get("summary", {})),
        },
        "artifacts": artifacts,
        "notes": notes,
        "diagnostics": copy.deepcopy(plan.get("diagnostics", [])),
    }


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return str(path)


def _validate_mode(mode: str) -> SceneBuildMode:
    if mode not in {"preview", "final"}:
        _raise_build_error(
            "Scene build mode is invalid.",
            [
                _diagnostic(
                    "SB1001",
                    "invalid_scene_build_mode",
                    "/mode",
                    "Scene build mode must be 'preview' or 'final'.",
                    details={"mode": mode},
                )
            ],
        )
    return mode  # type: ignore[return-value]


def _load_valid_scene_graph(scene_graph_path: str | Path) -> dict[str, Any]:
    try:
        scene_graph, diagnostics = load_and_check_scene_graph(scene_graph_path)
    except (LatheError, OSError) as exc:
        _raise_build_error(
            "Scene Graph could not be loaded.",
            [
                _diagnostic(
                    "SB1002",
                    "scene_graph_load_failed",
                    "/scene_graph",
                    str(exc),
                    details={"path": str(scene_graph_path)},
                )
            ],
        )
    if diagnostics:
        _raise_build_error("Scene Graph is invalid.", diagnostics)
    return scene_graph


def _validate_plan(plan: dict[str, Any]) -> None:
    diagnostics = [*plan.get("diagnostics", []), *validate_scene_plan_payload(plan)]
    if _has_error_diagnostic(diagnostics):
        _raise_build_error("Scene Plan is invalid.", diagnostics)


def _string_from_mapping(mapping: Mapping[str, Any], key: str, default: str = "") -> str:
    value = mapping.get(key)
    return value if isinstance(value, str) else default


def _build_options(
    *,
    mode: SceneBuildMode,
    runtime_config_path: Path | None,
    runtime_config_provided: bool,
    runtime_config: Mapping[str, Any],
    deterministic: bool,
    allow_fallback: bool,
    strict: bool,
    build_assets: bool,
) -> dict[str, Any]:
    shape = runtime_config.get("shape", {}) if isinstance(runtime_config.get("shape"), Mapping) else {}
    return {
        "schema_version": _SCENE_BUILD_OPTIONS_VERSION,
        "executor": _SCENE_EXECUTOR_ID,
        "mode": mode,
        "runtime_config": {
            "provided": runtime_config_provided,
            "path": _display_path(runtime_config_path) if runtime_config_path is not None else None,
        },
        "deterministic": bool(deterministic),
        "allow_fallback": bool(allow_fallback),
        "strict": bool(strict),
        "diagnostic_policy": {
            "scene_validation": "warnings_are_errors" if strict else "errors_are_errors",
            "plan_diagnostics": "warnings_are_errors" if strict else "errors_are_errors",
            "fallback_diagnostics": "errors_are_blocking" if strict else "warnings_allowed",
        },
        "runtime": {
            "provider_calls": "not_executed",
            "asset_build": "lathe.asset_build_pipeline.v1" if build_assets else "deterministic_proxy_manifest",
            "asset_materialization": "lathe.scene.materialize.v1" if build_assets else "not_executed",
            "renderer": "lathe.scene.proxy_renderer.v1",
            "exporter": "lathe.scene.proxy_glb_exporter.v1",
        },
        "effective_runtime": {
            "shape_provider": _string_from_mapping(shape, "provider", "auto"),
            "shape_strict": bool(shape.get("strict", False)),
            "shape_allow_fallback": bool(shape.get("allow_fallback", False)),
        },
        "fallbacks": {
            "deterministic_proxy_assets": True,
            "deterministic_proxy_renderer": True,
            "deterministic_proxy_glb_exporter": True,
            "provider_fallbacks_executed": False,
        },
    }


def _blocking_strict_diagnostics(diagnostics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        copy.deepcopy(diagnostic)
        for diagnostic in diagnostics
        if diagnostic.get("severity") in {"warning", "error"}
    ]


def _raise_strict_diagnostics(message: str, diagnostics: list[dict[str, Any]], *, pointer: str) -> None:
    blocking = _blocking_strict_diagnostics(diagnostics)
    if not blocking:
        return
    codes = [str(diagnostic.get("code", "")) for diagnostic in blocking if diagnostic.get("code")]
    _raise_build_error(
        message,
        [
            _diagnostic(
                "SB1011",
                "strict_scene_build_diagnostics",
                pointer,
                message,
                details={"codes": codes},
            ),
            *blocking,
        ],
    )


def _strict_fallback_diagnostics(plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for index, task in enumerate(plan.get("asset_tasks", [])):
        if not isinstance(task, Mapping):
            continue
        source = task.get("source")
        if not isinstance(source, Mapping) or source.get("kind") != "generated_fallback":
            continue
        diagnostics.append(
            _diagnostic(
                "SB1012",
                "strict_scene_fallback_blocked",
                f"/asset_tasks/{index}/source",
                "Strict scene build does not allow generated fallback asset sources.",
                details={
                    "task_id": task.get("task_id"),
                    "object_ids": list(task.get("object_ids", [])) if isinstance(task.get("object_ids"), list) else [],
                    "source": copy.deepcopy(dict(source)),
                },
            )
        )
    return diagnostics


def _validate_plan_strictness(plan: dict[str, Any], *, strict: bool) -> None:
    diagnostics = [*plan.get("diagnostics", []), *validate_scene_plan_payload(plan)]
    if _has_error_diagnostic(diagnostics):
        _raise_build_error("Scene Plan is invalid.", diagnostics)
    if strict:
        fallback_diagnostics = _strict_fallback_diagnostics(plan)
        if fallback_diagnostics:
            _raise_build_error(
                "Strict scene build blocked fallback asset planning.",
                [*fallback_diagnostics, *_blocking_strict_diagnostics(diagnostics)],
            )
        _raise_strict_diagnostics("Strict scene build blocked Scene Plan diagnostics.", diagnostics, pointer="/scene_plan")


def _build_world_memory(scene_graph: Mapping[str, Any]) -> dict[str, Any]:
    world_memory = create_world_memory(
        scene_graph,
        summary=f"Offline build continuity memory for {_scene_id(scene_graph)}.",
        events=_world_memory_events(scene_graph),
    )
    diagnostics = validate_world_memory(world_memory, scene_graph=scene_graph)
    if diagnostics:
        _raise_build_error("World Memory could not be derived from the Scene Graph.", diagnostics)
    return world_memory


def _validate_quality(
    scene_graph: Mapping[str, Any],
    scene_graph_path: str | Path,
    *,
    strict: bool,
) -> dict[str, Any]:
    report = run_scene_validators(scene_graph, root=Path(scene_graph_path).parent, require_export_artifacts=False)
    diagnostics = report.get("diagnostics", [])
    if isinstance(diagnostics, list) and _has_error_diagnostic(diagnostics):
        _raise_build_error("Scene quality validation failed.", diagnostics)
    if strict and isinstance(diagnostics, list):
        _raise_strict_diagnostics(
            "Strict scene build blocked scene validation diagnostics.",
            diagnostics,
            pointer="/scene_quality_report/diagnostics",
        )
    return report


def _render_passes_from_plan(plan: Mapping[str, Any]) -> list[str] | None:
    passes: list[str] = []
    seen: set[str] = set()
    for task in plan.get("render_tasks", []):
        if not isinstance(task, Mapping):
            continue
        task_passes = task.get("passes", [])
        if not isinstance(task_passes, list):
            continue
        for item in task_passes:
            if isinstance(item, str) and item not in seen:
                seen.add(item)
                passes.append(item)
    return passes or None


def _export_tasks_from_plan(plan: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [task for task in plan.get("export_tasks", []) if isinstance(task, Mapping)]


def build_scene_preview(
    scene_graph_path: str | Path,
    out_dir: str | Path,
    *,
    mode: ScenePlanMode = "preview",
    runtime_config_path: str | Path | None = None,
    runtime_config: Mapping[str, Any] | None = None,
    deterministic: bool = False,
    allow_fallback: bool = False,
    strict: bool = False,
    build_assets: bool = False,
) -> dict[str, Any]:
    """Build a deterministic offline scene preview package from Scene Graph JSON.

    The package contains normalized graph, memory, plan, validation, report,
    scene manifest, planned proxy build records, deterministic proxy render
    passes, and deterministic proxy GLB export artifacts. It intentionally does
    not execute Blender or mesh providers. The Lathe asset build pipeline is
    only invoked for generated asset sources when ``build_assets`` is true.
    """
    from .artifacts import SceneArtifactError, export_scene_glbs, render_scene_graph
    from .assembly import assemble_scene, validate_scene_assembly_payload

    build_mode = _validate_mode(str(mode))
    resolved_runtime_config, resolved_runtime_config_path = _load_scene_runtime_config(
        runtime_config_path,
        runtime_config,
        strict=bool(strict),
        allow_fallback=bool(allow_fallback),
    )
    build_options = _build_options(
        mode=build_mode,
        runtime_config_path=resolved_runtime_config_path,
        runtime_config_provided=runtime_config_path is not None or runtime_config is not None,
        runtime_config=resolved_runtime_config,
        deterministic=bool(deterministic),
        allow_fallback=bool(allow_fallback),
        strict=bool(strict),
        build_assets=bool(build_assets),
    )
    scene_graph = _load_valid_scene_graph(scene_graph_path)
    scene_plan = plan_scene(scene_graph, mode=build_mode)
    scene_plan["metadata"]["build_options"] = copy.deepcopy(build_options)
    _validate_plan_strictness(scene_plan, strict=bool(strict))
    runtime_scene_graph = _scene_graph_with_plan_composition_instances(scene_graph, scene_plan)
    quality_report = _validate_quality(scene_graph, scene_graph_path, strict=bool(strict))
    world_memory = _build_world_memory(scene_graph)
    scene_assembly = assemble_scene(runtime_scene_graph)
    assembly_diagnostics = validate_scene_assembly_payload(scene_assembly)
    if assembly_diagnostics:
        _raise_build_error("Scene Assembly IR is invalid.", assembly_diagnostics)

    out_root = _resolve_output_root(out_dir)
    package_dir = _safe_package_path(out_root, _scene_id(scene_graph))
    try:
        manifest_path, package_manifest = init_scene_package(
            package_dir,
            scene_id=_scene_id(scene_graph),
            overwrite=True,
        )
    except (LatheError, OSError) as exc:
        _raise_build_error(
            "Scene Package could not be initialized.",
            [
                _diagnostic(
                    "SB1007",
                    "scene_package_init_failed",
                    "/scene_package_manifest",
                    str(exc),
                    details={"package_dir": str(package_dir)},
                )
            ],
        )

    asset_materialization: dict[str, Any] | None = None
    if build_assets:
        asset_materialization = _materialize_missing_scene_assets(
            scene_graph_path,
            package_dir,
            mode=build_mode,
        )
        if not asset_materialization.get("ok"):
            _raise_asset_materialization_failure(asset_materialization)

    asset_proxy_paths = {
        str(task.get("task_id", "")): _asset_proxy_path(task)
        for task in scene_plan.get("asset_tasks", [])
        if isinstance(task, Mapping)
    }
    normalized_graph = normalized_scene_graph(runtime_scene_graph)
    try:
        render_report = render_scene_graph(
            runtime_scene_graph,
            package_dir,
            mode=build_mode,
            passes=_render_passes_from_plan(scene_plan),
            resolution=scene_plan.get("metadata", {}).get("budgets", {}).get("render_resolution")
            if isinstance(scene_plan.get("metadata"), Mapping)
            and isinstance(scene_plan.get("metadata", {}).get("budgets"), Mapping)
            else None,
            include_topdown=True,
            include_contact_sheet=True,
        )
        export_report = export_scene_glbs(
            runtime_scene_graph,
            package_dir,
            mode=build_mode,
            export_tasks=_export_tasks_from_plan(scene_plan),
            nested_assemblies=_nested_assembly_export_payloads(asset_materialization, package_dir),
        )
    except SceneArtifactError as exc:
        _raise_build_error("Scene render/export artifacts could not be built.", exc.diagnostics)
    scene_manifest = _scene_manifest(
        runtime_scene_graph,
        scene_plan,
        quality_report,
        mode=build_mode,
        build_options=build_options,
        asset_proxy_paths=asset_proxy_paths,
        render_report=render_report,
        export_report=export_report,
    )
    wonder_report = _wonder_report(
        runtime_scene_graph,
        scene_plan,
        quality_report,
        mode=build_mode,
        build_options=build_options,
        render_report=render_report,
        export_report=export_report,
        asset_materialization=asset_materialization,
    )
    cache_records: list[dict[str, Any]] = []
    asset_reuse_report = _asset_reuse_report(scene_graph, cache_records, mode=build_mode)
    scene_build_report = _scene_build_report(
        runtime_scene_graph,
        scene_plan,
        quality_report,
        asset_reuse_report,
        mode=build_mode,
        build_options=build_options,
        render_report=render_report,
        export_report=export_report,
        asset_materialization=asset_materialization,
    )

    try:
        _write_text(_safe_package_path(package_dir, "source/prompt.txt"), str(scene_graph.get("prompt", "")) + "\n")
        _write_json(_safe_package_path(package_dir, "source/style_bible.json"), dict(scene_graph["style_bible"]))
        _write_json(_safe_package_path(package_dir, _SCENE_GRAPH_PATH), scene_graph)
        _write_json(_safe_package_path(package_dir, _SCENE_GRAPH_NORMALIZED_PATH), normalized_graph)
        _write_json(_safe_package_path(package_dir, _WORLD_MEMORY_PATH), world_memory)
        _write_json(_safe_package_path(package_dir, _SCENE_PLAN_PATH), scene_plan)
        _write_json(_safe_package_path(package_dir, _SCENE_ASSEMBLY_PATH), scene_assembly)
        _write_json(
            _safe_package_path(package_dir, _OBJECT_SELECTION_PAYLOADS_PATH),
            {"schema_version": "lathe.object_selection_payloads.v1", "objects": scene_assembly["object_selection_payloads"]},
        )
        _write_json(_safe_package_path(package_dir, _VALIDATION_REPORT_PATH), quality_report)
        _write_json(_safe_package_path(package_dir, _SCENE_QUALITY_REPORT_PATH), quality_report)
        _write_json(_safe_package_path(package_dir, _WONDER_REPORT_PATH), wonder_report)
        _write_json(_safe_package_path(package_dir, _SCENE_MANIFEST_PATH), scene_manifest)
        _write_json(
            _safe_package_path(package_dir, _SCENE_BUILD_PROXY_PATH),
            _scene_build_proxy_manifest(scene_plan, mode=build_mode, build_options=build_options),
        )
        for task in scene_plan.get("asset_tasks", []):
            if not isinstance(task, Mapping):
                continue
            task_id = str(task.get("task_id", ""))
            cache_records.append(
                _write_asset_proxy_manifest(
                    package_dir,
                    asset_proxy_paths[task_id],
                    _asset_proxy_manifest(task, mode=build_mode, build_options=build_options),
                )
            )
        _verify_asset_build_artifacts(package_dir, asset_proxy_paths)
        asset_reuse_report = _asset_reuse_report(scene_graph, cache_records, mode=build_mode)
        scene_build_report = _scene_build_report(
            runtime_scene_graph,
            scene_plan,
            quality_report,
            asset_reuse_report,
            mode=build_mode,
            build_options=build_options,
            render_report=render_report,
            export_report=export_report,
            asset_materialization=asset_materialization,
        )
        _write_json(_safe_package_path(package_dir, _ASSET_REUSE_REPORT_PATH), asset_reuse_report)
        _write_json(_safe_package_path(package_dir, _SCENE_BUILD_REPORT_PATH), scene_build_report)
    except OSError as exc:
        _raise_build_error(
            "Scene Package artifact write failed.",
            [
                _diagnostic(
                    "SB1008",
                    "scene_package_write_failed",
                    "/scene_package",
                    str(exc),
                    details={"package_dir": str(package_dir)},
                )
            ],
        )

    package_manifest["source"] = [
        {"kind": "prompt", "path": "source/prompt.txt", "description": "Prompt copied from Scene Graph."},
        {
            "kind": "style_bible",
            "path": "source/style_bible.json",
            "description": "Style bible copied from Scene Graph.",
        },
    ]
    if asset_materialization is not None:
        package_manifest["source"].append(
            {
                "kind": "lathe_source",
                "path": _SCENE_MATERIALIZATION_MANIFEST_PATH,
                "description": "Generated Lathe asset sources and build outputs from scene materialization.",
            }
        )
        package_manifest["source"].extend(_nested_assembly_source_entries(asset_materialization))
    package_manifest["graph"] = {
        "scene_graph": _SCENE_GRAPH_PATH,
        "scene_graph_normalized": _SCENE_GRAPH_NORMALIZED_PATH,
    }
    package_manifest["build_options"] = copy.deepcopy(build_options)
    package_manifest["build"] = [
        *_build_manifest_entries(scene_plan, asset_proxy_paths),
        {"kind": "stage_bundle", "path": _SCENE_ASSEMBLY_PATH, "status": "built"},
        {"kind": "selector_manifest", "path": _OBJECT_SELECTION_PAYLOADS_PATH, "status": "built"},
    ]
    package_manifest["renders"] = _render_manifest_entries(render_report)
    package_manifest["exports"] = _export_manifest_entries(export_report)
    package_manifest["reports"] = [
        {"kind": "build_report", "path": _SCENE_BUILD_REPORT_PATH, "status": "built"},
        {"kind": "build_report", "path": _SCENE_PLAN_PATH, "status": "validated"},
        {"kind": "validation", "path": _VALIDATION_REPORT_PATH, "status": "validated"},
        {"kind": "validation", "path": _SCENE_QUALITY_REPORT_PATH, "status": "validated"},
        {"kind": "wonder_report", "path": _WONDER_REPORT_PATH, "status": "validated"},
        {"kind": "build_report", "path": _SCENE_MANIFEST_PATH, "status": "built"},
        {"kind": "build_report", "path": _SCENE_RENDER_ARTIFACTS_PATH, "status": "built"},
        {"kind": "build_report", "path": _SCENE_EXPORT_ARTIFACTS_PATH, "status": "built"},
    ]
    diagnostics = check_scene_package_manifest(package_manifest, root=package_dir, require_exists=True)
    if diagnostics:
        _raise_build_error("Scene Package manifest is invalid.", diagnostics)
    _write_json(manifest_path, package_manifest)

    materialization_summary = _asset_materialization_summary(asset_materialization)
    result_artifacts = {
        "scene_graph": _SCENE_GRAPH_PATH,
        "scene_graph_normalized": _SCENE_GRAPH_NORMALIZED_PATH,
        "world_memory": _WORLD_MEMORY_PATH,
        "scene_plan": _SCENE_PLAN_PATH,
        "build_report": _SCENE_BUILD_REPORT_PATH,
        "validation_report": _VALIDATION_REPORT_PATH,
        "scene_quality_report": _SCENE_QUALITY_REPORT_PATH,
        "wonder_report": _WONDER_REPORT_PATH,
        "scene_manifest": _SCENE_MANIFEST_PATH,
        "scene_package_manifest": SCENE_PACKAGE_MANIFEST_FILENAME,
        "asset_reuse_report": _ASSET_REUSE_REPORT_PATH,
        "scene_render_artifacts": _SCENE_RENDER_ARTIFACTS_PATH,
        "scene_export_artifacts": _SCENE_EXPORT_ARTIFACTS_PATH,
    }
    if materialization_summary["requested"]:
        result_artifacts["scene_materialization_manifest"] = _SCENE_MATERIALIZATION_MANIFEST_PATH

    return {
        "ok": True,
        "command": "scene.build",
        "contract": "scene_package_manifest",
        "scene_id": _scene_id(scene_graph),
        "scene_version": scene_graph.get("version"),
        "mode": build_mode,
        "build_options": copy.deepcopy(build_options),
        "asset_materialization": materialization_summary,
        "package_dir": _display_path(package_dir),
        "manifest_path": _display_path(manifest_path),
        "artifacts": result_artifacts,
        "counts": {
            "objects": len(_object_ids(scene_graph)),
            "asset_tasks": len(scene_plan.get("asset_tasks", [])),
            "assembly_tasks": len(scene_plan.get("assembly_tasks", [])),
            "render_tasks": len(scene_plan.get("render_tasks", [])),
            "export_tasks": len(scene_plan.get("export_tasks", [])),
            "render_artifacts": len(render_report.get("artifacts", []))
            if isinstance(render_report.get("artifacts"), list)
            else 0,
            "export_artifacts": len(export_report.get("artifacts", []))
            if isinstance(export_report.get("artifacts"), list)
            else 0,
            "memory_events": len(world_memory.get("events", [])) if isinstance(world_memory.get("events"), list) else 0,
            "asset_builds_requested": materialization_summary["builds_requested"],
            "asset_builds_succeeded": materialization_summary["builds_succeeded"],
            "asset_builds_failed": materialization_summary["builds_failed"],
            "nested_source_files": materialization_summary["nested_source_files"],
            "nested_assembly_files": materialization_summary["nested_assembly_files"],
            "nested_asset_builds_requested": materialization_summary["nested_builds_requested"],
            "nested_asset_builds_succeeded": materialization_summary["nested_builds_succeeded"],
            "nested_asset_builds_failed": materialization_summary["nested_builds_failed"],
        },
        "quality": {
            "status": quality_report.get("status"),
            "score": quality_report.get("score"),
        },
        "cache_reuse": copy.deepcopy(asset_reuse_report.get("summary", {})),
        "provider_fallback_trace": _provider_fallback_trace(build_options),
        "diagnostics": list(scene_plan.get("diagnostics", [])),
    }


__all__ = ["SceneBuildError", "SceneBuildMode", "build_scene_preview"]
