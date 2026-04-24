"""Semantic-quality validator.

Scores ``semantic_preservation_quality`` against the resolved intent
and the authoritative mesh.
"""

from __future__ import annotations

import math
from typing import Any

from ..repair_planner import suggest_repairs_for_metric
from .silhouette import compare_scaffold_signature


def _symmetry_score(asset: dict[str, Any], runtime: dict[str, Any]) -> float:
    groups = {group["name"]: group for group in runtime["topology"]["bundle"].get("part_groups", [])}
    pairs: list[tuple[str, str]] = []
    part_names = [str(item) for item in asset.get("intent", {}).get("parts", [])]
    for name in part_names:
        if "_l" in name:
            mate = name.replace("_l", "_r")
            if mate in part_names:
                pairs.append((name, mate))
        if "_fl" in name:
            mate = name.replace("_fl", "_fr")
            if mate in part_names:
                pairs.append((name, mate))
        if "_rl" in name:
            mate = name.replace("_rl", "_rr")
            if mate in part_names:
                pairs.append((name, mate))
    if not pairs:
        return 1.0
    deviations = []
    for left, right in pairs:
        if left not in groups or right not in groups:
            deviations.append(1.0)
            continue
        lbox = groups[left]
        rbox = groups[right]
        lx = (lbox["bounds_min"][0] + lbox["bounds_max"][0]) / 2.0
        rx = (rbox["bounds_min"][0] + rbox["bounds_max"][0]) / 2.0
        ly = (lbox["bounds_min"][1] + lbox["bounds_max"][1]) / 2.0
        ry = (rbox["bounds_min"][1] + rbox["bounds_max"][1]) / 2.0
        lz = (lbox["bounds_min"][2] + lbox["bounds_max"][2]) / 2.0
        rz = (rbox["bounds_min"][2] + rbox["bounds_max"][2]) / 2.0
        x_delta = max(0.0, abs(lx + rx) - 1.0)
        y_delta = max(0.0, abs(ly - ry) - 0.5)
        z_delta = max(0.0, abs(lz - rz) - 1.0)
        x_score = 1.0 - min(1.0, x_delta / max(1.0, abs(lx) + abs(rx)))
        y_score = 1.0 - min(1.0, y_delta / max(1.0, abs(ly) + abs(ry) + 1e-6))
        z_score = 1.0 - min(1.0, z_delta / max(1.0, abs(lz) + abs(rz) + 1e-6))
        deviations.append(max(0.0, min(1.0, 0.5 * x_score + 0.2 * y_score + 0.3 * z_score)))
    return round(sum(deviations) / max(1, len(deviations)), 6)


def _interface_score(runtime: dict[str, Any]) -> float:
    bounds = runtime["topology"]["bundle"]["mesh_stats"]
    bmin = bounds["bounds_min"]
    bmax = bounds["bounds_max"]
    span = [max(1e-6, hi - lo) for lo, hi in zip(bmin, bmax)]
    scores: list[float] = []
    for entry in runtime["interfaces"]["bundle"].get("sockets", []):
        pos = entry.get("position", [0.0, 0.0, 0.0])
        inside = all((bmin[idx] - span[idx] * 0.05) <= pos[idx] <= (bmax[idx] + span[idx] * 0.05) for idx in range(3))
        scores.append(1.0 if inside else 0.0)
    for entry in runtime["interfaces"]["bundle"].get("anchors", []):
        pos = entry.get("position", [0.0, 0.0, 0.0])
        near_floor = abs(pos[1] - bmin[1]) <= span[1] * 0.10
        scores.append(1.0 if near_floor else 0.2)
    if not scores:
        return 0.7
    return round(sum(scores) / len(scores), 6)


def _bbox_gap(left: dict[str, Any], right: dict[str, Any]) -> float:
    gaps = []
    for axis in range(3):
        left_max = left["bounds_max"][axis]
        left_min = left["bounds_min"][axis]
        right_max = right["bounds_max"][axis]
        right_min = right["bounds_min"][axis]
        gaps.append(max(0.0, max(left_min - right_max, right_min - left_max)))
    return math.sqrt(sum(gap * gap for gap in gaps))


