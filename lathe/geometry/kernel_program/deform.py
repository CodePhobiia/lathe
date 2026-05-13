"""Deform program — twist / taper / bend a source operand.

Per the §5.3 decomposition, this module hosts the ``deform`` family:
``sop.twist``, ``sop.taper``, ``sop.bend``. The executor takes exact
rebuild paths for primitives that admit an analytical deformation
(extruded profiles for twist+taper, cylinders for taper-as-revolve and
bend-as-curved-tube, capsules for sampled taper, spheres for axisymmetric
no-ops), then falls through to a generic per-vertex deformation with
optional subdivision refinement.
"""

from __future__ import annotations

import contextlib
import math
from typing import Any

import numpy as np
import trimesh

from ..kernel import GeometryKernel
from ._capabilities import (
    _kernel_capabilities,
    _require_capabilities,
    _validate_transform_operand,
)
from ._common import (
    _finite_float,
    _non_empty_mesh,
    _operation_id_fragment,
    _record_result_probe,
)
from ._core import (
    KernelOperand,
    KernelProgramResult,
    _exact_rebuild_required_capabilities,
    _required_capability_list,
    deform_operation_count,
)
from ._face_operation import _attach_direct_face_operation_metadata
from ._primitive_metadata import (
    _axis_index,
    _axis_name_from_index,
    _axis_span,
    _capsule_metadata,
    _cylinder_metadata,
    _extruded_profile_metadata,
    _mesh_with_vertices,
    _perpendicular_axis_indices,
    _rotate_profile_polygon_2d,
    _sphere_metadata,
    _validated_deform_axis,
    _validated_origin,
)
from ._records import _operand_operation_records
from ._semantic import (
    _final_semantic_operation_face_id,
    _operation_counts,
    _semantic_operation_records_from_manifest,
)
from ._semantic_handoff import _attach_kernel_program_semantic_handoff
from ._serialize import _dict_metadata, _json_safe

KERNEL_PROGRAM_VERSION = "lathe.geometry.kernel_program_v1"


def _validated_deform_operation(operation: str) -> str:
    """Normalize a deform operation alias to its canonical sop.* form."""
    key = str(operation or "").strip().lower()
    aliases = {
        "twist": "sop.twist",
        "sop.twist": "sop.twist",
        "taper": "sop.taper",
        "sop.taper": "sop.taper",
        "bend": "sop.bend",
        "sop.bend": "sop.bend",
    }
    if key not in aliases:
        raise ValueError("kernel deform operation must be one of: sop.twist, sop.taper, sop.bend")
    return aliases[key]


def _mesh_origin(mesh: trimesh.Trimesh, origin: list[float] | None) -> np.ndarray:
    """Resolve ``origin`` to a 3-vector, defaulting to the mesh's bounding-box center."""
    if origin is not None:
        return np.asarray(origin, dtype=np.float64)
    bounds = np.asarray(mesh.bounds, dtype=np.float64)
    return (bounds[0] + bounds[1]) * 0.5


def _subdivided_deform_mesh(
    mesh: trimesh.Trimesh,
    *,
    axis: str,
    subdivision_levels: int | None,
    segments: int | None,
) -> tuple[trimesh.Trimesh, dict[str, Any]]:
    """Pre-subdivide ``mesh`` to ``segments`` along ``axis`` for smooth deformation."""
    if len(mesh.vertices) == 0 or len(mesh.faces) == 0:
        raise ValueError("kernel deform source produced an empty mesh")
    explicit_levels = subdivision_levels is not None
    if explicit_levels:
        levels = int(subdivision_levels)
        if levels < 0 or levels > 6:
            raise ValueError("kernel deform subdivision_levels must be between 0 and 6")
        target_segments = max(1, 2**levels)
    elif segments is not None:
        target_segments = int(segments)
        if target_segments < 1:
            raise ValueError("kernel deform segments must be >= 1")
        target_segments = min(target_segments, 64)
        levels = max(1, min(6, math.ceil(math.log2(float(target_segments)))))
    else:
        target_segments = 12
        levels = max(1, min(6, math.ceil(math.log2(float(target_segments)))))

    axis_index = _axis_index(axis)
    _, _, span = _axis_span(np.asarray(mesh.vertices, dtype=np.float64), axis_index)
    details: dict[str, Any] = {
        "source_face_count": len(mesh.faces),
        "source_vertex_count": len(mesh.vertices),
        "deform_segments": target_segments,
        "subdivision_request": "levels" if explicit_levels else "segments",
    }
    if levels <= 0 or target_segments <= 1:
        details.update(
            {
                "subdivision_applied": False,
                "subdivision_levels": levels,
                "subdivision_target_segments": target_segments,
                "subdivision_axis_span_cm": span,
            }
        )
        return mesh.copy(), details

    try:
        vertices = np.asarray(mesh.vertices, dtype=np.float64)
        faces = np.asarray(mesh.faces, dtype=np.int64)
        for _ in range(levels):
            vertices, faces = trimesh.remesh.subdivide(vertices, faces)
    except (ValueError, RuntimeError, AttributeError, IndexError, TypeError) as exc:
        raise ValueError(f"kernel deform subdivision failed: {exc}") from exc
    refined = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    refined.metadata.update(dict(mesh.metadata))
    refined.remove_unreferenced_vertices()
    refined.merge_vertices()
    with contextlib.suppress(ValueError, RuntimeError, AttributeError, IndexError, TypeError):
        refined.fix_normals()
    if len(refined.vertices) == 0 or len(refined.faces) == 0:
        raise ValueError("kernel deform subdivision produced an empty mesh")
    details.update(
        {
            "subdivision_applied": True,
            "subdivision_levels": levels,
            "subdivision_target_segments": target_segments,
            "subdivision_axis_span_cm": span,
            "subdivided_face_count": len(refined.faces),
            "subdivided_vertex_count": len(refined.vertices),
        }
    )
    return refined, details


