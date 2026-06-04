"""Inigo Quilez-style SDF expression algebra.

Each :class:`SDFExpr` node implements ``distance(p) -> float`` (vectorized
over a point cloud via :class:`numpy.ndarray`). The formulas follow IQ's
canonical "Distance Functions" reference at https://iquilezles.org/.

Design notes:

* All distance methods accept ``points`` as either a single ``(3,)``
  vector or an ``(N, 3)`` array; the result is a scalar or ``(N,)``.
* Modifiers transform the *evaluation point* before delegating to the
  child expression. This is the standard SDF pattern — modeling space
  is morphed by inverse-transforming query points so the analytical
  primitive distance remains exact.
* Smooth booleans use the canonical IQ polynomial smooth-min / smooth-max
  with parameter ``k`` controlling blend radius.

The algebra is closed under composition: every node returns a valid SDF
that downstream evaluators and extractors can consume uniformly.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


@dataclass
class SDFExpr:
    """Abstract base for SDF expression nodes.

    Subclasses implement :meth:`distance` returning a signed distance for
    one or many query points. Negative values are inside the surface,
    zero on the surface, positive outside.
    """

    def distance(self, p: np.ndarray) -> np.ndarray:
        """Evaluate the SDF at ``p``.

        Args:
            p: query point(s). Either shape ``(3,)`` or ``(N, 3)``.

        Returns:
            Signed distance(s). Scalar or shape ``(N,)``.
        """
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        """Serialize the expression tree to a deterministic dict.

        Used by the IR serializer and trace records so the F-Rep program
        round-trips through the build cache.
        """
        raise NotImplementedError


@dataclass
class ConnectedIntent(SDFExpr):
    """Wrapper marking an authored SDF composition as one intended body."""

    expr: SDFExpr
    label: str = "connected"

    def distance(self, p: Any) -> np.ndarray:
        return self.expr.distance(p)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": "connected_intent",
            "label": str(self.label),
            "expr": self.expr.to_dict(),
        }


def _as_points(p: Any) -> np.ndarray:
    arr = np.asarray(p, dtype=np.float64)
    if arr.ndim == 1:
        if arr.shape[0] != 3:
            raise ValueError(f"SDF point must be 3D, got shape {arr.shape}")
        return arr.reshape(1, 3)
    if arr.ndim == 2 and arr.shape[1] == 3:
        return arr
    raise ValueError(f"SDF points must be (3,) or (N, 3), got shape {arr.shape}")


def _scalar_or_array(d: np.ndarray, was_single: bool) -> np.ndarray:
    if was_single:
        return float(d[0])
    return d


def _axis_indices(axis: str) -> tuple[int, tuple[int, int]]:
    resolved = str(axis).lower()
    if resolved == "x":
        return 0, (1, 2)
    if resolved == "y":
        return 1, (0, 2)
    if resolved == "z":
        return 2, (0, 1)
    raise ValueError(f"Axis must be x|y|z, got {axis!r}")


# ---------------------------------------------------------------------------
# Primitives — IQ canonical SDFs
# ---------------------------------------------------------------------------


@dataclass
class Sphere(SDFExpr):
    """Sphere SDF — IQ ``sdSphere``: ``length(p) - r``."""

    radius: float = 1.0

    def distance(self, p: Any) -> np.ndarray:
        pts = _as_points(p)
        d = np.linalg.norm(pts, axis=1) - float(self.radius)
        return _scalar_or_array(d, np.asarray(p).ndim == 1)

    def to_dict(self) -> dict[str, Any]:
        return {"op": "sphere", "radius": float(self.radius)}


@dataclass
class Box(SDFExpr):
    """Box SDF — IQ ``sdBox``.

    ``q = abs(p) - half_extents``;
    ``length(max(q, 0)) + min(max(q.x, q.y, q.z), 0)``.
    """

    half_extents: tuple[float, float, float] = (0.5, 0.5, 0.5)

    def distance(self, p: Any) -> np.ndarray:
        pts = _as_points(p)
        he = np.asarray(self.half_extents, dtype=np.float64)
        q = np.abs(pts) - he
        outside = np.linalg.norm(np.maximum(q, 0.0), axis=1)
        inside = np.minimum(np.max(q, axis=1), 0.0)
        d = outside + inside
        return _scalar_or_array(d, np.asarray(p).ndim == 1)

    def to_dict(self) -> dict[str, Any]:
        return {"op": "box", "half_extents": list(self.half_extents)}


@dataclass
class Plane(SDFExpr):
    """Plane SDF — half-space ``dot(p, n) - distance``.

    ``normal`` is normalized internally; ``distance`` is the signed offset
    from the origin along the normal.
    """

    normal: tuple[float, float, float] = (0.0, 1.0, 0.0)
    distance_offset: float = 0.0

    def distance(self, p: Any) -> np.ndarray:
        pts = _as_points(p)
        n = np.asarray(self.normal, dtype=np.float64)
        nlen = np.linalg.norm(n)
        if nlen < 1e-12:
            raise ValueError("Plane normal must be non-zero")
        n = n / nlen
        d = pts @ n - float(self.distance_offset)
        return _scalar_or_array(d, np.asarray(p).ndim == 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": "plane",
            "normal": list(self.normal),
            "distance_offset": float(self.distance_offset),
        }


@dataclass
class Cylinder(SDFExpr):
    """Capped cylinder SDF — IQ ``sdCappedCylinder``.

    Axis is +Y. Use a Rotate wrapper for other orientations.
    """

    radius: float = 0.5
    height: float = 1.0

    def distance(self, p: Any) -> np.ndarray:
        pts = _as_points(p)
        # IQ formula: d = abs(vec2(length(p.xz), p.y)) - vec2(r, h);
        # return min(max(d.x, d.y), 0) + length(max(d, 0))
        radial = np.linalg.norm(pts[:, [0, 2]], axis=1)
        dx = radial - float(self.radius)
        dy = np.abs(pts[:, 1]) - 0.5 * float(self.height)
        outside = np.sqrt(np.maximum(dx, 0.0) ** 2 + np.maximum(dy, 0.0) ** 2)
        inside = np.minimum(np.maximum(dx, dy), 0.0)
        d = outside + inside
        return _scalar_or_array(d, np.asarray(p).ndim == 1)

    def to_dict(self) -> dict[str, Any]:
        return {"op": "cylinder", "radius": float(self.radius), "height": float(self.height)}


@dataclass
class Frustum(SDFExpr):
    """Capped conical frustum SDF centered on the origin.

    Axis is +Y. ``radius_bottom`` is at ``-height/2`` and
    ``radius_top`` is at ``+height/2``.
    """

    radius_bottom: float = 0.5
    radius_top: float = 0.25
    height: float = 1.0

    def distance(self, p: Any) -> np.ndarray:
        pts = _as_points(p)
        half_height = 0.5 * float(self.height)
        r1 = float(self.radius_bottom)
        r2 = float(self.radius_top)
        radial = np.linalg.norm(pts[:, [0, 2]], axis=1)
        q = np.stack((radial, pts[:, 1]), axis=1)
        k1 = np.array((r2, half_height), dtype=np.float64)
        k2 = np.array((r2 - r1, 2.0 * half_height), dtype=np.float64)
        cap_radius = np.where(q[:, 1] < 0.0, r1, r2)
        ca = np.stack(
            (
                q[:, 0] - np.minimum(q[:, 0], cap_radius),
                np.abs(q[:, 1]) - half_height,
            ),
            axis=1,
        )
        denom = float(k2 @ k2)
        if denom <= 1e-12:
            d = Cylinder(radius=max(r1, r2), height=float(self.height)).distance(pts)
            return _scalar_or_array(d, np.asarray(p).ndim == 1)
        t = np.clip(((k1 - q) @ k2) / denom, 0.0, 1.0)
        cb = q - k1 + t[:, None] * k2
        sign = np.where((cb[:, 0] < 0.0) & (ca[:, 1] < 0.0), -1.0, 1.0)
        d2 = np.minimum(np.sum(ca * ca, axis=1), np.sum(cb * cb, axis=1))
        d = sign * np.sqrt(np.maximum(d2, 0.0))
        return _scalar_or_array(d, np.asarray(p).ndim == 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": "frustum",
            "radius_bottom": float(self.radius_bottom),
            "radius_top": float(self.radius_top),
            "height": float(self.height),
        }


@dataclass
class Torus(SDFExpr):
    """Torus SDF — IQ ``sdTorus``.

    ``length((length(p.xz) - major, p.y)) - minor``.
    Ring lies in the XZ plane around +Y.
    """

    major_radius: float = 0.5
    minor_radius: float = 0.15

    def distance(self, p: Any) -> np.ndarray:
        pts = _as_points(p)
        radial = np.linalg.norm(pts[:, [0, 2]], axis=1) - float(self.major_radius)
        d = np.sqrt(radial * radial + pts[:, 1] * pts[:, 1]) - float(self.minor_radius)
        return _scalar_or_array(d, np.asarray(p).ndim == 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": "torus",
            "major_radius": float(self.major_radius),
            "minor_radius": float(self.minor_radius),
        }


@dataclass
class Capsule(SDFExpr):
    """Capsule SDF — IQ ``sdVerticalCapsule``.

    Axis +Y, ``half_height`` is the half-height of the central cylindrical
    portion (excluding the caps), ``radius`` is the rounded-cap radius.
    """

    half_height: float = 0.4
    radius: float = 0.2

    def distance(self, p: Any) -> np.ndarray:
        pts = _as_points(p)
        q = pts.copy()
        q[:, 1] = q[:, 1] - np.clip(q[:, 1], -float(self.half_height), float(self.half_height))
        d = np.linalg.norm(q, axis=1) - float(self.radius)
        return _scalar_or_array(d, np.asarray(p).ndim == 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": "capsule",
            "half_height": float(self.half_height),
            "radius": float(self.radius),
        }


@dataclass
class SegmentCapsule(SDFExpr):
    """Capsule SDF between two arbitrary 3D endpoints."""

    a: tuple[float, float, float] = (0.0, -0.5, 0.0)
    b: tuple[float, float, float] = (0.0, 0.5, 0.0)
    radius: float = 0.2

    def distance(self, p: Any) -> np.ndarray:
        pts = _as_points(p)
        a = np.asarray(self.a, dtype=np.float64)
        b = np.asarray(self.b, dtype=np.float64)
        ba = b - a
        denom = float(np.dot(ba, ba))
        if denom <= 1e-12:
            d = np.linalg.norm(pts - a, axis=1) - float(self.radius)
            return _scalar_or_array(d, np.asarray(p).ndim == 1)
        pa = pts - a
        h = np.clip((pa @ ba) / denom, 0.0, 1.0)
        closest = a + h[:, None] * ba
        d = np.linalg.norm(pts - closest, axis=1) - float(self.radius)
        return _scalar_or_array(d, np.asarray(p).ndim == 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": "segment_capsule",
            "a": list(self.a),
            "b": list(self.b),
            "radius": float(self.radius),
        }


def _segment_frame(
    a: np.ndarray,
    b: np.ndarray,
    up_hint: tuple[float, float, float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    axis = b - a
    length = float(np.linalg.norm(axis))
    if length <= 1e-12:
        raise ValueError("Segment endpoints must be distinct")
    w = axis / length
    hint = np.asarray(up_hint, dtype=np.float64)
    hint_norm = float(np.linalg.norm(hint))
    if hint_norm <= 1e-12:
        hint = np.asarray((0.0, 1.0, 0.0), dtype=np.float64)
    else:
        hint = hint / hint_norm
    u = np.cross(hint, w)
    u_norm = float(np.linalg.norm(u))
    if u_norm <= 1e-8:
        fallback = np.asarray((0.0, 0.0, 1.0), dtype=np.float64)
        if abs(float(fallback @ w)) > 0.95:
            fallback = np.asarray((1.0, 0.0, 0.0), dtype=np.float64)
        u = np.cross(fallback, w)
        u_norm = float(np.linalg.norm(u))
    u = u / max(u_norm, 1e-12)
    v = np.cross(w, u)
    v = v / max(float(np.linalg.norm(v)), 1e-12)
    return w, u, v, length


@dataclass
class SegmentBox(SDFExpr):
    """Rectangular beam SDF between arbitrary 3D endpoints."""

    a: tuple[float, float, float] = (0.0, -0.5, 0.0)
    b: tuple[float, float, float] = (0.0, 0.5, 0.0)
    half_width: float = 0.1
    half_depth: float = 0.1
    up_hint: tuple[float, float, float] = (0.0, 1.0, 0.0)

    def distance(self, p: Any) -> np.ndarray:
        pts = _as_points(p)
        a = np.asarray(self.a, dtype=np.float64)
        b = np.asarray(self.b, dtype=np.float64)
        w, u, v, length = _segment_frame(a, b, self.up_hint)
        center = (a + b) * 0.5
        rel = pts - center
        local = np.stack((rel @ w, rel @ u, rel @ v), axis=1)
        half_extents = np.asarray(
            (0.5 * length, float(self.half_width), float(self.half_depth)),
            dtype=np.float64,
        )
        q = np.abs(local) - half_extents
        outside = np.linalg.norm(np.maximum(q, 0.0), axis=1)
        inside = np.minimum(np.max(q, axis=1), 0.0)
        d = outside + inside
        return _scalar_or_array(d, np.asarray(p).ndim == 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": "segment_box",
            "a": list(self.a),
            "b": list(self.b),
            "half_width": float(self.half_width),
            "half_depth": float(self.half_depth),
            "up_hint": list(self.up_hint),
        }


@dataclass
class SegmentExtrudedProfile(SDFExpr):
    """Sweep an arbitrary closed 2D profile between 3D endpoints."""

    a: tuple[float, float, float] = (0.0, -0.5, 0.0)
    b: tuple[float, float, float] = (0.0, 0.5, 0.0)
    profile_points: tuple[tuple[float, float], ...] = (
        (-0.1, -0.1),
        (0.1, -0.1),
        (0.1, 0.1),
        (-0.1, 0.1),
    )
    up_hint: tuple[float, float, float] = (0.0, 1.0, 0.0)
    start_scale: float = 1.0
    end_scale: float = 1.0
    twist_degrees: float = 0.0

    def distance(self, p: Any) -> np.ndarray:
        pts = _as_points(p)
        a = np.asarray(self.a, dtype=np.float64)
        b = np.asarray(self.b, dtype=np.float64)
        w, u, v, length = _segment_frame(a, b, self.up_hint)
        center = (a + b) * 0.5
        rel = pts - center
        axial = rel @ w
        cross = np.stack((rel @ u, rel @ v), axis=1)
        t = np.clip((axial / max(length, 1e-12)) + 0.5, 0.0, 1.0)
        scale = (
            float(self.start_scale) * (1.0 - t)
            + float(self.end_scale) * t
        )
        scale = np.maximum(scale, 1e-9)
        if abs(float(self.twist_degrees)) > 1e-12:
            angle = np.radians(float(self.twist_degrees)) * t
            ca = np.cos(-angle)
            sa = np.sin(-angle)
            x = cross[:, 0] * ca - cross[:, 1] * sa
            y = cross[:, 0] * sa + cross[:, 1] * ca
            cross = np.stack((x, y), axis=1)
        cross = cross / scale[:, None]
        profile = np.asarray(self.profile_points, dtype=np.float64)
        d2 = _signed_distance_polygon_2d(cross, profile) * scale
        da = np.abs(axial) - 0.5 * length
        outside = np.sqrt(np.maximum(d2, 0.0) ** 2 + np.maximum(da, 0.0) ** 2)
        inside = np.minimum(np.maximum(d2, da), 0.0)
        d = outside + inside
        return _scalar_or_array(d, np.asarray(p).ndim == 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": "segment_extruded_profile",
            "a": list(self.a),
            "b": list(self.b),
            "profile_points": [
                [float(point[0]), float(point[1])] for point in self.profile_points
            ],
            "up_hint": list(self.up_hint),
            "start_scale": float(self.start_scale),
            "end_scale": float(self.end_scale),
            "twist_degrees": float(self.twist_degrees),
        }


@dataclass
class SegmentLoftedProfile(SDFExpr):
    """Loft between two closed 2D profiles along a 3D segment."""

    a: tuple[float, float, float] = (0.0, -0.5, 0.0)
    b: tuple[float, float, float] = (0.0, 0.5, 0.0)
    profile_start: tuple[tuple[float, float], ...] = (
        (-0.1, -0.1),
        (0.1, -0.1),
        (0.1, 0.1),
        (-0.1, 0.1),
    )
    profile_end: tuple[tuple[float, float], ...] = (
        (-0.2, -0.05),
        (0.2, -0.05),
        (0.2, 0.05),
        (-0.2, 0.05),
    )
    up_hint: tuple[float, float, float] = (0.0, 1.0, 0.0)
    twist_degrees: float = 0.0

    def distance(self, p: Any) -> np.ndarray:
        pts = _as_points(p)
        a = np.asarray(self.a, dtype=np.float64)
        b = np.asarray(self.b, dtype=np.float64)
        w, u, v, length = _segment_frame(a, b, self.up_hint)
        center = (a + b) * 0.5
        rel = pts - center
        axial = rel @ w
        cross = np.stack((rel @ u, rel @ v), axis=1)
        t = np.clip((axial / max(length, 1e-12)) + 0.5, 0.0, 1.0)
        if abs(float(self.twist_degrees)) > 1e-12:
            angle = np.radians(float(self.twist_degrees)) * t
            ca = np.cos(-angle)
            sa = np.sin(-angle)
            x = cross[:, 0] * ca - cross[:, 1] * sa
            y = cross[:, 0] * sa + cross[:, 1] * ca
            cross = np.stack((x, y), axis=1)
        profile_start = np.asarray(self.profile_start, dtype=np.float64)
        profile_end = np.asarray(self.profile_end, dtype=np.float64)
        d2 = _signed_distance_lerped_polygon_2d(cross, profile_start, profile_end, t)
        da = np.abs(axial) - 0.5 * length
        outside = np.sqrt(np.maximum(d2, 0.0) ** 2 + np.maximum(da, 0.0) ** 2)
        inside = np.minimum(np.maximum(d2, da), 0.0)
        d = outside + inside
        return _scalar_or_array(d, np.asarray(p).ndim == 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": "segment_lofted_profile",
            "a": list(self.a),
            "b": list(self.b),
            "profile_start": [
                [float(point[0]), float(point[1])] for point in self.profile_start
            ],
            "profile_end": [
                [float(point[0]), float(point[1])] for point in self.profile_end
            ],
            "up_hint": list(self.up_hint),
            "twist_degrees": float(self.twist_degrees),
        }


@dataclass
class TaperedSegmentCapsule(SDFExpr):
    """Tapered capsule-like SDF between two endpoints.

    Radius varies linearly along the center segment, which gives Lathe
    branch, vine, cable, horn, handle, and limb forms without forcing
    authors back into hand-built loft meshes.
    """

    a: tuple[float, float, float] = (0.0, -0.5, 0.0)
    b: tuple[float, float, float] = (0.0, 0.5, 0.0)
    radius_start: float = 0.25
    radius_end: float = 0.1

    def distance(self, p: Any) -> np.ndarray:
        pts = _as_points(p)
        a = np.asarray(self.a, dtype=np.float64)
        b = np.asarray(self.b, dtype=np.float64)
        ba = b - a
        denom = float(np.dot(ba, ba))
        if denom <= 1e-12:
            radius = max(float(self.radius_start), float(self.radius_end))
            d = np.linalg.norm(pts - a, axis=1) - radius
            return _scalar_or_array(d, np.asarray(p).ndim == 1)
        pa = pts - a
        h = np.clip((pa @ ba) / denom, 0.0, 1.0)
        closest = a + h[:, None] * ba
        radius = (
            float(self.radius_start) * (1.0 - h)
            + float(self.radius_end) * h
        )
        d = np.linalg.norm(pts - closest, axis=1) - radius
        return _scalar_or_array(d, np.asarray(p).ndim == 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": "tapered_segment_capsule",
            "a": list(self.a),
            "b": list(self.b),
            "radius_start": float(self.radius_start),
            "radius_end": float(self.radius_end),
        }


@dataclass
class RoundedSlot(SDFExpr):
    """Extruded rounded-slot SDF centered on the origin."""

    length: float = 2.0
    radius: float = 0.25
    depth: float = 0.2
    axis: str = "x"
    normal_axis: str = "z"

    def distance(self, p: Any) -> np.ndarray:
        pts = _as_points(p)
        axes = {"x": 0, "y": 1, "z": 2}
        slot_axis = axes.get(str(self.axis).lower(), 0)
        normal_axis = axes.get(str(self.normal_axis).lower(), 2)
        if slot_axis == normal_axis:
            normal_axis = 2 if slot_axis != 2 else 1
        side_axis = next(axis for axis in range(3) if axis not in {slot_axis, normal_axis})
        half_segment = max(float(self.length) * 0.5 - float(self.radius), 0.0)
        qx = np.abs(pts[:, slot_axis]) - half_segment
        qy = np.abs(pts[:, side_axis])
        outside_2d = np.sqrt(np.maximum(qx, 0.0) ** 2 + np.maximum(qy, 0.0) ** 2)
        inside_2d = np.minimum(np.maximum(qx, qy), 0.0)
        d2 = outside_2d + inside_2d - float(self.radius)
        dz = np.abs(pts[:, normal_axis]) - 0.5 * float(self.depth)
        outside = np.sqrt(np.maximum(d2, 0.0) ** 2 + np.maximum(dz, 0.0) ** 2)
        inside = np.minimum(np.maximum(d2, dz), 0.0)
        d = outside + inside
        return _scalar_or_array(d, np.asarray(p).ndim == 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": "rounded_slot",
            "length": float(self.length),
            "radius": float(self.radius),
            "depth": float(self.depth),
            "axis": str(self.axis),
            "normal_axis": str(self.normal_axis),
        }


def _signed_distance_polygon_2d(points: np.ndarray, polygon: np.ndarray) -> np.ndarray:
    """Vectorized signed distance to a closed 2D polygon."""
    if polygon.ndim != 2 or polygon.shape[1] != 2 or polygon.shape[0] < 3:
        raise ValueError("ExtrudedPolygon profile_points must contain at least three 2D points")
    d2 = np.full(points.shape[0], np.inf, dtype=np.float64)
    inside = np.zeros(points.shape[0], dtype=bool)
    px = points[:, 0]
    py = points[:, 1]
    count = int(polygon.shape[0])
    for index in range(count):
        a = polygon[index]
        b = polygon[(index + 1) % count]
        edge = b - a
        edge_len2 = float(edge @ edge)
        if edge_len2 <= 1e-24:
            continue
        rel = points - a
        t = np.clip((rel @ edge) / edge_len2, 0.0, 1.0)
        closest = a + t[:, None] * edge
        delta = points - closest
        d2 = np.minimum(d2, np.sum(delta * delta, axis=1))

        ay = float(a[1])
        by = float(b[1])
        crosses = (ay > py) != (by > py)
        with np.errstate(divide="ignore", invalid="ignore"):
            x_at_y = float(a[0]) + (py - ay) * (float(b[0]) - float(a[0])) / (by - ay)
        inside ^= crosses & (px < x_at_y)
    distance = np.sqrt(np.maximum(d2, 0.0))
    return np.where(inside, -distance, distance)


def _polygon_area_2d(polygon: np.ndarray) -> float:
    if polygon.ndim != 2 or polygon.shape[1] != 2 or polygon.shape[0] < 3:
        return 0.0
    shifted = np.roll(polygon, -1, axis=0)
    return 0.5 * float(np.sum(polygon[:, 0] * shifted[:, 1] - shifted[:, 0] * polygon[:, 1]))


def _profile_alignment_points(polygon: np.ndarray) -> np.ndarray:
    centered = polygon - np.mean(polygon, axis=0)
    scale = float(np.max(np.linalg.norm(centered, axis=1)))
    if scale <= 1e-12 or not np.isfinite(scale):
        return centered
    return centered / scale


def _aligned_loft_profiles(
    profile_start: np.ndarray,
    profile_end: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return profile pair with matching winding and best cyclic start."""
    if profile_start.shape != profile_end.shape or profile_start.shape[0] < 3:
        return profile_start, profile_end
    start = np.asarray(profile_start, dtype=np.float64)
    end = np.asarray(profile_end, dtype=np.float64)
    start_area = _polygon_area_2d(start)
    end_area = _polygon_area_2d(end)
    if start_area * end_area < 0.0:
        end = end[::-1].copy()
    normalized_start = _profile_alignment_points(start)
    normalized_end = _profile_alignment_points(end)
    best_shift = 0
    best_score = float("inf")
    for shift in range(end.shape[0]):
        rolled = np.roll(normalized_end, shift, axis=0)
        score = float(np.sum((normalized_start - rolled) ** 2))
        if score < best_score:
            best_score = score
            best_shift = shift
    return start, np.roll(end, best_shift, axis=0)


