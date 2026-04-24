"""Unit tests for ``lathe.repair_executor.execute_shape_repairs``.

The repair executor takes the planner output (a list of
``SemanticRepairAction``) and applies them against the current
``ShapeIR``. It must:

* apply known repairs (delegating to the semantic apply step), marking
  them ``applied`` and returning a refreshed ShapeIR;
* honour the ``max_repairs`` budget (no more than ``max_repairs``
  actions executed);
* skip unrepairable actions silently rather than raising;
* leave the ShapeIR byte-stable (signature unchanged) when the input
  repair list is empty;
* record an applied-trace entry per accepted repair so callers can
  observe what ran;
* never execute an unknown custom action (defensive: the executor
  ignores actions outside its known custom set, leaving them with
  ``applied=False``).
"""

from __future__ import annotations

import unittest
from copy import deepcopy

from lathe.asset_graph import build_asset_graph
from lathe.repair_executor import execute_shape_repairs
from lathe.repair_planner import SemanticRepairAction, plan_shape_repairs
from lathe.shape_ir import ShapeIR, ShapePrimitive, ShapeRegion


def _asset_graph(parts: list[str] | None = None) -> "build_asset_graph":
    return build_asset_graph(
        {
            "name": "demo",
            "kind": "prop",
            "intent": {"role": "storage crate", "parts": list(parts or ["body", "lid"])},
            "build": {"shape": {"symmetry": "auto"}, "rig": {}, "interfaces": {}},
            "validate": {"threshold": 0.80},
        }
    )


def _region(
    *,
    name: str = "region_body",
    part: str = "body",
    component: str = "shell",
    center: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> ShapeRegion:
    return ShapeRegion(
        name=name,
        part=part,
        component=component,
        center=center,
        extents=(10.0, 6.0, 4.0),
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


def _shape_ir(
    *,
    regions: list[ShapeRegion] | None = None,
    primitives: list[ShapePrimitive] | None = None,
    assessment: dict | None = None,
) -> ShapeIR:
    healthy = {
        "richness_floor": 0.95,
        "feature_density": 0.95,
        "edge_treatment_count": 12,
        "panel_feature_count": 8,
        "support_feature_count": 4,
        "feature_types": ["panel", "trim"],
        "feature_coherence": 0.95,
    }
    return ShapeIR(
        asset_name="demo",
        family="hard_surface_prop_generic",
        blueprint_id="lathe.blueprint.test_v1",
        symmetry_axis="x",
        units="cm",
        primitives=list(primitives or [_primitive()]),
        regions=list(regions or [_region()]),
        primitives_used=["box"],
        part_graph=[],
        signature={"blueprint_notes": ["seeded"]},
        assessment=dict(assessment or healthy),
    )


class TestExecutorAppliesRepairs(unittest.TestCase):
    def test_executor_applies_single_missing_part_repair(self) -> None:
        # Planner emits "add_missing_required_part" for the missing lid;
        # executor should run it and return a non-empty applied list.
        graph = _asset_graph(["body", "lid"])
        shape_ir = _shape_ir(
            regions=[_region(name="region_body", part="body")],
            primitives=[_primitive(part="body", region="region_body")],
        )
        repairs = plan_shape_repairs(graph, shape_ir)
        self.assertTrue(repairs, "planner should emit at least one repair")
        _, applied = execute_shape_repairs(graph, shape_ir, repairs)
        self.assertTrue(applied)
        self.assertTrue(any(item.get("action") == "add_missing_required_part" for item in applied))


class TestExecutorRollbackOnRegression(unittest.TestCase):
    def test_executor_skips_custom_repair_with_no_target_region(self) -> None:
        # "shroud_exposed_frame" requires a rotor_pod region; with none
        # present the executor must not append anything to the applied
        # trace and must not mark the repair as applied. (The shape_ir
        # is refreshed unconditionally for the custom-repair branch — we
        # don't assert on signature stability here, only on the trace.)
        graph = _asset_graph(["body"])
        shape_ir = _shape_ir(
            regions=[_region(name="region_body", part="body")],
            primitives=[_primitive(part="body", region="region_body")],
        )
        repairs = [
            SemanticRepairAction(
                action="shroud_exposed_frame",
                target="rotor_pod",
                reason="no rotor pod present — should be skipped",
                details={},
            )
        ]
        _, applied = execute_shape_repairs(graph, shape_ir, repairs)
        self.assertEqual(applied, [])
        self.assertFalse(repairs[0].applied)


class TestExecutorRespectsBudget(unittest.TestCase):
    def test_max_repairs_caps_number_of_applied_actions(self) -> None:
        # Build a planner output of 3 base repairs; cap at 1.
        graph = _asset_graph(["body", "lid", "left_handle", "right_handle"])
        shape_ir = _shape_ir(
            regions=[_region(name="region_body", part="body")],
            primitives=[_primitive(part="body", region="region_body")],
        )
        repairs = plan_shape_repairs(graph, shape_ir)
        # Expect 3 missing-part repairs (lid, left_handle, right_handle).
        missing = [r for r in repairs if r.action == "add_missing_required_part"]
        self.assertGreaterEqual(len(missing), 3)
        _, applied = execute_shape_repairs(graph, shape_ir, missing, max_repairs=1)
        self.assertEqual(len(applied), 1)


class TestExecutorSkipsUnrepairable(unittest.TestCase):
    def test_unknown_custom_action_is_silently_ignored(self) -> None:
        # An action outside both base and custom sets must not raise and
        # must not be marked applied.
        graph = _asset_graph(["body"])
        shape_ir = _shape_ir()
        repairs = [
            SemanticRepairAction(
                action="totally_unknown_action_xyz",
                target="body",
                reason="unhandled",
                details={},
            )
        ]
        _, applied = execute_shape_repairs(graph, shape_ir, repairs)
        self.assertEqual(applied, [])
        self.assertFalse(repairs[0].applied)


class TestExecutorLogsAppliedTrace(unittest.TestCase):
    def test_each_applied_repair_emits_a_dict_trace_entry(self) -> None:
        graph = _asset_graph(["body", "lid"])
        shape_ir = _shape_ir(
            regions=[_region(name="region_body", part="body")],
            primitives=[_primitive(part="body", region="region_body")],
        )
        repairs = plan_shape_repairs(graph, shape_ir)
        _, applied = execute_shape_repairs(graph, shape_ir, repairs)
        self.assertTrue(applied)
        for entry in applied:
            self.assertIsInstance(entry, dict)
            for key in ("action", "target", "reason", "details", "applied"):
                self.assertIn(key, entry)
            self.assertTrue(entry["applied"])


class TestExecutorByteStabilityOnEmptyRepairs(unittest.TestCase):
    def test_no_repairs_returns_input_shape_ir_unchanged(self) -> None:
        # With an empty repair list the executor short-circuits — it
        # should return the *same* ShapeIR instance and an empty trace.
        graph = _asset_graph(["body"])
        shape_ir = _shape_ir()
        snapshot_signature = deepcopy(shape_ir.signature)
        snapshot_assessment = deepcopy(shape_ir.assessment)
        result_ir, applied = execute_shape_repairs(graph, shape_ir, [])
        self.assertIs(result_ir, shape_ir)
        self.assertEqual(applied, [])
        self.assertEqual(result_ir.signature, snapshot_signature)
        self.assertEqual(result_ir.assessment, snapshot_assessment)


if __name__ == "__main__":
    unittest.main()
