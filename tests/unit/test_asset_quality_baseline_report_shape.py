"""Phase 0 baseline contract tests for the certification report shape.

These tests lock the **set of keys** present at the v0.2.0rc1 baseline
(commit ``e94a202``) so the asset-quality upgrade phases described in
``docs/asset-quality/improvement-tasklist.md`` cannot silently remove or
rename fields downstream consumers depend on.

Additive growth is explicitly allowed: a new top-level key on the
certification report (e.g. ``quality_diagnostics`` introduced in Phase 1)
or a new entry inside ``visual_quality.metrics`` does not fail these
tests. Only **removal** or **renaming** of an existing key fails.

Companion document: ``docs/asset-quality/baseline-evidence.md`` Section 7.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from lathe.validators.visual_quality import evaluate_visual_quality


_REPO_ROOT = Path(__file__).resolve().parents[2]


_VISUAL_QUALITY_REQUIRED_KEYS: frozenset[str] = frozenset(
    {
        "family",
        "blueprint_id",
        "metrics",
        "thresholds",
        "diagnostics",
        "render_report",
    }
)


_VISUAL_QUALITY_METRICS_BASELINE_KEYS: frozenset[str] = frozenset(
    {
        "detail_density",
        "silhouette_complexity",
        "edge_readability",
        "attachment_integration_quality",
        "support_plausibility",
        "feature_coherence",
        "geometry_integration_quality",
        "surface_authoring_quality",
        "primitive_likeness_penalty",
        "assembled_primitives_penalty",
        "render_silhouette_complexity",
        "render_primitive_penalty",
        "render_assembly_artifact_penalty",
        "render_shading_variance",
        "bevel_continuity",
        "seam_quality",
        "stair_step_penalty",
        "boolean_scar_penalty",
        "shading_continuity",
        "geometry_dihedral_continuity",
        "geometry_feature_edge_persistence",
        "geometry_stair_step_penalty",
        "geometry_tiny_face_penalty",
        "texture_entropy",
        "normal_richness",
        "roughness_variation",
        "material_zone_coherence",
        "decal_coherence",
        "bake_cleanliness",
        "highlow_distinction_quality",
        "surface_texture_entropy",
        "surface_chroma_variation",
        "surface_normal_richness",
        "surface_roughness_variation",
        "surface_bake_cleanliness",
        "surface_material_zone_coherence",
        "surface_emissive_coherence",
        "surface_highlow_realness",
        "surface_authoring_quality",
    }
)


_VALIDATE_REPORT_REQUIRED_KEYS: frozenset[str] = frozenset(
    {
        "certified",
        "threshold",
        "score",
        "semantic_quality",
        "visual_quality",
        "flow_quality",
        "geometry_integrity",
        "urdf_validation",
        "rule_results",
        "diagnostics",
        "repair_policy",
        "repair_suggestions",
        "failure_summary",
        "semantic_repairs_applied",
        "reselection_attempts",
        "quality_diagnostics",
        "design_brief",
        "family_grammar",
        "construction_graph",
        "grammar_lowering",
        "highlow_relation",
        "material_wear_graph",
        "preview_evidence",
    }
)


def _mock_runtime() -> tuple[dict[str, Any], dict[str, Any]]:
    """Build a minimal mocked ``(asset, runtime)`` pair.

    Mirrors the fixture pattern in
    ``tests/unit/test_validators_visual_surface_fast.py`` so the contract
    test does not require a full build.
    """
    asset = {
        "name": "asset_quality_baseline",
        "intent": {"parts": ["body"]},
        "build": {"shape": {"mode": "generate"}},
    }
    shape_assessment = {
        "feature_count": 8,
        "feature_coherence": 1.0,
        "silhouette_complexity": 1.0,
        "edge_treatment_count": 8,
        "attachment_region_count": 2,
        "support_feature_count": 0,
    }
    runtime = {
        "shape": {
            "bundle": {
                "shape_assessment": shape_assessment,
                "scaffold_report": {
                    "shape_assessment": shape_assessment,
                    "asset_graph": {
                        "family": "asset_quality_baseline",
                        "semantic_requirements": {
                            "minimum_geometry_integration_quality": 0.0,
                            "minimum_surface_authoring_quality": 0.0,
                        },
                    },
                    "blueprint_id": "lathe.blueprint.test_baseline_v0",
                },
            }
        },
        "topology": {
            "bundle": {
                "mesh_stats": {
                    "triangle_count": 360,
                    "bounds_min": [0.0, 0.0, 0.0],
                    "extents": [1.0, 1.0, 1.0],
                },
                "part_groups": [],
            },
            "runtime_mesh": None,
        },
        "semantic_quality": {
            "metrics": {
                "silhouette_fidelity": 1.0,
                "adjacency_score": 1.0,
                "structural_richness": 1.0,
                "symmetry_score": 1.0,
            }
        },
        "render_eval": {
            "report": {
                "metrics": {
                    "render_silhouette_complexity": 1.0,
                    "render_primitive_penalty": 0.0,
                    "render_assembly_artifact_penalty": 0.0,
                    "render_shading_variance": 1.0,
                }
            }
        },
        "surface": {
            "bundle": {
                "backend_id": "lathe.surface.semantic_passthrough_v1",
                "maps": ["basecolor", "normal", "orm", "ao"],
                "material_zones": [{"material": "metal", "part": "body"}],
                "surface_manifest": {"workflow": "pbr_metal_rough"},
            }
        },
    }
    return asset, runtime


def test_visual_quality_report_top_level_shape_is_stable() -> None:
    """The top-level ``visual_quality`` report keys must remain a superset
    of the v0.2.0rc1 baseline so additive Phase 1+ work cannot accidentally
    drop existing fields."""
    asset, runtime = _mock_runtime()
    report = evaluate_visual_quality(asset, runtime)

    missing = _VISUAL_QUALITY_REQUIRED_KEYS - report.keys()
    assert (
        not missing
    ), f"visual_quality report dropped required keys: {sorted(missing)}"


def test_visual_quality_metrics_remain_a_superset_of_baseline() -> None:
    """``visual_quality.metrics`` must keep all keys present at baseline.
    New metrics may be added; existing metrics may not be removed."""
    asset, runtime = _mock_runtime()
    report = evaluate_visual_quality(asset, runtime)

    missing = _VISUAL_QUALITY_METRICS_BASELINE_KEYS - report["metrics"].keys()
    assert (
        not missing
    ), f"visual_quality.metrics dropped baseline keys: {sorted(missing)}"


@pytest.mark.skipif(
    not (_REPO_ROOT / ".tmp_tests" / "baseline_industrial_crate").exists()
    or not (
        _REPO_ROOT
        / ".tmp_tests"
        / "baseline_industrial_crate"
        / "industrial_crate"
        / "stages"
        / "validate"
        / "report.json"
    ).exists(),
    reason=(
        "Run `python -m lathe.cli build examples/industrial_crate.lth "
        "industrial_crate --out .tmp_tests/baseline_industrial_crate "
        "--deterministic` to enable this contract check."
    ),
)
def test_validate_report_top_level_keys_match_baseline_contract() -> None:
    """Optional integration-level contract: the validate stage's
    ``report.json`` must remain a superset of the v0.2.0rc1 baseline keys.
    Skipped automatically if no baseline build exists in ``.tmp_tests/``."""
    report_path = (
        _REPO_ROOT
        / ".tmp_tests"
        / "baseline_industrial_crate"
        / "industrial_crate"
        / "stages"
        / "validate"
        / "report.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))

    missing = _VALIDATE_REPORT_REQUIRED_KEYS - report.keys()
    assert (
        not missing
    ), f"validate report dropped required keys: {sorted(missing)}"


def test_visual_quality_diagnostics_field_is_a_list() -> None:
    """Diagnostics is consumed by the validator pipeline composition layer
    as a list. Lock the type so additive changes preserve this contract."""
    asset, runtime = _mock_runtime()
    report = evaluate_visual_quality(asset, runtime)

    assert isinstance(report["diagnostics"], list)


def test_visual_quality_metrics_field_is_a_dict_of_floats() -> None:
    """``metrics`` is a flat dict of floats at baseline. Phase 1+ may add
    nested structures under new keys, but the existing keys must remain
    flat numeric values."""
    asset, runtime = _mock_runtime()
    report = evaluate_visual_quality(asset, runtime)

    assert isinstance(report["metrics"], dict)
    for key in _VISUAL_QUALITY_METRICS_BASELINE_KEYS:
        if key not in report["metrics"]:
            continue
        value = report["metrics"][key]
        assert isinstance(
            value, int | float
        ), f"visual_quality.metrics[{key!r}] should be numeric, got {type(value).__name__}"
