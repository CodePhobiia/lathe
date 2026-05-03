"""Exact constructive solids helpers for ShapeIR primitive meshes."""

from __future__ import annotations

from collections.abc import Iterable
from contextlib import suppress

import numpy as np
import trimesh

from .errors import ContractViolation
from .fidelity import FidelityProfile
from .shape_ir import ShapeIR, ShapePrimitive

NUMERIC_EPSILON = 1e-6


def _missing_box_extents_error(primitive: ShapePrimitive) -> ContractViolation:
    return ContractViolation(
        f"invariant violation: box ShapePrimitive requires extents, got None (part={primitive.part!r})"
    )


def _missing_cylinder_dimensions_error(primitive: ShapePrimitive) -> ContractViolation:
    return ContractViolation(
        "invariant violation: cylinder ShapePrimitive requires radius and height, "
        f"got radius={primitive.radius!r}, height={primitive.height!r} "
        f"(part={primitive.part!r})"
    )


def _missing_revolved_profile_points_error(primitive: ShapePrimitive) -> ContractViolation:
    return ContractViolation(
        "invariant violation: revolved_profile ShapePrimitive requires "
        f"profile_points (>= 1 point), got {primitive.profile_points!r} "
        f"(part={primitive.part!r})"
    )


def _missing_extruded_profile_polygon_error(primitive: ShapePrimitive) -> ContractViolation:
    return ContractViolation(
        "invariant violation: extruded_profile ShapePrimitive requires "
        f"profile_polygon (>= 3 CCW points), got {primitive.profile_polygon!r} "
        f"(part={primitive.part!r})"
    )


def _missing_extruded_profile_height_error(primitive: ShapePrimitive) -> ContractViolation:
    return ContractViolation(
        "invariant violation: extruded_profile ShapePrimitive requires "
        f"extrude_height (> 0), got {primitive.extrude_height!r} "
        f"(part={primitive.part!r})"
    )


def _unsupported_primitive_type_error(primitive_type: str) -> ValueError:
    return ValueError(f"Unsupported primitive type '{primitive_type}'")


def _box_surface_point(point: np.ndarray, primitive: ShapePrimitive) -> np.ndarray:
    if primitive.extents is None:
        raise _missing_box_extents_error(primitive)
    center = np.asarray(primitive.center, dtype=np.float64)
    half = np.asarray(primitive.extents, dtype=np.float64) / 2.0
    local = point - center
    clipped = np.clip(local, -half, half)
    if np.all(np.abs(local) <= half + NUMERIC_EPSILON):
        slack = half - np.abs(local)
        axis = int(np.argmin(slack))
        clipped[axis] = (1.0 if local[axis] >= 0.0 else -1.0) * half[axis]
    return center + clipped


def _cylinder_surface_point(point: np.ndarray, primitive: ShapePrimitive) -> np.ndarray:
    if primitive.radius is None or primitive.height is None:
        raise _missing_cylinder_dimensions_error(primitive)
    center = np.asarray(primitive.center, dtype=np.float64)
    local = point - center
    radius = float(primitive.radius)
    half_height = float(primitive.height) / 2.0
    if primitive.axis == "x":
        axial = local[0]
        radial = np.asarray([local[1], local[2]], dtype=np.float64)

        def to_world(axial_value: float, radial_value: np.ndarray) -> np.ndarray:
            return center + np.asarray([axial_value, radial_value[0], radial_value[1]], dtype=np.float64)

    elif primitive.axis == "z":
        axial = local[2]
        radial = np.asarray([local[0], local[1]], dtype=np.float64)

        def to_world(axial_value: float, radial_value: np.ndarray) -> np.ndarray:
            return center + np.asarray([radial_value[0], radial_value[1], axial_value], dtype=np.float64)

    else:
        axial = local[1]
        radial = np.asarray([local[0], local[2]], dtype=np.float64)

        def to_world(axial_value: float, radial_value: np.ndarray) -> np.ndarray:
            return center + np.asarray([radial_value[0], axial_value, radial_value[1]], dtype=np.float64)

    radial_norm = float(np.linalg.norm(radial))
    radial_dir = (
        radial / radial_norm if radial_norm > NUMERIC_EPSILON else np.asarray([1.0, 0.0], dtype=np.float64)
    )
    side_point = to_world(float(np.clip(axial, -half_height, half_height)), radial_dir * radius)
    cap_radial = radial if radial_norm <= radius else radial_dir * radius
    cap_point = to_world((1.0 if axial >= 0.0 else -1.0) * half_height, cap_radial)
    return (
        side_point if np.linalg.norm(point - side_point) <= np.linalg.norm(point - cap_point) else cap_point
    )


