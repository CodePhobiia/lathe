"""Frond / palm-leaf generator.

A frond is a multi-segment ribbon — a long curved spine with a series
of paired leaflet cards arranged along it (palm leaves, fern fronds,
banana leaves). The spine is a ``swept_profile`` ribbon; the leaflets
are ``extruded_profile`` cards arranged on alternating sides.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class Frond:
    """A frond's spine + leaflet placements."""

    spine_path: list[tuple[float, float, float]] = field(default_factory=list)
    spine_width_cm: float = 4.0
    spine_thickness_cm: float = 0.4
    leaflets: list[dict] = field(default_factory=list)
    base_origin: tuple[float, float, float] = (0.0, 0.0, 0.0)
    base_axis: tuple[float, float, float] = (0.0, 1.0, 0.0)


def _normalize(v: tuple[float, float, float]) -> tuple[float, float, float]:
    n = math.sqrt(sum(c * c for c in v))
    if n < 1e-12:
        return (0.0, 1.0, 0.0)
    return (v[0] / n, v[1] / n, v[2] / n)


def generate_frond(
    *,
    origin: tuple[float, float, float] = (0.0, 0.0, 0.0),
    axis: tuple[float, float, float] = (0.0, 1.0, 0.0),
    length_cm: float = 200.0,
    droop_amount: float = 0.5,
    leaflet_count: int = 18,
    leaflet_length_cm: float = 28.0,
    leaflet_width_cm: float = 4.5,
    spine_width_cm: float = 4.0,
    spine_thickness_cm: float = 0.4,
    nodes_per_spine: int = 12,
) -> Frond:
    """Generate a frond.

    The spine starts at ``origin`` along ``axis`` and droops
    proportionally to ``droop_amount`` (0 = straight, 1 = strong arc).
    Leaflets are placed in pairs on alternating sides; their pitch
    rotates around the spine tangent.
    """
    axis = _normalize(axis)
    spine_path: list[tuple[float, float, float]] = []
    for i in range(nodes_per_spine):
        t = i / max(1, nodes_per_spine - 1)
        # Linear advance along axis.
        forward = (
            origin[0] + axis[0] * length_cm * t,
            origin[1] + axis[1] * length_cm * t,
            origin[2] + axis[2] * length_cm * t,
        )
        # Droop in -y proportional to t^2 (parabolic arc).
        droop = -length_cm * droop_amount * (t * t)
        spine_path.append((forward[0], forward[1] + droop, forward[2]))

    leaflets: list[dict] = []
    # Build a stable perpendicular for leaflet placement.
    perp_u = _normalize((axis[2], 0.0, -axis[0])) if abs(axis[1]) > 0.5 else (1.0, 0.0, 0.0)
    for k in range(leaflet_count):
        t = (k + 0.5) / max(1, leaflet_count)
        spine_idx = min(int(t * (len(spine_path) - 1)), len(spine_path) - 1)
        spine_pt = spine_path[spine_idx]
        side = 1 if k % 2 == 0 else -1
        # Leaflet attaches at spine point, extends along perp_u with
        # a pitch that flares outward.
        offset = (
            perp_u[0] * leaflet_length_cm * 0.5 * side,
            perp_u[1] * leaflet_length_cm * 0.5 * side,
            perp_u[2] * leaflet_length_cm * 0.5 * side,
        )
        center = (spine_pt[0] + offset[0], spine_pt[1] + offset[1], spine_pt[2] + offset[2])
        leaflets.append(
            {
                "center": list(center),
                "width_cm": leaflet_width_cm,
                "height_cm": leaflet_length_cm,
                "side": side,
                "spine_t": t,
                "yaw_rad": math.atan2(perp_u[2] * side, perp_u[0] * side),
            }
        )

    return Frond(
        spine_path=spine_path,
        spine_width_cm=spine_width_cm,
        spine_thickness_cm=spine_thickness_cm,
        leaflets=leaflets,
        base_origin=origin,
        base_axis=axis,
    )


def lower_to_primitives(frond: Frond) -> list[dict]:
    """Lower a frond into stable ShapeIR primitives.

    Spine → ``swept_profile`` ribbon. Leaflets → ``extruded_profile``
    cards with the same conventions as ``leaves.lower_to_extruded_profiles``.
    """
    primitives: list[dict] = []
    half_w = frond.spine_width_cm * 0.5
    half_t = frond.spine_thickness_cm * 0.5
    spine_cross = [
        (-half_w, -half_t),
        (half_w, -half_t),
        (half_w, half_t),
        (-half_w, half_t),
    ]
    primitives.append(
        {
            "primitive_type": "swept_profile",
            "part": "frond_spine",
            "center": list(frond.base_origin),
            "axis": "y",
            "tags": ["vegetation", "frond_spine"],
            "blend_mode": "union",
            "cross_section": spine_cross,
            "sweep_path": [tuple(p) for p in frond.spine_path],
            "rounding": 0.0,
            "wind_band": 1,
        }
    )
    for idx, leaflet in enumerate(frond.leaflets):
        half_lw = leaflet["width_cm"] * 0.5
        half_lh = leaflet["height_cm"] * 0.5
        polygon = [
            (-half_lw, -half_lh),
            (half_lw, -half_lh),
            (half_lw, half_lh),
            (-half_lw, half_lh),
        ]
        primitives.append(
            {
                "primitive_type": "extruded_profile",
                "part": f"frond_leaflet_{idx}",
                "center": list(leaflet["center"]),
                "axis": "z",
                "tags": ["vegetation", "frond_leaflet"],
                "blend_mode": "union",
                "profile_polygon": polygon,
                "extrude_height": 0.05,
                "rounding": 0.0,
                "vegetation_leaf_card": {
                    "yaw_rad": leaflet["yaw_rad"],
                    "pitch_rad": 0.0,
                    "color_index": 0,
                },
                "wind_band": 2,
            }
        )
    return primitives
