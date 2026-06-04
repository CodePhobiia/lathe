"""Hull program — convex hull over a list of operands.

Per the §5.3 decomposition, this module hosts the ``hull`` family:
``op.hull``. The executor takes exact-rebuild paths for pair-wise
hulls of recognized primitives (box, sphere, cylinder, capsule, plus
mixed coaxial round profiles) when the kernel advertises the
required capability. Otherwise it falls through to
``kernel.hull([...])`` and lets the kernel produce its own convex
hull result, recording the backend choice via the standard trace
surface.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import trimesh

from ..kernel import GeometryKernel
from ._capabilities import (
    _kernel_capabilities,
    _require_capabilities,
    _validate_hull_operands,
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
    hull_operation_count,
)
from ._face_operation import _attach_semantic_whole_result_face_metadata
from ._feature_detail import _kernel_feature_detail_metadata
from ._primitive_metadata import (
    _axis_aligned_box_metadata,
    _axis_index,
    _axis_name_from_index,
    _capsule_metadata,
    _cylinder_metadata,
    _positive_triplet,
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


def _axis_aligned_center_delta(
    left: tuple[float, float, float],
    right: tuple[float, float, float],
) -> tuple[str, float] | None:
    """Return ``(axis, distance)`` when ``right`` differs from ``left`` along exactly one axis."""
    delta = tuple(float(right[index]) - float(left[index]) for index in range(3))
    active = [index for index, value in enumerate(delta) if abs(value) > 1e-9]
    if len(active) != 1:
        return None
    axis_index = active[0]
    return _axis_name_from_index(axis_index), abs(float(delta[axis_index]))


def _sphere_axis_profile_samples(
    center_axis: float,
    radius: float,
    *,
    segments: int = 24,
) -> list[tuple[float, float]]:
    """Sample a sphere's upper revolved profile into ``(axial, radial)`` points."""
    steps = max(8, min(96, int(segments)))
    samples: list[tuple[float, float]] = []
    for index in range(steps + 1):
        theta = math.pi - math.pi * (index / float(steps))
        samples.append(
            (
                float(center_axis) + math.cos(theta) * float(radius),
                max(0.0, math.sin(theta) * float(radius)),
            )
        )
    return samples


def _capsule_axis_profile_samples(
    interval_min: float,
    interval_max: float,
    radius: float,
    *,
    segments: int = 24,
) -> list[tuple[float, float]]:
    """Sample a capsule's upper revolved profile from an axis interval and radius."""
    if interval_max < interval_min:
        return _sphere_axis_profile_samples((interval_min + interval_max) * 0.5, radius, segments=segments)
    steps = max(8, min(96, int(segments)))
    samples: list[tuple[float, float]] = []
    for index in range(steps + 1):
        theta = math.pi - (math.pi * 0.5) * (index / float(steps))
        samples.append(
            (
                float(interval_min) + math.cos(theta) * float(radius),
                max(0.0, math.sin(theta) * float(radius)),
            )
        )
    samples.append((float(interval_max), float(radius)))
    for index in range(steps + 1):
        theta = (math.pi * 0.5) - (math.pi * 0.5) * (index / float(steps))
        samples.append(
            (
                float(interval_max) + math.cos(theta) * float(radius),
                max(0.0, math.sin(theta) * float(radius)),
            )
        )
    return samples


def _round_profile_source_for_axis(
    mesh: trimesh.Trimesh,
    *,
    axis: str | None = None,
) -> dict[str, Any] | None:
    """Recognize a round primitive (sphere/cylinder/capsule) from mesh metadata."""
    sphere = _sphere_metadata(mesh)
    if sphere is not None:
        return {
            "kind": "sphere",
            "center": tuple(float(value) for value in sphere["center"]),
            "axis": axis,
            "radius": float(sphere["radius"]),
            "metadata": sphere,
        }
    cylinder = _cylinder_metadata(mesh)
    if cylinder is not None:
        return {
            "kind": "cylinder",
            "center": tuple(float(value) for value in cylinder["center"]),
            "axis": str(cylinder["axis"]),
            "radius": float(cylinder["radius"]),
            "height": float(cylinder["height"]),
            "metadata": cylinder,
        }
    capsule = _capsule_metadata(mesh)
    if capsule is not None:
        return {
            "kind": "capsule",
            "center": tuple(float(value) for value in capsule["center"]),
            "axis": str(capsule["axis"]),
            "radius": float(capsule["radius"]),
            "length": float(capsule["length"]),
            "metadata": capsule,
        }
    return None


def _round_profile_samples_for_source(
    source: dict[str, Any],
    *,
    axis: str,
) -> list[tuple[float, float]] | None:
    """Sample a round primitive's upper revolved profile along ``axis``."""
    axis_index = _axis_index(axis)
    center = tuple(float(value) for value in source["center"])
    radius = float(source["radius"])
    kind = str(source["kind"])
    if kind == "sphere":
        return _sphere_axis_profile_samples(center[axis_index], radius)
    if kind == "cylinder":
        half_height = float(source["height"]) * 0.5
        return [
            (center[axis_index] - half_height, radius),
            (center[axis_index] + half_height, radius),
        ]
    if kind == "capsule":
        shaft = float(source["length"]) - 2.0 * radius
        if shaft < -1e-9:
            return None
        interval_min = center[axis_index] - max(0.0, shaft) * 0.5
        interval_max = center[axis_index] + max(0.0, shaft) * 0.5
        return _capsule_axis_profile_samples(interval_min, interval_max, radius)
    return None


