"""Unit tests for ``lathe.inspection.evidence``.

Covers construction of the inspection-policy IR and the validation-evidence
IR under representative asset + runtime shapes, plus edge cases like empty
inputs, unknown evidence classes, and the uniqueness of the declared
evidence-class pointers.
"""

from __future__ import annotations

import unittest

from lathe.inspection.evidence import (
    EVIDENCE_CLASSES,
    build_inspection_policy_ir,
    build_validation_evidence_ir,
)


def _asset(
    *,
    policy_name: str = "default_policy",
    values: dict | None = None,
    build_render_fixture: str = "",
    build_bake_profile: str = "",
) -> dict:
    values = values or {}
    return {
        "execution": {
            "profile": "default",
            "engine": "cycles",
            "inspection_policy": policy_name,
            "resolved_inspection_policy": {"name": policy_name, "values": values},
        },
        "build": {
            "surface": {
                "render_fixture": build_render_fixture,
                "bake_profile": build_bake_profile,
            }
        },
    }


class InspectionPolicyIRTests(unittest.TestCase):
    def test_policy_ir_shape_basic(self) -> None:
        asset = _asset(values={"require": ["geometry_evidence", "uv_evidence"]})
        ir = build_inspection_policy_ir(asset)
        self.assertEqual(ir["schema"], "lathe.inspection_policy_ir.v1")
        self.assertEqual(ir["policy"], "default_policy")
        self.assertEqual(ir["resolved_policy"], "default_policy")
        self.assertEqual(ir["required_evidence"], ["geometry_evidence", "uv_evidence"])
        self.assertEqual(ir["unknown_evidence"], [])
        self.assertFalse(ir["patch_source_allowed"])
        self.assertFalse(ir["unsafe_blender_python_allowed"])

    def test_policy_ir_defaults_recovery_branches_when_missing(self) -> None:
        ir = build_inspection_policy_ir(_asset())
        self.assertEqual(
            ir["recovery_branches"],
            ["reselect_candidate", "repair_candidate", "regenerate_candidate", "patch_source"],
        )

    def test_policy_ir_partitions_unknown_evidence(self) -> None:
        asset = _asset(values={"require": ["geometry_evidence", "bogus_evidence", "uv_evidence"]})
        ir = build_inspection_policy_ir(asset)
        self.assertEqual(ir["required_evidence"], ["geometry_evidence", "uv_evidence"])
        self.assertEqual(ir["unknown_evidence"], ["bogus_evidence"])

    def test_policy_ir_falls_back_to_build_render_and_bake(self) -> None:
        asset = _asset(build_render_fixture="hero_views", build_bake_profile="game_ready")
        ir = build_inspection_policy_ir(asset)
        self.assertEqual(ir["render_fixtures"], ["hero_views"])
        self.assertEqual(ir["bake_profiles"], ["game_ready"])

    def test_policy_ir_empty_asset_is_stable(self) -> None:
        ir = build_inspection_policy_ir({})
        self.assertEqual(ir["policy"], "")
        self.assertEqual(ir["resolved_policy"], "")
        self.assertEqual(ir["required_evidence"], [])
        self.assertEqual(ir["render_fixtures"], [])
        self.assertEqual(ir["bake_profiles"], [])
        self.assertTrue(ir["recovery_branches"])

    def test_policy_ir_honors_custom_recovery_branches(self) -> None:
        asset = _asset(values={"recovery_branches": ["reselect_candidate"]})
        ir = build_inspection_policy_ir(asset)
        self.assertEqual(ir["recovery_branches"], ["reselect_candidate"])

    def test_evidence_classes_are_unique(self) -> None:
        self.assertEqual(len(EVIDENCE_CLASSES), len(set(EVIDENCE_CLASSES)))
        for name in EVIDENCE_CLASSES:
            self.assertTrue(name.endswith("_evidence"))


class ValidationEvidenceIRTests(unittest.TestCase):
    def test_validation_evidence_schema_and_shape(self) -> None:
        asset = _asset(values={"require": ["geometry_evidence"]})
        runtime = {
            "shape": {"bundle": {"candidates": [{"candidate_id": "c0"}]}},
            "topology": {"bundle": {"part_groups": []}},
            "uv": {"bundle": {}},
            "surface": {"bundle": {}},
        }
        ir = build_validation_evidence_ir(asset=asset, runtime=runtime, execution_bundle={})
        self.assertEqual(ir["schema"], "lathe.validation_evidence_ir.v1")
        self.assertEqual(ir["inspection_policy"], "default_policy")
        self.assertEqual(ir["required_evidence"], ["geometry_evidence"])
        for cls in EVIDENCE_CLASSES:
            self.assertIn(cls, ir["evidence"])
            self.assertIn("available", ir["evidence"][cls])
            self.assertIn("sources", ir["evidence"][cls])
        self.assertTrue(ir["satisfied"])
        self.assertEqual(ir["missing_required_evidence"], [])

    def test_validation_evidence_reports_missing_required_evidence(self) -> None:
        asset = _asset(values={"require": ["uv_evidence", "package_export_evidence"]})
        runtime = {"shape": {"bundle": {}}, "topology": {"bundle": {}}}
        ir = build_validation_evidence_ir(asset=asset, runtime=runtime, execution_bundle={})
        self.assertFalse(ir["satisfied"])
        self.assertEqual(
            sorted(ir["missing_required_evidence"]),
            ["package_export_evidence", "uv_evidence"],
        )

    def test_validation_evidence_detects_bake_plan(self) -> None:
        asset = _asset(values={"require": ["bake_evidence"]})
        runtime = {"surface": {"bundle": {}}}
        execution_bundle = {"bake_plan_ir": {"maps": [{"name": "normal"}]}}
        ir = build_validation_evidence_ir(asset=asset, runtime=runtime, execution_bundle=execution_bundle)
        self.assertTrue(ir["evidence"]["bake_evidence"]["available"])
        self.assertTrue(ir["satisfied"])

    def test_validation_evidence_counts_render_passes(self) -> None:
        asset = _asset()
        runtime = {"shape": {"bundle": {"x": 1}}}
        execution_bundle = {"render_eval_ir": {"evidence_passes": [{"view": "front"}, {"view": "iso"}]}}
        ir = build_validation_evidence_ir(asset=asset, runtime=runtime, execution_bundle=execution_bundle)
        self.assertEqual(ir["evidence"]["geometry_evidence"]["render_pass_count"], 2)
        self.assertEqual(ir["evidence"]["surface_evidence"]["render_pass_count"], 2)

    def test_validation_evidence_records_blend_artifact(self) -> None:
        asset = _asset()
        runtime = {}
        execution_bundle = {"blend_artifact_ir": {"generated": True, "artifact_path": "out.blend"}}
        ir = build_validation_evidence_ir(asset=asset, runtime=runtime, execution_bundle=execution_bundle)
        self.assertEqual(ir["evidence"]["geometry_evidence"]["blend_artifact"], "out.blend")

    def test_validation_evidence_sources_are_stable_pointers(self) -> None:
        ir = build_validation_evidence_ir(asset={}, runtime={}, execution_bundle={})
        all_sources = [s for cls in EVIDENCE_CLASSES for s in ir["evidence"][cls]["sources"]]
        self.assertTrue(all(s.startswith("stages/") for s in all_sources))


if __name__ == "__main__":
    unittest.main()
