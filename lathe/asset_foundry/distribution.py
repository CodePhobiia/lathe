"""Foundry Lane C — generic distribution primitive (linear / grid / radial / arc / along_path).

Per northstar §10 Lane C priority task #2, distribution should be a
generic primitive driven by typed parameters, not chest-specific
emitters. The existing ``op.distribute`` in
``feature_ops_v2_lowering.lower_distribute`` already handles grid /
line / ring / perimeter — this module adds the ``along_path`` mode
and an arc mode, plus the typed parameter record consumers + the
provenance fields newresearch.md §8 requires (count, density,
spacing, jitter, mirror, snap, seed).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

DISTRIBUTION_VERSION = "lathe.asset_foundry.distribution_v1"


@dataclass(frozen=True)
class DistributionParameters:
    """Per newresearch.md §8: distribution control surface."""

    mode: str = "grid"
    """``grid`` | ``linear`` | ``radial`` | ``arc`` | ``along_path``."""

    count: int = 1
    spacing_cm: float = 5.0
    density_per_cm: float | None = None
    """When set, derives count from path length / extent."""

    jitter_cm: float = 0.0
    """Random offset bound applied along the local normal."""

    jitter_seed: int = 0
    snap_to_axis: tuple[str, ...] = ()
    """e.g. ``("y", "z")`` to snap to whole-cm coords along Y/Z."""

    mirror_axis: str = ""
    """When set, mirrors the entire distribution across this axis."""


@dataclass(frozen=True)
class DistributionPlacement:
    """One placement output of a distribute call."""

    placement_id: str
    position_cm: tuple[float, float, float]
    orientation_quat: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)
    tangent: tuple[float, float, float] = (1.0, 0.0, 0.0)
    """Unit-length local tangent (useful for along_path orientation)."""

    normal: tuple[float, float, float] = (0.0, 0.0, 1.0)


@dataclass(frozen=True)
class DistributionReport:
    """Provenance record for a distribute call."""

    version: str
    parameters: DistributionParameters
    placements: tuple[DistributionPlacement, ...]
    actual_count: int
    actual_spacing_cm: float | None
    target_surface_or_face: str
    """The surface / face / spline ID the distribution landed on."""


class _Rng:
    """Deterministic LCG used for jitter."""

    def __init__(self, seed: int) -> None:
        self.state = seed if seed != 0 else 0xC0FFEE

    def next_float(self) -> float:
        self.state = (1664525 * self.state + 1013904223) & 0xFFFFFFFF
        return self.state / 0xFFFFFFFF


def _snap(value: float, axis: str, snap_axes: Sequence[str]) -> float:
    if axis in snap_axes:
        return round(value)
    return value


def _path_lengths(path: Sequence[tuple[float, float, float]]) -> tuple[float, list[float]]:
    """Compute cumulative arc length along a polyline."""
    cumulative = [0.0]
    total = 0.0
    for i in range(1, len(path)):
        ax, ay, az = path[i - 1]
        bx, by, bz = path[i]
        d = math.sqrt((bx - ax) ** 2 + (by - ay) ** 2 + (bz - az) ** 2)
        total += d
        cumulative.append(total)
    return total, cumulative


def _sample_path(
    path: Sequence[tuple[float, float, float]],
    cumulative: Sequence[float],
    target_length: float,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Return (position, tangent) at given arc length."""
    if not path or len(path) < 2:
        raise ValueError("path must have >= 2 points")
    total = cumulative[-1]
    s = max(0.0, min(total, target_length))
    for i in range(1, len(cumulative)):
        if cumulative[i] >= s:
            seg_start = cumulative[i - 1]
            seg_end = cumulative[i]
            seg_len = seg_end - seg_start
            t = (s - seg_start) / seg_len if seg_len > 1e-9 else 0.0
            ax, ay, az = path[i - 1]
            bx, by, bz = path[i]
            pos = (
                ax + t * (bx - ax),
                ay + t * (by - ay),
                az + t * (bz - az),
            )
            seg_dx, seg_dy, seg_dz = bx - ax, by - ay, bz - az
            seg_len_pos = math.sqrt(seg_dx ** 2 + seg_dy ** 2 + seg_dz ** 2) or 1.0
            tangent = (seg_dx / seg_len_pos, seg_dy / seg_len_pos, seg_dz / seg_len_pos)
            return pos, tangent
    return path[-1], (1.0, 0.0, 0.0)


