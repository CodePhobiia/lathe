"""Unit tests for the convex-collision proxy module (STAGE-2, V0.2 E3)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import trimesh

from lathe.stages import collision as collision_mod


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema" / "collision_manifest.schema.json"


@pytest.fixture()
def box() -> trimesh.Trimesh:
    return trimesh.creation.box(extents=(2.0, 3.0, 4.0))


@pytest.fixture()
def two_box_scene() -> tuple[trimesh.Trimesh, list[str]]:
    """A mesh with two named parts (box_a, box_b) fused, plus face-parts labels."""
    a = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    b = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    b.apply_translation([3.0, 0.0, 0.0])
    faces_a = len(a.faces)
    combined = trimesh.util.concatenate([a, b])
    face_parts = ["box_a"] * faces_a + ["box_b"] * (len(combined.faces) - faces_a)
    return combined, face_parts


def test_single_hull_is_watertight_and_convex(box: trimesh.Trimesh) -> None:
    proxy = collision_mod.single_hull(box)
    assert proxy.mesh.is_watertight
    assert proxy.mesh.is_convex


def test_single_hull_aabb_matches_source_mesh(box: trimesh.Trimesh) -> None:
    proxy = collision_mod.single_hull(box)
    # The convex hull of a box IS the box — AABB must match within 1e-6.
    for i in range(3):
        assert proxy.aabb_min[i] == pytest.approx(float(box.bounds[0][i]), abs=1e-6)
        assert proxy.aabb_max[i] == pytest.approx(float(box.bounds[1][i]), abs=1e-6)


def test_per_part_hulls_each_watertight_and_convex(two_box_scene: tuple[trimesh.Trimesh, list[str]]) -> None:
    mesh, face_parts = two_box_scene
    proxies = collision_mod.per_part_hulls(mesh, face_parts)
    assert len(proxies) == 2
    for p in proxies:
        assert p.mesh.is_watertight, f"proxy {p.name} not watertight"
        assert p.mesh.is_convex, f"proxy {p.name} not convex"


def test_per_part_hull_names_match_face_parts(two_box_scene: tuple[trimesh.Trimesh, list[str]]) -> None:
    mesh, face_parts = two_box_scene
    proxies = collision_mod.per_part_hulls(mesh, face_parts)
    names = sorted(p.name for p in proxies)
    assert names == ["box_a", "box_b"]


def test_combine_hulls_produces_nonempty_mesh(two_box_scene: tuple[trimesh.Trimesh, list[str]]) -> None:
    mesh, face_parts = two_box_scene
    proxies = collision_mod.per_part_hulls(mesh, face_parts)
    combined = collision_mod.combine_hulls(proxies)
    assert int(len(combined.faces)) == sum(int(len(p.mesh.faces)) for p in proxies)
    assert int(len(combined.vertices)) == sum(int(len(p.mesh.vertices)) for p in proxies)


def test_manifest_validates_against_schema(box: trimesh.Trimesh, two_box_scene: tuple[trimesh.Trimesh, list[str]]) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    mesh, face_parts = two_box_scene
    hull = collision_mod.single_hull(mesh)
    parts = collision_mod.per_part_hulls(mesh, face_parts)
    manifest = {
        "schemaVersion": 1,
        "proxies": [
            {
                "name": "hull",
                "tris": int(len(hull.mesh.faces)),
                "verts": int(len(hull.mesh.vertices)),
                "aabb": {"min": list(hull.aabb_min), "max": list(hull.aabb_max)},
                "path": "stages/optimize/collision_hull.glb",
            },
            {
                "name": "parts",
                "path": "stages/optimize/collision_parts.glb",
                "subproxies": [
                    {
                        "name": p.name,
                        "tris": int(len(p.mesh.faces)),
                        "verts": int(len(p.mesh.vertices)),
                        "aabb": {"min": list(p.aabb_min), "max": list(p.aabb_max)},
                    }
                    for p in parts
                ],
            },
        ],
    }
    jsonschema.validate(manifest, schema)


def test_hull_face_planes_keep_all_vertices_on_one_side(box: trimesh.Trimesh) -> None:
    """Direct convexity check: for each face, every vertex lies on or behind the plane."""
    proxy = collision_mod.single_hull(box)
    hull = proxy.mesh
    centroids = hull.triangles.mean(axis=1)
    normals = hull.face_normals
    verts = np.asarray(hull.vertices)
    tol = 1e-6
    for fi in range(len(hull.faces)):
        n = normals[fi]
        d = -float(np.dot(n, centroids[fi]))
        signed = verts @ n + d
        assert np.all(signed <= tol), f"face {fi} has vertices on outside (max={signed.max()})"
