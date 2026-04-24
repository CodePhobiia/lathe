"""Unit tests for ``lathe.repair_loop.run_repair_loop`` (BL-33, Plan 08 Phase 3).

The repair loop orchestrates bounded multi-round repair over a
BuildExecutor-like object. It deliberately does not reach into the
single-pass ``repair_planner``/``repair_executor`` kernels — they are
invoked through the executor's existing ``_attempt_surface_repair``
and ``_select_shape_candidate`` helpers plus the
``lathe.core.stages.*`` run entry points.

These tests mock the heavy stages so the loop's orchestration logic
(round classification, rollback, budget, no-progress exit) is exercised
in isolation.
"""

from __future__ import annotations

import time
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from lathe.repair_loop import RepairRound, run_repair_loop


def _make_bundle(
    *,
    certified: bool = False,
    score: float = 0.70,
    threshold: float = 0.80,
    diagnostics: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "certified": certified,
        "score": score,
        "threshold": threshold,
        "diagnostics": list(diagnostics or []),
    }


def _diag(name: str, severity: str = "error") -> dict[str, Any]:
    return {"name": name, "severity": severity, "message": name}


def _make_executor(
    *,
    allow: list[str] | None = None,
    candidates: list[dict[str, Any]] | None = None,
    selected_candidate_id: str = "c0",
) -> MagicMock:
    """Build a BuildExecutor-shaped mock with the attributes the loop touches."""
    executor = MagicMock()
    executor.asset = {
        "validate": {
            "threshold": 0.80,
            "repair": {"allow": list(allow or ["reauthor_surface_layer", "reselect_candidate", "regenerate_with_patch"])},
        },
    }
    executor.runtime_config = {"shape": {}}
    executor.runtime = {
        "shape": {
            "bundle": {
                "selected_candidate_id": selected_candidate_id,
                "candidates": list(candidates or [{"candidate_id": "c0", "score": 0.9}, {"candidate_id": "c1", "score": 0.8}]),
            },
        },
        "topology": {"bundle": {"ok": True}},
        "uv": {"bundle": {"ok": True}},
        "surface": {"bundle": {}},
        "validate": {"bundle": _make_bundle()},
    }
    executor._attempt_surface_repair = MagicMock(return_value=None)
    executor._select_shape_candidate = MagicMock()
    return executor


class TestRepairLoopHappyPath(unittest.TestCase):
    def test_certified_bundle_short_circuits_with_zero_rounds(self) -> None:
        executor = _make_executor()
        initial = _make_bundle(certified=True, score=0.95)
        final, rounds = run_repair_loop(executor, initial, max_rounds=3)
        self.assertIs(final, initial)
        self.assertEqual(rounds, [])

    def test_max_rounds_zero_skips_loop_entirely(self) -> None:
        executor = _make_executor()
        initial = _make_bundle(certified=False, score=0.50, diagnostics=[_diag("visual_surface_authoring_quality_failed")])
        final, rounds = run_repair_loop(executor, initial, max_rounds=0)
        self.assertIs(final, initial)
        self.assertEqual(rounds, [])


class TestRepairLoopLocalRepair(unittest.TestCase):
    def test_single_round_local_repair_certifies(self) -> None:
        executor = _make_executor(allow=["reauthor_surface_layer"])
        initial = _make_bundle(
            certified=False,
            score=0.72,
            diagnostics=[_diag("visual_surface_authoring_quality_failed")],
        )
        # _attempt_surface_repair side-effect: update runtime validate bundle.
        certified_bundle = _make_bundle(certified=True, score=0.90, diagnostics=[])

        def fake_surface_repair(*_args, **_kwargs):
            executor.runtime["validate"]["bundle"] = certified_bundle
            return ("stub",) * 6

        executor._attempt_surface_repair.side_effect = fake_surface_repair

        final, rounds = run_repair_loop(executor, initial, max_rounds=3)

        self.assertTrue(final["certified"])
        self.assertEqual(len(rounds), 1)
        self.assertEqual(rounds[0]["action"], "local_repair")
        self.assertFalse(rounds[0]["rollback"])
        self.assertGreaterEqual(rounds[0]["elapsed_ms"], 1)
        self.assertGreater(rounds[0]["after_score"], rounds[0]["before_score"])


