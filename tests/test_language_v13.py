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
V13_EXAMPLE = ROOT / "examples" / "brassbound_chest_v13_blender.lth"


class LatheV13LanguageTests(unittest.TestCase):
    def test_v13_declarations_parse_and_normalize(self) -> None:
        program = parse_file(V13_EXAMPLE)
        self.assertTrue(any(item["name"] == "hero_blender" for item in program["execution_profiles"]))
        self.assertTrue(any(item["name"] == "hero_prop_eval" for item in program["render_fixtures"]))
        self.assertTrue(any(item["name"] == "hero_pbr_bakes" for item in program["bake_profiles"]))
        self.assertTrue(any(item["name"] == "chest_hardware_blender" for item in program["library_bindings"]))
        self.assertTrue(any(item["name"] == "aged_brass_graph" for item in program["material_graphs"]))

        normalized = normalize_program(program)
        for key in (
            "execution_profiles",
            "render_fixtures",
            "bake_profiles",
            "library_bindings",
            "material_graphs",
        ):
            self.assertIn(key, normalized)

    def test_materialize_and_plan_resolve_v13_execution(self) -> None:
        program = parse_file(V13_EXAMPLE)
        asset = materialize_asset(program, "brassbound_chest_v13")
        self.assertEqual(asset["execution"]["profile"], "hero_blender")
        self.assertEqual(asset["execution"]["resolved_execution_profile"]["name"], "hero_blender")
        self.assertEqual(asset["build"]["surface"]["bake_profile"], "hero_pbr_bakes")
        self.assertEqual(asset["build"]["surface"]["resolved_bake_profile"]["name"], "hero_pbr_bakes")
        self.assertEqual(asset["build"]["surface"]["render_fixture"], "hero_prop_eval")
        self.assertEqual(asset["build"]["surface"]["resolved_render_fixture"]["name"], "hero_prop_eval")
        self.assertEqual(asset["surface"]["material_graph"], "aged_brass_graph")
        self.assertEqual(asset["surface"]["resolved_material_graph"]["name"], "aged_brass_graph")
        self.assertEqual(
            [item["name"] for item in asset["execution"]["resolved_library_bindings"]],
            ["chest_hardware_blender"],
        )

        plan = build_plan(program, "brassbound_chest_v13")
        self.assertEqual(plan["v1_3_execution"]["resolved_execution_profile"], "hero_blender")
        self.assertEqual(plan["v1_3_execution"]["resolved_bake_profile"], "hero_pbr_bakes")
        self.assertEqual(plan["v1_3_execution"]["resolved_render_fixture"], "hero_prop_eval")
        self.assertEqual(
            plan["v1_3_execution"]["internal_backends"]["surface_backend"],
            "lathe.surface.blender_materials_v1",
        )

    @pytest.mark.slow
    def test_v13_build_emits_execution_bundle_and_trace(self) -> None:
        program = parse_file(V13_EXAMPLE)
        tmpdir = tempfile.TemporaryDirectory(prefix="lathe_v13_build_")
        self.addCleanup(tmpdir.cleanup)
        out_dir = Path(tmpdir.name) / "brassbound_chest_v13"
        report = build_asset(program, "brassbound_chest_v13", out_dir)
        self.assertTrue(report["certified"])
        execution_bundle = json.loads(
            (out_dir / "stages" / "execution" / "bundle.json").read_text(encoding="utf-8")
        )
        self.assertEqual(execution_bundle["schema"], "lathe.blender_execution_bundle.v1")
        self.assertEqual(execution_bundle["backend_id"], "lathe.exec.blender_v1")
        self.assertEqual(execution_bundle["execution_ir"]["resolved_execution_profile"], "hero_blender")
        self.assertEqual(execution_bundle["bake_plan_ir"]["resolved_bake_profile"], "hero_pbr_bakes")
        self.assertEqual(execution_bundle["render_eval_ir"]["resolved_render_fixture"], "hero_prop_eval")
        self.assertEqual(
            execution_bundle["library_asset_ir"]["bindings"][0]["name"], "chest_hardware_blender"
        )

        trace = json.loads(
            (out_dir / "stages" / "package" / "trace_manifest.json").read_text(encoding="utf-8")
        )
        self.assertIn("execution", trace["stage_execution"])
        self.assertEqual(
            trace["stage_execution"]["execution"]["execution_ir"]["resolved_execution_profile"],
            "hero_blender",
        )

    @pytest.mark.slow
    def test_v13_cli_commands(self) -> None:
        tmpdir = tempfile.TemporaryDirectory(prefix="lathe_v13_cli_")
        self.addCleanup(tmpdir.cleanup)
        out_dir = Path(tmpdir.name) / "v13_cli"
        cli_env = {**os.environ, "LATHE_ALLOW_EXTERNAL_OUT": "1"}

        probe_cmd = [sys.executable, "-m", "lathe.cli", "probe-blender", "--runtime-config", ""]
        # Empty runtime-config is not valid, so run without it.
        probe_cmd = [sys.executable, "-m", "lathe.cli", "probe-blender"]
        probe_result = subprocess.run(probe_cmd, cwd=ROOT, text=True, capture_output=True, check=True)
        probe_payload = json.loads(probe_result.stdout)
        self.assertIn("supported_modes", probe_payload)

        build_cmd = [
            sys.executable,
            "-m",
            "lathe.cli",
            "build",
            str(V13_EXAMPLE),
            "brassbound_chest_v13",
            "--out",
            str(out_dir),
        ]
        build_result = subprocess.run(
            build_cmd,
            cwd=ROOT,
            env=cli_env,
            text=True,
            capture_output=True,
            check=True,
        )
        build_payload = json.loads(build_result.stdout)
        self.assertTrue(build_payload["certified"])

        inspect_cmd = [
            sys.executable,
            "-m",
            "lathe.cli",
            "inspect-blend",
            str(out_dir / "brassbound_chest_v13"),
        ]
        inspect_result = subprocess.run(inspect_cmd, cwd=ROOT, text=True, capture_output=True, check=True)
        inspect_payload = json.loads(inspect_result.stdout)
        self.assertIn("blend_artifact_ir", inspect_payload)
        self.assertIn("render_eval_ir", inspect_payload)

        render_eval_cmd = [
            sys.executable,
            "-m",
            "lathe.cli",
            "render-eval",
            str(V13_EXAMPLE),
            "brassbound_chest_v13",
            "--out",
            str(out_dir),
        ]
        render_eval_result = subprocess.run(
            render_eval_cmd,
            cwd=ROOT,
            env=cli_env,
            text=True,
            capture_output=True,
            check=True,
        )
        render_eval_payload = json.loads(render_eval_result.stdout)
        self.assertIn("render_eval_ir", render_eval_payload)
        self.assertEqual(render_eval_payload["render_eval_ir"]["resolved_render_fixture"], "hero_prop_eval")

        library_sync_cmd = [
            sys.executable,
            "-m",
            "lathe.cli",
            "library",
            "sync",
            str(V13_EXAMPLE),
            "--out",
            str(out_dir),
        ]
        library_sync_result = subprocess.run(
            library_sync_cmd,
            cwd=ROOT,
            env=cli_env,
            text=True,
            capture_output=True,
            check=True,
        )
        library_sync_payload = json.loads(library_sync_result.stdout)
        self.assertEqual(library_sync_payload["binding_count"], 1)


if __name__ == "__main__":
    unittest.main()
