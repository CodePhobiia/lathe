from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from .bridge.blender_plan import build_bridge_plan
from .capabilities import probe_blender
from .inspection.evidence import build_inspection_policy_ir, build_validation_evidence_ir
from .render_eval import evaluate_render_views


IMAGE_BG = (246, 247, 250, 255)
LINE_COLOR = (30, 36, 44, 255)
BACKEND_IDS = {
    "exec": "lathe.exec.blender_v1",
    "geometry_backend": {
        "blender_gnodes": "lathe.geometry.blender_gnodes_v1",
        "blender_modstack": "lathe.geometry.blender_modstack_v1",
    },
    "topology_backend": "lathe.topology.blender_mesh_v1",
    "uv_backend": {
        "blender_uv": "lathe.uv.blender_uv_v1",
    },
    "bake_backend": {
        "blender_cycles": "lathe.bake.blender_cycles_v1",
    },
    "surface_backend": {
        "blender_materials": "lathe.surface.blender_materials_v1",
    },
    "render_backend": {
        "blender_eval": "lathe.render.blender_eval_v1",
    },
    "package_backend": {
        "blender_export": "lathe.package.blender_export_v1",
    },
    "library_backend": {
        "blender_assets": "lathe.library.blender_assets_v1",
    },
}


def _dump_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False), encoding="utf-8")


def _hash_file(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _unit_px(value: Any, default: int) -> int:
    if isinstance(value, dict) and value.get("type") == "unit" and value.get("unit") == "px":
        return int(value.get("value", default))
    if isinstance(value, (int, float)):
        return int(value)
    return default


def _canonical_backends(execution: dict[str, Any]) -> dict[str, Any]:
    return {
        "geometry_backend": BACKEND_IDS["geometry_backend"].get(str(execution.get("geometry_backend", "")), ""),
        "topology_backend": BACKEND_IDS["topology_backend"],
        "uv_backend": BACKEND_IDS["uv_backend"].get(str(execution.get("uv_backend", "")), ""),
        "bake_backend": BACKEND_IDS["bake_backend"].get(str(execution.get("bake_backend", "")), ""),
        "surface_backend": BACKEND_IDS["surface_backend"].get(str(execution.get("surface_backend", "")), ""),
        "render_backend": BACKEND_IDS["render_backend"].get(str(execution.get("render_backend", "")), ""),
        "package_backend": BACKEND_IDS["package_backend"].get(str(execution.get("package_backend", "")), ""),
        "library_backend": BACKEND_IDS["library_backend"].get(str(execution.get("library_backend", "")), ""),
    }


def _resolve_render_fixture(asset: dict[str, Any]) -> dict[str, Any]:
    fixture = dict(asset.get("build", {}).get("surface", {}).get("resolved_render_fixture", {}).get("values", {}))
    if not fixture:
        fixture = {
            "views": ["front_34", "front", "side", "rear_34"],
            "shading": "studio_neutral",
            "passes": ["beauty", "normal", "depth"],
            "resolution": {"type": "unit", "value": 1024, "unit": "px"},
        }
    return fixture


def _resolve_bake_profile(asset: dict[str, Any]) -> dict[str, Any]:
    profile = dict(asset.get("build", {}).get("surface", {}).get("resolved_bake_profile", {}).get("values", {}))
    if not profile:
        profile = {
            "maps": list(asset.get("build", {}).get("surface", {}).get("bakes", [])),
            "target_resolution": asset.get("build", {}).get("surface", {}).get("resolution"),
            "normal_space": "tangent",
            "require_highlow": True,
        }
    return profile


def _render_rotation(view: str) -> np.ndarray:
    if view == "front":
        return _rotation_matrix(0.0, 0.0)
    if view == "front_34":
        return _rotation_matrix(np.radians(12.0), np.radians(35.0))
    if view == "side":
        return _rotation_matrix(0.0, np.pi / 2.0)
    if view == "rear":
        return _rotation_matrix(0.0, np.pi)
    if view == "rear_34":
        return _rotation_matrix(np.radians(12.0), np.radians(145.0))
    return _rotation_matrix(np.radians(35.264), np.radians(45.0))


def _rotation_matrix(x_angle: float, y_angle: float) -> np.ndarray:
    rx = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, np.cos(x_angle), -np.sin(x_angle)],
            [0.0, np.sin(x_angle), np.cos(x_angle)],
        ],
        dtype=np.float64,
    )
    ry = np.array(
        [
            [np.cos(y_angle), 0.0, np.sin(y_angle)],
            [0.0, 1.0, 0.0],
            [-np.sin(y_angle), 0.0, np.cos(y_angle)],
        ],
        dtype=np.float64,
    )
    return rx @ ry