def _signed_distance_lerped_polygon_2d(
    points: np.ndarray,
    profile_start: np.ndarray,
    profile_end: np.ndarray,
    t: np.ndarray,
) -> np.ndarray:
    """Vectorized signed distance to a per-sample interpolated polygon."""
    if (
        profile_start.ndim != 2
        or profile_end.ndim != 2
        or profile_start.shape != profile_end.shape
        or profile_start.shape[1] != 2
        or profile_start.shape[0] < 3
    ):
        raise ValueError("Lofted profiles must have matching 2D point counts")
    profile_start, profile_end = _aligned_loft_profiles(profile_start, profile_end)
    d2 = np.full(points.shape[0], np.inf, dtype=np.float64)
    inside = np.zeros(points.shape[0], dtype=bool)
    px = points[:, 0]
    py = points[:, 1]
    t2 = t[:, None]
    count = int(profile_start.shape[0])
    for index in range(count):
        a0 = profile_start[index]
        b0 = profile_start[(index + 1) % count]
        a1 = profile_end[index]
        b1 = profile_end[(index + 1) % count]
        a = a0 * (1.0 - t2) + a1 * t2
        b = b0 * (1.0 - t2) + b1 * t2
        edge = b - a
        edge_len2 = np.einsum("ij,ij->i", edge, edge)
        safe_len2 = np.maximum(edge_len2, 1e-24)
        rel = points - a
        u = np.clip(np.einsum("ij,ij->i", rel, edge) / safe_len2, 0.0, 1.0)
        closest = a + u[:, None] * edge
        delta = points - closest
        d2 = np.minimum(d2, np.einsum("ij,ij->i", delta, delta))

        ay = a[:, 1]
        by = b[:, 1]
        ax = a[:, 0]
        bx = b[:, 0]
        crosses = (ay > py) != (by > py)
        with np.errstate(divide="ignore", invalid="ignore"):
            x_at_y = ax + (py - ay) * (bx - ax) / (by - ay)
        inside ^= crosses & (px < x_at_y)
    distance = np.sqrt(np.maximum(d2, 0.0))
    return np.where(inside, -distance, distance)


