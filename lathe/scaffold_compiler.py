"""Scaffold compiler for the shape stage.

Lowers an assembly blueprint into parameterized scaffold primitives
that feed feature fusion and the authoritative mesh.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any

import numpy as np
import trimesh

from .assembly_kernel import compile_assembly_blueprint
from .asset_graph import AssetGraph
from .blueprints import resolve_blueprint
from .candidate_search import apply_candidate_params, generate_candidate_params, objective_weights
from .constants import RNG_PRIME_OFFSET
from .errors import ContractViolation
from .feature_grammar import compile_feature_enhancements
from .fidelity import infer_fidelity_profile
from .geometry import resolve_geometry_kernel
from .geometry_kernel import fuse_shape_ir
from .repair_executor import execute_shape_repairs
from .repair_planner import plan_shape_repairs
from .shape_ir import ShapeIR, ShapePrimitive


def _make_color(name: str) -> tuple[int, int, int]:
    digest = hashlib.sha256(name.encode("utf-8")).digest()
    return (80 + digest[0] % 140, 80 + digest[1] % 140, 80 + digest[2] % 140)


def _candidate_rng(seed: int, index: int) -> np.random.Generator:
    return np.random.default_rng(seed + index * RNG_PRIME_OFFSET)


def _translated_box(
    extents: tuple[float, float, float], center: tuple[float, float, float]
) -> trimesh.Trimesh:
    matrix = np.eye(4)
    matrix[:3, 3] = np.array(list(center), dtype=float)
    return trimesh.creation.box(extents=np.array(list(extents), dtype=float), transform=matrix)


def _translated_cylinder(
    radius: float, height: float, center: tuple[float, float, float], axis: str
) -> trimesh.Trimesh:
    mesh = trimesh.creation.cylinder(radius=radius, height=height, sections=40)
    if axis == "y":
        mesh.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, [1.0, 0.0, 0.0]))
    elif axis == "x":
        mesh.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, [0.0, 1.0, 0.0]))
    matrix = np.eye(4)
    matrix[:3, 3] = np.array(list(center), dtype=float)
    mesh.apply_transform(matrix)
    return mesh


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


def _unsupported_primitive_type_error(primitive_type: str) -> ValueError:
    return ValueError(f"Unsupported primitive type '{primitive_type}'")


def _primitive_mesh(primitive: ShapePrimitive) -> trimesh.Trimesh:
    if primitive.primitive_type == "box":
        if primitive.extents is None:
            raise _missing_box_extents_error(primitive)
        return _translated_box(primitive.extents, primitive.center)
    if primitive.primitive_type == "cylinder":
        if primitive.radius is None or primitive.height is None:
            raise _missing_cylinder_dimensions_error(primitive)
        return _translated_cylinder(primitive.radius, primitive.height, primitive.center, primitive.axis)
    raise _unsupported_primitive_type_error(primitive.primitive_type)


def _fuse_via_manifold_kernel(shape_ir: ShapeIR) -> tuple[trimesh.Trimesh, list[str]] | None:
    """Fuse a ShapeIR into a watertight mesh using the Manifold CSG kernel.

    Returns ``(mesh, face_parts)`` on success or ``None`` if Manifold is
    unavailable or any CSG op raises. Face parts are assigned by
    walking triangle centroids against the primitive bounding boxes;
    this is good enough for courier_drone-class scenes and mirrors the
    heuristic in :func:`lathe.geometry_kernel._assign_face_parts`.
    """
    try:
        from .geometry.manifold_kernel import ManifoldKernel as _MK
        from .geometry.manifold_kernel import manifold_available as _ma
    except ImportError:
        return None
    if not _ma():
        return None
    try:
        kernel = _MK()
    except Exception:
        return None

    primitives = list(shape_ir.primitives)
    if not primitives:
        return None

    part_handles: list[tuple[Any, str, str]] = []  # (handle, blend_mode, part)
    for primitive in primitives:
        try:
            if primitive.primitive_type == "box":
                handle = kernel.build_primitive(
                    "box",
                    extents=tuple(primitive.extents or (0.0, 0.0, 0.0)),
                    center=tuple(primitive.center),
                )
            elif primitive.primitive_type == "cylinder":
                handle = kernel.build_primitive(
                    "cylinder",
                    radius=float(primitive.radius or 0.0),
                    height=float(primitive.height or 0.0),
                    axis=primitive.axis,
                    center=tuple(primitive.center),
                )
            else:
                return None
        except Exception:
            return None
        part_handles.append((handle, primitive.blend_mode or "union", primitive.part))

    # Assemble: first union-positive, then subtract.
    positives = [h for h in part_handles if h[1] != "subtract"]
    negatives = [h for h in part_handles if h[1] == "subtract"]
    if not positives:
        return None
    try:
        acc = positives[0][0]
        for h, _mode, _part in positives[1:]:
            acc = kernel.union(acc, h)
        for h, _mode, _part in negatives:
            acc = kernel.difference(acc, h)
        mesh = kernel.to_trimesh(acc)
    except Exception:
        return None

    if len(mesh.faces) == 0:
        return None

    face_parts = _assign_face_parts_via_bounds(mesh, shape_ir)
    return mesh, face_parts


def _assign_face_parts_via_bounds(mesh: trimesh.Trimesh, shape_ir: ShapeIR) -> list[str]:
    """Assign a part label per face by matching triangle centroids against ShapeRegion AABBs."""
    centroids = np.asarray(mesh.triangles_center, dtype=np.float64)
    entries: list[tuple[str, np.ndarray, np.ndarray, np.ndarray]] = []
    for region in shape_ir.regions:
        center = np.array(region.center, dtype=np.float64)
        half = np.array(region.extents, dtype=np.float64) / 2.0
        entries.append((region.part, center - half, center + half, center))
    default_part = entries[0][0] if entries else "mesh"
    labels: list[str] = []
    for centroid in centroids:
        best_part = default_part
        best_distance = float("inf")
        for part, bmin, bmax, center in entries:
            extent = np.maximum((bmax - bmin) / 2.0, 1e-6)
            delta = np.abs(centroid - center) - extent
            outside = np.maximum(delta, 0.0)
            distance = float(np.linalg.norm(outside / extent))
            if distance < best_distance:
                best_distance = distance
                best_part = part
        labels.append(best_part)
    return labels


def _native_candidate_score(
    asset_graph: AssetGraph, shape_ir: ShapeIR, conditioning: dict[str, Any], candidate_index: int
) -> float:
    assessment = shape_ir.assessment
    objective_map = objective_weights(asset_graph)
    if objective_map:
        metric_values = {
            "silhouette_readability": assessment.get("silhouette_complexity", 0.0),
            "geometry_integration_quality": min(
                1.0,
                0.55
                + 0.06 * assessment.get("edge_treatment_count", 0)
                + 0.04 * assessment.get("feature_coherence", 0.0),
            ),
            "visual_surface_quality": min(
                1.0,
                0.45
                + 0.12 * assessment.get("feature_density", 0.0)
                + 0.12 * assessment.get("feature_coherence", 0.0),
            ),
            "primitive_likeness_penalty": max(
                0.0,
                0.48
                - 0.20 * assessment.get("feature_coherence", 0.0)
                - 0.08 * assessment.get("edge_treatment_count", 0),
            ),
            "feature_density": assessment.get("feature_density", 0.0),
        }
        total = 0.0
        for metric_name, weight in objective_map.items():
            value = float(metric_values.get(metric_name, 0.0))
            if metric_name.endswith("_penalty"):
                value = 1.0 - min(1.0, value)
            total += value * weight
        total += 0.04 * assessment.get("required_part_coverage", 0.0)
        total -= 0.012 * candidate_index
        return round(min(0.96, max(0.48, total + 0.55)), 6)
    score = 0.66
    score += 0.05 * assessment.get("required_part_coverage", 0.0)
    score += 0.05 * assessment.get("richness_floor", 0.0)
    score += 0.03 * assessment.get("symmetry_region_score", 0.0)
    score += 0.02 * assessment.get("primitive_diversity", 0.0)
    score += 0.04 * assessment.get("feature_density", 0.0)
    score += 0.03 * assessment.get("silhouette_complexity", 0.0)
    score += 0.03 * assessment.get("feature_coherence", 0.0)
    if conditioning.get("image_refs"):
        score += 0.02
    if conditioning.get("mesh_refs"):
        score += 0.03
    if asset_graph.kind == "env_module":
        score += 0.01
    score -= 0.015 * candidate_index
    return round(min(0.96, max(0.52, score)), 6)


def _needs_more_repairs(asset_graph: AssetGraph, shape_ir: ShapeIR) -> bool:
    assessment = shape_ir.assessment
    requirements = asset_graph.semantic_requirements
    return (
        assessment.get("feature_density", 0.0) < requirements.get("minimum_detail_density", 0.58)
        or assessment.get("feature_coherence", 0.0) < requirements.get("minimum_feature_coherence", 0.56)
        or assessment.get("edge_treatment_count", 0) < max(4, len(asset_graph.parts))
    )


def _selection_notes(
    asset_graph: AssetGraph,
    shape_ir: ShapeIR,
    conditioning: dict[str, Any],
    candidate_index: int,
    fidelity_tier: str,
    feature_ops_used: list[str],
) -> list[str]:
    notes = [
        f"native assembly candidate for family='{asset_graph.family}'",
        f"blueprint_id={shape_ir.blueprint_id}",
        f"candidate_index={candidate_index}",
        f"primitives_used={','.join(shape_ir.primitives_used)}",
        f"fidelity={fidelity_tier}",
        f"feature_ops={','.join(feature_ops_used)}",
    ]
    if conditioning.get("mesh_refs"):
        notes.insert(0, "reconstructed from mesh-conditioned assembly blueprint")
    elif conditioning.get("image_refs"):
        notes.insert(0, "generated from image-conditioned assembly blueprint")
    else:
        notes.insert(0, "generated from intent assembly blueprint")
    return notes


def _runtime_from_shape_ir(
    asset_graph: AssetGraph,
    shape_ir: ShapeIR,
    *,
    candidate_index: int,
    conditioning: dict[str, Any],
    mode: str,
    repairs_applied: list[dict[str, Any]],
    fidelity_tier: str,
    feature_report: dict[str, Any],
    candidate_params: dict[str, Any],
    fidelity_profile,
    geometry_kernel_id: str | None = None,
) -> dict[str, Any]:
    part_colors = {part.name: _make_color(part.name) for part in asset_graph.parts}
    fused_mesh_ir, integration_report = fuse_shape_ir(shape_ir, fidelity_profile)
    if geometry_kernel_id and isinstance(integration_report, dict):
        integration_report.setdefault("geometry_kernel", geometry_kernel_id)
    if fused_mesh_ir is None and geometry_kernel_id == "lathe.geometry.manifold_v1":
        manifold_fused = _fuse_via_manifold_kernel(shape_ir)
        if manifold_fused is not None:
            combined, face_parts = manifold_fused
            integration_report = {
                "mode": "manifold_csg",
                "search_mode": "manifold_csg",
                "geometry_kernel": geometry_kernel_id,
                "body_count": len(combined.split(only_watertight=False)) if len(combined.faces) > 0 else 0,
                "watertight": bool(combined.is_watertight),
                "primitive_count": len(list(shape_ir.primitives)),
            }
            return {
                "mesh": combined,
                "face_parts": face_parts,
                "part_colors": part_colors,
                "units": "cm",
                "meta": {
                    "parts": sorted({region.part for region in shape_ir.regions}),
                    "coarse_material_slots": max(1, len(asset_graph.materials)),
                    "score": _native_candidate_score(asset_graph, shape_ir, conditioning, candidate_index),
                    "selection_notes": _selection_notes(
                        asset_graph,
                        shape_ir,
                        conditioning,
                        candidate_index,
                        fidelity_tier,
                        feature_report.get("feature_ops_used", []),
                    ),
                    "conditioning": {
                        "provider": None,
                        "reference_strength": conditioning.get("reference_strength", 0.0),
                        "family": asset_graph.family,
                        "native_scaffold": True,
                        "mode": mode,
                        "blueprint_id": shape_ir.blueprint_id,
                    },
                    "blueprint_id": shape_ir.blueprint_id,
                    "primitives_used": list(shape_ir.primitives_used),
                    "shape_assessment": dict(shape_ir.assessment),
                    "repairs_applied": repairs_applied,
                    "feature_report": feature_report,
                    "candidate_params": candidate_params,
                    "integration_report": integration_report,
                    "mesh_ir": None,
                },
            }
    if fused_mesh_ir is None:
        named_meshes: list[tuple[str, trimesh.Trimesh]] = []
        face_parts = []
        for primitive in shape_ir.primitives:
            mesh = _primitive_mesh(primitive)
            named_meshes.append((primitive.part, mesh))
            face_parts.extend([primitive.part] * len(mesh.faces))
        combined = (
            trimesh.util.concatenate([mesh for _, mesh in named_meshes])
            if len(named_meshes) > 1
            else named_meshes[0][1]
        )
        integration_report = {"mode": "constructive_fallback", "reason": "geometry kernel unavailable"}
        mesh_ir_payload = None
    else:
        combined = fused_mesh_ir.to_trimesh()
        face_parts = list(fused_mesh_ir.face_parts)
        mesh_ir_payload = fused_mesh_ir.to_dict()
    return {
        "mesh": combined,
        "face_parts": face_parts,
        "part_colors": part_colors,
        "units": "cm",
        "meta": {
            "parts": sorted({region.part for region in shape_ir.regions}),
            "coarse_material_slots": max(1, len(asset_graph.materials)),
            "score": _native_candidate_score(asset_graph, shape_ir, conditioning, candidate_index),
            "selection_notes": _selection_notes(
                asset_graph,
                shape_ir,
                conditioning,
                candidate_index,
                fidelity_tier,
                feature_report.get("feature_ops_used", []),
            ),
            "conditioning": {
                "provider": None,
                "reference_strength": conditioning.get("reference_strength", 0.0),
                "family": asset_graph.family,
                "native_scaffold": True,
                "mode": mode,
                "blueprint_id": shape_ir.blueprint_id,
            },
            "blueprint_id": shape_ir.blueprint_id,
            "primitives_used": list(shape_ir.primitives_used),
            "shape_assessment": dict(shape_ir.assessment),
            "repairs_applied": repairs_applied,
            "feature_report": feature_report,
            "candidate_params": candidate_params,
            "integration_report": integration_report,
            "mesh_ir": mesh_ir_payload,
        },
    }


def compile_scaffold_candidates(
    asset_graph: AssetGraph,
    *,
    seed: int,
    candidates_count: int,
    conditioning: dict[str, Any],
    mode: str,
    runtime_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile scaffold candidates.

    Args:
        asset_graph: asset_graph argument.
        seed: seed argument.
        candidates_count: candidates_count argument.
        conditioning: conditioning argument.
        mode: mode argument.
        runtime_config: runtime_config argument.

    Returns:
        The result.
    """
    candidate_records: list[dict[str, Any]] = []
    fidelity = infer_fidelity_profile(asset_graph)
    geometry_kernel = resolve_geometry_kernel(runtime_config)
    geometry_kernel_id = getattr(geometry_kernel, "name", None)
    source_best_of = int(asset_graph.authoring.get("space", {}).get("select", {}).get("best_of", 0) or 0)
    search_count = max(3 if fidelity.tier == "hero" else 1, candidates_count, source_best_of)
    for index in range(search_count):
        rng = _candidate_rng(seed, index)
        params = generate_candidate_params(asset_graph, seed=seed, candidate_index=index, fidelity=fidelity)
        blueprint = apply_candidate_params(
            resolve_blueprint(asset_graph, conditioning, rng, index), params, asset_graph
        )
        shape_ir = compile_assembly_blueprint(asset_graph, blueprint)
        shape_ir, feature_report = compile_feature_enhancements(
            asset_graph, shape_ir, fidelity=fidelity, params=params
        )
        round_reports = []
        repaired_shape_ir = shape_ir
        applied_repairs: list[dict[str, Any]] = []
        round_index = 0
        while round_index < fidelity.repair_budget:
            planned_repairs = plan_shape_repairs(asset_graph, repaired_shape_ir)
            if not planned_repairs and not _needs_more_repairs(asset_graph, repaired_shape_ir):
                break
            repaired_shape_ir, round_applied = execute_shape_repairs(
                asset_graph,
                repaired_shape_ir,
                planned_repairs,
                max_repairs=max(1, fidelity.repair_budget - round_index),
            )
            round_reports.append(
                {
                    "round": round_index + 1,
                    "planned": [repair.to_dict() for repair in planned_repairs],
                    "applied": round_applied,
                    "shape_assessment": dict(repaired_shape_ir.assessment),
                }
            )
            applied_repairs.extend(round_applied)
            if not round_applied:
                break
            round_index += 1
        feature_report["shape_assessment"] = dict(repaired_shape_ir.assessment)
        feature_report["feature_ops_used"] = sorted(
            set(feature_report.get("feature_ops_used", []))
            | set(repaired_shape_ir.assessment.get("feature_types", []))
        )
        candidate_records.append(
            {
                "candidate_index": index,
                "shape_ir": repaired_shape_ir,
                "blueprint": blueprint.to_dict(),
                "feature_report": feature_report,
                "candidate_params": params.to_dict(),
                "repairs": {"candidate_index": index, "rounds": round_reports, "applied": applied_repairs},
                "pre_score": _native_candidate_score(asset_graph, repaired_shape_ir, conditioning, index),
            }
        )

    shortlist_count = min(2, len(candidate_records))
    shortlisted = sorted(candidate_records, key=lambda item: (-item["pre_score"], item["candidate_index"]))[
        :shortlist_count
    ]
    shortlisted = sorted(shortlisted, key=lambda item: item["candidate_index"])

    runtime_candidates: list[dict[str, Any]] = []
    shape_irs: list[ShapeIR] = []
    blueprints: list[dict[str, Any]] = []
    repairs: list[dict[str, Any]] = []
    feature_reports: list[dict[str, Any]] = []
    candidate_params_list: list[dict[str, Any]] = []
    for record in shortlisted:
        runtime_candidates.append(
            _runtime_from_shape_ir(
                asset_graph,
                record["shape_ir"],
                candidate_index=record["candidate_index"],
                conditioning=conditioning,
                mode=mode,
                repairs_applied=record["repairs"]["applied"],
                fidelity_tier=fidelity.tier,
                feature_report=record["feature_report"],
                candidate_params=record["candidate_params"],
                fidelity_profile=fidelity,
                geometry_kernel_id=geometry_kernel_id,
            )
        )
        shape_irs.append(record["shape_ir"])
        blueprints.append(record["blueprint"])
        repairs.append(record["repairs"])
        feature_reports.append(record["feature_report"])
        candidate_params_list.append(record["candidate_params"])

    first_ir = shape_irs[0]
    return {
        "asset_graph": asset_graph,
        "shape_irs": shape_irs,
        "runtime_candidates": runtime_candidates,
        "report": {
            "family": asset_graph.family,
            "generator": "parametric_hard_surface_assembly",
            "asset_graph": asset_graph.to_dict(),
            "shape_irs": [item.to_dict() for item in shape_irs],
            "blueprints": blueprints,
            "feature_reports": feature_reports,
            "candidate_search": candidate_params_list,
            "candidate_search_summary": [
                {
                    "candidate_index": item["candidate_index"],
                    "pre_score": item["pre_score"],
                    "shortlisted": item in shortlisted,
                    "shape_assessment": item["feature_report"].get("shape_assessment", {}),
                }
                for item in candidate_records
            ],
            "fidelity": fidelity.to_dict(),
            "signature": dict(first_ir.signature),
            "blueprint_id": first_ir.blueprint_id,
            "primitives_used": list(first_ir.primitives_used),
            "shape_assessment": dict(first_ir.assessment),
            "repairs": repairs,
            "authoritative_candidate_reason": "native_assembly_blueprint",
            "geometry_kernel": geometry_kernel_id,
        },
    }
