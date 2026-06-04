"""Unified tessellation policy.

Per northstar §10 Lane A future-tasks. A unified policy lets every
primitive (cylinder, sphere, torus, revolved profile, extruded profile)
pick its segment count from a shared rule rather than each kernel
hard-coding defaults.

Two profiles are pre-defined:
  - ``low_poly_fantasy`` — small segment counts, flat normals, suits
    Band A faceted style.
  - ``hard_surface_game`` — balanced segment counts, smooth normals
    where appropriate, suits Band D PBR.

Custom profiles can be authored at runtime.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field

TESSELLATION_POLICY_VERSION = "lathe.asset_foundry.tessellation_policy_v1"


@dataclass(frozen=True)
class TessellationProfile:
    """Per-primitive segment count rules."""

    profile_id: str
    cylinder_min_segments: int = 6
    cylinder_segments_per_cm_radius: float = 0.6
    sphere_lat_segments: int = 8
    sphere_lon_segments: int = 12
    torus_major_segments: int = 12
    torus_minor_segments: int = 6
    revolved_min_segments: int = 8
    revolved_segments_per_cm_radius: float = 0.4
    extruded_height_segments_per_cm: float = 0.0
    """0 = single segment along extrude direction. Increase for
    twisted/scaling extrudes that need cross-sections."""

    bevel_min_segments: int = 1
    bevel_max_segments: int = 3
    bevel_silhouette_bonus: int = 1
    """Edges marked ``exposure=silhouette`` get this many extra
    segments."""

    sliver_aspect_threshold: float = 0.15
    """Reject tessellation cells whose aspect ratio is below this
    threshold (newresearch.md §6 sliver rejection)."""


@dataclass(frozen=True)
class TessellationPolicy:
    """A policy collects multiple profiles + a default."""

    default_profile_id: str
    profiles: Mapping[str, TessellationProfile]


_LOW_POLY_FANTASY = TessellationProfile(
    profile_id="low_poly_fantasy",
    cylinder_min_segments=6,
    cylinder_segments_per_cm_radius=0.4,
    sphere_lat_segments=6,
    sphere_lon_segments=8,
    torus_major_segments=10,
    torus_minor_segments=4,
    revolved_min_segments=6,
    revolved_segments_per_cm_radius=0.3,
    extruded_height_segments_per_cm=0.0,
    bevel_min_segments=1,
    bevel_max_segments=1,
    bevel_silhouette_bonus=0,
)

_HARD_SURFACE_GAME = TessellationProfile(
    profile_id="hard_surface_game",
    cylinder_min_segments=12,
    cylinder_segments_per_cm_radius=0.8,
    sphere_lat_segments=12,
    sphere_lon_segments=18,
    torus_major_segments=18,
    torus_minor_segments=10,
    revolved_min_segments=12,
    revolved_segments_per_cm_radius=0.6,
    extruded_height_segments_per_cm=0.5,
    bevel_min_segments=2,
    bevel_max_segments=3,
    bevel_silhouette_bonus=1,
)

_HERO_HIGH_POLY = TessellationProfile(
    profile_id="hero_high_poly",
    cylinder_min_segments=24,
    cylinder_segments_per_cm_radius=1.5,
    sphere_lat_segments=24,
    sphere_lon_segments=36,
    torus_major_segments=32,
    torus_minor_segments=18,
    revolved_min_segments=24,
    revolved_segments_per_cm_radius=1.2,
    extruded_height_segments_per_cm=1.0,
    bevel_min_segments=3,
    bevel_max_segments=6,
    bevel_silhouette_bonus=2,
)

DEFAULT_POLICY = TessellationPolicy(
    default_profile_id="hard_surface_game",
    profiles={
        "low_poly_fantasy": _LOW_POLY_FANTASY,
        "hard_surface_game": _HARD_SURFACE_GAME,
        "hero_high_poly": _HERO_HIGH_POLY,
    },
)


def apply_tessellation_policy(
    policy: TessellationPolicy,
    *,
    profile_id: str | None = None,
    primitive: str = "cylinder",
    radius_cm: float | None = None,
) -> int:
    """Resolve the segment count for one primitive under a policy."""
    pid = profile_id or policy.default_profile_id
    if pid not in policy.profiles:
        raise ValueError(f"unknown tessellation profile: {pid!r}")
    profile = policy.profiles[pid]
    if primitive == "cylinder":
        base = profile.cylinder_min_segments
        if radius_cm and radius_cm > 0:
            return max(base, int(math.ceil(base + radius_cm * profile.cylinder_segments_per_cm_radius)))
        return base
    if primitive == "sphere":
        return max(profile.sphere_lat_segments, profile.sphere_lon_segments)
    if primitive == "torus":
        return profile.torus_major_segments * profile.torus_minor_segments
    if primitive == "revolved":
        base = profile.revolved_min_segments
        if radius_cm and radius_cm > 0:
            return max(base, int(math.ceil(base + radius_cm * profile.revolved_segments_per_cm_radius)))
        return base
    if primitive == "extruded":
        if radius_cm and radius_cm > 0:
            return max(1, int(math.ceil(radius_cm * profile.extruded_height_segments_per_cm)))
        return 1
    raise ValueError(f"unknown primitive: {primitive!r}")


__all__ = [
    "TESSELLATION_POLICY_VERSION",
    "DEFAULT_POLICY",
    "TessellationPolicy",
    "TessellationProfile",
    "apply_tessellation_policy",
]
