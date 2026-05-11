"""Phase 6 tests for ``lathe.asset_quality.grammar_lowering``.

Covers per task #6 of ``docs/asset-quality/improvement-tasklist.md``:

- ``RecipeResult`` is frozen.
- The industrial_crate recipe lowers all 10 grammar requirements into
  the expected v2 op names + synthesized graph nodes.
- Each ``ShapeOp`` carries a ``purpose`` string (none are ``None`` /
  empty).
- Synthesized ``node_type`` values are members of Phase 4's
  ``NODE_TYPES`` frozenset.
- Coverage improves: starting from the baseline parts list, publishing
  the recipe's synthesized graph nodes under ``grammar_lowering``
  strictly raises the live ``family_grammar`` coverage value
  (predicted 0.40 -> 0.70).
- The validator entry point's payload shape is exactly the seven keys
  declared in the master prompt.
- The validator never adds a top-level ``diagnostics`` key (informational
  contract — mirrors Phases 1 through 5).
- ``lower_to_v1`` on the recipe produces concrete v1 records for the
  private SOP/solid geometry and leaves only material wear masks as
  ``no_v1_equivalent``.
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

from lathe.asset_quality.construction_graph import NODE_TYPES, evaluate_construction_graph
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
from lathe.validators.composition import FunctionValidator, ValidatorPipeline


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
    "sop.polybevel",
    "sop.boolean",
    "sop.polybevel",
    "sop.copy_to_points",
    "sop.polybevel",
    "sop.polywire",
    "sop.polywire",
    "sop.polybevel",
    "sop.polybevel",
    "sop.copy_to_points",
    # Position 10 was a third sop.copy_to_points before the ShapeIR v2
    # repetition-op expansion; the recipe now uses op.distribute here so
    # the corner-fastener pattern routes through the dedicated repetition
    # family rather than another aggregate.
    "op.distribute",
    "sop.polyextrude",
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
    than the private recipe registry) must fall back to an empty
    :class:`ShapeProgram` with no synthesized nodes."""
    runtime = {"design_brief": {"brief": {"family": "unknown_machine"}}}
    asset = {"name": "unknown_machine", "intent": {"parts": []}}

    payload = evaluate_grammar_lowering(asset, runtime)

    assert payload["family"] == "unknown_machine"
    assert payload["shape_program"]["ops"] == []
    assert payload["synthesized_graph_nodes"] == []
    assert payload["synthesized_node_count"] == 0
    assert payload["shape_program_summary"]["op_count"] == 0


def test_mechanical_door_recipe_emits_private_sop_geometry() -> None:
    payload = evaluate_grammar_lowering(
        {"name": "mechanical_door", "intent": {"parts": []}},
        {"design_brief": {"brief": {"family": "mechanical_door"}}},
    )

    op_names = [item["op"] for item in payload["shape_program"]["ops"]]
    assert payload["family"] == "mechanical_door"
    assert payload["synthesized_node_count"] == 10
    assert payload["shape_program_summary"]["ops_by_family"]["sop_ops"] == 10
    assert op_names.count("sop.copy_to_points") == 5
    assert "sop.polywire" in op_names
    assert payload["v1_lowering"]["v1_record_count"] == 23
    # chip_edges now lowers to a first-class ``edge_chip_set`` v1 record
    # (per Phase 8+ ShapeIR v2 expansion) rather than emitting a
    # ``no_v1_equivalent`` diagnostic. All recipe ops should lower.
    assert {item["op"] for item in payload["v1_lowering"]["diagnostics"]} == set()


def test_service_cabinet_recipe_emits_private_sop_geometry() -> None:
    payload = evaluate_grammar_lowering(
        {"name": "service_cabinet", "intent": {"parts": []}},
        {"design_brief": {"brief": {"family": "service_cabinet"}}},
    )

    op_names = [item["op"] for item in payload["shape_program"]["ops"]]
    assert payload["family"] == "service_cabinet"
    assert payload["synthesized_node_count"] == 10
    assert payload["shape_program_summary"]["ops_by_family"]["sop_ops"] == 9
    assert op_names.count("sop.polywire") == 2
    assert "sop.polyextrude" in op_names
    assert payload["v1_lowering"]["v1_record_count"] == 20
    # chip_edges now lowers to a first-class ``edge_chip_set`` v1 record
    # (per Phase 8+ ShapeIR v2 expansion) rather than emitting a
    # ``no_v1_equivalent`` diagnostic. All recipe ops should lower.
    assert {item["op"] for item in payload["v1_lowering"]["diagnostics"]} == set()