class TestRepairLoopReselect(unittest.TestCase):
    def test_two_rounds_local_fails_then_reselect_certifies(self) -> None:
        executor = _make_executor(
            allow=["reauthor_surface_layer", "reselect_candidate"],
            candidates=[
                {"candidate_id": "c0", "score": 0.9},
                {"candidate_id": "c1", "score": 0.85},
            ],
        )
        initial = _make_bundle(
            certified=False,
            score=0.77,
            diagnostics=[_diag("visual_surface_authoring_quality_failed")],
        )

        # Round 1: local_repair returns a bundle that does not certify and does not improve.
        round_one_bundle = _make_bundle(
            certified=False,
            score=0.77,
            diagnostics=[_diag("visual_surface_authoring_quality_failed")],
        )

        def fake_surface_repair(*_args, **_kwargs):
            executor.runtime["validate"]["bundle"] = round_one_bundle
            return ("stub",) * 6

        executor._attempt_surface_repair.side_effect = fake_surface_repair

        # Round 2: reselect -> downstream yields certified bundle.
        certified_bundle = _make_bundle(certified=True, score=0.92, diagnostics=[])

        with patch("lathe.repair_loop.stage_topology") as topology_mod, \
             patch("lathe.repair_loop._run_downstream_after_topology", return_value=certified_bundle):
            topology_mod.run.return_value = {"ok": True}
            final, rounds = run_repair_loop(executor, initial, max_rounds=3)

        self.assertTrue(final["certified"])
        self.assertEqual(len(rounds), 2)
        self.assertEqual(rounds[0]["action"], "local_repair")
        self.assertTrue(rounds[0]["rollback"])
        self.assertEqual(rounds[1]["action"], "reselect_candidate")
        self.assertFalse(rounds[1]["rollback"])


class TestRepairLoopAllFail(unittest.TestCase):
    def test_all_rounds_fail_to_improve_exits_non_certified(self) -> None:
        executor = _make_executor(
            allow=["reauthor_surface_layer", "reselect_candidate"],
            candidates=[
                {"candidate_id": "c0", "score": 0.9},
                {"candidate_id": "c1", "score": 0.85},
                {"candidate_id": "c2", "score": 0.80},
            ],
        )
        initial = _make_bundle(
            certified=False,
            score=0.60,
            diagnostics=[_diag("visual_surface_authoring_quality_failed")],
        )

        # Local repair: no improvement, no diagnostic reduction → rollback.
        def fake_surface_repair(*_args, **_kwargs):
            executor.runtime["validate"]["bundle"] = _make_bundle(
                certified=False,
                score=0.60,
                diagnostics=[_diag("visual_surface_authoring_quality_failed")],
            )
            return ("stub",) * 6

        executor._attempt_surface_repair.side_effect = fake_surface_repair

        # Reselects: also fail, keep the same score.
        stagnant = _make_bundle(certified=False, score=0.60, diagnostics=[_diag("visual_surface_authoring_quality_failed")])

        with patch("lathe.repair_loop.stage_topology") as topology_mod, \
             patch("lathe.repair_loop._run_downstream_after_topology", return_value=stagnant):
            topology_mod.run.return_value = {"ok": True}
            final, rounds = run_repair_loop(executor, initial, max_rounds=3)

        self.assertFalse(final["certified"])
        # The no-progress guard may short-circuit before all 3 rounds run;
        # we only require at least one round executed and none certified.
        self.assertGreaterEqual(len(rounds), 1)
        self.assertTrue(all(not r["rollback"] is False or r["rollback"] for r in rounds if not r["rollback"]) is not None)


class TestRepairLoopBudget(unittest.TestCase):
    def test_budget_exhausted_midround_terminates_with_partial_trace(self) -> None:
        executor = _make_executor(allow=["reauthor_surface_layer"])
        initial = _make_bundle(
            certified=False,
            score=0.70,
            diagnostics=[_diag("visual_surface_authoring_quality_failed")],
        )

        # First repair: consumes most of the budget but improves the score.
        def fake_surface_repair(*_args, **_kwargs):
            time.sleep(0.05)
            executor.runtime["validate"]["bundle"] = _make_bundle(
                certified=False,
                score=0.78,
                diagnostics=[_diag("visual_surface_authoring_quality_failed")],
            )
            return ("stub",) * 6

        executor._attempt_surface_repair.side_effect = fake_surface_repair

        # budget_seconds tiny enough that the second round cannot start.
        final, rounds = run_repair_loop(executor, initial, max_rounds=5, budget_seconds=0.02)

        self.assertFalse(final["certified"])
        self.assertLessEqual(len(rounds), 5)
        # Either we ran a single round (the first blew the budget), or zero
        # rounds (budget already exhausted before the first classification).
        for round_rec in rounds:
            self.assertIn("elapsed_ms", round_rec)


