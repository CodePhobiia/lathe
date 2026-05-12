"""Unit tests for the procedural synthesizer's 8-stage compiler pipeline.

Exercises:
  - Empty asset → empty program (no crash).
  - Authored intent → non-empty ShapeProgram with family_dispatch_used: False.
  - Same intent, different brief → structurally-different program.
  - Knowledge pack loading via the JSON loader.
  - test_no_family_dispatch invariant on the SynthesizerTrace.
  - Schema validation surfaces as attribute_schema_violation traces.
  - The pipeline produces only ops in shape_ir_v2.ALL_OPS.
"""

from __future__ import annotations

import pytest

from lathe.asset_quality.procedural_synthesizer import (
    SynthesisResult,
    synthesize_procedural_program,
)
from lathe.asset_quality.procedural_synthesizer.knowledge_loader import (
    CompositionPolicy,
    PolicyExpansion,
    PolicyPrecondition,
    StyleKnowledge,
    FamilyAlias,
)
from lathe.asset_quality.shape_ir_v2 import ALL_OPS


_PRIMARY_NODE = {
    "node_id": "body",
    "node_type": "primary_volume",
    "attributes": {
        "shape": "rounded_box",
        "dimensions_cm": {"x": 40.0, "y": 30.0, "z": 20.0},
        "rounding_cm": 1.0,
    },
}

_PANEL_NODE = {
    "node_id": "front_panel",
    "node_type": "panel",
    "attributes": {
        "plane": "xy",
        "width_cm": 30.0,
        "height_cm": 15.0,
        "thickness_cm": 0.8,
        "inset_depth_cm": 0.5,
    },
}

_ATTACHED_EDGE = {
    "source_id": "front_panel",
    "target_id": "body",
    "edge_type": "attached_to",
    "attributes": {},
}


def _minimal_asset() -> dict:
    return {
        "name": "test_asset",
        "intent": {"parts": ["body", "front_panel"], "tags": []},
    }


def _runtime_with_graph(nodes: list[dict], edges: list[dict]) -> dict:
    return {
        "design_brief": {"brief": {}},
        "construction_graph": {"nodes": nodes, "edges": edges},
    }


