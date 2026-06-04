"""Helical sweep operator.

Per northstar §10 Lane A future-tasks. A helical sweep is a sweep
of a 2D profile along a helix; output is useful for screw threads,
spiral staircases, decorative twisted columns.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

HELICAL_SWEEP_VERSION = "lathe.asset_foundry.helical_sweep_v1"


@dataclass(frozen=True)
class HelicalSweep:
    """Parameter record for a helical sweep."""

    axis: str = "z"
    radius_cm: float = 5.0
    pitch_cm: float = 1.0
    """Vertical distance traveled per full revolution."""

    revolutions: float = 3.0
    """Number of helix turns."""

    sample_count: int = 64
    """Number of points sampled along the helix path."""

    start_angle_deg: float = 0.0
    handedness: str = "right"
    """``right`` | ``left``."""


def _resolve_axis(axis: str) -> int:
    a = axis.lower()
    if a == "x":
        return 0
    if a == "y":
        return 1
    if a == "z":
        return 2
    raise ValueError(f"unknown axis: {axis!r}")


def sample_helical_path(
    sweep: HelicalSweep,
    *,
    origin_cm: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> tuple[tuple[float, float, float], ...]:
    """Sample points along the helix path.

    Returns a tuple of ``(x, y, z)`` points. Use as input to a
    profile-sweep operator (the kernel program's sweep op consumes
    the path + a profile to produce real mesh geometry).
    """
    if sweep.sample_count < 2:
        raise ValueError("helical_sweep sample_count must be >= 2")
    if sweep.radius_cm <= 0 or sweep.pitch_cm == 0 or sweep.revolutions <= 0:
        raise ValueError(
            "helical_sweep radius_cm must be > 0 and revolutions/pitch must be non-zero"
        )
    sign = 1.0 if sweep.handedness.lower() == "right" else -1.0
    axis_idx = _resolve_axis(sweep.axis)
    perp_a = (axis_idx + 1) % 3
    perp_b = (axis_idx + 2) % 3
    total_angle_rad = sign * 2.0 * math.pi * sweep.revolutions
    start_angle_rad = math.radians(sweep.start_angle_deg)
    total_height_cm = sweep.pitch_cm * sweep.revolutions
    out: list[tuple[float, float, float]] = []
    for i in range(sweep.sample_count):
        t = i / (sweep.sample_count - 1)
        theta = start_angle_rad + t * total_angle_rad
        ca, sa = math.cos(theta), math.sin(theta)
        p = [origin_cm[0], origin_cm[1], origin_cm[2]]
        p[perp_a] += sweep.radius_cm * ca
        p[perp_b] += sweep.radius_cm * sa
        p[axis_idx] += t * total_height_cm
        out.append((p[0], p[1], p[2]))
    return tuple(out)


__all__ = [
    "HELICAL_SWEEP_VERSION",
    "HelicalSweep",
    "sample_helical_path",
]
