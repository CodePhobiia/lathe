from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..bridge.blender_plan import build_bridge_plan
from ..capabilities import probe_blender
from ..inspection.evidence import build_inspection_policy_ir, build_validation_evidence_ir
from ..render_eval import evaluate_render_views
from .drivers import BACKEND_IDS, _export_blend_artifact
from .plan_adapter import (
    _canonical_backends,
    _dump_json,
    _hash_file,
    _planned_materials,
    _planned_node_groups,
    _resolve_bake_profile,
    _resolve_render_fixture,
    _unit_px,
)
from .render import _render_mesh_pass


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
    internal_backends = _canonical_backends(execution, BACKEND_IDS)
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
