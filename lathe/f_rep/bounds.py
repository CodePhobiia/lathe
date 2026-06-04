"""Conservative AABB inference for bounded F-Rep/SDF expressions."""

from __future__ import annotations

from itertools import product

import numpy as np

from .expressions import (
    Bend,
    Box,
    Capsule,
    ChamferIntersect,
    ChamferSubtract,
    ChamferUnion,
    Cone,
    ConnectedIntent,
    Cylinder,
    Displace,
    Ellipsoid,
    ExtrudedPolygon,
    Frustum,
    HexPrism,
    Intersect,
    Mirror,
    Offset,
    Plane,
    Repeat,
    RevolvedProfile,
    Rotate,
    RoundedSlot,
    Scale,
    Scale3,
    SDFExpr,
    SegmentBox,
    SegmentCapsule,
    SegmentExtrudedProfile,
    SegmentLoftedProfile,
    Shell,
    SmoothIntersect,
    SmoothSubtract,
    SmoothUnion,
    Sphere,
    Subtract,
    Taper,
    TaperedSegmentCapsule,
    Torus,
    Translate,
    Twist,
    Union,
    Warp,
    _rotation_matrix,
)

Bounds = tuple[tuple[float, float, float], tuple[float, float, float]]


def estimate_bounds(expr: SDFExpr, *, padding: float = 0.0) -> Bounds | None:
    """Return conservative world-space bounds, or ``None`` if unbounded."""
    bounds = _estimate_bounds(expr)
    if bounds is None:
        return None
    amount = max(float(padding), 0.0)
    if amount <= 0.0:
        return bounds
    return _expand(bounds, amount)