def test_weapon_prop_recipe_emits_private_sop_geometry() -> None:
    payload = evaluate_grammar_lowering(
        {"name": "weapon_prop", "intent": {"parts": []}},
        {"design_brief": {"brief": {"family": "weapon_prop"}}},
    )

    op_names = [item["op"] for item in payload["shape_program"]["ops"]]
    assert payload["family"] == "weapon_prop"
    assert payload["synthesized_node_count"] == 10
    assert payload["shape_program_summary"]["ops_by_family"]["sop_ops"] == 9
    assert "sop.carve" in op_names
    assert "sop.polywire" in op_names
    assert payload["v1_lowering"]["v1_record_count"] >= 10
    # chip_edges now lowers to a first-class ``edge_chip_set`` v1 record
    # (per Phase 8+ ShapeIR v2 expansion) rather than emitting a
    # ``no_v1_equivalent`` diagnostic. All recipe ops should lower.
    assert {item["op"] for item in payload["v1_lowering"]["diagnostics"]} == set()


def test_vehicle_prop_recipe_emits_private_sop_geometry() -> None:
    payload = evaluate_grammar_lowering(
        {"name": "vehicle_prop", "intent": {"parts": []}},
        {"design_brief": {"brief": {"family": "vehicle_prop"}}},
    )

    op_names = [item["op"] for item in payload["shape_program"]["ops"]]
    assert payload["family"] == "vehicle_prop"
    assert payload["synthesized_node_count"] == 10
    assert payload["shape_program_summary"]["ops_by_family"]["sop_ops"] == 9
    assert "sop.boolean" in op_names
    assert "sop.copy_to_points" in op_names
    assert payload["v1_lowering"]["v1_record_count"] >= 10
    # chip_edges now lowers to a first-class ``edge_chip_set`` v1 record
    # (per Phase 8+ ShapeIR v2 expansion) rather than emitting a
    # ``no_v1_equivalent`` diagnostic. All recipe ops should lower.
    assert {item["op"] for item in payload["v1_lowering"]["diagnostics"]} == set()


def test_furniture_prop_recipe_emits_private_sop_geometry() -> None:
    payload = evaluate_grammar_lowering(
        {"name": "furniture_prop", "intent": {"parts": []}},
        {"design_brief": {"brief": {"family": "furniture_prop"}}},
    )

    op_names = [item["op"] for item in payload["shape_program"]["ops"]]
    assert payload["family"] == "furniture_prop"
    assert payload["synthesized_node_count"] == 10
    assert payload["shape_program_summary"]["ops_by_family"]["sop_ops"] == 9
    assert "sop.polywire" in op_names
    assert "sop.copy_to_points" in op_names
    assert payload["v1_lowering"]["v1_record_count"] >= 10
    # chip_edges now lowers to a first-class ``edge_chip_set`` v1 record
    # (per Phase 8+ ShapeIR v2 expansion) rather than emitting a
    # ``no_v1_equivalent`` diagnostic. All recipe ops should lower.
    assert {item["op"] for item in payload["v1_lowering"]["diagnostics"]} == set()


