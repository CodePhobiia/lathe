"""Phase 14C tests for universal art-direction IR."""

from __future__ import annotations

from lathe.asset_quality.art_direction import (
    ART_DIRECTION_DOCUMENT_VERSION,
    ART_DIRECTION_IR_VERSION,
    QUALITY_DIMENSIONS,
    build_art_direction_document,
    build_art_direction_ir,
    infer_object_family,
    normalize_art_direction,
    validate_art_direction_payload,
)


def test_art_direction_ir_normalizes_family_agnostic_style_and_platform() -> None:
    brief = {
        "asset_id": "shop_counter",
        "family": "environment_shop_counter",
        "style": {
            "theme": "warm fantasy shop counter",
            "keywords": ["shop", "environment", "cozy"],
            "forbidden": ["floating signage"],
        },
        "platform_profile": {
            "target": "realtime_environment_prop",
            "triangle_budget_warning": 4500,
            "triangle_budget_strict": 3000,
            "texture_budget": "proxy",
        },
        "required_features": ["usable counter surface", "raised shop sign"],
    }

    ir = build_art_direction_ir(brief)

    assert ir["schema_version"] == ART_DIRECTION_IR_VERSION
    assert ir["asset_id"] == "shop_counter"
    assert ir["object_family"] == "furniture"
    assert ir["platform"]["target"] == "realtime_environment_prop"
    assert ir["silhouette"]["thumbnail_size_px"] == 128
    assert "floating signage" in ir["forbidden_failure_modes"]
    assert "floating signage" in ir["forbidden_visual_failure_modes"]


def test_object_family_inference_is_not_weapon_specific() -> None:
    assert infer_object_family(family="sci_fi_crate", required_features=["corner guards"]) == "container"
    assert infer_object_family(family="roblox_tycoon_machine", required_features=["button"]) == "machine"
    assert infer_object_family(family="environment_shop_counter", required_features=["countertop"]) == "furniture"


def test_quality_dimensions_include_universal_scorecard() -> None:
    assert QUALITY_DIMENSIONS == (
        "silhouette_strength",
        "proportion_intent",
        "material_contrast",
        "detail_hierarchy",
        "motif_coherence",
        "surface_storytelling",
        "functional_readability",
        "style_consistency",
        "procedural_noise_penalty",
    )


def test_explicit_art_direction_document_normalizes_to_ir() -> None:
    brief = {
        "asset_id": "crate",
        "family": "sci_fi_crate",
        "style": {"theme": "sci-fi industrial", "keywords": ["sci-fi"], "forbidden": ["organic vines"]},
        "platform_profile": {"target": "realtime_proxy"},
        "required_features": ["corner guards", "latches"],
    }
    document = build_art_direction_document(brief)

    assert document["schema_version"] == ART_DIRECTION_DOCUMENT_VERSION
    assert validate_art_direction_payload(document) == []

    ir = normalize_art_direction(document, design_brief=brief)
    assert ir["schema_version"] == ART_DIRECTION_IR_VERSION
    assert ir["object_family"] == "container"
    assert "organic vines" in ir["forbidden_failure_modes"]


def test_art_direction_validation_rejects_missing_required_fields() -> None:
    issues = validate_art_direction_payload(
        {
            "schema_version": ART_DIRECTION_DOCUMENT_VERSION,
            "asset_id": "broken",
            "object_family": "prop",
        }
    )

    assert "style_intent" in issues
    assert "visual_hierarchy" in issues
    assert "forbidden_failure_modes" in issues


def test_art_direction_document_supports_all_quality_engine_families() -> None:
    fixtures = {
        "fantasy_weapon": "weapon",
        "sci_fi_crate": "container",
        "roblox_tycoon_machine": "machine",
        "environment_shop_counter": "furniture",
    }

    for family, object_family in fixtures.items():
        document = build_art_direction_document(
            {
                "asset_id": family,
                "family": family,
                "style": {"theme": family, "keywords": [family], "forbidden": ["random noise"]},
                "platform_profile": {"target": "realtime_proxy"},
                "required_features": [family],
            }
        )

        assert document["object_family"] == object_family
        assert validate_art_direction_payload(document) == []
