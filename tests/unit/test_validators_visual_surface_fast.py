from __future__ import annotations

from typing import Any

from lathe.validators.visual_quality import evaluate_visual_quality


def _runtime_with_surface(surface_bundle: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    asset = {
        "name": "surface_demo",
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
                        "semantic_requirements": {
                            "minimum_geometry_integration_quality": 0.0,
                            "minimum_surface_authoring_quality": 0.0,
                        }
                    },
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
        "surface": {"bundle": surface_bundle},
    }
    return asset, runtime


def test_malformed_surface_metadata_does_not_crash_in_fast_lane() -> None:
    asset, runtime = _runtime_with_surface(
        {
            "backend_id": "lathe.surface.semantic_passthrough_v1",
            "maps": None,
            "material_zones": [None, "not-a-zone"],
            "surface_manifest": None,
            "patterns": None,
            "decal_masks": None,
        }
    )

    report = evaluate_visual_quality(asset, runtime)

    assert report["metrics"]["surface_authoring_quality"] == 0.0
    assert "visual_surface_authoring_quality_failed" in {d["name"] for d in report["diagnostics"]}


def test_null_material_zones_surface_metadata_does_not_crash_in_fast_lane() -> None:
    asset, runtime = _runtime_with_surface(
        {
            "backend_id": "lathe.surface.semantic_passthrough_v1",
            "maps": ["basecolor", "normal"],
            "material_zones": None,
            "surface_manifest": {"maps": ["basecolor", "normal"], "workflow": "pbr_metal_rough"},
        }
    )

    report = evaluate_visual_quality(asset, runtime)

    assert "surface_authoring_quality" in report["metrics"]