def _upper_hull_axial_radius_points(
    points: list[tuple[float, float]],
) -> tuple[tuple[float, float], ...]:
    """Andrew's monotone-chain upper hull over ``(axial, radial)`` samples."""
    merged: dict[float, float] = {}
    for axial, radius in points:
        axial_value = float(axial)
        radius_value = float(radius)
        if not math.isfinite(axial_value) or not math.isfinite(radius_value) or radius_value <= 0.0:
            continue
        key = round(axial_value, 9)
        merged[key] = max(radius_value, merged.get(key, 0.0))
    ordered = sorted((float(axial), float(radius)) for axial, radius in merged.items())
    if len(ordered) <= 2:
        return tuple(ordered)

    def cross(
        origin: tuple[float, float],
        left: tuple[float, float],
        right: tuple[float, float],
    ) -> float:
        return (
            (left[0] - origin[0]) * (right[1] - origin[1])
            - (left[1] - origin[1]) * (right[0] - origin[0])
        )

    upper: list[tuple[float, float]] = []
    for point in ordered:
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) >= -1e-9:
            upper.pop()
        upper.append(point)
    return tuple(upper)


def _box_contains_box(
    outer: dict[str, Any],
    inner: dict[str, Any],
    *,
    tolerance: float = 1e-9,
) -> bool:
    """Return True iff ``outer``'s bounding box contains ``inner``'s with ``tolerance``."""
    outer_min = tuple(float(value) for value in outer["bounds_min"])
    outer_max = tuple(float(value) for value in outer["bounds_max"])
    inner_min = tuple(float(value) for value in inner["bounds_min"])
    inner_max = tuple(float(value) for value in inner["bounds_max"])
    return all(
        outer_min[index] <= inner_min[index] + tolerance
        and outer_max[index] >= inner_max[index] - tolerance
        for index in range(3)
    )


def _exact_axis_aligned_box_pair_hull_params(
    operands: list[KernelOperand],
) -> dict[str, Any] | None:
    """Detect a box-box pair hull that admits an exact axis-aligned rebuild."""
    if len(operands) != 2:
        return None
    left_mesh = operands[0].source_mesh or operands[0].handle
    right_mesh = operands[1].source_mesh or operands[1].handle
    if not isinstance(left_mesh, trimesh.Trimesh) or not isinstance(right_mesh, trimesh.Trimesh):
        return None
    left = _axis_aligned_box_metadata(left_mesh)
    right = _axis_aligned_box_metadata(right_mesh)
    if left is None or right is None:
        return None
    left_min = tuple(float(value) for value in left["bounds_min"])
    left_max = tuple(float(value) for value in left["bounds_max"])
    right_min = tuple(float(value) for value in right["bounds_min"])
    right_max = tuple(float(value) for value in right["bounds_max"])
    method = ""
    actual_operation = ""
    if _box_contains_box(left, right):
        result_min = left_min
        result_max = left_max
        method = "exact_nested_axis_aligned_box_hull_v1"
        actual_operation = "nested_axis_aligned_box_hull"
    elif _box_contains_box(right, left):
        result_min = right_min
        result_max = right_max
        method = "exact_nested_axis_aligned_box_hull_v1"
        actual_operation = "nested_axis_aligned_box_hull"
    else:
        left_center = tuple(float(value) for value in left["center"])
        right_center = tuple(float(value) for value in right["center"])
        center_delta = _axis_aligned_center_delta(left_center, right_center)
        if center_delta is None:
            return None
        axis_index = _axis_index(center_delta[0])
        for index in range(3):
            if index == axis_index:
                continue
            if abs(left_min[index] - right_min[index]) > 1e-9:
                return None
            if abs(left_max[index] - right_max[index]) > 1e-9:
                return None
        result_min = tuple(min(left_min[index], right_min[index]) for index in range(3))
        result_max = tuple(max(left_max[index], right_max[index]) for index in range(3))
        method = "exact_axis_aligned_box_strip_hull_v1"
        actual_operation = "axis_aligned_box_strip_hull"
    extents = tuple(result_max[index] - result_min[index] for index in range(3))
    if not _positive_triplet(extents):
        return None
    center = tuple((result_min[index] + result_max[index]) * 0.5 for index in range(3))
    return {
        "primitive_type": "box",
        "required_capabilities": ["box"],
        "method": method,
        "actual_operation": actual_operation,
        "result_kind": "box",
        "center": center,
        "extents": extents,
        "bounds_min": result_min,
        "bounds_max": result_max,
        "source_boxes": [left, right],
    }


