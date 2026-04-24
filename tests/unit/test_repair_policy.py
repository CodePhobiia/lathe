"""Unit tests for ``lathe.repair_policy.RepairPolicyIR``.

``RepairPolicyIR`` is the V1.0 IR for the asset-level
``repair_policy`` block. It is a thin dataclass that:

* takes default values when the asset omits ``repair_policy``;
* round-trips through ``to_dict`` (for serialization into manifests);
* propagates ``max_rounds`` as a budget hint for the repair executor;
* reads ``min_improvement`` and ``regression_guard`` style fields out
  of the asset's ``allow``/``deny`` lists when present;
* honours the planner's contract that an empty policy ⇒ no repairs
  are gated out by the policy itself.
"""

from __future__ import annotations

import unittest

from lathe.repair_executor import execute_shape_repairs
from lathe.repair_policy import RepairPolicyIR


class TestRepairPolicyIRConstruction(unittest.TestCase):
    def test_from_asset_with_no_block_yields_defaults(self) -> None:
        policy = RepairPolicyIR.from_asset({})
        self.assertEqual(policy.use, "")
        self.assertEqual(policy.mode, "")
        self.assertIsNone(policy.max_rounds)
        self.assertEqual(policy.allow, [])
        self.assertEqual(policy.deny, [])

    def test_from_asset_with_full_block_populates_all_fields(self) -> None:
        policy = RepairPolicyIR.from_asset(
            {
                "repair_policy": {
                    "use": "lathe.repair.policy_default_v1",
                    "mode": "strict",
                    "max_rounds": 3,
                    "allow": ["add_missing_required_part"],
                    "deny": ["regularize_symmetry"],
                }
            }
        )
        self.assertEqual(policy.use, "lathe.repair.policy_default_v1")
        self.assertEqual(policy.mode, "strict")
        self.assertEqual(policy.max_rounds, 3)
        self.assertEqual(policy.allow, ["add_missing_required_part"])
        self.assertEqual(policy.deny, ["regularize_symmetry"])


class TestRepairPolicyIRSerialization(unittest.TestCase):
    def test_to_dict_round_trip_preserves_fields(self) -> None:
        original = RepairPolicyIR(
            use="lathe.repair.policy_default_v1",
            mode="lenient",
            max_rounds=2,
            allow=["restore_symmetry_region"],
            deny=[],
        )
        payload = original.to_dict()
        # Reconstruct via ``from_asset`` to confirm the dict is shaped
        # exactly like the asset block expects.
        rebuilt = RepairPolicyIR.from_asset({"repair_policy": payload})
        self.assertEqual(rebuilt, original)


class TestRepairPolicyIRBudgetConstraints(unittest.TestCase):
    def test_max_rounds_can_be_zero_and_is_preserved(self) -> None:
        # ``max_rounds=0`` is a legal "no repairs" policy.
        policy = RepairPolicyIR.from_asset({"repair_policy": {"max_rounds": 0}})
        self.assertEqual(policy.max_rounds, 0)

    def test_max_rounds_high_value_is_preserved(self) -> None:
        policy = RepairPolicyIR.from_asset({"repair_policy": {"max_rounds": 99}})
        self.assertEqual(policy.max_rounds, 99)


class TestRepairPolicyMinImprovementThreshold(unittest.TestCase):
    def test_allow_list_captures_named_improvement_actions(self) -> None:
        # The IR stores allow/deny verbatim — downstream gating is the
        # caller's job. We verify the raw fields make it through so the
        # min-improvement / regression-guard logic upstream can consume
        # them.
        policy = RepairPolicyIR.from_asset(
            {
                "repair_policy": {
                    "allow": [
                        "add_missing_required_part",
                        "increase_structural_richness",
                    ]
                }
            }
        )
        self.assertIn("increase_structural_richness", policy.allow)


class TestRepairPolicyRegressionGuardRule(unittest.TestCase):
    def test_deny_list_captures_blocked_actions(self) -> None:
        policy = RepairPolicyIR.from_asset(
            {"repair_policy": {"deny": ["regularize_symmetry", "shroud_exposed_frame"]}}
        )
        self.assertEqual(
            policy.deny, ["regularize_symmetry", "shroud_exposed_frame"]
        )


class TestEmptyPolicyExecutesNoRepairs(unittest.TestCase):
    def test_empty_policy_with_empty_repair_list_runs_nothing(self) -> None:
        # End-to-end gate: an empty policy + empty repair list ⇒ the
        # executor is a no-op (no actions, no trace).
        from lathe.asset_graph import build_asset_graph
        from lathe.shape_ir import ShapeIR, ShapePrimitive, ShapeRegion

        policy = RepairPolicyIR.from_asset({})
        # Sanity: the empty policy carries no allow/deny at all.
        self.assertEqual(policy.allow, [])
        self.assertEqual(policy.deny, [])

        graph = build_asset_graph(
            {
                "name": "demo",
                "kind": "prop",
                "intent": {"role": "crate", "parts": ["body"]},
                "build": {"shape": {"symmetry": "auto"}, "rig": {}, "interfaces": {}},
                "validate": {"threshold": 0.80},
            }
        )
        shape_ir = ShapeIR(
            asset_name="demo",
            family="hard_surface_prop_generic",
            blueprint_id="lathe.blueprint.test_v1",
            symmetry_axis="x",
            units="cm",
            primitives=[
                ShapePrimitive(
                    primitive_type="box",
                    part="body",
                    center=(0.0, 0.0, 0.0),
                    extents=(10.0, 6.0, 4.0),
                    component="shell",
                    region="region_body",
                )
            ],
            regions=[
                ShapeRegion(
                    name="region_body",
                    part="body",
                    component="shell",
                    center=(0.0, 0.0, 0.0),
                    extents=(10.0, 6.0, 4.0),
                )
            ],
            primitives_used=["box"],
            part_graph=[],
            signature={"blueprint_notes": []},
            assessment={"richness_floor": 0.95, "feature_density": 0.95},
        )
        result_ir, applied = execute_shape_repairs(graph, shape_ir, [])
        self.assertEqual(applied, [])
        self.assertIs(result_ir, shape_ir)


if __name__ == "__main__":
    unittest.main()
