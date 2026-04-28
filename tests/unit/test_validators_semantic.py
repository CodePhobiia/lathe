"""Unit tests for ``lathe.validators.semantic_quality.evaluate_semantic_quality``.

Exercises per-rule diagnostic emission by mutating a fully-built
``courier_drone`` runtime bundle. The heavier integration corpus remains at
``tests/test_semantic_quality.py``.
"""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

import pytest
from lathe.executor import build_asset
from lathe.parser import parse_file
from lathe.validators.semantic_quality import evaluate_semantic_quality

REPO_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.slow
_BUILT: dict[str, Any] | None = None


def _build_courier_drone() -> dict[str, Any]:
    """Run a single cached ``build_asset`` and reconstruct a runtime-ish bundle.

    Returns a dict with ``asset`` (materialized) and ``runtime`` (the stage
    bundles + synthesized semantic/visual metrics). The returned object is a
    deep-copy-safe baseline; tests deep-copy before mutating.
    """
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
        asset = json.loads((out / "materialized_asset.json").read_text(encoding="utf-8"))
    _BUILT = {
        "asset": asset,
        "runtime": {
            "shape": {"bundle": shape_bundle},
            "topology": {"bundle": topology_bundle},
            "interfaces": {"bundle": interfaces_bundle},
        },
    }
    return _BUILT


def _baseline() -> tuple[dict[str, Any], dict[str, Any]]:
    built = _build_courier_drone()
    return copy.deepcopy(built["asset"]), copy.deepcopy(built["runtime"])


class SemanticQualityCertifiedTests(unittest.TestCase):
    def test_courier_drone_bundle_emits_no_error_diagnostics(self) -> None:
        asset, runtime = _baseline()
        report = evaluate_semantic_quality(asset, runtime)
        error_diags = [d for d in report["diagnostics"] if d.get("severity") == "error"]
        self.assertEqual(error_diags, [], f"unexpected errors: {error_diags}")
        self.assertGreaterEqual(report["metrics"]["part_coverage"], report["thresholds"]["part_coverage"])
        self.assertGreaterEqual(
            report["metrics"]["structural_richness"], report["thresholds"]["structural_richness"]
        )
        self.assertFalse(report["metrics"]["toy_detected"])


class SemanticQualityRejectsBadBundleTests(unittest.TestCase):
    def test_missing_required_part_emits_part_coverage_diagnostic(self) -> None:
        asset, runtime = _baseline()
        # Drop a required part group so part_coverage drops below threshold.
        groups = runtime["topology"]["bundle"]["part_groups"]
        runtime["topology"]["bundle"]["part_groups"] = [g for g in groups if g["name"] != "body"][:1]
        report = evaluate_semantic_quality(asset, runtime)
        names = {d["name"] for d in report["diagnostics"]}
        self.assertIn("semantic_part_coverage_failed", names)
        self.assertLess(report["metrics"]["part_coverage"], report["thresholds"]["part_coverage"])

    def test_silhouette_fidelity_collapses_when_extents_diverge(self) -> None:
        asset, runtime = _baseline()
        stats = runtime["topology"]["bundle"]["mesh_stats"]
        # Wildly wrong extents force silhouette ratio compare to collapse.
        stats["extents"] = [1.0, 900.0, 1.0]
        stats["bounds_min"] = [-0.5, -450.0, -0.5]
        stats["bounds_max"] = [0.5, 450.0, 0.5]
        report = evaluate_semantic_quality(asset, runtime)
        names = {d["name"] for d in report["diagnostics"]}
        self.assertIn("semantic_silhouette_fidelity_failed", names)
        self.assertLess(report["metrics"]["silhouette_fidelity"], report["thresholds"]["silhouette_fidelity"])

    def test_adjacency_score_fails_when_pairs_split_apart(self) -> None:
        asset, runtime = _baseline()
        groups = runtime["topology"]["bundle"]["part_groups"]
        # Push every group's bbox to the same huge offset so adjacency gaps blow up.
        for idx, group in enumerate(groups):
            shift = 1_000.0 * (idx + 1)
            group["bounds_min"] = [c + shift for c in group["bounds_min"]]
            group["bounds_max"] = [c + shift for c in group["bounds_max"]]
        report = evaluate_semantic_quality(asset, runtime)
        names = {d["name"] for d in report["diagnostics"]}
        self.assertIn("semantic_adjacency_score_failed", names)
        self.assertLess(report["metrics"]["adjacency_score"], report["thresholds"]["adjacency_score"])

    def test_fragmentation_penalty_exceeds_max_flags_failure(self) -> None:
        asset, runtime = _baseline()
        stats = runtime["topology"]["bundle"]["mesh_stats"]
        stats["body_count"] = 5000  # force ratio way above ceiling
        # Drop one part so the courier_drone "generous cap" branch is not triggered
        # (requires part_coverage >= 0.95 AND adjacency_score >= 0.90).
        runtime["topology"]["bundle"]["part_groups"] = [
            g for g in runtime["topology"]["bundle"]["part_groups"] if g["name"] != "cargo_door"
        ]
        asset["build"]["shape"]["mode"] = "generate"
        report = evaluate_semantic_quality(asset, runtime)
        names = {d["name"] for d in report["diagnostics"]}
        self.assertIn("semantic_fragmentation_failed", names)
        self.assertGreater(
            report["metrics"]["fragmentation_penalty"], report["thresholds"]["maximum_fragmentation_penalty"]
        )

    def test_toy_detected_on_under_structured_bundle(self) -> None:
        asset, runtime = _baseline()
        stats = runtime["topology"]["bundle"]["mesh_stats"]
        stats["triangle_count"] = 20
        stats["body_count"] = 80
        runtime["topology"]["bundle"]["part_groups"] = runtime["topology"]["bundle"]["part_groups"][:1]
        report = evaluate_semantic_quality(asset, runtime)
        names = {d["name"] for d in report["diagnostics"]}
        self.assertIn("toy_or_primitive_detected", names)
        self.assertTrue(report["metrics"]["toy_detected"])

    def test_diagnostic_shape_carries_path_and_suggested_repairs(self) -> None:
        asset, runtime = _baseline()
        runtime["topology"]["bundle"]["part_groups"] = []
        report = evaluate_semantic_quality(asset, runtime)
        self.assertTrue(report["diagnostics"])
        for diag in report["diagnostics"]:
            self.assertEqual(diag["severity"], "error")
            self.assertEqual(diag["phase"], "validate")
            self.assertEqual(diag["asset"], asset["name"])
            self.assertTrue(diag["path"].startswith("validate.semantic."))
            self.assertIsInstance(diag.get("suggested_repairs", []), list)


if __name__ == "__main__":
    unittest.main()
