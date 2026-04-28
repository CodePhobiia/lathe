"""Unit tests for ``lathe.validators.geometry_integrity``.

Covers the self-intersection, normal-consistency, and opt-in
body-count-stability checks, plus graceful degradation when the
runtime lacks a topology bundle.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import trimesh
from lathe.executor import build_asset
from lathe.parser import parse_file
from lathe.validators.geometry_integrity import evaluate_geometry_integrity

REPO_ROOT = Path(__file__).resolve().parents[2]


class _FakeRuntimeMesh:
    """Duck-typed RuntimeMesh exposing only the ``.mesh`` attribute."""

    def __init__(self, mesh: trimesh.Trimesh) -> None:
        self.mesh = mesh


def _runtime_with_mesh(mesh: trimesh.Trimesh) -> dict[str, Any]:
    return {"topology": {"runtime_mesh": _FakeRuntimeMesh(mesh)}}


def _cube(size: float = 1.0) -> trimesh.Trimesh:
    return trimesh.creation.box(extents=(size, size, size))


def _self_intersecting_pair() -> trimesh.Trimesh:
    """Two triangles whose interiors pierce each other."""
    vertices = np.array(
        [
            # Triangle A (in xz plane at y=0)
            [-1.0, 0.0, -1.0],
            [1.0, 0.0, -1.0],
            [0.0, 0.0, 1.0],
            # Triangle B (in yz plane at x=0, pierces A)
            [0.0, -1.0, -0.5],
            [0.0, 1.0, -0.5],
            [0.0, 0.0, 0.8],
        ],
        dtype=np.float64,
    )
    faces = np.array([[0, 1, 2], [3, 4, 5]], dtype=np.int64)
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def _inverted_cube() -> trimesh.Trimesh:
    """Cube with half its faces flipped — inconsistent winding."""
    mesh = _cube()
    faces = np.asarray(mesh.faces).copy()
    faces[: len(faces) // 2] = faces[: len(faces) // 2, ::-1]
    return trimesh.Trimesh(vertices=mesh.vertices, faces=faces, process=False)


def _non_manifold_mesh() -> trimesh.Trimesh:
    """Three triangles sharing an edge — non-manifold."""
    vertices = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.5, 1.0, 0.0],
            [0.5, -1.0, 0.0],
            [0.5, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    faces = np.array([[0, 1, 2], [0, 1, 3], [0, 1, 4]], dtype=np.int64)
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


class _StubKernel:
    def __init__(self, counts: list[int]) -> None:
        self._counts = iter(counts)

    def body_count(self, _mesh: trimesh.Trimesh) -> int:
        return int(next(self._counts))


class GeometryIntegrityTests(unittest.TestCase):
    def test_clean_cube_reports_no_diagnostics(self) -> None:
        runtime = _runtime_with_mesh(_cube())
        report = evaluate_geometry_integrity({"name": "cube"}, runtime)
        self.assertEqual(report["diagnostics"], [])
        self.assertEqual(report["metrics"]["self_intersection_rate"], 0.0)
        self.assertEqual(report["metrics"]["normal_consistency"], 1.0)
        self.assertEqual(report["metrics"]["body_count_stability"], 1.0)

    def test_self_intersection_emits_l6201(self) -> None:
        runtime = _runtime_with_mesh(_self_intersecting_pair())
        report = evaluate_geometry_integrity({"name": "x"}, runtime)
        codes = [d["code"] for d in report["diagnostics"]]
        self.assertIn("L6201", codes)
        self.assertGreater(report["metrics"]["self_intersection_rate"], 0.0)

    def test_non_manifold_mesh_does_not_crash(self) -> None:
        runtime = _runtime_with_mesh(_non_manifold_mesh())
        report = evaluate_geometry_integrity({"name": "x"}, runtime)
        self.assertIn("metrics", report)
        self.assertIn("diagnostics", report)

    def test_inconsistent_winding_emits_l6202(self) -> None:
        runtime = _runtime_with_mesh(_inverted_cube())
        report = evaluate_geometry_integrity({"name": "x"}, runtime)
        codes = [d["code"] for d in report["diagnostics"]]
        self.assertIn("L6202", codes)
        self.assertLess(report["metrics"]["normal_consistency"], 1.0)

    def test_body_count_stability_check_default_off_skips_rerun(self) -> None:
        calls = {"count": 0}

        class CountingKernel:
            def body_count(self, _mesh: trimesh.Trimesh) -> int:
                calls["count"] += 1
                return 1

        runtime = _runtime_with_mesh(_cube())
        runtime["shape"] = {"kernel": CountingKernel()}
        report = evaluate_geometry_integrity({"name": "cube"}, runtime)
        self.assertEqual(calls["count"], 0)
        self.assertEqual(report["metrics"]["body_count_stability"], 1.0)
        self.assertNotIn("L6203", [d["code"] for d in report["diagnostics"]])

    def test_body_count_stability_check_on_stable(self) -> None:
        runtime = _runtime_with_mesh(_cube())
        runtime["shape"] = {"kernel": _StubKernel([1, 1, 1])}
        asset = {
            "name": "cube",
            "build": {"shape": {"body_count_stability_check": True}},
        }
        report = evaluate_geometry_integrity(asset, runtime)
        self.assertEqual(report["metrics"]["body_count_stability"], 1.0)
        codes = [d["code"] for d in report["diagnostics"]]
        self.assertNotIn("L6203", codes)

    def test_body_count_stability_check_on_unstable_emits_l6203(self) -> None:
        runtime = _runtime_with_mesh(_cube())
        runtime["shape"] = {"kernel": _StubKernel([1, 2, 1])}
        asset = {
            "name": "cube",
            "build": {"shape": {"body_count_stability_check": True}},
        }
        report = evaluate_geometry_integrity(asset, runtime)
        self.assertLess(report["metrics"]["body_count_stability"], 1.0)
        l6203 = [d for d in report["diagnostics"] if d["code"] == "L6203"]
        self.assertEqual(len(l6203), 1)
        self.assertEqual(l6203[0]["severity"], "error")

    def test_geometry_strict_escalates_intersection_severity(self) -> None:
        runtime = _runtime_with_mesh(_self_intersecting_pair())
        asset = {"name": "x", "build": {"shape": {"geometry_strict": True}}}
        report = evaluate_geometry_integrity(asset, runtime)
        l6201 = [d for d in report["diagnostics"] if d["code"] == "L6201"]
        self.assertEqual(len(l6201), 1)
        self.assertEqual(l6201[0]["severity"], "error")

    def test_missing_topology_runtime_graceful(self) -> None:
        report = evaluate_geometry_integrity({"name": "x"}, {})
        self.assertEqual(report["diagnostics"], [])
        self.assertFalse(report["evidence"]["evaluated"])
        self.assertEqual(report["metrics"]["self_intersection_rate"], 0.0)
        self.assertEqual(report["metrics"]["normal_consistency"], 1.0)
        self.assertEqual(report["metrics"]["body_count_stability"], 1.0)

    def test_none_runtime_mesh_graceful(self) -> None:
        runtime = {"topology": {"runtime_mesh": None}}
        report = evaluate_geometry_integrity({"name": "x"}, runtime)
        self.assertEqual(report["diagnostics"], [])
        self.assertFalse(report["evidence"]["evaluated"])

    def test_empty_mesh_graceful(self) -> None:
        empty = trimesh.Trimesh(
            vertices=np.zeros((0, 3)), faces=np.zeros((0, 3), dtype=np.int64), process=False
        )
        runtime = _runtime_with_mesh(empty)
        report = evaluate_geometry_integrity({"name": "x"}, runtime)
        self.assertFalse(report["evidence"]["evaluated"])

    def test_default_severity_is_warning(self) -> None:
        runtime = _runtime_with_mesh(_self_intersecting_pair())
        report = evaluate_geometry_integrity({"name": "x"}, runtime)
        l6201 = [d for d in report["diagnostics"] if d["code"] == "L6201"]
        self.assertEqual(len(l6201), 1)
        self.assertEqual(l6201[0]["severity"], "warning")


@pytest.mark.slow
class CourierDroneIntegrationTests(unittest.TestCase):
    _CACHE: dict[str, Any] | None = None

    @classmethod
    def _build(cls) -> dict[str, Any]:
        if cls._CACHE is not None:
            return cls._CACHE
        program = parse_file(REPO_ROOT / "examples" / "courier_drone.lth")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "courier_drone"
            build_asset(program, "courier_drone", out)
            report = json.loads((out / "stages" / "validate" / "report.json").read_text(encoding="utf-8"))
        cls._CACHE = {"report": report}
        return cls._CACHE

    def test_courier_drone_build_surfaces_geometry_integrity(self) -> None:
        bundle = self._build()["report"]
        self.assertIn("geometry_integrity", bundle)
        section = bundle["geometry_integrity"]
        self.assertIn("metrics", section)
        errors = [d for d in section.get("diagnostics", []) if d.get("severity") == "error"]
        self.assertEqual(
            errors,
            [],
            f"geometry_integrity must not emit error diagnostics on courier_drone; got {errors}",
        )

    def test_courier_drone_overall_score_preserved(self) -> None:
        bundle = self._build()["report"]
        self.assertGreaterEqual(
            float(bundle["score"]),
            0.86,
            "courier_drone build must still certify ≥0.86 after geometry_integrity wiring",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
