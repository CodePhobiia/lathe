"""Autonomous multi-round repair loop (BL-33, Plan 08 Phase 3).

The repair loop orchestrates up to ``max_rounds`` repair attempts over an
already-built asset whose validate stage did not certify. Each round:

1. Classifies the current ``validate_bundle`` diagnostics into an action
   (``local_repair`` | ``reselect_candidate`` | ``regenerate_with_patch``).
2. Snapshots the executor runtime state so the round can be rolled back.
3. Invokes the existing single-pass helpers on the ``BuildExecutor``:
   ``_attempt_surface_repair`` for surface reauthoring, a per-round
   reselection helper for candidate switching, and a patch-runtime-config
   -plus-re-run-shape path for systemic regeneration.
4. Computes a diagnostics delta and score delta. If the round neither
   improved the score by ``min_improvement`` nor strictly reduced the
   diagnostic count at the triggering class, it is rolled back.

The loop returns the final validate_bundle (certified or not) plus a
list of ``RepairRound`` trace records suitable for inclusion in
``build_report.json["repair_rounds"]``.

This module deliberately does NOT touch ``repair_planner.py`` or
``repair_executor.py`` — those remain the single-pass semantic repair
kernel. The repair loop only orchestrates over them via the executor's
existing per-stage run helpers.
"""

from __future__ import annotations

import copy
import time
from typing import Any, TypedDict

from .core.stages import (
    interfaces as stage_interfaces,
    optimize as stage_optimize,
    physics as stage_physics,
    rig as stage_rig,
    shape as stage_shape,
    surface as stage_surface,
    topology as stage_topology,
    uv as stage_uv,
    validate as stage_validate,
)


class RepairRound(TypedDict):
    """One round of the autonomous repair loop.

    Fields:
        round_index: 1-indexed ordinal within the loop.
        action: One of ``reselect_candidate``, ``local_repair``,
            ``regenerate_with_patch``, or ``noop_exhausted`` when no
            action was available.
        before_score: Score of the validate_bundle entering the round.
        after_score: Score of the validate_bundle after the round.
            Equals before_score on a rollback.
        diagnostics_delta: Per-class change in diagnostic counts, keyed
            by ``{diagnostic_name}``; negative values indicate a
            reduction. Only entries that changed are included.
        rollback: True if the round was rolled back (neither score
            improvement nor diagnostic reduction).
        elapsed_ms: Wall-clock milliseconds spent in the round.
    """

    round_index: int
    action: str
    before_score: float
    after_score: float
    diagnostics_delta: dict[str, int]
    rollback: bool
    elapsed_ms: int


_SURFACE_DIAG_NAMES = {"visual_surface_authoring_quality_failed"}

_LOCAL_REPAIR_DIAG_NAMES = _SURFACE_DIAG_NAMES | {
    "semantic_quality_failed",
    "flow_quality_failed",
}

_RESELECT_SCORE_GAP = 0.05  # score within this of threshold => try reselect


def _diagnostic_name_counts(bundle: dict[str, Any]) -> dict[str, int]:
    """Return {diagnostic_name: count} from a validate bundle."""
    counts: dict[str, int] = {}
    for diag in bundle.get("diagnostics", []):
        name = diag.get("name") or diag.get("code") or "unknown"
        counts[name] = counts.get(name, 0) + 1
    return counts


