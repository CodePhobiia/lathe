"""Unit tests for ``lathe.validators.visual_quality.evaluate_visual_quality``.

Covers the per-metric threshold branches and the penalty-metric branches.
The broader positive + near-miss corpus lives at
``tests/test_visual_quality.py``.
"""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

import pytest
import trimesh
from lathe.core.mesh import RuntimeMesh
from lathe.executor import build_asset
from lathe.parser import parse_file
from lathe.validators.semantic_quality import evaluate_semantic_quality
from lathe.validators.visual_quality import evaluate_visual_quality

REPO_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.slow
_BUILT: dict[str, Any] | None = None


def _build_courier_drone() -> dict[str, Any]:
    """One-shot cached build; returns baseline asset+runtime state."""
    global _BUILT
    if _BUILT is not None:
        return _BUILT
    program = parse_file(REPO_ROOT / "examples" / "courier_drone.lth")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "courier_drone"
        build_asset(program, "courier_drone", out)
        shape_bundle = json.loads((out / "stages" / "shape" / "bundle.json").read_text(encoding="utf-8"))
        topology_bundle = json.loads(
            (out / "stages" / "topology" / "bundle.json").read_text(encoding="utf-8")
        )
        interfaces_bundle = json.loads(
            (out / "stages" / "interfaces" / "bundle.json").read_text(encoding="utf-8")
        )
        surface_bundle = json.loads((out / "stages" / "surface" / "bundle.json").read_text(encoding="utf-8"))
        asset = json.loads((out / "materialized_asset.json").read_text(encoding="utf-8"))
        validate_report = json.loads(
            (out / "stages" / "validate" / "report.json").read_text(encoding="utf-8")
        )
        mesh_uri = topology_bundle.get("mesh_uri", "stages/topology/topology.glb")
        mesh_path = out / mesh_uri
        mesh_obj = trimesh.load(mesh_path, force="mesh")
        default_part = topology_bundle.get("part_groups", [{}])[0].get("name", "mesh")
        runtime_mesh = RuntimeMesh(
            mesh=mesh_obj,
            face_parts=[default_part] * len(mesh_obj.faces),
            part_colors={default_part: (128, 128, 128)},
            units="cm",
        )
        surface_stage_dir = out / "stages" / "surface"
        # Stage_dir lives outside tmp so we copy what we need: but stage_dir is
        # only used to resolve surface maps. Keep a lightweight reference — the
        # tempdir is torn down below, so null it out; the validator handles
        # missing image maps by returning zeroed surface evidence.
        _ = surface_stage_dir
    _BUILT = {
        "asset": asset,
        "runtime": {
            "shape": {"bundle": shape_bundle},
            "topology": {"bundle": topology_bundle, "runtime_mesh": runtime_mesh},
            "interfaces": {"bundle": interfaces_bundle},
            "surface": {"bundle": surface_bundle},
        },
        "validate_report": validate_report,
    }
    return _BUILT


def _baseline() -> tuple[dict[str, Any], dict[str, Any]]:
    built = _build_courier_drone()
    asset = copy.deepcopy(built["asset"])
    # trimesh objects can't be deep-copied cheaply; share the reference
    # since no test mutates the actual mesh.
    runtime = {
        "shape": copy.deepcopy(built["runtime"]["shape"]),
        "topology": {
            "bundle": copy.deepcopy(built["runtime"]["topology"]["bundle"]),
            "runtime_mesh": built["runtime"]["topology"]["runtime_mesh"],
        },
        "interfaces": copy.deepcopy(built["runtime"]["interfaces"]),
        "surface": copy.deepcopy(built["runtime"]["surface"]),
    }
    runtime["semantic_quality"] = evaluate_semantic_quality(asset, runtime)
    return asset, runtime


class VisualQualityCertifiedTests(unittest.TestCase):
    def test_courier_drone_has_no_error_diagnostics_on_reference_build(self) -> None:
        # Use the on-disk report so we verify the stable outcome of a real
        # build, not a minimal reconstruction.
        report = _build_courier_drone()["validate_report"]["visual_quality"]
        self.assertEqual([d for d in report["diagnostics"] if d.get("severity") == "error"], [])
        self.assertGreaterEqual(report["metrics"]["detail_density"], report["thresholds"]["detail_density"])

    def test_large_positive_margin_on_reference_build_still_certifies(self) -> None:
        report = _build_courier_drone()["validate_report"]["visual_quality"]
        for metric_key in (
            "detail_density",
            "silhouette_complexity",
            "edge_readability",
            "feature_coherence",
        ):
            margin = report["metrics"][metric_key] - report["thresholds"][metric_key]
            self.assertGreater(margin, 0.0, f"{metric_key} should clear threshold with a margin")


