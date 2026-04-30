"""Phase 6 tests for ``lathe.asset_quality.grammar_lowering``.

Covers per task #6 of ``docs/asset-quality/improvement-tasklist.md``:

- ``RecipeResult`` is frozen.
- The industrial_crate recipe lowers all 10 grammar requirements into
  the expected v2 op names + synthesized graph nodes.
- Each ``ShapeOp`` carries a ``purpose`` string (none are ``None`` /
  empty).
- Synthesized ``node_type`` values are members of Phase 4's
  ``NODE_TYPES`` frozenset.
- Coverage improves: starting from the baseline parts list, merging the
  recipe's synthesized graph nodes into the construction graph
  strictly raises the ``family_grammar`` coverage value (predicted
  0.40 -> 0.70).
- The validator entry point's payload shape is exactly the seven keys
  declared in the master prompt.
- The validator never adds a top-level ``diagnostics`` key (informational
  contract — mirrors Phases 1 through 5).
- ``lower_to_v1`` on the recipe produces exactly 1 v1 record (the body
  ``solid.box``) plus per-op ``no_v1_equivalent`` diagnostics.
- The recipe is deterministic across calls.
- A generic family falls back to an empty program + zero synthesized
  nodes.
- A missing ``runtime["construction_graph"]`` block does not crash.
- A missing ``runtime["design_brief"]`` block falls back to ``generic``.
- ``shape_program_summary.op_count`` matches ``len(shape_program.ops)``.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from lathe.asset_quality.construction_graph import NODE_TYPES
from lathe.asset_quality.family_grammar import evaluate_family_grammar
from lathe.asset_quality.grammar_lowering import (
    GRAMMAR_LOWERING_VERSION,
    RecipeResult,
    evaluate_grammar_lowering,
    industrial_crate_recipe,
)
from lathe.asset_quality.shape_ir_v2 import (
    ALL_OPS,
    SHAPE_IR_V2_VERSION,
    ShapeProgram,
    lower_to_v1,
)


_BASELINE_PARTS: tuple[str, ...] = (
    "body",
    "latch_plate",
    "handle_l",
    "handle_r",
    "foot_l",
    "foot_r",
)


_BASELINE_GRAPH_NODES: tuple[dict[str, Any], ...] = (
    {"node_id": "body", "node_type": "primary_volume", "attributes": {}},
    {"node_id": "latch_plate", "node_type": "inset", "attributes": {}},
    {"node_id": "handle_l", "node_type": "handle", "attributes": {}},
    {"node_id": "handle_r", "node_type": "handle", "attributes": {}},
    {"node_id": "foot_l", "node_type": "mount", "attributes": {}},
    {"node_id": "foot_r", "node_type": "mount", "attributes": {}},
)


_EXPECTED_PAYLOAD_KEYS: frozenset[str] = frozenset(
    {
        "version",
        "family",
        "shape_program",
        "shape_program_summary",
        "synthesized_graph_nodes",
        "synthesized_node_count",
        "v1_lowering",
    }
)


_EXPECTED_OP_NAMES: tuple[str, ...] = (
    "solid.box",
    "op.inset",
    "op.cut_panel_line",
    "op.corner_guard_set",
    "op.mount_plate",
    "op.socket",
    "op.socket",
    "solid.rail",
    "solid.rail",
    "op.trim_band",
    "op.fastener_grid",
    "op.repeat",
    "op.chip_edges",
)


def _crate_runtime(
    graph_nodes: tuple[dict[str, Any], ...] | None = None,
) -> dict[str, Any]:
    """Build a runtime that publishes a Phase 2 brief + Phase 4 graph."""
    runtime: dict[str, Any] = {
        "design_brief": {"brief": {"family": "industrial_crate"}},
    }
    if graph_nodes is not None:
        runtime["construction_graph"] = {"nodes": list(graph_nodes)}
    return runtime


def _crate_asset() -> dict[str, Any]:
    return {
        "name": "industrial_crate",
        "intent": {"parts": list(_BASELINE_PARTS)},
    }


def test_recipe_result_dataclass_is_frozen() -> None:
    result = industrial_crate_recipe(brief={}, parts=(), graph_nodes=())
    assert isinstance(result, RecipeResult)
    with pytest.raises(FrozenInstanceError):
        result.family = "other"  # type: ignore[misc]


def test_grammar_lowering_version_constant() -> None:
    assert GRAMMAR_LOWERING_VERSION == "grammar_lowering_v1"


def test_industrial_crate_recipe_emits_expected_v2_op_names_in_order() -> None:
    """The recipe must emit ops keyed off the 10 industrial_crate
    requirements in declaration order. Locks the canonical lowering."""
    result = industrial_crate_recipe(brief={}, parts=(), graph_nodes=())

    op_names = tuple(op.op for op in result.shape_program.ops)
    assert op_names == _EXPECTED_OP_NAMES
    assert len(op_names) == 13


def test_industrial_crate_recipe_synthesizes_expected_node_types_by_count() -> None:
    """Per the master-prompt mapping table:

    - 1 primary_volume (body_shell)
    - 1 panel (lid_seam)
    - 8 guards (corner_guards, one per body corner)
    - 1 inset (latch_plate)
    - 2 handles (recessed_or_bracketed_handles)
    - 2 rails (foot_rails_or_feet)
    - 1 trim (trim_bands)
    - 1 fastener (fasteners)
    - 1 decal_zone (warning_or_decal_zones)
    - 1 wear_zone (edge_wear_masks)

    Total: 19 synthesized graph nodes.
    """
    result = industrial_crate_recipe(brief={}, parts=(), graph_nodes=())

    counts: dict[str, int] = {}
    for node in result.synthesized_graph_nodes:
        node_type = node["node_type"]
        counts[node_type] = counts.get(node_type, 0) + 1

    assert counts == {
        "primary_volume": 1,
        "panel": 1,
        "guard": 8,
        "inset": 1,
        "handle": 2,
        "rail": 2,
        "trim": 1,
        "fastener": 1,
        "decal_zone": 1,
        "wear_zone": 1,
    }
    assert len(result.synthesized_graph_nodes) == 19


def test_every_op_carries_a_non_empty_purpose_string() -> None:
    result = industrial_crate_recipe(brief={}, parts=(), graph_nodes=())

    for op in result.shape_program.ops:
        assert op.purpose is not None, f"Op {op.op} missing purpose"
        assert isinstance(op.purpose, str)
        assert op.purpose, f"Op {op.op} has empty purpose"


def test_synthesized_node_types_are_members_of_phase_4_node_types() -> None:
    """Every recipe synthesized node must use a ``node_type`` from Phase 4's
    ``NODE_TYPES`` frozenset so a future opt-in merger can drop the
    synthesized nodes into the live construction graph without
    translation."""
    result = industrial_crate_recipe(brief={}, parts=(), graph_nodes=())

    used = {node["node_type"] for node in result.synthesized_graph_nodes}
    unknown = used - NODE_TYPES
    assert not unknown, f"Recipe nodes use unknown node types: {sorted(unknown)}"


def test_synthesized_node_ids_mirror_requirement_origin() -> None:
    """Per spec the recipe's node ids start with ``recipe.`` and reference
    the triggering requirement (e.g. ``recipe.body_shell``,
    ``recipe.corner_guard_0`` ... ``recipe.corner_guard_7``,
    ``recipe.handle_l``, ``recipe.handle_r``)."""
    result = industrial_crate_recipe(brief={}, parts=(), graph_nodes=())

    node_ids = {node["node_id"] for node in result.synthesized_graph_nodes}
    for node_id in node_ids:
        assert node_id.startswith("recipe."), (
            f"Node id {node_id!r} should start with 'recipe.'"
        )
    assert "recipe.body_shell" in node_ids
    assert "recipe.handle_l" in node_ids
    assert "recipe.handle_r" in node_ids
    for index in range(8):
        assert f"recipe.corner_guard_{index}" in node_ids


def test_unknown_family_returns_empty_program_and_zero_nodes() -> None:
    """Families not yet covered by a Phase 6 recipe (everything other
    than ``industrial_crate``) must fall back to an empty
    :class:`ShapeProgram` with no synthesized nodes."""
    runtime = {"design_brief": {"brief": {"family": "mechanical_door"}}}
    asset = {"name": "mechanical_door", "intent": {"parts": []}}

    payload = evaluate_grammar_lowering(asset, runtime)

    assert payload["family"] == "mechanical_door"
    assert payload["shape_program"]["ops"] == []
    assert payload["synthesized_graph_nodes"] == []
    assert payload["synthesized_node_count"] == 0
    assert payload["shape_program_summary"]["op_count"] == 0


def test_generic_family_fallback_when_design_brief_missing() -> None:
    """A missing ``runtime["design_brief"]`` block must fall back to the
    ``generic`` family with an empty program and zero synthesized nodes."""
    payload = evaluate_grammar_lowering(
        asset={"name": "asset_x", "intent": {"parts": []}},
        runtime={},
    )

    assert payload["family"] == "generic"
    assert payload["shape_program"]["ops"] == []
    assert payload["synthesized_node_count"] == 0


def test_missing_construction_graph_does_not_crash() -> None:
    """The Phase 6 recipe is currently a function of family alone, so a
    missing ``runtime["construction_graph"]`` block must not crash."""
    runtime = {"design_brief": {"brief": {"family": "industrial_crate"}}}
    asset = {"name": "industrial_crate", "intent": {"parts": list(_BASELINE_PARTS)}}

    payload = evaluate_grammar_lowering(asset, runtime)

    assert payload["family"] == "industrial_crate"
    assert payload["synthesized_node_count"] == 19


def test_evaluate_grammar_lowering_payload_has_exactly_seven_keys() -> None:
    payload = evaluate_grammar_lowering(_crate_asset(), _crate_runtime())

    assert set(payload.keys()) == _EXPECTED_PAYLOAD_KEYS


def test_evaluate_grammar_lowering_has_no_top_level_diagnostics_field() -> None:
    """Mirrors Phases 1 through 5: ``FunctionValidator`` only flips
    ``passes`` to ``False`` when a diagnostic has ``severity == 'error'``.
    Returning no ``diagnostics`` field keeps the validator passing."""
    payload = evaluate_grammar_lowering(_crate_asset(), _crate_runtime())

    assert "diagnostics" not in payload


def test_payload_version_field_is_grammar_lowering_v1() -> None:
    payload = evaluate_grammar_lowering(_crate_asset(), _crate_runtime())

    assert payload["version"] == GRAMMAR_LOWERING_VERSION
    assert payload["version"] == "grammar_lowering_v1"


def test_shape_program_carries_correct_metadata() -> None:
    payload = evaluate_grammar_lowering(_crate_asset(), _crate_runtime())

    program = payload["shape_program"]
    assert program["version"] == SHAPE_IR_V2_VERSION
    assert program["family"] == "industrial_crate"
    assert program["asset_name"] == "industrial_crate"
    assert isinstance(program["ops"], list)
    assert len(program["ops"]) == 13


def test_shape_program_summary_op_count_matches_program_op_count() -> None:
    payload = evaluate_grammar_lowering(_crate_asset(), _crate_runtime())

    summary = payload["shape_program_summary"]
    program_ops = payload["shape_program"]["ops"]
    assert summary["op_count"] == len(program_ops)


def test_shape_program_summary_ops_by_family_breakdown() -> None:
    """Counts the 13 industrial_crate recipe ops by Phase 5 family.
    Locks the canonical mapping (3 solids, 2 booleans, 4 repetitions,
    3 integrations, 1 wear, 0 edge ops at Phase 6)."""
    payload = evaluate_grammar_lowering(_crate_asset(), _crate_runtime())

    by_family = payload["shape_program_summary"]["ops_by_family"]
    assert by_family == {
        "solid_ops": 3,
        "boolean_ops": 2,
        "edge_ops": 0,
        "repetition_ops": 4,
        "integration_ops": 3,
        "wear_ops": 1,
    }
    assert sum(by_family.values()) == 13


def test_v1_lowering_yields_exactly_one_v1_record_for_body_solid_box() -> None:
    """Only ``solid.box`` from Phase 5's ``_V1_LOWERERS`` is lowerable
    in the recipe. Everything else (op.inset, op.cut_panel_line,
    op.corner_guard_set, op.mount_plate, op.socket, solid.rail,
    op.trim_band, op.fastener_grid, op.repeat, op.chip_edges) emits a
    ``no_v1_equivalent`` diagnostic instead."""
    payload = evaluate_grammar_lowering(_crate_asset(), _crate_runtime())
    v1 = payload["v1_lowering"]

    assert v1["v1_record_count"] == 1
    assert v1["unsupported_ops"] == []

    diagnostic_op_names = {item["op"] for item in v1["diagnostics"]}
    diagnostic_codes = {item["code"] for item in v1["diagnostics"]}
    assert diagnostic_codes == {"no_v1_equivalent"}
    for expected_op in (
        "op.inset",
        "op.cut_panel_line",
        "op.corner_guard_set",
        "op.mount_plate",
        "op.socket",
        "solid.rail",
        "op.trim_band",
        "op.fastener_grid",
        "op.repeat",
        "op.chip_edges",
    ):
        assert expected_op in diagnostic_op_names, (
            f"Expected v1-adapter diagnostic for op {expected_op!r}"
        )


def test_v1_lowering_diagnostics_count_matches_unsupported_op_count() -> None:
    """Every recipe op except the body's ``solid.box`` produces a
    ``no_v1_equivalent`` diagnostic (12 of 13 ops)."""
    payload = evaluate_grammar_lowering(_crate_asset(), _crate_runtime())
    v1 = payload["v1_lowering"]

    assert len(v1["diagnostics"]) == 12


def test_recipe_is_deterministic_across_invocations() -> None:
    first = industrial_crate_recipe(brief={}, parts=(), graph_nodes=())
    second = industrial_crate_recipe(brief={}, parts=(), graph_nodes=())

    assert first.shape_program.to_dict() == second.shape_program.to_dict()
    assert first.synthesized_graph_nodes == second.synthesized_graph_nodes


def test_evaluate_grammar_lowering_is_deterministic_across_invocations() -> None:
    asset = _crate_asset()
    runtime = _crate_runtime(_BASELINE_GRAPH_NODES)

    first = evaluate_grammar_lowering(asset, runtime)
    second = evaluate_grammar_lowering(asset, runtime)

    assert first == second


def test_every_recipe_op_is_a_member_of_all_ops() -> None:
    """Catches a typo'd op name in the recipe — ``ALL_OPS`` is the union
    of Phase 5's six op-family frozensets."""
    result = industrial_crate_recipe(brief={}, parts=(), graph_nodes=())

    for op in result.shape_program.ops:
        assert op.op in ALL_OPS, (
            f"Recipe op {op.op!r} is not a member of ALL_OPS"
        )


