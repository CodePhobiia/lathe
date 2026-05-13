"""Shared-mask PBR channel composer (Wave 6 + Wave 9 seed).

The research's core PBR principle (§12): do NOT generate base color,
roughness, metallic, and normal independently. Use shared masks (paint,
metal_exposure, rust, edge_wear, dirt, scratches, decal, oil_stain),
and derive each channel from the SAME masks. That correlation is what
makes painted_steel actually look like painted_steel rather than a
gray shader.

This module composes PBR channel parameter vectors from a ``MaskGraph``
and a ``MaterialArchetype``. The output is parameter-rate (per zone),
not texture-rate (per pixel). Texture-rate baking is the next layer —
this module sets up the contract so the surface stage knows what
parameters to feed into its baker.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .mask_compiler import MaskGraph

CONTRACT_VERSION = "lathe.surface.pbr_composer_v1"


@dataclass(frozen=True)
class MaterialArchetype:
    """Material archetype = material_class × visual_language × condition.

    Carries the parameter-level recipe (base color, base roughness,
    base metallic, optional emissive, decal slot allowed, etc.) the
    PBR composer uses as the unweared baseline before mask-driven
    modulation kicks in.
    """

    archetype_id: str
    material_class: str
    base_color_rgb: tuple[int, int, int] = (132, 140, 124)  # painted steel sage
    base_roughness: float = 0.6
    base_metallic: float = 0.0
    emissive_rgb: tuple[int, int, int] = (0, 0, 0)
    raw_metal_color_rgb: tuple[int, int, int] = (140, 138, 130)
    rust_color_rgb: tuple[int, int, int] = (120, 60, 30)
    dirt_color_rgb: tuple[int, int, int] = (60, 50, 40)
    decal_allowed: bool = False


@dataclass(frozen=True)
class PBRChannelParams:
    """Resolved per-zone PBR channel parameters for one mask graph.

    The surface stage's baker consumes these to produce actual texture
    maps. Each channel value is the parameter the baker uses as the
    starting point; mask-driven texture modulation is applied at bake.
    """

    zone_id: str
    base_color_rgb: tuple[int, int, int]
    roughness: float
    metallic: float
    normal_strength: float
    height_displacement_cm: float
    ao_intensity: float
    emissive_rgb: tuple[int, int, int]
    decal_slot_active: bool


def _blend_rgb(
    a: tuple[int, int, int], b: tuple[int, int, int], t: float
) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return (
        int(round(a[0] * (1 - t) + b[0] * t)),
        int(round(a[1] * (1 - t) + b[1] * t)),
        int(round(a[2] * (1 - t) + b[2] * t)),
    )


def compose_pbr_channels(
    archetype: MaterialArchetype,
    mask_graph: MaskGraph,
) -> PBRChannelParams:
    """Compose PBR channel parameters from archetype + mask graph.

    The composition is intentionally correlated: rust raises roughness,
    drops metallic IF on a painted body, raises ao_intensity. Edge wear
    pulls toward raw metal color, drops roughness on convex edges
    (polish). Dirt darkens base color and raises roughness.
    """
    masks = mask_graph.masks
    edge_wear = masks.get("edge_wear_mask", 0.0)
    rust = masks.get("fastener_rust_mask", 0.0)
    dirt = masks.get("concave_dirt_mask", 0.0)
    scratches = masks.get("scratch_mask", 0.0)
    paint_chip = masks.get("paint_chip_mask", 0.0)
    polish = masks.get("convex_polish_mask", 0.0)

    # Base color: blend toward raw metal where edges are worn, toward
    # rust color in rust zones, darken with dirt.
    color = archetype.base_color_rgb
    color = _blend_rgb(color, archetype.raw_metal_color_rgb, paint_chip * 0.7 + edge_wear * 0.3)
    color = _blend_rgb(color, archetype.rust_color_rgb, rust * 0.6)
    color = _blend_rgb(color, archetype.dirt_color_rgb, dirt * 0.4)

    # Roughness: dirt + rust raise it, polish drops it.
    roughness = archetype.base_roughness
    roughness += dirt * 0.2
    roughness += rust * 0.25
    roughness += scratches * 0.1
    roughness -= polish * 0.15
    roughness = max(0.05, min(1.0, roughness))

    # Metallic: rust lowers metallic (oxide layer); edge wear can
    # reveal more metal on a painted-steel zone.
    if archetype.material_class.endswith("steel") or "metal" in archetype.material_class:
        metallic = archetype.base_metallic
        metallic += edge_wear * 0.4 * (1.0 - paint_chip)  # exposed metal
        metallic -= rust * 0.3
    else:
        metallic = archetype.base_metallic
    metallic = max(0.0, min(1.0, metallic))

    # Normal strength: scratches + rust pitting raise it.
    normal_strength = 0.5 + scratches * 0.4 + rust * 0.3

    # Height: paint chips remove a small amount; rust adds bloom.
    height = -paint_chip * 0.03 + rust * 0.04

    # AO: dirt accumulation in concavity zones.
    ao_intensity = 0.5 + dirt * 0.4

    return PBRChannelParams(
        zone_id=mask_graph.target_zone_id,
        base_color_rgb=color,
        roughness=roughness,
        metallic=metallic,
        normal_strength=max(0.0, min(2.0, normal_strength)),
        height_displacement_cm=height,
        ao_intensity=max(0.0, min(1.5, ao_intensity)),
        emissive_rgb=archetype.emissive_rgb,
        decal_slot_active=archetype.decal_allowed,
    )


# Built-in archetypes covering the canonical material × visual-language combos.
BUILTIN_ARCHETYPES: dict[str, MaterialArchetype] = {
    "painted_steel.utility_industrial": MaterialArchetype(
        archetype_id="painted_steel.utility_industrial",
        material_class="painted_steel",
        base_color_rgb=(132, 140, 124),  # sage
        base_roughness=0.58,
        base_metallic=0.0,
        raw_metal_color_rgb=(140, 138, 130),
        rust_color_rgb=(120, 60, 30),
        dirt_color_rgb=(60, 50, 40),
        decal_allowed=True,
    ),
    "painted_steel.sci_fi_clean": MaterialArchetype(
        archetype_id="painted_steel.sci_fi_clean",
        material_class="painted_steel",
        base_color_rgb=(180, 188, 200),
        base_roughness=0.35,
        base_metallic=0.0,
        raw_metal_color_rgb=(190, 195, 205),
        rust_color_rgb=(100, 80, 70),
        dirt_color_rgb=(80, 80, 90),
        decal_allowed=True,
    ),
    "raw_steel.abandoned_rusty": MaterialArchetype(
        archetype_id="raw_steel.abandoned_rusty",
        material_class="raw_steel",
        base_color_rgb=(120, 90, 70),
        base_roughness=0.7,
        base_metallic=0.5,
        raw_metal_color_rgb=(160, 155, 140),
        rust_color_rgb=(135, 65, 25),
        dirt_color_rgb=(70, 50, 35),
        decal_allowed=False,
    ),
    "brass_fittings.steampunk": MaterialArchetype(
        archetype_id="brass_fittings.steampunk",
        material_class="aged_brass",
        base_color_rgb=(165, 138, 92),
        base_roughness=0.5,
        base_metallic=0.9,
        raw_metal_color_rgb=(200, 165, 100),
        rust_color_rgb=(100, 80, 50),
        dirt_color_rgb=(80, 65, 40),
        decal_allowed=False,
    ),
    "oak_wood.fantasy": MaterialArchetype(
        archetype_id="oak_wood.fantasy",
        material_class="oak_wood",
        base_color_rgb=(110, 75, 45),
        base_roughness=0.75,
        base_metallic=0.0,
        raw_metal_color_rgb=(110, 75, 45),
        rust_color_rgb=(60, 40, 20),
        dirt_color_rgb=(50, 35, 25),
        decal_allowed=True,
    ),
    "rubber_grip.utility_industrial": MaterialArchetype(
        archetype_id="rubber_grip.utility_industrial",
        material_class="rubber",
        base_color_rgb=(40, 40, 42),
        base_roughness=0.9,
        base_metallic=0.0,
        raw_metal_color_rgb=(40, 40, 42),
        rust_color_rgb=(60, 50, 40),
        dirt_color_rgb=(30, 30, 32),
        decal_allowed=False,
    ),
    "decal_warning.utility_industrial": MaterialArchetype(
        archetype_id="decal_warning.utility_industrial",
        material_class="warning_decal",
        base_color_rgb=(220, 170, 40),
        base_roughness=0.4,
        base_metallic=0.0,
        emissive_rgb=(20, 16, 0),
        decal_allowed=True,
    ),
}


def resolve_archetype(
    material_class: str,
    visual_language_id: str = "utility_industrial_v1",
) -> MaterialArchetype:
    """Look up an archetype by (material_class, visual_language).

    Falls back to ``painted_steel.utility_industrial`` for unknown
    combinations so the synthesizer never lacks a material to apply.
    """
    # The visual_language_id format expected here is like "utility_industrial_v1"
    # — we extract the stem.
    vl_stem = visual_language_id.removesuffix("_v1") if visual_language_id else "utility_industrial"
    key = f"{material_class}.{vl_stem}"
    archetype = BUILTIN_ARCHETYPES.get(key)
    if archetype is not None:
        return archetype
    # Try with just material_class + utility_industrial fallback.
    fallback_key = f"{material_class}.utility_industrial"
    archetype = BUILTIN_ARCHETYPES.get(fallback_key)
    if archetype is not None:
        return archetype
    return BUILTIN_ARCHETYPES["painted_steel.utility_industrial"]


__all__ = [
    "CONTRACT_VERSION",
    "MaterialArchetype",
    "PBRChannelParams",
    "compose_pbr_channels",
    "BUILTIN_ARCHETYPES",
    "resolve_archetype",
]
