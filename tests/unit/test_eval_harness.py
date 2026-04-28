"""Unit tests for ``lathe.eval_harness``.

Covers the benchmark-catalog loader and ``run_benchmark_suite`` report
structure. The per-benchmark scorecard helpers are private and involve
heavy builds; these tests stub them via ``mock.patch`` so the harness
logic itself (aggregation, pass/fail rates, comparisons) is exercised
in isolation.
"""

from __future__ import annotations

import unittest
from unittest import mock

from lathe import eval_harness


def _positive_scorecard(asset: str = "hero_asset", ok: bool = True) -> dict:
    return {
        "name": asset,
        "asset": asset,
        "family": asset,
        "ok": ok,
        "score": 0.9 if ok else 0.2,
        "threshold": 0.5,
        "shared_primitives": True,
        "semantic_quality": {
            "metrics": {
                "silhouette_fidelity": 0.8,
                "structural_richness": 0.7,
                "adjacency_score": 0.6,
                "fragmentation_penalty": 0.1,
            }
        },
        "visual_quality": {
            "metrics": {
                "detail_density": 0.5,
                "edge_readability": 0.6,
                "primitive_likeness_penalty": 0.2,
            }
        },
    }


def _negative_scorecard(asset: str = "hero_asset", ok: bool = False) -> dict:
    return {
        "name": asset,
        "asset": asset,
        "ok": ok,
        "semantic_quality": {
            "metrics": {
                "silhouette_fidelity": 0.4,
                "structural_richness": 0.3,
                "adjacency_score": 0.2,
                "fragmentation_penalty": 0.5,
            },
            "diagnostics": [] if ok else [{"name": "semantic_fail"}],
        },
        "visual_quality": {
            "metrics": {
                "detail_density": 0.1,
                "edge_readability": 0.2,
                "primitive_likeness_penalty": 0.7,
            },
            "diagnostics": [] if ok else [{"name": "visual_fail"}],
        },
        "expected_to_fail": True,
        "selection_notes": [],
        "source_build": None,
    }


class LoadBenchmarkCatalogTests(unittest.TestCase):
    def test_catalog_has_positive_and_negative_sections(self) -> None:
        catalog = eval_harness.load_benchmark_catalog()
        self.assertIn("positive", catalog)
        self.assertIsInstance(catalog["positive"], list)
        self.assertTrue(catalog["positive"])

    def test_catalog_entries_have_required_keys(self) -> None:
        catalog = eval_harness.load_benchmark_catalog()
        for entry in catalog["positive"]:
            for key in ("name", "file", "asset", "family"):
                self.assertIn(key, entry)


class RunBenchmarkSuiteTests(unittest.TestCase):
    def _patched_run(self, catalog: dict, positives: list[dict], negatives: list[dict]) -> dict:
        neg_iter = iter(negatives)
        with (
            mock.patch.object(eval_harness, "load_benchmark_catalog", return_value=catalog),
            mock.patch.object(eval_harness, "_positive_scorecard", side_effect=positives),
            mock.patch.object(
                eval_harness,
                "_negative_scorecard",
                side_effect=lambda *a, **k: next(neg_iter),
            ),
        ):
            return eval_harness.run_benchmark_suite("/workspace/does-not-matter")

    def test_basic_eval_reports_rates(self) -> None:
        catalog = {
            "positive": [{"name": "a", "asset": "hero_asset", "family": "hero_asset", "file": "a.lth"}],
            "negative": [{"name": "a", "asset": "hero_asset", "file": "a.lth"}],
            "near_miss": [],
        }
        report = self._patched_run(
            catalog,
            [_positive_scorecard(ok=True)],
            [_negative_scorecard(ok=False)],
        )
        self.assertEqual(report["positive_pass_rate"], 1.0)
        self.assertEqual(report["negative_fail_rate"], 1.0)

    def test_multiple_criteria_aggregate(self) -> None:
        catalog = {
            "positive": [
                {"name": "a", "asset": "a", "family": "a", "file": "a.lth"},
                {"name": "b", "asset": "b", "family": "b", "file": "b.lth"},
            ],
            "negative": [],
            "near_miss": [],
        }
        report = self._patched_run(
            catalog,
            [_positive_scorecard(asset="a", ok=True), _positive_scorecard(asset="b", ok=False)],
            [],
        )
        self.assertEqual(report["positive_pass_rate"], 0.5)
        self.assertEqual(len(report["positive"]), 2)

    def test_failing_criterion_flagged(self) -> None:
        catalog = {
            "positive": [],
            "negative": [{"name": "x", "asset": "x", "file": "x.lth"}],
            "near_miss": [],
        }
        report = self._patched_run(catalog, [], [_negative_scorecard(asset="x", ok=True)])
        self.assertEqual(report["negative_fail_rate"], 0.0)

    def test_report_shape_has_all_sections(self) -> None:
        catalog = {"positive": [], "negative": [], "near_miss": []}
        report = self._patched_run(catalog, [], [])
        for key in (
            "positive",
            "negative",
            "near_miss",
            "comparisons",
            "positive_pass_rate",
            "negative_fail_rate",
            "shared_primitive_assets",
        ):
            self.assertIn(key, report)

    def test_hash_stability_across_runs(self) -> None:
        catalog = {
            "positive": [{"name": "a", "asset": "hero_asset", "family": "hero_asset", "file": "a.lth"}],
            "negative": [],
            "near_miss": [],
        }
        first = self._patched_run(catalog, [_positive_scorecard(ok=True)], [])
        second = self._patched_run(catalog, [_positive_scorecard(ok=True)], [])
        self.assertEqual(first, second)

    def test_empty_catalog_safe(self) -> None:
        catalog = {"positive": [], "negative": [], "near_miss": []}
        report = self._patched_run(catalog, [], [])
        self.assertEqual(report["positive"], [])
        self.assertEqual(report["negative"], [])
        self.assertEqual(report["near_miss"], [])
        self.assertEqual(report["comparisons"], [])
        self.assertEqual(report["positive_pass_rate"], 0.0)
        self.assertEqual(report["negative_fail_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
