"""Standardized lighting rigs for procedural-asset evaluation.

Four fixed setups (per research §13):

  1. Neutral studio — gray bg, soft area light, no dramatic contrast.
  2. Three-point product — key + fill + rim. Tests silhouette + specular.
  3. Outdoor gameplay — sun + sky. Engine/world plausibility.
  4. Low-key rim — dark fill, strong rim. Silhouette + edge readability.

All rigs use the SAME exposure/tonemapping/FOV so changes in output
trace only to changes in the asset, not the rig.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LightSource:
    """One directional + ambient light source for a render rig."""

    name: str
    kind: str  # directional | area | point | hdri | sky
    direction: tuple[float, float, float] = (0.0, 0.0, -1.0)
    color_rgb: tuple[float, float, float] = (1.0, 1.0, 1.0)
    intensity: float = 1.0


@dataclass(frozen=True)
class LightRig:
    """A complete lighting setup.

    Used as a key into the renderer — the renderer's job is to honor
    the rig deterministically so a build's renders are stable across
    sessions.
    """

    rig_id: str
    description: str
    background_rgb: tuple[float, float, float] = (0.5, 0.5, 0.5)
    ambient_intensity: float = 0.3
    lights: tuple[LightSource, ...] = ()
    exposure_ev: float = 0.0
    tonemapping: str = "linear"


LIGHTING_RIGS: dict[str, LightRig] = {
    "neutral_studio": LightRig(
        rig_id="neutral_studio",
        description="Soft gray background + HDRI-like area light. Tests material honesty.",
        background_rgb=(0.5, 0.5, 0.5),
        ambient_intensity=0.4,
        lights=(
            LightSource(
                name="key",
                kind="area",
                direction=(0.0, -0.5, -1.0),
                color_rgb=(1.0, 1.0, 0.98),
                intensity=2.5,
            ),
            LightSource(
                name="fill",
                kind="area",
                direction=(0.5, 0.5, -0.3),
                color_rgb=(0.85, 0.9, 1.0),
                intensity=1.0,
            ),
        ),
        exposure_ev=0.0,
        tonemapping="linear",
    ),
    "three_point_product": LightRig(
        rig_id="three_point_product",
        description="Key+fill+rim. Tests silhouette readability, bevel highlights, specular.",
        background_rgb=(0.92, 0.92, 0.94),
        ambient_intensity=0.2,
        lights=(
            LightSource(
                name="key",
                kind="directional",
                direction=(-0.6, -0.4, -0.7),
                color_rgb=(1.0, 0.98, 0.95),
                intensity=3.5,
            ),
            LightSource(
                name="fill",
                kind="directional",
                direction=(0.7, -0.3, -0.4),
                color_rgb=(0.6, 0.7, 1.0),
                intensity=1.5,
            ),
            LightSource(
                name="rim",
                kind="directional",
                direction=(0.2, 0.6, -0.3),
                color_rgb=(1.0, 0.9, 0.8),
                intensity=2.0,
            ),
        ),
        exposure_ev=0.0,
        tonemapping="aces",
    ),
    "outdoor_gameplay": LightRig(
        rig_id="outdoor_gameplay",
        description="Sun+sky. Tests engine/world lighting plausibility.",
        background_rgb=(0.65, 0.78, 0.92),
        ambient_intensity=0.45,
        lights=(
            LightSource(
                name="sun",
                kind="directional",
                direction=(-0.4, -0.8, -0.4),
                color_rgb=(1.0, 0.95, 0.85),
                intensity=4.0,
            ),
            LightSource(
                name="sky",
                kind="hdri",
                color_rgb=(0.5, 0.65, 0.85),
                intensity=1.2,
            ),
        ),
        exposure_ev=0.0,
        tonemapping="aces",
    ),
    "low_key_rim": LightRig(
        rig_id="low_key_rim",
        description="Dark fill, strong rim. Tests silhouette + edge readability.",
        background_rgb=(0.08, 0.08, 0.1),
        ambient_intensity=0.1,
        lights=(
            LightSource(
                name="rim",
                kind="directional",
                direction=(0.5, 0.5, -0.3),
                color_rgb=(1.0, 0.9, 0.7),
                intensity=4.5,
            ),
            LightSource(
                name="fill",
                kind="directional",
                direction=(-0.5, -0.2, -0.3),
                color_rgb=(0.3, 0.4, 0.6),
                intensity=0.4,
            ),
        ),
        exposure_ev=0.5,
        tonemapping="aces",
    ),
}


__all__ = ["LightRig", "LightSource", "LIGHTING_RIGS"]
