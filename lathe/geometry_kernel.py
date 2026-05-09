"""Legacy SDF and exact-surface shape fusion helpers."""

from __future__ import annotations

import hashlib
import json
from contextlib import suppress
from typing import Any

import numpy as np
import trimesh
from scipy.ndimage import gaussian_filter
from trimesh.voxel.ops import matrix_to_marching_cubes

from .errors import ContractViolation
from .exact_solids import compile_explicit_surface_mesh, exactify_surface_mesh
from .feature_fusion import integration_config_for_family, primitive_blend_mode, primitive_rounding
from .fidelity import FidelityProfile
from .mesh_finalize import finalize_mesh_ir
from .mesh_ir import MeshIR
from .shape_ir import ShapeIR, ShapePrimitive, ShapeRegion
from .solid_ir import SolidIR, SolidOp

_FUSION_CACHE: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
MAX_FUSION_VOXELS = 6_500_000
_SHAPE_IR_V2_KERNEL_MODIFIER_ATTRS = (
    "v2_subdivision_modifier",
    "v2_remesh_modifier",
    "v2_polybevel_modifier",
    "v2_mark_hard_edge_modifier",
    "v2_inset_modifier",
    "v2_weighted_normals_modifier",
    "v2_hull_modifier",
    "v2_minkowski_modifier",
)
_SHAPE_IR_V2_KERNEL_METADATA_CONTAINERS = (
    "shape_ir_v2",
    "shape_ir_v2_baked_source_modifiers",
    "semantic_metadata",
    "source_shape_primitive",
    "source_shape_primitives",
)


class _MissingBoxExtentsError(ContractViolation):
    def __init__(self, part: str) -> None:
        super().__init__(
            f"invariant violation: box ShapePrimitive requires extents, got None (part={part!r})"
        )


class _MissingCylinderDimensionsError(ContractViolation):
    def __init__(self, primitive: ShapePrimitive) -> None:
        super().__init__(
            "invariant violation: cylinder ShapePrimitive requires radius and height, "
            f"got radius={primitive.radius!r}, height={primitive.height!r} "
            f"(part={primitive.part!r})"
        )


class _MissingSphereRadiusError(ContractViolation):
    def __init__(self, primitive: ShapePrimitive) -> None:
        super().__init__(
            "invariant violation: sphere ShapePrimitive requires radius, "
            f"got radius={primitive.radius!r} (part={primitive.part!r})"
        )


class _UnsupportedPrimitiveTypeError(ValueError):
    def __init__(self, primitive_type: str) -> None:
        super().__init__(f"Unsupported primitive type '{primitive_type}'")


