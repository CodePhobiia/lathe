"""Unit tests for ``lathe.repair_planner.plan_shape_repairs``.

``plan_shape_repairs`` examines an ``AssetGraph`` + ``ShapeIR`` pair and
emits an ordered list of ``SemanticRepairAction`` records describing the
repairs needed to bring the blueprint up to the asset's semantic
requirements. The planner itself is pure — it never mutates the inputs
— so these tests focus on:

* no diagnostics ⇒ no repairs
* a single diagnostic (missing required part) ⇒ a single matching repair
* plan honors semantic_requirements thresholds (acts as the repair
  policy: lowering the required bar suppresses the repair)
* unrepairable conditions (e.g. richness floor already at or above min)
  are skipped
* repair_policy is honored via the semantic_requirements thresholds
  (the planner reads them to decide when to emit an action)
* every emitted action has the expected ``SemanticRepairAction`` shape
"""

from __future__ import annotations

import unittest

from lathe.asset_graph import build_asset_graph
from lathe.repair_planner import SemanticRepairAction, plan_shape_repairs
from lathe.shape_ir import ShapeIR, ShapePrimitive, ShapeRegion


def _asset_graph(
    parts: list[str] | None = None,
    *,
    role: str = "storage crate",
    kind: str = "prop",
) -> build_asset_graph:
    return build_asset_graph(
        {
            "name": "demo",
            "kind": kind,
            "intent": {"role": role, "parts": list(parts or ["body", "lid"])},
            "build": {
                "shape": {"symmetry": "auto"},
                "rig": {},
                "interfaces": {},
            },
            "validate": {"threshold": 0.80},
        }
    )


def _region(
    *,
    name: str = "region_body",
    part: str = "body",
    component: str = "shell",
    center: tuple[float, float, float] = (0.0, 0.0, 0.0),
    extents: tuple[float, float, float] = (10.0, 6.0, 4.0),
) -> ShapeRegion:
    return ShapeRegion(
        name=name,
        part=part,
        component=component,
        center=center,
        extents=extents,
    )