def test_lower_to_v1_on_recipe_produces_one_v1_record() -> None:
    """Direct ``lower_to_v1`` invocation on the recipe's program. Mirrors
    Phase 5's adapter contract end-to-end."""
    result = industrial_crate_recipe(brief={}, parts=(), graph_nodes=())

    adapter_result = lower_to_v1(result.shape_program)

    assert len(adapter_result.v1_records) == 1
    assert adapter_result.v1_records[0]["primitive_type"] == "box"
    assert adapter_result.v1_records[0]["part"] == "body"
    assert adapter_result.unsupported_ops == ()


def test_recipe_synthesized_nodes_lift_family_grammar_coverage() -> None:
    """Coverage-improves test (master-prompt requirement).

    Starting from the baseline ``[body, latch_plate, handle_l, handle_r,
    foot_l, foot_r]`` parts list (which yields 0.40 coverage with only
    the parts-derived construction graph), merging the recipe's
    synthesized graph nodes into the construction graph must STRICTLY
    raise the ``family_grammar`` coverage value because
    ``corner_guards``, ``trim_bands``, ``fasteners``,
    ``warning_or_decal_zones``, and ``edge_wear_masks`` get elevated
    from ``"missing"`` to ``"partial"`` via Phase 4's graph-elevation
    path. Predicted: 0.40 -> 0.70."""
    asset = _crate_asset()
    baseline_runtime = _crate_runtime(_BASELINE_GRAPH_NODES)
    baseline_payload = evaluate_family_grammar(asset, baseline_runtime)
    baseline_coverage = baseline_payload["coverage"]
    assert baseline_coverage == 0.4

    recipe_result = industrial_crate_recipe(brief={}, parts=(), graph_nodes=())
    merged_nodes = list(_BASELINE_GRAPH_NODES) + list(
        recipe_result.synthesized_graph_nodes
    )
    merged_runtime = _crate_runtime(tuple(merged_nodes))
    merged_payload = evaluate_family_grammar(asset, merged_runtime)
    merged_coverage = merged_payload["coverage"]

    assert merged_coverage > baseline_coverage, (
        f"Recipe synthesized nodes did not lift coverage: "
        f"baseline={baseline_coverage}, merged={merged_coverage}"
    )
    assert merged_coverage == 0.7


