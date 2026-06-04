"""Bend / twist / taper deformers.

Per northstar §10 Lane A future-tasks, these are mesh-level
deformers operating on vertex positions. Each deformer is a pure
function from a vertex list to a deformed vertex list, plus a
typed parameter record.

The deformers are deterministic, side-effect-free, and operate on
plain tuples so they can run without numpy / trimesh.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

DEFORMERS_VERSION = "lathe.asset_foundry.deformers_v1"


@dataclass(frozen=True)
class BendDeformer:
    """Bend along an axis."""

    axis: str = "z"
    """Axis along which the bend progresses (``x``, ``y``, ``z``)."""

    bend_axis: str = "y"
    """Axis around which the bend rotates (the curl axis)."""

    angle_deg: float = 90.0
    """Total bend angle across the asset's extent along ``axis``."""

    pivot_cm: tuple[float, float, float] = (0.0, 0.0, 0.0)
    """Pivot point for the bend."""

    range_min_cm: float = 0.0
    """Bend starts where coordinate along ``axis`` >= range_min_cm."""

    range_max_cm: float = 100.0
    """Bend tops out where coordinate along ``axis`` >= range_max_cm."""


@dataclass(frozen=True)
class TwistDeformer:
    """Twist around an axis."""

    axis: str = "z"
    """Twist axis."""

    angle_deg: float = 90.0
    """Total twist across the asset's extent along ``axis``."""

    pivot_cm: tuple[float, float, float] = (0.0, 0.0, 0.0)
    range_min_cm: float = 0.0
    range_max_cm: float = 100.0


@dataclass(frozen=True)
class TaperDeformer:
    """Taper along an axis."""

    axis: str = "z"
    scale_start: float = 1.0
    scale_end: float = 0.5
    pivot_cm: tuple[float, float, float] = (0.0, 0.0, 0.0)
    range_min_cm: float = 0.0
    range_max_cm: float = 100.0


_AXIS_INDEX = {"x": 0, "y": 1, "z": 2}


def _resolve_axis(axis: str) -> int:
    axis = axis.lower()
    if axis not in _AXIS_INDEX:
        raise ValueError(f"unknown axis: {axis!r}")
    return _AXIS_INDEX[axis]


def _parameter_along(
    point: tuple[float, float, float], axis_idx: int, range_min: float, range_max: float
) -> float:
    span = range_max - range_min
    if span <= 1e-9:
        return 0.0
    raw = (point[axis_idx] - range_min) / span
    return max(0.0, min(1.0, raw))


def apply_bend(
    vertices: Sequence[tuple[float, float, float]],
    deformer: BendDeformer,
) -> tuple[tuple[float, float, float], ...]:
    """Apply a bend deformer to a sequence of vertices."""
    axis_idx = _resolve_axis(deformer.axis)
    bend_axis_idx = _resolve_axis(deformer.bend_axis)
    if axis_idx == bend_axis_idx:
        raise ValueError("bend.axis and bend.bend_axis must differ")
    # The third axis is the one the vertex coordinate sweeps in.
    third_idx = 3 - axis_idx - bend_axis_idx
    px, py, pz = deformer.pivot_cm
    pivot = (px, py, pz)
    angle_rad_total = math.radians(deformer.angle_deg)
    out: list[tuple[float, float, float]] = []
    for v in vertices:
        t = _parameter_along(v, axis_idx, deformer.range_min_cm, deformer.range_max_cm)
        angle = angle_rad_total * t
        # Translate so axis_idx coord becomes radial.
        rel = (v[0] - pivot[0], v[1] - pivot[1], v[2] - pivot[2])
        # Rotate (rel[axis_idx], rel[third_idx]) by ``angle`` around bend_axis.
        a = rel[axis_idx]
        b = rel[third_idx]
        ca, sa = math.cos(angle), math.sin(angle)
        new_a = a * ca - b * sa
        new_b = a * sa + b * ca
        new_rel = [rel[0], rel[1], rel[2]]
        new_rel[axis_idx] = new_a
        new_rel[third_idx] = new_b
        out.append(
            (
                new_rel[0] + pivot[0],
                new_rel[1] + pivot[1],
                new_rel[2] + pivot[2],
            )
        )
    return tuple(out)


def apply_twist(
    vertices: Sequence[tuple[float, float, float]],
    deformer: TwistDeformer,
) -> tuple[tuple[float, float, float], ...]:
    """Apply a twist deformer to a sequence of vertices."""
    axis_idx = _resolve_axis(deformer.axis)
    perp_a = (axis_idx + 1) % 3
    perp_b = (axis_idx + 2) % 3
    angle_rad_total = math.radians(deformer.angle_deg)
    out: list[tuple[float, float, float]] = []
    px, py, pz = deformer.pivot_cm
    for v in vertices:
        t = _parameter_along(v, axis_idx, deformer.range_min_cm, deformer.range_max_cm)
        angle = angle_rad_total * t
        ca, sa = math.cos(angle), math.sin(angle)
        a = v[perp_a] - (px, py, pz)[perp_a]
        b = v[perp_b] - (px, py, pz)[perp_b]
        new_a = a * ca - b * sa
        new_b = a * sa + b * ca
        new_v = [0.0, 0.0, 0.0]
        new_v[axis_idx] = v[axis_idx]
        new_v[perp_a] = new_a + (px, py, pz)[perp_a]
        new_v[perp_b] = new_b + (px, py, pz)[perp_b]
        out.append((new_v[0], new_v[1], new_v[2]))
    return tuple(out)


def apply_taper(
    vertices: Sequence[tuple[float, float, float]],
    deformer: TaperDeformer,
) -> tuple[tuple[float, float, float], ...]:
    """Apply a taper deformer to a sequence of vertices."""
    axis_idx = _resolve_axis(deformer.axis)
    perp_a = (axis_idx + 1) % 3
    perp_b = (axis_idx + 2) % 3
    out: list[tuple[float, float, float]] = []
    px, py, pz = deformer.pivot_cm
    for v in vertices:
        t = _parameter_along(v, axis_idx, deformer.range_min_cm, deformer.range_max_cm)
        scale = deformer.scale_start + t * (deformer.scale_end - deformer.scale_start)
        new_v = [0.0, 0.0, 0.0]
        new_v[axis_idx] = v[axis_idx]
        new_v[perp_a] = (v[perp_a] - (px, py, pz)[perp_a]) * scale + (px, py, pz)[perp_a]
        new_v[perp_b] = (v[perp_b] - (px, py, pz)[perp_b]) * scale + (px, py, pz)[perp_b]
        out.append((new_v[0], new_v[1], new_v[2]))
    return tuple(out)


__all__ = [
    "DEFORMERS_VERSION",
    "BendDeformer",
    "TaperDeformer",
    "TwistDeformer",
    "apply_bend",
    "apply_taper",
    "apply_twist",
]
