"""Seasonal palette + leaf-density modulation.

Each season provides:
- a leaf-color palette (RGB triplets, 0-255)
- a leaf-density multiplier (1.0 = full canopy; 0.0 = bare branches)
- a frost/dryness factor that downstream surface bakes can read as a
  desaturation/wear hint.

Engines or downstream surface bakes consume the palette via the
``color_index`` carried on each ``LeafCard``. This module is purely
parametric — it does not paint pixels. Painting happens in the surface
stage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Season:
    """A single season variant."""

    name: str
    leaf_palette: list[tuple[int, int, int]] = field(default_factory=list)
    leaf_density_multiplier: float = 1.0
    frost_factor: float = 0.0
    dryness_factor: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "leaf_palette": [list(c) for c in self.leaf_palette],
            "leaf_density_multiplier": self.leaf_density_multiplier,
            "frost_factor": self.frost_factor,
            "dryness_factor": self.dryness_factor,
        }


SEASONAL_PALETTES: dict[str, Season] = {
    "spring": Season(
        name="spring",
        leaf_palette=[
            (130, 200, 90),
            (170, 220, 110),
            (110, 180, 80),
            (190, 210, 95),
        ],
        leaf_density_multiplier=0.9,
        frost_factor=0.0,
        dryness_factor=0.0,
    ),
    "summer": Season(
        name="summer",
        leaf_palette=[
            (60, 140, 50),
            (90, 160, 70),
            (50, 120, 40),
            (110, 175, 80),
        ],
        leaf_density_multiplier=1.0,
        frost_factor=0.0,
        dryness_factor=0.05,
    ),
    "autumn": Season(
        name="autumn",
        leaf_palette=[
            (200, 130, 40),
            (180, 90, 30),
            (220, 160, 60),
            (160, 70, 30),
        ],
        leaf_density_multiplier=0.7,
        frost_factor=0.0,
        dryness_factor=0.4,
    ),
    "winter": Season(
        name="winter",
        leaf_palette=[
            (110, 100, 90),
            (130, 120, 110),
            (90, 90, 95),
        ],
        leaf_density_multiplier=0.15,
        frost_factor=0.6,
        dryness_factor=0.7,
    ),
}


def apply_season(
    leaf_primitives: list[dict],
    *,
    season: str = "summer",
) -> tuple[list[dict], Season]:
    """Filter and tag leaf primitives for a given season.

    Drops a deterministic fraction of leaves matching
    ``1 - leaf_density_multiplier``. Reassigns ``color_index`` modulo the
    season palette length and adds a ``season_name`` tag. Returns the
    filtered list plus the Season record so downstream surface bakes
    can read the palette directly.
    """
    season_record = SEASONAL_PALETTES.get(season, SEASONAL_PALETTES["summer"])
    keep_ratio = max(0.0, min(1.0, season_record.leaf_density_multiplier))
    palette_size = max(1, len(season_record.leaf_palette))
    out: list[dict] = []
    for idx, prim in enumerate(leaf_primitives):
        if "leaf_card" not in prim.get("tags", []):
            out.append(prim)
            continue
        # Deterministic stride filter so the same input always yields the
        # same kept set for a given season.
        if keep_ratio < 1.0:
            cutoff = round(1.0 / max(keep_ratio, 1e-3))
            if idx % cutoff != 0:
                continue
        tags = list(prim.get("tags", []))
        tags.append(f"season_{season_record.name}")
        veg = dict(prim.get("vegetation_leaf_card", {}) or {})
        veg["color_index"] = idx % palette_size
        new_prim = {**prim, "tags": tags, "vegetation_leaf_card": veg}
        out.append(new_prim)
    return out, season_record