@dataclass
class ExtrudedPolygon(SDFExpr):
    """Extrude an arbitrary closed 2D profile into a finite prism."""

    profile_points: tuple[tuple[float, float], ...] = (
        (-0.5, -0.5),
        (0.5, -0.5),
        (0.5, 0.5),
        (-0.5, 0.5),
    )
    depth: float = 0.2
    axis_u: str = "x"
    axis_v: str = "y"
    normal_axis: str = "z"

    def distance(self, p: Any) -> np.ndarray:
        pts = _as_points(p)
        axes = {"x": 0, "y": 1, "z": 2}
        axis_u = axes.get(str(self.axis_u).lower())
        axis_v = axes.get(str(self.axis_v).lower())
        normal_axis = axes.get(str(self.normal_axis).lower())
        if axis_u is None or axis_v is None or normal_axis is None:
            raise ValueError("ExtrudedPolygon axes must be x|y|z")
        if len({axis_u, axis_v, normal_axis}) != 3:
            raise ValueError("ExtrudedPolygon axis_u, axis_v, and normal_axis must be distinct")
        polygon = np.asarray(self.profile_points, dtype=np.float64)
        plane_points = pts[:, [axis_u, axis_v]]
        d2 = _signed_distance_polygon_2d(plane_points, polygon)
        dn = np.abs(pts[:, normal_axis]) - 0.5 * float(self.depth)
        outside = np.sqrt(np.maximum(d2, 0.0) ** 2 + np.maximum(dn, 0.0) ** 2)
        inside = np.minimum(np.maximum(d2, dn), 0.0)
        d = outside + inside
        return _scalar_or_array(d, np.asarray(p).ndim == 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": "extruded_polygon",
            "profile_points": [
                [float(point[0]), float(point[1])] for point in self.profile_points
            ],
            "depth": float(self.depth),
            "axis_u": str(self.axis_u),
            "axis_v": str(self.axis_v),
            "normal_axis": str(self.normal_axis),
        }