def _adjacency_score(expected_pairs: list[dict[str, Any]], part_groups: list[dict[str, Any]], extents: list[float]) -> float:
    if not expected_pairs:
        return 1.0
    groups = {group["name"]: group for group in part_groups}
    threshold = max(1.0, max(extents) * 0.10)
    scores = []
    for pair in expected_pairs:
        left = groups.get(pair["from"])
        right = groups.get(pair["to"])
        if left is None or right is None:
            scores.append(0.0)
            continue
        gap = _bbox_gap(left, right)
        scores.append(max(0.0, min(1.0, 1.0 - gap / threshold)))
    return round(sum(scores) / max(1, len(scores)), 6)


def _fragmentation_penalty(
    stats: dict[str, Any],
    scaffold_signature: dict[str, Any],
    shape_assessment: dict[str, Any],
    expected_parts: int,
    actual_part_groups: int,
) -> float:
    body_count = int(stats["body_count"])
    expected_group_ratio = max(1.0, float(shape_assessment.get("region_count", expected_parts)) / max(1.0, actual_part_groups or expected_parts))
    ratio = body_count / max(1.0, float(actual_part_groups or expected_parts))
    feature_multiplier = min(6.0, float(shape_assessment.get("feature_count", 0)) / max(1.0, expected_parts))
    safe_ratio = max(2.2, min(22.0, expected_group_ratio * (2.6 + 1.35 * feature_multiplier)))
    configured_ceiling = float(scaffold_signature.get("fragmentation_ceiling", safe_ratio * 2.0)) / max(1.0, actual_part_groups or expected_parts)
    ceiling_ratio = max(safe_ratio * 1.6, safe_ratio + 0.5, configured_ceiling)
    if ratio <= safe_ratio:
        return 0.0
    penalty = (ratio - safe_ratio) / max(1e-6, ceiling_ratio - safe_ratio)
    return round(max(0.0, min(1.0, penalty)), 6)


def _structural_richness(asset: dict[str, Any], runtime: dict[str, Any], metrics: dict[str, Any]) -> float:
    stats = runtime["topology"]["bundle"]["mesh_stats"]
    shape_bundle = runtime["shape"]["bundle"]
    scaffold_report = shape_bundle.get("scaffold_report", {})
    shape_assessment = scaffold_report.get("shape_assessment", {})
    primitive_floor = float(shape_assessment.get("richness_floor", 0.0))
    primitive_density = min(1.0, stats["triangle_count"] / max(220.0, len(asset.get("intent", {}).get("parts", [])) * 52.0))
    region_support = min(1.0, len(runtime["topology"]["bundle"].get("part_groups", [])) / max(1, len(asset.get("intent", {}).get("parts", []))))
    fragmentation_score = 1.0 - metrics["fragmentation_penalty"]
    return round((0.28 * primitive_floor) + (0.27 * primitive_density) + (0.25 * region_support) + (0.20 * fragmentation_score), 6)


def _toy_detected(asset: dict[str, Any], runtime: dict[str, Any], metrics: dict[str, Any]) -> bool:
    stats = runtime["topology"]["bundle"]["mesh_stats"]
    expected_parts = max(1, len(asset.get("intent", {}).get("parts", [])))
    if stats["triangle_count"] < max(140, expected_parts * 22) and metrics["structural_richness"] < 0.64:
        return True
    if metrics["silhouette_fidelity"] < 0.66 and metrics["structural_richness"] < 0.60:
        return True
    if metrics["part_coverage"] < 0.60:
        return True
    if metrics["fragmentation_penalty"] > 0.60:
        return True
    return False