def _estimate_bounds(expr: SDFExpr) -> Bounds | None:
    if isinstance(expr, Sphere):
        r = float(expr.radius)
        return ((-r, -r, -r), (r, r, r))
    if isinstance(expr, Box):
        hx, hy, hz = (float(value) for value in expr.half_extents)
        return ((-hx, -hy, -hz), (hx, hy, hz))
    if isinstance(expr, Cylinder):
        r = float(expr.radius)
        h = float(expr.height) * 0.5
        return ((-r, -h, -r), (r, h, r))
    if isinstance(expr, Frustum):
        r = max(float(expr.radius_bottom), float(expr.radius_top))
        h = float(expr.height) * 0.5
        return ((-r, -h, -r), (r, h, r))
    if isinstance(expr, Torus):
        r = float(expr.major_radius) + float(expr.minor_radius)
        tube = float(expr.minor_radius)
        return ((-r, -tube, -r), (r, tube, r))
    if isinstance(expr, Capsule):
        r = float(expr.radius)
        h = float(expr.half_height) + r
        return ((-r, -h, -r), (r, h, r))
    if isinstance(expr, SegmentCapsule):
        r = float(expr.radius)
        a = tuple(float(value) for value in expr.a)
        b = tuple(float(value) for value in expr.b)
        return (
            tuple(min(a[axis], b[axis]) - r for axis in range(3)),
            tuple(max(a[axis], b[axis]) + r for axis in range(3)),
        )
    if isinstance(expr, SegmentBox):
        r = float(np.hypot(float(expr.half_width), float(expr.half_depth)))
        a = tuple(float(value) for value in expr.a)
        b = tuple(float(value) for value in expr.b)
        return (
            tuple(min(a[axis], b[axis]) - r for axis in range(3)),
            tuple(max(a[axis], b[axis]) + r for axis in range(3)),
        )
    if isinstance(expr, SegmentExtrudedProfile):
        points = np.asarray(expr.profile_points, dtype=np.float64)
        if points.ndim != 2 or points.shape[1] != 2 or points.shape[0] < 3:
            return None
        max_scale = max(float(expr.start_scale), float(expr.end_scale))
        if max_scale <= 0.0:
            return None
        r = float(np.max(np.linalg.norm(points, axis=1))) * max_scale
        a = tuple(float(value) for value in expr.a)
        b = tuple(float(value) for value in expr.b)
        return (
            tuple(min(a[axis], b[axis]) - r for axis in range(3)),
            tuple(max(a[axis], b[axis]) + r for axis in range(3)),
        )
    if isinstance(expr, SegmentLoftedProfile):
        start = np.asarray(expr.profile_start, dtype=np.float64)
        end = np.asarray(expr.profile_end, dtype=np.float64)
        if (
            start.ndim != 2
            or end.ndim != 2
            or start.shape != end.shape
            or start.shape[1] != 2
            or start.shape[0] < 3
        ):
            return None
        r = float(max(np.max(np.linalg.norm(start, axis=1)), np.max(np.linalg.norm(end, axis=1))))
        a = tuple(float(value) for value in expr.a)
        b = tuple(float(value) for value in expr.b)
        return (
            tuple(min(a[axis], b[axis]) - r for axis in range(3)),
            tuple(max(a[axis], b[axis]) + r for axis in range(3)),
        )
    if isinstance(expr, TaperedSegmentCapsule):
        r = max(float(expr.radius_start), float(expr.radius_end))
        a = tuple(float(value) for value in expr.a)
        b = tuple(float(value) for value in expr.b)
        return (
            tuple(min(a[axis], b[axis]) - r for axis in range(3)),
            tuple(max(a[axis], b[axis]) + r for axis in range(3)),
        )
    if isinstance(expr, RoundedSlot):
        axes = {"x": 0, "y": 1, "z": 2}
        slot_axis = axes.get(str(expr.axis).lower())
        normal_axis = axes.get(str(expr.normal_axis).lower())
        if slot_axis is None or normal_axis is None or slot_axis == normal_axis:
            return None
        side_axis = next(axis for axis in range(3) if axis not in {slot_axis, normal_axis})
        half = [0.0, 0.0, 0.0]
        half[slot_axis] = float(expr.length) * 0.5
        half[side_axis] = float(expr.radius)
        half[normal_axis] = float(expr.depth) * 0.5
        return (
            tuple(-float(value) for value in half),
            tuple(float(value) for value in half),
        )
    if isinstance(expr, ExtrudedPolygon):
        axes = {"x": 0, "y": 1, "z": 2}
        axis_u = axes.get(str(expr.axis_u).lower())
        axis_v = axes.get(str(expr.axis_v).lower())
        normal_axis = axes.get(str(expr.normal_axis).lower())
        if axis_u is None or axis_v is None or normal_axis is None:
            return None
        if len({axis_u, axis_v, normal_axis}) != 3:
            return None
        points = np.asarray(expr.profile_points, dtype=np.float64)
        if points.ndim != 2 or points.shape[1] != 2 or points.shape[0] < 3:
            return None
        lo = [0.0, 0.0, 0.0]
        hi = [0.0, 0.0, 0.0]
        lo[axis_u] = float(np.min(points[:, 0]))
        hi[axis_u] = float(np.max(points[:, 0]))
        lo[axis_v] = float(np.min(points[:, 1]))
        hi[axis_v] = float(np.max(points[:, 1]))
        lo[normal_axis] = -0.5 * float(expr.depth)
        hi[normal_axis] = 0.5 * float(expr.depth)
        return (tuple(lo), tuple(hi))
    if isinstance(expr, RevolvedProfile):
        axis = {"x": 0, "y": 1, "z": 2}.get(str(expr.axis).lower())
        if axis is None:
            return None
        points = np.asarray(expr.profile_points, dtype=np.float64)
        if points.ndim != 2 or points.shape[1] != 2 or points.shape[0] < 3:
            return None
        max_radius = float(np.max(points[:, 0]))
        if max_radius < 0.0:
            return None
        lo = [-max_radius, -max_radius, -max_radius]
        hi = [max_radius, max_radius, max_radius]
        lo[axis] = float(np.min(points[:, 1]))
        hi[axis] = float(np.max(points[:, 1]))
        return (tuple(lo), tuple(hi))
    if isinstance(expr, Cone):
        r = float(expr.radius)
        h = float(expr.half_height)
        return ((-r, -h, -r), (r, h, r))
    if isinstance(expr, HexPrism):
        r = float(expr.radius)
        h = float(expr.half_height)
        return ((-r, -h, -r), (r, h, r))
    if isinstance(expr, Ellipsoid):
        hx, hy, hz = (float(value) for value in expr.half_extents)
        return ((-hx, -hy, -hz), (hx, hy, hz))
    if isinstance(expr, Plane):
        return None
    if isinstance(expr, ConnectedIntent):
        return _estimate_bounds(expr.expr)
    if isinstance(expr, Translate):
        child = _estimate_bounds(expr.expr)
        if child is None:
            return None
        ox, oy, oz = (float(value) for value in expr.offset)
        return (
            (child[0][0] + ox, child[0][1] + oy, child[0][2] + oz),
            (child[1][0] + ox, child[1][1] + oy, child[1][2] + oz),
        )
    if isinstance(expr, Scale):
        child = _estimate_bounds(expr.expr)
        if child is None:
            return None
        factor = abs(float(expr.factor))
        return (
            tuple(float(value) * factor for value in child[0]),
            tuple(float(value) * factor for value in child[1]),
        )
    if isinstance(expr, Scale3):
        child = _estimate_bounds(expr.expr)
        if child is None:
            return None
        factors = tuple(abs(float(value)) for value in expr.factors)
        lo = tuple(float(child[0][axis]) * factors[axis] for axis in range(3))
        hi = tuple(float(child[1][axis]) * factors[axis] for axis in range(3))
        return (
            tuple(min(lo[axis], hi[axis]) for axis in range(3)),
            tuple(max(lo[axis], hi[axis]) for axis in range(3)),
        )
    if isinstance(expr, Twist):
        child = _estimate_bounds(expr.expr)
        if child is None:
            return None
        axis = {"x": 0, "y": 1, "z": 2}.get(str(expr.axis).lower())
        if axis is None:
            return None
        plane_axes = tuple(index for index in range(3) if index != axis)
        radius = 0.0
        for u in (float(child[0][plane_axes[0]]), float(child[1][plane_axes[0]])):
            for v in (float(child[0][plane_axes[1]]), float(child[1][plane_axes[1]])):
                radius = max(radius, float(np.hypot(u, v)))
        lo = [0.0, 0.0, 0.0]
        hi = [0.0, 0.0, 0.0]
        lo[axis] = float(child[0][axis])
        hi[axis] = float(child[1][axis])
        for plane_axis in plane_axes:
            lo[plane_axis] = -radius
            hi[plane_axis] = radius
        return (tuple(lo), tuple(hi))
    if isinstance(expr, Bend):
        child = _estimate_bounds(expr.expr)
        if child is None:
            return None
        axes = {"x": 0, "y": 1, "z": 2}
        axis = axes.get(str(expr.axis).lower())
        bend_axis = axes.get(str(expr.bend_axis).lower())
        if axis is None or bend_axis is None or axis == bend_axis:
            return None
        fixed_axis = next(index for index in range(3) if index not in {axis, bend_axis})
        radius = 0.0
        for u in (float(child[0][axis]), float(child[1][axis])):
            for v in (float(child[0][bend_axis]), float(child[1][bend_axis])):
                radius = max(radius, float(np.hypot(u, v)))
        lo = [0.0, 0.0, 0.0]
        hi = [0.0, 0.0, 0.0]
        lo[axis] = -radius
        hi[axis] = radius
        lo[bend_axis] = -radius
        hi[bend_axis] = radius
        lo[fixed_axis] = float(child[0][fixed_axis])
        hi[fixed_axis] = float(child[1][fixed_axis])
        return (tuple(lo), tuple(hi))
    if isinstance(expr, Taper):
        child = _estimate_bounds(expr.expr)
        if child is None:
            return None
        axis = {"x": 0, "y": 1, "z": 2}.get(str(expr.axis).lower())
        if axis is None:
            return None
        max_scale = max(float(expr.start_scale), float(expr.end_scale))
        if max_scale <= 0.0:
            return None
        lo = list(child[0])
        hi = list(child[1])
        for plane_axis in range(3):
            if plane_axis == axis:
                continue
            values = (
                float(child[0][plane_axis]) * max_scale,
                float(child[1][plane_axis]) * max_scale,
            )
            lo[plane_axis] = min(values)
            hi[plane_axis] = max(values)
        return (tuple(float(value) for value in lo), tuple(float(value) for value in hi))
    if isinstance(expr, Rotate):
        child = _estimate_bounds(expr.expr)
        if child is None:
            return None
        matrix = _rotation_matrix(expr.axis, float(expr.angle))
        return _transform_bounds(child, matrix)
    if isinstance(expr, Mirror):
        child = _estimate_bounds(expr.expr)
        if child is None:
            return None
        axis = {"x": 0, "y": 1, "z": 2}.get(str(expr.axis).lower())
        if axis is None:
            return None
        lo = list(child[0])
        hi = list(child[1])
        reflected = (-hi[axis], -lo[axis])
        lo[axis] = min(lo[axis], reflected[0])
        hi[axis] = max(hi[axis], reflected[1])
        return (tuple(float(value) for value in lo), tuple(float(value) for value in hi))
    if isinstance(expr, Repeat):
        child = _estimate_bounds(expr.expr)
        if child is None:
            return None
        axis = {"x": 0, "y": 1, "z": 2}.get(str(expr.axis).lower())
        if axis is None:
            return None
        count = max(int(expr.count), 1)
        period = float(expr.period)
        if period <= 0.0:
            return None
        center_offset = (count - 1) * 0.5
        first_center = (0.0 - center_offset) * period
        last_center = (float(count - 1) - center_offset) * period
        lo = list(child[0])
        hi = list(child[1])
        lo[axis] = float(child[0][axis]) + min(first_center, last_center)
        hi[axis] = float(child[1][axis]) + max(first_center, last_center)
        return (tuple(float(value) for value in lo), tuple(float(value) for value in hi))
    if isinstance(expr, Offset):
        child = _estimate_bounds(expr.expr)
        if child is None:
            return None
        return _expand(child, abs(float(expr.amount)))
    if isinstance(expr, Shell):
        child = _estimate_bounds(expr.expr)
        if child is None:
            return None
        return _expand(child, max(float(expr.thickness), 0.0) * 0.5)
    if isinstance(expr, Displace):
        child = _estimate_bounds(expr.expr)
        if child is None:
            return None
        return _expand(child, abs(float(expr.amplitude)))
    if isinstance(expr, Warp):
        child = _estimate_bounds(expr.expr)
        if child is None:
            return None
        amplitude = float(getattr(expr.vector_field, "lathe_amplitude_cm", 0.0) or 0.0)
        return _expand(child, abs(amplitude))
    if isinstance(expr, (Union, SmoothUnion, ChamferUnion)):
        left = _estimate_bounds(expr.a)
        right = _estimate_bounds(expr.b)
        if left is None or right is None:
            return None
        bounds = _union(left, right)
        radius = float(getattr(expr, "k", getattr(expr, "radius", 0.0)) or 0.0)
        return _expand(bounds, max(radius, 0.0))
    if isinstance(expr, (Intersect, SmoothIntersect, ChamferIntersect)):
        left = _estimate_bounds(expr.a)
        right = _estimate_bounds(expr.b)
        if left is None and right is None:
            return None
        if left is None:
            bounds = right
        elif right is None:
            bounds = left
        else:
            bounds = _intersect(left, right)
        radius = float(getattr(expr, "k", getattr(expr, "radius", 0.0)) or 0.0)
        return _expand(bounds, max(radius, 0.0))
    if isinstance(expr, (Subtract, SmoothSubtract, ChamferSubtract)):
        left = _estimate_bounds(expr.a)
        if left is None:
            return None
        radius = float(getattr(expr, "k", getattr(expr, "radius", 0.0)) or 0.0)
        return _expand(left, max(radius, 0.0))
    return None


