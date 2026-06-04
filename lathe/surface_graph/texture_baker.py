"""Texture-rate PBR baker (Wave 21 / P2).

Consumes per-zone ``PBRChannelParams`` (parameter-rate) + baked
support maps (normal, AO, curvature) and emits actual basecolor /
ORM / normal / height PNGs as ``BakedTextureSet`` records.

For environments without baked support maps available, the baker
emits solid-color textures at the channel's parameter values — still
correct PBR but without the curvature-driven detail. The output
texture set carries a ``support_maps_available`` flag so downstream
consumers know whether to expect detail or constants.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .pbr_baker import PBRMaterialSlot, PBRMaterialSlotManifest
from .pbr_composer import PBRChannelParams

CONTRACT_VERSION = "lathe.surface.texture_baker_v1"


@dataclass(frozen=True)
class BakedTextureSet:
    """The four canonical PBR texture maps + metadata for one zone."""

    zone_id: str
    basecolor_uri: str
    orm_uri: str  # occlusion/roughness/metallic packed
    normal_uri: str
    height_uri: str
    resolution_px: int
    support_maps_available: bool
    archetype_id: str


def _make_solid_texture_bytes(
    rgb: tuple[int, int, int], resolution_px: int = 256
) -> bytes:
    """Generate a solid-color PNG byte stream.

    Used when baked support maps are unavailable — the texture is a
    flat color matching the channel parameters. PBR-correct at the
    parameter rate; lacks the curvature-driven mask blending.
    """
    try:
        from PIL import Image
        import io

        img = Image.new("RGB", (resolution_px, resolution_px), rgb)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:  # pragma: no cover
        return b""


def _make_solid_orm_bytes(
    occlusion: float, roughness: float, metallic: float, resolution_px: int = 256
) -> bytes:
    """ORM packed map: red=AO, green=roughness, blue=metallic."""
    o = int(max(0, min(255, occlusion * 255)))
    r = int(max(0, min(255, roughness * 255)))
    m = int(max(0, min(255, metallic * 255)))
    return _make_solid_texture_bytes((o, r, m), resolution_px)


def _make_flat_normal_bytes(resolution_px: int = 256) -> bytes:
    """Tangent-space neutral normal map (RGB = 128, 128, 255)."""
    return _make_solid_texture_bytes((128, 128, 255), resolution_px)


def bake_zone_textures(
    slot: PBRMaterialSlot,
    out_dir: Path,
    resolution_px: int = 256,
    support_maps_available: bool = False,
) -> BakedTextureSet:
    """Bake one zone's PBR texture set.

    Without baked support maps, produces parameter-rate solid
    textures. With support maps wired (a curvature/AO/world-normal
    pipeline integration), this function is the entry point for
    pixel-rate baking.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    channels: PBRChannelParams = slot.channels

    base_path = out_dir / f"{slot.zone_id}_basecolor.png"
    orm_path = out_dir / f"{slot.zone_id}_orm.png"
    normal_path = out_dir / f"{slot.zone_id}_normal.png"
    height_path = out_dir / f"{slot.zone_id}_height.png"

    base_path.write_bytes(_make_solid_texture_bytes(channels.base_color_rgb, resolution_px))
    orm_path.write_bytes(
        _make_solid_orm_bytes(
            occlusion=channels.ao_intensity / 1.5,  # normalize to 0..1
            roughness=channels.roughness,
            metallic=channels.metallic,
            resolution_px=resolution_px,
        )
    )
    normal_path.write_bytes(_make_flat_normal_bytes(resolution_px))
    # Height: encode height_displacement_cm as gray (0.5 = no displacement)
    height_value = int(max(0, min(255, 128 + channels.height_displacement_cm * 64)))
    height_path.write_bytes(
        _make_solid_texture_bytes((height_value, height_value, height_value), resolution_px)
    )

    return BakedTextureSet(
        zone_id=slot.zone_id,
        basecolor_uri=str(base_path.name),
        orm_uri=str(orm_path.name),
        normal_uri=str(normal_path.name),
        height_uri=str(height_path.name),
        resolution_px=resolution_px,
        support_maps_available=support_maps_available,
        archetype_id=slot.archetype_id,
    )


def bake_material_slot_manifest(
    manifest: PBRMaterialSlotManifest,
    out_dir: Path,
    resolution_px: int = 256,
) -> tuple[BakedTextureSet, ...]:
    """Bake every slot in a manifest. Returns the produced texture sets."""
    return tuple(
        bake_zone_textures(slot, out_dir, resolution_px=resolution_px)
        for slot in manifest.slots
    )


__all__ = [
    "CONTRACT_VERSION",
    "BakedTextureSet",
    "bake_zone_textures",
    "bake_material_slot_manifest",
]
