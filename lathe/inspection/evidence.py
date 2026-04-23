from __future__ import annotations

from typing import Any


EVIDENCE_CLASSES = [
    "geometry_evidence",
    "topology_evidence",
    "uv_evidence",
    "bake_evidence",
    "surface_evidence",
    "package_export_evidence",
]


def _as_list(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return list(value)
    return [value]


def _policy_values(asset: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    execution = asset.get("execution", {})
    policy = execution.get("resolved_inspection_policy", {})
    values = policy.get("values", {}) if isinstance(policy, dict) else {}
    return execution.get("inspection_policy", ""), values


def build_inspection_policy_ir(asset: dict[str, Any]) -> dict[str, Any]:
    policy_name, values = _policy_values(asset)
    required = _as_list(values.get("require", values.get("required_evidence", values.get("evidence"))))
    render_fixtures = _as_list(values.get("render_fixtures", values.get("render_fixture")))
    bake_profiles = _as_list(values.get("bake_profiles", values.get("bake_profile")))
    if not render_fixtures:
        render_fixture = asset.get("build", {}).get("surface", {}).get("render_fixture", "")
        render_fixtures = _as_list(render_fixture)
    if not bake_profiles:
        bake_profile = asset.get("build", {}).get("surface", {}).get("bake_profile", "")
        bake_profiles = _as_list(bake_profile)
    return {
        "schema": "lathe.inspection_policy_ir.v1",
        "policy": policy_name,
        "resolved_policy": asset.get("execution", {}).get("resolved_inspection_policy", {}).get("name", ""),
        "required_evidence": [item for item in required if item in EVIDENCE_CLASSES],
        "unknown_evidence": [item for item in required if item not in EVIDENCE_CLASSES],
        "render_fixtures": render_fixtures,
        "bake_profiles": bake_profiles,
        "patch_source_allowed": bool(values.get("patch_source_allowed", False)),
        "unsafe_blender_python_allowed": bool(values.get("unsafe_blender_python_allowed", False)),
        "recovery_branches": _as_list(values.get("recovery_branches"))
        or ["reselect_candidate", "repair_candidate", "regenerate_candidate", "patch_source"],
    }


def _stage_available(runtime: dict[str, Any], stage: str) -> bool:
    return bool(runtime.get(stage, {}).get("bundle"))


def build_validation_evidence_ir(
    *,
    asset: dict[str, Any],
    runtime: dict[str, Any],
    execution_bundle: dict[str, Any],
) -> dict[str, Any]:
    policy_ir = build_inspection_policy_ir(asset)
    surface_bundle = runtime.get("surface", {}).get("bundle", {})
    bake_plan = execution_bundle.get("bake_plan_ir", {})
    render_eval = execution_bundle.get("render_eval_ir", {})
    blend_artifact = execution_bundle.get("blend_artifact_ir", {})
    evidence = {
        "geometry_evidence": {
            "available": _stage_available(runtime, "shape") or _stage_available(runtime, "topology"),
            "sources": ["stages/shape/bundle.json", "stages/topology/bundle.json"],
        },
        "topology_evidence": {
            "available": _stage_available(runtime, "topology"),
            "sources": ["stages/topology/bundle.json"],
        },
        "uv_evidence": {
            "available": _stage_available(runtime, "uv"),
            "sources": ["stages/uv/bundle.json"],
        },
        "bake_evidence": {
            "available": bool(bake_plan.get("maps") or surface_bundle.get("surface_control_pack", {}).get("bake_maps")),
            "sources": ["stages/execution/bake_plan_ir.json", "stages/surface/bundle.json"],
        },
        "surface_evidence": {
            "available": bool(surface_bundle.get("surface_validation_ir") or surface_bundle.get("surface_backend_report")),
            "sources": ["stages/surface/bundle.json"],
        },
        "package_export_evidence": {
            "available": False,
            "sources": ["stages/package/package_manifest.json"],
        },
    }
    render_passes = render_eval.get("evidence_passes", [])
    if render_passes:
        evidence["geometry_evidence"]["render_pass_count"] = len(render_passes)
        evidence["surface_evidence"]["render_pass_count"] = len(render_passes)
    if blend_artifact.get("generated"):
        evidence["geometry_evidence"]["blend_artifact"] = blend_artifact.get("artifact_path", "")

    missing = [item for item in policy_ir["required_evidence"] if not evidence.get(item, {}).get("available")]
    return {
        "schema": "lathe.validation_evidence_ir.v1",
        "inspection_policy": policy_ir["policy"],
        "required_evidence": policy_ir["required_evidence"],
        "evidence": evidence,
        "missing_required_evidence": missing,
        "satisfied": not missing,
    }