@dataclass
class RevolvedProfile(SDFExpr):
    """Revolve a closed radius/axis profile around a principal axis."""

    profile_points: tuple[tuple[float, float], ...] = (
        (0.0, -0.5),
        (0.5, -0.5),
        (0.5, 0.5),
        (0.0, 0.5),
    )
    axis: str = "y"
    revolve_degrees: float | None = None
    start_degrees: float = 0.0

    def distance(self, p: Any) -> np.ndarray:
        pts = _as_points(p)
        axis_index, plane_axes = _axis_indices(str(self.axis))
        plane = pts[:, list(plane_axes)]
        radial = np.linalg.norm(plane, axis=1)
        axial = pts[:, axis_index]
        profile_points = np.asarray(self.profile_points, dtype=np.float64)
        d = _signed_distance_polygon_2d(np.stack([radial, axial], axis=1), profile_points)
        if self.revolve_degrees is not None and float(self.revolve_degrees) < 360.0:
            sweep = max(min(math.radians(float(self.revolve_degrees)), math.tau), 0.0)
            if sweep <= 1e-12:
                raise ValueError("RevolvedProfile revolve_degrees must be > 0")
            start = math.radians(float(self.start_degrees))
            angle = np.mod(np.arctan2(plane[:, 1], plane[:, 0]) - start, math.tau)
            inside_sector = angle <= sweep
            start_ray = np.asarray([math.cos(start), math.sin(start)], dtype=np.float64)
            end = start + sweep
            end_ray = np.asarray([math.cos(end), math.sin(end)], dtype=np.float64)
            dist_start = np.abs(start_ray[0] * plane[:, 1] - start_ray[1] * plane[:, 0])
            dist_end = np.abs(end_ray[0] * plane[:, 1] - end_ray[1] * plane[:, 0])
            cap_distance = np.minimum(dist_start, dist_end)
            wedge = np.where(inside_sector, -cap_distance, cap_distance)
            d = np.maximum(d, wedge)
        return _scalar_or_array(d, np.asarray(p).ndim == 1)

    def to_dict(self) -> dict[str, Any]:
        result = {
            "op": "revolved_profile",
            "profile_points": [
                [float(point[0]), float(point[1])] for point in self.profile_points
            ],
            "axis": str(self.axis),
        }
        if self.revolve_degrees is not None:
            result["revolve_degrees"] = float(self.revolve_degrees)
            result["start_degrees"] = float(self.start_degrees)
        return result