def test_natural_form_recipe_emits_private_sop_geometry() -> None:
    payload = evaluate_grammar_lowering(
        {"name": "natural_form", "intent": {"parts": []}},
        {"design_brief": {"brief": {"family": "natural_form"}}},
    )

    op_names = [item["op"] for item in payload["shape_program"]["ops"]]
    assert payload["family"] == "natural_form"
    assert payload["synthesized_node_count"] == 10
    assert payload["shape_program_summary"]["ops_by_family"]["sop_ops"] == 9
    assert "sop.polyextrude" in op_names
    assert "sop.copy_to_points" in op_names
    assert payload["v1_lowering"]["v1_record_count"] >= 10
    # chip_edges now lowers to a first-class ``edge_chip_set`` v1 record
    # (per Phase 8+ ShapeIR v2 expansion) rather than emitting a
    # ``no_v1_equivalent`` diagnostic. All recipe ops should lower.
    assert {item["op"] for item in payload["v1_lowering"]["diagnostics"]} == set()


def test_environment_architecture_recipe_emits_private_sop_geometry() -> None:
    payload = evaluate_grammar_lowering(
        {"name": "environment_architecture", "intent": {"parts": []}},
        {"design_brief": {"brief": {"family": "environment_architecture"}}},
    )

    op_names = [item["op"] for item in payload["shape_program"]["ops"]]
    assert payload["family"] == "environment_architecture"
    assert payload["synthesized_node_count"] == 10
    assert payload["shape_program_summary"]["ops_by_family"]["sop_ops"] == 9
    assert "sop.loft" in op_names
    assert "sop.copy_to_points" in op_names
    assert payload["v1_lowering"]["v1_record_count"] >= 10
    # chip_edges now lowers to a first-class ``edge_chip_set`` v1 record
    # (per Phase 8+ ShapeIR v2 expansion) rather than emitting a
    # ``no_v1_equivalent`` diagnostic. All recipe ops should lower.
    assert {item["op"] for item in payload["v1_lowering"]["diagnostics"]} == set()


def test_lighting_prop_recipe_emits_private_sop_geometry() -> None:
    payload = evaluate_grammar_lowering(
        {"name": "lighting_prop", "intent": {"parts": []}},
        {"design_brief": {"brief": {"family": "lighting_prop"}}},
    )

    op_names = [item["op"] for item in payload["shape_program"]["ops"]]
    assert payload["family"] == "lighting_prop"
    assert payload["synthesized_node_count"] == 10
    assert payload["shape_program_summary"]["ops_by_family"]["sop_ops"] == 9
    assert "sop.polywire" in op_names
    assert "sop.copy_to_points" in op_names
    assert payload["v1_lowering"]["v1_record_count"] >= 10
    # chip_edges now lowers to a first-class ``edge_chip_set`` v1 record
    # (per Phase 8+ ShapeIR v2 expansion) rather than emitting a
    # ``no_v1_equivalent`` diagnostic. All recipe ops should lower.
    assert {item["op"] for item in payload["v1_lowering"]["diagnostics"]} == set()


def test_machine_console_recipe_emits_private_sop_geometry() -> None:
    payload = evaluate_grammar_lowering(
        {"name": "machine_console", "intent": {"parts": []}},
        {"design_brief": {"brief": {"family": "machine_console"}}},
    )

    op_names = [item["op"] for item in payload["shape_program"]["ops"]]
    assert payload["family"] == "machine_console"
    assert payload["synthesized_node_count"] == 10
    assert payload["shape_program_summary"]["ops_by_family"]["sop_ops"] == 9
    assert "sop.boolean" in op_names
    assert "sop.copy_to_points" in op_names
    assert payload["v1_lowering"]["v1_record_count"] >= 10
    # chip_edges now lowers to a first-class ``edge_chip_set`` v1 record
    # (per Phase 8+ ShapeIR v2 expansion) rather than emitting a
    # ``no_v1_equivalent`` diagnostic. All recipe ops should lower.
    assert {item["op"] for item in payload["v1_lowering"]["diagnostics"]} == set()


