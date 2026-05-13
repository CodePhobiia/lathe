"""Foundry Lane H #6 — repair rollback support.

Per northstar §10 Lane H priority task #6, the repair loop should
roll back when a rebuild *worsens* the evidence rather than committing
the worse output. This module extends the diagnose -> repair -> rebuild
chain in ``lathe/repair_loop_gate.py`` with snapshot/restore.

The rollback contract:
  - Before applying repair, snapshot the current runtime state +
    score + diagnostic count.
  - After rebuild, compare the new score + diagnostic count against
    the snapshot.
  - If new is worse (lower score, more diagnostics, or new errors),
    restore the snapshot and tag the round as ``rolled_back``.
  - Round-level diagnostics record both the attempted repair AND the
    rollback reason so the .lthpkg evidence sidecar carries the full
    history.

This is pure Python; no live geometry. The actual rebuild_fn /
validator_fn callables are injected by the build executor.
"""

from __future__ import annotations

import copy
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

REPAIR_ROLLBACK_VERSION = "lathe.asset_foundry.repair_rollback_v1"


@dataclass(frozen=True)
class RepairSnapshot:
    """A point-in-time snapshot of the build state."""

    runtime_state: Mapping[str, Any]
    score: float
    diagnostic_count: int
    error_count: int
    """Count of severity==error diagnostics."""

    round_index: int


@dataclass(frozen=True)
class RepairRoundResult:
    """One repair round's outcome."""

    round_index: int
    repair_actions_applied: tuple[str, ...]
    pre_score: float
    post_score: float
    pre_diagnostics: int
    post_diagnostics: int
    rolled_back: bool
    rollback_reason: str = ""


@dataclass(frozen=True)
class RepairLoopResult:
    """Full result of a repair-with-rollback loop."""

    version: str
    asset_id: str
    rounds_executed: int
    rounds_committed: int
    rounds_rolled_back: int
    final_score: float
    final_runtime_state: Mapping[str, Any]
    round_history: tuple[RepairRoundResult, ...]
    converged: bool


def _diagnostic_count(evidence: Mapping[str, Any]) -> tuple[int, int]:
    """Return (total_count, error_count) from an evidence dict."""
    diagnostics = evidence.get("diagnostics") or []
    if not isinstance(diagnostics, list):
        return 0, 0
    total = len(diagnostics)
    errors = sum(
        1
        for d in diagnostics
        if isinstance(d, Mapping) and str(d.get("severity", "")).lower() == "error"
    )
    return total, errors


def _is_worse(snapshot: RepairSnapshot, post_score: float, post_diags: int, post_errors: int) -> str:
    """Return a non-empty reason when the post-state is worse than the snapshot."""
    if post_errors > snapshot.error_count:
        return f"error_count_increased_{snapshot.error_count}_to_{post_errors}"
    if post_score + 1e-6 < snapshot.score:
        return f"score_dropped_{snapshot.score:.3f}_to_{post_score:.3f}"
    if post_diags > snapshot.diagnostic_count + 1 and post_score <= snapshot.score:
        return f"diag_count_grew_{snapshot.diagnostic_count}_to_{post_diags}_without_score_gain"
    return ""


