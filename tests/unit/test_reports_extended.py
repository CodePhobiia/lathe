"""Unit tests for the RPT-1/2/3 report extensions (V0.2 E4)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from lathe.reports import (
    canonicalize_report,
    render_html_report,
    render_terminal_report,
    write_report,
)


def _minimal_report(out_dir: Path) -> dict:
    return {
        "asset": "courier_drone",
        "kind": "asset",
        "out_dir": str(out_dir),
        "certified": True,
        "score": 0.88,
        "threshold": 0.85,
        "outputs": {"glb": "stages/package/courier_drone.glb"},
        "validate_detail": {
            "semantic_quality": {
                "metrics": {"x": 0.9},
                "thresholds": {"x": 0.85},
                "diagnostics": [],
            },
        },
        "diagnostics": [],
        "repair_suggestions": [],
        "timestamp": "2026-04-24T21:00:00Z",
        "stages_runtime": {"shape": {"runtime_ms": 123.456}},
    }


def _populate_build_dir(root: Path) -> None:
    """Write selector_manifest + stage bundles mimicking a real build."""

    (root / "stages" / "shape").mkdir(parents=True)
    (root / "stages" / "optimize").mkdir(parents=True)

    (root / "selector_manifest.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "latheVersion": "0.1.0",
                "sourcePath": "examples/courier_drone.lth",
                "asset": "courier_drone",
                "buildHash": "abcd1234" * 8,
                "parts": [
                    {"id": "body", "ref": "@lathe[courier_drone#part.body]", "name": "body"},
                    {"id": "rotor_fl", "ref": "@lathe[courier_drone#part.rotor_fl]", "name": "rotor_fl"},
                    {"id": "rotor_fr", "ref": "@lathe[courier_drone#part.rotor_fr]", "name": "rotor_fr"},
                    {"id": "rotor_rl", "ref": "@lathe[courier_drone#part.rotor_rl]", "name": "rotor_rl"},
                ],
                "sockets": [
                    {
                        "id": "battery_slot",
                        "ref": "@lathe[courier_drone#socket.battery_slot]",
                        "name": "battery_slot",
                    },
                ],
                "pivots": [],
                "collisions": [],
                "lods": [{"id": "lod0", "name": "lod0"}, {"id": "lod1", "name": "lod1"}],
                "materials": [
                    {"id": "shell", "name": "shell"},
                    {"id": "trim", "name": "trim"},
                ],
            }
        ),
        encoding="utf-8",
    )

    (root / "stages" / "shape" / "bundle.json").write_text(
        json.dumps(
            {
                "backend_id": "lathe.shape.intent_mesh_handoff_v1",
                "determinism_class": "deterministic",
                "bundle_stats": {
                    "candidate_count": 2,
                    "watertight_candidate_count": 2,
                    "watertight_rate": 1.0,
                    "geometry_kernel": "lathe.geometry.manifold_v1",
                },
            }
        ),
        encoding="utf-8",
    )

    (root / "stages" / "optimize" / "lod_manifest.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "lods": [
                    {"level": 0, "ratio": 1.0, "tris": 6676, "path": "stages\\optimize\\lod_0.glb"},
                    {"level": 1, "ratio": 0.5, "tris": 3338, "path": "stages\\optimize\\lod_1.glb"},
                    {"level": 2, "ratio": 0.25, "tris": 1669, "path": "stages\\optimize\\lod_2.glb"},
                    {"level": 3, "ratio": 0.1, "tris": 668, "path": "stages\\optimize\\lod_3.glb"},
                ],
            }
        ),
        encoding="utf-8",
    )

    (root / "stages" / "optimize" / "collision_manifest.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "proxies": [
                    {
                        "name": "hull",
                        "tris": 168,
                        "path": "stages/optimize/collision_hull.glb",
                        "aabb": {"min": [-70.0, -30.0, -77.0], "max": [70.0, 20.0, 77.0]},
                    },
                    {
                        "name": "parts",
                        "path": "stages/optimize/collision_parts.glb",
                        "subproxies": [
                            {
                                "name": "body",
                                "tris": 126,
                                "aabb": {"min": [-64.0, -16.0, -70.0], "max": [64.0, 20.0, 70.0]},
                            },
                            {"name": "rotor_fl", "tris": 154},
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


class HtmlExtendedSectionsTests(unittest.TestCase):
    def test_html_renders_refs_and_selector_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build_dir = Path(tmp)
            _populate_build_dir(build_dir)
            html = render_html_report(_minimal_report(build_dir))
            self.assertIn("Refs &amp; Selector Manifest", html)
            self.assertIn("rotor_fl", html)
            self.assertIn("battery_slot", html)
            # Counts should be rendered
            self.assertIn(">4<", html)  # 4 parts
            self.assertIn("abcd1234", html)  # buildHash prefix

    def test_html_renders_geometry_kernel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build_dir = Path(tmp)
            _populate_build_dir(build_dir)
            html = render_html_report(_minimal_report(build_dir))
            self.assertIn("Geometry Kernel", html)
            self.assertIn("lathe.geometry.manifold_v1", html)
            self.assertIn("100.0%", html)  # watertight_rate

    def test_html_renders_lod_ladder_with_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build_dir = Path(tmp)
            _populate_build_dir(build_dir)
            html = render_html_report(_minimal_report(build_dir))
            self.assertIn("LOD Ladder", html)
            # 4 rows
            self.assertIn(">6676<", html)
            self.assertIn(">3338<", html)
            self.assertIn(">1669<", html)
            self.assertIn(">668<", html)
            # Paths canonicalized to forward slashes
            self.assertIn("stages/optimize/lod_0.glb", html)

    def test_html_renders_collision_proxies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build_dir = Path(tmp)
            _populate_build_dir(build_dir)
            html = render_html_report(_minimal_report(build_dir))
            self.assertIn("Collision Proxies", html)
            self.assertIn("hull", html)
            self.assertIn(">168<", html)
            # AABB formatting
            self.assertIn("-70.00", html)

    def test_html_gracefully_skips_missing_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build_dir = Path(tmp)
            # No selector_manifest, no stages/ -- a pre-Wave-6 build dir.
            html = render_html_report(_minimal_report(build_dir))
            self.assertNotIn("Refs &amp; Selector Manifest", html)
            self.assertNotIn("Geometry Kernel", html)
            self.assertNotIn("LOD Ladder", html)
            self.assertNotIn("Collision Proxies", html)
            # Core sections still render
            self.assertIn("Validators", html)


class TerminalMirrorTests(unittest.TestCase):
    def test_terminal_mirrors_extended_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build_dir = Path(tmp)
            _populate_build_dir(build_dir)
            out = render_terminal_report(_minimal_report(build_dir), use_color=False)
            self.assertIn("Refs & Selector Manifest", out)
            self.assertIn("Geometry Kernel", out)
            self.assertIn("lathe.geometry.manifold_v1", out)
            self.assertIn("LOD Ladder", out)
            self.assertIn("Collision Proxies", out)
            self.assertIn("rotor_fl", out)


class DeterministicTests(unittest.TestCase):
    def test_canonicalize_zeroes_timestamps_and_paths(self) -> None:
        report = {
            "asset": "x",
            "timestamp": "2026-04-24T21:00:00Z",
            "started_at": "2026-04-24T20:59:50.123Z",
            "out_dir": "D:\\lathe_v0_1\\dist\\x",
            "stages_runtime": {"shape": {"runtime_ms": 123.789}},
            "diagnostics": [
                {"code": "b.later", "severity": "warning", "message": "b"},
                {"code": "a.first", "severity": "warning", "message": "a"},
            ],
        }
        canon = canonicalize_report(report)
        self.assertEqual(canon["timestamp"], "0000-00-00T00:00:00Z")
        self.assertEqual(canon["started_at"], "0000-00-00T00:00:00Z")
        self.assertNotIn("\\", canon["out_dir"])
        self.assertEqual(canon["stages_runtime"]["shape"]["runtime_ms"], 124)
        # Diagnostics now sorted by code
        codes = [d["code"] for d in canon["diagnostics"]]
        self.assertEqual(codes, ["a.first", "b.later"])

    def test_deterministic_json_is_byte_identical_across_writes(self) -> None:
        # Simulate two fresh builds into the *same* output dir. Differences
        # are pure transients (timestamp, stage runtime jitter, order of
        # diagnostics). Under --deterministic both must canonicalize to
        # byte-identical bytes.
        with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
            base = {
                "asset": "courier_drone",
                "kind": "asset",
                "out_dir": "dist/courier_drone",
                "certified": True,
                "score": 0.88,
                "threshold": 0.85,
                "outputs": {"glb": "stages/package/courier_drone.glb"},
                "validate_detail": {"x": {"metrics": {}, "thresholds": {}, "diagnostics": []}},
                "diagnostics": [
                    {"code": "a.one", "severity": "info", "message": "a"},
                    {"code": "b.two", "severity": "info", "message": "b"},
                ],
                "repair_suggestions": [],
                "stages_runtime": {"shape": {"runtime_ms": 123.1}},
                "timestamp": "2026-04-24T21:00:00Z",
            }
            report_b = json.loads(json.dumps(base))
            report_b["timestamp"] = "2026-04-24T22:15:30.777Z"
            report_b["stages_runtime"]["shape"]["runtime_ms"] = 123.4
            # Different diagnostics order — canonicalization must stabilize it.
            report_b["diagnostics"] = list(reversed(report_b["diagnostics"]))

            path_a = write_report(base, Path(tmp_a), "json", deterministic=True)
            path_b = write_report(report_b, Path(tmp_b), "json", deterministic=True)

            self.assertEqual(path_a.read_bytes(), path_b.read_bytes())


if __name__ == "__main__":
    unittest.main()
