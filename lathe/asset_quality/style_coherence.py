"""Style, material, proportion, and noise scoring helpers for Phase 14C."""

from __future__ import annotations

from typing import Any


def estimate_proportion_intent(
    art_direction: dict[str, Any],
    construction_graph: dict[str, Any],
) -> float:
    """Score whether proportion/scale anchors are explicit and semantic."""
    policy = _as_dict(art_direction.get("proportion_policy"))
    anchors = _as_list(policy.get("scale_anchors"))
    nodes = _as_list(construction_graph.get("nodes"))
    bounded_nodes = [
        node for node in nodes if isinstance(node, dict) and _as_dict(node.get("bounds"))
    ]
    score = 0.5 + min(0.24, 0.06 * len(anchors)) + min(0.26, 0.035 * len(bounded_nodes))
    return _clamp(score)


def estimate_material_contrast(
    art_direction: dict[str, Any],
    material_wear_graph: dict[str, Any],
) -> float:
    """Score semantic material-zone contrast."""
    material_goals = _as_dict(art_direction.get("materials"))
    goal_zones = _as_list(material_goals.get("zones"))
    summary = _as_dict(material_wear_graph.get("graph_summary"))
    zones = _number(summary.get("material_zone_count"), len(_as_list(material_wear_graph.get("material_zones"))))
    score = 0.42 + min(0.25, 0.04 * len(goal_zones)) + min(0.33, 0.065 * zones)
    return _clamp(score)


def estimate_functional_readability(
    quality_plan: dict[str, Any],
    construction_graph: dict[str, Any],
) -> float:
    """Score whether functional affordances are declared in graph/read layers."""
    hierarchy = _as_dict(quality_plan.get("visual_hierarchy"))
    nodes = _as_list(construction_graph.get("nodes"))
    categories = {
        str(node.get("category"))
        for node in nodes
        if isinstance(node, dict) and node.get("category")
    }
    affordance_hits = sum(
        1
        for token in ("handle", "guard", "button", "port", "latch", "grip", "countertop", "display")
        if token in categories or token in str(hierarchy).lower()
    )
    return _clamp(0.5 + min(0.38, 0.095 * affordance_hits) + (0.08 if nodes else 0.0))


def estimate_style_consistency(art_direction: dict[str, Any]) -> float:
    """Score whether style intent, motifs, materials, and forbiddens agree."""
    style = _as_dict(art_direction.get("style_intent"))
    motifs = _as_dict(art_direction.get("motifs"))
    materials = _as_dict(art_direction.get("materials"))
    forbidden = _as_list(art_direction.get("forbidden_visual_failure_modes"))
    score = 0.42
    if style.get("substyle") and style.get("substyle") != "general game asset":
        score += 0.16
    if _as_list(style.get("mood")):
        score += 0.12
    if _as_list(motifs.get("allowed")):
        score += 0.12
    if _as_list(materials.get("zones")):
        score += 0.1
    if forbidden:
        score += 0.08
    return _clamp(score)


def estimate_procedural_noise_penalty(
    art_direction: dict[str, Any],
    construction_graph: dict[str, Any],
) -> float:
    """Estimate bad procedural noise, where lower is better."""
    forbidden = " ".join(_as_list(art_direction.get("forbidden_visual_failure_modes"))).lower()
    summary = _as_dict(construction_graph.get("summary"))
    unclassified = _number(summary.get("unclassified_major_primitives"), 0.0)
    repeated_semantic = summary.get("repeated_elements_semantic") is True
    penalty = 0.22
    if "random" in forbidden or "noise" in forbidden:
        penalty -= 0.05
    if repeated_semantic:
        penalty -= 0.06
    penalty += min(0.4, 0.08 * unclassified)
    return _clamp(penalty)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _number(value: Any, default: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, round(value, 3)))


__all__ = [
    "estimate_functional_readability",
    "estimate_material_contrast",
    "estimate_procedural_noise_penalty",
    "estimate_proportion_intent",
    "estimate_style_consistency",
]