def test_recipe_brief_parts_and_graph_arguments_are_currently_ignored() -> None:
    """The Phase 6 industrial_crate recipe is a deterministic function of
    the family alone — the brief/parts/graph parameters are reserved for
    future variant recipes. Locks that contract: passing different briefs,
    parts, and graph nodes must yield identical output."""
    base = industrial_crate_recipe(brief={}, parts=(), graph_nodes=())
    populated = industrial_crate_recipe(
        brief={"family": "industrial_crate", "silhouette": "tall"},
        parts=("body", "lid", "handle_l"),
        graph_nodes=(
            {"node_id": "body", "node_type": "primary_volume", "attributes": {}},
        ),
    )

    assert base.shape_program.to_dict() == populated.shape_program.to_dict()
    assert base.synthesized_graph_nodes == populated.synthesized_graph_nodes


def test_shape_program_summary_ops_by_requirement_keyed_off_purpose_prefix() -> None:
    """The ``ops_by_requirement`` summary key buckets ops by the leading
    token of their ``purpose`` (``<requirement>.<suffix>``). Locks the
    canonical bucket counts."""
    payload = evaluate_grammar_lowering(_crate_asset(), _crate_runtime())
    summary = payload["shape_program_summary"]

    by_requirement = summary["ops_by_requirement"]
    assert by_requirement == {
        "body_shell": 1,
        "lid_seam": 2,
        "corner_guard_set": 1,
        "latch_plate": 1,
        "handles": 2,
        "foot_rails": 2,
        "trim_bands": 1,
        "fasteners": 1,
        "warning_decal_zone": 1,
        "edge_wear_masks": 1,
    }
    assert sum(by_requirement.values()) == 13


def test_shape_program_returned_from_recipe_is_a_shape_program_instance() -> None:
    result = industrial_crate_recipe(brief={}, parts=(), graph_nodes=())
    assert isinstance(result.shape_program, ShapeProgram)
    assert result.shape_program.version == SHAPE_IR_V2_VERSION