def _primitive_surface_point(point: np.ndarray, primitive: ShapePrimitive) -> np.ndarray:
    if primitive.primitive_type == "box":
        return _box_surface_point(point, primitive)
    if primitive.primitive_type == "cylinder":
        return _cylinder_surface_point(point, primitive)
    if primitive.primitive_type == "revolved_profile":
        # Use the bounding cylinder for surface-snap projection. Snapping
        # to the exact swept surface would require sampling the profile
        # polyline; the bounding cylinder is a safe under-approximation
        # that pulls vertices roughly toward the silhouette without
        # introducing oscillation. Hero exactification can be added in a
        # follow-up.
        return _cylinder_surface_point(point, _revolved_profile_bounding_cylinder(primitive))
    if primitive.primitive_type == "extruded_profile":
        # Use the bounding cylinder around the polygon's circumradius for
        # surface-snap projection. Snapping to the exact prismatic faces
        # would require per-edge plane projection; the circumscribing
        # cylinder is a safe outer envelope that matches the
        # revolved_profile fallback strategy.
        return _cylinder_surface_point(point, _extruded_profile_bounding_cylinder(primitive))
    raise _unsupported_primitive_type_error(primitive.primitive_type)


def _revolved_profile_bounding_cylinder(primitive: ShapePrimitive) -> ShapePrimitive:
    """Coerce a revolved_profile primitive into a bounding cylinder for snap fallbacks."""
    radius, height = _revolved_profile_extents(primitive)
    return ShapePrimitive(
        primitive_type="cylinder",
        part=primitive.part,
        center=primitive.center,
        radius=radius,
        height=height,
        axis=primitive.axis,
        component=primitive.component,
        region=primitive.region,
        blend_mode=primitive.blend_mode,
        rounding=primitive.rounding,
    )


def _revolved_profile_extents(primitive: ShapePrimitive) -> tuple[float, float]:
    """Return (max_radius, axial_height) of a revolved_profile primitive."""
    points = primitive.profile_points or []
    if not points:
        raise _missing_revolved_profile_points_error(primitive)
    axials = [float(a) for a, _ in points]
    radials = [abs(float(r)) for _, r in points]
    return max(radials), max(axials) - min(axials)


def _extruded_profile_polygon_bbox(
    primitive: ShapePrimitive,
) -> tuple[float, float, float, float]:
    """Return (umin, umax, vmin, vmax) of the cross-section polygon."""
    polygon = primitive.profile_polygon or []
    if len(polygon) < 3:  # noqa: PLR2004
        raise _missing_extruded_profile_polygon_error(primitive)
    us = [float(u) for u, _ in polygon]
    vs = [float(v) for _, v in polygon]
    return min(us), max(us), min(vs), max(vs)


def _extruded_profile_circumradius(primitive: ShapePrimitive) -> float:
    """Return the largest distance from the polygon centroid to any vertex."""
    polygon = primitive.profile_polygon or []
    if len(polygon) < 3:  # noqa: PLR2004
        raise _missing_extruded_profile_polygon_error(primitive)
    cu = sum(float(u) for u, _ in polygon) / len(polygon)
    cv = sum(float(v) for _, v in polygon) / len(polygon)
    return max(((float(u) - cu) ** 2 + (float(v) - cv) ** 2) ** 0.5 for u, v in polygon)