def test_portal_relic_recipe_emits_private_sop_geometry() -> None:
    payload = evaluate_grammar_lowering(
        {"name": "portal_relic", "intent": {"parts": []}},
        {"design_brief": {"brief": {"family": "portal_relic"}}},
    )

    op_names = [item["op"] for item in payload["shape_program"]["ops"]]
    assert payload["family"] == "portal_relic"
    assert payload["synthesized_node_count"] == 10
    assert payload["shape_program_summary"]["ops_by_family"]["sop_ops"] == 9
    assert "sop.polywire" in op_names
    assert "sop.copy_to_points" in op_names
    assert payload["v1_lowering"]["v1_record_count"] >= 10
    # chip_edges now lowers to a first-class ``edge_chip_set`` v1 record
    # (per Phase 8+ ShapeIR v2 expansion) rather than emitting a
    # ``no_v1_equivalent`` diagnostic. All recipe ops should lower.
    assert {item["op"] for item in payload["v1_lowering"]["diagnostics"]} == set()


def test_tool_prop_recipe_emits_private_sop_geometry() -> None:
    payload = evaluate_grammar_lowering(
        {"name": "tool_prop", "intent": {"parts": []}},
        {"design_brief": {"brief": {"family": "tool_prop"}}},
    )

    op_names = [item["op"] for item in payload["shape_program"]["ops"]]
    assert payload["family"] == "tool_prop"
    assert payload["synthesized_node_count"] == 10
    assert payload["shape_program_summary"]["ops_by_family"]["sop_ops"] == 9
    assert "sop.carve" in op_names
    assert "sop.copy_to_points" in op_names
    assert payload["v1_lowering"]["v1_record_count"] >= 10
    # chip_edges now lowers to a first-class ``edge_chip_set`` v1 record
    # (per Phase 8+ ShapeIR v2 expansion) rather than emitting a
    # ``no_v1_equivalent`` diagnostic. All recipe ops should lower.
    assert {item["op"] for item in payload["v1_lowering"]["diagnostics"]} == set()


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
    missing ``runtime["construction_graph"]`` block must not crash. With
    parts authored on the asset, ``_source_authored_graph_nodes`` lifts
    the parts into synthesized nodes that compose with the 19 recipe
    nodes, so the merged count exceeds the recipe-only count."""
    runtime = {"design_brief": {"brief": {"family": "industrial_crate"}}}
    asset = {"name": "industrial_crate", "intent": {"parts": list(_BASELINE_PARTS)}}

    payload = evaluate_grammar_lowering(asset, runtime)

    assert payload["family"] == "industrial_crate"
    # 19 recipe nodes + 6 authored part nodes = 25.
    assert payload["synthesized_node_count"] == 25


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
    Locks the private authoring mapping: top-level recipe geometry now
    routes through source-aware SOPs, with material wear still retained
    as a wear op."""
    payload = evaluate_grammar_lowering(_crate_asset(), _crate_runtime())

    by_family = payload["shape_program_summary"]["ops_by_family"]
    assert by_family == {
        "solid_ops": 0,
        "boolean_ops": 0,
        "edge_ops": 0,
        "sop_ops": 11,
        # op.distribute moved into REPETITION_OPS during the v2 expansion
        # — the recipe's corner-fastener pattern now routes through the
        # repetition family instead of a third sop.copy_to_points.
        "repetition_ops": 1,
        "integration_ops": 0,
        "wear_ops": 1,
    }
    assert sum(by_family.values()) == 13


def test_v1_lowering_yields_concrete_records_for_private_geometry() -> None:
    """Private SOP/solid recipe geometry lowers to concrete v1 records.
    With the Phase 8+ ShapeIR v2 expansion, every recipe op — including
    ``op.chip_edges`` (which now lowers to a first-class
    ``edge_chip_set``) — produces concrete records. The kernel-less
    lowering path preserves source records so SOP modifiers remain
    visible alongside their aggregates."""
    payload = evaluate_grammar_lowering(_crate_asset(), _crate_runtime())
    v1 = payload["v1_lowering"]

    assert v1["v1_record_count"] == 19
    assert v1["unsupported_ops"] == []
    assert v1["diagnostics"] == []


