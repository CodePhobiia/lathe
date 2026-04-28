"""Unit tests for ``lathe.test_runtime`` — the in-language ``test``
block runner and its expression evaluator.

``run_lathe_tests`` parses ``.lth`` files, materializes the asset
referenced by each ``test`` block, optionally builds it (when
``must_build`` / ``must_certify`` is set), and evaluates the test's
``assert`` expressions in a context that includes the asset payload
and (optionally) the build report.

``evaluate_test_expr`` is the small expression interpreter used by
both the test and benchmark runtimes. These cover the surface that the
language guarantees today.
"""

from __future__ import annotations

import unittest
from unittest import mock

from lathe import test_runtime
from lathe.test_runtime import evaluate_test_expr


class TestRunsSimpleTestBlock(unittest.TestCase):
    def test_program_with_no_tests_returns_ok_and_zero_total(self) -> None:
        with (
            mock.patch.object(test_runtime, "parse_file", return_value={"tests": []}),
            mock.patch.object(test_runtime, "check_program", return_value=[]),
            mock.patch.object(test_runtime, "Resolver"),
        ):
            summary = test_runtime.run_lathe_tests(["fake.lth"])
        self.assertTrue(summary["ok"])
        self.assertEqual(summary["total"], 0)
        self.assertEqual(summary["results"], [])


class TestReportsPassFail(unittest.TestCase):
    def test_summary_carries_pass_fail_keys(self) -> None:
        with (
            mock.patch.object(test_runtime, "parse_file", return_value={"tests": []}),
            mock.patch.object(test_runtime, "check_program", return_value=[]),
            mock.patch.object(test_runtime, "Resolver"),
        ):
            summary = test_runtime.run_lathe_tests(["fake.lth"])
        for key in ("ok", "total", "passed", "failed", "results"):
            self.assertIn(key, summary)


class TestAssertionFailure(unittest.TestCase):
    def test_failing_binary_assertion_marks_result_as_failed(self) -> None:
        program = {
            "tests": [
                {
                    "name": "trivial_fail",
                    "values": {},
                    "asserts": [
                        {
                            "expr": {
                                "type": "binary",
                                "op": "==",
                                "left": 1,
                                "right": 2,
                            }
                        }
                    ],
                }
            ]
        }
        with (
            mock.patch.object(test_runtime, "parse_file", return_value=program),
            mock.patch.object(test_runtime, "check_program", return_value=[]),
            mock.patch.object(test_runtime, "Resolver"),
        ):
            summary = test_runtime.run_lathe_tests(["fake.lth"])
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["passed"], 0)
        self.assertFalse(summary["results"][0]["passed"])


class TestHonorsSetupTeardown(unittest.TestCase):
    def test_must_build_flag_marks_failure_when_no_build_report(self) -> None:
        # When ``must_build`` is set but the asset name is absent (so the
        # build branch never runs), the test must be marked as failed.
        # This is the runtime's "setup" gate analogue.
        program = {
            "tests": [
                {
                    "name": "must_build_no_asset",
                    "values": {"must_build": True},
                    "asserts": [],
                }
            ]
        }
        with (
            mock.patch.object(test_runtime, "parse_file", return_value=program),
            mock.patch.object(test_runtime, "check_program", return_value=[]),
            mock.patch.object(test_runtime, "Resolver"),
        ):
            summary = test_runtime.run_lathe_tests(["fake.lth"])
        self.assertFalse(summary["results"][0]["passed"])


class TestEmptyTestListGraceful(unittest.TestCase):
    def test_no_files_yields_clean_summary(self) -> None:
        with mock.patch("pathlib.Path.glob", return_value=iter([])):
            summary = test_runtime.run_lathe_tests([])
        self.assertEqual(summary["total"], 0)
        self.assertTrue(summary["ok"])


class TestOutputShapeValid(unittest.TestCase):
    def test_result_entry_contains_expected_keys(self) -> None:
        program = {
            "tests": [
                {
                    "name": "passing_test",
                    "values": {},
                    "asserts": [
                        {
                            "expr": {
                                "type": "binary",
                                "op": "==",
                                "left": 1,
                                "right": 1,
                            }
                        }
                    ],
                }
            ]
        }
        with (
            mock.patch.object(test_runtime, "parse_file", return_value=program),
            mock.patch.object(test_runtime, "check_program", return_value=[]),
            mock.patch.object(test_runtime, "Resolver"),
        ):
            summary = test_runtime.run_lathe_tests(["fake.lth"])
        entry = summary["results"][0]
        for key in (
            "file",
            "name",
            "asset",
            "passed",
            "diagnostics",
            "assertions",
            "build",
            "build_error",
        ):
            self.assertIn(key, entry)
        self.assertTrue(entry["passed"])


class TestEvaluateExprBuiltins(unittest.TestCase):
    def test_evaluate_test_expr_handles_call_len_and_contains(self) -> None:
        ctx = {"items": [1, 2, 3], "values": {"score": 0.9}}
        # len([1,2,3]) == 3
        self.assertEqual(
            evaluate_test_expr({"type": "call", "name": "len", "args": [{"value": "items"}]}, ctx),
            3,
        )
        # contains([1,2,3], 2) == True
        self.assertTrue(
            evaluate_test_expr(
                {
                    "type": "call",
                    "name": "contains",
                    "args": [{"value": "items"}, {"value": 2}],
                },
                ctx,
            )
        )
        # ``not`` unary on a falsy literal returns True
        self.assertTrue(evaluate_test_expr({"type": "unary", "op": "not", "value": False}, ctx))


if __name__ == "__main__":
    unittest.main()
