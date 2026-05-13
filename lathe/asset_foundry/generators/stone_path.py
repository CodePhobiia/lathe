"""Foundry generator: StonePathSegment.

Per masterplan §16.5 + northstar §10.3.5. A walkable path spline plus
decorative stone slabs, with explicit walkable_surface metadata.
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

_GENERATOR_ID = "stone_path_segment"


@dataclass(frozen=True)
class StonePathParameters:
    seed: int = 0
    segment_length_cm: float = 400.0
    path_width_cm: float = 130.0
    stone_count: int = 12
    stone_size_range_cm: tuple[float, float] = (28.0, 48.0)
    stone_thickness_cm: float = 12.0
    grass_exclusion_width_cm: float = 24.0
    """Strip around the path where grass scatter is excluded."""
    slope_deg: float = 0.0
    """Optional uphill/downhill slope; > 8 deg triggers a stair
    diagnostic."""


def build_stone_path_segment(
    params: StonePathParameters | None = None,
    *,
    asset_id: str = "stone_path_segment_a",
) -> FoundryAsset:
    """Build a StonePathSegment asset spec."""
    p = params if params is not None else StonePathParameters()
    half_width = p.path_width_cm / 2.0
    half_length = p.segment_length_cm / 2.0

    # Path spline: simple straight segment between two endpoints.
    spline = [
        (-half_length, 0.0, 0.0),
        (half_length, 0.0, 0.0),
    ]

    # Distribute stones along the spline with bounded jitter.
    rng_state = p.seed if p.seed != 0 else 0xDEAD
    stones: list[dict[str, Any]] = []
    stone_lo, stone_hi = p.stone_size_range_cm
    for i in range(p.stone_count):
        t = i / max(1, p.stone_count - 1) if p.stone_count > 1 else 0.5
        x = -half_length + t * p.segment_length_cm
        # Jitter laterally.
        rng_state = (1664525 * rng_state + 1013904223) & 0xFFFFFFFF
        lateral = ((rng_state / 0xFFFFFFFF) - 0.5) * (half_width * 0.6)
        rng_state = (1664525 * rng_state + 1013904223) & 0xFFFFFFFF
        size = stone_lo + (rng_state / 0xFFFFFFFF) * (stone_hi - stone_lo)
        rng_state = (1664525 * rng_state + 1013904223) & 0xFFFFFFFF
        yaw = ((rng_state / 0xFFFFFFFF) - 0.5) * 30.0
        stones.append(
            {
                "stone_id": f"{asset_id}.stone_{i:02d}",
                "translation_cm": [x, lateral, 0.0],
                "size_cm": size,
                "thickness_cm": p.stone_thickness_cm,
                "yaw_deg": yaw,
                "zone_id": f"{asset_id}.stone_{i:02d}",
            }
        )

    geometry_payload: dict[str, Any] = {
        "kind": "stone_path_segment",
        "spline_cm": [list(pt) for pt in spline],
        "path_width_cm": p.path_width_cm,
        "stones": stones,
        "grass_exclusion_width_cm": p.grass_exclusion_width_cm,
        "slope_deg": p.slope_deg,
    }

    diagnostics: list[str] = []
    if p.slope_deg > 8.0:
        diagnostics.append(
            f"slope_exceeds_walkable_threshold: {p.slope_deg:.1f} deg > 8.0; consider inserting stairs"
        )
    if p.path_width_cm < 120.0:
        diagnostics.append(
            f"path_width_below_third_person_min: {p.path_width_cm} cm < 120 cm"
        )

    material_slots = (
        MaterialSlot(
            slot_id="stone",
            zone_id_prefix=f"{asset_id}.stone",
            material_class="stone_warm_gray",
            uv_policy="triplanar",
        ),
        MaterialSlot(
            slot_id="walkable_surface",
            zone_id_prefix=f"{asset_id}.walkable",
            material_class="path_dirt_compacted",
        ),
    )

    sockets = (
        SemanticSocket(
            socket_id="endpoint_a",
            role="walkable_endpoint",
            position_cm=(-half_length, 0.0, 0.0),
        ),
        SemanticSocket(
            socket_id="endpoint_b",
            role="walkable_endpoint",
            position_cm=(half_length, 0.0, 0.0),
        ),
        SemanticSocket(
            socket_id="lantern_anchor_left",
            role="lantern_mount",
            position_cm=(0.0, half_width + 10.0, 0.0),
        ),
        SemanticSocket(
            socket_id="lantern_anchor_right",
            role="lantern_mount",
            position_cm=(0.0, -(half_width + 10.0), 0.0),
        ),
    )

    collision = CollisionSpec(
        strategy="walkable_surface_only",
        walkable_zones=(f"{asset_id}.walkable",),
        blocking_zones=(),
        hazard_zones=(),
    )

    lod_policy = LodPolicy(
        lod_levels=3,
        target_triangle_counts=(2200, 700, 200),
        preserve_silhouette=False,
        drop_at_lod_features={"stones": 2},
    )

    spec = GeneratorSpec(
        generator_id=_GENERATOR_ID,
        parameters={
            "seed": p.seed,
            "segment_length_cm": p.segment_length_cm,
            "path_width_cm": p.path_width_cm,
            "stone_count": p.stone_count,
            "stone_size_range_cm": list(p.stone_size_range_cm),
            "stone_thickness_cm": p.stone_thickness_cm,
            "grass_exclusion_width_cm": p.grass_exclusion_width_cm,
            "slope_deg": p.slope_deg,
        },
        seed=p.seed,
        style_pack_id="lowpoly_fantasy_sunset_crystal_v1",
        family="environment_piece",
        semantic_parts=("walkable_ribbon",)
        + tuple(f"stone_{i:02d}" for i in range(p.stone_count)),
        geometry_payload=geometry_payload,
        material_slots=material_slots,
        sockets=sockets,
        collision=collision,
        lod_policy=lod_policy,
        diagnostics=tuple(diagnostics),
    )

    bbox_cm = (
        (-half_length, -half_width, 0.0),
        (half_length, half_width, p.stone_thickness_cm),
    )

    return FoundryAsset(
        asset_id=asset_id,
        spec=spec,
        bbox_cm=bbox_cm,
        quality_ladder_target=5,
        notes="Foundry F5 — StonePathSegment with walkable surface.",
    )


__all__ = ["StonePathParameters", "build_stone_path_segment"]
