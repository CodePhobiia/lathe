"""Unit tests for ``lathe.validators.silhouette``.

The module exposes a single public helper, ``compare_scaffold_signature``,
which produces the ``silhouette_fidelity`` signal consumed by
``evaluate_semantic_quality``. These tests cover the ratio-only branch,
the composite branch (with part groups), the stable-hash reproducibility
property, and the semantic-diagnostic fall-through.
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
from lathe.validators.silhouette import compare_scaffold_signature

REPO_ROOT = Path(__file__).resolve().parents[2]
_BUILT: dict[str, Any] | None = None


def _hero_snapshot() -> dict[str, Any]:
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
    built = _hero_snapshot()
    return copy.deepcopy(built["asset"]), copy.deepcopy(built["runtime"])


class CompareScaffoldSignatureTests(unittest.TestCase):
    def test_empty_signature_returns_neutral_score(self) -> None:
        score = compare_scaffold_signature({}, [10.0, 5.0, 20.0])
        self.assertEqual(score, 0.5)

    def test_perfect_ratio_match_scores_one(self) -> None:
        # Largest axis normalized to 1.0 drives the ratio comparison.
        sig = {"projected_ratio": [0.5, 0.25, 1.0]}
        score = compare_scaffold_signature(sig, [20.0, 10.0, 40.0])
        self.assertEqual(score, 1.0)

    def test_jagged_ratio_divergence_collapses_score(self) -> None:
        sig = {"projected_ratio": [0.5, 1.0, 0.5]}
        # Actual is long-and-flat -- ratios diverge on the middle axis.
        score = compare_scaffold_signature(sig, [1.0, 100.0, 1.0])
        self.assertLess(score, 0.5)

    def test_smooth_reference_without_features_collapses_when_part_groups_diverge(self) -> None:
        sig = {
            "projected_ratio": [0.5, 0.5, 1.0],
            "region_spread": [0.8, 0.8, 0.8],
            "vertical_profile": [0.33, 0.34, 0.33],
            "depth_profile": [0.33, 0.34, 0.33],
            "width_profile": [0.33, 0.34, 0.33],
            "expected_region_count": 8,
        }
        # Collapse all part groups onto a single point -> zero spread, single region.
        part_groups = [
            {"bounds_min": [0.0, 0.0, 0.0], "bounds_max": [0.1, 0.1, 0.1]},
            {"bounds_min": [0.0, 0.0, 0.0], "bounds_max": [0.1, 0.1, 0.1]},
        ]
        score = compare_scaffold_signature(sig, [10.0, 10.0, 20.0], part_groups)
        # Should stay below a healthy hero (≥0.8).
        self.assertLess(score, 0.75)

    def test_stable_hash_reproducibility_same_inputs_same_output(self) -> None:
        sig = {
            "projected_ratio": [0.5, 0.25, 1.0],
            "region_spread": [0.5, 0.3, 0.8],
            "vertical_profile": [0.3, 0.4, 0.3],
            "depth_profile": [0.3, 0.4, 0.3],
            "width_profile": [0.3, 0.4, 0.3],
            "expected_region_count": 4,
        }
        groups = [
            {"bounds_min": [0.0, 0.0, 0.0], "bounds_max": [1.0, 1.0, 1.0]},
            {"bounds_min": [2.0, 0.0, 0.0], "bounds_max": [3.0, 1.0, 1.0]},
            {"bounds_min": [0.0, 2.0, 0.0], "bounds_max": [1.0, 3.0, 1.0]},
            {"bounds_min": [0.0, 0.0, 2.0], "bounds_max": [1.0, 1.0, 3.0]},
        ]
        extents = [3.0, 3.0, 3.0]
        first = compare_scaffold_signature(sig, extents, copy.deepcopy(groups))
        second = compare_scaffold_signature(sig, extents, copy.deepcopy(groups))
        third = compare_scaffold_signature(sig, extents, copy.deepcopy(groups))
        self.assertEqual(first, second)
        self.assertEqual(second, third)


@pytest.mark.slow
class SilhouetteThroughSemanticTests(unittest.TestCase):
    def test_semantic_silhouette_fidelity_failure_fires_diagnostic(self) -> None:
        asset, runtime = _baseline()
        # Crush the extents signature -> silhouette ratio compare collapses.
        stats = runtime["topology"]["bundle"]["mesh_stats"]
        stats["extents"] = [1.0, 1.0, 900.0]
        stats["bounds_min"] = [-0.5, -0.5, -450.0]
        stats["bounds_max"] = [0.5, 0.5, 450.0]
        report = evaluate_semantic_quality(asset, runtime)
        names = {d["name"] for d in report["diagnostics"]}
        self.assertIn("semantic_silhouette_fidelity_failed", names)
        self.assertLess(report["metrics"]["silhouette_fidelity"], report["thresholds"]["silhouette_fidelity"])

    def test_semantic_silhouette_clears_threshold_for_hero_build(self) -> None:
        asset, runtime = _baseline()
        report = evaluate_semantic_quality(asset, runtime)
        self.assertGreaterEqual(
            report["metrics"]["silhouette_fidelity"],
            report["thresholds"]["silhouette_fidelity"],
            "hero courier_drone should clear its silhouette_fidelity minimum",
        )


if __name__ == "__main__":
    unittest.main()
