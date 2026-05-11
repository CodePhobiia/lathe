"""Primitive-recognizer + geometric helpers shared by per-op modules.

This module groups the shared cluster of "trimesh → primitive metadata"
recognizers and geometric helpers used by hull, minkowski, carve,
polyextrude, instances, and other per-op modules to take exact-rebuild
paths when the source mesh is a known analytical primitive.

The recognizers inspect a trimesh's metadata for ``lathe_shape_primitive``
and ``lathe_reference_primitive`` blobs, validating type/dimension
fields and returning a normalized record. The geometric helpers (axis
validation, span/interval math, profile polygon manipulation) live
here so they can be imported from one location.

Per the §5.3 decomposition, isolating these helpers keeps the per-op
modules thin. Per-op modules import from ``_primitive_metadata``;
``_primitive_metadata`` imports only from ``..kernel``, ``trimesh``,
``numpy``, and the stdlib.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import trimesh


def _validated_deform_axis(axis: str, *, field: str = "axis") -> str:
    """Validate that ``axis`` is one of x/y/z, returning the lowercase form."""
    value = str(axis or "").strip().lower()
    if value not in {"x", "y", "z"}:
        raise ValueError(f"kernel deform {field} must be one of: x, y, z")
    return value


def _axis_index(axis: str) -> int:
    """Map an axis name (x/y/z) to its 0/1/2 index."""
    if axis == "x":
        return 0
    if axis == "y":
        return 1
    if axis == "z":
        return 2
    raise ValueError("axis must be one of: x, y, z")


def _axis_name_from_index(index: int) -> str:
    """Map a 0/1/2 axis index to its x/y/z name."""
    return ("x", "y", "z")[index]


def _perpendicular_axis_indices(axis: str) -> tuple[int, int]:
    """Return the two axis indices perpendicular to ``axis``."""
    axis_index = _axis_index(axis)
    indices = tuple(index for index in (0, 1, 2) if index != axis_index)
    return (indices[0], indices[1])


def _validated_origin(origin: Any | None) -> list[float] | None:
    """Validate a 3-item numeric origin sequence or return None when ``origin`` is None."""
    from ._common import _finite_float

    if origin is None:
        return None
    if not isinstance(origin, (list, tuple)) or len(origin) != 3:
        raise ValueError("kernel deform origin must be a 3-item numeric sequence")
    return [_finite_float(value, field="origin") for value in origin]


def _axis_span(vertices: np.ndarray, axis_index: int) -> tuple[float, float, float]:
    """Return ``(min, max, span)`` along an axis; guards against degenerate zero span."""
    axis_min = float(vertices[:, axis_index].min())
    axis_max = float(vertices[:, axis_index].max())
    return axis_min, axis_max, max(axis_max - axis_min, 1e-6)


def _mesh_with_vertices(
    source_mesh: trimesh.Trimesh,
    vertices: np.ndarray,
) -> trimesh.Trimesh:
    """Clone ``source_mesh`` with new vertex coordinates; preserves metadata + faces."""
    mesh = trimesh.Trimesh(
        vertices=np.asarray(vertices, dtype=np.float64),
        faces=np.asarray(source_mesh.faces, dtype=np.int64).copy(),
        process=False,
    )
    mesh.metadata.update(dict(source_mesh.metadata))
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()
    try:
        mesh.fix_normals()
    except (ValueError, RuntimeError, AttributeError, IndexError, TypeError):
        pass
    return mesh


def _numeric_triplet(value: Any) -> tuple[float, float, float] | None:
    """Coerce ``value`` to a 3-tuple of finite floats or return None."""
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    try:
        out = tuple(float(item) for item in value)
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(item) for item in out):
        return None
    return out  # type: ignore[return-value]


def _positive_triplet(value: tuple[float, float, float]) -> bool:
    """Return True iff all 3 floats are positive and finite."""
    return all(item > 0.0 and math.isfinite(item) for item in value)


def _numeric_pair(value: Any) -> tuple[float, float] | None:
    """Coerce ``value`` to a 2-tuple of finite floats or return None."""
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    try:
        out = (float(value[0]), float(value[1]))
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(item) for item in out):
        return None
    return out


def _profile_polygon_2d(value: Any) -> tuple[tuple[float, float], ...] | None:
    """Coerce a profile-polygon literal to a tuple of (u, v) point pairs."""
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return None
    points: list[tuple[float, float]] = []
    for item in value:
        point = _numeric_pair(item)
        if point is None:
            return None
        points.append(point)
    return tuple(points)


def _rotate_profile_polygon_2d(
    polygon: tuple[tuple[float, float], ...],
    angle_degrees: float,
) -> tuple[tuple[float, float], ...]:
    """Rotate a 2D profile polygon by ``angle_degrees`` around the origin."""
    if abs(angle_degrees) <= 1e-12:
        return polygon
    angle = math.radians(float(angle_degrees))
    cos_value = math.cos(angle)
    sin_value = math.sin(angle)
    return tuple(
        (
            float(u) * cos_value - float(v) * sin_value,
            float(u) * sin_value + float(v) * cos_value,
        )
        for u, v in polygon
    )


def _rounded_rectangle_profile_points(
    *,
    width: float,
    height: float,
    radius: float,
    segments: int = 8,
) -> list[tuple[float, float]]:
    """Sample a rounded-rectangle profile for box+sphere/capsule Minkowski rebuilds."""
    half_width = float(width) * 0.5
    half_height = float(height) * 0.5
    corner_radius = min(float(radius), half_width, half_height)
    if corner_radius <= 1e-9:
        return [
            (-half_width, -half_height),
            (half_width, -half_height),
            (half_width, half_height),
            (-half_width, half_height),
        ]
    core_half_width = max(0.0, half_width - corner_radius)
    core_half_height = max(0.0, half_height - corner_radius)
    corner_specs = (
        ((core_half_width, core_half_height), 0.0, math.pi * 0.5),
        ((-core_half_width, core_half_height), math.pi * 0.5, math.pi),
        ((-core_half_width, -core_half_height), math.pi, math.pi * 1.5),
        ((core_half_width, -core_half_height), math.pi * 1.5, math.tau),
    )
    points: list[tuple[float, float]] = []
    steps = max(2, min(32, int(segments)))
    for (center_u, center_v), start, end in corner_specs:
        for index in range(steps + 1):
            if points and index == 0:
                continue
            t = index / float(steps)
            angle = start + (end - start) * t
            points.append(
                (
                    float(center_u + math.cos(angle) * corner_radius),
                    float(center_v + math.sin(angle) * corner_radius),
                )
            )
    return points


def _box_extents_in_extruded_profile_plane(
    box: dict[str, Any],
    *,
    axis: str,
) -> tuple[float, float, float] | None:
    """Return box extents reordered so the extrude axis is last; None when degenerate."""
    extents = box.get("extents")
    if not isinstance(extents, (list, tuple)) or len(extents) != 3:
        return None
    values = [float(value) for value in extents]
    if axis == "z":
        return values[0], values[1], values[2]
    if axis == "y":
        return values[0], values[2], values[1]
    if axis == "x":
        return values[2], values[1], values[0]
    return None


def _axis_interval_center_and_span(
    center: tuple[float, float, float],
    *,
    axis: str,
    span: float,
    u_start: float,
    u_end: float,
) -> tuple[tuple[float, float, float], float, float, float]:
    """Carve an axis interval, returning ``(new_center, carved_span, carved_min, carved_max)``."""
    axis_index = _axis_index(axis)
    source_min = float(center[axis_index]) - float(span) * 0.5
    source_max = float(center[axis_index]) + float(span) * 0.5  # noqa: F841 — kept for symmetry with _axis_extruded_center_and_span
    carved_min = source_min + float(span) * float(u_start)
    carved_max = source_min + float(span) * float(u_end)
    carved_span = max(carved_max - carved_min, 1e-6)
    result_center = list(float(value) for value in center)
    result_center[axis_index] = (carved_min + carved_max) * 0.5
    return (
        (float(result_center[0]), float(result_center[1]), float(result_center[2])),
        carved_span,
        carved_min,
        carved_max,
    )


def _axis_extruded_center_and_span(
    center: tuple[float, float, float],
    *,
    axis: str,
    span: float,
    distance: float,
) -> tuple[tuple[float, float, float], float, float, float, float]:
    """Extrude an axis interval by ``distance``, returning new center/span/source/result."""
    axis_index = _axis_index(axis)
    source_min = float(center[axis_index]) - float(span) * 0.5
    source_max = float(center[axis_index]) + float(span) * 0.5
    result_min = source_min + min(0.0, float(distance))
    result_max = source_max + max(0.0, float(distance))
    result_span = max(result_max - result_min, 1e-6)
    result_center = list(float(value) for value in center)
    result_center[axis_index] = (result_min + result_max) * 0.5
    return (
        (float(result_center[0]), float(result_center[1]), float(result_center[2])),
        result_span,
        source_min,
        source_max,
        result_min,
    )


def _box_metadata_from_bounds(
    bounds_min: tuple[float, float, float],
    bounds_max: tuple[float, float, float],
    *,
    source: str,
) -> dict[str, Any] | None:
    """Build a box-metadata record from explicit min/max bounds, or None when degenerate."""
    extents = tuple(bounds_max[axis] - bounds_min[axis] for axis in range(3))
    if not _positive_triplet(extents):
        return None
    center = tuple((bounds_min[axis] + bounds_max[axis]) * 0.5 for axis in range(3))
    return {
        "source": source,
        "center": center,
        "extents": extents,
        "bounds_min": bounds_min,
        "bounds_max": bounds_max,
    }


def _axis_aligned_box_metadata(mesh: trimesh.Trimesh) -> dict[str, Any] | None:
    """Recognize an axis-aligned box from mesh metadata; return None when not a box.

    Rejects rounded boxes and boxes with active modifiers
    (polybevel/subdivision/remesh) since those imply a non-box
    geometry that an exact-box reconstruction would miscompute.
    """
    metadata = mesh.metadata if isinstance(mesh.metadata, dict) else {}
    shape = metadata.get("lathe_shape_primitive")
    if isinstance(shape, dict) and str(shape.get("primitive_type") or "") == "box":
        try:
            rounding = float(shape.get("rounding") or shape.get("rounding_cm") or 0.0)
        except (TypeError, ValueError):
            rounding = 0.0
        if rounding > 1e-9:
            return None
        for modifier_name in (
            "v2_polybevel_modifier",
            "v2_subdivision_modifier",
            "v2_remesh_modifier",
        ):
            if shape.get(modifier_name) not in (None, {}, [], ()):
                return None
        extents = _numeric_triplet(shape.get("extents"))
        center = _numeric_triplet(shape.get("center")) or (0.0, 0.0, 0.0)
        if extents is not None and _positive_triplet(extents):
            half = tuple(item * 0.5 for item in extents)
            return {
                "source": "lathe_shape_primitive",
                "center": center,
                "extents": extents,
                "bounds_min": tuple(center[axis] - half[axis] for axis in range(3)),
                "bounds_max": tuple(center[axis] + half[axis] for axis in range(3)),
            }

    reference = metadata.get("lathe_reference_primitive")
    if isinstance(reference, dict) and str(reference.get("kind") or "") == "box":
        bounds_min = _numeric_triplet(reference.get("bounds_min"))
        bounds_max = _numeric_triplet(reference.get("bounds_max"))
        if bounds_min is not None and bounds_max is not None:
            return _box_metadata_from_bounds(
                bounds_min,
                bounds_max,
                source="lathe_reference_primitive",
            )
    return None


def _extruded_profile_metadata(mesh: trimesh.Trimesh) -> dict[str, Any] | None:
    """Recognize an extruded_profile primitive from mesh metadata; return None when not one.

    Validates the profile polygon, extrude height, axis, optional
    scale taper, and twist+segments. Returns a normalized record
    consumed by carve/polyextrude/instances exact paths.
    """
    metadata = mesh.metadata if isinstance(mesh.metadata, dict) else {}
    shape = metadata.get("lathe_shape_primitive")
    if not isinstance(shape, dict) or str(shape.get("primitive_type") or "") != "extruded_profile":
        return None
    polygon = _profile_polygon_2d(shape.get("profile_polygon"))
    if polygon is None:
        return None
    try:
        height = float(shape.get("extrude_height"))
    except (TypeError, ValueError):
        return None
    if height <= 0.0 or not math.isfinite(height):
        return None
    axis = str(shape.get("axis") or "y")
    if axis not in {"x", "y", "z"}:
        return None
    center = _numeric_triplet(shape.get("center")) or (0.0, 0.0, 0.0)
    start_scale = shape.get("extrude_start_scale")
    end_scale = shape.get("extrude_end_scale")
    twist = shape.get("extrude_twist_degrees")
    segments = shape.get("extrude_segments")

    def optional_float(value: Any, default: float) -> float:
        if value is None:
            return default
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError
        return parsed

    def optional_int(value: Any, default: int) -> int:
        if value is None:
            return default
        parsed = int(value)
        if parsed < 1:
            raise ValueError
        return parsed

    try:
        parsed_start_scale = optional_float(start_scale, 1.0)
        parsed_end_scale = optional_float(end_scale, 1.0)
        parsed_twist = optional_float(twist, 0.0)
        parsed_segments = optional_int(segments, 1)
    except (TypeError, ValueError):
        return None
    if parsed_start_scale <= 0.0 or parsed_end_scale <= 0.0:
        return None
    return {
        "source": "lathe_shape_primitive",
        "shape": dict(shape),
        "center": center,
        "axis": axis,
        "profile_polygon": polygon,
        "extrude_height": height,
        "extrude_start_scale": parsed_start_scale,
        "extrude_end_scale": parsed_end_scale,
        "extrude_twist_degrees": parsed_twist,
        "extrude_segments": parsed_segments,
    }


def _sphere_metadata(mesh: trimesh.Trimesh) -> dict[str, Any] | None:
    """Recognize a sphere primitive from mesh metadata; return None when not a sphere."""
    metadata = mesh.metadata if isinstance(mesh.metadata, dict) else {}
    shape = metadata.get("lathe_shape_primitive")
    if not isinstance(shape, dict) or str(shape.get("primitive_type") or "") != "sphere":
        return None
    try:
        radius = float(shape.get("radius"))
    except (TypeError, ValueError):
        return None
    if radius <= 0.0 or not math.isfinite(radius):
        return None
    center = _numeric_triplet(shape.get("center")) or (0.0, 0.0, 0.0)
    return {
        "source": "lathe_shape_primitive",
        "center": center,
        "radius": radius,
    }


def _cylinder_metadata(mesh: trimesh.Trimesh) -> dict[str, Any] | None:
    """Recognize a cylinder primitive from mesh metadata; return None when not a cylinder."""
    metadata = mesh.metadata if isinstance(mesh.metadata, dict) else {}
    shape = metadata.get("lathe_shape_primitive")
    if not isinstance(shape, dict) or str(shape.get("primitive_type") or "") != "cylinder":
        return None
    try:
        radius = float(shape.get("radius"))
        height = float(shape.get("height"))
    except (TypeError, ValueError):
        return None
    if radius <= 0.0 or height <= 0.0 or not math.isfinite(radius) or not math.isfinite(height):
        return None
    axis = str(shape.get("axis") or "y")
    if axis not in {"x", "y", "z"}:
        return None
    center = _numeric_triplet(shape.get("center")) or (0.0, 0.0, 0.0)
    return {
        "source": "lathe_shape_primitive",
        "center": center,
        "radius": radius,
        "height": height,
        "axis": axis,
    }


def _capsule_metadata(mesh: trimesh.Trimesh) -> dict[str, Any] | None:
    """Recognize a capsule primitive from mesh metadata; return None when not a capsule.

    Capsules require length > 2 * radius so the cylindrical shaft is
    non-degenerate; rejects collapsed/degenerate inputs.
    """
    metadata = mesh.metadata if isinstance(mesh.metadata, dict) else {}
    shape = metadata.get("lathe_shape_primitive")
    if not isinstance(shape, dict) or str(shape.get("primitive_type") or "") != "capsule":
        return None
    try:
        radius = float(shape.get("radius"))
        length = float(shape.get("length"))
    except (TypeError, ValueError):
        return None
    if radius <= 0.0 or length <= 2.0 * radius or not math.isfinite(radius) or not math.isfinite(length):
        return None
    axis = str(shape.get("axis") or "y")
    if axis not in {"x", "y", "z"}:
        return None
    center = _numeric_triplet(shape.get("center")) or (0.0, 0.0, 0.0)
    return {
        "source": "lathe_shape_primitive",
        "center": center,
        "radius": radius,
        "length": length,
        "axis": axis,
        "shaft_length": length - 2.0 * radius,
    }


__all__ = [
    "_axis_aligned_box_metadata",
    "_axis_extruded_center_and_span",
    "_axis_index",
    "_axis_interval_center_and_span",
    "_axis_name_from_index",
    "_axis_span",
    "_box_extents_in_extruded_profile_plane",
    "_box_metadata_from_bounds",
    "_capsule_metadata",
    "_cylinder_metadata",
    "_extruded_profile_metadata",
    "_mesh_with_vertices",
    "_numeric_pair",
    "_numeric_triplet",
    "_perpendicular_axis_indices",
    "_positive_triplet",
    "_profile_polygon_2d",
    "_rotate_profile_polygon_2d",
    "_rounded_rectangle_profile_points",
    "_sphere_metadata",
    "_validated_deform_axis",
    "_validated_origin",
]
