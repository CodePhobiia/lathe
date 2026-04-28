from __future__ import annotations

import unittest
from pathlib import Path

import pytest
from lathe.eval_harness import _negative_scorecard, load_benchmark_catalog

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.slow


class LatheSemanticQualityTests(unittest.TestCase):
    def test_legacy_negative_corpus_fails_truthful_certification(self) -> None:
        catalog = load_benchmark_catalog()
        negatives = {entry["asset"]: _negative_scorecard(ROOT, entry) for entry in catalog["negative"]}
        self.assertFalse(negatives["brassbound_chest"]["ok"])
        self.assertFalse(negatives["courier_drone"]["ok"])
        chest_names = {
            diag["name"] for diag in negatives["brassbound_chest"]["semantic_quality"]["diagnostics"]
        }
        drone_names = {diag["name"] for diag in negatives["courier_drone"]["semantic_quality"]["diagnostics"]}
        self.assertIn("semantic_silhouette_fidelity_failed", chest_names)
        expected_drone_failures = {
            "semantic_silhouette_fidelity_failed",
            "semantic_adjacency_score_failed",
        }
        self.assertTrue(expected_drone_failures & drone_names)


if __name__ == "__main__":
    unittest.main()
