"""Sprint 0 S0-5 — visible edge-treatment coverage diagnostic.

Detects the "looks like procedural blockout" failure mode the
northstar §8 names: a hard-surface body that ships zero bevel /
chamfer / edge_treatment ops in its ShapeProgram and zero
``edge_treatment_count`` in its shape_assessment, despite carrying
enough face area to make visible 90° edges glaringly obvious.

This diagnostic is intentionally NOT satisfied by candidate
reselection: it inspects the FINAL certified candidate's shape
assessment. If the chosen candidate has no edge treatment ops, the
diagnostic fires regardless of which candidate the build picked.
This is the gap the prior ``toy_or_primitive_detected`` semantic
validator left open — it gets resolved when a better-scored
candidate is picked, even if that candidate is still visibly
blockout.

The diagnostic is reusable beyond ``industrial_crate``: any
hard-surface prop with a primary body and >= ``_FACE_COUNT_FLOOR``
faces fires it when edge_treatment_count is zero. Sphere-only
shapes are exempt (they have no straight edges to treat).
"""

from __future__ import annotations

from typing import Any

VERSION = "lathe.validate.edge_treatment_coverage_v1"


# Below this face count, the asset is small / detail-only and a
# zero-bevel state is not a visible-blockout failure mode.
_FACE_COUNT_FLOOR = 200

# Asset kinds that the diagnostic activates against. Hard-surface and
# mechanical props with rectilinear primary volumes benefit most
# from edge treatment; vegetation / organic / fluid assets don't.
_HARD_SURFACE_KINDS: frozenset[str] = frozenset(
    {
        "hard_surface_prop",
        "mechanical_prop",
        "industrial_prop",
        "container",
        "weapon_prop",
    }
)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _asset_kind(asset: dict[str, Any]) -> str:
    intent = _as_dict(asset.get("intent"))
    raw = intent.get("kind") or asset.get("kind")
    if isinstance(raw, str):
        return raw.strip().lower()
    return ""


def _shape_assessment_for_runtime(runtime: dict[str, Any]) -> dict[str, Any]:
    shape = _as_dict(runtime.get("shape"))
    bundle = _as_dict(shape.get("bundle"))
    candidates = bundle.get("runtime_candidates")
    if isinstance(candidates, list) and candidates:
        first = candidates[0]
        if isinstance(first, dict):
            meta = _as_dict(first.get("meta"))
            assessment = _as_dict(meta.get("shape_assessment"))
            if assessment:
                return assessment
    return _as_dict(bundle.get("shape_assessment"))


def _shape_program_for_runtime(runtime: dict[str, Any]) -> dict[str, Any]:
    """Return the ShapeProgram dict from the runtime, or empty.

    Looks at three locations in priority order:
      1. ``runtime["shape"]["bundle"]["shape_program"]``
      2. ``runtime["grammar_lowering"]["shape_program"]``
      3. ``runtime["shape"]["bundle"]["runtime_candidates"][0]["meta"]["shape_program"]``
    """
    shape = _as_dict(runtime.get("shape"))
    bundle = _as_dict(shape.get("bundle"))
    program = bundle.get("shape_program")
    if isinstance(program, dict):
        return program
    grammar = _as_dict(runtime.get("grammar_lowering"))
    program = grammar.get("shape_program")
    if isinstance(program, dict):
        return program
    candidates = bundle.get("runtime_candidates")
    if isinstance(candidates, list) and candidates:
        first = candidates[0]
        if isinstance(first, dict):
            meta = _as_dict(first.get("meta"))
            program = meta.get("shape_program")
            if isinstance(program, dict):
                return program
    return {}


def _count_edge_treatment_ops(program: dict[str, Any]) -> int:
    ops = program.get("ops")
    if not isinstance(ops, (list, tuple)):
        return 0
    count = 0
    for op in ops:
        if not isinstance(op, dict):
            continue
        op_name = op.get("op")
        if op_name in ("op.bevel", "op.chamfer", "sop.polybevel"):
            count += 1
    return count


def _final_face_count(runtime: dict[str, Any]) -> int:
    topology = _as_dict(runtime.get("topology"))
    bundle = _as_dict(topology.get("bundle"))
    mesh_stats = _as_dict(bundle.get("mesh_stats"))
    raw = mesh_stats.get("triangle_count") or mesh_stats.get("face_count")
    if isinstance(raw, int) and raw > 0:
        return raw
    # Fallback: sum part_groups face_count
    groups = bundle.get("part_groups")
    if isinstance(groups, list):
        return sum(
            int(g.get("face_count") or 0)
            for g in groups
            if isinstance(g, dict)
        )
    return 0


def evaluate_edge_treatment_coverage(
    asset: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    """Evaluate edge-treatment coverage for a hard-surface body.

    Returns an additive payload with ``version``, ``metrics``, and a
    ``diagnostics`` list (empty when no failure). The diagnostic
    record carries a ``suggested_repairs`` list naming the concrete
    actions the repair planner can take (see S0-6 wiring).
    """
    asset_kind = _asset_kind(asset)
    program = _shape_program_for_runtime(runtime)
    shape_assessment = _shape_assessment_for_runtime(runtime)
    face_count = _final_face_count(runtime)
    op_treatment_count = _count_edge_treatment_ops(program)
    assessment_treatment_count = int(shape_assessment.get("edge_treatment_count") or 0)

    metrics: dict[str, Any] = {
        "asset_kind": asset_kind,
        "face_count": face_count,
        "shape_op_treatment_count": op_treatment_count,
        "shape_assessment_edge_treatment_count": assessment_treatment_count,
    }

    diagnostics: list[dict[str, Any]] = []

    activates = (
        asset_kind in _HARD_SURFACE_KINDS
        and face_count >= _FACE_COUNT_FLOOR
        and op_treatment_count == 0
        and assessment_treatment_count == 0
    )
    metrics["fires"] = activates

    if activates:
        diagnostics.append(
            {
                "code": "L6402",
                "name": "no_visible_edge_treatment_on_hard_surface_body",
                "severity": "warning",
                "phase": "validate",
                "stage": "validate",
                "asset": asset.get("name"),
                "path": "validate.edge_treatment_coverage",
                "message": (
                    f"Hard-surface asset ({asset_kind!r}) with "
                    f"{face_count} faces ships ZERO bevel / chamfer / "
                    f"polybevel ops and zero edge_treatment_count in "
                    f"shape_assessment. Every visible edge is a hard "
                    f"90°. This is the northstar §8 'looks like "
                    f"procedural blockout' failure mode and is NOT "
                    f"satisfied by candidate reselection — only by "
                    f"adding real edge treatment."
                ),
                "details": dict(metrics),
                # Primary suggested action uses the existing repair
                # vocabulary (``restore_edge_treatment``) so the repair
                # planner can apply it without learning a new name. The
                # additional names are aspirational / S0-6 follow-up:
                # apply_bevel_to_hard_edges would emit op.bevel directly
                # in the next pass; switch_style_pack_to_beveled_default
                # would patch the style pack the alias points at.
                "suggested_repairs": [
                    "restore_edge_treatment",
                    "apply_bevel_to_hard_edges",
                    "switch_style_pack_to_beveled_default",
                ],
                # repair_actions is the field the repair_loop reads
                # for diagnostic-driven routing. restore_edge_treatment
                # is in repair_loop's _SHAPE_REPAIR_ROUTE_ACTIONS.
                "repair_actions": ["restore_edge_treatment"],
            }
        )

    return {
        "version": VERSION,
        "metrics": metrics,
        "diagnostics": diagnostics,
    }
