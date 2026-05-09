"""Billboard imposter generator.

The LOD3 of a tree is a single quad with an 8-direction sprite atlas
baked from silhouette renders of the LOD0 mesh. This module produces
a *scaffold* of that imposter:

- one ``extruded_profile`` quad sized to the species' silhouette
  bounding box,
- an ``imposter_atlas`` record with placeholder uv rects for 8 yaw
  directions arranged in a 4x2 grid,
- a ``view_directions`` list (yaw angles in radians).

Lathe does not run a GPU silhouette renderer at compile time, so the
actual sprite rendering happens in the engine adapter (Unity tree
imposter system, Unreal foliage runtime, Roblox decal cache, etc).
The scaffold gives the adapter everything it needs except pixels.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class ImposterAtlas:
    """The 8-direction sprite atlas spec."""

    yaw_count: int = 8
    pitch_count: int = 1
    atlas_pixel_width: int = 1024
    atlas_pixel_height: int = 512
    cell_uv_rects: list[tuple[float, float, float, float]] = field(default_factory=list)
    view_directions_rad: list[float] = field(default_factory=list)
    rendered: bool = False
    render_status: str = "scaffold"

    def to_dict(self) -> dict:
        return {
            "yaw_count": self.yaw_count,
            "pitch_count": self.pitch_count,
            "atlas_pixel_width": self.atlas_pixel_width,
            "atlas_pixel_height": self.atlas_pixel_height,
            "cell_uv_rects": [list(r) for r in self.cell_uv_rects],
            "view_directions_rad": list(self.view_directions_rad),
            "rendered": self.rendered,
            "render_status": self.render_status,
        }


def _build_8_view_atlas(
    *, atlas_pixel_width: int = 1024, atlas_pixel_height: int = 512
) -> ImposterAtlas:
    """Build a 4x2 cell layout for 8 yaw directions."""
    cells_x = 4
    cells_y = 2
    rects: list[tuple[float, float, float, float]] = []
    yaws: list[float] = []
    for j in range(cells_y):
        for i in range(cells_x):
            u0 = i / cells_x
            v0 = j / cells_y
            u1 = (i + 1) / cells_x
            v1 = (j + 1) / cells_y
            rects.append((u0, v0, u1, v1))
            cell_index = j * cells_x + i
            yaws.append(2.0 * math.pi * cell_index / (cells_x * cells_y))
    return ImposterAtlas(
        yaw_count=8,
        pitch_count=1,
        atlas_pixel_width=atlas_pixel_width,
        atlas_pixel_height=atlas_pixel_height,
        cell_uv_rects=rects,
        view_directions_rad=yaws,
        rendered=False,
        render_status="scaffold",
    )


def generate_imposter(
    *,
    silhouette_extents_cm: tuple[float, float, float],
    center: tuple[float, float, float] = (0.0, 0.0, 0.0),
    atlas_pixel_width: int = 1024,
    atlas_pixel_height: int = 512,
) -> dict:
    """Build a billboard imposter scaffold for the given silhouette extents.

    Returns a dict with one ``extruded_profile`` primitive (the quad)
    and an ``imposter_atlas`` sub-record with the 8-direction atlas
    spec. The quad is centered at ``center``, sized to the silhouette
    width × height, faces +z by default, and is tagged so engine
    adapters recognize it as a tree imposter.
    """
    width, height, _ = silhouette_extents_cm
    half_w = width * 0.5
    half_h = height * 0.5
    polygon = [
        (-half_w, -half_h),
        (half_w, -half_h),
        (half_w, half_h),
        (-half_w, half_h),
    ]
    atlas = _build_8_view_atlas(
        atlas_pixel_width=atlas_pixel_width,
        atlas_pixel_height=atlas_pixel_height,
    )
    quad = {
        "primitive_type": "extruded_profile",
        "part": "imposter_quad",
        "center": list(center),
        "axis": "z",
        "tags": ["vegetation", "imposter", "lod3", "billboard"],
        "blend_mode": "union",
        "profile_polygon": polygon,
        "extrude_height": 0.05,
        "rounding": 0.0,
        "wind_band": 0,
        "vegetation_imposter_quad": {
            "atlas_uv_set": "imposter",
            "ref_pose_yaw_rad": 0.0,
        },
    }
    return {
        "primitives": [quad],
        "imposter_atlas": atlas.to_dict(),
        "schema": "lathe.vegetation_imposter.v1",
    }
