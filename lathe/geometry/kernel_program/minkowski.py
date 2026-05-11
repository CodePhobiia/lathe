"""Minkowski program — Minkowski sum of source and structuring operands.

Per the §5.3 decomposition, this module hosts the minkowski family:
op.minkowski. The executor takes exact-rebuild paths for many
recognized primitive pairs (box ⊕ box, box ⊕ sphere/capsule/cylinder,
sphere ⊕ sphere, cylinder ⊕ sphere/cylinder/capsule,
capsule ⊕ sphere/capsule). When no exact path applies, it falls
through to a convex vertex-sum hull approximation and records the
approximation explicitly in the trace.
"""

from __future__ import annotations

from contextlib import suppress
import math
from typing import Any

import numpy as np
import trimesh

from ..kernel import GeometryKernel
from ._capabilities import (
    _kernel_capabilities,
    _require_capabilities,
    _validate_minkowski_operands,
)
from ._common import (
    _non_empty_mesh,
    _operation_id_fragment,
    _record_result_probe,
)
from ._core import (
    KernelOperand,
    KernelProgramResult,
    _exact_rebuild_required_capabilities,
    _required_capability_list,
    minkowski_operation_count,
)
from ._face_operation import _attach_semantic_whole_result_face_metadata
from ._feature_detail import _kernel_feature_detail_metadata
from ._primitive_metadata import (
    _axis_aligned_box_metadata,
    _axis_index,
    _box_extents_in_extruded_profile_plane,
    _capsule_metadata,
    _cylinder_metadata,
    _positive_triplet,
    _rounded_rectangle_profile_points,
    _sphere_metadata,
)
from ._records import _operand_operation_records
from ._semantic import (
    _operation_counts,
    _semantic_operation_records_from_manifest,
)
from ._semantic_handoff import _attach_kernel_program_semantic_handoff
from ._serialize import _dict_metadata, _json_safe

KERNEL_PROGRAM_VERSION = "lathe.geometry.kernel_program_v1"


def _exact_axis_aligned_box_minkowski_params(
    source_mesh: trimesh.Trimesh,
    structuring_mesh: trimesh.Trimesh,
    *,
    structuring_center: tuple[float, float, float],
) -> dict[str, Any] | None:
    source_box = _axis_aligned_box_metadata(source_mesh)
    structuring_box = _axis_aligned_box_metadata(structuring_mesh)
    if source_box is None or structuring_box is None:
        return None
    center_offset = tuple(
        float(structuring_box["center"][axis]) - float(structuring_center[axis])
        for axis in range(3)
    )
    center = tuple(
        float(source_box["center"][axis]) + center_offset[axis]
        for axis in range(3)
    )
    extents = tuple(
        float(source_box["extents"][axis]) + float(structuring_box["extents"][axis])
        for axis in range(3)
    )
    if not _positive_triplet(extents):
        return None
    return {
        "center": center,
        "extents": extents,
        "source_box": source_box,
        "structuring_box": structuring_box,
        "structuring_center": structuring_center,
        "structuring_center_offset": center_offset,
    }


def _exact_axis_aligned_box_sphere_minkowski_params(
    source_mesh: trimesh.Trimesh,
    structuring_mesh: trimesh.Trimesh,
    *,
    structuring_center: tuple[float, float, float],
) -> dict[str, Any] | None:
    source_box = _axis_aligned_box_metadata(source_mesh)
    structuring_sphere = _sphere_metadata(structuring_mesh)
    if source_box is not None and structuring_sphere is not None:
        radius = float(structuring_sphere["radius"])
        center_offset = tuple(
            float(structuring_sphere["center"][axis]) - float(structuring_center[axis])
            for axis in range(3)
        )
        center = tuple(
            float(source_box["center"][axis]) + center_offset[axis]
            for axis in range(3)
        )
        extents = tuple(float(source_box["extents"][axis]) + 2.0 * radius for axis in range(3))
        if _positive_triplet(extents) and radius <= min(extents) * 0.5 * 0.92:
            return {
                "center": center,
                "extents": extents,
                "rounding": radius,
                "source_box": source_box,
                "structuring_sphere": structuring_sphere,
                "structuring_center": structuring_center,
                "structuring_center_offset": center_offset,
            }

    source_sphere = _sphere_metadata(source_mesh)
    structuring_box = _axis_aligned_box_metadata(structuring_mesh)
    if source_sphere is not None and structuring_box is not None:
        radius = float(source_sphere["radius"])
        center = tuple(
            float(source_sphere["center"][axis])
            + float(structuring_box["center"][axis])
            - float(structuring_center[axis])
            for axis in range(3)
        )
        extents = tuple(float(structuring_box["extents"][axis]) + 2.0 * radius for axis in range(3))
        if _positive_triplet(extents) and radius <= min(extents) * 0.5 * 0.92:
            return {
                "center": center,
                "extents": extents,
                "rounding": radius,
                "source_sphere": source_sphere,
                "structuring_box": structuring_box,
                "structuring_center": structuring_center,
                "structuring_center_offset": tuple(
                    float(structuring_box["center"][axis]) - float(structuring_center[axis])
                    for axis in range(3)
                ),
            }
    return None


def _exact_sphere_sphere_minkowski_params(
    source_mesh: trimesh.Trimesh,
    structuring_mesh: trimesh.Trimesh,
    *,
    structuring_center: tuple[float, float, float],
) -> dict[str, Any] | None:
    source_sphere = _sphere_metadata(source_mesh)
    structuring_sphere = _sphere_metadata(structuring_mesh)
    if source_sphere is None or structuring_sphere is None:
        return None
    radius = float(source_sphere["radius"]) + float(structuring_sphere["radius"])
    if radius <= 0.0 or not math.isfinite(radius):
        return None
    center_offset = tuple(
        float(structuring_sphere["center"][axis]) - float(structuring_center[axis])
        for axis in range(3)
    )
    center = tuple(
        float(source_sphere["center"][axis]) + center_offset[axis]
        for axis in range(3)
    )
    return {
        "center": center,
        "radius": radius,
        "source_sphere": source_sphere,
        "structuring_sphere": structuring_sphere,
        "structuring_center": structuring_center,
        "structuring_center_offset": center_offset,
    }