@dataclass
class Cone(SDFExpr):
    """Capped cone SDF — IQ ``sdCone`` (capped variant).

    Axis +Y. ``radius`` is the base radius; tip is at ``+y = half_height``.
    """

    radius: float = 0.5
    half_height: float = 0.5

    def distance(self, p: Any) -> np.ndarray:
        pts = _as_points(p)
        h = float(self.half_height) * 2.0
        r = float(self.radius)
        # Reframe so base is at y=0, tip at y=h
        py = pts[:, 1] + float(self.half_height)
        radial = np.linalg.norm(pts[:, [0, 2]], axis=1)
        # IQ "sdCone" capped variant
        q = np.stack([radial, py], axis=1)
        np.array([0.0, h], dtype=np.float64)
        base_to_tip = np.array([r, h], dtype=np.float64)
        # distance to the cone's slant edge
        slant_t = np.clip((q @ base_to_tip) / (base_to_tip @ base_to_tip), 0.0, 1.0)
        a = q - slant_t[:, None] * base_to_tip
        b = q - np.array([r, 0.0]) * np.stack(
            [np.clip(q[:, 0] / r, 0.0, 1.0), np.zeros(q.shape[0])], axis=1
        )
        k = np.sign(base_to_tip[1])
        d_min = np.minimum(np.sum(a * a, axis=1), np.sum(b * b, axis=1))
        s_a = k * (q[:, 0] * base_to_tip[1] - q[:, 1] * base_to_tip[0])
        s_b = k * (q[:, 1] - h)
        s = np.maximum(s_a, s_b)
        d = np.sqrt(d_min) * np.where(s < 0.0, -1.0, 1.0)
        return _scalar_or_array(d, np.asarray(p).ndim == 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": "cone",
            "radius": float(self.radius),
            "half_height": float(self.half_height),
        }


@dataclass
class HexPrism(SDFExpr):
    """Hexagonal prism SDF — IQ ``sdHexPrism``.

    Hex axis +Y, hex face in XZ plane.
    """

    radius: float = 0.4
    half_height: float = 0.3

    def distance(self, p: Any) -> np.ndarray:
        pts = _as_points(p)
        # k = vec3(-sqrt(3)/2, 0.5, 0.5/sqrt(3))
        k = np.array([-0.8660254037844387, 0.5, 0.5773502691896257])
        ax = np.abs(pts)
        # Reflect across hex symmetry: ax.xz -= 2 * min(dot(k.xy, ax.xz), 0) * k.xy
        dot_xz = ax[:, 0] * k[0] + ax[:, 2] * k[1]
        adj = 2.0 * np.minimum(dot_xz, 0.0)
        ax[:, 0] = ax[:, 0] - adj * k[0]
        ax[:, 2] = ax[:, 2] - adj * k[1]
        # 2D distance in (x, z) restricted to a clamped segment
        d_xz_x = ax[:, 0] - np.clip(ax[:, 0], -k[2] * float(self.radius), k[2] * float(self.radius))
        d_xz_z = ax[:, 2] - float(self.radius)
        outside_xy = np.sqrt(d_xz_x * d_xz_x + d_xz_z * d_xz_z) * np.sign(d_xz_z)
        d_y = ax[:, 1] - float(self.half_height)
        outside = np.sqrt(np.maximum(outside_xy, 0.0) ** 2 + np.maximum(d_y, 0.0) ** 2)
        inside = np.minimum(np.maximum(outside_xy, d_y), 0.0)
        d = outside + inside
        return _scalar_or_array(d, np.asarray(p).ndim == 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": "hex_prism",
            "radius": float(self.radius),
            "half_height": float(self.half_height),
        }


