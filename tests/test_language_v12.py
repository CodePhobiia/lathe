from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest
from lathe.executor import build_surface_stage
from lathe.normalizer import normalize_program
from lathe.parser import parse_file
from lathe.planner import build_plan
from lathe.resolver import materialize_asset
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
V12_EXAMPLE = ROOT / "examples" / "console_terminal_v12_surface.lth"


class LatheV12SurfaceTests(unittest.TestCase):
    def test_v12_runtime_modules_are_importable(self) -> None:
        for module_name in (
            "lathe.atlas_assembler",
            "lathe.codex_imagegen_bridge",
            "lathe.pbr_deriver",
            "lathe.repair.surface_repair",
            "lathe.texture_control_pack",
            "lathe.validators.surface_quality",
        ):
            importlib.import_module(module_name)

    def test_new_v12_declarations_parse_and_normalize(self) -> None:
        program = parse_file(V12_EXAMPLE)
        self.assertTrue(any(item["name"] == "codex_imagegen" for item in program["surface_backends"]))
        self.assertTrue(
            any(item["name"] == "hero_zone_first_surface" for item in program["surface_policies"])
        )
        self.assertTrue(
            any(item["name"] == "industrial_console_decals" for item in program["decal_libraries"])
        )
        self.assertTrue(any(item["name"] == "console_wear_masks" for item in program["mask_programs"]))
        self.assertTrue(any(item["name"] == "console_trim_sheet" for item in program["trim_sheets"]))

        normalized = normalize_program(program)
        for key in (
            "surface_backends",
            "surface_policies",
            "decal_libraries",
            "mask_programs",
            "trim_sheets",
        ):
            self.assertIn(key, normalized)

    def test_materialize_and_plan_resolve_v12_surface_authoring(self) -> None:
        program = parse_file(V12_EXAMPLE)
        asset = materialize_asset(program, "console_terminal_v12_surface")
        self.assertEqual(asset["surface"]["policy"], "hero_zone_first_surface")
        self.assertEqual(asset["surface"]["backend"], "codex_imagegen")
        self.assertEqual(asset["surface"]["resolved_surface_policy"]["name"], "hero_zone_first_surface")
        self.assertEqual(asset["surface"]["resolved_surface_backend"]["name"], "codex_imagegen")
        self.assertEqual(
            [item["name"] for item in asset["surface"]["resolved_decal_libraries"]],
            ["industrial_console_decals"],
        )
        self.assertEqual(
            [item["name"] for item in asset["surface"]["resolved_mask_programs"]], ["console_wear_masks"]
        )
        self.assertEqual(
            [item["name"] for item in asset["surface"]["resolved_trim_sheets"]], ["console_trim_sheet"]
        )

        plan = build_plan(program, "console_terminal_v12_surface")
        self.assertEqual(plan["v1_2_surface"]["authoring_backend"], "codex_imagegen")
        self.assertEqual(plan["v1_2_surface"]["resolved_surface_policy"], "hero_zone_first_surface")

    @pytest.mark.slow
    def test_v12_surface_stage_emits_control_pack_bundle(self) -> None:
        program = parse_file(V12_EXAMPLE)
        tmpdir = tempfile.TemporaryDirectory(prefix="lathe_v12_surface_")
        self.addCleanup(tmpdir.cleanup)
        out_dir = Path(tmpdir.name) / "console_terminal_v12_surface"
        emitted = build_surface_stage(program, "console_terminal_v12_surface", out_dir)
        surface_bundle = emitted["surface_bundle"]
        self.assertTrue(surface_bundle["surface_control_pack"]["manifest_uri"])
        self.assertEqual(
            surface_bundle["surface_backend_report"]["selected_backend_id"], "lathe.surface.codex_imagegen_v1"
        )
        self.assertFalse(surface_bundle["surface_backend_report"]["codex_imagegen_ran"])
        self.assertEqual(
            surface_bundle["surface_backend_report"]["fallback_backend_id"],
            "lathe.surface.deterministic_pbr_v1",
        )
        self.assertEqual(surface_bundle["atlas_assembly_ir"]["schema"], "lathe.atlas_assembly_ir.v1")
        self.assertEqual(surface_bundle["surface_validation_ir"]["schema"], "lathe.surface_validation_ir.v1")
        self.assertEqual(surface_bundle["surface_repair_ir"]["schema"], "lathe.surface_repair_ir.v1")
        self.assertTrue(
            (out_dir / "stages" / "surface" / surface_bundle["surface_control_pack"]["manifest_uri"]).exists()
        )

        saved_bundle = json.loads(
            (out_dir / "stages" / "surface" / "bundle.json").read_text(encoding="utf-8")
        )
        self.assertEqual(saved_bundle["surface_backend_report"], surface_bundle["surface_backend_report"])

    @pytest.mark.slow
    def test_v12_surface_cli_commands(self) -> None:
        tmpdir = tempfile.TemporaryDirectory(prefix="lathe_v12_cli_")
        self.addCleanup(tmpdir.cleanup)
        cli_env = {**os.environ, "LATHE_ALLOW_EXTERNAL_OUT": "1"}

        plan_cmd = [
            sys.executable,
            "-m",
            "lathe.cli",
            "surface-plan",
            str(V12_EXAMPLE),
            "console_terminal_v12_surface",
        ]
        plan_result = subprocess.run(plan_cmd, cwd=ROOT, text=True, capture_output=True, check=True)
        plan_payload = json.loads(plan_result.stdout)
        self.assertEqual(plan_payload["backend"], "codex_imagegen")
        self.assertIn("surface_authoring_quality", plan_payload["validation_gates"])

        out_dir = Path(tmpdir.name) / "surface_cli"
        build_cmd = [
            sys.executable,
            "-m",
            "lathe.cli",
            "surface-build",
            str(V12_EXAMPLE),
            "console_terminal_v12_surface",
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
        self.assertEqual(build_payload["surface_bundle_path"], "stages/surface/bundle.json")
        surface_bundle = build_payload["surface_bundle"]
        self.assertEqual(surface_bundle["surface_validation_ir"]["schema"], "lathe.surface_validation_ir.v1")

        validate_cmd = [
            sys.executable,
            "-m",
            "lathe.cli",
            "surface-validate",
            str(V12_EXAMPLE),
            "console_terminal_v12_surface",
            "--out",
            str(out_dir),
        ]
        validate_result = subprocess.run(
            validate_cmd,
            cwd=ROOT,
            env=cli_env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertIn(validate_result.returncode, {0, 1})
        validate_payload = json.loads(validate_result.stdout)
        self.assertIn("surface_authoring_quality", validate_payload["metrics"])
        self.assertEqual(
            validate_payload["surface_validation_ir"]["schema"], "lathe.surface_validation_ir.v1"
        )

    def test_codex_imagegen_emit_and_consume_handoff(self) -> None:
        program = parse_file(V12_EXAMPLE)
        tmpdir = tempfile.TemporaryDirectory(prefix="lathe_v12_imagegen_")
        self.addCleanup(tmpdir.cleanup)
        out_dir = Path(tmpdir.name) / "codex_imagegen_handoff"

        emitted = build_surface_stage(
            program,
            "console_terminal_v12_surface",
            out_dir,
            runtime_config={"surface": {"codex_imagegen": {"mode": "emit"}}},
        )
        requests = emitted["surface_bundle"]["codex_imagegen_requests"]
        self.assertEqual(requests["schema"], "lathe.codex_imagegen_requests.v1")
        self.assertGreater(requests["request_count"], 0)
        self.assertTrue(emitted["surface_bundle"]["surface_backend_report"]["codex_imagegen_pending"])

        for item in requests["requests"]:
            if item["map"] != "basecolor":
                continue
            output_path = out_dir / "stages" / "surface" / item["expected_output"]
            output_path.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (64, 64), (210, 64, 132)).save(output_path)

        consumed = build_surface_stage(
            program,
            "console_terminal_v12_surface",
            out_dir,
            runtime_config={"surface": {"codex_imagegen": {"mode": "consume"}}},
        )
        surface_bundle = consumed["surface_bundle"]
        report = surface_bundle["surface_backend_report"]
        self.assertTrue(report["codex_imagegen_ran"])
        self.assertFalse(report["fallback_backend_id"])
        self.assertEqual(surface_bundle["codex_imagegen_outputs"]["status"], "complete")
        self.assertTrue(
            (
                out_dir / "stages" / "surface" / surface_bundle["codex_imagegen_outputs"]["manifest_uri"]
            ).exists()
        )


if __name__ == "__main__":
    unittest.main()
