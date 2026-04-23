from __future__ import annotations

from typing import Any


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _reference_strength(runtime: dict[str, Any]) -> float:
    return float(runtime.get("shape", {}).get("bundle", {}).get("conditioning_report", {}).get("reference_strength", 0.0) or 0.0)


def _policy_present(asset: dict[str, Any], block: str, resolved_key: str) -> bool:
    resolved = asset.get(block, {}).get(resolved_key, {})
    return bool(resolved and resolved.get("name"))


def _adapt_metrics(asset: dict[str, Any], runtime: dict[str, Any]) -> dict[str, float]:
    semantic = runtime.get("semantic_quality", {}).get("metrics", {})
    visual = runtime.get("visual_quality", {}).get("metrics", {})
    transfer = asset.get("transfer", {})
    adapt_policy = transfer.get("resolved_adapt_policy", {})
    preserve = list(adapt_policy.get("values", {}).get("preserve", []) or adapt_policy.get("preserve", []) or [])
    transfer_rules = list(transfer.get("resolved_transfer_rules", []))
    optimize = asset.get("build", {}).get("optimize", {})

    semantic_preservation = _clamp01(
        0.34 * float(semantic.get("part_coverage", 0.0))
        + 0.24 * float(semantic.get("interface_score", 0.0))
        + 0.18 * float(semantic.get("silhouette_fidelity", 0.0))
        + 0.14 * min(1.0, len(preserve) / 4.0)
        + 0.10 * (1.0 if _policy_present(asset, "transfer", "resolved_adapt_policy") else 0.0)
    )
    profile_retarget = _clamp01(
        0.30
        + 0.18 * (1.0 if optimize.get("lods") else 0.0)
        + 0.18 * (1.0 if optimize.get("draw_calls") else 0.0)
        + 0.18 * (1.0 if optimize.get("texture_budget") else 0.0)
        + 0.16 * float(visual.get("surface_authoring_quality", 0.0))
    )
    transfer_integrity = _clamp01(
        0.32 * (1.0 if _policy_present(asset, "transfer", "resolved_adapt_policy") else 0.0)
        + 0.24 * min(1.0, len(transfer_rules) / 2.0)
        + 0.22 * float(semantic.get("part_coverage", 0.0))
        + 0.22 * float(visual.get("surface_material_zone_coherence", 0.0))
    )
    return {
        "semantic_preservation_quality": round(semantic_preservation, 6),
        "profile_retarget_quality": round(profile_retarget, 6),
        "transfer_integrity": round(transfer_integrity, 6),
    }


def _assembly_metrics(asset: dict[str, Any], runtime: dict[str, Any]) -> dict[str, float]:
    semantic = runtime.get("semantic_quality", {}).get("metrics", {})
    visual = runtime.get("visual_quality", {}).get("metrics", {})
    assembly = asset.get("assembly", {})
    constraints = asset.get("constraints", {})
    kit = assembly.get("resolved_kit", {})
    policy = constraints.get("resolved_assembly_policy", {})
    kit_values = kit.get("values", {})
    policy_values = policy.get("values", {})
    modules = list(kit_values.get("modules", []) or assembly.get("components", []) or [])
    allowed_joins = list(policy_values.get("allow", []) or kit_values.get("allowed_joins", []) or [])
    has_clearance = bool(policy_values.get("clearance") or kit_values.get("clearance"))

    join_legality = _clamp01(
        0.28 * (1.0 if kit else 0.0)
        + 0.24 * (1.0 if policy else 0.0)
        + 0.18 * min(1.0, len(allowed_joins) / 3.0)
        + 0.30 * float(semantic.get("adjacency_score", 0.0))
    )
    clearance = _clamp01(
        0.36 * (1.0 if has_clearance else 0.0)
        + 0.24 * (1.0 if policy_values.get("snap_grid") or kit_values.get("snap_grid") else 0.0)
        + 0.24 * float(semantic.get("interface_score", 0.0))
        + 0.16 * float(visual.get("support_plausibility", 0.0))
    )
    module_coherence = _clamp01(
        0.28 * min(1.0, len(modules) / max(1, len(asset.get("intent", {}).get("parts", []))))
        + 0.34 * float(semantic.get("part_coverage", 0.0))
        + 0.22 * float(semantic.get("structural_richness", 0.0))
        + 0.16 * float(visual.get("attachment_integration_quality", 0.0))
    )
    surface_continuity = _clamp01(
        0.42 * float(visual.get("surface_material_zone_coherence", 0.0))
        + 0.30 * float(visual.get("seam_quality", 0.0))
        + 0.28 * float(visual.get("surface_authoring_quality", 0.0))
    )
    return {
        "join_legality": round(join_legality, 6),
        "assembly_clearance_quality": round(clearance, 6),
        "module_coherence": round(module_coherence, 6),
        "assembly_surface_continuity": round(surface_continuity, 6),
    }


