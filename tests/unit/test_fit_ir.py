"""Unit tests for ``lathe.fit_ir.FitIR``.

``FitIR`` lifts an asset's ``fit`` block plus the resolved
``fit_profile`` / ``reconstruct_policy`` bundles. ``values`` is filtered
to drop ``resolved_*`` keys so authoring intent stays separate from
resolver output. Tests cover that filter, constraint preservation
(tri-budget / memory / scaling), round-tripping, and a real-example
path through the reconstruct flow.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from lathe.fit_ir import FitIR
from lathe.parser import parse_file
from lathe.resolver import materialize_asset


ROOT = Path(__file__).resolve().parents[2]
RECONSTRUCT_EXAMPLE = ROOT / "examples" / "reconstruct_courier_from_views.lth"


class FitIRTests(unittest.TestCase):
    def test_basic_construction(self) -> None:
        ir = FitIR(
            values={"fit_profile": "fp", "reconstruct_policy": "rp"},
            fit_profile={"name": "fp"},
            reconstruct_policy={"name": "rp"},
        )
        self.assertEqual(ir.values["fit_profile"], "fp")
        self.assertEqual(ir.fit_profile["name"], "fp")
        self.assertEqual(ir.reconstruct_policy["name"], "rp")

    def test_to_dict_round_trip(self) -> None:
        ir = FitIR(
            values={"fit_profile": "fp"},
            fit_profile={"name": "fp", "constraints": {"tri_budget": 18000}},
            reconstruct_policy={"name": "rp"},
        )
        payload = ir.to_dict()
        restored = FitIR(**payload)
        self.assertEqual(restored.to_dict(), payload)
        self.assertEqual(set(payload), {"values", "fit_profile", "reconstruct_policy"})

    def test_from_asset_filters_resolved_prefix(self) -> None:
        asset = {
            "fit": {
                "fit_profile": "fp",
                "reconstruct_policy": "rp",
                "resolved_fit_profile": {"name": "fp"},
                "resolved_reconstruct_policy": {"name": "rp"},
            }
        }
        ir = FitIR.from_asset(asset)
        self.assertIn("fit_profile", ir.values)
        self.assertIn("reconstruct_policy", ir.values)
        self.assertNotIn("resolved_fit_profile", ir.values)
        self.assertNotIn("resolved_reconstruct_policy", ir.values)
        self.assertEqual(ir.fit_profile["name"], "fp")
        self.assertEqual(ir.reconstruct_policy["name"], "rp")

    def test_tri_budget_and_memory_constraints_preserved(self) -> None:
        # Fit profiles carry the mobile-retarget constraint shape
        # (tri_budget, texture_memory, scaling). The IR must surface
        # those constraints verbatim so downstream stages can enforce
        # them.
        asset = {
            "fit": {
                "fit_profile": "mobile_fit",
                "resolved_fit_profile": {
                    "name": "mobile_fit",
                    "constraints": {
                        "tri_budget": 9000,
                        "texture_memory_mb": 8,
                        "scale": 1.45,
                    },
                },
            }
        }
        ir = FitIR.from_asset(asset)
        constraints = ir.fit_profile["constraints"]
        self.assertEqual(constraints["tri_budget"], 9000)
        self.assertEqual(constraints["texture_memory_mb"], 8)
        self.assertAlmostEqual(constraints["scale"], 1.45)

    def test_multiple_constraints_coexist(self) -> None:
        # tri-budget + memory + scaling + reconstruct policy should all
        # coexist in a single FitIR without collisions across the two
        # policy buckets.
        asset = {
            "fit": {
                "resolved_fit_profile": {
                    "constraints": {"tri_budget": 12000, "texture_memory_mb": 16, "scale": 0.9}
                },
                "resolved_reconstruct_policy": {
                    "constraints": {"view_count": 3, "seed": 42}
                },
            }
        }
        ir = FitIR.from_asset(asset)
        self.assertEqual(ir.fit_profile["constraints"]["tri_budget"], 12000)
        self.assertEqual(ir.fit_profile["constraints"]["texture_memory_mb"], 16)
        self.assertEqual(ir.reconstruct_policy["constraints"]["view_count"], 3)
        self.assertEqual(ir.reconstruct_policy["constraints"]["seed"], 42)

    def test_from_asset_missing_block_defaults(self) -> None:
        ir = FitIR.from_asset({})
        self.assertEqual(ir.values, {})
        self.assertEqual(ir.fit_profile, {})
        self.assertEqual(ir.reconstruct_policy, {})

    def test_from_asset_real_reconstruct_example(self) -> None:
        # ``reconstruct_courier_from_views.lth`` wires both fit_profile
        # and reconstruct_policy through ``build.shape``; after
        # materialization both bundles must surface on the FitIR.
        asset = materialize_asset(parse_file(RECONSTRUCT_EXAMPLE), "reconstruct_courier_from_views")
        ir = FitIR.from_asset(asset)
        self.assertEqual(ir.fit_profile.get("name"), "courier_fit_default")
        self.assertEqual(ir.reconstruct_policy.get("name"), "courier_reconstruct_policy")
        for key in ir.values:
            self.assertFalse(str(key).startswith("resolved_"))


if __name__ == "__main__":
    unittest.main()
