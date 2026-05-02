"""Family-agnostic detail hierarchy scoring helpers for Phase 14C."""

from __future__ import annotations

from typing import Any


def estimate_detail_hierarchy(
    quality_plan: dict[str, Any],
    construction_graph: dict[str, Any],
) -> float:
    """Return a score for primary/secondary/tertiary form separation."""
    zones = _as_dict(quality_plan.get("detail_density_zones"))
    nodes = _as_list(construction_graph.get("nodes"))
    categories = {
        str(node.get("category"))
        for node in nodes
        if isinstance(node, dict) and node.get("category")
    }
    score = 0.45
    if _as_list(zones.get("primary")):
        score += 0.17
    if _as_list(zones.get("secondary")):
        score += 0.17
    if _as_list(zones.get("tertiary")):
        score += 0.17
    if len(categories) >= 6:
        score += 0.04
    return _clamp(score)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, round(value, 3)))


__all__ = ["estimate_detail_hierarchy"]