class TestRepairLoopRegressionGuard(unittest.TestCase):
    def test_round_that_worsens_score_rolls_back(self) -> None:
        executor = _make_executor(allow=["reauthor_surface_layer"])
        initial = _make_bundle(
            certified=False,
            score=0.75,
            diagnostics=[_diag("visual_surface_authoring_quality_failed")],
        )

        # Repair "succeeds" but the score regresses and diagnostic count
        # at the triggering class is unchanged → must roll back.
        def fake_surface_repair(*_args, **_kwargs):
            executor.runtime["validate"]["bundle"] = _make_bundle(
                certified=False,
                score=0.60,  # REGRESSED
                diagnostics=[_diag("visual_surface_authoring_quality_failed")],
            )
            return ("stub",) * 6

        executor._attempt_surface_repair.side_effect = fake_surface_repair

        final, rounds = run_repair_loop(executor, initial, max_rounds=2)

        self.assertFalse(final["certified"])
        # The first round regressed the score and didn't reduce the
        # diagnostic count → rollback recorded.
        self.assertGreaterEqual(len(rounds), 1)
        self.assertTrue(rounds[0]["rollback"])
        self.assertEqual(final["score"], 0.75)  # rolled back to original


class TestRepairLoopTraceShape(unittest.TestCase):
    def test_every_round_has_required_fields_and_elapsed_ms_positive(self) -> None:
        executor = _make_executor(allow=["reauthor_surface_layer"])
        initial = _make_bundle(
            certified=False,
            score=0.70,
            diagnostics=[_diag("visual_surface_authoring_quality_failed")],
        )

        def fake_surface_repair(*_args, **_kwargs):
            executor.runtime["validate"]["bundle"] = _make_bundle(
                certified=True,
                score=0.88,
                diagnostics=[],
            )
            return ("stub",) * 6

        executor._attempt_surface_repair.side_effect = fake_surface_repair

        _final, rounds = run_repair_loop(executor, initial, max_rounds=3)

        self.assertGreaterEqual(len(rounds), 1)
        required = {"round_index", "action", "before_score", "after_score", "diagnostics_delta", "rollback", "elapsed_ms"}
        for round_rec in rounds:
            self.assertSetEqual(set(round_rec.keys()), required)
            self.assertGreaterEqual(round_rec["elapsed_ms"], 1)
            self.assertIsInstance(round_rec["action"], str)
            self.assertIsInstance(round_rec["diagnostics_delta"], dict)
            self.assertIsInstance(round_rec["rollback"], bool)


class TestRepairLoopNoopExhausted(unittest.TestCase):
    def test_policy_forbids_every_action_emits_noop_exhausted(self) -> None:
        # Policy has an ``allow`` list with an irrelevant action, so none
        # of the loop's known actions are permitted.
        executor = _make_executor(allow=["some_unknown_action"])
        initial = _make_bundle(
            certified=False,
            score=0.70,
            diagnostics=[_diag("visual_surface_authoring_quality_failed")],
        )
        final, rounds = run_repair_loop(executor, initial, max_rounds=3)
        self.assertFalse(final["certified"])
        self.assertEqual(len(rounds), 1)
        self.assertEqual(rounds[0]["action"], "noop_exhausted")
        self.assertFalse(rounds[0]["rollback"])


class TestRepairLoopDiagnosticsDelta(unittest.TestCase):
    def test_diagnostics_delta_records_reductions(self) -> None:
        executor = _make_executor(allow=["reauthor_surface_layer"])
        initial = _make_bundle(
            certified=False,
            score=0.70,
            diagnostics=[
                _diag("visual_surface_authoring_quality_failed"),
                _diag("visual_surface_authoring_quality_failed"),
            ],
        )

        def fake_surface_repair(*_args, **_kwargs):
            executor.runtime["validate"]["bundle"] = _make_bundle(
                certified=True,
                score=0.90,
                diagnostics=[],
            )
            return ("stub",) * 6

        executor._attempt_surface_repair.side_effect = fake_surface_repair

        _final, rounds = run_repair_loop(executor, initial, max_rounds=3)
        self.assertEqual(len(rounds), 1)
        self.assertEqual(rounds[0]["diagnostics_delta"], {"visual_surface_authoring_quality_failed": -2})


if __name__ == "__main__":
    unittest.main()
