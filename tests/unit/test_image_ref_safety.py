from __future__ import annotations

from pathlib import Path

import trimesh
from lathe.shape.geometry import conditioning
from lathe.shape.geometry.conditioning import collect_shape_conditioning
from PIL import Image


def _asset_with_image(ref: str) -> dict:
    return {"refs": {"images": [ref]}}


def _asset_with_mesh(ref: str) -> dict:
    return {"refs": {"meshes": [ref]}}


def _png(path: Path, *, size: tuple[int, int] = (4, 4)) -> None:
    Image.new("RGB", size, (80, 120, 160)).save(path)


def _mesh(path: Path) -> None:
    trimesh.creation.box(extents=(1.0, 1.0, 1.0)).export(path.as_posix())


def _first_ref(report: dict) -> dict:
    return report["consumed_refs"][0]


def test_valid_project_relative_image_ref_is_consumed(tmp_path: Path) -> None:
    image = tmp_path / "front.png"
    _png(image)

    report = collect_shape_conditioning(_asset_with_image("front.png"), tmp_path)

    entry = _first_ref(report)
    assert entry["exists"] is True
    assert "rejected_reason" not in entry
    assert report["image_refs"][0]["path"] == str(image.resolve())


def test_absolute_image_ref_is_rejected(tmp_path: Path) -> None:
    image = tmp_path / "front.png"
    _png(image)

    report = collect_shape_conditioning(_asset_with_image(str(image.resolve())), tmp_path)

    entry = _first_ref(report)
    assert entry["exists"] is False
    assert entry["rejected_reason"] == "absolute_path_rejected"
    assert report["image_refs"] == []


def test_traversal_image_ref_is_rejected(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside.png"
    _png(outside)

    report = collect_shape_conditioning(_asset_with_image("../outside.png"), project)

    entry = _first_ref(report)
    assert entry["exists"] is False
    assert entry["rejected_reason"] == "path_traversal_rejected"
    assert report["image_refs"] == []


def test_oversized_image_ref_is_rejected_before_decode(tmp_path: Path, monkeypatch) -> None:
    image = tmp_path / "front.png"
    image.write_bytes(b"not-an-image-but-too-large")
    monkeypatch.setattr(conditioning, "_MAX_IMAGE_REF_BYTES", 4)

    report = collect_shape_conditioning(_asset_with_image("front.png"), tmp_path)

    entry = _first_ref(report)
    assert entry["exists"] is False
    assert entry["rejected_reason"] == "image_file_too_large"
    assert report["image_refs"] == []


def test_unsupported_image_ref_format_is_rejected_before_decode(tmp_path: Path) -> None:
    image = tmp_path / "front.gif"
    image.write_bytes(b"GIF89a")

    report = collect_shape_conditioning(_asset_with_image("front.gif"), tmp_path)

    entry = _first_ref(report)
    assert entry["exists"] is False
    assert entry["rejected_reason"] == "unsupported_image_format"
    assert report["image_refs"] == []


def test_image_dimension_limit_rejects_decompression_bomb_risk(tmp_path: Path, monkeypatch) -> None:
    image = tmp_path / "front.png"
    _png(image, size=(4, 4))
    monkeypatch.setattr(conditioning, "_MAX_IMAGE_REF_PIXELS", 4)

    report = collect_shape_conditioning(_asset_with_image("front.png"), tmp_path)

    entry = _first_ref(report)
    assert entry["exists"] is False
    assert entry["rejected_reason"] == "image_dimensions_too_large"
    assert report["image_refs"] == []


def test_valid_project_relative_mesh_ref_is_consumed(tmp_path: Path) -> None:
    mesh = tmp_path / "source.glb"
    _mesh(mesh)

    report = collect_shape_conditioning(_asset_with_mesh("source.glb"), tmp_path)

    entry = _first_ref(report)
    assert entry["exists"] is True
    assert entry["kind"] == "mesh"
    assert report["mesh_refs"][0]["path"] == str(mesh.resolve())


def test_absolute_mesh_ref_is_rejected(tmp_path: Path) -> None:
    mesh = tmp_path / "source.glb"
    _mesh(mesh)

    report = collect_shape_conditioning(_asset_with_mesh(str(mesh.resolve())), tmp_path)

    entry = _first_ref(report)
    assert entry["exists"] is False
    assert entry["rejected_reason"] == "absolute_path_rejected"
    assert report["mesh_refs"] == []


def test_traversal_mesh_ref_is_rejected(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside.glb"
    _mesh(outside)

    report = collect_shape_conditioning(_asset_with_mesh("../outside.glb"), project)

    entry = _first_ref(report)
    assert entry["exists"] is False
    assert entry["rejected_reason"] == "path_traversal_rejected"
    assert report["mesh_refs"] == []


def test_unsupported_mesh_ref_format_is_rejected(tmp_path: Path) -> None:
    mesh = tmp_path / "source.txt"
    mesh.write_bytes(b"not a mesh")

    report = collect_shape_conditioning(_asset_with_mesh("source.txt"), tmp_path)

    entry = _first_ref(report)
    assert entry["exists"] is False
    assert entry["rejected_reason"] == "unsupported_mesh_format"
    assert report["mesh_refs"] == []


def test_oversized_mesh_ref_is_rejected_before_load(tmp_path: Path, monkeypatch) -> None:
    mesh = tmp_path / "source.glb"
    mesh.write_bytes(b"glTF" + b"x" * 32)
    monkeypatch.setattr(conditioning, "_MAX_MESH_REF_BYTES", 4)

    report = collect_shape_conditioning(_asset_with_mesh("source.glb"), tmp_path)

    entry = _first_ref(report)
    assert entry["exists"] is False
    assert entry["rejected_reason"] == "mesh_file_too_large"
    assert report["mesh_refs"] == []