def _primitive(
    *,
    part: str = "body",
    region: str = "region_body",
    center: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> ShapePrimitive:
    return ShapePrimitive(
        primitive_type="box",
        part=part,
        center=center,
        extents=(10.0, 6.0, 4.0),
        component="shell",
        region=region,
    )


def _healthy_assessment() -> dict:
    # Assessment values chosen to satisfy all default thresholds in
    # semantic_requirements (``minimum_detail_density`` etc. default to
    # ~0.58 for generic hard-surface props — see asset_graph.py).
    return {
        "richness_floor": 0.95,
        "feature_density": 0.95,
        "edge_treatment_count": 12,
        "panel_feature_count": 8,
        "support_feature_count": 4,
        "feature_types": ["panel", "rotor_shroud", "trim"],
        "feature_coherence": 0.95,
    }


def _shape_ir(
    *,
    regions: list[ShapeRegion] | None = None,
    primitives: list[ShapePrimitive] | None = None,
    assessment: dict | None = None,
    family: str = "hard_surface_prop_generic",
) -> ShapeIR:
    return ShapeIR(
        asset_name="demo",
        family=family,
        blueprint_id="lathe.blueprint.test_v1",
        symmetry_axis="x",
        units="cm",
        primitives=list(primitives or [_primitive()]),
        regions=list(regions or [_region()]),
        primitives_used=["box"],
        part_graph=[],
        signature={"blueprint_notes": ["seeded"]},
        assessment=dict(assessment or _healthy_assessment()),
    )


class TestPlannerNoDiagnostics(unittest.TestCase):
    def test_zero_diagnostics_yields_no_repairs(self) -> None:
        # All required parts present, assessment values above every
        # threshold in the default semantic_requirements floor. Use
        # non-articulated parts (no ``lid``/``door``/``hatch`` tokens) so
        # the hinge-alignment check does not fire.
        graph = _asset_graph(["body", "plate"])
        regions = [
            _region(name="region_body", part="body", component="shell"),
            _region(name="region_plate", part="plate", component="panel", center=(0.0, 0.0, 5.0)),
        ]
        primitives = [
            _primitive(part="body", region="region_body"),
            _primitive(part="plate", region="region_plate", center=(0.0, 0.0, 5.0)),
        ]
        shape_ir = _shape_ir(regions=regions, primitives=primitives)
        repairs = plan_shape_repairs(graph, shape_ir)
        self.assertEqual(repairs, [])


class TestPlannerSingleDiagnostic(unittest.TestCase):
    def test_missing_required_part_emits_single_repair(self) -> None:
        # The graph declares body + lid; the shape_ir only contains body,
        # so the "lid" part is missing.
        graph = _asset_graph(["body", "lid"])
        shape_ir = _shape_ir(
            regions=[_region(name="region_body", part="body")],
            primitives=[_primitive(part="body", region="region_body")],
        )
        repairs = plan_shape_repairs(graph, shape_ir)
        missing_actions = [r for r in repairs if r.action == "add_missing_required_part"]
        self.assertEqual(len(missing_actions), 1)
        self.assertEqual(missing_actions[0].target, "lid")
        self.assertFalse(missing_actions[0].applied)
        self.assertIn("required part is missing", missing_actions[0].reason)


class TestPlannerThresholdBehavior(unittest.TestCase):
    def test_planner_respects_richness_threshold(self) -> None:
        # Below-threshold richness triggers an increase_structural_richness
        # repair; raising the assessment above the floor suppresses it.
        graph = _asset_graph(["body", "lid"])
        regions = [
            _region(name="region_body", part="body"),
            _region(name="region_lid", part="lid", component="lid", center=(0.0, 0.0, 5.0)),
        ]
        primitives = [
            _primitive(part="body", region="region_body"),
            _primitive(part="lid", region="region_lid", center=(0.0, 0.0, 5.0)),
        ]
        low = _healthy_assessment()
        low["richness_floor"] = 0.10
        shape_ir_low = _shape_ir(regions=regions, primitives=primitives, assessment=low)
        low_repairs = plan_shape_repairs(graph, shape_ir_low)
        assert any(r.action == "increase_structural_richness" for r in low_repairs)
        # Same inputs with above-threshold richness ⇒ no richness repair.
        shape_ir_ok = _shape_ir(regions=regions, primitives=primitives)
        ok_repairs = plan_shape_repairs(graph, shape_ir_ok)
        assert not any(r.action == "increase_structural_richness" for r in ok_repairs)

    def test_planner_skips_unrepairable_when_assessment_already_meets_floor(
        self,
    ) -> None:
        # edge_treatment_count >= 4 ⇒ no restore_edge_treatment action.
        # panel_feature_count >= 3 and family not in panel families ⇒ skipped.
        graph = _asset_graph(["body", "lid"])
        regions = [
            _region(name="region_body", part="body"),
            _region(name="region_lid", part="lid", component="lid", center=(0.0, 0.0, 5.0)),
        ]
        primitives = [
            _primitive(part="body", region="region_body"),
            _primitive(part="lid", region="region_lid", center=(0.0, 0.0, 5.0)),
        ]
        shape_ir = _shape_ir(regions=regions, primitives=primitives)
        repairs = plan_shape_repairs(graph, shape_ir)
        assert not any(r.action == "restore_edge_treatment" for r in repairs)
        assert not any(r.action == "increase_panel_depth" for r in repairs)


class TestPlannerHonorsPolicyThresholds(unittest.TestCase):
    def test_feature_density_policy_gates_secondary_features_repair(self) -> None:
        # feature_density below minimum_detail_density ⇒ add_secondary_features.
        graph = _asset_graph(["body", "lid"])
        regions = [
            _region(name="region_body", part="body"),
            _region(name="region_lid", part="lid", component="lid", center=(0.0, 0.0, 5.0)),
        ]
        primitives = [
            _primitive(part="body", region="region_body"),
            _primitive(part="lid", region="region_lid", center=(0.0, 0.0, 5.0)),
        ]
        sparse = _healthy_assessment()
        sparse["feature_density"] = 0.10
        shape_ir = _shape_ir(regions=regions, primitives=primitives, assessment=sparse)
        repairs = plan_shape_repairs(graph, shape_ir)
        assert any(r.action == "add_secondary_features" for r in repairs)


class TestPlannerOutputShape(unittest.TestCase):
    def test_repair_action_to_dict_has_expected_keys(self) -> None:
        graph = _asset_graph(["body", "lid"])
        shape_ir = _shape_ir(
            regions=[_region(name="region_body", part="body")],
            primitives=[_primitive(part="body", region="region_body")],
        )
        repairs = plan_shape_repairs(graph, shape_ir)
        # At least one repair (missing "lid") should be planned.
        assert repairs, "expected at least one repair for missing required part"
        first = repairs[0]
        self.assertIsInstance(first, SemanticRepairAction)
        payload = first.to_dict()
        for key in ("action", "target", "reason", "details", "applied"):
            self.assertIn(key, payload)
        self.assertFalse(payload["applied"])
        self.assertIsInstance(payload["details"], dict)
        self.assertIsInstance(payload["action"], str)
        self.assertIsInstance(payload["target"], str)


if __name__ == "__main__":
    unittest.main()
