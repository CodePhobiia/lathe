"""Leaf-card scattering for vegetation species.

Lays leaf-card primitives on branch-tip anchors using a Poisson-disk-ish
spacing rule (deterministic, seeded). Leaf cards are 2D quads with a
silhouette texture/material slot, lowered to stable ShapeIR
``extruded_profile`` records (a flat polygon with negligible extrude
height so downstream surface bake regions stay valid).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass
class LeafCard:
    """A single leaf-card placement."""

    center: tuple[float, float, float]
    width_cm: float
    height_cm: float
    normal_axis: str  # 'x'|'y'|'z'
    yaw_rad: float
    pitch_rad: float
    depth: int
    color_index: int  # index into the species palette

    def to_dict(self) -> dict:
        return {
            "center": list(self.center),
            "width_cm": self.width_cm,
            "height_cm": self.height_cm,
            "normal_axis": self.normal_axis,
            "yaw_rad": self.yaw_rad,
            "pitch_rad": self.pitch_rad,
            "depth": self.depth,
            "color_index": self.color_index,
        }


def _poisson_filter(
    points: list[tuple[tuple[float, float, float], int]],
    *,
    min_spacing_cm: float,
) -> list[tuple[tuple[float, float, float], int]]:
    """Greedy Poisson-disk filter.

    For each candidate point, accept iff no already-accepted point is
    within ``min_spacing_cm``. Deterministic for ordered input.
    """
    accepted: list[tuple[tuple[float, float, float], int]] = []
    sq = min_spacing_cm * min_spacing_cm
    for p, depth in points:
        ok = True
        for q, _ in accepted:
            dx = p[0] - q[0]
            dy = p[1] - q[1]
            dz = p[2] - q[2]
            if dx * dx + dy * dy + dz * dz < sq:
                ok = False
                break
        if ok:
            accepted.append((p, depth))
    return accepted


def scatter_leaf_cards(
    anchors: list[tuple[tuple[float, float, float], int]],
    *,
    leaf_size_cm: float = 12.0,
    leaf_aspect: float = 1.4,
    leaves_per_anchor: int = 3,
    min_spacing_cm: float = 4.0,
    palette_size: int = 4,
    seed: int = 4321,
) -> list[LeafCard]:
    """Scatter leaf cards around branch-tip anchors.

    Each anchor produces ``leaves_per_anchor`` cards arranged in a
    spherical fan around the tip; the whole set is then Poisson-filtered
    so leaves don't pile up. Returns deterministic per-seed output.
    """
    if not anchors:
        return []
    rng = random.Random(seed)
    candidates: list[tuple[tuple[float, float, float], int]] = []
    raw: list[LeafCard] = []
    for anchor, depth in anchors:
        for k in range(leaves_per_anchor):
            yaw = (k / max(1, leaves_per_anchor)) * 2.0 * math.pi + rng.uniform(-0.4, 0.4)
            pitch = rng.uniform(-0.6, 0.6)
            radial_offset = leaf_size_cm * 0.4
            cx = anchor[0] + math.cos(yaw) * radial_offset
            cy = anchor[1] + math.sin(pitch) * radial_offset * 0.5
            cz = anchor[2] + math.sin(yaw) * radial_offset
            color_index = rng.randint(0, max(0, palette_size - 1))
            candidates.append(((cx, cy, cz), depth))
            raw.append(
                LeafCard(
                    center=(cx, cy, cz),
                    width_cm=leaf_size_cm,
                    height_cm=leaf_size_cm * leaf_aspect,
                    normal_axis="z",
                    yaw_rad=yaw,
                    pitch_rad=pitch,
                    depth=depth,
                    color_index=color_index,
                )
            )
    # Apply Poisson filter on the candidate centers and keep matching cards.
    kept_centers = {tuple(p): True for p, _ in _poisson_filter(candidates, min_spacing_cm=min_spacing_cm)}
    return [card for card in raw if tuple(card.center) in kept_centers]


def lower_to_extruded_profiles(
    cards: list[LeafCard],
    *,
    extrude_height_cm: float = 0.05,
) -> list[dict]:
    """Lower leaf cards into stable ShapeIR ``extruded_profile`` records.

    Each card becomes a thin extruded quad in the plane perpendicular to
    its normal axis. Extrude height stays small (0.05cm by default) so
    the leaf reads as a card, not a slab — but the geometry is still a
    proper closed solid for downstream packaging.
    """
    primitives: list[dict] = []
    for idx, card in enumerate(cards):
        half_w = card.width_cm * 0.5
        half_h = card.height_cm * 0.5
        # Quad polygon in (u, v) cross-section coords, CCW.
        polygon = [
            (-half_w, -half_h),
            (half_w, -half_h),
            (half_w, half_h),
            (-half_w, half_h),
        ]
        primitives.append(
            {
                "primitive_type": "extruded_profile",
                "part": f"leaf_card_{idx}_d{card.depth}",
                "center": list(card.center),
                "axis": card.normal_axis,
                "tags": [
                    "vegetation",
                    "leaf_card",
                    f"depth_{card.depth}",
                    f"color_{card.color_index}",
                ],
                "blend_mode": "union",
                "profile_polygon": polygon,
                "extrude_height": extrude_height_cm,
                "rounding": 0.0,
                "vegetation_leaf_card": {
                    "yaw_rad": card.yaw_rad,
                    "pitch_rad": card.pitch_rad,
                    "color_index": card.color_index,
                },
                "wind_band": 2,
            }
        )
    return primitives
