"""Phase 14C tests for universal quality scoring."""

from __future__ import annotations

from lathe.asset_quality.quality_planner import build_quality_plan
from lathe.asset_quality.universal_quality import (
    universal_quality_results,
    universal_quality_scores,
)


def _brief(family: str = "sci_fi_crate") -> dict:
    return {
        "asset_id": family,
        "family": family,
        "style": {
            "theme": family,
            "keywords": ["industrial", "readable"],
            "forbidden": ["organic vines", "random greebles"],
        },
        "platform_profile": {
            "target": "realtime_proxy",
            "triangle_budget_warning": 4000,
            "triangle_budget_strict": 2500,
        },
        "required_features": ["corner guards", "latches", "readable panels"],
    }


def test_silhouette_rewards_distinctive_semantic_features() -> None:
    plan = build_quality_plan(
        _brief(),
        family_grammar={"coverage": 1.0, "required_rules": ["corner_guard", "latch"]},
        construction_graph={
            "nodes": [
                {"node_id": "body", "category": "shell", "bounds": {"x": 1}},
                {"node_id": "guard", "category": "corner_guard", "bounds": {"x": 1}},
                {"node_id": "latch", "category": "latch", "bounds": {"x": 1}},
                {"node_id": "label", "category": "decal", "bounds": {"x": 1}},
            ],
            "summary": {
                "major_silhouette_nodes": ["body", "guard", "latch"],
                "unclassified_major_primitives": 0,
            },
        },
    )

    assert universal_quality_scores(plan)["silhouette_strength"] >= 8


def test_silhouette_penalizes_generic_primitive_stack() -> None:
    plan = build_quality_plan(
        {"asset_id": "box", "family": "generic", "required_features": []},
        construction_graph={
            "nodes": [{"node_id": "cube", "category": "primary_volume"}],
            "summary": {"major_silhouette_nodes": [], "unclassified_major_primitives": 3},
        },
    )

    assert universal_quality_scores(plan)["silhouette_strength"] < 7


def test_material_contrast_rewards_separated_zones_and_repairs_weak_contrast() -> None:
    good = build_quality_plan(
        _brief(),
        material_wear_graph={"graph_summary": {"material_zone_count": 5}},
    )
    weak = build_quality_plan(
        _brief(),
        material_wear_graph={"graph_summary": {"material_zone_count": 0}},
    )

    assert universal_quality_scores(good)["material_contrast"] >= 8
    weak_results = universal_quality_results(weak)
    repairs = weak_results["dimensions"]["material_contrast"]["repair_suggestions"]
    assert repairs
    assert repairs[0]["issue"] == "low_material_contrast"


def test_detail_hierarchy_penalizes_uniform_procedural_noise() -> None:
    plan = build_quality_plan(
        _brief(),
        construction_graph={
            "nodes": [{"node_id": f"rib_{idx}", "category": "rib"} for idx in range(12)],
            "summary": {
                "major_silhouette_nodes": ["rib_0"],
                "unclassified_major_primitives": 5,
                "repeated_elements_semantic": False,
            },
        },
    )
    scores = universal_quality_scores(plan)

    assert scores["procedural_noise_penalty"] < 7


def test_motif_and_style_scores_catch_forbidden_conflicts() -> None:
    plan = build_quality_plan(
        {
            **_brief("fantasy_weapon"),
            "style": {
                "theme": "",
                "keywords": [],
                "forbidden": ["sci-fi panels"],
            },
            "required_features": ["blade"],
        }
    )
    results = universal_quality_results(plan)

    assert results["dimensions"]["motif_coherence"]["score"] < 8
    assert results["dimensions"]["style_consistency"]["score"] < 8


def test_functional_readability_consumes_family_metadata() -> None:
    plan = build_quality_plan(
        _brief("roblox_tycoon_machine"),
        family_grammar={"coverage": 1.0, "required_rules": ["button", "port"]},
        construction_graph={
            "nodes": [
                {"node_id": "body", "category": "machine_body", "bounds": {"x": 1}},
                {"node_id": "button", "category": "button", "bounds": {"x": 1}},
                {"node_id": "output", "category": "port", "bounds": {"x": 1}},
            ],
            "summary": {"major_silhouette_nodes": ["body", "button"], "unclassified_major_primitives": 0},
        },
    )

    assert universal_quality_scores(plan)["functional_readability"] >= 8
