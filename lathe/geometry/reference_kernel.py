"""Reference geometry kernel backed by trimesh (GEO-3).

Always-available fallback for the ``lathe.geometry.reference_v1`` ID.
Wraps ``trimesh.creation`` for primitives and trimesh's boolean
pipeline (``trimesh.boolean.union/difference/intersection``) for CSG
ops. Results are not guaranteed watertight — trimesh booleans depend
on the configured engine and can emit non-manifold output on dense or
coplanar scenes. That known weakness is exactly what motivates
Manifold adoption (see ``docs/geometry_kernel_eval.md``); this kernel
exists so a Lathe install without ``manifold3d`` still has a working
geometry path.

The kernel exposes the Protocol surface the shape stage uses, including
the stable ShapeIR primitive vocabulary. Advanced primitives are built
through Lathe's exact mesh path and imported into the reference handle
type, with heightfields explicitly solidified for solid-kernel use.
Lower-level SDF fusion logic continues to live in
``lathe/geometry_kernel.py`` and is reached via that module's
``fuse_shape_ir`` helper; this kernel is the boolean/CSG surface, not
a replacement for the entire legacy module.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from copy import deepcopy
from typing import Any

import numpy as np
import trimesh
from trimesh.voxel.ops import matrix_to_marching_cubes

from .kernel import REFERENCE_KERNEL_ID, GeometryKernel

__all__ = ["ReferenceKernel", "reference_kernel"]

_EXACT_IMPORT_MODIFIER_KEYS = (
    "boolean_seam_groups",
    "bevel_seam_groups",
    "hard_edge_groups",
    "v2_polybevel_modifier",
    "v2_mark_hard_edge_modifier",
    "v2_weighted_normals_modifier",
    "v2_subdivision_modifier",
    "v2_remesh_modifier",
    "v2_tessellation_modifier",
)
_EXACT_IMPORT_PRIMITIVE_KINDS = frozenset(
    {
        "box",
        "cylinder",
        "sphere",
        "capsule",
        "revolved_profile",
        "extruded_profile",
        "rounded_slot",
        "socket",
        "countersunk_hole",
        "countersunk_hole_set",
        "panel",
        "panel_frame",
        "panel_line_cut",
        "inset_cut",
        "perforated_panel",
        "fastener_grid",
        "weld_seam",
        "dent_mask_set",
        "edge_chip_set",
        "surface_patch_set",
        "hinge",
        "handle",
        "corner_guard_set",
        "structural_beam",
        "rail",
        "ribbed_panel",
        "louver_panel",
        "vent_slats",
        "ladder_frame",
        "truss_frame",
        "support_bracket",
        "trim_band",
        "torus",
        "tube",
        "gear",
        "flange",
        "subdivision_box",
        "swept_profile",
        "helical_sweep",
        "spring",
        "threaded_cylinder",
        "curved_tube",
        "lofted_solid",
        "heightfield",
        "terrain_patch",
        "sdf_mesh",
        "sdf_metaball_cluster",
        "terrain_mesh",
        "kernel_primitive_mesh",
        "instance_mesh",
        "polybevel_mesh",
        "profile_mesh",
        "construction_feature_mesh",
        "edge_control_mesh",
        "hull_mesh",
        "minkowski_mesh",
        "subdivision_mesh",
        "remesh_mesh",
        "deform_mesh",
        "boolean_mesh",
        "component_assembly_mesh",
        "component_assembly",
    }
)
_BATCH_SOURCE_ATTR = "_lathe_reference_batch_union_sources"
_PRIMITIVE_METADATA_KEY = "lathe_reference_primitive"
_EXACT_BOOLEAN_METADATA_KEY = "lathe_reference_exact_boolean"
_SHAPE_PRIMITIVE_METADATA_KEY = "lathe_shape_primitive"
_PROFILE_CUT_STATE_METADATA_KEY = "lathe_reference_profile_cut_state"
_BOSS_STATE_METADATA_KEY = "lathe_reference_boss_state"


class _BoxExtentsRequiredError(ValueError):
    def __init__(self) -> None:
        super().__init__("box requires `extents` (3-tuple)")


class _CylinderDimensionsRequiredError(ValueError):
    def __init__(self) -> None:
        super().__init__("cylinder requires `radius` and `height`")


class _SphereRadiusRequiredError(ValueError):
    def __init__(self) -> None:
        super().__init__("sphere requires `radius`")


class _CapsuleDimensionsRequiredError(ValueError):
    def __init__(self) -> None:
        super().__init__("capsule requires `radius` and total `length > 2 * radius`")


class _UnsupportedPrimitiveKindError(ValueError):
    def __init__(self, kind: str) -> None:
        super().__init__(f"Unsupported primitive kind: {kind!r}")


class _HullEmptyError(ValueError):
    def __init__(self) -> None:
        super().__init__("hull requires at least one mesh")


class _BatchUnionEmptyError(ValueError):
    def __init__(self) -> None:
        super().__init__("batch_union requires at least one mesh")


def _shape_primitive_from_params(kind: str, params: dict[str, Any]):
    from dataclasses import fields

    from ..shape_ir import ShapePrimitive

    field_names = {field.name for field in fields(ShapePrimitive)}
    kwargs = {
        name: params[name]
        for name in field_names
        if name in params
    }
    kwargs["primitive_type"] = kind
    kwargs.setdefault("part", str(params.get("part") or kind))
    kwargs.setdefault(
        "center",
        tuple(float(value) for value in params.get("center", (0.0, 0.0, 0.0))),
    )
    if "v2_tessellation_modifier" in params and "v2_tessellation_modifier" not in kwargs:
        semantic_metadata = kwargs.get("semantic_metadata")
        if isinstance(semantic_metadata, dict):
            semantic_metadata = dict(semantic_metadata)
        else:
            semantic_metadata = {}
        semantic_metadata["v2_tessellation_modifier"] = params["v2_tessellation_modifier"]
        kwargs["semantic_metadata"] = semantic_metadata
    return ShapePrimitive(**kwargs)


def _requires_exact_import(kind: str, params: dict[str, Any]) -> bool:
    return kind in _EXACT_IMPORT_PRIMITIVE_KINDS and any(
        params.get(key) not in (None, {}, [], ())
        for key in _EXACT_IMPORT_MODIFIER_KEYS
    )


def _mesh_bounds(meshes: Iterable[trimesh.Trimesh]) -> tuple[np.ndarray, np.ndarray]:
    bounds = [np.asarray(mesh.bounds, dtype=np.float64) for mesh in meshes if len(mesh.faces) > 0]
    if not bounds:
        return np.zeros(3, dtype=np.float64), np.ones(3, dtype=np.float64)
    mins = np.min([item[0] for item in bounds], axis=0)
    maxs = np.max([item[1] for item in bounds], axis=0)
    return mins, maxs


def _bounds_overlap(a: trimesh.Trimesh, b: trimesh.Trimesh, *, pad: float = 1e-6) -> bool:
    if len(a.faces) == 0 or len(b.faces) == 0:
        return False
    a_bounds = np.asarray(a.bounds, dtype=np.float64)
    b_bounds = np.asarray(b.bounds, dtype=np.float64)
    return bool(
        np.all(a_bounds[1] + pad >= b_bounds[0])
        and np.all(b_bounds[1] + pad >= a_bounds[0])
    )


def _disjoint_additive_batch_union(meshes: list[trimesh.Trimesh]) -> trimesh.Trimesh | None:
    non_empty = [mesh for mesh in meshes if len(mesh.faces) > 0]
    if len(non_empty) <= 1:
        return None
    for left in range(len(non_empty)):
        for right in range(left + 1, len(non_empty)):
            if _bounds_overlap(non_empty[left], non_empty[right]):
                return None
    result = trimesh.util.concatenate([mesh.copy() for mesh in non_empty])
    result.remove_unreferenced_vertices()
    result.fix_normals()
    body_count = len(result.split(only_watertight=False)) if len(result.faces) else 0
    result.metadata["lathe_reference_batch_union"] = {
        "schema": "lathe.geometry.reference_batch_union.v1",
        "method": "disjoint_additive_mesh_concatenation",
        "operand_count": len(meshes),
        "non_empty_operand_count": len(non_empty),
        "reason": "reference_kernel_disjoint_additive_assembly",
        "result_face_count": len(result.faces),
        "result_watertight": bool(result.is_watertight),
        "result_body_count": int(body_count),
    }
    return _set_batch_source_meshes(result, non_empty)


def _profile_cut_state_additive_batch_union(meshes: list[trimesh.Trimesh]) -> trimesh.Trimesh | None:
    non_empty = [mesh for mesh in meshes if len(mesh.faces) > 0]
    if len(non_empty) <= 1:
        return None
    profile_state_count = sum(1 for mesh in non_empty if _profile_cut_state_from_mesh(mesh) is not None)
    if profile_state_count == 0:
        return None
    result = trimesh.util.concatenate([mesh.copy() for mesh in non_empty])
    result.remove_unreferenced_vertices()
    result.fix_normals()
    try:
        body_count = len(result.split(only_watertight=False)) if len(result.faces) else 0
    except (AttributeError, TypeError, ValueError):
        body_count = 0
    result.metadata["lathe_reference_batch_union"] = {
        "schema": "lathe.geometry.reference_batch_union.v1",
        "method": "profile_cut_state_additive_mesh_concatenation_v1",
        "operand_count": len(meshes),
        "non_empty_operand_count": len(non_empty),
        "profile_cut_state_operand_count": int(profile_state_count),
        "reason": "reference_kernel_preserved_profile_cut_additive_detail",
        "overlap_preserved": True,
        "result_face_count": len(result.faces),
        "result_watertight": bool(result.is_watertight),
        "result_body_count": int(body_count),
    }
    return _set_batch_source_meshes(result, non_empty)


def _overlapping_additive_batch_union(
    meshes: list[trimesh.Trimesh],
    *,
    expanded_operand_count: int | None = None,
) -> trimesh.Trimesh | None:
    non_empty = [mesh for mesh in meshes if len(mesh.faces) > 0]
    if len(non_empty) <= 1:
        return None
    result = trimesh.util.concatenate([mesh.copy() for mesh in non_empty])
    result.remove_unreferenced_vertices()
    result.fix_normals()
    try:
        body_count = len(result.split(only_watertight=False)) if len(result.faces) else 0
    except (AttributeError, TypeError, ValueError):
        body_count = 0
    payload: dict[str, Any] = {
        "schema": "lathe.geometry.reference_batch_union.v1",
        "method": "overlapping_additive_mesh_concatenation_v1",
        "operand_count": len(meshes),
        "non_empty_operand_count": len(non_empty),
        "reason": "reference_kernel_preserved_overlapping_additive_detail",
        "overlap_preserved": True,
        "result_face_count": len(result.faces),
        "result_watertight": bool(result.is_watertight),
        "result_body_count": int(body_count),
    }
    if expanded_operand_count is not None:
        payload["compound_source_expansion"] = True
        payload["expanded_operand_count"] = int(expanded_operand_count)
    result.metadata["lathe_reference_batch_union"] = payload
    return _set_batch_source_meshes(result, non_empty)


def _overlap_connected_mesh_groups(meshes: list[trimesh.Trimesh]) -> list[list[trimesh.Trimesh]]:
    non_empty = [mesh for mesh in meshes if len(mesh.faces) > 0]
    if not non_empty:
        return []
    parent = list(range(len(non_empty)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for left in range(len(non_empty)):
        for right in range(left + 1, len(non_empty)):
            if _bounds_overlap(non_empty[left], non_empty[right]):
                union(left, right)

    grouped: dict[int, list[trimesh.Trimesh]] = {}
    group_order: list[int] = []
    for index, mesh in enumerate(non_empty):
        root = find(index)
        if root not in grouped:
            grouped[root] = []
            group_order.append(root)
        grouped[root].append(mesh)
    return [grouped[root] for root in group_order]


def _sdf_primitive_batch_union(
    meshes: list[trimesh.Trimesh],
    *,
    original_operand_count: int,
    expanded_operand_count: int,
) -> trimesh.Trimesh | None:
    if len(meshes) < 2:
        return None
    sdf_union: trimesh.Trimesh | None = meshes[0]
    sdf_step_count = 0
    for operand in meshes[1:]:
        if sdf_union is None:
            return None
        sdf_union = _sdf_boolean("union", sdf_union, operand)
        if sdf_union is None:
            return None
        sdf_step_count += 1
    if sdf_union is None or sdf_step_count != len(meshes) - 1:
        return None
    body_count = len(sdf_union.split(only_watertight=False)) if len(sdf_union.faces) else 0
    if not bool(sdf_union.is_watertight) or body_count != 1:
        return None
    sdf_union.metadata["lathe_reference_batch_union"] = {
        "schema": "lathe.geometry.reference_batch_union.v1",
        "method": "sdf_primitive_batch_union_v1",
        "operand_count": int(original_operand_count),
        "expanded_operand_count": int(expanded_operand_count),
        "sdf_union_step_count": int(sdf_step_count),
        "reason": "reference_kernel_sdf_union_for_overlapping_supported_primitives",
        "result_face_count": len(sdf_union.faces),
        "result_watertight": bool(sdf_union.is_watertight),
        "result_body_count": int(body_count),
    }
    _set_batch_source_meshes(sdf_union, tuple(meshes))
    return sdf_union


def _sdf_batch_ultra_resolution(bounds_min: np.ndarray, bounds_max: np.ndarray) -> tuple[int, int, int]:
    high = _sdf_boolean_resolution(bounds_min, bounds_max, high_detail=True)
    rounded: list[int] = []
    for value in high:
        scaled = max(64, int(round(float(value) * 1.5)))
        multiple = int(round(float(scaled) / 32.0) * 32)
        rounded.append(int(max(64, min(192, multiple))))
    return tuple(rounded)


def _sdf_supported_primitive_batch_union(
    meshes: list[trimesh.Trimesh],
    *,
    original_operand_count: int,
    expanded_operand_count: int,
) -> trimesh.Trimesh | None:
    if len(meshes) < 2:
        return None
    try:
        from ..f_rep import Union, extract_mesh
        from ..f_rep.marching_cubes import _have_skimage
    except (ImportError, ModuleNotFoundError):
        return None
    expr: Any | None = None
    primitive_types: list[str] = []
    source_components: list[str] = []
    for mesh in meshes:
        item = _sdf_expr_from_shape_metadata(mesh)
        if item is None:
            return None
        primitive_expr, primitive_metadata = item
        expr = primitive_expr if expr is None else Union(expr, primitive_expr)
        primitive_types.append(str(primitive_metadata.get("primitive_type") or ""))
        source_components.append(str(primitive_metadata.get("component") or primitive_metadata.get("part") or ""))
    if expr is None:
        return None

    base_bounds_min, base_bounds_max = _mesh_bounds(meshes)
    base_bounds_min = np.asarray(base_bounds_min, dtype=np.float64)
    base_bounds_max = np.asarray(base_bounds_max, dtype=np.float64)
    base_margin = max(float(np.linalg.norm(base_bounds_max - base_bounds_min)) / 96.0, 0.12)
    extraction_backend = "marching_cubes" if _have_skimage() else "dual_contouring"
    extraction_attempts: list[dict[str, Any]] = []
    for margin_factor in (2.0, 3.0, 4.0, 6.0):
        attempt_bounds_min = base_bounds_min - base_margin * margin_factor
        attempt_bounds_max = base_bounds_max + base_margin * margin_factor
        resolution_levels = (
            ("default", _sdf_boolean_resolution(attempt_bounds_min, attempt_bounds_max)),
            ("high_detail", _sdf_boolean_resolution(attempt_bounds_min, attempt_bounds_max, high_detail=True)),
            ("ultra_rounded", _sdf_batch_ultra_resolution(attempt_bounds_min, attempt_bounds_max)),
        )
        for detail_level, resolution in resolution_levels:
            try:
                vertices, faces = extract_mesh(
                    expr,
                    bounds=(
                        tuple(float(value) for value in attempt_bounds_min),
                        tuple(float(value) for value in attempt_bounds_max),
                    ),
                    resolution=resolution,
                    backend=extraction_backend,
                )
            except (ValueError, RuntimeError, AttributeError, IndexError, TypeError, ImportError, ModuleNotFoundError):
                extraction_attempts.append(
                    {
                        "backend": extraction_backend,
                        "margin_factor": float(margin_factor),
                        "resolution": [int(value) for value in resolution],
                        "detail_level": detail_level,
                        "accepted": False,
                        "reason": "extract_mesh_failed",
                    }
                )
                continue
            result = trimesh.Trimesh(
                vertices=np.asarray(vertices, dtype=np.float64),
                faces=np.asarray(faces, dtype=np.int64),
                process=False,
            )
            if len(result.faces) == 0:
                extraction_attempts.append(
                    {
                        "backend": extraction_backend,
                        "margin_factor": float(margin_factor),
                        "resolution": [int(value) for value in resolution],
                        "detail_level": detail_level,
                        "accepted": False,
                        "reason": "empty_mesh",
                    }
                )
                continue
            result.remove_infinite_values()
            result.remove_unreferenced_vertices()
            result.merge_vertices()
            result.fix_normals()
            try:
                body_count = len(result.split(only_watertight=False)) if len(result.faces) else 0
            except (AttributeError, TypeError, ValueError):
                body_count = 0
            accepted = bool(result.is_watertight) and body_count == 1
            extraction_attempts.append(
                {
                    "backend": extraction_backend,
                    "margin_factor": float(margin_factor),
                    "resolution": [int(value) for value in resolution],
                    "detail_level": detail_level,
                    "accepted": accepted,
                    "result_face_count": len(result.faces),
                    "result_vertex_count": len(result.vertices),
                    "result_watertight": bool(result.is_watertight),
                    "result_body_count": int(body_count),
                }
            )
            if not accepted:
                continue
            result.metadata["lathe_reference_batch_union"] = {
                "schema": "lathe.geometry.reference_batch_union.v1",
                "method": "sdf_supported_primitive_batch_union_v1",
                "operand_count": int(original_operand_count),
                "expanded_operand_count": int(expanded_operand_count),
                "source_primitive_types": sorted(set(primitive_types)),
                "source_components": source_components,
                "reason": "reference_kernel_single_pass_sdf_union_for_supported_primitives",
                "backend": f"lathe.f_rep.{extraction_backend}",
                "requested_backend": "lathe.f_rep.marching_cubes",
                "actual_backend": f"lathe.f_rep.{extraction_backend}",
                "backend_fallback_reason": "" if extraction_backend == "marching_cubes" else "scikit_image_unavailable",
                "exact_kernel_path": False,
                "fallback": False,
                "bounds_min": [float(value) for value in attempt_bounds_min],
                "bounds_max": [float(value) for value in attempt_bounds_max],
                "resolution": [int(value) for value in resolution],
                "extraction_attempt_count": len(extraction_attempts),
                "extraction_attempts": extraction_attempts,
                "result_face_count": len(result.faces),
                "result_vertex_count": len(result.vertices),
                "result_watertight": bool(result.is_watertight),
                "result_body_count": int(body_count),
            }
            return _set_batch_source_meshes(result, tuple(meshes))
    return None


def _circular_swept_profile_graph_batch_union(
    meshes: list[trimesh.Trimesh],
    *,
    original_operand_count: int,
    expanded_operand_count: int,
) -> trimesh.Trimesh | None:
    if len(meshes) < 2:
        return None
    segments: list[dict[str, Any]] = []
    ring_count = 12
    source_components: list[str] = []
    for mesh in meshes:
        primitive = _resolved_shape_primitive_metadata(mesh)
        if str(primitive.get("primitive_type") or "") != "swept_profile":
            return None
        swept = _sdf_circular_swept_profile_metadata(primitive)
        if swept is None:
            return None
        try:
            center = np.asarray([float(value) for value in primitive.get("center", (0.0, 0.0, 0.0))], dtype=np.float64)
            start = np.asarray(swept["start"], dtype=np.float64)
            end = np.asarray(swept["end"], dtype=np.float64)
            radius = float(swept["radius"])
        except (TypeError, ValueError, KeyError):
            return None
        if center.shape != (3,) or start.shape != (3,) or end.shape != (3,) or radius <= 0.0:
            return None
        if not bool(swept.get("world_path")):
            start = center + start
            end = center + end
        length = float(np.linalg.norm(end - start))
        if length <= max(radius * 0.1, 1e-6):
            return None
        ring_count = max(ring_count, int(swept.get("cross_section_vertex_count") or 0))
        source_components.append(str(primitive.get("component") or "swept_profile_member"))
        segments.append(
            {
                "start": start,
                "end": end,
                "radius": radius,
                "length": length,
                "component": str(primitive.get("component") or "swept_profile_member"),
                "region": str(primitive.get("region") or ""),
                "part": str(primitive.get("part") or ""),
            }
        )
    ring_count = max(8, min(48, ring_count))
    vertices: list[list[float]] = []
    faces: list[list[int]] = []
    node_indices: dict[tuple[float, float, float], int] = {}

    def node_key(point: np.ndarray) -> tuple[float, float, float]:
        return tuple(round(float(value), 6) for value in point)

    def node_index(point: np.ndarray) -> int:
        key = node_key(point)
        existing = node_indices.get(key)
        if existing is not None:
            return existing
        index = len(vertices)
        vertices.append([float(value) for value in point])
        node_indices[key] = index
        return index

    def basis_for(direction: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
        unit = direction / float(np.linalg.norm(direction))
        reference = np.asarray((0.0, 0.0, 1.0), dtype=np.float64)
        if abs(float(np.dot(unit, reference))) > 0.92:
            reference = np.asarray((1.0, 0.0, 0.0), dtype=np.float64)
        u_axis = np.cross(unit, reference)
        u_len = float(np.linalg.norm(u_axis))
        if u_len <= 1e-9:
            return None
        u_axis = u_axis / u_len
        v_axis = np.cross(unit, u_axis)
        v_len = float(np.linalg.norm(v_axis))
        if v_len <= 1e-9:
            return None
        return u_axis, v_axis / v_len

    for segment in segments:
        start = np.asarray(segment["start"], dtype=np.float64)
        end = np.asarray(segment["end"], dtype=np.float64)
        direction = end - start
        basis = basis_for(direction)
        if basis is None:
            return None
        u_axis, v_axis = basis
        radius = float(segment["radius"])
        start_center = node_index(start)
        end_center = node_index(end)
        start_ring: list[int] = []
        end_ring: list[int] = []
        for index in range(ring_count):
            angle = (math.tau * float(index)) / float(ring_count)
            offset = radius * (math.cos(angle) * u_axis + math.sin(angle) * v_axis)
            start_ring.append(len(vertices))
            vertices.append([float(value) for value in start + offset])
            end_ring.append(len(vertices))
            vertices.append([float(value) for value in end + offset])
        for index in range(ring_count):
            next_index = (index + 1) % ring_count
            s0 = start_ring[index]
            s1 = start_ring[next_index]
            e0 = end_ring[index]
            e1 = end_ring[next_index]
            faces.append([s0, s1, e1])
            faces.append([s0, e1, e0])
            faces.append([start_center, s0, s1])
            faces.append([end_center, e1, e0])

    if not vertices or not faces:
        return None
    result = trimesh.Trimesh(
        vertices=np.asarray(vertices, dtype=np.float64),
        faces=np.asarray(faces, dtype=np.int64),
        process=False,
    )
    result.remove_infinite_values()
    result.remove_unreferenced_vertices()
    result.fix_normals()
    try:
        body_count = len(result.split(only_watertight=False)) if len(result.faces) else 0
    except (AttributeError, TypeError, ValueError):
        body_count = 0
    if not bool(result.is_watertight) or body_count != 1:
        return _circular_swept_profile_graph_sdf_union(
            segments,
            meshes=meshes,
            original_operand_count=original_operand_count,
            expanded_operand_count=expanded_operand_count,
            ring_count=ring_count,
            source_components=source_components,
        )
    result.metadata["lathe_reference_batch_union"] = {
        "schema": "lathe.geometry.reference_batch_union.v1",
        "method": "circular_swept_profile_graph_joint_mesh_v1",
        "operand_count": int(original_operand_count),
        "expanded_operand_count": int(expanded_operand_count),
        "source_member_count": len(segments),
        "joint_count": len(node_indices),
        "ring_vertex_count": int(ring_count),
        "reason": "reference_kernel_constructed_structural_swept_profile_graph",
        "exact_kernel_path": True,
        "fallback": False,
        "result_face_count": len(result.faces),
        "result_vertex_count": len(result.vertices),
        "result_watertight": bool(result.is_watertight),
        "result_body_count": int(body_count),
        "source_components": source_components,
    }
    result.metadata["lathe_reference_structural_graph"] = {
        "schema": "lathe.geometry.reference_structural_graph.v1",
        "method": "shared_joint_cap_tube_graph_v1",
        "member_count": len(segments),
        "joint_count": len(node_indices),
        "ring_vertex_count": int(ring_count),
    }
    return _set_batch_source_meshes(result, tuple(meshes))


def _circular_swept_profile_graph_sdf_union(
    segments: list[dict[str, Any]],
    *,
    meshes: list[trimesh.Trimesh],
    original_operand_count: int,
    expanded_operand_count: int,
    ring_count: int,
    source_components: list[str],
) -> trimesh.Trimesh | None:
    if len(segments) < 2:
        return None
    try:
        from ..f_rep import Cylinder, Rotate, Translate, Union, extract_mesh
        from ..f_rep.marching_cubes import _have_skimage
    except (ImportError, ModuleNotFoundError):
        return None

    def align_y_to_direction(expr: Any, direction: np.ndarray) -> Any | None:
        norm = float(np.linalg.norm(direction))
        if norm <= 1e-9:
            return None
        target = direction / norm
        source = np.asarray([0.0, 1.0, 0.0], dtype=np.float64)
        dot = float(np.clip(np.dot(source, target), -1.0, 1.0))
        if dot >= 1.0 - 1e-9:
            return expr
        if dot <= -1.0 + 1e-9:
            return Rotate(expr, axis=(1.0, 0.0, 0.0), angle=math.pi)
        axis = np.cross(source, target)
        axis_norm = float(np.linalg.norm(axis))
        if axis_norm <= 1e-9:
            return None
        axis = axis / axis_norm
        return Rotate(
            expr,
            axis=(float(axis[0]), float(axis[1]), float(axis[2])),
            angle=float(math.acos(dot)),
        )

    expr: Any | None = None
    max_radius = 0.0
    for segment in segments:
        start = np.asarray(segment["start"], dtype=np.float64)
        end = np.asarray(segment["end"], dtype=np.float64)
        direction = end - start
        radius = float(segment["radius"])
        length = float(segment["length"])
        max_radius = max(max_radius, radius)
        member_expr = align_y_to_direction(Cylinder(radius=radius, height=length), direction)
        if member_expr is None:
            return None
        midpoint = (start + end) * 0.5
        member_expr = Translate(member_expr, offset=tuple(float(value) for value in midpoint))
        expr = member_expr if expr is None else Union(expr, member_expr)
    if expr is None:
        return None

    base_bounds_min, base_bounds_max = _mesh_bounds(meshes)
    base_bounds_min = np.asarray(base_bounds_min, dtype=np.float64)
    base_bounds_max = np.asarray(base_bounds_max, dtype=np.float64)
    diagonal = float(np.linalg.norm(base_bounds_max - base_bounds_min))
    base_margin = max(diagonal / 128.0, max_radius * 2.5, 0.12)
    extraction_backend = "marching_cubes" if _have_skimage() else "dual_contouring"
    extraction_attempts: list[dict[str, Any]] = []
    for margin_factor in (1.5, 2.5, 4.0):
        attempt_bounds_min = base_bounds_min - base_margin * margin_factor
        attempt_bounds_max = base_bounds_max + base_margin * margin_factor
        for high_detail in (False, True):
            resolution = _sdf_boolean_resolution(
                attempt_bounds_min,
                attempt_bounds_max,
                high_detail=high_detail,
            )
            try:
                vertices, faces = extract_mesh(
                    expr,
                    bounds=(
                        tuple(float(value) for value in attempt_bounds_min),
                        tuple(float(value) for value in attempt_bounds_max),
                    ),
                    resolution=resolution,
                    backend=extraction_backend,
                )
            except (ValueError, RuntimeError, AttributeError, IndexError, TypeError, ImportError, ModuleNotFoundError):
                extraction_attempts.append(
                    {
                        "backend": extraction_backend,
                        "margin_factor": float(margin_factor),
                        "resolution": [int(value) for value in resolution],
                        "high_detail_retry": bool(high_detail),
                        "accepted": False,
                        "reason": "extract_mesh_failed",
                    }
                )
                continue
            result = trimesh.Trimesh(
                vertices=np.asarray(vertices, dtype=np.float64),
                faces=np.asarray(faces, dtype=np.int64),
                process=False,
            )
            if len(result.faces) == 0:
                extraction_attempts.append(
                    {
                        "backend": extraction_backend,
                        "margin_factor": float(margin_factor),
                        "resolution": [int(value) for value in resolution],
                        "high_detail_retry": bool(high_detail),
                        "accepted": False,
                        "reason": "empty_mesh",
                    }
                )
                continue
            result.remove_infinite_values()
            result.remove_unreferenced_vertices()
            result.merge_vertices()
            result.fix_normals()
            try:
                body_count = len(result.split(only_watertight=False)) if len(result.faces) else 0
            except (AttributeError, TypeError, ValueError):
                body_count = 0
            accepted = bool(result.is_watertight) and body_count == 1
            extraction_attempts.append(
                {
                    "backend": extraction_backend,
                    "margin_factor": float(margin_factor),
                    "resolution": [int(value) for value in resolution],
                    "high_detail_retry": bool(high_detail),
                    "accepted": accepted,
                    "result_face_count": len(result.faces),
                    "result_vertex_count": len(result.vertices),
                    "result_watertight": bool(result.is_watertight),
                    "result_body_count": int(body_count),
                }
            )
            if not accepted:
                continue
            joint_keys = {
                tuple(
                    round(float(value), 6)
                    for value in np.asarray(segment[key], dtype=np.float64)
                )
                for segment in segments
                for key in ("start", "end")
            }
            result.metadata["lathe_reference_batch_union"] = {
                "schema": "lathe.geometry.reference_batch_union.v1",
                "method": "sdf_circular_swept_profile_graph_union_v1",
                "operand_count": int(original_operand_count),
                "expanded_operand_count": int(expanded_operand_count),
                "source_member_count": len(segments),
                "joint_count": len(joint_keys),
                "ring_vertex_count": int(ring_count),
                "reason": "reference_kernel_fused_structural_swept_profile_graph",
                "backend": f"lathe.f_rep.{extraction_backend}",
                "requested_backend": "lathe.f_rep.marching_cubes",
                "actual_backend": f"lathe.f_rep.{extraction_backend}",
                "backend_fallback_reason": "" if extraction_backend == "marching_cubes" else "scikit_image_unavailable",
                "exact_kernel_path": False,
                "fallback": False,
                "result_face_count": len(result.faces),
                "result_vertex_count": len(result.vertices),
                "result_watertight": bool(result.is_watertight),
                "result_body_count": int(body_count),
                "extraction_attempt_count": len(extraction_attempts),
                "extraction_attempts": extraction_attempts,
                "source_components": source_components,
            }
            result.metadata["lathe_reference_structural_graph"] = {
                "schema": "lathe.geometry.reference_structural_graph.v1",
                "method": "single_sdf_extraction_tube_graph_v1",
                "member_count": len(segments),
                "joint_count": int(result.metadata["lathe_reference_batch_union"]["joint_count"]),
                "ring_vertex_count": int(ring_count),
            }
            return _set_batch_source_meshes(result, tuple(meshes))
    return None


def _batch_source_meshes(mesh: trimesh.Trimesh) -> tuple[trimesh.Trimesh, ...]:
    sources = getattr(mesh, _BATCH_SOURCE_ATTR, ())
    if not isinstance(sources, tuple):
        return ()
    return tuple(item for item in sources if isinstance(item, trimesh.Trimesh))


def _set_batch_source_meshes(
    mesh: trimesh.Trimesh,
    sources: Iterable[trimesh.Trimesh],
) -> trimesh.Trimesh:
    setattr(mesh, _BATCH_SOURCE_ATTR, tuple(source.copy() for source in sources))
    return mesh


def _axis_aligned_box_mesh(
    *,
    bounds_min: np.ndarray,
    bounds_max: np.ndarray,
) -> trimesh.Trimesh:
    extents = bounds_max - bounds_min
    center = (bounds_min + bounds_max) * 0.5
    transform = np.eye(4)
    transform[:3, 3] = center
    mesh = trimesh.creation.box(extents=extents, transform=transform)
    _record_box_metadata(mesh, bounds_min=bounds_min, bounds_max=bounds_max)
    return mesh


def _record_box_metadata(
    mesh: trimesh.Trimesh,
    *,
    bounds_min: np.ndarray,
    bounds_max: np.ndarray,
) -> None:
    mesh.metadata[_PRIMITIVE_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_primitive.v1",
        "kind": "box",
        "bounds_min": [float(value) for value in bounds_min],
        "bounds_max": [float(value) for value in bounds_max],
    }


def _record_cylinder_metadata(
    mesh: trimesh.Trimesh,
    *,
    center: np.ndarray,
    radius: float,
    height: float,
    axis: str,
    part: str = "cylinder",
) -> None:
    mesh.metadata[_PRIMITIVE_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_primitive.v1",
        "kind": "cylinder",
        "center": [float(value) for value in center],
        "radius": float(radius),
        "height": float(height),
        "axis": str(axis),
        "part": str(part),
    }


def _rectangular_extruded_profile_bounds(
    primitive: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray] | None:
    if primitive.get("primitive_type") != "extruded_profile":
        return None
    axis = str(primitive.get("axis") or "z")
    if axis not in {"x", "y", "z"}:
        return None
    if any(
        key in primitive
        and primitive.get(key) not in (None, 1.0, 0.0)
        for key in (
            "extrude_start_scale",
            "extrude_end_scale",
            "extrude_twist_degrees",
        )
    ):
        return None
    try:
        center = np.asarray(primitive["center"], dtype=np.float64)
        height = float(primitive["extrude_height"])
        polygon = [
            (float(point[0]), float(point[1]))
            for point in primitive["profile_polygon"]
        ]
    except (KeyError, TypeError, ValueError, IndexError):
        return None
    if center.shape != (3,) or height <= 0.0 or len(polygon) != 4:
        return None
    axis_index = _axis_index(axis)
    plane_axes = tuple(index for index in range(3) if index != axis_index)
    plane_points: list[tuple[float, float]] = []
    for u, v in polygon:
        if axis == "z":
            world = np.asarray((center[0] + u, center[1] + v, center[2]), dtype=np.float64)
        elif axis == "y":
            world = np.asarray((center[0] + u, center[1], center[2] - v), dtype=np.float64)
        else:
            world = np.asarray((center[0], center[1] + v, center[2] - u), dtype=np.float64)
        plane_points.append((float(world[plane_axes[0]]), float(world[plane_axes[1]])))
    coords = np.asarray(plane_points, dtype=np.float64)
    plane_min = coords.min(axis=0)
    plane_max = coords.max(axis=0)
    spans = plane_max - plane_min
    if bool(np.any(spans <= 1e-9)):
        return None
    area = 0.0
    for index, point in enumerate(plane_points):
        next_point = plane_points[(index + 1) % len(plane_points)]
        area += point[0] * next_point[1] - next_point[0] * point[1]
    area = abs(area) * 0.5
    rect_area = float(spans[0] * spans[1])
    if abs(area - rect_area) > max(1e-7, rect_area * 1e-7):
        return None
    tolerance = max(1e-7, float(max(spans)) * 1e-7)
    for point in plane_points:
        if any(
            abs(float(point[axis]) - float(plane_min[axis])) > tolerance
            and abs(float(point[axis]) - float(plane_max[axis])) > tolerance
            for axis in range(2)
        ):
            return None
    corner_keys = {
        (
            int(round((point[0] - plane_min[0]) / max(spans[0], 1e-9))),
            int(round((point[1] - plane_min[1]) / max(spans[1], 1e-9))),
        )
        for point in plane_points
    }
    if corner_keys != {(0, 0), (1, 0), (1, 1), (0, 1)}:
        return None
    bmin = np.zeros(3, dtype=np.float64)
    bmax = np.zeros(3, dtype=np.float64)
    bmin[axis_index] = float(center[axis_index] - height * 0.5)
    bmax[axis_index] = float(center[axis_index] + height * 0.5)
    bmin[plane_axes[0]] = float(plane_min[0])
    bmax[plane_axes[0]] = float(plane_max[0])
    bmin[plane_axes[1]] = float(plane_min[1])
    bmax[plane_axes[1]] = float(plane_max[1])
    return bmin, bmax


def _box_bounds_from_metadata(mesh: trimesh.Trimesh) -> tuple[np.ndarray, np.ndarray] | None:
    metadata = mesh.metadata.get(_PRIMITIVE_METADATA_KEY)
    if isinstance(metadata, dict) and metadata.get("kind") == "box":
        try:
            bmin = np.asarray(metadata["bounds_min"], dtype=np.float64)
            bmax = np.asarray(metadata["bounds_max"], dtype=np.float64)
        except (KeyError, TypeError, ValueError):
            return None
    else:
        cut_state = _profile_cut_state_from_mesh(mesh)
        if cut_state is not None:
            try:
                bmin = np.asarray(cut_state["box_min"], dtype=np.float64)
                bmax = np.asarray(cut_state["box_max"], dtype=np.float64)
            except (KeyError, TypeError, ValueError):
                return None
            if bmin.shape == (3,) and bmax.shape == (3,) and not bool(np.any(bmax <= bmin)):
                return bmin, bmax
        boss_state = _boss_state_from_mesh(mesh)
        if boss_state is not None:
            try:
                bmin = np.asarray(boss_state["box_min"], dtype=np.float64)
                bmax = np.asarray(boss_state["box_max"], dtype=np.float64)
            except (KeyError, TypeError, ValueError):
                return None
            if bmin.shape == (3,) and bmax.shape == (3,) and not bool(np.any(bmax <= bmin)):
                return bmin, bmax
        primitive = _resolved_shape_primitive_metadata(mesh)
        extruded_bounds = _rectangular_extruded_profile_bounds(primitive)
        if extruded_bounds is not None:
            bmin, bmax = extruded_bounds
        elif primitive.get("primitive_type") != "box":
            return None
        else:
            try:
                center = np.asarray(primitive["center"], dtype=np.float64)
                extents = np.asarray(primitive["extents"], dtype=np.float64)
            except (KeyError, TypeError, ValueError):
                return None
            if center.shape != (3,) or extents.shape != (3,):
                return None
            half = extents * 0.5
            bmin = center - half
            bmax = center + half
    if bmin.shape != (3,) or bmax.shape != (3,) or bool(np.any(bmax <= bmin)):
        return None
    return bmin, bmax


def _shape_primitive_metadata(mesh: trimesh.Trimesh) -> dict[str, Any]:
    metadata = mesh.metadata.get(_SHAPE_PRIMITIVE_METADATA_KEY)
    return dict(metadata) if isinstance(metadata, dict) else {}


def _record_shape_primitive_metadata_from_params(
    mesh: trimesh.Trimesh,
    kind: str,
    params: dict[str, Any],
) -> None:
    try:
        primitive = _shape_primitive_from_params(kind, params)
        payload = primitive.to_dict()
    except (TypeError, ValueError, KeyError, AttributeError):
        return
    payload["schema"] = "lathe.shape_primitive_mesh_metadata.v1"
    mesh.metadata[_SHAPE_PRIMITIVE_METADATA_KEY] = payload


def _cylinder_metadata(mesh: trimesh.Trimesh) -> dict[str, Any] | None:
    metadata = mesh.metadata.get(_PRIMITIVE_METADATA_KEY)
    if isinstance(metadata, dict) and metadata.get("kind") == "cylinder":
        try:
            center = np.asarray(metadata["center"], dtype=np.float64)
            radius = float(metadata["radius"])
            height = float(metadata["height"])
            axis = str(metadata.get("axis") or "y")
        except (KeyError, TypeError, ValueError):
            return None
        if center.shape != (3,) or radius <= 0.0 or height <= 0.0 or axis not in {"x", "y", "z"}:
            return None
        return {
            "axis": axis,
            "center": center,
            "radius": radius,
            "height": height,
            "part": str(metadata.get("part") or "cylinder"),
            "bevel_width_cm": 0.0,
        }
    primitive = _resolved_shape_primitive_metadata(mesh)
    if primitive.get("primitive_type") != "cylinder":
        return None
    try:
        center = np.asarray(primitive["center"], dtype=np.float64)
        radius = float(primitive["radius"])
        height = float(primitive["height"])
        axis = str(primitive.get("axis") or "y")
    except (KeyError, TypeError, ValueError):
        return None
    if center.shape != (3,) or radius <= 0.0 or height <= 0.0 or axis not in {"x", "y", "z"}:
        return None
    bevel = 0.0
    polybevel = primitive.get("v2_polybevel_modifier")
    if isinstance(polybevel, dict):
        try:
            bevel = max(0.0, float(polybevel.get("width_cm") or 0.0))
        except (TypeError, ValueError):
            bevel = 0.0
    return {
        "axis": axis,
        "center": center,
        "radius": radius,
        "height": height,
        "part": str(primitive.get("part") or "cylinder"),
        "bevel_width_cm": bevel,
    }


def _profile_cut_state_from_mesh(mesh: trimesh.Trimesh) -> dict[str, Any] | None:
    state = mesh.metadata.get(_PROFILE_CUT_STATE_METADATA_KEY)
    if not isinstance(state, dict) or state.get("schema") != "lathe.geometry.reference_profile_cut_state.v1":
        return None
    return dict(state)


def _boss_state_from_mesh(mesh: trimesh.Trimesh) -> dict[str, Any] | None:
    state = mesh.metadata.get(_BOSS_STATE_METADATA_KEY)
    if not isinstance(state, dict) or state.get("schema") != "lathe.geometry.reference_boss_state.v1":
        return None
    return dict(state)


def _resolved_shape_primitive_metadata(mesh: trimesh.Trimesh) -> dict[str, Any]:
    metadata = _shape_primitive_metadata(mesh)
    current = dict(metadata)
    for _ in range(4):
        semantic_metadata = current.get("semantic_metadata")
        if not isinstance(semantic_metadata, dict):
            break
        source_metadata = semantic_metadata.get("source_shape_primitive")
        if not isinstance(source_metadata, dict):
            break
        next_metadata = dict(source_metadata)
        if next_metadata == current:
            break
        current = next_metadata
    return current


def _requested_profile_hole_count_from_shape_metadata(metadata: dict[str, Any]) -> int:
    max_count = 0
    stack: list[tuple[dict[str, Any], int]] = [(metadata, 0)]
    seen: set[int] = set()
    while stack:
        current, depth = stack.pop()
        if depth > 6:
            continue
        marker = id(current)
        if marker in seen:
            continue
        seen.add(marker)
        modifier = current.get("v2_mount_plate_modifier")
        if isinstance(modifier, dict):
            try:
                max_count = max(max_count, int(modifier.get("hole_count") or 0))
            except (TypeError, ValueError):
                pass
        semantic_metadata = current.get("semantic_metadata")
        if isinstance(semantic_metadata, dict):
            shape_v2 = semantic_metadata.get("shape_ir_v2")
            if isinstance(shape_v2, dict):
                stack.append((shape_v2, depth + 1))
            source_metadata = semantic_metadata.get("source_shape_primitive")
            if isinstance(source_metadata, dict):
                stack.append((source_metadata, depth + 1))
            source_list = semantic_metadata.get("source_shape_primitives")
            if isinstance(source_list, list):
                for item in source_list:
                    if isinstance(item, dict):
                        stack.append((item, depth + 1))
    return max_count


def _shape_metadata_has_any_key(metadata: dict[str, Any], keys: set[str]) -> bool:
    stack: list[tuple[dict[str, Any], int]] = [(metadata, 0)]
    seen: set[int] = set()
    while stack:
        current, depth = stack.pop()
        if depth > 6:
            continue
        marker = id(current)
        if marker in seen:
            continue
        seen.add(marker)
        if any(key in current for key in keys):
            return True
        semantic_metadata = current.get("semantic_metadata")
        if isinstance(semantic_metadata, dict):
            shape_v2 = semantic_metadata.get("shape_ir_v2")
            if isinstance(shape_v2, dict):
                stack.append((shape_v2, depth + 1))
            source_metadata = semantic_metadata.get("source_shape_primitive")
            if isinstance(source_metadata, dict):
                stack.append((source_metadata, depth + 1))
            source_list = semantic_metadata.get("source_shape_primitives")
            if isinstance(source_list, list):
                for item in source_list:
                    if isinstance(item, dict):
                        stack.append((item, depth + 1))
    return False


def _source_mesh_from_shape_primitive_metadata(metadata: dict[str, Any]) -> trimesh.Trimesh | None:
    primitive_type = str(metadata.get("primitive_type") or "")
    if primitive_type not in _EXACT_IMPORT_PRIMITIVE_KINDS:
        return None
    try:
        from ..errors import ContractViolation
        from ..exact_solids import primitive_mesh

        primitive = _shape_primitive_from_params(primitive_type, metadata)
        mesh = primitive_mesh(primitive)
        if primitive_type in {"heightfield", "terrain_patch"} and not bool(mesh.is_watertight):
            from .shape_ir_lowering import _solidify_heightfield_mesh

            mesh, _ = _solidify_heightfield_mesh(mesh)
        if len(mesh.faces) == 0 or not bool(mesh.is_watertight):
            return None
        return mesh
    except (ContractViolation, ImportError, TypeError, ValueError, RuntimeError, KeyError, IndexError, OSError):
        return None


def _box_piece_meshes_from_exact_metadata(metadata: dict[str, Any]) -> tuple[trimesh.Trimesh, ...]:
    pieces = metadata.get("box_pieces")
    if not isinstance(pieces, list) or not pieces:
        return ()
    meshes: list[trimesh.Trimesh] = []
    for piece in pieces:
        if not isinstance(piece, dict):
            return ()
        try:
            piece_min = np.asarray(piece["box_min"], dtype=np.float64)
            piece_max = np.asarray(piece["box_max"], dtype=np.float64)
        except (KeyError, TypeError, ValueError):
            return ()
        if piece_min.shape != (3,) or piece_max.shape != (3,) or bool(np.any(piece_max <= piece_min + 1e-9)):
            return ()
        meshes.append(_axis_aligned_box_mesh(bounds_min=piece_min, bounds_max=piece_max))
    return tuple(meshes)


def _compound_source_meshes_from_metadata(mesh: trimesh.Trimesh) -> tuple[trimesh.Trimesh, ...]:
    metadata = _shape_primitive_metadata(mesh)
    semantic_metadata = metadata.get("semantic_metadata")
    if not isinstance(semantic_metadata, dict):
        return ()
    kernel_metadata = semantic_metadata.get("kernel_result_metadata")
    if isinstance(kernel_metadata, dict):
        if isinstance(kernel_metadata.get(_PROFILE_CUT_STATE_METADATA_KEY), dict):
            return ()
        exact = kernel_metadata.get(_EXACT_BOOLEAN_METADATA_KEY)
        if isinstance(exact, dict) and str(exact.get("op") or "") in {"difference", "intersection"}:
            exact_box_pieces = _box_piece_meshes_from_exact_metadata(exact)
            if exact_box_pieces:
                return exact_box_pieces
            return ()
    sources = semantic_metadata.get("source_shape_primitives")
    if not isinstance(sources, list) or not sources:
        single_source = semantic_metadata.get("source_shape_primitive")
        if isinstance(single_source, dict):
            sources = [single_source]
    if not isinstance(sources, list) or not sources:
        return ()
    meshes: list[trimesh.Trimesh] = []
    for source in sources:
        if not isinstance(source, dict):
            return ()
        source_mesh = _source_mesh_from_shape_primitive_metadata(source)
        if source_mesh is None or len(source_mesh.faces) == 0:
            return ()
        meshes.append(source_mesh)
    return tuple(meshes)


def _expand_compound_batch_union_sources(
    meshes: list[trimesh.Trimesh],
) -> tuple[list[trimesh.Trimesh], bool]:
    expanded: list[trimesh.Trimesh] = []
    changed = False
    for mesh in meshes:
        sources = _compound_source_meshes_from_metadata(mesh)
        if sources:
            expanded.extend(source.copy() for source in sources)
            changed = True
        else:
            expanded.append(mesh)
    return expanded, changed


def _mark_expanded_batch_union_result(
    result: trimesh.Trimesh,
    *,
    original_operand_count: int,
    expanded_operand_count: int,
) -> trimesh.Trimesh:
    for key in ("lathe_reference_batch_union", _EXACT_BOOLEAN_METADATA_KEY):
        metadata = result.metadata.get(key)
        if isinstance(metadata, dict):
            metadata["compound_source_expansion"] = True
            metadata["original_operand_count"] = int(original_operand_count)
            metadata["expanded_operand_count"] = int(expanded_operand_count)
            result.metadata[key] = metadata
    return result


def _extruded_profile_metadata(mesh: trimesh.Trimesh) -> dict[str, Any] | None:
    metadata = _resolved_shape_primitive_metadata(mesh)
    if metadata.get("primitive_type") != "extruded_profile":
        return None
    axis = str(metadata.get("axis") or "z")
    if axis not in {"x", "y", "z"}:
        return None
    try:
        center = np.asarray(metadata["center"], dtype=np.float64)
        height = float(metadata["extrude_height"])
        profile = [
            (float(point[0]), float(point[1]))
            for point in metadata["profile_polygon"]
        ]
    except (KeyError, TypeError, ValueError, IndexError):
        return None
    if center.shape != (3,) or height <= 0.0 or len(profile) < 3:
        return None
    bevel = 0.0
    bevel_segments = 1
    polybevel = metadata.get("v2_polybevel_modifier")
    if isinstance(polybevel, dict):
        try:
            bevel = max(0.0, float(polybevel.get("width_cm") or 0.0))
        except (TypeError, ValueError):
            bevel = 0.0
        try:
            bevel_segments = max(1, int(polybevel.get("segments") or 1))
        except (TypeError, ValueError):
            bevel_segments = 1
    return {
        "axis": axis,
        "center": center,
        "extrude_height": height,
        "profile_polygon": profile,
        "part": str(metadata.get("part") or "extruded_profile"),
        "bevel_width_cm": bevel,
        "bevel_segments": bevel_segments,
    }


def _revolved_profile_metadata(mesh: trimesh.Trimesh) -> dict[str, Any] | None:
    metadata = _resolved_shape_primitive_metadata(mesh)
    if metadata.get("primitive_type") != "revolved_profile":
        return None
    axis = str(metadata.get("axis") or "z")
    if axis not in {"x", "y", "z"}:
        return None
    try:
        center = np.asarray(metadata["center"], dtype=np.float64)
        profile = [
            (float(point[0]), abs(float(point[1])))
            for point in metadata["profile_points"]
        ]
    except (KeyError, TypeError, ValueError, IndexError):
        return None
    if center.shape != (3,) or len(profile) < 2:
        return None
    if any(radius <= 0.0 for _, radius in profile):
        return None
    bevel = 0.0
    polybevel = metadata.get("v2_polybevel_modifier")
    if isinstance(polybevel, dict):
        try:
            bevel = max(0.0, float(polybevel.get("width_cm") or 0.0))
        except (TypeError, ValueError):
            bevel = 0.0
    modifier = metadata.get("v2_countersunk_hole_modifier")
    style = ""
    if isinstance(modifier, dict):
        style = str(modifier.get("style") or "")
    return {
        "axis": axis,
        "center": center,
        "profile_points": profile,
        "part": str(metadata.get("part") or "revolved_profile"),
        "bevel_width_cm": bevel,
        "style": style,
    }


def _axis_index(axis: str) -> int:
    return {"x": 0, "y": 1, "z": 2}[axis]


def _axis_name(index: int) -> str:
    return ("x", "y", "z")[int(index)]


def _axis_aligned_uniform_transform(
    matrix: np.ndarray,
) -> tuple[
    np.ndarray,
    np.ndarray,
    tuple[int, int, int],
    tuple[int, int, int],
    float,
] | None:
    transform = np.asarray(matrix, dtype=np.float64)
    if transform.shape != (4, 4):
        return None
    eps = 1e-9
    if not np.allclose(transform[3], np.asarray([0.0, 0.0, 0.0, 1.0]), atol=eps):
        return None
    linear = transform[:3, :3]
    input_to_output: list[int] = [-1, -1, -1]
    input_signs: list[int] = [1, 1, 1]
    scales: list[float] = []
    used_outputs: set[int] = set()
    for input_axis in range(3):
        selected_output: int | None = None
        selected_sign = 1
        selected_scale = 0.0
        for output_axis in range(3):
            value = float(linear[output_axis, input_axis])
            if abs(value) <= eps:
                continue
            if selected_output is not None:
                return None
            selected_output = output_axis
            selected_sign = 1 if value > 0.0 else -1
            selected_scale = abs(value)
        if selected_output is None or selected_output in used_outputs:
            return None
        used_outputs.add(selected_output)
        input_to_output[input_axis] = selected_output
        input_signs[input_axis] = selected_sign
        scales.append(selected_scale)
    if sorted(input_to_output) != [0, 1, 2]:
        return None
    scale = sum(scales) / len(scales)
    if scale <= eps or any(abs(value - scale) > max(eps, scale * 1e-9) for value in scales):
        return None
    rotation = np.zeros((3, 3), dtype=np.float64)
    for input_axis, output_axis in enumerate(input_to_output):
        rotation[output_axis, input_axis] = float(input_signs[input_axis])
    return (
        rotation,
        transform[:3, 3].astype(np.float64),
        tuple(input_to_output),  # type: ignore[return-value]
        tuple(input_signs),  # type: ignore[return-value]
        float(scale),
    )


def _is_identity_axis_transform(
    input_to_output: tuple[int, int, int],
    input_signs: tuple[int, int, int],
) -> bool:
    return input_to_output == (0, 1, 2) and input_signs == (1, 1, 1)


def _transformed_point(
    point: Iterable[float],
    *,
    rotation: np.ndarray,
    translation: np.ndarray,
    scale: float,
) -> list[float]:
    values = np.asarray(list(point), dtype=np.float64)
    return [float(value) for value in (scale * (rotation @ values) + translation)]


def _transformed_vector(
    point: Iterable[float],
    *,
    rotation: np.ndarray,
    scale: float,
) -> list[float]:
    values = np.asarray(list(point), dtype=np.float64)
    return [float(value) for value in (scale * (rotation @ values))]


def _extruded_profile_basis(axis: str) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    if axis == "z":
        return (
            np.asarray([1.0, 0.0, 0.0], dtype=np.float64),
            np.asarray([0.0, 1.0, 0.0], dtype=np.float64),
            np.asarray([0.0, 0.0, 1.0], dtype=np.float64),
        )
    if axis == "y":
        return (
            np.asarray([1.0, 0.0, 0.0], dtype=np.float64),
            np.asarray([0.0, 0.0, -1.0], dtype=np.float64),
            np.asarray([0.0, 1.0, 0.0], dtype=np.float64),
        )
    if axis == "x":
        return (
            np.asarray([0.0, 0.0, -1.0], dtype=np.float64),
            np.asarray([0.0, 1.0, 0.0], dtype=np.float64),
            np.asarray([1.0, 0.0, 0.0], dtype=np.float64),
        )
    return None


def _transformed_extruded_profile_polygon(
    polygon: Any,
    *,
    source_axis: str,
    target_axis: str,
    rotation: np.ndarray,
    scale: float,
) -> list[tuple[float, float]] | None:
    source_basis = _extruded_profile_basis(source_axis)
    target_basis = _extruded_profile_basis(target_axis)
    if source_basis is None or target_basis is None:
        return None
    source_u, source_v, _ = source_basis
    target_u, target_v, _ = target_basis
    if not isinstance(polygon, (list, tuple)):
        return None
    transformed: list[tuple[float, float]] = []
    for point in polygon:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            return None
        relative = source_u * float(point[0]) + source_v * float(point[1])
        updated = scale * (rotation @ relative)
        transformed.append((float(np.dot(updated, target_u)), float(np.dot(updated, target_v))))
    if float(np.linalg.det(rotation)) < 0.0:
        transformed.reverse()
    return transformed


def _radial_2d_polygon(points: Any, *, tolerance: float = 1e-4) -> bool:
    if not isinstance(points, (list, tuple)) or len(points) < 6:
        return False
    radii: list[float] = []
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            return False
        radius = math.hypot(float(point[0]), float(point[1]))
        if radius <= 1e-9:
            return False
        radii.append(radius)
    mean = sum(radii) / len(radii)
    return all(abs(radius - mean) <= max(tolerance, mean * 0.02) for radius in radii)


def _scale_2d_polygon(points: Any, scale: float) -> list[tuple[float, float]] | None:
    if not isinstance(points, (list, tuple)):
        return None
    scaled: list[tuple[float, float]] = []
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            return None
        scaled.append((float(point[0]) * scale, float(point[1]) * scale))
    return scaled


def _scale_dimension_metadata(value: Any, scale: float) -> Any:
    if isinstance(value, dict):
        scaled: dict[str, Any] = {}
        for key, item in value.items():
            if isinstance(key, str) and key.endswith("_cm") and isinstance(item, (int, float)) and not isinstance(item, bool):
                scaled[key] = float(item) * scale
            else:
                scaled[key] = _scale_dimension_metadata(item, scale)
        return scaled
    if isinstance(value, list):
        return [_scale_dimension_metadata(item, scale) for item in value]
    if isinstance(value, tuple):
        return tuple(_scale_dimension_metadata(item, scale) for item in value)
    return value


def _transform_shape_primitive_metadata_record(
    metadata: dict[str, Any],
    matrix: np.ndarray,
    *,
    transform_semantic_sources: bool = True,
) -> dict[str, Any] | None:
    transform = _axis_aligned_uniform_transform(matrix)
    if transform is None:
        return None
    rotation, translation, input_to_output, input_signs, scale = transform
    record = deepcopy(metadata)
    semantic_metadata_transformed = False
    try:
        record["center"] = _transformed_point(
            record.get("center", (0.0, 0.0, 0.0)),
            rotation=rotation,
            translation=translation,
            scale=scale,
        )
    except (TypeError, ValueError):
        return None

    primitive_type = str(record.get("primitive_type") or "")
    identity_rotation = _is_identity_axis_transform(input_to_output, input_signs)
    if primitive_type == "box":
        extents = record.get("extents")
        if isinstance(extents, (list, tuple)) and len(extents) == 3:
            transformed_extents = [0.0, 0.0, 0.0]
            for input_axis, output_axis in enumerate(input_to_output):
                transformed_extents[output_axis] = float(extents[input_axis]) * scale
            record["extents"] = transformed_extents
    elif primitive_type == "sphere":
        if record.get("radius") is not None:
            record["radius"] = float(record["radius"]) * scale
    elif primitive_type in {"cylinder", "torus", "revolved_profile"}:
        source_axis = str(record.get("axis") or "y")
        if source_axis not in {"x", "y", "z"}:
            return None
        source_axis_index = _axis_index(source_axis)
        record["axis"] = _axis_name(input_to_output[source_axis_index])
        if primitive_type == "cylinder":
            if record.get("radius") is not None:
                record["radius"] = float(record["radius"]) * scale
            if record.get("height") is not None:
                record["height"] = float(record["height"]) * scale
        elif primitive_type == "torus":
            if record.get("major_radius") is not None:
                record["major_radius"] = float(record["major_radius"]) * scale
            if record.get("minor_radius") is not None:
                record["minor_radius"] = float(record["minor_radius"]) * scale
        else:
            profile = record.get("profile_points")
            if not isinstance(profile, (list, tuple)):
                return None
            flipped = input_signs[source_axis_index] < 0
            transformed_profile = [
                (
                    (-float(point[0]) if flipped else float(point[0])) * scale,
                    float(point[1]) * scale,
                )
                for point in profile
                if isinstance(point, (list, tuple)) and len(point) == 2
            ]
            if len(transformed_profile) != len(profile):
                return None
            record["profile_points"] = list(reversed(transformed_profile)) if flipped else transformed_profile
    elif primitive_type == "extruded_profile":
        source_axis = str(record.get("axis") or "z")
        if source_axis not in {"x", "y", "z"}:
            return None
        target_axis = _axis_name(input_to_output[_axis_index(source_axis)])
        polygon = _transformed_extruded_profile_polygon(
            record.get("profile_polygon"),
            source_axis=source_axis,
            target_axis=target_axis,
            rotation=rotation,
            scale=scale,
        )
        if polygon is None:
            return None
        record["axis"] = target_axis
        record["profile_polygon"] = polygon
        if record.get("extrude_height") is not None:
            record["extrude_height"] = float(record["extrude_height"]) * scale
    elif primitive_type == "subdivision_box":
        extents = record.get("extents")
        radii = record.get("corner_radii")
        if not isinstance(extents, (list, tuple)) or len(extents) != 3:
            return None
        if not isinstance(radii, (list, tuple)) or len(radii) != 8:
            return None
        transformed_extents = [0.0, 0.0, 0.0]
        for input_axis, output_axis in enumerate(input_to_output):
            transformed_extents[output_axis] = float(extents[input_axis]) * scale
        transformed_radii = [0.0] * 8
        for index, radius in enumerate(radii):
            input_sign_tuple = (
                -1 if (index & 1) == 0 else 1,
                -1 if (index & 2) == 0 else 1,
                -1 if (index & 4) == 0 else 1,
            )
            output_signs = [0, 0, 0]
            for input_axis, output_axis in enumerate(input_to_output):
                output_signs[output_axis] = input_sign_tuple[input_axis] * input_signs[input_axis]
            output_index = (
                (1 if output_signs[0] > 0 else 0)
                | (2 if output_signs[1] > 0 else 0)
                | (4 if output_signs[2] > 0 else 0)
            )
            transformed_radii[output_index] = float(radius) * scale
        record["extents"] = transformed_extents
        record["corner_radii"] = transformed_radii
    elif primitive_type == "swept_profile":
        cross_section = record.get("cross_section")
        if not identity_rotation and not _radial_2d_polygon(cross_section):
            return None
        scaled_section = _scale_2d_polygon(cross_section, scale)
        if scaled_section is None:
            return None
        path = record.get("sweep_path")
        if not isinstance(path, (list, tuple)):
            return None
        record["cross_section"] = scaled_section
        record["sweep_path"] = [
            _transformed_vector(point, rotation=rotation, scale=scale)
            for point in path
        ]
    elif primitive_type == "lofted_solid":
        sections = record.get("cross_sections")
        centers = record.get("section_centers")
        if not isinstance(sections, (list, tuple)) or not isinstance(centers, (list, tuple)):
            return None
        if not identity_rotation and not all(_radial_2d_polygon(section) for section in sections):
            return None
        scaled_sections: list[list[tuple[float, float]]] = []
        for section in sections:
            scaled = _scale_2d_polygon(section, scale)
            if scaled is None:
                return None
            scaled_sections.append(scaled)
        record["cross_sections"] = scaled_sections
        record["section_centers"] = [
            _transformed_vector(point, rotation=rotation, scale=scale)
            for point in centers
        ]
    elif primitive_type in {"heightfield", "terrain_patch"}:
        if not identity_rotation:
            return None
        bounds = record.get("bounds_xy")
        if isinstance(bounds, (list, tuple)) and len(bounds) == 4:
            record["bounds_xy"] = [float(value) * scale for value in bounds]
        if record.get("vertical_scale") is not None:
            record["vertical_scale"] = float(record["vertical_scale"]) * scale
    elif primitive_type in {
        "sdf_mesh",
        "sdf_metaball_cluster",
        "terrain_mesh",
        "kernel_primitive_mesh",
        "instance_mesh",
        "polybevel_mesh",
        "profile_mesh",
        "construction_feature_mesh",
        "edge_control_mesh",
        "hull_mesh",
        "minkowski_mesh",
        "subdivision_mesh",
        "remesh_mesh",
        "deform_mesh",
        "boolean_mesh",
        "component_assembly_mesh",
    }:
        vertices = record.get("mesh_vertices")
        if not isinstance(vertices, (list, tuple)):
            return None
        record["mesh_vertices"] = [
            _transformed_vector(vertex, rotation=rotation, scale=scale)
            for vertex in vertices
        ]

    if transform_semantic_sources and isinstance(record.get("semantic_metadata"), dict):
        transformed_semantic = _transform_semantic_source_metadata(
            record["semantic_metadata"],
            matrix,
        )
        if transformed_semantic is not None:
            record["semantic_metadata"] = transformed_semantic
            semantic_metadata_transformed = True

    for key, value in list(record.items()):
        if key == "semantic_metadata" and semantic_metadata_transformed:
            continue
        if key.startswith("v2_") or key in {"boolean_seam_groups", "bevel_seam_groups", "hard_edge_groups", "semantic_metadata"}:
            record[key] = _scale_dimension_metadata(value, scale)
    return record


def _transform_semantic_source_metadata(
    metadata: dict[str, Any],
    matrix: np.ndarray,
) -> dict[str, Any] | None:
    transform = _axis_aligned_uniform_transform(matrix)
    if transform is None:
        return None
    *_, scale = transform
    transformed = _scale_dimension_metadata(metadata, scale)

    source = metadata.get("source_shape_primitive")
    if isinstance(source, dict):
        transformed_source = _transform_shape_primitive_metadata_record(
            source,
            matrix,
            transform_semantic_sources=False,
        )
        if transformed_source is None:
            transformed.pop("source_shape_primitive", None)
        else:
            transformed["source_shape_primitive"] = transformed_source

    sources = metadata.get("source_shape_primitives")
    if isinstance(sources, list) and sources:
        transformed_sources: list[dict[str, Any]] = []
        for item in sources:
            if not isinstance(item, dict):
                transformed_sources = []
                break
            transformed_item = _transform_shape_primitive_metadata_record(
                item,
                matrix,
                transform_semantic_sources=False,
            )
            if transformed_item is None:
                transformed_sources = []
                break
            transformed_sources.append(transformed_item)
        if transformed_sources:
            transformed["source_shape_primitives"] = transformed_sources
        else:
            transformed.pop("source_shape_primitives", None)

    return transformed


def _transform_shape_primitive_metadata(mesh: trimesh.Trimesh, matrix: np.ndarray) -> None:
    metadata = _shape_primitive_metadata(mesh)
    if not metadata:
        return
    transformed = _transform_shape_primitive_metadata_record(metadata, matrix)
    if transformed is None:
        mesh.metadata.pop(_SHAPE_PRIMITIVE_METADATA_KEY, None)
        return
    mesh.metadata[_SHAPE_PRIMITIVE_METADATA_KEY] = transformed


def _transform_box_metadata(mesh: trimesh.Trimesh, matrix: np.ndarray) -> None:
    if _boss_state_from_mesh(mesh) is not None:
        mesh.metadata.pop(_PRIMITIVE_METADATA_KEY, None)
        return
    if _profile_cut_state_from_mesh(mesh) is not None:
        mesh.metadata.pop(_PRIMITIVE_METADATA_KEY, None)
        return
    bounds = _box_bounds_from_metadata(mesh)
    if bounds is None:
        return
    linear = matrix[:3, :3]
    if (
        _axis_aligned_uniform_transform(matrix) is None
        and not np.allclose(linear, np.diag(np.diagonal(linear)), atol=1e-9)
    ):
        mesh.metadata.pop(_PRIMITIVE_METADATA_KEY, None)
        return
    bmin, bmax = bounds
    corners = np.asarray(
        [
            [x, y, z, 1.0]
            for x in (bmin[0], bmax[0])
            for y in (bmin[1], bmax[1])
            for z in (bmin[2], bmax[2])
        ],
        dtype=np.float64,
    )
    transformed = (matrix @ corners.T).T[:, :3]
    _record_box_metadata(
        mesh,
        bounds_min=np.min(transformed, axis=0),
        bounds_max=np.max(transformed, axis=0),
    )


def _transform_cylinder_metadata(mesh: trimesh.Trimesh, matrix: np.ndarray) -> None:
    metadata = mesh.metadata.get(_PRIMITIVE_METADATA_KEY)
    if not isinstance(metadata, dict) or metadata.get("kind") != "cylinder":
        return
    transform = _axis_aligned_uniform_transform(matrix)
    if transform is None:
        mesh.metadata.pop(_PRIMITIVE_METADATA_KEY, None)
        return
    rotation, translation, input_to_output, _, scale = transform
    try:
        center = np.asarray(metadata["center"], dtype=np.float64)
        radius = float(metadata["radius"])
        height = float(metadata["height"])
        axis = str(metadata.get("axis") or "y")
    except (KeyError, TypeError, ValueError):
        mesh.metadata.pop(_PRIMITIVE_METADATA_KEY, None)
        return
    if center.shape != (3,) or axis not in {"x", "y", "z"}:
        mesh.metadata.pop(_PRIMITIVE_METADATA_KEY, None)
        return
    metadata["center"] = [
        float(value)
        for value in (scale * (rotation @ center) + translation)
    ]
    metadata["axis"] = _axis_name(input_to_output[_axis_index(axis)])
    metadata["radius"] = float(radius * scale)
    metadata["height"] = float(height * scale)
    mesh.metadata[_PRIMITIVE_METADATA_KEY] = metadata


def _transform_boss_state_metadata(mesh: trimesh.Trimesh, matrix: np.ndarray) -> None:
    state = _boss_state_from_mesh(mesh)
    if state is None:
        return

    def drop_state() -> None:
        mesh.metadata.pop(_BOSS_STATE_METADATA_KEY, None)
        mesh.metadata.pop(_PRIMITIVE_METADATA_KEY, None)
        mesh.metadata.pop(_SHAPE_PRIMITIVE_METADATA_KEY, None)

    transform = _axis_aligned_uniform_transform(matrix)
    if transform is None:
        drop_state()
        return
    rotation, translation, input_to_output, input_signs, scale = transform
    try:
        cut_axis = int(state["cut_axis"])
        plane_axes = tuple(int(value) for value in state["plane_axes"])
        box_min = np.asarray(state["box_min"], dtype=np.float64)
        box_max = np.asarray(state["box_max"], dtype=np.float64)
        side = int(state["side"])
    except (KeyError, TypeError, ValueError):
        drop_state()
        return
    if cut_axis not in {0, 1, 2} or len(plane_axes) != 2 or set(plane_axes) != ({0, 1, 2} - {cut_axis}):
        drop_state()
        return
    bosses = state.get("bosses")
    if not isinstance(bosses, list):
        drop_state()
        return

    new_cut_axis = int(input_to_output[cut_axis])
    new_plane_axes = tuple(index for index in range(3) if index != new_cut_axis)
    cut_axis_sign = int(input_signs[cut_axis])
    new_side = int(side * cut_axis_sign)

    def transform_point(point: np.ndarray) -> np.ndarray:
        return scale * (rotation @ point) + translation

    def transform_bounds(
        bounds_min: np.ndarray,
        bounds_max: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray] | None:
        if bounds_min.shape != (3,) or bounds_max.shape != (3,):
            return None
        corners = np.asarray(
            [
                [x, y, z]
                for x in (bounds_min[0], bounds_max[0])
                for y in (bounds_min[1], bounds_max[1])
                for z in (bounds_min[2], bounds_max[2])
            ],
            dtype=np.float64,
        )
        transformed = np.asarray([transform_point(corner) for corner in corners], dtype=np.float64)
        out_min = np.min(transformed, axis=0)
        out_max = np.max(transformed, axis=0)
        if bool(np.any(out_max <= out_min)):
            return None
        return out_min, out_max

    def transform_plane_point(point: tuple[float, float]) -> list[float]:
        coord = np.zeros(3, dtype=np.float64)
        coord[plane_axes[0]] = float(point[0])
        coord[plane_axes[1]] = float(point[1])
        transformed = transform_point(coord)
        return [float(transformed[new_plane_axes[0]]), float(transformed[new_plane_axes[1]])]

    def transform_axial(value: float) -> float:
        return float(translation[new_cut_axis] + float(cut_axis_sign) * scale * float(value))

    transformed_bounds = transform_bounds(box_min, box_max)
    if transformed_bounds is None:
        drop_state()
        return
    transformed_bosses: list[dict[str, Any]] = []
    for boss in bosses:
        if not isinstance(boss, dict):
            drop_state()
            return
        item = dict(boss)
        if "center" in item:
            try:
                center = np.asarray(item["center"], dtype=np.float64)
            except (TypeError, ValueError):
                drop_state()
                return
            if center.shape != (3,):
                drop_state()
                return
            item["center"] = [float(value) for value in transform_point(center)]
        try:
            plane_center = np.asarray(item["plane_center"], dtype=np.float64)
            base_axial = float(item["base_axial"])
            outer_axial = float(item["outer_axial"])
        except (KeyError, TypeError, ValueError):
            drop_state()
            return
        if plane_center.shape != (2,):
            drop_state()
            return
        item["plane_center"] = transform_plane_point((float(plane_center[0]), float(plane_center[1])))
        item["base_axial"] = transform_axial(base_axial)
        item["outer_axial"] = transform_axial(outer_axial)
        if "radius" in item and item["radius"] is not None:
            try:
                item["radius"] = float(item["radius"]) * scale
            except (TypeError, ValueError):
                drop_state()
                return
        if "rings" in item:
            try:
                rings = [
                    (float(ring[0]), float(ring[1]))
                    for ring in item["rings"]
                ]
            except (TypeError, ValueError, IndexError):
                drop_state()
                return
            item["rings"] = [
                [transform_axial(axial), float(radius) * scale]
                for axial, radius in rings
            ]
        if "profile_points" in item:
            try:
                profile_points = [
                    (float(point[0]), float(point[1]))
                    for point in item["profile_points"]
                ]
            except (TypeError, ValueError, IndexError):
                drop_state()
                return
            item["profile_points"] = [transform_plane_point(point) for point in profile_points]
        if "profile_rings" in item:
            try:
                profile_rings = [
                    [
                        (float(point[0]), float(point[1]))
                        for point in ring
                    ]
                    for ring in item["profile_rings"]
                ]
            except (TypeError, ValueError, IndexError):
                drop_state()
                return
            item["profile_rings"] = [
                [transform_plane_point(point) for point in ring]
                for ring in profile_rings
            ]
        if "profile_holes" in item:
            try:
                profile_holes = [
                    [
                        (float(point[0]), float(point[1]))
                        for point in hole
                    ]
                    for hole in item["profile_holes"]
                ]
            except (TypeError, ValueError, IndexError):
                drop_state()
                return
            item["profile_holes"] = [
                [transform_plane_point(point) for point in hole]
                for hole in profile_holes
            ]
        transformed_bosses.append(item)
    transformed_cuts: list[dict[str, Any]] = []
    cuts = state.get("through_cuts", [])
    if cuts:
        if not isinstance(cuts, list):
            drop_state()
            return
        for cut in cuts:
            if not isinstance(cut, dict):
                drop_state()
                return
            item = dict(cut)
            has_position = False
            if "center" in item:
                try:
                    center = np.asarray(item["center"], dtype=np.float64)
                except (TypeError, ValueError):
                    drop_state()
                    return
                if center.shape != (3,):
                    drop_state()
                    return
                item["center"] = [float(value) for value in transform_point(center)]
                has_position = True
            if "profile_points" in item:
                try:
                    profile_points = [
                        (float(point[0]), float(point[1]))
                        for point in item["profile_points"]
                    ]
                except (TypeError, ValueError, IndexError):
                    drop_state()
                    return
                item["profile_points"] = [transform_plane_point(point) for point in profile_points]
                has_position = True
            if "plane_center" in item:
                try:
                    plane_center = np.asarray(item["plane_center"], dtype=np.float64)
                except (TypeError, ValueError):
                    drop_state()
                    return
                if plane_center.shape != (2,):
                    drop_state()
                    return
                item["plane_center"] = transform_plane_point((float(plane_center[0]), float(plane_center[1])))
                has_position = True
            if not has_position:
                drop_state()
                return
            if "rings" in item and item["rings"] is not None:
                try:
                    rings = [
                        (float(ring[0]), float(ring[1]))
                        for ring in item["rings"]
                    ]
                except (TypeError, ValueError, IndexError):
                    drop_state()
                    return
                transformed_rings = [
                    [transform_axial(axial), float(radius) * scale]
                    for axial, radius in rings
                ]
                if any(
                    transformed_rings[index][0] > transformed_rings[index + 1][0] + 1e-9
                    for index in range(len(transformed_rings) - 1)
                ):
                    transformed_rings = list(reversed(transformed_rings))
                if any(
                    transformed_rings[index][0] > transformed_rings[index + 1][0] + 1e-9
                    for index in range(len(transformed_rings) - 1)
                ):
                    drop_state()
                    return
                item["rings"] = transformed_rings
            transformed_cuts.append(item)
    new_box_min, new_box_max = transformed_bounds
    state["box_min"] = [float(value) for value in new_box_min]
    state["box_max"] = [float(value) for value in new_box_max]
    state["cut_axis"] = int(new_cut_axis)
    state["plane_axes"] = [int(axis) for axis in new_plane_axes]
    state["side"] = int(new_side)
    state["bosses"] = transformed_bosses
    if transformed_cuts:
        state["through_cuts"] = transformed_cuts
    elif "through_cuts" in state:
        state.pop("through_cuts", None)
    mesh.metadata[_BOSS_STATE_METADATA_KEY] = state
    mesh.metadata.pop(_PRIMITIVE_METADATA_KEY, None)
    mesh.metadata.pop(_SHAPE_PRIMITIVE_METADATA_KEY, None)


def _transform_profile_cut_state_metadata(mesh: trimesh.Trimesh, matrix: np.ndarray) -> None:
    state = _profile_cut_state_from_mesh(mesh)
    if state is None:
        return

    def drop_state() -> None:
        mesh.metadata.pop(_PROFILE_CUT_STATE_METADATA_KEY, None)
        mesh.metadata.pop(_PRIMITIVE_METADATA_KEY, None)
        mesh.metadata.pop(_SHAPE_PRIMITIVE_METADATA_KEY, None)

    transform = _axis_aligned_uniform_transform(matrix)
    if transform is None:
        drop_state()
        return
    rotation, translation, input_to_output, input_signs, scale = transform
    try:
        cut_axis = int(state["cut_axis"])
        plane_axes = tuple(int(value) for value in state["plane_axes"])
        box_min = np.asarray(state["box_min"], dtype=np.float64)
        box_max = np.asarray(state["box_max"], dtype=np.float64)
    except (KeyError, TypeError, ValueError):
        drop_state()
        return
    if cut_axis not in {0, 1, 2} or len(plane_axes) != 2 or set(plane_axes) != ({0, 1, 2} - {cut_axis}):
        drop_state()
        return
    cuts = state.get("cuts")
    if not isinstance(cuts, list):
        drop_state()
        return

    new_cut_axis = int(input_to_output[cut_axis])
    new_plane_axes = tuple(index for index in range(3) if index != new_cut_axis)
    cut_axis_sign = int(input_signs[cut_axis])

    def transform_point(point: np.ndarray) -> np.ndarray:
        return scale * (rotation @ point) + translation

    def transform_bounds(
        bounds_min: np.ndarray,
        bounds_max: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray] | None:
        if bounds_min.shape != (3,) or bounds_max.shape != (3,):
            return None
        corners = np.asarray(
            [
                [x, y, z]
                for x in (bounds_min[0], bounds_max[0])
                for y in (bounds_min[1], bounds_max[1])
                for z in (bounds_min[2], bounds_max[2])
            ],
            dtype=np.float64,
        )
        transformed = np.asarray([transform_point(corner) for corner in corners], dtype=np.float64)
        out_min = np.min(transformed, axis=0)
        out_max = np.max(transformed, axis=0)
        if bool(np.any(out_max <= out_min)):
            return None
        return out_min, out_max

    def transform_plane_point(point: tuple[float, float]) -> list[float]:
        coord = np.zeros(3, dtype=np.float64)
        coord[plane_axes[0]] = float(point[0])
        coord[plane_axes[1]] = float(point[1])
        transformed = transform_point(coord)
        return [float(transformed[new_plane_axes[0]]), float(transformed[new_plane_axes[1]])]

    def transform_axial(value: float) -> float:
        return float(translation[new_cut_axis] + float(cut_axis_sign) * scale * float(value))

    transformed_bounds = transform_bounds(box_min, box_max)
    if transformed_bounds is None:
        drop_state()
        return
    transformed_cuts: list[dict[str, Any]] = []
    for cut in cuts:
        if not isinstance(cut, dict):
            drop_state()
            return
        item = dict(cut)
        has_position = False
        if "center" in item:
            try:
                center = np.asarray(item["center"], dtype=np.float64)
            except (TypeError, ValueError):
                drop_state()
                return
            if center.shape != (3,):
                drop_state()
                return
            item["center"] = [float(value) for value in transform_point(center)]
            has_position = True
        if "profile_points" in item:
            try:
                profile_points = [
                    (float(point[0]), float(point[1]))
                    for point in item["profile_points"]
                ]
            except (TypeError, ValueError, IndexError):
                drop_state()
                return
            item["profile_points"] = [transform_plane_point(point) for point in profile_points]
            has_position = True
        if "plane_center" in item:
            try:
                plane_center = np.asarray(item["plane_center"], dtype=np.float64)
            except (TypeError, ValueError):
                drop_state()
                return
            if plane_center.shape != (2,):
                drop_state()
                return
            item["plane_center"] = transform_plane_point(
                (float(plane_center[0]), float(plane_center[1]))
            )
            has_position = True
        if not has_position:
            drop_state()
            return
        if "rings" in item and item["rings"] is not None:
            try:
                rings = [
                    (float(ring[0]), float(ring[1]))
                    for ring in item["rings"]
                ]
            except (TypeError, ValueError, IndexError):
                drop_state()
                return
            transformed_rings = [
                [transform_axial(axial), float(radius) * scale]
                for axial, radius in rings
            ]
            if any(
                transformed_rings[index][0] > transformed_rings[index + 1][0] + 1e-9
                for index in range(len(transformed_rings) - 1)
            ):
                transformed_rings = list(reversed(transformed_rings))
            if any(
                transformed_rings[index][0] > transformed_rings[index + 1][0] + 1e-9
                for index in range(len(transformed_rings) - 1)
            ):
                drop_state()
                return
            item["rings"] = transformed_rings
        if "floor_axial_cm" in item:
            try:
                item["floor_axial_cm"] = transform_axial(float(item["floor_axial_cm"]))
            except (TypeError, ValueError):
                drop_state()
                return
        if "bevel_width" in item and item["bevel_width"] is not None:
            try:
                item["bevel_width"] = float(item["bevel_width"]) * scale
            except (TypeError, ValueError):
                drop_state()
                return
        if cut_axis_sign < 0 and item.get("open_side") in {"positive", "negative"}:
            item["open_side"] = "negative" if item["open_side"] == "positive" else "positive"
        transformed_cuts.append(item)
    new_box_min, new_box_max = transformed_bounds
    state["box_min"] = [float(value) for value in new_box_min]
    state["box_max"] = [float(value) for value in new_box_max]
    state["cut_axis"] = int(new_cut_axis)
    state["plane_axes"] = [int(axis) for axis in new_plane_axes]
    state["cuts"] = transformed_cuts
    mesh.metadata[_PROFILE_CUT_STATE_METADATA_KEY] = state
    mesh.metadata.pop(_PRIMITIVE_METADATA_KEY, None)
    mesh.metadata.pop(_SHAPE_PRIMITIVE_METADATA_KEY, None)


def _axis_values(*values: float) -> list[float]:
    out: list[float] = []
    for value in sorted(float(item) for item in values):
        if out and abs(out[-1] - value) <= 1e-9:
            continue
        out.append(value)
    return out


def _mesh_from_axis_aligned_box_cells(
    cells: list[tuple[np.ndarray, np.ndarray]],
) -> trimesh.Trimesh:
    vertices: list[tuple[float, float, float]] = []
    vertex_index: dict[tuple[float, float, float], int] = {}
    faces: list[list[int]] = []

    def add_vertex(coord: tuple[float, float, float]) -> int:
        key = tuple(round(float(value), 9) for value in coord)
        existing = vertex_index.get(key)
        if existing is not None:
            return existing
        vertex_index[key] = len(vertices)
        vertices.append(tuple(float(value) for value in coord))
        return len(vertices) - 1

    def has_neighbor(
        cell_min: np.ndarray,
        cell_max: np.ndarray,
        axis: int,
        side: int,
    ) -> bool:
        for other_min, other_max in cells:
            same_other_axes = all(
                axis_index == axis
                or (
                    abs(float(other_min[axis_index]) - float(cell_min[axis_index])) <= 1e-9
                    and abs(float(other_max[axis_index]) - float(cell_max[axis_index])) <= 1e-9
                )
                for axis_index in range(3)
            )
            if not same_other_axes:
                continue
            if side < 0 and abs(float(other_max[axis]) - float(cell_min[axis])) <= 1e-9:
                return True
            if side > 0 and abs(float(other_min[axis]) - float(cell_max[axis])) <= 1e-9:
                return True
        return False

    def add_quad(coords: tuple[tuple[float, float, float], ...]) -> None:
        quad = [add_vertex(coord) for coord in coords]
        faces.append([quad[0], quad[1], quad[2]])
        faces.append([quad[0], quad[2], quad[3]])

    for cell_min, cell_max in cells:
        x0, y0, z0 = (float(value) for value in cell_min)
        x1, y1, z1 = (float(value) for value in cell_max)
        if not has_neighbor(cell_min, cell_max, 0, -1):
            add_quad(((x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)))
        if not has_neighbor(cell_min, cell_max, 0, 1):
            add_quad(((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)))
        if not has_neighbor(cell_min, cell_max, 1, -1):
            add_quad(((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)))
        if not has_neighbor(cell_min, cell_max, 1, 1):
            add_quad(((x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0)))
        if not has_neighbor(cell_min, cell_max, 2, -1):
            add_quad(((x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)))
        if not has_neighbor(cell_min, cell_max, 2, 1):
            add_quad(((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)))

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    mesh.remove_unreferenced_vertices()
    try:
        mesh.update_faces(mesh.unique_faces())
        mesh.update_faces(mesh.nondegenerate_faces())
    except (AttributeError, IndexError, TypeError, ValueError):
        pass
    mesh.merge_vertices()
    mesh.fix_normals()
    return mesh


def _box_polybevel_width(mesh: trimesh.Trimesh) -> float:
    primitive = _resolved_shape_primitive_metadata(mesh)
    modifier = primitive.get("v2_polybevel_modifier")
    if not isinstance(modifier, dict):
        return 0.0
    try:
        return max(0.0, float(modifier.get("width_cm") or 0.0))
    except (TypeError, ValueError):
        return 0.0


def _box_polybevel_segments(mesh: trimesh.Trimesh) -> int:
    primitive = _resolved_shape_primitive_metadata(mesh)
    modifier = primitive.get("v2_polybevel_modifier")
    if not isinstance(modifier, dict):
        return 1
    try:
        return max(1, int(modifier.get("segments") or 1))
    except (TypeError, ValueError):
        return 1


def _mesh_from_open_box_shell(
    *,
    outer_min: np.ndarray,
    outer_max: np.ndarray,
    inner_min: np.ndarray,
    inner_max: np.ndarray,
    open_axis: int,
    open_side: int,
    bevel_width: float,
    bevel_segments: int = 1,
) -> tuple[trimesh.Trimesh, dict[str, Any]] | None:
    try:
        from shapely.geometry import Polygon
        from shapely.ops import triangulate
    except (ImportError, ModuleNotFoundError):
        return None
    if open_axis not in {0, 1, 2} or open_side not in {-1, 1}:
        return None
    plane_axes = tuple(index for index in range(3) if index != open_axis)
    if len(plane_axes) != 2:
        return None
    outer_u0 = float(outer_min[plane_axes[0]])
    outer_u1 = float(outer_max[plane_axes[0]])
    outer_v0 = float(outer_min[plane_axes[1]])
    outer_v1 = float(outer_max[plane_axes[1]])
    core_u0 = float(inner_min[plane_axes[0]])
    core_u1 = float(inner_max[plane_axes[0]])
    core_v0 = float(inner_min[plane_axes[1]])
    core_v1 = float(inner_max[plane_axes[1]])
    if not (outer_u0 < core_u0 < core_u1 < outer_u1 and outer_v0 < core_v0 < core_v1 < outer_v1):
        return None
    low = float(outer_min[open_axis])
    high = float(outer_max[open_axis])
    if open_side > 0:
        open_axial = high
        closed_axial = low
        floor_axial = float(inner_min[open_axis])
        if not (low < floor_axial < high):
            return None
    else:
        open_axial = low
        closed_axial = high
        floor_axial = float(inner_max[open_axis])
        if not (low < floor_axial < high):
            return None
    cavity_depth = abs(float(open_axial - floor_axial))
    wall_clearance = min(core_u0 - outer_u0, outer_u1 - core_u1, core_v0 - outer_v0, outer_v1 - core_v1)
    bevel = min(max(0.0, float(bevel_width)), max(0.0, wall_clearance - 1e-6), cavity_depth * 0.45)
    bevel_applied = bevel > 1e-9
    if bevel_applied:
        expanded_u0 = core_u0 - bevel
        expanded_u1 = core_u1 + bevel
        expanded_v0 = core_v0 - bevel
        expanded_v1 = core_v1 + bevel
        shoulder_axial = float(open_axial - open_side * bevel)
    else:
        expanded_u0 = core_u0
        expanded_u1 = core_u1
        expanded_v0 = core_v0
        expanded_v1 = core_v1
        shoulder_axial = float(open_axial)

    outer_rect = [
        (outer_u0, outer_v0),
        (outer_u1, outer_v0),
        (outer_u1, outer_v1),
        (outer_u0, outer_v1),
    ]
    core_rect = [
        (core_u0, core_v0),
        (core_u1, core_v0),
        (core_u1, core_v1),
        (core_u0, core_v1),
    ]
    expanded_rect = [
        (expanded_u0, expanded_v0),
        (expanded_u1, expanded_v0),
        (expanded_u1, expanded_v1),
        (expanded_u0, expanded_v1),
    ]
    outer_polygon = Polygon(outer_rect)
    core_polygon = Polygon(core_rect)
    rim_polygon = Polygon(outer_rect, [expanded_rect])
    if (
        outer_polygon.is_empty
        or core_polygon.is_empty
        or rim_polygon.is_empty
        or float(core_polygon.area) <= 1e-9
        or float(rim_polygon.area) <= 1e-9
        or not outer_polygon.covers(Polygon(expanded_rect))
    ):
        return None

    vertices: list[tuple[float, float, float]] = []
    vertex_index: dict[tuple[int, int, int], int] = {}
    faces: list[list[int]] = []

    def add_vertex(point: tuple[float, float], axial: float) -> int:
        coord = [0.0, 0.0, 0.0]
        coord[open_axis] = float(axial)
        coord[plane_axes[0]] = float(point[0])
        coord[plane_axes[1]] = float(point[1])
        key = tuple(int(round(value * 1_000_000)) for value in coord)
        existing = vertex_index.get(key)
        if existing is not None:
            return existing
        vertex_index[key] = len(vertices)
        vertices.append((coord[0], coord[1], coord[2]))
        return len(vertices) - 1

    def add_cap(polygon: Any, axial: float, *, reverse: bool) -> int:
        count = 0
        try:
            vertices_2d, faces_2d = trimesh.creation.triangulate_polygon(
                polygon,
                force_vertices=True,
            )
        except (AttributeError, ValueError, RuntimeError, ImportError, ModuleNotFoundError):
            for triangle in triangulate(polygon):
                if float(triangle.area) <= 1e-9 or not polygon.covers(triangle.representative_point()):
                    continue
                coords = [(float(x), float(y)) for x, y in list(triangle.exterior.coords)[:3]]
                tri = [add_vertex(point, axial) for point in coords]
                faces.append([tri[0], tri[2], tri[1]] if reverse else tri)
                count += 1
            return count
        for face in faces_2d:
            coords = [
                (float(vertices_2d[int(index)][0]), float(vertices_2d[int(index)][1]))
                for index in face[:3]
            ]
            if len(coords) < 3:
                continue
            tri = [add_vertex(point, axial) for point in coords]
            faces.append([tri[0], tri[2], tri[1]] if reverse else tri)
            count += 1
        return count

    def add_wall(
        lower_ring: list[tuple[float, float]],
        upper_ring: list[tuple[float, float]],
        *,
        lower_axial: float,
        upper_axial: float,
        reverse: bool,
    ) -> int:
        if len(lower_ring) != len(upper_ring) or len(lower_ring) < 3:
            return 0
        count = 0
        for index, lower_point in enumerate(lower_ring):
            next_index = (index + 1) % len(lower_ring)
            quad = [
                add_vertex(lower_point, lower_axial),
                add_vertex(lower_ring[next_index], lower_axial),
                add_vertex(upper_ring[next_index], upper_axial),
                add_vertex(upper_ring[index], upper_axial),
            ]
            faces.append([quad[0], quad[1], quad[2]] if not reverse else [quad[0], quad[2], quad[1]])
            faces.append([quad[0], quad[2], quad[3]] if not reverse else [quad[0], quad[3], quad[2]])
            count += 2
        return count

    cap_triangle_count = 0
    cap_triangle_count += add_cap(outer_polygon, closed_axial, reverse=open_side > 0)
    cap_triangle_count += add_cap(rim_polygon, open_axial, reverse=open_side < 0)
    cap_triangle_count += add_cap(core_polygon, floor_axial, reverse=open_side < 0)
    outer_wall_face_count = add_wall(
        outer_rect,
        outer_rect,
        lower_axial=low,
        upper_axial=high,
        reverse=False,
    )
    inner_low = min(float(floor_axial), float(shoulder_axial))
    inner_high = max(float(floor_axial), float(shoulder_axial))
    inner_wall_face_count = 0
    if inner_high > inner_low + 1e-9:
        inner_wall_face_count = add_wall(
            core_rect,
            core_rect,
            lower_axial=inner_low,
            upper_axial=inner_high,
            reverse=True,
        )
    chamfer_face_count = 0
    if bevel_applied:
        segment_count = max(1, int(bevel_segments))

        def lerp_ring(
            start: list[tuple[float, float]],
            end: list[tuple[float, float]],
            t: float,
        ) -> list[tuple[float, float]]:
            return [
                (
                    float(left[0]) + (float(right[0]) - float(left[0])) * t,
                    float(left[1]) + (float(right[1]) - float(left[1])) * t,
                )
                for left, right in zip(start, end, strict=True)
            ]

        if open_side > 0:
            for segment in range(segment_count):
                t0 = segment / segment_count
                t1 = (segment + 1) / segment_count
                chamfer_face_count += add_wall(
                    lerp_ring(core_rect, expanded_rect, t0),
                    lerp_ring(core_rect, expanded_rect, t1),
                    lower_axial=shoulder_axial + (open_axial - shoulder_axial) * t0,
                    upper_axial=shoulder_axial + (open_axial - shoulder_axial) * t1,
                    reverse=True,
                )
        else:
            for segment in range(segment_count):
                t0 = segment / segment_count
                t1 = (segment + 1) / segment_count
                chamfer_face_count += add_wall(
                    lerp_ring(expanded_rect, core_rect, t0),
                    lerp_ring(expanded_rect, core_rect, t1),
                    lower_axial=open_axial + (shoulder_axial - open_axial) * t0,
                    upper_axial=open_axial + (shoulder_axial - open_axial) * t1,
                    reverse=True,
                )

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()
    mesh.fix_normals()
    if not bool(mesh.is_watertight):
        return None
    return mesh, {
        "cap_triangle_count": cap_triangle_count,
        "outer_wall_face_count": outer_wall_face_count,
        "inner_wall_face_count": inner_wall_face_count,
        "rim_chamfer_face_count": chamfer_face_count,
        "bevel_width_cm": float(bevel),
        "bevel_segments": max(1, int(bevel_segments)) if bevel_applied else 0,
        "bevel_applied": bool(bevel_applied),
        "bevel_face_count": int(chamfer_face_count),
        "result_face_count": len(mesh.faces),
        "result_watertight": bool(mesh.is_watertight),
    }


def _exact_axis_aligned_box_open_shell_difference(
    a: trimesh.Trimesh,
    b: trimesh.Trimesh,
    *,
    a_bounds: tuple[np.ndarray, np.ndarray],
    b_bounds: tuple[np.ndarray, np.ndarray],
) -> trimesh.Trimesh | None:
    amin, amax = a_bounds
    bmin, bmax = b_bounds
    candidates: list[tuple[int, int]] = []
    for axis in range(3):
        plane_axes = tuple(index for index in range(3) if index != axis)
        if not all(bmin[index] > amin[index] + 1e-7 and bmax[index] < amax[index] - 1e-7 for index in plane_axes):
            continue
        if bmax[axis] >= amax[axis] - 1e-7 and amin[axis] + 1e-7 < bmin[axis] < amax[axis] - 1e-7:
            candidates.append((axis, 1))
        if bmin[axis] <= amin[axis] + 1e-7 and amin[axis] + 1e-7 < bmax[axis] < amax[axis] - 1e-7:
            candidates.append((axis, -1))
    if len(candidates) != 1:
        return None
    open_axis, open_side = candidates[0]
    bevel_width = _box_polybevel_width(b)
    bevel_segments = _box_polybevel_segments(b)
    built = _mesh_from_open_box_shell(
        outer_min=amin,
        outer_max=amax,
        inner_min=bmin,
        inner_max=bmax,
        open_axis=open_axis,
        open_side=open_side,
        bevel_width=bevel_width,
        bevel_segments=bevel_segments,
    )
    if built is None:
        return None
    result, stats = built
    _set_batch_source_meshes(result, (result,))
    result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_exact_boolean.v1",
        "method": "axis_aligned_box_open_shell_difference_v1",
        "op": "difference",
        "overlap": True,
        "passthrough": False,
        "open_axis": int(open_axis),
        "open_side": "positive" if open_side > 0 else "negative",
        "cutter_part": str(_resolved_shape_primitive_metadata(b).get("part") or "shell_void"),
        **stats,
    }
    return result


def _exact_axis_aligned_box_through_box_difference(
    a: trimesh.Trimesh,
    b: trimesh.Trimesh,
    *,
    a_bounds: tuple[np.ndarray, np.ndarray],
    b_bounds: tuple[np.ndarray, np.ndarray],
) -> trimesh.Trimesh | None:
    previous_state = _profile_cut_state_from_mesh(a)
    amin, amax = a_bounds
    bmin, bmax = b_bounds
    overlap_min = np.maximum(amin, bmin)
    overlap_max = np.minimum(amax, bmax)
    if bool(np.any(overlap_max <= overlap_min)):
        return None

    through_axes: list[int] = []
    for axis in range(3):
        if bmin[axis] <= amin[axis] + 1e-7 and bmax[axis] >= amax[axis] - 1e-7:
            through_axes.append(axis)
    if len(through_axes) != 1:
        return None

    cut_axis = through_axes[0]
    plane_axes = tuple(index for index in range(3) if index != cut_axis)
    plane_min = overlap_min[list(plane_axes)]
    plane_max = overlap_max[list(plane_axes)]
    box_plane_min = amin[list(plane_axes)]
    box_plane_max = amax[list(plane_axes)]
    if bool(np.any(plane_min <= box_plane_min + 1e-7)) or bool(
        np.any(plane_max >= box_plane_max - 1e-7)
    ):
        return None

    profile_points = [
        (float(overlap_min[plane_axes[0]]), float(overlap_min[plane_axes[1]])),
        (float(overlap_max[plane_axes[0]]), float(overlap_min[plane_axes[1]])),
        (float(overlap_max[plane_axes[0]]), float(overlap_max[plane_axes[1]])),
        (float(overlap_min[plane_axes[0]]), float(overlap_max[plane_axes[1]])),
    ]
    primitive_metadata = _resolved_shape_primitive_metadata(b)
    bevel_width = _box_polybevel_width(b)
    bevel_segments = _box_polybevel_segments(b)
    new_cut = {
        "cut_kind": "extruded",
        "profile_points": [[float(point[0]), float(point[1])] for point in profile_points],
        "bevel_width": float(bevel_width),
        "bevel_segments": int(bevel_segments),
        "cutter_part": str(primitive_metadata.get("part") or "box_cutter"),
        "source_kind": "box",
    }
    if bevel_width > 1e-9:
        new_cut["bevel_applied"] = True

    state_cut_kind = "extruded"
    if previous_state is not None:
        previous_kind = str(previous_state.get("cut_kind") or "")
        if previous_kind not in {"extruded", "revolved", "mixed"}:
            return None
        if int(previous_state.get("cut_axis", -1)) != int(cut_axis):
            return None
        previous_plane_axes = [int(value) for value in previous_state.get("plane_axes", [])]
        if previous_plane_axes != [int(axis) for axis in plane_axes]:
            return None
        cuts = [
            dict(cut)
            for cut in previous_state.get("cuts", [])
            if isinstance(cut, dict)
        ]
        if len(cuts) != len(previous_state.get("cuts", [])):
            return None
        if previous_kind != "mixed":
            cuts = [
                {**cut, "cut_kind": str(cut.get("cut_kind") or previous_kind)}
                for cut in cuts
            ]
        elif any(str(cut.get("cut_kind") or "") not in {"extruded", "revolved"} for cut in cuts):
            return None
        cuts.append(new_cut)
        if _profile_cut_records_touch_plane_boundary(
            cuts,
            box_min=amin,
            box_max=amax,
            plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
        ):
            return None
        if previous_kind == "extruded":
            built = _mesh_from_box_through_profile_cuts(
                box_min=amin,
                box_max=amax,
                cut_axis=cut_axis,
                plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
                cuts=cuts,
            )
            method = "axis_aligned_box_repeated_through_box_profile_difference_v1"
        else:
            built = _mesh_from_box_mixed_profile_cuts(
                box_min=amin,
                box_max=amax,
                cut_axis=cut_axis,
                plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
                cuts=cuts,
            )
            method = "axis_aligned_box_mixed_through_box_profile_difference_v1"
            state_cut_kind = "mixed"
    else:
        cuts = [new_cut]
        built = _mesh_from_box_through_profile_cut(
            box_min=amin,
            box_max=amax,
            cut_axis=cut_axis,
            plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
            profile_points=profile_points,
            bevel_width=bevel_width,
            bevel_segments=bevel_segments,
        )
        method = "axis_aligned_box_through_box_profile_difference_v1"

    if built is None:
        return None
    result, stats = built
    if not bool(result.is_watertight):
        return None
    _set_batch_source_meshes(result, (result,))
    result.metadata[_PROFILE_CUT_STATE_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_profile_cut_state.v1",
        "box_min": [float(value) for value in amin],
        "box_max": [float(value) for value in amax],
        "cut_kind": state_cut_kind,
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "cuts": cuts,
    }
    result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_exact_boolean.v1",
        "method": method,
        "op": "difference",
        "overlap": True,
        "through_cut": True,
        "blind_cut": False,
        "passthrough": False,
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "cutter_part": str(primitive_metadata.get("part") or "box_cutter"),
        "profile_cut_count": len(cuts),
        "profile_cut_kinds": sorted({str(cut.get("cut_kind") or state_cut_kind) for cut in cuts}),
        "result_face_count": len(result.faces),
        "result_watertight": bool(result.is_watertight),
        **stats,
    }
    return result


def _exact_profile_cut_state_box_difference(
    a: trimesh.Trimesh,
    b: trimesh.Trimesh,
    *,
    a_bounds: tuple[np.ndarray, np.ndarray],
    b_bounds: tuple[np.ndarray, np.ndarray],
) -> trimesh.Trimesh | None:
    previous_state = _profile_cut_state_from_mesh(a)
    if previous_state is None:
        return None
    previous_kind = str(previous_state.get("cut_kind") or "")
    if previous_kind not in {"extruded", "revolved", "mixed"}:
        return None
    try:
        cut_axis = int(previous_state["cut_axis"])
        plane_axes = tuple(int(axis) for axis in previous_state["plane_axes"])
    except (KeyError, TypeError, ValueError):
        return None
    if cut_axis not in {0, 1, 2} or len(plane_axes) != 2 or set(plane_axes) != ({0, 1, 2} - {cut_axis}):
        return None
    amin, amax = a_bounds
    bmin, bmax = b_bounds
    overlap_min = np.maximum(amin, bmin)
    overlap_max = np.minimum(amax, bmax)
    if bool(np.any(overlap_max <= overlap_min)):
        return None
    if bmin[cut_axis] > amin[cut_axis] + 1e-7 or bmax[cut_axis] < amax[cut_axis] - 1e-7:
        return None
    touches_plane_boundary = bool(np.any(overlap_min[list(plane_axes)] <= amin[list(plane_axes)] + 1e-7)) or bool(
        np.any(overlap_max[list(plane_axes)] >= amax[list(plane_axes)] - 1e-7)
    )

    profile_points = [
        (float(overlap_min[plane_axes[0]]), float(overlap_min[plane_axes[1]])),
        (float(overlap_max[plane_axes[0]]), float(overlap_min[plane_axes[1]])),
        (float(overlap_max[plane_axes[0]]), float(overlap_max[plane_axes[1]])),
        (float(overlap_min[plane_axes[0]]), float(overlap_max[plane_axes[1]])),
    ]
    primitive_metadata = _resolved_shape_primitive_metadata(b)
    new_cut = {
        "cut_kind": "extruded",
        "profile_points": [[float(point[0]), float(point[1])] for point in profile_points],
        "bevel_width": 0.0,
        "cutter_part": str(primitive_metadata.get("part") or "box_cutter"),
    }
    cuts = [
        dict(cut)
        for cut in previous_state.get("cuts", [])
        if isinstance(cut, dict)
    ]
    if previous_kind != "mixed":
        cuts = [
            {**cut, "cut_kind": str(cut.get("cut_kind") or previous_kind)}
            for cut in cuts
        ]
    elif any(str(cut.get("cut_kind") or "") not in {"extruded", "revolved"} for cut in cuts):
        return None
    cuts.append(new_cut)

    if touches_plane_boundary:
        built = _mesh_from_box_profile_cuts_with_open_extruded_boundaries(
            box_min=amin,
            box_max=amax,
            cut_axis=cut_axis,
            plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
            cuts=cuts,
        )
        state_cut_kind = "extruded" if previous_kind == "extruded" else "mixed"
        method = (
            "axis_aligned_box_profile_state_open_through_box_difference_v1"
            if previous_kind == "extruded"
            else "axis_aligned_box_mixed_profile_state_open_through_box_difference_v1"
        )
    elif previous_kind == "extruded":
        built = _mesh_from_box_through_profile_cuts(
            box_min=amin,
            box_max=amax,
            cut_axis=cut_axis,
            plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
            cuts=cuts,
        )
        state_cut_kind = "extruded"
        method = "axis_aligned_box_profile_state_through_box_difference_v1"
    else:
        built = _mesh_from_box_mixed_profile_cuts(
            box_min=amin,
            box_max=amax,
            cut_axis=cut_axis,
            plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
            cuts=cuts,
        )
        state_cut_kind = "mixed"
        method = "axis_aligned_box_mixed_profile_state_through_box_difference_v1"
    if built is None:
        return None
    result, stats = built
    _set_batch_source_meshes(result, (result,))
    result.metadata[_PROFILE_CUT_STATE_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_profile_cut_state.v1",
        "box_min": [float(value) for value in amin],
        "box_max": [float(value) for value in amax],
        "cut_kind": state_cut_kind,
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "cuts": cuts,
    }
    result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_exact_boolean.v1",
        "method": method,
        "op": "difference",
        "overlap": True,
        "through_cut": True,
        "passthrough": False,
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "cutter_part": str(primitive_metadata.get("part") or "box_cutter"),
        "profile_cut_count": len(cuts),
        "profile_cut_kinds": sorted(
            {
                str(cut.get("cut_kind") or state_cut_kind)
                for cut in cuts
            }
        ),
        "result_face_count": len(result.faces),
        "result_watertight": bool(result.is_watertight),
        **stats,
    }
    return result


def _exact_axis_aligned_box_blind_box_difference(
    a: trimesh.Trimesh,
    b: trimesh.Trimesh,
    *,
    a_bounds: tuple[np.ndarray, np.ndarray],
    b_bounds: tuple[np.ndarray, np.ndarray],
) -> trimesh.Trimesh | None:
    previous_state = _profile_cut_state_from_mesh(a)
    amin, amax = a_bounds
    bmin, bmax = b_bounds
    overlap_min = np.maximum(amin, bmin)
    overlap_max = np.minimum(amax, bmax)
    if bool(np.any(overlap_max <= overlap_min)):
        return None

    candidate: tuple[int, int, float] | None = None
    for axis in range(3):
        positive_open = (
            bmax[axis] >= amax[axis] - 1e-7
            and bmin[axis] > amin[axis] + 1e-7
            and bmin[axis] < amax[axis] - 1e-7
        )
        negative_open = (
            bmin[axis] <= amin[axis] + 1e-7
            and bmax[axis] < amax[axis] - 1e-7
            and bmax[axis] > amin[axis] + 1e-7
        )
        if positive_open == negative_open:
            continue
        if candidate is not None:
            return None
        candidate = (
            axis,
            1 if positive_open else -1,
            float(bmin[axis] if positive_open else bmax[axis]),
        )
    if candidate is None:
        return None

    cut_axis, open_side, floor_axial = candidate
    plane_axes = tuple(index for index in range(3) if index != cut_axis)
    touches_plane_boundary = bool(
        np.any(overlap_min[list(plane_axes)] <= amin[list(plane_axes)] + 1e-7)
    ) or bool(np.any(overlap_max[list(plane_axes)] >= amax[list(plane_axes)] - 1e-7))
    if touches_plane_boundary:
        return None

    profile_points = [
        (float(overlap_min[plane_axes[0]]), float(overlap_min[plane_axes[1]])),
        (float(overlap_max[plane_axes[0]]), float(overlap_min[plane_axes[1]])),
        (float(overlap_max[plane_axes[0]]), float(overlap_max[plane_axes[1]])),
        (float(overlap_min[plane_axes[0]]), float(overlap_max[plane_axes[1]])),
    ]
    primitive_metadata = _resolved_shape_primitive_metadata(b)
    bevel_width = _box_polybevel_width(b)
    bevel_segments = _box_polybevel_segments(b)
    new_cut = {
        "cut_kind": "extruded_blind",
        "profile_points": [[float(point[0]), float(point[1])] for point in profile_points],
        "bevel_width": float(bevel_width),
        "bevel_segments": int(bevel_segments),
        "cutter_part": str(primitive_metadata.get("part") or "box_cutter"),
        "open_side": "positive" if open_side > 0 else "negative",
        "floor_axial_cm": float(floor_axial),
    }

    if previous_state is None:
        cuts = [new_cut]
        state_cut_kind = "extruded_blind"
        built = _mesh_from_box_blind_profile_cut(
            box_min=amin,
            box_max=amax,
            cut_axis=cut_axis,
            plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
            profile_points=profile_points,
            open_side=open_side,
            floor_axial=floor_axial,
            bevel_width=bevel_width,
            bevel_segments=bevel_segments,
        )
        method = "axis_aligned_box_blind_box_profile_difference_v1"
    else:
        previous_cuts = _existing_blind_profile_cuts_from_state(
            previous_state,
            cut_axis=cut_axis,
            plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
        )
        if previous_cuts is None:
            return None
        cuts = [*previous_cuts, new_cut]
        state_cut_kind = _blind_cut_state_kind(cuts)
        built = _mesh_from_box_blind_cut_records(
            box_min=amin,
            box_max=amax,
            cut_axis=cut_axis,
            plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
            cuts=cuts,
        )
        method = (
            "axis_aligned_box_repeated_blind_box_profile_difference_v1"
            if state_cut_kind == "extruded_blind"
            else "axis_aligned_box_mixed_blind_profile_difference_v1"
        )
    if built is None:
        return None
    result, stats = built
    _set_batch_source_meshes(result, (result,))
    result.metadata[_PROFILE_CUT_STATE_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_profile_cut_state.v1",
        "box_min": [float(value) for value in amin],
        "box_max": [float(value) for value in amax],
        "cut_kind": state_cut_kind,
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "cuts": cuts,
    }
    result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_exact_boolean.v1",
        "method": method,
        "op": "difference",
        "overlap": True,
        "through_cut": False,
        "blind_cut": True,
        "passthrough": False,
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "cutter_part": str(primitive_metadata.get("part") or "box_cutter"),
        "profile_cut_count": len(cuts),
        "profile_cut_kinds": sorted({str(cut.get("cut_kind") or state_cut_kind) for cut in cuts}),
        "result_face_count": len(result.faces),
        "result_watertight": bool(result.is_watertight),
        **stats,
    }
    return result


def _adjacent_rectangular_union_bounds(
    left_min: np.ndarray,
    left_max: np.ndarray,
    right_min: np.ndarray,
    right_max: np.ndarray,
    *,
    allowed_union_axes: set[int],
) -> tuple[np.ndarray, np.ndarray, int] | None:
    tolerance = 1e-7
    for axis in sorted(allowed_union_axes):
        same_other_axes = True
        for other_axis in range(3):
            if other_axis == axis:
                continue
            if (
                abs(float(left_min[other_axis]) - float(right_min[other_axis])) > tolerance
                or abs(float(left_max[other_axis]) - float(right_max[other_axis])) > tolerance
            ):
                same_other_axes = False
                break
        if not same_other_axes:
            continue
        touches = (
            abs(float(left_max[axis]) - float(right_min[axis])) <= tolerance
            or abs(float(right_max[axis]) - float(left_min[axis])) <= tolerance
        )
        if not touches:
            continue
        union_min = np.minimum(left_min, right_min)
        union_max = np.maximum(left_max, right_max)
        if bool(np.any(union_max <= union_min)):
            return None
        return union_min, union_max, int(axis)
    return None


def _profile_cut_state_blind_cuts(
    state: dict[str, Any] | None,
    *,
    cut_axis: int,
    plane_axes: tuple[int, int],
) -> list[dict[str, Any]] | None:
    if state is None:
        return []
    return _existing_blind_profile_cuts_from_state(
        state,
        cut_axis=cut_axis,
        plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
    )


def _exact_profile_cut_state_box_union(
    a: trimesh.Trimesh,
    b: trimesh.Trimesh,
    *,
    a_bounds: tuple[np.ndarray, np.ndarray],
    b_bounds: tuple[np.ndarray, np.ndarray],
    a_cut_state: dict[str, Any] | None,
    b_cut_state: dict[str, Any] | None,
) -> trimesh.Trimesh | None:
    if a_cut_state is None and b_cut_state is None:
        return None

    source_state = a_cut_state or b_cut_state
    if source_state is None:
        return None
    try:
        cut_axis = int(source_state["cut_axis"])
        plane_axes = tuple(int(value) for value in source_state["plane_axes"])
    except (KeyError, TypeError, ValueError):
        return None
    if cut_axis not in {0, 1, 2} or len(plane_axes) != 2 or set(plane_axes) != ({0, 1, 2} - {cut_axis}):
        return None

    if a_cut_state is not None:
        a_axis = int(a_cut_state.get("cut_axis", -1))
        a_planes = [int(value) for value in a_cut_state.get("plane_axes", [])]
        if a_axis != cut_axis or a_planes != [int(axis) for axis in plane_axes]:
            return None
    if b_cut_state is not None:
        b_axis = int(b_cut_state.get("cut_axis", -1))
        b_planes = [int(value) for value in b_cut_state.get("plane_axes", [])]
        if b_axis != cut_axis or b_planes != [int(axis) for axis in plane_axes]:
            return None

    amin, amax = a_bounds
    bmin, bmax = b_bounds
    union = _adjacent_rectangular_union_bounds(
        amin,
        amax,
        bmin,
        bmax,
        allowed_union_axes={int(axis) for axis in plane_axes},
    )
    if union is None:
        return None
    union_min, union_max, union_axis = union

    cuts: list[dict[str, Any]] = []
    a_cuts = _profile_cut_state_blind_cuts(
        a_cut_state,
        cut_axis=cut_axis,
        plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
    )
    b_cuts = _profile_cut_state_blind_cuts(
        b_cut_state,
        cut_axis=cut_axis,
        plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
    )
    if a_cuts is None or b_cuts is None:
        return None
    cuts.extend(deepcopy(a_cuts))
    cuts.extend(deepcopy(b_cuts))
    if not cuts:
        return None

    state_cut_kind = _blind_cut_state_kind(cuts)
    built = _mesh_from_box_blind_cut_records(
        box_min=union_min,
        box_max=union_max,
        cut_axis=cut_axis,
        plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
        cuts=cuts,
    )
    if built is None:
        return None
    result, stats = built
    _set_batch_source_meshes(result, (result,))
    result.metadata[_PROFILE_CUT_STATE_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_profile_cut_state.v1",
        "box_min": [float(value) for value in union_min],
        "box_max": [float(value) for value in union_max],
        "cut_kind": state_cut_kind,
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "cuts": cuts,
    }
    result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_exact_boolean.v1",
        "method": "axis_aligned_box_profile_cut_union_v1",
        "op": "union",
        "overlap": False,
        "touching_union": True,
        "union_axis": int(union_axis),
        "profile_cut_operand_count": int((a_cut_state is not None) + (b_cut_state is not None)),
        "profile_cut_count": len(cuts),
        "profile_cut_kinds": sorted({str(cut.get("cut_kind") or state_cut_kind) for cut in cuts}),
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "passthrough": False,
        "result_face_count": len(result.faces),
        "result_watertight": bool(result.is_watertight),
        **stats,
    }
    return result


def _boss_state_components(
    state: dict[str, Any] | None,
    *,
    cut_axis: int,
    plane_axes: tuple[int, int],
    side: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | None:
    if state is None:
        return [], []
    try:
        state_cut_axis = int(state["cut_axis"])
        state_plane_axes = tuple(int(value) for value in state["plane_axes"])
        state_side = int(state["side"])
    except (KeyError, TypeError, ValueError):
        return None
    if state_cut_axis != cut_axis or state_plane_axes != plane_axes or state_side != side:
        return None
    bosses = [
        dict(item)
        for item in state.get("bosses", [])
        if isinstance(item, dict)
    ]
    if not bosses or len(bosses) != len(state.get("bosses", [])):
        return None
    through_cuts = _boss_state_through_cuts(state)
    if through_cuts is None:
        return None
    return bosses, through_cuts


def _exact_boss_state_box_union(
    a: trimesh.Trimesh,
    b: trimesh.Trimesh,
) -> trimesh.Trimesh | None:
    a_state = _boss_state_from_mesh(a)
    b_state = _boss_state_from_mesh(b)
    if a_state is None and b_state is None:
        return None
    source_state = a_state or b_state
    if source_state is None:
        return None
    try:
        cut_axis = int(source_state["cut_axis"])
        plane_axes = tuple(int(value) for value in source_state["plane_axes"])
        side = int(source_state["side"])
    except (KeyError, TypeError, ValueError):
        return None
    if cut_axis not in {0, 1, 2} or len(plane_axes) != 2 or set(plane_axes) != ({0, 1, 2} - {cut_axis}):
        return None
    if side not in {-1, 1}:
        return None

    a_bounds = _box_bounds_from_metadata(a)
    b_bounds = _box_bounds_from_metadata(b)
    if a_bounds is None or b_bounds is None:
        return None
    union = _adjacent_rectangular_union_bounds(
        a_bounds[0],
        a_bounds[1],
        b_bounds[0],
        b_bounds[1],
        allowed_union_axes={int(axis) for axis in plane_axes},
    )
    if union is None:
        return None
    union_min, union_max, union_axis = union

    a_components = _boss_state_components(
        a_state,
        cut_axis=cut_axis,
        plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
        side=side,
    )
    b_components = _boss_state_components(
        b_state,
        cut_axis=cut_axis,
        plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
        side=side,
    )
    if a_components is None or b_components is None:
        return None
    a_bosses, a_cuts = a_components
    b_bosses, b_cuts = b_components
    bosses = [*deepcopy(a_bosses), *deepcopy(b_bosses)]
    through_cuts = [*deepcopy(a_cuts), *deepcopy(b_cuts)]
    if not bosses:
        return None
    built = _mesh_from_box_cylinder_bosses(
        box_min=union_min,
        box_max=union_max,
        cut_axis=cut_axis,
        plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
        side=side,
        bosses=bosses,
        through_cuts=through_cuts,
    )
    if built is None:
        return None
    result, stats = built
    boss_state_payload = {
        "schema": "lathe.geometry.reference_boss_state.v1",
        "box_min": [float(value) for value in union_min],
        "box_max": [float(value) for value in union_max],
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "side": int(side),
        "bosses": bosses,
    }
    if through_cuts:
        boss_state_payload["through_cuts"] = through_cuts
    result.metadata[_BOSS_STATE_METADATA_KEY] = boss_state_payload
    result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_exact_boolean.v1",
        "method": "axis_aligned_box_boss_state_union_v1",
        "op": "union",
        "overlap": False,
        "touching_union": True,
        "union_axis": int(union_axis),
        "boss_state_operand_count": int((a_state is not None) + (b_state is not None)),
        "boss_count": len(bosses),
        "boss_styles": sorted({str(item.get("style") or "") for item in bosses}),
        "boss_source_kinds": sorted({str(item.get("source_kind") or "cylinder") for item in bosses}),
        "through_cut_count": len(through_cuts),
        "through_cut_kinds": sorted({str(cut.get("cut_kind") or "") for cut in through_cuts}),
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "side": int(side),
        "passthrough": False,
        "result_face_count": len(result.faces),
        "result_watertight": bool(result.is_watertight),
        **stats,
    }
    _set_batch_source_meshes(result, (result,))
    return result


def _exact_axis_aligned_box_boolean(
    op: str,
    a: trimesh.Trimesh,
    b: trimesh.Trimesh,
) -> trimesh.Trimesh | None:
    a_cut_state = _profile_cut_state_from_mesh(a)
    b_cut_state = _profile_cut_state_from_mesh(b)
    if _boss_state_from_mesh(a) is not None or _boss_state_from_mesh(b) is not None:
        return None
    a_bounds = _box_bounds_from_metadata(a)
    b_bounds = _box_bounds_from_metadata(b)
    if a_bounds is None or b_bounds is None:
        return None
    if op == "difference":
        b_profile = _extruded_profile_metadata(b)
        if b_profile is not None and float(b_profile.get("bevel_width_cm") or 0.0) > 1e-9:
            return None
    amin, amax = a_bounds
    bmin, bmax = b_bounds
    if op == "union" and (a_cut_state is not None or b_cut_state is not None):
        profile_union = _exact_profile_cut_state_box_union(
            a,
            b,
            a_bounds=(amin, amax),
            b_bounds=(bmin, bmax),
            a_cut_state=a_cut_state,
            b_cut_state=b_cut_state,
        )
        if profile_union is not None:
            return profile_union
    if op == "union" and a_cut_state is None and b_cut_state is None:
        xs = _axis_values(amin[0], amax[0], bmin[0], bmax[0])
        ys = _axis_values(amin[1], amax[1], bmin[1], bmax[1])
        zs = _axis_values(amin[2], amax[2], bmin[2], bmax[2])
        cells: list[tuple[np.ndarray, np.ndarray]] = []
        for ix in range(len(xs) - 1):
            for iy in range(len(ys) - 1):
                for iz in range(len(zs) - 1):
                    cell_min = np.asarray((xs[ix], ys[iy], zs[iz]), dtype=np.float64)
                    cell_max = np.asarray((xs[ix + 1], ys[iy + 1], zs[iz + 1]), dtype=np.float64)
                    if bool(np.any(cell_max - cell_min <= 1e-9)):
                        continue
                    center = (cell_min + cell_max) * 0.5
                    inside_a = bool(np.all(center >= amin - 1e-9) and np.all(center <= amax + 1e-9))
                    inside_b = bool(np.all(center >= bmin - 1e-9) and np.all(center <= bmax + 1e-9))
                    if inside_a or inside_b:
                        cells.append((cell_min, cell_max))
        if not cells:
            return None
        result = _mesh_from_axis_aligned_box_cells(cells)
        _set_batch_source_meshes(
            result,
            [_axis_aligned_box_mesh(bounds_min=cell_min, bounds_max=cell_max) for cell_min, cell_max in cells],
        )
        overlap_min_for_report = np.maximum(amin, bmin)
        overlap_max_for_report = np.minimum(amax, bmax)
        result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
            "schema": "lathe.geometry.reference_exact_boolean.v1",
            "method": "axis_aligned_box_union_v1",
            "op": op,
            "overlap": bool(np.all(overlap_max_for_report > overlap_min_for_report)),
            "piece_count": len(cells),
            "passthrough": False,
            "result_face_count": len(result.faces),
            "result_watertight": bool(result.is_watertight),
        }
        return result
    overlap_min = np.maximum(amin, bmin)
    overlap_max = np.minimum(amax, bmax)
    if bool(np.any(overlap_max <= overlap_min)):
        if op == "difference":
            result = a.copy()
            result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
                "schema": "lathe.geometry.reference_exact_boolean.v1",
                "method": "axis_aligned_box_difference_v1",
                "op": op,
                "overlap": False,
                "piece_count": 1,
                "box_piece_count": 1,
                "box_pieces": [
                    {
                        "box_min": [float(value) for value in amin],
                        "box_max": [float(value) for value in amax],
                    }
                ],
                "passthrough": False,
            }
            return result
        if op == "intersection":
            result = trimesh.Trimesh()
            result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
                "schema": "lathe.geometry.reference_exact_boolean.v1",
                "method": "axis_aligned_box_intersection_v1",
                "op": op,
                "overlap": False,
                "piece_count": 0,
                "passthrough": False,
            }
            return result
        return None
    if op == "difference" and b_cut_state is None:
        through_box_result = _exact_axis_aligned_box_through_box_difference(
            a,
            b,
            a_bounds=(amin, amax),
            b_bounds=(bmin, bmax),
        )
        if through_box_result is not None:
            return through_box_result
        blind_box_result = _exact_axis_aligned_box_blind_box_difference(
            a,
            b,
            a_bounds=(amin, amax),
            b_bounds=(bmin, bmax),
        )
        if blind_box_result is not None:
            return blind_box_result
    if a_cut_state is not None or b_cut_state is not None:
        if op == "difference" and a_cut_state is not None and b_cut_state is None:
            cut_result = _exact_profile_cut_state_box_difference(
                a,
                b,
                a_bounds=(amin, amax),
                b_bounds=(bmin, bmax),
            )
            if cut_result is not None:
                return cut_result
        return None
    if op == "intersection":
        bevel_width = max(_box_polybevel_width(a), _box_polybevel_width(b))
        if bevel_width > 1e-9:
            from ..exact_solids import _chamfered_box_mesh

            result = _chamfered_box_mesh(
                tuple(float(value) for value in (overlap_max - overlap_min)),
                tuple(float(value) for value in ((overlap_min + overlap_max) * 0.5)),
                width=bevel_width,
            )
            method = "axis_aligned_box_beveled_intersection_v1"
            bevel_applied = True
        else:
            result = _axis_aligned_box_mesh(bounds_min=overlap_min, bounds_max=overlap_max)
            method = "axis_aligned_box_intersection_v1"
            bevel_applied = False
        result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
            "schema": "lathe.geometry.reference_exact_boolean.v1",
            "method": method,
            "op": op,
            "overlap": True,
            "piece_count": 1,
            **(
                {
                    "box_piece_count": 1,
                    "box_pieces": [
                        {
                            "box_min": [float(value) for value in overlap_min],
                            "box_max": [float(value) for value in overlap_max],
                        }
                    ],
                }
                if not bevel_applied
                else {
                    "beveled_box_bounds": {
                        "box_min": [float(value) for value in overlap_min],
                        "box_max": [float(value) for value in overlap_max],
                    },
                    "bevel_width_cm": float(bevel_width),
                    "bevel_applied": True,
                    "bevel_face_count": max(0, int(len(result.faces) - 12)),
                }
            ),
            "passthrough": False,
            "result_face_count": len(result.faces),
            "result_watertight": bool(result.is_watertight),
        }
        return result
    if op != "difference":
        return None
    shell_result = _exact_axis_aligned_box_open_shell_difference(
        a,
        b,
        a_bounds=(amin, amax),
        b_bounds=(bmin, bmax),
    )
    if shell_result is not None:
        return shell_result

    xs = _axis_values(amin[0], overlap_min[0], overlap_max[0], amax[0])
    ys = _axis_values(amin[1], overlap_min[1], overlap_max[1], amax[1])
    zs = _axis_values(amin[2], overlap_min[2], overlap_max[2], amax[2])
    cells: list[tuple[np.ndarray, np.ndarray]] = []
    for ix in range(len(xs) - 1):
        for iy in range(len(ys) - 1):
            for iz in range(len(zs) - 1):
                cell_min = np.asarray((xs[ix], ys[iy], zs[iz]), dtype=np.float64)
                cell_max = np.asarray((xs[ix + 1], ys[iy + 1], zs[iz + 1]), dtype=np.float64)
                if bool(np.any(cell_max - cell_min <= 1e-9)):
                    continue
                inside_cut = bool(
                    np.all(cell_min >= overlap_min - 1e-9)
                    and np.all(cell_max <= overlap_max + 1e-9)
                )
                if not inside_cut:
                    cells.append((cell_min, cell_max))

    if not cells:
        result = trimesh.Trimesh()
        _set_batch_source_meshes(result, ())
    else:
        pieces = [
            _axis_aligned_box_mesh(bounds_min=cell_min, bounds_max=cell_max)
            for cell_min, cell_max in cells
        ]
        result = _mesh_from_axis_aligned_box_cells(cells)
        _set_batch_source_meshes(result, pieces)
    result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_exact_boolean.v1",
        "method": "axis_aligned_box_difference_v1",
        "op": op,
        "overlap": True,
        "piece_count": len(cells),
        "box_piece_count": len(cells),
        "box_pieces": [
            {
                "box_min": [float(value) for value in cell_min],
                "box_max": [float(value) for value in cell_max],
            }
            for cell_min, cell_max in cells
        ],
        "passthrough": False,
    }
    return result


def _exact_axis_aligned_box_batch_union(meshes: list[trimesh.Trimesh]) -> trimesh.Trimesh | None:
    box_bounds: list[tuple[np.ndarray, np.ndarray]] = []
    for mesh in meshes:
        if _profile_cut_state_from_mesh(mesh) is not None or _boss_state_from_mesh(mesh) is not None:
            return None
        bounds = _box_bounds_from_metadata(mesh)
        if bounds is None:
            return None
        box_bounds.append(bounds)
    if not box_bounds:
        return None
    xs = _axis_values(*[value for bounds in box_bounds for value in (bounds[0][0], bounds[1][0])])
    ys = _axis_values(*[value for bounds in box_bounds for value in (bounds[0][1], bounds[1][1])])
    zs = _axis_values(*[value for bounds in box_bounds for value in (bounds[0][2], bounds[1][2])])
    cells: list[tuple[np.ndarray, np.ndarray]] = []
    for ix in range(len(xs) - 1):
        for iy in range(len(ys) - 1):
            for iz in range(len(zs) - 1):
                cell_min = np.asarray((xs[ix], ys[iy], zs[iz]), dtype=np.float64)
                cell_max = np.asarray((xs[ix + 1], ys[iy + 1], zs[iz + 1]), dtype=np.float64)
                if bool(np.any(cell_max - cell_min <= 1e-9)):
                    continue
                center = (cell_min + cell_max) * 0.5
                if any(
                    bool(np.all(center >= bmin - 1e-9) and np.all(center <= bmax + 1e-9))
                    for bmin, bmax in box_bounds
                ):
                    cells.append((cell_min, cell_max))
    if not cells:
        return None
    result = _mesh_from_axis_aligned_box_cells(cells)
    try:
        result_body_count = len(result.split(only_watertight=False)) if len(result.faces) else 0
    except (AttributeError, TypeError, ValueError, RuntimeError):
        result_body_count = 0
    if not bool(result.is_watertight) or result_body_count != 1:
        return None
    _set_batch_source_meshes(
        result,
        [_axis_aligned_box_mesh(bounds_min=cell_min, bounds_max=cell_max) for cell_min, cell_max in cells],
    )
    result.metadata["lathe_reference_batch_union"] = {
        "schema": "lathe.geometry.reference_batch_union.v1",
        "method": "axis_aligned_box_batch_union_v1",
        "operand_count": len(meshes),
        "piece_count": len(cells),
        "result_face_count": len(result.faces),
        "result_watertight": bool(result.is_watertight),
        "result_body_count": int(result_body_count),
    }
    result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_exact_boolean.v1",
        "method": "axis_aligned_box_batch_union_v1",
        "op": "batch_union",
        "operand_count": len(meshes),
        "piece_count": len(cells),
        "passthrough": False,
        "result_face_count": len(result.faces),
        "result_watertight": bool(result.is_watertight),
        "result_body_count": int(result_body_count),
    }
    return result


def _fill_planar_boundary_loops(
    mesh: trimesh.Trimesh,
    *,
    max_loop_vertices: int = 8,
    tolerance: float = 1e-6,
) -> tuple[trimesh.Trimesh, int]:
    try:
        edges = np.asarray(mesh.edges_sorted, dtype=np.int64)
    except (AttributeError, TypeError, ValueError):
        return mesh, 0
    if edges.size == 0:
        return mesh, 0
    boundary_edges, edge_counts = np.unique(edges, axis=0, return_counts=True)
    boundary_edges = boundary_edges[edge_counts == 1]
    if len(boundary_edges) == 0:
        return mesh, 0
    adjacency: dict[int, list[int]] = {}
    for left, right in boundary_edges:
        left_index = int(left)
        right_index = int(right)
        adjacency.setdefault(left_index, []).append(right_index)
        adjacency.setdefault(right_index, []).append(left_index)
    added_faces: list[list[int]] = []

    def ordered_planar_component(component: set[int]) -> list[int]:
        if len(component) < 3 or len(component) > max_loop_vertices:
            return []
        points = np.asarray([mesh.vertices[index] for index in component], dtype=np.float64)
        spans = np.ptp(points, axis=0)
        drop_axis = int(np.argmin(spans))
        if float(spans[drop_axis]) > tolerance:
            normal = None
            for index in range(1, len(points) - 1):
                candidate = np.cross(points[index] - points[0], points[index + 1] - points[0])
                length = float(np.linalg.norm(candidate))
                if length > tolerance:
                    normal = candidate / length
                    break
            if normal is None:
                return []
            distances = np.abs((points - points[0]) @ normal)
            if float(np.max(distances)) > tolerance:
                return []
            drop_axis = int(np.argmax(np.abs(normal)))
        component_edges = {
            tuple(sorted((int(left), int(right))))
            for left, right in boundary_edges
            if int(left) in component and int(right) in component
        }
        if len(component_edges) < len(component):
            return []
        if all(len([neighbor for neighbor in adjacency[vertex] if neighbor in component]) == 2 for vertex in component):
            start = min(component)
            ordered = [start]
            previous = -1
            current = start
            while True:
                candidates = [
                    neighbor
                    for neighbor in adjacency[current]
                    if neighbor in component and neighbor != previous
                ]
                if not candidates:
                    break
                next_vertex = candidates[0]
                if next_vertex == start:
                    return ordered if len(ordered) == len(component) else []
                ordered.append(next_vertex)
                previous, current = current, next_vertex
                if len(ordered) > len(component):
                    break
        keep_axes = [axis for axis in range(3) if axis != drop_axis]
        projected = {
            vertex: (
                float(mesh.vertices[vertex][keep_axes[0]]),
                float(mesh.vertices[vertex][keep_axes[1]]),
            )
            for vertex in component
        }
        centroid = (
            sum(point[0] for point in projected.values()) / len(projected),
            sum(point[1] for point in projected.values()) / len(projected),
        )
        return sorted(
            component,
            key=lambda vertex: math.atan2(
                projected[vertex][1] - centroid[1],
                projected[vertex][0] - centroid[0],
            ),
        )

    visited_vertices: set[int] = set()
    for vertex in sorted(adjacency):
        if vertex in visited_vertices:
            continue
        stack = [vertex]
        component: set[int] = set()
        while stack:
            current = stack.pop()
            if current in component:
                continue
            component.add(current)
            for neighbor in adjacency.get(current, []):
                if neighbor not in component:
                    stack.append(neighbor)
        visited_vertices.update(component)
        loop = ordered_planar_component(component)
        if len(loop) < 3:
            continue
        for index in range(1, len(loop) - 1):
            added_faces.append([loop[0], loop[index], loop[index + 1]])
    if not added_faces:
        return mesh, 0
    filled = trimesh.Trimesh(
        vertices=np.asarray(mesh.vertices, dtype=np.float64),
        faces=np.vstack([np.asarray(mesh.faces, dtype=np.int64), np.asarray(added_faces, dtype=np.int64)]),
        process=False,
    )
    filled.remove_unreferenced_vertices()
    filled.merge_vertices()
    filled.fix_normals()
    return filled, len(added_faces)


def _mesh_from_axis_extruded_polygon_union(
    entries: list[dict[str, Any]],
    *,
    axis: int,
    plane_axes: tuple[int, int],
) -> tuple[trimesh.Trimesh, dict[str, Any]] | None:
    try:
        from shapely.geometry import LineString, Polygon
        from shapely.errors import GEOSException
        from shapely.ops import triangulate, unary_union
    except (ImportError, ModuleNotFoundError):
        return None
    if axis not in {0, 1, 2} or len(plane_axes) != 2 or set(plane_axes) != ({0, 1, 2} - {axis}):
        return None
    if not entries:
        return None
    axis_values = _axis_values(*[value for entry in entries for value in (entry["low"], entry["high"])])
    if len(axis_values) < 2:
        return None

    def polygons(geometry: Any) -> list[Any]:
        if geometry.is_empty:
            return []
        if geometry.geom_type == "Polygon":
            return [geometry]
        if geometry.geom_type == "MultiPolygon":
            return list(geometry.geoms)
        if geometry.geom_type == "GeometryCollection":
            out = []
            for child in geometry.geoms:
                out.extend(polygons(child))
            return out
        return []

    def split_ring_points_at_boundaries(
        points: list[tuple[float, float]],
        boundaries: list[Any],
    ) -> list[tuple[float, float]]:
        if len(points) < 3 or not boundaries:
            return points

        def add_intersection_points(geometry: Any, out: list[tuple[float, float]]) -> None:
            geom_type = getattr(geometry, "geom_type", "")
            if geom_type == "Point":
                out.append((float(geometry.x), float(geometry.y)))
                return
            if geom_type == "MultiPoint":
                for point in geometry.geoms:
                    out.append((float(point.x), float(point.y)))
                return
            if geom_type in {"LineString", "LinearRing"}:
                coords = list(geometry.coords)
                for coord in coords:
                    out.append((float(coord[0]), float(coord[1])))
                return
            if geom_type == "MultiLineString":
                for line in geometry.geoms:
                    add_intersection_points(line, out)
                return
            if geom_type == "GeometryCollection":
                for child in geometry.geoms:
                    add_intersection_points(child, out)

        split_points: list[tuple[float, tuple[float, float]]] = []
        eps = 1e-8
        ordered_points: list[tuple[float, float]] = []
        for index, start in enumerate(points):
            end = points[(index + 1) % len(points)]
            line = LineString((start, end))
            candidates = [start, end]
            for boundary in boundaries:
                intersection = line.intersection(boundary)
                if not intersection.is_empty:
                    add_intersection_points(intersection, candidates)
            dx = float(end[0] - start[0])
            dy = float(end[1] - start[1])
            denom = dx * dx + dy * dy
            if denom <= 1e-18:
                continue
            split_points.clear()
            for point in candidates:
                t = ((float(point[0] - start[0]) * dx) + (float(point[1] - start[1]) * dy)) / denom
                if -eps <= t <= 1.0 + eps:
                    split_points.append((min(1.0, max(0.0, t)), (float(point[0]), float(point[1]))))
            split_points.sort(key=lambda item: item[0])
            for _, point in split_points:
                if ordered_points and abs(ordered_points[-1][0] - point[0]) <= eps and abs(ordered_points[-1][1] - point[1]) <= eps:
                    continue
                ordered_points.append(point)
        if (
            len(ordered_points) > 1
            and abs(ordered_points[0][0] - ordered_points[-1][0]) <= eps
            and abs(ordered_points[0][1] - ordered_points[-1][1]) <= eps
        ):
            ordered_points.pop()
        return ordered_points if len(ordered_points) >= 3 else points

    def split_polygon_at_boundaries(polygon: Any, boundaries: list[Any]) -> Any:
        if not boundaries:
            return polygon
        exterior = [
            (float(x), float(y))
            for x, y in list(polygon.exterior.coords)[:-1]
        ]
        exterior = split_ring_points_at_boundaries(exterior, boundaries)
        holes = []
        for interior in polygon.interiors:
            ring = [
                (float(x), float(y))
                for x, y in list(interior.coords)[:-1]
            ]
            split_ring = split_ring_points_at_boundaries(ring, boundaries)
            if len(split_ring) >= 3:
                holes.append(split_ring)
        split = Polygon(exterior, holes)
        if not split.is_valid:
            split = split.buffer(0)
        return split if not split.is_empty else polygon

    slabs: list[dict[str, Any]] = []
    for left, right in zip(axis_values, axis_values[1:], strict=False):
        if right <= left + 1e-9:
            continue
        mid = (float(left) + float(right)) * 0.5
        active = [
            entry["polygon"]
            for entry in entries
            if float(entry["low"]) <= mid + 1e-9 and float(entry["high"]) >= mid - 1e-9
        ]
        if not active:
            continue
        union = unary_union(active)
        if union.is_empty or not polygons(union):
            continue
        slabs.append({"low": float(left), "high": float(right), "geometry": union})
    if not slabs:
        return None
    global_split_boundaries = [slab["geometry"].boundary for slab in slabs]

    vertices: list[tuple[float, float, float]] = []
    vertex_index: dict[tuple[int, int, int], int] = {}
    faces: list[list[int]] = []

    def add_vertex(point: tuple[float, float], axial: float) -> int:
        coord = [0.0, 0.0, 0.0]
        coord[axis] = float(axial)
        coord[plane_axes[0]] = float(point[0])
        coord[plane_axes[1]] = float(point[1])
        key = tuple(int(round(value * 1_000_000)) for value in coord)
        existing = vertex_index.get(key)
        if existing is not None:
            return existing
        vertex_index[key] = len(vertices)
        vertices.append((coord[0], coord[1], coord[2]))
        return len(vertices) - 1

    def add_wall(
        a_point: tuple[float, float],
        b_point: tuple[float, float],
        *,
        low: float,
        high: float,
        reverse: bool,
    ) -> None:
        quad = [
            add_vertex(a_point, low),
            add_vertex(b_point, low),
            add_vertex(b_point, high),
            add_vertex(a_point, high),
        ]
        faces.append([quad[0], quad[1], quad[2]] if not reverse else [quad[0], quad[2], quad[1]])
        faces.append([quad[0], quad[2], quad[3]] if not reverse else [quad[0], quad[3], quad[2]])

    cap_triangle_count = 0

    def add_cap(
        geometry: Any,
        axial: float,
        *,
        reverse: bool,
        boundaries: list[Any] | None = None,
    ) -> int:
        count = 0
        boundaries = boundaries or []
        for polygon in polygons(geometry):
            polygon = split_polygon_at_boundaries(polygon, boundaries)
            if polygon.is_empty or float(polygon.area) <= 1e-9:
                continue
            try:
                vertices_2d, faces_2d = trimesh.creation.triangulate_polygon(
                    polygon,
                    force_vertices=True,
                )
            except (AttributeError, ValueError, RuntimeError, ImportError, ModuleNotFoundError):
                for triangle in triangulate(polygon):
                    if float(triangle.area) <= 1e-9 or not polygon.covers(triangle.representative_point()):
                        continue
                    coords = [(float(x), float(y)) for x, y in list(triangle.exterior.coords)[:3]]
                    tri = [add_vertex(point, axial) for point in coords]
                    faces.append([tri[0], tri[2], tri[1]] if reverse else tri)
                    count += 1
                continue
            for face in faces_2d:
                coords = [
                    (float(vertices_2d[int(index)][0]), float(vertices_2d[int(index)][1]))
                    for index in face[:3]
                ]
                if len(coords) < 3:
                    continue
                tri = [add_vertex(point, axial) for point in coords]
                faces.append([tri[0], tri[2], tri[1]] if reverse else tri)
                count += 1
        return count

    side_wall_face_count = 0
    for slab in slabs:
        low = float(slab["low"])
        high = float(slab["high"])
        neighbor_boundaries = [
            other["geometry"].boundary
            for other in slabs
            if other is not slab
            and (
                abs(float(other["high"]) - low) <= 1e-9
                or abs(float(other["low"]) - high) <= 1e-9
            )
        ]
        if global_split_boundaries:
            neighbor_boundaries = global_split_boundaries
        wall_polygons = polygons(slab["geometry"])
        if neighbor_boundaries:
            wall_polygons = [
                split_polygon_at_boundaries(polygon, neighbor_boundaries)
                for polygon in wall_polygons
            ]
        for polygon in wall_polygons:
            exterior = [(float(x), float(y)) for x, y in list(polygon.exterior.coords)[:-1]]
            for index, point in enumerate(exterior):
                add_wall(point, exterior[(index + 1) % len(exterior)], low=low, high=high, reverse=False)
                side_wall_face_count += 2
            for interior in polygon.interiors:
                ring = [(float(x), float(y)) for x, y in list(interior.coords)[:-1]]
                if len(ring) < 3:
                    continue
                for index, point in enumerate(ring):
                    add_wall(point, ring[(index + 1) % len(ring)], low=low, high=high, reverse=True)
                    side_wall_face_count += 2

    boundary_values = sorted({float(slab["low"]) for slab in slabs} | {float(slab["high"]) for slab in slabs})
    empty = Polygon()
    for axial in boundary_values:
        left_geometries = [slab["geometry"] for slab in slabs if abs(float(slab["high"]) - axial) <= 1e-9]
        right_geometries = [slab["geometry"] for slab in slabs if abs(float(slab["low"]) - axial) <= 1e-9]
        left_geometry = unary_union(left_geometries) if left_geometries else empty
        right_geometry = unary_union(right_geometries) if right_geometries else empty
        left_only = left_geometry.difference(right_geometry) if left_geometries else empty
        right_only = right_geometry.difference(left_geometry) if right_geometries else empty
        if not left_only.is_empty:
            cap_triangle_count += add_cap(
                left_only,
                axial,
                reverse=False,
                boundaries=global_split_boundaries,
            )
        if not right_only.is_empty:
            cap_triangle_count += add_cap(
                right_only,
                axial,
                reverse=True,
                boundaries=global_split_boundaries,
            )

    if not faces:
        return None
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    mesh.remove_unreferenced_vertices()
    try:
        mesh.update_faces(mesh.unique_faces())
        mesh.update_faces(mesh.nondegenerate_faces())
    except (AttributeError, IndexError, TypeError, ValueError):
        pass
    mesh.merge_vertices()
    mesh.fix_normals()
    slab_mesh_repaired = False
    slab_boundary_hole_fill_count = 0
    if not bool(mesh.is_watertight):
        repaired = mesh.copy()
        try:
            trimesh.repair.fill_holes(repaired)
        except (AttributeError, ImportError, TypeError, ValueError):
            repaired = mesh
        repaired.remove_unreferenced_vertices()
        try:
            repaired.update_faces(repaired.unique_faces())
            repaired.update_faces(repaired.nondegenerate_faces())
        except (AttributeError, IndexError, TypeError, ValueError):
            pass
        repaired.merge_vertices()
        repaired.fix_normals()
        if not bool(repaired.is_watertight):
            repaired, slab_boundary_hole_fill_count = _fill_planar_boundary_loops(repaired)
        if bool(repaired.is_watertight):
            mesh = repaired
            slab_mesh_repaired = True
    if not bool(mesh.is_watertight):
        return None
    return mesh, {
        "slab_count": len(slabs),
        "cap_triangle_count": cap_triangle_count,
        "side_wall_face_count": side_wall_face_count,
        "result_face_count": len(mesh.faces),
        "result_watertight": bool(mesh.is_watertight),
        "slab_mesh_repaired": slab_mesh_repaired,
        "slab_boundary_hole_fill_count": int(slab_boundary_hole_fill_count),
    }


def _mesh_from_box_blind_profile_cuts_with_raised_details(
    *,
    box_min: np.ndarray,
    box_max: np.ndarray,
    cut_axis: int,
    plane_axes: tuple[int, int],
    cuts: list[dict[str, Any]],
    details: list[dict[str, Any]],
    sections: int = 48,
) -> tuple[trimesh.Trimesh, dict[str, Any]] | None:
    try:
        from shapely.geometry import Polygon
        from shapely.errors import GEOSException
        from shapely.ops import unary_union
    except (ImportError, ModuleNotFoundError):
        return None
    if not cuts and not details:
        return None
    if cut_axis not in {0, 1, 2} or len(plane_axes) != 2 or set(plane_axes) != ({0, 1, 2} - {cut_axis}):
        return None

    rect = Polygon(
        (
            (float(box_min[plane_axes[0]]), float(box_min[plane_axes[1]])),
            (float(box_max[plane_axes[0]]), float(box_min[plane_axes[1]])),
            (float(box_max[plane_axes[0]]), float(box_max[plane_axes[1]])),
            (float(box_min[plane_axes[0]]), float(box_max[plane_axes[1]])),
        )
    )
    if rect.is_empty or float(rect.area) <= 1e-9:
        return None
    low = float(box_min[cut_axis])
    high = float(box_max[cut_axis])
    levels: set[float] = {low, high}
    sampled_segment_count = 0

    def valid_geometry(geometry: Any) -> Any | None:
        try:
            if not geometry.is_valid:
                geometry = geometry.buffer(0)
        except GEOSException:
            return None
        if geometry.is_empty or float(geometry.area) <= 1e-9:
            return None
        return geometry

    def rect_intersection(geometry: Any) -> Any | None:
        try:
            return valid_geometry(geometry.intersection(rect))
        except GEOSException:
            return None

    def geometry_difference(left: Any, right: Any) -> Any | None:
        try:
            return valid_geometry(left.difference(right))
        except GEOSException:
            return None

    def geometry_union(geometries: list[Any]) -> Any | None:
        try:
            return valid_geometry(unary_union(geometries))
        except GEOSException:
            return None

    def expanded_polygon(points: list[tuple[float, float]], width: float) -> Any | None:
        if width <= 1e-9 or len(points) < 3:
            return None
        polygon = valid_geometry(Polygon(points))
        if polygon is None:
            return None
        centroid = polygon.centroid
        cx = float(centroid.x)
        cy = float(centroid.y)
        expanded_points: list[tuple[float, float]] = []
        for point_x, point_y in points:
            dx = float(point_x) - cx
            dy = float(point_y) - cy
            length = math.hypot(dx, dy)
            if length <= 1e-9:
                expanded_points.append((float(point_x), float(point_y)))
            else:
                scale = (length + width) / length
                expanded_points.append((cx + dx * scale, cy + dy * scale))
        return rect_intersection(Polygon(expanded_points))

    prepared_cuts: list[dict[str, Any]] = []
    for raw_cut in cuts:
        cut = dict(raw_cut)
        cut_kind = str(cut.get("cut_kind") or "")
        if cut_kind not in {*_BLIND_PROFILE_CUT_KINDS, "extruded", "revolved"}:
            return None
        if cut_kind in {"extruded", "extruded_blind"}:
            try:
                profile_points = [
                    (float(point[0]), float(point[1]))
                    for point in cut["profile_points"]
                ]
            except (KeyError, TypeError, ValueError, IndexError):
                return None
            if len(profile_points) < 3:
                return None
            cutter = rect_intersection(Polygon(profile_points))
            if cutter is None:
                return None
            prepared = {
                **cut,
                "cut_kind": cut_kind,
                "profile_points": profile_points,
                "cutter": cutter,
            }
            if cut_kind == "extruded_blind":
                try:
                    floor_axial = float(cut["floor_axial_cm"])
                except (KeyError, TypeError, ValueError):
                    return None
                if floor_axial <= low + 1e-9 or floor_axial >= high - 1e-9:
                    return None
                open_side = 1 if str(cut.get("open_side") or "positive") == "positive" else -1
                levels.add(floor_axial)
                bevel_width = max(0.0, float(cut.get("bevel_width") or 0.0))
                bevel_depth = min(bevel_width, abs((high if open_side > 0 else low) - floor_axial) * 0.45)
                expanded = expanded_polygon(profile_points, bevel_width)
                if bevel_depth > 1e-9 and expanded is not None and float(expanded.area) > float(cutter.area) + 1e-9:
                    open_axial = high if open_side > 0 else low
                    shoulder_axial = open_axial - open_side * bevel_depth
                    levels.add(shoulder_axial)
                    segment_low = min(shoulder_axial, open_axial)
                    segment_high = max(shoulder_axial, open_axial)
                    for index in range(9):
                        levels.add(segment_low + (segment_high - segment_low) * (index / 8.0))
                    sampled_segment_count += 1
                else:
                    expanded = None
                    bevel_depth = 0.0
                prepared.update(
                    {
                        "open_side": open_side,
                        "floor_axial": floor_axial,
                        "expanded_cutter": expanded,
                        "bevel_depth": bevel_depth,
                    }
                )
            else:
                levels.add(low)
                levels.add(high)
            prepared_cuts.append(prepared)
            continue

        try:
            rings = [
                (float(ring[0]), float(ring[1]))
                for ring in cut["rings"]
            ]
        except (KeyError, TypeError, ValueError, IndexError):
            return None
        if len(rings) < 2 or any(radius <= 0.0 for _, radius in rings):
            return None
        try:
            if "center" in cut:
                center = np.asarray(cut["center"], dtype=np.float64)
                if center.shape != (3,):
                    return None
                plane_center = np.asarray((center[plane_axes[0]], center[plane_axes[1]]), dtype=np.float64)
            else:
                plane_center = np.asarray(cut["plane_center"], dtype=np.float64)
        except (KeyError, TypeError, ValueError):
            return None
        if plane_center.shape != (2,):
            return None
        if cut_kind in _BLIND_PROFILE_CUT_KINDS:
            try:
                floor_axial = float(cut["floor_axial_cm"])
            except (KeyError, TypeError, ValueError):
                return None
            if floor_axial <= low + 1e-9 or floor_axial >= high - 1e-9:
                return None
            open_side = 1 if str(cut.get("open_side") or "positive") == "positive" else -1
            levels.add(floor_axial)
        else:
            floor_axial = 0.0
            open_side = 0
        for axial, _ in rings:
            levels.add(float(axial))
        for (left_axial, left_radius), (right_axial, right_radius) in zip(rings, rings[1:], strict=False):
            if abs(float(left_radius) - float(right_radius)) <= 1e-9:
                continue
            segment_low = min(float(left_axial), float(right_axial))
            segment_high = max(float(left_axial), float(right_axial))
            for index in range(9):
                levels.add(segment_low + (segment_high - segment_low) * (index / 8.0))
            sampled_segment_count += 1
        prepared_cuts.append(
            {
                **cut,
                "cut_kind": cut_kind,
                "rings": rings,
                "plane_center": plane_center,
                **(
                    {
                        "open_side": open_side,
                        "floor_axial": floor_axial,
                    }
                    if cut_kind in _BLIND_PROFILE_CUT_KINDS
                    else {}
                ),
            }
        )

    prepared_details: list[dict[str, Any]] = []
    detail_styles: list[str] = []
    for raw_detail in details:
        detail = dict(raw_detail)
        try:
            rings = [
                (float(ring[0]), float(ring[1]))
                for ring in detail["rings"]
            ]
            profile_points = [
                (float(point[0]), float(point[1]))
                for point in detail["profile_points"]
            ]
        except (KeyError, TypeError, ValueError, IndexError):
            return None
        if len(rings) < 2 or len(profile_points) < 3:
            return None
        detail_low = min(float(rings[0][0]), float(rings[-1][0]))
        detail_high = max(float(rings[0][0]), float(rings[-1][0]))
        if detail_high <= detail_low + 1e-9:
            return None
        profile_holes = [
            [
                (float(point[0]), float(point[1]))
                for point in hole
            ]
            for hole in detail.get("profile_holes", [])
        ]
        profile_rings = None
        if detail.get("profile_rings") is not None:
            try:
                profile_rings = [
                    [
                        (float(point[0]), float(point[1]))
                        for point in ring
                    ]
                    for ring in detail["profile_rings"]
                ]
            except (TypeError, ValueError, IndexError):
                return None
            if len(profile_rings) != len(rings) or any(len(ring) != len(profile_points) for ring in profile_rings):
                return None
            for (left_axial, _), (right_axial, _) in zip(rings, rings[1:], strict=False):
                segment_low = min(float(left_axial), float(right_axial))
                segment_high = max(float(left_axial), float(right_axial))
                for index in range(9):
                    levels.add(segment_low + (segment_high - segment_low) * (index / 8.0))
                sampled_segment_count += 1
        for axial, _ in rings:
            levels.add(float(axial))
        footprint = valid_geometry(Polygon(profile_points, profile_holes).intersection(rect))
        if footprint is None:
            return None
        detail_styles.append(str(detail.get("style") or "rectangular_box_detail"))
        prepared_details.append(
            {
                **detail,
                "rings": rings,
                "profile_points": profile_points,
                "profile_holes": profile_holes,
                "profile_rings": profile_rings,
                "low": detail_low,
                "high": detail_high,
                "footprint": footprint,
            }
        )

    def cut_polygon_at_axial(cut: dict[str, Any], axial: float) -> Any | None:
        cut_kind = str(cut["cut_kind"])
        if cut_kind in _BLIND_PROFILE_CUT_KINDS:
            open_side = int(cut["open_side"])
            floor_axial = float(cut["floor_axial"])
            open_axial = high if open_side > 0 else low
            if open_side > 0:
                if axial < floor_axial - 1e-9 or axial > high + 1e-9:
                    return None
            elif axial > floor_axial + 1e-9 or axial < low - 1e-9:
                return None
        else:
            open_side = 0
            open_axial = high
        if cut_kind == "extruded":
            return cut["cutter"]
        if cut_kind == "extruded_blind":
            expanded = cut.get("expanded_cutter")
            bevel_depth = float(cut.get("bevel_depth") or 0.0)
            if expanded is not None and bevel_depth > 1e-9:
                shoulder_axial = open_axial - open_side * bevel_depth
                if (
                    (open_side > 0 and axial > shoulder_axial + 1e-9)
                    or (open_side < 0 and axial < shoulder_axial - 1e-9)
                ):
                    return expanded
            return cut["cutter"]
        rings = cut["rings"]
        radius = _radius_at_profile_axial(rings, float(axial))
        if radius is None or radius <= 0.0:
            return None
        return rect_intersection(Polygon(_circle_points(cut["plane_center"], radius, sections=sections)))

    def detail_polygon_at_axial(detail: dict[str, Any], axial: float) -> Any | None:
        if axial < float(detail["low"]) - 1e-9 or axial > float(detail["high"]) + 1e-9:
            return None
        rings = detail["rings"]
        profile_rings = detail.get("profile_rings")
        points = detail["profile_points"]
        if profile_rings is not None:
            for index, ((left_axial, _), (right_axial, _)) in enumerate(zip(rings, rings[1:], strict=False)):
                segment_low = min(float(left_axial), float(right_axial))
                segment_high = max(float(left_axial), float(right_axial))
                if axial < segment_low - 1e-9 or axial > segment_high + 1e-9:
                    continue
                denominator = max(abs(float(right_axial) - float(left_axial)), 1e-9)
                t = min(1.0, max(0.0, abs(float(axial) - float(left_axial)) / denominator))
                left_ring = profile_rings[index]
                right_ring = profile_rings[index + 1]
                points = [
                    (
                        left_x + (right_x - left_x) * t,
                        left_y + (right_y - left_y) * t,
                    )
                    for (left_x, left_y), (right_x, right_y) in zip(left_ring, right_ring, strict=True)
                ]
                break
        return rect_intersection(Polygon(points, detail["profile_holes"]))

    entries: list[dict[str, Any]] = []
    axis_levels = _axis_values(*levels)
    for left, right in zip(axis_levels, axis_levels[1:], strict=False):
        if right <= left + 1e-9:
            continue
        mid = (left + right) * 0.5
        cut_polygons = [
            polygon
            for polygon in (cut_polygon_at_axial(cut, mid) for cut in prepared_cuts)
            if polygon is not None and not polygon.is_empty
        ]
        cut_union = geometry_union(cut_polygons) if cut_polygons else None
        base = geometry_difference(rect, cut_union) if cut_union is not None else rect
        base = valid_geometry(base) if base is not None else None
        active = []
        if base is not None:
            active.append(base)
        active.extend(
            polygon
            for polygon in (detail_polygon_at_axial(detail, mid) for detail in prepared_details)
            if polygon is not None and not polygon.is_empty
        )
        if not active:
            continue
        union = geometry_union(active)
        if union is None:
            continue
        entries.append({"polygon": union, "low": float(left), "high": float(right)})
    if not entries:
        return None
    built = _mesh_from_axis_extruded_polygon_union(
        entries,
        axis=cut_axis,
        plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
    )
    if built is None:
        return None
    mesh, stats = built
    return mesh, {
        **stats,
        "raised_detail_union": True,
        "profile_cut_state_blind_detail_union": bool(prepared_cuts),
        "blind_cut_count": len(prepared_cuts),
        "box_detail_count": len(prepared_details),
        "additive_detail_count": len(prepared_details),
        "boss_styles": sorted(set(detail_styles)),
        "profile_hole_count": sum(len(detail.get("profile_holes") or []) for detail in prepared_details),
        "sampled_axis_level_count": len(axis_levels),
        "sampled_segment_count": int(sampled_segment_count),
    }


def _exact_profile_cut_state_box_detail_union_ordered(
    base: trimesh.Trimesh,
    detail_mesh: trimesh.Trimesh,
) -> trimesh.Trimesh | None:
    state = _profile_cut_state_from_mesh(base)
    base_bounds = _box_bounds_from_metadata(base)
    detail_bounds = _box_bounds_from_metadata(detail_mesh)
    if state is None or base_bounds is None or detail_bounds is None:
        return None
    try:
        cut_axis = int(state["cut_axis"])
        plane_axes = tuple(int(value) for value in state["plane_axes"])
    except (KeyError, TypeError, ValueError):
        return None
    if cut_axis not in {0, 1, 2} or len(plane_axes) != 2 or set(plane_axes) != ({0, 1, 2} - {cut_axis}):
        return None
    blind_cuts = _existing_blind_profile_cuts_from_state(
        state,
        cut_axis=cut_axis,
        plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
    )
    if not blind_cuts:
        return None
    detail = _raised_box_detail_for_base(
        base_bounds=base_bounds,
        detail_bounds=detail_bounds,
        detail_mesh=detail_mesh,
    )
    if detail is None:
        return None
    detail_cut_axis, detail_plane_axes, side, detail_record = detail
    if detail_cut_axis != cut_axis or detail_plane_axes != (int(plane_axes[0]), int(plane_axes[1])):
        return None
    built = _mesh_from_box_blind_profile_cuts_with_raised_details(
        box_min=base_bounds[0],
        box_max=base_bounds[1],
        cut_axis=cut_axis,
        plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
        cuts=[dict(cut) for cut in blind_cuts],
        details=[dict(detail_record)],
    )
    if built is None:
        return None
    result, stats = built
    detail_record["part"] = str(detail_record.get("part") or _resolved_shape_primitive_metadata(detail_mesh).get("part") or "box_detail")
    result.metadata[_BOSS_STATE_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_boss_state.v1",
        "box_min": [float(value) for value in base_bounds[0]],
        "box_max": [float(value) for value in base_bounds[1]],
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "side": int(side),
        "bosses": [detail_record],
        "blind_cuts": [dict(cut) for cut in blind_cuts],
    }
    result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_exact_boolean.v1",
        "method": "axis_aligned_profile_cut_state_box_blind_detail_boss_union_v1",
        "op": "union",
        "overlap": True,
        "passthrough": False,
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "side": int(side),
        "profile_cut_state_consumed": True,
        "blind_cut_count": len(blind_cuts),
        "boss_count": 1,
        "box_detail_count": 1,
        "boss_styles": [str(detail_record.get("style") or "rectangular_box_detail")],
        "result_face_count": len(result.faces),
        "result_watertight": bool(result.is_watertight),
        **stats,
    }
    _set_batch_source_meshes(result, (result,))
    return result


def _exact_profile_cut_state_box_detail_union(
    a: trimesh.Trimesh,
    b: trimesh.Trimesh,
) -> trimesh.Trimesh | None:
    ordered = _exact_profile_cut_state_box_detail_union_ordered(a, b)
    if ordered is not None:
        return ordered
    return _exact_profile_cut_state_box_detail_union_ordered(b, a)


def _exact_profile_cut_state_box_detail_batch_union(
    meshes: list[trimesh.Trimesh],
) -> trimesh.Trimesh | None:
    if len(meshes) < 2:
        return None
    base_candidates: list[
        tuple[int, trimesh.Trimesh, dict[str, Any], tuple[np.ndarray, np.ndarray], list[dict[str, Any]]]
    ] = []
    for index, mesh in enumerate(meshes):
        state = _profile_cut_state_from_mesh(mesh)
        bounds = _box_bounds_from_metadata(mesh)
        if state is None or bounds is None:
            continue
        try:
            candidate_cut_axis = int(state["cut_axis"])
            candidate_plane_axes = tuple(int(value) for value in state["plane_axes"])
        except (KeyError, TypeError, ValueError):
            continue
        if (
            candidate_cut_axis not in {0, 1, 2}
            or len(candidate_plane_axes) != 2
            or set(candidate_plane_axes) != ({0, 1, 2} - {candidate_cut_axis})
        ):
            continue
        candidate_blind_cuts = _existing_blind_profile_cuts_from_state(
            state,
            cut_axis=candidate_cut_axis,
            plane_axes=(int(candidate_plane_axes[0]), int(candidate_plane_axes[1])),
        )
        if candidate_blind_cuts:
            base_candidates.append((index, mesh, state, bounds, candidate_blind_cuts))
    if len(base_candidates) != 1:
        return None
    base_index, _base_mesh, state, base_bounds, blind_cuts = base_candidates[0]
    try:
        cut_axis = int(state["cut_axis"])
        plane_axes = tuple(int(value) for value in state["plane_axes"])
    except (KeyError, TypeError, ValueError):
        return None
    if cut_axis not in {0, 1, 2} or len(plane_axes) != 2 or set(plane_axes) != ({0, 1, 2} - {cut_axis}):
        return None
    if not blind_cuts:
        return None
    detail_records: list[dict[str, Any]] = []
    sides: set[int] = set()
    for index, detail_mesh in enumerate(meshes):
        if index == base_index:
            continue
        if _boss_state_from_mesh(detail_mesh) is not None:
            return None
        detail_state = _profile_cut_state_from_mesh(detail_mesh)
        if detail_state is not None:
            try:
                detail_cut_axis = int(detail_state["cut_axis"])
                detail_plane_axes = tuple(int(value) for value in detail_state["plane_axes"])
            except (KeyError, TypeError, ValueError):
                return None
            detail_blind_cuts = _existing_blind_profile_cuts_from_state(
                detail_state,
                cut_axis=detail_cut_axis,
                plane_axes=(int(detail_plane_axes[0]), int(detail_plane_axes[1])),
            )
            if detail_blind_cuts:
                return None
        detail_bounds = _box_bounds_from_metadata(detail_mesh)
        if detail_bounds is None:
            return None
        detail = _raised_box_detail_for_base(
            base_bounds=base_bounds,
            detail_bounds=detail_bounds,
            detail_mesh=detail_mesh,
        )
        if detail is None:
            return None
        detail_cut_axis, detail_plane_axes, side, detail_record = detail
        if detail_cut_axis != cut_axis or detail_plane_axes != (int(plane_axes[0]), int(plane_axes[1])):
            return None
        detail_record = dict(detail_record)
        detail_record["part"] = str(
            detail_record.get("part")
            or _resolved_shape_primitive_metadata(detail_mesh).get("part")
            or "box_detail"
        )
        detail_records.append(detail_record)
        sides.add(int(side))
    if not detail_records or len(sides) != 1:
        return None
    side = next(iter(sides))
    built = _mesh_from_box_blind_profile_cuts_with_raised_details(
        box_min=base_bounds[0],
        box_max=base_bounds[1],
        cut_axis=cut_axis,
        plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
        cuts=[dict(cut) for cut in blind_cuts],
        details=[dict(detail) for detail in detail_records],
    )
    if built is None:
        return None
    result, stats = built
    if not bool(result.is_watertight):
        return None
    result.metadata[_BOSS_STATE_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_boss_state.v1",
        "box_min": [float(value) for value in base_bounds[0]],
        "box_max": [float(value) for value in base_bounds[1]],
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "side": int(side),
        "bosses": [dict(detail) for detail in detail_records],
        "blind_cuts": [dict(cut) for cut in blind_cuts],
    }
    batch_payload = {
        "schema": "lathe.geometry.reference_batch_union.v1",
        "method": "axis_aligned_profile_cut_state_box_blind_detail_boss_batch_union_v1",
        "operand_count": len(meshes),
        "profile_cut_state_consumed": True,
        "blind_cut_count": len(blind_cuts),
        "boss_count": len(detail_records),
        "box_detail_count": len(detail_records),
        "result_face_count": len(result.faces),
        "result_watertight": bool(result.is_watertight),
        **stats,
    }
    result.metadata["lathe_reference_batch_union"] = batch_payload
    result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_exact_boolean.v1",
        "method": "axis_aligned_profile_cut_state_box_blind_detail_boss_batch_union_v1",
        "op": "batch_union",
        "overlap": True,
        "passthrough": False,
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "side": int(side),
        "profile_cut_state_consumed": True,
        "blind_cut_count": len(blind_cuts),
        "boss_count": len(detail_records),
        "box_detail_count": len(detail_records),
        "result_face_count": len(result.faces),
        "result_watertight": bool(result.is_watertight),
        **stats,
    }
    return _set_batch_source_meshes(result, meshes)


def _exact_axis_aligned_box_extruded_profile_batch_union(meshes: list[trimesh.Trimesh]) -> trimesh.Trimesh | None:
    profile_items: list[tuple[trimesh.Trimesh, dict[str, Any]]] = []
    box_items: list[tuple[trimesh.Trimesh, tuple[np.ndarray, np.ndarray]]] = []
    for mesh in meshes:
        if _profile_cut_state_from_mesh(mesh) is not None or _boss_state_from_mesh(mesh) is not None:
            return None
        profile = _extruded_profile_metadata(mesh)
        if profile is not None:
            profile_items.append((mesh, profile))
            continue
        bounds = _box_bounds_from_metadata(mesh)
        if bounds is not None:
            box_items.append((mesh, bounds))
            continue
        return None
    if not profile_items or not box_items:
        return None
    axis_name = str(profile_items[0][1]["axis"])
    if any(str(profile["axis"]) != axis_name for _, profile in profile_items):
        return None
    axis = {"x": 0, "y": 1, "z": 2}[axis_name]
    plane_axes = tuple(index for index in range(3) if index != axis)
    try:
        from shapely.geometry import Polygon
    except (ImportError, ModuleNotFoundError):
        return None
    entries: list[dict[str, Any]] = []
    for _, bounds in box_items:
        bmin, bmax = bounds
        polygon = Polygon(
            (
                (float(bmin[plane_axes[0]]), float(bmin[plane_axes[1]])),
                (float(bmax[plane_axes[0]]), float(bmin[plane_axes[1]])),
                (float(bmax[plane_axes[0]]), float(bmax[plane_axes[1]])),
                (float(bmin[plane_axes[0]]), float(bmax[plane_axes[1]])),
            )
        )
        if polygon.is_empty or float(polygon.area) <= 1e-9:
            return None
        entries.append({"low": float(bmin[axis]), "high": float(bmax[axis]), "polygon": polygon})
    for _, profile in profile_items:
        converted = _extruded_profile_plane_points(profile)
        if converted is None:
            return None
        profile_axis, profile_plane_axes, points = converted
        if profile_axis != axis or profile_plane_axes != (int(plane_axes[0]), int(plane_axes[1])):
            return None
        polygon = Polygon(points)
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        if polygon.is_empty or float(polygon.area) <= 1e-9:
            return None
        center = np.asarray(profile["center"], dtype=np.float64)
        half_height = float(profile["extrude_height"]) * 0.5
        entries.append(
            {
                "low": float(center[axis] - half_height),
                "high": float(center[axis] + half_height),
                "polygon": polygon,
            }
        )
    built = _mesh_from_axis_extruded_polygon_union(
        entries,
        axis=axis,
        plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
    )
    if built is None:
        return None
    result, stats = built
    _set_batch_source_meshes(result, meshes)
    result.metadata["lathe_reference_batch_union"] = {
        "schema": "lathe.geometry.reference_batch_union.v1",
        "method": "axis_aligned_box_extruded_profile_batch_union_v1",
        "operand_count": len(meshes),
        "box_count": len(box_items),
        "extruded_profile_count": len(profile_items),
        "axis": axis_name,
        **stats,
    }
    result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_exact_boolean.v1",
        "method": "axis_aligned_box_extruded_profile_batch_union_v1",
        "op": "batch_union",
        "operand_count": len(meshes),
        "box_count": len(box_items),
        "extruded_profile_count": len(profile_items),
        "axis": axis_name,
        "passthrough": False,
        **stats,
    }
    return result


def _extruded_profile_plane_points(
    metadata: dict[str, Any],
) -> tuple[int, tuple[int, int], list[tuple[float, float]]] | None:
    axis = str(metadata["axis"])
    axis_index = {"x": 0, "y": 1, "z": 2}[axis]
    plane_axes = tuple(index for index in range(3) if index != axis_index)
    center = np.asarray(metadata["center"], dtype=np.float64)
    points: list[tuple[float, float]] = []
    for u_value, v_value in metadata["profile_polygon"]:
        u = float(u_value)
        v = float(v_value)
        if axis == "z":
            world = np.asarray((center[0] + u, center[1] + v, center[2]), dtype=np.float64)
        elif axis == "y":
            world = np.asarray((center[0] + u, center[1], center[2] - v), dtype=np.float64)
        else:
            world = np.asarray((center[0], center[1] + v, center[2] - u), dtype=np.float64)
        points.append((float(world[plane_axes[0]]), float(world[plane_axes[1]])))
    return axis_index, (int(plane_axes[0]), int(plane_axes[1])), points


def _mesh_from_box_through_profile_cut(
    *,
    box_min: np.ndarray,
    box_max: np.ndarray,
    cut_axis: int,
    plane_axes: tuple[int, int],
    profile_points: list[tuple[float, float]],
    bevel_width: float = 0.0,
    bevel_segments: int = 1,
) -> tuple[trimesh.Trimesh, dict[str, Any]] | None:
    try:
        from shapely.geometry import LineString, Polygon
        from shapely.ops import triangulate
    except (ImportError, ModuleNotFoundError):
        return None

    rect = Polygon(
        (
            (float(box_min[plane_axes[0]]), float(box_min[plane_axes[1]])),
            (float(box_max[plane_axes[0]]), float(box_min[plane_axes[1]])),
            (float(box_max[plane_axes[0]]), float(box_max[plane_axes[1]])),
            (float(box_min[plane_axes[0]]), float(box_max[plane_axes[1]])),
        )
    )
    cutter = Polygon(profile_points)
    if not cutter.is_valid:
        cutter = cutter.buffer(0)
    if cutter.is_empty or float(cutter.area) <= 1e-9:
        return None
    if not rect.contains(cutter):
        return None
    bevel_width = max(0.0, float(bevel_width))
    cap_cutter = cutter
    bevel_ring = False
    expanded_points: list[tuple[float, float]] = []
    if bevel_width > 1e-9:
        centroid = cutter.centroid
        cx = float(centroid.x)
        cy = float(centroid.y)
        for point_x, point_y in profile_points:
            dx = float(point_x) - cx
            dy = float(point_y) - cy
            length = math.hypot(dx, dy)
            if length <= 1e-9:
                expanded_points.append((float(point_x), float(point_y)))
            else:
                scale = (length + bevel_width) / length
                expanded_points.append((cx + dx * scale, cy + dy * scale))
        expanded = Polygon(expanded_points)
        if not expanded.is_valid:
            expanded = expanded.buffer(0)
        if (
            not expanded.is_empty
            and float(expanded.area) > float(cutter.area)
            and rect.contains(expanded)
        ):
            cap_cutter = expanded
            bevel_ring = True

    remaining = rect.difference(cap_cutter)
    if remaining.is_empty or float(remaining.area) <= 1e-9:
        return None

    vertices: list[tuple[float, float, float]] = []
    vertex_index: dict[tuple[int, int, int], int] = {}
    faces: list[list[int]] = []

    def add_vertex(plane_point: tuple[float, float], axial: float) -> int:
        coord = [0.0, 0.0, 0.0]
        coord[cut_axis] = float(axial)
        coord[plane_axes[0]] = float(plane_point[0])
        coord[plane_axes[1]] = float(plane_point[1])
        key = tuple(int(round(value * 1_000_000)) for value in coord)
        existing = vertex_index.get(key)
        if existing is not None:
            return existing
        vertex_index[key] = len(vertices)
        vertices.append((coord[0], coord[1], coord[2]))
        return len(vertices) - 1

    def add_triangle(points: list[tuple[float, float]], axial: float, *, reverse: bool) -> None:
        if len(points) < 3:
            return
        tri = [add_vertex(point, axial) for point in points[:3]]
        faces.append([tri[0], tri[2], tri[1]] if reverse else tri)

    def add_wall(
        a_point: tuple[float, float],
        b_point: tuple[float, float],
        *,
        reverse: bool,
        low: float | None = None,
        high: float | None = None,
    ) -> None:
        low = float(box_min[cut_axis]) if low is None else float(low)
        high = float(box_max[cut_axis]) if high is None else float(high)
        quad = [
            add_vertex(a_point, low),
            add_vertex(b_point, low),
            add_vertex(b_point, high),
            add_vertex(a_point, high),
        ]
        faces.append([quad[0], quad[1], quad[2]] if not reverse else [quad[0], quad[2], quad[1]])
        faces.append([quad[0], quad[2], quad[3]] if not reverse else [quad[0], quad[3], quad[2]])

    cap_triangle_count = 0
    for triangle in triangulate(remaining):
        if float(triangle.area) <= 1e-9 or not remaining.covers(triangle.representative_point()):
            continue
        coords = [(float(x), float(y)) for x, y in list(triangle.exterior.coords)[:3]]
        add_triangle(coords, float(box_min[cut_axis]), reverse=True)
        add_triangle(coords, float(box_max[cut_axis]), reverse=False)
        cap_triangle_count += 2

    rect_ring = [(float(x), float(y)) for x, y in list(rect.exterior.coords)]
    for index in range(len(rect_ring) - 1):
        add_wall(rect_ring[index], rect_ring[index + 1], reverse=False)

    cutter_ring = [(float(x), float(y)) for x, y in list(cutter.exterior.coords)]
    cap_ring = [(float(x), float(y)) for x, y in list(cap_cutter.exterior.coords)]
    inner_wall_face_count = 0
    bevel_face_count = 0
    if bevel_ring and len(expanded_points) == len(profile_points):
        low = float(box_min[cut_axis])
        high = float(box_max[cut_axis])
        bevel_depth = min(bevel_width, max((high - low) * 0.45, 0.0))
        low_inner = low + bevel_depth
        high_inner = high - bevel_depth
        segment_count = max(1, int(bevel_segments))

        def add_quad_points(
            points: tuple[
                tuple[tuple[float, float], float],
                tuple[tuple[float, float], float],
                tuple[tuple[float, float], float],
                tuple[tuple[float, float], float],
            ],
            *,
            reverse: bool,
        ) -> None:
            quad = [add_vertex(point, axial) for point, axial in points]
            faces.append([quad[0], quad[1], quad[2]] if not reverse else [quad[0], quad[2], quad[1]])
            faces.append([quad[0], quad[2], quad[3]] if not reverse else [quad[0], quad[3], quad[2]])

        def lerp_point(
            a_point: tuple[float, float],
            b_point: tuple[float, float],
            t: float,
        ) -> tuple[float, float]:
            return (
                float(a_point[0]) + (float(b_point[0]) - float(a_point[0])) * t,
                float(a_point[1]) + (float(b_point[1]) - float(a_point[1])) * t,
            )

        for index in range(len(profile_points)):
            next_index = (index + 1) % len(profile_points)
            outer_a = expanded_points[index]
            outer_b = expanded_points[next_index]
            inner_a = profile_points[index]
            inner_b = profile_points[next_index]
            for segment in range(segment_count):
                t0 = segment / segment_count
                t1 = (segment + 1) / segment_count
                low_a0 = lerp_point(outer_a, inner_a, t0)
                low_b0 = lerp_point(outer_b, inner_b, t0)
                low_a1 = lerp_point(outer_a, inner_a, t1)
                low_b1 = lerp_point(outer_b, inner_b, t1)
                low_z0 = low + (low_inner - low) * t0
                low_z1 = low + (low_inner - low) * t1
                add_quad_points(
                    (
                        (low_a0, low_z0),
                        (low_b0, low_z0),
                        (low_b1, low_z1),
                        (low_a1, low_z1),
                    ),
                    reverse=True,
                )
                high_a0 = lerp_point(inner_a, outer_a, t0)
                high_b0 = lerp_point(inner_b, outer_b, t0)
                high_a1 = lerp_point(inner_a, outer_a, t1)
                high_b1 = lerp_point(inner_b, outer_b, t1)
                high_z0 = high_inner + (high - high_inner) * t0
                high_z1 = high_inner + (high - high_inner) * t1
                add_quad_points(
                    (
                        (high_a0, high_z0),
                        (high_b0, high_z0),
                        (high_b1, high_z1),
                        (high_a1, high_z1),
                    ),
                    reverse=False,
                )
                bevel_face_count += 4
        if high_inner > low_inner + 1e-9:
            for index in range(len(cutter_ring) - 1):
                add_wall(cutter_ring[index], cutter_ring[index + 1], reverse=True, low=low_inner, high=high_inner)
                inner_wall_face_count += 2
    else:
        for index in range(len(cutter_ring) - 1):
            add_wall(cutter_ring[index], cutter_ring[index + 1], reverse=True)
            inner_wall_face_count += 2

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()
    mesh.fix_normals()
    return mesh, {
        "cap_triangle_count": cap_triangle_count,
        "inner_wall_face_count": inner_wall_face_count,
        "bevel_face_count": bevel_face_count,
        "bevel_width_cm": bevel_width if bevel_ring else 0.0,
        "bevel_segments": max(1, int(bevel_segments)) if bevel_ring else 0,
        "bevel_applied": bevel_ring,
        "profile_vertex_count": max(0, len(cutter_ring) - 1),
        "cap_profile_vertex_count": max(0, len(cap_ring) - 1),
    }


def _mesh_from_box_blind_profile_cut(
    *,
    box_min: np.ndarray,
    box_max: np.ndarray,
    cut_axis: int,
    plane_axes: tuple[int, int],
    profile_points: list[tuple[float, float]],
    open_side: int,
    floor_axial: float,
    bevel_width: float,
    bevel_segments: int = 1,
) -> tuple[trimesh.Trimesh, dict[str, Any]] | None:
    try:
        from shapely.geometry import Polygon
        from shapely.ops import triangulate
    except (ImportError, ModuleNotFoundError):
        return None

    rect = Polygon(
        (
            (float(box_min[plane_axes[0]]), float(box_min[plane_axes[1]])),
            (float(box_max[plane_axes[0]]), float(box_min[plane_axes[1]])),
            (float(box_max[plane_axes[0]]), float(box_max[plane_axes[1]])),
            (float(box_min[plane_axes[0]]), float(box_max[plane_axes[1]])),
        )
    )
    cutter = Polygon(profile_points)
    if not cutter.is_valid:
        cutter = cutter.buffer(0)
    if cutter.is_empty or float(cutter.area) <= 1e-9 or not rect.contains(cutter):
        return None

    bevel_width = max(0.0, float(bevel_width))
    cap_cutter = cutter
    bevel_ring = False
    expanded_points: list[tuple[float, float]] = []
    if bevel_width > 1e-9:
        centroid = cutter.centroid
        cx = float(centroid.x)
        cy = float(centroid.y)
        for point_x, point_y in profile_points:
            dx = float(point_x) - cx
            dy = float(point_y) - cy
            length = math.hypot(dx, dy)
            if length <= 1e-9:
                expanded_points.append((float(point_x), float(point_y)))
            else:
                scale = (length + bevel_width) / length
                expanded_points.append((cx + dx * scale, cy + dy * scale))
        expanded = Polygon(expanded_points)
        if not expanded.is_valid:
            expanded = expanded.buffer(0)
        if (
            not expanded.is_empty
            and float(expanded.area) > float(cutter.area)
            and rect.contains(expanded)
        ):
            cap_cutter = expanded
            bevel_ring = True

    remaining_open_cap = rect.difference(cap_cutter)
    if remaining_open_cap.is_empty or float(remaining_open_cap.area) <= 1e-9:
        return None

    low = float(box_min[cut_axis])
    high = float(box_max[cut_axis])
    open_axial = high if int(open_side) >= 0 else low
    floor_axial = float(floor_axial)
    if int(open_side) >= 0:
        if floor_axial <= low + 1e-9 or floor_axial >= high - 1e-9:
            return None
        bevel_depth = min(bevel_width, max((open_axial - floor_axial) * 0.45, 0.0))
        inner_axial = open_axial - bevel_depth if bevel_ring else open_axial
        floor_reverse = False
        open_cap_reverse = False
    else:
        if floor_axial <= low + 1e-9 or floor_axial >= high - 1e-9:
            return None
        bevel_depth = min(bevel_width, max((floor_axial - open_axial) * 0.45, 0.0))
        inner_axial = open_axial + bevel_depth if bevel_ring else open_axial
        floor_reverse = True
        open_cap_reverse = True

    vertices: list[tuple[float, float, float]] = []
    vertex_index: dict[tuple[int, int, int], int] = {}
    faces: list[list[int]] = []

    def add_vertex(plane_point: tuple[float, float], axial: float) -> int:
        coord = [0.0, 0.0, 0.0]
        coord[cut_axis] = float(axial)
        coord[plane_axes[0]] = float(plane_point[0])
        coord[plane_axes[1]] = float(plane_point[1])
        key = tuple(int(round(value * 1_000_000)) for value in coord)
        existing = vertex_index.get(key)
        if existing is not None:
            return existing
        vertex_index[key] = len(vertices)
        vertices.append((coord[0], coord[1], coord[2]))
        return len(vertices) - 1

    def add_triangle(
        points: list[tuple[float, float]],
        axial: float,
        *,
        reverse: bool,
    ) -> None:
        triangle = [add_vertex(point, axial) for point in points]
        faces.append([triangle[0], triangle[2], triangle[1]] if reverse else triangle)

    def add_wall(
        a_point: tuple[float, float],
        b_point: tuple[float, float],
        *,
        wall_low: float,
        wall_high: float,
        reverse: bool,
    ) -> None:
        quad = [
            add_vertex(a_point, wall_low),
            add_vertex(b_point, wall_low),
            add_vertex(b_point, wall_high),
            add_vertex(a_point, wall_high),
        ]
        faces.append([quad[0], quad[1], quad[2]] if not reverse else [quad[0], quad[2], quad[1]])
        faces.append([quad[0], quad[2], quad[3]] if not reverse else [quad[0], quad[3], quad[2]])

    cap_triangle_count = 0
    for triangle in triangulate(remaining_open_cap):
        if float(triangle.area) <= 1e-9 or not remaining_open_cap.covers(triangle.representative_point()):
            continue
        coords = [(float(x), float(y)) for x, y in list(triangle.exterior.coords)[:3]]
        add_triangle(coords, open_axial, reverse=open_cap_reverse)
        cap_triangle_count += 1
    opposite_axial = low if int(open_side) >= 0 else high
    for triangle in triangulate(rect):
        if float(triangle.area) <= 1e-9 or not rect.covers(triangle.representative_point()):
            continue
        coords = [(float(x), float(y)) for x, y in list(triangle.exterior.coords)[:3]]
        add_triangle(coords, opposite_axial, reverse=int(open_side) >= 0)
        cap_triangle_count += 1

    floor_triangle_count = 0
    for triangle in triangulate(cutter):
        if float(triangle.area) <= 1e-9 or not cutter.covers(triangle.representative_point()):
            continue
        coords = [(float(x), float(y)) for x, y in list(triangle.exterior.coords)[:3]]
        add_triangle(coords, floor_axial, reverse=floor_reverse)
        floor_triangle_count += 1

    rect_ring = [(float(x), float(y)) for x, y in list(rect.exterior.coords)]
    for index in range(len(rect_ring) - 1):
        add_wall(rect_ring[index], rect_ring[index + 1], wall_low=low, wall_high=high, reverse=False)

    bevel_face_count = 0
    cutter_ring = [(float(x), float(y)) for x, y in list(cutter.exterior.coords)]
    if bevel_ring and len(expanded_points) == len(profile_points):
        segment_count = max(1, int(bevel_segments))

        def add_quad_points(
            points: tuple[
                tuple[tuple[float, float], float],
                tuple[tuple[float, float], float],
                tuple[tuple[float, float], float],
                tuple[tuple[float, float], float],
            ],
            *,
            reverse: bool,
        ) -> None:
            quad = [add_vertex(point, axial) for point, axial in points]
            faces.append([quad[0], quad[1], quad[2]] if not reverse else [quad[0], quad[2], quad[1]])
            faces.append([quad[0], quad[2], quad[3]] if not reverse else [quad[0], quad[3], quad[2]])

        def lerp_point(
            a_point: tuple[float, float],
            b_point: tuple[float, float],
            t: float,
        ) -> tuple[float, float]:
            return (
                float(a_point[0]) + (float(b_point[0]) - float(a_point[0])) * t,
                float(a_point[1]) + (float(b_point[1]) - float(a_point[1])) * t,
            )

        for index in range(len(profile_points)):
            next_index = (index + 1) % len(profile_points)
            outer_a = expanded_points[index]
            outer_b = expanded_points[next_index]
            inner_a = profile_points[index]
            inner_b = profile_points[next_index]
            for segment in range(segment_count):
                t0 = segment / segment_count
                t1 = (segment + 1) / segment_count
                if int(open_side) >= 0:
                    a0 = lerp_point(inner_a, outer_a, t0)
                    b0 = lerp_point(inner_b, outer_b, t0)
                    a1 = lerp_point(inner_a, outer_a, t1)
                    b1 = lerp_point(inner_b, outer_b, t1)
                    z0 = inner_axial + (open_axial - inner_axial) * t0
                    z1 = inner_axial + (open_axial - inner_axial) * t1
                    add_quad_points(
                        (
                            (a0, z0),
                            (b0, z0),
                            (b1, z1),
                            (a1, z1),
                        ),
                        reverse=False,
                    )
                else:
                    a0 = lerp_point(outer_a, inner_a, t0)
                    b0 = lerp_point(outer_b, inner_b, t0)
                    a1 = lerp_point(outer_a, inner_a, t1)
                    b1 = lerp_point(outer_b, inner_b, t1)
                    z0 = open_axial + (inner_axial - open_axial) * t0
                    z1 = open_axial + (inner_axial - open_axial) * t1
                    add_quad_points(
                        (
                            (a0, z0),
                            (b0, z0),
                            (b1, z1),
                            (a1, z1),
                        ),
                        reverse=True,
                    )
                bevel_face_count += 2

    wall_low = min(floor_axial, inner_axial)
    wall_high = max(floor_axial, inner_axial)
    inner_wall_face_count = 0
    if wall_high > wall_low + 1e-9:
        for index in range(len(cutter_ring) - 1):
            add_wall(
                cutter_ring[index],
                cutter_ring[index + 1],
                wall_low=wall_low,
                wall_high=wall_high,
                reverse=True,
            )
            inner_wall_face_count += 2

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()
    mesh.fix_normals()
    return mesh, {
        "cap_triangle_count": cap_triangle_count,
        "floor_triangle_count": floor_triangle_count,
        "inner_wall_face_count": inner_wall_face_count,
        "bevel_face_count": bevel_face_count,
        "bevel_width_cm": bevel_width if bevel_ring else 0.0,
        "bevel_segments": max(1, int(bevel_segments)) if bevel_ring else 0,
        "bevel_applied": bevel_ring,
        "profile_vertex_count": max(0, len(cutter_ring) - 1),
        "open_side": "positive" if int(open_side) >= 0 else "negative",
        "floor_axial_cm": float(floor_axial),
        "result_face_count": len(mesh.faces),
        "result_watertight": bool(mesh.is_watertight),
    }


def _mesh_from_box_blind_profile_cuts(
    *,
    box_min: np.ndarray,
    box_max: np.ndarray,
    cut_axis: int,
    plane_axes: tuple[int, int],
    cuts: list[dict[str, Any]],
) -> tuple[trimesh.Trimesh, dict[str, Any]] | None:
    try:
        from shapely.geometry import Polygon
        from shapely.ops import triangulate, unary_union
    except (ImportError, ModuleNotFoundError):
        return None

    if not cuts:
        return None
    rect = Polygon(
        (
            (float(box_min[plane_axes[0]]), float(box_min[plane_axes[1]])),
            (float(box_max[plane_axes[0]]), float(box_min[plane_axes[1]])),
            (float(box_max[plane_axes[0]]), float(box_max[plane_axes[1]])),
            (float(box_min[plane_axes[0]]), float(box_max[plane_axes[1]])),
        )
    )
    low = float(box_min[cut_axis])
    high = float(box_max[cut_axis])

    prepared: list[dict[str, Any]] = []
    cap_cutters = []
    cap_area_sum = 0.0
    open_side_ref: int | None = None
    floor_ref: float | None = None
    for cut in cuts:
        try:
            profile_points = [
                (float(point[0]), float(point[1]))
                for point in cut["profile_points"]
            ]
            open_side_value = 1 if str(cut.get("open_side") or "positive") == "positive" else -1
            floor_axial = float(cut["floor_axial_cm"])
        except (KeyError, TypeError, ValueError, IndexError):
            return None
        if open_side_ref is None:
            open_side_ref = open_side_value
        elif open_side_ref != open_side_value:
            return None
        if floor_ref is None:
            floor_ref = floor_axial
        elif abs(float(floor_ref) - floor_axial) > 1e-7:
            return None
        cutter = Polygon(profile_points)
        if not cutter.is_valid:
            cutter = cutter.buffer(0)
        if cutter.is_empty or float(cutter.area) <= 1e-9 or not rect.contains(cutter):
            return None

        bevel_width = max(0.0, float(cut.get("bevel_width") or 0.0))
        try:
            bevel_segments = max(1, int(cut.get("bevel_segments") or 1))
        except (TypeError, ValueError):
            bevel_segments = 1
        cap_cutter = cutter
        bevel_ring = False
        expanded_points: list[tuple[float, float]] = []
        if bevel_width > 1e-9:
            centroid = cutter.centroid
            cx = float(centroid.x)
            cy = float(centroid.y)
            for point_x, point_y in profile_points:
                dx = float(point_x) - cx
                dy = float(point_y) - cy
                length = math.hypot(dx, dy)
                if length <= 1e-9:
                    expanded_points.append((float(point_x), float(point_y)))
                else:
                    scale = (length + bevel_width) / length
                    expanded_points.append((cx + dx * scale, cy + dy * scale))
            expanded = Polygon(expanded_points)
            if not expanded.is_valid:
                expanded = expanded.buffer(0)
            if (
                not expanded.is_empty
                and float(expanded.area) > float(cutter.area)
                and rect.contains(expanded)
            ):
                cap_cutter = expanded
                bevel_ring = True
        cap_cutters.append(cap_cutter)
        cap_area_sum += float(cap_cutter.area)
        prepared.append(
            {
                "profile_points": profile_points,
                "cutter": cutter,
                "cap_cutter": cap_cutter,
                "expanded_points": expanded_points,
                "bevel_width": bevel_width,
                "bevel_segments": bevel_segments,
                "bevel_ring": bevel_ring,
                "floor_axial": floor_axial,
            }
        )

    if open_side_ref is None or floor_ref is None:
        return None
    open_axial = high if open_side_ref >= 0 else low
    if open_side_ref >= 0:
        if floor_ref <= low + 1e-9 or floor_ref >= high - 1e-9:
            return None
        floor_reverse = False
        open_cap_reverse = False
    else:
        if floor_ref <= low + 1e-9 or floor_ref >= high - 1e-9:
            return None
        floor_reverse = True
        open_cap_reverse = True

    cap_union = unary_union(cap_cutters)
    if cap_union.is_empty or abs(float(cap_union.area) - cap_area_sum) > 1e-6:
        return None
    remaining_open_cap = rect.difference(cap_union)
    if remaining_open_cap.is_empty or float(remaining_open_cap.area) <= 1e-9:
        return None

    vertices: list[tuple[float, float, float]] = []
    vertex_index: dict[tuple[int, int, int], int] = {}
    faces: list[list[int]] = []

    def add_vertex(plane_point: tuple[float, float], axial: float) -> int:
        coord = [0.0, 0.0, 0.0]
        coord[cut_axis] = float(axial)
        coord[plane_axes[0]] = float(plane_point[0])
        coord[plane_axes[1]] = float(plane_point[1])
        key = tuple(int(round(value * 1_000_000)) for value in coord)
        existing = vertex_index.get(key)
        if existing is not None:
            return existing
        vertex_index[key] = len(vertices)
        vertices.append((coord[0], coord[1], coord[2]))
        return len(vertices) - 1

    def add_triangle(
        points: list[tuple[float, float]],
        axial: float,
        *,
        reverse: bool,
    ) -> None:
        triangle = [add_vertex(point, axial) for point in points]
        faces.append([triangle[0], triangle[2], triangle[1]] if reverse else triangle)

    def add_wall(
        a_point: tuple[float, float],
        b_point: tuple[float, float],
        *,
        wall_low: float,
        wall_high: float,
        reverse: bool,
    ) -> None:
        quad = [
            add_vertex(a_point, wall_low),
            add_vertex(b_point, wall_low),
            add_vertex(b_point, wall_high),
            add_vertex(a_point, wall_high),
        ]
        faces.append([quad[0], quad[1], quad[2]] if not reverse else [quad[0], quad[2], quad[1]])
        faces.append([quad[0], quad[2], quad[3]] if not reverse else [quad[0], quad[3], quad[2]])

    cap_triangle_count = 0
    for triangle in triangulate(remaining_open_cap):
        if float(triangle.area) <= 1e-9 or not remaining_open_cap.covers(triangle.representative_point()):
            continue
        coords = [(float(x), float(y)) for x, y in list(triangle.exterior.coords)[:3]]
        add_triangle(coords, open_axial, reverse=open_cap_reverse)
        cap_triangle_count += 1
    opposite_axial = low if open_side_ref >= 0 else high
    for triangle in triangulate(rect):
        if float(triangle.area) <= 1e-9 or not rect.covers(triangle.representative_point()):
            continue
        coords = [(float(x), float(y)) for x, y in list(triangle.exterior.coords)[:3]]
        add_triangle(coords, opposite_axial, reverse=open_side_ref >= 0)
        cap_triangle_count += 1

    rect_ring = [(float(x), float(y)) for x, y in list(rect.exterior.coords)]
    for index in range(len(rect_ring) - 1):
        add_wall(rect_ring[index], rect_ring[index + 1], wall_low=low, wall_high=high, reverse=False)

    floor_triangle_count = 0
    inner_wall_face_count = 0
    bevel_face_count = 0
    bevel_cut_count = 0
    profile_vertex_count = 0
    for item in prepared:
        cutter = item["cutter"]
        cutter_ring = [(float(x), float(y)) for x, y in list(cutter.exterior.coords)]
        profile_points = item["profile_points"]
        profile_vertex_count += max(0, len(cutter_ring) - 1)
        for triangle in triangulate(cutter):
            if float(triangle.area) <= 1e-9 or not cutter.covers(triangle.representative_point()):
                continue
            coords = [(float(x), float(y)) for x, y in list(triangle.exterior.coords)[:3]]
            add_triangle(coords, float(item["floor_axial"]), reverse=floor_reverse)
            floor_triangle_count += 1
        bevel_width = float(item["bevel_width"])
        bevel_depth = min(bevel_width, max(abs(open_axial - float(item["floor_axial"])) * 0.45, 0.0))
        inner_axial = (
            open_axial - bevel_depth
            if open_side_ref >= 0 and item["bevel_ring"]
            else open_axial + bevel_depth
            if item["bevel_ring"]
            else open_axial
        )
        if item["bevel_ring"] and len(item["expanded_points"]) == len(profile_points):
            segment_count = max(1, int(item.get("bevel_segments") or 1))

            def add_quad_points(
                points: tuple[
                    tuple[tuple[float, float], float],
                    tuple[tuple[float, float], float],
                    tuple[tuple[float, float], float],
                    tuple[tuple[float, float], float],
                ],
                *,
                reverse: bool,
            ) -> None:
                quad = [add_vertex(point, axial) for point, axial in points]
                faces.append([quad[0], quad[1], quad[2]] if not reverse else [quad[0], quad[2], quad[1]])
                faces.append([quad[0], quad[2], quad[3]] if not reverse else [quad[0], quad[3], quad[2]])

            def lerp_point(
                a_point: tuple[float, float],
                b_point: tuple[float, float],
                t: float,
            ) -> tuple[float, float]:
                return (
                    float(a_point[0]) + (float(b_point[0]) - float(a_point[0])) * t,
                    float(a_point[1]) + (float(b_point[1]) - float(a_point[1])) * t,
                )

            expanded_points = item["expanded_points"]
            for index in range(len(profile_points)):
                next_index = (index + 1) % len(profile_points)
                outer_a = expanded_points[index]
                outer_b = expanded_points[next_index]
                inner_a = profile_points[index]
                inner_b = profile_points[next_index]
                for segment in range(segment_count):
                    t0 = segment / segment_count
                    t1 = (segment + 1) / segment_count
                    if open_side_ref >= 0:
                        a0 = lerp_point(inner_a, outer_a, t0)
                        b0 = lerp_point(inner_b, outer_b, t0)
                        a1 = lerp_point(inner_a, outer_a, t1)
                        b1 = lerp_point(inner_b, outer_b, t1)
                        z0 = inner_axial + (open_axial - inner_axial) * t0
                        z1 = inner_axial + (open_axial - inner_axial) * t1
                        add_quad_points(
                            (
                                (a0, z0),
                                (b0, z0),
                                (b1, z1),
                                (a1, z1),
                            ),
                            reverse=False,
                        )
                    else:
                        a0 = lerp_point(outer_a, inner_a, t0)
                        b0 = lerp_point(outer_b, inner_b, t0)
                        a1 = lerp_point(outer_a, inner_a, t1)
                        b1 = lerp_point(outer_b, inner_b, t1)
                        z0 = open_axial + (inner_axial - open_axial) * t0
                        z1 = open_axial + (inner_axial - open_axial) * t1
                        add_quad_points(
                            (
                                (a0, z0),
                                (b0, z0),
                                (b1, z1),
                                (a1, z1),
                            ),
                            reverse=True,
                        )
                    bevel_face_count += 2
            bevel_cut_count += 1
        wall_low = min(float(item["floor_axial"]), inner_axial)
        wall_high = max(float(item["floor_axial"]), inner_axial)
        if wall_high > wall_low + 1e-9:
            for index in range(len(cutter_ring) - 1):
                add_wall(
                    cutter_ring[index],
                    cutter_ring[index + 1],
                    wall_low=wall_low,
                    wall_high=wall_high,
                    reverse=True,
                )
                inner_wall_face_count += 2

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()
    mesh.fix_normals()
    return mesh, {
        "cap_triangle_count": cap_triangle_count,
        "floor_triangle_count": floor_triangle_count,
        "inner_wall_face_count": inner_wall_face_count,
        "bevel_face_count": bevel_face_count,
        "bevel_segments": max(
            (int(item.get("bevel_segments") or 0) for item in prepared if bool(item.get("bevel_ring"))),
            default=0,
        ),
        "bevel_cut_count": bevel_cut_count,
        "bevel_applied": bevel_cut_count > 0,
        "profile_vertex_count": profile_vertex_count,
        "open_side": "positive" if open_side_ref >= 0 else "negative",
        "floor_axial_cm": float(floor_ref),
        "cut_count": len(prepared),
        "result_face_count": len(mesh.faces),
        "result_watertight": bool(mesh.is_watertight),
    }


def _mesh_from_box_through_profile_cuts(
    *,
    box_min: np.ndarray,
    box_max: np.ndarray,
    cut_axis: int,
    plane_axes: tuple[int, int],
    cuts: list[dict[str, Any]],
) -> tuple[trimesh.Trimesh, dict[str, Any]] | None:
    try:
        from shapely.geometry import Polygon
        from shapely.ops import triangulate, unary_union
    except (ImportError, ModuleNotFoundError):
        return None

    rect = Polygon(
        (
            (float(box_min[plane_axes[0]]), float(box_min[plane_axes[1]])),
            (float(box_max[plane_axes[0]]), float(box_min[plane_axes[1]])),
            (float(box_max[plane_axes[0]]), float(box_max[plane_axes[1]])),
            (float(box_min[plane_axes[0]]), float(box_max[plane_axes[1]])),
        )
    )
    prepared: list[dict[str, Any]] = []
    cap_cutters = []
    cap_area_sum = 0.0
    for cut in cuts:
        try:
            profile_points = [
                (float(point[0]), float(point[1]))
                for point in cut["profile_points"]
            ]
        except (KeyError, TypeError, ValueError, IndexError):
            return None
        cutter = Polygon(profile_points)
        if not cutter.is_valid:
            cutter = cutter.buffer(0)
        if cutter.is_empty or float(cutter.area) <= 1e-9 or not rect.contains(cutter):
            return None
        bevel_width = max(0.0, float(cut.get("bevel_width") or 0.0))
        try:
            bevel_segments = max(1, int(cut.get("bevel_segments") or 1))
        except (TypeError, ValueError):
            bevel_segments = 1
        cap_cutter = cutter
        bevel_ring = False
        expanded_points: list[tuple[float, float]] = []
        if bevel_width > 1e-9:
            centroid = cutter.centroid
            cx = float(centroid.x)
            cy = float(centroid.y)
            for point_x, point_y in profile_points:
                dx = float(point_x) - cx
                dy = float(point_y) - cy
                length = math.hypot(dx, dy)
                if length <= 1e-9:
                    expanded_points.append((float(point_x), float(point_y)))
                else:
                    scale = (length + bevel_width) / length
                    expanded_points.append((cx + dx * scale, cy + dy * scale))
            expanded = Polygon(expanded_points)
            if not expanded.is_valid:
                expanded = expanded.buffer(0)
            if (
                not expanded.is_empty
                and float(expanded.area) > float(cutter.area)
                and rect.contains(expanded)
            ):
                cap_cutter = expanded
                bevel_ring = True
        cap_cutters.append(cap_cutter)
        cap_area_sum += float(cap_cutter.area)
        prepared.append(
            {
                "profile_points": profile_points,
                "cutter": cutter,
                "cap_cutter": cap_cutter,
                "expanded_points": expanded_points,
                "bevel_width": bevel_width,
                "bevel_segments": bevel_segments,
                "bevel_ring": bevel_ring,
            }
        )

    cap_union = unary_union(cap_cutters)
    if cap_union.is_empty:
        return None
    overlap_tolerance = max(1e-6, abs(cap_area_sum) * 1e-7)
    overlapping_caps = abs(float(cap_union.area) - cap_area_sum) > overlap_tolerance
    remaining = rect.difference(cap_union)
    if remaining.is_empty or float(remaining.area) <= 1e-9:
        return None
    if overlapping_caps:
        bevel_dropped_count = sum(1 for item in prepared if bool(item.get("bevel_ring")))
        if bevel_dropped_count:
            base_union = unary_union([item["cutter"] for item in prepared])
            if base_union.is_empty:
                return None
            remaining = rect.difference(base_union)
            if remaining.is_empty or float(remaining.area) <= 1e-9:
                return None
        built = _mesh_from_axis_extruded_polygon_union(
            [{"polygon": remaining, "low": float(box_min[cut_axis]), "high": float(box_max[cut_axis])}],
            axis=cut_axis,
            plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
        )
        if built is None:
            return None
        mesh, stats = built
        return mesh, {
            **stats,
            "cap_triangle_count": int(stats.get("cap_triangle_count") or 0),
            "inner_wall_face_count": int(stats.get("side_wall_face_count") or 0),
            "bevel_face_count": 0,
            "cut_count": len(prepared),
            "overlapping_profile_cut_caps": True,
            "through_profile_cut_union": True,
            "overlapping_profile_cut_bevel_dropped_count": int(bevel_dropped_count),
            "result_face_count": len(mesh.faces),
            "result_watertight": bool(mesh.is_watertight),
        }

    vertices: list[tuple[float, float, float]] = []
    vertex_index: dict[tuple[int, int, int], int] = {}
    faces: list[list[int]] = []

    def add_vertex(plane_point: tuple[float, float], axial: float) -> int:
        coord = [0.0, 0.0, 0.0]
        coord[cut_axis] = float(axial)
        coord[plane_axes[0]] = float(plane_point[0])
        coord[plane_axes[1]] = float(plane_point[1])
        key = tuple(int(round(value * 1_000_000)) for value in coord)
        existing = vertex_index.get(key)
        if existing is not None:
            return existing
        vertex_index[key] = len(vertices)
        vertices.append((coord[0], coord[1], coord[2]))
        return len(vertices) - 1

    def add_wall(
        a_point: tuple[float, float],
        b_point: tuple[float, float],
        *,
        reverse: bool,
        low: float | None = None,
        high: float | None = None,
    ) -> None:
        low = float(box_min[cut_axis]) if low is None else float(low)
        high = float(box_max[cut_axis]) if high is None else float(high)
        quad = [
            add_vertex(a_point, low),
            add_vertex(b_point, low),
            add_vertex(b_point, high),
            add_vertex(a_point, high),
        ]
        faces.append([quad[0], quad[1], quad[2]] if not reverse else [quad[0], quad[2], quad[1]])
        faces.append([quad[0], quad[2], quad[3]] if not reverse else [quad[0], quad[3], quad[2]])

    cap_triangle_count = 0
    for triangle in triangulate(remaining):
        if float(triangle.area) <= 1e-9 or not remaining.covers(triangle.representative_point()):
            continue
        coords = [(float(x), float(y)) for x, y in list(triangle.exterior.coords)[:3]]
        low_tri = [add_vertex(point, float(box_min[cut_axis])) for point in coords]
        high_tri = [add_vertex(point, float(box_max[cut_axis])) for point in coords]
        faces.append([low_tri[0], low_tri[2], low_tri[1]])
        faces.append(high_tri)
        cap_triangle_count += 2

    rect_ring = [(float(x), float(y)) for x, y in list(rect.exterior.coords)]
    for index in range(len(rect_ring) - 1):
        add_wall(rect_ring[index], rect_ring[index + 1], reverse=False)

    inner_wall_face_count = 0
    bevel_face_count = 0
    for item in prepared:
        profile_points = item["profile_points"]
        cutter_ring = [(float(x), float(y)) for x, y in list(item["cutter"].exterior.coords)]
        if item["bevel_ring"] and len(item["expanded_points"]) == len(profile_points):
            low = float(box_min[cut_axis])
            high = float(box_max[cut_axis])
            bevel_width = float(item["bevel_width"])
            segment_count = max(1, int(item.get("bevel_segments") or 1))
            bevel_depth = min(bevel_width, max((high - low) * 0.45, 0.0))
            low_inner = low + bevel_depth
            high_inner = high - bevel_depth

            def add_quad_points(
                points: tuple[
                    tuple[tuple[float, float], float],
                    tuple[tuple[float, float], float],
                    tuple[tuple[float, float], float],
                    tuple[tuple[float, float], float],
                ],
                *,
                reverse: bool,
            ) -> None:
                quad = [add_vertex(point, axial) for point, axial in points]
                faces.append([quad[0], quad[1], quad[2]] if not reverse else [quad[0], quad[2], quad[1]])
                faces.append([quad[0], quad[2], quad[3]] if not reverse else [quad[0], quad[3], quad[2]])

            def lerp_point(
                a_point: tuple[float, float],
                b_point: tuple[float, float],
                t: float,
            ) -> tuple[float, float]:
                return (
                    float(a_point[0]) + (float(b_point[0]) - float(a_point[0])) * t,
                    float(a_point[1]) + (float(b_point[1]) - float(a_point[1])) * t,
                )

            expanded_points = item["expanded_points"]
            for index in range(len(profile_points)):
                next_index = (index + 1) % len(profile_points)
                outer_a = expanded_points[index]
                outer_b = expanded_points[next_index]
                inner_a = profile_points[index]
                inner_b = profile_points[next_index]
                for segment in range(segment_count):
                    t0 = segment / segment_count
                    t1 = (segment + 1) / segment_count
                    low_a0 = lerp_point(outer_a, inner_a, t0)
                    low_b0 = lerp_point(outer_b, inner_b, t0)
                    low_a1 = lerp_point(outer_a, inner_a, t1)
                    low_b1 = lerp_point(outer_b, inner_b, t1)
                    low_z0 = low + (low_inner - low) * t0
                    low_z1 = low + (low_inner - low) * t1
                    add_quad_points(
                        (
                            (low_a0, low_z0),
                            (low_b0, low_z0),
                            (low_b1, low_z1),
                            (low_a1, low_z1),
                        ),
                        reverse=True,
                    )
                    high_a0 = lerp_point(inner_a, outer_a, t0)
                    high_b0 = lerp_point(inner_b, outer_b, t0)
                    high_a1 = lerp_point(inner_a, outer_a, t1)
                    high_b1 = lerp_point(inner_b, outer_b, t1)
                    high_z0 = high_inner + (high - high_inner) * t0
                    high_z1 = high_inner + (high - high_inner) * t1
                    add_quad_points(
                        (
                            (high_a0, high_z0),
                            (high_b0, high_z0),
                            (high_b1, high_z1),
                            (high_a1, high_z1),
                        ),
                        reverse=False,
                    )
                    bevel_face_count += 4
            if high_inner > low_inner + 1e-9:
                for index in range(len(cutter_ring) - 1):
                    add_wall(cutter_ring[index], cutter_ring[index + 1], reverse=True, low=low_inner, high=high_inner)
                    inner_wall_face_count += 2
        else:
            for index in range(len(cutter_ring) - 1):
                add_wall(cutter_ring[index], cutter_ring[index + 1], reverse=True)
                inner_wall_face_count += 2

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()
    mesh.fix_normals()
    return mesh, {
        "cap_triangle_count": cap_triangle_count,
        "inner_wall_face_count": inner_wall_face_count,
        "bevel_face_count": bevel_face_count,
        "bevel_segments": max(
            (int(item.get("bevel_segments") or 0) for item in prepared if bool(item.get("bevel_ring"))),
            default=0,
        ),
        "cut_count": len(prepared),
        "result_face_count": len(mesh.faces),
        "result_watertight": bool(mesh.is_watertight),
    }


def _exact_extruded_profile_extruded_profile_difference(
    a: trimesh.Trimesh,
    b: trimesh.Trimesh,
) -> trimesh.Trimesh | None:
    source_metadata = _extruded_profile_metadata(a)
    cutter_metadata = _extruded_profile_metadata(b)
    if source_metadata is None or cutter_metadata is None:
        return None
    if str(source_metadata.get("axis") or "") != str(cutter_metadata.get("axis") or ""):
        return None
    source_plane = _extruded_profile_plane_points(source_metadata)
    cutter_plane = _extruded_profile_plane_points(cutter_metadata)
    if source_plane is None or cutter_plane is None:
        return None
    cut_axis, plane_axes, source_points = source_plane
    cutter_axis, cutter_plane_axes, cutter_points = cutter_plane
    if int(cutter_axis) != int(cut_axis) or tuple(cutter_plane_axes) != tuple(plane_axes):
        return None
    source_center = np.asarray(source_metadata["center"], dtype=np.float64)
    cutter_center = np.asarray(cutter_metadata["center"], dtype=np.float64)
    source_half = float(source_metadata["extrude_height"]) * 0.5
    cutter_half = float(cutter_metadata["extrude_height"]) * 0.5
    source_low = float(source_center[cut_axis] - source_half)
    source_high = float(source_center[cut_axis] + source_half)
    cutter_low = float(cutter_center[cut_axis] - cutter_half)
    cutter_high = float(cutter_center[cut_axis] + cutter_half)
    if cutter_high <= source_low + 1e-7 or cutter_low >= source_high - 1e-7:
        return None
    cut_low = max(source_low, cutter_low)
    cut_high = min(source_high, cutter_high)
    if cut_high <= cut_low + 1e-9:
        return None
    through_cut = cutter_low <= source_low + 1e-7 and cutter_high >= source_high - 1e-7
    try:
        from shapely.geometry import Polygon
    except (ImportError, ModuleNotFoundError):
        return None

    source_polygon = Polygon(source_points)
    cutter_polygon = Polygon(cutter_points)
    if not source_polygon.is_valid:
        source_polygon = source_polygon.buffer(0)
    if not cutter_polygon.is_valid:
        cutter_polygon = cutter_polygon.buffer(0)
    if (
        source_polygon.is_empty
        or cutter_polygon.is_empty
        or float(source_polygon.area) <= 1e-9
        or float(cutter_polygon.area) <= 1e-9
        or not source_polygon.intersects(cutter_polygon)
    ):
        return None
    cut_touches_source_boundary = not bool(source_polygon.contains(cutter_polygon))
    bevel_width = max(0.0, float(cutter_metadata.get("bevel_width_cm") or 0.0))
    cap_cutter = cutter_polygon
    bevel_approximated = False
    if bevel_width > 1e-9:
        centroid = cutter_polygon.centroid
        cx = float(centroid.x)
        cy = float(centroid.y)
        expanded_points: list[tuple[float, float]] = []
        for point_x, point_y in cutter_points:
            dx = float(point_x) - cx
            dy = float(point_y) - cy
            length = math.hypot(dx, dy)
            if length <= 1e-9:
                expanded_points.append((float(point_x), float(point_y)))
            else:
                scale = (length + bevel_width) / length
                expanded_points.append((cx + dx * scale, cy + dy * scale))
        expanded = Polygon(expanded_points)
        if not expanded.is_valid:
            expanded = expanded.buffer(0)
        if (
            not expanded.is_empty
            and float(expanded.area) > float(cutter_polygon.area)
            and source_polygon.intersects(expanded)
        ):
            cap_cutter = expanded
            bevel_approximated = True

    remaining = source_polygon.difference(cap_cutter)
    if remaining.is_empty or float(remaining.area) <= 1e-9:
        return None
    slab_entries: list[dict[str, Any]] = []
    if source_low < cut_low - 1e-9:
        slab_entries.append({"polygon": source_polygon, "low": source_low, "high": cut_low})
    slab_entries.append({"polygon": remaining, "low": cut_low, "high": cut_high})
    if cut_high < source_high - 1e-9:
        slab_entries.append({"polygon": source_polygon, "low": cut_high, "high": source_high})
    built = _mesh_from_axis_extruded_polygon_union(
        slab_entries,
        axis=cut_axis,
        plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
    )
    if built is None:
        return None
    result, stats = built
    _set_batch_source_meshes(result, (result,))
    result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_exact_boolean.v1",
        "method": (
            "extruded_profile_through_extruded_profile_difference_v1"
            if through_cut
            else "extruded_profile_segment_extruded_profile_difference_v1"
        ),
        "op": "difference",
        "overlap": True,
        "through_cut": bool(through_cut),
        "segment_cut": not bool(through_cut),
        "passthrough": False,
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "cut_low_cm": float(cut_low),
        "cut_high_cm": float(cut_high),
        "source_part": str(source_metadata.get("part") or ""),
        "cutter_part": str(cutter_metadata.get("part") or ""),
        "profile_cut_count": 1,
        "profile_cut_kinds": ["extruded"],
        "source_profile_vertex_count": len(source_points),
        "cutter_profile_vertex_count": len(cutter_points),
        "open_profile_boundary_cut": bool(cut_touches_source_boundary or not source_polygon.contains(cap_cutter)),
        "bevel_width_cm": float(bevel_width),
        "bevel_approximated": bool(bevel_approximated),
        "bevel_face_count": 0,
        "result_face_count": len(result.faces),
        "result_watertight": bool(result.is_watertight),
        **stats,
    }
    return result


def _profile_cutter_inside_existing_blind_void(
    state: dict[str, Any] | None,
    *,
    cut_axis: int,
    plane_axes: tuple[int, int],
    cutter_low: float,
    cutter_high: float,
    profile_points: list[tuple[float, float]],
) -> dict[str, Any] | None:
    if state is None:
        return None
    try:
        state_cut_axis = int(state["cut_axis"])
        state_plane_axes = tuple(int(value) for value in state["plane_axes"])
    except (KeyError, TypeError, ValueError):
        return None
    if state_cut_axis != int(cut_axis) or state_plane_axes != tuple(int(axis) for axis in plane_axes):
        return None
    cuts = _existing_blind_profile_cuts_from_state(
        state,
        cut_axis=cut_axis,
        plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
    )
    if not cuts:
        return None
    try:
        from shapely.geometry import Polygon
    except (ImportError, ModuleNotFoundError):
        return None
    cutter_polygon = Polygon(profile_points)
    if not cutter_polygon.is_valid:
        cutter_polygon = cutter_polygon.buffer(0)
    if cutter_polygon.is_empty or float(cutter_polygon.area) <= 1e-9:
        return None
    for cut in cuts:
        try:
            floor_axial = float(cut["floor_axial_cm"])
            cut_points = [
                (float(point[0]), float(point[1]))
                for point in cut["profile_points"]
            ]
        except (KeyError, TypeError, ValueError, IndexError):
            continue
        open_side = str(cut.get("open_side") or "positive").strip().lower()
        if open_side == "positive":
            if cutter_low < floor_axial - 1e-7:
                continue
        elif open_side == "negative":
            if cutter_high > floor_axial + 1e-7:
                continue
        else:
            continue
        void_polygon = Polygon(cut_points)
        if not void_polygon.is_valid:
            void_polygon = void_polygon.buffer(0)
        if void_polygon.is_empty or float(void_polygon.area) <= 1e-9:
            continue
        if void_polygon.buffer(1e-7).covers(cutter_polygon):
            return dict(cut)
    return None


def _profile_cutter_opens_into_existing_blind_void(
    state: dict[str, Any] | None,
    *,
    cut_axis: int,
    plane_axes: tuple[int, int],
    cutter_low: float,
    cutter_high: float,
    profile_points: list[tuple[float, float]],
) -> dict[str, Any] | None:
    if state is None:
        return None
    try:
        state_cut_axis = int(state["cut_axis"])
        state_plane_axes = tuple(int(value) for value in state["plane_axes"])
    except (KeyError, TypeError, ValueError):
        return None
    if state_cut_axis != int(cut_axis) or state_plane_axes != tuple(int(axis) for axis in plane_axes):
        return None
    cuts = _existing_blind_profile_cuts_from_state(
        state,
        cut_axis=cut_axis,
        plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
    )
    if not cuts:
        return None
    try:
        from shapely.geometry import Polygon
    except (ImportError, ModuleNotFoundError):
        return None
    cutter_polygon = Polygon(profile_points)
    if not cutter_polygon.is_valid:
        cutter_polygon = cutter_polygon.buffer(0)
    if cutter_polygon.is_empty or float(cutter_polygon.area) <= 1e-9:
        return None
    for cut in cuts:
        try:
            floor_axial = float(cut["floor_axial_cm"])
            cut_points = [
                (float(point[0]), float(point[1]))
                for point in cut["profile_points"]
            ]
        except (KeyError, TypeError, ValueError, IndexError):
            continue
        void_polygon = Polygon(cut_points)
        if not void_polygon.is_valid:
            void_polygon = void_polygon.buffer(0)
        if void_polygon.is_empty or float(void_polygon.area) <= 1e-9:
            continue
        if not void_polygon.buffer(1e-7).covers(cutter_polygon):
            continue
        open_side = str(cut.get("open_side") or "positive").strip().lower()
        if open_side == "positive" and cutter_low < floor_axial - 1e-7 < cutter_high:
            return {
                "open_side": 1,
                "floor_axial": float(cutter_low),
                "containing_cut": dict(cut),
            }
        if open_side == "negative" and cutter_low < floor_axial < cutter_high + 1e-7:
            return {
                "open_side": -1,
                "floor_axial": float(cutter_high),
                "containing_cut": dict(cut),
            }
    return None


def _profile_cut_existing_void_passthrough(
    a: trimesh.Trimesh,
    *,
    cut_axis: int,
    plane_axes: tuple[int, int],
    cutter_low: float,
    cutter_high: float,
    cutter_part: str,
    containing_cut: dict[str, Any],
) -> trimesh.Trimesh:
    result = a.copy()
    sources = _batch_source_meshes(a)
    if sources:
        _set_batch_source_meshes(result, sources)
    result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_exact_boolean.v1",
        "method": "axis_aligned_box_blind_profile_existing_void_passthrough_v1",
        "op": "difference",
        "overlap": False,
        "passthrough": True,
        "noop_existing_void": True,
        "through_cut": False,
        "blind_cut": True,
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "cut_low_cm": float(cutter_low),
        "cut_high_cm": float(cutter_high),
        "cutter_part": str(cutter_part),
        "containing_cut_kind": str(containing_cut.get("cut_kind") or "extruded_blind"),
        "containing_cut_open_side": str(containing_cut.get("open_side") or ""),
        "containing_cut_floor_axial_cm": float(containing_cut.get("floor_axial_cm") or 0.0),
        "profile_cut_state_preserved": True,
        "result_face_count": len(result.faces),
        "result_watertight": bool(result.is_watertight),
    }
    return result


def _exact_axis_aligned_box_extruded_profile_difference(
    a: trimesh.Trimesh,
    b: trimesh.Trimesh,
) -> trimesh.Trimesh | None:
    if _boss_state_from_mesh(a) is not None:
        return None
    a_bounds = _box_bounds_from_metadata(a)
    profile_metadata = _extruded_profile_metadata(b)
    if a_bounds is None or profile_metadata is None:
        return None
    amin, amax = a_bounds
    plane = _extruded_profile_plane_points(profile_metadata)
    if plane is None:
        return None
    cut_axis, plane_axes, profile_points = plane
    center = np.asarray(profile_metadata["center"], dtype=np.float64)
    half_height = float(profile_metadata["extrude_height"]) * 0.5
    cutter_low = float(center[cut_axis] - half_height)
    cutter_high = float(center[cut_axis] + half_height)
    through_cut = cutter_low <= float(amin[cut_axis]) + 1e-7 and cutter_high >= float(amax[cut_axis]) - 1e-7
    previous_state = _profile_cut_state_from_mesh(a)
    blind_open_side = 0
    blind_floor_axial = 0.0
    if not through_cut:
        if cutter_high >= float(amax[cut_axis]) - 1e-7 and cutter_low > float(amin[cut_axis]) + 1e-7:
            blind_open_side = 1
            blind_floor_axial = cutter_low
        elif cutter_low <= float(amin[cut_axis]) + 1e-7 and cutter_high < float(amax[cut_axis]) - 1e-7:
            blind_open_side = -1
            blind_floor_axial = cutter_high
        else:
            containing_cut = _profile_cutter_inside_existing_blind_void(
                previous_state,
                cut_axis=cut_axis,
                plane_axes=plane_axes,
                cutter_low=cutter_low,
                cutter_high=cutter_high,
                profile_points=profile_points,
            )
            if containing_cut is not None:
                return _profile_cut_existing_void_passthrough(
                    a,
                    cut_axis=cut_axis,
                    plane_axes=plane_axes,
                    cutter_low=cutter_low,
                    cutter_high=cutter_high,
                    cutter_part=str(profile_metadata.get("part") or ""),
                    containing_cut=containing_cut,
                )
            opening = _profile_cutter_opens_into_existing_blind_void(
                previous_state,
                cut_axis=cut_axis,
                plane_axes=plane_axes,
                cutter_low=cutter_low,
                cutter_high=cutter_high,
                profile_points=profile_points,
            )
            if opening is not None:
                blind_open_side = int(opening["open_side"])
                blind_floor_axial = float(opening["floor_axial"])
            else:
                return None
    profile_array = np.asarray(profile_points, dtype=np.float64)
    plane_min = profile_array.min(axis=0)
    plane_max = profile_array.max(axis=0)
    box_plane_min = amin[list(plane_axes)]
    box_plane_max = amax[list(plane_axes)]
    touches_plane_boundary = bool(np.any(plane_min <= box_plane_min + 1e-7)) or bool(
        np.any(plane_max >= box_plane_max - 1e-7)
    )

    new_cut = {
        "cut_kind": "extruded",
        "profile_points": [[float(point[0]), float(point[1])] for point in profile_points],
        "bevel_width": float(profile_metadata.get("bevel_width_cm") or 0.0),
        "bevel_segments": int(profile_metadata.get("bevel_segments") or 1),
        "cutter_part": str(profile_metadata.get("part") or ""),
    }
    if float(new_cut["bevel_width"]) > 1e-9:
        new_cut["bevel_applied"] = True
    if not through_cut:
        new_blind_cut = {
            **new_cut,
            "cut_kind": "extruded_blind",
            "open_side": "positive" if blind_open_side > 0 else "negative",
            "floor_axial_cm": float(blind_floor_axial),
        }
        if previous_state is not None:
            previous_cuts = _existing_blind_profile_cuts_from_state(
                previous_state,
                cut_axis=cut_axis,
                plane_axes=plane_axes,
            )
            if previous_cuts is None:
                previous_cuts = _existing_profile_cut_records_from_state(
                    previous_state,
                    cut_axis=cut_axis,
                    plane_axes=plane_axes,
                )
            if previous_cuts is None:
                return None
            cuts = [*previous_cuts, new_blind_cut]
            state_cut_kind = _profile_cut_state_kind_from_records(cuts)
            if state_cut_kind == "mixed_depth_profile":
                built = _mesh_from_box_blind_profile_cuts_with_raised_details(
                    box_min=amin,
                    box_max=amax,
                    cut_axis=cut_axis,
                    plane_axes=plane_axes,
                    cuts=cuts,
                    details=[],
                )
                method = "axis_aligned_box_mixed_depth_profile_difference_v1"
            else:
                built = _mesh_from_box_blind_cut_records(
                    box_min=amin,
                    box_max=amax,
                    cut_axis=cut_axis,
                    plane_axes=plane_axes,
                    cuts=cuts,
                )
                method = (
                    "axis_aligned_box_repeated_blind_extruded_profile_difference_v1"
                    if state_cut_kind == "extruded_blind"
                    else "axis_aligned_box_mixed_blind_profile_difference_v1"
                )
        else:
            cuts = [new_blind_cut]
            state_cut_kind = "extruded_blind"
            built = _mesh_from_box_blind_profile_cut(
                box_min=amin,
                box_max=amax,
                cut_axis=cut_axis,
                plane_axes=plane_axes,
                profile_points=profile_points,
                open_side=blind_open_side,
                floor_axial=blind_floor_axial,
                bevel_width=float(profile_metadata.get("bevel_width_cm") or 0.0),
                bevel_segments=int(profile_metadata.get("bevel_segments") or 1),
            )
            if built is None:
                built = _mesh_from_box_blind_cut_records(
                    box_min=amin,
                    box_max=amax,
                    cut_axis=cut_axis,
                    plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
                    cuts=cuts,
                )
            method = "axis_aligned_box_blind_extruded_profile_difference_v1"
        if built is None:
            backend_assisted = _backend_assisted_blind_profile_difference(
                a,
                b,
                box_min=amin,
                box_max=amax,
                cut_axis=cut_axis,
                plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
                cuts=cuts,
                state_cut_kind=state_cut_kind,
                attempted_method=method,
            )
            if backend_assisted is not None:
                return backend_assisted
            return None
        result, stats = built
        _set_batch_source_meshes(result, (result,))
        result.metadata[_PROFILE_CUT_STATE_METADATA_KEY] = {
            "schema": "lathe.geometry.reference_profile_cut_state.v1",
            "box_min": [float(value) for value in amin],
            "box_max": [float(value) for value in amax],
            "cut_kind": state_cut_kind,
            "cut_axis": int(cut_axis),
            "plane_axes": [int(axis) for axis in plane_axes],
            "cuts": cuts,
        }
        result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
            "schema": "lathe.geometry.reference_exact_boolean.v1",
            "method": method,
            "op": "difference",
            "overlap": True,
            "through_cut": False,
            "blind_cut": True,
            "passthrough": False,
            "cut_axis": int(cut_axis),
            "plane_axes": [int(axis) for axis in plane_axes],
            "cutter_part": str(profile_metadata.get("part") or ""),
            "profile_cut_count": len(cuts),
            "profile_cut_kinds": sorted({str(cut.get("cut_kind") or state_cut_kind) for cut in cuts}),
            "result_face_count": len(result.faces),
            "result_watertight": bool(result.is_watertight),
            **stats,
        }
        return result
    state_cut_kind = "extruded"
    if previous_state is not None:
        previous_kind = str(previous_state.get("cut_kind") or "")
        if previous_kind not in {"extruded", "revolved", "mixed"}:
            return None
        if int(previous_state.get("cut_axis", -1)) != int(cut_axis):
            return None
        previous_plane_axes = [int(value) for value in previous_state.get("plane_axes", [])]
        if previous_plane_axes != [int(axis) for axis in plane_axes]:
            return None
        cuts = [
            dict(cut)
            for cut in previous_state.get("cuts", [])
            if isinstance(cut, dict)
        ]
        if previous_kind != "mixed":
            cuts = [
                {**cut, "cut_kind": str(cut.get("cut_kind") or previous_kind)}
                for cut in cuts
            ]
        elif any(str(cut.get("cut_kind") or "") not in {"extruded", "revolved"} for cut in cuts):
            return None
        cuts.append(new_cut)
        open_boundary_profile_state = touches_plane_boundary or _profile_cut_records_touch_plane_boundary(
            cuts,
            box_min=amin,
            box_max=amax,
            plane_axes=plane_axes,
        )
        if open_boundary_profile_state:
            built = _mesh_from_box_profile_cuts_with_open_extruded_boundaries(
                box_min=amin,
                box_max=amax,
                cut_axis=cut_axis,
                plane_axes=plane_axes,
                cuts=cuts,
            )
            method = (
                "axis_aligned_box_repeated_open_through_extruded_profile_difference_v1"
                if previous_kind == "extruded"
                else "axis_aligned_box_mixed_open_through_profile_difference_v1"
            )
            state_cut_kind = "extruded" if previous_kind == "extruded" else "mixed"
        elif previous_kind == "extruded":
            built = _mesh_from_box_through_profile_cuts(
                box_min=amin,
                box_max=amax,
                cut_axis=cut_axis,
                plane_axes=plane_axes,
                cuts=cuts,
            )
            method = "axis_aligned_box_repeated_through_extruded_profile_difference_v1"
        else:
            built = _mesh_from_box_mixed_profile_cuts(
                box_min=amin,
                box_max=amax,
                cut_axis=cut_axis,
                plane_axes=plane_axes,
                cuts=cuts,
            )
            if built is None:
                built = _mesh_from_box_blind_profile_cuts_with_raised_details(
                    box_min=amin,
                    box_max=amax,
                    cut_axis=cut_axis,
                    plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
                    cuts=cuts,
                    details=[],
                )
                if built is not None:
                    mesh, stats = built
                    built = (
                        mesh,
                        {
                            **stats,
                            "mixed_through_profile_cut_union": True,
                            "through_cut_count": len(cuts),
                            "blind_cut_count": 0,
                        },
                    )
            method = "axis_aligned_box_mixed_through_profile_difference_v1"
            state_cut_kind = "mixed"
    else:
        cuts = [new_cut]
        if touches_plane_boundary:
            built = _mesh_from_box_profile_cuts_with_open_extruded_boundaries(
                box_min=amin,
                box_max=amax,
                cut_axis=cut_axis,
                plane_axes=plane_axes,
                cuts=cuts,
            )
            method = "axis_aligned_box_open_through_extruded_profile_difference_v1"
        else:
            built = _mesh_from_box_through_profile_cut(
                box_min=amin,
                box_max=amax,
                cut_axis=cut_axis,
                plane_axes=plane_axes,
                profile_points=profile_points,
                bevel_width=float(profile_metadata.get("bevel_width_cm") or 0.0),
                bevel_segments=int(profile_metadata.get("bevel_segments") or 1),
            )
            method = "axis_aligned_box_through_extruded_profile_difference_v1"
    if built is None:
        return None
    result, stats = built
    _set_batch_source_meshes(result, (result,))
    result.metadata[_PROFILE_CUT_STATE_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_profile_cut_state.v1",
        "box_min": [float(value) for value in amin],
        "box_max": [float(value) for value in amax],
        "cut_kind": state_cut_kind,
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "cuts": cuts,
    }
    result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_exact_boolean.v1",
        "method": method,
        "op": "difference",
        "overlap": True,
        "through_cut": True,
        "passthrough": False,
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "cutter_part": str(profile_metadata.get("part") or ""),
        "profile_cut_count": len(cuts),
        "profile_cut_kinds": sorted(
            {
                str(cut.get("cut_kind") or state_cut_kind)
                for cut in cuts
            }
        ),
        "result_face_count": len(result.faces),
        "result_watertight": bool(result.is_watertight),
        **stats,
    }
    return result


def _circle_points(
    center: np.ndarray,
    radius: float,
    *,
    sections: int = 48,
) -> list[tuple[float, float]]:
    return [
        (
            float(center[0] + math.cos(math.tau * index / sections) * radius),
            float(center[1] + math.sin(math.tau * index / sections) * radius),
        )
        for index in range(sections)
    ]


def _radius_at_profile_axial(
    profile: list[tuple[float, float]],
    axial: float,
) -> float | None:
    for (left_axial, left_radius), (right_axial, right_radius) in zip(
        profile,
        profile[1:],
        strict=False,
    ):
        if abs(right_axial - left_axial) <= 1e-9:
            continue
        low = min(left_axial, right_axial)
        high = max(left_axial, right_axial)
        if axial < low - 1e-9 or axial > high + 1e-9:
            continue
        t = (axial - left_axial) / (right_axial - left_axial)
        return float(left_radius + (right_radius - left_radius) * t)
    matches = [radius for point_axial, radius in profile if abs(point_axial - axial) <= 1e-9]
    if matches:
        return float(max(matches))
    return None


def _clipped_revolved_profile_rings(
    *,
    center: np.ndarray,
    profile: list[tuple[float, float]],
    axis_index: int,
    low: float,
    high: float,
    bevel_width: float,
) -> list[tuple[float, float]] | None:
    world_profile = [
        (float(center[axis_index] + axial), float(radius))
        for axial, radius in sorted(profile, key=lambda item: item[0])
    ]
    if not world_profile or world_profile[0][0] > low + 1e-7 or world_profile[-1][0] < high - 1e-7:
        return None

    low_radius = _radius_at_profile_axial(world_profile, low)
    high_radius = _radius_at_profile_axial(world_profile, high)
    if low_radius is None or high_radius is None:
        return None

    rings: list[tuple[float, float]] = [(float(low), float(low_radius))]
    for axial, radius in world_profile:
        if low + 1e-9 < axial < high - 1e-9:
            rings.append((float(axial), float(radius)))
    rings.append((float(high), float(high_radius)))

    deduped: list[tuple[float, float]] = []
    for axial, radius in rings:
        if radius <= 0.0:
            return None
        if deduped and abs(deduped[-1][0] - axial) <= 1e-9 and abs(deduped[-1][1] - radius) <= 1e-9:
            continue
        deduped.append((axial, radius))

    variable_profile = max(radius for _, radius in deduped) - min(radius for _, radius in deduped) > 1e-9
    bevel_width = max(0.0, float(bevel_width))
    if variable_profile:
        if bevel_width <= 1e-9:
            return deduped
        beveled = _beveled_revolved_profile_radius_steps(deduped, bevel_width=bevel_width)
        return beveled or deduped
    if bevel_width <= 1e-9:
        return deduped

    radius = deduped[0][1]
    depth = max(0.0, high - low)
    bevel_depth = min(bevel_width, depth * 0.45)
    bevel_radius = radius + bevel_width
    return [
        (float(low), float(bevel_radius)),
        (float(low + bevel_depth), float(radius)),
        (float(high - bevel_depth), float(radius)),
        (float(high), float(bevel_radius)),
    ]


def _beveled_revolved_profile_radius_steps(
    rings: list[tuple[float, float]],
    *,
    bevel_width: float,
) -> list[tuple[float, float]] | None:
    if len(rings) < 3 or bevel_width <= 1e-9:
        return None
    result: list[tuple[float, float]] = []
    index = 0
    changed = False
    while index < len(rings):
        axial, radius = rings[index]
        if (
            index + 1 < len(rings)
            and abs(float(rings[index + 1][0]) - float(axial)) <= 1e-9
            and abs(float(rings[index + 1][1]) - float(radius)) > 1e-9
        ):
            next_axial, next_radius = rings[index + 1]
            previous_axial = next(
                (
                    float(rings[previous_index][0])
                    for previous_index in range(index - 1, -1, -1)
                    if abs(float(rings[previous_index][0]) - float(axial)) > 1e-9
                ),
                None,
            )
            following_axial = next(
                (
                    float(rings[following_index][0])
                    for following_index in range(index + 2, len(rings))
                    if abs(float(rings[following_index][0]) - float(axial)) > 1e-9
                ),
                None,
            )
            before_room = (
                float("inf")
                if previous_axial is None
                else max(0.0, float(axial) - previous_axial)
            )
            after_room = (
                float("inf")
                if following_axial is None
                else max(0.0, following_axial - float(axial))
            )
            depth = min(float(bevel_width), before_room * 0.45, after_room * 0.45)
            if depth > 1e-9 and math.isfinite(depth):
                left = (float(axial) - depth, float(radius))
                right = (float(next_axial) + depth, float(next_radius))
                if result and left[0] <= result[-1][0] + 1e-9:
                    result.append((float(axial), float(radius)))
                    result.append((float(next_axial), float(next_radius)))
                else:
                    result.append(left)
                    result.append(right)
                    changed = True
                index += 2
                continue
        result.append((float(axial), float(radius)))
        index += 1
    if not changed:
        return None
    cleaned: list[tuple[float, float]] = []
    for axial, radius in result:
        if cleaned and abs(cleaned[-1][0] - axial) <= 1e-9 and abs(cleaned[-1][1] - radius) <= 1e-9:
            continue
        if cleaned and axial < cleaned[-1][0] - 1e-9:
            return None
        cleaned.append((float(axial), float(radius)))
    return cleaned if len(cleaned) >= 2 else None


def _blind_revolved_profile_rings(
    *,
    center: np.ndarray,
    profile: list[tuple[float, float]],
    axis_index: int,
    low: float,
    high: float,
    bevel_width: float,
) -> tuple[list[tuple[float, float]], int, float, bool] | None:
    world_profile = [
        (float(center[axis_index] + axial), float(radius))
        for axial, radius in sorted(profile, key=lambda item: item[0])
    ]
    if len(world_profile) < 2:
        return None
    if any(radius <= 1e-9 for _, radius in world_profile):
        return None

    tolerance = 1e-7
    if world_profile[-1][0] >= high - tolerance and world_profile[0][0] > low + tolerance:
        open_side = 1
        open_axial = float(high)
        floor_axial = float(world_profile[0][0])
        inner_limit = open_axial - min(max(0.0, bevel_width), max((open_axial - floor_axial) * 0.45, 0.0))
    elif world_profile[0][0] <= low + tolerance and world_profile[-1][0] < high - tolerance:
        open_side = -1
        open_axial = float(low)
        floor_axial = float(world_profile[-1][0])
        inner_limit = open_axial + min(max(0.0, bevel_width), max((floor_axial - open_axial) * 0.45, 0.0))
    else:
        return None

    open_radius = _radius_at_profile_axial(world_profile, open_axial)
    floor_radius = _radius_at_profile_axial(world_profile, floor_axial)
    if open_radius is None or floor_radius is None:
        return None

    bevel_applied = False
    rings: list[tuple[float, float]] = []

    def append_ring(axial: float, radius: float) -> None:
        if radius <= 1e-9:
            return
        if (
            rings
            and abs(rings[-1][0] - axial) <= 1e-9
            and abs(rings[-1][1] - radius) <= 1e-9
        ):
            return
        rings.append((float(axial), float(radius)))

    if open_side > 0:
        for axial, radius in world_profile:
            if axial < floor_axial - tolerance or axial > high + tolerance:
                continue
            if bevel_width > 1e-9 and axial > inner_limit + tolerance:
                continue
            append_ring(max(float(low), min(float(high), axial)), radius)
        if bevel_width > 1e-9:
            inner_radius = _radius_at_profile_axial(world_profile, inner_limit)
            if inner_radius is None:
                return None
            append_ring(inner_limit, inner_radius)
            append_ring(open_axial, float(open_radius) + max(0.0, bevel_width))
            bevel_applied = True
        else:
            append_ring(open_axial, float(open_radius))
    else:
        if bevel_width > 1e-9:
            inner_radius = _radius_at_profile_axial(world_profile, inner_limit)
            if inner_radius is None:
                return None
            append_ring(open_axial, float(open_radius) + max(0.0, bevel_width))
            append_ring(inner_limit, inner_radius)
            bevel_applied = True
        else:
            append_ring(open_axial, float(open_radius))
        for axial, radius in world_profile:
            if axial < low - tolerance or axial > floor_axial + tolerance:
                continue
            if bevel_width > 1e-9 and axial < inner_limit - tolerance:
                continue
            append_ring(max(float(low), min(float(high), axial)), radius)
        append_ring(floor_axial, float(floor_radius))

    cleaned: list[tuple[float, float]] = []
    for axial, radius in rings:
        if axial < low - tolerance or axial > high + tolerance:
            return None
        if cleaned and axial < cleaned[-1][0] - tolerance:
            return None
        if cleaned and abs(axial - cleaned[-1][0]) <= 1e-9 and abs(radius - cleaned[-1][1]) <= 1e-9:
            continue
        cleaned.append((float(axial), float(radius)))
    if len(cleaned) < 2:
        return None
    return cleaned, open_side, floor_axial, bevel_applied


def _rect_available_circle_radius(rect: Any, plane_center: np.ndarray) -> float:
    try:
        min_x, min_y, max_x, max_y = (float(value) for value in rect.bounds)
        center_x = float(plane_center[0])
        center_y = float(plane_center[1])
    except (TypeError, ValueError, IndexError, AttributeError):
        return -1.0
    return min(center_x - min_x, max_x - center_x, center_y - min_y, max_y - center_y)


def _clamp_revolved_rings_to_rect(
    rect: Any,
    plane_center: np.ndarray,
    rings: list[tuple[float, float]],
    *,
    tolerance: float = 1e-7,
) -> tuple[list[tuple[float, float]], dict[str, Any]] | None:
    if len(rings) < 2:
        return None
    cleaned = [(float(axial), float(radius)) for axial, radius in rings]
    if any(radius <= 0.0 for _, radius in cleaned):
        return None
    available_radius = _rect_available_circle_radius(rect, plane_center)
    if available_radius <= tolerance:
        return None
    requested_min_radius = min(radius for _, radius in cleaned)
    requested_max_radius = max(radius for _, radius in cleaned)
    if requested_max_radius <= available_radius - tolerance:
        return cleaned, {}
    if requested_min_radius >= available_radius - tolerance:
        return None
    actual_max_radius = max(requested_min_radius, available_radius - tolerance)
    clamped = [
        (axial, min(radius, actual_max_radius))
        for axial, radius in cleaned
    ]
    return clamped, {
        "profile_radius_clamped": True,
        "requested_max_radius_cm": float(requested_max_radius),
        "actual_max_radius_cm": float(max(radius for _, radius in clamped)),
        "available_radius_cm": float(available_radius),
    }


def _mesh_from_box_revolved_profile_cut(
    *,
    box_min: np.ndarray,
    box_max: np.ndarray,
    cut_axis: int,
    plane_axes: tuple[int, int],
    center: np.ndarray,
    rings: list[tuple[float, float]],
    sections: int = 48,
) -> tuple[trimesh.Trimesh, dict[str, Any]] | None:
    try:
        from shapely.geometry import Polygon
        from shapely.ops import triangulate
    except (ImportError, ModuleNotFoundError):
        return None

    plane_center = np.asarray(
        [center[plane_axes[0]], center[plane_axes[1]]],
        dtype=np.float64,
    )
    rect = Polygon(
        (
            (float(box_min[plane_axes[0]]), float(box_min[plane_axes[1]])),
            (float(box_max[plane_axes[0]]), float(box_min[plane_axes[1]])),
            (float(box_max[plane_axes[0]]), float(box_max[plane_axes[1]])),
            (float(box_min[plane_axes[0]]), float(box_max[plane_axes[1]])),
        )
    )
    clamped = _clamp_revolved_rings_to_rect(rect, plane_center, rings)
    if clamped is None:
        return None
    rings, clamp_stats = clamped
    max_radius = max(radius for _, radius in rings)
    if not rect.contains(Polygon(_circle_points(plane_center, max_radius, sections=sections))):
        return None

    vertices: list[tuple[float, float, float]] = []
    vertex_index: dict[tuple[int, int, int], int] = {}
    faces: list[list[int]] = []

    def add_vertex(plane_point: tuple[float, float], axial: float) -> int:
        coord = [0.0, 0.0, 0.0]
        coord[cut_axis] = float(axial)
        coord[plane_axes[0]] = float(plane_point[0])
        coord[plane_axes[1]] = float(plane_point[1])
        key = tuple(int(round(value * 1_000_000)) for value in coord)
        existing = vertex_index.get(key)
        if existing is not None:
            return existing
        vertex_index[key] = len(vertices)
        vertices.append((coord[0], coord[1], coord[2]))
        return len(vertices) - 1

    def add_wall(
        a_point: tuple[float, float],
        b_point: tuple[float, float],
        *,
        low: float,
        high: float,
        reverse: bool,
    ) -> None:
        quad = [
            add_vertex(a_point, low),
            add_vertex(b_point, low),
            add_vertex(b_point, high),
            add_vertex(a_point, high),
        ]
        faces.append([quad[0], quad[1], quad[2]] if not reverse else [quad[0], quad[2], quad[1]])
        faces.append([quad[0], quad[2], quad[3]] if not reverse else [quad[0], quad[3], quad[2]])

    def add_cap(radius: float, axial: float, *, reverse: bool) -> int:
        cutter = Polygon(_circle_points(plane_center, radius, sections=sections))
        remaining = rect.difference(cutter)
        if remaining.is_empty or float(remaining.area) <= 1e-9:
            return 0
        count = 0
        for triangle in triangulate(remaining):
            if float(triangle.area) <= 1e-9 or not remaining.covers(triangle.representative_point()):
                continue
            coords = [(float(x), float(y)) for x, y in list(triangle.exterior.coords)[:3]]
            tri = [add_vertex(point, axial) for point in coords]
            faces.append([tri[0], tri[2], tri[1]] if reverse else tri)
            count += 1
        return count

    low = float(box_min[cut_axis])
    high = float(box_max[cut_axis])
    cap_triangle_count = add_cap(rings[0][1], low, reverse=True)
    cap_triangle_count += add_cap(rings[-1][1], high, reverse=False)

    rect_ring = [(float(x), float(y)) for x, y in list(rect.exterior.coords)]
    for index in range(len(rect_ring) - 1):
        add_wall(rect_ring[index], rect_ring[index + 1], low=low, high=high, reverse=False)

    ring_points = [
        _circle_points(plane_center, radius, sections=sections)
        for _, radius in rings
    ]
    bore_face_count = 0
    shoulder_face_count = 0
    chamfer_face_count = 0
    for ring_index in range(len(rings) - 1):
        left_axial, left_radius = rings[ring_index]
        right_axial, right_radius = rings[ring_index + 1]
        left_ring = ring_points[ring_index]
        right_ring = ring_points[ring_index + 1]
        if abs(left_axial - right_axial) <= 1e-9 and abs(left_radius - right_radius) <= 1e-9:
            continue
        for index in range(sections):
            next_index = (index + 1) % sections
            quad = [
                add_vertex(left_ring[index], left_axial),
                add_vertex(left_ring[next_index], left_axial),
                add_vertex(right_ring[next_index], right_axial),
                add_vertex(right_ring[index], right_axial),
            ]
            faces.append([quad[0], quad[2], quad[1]])
            faces.append([quad[0], quad[3], quad[2]])
            if abs(left_axial - right_axial) <= 1e-9:
                shoulder_face_count += 2
            elif abs(left_radius - right_radius) > 1e-9:
                chamfer_face_count += 2
            else:
                bore_face_count += 2

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()
    mesh.fix_normals()
    return mesh, {
        "cap_triangle_count": cap_triangle_count,
        "bore_wall_face_count": bore_face_count,
        "shoulder_face_count": shoulder_face_count,
        "chamfer_face_count": chamfer_face_count,
        "ring_count": len(rings),
        "radial_section_count": sections,
        "min_radius_cm": float(min(radius for _, radius in rings)),
        "max_radius_cm": float(max(radius for _, radius in rings)),
        **clamp_stats,
    }


def _mesh_from_box_blind_revolved_profile_cut(
    *,
    box_min: np.ndarray,
    box_max: np.ndarray,
    cut_axis: int,
    plane_axes: tuple[int, int],
    center: np.ndarray,
    rings: list[tuple[float, float]],
    open_side: int,
    bevel_applied: bool,
    sections: int = 48,
) -> tuple[trimesh.Trimesh, dict[str, Any]] | None:
    try:
        from shapely.geometry import Polygon
        from shapely.ops import triangulate
    except (ImportError, ModuleNotFoundError):
        return None

    if len(rings) < 2:
        return None
    plane_center = np.asarray(
        [center[plane_axes[0]], center[plane_axes[1]]],
        dtype=np.float64,
    )
    rect = Polygon(
        (
            (float(box_min[plane_axes[0]]), float(box_min[plane_axes[1]])),
            (float(box_max[plane_axes[0]]), float(box_min[plane_axes[1]])),
            (float(box_max[plane_axes[0]]), float(box_max[plane_axes[1]])),
            (float(box_min[plane_axes[0]]), float(box_max[plane_axes[1]])),
        )
    )
    clamped = _clamp_revolved_rings_to_rect(rect, plane_center, rings)
    if clamped is None:
        return None
    rings, clamp_stats = clamped
    max_radius = max(radius for _, radius in rings)
    if not rect.contains(Polygon(_circle_points(plane_center, max_radius, sections=sections))):
        return None

    vertices: list[tuple[float, float, float]] = []
    vertex_index: dict[tuple[int, int, int], int] = {}
    faces: list[list[int]] = []

    def add_vertex(plane_point: tuple[float, float], axial: float) -> int:
        coord = [0.0, 0.0, 0.0]
        coord[cut_axis] = float(axial)
        coord[plane_axes[0]] = float(plane_point[0])
        coord[plane_axes[1]] = float(plane_point[1])
        key = tuple(int(round(value * 1_000_000)) for value in coord)
        existing = vertex_index.get(key)
        if existing is not None:
            return existing
        vertex_index[key] = len(vertices)
        vertices.append((coord[0], coord[1], coord[2]))
        return len(vertices) - 1

    def add_triangle(
        points: list[tuple[float, float]],
        axial: float,
        *,
        reverse: bool,
    ) -> None:
        tri = [add_vertex(point, axial) for point in points]
        faces.append([tri[0], tri[2], tri[1]] if reverse else tri)

    def add_wall(
        a_point: tuple[float, float],
        b_point: tuple[float, float],
        *,
        low: float,
        high: float,
        reverse: bool,
    ) -> None:
        quad = [
            add_vertex(a_point, low),
            add_vertex(b_point, low),
            add_vertex(b_point, high),
            add_vertex(a_point, high),
        ]
        faces.append([quad[0], quad[1], quad[2]] if not reverse else [quad[0], quad[2], quad[1]])
        faces.append([quad[0], quad[2], quad[3]] if not reverse else [quad[0], quad[3], quad[2]])

    low = float(box_min[cut_axis])
    high = float(box_max[cut_axis])
    open_axial = high if int(open_side) >= 0 else low
    opposite_axial = low if int(open_side) >= 0 else high
    floor_axial = float(rings[0][0] if int(open_side) >= 0 else rings[-1][0])
    open_radius = float(rings[-1][1] if int(open_side) >= 0 else rings[0][1])
    floor_radius = float(rings[0][1] if int(open_side) >= 0 else rings[-1][1])

    open_circle = Polygon(_circle_points(plane_center, open_radius, sections=sections))
    remaining = rect.difference(open_circle)
    if remaining.is_empty or float(remaining.area) <= 1e-9:
        return None

    cap_triangle_count = 0
    for triangle in triangulate(remaining):
        if float(triangle.area) <= 1e-9 or not remaining.covers(triangle.representative_point()):
            continue
        coords = [(float(x), float(y)) for x, y in list(triangle.exterior.coords)[:3]]
        add_triangle(coords, open_axial, reverse=int(open_side) < 0)
        cap_triangle_count += 1
    for triangle in triangulate(rect):
        if float(triangle.area) <= 1e-9 or not rect.covers(triangle.representative_point()):
            continue
        coords = [(float(x), float(y)) for x, y in list(triangle.exterior.coords)[:3]]
        add_triangle(coords, opposite_axial, reverse=int(open_side) >= 0)
        cap_triangle_count += 1

    floor_circle = Polygon(_circle_points(plane_center, floor_radius, sections=sections))
    floor_triangle_count = 0
    for triangle in triangulate(floor_circle):
        if float(triangle.area) <= 1e-9 or not floor_circle.covers(triangle.representative_point()):
            continue
        coords = [(float(x), float(y)) for x, y in list(triangle.exterior.coords)[:3]]
        add_triangle(coords, floor_axial, reverse=int(open_side) < 0)
        floor_triangle_count += 1

    rect_ring = [(float(x), float(y)) for x, y in list(rect.exterior.coords)]
    for index in range(len(rect_ring) - 1):
        add_wall(rect_ring[index], rect_ring[index + 1], low=low, high=high, reverse=False)

    ring_points = [
        _circle_points(plane_center, radius, sections=sections)
        for _, radius in rings
    ]
    bore_face_count = 0
    shoulder_face_count = 0
    chamfer_face_count = 0
    rim_bevel_face_count = 0
    bevel_segment_index = (len(rings) - 2) if int(open_side) >= 0 else 0
    for ring_index in range(len(rings) - 1):
        left_axial, left_radius = rings[ring_index]
        right_axial, right_radius = rings[ring_index + 1]
        left_ring = ring_points[ring_index]
        right_ring = ring_points[ring_index + 1]
        if abs(left_axial - right_axial) <= 1e-9 and abs(left_radius - right_radius) <= 1e-9:
            continue
        for index in range(sections):
            next_index = (index + 1) % sections
            quad = [
                add_vertex(left_ring[index], left_axial),
                add_vertex(left_ring[next_index], left_axial),
                add_vertex(right_ring[next_index], right_axial),
                add_vertex(right_ring[index], right_axial),
            ]
            faces.append([quad[0], quad[2], quad[1]])
            faces.append([quad[0], quad[3], quad[2]])
            if abs(left_axial - right_axial) <= 1e-9:
                shoulder_face_count += 2
            elif abs(left_radius - right_radius) > 1e-9:
                chamfer_face_count += 2
                if bevel_applied and ring_index == bevel_segment_index:
                    rim_bevel_face_count += 2
            else:
                bore_face_count += 2

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()
    mesh.fix_normals()
    actual_bevel_applied = bool(bevel_applied) and max(radius for _, radius in rings) - min(radius for _, radius in rings) > 1e-9
    return mesh, {
        "cap_triangle_count": cap_triangle_count,
        "floor_triangle_count": floor_triangle_count,
        "bore_wall_face_count": bore_face_count,
        "shoulder_face_count": shoulder_face_count,
        "chamfer_face_count": chamfer_face_count,
        "bevel_face_count": rim_bevel_face_count,
        "bevel_applied": bool(bevel_applied),
        "ring_count": len(rings),
        "radial_section_count": sections,
        "min_radius_cm": float(min(radius for _, radius in rings)),
        "max_radius_cm": float(max(radius for _, radius in rings)),
        "open_side": "positive" if int(open_side) >= 0 else "negative",
        "floor_axial_cm": floor_axial,
        "result_face_count": len(mesh.faces),
        "result_watertight": bool(mesh.is_watertight),
        "bevel_applied": actual_bevel_applied,
        **clamp_stats,
    }


def _mesh_from_box_blind_revolved_profile_cuts(
    *,
    box_min: np.ndarray,
    box_max: np.ndarray,
    cut_axis: int,
    plane_axes: tuple[int, int],
    cuts: list[dict[str, Any]],
    sections: int = 48,
) -> tuple[trimesh.Trimesh, dict[str, Any]] | None:
    try:
        from shapely.geometry import Polygon
        from shapely.ops import triangulate, unary_union
    except (ImportError, ModuleNotFoundError):
        return None

    if not cuts:
        return None
    rect = Polygon(
        (
            (float(box_min[plane_axes[0]]), float(box_min[plane_axes[1]])),
            (float(box_max[plane_axes[0]]), float(box_min[plane_axes[1]])),
            (float(box_max[plane_axes[0]]), float(box_max[plane_axes[1]])),
            (float(box_min[plane_axes[0]]), float(box_max[plane_axes[1]])),
        )
    )
    low = float(box_min[cut_axis])
    high = float(box_max[cut_axis])

    prepared: list[dict[str, Any]] = []
    open_cutters = []
    open_area_sum = 0.0
    open_side_ref: int | None = None
    floor_ref: float | None = None
    radius_clamp_count = 0
    requested_max_radii: list[float] = []
    actual_max_radii: list[float] = []
    for cut in cuts:
        try:
            rings = [
                (float(point[0]), float(point[1]))
                for point in cut["rings"]
            ]
            center = np.asarray(cut["center"], dtype=np.float64)
            open_side_value = 1 if str(cut.get("open_side") or "positive") == "positive" else -1
            floor_axial = float(cut["floor_axial_cm"])
        except (KeyError, TypeError, ValueError, IndexError):
            return None
        if center.shape != (3,) or len(rings) < 2:
            return None
        if any(radius <= 1e-9 for _, radius in rings):
            return None
        if any(rings[index][0] > rings[index + 1][0] + 1e-9 for index in range(len(rings) - 1)):
            return None
        if open_side_ref is None:
            open_side_ref = open_side_value
        elif open_side_ref != open_side_value:
            return None
        if floor_ref is None:
            floor_ref = floor_axial
        elif abs(float(floor_ref) - floor_axial) > 1e-7:
            return None

        plane_center = np.asarray(
            [center[plane_axes[0]], center[plane_axes[1]]],
            dtype=np.float64,
        )
        clamped = _clamp_revolved_rings_to_rect(rect, plane_center, rings)
        if clamped is None:
            return None
        rings, clamp_stats = clamped
        if clamp_stats:
            radius_clamp_count += 1
            requested_max_radii.append(float(clamp_stats["requested_max_radius_cm"]))
            actual_max_radii.append(float(clamp_stats["actual_max_radius_cm"]))
        max_radius = max(radius for _, radius in rings)
        if not rect.contains(Polygon(_circle_points(plane_center, max_radius, sections=sections))):
            return None
        open_radius = float(rings[-1][1] if open_side_value >= 0 else rings[0][1])
        open_circle = Polygon(_circle_points(plane_center, open_radius, sections=sections))
        open_cutters.append(open_circle)
        open_area_sum += float(open_circle.area)
        prepared.append(
            {
                "center": center,
                "plane_center": plane_center,
                "rings": rings,
                "open_side": open_side_value,
                "floor_axial": floor_axial,
                "open_radius": open_radius,
                "floor_radius": float(rings[0][1] if open_side_value >= 0 else rings[-1][1]),
                "bevel_applied": bool(cut.get("bevel_applied"))
                and max(radius for _, radius in rings) - min(radius for _, radius in rings) > 1e-9,
            }
        )

    if open_side_ref is None or floor_ref is None:
        return None
    open_union = unary_union(open_cutters)
    if open_union.is_empty or abs(float(open_union.area) - open_area_sum) > 1e-6:
        return None
    remaining = rect.difference(open_union)
    if remaining.is_empty or float(remaining.area) <= 1e-9:
        return None

    vertices: list[tuple[float, float, float]] = []
    vertex_index: dict[tuple[int, int, int], int] = {}
    faces: list[list[int]] = []

    def add_vertex(plane_point: tuple[float, float], axial: float) -> int:
        coord = [0.0, 0.0, 0.0]
        coord[cut_axis] = float(axial)
        coord[plane_axes[0]] = float(plane_point[0])
        coord[plane_axes[1]] = float(plane_point[1])
        key = tuple(int(round(value * 1_000_000)) for value in coord)
        existing = vertex_index.get(key)
        if existing is not None:
            return existing
        vertex_index[key] = len(vertices)
        vertices.append((coord[0], coord[1], coord[2]))
        return len(vertices) - 1

    def add_triangle(
        points: list[tuple[float, float]],
        axial: float,
        *,
        reverse: bool,
    ) -> None:
        tri = [add_vertex(point, axial) for point in points]
        faces.append([tri[0], tri[2], tri[1]] if reverse else tri)

    def add_wall(
        a_point: tuple[float, float],
        b_point: tuple[float, float],
        *,
        low: float,
        high: float,
        reverse: bool,
    ) -> None:
        quad = [
            add_vertex(a_point, low),
            add_vertex(b_point, low),
            add_vertex(b_point, high),
            add_vertex(a_point, high),
        ]
        faces.append([quad[0], quad[1], quad[2]] if not reverse else [quad[0], quad[2], quad[1]])
        faces.append([quad[0], quad[2], quad[3]] if not reverse else [quad[0], quad[3], quad[2]])

    open_axial = high if open_side_ref >= 0 else low
    opposite_axial = low if open_side_ref >= 0 else high
    cap_triangle_count = 0
    for triangle in triangulate(remaining):
        if float(triangle.area) <= 1e-9 or not remaining.covers(triangle.representative_point()):
            continue
        coords = [(float(x), float(y)) for x, y in list(triangle.exterior.coords)[:3]]
        add_triangle(coords, open_axial, reverse=open_side_ref < 0)
        cap_triangle_count += 1
    for triangle in triangulate(rect):
        if float(triangle.area) <= 1e-9 or not rect.covers(triangle.representative_point()):
            continue
        coords = [(float(x), float(y)) for x, y in list(triangle.exterior.coords)[:3]]
        add_triangle(coords, opposite_axial, reverse=open_side_ref >= 0)
        cap_triangle_count += 1

    rect_ring = [(float(x), float(y)) for x, y in list(rect.exterior.coords)]
    for index in range(len(rect_ring) - 1):
        add_wall(rect_ring[index], rect_ring[index + 1], low=low, high=high, reverse=False)

    floor_triangle_count = 0
    bore_face_count = 0
    shoulder_face_count = 0
    chamfer_face_count = 0
    rim_bevel_face_count = 0
    ring_count = 0
    radii: list[float] = []
    bevel_cut_count = 0
    for item in prepared:
        rings = item["rings"]
        ring_count += len(rings)
        radii.extend(float(radius) for _, radius in rings)
        floor_circle = Polygon(
            _circle_points(item["plane_center"], float(item["floor_radius"]), sections=sections)
        )
        for triangle in triangulate(floor_circle):
            if float(triangle.area) <= 1e-9 or not floor_circle.covers(triangle.representative_point()):
                continue
            coords = [(float(x), float(y)) for x, y in list(triangle.exterior.coords)[:3]]
            add_triangle(coords, float(item["floor_axial"]), reverse=open_side_ref < 0)
            floor_triangle_count += 1

        ring_points = [
            _circle_points(item["plane_center"], radius, sections=sections)
            for _, radius in rings
        ]
        bevel_segment_index = (len(rings) - 2) if open_side_ref >= 0 else 0
        if item["bevel_applied"]:
            bevel_cut_count += 1
        for ring_index in range(len(rings) - 1):
            left_axial, left_radius = rings[ring_index]
            right_axial, right_radius = rings[ring_index + 1]
            left_ring = ring_points[ring_index]
            right_ring = ring_points[ring_index + 1]
            if abs(left_axial - right_axial) <= 1e-9 and abs(left_radius - right_radius) <= 1e-9:
                continue
            for section_index in range(sections):
                next_index = (section_index + 1) % sections
                quad = [
                    add_vertex(left_ring[section_index], left_axial),
                    add_vertex(left_ring[next_index], left_axial),
                    add_vertex(right_ring[next_index], right_axial),
                    add_vertex(right_ring[section_index], right_axial),
                ]
                faces.append([quad[0], quad[2], quad[1]])
                faces.append([quad[0], quad[3], quad[2]])
                if abs(left_axial - right_axial) <= 1e-9:
                    shoulder_face_count += 2
                elif abs(left_radius - right_radius) > 1e-9:
                    chamfer_face_count += 2
                    if item["bevel_applied"] and ring_index == bevel_segment_index:
                        rim_bevel_face_count += 2
                else:
                    bore_face_count += 2

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()
    mesh.fix_normals()
    stats: dict[str, Any] = {
        "cap_triangle_count": cap_triangle_count,
        "floor_triangle_count": floor_triangle_count,
        "bore_wall_face_count": bore_face_count,
        "shoulder_face_count": shoulder_face_count,
        "chamfer_face_count": chamfer_face_count,
        "bevel_face_count": rim_bevel_face_count,
        "bevel_applied": bevel_cut_count > 0,
        "bevel_cut_count": bevel_cut_count,
        "ring_count": ring_count,
        "radial_section_count": sections,
        "open_side": "positive" if open_side_ref >= 0 else "negative",
        "floor_axial_cm": float(floor_ref),
        "cut_count": len(prepared),
        "result_face_count": len(mesh.faces),
        "result_watertight": bool(mesh.is_watertight),
    }
    if radii:
        stats["min_radius_cm"] = float(min(radii))
        stats["max_radius_cm"] = float(max(radii))
    if radius_clamp_count:
        stats["profile_radius_clamped"] = True
        stats["profile_radius_clamp_count"] = int(radius_clamp_count)
        stats["requested_max_radius_cm"] = float(max(requested_max_radii))
        stats["actual_max_radius_cm"] = float(max(actual_max_radii))
    return mesh, stats


def _mesh_from_box_opposite_side_blind_profile_cuts(
    *,
    box_min: np.ndarray,
    box_max: np.ndarray,
    cut_axis: int,
    plane_axes: tuple[int, int],
    cuts: list[dict[str, Any]],
    sections: int = 48,
) -> tuple[trimesh.Trimesh, dict[str, Any]] | None:
    try:
        from shapely.geometry import Polygon
        from shapely.ops import triangulate, unary_union
    except (ImportError, ModuleNotFoundError):
        return None

    if len(cuts) < 2:
        return None
    low = float(box_min[cut_axis])
    high = float(box_max[cut_axis])
    rect = Polygon(
        (
            (float(box_min[plane_axes[0]]), float(box_min[plane_axes[1]])),
            (float(box_max[plane_axes[0]]), float(box_min[plane_axes[1]])),
            (float(box_max[plane_axes[0]]), float(box_max[plane_axes[1]])),
            (float(box_min[plane_axes[0]]), float(box_max[plane_axes[1]])),
        )
    )
    prepared: list[dict[str, Any]] = []
    cap_cutters = []
    positive_cap_cutters = []
    negative_cap_cutters = []
    cap_area_sum = 0.0
    floor_values: list[float] = []
    extruded_cut_count = 0
    revolved_cut_count = 0

    def valid_polygon(geometry: Any) -> Any | None:
        if not geometry.is_valid:
            geometry = geometry.buffer(0)
        if geometry.is_empty or float(geometry.area) <= 1e-9:
            return None
        return geometry

    for cut in cuts:
        cut_kind = str(cut.get("cut_kind") or "")
        try:
            open_side = 1 if str(cut.get("open_side") or "positive") == "positive" else -1
            floor_axial = float(cut["floor_axial_cm"])
        except (KeyError, TypeError, ValueError):
            return None
        if floor_axial <= low + 1e-9 or floor_axial >= high - 1e-9:
            return None
        floor_values.append(float(floor_axial))

        if cut_kind == "extruded_blind":
            try:
                profile_points = [
                    (float(point[0]), float(point[1]))
                    for point in cut["profile_points"]
                ]
            except (KeyError, TypeError, ValueError, IndexError):
                return None
            if len(profile_points) < 3:
                return None
            cutter = valid_polygon(Polygon(profile_points))
            if cutter is None or not rect.contains(cutter):
                return None
            bevel_width = max(0.0, float(cut.get("bevel_width") or 0.0))
            if bevel_width > 1e-9:
                return None
            cap_cutter = cutter
            extruded_cut_count += 1
            item = {
                "cut_kind": "extruded_blind",
                "profile_points": profile_points,
                "cutter": cutter,
                "cap_cutter": cap_cutter,
                "floor_axial": float(floor_axial),
                "open_side": int(open_side),
            }
        elif cut_kind in {"revolved_blind", "cylinder_blind"}:
            try:
                rings = [
                    (float(point[0]), float(point[1]))
                    for point in cut["rings"]
                ]
                center = np.asarray(cut["center"], dtype=np.float64)
            except (KeyError, TypeError, ValueError, IndexError):
                return None
            if center.shape != (3,) or len(rings) < 2:
                return None
            if any(radius <= 1e-9 for _, radius in rings):
                return None
            if any(rings[index][0] > rings[index + 1][0] + 1e-9 for index in range(len(rings) - 1)):
                return None
            plane_center = np.asarray(
                [center[plane_axes[0]], center[plane_axes[1]]],
                dtype=np.float64,
            )
            max_radius = max(radius for _, radius in rings)
            max_circle = valid_polygon(Polygon(_circle_points(plane_center, max_radius, sections=sections)))
            if max_circle is None or not rect.contains(max_circle):
                return None
            open_radius = float(rings[-1][1] if open_side >= 0 else rings[0][1])
            floor_radius = float(rings[0][1] if open_side >= 0 else rings[-1][1])
            cap_cutter = valid_polygon(Polygon(_circle_points(plane_center, open_radius, sections=sections)))
            if cap_cutter is None:
                return None
            revolved_cut_count += 1
            item = {
                "cut_kind": cut_kind,
                "center": center,
                "plane_center": plane_center,
                "rings": rings,
                "open_side": int(open_side),
                "floor_axial": float(floor_axial),
                "floor_radius": floor_radius,
                "cap_cutter": cap_cutter,
                "bevel_applied": bool(cut.get("bevel_applied")),
            }
        else:
            return None

        cap_cutters.append(cap_cutter)
        cap_area_sum += float(cap_cutter.area)
        if open_side >= 0:
            positive_cap_cutters.append(cap_cutter)
        else:
            negative_cap_cutters.append(cap_cutter)
        prepared.append(item)

    if not positive_cap_cutters or not negative_cap_cutters:
        return None
    cap_union = unary_union(cap_cutters)
    tolerance = max(1e-6, abs(cap_area_sum) * 1e-7)
    if cap_union.is_empty or abs(float(cap_union.area) - cap_area_sum) > tolerance:
        return None
    positive_union = unary_union(positive_cap_cutters)
    negative_union = unary_union(negative_cap_cutters)
    high_cap = rect.difference(positive_union)
    low_cap = rect.difference(negative_union)
    if (
        high_cap.is_empty
        or low_cap.is_empty
        or float(high_cap.area) <= 1e-9
        or float(low_cap.area) <= 1e-9
    ):
        return None

    vertices: list[tuple[float, float, float]] = []
    vertex_index: dict[tuple[int, int, int], int] = {}
    faces: list[list[int]] = []

    def add_vertex(plane_point: tuple[float, float], axial: float) -> int:
        coord = [0.0, 0.0, 0.0]
        coord[cut_axis] = float(axial)
        coord[plane_axes[0]] = float(plane_point[0])
        coord[plane_axes[1]] = float(plane_point[1])
        key = tuple(int(round(value * 1_000_000)) for value in coord)
        existing = vertex_index.get(key)
        if existing is not None:
            return existing
        vertex_index[key] = len(vertices)
        vertices.append((coord[0], coord[1], coord[2]))
        return len(vertices) - 1

    def add_triangle(points: list[tuple[float, float]], axial: float, *, reverse: bool) -> None:
        triangle = [add_vertex(point, axial) for point in points]
        faces.append([triangle[0], triangle[2], triangle[1]] if reverse else triangle)

    def add_wall(
        a_point: tuple[float, float],
        b_point: tuple[float, float],
        *,
        wall_low: float,
        wall_high: float,
        reverse: bool,
    ) -> None:
        quad = [
            add_vertex(a_point, wall_low),
            add_vertex(b_point, wall_low),
            add_vertex(b_point, wall_high),
            add_vertex(a_point, wall_high),
        ]
        faces.append([quad[0], quad[1], quad[2]] if not reverse else [quad[0], quad[2], quad[1]])
        faces.append([quad[0], quad[2], quad[3]] if not reverse else [quad[0], quad[3], quad[2]])

    def add_polygon_cap(polygon: Any, axial: float, *, reverse: bool) -> int:
        count = 0
        geoms = list(getattr(polygon, "geoms", ()) or ())
        if geoms:
            for geom in geoms:
                count += add_polygon_cap(geom, axial, reverse=reverse)
            return count
        try:
            vertices_2d, faces_2d = trimesh.creation.triangulate_polygon(
                polygon,
                force_vertices=True,
            )
        except (AttributeError, ValueError, RuntimeError, ImportError, ModuleNotFoundError):
            for triangle in triangulate(polygon):
                if float(triangle.area) <= 1e-9 or not polygon.covers(triangle.representative_point()):
                    continue
                coords = [(float(x), float(y)) for x, y in list(triangle.exterior.coords)[:3]]
                add_triangle(coords, axial, reverse=reverse)
                count += 1
            return count
        for face in faces_2d:
            coords = [
                (float(vertices_2d[int(index)][0]), float(vertices_2d[int(index)][1]))
                for index in face[:3]
            ]
            if len(coords) < 3:
                continue
            add_triangle(coords, axial, reverse=reverse)
            count += 1
        return count

    cap_triangle_count = 0
    cap_triangle_count += add_polygon_cap(low_cap, low, reverse=True)
    cap_triangle_count += add_polygon_cap(high_cap, high, reverse=False)

    rect_ring = [(float(x), float(y)) for x, y in list(rect.exterior.coords)]
    for index in range(len(rect_ring) - 1):
        add_wall(rect_ring[index], rect_ring[index + 1], wall_low=low, wall_high=high, reverse=False)

    floor_triangle_count = 0
    inner_wall_face_count = 0
    bore_face_count = 0
    shoulder_face_count = 0
    chamfer_face_count = 0
    ring_count = 0
    radii: list[float] = []
    bevel_cut_count = 0
    profile_vertex_count = 0

    for item in prepared:
        open_side = int(item["open_side"])
        open_axial = high if open_side >= 0 else low
        floor_reverse = open_side < 0
        if item["cut_kind"] == "extruded_blind":
            cutter = item["cutter"]
            cutter_ring = [(float(x), float(y)) for x, y in list(cutter.exterior.coords)]
            profile_vertex_count += max(0, len(cutter_ring) - 1)
            for triangle in triangulate(cutter):
                if float(triangle.area) <= 1e-9 or not cutter.covers(triangle.representative_point()):
                    continue
                coords = [(float(x), float(y)) for x, y in list(triangle.exterior.coords)[:3]]
                add_triangle(coords, float(item["floor_axial"]), reverse=floor_reverse)
                floor_triangle_count += 1
            wall_low = min(float(item["floor_axial"]), open_axial)
            wall_high = max(float(item["floor_axial"]), open_axial)
            if wall_high > wall_low + 1e-9:
                for index in range(len(cutter_ring) - 1):
                    add_wall(
                        cutter_ring[index],
                        cutter_ring[index + 1],
                        wall_low=wall_low,
                        wall_high=wall_high,
                        reverse=True,
                    )
                    inner_wall_face_count += 2
            continue

        rings = item["rings"]
        ring_count += len(rings)
        radii.extend(float(radius) for _, radius in rings)
        if item["bevel_applied"]:
            bevel_cut_count += 1
        floor_circle = Polygon(
            _circle_points(item["plane_center"], float(item["floor_radius"]), sections=sections)
        )
        for triangle in triangulate(floor_circle):
            if float(triangle.area) <= 1e-9 or not floor_circle.covers(triangle.representative_point()):
                continue
            coords = [(float(x), float(y)) for x, y in list(triangle.exterior.coords)[:3]]
            add_triangle(coords, float(item["floor_axial"]), reverse=floor_reverse)
            floor_triangle_count += 1
        ring_points = [
            _circle_points(item["plane_center"], radius, sections=sections)
            for _, radius in rings
        ]
        for ring_index in range(len(rings) - 1):
            left_axial, left_radius = rings[ring_index]
            right_axial, right_radius = rings[ring_index + 1]
            left_ring = ring_points[ring_index]
            right_ring = ring_points[ring_index + 1]
            if abs(left_axial - right_axial) <= 1e-9 and abs(left_radius - right_radius) <= 1e-9:
                continue
            for section_index in range(sections):
                next_index = (section_index + 1) % sections
                quad = [
                    add_vertex(left_ring[section_index], left_axial),
                    add_vertex(left_ring[next_index], left_axial),
                    add_vertex(right_ring[next_index], right_axial),
                    add_vertex(right_ring[section_index], right_axial),
                ]
                faces.append([quad[0], quad[2], quad[1]])
                faces.append([quad[0], quad[3], quad[2]])
                if abs(left_axial - right_axial) <= 1e-9:
                    shoulder_face_count += 2
                elif abs(left_radius - right_radius) > 1e-9:
                    chamfer_face_count += 2
                else:
                    bore_face_count += 2

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()
    mesh.fix_normals()
    if not bool(mesh.is_watertight):
        return None
    unique_floor_values = sorted({round(float(value), 9) for value in floor_values})
    same_floor = len(unique_floor_values) == 1
    stats: dict[str, Any] = {
        "cap_triangle_count": cap_triangle_count,
        "floor_triangle_count": floor_triangle_count,
        "inner_wall_face_count": inner_wall_face_count,
        "bevel_face_count": 0,
        "bore_wall_face_count": bore_face_count,
        "shoulder_face_count": shoulder_face_count,
        "chamfer_face_count": chamfer_face_count,
        "rim_bevel_face_count": 0,
        "bevel_applied": bevel_cut_count > 0,
        "bevel_cut_count": bevel_cut_count,
        "ring_count": ring_count,
        "profile_vertex_count": profile_vertex_count,
        "radial_section_count": sections,
        "open_sides": ["negative", "positive"],
        "opposite_open_sides": True,
        "floor_axial_values_cm": [float(value) for value in unique_floor_values],
        "mixed_floor_depths": not same_floor,
        "cut_count": len(prepared),
        "extruded_cut_count": extruded_cut_count,
        "revolved_cut_count": revolved_cut_count,
        "result_face_count": len(mesh.faces),
        "result_watertight": bool(mesh.is_watertight),
    }
    if same_floor:
        stats["floor_axial_cm"] = float(unique_floor_values[0])
    if radii:
        stats["min_radius_cm"] = float(min(radii))
        stats["max_radius_cm"] = float(max(radii))
    return mesh, stats


def _mesh_from_box_layered_blind_profile_cut_cells(
    *,
    box_min: np.ndarray,
    box_max: np.ndarray,
    cut_axis: int,
    plane_axes: tuple[int, int],
    rect: Any,
    prepared: list[dict[str, Any]],
    open_side: int,
) -> tuple[trimesh.Trimesh, dict[str, Any]] | None:
    if not prepared:
        return None
    low = float(box_min[cut_axis])
    high = float(box_max[cut_axis])

    def polygons(geometry: Any) -> list[Any]:
        if geometry.is_empty:
            return []
        if geometry.geom_type == "Polygon":
            return [geometry]
        if geometry.geom_type == "MultiPolygon":
            return list(geometry.geoms)
        if geometry.geom_type == "GeometryCollection":
            out = []
            for child in geometry.geoms:
                out.extend(polygons(child))
            return out
        return []

    def valid_geometry(geometry: Any) -> Any | None:
        if not geometry.is_valid:
            geometry = geometry.buffer(0)
        if geometry.is_empty or float(geometry.area) <= 1e-9:
            return None
        return geometry

    cells: list[dict[str, Any]] = [
        {
            "geometry": rect,
            "low": low,
            "high": high,
        }
    ]
    for item in prepared:
        cutter = item.get("cap_cutter")
        if cutter is None or cutter.is_empty:
            return None
        if item["cut_kind"] == "extruded_blind":
            if bool(item.get("bevel_ring")) or float(item.get("bevel_width") or 0.0) > 1e-9:
                return None
        else:
            if bool(item.get("bevel_applied")):
                return None
            try:
                radii = [float(radius) for _, radius in item["rings"]]
                open_radius = float(item["open_radius"])
                floor_radius = float(item["floor_radius"])
            except (KeyError, TypeError, ValueError):
                return None
            if (
                not radii
                or max(radii) - min(radii) > 1e-7
                or abs(open_radius - floor_radius) > 1e-7
            ):
                return None
        try:
            floor_axial = float(item["floor_axial"])
        except (KeyError, TypeError, ValueError):
            return None
        next_cells: list[dict[str, Any]] = []
        for cell in cells:
            geometry = cell["geometry"]
            inside = valid_geometry(geometry.intersection(cutter))
            outside = valid_geometry(geometry.difference(cutter))
            if outside is not None:
                next_cells.append(
                    {
                        "geometry": outside,
                        "low": float(cell["low"]),
                        "high": float(cell["high"]),
                    }
                )
            if inside is not None:
                if open_side >= 0:
                    next_cells.append(
                        {
                            "geometry": inside,
                            "low": float(cell["low"]),
                            "high": min(float(cell["high"]), floor_axial),
                        }
                    )
                else:
                    next_cells.append(
                        {
                            "geometry": inside,
                            "low": max(float(cell["low"]), floor_axial),
                            "high": float(cell["high"]),
                        }
                    )
        cells = [
            cell
            for cell in next_cells
            if float(cell["high"]) > float(cell["low"]) + 1e-9
        ]
        if not cells:
            return None

    entries: list[dict[str, Any]] = []
    for cell in cells:
        for polygon in polygons(cell["geometry"]):
            if float(polygon.area) <= 1e-9:
                continue
            entries.append(
                {
                    "polygon": polygon,
                    "low": float(cell["low"]),
                    "high": float(cell["high"]),
                }
            )
    if not entries:
        return None
    built = _mesh_from_axis_extruded_polygon_union(
        entries,
        axis=cut_axis,
        plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
    )
    if built is None:
        return None
    mesh, stats = built
    stats = {
        **stats,
        "layered_cell_count": len(cells),
        "layered_entry_count": len(entries),
    }
    return mesh, stats


def _mesh_from_box_sampled_layered_blind_profile_cut_cells(
    *,
    box_min: np.ndarray,
    box_max: np.ndarray,
    cut_axis: int,
    plane_axes: tuple[int, int],
    rect: Any,
    prepared: list[dict[str, Any]],
    open_side: int,
    sections: int = 48,
) -> tuple[trimesh.Trimesh, dict[str, Any]] | None:
    try:
        from shapely.geometry import Polygon
        from shapely.ops import unary_union
    except (ImportError, ModuleNotFoundError):
        return None
    if not prepared:
        return None
    low = float(box_min[cut_axis])
    high = float(box_max[cut_axis])
    open_axial = high if open_side >= 0 else low
    has_sampled_boundary = False

    def valid_geometry(geometry: Any) -> Any | None:
        if not geometry.is_valid:
            geometry = geometry.buffer(0)
        if geometry.is_empty or float(geometry.area) <= 1e-9:
            return None
        return geometry

    def polygon_at_axial(item: dict[str, Any], axial: float) -> Any | None:
        floor_axial = float(item["floor_axial"])
        if open_side >= 0:
            if axial < floor_axial - 1e-9 or axial > high + 1e-9:
                return None
        elif axial > floor_axial + 1e-9 or axial < low - 1e-9:
            return None
        if item["cut_kind"] == "extruded_blind":
            if bool(item.get("bevel_ring")) and item.get("expanded_points"):
                bevel_width = max(0.0, float(item.get("bevel_width") or 0.0))
                bevel_depth = min(bevel_width, max(abs(open_axial - floor_axial) * 0.45, 0.0))
                shoulder_axial = open_axial - open_side * bevel_depth
                if bevel_depth > 1e-9 and (
                    (open_side >= 0 and axial > shoulder_axial + 1e-9)
                    or (open_side < 0 and axial < shoulder_axial - 1e-9)
                ):
                    denominator = max(abs(open_axial - shoulder_axial), 1e-9)
                    t = min(1.0, max(0.0, abs(axial - shoulder_axial) / denominator))
                    try:
                        core_points = [
                            (float(point[0]), float(point[1]))
                            for point in item["profile_points"]
                        ]
                        expanded_points = [
                            (float(point[0]), float(point[1]))
                            for point in item["expanded_points"]
                        ]
                    except (KeyError, TypeError, ValueError, IndexError):
                        return None
                    if len(core_points) == len(expanded_points) and len(core_points) >= 3:
                        polygon = Polygon(
                            [
                                (
                                    core_x + (expanded_x - core_x) * t,
                                    core_y + (expanded_y - core_y) * t,
                                )
                                for (core_x, core_y), (expanded_x, expanded_y) in zip(
                                    core_points,
                                    expanded_points,
                                    strict=True,
                                )
                            ]
                        )
                        return valid_geometry(polygon.intersection(rect))
            cutter = item.get("cutter")
            return valid_geometry(cutter.intersection(rect)) if cutter is not None else None

        try:
            rings = [
                (float(ring[0]), float(ring[1]))
                for ring in item["rings"]
            ]
            plane_center = np.asarray(item["plane_center"], dtype=np.float64)
        except (KeyError, TypeError, ValueError, IndexError):
            return None
        radius = _radius_at_profile_axial(rings, float(axial))
        if radius is None or radius <= 1e-9:
            return None
        return valid_geometry(
            Polygon(_circle_points(plane_center, float(radius), sections=sections)).intersection(rect)
        )

    levels: set[float] = {low, high}
    sampled_segment_count = 0
    for item in prepared:
        floor_axial = float(item["floor_axial"])
        levels.add(floor_axial)
        if item["cut_kind"] == "extruded_blind":
            if bool(item.get("bevel_ring")) and item.get("expanded_points"):
                bevel_width = max(0.0, float(item.get("bevel_width") or 0.0))
                bevel_depth = min(bevel_width, max(abs(open_axial - floor_axial) * 0.45, 0.0))
                if bevel_depth > 1e-9:
                    shoulder_axial = open_axial - open_side * bevel_depth
                    segment_low = min(shoulder_axial, open_axial)
                    segment_high = max(shoulder_axial, open_axial)
                    for index in range(9):
                        levels.add(segment_low + (segment_high - segment_low) * (index / 8.0))
                    sampled_segment_count += 1
                    has_sampled_boundary = True
            continue
        try:
            rings = [
                (float(ring[0]), float(ring[1]))
                for ring in item["rings"]
            ]
        except (KeyError, TypeError, ValueError, IndexError):
            return None
        for axial, _ in rings:
            levels.add(float(axial))
        for (left_axial, left_radius), (right_axial, right_radius) in zip(rings, rings[1:], strict=False):
            if abs(float(left_radius) - float(right_radius)) <= 1e-9:
                continue
            segment_low = min(float(left_axial), float(right_axial))
            segment_high = max(float(left_axial), float(right_axial))
            for index in range(9):
                levels.add(segment_low + (segment_high - segment_low) * (index / 8.0))
            sampled_segment_count += 1
            has_sampled_boundary = True
    if not has_sampled_boundary:
        return None

    axis_levels = _axis_values(*levels)
    entries: list[dict[str, Any]] = []
    slab_count = 0
    for left, right in zip(axis_levels, axis_levels[1:], strict=False):
        if right <= left + 1e-9:
            continue
        mid = (left + right) * 0.5
        cutters = [
            cutter
            for cutter in (polygon_at_axial(item, mid) for item in prepared)
            if cutter is not None and not cutter.is_empty
        ]
        removed = unary_union(cutters) if cutters else None
        remaining = rect if removed is None or removed.is_empty else rect.difference(removed)
        remaining = valid_geometry(remaining)
        if remaining is None:
            continue
        entries.append({"polygon": remaining, "low": float(left), "high": float(right)})
        slab_count += 1
    if not entries:
        return None
    built = _mesh_from_axis_extruded_polygon_union(
        entries,
        axis=cut_axis,
        plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
    )
    if built is None:
        return None
    mesh, stats = built
    stats = {
        **stats,
        "sampled_layered_profile_cut_mesh": True,
        "sampled_bevel_profile_cut_mesh": True,
        "sampled_layer_count": int(slab_count),
        "sampled_axis_level_count": len(axis_levels),
        "sampled_bevel_segment_count": int(sampled_segment_count),
    }
    return mesh, stats


def _mesh_from_box_blind_mixed_profile_cuts(
    *,
    box_min: np.ndarray,
    box_max: np.ndarray,
    cut_axis: int,
    plane_axes: tuple[int, int],
    cuts: list[dict[str, Any]],
    sections: int = 48,
) -> tuple[trimesh.Trimesh, dict[str, Any]] | None:
    try:
        from shapely.geometry import Polygon
        from shapely.ops import triangulate, unary_union
    except (ImportError, ModuleNotFoundError):
        return None

    if not cuts:
        return None
    rect = Polygon(
        (
            (float(box_min[plane_axes[0]]), float(box_min[plane_axes[1]])),
            (float(box_max[plane_axes[0]]), float(box_min[plane_axes[1]])),
            (float(box_max[plane_axes[0]]), float(box_max[plane_axes[1]])),
            (float(box_min[plane_axes[0]]), float(box_max[plane_axes[1]])),
        )
    )
    low = float(box_min[cut_axis])
    high = float(box_max[cut_axis])
    prepared: list[dict[str, Any]] = []
    cap_cutters = []
    cap_area_sum = 0.0
    open_side_ref: int | None = None
    open_side_values: set[int] = set()
    floor_values: list[float] = []
    extruded_cut_count = 0
    revolved_cut_count = 0

    def valid_polygon(geometry: Any) -> Any | None:
        if not geometry.is_valid:
            geometry = geometry.buffer(0)
        if geometry.is_empty or float(geometry.area) <= 1e-9:
            return None
        return geometry

    for cut in cuts:
        cut_kind = str(cut.get("cut_kind") or "")
        try:
            open_side_value = 1 if str(cut.get("open_side") or "positive") == "positive" else -1
            floor_axial = float(cut["floor_axial_cm"])
        except (KeyError, TypeError, ValueError):
            return None
        open_side_values.add(open_side_value)
        if open_side_ref is None:
            open_side_ref = open_side_value
        if floor_axial <= low + 1e-9 or floor_axial >= high - 1e-9:
            return None
        floor_values.append(floor_axial)

        if cut_kind == "extruded_blind":
            try:
                profile_points = [
                    (float(point[0]), float(point[1]))
                    for point in cut["profile_points"]
                ]
            except (KeyError, TypeError, ValueError, IndexError):
                return None
            if len(profile_points) < 3:
                return None
            cutter_raw = valid_polygon(Polygon(profile_points))
            if cutter_raw is None:
                return None
            clipped_by_box = not bool(rect.covers(cutter_raw))
            cutter = valid_polygon(cutter_raw.intersection(rect))
            if cutter is None:
                return None
            bevel_width = max(0.0, float(cut.get("bevel_width") or 0.0))
            cap_cutter = cutter
            bevel_ring = False
            expanded_points: list[tuple[float, float]] = []
            bevel_clipped_by_box = False
            if bevel_width > 1e-9:
                centroid = cutter.centroid
                cx = float(centroid.x)
                cy = float(centroid.y)
                for point_x, point_y in profile_points:
                    dx = float(point_x) - cx
                    dy = float(point_y) - cy
                    length = math.hypot(dx, dy)
                    if length <= 1e-9:
                        expanded_points.append((float(point_x), float(point_y)))
                    else:
                        scale = (length + bevel_width) / length
                        expanded_points.append((cx + dx * scale, cy + dy * scale))
                expanded = valid_polygon(Polygon(expanded_points))
                expanded_clipped = valid_polygon(expanded.intersection(rect)) if expanded is not None else None
                if (
                    expanded_clipped is not None
                    and float(expanded_clipped.area) > float(cutter.area) + 1e-9
                ):
                    cap_cutter = expanded_clipped
                    bevel_ring = True
                    bevel_clipped_by_box = not bool(rect.covers(expanded))
            cap_cutters.append(cap_cutter)
            cap_area_sum += float(cap_cutter.area)
            extruded_cut_count += 1
            prepared.append(
                {
                    "cut_kind": "extruded_blind",
                    "profile_points": profile_points,
                    "cutter": cutter,
                    "cap_cutter": cap_cutter,
                    "expanded_points": expanded_points,
                    "bevel_width": bevel_width,
                    "bevel_ring": bevel_ring,
                    "bevel_clipped_by_box": bool(bevel_clipped_by_box),
                    "floor_axial": floor_axial,
                    "open_side": open_side_value,
                    "clipped_by_box": bool(clipped_by_box),
                }
            )
            continue

        if cut_kind in {"revolved_blind", "cylinder_blind"}:
            try:
                rings = [
                    (float(point[0]), float(point[1]))
                    for point in cut["rings"]
                ]
                center = np.asarray(cut["center"], dtype=np.float64)
            except (KeyError, TypeError, ValueError, IndexError):
                return None
            if center.shape != (3,) or len(rings) < 2:
                return None
            if any(radius <= 1e-9 for _, radius in rings):
                return None
            if any(rings[index][0] > rings[index + 1][0] + 1e-9 for index in range(len(rings) - 1)):
                return None
            plane_center = np.asarray(
                [center[plane_axes[0]], center[plane_axes[1]]],
                dtype=np.float64,
            )
            max_radius = max(radius for _, radius in rings)
            max_circle = valid_polygon(Polygon(_circle_points(plane_center, max_radius, sections=sections)))
            if max_circle is None:
                return None
            clipped_by_box = not bool(rect.covers(max_circle))
            max_circle_clipped = valid_polygon(max_circle.intersection(rect))
            if max_circle_clipped is None:
                return None
            open_radius = float(rings[-1][1] if open_side_value >= 0 else rings[0][1])
            open_circle_raw = valid_polygon(Polygon(_circle_points(plane_center, open_radius, sections=sections)))
            if open_circle_raw is None:
                return None
            open_circle = valid_polygon(open_circle_raw.intersection(rect))
            if open_circle is None:
                return None
            cap_cutters.append(open_circle)
            cap_area_sum += float(open_circle.area)
            revolved_cut_count += 1
            prepared.append(
                {
                    "cut_kind": cut_kind,
                    "center": center,
                    "plane_center": plane_center,
                    "rings": rings,
                    "open_side": open_side_value,
                    "floor_axial": floor_axial,
                    "open_radius": open_radius,
                    "floor_radius": float(rings[0][1] if open_side_value >= 0 else rings[-1][1]),
                    "cap_cutter": open_circle,
                    "bevel_applied": bool(cut.get("bevel_applied")),
                    "clipped_by_box": bool(clipped_by_box),
                }
            )
            continue
        return None

    if not floor_values:
        return None
    if len(open_side_values) > 1:
        return _mesh_from_box_opposite_side_blind_profile_cuts(
            box_min=box_min,
            box_max=box_max,
            cut_axis=cut_axis,
            plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
            cuts=cuts,
            sections=sections,
        )
    if open_side_ref is None:
        return None
    cap_union = unary_union(cap_cutters)
    tolerance = max(1e-6, abs(cap_area_sum) * 1e-7)
    if cap_union.is_empty:
        return None
    overlapping_caps = abs(float(cap_union.area) - cap_area_sum) > tolerance
    remaining_open_cap = rect.difference(cap_union)
    if remaining_open_cap.is_empty or float(remaining_open_cap.area) <= 1e-9:
        return None

    open_axial = high if open_side_ref >= 0 else low
    opposite_axial = low if open_side_ref >= 0 else high
    floor_reverse = open_side_ref < 0
    open_cap_reverse = open_side_ref < 0

    vertices: list[tuple[float, float, float]] = []
    vertex_index: dict[tuple[int, int, int], int] = {}
    faces: list[list[int]] = []

    def add_vertex(plane_point: tuple[float, float], axial: float) -> int:
        coord = [0.0, 0.0, 0.0]
        coord[cut_axis] = float(axial)
        coord[plane_axes[0]] = float(plane_point[0])
        coord[plane_axes[1]] = float(plane_point[1])
        key = tuple(int(round(value * 1_000_000)) for value in coord)
        existing = vertex_index.get(key)
        if existing is not None:
            return existing
        vertex_index[key] = len(vertices)
        vertices.append((coord[0], coord[1], coord[2]))
        return len(vertices) - 1

    def add_triangle(points: list[tuple[float, float]], axial: float, *, reverse: bool) -> None:
        triangle = [add_vertex(point, axial) for point in points]
        faces.append([triangle[0], triangle[2], triangle[1]] if reverse else triangle)

    def add_wall(
        a_point: tuple[float, float],
        b_point: tuple[float, float],
        *,
        wall_low: float,
        wall_high: float,
        reverse: bool,
    ) -> None:
        quad = [
            add_vertex(a_point, wall_low),
            add_vertex(b_point, wall_low),
            add_vertex(b_point, wall_high),
            add_vertex(a_point, wall_high),
        ]
        faces.append([quad[0], quad[1], quad[2]] if not reverse else [quad[0], quad[2], quad[1]])
        faces.append([quad[0], quad[2], quad[3]] if not reverse else [quad[0], quad[3], quad[2]])

    def add_polygon_cap(polygon: Any, axial: float, *, reverse: bool) -> int:
        count = 0
        geoms = list(getattr(polygon, "geoms", ()) or ())
        if geoms:
            for geom in geoms:
                count += add_polygon_cap(geom, axial, reverse=reverse)
            return count
        try:
            vertices_2d, faces_2d = trimesh.creation.triangulate_polygon(
                polygon,
                force_vertices=True,
            )
        except (AttributeError, ValueError, RuntimeError, ImportError, ModuleNotFoundError):
            for triangle in triangulate(polygon):
                if float(triangle.area) <= 1e-9 or not polygon.covers(triangle.representative_point()):
                    continue
                coords = [(float(x), float(y)) for x, y in list(triangle.exterior.coords)[:3]]
                add_triangle(coords, axial, reverse=reverse)
                count += 1
            return count
        for face in faces_2d:
            coords = [
                (float(vertices_2d[int(index)][0]), float(vertices_2d[int(index)][1]))
                for index in face[:3]
            ]
            if len(coords) < 3:
                continue
            add_triangle(coords, axial, reverse=reverse)
            count += 1
        return count

    cap_triangle_count = 0
    cap_triangle_count += add_polygon_cap(
        remaining_open_cap,
        open_axial,
        reverse=open_cap_reverse,
    )
    cap_triangle_count += add_polygon_cap(
        rect,
        opposite_axial,
        reverse=open_side_ref >= 0,
    )

    rect_ring = [(float(x), float(y)) for x, y in list(rect.exterior.coords)]
    for index in range(len(rect_ring) - 1):
        add_wall(rect_ring[index], rect_ring[index + 1], wall_low=low, wall_high=high, reverse=False)

    floor_triangle_count = 0
    inner_wall_face_count = 0
    bevel_face_count = 0
    bevel_cut_count = 0
    profile_vertex_count = 0
    bore_face_count = 0
    shoulder_face_count = 0
    chamfer_face_count = 0
    rim_bevel_face_count = 0
    ring_count = 0
    radii: list[float] = []

    needs_layered_cells = overlapping_caps or any(
        bool(item.get("clipped_by_box")) or bool(item.get("bevel_clipped_by_box"))
        for item in prepared
    )
    if needs_layered_cells:
        layered_cells = _mesh_from_box_layered_blind_profile_cut_cells(
            box_min=box_min,
            box_max=box_max,
            cut_axis=cut_axis,
            plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
            rect=rect,
            prepared=prepared,
            open_side=open_side_ref,
        )
        if layered_cells is not None:
            mesh, layered_stats = layered_cells
            for item in prepared:
                if item["cut_kind"] == "extruded_blind":
                    profile_vertex_count += max(0, len(list(item["cutter"].exterior.coords)) - 1)
                    if bool(item.get("bevel_ring")):
                        bevel_cut_count += 1
                    continue
                rings = item["rings"]
                ring_count += len(rings)
                radii.extend(float(radius) for _, radius in rings)
                if item["bevel_applied"]:
                    bevel_cut_count += 1
            unique_floor_values = sorted({round(float(value), 9) for value in floor_values})
            same_floor = len(unique_floor_values) == 1
            stats = {
                "cap_triangle_count": int(layered_stats.get("cap_triangle_count") or 0),
                "floor_triangle_count": int(layered_stats.get("cap_triangle_count") or 0),
                "inner_wall_face_count": int(layered_stats.get("side_wall_face_count") or 0),
                "bevel_face_count": 0,
                "bore_wall_face_count": 0,
                "shoulder_face_count": 0,
                "chamfer_face_count": 0,
                "rim_bevel_face_count": 0,
                "bevel_applied": bevel_cut_count > 0,
                "bevel_cut_count": bevel_cut_count,
                "ring_count": ring_count,
                "radial_section_count": sections,
                "open_side": "positive" if open_side_ref >= 0 else "negative",
                "floor_axial_values_cm": [float(value) for value in unique_floor_values],
                "mixed_floor_depths": not same_floor,
                "overlapping_profile_cut_caps": bool(overlapping_caps),
                "box_clipped_profile_cut_caps": bool(
                    any(bool(item.get("clipped_by_box")) for item in prepared)
                ),
                "box_clipped_profile_bevel_caps": bool(
                    any(bool(item.get("bevel_clipped_by_box")) for item in prepared)
                ),
                "layered_profile_cut_mesh": True,
                "layered_cell_profile_cut_mesh": True,
                "cut_count": len(prepared),
                "extruded_cut_count": extruded_cut_count,
                "revolved_cut_count": revolved_cut_count,
                "profile_vertex_count": profile_vertex_count,
                "result_face_count": len(mesh.faces),
                "result_watertight": bool(mesh.is_watertight),
                **layered_stats,
            }
            if same_floor:
                stats["floor_axial_cm"] = float(unique_floor_values[0])
            if radii:
                stats["min_radius_cm"] = float(min(radii))
                stats["max_radius_cm"] = float(max(radii))
            return mesh, stats

        sampled_cells = _mesh_from_box_sampled_layered_blind_profile_cut_cells(
            box_min=box_min,
            box_max=box_max,
            cut_axis=cut_axis,
            plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
            rect=rect,
            prepared=prepared,
            open_side=open_side_ref,
            sections=sections,
        )
        if sampled_cells is not None:
            mesh, sampled_stats = sampled_cells
            for item in prepared:
                if item["cut_kind"] == "extruded_blind":
                    profile_vertex_count += max(0, len(list(item["cutter"].exterior.coords)) - 1)
                    if bool(item.get("bevel_ring")):
                        bevel_cut_count += 1
                    continue
                rings = item["rings"]
                ring_count += len(rings)
                radii.extend(float(radius) for _, radius in rings)
                if item["bevel_applied"]:
                    bevel_cut_count += 1
            unique_floor_values = sorted({round(float(value), 9) for value in floor_values})
            same_floor = len(unique_floor_values) == 1
            stats = {
                "cap_triangle_count": int(sampled_stats.get("cap_triangle_count") or 0),
                "floor_triangle_count": int(sampled_stats.get("cap_triangle_count") or 0),
                "inner_wall_face_count": int(sampled_stats.get("side_wall_face_count") or 0),
                "bevel_face_count": 0,
                "bore_wall_face_count": 0,
                "shoulder_face_count": 0,
                "chamfer_face_count": 0,
                "rim_bevel_face_count": 0,
                "bevel_applied": bevel_cut_count > 0,
                "bevel_cut_count": bevel_cut_count,
                "ring_count": ring_count,
                "radial_section_count": sections,
                "open_side": "positive" if open_side_ref >= 0 else "negative",
                "floor_axial_values_cm": [float(value) for value in unique_floor_values],
                "mixed_floor_depths": not same_floor,
                "overlapping_profile_cut_caps": bool(overlapping_caps),
                "box_clipped_profile_cut_caps": bool(
                    any(bool(item.get("clipped_by_box")) for item in prepared)
                ),
                "box_clipped_profile_bevel_caps": bool(
                    any(bool(item.get("bevel_clipped_by_box")) for item in prepared)
                ),
                "layered_profile_cut_mesh": True,
                "layered_cell_profile_cut_mesh": False,
                "cut_count": len(prepared),
                "extruded_cut_count": extruded_cut_count,
                "revolved_cut_count": revolved_cut_count,
                "profile_vertex_count": profile_vertex_count,
                "result_face_count": len(mesh.faces),
                "result_watertight": bool(mesh.is_watertight),
                **sampled_stats,
            }
            if same_floor:
                stats["floor_axial_cm"] = float(unique_floor_values[0])
            if radii:
                stats["min_radius_cm"] = float(min(radii))
                stats["max_radius_cm"] = float(max(radii))
            return mesh, stats

        floor_levels = sorted({float(value) for value in floor_values})

        def active_cut_union(axial: float) -> Any | None:
            active = []
            for item in prepared:
                floor_axial = float(item["floor_axial"])
                if (
                    (open_side_ref >= 0 and axial >= floor_axial - 1e-9)
                    or (open_side_ref < 0 and axial <= floor_axial + 1e-9)
                ):
                    cutter = item.get("cap_cutter") if item["cut_kind"] != "extruded_blind" else item.get("cap_cutter")
                    if cutter is not None and not cutter.is_empty:
                        active.append(cutter)
            if not active:
                return None
            union = unary_union(active)
            if union.is_empty:
                return None
            return union

        def add_boundary_walls(polygon: Any, *, wall_low: float, wall_high: float) -> int:
            face_count = 0
            geoms = list(getattr(polygon, "geoms", ()) or ())
            if geoms:
                for geom in geoms:
                    face_count += add_boundary_walls(geom, wall_low=wall_low, wall_high=wall_high)
                return face_count
            exterior = [(float(x), float(y)) for x, y in list(polygon.exterior.coords)]
            for index in range(len(exterior) - 1):
                add_wall(exterior[index], exterior[index + 1], wall_low=wall_low, wall_high=wall_high, reverse=True)
                face_count += 2
            for interior in polygon.interiors:
                ring = [(float(x), float(y)) for x, y in list(interior.coords)]
                for index in range(len(ring) - 1):
                    add_wall(ring[index], ring[index + 1], wall_low=wall_low, wall_high=wall_high, reverse=False)
                    face_count += 2
            return face_count

        boundary_levels = sorted({low, high, *floor_levels})
        for left, right in zip(boundary_levels, boundary_levels[1:], strict=False):
            if right <= left + 1e-9:
                continue
            mid = (left + right) * 0.5
            active = active_cut_union(mid)
            if active is None:
                continue
            inner_wall_face_count += add_boundary_walls(active, wall_low=left, wall_high=right)

        probe_epsilon = max((high - low) * 1e-7, 1e-7)
        for floor_axial in floor_levels:
            towards_open = active_cut_union(floor_axial + open_side_ref * probe_epsilon)
            towards_closed = active_cut_union(floor_axial - open_side_ref * probe_epsilon)
            if towards_open is None:
                continue
            floor_region = (
                towards_open
                if towards_closed is None
                else towards_open.difference(towards_closed)
            )
            if floor_region.is_empty or float(floor_region.area) <= 1e-9:
                continue
            floor_triangle_count += add_polygon_cap(
                floor_region,
                floor_axial,
                reverse=floor_reverse,
            )

        for item in prepared:
            if item["cut_kind"] == "extruded_blind":
                profile_vertex_count += max(0, len(list(item["cutter"].exterior.coords)) - 1)
                if bool(item.get("bevel_ring")):
                    bevel_cut_count += 1
                continue
            rings = item["rings"]
            ring_count += len(rings)
            radii.extend(float(radius) for _, radius in rings)
            if item["bevel_applied"]:
                bevel_cut_count += 1

        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        mesh.remove_unreferenced_vertices()
        mesh.merge_vertices()
        mesh.fix_normals()
        if not bool(mesh.is_watertight):
            return None
        unique_floor_values = sorted({round(float(value), 9) for value in floor_values})
        same_floor = len(unique_floor_values) == 1
        stats = {
            "cap_triangle_count": cap_triangle_count,
            "floor_triangle_count": floor_triangle_count,
            "inner_wall_face_count": inner_wall_face_count,
            "bevel_face_count": 0,
            "bore_wall_face_count": 0,
            "shoulder_face_count": 0,
            "chamfer_face_count": 0,
            "rim_bevel_face_count": 0,
            "bevel_applied": bevel_cut_count > 0,
            "bevel_cut_count": bevel_cut_count,
            "ring_count": ring_count,
            "radial_section_count": sections,
            "open_side": "positive" if open_side_ref >= 0 else "negative",
            "floor_axial_values_cm": [float(value) for value in unique_floor_values],
            "mixed_floor_depths": not same_floor,
            "overlapping_profile_cut_caps": True,
            "layered_profile_cut_mesh": True,
            "cut_count": len(prepared),
            "extruded_cut_count": extruded_cut_count,
            "revolved_cut_count": revolved_cut_count,
            "result_face_count": len(mesh.faces),
            "result_watertight": bool(mesh.is_watertight),
        }
        if same_floor:
            stats["floor_axial_cm"] = float(unique_floor_values[0])
        if radii:
            stats["min_radius_cm"] = float(min(radii))
            stats["max_radius_cm"] = float(max(radii))
        return mesh, stats

    def add_quad_points(
        points: tuple[
            tuple[tuple[float, float], float],
            tuple[tuple[float, float], float],
            tuple[tuple[float, float], float],
            tuple[tuple[float, float], float],
        ],
        *,
        reverse: bool,
    ) -> None:
        quad = [add_vertex(point, axial) for point, axial in points]
        faces.append([quad[0], quad[1], quad[2]] if not reverse else [quad[0], quad[2], quad[1]])
        faces.append([quad[0], quad[2], quad[3]] if not reverse else [quad[0], quad[3], quad[2]])

    for item in prepared:
        if item["cut_kind"] == "extruded_blind":
            cutter = item["cutter"]
            cutter_ring = [(float(x), float(y)) for x, y in list(cutter.exterior.coords)]
            profile_points = item["profile_points"]
            profile_vertex_count += max(0, len(cutter_ring) - 1)
            for triangle in triangulate(cutter):
                if float(triangle.area) <= 1e-9 or not cutter.covers(triangle.representative_point()):
                    continue
                coords = [(float(x), float(y)) for x, y in list(triangle.exterior.coords)[:3]]
                add_triangle(coords, float(item["floor_axial"]), reverse=floor_reverse)
                floor_triangle_count += 1
            bevel_width = float(item["bevel_width"])
            bevel_depth = min(bevel_width, max(abs(open_axial - float(item["floor_axial"])) * 0.45, 0.0))
            inner_axial = (
                open_axial - bevel_depth
                if open_side_ref >= 0 and item["bevel_ring"]
                else open_axial + bevel_depth
                if item["bevel_ring"]
                else open_axial
            )
            if item["bevel_ring"] and len(item["expanded_points"]) == len(profile_points):
                expanded_points = item["expanded_points"]
                for index in range(len(profile_points)):
                    next_index = (index + 1) % len(profile_points)
                    outer_a = expanded_points[index]
                    outer_b = expanded_points[next_index]
                    inner_a = profile_points[index]
                    inner_b = profile_points[next_index]
                    if open_side_ref >= 0:
                        add_quad_points(
                            (
                                (inner_a, inner_axial),
                                (inner_b, inner_axial),
                                (outer_b, open_axial),
                                (outer_a, open_axial),
                            ),
                            reverse=False,
                        )
                    else:
                        add_quad_points(
                            (
                                (outer_a, open_axial),
                                (outer_b, open_axial),
                                (inner_b, inner_axial),
                                (inner_a, inner_axial),
                            ),
                            reverse=True,
                        )
                    bevel_face_count += 2
                bevel_cut_count += 1
            wall_low = min(float(item["floor_axial"]), inner_axial)
            wall_high = max(float(item["floor_axial"]), inner_axial)
            if wall_high > wall_low + 1e-9:
                for index in range(len(cutter_ring) - 1):
                    add_wall(
                        cutter_ring[index],
                        cutter_ring[index + 1],
                        wall_low=wall_low,
                        wall_high=wall_high,
                        reverse=True,
                    )
                    inner_wall_face_count += 2
            continue

        rings = item["rings"]
        ring_count += len(rings)
        radii.extend(float(radius) for _, radius in rings)
        floor_circle = Polygon(
            _circle_points(item["plane_center"], float(item["floor_radius"]), sections=sections)
        )
        for triangle in triangulate(floor_circle):
            if float(triangle.area) <= 1e-9 or not floor_circle.covers(triangle.representative_point()):
                continue
            coords = [(float(x), float(y)) for x, y in list(triangle.exterior.coords)[:3]]
            add_triangle(coords, float(item["floor_axial"]), reverse=floor_reverse)
            floor_triangle_count += 1
        ring_points = [
            _circle_points(item["plane_center"], radius, sections=sections)
            for _, radius in rings
        ]
        bevel_segment_index = (len(rings) - 2) if open_side_ref >= 0 else 0
        if item["bevel_applied"]:
            bevel_cut_count += 1
        for ring_index in range(len(rings) - 1):
            left_axial, left_radius = rings[ring_index]
            right_axial, right_radius = rings[ring_index + 1]
            left_ring = ring_points[ring_index]
            right_ring = ring_points[ring_index + 1]
            if abs(left_axial - right_axial) <= 1e-9 and abs(left_radius - right_radius) <= 1e-9:
                continue
            for section_index in range(sections):
                next_index = (section_index + 1) % sections
                quad = [
                    add_vertex(left_ring[section_index], left_axial),
                    add_vertex(left_ring[next_index], left_axial),
                    add_vertex(right_ring[next_index], right_axial),
                    add_vertex(right_ring[section_index], right_axial),
                ]
                faces.append([quad[0], quad[2], quad[1]])
                faces.append([quad[0], quad[3], quad[2]])
                if abs(left_axial - right_axial) <= 1e-9:
                    shoulder_face_count += 2
                elif abs(left_radius - right_radius) > 1e-9:
                    chamfer_face_count += 2
                    if item["bevel_applied"] and ring_index == bevel_segment_index:
                        rim_bevel_face_count += 2
                else:
                    bore_face_count += 2

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()
    mesh.fix_normals()
    unique_floor_values = sorted(
        {
            round(float(value), 9)
            for value in floor_values
        }
    )
    same_floor = len(unique_floor_values) == 1
    stats: dict[str, Any] = {
        "cap_triangle_count": cap_triangle_count,
        "floor_triangle_count": floor_triangle_count,
        "inner_wall_face_count": inner_wall_face_count,
        "bevel_face_count": bevel_face_count + rim_bevel_face_count,
        "bore_wall_face_count": bore_face_count,
        "shoulder_face_count": shoulder_face_count,
        "chamfer_face_count": chamfer_face_count,
        "rim_bevel_face_count": rim_bevel_face_count,
        "bevel_applied": bevel_cut_count > 0,
        "bevel_cut_count": bevel_cut_count,
        "ring_count": ring_count,
        "radial_section_count": sections,
        "open_side": "positive" if open_side_ref >= 0 else "negative",
        "floor_axial_values_cm": [float(value) for value in unique_floor_values],
        "mixed_floor_depths": not same_floor,
        "cut_count": len(prepared),
        "extruded_cut_count": extruded_cut_count,
        "revolved_cut_count": revolved_cut_count,
        "result_face_count": len(mesh.faces),
        "result_watertight": bool(mesh.is_watertight),
    }
    if same_floor:
        stats["floor_axial_cm"] = float(unique_floor_values[0])
    if radii:
        stats["min_radius_cm"] = float(min(radii))
        stats["max_radius_cm"] = float(max(radii))
    return mesh, stats


_BLIND_PROFILE_CUT_KINDS = frozenset(
    {"extruded_blind", "revolved_blind", "cylinder_blind"}
)
_THROUGH_PROFILE_CUT_KINDS = frozenset({"extruded", "revolved"})


def _existing_blind_profile_cuts_from_state(
    state: dict[str, Any],
    *,
    cut_axis: int,
    plane_axes: tuple[int, int],
) -> list[dict[str, Any]] | None:
    previous_kind = str(state.get("cut_kind") or "")
    if previous_kind not in {*_BLIND_PROFILE_CUT_KINDS, "mixed_blind"}:
        return None
    if int(state.get("cut_axis", -1)) != int(cut_axis):
        return None
    previous_plane_axes = [int(value) for value in state.get("plane_axes", [])]
    if previous_plane_axes != [int(axis) for axis in plane_axes]:
        return None
    cuts = [dict(cut) for cut in state.get("cuts", []) if isinstance(cut, dict)]
    if len(cuts) != len(state.get("cuts", [])):
        return None
    normalized: list[dict[str, Any]] = []
    for cut in cuts:
        cut_kind = str(cut.get("cut_kind") or previous_kind)
        if cut_kind not in _BLIND_PROFILE_CUT_KINDS:
            return None
        normalized.append({**cut, "cut_kind": cut_kind})
    return normalized


def _blind_cut_state_kind(cuts: list[dict[str, Any]]) -> str:
    kinds = {str(cut.get("cut_kind") or "") for cut in cuts}
    return next(iter(kinds)) if len(kinds) == 1 else "mixed_blind"


def _profile_cut_state_kind_from_records(cuts: list[dict[str, Any]]) -> str:
    kinds = {str(cut.get("cut_kind") or "") for cut in cuts}
    if kinds and kinds.issubset(_BLIND_PROFILE_CUT_KINDS):
        return _blind_cut_state_kind(cuts)
    if kinds and kinds.issubset(_THROUGH_PROFILE_CUT_KINDS):
        return next(iter(kinds)) if len(kinds) == 1 else "mixed"
    return "mixed_depth_profile"


def _profile_cut_records_touch_plane_boundary(
    cuts: list[dict[str, Any]],
    *,
    box_min: np.ndarray,
    box_max: np.ndarray,
    plane_axes: tuple[int, int],
) -> bool:
    box_plane_min = box_min[list(plane_axes)]
    box_plane_max = box_max[list(plane_axes)]
    for cut in cuts:
        cut_kind = str(cut.get("cut_kind") or "")
        if cut_kind == "extruded":
            try:
                points = np.asarray(
                    [
                        (float(point[0]), float(point[1]))
                        for point in cut["profile_points"]
                    ],
                    dtype=np.float64,
                )
            except (KeyError, TypeError, ValueError, IndexError):
                continue
            if points.ndim != 2 or points.shape[1] != 2 or len(points) < 3:
                continue
            plane_min = points.min(axis=0)
            plane_max = points.max(axis=0)
        elif cut_kind in {"revolved", "cylinder"}:
            try:
                center = np.asarray(cut["center"], dtype=np.float64)
                max_radius = max(float(ring[1]) for ring in cut["rings"])
            except (KeyError, TypeError, ValueError, IndexError):
                continue
            if center.shape != (3,) or max_radius <= 0.0:
                continue
            plane_center = center[list(plane_axes)]
            plane_min = plane_center - max_radius
            plane_max = plane_center + max_radius
        else:
            continue
        if bool(np.any(plane_min <= box_plane_min + 1e-7)) or bool(
            np.any(plane_max >= box_plane_max - 1e-7)
        ):
            return True
    return False


def _existing_profile_cut_records_from_state(
    state: dict[str, Any],
    *,
    cut_axis: int,
    plane_axes: tuple[int, int],
) -> list[dict[str, Any]] | None:
    previous_kind = str(state.get("cut_kind") or "")
    allowed_state_kinds = {
        *_BLIND_PROFILE_CUT_KINDS,
        *_THROUGH_PROFILE_CUT_KINDS,
        "mixed",
        "mixed_blind",
        "mixed_depth_profile",
    }
    if previous_kind not in allowed_state_kinds:
        return None
    if int(state.get("cut_axis", -1)) != int(cut_axis):
        return None
    previous_plane_axes = [int(value) for value in state.get("plane_axes", [])]
    if previous_plane_axes != [int(axis) for axis in plane_axes]:
        return None
    raw_cuts = state.get("cuts", [])
    if not isinstance(raw_cuts, list):
        return None
    normalized: list[dict[str, Any]] = []
    for raw_cut in raw_cuts:
        if not isinstance(raw_cut, dict):
            return None
        cut_kind = str(raw_cut.get("cut_kind") or previous_kind)
        if cut_kind not in {*_BLIND_PROFILE_CUT_KINDS, *_THROUGH_PROFILE_CUT_KINDS}:
            return None
        normalized.append({**raw_cut, "cut_kind": cut_kind})
    return normalized


def _backend_assisted_blind_profile_difference(
    a: trimesh.Trimesh,
    b: trimesh.Trimesh,
    *,
    box_min: np.ndarray,
    box_max: np.ndarray,
    cut_axis: int,
    plane_axes: tuple[int, int],
    cuts: list[dict[str, Any]],
    state_cut_kind: str,
    attempted_method: str,
) -> trimesh.Trimesh | None:
    try:
        result = trimesh.boolean.difference([a, b])
    except (ImportError, ValueError, RuntimeError, AttributeError, TypeError):
        return None
    if isinstance(result, list):
        if not result:
            return None
        result_mesh = trimesh.util.concatenate(result) if len(result) > 1 else result[0]
    else:
        result_mesh = result
    if not isinstance(result_mesh, trimesh.Trimesh) or len(result_mesh.faces) == 0:
        return None
    result_mesh.remove_unreferenced_vertices()
    result_mesh.merge_vertices()
    result_mesh.fix_normals()
    if not bool(result_mesh.is_watertight):
        return None
    _set_batch_source_meshes(result_mesh, (result_mesh,))
    normalized_cuts = [dict(cut) for cut in cuts]
    result_mesh.metadata[_PROFILE_CUT_STATE_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_profile_cut_state.v1",
        "box_min": [float(value) for value in box_min],
        "box_max": [float(value) for value in box_max],
        "cut_kind": str(state_cut_kind),
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "cuts": normalized_cuts,
    }
    bevel_applied = False
    bevel_widths: list[float] = []
    for cut in normalized_cuts:
        try:
            width = float(cut.get("bevel_width") or 0.0)
        except (TypeError, ValueError):
            width = 0.0
        if width > 1e-9:
            bevel_widths.append(width)
        if bool(cut.get("bevel_applied")) or width > 1e-9:
            bevel_applied = True
    result_mesh.metadata["lathe_reference_boolean_backend"] = {
        "schema": "lathe.geometry.reference_boolean_backend.v1",
        "method": "trimesh_boolean_backend_profile_cut_state_v1",
        "backend": "trimesh.boolean",
        "op": "difference",
        "attempted_backend": "lathe.reference.analytic_profile_cut",
        "actual_backend": "trimesh.boolean",
        "attempted_exact_method": str(attempted_method),
        "exact_kernel_path": False,
        "fallback": False,
        "passthrough": False,
        "profile_cut_state_preserved": True,
        "profile_cut_bevel_applied": bool(bevel_applied),
        "profile_cut_count": len(normalized_cuts),
        "profile_cut_kinds": sorted({str(cut.get("cut_kind") or state_cut_kind) for cut in normalized_cuts}),
        "bevel_cut_count": sum(1 for cut in normalized_cuts if bool(cut.get("bevel_applied"))),
        "bevel_width_values_cm": [float(value) for value in sorted(set(bevel_widths))],
        "source_has_profile_cut_state": _profile_cut_state_from_mesh(a) is not None,
        "cutter_has_profile_cut_state": _profile_cut_state_from_mesh(b) is not None,
        "source_has_boss_state": _boss_state_from_mesh(a) is not None,
        "cutter_has_boss_state": _boss_state_from_mesh(b) is not None,
        "result_face_count": len(result_mesh.faces),
        "result_watertight": bool(result_mesh.is_watertight),
    }
    return result_mesh


def _mesh_from_box_blind_cut_records(
    *,
    box_min: np.ndarray,
    box_max: np.ndarray,
    cut_axis: int,
    plane_axes: tuple[int, int],
    cuts: list[dict[str, Any]],
) -> tuple[trimesh.Trimesh, dict[str, Any]] | None:
    state_kind = _blind_cut_state_kind(cuts)
    if state_kind == "extruded_blind":
        built = _mesh_from_box_blind_profile_cuts(
            box_min=box_min,
            box_max=box_max,
            cut_axis=cut_axis,
            plane_axes=plane_axes,
            cuts=cuts,
        )
        if built is not None:
            return built
        return _mesh_from_box_blind_mixed_profile_cuts(
            box_min=box_min,
            box_max=box_max,
            cut_axis=cut_axis,
            plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
            cuts=cuts,
        )
    if state_kind in {"revolved_blind", "cylinder_blind"}:
        built = _mesh_from_box_blind_revolved_profile_cuts(
            box_min=box_min,
            box_max=box_max,
            cut_axis=cut_axis,
            plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
            cuts=cuts,
        )
        if built is not None:
            return built
        return _mesh_from_box_blind_mixed_profile_cuts(
            box_min=box_min,
            box_max=box_max,
            cut_axis=cut_axis,
            plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
            cuts=cuts,
        )
    return _mesh_from_box_blind_mixed_profile_cuts(
        box_min=box_min,
        box_max=box_max,
        cut_axis=cut_axis,
        plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
        cuts=cuts,
    )


def _mesh_from_box_revolved_profile_cuts(
    *,
    box_min: np.ndarray,
    box_max: np.ndarray,
    cut_axis: int,
    plane_axes: tuple[int, int],
    cuts: list[dict[str, Any]],
    sections: int = 48,
) -> tuple[trimesh.Trimesh, dict[str, Any]] | None:
    try:
        from shapely.geometry import LineString, Polygon
        from shapely.ops import triangulate, unary_union
    except (ImportError, ModuleNotFoundError):
        return None

    rect = Polygon(
        (
            (float(box_min[plane_axes[0]]), float(box_min[plane_axes[1]])),
            (float(box_max[plane_axes[0]]), float(box_min[plane_axes[1]])),
            (float(box_max[plane_axes[0]]), float(box_max[plane_axes[1]])),
            (float(box_min[plane_axes[0]]), float(box_max[plane_axes[1]])),
        )
    )

    prepared: list[dict[str, Any]] = []
    low_cap_cutters = []
    high_cap_cutters = []
    max_cutters = []
    low_cap_area_sum = 0.0
    high_cap_area_sum = 0.0
    max_area_sum = 0.0
    radius_clamp_count = 0
    requested_max_radii: list[float] = []
    actual_max_radii: list[float] = []

    def circle_polygon(plane_center: np.ndarray, radius: float) -> Any:
        cutter = Polygon(_circle_points(plane_center, radius, sections=sections))
        if not cutter.is_valid:
            cutter = cutter.buffer(0)
        return cutter

    for cut in cuts:
        try:
            center = np.asarray(cut["center"], dtype=np.float64)
            rings = [
                (float(ring[0]), float(ring[1]))
                for ring in cut["rings"]
            ]
        except (KeyError, TypeError, ValueError, IndexError):
            return None
        if center.shape != (3,) or len(rings) < 2:
            return None
        if any(radius <= 0.0 for _, radius in rings):
            return None
        plane_center = np.asarray(
            [center[plane_axes[0]], center[plane_axes[1]]],
            dtype=np.float64,
        )
        clamped = _clamp_revolved_rings_to_rect(rect, plane_center, rings)
        if clamped is None:
            return None
        rings, clamp_stats = clamped
        if clamp_stats:
            radius_clamp_count += 1
            requested_max_radii.append(float(clamp_stats["requested_max_radius_cm"]))
            actual_max_radii.append(float(clamp_stats["actual_max_radius_cm"]))
        low_cutter = circle_polygon(plane_center, rings[0][1])
        high_cutter = circle_polygon(plane_center, rings[-1][1])
        max_cutter = circle_polygon(plane_center, max(radius for _, radius in rings))
        if (
            low_cutter.is_empty
            or high_cutter.is_empty
            or max_cutter.is_empty
            or float(low_cutter.area) <= 1e-9
            or float(high_cutter.area) <= 1e-9
            or float(max_cutter.area) <= 1e-9
            or not rect.contains(max_cutter)
        ):
            return None
        low_cap_cutters.append(low_cutter)
        high_cap_cutters.append(high_cutter)
        max_cutters.append(max_cutter)
        low_cap_area_sum += float(low_cutter.area)
        high_cap_area_sum += float(high_cutter.area)
        max_area_sum += float(max_cutter.area)
        prepared.append(
            {
                "center": center,
                "plane_center": plane_center,
                "rings": rings,
            }
        )

    def checked_union(cutters: list[Any], area_sum: float) -> Any | None:
        union = unary_union(cutters)
        tolerance = max(1e-6, abs(area_sum) * 1e-7)
        if union.is_empty or abs(float(union.area) - area_sum) > tolerance:
            return None
        return union

    low_cap_union = checked_union(low_cap_cutters, low_cap_area_sum)
    high_cap_union = checked_union(high_cap_cutters, high_cap_area_sum)
    max_union = checked_union(max_cutters, max_area_sum)
    if low_cap_union is None or high_cap_union is None or max_union is None:
        return None

    low_remaining = rect.difference(low_cap_union)
    high_remaining = rect.difference(high_cap_union)
    if (
        low_remaining.is_empty
        or high_remaining.is_empty
        or float(low_remaining.area) <= 1e-9
        or float(high_remaining.area) <= 1e-9
    ):
        return None

    vertices: list[tuple[float, float, float]] = []
    vertex_index: dict[tuple[int, int, int], int] = {}
    faces: list[list[int]] = []

    def add_vertex(plane_point: tuple[float, float], axial: float) -> int:
        coord = [0.0, 0.0, 0.0]
        coord[cut_axis] = float(axial)
        coord[plane_axes[0]] = float(plane_point[0])
        coord[plane_axes[1]] = float(plane_point[1])
        key = tuple(int(round(value * 1_000_000)) for value in coord)
        existing = vertex_index.get(key)
        if existing is not None:
            return existing
        vertex_index[key] = len(vertices)
        vertices.append((coord[0], coord[1], coord[2]))
        return len(vertices) - 1

    def add_wall(
        a_point: tuple[float, float],
        b_point: tuple[float, float],
        *,
        low: float,
        high: float,
        reverse: bool,
    ) -> None:
        quad = [
            add_vertex(a_point, low),
            add_vertex(b_point, low),
            add_vertex(b_point, high),
            add_vertex(a_point, high),
        ]
        faces.append([quad[0], quad[1], quad[2]] if not reverse else [quad[0], quad[2], quad[1]])
        faces.append([quad[0], quad[2], quad[3]] if not reverse else [quad[0], quad[3], quad[2]])

    def add_cap(remaining: Any, axial: float, *, reverse: bool) -> int:
        count = 0
        for triangle in triangulate(remaining):
            if float(triangle.area) <= 1e-9 or not remaining.covers(triangle.representative_point()):
                continue
            coords = [(float(x), float(y)) for x, y in list(triangle.exterior.coords)[:3]]
            tri = [add_vertex(point, axial) for point in coords]
            faces.append([tri[0], tri[2], tri[1]] if reverse else tri)
            count += 1
        return count

    low = float(box_min[cut_axis])
    high = float(box_max[cut_axis])
    cap_triangle_count = add_cap(low_remaining, low, reverse=True)
    cap_triangle_count += add_cap(high_remaining, high, reverse=False)

    rect_ring = [(float(x), float(y)) for x, y in list(rect.exterior.coords)]
    for index in range(len(rect_ring) - 1):
        add_wall(rect_ring[index], rect_ring[index + 1], low=low, high=high, reverse=False)

    bore_face_count = 0
    shoulder_face_count = 0
    chamfer_face_count = 0
    ring_count = 0
    radii: list[float] = []
    for item in prepared:
        rings = item["rings"]
        ring_count += len(rings)
        radii.extend(float(radius) for _, radius in rings)
        ring_points = [
            _circle_points(item["plane_center"], radius, sections=sections)
            for _, radius in rings
        ]
        for ring_index in range(len(rings) - 1):
            left_axial, left_radius = rings[ring_index]
            right_axial, right_radius = rings[ring_index + 1]
            left_ring = ring_points[ring_index]
            right_ring = ring_points[ring_index + 1]
            if abs(left_axial - right_axial) <= 1e-9 and abs(left_radius - right_radius) <= 1e-9:
                continue
            segment_count = min(len(left_ring), len(right_ring))
            if segment_count < 3:
                return None
            for index in range(segment_count):
                next_index = (index + 1) % segment_count
                quad = [
                    add_vertex(left_ring[index], left_axial),
                    add_vertex(left_ring[next_index], left_axial),
                    add_vertex(right_ring[next_index], right_axial),
                    add_vertex(right_ring[index], right_axial),
                ]
                faces.append([quad[0], quad[2], quad[1]])
                faces.append([quad[0], quad[3], quad[2]])
                if abs(left_axial - right_axial) <= 1e-9:
                    shoulder_face_count += 2
                elif abs(left_radius - right_radius) > 1e-9:
                    chamfer_face_count += 2
                else:
                    bore_face_count += 2

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()
    mesh.fix_normals()
    stats: dict[str, Any] = {
        "cap_triangle_count": cap_triangle_count,
        "bore_wall_face_count": bore_face_count,
        "shoulder_face_count": shoulder_face_count,
        "chamfer_face_count": chamfer_face_count,
        "ring_count": ring_count,
        "radial_section_count": sections,
        "cut_count": len(prepared),
        "result_face_count": len(mesh.faces),
        "result_watertight": bool(mesh.is_watertight),
        "min_radius_cm": float(min(radii)),
        "max_radius_cm": float(max(radii)),
    }
    if radius_clamp_count:
        stats["profile_radius_clamped"] = True
        stats["profile_radius_clamp_count"] = int(radius_clamp_count)
        stats["requested_max_radius_cm"] = float(max(requested_max_radii))
        stats["actual_max_radius_cm"] = float(max(actual_max_radii))
    return mesh, stats


def _mesh_from_box_mixed_profile_cuts(
    *,
    box_min: np.ndarray,
    box_max: np.ndarray,
    cut_axis: int,
    plane_axes: tuple[int, int],
    cuts: list[dict[str, Any]],
    sections: int = 48,
) -> tuple[trimesh.Trimesh, dict[str, Any]] | None:
    try:
        from shapely.geometry import Polygon
        from shapely.ops import triangulate, unary_union
    except (ImportError, ModuleNotFoundError):
        return None

    rect = Polygon(
        (
            (float(box_min[plane_axes[0]]), float(box_min[plane_axes[1]])),
            (float(box_max[plane_axes[0]]), float(box_min[plane_axes[1]])),
            (float(box_max[plane_axes[0]]), float(box_max[plane_axes[1]])),
            (float(box_min[plane_axes[0]]), float(box_max[plane_axes[1]])),
        )
    )
    prepared: list[dict[str, Any]] = []
    low_cap_cutters = []
    high_cap_cutters = []
    max_cutters = []
    low_area_sum = 0.0
    high_area_sum = 0.0
    max_area_sum = 0.0
    radius_clamp_count = 0
    requested_max_radii: list[float] = []
    actual_max_radii: list[float] = []

    def polygon_area_checked(cutter: Any) -> Any | None:
        if not cutter.is_valid:
            cutter = cutter.buffer(0)
        if cutter.is_empty or float(cutter.area) <= 1e-9:
            return None
        return cutter

    for cut in cuts:
        cut_kind = str(cut.get("cut_kind") or "")
        if cut_kind == "extruded":
            try:
                profile_points = [
                    (float(point[0]), float(point[1]))
                    for point in cut["profile_points"]
                ]
            except (KeyError, TypeError, ValueError, IndexError):
                return None
            cutter = polygon_area_checked(Polygon(profile_points))
            if cutter is None or not rect.contains(cutter):
                return None
            bevel_width = max(0.0, float(cut.get("bevel_width") or 0.0))
            cap_cutter = cutter
            bevel_ring = False
            expanded_points: list[tuple[float, float]] = []
            if bevel_width > 1e-9:
                centroid = cutter.centroid
                cx = float(centroid.x)
                cy = float(centroid.y)
                for point_x, point_y in profile_points:
                    dx = float(point_x) - cx
                    dy = float(point_y) - cy
                    length = math.hypot(dx, dy)
                    if length <= 1e-9:
                        expanded_points.append((float(point_x), float(point_y)))
                    else:
                        scale = (length + bevel_width) / length
                        expanded_points.append((cx + dx * scale, cy + dy * scale))
                expanded = polygon_area_checked(Polygon(expanded_points))
                if expanded is not None and float(expanded.area) > float(cutter.area) and rect.contains(expanded):
                    cap_cutter = expanded
                    bevel_ring = True
            low_cap_cutters.append(cap_cutter)
            high_cap_cutters.append(cap_cutter)
            max_cutters.append(cap_cutter)
            low_area_sum += float(cap_cutter.area)
            high_area_sum += float(cap_cutter.area)
            max_area_sum += float(cap_cutter.area)
            prepared.append(
                {
                    "cut_kind": "extruded",
                    "profile_points": profile_points,
                    "cutter": cutter,
                    "expanded_points": expanded_points,
                    "bevel_width": bevel_width,
                    "bevel_ring": bevel_ring,
                }
            )
        elif cut_kind == "revolved":
            try:
                center = np.asarray(cut["center"], dtype=np.float64)
                rings = [
                    (float(ring[0]), float(ring[1]))
                    for ring in cut["rings"]
                ]
            except (KeyError, TypeError, ValueError, IndexError):
                return None
            if center.shape != (3,) or len(rings) < 2 or any(radius <= 0.0 for _, radius in rings):
                return None
            plane_center = np.asarray(
                [center[plane_axes[0]], center[plane_axes[1]]],
                dtype=np.float64,
            )
            clamped = _clamp_revolved_rings_to_rect(rect, plane_center, rings)
            if clamped is None:
                return None
            rings, clamp_stats = clamped
            if clamp_stats:
                radius_clamp_count += 1
                requested_max_radii.append(float(clamp_stats["requested_max_radius_cm"]))
                actual_max_radii.append(float(clamp_stats["actual_max_radius_cm"]))
            low_cutter = polygon_area_checked(Polygon(_circle_points(plane_center, rings[0][1], sections=sections)))
            high_cutter = polygon_area_checked(Polygon(_circle_points(plane_center, rings[-1][1], sections=sections)))
            max_cutter = polygon_area_checked(
                Polygon(_circle_points(plane_center, max(radius for _, radius in rings), sections=sections))
            )
            if (
                low_cutter is None
                or high_cutter is None
                or max_cutter is None
                or not rect.contains(max_cutter)
            ):
                return None
            low_cap_cutters.append(low_cutter)
            high_cap_cutters.append(high_cutter)
            max_cutters.append(max_cutter)
            low_area_sum += float(low_cutter.area)
            high_area_sum += float(high_cutter.area)
            max_area_sum += float(max_cutter.area)
            prepared.append(
                {
                    "cut_kind": "revolved",
                    "plane_center": plane_center,
                    "rings": rings,
                }
            )
        else:
            return None

    def checked_union(cutters: list[Any], area_sum: float) -> Any | None:
        union = unary_union(cutters)
        tolerance = max(1e-6, abs(area_sum) * 1e-7)
        if union.is_empty or abs(float(union.area) - area_sum) > tolerance:
            return None
        return union

    low_union = checked_union(low_cap_cutters, low_area_sum)
    high_union = checked_union(high_cap_cutters, high_area_sum)
    max_union = checked_union(max_cutters, max_area_sum)
    if low_union is None or high_union is None or max_union is None:
        merged_cutters = unary_union(max_cutters)
        if merged_cutters.is_empty:
            return None
        remaining = rect.difference(merged_cutters)
        if remaining.is_empty or float(remaining.area) <= 1e-9:
            return None
        built = _mesh_from_axis_extruded_polygon_union(
            [{"polygon": remaining, "low": float(box_min[cut_axis]), "high": float(box_max[cut_axis])}],
            axis=cut_axis,
            plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
        )
        if built is None:
            return None
        mesh, stats = built
        extruded_count = sum(1 for item in prepared if item["cut_kind"] == "extruded")
        revolved_count = sum(1 for item in prepared if item["cut_kind"] == "revolved")
        bevel_dropped_count = sum(
            1
            for item in prepared
            if item["cut_kind"] == "extruded" and bool(item.get("bevel_ring"))
        )
        detail_dropped_count = int(bevel_dropped_count + revolved_count)
        return mesh, {
            **stats,
            "cap_triangle_count": int(stats.get("cap_triangle_count") or 0),
            "inner_wall_face_count": int(stats.get("side_wall_face_count") or 0),
            "bevel_face_count": 0,
            "bore_wall_face_count": 0,
            "shoulder_face_count": 0,
            "chamfer_face_count": 0,
            "ring_count": 0,
            "radial_section_count": int(sections),
            "cut_count": len(prepared),
            "extruded_cut_count": int(extruded_count),
            "revolved_cut_count": int(revolved_count),
            "mixed_profile_cut_union": True,
            "overlapping_mixed_profile_cut_caps": True,
            "mixed_profile_cut_detail_dropped_count": detail_dropped_count,
            "overlapping_profile_cut_bevel_dropped_count": int(bevel_dropped_count),
            "result_face_count": len(mesh.faces),
            "result_watertight": bool(mesh.is_watertight),
        }
    low_remaining = rect.difference(low_union)
    high_remaining = rect.difference(high_union)
    if (
        low_remaining.is_empty
        or high_remaining.is_empty
        or float(low_remaining.area) <= 1e-9
        or float(high_remaining.area) <= 1e-9
    ):
        return None

    vertices: list[tuple[float, float, float]] = []
    vertex_index: dict[tuple[int, int, int], int] = {}
    faces: list[list[int]] = []

    def add_vertex(plane_point: tuple[float, float], axial: float) -> int:
        coord = [0.0, 0.0, 0.0]
        coord[cut_axis] = float(axial)
        coord[plane_axes[0]] = float(plane_point[0])
        coord[plane_axes[1]] = float(plane_point[1])
        key = tuple(int(round(value * 1_000_000)) for value in coord)
        existing = vertex_index.get(key)
        if existing is not None:
            return existing
        vertex_index[key] = len(vertices)
        vertices.append((coord[0], coord[1], coord[2]))
        return len(vertices) - 1

    def add_wall(
        a_point: tuple[float, float],
        b_point: tuple[float, float],
        *,
        reverse: bool,
        low: float | None = None,
        high: float | None = None,
    ) -> None:
        low = float(box_min[cut_axis]) if low is None else float(low)
        high = float(box_max[cut_axis]) if high is None else float(high)
        quad = [
            add_vertex(a_point, low),
            add_vertex(b_point, low),
            add_vertex(b_point, high),
            add_vertex(a_point, high),
        ]
        faces.append([quad[0], quad[1], quad[2]] if not reverse else [quad[0], quad[2], quad[1]])
        faces.append([quad[0], quad[2], quad[3]] if not reverse else [quad[0], quad[3], quad[2]])

    def add_cap(remaining: Any, axial: float, *, reverse: bool) -> int:
        count = 0
        for triangle in triangulate(remaining):
            if float(triangle.area) <= 1e-9 or not remaining.covers(triangle.representative_point()):
                continue
            coords = [(float(x), float(y)) for x, y in list(triangle.exterior.coords)[:3]]
            tri = [add_vertex(point, axial) for point in coords]
            faces.append([tri[0], tri[2], tri[1]] if reverse else tri)
            count += 1
        return count

    low = float(box_min[cut_axis])
    high = float(box_max[cut_axis])
    cap_triangle_count = add_cap(low_remaining, low, reverse=True)
    cap_triangle_count += add_cap(high_remaining, high, reverse=False)

    rect_ring = [(float(x), float(y)) for x, y in list(rect.exterior.coords)]
    for index in range(len(rect_ring) - 1):
        add_wall(rect_ring[index], rect_ring[index + 1], reverse=False)

    inner_wall_face_count = 0
    bevel_face_count = 0
    bore_face_count = 0
    shoulder_face_count = 0
    chamfer_face_count = 0
    ring_count = 0
    radii: list[float] = []
    extruded_cut_count = 0
    revolved_cut_count = 0
    for item in prepared:
        if item["cut_kind"] == "extruded":
            extruded_cut_count += 1
            profile_points = item["profile_points"]
            cutter_ring = [(float(x), float(y)) for x, y in list(item["cutter"].exterior.coords)]
            if item["bevel_ring"] and len(item["expanded_points"]) == len(profile_points):
                bevel_width = float(item["bevel_width"])
                bevel_depth = min(bevel_width, max((high - low) * 0.45, 0.0))
                low_inner = low + bevel_depth
                high_inner = high - bevel_depth

                def add_quad_points(
                    points: tuple[
                        tuple[tuple[float, float], float],
                        tuple[tuple[float, float], float],
                        tuple[tuple[float, float], float],
                        tuple[tuple[float, float], float],
                    ],
                    *,
                    reverse: bool,
                ) -> None:
                    quad = [add_vertex(point, axial) for point, axial in points]
                    faces.append([quad[0], quad[1], quad[2]] if not reverse else [quad[0], quad[2], quad[1]])
                    faces.append([quad[0], quad[2], quad[3]] if not reverse else [quad[0], quad[3], quad[2]])

                expanded_points = item["expanded_points"]
                for point_index in range(len(profile_points)):
                    next_index = (point_index + 1) % len(profile_points)
                    outer_a = expanded_points[point_index]
                    outer_b = expanded_points[next_index]
                    inner_a = profile_points[point_index]
                    inner_b = profile_points[next_index]
                    add_quad_points(
                        (
                            (outer_a, low),
                            (outer_b, low),
                            (inner_b, low_inner),
                            (inner_a, low_inner),
                        ),
                        reverse=True,
                    )
                    add_quad_points(
                        (
                            (inner_a, high_inner),
                            (inner_b, high_inner),
                            (outer_b, high),
                            (outer_a, high),
                        ),
                        reverse=False,
                    )
                    bevel_face_count += 4
                if high_inner > low_inner + 1e-9:
                    for edge_index in range(len(cutter_ring) - 1):
                        add_wall(cutter_ring[edge_index], cutter_ring[edge_index + 1], reverse=True, low=low_inner, high=high_inner)
                        inner_wall_face_count += 2
            else:
                for edge_index in range(len(cutter_ring) - 1):
                    add_wall(cutter_ring[edge_index], cutter_ring[edge_index + 1], reverse=True)
                    inner_wall_face_count += 2
        else:
            revolved_cut_count += 1
            rings = item["rings"]
            ring_count += len(rings)
            radii.extend(float(radius) for _, radius in rings)
            ring_points = [
                _circle_points(item["plane_center"], radius, sections=sections)
                for _, radius in rings
            ]
            for ring_index in range(len(rings) - 1):
                left_axial, left_radius = rings[ring_index]
                right_axial, right_radius = rings[ring_index + 1]
                left_ring = ring_points[ring_index]
                right_ring = ring_points[ring_index + 1]
                if abs(left_axial - right_axial) <= 1e-9 and abs(left_radius - right_radius) <= 1e-9:
                    continue
                for section_index in range(sections):
                    next_index = (section_index + 1) % sections
                    quad = [
                        add_vertex(left_ring[section_index], left_axial),
                        add_vertex(left_ring[next_index], left_axial),
                        add_vertex(right_ring[next_index], right_axial),
                        add_vertex(right_ring[section_index], right_axial),
                    ]
                    faces.append([quad[0], quad[2], quad[1]])
                    faces.append([quad[0], quad[3], quad[2]])
                    if abs(left_axial - right_axial) <= 1e-9:
                        shoulder_face_count += 2
                    elif abs(left_radius - right_radius) > 1e-9:
                        chamfer_face_count += 2
                    else:
                        bore_face_count += 2

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()
    mesh.fix_normals()
    stats: dict[str, Any] = {
        "cap_triangle_count": cap_triangle_count,
        "inner_wall_face_count": inner_wall_face_count,
        "bevel_face_count": bevel_face_count,
        "bore_wall_face_count": bore_face_count,
        "shoulder_face_count": shoulder_face_count,
        "chamfer_face_count": chamfer_face_count,
        "ring_count": ring_count,
        "radial_section_count": sections,
        "cut_count": len(prepared),
        "extruded_cut_count": extruded_cut_count,
        "revolved_cut_count": revolved_cut_count,
        "result_face_count": len(mesh.faces),
        "result_watertight": bool(mesh.is_watertight),
    }
    if radii:
        stats["min_radius_cm"] = float(min(radii))
        stats["max_radius_cm"] = float(max(radii))
    if radius_clamp_count:
        stats["profile_radius_clamped"] = True
        stats["profile_radius_clamp_count"] = int(radius_clamp_count)
        stats["requested_max_radius_cm"] = float(max(requested_max_radii))
        stats["actual_max_radius_cm"] = float(max(actual_max_radii))
    return mesh, stats


def _mesh_from_box_profile_cuts_with_open_extruded_boundaries(
    *,
    box_min: np.ndarray,
    box_max: np.ndarray,
    cut_axis: int,
    plane_axes: tuple[int, int],
    cuts: list[dict[str, Any]],
    sections: int = 48,
) -> tuple[trimesh.Trimesh, dict[str, Any]] | None:
    try:
        from shapely.geometry import Polygon
        from shapely.ops import triangulate, unary_union
    except (ImportError, ModuleNotFoundError):
        return None

    rect = Polygon(
        (
            (float(box_min[plane_axes[0]]), float(box_min[plane_axes[1]])),
            (float(box_max[plane_axes[0]]), float(box_min[plane_axes[1]])),
            (float(box_max[plane_axes[0]]), float(box_max[plane_axes[1]])),
            (float(box_min[plane_axes[0]]), float(box_max[plane_axes[1]])),
        )
    )
    prepared: list[dict[str, Any]] = []
    extruded_cutters = []
    low_cutters = []
    high_cutters = []
    max_cutters = []
    area_sum = 0.0
    low_area_sum = 0.0
    high_area_sum = 0.0
    extruded_bevel_request_count = 0
    extruded_bevel_expanded_open_boundary_count = 0
    extruded_bevel_dropped_count = 0

    def valid_polygon(geometry: Any) -> Any | None:
        if geometry.is_empty:
            return None
        if not geometry.is_valid:
            geometry = geometry.buffer(0)
        if geometry.is_empty or float(geometry.area) <= 1e-9:
            return None
        if geometry.geom_type != "Polygon":
            return None
        return geometry

    for cut in cuts:
        cut_kind = str(cut.get("cut_kind") or "")
        if cut_kind == "extruded":
            try:
                profile_points = [
                    (float(point[0]), float(point[1]))
                    for point in cut["profile_points"]
                ]
            except (KeyError, TypeError, ValueError, IndexError):
                return None
            cutter = valid_polygon(Polygon(profile_points))
            if cutter is None:
                return None
            clipped = valid_polygon(rect.intersection(cutter))
            if clipped is None:
                return None
            bevel_width = max(0.0, float(cut.get("bevel_width") or 0.0))
            cut_polygon = clipped
            if bevel_width > 1e-9:
                extruded_bevel_request_count += 1
                centroid = cutter.centroid
                cx = float(centroid.x)
                cy = float(centroid.y)
                expanded_points: list[tuple[float, float]] = []
                for point_x, point_y in profile_points:
                    dx = float(point_x) - cx
                    dy = float(point_y) - cy
                    length = math.hypot(dx, dy)
                    if length <= 1e-9:
                        expanded_points.append((float(point_x), float(point_y)))
                    else:
                        scale = (length + bevel_width) / length
                        expanded_points.append((cx + dx * scale, cy + dy * scale))
                expanded = valid_polygon(Polygon(expanded_points))
                expanded_clipped = valid_polygon(rect.intersection(expanded)) if expanded is not None else None
                if (
                    expanded_clipped is not None
                    and float(expanded_clipped.area) > float(clipped.area) + 1e-9
                ):
                    cut_polygon = expanded_clipped
                    extruded_bevel_expanded_open_boundary_count += 1
                else:
                    extruded_bevel_dropped_count += 1
            extruded_cutters.append(cut_polygon)
            low_cutters.append(cut_polygon)
            high_cutters.append(cut_polygon)
            max_cutters.append(cut_polygon)
            area = float(cut_polygon.area)
            area_sum += area
            low_area_sum += area
            high_area_sum += area
            prepared.append({"cut_kind": "extruded", "cutter": cut_polygon})
        elif cut_kind == "revolved":
            try:
                center = np.asarray(cut["center"], dtype=np.float64)
                rings = [
                    (float(ring[0]), float(ring[1]))
                    for ring in cut["rings"]
                ]
            except (KeyError, TypeError, ValueError, IndexError):
                return None
            if center.shape != (3,) or len(rings) < 2 or any(radius <= 0.0 for _, radius in rings):
                return None
            plane_center = np.asarray(
                [center[plane_axes[0]], center[plane_axes[1]]],
                dtype=np.float64,
            )
            low_cutter = valid_polygon(Polygon(_circle_points(plane_center, rings[0][1], sections=sections)))
            high_cutter = valid_polygon(Polygon(_circle_points(plane_center, rings[-1][1], sections=sections)))
            max_cutter = valid_polygon(
                Polygon(_circle_points(plane_center, max(radius for _, radius in rings), sections=sections))
            )
            if (
                low_cutter is None
                or high_cutter is None
                or max_cutter is None
                or not rect.contains(max_cutter)
            ):
                return None
            low_cutters.append(low_cutter)
            high_cutters.append(high_cutter)
            max_cutters.append(max_cutter)
            low_area_sum += float(low_cutter.area)
            high_area_sum += float(high_cutter.area)
            area_sum += float(max_cutter.area)
            prepared.append(
                {
                    "cut_kind": "revolved",
                    "plane_center": plane_center,
                    "rings": rings,
                }
            )
        else:
            return None

    def checked_union(cutters: list[Any], expected_area: float) -> Any | None:
        union = unary_union(cutters)
        tolerance = max(1e-6, abs(expected_area) * 1e-7)
        if union.is_empty or abs(float(union.area) - expected_area) > tolerance:
            return None
        return union

    low_union = checked_union(low_cutters, low_area_sum)
    high_union = checked_union(high_cutters, high_area_sum)
    max_union = checked_union(max_cutters, area_sum)
    if low_union is None or high_union is None or max_union is None:
        return None
    low_remaining = rect.difference(low_union)
    high_remaining = rect.difference(high_union)
    side_remaining = rect.difference(unary_union(extruded_cutters)) if extruded_cutters else rect
    if (
        low_remaining.is_empty
        or high_remaining.is_empty
        or side_remaining.is_empty
        or float(low_remaining.area) <= 1e-9
        or float(high_remaining.area) <= 1e-9
        or float(side_remaining.area) <= 1e-9
    ):
        return None

    vertices: list[tuple[float, float, float]] = []
    vertex_index: dict[tuple[int, int, int], int] = {}
    faces: list[list[int]] = []

    def add_vertex(plane_point: tuple[float, float], axial: float) -> int:
        coord = [0.0, 0.0, 0.0]
        coord[cut_axis] = float(axial)
        coord[plane_axes[0]] = float(plane_point[0])
        coord[plane_axes[1]] = float(plane_point[1])
        key = tuple(int(round(value * 1_000_000)) for value in coord)
        existing = vertex_index.get(key)
        if existing is not None:
            return existing
        vertex_index[key] = len(vertices)
        vertices.append((coord[0], coord[1], coord[2]))
        return len(vertices) - 1

    def add_wall(
        a_point: tuple[float, float],
        b_point: tuple[float, float],
        *,
        low: float,
        high: float,
        reverse: bool,
    ) -> None:
        quad = [
            add_vertex(a_point, low),
            add_vertex(b_point, low),
            add_vertex(b_point, high),
            add_vertex(a_point, high),
        ]
        faces.append([quad[0], quad[1], quad[2]] if not reverse else [quad[0], quad[2], quad[1]])
        faces.append([quad[0], quad[2], quad[3]] if not reverse else [quad[0], quad[3], quad[2]])

    def polygons(geometry: Any) -> list[Any]:
        if geometry.geom_type == "Polygon":
            return [geometry]
        if geometry.geom_type == "MultiPolygon":
            return list(geometry.geoms)
        return []

    def add_cap(remaining: Any, axial: float, *, reverse: bool) -> int:
        count = 0
        for polygon in polygons(remaining):
            for triangle in triangulate(polygon):
                if float(triangle.area) <= 1e-9 or not polygon.covers(triangle.representative_point()):
                    continue
                coords = [(float(x), float(y)) for x, y in list(triangle.exterior.coords)[:3]]
                tri = [add_vertex(point, axial) for point in coords]
                faces.append([tri[0], tri[2], tri[1]] if reverse else tri)
                count += 1
        return count

    low = float(box_min[cut_axis])
    high = float(box_max[cut_axis])
    cap_triangle_count = add_cap(low_remaining, low, reverse=True)
    cap_triangle_count += add_cap(high_remaining, high, reverse=False)

    boundary_wall_face_count = 0
    for polygon in polygons(side_remaining):
        exterior = [(float(x), float(y)) for x, y in list(polygon.exterior.coords)]
        for index in range(len(exterior) - 1):
            add_wall(exterior[index], exterior[index + 1], low=low, high=high, reverse=False)
            boundary_wall_face_count += 2
        for interior in polygon.interiors:
            ring = [(float(x), float(y)) for x, y in list(interior.coords)]
            for index in range(len(ring) - 1):
                add_wall(ring[index], ring[index + 1], low=low, high=high, reverse=True)
                boundary_wall_face_count += 2

    bore_face_count = 0
    shoulder_face_count = 0
    chamfer_face_count = 0
    ring_count = 0
    radii: list[float] = []
    revolved_cut_count = 0
    for item in prepared:
        if item["cut_kind"] != "revolved":
            continue
        revolved_cut_count += 1
        rings = item["rings"]
        ring_count += len(rings)
        radii.extend(float(radius) for _, radius in rings)
        ring_points = [
            _circle_points(item["plane_center"], radius, sections=sections)
            for _, radius in rings
        ]
        for ring_index in range(len(rings) - 1):
            left_axial, left_radius = rings[ring_index]
            right_axial, right_radius = rings[ring_index + 1]
            left_ring = ring_points[ring_index]
            right_ring = ring_points[ring_index + 1]
            if abs(left_axial - right_axial) <= 1e-9 and abs(left_radius - right_radius) <= 1e-9:
                continue
            for section_index in range(sections):
                next_index = (section_index + 1) % sections
                quad = [
                    add_vertex(left_ring[section_index], left_axial),
                    add_vertex(left_ring[next_index], left_axial),
                    add_vertex(right_ring[next_index], right_axial),
                    add_vertex(right_ring[section_index], right_axial),
                ]
                faces.append([quad[0], quad[2], quad[1]])
                faces.append([quad[0], quad[3], quad[2]])
                if abs(left_axial - right_axial) <= 1e-9:
                    shoulder_face_count += 2
                elif abs(left_radius - right_radius) > 1e-9:
                    chamfer_face_count += 2
                else:
                    bore_face_count += 2

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()
    mesh.fix_normals()
    stats: dict[str, Any] = {
        "cap_triangle_count": cap_triangle_count,
        "boundary_wall_face_count": boundary_wall_face_count,
        "bore_wall_face_count": bore_face_count,
        "shoulder_face_count": shoulder_face_count,
        "chamfer_face_count": chamfer_face_count,
        "ring_count": ring_count,
        "radial_section_count": sections,
        "cut_count": len(prepared),
        "extruded_cut_count": len(prepared) - revolved_cut_count,
        "revolved_cut_count": revolved_cut_count,
        "extruded_bevel_request_count": extruded_bevel_request_count,
        "extruded_bevel_expanded_open_boundary_count": extruded_bevel_expanded_open_boundary_count,
        "extruded_bevel_dropped_count": extruded_bevel_dropped_count,
        "result_face_count": len(mesh.faces),
        "result_watertight": bool(mesh.is_watertight),
    }
    if radii:
        stats["min_radius_cm"] = float(min(radii))
        stats["max_radius_cm"] = float(max(radii))
    return mesh, stats


def _exact_axis_aligned_box_revolved_profile_difference(
    a: trimesh.Trimesh,
    b: trimesh.Trimesh,
) -> trimesh.Trimesh | None:
    if _boss_state_from_mesh(a) is not None:
        return None
    a_bounds = _box_bounds_from_metadata(a)
    profile_metadata = _revolved_profile_metadata(b)
    if a_bounds is None or profile_metadata is None:
        return None
    amin, amax = a_bounds
    axis = str(profile_metadata["axis"])
    cut_axis = {"x": 0, "y": 1, "z": 2}[axis]
    plane_axes = tuple(index for index in range(3) if index != cut_axis)
    center = np.asarray(profile_metadata["center"], dtype=np.float64)
    rings = _clipped_revolved_profile_rings(
        center=center,
        profile=list(profile_metadata["profile_points"]),
        axis_index=cut_axis,
        low=float(amin[cut_axis]),
        high=float(amax[cut_axis]),
        bevel_width=float(profile_metadata.get("bevel_width_cm") or 0.0),
    )
    if rings is None:
        blind = _blind_revolved_profile_rings(
            center=center,
            profile=list(profile_metadata["profile_points"]),
            axis_index=cut_axis,
            low=float(amin[cut_axis]),
            high=float(amax[cut_axis]),
            bevel_width=float(profile_metadata.get("bevel_width_cm") or 0.0),
        )
        if blind is None:
            return None
        rings, open_side, floor_axial, bevel_applied = blind
        new_blind_cut = {
            "cut_kind": "revolved_blind",
            "center": [float(value) for value in center],
            "rings": [[float(axial), float(radius)] for axial, radius in rings],
            "style": str(profile_metadata.get("style") or ""),
            "cutter_part": str(profile_metadata.get("part") or ""),
            "open_side": "positive" if open_side > 0 else "negative",
            "floor_axial_cm": float(floor_axial),
            "bevel_applied": bool(bevel_applied),
            "bevel_width": float(profile_metadata.get("bevel_width_cm") or 0.0),
        }
        previous_state = _profile_cut_state_from_mesh(a)
        if previous_state is not None:
            previous_cuts = _existing_blind_profile_cuts_from_state(
                previous_state,
                cut_axis=cut_axis,
                plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
            )
            if previous_cuts is None:
                previous_cuts = _existing_profile_cut_records_from_state(
                    previous_state,
                    cut_axis=cut_axis,
                    plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
                )
            if previous_cuts is None:
                return None
            cuts = [*previous_cuts, new_blind_cut]
            state_cut_kind = _profile_cut_state_kind_from_records(cuts)
            if state_cut_kind == "mixed_depth_profile":
                built = _mesh_from_box_blind_profile_cuts_with_raised_details(
                    box_min=amin,
                    box_max=amax,
                    cut_axis=cut_axis,
                    plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
                    cuts=cuts,
                    details=[],
                )
                method = "axis_aligned_box_mixed_depth_profile_difference_v1"
            else:
                built = _mesh_from_box_blind_cut_records(
                    box_min=amin,
                    box_max=amax,
                    cut_axis=cut_axis,
                    plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
                    cuts=cuts,
                )
                method = (
                    "axis_aligned_box_repeated_blind_revolved_profile_difference_v1"
                    if state_cut_kind == "revolved_blind"
                    else "axis_aligned_box_mixed_blind_profile_difference_v1"
                )
        else:
            cuts = [new_blind_cut]
            state_cut_kind = "revolved_blind"
            built = _mesh_from_box_blind_revolved_profile_cut(
                box_min=amin,
                box_max=amax,
                cut_axis=cut_axis,
                plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
                center=center,
                rings=rings,
                open_side=open_side,
                bevel_applied=bevel_applied,
            )
            if built is None:
                built = _mesh_from_box_blind_cut_records(
                    box_min=amin,
                    box_max=amax,
                    cut_axis=cut_axis,
                    plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
                    cuts=cuts,
                )
            method = "axis_aligned_box_blind_revolved_profile_difference_v1"
        if built is None:
            backend_assisted = _backend_assisted_blind_profile_difference(
                a,
                b,
                box_min=amin,
                box_max=amax,
                cut_axis=cut_axis,
                plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
                cuts=cuts,
                state_cut_kind=state_cut_kind,
                attempted_method=method,
            )
            if backend_assisted is not None:
                return backend_assisted
            return None
        result, stats = built
        _set_batch_source_meshes(result, (result,))
        result.metadata[_PROFILE_CUT_STATE_METADATA_KEY] = {
            "schema": "lathe.geometry.reference_profile_cut_state.v1",
            "box_min": [float(value) for value in amin],
            "box_max": [float(value) for value in amax],
            "cut_kind": state_cut_kind,
            "cut_axis": int(cut_axis),
            "plane_axes": [int(axis) for axis in plane_axes],
            "cuts": cuts,
        }
        result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
            "schema": "lathe.geometry.reference_exact_boolean.v1",
            "method": method,
            "op": "difference",
            "overlap": True,
            "through_cut": False,
            "blind_cut": True,
            "passthrough": False,
            "cut_axis": int(cut_axis),
            "plane_axes": [int(axis) for axis in plane_axes],
            "cutter_part": str(profile_metadata.get("part") or ""),
            "profile_style": str(profile_metadata.get("style") or ""),
            "profile_styles": [str(profile_metadata.get("style") or "")],
            "profile_cut_count": len(cuts),
            "profile_cut_kinds": sorted({str(cut.get("cut_kind") or state_cut_kind) for cut in cuts}),
            "result_face_count": len(result.faces),
            "result_watertight": bool(result.is_watertight),
            **stats,
        }
        return result
    new_cut = {
        "cut_kind": "revolved",
        "center": [float(value) for value in center],
        "rings": [[float(axial), float(radius)] for axial, radius in rings],
        "style": str(profile_metadata.get("style") or ""),
        "cutter_part": str(profile_metadata.get("part") or ""),
    }
    state_cut_kind = "revolved"
    previous_state = _profile_cut_state_from_mesh(a)
    if previous_state is not None:
        previous_kind = str(previous_state.get("cut_kind") or "")
        if previous_kind not in {"extruded", "revolved", "mixed"}:
            return None
        if int(previous_state.get("cut_axis", -1)) != int(cut_axis):
            return None
        previous_plane_axes = [int(value) for value in previous_state.get("plane_axes", [])]
        if previous_plane_axes != [int(axis) for axis in plane_axes]:
            return None
        cuts = [
            dict(cut)
            for cut in previous_state.get("cuts", [])
            if isinstance(cut, dict)
        ]
        if previous_kind != "mixed":
            cuts = [
                {**cut, "cut_kind": str(cut.get("cut_kind") or previous_kind)}
                for cut in cuts
            ]
        elif any(str(cut.get("cut_kind") or "") not in {"extruded", "revolved"} for cut in cuts):
            return None
        cuts.append(new_cut)
        if previous_kind == "revolved":
            built = _mesh_from_box_revolved_profile_cuts(
                box_min=amin,
                box_max=amax,
                cut_axis=cut_axis,
                plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
                cuts=cuts,
            )
            method = "axis_aligned_box_repeated_through_revolved_profile_difference_v1"
        else:
            built = _mesh_from_box_mixed_profile_cuts(
                box_min=amin,
                box_max=amax,
                cut_axis=cut_axis,
                plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
                cuts=cuts,
            )
            if built is None:
                built = _mesh_from_box_blind_profile_cuts_with_raised_details(
                    box_min=amin,
                    box_max=amax,
                    cut_axis=cut_axis,
                    plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
                    cuts=cuts,
                    details=[],
                )
                if built is not None:
                    mesh, stats = built
                    built = (
                        mesh,
                        {
                            **stats,
                            "mixed_through_profile_cut_union": True,
                            "through_cut_count": len(cuts),
                            "blind_cut_count": 0,
                        },
                    )
            method = "axis_aligned_box_mixed_through_profile_difference_v1"
            state_cut_kind = "mixed"
    else:
        cuts = [new_cut]
        built = _mesh_from_box_revolved_profile_cut(
            box_min=amin,
            box_max=amax,
            cut_axis=cut_axis,
            plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
            center=center,
            rings=rings,
        )
        method = "axis_aligned_box_through_revolved_profile_difference_v1"
    if built is None:
        return None
    result, stats = built
    _set_batch_source_meshes(result, (result,))
    result.metadata[_PROFILE_CUT_STATE_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_profile_cut_state.v1",
        "box_min": [float(value) for value in amin],
        "box_max": [float(value) for value in amax],
        "cut_kind": state_cut_kind,
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "cuts": cuts,
    }
    result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_exact_boolean.v1",
        "method": method,
        "op": "difference",
        "overlap": True,
        "through_cut": True,
        "passthrough": False,
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "cutter_part": str(profile_metadata.get("part") or ""),
        "profile_style": str(profile_metadata.get("style") or ""),
        "profile_styles": sorted(
            {
                str(cut.get("style") or "")
                for cut in cuts
            }
        ),
        "profile_cut_count": len(cuts),
        "profile_cut_kinds": sorted(
            {
                str(cut.get("cut_kind") or state_cut_kind)
                for cut in cuts
            }
        ),
        "result_face_count": len(result.faces),
        "result_watertight": bool(result.is_watertight),
        **stats,
    }
    return result


def _exact_axis_aligned_box_cylinder_difference(
    a: trimesh.Trimesh,
    b: trimesh.Trimesh,
) -> trimesh.Trimesh | None:
    if _boss_state_from_mesh(a) is not None:
        return None
    a_bounds = _box_bounds_from_metadata(a)
    cylinder = _cylinder_metadata(b)
    if a_bounds is None or cylinder is None:
        return None
    amin, amax = a_bounds
    axis = str(cylinder["axis"])
    cut_axis = {"x": 0, "y": 1, "z": 2}[axis]
    plane_axes = tuple(index for index in range(3) if index != cut_axis)
    center = np.asarray(cylinder["center"], dtype=np.float64)
    radius = float(cylinder["radius"])
    half_height = float(cylinder["height"]) * 0.5
    cutter_low = float(center[cut_axis] - half_height)
    cutter_high = float(center[cut_axis] + half_height)
    through_cut = cutter_low <= float(amin[cut_axis]) + 1e-7 and cutter_high >= float(amax[cut_axis]) - 1e-7
    low = float(amin[cut_axis])
    high = float(amax[cut_axis])
    bevel_width = max(0.0, float(cylinder.get("bevel_width_cm") or 0.0))
    if not through_cut:
        if cutter_high >= high - 1e-7 and cutter_low > low + 1e-7:
            open_side = 1
            floor_axial = cutter_low
            bevel_depth = min(bevel_width, max((high - floor_axial) * 0.45, 0.0))
            rings = (
                [
                    (floor_axial, radius),
                    (high - bevel_depth, radius),
                    (high, radius + bevel_width),
                ]
                if bevel_width > 1e-9
                else [(floor_axial, radius), (high, radius)]
            )
        elif cutter_low <= low + 1e-7 and cutter_high < high - 1e-7:
            open_side = -1
            floor_axial = cutter_high
            bevel_depth = min(bevel_width, max((floor_axial - low) * 0.45, 0.0))
            rings = (
                [
                    (low, radius + bevel_width),
                    (low + bevel_depth, radius),
                    (floor_axial, radius),
                ]
                if bevel_width > 1e-9
                else [(low, radius), (floor_axial, radius)]
            )
        else:
            return None
        new_blind_cut = {
            "cut_kind": "cylinder_blind",
            "center": [float(value) for value in center],
            "rings": [[float(axial), float(ring_radius)] for axial, ring_radius in rings],
            "cutter_part": str(cylinder.get("part") or ""),
            "open_side": "positive" if open_side > 0 else "negative",
            "floor_axial_cm": float(floor_axial),
            "bevel_applied": bevel_width > 1e-9,
            "bevel_width": bevel_width,
        }
        previous_state = _profile_cut_state_from_mesh(a)
        if previous_state is not None:
            previous_cuts = _existing_blind_profile_cuts_from_state(
                previous_state,
                cut_axis=cut_axis,
                plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
            )
            if previous_cuts is None:
                return None
            cuts = [*previous_cuts, new_blind_cut]
            state_cut_kind = _blind_cut_state_kind(cuts)
            built = _mesh_from_box_blind_cut_records(
                box_min=amin,
                box_max=amax,
                cut_axis=cut_axis,
                plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
                cuts=cuts,
            )
            method = (
                "axis_aligned_box_repeated_blind_cylinder_difference_v1"
                if state_cut_kind == "cylinder_blind"
                else "axis_aligned_box_mixed_blind_profile_difference_v1"
            )
        else:
            cuts = [new_blind_cut]
            state_cut_kind = "cylinder_blind"
            built = _mesh_from_box_blind_revolved_profile_cut(
                box_min=amin,
                box_max=amax,
                cut_axis=cut_axis,
                plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
                center=center,
                rings=rings,
                open_side=open_side,
                bevel_applied=bevel_width > 1e-9,
            )
            if built is None:
                built = _mesh_from_box_blind_cut_records(
                    box_min=amin,
                    box_max=amax,
                    cut_axis=cut_axis,
                    plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
                    cuts=cuts,
                )
            method = "axis_aligned_box_blind_cylinder_difference_v1"
        if built is None:
            backend_assisted = _backend_assisted_blind_profile_difference(
                a,
                b,
                box_min=amin,
                box_max=amax,
                cut_axis=cut_axis,
                plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
                cuts=cuts,
                state_cut_kind=state_cut_kind,
                attempted_method=method,
            )
            if backend_assisted is not None:
                return backend_assisted
            return None
        result, stats = built
        _set_batch_source_meshes(result, (result,))
        result.metadata[_PROFILE_CUT_STATE_METADATA_KEY] = {
            "schema": "lathe.geometry.reference_profile_cut_state.v1",
            "box_min": [float(value) for value in amin],
            "box_max": [float(value) for value in amax],
            "cut_kind": state_cut_kind,
            "cut_axis": int(cut_axis),
            "plane_axes": [int(axis) for axis in plane_axes],
            "cuts": cuts,
        }
        result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
            "schema": "lathe.geometry.reference_exact_boolean.v1",
            "method": method,
            "op": "difference",
            "overlap": True,
            "through_cut": False,
            "blind_cut": True,
            "passthrough": False,
            "cut_axis": int(cut_axis),
            "plane_axes": [int(axis) for axis in plane_axes],
            "cutter_part": str(cylinder.get("part") or ""),
            "profile_cut_count": len(cuts),
            "profile_cut_kinds": sorted({str(cut.get("cut_kind") or state_cut_kind) for cut in cuts}),
            "result_face_count": len(result.faces),
            "result_watertight": bool(result.is_watertight),
            **stats,
        }
        return result
    if bevel_width > 1e-9:
        depth = max(0.0, high - low)
        bevel_depth = min(bevel_width, depth * 0.45)
        bevel_radius = radius + bevel_width
        rings = [
            (low, bevel_radius),
            (low + bevel_depth, radius),
            (high - bevel_depth, radius),
            (high, bevel_radius),
        ]
    else:
        rings = [
            (low, radius),
            (high, radius),
        ]
    new_cut = {
        "cut_kind": "revolved",
        "center": [float(value) for value in center],
        "rings": [[float(axial), float(value)] for axial, value in rings],
        "style": "beveled_cylinder" if bevel_width > 1e-9 else "cylinder",
        "cutter_part": str(cylinder.get("part") or "cylinder"),
    }
    state_cut_kind = "revolved"
    previous_state = _profile_cut_state_from_mesh(a)
    if previous_state is not None:
        previous_kind = str(previous_state.get("cut_kind") or "")
        if previous_kind not in {"extruded", "revolved", "mixed"}:
            return None
        if int(previous_state.get("cut_axis", -1)) != int(cut_axis):
            return None
        previous_plane_axes = [int(value) for value in previous_state.get("plane_axes", [])]
        if previous_plane_axes != [int(axis) for axis in plane_axes]:
            return None
        cuts = [
            dict(cut)
            for cut in previous_state.get("cuts", [])
            if isinstance(cut, dict)
        ]
        if previous_kind != "mixed":
            cuts = [
                {**cut, "cut_kind": str(cut.get("cut_kind") or previous_kind)}
                for cut in cuts
            ]
        elif any(str(cut.get("cut_kind") or "") not in {"extruded", "revolved"} for cut in cuts):
            return None
        cuts.append(new_cut)
        if previous_kind == "revolved":
            built = _mesh_from_box_revolved_profile_cuts(
                box_min=amin,
                box_max=amax,
                cut_axis=cut_axis,
                plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
                cuts=cuts,
            )
            method = "axis_aligned_box_repeated_through_cylinder_profile_difference_v1"
        else:
            built = _mesh_from_box_mixed_profile_cuts(
                box_min=amin,
                box_max=amax,
                cut_axis=cut_axis,
                plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
                cuts=cuts,
            )
            method = "axis_aligned_box_mixed_through_cylinder_profile_difference_v1"
            state_cut_kind = "mixed"
    else:
        cuts = [new_cut]
        built = _mesh_from_box_revolved_profile_cut(
            box_min=amin,
            box_max=amax,
            cut_axis=cut_axis,
            plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
            center=center,
            rings=rings,
        )
        method = "axis_aligned_box_through_cylinder_difference_v1"
    if built is None:
        return None
    result, stats = built
    _set_batch_source_meshes(result, (result,))
    result.metadata[_PROFILE_CUT_STATE_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_profile_cut_state.v1",
        "box_min": [float(value) for value in amin],
        "box_max": [float(value) for value in amax],
        "cut_kind": state_cut_kind,
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "cuts": cuts,
    }
    result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_exact_boolean.v1",
        "method": method,
        "op": "difference",
        "overlap": True,
        "through_cut": True,
        "passthrough": False,
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "cutter_part": str(cylinder.get("part") or "cylinder"),
        "profile_style": str(new_cut.get("style") or "cylinder"),
        "profile_styles": sorted({str(cut.get("style") or "") for cut in cuts}),
        "profile_cut_count": len(cuts),
        "profile_cut_kinds": sorted(
            {
                str(cut.get("cut_kind") or state_cut_kind)
                for cut in cuts
            }
        ),
        "result_face_count": len(result.faces),
        "result_watertight": bool(result.is_watertight),
        **stats,
        "bevel_width_cm": bevel_width,
        "bevel_face_count": int(stats.get("chamfer_face_count") or 0) if bevel_width > 1e-9 else 0,
        "bevel_applied": bevel_width > 1e-9,
    }
    return result


def _mesh_from_box_cylinder_bosses(
    *,
    box_min: np.ndarray,
    box_max: np.ndarray,
    cut_axis: int,
    plane_axes: tuple[int, int],
    side: int,
    bosses: list[dict[str, Any]],
    through_cuts: list[dict[str, Any]] | None = None,
    sections: int = 48,
) -> tuple[trimesh.Trimesh, dict[str, Any]] | None:
    try:
        from shapely.geometry import LineString, Polygon
        from shapely.ops import triangulate, unary_union
    except (ImportError, ModuleNotFoundError):
        return None

    if side not in {-1, 1} or cut_axis not in {0, 1, 2}:
        return None
    if len(plane_axes) != 2 or set(plane_axes) != ({0, 1, 2} - {cut_axis}):
        return None
    if not bosses:
        return None

    rect = Polygon(
        (
            (float(box_min[plane_axes[0]]), float(box_min[plane_axes[1]])),
            (float(box_max[plane_axes[0]]), float(box_min[plane_axes[1]])),
            (float(box_max[plane_axes[0]]), float(box_max[plane_axes[1]])),
            (float(box_min[plane_axes[0]]), float(box_max[plane_axes[1]])),
        )
    )
    if rect.is_empty or float(rect.area) <= 1e-9:
        return None

    def valid_footprint(geometry: Any) -> Any | None:
        try:
            if not geometry.is_valid:
                geometry = geometry.buffer(0)
        except GEOSException:
            return None
        if geometry.is_empty or float(geometry.area) <= 1e-9:
            return None
        return geometry

    def union_footprints(geometries: list[Any]) -> Any | None:
        try:
            return valid_footprint(unary_union(geometries))
        except GEOSException:
            return None

    prepared: list[dict[str, Any]] = []
    base_footprint_area_sum = 0.0
    max_footprint_area_sum = 0.0
    base_footprints: list[Any] = []
    max_footprints: list[Any] = []
    base_axial = float(box_max[cut_axis] if side > 0 else box_min[cut_axis])
    for boss in bosses:
        try:
            plane_center = np.asarray(boss["plane_center"], dtype=np.float64)
        except (KeyError, TypeError, ValueError):
            return None
        if plane_center.shape != (2,):
            return None
        try:
            rings = [
                (float(ring[0]), float(ring[1]))
                for ring in boss.get("rings", [])
            ]
        except (TypeError, ValueError, IndexError):
            return None
        if not rings:
            try:
                radius = float(boss["radius"])
                outer_axial = float(boss["outer_axial"])
            except (KeyError, TypeError, ValueError):
                return None
            boss_base_axial = float(boss.get("base_axial", base_axial))
            rings = [(boss_base_axial, radius), (outer_axial, radius)]
        if len(rings) < 2 or any(radius <= 0.0 for _, radius in rings):
            return None
        try:
            boss_base_axial = float(boss.get("base_axial", rings[0][0]))
        except (TypeError, ValueError):
            return None
        if abs(float(rings[0][0]) - boss_base_axial) > 1e-7:
            return None
        outer_axial = float(rings[-1][0])
        if side > 0 and (
            boss_base_axial < base_axial - 1e-7
            or outer_axial <= boss_base_axial + 1e-9
        ):
            return None
        if side < 0 and (
            boss_base_axial > base_axial + 1e-7
            or outer_axial >= boss_base_axial - 1e-9
        ):
            return None
        for (left_axial, _), (right_axial, _) in zip(rings, rings[1:], strict=False):
            if side > 0 and right_axial < left_axial - 1e-9:
                return None
            if side < 0 and right_axial > left_axial + 1e-9:
                return None

        base_radius = float(rings[0][1])
        outer_radius = float(rings[-1][1])
        max_radius = float(max(radius for _, radius in rings))
        constant_profile_points: list[tuple[float, float]] | None = None
        profile_ring_points: list[list[tuple[float, float]]] | None = None
        profile_holes: list[list[tuple[float, float]]] = []
        if "profile_points" in boss:
            try:
                constant_profile_points = [
                    (float(point[0]), float(point[1]))
                    for point in boss["profile_points"]
                ]
                profile_holes = [
                    [
                        (float(point[0]), float(point[1]))
                        for point in hole
                    ]
                    for hole in boss.get("profile_holes", [])
                ]
            except (TypeError, ValueError, IndexError):
                return None
            if len(constant_profile_points) < 3:
                return None
            if any(len(hole) < 3 for hole in profile_holes):
                return None
            if "profile_rings" in boss:
                try:
                    profile_ring_points = [
                        [
                            (float(point[0]), float(point[1]))
                            for point in ring
                        ]
                        for ring in boss["profile_rings"]
                    ]
                except (TypeError, ValueError, IndexError):
                    return None
                if len(profile_ring_points) != len(rings) or any(len(ring) < 3 for ring in profile_ring_points):
                    return None
                ring_footprints = [
                    valid_footprint(Polygon(ring, profile_holes))
                    for ring in profile_ring_points
                ]
                if any(footprint is None for footprint in ring_footprints):
                    return None
                base_footprint = ring_footprints[0]
                outer_footprint = ring_footprints[-1]
                max_footprint = union_footprints(ring_footprints)
                if max_footprint is None:
                    return None
            else:
                base_footprint = valid_footprint(Polygon(constant_profile_points, profile_holes))
                outer_footprint = valid_footprint(Polygon(constant_profile_points, profile_holes))
                max_footprint = valid_footprint(Polygon(constant_profile_points, profile_holes))
        else:
            base_footprint = valid_footprint(Polygon(_circle_points(plane_center, base_radius, sections=sections)))
            outer_footprint = valid_footprint(Polygon(_circle_points(plane_center, outer_radius, sections=sections)))
            max_footprint = valid_footprint(Polygon(_circle_points(plane_center, max_radius, sections=sections)))
        if (
            base_footprint is None
            or outer_footprint is None
            or max_footprint is None
            or not rect.covers(max_footprint)
        ):
            return None
        base_footprints.append(base_footprint)
        max_footprints.append(max_footprint)
        base_footprint_area_sum += float(base_footprint.area)
        max_footprint_area_sum += float(max_footprint.area)
        prepared.append(
            {
                "plane_center": plane_center,
                "radius": max_radius,
                "base_axial": boss_base_axial,
                "outer_axial": outer_axial,
                "rings": rings,
                "profile_points": constant_profile_points,
                "profile_rings": profile_ring_points,
                "profile_holes": profile_holes,
                "base_footprint": base_footprint,
                "outer_footprint": outer_footprint,
                "max_footprint": max_footprint,
            }
        )

    parent_by_boss: dict[int, int] = {}
    top_level_footprints: list[Any] = []
    top_level_area_sum = 0.0
    for index, boss in enumerate(prepared):
        boss_base_axial = float(boss["base_axial"])
        if abs(boss_base_axial - base_axial) <= 1e-7:
            top_level_footprints.append(boss["base_footprint"])
            top_level_area_sum += float(boss["base_footprint"].area)
            continue
        parents: list[int] = []
        for parent_index, parent in enumerate(prepared):
            if parent_index == index:
                continue
            parent_outer_axial = float(parent["outer_axial"])
            if abs(boss_base_axial - parent_outer_axial) > 1e-7:
                continue
            if parent["outer_footprint"].covers(boss["base_footprint"]):
                parents.append(parent_index)
        if len(parents) != 1:
            return None
        parent_by_boss[index] = parents[0]

    for left_index, left in enumerate(prepared):
        for right_index in range(left_index + 1, len(prepared)):
            right = prepared[right_index]
            intersection = left["max_footprint"].intersection(right["max_footprint"])
            if intersection.is_empty or float(intersection.area) <= 1e-9:
                continue
            nested = (
                parent_by_boss.get(left_index) == right_index
                or parent_by_boss.get(right_index) == left_index
            )
            if not nested:
                return None

    top_level_union = unary_union(top_level_footprints) if top_level_footprints else None
    top_level_tolerance = max(1e-6, abs(top_level_area_sum) * 1e-7)
    if (
        top_level_union is None
        or top_level_union.is_empty
        or abs(float(top_level_union.area) - top_level_area_sum) > top_level_tolerance
    ):
        return None
    prepared_holes: list[dict[str, Any]] = []
    hole_footprints: list[Any] = []
    hole_area_sum = 0.0

    def split_ring_points_at_boundaries(
        points: list[tuple[float, float]],
        boundaries: list[Any],
    ) -> list[tuple[float, float]]:
        if len(points) < 3 or not boundaries:
            return points

        def add_intersection_points(geometry: Any, out: list[tuple[float, float]]) -> None:
            geom_type = getattr(geometry, "geom_type", "")
            if geom_type == "Point":
                out.append((float(geometry.x), float(geometry.y)))
                return
            if geom_type == "MultiPoint":
                for point in geometry.geoms:
                    out.append((float(point.x), float(point.y)))
                return
            if geom_type in {"LineString", "LinearRing"}:
                coords = list(geometry.coords)
                if coords:
                    out.append((float(coords[0][0]), float(coords[0][1])))
                    out.append((float(coords[-1][0]), float(coords[-1][1])))
                return
            if geom_type == "GeometryCollection":
                for child in geometry.geoms:
                    add_intersection_points(child, out)

        split_points: list[tuple[float, float]] = []
        eps = 1e-8
        for index, start in enumerate(points):
            end = points[(index + 1) % len(points)]
            line = LineString((start, end))
            candidates = [start, end]
            for boundary in boundaries:
                intersection = line.intersection(boundary)
                if not intersection.is_empty:
                    add_intersection_points(intersection, candidates)
            dx = float(end[0] - start[0])
            dy = float(end[1] - start[1])
            denom = dx * dx + dy * dy
            if denom <= 1e-18:
                continue
            ordered: list[tuple[float, tuple[float, float]]] = []
            for point in candidates:
                t = ((float(point[0] - start[0]) * dx) + (float(point[1] - start[1]) * dy)) / denom
                if -eps <= t <= 1.0 + eps:
                    ordered.append((min(1.0, max(0.0, t)), (float(point[0]), float(point[1]))))
            ordered.sort(key=lambda item: item[0])
            for _, point in ordered:
                if split_points and abs(split_points[-1][0] - point[0]) <= eps and abs(split_points[-1][1] - point[1]) <= eps:
                    continue
                split_points.append(point)
        if (
            len(split_points) > 1
            and abs(split_points[0][0] - split_points[-1][0]) <= eps
            and abs(split_points[0][1] - split_points[-1][1]) <= eps
        ):
            split_points.pop()
        return split_points if len(split_points) >= 3 else points

    for cut in through_cuts or []:
        profile_points: list[tuple[float, float]]
        rings: list[tuple[float, float]] | None = None
        if "rings" in cut:
            try:
                plane_center = np.asarray(cut["plane_center"], dtype=np.float64)
                rings = [
                    (float(ring[0]), float(ring[1]))
                    for ring in cut["rings"]
                ]
            except (KeyError, TypeError, ValueError, IndexError):
                return None
            if plane_center.shape != (2,) or len(rings) < 2 or any(radius <= 0.0 for _, radius in rings):
                return None
            max_radius = float(max(radius for _, radius in rings))
            profile_points = _circle_points(plane_center, max_radius, sections=sections)
            footprint = Polygon(profile_points)
        elif "profile_points" in cut:
            try:
                profile_points = [
                    (float(point[0]), float(point[1]))
                    for point in cut["profile_points"]
                ]
            except (TypeError, ValueError, IndexError):
                return None
            if len(profile_points) < 3:
                return None
            footprint = Polygon(profile_points)
            plane_center = np.asarray(
                (float(footprint.centroid.x), float(footprint.centroid.y)),
                dtype=np.float64,
            )
        else:
            try:
                plane_center = np.asarray(cut["plane_center"], dtype=np.float64)
                radius = float(cut["radius"])
            except (KeyError, TypeError, ValueError):
                return None
            if plane_center.shape != (2,) or radius <= 0.0:
                return None
            profile_points = _circle_points(plane_center, radius, sections=sections)
            footprint = Polygon(profile_points)
        if not footprint.is_valid:
            footprint = footprint.buffer(0)
        if footprint.is_empty or float(footprint.area) <= 1e-9 or not rect.contains(footprint):
            return None
        ring_points = [(float(x), float(y)) for x, y in list(footprint.exterior.coords)[:-1]]
        if len(ring_points) < 3:
            return None
        cap_footprint = footprint
        cap_profile_points = list(ring_points)
        profile_bevel_width = 0.0
        profile_bevel_applied = False
        containing_boss_index: int | None = None
        partial_boss_cuts: list[dict[str, Any]] = []
        for index, boss in enumerate(prepared):
            boss_footprint = boss["base_footprint"]
            if boss_footprint.covers(footprint):
                if containing_boss_index is not None:
                    return None
                containing_boss_index = index
                continue
            if boss["max_footprint"].intersects(footprint):
                if rings is not None or boss.get("profile_points") is None:
                    return None
                intersection = boss["max_footprint"].intersection(footprint)
                if intersection.is_empty or float(intersection.area) <= 1e-9:
                    continue
                partial_boss_cuts.append(
                    {
                        "boss_index": int(index),
                        "footprint": intersection,
                    }
                )
        if rings is None and containing_boss_index is None and not partial_boss_cuts:
            try:
                candidate_bevel_width = max(0.0, float(cut.get("bevel_width") or 0.0))
            except (TypeError, ValueError):
                candidate_bevel_width = 0.0
            if candidate_bevel_width > 1e-9:
                centroid = footprint.centroid
                cx = float(centroid.x)
                cy = float(centroid.y)
                expanded_points: list[tuple[float, float]] = []
                for point_x, point_y in ring_points:
                    dx = float(point_x) - cx
                    dy = float(point_y) - cy
                    length = math.hypot(dx, dy)
                    if length <= 1e-9:
                        expanded_points.append((float(point_x), float(point_y)))
                    else:
                        scale = (length + candidate_bevel_width) / length
                        expanded_points.append((cx + dx * scale, cy + dy * scale))
                expanded = Polygon(expanded_points)
                if not expanded.is_valid:
                    expanded = expanded.buffer(0)
                intersects_boss = False
                for boss in prepared:
                    intersection = boss["max_footprint"].intersection(expanded)
                    if not intersection.is_empty and float(intersection.area) > 1e-9:
                        intersects_boss = True
                        break
                if (
                    not intersects_boss
                    and not expanded.is_empty
                    and float(expanded.area) > float(footprint.area)
                    and rect.contains(expanded)
                ):
                    cap_footprint = expanded
                    cap_profile_points = expanded_points
                    profile_bevel_width = candidate_bevel_width
                    profile_bevel_applied = True
        if partial_boss_cuts:
            ring_points = split_ring_points_at_boundaries(
                ring_points,
                [
                    prepared[int(partial["boss_index"])]["max_footprint"].boundary
                    for partial in partial_boss_cuts
                    if isinstance(partial, dict) and isinstance(partial.get("boss_index"), int)
                ],
            )
        hole_footprints.append(cap_footprint)
        hole_area_sum += float(cap_footprint.area)
        prepared_holes.append(
            {
                "plane_center": plane_center,
                "radius": float(cut.get("radius") or 0.0),
                "rings": [[float(axial), float(radius)] for axial, radius in rings] if rings is not None else None,
                "profile_points": [[float(x), float(y)] for x, y in ring_points],
                "cap_profile_points": [[float(x), float(y)] for x, y in cap_profile_points],
                "bevel_width": float(profile_bevel_width),
                "bevel_applied": bool(profile_bevel_applied),
                "cut_kind": str(cut.get("cut_kind") or "profile_through"),
                "footprint": footprint,
                "cap_footprint": cap_footprint,
                "boss_index": containing_boss_index,
                "partial_boss_cuts": partial_boss_cuts,
            }
        )
    def hole_polygon_at_axial(hole: dict[str, Any], axial: float) -> Any | None:
        rings_value = hole.get("rings")
        if isinstance(rings_value, list) and rings_value:
            try:
                rings = [
                    (float(ring[0]), float(ring[1]))
                    for ring in rings_value
                ]
            except (TypeError, ValueError, IndexError):
                return None
            radius = _radius_at_profile_axial(rings, float(axial))
            if radius is None or radius <= 0.0:
                return None
            plane_center = np.asarray(hole["plane_center"], dtype=np.float64)
            return Polygon(_circle_points(plane_center, radius, sections=sections))
        try:
            points_key = "cap_profile_points" if hole.get("bevel_applied") else "profile_points"
            points = [
                (float(point[0]), float(point[1]))
                for point in hole[points_key]
            ]
        except (KeyError, TypeError, ValueError, IndexError):
            return None
        return Polygon(points)

    max_hole_union = None
    if hole_footprints:
        max_hole_union = unary_union(hole_footprints)
        hole_tolerance = max(1e-6, abs(hole_area_sum) * 1e-7)
        if max_hole_union.is_empty or abs(float(max_hole_union.area) - hole_area_sum) > hole_tolerance:
            return None
    base_face_axial = float(box_max[cut_axis] if side > 0 else box_min[cut_axis])
    opposite_face_axial = float(box_min[cut_axis] if side > 0 else box_max[cut_axis])
    base_face_holes: list[Any] = []
    opposite_face_holes: list[Any] = []
    for hole in prepared_holes:
        base_hole = hole_polygon_at_axial(hole, base_face_axial)
        opposite_hole = hole_polygon_at_axial(hole, opposite_face_axial)
        if base_hole is None or opposite_hole is None:
            return None
        base_face_holes.append(base_hole)
        opposite_face_holes.append(opposite_hole)
    base_face_hole_union = unary_union(base_face_holes) if base_face_holes else None
    opposite_face_hole_union = unary_union(opposite_face_holes) if opposite_face_holes else None
    base_blockers = list(top_level_footprints)
    if base_face_hole_union is not None:
        base_blockers.append(base_face_hole_union)
    base_remaining = rect.difference(unary_union(base_blockers))
    if base_remaining.is_empty or float(base_remaining.area) <= 1e-9:
        return None
    opposite_remaining = rect.difference(opposite_face_hole_union) if opposite_face_hole_union is not None else rect
    if opposite_remaining.is_empty or float(opposite_remaining.area) <= 1e-9:
        return None

    vertices: list[tuple[float, float, float]] = []
    vertex_index: dict[tuple[int, int, int], int] = {}
    faces: list[list[int]] = []

    def add_vertex(plane_point: tuple[float, float], axial: float) -> int:
        coord = [0.0, 0.0, 0.0]
        coord[cut_axis] = float(axial)
        coord[plane_axes[0]] = float(plane_point[0])
        coord[plane_axes[1]] = float(plane_point[1])
        key = tuple(int(round(value * 1_000_000)) for value in coord)
        existing = vertex_index.get(key)
        if existing is not None:
            return existing
        vertex_index[key] = len(vertices)
        vertices.append((coord[0], coord[1], coord[2]))
        return len(vertices) - 1

    def add_triangle(points: list[tuple[float, float]], axial: float, *, reverse: bool) -> None:
        if len(points) < 3:
            return
        tri = [add_vertex(point, axial) for point in points[:3]]
        faces.append([tri[0], tri[2], tri[1]] if reverse else tri)

    def add_wall(
        a_point: tuple[float, float],
        b_point: tuple[float, float],
        *,
        low: float,
        high: float,
        reverse: bool,
    ) -> None:
        quad = [
            add_vertex(a_point, low),
            add_vertex(b_point, low),
            add_vertex(b_point, high),
            add_vertex(a_point, high),
        ]
        faces.append([quad[0], quad[1], quad[2]] if not reverse else [quad[0], quad[2], quad[1]])
        faces.append([quad[0], quad[2], quad[3]] if not reverse else [quad[0], quad[3], quad[2]])

    def polygons(geometry: Any) -> list[Any]:
        if geometry.geom_type == "Polygon":
            return [geometry]
        if geometry.geom_type == "MultiPolygon":
            return list(geometry.geoms)
        return []

    def add_geometry_boundary_walls(
        geometry: Any,
        *,
        wall_low: float,
        wall_high: float,
    ) -> int:
        count = 0
        for polygon in polygons(geometry):
            exterior = [
                (float(x), float(y))
                for x, y in list(polygon.exterior.coords)[:-1]
            ]
            for index, point in enumerate(exterior):
                add_wall(point, exterior[(index + 1) % len(exterior)], low=wall_low, high=wall_high, reverse=False)
                count += 2
            for interior in polygon.interiors:
                ring = [
                    (float(x), float(y))
                    for x, y in list(interior.coords)[:-1]
                ]
                if len(ring) < 3:
                    continue
                for index, point in enumerate(ring):
                    add_wall(point, ring[(index + 1) % len(ring)], low=wall_low, high=wall_high, reverse=True)
                    count += 2
        return count

    cap_triangle_count = 0

    def add_cap(geometry: Any, axial: float, *, reverse: bool) -> int:
        count = 0
        for polygon in polygons(geometry):
            try:
                vertices_2d, faces_2d = trimesh.creation.triangulate_polygon(
                    polygon,
                    force_vertices=True,
                )
            except (AttributeError, ValueError, RuntimeError, ImportError, ModuleNotFoundError):
                for triangle in triangulate(polygon):
                    if float(triangle.area) <= 1e-9 or not polygon.covers(triangle.representative_point()):
                        continue
                    coords = [(float(x), float(y)) for x, y in list(triangle.exterior.coords)[:3]]
                    add_triangle(coords, axial, reverse=reverse)
                    count += 1
                continue
            for face in faces_2d:
                coords = [
                    (float(vertices_2d[int(index)][0]), float(vertices_2d[int(index)][1]))
                    for index in face[:3]
                ]
                if len(coords) < 3:
                    continue
                add_triangle(coords, axial, reverse=reverse)
                count += 1
        return count

    low = float(box_min[cut_axis])
    high = float(box_max[cut_axis])
    if side > 0:
        cap_triangle_count += add_cap(opposite_remaining, low, reverse=True)
        cap_triangle_count += add_cap(base_remaining, high, reverse=False)
    else:
        cap_triangle_count += add_cap(base_remaining, low, reverse=True)
        cap_triangle_count += add_cap(opposite_remaining, high, reverse=False)

    rect_ring = [(float(x), float(y)) for x, y in list(rect.exterior.coords)]
    box_side_face_count = 0
    for index in range(len(rect_ring) - 1):
        add_wall(rect_ring[index], rect_ring[index + 1], low=low, high=high, reverse=False)
        box_side_face_count += 2

    boss_wall_face_count = 0
    boss_cap_face_count = 0
    boss_cylinder_face_count = 0
    boss_chamfer_face_count = 0
    boss_shoulder_face_count = 0
    partial_boss_cut_count = 0
    for boss_index, boss in enumerate(prepared):
        plane_center = boss["plane_center"]
        rings = boss["rings"]
        if boss.get("profile_points") is not None:
            profile_points = [
                (float(point[0]), float(point[1]))
                for point in boss["profile_points"]
            ]
            if boss.get("profile_rings") is not None:
                try:
                    ring_points = [
                        [
                            (float(point[0]), float(point[1]))
                            for point in ring
                        ]
                        for ring in boss["profile_rings"]
                    ]
                except (TypeError, ValueError, IndexError):
                    return None
                if len(ring_points) != len(rings) or any(len(ring) < 3 for ring in ring_points):
                    return None
            else:
                ring_points = [profile_points for _ in rings]
            profile_holes = [
                [
                    (float(point[0]), float(point[1]))
                    for point in hole
                ]
                for hole in boss.get("profile_holes", [])
            ]
        else:
            ring_points = [
                _circle_points(plane_center, radius, sections=sections)
                for _, radius in rings
            ]
            profile_holes = []
        cap_geometry = boss["outer_footprint"]
        boss_holes = []
        boss_partial_holes = []
        child_boss_footprints = [
            prepared[child_index]["base_footprint"]
            for child_index, parent_index in parent_by_boss.items()
            if parent_index == boss_index
        ]
        for hole in prepared_holes:
            if hole.get("boss_index") != boss_index:
                for partial in hole.get("partial_boss_cuts", []):
                    if not isinstance(partial, dict) or partial.get("boss_index") != boss_index:
                        continue
                    hole_cap = hole_polygon_at_axial(hole, float(rings[-1][0]))
                    if hole_cap is None:
                        return None
                    intersection = boss["outer_footprint"].intersection(hole_cap)
                    if intersection.is_empty or float(intersection.area) <= 1e-9:
                        continue
                    boss_partial_holes.append(intersection)
                continue
            hole_cap = hole_polygon_at_axial(hole, float(rings[-1][0]))
            if hole_cap is None:
                return None
            boss_holes.append(hole_cap)
        if boss_holes and boss_partial_holes:
            return None
        partial_boss_cut_count += len(boss_partial_holes)
        use_boundary_wall_geometry = bool(boss_partial_holes) and boss.get("profile_points") is not None
        wall_cut_holes = [*boss_holes, *boss_partial_holes]
        if wall_cut_holes:
            cap_geometry = cap_geometry.difference(unary_union(wall_cut_holes))
            if cap_geometry.is_empty or float(cap_geometry.area) <= 1e-9:
                return None
        wall_geometry = cap_geometry
        if child_boss_footprints:
            cap_geometry = cap_geometry.difference(unary_union(child_boss_footprints))
            if cap_geometry.is_empty or float(cap_geometry.area) <= 1e-9:
                return None
        if use_boundary_wall_geometry:
            for ring_index in range(len(rings) - 1):
                left_axial, left_radius = rings[ring_index]
                right_axial, right_radius = rings[ring_index + 1]
                if abs(left_axial - right_axial) <= 1e-9 and abs(left_radius - right_radius) <= 1e-9:
                    continue
                added = add_geometry_boundary_walls(
                    wall_geometry,
                    wall_low=float(left_axial),
                    wall_high=float(right_axial),
                )
                boss_wall_face_count += added
                if abs(left_axial - right_axial) <= 1e-9:
                    boss_shoulder_face_count += added
                elif abs(left_radius - right_radius) > 1e-9:
                    boss_chamfer_face_count += added
                else:
                    boss_cylinder_face_count += added
        else:
            for ring_index in range(len(rings) - 1):
                left_axial, left_radius = rings[ring_index]
                right_axial, right_radius = rings[ring_index + 1]
                left_ring = ring_points[ring_index]
                right_ring = ring_points[ring_index + 1]
                if abs(left_axial - right_axial) <= 1e-9 and abs(left_radius - right_radius) <= 1e-9:
                    continue
                segment_count = min(len(left_ring), len(right_ring))
                if segment_count < 3:
                    return None
                for index in range(segment_count):
                    next_index = (index + 1) % segment_count
                    quad = [
                        add_vertex(left_ring[index], left_axial),
                        add_vertex(left_ring[next_index], left_axial),
                        add_vertex(right_ring[next_index], right_axial),
                        add_vertex(right_ring[index], right_axial),
                    ]
                    faces.append([quad[0], quad[1], quad[2]])
                    faces.append([quad[0], quad[2], quad[3]])
                    boss_wall_face_count += 2
                    if abs(left_axial - right_axial) <= 1e-9:
                        boss_shoulder_face_count += 2
                    elif abs(left_radius - right_radius) > 1e-9:
                        boss_chamfer_face_count += 2
                    else:
                        boss_cylinder_face_count += 2
                for hole in profile_holes:
                    if len(hole) < 3:
                        return None
                    for index in range(len(hole)):
                        next_index = (index + 1) % len(hole)
                        quad = [
                            add_vertex(hole[index], left_axial),
                            add_vertex(hole[next_index], left_axial),
                            add_vertex(hole[next_index], right_axial),
                            add_vertex(hole[index], right_axial),
                        ]
                        faces.append([quad[0], quad[2], quad[1]])
                        faces.append([quad[0], quad[3], quad[2]])
                        boss_wall_face_count += 2
                        if abs(left_axial - right_axial) <= 1e-9:
                            boss_shoulder_face_count += 2
                        elif abs(left_radius - right_radius) > 1e-9:
                            boss_chamfer_face_count += 2
                        else:
                            boss_cylinder_face_count += 2
        boss_cap_face_count += add_cap(
            cap_geometry,
            float(rings[-1][0]),
            reverse=side < 0,
        )

    hole_wall_face_count = 0
    through_cut_bevel_face_count = 0

    def add_profile_hole_walls(
        hole: dict[str, Any],
        wall_low: float,
        wall_high: float,
    ) -> tuple[int, int] | None:
        try:
            core_points = [
                (float(point[0]), float(point[1]))
                for point in hole["profile_points"]
            ]
        except (KeyError, TypeError, ValueError, IndexError):
            return None
        if len(core_points) < 3:
            return None
        bevel_width = max(0.0, float(hole.get("bevel_width") or 0.0))
        if not bool(hole.get("bevel_applied")) or bevel_width <= 1e-9:
            count = 0
            for index, point in enumerate(core_points):
                add_wall(point, core_points[(index + 1) % len(core_points)], low=wall_low, high=wall_high, reverse=True)
                count += 2
            return count, 0
        try:
            cap_points = [
                (float(point[0]), float(point[1]))
                for point in hole["cap_profile_points"]
            ]
        except (KeyError, TypeError, ValueError, IndexError):
            return None
        if len(cap_points) != len(core_points):
            return None
        bevel_depth = min(bevel_width, max((float(wall_high) - float(wall_low)) * 0.45, 0.0))
        if bevel_depth <= 1e-9:
            return None
        low_inner = float(wall_low) + bevel_depth
        high_inner = float(wall_high) - bevel_depth

        def add_quad_points(
            points: tuple[
                tuple[tuple[float, float], float],
                tuple[tuple[float, float], float],
                tuple[tuple[float, float], float],
                tuple[tuple[float, float], float],
            ],
            *,
            reverse: bool,
        ) -> None:
            quad = [add_vertex(point, axial) for point, axial in points]
            faces.append([quad[0], quad[1], quad[2]] if not reverse else [quad[0], quad[2], quad[1]])
            faces.append([quad[0], quad[2], quad[3]] if not reverse else [quad[0], quad[3], quad[2]])

        bevel_count = 0
        for index, core_a in enumerate(core_points):
            next_index = (index + 1) % len(core_points)
            core_b = core_points[next_index]
            cap_a = cap_points[index]
            cap_b = cap_points[next_index]
            add_quad_points(
                (
                    (cap_a, float(wall_low)),
                    (cap_b, float(wall_low)),
                    (core_b, low_inner),
                    (core_a, low_inner),
                ),
                reverse=True,
            )
            add_quad_points(
                (
                    (core_a, high_inner),
                    (core_b, high_inner),
                    (cap_b, float(wall_high)),
                    (cap_a, float(wall_high)),
                ),
                reverse=False,
            )
            bevel_count += 4
        wall_count = 0
        if high_inner > low_inner + 1e-9:
            for index, point in enumerate(core_points):
                add_wall(point, core_points[(index + 1) % len(core_points)], low=low_inner, high=high_inner, reverse=True)
                wall_count += 2
        return wall_count, bevel_count

    def add_revolved_hole_walls(hole: dict[str, Any], wall_low: float, wall_high: float) -> tuple[int, int] | None:
        try:
            rings = [
                (float(ring[0]), float(ring[1]))
                for ring in hole["rings"]
            ]
            plane_center = np.asarray(hole["plane_center"], dtype=np.float64)
        except (KeyError, TypeError, ValueError, IndexError):
            return None
        low_radius = _radius_at_profile_axial(rings, wall_low)
        high_radius = _radius_at_profile_axial(rings, wall_high)
        if low_radius is None or high_radius is None:
            return None
        clipped: list[tuple[float, float]] = [(float(wall_low), float(low_radius))]
        for axial, radius in rings:
            if wall_low + 1e-9 < axial < wall_high - 1e-9:
                clipped.append((float(axial), float(radius)))
        clipped.append((float(wall_high), float(high_radius)))
        cleaned: list[tuple[float, float]] = []
        for axial, radius in clipped:
            if cleaned and abs(cleaned[-1][0] - axial) <= 1e-9 and abs(cleaned[-1][1] - radius) <= 1e-9:
                continue
            cleaned.append((axial, radius))
        if len(cleaned) < 2:
            return None
        wall_count = 0
        bevel_count = 0
        ring_points = [
            _circle_points(plane_center, radius, sections=sections)
            for _, radius in cleaned
        ]
        for ring_index in range(len(cleaned) - 1):
            left_axial, left_radius = cleaned[ring_index]
            right_axial, right_radius = cleaned[ring_index + 1]
            left_ring = ring_points[ring_index]
            right_ring = ring_points[ring_index + 1]
            for index, point in enumerate(left_ring):
                next_index = (index + 1) % len(left_ring)
                quad = [
                    add_vertex(point, left_axial),
                    add_vertex(left_ring[next_index], left_axial),
                    add_vertex(right_ring[next_index], right_axial),
                    add_vertex(right_ring[index], right_axial),
                ]
                faces.append([quad[0], quad[2], quad[1]])
                faces.append([quad[0], quad[3], quad[2]])
                wall_count += 2
                if abs(left_radius - right_radius) > 1e-9:
                    bevel_count += 2
        return wall_count, bevel_count

    for hole in prepared_holes:
        if hole.get("rings") is not None:
            added = add_revolved_hole_walls(hole, low, high)
            if added is None:
                return None
            wall_count, bevel_count = added
            hole_wall_face_count += wall_count
            through_cut_bevel_face_count += bevel_count
        else:
            added = add_profile_hole_walls(hole, low, high)
            if added is None:
                return None
            wall_count, bevel_count = added
            hole_wall_face_count += wall_count
            through_cut_bevel_face_count += bevel_count
        boss_index = hole.get("boss_index")
        if isinstance(boss_index, int):
            outer_axial = float(prepared[boss_index]["rings"][-1][0])
            wall_low = min(base_axial, outer_axial)
            wall_high = max(base_axial, outer_axial)
            if hole.get("rings") is not None:
                added = add_revolved_hole_walls(hole, wall_low, wall_high)
                if added is None:
                    return None
                wall_count, bevel_count = added
                hole_wall_face_count += wall_count
                through_cut_bevel_face_count += bevel_count
            else:
                added = add_profile_hole_walls(hole, wall_low, wall_high)
                if added is None:
                    return None
                wall_count, bevel_count = added
                hole_wall_face_count += wall_count
                through_cut_bevel_face_count += bevel_count

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()
    mesh.fix_normals()
    boss_bevel_face_count = int(boss_chamfer_face_count)
    through_bevel_face_count = int(through_cut_bevel_face_count)
    total_bevel_face_count = boss_bevel_face_count + through_bevel_face_count
    return mesh, {
        "boss_count": len(bosses),
        "nested_boss_count": len(parent_by_boss),
        "cap_triangle_count": cap_triangle_count,
        "box_side_face_count": box_side_face_count,
        "boss_wall_face_count": boss_wall_face_count,
        "boss_cylinder_face_count": boss_cylinder_face_count,
        "boss_chamfer_face_count": boss_chamfer_face_count,
        "boss_shoulder_face_count": boss_shoulder_face_count,
        "boss_cap_face_count": boss_cap_face_count,
        "through_cut_count": len(prepared_holes),
        "through_cut_kinds": sorted({str(hole.get("cut_kind") or "") for hole in prepared_holes}),
        "partial_boss_cut_count": partial_boss_cut_count,
        "boss_profile_hole_count": sum(len(boss.get("profile_holes") or []) for boss in prepared),
        "hole_wall_face_count": hole_wall_face_count,
        "through_cut_bevel_face_count": through_bevel_face_count,
        "boss_bevel_face_count": boss_bevel_face_count,
        "bevel_face_count": total_bevel_face_count,
        "bevel_applied": total_bevel_face_count > 0,
        "radial_section_count": int(sections),
        "result_face_count": len(mesh.faces),
        "result_watertight": bool(mesh.is_watertight),
    }


def _exact_boss_state_cylinder_difference(
    a: trimesh.Trimesh,
    b: trimesh.Trimesh,
) -> trimesh.Trimesh | None:
    state = _boss_state_from_mesh(a)
    cylinder = _cylinder_metadata(b)
    if state is None or cylinder is None:
        return None
    try:
        box_min = np.asarray(state["box_min"], dtype=np.float64)
        box_max = np.asarray(state["box_max"], dtype=np.float64)
        cut_axis = int(state["cut_axis"])
        plane_axes = tuple(int(value) for value in state["plane_axes"])
        side = int(state["side"])
    except (KeyError, TypeError, ValueError):
        return None
    if box_min.shape != (3,) or box_max.shape != (3,) or bool(np.any(box_max <= box_min)):
        return None
    if side not in {-1, 1} or cut_axis not in {0, 1, 2}:
        return None
    if len(plane_axes) != 2 or set(plane_axes) != ({0, 1, 2} - {cut_axis}):
        return None
    if {"x": 0, "y": 1, "z": 2}[str(cylinder["axis"])] != cut_axis:
        return None

    bosses = [
        dict(item)
        for item in state.get("bosses", [])
        if isinstance(item, dict)
    ]
    if not bosses or len(bosses) != len(state.get("bosses", [])):
        return None
    previous_cuts = [
        dict(item)
        for item in state.get("through_cuts", [])
        if isinstance(item, dict)
    ]
    if len(previous_cuts) != len(state.get("through_cuts", [])):
        return None

    center = np.asarray(cylinder["center"], dtype=np.float64)
    radius = float(cylinder["radius"])
    half_height = float(cylinder["height"]) * 0.5
    cyl_min = float(center[cut_axis] - half_height)
    cyl_max = float(center[cut_axis] + half_height)
    outer_axials: list[float] = []
    for boss in bosses:
        try:
            outer_axials.append(float(boss["outer_axial"]))
        except (KeyError, TypeError, ValueError):
            return None
    object_low = float(box_min[cut_axis])
    object_high = float(box_max[cut_axis])
    if side > 0:
        object_high = max([object_high, *outer_axials])
    else:
        object_low = min([object_low, *outer_axials])
    if cyl_min > object_low + 1e-7 or cyl_max < object_high - 1e-7:
        return None

    plane_center = np.asarray((center[plane_axes[0]], center[plane_axes[1]]), dtype=np.float64)
    bevel_width = max(0.0, float(cylinder.get("bevel_width_cm") or 0.0))
    if bevel_width > 1e-9:
        depth = max(0.0, object_high - object_low)
        bevel_depth = min(bevel_width, depth * 0.45)
        bevel_radius = radius + bevel_width
        rings = [
            (object_low, bevel_radius),
            (object_low + bevel_depth, radius),
            (object_high - bevel_depth, radius),
            (object_high, bevel_radius),
        ]
        cut_kind = "beveled_cylinder_through"
        style = "beveled_cylinder"
    else:
        rings = []
        cut_kind = "cylinder_through"
        style = "cylinder"
    new_cut = {
        "cut_kind": cut_kind,
        "center": [float(value) for value in center],
        "plane_center": [float(value) for value in plane_center],
        "radius": radius,
        **({"rings": [[float(axial), float(value)] for axial, value in rings]} if rings else {}),
        "style": style,
        "cutter_part": str(cylinder.get("part") or "cylinder"),
    }
    cuts = [*previous_cuts, new_cut]
    built = _mesh_from_box_cylinder_bosses(
        box_min=box_min,
        box_max=box_max,
        cut_axis=cut_axis,
        plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
        side=side,
        bosses=bosses,
        through_cuts=cuts,
    )
    if built is None:
        return None
    result, stats = built
    method = (
        "axis_aligned_boss_state_repeated_through_cylinder_difference_v1"
        if previous_cuts
        else "axis_aligned_boss_state_through_cylinder_difference_v1"
    )
    result.metadata[_BOSS_STATE_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_boss_state.v1",
        "box_min": [float(value) for value in box_min],
        "box_max": [float(value) for value in box_max],
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "side": int(side),
        "bosses": bosses,
        "through_cuts": cuts,
    }
    result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_exact_boolean.v1",
        "method": method,
        "op": "difference",
        "overlap": True,
        "through_cut": True,
        "passthrough": False,
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "side": int(side),
        "cutter_part": str(cylinder.get("part") or "cylinder"),
        "profile_style": style,
        "boss_count": len(bosses),
        "through_cut_count": len(cuts),
        "through_cut_kinds": sorted({str(cut.get("cut_kind") or "") for cut in cuts}),
        **stats,
        "bevel_width_cm": bevel_width,
        "bevel_applied": bevel_width > 1e-9,
    }
    _set_batch_source_meshes(result, (result,))
    return result


def _exact_boss_state_extruded_profile_difference(
    a: trimesh.Trimesh,
    b: trimesh.Trimesh,
) -> trimesh.Trimesh | None:
    state = _boss_state_from_mesh(a)
    profile_metadata = _extruded_profile_metadata(b)
    if state is None or profile_metadata is None:
        return None
    plane = _extruded_profile_plane_points(profile_metadata)
    if plane is None:
        return None
    profile_cut_axis, profile_plane_axes, profile_points = plane
    try:
        box_min = np.asarray(state["box_min"], dtype=np.float64)
        box_max = np.asarray(state["box_max"], dtype=np.float64)
        cut_axis = int(state["cut_axis"])
        plane_axes = tuple(int(value) for value in state["plane_axes"])
        side = int(state["side"])
    except (KeyError, TypeError, ValueError):
        return None
    if box_min.shape != (3,) or box_max.shape != (3,) or bool(np.any(box_max <= box_min)):
        return None
    if profile_cut_axis != cut_axis or tuple(profile_plane_axes) != tuple(plane_axes):
        return None
    if side not in {-1, 1} or cut_axis not in {0, 1, 2}:
        return None
    if len(plane_axes) != 2 or set(plane_axes) != ({0, 1, 2} - {cut_axis}):
        return None

    bosses = [
        dict(item)
        for item in state.get("bosses", [])
        if isinstance(item, dict)
    ]
    if not bosses or len(bosses) != len(state.get("bosses", [])):
        return None
    previous_cuts = [
        dict(item)
        for item in state.get("through_cuts", [])
        if isinstance(item, dict)
    ]
    if len(previous_cuts) != len(state.get("through_cuts", [])):
        return None

    center = np.asarray(profile_metadata["center"], dtype=np.float64)
    half_height = float(profile_metadata["extrude_height"]) * 0.5
    cutter_low = float(center[cut_axis] - half_height)
    cutter_high = float(center[cut_axis] + half_height)
    outer_axials: list[float] = []
    for boss in bosses:
        try:
            outer_axials.append(float(boss["outer_axial"]))
        except (KeyError, TypeError, ValueError):
            return None
    object_low = float(box_min[cut_axis])
    object_high = float(box_max[cut_axis])
    if side > 0:
        object_high = max([object_high, *outer_axials])
    else:
        object_low = min([object_low, *outer_axials])
    if cutter_low > object_low + 1e-7 or cutter_high < object_high - 1e-7:
        return None

    new_cut = {
        "cut_kind": "extruded_profile_through",
        "profile_points": [[float(point[0]), float(point[1])] for point in profile_points],
        "bevel_width": float(profile_metadata.get("bevel_width_cm") or 0.0),
        "cutter_part": str(profile_metadata.get("part") or "extruded_profile"),
    }
    cuts = [*previous_cuts, new_cut]
    built = _mesh_from_box_cylinder_bosses(
        box_min=box_min,
        box_max=box_max,
        cut_axis=cut_axis,
        plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
        side=side,
        bosses=bosses,
        through_cuts=cuts,
    )
    if built is None:
        return None
    result, stats = built
    method = (
        "axis_aligned_boss_state_repeated_through_profile_difference_v1"
        if previous_cuts
        else "axis_aligned_boss_state_through_profile_difference_v1"
    )
    result.metadata[_BOSS_STATE_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_boss_state.v1",
        "box_min": [float(value) for value in box_min],
        "box_max": [float(value) for value in box_max],
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "side": int(side),
        "bosses": bosses,
        "through_cuts": cuts,
    }
    result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_exact_boolean.v1",
        "method": method,
        "op": "difference",
        "overlap": True,
        "through_cut": True,
        "passthrough": False,
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "side": int(side),
        "cutter_part": str(profile_metadata.get("part") or "extruded_profile"),
        "boss_count": len(bosses),
        "through_cut_count": len(cuts),
        "through_cut_kinds": sorted({str(cut.get("cut_kind") or "") for cut in cuts}),
        **stats,
    }
    _set_batch_source_meshes(result, (result,))
    return result


def _exact_boss_state_box_difference(
    a: trimesh.Trimesh,
    b: trimesh.Trimesh,
) -> trimesh.Trimesh | None:
    state = _boss_state_from_mesh(a)
    cutter_bounds = _box_bounds_from_metadata(b)
    if (
        state is None
        or cutter_bounds is None
        or _boss_state_from_mesh(b) is not None
        or _profile_cut_state_from_mesh(b) is not None
    ):
        return None
    try:
        box_min = np.asarray(state["box_min"], dtype=np.float64)
        box_max = np.asarray(state["box_max"], dtype=np.float64)
        cut_axis = int(state["cut_axis"])
        plane_axes = tuple(int(value) for value in state["plane_axes"])
        side = int(state["side"])
    except (KeyError, TypeError, ValueError):
        return None
    if box_min.shape != (3,) or box_max.shape != (3,) or bool(np.any(box_max <= box_min)):
        return None
    if side not in {-1, 1} or cut_axis not in {0, 1, 2}:
        return None
    if len(plane_axes) != 2 or set(plane_axes) != ({0, 1, 2} - {cut_axis}):
        return None

    bosses = [
        dict(item)
        for item in state.get("bosses", [])
        if isinstance(item, dict)
    ]
    if not bosses or len(bosses) != len(state.get("bosses", [])):
        return None
    previous_cuts = [
        dict(item)
        for item in state.get("through_cuts", [])
        if isinstance(item, dict)
    ]
    if len(previous_cuts) != len(state.get("through_cuts", [])):
        return None

    cutter_min, cutter_max = cutter_bounds
    if cutter_min.shape != (3,) or cutter_max.shape != (3,) or bool(np.any(cutter_max <= cutter_min)):
        return None
    outer_axials: list[float] = []
    for boss in bosses:
        try:
            outer_axials.append(float(boss["outer_axial"]))
        except (KeyError, TypeError, ValueError):
            return None
    object_low = float(box_min[cut_axis])
    object_high = float(box_max[cut_axis])
    if side > 0:
        object_high = max([object_high, *outer_axials])
    else:
        object_low = min([object_low, *outer_axials])
    if float(cutter_min[cut_axis]) > object_low + 1e-7:
        return None
    if float(cutter_max[cut_axis]) < object_high - 1e-7:
        return None

    u0 = float(cutter_min[plane_axes[0]])
    u1 = float(cutter_max[plane_axes[0]])
    v0 = float(cutter_min[plane_axes[1]])
    v1 = float(cutter_max[plane_axes[1]])
    if u1 <= u0 + 1e-9 or v1 <= v0 + 1e-9:
        return None
    primitive = _resolved_shape_primitive_metadata(b)
    new_cut = {
        "cut_kind": "box_profile_through",
        "profile_points": [[u0, v0], [u1, v0], [u1, v1], [u0, v1]],
        "cutter_part": str(primitive.get("part") or "box"),
    }
    cuts = [*previous_cuts, new_cut]
    built = _mesh_from_box_cylinder_bosses(
        box_min=box_min,
        box_max=box_max,
        cut_axis=cut_axis,
        plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
        side=side,
        bosses=bosses,
        through_cuts=cuts,
    )
    if built is None:
        return None
    result, stats = built
    method = (
        "axis_aligned_boss_state_repeated_through_box_profile_difference_v1"
        if previous_cuts
        else "axis_aligned_boss_state_through_box_profile_difference_v1"
    )
    result.metadata[_BOSS_STATE_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_boss_state.v1",
        "box_min": [float(value) for value in box_min],
        "box_max": [float(value) for value in box_max],
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "side": int(side),
        "bosses": bosses,
        "through_cuts": cuts,
    }
    result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_exact_boolean.v1",
        "method": method,
        "op": "difference",
        "overlap": True,
        "through_cut": True,
        "passthrough": False,
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "side": int(side),
        "cutter_part": str(new_cut["cutter_part"]),
        "boss_count": len(bosses),
        "through_cut_count": len(cuts),
        "through_cut_kinds": sorted({str(cut.get("cut_kind") or "") for cut in cuts}),
        **stats,
    }
    _set_batch_source_meshes(result, (result,))
    return result


def _exact_boss_state_revolved_profile_difference(
    a: trimesh.Trimesh,
    b: trimesh.Trimesh,
) -> trimesh.Trimesh | None:
    state = _boss_state_from_mesh(a)
    profile_metadata = _revolved_profile_metadata(b)
    if state is None or profile_metadata is None:
        return None
    try:
        box_min = np.asarray(state["box_min"], dtype=np.float64)
        box_max = np.asarray(state["box_max"], dtype=np.float64)
        cut_axis = int(state["cut_axis"])
        plane_axes = tuple(int(value) for value in state["plane_axes"])
        side = int(state["side"])
    except (KeyError, TypeError, ValueError):
        return None
    if box_min.shape != (3,) or box_max.shape != (3,) or bool(np.any(box_max <= box_min)):
        return None
    if side not in {-1, 1} or cut_axis not in {0, 1, 2}:
        return None
    if len(plane_axes) != 2 or set(plane_axes) != ({0, 1, 2} - {cut_axis}):
        return None
    if {"x": 0, "y": 1, "z": 2}[str(profile_metadata["axis"])] != cut_axis:
        return None

    bosses = [
        dict(item)
        for item in state.get("bosses", [])
        if isinstance(item, dict)
    ]
    if not bosses or len(bosses) != len(state.get("bosses", [])):
        return None
    previous_cuts = [
        dict(item)
        for item in state.get("through_cuts", [])
        if isinstance(item, dict)
    ]
    if len(previous_cuts) != len(state.get("through_cuts", [])):
        return None

    center = np.asarray(profile_metadata["center"], dtype=np.float64)
    outer_axials: list[float] = []
    for boss in bosses:
        try:
            outer_axials.append(float(boss["outer_axial"]))
        except (KeyError, TypeError, ValueError):
            return None
    object_low = float(box_min[cut_axis])
    object_high = float(box_max[cut_axis])
    if side > 0:
        object_high = max([object_high, *outer_axials])
    else:
        object_low = min([object_low, *outer_axials])
    rings = _clipped_revolved_profile_rings(
        center=center,
        profile=list(profile_metadata["profile_points"]),
        axis_index=cut_axis,
        low=object_low,
        high=object_high,
        bevel_width=float(profile_metadata.get("bevel_width_cm") or 0.0),
    )
    if rings is None:
        return None
    plane_center = np.asarray((center[plane_axes[0]], center[plane_axes[1]]), dtype=np.float64)
    new_cut = {
        "cut_kind": "revolved_profile_through",
        "center": [float(value) for value in center],
        "plane_center": [float(value) for value in plane_center],
        "rings": [[float(axial), float(radius)] for axial, radius in rings],
        "style": str(profile_metadata.get("style") or "revolved_profile"),
        "cutter_part": str(profile_metadata.get("part") or "revolved_profile"),
    }
    cuts = [*previous_cuts, new_cut]
    built = _mesh_from_box_cylinder_bosses(
        box_min=box_min,
        box_max=box_max,
        cut_axis=cut_axis,
        plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
        side=side,
        bosses=bosses,
        through_cuts=cuts,
    )
    if built is None:
        return None
    result, stats = built
    method = (
        "axis_aligned_boss_state_repeated_through_revolved_profile_difference_v1"
        if previous_cuts
        else "axis_aligned_boss_state_through_revolved_profile_difference_v1"
    )
    result.metadata[_BOSS_STATE_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_boss_state.v1",
        "box_min": [float(value) for value in box_min],
        "box_max": [float(value) for value in box_max],
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "side": int(side),
        "bosses": bosses,
        "through_cuts": cuts,
    }
    result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_exact_boolean.v1",
        "method": method,
        "op": "difference",
        "overlap": True,
        "through_cut": True,
        "passthrough": False,
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "side": int(side),
        "cutter_part": str(profile_metadata.get("part") or "revolved_profile"),
        "boss_count": len(bosses),
        "through_cut_count": len(cuts),
        "through_cut_kinds": sorted({str(cut.get("cut_kind") or "") for cut in cuts}),
        **stats,
    }
    _set_batch_source_meshes(result, (result,))
    return result


def _boss_state_through_cuts(state: dict[str, Any]) -> list[dict[str, Any]] | None:
    raw_cuts = state.get("through_cuts", [])
    if not raw_cuts:
        return []
    if not isinstance(raw_cuts, list):
        return None
    cuts = [dict(item) for item in raw_cuts if isinstance(item, dict)]
    if len(cuts) != len(raw_cuts):
        return None
    return cuts


def _through_cuts_from_profile_cut_state(
    state: dict[str, Any],
    *,
    plane_axes: tuple[int, int],
) -> list[dict[str, Any]] | None:
    state_kind = str(state.get("cut_kind") or "")
    if state_kind not in {"extruded", "revolved", "mixed"}:
        return None
    raw_cuts = state.get("cuts", [])
    if not isinstance(raw_cuts, list):
        return None
    through_cuts: list[dict[str, Any]] = []
    for raw_cut in raw_cuts:
        if not isinstance(raw_cut, dict):
            return None
        cut_kind = str(raw_cut.get("cut_kind") or state_kind)
        if cut_kind not in {"extruded", "revolved"}:
            return None
        cut: dict[str, Any] = {
            "cut_kind": cut_kind,
            "cutter_part": str(raw_cut.get("cutter_part") or ""),
        }
        if "profile_points" in raw_cut:
            try:
                profile_points = [
                    [float(point[0]), float(point[1])]
                    for point in raw_cut["profile_points"]
                ]
            except (TypeError, ValueError, IndexError):
                return None
            if len(profile_points) < 3:
                return None
            cut["profile_points"] = profile_points
            with suppress(TypeError, ValueError):
                cut["bevel_width"] = max(0.0, float(raw_cut.get("bevel_width") or 0.0))
        elif "rings" in raw_cut:
            try:
                rings = [
                    [float(ring[0]), float(ring[1])]
                    for ring in raw_cut["rings"]
                ]
            except (TypeError, ValueError, IndexError):
                return None
            if len(rings) < 2 or any(float(radius) <= 0.0 for _, radius in rings):
                return None
            if "plane_center" in raw_cut:
                try:
                    plane_center = [
                        float(raw_cut["plane_center"][0]),
                        float(raw_cut["plane_center"][1]),
                    ]
                except (TypeError, ValueError, IndexError):
                    return None
            else:
                try:
                    center = np.asarray(raw_cut["center"], dtype=np.float64)
                except (KeyError, TypeError, ValueError):
                    return None
                if center.shape != (3,):
                    return None
                plane_center = [
                    float(center[plane_axes[0]]),
                    float(center[plane_axes[1]]),
                ]
            cut["plane_center"] = plane_center
            cut["rings"] = rings
            if raw_cut.get("style") is not None:
                cut["style"] = str(raw_cut.get("style") or "")
        else:
            return None
        through_cuts.append(cut)
    return through_cuts


def _exact_profile_cut_state_box_boss_union_ordered(
    base: trimesh.Trimesh,
    boss_mesh: trimesh.Trimesh,
) -> trimesh.Trimesh | None:
    state = _profile_cut_state_from_mesh(base)
    base_bounds = _box_bounds_from_metadata(base)
    if state is None or base_bounds is None:
        return None
    try:
        from shapely.geometry import Polygon

        cut_axis = int(state["cut_axis"])
        plane_axes = tuple(int(value) for value in state["plane_axes"])
        state_min = np.asarray(state["box_min"], dtype=np.float64)
        state_max = np.asarray(state["box_max"], dtype=np.float64)
    except (ImportError, ModuleNotFoundError, KeyError, TypeError, ValueError):
        return None
    if cut_axis not in {0, 1, 2}:
        return None
    if len(plane_axes) != 2 or set(plane_axes) != ({0, 1, 2} - {cut_axis}):
        return None
    box_min, box_max = base_bounds
    if (
        state_min.shape != (3,)
        or state_max.shape != (3,)
        or bool(np.any(np.abs(state_min - box_min) > 1e-6))
        or bool(np.any(np.abs(state_max - box_max) > 1e-6))
    ):
        return None
    through_cuts = _through_cuts_from_profile_cut_state(
        state,
        plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
    )
    if through_cuts is None:
        return None
    base_surface = Polygon(
        (
            (float(box_min[plane_axes[0]]), float(box_min[plane_axes[1]])),
            (float(box_max[plane_axes[0]]), float(box_min[plane_axes[1]])),
            (float(box_max[plane_axes[0]]), float(box_max[plane_axes[1]])),
            (float(box_min[plane_axes[0]]), float(box_max[plane_axes[1]])),
        )
    )
    if base_surface.is_empty or float(base_surface.area) <= 1e-9:
        return None
    matches: list[tuple[int, dict[str, Any]]] = []
    for side in (1, -1):
        attach_axial = float(box_max[cut_axis] if side > 0 else box_min[cut_axis])
        record = _boss_record_for_attachment_surface(
            boss_mesh,
            attach_axial=attach_axial,
            surface_footprint=base_surface,
            cut_axis=cut_axis,
            plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
            side=side,
        )
        if record is not None:
            matches.append((int(side), record))
    if len(matches) != 1:
        return None
    side, boss = matches[0]
    built = _mesh_from_box_cylinder_bosses(
        box_min=box_min,
        box_max=box_max,
        cut_axis=cut_axis,
        plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
        side=side,
        bosses=[boss],
        through_cuts=through_cuts,
    )
    if built is None:
        return None
    result, stats = built
    boss_state_payload = {
        "schema": "lathe.geometry.reference_boss_state.v1",
        "box_min": [float(value) for value in box_min],
        "box_max": [float(value) for value in box_max],
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "side": int(side),
        "bosses": [boss],
        "through_cuts": through_cuts,
    }
    result.metadata[_BOSS_STATE_METADATA_KEY] = boss_state_payload
    boss_source_kind = str(boss.get("source_kind") or "")
    method = (
        "axis_aligned_profile_cut_state_box_cylinder_boss_union_v1"
        if boss_source_kind == "cylinder"
        else "axis_aligned_profile_cut_state_box_profile_boss_union_v1"
    )
    result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_exact_boolean.v1",
        "method": method,
        "op": "union",
        "overlap": True,
        "passthrough": False,
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "side": int(side),
        "boss_part": str(boss.get("part") or "boss"),
        "boss_count": 1,
        "boss_styles": [str(boss.get("style") or "")],
        "boss_source_kinds": [boss_source_kind],
        "profile_cut_state_consumed": True,
        "through_cut_count": len(through_cuts),
        "through_cut_kinds": sorted({str(cut.get("cut_kind") or "") for cut in through_cuts}),
        **stats,
    }
    _set_batch_source_meshes(result, (result,))
    return result


def _exact_axis_aligned_box_cylinder_boss_union_ordered(
    base: trimesh.Trimesh,
    boss_mesh: trimesh.Trimesh,
) -> trimesh.Trimesh | None:
    cylinder = _cylinder_metadata(boss_mesh)
    revolved_profile = None if cylinder is not None else _revolved_profile_metadata(boss_mesh)
    base_bounds = _box_bounds_from_metadata(base)
    if base_bounds is None or (cylinder is None and revolved_profile is None):
        return None

    amin, amax = base_bounds
    eps = 1e-7
    profile_cut_state = _profile_cut_state_from_mesh(base)
    if profile_cut_state is not None:
        return _exact_profile_cut_state_box_boss_union_ordered(base, boss_mesh)
    previous_state = _boss_state_from_mesh(base)
    if previous_state is not None:
        attached = _boss_record_for_existing_boss_state(
            boss_state=previous_state,
            boss_mesh=boss_mesh,
        )
        if attached is not None:
            cut_axis, plane_axes, side, new_boss = attached
            try:
                bosses = [
                    dict(item)
                    for item in previous_state.get("bosses", [])
                    if isinstance(item, dict)
                ]
            except (AttributeError, TypeError):
                return None
            if len(bosses) != len(previous_state.get("bosses", [])):
                return None
            bosses.append(new_boss)
            through_cuts = _boss_state_through_cuts(previous_state)
            if through_cuts is None:
                return None
            built = _mesh_from_box_cylinder_bosses(
                box_min=amin,
                box_max=amax,
                cut_axis=cut_axis,
                plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
                side=side,
                bosses=bosses,
                through_cuts=through_cuts,
            )
            if built is None:
                return None
            result, stats = built
            boss_state_payload = {
                "schema": "lathe.geometry.reference_boss_state.v1",
                "box_min": [float(value) for value in amin],
                "box_max": [float(value) for value in amax],
                "cut_axis": int(cut_axis),
                "plane_axes": [int(axis) for axis in plane_axes],
                "side": int(side),
                "bosses": bosses,
            }
            if through_cuts:
                boss_state_payload["through_cuts"] = through_cuts
            result.metadata[_BOSS_STATE_METADATA_KEY] = boss_state_payload
            part = str(new_boss.get("part") or "boss")
            method = "axis_aligned_box_nested_boss_union_v1"
            result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
                "schema": "lathe.geometry.reference_exact_boolean.v1",
                "method": method,
                "op": "union",
                "overlap": True,
                "passthrough": False,
                "cut_axis": int(cut_axis),
                "plane_axes": [int(axis) for axis in plane_axes],
                "side": int(side),
                "boss_part": part,
                "boss_count": len(bosses),
                "boss_styles": sorted({str(item.get("style") or "") for item in bosses}),
                "boss_source_kinds": sorted({str(item.get("source_kind") or "") for item in bosses}),
                **stats,
            }
            _set_batch_source_meshes(result, (result,))
            return result

    if cylinder is not None:
        axis = str(cylinder["axis"])
        cut_axis = {"x": 0, "y": 1, "z": 2}[axis]
        plane_axes = tuple(index for index in range(3) if index != cut_axis)
        center = np.asarray(cylinder["center"], dtype=np.float64)
        radius = float(cylinder["radius"])
        half_height = float(cylinder["height"]) * 0.5
        cyl_min = float(center[cut_axis] - half_height)
        cyl_max = float(center[cut_axis] + half_height)
        positive_side = (
            cyl_min <= float(amax[cut_axis]) + eps
            and cyl_max > float(amax[cut_axis]) + eps
            and cyl_min >= float(amin[cut_axis]) - eps
        )
        negative_side = (
            cyl_max >= float(amin[cut_axis]) - eps
            and cyl_min < float(amin[cut_axis]) - eps
            and cyl_max <= float(amax[cut_axis]) + eps
        )
        if positive_side == negative_side:
            return None

        side = 1 if positive_side else -1
        outer_axial = cyl_max if side > 0 else cyl_min
        base_axial = float(amax[cut_axis] if side > 0 else amin[cut_axis])
        bevel_width = max(0.0, float(cylinder.get("bevel_width_cm") or 0.0))
        if bevel_width > 1e-9:
            depth = min(bevel_width, abs(outer_axial - base_axial) * 0.45)
            cap_radius = max(radius - bevel_width, radius * 0.20)
            inner_axial = outer_axial - (side * depth)
            rings = [
                (base_axial, radius),
                (inner_axial, radius),
                (outer_axial, cap_radius),
            ]
            style = "beveled_cylinder_boss"
            method_prefix = "beveled_cylinder_boss"
        else:
            rings = [(base_axial, radius), (outer_axial, radius)]
            style = "cylinder_boss"
            method_prefix = "cylinder_boss"
        part = str(cylinder.get("part") or "cylinder")
        source_kind = "cylinder"
    else:
        assert revolved_profile is not None
        axis = str(revolved_profile["axis"])
        cut_axis = {"x": 0, "y": 1, "z": 2}[axis]
        plane_axes = tuple(index for index in range(3) if index != cut_axis)
        center = np.asarray(revolved_profile["center"], dtype=np.float64)
        world_profile = [
            (float(center[cut_axis] + axial), float(radius))
            for axial, radius in sorted(revolved_profile["profile_points"], key=lambda item: item[0])
        ]
        if len(world_profile) < 2 or any(radius <= 0.0 for _, radius in world_profile):
            return None
        positive_side = (
            world_profile[0][0] <= float(amax[cut_axis]) + eps
            and world_profile[-1][0] > float(amax[cut_axis]) + eps
            and world_profile[0][0] >= float(amin[cut_axis]) - eps
        )
        negative_side = (
            world_profile[-1][0] >= float(amin[cut_axis]) - eps
            and world_profile[0][0] < float(amin[cut_axis]) - eps
            and world_profile[-1][0] <= float(amax[cut_axis]) + eps
        )
        if positive_side == negative_side:
            return None
        side = 1 if positive_side else -1
        base_axial = float(amax[cut_axis] if side > 0 else amin[cut_axis])
        outer_axial = float(world_profile[-1][0] if side > 0 else world_profile[0][0])
        base_radius = _radius_at_profile_axial(world_profile, base_axial)
        if base_radius is None:
            return None
        if side > 0:
            rings = [(base_axial, base_radius)]
            rings.extend((axial, radius) for axial, radius in world_profile if axial > base_axial + 1e-9)
        else:
            rings = [(base_axial, base_radius)]
            rings.extend((axial, radius) for axial, radius in reversed(world_profile) if axial < base_axial - 1e-9)
        if len(rings) < 2 or abs(float(rings[-1][0]) - outer_axial) > 1e-7:
            return None
        profile_style = str(revolved_profile.get("style") or "profile")
        style = f"revolved_profile_boss:{profile_style}"
        method_prefix = "revolved_profile_boss"
        part = str(revolved_profile.get("part") or "revolved_profile")
        source_kind = "revolved_profile"

    plane_center = np.asarray((center[plane_axes[0]], center[plane_axes[1]]), dtype=np.float64)
    radius = float(max(value for _, value in rings))
    new_boss = {
        "center": [float(value) for value in center],
        "plane_center": [float(value) for value in plane_center],
        "radius": radius,
        "base_axial": base_axial,
        "outer_axial": outer_axial,
        "rings": [[float(axial), float(value)] for axial, value in rings],
        "style": style,
        "source_kind": source_kind,
        "part": part,
    }

    if previous_state is not None:
        try:
            state_cut_axis = int(previous_state["cut_axis"])
            state_plane_axes = tuple(int(value) for value in previous_state["plane_axes"])
            state_side = int(previous_state["side"])
        except (KeyError, TypeError, ValueError):
            return None
        if state_cut_axis != cut_axis or state_plane_axes != plane_axes or state_side != side:
            return None
        bosses = [
            dict(item)
            for item in previous_state.get("bosses", [])
            if isinstance(item, dict)
        ]
        if len(bosses) != len(previous_state.get("bosses", [])):
            return None
        existing_kinds = {str(item.get("source_kind") or "cylinder") for item in bosses}
        if existing_kinds == {"cylinder"} and method_prefix == "cylinder_boss":
            method = "axis_aligned_box_repeated_cylinder_boss_union_v1"
        else:
            method = "axis_aligned_box_repeated_profile_boss_union_v1"
    else:
        bosses = []
        if method_prefix == "cylinder_boss":
            method = "axis_aligned_box_cylinder_boss_union_v1"
        elif method_prefix == "beveled_cylinder_boss":
            method = "axis_aligned_box_beveled_cylinder_boss_union_v1"
        else:
            method = "axis_aligned_box_revolved_profile_boss_union_v1"

    through_cuts = []
    if previous_state is not None:
        through_cuts = _boss_state_through_cuts(previous_state)
        if through_cuts is None:
            return None
    bosses.append(new_boss)
    built = _mesh_from_box_cylinder_bosses(
        box_min=amin,
        box_max=amax,
        cut_axis=cut_axis,
        plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
        side=side,
        bosses=bosses,
        through_cuts=through_cuts,
    )
    if built is None:
        return None
    result, stats = built
    boss_state_payload = {
        "schema": "lathe.geometry.reference_boss_state.v1",
        "box_min": [float(value) for value in amin],
        "box_max": [float(value) for value in amax],
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "side": int(side),
        "bosses": bosses,
    }
    if through_cuts:
        boss_state_payload["through_cuts"] = through_cuts
    result.metadata[_BOSS_STATE_METADATA_KEY] = boss_state_payload
    result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_exact_boolean.v1",
        "method": method,
        "op": "union",
        "overlap": True,
        "passthrough": False,
        "cut_axis": int(cut_axis),
        "plane_axes": [int(axis) for axis in plane_axes],
        "side": int(side),
        "boss_part": part,
        "boss_count": len(bosses),
        "boss_styles": sorted({str(item.get("style") or "") for item in bosses}),
        "boss_source_kinds": sorted({str(item.get("source_kind") or "") for item in bosses}),
        **stats,
    }
    _set_batch_source_meshes(result, (result,))
    return result


def _exact_axis_aligned_box_cylinder_boss_union(
    a: trimesh.Trimesh,
    b: trimesh.Trimesh,
) -> trimesh.Trimesh | None:
    ordered = _exact_axis_aligned_box_cylinder_boss_union_ordered(a, b)
    if ordered is not None:
        return ordered
    return _exact_axis_aligned_box_cylinder_boss_union_ordered(b, a)


def _profile_holes_from_profile_cut_state_detail(
    detail_mesh: trimesh.Trimesh,
    *,
    detail_bounds: tuple[np.ndarray, np.ndarray],
    cut_axis: int,
    plane_axes: tuple[int, int],
    sections: int = 48,
) -> list[list[list[float]]] | None:
    state = _profile_cut_state_from_mesh(detail_mesh)
    if state is None:
        return []
    try:
        from shapely.geometry import Polygon
        from shapely.ops import unary_union

        state_cut_axis = int(state["cut_axis"])
        state_plane_axes = tuple(int(value) for value in state["plane_axes"])
        state_min = np.asarray(state["box_min"], dtype=np.float64)
        state_max = np.asarray(state["box_max"], dtype=np.float64)
    except (ImportError, ModuleNotFoundError, KeyError, TypeError, ValueError):
        return None
    if state_cut_axis != cut_axis or state_plane_axes != (int(plane_axes[0]), int(plane_axes[1])):
        return None
    detail_min, detail_max = detail_bounds
    if (
        state_min.shape != (3,)
        or state_max.shape != (3,)
        or bool(np.any(np.abs(state_min - detail_min) > 1e-6))
        or bool(np.any(np.abs(state_max - detail_max) > 1e-6))
    ):
        return None
    rect = Polygon(
        (
            (float(detail_min[plane_axes[0]]), float(detail_min[plane_axes[1]])),
            (float(detail_max[plane_axes[0]]), float(detail_min[plane_axes[1]])),
            (float(detail_max[plane_axes[0]]), float(detail_max[plane_axes[1]])),
            (float(detail_min[plane_axes[0]]), float(detail_max[plane_axes[1]])),
        )
    )
    holes: list[list[list[float]]] = []
    hole_polygons = []
    for cut in state.get("cuts", []):
        if not isinstance(cut, dict):
            return None
        if "profile_points" in cut:
            try:
                points = [
                    (float(point[0]), float(point[1]))
                    for point in cut["profile_points"]
                ]
            except (TypeError, ValueError, IndexError):
                return None
            if len(points) < 3:
                return None
            polygon = Polygon(points)
        else:
            try:
                if "rings" in cut:
                    center = np.asarray(cut["center"], dtype=np.float64)
                    rings = [
                        (float(ring[0]), float(ring[1]))
                        for ring in cut["rings"]
                    ]
                    radius = float(max(value for _, value in rings))
                    plane_center = np.asarray((center[plane_axes[0]], center[plane_axes[1]]), dtype=np.float64)
                else:
                    plane_center = np.asarray(cut["plane_center"], dtype=np.float64)
                    radius = float(cut["radius"])
            except (KeyError, TypeError, ValueError, IndexError):
                return None
            if plane_center.shape != (2,) or radius <= 0.0:
                return None
            polygon = Polygon(_circle_points(plane_center, radius, sections=sections))
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        if polygon.is_empty or float(polygon.area) <= 1e-9 or not rect.contains(polygon):
            return None
        ring = [
            [float(x), float(y)]
            for x, y in list(polygon.exterior.coords)[:-1]
        ]
        if len(ring) < 3:
            return None
        holes.append(ring)
        hole_polygons.append(polygon)
    if hole_polygons:
        union = unary_union(hole_polygons)
        area_sum = sum(float(polygon.area) for polygon in hole_polygons)
        tolerance = max(1e-6, abs(area_sum) * 1e-7)
        if union.is_empty or abs(float(union.area) - area_sum) > tolerance:
            return None
    return holes


def _raised_box_detail_for_base(
    *,
    base_bounds: tuple[np.ndarray, np.ndarray],
    detail_bounds: tuple[np.ndarray, np.ndarray],
    detail_mesh: trimesh.Trimesh | None = None,
) -> tuple[int, tuple[int, int], int, dict[str, Any]] | None:
    base_min, base_max = base_bounds
    detail_min, detail_max = detail_bounds
    if bool(np.any(detail_max <= detail_min)):
        return None
    raw_detail_metadata = _shape_primitive_metadata(detail_mesh) if detail_mesh is not None else {}
    resolved_detail_metadata = _resolved_shape_primitive_metadata(detail_mesh) if detail_mesh is not None else {}
    authored_surface_detail = (
        _shape_metadata_has_any_key(
            raw_detail_metadata,
            {"v2_mount_plate_modifier", "v2_trim_band_modifier"},
        )
        or _shape_metadata_has_any_key(
            resolved_detail_metadata,
            {"v2_mount_plate_modifier", "v2_trim_band_modifier"},
        )
    )
    for cut_axis in range(3):
        plane_axes = tuple(index for index in range(3) if index != cut_axis)
        for side in (1, -1):
            base_axial = float(base_max[cut_axis] if side > 0 else base_min[cut_axis])
            detail_height = float(detail_max[cut_axis] - detail_min[cut_axis])
            seat_fraction = 0.5 if authored_surface_detail else 0.25
            seat_tolerance = max(1e-7, min(0.08, detail_height * seat_fraction))
            if side > 0:
                base_delta = float(detail_min[cut_axis] - base_axial)
                if abs(base_delta) > seat_tolerance:
                    continue
                outer_axial = float(detail_max[cut_axis] - base_delta)
                if outer_axial <= base_axial + 1e-7:
                    continue
            else:
                base_delta = float(detail_max[cut_axis] - base_axial)
                if abs(base_delta) > seat_tolerance:
                    continue
                outer_axial = float(detail_min[cut_axis] - base_delta)
                if outer_axial >= base_axial - 1e-7:
                    continue
            if any(
                detail_min[axis] < base_min[axis] - 1e-7 or detail_max[axis] > base_max[axis] + 1e-7
                for axis in plane_axes
            ):
                continue
            u0 = float(detail_min[plane_axes[0]])
            u1 = float(detail_max[plane_axes[0]])
            v0 = float(detail_min[plane_axes[1]])
            v1 = float(detail_max[plane_axes[1]])
            if u1 <= u0 + 1e-9 or v1 <= v0 + 1e-9:
                return None
            profile_points = [
                [u0, v0],
                [u1, v0],
                [u1, v1],
                [u0, v1],
            ]
            profile_holes: list[list[list[float]]] = []
            primitive: dict[str, Any] = {}
            if detail_mesh is not None:
                raw_primitive = _shape_primitive_metadata(detail_mesh)
                primitive = _resolved_shape_primitive_metadata(detail_mesh)
                profile_holes = _profile_holes_from_profile_cut_state_detail(
                    detail_mesh,
                    detail_bounds=detail_bounds,
                    cut_axis=cut_axis,
                    plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
                )
                if profile_holes is None:
                    return None
                requested_hole_count = max(
                    _requested_profile_hole_count_from_shape_metadata(raw_primitive),
                    _requested_profile_hole_count_from_shape_metadata(primitive),
                )
                if requested_hole_count > 0 and len(profile_holes) < requested_hole_count:
                    return None
                if not profile_holes and len(detail_mesh.faces) > 96:
                    return None
            plane_center = np.asarray(((u0 + u1) * 0.5, (v0 + v1) * 0.5), dtype=np.float64)
            radius = max(u1 - u0, v1 - v0) * 0.5
            rings = [[base_axial, float(max(radius, 1e-6))], [outer_axial, float(max(radius, 1e-6))]]
            style = "rectangular_box_detail"
            profile_rings = None
            bevel_width = 0.0
            if detail_mesh is not None:
                modifier = primitive.get("v2_polybevel_modifier")
                if isinstance(modifier, dict):
                    try:
                        bevel_width = max(0.0, float(modifier.get("width_cm") or 0.0))
                    except (TypeError, ValueError):
                        bevel_width = 0.0
                if bevel_width <= 1e-9:
                    mount_plate_modifier = primitive.get("v2_mount_plate_modifier")
                    if isinstance(mount_plate_modifier, dict):
                        try:
                            bevel_width = max(0.0, float(mount_plate_modifier.get("bevel_width_cm") or 0.0))
                        except (TypeError, ValueError):
                            bevel_width = 0.0
            if bevel_width > 1e-9:
                depth = min(bevel_width, abs(outer_axial - base_axial) * 0.45)
                inset = min(bevel_width, (u1 - u0) * 0.45, (v1 - v0) * 0.45)
                if depth > 1e-9 and inset > 1e-9:
                    cap_u0 = u0 + inset
                    cap_u1 = u1 - inset
                    cap_v0 = v0 + inset
                    cap_v1 = v1 - inset
                    if cap_u1 > cap_u0 + 1e-9 and cap_v1 > cap_v0 + 1e-9:
                        shoulder_axial = outer_axial - side * depth
                        cap_profile = [
                            [cap_u0, cap_v0],
                            [cap_u1, cap_v0],
                            [cap_u1, cap_v1],
                            [cap_u0, cap_v1],
                        ]
                        rings = [
                            [base_axial, float(max(radius, 1e-6))],
                            [float(shoulder_axial), float(max(radius, 1e-6))],
                            [outer_axial, float(max(radius - inset, 1e-6))],
                        ]
                        profile_rings = [profile_points, profile_points, cap_profile]
                        style = "beveled_rectangular_box_detail"
            center = (detail_min + detail_max) * 0.5
            record = {
                "center": [float(value) for value in center],
                "plane_center": [float(value) for value in plane_center],
                "radius": float(max(radius, 1e-6)),
                "base_axial": base_axial,
                "outer_axial": outer_axial,
                "rings": rings,
                "profile_points": profile_points,
                "style": style,
                "source_kind": "box",
                "part": "box_detail",
            }
            if abs(base_delta) > 1e-7:
                record["source_base_axial"] = float(base_axial + base_delta)
                record["seating_snap_cm"] = float(-base_delta)
            if profile_holes:
                record["profile_holes"] = profile_holes
                record["profile_hole_count"] = len(profile_holes)
            if profile_rings is not None:
                record["profile_rings"] = profile_rings
                record["bevel_width_cm"] = float(bevel_width)
            return (
                int(cut_axis),
                (int(plane_axes[0]), int(plane_axes[1])),
                int(side),
                record,
            )
    return None


def _polygon_profile_payload(polygon: Any) -> dict[str, Any] | None:
    if polygon.is_empty or float(polygon.area) <= 1e-9:
        return None
    exterior = [
        [float(x), float(y)]
        for x, y in list(polygon.exterior.coords)[:-1]
    ]
    if len(exterior) < 3:
        return None
    holes: list[list[list[float]]] = []
    for interior in polygon.interiors:
        ring = [
            [float(x), float(y)]
            for x, y in list(interior.coords)[:-1]
        ]
        if len(ring) >= 3:
            holes.append(ring)
    return {
        "profile_points": exterior,
        **({"profile_holes": holes} if holes else {}),
    }


def _merge_rectangular_box_detail_bosses(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(records) < 2:
        return records
    try:
        from shapely.geometry import Polygon
        from shapely.ops import unary_union
    except (ImportError, ModuleNotFoundError):
        return records

    grouped: dict[tuple[float, float], list[dict[str, Any]]] = {}
    passthrough: list[dict[str, Any]] = []
    for record in records:
        style = str(record.get("style") or "")
        if (
            str(record.get("source_kind") or "") != "box"
            or style not in {"rectangular_box_detail", "beveled_rectangular_box_detail"}
            or "profile_points" not in record
        ):
            passthrough.append(record)
            continue
        try:
            base_axial = round(float(record["base_axial"]), 7)
            outer_axial = round(float(record["outer_axial"]), 7)
        except (KeyError, TypeError, ValueError):
            passthrough.append(record)
            continue
        grouped.setdefault((base_axial, outer_axial), []).append(record)

    merged: list[dict[str, Any]] = list(passthrough)
    for (base_axial, outer_axial), group in sorted(grouped.items()):
        polygons = []
        for record in group:
            try:
                points = [
                    (float(point[0]), float(point[1]))
                    for point in record["profile_points"]
                ]
            except (TypeError, ValueError, IndexError):
                merged.extend(group)
                break
            polygon = Polygon(points)
            if not polygon.is_valid:
                polygon = polygon.buffer(0)
            if polygon.is_empty or float(polygon.area) <= 1e-9:
                merged.extend(group)
                break
            polygons.append(polygon)
        else:
            union = unary_union(polygons)
            group_has_bevel = any(float(record.get("bevel_width_cm") or 0.0) > 1e-9 for record in group)
            if group_has_bevel and union.geom_type == "MultiPolygon":
                merged.extend(group)
                continue
            parts = [union] if union.geom_type == "Polygon" else list(union.geoms) if union.geom_type == "MultiPolygon" else []
            if not parts:
                merged.extend(group)
                continue
            for index, polygon in enumerate(parts):
                payload = _polygon_profile_payload(polygon)
                if payload is None:
                    merged.extend(group)
                    break
                minx, miny, maxx, maxy = polygon.bounds
                plane_center = np.asarray(((minx + maxx) * 0.5, (miny + maxy) * 0.5), dtype=np.float64)
                radius = max(float(maxx - minx), float(maxy - miny)) * 0.5
                template = dict(group[0])
                template.update(payload)
                if group_has_bevel:
                    template.pop("profile_rings", None)
                    template.pop("bevel_width_cm", None)
                    template["style"] = "rectangular_box_detail"
                template["plane_center"] = [float(value) for value in plane_center]
                template["radius"] = float(max(radius, 1e-6))
                template["base_axial"] = float(base_axial)
                template["outer_axial"] = float(outer_axial)
                template["rings"] = [
                    [float(base_axial), float(max(radius, 1e-6))],
                    [float(outer_axial), float(max(radius, 1e-6))],
                ]
                template["part"] = "merged_box_detail" if len(parts) == 1 else f"merged_box_detail_{index}"
                template["merged_detail_count"] = len(group)
                template["profile_hole_count"] = len(template.get("profile_holes", []))
                merged.append(template)
            else:
                continue
    return merged


def _boss_footprint_from_record(record: dict[str, Any], *, sections: int = 48) -> Any | None:
    try:
        from shapely.geometry import Polygon
    except (ImportError, ModuleNotFoundError):
        return None
    if "profile_rings" in record:
        try:
            raw_rings = record["profile_rings"]
            points = [
                (float(point[0]), float(point[1]))
                for point in raw_rings[-1]
            ]
            holes = [
                [
                    (float(point[0]), float(point[1]))
                    for point in hole
                ]
                for hole in record.get("profile_holes", [])
            ]
        except (TypeError, ValueError, IndexError):
            return None
        if len(points) < 3 or any(len(hole) < 3 for hole in holes):
            return None
        polygon = Polygon(points, holes)
    elif "profile_points" in record:
        try:
            points = [
                (float(point[0]), float(point[1]))
                for point in record["profile_points"]
            ]
            holes = [
                [
                    (float(point[0]), float(point[1]))
                    for point in hole
                ]
                for hole in record.get("profile_holes", [])
            ]
        except (TypeError, ValueError, IndexError):
            return None
        if len(points) < 3:
            return None
        polygon = Polygon(points, holes)
    else:
        try:
            plane_center = np.asarray(record["plane_center"], dtype=np.float64)
            radius = float(record["radius"])
        except (KeyError, TypeError, ValueError):
            return None
        if plane_center.shape != (2,) or radius <= 0.0:
            return None
        polygon = Polygon(_circle_points(plane_center, radius, sections=sections))
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    if polygon.is_empty or float(polygon.area) <= 1e-9:
        return None
    return polygon


def _boss_record_for_attachment_surface(
    boss_mesh: trimesh.Trimesh,
    *,
    attach_axial: float,
    surface_footprint: Any,
    cut_axis: int,
    plane_axes: tuple[int, int],
    side: int,
) -> dict[str, Any] | None:
    cylinder = _cylinder_metadata(boss_mesh)
    revolved_profile = None if cylinder is not None else _revolved_profile_metadata(boss_mesh)
    if cylinder is None and revolved_profile is None:
        return None
    eps = 1e-6
    if cylinder is not None:
        axis = str(cylinder["axis"])
        if {"x": 0, "y": 1, "z": 2}[axis] != cut_axis:
            return None
        center = np.asarray(cylinder["center"], dtype=np.float64)
        radius = float(cylinder["radius"])
        half_height = float(cylinder["height"]) * 0.5
        low = float(center[cut_axis] - half_height)
        high = float(center[cut_axis] + half_height)
        height = float(high - low)
        seat_tolerance = max(eps, min(0.08, height * 0.25))
        if side > 0:
            base_delta = low - float(attach_axial)
            if abs(base_delta) > seat_tolerance or high <= low + eps:
                return None
            outer_axial = high - base_delta
        else:
            base_delta = high - float(attach_axial)
            if abs(base_delta) > seat_tolerance or low >= high - eps:
                return None
            outer_axial = low - base_delta
        bevel_width = max(0.0, float(cylinder.get("bevel_width_cm") or 0.0))
        if bevel_width > 1e-9:
            depth = min(bevel_width, abs(outer_axial - attach_axial) * 0.45)
            cap_radius = max(radius - bevel_width, radius * 0.20)
            inner_axial = outer_axial - (side * depth)
            rings = [
                (attach_axial, radius),
                (inner_axial, radius),
                (outer_axial, cap_radius),
            ]
            style = "beveled_cylinder_boss"
        else:
            rings = [(attach_axial, radius), (outer_axial, radius)]
            style = "cylinder_boss"
        part = str(cylinder.get("part") or "cylinder")
        source_kind = "cylinder"
    else:
        assert revolved_profile is not None
        axis = str(revolved_profile["axis"])
        if {"x": 0, "y": 1, "z": 2}[axis] != cut_axis:
            return None
        center = np.asarray(revolved_profile["center"], dtype=np.float64)
        world_profile = [
            (float(center[cut_axis] + axial), float(radius))
            for axial, radius in sorted(revolved_profile["profile_points"], key=lambda item: item[0])
        ]
        if len(world_profile) < 2 or any(radius <= 0.0 for _, radius in world_profile):
            return None
        profile_low = float(world_profile[0][0])
        profile_high = float(world_profile[-1][0])
        profile_height = abs(profile_high - profile_low)
        seat_tolerance = max(eps, min(0.08, profile_height * 0.25))
        if side > 0:
            source_base_axial = profile_low
            base_delta = source_base_axial - float(attach_axial)
            if abs(base_delta) > seat_tolerance or profile_high <= source_base_axial + eps:
                return None
            axial_shift = float(attach_axial) - source_base_axial
            outer_axial = float(profile_high + axial_shift)
            base_radius = _radius_at_profile_axial(world_profile, source_base_axial)
            if base_radius is None:
                return None
            rings = [(attach_axial, base_radius)]
            rings.extend(
                (float(axial + axial_shift), radius)
                for axial, radius in world_profile
                if axial > source_base_axial + 1e-9
            )
        else:
            source_base_axial = profile_high
            base_delta = source_base_axial - float(attach_axial)
            if abs(base_delta) > seat_tolerance or profile_low >= source_base_axial - eps:
                return None
            axial_shift = float(attach_axial) - source_base_axial
            outer_axial = float(profile_low + axial_shift)
            base_radius = _radius_at_profile_axial(world_profile, source_base_axial)
            if base_radius is None:
                return None
            rings = [(attach_axial, base_radius)]
            rings.extend(
                (float(axial + axial_shift), radius)
                for axial, radius in reversed(world_profile)
                if axial < source_base_axial - 1e-9
            )
        if len(rings) < 2 or abs(float(rings[-1][0]) - outer_axial) > 1e-7:
            return None
        profile_style = str(revolved_profile.get("style") or "profile")
        style = f"revolved_profile_boss:{profile_style}"
        part = str(revolved_profile.get("part") or "revolved_profile")
        source_kind = "revolved_profile"

    plane_center = np.asarray((center[plane_axes[0]], center[plane_axes[1]]), dtype=np.float64)
    radius = float(max(value for _, value in rings))
    record = {
        "center": [float(value) for value in center],
        "plane_center": [float(value) for value in plane_center],
        "radius": radius,
        "base_axial": float(attach_axial),
        "outer_axial": float(outer_axial),
        "rings": [[float(axial), float(value)] for axial, value in rings],
        "style": style,
        "source_kind": source_kind,
        "part": part,
    }
    if abs(base_delta) > eps:
        record["source_base_axial"] = float(attach_axial + base_delta)
        record["seating_snap_cm"] = float(-base_delta)
    footprint = _boss_footprint_from_record(record)
    if footprint is None or not surface_footprint.covers(footprint):
        return None
    return record


def _boss_records_for_attachment_surfaces(
    *,
    base_bounds: tuple[np.ndarray, np.ndarray],
    detail_records: list[dict[str, Any]],
    boss_meshes: list[trimesh.Trimesh],
    cut_axis: int,
    plane_axes: tuple[int, int],
    side: int,
) -> list[dict[str, Any]] | None:
    if not boss_meshes:
        return []
    try:
        from shapely.geometry import Polygon
    except (ImportError, ModuleNotFoundError):
        return None
    base_min, base_max = base_bounds
    base_axial = float(base_max[cut_axis] if side > 0 else base_min[cut_axis])
    base_surface = Polygon(
        (
            (float(base_min[plane_axes[0]]), float(base_min[plane_axes[1]])),
            (float(base_max[plane_axes[0]]), float(base_min[plane_axes[1]])),
            (float(base_max[plane_axes[0]]), float(base_max[plane_axes[1]])),
            (float(base_min[plane_axes[0]]), float(base_max[plane_axes[1]])),
        )
    )
    surfaces: list[tuple[float, Any]] = [(base_axial, base_surface)]
    for detail in detail_records:
        footprint = _boss_footprint_from_record(detail)
        if footprint is None:
            return None
        try:
            surfaces.append((float(detail["outer_axial"]), footprint))
        except (KeyError, TypeError, ValueError):
            return None

    records: list[dict[str, Any]] = []
    for boss_mesh in boss_meshes:
        matches: list[dict[str, Any]] = []
        for attach_axial, surface_footprint in surfaces:
            record = _boss_record_for_attachment_surface(
                boss_mesh,
                attach_axial=attach_axial,
                surface_footprint=surface_footprint,
                cut_axis=cut_axis,
                plane_axes=plane_axes,
                side=side,
            )
            if record is not None:
                matches.append(record)
        if len(matches) != 1:
            return None
        records.append(matches[0])
    return records


def _boss_record_for_existing_boss_state(
    *,
    boss_state: dict[str, Any],
    boss_mesh: trimesh.Trimesh,
) -> tuple[int, tuple[int, int], int, dict[str, Any]] | None:
    try:
        from shapely.geometry import Polygon
        cut_axis = int(boss_state["cut_axis"])
        plane_axes = tuple(int(value) for value in boss_state["plane_axes"])
        side = int(boss_state["side"])
        box_min = np.asarray(boss_state["box_min"], dtype=np.float64)
        box_max = np.asarray(boss_state["box_max"], dtype=np.float64)
    except (ImportError, ModuleNotFoundError, KeyError, TypeError, ValueError):
        return None
    if box_min.shape != (3,) or box_max.shape != (3,) or cut_axis not in {0, 1, 2}:
        return None
    if len(plane_axes) != 2 or set(plane_axes) != ({0, 1, 2} - {cut_axis}) or side not in {-1, 1}:
        return None
    base_axial = float(box_max[cut_axis] if side > 0 else box_min[cut_axis])
    base_surface = Polygon(
        (
            (float(box_min[plane_axes[0]]), float(box_min[plane_axes[1]])),
            (float(box_max[plane_axes[0]]), float(box_min[plane_axes[1]])),
            (float(box_max[plane_axes[0]]), float(box_max[plane_axes[1]])),
            (float(box_min[plane_axes[0]]), float(box_max[plane_axes[1]])),
        )
    )
    surfaces: list[tuple[float, Any]] = [(base_axial, base_surface)]
    bosses = boss_state.get("bosses", [])
    if not isinstance(bosses, list):
        return None
    for boss in bosses:
        if not isinstance(boss, dict):
            return None
        footprint = _boss_footprint_from_record(boss)
        if footprint is None:
            return None
        try:
            surfaces.append((float(boss["outer_axial"]), footprint))
        except (KeyError, TypeError, ValueError):
            return None

    matches: list[dict[str, Any]] = []
    for attach_axial, surface_footprint in surfaces:
        record = _boss_record_for_attachment_surface(
            boss_mesh,
            attach_axial=attach_axial,
            surface_footprint=surface_footprint,
            cut_axis=cut_axis,
            plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
            side=side,
        )
        if record is not None:
            matches.append(record)
    if len(matches) != 1:
        return None
    return int(cut_axis), (int(plane_axes[0]), int(plane_axes[1])), int(side), matches[0]


def _boss_records_for_base_mesh(
    *,
    base_mesh: trimesh.Trimesh,
    boss_meshes: list[trimesh.Trimesh],
) -> tuple[int, tuple[int, int], int, list[dict[str, Any]]] | None:
    records: list[dict[str, Any]] = []
    cut_axis: int | None = None
    plane_axes: tuple[int, int] | None = None
    side: int | None = None
    for boss_mesh in boss_meshes:
        result = _exact_axis_aligned_box_cylinder_boss_union_ordered(base_mesh, boss_mesh)
        if result is None:
            return None
        state = _boss_state_from_mesh(result)
        if state is None:
            return None
        try:
            item_cut_axis = int(state["cut_axis"])
            item_plane_axes = tuple(int(value) for value in state["plane_axes"])
            item_side = int(state["side"])
        except (KeyError, TypeError, ValueError):
            return None
        bosses = [dict(item) for item in state.get("bosses", []) if isinstance(item, dict)]
        if len(bosses) != 1:
            return None
        if cut_axis is None:
            cut_axis = item_cut_axis
            plane_axes = (int(item_plane_axes[0]), int(item_plane_axes[1]))
            side = item_side
        elif cut_axis != item_cut_axis or plane_axes != item_plane_axes or side != item_side:
            return None
        records.append(bosses[0])
    if cut_axis is None or plane_axes is None or side is None:
        return None
    return int(cut_axis), (int(plane_axes[0]), int(plane_axes[1])), int(side), records


def _exact_axis_aligned_box_detail_boss_batch_union(meshes: list[trimesh.Trimesh]) -> trimesh.Trimesh | None:
    box_entries: list[tuple[int, tuple[np.ndarray, np.ndarray]]] = []
    boss_entries: list[tuple[int, trimesh.Trimesh]] = []
    for index, mesh in enumerate(meshes):
        if _boss_state_from_mesh(mesh) is not None:
            return None
        bounds = _box_bounds_from_metadata(mesh)
        if bounds is not None:
            box_entries.append((index, bounds))
            continue
        if _cylinder_metadata(mesh) is not None or _revolved_profile_metadata(mesh) is not None:
            boss_entries.append((index, mesh))
            continue
        return None
    if len(box_entries) < 2:
        return None

    def volume(bounds: tuple[np.ndarray, np.ndarray]) -> float:
        return float(np.prod(bounds[1] - bounds[0]))

    for base_index, base_bounds in sorted(box_entries, key=lambda item: volume(item[1]), reverse=True):
        boss_records: list[dict[str, Any]] = []
        cut_axis: int | None = None
        plane_axes: tuple[int, int] | None = None
        side: int | None = None
        detail_records: list[dict[str, Any]] = []
        for detail_index, detail_bounds in box_entries:
            if detail_index == base_index:
                continue
            detail = _raised_box_detail_for_base(
                base_bounds=base_bounds,
                detail_bounds=detail_bounds,
                detail_mesh=meshes[detail_index],
            )
            if detail is None:
                break
            detail_cut_axis, detail_plane_axes, detail_side, detail_record = detail
            if cut_axis is None:
                cut_axis = detail_cut_axis
                plane_axes = detail_plane_axes
                side = detail_side
            elif detail_cut_axis != cut_axis or detail_plane_axes != plane_axes or detail_side != side:
                break
            detail_record["part"] = f"box_detail_{detail_index}"
            detail_records.append(detail_record)
        else:
            if cut_axis is None or plane_axes is None or side is None:
                continue
            detail_records = _merge_rectangular_box_detail_bosses(detail_records)
            through_cuts: list[dict[str, Any]] = []
            base_profile_state = _profile_cut_state_from_mesh(meshes[base_index])
            if base_profile_state is not None:
                try:
                    state_cut_axis = int(base_profile_state["cut_axis"])
                    state_plane_axes = tuple(int(value) for value in base_profile_state["plane_axes"])
                except (KeyError, TypeError, ValueError):
                    continue
                if state_cut_axis != int(cut_axis) or state_plane_axes != (
                    int(plane_axes[0]),
                    int(plane_axes[1]),
                ):
                    continue
                state_through_cuts = _through_cuts_from_profile_cut_state(
                    base_profile_state,
                    plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
                )
                if state_through_cuts is None:
                    continue
                through_cuts = state_through_cuts
            if boss_entries:
                boss_records = _boss_records_for_attachment_surfaces(
                    base_bounds=base_bounds,
                    detail_records=detail_records,
                    boss_meshes=[mesh for _, mesh in boss_entries],
                    cut_axis=int(cut_axis),
                    plane_axes=(int(plane_axes[0]), int(plane_axes[1])),
                    side=int(side),
                )
                if boss_records is None:
                    continue
            bosses = [*detail_records, *boss_records]
            if not bosses:
                continue
            if (
                not boss_records
                and not through_cuts
                and any(detail.get("profile_holes") for detail in detail_records)
            ):
                built = _mesh_from_box_blind_profile_cuts_with_raised_details(
                    box_min=base_bounds[0],
                    box_max=base_bounds[1],
                    cut_axis=cut_axis,
                    plane_axes=plane_axes,
                    cuts=[],
                    details=detail_records,
                )
            else:
                built = _mesh_from_box_cylinder_bosses(
                    box_min=base_bounds[0],
                    box_max=base_bounds[1],
                    cut_axis=cut_axis,
                    plane_axes=plane_axes,
                    side=side,
                    bosses=bosses,
                    through_cuts=through_cuts,
                )
            if built is None:
                continue
            result, stats = built
            if not bool(result.is_watertight):
                continue
            boss_source_kinds = sorted({str(item.get("source_kind") or "") for item in bosses})
            boss_styles = sorted({str(item.get("style") or "") for item in bosses})
            boss_state_payload = {
                "schema": "lathe.geometry.reference_boss_state.v1",
                "box_min": [float(value) for value in base_bounds[0]],
                "box_max": [float(value) for value in base_bounds[1]],
                "cut_axis": int(cut_axis),
                "plane_axes": [int(axis) for axis in plane_axes],
                "side": int(side),
                "bosses": bosses,
            }
            if through_cuts:
                boss_state_payload["through_cuts"] = through_cuts
            result.metadata[_BOSS_STATE_METADATA_KEY] = boss_state_payload
            method = (
                "axis_aligned_profile_cut_state_box_detail_boss_batch_union_v1"
                if through_cuts
                else "axis_aligned_box_detail_boss_batch_union_v1"
            )
            through_cut_metadata = (
                {
                    "through_cut_count": len(through_cuts),
                    "through_cut_kinds": sorted({str(cut.get("cut_kind") or "") for cut in through_cuts}),
                }
                if through_cuts
                else {}
            )
            payload = {
                "schema": "lathe.geometry.reference_exact_boolean.v1",
                "method": method,
                "op": "batch_union",
                "operand_count": len(meshes),
                "base_box_operand_index": int(base_index),
                "box_detail_count": len(detail_records),
                "boss_count": len(boss_records),
                "additive_detail_count": len(bosses),
                "boss_source_kinds": boss_source_kinds,
                "boss_styles": boss_styles,
                "passthrough": False,
                "result_face_count": len(result.faces),
                "result_watertight": bool(result.is_watertight),
                **through_cut_metadata,
                **stats,
            }
            result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = payload
            result.metadata["lathe_reference_batch_union"] = {
                **payload,
                "schema": "lathe.geometry.reference_batch_union.v1",
            }
            _set_batch_source_meshes(result, (result,))
            return result
    return None


def _exact_axis_aligned_box_cylinder_boss_batch_union(meshes: list[trimesh.Trimesh]) -> trimesh.Trimesh | None:
    base_index: int | None = None
    boss_indices: list[int] = []
    for index, mesh in enumerate(meshes):
        if _cylinder_metadata(mesh) is not None or _revolved_profile_metadata(mesh) is not None:
            boss_indices.append(index)
            continue
        if _box_bounds_from_metadata(mesh) is not None:
            if base_index is not None:
                return None
            base_index = index
            continue
        return None

    if base_index is None or not boss_indices:
        return None
    result = meshes[base_index].copy()
    for index in boss_indices:
        next_result = _exact_axis_aligned_box_cylinder_boss_union_ordered(result, meshes[index])
        if next_result is None:
            return None
        result = next_result

    boss_state = _boss_state_from_mesh(result)
    if boss_state is None:
        return None
    boss_count = len([item for item in boss_state.get("bosses", []) if isinstance(item, dict)])
    boss_source_kinds = sorted(
        {
            str(item.get("source_kind") or "")
            for item in boss_state.get("bosses", [])
            if isinstance(item, dict)
        }
    )
    boss_styles = sorted(
        {
            str(item.get("style") or "")
            for item in boss_state.get("bosses", [])
            if isinstance(item, dict)
        }
    )
    through_cuts = _boss_state_through_cuts(boss_state)
    if through_cuts is None:
        return None
    if through_cuts:
        method = (
            "axis_aligned_profile_cut_state_box_cylinder_boss_batch_union_v1"
            if boss_source_kinds == ["cylinder"] and not any("beveled" in style for style in boss_styles)
            else "axis_aligned_profile_cut_state_box_profile_boss_batch_union_v1"
        )
    else:
        method = (
            "axis_aligned_box_cylinder_boss_batch_union_v1"
            if boss_source_kinds == ["cylinder"] and not any("beveled" in style for style in boss_styles)
            else "axis_aligned_box_profile_boss_batch_union_v1"
        )
    through_cut_metadata = (
        {
            "through_cut_count": len(through_cuts),
            "through_cut_kinds": sorted({str(cut.get("cut_kind") or "") for cut in through_cuts}),
        }
        if through_cuts
        else {}
    )
    result.metadata["lathe_reference_batch_union"] = {
        "schema": "lathe.geometry.reference_batch_union.v1",
        "method": method,
        "operand_count": len(meshes),
        "boss_count": boss_count,
        "boss_source_kinds": boss_source_kinds,
        "boss_styles": boss_styles,
        "result_face_count": len(result.faces),
        "result_watertight": bool(result.is_watertight),
        **through_cut_metadata,
    }
    result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
        "schema": "lathe.geometry.reference_exact_boolean.v1",
        "method": method,
        "op": "batch_union",
        "operand_count": len(meshes),
        "boss_count": boss_count,
        "boss_source_kinds": boss_source_kinds,
        "boss_styles": boss_styles,
        "passthrough": False,
        "result_face_count": len(result.faces),
        "result_watertight": bool(result.is_watertight),
        **through_cut_metadata,
    }
    _set_batch_source_meshes(result, (result,))
    return result


def _voxel_boolean_pitch(a: trimesh.Trimesh, b: trimesh.Trimesh) -> tuple[float, np.ndarray]:
    bounds_min, bounds_max = _mesh_bounds((a, b))
    extents = np.maximum(bounds_max - bounds_min, 1e-6)
    diagonal = float(np.linalg.norm(extents))
    pitch = max(diagonal / 96.0, 0.15)
    dims = np.ceil(extents / pitch).astype(int) + 5
    voxel_count = int(np.prod(np.maximum(dims, 1)))
    max_voxels = 1_500_000
    if voxel_count > max_voxels:
        scale = (voxel_count / max_voxels) ** (1.0 / 3.0)
        pitch *= float(scale)
        dims = np.ceil(extents / pitch).astype(int) + 5
    origin = bounds_min - pitch * 2.0
    return pitch, origin


def _voxel_index_set(mesh: trimesh.Trimesh, *, pitch: float, origin: np.ndarray) -> set[tuple[int, int, int]]:
    voxels = mesh.voxelized(pitch).fill()
    points = np.asarray(voxels.points, dtype=np.float64)
    if points.size == 0:
        return set()
    indices = np.rint((points - origin) / pitch).astype(np.int64)
    return {tuple(int(value) for value in row) for row in indices}


def _mesh_from_voxel_indices(
    indices: set[tuple[int, int, int]],
    *,
    pitch: float,
    origin: np.ndarray,
) -> trimesh.Trimesh:
    if not indices:
        return trimesh.Trimesh()
    coords = np.asarray(sorted(indices), dtype=np.int64)
    dims = np.max(coords, axis=0) + 3
    matrix = np.zeros(tuple(int(value) for value in dims), dtype=bool)
    matrix[coords[:, 0], coords[:, 1], coords[:, 2]] = True
    try:
        mesh = matrix_to_marching_cubes(matrix, pitch=pitch)
        mesh.apply_translation(origin)
    except (ImportError, ModuleNotFoundError, AttributeError, ValueError, RuntimeError, IndexError, TypeError):
        mesh = _block_mesh_from_voxel_indices(indices, pitch=pitch, origin=origin)
    mesh.remove_infinite_values()
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()
    mesh.fix_normals()
    return mesh


_VOXEL_FACE_CORNERS: tuple[
    tuple[tuple[int, int, int], tuple[tuple[float, float, float], ...]],
    ...
] = (
    ((1, 0, 0), ((0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (0.5, 0.5, 0.5), (0.5, -0.5, 0.5))),
    ((-1, 0, 0), ((-0.5, -0.5, -0.5), (-0.5, -0.5, 0.5), (-0.5, 0.5, 0.5), (-0.5, 0.5, -0.5))),
    ((0, 1, 0), ((-0.5, 0.5, -0.5), (-0.5, 0.5, 0.5), (0.5, 0.5, 0.5), (0.5, 0.5, -0.5))),
    ((0, -1, 0), ((-0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.5, -0.5, 0.5), (-0.5, -0.5, 0.5))),
    ((0, 0, 1), ((-0.5, -0.5, 0.5), (0.5, -0.5, 0.5), (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5))),
    ((0, 0, -1), ((-0.5, -0.5, -0.5), (-0.5, 0.5, -0.5), (0.5, 0.5, -0.5), (0.5, -0.5, -0.5))),
)


def _block_mesh_from_voxel_indices(
    indices: set[tuple[int, int, int]],
    *,
    pitch: float,
    origin: np.ndarray,
) -> trimesh.Trimesh:
    vertices: list[tuple[float, float, float]] = []
    vertex_index: dict[tuple[int, int, int], int] = {}
    faces: list[list[int]] = []
    scale = float(pitch)

    def add_vertex(coord: tuple[float, float, float]) -> int:
        key = tuple(int(round(value * 2.0)) for value in coord)
        existing = vertex_index.get(key)
        if existing is not None:
            return existing
        world = tuple(float(origin[axis] + coord[axis] * scale) for axis in range(3))
        vertex_index[key] = len(vertices)
        vertices.append(world)
        return len(vertices) - 1

    for i, j, k in sorted(indices):
        center = (float(i), float(j), float(k))
        for normal, corners in _VOXEL_FACE_CORNERS:
            neighbor = (i + normal[0], j + normal[1], k + normal[2])
            if neighbor in indices:
                continue
            quad = [
                add_vertex((center[0] + corner[0], center[1] + corner[1], center[2] + corner[2]))
                for corner in corners
            ]
            faces.append([quad[0], quad[1], quad[2]])
            faces.append([quad[0], quad[2], quad[3]])
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def _voxel_boolean(
    op: str,
    a: trimesh.Trimesh,
    b: trimesh.Trimesh,
) -> tuple[trimesh.Trimesh, dict[str, Any]] | None:
    if op not in {"union", "difference", "intersection"}:
        return None
    pitch, origin = _voxel_boolean_pitch(a, b)
    try:
        a_indices = _voxel_index_set(a, pitch=pitch, origin=origin)
        b_indices = _voxel_index_set(b, pitch=pitch, origin=origin)
    except (AttributeError, ValueError, RuntimeError, IndexError, TypeError):
        return None
    if not a_indices:
        return None
    if op == "union":
        result_indices = a_indices | b_indices
    elif op == "difference":
        result_indices = a_indices - b_indices
    else:
        result_indices = a_indices & b_indices
    result_details = {
        "method": "voxel_boolean_fallback_v1",
        "op": op,
        "attempted_backend": "trimesh.boolean",
        "actual_backend": "lathe.reference.voxel_boolean",
        "actual_operation": f"voxel_{op}",
        "exact_kernel_path": False,
        "fallback": True,
        "passthrough": False,
        "pitch_cm": float(pitch),
        "source_voxel_count": len(a_indices),
        "cutter_voxel_count": len(b_indices),
        "result_voxel_count": len(result_indices),
    }
    if not result_indices and op in {"difference", "intersection"}:
        mesh = trimesh.Trimesh()
        return mesh, {
            **result_details,
            "empty_result": True,
            "result_face_count": 0,
            "result_watertight": False,
            "result_body_count": 0,
        }
    mesh = _mesh_from_voxel_indices(result_indices, pitch=pitch, origin=origin)
    if len(mesh.faces) == 0:
        return None
    try:
        body_count = len(mesh.split(only_watertight=False))
    except (AttributeError, TypeError, ValueError):
        body_count = 0
    return mesh, {
        **result_details,
        "result_face_count": len(mesh.faces),
        "result_watertight": bool(mesh.is_watertight),
        "result_body_count": int(body_count),
    }


def _sdf_metadata_float(metadata: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key not in metadata:
            continue
        try:
            return float(metadata[key])
        except (TypeError, ValueError):
            return None
    return None


def _sdf_metadata_tuple(metadata: dict[str, Any], *keys: str) -> tuple[float, ...] | None:
    for key in keys:
        if key not in metadata:
            continue
        try:
            return tuple(float(value) for value in metadata[key])
        except (TypeError, ValueError):
            return None
    return None


def _sdf_metadata_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _sdf_boolean_blend_width(
    op: str,
    left_metadata: dict[str, Any],
    right_metadata: dict[str, Any],
) -> float:
    candidates = [right_metadata]
    if op in {"union", "intersection"}:
        candidates.append(left_metadata)
    width = 0.0
    for metadata in candidates:
        modifier = metadata.get("v2_polybevel_modifier")
        if isinstance(modifier, dict):
            candidate = _sdf_metadata_float(modifier, "width_cm", "radius_cm")
            if candidate is not None:
                width = max(width, candidate)
        for group in _sdf_metadata_list(metadata.get("bevel_seam_groups")):
            candidate = _sdf_metadata_float(group, "width_cm", "radius_cm")
            if candidate is not None:
                width = max(width, candidate)
    return max(0.0, float(width))


def _sdf_semantic_metadata_fields(primitive: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for key in (
        "part",
        "component",
        "region",
        "tags",
        "boolean_seam_groups",
        "bevel_seam_groups",
        "hard_edge_groups",
        "v2_polybevel_modifier",
        "semantic_metadata",
    ):
        value = primitive.get(key)
        if value not in (None, "", (), [], {}):
            fields[key] = deepcopy(value)
    return fields


def _sdf_nested_dict(metadata: dict[str, Any], *path: str) -> dict[str, Any]:
    current: Any = metadata
    for key in path:
        if not isinstance(current, dict):
            return {}
        current = current.get(key)
    return dict(current) if isinstance(current, dict) else {}


def _sdf_capsule_metadata(primitive: dict[str, Any]) -> tuple[float, float, str] | None:
    modifier = _sdf_nested_dict(
        primitive,
        "semantic_metadata",
        "shape_ir_v2",
        "v2_capsule_modifier",
    )
    if not modifier:
        source = _sdf_nested_dict(primitive, "semantic_metadata", "source_shape_primitive")
        modifier = _sdf_nested_dict(
            source,
            "semantic_metadata",
            "shape_ir_v2",
            "v2_capsule_modifier",
        )
        if not modifier:
            modifier = _sdf_nested_dict(source, "v2_capsule_modifier")
    if not modifier:
        return None
    radius = _sdf_metadata_float(modifier, "radius_cm", "radius")
    length = _sdf_metadata_float(modifier, "length_cm", "length")
    if radius is None or length is None or radius <= 0.0 or length <= radius * 2.0:
        return None
    axis = str(modifier.get("axis") or primitive.get("axis") or "y")
    if axis not in {"x", "y", "z"}:
        return None
    return radius, length, axis


def _sdf_tube_metadata(primitive: dict[str, Any]) -> dict[str, Any] | None:
    if str(primitive.get("primitive_type") or "") == "tube":
        outer_radius = _sdf_metadata_float(primitive, "outer_radius_cm", "outer_radius")
        inner_radius = _sdf_metadata_float(primitive, "inner_radius_cm", "inner_radius")
        height = _sdf_metadata_float(primitive, "height_cm", "height")
        if (
            outer_radius is not None
            and inner_radius is not None
            and height is not None
            and outer_radius > 0.0
            and inner_radius > 0.0
            and inner_radius < outer_radius
            and height > 0.0
        ):
            axis = str(primitive.get("axis") or "y")
            if axis in {"x", "y", "z"}:
                rim_bevel = _sdf_metadata_float(primitive, "rim_bevel_cm", "rim_bevel") or 0.0
                return {
                    "outer_radius": float(outer_radius),
                    "inner_radius": float(inner_radius),
                    "height": float(height),
                    "axis": axis,
                    "rim_bevel": max(0.0, float(rim_bevel)),
                    "wall_thickness": float(outer_radius - inner_radius),
                }
    modifier = _sdf_nested_dict(
        primitive,
        "semantic_metadata",
        "shape_ir_v2",
        "v2_tube_modifier",
    )
    if not modifier:
        source = _sdf_nested_dict(primitive, "semantic_metadata", "source_shape_primitive")
        modifier = _sdf_nested_dict(
            source,
            "semantic_metadata",
            "shape_ir_v2",
            "v2_tube_modifier",
        )
        if not modifier:
            modifier = _sdf_nested_dict(source, "v2_tube_modifier")
    if not modifier:
        return None
    outer_radius = _sdf_metadata_float(modifier, "outer_radius_cm", "outer_radius")
    inner_radius = _sdf_metadata_float(modifier, "inner_radius_cm", "inner_radius")
    height = _sdf_metadata_float(modifier, "height_cm", "height")
    if (
        outer_radius is None
        or inner_radius is None
        or height is None
        or outer_radius <= 0.0
        or inner_radius <= 0.0
        or inner_radius >= outer_radius
        or height <= 0.0
    ):
        return None
    rim_bevel = _sdf_metadata_float(modifier, "rim_bevel_cm", "rim_bevel") or 0.0
    axis = str(modifier.get("axis") or primitive.get("axis") or "y")
    if axis not in {"x", "y", "z"}:
        return None
    return {
        "outer_radius": float(outer_radius),
        "inner_radius": float(inner_radius),
        "height": float(height),
        "axis": axis,
        "rim_bevel": max(0.0, float(rim_bevel)),
        "wall_thickness": float(outer_radius - inner_radius),
    }


def _sdf_cylindrical_bore_metadata(primitive: dict[str, Any]) -> dict[str, Any] | None:
    if str(primitive.get("primitive_type") or "") == "cylindrical_bore":
        radius = _sdf_metadata_float(primitive, "radius_cm", "radius")
        depth = _sdf_metadata_float(primitive, "depth_cm", "height_cm", "height")
        if radius is not None and depth is not None and radius > 0.0 and depth > 0.0:
            axis = str(primitive.get("axis") or "y")
            if axis in {"x", "y", "z"}:
                return {
                    "radius": float(radius),
                    "depth": float(depth),
                    "axis": axis,
                    "style": str(primitive.get("style") or "straight"),
                    "seam_group": str(primitive.get("seam_group") or ""),
                }
    modifier = _sdf_nested_dict(
        primitive,
        "semantic_metadata",
        "shape_ir_v2",
        "v2_countersunk_hole_modifier",
    )
    if not modifier:
        modifier = _sdf_nested_dict(primitive, "v2_countersunk_hole_modifier")
    if modifier and str(modifier.get("style") or "straight") != "straight":
        return None
    radius = (
        _sdf_metadata_float(modifier, "radius_cm", "radius")
        if modifier
        else None
    )
    depth = (
        _sdf_metadata_float(modifier, "depth_cm", "depth")
        if modifier
        else None
    )
    if radius is None or depth is None:
        profile = primitive.get("profile_points")
        if not isinstance(profile, (list, tuple)) or len(profile) != 2:
            return None
        try:
            first = (float(profile[0][0]), float(profile[0][1]))
            second = (float(profile[1][0]), float(profile[1][1]))
        except (TypeError, ValueError, IndexError):
            return None
        if first[1] <= 0.0 or abs(first[1] - second[1]) > max(1e-6, first[1] * 1e-5):
            return None
        radius = first[1]
        depth = abs(second[0] - first[0])
    if radius is None or depth is None or radius <= 0.0 or depth <= 0.0:
        return None
    axis = str((modifier or {}).get("axis") or primitive.get("axis") or "y")
    if axis not in {"x", "y", "z"}:
        return None
    return {
        "radius": float(radius),
        "depth": float(depth),
        "axis": axis,
        "style": "straight",
        "seam_group": str((modifier or {}).get("seam_group") or ""),
    }


def _sdf_rectangular_extruded_profile_metadata(primitive: dict[str, Any]) -> dict[str, Any] | None:
    axis = str(primitive.get("axis") or "z")
    if axis not in {"x", "y", "z"}:
        return None
    height = _sdf_metadata_float(primitive, "extrude_height", "extrude_height_cm", "height_cm")
    if height is None or height <= 0.0:
        return None
    extents = _sdf_metadata_tuple(primitive, "extents", "extents_cm")
    if extents is not None and len(extents) == 3 and all(value > 0.0 for value in extents):
        return {"axis": axis, "extents": tuple(float(value) for value in extents), "extrude_height": height}
    polygon = primitive.get("profile_polygon")
    if not isinstance(polygon, (list, tuple)) or len(polygon) != 4:
        return None
    try:
        points = [(float(point[0]), float(point[1])) for point in polygon]
    except (TypeError, ValueError, IndexError):
        return None
    xs = sorted({round(point[0], 9) for point in points})
    ys = sorted({round(point[1], 9) for point in points})
    if len(xs) != 2 or len(ys) != 2:
        return None
    corners = {(xs[0], ys[0]), (xs[1], ys[0]), (xs[1], ys[1]), (xs[0], ys[1])}
    if {(round(x, 9), round(y, 9)) for x, y in points} != corners:
        return None
    width = float(xs[1] - xs[0])
    profile_height = float(ys[1] - ys[0])
    if width <= 0.0 or profile_height <= 0.0:
        return None
    if axis == "z":
        extents = (width, profile_height, height)
    elif axis == "y":
        extents = (width, height, profile_height)
    else:
        extents = (height, profile_height, width)
    return {
        "axis": axis,
        "extents": extents,
        "extrude_height": float(height),
        "profile_width": width,
        "profile_height": profile_height,
        "profile_polygon": points,
    }


def _sdf_circular_swept_profile_metadata(primitive: dict[str, Any]) -> dict[str, Any] | None:
    if str(primitive.get("primitive_type") or "") != "swept_profile":
        return None
    if str(primitive.get("sdf_approximation") or "") == "straight_circular_swept_profile_as_oriented_cylinder_v1":
        radius = _sdf_metadata_float(primitive, "radius_cm", "radius")
        if radius is None or radius <= 0.0:
            return None
        try:
            start = np.asarray([float(value) for value in primitive["start"]], dtype=np.float64)
            end = np.asarray([float(value) for value in primitive["end"]], dtype=np.float64)
        except (KeyError, TypeError, ValueError):
            return None
        if start.shape != (3,) or end.shape != (3,):
            return None
        length = float(np.linalg.norm(end - start))
        if length <= 1e-9:
            return None
        return {
            "radius": float(radius),
            "length": float(length),
            "start": start,
            "end": end,
            "world_path": True,
            "cross_section_vertex_count": int(primitive.get("cross_section_vertex_count") or 0),
        }
    cross_section = primitive.get("cross_section")
    if not _radial_2d_polygon(cross_section):
        return None
    sweep_path = primitive.get("sweep_path")
    if not isinstance(sweep_path, (list, tuple)) or len(sweep_path) != 2:
        return None
    try:
        radii = [
            math.hypot(float(point[0]), float(point[1]))
            for point in cross_section
        ]
        start = np.asarray(
            [float(value) for value in sweep_path[0]],
            dtype=np.float64,
        )
        end = np.asarray(
            [float(value) for value in sweep_path[1]],
            dtype=np.float64,
        )
    except (TypeError, ValueError, IndexError):
        return None
    if start.shape != (3,) or end.shape != (3,) or not radii:
        return None
    radius = max(float(value) for value in radii)
    length = float(np.linalg.norm(end - start))
    if radius <= 0.0 or length <= 1e-9:
        return None
    return {
        "radius": float(radius),
        "length": float(length),
        "start": start,
        "end": end,
        "world_path": False,
        "cross_section_vertex_count": len(radii),
    }


def _sdf_circular_swept_profile_path_metadata(primitive: dict[str, Any]) -> dict[str, Any] | None:
    if str(primitive.get("primitive_type") or "") != "swept_profile":
        return None
    approximation = str(primitive.get("sdf_approximation") or "")
    if approximation == "polyline_circular_swept_profile_as_capsule_chain_v1":
        radius = _sdf_metadata_float(primitive, "radius_cm", "radius")
        raw_path = primitive.get("path") or primitive.get("sweep_path")
        world_path = True
        cross_section_vertex_count = int(primitive.get("cross_section_vertex_count") or 0)
    else:
        cross_section = primitive.get("cross_section")
        if not _radial_2d_polygon(cross_section):
            return None
        raw_path = primitive.get("sweep_path")
        world_path = False
        cross_section_vertex_count = len(cross_section)
        try:
            radius = max(math.hypot(float(point[0]), float(point[1])) for point in cross_section)
        except (TypeError, ValueError, IndexError):
            return None
    if radius is None or radius <= 0.0:
        return None
    if not isinstance(raw_path, (list, tuple)) or len(raw_path) < 3:
        return None
    path: list[np.ndarray] = []
    try:
        for point in raw_path:
            parsed = np.asarray([float(value) for value in point], dtype=np.float64)
            if parsed.shape != (3,):
                return None
            path.append(parsed)
    except (TypeError, ValueError):
        return None
    if any(float(np.linalg.norm(end - start)) <= 1e-9 for start, end in zip(path, path[1:])):
        return None
    return {
        "radius": float(radius),
        "path": path,
        "world_path": bool(world_path),
        "cross_section_vertex_count": int(cross_section_vertex_count),
    }


def _sdf_expr_from_shape_metadata(mesh: trimesh.Trimesh) -> tuple[Any, dict[str, Any]] | None:
    sdf_boolean = mesh.metadata.get("lathe_reference_sdf_boolean")
    if isinstance(sdf_boolean, dict):
        composed = _sdf_expr_from_sdf_boolean_metadata(sdf_boolean)
        if composed is not None:
            return composed
    return _sdf_expr_from_primitive_metadata(_resolved_shape_primitive_metadata(mesh))


def _sdf_expr_from_sdf_boolean_metadata(metadata: dict[str, Any]) -> tuple[Any, dict[str, Any]] | None:
    op = str(metadata.get("op") or "")
    if op not in {"union", "difference", "intersection"}:
        return None
    source = metadata.get("source")
    cutter = metadata.get("cutter")
    if not isinstance(source, dict) or not isinstance(cutter, dict):
        return None
    left = _sdf_expr_from_primitive_metadata(source)
    if left is None and str(source.get("primitive_type") or "") == "sdf_boolean":
        left = _sdf_expr_from_sdf_boolean_metadata(source)
    right = _sdf_expr_from_primitive_metadata(cutter)
    if right is None and str(cutter.get("primitive_type") or "") == "sdf_boolean":
        right = _sdf_expr_from_sdf_boolean_metadata(cutter)
    if left is None or right is None:
        return None
    left_expr, left_metadata = left
    right_expr, right_metadata = right
    try:
        from ..f_rep import Intersect, SmoothIntersect, SmoothSubtract, SmoothUnion, Subtract, Union
    except (ImportError, ModuleNotFoundError):
        return None
    blend_width = _sdf_metadata_float(metadata, "blend_width_cm", "smooth_blend_width_cm") or 0.0
    if op == "union":
        expr = (
            SmoothUnion(left_expr, right_expr, k=blend_width)
            if blend_width > 0.0
            else Union(left_expr, right_expr)
        )
    elif op == "difference":
        expr = (
            SmoothSubtract(left_expr, right_expr, k=blend_width)
            if blend_width > 0.0
            else Subtract(left_expr, right_expr)
        )
    else:
        expr = (
            SmoothIntersect(left_expr, right_expr, k=blend_width)
            if blend_width > 0.0
            else Intersect(left_expr, right_expr)
        )
    return expr, {
        "primitive_type": "sdf_boolean",
        "op": op,
        "blend_width_cm": float(blend_width),
        "source_primitive_type": str(left_metadata.get("primitive_type") or ""),
        "cutter_primitive_type": str(right_metadata.get("primitive_type") or ""),
        "source": left_metadata,
        "cutter": right_metadata,
    }


def _sdf_expr_from_primitive_metadata(primitive: dict[str, Any]) -> tuple[Any, dict[str, Any]] | None:
    primitive_type = str(primitive.get("primitive_type") or "")
    try:
        from ..f_rep import Box, Capsule, Cylinder, Rotate, SmoothSubtract, SmoothUnion, Sphere, Subtract, Torus, Translate
    except (ImportError, ModuleNotFoundError):
        return None
    try:
        center = tuple(float(value) for value in primitive.get("center", (0.0, 0.0, 0.0)))
    except (TypeError, ValueError):
        return None
    if len(center) != 3:
        return None

    def _axis_aligned(expr: Any, axis: str) -> Any | None:
        if axis == "y":
            return expr
        if axis == "x":
            return Rotate(expr, axis=(0.0, 0.0, 1.0), angle=-math.pi / 2.0)
        if axis == "z":
            return Rotate(expr, axis=(1.0, 0.0, 0.0), angle=math.pi / 2.0)
        return None

    def _align_y_to_direction(expr: Any, direction: np.ndarray) -> Any | None:
        norm = float(np.linalg.norm(direction))
        if norm <= 1e-9:
            return None
        target = direction / norm
        source = np.asarray([0.0, 1.0, 0.0], dtype=np.float64)
        dot = float(np.clip(np.dot(source, target), -1.0, 1.0))
        if dot >= 1.0 - 1e-9:
            return expr
        if dot <= -1.0 + 1e-9:
            return Rotate(expr, axis=(1.0, 0.0, 0.0), angle=math.pi)
        axis = np.cross(source, target)
        axis_norm = float(np.linalg.norm(axis))
        if axis_norm <= 1e-9:
            return None
        axis = axis / axis_norm
        return Rotate(
            expr,
            axis=(float(axis[0]), float(axis[1]), float(axis[2])),
            angle=float(math.acos(dot)),
        )

    if primitive_type == "sphere":
        radius = _sdf_metadata_float(primitive, "radius", "radius_cm")
        if radius is None:
            return None
        if radius <= 0.0:
            return None
        return Translate(Sphere(radius=radius), offset=center), {
            "primitive_type": primitive_type,
            "radius_cm": float(radius),
            "center": [float(value) for value in center],
            **_sdf_semantic_metadata_fields(primitive),
        }
    if primitive_type == "cylinder":
        radius = _sdf_metadata_float(primitive, "radius", "radius_cm")
        height = _sdf_metadata_float(primitive, "height", "height_cm")
        if radius is None or height is None:
            return None
        if radius <= 0.0 or height <= 0.0:
            return None
        axis = str(primitive.get("axis") or "y")
        expr = _axis_aligned(Cylinder(radius=radius, height=height), axis)
        if expr is None:
            return None
        return Translate(expr, offset=center), {
            "primitive_type": primitive_type,
            "radius_cm": float(radius),
            "height_cm": float(height),
            "axis": axis,
            "center": [float(value) for value in center],
            **_sdf_semantic_metadata_fields(primitive),
        }
    if primitive_type == "torus":
        major_radius = _sdf_metadata_float(primitive, "major_radius", "major_radius_cm")
        minor_radius = _sdf_metadata_float(primitive, "minor_radius", "minor_radius_cm")
        if major_radius is None or minor_radius is None:
            return None
        if major_radius <= 0.0 or minor_radius <= 0.0:
            return None
        axis = str(primitive.get("axis") or "y")
        expr = _axis_aligned(
            Torus(major_radius=major_radius, minor_radius=minor_radius),
            axis,
        )
        if expr is None:
            return None
        return Translate(expr, offset=center), {
            "primitive_type": primitive_type,
            "major_radius_cm": float(major_radius),
            "minor_radius_cm": float(minor_radius),
            "axis": axis,
            "center": [float(value) for value in center],
            **_sdf_semantic_metadata_fields(primitive),
        }
    if primitive_type == "tube":
        tube = _sdf_tube_metadata(primitive)
        if tube is not None:
            outer = Cylinder(radius=tube["outer_radius"], height=tube["height"])
            cut_height = tube["height"] + max(tube["rim_bevel"] * 2.0, 1e-3)
            inner = Cylinder(radius=tube["inner_radius"], height=cut_height)
            expr = (
                SmoothSubtract(outer, inner, k=tube["rim_bevel"])
                if tube["rim_bevel"] > 0.0
                else Subtract(outer, inner)
            )
            aligned = _axis_aligned(expr, str(tube["axis"]))
            if aligned is None:
                return None
            return Translate(aligned, offset=center), {
                "primitive_type": "tube",
                "outer_radius_cm": float(tube["outer_radius"]),
                "inner_radius_cm": float(tube["inner_radius"]),
                "wall_thickness_cm": float(tube["wall_thickness"]),
                "height_cm": float(tube["height"]),
                "axis": str(tube["axis"]),
                "rim_bevel_cm": float(tube["rim_bevel"]),
                "center": [float(value) for value in center],
                **_sdf_semantic_metadata_fields(primitive),
            }
    if primitive_type == "extruded_profile":
        profile = _sdf_rectangular_extruded_profile_metadata(primitive)
        if profile is not None:
            extents = tuple(float(value) for value in profile["extents"])
            return Translate(Box(half_extents=tuple(value * 0.5 for value in extents)), offset=center), {
                "primitive_type": "extruded_profile",
                "extents_cm": [float(value) for value in extents],
                "axis": str(profile["axis"]),
                "extrude_height_cm": float(profile["extrude_height"]),
                "profile_width_cm": float(profile.get("profile_width") or 0.0),
                "profile_height_cm": float(profile.get("profile_height") or 0.0),
                "profile_polygon": deepcopy(profile.get("profile_polygon") or []),
                "center": [float(value) for value in center],
                **_sdf_semantic_metadata_fields(primitive),
            }
    if primitive_type == "swept_profile":
        swept_path = _sdf_circular_swept_profile_path_metadata(primitive)
        if swept_path is not None:
            radius = float(swept_path["radius"])
            raw_path = [np.asarray(point, dtype=np.float64) for point in swept_path["path"]]
            primitive_center = np.asarray(center, dtype=np.float64)
            path = raw_path if bool(swept_path.get("world_path")) else [primitive_center + point for point in raw_path]
            expr: Any | None = None
            for start, end in zip(path, path[1:]):
                direction = end - start
                length = float(np.linalg.norm(direction))
                member_expr = _align_y_to_direction(Capsule(half_height=length * 0.5, radius=radius), direction)
                if member_expr is None:
                    return None
                midpoint = (start + end) * 0.5
                member_expr = Translate(member_expr, offset=tuple(float(value) for value in midpoint))
                expr = member_expr if expr is None else SmoothUnion(expr, member_expr, k=max(radius * 0.35, 1e-4))
            if expr is None:
                return None
            return expr, {
                "primitive_type": "swept_profile",
                "sdf_approximation": "polyline_circular_swept_profile_as_capsule_chain_v1",
                "radius_cm": radius,
                "path": [[float(value) for value in point] for point in path],
                "center": [float(value) for value in center],
                "segment_count": len(path) - 1,
                "cross_section_vertex_count": int(swept_path["cross_section_vertex_count"]),
                **_sdf_semantic_metadata_fields(primitive),
            }
        swept = _sdf_circular_swept_profile_metadata(primitive)
        if swept is not None:
            start = np.asarray(swept["start"], dtype=np.float64)
            end = np.asarray(swept["end"], dtype=np.float64)
            primitive_center = np.asarray(center, dtype=np.float64)
            if bool(swept.get("world_path")):
                start_world = start
                end_world = end
            else:
                start_world = primitive_center + start
                end_world = primitive_center + end
            midpoint = (start_world + end_world) * 0.5
            direction = end_world - start_world
            radius = float(swept["radius"])
            length = float(swept["length"])
            expr = _align_y_to_direction(Cylinder(radius=radius, height=length), direction)
            if expr is None:
                return None
            return Translate(expr, offset=tuple(float(value) for value in midpoint)), {
                "primitive_type": "swept_profile",
                "sdf_approximation": "straight_circular_swept_profile_as_oriented_cylinder_v1",
                "radius_cm": radius,
                "height_cm": length,
                "length_cm": length,
                "start": [float(value) for value in start_world],
                "end": [float(value) for value in end_world],
                "center": [float(value) for value in midpoint],
                "cross_section_vertex_count": int(swept["cross_section_vertex_count"]),
                **_sdf_semantic_metadata_fields(primitive),
            }
    if primitive_type == "sdf_mesh":
        tube = _sdf_tube_metadata(primitive)
        if tube is not None:
            outer = Cylinder(radius=tube["outer_radius"], height=tube["height"])
            cut_height = tube["height"] + max(tube["rim_bevel"] * 2.0, 1e-3)
            inner = Cylinder(radius=tube["inner_radius"], height=cut_height)
            expr = (
                SmoothSubtract(outer, inner, k=tube["rim_bevel"])
                if tube["rim_bevel"] > 0.0
                else Subtract(outer, inner)
            )
            aligned = _axis_aligned(expr, str(tube["axis"]))
            if aligned is None:
                return None
            return Translate(aligned, offset=center), {
                "primitive_type": "tube",
                "outer_radius_cm": float(tube["outer_radius"]),
                "inner_radius_cm": float(tube["inner_radius"]),
                "wall_thickness_cm": float(tube["wall_thickness"]),
                "height_cm": float(tube["height"]),
                "axis": str(tube["axis"]),
                "rim_bevel_cm": float(tube["rim_bevel"]),
                "center": [float(value) for value in center],
                **_sdf_semantic_metadata_fields(primitive),
            }
        capsule = _sdf_capsule_metadata(primitive)
        if capsule is not None:
            radius, length, axis = capsule
            shaft_length = length - radius * 2.0
            expr = _axis_aligned(
                Capsule(half_height=shaft_length * 0.5, radius=radius),
                axis,
            )
            if expr is None:
                return None
            return Translate(expr, offset=center), {
                "primitive_type": "capsule",
                "radius_cm": float(radius),
                "length_cm": float(length),
                "shaft_length_cm": float(shaft_length),
                "axis": axis,
                "center": [float(value) for value in center],
                **_sdf_semantic_metadata_fields(primitive),
            }
    if primitive_type in {"revolved_profile", "cylindrical_bore"}:
        bore = _sdf_cylindrical_bore_metadata(primitive)
        if bore is not None:
            expr = _axis_aligned(
                Cylinder(radius=bore["radius"], height=bore["depth"]),
                str(bore["axis"]),
            )
            if expr is None:
                return None
            return Translate(expr, offset=center), {
                "primitive_type": "cylindrical_bore",
                "radius_cm": float(bore["radius"]),
                "depth_cm": float(bore["depth"]),
                "height_cm": float(bore["depth"]),
                "axis": str(bore["axis"]),
                "style": str(bore["style"]),
                "seam_group": str(bore["seam_group"]),
                "center": [float(value) for value in center],
                **_sdf_semantic_metadata_fields(primitive),
            }
    if primitive_type == "box":
        extents = _sdf_metadata_tuple(primitive, "extents", "extents_cm")
        if extents is None:
            return None
        if len(extents) != 3 or any(value <= 0.0 for value in extents):
            return None
        half_extents = tuple(float(value) * 0.5 for value in extents)
        return Translate(Box(half_extents=half_extents), offset=center), {
            "primitive_type": primitive_type,
            "extents_cm": [float(value) for value in extents],
            "center": [float(value) for value in center],
            **_sdf_semantic_metadata_fields(primitive),
        }
    return None


def _sdf_boolean_resolution(
    bounds_min: np.ndarray,
    bounds_max: np.ndarray,
    *,
    high_detail: bool = False,
) -> tuple[int, int, int]:
    extents = np.maximum(bounds_max - bounds_min, 1e-6)
    diagonal = float(np.linalg.norm(extents))
    if high_detail:
        pitch = max(diagonal / 128.0, 0.08)
        min_resolution = 32
        max_resolution = 144
    else:
        pitch = max(diagonal / 96.0, 0.12)
        min_resolution = 24
        max_resolution = 112
    resolution = np.ceil(extents / pitch).astype(int) + 3
    return tuple(int(max(min_resolution, min(max_resolution, value))) for value in resolution)


def _sdf_metadata_contains_primitive_type(metadata: dict[str, Any], primitive_type: str) -> bool:
    stack: list[dict[str, Any]] = [metadata]
    seen: set[int] = set()
    while stack:
        current = stack.pop()
        marker = id(current)
        if marker in seen:
            continue
        seen.add(marker)
        if str(current.get("primitive_type") or "") == primitive_type:
            return True
        for key in ("source", "cutter"):
            child = current.get(key)
            if isinstance(child, dict):
                stack.append(child)
    return False


def _sdf_boolean(
    op: str,
    a: trimesh.Trimesh,
    b: trimesh.Trimesh,
) -> trimesh.Trimesh | None:
    if op not in {"union", "difference", "intersection"}:
        return None
    left = _sdf_expr_from_shape_metadata(a)
    right = _sdf_expr_from_shape_metadata(b)
    if left is None or right is None:
        return None
    left_expr, left_metadata = left
    right_expr, right_metadata = right
    blend_width = _sdf_boolean_blend_width(op, left_metadata, right_metadata)
    try:
        from ..f_rep import (
            Intersect,
            SmoothIntersect,
            SmoothSubtract,
            SmoothUnion,
            Subtract,
            Union,
            extract_mesh,
        )
        from ..f_rep.marching_cubes import _have_skimage
    except (ImportError, ModuleNotFoundError):
        return None
    if op == "union":
        expr = (
            SmoothUnion(left_expr, right_expr, k=blend_width)
            if blend_width > 0.0
            else Union(left_expr, right_expr)
        )
    elif op == "difference":
        expr = (
            SmoothSubtract(left_expr, right_expr, k=blend_width)
            if blend_width > 0.0
            else Subtract(left_expr, right_expr)
        )
    else:
        expr = (
            SmoothIntersect(left_expr, right_expr, k=blend_width)
            if blend_width > 0.0
            else Intersect(left_expr, right_expr)
        )
    if op == "difference":
        bounds_min, bounds_max = _mesh_bounds((a,))
    elif op == "union":
        bounds_min, bounds_max = _mesh_bounds((a, b))
    else:
        a_bounds = np.asarray(a.bounds, dtype=np.float64)
        b_bounds = np.asarray(b.bounds, dtype=np.float64)
        if a_bounds.shape != (2, 3) or b_bounds.shape != (2, 3):
            return None
        bounds_min = np.maximum(a_bounds[0], b_bounds[0])
        bounds_max = np.minimum(a_bounds[1], b_bounds[1])
        if bool(np.any(bounds_max <= bounds_min)):
            return trimesh.Trimesh()
    base_bounds_min = np.asarray(bounds_min, dtype=np.float64)
    base_bounds_max = np.asarray(bounds_max, dtype=np.float64)
    base_margin = max(float(np.linalg.norm(base_bounds_max - base_bounds_min)) / 96.0, 0.12)
    extraction_backend = "marching_cubes" if _have_skimage() else "dual_contouring"
    accepted_mesh: trimesh.Trimesh | None = None
    accepted_bounds_min: np.ndarray | None = None
    accepted_bounds_max: np.ndarray | None = None
    accepted_resolution: tuple[int, int, int] | None = None
    extraction_attempts: list[dict[str, Any]] = []
    needs_swept_retry = op == "union" and (
        _sdf_metadata_contains_primitive_type(left_metadata, "swept_profile")
        or _sdf_metadata_contains_primitive_type(right_metadata, "swept_profile")
    )
    for margin_factor in (2.0, 3.0, 4.0, 6.0):
        attempt_bounds_min = base_bounds_min - base_margin * margin_factor
        attempt_bounds_max = base_bounds_max + base_margin * margin_factor
        attempt_detail_levels = (False, True) if needs_swept_retry else (False,)
        for high_detail in attempt_detail_levels:
            resolution = _sdf_boolean_resolution(
                attempt_bounds_min,
                attempt_bounds_max,
                high_detail=high_detail,
            )
            try:
                vertices, faces = extract_mesh(
                    expr,
                    bounds=(
                        tuple(float(value) for value in attempt_bounds_min),
                        tuple(float(value) for value in attempt_bounds_max),
                    ),
                    resolution=resolution,
                    backend=extraction_backend,
                )
            except (ValueError, RuntimeError, AttributeError, IndexError, TypeError, ImportError, ModuleNotFoundError):
                extraction_attempts.append(
                    {
                        "backend": extraction_backend,
                        "margin_factor": float(margin_factor),
                        "resolution": [int(value) for value in resolution],
                        "high_detail_retry": bool(high_detail),
                        "accepted": False,
                        "reason": "extract_mesh_failed",
                    }
                )
                continue
            mesh = trimesh.Trimesh(
                vertices=np.asarray(vertices, dtype=np.float64),
                faces=np.asarray(faces, dtype=np.int64),
                process=False,
            )
            if len(mesh.faces) == 0:
                extraction_attempts.append(
                    {
                        "backend": extraction_backend,
                        "margin_factor": float(margin_factor),
                        "resolution": [int(value) for value in resolution],
                        "high_detail_retry": bool(high_detail),
                        "accepted": False,
                        "reason": "empty_mesh",
                    }
                )
                continue
            mesh.remove_infinite_values()
            mesh.remove_unreferenced_vertices()
            mesh.merge_vertices()
            mesh.fix_normals()
            watertight = bool(mesh.is_watertight)
            extraction_attempts.append(
                {
                    "backend": extraction_backend,
                    "margin_factor": float(margin_factor),
                    "resolution": [int(value) for value in resolution],
                    "high_detail_retry": bool(high_detail),
                    "accepted": watertight,
                    "result_face_count": len(mesh.faces),
                    "result_vertex_count": len(mesh.vertices),
                    "result_watertight": watertight,
                }
            )
            if watertight:
                accepted_mesh = mesh
                accepted_bounds_min = attempt_bounds_min
                accepted_bounds_max = attempt_bounds_max
                accepted_resolution = resolution
                break
        if accepted_mesh is not None:
            break
    if accepted_mesh is None or accepted_bounds_min is None or accepted_bounds_max is None or accepted_resolution is None:
        return None
    mesh = accepted_mesh
    _set_batch_source_meshes(mesh, (mesh,))
    mesh.metadata["lathe_reference_sdf_boolean"] = {
        "schema": "lathe.geometry.reference_sdf_boolean.v1",
        "method": "sdf_smooth_boolean_v1" if blend_width > 0.0 else "sdf_sampled_boolean_v1",
        "op": op,
        "smooth_boolean": bool(blend_width > 0.0),
        "blend_width_cm": float(blend_width),
        "backend": f"lathe.f_rep.{extraction_backend}",
        "requested_backend": "lathe.f_rep.marching_cubes",
        "actual_backend": f"lathe.f_rep.{extraction_backend}",
        "backend_fallback_reason": "" if extraction_backend == "marching_cubes" else "scikit_image_unavailable",
        "exact_kernel_path": False,
        "fallback": False,
        "passthrough": False,
        "source_primitive_type": str(left_metadata.get("primitive_type") or ""),
        "cutter_primitive_type": str(right_metadata.get("primitive_type") or ""),
        "source": left_metadata,
        "cutter": right_metadata,
        "bounds_min": [float(value) for value in accepted_bounds_min],
        "bounds_max": [float(value) for value in accepted_bounds_max],
        "resolution": [int(value) for value in accepted_resolution],
        "extraction_attempt_count": len(extraction_attempts),
        "extraction_attempts": extraction_attempts,
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_watertight": bool(mesh.is_watertight),
        "result_body_count": len(mesh.split(only_watertight=False)) if len(mesh.faces) > 0 else 0,
    }
    return mesh


def _record_successful_backend_boolean(
    mesh: trimesh.Trimesh,
    *,
    op: str,
    a: trimesh.Trimesh,
    b: trimesh.Trimesh,
) -> trimesh.Trimesh:
    if not isinstance(mesh, trimesh.Trimesh):
        return mesh
    mesh.metadata["lathe_reference_boolean_backend"] = {
        "schema": "lathe.geometry.reference_boolean_backend.v1",
        "method": "trimesh_boolean_backend_v1",
        "backend": "trimesh.boolean",
        "op": op,
        "attempted_backend": "trimesh.boolean",
        "actual_backend": "trimesh.boolean",
        "exact_kernel_path": False,
        "fallback": False,
        "passthrough": False,
        "source_has_profile_cut_state": _profile_cut_state_from_mesh(a) is not None,
        "cutter_has_profile_cut_state": _profile_cut_state_from_mesh(b) is not None,
        "source_has_boss_state": _boss_state_from_mesh(a) is not None,
        "cutter_has_boss_state": _boss_state_from_mesh(b) is not None,
        "result_face_count": len(mesh.faces),
        "result_watertight": bool(mesh.is_watertight),
    }
    return mesh


def _record_exact_reference_boolean_result(
    mesh: trimesh.Trimesh,
    *,
    op: str,
) -> trimesh.Trimesh:
    if not isinstance(mesh, trimesh.Trimesh):
        return mesh
    exact = mesh.metadata.get(_EXACT_BOOLEAN_METADATA_KEY)
    if not isinstance(exact, dict):
        return mesh
    exact.setdefault("op", op)
    exact.setdefault("attempted_backend", "lathe.reference.exact_boolean")
    exact.setdefault("actual_backend", "lathe.reference.exact_boolean")
    exact.setdefault("actual_operation", str(exact.get("method") or f"exact_{op}"))
    exact.setdefault("exact_kernel_path", True)
    exact.setdefault("fallback", False)
    exact.setdefault("passthrough", False)
    exact.setdefault("result_face_count", len(mesh.faces))
    exact.setdefault("result_vertex_count", len(mesh.vertices))
    exact.setdefault("result_watertight", bool(mesh.is_watertight))
    if "result_body_count" not in exact:
        try:
            exact["result_body_count"] = (
                len(mesh.split(only_watertight=False)) if len(mesh.faces) else 0
            )
        except (AttributeError, TypeError, ValueError):
            exact["result_body_count"] = 0
    mesh.metadata[_EXACT_BOOLEAN_METADATA_KEY] = exact
    return mesh


def _record_reference_batch_union_result(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    if not isinstance(mesh, trimesh.Trimesh):
        return mesh
    payload = mesh.metadata.get("lathe_reference_batch_union")
    if not isinstance(payload, dict):
        return mesh
    payload.setdefault("attempted_backend", "lathe.reference.batch_union")
    payload.setdefault("actual_backend", "lathe.reference.batch_union")
    payload.setdefault(
        "actual_operation",
        str(payload.get("method") or "batch_union"),
    )
    payload.setdefault("fallback", False)
    payload.setdefault("passthrough", False)
    payload.setdefault("result_face_count", len(mesh.faces))
    payload.setdefault("result_vertex_count", len(mesh.vertices))
    payload.setdefault("result_watertight", bool(mesh.is_watertight))
    if "result_body_count" not in payload:
        try:
            payload["result_body_count"] = (
                len(mesh.split(only_watertight=False)) if len(mesh.faces) else 0
            )
        except (AttributeError, TypeError, ValueError):
            payload["result_body_count"] = 0
    mesh.metadata["lathe_reference_batch_union"] = payload
    return mesh


class ReferenceKernel:
    """Trimesh-backed geometry kernel (always available)."""

    name = REFERENCE_KERNEL_ID
    version = "0.1"

    def probe(self) -> dict[str, Any]:
        """Availability + capability metadata."""
        return {
            "name": self.name,
            "version": self.version,
            "available": True,
            "capabilities": {
                "union": True,
                "difference": True,
                "intersection": True,
                "hull": True,
                "transform": True,
                "deform_program": True,
                "refine_program": True,
                "carve_program": True,
                "polyextrude_program": True,
                "component_assembly_program": True,
                "profile_path_program": True,
                "sdf_field_program": True,
                "terrain_field_program": True,
                "scatter_program": True,
                "pattern_instances_program": True,
                "edge_control_program": True,
                "edge_treatment_program": True,
                "feature_detail_program": True,
                "surface_damage_program": True,
                "hull_execution_metadata": True,
                "transform_execution_metadata": True,
                "batch_union": True,
                "additive_batch_union": True,
                "overlapping_additive_batch_union": True,
                "voxel_boolean_fallback": True,
                "exact_bounds_disjoint_difference": True,
                "exact_bounds_disjoint_intersection": True,
                "boolean_execution_metadata": True,
                "exact_axis_aligned_box_union": True,
                "exact_axis_aligned_box_batch_union": True,
                "exact_axis_aligned_box_cylinder_boss_union": True,
                "exact_axis_aligned_box_repeated_cylinder_boss_union": True,
                "exact_axis_aligned_box_cylinder_boss_batch_union": True,
                "exact_axis_aligned_box_beveled_cylinder_boss_union": True,
                "exact_axis_aligned_box_revolved_profile_boss_union": True,
                "exact_axis_aligned_box_repeated_profile_boss_union": True,
                "exact_axis_aligned_box_nested_boss_union": True,
                "exact_axis_aligned_box_profile_boss_batch_union": True,
                "exact_axis_aligned_box_detail_boss_batch_union": True,
                "exact_axis_aligned_profile_cut_state_box_cylinder_boss_union": True,
                "exact_axis_aligned_profile_cut_state_box_profile_boss_union": True,
                "exact_axis_aligned_profile_cut_state_box_blind_detail_boss_union": True,
                "exact_axis_aligned_profile_cut_state_box_cylinder_boss_batch_union": True,
                "exact_axis_aligned_profile_cut_state_box_profile_boss_batch_union": True,
                "exact_axis_aligned_profile_cut_state_box_blind_detail_boss_batch_union": True,
                "exact_axis_aligned_profile_cut_state_box_detail_boss_batch_union": True,
                "exact_axis_aligned_boss_state_through_box_profile_difference": True,
                "exact_axis_aligned_boss_state_repeated_through_box_profile_difference": True,
                "exact_axis_aligned_boss_state_through_cylinder_difference": True,
                "exact_axis_aligned_boss_state_repeated_through_cylinder_difference": True,
                "exact_axis_aligned_boss_state_through_profile_difference": True,
                "exact_axis_aligned_boss_state_repeated_through_profile_difference": True,
                "exact_axis_aligned_boss_state_through_profile_bevel_difference": True,
                "exact_axis_aligned_boss_state_through_revolved_profile_difference": True,
                "exact_axis_aligned_boss_state_repeated_through_revolved_profile_difference": True,
                "exact_axis_aligned_box_difference": True,
                "exact_axis_aligned_box_intersection": True,
                "exact_extruded_profile_extruded_profile_difference": True,
                "exact_extruded_profile_through_extruded_profile_difference": True,
                "exact_extruded_profile_segment_extruded_profile_difference": True,
                "exact_axis_aligned_box_through_extruded_profile_difference": True,
                "exact_axis_aligned_box_repeated_through_extruded_profile_difference": True,
                "exact_axis_aligned_box_open_through_extruded_profile_difference": True,
                "sampled_axis_aligned_box_open_through_profile_bevel_difference": True,
                "exact_axis_aligned_box_through_revolved_profile_difference": True,
                "exact_axis_aligned_box_repeated_through_revolved_profile_difference": True,
                "exact_axis_aligned_box_mixed_through_profile_difference": True,
                "exact_axis_aligned_box_mixed_open_through_profile_difference": True,
                "exact_axis_aligned_box_blind_extruded_profile_difference": True,
                "exact_axis_aligned_box_repeated_blind_extruded_profile_difference": True,
                "exact_axis_aligned_box_blind_box_profile_difference": True,
                "exact_axis_aligned_box_repeated_blind_box_profile_difference": True,
                "exact_axis_aligned_box_blind_revolved_profile_difference": True,
                "exact_axis_aligned_box_repeated_blind_revolved_profile_difference": True,
                "exact_axis_aligned_box_blind_cylinder_difference": True,
                "exact_axis_aligned_box_repeated_blind_cylinder_difference": True,
                "exact_axis_aligned_box_mixed_blind_profile_difference": True,
                "exact_axis_aligned_box_mixed_blind_profile_per_cut_depth_difference": True,
                "exact_axis_aligned_box_clipped_blind_profile_difference": True,
                "sampled_axis_aligned_box_blind_profile_bevel_difference": True,
                "sampled_axis_aligned_box_clipped_blind_profile_bevel_difference": True,
                "backend_assisted_blind_profile_state_difference": True,
                "exact_axis_aligned_box_profile_state_through_box_difference": True,
                "exact_axis_aligned_box_profile_state_open_through_box_difference": True,
                "exact_axis_aligned_box_through_cylinder_difference": True,
                "from_trimesh": True,
                "box": True,
                "box_rounding": True,
                "exact_modifier_import": True,
                "cylinder": True,
                "sphere": True,
                "capsule": True,
                "revolved_profile": True,
                "partial_revolved_profile": True,
                "extruded_profile": True,
                "generalized_extruded_profile": True,
                "rounded_slot": True,
                "socket": True,
                "countersunk_hole": True,
                "countersunk_hole_set": True,
                "panel": True,
                "panel_frame": True,
                "panel_line_cut": True,
                "inset_cut": True,
                "perforated_panel": True,
                "fastener_grid": True,
                "weld_seam": True,
                "dent_mask_set": True,
                "edge_chip_set": True,
                "surface_patch_set": True,
                "hinge": True,
                "handle": True,
                "corner_guard_set": True,
                "structural_beam": True,
                "rail": True,
                "ribbed_panel": True,
                "louver_panel": True,
                "vent_slats": True,
                "ladder_frame": True,
                "truss_frame": True,
                "support_bracket": True,
                "trim_band": True,
                "torus": True,
                "tube": True,
                "gear": True,
                "flange": True,
                "subdivision_box": True,
                "swept_profile": True,
                "helical_sweep": True,
                "spring": True,
                "threaded_cylinder": True,
                "curved_tube": True,
                "lofted_solid": True,
                "heightfield": True,
                "heightfield_solid_import": True,
                "terrain_patch": True,
                "terrain_patch_import": True,
                "sdf_mesh": True,
                "sdf_mesh_import": True,
                "sdf_metaball_cluster": True,
                "sdf_metaball_cluster_import": True,
                "terrain_mesh": True,
                "terrain_mesh_import": True,
                "kernel_primitive_mesh": True,
                "kernel_primitive_mesh_import": True,
                "instance_mesh": True,
                "instance_mesh_import": True,
                "polybevel_mesh": True,
                "polybevel_mesh_import": True,
                "profile_mesh": True,
                "profile_mesh_import": True,
                "construction_feature_mesh": True,
                "construction_feature_mesh_import": True,
                "edge_control_mesh": True,
                "edge_control_mesh_import": True,
                "hull_mesh": True,
                "hull_mesh_import": True,
                "minkowski_mesh": True,
                "minkowski_mesh_import": True,
                "subdivision_mesh": True,
                "subdivision_mesh_import": True,
                "remesh_mesh": True,
                "remesh_mesh_import": True,
                "deform_mesh": True,
                "deform_mesh_import": True,
                "boolean_mesh": True,
                "boolean_mesh_import": True,
                "component_assembly_mesh": True,
                "component_assembly_mesh_import": True,
                "component_assembly": True,
                "to_trimesh": True,
                "body_count": True,
                "watertight_by_construction": False,
            },
            "notes": (
                "Trimesh booleans depend on an available engine and may "
                "emit non-watertight output on dense / coplanar scenes."
            ),
        }

    def build_primitive(self, kind: str, **params: Any) -> trimesh.Trimesh:
        """Create a primitive trimesh handle."""
        center = tuple(float(v) for v in params.get("center", (0.0, 0.0, 0.0)))
        if _requires_exact_import(kind, params):
            from ..exact_solids import primitive_mesh

            primitive = _shape_primitive_from_params(kind, params)
            return self.from_trimesh(primitive_mesh(primitive))

        if kind in {
            "revolved_profile",
            "extruded_profile",
            "rounded_slot",
            "socket",
            "countersunk_hole",
            "countersunk_hole_set",
            "panel",
            "panel_frame",
            "panel_line_cut",
            "inset_cut",
            "perforated_panel",
            "fastener_grid",
            "weld_seam",
            "dent_mask_set",
            "edge_chip_set",
            "surface_patch_set",
            "hinge",
            "handle",
            "corner_guard_set",
            "structural_beam",
            "rail",
            "ribbed_panel",
            "louver_panel",
            "vent_slats",
            "ladder_frame",
            "truss_frame",
            "support_bracket",
            "trim_band",
            "torus",
            "tube",
            "gear",
            "flange",
            "subdivision_box",
            "swept_profile",
            "helical_sweep",
            "spring",
            "threaded_cylinder",
            "curved_tube",
            "lofted_solid",
            "heightfield",
            "terrain_patch",
            "sdf_mesh",
            "sdf_metaball_cluster",
            "terrain_mesh",
            "kernel_primitive_mesh",
            "instance_mesh",
            "polybevel_mesh",
            "profile_mesh",
            "construction_feature_mesh",
            "edge_control_mesh",
            "hull_mesh",
            "minkowski_mesh",
            "subdivision_mesh",
            "remesh_mesh",
            "deform_mesh",
            "boolean_mesh",
            "component_assembly_mesh",
            "component_assembly",
        }:
            from ..exact_solids import primitive_mesh

            primitive = _shape_primitive_from_params(kind, params)
            mesh = primitive_mesh(primitive)
            if kind in {"heightfield", "terrain_patch"} and not bool(mesh.is_watertight):
                from .shape_ir_lowering import _solidify_heightfield_mesh

                mesh, _ = _solidify_heightfield_mesh(mesh)
            return self.from_trimesh(mesh)

        if kind == "box":
            extents = params.get("extents")
            if extents is None:
                raise _BoxExtentsRequiredError
            rounding = float(params.get("rounding") or params.get("rounding_cm") or 0.0)
            if rounding > 1e-9:
                from ..exact_solids import primitive_mesh

                primitive = _shape_primitive_from_params(kind, params)
                mesh = primitive_mesh(primitive)
                mesh.metadata[_PRIMITIVE_METADATA_KEY] = {
                    "schema": "lathe.geometry.reference_primitive.v1",
                    "method": "rounded_box_exact_mesh_build_primitive_v1",
                    "primitive_type": "box",
                    "rounding_cm": float(rounding),
                    "requested_backend": "lathe.geometry.reference_v1.build_primitive",
                    "actual_backend": "lathe.exact_solids.rounded_box",
                    "fallback": False,
                    "passthrough": False,
                    "result_face_count": len(mesh.faces),
                    "result_watertight": bool(mesh.is_watertight),
                }
                _record_shape_primitive_metadata_from_params(mesh, kind, params)
                return self.from_trimesh(mesh)
            extents_array = np.asarray(list(extents), dtype=np.float64)
            center_array = np.asarray(center, dtype=np.float64)
            half = extents_array * 0.5
            mesh = _axis_aligned_box_mesh(
                bounds_min=center_array - half,
                bounds_max=center_array + half,
            )
            _record_shape_primitive_metadata_from_params(mesh, kind, params)
            return mesh

        if kind == "cylinder":
            radius = params.get("radius")
            height = params.get("height")
            if radius is None or height is None:
                raise _CylinderDimensionsRequiredError
            axis = params.get("axis", "y")
            segments = int(params.get("segments", 32))
            mesh = trimesh.creation.cylinder(radius=float(radius), height=float(height), sections=segments)
            if axis == "x":
                mesh.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, [0.0, 1.0, 0.0]))
            elif axis == "y":
                mesh.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, [1.0, 0.0, 0.0]))
            translation = np.eye(4)
            translation[:3, 3] = np.array(center, dtype=float)
            mesh.apply_transform(translation)
            _record_cylinder_metadata(
                mesh,
                center=np.asarray(center, dtype=np.float64),
                radius=float(radius),
                height=float(height),
                axis=str(axis),
                part=str(params.get("part") or "cylinder"),
            )
            _record_shape_primitive_metadata_from_params(mesh, kind, params)
            return mesh

        if kind == "capsule":
            radius = params.get("radius")
            length = params.get("length")
            if radius is None or length is None:
                raise _CapsuleDimensionsRequiredError
            radius_value = float(radius)
            length_value = float(length)
            if radius_value <= 0.0 or length_value <= radius_value * 2.0:
                raise _CapsuleDimensionsRequiredError
            axis = str(params.get("axis", "y"))
            sections = max(8, min(128, int(params.get("sections") or params.get("segments") or 32)))
            rings = max(4, min(64, int(params.get("rings") or max(6, sections // 2))))
            shaft_length = length_value - radius_value * 2.0
            mesh = trimesh.creation.capsule(
                height=shaft_length,
                radius=radius_value,
                count=(rings, sections),
            )
            if axis == "x":
                mesh.apply_transform(
                    trimesh.transformations.rotation_matrix(math.pi / 2.0, [0.0, 1.0, 0.0])
                )
            elif axis == "y":
                mesh.apply_transform(
                    trimesh.transformations.rotation_matrix(-math.pi / 2.0, [1.0, 0.0, 0.0])
                )
            elif axis != "z":
                raise ValueError("capsule axis must be one of: x, y, z")
            translation = np.eye(4)
            translation[:3, 3] = np.asarray(center, dtype=np.float64)
            mesh.apply_transform(translation)
            mesh.remove_unreferenced_vertices()
            mesh.merge_vertices()
            mesh.fix_normals()
            mesh.metadata["lathe_reference_primitive"] = {
                "schema": "lathe.geometry.reference_primitive.v1",
                "kind": "capsule",
                "method": "trimesh_creation_capsule_v1",
                "center": [float(value) for value in center],
                "radius": radius_value,
                "length": length_value,
                "shaft_length": shaft_length,
                "axis": axis,
                "sections": sections,
                "rings": rings,
                "result_face_count": len(mesh.faces),
                "result_watertight": bool(mesh.is_watertight),
            }
            _record_shape_primitive_metadata_from_params(mesh, kind, params)
            return mesh

        if kind == "sphere":
            radius = params.get("radius")
            if radius is None:
                raise _SphereRadiusRequiredError
            segments = int(params.get("segments", 32))
            mesh = trimesh.creation.icosphere(
                subdivisions=max(1, int(math.log2(max(2, segments // 4)))),
                radius=float(radius),
            )
            translation = np.eye(4)
            translation[:3, 3] = np.array(center, dtype=float)
            mesh.apply_transform(translation)
            _record_shape_primitive_metadata_from_params(mesh, kind, params)
            return mesh

        raise _UnsupportedPrimitiveKindError(kind)

    def from_trimesh(self, mesh: trimesh.Trimesh) -> trimesh.Trimesh:
        """Import an authored/exact mesh as the reference-kernel handle."""
        candidate = mesh.copy()
        candidate.remove_infinite_values()
        candidate.remove_unreferenced_vertices()
        if not bool(candidate.is_watertight):
            candidate.merge_vertices()
        candidate.fix_normals()
        return candidate

    def _boolean(self, op: str, a: trimesh.Trimesh, b: trimesh.Trimesh) -> trimesh.Trimesh:
        def exact(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
            return _record_exact_reference_boolean_result(mesh, op=op)

        if op in {"difference", "intersection"} and not _bounds_overlap(a, b):
            if op == "difference":
                result = a.copy()
                try:
                    body_count = (
                        len(result.split(only_watertight=False))
                        if len(result.faces)
                        else 0
                    )
                except (AttributeError, TypeError, ValueError):
                    body_count = 0
            else:
                result = trimesh.Trimesh()
                body_count = 0
            result.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
                "schema": "lathe.geometry.reference_exact_boolean.v1",
                "method": f"bounds_disjoint_{op}_v1",
                "op": op,
                "attempted_backend": "lathe.reference.bounds_test",
                "actual_backend": "lathe.reference.bounds_test",
                "actual_operation": f"bounds_disjoint_{op}",
                "exact_kernel_path": True,
                "fallback": False,
                "overlap": False,
                "piece_count": 1 if op == "difference" and len(result.faces) else 0,
                "passthrough": False,
                "result_face_count": len(result.faces),
                "result_watertight": bool(result.is_watertight),
                "result_body_count": int(body_count),
            }
            return exact(result)
        exact_result = _exact_axis_aligned_box_boolean(op, a, b)
        if exact_result is not None:
            return exact(exact_result)
        if op == "union":
            disjoint = _disjoint_additive_batch_union([a, b])
            if disjoint is not None:
                return _record_reference_batch_union_result(disjoint)
            exact_result = _exact_profile_cut_state_box_detail_union(a, b)
            if exact_result is not None:
                return exact(exact_result)
            exact_result = _exact_axis_aligned_box_cylinder_boss_union(a, b)
            if exact_result is not None:
                return exact(exact_result)
            exact_result = _exact_boss_state_box_union(a, b)
            if exact_result is not None:
                return exact(exact_result)
            profile_additive = _profile_cut_state_additive_batch_union([a, b])
            if profile_additive is not None:
                batch_payload = profile_additive.metadata.get("lathe_reference_batch_union")
                method = (
                    str(batch_payload.get("method") or "profile_cut_state_additive_mesh_concatenation_v1")
                    if isinstance(batch_payload, dict)
                    else "profile_cut_state_additive_mesh_concatenation_v1"
                )
                profile_additive.metadata[_EXACT_BOOLEAN_METADATA_KEY] = {
                    "schema": "lathe.geometry.reference_exact_boolean.v1",
                    "method": method,
                    "op": "union",
                    "overlap": True,
                    "passthrough": False,
                    "profile_cut_state_operand_count": (
                        int(batch_payload.get("profile_cut_state_operand_count") or 0)
                        if isinstance(batch_payload, dict)
                        else 0
                    ),
                    "result_face_count": len(profile_additive.faces),
                    "result_watertight": bool(profile_additive.is_watertight),
                }
                return _record_reference_batch_union_result(exact(profile_additive))
        if op == "difference":
            exact_result = _exact_boss_state_box_difference(a, b)
            if exact_result is not None:
                return exact(exact_result)
            exact_result = _exact_boss_state_extruded_profile_difference(a, b)
            if exact_result is not None:
                return exact(exact_result)
            exact_result = _exact_boss_state_revolved_profile_difference(a, b)
            if exact_result is not None:
                return exact(exact_result)
            exact_result = _exact_boss_state_cylinder_difference(a, b)
            if exact_result is not None:
                return exact(exact_result)
            exact_result = _exact_axis_aligned_box_extruded_profile_difference(a, b)
            if exact_result is not None:
                return exact(exact_result)
            exact_result = _exact_extruded_profile_extruded_profile_difference(a, b)
            if exact_result is not None:
                return exact(exact_result)
            exact_result = _exact_axis_aligned_box_revolved_profile_difference(a, b)
            if exact_result is not None:
                return exact(exact_result)
            exact_result = _exact_axis_aligned_box_cylinder_difference(a, b)
            if exact_result is not None:
                return exact(exact_result)
        sdf_result = _sdf_boolean(op, a, b)
        if sdf_result is not None:
            return sdf_result
        sourcewise = self._sourcewise_batch_boolean(op, a, b)
        if sourcewise is not None:
            return sourcewise
        # trimesh.boolean.{union,difference,intersection} accept an iterable.
        fn = getattr(trimesh.boolean, op)
        try:
            result = fn([a, b])
        except (ImportError, ValueError, RuntimeError, AttributeError, TypeError) as exc:
            # Fall back to concatenation/passthrough for union when no engine is present;
            # caller contract is "best-effort CSG", not watertightness.
            fallback = {
                "schema": "lathe.geometry.reference_boolean_fallback.v1",
                "op": op,
                "reason": "trimesh_boolean_engine_unavailable_or_failed",
                "exception_type": type(exc).__name__,
                "exception": str(exc),
                "passthrough": True,
            }
            voxel_result = _voxel_boolean(op, a, b)
            if voxel_result is not None:
                mesh, voxel_details = voxel_result
                mesh.metadata["lathe_reference_boolean_fallback"] = {
                    **fallback,
                    **voxel_details,
                }
                return mesh
            if op == "union":
                mesh = trimesh.util.concatenate([a, b])
                mesh.metadata["lathe_reference_boolean_fallback"] = {
                    **fallback,
                    "actual_backend": "trimesh.util.concatenate",
                    "actual_operation": "additive_mesh_concatenation",
                }
                return mesh
            if op == "difference":
                mesh = a.copy()
                mesh.metadata["lathe_reference_boolean_fallback"] = {
                    **fallback,
                    "actual_backend": "left_operand_passthrough",
                    "actual_operation": "difference_unexecuted_passthrough",
                }
                return mesh
            if op == "intersection":
                mesh = a.copy()
                mesh.metadata["lathe_reference_boolean_fallback"] = {
                    **fallback,
                    "actual_backend": "left_operand_passthrough",
                    "actual_operation": "intersection_unexecuted_passthrough",
                }
                return mesh
            raise
        if isinstance(result, list):
            if not result:
                return trimesh.Trimesh()
            mesh = trimesh.util.concatenate(result) if len(result) > 1 else result[0]
            return _record_successful_backend_boolean(mesh, op=op, a=a, b=b)
        return _record_successful_backend_boolean(result, op=op, a=a, b=b)

    def _sourcewise_batch_boolean(
        self,
        op: str,
        a: trimesh.Trimesh,
        b: trimesh.Trimesh,
    ) -> trimesh.Trimesh | None:
        if op not in {"difference", "intersection"}:
            return None
        sources = _batch_source_meshes(a) or _compound_source_meshes_from_metadata(a)
        decomposed_cutter_sources = (
            _batch_source_meshes(b)
            or _compound_source_meshes_from_metadata(b)
        )
        source_origin = "left_operand_sources"
        if not sources:
            if not decomposed_cutter_sources or len(a.faces) == 0:
                return None
            sources = (a.copy(),)
            source_origin = "single_left_operand"
        cutter_sources = decomposed_cutter_sources or (b,)

        pieces: list[trimesh.Trimesh] = []
        affected = 0
        affected_pairs = 0
        nested_fallbacks: list[dict[str, Any]] = []
        nested_exact_booleans: list[dict[str, Any]] = []
        nested_backend_booleans: list[dict[str, Any]] = []
        passthrough = False

        def record_nested_result(result: trimesh.Trimesh) -> None:
            nonlocal passthrough
            fallback = result.metadata.get("lathe_reference_boolean_fallback")
            if isinstance(fallback, dict):
                nested_fallbacks.append(dict(fallback))
                passthrough = passthrough or bool(fallback.get("passthrough", True))
            exact = result.metadata.get(_EXACT_BOOLEAN_METADATA_KEY)
            if isinstance(exact, dict):
                nested_exact_booleans.append(dict(exact))
            backend = result.metadata.get("lathe_reference_boolean_backend")
            if isinstance(backend, dict):
                nested_backend_booleans.append(dict(backend))

        for source in sources:
            overlapping_cutters = [
                cutter
                for cutter in cutter_sources
                if _bounds_overlap(source, cutter)
            ]
            if not overlapping_cutters:
                if op == "difference":
                    pieces.append(source.copy())
                continue
            affected += 1
            affected_pairs += len(overlapping_cutters)
            if op == "difference":
                current_pieces = [source.copy()]
                for cutter in overlapping_cutters:
                    next_pieces: list[trimesh.Trimesh] = []
                    for piece in current_pieces:
                        if not _bounds_overlap(piece, cutter):
                            next_pieces.append(piece)
                            continue
                        result = self._boolean(op, piece, cutter)
                        record_nested_result(result)
                        if len(result.faces) > 0:
                            next_pieces.append(result)
                    current_pieces = next_pieces
                    if not current_pieces:
                        break
                pieces.extend(current_pieces)
                continue

            for cutter in overlapping_cutters:
                result = self._boolean(op, source, cutter)
                record_nested_result(result)
                if len(result.faces) > 0:
                    pieces.append(result)

        if op == "difference" and affected == 0:
            result = a.copy()
            _set_batch_source_meshes(result, sources)
        elif not pieces:
            result = trimesh.Trimesh()
            _set_batch_source_meshes(result, ())
        else:
            result = trimesh.util.concatenate(pieces) if len(pieces) > 1 else pieces[0].copy()
            _set_batch_source_meshes(result, pieces)
            result.remove_unreferenced_vertices()
            result.fix_normals()

        decomposition = {
            "schema": "lathe.geometry.reference_sourcewise_boolean.v1",
            "op": op,
            "method": "batch_union_sourcewise_boolean_v1",
            "source_count": len(sources),
            "source_origin": source_origin,
            "cutter_source_count": len(cutter_sources),
            "affected_source_count": affected,
            "affected_source_cutter_pair_count": affected_pairs,
            "result_source_count": len(_batch_source_meshes(result)),
            "nested_exact_boolean_count": len(nested_exact_booleans),
            "nested_exact_boolean_methods": sorted(
                {
                    str(record.get("method") or "")
                    for record in nested_exact_booleans
                    if record.get("method")
                }
            ),
            "nested_backend_boolean_count": len(nested_backend_booleans),
            "nested_backend_boolean_methods": sorted(
                {
                    str(record.get("method") or "")
                    for record in nested_backend_booleans
                    if record.get("method")
                }
            ),
            "nested_fallback_count": len(nested_fallbacks),
            "passthrough_nested_fallback": passthrough,
        }
        result.metadata["lathe_reference_boolean_decomposition"] = decomposition
        if nested_exact_booleans:
            result.metadata["lathe_reference_nested_exact_booleans"] = nested_exact_booleans
        if nested_backend_booleans:
            result.metadata["lathe_reference_nested_backend_booleans"] = nested_backend_booleans
        if nested_fallbacks:
            result.metadata["lathe_reference_boolean_fallback"] = {
                "schema": "lathe.geometry.reference_boolean_fallback.v1",
                "op": op,
                "method": "batch_union_sourcewise_boolean_v1",
                "reason": "sourcewise_boolean_used_nested_fallback",
                "passthrough": passthrough,
                "nested_fallback_count": len(nested_fallbacks),
                "source_count": len(sources),
                "cutter_source_count": len(cutter_sources),
                "affected_source_count": affected,
                "affected_source_cutter_pair_count": affected_pairs,
            }
        return result

    def union(self, a: trimesh.Trimesh, b: trimesh.Trimesh) -> trimesh.Trimesh:
        """Return the boolean union of two trimesh handles."""
        return self._boolean("union", a, b)

    def difference(self, a: trimesh.Trimesh, b: trimesh.Trimesh) -> trimesh.Trimesh:
        """Return the boolean difference of two trimesh handles."""
        return self._boolean("difference", a, b)

    def intersection(self, a: trimesh.Trimesh, b: trimesh.Trimesh) -> trimesh.Trimesh:
        """Return the boolean intersection of two trimesh handles."""
        return self._boolean("intersection", a, b)

    def _pairwise_batch_union(
        self,
        meshes: list[trimesh.Trimesh],
        *,
        original_operand_count: int,
        expanded: bool,
    ) -> trimesh.Trimesh | None:
        if len(meshes) < 2 or len(meshes) > 64:
            return None
        current = meshes[0].copy()
        nested_exact: list[dict[str, Any]] = []
        nested_backend: list[dict[str, Any]] = []
        nested_fallback: list[dict[str, Any]] = []
        passthrough = False
        for mesh in meshes[1:]:
            current = self.union(current, mesh)
            if len(current.faces) == 0:
                return None
            fallback = current.metadata.get("lathe_reference_boolean_fallback")
            if isinstance(fallback, dict):
                nested_fallback.append(dict(fallback))
                passthrough = passthrough or bool(fallback.get("passthrough", True))
            exact = current.metadata.get(_EXACT_BOOLEAN_METADATA_KEY)
            if isinstance(exact, dict):
                nested_exact.append(dict(exact))
            backend = current.metadata.get("lathe_reference_boolean_backend")
            if isinstance(backend, dict):
                nested_backend.append(dict(backend))
        if passthrough:
            return None
        try:
            body_count = len(current.split(only_watertight=False)) if len(current.faces) else 0
        except (AttributeError, TypeError, ValueError):
            return None
        source_face_count = sum(len(mesh.faces) for mesh in meshes)
        largest_source_face_count = max((len(mesh.faces) for mesh in meshes), default=0)
        if expanded and len(current.faces) < largest_source_face_count:
            current.metadata["lathe_reference_boolean_fallback"] = {
                "schema": "lathe.geometry.reference_boolean_fallback.v1",
                "op": "batch_union",
                "method": "pairwise_boolean_batch_union_v1",
                "reason": "pairwise_batch_union_collapsed_compound_visible_operand",
                "passthrough": False,
                "source_face_count": int(source_face_count),
                "largest_source_face_count": int(largest_source_face_count),
                "result_face_count": int(len(current.faces)),
            }
            return None
        if not bool(current.is_watertight) or body_count != 1:
            return None
        method = "pairwise_boolean_batch_union_v1"
        payload = {
            "schema": "lathe.geometry.reference_batch_union.v1",
            "method": method,
            "operand_count": original_operand_count,
            "expanded_operand_count": len(meshes),
            "compound_source_expansion": bool(expanded),
            "nested_exact_boolean_count": len(nested_exact),
            "nested_backend_boolean_count": len(nested_backend),
            "nested_fallback_count": len(nested_fallback),
            "passthrough_nested_fallback": False,
            "result_face_count": len(current.faces),
            "result_watertight": bool(current.is_watertight),
            "result_body_count": body_count,
        }
        if nested_exact:
            payload["nested_exact_boolean_methods"] = sorted(
                {
                    str(record.get("method") or "")
                    for record in nested_exact
                    if record.get("method")
                }
            )
            current.metadata["lathe_reference_nested_exact_booleans"] = nested_exact
        if nested_backend:
            payload["nested_backend_boolean_methods"] = sorted(
                {
                    str(record.get("method") or "")
                    for record in nested_backend
                    if record.get("method")
                }
            )
            current.metadata["lathe_reference_nested_backend_booleans"] = nested_backend
        if nested_fallback:
            current.metadata["lathe_reference_boolean_fallback"] = {
                "schema": "lathe.geometry.reference_boolean_fallback.v1",
                "op": "batch_union",
                "method": method,
                "reason": "pairwise_batch_union_used_nested_fallback",
                "passthrough": False,
                "nested_fallback_count": len(nested_fallback),
            }
        current.metadata["lathe_reference_batch_union"] = payload
        _set_batch_source_meshes(current, (current,))
        return current

    def batch_union(self, meshes: Iterable[trimesh.Trimesh]) -> trimesh.Trimesh:
        """Return a deterministic additive assembly of many mesh handles.

        The reference kernel is the always-available path. When Lathe is
        assembling visible additive details, concatenating already-solid
        operands is the truthful operation: it preserves every authored part
        without depending on an external boolean engine. Destructive CSG still
        goes through ``difference`` / ``intersection`` and reports fallback
        diagnostics if trimesh has no boolean engine.
        """
        def batch(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
            return _record_reference_batch_union_result(mesh)

        seq = [mesh.copy() for mesh in meshes]
        if not seq:
            raise _BatchUnionEmptyError
        exact = _exact_profile_cut_state_box_detail_batch_union(seq)
        if exact is not None:
            return batch(exact)
        exact = _exact_axis_aligned_box_detail_boss_batch_union(seq)
        if exact is not None:
            return batch(exact)
        early_expanded_seq, early_expanded = _expand_compound_batch_union_sources(seq)
        if early_expanded:
            exact = _exact_profile_cut_state_box_detail_batch_union(early_expanded_seq)
            if exact is not None:
                return batch(
                    _mark_expanded_batch_union_result(
                        exact,
                        original_operand_count=len(seq),
                        expanded_operand_count=len(early_expanded_seq),
                    )
                )
            exact = _exact_axis_aligned_box_detail_boss_batch_union(early_expanded_seq)
            if exact is not None:
                return batch(
                    _mark_expanded_batch_union_result(
                        exact,
                        original_operand_count=len(seq),
                        expanded_operand_count=len(early_expanded_seq),
                    )
                )
        disjoint = _disjoint_additive_batch_union(seq)
        if disjoint is not None:
            return batch(disjoint)
        groups = _overlap_connected_mesh_groups(seq)
        if len(groups) > 1:
            group_results = [
                group[0].copy() if len(group) == 1 else self.batch_union(group)
                for group in groups
            ]
            result = trimesh.util.concatenate(group_results)
            result.remove_unreferenced_vertices()
            result.fix_normals()
            body_count = len(result.split(only_watertight=False)) if len(result.faces) else 0
            result.metadata["lathe_reference_batch_union"] = {
                "schema": "lathe.geometry.reference_batch_union.v1",
                "method": "overlap_grouped_additive_batch_union",
                "operand_count": len(seq),
                "group_count": len(groups),
                "group_operand_counts": [len(group) for group in groups],
                "reason": "reference_kernel_preserved_disjoint_additive_groups",
                "result_face_count": len(result.faces),
                "result_watertight": bool(result.is_watertight),
                "result_body_count": int(body_count),
            }
            return batch(_set_batch_source_meshes(result, group_results))
        expanded_seq, expanded = _expand_compound_batch_union_sources(seq)
        exact_inputs = expanded_seq if expanded else seq
        exact = _exact_profile_cut_state_box_detail_batch_union(exact_inputs)
        if exact is not None:
            return batch(
                (
                    _mark_expanded_batch_union_result(
                        exact,
                        original_operand_count=len(seq),
                        expanded_operand_count=len(exact_inputs),
                    )
                    if expanded
                    else exact
                )
            )
        exact = _exact_axis_aligned_box_detail_boss_batch_union(exact_inputs)
        if exact is not None:
            return batch(
                (
                    _mark_expanded_batch_union_result(
                        exact,
                        original_operand_count=len(seq),
                        expanded_operand_count=len(exact_inputs),
                    )
                    if expanded
                    else exact
                )
            )
        disjoint = _disjoint_additive_batch_union(exact_inputs)
        if disjoint is not None:
            return batch(
                (
                    _mark_expanded_batch_union_result(
                        disjoint,
                        original_operand_count=len(seq),
                        expanded_operand_count=len(exact_inputs),
                    )
                    if expanded
                    else disjoint
                )
            )
        exact = _exact_axis_aligned_box_detail_boss_batch_union(exact_inputs)
        if exact is not None:
            return batch(
                (
                    _mark_expanded_batch_union_result(
                        exact,
                        original_operand_count=len(seq),
                        expanded_operand_count=len(exact_inputs),
                    )
                    if expanded
                    else exact
                )
            )
        exact = _exact_axis_aligned_box_extruded_profile_batch_union(exact_inputs)
        if exact is not None:
            return batch(
                (
                    _mark_expanded_batch_union_result(
                        exact,
                        original_operand_count=len(seq),
                        expanded_operand_count=len(exact_inputs),
                    )
                    if expanded
                    else exact
                )
            )
        exact = _exact_axis_aligned_box_batch_union(exact_inputs)
        if exact is not None:
            return batch(
                (
                    _mark_expanded_batch_union_result(
                        exact,
                        original_operand_count=len(seq),
                        expanded_operand_count=len(exact_inputs),
                    )
                    if expanded
                    else exact
                )
            )
        exact = _exact_axis_aligned_box_cylinder_boss_batch_union(exact_inputs)
        if exact is not None:
            return batch(
                (
                    _mark_expanded_batch_union_result(
                        exact,
                        original_operand_count=len(seq),
                        expanded_operand_count=len(exact_inputs),
                    )
                    if expanded
                    else exact
                )
            )
        profile_additive = _profile_cut_state_additive_batch_union(exact_inputs)
        if profile_additive is not None:
            return batch(
                (
                    _mark_expanded_batch_union_result(
                        profile_additive,
                        original_operand_count=len(seq),
                        expanded_operand_count=len(exact_inputs),
                    )
                    if expanded
                    else profile_additive
                )
            )
        graph_union = _circular_swept_profile_graph_batch_union(
            exact_inputs,
            original_operand_count=len(seq),
            expanded_operand_count=len(exact_inputs),
        )
        if graph_union is not None:
            return batch(
                (
                    _mark_expanded_batch_union_result(
                        graph_union,
                        original_operand_count=len(seq),
                        expanded_operand_count=len(exact_inputs),
                    )
                    if expanded
                    else graph_union
                )
            )
        sdf_union = _sdf_primitive_batch_union(
            exact_inputs,
            original_operand_count=len(seq),
            expanded_operand_count=len(exact_inputs),
        )
        if sdf_union is not None:
            return batch(
                (
                    _mark_expanded_batch_union_result(
                        sdf_union,
                        original_operand_count=len(seq),
                        expanded_operand_count=len(exact_inputs),
                    )
                    if expanded
                    else sdf_union
                )
            )
        sdf_union = _sdf_supported_primitive_batch_union(
            exact_inputs,
            original_operand_count=len(seq),
            expanded_operand_count=len(exact_inputs),
        )
        if sdf_union is not None:
            return batch(
                (
                    _mark_expanded_batch_union_result(
                        sdf_union,
                        original_operand_count=len(seq),
                        expanded_operand_count=len(exact_inputs),
                    )
                    if expanded
                    else sdf_union
                )
            )
        if expanded:
            overlapping_additive = _overlapping_additive_batch_union(
                seq,
                expanded_operand_count=len(exact_inputs),
            )
            if overlapping_additive is not None:
                return batch(overlapping_additive)
        pairwise = self._pairwise_batch_union(
            exact_inputs,
            original_operand_count=len(seq),
            expanded=expanded,
        )
        if pairwise is not None:
            return batch(pairwise)
        result = trimesh.util.concatenate(seq) if len(seq) > 1 else seq[0]
        result.metadata["lathe_reference_batch_union"] = {
            "schema": "lathe.geometry.reference_batch_union.v1",
            "method": "additive_mesh_concatenation",
            "operand_count": len(seq),
            "reason": "reference_kernel_additive_assembly",
        }
        result.remove_unreferenced_vertices()
        result.fix_normals()
        return batch(_set_batch_source_meshes(result, seq))

    def hull(self, meshes: Iterable[trimesh.Trimesh]) -> trimesh.Trimesh:
        """Return a convex hull over the supplied trimesh handles."""
        seq = list(meshes)
        if not seq:
            raise _HullEmptyError
        combined = trimesh.util.concatenate(seq) if len(seq) > 1 else seq[0]
        result = combined.convex_hull
        try:
            body_count = (
                len(result.split(only_watertight=False)) if len(result.faces) else 0
            )
        except (AttributeError, TypeError, ValueError):
            body_count = 0
        result.metadata["lathe_reference_hull"] = {
            "schema": "lathe.geometry.reference_hull.v1",
            "method": "trimesh_convex_hull_v1",
            "attempted_backend": "trimesh.convex_hull",
            "actual_backend": "trimesh.convex_hull",
            "actual_operation": "convex_hull",
            "operand_count": len(seq),
            "source_face_count": sum(len(mesh.faces) for mesh in seq),
            "result_face_count": len(result.faces),
            "result_vertex_count": len(result.vertices),
            "result_watertight": bool(result.is_watertight),
            "result_body_count": int(body_count),
            "fallback": False,
            "passthrough": False,
        }
        return result

    def transform(self, handle: trimesh.Trimesh, matrix: list[list[float]]) -> trimesh.Trimesh:
        """Return a transformed copy of a trimesh handle."""
        mesh = handle.copy()
        transform = np.asarray(matrix, dtype=np.float64)
        mesh.apply_transform(transform)
        _transform_boss_state_metadata(mesh, transform)
        _transform_profile_cut_state_metadata(mesh, transform)
        _transform_box_metadata(mesh, transform)
        _transform_cylinder_metadata(mesh, transform)
        _transform_shape_primitive_metadata(mesh, transform)
        mesh.remove_unreferenced_vertices()
        mesh.fix_normals()
        try:
            body_count = (
                len(mesh.split(only_watertight=False)) if len(mesh.faces) else 0
            )
        except (AttributeError, TypeError, ValueError):
            body_count = 0
        mesh.metadata["lathe_reference_transform"] = {
            "schema": "lathe.geometry.reference_transform.v1",
            "method": "trimesh_apply_transform_v1",
            "attempted_backend": "trimesh.Trimesh.apply_transform",
            "actual_backend": "trimesh.Trimesh.apply_transform",
            "actual_operation": "matrix_transform",
            "result_face_count": len(mesh.faces),
            "result_vertex_count": len(mesh.vertices),
            "result_watertight": bool(mesh.is_watertight),
            "result_body_count": int(body_count),
            "fallback": False,
            "passthrough": False,
        }
        return mesh

    def to_trimesh(self, handle: trimesh.Trimesh) -> trimesh.Trimesh:
        """Return the trimesh handle unchanged."""
        return handle

    def is_watertight(self, handle: trimesh.Trimesh) -> bool:
        """Return whether the trimesh handle is non-empty and watertight."""
        if handle is None or len(handle.faces) == 0:
            return False
        return bool(handle.is_watertight)

    def body_count(self, handle: trimesh.Trimesh) -> int:
        """Return the number of disjoint mesh bodies."""
        if handle is None or len(handle.faces) == 0:
            return 0
        try:
            return len(handle.split(only_watertight=False))
        except (ValueError, RuntimeError, AttributeError, IndexError, TypeError):
            sources = _batch_source_meshes(handle)
            if sources:
                return len([source for source in sources if len(source.faces) > 0])
            return 1


def reference_kernel() -> GeometryKernel:
    """Instantiate the reference (trimesh) geometry kernel."""
    return ReferenceKernel()  # type: ignore[return-value]
