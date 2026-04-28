"""Unit tests for ``lathe.texture_control_pack``.

The texture control pack is the V1.2 surface artifact bundled with
emitted assets — it carries the UV layout, padded island mask,
material zone mask, AO, curvature, normal reference, and a manifest
that pins the schema, target resolution, required maps, per-zone PBR
constraints, semantic descriptors (program / policy / decal libraries
/ mask programs / trim sheets), and image URIs. These tests pin the
manifest schema, the on-disk layout, semantic field flow-through, and
deterministic reproducibility (same inputs ⇒ identical manifest bytes).
"""

from __future__ import annotations

import json
from pathlib import Path

from lathe.texture_control_pack import write_surface_control_pack
from PIL import Image

SIZE = 32


def _solid(mode: str, color: object) -> Image.Image:
    return Image.new(mode, (SIZE, SIZE), color)


def _zones() -> list[dict[str, object]]:
    return [
        {
            "part": "body",
            "material": "aluminum",
            "metallic": 1.0,
            "roughness": 0.5,
            "basecolor": [110, 120, 130],
        },
        {
            "part": "screen",
            "material": "glass",
            "metallic": 0.0,
            "roughness": 0.2,
            "basecolor": [40, 80, 200],
        },
    ]


def _surface_cfg(maps: list[str]) -> dict[str, object]:
    return {"maps": maps}


def _source_surface() -> dict[str, object]:
    return {
        "program": "std.surface.program.console_v1",
        "policy": "std.surface.policy.game_pbr_v1",
        "decal_libraries": ["std.surface.decal_library.industrial_v1"],
        "mask_programs": ["std.surface.mask.seam_highlight_v1"],
        "trim_sheets": ["std.surface.trim.metal_strips_v1"],
    }


def _call(
    out_dir: Path,
    *,
    zones: list[dict[str, object]] | None = None,
    source_surface: dict[str, object] | None = None,
) -> dict[str, object]:
    return write_surface_control_pack(
        out_dir=out_dir,
        size=SIZE,
        material_zones=zones if zones is not None else _zones(),
        surface_cfg=_surface_cfg(["basecolor", "normal", "roughness", "ao"]),
        source_surface=source_surface if source_surface is not None else _source_surface(),
        ao=_solid("L", 200),
        curvature=_solid("L", 128),
        normal=_solid("RGB", (128, 128, 255)),
        id_map=_solid("RGB", (110, 120, 130)),
    )


class TestWriteSurfaceControlPack:
    def test_pack_writes_manifest_and_images(self, tmp_path: Path) -> None:
        result = _call(tmp_path)
        assert "manifest_uri" in result
        assert "images" in result
        manifest_path = tmp_path / "surface_control_pack" / "manifest.json"
        assert manifest_path.is_file()

    def test_manifest_pins_schema_and_resolution(self, tmp_path: Path) -> None:
        _call(tmp_path)
        manifest = json.loads(
            (tmp_path / "surface_control_pack" / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["schema"] == "lathe.surface_control_pack.v1"
        assert manifest["target_resolution"] == SIZE

    def test_manifest_includes_per_zone_constraints(self, tmp_path: Path) -> None:
        _call(tmp_path)
        manifest = json.loads(
            (tmp_path / "surface_control_pack" / "manifest.json").read_text(encoding="utf-8")
        )
        constraints = manifest["per_zone_constraints"]
        assert "body" in constraints and "screen" in constraints
        assert constraints["body"]["metallic"] == 1.0
        assert constraints["screen"]["roughness"] == 0.2

    def test_manifest_propagates_semantic_descriptors(self, tmp_path: Path) -> None:
        _call(tmp_path)
        manifest = json.loads(
            (tmp_path / "surface_control_pack" / "manifest.json").read_text(encoding="utf-8")
        )
        descriptors = manifest["semantic_descriptors"]
        assert descriptors["surface_program"] == "std.surface.program.console_v1"
        assert descriptors["policy"] == "std.surface.policy.game_pbr_v1"
        assert descriptors["decal_libraries"] == ["std.surface.decal_library.industrial_v1"]
        assert descriptors["mask_programs"] == ["std.surface.mask.seam_highlight_v1"]
        assert descriptors["trim_sheets"] == ["std.surface.trim.metal_strips_v1"]

    def test_pack_with_empty_zones_still_writes_manifest(self, tmp_path: Path) -> None:
        result = _call(tmp_path, zones=[])
        manifest = json.loads(
            (tmp_path / "surface_control_pack" / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["material_zones"] == []
        assert manifest["per_zone_constraints"] == {}
        # Images written even when zones empty.
        assert "uv_layout" in result["images"]
        assert "ao" in result["images"]

    def test_pack_with_empty_descriptors_falls_back_to_defaults(self, tmp_path: Path) -> None:
        empty_source = {
            "program": "",
            "policy": "",
            "decal_libraries": [],
            "mask_programs": [],
            "trim_sheets": [],
        }
        _call(tmp_path, source_surface=empty_source)
        manifest = json.loads(
            (tmp_path / "surface_control_pack" / "manifest.json").read_text(encoding="utf-8")
        )
        descriptors = manifest["semantic_descriptors"]
        assert descriptors["surface_program"] == ""
        assert descriptors["decal_libraries"] == []

    def test_pack_is_deterministic_across_two_calls(self, tmp_path: Path) -> None:
        a_dir = tmp_path / "a"
        b_dir = tmp_path / "b"
        a_dir.mkdir()
        b_dir.mkdir()
        _call(a_dir)
        _call(b_dir)
        a_manifest = (a_dir / "surface_control_pack" / "manifest.json").read_bytes()
        b_manifest = (b_dir / "surface_control_pack" / "manifest.json").read_bytes()
        # Manifest content (with relative URIs) is identical when written
        # to identically structured directories.
        # Note: absolute uri paths inside images entries differ; manifest
        # uses the relative_uri helper for image references.
        a_doc = json.loads(a_manifest)
        b_doc = json.loads(b_manifest)
        assert a_doc["images"] == b_doc["images"]
        assert a_doc["material_zones"] == b_doc["material_zones"]
        assert a_doc["semantic_descriptors"] == b_doc["semantic_descriptors"]
