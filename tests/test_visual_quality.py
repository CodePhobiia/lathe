from __future__ import annotations

import unittest
from functools import cache
from pathlib import Path

import pytest
from lathe.eval_harness import run_benchmark_suite

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.slow


@cache
def _benchmark_result() -> dict:
    return run_benchmark_suite(ROOT)


class LatheVisualQualityTests(unittest.TestCase):
    def test_legacy_and_near_miss_outputs_fail_visual_quality(self) -> None:
        result = _benchmark_result()
        legacy_by_asset = {item["asset"]: item for item in result["negative"] + result["near_miss"]}
        self.assertIn("brassbound_chest", legacy_by_asset)
        self.assertIn("courier_drone", legacy_by_asset)
        self.assertIn("console_terminal", legacy_by_asset)
        for asset_name in ("brassbound_chest", "courier_drone", "console_terminal"):
            diagnostics = legacy_by_asset[asset_name]["visual_quality"]["diagnostics"]
            self.assertTrue(diagnostics)
            names = {diag["name"] for diag in diagnostics}
            self.assertTrue(any(name.startswith("visual_") for name in names))

        near_miss_names = {item["name"] for item in result["near_miss"]}
        self.assertIn("legacy_brassbound_chest_v06", near_miss_names)
        self.assertIn("legacy_courier_drone_v06", near_miss_names)
        self.assertIn("legacy_console_terminal_v06", near_miss_names)

    def test_current_positive_assets_clear_visual_quality_thresholds(self) -> None:
        result = _benchmark_result()
        for item in result["positive"]:
            self.assertEqual(item["visual_quality"]["diagnostics"], [])


if __name__ == "__main__":
    unittest.main()
