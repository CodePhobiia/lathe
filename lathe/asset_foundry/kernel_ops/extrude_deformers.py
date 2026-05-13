"""Twist + scale variants on extruded profiles.

Per northstar §10 Lane A future-tasks, extruded profiles should
support optional twist (rotation of the profile along the extrusion
axis) and optional scale (taper). This module declares the
parameter records; the real geometry build is performed by the
kernel program when it sees the parameters.
"""

from __future__ import annotations

from dataclasses import dataclass, field

EXTRUDE_DEFORMERS_VERSION = "lathe.asset_foundry.extrude_deformers_v1"


@dataclass(frozen=True)
class ExtrudeDeformer:
    """Base parameter container; never instantiated directly."""

    height_cm: float = 1.0
    """Extrusion height along the extrude axis."""

    segments: int = 1
    """Number of intermediate cross-sections sampled along the axis.
    Twist/taper require segments >= 2 for visible effect."""


@dataclass(frozen=True)
class TwistedExtrude(ExtrudeDeformer):
    """Rotates the profile through ``twist_deg`` over the extrude."""

    twist_deg: float = 90.0
    """Total rotation in degrees applied across the full height."""

    twist_pivot_xy_cm: tuple[float, float] = (0.0, 0.0)
    """Optional pivot in profile plane."""


@dataclass(frozen=True)
class ScalingExtrude(ExtrudeDeformer):
    """Tapers the profile from ``scale_start`` to ``scale_end``."""

    scale_start: float = 1.0
    scale_end: float = 0.5
    pivot_xy_cm: tuple[float, float] = (0.0, 0.0)


__all__ = [
    "EXTRUDE_DEFORMERS_VERSION",
    "ExtrudeDeformer",
    "ScalingExtrude",
    "TwistedExtrude",
]