def _extruded_profile_bounding_cylinder(primitive: ShapePrimitive) -> ShapePrimitive:
    """Coerce an extruded_profile primitive into a bounding cylinder for snap fallbacks."""
    if primitive.extrude_height is None or float(primitive.extrude_height) <= 0.0:
        raise _missing_extruded_profile_height_error(primitive)
    radius = _extruded_profile_circumradius(primitive)
    return ShapePrimitive(
        primitive_type="cylinder",
        part=primitive.part,
        center=primitive.center,
        radius=float(radius),
        height=float(primitive.extrude_height),
        axis=primitive.axis,
        component=primitive.component,
        region=primitive.region,
        blend_mode=primitive.blend_mode,
        rounding=primitive.rounding,
    )


def _translated_box(
    extents: tuple[float, float, float], center: tuple[float, float, float]
) -> trimesh.Trimesh:
    matrix = np.eye(4)
    matrix[:3, 3] = np.asarray(center, dtype=np.float64)
    return trimesh.creation.box(extents=np.asarray(extents, dtype=np.float64), transform=matrix)


def _translated_cylinder(
    radius: float, height: float, center: tuple[float, float, float], axis: str
) -> trimesh.Trimesh:
    sections = 56
    mesh = trimesh.creation.cylinder(radius=radius, height=height, sections=sections)
    if axis == "y":
        mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2.0, [1.0, 0.0, 0.0]))
    elif axis == "x":
        mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2.0, [0.0, 1.0, 0.0]))
    matrix = np.eye(4)
    matrix[:3, 3] = np.asarray(center, dtype=np.float64)
    mesh.apply_transform(matrix)
    return mesh


def _rounded_box_mesh(
    extents: tuple[float, float, float],
    center: tuple[float, float, float],
    *,
    radius: float,
    segments: int,
) -> trimesh.Trimesh:
    half = np.asarray(extents, dtype=np.float64) / 2.0
    radius = min(max(float(radius), 0.0), float(np.min(half)) * 0.92)
    if radius <= NUMERIC_EPSILON:
        return _translated_box(extents, center)

    steps = max(1, min(6, int(segments)))
    points: list[tuple[float, float, float]] = []
    core = np.maximum(half - radius, NUMERIC_EPSILON)
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            for sz in (-1.0, 1.0):
                base = np.asarray([sx * core[0], sy * core[1], sz * core[2]], dtype=np.float64)
                for theta_i in range(steps + 1):
                    theta = (np.pi / 2.0) * theta_i / steps
                    for phi_i in range(steps + 1):
                        phi = (np.pi / 2.0) * phi_i / steps
                        direction = np.asarray(
                            [
                                sx * np.cos(theta) * np.cos(phi),
                                sy * np.sin(theta) * np.cos(phi),
                                sz * np.sin(phi),
                            ],
                            dtype=np.float64,
                        )
                        point = base + radius * direction
                        points.append((float(point[0]), float(point[1]), float(point[2])))
    cloud = trimesh.Trimesh(vertices=np.asarray(points, dtype=np.float64), faces=None, process=False)
    mesh = cloud.convex_hull
    mesh.apply_translation(np.asarray(center, dtype=np.float64))
    mesh.remove_unreferenced_vertices()
    mesh.fix_normals()
    return mesh


def _rounding_segments(primitive: ShapePrimitive) -> int:
    for tag in primitive.tags:
        text = str(tag)
        if text.startswith("bevel_segments_") or text.startswith("chamfer_segments_"):
            try:
                return int(text.rsplit("_", 1)[-1])
            except ValueError:
                return 3
    return 3


def _primitive_mesh(primitive: ShapePrimitive) -> trimesh.Trimesh:
    if primitive.primitive_type == "box":
        if primitive.extents is None:
            raise _missing_box_extents_error(primitive)
        if float(primitive.rounding or 0.0) > NUMERIC_EPSILON:
            return _rounded_box_mesh(
                primitive.extents,
                primitive.center,
                radius=float(primitive.rounding or 0.0),
                segments=_rounding_segments(primitive),
            )
        return _translated_box(primitive.extents, primitive.center)
    if primitive.primitive_type == "cylinder":
        if primitive.radius is None or primitive.height is None:
            raise _missing_cylinder_dimensions_error(primitive)
        return _translated_cylinder(
            float(primitive.radius), float(primitive.height), primitive.center, primitive.axis
        )
    if primitive.primitive_type == "revolved_profile":
        return _revolved_profile_mesh(primitive)
    if primitive.primitive_type == "extruded_profile":
        return _extruded_profile_mesh(primitive)
    raise _unsupported_primitive_type_error(primitive.primitive_type)


