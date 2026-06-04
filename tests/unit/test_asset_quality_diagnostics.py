"""Phase 1 tests for ``lathe.asset_quality.diagnostics``.

Covers per task #1.10 of ``docs/asset-quality/improvement-tasklist.md``:

- payload shape / version field
- metrics are numeric floats
- each of the five warnings fires for a clearly-bad fixture
- no warnings fire for a clearly-good fixture
- missing optional runtime data does not crash
"""

from __future__ import annotations

from typing import Any

from lathe.asset_quality.diagnostics import (
    _RECOMMENDATIONS,
    VERSION,
    evaluate_quality_diagnostics,
)


def _runtime(
    *,
    visual_metrics: dict[str, Any] | None = None,
    shape_assessment: dict[str, Any] | None = None,
    highlow: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build a synthetic ``(asset, runtime)`` pair with sensible defaults.

    Each kwarg overrides one nested section. Defaults model an asset that
    is *clean* (clears all five warnings) so individual tests can dial a
    single section into a bad state to exercise one warning at a time.
    """
    asset = {
        "name": "diagnostics_fixture",
        "intent": {"parts": ["body", "lid", "handle_l", "handle_r", "foot_l", "foot_r"]},
        "build": {"shape": {"mode": "generate"}},
    }
    default_visual = {
        "geometry_tiny_face_penalty": 0.10,
        "geometry_stair_step_penalty": 0.10,
        "boolean_scar_penalty": 0.10,
        "texture_entropy": 0.70,
        "roughness_variation": 0.60,
        "surface_chroma_variation": 0.80,
        "attachment_integration_quality": 0.95,
        "feature_coherence": 0.90,
        "silhouette_complexity": 0.85,
        "detail_density": 0.90,
    }
    if visual_metrics:
        default_visual.update(visual_metrics)

    default_shape_assessment = {
        "feature_count": 80,
        "attachment_region_count": 5,
    }
    if shape_assessment:
        default_shape_assessment.update(shape_assessment)

    default_highlow = {
        "high_mesh_uri": "stages/shape/high.glb",
        "low_mesh_uri": "stages/topology/low.glb",
        "high_triangle_count": 5000,
        "low_triangle_count": 1000,
    }
    if highlow is not None:
        default_highlow = {**default_highlow, **highlow} if highlow else {}

    runtime = {
        "shape": {
            "bundle": {
                "shape_assessment": default_shape_assessment,
            }
        },
        "visual_quality": {"metrics": default_visual},
        "surface": {
            "bundle": {
                "surface_manifest": {"hero_surface": True},
                "highlow_relation": default_highlow,
            }
        },
    }
    return asset, runtime


def test_payload_shape_and_version() -> None:
    asset, runtime = _runtime()
    report = evaluate_quality_diagnostics(asset, runtime)

    assert report["version"] == VERSION
    assert VERSION == "asset_quality_diagnostics_v1"
    assert set(report.keys()) == {
        "version",
        "metrics",
        "warnings",
        "recommendations",
        "findings",
        "repair_routes",
        "render_class_validators",
    }
    assert isinstance(report["metrics"], dict)
    assert isinstance(report["warnings"], list)
    assert isinstance(report["recommendations"], list)
    assert isinstance(report["findings"], list)
    assert isinstance(report["repair_routes"], list)
    assert isinstance(report["render_class_validators"], dict)
    assert "diagnostics" not in report


def test_metrics_are_numeric_floats() -> None:
    asset, runtime = _runtime()
    report = evaluate_quality_diagnostics(asset, runtime)

    expected_phase1 = {
        "random_triangulation_penalty",
        "debug_material_preview_penalty",
        "highlow_fake_detail_penalty",
        "attachment_seating_quality",
        "primary_secondary_tertiary_balance",
        "family_grammar_coverage",
    }
    # Render-class validators (`lathe.validators.render_class`) merge their
    # per-validator scores into the diagnostics metrics dict so dashboards
    # surface every quality signal under one namespace.
    expected_render_class = {
        "box_stack_detector",
        "edge_density_variance",
        "curvature_distribution",
        "topology_class_compliance",
        "texel_density_consistency",
        "silhouette_multi_angle",
        "frequency_energy",
        "pbr_chart_compliance",
    }
    assert set(report["metrics"].keys()) == expected_phase1 | expected_render_class
    for key, value in report["metrics"].items():
        assert isinstance(value, int | float), f"{key!r} should be numeric"
        assert 0.0 <= float(value) <= 1.0, f"{key!r} out of [0,1]: {value}"


def test_clean_baseline_emits_no_warnings() -> None:
    asset, runtime = _runtime()
    report = evaluate_quality_diagnostics(asset, runtime)

    assert report["warnings"] == []
    assert report["recommendations"] == []


def test_noisy_triangulation_warning_fires() -> None:
    asset, runtime = _runtime(
        visual_metrics={
            "geometry_tiny_face_penalty": 0.65,
            "geometry_stair_step_penalty": 0.50,
            "boolean_scar_penalty": 0.45,
        }
    )
    report = evaluate_quality_diagnostics(asset, runtime)

    assert report["metrics"]["random_triangulation_penalty"] > 0.30
    assert any("noisy diagonal topology" in w for w in report["warnings"])
    assert any("panel lines" in r or "topology" in r for r in report["recommendations"])


def test_debug_material_preview_warning_fires() -> None:
    asset, runtime = _runtime(
        visual_metrics={
            "texture_entropy": 0.10,
            "roughness_variation": 0.05,
            "surface_chroma_variation": 0.10,
        }
    )
    report = evaluate_quality_diagnostics(asset, runtime)

    assert report["metrics"]["debug_material_preview_penalty"] > 0.50
    assert any("material-ID" in w or "debug" in w for w in report["warnings"])
    assert any("PBR" in r for r in report["recommendations"])


def test_fake_highlow_warning_fires_when_triangle_counts_match() -> None:
    asset, runtime = _runtime(
        highlow={
            "high_mesh_uri": "stages/shape/high.glb",
            "low_mesh_uri": "stages/topology/low.glb",
            "high_triangle_count": 1376,
            "low_triangle_count": 1376,
        }
    )
    report = evaluate_quality_diagnostics(asset, runtime)

    assert report["metrics"]["highlow_fake_detail_penalty"] > 0.40
    assert any("high-poly" in w or "high/low" in w for w in report["warnings"])
    assert any("high-poly source" in r for r in report["recommendations"])


def test_fake_highlow_warning_fires_when_uris_missing() -> None:
    asset, runtime = _runtime(highlow={})
    report = evaluate_quality_diagnostics(asset, runtime)

    assert report["metrics"]["highlow_fake_detail_penalty"] >= 0.99
    assert any("high-poly" in w or "high/low" in w for w in report["warnings"])


def test_nonhero_assets_do_not_receive_highlow_penalty() -> None:
    asset, runtime = _runtime(highlow={})
    asset["name"] = "generic_widget"
    runtime["surface"]["bundle"]["surface_manifest"]["hero_surface"] = False

    report = evaluate_quality_diagnostics(asset, runtime)

    assert report["metrics"]["highlow_fake_detail_penalty"] == 0.0
    assert not any("highlow_fake_detail_penalty" in w for w in report["warnings"])


def test_weak_attachment_seating_warning_fires() -> None:
    asset, runtime = _runtime(
        shape_assessment={"attachment_region_count": 0, "feature_count": 80},
        visual_metrics={
            "attachment_integration_quality": 0.20,
            "feature_coherence": 0.30,
        },
    )
    report = evaluate_quality_diagnostics(asset, runtime)

    assert report["metrics"]["attachment_seating_quality"] < 0.50
    assert any("stuck-on" in w or "under-integrated" in w for w in report["warnings"])
    assert any("socket" in r or "bracket" in r for r in report["recommendations"])


def test_weak_hierarchy_balance_warning_fires() -> None:
    asset, runtime = _runtime(
        shape_assessment={"feature_count": 6, "attachment_region_count": 5},
        visual_metrics={
            "silhouette_complexity": 0.30,
            "detail_density": 0.30,
        },
    )
    report = evaluate_quality_diagnostics(asset, runtime)

    assert report["metrics"]["primary_secondary_tertiary_balance"] < 0.50
    assert any(
        "medium-scale construction hierarchy" in w or "hierarchy" in w
        for w in report["warnings"]
    )
    assert any("medium-scale" in r or "frames" in r for r in report["recommendations"])


def test_missing_runtime_data_does_not_crash() -> None:
    asset = {"name": "minimal", "intent": {}, "build": {}}
    runtime: dict[str, Any] = {}

    report = evaluate_quality_diagnostics(asset, runtime)

    assert report["version"] == VERSION
    for value in report["metrics"].values():
        assert isinstance(value, int | float)
        assert 0.0 <= float(value) <= 1.0


def test_partial_runtime_data_does_not_crash() -> None:
    asset = {"name": "partial", "intent": {"parts": ["body"]}, "build": {}}
    runtime = {
        "shape": {"bundle": {}},
        "visual_quality": {"metrics": {"detail_density": 0.5}},
        "surface": {"bundle": {}},
    }

    report = evaluate_quality_diagnostics(asset, runtime)

    assert report["version"] == VERSION
    assert isinstance(report["warnings"], list)
    assert isinstance(report["recommendations"], list)


def test_warnings_and_recommendations_are_paired() -> None:
    asset, runtime = _runtime(highlow={})
    report = evaluate_quality_diagnostics(asset, runtime)

    assert len(report["warnings"]) == len(report["recommendations"])


def test_no_diagnostics_field_so_validator_pipeline_treats_as_passing() -> None:
    asset, runtime = _runtime(highlow={})
    report = evaluate_quality_diagnostics(asset, runtime)

    assert "diagnostics" not in report


def test_findings_pair_metric_to_recommendation_for_multiple_warnings() -> None:
    """Trigger all five warnings simultaneously and verify each finding's
    metric/severity/warning/recommendation are correctly paired.

    Catches a bug in which a developer accidentally swaps recommendations
    between metrics — the original ``test_warnings_and_recommendations_are_paired``
    only checks list lengths, not pairing correctness.
    """
    asset, runtime = _runtime(
        visual_metrics={
            "geometry_tiny_face_penalty": 0.65,
            "geometry_stair_step_penalty": 0.50,
            "boolean_scar_penalty": 0.45,
            "texture_entropy": 0.10,
            "roughness_variation": 0.05,
            "surface_chroma_variation": 0.10,
            "attachment_integration_quality": 0.20,
            "feature_coherence": 0.30,
            "silhouette_complexity": 0.30,
            "detail_density": 0.30,
        },
        shape_assessment={"feature_count": 6, "attachment_region_count": 0},
        highlow={},
    )
    report = evaluate_quality_diagnostics(asset, runtime)

    # ``findings`` now also carries render-class informational findings
    # (e.g. renderer-unavailable info notes). The pairing contract guarded
    # by this test applies to the Phase-1 warning-severity findings only.
    warning_findings = [f for f in report["findings"] if f.get("severity") == "warning"]

    assert {f["metric"] for f in warning_findings} == {
        "random_triangulation_penalty",
        "debug_material_preview_penalty",
        "highlow_fake_detail_penalty",
        "attachment_seating_quality",
        "primary_secondary_tertiary_balance",
    }

    for finding in warning_findings:
        assert finding["severity"] == "warning"
        assert finding["recommendation"] == _RECOMMENDATIONS[finding["metric"]]
        assert finding["metric"] in finding["warning"]

    assert len(report["warnings"]) == len(warning_findings)
    assert len(report["recommendations"]) == len(warning_findings)
    for i, finding in enumerate(warning_findings):
        assert report["warnings"][i] == finding["warning"]
        assert report["recommendations"][i] == finding["recommendation"]


def test_surface_chroma_variation_falls_back_to_texture_entropy_when_missing() -> None:
    """When ``surface_chroma_variation`` is absent from visual_quality.metrics,
    debug_material_preview_penalty must use ``texture_entropy`` as the chroma
    fallback per docs/asset-quality/quality-diagnostics-v1.md §3.2.
    """
    asset, runtime = _runtime(
        visual_metrics={
            "texture_entropy": 0.30,
            "roughness_variation": 0.30,
        }
    )
    del runtime["visual_quality"]["metrics"]["surface_chroma_variation"]

    report = evaluate_quality_diagnostics(asset, runtime)

    expected = round(
        min(
            1.0,
            0.40 * (1.0 - 0.30) + 0.35 * (1.0 - 0.30) + 0.25 * (1.0 - 0.30),
        ),
        6,
    )
    assert report["metrics"]["debug_material_preview_penalty"] == expected