def _exact_sphere_pair_hull_params(
    operands: list[KernelOperand],
) -> dict[str, Any] | None:
    """Detect a sphere-sphere pair hull that admits an exact rebuild.

    Returns a sphere (when one sphere contains the other) or a capsule
    (axis-aligned equal-radius pair) or a sampled revolved_profile
    (axis-aligned unequal-radius pair).
    """
    if len(operands) != 2:
        return None
    left_mesh = operands[0].source_mesh or operands[0].handle
    right_mesh = operands[1].source_mesh or operands[1].handle
    if not isinstance(left_mesh, trimesh.Trimesh) or not isinstance(right_mesh, trimesh.Trimesh):
        return None
    left_sphere = _sphere_metadata(left_mesh)
    right_sphere = _sphere_metadata(right_mesh)
    if left_sphere is None or right_sphere is None:
        return None
    radius = float(left_sphere["radius"])
    right_radius = float(right_sphere["radius"])
    left_center = tuple(float(value) for value in left_sphere["center"])
    right_center = tuple(float(value) for value in right_sphere["center"])
    distance = math.dist(left_center, right_center)
    if distance + min(radius, right_radius) <= max(radius, right_radius) + 1e-9:
        source = left_sphere if radius >= right_radius else right_sphere
        return {
            "primitive_type": "sphere",
            "required_capabilities": ["sphere"],
            "method": "exact_contained_sphere_hull_v1",
            "actual_operation": "contained_sphere_hull",
            "result_kind": "sphere",
            "center": tuple(float(value) for value in source["center"]),
            "radius": max(radius, right_radius),
            "source_spheres": [left_sphere, right_sphere],
        }
    if distance <= 1e-9:
        return {
            "primitive_type": "sphere",
            "required_capabilities": ["sphere"],
            "method": "exact_coincident_sphere_hull_v1",
            "actual_operation": "coincident_sphere_hull",
            "result_kind": "sphere",
            "center": left_center,
            "radius": radius,
            "source_spheres": [left_sphere, right_sphere],
        }
    axis = _axis_aligned_center_delta(left_center, right_center)
    if axis is None:
        return None
    axis_name, axis_distance = axis
    if abs(radius - right_radius) > max(1e-7, max(radius, right_radius) * 1e-6):
        axis_index = _axis_index(axis_name)
        samples = _upper_hull_axial_radius_points(
            [
                *_sphere_axis_profile_samples(left_center[axis_index], radius),
                *_sphere_axis_profile_samples(right_center[axis_index], right_radius),
            ]
        )
        if len(samples) < 3:
            return None
        result_min = min(float(axial) for axial, _radius in samples)
        result_max = max(float(axial) for axial, _radius in samples)
        center = list(left_center)
        center[axis_index] = (result_min + result_max) * 0.5
        center_axis = float(center[axis_index])
        profile_points = tuple(
            (float(axial) - center_axis, float(profile_radius))
            for axial, profile_radius in samples
        )
        return {
            "primitive_type": "revolved_profile",
            "required_capabilities": ["revolved_profile"],
            "method": "sampled_axis_aligned_unequal_sphere_hull_profile_v1",
            "actual_operation": "axis_aligned_unequal_sphere_hull_profile",
            "result_kind": "revolved_profile",
            "center": tuple(center),
            "axis": axis_name,
            "profile_points": profile_points,
            "profile_point_count": len(profile_points),
            "profile_approximation": "sampled_upper_spherocone_profile",
            "profile_sample_count": len(samples),
            "exact": False,
            "source_spheres": [left_sphere, right_sphere],
        }
    center = tuple((left_center[index] + right_center[index]) * 0.5 for index in range(3))
    return {
        "primitive_type": "capsule",
        "required_capabilities": ["capsule"],
        "method": "exact_axis_aligned_equal_sphere_capsule_hull_v1",
        "actual_operation": "axis_aligned_equal_sphere_hull",
        "result_kind": "capsule",
        "center": center,
        "radius": radius,
        "length": axis_distance + 2.0 * radius,
        "axis": axis_name,
        "source_spheres": [left_sphere, right_sphere],
    }


def _exact_cylinder_pair_hull_params(
    operands: list[KernelOperand],
) -> dict[str, Any] | None:
    """Detect a cylinder-cylinder coaxial pair hull that admits an exact rebuild."""
    if len(operands) != 2:
        return None
    left_mesh = operands[0].source_mesh or operands[0].handle
    right_mesh = operands[1].source_mesh or operands[1].handle
    if not isinstance(left_mesh, trimesh.Trimesh) or not isinstance(right_mesh, trimesh.Trimesh):
        return None
    left = _cylinder_metadata(left_mesh)
    right = _cylinder_metadata(right_mesh)
    if left is None or right is None:
        return None
    axis = str(left["axis"])
    if axis != str(right["axis"]):
        return None
    radius = float(left["radius"])
    right_radius = float(right["radius"])
    left_center = tuple(float(value) for value in left["center"])
    right_center = tuple(float(value) for value in right["center"])
    center_delta = _axis_aligned_center_delta(left_center, right_center)
    if center_delta is not None and center_delta[0] != axis:
        return None
    if center_delta is None and any(abs(left_center[index] - right_center[index]) > 1e-9 for index in range(3)):
        return None
    axis_index = _axis_index(axis)
    left_min = left_center[axis_index] - float(left["height"]) * 0.5
    left_max = left_center[axis_index] + float(left["height"]) * 0.5
    right_min = right_center[axis_index] - float(right["height"]) * 0.5
    right_max = right_center[axis_index] + float(right["height"]) * 0.5
    result_min = min(left_min, right_min)
    result_max = max(left_max, right_max)
    center = list(left_center)
    center[axis_index] = (result_min + result_max) * 0.5
    height = result_max - result_min
    if height <= 0.0:
        return None
    if abs(radius - right_radius) > max(1e-7, max(radius, right_radius) * 1e-6):
        upper_profile = _upper_hull_axial_radius_points(
            [
                (left_min, radius),
                (left_max, radius),
                (right_min, right_radius),
                (right_max, right_radius),
            ]
        )
        if len(upper_profile) < 2:
            return None
        center_axis = float(center[axis_index])
        profile_points = tuple(
            (float(axial) - center_axis, float(profile_radius))
            for axial, profile_radius in upper_profile
        )
        return {
            "primitive_type": "revolved_profile",
            "required_capabilities": ["revolved_profile"],
            "method": "exact_coaxial_cylinder_frustum_hull_v1",
            "actual_operation": "coaxial_cylinder_frustum_hull",
            "result_kind": "revolved_profile",
            "center": tuple(center),
            "height": height,
            "axis": axis,
            "profile_points": profile_points,
            "profile_point_count": len(profile_points),
            "source_cylinders": [left, right],
        }
    return {
        "primitive_type": "cylinder",
        "required_capabilities": ["cylinder"],
        "method": "exact_coaxial_equal_radius_cylinder_hull_v1",
        "actual_operation": "coaxial_equal_radius_cylinder_hull",
        "result_kind": "cylinder",
        "center": tuple(center),
        "radius": radius,
        "height": height,
        "axis": axis,
        "source_cylinders": [left, right],
    }


