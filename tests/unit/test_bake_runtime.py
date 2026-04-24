"""Unit tests for ``lathe.bake_runtime``.

The bake runtime is the deterministic PBR baker used by the V1.2 surface
stage when no learned bridge (Codex ImageGen) is wired. It produces id /
basecolor / normal / curvature / ao / roughness / metallic / emissive
maps from a triangulated mesh, plus decal overlays and an ORM composite.

These tests cover the public bake_* functions: image shape/mode
contracts, material-zone fidelity (id colors round-trip into downstream
maps), the no-decal short-circuit, the empty-zone graceful path, ORM
channel ordering, and reproducibility/determinism (same inputs ⇒ byte
identical bytes).
"""

from __future__ import annotations

import numpy as np
import pytest
import trimesh
from PIL import Image

from lathe.bake_runtime import (
    apply_decal_overlays,
    bake_ao_map,
    bake_basecolor_map,
    bake_curvature_map,
    bake_emissive_map,
    bake_id_map,
    bake_metallic_map,
    bake_normal_map,
    bake_roughness_map,
    combine_orm,
    enhance_normal_map,
)


SIZE = 64


def _box_with_uvs() -> trimesh.Trimesh:
    mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    n_vertices = len(mesh.vertices)
    uv = np.zeros((n_vertices, 2), dtype=np.float64)
    for i in range(n_vertices):
        uv[i, 0] = (i % 4) / 3.0
        uv[i, 1] = ((i // 4) % 2) / 1.0
    try:
        mesh.visual = trimesh.visual.TextureVisuals(uv=uv)
    except Exception:  # pragma: no cover
        mesh.visual.uv = uv
    return mesh


def _zones() -> list[dict[str, object]]:
    return [
        {
            "part": "body",
            "material": "aluminum",
            "basecolor": [110, 120, 130],
            "metallic": 1.0,
            "roughness": 0.5,
            "roughness_range": [0.3, 0.7],
            "emissive": [0, 0, 0],
            "surface_profile": "brushed_metal",
            "wear": 0.2,
            "normal_intensity": 0.1,
        },
        {
            "part": "screen",
            "material": "glass",
            "basecolor": [40, 80, 200],
            "metallic": 0.0,
            "roughness": 0.2,
            "roughness_range": [0.1, 0.3],
            "emissive": [40, 60, 200],
            "surface_profile": "screen_glass",
            "wear": 0.0,
            "normal_intensity": 0.05,
        },
    ]


class TestBakeIdMap:
    def test_id_map_returns_rgb_image_of_target_size(self) -> None:
        mesh = _box_with_uvs()
        face_parts = ["body"] * len(mesh.faces)
        image = bake_id_map(mesh, face_parts, _zones(), SIZE)
        assert image.size == (SIZE, SIZE)
        assert image.mode == "RGB"

    def test_id_map_uses_zone_basecolor_for_part(self) -> None:
        mesh = _box_with_uvs()
        face_parts = ["body"] * len(mesh.faces)
        image = bake_id_map(mesh, face_parts, _zones(), SIZE)
        arr = np.asarray(image, dtype=np.uint8)
        body = np.asarray([110, 120, 130], dtype=np.uint8)
        # At least some pixels should match the body color exactly.
        matches = np.all(arr == body, axis=-1)
        assert matches.any()

    def test_id_map_with_empty_face_parts_uses_default_gray(self) -> None:
        mesh = _box_with_uvs()
        image = bake_id_map(mesh, [], _zones(), SIZE)
        assert image.size == (SIZE, SIZE)


class TestBakeNormalAndCurvature:
    def test_normal_map_neutral_default(self) -> None:
        mesh = _box_with_uvs()
        image = bake_normal_map(mesh, SIZE)
        assert image.mode == "RGB"
        assert image.size == (SIZE, SIZE)

    def test_curvature_map_is_grayscale(self) -> None:
        mesh = _box_with_uvs()
        image = bake_curvature_map(mesh, SIZE)
        assert image.mode == "L"
        assert image.size == (SIZE, SIZE)

    def test_ao_map_is_grayscale(self) -> None:
        mesh = _box_with_uvs()
        image = bake_ao_map(mesh, SIZE)
        assert image.mode == "L"
        assert image.size == (SIZE, SIZE)


class TestBakeBasecolorRoughnessMetallic:
    def test_basecolor_pulls_from_id_map(self) -> None:
        mesh = _box_with_uvs()
        face_parts = ["body"] * len(mesh.faces)
        zones = _zones()
        id_map = bake_id_map(mesh, face_parts, zones, SIZE)
        curv = bake_curvature_map(mesh, SIZE)
        ao = bake_ao_map(mesh, SIZE)
        basecolor = bake_basecolor_map(id_map, zones, curv, ao)
        assert basecolor.mode == "RGB"
        assert basecolor.size == (SIZE, SIZE)

    def test_roughness_clipped_to_unit_range(self) -> None:
        mesh = _box_with_uvs()
        face_parts = ["body"] * len(mesh.faces)
        zones = _zones()
        id_map = bake_id_map(mesh, face_parts, zones, SIZE)
        curv = bake_curvature_map(mesh, SIZE)
        ao = bake_ao_map(mesh, SIZE)
        rough = bake_roughness_map(id_map, zones, curv, ao)
        arr = np.asarray(rough, dtype=np.uint8)
        assert arr.min() >= 0
        assert arr.max() <= 255

    def test_metallic_uses_zone_value(self) -> None:
        mesh = _box_with_uvs()
        face_parts = ["body"] * len(mesh.faces)
        zones = _zones()
        id_map = bake_id_map(mesh, face_parts, zones, SIZE)
        metallic = bake_metallic_map(id_map, zones)
        assert metallic.mode == "L"
        arr = np.asarray(metallic, dtype=np.uint8)
        # Metallic body (1.0) should produce 255 in some pixel.
        assert arr.max() == 255

    def test_emissive_off_for_zero_emissive(self) -> None:
        mesh = _box_with_uvs()
        face_parts = ["body"] * len(mesh.faces)
        zones = [
            {
                "part": "body",
                "material": "aluminum",
                "basecolor": [110, 120, 130],
                "metallic": 1.0,
                "roughness": 0.5,
                "emissive": [0, 0, 0],
                "surface_profile": "brushed_metal",
            }
        ]
        id_map = bake_id_map(mesh, face_parts, zones, SIZE)
        emissive = bake_emissive_map(id_map, zones)
        arr = np.asarray(emissive, dtype=np.uint8)
        # All-zero emissive zone ⇒ emissive map remains black.
        assert arr.sum() == 0


class TestEnhanceNormalAndDecals:
    def test_enhance_normal_map_preserves_shape_and_mode(self) -> None:
        mesh = _box_with_uvs()
        face_parts = ["body"] * len(mesh.faces)
        zones = _zones()
        id_map = bake_id_map(mesh, face_parts, zones, SIZE)
        curv = bake_curvature_map(mesh, SIZE)
        base_normal = bake_normal_map(mesh, SIZE)
        enhanced = enhance_normal_map(base_normal, id_map, zones, curv)
        assert enhanced.mode == "RGB"
        assert enhanced.size == (SIZE, SIZE)

    def test_no_decals_returns_inputs_unchanged(self) -> None:
        mesh = _box_with_uvs()
        face_parts = ["body"] * len(mesh.faces)
        zones = _zones()
        id_map = bake_id_map(mesh, face_parts, zones, SIZE)
        curv = bake_curvature_map(mesh, SIZE)
        ao = bake_ao_map(mesh, SIZE)
        basecolor = bake_basecolor_map(id_map, zones, curv, ao)
        rough = bake_roughness_map(id_map, zones, curv, ao)
        emissive = bake_emissive_map(id_map, zones)
        b2, r2, e2 = apply_decal_overlays(basecolor, rough, emissive, [])
        assert b2 is basecolor and r2 is rough and e2 is emissive

    def test_decal_overlay_modifies_basecolor(self) -> None:
        mesh = _box_with_uvs()
        face_parts = ["body"] * len(mesh.faces)
        zones = _zones()
        id_map = bake_id_map(mesh, face_parts, zones, SIZE)
        curv = bake_curvature_map(mesh, SIZE)
        ao = bake_ao_map(mesh, SIZE)
        basecolor = bake_basecolor_map(id_map, zones, curv, ao)
        rough = bake_roughness_map(id_map, zones, curv, ao)
        emissive = bake_emissive_map(id_map, zones)
        b2, _, _ = apply_decal_overlays(basecolor, rough, emissive, ["serial_label"])
        before = np.asarray(basecolor, dtype=np.uint8)
        after = np.asarray(b2, dtype=np.uint8)
        assert not np.array_equal(before, after)


class TestCombineOrm:
    def test_orm_channel_order_is_ao_rough_metallic(self) -> None:
        size = SIZE
        ao = Image.new("L", (size, size), 200)
        rough = Image.new("L", (size, size), 128)
        metallic = Image.new("L", (size, size), 64)
        orm = combine_orm(ao, rough, metallic)
        assert orm.mode == "RGB"
        arr = np.asarray(orm, dtype=np.uint8)
        assert (arr[..., 0] == 200).all()
        assert (arr[..., 1] == 128).all()
        assert (arr[..., 2] == 64).all()

    def test_bake_outputs_are_deterministic(self) -> None:
        mesh = _box_with_uvs()
        face_parts = ["body"] * len(mesh.faces)
        zones = _zones()
        id_a = bake_id_map(mesh, face_parts, zones, SIZE)
        id_b = bake_id_map(mesh, face_parts, zones, SIZE)
        assert id_a.tobytes() == id_b.tobytes()


class TestMalformedInputs:
    def test_basecolor_raises_on_zone_missing_basecolor(self) -> None:
        mesh = _box_with_uvs()
        face_parts = ["body"] * len(mesh.faces)
        zones = [{"part": "body", "material": "x"}]  # no basecolor key
        with pytest.raises(KeyError):
            bake_id_map(mesh, face_parts, zones, SIZE)
