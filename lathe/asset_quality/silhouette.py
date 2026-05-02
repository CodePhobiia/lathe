"""Family-agnostic silhouette scoring helpers for Phase 14C."""

from __future__ import annotations

from typing import Any


def estimate_silhouette_strength(
    art_direction: dict[str, Any],
    construction_graph: dict[str, Any],
) -> float:
    """Estimate thumbnail/silhouette strength from semantic evidence."""
    silhouette = _as_dict(art_direction.get("silhouette"))
    summary = _as_dict(construction_graph.get("summary"))
    nodes = _as_list(construction_graph.get("nodes"))
    required = _as_list(silhouette.get("required_distinctive_features"))
    major = _as_list(summary.get("major_silhouette_nodes"))
    categories = {
        str(node.get("category"))
        for node in nodes
        if isinstance(node, dict) and node.get("category")
    }
    score = 0.48
    score += min(0.22, 0.05 * len(required))
    score += min(0.18, 0.04 * len(major))
    score += min(0.12, 0.02 * len(categories))
    if summary.get("unclassified_major_primitives") == 0:
        score += 0.04
    return _clamp(score)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, round(value, 3)))


__all__ = ["estimate_silhouette_strength"]
