from __future__ import annotations

from typing import Iterable

import numpy as np
import trimesh

from .errors import ContractViolation
from .fidelity import FidelityProfile
from .shape_ir import ShapeIR, ShapePrimitive


def _box_surface_point(point: np.ndarray, primitive: ShapePrimitive) -> np.ndarray:
    if primitive.extents is None:
        raise ContractViolation(
            f"invariant violation: box ShapePrimitive requires extents, got None (part={primitive.part!r})"
        )
    center = np.asarray(primitive.center, dtype=np.float64)
    half = np.asarray(primitive.extents, dtype=np.float64) / 2.0
    local = point - center
    clipped = np.clip(local, -half, half)
    if np.all(np.abs(local) <= half + 1e-6):
        slack = half - np.abs(local)
        axis = int(np.argmin(slack))
        clipped[axis] = (1.0 if local[axis] >= 0.0 else -1.0) * half[axis]
    return center + clipped


def _cylinder_surface_point(point: np.ndarray, primitive: ShapePrimitive) -> np.ndarray:
    if primitive.radius is None or primitive.height is None:
        raise ContractViolation(
            f"invariant violation: cylinder ShapePrimitive requires radius and height, "
            f"got radius={primitive.radius!r}, height={primitive.height!r} (part={primitive.part!r})"
        )
    center = np.asarray(primitive.center, dtype=np.float64)
    local = point - center
    radius = float(primitive.radius)
    half_height = float(primitive.height) / 2.0
    if primitive.axis == "x":
        axial = local[0]
        radial = np.asarray([local[1], local[2]], dtype=np.float64)
        to_world = lambda axial_value, radial_value: center + np.asarray([axial_value, radial_value[0], radial_value[1]], dtype=np.float64)
    elif primitive.axis == "z":
        axial = local[2]
        radial = np.asarray([local[0], local[1]], dtype=np.float64)
        to_world = lambda axial_value, radial_value: center + np.asarray([radial_value[0], radial_value[1], axial_value], dtype=np.float64)
    else:
        axial = local[1]
        radial = np.asarray([local[0], local[2]], dtype=np.float64)
        to_world = lambda axial_value, radial_value: center + np.asarray([radial_value[0], axial_value, radial_value[1]], dtype=np.float64)

    radial_norm = float(np.linalg.norm(radial))
    radial_dir = radial / radial_norm if radial_norm > 1e-6 else np.asarray([1.0, 0.0], dtype=np.float64)
    side_point = to_world(float(np.clip(axial, -half_height, half_height)), radial_dir * radius)
    cap_radial = radial if radial_norm <= radius else radial_dir * radius
    cap_point = to_world((1.0 if axial >= 0.0 else -1.0) * half_height, cap_radial)
    return side_point if np.linalg.norm(point - side_point) <= np.linalg.norm(point - cap_point) else cap_point


def _primitive_surface_point(point: np.ndarray, primitive: ShapePrimitive) -> np.ndarray:
    if primitive.primitive_type == "box":
        return _box_surface_point(point, primitive)
    if primitive.primitive_type == "cylinder":
        return _cylinder_surface_point(point, primitive)
    raise ValueError(f"Unsupported primitive type '{primitive.primitive_type}'")


def _translated_box(extents: tuple[float, float, float], center: tuple[float, float, float]) -> trimesh.Trimesh:
    matrix = np.eye(4)
    matrix[:3, 3] = np.asarray(center, dtype=np.float64)
    return trimesh.creation.box(extents=np.asarray(extents, dtype=np.float64), transform=matrix)


def _translated_cylinder(radius: float, height: float, center: tuple[float, float, float], axis: str) -> trimesh.Trimesh:
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


def _primitive_mesh(primitive: ShapePrimitive) -> trimesh.Trimesh:
    if primitive.primitive_type == "box":
        if primitive.extents is None:
            raise ContractViolation(
                f"invariant violation: box ShapePrimitive requires extents, got None (part={primitive.part!r})"
            )
        return _translated_box(primitive.extents, primitive.center)
    if primitive.primitive_type == "cylinder":
        if primitive.radius is None or primitive.height is None:
            raise ContractViolation(
                f"invariant violation: cylinder ShapePrimitive requires radius and height, "
                f"got radius={primitive.radius!r}, height={primitive.height!r} (part={primitive.part!r})"
            )
        return _translated_cylinder(float(primitive.radius), float(primitive.height), primitive.center, primitive.axis)
    raise ValueError(f"Unsupported primitive type '{primitive.primitive_type}'")


