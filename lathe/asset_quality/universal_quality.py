"""Universal quality scoring for Phase 14C.

This module centralizes the family-agnostic quality dimensions used by
quality plans and certificates. It works from semantic evidence only:
no renderer, bake, mesh, or engine export is executed here.
"""

from __future__ import annotations

from typing import Any

from .art_direction import QUALITY_DIMENSIONS
from .detail_hierarchy import estimate_detail_hierarchy
from .motif_language import estimate_motif_coherence, estimate_surface_storytelling
from .semantic_critique import repair_suggestions_for_scores
from .silhouette import estimate_silhouette_strength
from .style_coherence import (
    estimate_functional_readability,
    estimate_material_contrast,
    estimate_procedural_noise_penalty,
    estimate_proportion_intent,
    estimate_style_consistency,
)

UNIVERSAL_QUALITY_VERSION = "lathe.asset_quality.universal_quality.v1"


def universal_quality_metrics(
    quality_plan: dict[str, Any],
    *,
    art_direction: dict[str, Any] | None = None,
    construction_graph: dict[str, Any] | None = None,
    material_wear_graph: dict[str, Any] | None = None,
) -> dict[str, float]:
    """Return normalized 0-1 metrics for every universal dimension."""
    plan = _as_dict(quality_plan)
    existing = _as_dict(plan.get("metrics"))
    if all(name in existing for name in QUALITY_DIMENSIONS):
        return {
            name: _normalized_metric(existing.get(name), name)
            for name in QUALITY_DIMENSIONS
        }
    direction = _as_dict(art_direction) or _as_dict(plan.get("art_direction_ir"))
    graph = _as_dict(construction_graph)
    material = _as_dict(material_wear_graph)
    return {
        "silhouette_strength": estimate_silhouette_strength(direction, graph),
        "proportion_intent": estimate_proportion_intent(direction, graph),
        "material_contrast": estimate_material_contrast(direction, material),
        "detail_hierarchy": estimate_detail_hierarchy(plan, graph),
        "motif_coherence": estimate_motif_coherence(plan),
        "surface_storytelling": estimate_surface_storytelling(plan, material),
        "functional_readability": estimate_functional_readability(plan, graph),
        "style_consistency": estimate_style_consistency(direction),
        "procedural_noise_penalty": estimate_procedural_noise_penalty(direction, graph),
    }


def universal_quality_scores(
    quality_plan: dict[str, Any],
    *,
    construction_graph: dict[str, Any] | None = None,
    material_wear_graph: dict[str, Any] | None = None,
) -> dict[str, int]:
    """Return integer 0-10 scores where higher always means better."""
    metrics = universal_quality_metrics(
        quality_plan,
        construction_graph=construction_graph,
        material_wear_graph=material_wear_graph,
    )
    return {
        dimension: _metric_to_score(metrics[dimension], dimension)
        for dimension in QUALITY_DIMENSIONS
    }


def universal_quality_results(
    quality_plan: dict[str, Any],
    *,
    construction_graph: dict[str, Any] | None = None,
    material_wear_graph: dict[str, Any] | None = None,
    repair_threshold: float = 0.75,
) -> dict[str, Any]:
    """Return per-dimension scores, diagnostics, and repair suggestions."""
    metrics = universal_quality_metrics(
        quality_plan,
        construction_graph=construction_graph,
        material_wear_graph=material_wear_graph,
    )
    scores = {
        dimension: _metric_to_score(metrics[dimension], dimension)
        for dimension in QUALITY_DIMENSIONS
    }
    normalized_scores = {
        dimension: _score_quality_value(metrics[dimension], dimension)
        for dimension in QUALITY_DIMENSIONS
    }
    repairs = repair_suggestions_for_scores(metrics, threshold=repair_threshold)
    repairs_by_dimension: dict[str, list[dict[str, Any]]] = {
        dimension: [] for dimension in QUALITY_DIMENSIONS
    }
    for repair in repairs:
        dimension = repair.get("dimension")
        if isinstance(dimension, str) and dimension in repairs_by_dimension:
            repairs_by_dimension[dimension].append(repair)
    dimensions = {
        dimension: {
            "score": scores[dimension],
            "max_score": 10,
            "metric": metrics[dimension],
            "diagnostics": _diagnostics_for_dimension(
                dimension,
                normalized_scores[dimension],
            ),
            "repair_suggestions": repairs_by_dimension[dimension],
        }
        for dimension in QUALITY_DIMENSIONS
    }
    return {
        "schema_version": UNIVERSAL_QUALITY_VERSION,
        "scores": scores,
        "metrics": metrics,
        "dimensions": dimensions,
    }


def _diagnostics_for_dimension(dimension: str, score: float) -> list[str]:
    if score >= 0.75:
        return []
    messages = {
        "silhouette_strength": "silhouette lacks enough distinctive semantic features",
        "proportion_intent": "proportion anchors are weak or missing",
        "material_contrast": "material zones are not sufficiently separated",
        "detail_hierarchy": "primary/secondary/tertiary detail hierarchy is weak",
        "motif_coherence": "motifs are missing, forbidden, or not placement-bound",
        "surface_storytelling": "wear, grime, decal, or glow logic lacks semantic anchors",
        "functional_readability": "viewer-facing functional affordances are unclear",
        "style_consistency": "style intent, motifs, materials, or forbiddens conflict",
        "procedural_noise_penalty": "procedural detail reads as unbounded noise",
    }
    return [messages.get(dimension, "universal quality dimension is below threshold")]


def _metric_to_score(value: float, dimension: str) -> int:
    return max(0, min(10, round(_score_quality_value(value, dimension) * 10)))


def _score_quality_value(value: float, dimension: str) -> float:
    metric = _normalized_metric(value, dimension)
    if dimension == "procedural_noise_penalty":
        return 1.0 - metric
    return metric


def _normalized_metric(value: Any, _dimension: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return max(0.0, min(1.0, float(value)))


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


__all__ = [
    "UNIVERSAL_QUALITY_VERSION",
    "QUALITY_DIMENSIONS",
    "universal_quality_metrics",
    "universal_quality_results",
    "universal_quality_scores",
]