def _revolved_profile_mesh(primitive: ShapePrimitive) -> trimesh.Trimesh:
    """Build a solid-of-revolution trimesh from a 2D (axial, radial) profile.

    The profile is revolved 360° around ``primitive.axis`` through
    ``primitive.center``. The polyline is automatically closed back to the
    axis (radial=0) at both ends so the result is watertight even when the
    author specified an open profile.
    """
    points = primitive.profile_points or []
    if not points:
        raise _missing_revolved_profile_points_error(primitive)
    sections = max(16, min(96, _rounding_segments(primitive) * 16))

    # Build a closed profile in (radial, axial) form because trimesh's
    # ``revolve`` revolves the 2D Y-axis into the 3D Z-axis (matching
    # manifold3d's convention). Snap the first/last points back to the
    # axis (radial=0) to guarantee watertightness.
    profile: list[tuple[float, float]] = []
    first_axial = float(points[0][0])
    last_axial = float(points[-1][0])
    profile.append((0.0, first_axial))
    for axial, radial in points:
        profile.append((max(0.0, float(radial)), float(axial)))
    profile.append((0.0, last_axial))

    linestring = np.asarray(profile, dtype=np.float64)
    mesh = trimesh.creation.revolve(linestring, sections=sections)

    # trimesh.creation.revolve emits the result aligned to 3D Z. Rotate to
    # the requested axis, then translate to the primitive's center.
    if primitive.axis == "x":
        mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2.0, [0.0, 1.0, 0.0]))
    elif primitive.axis == "y":
        mesh.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2.0, [1.0, 0.0, 0.0]))
    matrix = np.eye(4)
    matrix[:3, 3] = np.asarray(primitive.center, dtype=np.float64)
    mesh.apply_transform(matrix)
    mesh.fix_normals()
    return mesh


def _extruded_profile_mesh(primitive: ShapePrimitive) -> trimesh.Trimesh:
    """Build a prismatic trimesh by linearly extruding a 2D polygon.

    The polygon (``profile_polygon``, CCW (u, v) points in the
    cross-section plane) is swept ``extrude_height`` along
    ``primitive.axis`` through ``primitive.center``. The polygon is
    triangulated by shapely and capped at both ends so the result is
    watertight.
    """
    polygon = primitive.profile_polygon or []
    if len(polygon) < 3:  # noqa: PLR2004
        raise _missing_extruded_profile_polygon_error(primitive)
    if primitive.extrude_height is None or float(primitive.extrude_height) <= 0.0:
        raise _missing_extruded_profile_height_error(primitive)

    from shapely.geometry import Polygon  # local import: shapely is optional outside this path

    coords = [(float(u), float(v)) for u, v in polygon]
    shape_polygon = Polygon(coords)
    if not shape_polygon.is_valid:
        # Triangulation requires a simple, non-self-intersecting polygon;
        # ``buffer(0)`` is shapely's idiomatic repair for near-degenerate
        # CCW input that the user supplied with redundant vertices.
        shape_polygon = shape_polygon.buffer(0)
    height = float(primitive.extrude_height)
    mesh = trimesh.creation.extrude_polygon(shape_polygon, height)

    # ``extrude_polygon`` extrudes along +Z starting at z=0; recenter to
    # z=0 so the primitive's ``center`` translates the geometric center.
    mesh.apply_translation(np.asarray([0.0, 0.0, -height / 2.0], dtype=np.float64))

    # Rotate so the extrusion axis matches ``primitive.axis``.
    if primitive.axis == "x":
        mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2.0, [0.0, 1.0, 0.0]))
    elif primitive.axis == "y":
        mesh.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2.0, [1.0, 0.0, 0.0]))

    matrix = np.eye(4)
    matrix[:3, 3] = np.asarray(primitive.center, dtype=np.float64)
    mesh.apply_transform(matrix)
    mesh.fix_normals()
    return mesh


