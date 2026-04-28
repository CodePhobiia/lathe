"""Unit tests for ``lathe.validators.flow_quality.evaluate_flow_quality``.

The flow validator branches on ``asset.build.shape.mode`` — each mode
(``generate``/``adapt``/``assemble``/``reconstruct``) produces a distinct
metric set. These tests exercise each branch with a minimal synthesized
asset+runtime, then verify per-metric diagnostic codes and graceful empty
behavior.
"""

from __future__ import annotations

import unittest
from typing import Any

from lathe.validators.flow_quality import evaluate_flow_quality


def _base_asset(mode: str) -> dict[str, Any]:
    return {
        "name": "unit_flow_asset",
        "build": {
            "shape": {"mode": mode},
            "optimize": {"lods": True, "draw_calls": True, "texture_budget": True},
        },
        "intent": {"parts": ["a", "b"]},
        "transfer": {
            "resolved_adapt_policy": {
                "name": "p1",
                "values": {"preserve": ["silhouette", "interfaces", "part_a", "part_b"]},
            },
            "resolved_transfer_rules": [{"from": "src", "to": "dst"}, {"from": "a", "to": "b"}],
        },
        "assembly": {
            "components": ["mod_a", "mod_b"],
            "resolved_kit": {
                "name": "kit1",
                "values": {
                    "modules": ["mod_a", "mod_b"],
                    "snap_grid": True,
                    "allowed_joins": ["socket", "bolt", "weld"],
                },
            },
        },
        "constraints": {
            "resolved_assembly_policy": {
                "name": "pol1",
                "values": {"allow": ["socket", "bolt"], "clearance": 0.5, "snap_grid": True},
            },
        },
        "refs": {
            "resolved_reference_sets": [{"name": "ref1"}],
            "images": ["a.png", "b.png"],
            "meshes": ["m.glb"],
        },
        "fit": {
            "resolved_reconstruct_policy": {"name": "rec1"},
            "resolved_fit_profile": {"name": "fit1"},
        },
        "validate": {"threshold": 0.8},
    }


def _good_runtime(mode: str) -> dict[str, Any]:
    semantic = {
        "part_coverage": 1.0,
        "silhouette_fidelity": 0.95,
        "symmetry_score": 0.9,
        "interface_score": 0.9,
        "adjacency_score": 0.95,
        "structural_richness": 0.9,
    }
    visual = {
        "surface_authoring_quality": 0.9,
        "surface_material_zone_coherence": 0.9,
        "support_plausibility": 0.9,
        "attachment_integration_quality": 0.9,
        "seam_quality": 0.9,
    }
    conditioning = {"reference_strength": 1.0, "image_refs": ["a", "b"], "mesh_refs": ["m"]}
    return {
        "semantic_quality": {"metrics": semantic},
        "visual_quality": {"metrics": visual},
        "shape": {"bundle": {"conditioning_report": conditioning}},
    }


class FlowQualityCertifiedTests(unittest.TestCase):
    def test_reconstruct_flow_with_strong_evidence_emits_no_diagnostics(self) -> None:
        asset = _base_asset("reconstruct")
        runtime = _good_runtime("reconstruct")
        report = evaluate_flow_quality(asset, runtime)
        self.assertEqual(report["mode"], "reconstruct")
        self.assertEqual(report["diagnostics"], [])
        self.assertGreaterEqual(
            report["metrics"]["reconstruct_honesty_score"],
            report["thresholds"]["reconstruct_honesty_score"],
        )

    def test_assemble_flow_with_kit_and_policy_emits_no_diagnostics(self) -> None:
        asset = _base_asset("assemble")
        runtime = _good_runtime("assemble")
        report = evaluate_flow_quality(asset, runtime)
        self.assertEqual(report["mode"], "assemble")
        self.assertEqual(report["diagnostics"], [])
        self.assertGreaterEqual(report["metrics"]["join_legality"], report["thresholds"]["join_legality"])

    def test_generate_mode_bypasses_flow_checks(self) -> None:
        asset = _base_asset("generate")
        runtime = _good_runtime("generate")
        report = evaluate_flow_quality(asset, runtime)
        self.assertEqual(report["mode"], "generate")
        self.assertEqual(report["metrics"], {})
        self.assertEqual(report["diagnostics"], [])