def run_repair_with_rollback(
    *,
    asset: Mapping[str, Any],
    initial_runtime: Mapping[str, Any],
    initial_evidence: Mapping[str, Any],
    repair_planner_fn: Callable[[Mapping[str, Any], Mapping[str, Any], tuple[str, ...]], Mapping[str, Any]],
    rebuild_fn: Callable[[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]],
    validator_fn: Callable[[Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]],
    score_fn: Callable[[Mapping[str, Any]], float] | None = None,
    max_rounds: int = 3,
    asset_id: str = "asset",
) -> RepairLoopResult:
    """Drive the repair loop with rollback on worse outputs.

    Args:
        asset: typed asset dict.
        initial_runtime: starting runtime state.
        initial_evidence: starting validator evidence.
        repair_planner_fn: ``(asset, runtime, actions) -> plan``.
        rebuild_fn: ``(asset, runtime, plan) -> new_runtime``.
        validator_fn: ``(asset, runtime) -> evidence``.
        score_fn: ``(evidence) -> float`` extractor. Defaults to
            reading ``evidence["score"]``.
        max_rounds: max number of repair rounds before giving up.
    """
    if score_fn is None:
        def score_fn(e: Mapping[str, Any]) -> float:
            return float(e.get("score") or 0.0)

    current_runtime = dict(initial_runtime)
    current_evidence = initial_evidence
    current_score = score_fn(current_evidence)
    rounds: list[RepairRoundResult] = []
    committed = 0
    rolled_back_count = 0

    for round_idx in range(max_rounds):
        diag = (current_evidence.get("diagnostics") or [{}])[0]
        if not isinstance(diag, Mapping):
            break
        actions = tuple(str(a) for a in (diag.get("repair_actions") or []) if a)
        if not actions:
            break

        pre_diags, pre_errors = _diagnostic_count(current_evidence)
        snapshot = RepairSnapshot(
            runtime_state=copy.deepcopy(current_runtime),
            score=current_score,
            diagnostic_count=pre_diags,
            error_count=pre_errors,
            round_index=round_idx,
        )

        plan = repair_planner_fn(asset, current_runtime, actions)
        new_runtime = rebuild_fn(asset, current_runtime, plan)
        new_evidence = validator_fn(asset, new_runtime)
        new_score = score_fn(new_evidence)
        post_diags, post_errors = _diagnostic_count(new_evidence)

        worse_reason = _is_worse(snapshot, new_score, post_diags, post_errors)
        if worse_reason:
            rolled_back_count += 1
            rounds.append(
                RepairRoundResult(
                    round_index=round_idx,
                    repair_actions_applied=actions,
                    pre_score=snapshot.score,
                    post_score=new_score,
                    pre_diagnostics=snapshot.diagnostic_count,
                    post_diagnostics=post_diags,
                    rolled_back=True,
                    rollback_reason=worse_reason,
                )
            )
            # Restore snapshot — do not commit the worse state.
            current_runtime = dict(snapshot.runtime_state)
            # current_evidence + current_score stay at snapshot values.
            # Stop attempting further rounds — repeated worsenings are
            # a sign the repair plan is wrong, not flaky.
            break
        committed += 1
        rounds.append(
            RepairRoundResult(
                round_index=round_idx,
                repair_actions_applied=actions,
                pre_score=snapshot.score,
                post_score=new_score,
                pre_diagnostics=snapshot.diagnostic_count,
                post_diagnostics=post_diags,
                rolled_back=False,
            )
        )
        current_runtime = dict(new_runtime)
        current_evidence = new_evidence
        current_score = new_score
        # Converged when no diagnostics remain.
        if post_diags == 0:
            break

    converged = (
        not (current_evidence.get("diagnostics") or [])
        or all(
            isinstance(d, Mapping) and str(d.get("severity", "")).lower() != "error"
            for d in (current_evidence.get("diagnostics") or [])
        )
    )

    return RepairLoopResult(
        version=REPAIR_ROLLBACK_VERSION,
        asset_id=asset_id,
        rounds_executed=len(rounds),
        rounds_committed=committed,
        rounds_rolled_back=rolled_back_count,
        final_score=current_score,
        final_runtime_state=current_runtime,
        round_history=tuple(rounds),
        converged=converged,
    )


def repair_result_to_dict(result: RepairLoopResult) -> dict[str, Any]:
    return {
        "version": result.version,
        "asset_id": result.asset_id,
        "rounds_executed": result.rounds_executed,
        "rounds_committed": result.rounds_committed,
        "rounds_rolled_back": result.rounds_rolled_back,
        "final_score": result.final_score,
        "converged": result.converged,
        "round_history": [
            {
                "round_index": r.round_index,
                "repair_actions_applied": list(r.repair_actions_applied),
                "pre_score": r.pre_score,
                "post_score": r.post_score,
                "pre_diagnostics": r.pre_diagnostics,
                "post_diagnostics": r.post_diagnostics,
                "rolled_back": r.rolled_back,
                "rollback_reason": r.rollback_reason,
            }
            for r in result.round_history
        ],
    }


__all__ = [
    "REPAIR_ROLLBACK_VERSION",
    "RepairLoopResult",
    "RepairRoundResult",
    "RepairSnapshot",
    "repair_result_to_dict",
    "run_repair_with_rollback",
]
