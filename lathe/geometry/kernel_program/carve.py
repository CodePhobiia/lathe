"""Carve program — axis-bounded interval refinement of a single operand.

Per the §5.3 decomposition, this module hosts the ``carve`` family:
``sop.carve``, a single-source op that trims a mesh down to the
``[u_start, u_end]`` interval along an axis. The executor takes
exact-primitive rebuild paths for box/cylinder/extruded_profile
sources when the kernel advertises the required capabilities, then
falls through to a generic axis-slab slice/cap path on trimesh.

The fallback chain (axis_slab_slice_cap → measured_bounds_axis_slab →
axis_interval_scale) is preserved: each path records its method and
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
    carve_operation_count,
)
from ._face_operation import _attach_direct_face_operation_metadata
from ._primitive_metadata import (
    _axis_aligned_box_metadata,
    _axis_index,
    _axis_interval_center_and_span,
    _axis_span,
    _cylinder_metadata,
    _extruded_profile_metadata,
    _mesh_with_vertices,
    _validated_deform_axis,
)
from ._records import _operand_operation_records
from ._semantic import (
    _final_semantic_operation_face_id,
    _operation_counts,
    _semantic_operation_records_from_manifest,
)
from ._semantic_handoff import _attach_kernel_program_semantic_handoff
from ._serialize import _json_safe

KERNEL_PROGRAM_VERSION = "lathe.geometry.kernel_program_v1"


def _carved_axis_interval_mesh(
    mesh: trimesh.Trimesh,
    *,
    axis: str,
    u_start: float,
    u_end: float,
) -> tuple[trimesh.Trimesh, dict[str, Any]]:
    """Trim ``mesh`` to the ``[u_start, u_end]`` interval along ``axis``.

    Tries three paths in order:
      1. ``axis_slab_slice_cap_v1`` — exact slice via trimesh.intersections.
      2. ``measured_bounds_axis_slab_carve_v1`` — measured bounds → box.
      3. ``axis_interval_scale_v1`` — vertex-level fallback that scales
         the axis interval; lossy but always returns geometry.

    The returned dict records which method succeeded plus
    ``fallback_chain`` and ``fallback_reason`` for the trace.
    """
    axis_index = _axis_index(axis)
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    source_min, source_max, source_span = _axis_span(vertices, axis_index)
    carved_min = source_min + source_span * u_start
    carved_max = source_min + source_span * u_end
    carved_span = max(carved_max - carved_min, 1e-6)
    exact_slice_failure: str | None = None
    exact_slice_mesh = None
    try:
        from trimesh.intersections import slice_mesh_plane

        plane_normal = np.zeros(3, dtype=np.float64)
        plane_normal[axis_index] = 1.0
        lower_origin = np.zeros(3, dtype=np.float64)
        lower_origin[axis_index] = carved_min
        upper_origin = np.zeros(3, dtype=np.float64)
        upper_origin[axis_index] = carved_max
        lower_clipped = slice_mesh_plane(
            mesh,
            plane_normal,
            lower_origin,
            cap=True,
        )
        upper_clipped = slice_mesh_plane(
            lower_clipped,
            -plane_normal,
            upper_origin,
            cap=True,
        )
        if isinstance(upper_clipped, trimesh.Trimesh) and len(upper_clipped.faces) > 0:
            upper_clipped.metadata.update(dict(mesh.metadata))
            upper_clipped.remove_unreferenced_vertices()
            with contextlib.suppress(AttributeError, TypeError, ValueError, RuntimeError):
                upper_clipped.fix_normals()
            exact_slice_mesh = upper_clipped
        else:
            exact_slice_failure = "empty_or_non_mesh_slice_result"
    except (
        AttributeError,
        ImportError,
        IndexError,
        ModuleNotFoundError,
        NotImplementedError,
        TypeError,
        ValueError,
        RuntimeError,
    ) as exc:
        exact_slice_failure = f"{type(exc).__name__}: {exc}"
    if exact_slice_mesh is not None:
        return exact_slice_mesh, {
            "method": "axis_slab_slice_cap_v1",
            "fallback": False,
            "fallback_from": "",
            "fallback_reason": "",
            "source_min_cm": source_min,
            "source_max_cm": source_max,
            "source_span_cm": source_span,
            "carved_min_cm": carved_min,
            "carved_max_cm": carved_max,
            "carved_span_cm": carved_span,
        }

    measured_mesh: trimesh.Trimesh | None = None
    measured_failure: str | None = None
    try:
        bounds = np.asarray(mesh.bounds, dtype=np.float64)
        bounds_min = bounds[0].astype(np.float64)
        bounds_max = bounds[1].astype(np.float64)
        bounds_min[axis_index] = carved_min
        bounds_max[axis_index] = carved_max
        extents = bounds_max - bounds_min
        if np.any(extents <= 1e-6):
            measured_failure = "measured_bounds_axis_slab_collapsed"
        else:
            center = (bounds_min + bounds_max) * 0.5
            candidate = trimesh.creation.box(extents=extents)
            candidate.apply_translation(center)
            candidate.metadata.update(dict(mesh.metadata))
            candidate.remove_unreferenced_vertices()
            with contextlib.suppress(AttributeError, TypeError, ValueError, RuntimeError):
                candidate.fix_normals()
            if len(candidate.faces) == 0:
                measured_failure = "measured_bounds_axis_slab_result_empty"
            elif not bool(candidate.is_watertight):
                measured_failure = "measured_bounds_axis_slab_result_not_watertight"
            else:
                measured_mesh = candidate
    except (
        AttributeError,
        IndexError,
        TypeError,
        ValueError,
        RuntimeError,
    ) as exc:
        measured_failure = f"{type(exc).__name__}: {exc}"

    if measured_mesh is not None:
        return measured_mesh, {
            "method": "measured_bounds_axis_slab_carve_v1",
            "fallback": True,
            "fallback_from": "axis_slab_slice_cap_v1",
            "fallback_reason": exact_slice_failure or "slice_backend_unavailable",
            "source_min_cm": source_min,
            "source_max_cm": source_max,
            "source_span_cm": source_span,
            "carved_min_cm": carved_min,
            "carved_max_cm": carved_max,
            "carved_span_cm": carved_span,
            "source_face_count": len(mesh.faces),
            "source_vertex_count": len(mesh.vertices),
            "result_face_count": len(measured_mesh.faces),
            "result_vertex_count": len(measured_mesh.vertices),
            "result_watertight": bool(measured_mesh.is_watertight),
        }

    transformed = vertices.copy()
    transformed[:, axis_index] = carved_min + (
        (transformed[:, axis_index] - source_min) / source_span
    ) * carved_span
    fallback = _mesh_with_vertices(mesh, transformed)
    return fallback, {
        "method": "axis_interval_scale_v1",
        "fallback": True,
        "fallback_from": "measured_bounds_axis_slab_carve_v1",
        "fallback_chain": [
            "axis_slab_slice_cap_v1",
            "measured_bounds_axis_slab_carve_v1",
        ],
        "fallback_reason": measured_failure or exact_slice_failure or "measured_bounds_axis_slab_unavailable",
        "exact_carve_failure": exact_slice_failure or "",
        "measured_carve_failure": measured_failure or "",
        "source_min_cm": source_min,
        "source_max_cm": source_max,
        "source_span_cm": source_span,
        "carved_min_cm": carved_min,
        "carved_max_cm": carved_max,
        "carved_span_cm": carved_span,
    }


def _exact_primitive_carve_params(
    mesh: trimesh.Trimesh,
    *,
    axis: str,
    u_start: float,
    u_end: float,
) -> dict[str, Any] | None:
    """Detect a known primitive (box/cylinder/extruded_profile) for the exact-carve path.

    When ``mesh`` is recognized as a primitive whose carve can be
    expressed as a smaller instance of the same primitive (a box
    becomes a smaller box, a cylinder becomes a shorter cylinder, an
    extruded_profile becomes a shorter extruded_profile with adjusted
    scale taper), return the kernel build_primitive kwargs and
    audit metadata. Twist-extruded profiles cannot be carved exactly
    and return None.
    """
    box = _axis_aligned_box_metadata(mesh)
    if box is not None:
        axis_index = _axis_index(axis)
        bounds_min = list(float(value) for value in box["bounds_min"])
        bounds_max = list(float(value) for value in box["bounds_max"])
        source_span = float(bounds_max[axis_index] - bounds_min[axis_index])
        if source_span <= 1e-9:
            return None
        carved_min = bounds_min[axis_index] + source_span * float(u_start)
        carved_max = bounds_min[axis_index] + source_span * float(u_end)
        bounds_min[axis_index] = carved_min
        bounds_max[axis_index] = carved_max
        extents = tuple(bounds_max[index] - bounds_min[index] for index in range(3))
        center = tuple((bounds_min[index] + bounds_max[index]) * 0.5 for index in range(3))
        return {
            "method": "exact_box_axis_interval_carve_v1",
            "primitive_type": "box",
            "required_capabilities": ["box", "to_trimesh"],
            "build_params": {
                "center": center,
                "extents": extents,
                "part": "carved_box",
            },
            "source_primitive_type": "box",
            "result_primitive_type": "box",
            "result_axis": axis,
            "result_extents": extents,
            "source_min_cm": float(box["bounds_min"][axis_index]),
            "source_max_cm": float(box["bounds_max"][axis_index]),
            "source_span_cm": source_span,
            "carved_min_cm": carved_min,
            "carved_max_cm": carved_max,
            "carved_span_cm": carved_max - carved_min,
        }

    cylinder = _cylinder_metadata(mesh)
    if cylinder is not None and str(cylinder["axis"]) == axis:
        center, carved_height, carved_min, carved_max = _axis_interval_center_and_span(
            tuple(float(value) for value in cylinder["center"]),
            axis=axis,
            span=float(cylinder["height"]),
            u_start=u_start,
            u_end=u_end,
        )
        return {
            "method": "exact_cylinder_axis_interval_carve_v1",
            "primitive_type": "cylinder",
            "required_capabilities": ["cylinder", "to_trimesh"],
            "build_params": {
                "center": center,
                "axis": axis,
                "radius": float(cylinder["radius"]),
                "height": carved_height,
                "part": "carved_cylinder",
            },
            "source_primitive_type": "cylinder",
            "result_primitive_type": "cylinder",
            "result_axis": axis,
            "result_radius": float(cylinder["radius"]),
            "result_height": carved_height,
            "source_min_cm": float(cylinder["center"][_axis_index(axis)]) - float(cylinder["height"]) * 0.5,
            "source_max_cm": float(cylinder["center"][_axis_index(axis)]) + float(cylinder["height"]) * 0.5,
            "source_span_cm": float(cylinder["height"]),
            "carved_min_cm": carved_min,
            "carved_max_cm": carved_max,
            "carved_span_cm": carved_height,
        }

    profile = _extruded_profile_metadata(mesh)
    if profile is not None and str(profile["axis"]) == axis:
        if abs(float(profile["extrude_twist_degrees"])) > 1e-9:
            return None
        source_height = float(profile["extrude_height"])
        center, carved_height, carved_min, carved_max = _axis_interval_center_and_span(
            tuple(float(value) for value in profile["center"]),
            axis=axis,
            span=source_height,
            u_start=u_start,
            u_end=u_end,
        )
        source_start_scale = float(profile["extrude_start_scale"])
        source_end_scale = float(profile["extrude_end_scale"])
        result_start_scale = source_start_scale + (source_end_scale - source_start_scale) * float(u_start)
        result_end_scale = source_start_scale + (source_end_scale - source_start_scale) * float(u_end)
        shape = dict(profile["shape"])
        shape["center"] = center
        shape["axis"] = axis
        shape["extrude_height"] = carved_height
        shape["extrude_start_scale"] = result_start_scale
        shape["extrude_end_scale"] = result_end_scale
        shape["extrude_twist_degrees"] = None
        shape["part"] = "carved_extruded_profile"
        return {
            "method": "exact_extruded_profile_axis_interval_carve_v1",
            "primitive_type": "extruded_profile",
            "required_capabilities": ["extruded_profile", "to_trimesh"],
            "build_params": shape,
            "source_primitive_type": "extruded_profile",
            "result_primitive_type": "extruded_profile",
            "result_axis": axis,
            "result_height": carved_height,
            "result_profile_point_count": len(profile["profile_polygon"]),
            "result_start_scale": result_start_scale,
            "result_end_scale": result_end_scale,
            "source_min_cm": float(profile["center"][_axis_index(axis)]) - source_height * 0.5,
            "source_max_cm": float(profile["center"][_axis_index(axis)]) + source_height * 0.5,
            "source_span_cm": source_height,
            "carved_min_cm": carved_min,
            "carved_max_cm": carved_max,
            "carved_span_cm": carved_height,
        }
    return None


def build_carve_program_manifest(
    source: KernelOperand,
    *,
    u_start: float,
    u_end: float,
    axis: str,
    route: str = "carve_program",
    backend: str | None = None,
    operation_limit: int | None = None,
) -> dict[str, Any]:
    """Return a deterministic, handle-free manifest for axis carve refinement."""
    operation_records = _operand_operation_records([source])
    if not any(str(record.get("operation") or "") == "sop.carve" for record in operation_records):
        operation_records.append(
            {
                "operation_id": f"program:{_operation_id_fragment(route)}:sop_carve",
                "operation": "sop.carve",
                "repair_action": "",
                "operand_id": source.operand_id,
                "operand_index": 0,
                "part": source.part or "",
                "primitive_type": source.primitive_type or "",
                "blend_mode": source.blend_mode,
                "source": "kernel_program.carve",
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
    operation_count = carve_operation_count(source)
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
        "program_kind": "carve",
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
        "u_start": u_start,
        "u_end": u_end,
        "axis": axis,
        "diagnostics": diagnostics,
    }


def execute_carve_program(
    kernel: GeometryKernel,
    source: KernelOperand,
    *,
    u_start: float,
    u_end: float,
    axis: str = "z",
    operation_limit: int | None = None,
    route: str = "carve_program",
    backend: str | None = None,
) -> KernelProgramResult:
    """Execute an axis-bounded carve through the typed KernelProgram seam."""
    start = _finite_float(u_start, field="u_start")
    end = _finite_float(u_end, field="u_end")
    if not 0.0 <= start < end <= 1.0:
        raise ValueError("kernel carve u_start/u_end must satisfy 0 <= start < end <= 1")
    axis_name = _validated_deform_axis(axis)
    _validate_transform_operand(source)
    operation_count = carve_operation_count(source)
    if operation_limit is not None and operation_count > operation_limit:
        raise ValueError(
            f"kernel carve operation_count={operation_count} exceeds limit={operation_limit}"
        )
    capabilities = _kernel_capabilities(kernel)
    required = {"from_trimesh", "to_trimesh"}
    _require_capabilities(kernel, capabilities, required)
    manifest = build_carve_program_manifest(
        source,
        u_start=start,
        u_end=end,
        axis=axis_name,
        route=route,
        backend=backend,
        operation_limit=operation_limit,
    )
    source_mesh = _non_empty_mesh(kernel, source.handle)
    exact_carve_params = _exact_primitive_carve_params(
        source_mesh,
        axis=axis_name,
        u_start=start,
        u_end=end,
    )
    exact_carve_failure = ""
    if exact_carve_params is not None:
        exact_required = _exact_rebuild_required_capabilities(exact_carve_params)
        exact_checked_capabilities = _required_capability_list(
            sorted(required),
            exact_required,
        )
        if exact_required and all(capabilities.get(name) is True for name in exact_required):
            try:
                current = kernel.build_primitive(
                    str(exact_carve_params["primitive_type"]),
                    **dict(exact_carve_params["build_params"]),
                )
                mesh = _non_empty_mesh(kernel, current)
                carve_metadata = {
                    "schema": "lathe.geometry.kernel_carve.v1",
                    "operation": "sop.carve",
                    "method": str(exact_carve_params["method"]),
                    "axis": axis_name,
                    "u_start": start,
                    "u_end": end,
                    "attempted_backend": f"{kernel.name}.build_primitive",
                    "actual_backend": f"{kernel.name}.build_primitive",
                    "attempted_kernel": kernel.name,
                    "actual_kernel": kernel.name,
                    "actual_operation": "sop.carve",
                    "exact_kernel_path": True,
                    "fallback": False,
                    "passthrough": False,
                    "source_primitive_type": str(exact_carve_params["source_primitive_type"]),
                    "result_primitive_type": str(exact_carve_params["result_primitive_type"]),
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
                    "source_span_cm",
                    "carved_min_cm",
                    "carved_max_cm",
                    "carved_span_cm",
                    "result_radius",
                    "result_height",
                    "result_start_scale",
                    "result_end_scale",
                ):
                    if exact_carve_params.get(key) is not None:
                        carve_metadata[key] = float(exact_carve_params[key])
                if exact_carve_params.get("result_profile_point_count") is not None:
                    carve_metadata["result_profile_point_count"] = int(
                        exact_carve_params["result_profile_point_count"]
                    )
                if exact_carve_params.get("result_axis") is not None:
                    carve_metadata["result_axis"] = str(exact_carve_params["result_axis"])
                if exact_carve_params.get("result_extents") is not None:
                    carve_metadata["result_extents"] = [
                        float(value) for value in exact_carve_params["result_extents"]
                    ]
                mesh.metadata["lathe_kernel_carve"] = dict(carve_metadata)
                operation_records = _semantic_operation_records_from_manifest(manifest)
                operation_record = {
                    "op": "carve",
                    "source": source.operand_id,
                    "attempted_kernel": kernel.name,
                    "actual_kernel": kernel.name,
                    "attempted_backend": f"{kernel.name}.build_primitive",
                    "actual_backend": f"{kernel.name}.build_primitive",
                    "semantic_operation": "sop.carve",
                    "axis": axis_name,
                    "u_start": start,
                    "u_end": end,
                    "result_face_count": len(mesh.faces),
                    "result_vertex_count": len(mesh.vertices),
                    "result_watertight": bool(mesh.is_watertight),
                    "result_body_count": kernel.body_count(current),
                    "exact_kernel_path": True,
                    "kernel_carve": dict(carve_metadata),
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
                    if key in carve_metadata:
                        operation_record[key] = carve_metadata[key]
                face_operation_id, final_operation_record = _final_semantic_operation_face_id(
                    operation_records,
                    "sop.carve",
                    fallback=f"{source.operand_id}.sop_carve",
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
                    source=f"kernel_program.carve.{carve_metadata['result_primitive_type']}_rebuild",
                    method=f"{exact_carve_params['method']}_face_ranges",
                )
                semantic_handoff = _attach_kernel_program_semantic_handoff(
                    mesh,
                    [source],
                    [operation_record],
                )
                carve_detail_payload: dict[str, Any] = {
                    "carve_exact": True,
                    "carve_exact_method": str(exact_carve_params["method"]),
                    "carve_result_primitive_type": str(carve_metadata["result_primitive_type"]),
                }
                for metadata_key, detail_key in (
                    ("result_axis", "carve_result_axis"),
                    ("result_extents", "carve_result_extents"),
                    ("result_radius", "carve_result_radius"),
                    ("result_height", "carve_result_height"),
                    ("result_profile_point_count", "carve_result_profile_point_count"),
                    ("result_start_scale", "carve_result_start_scale"),
                    ("result_end_scale", "carve_result_end_scale"),
                ):
                    if metadata_key in carve_metadata:
                        carve_detail_payload[detail_key] = carve_metadata[metadata_key]
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
                            "exact_carve_method": str(exact_carve_params["method"]),
                        },
                        "kernel_program_capabilities_checked": exact_checked_capabilities,
                        "kernel_program_watertight": bool(mesh.is_watertight),
                        "kernel_program_body_count": kernel.body_count(current),
                        "kernel_program_operands": [source.trace_record()],
                        "kernel_program_operations": [operation_record],
                        "kernel_program_face_operation_attribution": face_operation_attribution,
                        "face_operation_ids": face_operation_ids,
                        "face_operation_summary": face_operation_summary,
                        "kernel_program_carve_source_operand_id": source.operand_id,
                        "carve_axis": axis_name,
                        "carve_u_start": start,
                        "carve_u_end": end,
                        "carve_source_face_count": len(source_mesh.faces),
                        "carve_source_vertex_count": len(source_mesh.vertices),
                        "carve_result_face_count": len(mesh.faces),
                        "carve_result_vertex_count": len(mesh.vertices),
                        "carve_result_watertight": bool(mesh.is_watertight),
                        "kernel_carve": carve_metadata,
                        "kernel_program_carve": carve_metadata,
                        **{
                            key: carve_metadata[key]
                            for key in (
                                "source_min_cm",
                                "source_max_cm",
                                "source_span_cm",
                                "carved_min_cm",
                                "carved_max_cm",
                                "carved_span_cm",
                            )
                            if key in carve_metadata
                        },
                        **carve_detail_payload,
                        "kernel_program_semantic_handoff": semantic_handoff,
                    },
                )
            except (AttributeError, TypeError, ValueError, RuntimeError, OSError) as exc:
                exact_carve_failure = f"{type(exc).__name__}: {exc}"
    result_mesh, carve_details = _carved_axis_interval_mesh(
        source_mesh,
        axis=axis_name,
        u_start=start,
        u_end=end,
    )
    if exact_carve_params is not None:
        carve_details["exact_carve_path_available"] = True
        carve_details["exact_carve_path_method"] = str(exact_carve_params["method"])
        carve_details["exact_carve_required_capabilities"] = list(exact_required)
        if exact_carve_failure:
            carve_details["exact_carve_path_failed"] = exact_carve_failure
            carve_details["exact_kernel_path_fallback"] = True
        elif not all(capabilities.get(str(name)) is True for name in exact_required):
            carve_details["exact_carve_path_skipped"] = (
                "kernel_did_not_advertise_required_capability"
            )
    carve_metadata = {
        "schema": "lathe.geometry.kernel_carve.v1",
        "operation": "sop.carve",
        "axis": axis_name,
        "u_start": start,
        "u_end": end,
        "attempted_backend": kernel.name,
        "actual_backend": kernel.name,
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "actual_operation": "sop.carve",
        "passthrough": False,
        "source_face_count": len(source_mesh.faces),
        "source_vertex_count": len(source_mesh.vertices),
        "result_face_count": len(result_mesh.faces),
        "result_vertex_count": len(result_mesh.vertices),
        "result_watertight": bool(result_mesh.is_watertight),
        "result_body_count": len(result_mesh.split(only_watertight=False)),
        **carve_details,
    }
    result_mesh.metadata["lathe_kernel_carve"] = dict(carve_metadata)
    current = kernel.from_trimesh(result_mesh)
    mesh = _non_empty_mesh(kernel, current)
    mesh.metadata["lathe_kernel_carve"] = dict(carve_metadata)
    operation_records = _semantic_operation_records_from_manifest(manifest)
    operation_record = {
        "op": "carve",
        "source": source.operand_id,
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "semantic_operation": "sop.carve",
        "axis": axis_name,
        "u_start": start,
        "u_end": end,
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_watertight": bool(mesh.is_watertight),
        "result_body_count": kernel.body_count(current),
        "kernel_carve": dict(carve_metadata),
    }
    face_operation_id, final_operation_record = _final_semantic_operation_face_id(
        operation_records,
        "sop.carve",
        fallback=f"{source.operand_id}.sop_carve",
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
        source="kernel_program.carve.source_operand",
        method="carved_source_face_ranges",
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
        "kernel_program_carve_source_operand_id": source.operand_id,
        "carve_axis": axis_name,
        "carve_u_start": start,
        "carve_u_end": end,
        "carve_source_face_count": len(source_mesh.faces),
        "carve_source_vertex_count": len(source_mesh.vertices),
        "carve_result_face_count": len(mesh.faces),
        "carve_result_vertex_count": len(mesh.vertices),
        "carve_result_watertight": bool(mesh.is_watertight),
        "kernel_carve": carve_metadata,
        "kernel_program_carve": carve_metadata,
        **carve_details,
        "kernel_program_semantic_handoff": semantic_handoff,
    }
    return KernelProgramResult(
        mesh=mesh,
        handle=current,
        operation_count=operation_count,
        details=details,
    )


__all__ = [
    "build_carve_program_manifest",
    "execute_carve_program",
]