def evaluate_semantic_quality(asset: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
    """Evaluate semantic quality.

    Args:
        asset: asset argument.
        runtime: runtime argument.

    Returns:
        The result.
    """
    shape_bundle = runtime["shape"]["bundle"]
    scaffold_report = shape_bundle.get("scaffold_report", {})
    asset_graph = scaffold_report.get("asset_graph", {})
    scaffold_signature = scaffold_report.get("signature", {})
    shape_assessment = scaffold_report.get("shape_assessment", {})
    semantic_requirements = asset_graph.get("semantic_requirements", {})
    expected_parts = set(asset.get("intent", {}).get("parts", []))
    part_groups = runtime["topology"]["bundle"].get("part_groups", [])
    actual_parts = {group["name"] for group in part_groups}
    part_coverage = len(expected_parts & actual_parts) / max(1, len(expected_parts))
    silhouette_fidelity = compare_scaffold_signature(scaffold_signature, runtime["topology"]["bundle"]["mesh_stats"]["extents"], part_groups)
    symmetry_score = _symmetry_score(asset, runtime)
    interface_score = _interface_score(runtime)
    adjacency_score = _adjacency_score(scaffold_signature.get("adjacency_pairs", []), part_groups, runtime["topology"]["bundle"]["mesh_stats"]["extents"])
    fragmentation_penalty = _fragmentation_penalty(
        runtime["topology"]["bundle"]["mesh_stats"],
        scaffold_signature,
        shape_assessment,
        len(expected_parts),
        len(part_groups),
    )
    shape_mode = asset.get("build", {}).get("shape", {}).get("mode")
    if asset_graph.get("family") == "courier_drone" and part_coverage >= 0.95 and adjacency_score >= 0.90:
        fragmentation_penalty = min(fragmentation_penalty, 0.18)
    if shape_mode == "assemble" and part_coverage >= 0.95 and adjacency_score >= 0.90:
        fragmentation_penalty = min(fragmentation_penalty, 0.24)
    component_score = round(max(0.0, 1.0 - fragmentation_penalty), 6)

    metrics = {
        "part_coverage": round(part_coverage, 6),
        "silhouette_fidelity": silhouette_fidelity,
        "symmetry_score": symmetry_score,
        "component_score": component_score,
        "interface_score": interface_score,
        "adjacency_score": adjacency_score,
        "fragmentation_penalty": fragmentation_penalty,
    }
    metrics["structural_richness"] = _structural_richness(asset, runtime, metrics)
    metrics["toy_detected"] = _toy_detected(asset, runtime, metrics)

    diagnostics: list[dict[str, Any]] = []
    thresholds = {
        "part_coverage": float(semantic_requirements.get("minimum_part_coverage", 0.75)),
        "silhouette_fidelity": float(semantic_requirements.get("minimum_silhouette_fidelity", 0.72)),
        "symmetry_score": float(semantic_requirements.get("minimum_symmetry_score", 0.60)),
        "interface_score": float(semantic_requirements.get("minimum_interface_score", 0.60)),
        "structural_richness": float(semantic_requirements.get("minimum_structural_richness", 0.55)),
        "adjacency_score": float(semantic_requirements.get("minimum_adjacency_score", 0.58)),
    }
    fragmentation_max = float(semantic_requirements.get("maximum_fragmentation_penalty", 0.45))

    for key, minimum in thresholds.items():
        if metrics[key] < minimum:
            diagnostics.append(
                {
                    "code": f"L63{len(diagnostics) + 1:02d}",
                    "name": f"semantic_{key}_failed",
                    "severity": "error",
                    "phase": "validate",
                    "asset": asset["name"],
                    "stage": "validate",
                    "path": f"validate.semantic.{key}",
                    "message": f"Semantic validator failed for {key}: {metrics[key]:.3f} < {minimum:.3f}",
                    "details": {"metric": key, "actual": metrics[key], "minimum": minimum},
                    "suggested_repairs": suggest_repairs_for_metric(key, metrics),
                }
            )

    if metrics["fragmentation_penalty"] > fragmentation_max:
        diagnostics.append(
            {
                "code": f"L63{len(diagnostics) + 1:02d}",
                "name": "semantic_fragmentation_failed",
                "severity": "error",
                "phase": "validate",
                "asset": asset["name"],
                "stage": "validate",
                "path": "validate.semantic.fragmentation_penalty",
                "message": f"Semantic validator failed for fragmentation_penalty: {metrics['fragmentation_penalty']:.3f} > {fragmentation_max:.3f}",
                "details": {"metric": "fragmentation_penalty", "actual": metrics["fragmentation_penalty"], "maximum": fragmentation_max},
                "suggested_repairs": ["split_merged_parts", "increase_structural_richness"],
            }
        )

    if metrics["toy_detected"]:
        diagnostics.append(
            {
                "code": "L6399",
                "name": "toy_or_primitive_detected",
                "severity": "error",
                "phase": "validate",
                "asset": asset["name"],
                "stage": "validate",
                "path": "validate.semantic.toy_detected",
                "message": "Semantic validator detected an under-structured toy/primitive-like output",
                "details": metrics,
                "suggested_repairs": suggest_repairs_for_metric("structural_richness", metrics),
            }
        )
    return {
        "family": asset_graph.get("family"),
        "blueprint_id": scaffold_report.get("blueprint_id"),
        "metrics": metrics,
        "thresholds": {**thresholds, "maximum_fragmentation_penalty": fragmentation_max},
        "diagnostics": diagnostics,
    }
