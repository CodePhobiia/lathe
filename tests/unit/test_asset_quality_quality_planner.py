"""Phase 14C tests for universal quality planning."""

from __future__ import annotations

import json
from pathlib import Path

from lathe.asset_quality.quality_planner import (
    QUALITY_PLAN_VERSION,
    build_quality_plan,
    evaluate_quality_plan,
    universal_quality_scores,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_QUALITY_ENGINE = _REPO_ROOT / "examples" / "asset_quality" / "quality_engine"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_quality_planner_matches_checked_in_plans_for_all_families() -> None:
    expected_families = {
        "fantasy_weapon": "weapon",
        "sci_fi_crate": "container",
        "roblox_tycoon_machine": "machine",
        "environment_shop_counter": "furniture",
    }

    for fixture_name, object_family in expected_families.items():
        fixture = _QUALITY_ENGINE / fixture_name
        plan = build_quality_plan(
            _load(fixture / "design_brief.json"),
            art_direction=_load(fixture / "art_direction.json"),
            family_grammar=_load(fixture / "family_grammar_coverage.json"),
            construction_graph=_load(fixture / "construction_graph.json"),
            material_wear_graph=_load(fixture / "material_wear_graph.json"),
        )

        assert plan == _load(fixture / "quality_plan.json")
        assert plan["schema_version"] == QUALITY_PLAN_VERSION
        assert plan["object_family"] == object_family
        assert plan["source_art_direction"] == "art_direction.json"
        assert plan["source_family_metadata"] == "family_grammar_coverage.json"
        assert set(plan["primary_secondary_tertiary"]) == {"primary", "secondary", "tertiary"}
        assert plan["material_requirements"] == plan["material_separation_requirements"]
        assert plan["detail_requirements"]["density_zones"] == plan["detail_density_zones"]
        assert plan["motif_requirements"] == plan["motif_language"]
        assert plan["surface_story_requirements"] == plan["surface_story"]
        assert plan["certification_targets"]["warning_min_score"] == 75
        assert plan["certification_targets"]["strict_min_score"] == 90
        assert plan["certification_targets"]["required_dimensions"]
        assert plan["semantic_critique"]["issue_count"] == 0


def test_universal_quality_scores_are_strict_ready_for_proof_fixtures() -> None:
    for fixture in sorted(_QUALITY_ENGINE.iterdir()):
        if not fixture.is_dir():
            continue
        scores = universal_quality_scores(
            _load(fixture / "quality_plan.json"),
            construction_graph=_load(fixture / "construction_graph.json"),
            material_wear_graph=_load(fixture / "material_wear_graph.json"),
        )

        assert min(scores.values()) >= 8


def test_quality_planner_has_no_sword_specific_crate_path() -> None:
    fixture = _QUALITY_ENGINE / "sci_fi_crate"
    plan = build_quality_plan(
        _load(fixture / "design_brief.json"),
        art_direction=_load(fixture / "art_direction.json"),
        family_grammar=_load(fixture / "family_grammar_coverage.json"),
        construction_graph=_load(fixture / "construction_graph.json"),
        material_wear_graph=_load(fixture / "material_wear_graph.json"),
    )

    assert "sword" not in json.dumps(plan, sort_keys=True).lower()
    assert plan["object_family"] == "container"


def test_quality_plan_validator_publishes_runtime_evidence() -> None:
    payload = evaluate_quality_plan(
        {"name": "roblox_dropper", "intent": {"parts": ["body", "button", "conveyor"]}},
        {
            "design_brief": {
                "brief": {
                    "asset_name": "roblox_dropper",
                    "family": "roblox_tycoon_machine",
                    "style_tags": ["roblox", "tycoon"],
                    "negative_constraints": ["tiny controls"],
                }
            },
            "family_grammar": {"coverage": 1.0, "required_rules": ["button"]},
            "construction_graph": {"nodes": [], "summary": {}},
        },
    )

    assert payload["schema_version"] == QUALITY_PLAN_VERSION
    assert payload["object_family"] == "machine"
    assert payload["diagnostics"] == []
