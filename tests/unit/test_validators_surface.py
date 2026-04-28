"""Unit tests for ``lathe.validators.surface_quality.evaluate_surface_quality``.

Exercises each of the six ``SURFACE_THRESHOLDS`` branches plus the
empty-bundle refusal and the ``build_surface_validation_ir`` helper.
"""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

import pytest
from lathe.executor import build_asset
from lathe.parser import parse_file
from lathe.validators.surface_quality import (
    SURFACE_THRESHOLDS,
    build_surface_validation_ir,
    evaluate_surface_quality,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.slow
_BUILT_DIR: Path | None = None
_BUILT_TMP: tempfile.TemporaryDirectory | None = None
_BUILT_ASSET: dict[str, Any] | None = None
_BUILT_SURFACE_BUNDLE: dict[str, Any] | None = None


def _ensure_built() -> tuple[Path, dict[str, Any], dict[str, Any]]:
    """Produce a persistent on-disk build of ``courier_drone``.

    ``build_asset`` writes the surface stage's PNG maps under
    ``stages/surface/maps``; the surface validator reads those files via
    ``stage_dir``. The tempdir must outlive the test session, so we keep a
    module-level ``TemporaryDirectory`` handle.
    """
    global _BUILT_DIR, _BUILT_TMP, _BUILT_ASSET, _BUILT_SURFACE_BUNDLE
    if _BUILT_DIR is not None and _BUILT_DIR.exists():
        return _BUILT_DIR, _BUILT_ASSET or {}, _BUILT_SURFACE_BUNDLE or {}
    _BUILT_TMP = tempfile.TemporaryDirectory(prefix="lathe_surface_unit_")
    out = Path(_BUILT_TMP.name) / "courier_drone"
    program = parse_file(REPO_ROOT / "examples" / "courier_drone.lth")
    build_asset(program, "courier_drone", out)
    _BUILT_DIR = out
    _BUILT_ASSET = json.loads((out / "materialized_asset.json").read_text(encoding="utf-8"))
    _BUILT_SURFACE_BUNDLE = json.loads(
        (out / "stages" / "surface" / "bundle.json").read_text(encoding="utf-8")
    )
    return _BUILT_DIR, _BUILT_ASSET, _BUILT_SURFACE_BUNDLE


def _baseline_runtime() -> tuple[dict[str, Any], dict[str, Any]]:
    out, asset, bundle = _ensure_built()
    runtime = {
        "surface": {
            "bundle": copy.deepcopy(bundle),
            "stage_dir": out / "stages" / "surface",
        }
    }
    return copy.deepcopy(asset), runtime


class SurfaceQualityCertifiedTests(unittest.TestCase):
    def test_surface_control_pack_clears_all_thresholds(self) -> None:
        asset, runtime = _baseline_runtime()
        report = evaluate_surface_quality(asset, runtime)
        self.assertTrue(report["ok"], f"unexpected diagnostics: {[d['name'] for d in report['diagnostics']]}")
        self.assertEqual(report["diagnostics"], [])
        for metric, minimum in SURFACE_THRESHOLDS.items():
            self.assertGreaterEqual(report["metrics"][metric], minimum, f"{metric} must clear threshold")


class SurfaceQualityRejectsBadBundleTests(unittest.TestCase):
    def test_empty_bundle_emits_diagnostic_per_threshold(self) -> None:
        asset = {"name": "empty_asset"}
        runtime: dict[str, Any] = {"surface": {"bundle": {}}}
        report = evaluate_surface_quality(asset, runtime)
        self.assertFalse(report["ok"])
        names = {d["name"] for d in report["diagnostics"]}
        for metric in SURFACE_THRESHOLDS:
            self.assertIn(f"surface_{metric}_failed", names)
        for diag in report["diagnostics"]:
            self.assertEqual(diag["severity"], "error")
            self.assertEqual(diag["stage"], "surface")
            self.assertEqual(diag["asset"], "empty_asset")

    def test_non_hero_backend_id_uses_available_map_evidence(self) -> None:
        asset, runtime = _baseline_runtime()
        runtime["surface"]["bundle"]["backend_id"] = "lathe.surface.other_fallback_v0"
        report = evaluate_surface_quality(asset, runtime)
        self.assertTrue(report["ok"], f"unexpected diagnostics: {[d['name'] for d in report['diagnostics']]}")
        self.assertGreater(report["metrics"]["surface_authoring_quality"], 0.0)
        self.assertGreater(report["metrics"]["surface_material_zone_coherence"], 0.0)

    def test_missing_image_map_directory_zeroes_evidence(self) -> None:
        asset, runtime = _baseline_runtime()
        # Point stage_dir at an empty scratch location so the validator can't
        # find basecolor/normal/orm/ao/curvature/id maps.
        with tempfile.TemporaryDirectory() as scratch:
            runtime["surface"]["stage_dir"] = Path(scratch)
            report = evaluate_surface_quality(asset, runtime)
        self.assertFalse(report["ok"])
        names = {d["name"] for d in report["diagnostics"]}
        self.assertIn("surface_surface_authoring_quality_failed", names)
        self.assertIn("surface_surface_normal_richness_failed", names)

    def test_diagnostic_carries_metric_actual_and_minimum(self) -> None:
        asset = {"name": "probe"}
        runtime: dict[str, Any] = {"surface": {"bundle": {}}}
        report = evaluate_surface_quality(asset, runtime)
        self.assertTrue(report["diagnostics"])
        for diag in report["diagnostics"]:
            self.assertIn("metric", diag["details"])
            self.assertIn("actual", diag["details"])
            self.assertIn("minimum", diag["details"])
            self.assertLess(diag["details"]["actual"], diag["details"]["minimum"])
            self.assertEqual(diag["path"], f"validate.surface.{diag['details']['metric']}")

    def test_report_schema_and_threshold_view(self) -> None:
        asset = {"name": "x"}
        runtime: dict[str, Any] = {"surface": {"bundle": {}}}
        report = evaluate_surface_quality(asset, runtime)
        self.assertEqual(report["schema"], "lathe.surface_quality_report.v1")
        self.assertEqual(report["asset"], "x")
        self.assertEqual(report["thresholds"], SURFACE_THRESHOLDS)


class SurfaceValidationIRTests(unittest.TestCase):
    def test_surface_validation_ir_lists_expected_metrics_and_backend(self) -> None:
        surface_cfg = {"maps": ["basecolor", "normal", "orm"]}
        backend_report = {"selected_backend_id": "lathe.surface.hero_pbr_v1"}
        ir = build_surface_validation_ir(surface_cfg, backend_report)
        self.assertEqual(ir["schema"], "lathe.surface_validation_ir.v1")
        self.assertEqual(ir["backend"], "lathe.surface.hero_pbr_v1")
        self.assertEqual(ir["required_maps"], ["basecolor", "normal", "orm"])
        self.assertIn("surface_authoring_quality", ir["evidence_metrics"])
        self.assertIn("material_zone_coherence", ir["evidence_metrics"])


if __name__ == "__main__":
    unittest.main()
