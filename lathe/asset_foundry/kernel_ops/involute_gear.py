"""Involute gear primitive.

Per northstar §10 Lane A future-tasks. Generates an analytic
involute-tooth profile for a spur gear, suitable for steampunk +
mechanical kits in the Foundry's Band-D PBR hard-surface lane.

The profile is a 2D polyline; pair it with an extrude operator (or
swept_profile) to produce a 3D gear blank.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

INVOLUTE_GEAR_VERSION = "lathe.asset_foundry.involute_gear_v1"


@dataclass(frozen=True)
class InvoluteGearParameters:
    """Parameters for a metric involute spur gear."""

    teeth_count: int = 20
    module_cm: float = 0.2
    """Standard gear module — pitch_diameter = teeth_count * module."""

    pressure_angle_deg: float = 20.0
    addendum_factor: float = 1.0
    """Tooth height above pitch circle, multiplied by module."""

    dedendum_factor: float = 1.25
    """Root depth below pitch circle, multiplied by module."""

    bore_radius_cm: float | None = None
    """When set, an inner bore polygon is included. None = solid."""

    samples_per_flank: int = 8


@dataclass(frozen=True)
class InvoluteGearProfile:
    """The 2D outline of an involute gear blank."""

    parameters: InvoluteGearParameters
    outer_polyline_cm: tuple[tuple[float, float], ...]
    """Outer tooth profile, CCW from outside."""

    bore_polyline_cm: tuple[tuple[float, float], ...] | None
    """Inner bore, CW from inside (so polygon area is negative when
    consumed by a 2D triangulator)."""

    pitch_diameter_cm: float
    addendum_radius_cm: float
    dedendum_radius_cm: float


def _involute(base_radius: float, t: float) -> tuple[float, float]:
    """Single involute point parametrized by roll angle ``t``."""
    return (
        base_radius * (math.cos(t) + t * math.sin(t)),
        base_radius * (math.sin(t) - t * math.cos(t)),
    )


def build_involute_gear_profile(
    params: InvoluteGearParameters,
) -> InvoluteGearProfile:
    """Build a 2D involute-gear outline."""
    if params.teeth_count < 4:
        raise ValueError("teeth_count must be >= 4")
    if params.module_cm <= 0:
        raise ValueError("module_cm must be > 0")
    if params.samples_per_flank < 2:
        raise ValueError("samples_per_flank must be >= 2")

    pitch_radius = params.teeth_count * params.module_cm / 2.0
    addendum_radius = pitch_radius + params.addendum_factor * params.module_cm
    dedendum_radius = pitch_radius - params.dedendum_factor * params.module_cm
    pressure_angle_rad = math.radians(params.pressure_angle_deg)
    base_radius = pitch_radius * math.cos(pressure_angle_rad)
    tooth_spacing = 2.0 * math.pi / params.teeth_count

    # Roll angle for the involute to reach the addendum.
    if addendum_radius >= base_radius:
        max_t = math.sqrt(max(0.0, (addendum_radius / base_radius) ** 2 - 1.0))
    else:
        max_t = 0.0

    # Tooth thickness on pitch circle (half-angular width).
    inv_pa = math.tan(pressure_angle_rad) - pressure_angle_rad
    half_thickness_at_pitch = (math.pi / 2.0 / params.teeth_count) - inv_pa

    points: list[tuple[float, float]] = []
    for tooth_idx in range(params.teeth_count):
        center_angle = tooth_idx * tooth_spacing
        # Left flank — involute from base to addendum, rotated so the
        # tip lands at center_angle + half_thickness_at_pitch.
        flank_left: list[tuple[float, float]] = []
        for s in range(params.samples_per_flank + 1):
            t = max_t * s / params.samples_per_flank
            xi, yi = _involute(base_radius, t)
            # Rotate so this flank's tip is at the correct position.
            rotate = center_angle - half_thickness_at_pitch
            ca, sa = math.cos(rotate), math.sin(rotate)
            flank_left.append((xi * ca - yi * sa, xi * sa + yi * ca))
        # Right flank — mirrored across the tooth midline.
        flank_right: list[tuple[float, float]] = []
        for s in range(params.samples_per_flank + 1):
            t = max_t * s / params.samples_per_flank
            xi, yi = _involute(base_radius, -t)
            rotate = center_angle + half_thickness_at_pitch
            ca, sa = math.cos(rotate), math.sin(rotate)
            flank_right.append((xi * ca - yi * sa, xi * sa + yi * ca))
        # Tooth tip arc — short arc on the addendum circle.
        tip_angle_a = math.atan2(flank_left[-1][1], flank_left[-1][0])
        tip_angle_b = math.atan2(flank_right[-1][1], flank_right[-1][0])
        if tip_angle_b < tip_angle_a:
            tip_angle_b += 2.0 * math.pi
        tip_samples = max(1, params.samples_per_flank // 2)
        tip_arc: list[tuple[float, float]] = []
        for s in range(tip_samples + 1):
            theta = tip_angle_a + (tip_angle_b - tip_angle_a) * s / tip_samples
            tip_arc.append(
                (
                    addendum_radius * math.cos(theta),
                    addendum_radius * math.sin(theta),
                )
            )
        # Tooth root arc — between this tooth's right flank and the
        # next tooth's left flank.
        next_left_root_angle = center_angle + tooth_spacing - half_thickness_at_pitch
        root_arc_samples = max(1, params.samples_per_flank // 2)
        root_arc: list[tuple[float, float]] = []
        for s in range(1, root_arc_samples):
            theta = (
                math.atan2(flank_right[0][1], flank_right[0][0])
                + (next_left_root_angle - math.atan2(flank_right[0][1], flank_right[0][0]))
                * s
                / root_arc_samples
            )
            root_arc.append(
                (
                    dedendum_radius * math.cos(theta),
                    dedendum_radius * math.sin(theta),
                )
            )
        points.extend(flank_left)
        points.extend(tip_arc)
        points.extend(reversed(flank_right))
        points.extend(root_arc)

    bore: tuple[tuple[float, float], ...] | None = None
    if params.bore_radius_cm and params.bore_radius_cm > 0:
        bore_samples = max(8, params.samples_per_flank * 2)
        bore_pts = []
        for i in range(bore_samples):
            theta = 2.0 * math.pi * i / bore_samples
            bore_pts.append(
                (
                    params.bore_radius_cm * math.cos(-theta),
                    params.bore_radius_cm * math.sin(-theta),
                )
            )
        bore = tuple(bore_pts)

    return InvoluteGearProfile(
        parameters=params,
        outer_polyline_cm=tuple(points),
        bore_polyline_cm=bore,
        pitch_diameter_cm=pitch_radius * 2.0,
        addendum_radius_cm=addendum_radius,
        dedendum_radius_cm=dedendum_radius,
    )


__all__ = [
    "INVOLUTE_GEAR_VERSION",
    "InvoluteGearParameters",
    "InvoluteGearProfile",
    "build_involute_gear_profile",
]