class TestPipeline:
    def test_empty_runtime_produces_empty_program_without_crashing(self) -> None:
        result = synthesize_procedural_program({}, {})
        assert isinstance(result, SynthesisResult)
        assert result.shape_program.ops == ()
        assert result.trace.family_dispatch_used is False
        assert result.trace.attempted_via == "procedural_engine"

    def test_authored_graph_produces_non_empty_program(self) -> None:
        runtime = _runtime_with_graph([_PRIMARY_NODE, _PANEL_NODE], [_ATTACHED_EDGE])
        result = synthesize_procedural_program(_minimal_asset(), runtime)
        assert len(result.shape_program.ops) >= 3, (
            "expected at least 3 ops (primary_volume + panel + union), "
            f"got {len(result.shape_program.ops)}"
        )
        assert result.trace.family_dispatch_used is False

    def test_emitted_ops_are_all_in_shape_ir_v2_all_ops(self) -> None:
        runtime = _runtime_with_graph([_PRIMARY_NODE, _PANEL_NODE], [_ATTACHED_EDGE])
        result = synthesize_procedural_program(_minimal_asset(), runtime)
        for op in result.shape_program.ops:
            assert op.op in ALL_OPS, (
                f"emitted op {op.op!r} not in shape_ir_v2.ALL_OPS — "
                "Stage 8 validation must have failed"
            )

    def test_node_attribute_changes_flow_through_to_emitted_op_parameters(self) -> None:
        # Two assets with the same brief but a single node-attribute
        # difference (rounding_cm) — proves authored attributes flow
        # through Stage 4 validation into the generator's emitted op
        # parameters. NOTE: this is a node-attribute test, not a
        # brief/style biasing test; the pipeline does have a
        # style-biasing path via parameter_priors but it requires a
        # loaded StyleKnowledge with primary_volume.rounding_cm in its
        # parameter_priors, which the default test fixture does not
        # exercise.
        asset = _minimal_asset()
        runtime_a = _runtime_with_graph([_PRIMARY_NODE], [])
        runtime_b = _runtime_with_graph(
            [
                {
                    **_PRIMARY_NODE,
                    "attributes": {
                        **_PRIMARY_NODE["attributes"],
                        "rounding_cm": 5.0,  # different rounding on the node
                    },
                }
            ],
            [],
        )
        result_a = synthesize_procedural_program(asset, runtime_a)
        result_b = synthesize_procedural_program(asset, runtime_b)
        ops_a = [op for op in result_a.shape_program.ops if op.op == "solid.rounded_box"]
        ops_b = [op for op in result_b.shape_program.ops if op.op == "solid.rounded_box"]
        assert ops_a and ops_b
        assert ops_a[0].parameters["rounding_cm"] != ops_b[0].parameters["rounding_cm"]

    def test_attribute_schema_violation_surfaces_in_trace_not_crash(self) -> None:
        # Missing required dimension key — schema rejects the node, but
        # the pipeline continues gracefully.
        bad_node = {
            "node_id": "bad",
            "node_type": "primary_volume",
            "attributes": {
                "shape": "box",
                # missing 'dimensions_cm'
            },
        }
        runtime = _runtime_with_graph([bad_node], [])
        result = synthesize_procedural_program(_minimal_asset(), runtime)
        violations = result.trace.entries_of_kind("attribute_schema_violation")
        assert len(violations) == 1
        assert violations[0].payload["node_id"] == "bad"
        # Pipeline still ran all 8 stages — the bad node was dropped
        assert result.shape_program.ops == ()
        assert result.trace.family_dispatch_used is False

    def test_family_alias_in_brief_appears_in_trace_metadata_only(self) -> None:
        # Brief carries 'family' string — synthesizer records it as
        # metadata via alias_missing trace (we haven't authored any
        # alias JSON for this test) but does NOT dispatch on it.
        asset = _minimal_asset()
        runtime = {
            "design_brief": {"brief": {"family": "test_family_no_alias_exists"}},
            "construction_graph": {"nodes": [_PRIMARY_NODE], "edges": []},
        }
        result = synthesize_procedural_program(asset, runtime)
        alias_missing = result.trace.entries_of_kind("alias_missing")
        assert len(alias_missing) == 1
        assert alias_missing[0].payload["family"] == "test_family_no_alias_exists"
        assert result.trace.family_dispatch_used is False

    def test_pipeline_records_all_8_stages_in_trace(self) -> None:
        runtime = _runtime_with_graph([_PRIMARY_NODE, _PANEL_NODE], [_ATTACHED_EDGE])
        result = synthesize_procedural_program(_minimal_asset(), runtime)
        starts = result.trace.entries_of_kind("stage_start")
        ends = result.trace.entries_of_kind("stage_end")
        # Every stage emits start + end
        assert len(starts) == 8
        assert len(ends) == 8
        # Stage numbers 1..8 inclusive
        assert sorted(e.stage for e in starts) == [1, 2, 3, 4, 5, 6, 7, 8]