def distribute_along_path(
    params: DistributionParameters,
    *,
    path_cm: Sequence[tuple[float, float, float]],
    target_id: str = "path",
) -> DistributionReport:
    """Distribute placements along a polyline path."""
    if len(path_cm) < 2:
        raise ValueError("path_cm must have >= 2 points")
    total, cumulative = _path_lengths(path_cm)
    if params.density_per_cm and params.density_per_cm > 0:
        count = max(1, int(round(total * params.density_per_cm)))
    else:
        count = params.count
    actual_count = max(1, count)
    actual_spacing = total / max(1, actual_count - 1) if actual_count > 1 else None
    rng = _Rng(params.jitter_seed)
    placements: list[DistributionPlacement] = []
    for i in range(actual_count):
        t = i / max(1, actual_count - 1) if actual_count > 1 else 0.5
        target_length = t * total
        pos, tangent = _sample_path(path_cm, cumulative, target_length)
        if params.jitter_cm > 0:
            dy = (rng.next_float() - 0.5) * 2.0 * params.jitter_cm
            dz = (rng.next_float() - 0.5) * 2.0 * params.jitter_cm
            pos = (pos[0], pos[1] + dy, pos[2] + dz)
        sx = _snap(pos[0], "x", params.snap_to_axis)
        sy = _snap(pos[1], "y", params.snap_to_axis)
        sz = _snap(pos[2], "z", params.snap_to_axis)
        placements.append(
            DistributionPlacement(
                placement_id=f"{target_id}.placement_{i:03d}",
                position_cm=(sx, sy, sz),
                tangent=tangent,
            )
        )
    if params.mirror_axis:
        mirrored = _mirror_placements(placements, params.mirror_axis)
        placements = list(placements) + list(mirrored)
        actual_count = len(placements)
    return DistributionReport(
        version=DISTRIBUTION_VERSION,
        parameters=params,
        placements=tuple(placements),
        actual_count=actual_count,
        actual_spacing_cm=actual_spacing,
        target_surface_or_face=target_id,
    )


def distribute_arc(
    params: DistributionParameters,
    *,
    center_cm: tuple[float, float, float] = (0.0, 0.0, 0.0),
    radius_cm: float = 10.0,
    axis: str = "z",
    start_angle_deg: float = 0.0,
    sweep_angle_deg: float = 90.0,
    target_id: str = "arc",
) -> DistributionReport:
    """Distribute placements along an arc."""
    if params.count < 1:
        raise ValueError("arc count must be >= 1")
    axis_idx = {"x": 0, "y": 1, "z": 2}[axis.lower()]
    perp_a = (axis_idx + 1) % 3
    perp_b = (axis_idx + 2) % 3
    sweep_rad = math.radians(sweep_angle_deg)
    start_rad = math.radians(start_angle_deg)
    placements: list[DistributionPlacement] = []
    rng = _Rng(params.jitter_seed)
    for i in range(params.count):
        t = i / max(1, params.count - 1) if params.count > 1 else 0.5
        theta = start_rad + t * sweep_rad
        ca, sa = math.cos(theta), math.sin(theta)
        pos = [center_cm[0], center_cm[1], center_cm[2]]
        pos[perp_a] += radius_cm * ca
        pos[perp_b] += radius_cm * sa
        if params.jitter_cm > 0:
            pos[axis_idx] += (rng.next_float() - 0.5) * 2.0 * params.jitter_cm
        tangent = [0.0, 0.0, 0.0]
        tangent[perp_a] = -sa
        tangent[perp_b] = ca
        placements.append(
            DistributionPlacement(
                placement_id=f"{target_id}.placement_{i:03d}",
                position_cm=(pos[0], pos[1], pos[2]),
                tangent=(tangent[0], tangent[1], tangent[2]),
            )
        )
    actual_arc_length = radius_cm * abs(sweep_rad)
    actual_spacing = (
        actual_arc_length / max(1, params.count - 1) if params.count > 1 else None
    )
    return DistributionReport(
        version=DISTRIBUTION_VERSION,
        parameters=params,
        placements=tuple(placements),
        actual_count=params.count,
        actual_spacing_cm=actual_spacing,
        target_surface_or_face=target_id,
    )


def _mirror_placements(
    placements: Sequence[DistributionPlacement], axis: str
) -> tuple[DistributionPlacement, ...]:
    axis_idx = {"x": 0, "y": 1, "z": 2}.get(axis.lower())
    if axis_idx is None:
        return ()
    out: list[DistributionPlacement] = []
    for p in placements:
        pos = list(p.position_cm)
        pos[axis_idx] = -pos[axis_idx]
        out.append(
            DistributionPlacement(
                placement_id=f"{p.placement_id}.mirror",
                position_cm=(pos[0], pos[1], pos[2]),
                orientation_quat=p.orientation_quat,
                tangent=p.tangent,
                normal=p.normal,
            )
        )
    return tuple(out)


def report_to_dict(report: DistributionReport) -> dict:
    return {
        "version": report.version,
        "actual_count": report.actual_count,
        "actual_spacing_cm": report.actual_spacing_cm,
        "target_surface_or_face": report.target_surface_or_face,
        "parameters": {
            "mode": report.parameters.mode,
            "count": report.parameters.count,
            "spacing_cm": report.parameters.spacing_cm,
            "density_per_cm": report.parameters.density_per_cm,
            "jitter_cm": report.parameters.jitter_cm,
            "jitter_seed": report.parameters.jitter_seed,
            "snap_to_axis": list(report.parameters.snap_to_axis),
            "mirror_axis": report.parameters.mirror_axis,
        },
        "placements": [
            {
                "placement_id": p.placement_id,
                "position_cm": list(p.position_cm),
                "orientation_quat": list(p.orientation_quat),
                "tangent": list(p.tangent),
                "normal": list(p.normal),
            }
            for p in report.placements
        ],
    }


__all__ = [
    "DISTRIBUTION_VERSION",
    "DistributionParameters",
    "DistributionPlacement",
    "DistributionReport",
    "distribute_along_path",
    "distribute_arc",
    "report_to_dict",
]
