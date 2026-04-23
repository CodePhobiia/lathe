from __future__ import annotations

import unittest
from pathlib import Path

from lathe.eval_harness import run_benchmark_suite


ROOT = Path(__file__).resolve().parents[1]


class LatheBenchmarkTests(unittest.TestCase):
    def test_benchmark_suite_reports_positive_and_negative_sets(self) -> None:
        result = run_benchmark_suite(ROOT)
        self.assertEqual(result["positive_pass_rate"], 1.0)
        self.assertEqual(result["negative_fail_rate"], 1.0)
        self.assertIn("industrial_crate", result["shared_primitive_assets"])
        self.assertIn("mechanical_door", result["shared_primitive_assets"])
        self.assertIn("console_terminal", result["shared_primitive_assets"])
        self.assertTrue(any(item["asset"] == "brassbound_chest" for item in result["comparisons"]))
        self.assertTrue(any(item["asset"] == "console_terminal" for item in result["comparisons"]))
        self.assertGreaterEqual(len(result["near_miss"]), 3)
        near_miss_names = {item["name"] for item in result["near_miss"]}
        self.assertIn("legacy_brassbound_chest_v06", near_miss_names)
        self.assertIn("legacy_courier_drone_v06", near_miss_names)
        self.assertIn("legacy_console_terminal_v06", near_miss_names)


if __name__ == "__main__":
    unittest.main()