def compile_explicit_surface_mesh(
    shape_ir: ShapeIR,
    fidelity: FidelityProfile,
    *,
    combine_mode: str = "explicit_mesh",
) -> tuple[trimesh.Trimesh, list[str], dict[str, float | int | str]]:
    meshes: list[trimesh.Trimesh] = []
    face_parts: list[str] = []
    for primitive in shape_ir.primitives:
        mesh = _primitive_mesh(primitive)
        meshes.append(mesh)
        face_parts.extend([primitive.part] * int(len(mesh.faces)))

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
        try:
            trimesh.smoothing.filter_taubin(combined, lamb=0.18, nu=-0.19, iterations=1)
            combined.fix_normals()
        except (ValueError, RuntimeError, AttributeError, IndexError):
            # Taubin smoothing fails on degenerate / non-manifold topology.
            pass
    report = {
        "mode": mode,
        "primitive_count": len(shape_ir.primitives),
        "triangle_count": int(len(combined.faces)),
        "vertex_count": int(len(combined.vertices)),
    }
    return combined, face_parts_out, report


def _primitive_bounds(primitive: ShapePrimitive, margin: float) -> tuple[np.ndarray, np.ndarray]:
    center = np.asarray(primitive.center, dtype=np.float64)
    if primitive.primitive_type == "box":
        if primitive.extents is None:
            raise ContractViolation(
                f"invariant violation: box ShapePrimitive requires extents, got None (part={primitive.part!r})"
            )
        half = np.asarray(primitive.extents, dtype=np.float64) / 2.0 + margin
    elif primitive.primitive_type == "cylinder":
        if primitive.radius is None or primitive.height is None:
            raise ContractViolation(
                f"invariant violation: cylinder ShapePrimitive requires radius and height, "
                f"got radius={primitive.radius!r}, height={primitive.height!r} (part={primitive.part!r})"
            )
        radius = float(primitive.radius) + margin
        half_height = float(primitive.height) / 2.0 + margin
        if primitive.axis == "x":
            half = np.asarray([half_height, radius, radius], dtype=np.float64)
        elif primitive.axis == "z":
            half = np.asarray([radius, radius, half_height], dtype=np.float64)
        else:
            half = np.asarray([radius, half_height, radius], dtype=np.float64)
    else:
        raise ValueError(f"Unsupported primitive type '{primitive.primitive_type}'")
    return center - half, center + half


def _iter_candidate_primitives(shape_ir: ShapeIR, margin: float) -> Iterable[tuple[ShapePrimitive, np.ndarray, np.ndarray]]:
    for primitive in shape_ir.primitives:
        bounds_min, bounds_max = _primitive_bounds(primitive, margin)
        yield primitive, bounds_min, bounds_max


def exactify_surface_mesh(mesh: trimesh.Trimesh, shape_ir: ShapeIR, fidelity: FidelityProfile) -> tuple[trimesh.Trimesh, dict[str, float | int]]:
    refined = mesh.copy()
    if len(refined.vertices) == 0 or len(shape_ir.primitives) == 0:
        return refined, {"projection_iterations": 0, "mean_vertex_shift": 0.0, "max_vertex_shift": 0.0}

    snap_radius = max(1.5, float(np.linalg.norm(refined.extents)) * (0.030 if fidelity.tier == "hero" else 0.022))
    blend = 0.78 if fidelity.tier == "hero" else 0.62
    iterations = 2 if fidelity.tier == "hero" else 1
    margin = snap_radius * 0.8

    try:
        trimesh.smoothing.filter_taubin(refined, lamb=0.35, nu=-0.37, iterations=4 if fidelity.tier == "hero" else 2)
    except (ValueError, RuntimeError, AttributeError, IndexError):
        # Taubin smoothing fails on degenerate / non-manifold topology.
        pass

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
    try:
        refined.process(validate=True)
    except (ValueError, RuntimeError, AttributeError, IndexError):
        # trimesh.process(validate=True) can raise on malformed topology;
        # the caller still finalizes with remove/merge/fix_normals below.
        pass
    refined.fix_normals()
    return refined, {
        "projection_iterations": iterations,
        "snap_radius": round(float(snap_radius), 6),
        "mean_vertex_shift": round(float(np.mean(shifts)) if shifts else 0.0, 6),
        "max_vertex_shift": round(float(np.max(shifts)) if shifts else 0.0, 6),
    }
