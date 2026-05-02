"""Motif and surface-story scoring helpers for Phase 14C."""

from __future__ import annotations

from typing import Any


def estimate_motif_coherence(quality_plan: dict[str, Any]) -> float:
    """Score whether motifs have allowed tokens and placement rules."""
    motifs = _as_dict(quality_plan.get("motif_language"))
    allowed = _as_list(motifs.get("allowed"))
    rules = _as_list(motifs.get("placement_rules"))
    score = 0.42 + min(0.28, 0.07 * len(allowed)) + min(0.22, 0.08 * len(rules))
    return _clamp(score)


def estimate_surface_storytelling(
    quality_plan: dict[str, Any],
    material_wear_graph: dict[str, Any],
) -> float:
    """Score whether wear/decal/grime intent has semantic anchors."""
    story = _as_dict(quality_plan.get("surface_story"))
    wear_logic = _as_list(story.get("wear_logic"))
    decals = _as_list(story.get("decals"))
    material_summary = _as_dict(material_wear_graph.get("graph_summary"))
    wear_count = _number(material_summary.get("wear_mask_count"), 0.0)
    score = 0.42
    score += min(0.24, 0.06 * len(wear_logic))
    score += min(0.12, 0.04 * len(decals))
    score += min(0.22, 0.04 * wear_count)
    return _clamp(score)


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


__all__ = ["estimate_motif_coherence", "estimate_surface_storytelling"]