def _capsule_axis_interval(capsule: dict[str, Any]) -> tuple[float, float] | None:
    """Return the cylindrical-shaft axis interval of a capsule, or None when degenerate."""
    radius = float(capsule["radius"])
    length = float(capsule["length"])
    shaft = length - 2.0 * radius
    if shaft < -1e-9:
        return None
    center = tuple(float(value) for value in capsule["center"])
    axis_index = _axis_index(str(capsule["axis"]))
    return (
        center[axis_index] - max(0.0, shaft) * 0.5,
        center[axis_index] + max(0.0, shaft) * 0.5,
    )


def _exact_capsule_pair_hull_params(
    operands: list[KernelOperand],
) -> dict[str, Any] | None:
    """Detect a capsule-capsule coaxial pair hull that admits an exact rebuild."""
    if len(operands) != 2:
        return None
    left_mesh = operands[0].source_mesh or operands[0].handle
    right_mesh = operands[1].source_mesh or operands[1].handle
    if not isinstance(left_mesh, trimesh.Trimesh) or not isinstance(right_mesh, trimesh.Trimesh):
        return None
    left = _capsule_metadata(left_mesh)
    right = _capsule_metadata(right_mesh)
    if left is None or right is None:
        return None
    axis = str(left["axis"])
    if axis != str(right["axis"]):
        return None
    radius = float(left["radius"])
    right_radius = float(right["radius"])
    left_center = tuple(float(value) for value in left["center"])
    right_center = tuple(float(value) for value in right["center"])
    center_delta = _axis_aligned_center_delta(left_center, right_center)
    if center_delta is not None and center_delta[0] != axis:
        return None
    if center_delta is None and any(abs(left_center[index] - right_center[index]) > 1e-9 for index in range(3)):
        return None
    left_interval = _capsule_axis_interval(left)
    right_interval = _capsule_axis_interval(right)
    if left_interval is None or right_interval is None:
        return None
    result_min = min(left_interval[0], right_interval[0])
    result_max = max(left_interval[1], right_interval[1])
    axis_index = _axis_index(axis)
    center = list(left_center)
    if abs(radius - right_radius) > max(1e-7, max(radius, right_radius) * 1e-6):
        samples = _upper_hull_axial_radius_points(
            [
                *_capsule_axis_profile_samples(left_interval[0], left_interval[1], radius),
                *_capsule_axis_profile_samples(right_interval[0], right_interval[1], right_radius),
            ]
        )
        if len(samples) < 3:
            return None
        sample_min = min(float(axial) for axial, _radius in samples)
        sample_max = max(float(axial) for axial, _radius in samples)
        center[axis_index] = (sample_min + sample_max) * 0.5
        center_axis = float(center[axis_index])
        profile_points = tuple(
            (float(axial) - center_axis, float(profile_radius))
            for axial, profile_radius in samples
        )
        return {
            "primitive_type": "revolved_profile",
            "required_capabilities": ["revolved_profile"],
            "method": "sampled_coaxial_unequal_capsule_hull_profile_v1",
            "actual_operation": "coaxial_unequal_capsule_hull_profile",
            "result_kind": "revolved_profile",
            "center": tuple(center),
            "height": sample_max - sample_min,
            "axis": axis,
            "profile_points": profile_points,
            "profile_point_count": len(profile_points),
            "profile_approximation": "sampled_upper_capsule_hull_profile",
            "profile_sample_count": len(samples),
            "exact": False,
            "source_capsules": [left, right],
        }
    center[axis_index] = (result_min + result_max) * 0.5
    length = (result_max - result_min) + 2.0 * radius
    if length <= 2.0 * radius:
        return {
            "primitive_type": "sphere",
            "required_capabilities": ["sphere"],
            "method": "exact_coincident_capsule_sphere_hull_v1",
            "actual_operation": "coincident_capsule_hull",
            "result_kind": "sphere",
            "center": tuple(center),
            "radius": radius,
            "source_capsules": [left, right],
        }
    return {
        "primitive_type": "capsule",
        "required_capabilities": ["capsule"],
        "method": "exact_coaxial_equal_radius_capsule_hull_v1",
        "actual_operation": "coaxial_equal_radius_capsule_hull",
        "result_kind": "capsule",
        "center": tuple(center),
        "radius": radius,
        "length": length,
        "axis": axis,
        "source_capsules": [left, right],
    }


