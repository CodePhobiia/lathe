"""Unit tests for ``lathe.asset_quality.grammar_lowering``.

Covers the post-Cycle-3 synthesizer-driven evaluator. After Round 6
decommissioned ``_RECIPES`` + the 71 family-keyed recipe functions,
``evaluate_grammar_lowering`` is a pure dispatch-to-synthesizer
validator. These tests verify:

- ``RecipeResult`` is frozen.
- The validator's payload shape is exactly the seven documented keys.
- The validator never adds a top-level ``diagnostics`` key
  (informational contract — mirrors Phases 1 through 5).
- A missing ``runtime["construction_graph"]`` block does not crash.
- A missing ``runtime["design_brief"]`` block falls back to ``generic``.
- ``shape_program_summary.op_count`` matches ``len(shape_program.ops)``.
- Synthesizer-emitted ops are all members of
  ``shape_ir_v2.ALL_OPS``.
- A construction graph with a single ``primary_volume`` produces a
  non-empty ShapeProgram routed through the procedural synthesizer.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any

import pytest
from lathe.asset_quality.grammar_lowering import (
    GRAMMAR_LOWERING_VERSION,
    RecipeResult,
    _select_recipe_result,
    evaluate_grammar_lowering,
)
from lathe.asset_quality.shape_ir_v2 import (
    ALL_OPS,
    SHAPE_IR_V2_VERSION,
    ShapeProgram,
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


def _minimal_primary_volume_node() -> dict[str, Any]:
    return {
        "node_id": "body",
        "node_type": "primary_volume",
        "domain": "hard_surface",
        "attributes": {
            "shape": "rounded_box",
            "dimensions_cm": {"x": 30.0, "y": 30.0, "z": 30.0},
            "rounding_cm": 1.5,
        },
    }


def _minimal_runtime_with_primary_volume(family: str = "inventory_economy_object") -> tuple[dict[str, Any], dict[str, Any]]:
    cg = {"nodes": [_minimal_primary_volume_node()], "edges": []}
    asset = {"name": family, "intent": {"construction_graph": cg}}
    runtime = {
        "design_brief": {"brief": {"family": family}},
        "construction_graph": cg,
    }
    return asset, runtime


def test_recipe_result_is_frozen() -> None:
    """RecipeResult must reject post-construction mutation."""
    result = RecipeResult(
        family="inventory_economy_object",
        shape_program=ShapeProgram(
            version=SHAPE_IR_V2_VERSION,
            asset_name="inventory_economy_object",
            family="inventory_economy_object",
            ops=(),
        ),
        synthesized_graph_nodes=(),
    )
    with pytest.raises(FrozenInstanceError):
        result.family = "other"  # type: ignore[misc]


def test_evaluate_grammar_lowering_returns_seven_documented_keys() -> None:
    """The validator's payload shape is the seven-key contract."""
    asset, runtime = _minimal_runtime_with_primary_volume()
    payload = evaluate_grammar_lowering(asset, runtime)
    assert set(payload.keys()) == _EXPECTED_PAYLOAD_KEYS


def test_evaluate_grammar_lowering_omits_top_level_diagnostics() -> None:
    """Validator is informational; never produces a top-level diagnostics key."""
    asset, runtime = _minimal_runtime_with_primary_volume()
    payload = evaluate_grammar_lowering(asset, runtime)
    assert "diagnostics" not in payload


def test_evaluate_grammar_lowering_handles_missing_runtime_construction_graph() -> None:
    """No construction_graph → empty program; the validator does not crash."""
    asset: dict[str, Any] = {"name": "asset"}
    runtime: dict[str, Any] = {"design_brief": {"brief": {"family": "asset"}}}
    payload = evaluate_grammar_lowering(asset, runtime)
    assert payload["family"] == "asset"
    assert payload["shape_program_summary"]["op_count"] == 0


def test_evaluate_grammar_lowering_handles_missing_design_brief() -> None:
    """No design brief → family falls back to ``generic``; validator does not crash."""
    asset: dict[str, Any] = {"name": "asset"}
    runtime: dict[str, Any] = {}
    payload = evaluate_grammar_lowering(asset, runtime)
    assert payload["family"] == "generic"
    assert "shape_program" in payload


def test_shape_program_summary_op_count_matches_program_ops() -> None:
    """``shape_program_summary.op_count`` must equal the literal program ops length."""
    asset, runtime = _minimal_runtime_with_primary_volume()
    payload = evaluate_grammar_lowering(asset, runtime)
    summary = payload["shape_program_summary"]
    program_dict = payload["shape_program"]
    assert summary["op_count"] == len(program_dict["ops"])


def test_synthesizer_emitted_ops_are_in_all_ops() -> None:
    """Every op the synthesizer emits via grammar lowering must be in ALL_OPS."""
    asset, runtime = _minimal_runtime_with_primary_volume()
    payload = evaluate_grammar_lowering(asset, runtime)
    program_dict = payload["shape_program"]
    for op in program_dict["ops"]:
        assert op["op"] in ALL_OPS, (
            f"synthesizer-emitted op {op['op']!r} not in ALL_OPS"
        )


def test_minimal_primary_volume_produces_at_least_one_op() -> None:
    """A primary_volume node drives the synthesizer's primary_volume generator."""
    asset, runtime = _minimal_runtime_with_primary_volume()
    payload = evaluate_grammar_lowering(asset, runtime)
    assert payload["shape_program_summary"]["op_count"] >= 1


def test_select_recipe_result_returns_recipe_result_type() -> None:
    """Internal dispatch helper returns the documented RecipeResult shape."""
    result = _select_recipe_result(
        family="generic",
        asset_name="asset",
        brief={},
        parts=(),
        graph_nodes=(),
        graph_edges=(),
    )
    assert isinstance(result, RecipeResult)
    assert result.family == "generic"
    assert isinstance(result.shape_program, ShapeProgram)


def test_grammar_lowering_version_is_v1() -> None:
    """The payload version tag pins to ``grammar_lowering_v1``."""
    asset, runtime = _minimal_runtime_with_primary_volume()
    payload = evaluate_grammar_lowering(asset, runtime)
    assert payload["version"] == GRAMMAR_LOWERING_VERSION
    assert GRAMMAR_LOWERING_VERSION == "grammar_lowering_v1"


def test_v1_lowering_section_present_with_required_keys() -> None:
    """The nested ``v1_lowering`` section reports the adapter result."""
    asset, runtime = _minimal_runtime_with_primary_volume()
    payload = evaluate_grammar_lowering(asset, runtime)
    v1 = payload["v1_lowering"]
    assert "v1_record_count" in v1
    assert "diagnostics" in v1
    assert "unsupported_ops" in v1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
