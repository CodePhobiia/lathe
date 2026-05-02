"""Phase 14C generation-time quality steering tests.

These tests lock the missing bridge from post-generation quality evidence into
pre-shape art direction, shape/material conditioning, and concrete repair ops.
"""

from __future__ import annotations

from lathe.asset_quality.quality_planner import build_generation_quality_context
from lathe.candidate_search import CandidateParams, apply_quality_adapters_to_candidate_params
from lathe.repair_planner import semantic_critique_to_repair_actions
from lathe.shape.geometry.conditioning import merge_quality_generation_conditioning


def _asset(detail_density: str = "hero") -> dict:
    return {
        "name": "phase14_hero_crate",
        "kind": "sci_fi_crate",
        "intent": {"parts": ["body", "latch", "corner_guard", "hinge"]},
        "experimental": {
            "art_direction": {
                "style_tags": ["premium", "industrial", "readable"],
                "silhouette": "chunky protected silhouette with strong corner reads",
                "detail_density": detail_density,
                "material_age": "painted metal with edge wear",
                "shape_language": "primary mass, secondary armor plates, tertiary bolts",
            }
        },
    }


def test_generation_quality_context_is_created_before_shape_with_plan_and_adapters() -> None:
    context = build_generation_quality_context(
        _asset(),
        {
            "_reference_board": {
                "negative_constraints": ["plain cube blockout", "unbounded random greebles"],
            }
        },
    )

    assert context["schema_version"] == "lathe.asset_quality.generation_quality.v1"
    assert context["source_stage"] == "pre_shape"
    assert context["stage_order"]["created_before"] == "shape"
    assert context["quality_plan"]["schema_version"] == "lathe.asset_quality.quality_plan.v1"
    assert context["art_direction_ir"] == context["quality_plan"]["art_direction_ir"]
    assert context["generation_adapters"]["quality_plan_available"] is True
    assert context["generation_adapters"]["feature_density_multiplier"] > 1.0


def test_shape_conditioning_records_that_quality_plan_was_consumed() -> None:
    quality_generation = build_generation_quality_context(_asset(), {})
    merged = merge_quality_generation_conditioning(
        {"source_root": "/tmp/project", "reference_strength": 0.0, "palette": []},
        quality_generation,
    )

    assert merged["quality_plan_consumed"] is True
    assert merged["quality_generation_source_stage"] == "pre_shape"
    assert merged["quality_plan"]["schema_version"] == "lathe.asset_quality.quality_plan.v1"
    assert merged["art_direction_ir"] == quality_generation["art_direction_ir"]
    assert merged["quality_conditioning"]["feature_density_multiplier"] > 1.0


def test_art_direction_quality_adapters_change_candidate_params() -> None:
    base = CandidateParams(
        width_scale=1.0,
        height_scale=1.0,
        depth_scale=1.0,
        feature_density=1.0,
        panel_depth=1.0,
        edge_weight=1.0,
        support_spread=1.0,
        attachment_spread=1.0,
        trim_scale=1.0,
        silhouette_bias=1.0,
        rotor_guard_scale=1.0,
    )
    simple = build_generation_quality_context(_asset("low"), {})["generation_adapters"]
    hero = build_generation_quality_context(_asset("hero"), {})["generation_adapters"]

    simple_params = apply_quality_adapters_to_candidate_params(base, simple)
    hero_params = apply_quality_adapters_to_candidate_params(base, hero)

    assert hero_params.feature_density > simple_params.feature_density
    assert hero_params.panel_depth >= simple_params.panel_depth
    assert hero_params.edge_weight >= simple_params.edge_weight
    assert hero_params.silhouette_bias >= simple_params.silhouette_bias
    assert base.feature_density == 1.0  # adapter does not mutate caller-owned params


def test_semantic_critique_suggestions_map_to_concrete_repair_actions() -> None:
    critique = {
        "suggestions": [
            {
                "dimension": "silhouette_strength",
                "severity": "error",
                "target": "overall",
                "repair_hint": "reselect or refit silhouette with clearer primary read",
            },
            {
                "dimension": "detail_hierarchy",
                "severity": "warning",
                "target": "secondary_detail",
                "repair_hint": "add secondary features and reduce flat blockout feel",
            },
            {
                "dimension": "material_contrast",
                "severity": "warning",
                "target": "surface",
                "repair_hint": "reauthor surface zones with stronger material contrast",
            },
        ]
    }

    actions = semantic_critique_to_repair_actions(critique)
    action_names = [action.action for action in actions]

    assert "reselect_candidate" in action_names
    assert "add_secondary_features" in action_names
    assert "reauthor_surface_layer" in action_names
    assert all(action.details.get("source") == "semantic_critique" for action in actions)