def _project_mesh(runtime_mesh: Any, view: str, size: int) -> tuple[np.ndarray, np.ndarray, list[tuple[float, list[tuple[float, float]], int, tuple[int, int, int]]]]:
    mesh = runtime_mesh.mesh
    rotation = _render_rotation(view)
    projected = np.asarray(mesh.vertices, dtype=np.float64) @ rotation.T
    xy = projected[:, :2]
    depth = projected[:, 2]
    bounds_min = xy.min(axis=0)
    bounds_max = xy.max(axis=0)
    span = np.maximum(bounds_max - bounds_min, 1e-6)
    scale = min((size - 80) / span[0], (size - 80) / span[1])
    screen = (xy - bounds_min) * scale + np.array([40.0, 40.0])
    screen[:, 1] = size - screen[:, 1]
    light = np.array([0.45, 0.78, 0.44], dtype=np.float64)
    light /= np.linalg.norm(light)
    face_parts = list(getattr(runtime_mesh, "face_parts", []))
    colors = dict(getattr(runtime_mesh, "part_colors", {}))
    triangles = []
    for face_index, face in enumerate(mesh.faces):
        pts = [tuple(screen[idx]) for idx in face]
        part = face_parts[min(face_index, len(face_parts) - 1)] if face_parts else "mesh"
        base = colors.get(part, (146, 162, 188))
        brightness = np.clip(np.dot(mesh.face_normals[face_index], light) * 0.5 + 0.5, 0.0, 1.0)
        depth_value = int(np.clip((depth[list(face)].mean() - depth.min()) / max(1e-6, depth.max() - depth.min()) * 255.0, 0.0, 255.0))
        triangles.append((float(depth[list(face)].mean()), pts, depth_value, base, float(brightness)))
    triangles.sort(key=lambda item: item[0])
    return screen, depth, triangles


