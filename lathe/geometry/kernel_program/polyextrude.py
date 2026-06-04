"""Polyextrude program — extrude a source operand along an axis by a signed distance.

Per the §5.3 decomposition, this module hosts the ``polyextrude``
family: ``sop.polyextrude``, a single-source op that extends the
``cap`` end of a mesh along ``axis`` by ``distance_cm``. The executor
takes exact-primitive rebuild paths for box/cylinder/extruded_profile
sources when the kernel supports them, then falls through to a
generic axis-planar-cap extension on trimesh.

Fallback chain (axis_planar_cap → measured_bounds_cap_hull →
axis_interval_scale) records its method, source/result extents, and
the reason its predecessor degraded so the trace surfaces an honest
attempted-vs-actual story.
"""

from __future__ import annotations

import contextlib
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
    polyextrude_operation_count,
)
from ._face_operation import _attach_direct_face_operation_metadata
from ._feature_detail import _kernel_feature_detail_metadata
from ._primitive_metadata import (
    _axis_aligned_box_metadata,
    _axis_extruded_center_and_span,
    _axis_index,
    _axis_span,
    _cylinder_metadata,
    _extruded_profile_metadata,
    _mesh_with_vertices,
    _positive_triplet,
    _validated_deform_axis,
)
from ._records import _operand_operation_records
from ._semantic import (
    _final_semantic_operation_record,
    _operation_counts,
    _semantic_operation_records_from_manifest,
)
from ._semantic_handoff import _attach_kernel_program_semantic_handoff
from ._serialize import _json_safe

KERNEL_PROGRAM_VERSION = "lathe.geometry.kernel_program_v1"


def _exact_primitive_polyextrude_params(
    mesh: trimesh.Trimesh,
    *,
    axis: str,
    distance_cm: float,
) -> dict[str, Any] | None:
    """Detect a known primitive (box/cylinder/extruded_profile) for the exact-polyextrude path.

    Returns rebuild parameters when the source mesh is recognized as a
    primitive whose extrusion can be expressed as a larger instance of
    the same primitive. Twisted or scale-tapered extruded profiles
    cannot be polyextruded exactly and return None.
    """
    distance = float(distance_cm)
    if abs(distance) <= 1e-9:
        return None
    box = _axis_aligned_box_metadata(mesh)
    if box is not None:
        axis_index = _axis_index(axis)
        bounds_min = list(float(value) for value in box["bounds_min"])
        bounds_max = list(float(value) for value in box["bounds_max"])
        source_min = float(bounds_min[axis_index])
        source_max = float(bounds_max[axis_index])
        if distance >= 0.0:
            bounds_max[axis_index] += distance
        else:
            bounds_min[axis_index] += distance
        extents = tuple(bounds_max[index] - bounds_min[index] for index in range(3))
        if not _positive_triplet(extents):
            return None
        center = tuple((bounds_min[index] + bounds_max[index]) * 0.5 for index in range(3))
        return {
            "method": "exact_box_axis_polyextrude_v1",
            "primitive_type": "box",
            "required_capabilities": ["box", "to_trimesh"],
            "build_params": {
                "center": center,
                "extents": extents,
                "part": "polyextruded_box",
            },
            "source_primitive_type": "box",
            "result_primitive_type": "box",
            "result_axis": axis,
            "result_extents": extents,
            "source_min_cm": source_min,
            "source_max_cm": source_max,
            "source_extent_cm": source_max - source_min,
            "result_min_cm": float(bounds_min[axis_index]),
            "result_max_cm": float(bounds_max[axis_index]),
            "result_extent_cm": float(extents[axis_index]),
            "side": "max" if distance >= 0.0 else "min",
        }

    cylinder = _cylinder_metadata(mesh)
    if cylinder is not None and str(cylinder["axis"]) == axis:
        center, result_height, source_min, source_max, result_min = _axis_extruded_center_and_span(
            tuple(float(value) for value in cylinder["center"]),
            axis=axis,
            span=float(cylinder["height"]),
            distance=distance,
        )
        return {
            "method": "exact_cylinder_axis_polyextrude_v1",
            "primitive_type": "cylinder",
            "required_capabilities": ["cylinder", "to_trimesh"],
            "build_params": {
                "center": center,
                "axis": axis,
                "radius": float(cylinder["radius"]),
                "height": result_height,
                "part": "polyextruded_cylinder",
            },
            "source_primitive_type": "cylinder",
            "result_primitive_type": "cylinder",
            "result_axis": axis,
            "result_radius": float(cylinder["radius"]),
            "result_height": result_height,
            "source_min_cm": source_min,
            "source_max_cm": source_max,
            "source_extent_cm": float(cylinder["height"]),
            "result_min_cm": result_min,
            "result_max_cm": result_min + result_height,
            "result_extent_cm": result_height,
            "side": "max" if distance >= 0.0 else "min",
        }

    profile = _extruded_profile_metadata(mesh)
    if profile is not None and str(profile["axis"]) == axis:
        if (
            abs(float(profile["extrude_twist_degrees"])) > 1e-9
            or abs(float(profile["extrude_start_scale"]) - float(profile["extrude_end_scale"])) > 1e-9
        ):
            return None
        source_height = float(profile["extrude_height"])
        center, result_height, source_min, source_max, result_min = _axis_extruded_center_and_span(
            tuple(float(value) for value in profile["center"]),
            axis=axis,
            span=source_height,
            distance=distance,
        )
        shape = dict(profile["shape"])
        shape["center"] = center
        shape["axis"] = axis
        shape["extrude_height"] = result_height
        shape["part"] = "polyextruded_extruded_profile"
        return {
            "method": "exact_extruded_profile_axis_polyextrude_v1",
            "primitive_type": "extruded_profile",
            "required_capabilities": ["extruded_profile", "to_trimesh"],
            "build_params": shape,
            "source_primitive_type": "extruded_profile",
            "result_primitive_type": "extruded_profile",
            "result_axis": axis,
            "result_height": result_height,
            "result_profile_point_count": len(profile["profile_polygon"]),
            "result_start_scale": float(profile["extrude_start_scale"]),
            "result_end_scale": float(profile["extrude_end_scale"]),
            "source_min_cm": source_min,
            "source_max_cm": source_max,
            "source_extent_cm": source_height,
            "result_min_cm": result_min,
            "result_max_cm": result_min + result_height,
            "result_extent_cm": result_height,
            "side": "max" if distance >= 0.0 else "min",
        }
    return None