def _exact_cylinder_sphere_minkowski_params(
    source_mesh: trimesh.Trimesh,
    structuring_mesh: trimesh.Trimesh,
    *,
    structuring_center: tuple[float, float, float],
) -> dict[str, Any] | None:
    source_cylinder = _cylinder_metadata(source_mesh)
    structuring_sphere = _sphere_metadata(structuring_mesh)
    if source_cylinder is not None and structuring_sphere is not None:
        sphere_radius = float(structuring_sphere["radius"])
        center_offset = tuple(
            float(structuring_sphere["center"][axis]) - float(structuring_center[axis])
            for axis in range(3)
        )
        center = tuple(
            float(source_cylinder["center"][axis]) + center_offset[axis]
            for axis in range(3)
        )
        radius = float(source_cylinder["radius"]) + sphere_radius
        length = float(source_cylinder["height"]) + 2.0 * sphere_radius
        if length > 2.0 * radius and radius > 0.0:
            return {
                "center": center,
                "radius": radius,
                "length": length,
                "axis": str(source_cylinder["axis"]),
                "source_cylinder": source_cylinder,
                "structuring_sphere": structuring_sphere,
                "structuring_center": structuring_center,
                "structuring_center_offset": center_offset,
            }

    source_sphere = _sphere_metadata(source_mesh)
    structuring_cylinder = _cylinder_metadata(structuring_mesh)
    if source_sphere is not None and structuring_cylinder is not None:
        sphere_radius = float(source_sphere["radius"])
        center = tuple(
            float(source_sphere["center"][axis])
            + float(structuring_cylinder["center"][axis])
            - float(structuring_center[axis])
            for axis in range(3)
        )
        radius = float(structuring_cylinder["radius"]) + sphere_radius
        length = float(structuring_cylinder["height"]) + 2.0 * sphere_radius
        if length > 2.0 * radius and radius > 0.0:
            return {
                "center": center,
                "radius": radius,
                "length": length,
                "axis": str(structuring_cylinder["axis"]),
                "source_sphere": source_sphere,
                "structuring_cylinder": structuring_cylinder,
                "structuring_center": structuring_center,
                "structuring_center_offset": tuple(
                    float(structuring_cylinder["center"][axis]) - float(structuring_center[axis])
                    for axis in range(3)
                ),
            }
    return None


def _exact_cylinder_cylinder_minkowski_params(
    source_mesh: trimesh.Trimesh,
    structuring_mesh: trimesh.Trimesh,
    *,
    structuring_center: tuple[float, float, float],
) -> dict[str, Any] | None:
    source_cylinder = _cylinder_metadata(source_mesh)
    structuring_cylinder = _cylinder_metadata(structuring_mesh)
    if source_cylinder is None or structuring_cylinder is None:
        return None
    source_axis = str(source_cylinder["axis"])
    structuring_axis = str(structuring_cylinder["axis"])
    if source_axis != structuring_axis:
        return None
    radius = float(source_cylinder["radius"]) + float(structuring_cylinder["radius"])
    height = float(source_cylinder["height"]) + float(structuring_cylinder["height"])
    if radius <= 0.0 or height <= 0.0 or not math.isfinite(radius) or not math.isfinite(height):
        return None
    center_offset = tuple(
        float(structuring_cylinder["center"][axis]) - float(structuring_center[axis])
        for axis in range(3)
    )
    center = tuple(
        float(source_cylinder["center"][axis]) + center_offset[axis]
        for axis in range(3)
    )
    return {
        "center": center,
        "radius": radius,
        "height": height,
        "axis": source_axis,
        "source_cylinder": source_cylinder,
        "structuring_cylinder": structuring_cylinder,
        "structuring_center": structuring_center,
        "structuring_center_offset": center_offset,
    }


def _exact_cylinder_capsule_minkowski_params(
    source_mesh: trimesh.Trimesh,
    structuring_mesh: trimesh.Trimesh,
    *,
    structuring_center: tuple[float, float, float],
) -> dict[str, Any] | None:
    source_cylinder = _cylinder_metadata(source_mesh)
    structuring_capsule = _capsule_metadata(structuring_mesh)
    if source_cylinder is not None and structuring_capsule is not None:
        axis = str(source_cylinder["axis"])
        if axis != str(structuring_capsule["axis"]):
            return None
        radius = float(source_cylinder["radius"]) + float(structuring_capsule["radius"])
        length = float(source_cylinder["height"]) + float(structuring_capsule["length"])
        if length <= 2.0 * radius or radius <= 0.0:
            return None
        center_offset = tuple(
            float(structuring_capsule["center"][index]) - float(structuring_center[index])
            for index in range(3)
        )
        center = tuple(
            float(source_cylinder["center"][index]) + center_offset[index]
            for index in range(3)
        )
        return {
            "center": center,
            "radius": radius,
            "length": length,
            "axis": axis,
            "source_cylinder": source_cylinder,
            "structuring_capsule": structuring_capsule,
            "structuring_center": structuring_center,
            "structuring_center_offset": center_offset,
        }

    source_capsule = _capsule_metadata(source_mesh)
    structuring_cylinder = _cylinder_metadata(structuring_mesh)
    if source_capsule is not None and structuring_cylinder is not None:
        axis = str(source_capsule["axis"])
        if axis != str(structuring_cylinder["axis"]):
            return None
        radius = float(source_capsule["radius"]) + float(structuring_cylinder["radius"])
        length = float(source_capsule["length"]) + float(structuring_cylinder["height"])
        if length <= 2.0 * radius or radius <= 0.0:
            return None
        center = tuple(
            float(source_capsule["center"][index])
            + float(structuring_cylinder["center"][index])
            - float(structuring_center[index])
            for index in range(3)
        )
        return {
            "center": center,
            "radius": radius,
            "length": length,
            "axis": axis,
            "source_capsule": source_capsule,
            "structuring_cylinder": structuring_cylinder,
            "structuring_center": structuring_center,
            "structuring_center_offset": tuple(
                float(structuring_cylinder["center"][index]) - float(structuring_center[index])
                for index in range(3)
            ),
        }
    return None


def _exact_capsule_sphere_minkowski_params(
    source_mesh: trimesh.Trimesh,
    structuring_mesh: trimesh.Trimesh,
    *,
    structuring_center: tuple[float, float, float],
) -> dict[str, Any] | None:
    source_capsule = _capsule_metadata(source_mesh)
    structuring_sphere = _sphere_metadata(structuring_mesh)
    if source_capsule is not None and structuring_sphere is not None:
        sphere_radius = float(structuring_sphere["radius"])
        center_offset = tuple(
            float(structuring_sphere["center"][axis]) - float(structuring_center[axis])
            for axis in range(3)
        )
        center = tuple(
            float(source_capsule["center"][axis]) + center_offset[axis]
            for axis in range(3)
        )
        radius = float(source_capsule["radius"]) + sphere_radius
        length = float(source_capsule["length"]) + 2.0 * sphere_radius
        if length > 2.0 * radius and radius > 0.0:
            return {
                "center": center,
                "radius": radius,
                "length": length,
                "axis": str(source_capsule["axis"]),
                "source_capsule": source_capsule,
                "structuring_sphere": structuring_sphere,
                "structuring_center": structuring_center,
                "structuring_center_offset": center_offset,
            }

    source_sphere = _sphere_metadata(source_mesh)
    structuring_capsule = _capsule_metadata(structuring_mesh)
    if source_sphere is not None and structuring_capsule is not None:
        sphere_radius = float(source_sphere["radius"])
        center = tuple(
            float(source_sphere["center"][axis])
            + float(structuring_capsule["center"][axis])
            - float(structuring_center[axis])
            for axis in range(3)
        )
        radius = float(structuring_capsule["radius"]) + sphere_radius
        length = float(structuring_capsule["length"]) + 2.0 * sphere_radius
        if length > 2.0 * radius and radius > 0.0:
            return {
                "center": center,
                "radius": radius,
                "length": length,
                "axis": str(structuring_capsule["axis"]),
                "source_sphere": source_sphere,
                "structuring_capsule": structuring_capsule,
                "structuring_center": structuring_center,
                "structuring_center_offset": tuple(
                    float(structuring_capsule["center"][axis]) - float(structuring_center[axis])
                    for axis in range(3)
                ),
            }
    return None