def _sampled_mixed_coaxial_profile_hull_params(
    operands: list[KernelOperand],
) -> dict[str, Any] | None:
    """Detect a coaxial mixed-primitive hull (sphere+cylinder, etc.) for a sampled rebuild."""
    if len(operands) != 2:
        return None
    left_mesh = operands[0].source_mesh or operands[0].handle
    right_mesh = operands[1].source_mesh or operands[1].handle
    if not isinstance(left_mesh, trimesh.Trimesh) or not isinstance(right_mesh, trimesh.Trimesh):
        return None
    left = _round_profile_source_for_axis(left_mesh)
    right = _round_profile_source_for_axis(right_mesh)
    if left is None or right is None:
        return None
    if str(left["kind"]) == str(right["kind"]):
        return None
    axes = {str(source["axis"]) for source in (left, right) if source.get("axis")}
    if len(axes) != 1:
        return None
    axis = axes.pop()
    left["axis"] = axis
    right["axis"] = axis
    left_center = tuple(float(value) for value in left["center"])
    right_center = tuple(float(value) for value in right["center"])
    center_delta = _axis_aligned_center_delta(left_center, right_center)
    if center_delta is not None and center_delta[0] != axis:
        return None
    if center_delta is None and any(abs(left_center[index] - right_center[index]) > 1e-9 for index in range(3)):
        return None
    axis_index = _axis_index(axis)
    left_samples = _round_profile_samples_for_source(left, axis=axis)
    right_samples = _round_profile_samples_for_source(right, axis=axis)
    if left_samples is None or right_samples is None:
        return None
    samples = _upper_hull_axial_radius_points([*left_samples, *right_samples])
    if len(samples) < 2:
        return None
    sample_min = min(float(axial) for axial, _radius in samples)
    sample_max = max(float(axial) for axial, _radius in samples)
    center = list(left_center)
    center[axis_index] = (sample_min + sample_max) * 0.5
    center_axis = float(center[axis_index])
    profile_points = tuple(
        (float(axial) - center_axis, float(profile_radius))
        for axial, profile_radius in samples
    )
    kind_pair = "_".join(sorted((str(left["kind"]), str(right["kind"]))))
    return {
        "primitive_type": "revolved_profile",
        "required_capabilities": ["revolved_profile"],
        "method": f"sampled_coaxial_{kind_pair}_hull_profile_v1",
        "actual_operation": f"coaxial_{kind_pair}_hull_profile",
        "result_kind": "revolved_profile",
        "center": tuple(center),
        "height": sample_max - sample_min,
        "axis": axis,
        "profile_points": profile_points,
        "profile_point_count": len(profile_points),
        "profile_approximation": "sampled_upper_coaxial_mixed_profile",
        "profile_sample_count": len(samples),
        "exact": False,
        "source_profile_hull_operands": [
            {"kind": left["kind"], **_dict_metadata(left.get("metadata"))},
            {"kind": right["kind"], **_dict_metadata(right.get("metadata"))},
        ],
    }