def _polyextruded_axis_mesh(
    mesh: trimesh.Trimesh,
    *,
    axis: str,
    distance_cm: float,
) -> tuple[trimesh.Trimesh, dict[str, Any]]:
    """Extend ``mesh`` along ``axis`` by ``distance_cm``.

    Tries three paths in order:
      1. ``axis_planar_cap_polyextrude_v1`` — extends the planar cap
         faces on the extrude side, preserving topology elsewhere.
      2. ``measured_bounds_cap_hull_polyextrude_v1`` — convex hull of
         source + bounding-box cap points; safer but loses topology.
      3. ``axis_interval_scale_polyextrude_v1`` — vertex-level
         interval-scale fallback; always returns geometry.

    The returned dict records which method succeeded plus
    ``fallback_chain`` and ``fallback_reason`` for the trace.
    """
    axis_index = _axis_index(axis)
    distance = float(distance_cm)
    source_vertices = np.asarray(mesh.vertices, dtype=np.float64)
    source_min, source_max, source_extent = _axis_span(source_vertices, axis_index)
    if abs(distance) <= 1e-9:
        candidate = mesh.copy()
        candidate.metadata.update(dict(mesh.metadata))
        return candidate, {
            "method": "identity_noop_v1",
            "fallback": False,
            "fallback_from": "",
            "fallback_reason": "",
            "axis": axis,
            "distance_cm": 0.0,
            "source_min_cm": source_min,
            "source_max_cm": source_max,
            "source_extent_cm": source_extent,
            "result_extent_cm": source_extent,
        }

    sign = 1.0 if distance >= 0.0 else -1.0
    depth = abs(distance)
    cap_coord = source_max if sign > 0.0 else source_min
    exact_failure: str | None = None
    exact_mesh = None
    exact_details: dict[str, Any] = {}
    try:
        faces = np.asarray(mesh.faces, dtype=np.int64)
        diagonal = float(np.linalg.norm(np.asarray(mesh.bounds[1]) - np.asarray(mesh.bounds[0])))
        tolerance = max(1e-6, diagonal * 1e-7)
        cap_vertex_mask = np.abs(source_vertices[:, axis_index] - cap_coord) <= tolerance
        cap_face_mask = np.asarray(
            [bool(np.all(cap_vertex_mask[face])) for face in faces],
            dtype=bool,
        )
        cap_face_indices = np.nonzero(cap_face_mask)[0]
        if len(cap_face_indices) == 0:
            exact_failure = "no_planar_cap_faces_on_extrude_side"
        else:
            cap_faces = faces[cap_face_indices]
            cap_vertices = sorted({int(index) for face in cap_faces for index in face})
            if len(cap_vertices) < 3:
                exact_failure = "planar_cap_has_too_few_vertices"
            else:
                edge_counts: dict[tuple[int, int], int] = {}
                for face in cap_faces:
                    for offset in range(3):
                        edge = tuple(sorted((int(face[offset]), int(face[(offset + 1) % 3]))))
                        edge_counts[edge] = edge_counts.get(edge, 0) + 1
                boundary_edges = [edge for edge, count in edge_counts.items() if count == 1]
                if not boundary_edges:
                    exact_failure = "planar_cap_boundary_loop_missing"
                else:
                    translation = np.zeros(3, dtype=np.float64)
                    translation[axis_index] = sign * depth
                    new_vertices = source_vertices.tolist()
                    duplicate_index: dict[int, int] = {}
                    for old_index in cap_vertices:
                        duplicate_index[old_index] = len(new_vertices)
                        new_vertices.append((source_vertices[old_index] + translation).tolist())

                    new_faces: list[list[int]] = [
                        [int(value) for value in face]
                        for face in faces[~cap_face_mask].tolist()
                    ]
                    for face in cap_faces.tolist():
                        new_faces.append([duplicate_index[int(value)] for value in face])
                    for left, right in boundary_edges:
                        left_new = duplicate_index[int(left)]
                        right_new = duplicate_index[int(right)]
                        new_faces.append([int(left), int(right), right_new])
                        new_faces.append([int(left), right_new, left_new])

                    candidate = trimesh.Trimesh(
                        vertices=np.asarray(new_vertices, dtype=np.float64),
                        faces=np.asarray(new_faces, dtype=np.int64),
                        process=False,
                    )
                    candidate.metadata.update(dict(mesh.metadata))
                    candidate.remove_unreferenced_vertices()
                    with contextlib.suppress(AttributeError, TypeError, ValueError, RuntimeError):
                        candidate.fix_normals()
                    if len(candidate.faces) == 0:
                        exact_failure = "planar_cap_extend_result_empty"
                    elif not bool(candidate.is_watertight):
                        exact_failure = "planar_cap_extend_result_not_watertight"
                    else:
                        exact_mesh = candidate
                        exact_details = {
                            "cap_coordinate_cm": cap_coord,
                            "cap_face_count": len(cap_face_indices),
                            "cap_vertex_count": len(cap_vertices),
                            "cap_boundary_edge_count": len(boundary_edges),
                        }
    except (
        AttributeError,
        IndexError,
        TypeError,
        ValueError,
        RuntimeError,
    ) as exc:
        exact_failure = f"{type(exc).__name__}: {exc}"

    if exact_mesh is not None:
        _, result_max, result_extent = _axis_span(np.asarray(exact_mesh.vertices), axis_index)
        result_min = float(np.asarray(exact_mesh.vertices)[:, axis_index].min())
        return exact_mesh, {
            "method": "axis_planar_cap_polyextrude_v1",
            "fallback": False,
            "fallback_from": "",
            "fallback_reason": "",
            "axis": axis,
            "distance_cm": distance,
            "side": "positive" if sign > 0.0 else "negative",
            "source_min_cm": source_min,
            "source_max_cm": source_max,
            "source_extent_cm": source_extent,
            "result_min_cm": result_min,
            "result_max_cm": result_max,
            "result_extent_cm": result_extent,
            **exact_details,
        }

    measured_mesh: trimesh.Trimesh | None = None
    measured_failure: str | None = None
    measured_details: dict[str, Any] = {}
    try:
        bounds = np.asarray(mesh.bounds, dtype=np.float64)
        source_min_vector = bounds[0].astype(np.float64)
        source_max_vector = bounds[1].astype(np.float64)
        source_span_vector = np.maximum(source_max_vector - source_min_vector, 1e-6)
        tangent_axes = [index for index in range(3) if index != axis_index]
        if any(float(source_span_vector[index]) <= 1e-6 for index in tangent_axes):
            measured_failure = "source_tangent_bounds_collapsed"
        else:
            out_coord = cap_coord + sign * depth
            cap_points: list[list[float]] = []
            for first, second in ((0, 0), (1, 0), (1, 1), (0, 1)):
                point = source_min_vector.copy()
                point[axis_index] = out_coord
                point[tangent_axes[0]] = (
                    source_max_vector[tangent_axes[0]]
                    if first
                    else source_min_vector[tangent_axes[0]]
                )
                point[tangent_axes[1]] = (
                    source_max_vector[tangent_axes[1]]
                    if second
                    else source_min_vector[tangent_axes[1]]
                )
                cap_points.append([float(value) for value in point.tolist()])
            cloud = trimesh.Trimesh(
                vertices=np.vstack([source_vertices, np.asarray(cap_points, dtype=np.float64)]),
                faces=None,
                process=False,
            )
            candidate = cloud.convex_hull
            if not isinstance(candidate, trimesh.Trimesh) or len(candidate.faces) == 0:
                measured_failure = "measured_bounds_cap_hull_result_empty"
            elif not bool(candidate.is_watertight):
                measured_failure = "measured_bounds_cap_hull_result_not_watertight"
            else:
                candidate.metadata.update(dict(mesh.metadata))
                candidate.remove_unreferenced_vertices()
                with contextlib.suppress(AttributeError, TypeError, ValueError, RuntimeError):
                    candidate.fix_normals()
                measured_mesh = candidate
                measured_details = {
                    "cap_coordinate_cm": cap_coord,
                    "result_cap_coordinate_cm": out_coord,
                    "measured_cap_vertex_count": len(cap_points),
                }
    except (
        AttributeError,
        IndexError,
        TypeError,
        ValueError,
        RuntimeError,
    ) as exc:
        measured_failure = f"{type(exc).__name__}: {exc}"

    if measured_mesh is not None:
        result_min, result_max, result_extent = _axis_span(np.asarray(measured_mesh.vertices), axis_index)
        return measured_mesh, {
            "method": "measured_bounds_cap_hull_polyextrude_v1",
            "fallback": True,
            "fallback_from": "axis_planar_cap_polyextrude_v1",
            "fallback_reason": exact_failure or "planar_cap_extend_unavailable",
            "axis": axis,
            "distance_cm": distance,
            "side": "positive" if sign > 0.0 else "negative",
            "source_min_cm": source_min,
            "source_max_cm": source_max,
            "source_extent_cm": source_extent,
            "result_min_cm": result_min,
            "result_max_cm": result_max,
            "result_extent_cm": result_extent,
            "source_vertex_count": len(source_vertices),
            "source_face_count": len(mesh.faces),
            "result_face_count": len(measured_mesh.faces),
            "result_vertex_count": len(measured_mesh.vertices),
            "result_watertight": bool(measured_mesh.is_watertight),
            **measured_details,
        }

    anchor = source_min if sign > 0.0 else source_max
    scale = (source_extent + depth) / source_extent
    transformed = source_vertices.copy()
    transformed[:, axis_index] = anchor + (transformed[:, axis_index] - anchor) * scale
    fallback = _mesh_with_vertices(mesh, transformed)
    result_min, result_max, result_extent = _axis_span(np.asarray(fallback.vertices), axis_index)
    return fallback, {
        "method": "axis_interval_scale_polyextrude_v1",
        "fallback": True,
        "fallback_from": "measured_bounds_cap_hull_polyextrude_v1",
        "fallback_chain": [
            "axis_planar_cap_polyextrude_v1",
            "measured_bounds_cap_hull_polyextrude_v1",
        ],
        "fallback_reason": measured_failure or exact_failure or "measured_bounds_cap_hull_unavailable",
        "exact_polyextrude_failure": exact_failure or "",
        "measured_polyextrude_failure": measured_failure or "",
        "axis": axis,
        "distance_cm": distance,
        "side": "positive" if sign > 0.0 else "negative",
        "source_min_cm": source_min,
        "source_max_cm": source_max,
        "source_extent_cm": source_extent,
        "result_min_cm": result_min,
        "result_max_cm": result_max,
        "result_extent_cm": result_extent,
    }


