"""Foundry generator: CozyCottage.

Per masterplan §16.1 + northstar §5.1.1. Wall shell + exaggerated
gable roof + door + warm emissive windows + timber framing +
optional chimney. Multi-variant + game-ready.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ._base import (
    CollisionSpec,
    FoundryAsset,
    GeneratorSpec,
    LodPolicy,
    MaterialSlot,
    SemanticSocket,
)

_GENERATOR_ID = "cozy_cottage"


@dataclass(frozen=True)
class CozyCottageParameters:
    seed: int = 0
    width_cm: float = 360.0
    depth_cm: float = 280.0
    wall_height_cm: float = 220.0
    roof_pitch_height_cm: float = 180.0
    roof_overhang_cm: float = 50.0
    door_width_cm: float = 90.0
    door_height_cm: float = 180.0
    window_count: int = 3
    window_width_cm: float = 80.0
    window_height_cm: float = 90.0
    timber_frame_thickness_cm: float = 14.0
    chimney_present: bool = True
    chimney_width_cm: float = 50.0
    chimney_height_cm: float = 90.0


def build_cozy_cottage(
    params: CozyCottageParameters | None = None,
    *,
    asset_id: str = "cozy_cottage_a",
) -> FoundryAsset:
    """Build a CozyCottage asset spec."""
    p = params if params is not None else CozyCottageParameters()
    half_w = p.width_cm / 2.0
    half_d = p.depth_cm / 2.0
    roof_top_z = p.wall_height_cm + p.roof_pitch_height_cm

    geometry_payload: dict[str, Any] = {
        "kind": "cozy_cottage",
        "wall_shell": {
            "zone_id_prefix": f"{asset_id}.wall",
            "width_cm": p.width_cm,
            "depth_cm": p.depth_cm,
            "height_cm": p.wall_height_cm,
            "thickness_cm": 14.0,
        },
        "roof_gable": {
            "zone_id_prefix": f"{asset_id}.roof",
            "pitch_height_cm": p.roof_pitch_height_cm,
            "overhang_cm": p.roof_overhang_cm,
            "ridge_axis": "y",
        },
        "door": {
            "zone_id": f"{asset_id}.door",
            "width_cm": p.door_width_cm,
            "height_cm": p.door_height_cm,
            "wall_side": "front_y_neg",
            "translation_cm": [0.0, -half_d, p.door_height_cm / 2.0],
        },
        "windows": [
            {
                "window_id": f"{asset_id}.window_{i:02d}",
                "translation_cm": [
                    -half_w * 0.55 + i * (half_w * 1.1 / max(1, p.window_count - 1)),
                    -half_d,
                    p.wall_height_cm * 0.6,
                ],
                "width_cm": p.window_width_cm,
                "height_cm": p.window_height_cm,
                "zone_id": f"{asset_id}.window_{i:02d}",
            }
            for i in range(p.window_count)
        ],
        "timber_frame": {
            "zone_id_prefix": f"{asset_id}.timber",
            "thickness_cm": p.timber_frame_thickness_cm,
            "patterns": ["corner_posts", "horizontal_belt", "vertical_studs"],
        },
        "chimney": (
            {
                "zone_id": f"{asset_id}.chimney",
                "width_cm": p.chimney_width_cm,
                "height_cm": p.chimney_height_cm,
                "translation_cm": [half_w * 0.6, 0.0, roof_top_z],
            }
            if p.chimney_present
            else None
        ),
    }

    diagnostics: list[str] = []
    if p.roof_pitch_height_cm < p.wall_height_cm * 0.5:
        diagnostics.append(
            f"roof_pitch_too_shallow: {p.roof_pitch_height_cm:.0f}cm < 50% of wall_height ({p.wall_height_cm:.0f}cm); cottage may read boxy"
        )
    if p.window_count == 0:
        diagnostics.append("missing_window_glow: cottage has no windows, will fail style pack window_emissive_warm requirement")
    if p.window_count > 5:
        diagnostics.append(
            f"window_count_above_recommended: {p.window_count} > 5; cottage may read as office not cozy"
        )

    material_slots = (
        MaterialSlot(
            slot_id="wall",
            zone_id_prefix=f"{asset_id}.wall",
            material_class="wall_plaster",
            uv_policy="world_scale",
        ),
        MaterialSlot(
            slot_id="roof",
            zone_id_prefix=f"{asset_id}.roof",
            material_class="roof_thatch_golden",
            uv_policy="trim_sheet",
        ),
        MaterialSlot(
            slot_id="door",
            zone_id_prefix=f"{asset_id}.door",
            material_class="wood_reddish_brown",
        ),
        MaterialSlot(
            slot_id="window_emissive",
            zone_id_prefix=f"{asset_id}.window",
            material_class="window_emissive_warm",
            palette_token="#f5b03d",
        ),
        MaterialSlot(
            slot_id="timber_frame",
            zone_id_prefix=f"{asset_id}.timber",
            material_class="wood_warm_brown",
        ),
        MaterialSlot(
            slot_id="chimney",
            zone_id_prefix=f"{asset_id}.chimney",
            material_class="stone_warm_gray",
        ),
    )

    sockets = (
        SemanticSocket(
            socket_id="door_entry",
            role="door_entry",
            position_cm=(0.0, -half_d, 0.0),
        ),
        SemanticSocket(
            socket_id="ground_anchor",
            role="ground_anchor",
            position_cm=(0.0, 0.0, 0.0),
        ),
        SemanticSocket(
            socket_id="chimney_smoke_emitter",
            role="emitter",
            position_cm=(half_w * 0.6, 0.0, roof_top_z + p.chimney_height_cm),
        ),
    )

    collision = CollisionSpec(
        strategy="compound_hulls",
        walkable_zones=(),
        blocking_zones=(f"{asset_id}.wall", f"{asset_id}.roof"),
        hazard_zones=(),
    )

    lod_policy = LodPolicy(
        lod_levels=4,
        target_triangle_counts=(15000, 5000, 1500, 400),
        preserve_silhouette=True,
        drop_at_lod_features={
            "timber_frame_detail": 1,
            "window_detail": 2,
            "chimney_detail": 2,
            "roof_overhang": 3,
        },
    )

    spec = GeneratorSpec(
        generator_id=_GENERATOR_ID,
        parameters={
            "seed": p.seed,
            "width_cm": p.width_cm,
            "depth_cm": p.depth_cm,
            "wall_height_cm": p.wall_height_cm,
            "roof_pitch_height_cm": p.roof_pitch_height_cm,
            "roof_overhang_cm": p.roof_overhang_cm,
            "door_width_cm": p.door_width_cm,
            "door_height_cm": p.door_height_cm,
            "window_count": p.window_count,
            "window_width_cm": p.window_width_cm,
            "window_height_cm": p.window_height_cm,
            "timber_frame_thickness_cm": p.timber_frame_thickness_cm,
            "chimney_present": p.chimney_present,
            "chimney_width_cm": p.chimney_width_cm,
            "chimney_height_cm": p.chimney_height_cm,
        },
        seed=p.seed,
        style_pack_id="lowpoly_fantasy_sunset_crystal_v1",
        family="architecture",
        semantic_parts=(
            "wall_shell",
            "roof_gable",
            "door",
            "windows",
            "timber_frame",
        )
        + (("chimney",) if p.chimney_present else ()),
        geometry_payload=geometry_payload,
        material_slots=material_slots,
        sockets=sockets,
        collision=collision,
        lod_policy=lod_policy,
        diagnostics=tuple(diagnostics),
    )

    chimney_top = roof_top_z + (p.chimney_height_cm if p.chimney_present else 0.0)
    bbox_cm = (
        (-half_w - p.roof_overhang_cm, -half_d - p.roof_overhang_cm, 0.0),
        (half_w + p.roof_overhang_cm, half_d + p.roof_overhang_cm, chimney_top),
    )

    return FoundryAsset(
        asset_id=asset_id,
        spec=spec,
        bbox_cm=bbox_cm,
        quality_ladder_target=5,
        notes="Foundry F5 — CozyCottage with exaggerated roof + emissive windows.",
    )


__all__ = ["CozyCottageParameters", "build_cozy_cottage"]
