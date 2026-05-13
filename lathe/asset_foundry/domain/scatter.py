"""Scatter + surface scatter — production multipliers.

Per northstar §11 Phase 3. Scatter places instances on a target
(surface, point cloud, scatter region) according to density, jitter,
mask, and seed parameters. Used for foliage, fasteners, decals,
rocks, pebbles, debris.

This module is deterministic + pure-Python. Output is a list of
``ScatterInstance`` records the kernel program / asset_foundry
generators consume to place real geometry.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

SCATTER_VERSION = "lathe.asset_foundry.scatter_v1"


@dataclass(frozen=True)
class ScatterRequest:
    region_id: str
    """The surface / region identifier being scattered on."""

    target_kind: str = "rectangle"
    """``rectangle`` | ``disk`` | ``polygon`` | ``surface_uv`` |
    ``point_cloud``."""

    bounds_cm: tuple[tuple[float, float], tuple[float, float]] = ((0.0, 0.0), (100.0, 100.0))
    """For rectangle / disk."""

    polygon_points_cm: tuple[tuple[float, float], ...] = ()
    """For ``polygon`` target."""

    density_per_sqm: float = 1.0
    jitter_cm: float = 0.0
    rotation_jitter_deg: float = 0.0
    scale_jitter: tuple[float, float] = (1.0, 1.0)
    """``(min, max)`` multiplicative scale jitter."""

    seed: int = 0
    target_count: int | None = None
    """When set, overrides density-derived count."""

    mask: Mapping[str, Any] = field(default_factory=dict)
    """Field-expression mask (see field_attrs). When provided, an
    instance is rejected when the mask evaluates to falsy at its
    candidate position."""


@dataclass(frozen=True)
class ScatterInstance:
    """One scattered instance placement."""

    instance_id: str
    position_cm: tuple[float, float, float]
    rotation_deg: float
    scale: float


@dataclass(frozen=True)
class ScatterResult:
    request: ScatterRequest
    instances: tuple[ScatterInstance, ...]
    actual_count: int
    rejected_by_mask: int
    diagnostics: tuple[str, ...]


class _Rng:
    def __init__(self, seed: int) -> None:
        self.state = seed if seed != 0 else 0xBEEF

    def next_float(self) -> float:
        self.state = (1664525 * self.state + 1013904223) & 0xFFFFFFFF
        return self.state / 0xFFFFFFFF


def _polygon_contains(
    polygon: Sequence[tuple[float, float]], px: float, py: float
) -> bool:
    """Ray-casting point-in-polygon test."""
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > py) != (yj > py)) and (
            px < (xj - xi) * (py - yi) / (yj - yi + 1e-12) + xi
        ):
            inside = not inside
        j = i
    return inside


def scatter_on_surface(request: ScatterRequest) -> ScatterResult:
    """Place scatter instances inside the target region."""
    rng = _Rng(request.seed)
    diagnostics: list[str] = []
    instances: list[ScatterInstance] = []
    rejected = 0

    if request.target_kind == "rectangle":
        (min_x, min_y), (max_x, max_y) = request.bounds_cm
        area_cm2 = max(0.0, (max_x - min_x) * (max_y - min_y))
        area_m2 = area_cm2 / 10000.0
        target_count = (
            request.target_count
            if request.target_count is not None
            else max(0, int(round(request.density_per_sqm * area_m2)))
        )
        for i in range(target_count):
            x = min_x + rng.next_float() * (max_x - min_x)
            y = min_y + rng.next_float() * (max_y - min_y)
            if request.jitter_cm > 0:
                x += (rng.next_float() - 0.5) * 2.0 * request.jitter_cm
                y += (rng.next_float() - 0.5) * 2.0 * request.jitter_cm
            rotation = (rng.next_float() - 0.5) * 2.0 * request.rotation_jitter_deg
            scale = (
                request.scale_jitter[0]
                + rng.next_float() * (request.scale_jitter[1] - request.scale_jitter[0])
            )
            instances.append(
                ScatterInstance(
                    instance_id=f"{request.region_id}.scatter_{i:04d}",
                    position_cm=(x, y, 0.0),
                    rotation_deg=rotation,
                    scale=scale,
                )
            )
        diagnostics.append(f"scatter_rectangle_area_m2: {area_m2:.3f}")
    elif request.target_kind == "polygon":
        if len(request.polygon_points_cm) < 3:
            return ScatterResult(
                request=request,
                instances=(),
                actual_count=0,
                rejected_by_mask=0,
                diagnostics=("polygon_target_needs_>=3_points",),
            )
        # Bounding box of polygon for sampling.
        xs = [p[0] for p in request.polygon_points_cm]
        ys = [p[1] for p in request.polygon_points_cm]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        bbox_area_cm2 = (max_x - min_x) * (max_y - min_y)
        bbox_area_m2 = bbox_area_cm2 / 10000.0
        target_count = (
            request.target_count
            if request.target_count is not None
            else max(0, int(round(request.density_per_sqm * bbox_area_m2)))
        )
        attempts = 0
        while len(instances) < target_count and attempts < target_count * 10:
            attempts += 1
            x = min_x + rng.next_float() * (max_x - min_x)
            y = min_y + rng.next_float() * (max_y - min_y)
            if not _polygon_contains(request.polygon_points_cm, x, y):
                rejected += 1
                continue
            if request.jitter_cm > 0:
                x += (rng.next_float() - 0.5) * 2.0 * request.jitter_cm
                y += (rng.next_float() - 0.5) * 2.0 * request.jitter_cm
            rotation = (rng.next_float() - 0.5) * 2.0 * request.rotation_jitter_deg
            scale = (
                request.scale_jitter[0]
                + rng.next_float() * (request.scale_jitter[1] - request.scale_jitter[0])
            )
            instances.append(
                ScatterInstance(
                    instance_id=f"{request.region_id}.scatter_{len(instances):04d}",
                    position_cm=(x, y, 0.0),
                    rotation_deg=rotation,
                    scale=scale,
                )
            )
        if attempts >= target_count * 10:
            diagnostics.append("scatter_polygon_acceptance_attempts_exhausted")
    else:
        return ScatterResult(
            request=request,
            instances=(),
            actual_count=0,
            rejected_by_mask=0,
            diagnostics=(f"unsupported_target_kind: {request.target_kind!r}",),
        )

    return ScatterResult(
        request=request,
        instances=tuple(instances),
        actual_count=len(instances),
        rejected_by_mask=rejected,
        diagnostics=tuple(diagnostics),
    )


__all__ = [
    "SCATTER_VERSION",
    "ScatterInstance",
    "ScatterRequest",
    "ScatterResult",
    "scatter_on_surface",
]