def _exact_capsule_capsule_minkowski_params(
    source_mesh: trimesh.Trimesh,
    structuring_mesh: trimesh.Trimesh,
    *,
    structuring_center: tuple[float, float, float],
) -> dict[str, Any] | None:
    source_capsule = _capsule_metadata(source_mesh)
    structuring_capsule = _capsule_metadata(structuring_mesh)
    if source_capsule is None or structuring_capsule is None:
        return None
    source_axis = str(source_capsule["axis"])
    structuring_axis = str(structuring_capsule["axis"])
    if source_axis != structuring_axis:
        return None
    radius = float(source_capsule["radius"]) + float(structuring_capsule["radius"])
    length = float(source_capsule["length"]) + float(structuring_capsule["length"])
    if length <= 2.0 * radius or radius <= 0.0:
        return None
    center_offset = tuple(
        float(structuring_capsule["center"][axis]) - float(structuring_center[axis])
        for axis in range(3)
    )
    center = tuple(
        float(source_capsule["center"][axis]) + center_offset[axis]
        for axis in range(3)
    )
    return {
        "center": center,
        "radius": radius,
        "length": length,
        "axis": source_axis,
        "source_capsule": source_capsule,
        "structuring_capsule": structuring_capsule,
        "structuring_center": structuring_center,
        "structuring_center_offset": center_offset,
    }


def _exact_axis_aligned_box_cylinder_minkowski_params(
    source_mesh: trimesh.Trimesh,
    structuring_mesh: trimesh.Trimesh,
    *,
    structuring_center: tuple[float, float, float],
) -> dict[str, Any] | None:
    source_box = _axis_aligned_box_metadata(source_mesh)
    structuring_cylinder = _cylinder_metadata(structuring_mesh)
    if source_box is not None and structuring_cylinder is not None:
        axis = str(structuring_cylinder["axis"])
        plane_extents = _box_extents_in_extruded_profile_plane(source_box, axis=axis)
        if plane_extents is None:
            return None
        plane_u, plane_v, axial = plane_extents
        radius = float(structuring_cylinder["radius"])
        height = float(structuring_cylinder["height"])
        center_offset = tuple(
            float(structuring_cylinder["center"][axis_index]) - float(structuring_center[axis_index])
            for axis_index in range(3)
        )
        center = tuple(
            float(source_box["center"][axis_index]) + center_offset[axis_index]
            for axis_index in range(3)
        )
        if radius > 0.0 and height > 0.0 and plane_u > 0.0 and plane_v > 0.0 and axial > 0.0:
            profile = _rounded_rectangle_profile_points(
                width=plane_u + 2.0 * radius,
                height=plane_v + 2.0 * radius,
                radius=radius,
            )
            return {
                "center": center,
                "axis": axis,
                "profile_polygon": profile,
                "extrude_height": axial + height,
                "rounding_radius": radius,
                "profile_width": plane_u + 2.0 * radius,
                "profile_height": plane_v + 2.0 * radius,
                "source_box": source_box,
                "structuring_cylinder": structuring_cylinder,
                "structuring_center": structuring_center,
                "structuring_center_offset": center_offset,
            }

    source_cylinder = _cylinder_metadata(source_mesh)
    structuring_box = _axis_aligned_box_metadata(structuring_mesh)
    if source_cylinder is not None and structuring_box is not None:
        axis = str(source_cylinder["axis"])
        plane_extents = _box_extents_in_extruded_profile_plane(structuring_box, axis=axis)
        if plane_extents is None:
            return None
        plane_u, plane_v, axial = plane_extents
        radius = float(source_cylinder["radius"])
        height = float(source_cylinder["height"])
        center = tuple(
            float(source_cylinder["center"][axis_index])
            + float(structuring_box["center"][axis_index])
            - float(structuring_center[axis_index])
            for axis_index in range(3)
        )
        if radius > 0.0 and height > 0.0 and plane_u > 0.0 and plane_v > 0.0 and axial > 0.0:
            profile = _rounded_rectangle_profile_points(
                width=plane_u + 2.0 * radius,
                height=plane_v + 2.0 * radius,
                radius=radius,
            )
            return {
                "center": center,
                "axis": axis,
                "profile_polygon": profile,
                "extrude_height": axial + height,
                "rounding_radius": radius,
                "profile_width": plane_u + 2.0 * radius,
                "profile_height": plane_v + 2.0 * radius,
                "source_cylinder": source_cylinder,
                "structuring_box": structuring_box,
                "structuring_center": structuring_center,
                "structuring_center_offset": tuple(
                    float(structuring_box["center"][axis_index]) - float(structuring_center[axis_index])
                    for axis_index in range(3)
                ),
            }
    return None


def _exact_axis_aligned_box_capsule_minkowski_params(
    source_mesh: trimesh.Trimesh,
    structuring_mesh: trimesh.Trimesh,
    *,
    structuring_center: tuple[float, float, float],
) -> dict[str, Any] | None:
    source_box = _axis_aligned_box_metadata(source_mesh)
    structuring_capsule = _capsule_metadata(structuring_mesh)
    if source_box is not None and structuring_capsule is not None:
        axis = str(structuring_capsule["axis"])
        axis_index = _axis_index(axis)
        radius = float(structuring_capsule["radius"])
        extents = [
            float(value) + 2.0 * radius
            for value in source_box["extents"]
        ]
        extents[axis_index] = float(source_box["extents"][axis_index]) + float(structuring_capsule["length"])
        center_offset = tuple(
            float(structuring_capsule["center"][index]) - float(structuring_center[index])
            for index in range(3)
        )
        center = tuple(
            float(source_box["center"][index]) + center_offset[index]
            for index in range(3)
        )
        if _positive_triplet((extents[0], extents[1], extents[2])) and radius <= min(extents) * 0.5 * 0.92:
            return {
                "center": center,
                "extents": tuple(extents),
                "rounding": radius,
                "axis": axis,
                "source_box": source_box,
                "structuring_capsule": structuring_capsule,
                "structuring_center": structuring_center,
                "structuring_center_offset": center_offset,
            }

    source_capsule = _capsule_metadata(source_mesh)
    structuring_box = _axis_aligned_box_metadata(structuring_mesh)
    if source_capsule is not None and structuring_box is not None:
        axis = str(source_capsule["axis"])
        axis_index = _axis_index(axis)
        radius = float(source_capsule["radius"])
        extents = [
            float(value) + 2.0 * radius
            for value in structuring_box["extents"]
        ]
        extents[axis_index] = float(structuring_box["extents"][axis_index]) + float(source_capsule["length"])
        center = tuple(
            float(source_capsule["center"][index])
            + float(structuring_box["center"][index])
            - float(structuring_center[index])
            for index in range(3)
        )
        if _positive_triplet((extents[0], extents[1], extents[2])) and radius <= min(extents) * 0.5 * 0.92:
            return {
                "center": center,
                "extents": tuple(extents),
                "rounding": radius,
                "axis": axis,
                "source_capsule": source_capsule,
                "structuring_box": structuring_box,
                "structuring_center": structuring_center,
                "structuring_center_offset": tuple(
                    float(structuring_box["center"][index]) - float(structuring_center[index])
                    for index in range(3)
                ),
            }
    return None


