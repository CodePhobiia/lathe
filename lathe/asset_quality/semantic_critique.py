"""Semantic repair suggestions for Phase 14C quality failures."""

from __future__ import annotations

import hashlib
from typing import Any

SEMANTIC_CRITIQUE_VERSION = "lathe.asset_quality.semantic_critique.v1"

_REPAIRS: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "silhouette_strength": (
        "silhouette.required_distinctive_features",
        "Add or emphasize a family-specific silhouette landmark visible at 128px.",
        ("primary_silhouette", "functional_parts"),
    ),
    "proportion_intent": (
        "proportion_policy.scale_anchors",
        "Tighten functional scale relationships before adding tertiary detail.",
        ("construction_identity", "functional_parts"),
    ),
    "material_contrast": (
        "materials.zones",
        "Increase value/hue separation and bind accent material to a focal affordance.",
        ("primary_silhouette", "material_roles"),
    ),
    "detail_hierarchy": (
        "detail_density_zones",
        "Separate primary, secondary, and tertiary forms before adding microdetail.",
        ("primary_silhouette", "construction_identity"),
    ),
    "motif_coherence": (
        "motif_language.placement_rules",
        "Bind ornament to declared motifs and forbid unrelated repetition.",
        ("style_intent", "functional_parts"),
    ),
    "surface_storytelling": (
        "surface_story.wear_logic",
        "Move wear and grime to contact, edge, recess, and affordance zones.",
        ("material_roles", "construction_identity"),
    ),
    "functional_readability": (
        "visual_hierarchy.secondary_read",
        "Clarify handles, buttons, edges, screens, sockets, or other use affordances.",
        ("primary_silhouette", "platform_budget"),
    ),
    "style_consistency": (
        "style_intent",
        "Align materials, motifs, proportions, and forbidden forms to one style language.",
        ("construction_identity", "material_roles"),
    ),
    "procedural_noise_penalty": (
        "visual_hierarchy.noise_policy",
        "Reduce unbounded procedural repetition and keep detail tied to motif or function.",
        ("primary_silhouette", "style_intent"),
    ),
}


def critique_quality_plan(
    quality_plan: dict[str, Any],
    *,
    threshold: float = 0.75,
) -> dict[str, Any]:
    """Return deterministic semantic repair suggestions for weak scores."""
    scores = _as_dict(quality_plan.get("metrics"))
    issues = repair_suggestions_for_scores(scores, threshold=threshold)
    highest = issues[0]["issue"] if issues else None
    return {
        "schema_version": SEMANTIC_CRITIQUE_VERSION,
        "asset_id": quality_plan.get("asset_id"),
        "source_quality_plan": "quality_plan.json",
        "summary": {
            "status": "warning_pass_with_repairs" if issues else "pass",
            "highest_priority_issue": highest,
        },
        "issue_count": len(issues),
        "issues": issues,
        "repairs": issues,
    }


def repair_suggestions_for_scores(
    scores: dict[str, Any],
    *,
    threshold: float = 0.75,
) -> list[dict[str, Any]]:
    """Convert low normalized scores into semantic, patchable repairs."""
    repairs: list[dict[str, Any]] = []
    for dimension in sorted(_REPAIRS):
        value = _normalized_score(scores.get(dimension), dimension)
        if value >= threshold:
            continue
        target, repair, preserve = _REPAIRS[dimension]
        repairs.append(
            {
                "issue_id": _issue_id(dimension, repair),
                "issue": f"low_{dimension}",
                "severity": "warning",
                "dimension": dimension,
                "score": value,
                "threshold": threshold,
                "target": target,
                "evidence": _evidence_for_dimension(dimension),
                "repair": repair,
                "preserve": list(preserve),
            }
        )
    return repairs


def _evidence_for_dimension(dimension: str) -> list[str]:
    evidence = {
        "silhouette_strength": ["quality_plan.json", "construction_graph.json"],
        "proportion_intent": ["quality_plan.json", "construction_graph.json"],
        "material_contrast": ["quality_plan.json", "material_wear_graph.json"],
        "detail_hierarchy": ["quality_plan.json", "construction_graph.json"],
        "motif_coherence": ["quality_plan.json", "art_direction.json"],
        "surface_storytelling": ["quality_plan.json", "material_wear_graph.json"],
        "functional_readability": ["quality_plan.json", "construction_graph.json"],
        "style_consistency": ["quality_plan.json", "art_direction.json"],
        "procedural_noise_penalty": ["quality_plan.json", "construction_graph.json"],
    }
    return evidence.get(dimension, ["quality_plan.json"])


def _normalized_score(value: Any, dimension: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    numeric = max(0.0, min(1.0, float(value)))
    if dimension == "procedural_noise_penalty":
        return 1.0 - numeric
    return numeric


def _issue_id(dimension: str, repair: str) -> str:
    payload = f"{dimension}|{repair}".encode()
    return hashlib.blake2b(payload, digest_size=8).hexdigest()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


__all__ = [
    "SEMANTIC_CRITIQUE_VERSION",
    "critique_quality_plan",
    "repair_suggestions_for_scores",
]