def _primitive_bounds(primitive: ShapePrimitive, rounding: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    center_offset = np.zeros(3, dtype=np.float64)
    if primitive.primitive_type == "box":
        if primitive.extents is None:
            raise _MissingBoxExtentsError(primitive.part)
        half = np.array(primitive.extents, dtype=np.float64) / 2.0 + rounding
    elif primitive.primitive_type == "cylinder":
        if primitive.radius is None or primitive.height is None:
            raise _MissingCylinderDimensionsError(primitive)
        radius = float(primitive.radius) + rounding
        half_h = float(primitive.height) / 2.0 + rounding
        if primitive.axis == "x":
            half = np.array([half_h, radius, radius], dtype=np.float64)
        elif primitive.axis == "z":
            half = np.array([radius, radius, half_h], dtype=np.float64)
        else:
            half = np.array([radius, half_h, radius], dtype=np.float64)
    elif primitive.primitive_type == "sphere":
        if primitive.radius is None:
            raise _MissingSphereRadiusError(primitive)
        radius = float(primitive.radius) + rounding
        half = np.array([radius, radius, radius], dtype=np.float64)
    elif primitive.primitive_type == "revolved_profile":
        # Bounding cylinder of the swept profile; SDF path uses this as
        # an outer envelope, which is fine for voxelization since the
        # exact-solid path produces the actual mesh.
        points = primitive.profile_points or []
        if not points:
            raise _UnsupportedPrimitiveTypeError(
                f"revolved_profile primitive missing profile_points (part={primitive.part!r})"
            )
        radius = max(abs(float(r)) for _, r in points) + rounding
        axials = [float(a) for a, _ in points]
        min_axial = min(axials)
        max_axial = max(axials)
        half_h = (max_axial - min_axial) / 2.0 + rounding
        axial_center = (min_axial + max_axial) / 2.0
        if primitive.axis == "x":
            half = np.array([half_h, radius, radius], dtype=np.float64)
            center_offset = np.array([axial_center, 0.0, 0.0], dtype=np.float64)
        elif primitive.axis == "z":
            half = np.array([radius, radius, half_h], dtype=np.float64)
            center_offset = np.array([0.0, 0.0, axial_center], dtype=np.float64)
        else:
            half = np.array([radius, half_h, radius], dtype=np.float64)
            center_offset = np.array([0.0, axial_center, 0.0], dtype=np.float64)
    elif primitive.primitive_type == "extruded_profile":
        # AABB of the polygon's 2D bbox extruded along ``axis``. The
        # voxelization fallback is rarely invoked; manifold/exact paths
        # produce the accurate prismatic mesh.
        polygon = primitive.profile_polygon or []
        if len(polygon) < 3:  # noqa: PLR2004
            raise _UnsupportedPrimitiveTypeError(
                f"extruded_profile primitive missing profile_polygon (part={primitive.part!r})"
            )
        if primitive.extrude_height is None or float(primitive.extrude_height) <= 0.0:
            raise _UnsupportedPrimitiveTypeError(
                f"extruded_profile primitive missing extrude_height (part={primitive.part!r})"
            )
        us = [float(u) for u, _ in polygon]
        vs = [float(v) for _, v in polygon]
        min_u = min(us)
        max_u = max(us)
        min_v = min(vs)
        max_v = max(vs)
        half_u = (max_u - min_u) / 2.0 + rounding
        half_v = (max_v - min_v) / 2.0 + rounding
        center_u = (min_u + max_u) / 2.0
        center_v = (min_v + max_v) / 2.0
        half_h = float(primitive.extrude_height) / 2.0 + rounding
        if primitive.axis == "x":
            half = np.array([half_h, half_u, half_v], dtype=np.float64)
            center_offset = np.array([0.0, center_u, center_v], dtype=np.float64)
        elif primitive.axis == "z":
            half = np.array([half_u, half_v, half_h], dtype=np.float64)
            center_offset = np.array([center_u, center_v, 0.0], dtype=np.float64)
        else:
            half = np.array([half_u, half_h, half_v], dtype=np.float64)
            center_offset = np.array([center_u, 0.0, center_v], dtype=np.float64)
    elif primitive.primitive_type == "torus":
        # Bounding cylinder of the ring (outer radius major+minor, height
        # 2*minor). SDF voxelization uses this envelope; the manifold/
        # exact paths produce the accurate ring mesh.
        if primitive.major_radius is None or primitive.minor_radius is None:
            raise _UnsupportedPrimitiveTypeError(
                f"torus primitive missing major_radius/minor_radius (part={primitive.part!r})"
            )
        major = float(primitive.major_radius)
        minor = float(primitive.minor_radius)
        radius = major + minor + rounding
        half_h = minor + rounding
        if primitive.axis == "x":
            half = np.array([half_h, radius, radius], dtype=np.float64)
        elif primitive.axis == "z":
            half = np.array([radius, radius, half_h], dtype=np.float64)
        else:
            half = np.array([radius, half_h, radius], dtype=np.float64)
    elif primitive.primitive_type == "subdivision_box":
        # Per-corner radii are clamped within ``extents``; the cuboid
        # AABB is unchanged regardless of corner_radii values.
        if primitive.extents is None:
            raise _MissingBoxExtentsError(primitive.part)
        half = np.array(primitive.extents, dtype=np.float64) / 2.0 + rounding
    elif primitive.primitive_type == "swept_profile":
        # AABB of the path origins expanded by the cross-section
        # circumradius. The SDF voxelization path is rarely hit for
        # swept_profile — manifold/exact handles it — but the box gives
        # a safe outer envelope when this path is taken.
        from .exact_solids import _swept_profile_extents

        path_min, path_max, circumradius = _swept_profile_extents(primitive)
        reach = circumradius + rounding
        path_center = 0.5 * (path_min + path_max)
        half = 0.5 * (path_max - path_min) + reach
        center = np.array(primitive.center, dtype=np.float64) + path_center
        return center - half, center + half
    elif primitive.primitive_type == "lofted_solid":
        # Same envelope strategy as swept_profile: section-centers AABB
        # expanded by the worst-case cross-section reach. The SDF
        # voxelization fallback is rarely hit for lofted_solid — the
        # exact ring-stitched mesh path is preferred.
        from .exact_solids import _lofted_solid_extents

        path_min, path_max, circumradius = _lofted_solid_extents(primitive)
        reach = circumradius + rounding
        path_center = 0.5 * (path_min + path_max)
        half = 0.5 * (path_max - path_min) + reach
        center = np.array(primitive.center, dtype=np.float64) + path_center
        return center - half, center + half
    else:
        raise _UnsupportedPrimitiveTypeError(primitive.primitive_type)
    center = np.array(primitive.center, dtype=np.float64) + center_offset
    return center - half, center + half


def _box_sdf(points: np.ndarray, primitive: ShapePrimitive, rounding: float) -> np.ndarray:
    if primitive.extents is None:
        raise _MissingBoxExtentsError(primitive.part)
    center = np.array(primitive.center, dtype=np.float64)
    half = np.array(primitive.extents, dtype=np.float64) / 2.0 - rounding
    q = np.abs(points - center) - half
    outside = np.linalg.norm(np.maximum(q, 0.0), axis=-1)
    inside = np.minimum(np.max(q, axis=-1), 0.0)
    return outside + inside - rounding


def _cylinder_sdf(points: np.ndarray, primitive: ShapePrimitive, rounding: float) -> np.ndarray:
    if primitive.radius is None or primitive.height is None:
        raise _MissingCylinderDimensionsError(primitive)
    center = np.array(primitive.center, dtype=np.float64)
    p = points - center
    radius = float(primitive.radius)
    half_h = float(primitive.height) / 2.0
    if primitive.axis == "x":
        radial = np.linalg.norm(p[..., 1:], axis=-1)
        axial = np.abs(p[..., 0])
    elif primitive.axis == "z":
        radial = np.linalg.norm(p[..., :2], axis=-1)
        axial = np.abs(p[..., 2])
    else:
        radial = np.linalg.norm(p[..., [0, 2]], axis=-1)
        axial = np.abs(p[..., 1])
    d = np.stack(
        [radial - max(0.0, radius - rounding), axial - max(0.0, half_h - rounding)],
        axis=-1,
    )
    outside = np.linalg.norm(np.maximum(d, 0.0), axis=-1)
    inside = np.minimum(np.max(d, axis=-1), 0.0)
    return outside + inside - rounding


def _sphere_sdf(points: np.ndarray, primitive: ShapePrimitive, rounding: float) -> np.ndarray:
    if primitive.radius is None:
        raise _MissingSphereRadiusError(primitive)
    center = np.array(primitive.center, dtype=np.float64)
    radius = max(0.0, float(primitive.radius) - rounding)
    return np.linalg.norm(points - center, axis=-1) - radius - rounding


def _axis_local_points(points: np.ndarray, primitive: ShapePrimitive) -> tuple[np.ndarray, np.ndarray]:
    center = np.asarray(primitive.center, dtype=np.float64)
    local = points - center
    if primitive.axis == "x":
        return local[..., 0], local[..., [1, 2]]
    if primitive.axis == "z":
        return local[..., 2], local[..., [0, 1]]
    return local[..., 1], local[..., [0, 2]]


def _clean_polygon_points(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    clean: list[tuple[float, float]] = []
    for u, v in points:
        point = (float(u), float(v))
        if not clean or clean[-1] != point:
            clean.append(point)
    if len(clean) > 1 and clean[0] == clean[-1]:
        clean.pop()
    return clean


def _signed_polygon_distance_2d(points_2d: np.ndarray, polygon: list[tuple[float, float]]) -> np.ndarray:
    vertices = np.asarray(_clean_polygon_points(polygon), dtype=np.float64)
    if len(vertices) < 3:  # noqa: PLR2004
        raise _UnsupportedPrimitiveTypeError("signed polygon SDF requires at least 3 points")

    shape = points_2d.shape[:-1]
    query = points_2d.reshape(-1, 2)
    x = query[:, 0]
    y = query[:, 1]
    inside = np.zeros(len(query), dtype=bool)
    min_distance_sq = np.full(len(query), np.inf, dtype=np.float64)

    for index, left in enumerate(vertices):
        right = vertices[(index + 1) % len(vertices)]
        edge = right - left
        edge_len_sq = float(np.dot(edge, edge))
        if edge_len_sq > 0.0:
            t = np.clip(((query - left) @ edge) / edge_len_sq, 0.0, 1.0)
            closest = left + t[:, None] * edge
            delta = query - closest
            min_distance_sq = np.minimum(min_distance_sq, np.einsum("ij,ij->i", delta, delta))

        x0, y0 = left
        x1, y1 = right
        denom = y1 - y0
        if abs(float(denom)) <= 1.0e-12:
            denom = 1.0e-12 if denom >= 0.0 else -1.0e-12
        crossing = ((y0 > y) != (y1 > y)) & (x < ((x1 - x0) * (y - y0) / denom + x0))
        inside ^= crossing

    distance = np.sqrt(np.maximum(min_distance_sq, 0.0))
    return np.where(inside, -distance, distance).reshape(shape)


def _extruded_profile_sdf(points: np.ndarray, primitive: ShapePrimitive, rounding: float) -> np.ndarray:
    polygon = primitive.profile_polygon or []
    if len(polygon) < 3:  # noqa: PLR2004
        raise _UnsupportedPrimitiveTypeError(
            f"extruded_profile primitive missing profile_polygon (part={primitive.part!r})"
        )
    if primitive.extrude_height is None or float(primitive.extrude_height) <= 0.0:
        raise _UnsupportedPrimitiveTypeError(
            f"extruded_profile primitive missing extrude_height (part={primitive.part!r})"
        )
    if (
        primitive.extrude_start_scale is not None
        or primitive.extrude_end_scale is not None
        or primitive.extrude_twist_degrees is not None
        or primitive.extrude_segments is not None
    ):
        raise _UnsupportedPrimitiveTypeError(
            "generalized extruded_profile SDF fallback is unsupported; "
            "use the exact mesh path for tapered or twisted extrusions"
        )

    axial, plane = _axis_local_points(points, primitive)
    inset = max(0.0, float(rounding))
    polygon_distance = _signed_polygon_distance_2d(plane, polygon) + inset
    half_height = max(0.0, float(primitive.extrude_height) / 2.0 - inset)
    axial_distance = np.abs(axial) - half_height
    d = np.stack([polygon_distance, axial_distance], axis=-1)
    outside = np.linalg.norm(np.maximum(d, 0.0), axis=-1)
    inside = np.minimum(np.maximum(polygon_distance, axial_distance), 0.0)
    return outside + inside - inset


def _revolved_profile_sdf(points: np.ndarray, primitive: ShapePrimitive, rounding: float) -> np.ndarray:
    profile_points = primitive.profile_points or []
    if not profile_points:
        raise _UnsupportedPrimitiveTypeError(
            f"revolved_profile primitive missing profile_points (part={primitive.part!r})"
        )
    if primitive.revolve_degrees is not None and abs(float(primitive.revolve_degrees) - 360.0) > 1e-6:
        raise _UnsupportedPrimitiveTypeError(
            "partial revolved_profile SDF fallback is unsupported; "
            "use the exact mesh path for revolve_degrees < 360"
        )

    axial, plane = _axis_local_points(points, primitive)
    radial = np.linalg.norm(plane, axis=-1)
    query = np.stack([axial, radial], axis=-1)
    profile = [(float(profile_points[0][0]), 0.0)]
    profile.extend(
        (float(axial_value), max(0.0, abs(float(radial_value))))
        for axial_value, radial_value in profile_points
    )
    profile.append((float(profile_points[-1][0]), 0.0))
    profile = _clean_polygon_points(profile)
    if len(profile) < 3:  # noqa: PLR2004
        from .exact_solids import _revolved_profile_extents

        radius, height = _revolved_profile_extents(primitive)
        proxy = ShapePrimitive(
            primitive_type="cylinder",
            part=primitive.part,
            center=primitive.center,
            radius=float(radius),
            height=float(height),
            axis=primitive.axis,
            blend_mode=primitive.blend_mode,
            rounding=primitive.rounding,
        )
        return _cylinder_sdf(points, proxy, rounding)
    return _signed_polygon_distance_2d(query, profile) - max(0.0, float(rounding))


def _torus_sdf(points: np.ndarray, primitive: ShapePrimitive, rounding: float) -> np.ndarray:
    if primitive.major_radius is None or primitive.minor_radius is None:
        raise _UnsupportedPrimitiveTypeError(
            f"torus primitive missing major_radius/minor_radius (part={primitive.part!r})"
        )
    axial, plane = _axis_local_points(points, primitive)
    major = float(primitive.major_radius)
    minor = max(0.0, float(primitive.minor_radius) - rounding)
    radial = np.linalg.norm(plane, axis=-1)
    tube = np.stack([radial - major, axial], axis=-1)
    return np.linalg.norm(tube, axis=-1) - minor - rounding


def _distance_to_sweep_path(points: np.ndarray, primitive: ShapePrimitive) -> np.ndarray:
    sweep_path = primitive.sweep_path or []
    if len(sweep_path) < 2:  # noqa: PLR2004
        raise _UnsupportedPrimitiveTypeError(
            f"swept_profile primitive missing sweep_path (part={primitive.part!r})"
        )
    center = np.asarray(primitive.center, dtype=np.float64)
    path = center + np.asarray(
        [[float(x), float(y), float(z)] for x, y, z in sweep_path],
        dtype=np.float64,
    )
    shape = points.shape[:-1]
    query = points.reshape(-1, 3)
    min_distance_sq = np.full(len(query), np.inf, dtype=np.float64)
    for left, right in zip(path, path[1:], strict=True):
        edge = right - left
        edge_len_sq = float(np.dot(edge, edge))
        if edge_len_sq <= 0.0:
            delta = query - left
        else:
            t = np.clip(((query - left) @ edge) / edge_len_sq, 0.0, 1.0)
            delta = query - (left + t[:, None] * edge)
        min_distance_sq = np.minimum(min_distance_sq, np.einsum("ij,ij->i", delta, delta))
    return np.sqrt(np.maximum(min_distance_sq, 0.0)).reshape(shape)


def _swept_profile_sdf(points: np.ndarray, primitive: ShapePrimitive, rounding: float) -> np.ndarray:
    cross_section = primitive.cross_section or []
    if len(cross_section) < 3:  # noqa: PLR2004
        raise _UnsupportedPrimitiveTypeError(
            f"swept_profile primitive missing cross_section (part={primitive.part!r})"
        )
    radius = max(float(np.hypot(float(u), float(v))) for u, v in cross_section)
    inset = max(0.0, float(rounding))
    return _distance_to_sweep_path(points, primitive) - max(0.0, radius - inset) - inset


def _distance_to_section_path(points: np.ndarray, primitive: ShapePrimitive) -> np.ndarray:
    section_centers = primitive.section_centers or []
    if len(section_centers) < 2:  # noqa: PLR2004
        raise _UnsupportedPrimitiveTypeError(
            f"lofted_solid primitive missing section_centers (part={primitive.part!r})"
        )
    center = np.asarray(primitive.center, dtype=np.float64)
    path = center + np.asarray(
        [[float(x), float(y), float(z)] for x, y, z in section_centers],
        dtype=np.float64,
    )
    shape = points.shape[:-1]
    query = points.reshape(-1, 3)
    min_distance_sq = np.full(len(query), np.inf, dtype=np.float64)
    for left, right in zip(path, path[1:], strict=True):
        edge = right - left
        edge_len_sq = float(np.dot(edge, edge))
        if edge_len_sq <= 0.0:
            delta = query - left
        else:
            t = np.clip(((query - left) @ edge) / edge_len_sq, 0.0, 1.0)
            delta = query - (left + t[:, None] * edge)
        min_distance_sq = np.minimum(min_distance_sq, np.einsum("ij,ij->i", delta, delta))
    return np.sqrt(np.maximum(min_distance_sq, 0.0)).reshape(shape)


def _lofted_solid_sdf(points: np.ndarray, primitive: ShapePrimitive, rounding: float) -> np.ndarray:
    cross_sections = primitive.cross_sections or []
    if len(cross_sections) < 2:  # noqa: PLR2004
        raise _UnsupportedPrimitiveTypeError(
            f"lofted_solid primitive missing cross_sections (part={primitive.part!r})"
        )
    radius = 0.0
    for section in cross_sections:
        if not section:
            continue
        radius = max(
            radius,
            max(float(np.hypot(float(u), float(v))) for u, v in section),
        )
    inset = max(0.0, float(rounding))
    return _distance_to_section_path(points, primitive) - max(0.0, radius - inset) - inset


def _primitive_sdf(points: np.ndarray, primitive: ShapePrimitive, rounding: float) -> np.ndarray:
    if primitive.primitive_type == "box":
        return _box_sdf(points, primitive, rounding)
    if primitive.primitive_type == "cylinder":
        return _cylinder_sdf(points, primitive, rounding)
    if primitive.primitive_type == "sphere":
        return _sphere_sdf(points, primitive, rounding)
    if primitive.primitive_type == "revolved_profile":
        return _revolved_profile_sdf(points, primitive, rounding)
    if primitive.primitive_type == "extruded_profile":
        return _extruded_profile_sdf(points, primitive, rounding)
    if primitive.primitive_type == "torus":
        return _torus_sdf(points, primitive, rounding)
    if primitive.primitive_type == "subdivision_box":
        # SDF path approximates per-corner radii by the maximum corner
        # radius applied uniformly via the existing rounded-box SDF.
        radii = primitive.corner_radii or ()
        max_radius = max((float(r) for r in radii), default=0.0)
        proxy = ShapePrimitive(
            primitive_type="box",
            part=primitive.part,
            center=primitive.center,
            extents=primitive.extents,
            blend_mode=primitive.blend_mode,
            rounding=primitive.rounding,
        )
        return _box_sdf(points, proxy, rounding + max_radius)
    if primitive.primitive_type == "swept_profile":
        # SDF path is rarely hit for swept_profile — manifold/exact paths
        return _swept_profile_sdf(points, primitive, rounding)
    if primitive.primitive_type == "lofted_solid":
        # SDF path is rarely hit for lofted_solid — the ring-stitched
        # exact mesh path is preferred. Approximate with the worst-case
        # cross-section reach + section_centers path: this is a safe
        # outer envelope analogous to ``swept_profile``'s tube.
        return _lofted_solid_sdf(points, primitive, rounding)
    raise _UnsupportedPrimitiveTypeError(primitive.primitive_type)


def _region_lookup(shape_ir: ShapeIR) -> list[tuple[ShapeRegion, np.ndarray, np.ndarray]]:
    entries = []
    for region in shape_ir.regions:
        center = np.array(region.center, dtype=np.float64)
        half = np.array(region.extents, dtype=np.float64) / 2.0
        entries.append((region, center - half, center + half))
    return entries


def solid_ir_from_shape(shape_ir: ShapeIR) -> SolidIR:
    """Convert shape primitives into the stable solid IR operation list."""
    operations = []
    for primitive in shape_ir.primitives:
        params: dict[str, Any] = {
            "center": list(primitive.center),
            "axis": primitive.axis,
            "blend_mode": primitive.blend_mode,
            "rounding": primitive.rounding,
        }
        if primitive.extents is not None:
            params["extents"] = list(primitive.extents)
        if primitive.radius is not None:
            params["radius"] = primitive.radius
        if primitive.height is not None:
            params["height"] = primitive.height
        if primitive.profile_points is not None:
            params["profile_points"] = [list(point) for point in primitive.profile_points]
        if primitive.revolve_degrees is not None:
            params["revolve_degrees"] = primitive.revolve_degrees
        if primitive.revolve_start_degrees is not None:
            params["revolve_start_degrees"] = primitive.revolve_start_degrees
        if primitive.profile_polygon is not None:
            params["profile_polygon"] = [list(point) for point in primitive.profile_polygon]
        if primitive.extrude_height is not None:
            params["extrude_height"] = primitive.extrude_height
        if primitive.extrude_start_scale is not None:
            params["extrude_start_scale"] = primitive.extrude_start_scale
        if primitive.extrude_end_scale is not None:
            params["extrude_end_scale"] = primitive.extrude_end_scale
        if primitive.extrude_twist_degrees is not None:
            params["extrude_twist_degrees"] = primitive.extrude_twist_degrees
        if primitive.extrude_segments is not None:
            params["extrude_segments"] = primitive.extrude_segments
        if primitive.major_radius is not None:
            params["major_radius"] = primitive.major_radius
        if primitive.minor_radius is not None:
            params["minor_radius"] = primitive.minor_radius
        if primitive.corner_radii is not None:
            params["corner_radii"] = list(primitive.corner_radii)
            params["corner_segments"] = primitive.corner_segments
        if primitive.cross_section is not None:
            params["cross_section"] = [list(point) for point in primitive.cross_section]
        if primitive.sweep_path is not None:
            params["sweep_path"] = [list(point) for point in primitive.sweep_path]
        if primitive.boolean_seam_groups:
            params["boolean_seam_groups"] = list(primitive.boolean_seam_groups)
        if primitive.bevel_seam_groups:
            params["bevel_seam_groups"] = list(primitive.bevel_seam_groups)
        if primitive.hard_edge_groups:
            params["hard_edge_groups"] = list(primitive.hard_edge_groups)
        for modifier_attr, modifier in _primitive_v2_modifier_items(primitive):
            if modifier is not None:
                params[modifier_attr] = dict(modifier) if isinstance(modifier, dict) else modifier
        if primitive.semantic_metadata:
            params["semantic_metadata"] = dict(primitive.semantic_metadata)
        operations.append(
            SolidOp(
                op=primitive_blend_mode(primitive),
                primitive_type=primitive.primitive_type,
                part=primitive.part,
                region=primitive.region,
                component=primitive.component,
                params=params,
                tags=list(primitive.tags),
            )
        )
    return SolidIR(
        asset_name=shape_ir.asset_name,
        family=shape_ir.family,
        operations=operations,
        notes=list(shape_ir.signature.get("blueprint_notes", [])),
    )


def _primitive_part_lookup(
    shape_ir: ShapeIR,
) -> list[tuple[str, np.ndarray, np.ndarray, np.ndarray, float]]:
    """Build per-primitive (part, center, bmin, bmax, volume) entries.

    Skips ``subtract`` primitives — those carve negative space and own no
    output surfaces, so faces should never be attributed to a subtract
    primitive's part. Restricts to primitives whose AABB can be computed
    cheaply; primitives with unsupported types are skipped silently
    (callers fall back to the region-based lookup).
    """
    entries: list[tuple[str, np.ndarray, np.ndarray, np.ndarray, float]] = []
    for primitive in shape_ir.primitives:
        if primitive_blend_mode(primitive) == "subtract":
            continue
        try:
            bmin, bmax = _primitive_bounds(primitive, 0.0)
        except _UnsupportedPrimitiveTypeError:
            continue
        center = (bmin + bmax) * 0.5
        volume = float(np.prod(np.maximum(bmax - bmin, 1e-6)))
        entries.append((primitive.part, center, bmin, bmax, volume))
    return entries


def _assign_face_parts(mesh: trimesh.Trimesh, shape_ir: ShapeIR) -> list[str]:
    """Attribute each face of a fused mesh to a part name.

    Prefers per-primitive AABB attribution: each output face centroid is
    matched to the closest contributing (non-subtract) primitive whose
    bounding box contains it, falling back to the nearest primitive when
    no AABB contains the centroid. Primitive AABBs are tighter than
    blueprint regions, so this avoids the failure mode where a small
    region (e.g. ``lock_region``) extends into the body interior and
    absorbs unrelated geometry. When primitive entries are unavailable
    (e.g. unsupported primitive types upstream), falls back to the
    legacy region-based lookup so existing call sites stay safe.
    """
    centroids = np.asarray(mesh.triangles_center, dtype=np.float64)
    primitive_entries = _primitive_part_lookup(shape_ir)
    if primitive_entries:
        return _assign_face_parts_from_primitives(centroids, primitive_entries)
    return _assign_face_parts_from_regions(centroids, _region_lookup(shape_ir))


def _assign_face_parts_from_primitives(
    centroids: np.ndarray,
    entries: list[tuple[str, np.ndarray, np.ndarray, np.ndarray, float]],
) -> list[str]:
    labels: list[str] = []
    pad = 0.1  # cm — primitives already include rounding/margin upstream
    for centroid in centroids:
        inside: list[tuple[str, float]] = []
        nearest: list[tuple[str, float]] = []
        for part, center, bmin, bmax, volume in entries:
            inside_aabb = bool(
                np.all(centroid >= bmin - pad) and np.all(centroid <= bmax + pad)
            )
            if inside_aabb:
                # Distance to primitive center as the tiebreaker — picks
                # the primitive whose center the face sits closest to,
                # not whichever happens to have the smallest bbox.
                inside.append((part, float(np.linalg.norm(centroid - center))))
                continue
            extent = np.maximum((bmax - bmin) / 2.0, 1e-6)
            delta = np.abs(centroid - center) - extent
            outside = np.maximum(delta, 0.0)
            distance = float(np.linalg.norm(outside))
            nearest.append((part, distance))
        if inside:
            labels.append(min(inside, key=lambda item: item[1])[0])
        elif nearest:
            labels.append(min(nearest, key=lambda item: item[1])[0])
        else:
            labels.append("")
    return labels


def _assign_face_parts_from_regions(
    centroids: np.ndarray,
    region_entries: list[tuple[ShapeRegion, np.ndarray, np.ndarray]],
) -> list[str]:
    labels: list[str] = []
    for centroid in centroids:
        inside: list[tuple[str, float]] = []
        nearest: list[tuple[str, float]] = []
        for region, bmin, bmax in region_entries:
            extent = np.maximum((bmax - bmin) / 2.0, 1e-6)
            delta = np.abs(centroid - np.array(region.center, dtype=np.float64)) - extent
            outside = np.maximum(delta, 0.0)
            distance = float(np.linalg.norm(outside / extent))
            volume = float(np.prod(extent * 2.0))
            if np.all(centroid >= bmin - 0.6) and np.all(centroid <= bmax + 0.6):
                inside.append((region.part, volume))
            nearest.append((region.part, distance + volume * 1e-4))
        if inside:
            labels.append(min(inside, key=lambda item: item[1])[0])
        else:
            labels.append(min(nearest, key=lambda item: item[1])[0])
    return labels


def _fallback_report(reason: str) -> dict[str, str]:
    return {"mode": "constructive_fallback", "reason": reason}


def _dict_metadata(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _primitive_v2_modifier_items(primitive: ShapePrimitive) -> list[tuple[str, Any]]:
    return [
        (name, value)
        for name, value in vars(primitive).items()
        if isinstance(name, str)
        and name.startswith("v2_")
        and name.endswith("_modifier")
        and value not in (None, "", (), [], {})
    ]


def _has_v2_kernel_modifier_metadata(value: Any, *, depth: int = 0) -> bool:
    if isinstance(value, list):
        return depth <= 4 and any(
            _has_v2_kernel_modifier_metadata(item, depth=depth + 1)
            for item in value
            if isinstance(item, dict)
        )
    metadata = _dict_metadata(value)
    if not metadata or depth > 4:
        return False
    for key, item in metadata.items():
        text_key = str(key)
        if item in (None, "", (), [], {}):
            continue
        if text_key in _SHAPE_IR_V2_KERNEL_MODIFIER_ATTRS:
            return True
        if text_key.startswith("v2_") and text_key.endswith("_modifier"):
            return True
    return any(
        _has_v2_kernel_modifier_metadata(metadata.get(container), depth=depth + 1)
        for container in _SHAPE_IR_V2_KERNEL_METADATA_CONTAINERS
    )


def _primitive_has_semantic_operation(primitive: ShapePrimitive) -> bool:
    semantic_metadata = _dict_metadata(getattr(primitive, "semantic_metadata", None))
    v2_metadata = _dict_metadata(semantic_metadata.get("shape_ir_v2"))
    repair_metadata = _dict_metadata(semantic_metadata.get("semantic_repair"))
    if any(
        (
            v2_metadata.get("v2_op"),
            v2_metadata.get("operation_id"),
            repair_metadata.get("lowered_operation"),
            repair_metadata.get("operation_id"),
            semantic_metadata.get("operation"),
            semantic_metadata.get("operation_id"),
        )
    ):
        return True
    if any(str(key).startswith("v2_") for key in semantic_metadata):
        return True
    if _primitive_v2_modifier_items(primitive):
        return True
    if _has_v2_kernel_modifier_metadata(semantic_metadata):
        return True
    if int(getattr(primitive, "subdivision_levels", 0) or 0) > 0:
        return True
    if getattr(primitive, "remesh_target_edge_length_cm", None) is not None:
        return True
    return any(
        getattr(primitive, attr, None) is not None
        for attr in _SHAPE_IR_V2_KERNEL_MODIFIER_ATTRS
    )


def _shape_ir_has_semantic_operations(shape_ir: ShapeIR) -> bool:
    return any(_primitive_has_semantic_operation(primitive) for primitive in shape_ir.primitives)


def _exact_combine_mode_for_shape_ir(shape_ir: ShapeIR, config: dict[str, Any]) -> str:
    mode = str(config.get("exact_mode"))
    if mode == "component_assembly":
        signature = shape_ir.signature if isinstance(shape_ir.signature, dict) else {}
        if signature.get("kernel_program_disabled"):
            return mode
        for primitive in shape_ir.primitives:
            if primitive_blend_mode(primitive) in {"subtract", "intersect"}:
                return "kernel_program"
        if _shape_ir_has_semantic_operations(shape_ir):
            return "kernel_program"
        return mode
    if mode != "explicit_mesh":
        return mode
    signature = shape_ir.signature if isinstance(shape_ir.signature, dict) else {}
    if signature.get("kernel_program_disabled"):
        return mode
    for primitive in shape_ir.primitives:
        if primitive_blend_mode(primitive) in {"subtract", "intersect"}:
            return "kernel_program"
    if _shape_ir_has_semantic_operations(shape_ir):
        return "kernel_program"
    return mode


def _compile_exact_mesh_ir(
    shape_ir: ShapeIR,
    fidelity: FidelityProfile,
    config: dict[str, Any],
) -> tuple[MeshIR, dict[str, Any]]:
    mesh, face_parts, exact_report = compile_explicit_surface_mesh(
        shape_ir,
        fidelity,
        combine_mode=_exact_combine_mode_for_shape_ir(shape_ir, config),
    )
    if not face_parts or len(face_parts) != len(mesh.faces):
        face_parts = _assign_face_parts(mesh, shape_ir)
    solid_ir = solid_ir_from_shape(shape_ir)
    report = {
        **exact_report,
        "search_mode": "parametric_exact_assembly",
        "hero_family": bool(config["hero_family"]),
        "intent_driven_exact": bool(config.get("intent_driven_exact")),
        "exact_reason": config.get("exact_reason"),
        "exact_mode": config.get("exact_mode"),
        "meshing_strategy": config.get("meshing_strategy"),
        "solid_ir": solid_ir.to_dict(),
        "cache_hit": False,
    }
    mesh_ir = finalize_mesh_ir(mesh, shape_ir, face_parts, metadata={"integration_report": report})
    return mesh_ir, report


def _fusion_cache_key(
    shape_ir: ShapeIR,
    fidelity: FidelityProfile,
    primitives: list[ShapePrimitive],
) -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "family": shape_ir.family,
                "fidelity": fidelity.to_dict(),
                "primitives": [primitive.to_dict() for primitive in primitives],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _cached_fusion(cache_key: str) -> tuple[MeshIR, dict[str, Any]] | None:
    if cache_key not in _FUSION_CACHE:
        return None
    mesh_ir_payload, report = _FUSION_CACHE[cache_key]
    # JSON ingress is an internal in-memory deep copy of our own cache entry.
    return MeshIR(**json.loads(json.dumps(mesh_ir_payload))), {**report, "cache_hit": True}


def _fusion_grid(
    primitives: list[ShapePrimitive],
    fidelity: FidelityProfile,
    pitch: float,
) -> tuple[np.ndarray, np.ndarray, float]:
    bounds = [
        _primitive_bounds(primitive, primitive_rounding(primitive, fidelity)) for primitive in primitives
    ]
    bounds_min = np.min([item[0] for item in bounds], axis=0)
    bounds_max = np.max([item[1] for item in bounds], axis=0)
    margin = max(2.0, pitch * 3.0)
    origin = bounds_min - margin
    top = bounds_max + margin
    dims = np.maximum(np.ceil((top - origin) / pitch).astype(int) + 1, 4)
    voxel_count = np.prod(dims)
    if voxel_count > MAX_FUSION_VOXELS:
        scale = (voxel_count / MAX_FUSION_VOXELS) ** (1 / 3)
        pitch *= float(scale)
        dims = np.maximum(np.ceil((top - origin) / pitch).astype(int) + 1, 4)
    return origin, dims, pitch


def _field_axes(
    origin: np.ndarray, dims: np.ndarray, pitch: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x_axis = origin[0] + np.arange(dims[0], dtype=np.float32) * pitch
    y_axis = origin[1] + np.arange(dims[1], dtype=np.float32) * pitch
    z_axis = origin[2] + np.arange(dims[2], dtype=np.float32) * pitch
    return x_axis, y_axis, z_axis


def _apply_primitive_to_field(
    field: np.ndarray,
    axes: tuple[np.ndarray, np.ndarray, np.ndarray],
    origin: np.ndarray,
    dims: np.ndarray,
    pitch: float,
    primitive: ShapePrimitive,
    fidelity: FidelityProfile,
) -> None:
    rounding = primitive_rounding(primitive, fidelity)
    bmin, bmax = _primitive_bounds(primitive, rounding)
    lo = np.maximum(np.floor((bmin - origin) / pitch).astype(int) - 1, 0)
    hi = np.minimum(np.ceil((bmax - origin) / pitch).astype(int) + 2, dims)
    x_axis, y_axis, z_axis = axes
    xx, yy, zz = np.meshgrid(
        x_axis[lo[0] : hi[0]],
        y_axis[lo[1] : hi[1]],
        z_axis[lo[2] : hi[2]],
        indexing="ij",
    )
    points = np.stack([xx, yy, zz], axis=-1)
    sdf = _primitive_sdf(points, primitive, rounding).astype(np.float32)
    field_slice = (slice(lo[0], hi[0]), slice(lo[1], hi[1]), slice(lo[2], hi[2]))
    target = field[field_slice]
    if primitive_blend_mode(primitive) == "subtract":
        field[field_slice] = np.maximum(target, -sdf)
    else:
        field[field_slice] = np.minimum(target, sdf)


def _mesh_from_field(
    field: np.ndarray,
    origin: np.ndarray,
    pitch: float,
    config: dict[str, Any],
) -> tuple[trimesh.Trimesh, float] | None:
    sigma = float(config["blur_sigma"])
    if sigma > 0:
        field = gaussian_filter(field, sigma=sigma)
    matrix = field < 0.0
    if not np.any(matrix):
        return None
    mesh = matrix_to_marching_cubes(matrix, pitch=pitch)
    mesh.apply_translation(origin)
    mesh.remove_infinite_values()
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()
    # trimesh.process(validate=True) can raise on malformed topology;
    # remove_/merge_ above have already done the essential cleanup.
    with suppress(ValueError, RuntimeError, AttributeError, IndexError):
        mesh.process(validate=True)
    return mesh, sigma


def _finalize_fused_mesh_ir(
    mesh: trimesh.Trimesh,
    shape_ir: ShapeIR,
    fidelity: FidelityProfile,
    config: dict[str, Any],
    primitives: list[ShapePrimitive],
    pitch: float,
    dims: np.ndarray,
    sigma: float,
) -> tuple[MeshIR, dict[str, Any]]:
    exact_report: dict[str, Any] | None = None
    if config.get("exact_finalize"):
        mesh, exact_report = exactify_surface_mesh(mesh, shape_ir, fidelity)
    face_parts = _assign_face_parts(mesh, shape_ir)
    solid_ir = solid_ir_from_shape(shape_ir)
    report = {
        "mode": "exact_surface_finalize" if exact_report else "sdf_voxel_fusion",
        "search_mode": "sdf_voxel_fusion",
        "pitch": round(pitch, 6),
        "blur_sigma": sigma,
        "dims": [int(value) for value in dims],
        "hero_family": bool(config["hero_family"]),
        "intent_driven_exact": bool(config.get("intent_driven_exact")),
        "exact_reason": config.get("exact_reason"),
        "exact_mode": config.get("exact_mode"),
        "meshing_strategy": config.get("meshing_strategy"),
        "primitive_count": len(primitives),
        "cache_hit": False,
        "solid_ir": solid_ir.to_dict(),
    }
    if exact_report:
        report["exact_report"] = exact_report
    mesh_ir = finalize_mesh_ir(mesh, shape_ir, face_parts, metadata={"integration_report": report})
    return mesh_ir, report


def fuse_shape_ir(shape_ir: ShapeIR, fidelity: FidelityProfile) -> tuple[MeshIR | None, dict[str, Any]]:
    """Fuse shape primitives into a mesh IR and integration report."""
    meshing_strategy = (
        shape_ir.signature.get("meshing_strategy") if shape_ir.signature else None
    )
    config = integration_config_for_family(
        shape_ir.family,
        fidelity,
        meshing_strategy=meshing_strategy,
        primitives=list(shape_ir.primitives),
        shape_signature=shape_ir.signature,
        shape_assessment=shape_ir.assessment,
    )
    if not config["enabled"]:
        return None, _fallback_report("integration disabled for this family/fidelity")

    primitives = list(shape_ir.primitives)
    if not primitives:
        return None, _fallback_report("no primitives")

    if config.get("exact_mode") in {"explicit_mesh", "component_assembly"}:
        return _compile_exact_mesh_ir(shape_ir, fidelity, config)

    cache_key = _fusion_cache_key(shape_ir, fidelity, primitives)
    cached = _cached_fusion(cache_key)
    if cached is not None:
        return cached

    origin, dims, pitch = _fusion_grid(primitives, fidelity, float(config["pitch"]))

    field = np.full(tuple(int(value) for value in dims), 9_999.0, dtype=np.float32)
    axes = _field_axes(origin, dims, pitch)
    for primitive in primitives:
        _apply_primitive_to_field(field, axes, origin, dims, pitch, primitive, fidelity)

    mesh_result = _mesh_from_field(field, origin, pitch, config)
    if mesh_result is None:
        return None, _fallback_report("empty_fusion_volume")
    mesh, sigma = mesh_result
    mesh_ir, report = _finalize_fused_mesh_ir(
        mesh,
        shape_ir,
        fidelity,
        config,
        primitives,
        pitch,
        dims,
        sigma,
    )
    _FUSION_CACHE[cache_key] = (mesh_ir.to_dict(), dict(report))
    return mesh_ir, report