def _exact_extruded_profile_deform_params(
    mesh: trimesh.Trimesh,
    *,
    operation: str,
    axis: str,
    angle_degrees: float | None,
    start_scale: float | None,
    end_scale: float | None,
    origin: list[float] | None,
    segments: int | None,
    subdivision_levels: int | None,
) -> dict[str, Any] | None:
    """Detect an extruded_profile primitive whose deform can be expressed as a rebuild.

    Twist on an untapered profile becomes a twist-extruded profile.
    Taper on an untwisted profile becomes a scaled-extruded profile.
    """
    profile = _extruded_profile_metadata(mesh)
    if profile is None or str(profile["axis"]) != axis:
        return None
    if origin is not None:
        origin_tuple = tuple(float(value) for value in origin)
        center = tuple(float(value) for value in profile["center"])
        if any(abs(origin_tuple[index] - center[index]) > 1e-7 for index in range(3)):
            return None
    if operation not in {"sop.twist", "sop.taper"}:
        return None
    existing_start = float(profile["extrude_start_scale"])
    existing_end = float(profile["extrude_end_scale"])
    existing_twist = float(profile["extrude_twist_degrees"])
    existing_segments = int(profile["extrude_segments"])
    polygon = tuple(profile["profile_polygon"])
    method = ""
    result_start = existing_start
    result_end = existing_end
    result_twist = existing_twist
    result_polygon = polygon
    if operation == "sop.twist":
        angle = _finite_float(angle_degrees, field="angle_degrees")
        if abs(existing_start - existing_end) > 1e-9:
            return None
        result_polygon = _rotate_profile_polygon_2d(polygon, -0.5 * angle)
        result_twist = existing_twist + angle
        method = "exact_extruded_profile_twist_rebuild_v1"
    else:
        start = _finite_float(1.0 if start_scale is None else start_scale, field="start_scale")
        end = _finite_float(end_scale, field="end_scale")
        if start <= 0.0 or end <= 0.0:
            raise ValueError("kernel deform taper scale values must be > 0")
        if abs(existing_twist) > 1e-9 or abs(existing_start - existing_end) > 1e-9:
            return None
        result_start = existing_start * start
        result_end = existing_end * end
        method = "exact_extruded_profile_taper_rebuild_v1"
    requested_segments = segments
    if requested_segments is None and subdivision_levels is not None:
        requested_segments = max(1, 2 ** int(subdivision_levels))
    twist_segments = max(existing_segments, 1)
    if operation == "sop.twist":
        twist_segments = max(twist_segments, math.ceil(abs(result_twist) / 30.0))
    if requested_segments is not None:
        twist_segments = max(twist_segments, int(requested_segments))
    twist_segments = max(1, min(96, twist_segments))
    shape = dict(profile["shape"])
    shape["profile_polygon"] = [tuple(point) for point in result_polygon]
    shape["extrude_start_scale"] = result_start
    shape["extrude_end_scale"] = result_end
    shape["extrude_twist_degrees"] = result_twist if abs(result_twist) > 1e-9 else None
    shape["extrude_segments"] = twist_segments
    shape["semantic_metadata"] = dict(_dict_metadata(shape.get("semantic_metadata")))
    shape["semantic_metadata"]["exact_deform_rebuild"] = {
        "schema": "lathe.geometry.exact_extruded_profile_deform.v1",
        "method": method,
        "operation": operation,
        "source_axis": axis,
        "source_start_scale": existing_start,
        "source_end_scale": existing_end,
        "source_twist_degrees": existing_twist,
        "result_start_scale": result_start,
        "result_end_scale": result_end,
        "result_twist_degrees": result_twist,
        "result_segments": twist_segments,
    }
    return {
        "method": method,
        "primitive_type": "extruded_profile",
        "required_capabilities": ["extruded_profile", "to_trimesh"],
        "build_params": shape,
        "source_profile": profile,
        "result_profile_point_count": len(result_polygon),
        "result_start_scale": result_start,
        "result_end_scale": result_end,
        "result_twist_degrees": result_twist,
        "result_segments": twist_segments,
    }


def _origin_matches_center(
    origin: list[float] | None,
    center: tuple[float, float, float],
    *,
    tolerance: float = 1e-7,
) -> bool:
    """Return True when ``origin`` is None or within ``tolerance`` of ``center``."""
    if origin is None:
        return True
    return all(abs(float(origin[index]) - float(center[index])) <= tolerance for index in range(3))


def _capsule_taper_profile_points(
    *,
    radius: float,
    length: float,
    start_scale: float,
    end_scale: float,
    segments: int,
) -> tuple[tuple[float, float], ...]:
    """Sample a tapered capsule into ``(axial, radial)`` profile points."""
    sample_count = max(16, min(128, int(segments)))
    shaft = max(0.0, float(length) - 2.0 * float(radius))
    half_shaft = shaft * 0.5
    half_length = float(length) * 0.5
    points: list[tuple[float, float]] = []
    for index in range(sample_count + 1):
        axial = -half_length + float(length) * (index / float(sample_count))
        if axial < -half_shaft:
            local = axial + half_shaft
            base_radius = math.sqrt(max(0.0, float(radius) ** 2 - local * local))
        elif axial > half_shaft:
            local = axial - half_shaft
            base_radius = math.sqrt(max(0.0, float(radius) ** 2 - local * local))
        else:
            base_radius = float(radius)
        t = (axial + half_length) / max(float(length), 1e-9)
        scale = start_scale + (end_scale - start_scale) * t
        points.append((float(axial), max(0.0, base_radius * scale)))
    return tuple(points)


