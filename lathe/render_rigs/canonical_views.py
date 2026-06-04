"""Canonical 8-view + auxiliary-pass camera definitions.

Per research §7: each generated asset should render 8 RGB views
(front/back/left/right/top + 3× 3/4 views) plus auxiliary passes
(normal, depth, material_id, part_id, silhouette). Scoring against
class anchors uses these standardized views.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ViewSpec:
    """One canonical camera view."""

    view_id: str
    description: str
    # Spherical coords relative to the asset's centroid.
    azimuth_deg: float = 0.0       # 0 = +X, 90 = +Y, 180 = -X, 270 = -Y
    elevation_deg: float = 0.0     # 0 = horizontal, +90 = top, -90 = bottom
    distance_factor: float = 1.5   # multiplier of asset diagonal
    fov_deg: float = 35.0
    aspect: float = 1.33
    role: str = "rgb"              # rgb | top | three_quarter


CANONICAL_VIEWS: tuple[ViewSpec, ...] = (
    ViewSpec(
        view_id="front",
        description="Looking at the +Y face from -Y direction.",
        azimuth_deg=270.0,
        elevation_deg=5.0,
        distance_factor=1.5,
    ),
    ViewSpec(
        view_id="back",
        description="Looking at the -Y face from +Y direction.",
        azimuth_deg=90.0,
        elevation_deg=5.0,
        distance_factor=1.5,
    ),
    ViewSpec(
        view_id="left",
        description="Looking at the -X face from +X direction.",
        azimuth_deg=180.0,
        elevation_deg=0.0,
        distance_factor=1.5,
    ),
    ViewSpec(
        view_id="right",
        description="Looking at the +X face from -X direction.",
        azimuth_deg=0.0,
        elevation_deg=0.0,
        distance_factor=1.5,
    ),
    ViewSpec(
        view_id="top",
        description="Looking down at the +Z face.",
        azimuth_deg=0.0,
        elevation_deg=85.0,
        distance_factor=1.8,
        role="top",
    ),
    ViewSpec(
        view_id="three_quarter_front_right",
        description="Hero 3/4 view from upper-right-front.",
        azimuth_deg=315.0,
        elevation_deg=20.0,
        distance_factor=1.7,
        role="three_quarter",
    ),
    ViewSpec(
        view_id="three_quarter_front_left",
        description="Hero 3/4 view from upper-left-front.",
        azimuth_deg=225.0,
        elevation_deg=20.0,
        distance_factor=1.7,
        role="three_quarter",
    ),
    ViewSpec(
        view_id="three_quarter_back_right",
        description="Hero 3/4 view from upper-right-back.",
        azimuth_deg=45.0,
        elevation_deg=20.0,
        distance_factor=1.7,
        role="three_quarter",
    ),
)


AUXILIARY_PASSES: tuple[str, ...] = (
    "rgb",
    "normal",
    "depth",
    "material_id",
    "part_id",
    "silhouette",
)


def view_camera_position(view: ViewSpec, centroid: tuple[float, float, float], diagonal: float) -> tuple[float, float, float]:
    """Return world-space camera position for the view."""
    az = math.radians(view.azimuth_deg)
    el = math.radians(view.elevation_deg)
    distance = max(1.0, view.distance_factor * diagonal)
    x = centroid[0] + math.cos(el) * math.cos(az) * distance
    y = centroid[1] + math.cos(el) * math.sin(az) * distance
    z = centroid[2] + math.sin(el) * distance
    return (x, y, z)


def projected_pixel_width(
    feature_world_width_m: float,
    screen_height_px: int,
    camera_distance_m: float,
    vertical_fov_deg: float,
) -> float:
    """Approximate projected pixel width of a world-space feature.

    Per research §13: ``pixels ≈ feature_world_width × screen_height_px
    / (2 × camera_distance × tan(vertical_fov / 2))``.
    """
    if camera_distance_m <= 0:
        return 0.0
    tan_half = math.tan(math.radians(vertical_fov_deg) / 2.0)
    if tan_half <= 0:
        return 0.0
    return feature_world_width_m * screen_height_px / (2.0 * camera_distance_m * tan_half)


def auto_representation_for_feature(
    feature_world_width_cm: float,
    camera_distance_m: float = 2.0,
    screen_height_px: int = 1080,
    vertical_fov_deg: float = 60.0,
    is_silhouette_feature: bool = False,
) -> str:
    """Decide geometry vs normal-stamp vs texture vs removed for a feature.

    Per research §16:

      - < 1px: texture/normal/roughness only
      - 1–2px: depends on silhouette + material gloss + hero distance
      - > 2px: geometry if visible/exposed
      - silhouette feature: geometry even if small (when it affects outline)
      - flat internal detail: normal/height/roughness unless hero-close
    """
    px = projected_pixel_width(
        feature_world_width_cm / 100.0,
        screen_height_px,
        camera_distance_m,
        vertical_fov_deg,
    )
    if px < 0.5 and not is_silhouette_feature:
        return "removed"
    if px < 1.0:
        return "texture_only"
    if px < 2.0:
        return "geometry" if is_silhouette_feature else "normal_stamp"
    return "geometry"


__all__ = [
    "ViewSpec",
    "CANONICAL_VIEWS",
    "AUXILIARY_PASSES",
    "view_camera_position",
    "projected_pixel_width",
    "auto_representation_for_feature",
]
