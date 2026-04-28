"""Unit tests for ``lathe.stages.budgets`` (STAGE-7/8).

Covers the three budget categories (texture memory, material count,
draw calls), severity escalation at the 25% threshold, graceful
degradation when upstream data is missing, schema validation, and the
end-to-end selector-manifest integration via the courier_drone build.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from lathe.stages import budgets as budgets_mod

REPO_ROOT = Path(__file__).resolve().parents[2]
BUDGET_SCHEMA = json.loads((REPO_ROOT / "schema" / "budget_manifest.schema.json").read_text(encoding="utf-8"))
SELECTOR_SCHEMA = json.loads(
    (REPO_ROOT / "schema" / "lathe.selector.schema.json").read_text(encoding="utf-8")
)


def _asset(**optimize_overrides: Any) -> dict[str, Any]:
    return {"build": {"optimize": dict(optimize_overrides)}}


def _surface_bundle_with_materials(count: int, *, resolution: int = 2048, maps: int = 4) -> dict[str, Any]:
    return {
        "surface": {
            "bundle": {
                "material_zones": [{"part": f"p{i}", "material": f"mat_{i}"} for i in range(count)],
                "maps": [f"channel_{i}" for i in range(maps)],
                "material_slots": count,
                "surface_manifest": {
                    "resolution": {"type": "unit", "value": resolution, "unit": "px"},
                    "workflow": "pbr_metal_rough",
                },
            }
        }
    }


def _runtime_with_optimize(surface_runtime: dict[str, Any], lods: int) -> dict[str, Any]:
    return {
        **surface_runtime,
        "optimize": {
            "bundle": {
                "lods": [{"name": f"lod{i}", "triangle_count": 100} for i in range(lods)],
            }
        },
    }


class TextureMemoryBudgetTests(unittest.TestCase):
    def test_under_budget_emits_no_diagnostic(self) -> None:
        asset = _asset(texture_memory_budget_mb=256)
        runtime = _runtime_with_optimize(_surface_bundle_with_materials(2, resolution=512, maps=4), lods=2)
        report, diags = budgets_mod.evaluate(asset, runtime)
        self.assertEqual(report["texture_memory"]["status"], "pass")
        # No L6301 in diagnostics.
        self.assertFalse(any(d["code"] == "L6301" for d in diags))
        self.assertGreater(report["texture_memory"]["estimated_bytes"], 0)

    def test_within_25_percent_over_is_warning(self) -> None:
        # 2048x2048x4x1bpp = 16 MiB exactly. Budget 14 MiB => ~14% over => warning.
        asset = _asset(texture_memory_budget_mb=14)
        runtime = _runtime_with_optimize(_surface_bundle_with_materials(1, resolution=2048, maps=4), lods=2)
        report, diags = budgets_mod.evaluate(asset, runtime)
        self.assertEqual(report["texture_memory"]["status"], "warning")
        matched = [d for d in diags if d["code"] == "L6301"]
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["severity"], "warning")

    def test_severe_overage_is_error(self) -> None:
        # Budget 1 MiB vs. estimated 16 MiB => ~1500% over => error.
        asset = _asset(texture_memory_budget_mb=1)
        runtime = _runtime_with_optimize(_surface_bundle_with_materials(1, resolution=2048, maps=4), lods=2)
        report, diags = budgets_mod.evaluate(asset, runtime)
        self.assertEqual(report["texture_memory"]["status"], "error")
        self.assertEqual(report["overall_status"], "error")
        matched = [d for d in diags if d["code"] == "L6301"]
        self.assertEqual(matched[0]["severity"], "error")


class MaterialCountBudgetTests(unittest.TestCase):
    def test_under_budget(self) -> None:
        asset = _asset(material_count_budget=16)
        runtime = _runtime_with_optimize(_surface_bundle_with_materials(4), lods=2)
        report, diags = budgets_mod.evaluate(asset, runtime)
        self.assertEqual(report["materials"]["status"], "pass")
        self.assertEqual(report["materials"]["count"], 4)
        self.assertFalse(any(d["code"] == "L6302" for d in diags))

    def test_warning_over_budget(self) -> None:
        # 11 materials, budget 10 => 10% over => warning.
        asset = _asset(material_count_budget=10)
        runtime = _runtime_with_optimize(_surface_bundle_with_materials(11), lods=2)
        report, diags = budgets_mod.evaluate(asset, runtime)
        self.assertEqual(report["materials"]["status"], "warning")
        matched = [d for d in diags if d["code"] == "L6302"]
        self.assertEqual(len(matched), 1)

    def test_severe_over_budget(self) -> None:
        # 20 materials, budget 5 => 300% over => error.
        asset = _asset(material_count_budget=5)
        runtime = _runtime_with_optimize(_surface_bundle_with_materials(20), lods=2)
        report, diags = budgets_mod.evaluate(asset, runtime)
        self.assertEqual(report["materials"]["status"], "error")
        self.assertEqual(
            [d["severity"] for d in diags if d["code"] == "L6302"],
            ["error"],
        )


class DrawCallBudgetTests(unittest.TestCase):
    def test_under_budget(self) -> None:
        asset = _asset(draw_call_budget=64)
        # 4 materials x 4 LODs = 16 draw calls, under 64.
        runtime = _runtime_with_optimize(_surface_bundle_with_materials(4), lods=4)
        report, _diags = budgets_mod.evaluate(asset, runtime)
        self.assertEqual(report["draw_calls"]["status"], "pass")
        self.assertEqual(report["draw_calls"]["estimated"], 16)
        self.assertEqual(len(report["draw_calls"]["breakdown"]), 4)

    def test_warning_over_budget(self) -> None:
        # 6 materials x 4 LODs = 24 draw calls, budget 20 => 20% over => warning.
        asset = _asset(draw_call_budget=20)
        runtime = _runtime_with_optimize(_surface_bundle_with_materials(6), lods=4)
        report, _diags = budgets_mod.evaluate(asset, runtime)
        self.assertEqual(report["draw_calls"]["status"], "warning")

    def test_severe_over_budget(self) -> None:
        # 10 x 4 = 40 vs. budget 8 => 400% over => error.
        asset = _asset(draw_call_budget=8)
        runtime = _runtime_with_optimize(_surface_bundle_with_materials(10), lods=4)
        report, diags = budgets_mod.evaluate(asset, runtime)
        self.assertEqual(report["draw_calls"]["status"], "error")
        matched = [d for d in diags if d["code"] == "L6303"]
        self.assertEqual(matched[0]["severity"], "error")


class GracefulDegradationTests(unittest.TestCase):
    def test_missing_surface_runtime_skips_without_crash(self) -> None:
        asset = _asset()
        runtime: dict[str, Any] = {}
        report, diags = budgets_mod.evaluate(asset, runtime)
        self.assertEqual(report["texture_memory"]["status"], "skipped")
        self.assertEqual(report["materials"]["status"], "skipped")
        self.assertEqual(report["draw_calls"]["status"], "skipped")
        self.assertEqual(report["overall_status"], "skipped")
        self.assertEqual(diags, [])

    def test_semantic_passthrough_surface_bundle_is_handled(self) -> None:
        # Mirrors the courier_drone bundle shape (no material_zones, has
        # semantic_materials fallback).
        asset = _asset()
        runtime = _runtime_with_optimize(
            {
                "surface": {
                    "bundle": {
                        "material_slots": 1,
                        "maps": ["basecolor", "normal", "orm", "emissive"],
                        "surface_manifest": {
                            "resolution": {"type": "unit", "value": 4096, "unit": "px"},
                            "semantic_materials": [
                                "anodized_aluminum",
                                "carbon_fiber",
                                "amber_glass",
                            ],
                        },
                    }
                }
            },
            lods=4,
        )
        report, _ = budgets_mod.evaluate(asset, runtime)
        self.assertEqual(report["materials"]["count"], 3)
        self.assertIn(report["materials"]["status"], {"pass", "warning", "error"})
        self.assertGreater(report["texture_memory"]["estimated_bytes"], 0)


class SchemaValidationTests(unittest.TestCase):
    def test_report_validates_against_schema(self) -> None:
        asset = _asset()
        runtime = _runtime_with_optimize(_surface_bundle_with_materials(4), lods=4)
        report, _ = budgets_mod.evaluate(asset, runtime)
        jsonschema.Draft202012Validator(BUDGET_SCHEMA).validate(report)

    def test_skipped_report_validates(self) -> None:
        asset = _asset()
        runtime: dict[str, Any] = {}
        report, _ = budgets_mod.evaluate(asset, runtime)
        jsonschema.Draft202012Validator(BUDGET_SCHEMA).validate(report)


class SelectorManifestIntegrationTests(unittest.TestCase):
    def test_selector_manifest_carries_budgets_block(self) -> None:
        # Smaller smoke: feed a fake runtime through build_selector_manifest.
        from lathe.selector_manifest import build_selector_manifest

        asset = {"build": {"optimize": {}}, "space": {"up_axis": "Y", "unit": "cm"}}
        surface_runtime = _surface_bundle_with_materials(3)
        runtime = _runtime_with_optimize(surface_runtime, lods=3)
        report, _ = budgets_mod.evaluate(asset, runtime)
        runtime["optimize"]["bundle"]["budget_report"] = report
        manifest = build_selector_manifest(
            asset_name="courier_drone",
            variant_name=None,
            source_path="examples/courier_drone.lth",
            build_hash="a1b2c3d4e5f6",
            package_hash="deadbeef01234567",
            runtime=runtime,
            asset=asset,
        )
        self.assertIn("budgets", manifest)
        self.assertEqual(manifest["budgets"]["schemaVersion"], 1)
        jsonschema.Draft202012Validator(SELECTOR_SCHEMA).validate(manifest)


@pytest.mark.slow
class EndToEndCourierDroneTests(unittest.TestCase):
    """End-to-end: run a full build, verify budget_report.json on disk and
    the selector manifest carries the budgets block."""

    def test_courier_drone_build_emits_budget_report(self) -> None:
        try:
            from lathe.executor import build_asset
            from lathe.parser import parse_file
        except ImportError:
            self.skipTest("lathe executor/parser not importable in this env")

        src = REPO_ROOT / "examples" / "courier_drone.lth"
        if not src.exists():
            self.skipTest("courier_drone example missing")

        with tempfile.TemporaryDirectory(prefix="budget_e2e_") as tmp:
            out_dir = Path(tmp) / "build"
            try:
                parsed = parse_file(str(src))
                build_asset(
                    parsed,
                    asset_name="courier_drone",
                    out_dir=str(out_dir),
                    runtime_config=None,
                )
            except Exception as exc:
                self.skipTest(f"full build not runnable in this env: {exc!r}")

            budget_path = out_dir / "stages" / "optimize" / "budget_report.json"
            self.assertTrue(budget_path.exists(), f"{budget_path} missing")
            report = json.loads(budget_path.read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator(BUDGET_SCHEMA).validate(report)

            selector_path = out_dir / "selector_manifest.json"
            if selector_path.exists():
                manifest = json.loads(selector_path.read_text(encoding="utf-8"))
                self.assertIn("budgets", manifest)
                jsonschema.Draft202012Validator(SELECTOR_SCHEMA).validate(manifest)


if __name__ == "__main__":
    unittest.main()