def build_hull_program_manifest(
    operands: list[KernelOperand],
    *,
    route: str = "convex_hull_program",
    backend: str | None = None,
    operation_limit: int | None = None,
) -> dict[str, Any]:
    """Return a deterministic, handle-free manifest for a hull program."""
    operation_records = _operand_operation_records(operands)
    if not any(str(record.get("operation") or "") == "op.hull" for record in operation_records):
        operation_records.append(
            {
                "operation_id": f"program:{_operation_id_fragment(route)}:op_hull",
                "operation": "op.hull",
                "repair_action": "",
                "operand_id": "",
                "operand_index": -1,
                "part": "",
                "primitive_type": "",
                "blend_mode": "",
                "source": "kernel_program.hull",
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
    operation_count = hull_operation_count(operands)
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
        "program_kind": "hull",
        "route": route,
        "backend": backend,
        "operation_count": operation_count,
        "kernel_call_count": operation_count,
        "operation_limit": operation_limit,
        "required_capabilities": ["hull", "to_trimesh"],
        "operand_count": len(operands),
        "operands": [_json_safe(operand.trace_record()) for operand in operands],
        "semantic_operation_record_count": len(operation_records),
        "semantic_operation_counts": _operation_counts(operation_records),
        "semantic_operation_records": _json_safe(operation_records),
        "diagnostics": diagnostics,
    }


def execute_hull_program(
    kernel: GeometryKernel,
    operands: list[KernelOperand],
    *,
    operation_limit: int | None = None,
    route: str = "convex_hull_program",
    backend: str | None = None,
) -> KernelProgramResult:
    """Execute a convex hull over already-imported kernel operands."""
    _validate_hull_operands(operands)
    operation_count = hull_operation_count(operands)
    if operation_limit is not None and operation_count > operation_limit:
        raise ValueError(
            f"kernel hull operation_count={operation_count} exceeds limit={operation_limit}"
        )
    capabilities = _kernel_capabilities(kernel)
    exact_hull_params = _exact_axis_aligned_box_pair_hull_params(operands)
    if exact_hull_params is None:
        exact_hull_params = _exact_sphere_pair_hull_params(operands)
    if exact_hull_params is None:
        exact_hull_params = _exact_cylinder_pair_hull_params(operands)
    if exact_hull_params is None:
        exact_hull_params = _exact_capsule_pair_hull_params(operands)
    if exact_hull_params is None:
        exact_hull_params = _sampled_mixed_coaxial_profile_hull_params(operands)
    if exact_hull_params is not None:
        required = _exact_rebuild_required_capabilities(exact_hull_params)
        if required and all(capabilities.get(name) is True for name in required):
            hull_exact = bool(exact_hull_params.get("exact", True))
            manifest = build_hull_program_manifest(
                operands,
                route=route,
                backend=backend,
                operation_limit=operation_limit,
            )
            manifest = {
                **manifest,
                "required_capabilities": required,
                "exact_kernel_path": hull_exact,
                **(
                    {"profile_approximation": str(exact_hull_params["profile_approximation"])}
                    if "profile_approximation" in exact_hull_params
                    else {}
                ),
                "exact_hull_method": str(exact_hull_params["method"]),
            }
            primitive_type = str(exact_hull_params["primitive_type"])
            build_kwargs: dict[str, Any] = {
                "center": exact_hull_params["center"],
                "part": "hull",
                "semantic_metadata": {
                    "kernel_program": {
                        "op": "hull",
                        "method": str(exact_hull_params["method"]),
                        "operand_ids": [operand.operand_id for operand in operands],
                    }
                },
            }
            if primitive_type == "box":
                build_kwargs["extents"] = exact_hull_params["extents"]
                build_kwargs["rounding"] = 0.0
            elif primitive_type == "sphere":
                build_kwargs["radius"] = exact_hull_params["radius"]
            elif primitive_type == "capsule":
                build_kwargs["radius"] = exact_hull_params["radius"]
                build_kwargs["length"] = exact_hull_params["length"]
                build_kwargs["axis"] = exact_hull_params["axis"]
            elif primitive_type == "cylinder":
                build_kwargs["radius"] = exact_hull_params["radius"]
                build_kwargs["height"] = exact_hull_params["height"]
                build_kwargs["axis"] = exact_hull_params["axis"]
            elif primitive_type == "revolved_profile":
                build_kwargs["profile_points"] = exact_hull_params["profile_points"]
                build_kwargs["axis"] = exact_hull_params["axis"]
            else:
                build_kwargs = {}
            if build_kwargs:
                current = kernel.build_primitive(primitive_type, **build_kwargs)
                mesh = _non_empty_mesh(kernel, current)
                operation_record: dict[str, Any] = {
                    "op": "hull",
                    "inputs": [operand.operand_id for operand in operands],
                    "attempted_kernel": kernel.name,
                    "actual_kernel": kernel.name,
                    "attempted_backend": f"{kernel.name}.build_primitive",
                    "actual_backend": f"{kernel.name}.build_primitive",
                    "actual_operation": str(exact_hull_params["actual_operation"]),
                    "kernel_hull_method": str(exact_hull_params["method"]),
                    "exact_kernel_path": hull_exact,
                    "fallback": False,
                    "passthrough": False,
                    "result_kind": str(exact_hull_params["result_kind"]),
                    "result_center": list(exact_hull_params["center"]),
                    "result_face_count": len(mesh.faces),
                    "result_vertex_count": len(mesh.vertices),
                    "result_watertight": bool(mesh.is_watertight),
                    "result_body_count": kernel.body_count(current),
                }
                if "radius" in exact_hull_params:
                    operation_record["result_radius"] = float(exact_hull_params["radius"])
                if "extents" in exact_hull_params:
                    operation_record["result_extents"] = [
                        float(value) for value in exact_hull_params["extents"]
                    ]
                if "bounds_min" in exact_hull_params:
                    operation_record["result_bounds_min"] = [
                        float(value) for value in exact_hull_params["bounds_min"]
                    ]
                if "bounds_max" in exact_hull_params:
                    operation_record["result_bounds_max"] = [
                        float(value) for value in exact_hull_params["bounds_max"]
                    ]
                if "length" in exact_hull_params:
                    operation_record["result_length"] = float(exact_hull_params["length"])
                if "height" in exact_hull_params:
                    operation_record["result_height"] = float(exact_hull_params["height"])
                if "axis" in exact_hull_params:
                    operation_record["result_axis"] = str(exact_hull_params["axis"])
                if "profile_point_count" in exact_hull_params:
                    operation_record["result_profile_point_count"] = int(
                        exact_hull_params["profile_point_count"]
                    )
                if "profile_points" in exact_hull_params:
                    operation_record["result_profile_points"] = _json_safe(
                        exact_hull_params["profile_points"]
                    )
                if "profile_approximation" in exact_hull_params:
                    operation_record["profile_approximation"] = str(
                        exact_hull_params["profile_approximation"]
                    )
                if "profile_sample_count" in exact_hull_params:
                    operation_record["profile_sample_count"] = int(
                        exact_hull_params["profile_sample_count"]
                    )
                if "source_spheres" in exact_hull_params:
                    operation_record["source_spheres"] = _json_safe(exact_hull_params["source_spheres"])
                if "source_cylinders" in exact_hull_params:
                    operation_record["source_cylinders"] = _json_safe(exact_hull_params["source_cylinders"])
                if "source_capsules" in exact_hull_params:
                    operation_record["source_capsules"] = _json_safe(exact_hull_params["source_capsules"])
                if "source_boxes" in exact_hull_params:
                    operation_record["source_boxes"] = _json_safe(exact_hull_params["source_boxes"])
                if "source_profile_hull_operands" in exact_hull_params:
                    operation_record["source_profile_hull_operands"] = _json_safe(
                        exact_hull_params["source_profile_hull_operands"]
                    )
                mesh.metadata["lathe_kernel_hull"] = {
                    "schema": "lathe.geometry.kernel_hull.v1",
                    "method": str(exact_hull_params["method"]),
                    "actual_operation": str(exact_hull_params["actual_operation"]),
                    "result_kind": str(exact_hull_params["result_kind"]),
                    "exact_kernel_path": hull_exact,
                    **(
                        {"radius": float(exact_hull_params["radius"])}
                        if "radius" in exact_hull_params
                        else {}
                    ),
                    **(
                        {"extents": [float(value) for value in exact_hull_params["extents"]]}
                        if "extents" in exact_hull_params
                        else {}
                    ),
                    **(
                        {"length": float(exact_hull_params["length"]), "axis": str(exact_hull_params["axis"])}
                        if "length" in exact_hull_params
                        else {}
                    ),
                    **(
                        {"height": float(exact_hull_params["height"]), "axis": str(exact_hull_params["axis"])}
                        if "height" in exact_hull_params
                        else {}
                    ),
                    **(
                        {
                            "profile_point_count": int(exact_hull_params["profile_point_count"]),
                            "profile_points": _json_safe(exact_hull_params["profile_points"]),
                            "axis": str(exact_hull_params["axis"]),
                            **(
                                {"profile_approximation": str(exact_hull_params["profile_approximation"])}
                                if "profile_approximation" in exact_hull_params
                                else {}
                            ),
                            **(
                                {"profile_sample_count": int(exact_hull_params["profile_sample_count"])}
                                if "profile_sample_count" in exact_hull_params
                                else {}
                            ),
                        }
                        if "profile_points" in exact_hull_params
                        else {}
                    ),
                    "fallback": False,
                    "passthrough": False,
                    "result_face_count": len(mesh.faces),
                    "result_vertex_count": len(mesh.vertices),
                    "result_watertight": bool(mesh.is_watertight),
                }
                _record_result_probe(operation_record, kernel=kernel, result_handle=current)
                operation_records = _semantic_operation_records_from_manifest(manifest)
                (
                    final_operation_record,
                    face_operation_ids,
                    face_operation_summary,
                    face_operation_attribution,
                ) = _attach_semantic_whole_result_face_metadata(
                    mesh,
                    operation_records,
                    "op.hull",
                    source="kernel_program.hull.whole_result_semantic_operation",
                    method="whole_result_semantic_operation_range",
                    reason="hull_kernel_rebuilt_result_without_source_face_ranges",
                    extra={
                        "hull_execution_method": str(exact_hull_params["method"]),
                        "exact_kernel_path": hull_exact,
                    },
                )
                if final_operation_record:
                    operation_record["semantic_operation_record"] = dict(final_operation_record)
                kernel_hull = dict(mesh.metadata.get("lathe_kernel_hull") or {})
                kernel_feature_detail = _kernel_feature_detail_metadata(
                    kernel,
                    mesh,
                    current,
                    operands,
                    semantic_operation="op.hull",
                    method_suffix="hull_kernel_program_v1",
                    fallback=False,
                    face_operation_attributed=bool(face_operation_ids),
                    extra={
                        "operand_count": len(operands),
                        "hull_execution_method": str(exact_hull_params["method"]),
                        "exact_kernel_path": hull_exact,
                        "result_kind": str(exact_hull_params["result_kind"]),
                    },
                )
                if kernel_feature_detail:
                    mesh.metadata["lathe_kernel_feature_detail"] = dict(kernel_feature_detail)
                semantic_handoff = _attach_kernel_program_semantic_handoff(
                    mesh,
                    operands,
                    [operation_record],
                )
                return KernelProgramResult(
                    mesh=mesh,
                    handle=current,
                    operation_count=operation_count,
                    details={
                        "kernel_program_version": KERNEL_PROGRAM_VERSION,
                        "kernel_program_route": route,
                        "kernel_program_operation_count": operation_count,
                        "kernel_program_operand_count": len(operands),
                        "kernel_program_semantic_operation_record_count": len(operation_records),
                        "kernel_program_semantic_operation_counts": _operation_counts(operation_records),
                        "kernel_program_semantic_operation_records": operation_records,
                        "kernel_program_kernel": kernel.name,
                        "kernel_program_backend": backend,
                        "kernel_program_manifest": manifest,
                        "kernel_program_capabilities_checked": required,
                        "kernel_program_watertight": bool(mesh.is_watertight),
                        "kernel_program_body_count": kernel.body_count(current),
                        "kernel_program_operands": [operand.trace_record() for operand in operands],
                        "kernel_program_operations": [operation_record],
                        "kernel_program_face_operation_attribution": face_operation_attribution,
                        "face_operation_ids": face_operation_ids,
                        "face_operation_summary": face_operation_summary,
                        "kernel_hull": kernel_hull,
                        "kernel_program_hull": kernel_hull,
                        "kernel_feature_detail": kernel_feature_detail,
                        "kernel_program_feature_detail": kernel_feature_detail,
                        "kernel_program_hull_operand_ids": [operand.operand_id for operand in operands],
                        "kernel_program_semantic_handoff": semantic_handoff,
                        "hull_execution_method": str(exact_hull_params["method"]),
                        "hull_exact": hull_exact,
                        "hull_result_kind": str(exact_hull_params["result_kind"]),
                        "hull_result_center": list(exact_hull_params["center"]),
                        **(
                            {
                                "hull_profile_approximation": str(
                                    exact_hull_params["profile_approximation"]
                                )
                            }
                            if "profile_approximation" in exact_hull_params
                            else {}
                        ),
                        **(
                            {"hull_result_radius": float(exact_hull_params["radius"])}
                            if "radius" in exact_hull_params
                            else {}
                        ),
                        **(
                            {
                                "hull_result_extents": [
                                    float(value) for value in exact_hull_params["extents"]
                                ],
                                "hull_result_bounds_min": [
                                    float(value) for value in exact_hull_params["bounds_min"]
                                ],
                                "hull_result_bounds_max": [
                                    float(value) for value in exact_hull_params["bounds_max"]
                                ],
                            }
                            if "extents" in exact_hull_params
                            else {}
                        ),
                        **(
                            {
                                "hull_result_length": float(exact_hull_params["length"]),
                                "hull_result_axis": str(exact_hull_params["axis"]),
                            }
                            if "length" in exact_hull_params
                            else {}
                        ),
                        **(
                            {
                                "hull_result_height": float(exact_hull_params["height"]),
                                "hull_result_axis": str(exact_hull_params["axis"]),
                            }
                            if "height" in exact_hull_params
                            else {}
                        ),
                        **(
                            {
                                "hull_result_profile_point_count": int(
                                    exact_hull_params["profile_point_count"]
                                ),
                                "hull_result_profile_points": _json_safe(
                                    exact_hull_params["profile_points"]
                                ),
                                "hull_result_axis": str(exact_hull_params["axis"]),
                                **(
                                    {"hull_profile_sample_count": int(exact_hull_params["profile_sample_count"])}
                                    if "profile_sample_count" in exact_hull_params
                                    else {}
                                ),
                            }
                            if "profile_points" in exact_hull_params
                            else {}
                        ),
                    },
                )
    _require_capabilities(kernel, capabilities, {"hull", "to_trimesh"})
    manifest = build_hull_program_manifest(
        operands,
        route=route,
        backend=backend,
        operation_limit=operation_limit,
    )

    operand_ids = [operand.operand_id for operand in operands]
    current = kernel.hull([operand.handle for operand in operands])
    mesh = _non_empty_mesh(kernel, current)
    bounds = np.asarray(mesh.bounds, dtype=np.float64)
    bounds_min = [float(value) for value in bounds[0]]
    bounds_max = [float(value) for value in bounds[1]]
    result_extents = [
        float(bounds_max[index] - bounds_min[index])
        for index in range(3)
    ]
    result_center = [
        float((bounds_min[index] + bounds_max[index]) * 0.5)
        for index in range(3)
    ]
    operation_record: dict[str, Any] = {
        "op": "hull",
        "inputs": operand_ids,
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_watertight": bool(mesh.is_watertight),
        "result_body_count": kernel.body_count(current),
        "result_kind": "convex_hull",
        "result_center": result_center,
        "result_bounds_min": bounds_min,
        "result_bounds_max": bounds_max,
        "result_extents": result_extents,
        "exact_kernel_path": True,
        "fallback": False,
        "passthrough": False,
    }
    kernel_hull = _dict_metadata(mesh.metadata.get("lathe_reference_hull"))
    if not kernel_hull:
        kernel_hull = _dict_metadata(mesh.metadata.get("lathe_manifold_hull"))
    if kernel_hull:
        operation_record["kernel_hull"] = dict(kernel_hull)
        operation_record["kernel_hull_method"] = str(kernel_hull.get("method") or "")
        operation_record["attempted_backend"] = str(
            kernel_hull.get("attempted_backend") or ""
        )
        operation_record["actual_backend"] = str(kernel_hull.get("actual_backend") or "")
        operation_record["actual_operation"] = str(
            kernel_hull.get("actual_operation") or ""
        )
    hull_method = str(
        operation_record.get("kernel_hull_method")
        or operation_record.get("actual_operation")
        or "kernel_convex_hull_v1"
    )
    operation_record["kernel_hull_method"] = hull_method
    operation_records = _semantic_operation_records_from_manifest(manifest)
    kernel_hull_payload = {
        "schema": "lathe.geometry.kernel_hull.v1",
        "method": hull_method,
        "source_operand_ids": operand_ids,
        "attempted_backend": str(operation_record.get("attempted_backend") or f"{kernel.name}.hull"),
        "actual_backend": str(operation_record.get("actual_backend") or f"{kernel.name}.hull"),
        "actual_operation": str(operation_record.get("actual_operation") or hull_method),
        "result_kind": "convex_hull",
        "result_center": result_center,
        "result_bounds_min": bounds_min,
        "result_bounds_max": bounds_max,
        "result_extents": result_extents,
        "exact_kernel_path": True,
        "fallback": False,
        "passthrough": False,
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_watertight": bool(mesh.is_watertight),
    }
    if kernel_hull:
        kernel_hull_payload["kernel_trace"] = dict(kernel_hull)
    mesh.metadata["lathe_kernel_hull"] = dict(kernel_hull_payload)
    (
        final_operation_record,
        face_operation_ids,
        face_operation_summary,
        face_operation_attribution,
    ) = _attach_semantic_whole_result_face_metadata(
        mesh,
        operation_records,
        "op.hull",
        source="kernel_program.hull.whole_result_semantic_operation",
        method="whole_result_semantic_operation_range",
        reason="hull_kernel_did_not_preserve_source_face_ranges",
        extra={
            "hull_execution_method": hull_method,
            "exact_kernel_path": True,
        },
    )
    if final_operation_record:
        operation_record["semantic_operation_record"] = dict(final_operation_record)
    kernel_feature_detail = _kernel_feature_detail_metadata(
        kernel,
        mesh,
        current,
        operands,
        semantic_operation="op.hull",
        method_suffix="hull_kernel_program_v1",
        fallback=False,
        face_operation_attributed=bool(face_operation_ids),
        extra={
            "operand_count": len(operands),
            "hull_execution_method": hull_method,
            "exact_kernel_path": True,
            "result_kind": "convex_hull",
        },
    )
    if kernel_feature_detail:
        mesh.metadata["lathe_kernel_feature_detail"] = dict(kernel_feature_detail)
    semantic_handoff = _attach_kernel_program_semantic_handoff(
        mesh,
        operands,
        [operation_record],
    )
    details = {
        "kernel_program_version": KERNEL_PROGRAM_VERSION,
        "kernel_program_route": route,
        "kernel_program_operation_count": operation_count,
        "kernel_program_operand_count": len(operands),
        "kernel_program_semantic_operation_record_count": len(operation_records),
        "kernel_program_semantic_operation_counts": _operation_counts(operation_records),
        "kernel_program_semantic_operation_records": operation_records,
        "kernel_program_kernel": kernel.name,
        "kernel_program_backend": backend,
        "kernel_program_manifest": manifest,
        "kernel_program_capabilities_checked": ["hull", "to_trimesh"],
        "kernel_program_watertight": kernel.is_watertight(current),
        "kernel_program_body_count": kernel.body_count(current),
        "kernel_program_operands": [operand.trace_record() for operand in operands],
        "kernel_program_operations": [operation_record],
        "kernel_program_face_operation_attribution": face_operation_attribution,
        "face_operation_ids": face_operation_ids,
        "face_operation_summary": face_operation_summary,
        "kernel_hull": kernel_hull_payload,
        "kernel_program_hull": kernel_hull_payload,
        "kernel_feature_detail": kernel_feature_detail,
        "kernel_program_feature_detail": kernel_feature_detail,
        "kernel_program_hull_operand_ids": operand_ids,
        "kernel_program_semantic_handoff": semantic_handoff,
        "hull_execution_method": hull_method,
        "hull_exact": True,
        "hull_result_kind": "convex_hull",
        "hull_result_center": result_center,
        "hull_result_bounds_min": bounds_min,
        "hull_result_bounds_max": bounds_max,
        "hull_result_extents": result_extents,
    }
    return KernelProgramResult(
        mesh=mesh,
        handle=current,
        operation_count=operation_count,
        details=details,
    )


__all__ = [
    "build_hull_program_manifest",
    "execute_hull_program",
]