def _diagnostics_delta(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    """Compute (after - before) keyed deltas; include only changed entries."""
    keys = set(before) | set(after)
    delta: dict[str, int] = {}
    for name in sorted(keys):
        diff = after.get(name, 0) - before.get(name, 0)
        if diff != 0:
            delta[name] = diff
    return delta


def _classify(
    validate_bundle: dict[str, Any],
    threshold: float,
    *,
    allowed_actions: set[str],
    exhausted_actions: set[str],
) -> str:
    """Pick an action for the next round.

    Decision order (first allowed + not-exhausted action wins):
    1. ``local_repair`` when a surface diagnostic is present and
       ``reauthor_surface_layer`` is allowed.
    2. ``reselect_candidate`` when the score is within
       ``_RESELECT_SCORE_GAP`` of the threshold.
    3. ``regenerate_with_patch`` when diagnostics span multiple classes
       (systemic failure).
    4. ``reselect_candidate`` as a general fallback.
    5. ``local_repair`` for any local-repair-class diagnostic.
    6. ``noop_exhausted`` if nothing above applies.

    An action previously recorded as ``exhausted`` (e.g. local_repair
    was tried and rolled back) is skipped so the loop can escalate to
    the next action class.
    """
    score = float(validate_bundle.get("score", 0.0))
    diag_names = {d.get("name") for d in validate_bundle.get("diagnostics", []) if d.get("severity") == "error"}
    has_surface_diag = bool(diag_names & _SURFACE_DIAG_NAMES)
    distinct_classes = len({name for name in diag_names if name})

    def available(action: str) -> bool:
        return action not in exhausted_actions

    if has_surface_diag and "reauthor_surface_layer" in allowed_actions and available("local_repair"):
        return "local_repair"
    if (
        threshold - score <= _RESELECT_SCORE_GAP
        and "reselect_candidate" in allowed_actions
        and available("reselect_candidate")
    ):
        return "reselect_candidate"
    if distinct_classes >= 2 and "regenerate_with_patch" in allowed_actions and available("regenerate_with_patch"):
        return "regenerate_with_patch"
    if "reselect_candidate" in allowed_actions and available("reselect_candidate"):
        return "reselect_candidate"
    if (
        "reauthor_surface_layer" in allowed_actions
        and diag_names & _LOCAL_REPAIR_DIAG_NAMES
        and available("local_repair")
    ):
        return "local_repair"
    if "regenerate_with_patch" in allowed_actions and available("regenerate_with_patch"):
        return "regenerate_with_patch"
    return "noop_exhausted"


def _snapshot_runtime(executor: Any) -> dict[str, Any]:
    """Shallow-deep-copy the executor runtime dict so rollback is safe.

    ``RuntimeMesh`` holds numpy arrays which are expensive to copy; we
    snapshot the dict structure + ``bundle`` JSON so restoring a round
    returns identical validate-relevant data. Provider proposal tensors
    are shallow-aliased (they are read-only after the shape round).
    """
    snap: dict[str, Any] = {}
    for stage, payload in executor.runtime.items():
        if isinstance(payload, dict):
            snap[stage] = {k: v for k, v in payload.items()}
            if "bundle" in payload and isinstance(payload["bundle"], dict):
                try:
                    snap[stage]["bundle"] = copy.deepcopy(payload["bundle"])
                except (TypeError, ValueError):
                    snap[stage]["bundle"] = dict(payload["bundle"])
        else:
            snap[stage] = payload
    return snap


def _restore_runtime(executor: Any, snapshot: dict[str, Any]) -> None:
    """Restore the runtime from a snapshot produced by ``_snapshot_runtime``."""
    executor.runtime = snapshot


def _select_next_candidate(executor: Any, attempted: set[str]) -> str | None:
    """Return the next untried candidate id sorted by descending score.

    Returns None when every candidate has been attempted (or only the
    currently selected one remains).
    """
    bundle = executor.runtime["shape"]["bundle"]
    current = bundle.get("selected_candidate_id")
    ordered = sorted(
        bundle.get("candidates", []),
        key=lambda item: (-float(item.get("score", 0.0)), item.get("candidate_id", "")),
    )
    for candidate in ordered:
        cid = candidate.get("candidate_id")
        if cid is None or cid == current or cid in attempted:
            continue
        return cid
    return None


def _run_downstream_after_topology(executor: Any, topology_bundle: dict[str, Any]) -> dict[str, Any]:
    """Run uv → surface → rig → ... → validate and return the validate bundle."""
    uv_bundle = stage_uv.run(executor, topology_bundle)
    surface_bundle = stage_surface.run(executor, uv_bundle)
    rig_bundle = stage_rig.run(executor, surface_bundle)
    interfaces_bundle = stage_interfaces.run(executor, rig_bundle)
    physics_bundle = stage_physics.run(executor, interfaces_bundle)
    optimize_bundle = stage_optimize.run(executor, physics_bundle)
    return stage_validate.run(executor, optimize_bundle)


def _execute_local_repair(executor: Any) -> dict[str, Any] | None:
    """Run one surface-reauthor repair pass; returns the new validate bundle or None."""
    topology_bundle = executor.runtime.get("topology", {}).get("bundle")
    uv_bundle = executor.runtime.get("uv", {}).get("bundle")
    validate_bundle = executor.runtime.get("validate", {}).get("bundle")
    if topology_bundle is None or uv_bundle is None or validate_bundle is None:
        return None
    result = executor._attempt_surface_repair(validate_bundle, topology_bundle, uv_bundle)
    if result is None:
        return None
    # _attempt_surface_repair runs validate internally; return its bundle.
    return executor.runtime["validate"]["bundle"]


def _execute_reselect(executor: Any, attempted: set[str]) -> dict[str, Any] | None:
    """Select the next best candidate and rerun topology→validate. Returns validate bundle or None."""
    candidate_id = _select_next_candidate(executor, attempted)
    if candidate_id is None:
        return None
    attempted.add(candidate_id)
    executor._select_shape_candidate(candidate_id, "repair_loop_reselect")
    topology_bundle = stage_topology.run(executor, executor.runtime["shape"]["bundle"])
    return _run_downstream_after_topology(executor, topology_bundle)


def _execute_regenerate_with_patch(executor: Any, round_index: int) -> dict[str, Any] | None:
    """Apply a patch to the runtime_config and re-run shape → validate.

    The patch bumps a shape-stage nonce so the provider re-seeds its
    candidate search, and sets ``shape.repair_nonce`` to the round index
    so the trace is observable.
    """
    shape_cfg = executor.runtime_config.setdefault("shape", {})
    shape_cfg["repair_nonce"] = round_index
    try:
        shape_bundle = stage_shape.run(executor)
    except Exception:  # noqa: BLE001 — shape is probabilistic; bail the round gracefully
        return None
    topology_bundle = stage_topology.run(executor, shape_bundle)
    return _run_downstream_after_topology(executor, topology_bundle)


def _choose_trigger_class(validate_bundle: dict[str, Any]) -> str | None:
    """Return the most-common error-diagnostic name, or None if none."""
    counts: dict[str, int] = {}
    for diag in validate_bundle.get("diagnostics", []):
        if diag.get("severity") != "error":
            continue
        name = diag.get("name")
        if name:
            counts[name] = counts.get(name, 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda kv: (kv[1], kv[0]))[0]


def run_repair_loop(
    executor: Any,
    initial_validate_bundle: dict[str, Any],
    *,
    max_rounds: int = 3,
    min_improvement: float = 0.01,
    budget_seconds: float = 180.0,
) -> tuple[dict[str, Any], list[RepairRound]]:
    """Attempt bounded multi-round repair.

    Args:
        executor: BuildExecutor-like object. The loop uses its
            ``_attempt_surface_repair`` and ``_select_shape_candidate``
            helpers plus the ``core.stages.*`` run entry points.
        initial_validate_bundle: The validate bundle that triggered
            repair. Must include ``certified``, ``score``, ``threshold``,
            and ``diagnostics``.
        max_rounds: Upper bound on rounds attempted. 0 disables the loop
            (returns the input bundle untouched).
        min_improvement: Minimum score improvement (exclusive) required
            to accept a round whose diagnostic count did not strictly
            decrease at its triggering class.
        budget_seconds: Wall-clock cap across all rounds combined.

    Returns:
        (final_validate_bundle, rounds_trace). The trace is an in-order
        list of RepairRound records, one per attempted round.
    """
    if initial_validate_bundle.get("certified") or max_rounds <= 0:
        return initial_validate_bundle, []

    repair_cfg = executor.asset.get("validate", {}).get("repair", {})
    allowed_actions: set[str] = set(repair_cfg.get("allow", []))
    # A regenerate_with_patch action is implicitly allowed when the asset
    # declares no ``allow`` list — otherwise it must be opted in.
    if not allowed_actions:
        allowed_actions = {"reauthor_surface_layer", "reselect_candidate"}

    current_bundle = initial_validate_bundle
    threshold = float(initial_validate_bundle.get("threshold", 0.80))
    rounds: list[RepairRound] = []
    attempted_candidates: set[str] = set()
    exhausted_actions: set[str] = set()
    start = time.monotonic()

    for round_index in range(1, max_rounds + 1):
        if time.monotonic() - start >= budget_seconds:
            break
        if current_bundle.get("certified"):
            break

        round_start = time.monotonic()
        before_score = float(current_bundle.get("score", 0.0))
        before_counts = _diagnostic_name_counts(current_bundle)
        trigger_class = _choose_trigger_class(current_bundle)

        action = _classify(
            current_bundle,
            threshold,
            allowed_actions=allowed_actions,
            exhausted_actions=exhausted_actions,
        )
        if action == "noop_exhausted":
            rounds.append({
                "round_index": round_index,
                "action": action,
                "before_score": before_score,
                "after_score": before_score,
                "diagnostics_delta": {},
                "rollback": False,
                "elapsed_ms": max(1, int((time.monotonic() - round_start) * 1000)),
            })
            break

        snapshot = _snapshot_runtime(executor)
        new_bundle: dict[str, Any] | None
        if action == "local_repair":
            new_bundle = _execute_local_repair(executor)
        elif action == "reselect_candidate":
            new_bundle = _execute_reselect(executor, attempted_candidates)
        elif action == "regenerate_with_patch":
            new_bundle = _execute_regenerate_with_patch(executor, round_index)
        else:
            new_bundle = None

        elapsed_ms = max(1, int((time.monotonic() - round_start) * 1000))

        if new_bundle is None:
            _restore_runtime(executor, snapshot)
            exhausted_actions.add(action)
            rounds.append({
                "round_index": round_index,
                "action": action,
                "before_score": before_score,
                "after_score": before_score,
                "diagnostics_delta": {},
                "rollback": True,
                "elapsed_ms": elapsed_ms,
            })
            continue

        after_score = float(new_bundle.get("score", 0.0))
        after_counts = _diagnostic_name_counts(new_bundle)
        delta = _diagnostics_delta(before_counts, after_counts)

        score_improved = (after_score - before_score) >= min_improvement
        trigger_reduced = (
            trigger_class is not None
            and after_counts.get(trigger_class, 0) < before_counts.get(trigger_class, 0)
        )
        certified = bool(new_bundle.get("certified"))
        accept = certified or score_improved or trigger_reduced

        if accept:
            current_bundle = new_bundle
            rounds.append({
                "round_index": round_index,
                "action": action,
                "before_score": before_score,
                "after_score": after_score,
                "diagnostics_delta": delta,
                "rollback": False,
                "elapsed_ms": elapsed_ms,
            })
            if certified:
                break
        else:
            _restore_runtime(executor, snapshot)
            exhausted_actions.add(action)
            rounds.append({
                "round_index": round_index,
                "action": action,
                "before_score": before_score,
                "after_score": after_score,
                "diagnostics_delta": delta,
                "rollback": True,
                "elapsed_ms": elapsed_ms,
            })

    return current_bundle, rounds


__all__ = ["RepairRound", "run_repair_loop"]