@dataclass
class Ellipsoid(SDFExpr):
    """Ellipsoid SDF — IQ approximation ``sdEllipsoid``.

    Not a true Euclidean SDF (it is an inexact bound) — IQ uses
    ``k0 * (k0 - 1) / k1`` with ``k0 = length(p / r)``,
    ``k1 = length(p / (r*r))``. Sufficient for marching cubes.
    """

    half_extents: tuple[float, float, float] = (0.5, 0.3, 0.3)

    def distance(self, p: Any) -> np.ndarray:
        pts = _as_points(p)
        r = np.asarray(self.half_extents, dtype=np.float64)
        if np.any(r <= 0.0):
            raise ValueError("Ellipsoid half_extents must be positive")
        k0 = np.linalg.norm(pts / r, axis=1)
        k1 = np.linalg.norm(pts / (r * r), axis=1)
        d = np.where(k1 > 0.0, k0 * (k0 - 1.0) / np.maximum(k1, 1e-12), -np.min(r))
        return _scalar_or_array(d, np.asarray(p).ndim == 1)

    def to_dict(self) -> dict[str, Any]:
        return {"op": "ellipsoid", "half_extents": list(self.half_extents)}


# ---------------------------------------------------------------------------
# Hard boolean ops
# ---------------------------------------------------------------------------


@dataclass
class Union(SDFExpr):
    """Hard union: ``min(a, b)``."""

    a: SDFExpr
    b: SDFExpr

    def distance(self, p: Any) -> np.ndarray:
        da = self.a.distance(p)
        db = self.b.distance(p)
        return np.minimum(da, db)

    def to_dict(self) -> dict[str, Any]:
        return {"op": "union", "a": self.a.to_dict(), "b": self.b.to_dict()}


@dataclass
class Intersect(SDFExpr):
    """Hard intersection: ``max(a, b)``."""

    a: SDFExpr
    b: SDFExpr

    def distance(self, p: Any) -> np.ndarray:
        da = self.a.distance(p)
        db = self.b.distance(p)
        return np.maximum(da, db)

    def to_dict(self) -> dict[str, Any]:
        return {"op": "intersect", "a": self.a.to_dict(), "b": self.b.to_dict()}


@dataclass
class Subtract(SDFExpr):
    """Hard subtraction: ``max(a, -b)`` — A minus B."""

    a: SDFExpr
    b: SDFExpr

    def distance(self, p: Any) -> np.ndarray:
        da = self.a.distance(p)
        db = self.b.distance(p)
        return np.maximum(da, -db)

    def to_dict(self) -> dict[str, Any]:
        return {"op": "subtract", "a": self.a.to_dict(), "b": self.b.to_dict()}


def _chamfer_union(da: np.ndarray, db: np.ndarray, radius: float) -> np.ndarray:
    if radius <= 0.0:
        return np.minimum(da, db)
    return np.minimum(np.minimum(da, db), (da - radius + db) * math.sqrt(0.5))


def _chamfer_intersect(da: np.ndarray, db: np.ndarray, radius: float) -> np.ndarray:
    if radius <= 0.0:
        return np.maximum(da, db)
    return np.maximum(np.maximum(da, db), (da + radius + db) * math.sqrt(0.5))


@dataclass
class ChamferUnion(SDFExpr):
    """Hard-surface chamfered union between two SDFs."""

    a: SDFExpr
    b: SDFExpr
    radius: float = 0.1

    def distance(self, p: Any) -> np.ndarray:
        return _chamfer_union(self.a.distance(p), self.b.distance(p), float(self.radius))

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": "chamfer_union",
            "a": self.a.to_dict(),
            "b": self.b.to_dict(),
            "radius": float(self.radius),
        }


@dataclass
class ChamferIntersect(SDFExpr):
    """Hard-surface chamfered intersection between two SDFs."""

    a: SDFExpr
    b: SDFExpr
    radius: float = 0.1

    def distance(self, p: Any) -> np.ndarray:
        return _chamfer_intersect(self.a.distance(p), self.b.distance(p), float(self.radius))

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": "chamfer_intersect",
            "a": self.a.to_dict(),
            "b": self.b.to_dict(),
            "radius": float(self.radius),
        }


@dataclass
class ChamferSubtract(SDFExpr):
    """Hard-surface chamfered A-minus-B cut."""

    a: SDFExpr
    b: SDFExpr
    radius: float = 0.1

    def distance(self, p: Any) -> np.ndarray:
        da = self.a.distance(p)
        db = self.b.distance(p)
        return _chamfer_intersect(da, -db, float(self.radius))

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": "chamfer_subtract",
            "a": self.a.to_dict(),
            "b": self.b.to_dict(),
            "radius": float(self.radius),
        }


# ---------------------------------------------------------------------------
# Smooth boolean ops — IQ canonical polynomial smooth-min/max
# ---------------------------------------------------------------------------


def _smooth_min(da: np.ndarray, db: np.ndarray, k: float) -> np.ndarray:
    """IQ ``opSmoothUnion`` polynomial smoothing.

    ``h = clamp(0.5 + 0.5 * (db - da) / k, 0, 1)``;
    ``return mix(db, da, h) - k * h * (1 - h)``.
    """
    if k <= 0.0:
        return np.minimum(da, db)
    h = np.clip(0.5 + 0.5 * (db - da) / k, 0.0, 1.0)
    return db * (1.0 - h) + da * h - k * h * (1.0 - h)


def _smooth_max(da: np.ndarray, db: np.ndarray, k: float) -> np.ndarray:
    """IQ ``opSmoothIntersection`` polynomial smoothing."""
    if k <= 0.0:
        return np.maximum(da, db)
    h = np.clip(0.5 - 0.5 * (db - da) / k, 0.0, 1.0)
    return db * (1.0 - h) + da * h + k * h * (1.0 - h)


@dataclass
class SmoothUnion(SDFExpr):
    """IQ ``opSmoothUnion`` — organic blend with radius ``k``."""

    a: SDFExpr
    b: SDFExpr
    k: float = 0.1

    def distance(self, p: Any) -> np.ndarray:
        return _smooth_min(self.a.distance(p), self.b.distance(p), float(self.k))

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": "smooth_union",
            "a": self.a.to_dict(),
            "b": self.b.to_dict(),
            "k": float(self.k),
        }


@dataclass
class SmoothIntersect(SDFExpr):
    """IQ ``opSmoothIntersection`` — softened max."""

    a: SDFExpr
    b: SDFExpr
    k: float = 0.1

    def distance(self, p: Any) -> np.ndarray:
        return _smooth_max(self.a.distance(p), self.b.distance(p), float(self.k))

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": "smooth_intersect",
            "a": self.a.to_dict(),
            "b": self.b.to_dict(),
            "k": float(self.k),
        }


