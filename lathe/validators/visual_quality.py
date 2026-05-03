"""Visual-quality validator.

Combines shape scaffolds, renders and surface evidence into a
consolidated visual score used in certification.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from ..errors import LatheError
from ..imaging import open_guarded
from ..render_eval import evaluate_render_views
from ..repair_planner import suggest_repairs_for_metric

GENERATED_GEOMETRY_INTEGRATION_FLOOR = 0.40
GENERATED_SURFACE_AUTHORING_FLOOR = 0.40
_MIN_SUPPORT_FACE_COUNT = 2
_RGB_CHANNELS = 3
_COPLANAR_ANGLE_MAX = 0.05
_STAIR_STEP_ANGLE_MAX = 0.42
_SHARP_BOUNDARY_ANGLE_MIN = 0.48


class SurfaceEvidenceInvariantError(LatheError):
    """Raised when surface evidence reaches metric computation without inputs."""

    def __init__(self) -> None:
        """Create the invariant error with the canonical Lathe message."""
        super().__init__("surface evidence invariant violation")


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _support_plausibility(
    asset: dict[str, Any], runtime: dict[str, Any], shape_assessment: dict[str, Any]
) -> float:
    supports = [
        group
        for group in runtime["topology"]["bundle"].get("part_groups", [])
        if any(token in group["name"].lower() for token in ("foot", "leg", "stand", "bracket"))
    ]
    if not supports:
        return 0.75
    support_bonus = min(1.0, shape_assessment.get("support_feature_count", 0) / max(1, len(supports)))
    if any(int(group.get("face_count", 0)) <= _MIN_SUPPORT_FACE_COUNT for group in supports):
        return round(min(1.0, 0.58 + 0.18 * support_bonus), 6)
    bmin = runtime["topology"]["bundle"]["mesh_stats"]["bounds_min"]
    span_y = max(1e-6, runtime["topology"]["bundle"]["mesh_stats"]["extents"][1])
    scores = []
    for support in supports:
        near_floor = abs(support["bounds_min"][1] - bmin[1]) <= span_y * 0.22
        scores.append(1.0 if near_floor else 0.4)
    return round(min(1.0, 0.75 * (sum(scores) / len(scores)) + 0.25 * support_bonus), 6)


def _surface_stage_dir(runtime: dict[str, Any]) -> Path | None:
    stage_dir = runtime.get("surface", {}).get("stage_dir")
    if stage_dir is None:
        return None
    return Path(stage_dir)


def _surface_output_path(runtime: dict[str, Any], name: str) -> Path | None:
    stage_dir = _surface_stage_dir(runtime)
    if stage_dir is None:
        return None
    bundle = runtime.get("surface", {}).get("bundle", {})
    outputs = bundle.get("outputs", {})
    entry = outputs.get(name)
    if isinstance(entry, dict) and entry.get("uri"):
        candidate = stage_dir / entry["uri"]
        if candidate.exists():
            return candidate
    fallback = stage_dir / "maps" / f"{name}.png"
    return fallback if fallback.exists() else None


def _load_image(runtime: dict[str, Any], name: str) -> np.ndarray | None:
    path = _surface_output_path(runtime, name)
    if path is None:
        return None
    try:
        with open_guarded(path) as image:
            return np.asarray(image.convert("RGB" if image.mode != "L" else "L"))
    except (
        OSError,
        ValueError,
        TypeError,
        Image.UnidentifiedImageError,
        Image.DecompressionBombError,
    ):
        # PIL raises UnidentifiedImageError for unknown formats, OSError for
        # truncated files, ValueError for invalid mode conversions, and
        # DecompressionBombError when a hostile/malformed asset declares
        # dimensions above PIL.Image.MAX_IMAGE_PIXELS.
        return None


def _image_entropy(image: np.ndarray) -> float:
    if image.ndim == _RGB_CHANNELS:
        gray = np.asarray(np.mean(image.astype(np.float64), axis=2), dtype=np.uint8)
    else:
        gray = np.asarray(image, dtype=np.uint8)
    hist = np.bincount(gray.ravel(), minlength=256).astype(np.float64)
    total = hist.sum()
    if total <= 0:
        return 0.0
    probs = hist / total
    probs = probs[probs > 0]
    return float(-np.sum(probs * np.log2(probs)) / 8.0)


def _zero_surface_evidence() -> dict[str, float]:
    return {
        "texture_entropy": 0.0,
        "normal_richness": 0.0,
        "roughness_variation": 0.0,
        "material_zone_coherence": 0.0,
        "decal_coherence": 0.0,
        "bake_cleanliness": 0.0,
        "highlow_distinction_quality": 0.0,
        "surface_texture_entropy": 0.0,
        "surface_chroma_variation": 0.0,
        "surface_normal_richness": 0.0,
        "surface_roughness_variation": 0.0,
        "surface_bake_cleanliness": 0.0,
        "surface_material_zone_coherence": 0.0,
        "surface_emissive_coherence": 0.0,
        "surface_highlow_realness": 0.0,
        "surface_authoring_quality": 0.0,
    }


def _requested_surface_maps(surface_bundle: dict[str, Any]) -> set[str]:
    manifest = _as_dict(surface_bundle.get("surface_manifest", {}))
    return {
        str(name).lower()
        for name in [
            *_as_list(surface_bundle.get("maps", [])),
            *_as_list(manifest.get("maps", [])),
        ]
    }


def _metadata_surface_evidence(surface_bundle: dict[str, Any]) -> dict[str, float]:
    maps = _requested_surface_maps(surface_bundle)
    material_zones = [
        entry for entry in _as_list(surface_bundle.get("material_zones", [])) if isinstance(entry, dict)
    ]
    if not maps and not material_zones:
        return _zero_surface_evidence()

    manifest = _as_dict(surface_bundle.get("surface_manifest", {}))
    materials = {
        str(entry.get("material") or entry.get("part") or "")
        for entry in material_zones
        if entry.get("material") or entry.get("part")
    }
    zone_diversity = min(1.0, len(materials) / 3.0) if materials else 0.0
    workflow = str(manifest.get("workflow") or "").lower()
    pbr_workflow = 1.0 if workflow in {"pbr_metal_rough", "metallic_roughness", "pbr_spec_gloss"} else 0.0
    has_basecolor = "basecolor" in maps or "albedo" in maps
    has_normal = "normal" in maps
    has_roughness = "orm" in maps or "roughness" in maps
    has_ao = "orm" in maps or "ao" in maps
    has_emissive = "emissive" in maps
    map_coverage = sum(1 for present in (has_basecolor, has_normal, has_roughness, has_ao) if present) / 4.0
    authored_surface = any(
        manifest.get(key) or surface_bundle.get(key)
        for key in (
            "program",
            "palette",
            "patterns",
            "decal_libraries",
            "mask_programs",
            "trim_sheets",
            "surface_program",
        )
    )
    decal_count = (
        len(_as_list(surface_bundle.get("decal_masks", [])))
        + len(_as_list(surface_bundle.get("patterns", [])))
        + len(_as_list(manifest.get("patterns", [])))
    )

    texture_entropy = min(
        1.0, 0.16 + 0.18 * zone_diversity + 0.12 * map_coverage + (0.06 if authored_surface else 0.0)
    )
    chroma_variation = min(
        1.0,
        0.14 + 0.20 * zone_diversity + (0.08 if has_basecolor else 0.0) + (0.05 if authored_surface else 0.0),
    )
    normal_richness = min(1.0, 0.08 + (0.20 if has_normal else 0.0) + 0.04 * zone_diversity)
    roughness_variation = min(1.0, 0.08 + (0.20 if has_roughness else 0.0) + 0.04 * zone_diversity)
    bake_cleanliness = min(1.0, 0.10 + 0.18 * map_coverage + 0.07 * pbr_workflow)
    material_zone_coherence = min(
        1.0, 0.22 + 0.36 * zone_diversity + 0.22 * map_coverage + 0.10 * pbr_workflow
    )
    emissive_coherence = 0.70 if has_emissive else 0.80
    decal_coherence = min(1.0, 0.52 + 0.10 * min(1.0, decal_count / 2.0) + 0.18 * material_zone_coherence)
    highlow_realness = 0.0
    surface_authoring_quality = min(
        1.0,
        0.20 * texture_entropy
        + 0.12 * chroma_variation
        + 0.18 * normal_richness
        + 0.19 * roughness_variation
        + 0.10 * bake_cleanliness
        + 0.10 * material_zone_coherence
        + 0.04 * decal_coherence
        + 0.01 * emissive_coherence
        + 0.06 * highlow_realness,
    )
    return {
        "texture_entropy": round(texture_entropy, 6),
        "normal_richness": round(normal_richness, 6),
        "roughness_variation": round(roughness_variation, 6),
        "material_zone_coherence": round(material_zone_coherence, 6),
        "decal_coherence": round(decal_coherence, 6),
        "bake_cleanliness": round(bake_cleanliness, 6),
        "highlow_distinction_quality": round(highlow_realness, 6),
        "surface_texture_entropy": round(texture_entropy, 6),
        "surface_chroma_variation": round(chroma_variation, 6),
        "surface_normal_richness": round(normal_richness, 6),
        "surface_roughness_variation": round(roughness_variation, 6),
        "surface_bake_cleanliness": round(bake_cleanliness, 6),
        "surface_material_zone_coherence": round(material_zone_coherence, 6),
        "surface_emissive_coherence": round(emissive_coherence, 6),
        "surface_highlow_realness": round(highlow_realness, 6),
        "surface_authoring_quality": round(surface_authoring_quality, 6),
    }


def _surface_evidence(runtime: dict[str, Any], surface_bundle: dict[str, Any]) -> dict[str, float]:
    backend_id = surface_bundle.get("backend_id")

    basecolor = _load_image(runtime, "basecolor")
    normal = _load_image(runtime, "normal")
    orm = _load_image(runtime, "orm")
    ao = _load_image(runtime, "ao")
    curvature = _load_image(runtime, "curvature")
    id_map = _load_image(runtime, "id")
    emissive = _load_image(runtime, "emissive")
    if any(image is None for image in (basecolor, normal, orm, ao, curvature, id_map)):
        if backend_id != "lathe.surface.hero_pbr_v1":
            return _metadata_surface_evidence(surface_bundle)
        return _zero_surface_evidence()

    if (
        basecolor is None
        or normal is None
        or orm is None
        or ao is None
        or curvature is None
        or id_map is None
    ):
        raise SurfaceEvidenceInvariantError
    texture_entropy = _image_entropy(basecolor)
    chroma_variation = min(1.0, float(np.std(basecolor.astype(np.float64), axis=(0, 1)).mean() / 72.0))
    normal_xy = normal[:, :, :2].astype(np.float64) - 128.0
    normal_richness = min(1.0, float(np.mean(np.linalg.norm(normal_xy, axis=2)) / 46.0))
    roughness = orm[:, :, 1].astype(np.float64)
    roughness_variation = min(1.0, float(np.std(roughness) / 52.0))
    ao_std = min(1.0, float(np.std(ao.astype(np.float64)) / 48.0))
    curvature_std = min(1.0, float(np.std(curvature.astype(np.float64)) / 54.0))
    bake_cleanliness = min(1.0, 0.48 * normal_richness + 0.26 * ao_std + 0.26 * curvature_std)

    unique_colors = np.unique(id_map.reshape(-1, id_map.shape[-1]), axis=0)
    unique_colors = [
        tuple(int(value) for value in color)
        for color in unique_colors
        if tuple(int(value) for value in color) != (8, 8, 8)
    ]
    material_zones = [
        entry for entry in _as_list(surface_bundle.get("material_zones")) if isinstance(entry, dict)
    ]
    expected_zone_count = max(
        1,
        len({entry.get("material", entry.get("part")) for entry in material_zones}),
    )
    zone_coverage = min(1.0, len(unique_colors) / expected_zone_count)
    horizontal_edges = (
        np.any(id_map[:, 1:] != id_map[:, :-1], axis=2)
        if id_map.ndim == _RGB_CHANNELS
        else id_map[:, 1:] != id_map[:, :-1]
    )
    vertical_edges = (
        np.any(id_map[1:, :] != id_map[:-1, :], axis=2)
        if id_map.ndim == _RGB_CHANNELS
        else id_map[1:, :] != id_map[:-1, :]
    )
    boundary_density = float((horizontal_edges.mean() + vertical_edges.mean()) / 2.0)
    target_density = 0.018 + min(0.06, expected_zone_count * 0.006)
    boundary_cleanliness = max(
        0.0, 1.0 - abs(boundary_density - target_density) / max(target_density * 1.8, 0.04)
    )
    material_zone_coherence = min(1.0, 0.60 * zone_coverage + 0.40 * boundary_cleanliness)

    emissive_expected = any(max(entry.get("emissive", [0, 0, 0])) > 0 for entry in material_zones)
    emissive_strength = 0.0
    if emissive is not None:
        emissive_strength = float(np.mean(np.max(emissive.astype(np.float64), axis=2)) / 255.0)
    if emissive_expected:
        emissive_coherence = min(1.0, 0.35 + emissive_strength * 1.8) if emissive is not None else 0.0
    else:
        emissive_coherence = 0.8

    highlow = surface_bundle.get("highlow_relation", {})
    high_uri = highlow.get("high_mesh_uri")
    low_uri = highlow.get("low_mesh_uri")
    distinct_mesh_uris = bool(high_uri and low_uri and high_uri != low_uri)
    selected_id = runtime.get("shape", {}).get("bundle", {}).get("selected_candidate_id")
    high_candidate = next(
        (
            candidate
            for candidate in runtime.get("shape", {}).get("bundle", {}).get("candidates", [])
            if candidate.get("candidate_id") == selected_id
        ),
        runtime.get("shape", {}).get("selected", {}),
    )
    high_stats = high_candidate.get("mesh_stats", {}) if isinstance(high_candidate, dict) else {}
    low_stats = runtime.get("topology", {}).get("bundle", {}).get("mesh_stats", {})
    high_triangles = float(highlow.get("high_triangle_count", high_stats.get("triangle_count", 0)))
    low_triangles = float(highlow.get("low_triangle_count", low_stats.get("triangle_count", 0)))
    if high_triangles > low_triangles >= 0.0:
        triangle_delta = (high_triangles - low_triangles) / max(1.0, high_triangles)
    else:
        triangle_delta = 0.0
    highlow_realness = min(1.0, (0.45 if distinct_mesh_uris else 0.0) + min(0.55, triangle_delta / 0.18))
    requested_decals = list(surface_bundle.get("decal_masks", [])) + list(surface_bundle.get("patterns", []))
    if requested_decals:
        decal_coherence = min(
            1.0,
            0.45 * texture_entropy
            + 0.20 * chroma_variation
            + 0.20 * roughness_variation
            + 0.15 * material_zone_coherence,
        )
    else:
        decal_coherence = 0.78

    surface_authoring_quality = min(
        1.0,
        0.20 * texture_entropy
        + 0.12 * chroma_variation
        + 0.18 * normal_richness
        + 0.19 * roughness_variation
        + 0.10 * bake_cleanliness
        + 0.10 * material_zone_coherence
        + 0.04 * decal_coherence
        + 0.01 * emissive_coherence
        + 0.06 * highlow_realness,
    )
    return {
        "texture_entropy": round(texture_entropy, 6),
        "normal_richness": round(normal_richness, 6),
        "roughness_variation": round(roughness_variation, 6),
        "material_zone_coherence": round(material_zone_coherence, 6),
        "decal_coherence": round(decal_coherence, 6),
        "bake_cleanliness": round(bake_cleanliness, 6),
        "highlow_distinction_quality": round(highlow_realness, 6),
        "surface_texture_entropy": round(texture_entropy, 6),
        "surface_chroma_variation": round(chroma_variation, 6),
        "surface_normal_richness": round(normal_richness, 6),
        "surface_roughness_variation": round(roughness_variation, 6),
        "surface_bake_cleanliness": round(bake_cleanliness, 6),
        "surface_material_zone_coherence": round(material_zone_coherence, 6),
        "surface_emissive_coherence": round(emissive_coherence, 6),
        "surface_highlow_realness": round(highlow_realness, 6),
        "surface_authoring_quality": round(surface_authoring_quality, 6),
    }


def _geometry_evidence(
    runtime: dict[str, Any],
    semantic: dict[str, Any],
    shape_assessment: dict[str, Any],
    render_metrics: dict[str, Any],
) -> dict[str, float]:
    topology_runtime = runtime.get("topology", {}).get("runtime_mesh")
    if topology_runtime is None or len(topology_runtime.mesh.faces) == 0:
        return {
            "bevel_continuity": 0.0,
            "seam_quality": 0.0,
            "stair_step_penalty": 1.0,
            "boolean_scar_penalty": 1.0,
            "shading_continuity": 0.0,
            "geometry_dihedral_continuity": 0.0,
            "geometry_feature_edge_persistence": 0.0,
            "geometry_stair_step_penalty": 1.0,
            "geometry_tiny_face_penalty": 1.0,
            "geometry_integration_quality": 0.0,
        }

    mesh = topology_runtime.mesh
    adjacency = np.asarray(mesh.face_adjacency, dtype=np.int64)
    if len(adjacency) == 0:
        return {
            "bevel_continuity": 0.0,
            "seam_quality": 0.0,
            "stair_step_penalty": 1.0,
            "boolean_scar_penalty": 1.0,
            "shading_continuity": 0.0,
            "geometry_dihedral_continuity": 0.0,
            "geometry_feature_edge_persistence": 0.0,
            "geometry_stair_step_penalty": 1.0,
            "geometry_tiny_face_penalty": 1.0,
            "geometry_integration_quality": 0.0,
        }
    try:
        angles = np.asarray(mesh.face_adjacency_angles, dtype=np.float64)
    except (AttributeError, ValueError, IndexError, RuntimeError):
        # trimesh.face_adjacency_angles is a cached property that can raise on
        # meshes without face adjacency or degenerate normal computation;
        # fall back to an explicit dot-product pass.
        normals = np.asarray(mesh.face_normals, dtype=np.float64)
        angles = np.array(
            [
                np.arccos(float(np.clip(np.dot(normals[left], normals[right]), -1.0, 1.0)))
                for left, right in adjacency
            ],
            dtype=np.float64,
        )

    face_parts = list(getattr(topology_runtime, "face_parts", []))
    if len(face_parts) == len(mesh.faces):
        same_part_mask = np.array(
            [face_parts[left] == face_parts[right] for left, right in adjacency], dtype=bool
        )
    else:
        same_part_mask = np.ones(len(adjacency), dtype=bool)
    same_part_angles = angles[same_part_mask] if np.any(same_part_mask) else angles
    cross_part_angles = angles[~same_part_mask] if np.any(~same_part_mask) else angles
    coplanar_ratio = float(np.mean(same_part_angles < _COPLANAR_ANGLE_MAX)) if len(same_part_angles) else 0.0
    stair_step_ratio = (
        float(
            np.mean((same_part_angles >= _COPLANAR_ANGLE_MAX) & (same_part_angles <= _STAIR_STEP_ANGLE_MAX))
        )
        if len(same_part_angles)
        else 1.0
    )
    sharp_boundary_ratio = (
        float(np.mean(cross_part_angles > _SHARP_BOUNDARY_ANGLE_MIN)) if len(cross_part_angles) else 0.0
    )

    face_areas = np.asarray(mesh.area_faces, dtype=np.float64)
    median_area = float(np.median(face_areas)) if len(face_areas) else 0.0
    tiny_face_penalty = (
        min(1.0, float(np.mean(face_areas < max(1e-6, median_area * 0.22))) * 1.55)
        if len(face_areas)
        else 1.0
    )
    boolean_scar_penalty = min(
        1.0, 0.60 * tiny_face_penalty + 0.40 * render_metrics.get("render_assembly_artifact_penalty", 1.0)
    )

    dihedral_continuity = min(
        1.0,
        0.48 * coplanar_ratio
        + 0.22 * (1.0 - stair_step_ratio)
        + 0.14 * (1.0 - render_metrics.get("render_assembly_artifact_penalty", 1.0))
        + 0.16 * semantic.get("adjacency_score", 0.0),
    )
    feature_edge_persistence = min(
        1.0,
        0.42 * min(1.0, sharp_boundary_ratio / 0.20)
        + 0.28 * min(1.0, shape_assessment.get("edge_treatment_count", 0) / 8.0)
        + 0.15 * semantic.get("silhouette_fidelity", 0.0)
        + 0.15 * (1.0 - tiny_face_penalty),
    )
    stair_step_penalty = min(1.0, 0.62 * stair_step_ratio + 0.38 * tiny_face_penalty)
    bevel_continuity = min(1.0, 0.60 * feature_edge_persistence + 0.40 * dihedral_continuity)
    seam_quality = min(
        1.0, 0.55 * min(1.0, sharp_boundary_ratio / 0.18) + 0.45 * semantic.get("adjacency_score", 0.0)
    )
    shading_continuity = min(
        1.0,
        0.55 * dihedral_continuity
        + 0.20 * (1.0 - boolean_scar_penalty)
        + 0.25 * min(1.0, render_metrics.get("render_shading_variance", 0.0) / 0.22),
    )
    geometry_integration_quality = min(
        1.0,
        0.18 * dihedral_continuity
        + 0.14 * feature_edge_persistence
        + 0.14 * bevel_continuity
        + 0.12 * seam_quality
        + 0.12 * shading_continuity
        + 0.10 * (1.0 - stair_step_penalty)
        + 0.08 * (1.0 - boolean_scar_penalty)
        + 0.10 * (1.0 - render_metrics.get("render_assembly_artifact_penalty", 1.0))
        + 0.11 * semantic.get("adjacency_score", 0.0)
        + 0.11 * shape_assessment.get("feature_coherence", 0.0),
    )
    return {
        "bevel_continuity": round(bevel_continuity, 6),
        "seam_quality": round(seam_quality, 6),
        "stair_step_penalty": round(stair_step_penalty, 6),
        "boolean_scar_penalty": round(boolean_scar_penalty, 6),
        "shading_continuity": round(shading_continuity, 6),
        "geometry_dihedral_continuity": round(dihedral_continuity, 6),
        "geometry_feature_edge_persistence": round(feature_edge_persistence, 6),
        "geometry_stair_step_penalty": round(stair_step_penalty, 6),
        "geometry_tiny_face_penalty": round(tiny_face_penalty, 6),
        "geometry_integration_quality": round(geometry_integration_quality, 6),
    }


def _is_generated_asset(asset: dict[str, Any]) -> bool:
    return str(asset.get("build", {}).get("shape", {}).get("mode", "generate")) == "generate"


def _effective_minimum(
    requirements: dict[str, Any],
    key: str,
    default: float,
    generated_floor: float | None,
    asset: dict[str, Any],
) -> float:
    try:
        minimum = float(requirements.get(key, default))
    except (TypeError, ValueError):
        minimum = default
    if generated_floor is not None and _is_generated_asset(asset):
        return max(minimum, generated_floor)
    return minimum


def _visual_metric_details(
    metric: str, actual: float, minimum: float, runtime: dict[str, Any], surface_bundle: dict[str, Any]
) -> dict[str, Any]:
    details: dict[str, Any] = {"metric": metric, "actual": actual, "minimum": minimum}
    if metric == "surface_authoring_quality":
        outputs = surface_bundle.get("outputs", {})
        details.update(
            {
                "surface_backend_id": surface_bundle.get("backend_id", ""),
                "surface_maps": sorted(_requested_surface_maps(surface_bundle)),
                "surface_output_maps": sorted(outputs) if isinstance(outputs, dict) else [],
                "surface_material_zone_count": len(_as_list(surface_bundle.get("material_zones"))),
            }
        )
    elif metric == "geometry_integration_quality":
        topology_runtime = runtime.get("topology", {}).get("runtime_mesh")
        mesh = getattr(topology_runtime, "mesh", None)
        details.update(
            {
                "topology_runtime_mesh_present": topology_runtime is not None,
                "topology_face_count": len(mesh.faces) if mesh is not None and hasattr(mesh, "faces") else 0,
            }
        )
    return details


def evaluate_visual_quality(asset: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
    """Evaluate visual quality.

    Args:
        asset: asset argument.
        runtime: runtime argument.

    Returns:
        The result.
    """
    shape_bundle = runtime["shape"]["bundle"]
    scaffold_report = shape_bundle.get("scaffold_report", {})
    asset_graph = scaffold_report.get("asset_graph", {})
    semantic = runtime.get("semantic_quality", {}).get("metrics", {})
    shape_assessment = shape_bundle.get("shape_assessment", scaffold_report.get("shape_assessment", {}))
    stats = runtime["topology"]["bundle"]["mesh_stats"]
    render_report = runtime.get("render_eval", {}).get("report") or evaluate_render_views(runtime["topology"])
    render_metrics = render_report["metrics"]
    surface_bundle = runtime.get("surface", {}).get("bundle", {})
    expected_parts = max(1, len(asset.get("intent", {}).get("parts", [])))
    feature_count = int(shape_assessment.get("feature_count", 0))
    expected_feature_floor = max(4, expected_parts * 2)
    expected_triangles = max(220, expected_parts * 70 + feature_count * 12)
    detail_density = min(
        1.0,
        0.38 * min(1.0, feature_count / expected_feature_floor)
        + 0.28 * min(1.0, stats["triangle_count"] / expected_triangles)
        + 0.22 * render_metrics.get("render_silhouette_complexity", 0.0)
        + 0.12 * shape_assessment.get("feature_coherence", 0.0),
    )
    silhouette_complexity = min(
        1.0,
        0.35 * shape_assessment.get("silhouette_complexity", 0.0)
        + 0.30 * semantic.get("silhouette_fidelity", 0.0)
        + 0.20 * render_metrics.get("render_silhouette_complexity", 0.0)
        + 0.15 * max(0.0, 1.0 - render_metrics.get("render_primitive_penalty", 1.0)),
    )
    edge_readability = min(
        1.0,
        0.50 * min(1.0, shape_assessment.get("edge_treatment_count", 0) / max(4, expected_parts))
        + 0.20 * detail_density
        + 0.10 * semantic.get("silhouette_fidelity", 0.0)
        + 0.20 * render_metrics.get("render_shading_variance", 0.0),
    )
    attachment_integration_quality = min(
        1.0,
        0.45 * semantic.get("adjacency_score", 0.0)
        + 0.35 * min(1.0, shape_assessment.get("attachment_region_count", 0) / max(1, expected_parts / 2))
        + 0.20 * min(1.0, shape_assessment.get("feature_coherence", 0.0)),
    )
    support_plausibility = _support_plausibility(asset, runtime, shape_assessment)
    feature_coherence = min(
        1.0,
        0.40 * shape_assessment.get("feature_coherence", 0.0)
        + 0.25 * detail_density
        + 0.20 * edge_readability
        + 0.15 * attachment_integration_quality,
    )

    geometry_metrics = _geometry_evidence(runtime, semantic, shape_assessment, render_metrics)
    surface_metrics = _surface_evidence(runtime, surface_bundle)
    geometry_integration_quality = geometry_metrics["geometry_integration_quality"]
    surface_authoring_quality = surface_metrics["surface_authoring_quality"]
    open_frame_family = asset_graph.get("family") == "courier_drone"
    primitive_likeness_penalty = max(
        0.0,
        1.0
        - (
            (0.22 if open_frame_family else 0.24) * detail_density
            + (0.16 if open_frame_family else 0.18) * silhouette_complexity
            + 0.14 * edge_readability
            + 0.10 * feature_coherence
            + (0.14 if open_frame_family else 0.10) * geometry_integration_quality
            + 0.10 * semantic.get("structural_richness", 0.0)
            + (0.06 if open_frame_family else 0.14)
            * (1.0 - render_metrics.get("render_primitive_penalty", 1.0))
            + (0.08 if open_frame_family else 0.0) * attachment_integration_quality
        ),
    )
    assembled_primitives_penalty = max(
        0.0,
        1.0
        - (
            0.26 * attachment_integration_quality
            + 0.18 * support_plausibility
            + 0.12 * feature_coherence
            + 0.16 * geometry_integration_quality
            + 0.12 * semantic.get("symmetry_score", 0.0)
            + 0.16 * (1.0 - render_metrics.get("render_assembly_artifact_penalty", 1.0))
        ),
    )

    metrics = {
        "detail_density": round(detail_density, 6),
        "silhouette_complexity": round(silhouette_complexity, 6),
        "edge_readability": round(edge_readability, 6),
        "attachment_integration_quality": round(attachment_integration_quality, 6),
        "support_plausibility": round(support_plausibility, 6),
        "feature_coherence": round(feature_coherence, 6),
        "geometry_integration_quality": round(geometry_integration_quality, 6),
        "surface_authoring_quality": round(surface_authoring_quality, 6),
        "primitive_likeness_penalty": round(primitive_likeness_penalty, 6),
        "assembled_primitives_penalty": round(assembled_primitives_penalty, 6),
        "render_silhouette_complexity": render_metrics.get("render_silhouette_complexity", 0.0),
        "render_primitive_penalty": render_metrics.get("render_primitive_penalty", 1.0),
        "render_assembly_artifact_penalty": render_metrics.get("render_assembly_artifact_penalty", 1.0),
        "render_shading_variance": render_metrics.get("render_shading_variance", 0.0),
        **geometry_metrics,
        **surface_metrics,
    }

    requirements = asset_graph.get("semantic_requirements", {})
    thresholds = {
        "detail_density": _effective_minimum(requirements, "minimum_detail_density", 0.58, None, asset),
        "silhouette_complexity": _effective_minimum(
            requirements, "minimum_silhouette_complexity", 0.58, None, asset
        ),
        "edge_readability": _effective_minimum(requirements, "minimum_edge_readability", 0.55, None, asset),
        "attachment_integration_quality": _effective_minimum(
            requirements, "minimum_attachment_integration_quality", 0.58, None, asset
        ),
        "support_plausibility": _effective_minimum(
            requirements, "minimum_support_plausibility", 0.52, None, asset
        ),
        "feature_coherence": _effective_minimum(requirements, "minimum_feature_coherence", 0.56, None, asset),
        "geometry_integration_quality": _effective_minimum(
            requirements,
            "minimum_geometry_integration_quality",
            0.0,
            GENERATED_GEOMETRY_INTEGRATION_FLOOR,
            asset,
        ),
        "surface_authoring_quality": _effective_minimum(
            requirements, "minimum_surface_authoring_quality", 0.0, GENERATED_SURFACE_AUTHORING_FLOOR, asset
        ),
        "maximum_primitive_likeness_penalty": _effective_minimum(
            requirements, "maximum_primitive_likeness_penalty", 0.44, None, asset
        ),
        "maximum_assembled_primitives_penalty": _effective_minimum(
            requirements, "maximum_assembled_primitives_penalty", 0.42, None, asset
        ),
    }

    diagnostics: list[dict[str, Any]] = []
    for metric in (
        "detail_density",
        "silhouette_complexity",
        "edge_readability",
        "attachment_integration_quality",
        "support_plausibility",
        "feature_coherence",
        "geometry_integration_quality",
        "surface_authoring_quality",
    ):
        if metrics[metric] < thresholds[metric]:
            diagnostics.append(
                {
                    "code": f"L64{len(diagnostics) + 1:02d}",
                    "name": f"visual_{metric}_failed",
                    "severity": "error",
                    "phase": "validate",
                    "asset": asset["name"],
                    "stage": "validate",
                    "path": f"validate.visual.{metric}",
                    "message": (
                        f"Visual validator failed for {metric}: "
                        f"{metrics[metric]:.3f} < {thresholds[metric]:.3f}"
                    ),
                    "details": _visual_metric_details(
                        metric, metrics[metric], thresholds[metric], runtime, surface_bundle
                    ),
                    "suggested_repairs": suggest_repairs_for_metric(metric, {**metrics, **semantic}),
                }
            )

    for metric, threshold_key in (
        ("primitive_likeness_penalty", "maximum_primitive_likeness_penalty"),
        ("assembled_primitives_penalty", "maximum_assembled_primitives_penalty"),
    ):
        if metrics[metric] > thresholds[threshold_key]:
            diagnostics.append(
                {
                    "code": f"L64{len(diagnostics) + 1:02d}",
                    "name": f"visual_{metric}_failed",
                    "severity": "error",
                    "phase": "validate",
                    "asset": asset["name"],
                    "stage": "validate",
                    "path": f"validate.visual.{metric}",
                    "message": (
                        f"Visual validator failed for {metric}: "
                        f"{metrics[metric]:.3f} > {thresholds[threshold_key]:.3f}"
                    ),
                    "details": {
                        "metric": metric,
                        "actual": metrics[metric],
                        "maximum": thresholds[threshold_key],
                    },
                    "suggested_repairs": suggest_repairs_for_metric(
                        "feature_coherence", {**metrics, **semantic}
                    ),
                }
            )

    return {
        "family": asset_graph.get("family"),
        "blueprint_id": scaffold_report.get("blueprint_id"),
        "metrics": metrics,
        "thresholds": thresholds,
        "diagnostics": diagnostics,
        "render_report": render_report,
    }
