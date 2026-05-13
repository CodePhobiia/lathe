"""Parameter-rate PBR baker (Wave 16 / research §11+§12).

Consumes a ``ZoneAtlas`` + per-zone ``WearMaskRecipe``s, resolves
each zone's ``MaterialArchetype``, composes ``PBRChannelParams`` via
``compose_pbr_channels``, and emits a ``PBRMaterialSlotManifest``
that the surface stage's texture baker reads as input.

This is parameter-rate, not texture-rate. The texture baker turns the
per-zone channel params + the mesh's baked support maps (normal, AO,
curvature, world_normal, position) into actual basecolor / ORM /
normal / height textures. That texture-rate work is the per-engine
follow-on; this module lands the channel parameter contract so the
baker has a typed input.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .mask_compiler import WearMaskRecipe, compile_mask_graph
from .pbr_composer import PBRChannelParams, compose_pbr_channels, resolve_archetype
from .zone_binding import ZoneAtlas

CONTRACT_VERSION = "lathe.surface.pbr_baker_v1"


@dataclass(frozen=True)
class PBRMaterialSlot:
    """One material slot in the asset's slot manifest."""

    slot_index: int
    slot_name: str
    zone_id: str
    material_class: str
    archetype_id: str
    channels: PBRChannelParams
    face_count: int = 0
    decal_slot_index: int | None = None


@dataclass(frozen=True)
class PBRMaterialSlotManifest:
    """The full per-asset PBR material slot manifest."""

    contract_version: str
    asset_id: str
    slots: tuple[PBRMaterialSlot, ...]
    fallback_material_class: str = "painted_steel"

    def slot_count(self) -> int:
        return len(self.slots)

    def slot_by_zone(self, zone_id: str) -> PBRMaterialSlot | None:
        for s in self.slots:
            if s.zone_id == zone_id:
                return s
        return None


def bake_pbr_material_slots(
    asset_id: str,
    atlas: ZoneAtlas,
    visual_language_id: str = "utility_industrial_v1",
    condition_by_zone: Mapping[str, float] | None = None,
    environment: str = "neutral",
) -> PBRMaterialSlotManifest:
    """Bake a parameter-rate PBR slot manifest from a ZoneAtlas.

    For each zone: resolve the (material_class, visual_language)
    archetype, build a WearMaskRecipe (default condition 0.3 unless
    overridden per zone), compile the mask graph, compose channel
    params, and emit a slot. The slot index is the zone's position
    in the atlas.
    """
    by_zone = condition_by_zone or {}
    slots: list[PBRMaterialSlot] = []
    for index, zone in enumerate(atlas.zones):
        material_class = zone.material_class or "painted_steel"
        archetype = resolve_archetype(material_class, visual_language_id)
        condition = float(by_zone.get(zone.zone_id, 0.3))
        recipe = WearMaskRecipe(
            target_zone_id=zone.zone_id,
            condition=condition,
            environment=environment,
            mask_weights={},
        )
        mask_graph = compile_mask_graph(recipe)
        channels = compose_pbr_channels(archetype, mask_graph)
        face_count = len(atlas.faces_for_zone(zone.zone_id))
        slots.append(
            PBRMaterialSlot(
                slot_index=index,
                slot_name=f"{material_class}.{zone.zone_id}",
                zone_id=zone.zone_id,
                material_class=material_class,
                archetype_id=archetype.archetype_id,
                channels=channels,
                face_count=face_count,
            )
        )
    return PBRMaterialSlotManifest(
        contract_version=CONTRACT_VERSION,
        asset_id=asset_id,
        slots=tuple(slots),
    )


def manifest_to_dict(manifest: PBRMaterialSlotManifest) -> dict[str, Any]:
    """Serialize a PBRMaterialSlotManifest for build_report inclusion."""
    return {
        "contract_version": manifest.contract_version,
        "asset_id": manifest.asset_id,
        "slot_count": manifest.slot_count(),
        "fallback_material_class": manifest.fallback_material_class,
        "slots": [
            {
                "slot_index": s.slot_index,
                "slot_name": s.slot_name,
                "zone_id": s.zone_id,
                "material_class": s.material_class,
                "archetype_id": s.archetype_id,
                "face_count": s.face_count,
                "channels": {
                    "base_color_rgb": list(s.channels.base_color_rgb),
                    "roughness": s.channels.roughness,
                    "metallic": s.channels.metallic,
                    "normal_strength": s.channels.normal_strength,
                    "height_displacement_cm": s.channels.height_displacement_cm,
                    "ao_intensity": s.channels.ao_intensity,
                    "emissive_rgb": list(s.channels.emissive_rgb),
                    "decal_slot_active": s.channels.decal_slot_active,
                },
            }
            for s in manifest.slots
        ],
    }


__all__ = [
    "CONTRACT_VERSION",
    "PBRMaterialSlot",
    "PBRMaterialSlotManifest",
    "bake_pbr_material_slots",
    "manifest_to_dict",
]