def build_polyextrude_program_manifest(
    source: KernelOperand,
    *,
    axis: str,
    distance_cm: float,
    semantic_operation: str = "sop.polyextrude",
    route: str = "polyextrude_program",
    backend: str | None = None,
    operation_limit: int | None = None,
) -> dict[str, Any]:
    """Return a deterministic, handle-free manifest for source polyextrusion."""
    operation_records = _operand_operation_records([source])
    if not any(str(record.get("operation") or "") == semantic_operation for record in operation_records):
        operation_records.append(
            {
                "operation_id": f"program:{_operation_id_fragment(route)}:{_operation_id_fragment(semantic_operation)}",
                "operation": semantic_operation,
                "repair_action": "",
                "operand_id": source.operand_id,
                "operand_index": 0,
                "part": source.part or "",
                "primitive_type": source.primitive_type or "",
                "blend_mode": source.blend_mode,
                "source": "kernel_program.polyextrude",
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
    operation_count = polyextrude_operation_count(source)
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
        "program_kind": "polyextrude",
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
        "semantic_operation": semantic_operation,
        "axis": axis,
        "distance_cm": distance_cm,
        "diagnostics": diagnostics,
    }


def execute_polyextrude_program(
    kernel: GeometryKernel,
    source: KernelOperand,
    *,
    axis: str,
    distance_cm: float,
    semantic_operation: str = "sop.polyextrude",
    operation_limit: int | None = None,
    route: str = "polyextrude_program",
    backend: str | None = None,
) -> KernelProgramResult:
    """Execute source polyextrusion through the typed KernelProgram seam."""
    axis_name = _validated_deform_axis(axis)
    distance = _finite_float(distance_cm, field="distance_cm")
    _validate_transform_operand(source)
    operation_count = polyextrude_operation_count(source)
    if operation_limit is not None and operation_count > operation_limit:
        raise ValueError(
            f"kernel polyextrude operation_count={operation_count} exceeds limit={operation_limit}"
        )
    capabilities = _kernel_capabilities(kernel)
    required = {"from_trimesh", "to_trimesh"}
    _require_capabilities(kernel, capabilities, required)
    manifest = build_polyextrude_program_manifest(
        source,
        axis=axis_name,
        distance_cm=distance,
        semantic_operation=semantic_operation,
        route=route,
        backend=backend,
        operation_limit=operation_limit,
    )
    source_mesh = _non_empty_mesh(kernel, source.handle)
    exact_polyextrude_params = _exact_primitive_polyextrude_params(
        source_mesh,
        axis=axis_name,
        distance_cm=distance,
    )
    exact_polyextrude_failure = ""
    if exact_polyextrude_params is not None:
        exact_required = _exact_rebuild_required_capabilities(exact_polyextrude_params)
        exact_checked_capabilities = _required_capability_list(
            sorted(required),
            exact_required,
        )
        if exact_required and all(capabilities.get(name) is True for name in exact_required):
            try:
                current = kernel.build_primitive(
                    str(exact_polyextrude_params["primitive_type"]),
                    **dict(exact_polyextrude_params["build_params"]),
                )
                mesh = _non_empty_mesh(kernel, current)
                polyextrude_metadata = {
                    "schema": "lathe.geometry.kernel_polyextrude.v1",
                    "operation": semantic_operation,
                    "method": str(exact_polyextrude_params["method"]),
                    "axis": axis_name,
                    "distance_cm": distance,
                    "attempted_backend": f"{kernel.name}.build_primitive",
                    "actual_backend": f"{kernel.name}.build_primitive",
                    "attempted_kernel": kernel.name,
                    "actual_kernel": kernel.name,
                    "actual_operation": semantic_operation,
                    "exact_kernel_path": True,
                    "fallback": False,
                    "passthrough": False,
                    "source_primitive_type": str(exact_polyextrude_params["source_primitive_type"]),
                    "result_primitive_type": str(exact_polyextrude_params["result_primitive_type"]),
                    "source_face_count": len(source_mesh.faces),
                    "source_vertex_count": len(source_mesh.vertices),
                    "result_face_count": len(mesh.faces),
                    "result_vertex_count": len(mesh.vertices),
                    "result_watertight": bool(mesh.is_watertight),
                    "result_body_count": kernel.body_count(current),
                }
                for key in (
                    "source_min_cm",
                    "source_max_cm",
                    "source_extent_cm",
                    "result_min_cm",
                    "result_max_cm",
                    "result_extent_cm",
                    "result_radius",
                    "result_height",
                    "result_start_scale",
                    "result_end_scale",
                ):
                    if exact_polyextrude_params.get(key) is not None:
                        polyextrude_metadata[key] = float(exact_polyextrude_params[key])
                if exact_polyextrude_params.get("result_profile_point_count") is not None:
                    polyextrude_metadata["result_profile_point_count"] = int(
                        exact_polyextrude_params["result_profile_point_count"]
                    )
                if exact_polyextrude_params.get("result_axis") is not None:
                    polyextrude_metadata["result_axis"] = str(exact_polyextrude_params["result_axis"])
                if exact_polyextrude_params.get("result_extents") is not None:
                    polyextrude_metadata["result_extents"] = [
                        float(value) for value in exact_polyextrude_params["result_extents"]
                    ]
                if exact_polyextrude_params.get("side") is not None:
                    polyextrude_metadata["side"] = str(exact_polyextrude_params["side"])
                mesh.metadata["lathe_kernel_polyextrude"] = dict(polyextrude_metadata)
                operation_records = _semantic_operation_records_from_manifest(manifest)
                operation_record = {
                    "op": "polyextrude",
                    "source": source.operand_id,
                    "attempted_kernel": kernel.name,
                    "actual_kernel": kernel.name,
                    "attempted_backend": f"{kernel.name}.build_primitive",
                    "actual_backend": f"{kernel.name}.build_primitive",
                    "semantic_operation": semantic_operation,
                    "axis": axis_name,
                    "distance_cm": distance,
                    "result_face_count": len(mesh.faces),
                    "result_vertex_count": len(mesh.vertices),
                    "result_watertight": bool(mesh.is_watertight),
                    "result_body_count": kernel.body_count(current),
                    "exact_kernel_path": True,
                    "kernel_polyextrude": dict(polyextrude_metadata),
                }
                for key in (
                    "result_primitive_type",
                    "result_axis",
                    "result_extents",
                    "result_radius",
                    "result_height",
                    "result_profile_point_count",
                    "result_start_scale",
                    "result_end_scale",
                ):
                    if key in polyextrude_metadata:
                        operation_record[key] = polyextrude_metadata[key]
                _record_result_probe(operation_record, kernel=kernel, result_handle=current)
                final_operation_record = _final_semantic_operation_record(
                    operation_records,
                    semantic_operation,
                )
                face_operation_id = str(
                    final_operation_record.get("operation_id")
                    or f"{source.operand_id}.{_operation_id_fragment(semantic_operation)}"
                )
                (
                    face_operation_ids,
                    face_operation_summary,
                    face_operation_attribution,
                ) = _attach_direct_face_operation_metadata(
                    mesh,
                    face_operation_id,
                    source=f"kernel_program.polyextrude.{polyextrude_metadata['result_primitive_type']}_rebuild",
                    method=f"{exact_polyextrude_params['method']}_face_ranges",
                )
                kernel_feature_detail = _kernel_feature_detail_metadata(
                    kernel,
                    mesh,
                    current,
                    [source],
                    semantic_operation=semantic_operation,
                    method_suffix="polyextrude_kernel_program_v1",
                    fallback=False,
                    face_operation_attributed=bool(face_operation_ids),
                    extra={
                        "exact_kernel_path": True,
                        "polyextrude_axis": axis_name,
                        "polyextrude_distance_cm": distance,
                    },
                )
                if kernel_feature_detail:
                    mesh.metadata["lathe_kernel_feature_detail"] = dict(kernel_feature_detail)
                semantic_handoff = _attach_kernel_program_semantic_handoff(
                    mesh,
                    [source],
                    [operation_record],
                )
                polyextrude_detail_payload: dict[str, Any] = {
                    "polyextrude_exact": True,
                    "polyextrude_exact_method": str(exact_polyextrude_params["method"]),
                    "polyextrude_result_primitive_type": str(polyextrude_metadata["result_primitive_type"]),
                }
                for metadata_key, detail_key in (
                    ("result_axis", "polyextrude_result_axis"),
                    ("result_extents", "polyextrude_result_extents"),
                    ("result_radius", "polyextrude_result_radius"),
                    ("result_height", "polyextrude_result_height"),
                    ("result_profile_point_count", "polyextrude_result_profile_point_count"),
                    ("result_start_scale", "polyextrude_result_start_scale"),
                    ("result_end_scale", "polyextrude_result_end_scale"),
                    ("side", "polyextrude_side"),
                ):
                    if metadata_key in polyextrude_metadata:
                        polyextrude_detail_payload[detail_key] = polyextrude_metadata[metadata_key]
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
                            "exact_kernel_path": True,
                            "exact_polyextrude_method": str(exact_polyextrude_params["method"]),
                        },
                        "kernel_program_capabilities_checked": exact_checked_capabilities,
                        "kernel_program_watertight": bool(mesh.is_watertight),
                        "kernel_program_body_count": kernel.body_count(current),
                        "kernel_program_operands": [source.trace_record()],
                        "kernel_program_operations": [operation_record],
                        "kernel_program_face_operation_attribution": face_operation_attribution,
                        "face_operation_ids": face_operation_ids,
                        "face_operation_summary": face_operation_summary,
                        "kernel_feature_detail": kernel_feature_detail,
                        "kernel_program_feature_detail": kernel_feature_detail,
                        "kernel_program_polyextrude_source_operand_id": source.operand_id,
                        "polyextrude_axis": axis_name,
                        "polyextrude_distance_cm": distance,
                        "polyextrude_source_face_count": len(source_mesh.faces),
                        "polyextrude_source_vertex_count": len(source_mesh.vertices),
                        "polyextrude_result_face_count": len(mesh.faces),
                        "polyextrude_result_vertex_count": len(mesh.vertices),
                        "polyextrude_result_watertight": bool(mesh.is_watertight),
                        "kernel_polyextrude": polyextrude_metadata,
                        **{
                            key: polyextrude_metadata[key]
                            for key in (
                                "source_min_cm",
                                "source_max_cm",
                                "source_extent_cm",
                                "result_min_cm",
                                "result_max_cm",
                                "result_extent_cm",
                            )
                            if key in polyextrude_metadata
                        },
                        **polyextrude_detail_payload,
                        "kernel_program_semantic_handoff": semantic_handoff,
                    },
                )
            except (AttributeError, TypeError, ValueError, RuntimeError, OSError) as exc:
                exact_polyextrude_failure = f"{type(exc).__name__}: {exc}"
    result_mesh, polyextrude_details = _polyextruded_axis_mesh(
        source_mesh,
        axis=axis_name,
        distance_cm=distance,
    )
    if exact_polyextrude_params is not None:
        polyextrude_details["exact_polyextrude_path_available"] = True
        polyextrude_details["exact_polyextrude_path_method"] = str(exact_polyextrude_params["method"])
        polyextrude_details["exact_polyextrude_required_capabilities"] = list(exact_required)
        if exact_polyextrude_failure:
            polyextrude_details["exact_polyextrude_path_failed"] = exact_polyextrude_failure
            polyextrude_details["exact_kernel_path_fallback"] = True
        elif not all(capabilities.get(str(name)) is True for name in exact_required):
            polyextrude_details["exact_polyextrude_path_skipped"] = (
                "kernel_did_not_advertise_required_capability"
            )
    polyextrude_metadata = {
        "schema": "lathe.geometry.kernel_polyextrude.v1",
        "operation": semantic_operation,
        "axis": axis_name,
        "distance_cm": distance,
        "attempted_backend": kernel.name,
        "actual_backend": kernel.name,
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "actual_operation": semantic_operation,
        "passthrough": abs(distance) <= 1e-9,
        "source_face_count": len(source_mesh.faces),
        "source_vertex_count": len(source_mesh.vertices),
        "result_face_count": len(result_mesh.faces),
        "result_vertex_count": len(result_mesh.vertices),
        "result_watertight": bool(result_mesh.is_watertight),
        "result_body_count": len(result_mesh.split(only_watertight=False)),
        **polyextrude_details,
    }
    result_mesh.metadata["lathe_kernel_polyextrude"] = dict(polyextrude_metadata)
    current = source.handle if abs(distance) <= 1e-9 else kernel.from_trimesh(result_mesh)
    mesh = result_mesh if abs(distance) <= 1e-9 else _non_empty_mesh(kernel, current)
    mesh.metadata["lathe_kernel_polyextrude"] = dict(polyextrude_metadata)
    operation_records = _semantic_operation_records_from_manifest(manifest)
    operation_record = {
        "op": "polyextrude",
        "source": source.operand_id,
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "semantic_operation": semantic_operation,
        "axis": axis_name,
        "distance_cm": distance,
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_watertight": bool(mesh.is_watertight),
        "result_body_count": kernel.body_count(current),
        "kernel_polyextrude": dict(polyextrude_metadata),
    }
    _record_result_probe(operation_record, kernel=kernel, result_handle=current)
    final_operation_record = _final_semantic_operation_record(
        operation_records,
        semantic_operation,
    )
    face_operation_id = str(
        final_operation_record.get("operation_id")
        or f"{source.operand_id}.{_operation_id_fragment(semantic_operation)}"
    )
    (
        face_operation_ids,
        face_operation_summary,
        face_operation_attribution,
    ) = _attach_direct_face_operation_metadata(
        mesh,
        face_operation_id,
        source="kernel_program.polyextrude.source_operand",
        method="polyextruded_source_face_ranges",
    )
    kernel_feature_detail = _kernel_feature_detail_metadata(
        kernel,
        mesh,
        current,
        [source],
        semantic_operation=semantic_operation,
        method_suffix="polyextrude_kernel_program_v1",
        fallback=bool(polyextrude_details.get("fallback"))
        or bool(polyextrude_details.get("exact_kernel_path_fallback")),
        face_operation_attributed=bool(face_operation_ids),
        extra={
            "exact_kernel_path": bool(polyextrude_details.get("exact_kernel_path", False)),
            "polyextrude_axis": axis_name,
            "polyextrude_distance_cm": distance,
        },
    )
    if kernel_feature_detail:
        mesh.metadata["lathe_kernel_feature_detail"] = dict(kernel_feature_detail)
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
        "kernel_feature_detail": kernel_feature_detail,
        "kernel_program_feature_detail": kernel_feature_detail,
        "kernel_program_polyextrude_source_operand_id": source.operand_id,
        "polyextrude_axis": axis_name,
        "polyextrude_distance_cm": distance,
        "polyextrude_source_face_count": len(source_mesh.faces),
        "polyextrude_source_vertex_count": len(source_mesh.vertices),
        "polyextrude_result_face_count": len(mesh.faces),
        "polyextrude_result_vertex_count": len(mesh.vertices),
        "polyextrude_result_watertight": bool(mesh.is_watertight),
        **polyextrude_details,
        "kernel_program_semantic_handoff": semantic_handoff,
    }
    return KernelProgramResult(
        mesh=mesh,
        handle=current,
        operation_count=operation_count,
        details=details,
    )


__all__ = [
    "build_polyextrude_program_manifest",
    "execute_polyextrude_program",
]