def _curved_tube_basis_axes(plane_axis: str) -> tuple[str, str] | None:
    """Return the two perpendicular axis names that span the bend plane."""
    if plane_axis == "x":
        return "y", "z"
    if plane_axis == "y":
        return "x", "z"
    if plane_axis == "z":
        return "x", "y"
    return None


def _remaining_axis(first_axis: str, second_axis: str) -> str | None:
    """Return the third axis name when given two distinct axes; None otherwise."""
    axes = {"x", "y", "z"}
    remaining = axes - {first_axis, second_axis}
    if len(remaining) != 1:
        return None
    return next(iter(remaining))


def _axis_unit_vector(axis: str) -> tuple[float, float, float]:
    """Return the unit vector along ``axis``."""
    vector = [0.0, 0.0, 0.0]
    vector[_axis_index(axis)] = 1.0
    return (float(vector[0]), float(vector[1]), float(vector[2]))


def _round_primitive_deform_params(
    mesh: trimesh.Trimesh,
    *,
    operation: str,
    axis: str,
    angle_degrees: float | None,
    start_scale: float | None,
    end_scale: float | None,
    direction_axis: str | None,
    origin: list[float] | None,
    segments: int | None,
    subdivision_levels: int | None,
) -> dict[str, Any] | None:
    """Detect a round primitive (sphere/cylinder/capsule) whose deform admits a rebuild.

    Sphere twist around its own axis is a no-op rebuild; cylinder/capsule
    twist on-axis is similarly a no-op. Cylinder bend becomes a curved tube.
    Cylinder taper becomes a revolved_profile. Capsule taper is sampled.
    Returns None when no rebuild applies.
    """
    sphere = _sphere_metadata(mesh)
    cylinder = _cylinder_metadata(mesh)
    capsule = _capsule_metadata(mesh)
    source = sphere or cylinder or capsule
    if source is None:
        return None
    center = tuple(float(value) for value in source["center"])
    if not _origin_matches_center(origin, center):
        return None
    requested_segments = segments
    if requested_segments is None and subdivision_levels is not None:
        requested_segments = max(1, 2 ** int(subdivision_levels))
    result_segments = max(1, min(128, int(requested_segments or 24)))

    if operation == "sop.twist":
        _finite_float(angle_degrees, field="angle_degrees")
        if sphere is not None:
            return {
                "method": "exact_axisymmetric_sphere_twist_noop_v1",
                "primitive_type": "sphere",
                "required_capabilities": ["sphere", "to_trimesh"],
                "exact": True,
                "build_params": {
                    "center": center,
                    "radius": float(sphere["radius"]),
                    "part": "deformed_sphere",
                },
                "source_profile": {"center": center, "primitive_type": "sphere"},
                "result_radius": float(sphere["radius"]),
                "result_profile_point_count": 0,
                "result_start_scale": 1.0,
                "result_end_scale": 1.0,
                "result_twist_degrees": float(angle_degrees or 0.0),
                "result_segments": result_segments,
                "result_primitive_type": "sphere",
            }
        round_source = cylinder or capsule
        if round_source is None or str(round_source["axis"]) != axis:
            return None
        primitive_type = "cylinder" if cylinder is not None else "capsule"
        build_params = {
            "center": center,
            "axis": axis,
            "part": f"deformed_{primitive_type}",
        }
        if cylinder is not None:
            build_params.update(
                {
                    "radius": float(cylinder["radius"]),
                    "height": float(cylinder["height"]),
                }
            )
        else:
            build_params.update(
                {
                    "radius": float(capsule["radius"]),
                    "length": float(capsule["length"]),
                }
            )
        return {
            "method": f"exact_axisymmetric_{primitive_type}_twist_noop_v1",
            "primitive_type": primitive_type,
            "required_capabilities": [primitive_type, "to_trimesh"],
            "exact": True,
            "build_params": build_params,
            "source_profile": {"center": center, "primitive_type": primitive_type},
            "result_axis": axis,
            "result_radius": float(round_source["radius"]),
            **(
                {"result_height": float(cylinder["height"])}
                if cylinder is not None
                else {"result_length": float(capsule["length"])}
            ),
            "result_profile_point_count": 0,
            "result_start_scale": 1.0,
            "result_end_scale": 1.0,
            "result_twist_degrees": float(angle_degrees or 0.0),
            "result_segments": result_segments,
            "result_primitive_type": primitive_type,
        }

    if operation == "sop.bend":
        if cylinder is None:
            return None
        if str(cylinder["axis"]) != axis:
            return None
        bend_angle = _finite_float(angle_degrees, field="angle_degrees")
        if abs(bend_angle) <= 1e-9 or abs(bend_angle) > 330.0:
            return None
        bend_axis = direction_axis
        if bend_axis is None:
            first, _ = _perpendicular_axis_indices(axis)
            bend_axis = _axis_name_from_index(first)
        if bend_axis == axis:
            return None
        plane_axis = _remaining_axis(axis, bend_axis)
        if plane_axis is None:
            return None
        basis = _curved_tube_basis_axes(plane_axis)
        if basis is None:
            return None
        radius = float(cylinder["radius"])
        height = float(cylinder["height"])
        bend_radius = height / abs(math.radians(bend_angle))
        if radius >= bend_radius:
            return None
        basis_u, basis_v = basis
        if basis_u == bend_axis and basis_v == axis:
            path_angle = bend_angle
            start_angle = -0.5 * bend_angle
        elif basis_u == axis and basis_v == bend_axis:
            path_angle = -bend_angle
            start_angle = 90.0 + 0.5 * bend_angle
        else:
            return None
        direction_vector = _axis_unit_vector(bend_axis)
        bend_center = tuple(
            center[index] - direction_vector[index] * bend_radius
            for index in range(3)
        )
        path_segments = max(
            8,
            min(
                256,
                int(segments or math.ceil(abs(bend_angle) / 10.0)),
            ),
        )
        cross_section_segments = max(8, min(128, int(segments or 32)))
        return {
            "method": "exact_cylinder_bend_curved_tube_v1",
            "primitive_type": "curved_tube",
            "required_capabilities": ["curved_tube", "to_trimesh"],
            "exact": True,
            "build_params": {
                "center": bend_center,
                "radius": bend_radius,
                "tube_radius": radius,
                "angle_degrees": path_angle,
                "start_angle_degrees": start_angle,
                "plane_axis": plane_axis,
                "path_segments": path_segments,
                "cross_section_segments": cross_section_segments,
                "part": "deformed_cylinder_bend",
            },
            "source_profile": {"center": center, "primitive_type": "cylinder"},
            "result_primitive_type": "curved_tube",
            "result_axis": axis,
            "result_direction_axis": bend_axis,
            "result_plane_axis": plane_axis,
            "result_radius": bend_radius,
            "result_tube_radius": radius,
            "result_height": height,
            "result_angle_degrees": path_angle,
            "result_start_angle_degrees": start_angle,
            "result_profile_point_count": cross_section_segments,
            "result_segments": path_segments,
        }

    if operation != "sop.taper":
        return None
    start = _finite_float(1.0 if start_scale is None else start_scale, field="start_scale")
    end = _finite_float(end_scale, field="end_scale")
    if start <= 0.0 or end <= 0.0:
        raise ValueError("kernel deform taper scale values must be > 0")
    if cylinder is not None:
        if str(cylinder["axis"]) != axis:
            return None
        radius = float(cylinder["radius"])
        height = float(cylinder["height"])
        profile_points = (
            (-height * 0.5, radius * start),
            (height * 0.5, radius * end),
        )
        return {
            "method": "exact_cylinder_taper_revolved_profile_v1",
            "primitive_type": "revolved_profile",
            "required_capabilities": ["revolved_profile", "to_trimesh"],
            "exact": True,
            "build_params": {
                "center": center,
                "axis": axis,
                "profile_points": profile_points,
                "part": "deformed_cylinder_taper",
            },
            "source_profile": {"center": center, "primitive_type": "cylinder"},
            "result_axis": axis,
            "result_radius": max(radius * start, radius * end),
            "result_start_radius": radius * start,
            "result_end_radius": radius * end,
            "result_height": height,
            "result_profile_point_count": len(profile_points),
            "result_start_scale": start,
            "result_end_scale": end,
            "result_twist_degrees": 0.0,
            "result_segments": result_segments,
            "result_primitive_type": "revolved_profile",
        }
    if capsule is not None:
        if str(capsule["axis"]) != axis:
            return None
        profile_points = _capsule_taper_profile_points(
            radius=float(capsule["radius"]),
            length=float(capsule["length"]),
            start_scale=start,
            end_scale=end,
            segments=result_segments,
        )
        return {
            "method": "sampled_capsule_taper_revolved_profile_v1",
            "primitive_type": "revolved_profile",
            "required_capabilities": ["revolved_profile", "to_trimesh"],
            "build_params": {
                "center": center,
                "axis": axis,
                "profile_points": profile_points,
                "part": "deformed_capsule_taper",
            },
            "source_profile": {"center": center, "primitive_type": "capsule"},
            "result_axis": axis,
            "result_radius": max(float(capsule["radius"]) * start, float(capsule["radius"]) * end),
            "result_start_radius": float(capsule["radius"]) * start,
            "result_end_radius": float(capsule["radius"]) * end,
            "result_length": float(capsule["length"]),
            "result_profile_point_count": len(profile_points),
            "result_start_scale": start,
            "result_end_scale": end,
            "result_twist_degrees": 0.0,
            "result_segments": result_segments,
            "result_primitive_type": "revolved_profile",
            "exact": False,
            "approximation": "sampled_capsule_taper_profile",
        }
    return None