def build_minkowski_program_manifest(
    source: KernelOperand,
    structuring: KernelOperand,
    *,
    route: str = "convex_minkowski_program",
    backend: str | None = None,
    operation_limit: int | None = None,
    sample_limit: int = 50_000,
    pair_count: int | None = None,
    sample_stride: int | None = None,
    sample_count: int | None = None,
    approximation: str = "convex_vertex_sum_hull",
    required_capabilities: list[str] | None = None,
) -> dict[str, Any]:
    """Return a deterministic, handle-free manifest for a Minkowski program."""
    operands = [source, structuring]
    operation_records = _operand_operation_records(operands)
    if not any(str(record.get("operation") or "") == "op.minkowski" for record in operation_records):
        operation_records.append(
            {
                "operation_id": f"program:{_operation_id_fragment(route)}:op_minkowski",
                "operation": "op.minkowski",
                "repair_action": "",
                "operand_id": "",
                "operand_index": -1,
                "part": "",
                "primitive_type": "",
                "blend_mode": "",
                "source": "kernel_program.minkowski",
            }
        )
    missing_handle_ids = [operand.operand_id for operand in operands if operand.handle is None]
    diagnostics: list[dict[str, Any]] = []
    if missing_handle_ids:
        diagnostics.append(
            {
                "code": "missing_kernel_operand_handle",
                "severity": "error",
                "operand_ids": missing_handle_ids,
            }
        )
    operation_count = minkowski_operation_count(source, structuring)
    if operation_limit is not None and operation_count > operation_limit:
        diagnostics.append(
            {
                "code": "kernel_program_operation_limit_exceeded",
                "severity": "error",
                "operation_count": operation_count,
                "operation_limit": operation_limit,
            }
        )
    if sample_limit <= 0:
        diagnostics.append(
            {
                "code": "invalid_minkowski_sample_limit",
                "severity": "error",
                "sample_limit": sample_limit,
            }
        )
    return {
        "schema": "lathe.geometry.kernel_program_manifest.v1",
        "version": KERNEL_PROGRAM_VERSION,
        "program_kind": "minkowski",
        "route": route,
        "backend": backend,
        "operation_count": operation_count,
        "kernel_call_count": operation_count,
        "operation_limit": operation_limit,
        "required_capabilities": _required_capability_list(
            required_capabilities or ["hull"],
            "to_trimesh",
        ),
        "operand_count": len(operands),
        "operands": [_json_safe(operand.trace_record()) for operand in operands],
        "semantic_operation_record_count": len(operation_records),
        "semantic_operation_counts": _operation_counts(operation_records),
        "semantic_operation_records": _json_safe(operation_records),
        "approximation": approximation,
        "sample_limit": int(sample_limit),
        "pair_count": pair_count,
        "sample_stride": sample_stride,
        "sample_count": sample_count,
        "diagnostics": diagnostics,
    }


