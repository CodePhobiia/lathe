"""Phase 14C universal quality planner."""

from __future__ import annotations

from typing import Any

from .art_direction import QUALITY_DIMENSIONS, normalize_art_direction
from .semantic_critique import critique_quality_plan
from .universal_quality import (
    universal_quality_metrics,
    universal_quality_scores,
)

QUALITY_PLAN_VERSION = "lathe.asset_quality.quality_plan.v1"


def build_quality_plan(
    design_brief: dict[str, Any],
    *,
    art_direction: dict[str, Any] | None = None,
    family_grammar: dict[str, Any] | None = None,
    construction_graph: dict[str, Any] | None = None,
    material_wear_graph: dict[str, Any] | None = None,
    reference_board: dict[str, Any] | None = None,
    style_pack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic family-agnostic quality plan."""
    brief = _normalize_design_brief(design_brief)
    grammar = _as_dict(family_grammar)
    graph = _as_dict(construction_graph)
    material = _as_dict(material_wear_graph)
    normalized_art_direction = normalize_art_direction(
        art_direction,
        design_brief=brief,
        family_metadata=grammar,
        reference_board=reference_board,
    )
    object_family = str(normalized_art_direction["object_family"])
    detail_zones = _detail_density_zones(object_family, graph)
    visual_hierarchy = _as_dict(normalized_art_direction.get("visual_hierarchy"))
    material_requirements = _as_dict(normalized_art_direction.get("materials"))
    motif_requirements = _as_dict(normalized_art_direction.get("motifs"))
    surface_story = _as_dict(normalized_art_direction.get("surface_story"))
    detail_requirements = {
        "density_zones": detail_zones,
        "tertiary_detail_budget": "bounded",
        "noise_policy": visual_hierarchy.get("noise_policy", "semantic-only"),
    }
    if brief.get("detail_density") is not None:
        detail_requirements["density"] = brief.get("detail_density")
    quality_plan = {
        "schema_version": QUALITY_PLAN_VERSION,
        "asset_id": normalized_art_direction["asset_id"],
        "family": normalized_art_direction["family"],
        "object_family": object_family,
        "source_art_direction": "art_direction.json" if art_direction else "design_brief.json",
        "source_family_metadata": "family_grammar_coverage.json",
        "primary_secondary_tertiary": detail_zones,
        "art_direction_ir": normalized_art_direction,
        "style_pack": _style_pack_summary(style_pack),
        "visual_hierarchy": visual_hierarchy,
        "silhouette_requirements": _silhouette_requirements(normalized_art_direction, grammar),
        "proportion_requirements": _as_dict(normalized_art_direction.get("proportion_policy")),
        "material_requirements": material_requirements,
        "material_separation_requirements": material_requirements,
        "detail_requirements": detail_requirements,
        "detail_density_zones": detail_zones,
        "motif_requirements": motif_requirements,
        "motif_language": motif_requirements,
        "surface_story_requirements": surface_story,
        "surface_story": surface_story,
        "platform": _as_dict(normalized_art_direction.get("platform")),
        "certification_targets": {
            "warning_min_score": 75,
            "strict_min_score": 90,
            "required_dimensions": list(QUALITY_DIMENSIONS),
            "warning_minimum": 0.75,
            "strict_minimum": 0.9,
            "dimensions": list(QUALITY_DIMENSIONS),
        },
        "likely_failure_modes": _likely_failure_modes(normalized_art_direction, grammar),
    }
    metrics = universal_quality_metrics(
        quality_plan,
        art_direction=normalized_art_direction,
        construction_graph=graph,
        material_wear_graph=material,
    )
    quality_plan["metrics"] = metrics
    quality_plan["semantic_critique"] = critique_quality_plan(quality_plan)
    return quality_plan


def evaluate_quality_plan(asset: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
    """Build the additive validate-stage quality-plan payload."""
    safe_asset = asset if isinstance(asset, dict) else {}
    safe_runtime = runtime if isinstance(runtime, dict) else {}
    brief = _runtime_design_brief(safe_asset, safe_runtime)
    plan = build_quality_plan(
        brief,
        family_grammar=_as_dict(safe_runtime.get("family_grammar")),
        construction_graph=_as_dict(safe_runtime.get("construction_graph")),
        material_wear_graph=_as_dict(safe_runtime.get("material_wear_graph")),
        reference_board=_as_dict(safe_runtime.get("reference_board")),
    )
    return {**plan, "diagnostics": []}


def _normalize_design_brief(design_brief: dict[str, Any]) -> dict[str, Any]:
    brief = _as_dict(design_brief)
    if "brief" in brief and isinstance(brief.get("brief"), dict):
        brief = _as_dict(brief.get("brief"))
    return brief


def _runtime_design_brief(asset: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
    runtime_brief = _as_dict(_as_dict(runtime.get("design_brief")).get("brief"))
    if runtime_brief:
        return {
            "asset_id": runtime_brief.get("asset_name") or asset.get("name") or "unnamed_asset",
            "family": runtime_brief.get("family") or "generic",
            "style_tags": runtime_brief.get("style_tags", []),
            "negative_constraints": runtime_brief.get("negative_constraints", []),
            "platform_profile": {"target": "game_runtime_proxy", "texture_budget": "proxy_or_deferred"},
            "required_features": _asset_parts(asset),
            "acceptance_goals": {
                "silhouette_readability": runtime_brief.get("silhouette"),
                "construction_intent": runtime_brief.get("shape_language"),
                "material_storytelling": runtime_brief.get("material_age"),
            },
        }
    return {
        "asset_id": asset.get("name") if isinstance(asset.get("name"), str) else "unnamed_asset",
        "family": asset.get("kind") if isinstance(asset.get("kind"), str) else "generic",
        "style": {"theme": "generic game asset", "keywords": [], "forbidden": []},
        "platform_profile": {"target": "game_runtime_proxy", "texture_budget": "proxy_or_deferred"},
        "required_features": _asset_parts(asset),
        "acceptance_goals": {},
    }


def _asset_parts(asset: dict[str, Any]) -> list[str]:
    intent = _as_dict(asset.get("intent"))
    parts = intent.get("parts")
    if isinstance(parts, list):
        return [str(part) for part in parts if isinstance(part, str)]
    return []


def _detail_density_zones(object_family: str, graph: dict[str, Any]) -> dict[str, list[str]]:
    nodes = [node for node in _as_list(graph.get("nodes")) if isinstance(node, dict)]
    by_category: dict[str, list[str]] = {}
    for node in nodes:
        category = str(node.get("category") or "detail")
        node_id = str(node.get("node_id") or category)
        by_category.setdefault(category, []).append(node_id)
    defaults = {
        "weapon": {
            "primary": ["blade_or_striking_surface"],
            "secondary": ["guard_or_handle"],
            "tertiary": ["edge_detail", "grip_wrap", "trim"],
        },
        "container": {
            "primary": ["body_shell"],
            "secondary": ["frame", "corner_guards", "handles"],
            "tertiary": ["decals", "wear", "fasteners"],
        },
        "machine": {
            "primary": ["machine_body"],
            "secondary": ["input_output_affordances", "service_panels"],
            "tertiary": ["status_lights", "labels", "wear"],
        },
        "furniture": {
            "primary": ["usable_surface"],
            "secondary": ["supports", "display_faces"],
            "tertiary": ["trim", "signage", "contact_wear"],
        },
    }
    zones = defaults.get(
        object_family,
        {
            "primary": ["primary_volume"],
            "secondary": ["functional_affordances"],
            "tertiary": ["motifs", "wear", "decals"],
        },
    )
    if by_category:
        zones = {
            "primary": _first_non_empty(
                by_category,
                ("blade", "shell", "body", "machine_body", "countertop", "primary_volume"),
                zones["primary"],
            ),
            "secondary": _first_non_empty(
                by_category,
                ("guard", "frame", "handle", "button", "port", "support", "display"),
                zones["secondary"],
            ),
            "tertiary": _first_non_empty(
                by_category,
                ("focal_detail", "trim", "decal", "wear_anchor", "fastener", "panel"),
                zones["tertiary"],
            ),
        }
    return zones


def _first_non_empty(
    by_category: dict[str, list[str]],
    categories: tuple[str, ...],
    fallback: list[str],
) -> list[str]:
    out: list[str] = []
    for category in categories:
        out.extend(by_category.get(category, []))
    return out or fallback


def _silhouette_requirements(
    art_direction: dict[str, Any],
    family_grammar: dict[str, Any],
) -> list[str]:
    silhouette = _as_dict(art_direction.get("silhouette"))
    requirements = [
        str(item)
        for item in _as_list(silhouette.get("required_distinctive_features"))
        if isinstance(item, str) and item
    ]
    grammar_rules = [
        str(item)
        for item in _as_list(family_grammar.get("required_rules"))
        if isinstance(item, str) and item
    ]
    return list(dict.fromkeys(requirements + grammar_rules[:4]))


def _likely_failure_modes(
    art_direction: dict[str, Any],
    family_grammar: dict[str, Any],
) -> list[str]:
    missing = [
        f"missing_family_rule:{item}"
        for item in _as_list(family_grammar.get("missing_required_rules"))
        if isinstance(item, str) and item
    ]
    forbidden = [
        str(item)
        for item in _as_list(art_direction.get("forbidden_visual_failure_modes"))
        if isinstance(item, str) and item
    ]
    return list(dict.fromkeys(missing + forbidden))[:12]


def _style_pack_summary(style_pack: dict[str, Any] | None) -> dict[str, Any]:
    pack = _as_dict(style_pack)
    if not pack:
        return {"present": False}
    return {
        "present": True,
        "id": pack.get("id"),
        "motif_count": len(_as_list(pack.get("motifs"))),
        "material_count": len(_as_list(pack.get("materials"))),
    }


def build_generation_quality_context(asset: dict[str, Any], runtime: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build the pre-shape quality context consumed by generation stages.

    This is intentionally additive: validate-stage ``evaluate_quality_plan``
    remains the certification source, while this helper publishes the same art
    direction / quality plan *before* shape generation so shape, surface, and
    repair adapters can steer output rather than only score it afterward.
    """
    safe_asset = asset if isinstance(asset, dict) else {}
    safe_runtime = runtime if isinstance(runtime, dict) else {}

    # Imported lazily to keep the validate-only planner path free of import
    # cycles and to reuse the same reference-negative merge semantics.
    from .design_brief import evaluate_design_brief

    design_brief = evaluate_design_brief(safe_asset, safe_runtime)
    reference_board = _as_dict(safe_runtime.get("_reference_board")) or _as_dict(
        safe_runtime.get("reference_board")
    )
    plan = build_quality_plan(
        _as_dict(design_brief.get("brief")),
        reference_board=reference_board,
    )
    adapters = quality_plan_generation_adapters(plan)
    return {
        "schema_version": "lathe.asset_quality.generation_quality.v1",
        "source_stage": "pre_shape",
        "stage_order": {
            "created_before": "shape",
            "consumed_by": ["shape", "surface", "repair"],
        },
        "design_brief": design_brief,
        "art_direction_ir": _as_dict(plan.get("art_direction_ir")),
        "quality_plan": plan,
        "generation_adapters": adapters,
        "diagnostics": [],
    }


def quality_plan_generation_adapters(quality_plan: dict[str, Any]) -> dict[str, Any]:
    """Translate generic quality-plan fields into generation adapter knobs."""
    plan = _as_dict(quality_plan)
    art_direction = _as_dict(plan.get("art_direction_ir"))
    visual_hierarchy = _as_dict(plan.get("visual_hierarchy"))
    material = _as_dict(plan.get("material_requirements"))
    detail = _as_dict(plan.get("detail_requirements"))
    surface_story = _as_dict(plan.get("surface_story")) or _as_dict(
        plan.get("surface_story_requirements")
    )
    motifs = _as_dict(plan.get("motif_language")) or _as_dict(plan.get("motif_requirements"))
    platform = _as_dict(plan.get("platform"))
    density_text = " ".join(
        str(value).lower()
        for value in (
            art_direction.get("detail_density"),
            visual_hierarchy.get("detail_density"),
            detail.get("density"),
            detail.get("noise_policy"),
        )
        if value is not None
    )
    silhouette_text = " ".join(
        str(value).lower()
        for value in (
            art_direction.get("silhouette_language"),
            art_direction.get("silhouette"),
            plan.get("silhouette_requirements"),
            art_direction.get("shape_language"),
        )
        if value is not None
    )
    material_text = " ".join(
        str(value).lower() for value in (material, surface_story, art_direction.get("materials"))
    )

    detail_level = _density_level(density_text)
    silhouette_level = 1 if _contains_any(
        silhouette_text,
        ("bold", "chunky", "distinct", "iconic", "guard", "readable", "strong"),
    ) else 0
    material_contrast_level = 1 if _contains_any(
        material_text,
        ("contrast", "separation", "paint", "metal", "wear", "edge", "material"),
    ) else 0
    motif_terms = _flatten_terms(motifs)
    wear_terms = _flatten_terms(surface_story)
    platform_target = str(platform.get("target") or platform.get("profile") or "").lower()
    runtime_budget_multiplier = 0.94 if "mobile" in platform_target else 1.0

    return {
        "quality_plan_available": bool(plan),
        "quality_plan_schema": plan.get("schema_version"),
        "object_family": plan.get("object_family") or plan.get("family"),
        "feature_density_multiplier": _clamp(1.0 + detail_level * 0.11, 0.75, 1.35),
        "panel_depth_multiplier": _clamp(1.0 + detail_level * 0.05 + material_contrast_level * 0.04, 0.8, 1.25),
        "edge_weight_multiplier": _clamp(1.0 + detail_level * 0.04 + material_contrast_level * 0.05, 0.8, 1.25),
        "silhouette_bias_multiplier": _clamp(1.0 + silhouette_level * 0.07, 0.85, 1.2),
        "trim_scale_multiplier": _clamp(1.0 + detail_level * 0.04, 0.8, 1.2),
        "detail_policy": detail.get("noise_policy", "semantic-only"),
        "material_contrast_policy": "high" if material_contrast_level else "standard",
        "motifs": motif_terms[:8],
        "wear_anchors": wear_terms[:8],
        "runtime_budget_multiplier": runtime_budget_multiplier,
    }


def _density_level(text: str) -> int:
    lowered = text.lower()
    if _contains_any(lowered, ("hero", "high", "dense", "premium", "tertiary", "rich")):
        return 2
    if _contains_any(lowered, ("medium", "balanced", "secondary")):
        return 1
    if _contains_any(lowered, ("low", "simple", "minimal", "blockout")):
        return -1
    return 0


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _flatten_terms(value: Any) -> list[str]:
    if isinstance(value, dict):
        out: list[str] = []
        for item in value.values():
            out.extend(_flatten_terms(item))
        return list(dict.fromkeys(out))
    if isinstance(value, list):
        out = []
        for item in value:
            out.extend(_flatten_terms(item))
        return list(dict.fromkeys(out))
    if isinstance(value, str) and value:
        return [value]
    return []


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


__all__ = [
    "QUALITY_PLAN_VERSION",
    "build_generation_quality_context",
    "build_quality_plan",
    "evaluate_quality_plan",
    "quality_plan_generation_adapters",
    "universal_quality_scores",
]