def _render_mesh_pass(runtime_mesh: Any, path: Path, view: str, mode: str, size: int) -> None:
    _, _, triangles = _project_mesh(runtime_mesh, view, size)
    if mode in {"beauty", "normal"}:
        image = Image.new("RGBA", (size, size), IMAGE_BG)
        draw = ImageDraw.Draw(image, "RGBA")
    else:
        image = Image.new("L", (size, size), 0)
        draw = ImageDraw.Draw(image, "L")

    for _, pts, depth_value, base, brightness in triangles:
        if mode == "beauty":
            fill = tuple(int(np.clip(channel * (0.72 + brightness * 0.34), 0, 255)) for channel in base) + (255,)
            draw.polygon(pts, fill=fill, outline=LINE_COLOR)
        elif mode == "normal":
            fill = (int(128 + (base[0] - 128) * 0.35), int(128 + (base[1] - 128) * 0.35), 255, 255)
            draw.polygon(pts, fill=fill, outline=LINE_COLOR)
        else:
            draw.polygon(pts, fill=depth_value)

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _planned_node_groups(asset: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for component in asset.get("assembly", {}).get("components", []):
        names.append(f"gn_{component}")
    for mechanism in asset.get("assembly", {}).get("mechanisms", []):
        names.append(f"gn_{mechanism}")
    for pattern in asset.get("surface", {}).get("patterns", []):
        names.append(f"mat_{pattern}")
    return names


def _planned_materials(asset: dict[str, Any]) -> list[str]:
    materials = list(asset.get("surface", {}).get("materials", []))
    material_graph = asset.get("surface", {}).get("material_graph", "")
    if material_graph:
        materials.append(material_graph)
    return sorted(dict.fromkeys(materials))


def _export_blend_artifact(blender: dict[str, Any], input_glb: Path, output_blend: Path, summary_path: Path) -> dict[str, Any]:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "blender_export_blend.py"
    proc = subprocess.run(
        [
            blender["path"],
            "--background",
            "--factory-startup",
            "--python",
            str(script_path),
            "--",
            "--input",
            str(input_glb),
            "--output",
            str(output_blend),
            "--summary",
            str(summary_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )
    return {
        "ok": proc.returncode == 0 and output_blend.exists(),
        "stdout_tail": (proc.stdout or "").strip()[-800:] or None,
        "stderr_tail": (proc.stderr or "").strip()[-800:] or None,
        "returncode": proc.returncode,
    }


def build_execution_bundle(
    *,
    asset: dict[str, Any],
    stage_dir: Path,
    runtime: dict[str, Any],
    runtime_config: dict[str, Any] | None,
    out_dir: Path,
) -> dict[str, Any]:
    execution = dict(asset.get("execution", {}))
    requested = bool(execution.get("profile") or execution.get("engine"))
    resolved_profile = dict(execution.get("resolved_execution_profile", {}))
    engine = str(execution.get("engine", "") or "")
    mode = str(execution.get("mode", "") or "")
    if not requested or engine != "blender":
        bundle = {
            "schema": "lathe.blender_execution_bundle.v1",
            "requested": False,
            "requested_engine": engine,
            "requested_profile": execution.get("profile", ""),
            "status": "not_requested",
            "backend_id": "",
            "execution_ir": {},
            "blender_execution_ir": {},
            "bake_plan_ir": {},
            "render_eval_ir": {},
            "blend_artifact_ir": {},
            "library_asset_ir": {},
            "bridge_plan_ir": {},
            "inspection_policy_ir": {},
            "validation_evidence_ir": {},
            "diagnostics": [],
        }
        _dump_json(stage_dir / "bundle.json", bundle)
        return bundle

    blender = probe_blender(runtime_config)
    internal_backends = _canonical_backends(execution)
    bridge_plan_ir = build_bridge_plan(asset, runtime_config)
    inspection_policy_ir = build_inspection_policy_ir(asset)
    bake_profile = _resolve_bake_profile(asset)
    render_fixture = _resolve_render_fixture(asset)
    surface_bundle = runtime.get("surface", {}).get("bundle", {})
    render_report = evaluate_render_views(runtime.get("optimize") or runtime["topology"], views=list(render_fixture.get("views", [])))
    execution_ir = {
        "schema": "lathe.execution_ir.v1",
        "profile": execution.get("profile", ""),
        "resolved_execution_profile": resolved_profile.get("name", ""),
        "engine": engine,
        "mode": mode,
        "deterministic": execution.get("deterministic"),
        "preserve_blend": execution.get("preserve_blend", ""),
    }
    blender_execution_ir = {
        "schema": "lathe.blender_execution_ir.v1",
        "pinned_blender_version_intent": resolved_profile.get("values", {}).get("blender_version", blender.get("version")),
        "execution_mode": mode,
        "selected_backend_ids": internal_backends,
        "node_group_generation_plan": _planned_node_groups(asset),
        "material_graph_generation_plan": {
            "material_graph": asset.get("surface", {}).get("material_graph", ""),
            "resolved_material_graph": asset.get("surface", {}).get("resolved_material_graph", {}).get("name", ""),
            "surface_program": asset.get("surface", {}).get("program", ""),
        },
        "asset_library_references": [
            {
                "name": binding.get("name"),
                "catalog": binding.get("values", {}).get("catalog", ""),
                "target": binding.get("values", {}).get("target", ""),
            }
            for binding in execution.get("resolved_library_bindings", [])
        ],
        "bake_plan": {
            "maps": list(bake_profile.get("maps", [])),
            "target_resolution": bake_profile.get("target_resolution"),
            "require_highlow": bake_profile.get("require_highlow"),
        },
        "render_eval_plan": {
            "views": list(render_fixture.get("views", [])),
            "passes": list(render_fixture.get("passes", [])),
            "resolution": render_fixture.get("resolution"),
            "shading": render_fixture.get("shading", ""),
        },
        "export_plan": {
            "formats": list(asset.get("package", {}).get("formats", [])),
            "preserve_blend": execution.get("preserve_blend", ""),
        },
        "safety_policy": {
            "allow_autoexec": bool(((runtime_config or {}).get("execution", {}).get("blender", {}) or {}).get("allow_autoexec", False)),
            "trusted": bool(((runtime_config or {}).get("execution", {}).get("blender", {}) or {}).get("trusted", False)),
        },
    }
    bake_plan_ir = {
        "schema": "lathe.bake_plan_ir.v1",
        "profile": asset.get("build", {}).get("surface", {}).get("bake_profile", ""),
        "resolved_bake_profile": asset.get("build", {}).get("surface", {}).get("resolved_bake_profile", {}).get("name", ""),
        "maps": list(bake_profile.get("maps", [])),
        "target_resolution": bake_profile.get("target_resolution"),
        "normal_space": bake_profile.get("normal_space", "tangent"),
        "require_highlow": bool(bake_profile.get("require_highlow", True)),
        "highlow_relation": surface_bundle.get("highlow_relation", {}),
    }
    evidence_dir = stage_dir / "render_evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    render_resolution = _unit_px(render_fixture.get("resolution"), 1024)
    runtime_mesh = (runtime.get("optimize") or runtime["topology"]).get("runtime_mesh")
    evidence_passes: list[dict[str, Any]] = []
    if runtime_mesh is not None:
        for view in render_fixture.get("views", []):
            for render_pass in render_fixture.get("passes", []):
                pass_path = evidence_dir / f"{view}_{render_pass}.png"
                _render_mesh_pass(runtime_mesh, pass_path, str(view), str(render_pass), render_resolution)
                evidence_passes.append(
                    {
                        "view": view,
                        "pass": render_pass,
                        "uri": str(pass_path.relative_to(out_dir)),
                        "sha256": _hash_file(pass_path),
                    }
                )
    render_eval_ir = {
        "schema": "lathe.render_eval_ir.v1",
        "fixture": asset.get("build", {}).get("surface", {}).get("render_fixture", ""),
        "resolved_render_fixture": asset.get("build", {}).get("surface", {}).get("resolved_render_fixture", {}).get("name", ""),
        "views": list(render_fixture.get("views", [])),
        "passes": list(render_fixture.get("passes", [])),
        "resolution": render_fixture.get("resolution"),
        "evidence_passes": evidence_passes,
        "metrics": render_report.get("metrics", {}),
        "view_metrics": render_report.get("views", {}),
        "backend_id": internal_backends.get("render_backend"),
        "actual_adapter": "reference_render_proxy",
    }

    library_asset_ir = {
        "schema": "lathe.library_asset_ir.v1",
        "bindings": [
            {
                "name": binding.get("name"),
                "target": binding.get("values", {}).get("target", ""),
                "catalog": binding.get("values", {}).get("catalog", ""),
                "maps": dict(binding.get("values", {}).get("maps", {})),
            }
            for binding in execution.get("resolved_library_bindings", [])
        ],
    }

    blend_path: Path | None = None
    blend_summary: dict[str, Any] = {
        "objects": [],
        "collections": [],
        "materials": _planned_materials(asset),
        "node_groups": _planned_node_groups(asset),
        "linked_libraries": [item["catalog"] for item in library_asset_ir["bindings"] if item.get("catalog")],
        "overrides": [],
    }
    artifact_status = "planned_only"
    diagnostics: list[dict[str, Any]] = []
    if blender.get("available") and runtime_mesh is not None:
        input_glb = stage_dir / "blend_input.glb"
        runtime_mesh.mesh.export(input_glb)
        blend_path = stage_dir / f"{asset['name']}.blend"
        summary_path = stage_dir / "blend_summary.json"
        export_result = _export_blend_artifact(blender, input_glb, blend_path, summary_path)
        if export_result["ok"]:
            artifact_status = "generated"
            if summary_path.exists():
                blend_summary = json.loads(summary_path.read_text(encoding="utf-8"))
        else:
            artifact_status = "generation_failed"
            diagnostics.append(
                {
                    "code": "L7201",
                    "name": "blend_artifact_generation_failed",
                    "severity": "warning",
                    "phase": "build",
                    "asset": asset["name"],
                    "stage": "execution",
                    "path": "execution.blend",
                    "message": "Blender was available but the .blend artifact could not be generated",
                    "details": export_result,
                    "suggested_repairs": [],
                }
            )
    else:
        reason = blender.get("message", "Blender unavailable") if not blender.get("available") else "No runtime mesh available"
        diagnostics.append(
            {
                "code": "L7202",
                "name": "blender_not_found" if not blender.get("available") else "blend_artifact_generation_skipped",
                "severity": "warning",
                "phase": "build",
                "asset": asset["name"],
                "stage": "execution",
                "path": "execution.profile",
                "message": reason,
                "details": {"probe": blender},
                "suggested_repairs": [],
            }
        )

    blend_artifact_ir = {
        "schema": "lathe.blend_artifact_ir.v1",
        "generated": bool(blend_path and blend_path.exists()),
        "status": artifact_status,
        "artifact_path": str(blend_path.relative_to(out_dir)) if blend_path and blend_path.exists() else "",
        "artifact_hash": _hash_file(blend_path),
        "asset_collections": list(blend_summary.get("collections", [])),
        "node_groups_generated": list(blend_summary.get("node_groups", [])),
        "materials_generated": list(blend_summary.get("materials", [])),
        "linked_libraries_used": list(blend_summary.get("linked_libraries", [])),
        "overrides_created": list(blend_summary.get("overrides", [])),
        "objects": list(blend_summary.get("objects", [])),
    }
    validation_evidence_ir = build_validation_evidence_ir(
        asset=asset,
        runtime=runtime,
        execution_bundle={
            "bake_plan_ir": bake_plan_ir,
            "render_eval_ir": render_eval_ir,
            "blend_artifact_ir": blend_artifact_ir,
        },
    )
    for missing_evidence in validation_evidence_ir.get("missing_required_evidence", []):
        diagnostics.append(
            {
                "code": "L7301",
                "name": f"{missing_evidence}_missing",
                "severity": "error",
                "phase": "validate",
                "asset": asset["name"],
                "stage": "execution",
                "path": "execution.inspection_policy",
                "message": f"Inspection policy requires missing evidence class '{missing_evidence}'",
                "details": {"validation_evidence_ir": validation_evidence_ir},
                "suggested_repairs": ["rerender_eval_fixture", "rebake_cycles"],
            }
        )

    bundle = {
        "schema": "lathe.blender_execution_bundle.v1",
        "requested": True,
        "requested_engine": engine,
        "requested_profile": execution.get("profile", ""),
        "status": artifact_status if blender.get("available") else "planned_only",
        "backend_id": BACKEND_IDS["exec"],
        "probe": blender,
        "execution_ir": execution_ir,
        "blender_execution_ir": blender_execution_ir,
        "bake_plan_ir": bake_plan_ir,
        "render_eval_ir": render_eval_ir,
        "blend_artifact_ir": blend_artifact_ir,
        "library_asset_ir": library_asset_ir,
        "bridge_plan_ir": bridge_plan_ir,
        "inspection_policy_ir": inspection_policy_ir,
        "validation_evidence_ir": validation_evidence_ir,
        "diagnostics": diagnostics,
    }
    _dump_json(stage_dir / "execution_ir.json", execution_ir)
    _dump_json(stage_dir / "blender_execution_ir.json", blender_execution_ir)
    _dump_json(stage_dir / "bake_plan_ir.json", bake_plan_ir)
    _dump_json(stage_dir / "render_eval_ir.json", render_eval_ir)
    _dump_json(stage_dir / "blend_artifact_ir.json", blend_artifact_ir)
    _dump_json(stage_dir / "library_asset_ir.json", library_asset_ir)
    _dump_json(stage_dir / "bridge_plan_ir.json", bridge_plan_ir)
    _dump_json(stage_dir / "inspection_policy_ir.json", inspection_policy_ir)
    _dump_json(stage_dir / "validation_evidence_ir.json", validation_evidence_ir)
    _dump_json(stage_dir / "bundle.json", bundle)
    return bundle


def inspect_blend_artifact(build_dir: Path) -> dict[str, Any]:
    stage_dir = build_dir / "stages" / "execution"
    bundle = json.loads((stage_dir / "bundle.json").read_text(encoding="utf-8"))
    return {
        "asset": bundle.get("requested_profile") or build_dir.name,
        "backend_id": bundle.get("backend_id"),
        "probe": bundle.get("probe", {}),
        "blend_artifact_ir": bundle.get("blend_artifact_ir", {}),
        "render_eval_ir": bundle.get("render_eval_ir", {}),
        "library_asset_ir": bundle.get("library_asset_ir", {}),
        "bridge_plan_ir": bundle.get("bridge_plan_ir", {}),
        "inspection_policy_ir": bundle.get("inspection_policy_ir", {}),
        "validation_evidence_ir": bundle.get("validation_evidence_ir", {}),
    }


def export_blend_artifact(build_dir: Path, destination: Path | None = None) -> dict[str, Any]:
    inspect = inspect_blend_artifact(build_dir)
    artifact_path = inspect.get("blend_artifact_ir", {}).get("artifact_path")
    if not artifact_path:
        raise FileNotFoundError("No retained .blend artifact is recorded for this build")
    source = build_dir / artifact_path
    if destination is not None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    return {
        "artifact_path": str(source),
        "artifact_hash": inspect.get("blend_artifact_ir", {}).get("artifact_hash"),
        "exported_to": str(destination) if destination is not None else str(source),
    }


def build_library_sync_manifest(program: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    bindings = []
    for binding in program.get("library_bindings", []):
        values = binding.get("values", {})
        bindings.append(
            {
                "name": binding.get("name"),
                "target": values.get("target", ""),
                "catalog": values.get("catalog", ""),
                "maps": dict(values.get("maps", {})),
            }
        )
    manifest = {
        "schema": "lathe.library_sync_manifest.v1",
        "binding_count": len(bindings),
        "bindings": bindings,
    }
    _dump_json(out_dir / "library_sync_manifest.json", manifest)
    return manifest
