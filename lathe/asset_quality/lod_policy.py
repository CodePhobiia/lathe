"""LOD policy compiler (Wave 9 / research §6+§16).

Per research §6: a 1m crate at 125k tris is a pipeline smell. LODs
should be generated from feature rules first, decimation second.
This module is the contract surface for that compiler.

A ``LODPolicy`` declares per-LOD targets (bevel segments, fastener
representation, panel-groove representation, target tris). The
synthesizer/optimize stages consume the policy to emit per-LOD
ShapeProgram variants instead of decimating one fused mesh.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

CONTRACT_VERSION = "lathe.asset.lod_policy_v1"

# Default LOD ladder for hard-surface props (research §6 target).
DEFAULT_LOD_LADDER: tuple[tuple[str, int, float], ...] = (
    # (lod_id, target_tris, screen_size_threshold)
    ("LOD0", 18000, 0.5),
    ("LOD1", 6000, 0.2),
    ("LOD2", 1500, 0.05),
    ("LOD3", 300, 0.01),
)


@dataclass(frozen=True)
class FeatureRepresentation:
    """How a feature is represented at a given LOD."""

    representation: str  # geometry | normal_stamp | texture_only | removed | proxy | impostor
    bevel_segments: int = 1
    detail_scale: float = 1.0


@dataclass(frozen=True)
class LODLevelPolicy:
    """Per-LOD policy block."""

    lod_id: str
    target_tris: int
    screen_size_threshold: float
    bevel_segments: int = 1
    fastener_representation: str = "geometry"
    panel_groove_representation: str = "geometry"
    trim_representation: str = "geometry"
    secondary_part_representation: str = "geometry"
    impostor: bool = False


@dataclass(frozen=True)
class LODPolicy:
    """Full LOD policy — applied during synthesizer LOD variant emission."""

    levels: tuple[LODLevelPolicy, ...] = ()
    rationale: str = ""


def default_lod_policy(class_anchor: str = "crate") -> LODPolicy:
    """Return a canonical LOD policy per class anchor."""
    if class_anchor == "door":
        return LODPolicy(
            levels=(
                LODLevelPolicy(
                    lod_id="LOD0",
                    target_tris=15000,
                    screen_size_threshold=0.5,
                    bevel_segments=2,
                    fastener_representation="geometry",
                    panel_groove_representation="geometry",
                ),
                LODLevelPolicy(
                    lod_id="LOD1",
                    target_tris=4000,
                    screen_size_threshold=0.2,
                    bevel_segments=1,
                    fastener_representation="normal_stamp",
                    panel_groove_representation="geometry",
                ),
                LODLevelPolicy(
                    lod_id="LOD2",
                    target_tris=1000,
                    screen_size_threshold=0.05,
                    bevel_segments=0,
                    fastener_representation="texture_only",
                    panel_groove_representation="normal_stamp",
                ),
                LODLevelPolicy(
                    lod_id="LOD3",
                    target_tris=200,
                    screen_size_threshold=0.01,
                    bevel_segments=0,
                    fastener_representation="removed",
                    panel_groove_representation="texture_only",
                    impostor=False,
                ),
            ),
            rationale="door class — silhouette dominated by panel rectangle; fasteners can drop early",
        )
    # Default: crate / hard-surface prop.
    return LODPolicy(
        levels=(
            LODLevelPolicy(
                lod_id="LOD0",
                target_tris=18000,
                screen_size_threshold=0.5,
                bevel_segments=2,
                fastener_representation="geometry",
                panel_groove_representation="geometry",
                trim_representation="geometry",
                secondary_part_representation="geometry",
            ),
            LODLevelPolicy(
                lod_id="LOD1",
                target_tris=6000,
                screen_size_threshold=0.2,
                bevel_segments=1,
                fastener_representation="normal_stamp",
                panel_groove_representation="geometry",
                trim_representation="geometry",
                secondary_part_representation="geometry",
            ),
            LODLevelPolicy(
                lod_id="LOD2",
                target_tris=1500,
                screen_size_threshold=0.05,
                bevel_segments=0,
                fastener_representation="texture_only",
                panel_groove_representation="normal_stamp",
                trim_representation="normal_stamp",
                secondary_part_representation="texture_only",
            ),
            LODLevelPolicy(
                lod_id="LOD3",
                target_tris=300,
                screen_size_threshold=0.01,
                bevel_segments=0,
                fastener_representation="removed",
                panel_groove_representation="removed",
                trim_representation="removed",
                secondary_part_representation="removed",
                impostor=False,
            ),
        ),
        rationale="hard-surface crate — full geometry hero, normal-stamp gameplay, texture distant, proxy fallback",
    )


def projected_px_for_camera_distance(
    feature_world_cm: float, camera_distance_m: float, screen_height_px: int = 1080, vfov_deg: float = 60.0
) -> float:
    """Compute projected pixel width — matches render_rigs.canonical_views formula."""
    if camera_distance_m <= 0:
        return 0.0
    tan_half = math.tan(math.radians(vfov_deg) / 2.0)
    if tan_half <= 0:
        return 0.0
    return (feature_world_cm / 100.0) * screen_height_px / (2.0 * camera_distance_m * tan_half)


def representation_for_lod(
    feature_world_cm: float,
    lod_level: LODLevelPolicy,
    is_silhouette_feature: bool = False,
) -> FeatureRepresentation:
    """Decide how a feature is represented at a given LOD.

    Uses the LOD's screen-size threshold as the equivalent camera
    distance — the lower the threshold, the further away the asset
    is when this LOD is selected, and the more aggressive the
    representation downgrade.
    """
    # screen_size_threshold → equivalent camera distance: lower threshold
    # means further away, so we synthesize a representative distance.
    if lod_level.screen_size_threshold >= 0.4:
        camera_distance_m = 2.0
    elif lod_level.screen_size_threshold >= 0.15:
        camera_distance_m = 5.0
    elif lod_level.screen_size_threshold >= 0.04:
        camera_distance_m = 15.0
    else:
        camera_distance_m = 50.0

    px = projected_px_for_camera_distance(feature_world_cm, camera_distance_m)
    if is_silhouette_feature and px >= 1.0:
        return FeatureRepresentation(representation="geometry", bevel_segments=lod_level.bevel_segments)
    if px >= 2.0:
        return FeatureRepresentation(representation="geometry", bevel_segments=lod_level.bevel_segments)
    if px >= 1.0:
        return FeatureRepresentation(representation="normal_stamp", bevel_segments=max(0, lod_level.bevel_segments - 1))
    if px >= 0.5:
        return FeatureRepresentation(representation="texture_only", bevel_segments=0)
    return FeatureRepresentation(representation="removed", bevel_segments=0)


__all__ = [
    "CONTRACT_VERSION",
    "DEFAULT_LOD_LADDER",
    "FeatureRepresentation",
    "LODLevelPolicy",
    "LODPolicy",
    "default_lod_policy",
    "projected_px_for_camera_distance",
    "representation_for_lod",
]