def build_deform_program_manifest(
    source: KernelOperand,
    *,
    deform_operation: str,
    axis: str,
    angle_degrees: float | None = None,
    start_scale: float | None = None,
    end_scale: float | None = None,
    direction_axis: str | None = None,
    origin: list[float] | None = None,
    subdivision_levels: int | None = None,
    segments: int | None = None,
    route: str = "deform_program",
    backend: str | None = None,
    operation_limit: int | None = None,
) -> dict[str, Any]:
    """Return a deterministic, handle-free manifest for a mesh deform program."""
    operation_records = _operand_operation_records([source])
    if not any(str(record.get("operation") or "") == deform_operation for record in operation_records):
        operation_records.append(
            {
                "operation_id": f"program:{_operation_id_fragment(route)}:{_operation_id_fragment(deform_operation)}",
                "operation": deform_operation,
                "repair_action": "",
                "operand_id": source.operand_id,
                "operand_index": 0,
                "part": source.part or "",
                "primitive_type": source.primitive_type or "",
                "blend_mode": source.blend_mode,
                "source": "kernel_program.deform",
            }
        )
    diagnostics: list[dict[str, Any]] = []
    if source.handle is None:
        diagnostics.append(
            {
                "code": "missing_kernel_operand_handle",
                "severity": "error",
                "operand_ids": [source.operand_id],
            }
        )
    operation_count = deform_operation_count(source)
    if operation_limit is not None and operation_count > operation_limit:
        diagnostics.append(
            {
                "code": "kernel_program_operation_limit_exceeded",
                "severity": "error",
                "operation_count": operation_count,
                "operation_limit": operation_limit,
            }
        )
    return {
        "schema": "lathe.geometry.kernel_program_manifest.v1",
        "version": KERNEL_PROGRAM_VERSION,
        "program_kind": "deform",
        "route": route,
        "backend": backend,
        "operation_count": operation_count,
        "kernel_call_count": operation_count,
        "operation_limit": operation_limit,
        "required_capabilities": ["from_trimesh", "to_trimesh"],
        "operand_count": 1,
        "operands": [_json_safe(source.trace_record())],
        "semantic_operation_record_count": len(operation_records),
        "semantic_operation_counts": _operation_counts(operation_records),
        "semantic_operation_records": _json_safe(operation_records),
        "deform_operation": deform_operation,
        "axis": axis,
        "angle_degrees": angle_degrees,
        "start_scale": start_scale,
        "end_scale": end_scale,
        "direction_axis": direction_axis,
        "origin_cm": _json_safe(origin),
        "subdivision_levels": subdivision_levels,
        "segments": segments,
        "diagnostics": diagnostics,
    }