def primitive_mesh(primitive: ShapePrimitive) -> trimesh.Trimesh:
    """Compile one ShapePrimitive into its visible mesh surface."""
    return _primitive_mesh(primitive)


def compile_explicit_surface_mesh(
    shape_ir: ShapeIR,
    fidelity: FidelityProfile,
    *,
    combine_mode: str = "explicit_mesh",
) -> tuple[trimesh.Trimesh, list[str], dict[str, float | int | str]]:
    """Compile ShapeIR primitives into an explicit trimesh surface mesh."""
    meshes: list[trimesh.Trimesh] = []
    face_parts: list[str] = []
    for primitive in shape_ir.primitives:
        mesh = _primitive_mesh(primitive)
        meshes.append(mesh)
        face_parts.extend([primitive.part] * len(mesh.faces))

    if not meshes:
        return trimesh.Trimesh(), [], {"mode": "exact_explicit_assembly", "primitive_count": 0}

    mode = "exact_explicit_assembly"
    face_parts_out = list(face_parts)
    if len(meshes) > 1 and combine_mode != "component_assembly":
        try:
            unioned = trimesh.boolean.union(meshes)
            if isinstance(unioned, trimesh.Trimesh) and len(unioned.faces) > 0:
                combined = unioned.copy()
                face_parts_out = []
                mode = "exact_boolean_union"
            else:
                combined = trimesh.util.concatenate(meshes)
        except (ValueError, RuntimeError, AttributeError, IndexError, OSError):
            # trimesh.boolean.union delegates to blender/manifold/openscad
            # engines — each can fail with its own exception class. Fall
            # back to deterministic concatenation.
            combined = trimesh.util.concatenate(meshes)
    else:
        combined = trimesh.util.concatenate(meshes) if len(meshes) > 1 else meshes[0].copy()
        if combine_mode == "component_assembly":
            mode = "exact_component_assembly"
    combined.remove_infinite_values()
    combined.remove_unreferenced_vertices()
    combined.merge_vertices()
    combined.fix_normals()
    if fidelity.tier == "hero":
        with suppress(ValueError, RuntimeError, AttributeError, IndexError):
            trimesh.smoothing.filter_taubin(combined, lamb=0.18, nu=-0.19, iterations=1)
            combined.fix_normals()
    report = {
        "mode": mode,
        "primitive_count": len(shape_ir.primitives),
        "triangle_count": len(combined.faces),
        "vertex_count": len(combined.vertices),
    }
    return combined, face_parts_out, report


def _primitive_bounds(primitive: ShapePrimitive, margin: float) -> tuple[np.ndarray, np.ndarray]:
    center = np.asarray(primitive.center, dtype=np.float64)
    if primitive.primitive_type == "box":
        if primitive.extents is None:
            raise _missing_box_extents_error(primitive)
        half = np.asarray(primitive.extents, dtype=np.float64) / 2.0 + margin
    elif primitive.primitive_type == "cylinder":
        if primitive.radius is None or primitive.height is None:
            raise _missing_cylinder_dimensions_error(primitive)
        radius = float(primitive.radius) + margin
        half_height = float(primitive.height) / 2.0 + margin
        if primitive.axis == "x":
            half = np.asarray([half_height, radius, radius], dtype=np.float64)
        elif primitive.axis == "z":
            half = np.asarray([radius, radius, half_height], dtype=np.float64)
        else:
            half = np.asarray([radius, half_height, radius], dtype=np.float64)
    elif primitive.primitive_type == "revolved_profile":
        radius, height = _revolved_profile_extents(primitive)
        radius = radius + margin
        half_height = height / 2.0 + margin
        if primitive.axis == "x":
            half = np.asarray([half_height, radius, radius], dtype=np.float64)
        elif primitive.axis == "z":
            half = np.asarray([radius, radius, half_height], dtype=np.float64)
        else:
            half = np.asarray([radius, half_height, radius], dtype=np.float64)
    elif primitive.primitive_type == "extruded_profile":
        # AABB derived from the polygon's 2D bbox (in the cross-section
        # plane) plus the extrude_height along ``axis``.
        umin, umax, vmin, vmax = _extruded_profile_polygon_bbox(primitive)
        if primitive.extrude_height is None or float(primitive.extrude_height) <= 0.0:
            raise _missing_extruded_profile_height_error(primitive)
        half_axial = float(primitive.extrude_height) / 2.0 + margin
        half_u = (umax - umin) / 2.0 + margin
        half_v = (vmax - vmin) / 2.0 + margin
        if primitive.axis == "x":
            half = np.asarray([half_axial, half_u, half_v], dtype=np.float64)
        elif primitive.axis == "z":
            half = np.asarray([half_u, half_v, half_axial], dtype=np.float64)
        else:
            half = np.asarray([half_u, half_axial, half_v], dtype=np.float64)
    else:
        raise _unsupported_primitive_type_error(primitive.primitive_type)
    return center - half, center + half


