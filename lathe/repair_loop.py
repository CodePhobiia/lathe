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
from typing import Any, NotRequired, TypedDict

from .core.stages import (
    interfaces as stage_interfaces,
)
from .core.stages import (
    optimize as stage_optimize,
)
from .core.stages import (
    physics as stage_physics,
)
from .core.stages import (
    rig as stage_rig,
)
from .core.stages import (
    shape as stage_shape,
)
from .core.stages import (
    surface as stage_surface,
)
from .core.stages import (
    topology as stage_topology,
)
from .core.stages import (
    uv as stage_uv,
)
from .core.stages import (
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
        repair_route_actions: Optional diagnostic repair-route actions
            that influenced the round.
        repair_route_feature_kinds: Optional feature kinds translated
            from routed construction-graph requests.
        repair_route_requests: Optional construction-graph request names
            that produced routed diagnostics.
        repair_route_lowered_operations: Optional lowered operation names
            associated with routed diagnostics.
        repair_policy_patch: Optional transient asset repair_policy patch
            used by a regenerate_with_patch round.
    """

    round_index: int
    action: str
    before_score: float
    after_score: float
    diagnostics_delta: dict[str, int]
    rollback: bool
    elapsed_ms: int
    repair_route_actions: NotRequired[list[str]]
    repair_route_feature_kinds: NotRequired[list[str]]
    repair_route_requests: NotRequired[list[str]]
    repair_route_lowered_operations: NotRequired[list[str]]
    repair_policy_patch: NotRequired[dict[str, Any]]


_SURFACE_DIAG_NAMES = {"visual_surface_authoring_quality_failed"}

_LOCAL_REPAIR_DIAG_NAMES = _SURFACE_DIAG_NAMES | {
    "semantic_quality_failed",
    "flow_quality_failed",
}

_RESELECT_SCORE_GAP = 0.05  # score within this of threshold => try reselect

# Mesh-level repair operators dispatched via ``lathe.repair_operators``. Each
# entry maps an operator name (as it appears in ``validate.repair.allow``) to
# the diagnostic-name hints that suggest it. The classifier picks the first
# allowed operator whose diagnostic hints intersect the current bundle.
_MESH_OPERATOR_HINTS: dict[str, set[str]] = {
    "enforce_symmetry": {"symmetry_violation", "asymmetric_silhouette"},
    "seal_mesh": {"non_manifold_mesh", "open_edges", "watertight_failed"},
    "retopo_auto": {"topology_quality_failed", "non_quad_dominant", "high_poly_density"},
    "reduce_tris": {"triangle_budget_exceeded", "tri_count_over_budget", "lod_budget_exceeded"},
    "repack_uvs": {"uv_packing_efficiency_low", "uv_overlap", "uv_padding_violation"},
    "rebake_maps": {"bake_transfer_failed", "normal_map_artifact", "visual_surface_authoring_quality_failed"},
    "normalize_pivots": {"pivot_misaligned", "floor_contact_offset", "pivot_policy_failed"},
    "create_collision_proxy": {"collision_proxy_missing", "physics_collision_failed"},
    "generate_lods": {"lod_chain_incomplete", "lod_missing"},
}

_ALL_MESH_OPERATORS = frozenset(_MESH_OPERATOR_HINTS.keys())
_SHAPE_REPAIR_ROUTE_ACTIONS = frozenset(
    {
        "add_secondary_features",
        "restore_edge_treatment",
        "increase_panel_depth",
        "improve_attachment_integration",
        "refine_support_layout",
        "restore_hinge_alignment",
    }
)
_REPAIR_POLICY_FEATURE_BY_OPERATION = {
    "op.trim_band": "trim_band",
    "op.fastener_grid": "fastener_grid",
    "op.vent_slats": "vent_slats",
    "op.panel_frame": "panel_frame",
    "op.inset": "inset_panel",
    "op.cut_panel_line": "panel_groove",
    "op.corner_guard_set": "corner_guard",
    "op.bracket": "support_bracket",
    "op.mount_plate": "mount_plate",
    "solid.hinge": "hinge",
    "solid.handle": "pull_handle",
    "sop.polywire": "conduit_run",
    "op.socket": "socket_point",
    "op.chip_edges": "edge_wear",
    "op.grime_mask": "grime_mask",
    "op.weld_seam": "weld_seam",
    "op.mirror": "mirror_instances",
}
_REPAIR_POLICY_FEATURE_BY_REQUEST = {
    "construction_graph.trim_band": "trim_band",
    "construction_graph.fastener_grid": "fastener_grid",
    "construction_graph.vent_slats": "vent_slats",
    "construction_graph.panel_frame": "panel_frame",
    "construction_graph.recessed_panel": "inset_panel",
    "construction_graph.panel_groove": "panel_groove",
    "construction_graph.corner_guard": "corner_guard",
    "construction_graph.support_bracket": "support_bracket",
    "construction_graph.mount_plate": "mount_plate",
    "construction_graph.latch_plate": "latch_plate",
    "construction_graph.hinge_mount_plate": "hinge",
    "construction_graph.pull_handle": "pull_handle",
    "construction_graph.conduit_run": "conduit_run",
    "construction_graph.socket_port": "socket_point",
    "construction_graph.chip_edges": "edge_wear",
    "construction_graph.grime_mask": "grime_mask",
    "construction_graph.weld_seam": "weld_seam",
    "construction_graph.mirror_instances": "mirror_instances",
    "construction_graph.edge_wear": "edge_wear",
}


def _diagnostic_repair_actions(validate_bundle: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    for diag in validate_bundle.get("diagnostics", []):
        if not isinstance(diag, dict):
            continue
        route = diag.get("repair_route")
        route = route if isinstance(route, dict) else {}
        for source in (diag.get("repair_actions"), route.get("actions")):
            if not isinstance(source, list):
                continue
            for action in source:
                action_text = str(action or "")
                if action_text:
                    actions.append(action_text)
    return list(dict.fromkeys(actions))


def _route_action_available(action: str, allowed_actions: set[str], exhausted_actions: set[str]) -> bool:
    if action == "reauthor_surface_layer":
        return action in allowed_actions and "local_repair" not in exhausted_actions
    if action in _SHAPE_REPAIR_ROUTE_ACTIONS:
        return "regenerate_with_patch" in allowed_actions and "regenerate_with_patch" not in exhausted_actions
    if action in _ALL_MESH_OPERATORS:
        return action in allowed_actions and action not in exhausted_actions
    if action in allowed_actions:
        return action not in exhausted_actions
    return False


def _classify_from_repair_routes(
    validate_bundle: dict[str, Any],
    *,
    allowed_actions: set[str],
    exhausted_actions: set[str],
) -> str | None:
    route_actions = _diagnostic_repair_actions(validate_bundle)
    if not route_actions:
        return None
    for action in route_actions:
        if action in _ALL_MESH_OPERATORS and _route_action_available(
            action,
            allowed_actions,
            exhausted_actions,
        ):
            return action
    if any(
        action in _SHAPE_REPAIR_ROUTE_ACTIONS
        and _route_action_available(action, allowed_actions, exhausted_actions)
        for action in route_actions
    ):
        return "regenerate_with_patch"
    if "reauthor_surface_layer" in route_actions and _route_action_available(
        "reauthor_surface_layer",
        allowed_actions,
        exhausted_actions,
    ):
        return "local_repair"
    return None


def _diagnostic_repair_feature_kinds(validate_bundle: dict[str, Any]) -> list[str]:
    feature_kinds: list[str] = []
    for diag in validate_bundle.get("diagnostics", []):
        if not isinstance(diag, dict):
            continue
        route = diag.get("repair_route")
        route = route if isinstance(route, dict) else {}
        operation = str(diag.get("lowered_operation") or route.get("lowered_operation") or "")
        request = str(diag.get("request") or route.get("request") or "")
        for kind in (
            _REPAIR_POLICY_FEATURE_BY_REQUEST.get(request, ""),
            _REPAIR_POLICY_FEATURE_BY_OPERATION.get(operation, ""),
        ):
            if kind:
                feature_kinds.append(kind)
    return list(dict.fromkeys(feature_kinds))


def _diagnostic_repair_policy_patch(validate_bundle: dict[str, Any]) -> dict[str, Any]:
    route_actions = [
        action
        for action in _diagnostic_repair_actions(validate_bundle)
        if action in _SHAPE_REPAIR_ROUTE_ACTIONS
    ]
    if not route_actions:
        return {}
    feature_kinds = _diagnostic_repair_feature_kinds(validate_bundle)
    lowered_operations: list[str] = []
    requests: list[str] = []
    for diag in validate_bundle.get("diagnostics", []):
        if not isinstance(diag, dict):
            continue
        route = diag.get("repair_route")
        route = route if isinstance(route, dict) else {}
        operation = str(diag.get("lowered_operation") or route.get("lowered_operation") or "")
        if operation:
            lowered_operations.append(operation)
        request = str(diag.get("request") or route.get("request") or "")
        if request:
            requests.append(request)
    return {
        "use": "construction_graph_repair_route",
        "mode": "regenerate_with_patch",
        "allow": list(dict.fromkeys([*feature_kinds, *route_actions])),
        "source": "validate.diagnostics.repair_route",
        "requests": list(dict.fromkeys(requests)),
        "lowered_operations": list(dict.fromkeys(lowered_operations)),
    }


def _diagnostic_repair_route_trace(validate_bundle: dict[str, Any]) -> dict[str, Any]:
    """Return reportable repair-route fields derived from validate diagnostics."""
    route_actions = _diagnostic_repair_actions(validate_bundle)
    feature_kinds = _diagnostic_repair_feature_kinds(validate_bundle)
    lowered_operations: list[str] = []
    requests: list[str] = []
    for diag in validate_bundle.get("diagnostics", []):
        if not isinstance(diag, dict):
            continue
        route = diag.get("repair_route")
        route = route if isinstance(route, dict) else {}
        operation = str(diag.get("lowered_operation") or route.get("lowered_operation") or "")
        if operation:
            lowered_operations.append(operation)
        request = str(diag.get("request") or route.get("request") or "")
        if request:
            requests.append(request)
    trace: dict[str, Any] = {}
    if route_actions:
        trace["repair_route_actions"] = route_actions
    if feature_kinds:
        trace["repair_route_feature_kinds"] = feature_kinds
    if requests:
        trace["repair_route_requests"] = list(dict.fromkeys(requests))
    if lowered_operations:
        trace["repair_route_lowered_operations"] = list(dict.fromkeys(lowered_operations))
    return trace


def _attach_repair_route_trace(
    round_trace: dict[str, Any],
    route_trace: dict[str, Any],
    *,
    repair_policy_patch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Attach optional route metadata to a repair round trace."""
    if route_trace:
        round_trace.update(route_trace)
    if repair_policy_patch:
        round_trace["repair_policy_patch"] = repair_policy_patch
    return round_trace


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
    1. A diagnostic ``repair_route`` when it maps to an allowed action.
    2. ``local_repair`` when a surface diagnostic is present and
       ``reauthor_surface_layer`` is allowed.
    3. ``reselect_candidate`` when the score is within
       ``_RESELECT_SCORE_GAP`` of the threshold.
    4. ``regenerate_with_patch`` when diagnostics span multiple classes
       (systemic failure).
    5. ``reselect_candidate`` as a general fallback.
    6. ``local_repair`` for any local-repair-class diagnostic.
    7. ``noop_exhausted`` if nothing above applies.

    An action previously recorded as ``exhausted`` (e.g. local_repair
    was tried and rolled back) is skipped so the loop can escalate to
    the next action class.
    """
    score = float(validate_bundle.get("score", 0.0))
    diag_names = {
        d.get("name") for d in validate_bundle.get("diagnostics", []) if d.get("severity") == "error"
    }
    has_surface_diag = bool(diag_names & _SURFACE_DIAG_NAMES)
    distinct_classes = len({name for name in diag_names if name})

    def available(action: str) -> bool:
        return action not in exhausted_actions

    routed_action = _classify_from_repair_routes(
        validate_bundle,
        allowed_actions=allowed_actions,
        exhausted_actions=exhausted_actions,
    )
    if routed_action is not None:
        return routed_action

    if has_surface_diag and "reauthor_surface_layer" in allowed_actions and available("local_repair"):
        return "local_repair"
    # Mesh-level operators with a matching diagnostic hint take priority
    # over the cheap reselect fallback — when the asset has declared a
    # targeted operator (e.g. ``seal_mesh`` for ``non_manifold_mesh``),
    # we should run it before retrying with another candidate.
    for op_name, hints in _MESH_OPERATOR_HINTS.items():
        if op_name in allowed_actions and (diag_names & hints) and available(op_name):
            return op_name
    if (
        threshold - score <= _RESELECT_SCORE_GAP
        and "reselect_candidate" in allowed_actions
        and available("reselect_candidate")
    ):
        return "reselect_candidate"
    if (
        distinct_classes >= 2
        and "regenerate_with_patch" in allowed_actions
        and available("regenerate_with_patch")
    ):
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
    # Last-ditch fallback: any allowed mesh operator that hasn't been tried,
    # even without a diagnostic-name match. Useful when diagnostics are
    # generic (semantic_quality_failed) but the asset declares specific
    # mesh repairs to attempt.
    for op_name in _MESH_OPERATOR_HINTS:
        if op_name in allowed_actions and available(op_name):
            return op_name
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


def _execute_mesh_operator(executor: Any, op_name: str) -> dict[str, Any] | None:
    """Run a mesh-level repair operator, then re-run downstream stages.

    Returns the new validate bundle, or None if the operator did not apply
    a change (in which case the loop will roll back / mark exhausted).
    """
    from .repair_operators import dispatch_operator

    result = dispatch_operator(op_name, executor)
    if not result.applied_change:
        return None
    # Record the operator trace under shape runtime for observability.
    shape_runtime = executor.runtime.setdefault("shape", {})
    op_trace = shape_runtime.setdefault("repair_operator_trace", [])
    op_trace.append(
        {
            "operator": op_name,
            "score_delta_estimate": result.score_delta_estimate,
            "evidence": result.evidence,
            "error": result.error,
        }
    )
    # Choose the appropriate downstream restart point based on the operator.
    # Operators that mutate UV/topology meshes restart from UV; the topology
    # operator restarts from UV as well since it ran topology already.
    topology_bundle = executor.runtime.get("topology", {}).get("bundle")
    if topology_bundle is None:
        return None
    if op_name in {"rebake_maps", "repack_uvs"}:
        # repack_uvs already re-ran the UV stage; rebake_maps already
        # re-ran surface. Pick up downstream from the relevant bundle.
        if op_name == "repack_uvs":
            uv_bundle = executor.runtime.get("uv", {}).get("bundle") or topology_bundle
            surface_bundle = stage_surface.run(executor, uv_bundle)
        else:
            surface_bundle = executor.runtime.get("surface", {}).get("bundle")
            if surface_bundle is None:
                return None
        rig_bundle = stage_rig.run(executor, surface_bundle)
        interfaces_bundle = stage_interfaces.run(executor, rig_bundle)
        physics_bundle = stage_physics.run(executor, interfaces_bundle)
        optimize_bundle = stage_optimize.run(executor, physics_bundle)
        return stage_validate.run(executor, optimize_bundle)
    # All other mesh-mutating operators restart from UV.
    try:
        return _run_downstream_after_topology(executor, topology_bundle)
    except Exception:
        return None


def _execute_regenerate_with_patch(
    executor: Any,
    round_index: int,
    validate_bundle: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Apply a patch to the runtime_config and re-run shape → validate.

    The patch bumps a shape-stage nonce so the provider re-seeds its
    candidate search, and sets ``shape.repair_nonce`` to the round index
    so the trace is observable.
    """
    shape_cfg = executor.runtime_config.setdefault("shape", {})
    shape_cfg["repair_nonce"] = round_index
    policy_patch = _diagnostic_repair_policy_patch(validate_bundle or {})
    previous_policy = copy.deepcopy(executor.asset.get("repair_policy", {}))
    if policy_patch:
        merged_policy = {
            **(previous_policy if isinstance(previous_policy, dict) else {}),
            **policy_patch,
        }
        merged_policy["allow"] = list(
            dict.fromkeys(
                [
                    *(
                        previous_policy.get("allow", [])
                        if isinstance(previous_policy, dict) and isinstance(previous_policy.get("allow"), list)
                        else []
                    ),
                    *policy_patch["allow"],
                ]
            )
        )
        executor.asset["repair_policy"] = merged_policy
    try:
        shape_bundle = stage_shape.run(executor)
    except Exception:
        return None
    finally:
        if policy_patch:
            if previous_policy:
                executor.asset["repair_policy"] = previous_policy
            else:
                executor.asset.pop("repair_policy", None)
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
        for diag in validate_bundle.get("diagnostics", []):
            if not isinstance(diag, dict):
                continue
            if not diag.get("repair_route") and not diag.get("repair_actions"):
                continue
            name = diag.get("name") or diag.get("code")
            if name:
                counts[str(name)] = counts.get(str(name), 0) + 1
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
        allowed_actions = {"reauthor_surface_layer", "reselect_candidate", "regenerate_with_patch"}

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
        repair_policy_patch = _diagnostic_repair_policy_patch(current_bundle)
        repair_route_trace = _diagnostic_repair_route_trace(current_bundle)

        action = _classify(
            current_bundle,
            threshold,
            allowed_actions=allowed_actions,
            exhausted_actions=exhausted_actions,
        )
        if action == "noop_exhausted":
            rounds.append(
                _attach_repair_route_trace(
                    {
                        "round_index": round_index,
                        "action": action,
                        "before_score": before_score,
                        "after_score": before_score,
                        "diagnostics_delta": {},
                        "rollback": False,
                        "elapsed_ms": max(1, int((time.monotonic() - round_start) * 1000)),
                    },
                    repair_route_trace,
                )
            )
            break

        snapshot = _snapshot_runtime(executor)
        new_bundle: dict[str, Any] | None
        if action == "local_repair":
            new_bundle = _execute_local_repair(executor)
        elif action == "reselect_candidate":
            new_bundle = _execute_reselect(executor, attempted_candidates)
        elif action == "regenerate_with_patch":
            new_bundle = _execute_regenerate_with_patch(executor, round_index, current_bundle)
        elif action in _ALL_MESH_OPERATORS:
            new_bundle = _execute_mesh_operator(executor, action)
        else:
            new_bundle = None

        elapsed_ms = max(1, int((time.monotonic() - round_start) * 1000))

        if new_bundle is None:
            _restore_runtime(executor, snapshot)
            exhausted_actions.add(action)
            rounds.append(
                _attach_repair_route_trace(
                    {
                        "round_index": round_index,
                        "action": action,
                        "before_score": before_score,
                        "after_score": before_score,
                        "diagnostics_delta": {},
                        "rollback": True,
                        "elapsed_ms": elapsed_ms,
                    },
                    repair_route_trace,
                    repair_policy_patch=repair_policy_patch if action == "regenerate_with_patch" else None,
                )
            )
            continue

        after_score = float(new_bundle.get("score", 0.0))
        after_counts = _diagnostic_name_counts(new_bundle)
        delta = _diagnostics_delta(before_counts, after_counts)

        score_improved = (after_score - before_score) >= min_improvement
        trigger_reduced = trigger_class is not None and after_counts.get(
            trigger_class, 0
        ) < before_counts.get(trigger_class, 0)
        certified = bool(new_bundle.get("certified"))
        accept = certified or score_improved or trigger_reduced

        if accept:
            current_bundle = new_bundle
            round_trace: dict[str, Any] = {
                "round_index": round_index,
                "action": action,
                "before_score": before_score,
                "after_score": after_score,
                "diagnostics_delta": delta,
                "rollback": False,
                "elapsed_ms": elapsed_ms,
            }
            rounds.append(
                _attach_repair_route_trace(
                    round_trace,
                    repair_route_trace,
                    repair_policy_patch=repair_policy_patch if action == "regenerate_with_patch" else None,
                )
            )
            if certified:
                break
        else:
            _restore_runtime(executor, snapshot)
            exhausted_actions.add(action)
            round_trace = {
                "round_index": round_index,
                "action": action,
                "before_score": before_score,
                "after_score": after_score,
                "diagnostics_delta": delta,
                "rollback": True,
                "elapsed_ms": elapsed_ms,
            }
            rounds.append(
                _attach_repair_route_trace(
                    round_trace,
                    repair_route_trace,
                    repair_policy_patch=repair_policy_patch if action == "regenerate_with_patch" else None,
                )
            )

    return current_bundle, rounds


__all__ = ["RepairRound", "run_repair_loop"]