def execute_deform_program(
    kernel: GeometryKernel,
    source: KernelOperand,
    *,
    deform_operation: str,
    axis: str = "y",
    angle_degrees: float | None = None,
    start_scale: float | None = None,
    end_scale: float | None = None,
    direction_axis: str | None = None,
    origin: list[float] | tuple[float, float, float] | None = None,
    subdivision_levels: int | None = None,
    segments: int | None = None,
    operation_limit: int | None = None,
    route: str = "deform_program",
    backend: str | None = None,
) -> KernelProgramResult:
    """Execute a vertex deformation through the typed KernelProgram seam."""
    operation = _validated_deform_operation(deform_operation)
    axis_name = _validated_deform_axis(axis)
    direction_name = (
        _validated_deform_axis(direction_axis, field="direction_axis")
        if direction_axis is not None
        else None
    )
    origin_cm = _validated_origin(origin)
    _validate_transform_operand(source)
    operation_count = deform_operation_count(source)
    if operation_limit is not None and operation_count > operation_limit:
        raise ValueError(
            f"kernel deform operation_count={operation_count} exceeds limit={operation_limit}"
        )
    capabilities = _kernel_capabilities(kernel)
    required = {"from_trimesh", "to_trimesh"}
    _require_capabilities(kernel, capabilities, required)
    manifest = build_deform_program_manifest(
        source,
        deform_operation=operation,
        axis=axis_name,
        angle_degrees=angle_degrees,
        start_scale=start_scale,
        end_scale=end_scale,
        direction_axis=direction_name,
        origin=origin_cm,
        subdivision_levels=subdivision_levels,
        segments=segments,
        route=route,
        backend=backend,
        operation_limit=operation_limit,
    )

    source_mesh = _non_empty_mesh(kernel, source.handle)
    exact_deform_params = _exact_extruded_profile_deform_params(
        source_mesh,
        operation=operation,
        axis=axis_name,
        angle_degrees=angle_degrees,
        start_scale=start_scale,
        end_scale=end_scale,
        origin=origin_cm,
        segments=segments,
        subdivision_levels=subdivision_levels,
    )
    if exact_deform_params is None:
        exact_deform_params = _round_primitive_deform_params(
            source_mesh,
            operation=operation,
            axis=axis_name,
            angle_degrees=angle_degrees,
            start_scale=start_scale,
            end_scale=end_scale,
            direction_axis=direction_name,
            origin=origin_cm,
            segments=segments,
            subdivision_levels=subdivision_levels,
    )
    exact_deform_failure = ""
    if exact_deform_params is not None:
        exact_required = _exact_rebuild_required_capabilities(exact_deform_params)
        exact_checked_capabilities = _required_capability_list(
            sorted(required),
            exact_required,
        )
        if exact_required and all(capabilities.get(name) is True for name in exact_required):
            try:
                current = kernel.build_primitive(
                    str(exact_deform_params["primitive_type"]),
                    **dict(exact_deform_params["build_params"]),
                )
                mesh = _non_empty_mesh(kernel, current)
                source_profile = dict(exact_deform_params.get("source_profile") or {})
                source_center = source_profile.get("center") or (0.0, 0.0, 0.0)
                source_primitive_type = str(
                    source_profile.get("primitive_type")
                    or exact_deform_params.get("source_primitive_type")
                    or "unknown"
                )
                result_primitive_type = str(
                    exact_deform_params.get("result_primitive_type")
                    or exact_deform_params["primitive_type"]
                )
                deform_exact = bool(exact_deform_params.get("exact", True))
                deform_approximation = exact_deform_params.get("approximation")
                exact_metadata = {
                    "schema": "lathe.geometry.kernel_deform.v1",
                    "method": str(exact_deform_params["method"]),
                    "operation": operation,
                    "axis": axis_name,
                    "origin_cm": [
                        float(value)
                        for value in (
                            origin_cm
                            if origin_cm is not None
                            else source_center
                        )
                    ],
                    "attempted_backend": f"{kernel.name}.build_primitive",
                    "actual_backend": f"{kernel.name}.build_primitive",
                    "attempted_kernel": kernel.name,
                    "actual_kernel": kernel.name,
                    "actual_operation": operation,
                    "kernel_rebuild_path": True,
                    "exact_kernel_path": deform_exact,
                    "deform_exact": deform_exact,
                    "fallback": False,
                    "passthrough": False,
                    "source_primitive_type": source_primitive_type,
                    "result_primitive_type": result_primitive_type,
                    "source_face_count": len(source_mesh.faces),
                    "source_vertex_count": len(source_mesh.vertices),
                    "result_face_count": len(mesh.faces),
                    "result_vertex_count": len(mesh.vertices),
                    "result_watertight": bool(mesh.is_watertight),
                    "result_body_count": kernel.body_count(current),
                }
                for key in ("result_profile_point_count", "result_segments"):
                    if exact_deform_params.get(key) is not None:
                        exact_metadata[key] = int(exact_deform_params[key])
                for key in (
                    "result_radius",
                    "result_start_radius",
                    "result_end_radius",
                    "result_height",
                    "result_length",
                    "result_tube_radius",
                    "result_angle_degrees",
                    "result_start_angle_degrees",
                    "result_start_scale",
                    "result_end_scale",
                    "result_twist_degrees",
                ):
                    if exact_deform_params.get(key) is not None:
                        exact_metadata[key] = float(exact_deform_params[key])
                for key in ("result_axis", "result_direction_axis", "result_plane_axis"):
                    if exact_deform_params.get(key) is not None:
                        exact_metadata[key] = str(exact_deform_params[key])
                if deform_approximation is not None:
                    exact_metadata["deform_approximation"] = str(deform_approximation)
                if angle_degrees is not None:
                    exact_metadata["angle_degrees"] = float(angle_degrees)
                if start_scale is not None:
                    exact_metadata["start_scale"] = float(start_scale)
                if end_scale is not None:
                    exact_metadata["end_scale"] = float(end_scale)
                mesh.metadata["lathe_kernel_deform"] = dict(exact_metadata)
                operation_records = _semantic_operation_records_from_manifest(manifest)
                operation_record = {
                    "op": "deform",
                    "source": source.operand_id,
                    "attempted_kernel": kernel.name,
                    "actual_kernel": kernel.name,
                    "attempted_backend": f"{kernel.name}.build_primitive",
                    "actual_backend": f"{kernel.name}.build_primitive",
                    "semantic_operation": operation,
                    "deform_operation": operation,
                    "axis": axis_name,
                    "direction_axis": direction_name,
                    "angle_degrees": exact_metadata.get("angle_degrees"),
                    "start_scale": exact_metadata.get("start_scale"),
                    "end_scale": exact_metadata.get("end_scale"),
                    "origin_cm": exact_metadata["origin_cm"],
                    "result_face_count": len(mesh.faces),
                    "result_vertex_count": len(mesh.vertices),
                    "result_watertight": bool(mesh.is_watertight),
                    "result_body_count": kernel.body_count(current),
                    "kernel_rebuild_path": True,
                    "exact_kernel_path": deform_exact,
                    "deform_exact": deform_exact,
                    "kernel_deform": dict(exact_metadata),
                }
                if deform_approximation is not None:
                    operation_record["deform_approximation"] = str(deform_approximation)
                for key in (
                    "result_primitive_type",
                    "result_axis",
                    "result_radius",
                    "result_start_radius",
                    "result_end_radius",
                    "result_height",
                    "result_length",
                    "result_tube_radius",
                    "result_angle_degrees",
                    "result_start_angle_degrees",
                    "result_profile_point_count",
                    "result_segments",
                    "result_direction_axis",
                    "result_plane_axis",
                ):
                    if key in exact_metadata:
                        operation_record[key] = exact_metadata[key]
                face_operation_id, final_operation_record = _final_semantic_operation_face_id(
                    operation_records,
                    operation,
                    fallback=f"{source.operand_id}.{_operation_id_fragment(operation)}",
                )
                if final_operation_record:
                    operation_record["semantic_operation_record"] = dict(final_operation_record)
                _record_result_probe(operation_record, kernel=kernel, result_handle=current)
                (
                    face_operation_ids,
                    face_operation_summary,
                    face_operation_attribution,
                ) = _attach_direct_face_operation_metadata(
                    mesh,
                    face_operation_id,
                    source=f"kernel_program.deform.{result_primitive_type}_rebuild",
                    method=f"{exact_deform_params['method']}_face_ranges",
                )
                semantic_handoff = _attach_kernel_program_semantic_handoff(
                    mesh,
                    [source],
                    [operation_record],
                )
                deform_detail_payload: dict[str, Any] = {
                    "deform_exact": deform_exact,
                    "deform_exact_method": str(exact_deform_params["method"]),
                    "deform_result_primitive_type": result_primitive_type,
                }
                if deform_approximation is not None:
                    deform_detail_payload["deform_approximation"] = str(deform_approximation)
                for metadata_key, detail_key in (
                    ("result_axis", "deform_result_axis"),
                    ("result_radius", "deform_result_radius"),
                    ("result_start_radius", "deform_result_start_radius"),
                    ("result_end_radius", "deform_result_end_radius"),
                    ("result_height", "deform_result_height"),
                    ("result_length", "deform_result_length"),
                    ("result_tube_radius", "deform_result_tube_radius"),
                    ("result_angle_degrees", "deform_result_angle_degrees"),
                    ("result_start_angle_degrees", "deform_result_start_angle_degrees"),
                    ("result_direction_axis", "deform_result_direction_axis"),
                    ("result_plane_axis", "deform_result_plane_axis"),
                    ("result_profile_point_count", "deform_result_profile_point_count"),
                    ("result_segments", "deform_result_segments"),
                ):
                    if metadata_key in exact_metadata:
                        deform_detail_payload[detail_key] = exact_metadata[metadata_key]
                return KernelProgramResult(
                    mesh=mesh,
                    handle=current,
                    operation_count=operation_count,
                    details={
                        "kernel_program_version": KERNEL_PROGRAM_VERSION,
                        "kernel_program_route": route,
                        "kernel_program_operation_count": operation_count,
                        "kernel_program_operand_count": 1,
                        "kernel_program_semantic_operation_record_count": len(operation_records),
                        "kernel_program_semantic_operation_counts": _operation_counts(operation_records),
                        "kernel_program_semantic_operation_records": operation_records,
                        "kernel_program_kernel": kernel.name,
                        "kernel_program_backend": backend,
                        "kernel_program_manifest": {
                            **manifest,
                            "required_capabilities": exact_checked_capabilities,
                            "kernel_rebuild_path": True,
                            "exact_kernel_path": deform_exact,
                            "exact_deform_method": str(exact_deform_params["method"]),
                            **(
                                {"deform_approximation": str(deform_approximation)}
                                if deform_approximation is not None
                                else {}
                            ),
                        },
                        "kernel_program_capabilities_checked": exact_checked_capabilities,
                        "kernel_program_watertight": bool(mesh.is_watertight),
                        "kernel_program_body_count": kernel.body_count(current),
                        "kernel_program_operands": [source.trace_record()],
                        "kernel_program_operations": [operation_record],
                        "kernel_program_face_operation_attribution": face_operation_attribution,
                        "face_operation_ids": face_operation_ids,
                        "face_operation_summary": face_operation_summary,
                        "kernel_program_deform_source_operand_id": source.operand_id,
                        "deform_operation": operation,
                        "deform_axis": axis_name,
                        "deform_direction_axis": direction_name,
                        "deform_angle_degrees": exact_metadata.get("angle_degrees"),
                        "deform_start_scale": exact_metadata.get("start_scale"),
                        "deform_end_scale": exact_metadata.get("end_scale"),
                        "deform_origin_cm": exact_metadata["origin_cm"],
                        "deform_source_face_count": len(source_mesh.faces),
                        "deform_source_vertex_count": len(source_mesh.vertices),
                        "deform_result_face_count": len(mesh.faces),
                        "deform_result_vertex_count": len(mesh.vertices),
                        "deform_result_watertight": bool(mesh.is_watertight),
                        **deform_detail_payload,
                        "kernel_deform": exact_metadata,
                        "kernel_program_deform": exact_metadata,
                        "kernel_program_semantic_handoff": semantic_handoff,
                    },
                )
            except (AttributeError, TypeError, ValueError, RuntimeError, OSError) as exc:
                exact_deform_failure = f"{type(exc).__name__}: {exc}"

    working_mesh, subdivision_details = _subdivided_deform_mesh(
        source_mesh,
        axis=axis_name,
        subdivision_levels=subdivision_levels,
        segments=segments,
    )
    origin_vector = _mesh_origin(working_mesh, origin_cm)
    vertices = np.asarray(working_mesh.vertices, dtype=np.float64).copy()
    axis_index = _axis_index(axis_name)
    axis_min, _, span = _axis_span(vertices, axis_index)
    first, second = _perpendicular_axis_indices(axis_name)
    relative = vertices - origin_vector

    operation_payload: dict[str, Any] = {
        "schema": "lathe.geometry.kernel_deform.v1",
        "method": "kernel_program_mesh_deform_v1",
        "operation": operation,
        "axis": axis_name,
        "origin_cm": [float(value) for value in origin_vector.tolist()],
        "span_cm": float(span),
        "attempted_backend": kernel.name,
        "actual_backend": kernel.name,
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "actual_operation": operation,
        "fallback": False,
        "passthrough": False,
        **subdivision_details,
    }
    if exact_deform_params is not None:
        operation_payload["exact_deform_path_available"] = True
        operation_payload["exact_deform_path_method"] = str(exact_deform_params["method"])
        operation_payload["exact_deform_required_capabilities"] = list(exact_required)
        if exact_deform_failure:
            operation_payload["exact_deform_path_failed"] = exact_deform_failure
            operation_payload["exact_kernel_path_fallback"] = True
        elif not all(capabilities.get(str(name)) is True for name in exact_required):
            operation_payload["exact_deform_path_skipped"] = (
                "kernel_did_not_advertise_required_capability"
            )
    if operation == "sop.twist":
        angle = _finite_float(angle_degrees, field="angle_degrees")
        angles = math.radians(angle) * (relative[:, axis_index] / span)
        cos_values = np.cos(angles)
        sin_values = np.sin(angles)
        first_values = relative[:, first].copy()
        second_values = relative[:, second].copy()
        vertices[:, first] = origin_vector[first] + first_values * cos_values - second_values * sin_values
        vertices[:, second] = origin_vector[second] + first_values * sin_values + second_values * cos_values
        operation_payload["angle_degrees"] = float(angle)
    elif operation == "sop.taper":
        start = _finite_float(1.0 if start_scale is None else start_scale, field="start_scale")
        end = _finite_float(end_scale, field="end_scale")
        if start <= 0.0 or end <= 0.0:
            raise ValueError("kernel deform taper scale values must be > 0")
        t = (vertices[:, axis_index] - axis_min) / span
        scale = start + (end - start) * t
        vertices[:, first] = origin_vector[first] + (vertices[:, first] - origin_vector[first]) * scale
        vertices[:, second] = origin_vector[second] + (vertices[:, second] - origin_vector[second]) * scale
        operation_payload["start_scale"] = float(start)
        operation_payload["end_scale"] = float(end)
    elif operation == "sop.bend":
        angle = _finite_float(angle_degrees, field="angle_degrees")
        if direction_name is None:
            direction_name = _axis_name_from_index(first)
        if direction_name == axis_name:
            raise ValueError("kernel deform bend direction_axis must differ from axis")
        direction_index = _axis_index(direction_name)
        angle_radians = math.radians(angle)
        if abs(angle_radians) > 1e-9:
            radius = span / abs(angle_radians)
            relative_axis = vertices[:, axis_index] - origin_vector[axis_index]
            relative_direction = vertices[:, direction_index] - origin_vector[direction_index]
            theta = (relative_axis / span) * angle_radians
            vertices[:, axis_index] = origin_vector[axis_index] + np.sin(theta) * radius
            vertices[:, direction_index] = (
                origin_vector[direction_index]
                + (np.cos(theta) - 1.0) * radius
                + relative_direction * np.cos(theta)
            )
        operation_payload["angle_degrees"] = float(angle)
        operation_payload["direction_axis"] = direction_name

    deformed = _mesh_with_vertices(working_mesh, vertices)
    operation_payload.update(
        {
            "source_face_count": len(source_mesh.faces),
            "source_vertex_count": len(source_mesh.vertices),
            "deform_input_face_count": len(working_mesh.faces),
            "deform_input_vertex_count": len(working_mesh.vertices),
            "result_face_count": len(deformed.faces),
            "result_vertex_count": len(deformed.vertices),
            "result_watertight": bool(deformed.is_watertight),
            "result_body_count": len(deformed.split(only_watertight=False)),
        }
    )
    deformed.metadata["lathe_kernel_deform"] = dict(operation_payload)
    current = kernel.from_trimesh(deformed)
    mesh = _non_empty_mesh(kernel, current)
    mesh.metadata["lathe_kernel_deform"] = dict(operation_payload)
    operation_records = _semantic_operation_records_from_manifest(manifest)
    operation_record = {
        "op": "deform",
        "source": source.operand_id,
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "semantic_operation": operation,
        "deform_operation": operation,
        "axis": axis_name,
        "direction_axis": direction_name,
        "angle_degrees": operation_payload.get("angle_degrees"),
        "start_scale": operation_payload.get("start_scale"),
        "end_scale": operation_payload.get("end_scale"),
        "origin_cm": operation_payload["origin_cm"],
        "span_cm": operation_payload["span_cm"],
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_watertight": bool(mesh.is_watertight),
        "result_body_count": kernel.body_count(current),
        "kernel_deform": dict(operation_payload),
    }
    face_operation_id, final_operation_record = _final_semantic_operation_face_id(
        operation_records,
        operation,
        fallback=f"{source.operand_id}.{_operation_id_fragment(operation)}",
    )
    if final_operation_record:
        operation_record["semantic_operation_record"] = dict(final_operation_record)
    _record_result_probe(operation_record, kernel=kernel, result_handle=current)
    (
        face_operation_ids,
        face_operation_summary,
        face_operation_attribution,
    ) = _attach_direct_face_operation_metadata(
        mesh,
        face_operation_id,
        source="kernel_program.deform.source_operand",
        method="deformed_source_face_ranges",
    )
    semantic_handoff = _attach_kernel_program_semantic_handoff(
        mesh,
        [source],
        [operation_record],
    )
    details = {
        "kernel_program_version": KERNEL_PROGRAM_VERSION,
        "kernel_program_route": route,
        "kernel_program_operation_count": operation_count,
        "kernel_program_operand_count": 1,
        "kernel_program_semantic_operation_record_count": len(operation_records),
        "kernel_program_semantic_operation_counts": _operation_counts(operation_records),
        "kernel_program_semantic_operation_records": operation_records,
        "kernel_program_kernel": kernel.name,
        "kernel_program_backend": backend,
        "kernel_program_manifest": manifest,
        "kernel_program_capabilities_checked": sorted(required),
        "kernel_program_watertight": kernel.is_watertight(current),
        "kernel_program_body_count": kernel.body_count(current),
        "kernel_program_operands": [source.trace_record()],
        "kernel_program_operations": [operation_record],
        "kernel_program_face_operation_attribution": face_operation_attribution,
        "face_operation_ids": face_operation_ids,
        "face_operation_summary": face_operation_summary,
        "kernel_program_deform_source_operand_id": source.operand_id,
        "deform_operation": operation,
        "deform_axis": axis_name,
        "deform_direction_axis": direction_name,
        "deform_angle_degrees": operation_payload.get("angle_degrees"),
        "deform_start_scale": operation_payload.get("start_scale"),
        "deform_end_scale": operation_payload.get("end_scale"),
        "deform_origin_cm": operation_payload["origin_cm"],
        "deform_span_cm": operation_payload["span_cm"],
        "deform_source_face_count": len(source_mesh.faces),
        "deform_source_vertex_count": len(source_mesh.vertices),
        "deform_input_face_count": len(working_mesh.faces),
        "deform_input_vertex_count": len(working_mesh.vertices),
        "deform_result_face_count": len(mesh.faces),
        "deform_result_vertex_count": len(mesh.vertices),
        "deform_result_watertight": bool(mesh.is_watertight),
        "kernel_deform": operation_payload,
        "kernel_program_deform": operation_payload,
        **subdivision_details,
        "kernel_program_semantic_handoff": semantic_handoff,
    }
    return KernelProgramResult(
        mesh=mesh,
        handle=current,
        operation_count=operation_count,
        details=details,
    )


__all__ = [
    "build_deform_program_manifest",
    "execute_deform_program",
]
