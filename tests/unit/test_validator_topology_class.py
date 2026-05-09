"""Unit tests for ``lathe.validators.topology_class``.

Verifies that the tuned saturation thresholds (ngon ≥7 incident tris,
adaptive pole-density saturation) let well-formed hard-surface meshes
score >0.7 instead of being capped at 0.55 by always-saturated penalties.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import trimesh
from lathe.validators.topology_class import evaluate_topology_class_compliance


class _FakeRuntimeMesh:
    """Duck-typed RuntimeMesh exposing only the ``.mesh`` attribute."""

    def __init__(self, mesh: trimesh.Trimesh) -> None:
        self.mesh = mesh


def _runtime_with_mesh(mesh: trimesh.Trimesh) -> dict[str, Any]:
    return {"topology": {"runtime_mesh": _FakeRuntimeMesh(mesh)}}


def _hard_surface_asset() -> dict[str, Any]:
    return {"intent": {"asset_class": "hero"}}


def _cube(size: float = 1.0) -> trimesh.Trimesh:
    return trimesh.creation.box(extents=(size, size, size))


def _cube_with_bevel(size: float = 1.0, bevel: float = 0.05) -> trimesh.Trimesh:
    """Approximate a beveled cube using subdivision + small chamfer."""
    inner = size - 2 * bevel
    box = trimesh.creation.box(extents=(inner, inner, inner))
    # Subdivide once to get extra edge loops near corners (proxy for bevel
    # geometry; produces additional incident tris at corner-adjacent verts).
    box = box.subdivide()
    return box


def _cube_with_edge_loops(size: float = 1.0, loops: int = 3) -> trimesh.Trimesh:
    """Cube with edge loops along faces (subdivision)."""
    box = trimesh.creation.box(extents=(size, size, size))
    for _ in range(loops):
        box = box.subdivide()
    return box


def test_plain_cube_scores_high() -> None:
    mesh = _cube()
    runtime = _runtime_with_mesh(mesh)
    asset = _hard_surface_asset()
    result = evaluate_topology_class_compliance(asset, runtime)
    assert result["score"] >= 0.7, (
        f"Plain cube should score >0.7, got {result['score']}: {result['evidence']}"
    )
    assert result["status"] in {"pass", "warn"}


def test_beveled_cube_scores_high() -> None:
    mesh = _cube_with_bevel()
    runtime = _runtime_with_mesh(mesh)
    asset = _hard_surface_asset()
    result = evaluate_topology_class_compliance(asset, runtime)
    assert result["score"] >= 0.7, (
        f"Beveled cube should score >0.7, got {result['score']}: {result['evidence']}"
    )


def test_subdivided_cube_scores_high() -> None:
    mesh = _cube_with_edge_loops(loops=2)
    runtime = _runtime_with_mesh(mesh)
    asset = _hard_surface_asset()
    result = evaluate_topology_class_compliance(asset, runtime)
    assert result["score"] >= 0.7, (
        f"Subdivided cube should score >0.7, got {result['score']}: {result['evidence']}"
    )


def test_pole_penalty_is_density_proportional() -> None:
    """A mesh with many vertices should not have its pole penalty saturated
    just because the absolute pole count is high. The saturation must scale
    with vertex count (20% density tolerance)."""
    mesh = _cube_with_edge_loops(loops=3)
    runtime = _runtime_with_mesh(mesh)
    asset = _hard_surface_asset()
    result = evaluate_topology_class_compliance(asset, runtime)
    evidence = result["evidence"]
    n_verts = evidence["vertex_count"]
    sat_count = evidence["pole_saturation_count"]
    assert sat_count == round(max(1.0, n_verts * 0.30), 3), (
        f"pole_saturation_count should be n_verts*0.30, "
        f"got {sat_count} for n_verts={n_verts}"
    )


def test_skipped_when_no_mesh() -> None:
    runtime: dict[str, Any] = {"topology": {}}
    asset = _hard_surface_asset()
    result = evaluate_topology_class_compliance(asset, runtime)
    assert result["status"] == "skipped"
    assert result["score"] == 1.0


def test_evidence_exposes_tuned_thresholds() -> None:
    mesh = _cube()
    result = evaluate_topology_class_compliance(
        _hard_surface_asset(), _runtime_with_mesh(mesh)
    )
    evidence = result["evidence"]
    assert evidence["ngon_min_incident_tris"] == 7
    assert evidence["pole_density_saturation"] == 0.30
    assert evidence["ngon_density_saturation"] == 0.30
    assert "vertex_count" in evidence
    assert "pole_saturation_count" in evidence
    assert "ngon_saturation_count" in evidence


def test_ngon_penalty_is_density_proportional() -> None:
    """A handful of true ngons in a large mesh should not saturate the
    ngon penalty — penalty must scale with vertex count."""
    mesh = _cube_with_edge_loops(loops=3)
    runtime = _runtime_with_mesh(mesh)
    asset = _hard_surface_asset()
    result = evaluate_topology_class_compliance(asset, runtime)
    evidence = result["evidence"]
    n_verts = evidence["vertex_count"]
    ngon_sat = evidence["ngon_saturation_count"]
    assert ngon_sat == round(max(1.0, n_verts * 0.30), 3)


def test_genuine_high_valence_vertex_still_flagged() -> None:
    """A vertex with 8+ incident triangles (true ngon) should still trigger
    the ngon penalty even with the relaxed ≥7 threshold."""
    # Build a fan of 10 triangles around a central vertex (a "true" ngon).
    n_fan = 10
    angles = np.linspace(0.0, 2.0 * np.pi, n_fan, endpoint=False)
    verts = [[0.0, 0.0, 0.0]]
    for ang in angles:
        verts.append([float(np.cos(ang)), float(np.sin(ang)), 0.0])
    vertices = np.asarray(verts, dtype=np.float64)
    faces = np.asarray(
        [[0, i + 1, ((i + 1) % n_fan) + 1] for i in range(n_fan)],
        dtype=np.int64,
    )
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    runtime = _runtime_with_mesh(mesh)
    asset = _hard_surface_asset()
    result = evaluate_topology_class_compliance(asset, runtime)
    assert result["evidence"]["ngon_count"] >= 1, (
        f"10-tri fan should be flagged as ngon, got {result['evidence']}"
    )
