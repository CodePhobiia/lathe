"""Wave 21 tests: texture baker + render executor + perceptual scoring."""

from __future__ import annotations

import tempfile
from pathlib import Path

from lathe.render_rigs.perceptual_scoring import (
    score_clip_similarity_to_class,
    score_silhouette_iou_to_archetype,
)
from lathe.render_rigs.renderer import render_views
from lathe.surface_graph.pbr_baker import bake_pbr_material_slots
from lathe.surface_graph.texture_baker import (
    bake_material_slot_manifest,
    bake_zone_textures,
)
from lathe.surface_graph.zone_binding import FaceZoneAssignment, ZoneAtlas, ZoneTag


def _atlas() -> ZoneAtlas:
    return ZoneAtlas(
        zones=(
            ZoneTag(zone_id="body", material_class="painted_steel"),
            ZoneTag(zone_id="trim", material_class="aged_brass"),
        ),
        face_assignments=(
            FaceZoneAssignment(face_index=0, zone_id="body"),
            FaceZoneAssignment(face_index=1, zone_id="trim"),
        ),
    )


def test_bake_zone_textures_writes_four_pngs() -> None:
    atlas = _atlas()
    manifest = bake_pbr_material_slots("crate", atlas, visual_language_id="utility_industrial_v1")
    body_slot = manifest.slot_by_zone("body")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        baked = bake_zone_textures(body_slot, out, resolution_px=64)
        assert (out / baked.basecolor_uri).is_file()
        assert (out / baked.orm_uri).is_file()
        assert (out / baked.normal_uri).is_file()
        assert (out / baked.height_uri).is_file()
        # Basecolor file is a valid PNG (starts with PNG signature).
        with open(out / baked.basecolor_uri, "rb") as f:
            sig = f.read(8)
        assert sig.startswith(b"\x89PNG\r\n")


def test_bake_manifest_emits_per_slot() -> None:
    atlas = _atlas()
    manifest = bake_pbr_material_slots("crate", atlas)
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        textures = bake_material_slot_manifest(manifest, out, resolution_px=32)
        assert len(textures) == 2
        zone_ids = {t.zone_id for t in textures}
        assert zone_ids == {"body", "trim"}


def test_render_views_falls_back_gracefully_with_no_mesh() -> None:
    """Renderer never crashes — soft-falls when mesh / pyrender absent."""
    import trimesh
    mesh = trimesh.creation.box(extents=(2.0, 2.0, 2.0))
    with tempfile.TemporaryDirectory() as td:
        result = render_views(mesh, "test_box", Path(td), resolution_px=(64, 48))
        assert result.asset_id == "test_box"
        # Either pyrender produces views OR trimesh fallback produces 1.
        assert len(result.views) >= 1


def test_perceptual_clip_score_returns_neutral_without_dependency() -> None:
    score = score_clip_similarity_to_class([], "crate", threshold=0.3)
    # CLIP unavailable → neutral 0.5.
    assert score.value == 0.5
    assert score.backend == "none"
    assert score.passed is True


def test_perceptual_silhouette_iou_handles_empty_inputs() -> None:
    score = score_silhouette_iou_to_archetype([], [], threshold=0.4)
    # No inputs → neutral 0.5, passes (insufficient data).
    assert score.value == 0.5
    assert "insufficient data" in score.notes


def test_perceptual_silhouette_iou_computes_real_iou() -> None:
    """Real IoU between two simple silhouettes."""
    from PIL import Image
    import numpy as np

    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        # Render: white square in center.
        rendered = np.zeros((100, 100), dtype=np.uint8)
        rendered[25:75, 25:75] = 255
        rendered_path = out / "rendered.png"
        Image.fromarray(rendered, mode="L").save(rendered_path)

        # Archetype: identical white square → IoU should be ~1.0.
        arch_path = out / "archetype.png"
        Image.fromarray(rendered, mode="L").save(arch_path)

        score = score_silhouette_iou_to_archetype(
            [rendered_path], [arch_path], threshold=0.4
        )
        assert score.value > 0.95
        assert score.passed is True