class TestKnowledgePackInjection:
    def test_pre_loaded_packs_bypass_disk_io(self) -> None:
        # Pass empty maps — synthesizer must not try to load from disk
        result = synthesize_procedural_program(
            _minimal_asset(),
            _runtime_with_graph([_PRIMARY_NODE], []),
            style_packs={},
            policy_packs={},
            alias_packs={},
        )
        assert result.shape_program.ops != ()
        assert result.trace.family_dispatch_used is False

    def test_policy_precondition_match_adds_node(self) -> None:
        # Author a custom policy that adds a panel node when a
        # primary_volume is present. Verifies stage 3 (expand_policies).
        custom_policy = CompositionPolicy(
            policy_id="test_panel_adder",
            domain="hard_surface",
            precondition=PolicyPrecondition(
                requires_node_types=("primary_volume",),
            ),
            expansions=(
                PolicyExpansion(
                    add_node_type="panel",
                    count=1,
                    attributes_template={
                        "plane": "xy",
                        "width_cm": 10.0,
                        "height_cm": 5.0,
                        "thickness_cm": 0.4,
                    },
                ),
            ),
        )
        custom_alias = FamilyAlias(
            family_id="test_with_panel_policy",
            style_id="industrial_pbr_v1",
            policy_ids=("test_panel_adder",),
            domain="hard_surface",
        )
        runtime = {
            "design_brief": {"brief": {"family": "test_with_panel_policy"}},
            "construction_graph": {"nodes": [_PRIMARY_NODE], "edges": []},
        }
        result = synthesize_procedural_program(
            _minimal_asset(),
            runtime,
            policy_packs={"test_panel_adder": custom_policy},
            alias_packs={"test_with_panel_policy": custom_alias},
        )
        # One primary_volume op + one policy-added panel op
        policy_added = result.trace.entries_of_kind("policy_added_node")
        assert len(policy_added) == 1
        assert policy_added[0].payload["node_type"] == "panel"
        op_kinds = {op.op for op in result.shape_program.ops}
        assert "solid.panel" in op_kinds
        assert "solid.rounded_box" in op_kinds
        assert len(result.synthesized_graph_nodes) == 1
        assert result.synthesized_graph_nodes[0]["added_by_policy"] == "test_panel_adder"