class VisualQualityRejectsBadBundleTests(unittest.TestCase):
    def test_silhouette_complexity_failure_emitted_when_assessment_flat(self) -> None:
        asset, runtime = _baseline()
        scaffold = runtime["shape"]["bundle"]["scaffold_report"]
        scaffold["shape_assessment"]["silhouette_complexity"] = 0.0
        scaffold["shape_assessment"]["feature_coherence"] = 0.0
        runtime["shape"]["bundle"]["shape_assessment"]["silhouette_complexity"] = 0.0
        runtime["shape"]["bundle"]["shape_assessment"]["feature_coherence"] = 0.0
        # Also knock semantic silhouette_fidelity down so rollup fails.
        runtime["semantic_quality"]["metrics"]["silhouette_fidelity"] = 0.0
        report = evaluate_visual_quality(asset, runtime)
        names = {d["name"] for d in report["diagnostics"]}
        self.assertIn("visual_silhouette_complexity_failed", names)
        self.assertLess(
            report["metrics"]["silhouette_complexity"], report["thresholds"]["silhouette_complexity"]
        )

    def test_edge_readability_fails_when_edge_treatment_count_zeroed(self) -> None:
        asset, runtime = _baseline()
        scaffold = runtime["shape"]["bundle"]["scaffold_report"]
        scaffold["shape_assessment"]["edge_treatment_count"] = 0
        runtime["shape"]["bundle"]["shape_assessment"]["edge_treatment_count"] = 0
        # Drive detail_density / render shading variance down too so the rollup drops.
        stats = runtime["topology"]["bundle"]["mesh_stats"]
        stats["triangle_count"] = 1
        scaffold["shape_assessment"]["feature_count"] = 0
        runtime["shape"]["bundle"]["shape_assessment"]["feature_count"] = 0
        report = evaluate_visual_quality(asset, runtime)
        names = {d["name"] for d in report["diagnostics"]}
        self.assertIn("visual_edge_readability_failed", names)
        self.assertLess(report["metrics"]["edge_readability"], report["thresholds"]["edge_readability"])

    def test_geometry_integration_zeroed_when_runtime_mesh_empty(self) -> None:
        asset, runtime = _baseline()
        runtime["topology"]["runtime_mesh"] = None
        report = evaluate_visual_quality(asset, runtime)
        self.assertEqual(report["metrics"]["geometry_integration_quality"], 0.0)
        names = {d["name"] for d in report["diagnostics"]}
        self.assertIn("visual_geometry_integration_quality_failed", names)

    def test_generated_zero_surface_quality_fails_even_with_zero_contract_default(self) -> None:
        asset, runtime = _baseline()
        requirements = runtime["shape"]["bundle"]["scaffold_report"]["asset_graph"]["semantic_requirements"]
        requirements["minimum_surface_authoring_quality"] = 0.0
        requirements["minimum_geometry_integration_quality"] = 0.0
        runtime["surface"] = {
            "bundle": {
                "backend_id": "lathe.surface.semantic_passthrough_v1",
                "maps": [],
                "material_zones": [],
                "surface_manifest": {"hero_surface": False, "maps": []},
            }
        }

        report = evaluate_visual_quality(asset, runtime)

        self.assertEqual(report["metrics"]["surface_authoring_quality"], 0.0)
        self.assertGreater(report["thresholds"]["surface_authoring_quality"], 0.0)
        diagnostics = {d["name"]: d for d in report["diagnostics"]}
        self.assertIn("visual_surface_authoring_quality_failed", diagnostics)
        details = diagnostics["visual_surface_authoring_quality_failed"]["details"]
        self.assertEqual(details["surface_backend_id"], "lathe.surface.semantic_passthrough_v1")
        self.assertEqual(details["surface_material_zone_count"], 0)

    def test_non_hero_surface_metadata_produces_authoring_evidence(self) -> None:
        asset, runtime = _baseline()
        requirements = runtime["shape"]["bundle"]["scaffold_report"]["asset_graph"]["semantic_requirements"]
        requirements["minimum_surface_authoring_quality"] = 0.0
        requirements["minimum_geometry_integration_quality"] = 0.0
        surface_bundle = runtime["surface"]["bundle"]
        surface_bundle["backend_id"] = "lathe.surface.semantic_passthrough_v1"
        surface_bundle.pop("outputs", None)
        surface_bundle.pop("surface_control_pack", None)
        surface_bundle.pop("highlow_relation", None)

        report = evaluate_visual_quality(asset, runtime)

        self.assertGreater(report["metrics"]["surface_authoring_quality"], 0.0)
        self.assertGreaterEqual(
            report["metrics"]["surface_authoring_quality"],
            report["thresholds"]["surface_authoring_quality"],
        )
        self.assertNotIn(
            "visual_surface_authoring_quality_failed", {d["name"] for d in report["diagnostics"]}
        )

    def test_malformed_surface_metadata_does_not_crash(self) -> None:
        asset, runtime = _baseline()
        requirements = runtime["shape"]["bundle"]["scaffold_report"]["asset_graph"]["semantic_requirements"]
        requirements["minimum_surface_authoring_quality"] = 0.0
        requirements["minimum_geometry_integration_quality"] = 0.0
        runtime["surface"] = {
            "bundle": {
                "backend_id": "lathe.surface.semantic_passthrough_v1",
                "maps": None,
                "material_zones": [None, "not-a-zone"],
                "surface_manifest": None,
                "patterns": None,
                "decal_masks": None,
            }
        }

        report = evaluate_visual_quality(asset, runtime)

        self.assertEqual(report["metrics"]["surface_authoring_quality"], 0.0)
        self.assertIn("visual_surface_authoring_quality_failed", {d["name"] for d in report["diagnostics"]})

    def test_null_material_zones_surface_metadata_does_not_crash(self) -> None:
        asset, runtime = _baseline()
        requirements = runtime["shape"]["bundle"]["scaffold_report"]["asset_graph"]["semantic_requirements"]
        requirements["minimum_surface_authoring_quality"] = 0.0
        requirements["minimum_geometry_integration_quality"] = 0.0
        runtime["surface"]["bundle"]["material_zones"] = None

        report = evaluate_visual_quality(asset, runtime)

        self.assertIn("surface_authoring_quality", report["metrics"])

    def test_detail_density_fails_on_impoverished_mesh(self) -> None:
        asset, runtime = _baseline()
        stats = runtime["topology"]["bundle"]["mesh_stats"]
        stats["triangle_count"] = 1
        scaffold = runtime["shape"]["bundle"]["scaffold_report"]
        scaffold["shape_assessment"]["feature_count"] = 0
        scaffold["shape_assessment"]["feature_coherence"] = 0.0
        runtime["shape"]["bundle"]["shape_assessment"]["feature_count"] = 0
        runtime["shape"]["bundle"]["shape_assessment"]["feature_coherence"] = 0.0
        report = evaluate_visual_quality(asset, runtime)
        names = {d["name"] for d in report["diagnostics"]}
        self.assertIn("visual_detail_density_failed", names)

    def test_support_plausibility_drops_when_supports_are_flat_faces(self) -> None:
        asset, runtime = _baseline()
        for group in runtime["topology"]["bundle"]["part_groups"]:
            if "leg" in group["name"]:
                group["face_count"] = 2
                # Lift the leg away from the floor.
                group["bounds_min"] = [100.0, 100.0, 100.0]
                group["bounds_max"] = [101.0, 101.0, 101.0]
        scaffold = runtime["shape"]["bundle"]["scaffold_report"]
        scaffold["shape_assessment"]["support_feature_count"] = 0
        runtime["shape"]["bundle"]["shape_assessment"]["support_feature_count"] = 0
        report = evaluate_visual_quality(asset, runtime)
        names = {d["name"] for d in report["diagnostics"]}
        self.assertIn("visual_support_plausibility_failed", names)

    def test_primitive_likeness_penalty_exceeds_max_when_features_collapse(self) -> None:
        asset, runtime = _baseline()
        # Zero every positive-signal input so the penalty rises to ~1.0.
        runtime["semantic_quality"]["metrics"].update(
            {"silhouette_fidelity": 0.0, "structural_richness": 0.0, "adjacency_score": 0.0}
        )
        scaffold = runtime["shape"]["bundle"]["scaffold_report"]
        scaffold["shape_assessment"].update(
            {
                "feature_coherence": 0.0,
                "silhouette_complexity": 0.0,
                "feature_count": 0,
                "edge_treatment_count": 0,
                "attachment_region_count": 0,
            }
        )
        runtime["shape"]["bundle"]["shape_assessment"].update(
            {
                "feature_coherence": 0.0,
                "silhouette_complexity": 0.0,
                "feature_count": 0,
                "edge_treatment_count": 0,
                "attachment_region_count": 0,
            }
        )
        runtime["topology"]["bundle"]["mesh_stats"]["triangle_count"] = 1
        report = evaluate_visual_quality(asset, runtime)
        names = {d["name"] for d in report["diagnostics"]}
        self.assertIn("visual_primitive_likeness_penalty_failed", names)
        self.assertGreater(
            report["metrics"]["primitive_likeness_penalty"],
            report["thresholds"]["maximum_primitive_likeness_penalty"],
        )


if __name__ == "__main__":
    unittest.main()
