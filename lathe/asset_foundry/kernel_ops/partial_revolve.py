"""Partial rotate-extrude (sweep angle < 360°).

Per northstar §10 Lane A future-tasks, the kernel should support a
partial revolve — useful for arches, ring sectors, fan shapes,
chamfered corners. This module builds the typed mesh from a 2D
profile + sweep angle + axis.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

PARTIAL_REVOLVE_VERSION = "lathe.asset_foundry.partial_revolve_v1"


@dataclass(frozen=True)
class PartialRevolveRequest:
    """Inputs for a partial-revolve build."""

    profile_xy_cm: tuple[tuple[float, float], ...]
    """The 2D profile points in (radius, height) coordinates. Must be
    non-self-intersecting and CCW from outside."""

    axis: str = "z"
    """Revolution axis (``x`` | ``y`` | ``z``)."""

    start_angle_deg: float = 0.0
    sweep_angle_deg: float = 90.0
    """Total sweep. Negative sweeps CW. Total angle is clamped to
    [-360, 360]."""

    segments: int = 16
    """Angular subdivision count over the sweep."""

    cap_start: bool = True
    cap_end: bool = True
    """When True, the open sweep ends are closed with cap fans."""

    zone_prefix: str = "partial_revolve"


@dataclass(frozen=True)
class PartialRevolveMesh:
    """Output of a partial-revolve build."""

    request: PartialRevolveRequest
    vertices: tuple[tuple[float, float, float], ...]
    faces: tuple[tuple[int, ...], ...]
    face_zone_ids: tuple[str, ...]
    is_closed: bool


def _resolve_axis(axis: str) -> int:
    a = axis.lower()
    if a == "x":
        return 0
    if a == "y":
        return 1
    if a == "z":
        return 2
    raise ValueError(f"unknown axis: {axis!r}")


def build_partial_revolve(request: PartialRevolveRequest) -> PartialRevolveMesh:
    """Build a partial-revolve mesh from a profile + sweep parameters."""
    if request.segments < 2:
        raise ValueError("partial_revolve segments must be >= 2")
    if len(request.profile_xy_cm) < 2:
        raise ValueError("partial_revolve profile must have >= 2 points")
    sweep = max(-360.0, min(360.0, request.sweep_angle_deg))
    angle_step = math.radians(sweep) / request.segments
    angle_start = math.radians(request.start_angle_deg)
    axis_idx = _resolve_axis(request.axis)
    perp_a = (axis_idx + 1) % 3
    perp_b = (axis_idx + 2) % 3

    rings: list[list[tuple[float, float, float]]] = []
    for s in range(request.segments + 1):
        theta = angle_start + s * angle_step
        ca, sa = math.cos(theta), math.sin(theta)
        ring: list[tuple[float, float, float]] = []
        for rx, h in request.profile_xy_cm:
            v = [0.0, 0.0, 0.0]
            v[axis_idx] = h
            v[perp_a] = rx * ca
            v[perp_b] = rx * sa
            ring.append((v[0], v[1], v[2]))
        rings.append(ring)

    profile_len = len(request.profile_xy_cm)
    vertices: list[tuple[float, float, float]] = []
    for ring in rings:
        vertices.extend(ring)

    def idx(seg: int, prof: int) -> int:
        return seg * profile_len + prof

    faces: list[tuple[int, ...]] = []
    zones: list[str] = []
    for seg in range(request.segments):
        for prof in range(profile_len - 1):
            a = idx(seg, prof)
            b = idx(seg, prof + 1)
            c = idx(seg + 1, prof + 1)
            d = idx(seg + 1, prof)
            faces.append((a, b, c, d))
            zones.append(f"{request.zone_prefix}.seg_{seg:03d}.prof_{prof:03d}")

    is_closed = abs(abs(sweep) - 360.0) < 1e-6
    if request.cap_start and not is_closed:
        cap = tuple(idx(0, p) for p in range(profile_len))
        faces.append(cap)
        zones.append(f"{request.zone_prefix}.cap_start")
    if request.cap_end and not is_closed:
        cap = tuple(idx(request.segments, p) for p in reversed(range(profile_len)))
        faces.append(cap)
        zones.append(f"{request.zone_prefix}.cap_end")

    return PartialRevolveMesh(
        request=request,
        vertices=tuple(vertices),
        faces=tuple(faces),
        face_zone_ids=tuple(zones),
        is_closed=is_closed,
    )


__all__ = [
    "PARTIAL_REVOLVE_VERSION",
    "PartialRevolveRequest",
    "PartialRevolveMesh",
    "build_partial_revolve",
]