@dataclass
class SmoothSubtract(SDFExpr):
    """IQ ``opSmoothSubtraction`` — softened A minus B."""

    a: SDFExpr
    b: SDFExpr
    k: float = 0.1

    def distance(self, p: Any) -> np.ndarray:
        da = self.a.distance(p)
        db = self.b.distance(p)
        return _smooth_max(da, -db, float(self.k))

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": "smooth_subtract",
            "a": self.a.to_dict(),
            "b": self.b.to_dict(),
            "k": float(self.k),
        }


# ---------------------------------------------------------------------------
# Spatial modifiers — transform the query point before child evaluation.
# ---------------------------------------------------------------------------


@dataclass
class Translate(SDFExpr):
    """Translate the modeling space by ``offset`` (subtract from query)."""

    expr: SDFExpr
    offset: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def distance(self, p: Any) -> np.ndarray:
        pts = _as_points(p)
        off = np.asarray(self.offset, dtype=np.float64)
        d = self.expr.distance(pts - off)
        return _scalar_or_array(np.atleast_1d(d), np.asarray(p).ndim == 1)

    def to_dict(self) -> dict[str, Any]:
        return {"op": "translate", "offset": list(self.offset), "expr": self.expr.to_dict()}


def _rotation_matrix(axis: tuple[float, float, float], angle_rad: float) -> np.ndarray:
    """Rodrigues rotation matrix for a unit axis."""
    a = np.asarray(axis, dtype=np.float64)
    n = np.linalg.norm(a)
    if n < 1e-12:
        raise ValueError("Rotation axis must be non-zero")
    a = a / n
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    x, y, z = float(a[0]), float(a[1]), float(a[2])
    return np.array(
        [
            [c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
            [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
            [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)],
        ],
        dtype=np.float64,
    )


@dataclass
class Rotate(SDFExpr):
    """Rotate modeling space around ``axis`` by ``angle`` radians.

    Inverse-rotates the query points before delegating to ``expr``.
    """

    expr: SDFExpr
    axis: tuple[float, float, float] = (0.0, 1.0, 0.0)
    angle: float = 0.0

    def distance(self, p: Any) -> np.ndarray:
        pts = _as_points(p)
        # Inverse rotation = rotation by -angle = transpose for orthonormal R
        r_inv = _rotation_matrix(self.axis, -float(self.angle))
        d = self.expr.distance(pts @ r_inv.T)
        return _scalar_or_array(np.atleast_1d(d), np.asarray(p).ndim == 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": "rotate",
            "axis": list(self.axis),
            "angle": float(self.angle),
            "expr": self.expr.to_dict(),
        }


@dataclass
class Scale(SDFExpr):
    """Uniform scale modeling space by ``factor``.

    Distances are multiplied by ``factor`` after the inverse-scaled query
    so the result remains a valid SDF (Lipschitz preserved).
    """

    expr: SDFExpr
    factor: float = 1.0

    def distance(self, p: Any) -> np.ndarray:
        pts = _as_points(p)
        f = float(self.factor)
        if f <= 0.0:
            raise ValueError("Scale factor must be positive")
        d = self.expr.distance(pts / f) * f
        return _scalar_or_array(np.atleast_1d(d), np.asarray(p).ndim == 1)

    def to_dict(self) -> dict[str, Any]:
        return {"op": "scale", "factor": float(self.factor), "expr": self.expr.to_dict()}


@dataclass
class Scale3(SDFExpr):
    """Non-uniform scale modeling space by per-axis factors.

    The zero isosurface is exact. Distances use the minimum absolute
    factor as a conservative scale so extraction keeps a coherent sign
    field under anisotropic transforms.
    """

    expr: SDFExpr
    factors: tuple[float, float, float] = (1.0, 1.0, 1.0)

    def distance(self, p: Any) -> np.ndarray:
        pts = _as_points(p)
        factors = np.asarray(self.factors, dtype=np.float64)
        if np.any(factors <= 0.0):
            raise ValueError("Scale3 factors must be positive")
        d = self.expr.distance(pts / factors) * float(np.min(factors))
        return _scalar_or_array(np.atleast_1d(d), np.asarray(p).ndim == 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": "scale3",
            "factors": [float(value) for value in self.factors],
            "expr": self.expr.to_dict(),
        }


@dataclass
class Twist(SDFExpr):
    """Twist modeling space around an axis.

    ``radians_per_cm`` controls twist rate along the axis. The zero
    isosurface is exact for the inverse domain transform; distance is a
    coherent signed field suitable for extraction.
    """

    expr: SDFExpr
    axis: str = "y"
    radians_per_cm: float = 0.0
    angle_offset: float = 0.0

    def distance(self, p: Any) -> np.ndarray:
        pts = _as_points(p)
        axial_index, plane_axes = _axis_indices(self.axis)
        theta = -(float(self.radians_per_cm) * pts[:, axial_index] + float(self.angle_offset))
        c = np.cos(theta)
        s = np.sin(theta)
        transformed = pts.copy()
        u = pts[:, plane_axes[0]]
        v = pts[:, plane_axes[1]]
        transformed[:, plane_axes[0]] = c * u - s * v
        transformed[:, plane_axes[1]] = s * u + c * v
        d = self.expr.distance(transformed)
        return _scalar_or_array(np.atleast_1d(d), np.asarray(p).ndim == 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": "twist",
            "axis": str(self.axis),
            "radians_per_cm": float(self.radians_per_cm),
            "angle_offset": float(self.angle_offset),
            "expr": self.expr.to_dict(),
        }


@dataclass
class Bend(SDFExpr):
    """Cheap domain bend in a plane containing the length axis."""

    expr: SDFExpr
    axis: str = "x"
    bend_axis: str = "y"
    radians_per_cm: float = 0.0
    angle_offset: float = 0.0

    def distance(self, p: Any) -> np.ndarray:
        pts = _as_points(p)
        axes = {"x": 0, "y": 1, "z": 2}
        axis_index = axes.get(str(self.axis).lower())
        bend_index = axes.get(str(self.bend_axis).lower())
        if axis_index is None or bend_index is None or axis_index == bend_index:
            raise ValueError("Bend axis and bend_axis must be different x|y|z axes")
        theta = -(float(self.radians_per_cm) * pts[:, axis_index] + float(self.angle_offset))
        c = np.cos(theta)
        s = np.sin(theta)
        transformed = pts.copy()
        u = pts[:, axis_index]
        v = pts[:, bend_index]
        transformed[:, axis_index] = c * u - s * v
        transformed[:, bend_index] = s * u + c * v
        d = self.expr.distance(transformed)
        return _scalar_or_array(np.atleast_1d(d), np.asarray(p).ndim == 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": "bend",
            "axis": str(self.axis),
            "bend_axis": str(self.bend_axis),
            "radians_per_cm": float(self.radians_per_cm),
            "angle_offset": float(self.angle_offset),
            "expr": self.expr.to_dict(),
        }


@dataclass
class Taper(SDFExpr):
    """Linearly taper modeling space along an axis."""

    expr: SDFExpr
    axis: str = "y"
    start_scale: float = 1.0
    end_scale: float = 0.5
    height: float = 1.0

    def distance(self, p: Any) -> np.ndarray:
        pts = _as_points(p)
        if self.height <= 0.0:
            raise ValueError("Taper height must be positive")
        start = float(self.start_scale)
        end = float(self.end_scale)
        if start <= 0.0 or end <= 0.0:
            raise ValueError("Taper scales must be positive")
        axial_index, plane_axes = _axis_indices(self.axis)
        t = np.clip(pts[:, axial_index] / float(self.height) + 0.5, 0.0, 1.0)
        scale = start + (end - start) * t
        transformed = pts.copy()
        transformed[:, plane_axes[0]] = transformed[:, plane_axes[0]] / scale
        transformed[:, plane_axes[1]] = transformed[:, plane_axes[1]] / scale
        d = self.expr.distance(transformed) * min(start, end)
        return _scalar_or_array(np.atleast_1d(d), np.asarray(p).ndim == 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": "taper",
            "axis": str(self.axis),
            "start_scale": float(self.start_scale),
            "end_scale": float(self.end_scale),
            "height": float(self.height),
            "expr": self.expr.to_dict(),
        }


@dataclass
class Mirror(SDFExpr):
    """Mirror modeling space across the plane normal to ``axis``.

    Replaces the absolute value of the chosen component before query.
    Equivalent to IQ's ``opSymX/Y/Z``.
    """

    expr: SDFExpr
    axis: str = "x"

    def distance(self, p: Any) -> np.ndarray:
        pts = _as_points(p).copy()
        idx = {"x": 0, "y": 1, "z": 2}.get(self.axis.lower())
        if idx is None:
            raise ValueError(f"Mirror axis must be x|y|z, got {self.axis!r}")
        pts[:, idx] = np.abs(pts[:, idx])
        d = self.expr.distance(pts)
        return _scalar_or_array(np.atleast_1d(d), np.asarray(p).ndim == 1)

    def to_dict(self) -> dict[str, Any]:
        return {"op": "mirror", "axis": self.axis, "expr": self.expr.to_dict()}


@dataclass
class Repeat(SDFExpr):
    """Finite domain repetition along ``axis`` — IQ ``opRepLim``.

    Tiles ``expr`` ``count`` times spaced by ``period`` along ``axis``,
    centered on the origin. The repetition is clamped so only ``count``
    instances exist (not the infinite ``opRep``).
    """

    expr: SDFExpr
    axis: str = "x"
    count: int = 3
    period: float = 1.0

    def distance(self, p: Any) -> np.ndarray:
        pts = _as_points(p).copy()
        idx = {"x": 0, "y": 1, "z": 2}.get(self.axis.lower())
        if idx is None:
            raise ValueError(f"Repeat axis must be x|y|z, got {self.axis!r}")
        c = max(int(self.count), 1)
        s = float(self.period)
        if s <= 0.0:
            raise ValueError("Repeat period must be positive")
        col = pts[:, idx]
        # Finite centered repeat: choose the nearest center from exactly
        # ``count`` allowed cells. This keeps even counts from gaining an
        # unintended center instance at the origin.
        center_offset = (c - 1) * 0.5
        nearest = np.clip(np.rint((col / s) + center_offset), 0, c - 1)
        centers = (nearest - center_offset) * s
        pts[:, idx] = col - centers
        d = self.expr.distance(pts)
        return _scalar_or_array(np.atleast_1d(d), np.asarray(p).ndim == 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": "repeat",
            "axis": self.axis,
            "count": int(self.count),
            "period": float(self.period),
            "expr": self.expr.to_dict(),
        }


@dataclass
class Offset(SDFExpr):
    """Constant SDF offset.

    Positive ``amount`` grows the enclosed solid; negative values shrink it.
    This is the implicit equivalent of dilation/erosion and is useful for
    clearance, padding, stylized swelling, and authoring extraction offsets
    without changing the final iso value.
    """

    expr: SDFExpr
    amount: float = 0.0

    def distance(self, p: Any) -> np.ndarray:
        d = np.atleast_1d(self.expr.distance(p))
        return _scalar_or_array(d - float(self.amount), np.asarray(p).ndim == 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": "offset",
            "amount": float(self.amount),
            "expr": self.expr.to_dict(),
        }


@dataclass
class Shell(SDFExpr):
    """Turn an SDF surface into a finite-thickness shell.

    ``thickness`` is the total wall thickness around the source iso-surface:
    the shell occupies approximately ``thickness / 2`` on either side of the
    original surface.
    """

    expr: SDFExpr
    thickness: float = 0.1

    def distance(self, p: Any) -> np.ndarray:
        d = np.atleast_1d(self.expr.distance(p))
        half_thickness = float(self.thickness) * 0.5
        return _scalar_or_array(np.abs(d) - half_thickness, np.asarray(p).ndim == 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": "shell",
            "thickness": float(self.thickness),
            "expr": self.expr.to_dict(),
        }


# Type alias for noise/displacement callables used by Displace/Warp.
NoiseField = Callable[[np.ndarray], np.ndarray]
VectorField = Callable[[np.ndarray], np.ndarray]


@dataclass
class Displace(SDFExpr):
    """Surface displacement — adds ``amplitude * noise(p)`` to the SDF.

    The result is no longer an exact SDF (Lipschitz can be broken) but
    is a faithful implicit surface for marching-cubes extraction. Use a
    bounded noise field (sin-product, value, simplex) and keep
    ``amplitude`` smaller than the local feature size.
    """

    expr: SDFExpr
    noise: NoiseField | None = None
    amplitude: float = 0.05

    def distance(self, p: Any) -> np.ndarray:
        pts = _as_points(p)
        d = np.atleast_1d(self.expr.distance(pts))
        if self.noise is not None and float(self.amplitude) != 0.0:
            n = np.asarray(self.noise(pts), dtype=np.float64).reshape(-1)
            d = d + float(self.amplitude) * n
        return _scalar_or_array(d, np.asarray(p).ndim == 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": "displace",
            "amplitude": float(self.amplitude),
            "noise": getattr(self.noise, "__name__", "<callable>") if self.noise else None,
            "expr": self.expr.to_dict(),
        }


@dataclass
class Warp(SDFExpr):
    """Domain warping — pre-compose query points with ``vector_field``.

    ``q = p + vector_field(p)`` then evaluates ``expr.distance(q)``. As
    with :class:`Displace`, the result is an approximate SDF; keep the
    field smooth and bounded.
    """

    expr: SDFExpr
    vector_field: VectorField | None = None

    def distance(self, p: Any) -> np.ndarray:
        pts = _as_points(p)
        if self.vector_field is not None:
            v = np.asarray(self.vector_field(pts), dtype=np.float64)
            if v.shape != pts.shape:
                raise ValueError(f"Warp vector_field must return shape {pts.shape}, got {v.shape}")
            pts = pts + v
        d = np.atleast_1d(self.expr.distance(pts))
        return _scalar_or_array(d, np.asarray(p).ndim == 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": "warp",
            "vector_field": getattr(self.vector_field, "__name__", "<callable>")
            if self.vector_field
            else None,
            "expr": self.expr.to_dict(),
        }
