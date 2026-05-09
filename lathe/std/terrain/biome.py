"""Biome layering — at-altitude / at-slope / at-flow zones.

Tags each heightfield cell with a biome ID derived from elevation,
slope, and (optional) hydraulic flow accumulation. The output is
twofold:

    - ``zone_ids`` — integer per-cell biome identifier (0..n_biomes-1).
    - ``zone_mask`` — float per-biome boolean (or soft, if blended)
      mask, suitable as input to the surface_graph material zone
      compositor.

The default biome table is the canonical World-Machine-style stack
used by the §A.4 reference:

    | id | name   | rule                                              |
    |----|--------|---------------------------------------------------|
    | 0  | snow   | high altitude AND low slope                       |
    | 1  | rock   | high slope (anywhere)                             |
    | 2  | forest | mid altitude AND low slope                        |
    | 3  | grass  | low-mid altitude AND low slope                    |
    | 4  | sand   | low altitude AND low slope (riverbeds + beaches)  |

Callers can supply their own table via the ``biomes`` argument.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .heightfield import Heightfield


@dataclass(frozen=True)
class BiomeRule:
    """A single biome's selection rule.

    All rules use *normalised* altitude (in ``[0, 1]`` over the
    heightfield's min..max), slope mask (in ``[0, 1]``), and flow mask
    (in ``[0, 1]``).
    """

    name: str
    altitude_min: float = 0.0
    altitude_max: float = 1.0
    slope_min: float = 0.0
    slope_max: float = 1.0
    flow_min: float = 0.0
    flow_max: float = 1.0


DEFAULT_BIOMES: tuple[BiomeRule, ...] = (
    BiomeRule("snow", altitude_min=0.78, slope_max=0.45),
    BiomeRule("rock", slope_min=0.40),
    BiomeRule("forest", altitude_min=0.40, altitude_max=0.78, slope_max=0.45),
    BiomeRule("grass", altitude_min=0.20, altitude_max=0.40, slope_max=0.45),
    BiomeRule("sand", altitude_max=0.20, slope_max=0.45),
)


def layer_biomes(
    heightfield: Heightfield,
    *,
    biomes: tuple[BiomeRule, ...] | None = None,
    flow_mask: np.ndarray | None = None,
) -> dict[str, np.ndarray]:
    """Tag each cell with a biome ID and emit per-biome zone masks.

    Returns ``{"zone_ids": (ny, nx) int64, "<biome>_zone": (ny, nx)
    float64, ...}`` and side-channels each per-biome zone mask back into
    ``heightfield.masks`` so the surface_graph layer_stack can address
    them by name.
    """
    rules = biomes or DEFAULT_BIOMES
    if not rules:
        raise ValueError("layer_biomes requires at least one BiomeRule")

    z = heightfield.heights * heightfield.vertical_scale
    z_min = float(np.min(z))
    z_max = float(np.max(z))
    span = max(z_max - z_min, 1e-9)
    altitude_norm = (z - z_min) / span
    slope_norm = heightfield.slope_mask()
    if flow_mask is None:
        flow_norm = heightfield.get_mask("flow_mask")
        if flow_norm is None:
            flow_norm = np.zeros_like(z)
    else:
        flow_norm = flow_mask

    ny, nx = heightfield.heights.shape
    zone_ids = np.full((ny, nx), -1, dtype=np.int64)
    out: dict[str, np.ndarray] = {}
    for idx, rule in enumerate(rules):
        match = (
            (altitude_norm >= rule.altitude_min)
            & (altitude_norm <= rule.altitude_max)
            & (slope_norm >= rule.slope_min)
            & (slope_norm <= rule.slope_max)
            & (flow_norm >= rule.flow_min)
            & (flow_norm <= rule.flow_max)
        )
        # First-match wins: only assign IDs to cells that are still -1.
        unassigned = zone_ids == -1
        assign = match & unassigned
        zone_ids = np.where(assign, idx, zone_ids)
        zone_mask = assign.astype(np.float64)
        key = f"{rule.name}_zone"
        out[key] = zone_mask
        heightfield.set_mask(key, zone_mask)
    # Anything unassigned falls into the *last* biome (rest-of-world).
    fallback_idx = len(rules) - 1
    fallback_assign = zone_ids == -1
    if fallback_assign.any():
        zone_ids = np.where(fallback_assign, fallback_idx, zone_ids)
        last_name = rules[-1].name
        out[f"{last_name}_zone"] = out[f"{last_name}_zone"] + fallback_assign.astype(
            np.float64
        )
        heightfield.set_mask(f"{last_name}_zone", out[f"{last_name}_zone"])

    out["zone_ids"] = zone_ids
    heightfield.masks["biome_zone_ids"] = zone_ids.astype(np.float64)
    return out