def _expand(bounds: Bounds, amount: float) -> Bounds:
    return (
        tuple(float(value) - amount for value in bounds[0]),
        tuple(float(value) + amount for value in bounds[1]),
    )


def _union(a: Bounds, b: Bounds) -> Bounds:
    return (
        tuple(min(float(a[0][axis]), float(b[0][axis])) for axis in range(3)),
        tuple(max(float(a[1][axis]), float(b[1][axis])) for axis in range(3)),
    )


def _intersect(a: Bounds, b: Bounds) -> Bounds:
    return (
        tuple(max(float(a[0][axis]), float(b[0][axis])) for axis in range(3)),
        tuple(min(float(a[1][axis]), float(b[1][axis])) for axis in range(3)),
    )


def _transform_bounds(bounds: Bounds, matrix: np.ndarray) -> Bounds:
    lo, hi = bounds
    corners = np.asarray(
        [
            (x, y, z)
            for x, y, z in product(
                (float(lo[0]), float(hi[0])),
                (float(lo[1]), float(hi[1])),
                (float(lo[2]), float(hi[2])),
            )
        ],
        dtype=np.float64,
    )
    transformed = corners @ np.asarray(matrix, dtype=np.float64).T
    return (
        tuple(float(value) for value in transformed.min(axis=0)),
        tuple(float(value) for value in transformed.max(axis=0)),
    )