class TestIndividualGenerators:
    def test_primary_volume_box(self) -> None:
        node = {
            **_PRIMARY_NODE,
            "attributes": {
                "shape": "box",
                "dimensions_cm": {"x": 10.0, "y": 20.0, "z": 30.0},
            },
        }
        result = synthesize_procedural_program(
            _minimal_asset(),
            _runtime_with_graph([node], []),
        )
        op = result.shape_program.ops[0]
        assert op.op == "solid.box"
        assert op.parameters["width_cm"] == 10.0
        assert op.parameters["height_cm"] == 20.0
        assert op.parameters["depth_cm"] == 30.0

    def test_primary_volume_edge_treatment_attribute_emits_bevel_op(self) -> None:
        """Sprint 0 S0-3: a primary_volume with edge_treatment='beveled' emits
        an op.bevel op immediately after the primary solid, keyed to the same
        target. This is the path that escapes the "looks like procedural
        blockout" failure mode by adding visible chamfered edges to every
        hard-surface body.
        """
        node = {
            **_PRIMARY_NODE,
            "attributes": {
                "shape": "box",
                "dimensions_cm": {"x": 10.0, "y": 10.0, "z": 10.0},
                "edge_treatment": "beveled",
                "edge_treatment_width_cm": 0.8,
                "edge_treatment_segments": 3,
            },
        }
        result = synthesize_procedural_program(
            _minimal_asset(),
            _runtime_with_graph([node], []),
        )
        ops = result.shape_program.ops
        body_ops = [op for op in ops if op.target == "body"]
        assert len(body_ops) == 2, (
            f"expected 2 body-targeted ops (solid.box + op.bevel), got {len(body_ops)}: "
            f"{[(op.op, op.target) for op in body_ops]}"
        )
        primary, bevel = body_ops
        assert primary.op == "solid.box"
        assert bevel.op == "op.bevel"
        assert bevel.target == "body"
        assert bevel.parameters["width_cm"] == 0.8
        assert bevel.parameters["segments"] == 3

    def test_primary_volume_edge_treatment_chamfered_emits_chamfer_op(self) -> None:
        """Mirror of the beveled test but for chamfered edge treatment.

        op.chamfer emits a single 45° face (no segments parameter).
        """
        node = {
            **_PRIMARY_NODE,
            "attributes": {
                "shape": "box",
                "dimensions_cm": {"x": 10.0, "y": 10.0, "z": 10.0},
                "edge_treatment": "chamfered",
                "edge_treatment_width_cm": 0.5,
            },
        }
        result = synthesize_procedural_program(
            _minimal_asset(),
            _runtime_with_graph([node], []),
        )
        body_ops = [op for op in result.shape_program.ops if op.target == "body"]
        chamfer_ops = [op for op in body_ops if op.op == "op.chamfer"]
        assert len(chamfer_ops) == 1, (
            f"expected exactly 1 op.chamfer keyed to body, got {len(chamfer_ops)}"
        )
        assert chamfer_ops[0].parameters["width_cm"] == 0.5

    def test_primary_volume_sphere_skips_edge_treatment(self) -> None:
        """Spheres have no straight edges; the generator must not emit a
        bevel/chamfer op for them even when edge_treatment is requested."""
        node = {
            **_PRIMARY_NODE,
            "attributes": {
                "shape": "sphere",
                "dimensions_cm": {"radius": 5.0},
                "edge_treatment": "beveled",
                "edge_treatment_width_cm": 0.3,
            },
        }
        result = synthesize_procedural_program(
            _minimal_asset(),
            _runtime_with_graph([node], []),
        )
        body_ops = [op for op in result.shape_program.ops if op.target == "body"]
        assert len(body_ops) == 1, (
            "sphere should emit exactly 1 op (solid.sphere) and skip edge treatment"
        )
        assert body_ops[0].op == "solid.sphere"

    def test_primary_volume_sharp_attribute_emits_no_edge_op(self) -> None:
        """Default 'sharp' edge_treatment must not emit op.bevel / op.chamfer."""
        node = {
            **_PRIMARY_NODE,
            "attributes": {
                "shape": "box",
                "dimensions_cm": {"x": 10.0, "y": 10.0, "z": 10.0},
                # edge_treatment omitted — defaults to "sharp"
            },
        }
        result = synthesize_procedural_program(
            _minimal_asset(),
            _runtime_with_graph([node], []),
        )
        body_ops = [op for op in result.shape_program.ops if op.target == "body"]
        edge_ops = [op for op in body_ops if op.op in ("op.bevel", "op.chamfer")]
        assert not edge_ops, (
            f"sharp edge_treatment should emit no edge ops; got: "
            f"{[(op.op, op.parameters) for op in edge_ops]}"
        )

    def test_primary_volume_cylinder(self) -> None:
        node = {
            "node_id": "body",
            "node_type": "primary_volume",
            "attributes": {
                "shape": "cylinder",
                "dimensions_cm": {"radius": 4.0, "height": 12.0},
            },
        }
        result = synthesize_procedural_program(
            _minimal_asset(),
            _runtime_with_graph([node], []),
        )
        op = result.shape_program.ops[0]
        assert op.op == "solid.cylinder"
        assert op.parameters["radius_cm"] == 4.0
        assert op.parameters["height_cm"] == 12.0

    def test_panel_axis_mapping(self) -> None:
        # plane='xz' should map to thickness axis 'y'
        node = {
            "node_id": "p",
            "node_type": "panel",
            "attributes": {
                "plane": "xz",
                "width_cm": 5.0,
                "height_cm": 6.0,
                "thickness_cm": 0.7,
            },
        }
        result = synthesize_procedural_program(
            _minimal_asset(),
            _runtime_with_graph([node], []),
        )
        op = result.shape_program.ops[0]
        assert op.op == "solid.panel"
        assert op.parameters["axis"] == "y"
        assert op.parameters["width_cm"] == 5.0


class TestAttachedToDecorator:
    def test_attached_to_emits_union_op(self) -> None:
        runtime = _runtime_with_graph([_PRIMARY_NODE, _PANEL_NODE], [_ATTACHED_EDGE])
        result = synthesize_procedural_program(_minimal_asset(), runtime)
        union_ops = [op for op in result.shape_program.ops if op.op == "op.union"]
        assert len(union_ops) == 1
        # Union targets the body (the attachment target)
        assert union_ops[0].target == "body"


class TestEligibility:
    def test_empty_graph_produces_no_ops(self) -> None:
        result = synthesize_procedural_program(
            _minimal_asset(),
            _runtime_with_graph([], []),
        )
        assert result.shape_program.ops == ()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
