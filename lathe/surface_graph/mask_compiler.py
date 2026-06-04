"""Surface mask compiler — wear_zone → shared masks (Wave 6 + Wave 9 seed).

Per ``docs/research/newresearch.md`` §11+§12, surface detail is the
multiplicative product of:

    geometry signal × material rule × directional bias × noise

The mask compiler takes a ``WearMaskRecipe`` (condition scalar +
environment + material context) and produces named masks the PBR
composer can blend together. Same masks drive base color, roughness,
metallic, normal, height — that's how PBR channels stay correlated.

Stub-first: the actual texture-rate computation requires baked support
maps (AO, curvature, world-space normal). This module defines the
recipe contract + names the canonical masks the surface stage will
fill in.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

CONTRACT_VERSION = "lathe.surface.mask_compiler_v1"

# Canonical mask names. Generators / surface graphs reference these.
CANONICAL_MASK_NAMES: tuple[str, ...] = (
    "edge_wear_mask",
    "concave_dirt_mask",
    "fastener_rust_mask",
    "vertical_streak_mask",
    "paint_chip_mask",
    "decal_fade_mask",
    "scratch_mask",
    "convex_polish_mask",
    "oil_stain_mask",
)


@dataclass(frozen=True)
class WearMaskRecipe:
    """Declarative wear/dirt/rust recipe for one material zone.

    ``condition`` is a continuous 0..1 knob (0 = factory new,
    1 = derelict). The compiler fans it into a correlated parameter
    vector — see ``condition_to_params`` for the mapping table.
    """

    target_zone_id: str
    condition: float = 0.3
    environment: str = "neutral"  # humid_industrial, arid, wet, indoor, outdoor
    mask_weights: Mapping[str, float] = field(default_factory=dict)
    style_hint: str = ""


@dataclass(frozen=True)
class MaskGraph:
    """Compiled mask graph for one zone — drives PBR channel composition."""

    target_zone_id: str
    masks: Mapping[str, float]  # mask_name → blend weight
    condition: float
    environment: str


def condition_to_params(condition: float) -> dict[str, float]:
    """Fan one condition scalar into a correlated parameter vector.

    The mapping is monotone but each parameter has its own curve so
    "freshly stamped → 20 years old, rusty, scratched" produces
    correlated wear features rather than independent slider drift.
    """
    c = max(0.0, min(1.0, condition))
    return {
        "paint_chipping_amount": c ** 1.3,
        "paint_chipping_scale": 0.3 + c * 0.7,
        "exposed_metal_fraction": c ** 1.5,
        "rust_probability": max(0.0, c - 0.4) * 1.5,
        "rust_depth": max(0.0, c - 0.5) * 1.2,
        "dust_accumulation": c * 0.8,
        "scratch_density": c * 0.6,
        "roughness_variance": 0.05 + c * 0.4,
        "decal_fade": c ** 1.2,
        "color_desaturation": c * 0.5,
        "edge_darkening": c * 0.4,
        "fastener_staining": max(0.0, c - 0.3) * 0.9,
        "dirt_vertical_streaking": c ** 1.4 * 0.8,
    }


def compile_mask_graph(recipe: WearMaskRecipe) -> MaskGraph:
    """Compile a WearMaskRecipe into a named-mask blend graph."""
    params = condition_to_params(recipe.condition)
    masks: dict[str, float] = {}
    # Base weights from condition + recipe overrides.
    masks["edge_wear_mask"] = (
        params["exposed_metal_fraction"] * 0.8 + recipe.mask_weights.get("convex_edge_wear", 0.0)
    )
    masks["concave_dirt_mask"] = (
        params["dust_accumulation"] * 0.7 + recipe.mask_weights.get("concave_dirt", 0.0)
    )
    masks["fastener_rust_mask"] = (
        params["rust_probability"] * 0.9 + recipe.mask_weights.get("fastener_rust", 0.0)
    )
    masks["vertical_streak_mask"] = (
        params["dirt_vertical_streaking"] * 0.6 + recipe.mask_weights.get("vertical_streaking", 0.0)
    )
    masks["paint_chip_mask"] = (
        params["paint_chipping_amount"] * 0.85 + recipe.mask_weights.get("paint_chipping", 0.0)
    )
    masks["decal_fade_mask"] = (
        params["decal_fade"] * 0.7 + recipe.mask_weights.get("decal_fade", 0.0)
    )
    masks["scratch_mask"] = (
        params["scratch_density"] * 0.5 + recipe.mask_weights.get("scratches", 0.0)
    )
    masks["convex_polish_mask"] = max(0.0, 1.0 - recipe.condition) * 0.4
    masks["oil_stain_mask"] = recipe.mask_weights.get("oil_stain", 0.0)
    # Environment modulation.
    env = recipe.environment.lower()
    if env in ("humid_industrial", "wet"):
        masks["fastener_rust_mask"] *= 1.4
        masks["concave_dirt_mask"] *= 1.2
    if env in ("arid", "desert"):
        masks["fastener_rust_mask"] *= 0.4
        masks["scratch_mask"] *= 1.2
    # Clamp.
    masks = {k: max(0.0, min(1.0, v)) for k, v in masks.items()}
    return MaskGraph(
        target_zone_id=recipe.target_zone_id,
        masks=masks,
        condition=recipe.condition,
        environment=recipe.environment,
    )


__all__ = [
    "CONTRACT_VERSION",
    "CANONICAL_MASK_NAMES",
    "WearMaskRecipe",
    "MaskGraph",
    "condition_to_params",
    "compile_mask_graph",
]
