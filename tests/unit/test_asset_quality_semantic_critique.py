"""Phase 14C tests for semantic quality critique repair suggestions."""

from __future__ import annotations

from lathe.asset_quality.art_direction import QUALITY_DIMENSIONS
from lathe.asset_quality.semantic_critique import critique_quality_plan, repair_suggestions_for_scores


def test_each_low_quality_dimension_produces_actionable_repair() -> None:
    for dimension in QUALITY_DIMENSIONS:
        scores = {name: 1.0 for name in QUALITY_DIMENSIONS}
        scores["procedural_noise_penalty"] = 0.1
        scores[dimension] = 0.9 if dimension == "procedural_noise_penalty" else 0.2

        repairs = repair_suggestions_for_scores(scores, threshold=0.75)

        assert len(repairs) == 1
        repair = repairs[0]
        assert repair["dimension"] == dimension
        assert repair["severity"] == "warning"
        assert repair["target"]
        assert repair["evidence"]
        assert repair["repair"]
        assert "random regeneration" not in repair["repair"].lower()
        assert repair["preserve"]


def test_quality_plan_critique_is_empty_when_scores_are_good() -> None:
    payload = critique_quality_plan(
        {
            "asset_id": "good_asset",
            "metrics": {
                **{name: 0.9 for name in QUALITY_DIMENSIONS},
                "procedural_noise_penalty": 0.1,
            },
        }
    )

    assert payload["asset_id"] == "good_asset"
    assert payload["source_quality_plan"] == "quality_plan.json"
    assert payload["summary"]["status"] == "pass"
    assert payload["issue_count"] == 0
    assert payload["issues"] == []
    assert payload["repairs"] == []


def test_quality_plan_critique_preserves_identity_for_material_repair() -> None:
    payload = critique_quality_plan(
        {
            "asset_id": "low_material_asset",
            "metrics": {
                **{name: 0.9 for name in QUALITY_DIMENSIONS},
                "material_contrast": 0.2,
                "procedural_noise_penalty": 0.1,
            },
        }
    )

    assert payload["issue_count"] == 1
    assert payload == critique_quality_plan(
        {
            "asset_id": "low_material_asset",
            "metrics": {
                **{name: 0.9 for name in QUALITY_DIMENSIONS},
                "material_contrast": 0.2,
                "procedural_noise_penalty": 0.1,
            },
        }
    )
    repair = payload["issues"][0]
    assert repair["issue"] == "low_material_contrast"
    assert repair["target"] == "materials.zones"
    assert "material_wear_graph.json" in repair["evidence"]
    assert "material_roles" in repair["preserve"]
