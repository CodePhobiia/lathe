"""Foundry generator: LanternPost.

Per masterplan §16.8 + northstar §10.3.4. Post + base + crossbeam +
lantern housing + emissive core.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ._base import (
    CollisionSpec,
    FoundryAsset,
    GeneratorSpec,
    LodPolicy,
    MaterialSlot,
    SemanticSocket,
)

_GENERATOR_ID = "lantern_post"


@dataclass(frozen=True)
class LanternPostParameters:
    seed: int = 0
    post_height_cm: float = 220.0
    post_radius_cm: float = 5.0
    base_width_cm: float = 18.0
    base_height_cm: float = 6.0
    crossbeam_length_cm: float = 32.0
    crossbeam_thickness_cm: float = 4.0
    lantern_size_cm: float = 16.0
    """Cubic housing edge length."""
    lantern_offset_cm: float = 14.0
    """How far the lantern hangs from the post under the crossbeam."""
    emissive_color_hex: str = "#ffba5a"


def build_lantern_post(
    params: LanternPostParameters | None = None,
    *,
    asset_id: str = "lantern_post_a",
) -> FoundryAsset:
    """Build a LanternPost asset spec."""
    p = params if params is not None else LanternPostParameters()
    lantern_z = p.post_height_cm - p.lantern_offset_cm

    geometry_payload: dict[str, Any] = {
        "kind": "lantern_post",
        "post": {
            "zone_id": f"{asset_id}.post",
            "height_cm": p.post_height_cm,
            "radius_cm": p.post_radius_cm,
        },
        "base": {
            "zone_id": f"{asset_id}.base",
            "width_cm": p.base_width_cm,
            "height_cm": p.base_height_cm,
        },
        "crossbeam": {
            "zone_id": f"{asset_id}.crossbeam",
            "length_cm": p.crossbeam_length_cm,
            "thickness_cm": p.crossbeam_thickness_cm,
            "z_offset_cm": p.post_height_cm - 12.0,
        },
        "lantern": {
            "zone_id": f"{asset_id}.lantern",
            "size_cm": p.lantern_size_cm,
            "translation_cm": [
                p.crossbeam_length_cm * 0.4,
                0.0,
                lantern_z,
            ],
        },
        "emissive_core": {
            "zone_id": f"{asset_id}.emissive",
            "color_hex": p.emissive_color_hex,
        },
    }

    material_slots = (
        MaterialSlot(
            slot_id="post",
            zone_id_prefix=f"{asset_id}.post",
            material_class="wood_warm_brown",
        ),
        MaterialSlot(
            slot_id="base",
            zone_id_prefix=f"{asset_id}.base",
            material_class="stone_warm_gray",
        ),
        MaterialSlot(
            slot_id="crossbeam",
            zone_id_prefix=f"{asset_id}.crossbeam",
            material_class="metal_warm",
        ),
        MaterialSlot(
            slot_id="lantern_housing",
            zone_id_prefix=f"{asset_id}.lantern",
            material_class="metal_warm",
        ),
        MaterialSlot(
            slot_id="lantern_glass",
            zone_id_prefix=f"{asset_id}.emissive",
            material_class="lantern_emissive_warm",
            palette_token=p.emissive_color_hex,
        ),
    )

    sockets = (
        SemanticSocket(
            socket_id="ground_anchor",
            role="ground_anchor",
            position_cm=(0.0, 0.0, 0.0),
        ),
        SemanticSocket(
            socket_id="light_emitter",
            role="point_light",
            position_cm=(p.crossbeam_length_cm * 0.4, 0.0, lantern_z),
        ),
    )

    collision = CollisionSpec(
        strategy="capsule",
        walkable_zones=(),
        blocking_zones=(f"{asset_id}.post",),
        hazard_zones=(),
    )

    lod_policy = LodPolicy(
        lod_levels=3,
        target_triangle_counts=(1200, 400, 100),
        preserve_silhouette=True,
        drop_at_lod_features={"crossbeam_detail": 2, "lantern_housing_detail": 2},
    )

    spec = GeneratorSpec(
        generator_id=_GENERATOR_ID,
        parameters={
            "seed": p.seed,
            "post_height_cm": p.post_height_cm,
            "post_radius_cm": p.post_radius_cm,
            "base_width_cm": p.base_width_cm,
            "base_height_cm": p.base_height_cm,
            "crossbeam_length_cm": p.crossbeam_length_cm,
            "crossbeam_thickness_cm": p.crossbeam_thickness_cm,
            "lantern_size_cm": p.lantern_size_cm,
            "lantern_offset_cm": p.lantern_offset_cm,
            "emissive_color_hex": p.emissive_color_hex,
        },
        seed=p.seed,
        style_pack_id="lowpoly_fantasy_sunset_crystal_v1",
        family="prop",
        semantic_parts=(
            "post",
            "base",
            "crossbeam",
            "lantern_housing",
            "emissive_core",
        ),
        geometry_payload=geometry_payload,
        material_slots=material_slots,
        sockets=sockets,
        collision=collision,
        lod_policy=lod_policy,
        diagnostics=(),
    )

    bbox_cm = (
        (-p.base_width_cm / 2.0, -p.base_width_cm / 2.0, 0.0),
        (
            max(p.base_width_cm / 2.0, p.crossbeam_length_cm * 0.5),
            max(p.base_width_cm / 2.0, p.lantern_size_cm),
            p.post_height_cm,
        ),
    )

    return FoundryAsset(
        asset_id=asset_id,
        spec=spec,
        bbox_cm=bbox_cm,
        quality_ladder_target=5,
        notes="Foundry F5 — LanternPost with warm emissive core.",
    )


__all__ = ["LanternPostParameters", "build_lantern_post"]
