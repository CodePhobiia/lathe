"""NURBS-backed profile curves.

Per northstar §10 Lane A future-tasks. NURBS curves give artists
smooth, continuous profiles for revolved/swept ops without the
faceting artifacts of piecewise-linear polylines.

The implementation is a Cox-de Boor B-spline evaluator with
rational (weight-aware) coordinate reconstruction. Pure Python.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

NURBS_CURVE_VERSION = "lathe.asset_foundry.nurbs_curve_v1"


@dataclass(frozen=True)
class NurbsControlPoint:
    """A weighted 3D control point."""

    x: float
    y: float
    z: float = 0.0
    w: float = 1.0
    """Weight. > 0 for ordinary control; > 1 pulls the curve toward
    the control point; rational curves use varying weights."""


@dataclass(frozen=True)
class NurbsCurve:
    """A NURBS curve with control points, knot vector, and degree."""

    control_points: tuple[NurbsControlPoint, ...]
    knots: tuple[float, ...]
    degree: int = 3
    closed: bool = False


def _basis(
    i: int, p: int, u: float, knots: Sequence[float]
) -> float:
    """Cox-de Boor recursion."""
    if p == 0:
        return 1.0 if knots[i] <= u < knots[i + 1] else 0.0
    denom1 = knots[i + p] - knots[i]
    denom2 = knots[i + p + 1] - knots[i + 1]
    term1 = (
        ((u - knots[i]) / denom1) * _basis(i, p - 1, u, knots) if denom1 > 1e-12 else 0.0
    )
    term2 = (
        ((knots[i + p + 1] - u) / denom2) * _basis(i + 1, p - 1, u, knots)
        if denom2 > 1e-12
        else 0.0
    )
    return term1 + term2


def evaluate_nurbs_at(curve: NurbsCurve, u: float) -> tuple[float, float, float]:
    """Evaluate the curve at parameter ``u`` (in knot range)."""
    p = curve.degree
    n = len(curve.control_points)
    if len(curve.knots) != n + p + 1:
        raise ValueError(
            f"NURBS knot count must be {n + p + 1} (n={n} + p={p} + 1), got {len(curve.knots)}"
        )
    # Clamp u to knot range to avoid edge zero-basis.
    u_min, u_max = curve.knots[p], curve.knots[n]
    u = max(u_min, min(u_max - 1e-9, u))
    numerator_x = 0.0
    numerator_y = 0.0
    numerator_z = 0.0
    denominator = 0.0
    for i, cp in enumerate(curve.control_points):
        b = _basis(i, p, u, curve.knots)
        weighted = b * cp.w
        numerator_x += weighted * cp.x
        numerator_y += weighted * cp.y
        numerator_z += weighted * cp.z
        denominator += weighted
    if denominator <= 1e-12:
        return curve.control_points[-1].x, curve.control_points[-1].y, curve.control_points[-1].z
    return (
        numerator_x / denominator,
        numerator_y / denominator,
        numerator_z / denominator,
    )


def sample_nurbs_curve(
    curve: NurbsCurve, samples: int = 32
) -> tuple[tuple[float, float, float], ...]:
    """Sample ``samples`` points uniformly along the curve."""
    if samples < 2:
        raise ValueError("samples must be >= 2")
    p = curve.degree
    n = len(curve.control_points)
    u_min, u_max = curve.knots[p], curve.knots[n]
    out: list[tuple[float, float, float]] = []
    for i in range(samples):
        t = i / (samples - 1)
        u = u_min + t * (u_max - u_min)
        out.append(evaluate_nurbs_at(curve, u))
    return tuple(out)


def open_uniform_knot_vector(control_count: int, degree: int = 3) -> tuple[float, ...]:
    """Standard open-uniform knot vector (clamped endpoints)."""
    if control_count < degree + 1:
        raise ValueError(
            f"control_count {control_count} must be >= degree + 1 ({degree + 1})"
        )
    knot_count = control_count + degree + 1
    interior_count = knot_count - 2 * (degree + 1)
    knots: list[float] = []
    knots.extend([0.0] * (degree + 1))
    for i in range(1, interior_count + 1):
        knots.append(i / (interior_count + 1))
    knots.extend([1.0] * (degree + 1))
    return tuple(knots)


__all__ = [
    "NURBS_CURVE_VERSION",
    "NurbsControlPoint",
    "NurbsCurve",
    "evaluate_nurbs_at",
    "open_uniform_knot_vector",
    "sample_nurbs_curve",
]