def execute_minkowski_program(
    kernel: GeometryKernel,
    source: KernelOperand,
    structuring: KernelOperand,
    *,
    structuring_center: tuple[float, float, float] = (0.0, 0.0, 0.0),
    sample_limit: int = 50_000,
    operation_limit: int | None = None,
    route: str = "convex_minkowski_program",
    backend: str | None = None,
) -> KernelProgramResult:
    """Execute a deterministic Minkowski construction.

    Exact axis-aligned box cases lower to native kernel primitives. General
    convex operands still use the vertex-sum convex hull fallback and record
    that approximation explicitly.
    """
    if sample_limit <= 0:
        raise ValueError("kernel minkowski sample_limit must be positive")
    _validate_minkowski_operands(source, structuring)
    operation_count = minkowski_operation_count(source, structuring)
    if operation_limit is not None and operation_count > operation_limit:
        raise ValueError(
            f"kernel minkowski operation_count={operation_count} exceeds limit={operation_limit}"
        )
    capabilities = _kernel_capabilities(kernel)
    _require_capabilities(kernel, capabilities, {"to_trimesh"})

    source_mesh = _non_empty_mesh(kernel, source.handle)
    structuring_mesh = _non_empty_mesh(kernel, structuring.handle)
    source_vertex_count = len(source_mesh.vertices)
    structuring_vertex_count = len(structuring_mesh.vertices)
    pair_count = source_vertex_count * structuring_vertex_count
    if source_vertex_count == 0 or structuring_vertex_count == 0:
        raise ValueError("kernel minkowski requires non-empty source and structuring meshes")

    exact_box_params = _exact_axis_aligned_box_minkowski_params(
        source_mesh,
        structuring_mesh,
        structuring_center=structuring_center,
    )
    exact_round_box_params = None
    if exact_box_params is None:
        exact_round_box_params = _exact_axis_aligned_box_sphere_minkowski_params(
            source_mesh,
            structuring_mesh,
            structuring_center=structuring_center,
        )
    if exact_box_params is None and exact_round_box_params is None:
        exact_box_capsule_params = _exact_axis_aligned_box_capsule_minkowski_params(
            source_mesh,
            structuring_mesh,
            structuring_center=structuring_center,
        )
    else:
        exact_box_capsule_params = None
    if (
        exact_box_params is None
        and exact_round_box_params is None
        and exact_box_capsule_params is None
    ):
        exact_box_cylinder_params = _exact_axis_aligned_box_cylinder_minkowski_params(
            source_mesh,
            structuring_mesh,
            structuring_center=structuring_center,
        )
    else:
        exact_box_cylinder_params = None
    exact_sphere_params = None
    if (
        exact_box_params is None
        and exact_round_box_params is None
        and exact_box_capsule_params is None
    ):
        exact_cylinder_cylinder_params = _exact_cylinder_cylinder_minkowski_params(
            source_mesh,
            structuring_mesh,
            structuring_center=structuring_center,
        )
    else:
        exact_cylinder_cylinder_params = None
    if (
        exact_box_params is None
        and exact_round_box_params is None
        and exact_box_capsule_params is None
        and exact_box_cylinder_params is None
        and exact_cylinder_cylinder_params is None
    ):
        exact_cylinder_capsule_params = _exact_cylinder_capsule_minkowski_params(
            source_mesh,
            structuring_mesh,
            structuring_center=structuring_center,
        )
    else:
        exact_cylinder_capsule_params = None
    if (
        exact_box_params is None
        and exact_round_box_params is None
        and exact_box_capsule_params is None
        and exact_box_cylinder_params is None
        and exact_cylinder_cylinder_params is None
        and exact_cylinder_capsule_params is None
    ):
        exact_capsule_capsule_params = _exact_capsule_capsule_minkowski_params(
            source_mesh,
            structuring_mesh,
            structuring_center=structuring_center,
        )
    else:
        exact_capsule_capsule_params = None
    if (
        exact_box_params is None
        and exact_round_box_params is None
        and exact_box_capsule_params is None
        and exact_box_cylinder_params is None
        and exact_cylinder_cylinder_params is None
        and exact_cylinder_capsule_params is None
        and exact_capsule_capsule_params is None
    ):
        exact_capsule_sphere_params = _exact_capsule_sphere_minkowski_params(
            source_mesh,
            structuring_mesh,
            structuring_center=structuring_center,
        )
    else:
        exact_capsule_sphere_params = None
    if (
        exact_box_params is None
        and exact_round_box_params is None
        and exact_box_capsule_params is None
        and exact_box_cylinder_params is None
        and exact_cylinder_cylinder_params is None
        and exact_cylinder_capsule_params is None
        and exact_capsule_capsule_params is None
        and exact_capsule_sphere_params is None
    ):
        exact_cylinder_sphere_params = _exact_cylinder_sphere_minkowski_params(
            source_mesh,
            structuring_mesh,
            structuring_center=structuring_center,
        )
    else:
        exact_cylinder_sphere_params = None
    if (
        exact_box_params is None
        and exact_round_box_params is None
        and exact_box_cylinder_params is None
        and exact_cylinder_cylinder_params is None
        and exact_cylinder_capsule_params is None
        and exact_capsule_capsule_params is None
        and exact_capsule_sphere_params is None
        and exact_cylinder_sphere_params is None
    ):
        exact_sphere_params = _exact_sphere_sphere_minkowski_params(
            source_mesh,
            structuring_mesh,
            structuring_center=structuring_center,
        )
    else:
        exact_sphere_params = None
    exact_minkowski_params: dict[str, Any] | None = None
    if exact_box_params is not None:
        exact_minkowski_params = {
            **exact_box_params,
            "required_capability": "box",
            "required_capabilities": ["box"],
            "primitive_type": "box",
            "method": "exact_axis_aligned_box_sum_v1",
            "actual_operation": "axis_aligned_box_minkowski_sum",
            "approximation": "none_exact_axis_aligned_box_sum",
            "result_kind": "box",
            "rounding": 0.0,
        }
    elif exact_round_box_params is not None:
        exact_minkowski_params = {
            **exact_round_box_params,
            "required_capability": "box_rounding",
            "required_capabilities": ["box", "box_rounding"],
            "primitive_type": "box",
            "method": "exact_axis_aligned_box_sphere_rounding_v1",
            "actual_operation": "axis_aligned_box_sphere_minkowski_sum",
            "approximation": "none_exact_axis_aligned_box_sphere_rounding",
            "result_kind": "rounded_box",
        }
    elif exact_box_capsule_params is not None:
        exact_minkowski_params = {
            **exact_box_capsule_params,
            "required_capability": "box_rounding",
            "required_capabilities": ["box", "box_rounding"],
            "primitive_type": "box",
            "method": "exact_axis_aligned_box_capsule_rounding_v1",
            "actual_operation": "axis_aligned_box_capsule_minkowski_sum",
            "approximation": "none_exact_axis_aligned_box_capsule_rounding",
            "result_kind": "rounded_box",
        }
    elif exact_box_cylinder_params is not None:
        exact_minkowski_params = {
            **exact_box_cylinder_params,
            "required_capability": "extruded_profile",
            "required_capabilities": ["extruded_profile"],
            "primitive_type": "extruded_profile",
            "method": "exact_axis_aligned_box_cylinder_profile_sum_v1",
            "actual_operation": "axis_aligned_box_cylinder_minkowski_sum",
            "approximation": "none_exact_axis_aligned_box_cylinder_profile_sum",
            "result_kind": "rounded_rectangle_extruded_profile",
            "rounding": 0.0,
        }
    elif exact_cylinder_cylinder_params is not None:
        exact_minkowski_params = {
            **exact_cylinder_cylinder_params,
            "required_capability": "cylinder",
            "required_capabilities": ["cylinder"],
            "primitive_type": "cylinder",
            "method": "exact_coaxial_cylinder_sum_v1",
            "actual_operation": "coaxial_cylinder_minkowski_sum",
            "approximation": "none_exact_coaxial_cylinder_sum",
            "result_kind": "cylinder",
            "rounding": 0.0,
        }
    elif exact_cylinder_capsule_params is not None:
        exact_minkowski_params = {
            **exact_cylinder_capsule_params,
            "required_capability": "capsule",
            "required_capabilities": ["capsule"],
            "primitive_type": "capsule",
            "method": "exact_coaxial_cylinder_capsule_sum_v1",
            "actual_operation": "coaxial_cylinder_capsule_minkowski_sum",
            "approximation": "none_exact_coaxial_cylinder_capsule_sum",
            "result_kind": "capsule",
            "rounding": 0.0,
        }
    elif exact_capsule_capsule_params is not None:
        exact_minkowski_params = {
            **exact_capsule_capsule_params,
            "required_capability": "capsule",
            "required_capabilities": ["capsule"],
            "primitive_type": "capsule",
            "method": "exact_coaxial_capsule_sum_v1",
            "actual_operation": "coaxial_capsule_minkowski_sum",
            "approximation": "none_exact_coaxial_capsule_sum",
            "result_kind": "capsule",
            "rounding": 0.0,
        }
    elif exact_capsule_sphere_params is not None:
        exact_minkowski_params = {
            **exact_capsule_sphere_params,
            "required_capability": "capsule",
            "required_capabilities": ["capsule"],
            "primitive_type": "capsule",
            "method": "exact_capsule_sphere_sum_v1",
            "actual_operation": "capsule_sphere_minkowski_sum",
            "approximation": "none_exact_capsule_sphere_sum",
            "result_kind": "capsule",
            "rounding": 0.0,
        }
    elif exact_cylinder_sphere_params is not None:
        exact_minkowski_params = {
            **exact_cylinder_sphere_params,
            "required_capability": "capsule",
            "required_capabilities": ["capsule"],
            "primitive_type": "capsule",
            "method": "exact_cylinder_sphere_capsule_sum_v1",
            "actual_operation": "cylinder_sphere_minkowski_sum",
            "approximation": "none_exact_cylinder_sphere_capsule_sum",
            "result_kind": "capsule",
            "rounding": 0.0,
        }
    elif exact_sphere_params is not None:
        exact_minkowski_params = {
            **exact_sphere_params,
            "required_capability": "sphere",
            "required_capabilities": ["sphere"],
            "primitive_type": "sphere",
            "method": "exact_sphere_sum_v1",
            "actual_operation": "sphere_minkowski_sum",
            "approximation": "none_exact_sphere_sum",
            "result_kind": "sphere",
            "rounding": 0.0,
        }
    exact_box_failure: str | None = None
    exact_required_capabilities = _exact_rebuild_required_capabilities(
        exact_minkowski_params
    )
    if (
        exact_minkowski_params is not None
        and exact_required_capabilities
        and all(capabilities.get(str(name)) is True for name in exact_required_capabilities)
    ):
        manifest = build_minkowski_program_manifest(
            source,
            structuring,
            route=route,
            backend=backend,
            operation_limit=operation_limit,
            sample_limit=sample_limit,
            pair_count=pair_count,
            sample_stride=0,
            sample_count=0,
            approximation=str(exact_minkowski_params["approximation"]),
            required_capabilities=[str(name) for name in exact_required_capabilities],
        )
        result_extents = exact_minkowski_params.get("extents")
        result_radius = exact_minkowski_params.get("radius")
        result_length = exact_minkowski_params.get("length")
        result_height = exact_minkowski_params.get("height")
        result_extrude_height = exact_minkowski_params.get("extrude_height")
        result_profile_polygon = exact_minkowski_params.get("profile_polygon")
        result_axis = exact_minkowski_params.get("axis")
        operation_record = {
            "op": "minkowski",
            "source": source.operand_id,
            "structuring": structuring.operand_id,
            "attempted_kernel": kernel.name,
            "actual_kernel": kernel.name,
            "attempted_backend": f"{kernel.name}.build_primitive",
            "actual_backend": f"{kernel.name}.build_primitive",
            "actual_operation": str(exact_minkowski_params["actual_operation"]),
            "kernel_minkowski_method": str(exact_minkowski_params["method"]),
            "exact_kernel_path": True,
            "fallback": False,
            "passthrough": False,
            "approximation": "none",
            "result_kind": str(exact_minkowski_params["result_kind"]),
            "source_vertex_count": source_vertex_count,
            "structuring_vertex_count": structuring_vertex_count,
            "pair_count": pair_count,
            "sample_stride": 0,
            "sample_count": 0,
            "structuring_center": list(exact_minkowski_params["structuring_center"]),
            "structuring_center_offset": list(exact_minkowski_params["structuring_center_offset"]),
            "result_center": list(exact_minkowski_params["center"]),
        }
        if result_extents is not None:
            operation_record["result_extents"] = list(result_extents)
        if result_radius is not None:
            operation_record["result_radius"] = float(result_radius)
        if result_length is not None:
            operation_record["result_length"] = float(result_length)
        if result_height is not None:
            operation_record["result_height"] = float(result_height)
        if result_extrude_height is not None:
            operation_record["result_extrude_height"] = float(result_extrude_height)
        if isinstance(result_profile_polygon, list):
            operation_record["result_profile_point_count"] = len(result_profile_polygon)
        if result_axis is not None:
            operation_record["result_axis"] = str(result_axis)
        for metadata_name in (
            "source_box",
            "structuring_box",
            "source_cylinder",
            "structuring_cylinder",
            "source_capsule",
            "structuring_capsule",
            "source_sphere",
            "structuring_sphere",
        ):
            if metadata_name in exact_minkowski_params:
                operation_record[metadata_name] = _json_safe(exact_minkowski_params[metadata_name])
        try:
            part = source.part or "minkowski"
            primitive_type = str(exact_minkowski_params.get("primitive_type") or "box")
            build_kwargs: dict[str, Any] = {
                "center": exact_minkowski_params["center"],
                "part": f"{part}_minkowski",
                "semantic_metadata": {
                    "kernel_program": {
                        "op": "minkowski",
                        "method": str(exact_minkowski_params["method"]),
                        "source_operand_id": source.operand_id,
                        "structuring_operand_id": structuring.operand_id,
                    }
                },
            }
            if primitive_type == "sphere":
                build_kwargs["radius"] = exact_minkowski_params["radius"]
            elif primitive_type == "capsule":
                build_kwargs["radius"] = exact_minkowski_params["radius"]
                build_kwargs["length"] = exact_minkowski_params["length"]
                build_kwargs["axis"] = exact_minkowski_params["axis"]
            elif primitive_type == "cylinder":
                build_kwargs["radius"] = exact_minkowski_params["radius"]
                build_kwargs["height"] = exact_minkowski_params["height"]
                build_kwargs["axis"] = exact_minkowski_params["axis"]
            elif primitive_type == "extruded_profile":
                build_kwargs["profile_polygon"] = exact_minkowski_params["profile_polygon"]
                build_kwargs["extrude_height"] = exact_minkowski_params["extrude_height"]
                build_kwargs["axis"] = exact_minkowski_params["axis"]
            else:
                build_kwargs["extents"] = exact_minkowski_params["extents"]
                build_kwargs["rounding"] = float(exact_minkowski_params.get("rounding") or 0.0)
            current = kernel.build_primitive(primitive_type, **build_kwargs)
            mesh = _non_empty_mesh(kernel, current)
            if primitive_type == "sphere":
                shape_payload = {"radius": float(exact_minkowski_params["radius"])}
            elif primitive_type == "capsule":
                shape_payload = {
                    "radius": float(exact_minkowski_params["radius"]),
                    "length": float(exact_minkowski_params["length"]),
                    "axis": str(exact_minkowski_params["axis"]),
                }
            elif primitive_type == "cylinder":
                shape_payload = {
                    "radius": float(exact_minkowski_params["radius"]),
                    "height": float(exact_minkowski_params["height"]),
                    "axis": str(exact_minkowski_params["axis"]),
                }
            elif primitive_type == "extruded_profile":
                shape_payload = {
                    "axis": str(exact_minkowski_params["axis"]),
                    "extrude_height": float(exact_minkowski_params["extrude_height"]),
                    "profile_point_count": len(exact_minkowski_params.get("profile_polygon") or []),
                    "rounding_radius": float(exact_minkowski_params.get("rounding_radius") or 0.0),
                    "profile_width": float(exact_minkowski_params.get("profile_width") or 0.0),
                    "profile_height": float(exact_minkowski_params.get("profile_height") or 0.0),
                }
            else:
                shape_payload = {"rounding": float(exact_minkowski_params.get("rounding") or 0.0)}
            mesh.metadata["lathe_kernel_minkowski"] = {
                "schema": "lathe.geometry.kernel_minkowski.v1",
                "method": str(exact_minkowski_params["method"]),
                "source_operand_id": source.operand_id,
                "structuring_operand_id": structuring.operand_id,
                "attempted_backend": f"{kernel.name}.build_primitive",
                "actual_backend": f"{kernel.name}.build_primitive",
                "actual_operation": str(exact_minkowski_params["actual_operation"]),
                "result_kind": str(exact_minkowski_params["result_kind"]),
                **shape_payload,
                "fallback": False,
                "passthrough": False,
                "result_face_count": len(mesh.faces),
                "result_vertex_count": len(mesh.vertices),
                "result_watertight": bool(mesh.is_watertight),
            }
            _record_result_probe(operation_record, kernel=kernel, result_handle=current)
            operand_records = _semantic_operation_records_from_manifest(manifest)
            (
                final_operation_record,
                face_operation_ids,
                face_operation_summary,
                face_operation_attribution,
            ) = _attach_semantic_whole_result_face_metadata(
                mesh,
                operand_records,
                "op.minkowski",
                source="kernel_program.minkowski.whole_result_semantic_operation",
                method="whole_result_semantic_operation_range",
                reason="minkowski_kernel_rebuilt_result_without_source_face_ranges",
                extra={
                    "minkowski_execution_method": str(exact_minkowski_params["method"]),
                    "exact_kernel_path": True,
                },
            )
            if final_operation_record:
                operation_record["semantic_operation_record"] = dict(final_operation_record)
            kernel_minkowski = dict(mesh.metadata.get("lathe_kernel_minkowski") or {})
            kernel_feature_detail = _kernel_feature_detail_metadata(
                kernel,
                mesh,
                current,
                [source, structuring],
                semantic_operation="op.minkowski",
                method_suffix="minkowski_kernel_program_v1",
                fallback=False,
                face_operation_attributed=bool(face_operation_ids),
                extra={
                    "minkowski_execution_method": str(exact_minkowski_params["method"]),
                    "exact_kernel_path": True,
                    "approximation": "none",
                    "pair_count": pair_count,
                },
            )
            if kernel_feature_detail:
                mesh.metadata["lathe_kernel_feature_detail"] = dict(kernel_feature_detail)
            details = {
                "kernel_program_version": KERNEL_PROGRAM_VERSION,
                "kernel_program_route": route,
                "kernel_program_operation_count": operation_count,
                "kernel_program_operand_count": 2,
                "kernel_program_semantic_operation_record_count": len(operand_records),
                "kernel_program_semantic_operation_counts": _operation_counts(operand_records),
                "kernel_program_semantic_operation_records": operand_records,
                "kernel_program_kernel": kernel.name,
                "kernel_program_backend": backend,
                "kernel_program_manifest": manifest,
                "kernel_program_capabilities_checked": _required_capability_list(
                    exact_required_capabilities,
                    "to_trimesh",
                ),
                "kernel_program_watertight": bool(mesh.is_watertight),
                "kernel_program_body_count": len(mesh.split(only_watertight=False)),
                "kernel_program_operands": [source.trace_record(), structuring.trace_record()],
                "kernel_program_operations": [operation_record],
                "kernel_program_face_operation_attribution": face_operation_attribution,
                "face_operation_ids": face_operation_ids,
                "face_operation_summary": face_operation_summary,
                "kernel_minkowski": kernel_minkowski,
                "kernel_program_minkowski": kernel_minkowski,
                "kernel_feature_detail": kernel_feature_detail,
                "kernel_program_feature_detail": kernel_feature_detail,
                "kernel_program_minkowski_source_operand_id": source.operand_id,
                "kernel_program_minkowski_structuring_operand_id": structuring.operand_id,
                "minkowski_execution_method": str(exact_minkowski_params["method"]),
                "minkowski_exact": True,
                "minkowski_approximation": "none",
                "minkowski_pair_count": pair_count,
                "minkowski_sample_stride": 0,
                "minkowski_sample_count": 0,
                "minkowski_kernel_import_succeeded": False,
                "minkowski_finalized_by_kernel": True,
                "minkowski_result_kind": str(exact_minkowski_params["result_kind"]),
                "minkowski_result_center": list(exact_minkowski_params["center"]),
            }
            if result_extents is not None:
                details["minkowski_result_extents"] = list(result_extents)
            if result_radius is not None:
                details["minkowski_result_radius"] = float(result_radius)
            if result_length is not None:
                details["minkowski_result_length"] = float(result_length)
            if result_height is not None:
                details["minkowski_result_height"] = float(result_height)
            if result_extrude_height is not None:
                details["minkowski_result_extrude_height"] = float(result_extrude_height)
            if isinstance(result_profile_polygon, list):
                details["minkowski_result_profile_point_count"] = len(result_profile_polygon)
            if result_axis is not None:
                details["minkowski_result_axis"] = str(result_axis)
            if primitive_type not in {"sphere", "capsule", "cylinder", "extruded_profile"}:
                details["minkowski_rounding"] = float(exact_minkowski_params.get("rounding") or 0.0)
            semantic_handoff = _attach_kernel_program_semantic_handoff(
                mesh,
                [source, structuring],
                [operation_record],
            )
            details["kernel_program_semantic_handoff"] = semantic_handoff
            return KernelProgramResult(
                mesh=mesh,
                handle=current,
                operation_count=operation_count,
                details=details,
            )
        except (AttributeError, TypeError, ValueError, RuntimeError, OSError) as exc:
            exact_box_failure = f"{type(exc).__name__}: {exc}"

    _require_capabilities(kernel, capabilities, {"hull", "to_trimesh"})
    offsets = [
        (
            float(vertex[0]) - structuring_center[0],
            float(vertex[1]) - structuring_center[1],
            float(vertex[2]) - structuring_center[2],
        )
        for vertex in structuring_mesh.vertices.tolist()
    ]
    source_vertices = [
        (float(vertex[0]), float(vertex[1]), float(vertex[2]))
        for vertex in source_mesh.vertices.tolist()
    ]

    stride = max(1, math.ceil(pair_count / sample_limit))
    points: list[tuple[float, float, float]] = []
    pair_index = 0
    for vertex in source_vertices:
        for offset in offsets:
            if pair_index % stride == 0:
                points.append(
                    (
                        vertex[0] + offset[0],
                        vertex[1] + offset[1],
                        vertex[2] + offset[2],
                    )
                )
            pair_index += 1

    hull_seed = trimesh.Trimesh(vertices=points, faces=[], process=False).convex_hull
    if not isinstance(hull_seed, trimesh.Trimesh) or len(hull_seed.faces) == 0:
        raise ValueError("kernel minkowski convex hull approximation produced an empty mesh")
    manifest = build_minkowski_program_manifest(
        source,
        structuring,
        route=route,
        backend=backend,
        operation_limit=operation_limit,
        sample_limit=sample_limit,
        pair_count=pair_count,
        sample_stride=stride,
        sample_count=len(points),
    )

    import_succeeded = False
    finalized_by_kernel = False
    kernel_failure: str | None = None
    current: Any = hull_seed
    mesh = hull_seed
    operation_record: dict[str, Any] = {
        "op": "minkowski",
        "source": source.operand_id,
        "structuring": structuring.operand_id,
        "attempted_kernel": kernel.name,
        "attempted_backend": f"{kernel.name}.hull",
        "actual_backend": "trimesh.convex_hull",
        "actual_operation": "convex_vertex_sum_hull",
        "exact_kernel_path": False,
        "actual_kernel": "trimesh.convex_hull",
        "approximation": "convex_vertex_sum_hull",
        "source_vertex_count": len(source_vertices),
        "structuring_vertex_count": len(offsets),
        "pair_count": pair_count,
        "sample_stride": stride,
        "sample_count": len(points),
        "seed_hull_face_count": len(hull_seed.faces),
        "seed_hull_watertight": bool(hull_seed.is_watertight),
    }
    if exact_minkowski_params is not None:
        operation_record["exact_minkowski_path_available"] = True
        operation_record["exact_minkowski_path_method"] = str(
            exact_minkowski_params.get("method") or ""
        )
        if not all(capabilities.get(str(name)) is True for name in exact_required_capabilities):
            operation_record["exact_minkowski_path_skipped"] = (
                "kernel_did_not_advertise_required_capability"
            )
            operation_record["exact_minkowski_required_capabilities"] = [
                str(name)
                for name in exact_required_capabilities
            ]
    if exact_box_failure:
        operation_record["exact_minkowski_path_failed"] = exact_box_failure
        operation_record["exact_kernel_path_fallback"] = True
        operation_record["fallback"] = True
    try:
        imported = kernel.from_trimesh(hull_seed)
        import_succeeded = True
        current = kernel.hull([imported])
        mesh = _non_empty_mesh(kernel, current)
        finalized_by_kernel = True
        operation_record["actual_kernel"] = kernel.name
        _record_result_probe(operation_record, kernel=kernel, result_handle=current)
    except (AttributeError, TypeError, ValueError, RuntimeError, OSError) as exc:
        kernel_failure = f"{type(exc).__name__}: {exc}"
        current = hull_seed
        mesh = hull_seed
        operation_record["kernel_finalize_failed"] = kernel_failure
        operation_record["result_face_count"] = len(mesh.faces)
        operation_record["result_watertight"] = bool(mesh.is_watertight)
        operation_record["result_body_count"] = len(mesh.split(only_watertight=False))

    operand_records = _semantic_operation_records_from_manifest(manifest)
    kernel_minkowski = {
        "schema": "lathe.geometry.kernel_minkowski.v1",
        "method": "convex_vertex_sum_hull",
        "source_operand_id": source.operand_id,
        "structuring_operand_id": structuring.operand_id,
        "attempted_backend": f"{kernel.name}.hull",
        "actual_backend": str(operation_record.get("actual_backend") or "trimesh.convex_hull"),
        "actual_operation": "convex_vertex_sum_hull",
        "result_kind": "convex_hull_approximation",
        "exact_kernel_path": False,
        "approximation": "convex_vertex_sum_hull",
        "fallback": bool(operation_record.get("fallback", False)),
        "passthrough": False,
        "source_vertex_count": len(source_vertices),
        "structuring_vertex_count": len(offsets),
        "pair_count": pair_count,
        "sample_stride": stride,
        "sample_count": len(points),
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_watertight": bool(mesh.is_watertight),
    }
    if kernel_failure:
        kernel_minkowski["kernel_finalize_failed"] = kernel_failure
    if exact_box_failure:
        kernel_minkowski["exact_kernel_path_failed"] = exact_box_failure
    mesh.metadata["lathe_kernel_minkowski"] = dict(kernel_minkowski)
    (
        final_operation_record,
        face_operation_ids,
        face_operation_summary,
        face_operation_attribution,
    ) = _attach_semantic_whole_result_face_metadata(
        mesh,
        operand_records,
        "op.minkowski",
        source="kernel_program.minkowski.whole_result_semantic_operation",
        method="whole_result_semantic_operation_range",
        reason="minkowski_kernel_did_not_preserve_source_face_ranges",
        extra={
            "minkowski_execution_method": "convex_vertex_sum_hull",
            "exact_kernel_path": False,
            "approximation": "convex_vertex_sum_hull",
        },
    )
    if final_operation_record:
        operation_record["semantic_operation_record"] = dict(final_operation_record)
    kernel_feature_detail = _kernel_feature_detail_metadata(
        kernel,
        mesh,
        current,
        [source, structuring],
        semantic_operation="op.minkowski",
        method_suffix="minkowski_kernel_program_v1",
        fallback=bool(operation_record.get("fallback", False)),
        face_operation_attributed=bool(face_operation_ids),
        extra={
            "minkowski_execution_method": "convex_vertex_sum_hull",
            "exact_kernel_path": False,
            "approximation": "convex_vertex_sum_hull",
            "pair_count": pair_count,
        },
    )
    if kernel_feature_detail:
        mesh.metadata["lathe_kernel_feature_detail"] = dict(kernel_feature_detail)
    details = {
        "kernel_program_version": KERNEL_PROGRAM_VERSION,
        "kernel_program_route": route,
        "kernel_program_operation_count": operation_count,
        "kernel_program_operand_count": 2,
        "kernel_program_semantic_operation_record_count": len(operand_records),
        "kernel_program_semantic_operation_counts": _operation_counts(operand_records),
        "kernel_program_semantic_operation_records": operand_records,
        "kernel_program_kernel": kernel.name,
        "kernel_program_backend": backend,
        "kernel_program_manifest": manifest,
        "kernel_program_capabilities_checked": ["hull", "to_trimesh"],
        "kernel_program_watertight": bool(mesh.is_watertight),
        "kernel_program_body_count": len(mesh.split(only_watertight=False)),
        "kernel_program_operands": [source.trace_record(), structuring.trace_record()],
        "kernel_program_operations": [operation_record],
        "kernel_program_face_operation_attribution": face_operation_attribution,
        "face_operation_ids": face_operation_ids,
        "face_operation_summary": face_operation_summary,
        "kernel_minkowski": kernel_minkowski,
        "kernel_program_minkowski": kernel_minkowski,
        "kernel_feature_detail": kernel_feature_detail,
        "kernel_program_feature_detail": kernel_feature_detail,
        "kernel_program_minkowski_source_operand_id": source.operand_id,
        "kernel_program_minkowski_structuring_operand_id": structuring.operand_id,
        "minkowski_execution_method": "convex_vertex_sum_hull",
        "minkowski_exact": False,
        "minkowski_approximation": "convex_vertex_sum_hull",
        "minkowski_pair_count": pair_count,
        "minkowski_sample_stride": stride,
        "minkowski_sample_count": len(points),
        "minkowski_kernel_import_succeeded": import_succeeded,
        "minkowski_finalized_by_kernel": finalized_by_kernel,
    }
    if exact_box_failure:
        details["minkowski_exact_path_failure"] = exact_box_failure
    if kernel_failure:
        details["minkowski_kernel_finalize_failure"] = kernel_failure
    semantic_handoff = _attach_kernel_program_semantic_handoff(
        mesh,
        [source, structuring],
        [operation_record],
    )
    details["kernel_program_semantic_handoff"] = semantic_handoff
    return KernelProgramResult(
        mesh=mesh,
        handle=current,
        operation_count=operation_count,
        details=details,
    )


__all__ = [
    "build_minkowski_program_manifest",
    "execute_minkowski_program",
]