class FlowQualityRejectsBadBundleTests(unittest.TestCase):
    def test_assemble_join_legality_fails_without_kit_or_policy(self) -> None:
        asset = _base_asset("assemble")
        asset["assembly"] = {}
        asset["constraints"] = {}
        runtime = _good_runtime("assemble")
        runtime["semantic_quality"]["metrics"]["adjacency_score"] = 0.0
        report = evaluate_flow_quality(asset, runtime)
        names = {d["name"] for d in report["diagnostics"]}
        self.assertIn("flow_join_legality_failed", names)
        self.assertLess(report["metrics"]["join_legality"], report["thresholds"]["join_legality"])

    def test_reconstruct_honesty_score_fails_when_evidence_absent(self) -> None:
        asset = _base_asset("reconstruct")
        asset["refs"] = {}
        asset["fit"] = {}
        asset["validate"] = {}
        runtime = _good_runtime("reconstruct")
        runtime["shape"]["bundle"]["conditioning_report"] = {
            "reference_strength": 0.0,
            "image_refs": [],
            "mesh_refs": [],
        }
        runtime["semantic_quality"]["metrics"] = {k: 0.0 for k in runtime["semantic_quality"]["metrics"]}
        report = evaluate_flow_quality(asset, runtime)
        names = {d["name"] for d in report["diagnostics"]}
        self.assertIn("flow_reconstruct_honesty_score_failed", names)
        self.assertLess(
            report["metrics"]["reconstruct_honesty_score"],
            report["thresholds"]["reconstruct_honesty_score"],
        )

    def test_adapt_semantic_preservation_fails_when_metrics_zeroed(self) -> None:
        asset = _base_asset("adapt")
        asset["transfer"]["resolved_adapt_policy"] = {}
        asset["transfer"]["resolved_transfer_rules"] = []
        runtime = _good_runtime("adapt")
        runtime["semantic_quality"]["metrics"] = {k: 0.0 for k in runtime["semantic_quality"]["metrics"]}
        runtime["visual_quality"]["metrics"] = {k: 0.0 for k in runtime["visual_quality"]["metrics"]}
        report = evaluate_flow_quality(asset, runtime)
        names = {d["name"] for d in report["diagnostics"]}
        self.assertIn("flow_semantic_preservation_quality_failed", names)
        self.assertLess(
            report["metrics"]["semantic_preservation_quality"],
            report["thresholds"]["semantic_preservation_quality"],
        )

    def test_generate_vs_reconstruct_produce_different_metric_keysets(self) -> None:
        asset = _base_asset("reconstruct")
        runtime = _good_runtime("reconstruct")
        recon = evaluate_flow_quality(asset, runtime)
        gen_asset = _base_asset("generate")
        gen = evaluate_flow_quality(gen_asset, runtime)
        self.assertNotEqual(set(recon["metrics"].keys()), set(gen["metrics"].keys()))
        self.assertIn("reconstruct_honesty_score", recon["metrics"])
        self.assertEqual(gen["metrics"], {})

    def test_diagnostic_carries_mode_and_suggested_repairs(self) -> None:
        asset = _base_asset("reconstruct")
        asset["refs"] = {}
        asset["fit"] = {}
        runtime = _good_runtime("reconstruct")
        runtime["shape"]["bundle"]["conditioning_report"] = {
            "reference_strength": 0.0,
            "image_refs": [],
            "mesh_refs": [],
        }
        runtime["semantic_quality"]["metrics"] = {k: 0.0 for k in runtime["semantic_quality"]["metrics"]}
        report = evaluate_flow_quality(asset, runtime)
        self.assertTrue(report["diagnostics"])
        for diag in report["diagnostics"]:
            self.assertEqual(diag["severity"], "error")
            self.assertEqual(diag["details"]["mode"], "reconstruct")
            self.assertTrue(diag["path"].startswith("validate.flow."))
            self.assertIsInstance(diag.get("suggested_repairs", []), list)
            self.assertTrue(diag["suggested_repairs"])

    def test_unknown_mode_returns_empty_graceful(self) -> None:
        asset = _base_asset("weird_nonexistent_mode")
        runtime = _good_runtime("weird_nonexistent_mode")
        report = evaluate_flow_quality(asset, runtime)
        self.assertEqual(report["metrics"], {})
        self.assertEqual(report["diagnostics"], [])
        self.assertEqual(report["thresholds"], {})


if __name__ == "__main__":
    unittest.main()