def _iter_candidate_primitives(
    shape_ir: ShapeIR, margin: float
) -> Iterable[tuple[ShapePrimitive, np.ndarray, np.ndarray]]:
    for primitive in shape_ir.primitives:
        bounds_min, bounds_max = _primitive_bounds(primitive, margin)
        yield primitive, bounds_min, bounds_max


def exactify_surface_mesh(
    mesh: trimesh.Trimesh, shape_ir: ShapeIR, fidelity: FidelityProfile
) -> tuple[trimesh.Trimesh, dict[str, float | int]]:
    """Snap a mesh toward the exact primitive surfaces described by ShapeIR."""
    refined = mesh.copy()
    if len(refined.vertices) == 0 or len(shape_ir.primitives) == 0:
        return refined, {"projection_iterations": 0, "mean_vertex_shift": 0.0, "max_vertex_shift": 0.0}

    snap_radius = max(
        1.5, float(np.linalg.norm(refined.extents)) * (0.030 if fidelity.tier == "hero" else 0.022)
    )
    blend = 0.78 if fidelity.tier == "hero" else 0.62
    iterations = 2 if fidelity.tier == "hero" else 1
    margin = snap_radius * 0.8

    with suppress(ValueError, RuntimeError, AttributeError, IndexError):
        trimesh.smoothing.filter_taubin(
            refined, lamb=0.35, nu=-0.37, iterations=4 if fidelity.tier == "hero" else 2
        )

    vertices = np.asarray(refined.vertices, dtype=np.float64)
    shifts: list[float] = []
    primitive_bounds = list(_iter_candidate_primitives(shape_ir, margin))
    for _ in range(iterations):
        updated = vertices.copy()
        for index, vertex in enumerate(vertices):
            best_point: np.ndarray | None = None
            best_distance = snap_radius
            for primitive, bounds_min, bounds_max in primitive_bounds:
                if np.any(vertex < bounds_min) or np.any(vertex > bounds_max):
                    continue
                candidate = _primitive_surface_point(vertex, primitive)
                distance = float(np.linalg.norm(vertex - candidate))
                if distance < best_distance:
                    best_distance = distance
                    best_point = candidate
            if best_point is None:
                continue
            snapped = vertex * (1.0 - blend) + best_point * blend
            updated[index] = snapped
            shifts.append(float(np.linalg.norm(snapped - vertex)))
        vertices = updated

    refined.vertices = vertices
    refined.remove_infinite_values()
    refined.remove_unreferenced_vertices()
    refined.merge_vertices()
    with suppress(ValueError, RuntimeError, AttributeError, IndexError):
        refined.process(validate=True)
    refined.fix_normals()
    return refined, {
        "projection_iterations": iterations,
        "snap_radius": round(float(snap_radius), 6),
        "mean_vertex_shift": round(float(np.mean(shifts)) if shifts else 0.0, 6),
        "max_vertex_shift": round(float(np.max(shifts)) if shifts else 0.0, 6),
    }
