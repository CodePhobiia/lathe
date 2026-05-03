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


class _UnsupportedPrimitiveTypeError(ValueError):
    def __init__(self, primitive_type: str) -> None:
        super().__init__(f"Unsupported primitive type '{primitive_type}'")


def _primitive_bounds(primitive: ShapePrimitive, rounding: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
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
        half_h = (max(axials) - min(axials)) / 2.0 + rounding
        if primitive.axis == "x":
            half = np.array([half_h, radius, radius], dtype=np.float64)
        elif primitive.axis == "z":
            half = np.array([radius, radius, half_h], dtype=np.float64)
        else:
            half = np.array([radius, half_h, radius], dtype=np.float64)
    else:
        raise _UnsupportedPrimitiveTypeError(primitive.primitive_type)
    center = np.array(primitive.center, dtype=np.float64)
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


def _primitive_sdf(points: np.ndarray, primitive: ShapePrimitive, rounding: float) -> np.ndarray:
    if primitive.primitive_type == "box":
        return _box_sdf(points, primitive, rounding)
    if primitive.primitive_type == "cylinder":
        return _cylinder_sdf(points, primitive, rounding)
    if primitive.primitive_type == "revolved_profile":
        # SDF path uses the bounding cylinder as a coarse approximation.
        # The voxelization fallback is only invoked when the exact-solid
        # path is unavailable; the manifold/exact paths produce the
        # accurate revolved mesh.
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


def _fallback_report(reason: str) -> dict[str, str]:
    return {"mode": "constructive_fallback", "reason": reason}


def _compile_exact_mesh_ir(
    shape_ir: ShapeIR,
    fidelity: FidelityProfile,
    config: dict[str, Any],
) -> tuple[MeshIR, dict[str, Any]]:
    mesh, face_parts, exact_report = compile_explicit_surface_mesh(
        shape_ir,
        fidelity,
        combine_mode=str(config.get("exact_mode")),
    )
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
    config = integration_config_for_family(shape_ir.family, fidelity)
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
