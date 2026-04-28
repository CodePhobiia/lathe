from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest
from lathe.executor import build_asset
from lathe.normalizer import normalize_program
from lathe.parser import parse_file
from lathe.planner import build_plan
from lathe.resolver import materialize_asset

ROOT = Path(__file__).resolve().parents[1]
V13_1_EXAMPLE = ROOT / "examples" / "brassbound_chest_v13_1_codex_blender.lth"


class LatheV13_1LanguageTests(unittest.TestCase):
    def test_inspection_policy_parses_and_normalizes(self) -> None:
        program = parse_file(V13_1_EXAMPLE)
        self.assertTrue(any(item["name"] == "hero_visual_gate" for item in program["inspection_policies"]))

        normalized = normalize_program(program)
        self.assertIn("inspection_policies", normalized)
        self.assertEqual(normalized["inspection_policies"][0]["node_type"], "inspection_policy")

    def test_materialize_and_plan_resolve_inspection_policy(self) -> None:
        program = parse_file(V13_1_EXAMPLE)
        asset = materialize_asset(program, "brassbound_chest_v13_1")
        self.assertEqual(asset["execution"]["inspection_policy"], "hero_visual_gate")
        self.assertEqual(asset["execution"]["resolved_inspection_policy"]["name"], "hero_visual_gate")

        plan = build_plan(program, "brassbound_chest_v13_1")
        self.assertEqual(plan["v1_3_1_control"]["bridge_backend"], "lathe.bridge.blender_execution_v1")
        self.assertEqual(plan["v1_3_1_control"]["resolved_inspection_policy"], "hero_visual_gate")
        self.assertIn("surface_evidence", plan["v1_3_1_control"]["required_evidence"])

    @pytest.mark.slow
    def test_v13_1_build_emits_bridge_and_evidence_ir(self) -> None:
        program = parse_file(V13_1_EXAMPLE)
        tmpdir = tempfile.TemporaryDirectory(prefix="lathe_v13_1_build_")
        self.addCleanup(tmpdir.cleanup)
        out_dir = Path(tmpdir.name) / "brassbound_chest_v13_1"
        report = build_asset(program, "brassbound_chest_v13_1", out_dir)
        self.assertTrue(report["certified"])

        execution_bundle = json.loads(
            (out_dir / "stages" / "execution" / "bundle.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            execution_bundle["bridge_plan_ir"]["backend_id"], "lathe.bridge.blender_execution_v1"
        )
        self.assertEqual(execution_bundle["inspection_policy_ir"]["resolved_policy"], "hero_visual_gate")
        self.assertTrue(execution_bundle["validation_evidence_ir"]["satisfied"])
        self.assertEqual(execution_bundle["validation_evidence_ir"]["missing_required_evidence"], [])

        trace = json.loads(
            (out_dir / "stages" / "package" / "trace_manifest.json").read_text(encoding="utf-8")
        )
        execution_trace = trace["stage_execution"]["execution"]
        self.assertEqual(execution_trace["inspection_policy_ir"]["resolved_policy"], "hero_visual_gate")
        self.assertTrue(execution_trace["validation_evidence_ir"]["satisfied"])

    @pytest.mark.slow
    def test_v13_1_cli_commands(self) -> None:
        tmpdir = tempfile.TemporaryDirectory(prefix="lathe_v13_1_cli_")
        self.addCleanup(tmpdir.cleanup)
        out_dir = Path(tmpdir.name) / "v13_1_cli"
        cli_env = {**os.environ, "LATHE_ALLOW_EXTERNAL_OUT": "1"}

        doctor_result = subprocess.run(
            [sys.executable, "-m", "lathe.cli", "bridge", "doctor"],
            cwd=ROOT,
            env=cli_env,
            text=True,
            capture_output=True,
            check=True,
        )
        doctor_payload = json.loads(doctor_result.stdout)
        self.assertEqual(doctor_payload["bridge_backend"], "lathe.bridge.blender_execution_v1")
        self.assertGreaterEqual(doctor_payload["tool_contracts"]["blender_mcp_count"], 1)

        plan_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "lathe.cli",
                "bridge",
                "plan",
                str(V13_1_EXAMPLE),
                "brassbound_chest_v13_1",
            ],
            cwd=ROOT,
            env=cli_env,
            text=True,
            capture_output=True,
            check=True,
        )
        plan_payload = json.loads(plan_result.stdout)
        self.assertEqual(plan_payload["inspection_policy_ir"]["resolved_policy"], "hero_visual_gate")
        self.assertFalse(plan_payload["tool_plane"]["unsafe_arbitrary_blender_python_exposed"])

        build_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "lathe.cli",
                "build",
                str(V13_1_EXAMPLE),
                "brassbound_chest_v13_1",
                "--out",
                str(out_dir),
            ],
            cwd=ROOT,
            env=cli_env,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertTrue(json.loads(build_result.stdout)["certified"])
        build_dir = out_dir / "brassbound_chest_v13_1"

        inspect_result = subprocess.run(
            [sys.executable, "-m", "lathe.cli", "inspect", str(build_dir)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        inspect_payload = json.loads(inspect_result.stdout)
        self.assertTrue(inspect_payload["validation_evidence_ir"]["satisfied"])

        bake_result = subprocess.run(
            [sys.executable, "-m", "lathe.cli", "bake-audit", str(build_dir)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        bake_payload = json.loads(bake_result.stdout)
        self.assertIn("normal", bake_payload["bake_plan_ir"]["maps"])

        render_result = subprocess.run(
            [sys.executable, "-m", "lathe.cli", "render-fixture", str(build_dir)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        render_payload = json.loads(render_result.stdout)
        self.assertEqual(render_payload["render_eval_ir"]["resolved_render_fixture"], "hero_prop_eval")


if __name__ == "__main__":
    unittest.main()
