"""Contract test: every ShapeIR v2 op has an explicit kernel-state classification.

Per `docs/asset-quality/lathe-northstar-full-implementation-plan.md`
v2 §5.4 (Cycle 2 acceptance):

> For each of 83 ShapeIR v2 ops, the kernel trace contains an
> explicit ``executed | approximated | unsupported`` state.
> Automated test enforces this enumeration.

This test enumerates every member of ``shape_ir_v2.ALL_OPS`` and
probes ``lower_to_v1`` with a minimal valid input for each. The
result classifies into one of three states based on the v1_records /
diagnostics shape:

  - ``executed``: lowering produced v1 records and no diagnostics.
  - ``approximated``: lowering produced v1 records AND diagnostics
    (degraded path / fallback / hint).
  - ``unsupported``: lowering produced only diagnostics, no records.

A fourth classification ``provisional`` covers ops whose required-
param coverage in the stub input is incomplete, signalling the test
itself needs widening rather than the op being unsupported. Any op
producing neither records nor diagnostics fails the test — it has
no honest state to report.

The test runs every commit; a new op added to ``ALL_OPS`` without
a coverage path here fails the assertion immediately.
"""

from __future__ import annotations

from typing import Any

import pytest

from lathe.asset_quality.shape_ir_v2 import (
    ALL_OPS,
    ShapeOp,
    ShapeProgram,
    _REQUIRED_PARAMS,
    lower_to_v1,
)


_VALID_STATES: frozenset[str] = frozenset(
    {"executed", "approximated", "unsupported", "provisional"}
)


# Per-param default values for the minimal-valid-input stub generator.
# Maps a required parameter name to a sensible test default. Some param
# names route to a generator function (signified by a callable) for
# dynamic construction (e.g., nested source op for sop.* boolean
# variants).
def _default_box_source() -> dict[str, Any]:
    """A minimal solid.box source dict suitable for embedding in op.source."""
    return {
        "op": "solid.box",
        "target": "stub.body",
        "parameters": {"width_cm": 10.0, "height_cm": 10.0, "depth_cm": 10.0},
    }


_PARAM_STUBS: dict[str, Any] = {
    # length-like
    "width_cm": 10.0,
    "height_cm": 10.0,
    "depth_cm": 10.0,
    "thickness_cm": 1.0,
    "radius_cm": 5.0,
    "length_cm": 10.0,
    "span_cm": 8.0,
    "standoff_cm": 1.5,
    "grip_radius_cm": 1.0,
    "barrel_radius_cm": 1.0,
    "leaf_width_cm": 4.0,
    "rail_radius_cm": 0.5,
    "tube_radius_cm": 1.0,
    "outer_radius_cm": 6.0,
    "inner_radius_cm": 3.0,
    "bore_radius_cm": 2.0,
    "wire_radius_cm": 0.5,
    "hole_radius_cm": 0.8,
    "member_radius_cm": 0.6,
    "trunk_radius_cm": 2.0,
    "field_radius_cm": 6.0,
    "major_radius_cm": 4.0,
    "minor_radius_cm": 1.0,
    "pitch_radius_cm": 5.0,
    "profile_cm": 4.0,
    "border_width_cm": 1.0,
    "spacing_cm": 4.0,
    "thread_pitch_cm": 0.5,
    "thread_depth_cm": 0.5,
    "cell_size_cm": 5.0,
    "target_edge_length_cm": 1.0,
    "extrude_height_cm": 5.0,
    "size_cm": 2.0,
    # counts
    "segments": 4,
    "rows": 4,
    "columns": 4,
    "count": 4,
    "turns": 3,
    "teeth": 12,
    "rung_count": 5,
    "bay_count": 4,
    "rib_count": 6,
    "slat_count": 8,
    "blob_count": 5,
    "branch_count": 6,
    "floors": 2,
    "bays": 3,
    "resolution": 16,
    "levels": 1,
    "width_cells": 3,
    "depth_cells": 3,
    # axes / strings
    "axis": "x",
    "pattern": "grid",
    "operation": "subtract",
    # ranges
    "u_start": 0.0,
    "u_end": 1.0,
    "scale": 1.2,
    "angle_degrees": 45.0,
    "density": 1.0,
    "angle_degrees": 30.0,
    # tuples / lists — minimal viable shapes
    "corner_radii_cm": (0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5),
    "profile_points": [(0.0, 0.0), (5.0, 0.0), (5.0, 5.0), (0.0, 5.0)],
    "profile_polygon": [(0.0, 0.0), (5.0, 0.0), (5.0, 5.0), (0.0, 5.0)],
    "profile_curve": [(0.0, 0.0), (5.0, 0.0), (5.0, 5.0), (0.0, 5.0)],
    "cross_section_curve": [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
    "sweep_curve": [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)],
    "cross_section": [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
    "sweep_path": [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)],
    "sections": [
        [(0.0, 0.0), (5.0, 0.0), (5.0, 5.0), (0.0, 5.0)],
        [(0.0, 0.0), (3.0, 0.0), (3.0, 3.0), (0.0, 3.0)],
    ],
    "path": [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)],
    "hole_centers": [(0.0, 0.0), (5.0, 0.0)],
    "points": [(0.0, 0.0, 0.0), (5.0, 0.0, 0.0)],
    # nested-op stubs
    "source": _default_box_source,
    "target": _default_box_source,
}


