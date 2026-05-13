"""Foundry generator: RopeBridge.

Per masterplan §16.6 + northstar §10.3.5. Plank ribbon + posts + rope
rails + sag. Walkable surface + nav link metadata.
"""

from __future__ import annotations

import math
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

_GENERATOR_ID = "rope_bridge"


@dataclass(frozen=True)
class RopeBridgeParameters:
    seed: int = 0
    span_cm: float = 600.0
    width_cm: float = 130.0
    plank_length_cm: float = 110.0
    plank_thickness_cm: float = 4.0
    plank_count: int = 18
    sag_cm: float = 28.0
    post_height_cm: float = 110.0
    post_radius_cm: float = 4.0
    rope_radius_cm: float = 1.6
    fasteners_per_plank: int = 4


def build_rope_bridge(
    params: RopeBridgeParameters | None = None,
    *,
    asset_id: str = "rope_bridge_a",
) -> FoundryAsset:
    """Build a RopeBridge asset spec."""
    p = params if params is not None else RopeBridgeParameters()
    half_span = p.span_cm / 2.0
    half_width = p.width_cm / 2.0

    # Plank distribution along the span with parabolic sag.
    planks: list[dict[str, Any]] = []
    for i in range(p.plank_count):
        t = (i + 0.5) / p.plank_count
        x = -half_span + t * p.span_cm
        # Sag: max at center, 0 at endpoints.
        sag = -p.sag_cm * 4.0 * t * (1.0 - t)
        planks.append(
            {
                "plank_id": f"{asset_id}.plank_{i:02d}",
                "translation_cm": [x, 0.0, sag],
                "length_cm": p.plank_length_cm,
                "thickness_cm": p.plank_thickness_cm,
                "zone_id": f"{asset_id}.plank_{i:02d}",
            }
        )

    # Endpoint posts (4 — two on each side).
    posts = [
        {
            "post_id": f"{asset_id}.post_a_left",
            "translation_cm": [-half_span, half_width, 0.0],
            "zone_id": f"{asset_id}.post_a_left",
        },
        {
            "post_id": f"{asset_id}.post_a_right",
            "translation_cm": [-half_span, -half_width, 0.0],
            "zone_id": f"{asset_id}.post_a_right",
        },
        {
            "post_id": f"{asset_id}.post_b_left",
            "translation_cm": [half_span, half_width, 0.0],
            "zone_id": f"{asset_id}.post_b_left",
        },
        {
            "post_id": f"{asset_id}.post_b_right",
            "translation_cm": [half_span, -half_width, 0.0],
            "zone_id": f"{asset_id}.post_b_right",
        },
    ]

    # Rope rails: top + handrail on each side. Sample along the span.
    rail_samples = 24
    rails: list[dict[str, Any]] = []
    for side, side_y in (("left", half_width), ("right", -half_width)):
        for level in ("handrail", "footrail"):
            level_z = p.post_height_cm - 12.0 if level == "handrail" else 6.0
            samples = []
            for s in range(rail_samples + 1):
                t = s / rail_samples
                x = -half_span + t * p.span_cm
                sag = -p.sag_cm * 4.0 * t * (1.0 - t) * (0.65 if level == "footrail" else 0.3)
                samples.append([x, side_y, level_z + sag])
            rails.append(
                {
                    "rail_id": f"{asset_id}.rope_{side}_{level}",
                    "samples_cm": samples,
                    "radius_cm": p.rope_radius_cm,
                    "zone_id": f"{asset_id}.rope_{side}_{level}",
                }
            )

    geometry_payload: dict[str, Any] = {
        "kind": "rope_bridge",
        "span_cm": p.span_cm,
        "width_cm": p.width_cm,
        "planks": planks,
        "posts": posts,
        "rope_rails": rails,
        "fasteners_per_plank": p.fasteners_per_plank,
    }

    material_slots = (
        MaterialSlot(
            slot_id="planks",
            zone_id_prefix=f"{asset_id}.plank",
            material_class="wood_warm_brown",
            uv_policy="world_scale",
        ),
        MaterialSlot(
            slot_id="posts",
            zone_id_prefix=f"{asset_id}.post",
            material_class="wood_reddish_brown",
        ),
        MaterialSlot(
            slot_id="rope",
            zone_id_prefix=f"{asset_id}.rope",
            material_class="rope_fiber",
            uv_policy="triplanar",
        ),
        MaterialSlot(
            slot_id="fasteners",
            zone_id_prefix=f"{asset_id}.fastener",
            material_class="metal_bare",
        ),
    )

    sockets = (
        SemanticSocket(
            socket_id="endpoint_a",
            role="walkable_endpoint",
            position_cm=(-half_span, 0.0, 0.0),
        ),
        SemanticSocket(
            socket_id="endpoint_b",
            role="walkable_endpoint",
            position_cm=(half_span, 0.0, 0.0),
        ),
    )

    collision = CollisionSpec(
        strategy="walkable_surface_only",
        walkable_zones=tuple(f"{asset_id}.plank_{i:02d}" for i in range(p.plank_count)),
        blocking_zones=tuple(f"{asset_id}.post_{p}" for p in ("a_left", "a_right", "b_left", "b_right")),
        hazard_zones=(f"{asset_id}.bridge_edge",),
    )

    lod_policy = LodPolicy(
        lod_levels=3,
        target_triangle_counts=(3500, 1200, 350),
        preserve_silhouette=True,
        drop_at_lod_features={"rope_segments": 1, "fasteners": 2},
    )

    spec = GeneratorSpec(
        generator_id=_GENERATOR_ID,
        parameters={
            "seed": p.seed,
            "span_cm": p.span_cm,
            "width_cm": p.width_cm,
            "plank_length_cm": p.plank_length_cm,
            "plank_thickness_cm": p.plank_thickness_cm,
            "plank_count": p.plank_count,
            "sag_cm": p.sag_cm,
            "post_height_cm": p.post_height_cm,
            "post_radius_cm": p.post_radius_cm,
            "rope_radius_cm": p.rope_radius_cm,
            "fasteners_per_plank": p.fasteners_per_plank,
        },
        seed=p.seed,
        style_pack_id="lowpoly_fantasy_sunset_crystal_v1",
        family="architecture",
        semantic_parts=("planks", "posts", "rope_rails", "fasteners"),
        geometry_payload=geometry_payload,
        material_slots=material_slots,
        sockets=sockets,
        collision=collision,
        lod_policy=lod_policy,
        diagnostics=(),
    )

    bbox_cm = (
        (-half_span, -half_width, -p.sag_cm),
        (half_span, half_width, p.post_height_cm),
    )

    return FoundryAsset(
        asset_id=asset_id,
        spec=spec,
        bbox_cm=bbox_cm,
        quality_ladder_target=5,
        notes="Foundry F5 — RopeBridge with sagged plank ribbon and walkable surface.",
    )


__all__ = ["RopeBridgeParameters", "build_rope_bridge"]
