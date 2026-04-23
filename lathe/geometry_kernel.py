from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np
import trimesh
from scipy.ndimage import gaussian_filter
from trimesh.voxel.ops import matrix_to_marching_cubes

from .exact_solids import compile_explicit_surface_mesh, exactify_surface_mesh
from .feature_fusion import integration_config_for_family, primitive_blend_mode, primitive_rounding
from .fidelity import FidelityProfile
from .mesh_finalize import finalize_mesh_ir
from .mesh_ir import MeshIR
from .solid_ir import SolidIR, SolidOp
from .shape_ir import ShapeIR, ShapeRegion, ShapePrimitive


_FUSION_CACHE: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}


def _primitive_bounds(primitive: ShapePrimitive, rounding: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    if primitive.primitive_type == "box":
        assert primitive.extents is not None
        half = np.array(primitive.extents, dtype=np.float64) / 2.0 + rounding
    elif primitive.primitive_type == "cylinder":
        assert primitive.radius is not None and primitive.height is not None
        radius = float(primitive.radius) + rounding
        half_h = float(primitive.height) / 2.0 + rounding
        if primitive.axis == "x":
            half = np.array([half_h, radius, radius], dtype=np.float64)
        elif primitive.axis == "z":
            half = np.array([radius, radius, half_h], dtype=np.float64)
        else:
            half = np.array([radius, half_h, radius], dtype=np.float64)
    else:
        raise ValueError(f"Unsupported primitive type '{primitive.primitive_type}'")
    center = np.array(primitive.center, dtype=np.float64)
    return center - half, center + half


def _box_sdf(points: np.ndarray, primitive: ShapePrimitive, rounding: float) -> np.ndarray:
    assert primitive.extents is not None
    center = np.array(primitive.center, dtype=np.float64)
    half = np.array(primitive.extents, dtype=np.float64) / 2.0 - rounding
    q = np.abs(points - center) - half
    outside = np.linalg.norm(np.maximum(q, 0.0), axis=-1)
    inside = np.minimum(np.max(q, axis=-1), 0.0)
    return outside + inside - rounding


def _cylinder_sdf(points: np.ndarray, primitive: ShapePrimitive, rounding: float) -> np.ndarray:
    assert primitive.radius is not None and primitive.height is not None
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
    d = np.stack([radial - max(0.0, radius - rounding), axial - max(0.0, half_h - rounding)], axis=-1)
    outside = np.linalg.norm(np.maximum(d, 0.0), axis=-1)
    inside = np.minimum(np.max(d, axis=-1), 0.0)
    return outside + inside - rounding


def _primitive_sdf(points: np.ndarray, primitive: ShapePrimitive, rounding: float) -> np.ndarray:
    if primitive.primitive_type == "box":
        return _box_sdf(points, primitive, rounding)
    if primitive.primitive_type == "cylinder":
        return _cylinder_sdf(points, primitive, rounding)
    raise ValueError(f"Unsupported primitive type '{primitive.primitive_type}'")


def _region_lookup(shape_ir: ShapeIR) -> list[tuple[ShapeRegion, np.ndarray, np.ndarray]]:
    entries = []
    for region in shape_ir.regions:
        center = np.array(region.center, dtype=np.float64)
        half = np.array(region.extents, dtype=np.float64) / 2.0
        entries.append((region, center - half, center + half))
    return entries


def solid_ir_from_shape(shape_ir: ShapeIR) -> SolidIR:
    operations = []
    for primitive in shape_ir.primitives:
        params: dict[str, Any] = {"center": list(primitive.center), "axis": primitive.axis, "blend_mode": primitive.blend_mode, "rounding": primitive.rounding}
        if primitive.extents is not None:
            params["extents"] = list(primitive.extents)
        if primitive.radius is not None:
            params["radius"] = primitive.radius
        if primitive.height is not None:
            params["height"] = primitive.height
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
    return SolidIR(asset_name=shape_ir.asset_name, family=shape_ir.family, operations=operations, notes=list(shape_ir.signature.get("blueprint_notes", [])))


def _assign_face_parts(mesh: trimesh.Trimesh, shape_ir: ShapeIR) -> list[str]:
    centroids = np.asarray(mesh.triangles_center, dtype=np.float64)
    region_entries = _region_lookup(shape_ir)
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


def fuse_shape_ir(shape_ir: ShapeIR, fidelity: FidelityProfile) -> tuple[MeshIR | None, dict[str, Any]]:
    config = integration_config_for_family(shape_ir.family, fidelity)
    if not config["enabled"]:
        return None, {"mode": "constructive_fallback", "reason": "integration disabled for this family/fidelity"}

    primitives = list(shape_ir.primitives)
    if not primitives:
        return None, {"mode": "constructive_fallback", "reason": "no primitives"}

    if config.get("exact_mode") in {"explicit_mesh", "component_assembly"}:
        mesh, face_parts, exact_report = compile_explicit_surface_mesh(shape_ir, fidelity, combine_mode=str(config.get("exact_mode")))
        if not face_parts or len(face_parts) != len(mesh.faces):
            face_parts = _assign_face_parts(mesh, shape_ir)
        solid_ir = solid_ir_from_shape(shape_ir)
        report = {
            **exact_report,
            "search_mode": "parametric_exact_assembly",
            "hero_family": bool(config["hero_family"]),
            "solid_ir": solid_ir.to_dict(),
            "cache_hit": False,
        }
        mesh_ir = finalize_mesh_ir(mesh, shape_ir, face_parts, metadata={"integration_report": report})
        return mesh_ir, report

    cache_key = hashlib.sha256(
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
    if cache_key in _FUSION_CACHE:
        mesh_ir_payload, report = _FUSION_CACHE[cache_key]
        return MeshIR(**json.loads(json.dumps(mesh_ir_payload))), {**report, "cache_hit": True}

    bounds = [_primitive_bounds(primitive, primitive_rounding(primitive, fidelity)) for primitive in primitives]
    bounds_min = np.min([item[0] for item in bounds], axis=0)
    bounds_max = np.max([item[1] for item in bounds], axis=0)
    pitch = float(config["pitch"])
    margin = max(2.0, pitch * 3.0)
    origin = bounds_min - margin
    top = bounds_max + margin
    dims = np.maximum(np.ceil((top - origin) / pitch).astype(int) + 1, 4)
    if np.prod(dims) > 6_500_000:
        scale = (np.prod(dims) / 6_500_000) ** (1 / 3)
        pitch *= float(scale)
        dims = np.maximum(np.ceil((top - origin) / pitch).astype(int) + 1, 4)

    field = np.full(tuple(int(value) for value in dims), 9_999.0, dtype=np.float32)
    x_axis = origin[0] + np.arange(dims[0], dtype=np.float32) * pitch
    y_axis = origin[1] + np.arange(dims[1], dtype=np.float32) * pitch
    z_axis = origin[2] + np.arange(dims[2], dtype=np.float32) * pitch

    for primitive in primitives:
        rounding = primitive_rounding(primitive, fidelity)
        bmin, bmax = _primitive_bounds(primitive, rounding)
        lo = np.maximum(np.floor((bmin - origin) / pitch).astype(int) - 1, 0)
        hi = np.minimum(np.ceil((bmax - origin) / pitch).astype(int) + 2, dims)
        xs = x_axis[lo[0] : hi[0]]
        ys = y_axis[lo[1] : hi[1]]
        zs = z_axis[lo[2] : hi[2]]
        xx, yy, zz = np.meshgrid(xs, ys, zs, indexing="ij")
        points = np.stack([xx, yy, zz], axis=-1)
        sdf = _primitive_sdf(points, primitive, rounding).astype(np.float32)
        target = field[lo[0] : hi[0], lo[1] : hi[1], lo[2] : hi[2]]
        if primitive_blend_mode(primitive) == "subtract":
            field[lo[0] : hi[0], lo[1] : hi[1], lo[2] : hi[2]] = np.maximum(target, -sdf)
        else:
            field[lo[0] : hi[0], lo[1] : hi[1], lo[2] : hi[2]] = np.minimum(target, sdf)

    sigma = float(config["blur_sigma"])
    if sigma > 0:
        field = gaussian_filter(field, sigma=sigma)
    matrix = field < 0.0
    if not np.any(matrix):
        return None, {"mode": "constructive_fallback", "reason": "empty_fusion_volume"}

    mesh = matrix_to_marching_cubes(matrix, pitch=pitch)
    mesh.apply_translation(origin)
    mesh.remove_infinite_values()
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()
    try:
        mesh.process(validate=True)
    except Exception:  # noqa: BLE001
        pass
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
        "primitive_count": len(primitives),
        "cache_hit": False,
        "solid_ir": solid_ir.to_dict(),
    }
    if exact_report:
        report["exact_report"] = exact_report
    mesh_ir = finalize_mesh_ir(mesh, shape_ir, face_parts, metadata={"integration_report": report})
    _FUSION_CACHE[cache_key] = (mesh_ir.to_dict(), dict(report))
    return mesh_ir, report
