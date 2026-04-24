"""Unit tests for ``lathe.validators.composition``.

Covers the :class:`ValidatorPipeline` contract: topological ordering,
aggregate scoring, certification gate semantics, protocol conformance
of :class:`FunctionValidator`, and edge cases (empty pipeline, single
validator).
"""

from __future__ import annotations

import unittest
from typing import Any

from lathe.validators import ValidatorPipeline
from lathe.validators.composition import (
    FunctionValidator,
    Validator,
    ValidatorReport,
)


class _StaticValidator:
    """Test fixture implementing the Validator protocol with a frozen report."""

    def __init__(
        self,
        name: str,
        score: float,
        passes: bool,
        stage_dependencies: list[str] | None = None,
        weight: float = 1.0,
    ) -> None:
        self.name = name
        self._score = score
        self._passes = passes
        self.stage_dependencies = list(stage_dependencies or [])
        self.weight = weight

    def evaluate(self, runtime: dict[str, Any], asset: dict[str, Any], artifacts: dict[str, Any]) -> ValidatorReport:
        diag: list[dict[str, Any]] = (
            []
            if self._passes
            else [{"code": "TEST", "severity": "error", "message": "fail"}]
        )
        return ValidatorReport(
            name=self.name,
            score=self._score,
            passes=self._passes,
            diagnostics=diag,
            evidence={"metrics": {"score": self._score}},
            subreports={},
        )


class ValidatorPipelineTests(unittest.TestCase):
    def test_empty_pipeline_trivially_certified(self) -> None:
        pipeline = ValidatorPipeline([])
        bundle = pipeline.run({}, {}, {})
        self.assertTrue(bundle["certified"])
        self.assertEqual(bundle["score"], 1.0)
        self.assertEqual(bundle["validators"], {})

    def test_single_passing_validator(self) -> None:
        validator = _StaticValidator("semantic", score=0.9, passes=True)
        pipeline = ValidatorPipeline([validator])
        bundle = pipeline.run({}, {}, {})
        self.assertTrue(bundle["certified"])
        self.assertAlmostEqual(bundle["score"], 0.9, places=6)
        self.assertIn("semantic", bundle["validators"])

    def test_single_failing_validator(self) -> None:
        validator = _StaticValidator("semantic", score=0.3, passes=False)
        pipeline = ValidatorPipeline([validator])
        bundle = pipeline.run({}, {}, {})
        self.assertFalse(bundle["certified"])
        self.assertAlmostEqual(bundle["score"], 0.3, places=6)

    def test_one_pass_one_fail_flips_certified_to_false(self) -> None:
        passing = _StaticValidator("a", score=0.95, passes=True)
        failing = _StaticValidator("b", score=0.40, passes=False)
        pipeline = ValidatorPipeline([passing, failing])
        bundle = pipeline.run({}, {}, {})
        self.assertFalse(bundle["certified"])
        # Weighted sum of scores with unit weights ⇒ simple mean.
        self.assertAlmostEqual(bundle["score"], (0.95 + 0.40) / 2, places=6)

    def test_all_passing_certified_true_weighted_sum(self) -> None:
        first = _StaticValidator("a", score=0.8, passes=True, weight=1.0)
        second = _StaticValidator("b", score=0.6, passes=True, weight=3.0)
        pipeline = ValidatorPipeline([first, second])
        bundle = pipeline.run({}, {}, {})
        self.assertTrue(bundle["certified"])
        # (1.0 * 0.8 + 3.0 * 0.6) / (1.0 + 3.0) = 2.6 / 4.0 = 0.65
        self.assertAlmostEqual(bundle["score"], 0.65, places=6)

    def test_topological_order_honours_dependencies(self) -> None:
        # ``b`` depends on stage ``a_stage`` announced by ``a``'s presence.
        # Registration order deliberately places b first to prove ordering.
        first = _StaticValidator("b", score=0.5, passes=True, stage_dependencies=["a"])
        second = _StaticValidator("a", score=0.5, passes=True, stage_dependencies=[])
        pipeline = ValidatorPipeline([first, second])
        names = [validator.name for validator in pipeline.validators]
        self.assertEqual(names, ["a", "b"])

    def test_topological_order_preserves_order_when_ties(self) -> None:
        one = _StaticValidator("x", score=0.5, passes=True)
        two = _StaticValidator("y", score=0.5, passes=True)
        three = _StaticValidator("z", score=0.5, passes=True)
        pipeline = ValidatorPipeline([one, two, three])
        self.assertEqual([validator.name for validator in pipeline.validators], ["x", "y", "z"])

    def test_report_shape_conforms_to_validator_report(self) -> None:
        validator = _StaticValidator("semantic", score=0.7, passes=True)
        pipeline = ValidatorPipeline([validator])
        bundle = pipeline.run({}, {}, {})
        report = bundle["validators"]["semantic"]
        for key in ("name", "score", "passes", "diagnostics", "evidence"):
            self.assertIn(key, report)
        self.assertEqual(report["name"], "semantic")
        self.assertIsInstance(report["diagnostics"], list)
        self.assertIsInstance(report["evidence"], dict)

    def test_function_validator_satisfies_protocol(self) -> None:
        def fake(asset: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
            return {"metrics": {"x": 1.0}, "diagnostics": []}

        adapter = FunctionValidator(name="fake", fn=fake, stage_dependencies=["shape"])
        self.assertIsInstance(adapter, Validator)
        report = adapter.evaluate({}, {}, {})
        self.assertTrue(report["passes"])
        self.assertEqual(report["name"], "fake")
        self.assertIn("metrics", report["evidence"])

    def test_function_validator_flags_failure_on_error_diagnostic(self) -> None:
        def fake(asset: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
            return {
                "metrics": {},
                "diagnostics": [{"code": "L6301", "severity": "error", "message": "boom"}],
            }

        adapter = FunctionValidator(name="fake", fn=fake)
        report = adapter.evaluate({}, {}, {})
        self.assertFalse(report["passes"])
        self.assertEqual(report["score"], 0.0)

    def test_pipeline_publishes_evidence_into_runtime_between_steps(self) -> None:
        """Legacy validators chain through ``runtime[name]``; the pipeline
        must keep that contract so downstream readers observe upstream
        metrics without mutating the validator functions."""
        seen: dict[str, Any] = {}

        def first_fn(asset: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
            return {"metrics": {"first_metric": 0.42}, "diagnostics": []}

        def second_fn(asset: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
            seen["first_visible_to_second"] = runtime.get("first")
            return {"metrics": {"second_metric": 0.99}, "diagnostics": []}

        pipeline = ValidatorPipeline(
            [
                FunctionValidator(name="first", fn=first_fn),
                FunctionValidator(name="second", fn=second_fn),
            ]
        )
        pipeline.run({}, {}, {})
        self.assertIsNotNone(seen["first_visible_to_second"])
        self.assertEqual(seen["first_visible_to_second"]["metrics"]["first_metric"], 0.42)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