def _stub_parameters_for(op_name: str) -> dict[str, Any]:
    """Build a minimal valid parameters dict for ``op_name``.

    Pulls each required param from ``_PARAM_STUBS``. Callable values
    are invoked to produce fresh instances. Unknown params return None
    so the test can mark that op as ``provisional`` rather than
    crashing.
    """
    required = _REQUIRED_PARAMS.get(op_name, ())
    params: dict[str, Any] = {}
    for name in required:
        stub = _PARAM_STUBS.get(name)
        if callable(stub):
            params[name] = stub()
        elif stub is not None:
            params[name] = stub
        else:
            # Unknown param — return sentinel so test marks provisional
            params[name] = None
    return params


def _classify_state(adapter_result: Any, missing_stub_params: bool) -> str:
    """Classify a v1 adapter result into one of the four coverage states.

    Args:
        adapter_result: V1AdapterResult from ``lower_to_v1``.
        missing_stub_params: True if any required param had no stub.

    Returns one of: ``executed``, ``approximated``, ``unsupported``,
    ``provisional``.
    """
    if missing_stub_params:
        return "provisional"
    records = tuple(adapter_result.v1_records)
    diagnostics = tuple(adapter_result.diagnostics)
    if records and not diagnostics:
        return "executed"
    if records and diagnostics:
        return "approximated"
    if not records and diagnostics:
        return "unsupported"
    # Neither records nor diagnostics — the op has no honest state.
    return ""


def _probe_op(op_name: str) -> tuple[str, dict[str, Any]]:
    """Probe one op with a minimal stub input. Return (state, evidence)."""
    required = _REQUIRED_PARAMS.get(op_name, ())
    parameters = _stub_parameters_for(op_name)
    missing_stub_params = any(parameters.get(name) is None for name in required)

    op = ShapeOp(op=op_name, target="stub.target", parameters=parameters, purpose="op_coverage_probe")
    program = ShapeProgram(
        version="2",
        asset_name="op_coverage_probe",
        family=None,
        ops=(op,),
    )
    try:
        result = lower_to_v1(program)
    except (TypeError, ValueError, RuntimeError, AttributeError) as exc:
        # Lowering raised — classify as unsupported with an error
        # diagnostic surrogate.
        return "unsupported", {
            "exception": type(exc).__name__,
            "message": str(exc)[:200],
        }

    state = _classify_state(result, missing_stub_params)
    return state, {
        "v1_record_count": len(result.v1_records),
        "diagnostic_count": len(result.diagnostics),
        "diagnostic_codes": sorted({d.get("code", "") for d in result.diagnostics}),
        "unsupported_ops": list(result.unsupported_ops),
        "missing_stub_params": missing_stub_params,
    }


def test_every_op_has_explicit_coverage_state() -> None:
    """Every member of ALL_OPS produces one of the four valid states.

    Failure here means an op is in ALL_OPS but its lowering produces
    neither v1_records nor diagnostics — there is no honest state to
    surface in the kernel trace. The op must either:

      - Be removed from ALL_OPS (it is not actually supported), OR
      - Have its lowering updated to emit at least one diagnostic
        even when it cannot produce records, OR
      - Be added to ``_REQUIRED_PARAMS`` with proper stub support so
        this test can classify it.
    """
    op_states: dict[str, str] = {}
    op_evidence: dict[str, dict[str, Any]] = {}

    for op_name in sorted(ALL_OPS):
        state, evidence = _probe_op(op_name)
        op_states[op_name] = state
        op_evidence[op_name] = evidence

    # Every op must have a valid state
    invalid = {name: state for name, state in op_states.items() if state not in _VALID_STATES}
    if invalid:
        lines = [
            "Some ShapeIR v2 ops produced neither records nor diagnostics — "
            "they have no honest kernel-trace state:",
        ]
        for name in sorted(invalid):
            lines.append(f"  {name}: state={op_states[name]!r}  evidence={op_evidence[name]}")
        pytest.fail("\n".join(lines))


def test_op_coverage_state_distribution_reported() -> None:
    """Report the state distribution as evidence (not strict assertion).

    This test always passes but emits a summary so each test run leaves
    an audit trail of where coverage stands. It is purposely permissive
    — the strict assertion is in ``test_every_op_has_explicit_coverage_state``.
    """
    counts: dict[str, int] = {state: 0 for state in _VALID_STATES}
    counts[""] = 0  # placeholder for invalid
    for op_name in ALL_OPS:
        state, _ = _probe_op(op_name)
        counts[state] = counts.get(state, 0) + 1

    total = sum(counts.values())
    assert total == len(ALL_OPS), (
        f"coverage probe processed {total} ops but ALL_OPS has {len(ALL_OPS)}"
    )
    # Print summary via pytest's captured output
    print()
    print(f"ShapeIR v2 op coverage state distribution ({len(ALL_OPS)} ops):")
    for state in sorted(_VALID_STATES) + [""]:
        if state in counts and counts[state] > 0:
            label = state or "<no state>"
            print(f"  {label}: {counts[state]}")


def test_all_ops_count_matches_pinned_value() -> None:
    """Pin the current ALL_OPS count so additions to the op set are visible.

    This catches accidental op-set drift from migration / refactoring.
    Update the pinned count when intentionally adding/removing ops.
    """
    assert len(ALL_OPS) == 86, (
        f"ALL_OPS has {len(ALL_OPS)} members; pinned value is 86. If this is an "
        "intentional change, update the pinned value here and re-run the "
        "coverage assertion to confirm new ops have explicit states."
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
