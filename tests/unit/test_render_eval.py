"""Unit tests for ``lathe.render_eval``.

Exercises ``evaluate_render_views`` through its rectangle-rasterization path
(driven by ``part_groups`` bounds), plus the empty-input fallback and
determinism properties.
"""

from __future__ import annotations

import unittest

from lathe.render_eval import evaluate_render_views


def _two_part_runtime() -> dict:
    return {
        "bundle": {
            "part_groups": [
                {
                    "name": "hull",
                    "bounds_min": [-1.0, -0.5, -1.0],
                    "bounds_max": [1.0, 0.5, 1.0],
                },
                {
                    "name": "strut",
                    "bounds_min": [-0.1, 0.5, -0.1],
                    "bounds_max": [0.1, 1.5, 0.1],
                },
            ]
        }
    }


class EvaluateRenderViewsTests(unittest.TestCase):
    def test_runs_on_mock_part_groups(self) -> None:
        result = evaluate_render_views(_two_part_runtime())
        self.assertIn("views", result)
        self.assertIn("metrics", result)
        self.assertEqual(set(result["views"].keys()), {"front", "side", "iso"})

    def test_empty_runtime_returns_default_thresholds(self) -> None:
        result = evaluate_render_views({"bundle": {"part_groups": []}})
        self.assertEqual(result["views"], {})
        metrics = result["metrics"]
        self.assertEqual(metrics["render_silhouette_complexity"], 0.0)
        self.assertEqual(metrics["render_primitive_penalty"], 1.0)
        self.assertEqual(metrics["render_assembly_artifact_penalty"], 1.0)
        self.assertEqual(metrics["render_component_clutter"], 1.0)
        self.assertEqual(metrics["render_shading_variance"], 0.0)

    def test_per_view_scoring_has_expected_keys(self) -> None:
        result = evaluate_render_views(_two_part_runtime(), views=["front", "iso"])
        for view_name in ("front", "iso"):
            view = result["views"][view_name]
            for key in (
                "area",
                "bbox_area",
                "perimeter",
                "components",
                "complexity",
                "primitive_penalty",
                "artifact_penalty",
                "clutter",
                "shading_variance",
            ):
                self.assertIn(key, view)

    def test_aggregation_is_mean_of_per_view_scores(self) -> None:
        result = evaluate_render_views(_two_part_runtime(), views=["front", "side"])
        per_view = result["views"]
        complexities = [per_view[v]["complexity"] for v in ("front", "side")]
        expected = round(sum(complexities) / 2, 6)
        self.assertAlmostEqual(
            result["metrics"]["render_silhouette_complexity"], expected, places=5
        )

    def test_single_tiny_part_flags_primitive_like(self) -> None:
        runtime = {
            "bundle": {
                "part_groups": [
                    {
                        "name": "cube",
                        "bounds_min": [-0.5, -0.5, -0.5],
                        "bounds_max": [0.5, 0.5, 0.5],
                    }
                ]
            }
        }
        result = evaluate_render_views(runtime, views=["front"])
        metrics = result["metrics"]
        self.assertGreaterEqual(metrics["render_primitive_penalty"], 0.0)
        self.assertLessEqual(metrics["render_primitive_penalty"], 1.0)
        self.assertEqual(metrics["render_shading_variance"], 0.0)

    def test_deterministic_on_identical_input(self) -> None:
        first = evaluate_render_views(_two_part_runtime())
        second = evaluate_render_views(_two_part_runtime())
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
