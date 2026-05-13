"""Class anchor → repair budget gate (Wave 22 / P3+P5).

Wires class_anchor failures into the build's auto-retry path. When
the validator emits L6500, this gate translates the diagnostic into a
``RepairBudgetTrigger`` the build executor consumes to invoke the
repair_planner + executor + rebuild.

Demonstrates the closed loop:
  featureless build → L6500 → repair plan → graph mutation → rebuild
  → second class_anchor check passes (or budget exhausted).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

CONTRACT_VERSION = "lathe.repair.gate_v1"


@dataclass(frozen=True)
class RepairBudgetTrigger:
    """An auto-retry request emitted by the gate."""

    reason: str
    diagnostic_code: str
    repair_actions: tuple[str, ...]
    rebuild_target: str = "shape"  # which stage to re-enter
    budget_remaining: int = 0


@dataclass(frozen=True)
class RepairLoopDemoResult:
    """Outcome of a demonstrated diagnose → repair → rebuild loop."""

    initial_evidence: Mapping[str, Any]
    repair_actions_applied: tuple[str, ...]
    final_evidence: Mapping[str, Any]
    converged: bool
    rounds: int


def gate_class_anchor_failure(
    validate_bundle: Mapping[str, Any],
    budget_remaining: int,
) -> RepairBudgetTrigger | None:
    """Return a repair trigger when class_anchor fails + budget allows.

    Reads the validate bundle's diagnostics, looks for L6500
    class_anchor_fail, extracts repair_actions, returns a trigger
    when at least one action is named and budget > 0. Returns None
    otherwise so the build proceeds without a repair round.
    """
    if budget_remaining <= 0:
        return None
    diagnostics = validate_bundle.get("diagnostics") or []
    for diag in diagnostics:
        if not isinstance(diag, Mapping):
            continue
        if diag.get("code") != "L6500":
            continue
        actions = tuple(str(a) for a in (diag.get("repair_actions") or []) if a)
        if not actions:
            continue
        return RepairBudgetTrigger(
            reason=str(diag.get("name") or "class_anchor_fail"),
            diagnostic_code="L6500",
            repair_actions=actions,
            rebuild_target="shape",
            budget_remaining=budget_remaining,
        )
    return None


def demonstrate_repair_loop(
    asset: Mapping[str, Any],
    initial_runtime: Mapping[str, Any],
    repair_planner_fn,
    rebuild_fn,
    validator_fn,
    max_rounds: int = 3,
) -> RepairLoopDemoResult:
    """Drive a diagnose → repair → rebuild loop until convergence.

    The fn parameters are injected so the demo can run with mocks in
    unit tests. The integration test wires the real planner +
    rebuild + validator.
    """
    current_runtime = dict(initial_runtime)
    initial_evidence = validator_fn(asset, current_runtime)
    if not initial_evidence.get("diagnostics"):
        return RepairLoopDemoResult(
            initial_evidence=initial_evidence,
            repair_actions_applied=(),
            final_evidence=initial_evidence,
            converged=True,
            rounds=0,
        )

    actions_applied: list[str] = []
    rounds = 0
    final_evidence = initial_evidence
    for round_idx in range(max_rounds):
        rounds += 1
        diag = (final_evidence.get("diagnostics") or [{}])[0]
        if not isinstance(diag, Mapping):
            break
        actions = tuple(str(a) for a in (diag.get("repair_actions") or []) if a)
        if not actions:
            break

        plan = repair_planner_fn(asset, current_runtime, actions)
        actions_applied.extend(actions)

        current_runtime = rebuild_fn(asset, current_runtime, plan)
        final_evidence = validator_fn(asset, current_runtime)
        if not final_evidence.get("diagnostics"):
            return RepairLoopDemoResult(
                initial_evidence=initial_evidence,
                repair_actions_applied=tuple(actions_applied),
                final_evidence=final_evidence,
                converged=True,
                rounds=rounds,
            )

    return RepairLoopDemoResult(
        initial_evidence=initial_evidence,
        repair_actions_applied=tuple(actions_applied),
        final_evidence=final_evidence,
        converged=False,
        rounds=rounds,
    )


__all__ = [
    "CONTRACT_VERSION",
    "RepairBudgetTrigger",
    "RepairLoopDemoResult",
    "gate_class_anchor_failure",
    "demonstrate_repair_loop",
]
