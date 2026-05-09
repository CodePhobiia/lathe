"""Tests for bounded mesh preview rendering."""

from __future__ import annotations

import trimesh

from lathe.core import rendering
from lathe.core.mesh import RuntimeMesh


def test_render_mesh_preview_samples_large_mesh(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(rendering, "MAX_PREVIEW_FACES", 3)
    mesh = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
    runtime_mesh = RuntimeMesh(
        mesh=mesh,
        face_parts=["body"] * len(mesh.faces),
        part_colors={"body": (120, 150, 190)},
        units="cm",
    )

    report = rendering.render_mesh_preview(runtime_mesh, tmp_path / "preview.png", mode="material_ids")

    assert (tmp_path / "preview.png").exists()
    assert report["status"] == "rendered_sampled_preview"
    assert report["sampled"] is True
    assert report["face_count"] == len(mesh.faces)
    assert report["rendered_face_count"] == 3
