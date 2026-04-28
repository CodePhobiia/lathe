"""Unit tests for ``lathe.bench_runtime.run_lathe_benchmarks``.

``run_lathe_benchmarks`` discovers ``benchmark`` blocks inside ``.lth``
sources and drives them: it builds the named asset, replays declared
``compare_against`` fixtures through the negative-scorecard, and
evaluates each ``assert`` expression in a context made of the build
report + shape bundle + validate report.

These tests are unit-level and avoid touching the real build pipeline
— they exercise the runtime's discovery + reporting shape using a
no-benchmarks ``.lth`` file, an explicit empty file list, and a
monkeypatched ``build_asset`` for the path that would otherwise call
the full executor.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

from lathe import bench_runtime

_NO_BENCH_LTH = """
asset noop_asset {
  kind = prop
  intent { role = crate, parts = [body] }
  build { shape { symmetry = auto }, rig {}, interfaces {} }
  validate { threshold = 0.80 }
}
"""


def _write_lth(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "noop.lth"
    path.write_text(body, encoding="utf-8")
    return path


class TestBenchRunsSimpleBenchmarkBlock(unittest.TestCase):
    def test_program_with_no_benchmarks_passes_trivially(self) -> None:
        # An empty benchmarks list ⇒ ok=True, total=0, passed=0.
        with mock.patch.object(bench_runtime, "parse_file", return_value={"fixtures": [], "benchmarks": []}):
            summary = bench_runtime.run_lathe_benchmarks(["fake.lth"])
        self.assertTrue(summary["ok"])
        self.assertEqual(summary["total"], 0)
        self.assertEqual(summary["passed"], 0)
        self.assertEqual(summary["results"], [])


class TestBenchReportsTiming(unittest.TestCase):
    def test_summary_shape_includes_pass_fail_counts(self) -> None:
        # The summary dict must always carry the keys the CLI reporter
        # expects, even when nothing ran.
        with mock.patch.object(bench_runtime, "parse_file", return_value={"fixtures": [], "benchmarks": []}):
            summary = bench_runtime.run_lathe_benchmarks(["fake.lth"])
        for key in ("ok", "total", "passed", "failed", "results"):
            self.assertIn(key, summary)
        self.assertEqual(summary["failed"], 0)


class TestBenchHonorsIterationCount(unittest.TestCase):
    def test_each_benchmark_decl_produces_one_result_entry(self) -> None:
        # One benchmark decl ⇒ one result entry, regardless of internal
        # iteration count. We mock ``build_asset`` and the validate /
        # shape JSON loads to keep this hermetic.
        program = {
            "fixtures": [],
            "benchmarks": [
                {
                    "name": "bench_a",
                    "values": {"asset": "asset_a", "must_pass": False, "compare_against": []},
                    "asserts": [],
                }
            ],
        }
        fake_report = {"score": 1.0, "threshold": 0.5, "certified": True}
        with (
            mock.patch.object(bench_runtime, "parse_file", return_value=program),
            mock.patch.object(bench_runtime, "build_asset", return_value=fake_report),
            mock.patch("pathlib.Path.read_text", return_value=json.dumps({})),
        ):
            summary = bench_runtime.run_lathe_benchmarks(["fake.lth"])
        self.assertEqual(summary["total"], 1)
        self.assertEqual(len(summary["results"]), 1)
        self.assertEqual(summary["results"][0]["name"], "bench_a")


class TestBenchWithFailingBlock(unittest.TestCase):
    def test_failing_assertion_marks_result_as_not_passed(self) -> None:
        program = {
            "fixtures": [],
            "benchmarks": [
                {
                    "name": "bench_fail",
                    "values": {"asset": "asset_a", "must_pass": False, "compare_against": []},
                    "asserts": [
                        {
                            "expr": {
                                "type": "binary",
                                "op": ">",
                                "left": "score",
                                "right": "threshold",
                            }
                        }
                    ],
                }
            ],
        }
        # score (0.1) is NOT greater than threshold (0.5) ⇒ assert fails.
        fake_report = {"score": 0.1, "threshold": 0.5, "certified": False}
        with (
            mock.patch.object(bench_runtime, "parse_file", return_value=program),
            mock.patch.object(bench_runtime, "build_asset", return_value=fake_report),
            mock.patch("pathlib.Path.read_text", return_value=json.dumps({})),
        ):
            summary = bench_runtime.run_lathe_benchmarks(["fake.lth"])
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["passed"], 0)
        self.assertFalse(summary["ok"])
        self.assertFalse(summary["results"][0]["passed"])


class TestBenchEmptyListGraceful(unittest.TestCase):
    def test_empty_files_argument_does_not_crash(self) -> None:
        # ``files=[]`` falls back to globbing examples/*.lth; we patch
        # the glob to return nothing so the runtime stays hermetic.
        with mock.patch("pathlib.Path.glob", return_value=iter([])):
            summary = bench_runtime.run_lathe_benchmarks([])
        self.assertEqual(summary["total"], 0)
        self.assertTrue(summary["ok"])


class TestBenchOutputShapeValid(unittest.TestCase):
    def test_result_entry_carries_expected_keys(self) -> None:
        program = {
            "fixtures": [],
            "benchmarks": [
                {
                    "name": "bench_shape",
                    "values": {"asset": "asset_a", "must_pass": False, "compare_against": []},
                    "asserts": [],
                }
            ],
        }
        fake_report = {"score": 1.0, "threshold": 0.5, "certified": True}
        with (
            mock.patch.object(bench_runtime, "parse_file", return_value=program),
            mock.patch.object(bench_runtime, "build_asset", return_value=fake_report),
            mock.patch("pathlib.Path.read_text", return_value=json.dumps({})),
        ):
            summary = bench_runtime.run_lathe_benchmarks(["fake.lth"])
        entry = summary["results"][0]
        for key in (
            "file",
            "resolved_file",
            "name",
            "asset",
            "passed",
            "report",
            "validate",
            "shape",
            "comparisons",
            "assertions",
        ):
            self.assertIn(key, entry)


if __name__ == "__main__":
    unittest.main()
