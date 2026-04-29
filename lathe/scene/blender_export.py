"""Blender-backed scene export helpers for Wonder Scene Graph payloads."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from lathe.capabilities import probe_blender
from lathe.paths import PathGuardError, safe_resolve
from lathe.sandbox.blender import run_blender_sandboxed

from .artifacts import SCENE_EXPORT_ARTIFACTS_VERSION, SceneArtifactError, export_scene_glb
from .io import write_json_atomic
from .layout import instancing_metadata_by_object_id

BLENDER_EXPORTER_ID = "lathe.scene.blender_exporter.v1"
BLENDER_EXPORT_METADATA_VERSION = "lathe.scene_blender_export_metadata.v1"
BLENDER_EXPORT_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "blender_export_blend.py"

_SAFE_FILE_RE = re.compile(r"[^a-z0-9_]+")


def export_scene_blend(
    scene_graph: Mapping[str, Any],
    package_dir: str | Path,
    *,
    mode: str = "preview",
    include_collision_nodes: bool = False,
) -> dict[str, Any]:
    """Export a Scene Graph to a Blender ``.blend`` file through the sandbox."""
    package_root = Path(package_dir)
    scene_id = _scene_id(scene_graph)
    blend_path = _safe_package_path(package_root, f"exports/{_safe_file(scene_id, suffix='.blend')}")
    report_path = _safe_package_path(package_root, "reports/scene_export_artifacts.json")
    metadata_path = _safe_package_path(package_root, "reports/blender_export_metadata.json")
    summary_path = _safe_package_path(package_root, "reports/blender_export_summary.json")
    log_dir = _safe_package_path(package_root, "reports/blender_logs")

    intermediate_root = _safe_package_path(package_root, "build/blender_export_intermediate")
    glb_report = export_scene_glb(
        scene_graph,
        intermediate_root,
        mode=mode,  # type: ignore[arg-type]
        include_collision_nodes=include_collision_nodes,
    )
    glb_artifact = next(
        (item for item in glb_report.get("artifacts", []) if isinstance(item, Mapping) and item.get("target") == "glb"),
        None,
    )
    if not isinstance(glb_artifact, Mapping) or not isinstance(glb_artifact.get("path"), str):
        _raise_blender_error(
            "Blender export could not produce a proxy GLB intermediate.",
            "SX1200",
            "blender_proxy_glb_missing",
            "/exports/blender/intermediate_glb",
            "Blender export requires a proxy GLB intermediate, but none was written.",
        )
    glb_path = intermediate_root / str(glb_artifact["path"])

    metadata = _blender_metadata(scene_graph, exporter=BLENDER_EXPORTER_ID)
    blend_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    _write_json(metadata_path, metadata)
    probe = probe_blender()
    if not probe.get("available"):
        _raise_blender_error(
            "Blender executable is not available for scene export.",
            "SX1201",
            "blender_export_runtime_unavailable",
            "/exports/blender/probe",
            "Blender was explicitly requested for scene export, but no Blender executable was available.",
            details={"probe": probe},
        )
    blender_path = str(probe.get("path") or "")
    command = [
        blender_path,
        "--background",
        "--factory-startup",
        "--python",
        str(BLENDER_EXPORT_SCRIPT),
        "--",
        "--input",
        str(glb_path),
        "--output",
        str(blend_path),
        "--summary",
        str(summary_path),
        "--metadata",
        str(metadata_path),
    ]
    result = run_blender_sandboxed(
        command,
        cwd=package_root,
        expect_files=[blend_path, summary_path],
        log_dir=log_dir,
        log_prefix="scene_blender_export",
    )
    if not result.ok:
        _raise_blender_error(
            "Blender scene export failed.",
            "SX1202",
            "blender_export_failed",
            "/exports/blender",
            "Blender failed while exporting the scene package.",
            details={
                "exit_code": result.exit_code,
                "timed_out": result.timed_out,
                "stderr_tail": result.stderr_tail,
                "stdout_log_path": _relative_or_none(package_root, result.stdout_log_path),
                "stderr_log_path": _relative_or_none(package_root, result.stderr_log_path),
            },
        )
    if not blend_path.exists() or not summary_path.exists():
        _raise_blender_error(
            "Blender scene export did not write expected artifacts.",
            "SX1203",
            "blender_export_artifacts_missing",
            "/exports/blender",
            "Blender reported success but the expected .blend or summary artifact is missing.",
            details={
                "blend_path": _relative_to(package_root, blend_path),
                "summary_path": _relative_to(package_root, summary_path),
            },
        )
    summary = _load_summary(summary_path)
    identity = _validate_blender_identity(summary, _object_ids(scene_graph))
    if identity["status"] != "passed":
        _raise_blender_error(
            "Blender scene export did not preserve required object IDs.",
            "SX1204",
            "blender_export_identity_failed",
            "/exports/blender/identity",
            "Blender export identity validation failed after export.",
            details={"identity": identity},
        )

    artifacts = [
        {
            "target": "blend",
            "format": "blend",
            "path": _relative_to(package_root, blend_path),
            "status": "built",
            "bytes": blend_path.stat().st_size,
            "object_count": len(_object_ids(scene_graph)),
            "identity": identity,
            "collections": _collection_summary(summary, scene_graph),
            "cameras": _named_summary(summary, "cameras", "camera_id", scene_graph.get("cameras", [])),
            "lights": _named_summary(summary, "lights", "light_id", scene_graph.get("lights", [])),
            "materials": _named_summary(summary, "materials", "material_id", scene_graph.get("materials", [])),
            "mode": mode,
        },
        {
            "target": "blend_summary",
            "format": "json",
            "path": _relative_to(package_root, summary_path),
            "status": "built",
            "object_count": len(_object_ids(scene_graph)),
            "mode": mode,
        },
    ]
    report = {
        "schema_version": SCENE_EXPORT_ARTIFACTS_VERSION,
        "scene_id": scene_id,
        "mode": mode,
        "exporter": BLENDER_EXPORTER_ID,
        "probe": _public_probe(probe),
        "sandbox": {
            "duration_s": result.duration_s,
            "stdout_log_path": _relative_or_none(package_root, result.stdout_log_path),
            "stderr_log_path": _relative_or_none(package_root, result.stderr_log_path),
        },
        "artifacts": artifacts,
        "diagnostics": [],
    }
    _write_json(report_path, report)
    report["report_path"] = _relative_to(package_root, report_path)
    return report


def _blender_metadata(scene_graph: Mapping[str, Any], *, exporter: str) -> dict[str, Any]:
    instancing_by_object_id = instancing_metadata_by_object_id(scene_graph)
    return {
        "schema_version": BLENDER_EXPORT_METADATA_VERSION,
        "scene_id": _scene_id(scene_graph),
        "exporter": exporter,
        "regions": [
            {
                "region_id": region_id,
                "name": _string_field(item, "name") or region_id,
            }
            for item in _mapping_items(scene_graph.get("regions", []))
            if (region_id := _string_field(item, "region_id")) is not None
        ],
        "objects": [
            {
                "object_id": object_id,
                "name": _string_field(item, "name") or object_id,
                "region_id": _string_field(item, "region") or "",
                "role": _string_field(item, "role") or "",
                "material_id": _primary_material_id(item) or "",
                "provenance": _object_provenance(item),
                "instancing": instancing_by_object_id.get(object_id, {}),
            }
            for item in _mapping_items(scene_graph.get("objects", []))
            if (object_id := _string_field(item, "object_id")) is not None
        ],
        "materials": [
            {
                "material_id": material_id,
                "name": _string_field(item, "name") or material_id,
            }
            for item in _mapping_items(scene_graph.get("materials", []))
            if (material_id := _string_field(item, "material_id")) is not None
        ],
        "cameras": [
            {
                "camera_id": camera_id,
                "target": _string_field(item, "target") or "",
                "framing": _string_field(item, "framing") or "",
            }
            for item in _mapping_items(scene_graph.get("cameras", []))
            if (camera_id := _string_field(item, "camera_id")) is not None
        ],
        "lights": [
            {
                "light_id": light_id,
                "target": _string_field(item, "target") or "",
                "type": _string_field(item, "type") or "",
            }
            for item in _mapping_items(scene_graph.get("lights", []))
            if (light_id := _string_field(item, "light_id")) is not None
        ],
    }


def _load_summary(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        _raise_blender_error(
            "Blender export summary could not be read.",
            "SX1205",
            "blender_export_summary_invalid",
            "/exports/blender/summary",
            f"Blender export summary is invalid: {exc}",
        )
    return raw if isinstance(raw, dict) else {}


def _validate_blender_identity(summary: Mapping[str, Any], object_ids: list[str]) -> dict[str, Any]:
    found: set[str] = set()
    object_names = {str(item).split(".", 1)[0] for item in summary.get("objects", []) if isinstance(item, str)}
    for object_id in object_ids:
        if object_id in object_names:
            found.add(object_id)
    custom_props = summary.get("custom_properties")
    objects = custom_props.get("objects", {}) if isinstance(custom_props, Mapping) else {}
    if isinstance(objects, Mapping):
        for value in objects.values():
            if isinstance(value, Mapping):
                object_id = value.get("lathe_object_id")
                if isinstance(object_id, str) and object_id in object_ids:
                    found.add(object_id)
    missing = sorted(set(object_ids) - found)
    return {
        "status": "passed" if not missing else "failed",
        "object_ids_expected": object_ids,
        "object_ids_found": sorted(found),
        "object_ids_missing": missing,
    }


def _collection_summary(summary: Mapping[str, Any], scene_graph: Mapping[str, Any]) -> dict[str, Any]:
    expected = [
        region_id
        for item in _mapping_items(scene_graph.get("regions", []))
        if (region_id := _string_field(item, "region_id")) is not None
    ]
    names = {str(item) for item in summary.get("collections", []) if isinstance(item, str)}
    custom_props = summary.get("custom_properties")
    collections = custom_props.get("collections", {}) if isinstance(custom_props, Mapping) else {}
    found = set(region_id for region_id in expected if region_id in names)
    if isinstance(collections, Mapping):
        for value in collections.values():
            if isinstance(value, Mapping):
                region_id = value.get("lathe_region_id")
                if isinstance(region_id, str) and region_id in expected:
                    found.add(region_id)
    return {"expected": expected, "found": sorted(found), "missing": sorted(set(expected) - found)}


def _named_summary(
    summary: Mapping[str, Any],
    summary_key: str,
    id_key: str,
    source_items: object,
) -> dict[str, Any]:
    expected = [
        item_id
        for item in _mapping_items(source_items)
        if (item_id := _string_field(item, id_key)) is not None
    ]
    names = {str(item).split(".", 1)[0] for item in summary.get(summary_key, []) if isinstance(item, str)}
    found = sorted(item_id for item_id in expected if item_id in names)
    return {"expected": expected, "found": found, "missing": sorted(set(expected) - set(found))}


def _public_probe(probe: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "available": bool(probe.get("available")),
        "version": probe.get("version"),
        "code": probe.get("code"),
        "supported_modes": probe.get("supported_modes", []),
    }


def _mapping_items(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _object_ids(scene_graph: Mapping[str, Any]) -> list[str]:
    return [
        object_id
        for item in _mapping_items(scene_graph.get("objects", []))
        if (object_id := _string_field(item, "object_id")) is not None
    ]


def _primary_material_id(item: Mapping[str, Any]) -> str | None:
    bindings = item.get("material_bindings")
    if not isinstance(bindings, list):
        return None
    for binding in bindings:
        if isinstance(binding, Mapping):
            material_id = _string_field(binding, "material")
            if material_id is not None:
                return material_id
    return None


def _object_provenance(item: Mapping[str, Any]) -> dict[str, Any]:
    provenance = item.get("provenance")
    if not isinstance(provenance, Mapping):
        return {}
    return {
        key: value
        for key, value in provenance.items()
        if key in {"source", "license", "commercial_use", "provider", "reference"}
        and isinstance(value, str | bool | int | float)
    }


def _safe_file(value: str, *, suffix: str) -> str:
    stem = _SAFE_FILE_RE.sub("_", value.lower()).strip("_") or "scene"
    return f"{stem[:80].rstrip('_')}{suffix}"


def _safe_package_path(package_dir: Path, relative_path: str) -> Path:
    try:
        return safe_resolve(package_dir, relative_path)
    except PathGuardError as exc:
        _raise_blender_error(
            "Scene Blender export package path is unsafe.",
            "SX1206",
            "unsafe_blender_export_path",
            f"/package/{relative_path}",
            f"Scene Blender export path {relative_path!r} is unsafe: {exc}",
            details={"path": relative_path, "package_dir": str(package_dir)},
        )


def _relative_to(root: Path, path: Path) -> str:
    return path.resolve(strict=False).relative_to(root.resolve(strict=False)).as_posix()


def _relative_or_none(root: Path, path: Path | None) -> str | None:
    return None if path is None else _relative_to(root, path)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    write_json_atomic(path, payload)


def _string_field(item: Mapping[str, Any], field: str) -> str | None:
    value = item.get(field)
    return value if isinstance(value, str) and value else None


def _scene_id(scene_graph: Mapping[str, Any]) -> str:
    return _string_field(scene_graph, "scene_id") or "scene"


def _raise_blender_error(
    message: str,
    code: str,
    name: str,
    path: str,
    diagnostic_message: str,
    *,
    details: Mapping[str, Any] | None = None,
) -> None:
    raise SceneArtifactError(
        message,
        diagnostics=[
            {
                "code": code,
                "name": name,
                "severity": "error",
                "contract": "scene_export",
                "phase": "scene_blender_export",
                "path": path,
                "message": diagnostic_message,
                **({"details": dict(details)} if details is not None else {}),
            }
        ],
    )


__all__ = [
    "BLENDER_EXPORTER_ID",
    "BLENDER_EXPORT_METADATA_VERSION",
    "export_scene_blend",
]