def test_v1_lowering_diagnostics_count_matches_unsupported_op_count() -> None:
    """Every recipe op now lowers cleanly. Diagnostics is empty and
    matches ``unsupported_ops`` (also empty) — neither honestly-flagged
    nor silently-dropped."""
    payload = evaluate_grammar_lowering(_crate_asset(), _crate_runtime())
    v1 = payload["v1_lowering"]

    assert len(v1["diagnostics"]) == 0
    assert v1["unsupported_ops"] == []


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
    of Phase 5's op-family frozensets."""
    result = industrial_crate_recipe(brief={}, parts=(), graph_nodes=())

    for op in result.shape_program.ops:
        assert op.op in ALL_OPS, (
            f"Recipe op {op.op!r} is not a member of ALL_OPS"
        )


def test_lower_to_v1_on_recipe_produces_private_geometry_records() -> None:
    """Direct ``lower_to_v1`` invocation on the recipe's program. Mirrors
    the adapter contract end-to-end and locks in the kernel-less primitive
    set the recipe drops onto: subdivision boxes from polybevel, swept
    profiles from polywire, component aggregates from copy/distribute, and
    edge_chip_set fan-out from ``op.chip_edges``."""
    result = industrial_crate_recipe(brief={}, parts=(), graph_nodes=())

    adapter_result = lower_to_v1(result.shape_program)

    assert len(adapter_result.v1_records) == 19
    assert adapter_result.v1_records[0]["primitive_type"] == "subdivision_box"
    assert adapter_result.v1_records[0]["part"] == "body"
    assert adapter_result.v1_records[0]["v2_op"] == "sop.polybevel"
    assert {record["primitive_type"] for record in adapter_result.v1_records} >= {
        "subdivision_box",
        "swept_profile",
        "component_assembly",
        "edge_chip_set",
    }
    assert adapter_result.unsupported_ops == ()


def test_recipe_synthesized_nodes_lift_family_grammar_coverage() -> None:
    """Coverage-improves test (master-prompt requirement).

    Starting from the baseline ``[body, latch_plate, handle_l, handle_r,
    foot_l, foot_r]`` parts list (which yields 0.40 coverage with only
    the parts-derived construction graph), publishing the recipe's
    synthesized graph nodes under ``runtime["grammar_lowering"]`` must
    STRICTLY raise the live ``family_grammar`` coverage value because
    ``corner_guards``, ``trim_bands``, ``fasteners``,
    ``warning_or_decal_zones``, and ``edge_wear_masks`` get elevated
    from ``"missing"`` to ``"partial"`` via Phase 4's graph-elevation
    path. Predicted: 0.40 -> 0.70."""
    asset = _crate_asset()
    baseline_runtime = _crate_runtime(_BASELINE_GRAPH_NODES)
    baseline_payload = evaluate_family_grammar(asset, baseline_runtime)
    baseline_coverage = baseline_payload["coverage"]
    assert baseline_coverage == 0.4

    grammar_payload = evaluate_grammar_lowering(asset, baseline_runtime)
    merged_runtime = _crate_runtime(_BASELINE_GRAPH_NODES)
    merged_runtime["grammar_lowering"] = grammar_payload
    merged_payload = evaluate_family_grammar(asset, merged_runtime)
    merged_coverage = merged_payload["coverage"]

    assert merged_coverage > baseline_coverage, (
        f"Recipe synthesized nodes did not lift coverage: "
        f"baseline={baseline_coverage}, merged={merged_coverage}"
    )
    assert merged_coverage == 0.7


def test_validator_pipeline_lifts_family_grammar_coverage_live() -> None:
    pipeline = ValidatorPipeline(
        [
            FunctionValidator(
                name="construction_graph",
                fn=evaluate_construction_graph,
                stage_dependencies=[],
                weight=0.0,
            ),
            FunctionValidator(
                name="grammar_lowering",
                fn=evaluate_grammar_lowering,
                stage_dependencies=[],
                weight=0.0,
            ),
            FunctionValidator(
                name="family_grammar",
                fn=evaluate_family_grammar,
                stage_dependencies=[],
                weight=0.0,
            ),
        ]
    )
    runtime = _crate_runtime()
    report = pipeline.run(runtime, _crate_asset(), artifacts={})

    family_evidence = report["validators"]["family_grammar"]["evidence"]
    assert family_evidence["coverage"] == 0.7
    assert runtime["family_grammar"]["coverage"] == 0.7


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