def _reconstruct_metrics(asset: dict[str, Any], runtime: dict[str, Any]) -> dict[str, float]:
    semantic = runtime.get("semantic_quality", {}).get("metrics", {})
    refs = asset.get("refs", {})
    fit = asset.get("fit", {})
    reference_sets = list(refs.get("resolved_reference_sets", []))
    conditioning = runtime.get("shape", {}).get("bundle", {}).get("conditioning_report", {})
    image_count = len(conditioning.get("image_refs", []))
    mesh_count = len(conditioning.get("mesh_refs", []))
    policy_score = 1.0 if _policy_present(asset, "fit", "resolved_reconstruct_policy") else 0.55
    fit_score = 1.0 if _policy_present(asset, "fit", "resolved_fit_profile") else 0.55
    evidence_score = _clamp01(0.45 * _reference_strength(runtime) + 0.20 * min(1.0, image_count / 2.0) + 0.20 * min(1.0, mesh_count) + 0.15 * min(1.0, len(reference_sets)))

    family_fit = _clamp01(0.32 * evidence_score + 0.24 * fit_score + 0.24 * policy_score + 0.20 * float(semantic.get("silhouette_fidelity", 0.0)))
    component_fit = _clamp01(0.46 * float(semantic.get("part_coverage", 0.0)) + 0.28 * float(semantic.get("adjacency_score", 0.0)) + 0.26 * fit_score)
    measurement = _clamp01(0.34 * evidence_score + 0.28 * float(semantic.get("symmetry_score", 0.0)) + 0.20 * (1.0 if refs.get("images") or refs.get("meshes") else 0.0) + 0.18 * fit_score)
    honesty = _clamp01(0.24 * family_fit + 0.24 * component_fit + 0.20 * measurement + 0.20 * policy_score + 0.12 * (1.0 if asset.get("validate", {}).get("threshold") else 0.0))
    return {
        "family_fit_confidence": round(family_fit, 6),
        "component_fit_confidence": round(component_fit, 6),
        "measurement_consistency": round(measurement, 6),
        "reconstruct_honesty_score": round(honesty, 6),
    }


def evaluate_flow_quality(asset: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
    mode = str(asset.get("build", {}).get("shape", {}).get("mode", "generate"))
    if mode == "adapt":
        metrics = _adapt_metrics(asset, runtime)
        minimums = {
            "semantic_preservation_quality": 0.58,
            "profile_retarget_quality": 0.55,
            "transfer_integrity": 0.50,
        }
    elif mode == "assemble":
        metrics = _assembly_metrics(asset, runtime)
        minimums = {
            "join_legality": 0.55,
            "assembly_clearance_quality": 0.50,
            "module_coherence": 0.55,
            "assembly_surface_continuity": 0.20,
        }
    elif mode == "reconstruct":
        metrics = _reconstruct_metrics(asset, runtime)
        minimums = {
            "family_fit_confidence": 0.48,
            "component_fit_confidence": 0.52,
            "measurement_consistency": 0.45,
            "reconstruct_honesty_score": 0.50,
        }
    else:
        return {"mode": mode, "metrics": {}, "thresholds": {}, "diagnostics": []}

    diagnostics = []
    for metric, minimum in minimums.items():
        if metrics.get(metric, 0.0) < minimum:
            diagnostics.append(
                {
                    "code": f"L65{len(diagnostics) + 1:02d}",
                    "name": f"flow_{metric}_failed",
                    "severity": "error",
                    "phase": "validate",
                    "asset": asset["name"],
                    "stage": "validate",
                    "path": f"validate.flow.{metric}",
                    "message": f"V1.1 flow validator failed for {metric}: {metrics.get(metric, 0.0):.3f} < {minimum:.3f}",
                    "details": {"mode": mode, "metric": metric, "actual": metrics.get(metric, 0.0), "minimum": minimum},
                    "suggested_repairs": _flow_repairs(mode, metric),
                }
            )
    return {"mode": mode, "metrics": metrics, "thresholds": minimums, "diagnostics": diagnostics}


def _flow_repairs(mode: str, metric: str) -> list[str]:
    if mode == "adapt":
        return ["restore_preserved_semantics", "repair_profile_retarget", "rebuild_surface_transfer"]
    if mode == "assemble":
        return ["resolve_mount_conflict", "increase_clearance", "repair_join_continuity", "repack_module_layout"]
    if mode == "reconstruct":
        return ["regularize_symmetry", "refit_family_parameters", "rebuild_from_component_library"]
    return [metric]
