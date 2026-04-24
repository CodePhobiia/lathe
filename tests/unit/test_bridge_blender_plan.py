"""Unit tests for ``lathe.bridge.blender_plan``.

Covers the V1.3 Codex-operated Blender bridge: plan construction under
bake- and render-oriented asset shapes, tool-contract construction, and
doctor reporting. Uses monkeypatching to replace ``probe_blender`` with
a deterministic stub so tests stay hermetic.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from lathe.bridge import blender_plan as bp


_STUB_PROBE = {
    "available": True,
    "path": "/fake/blender",
    "version": "4.5.0",
    "python_module_available": False,
    "supported_modes": ["background_cli"],
    "asset_libraries": [],
    "addons": [],
    "code": "ok",
}


def _asset(
    *,
    profile: str = "hero_profile",
    engine: str = "cycles",
    mode: str = "bake",
    policy: str = "hero_policy",
    values: dict | None = None,
) -> dict:
    values = values or {"require": ["geometry_evidence"], "render_fixtures": ["hero_views"]}
    return {
        "execution": {
            "profile": profile,
            "engine": engine,
            "mode": mode,
            "inspection_policy": policy,
            "resolved_inspection_policy": {"name": policy, "values": values},
        },
        "build": {"surface": {"render_fixture": "", "bake_profile": ""}},
    }


class BridgePlanConstructionTests(unittest.TestCase):
    def test_plan_for_hero_marks_requested_and_backend_id(self) -> None:
        with mock.patch.object(bp, "probe_blender", return_value=_STUB_PROBE):
            plan = bp.build_bridge_plan(_asset())
        self.assertEqual(plan["schema"], "lathe.blender_bridge_plan.v1")
        self.assertEqual(plan["backend_id"], bp.BRIDGE_BACKEND_ID)
        self.assertTrue(plan["requested"])
        self.assertEqual(plan["source_of_truth"], "lathe_source")
        self.assertFalse(plan["generated_artifacts_are_authoritative"])
        self.assertEqual(plan["execution_profile"], "hero_profile")
        self.assertEqual(plan["engine"], "cycles")

    def test_plan_with_bake_intent_exposes_inspection_policy_ir(self) -> None:
        asset = _asset(mode="bake", values={"require": ["bake_evidence"], "bake_profiles": ["game_ready"]})
        with mock.patch.object(bp, "probe_blender", return_value=_STUB_PROBE):
            plan = bp.build_bridge_plan(asset)
        self.assertEqual(plan["mode"], "bake")
        policy_ir = plan["inspection_policy_ir"]
        self.assertEqual(policy_ir["required_evidence"], ["bake_evidence"])
        self.assertEqual(policy_ir["bake_profiles"], ["game_ready"])

    def test_plan_with_render_intent_has_render_fixtures(self) -> None:
        asset = _asset(mode="render", values={"render_fixtures": ["hero_views", "turntable"]})
        with mock.patch.object(bp, "probe_blender", return_value=_STUB_PROBE):
            plan = bp.build_bridge_plan(asset)
        self.assertEqual(plan["mode"], "render")
        self.assertEqual(
            plan["inspection_policy_ir"]["render_fixtures"],
            ["hero_views", "turntable"],
        )

    def test_plan_is_json_serializable(self) -> None:
        with mock.patch.object(bp, "probe_blender", return_value=_STUB_PROBE):
            plan = bp.build_bridge_plan(_asset())
        text = json.dumps(plan)
        reparsed = json.loads(text)
        self.assertEqual(reparsed["backend_id"], bp.BRIDGE_BACKEND_ID)

    def test_plan_tool_plane_and_handoff_contracts(self) -> None:
        with mock.patch.object(bp, "probe_blender", return_value=_STUB_PROBE):
            plan = bp.build_bridge_plan(_asset())
        self.assertIn("lathe_source", plan["bridge_handoff"])
        self.assertIn("validation_evidence_ir", plan["bridge_handoff"])
        lathe_contracts = plan["tool_plane"]["lathe_mcp"]
        blender_contracts = plan["tool_plane"]["blender_mcp"]
        self.assertEqual(len(lathe_contracts), len(bp.LATHE_TOOL_CONTRACTS))
        self.assertEqual(len(blender_contracts), len(bp.BLENDER_TOOL_CONTRACTS))
        for contract in lathe_contracts + blender_contracts:
            self.assertIn("name", contract)
            self.assertIn("determinism_class", contract)
            self.assertIn("side_effect_class", contract)
            self.assertIn("approval_class", contract)
        self.assertFalse(plan["tool_plane"]["unsafe_arbitrary_blender_python_exposed"])

    def test_inspect_completed_build_malformed_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build_dir = Path(tmp)
            stage_dir = build_dir / "stages" / "execution"
            stage_dir.mkdir(parents=True)
            (stage_dir / "bundle.json").write_text("{not valid json", encoding="utf-8")
            with self.assertRaises(json.JSONDecodeError):
                bp.inspect_completed_build(build_dir)


class BridgeDoctorTests(unittest.TestCase):
    def test_doctor_reports_contract_counts(self) -> None:
        with mock.patch.object(bp, "probe_blender", return_value=_STUB_PROBE):
            doctor = bp.build_bridge_doctor()
        self.assertEqual(doctor["schema"], "lathe.bridge_doctor.v1")
        self.assertEqual(doctor["bridge_backend"], bp.BRIDGE_BACKEND_ID)
        self.assertEqual(doctor["tool_contracts"]["lathe_mcp_count"], len(bp.LATHE_TOOL_CONTRACTS))
        self.assertEqual(doctor["tool_contracts"]["blender_mcp_count"], len(bp.BLENDER_TOOL_CONTRACTS))
        self.assertEqual(doctor["safety"]["arbitrary_blender_python_default"], "blocked")
        self.assertFalse(doctor["safety"]["blend_files_are_source_of_truth"])


if __name__ == "__main__":
    unittest.main()
