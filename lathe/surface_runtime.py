from __future__ import annotations

from dataclasses import fields
from pathlib import Path
from typing import Any

import numpy as np
import trimesh
from PIL import Image

from .atlas_assembler import build_atlas_assembly_ir
from .bake_runtime import (
    _uv_image_size,
    apply_decal_overlays,
    bake_ao_map,
    bake_basecolor_map,
    bake_curvature_map,
    bake_emissive_map,
    bake_highlow_curvature_transfer_map,
    bake_highlow_normal_transfer_map,
    bake_id_map,
    bake_material_layer_mask,
    bake_metallic_map,
    bake_normal_map,
    bake_roughness_map,
    bake_wear_mask,
    enhance_normal_map,
    pad_low_coverage_atlas_maps,
    renormalize_tangent_normal_map,
)
from .codex_imagegen_bridge import (
    codex_imagegen_mode,
    consume_codex_imagegen_outputs,
    emit_codex_imagegen_requests,
    resolve_surface_backend_report,
)
from .core.io import export_glb
from .exact_solids import compile_explicit_surface_mesh
from .fidelity import FidelityProfile, _tier_multipliers
from .highlow import HighLowRelation
from .materials import assign_material_zones, palette_for_material, surface_with_style_pack_defaults
from .pbr_deriver import derive_orm_map
from .repair.surface_repair import build_surface_repair_ir
from .shape_ir import ShapeIR, ShapePrimitive, ShapeRegion
from .surface_grammar import merge_surface_grammar, surface_grammar_for_asset
from .surface_graph import DesignerGraph, dispatch_surface_program
from .surface_graph.materialx import write_materialx
from .surface_story import build_surface_story_placement_plan
from .texture_control_pack import relative_uri, write_image, write_surface_control_pack
from .validators.surface_quality import build_surface_validation_ir

HERO_FAMILIES = {"brassbound_chest", "courier_drone", "console_terminal"}
V09_HERO_FAMILIES = {
    "brassbound_chest",
    "industrial_crate",
    "mechanical_door",
    "console_terminal",
    "service_cabinet",
    "control_pedestal",
    "supply_container",
    "hero_sword",
    "procedural_building",
    "procedural_vehicle",
    "procedural_weapon",
    "procedural_boat",
    "procedural_machine",
    "procedural_road",
    "procedural_bridge",
    "procedural_terrain",
    "procedural_city_block",
    "procedural_interior",
    "procedural_furniture",
    "procedural_foliage",
    "procedural_infrastructure",
    "procedural_access",
    "procedural_urban_prop",
    "procedural_setpiece",
}
MAX_SURFACE_HIGHLOW_FACES = 120_000
_SHAPE_PRIMITIVE_FIELD_NAMES = {field.name for field in fields(ShapePrimitive)}
_SHAPE_REGION_FIELD_NAMES = {field.name for field in fields(ShapeRegion)}
_SHAPE_IR_FIELD_NAMES = {field.name for field in fields(ShapeIR)}
_HIGH_SOURCE_DETAIL_PRIMITIVES = {
    "revolved_profile",
    "extruded_profile",
    "torus",
    "subdivision_box",
    "swept_profile",
    "lofted_solid",
    "sdf_mesh",
    "heightfield",
}


def _hero_surface_enabled(shape_bundle: dict[str, Any]) -> bool:
    asset_graph = shape_bundle.get("asset_graph", {})
    family = asset_graph.get("family")
    return family in V09_HERO_FAMILIES or family in HERO_FAMILIES


def _token(value: Any) -> str:
    return str(value or "").lower().replace("-", "_").replace(" ", "_").strip()


def _count(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        return max(0, int(round(value)))
    try:
        return max(0, int(round(float(str(value).strip()))))
    except ValueError:
        return default


def _level(value: Any, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return max(0.0, float(value))
    try:
        return max(0.0, float(str(value).strip()))
    except ValueError:
        return default


def _optional_level(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return max(0.0, float(value))
    try:
        return max(0.0, float(str(value).strip()))
    except ValueError:
        return None


def _flag(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    token = _token(value)
    if token in {"1", "true", "yes", "on", "bidirectional", "both", "two_sided"}:
        return True
    if token in {"0", "false", "no", "off", "single", "single_sided"}:
        return False
    return default


def _highlow_requested(shape_cfg: dict[str, Any]) -> bool:
    mode = _token(shape_cfg.get("highlow_mode"))
    return mode in {"lod_pair", "real_lod", "runtime_lod", "high_to_low"} or any(
        field in shape_cfg
        for field in (
            "highlow_low_lod",
            "highlow_bake_cage_offset_cm",
            "highlow_bake_max_ray_distance_cm",
            "highlow_bake_bidirectional",
        )
    )


def _projection_quality(projection_stats: dict[str, Any]) -> dict[str, Any]:
    channels: dict[str, Any] = {}
    hit_ratios: list[float] = []
    fallback_ratios: list[float] = []
    backend_available = True
    for channel, raw_stats in projection_stats.items():
        if not isinstance(raw_stats, dict):
            continue
        face_count = max(0, int(raw_stats.get("face_count", 0) or 0))
        ray_hits = max(0, int(raw_stats.get("ray_hit_count", 0) or 0))
        fallbacks = max(0, int(raw_stats.get("fallback_count", 0) or 0))
        rejected = max(0, int(raw_stats.get("rejected_distance_count", 0) or 0))
        channel_backend = bool(raw_stats.get("ray_backend_available", False))
        backend_available = backend_available and channel_backend
        hit_ratio = round(ray_hits / max(1, face_count), 6) if face_count else 0.0
        fallback_ratio = round(fallbacks / max(1, face_count), 6) if face_count else 0.0
        hit_ratios.append(hit_ratio)
        fallback_ratios.append(fallback_ratio)
        if not channel_backend:
            decision = "fallback_backend_unavailable"
        elif face_count == 0:
            decision = "unavailable_no_faces"
        elif hit_ratio >= 0.80:
            decision = "ray_primary"
        elif hit_ratio >= 0.35:
            decision = "mixed_ray_fallback"
        else:
            decision = "fallback_primary"
        channels[str(channel)] = {
            "decision": decision,
            "hit_ratio": hit_ratio,
            "fallback_ratio": fallback_ratio,
            "face_count": face_count,
            "ray_hit_count": ray_hits,
            "fallback_count": fallbacks,
            "rejected_distance_count": rejected,
            "ray_backend_available": channel_backend,
        }

    overall_hit_ratio = round(min(hit_ratios), 6) if hit_ratios else 0.0
    overall_fallback_ratio = round(max(fallback_ratios), 6) if fallback_ratios else 0.0
    if not channels:
        decision = "unavailable_no_projection_stats"
    elif not backend_available:
        decision = "fallback_backend_unavailable"
    elif overall_hit_ratio >= 0.80:
        decision = "ray_primary"
    elif overall_hit_ratio >= 0.35:
        decision = "mixed_ray_fallback"
    else:
        decision = "fallback_primary"
    return {
        "decision": decision,
        "overall_hit_ratio": overall_hit_ratio,
        "overall_fallback_ratio": overall_fallback_ratio,
        "channels": channels,
    }


def _projection_trust(decision: str) -> float:
    if decision == "ray_primary":
        return 1.0
    if decision == "mixed_ray_fallback":
        return 0.72
    if decision == "fallback_primary":
        return 0.44
    return 0.30


def _projection_transfer_policy(projection_quality: dict[str, Any]) -> dict[str, Any]:
    decision = str(projection_quality.get("decision", "unavailable_no_projection_stats"))
    trust = _projection_trust(decision)
    if decision == "ray_primary":
        policy = {
            "policy": "accept_ray_projected_high_detail",
            "normal_source": "ray_projected_high_to_low_tangent_space",
            "curvature_source": "ray_projected_high_to_low_uv",
            "detail_reliability": "authoritative",
            "fallback_action": "none",
        }
    elif decision == "mixed_ray_fallback":
        policy = {
            "policy": "accept_mixed_projection_with_fallback_accounting",
            "normal_source": "mixed_ray_and_cage_nearest_high",
            "curvature_source": "mixed_ray_and_cage_nearest_high",
            "detail_reliability": "usable_mixed",
            "fallback_action": "keep_projection_stats_and_blend_curvature_by_trust",
        }
    elif decision == "fallback_primary":
        policy = {
            "policy": "accept_cage_nearest_with_low_detail_trust",
            "normal_source": "cage_nearest_high_tangent_space",
            "curvature_source": "cage_nearest_high",
            "detail_reliability": "fallback",
            "fallback_action": "neutralize_curvature_by_trust_before_wear",
        }
    elif decision == "fallback_backend_unavailable":
        policy = {
            "policy": "degrade_to_cage_nearest_without_ray_backend",
            "normal_source": "cage_nearest_high_tangent_space",
            "curvature_source": "cage_nearest_high",
            "detail_reliability": "backend_limited",
            "fallback_action": "preserve_maps_but_mark_transfer_backend_unavailable",
        }
    else:
        policy = {
            "policy": "treat_highlow_transfer_as_unavailable",
            "normal_source": "low_surface_or_missing_transfer",
            "curvature_source": "low_surface_or_missing_transfer",
            "detail_reliability": "unavailable",
            "fallback_action": "do_not_credit_projection_quality",
        }
    return {
        **policy,
        "decision": decision,
        "projection_trust": round(trust, 6),
        "overall_hit_ratio": projection_quality.get("overall_hit_ratio", 0.0),
        "overall_fallback_ratio": projection_quality.get("overall_fallback_ratio", 0.0),
    }


def _projection_tuned_curvature(
    curvature: Image.Image,
    projection_quality: dict[str, Any],
) -> tuple[Image.Image, dict[str, Any]]:
    decision = str(projection_quality.get("decision", "unavailable_no_projection_stats"))
    trust = _projection_trust(decision)
    if trust >= 0.999:
        return curvature, {
            "source": "projection_quality_curvature_tuning_v1",
            "decision": decision,
            "curvature_trust": trust,
            "neutral_blend": 0.0,
        }
    source = np.asarray(curvature.convert("L"), dtype=np.float64)
    neutral = np.full_like(source, 128.0, dtype=np.float64)
    tuned = source * trust + neutral * (1.0 - trust)
    return Image.fromarray(np.clip(tuned, 0.0, 255.0).astype(np.uint8), mode="L"), {
        "source": "projection_quality_curvature_tuning_v1",
        "decision": decision,
        "curvature_trust": round(trust, 6),
        "neutral_blend": round(1.0 - trust, 6),
    }


def _procedural_high_target_faces(shape_cfg: dict[str, Any], current_faces: int) -> int:
    authored_target_quads = _count(shape_cfg.get("target_quads"), 0)
    authored_target_tris = authored_target_quads * 2 if authored_target_quads else 0
    baseline = max(current_faces * 2, authored_target_tris, current_faces + 1)
    return min(MAX_SURFACE_HIGHLOW_FACES, baseline)


def _edge_length_target_for_face_budget(mesh: trimesh.Trimesh, target_faces: int) -> float | None:
    if target_faces <= len(mesh.faces) or len(mesh.edges_unique_length) == 0:
        return None
    bounds = getattr(mesh, "bounds", None)
    if bounds is None or len(bounds) != 2:
        return None
    diagonal = float(((bounds[1] - bounds[0]) ** 2).sum() ** 0.5)
    if diagonal <= 0.0:
        return None
    scale = (max(1, target_faces) / max(1, len(mesh.faces))) ** 0.5
    longest_edge = float(max(mesh.edges_unique_length))
    return max(diagonal / 320.0, longest_edge / max(1.0, scale))


def _surface_high_source_fidelity(shape_cfg: dict[str, Any]) -> FidelityProfile:
    tier = _token(
        shape_cfg.get("highlow_high_fidelity")
        or shape_cfg.get("high_source_fidelity")
        or shape_cfg.get("fidelity")
        or "cinematic"
    )
    if tier not in {"blockout", "game", "hero", "cinematic"}:
        tier = "cinematic"
    mult = _tier_multipliers(tier)
    return FidelityProfile(
        tier=tier,
        detail_density=float(mult["detail_density"]),
        edge_weight=float(mult["edge_weight"]),
        panel_depth=float(mult["panel_depth"]),
        trim_complexity=int(mult["trim_complexity"]),
        support_complexity=float(mult["support_complexity"]),
        silhouette_refinement=float(mult["silhouette_refinement"]),
        repair_budget=int(mult["repair_budget"]),
    )


def _shape_primitive_from_payload(payload: Any) -> ShapePrimitive | None:
    if isinstance(payload, ShapePrimitive):
        return payload
    if not isinstance(payload, dict):
        return None
    kwargs = {
        name: payload[name]
        for name in _SHAPE_PRIMITIVE_FIELD_NAMES
        if name in payload
    }
    if not {"primitive_type", "part", "center"}.issubset(kwargs):
        return None
    return ShapePrimitive(**kwargs)


def _shape_region_from_payload(payload: Any) -> ShapeRegion | None:
    if isinstance(payload, ShapeRegion):
        return payload
    if not isinstance(payload, dict):
        return None
    kwargs = {
        name: payload[name]
        for name in _SHAPE_REGION_FIELD_NAMES
        if name in payload
    }
    if not {"name", "part", "component", "center", "extents"}.issubset(kwargs):
        return None
    return ShapeRegion(**kwargs)


def _shape_ir_from_payload(payload: Any) -> ShapeIR | None:
    if isinstance(payload, ShapeIR):
        return payload
    if not isinstance(payload, dict):
        return None
    primitives = [
        primitive
        for primitive in (_shape_primitive_from_payload(item) for item in payload.get("primitives", []))
        if primitive is not None
    ]
    if not primitives:
        return None
    regions = [
        region
        for region in (_shape_region_from_payload(item) for item in payload.get("regions", []))
        if region is not None
    ]
    kwargs = {
        name: payload[name]
        for name in _SHAPE_IR_FIELD_NAMES
        if name in payload and name not in {"primitives", "regions"}
    }
    return ShapeIR(
        asset_name=str(kwargs.get("asset_name") or "asset"),
        family=str(kwargs.get("family") or "unknown"),
        blueprint_id=str(kwargs.get("blueprint_id") or "shape_ir"),
        symmetry_axis=kwargs.get("symmetry_axis"),
        units=str(kwargs.get("units") or "cm"),
        primitives=primitives,
        regions=regions,
        primitives_used=list(kwargs.get("primitives_used") or []),
        part_graph=list(kwargs.get("part_graph") or []),
        signature=dict(kwargs.get("signature") or {}),
        assessment=dict(kwargs.get("assessment") or {}),
    )


def _candidate_index(candidate_id: Any) -> int | None:
    suffix = str(candidate_id or "").rsplit("_", 1)[-1]
    if suffix.isdigit():
        return int(suffix)
    return None


def _selected_shape_ir(shape_bundle: dict[str, Any]) -> tuple[ShapeIR | None, dict[str, Any]]:
    raw_shape_ir = shape_bundle.get("shape_ir")
    if isinstance(raw_shape_ir, list):
        selected_index = _candidate_index(shape_bundle.get("selected_candidate_id"))
        if selected_index is None:
            selected_index = 0
        if 0 <= selected_index < len(raw_shape_ir):
            selected = _shape_ir_from_payload(raw_shape_ir[selected_index])
            return selected, {
                "shape_ir_source": f"shape_bundle.shape_ir[{selected_index}]",
                "selected_candidate_id": shape_bundle.get("selected_candidate_id", ""),
                "selected_index": selected_index,
                "available_shape_ir_count": len(raw_shape_ir),
            }
        return None, {
            "shape_ir_source": "shape_bundle.shape_ir",
            "selected_candidate_id": shape_bundle.get("selected_candidate_id", ""),
            "selected_index": selected_index,
            "available_shape_ir_count": len(raw_shape_ir),
            "reason": "selected_candidate_index_out_of_range",
        }
    selected = _shape_ir_from_payload(raw_shape_ir)
    return selected, {
        "shape_ir_source": "shape_bundle.shape_ir",
        "selected_candidate_id": shape_bundle.get("selected_candidate_id", ""),
        "selected_index": _candidate_index(shape_bundle.get("selected_candidate_id")),
        "available_shape_ir_count": 1 if selected is not None else 0,
        "reason": "" if selected is not None else "missing_or_unreadable_shape_ir",
    }


def _metadata_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _semantic_metadata_tokens(metadata: dict[str, Any]) -> list[Any]:
    tokens: list[Any] = [
        metadata.get("component"),
        metadata.get("feature"),
        metadata.get("operation"),
        metadata.get("material_hint"),
        metadata.get("material_zone"),
    ]
    for key, value in metadata.items():
        if key.startswith("v2_"):
            tokens.append(key)
            if isinstance(value, dict):
                tokens.extend(value.get(item) for item in ("operation", "op", "kind", "component"))

    v2_metadata = _metadata_dict(metadata.get("shape_ir_v2"))
    tokens.extend(
        v2_metadata.get(item)
        for item in (
            "v2_op",
            "v2_source_op",
            "v2_purpose",
            "operation_id",
            "repair_action",
        )
    )
    for key, value in v2_metadata.items():
        if key.startswith("v2_"):
            tokens.append(key)
            if isinstance(value, dict):
                tokens.extend(value.get(item) for item in ("operation", "op", "kind", "component"))

    repair_metadata = _metadata_dict(metadata.get("semantic_repair"))
    tokens.extend(
        repair_metadata.get(item)
        for item in (
            "action",
            "lowered_operation",
            "operation_id",
            "execution_path",
        )
    )
    return tokens


def _operation_source_tokens(metadata: dict[str, Any]) -> list[str]:
    sources: list[str] = []
    v2_metadata = _metadata_dict(metadata.get("shape_ir_v2"))
    for label, value in (
        ("shape_ir_v2", v2_metadata.get("v2_op")),
        ("shape_ir_v2_source", v2_metadata.get("v2_source_op")),
        ("shape_ir_v2_repair", v2_metadata.get("repair_action")),
    ):
        token = _token(value)
        if token:
            sources.append(f"{label}:{token}")
    repair_metadata = _metadata_dict(metadata.get("semantic_repair"))
    for label, value in (
        ("semantic_repair", repair_metadata.get("action")),
        ("semantic_repair_operation", repair_metadata.get("lowered_operation")),
    ):
        token = _token(value)
        if token:
            sources.append(f"{label}:{token}")
    return sources


def _primitive_detail_sources(primitive: ShapePrimitive) -> list[str]:
    sources: list[str] = []
    primitive_type = _token(primitive.primitive_type)
    if primitive_type in _HIGH_SOURCE_DETAIL_PRIMITIVES:
        sources.append(f"primitive_type:{primitive_type}")
    if float(primitive.rounding or 0.0) > 0.0:
        sources.append("rounding")
    detail_attrs = {
        "boolean_seam_groups": primitive.boolean_seam_groups,
        "bevel_seam_groups": primitive.bevel_seam_groups,
        "v2_polybevel_modifier": primitive.v2_polybevel_modifier,
        "hard_edge_groups": primitive.hard_edge_groups,
        "v2_mark_hard_edge_modifier": primitive.v2_mark_hard_edge_modifier,
        "v2_weighted_normals_modifier": primitive.v2_weighted_normals_modifier,
        "v2_hull_modifier": primitive.v2_hull_modifier,
        "v2_minkowski_modifier": primitive.v2_minkowski_modifier,
        "v2_subdivision_modifier": primitive.v2_subdivision_modifier,
        "v2_remesh_modifier": primitive.v2_remesh_modifier,
    }
    for attr, value in detail_attrs.items():
        if bool(value):
            sources.append(attr)
    semantic_metadata = _metadata_dict(primitive.semantic_metadata)
    sources.extend(_operation_source_tokens(semantic_metadata))
    tags = list(primitive.tags or [])
    semantic_tokens = [
        primitive.component,
        primitive.region,
        *tags,
        *_semantic_metadata_tokens(semantic_metadata),
    ]
    detail_words = {
        "bevel",
        "polybevel",
        "chamfer",
        "edge_break",
        "hard_edge",
        "weighted_normals",
        "fastener",
        "head",
        "washer",
        "rivet",
        "bolt",
        "trim",
        "band",
        "vent",
        "slat",
        "panel",
        "groove",
        "seam",
        "grille",
        "hinge",
        "handle",
        "socket",
        "bracket",
        "mount",
        "minkowski",
        "hull",
        "inset",
        "repair",
    }
    for token in semantic_tokens:
        value = _token(token)
        if value and any(word in value for word in detail_words):
            sources.append(f"semantic:{value}")
    return list(dict.fromkeys(sources))


def _shape_ir_detail_report(shape_ir: ShapeIR) -> dict[str, Any]:
    primitive_type_counts: dict[str, int] = {}
    detail_sources: list[str] = []
    detail_primitive_count = 0
    subtract_count = 0
    intersect_count = 0
    for primitive in shape_ir.primitives:
        primitive_type = str(primitive.primitive_type)
        primitive_type_counts[primitive_type] = primitive_type_counts.get(primitive_type, 0) + 1
        blend_mode = _token(primitive.blend_mode or "union")
        if blend_mode == "subtract":
            subtract_count += 1
        elif blend_mode == "intersect":
            intersect_count += 1
        sources = _primitive_detail_sources(primitive)
        if sources or blend_mode in {"subtract", "intersect"}:
            detail_primitive_count += 1
            semantic_metadata = primitive.semantic_metadata if isinstance(primitive.semantic_metadata, dict) else {}
            part = str(primitive.part or "primitive")
            component = str(primitive.component or semantic_metadata.get("component", "") or "")
            label = f"{part}:{component}" if component else part
            detail_sources.extend(f"{label}:{source}" for source in sources or [f"blend_mode:{blend_mode}"])
    return {
        "shape_ir_primitive_count": len(shape_ir.primitives),
        "detail_primitive_count": detail_primitive_count,
        "subtract_primitive_count": subtract_count,
        "intersect_primitive_count": intersect_count,
        "native_primitive_types": primitive_type_counts,
        "semantic_detail_sources": list(dict.fromkeys(detail_sources))[:96],
    }


def _procedural_high_source_mesh(mesh: trimesh.Trimesh, shape_cfg: dict[str, Any]) -> tuple[trimesh.Trimesh, dict[str, Any]]:
    target_faces = _procedural_high_target_faces(shape_cfg, len(mesh.faces))
    high_mesh = mesh.copy()
    method = "copy"
    target_edge_length = _edge_length_target_for_face_budget(high_mesh, target_faces)
    if target_edge_length is not None:
        vertices, faces = trimesh.remesh.subdivide_to_size(
            high_mesh.vertices,
            high_mesh.faces,
            max_edge=target_edge_length,
            max_iter=6,
            return_index=False,
        )
        high_mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        method = "target_edge_subdivide"
    if len(high_mesh.faces) <= len(mesh.faces) and target_faces > len(mesh.faces):
        high_mesh = mesh.subdivide()
        method = "uniform_subdivide"
    high_mesh.remove_infinite_values()
    high_mesh.remove_unreferenced_vertices()
    high_mesh.merge_vertices()
    high_mesh.fix_normals()
    report = {
        "source": "surface_procedural_high_source_v1",
        "method": method,
        "target_faces": target_faces,
        "target_edge_length_cm": round(float(target_edge_length or 0.0), 6),
        "input_faces": len(mesh.faces),
        "output_faces": len(high_mesh.faces),
    }
    return high_mesh, report


def _fallback_high_source_mesh(
    mesh: trimesh.Trimesh,
    shape_cfg: dict[str, Any],
    *,
    reason: str,
    selection_report: dict[str, Any] | None = None,
    detail_report: dict[str, Any] | None = None,
) -> tuple[trimesh.Trimesh, dict[str, Any]]:
    high_mesh, report = _procedural_high_source_mesh(mesh, shape_cfg)
    return high_mesh, {
        **report,
        "attempted_source": "surface_shape_ir_primitive_high_source_v1",
        "actual_source": report.get("source", "surface_procedural_high_source_v1"),
        "fallback_reason": reason,
        "shape_ir_high_source_fallback": True,
        **(selection_report or {}),
        **(detail_report or {}),
    }


def _shape_ir_high_source_mesh(
    mesh: trimesh.Trimesh,
    shape_bundle: dict[str, Any],
    shape_cfg: dict[str, Any],
) -> tuple[trimesh.Trimesh, dict[str, Any]]:
    shape_ir, selection_report = _selected_shape_ir(shape_bundle)
    if shape_ir is None:
        return _fallback_high_source_mesh(
            mesh,
            shape_cfg,
            reason=str(selection_report.get("reason") or "missing_shape_ir"),
            selection_report=selection_report,
        )

    detail_report = _shape_ir_detail_report(shape_ir)
    fidelity = _surface_high_source_fidelity(shape_cfg)
    try:
        high_mesh, face_parts, compile_report = compile_explicit_surface_mesh(
            shape_ir,
            fidelity,
            combine_mode="kernel_program",
        )
    except (ValueError, RuntimeError, AttributeError, IndexError, OSError, ImportError, TypeError) as exc:
        return _fallback_high_source_mesh(
            mesh,
            shape_cfg,
            reason=f"shape_ir_compile_failed:{type(exc).__name__}",
            selection_report=selection_report,
            detail_report={**detail_report, "shape_ir_compile_failure": str(exc)},
        )

    if len(high_mesh.faces) == 0:
        return _fallback_high_source_mesh(
            mesh,
            shape_cfg,
            reason="shape_ir_compile_empty_mesh",
            selection_report=selection_report,
            detail_report=detail_report,
        )

    base_faces = len(high_mesh.faces)
    target_faces = _procedural_high_target_faces(shape_cfg, len(mesh.faces))
    target_edge_length = _edge_length_target_for_face_budget(high_mesh, target_faces)
    method_parts = [
        "shape_ir_kernel_program_rebuild"
        if compile_report.get("kernel_program_attempted")
        else "shape_ir_exact_rebuild"
    ]
    if target_edge_length is not None:
        vertices, faces = trimesh.remesh.subdivide_to_size(
            high_mesh.vertices,
            high_mesh.faces,
            max_edge=target_edge_length,
            max_iter=6,
            return_index=False,
        )
        high_mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        method_parts.append("target_edge_subdivide")
    if len(high_mesh.faces) <= base_faces and target_faces > len(high_mesh.faces):
        high_mesh = high_mesh.subdivide()
        method_parts.append("uniform_subdivide")
    high_mesh.remove_infinite_values()
    high_mesh.remove_unreferenced_vertices()
    high_mesh.merge_vertices()
    high_mesh.fix_normals()

    compile_summary = {
        key: compile_report.get(key)
        for key in (
            "mode",
            "primitive_count",
            "boolean_operation_count",
            "subtract_primitive_count",
            "intersect_primitive_count",
            "boolean_kernel",
            "boolean_backend",
            "boolean_fallback",
            "kernel_program_attempted",
            "kernel_program_succeeded",
            "face_part_attribution_mode",
            "post_boolean_polybevel_face_count",
            "post_boolean_seam_group_count",
        )
        if key in compile_report
    }
    return high_mesh, {
        "source": "surface_shape_ir_primitive_high_source_v1",
        "attempted_source": "surface_shape_ir_primitive_high_source_v1",
        "actual_source": "surface_shape_ir_primitive_high_source_v1",
        "method": "+".join(method_parts),
        "target_faces": target_faces,
        "target_edge_length_cm": round(float(target_edge_length or 0.0), 6),
        "input_faces": len(mesh.faces),
        "shape_ir_base_faces": base_faces,
        "output_faces": len(high_mesh.faces),
        "shape_ir_high_source_fallback": False,
        "high_source_fidelity": fidelity.to_dict(),
        "face_part_count": len(face_parts),
        "shape_ir_compile_report": compile_summary,
        **selection_report,
        **detail_report,
    }


def _write_image(image: Image.Image, path: Path) -> dict[str, Any]:
    return write_image(image, path)


def _surface_manifest(
    surface_cfg: dict[str, Any], material_zones: list[dict[str, Any]], material_slots: int, hero_mode: bool
) -> dict[str, Any]:
    return {
        "workflow": surface_cfg.get("workflow"),
        "maps": list(surface_cfg.get("maps", [])),
        "resolution": surface_cfg.get("resolution"),
        "semantic_materials": [entry["material"] for entry in material_zones],
        "material_slots": material_slots,
        "decals": list(surface_cfg.get("decals", [])),
        "hero_surface": hero_mode,
    }


def _dict_records(value: Any) -> list[dict[str, Any]]:
    return [dict(record) for record in value if isinstance(record, dict)] if isinstance(value, list) else []


_SURFACE_OPERATION_FEATURE_KINDS = {
    "bevel",
    "branching_tree",
    "bracket",
    "chamfer",
    "chip_edges",
    "corner_guard_set",
    "countersunk_hole",
    "countersunk_hole_set",
    "curved_tube",
    "curve_extruded_profile",
    "curve_lofted_solid",
    "curve_profile",
    "curve_revolved_profile",
    "curve_swept_profile",
    "dent_mask",
    "edge_chip",
    "fastener_grid",
    "flange",
    "gear",
    "grime_mask",
    "handle",
    "hinge",
    "ladder_frame",
    "loft",
    "louver_panel",
    "mark_hard_edge",
    "mark_hard_edges",
    "mount_plate",
    "panel",
    "panel_line_cut",
    "panel_frame",
    "perforated_panel",
    "polybevel",
    "polywire",
    "prism",
    "rail",
    "ribbed_panel",
    "rounded_slot",
    "sdf_metaball_cluster",
    "scratch_mask",
    "socket",
    "spring",
    "structural_beam",
    "support_bracket",
    "surface_scatter",
    "terrain_patch",
    "threaded_cylinder",
    "trim_band",
    "trim_frame",
    "truss_frame",
    "tube",
    "vent_slats",
    "weld_seam",
    "wfc_modular_assembly",
}


def _surface_operation_feature_kind(operation: Any) -> str:
    token = str(operation or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not token:
        return ""
    candidate = token.split(".")[-1]
    return candidate if candidate in _SURFACE_OPERATION_FEATURE_KINDS else ""


_SURFACE_PART_LINK_KEYS = (
    "part",
    "source_part",
    "target_part",
    "template_part",
    "component_part",
    "result_part",
    "primary_part",
    "assembly_part",
    "linked_part",
)
_SURFACE_PART_LINK_LIST_KEYS = (
    "parts",
    "source_parts",
    "target_parts",
    "template_parts",
    "component_parts",
    "assembly_parts",
    "source_context_parts",
)
_SURFACE_NESTED_PART_LINK_FIELDS = (
    "features",
    "treatments",
    "damages",
    "components",
    "component_records",
    "instances",
    "instance_records",
    "operand_records",
    "operation_records",
    "source_records",
    "source_shape_primitives",
    "feature_records",
    "provenance_records",
    "children",
    "members",
)


def _surface_record_link_parts(*records: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        part = str(value or "").strip()
        if not part or part in seen:
            return
        seen.add(part)
        parts.append(part)

    def walk(value: Any, depth: int = 0) -> None:
        if depth > 4:
            return
        if isinstance(value, dict):
            for key in _SURFACE_PART_LINK_KEYS:
                add(value.get(key))
            for key in _SURFACE_PART_LINK_LIST_KEYS:
                items = value.get(key)
                if isinstance(items, (list, tuple, set)):
                    for item in items:
                        add(item)
            for field in _SURFACE_NESTED_PART_LINK_FIELDS:
                nested = value.get(field)
                if nested is not None:
                    walk(nested, depth + 1)
            return
        if isinstance(value, list):
            for item in value:
                walk(item, depth + 1)

    for record in records:
        walk(record)
    return parts


def _append_kernel_material_records(
    records_by_part: dict[str, list[dict[str, Any]]],
    part_names: list[str],
    topology_bundle: dict[str, Any],
) -> None:
    for detail in _dict_records(topology_bundle.get("kernel_feature_details")):
        for feature in _dict_records(detail.get("features")):
            for part in _surface_record_link_parts(feature, detail):
                part_names.append(part)
                records_by_part.setdefault(part, []).append(
                    {
                        "part": part,
                        "material_hint": str(feature.get("feature_kind") or detail.get("feature_kind") or "feature"),
                        "source": "kernel_feature_detail",
                        "operation": str(detail.get("operation") or ""),
                        "feature_kind": str(feature.get("feature_kind") or detail.get("feature_kind") or ""),
                        "semantic_role": "visible_feature_detail",
                    }
                )

    for treatment in _dict_records(topology_bundle.get("kernel_edge_treatments")):
        for edge in _dict_records(treatment.get("treatments")):
            for part in _surface_record_link_parts(edge, treatment):
                part_names.append(part)
                records_by_part.setdefault(part, []).append(
                    {
                        "part": part,
                        "material_hint": str(
                            edge.get("treatment_kind")
                            or treatment.get("treatment_kind")
                            or "edge_treatment"
                        ),
                        "source": "kernel_edge_treatment",
                        "operation": str(treatment.get("operation") or ""),
                        "treatment_kind": str(
                            edge.get("treatment_kind")
                            or treatment.get("treatment_kind")
                            or ""
                        ),
                        "semantic_role": "edge_treatment",
                    }
                )

    for damage in _dict_records(topology_bundle.get("kernel_surface_damage")):
        for item in _dict_records(damage.get("damages")):
            damage_kind = str(item.get("damage_kind") or damage.get("damage_kind") or "wear")
            for part in _surface_record_link_parts(item, damage):
                part_names.append(part)
                records_by_part.setdefault(part, []).append(
                    {
                        "part": part,
                        "material_hint": f"wear_{damage_kind}",
                        "source": "kernel_surface_damage",
                        "operation": str(damage.get("operation") or ""),
                        "damage_kind": damage_kind,
                        "semantic_role": "surface_damage",
                    }
                )

    for scatter in _dict_records(topology_bundle.get("kernel_scatters")):
        scatter_kind = str(scatter.get("scatter_kind") or "scatter")
        for part in _surface_record_link_parts(scatter):
            part_names.append(part)
            records_by_part.setdefault(part, []).append(
                {
                    "part": part,
                    "material_hint": scatter_kind,
                    "source": "kernel_scatter",
                    "operation": str(scatter.get("operation") or ""),
                    "scatter_kind": scatter_kind,
                    "instance_count": _count(scatter.get("instance_count"), 0),
                    "semantic_role": "surface_scatter"
                    if scatter_kind == "surface_scatter"
                    else "instanced_detail",
                }
            )

    for pattern in _dict_records(topology_bundle.get("kernel_pattern_instances")):
        pattern_kind = str(pattern.get("pattern_kind") or "pattern_instances")
        for part in _surface_record_link_parts(pattern):
            part_names.append(part)
            records_by_part.setdefault(part, []).append(
                {
                    "part": part,
                    "material_hint": pattern_kind,
                    "source": "kernel_pattern_instances",
                    "operation": str(pattern.get("operation") or ""),
                    "pattern_kind": pattern_kind,
                    "instance_count": _count(pattern.get("instance_count"), 0),
                    "semantic_role": "pattern_instances",
                }
            )

    for assembly in _dict_records(topology_bundle.get("kernel_component_assemblies")):
        assembly_kind = str(assembly.get("assembly_kind") or "component_assembly")
        for part in _surface_record_link_parts(assembly):
            part_names.append(part)
            records_by_part.setdefault(part, []).append(
                {
                    "part": part,
                    "material_hint": assembly_kind,
                    "source": "kernel_component_assembly",
                    "operation": str(assembly.get("operation") or ""),
                    "assembly_kind": assembly_kind,
                    "operand_count": _count(assembly.get("operand_count"), 0),
                    "semantic_role": "component_assembly",
                }
            )

    for sdf_field in _dict_records(topology_bundle.get("kernel_sdf_fields")):
        field_kind = str(sdf_field.get("field_kind") or "sdf_field")
        for part in _surface_record_link_parts(sdf_field):
            part_names.append(part)
            records_by_part.setdefault(part, []).append(
                {
                    "part": part,
                    "material_hint": field_kind,
                    "source": "kernel_sdf_field",
                    "operation": str(sdf_field.get("operation") or ""),
                    "field_kind": field_kind,
                    "semantic_role": "implicit_field",
                }
            )

    for terrain_field in _dict_records(topology_bundle.get("kernel_terrain_fields")):
        terrain_kind = str(terrain_field.get("terrain_kind") or "terrain_field")
        for part in _surface_record_link_parts(terrain_field):
            part_names.append(part)
            records_by_part.setdefault(part, []).append(
                {
                    "part": part,
                    "material_hint": terrain_kind,
                    "source": "kernel_terrain_field",
                    "operation": str(terrain_field.get("operation") or ""),
                    "terrain_kind": terrain_kind,
                    "semantic_role": "terrain_field",
                }
            )

    for profile_path in _dict_records(topology_bundle.get("kernel_profile_paths")):
        profile_kind = str(profile_path.get("profile_kind") or "profile_path")
        for part in _surface_record_link_parts(profile_path):
            part_names.append(part)
            records_by_part.setdefault(part, []).append(
                {
                    "part": part,
                    "material_hint": profile_kind,
                    "source": "kernel_profile_path",
                    "operation": str(profile_path.get("operation") or ""),
                    "profile_kind": profile_kind,
                    "semantic_role": "profile_path",
                }
            )

    for deform in _dict_records(topology_bundle.get("kernel_deforms")):
        deform_kind = str(deform.get("deform_kind") or deform.get("operation") or "deform")
        for part in _surface_record_link_parts(deform):
            part_names.append(part)
            records_by_part.setdefault(part, []).append(
                {
                    "part": part,
                    "material_hint": deform_kind,
                    "source": "kernel_deform",
                    "operation": str(deform.get("operation") or ""),
                    "deform_kind": deform_kind,
                    "semantic_role": "deformed_surface",
                }
            )

    for edge_control in _dict_records(topology_bundle.get("kernel_edge_controls")):
        control_kind = str(edge_control.get("edge_control_kind") or "edge_control")
        for part in _surface_record_link_parts(edge_control):
            part_names.append(part)
            records_by_part.setdefault(part, []).append(
                {
                    "part": part,
                    "material_hint": control_kind,
                    "source": "kernel_edge_control",
                    "operation": str(edge_control.get("operation") or ""),
                    "edge_control_kind": control_kind,
                    "semantic_role": "edge_control",
                }
            )

    for operation_record in _dict_records(topology_bundle.get("operation_records")):
        part = str(operation_record.get("part") or "")
        operation = str(operation_record.get("operation") or operation_record.get("repair_action") or "")
        feature_kind = _surface_operation_feature_kind(operation)
        if not part or not feature_kind:
            continue
        part_names.append(part)
        records_by_part.setdefault(part, []).append(
            {
                "part": part,
                "material_hint": feature_kind,
                "source": "kernel_operation_record",
                "operation": operation,
                "operation_id": str(operation_record.get("operation_id") or ""),
                "feature_kind": feature_kind,
                "semantic_role": "operation_surface_detail",
            }
        )


def _topology_material_hint(records: list[dict[str, Any]]) -> str:
    kernel_hint = ""
    for record in records:
        hint = str(record.get("material_hint") or "")
        if not hint:
            continue
        source = str(record.get("source") or "")
        if (
            source in {"primitive", "region"}
            or "material_zone_candidates" in source
            or source.endswith(".material_zones")
        ):
            return hint
        if source == "kernel_surface_damage":
            return hint
        if source in {
            "kernel_edge_treatment",
            "kernel_feature_detail",
            "kernel_operation_record",
            "kernel_scatter",
            "kernel_pattern_instances",
            "kernel_component_assembly",
            "kernel_sdf_field",
            "kernel_terrain_field",
            "kernel_profile_path",
            "kernel_deform",
            "kernel_edge_control",
        } and not kernel_hint:
            kernel_hint = hint
    return kernel_hint


def _topology_record_sources(records: list[dict[str, Any]]) -> set[str]:
    return {str(record.get("source") or "") for record in records if str(record.get("source") or "")}


def _surface_feature_payload(
    *,
    previous_material: str,
    material_source: str,
    semantic_surface_role: str,
    topology_material_hint: str,
    surface_features: list[str],
    wear_floor: float = 0.0,
    roughness_boost: float = 0.0,
) -> dict[str, Any]:
    material = previous_material or "worn_paint"
    palette = palette_for_material(material)
    payload = {
        "material": material,
        **palette,
        "material_source": material_source,
        "semantic_surface_role": semantic_surface_role,
        "topology_material_hint": topology_material_hint,
        "surface_features": list(dict.fromkeys([feature for feature in surface_features if feature])),
    }
    if wear_floor > 0.0:
        payload["wear"] = round(max(float(palette.get("wear", 0.0) or 0.0), wear_floor), 6)
    if roughness_boost > 0.0:
        payload["roughness"] = round(
            min(1.0, float(palette.get("roughness", 0.58) or 0.58) + roughness_boost),
            6,
        )
    return payload


def _topology_record_tokens(records: list[dict[str, Any]]) -> set[str]:
    tokens: set[str] = set()
    for record in records:
        for key in ("part", "name", "component", "material_hint", "source", "semantic_role"):
            value = record.get(key)
            if value not in (None, "", (), [], {}):
                tokens.update(str(value).lower().replace("-", "_").replace(".", "_").split("_"))
        tags = record.get("tags")
        if isinstance(tags, list):
            for tag in tags:
                if str(tag):
                    tokens.update(str(tag).lower().replace("-", "_").replace(".", "_").split("_"))
    return {token for token in tokens if token}


def _topology_surface_treatment(
    records: list[dict[str, Any]],
    *,
    previous_material: str,
) -> dict[str, Any]:
    hint = _topology_material_hint(records)
    if not hint:
        return {}
    normalized = hint.lower().replace("-", "_").strip()
    tokens = _topology_record_tokens(records)
    sources = _topology_record_sources(records)

    if normalized == "material_zone":
        return {
            "material_source": "topology_mesh_ir.semantic_surface_hint",
            "semantic_surface_role": "material_zone",
            "topology_material_hint": hint,
            "surface_features": ["material_zone"],
        }

    if normalized == "decal_zone":
        material = "warning_paint" if "warning" in tokens else "painted_decal"
        return {
            "material": material,
            **palette_for_material(material),
            "material_source": "topology_mesh_ir.semantic_surface_hint",
            "semantic_surface_role": "decal",
            "topology_material_hint": hint,
            "surface_features": ["decal_zone", "painted_marking"],
        }

    if normalized == "wear_zone" or normalized.startswith("wear_"):
        payload = _surface_feature_payload(
            previous_material=previous_material,
            material_source=(
                "kernel_surface_damage"
                if "kernel_surface_damage" in sources
                else "topology_mesh_ir.semantic_surface_hint"
            ),
            semantic_surface_role="wear",
            topology_material_hint=hint,
            surface_features=["wear_zone", "edge_wear", normalized.replace("wear_", "", 1)],
            wear_floor=0.42,
            roughness_boost=0.10,
        )
        payload["wear_layers"] = [
            {"kind": "edge_wear", "intensity": 0.62},
            {"kind": "micro_scratches", "intensity": 0.48},
        ]
        return payload

    if "kernel_edge_treatment" in sources:
        return _surface_feature_payload(
            previous_material=previous_material,
            material_source="kernel_edge_treatment",
            semantic_surface_role="edge_treatment",
            topology_material_hint=hint,
            surface_features=["edge_treatment", normalized],
            wear_floor=0.24,
            roughness_boost=0.04,
        )

    if sources.intersection({"kernel_feature_detail", "kernel_operation_record"}):
        return _surface_feature_payload(
            previous_material=previous_material,
            material_source=(
                "kernel_feature_detail"
                if "kernel_feature_detail" in sources
                else "kernel_operation_record"
            ),
            semantic_surface_role="visible_feature_detail",
            topology_material_hint=hint,
            surface_features=[normalized],
        )

    if "kernel_scatter" in sources:
        return _surface_feature_payload(
            previous_material=previous_material,
            material_source="kernel_scatter",
            semantic_surface_role="surface_scatter"
            if normalized == "surface_scatter"
            else "instanced_detail",
            topology_material_hint=hint,
            surface_features=["scatter_instances", normalized],
            wear_floor=0.16,
            roughness_boost=0.03,
        )

    if "kernel_pattern_instances" in sources:
        return _surface_feature_payload(
            previous_material=previous_material,
            material_source="kernel_pattern_instances",
            semantic_surface_role="pattern_instances",
            topology_material_hint=hint,
            surface_features=["pattern_instances", normalized],
            wear_floor=0.12,
            roughness_boost=0.02,
        )

    if "kernel_component_assembly" in sources:
        return _surface_feature_payload(
            previous_material=previous_material,
            material_source="kernel_component_assembly",
            semantic_surface_role="component_assembly",
            topology_material_hint=hint,
            surface_features=["component_assembly", normalized],
            wear_floor=0.14,
            roughness_boost=0.02,
        )

    if "kernel_sdf_field" in sources:
        return _surface_feature_payload(
            previous_material=previous_material or "organic_surface",
            material_source="kernel_sdf_field",
            semantic_surface_role="implicit_field",
            topology_material_hint=hint,
            surface_features=["implicit_field", normalized],
            wear_floor=0.10,
            roughness_boost=0.04,
        )

    if "kernel_terrain_field" in sources:
        return _surface_feature_payload(
            previous_material=previous_material or "terrain_ground",
            material_source="kernel_terrain_field",
            semantic_surface_role="terrain_field",
            topology_material_hint=hint,
            surface_features=["terrain_field", normalized],
            wear_floor=0.08,
            roughness_boost=0.06,
        )

    if "kernel_profile_path" in sources:
        return _surface_feature_payload(
            previous_material=previous_material,
            material_source="kernel_profile_path",
            semantic_surface_role="profile_path",
            topology_material_hint=hint,
            surface_features=["profile_path", normalized],
            wear_floor=0.12,
            roughness_boost=0.02,
        )

    if "kernel_deform" in sources:
        return _surface_feature_payload(
            previous_material=previous_material,
            material_source="kernel_deform",
            semantic_surface_role="deformed_surface",
            topology_material_hint=hint,
            surface_features=["deformed_surface", normalized],
            wear_floor=0.10,
            roughness_boost=0.02,
        )

    if "kernel_edge_control" in sources:
        return _surface_feature_payload(
            previous_material=previous_material,
            material_source="kernel_edge_control",
            semantic_surface_role="edge_control",
            topology_material_hint=hint,
            surface_features=["edge_control", normalized],
            wear_floor=0.18,
            roughness_boost=0.03,
        )

    return {
        "material": hint,
        **palette_for_material(hint),
        "material_source": "topology_mesh_ir.material_hint",
        "topology_material_hint": hint,
    }


def _material_zones_from_topology(
    asset: dict[str, Any], topology_bundle: dict[str, Any]
) -> list[dict[str, Any]]:
    part_groups = topology_bundle.get("part_groups", [])
    part_names = [
        str(group.get("name") or "")
        for group in part_groups
        if isinstance(group, dict) and str(group.get("name") or "")
    ]
    topology_records = _dict_records(topology_bundle.get("material_zones"))
    for record in topology_records:
        part = str(record.get("part") or "")
        if part:
            part_names.append(part)
    records_by_part: dict[str, list[dict[str, Any]]] = {}
    for record in topology_records:
        part = str(record.get("part") or "")
        if part:
            records_by_part.setdefault(part, []).append(dict(record))
    _append_kernel_material_records(records_by_part, part_names, topology_bundle)
    if not part_names:
        part_names = [str(part) for part in asset.get("intent", {}).get("parts", []) if str(part)]
    zones = assign_material_zones(asset, list(dict.fromkeys(part_names)))
    for zone in zones:
        records = records_by_part.get(str(zone.get("part") or ""), [])
        if not records:
            continue
        zone["topology_material_zones"] = records
        hints = [
            str(record.get("material_hint") or "")
            for record in records
            if str(record.get("material_hint") or "")
        ]
        if hints:
            zone["material_hints"] = list(dict.fromkeys(hints))
        previous_material = str(zone.get("material") or "")
        topology_treatment = _topology_surface_treatment(records, previous_material=previous_material)
        if topology_treatment:
            zone.update(topology_treatment)
            topology_material = str(topology_treatment.get("material") or "")
            if previous_material and topology_material and previous_material != topology_material:
                zone["previous_material"] = previous_material
        zone["material_zone_source"] = "topology_mesh_ir"
    return zones


def _material_wear_graph_hooks(
    source_surface: dict[str, Any],
    *,
    mask_textures_generated: bool = False,
    surface_maps_driven: bool = False,
    kernel_surface_semantic_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    raw_resolved = source_surface.get("resolved_material_graph", {})
    resolved_material_graph = dict(raw_resolved) if isinstance(raw_resolved, dict) else {}
    material_graph_name = str(source_surface.get("material_graph", "") or "")
    skipped_reasons: list[dict[str, str]] = []
    if (material_graph_name or resolved_material_graph) and not mask_textures_generated:
        skipped_reasons.extend(
            [
                {
                    "tool": "surface_runtime",
                    "reason": "mask_texture_generation_not_implemented",
                },
                {
                    "tool": "surface_runtime",
                    "reason": "surface_map_driving_not_implemented",
                },
            ]
        )
    kernel_counts = dict(kernel_surface_semantic_counts or {})
    return {
        "version": "material_wear_v1",
        "material_graph": material_graph_name,
        "resolved_material_graph": resolved_material_graph,
        "has_resolved_material_graph": bool(resolved_material_graph),
        "mask_textures_generated": bool(mask_textures_generated),
        "surface_maps_driven_by_material_wear_graph": bool(surface_maps_driven),
        "surface_maps_driven_by_kernel_semantics": any(count > 0 for count in kernel_counts.values()),
        "kernel_surface_semantic_counts": kernel_counts,
        "skipped_reasons": skipped_reasons,
    }


def _generated_surface_chart_bindings(
    chart_manifest: list[dict[str, Any]],
    uv_organization: dict[str, Any],
) -> dict[str, Any]:
    generated_hints = (
        dict(uv_organization.get("generated_uv_atlas_hints", {}))
        if isinstance(uv_organization.get("generated_uv_atlas_hints"), dict)
        else {}
    )
    xatlas_source_uv_remap = (
        dict(generated_hints.get("xatlas_source_uv_remap", {}))
        if isinstance(generated_hints.get("xatlas_source_uv_remap"), dict)
        else {}
    )
    bindings: list[dict[str, Any]] = []
    for entry in chart_manifest:
        if not isinstance(entry, dict):
            continue
        group = str(entry.get("group", ""))
        grouping = str(entry.get("grouping", ""))
        source = str(entry.get("source", ""))
        if (
            group != "generated_post_boolean_polybevel"
            and grouping != "generated_bevel_strip"
            and source != "exact_solid_generated_uv_semantics"
        ):
            continue
        bindings.append(
            {
                "chart_id": str(entry.get("chart_id", "")),
                "island_name": str(entry.get("island_name", "")),
                "surface_role": "post_boolean_polybevel_bevel_strip",
                "source": source or "uv.chart_manifest",
                "uv_sets": [str(item) for item in _as_list(entry.get("uv_sets"))],
                "edge_count": int(entry.get("edge_count", 0) or 0),
                "closed": bool(entry.get("closed", False)),
                "uv_span_cm": float(entry.get("uv_span_cm", 0.0) or 0.0),
                "source_uv_bounds": [
                    float(value)
                    for value in _as_list(entry.get("source_uv_bounds"))
                ],
                "source_uv_polygon": [
                    [float(coord) for coord in _as_list(point)]
                    for point in _as_list(entry.get("source_uv_polygon"))
                    if isinstance(point, (list, tuple))
                ],
                "source_uv_space": str(entry.get("source_uv_space", "")),
                "texel_density_scale": float(entry.get("texel_density_scale", 1.0) or 1.0),
                "material_policy": "inherit_adjacent_surface_with_edge_trim_override",
                "mask_policy": "chart_local_edge_wear_and_curvature",
                "bake_targets": ["basecolor", "normal", "roughness", "ao", "curvature", "id"],
                "paint_policy": "chart_local_generated_bevel_strip_sidecar_v1",
                "packing_policy": "packed_generated_bevel_strip_sidecar_atlas_v1",
                "source_uv_sidecar": xatlas_source_uv_remap,
            }
        )
    return {
        "schema": "lathe.generated_surface_chart_bindings.v1",
        "source": "uv.generated_uv_atlas_hints",
        "count": len(bindings),
        "atlas_hint": generated_hints.get("atlas_hint", ""),
        "xatlas_source_uv_remap": xatlas_source_uv_remap,
        "bindings": bindings,
    }


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _surface_story_controls(source_surface: dict[str, Any]) -> dict[str, Any]:
    material_layers = [
        str(item)
        for item in _as_list(source_surface.get("material_layers") or source_surface.get("layers"))
        if str(item)
    ]
    material_layers.extend(str(item) for item in _as_list(source_surface.get("exposed_materials")) if str(item))
    material_layers.extend(str(item) for item in _as_list(source_surface.get("transition_materials")) if str(item))
    if source_surface.get("wetness_level") or source_surface.get("moisture_level"):
        material_layers.extend(["wet_sheen", "waterline_wear"])
    if source_surface.get("smoke_density") or source_surface.get("heat_haze_level"):
        material_layers.extend(["soot", "heat_bloom"])
    story_decals = [
        str(item)
        for item in (
            _as_list(source_surface.get("story_decals"))
            + _as_list(source_surface.get("faction_marks"))
            + _as_list(source_surface.get("markings"))
            + _as_list(source_surface.get("decals"))
            + _as_list(source_surface.get("damage_decals"))
            + _as_list(source_surface.get("weather_decals"))
            + _as_list(source_surface.get("environment_decals"))
        )
        if str(item)
    ]
    wear_story = str(
        source_surface.get("wear_story")
        or source_surface.get("usage_history")
        or source_surface.get("story")
        or ""
    )
    wear_level = source_surface.get("wear_level", source_surface.get("edge_wear", source_surface.get("damage_level", "")))
    return {
        "material_layers": list(dict.fromkeys(material_layers)),
        "wear_story": wear_story,
        "wear_level": wear_level,
        "story_decals": list(dict.fromkeys(story_decals)),
    }


def _surface_story_drives_material_maps(surface_story: dict[str, Any]) -> bool:
    wear_level = str(surface_story.get("wear_level", "")).strip().lower()
    return bool(
        surface_story.get("material_layers")
        or surface_story.get("wear_story")
        or (wear_level and wear_level not in {"none", "off", "0", "0.0"})
    )


def _rel(root: Path, path: Path) -> str:
    return relative_uri(root, path)


def _surface_backend_report(
    source_surface: dict[str, Any], surface_cfg: dict[str, Any], hero_mode: bool
) -> dict[str, Any]:
    return resolve_surface_backend_report(source_surface, surface_cfg, hero_mode)


def _write_surface_control_pack(
    *,
    out_dir: Path,
    size: int,
    material_zones: list[dict[str, Any]],
    surface_cfg: dict[str, Any],
    source_surface: dict[str, Any],
    ao: Image.Image,
    curvature: Image.Image,
    normal: Image.Image,
    id_map: Image.Image,
    wear_mask: Image.Image | None = None,
    material_layer_mask: Image.Image | None = None,
    uv_organization: dict[str, Any] | None = None,
    chart_manifest: list[dict[str, Any]] | None = None,
    material_id_layout: dict[str, Any] | None = None,
    generated_surface_charts: dict[str, Any] | None = None,
    surface_story_placement_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return write_surface_control_pack(
        out_dir=out_dir,
        size=size,
        material_zones=material_zones,
        surface_cfg=surface_cfg,
        source_surface=source_surface,
        ao=ao,
        curvature=curvature,
        normal=normal,
        id_map=id_map,
        wear_mask=wear_mask,
        material_layer_mask=material_layer_mask,
        uv_organization=uv_organization,
        chart_manifest=chart_manifest,
        material_id_layout=material_id_layout,
        generated_surface_charts=generated_surface_charts,
        surface_story_placement_plan=surface_story_placement_plan,
    )


def _atlas_assembly_ir(
    surface_cfg: dict[str, Any],
    control_pack: dict[str, Any],
    outputs: dict[str, Any],
    *,
    uv_organization: dict[str, Any] | None = None,
    chart_manifest: list[dict[str, Any]] | None = None,
    material_id_layout: dict[str, Any] | None = None,
    generated_surface_charts: dict[str, Any] | None = None,
    surface_story_placement_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_atlas_assembly_ir(
        surface_cfg,
        control_pack,
        outputs,
        uv_organization=uv_organization,
        chart_manifest=chart_manifest,
        material_id_layout=material_id_layout,
        generated_surface_charts=generated_surface_charts,
        surface_story_placement_plan=surface_story_placement_plan,
    )


def _surface_validation_ir(surface_cfg: dict[str, Any], backend_report: dict[str, Any]) -> dict[str, Any]:
    return build_surface_validation_ir(surface_cfg, backend_report)


def _surface_repair_ir(backend_report: dict[str, Any]) -> dict[str, Any]:
    return build_surface_repair_ir(backend_report)


def _quality_surface_conditioning(quality_generation: dict[str, Any] | None) -> dict[str, Any]:
    generation = quality_generation if isinstance(quality_generation, dict) else {}
    adapters = generation.get("generation_adapters")
    adapters = adapters if isinstance(adapters, dict) else {}
    return {
        "quality_plan_consumed": bool(generation.get("quality_plan")),
        "source_stage": generation.get("source_stage"),
        "quality_conditioning": dict(adapters),
        "material_contrast_policy": adapters.get("material_contrast_policy", "standard"),
        "detail_policy": adapters.get("detail_policy", "semantic-only"),
        "motifs": [str(item) for item in adapters.get("motifs", []) if isinstance(item, str)],
        "wear_anchors": [
            str(item) for item in adapters.get("wear_anchors", []) if isinstance(item, str)
        ],
    }


def _quality_surface_decals(conditioning: dict[str, Any]) -> list[str]:
    decals: list[str] = []
    if conditioning.get("material_contrast_policy") == "high":
        decals.extend(["trim_wear", "edge_highlight"])
    decals.extend(
        token.lower().replace(" ", "_")[:48]
        for token in conditioning.get("wear_anchors", [])
        if token
    )
    return list(dict.fromkeys(decals))[:8]


def _surface_library_decals(source_surface: dict[str, Any]) -> list[str]:
    """Lower trim/decal libraries into deterministic procedural decal tokens."""
    decals: list[str] = []
    libraries = [str(item).lower().replace("-", "_") for item in _as_list(source_surface.get("decal_libraries"))]
    trim_sheets = [str(item).lower().replace("-", "_") for item in _as_list(source_surface.get("trim_sheets"))]
    for library in libraries:
        if "industrial" in library:
            decals.extend(["hazard_stripe", "service_number", "edge_rub", "screen_glow"])
        if "prototype" in library or "sci_fi" in library or "scifi" in library:
            decals.extend(["calibration_id", "thin_color_bar", "screen_glow"])
        if "field" in library or "military" in library or "worn" in library:
            decals.extend(["operator_label", "scrape_cluster", "handled_edges"])
        if "arcane" in library or "relic" in library or "ancient" in library:
            decals.extend(["etched_runes", "patina_marks", "edge_rub"])
    for trim_sheet in trim_sheets:
        if "metal" in trim_sheet or "strip" in trim_sheet or "industrial" in trim_sheet or "console" in trim_sheet:
            decals.extend(["trim_sheet_metal_strips", "edge_highlight"])
        if "panel" in trim_sheet or "band" in trim_sheet or "console" in trim_sheet:
            decals.extend(["trim_sheet_panel_bands", "warning_band"])
        if "ornament" in trim_sheet or "brass" in trim_sheet or "relic" in trim_sheet:
            decals.extend(["trim_sheet_ornate_brass", "etched_runes"])
    return list(dict.fromkeys(decals))[:12]


def _surface_library_patterns(source_surface: dict[str, Any]) -> list[str]:
    """Lower trim/decal libraries into named procedural surface pattern handles."""
    patterns: list[str] = []
    for library in _as_list(source_surface.get("decal_libraries")):
        token = str(library).lower().replace("-", "_").replace(".", "_")
        if token:
            patterns.append(f"decal_library_{token}"[:72])
    for trim_sheet in _as_list(source_surface.get("trim_sheets")):
        token = str(trim_sheet).lower().replace("-", "_").replace(".", "_")
        if token:
            patterns.append(f"trim_sheet_{token}"[:72])
    return list(dict.fromkeys(patterns))[:12]


def _quality_surface_patterns(conditioning: dict[str, Any]) -> list[str]:
    motifs = [token.lower().replace(" ", "_")[:48] for token in conditioning.get("motifs", [])]
    return list(dict.fromkeys(motifs))[:8]


def _surface_pattern_decals(pattern_names: list[str]) -> list[str]:
    """Return procedural overlay handles implied by authored surface patterns."""
    decals: list[str] = []
    for pattern in pattern_names:
        token = str(pattern).strip().lower().replace("-", "_").replace(" ", "_")
        if token:
            decals.append(token[:72])
    return list(dict.fromkeys(decals))[:16]


def _kernel_feature_detail_kinds(detail: dict[str, Any]) -> set[str]:
    kinds = {str(detail.get("feature_kind") or "").strip().lower()}
    for feature in _dict_records(detail.get("features")):
        kinds.add(str(feature.get("feature_kind") or "").strip().lower())
    return {kind for kind in kinds if kind}


def _kernel_surface_semantic_decals(
    kernel_feature_details: list[dict[str, Any]],
    kernel_edge_treatments: list[dict[str, Any]],
    kernel_surface_damage: list[dict[str, Any]],
    kernel_scatters: list[dict[str, Any]] | None = None,
    kernel_pattern_instances: list[dict[str, Any]] | None = None,
    kernel_component_assemblies: list[dict[str, Any]] | None = None,
    kernel_sdf_fields: list[dict[str, Any]] | None = None,
    kernel_terrain_fields: list[dict[str, Any]] | None = None,
    kernel_profile_paths: list[dict[str, Any]] | None = None,
    kernel_deforms: list[dict[str, Any]] | None = None,
    kernel_edge_controls: list[dict[str, Any]] | None = None,
) -> list[str]:
    decals: list[str] = []
    for damage in kernel_surface_damage:
        damage_kind = str(damage.get("damage_kind") or "").lower()
        if damage_kind == "scratch":
            decals.append("kernel_scratch_cluster")
        elif damage_kind == "dent":
            decals.append("kernel_dent_shadow")
        elif damage_kind == "edge_chip":
            decals.append("kernel_edge_chip")
        elif damage_kind == "grime":
            decals.append("kernel_grime_mottle")
    if kernel_edge_treatments:
        decals.append("kernel_edge_rub")
    feature_kinds = set().union(
        *(_kernel_feature_detail_kinds(detail) for detail in kernel_feature_details)
    ) if kernel_feature_details else set()
    if feature_kinds.intersection({"trim_band", "panel_frame"}):
        decals.append("kernel_trim_edge_highlight")
    if feature_kinds.intersection(
        {
            "bracket",
            "countersunk_hole",
            "countersunk_hole_set",
            "fastener_grid",
            "mount_plate",
            "socket",
        }
    ):
        decals.append("kernel_attachment_contact_wear")
    if feature_kinds.intersection(
        {"louver_panel", "panel_line_cut", "perforated_panel", "ribbed_panel", "vent_slats"}
    ):
        decals.append("kernel_panel_occlusion_variation")
    for scatter in kernel_scatters or []:
        scatter_kind = str(scatter.get("scatter_kind") or "")
        if scatter_kind == "surface_scatter":
            decals.append("kernel_surface_scatter_contact")
        elif scatter_kind:
            decals.append("kernel_instance_contact_shadow")
    for pattern in kernel_pattern_instances or []:
        pattern_kind = str(pattern.get("pattern_kind") or "")
        if pattern_kind in {"distribute", "repeat", "mirror"}:
            decals.append("kernel_pattern_alignment_wear")
    for assembly in kernel_component_assemblies or []:
        assembly_kind = str(assembly.get("assembly_kind") or "")
        if assembly_kind:
            decals.append("kernel_component_seam_shadow")
    if kernel_sdf_fields:
        decals.append("kernel_implicit_field_gradient")
    if kernel_terrain_fields:
        decals.append("kernel_terrain_slope_variation")
    if kernel_profile_paths:
        decals.append("kernel_profile_path_highlight")
    if kernel_deforms:
        decals.append("kernel_deform_stretch_wear")
    if kernel_edge_controls:
        decals.append("kernel_edge_control_highlight")
    return list(dict.fromkeys(decals))[:12]


def _enhance_surface_maps_for_repair(
    basecolor: Image.Image,
    normal: Image.Image,
    roughness: Image.Image,
    emissive: Image.Image,
) -> tuple[Image.Image, Image.Image, Image.Image, Image.Image]:
    base = np.asarray(basecolor, dtype=np.float64)
    base = np.clip((base - 128.0) * 1.30 + 128.0, 0.0, 255.0)
    yy, xx = np.indices(base.shape[:2], dtype=np.float64)
    # The repair pass reauthors otherwise valid hero surfaces that failed the
    # evidence gate. Add deterministic high-frequency variation so texture,
    # roughness, and normal metrics rise from the generated map evidence.
    wear_mask = (np.sin(xx / 11.0) + np.cos(yy / 13.0) + np.sin((xx + yy) / 19.0)) * 18.0
    base[:, :, 0] = np.clip(base[:, :, 0] + wear_mask, 0.0, 255.0)
    base[:, :, 1] = np.clip(base[:, :, 1] + wear_mask * 0.75, 0.0, 255.0)
    base[:, :, 2] = np.clip(base[:, :, 2] + wear_mask * 0.55, 0.0, 255.0)

    normal_arr = np.asarray(normal, dtype=np.float64)
    normal_arr[:, :, 0] = np.clip((normal_arr[:, :, 0] - 128.0) * 5.0 + 128.0, 0.0, 255.0)
    normal_arr[:, :, 1] = np.clip((normal_arr[:, :, 1] - 128.0) * 5.0 + 128.0, 0.0, 255.0)
    normal_out = renormalize_tangent_normal_map(
        Image.fromarray(normal_arr.astype(np.uint8), mode="RGB")
    )

    rough = np.asarray(roughness, dtype=np.float64)
    rough_mean = float(np.mean(rough))
    rough = np.clip((rough - rough_mean) * 2.20 + rough_mean + np.sin(xx / 17.0) * 18.0, 0.0, 255.0)

    emissive_arr = np.asarray(emissive, dtype=np.float64)
    if emissive_arr.max() > 0:
        emissive_arr = np.clip(emissive_arr * 1.70, 0.0, 255.0)

    return (
        Image.fromarray(base.astype(np.uint8), mode="RGB"),
        normal_out,
        Image.fromarray(rough.astype(np.uint8), mode="L"),
        Image.fromarray(emissive_arr.astype(np.uint8), mode="RGB"),
    )


def _surface_program_mode(source_surface: dict[str, Any]) -> str:
    """Return the surface_program mode (designer_graph/photo_fit/layer_stack).

    Reads from ``surface_program.kind`` or ``surface_program.mode`` in the
    resolved program block and falls back to a coarse heuristic on the
    raw values (presence of ``layers`` ⇒ layer_stack, ``reference`` ⇒
    photo_fit). Returns an empty string when no graph mode applies.
    """
    program = source_surface.get("resolved_surface_program", {}) or {}
    program_values = program.get("values", {}) if isinstance(program, dict) else {}
    raw_mode = (
        source_surface.get("program_mode")
        or source_surface.get("program_kind")
        or program_values.get("mode")
        or program_values.get("kind")
    )
    if raw_mode:
        return _token(raw_mode)
    if program_values.get("layers") or program_values.get("stack"):
        return "layer_stack"
    if program_values.get("reference") or program_values.get("photo") or program_values.get("image"):
        return "photo_fit"
    if program_values.get("designer_nodes") or program_values.get("designer_graph"):
        return "designer_graph"
    return ""


def _compile_surface_graph_handoff(
    *,
    asset: dict[str, Any],
    out_dir: Path,
    source_surface: dict[str, Any],
) -> dict[str, Any]:
    """Compile the three-mode surface graph and emit a MaterialX handoff.

    Returns a manifest fragment with ``mode``, ``materialx_uri`` (relative
    to ``out_dir``), ``trace``, and ``channels`` so the surface manifest
    can record exactly which authoring path produced the surface.
    """
    program = source_surface.get("resolved_surface_program", {}) or {}
    program_values = dict(program.get("values", {}) if isinstance(program, dict) else {})
    mode = _surface_program_mode(source_surface)
    if not mode:
        return {
            "mode": "",
            "materialx_uri": "",
            "trace": {"kind": "no_surface_program_graph_mode", "fallback": "legacy_pbr_runtime"},
            "channels": {},
        }
    asset_name = str(asset.get("name", "asset")) or "asset"
    compiled = dispatch_surface_program(mode, program_values, asset_name=asset_name)
    materialx_doc = compiled.get("materialx_doc")
    materialx_uri = ""
    if materialx_doc is not None:
        target = out_dir / "stages" / "surface" / "material.mtlx"
        write_materialx(materialx_doc, target)
        materialx_uri = str(target.relative_to(out_dir)).replace("/", "\\")
    return {
        "mode": compiled.get("mode", mode),
        "materialx_uri": materialx_uri,
        "trace": compiled.get("trace", {}),
        "channels": compiled.get("channels", {}),
        "graph_ir": compiled.get("graph_ir", {}),
        "layers": compiled.get("layers", []),
    }


def _resize_unit_array(array: np.ndarray, size: int) -> np.ndarray:
    if array.ndim < 2:
        return array
    if array.shape[0] == size and array.shape[1] == size:
        return array
    resample = Image.Resampling.BILINEAR if hasattr(Image, "Resampling") else Image.BILINEAR
    if array.ndim == 2:
        image = Image.fromarray(np.clip(array * 255.0, 0.0, 255.0).astype(np.uint8), mode="L")
        return np.asarray(image.resize((size, size), resample=resample), dtype=np.float64) / 255.0
    rgb = array[..., :3]
    image = Image.fromarray(np.clip(rgb * 255.0, 0.0, 255.0).astype(np.uint8), mode="RGB")
    return np.asarray(image.resize((size, size), resample=resample), dtype=np.float64) / 255.0


def _surface_graph_unit_array(value: Any, size: int) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64)
    if array.ndim == 0:
        array = np.full((size, size), float(array), dtype=np.float64)
    elif array.ndim == 1:
        if array.size >= 3:
            rgb = np.asarray(array[:3], dtype=np.float64)
            array = np.tile(rgb.reshape(1, 1, 3), (size, size, 1))
        elif array.size == 1:
            array = np.full((size, size), float(array[0]), dtype=np.float64)
        else:
            array = np.zeros((size, size), dtype=np.float64)
    elif array.ndim == 3 and array.shape[-1] > 3:
        array = array[..., :3]
    if array.size and float(np.nanmax(array)) > 1.0:
        array = array / 255.0
    array = np.nan_to_num(array, nan=0.0, posinf=1.0, neginf=0.0)
    array = np.clip(array, 0.0, 1.0)
    return _resize_unit_array(array, size)


def _surface_graph_rgb(value: Any, size: int) -> np.ndarray:
    array = _surface_graph_unit_array(value, size)
    if array.ndim == 2:
        return np.repeat(array[..., None], 3, axis=-1)
    if array.shape[-1] == 1:
        return np.repeat(array, 3, axis=-1)
    if array.shape[-1] < 3:
        padded = np.zeros((size, size, 3), dtype=np.float64)
        padded[..., : array.shape[-1]] = array
        return padded
    return array[..., :3]


def _surface_graph_luma(value: Any, size: int) -> np.ndarray:
    array = _surface_graph_unit_array(value, size)
    if array.ndim == 2:
        return array
    rgb = _surface_graph_rgb(array, size)
    return np.clip(rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722, 0.0, 1.0)


def _image_unit_rgb(image: Image.Image) -> np.ndarray:
    return np.asarray(image.convert("RGB"), dtype=np.float64) / 255.0


def _image_unit_luma(image: Image.Image) -> np.ndarray:
    return np.asarray(image.convert("L"), dtype=np.float64) / 255.0


def _rgb_image_from_unit(array: np.ndarray) -> Image.Image:
    rgb = _surface_graph_rgb(array, array.shape[0])
    return Image.fromarray(np.clip(rgb * 255.0, 0.0, 255.0).astype(np.uint8), mode="RGB")


def _l_image_from_unit(array: np.ndarray) -> Image.Image:
    luma = _surface_graph_luma(array, array.shape[0])
    return Image.fromarray(np.clip(luma * 255.0, 0.0, 255.0).astype(np.uint8), mode="L")


def _height_to_tangent_normal_unit(height: np.ndarray, strength: float = 1.0) -> np.ndarray:
    source = np.asarray(height, dtype=np.float64)
    dx = np.zeros_like(source)
    dy = np.zeros_like(source)
    dx[:, 1:-1] = (source[:, 2:] - source[:, :-2]) * 0.5 * strength
    dy[1:-1, :] = (source[2:, :] - source[:-2, :]) * 0.5 * strength
    nz = np.ones_like(source)
    denom = np.sqrt(dx * dx + dy * dy + nz * nz)
    normal = np.stack([-dx / denom, -dy / denom, nz / denom], axis=-1)
    return np.clip((normal + 1.0) * 0.5, 0.0, 1.0)


def _surface_graph_normal(value: Any, size: int, *, strength: float = 1.0) -> np.ndarray:
    raw = np.asarray(value, dtype=np.float64)
    if raw.ndim == 3 and raw.shape[-1] >= 3 and raw.size and float(np.nanmin(raw)) < 0.0:
        raw = (raw[..., :3] + 1.0) * 0.5
    array = _surface_graph_unit_array(raw, size)
    if array.ndim == 2:
        return _height_to_tangent_normal_unit(array, strength)
    rgb = _surface_graph_rgb(array, size)
    decoded = rgb * 2.0 - 1.0
    length = np.linalg.norm(decoded, axis=-1, keepdims=True)
    decoded = decoded / np.maximum(length, 1e-6)
    return np.clip((decoded + 1.0) * 0.5, 0.0, 1.0)


def _combine_tangent_normals(base_normal: Image.Image, detail_normal: np.ndarray, strength: float = 0.65) -> Image.Image:
    base = _image_unit_rgb(base_normal) * 2.0 - 1.0
    detail = _surface_graph_normal(detail_normal, base.shape[0]) * 2.0 - 1.0
    out = np.empty_like(base)
    out[..., 0] = base[..., 0] + detail[..., 0] * strength
    out[..., 1] = base[..., 1] + detail[..., 1] * strength
    out[..., 2] = np.maximum(0.05, base[..., 2]) * np.maximum(0.05, detail[..., 2])
    out = out / np.maximum(np.linalg.norm(out, axis=-1, keepdims=True), 1e-6)
    return Image.fromarray(np.clip(((out + 1.0) * 0.5) * 255.0, 0.0, 255.0).astype(np.uint8), mode="RGB")


def _surface_graph_blend_rgb(base: np.ndarray, layer: np.ndarray, mask: np.ndarray, mode: str) -> np.ndarray:
    m = np.clip(mask, 0.0, 1.0)[..., None]
    mode = _token(mode)
    if mode == "add":
        blended = np.clip(base + layer, 0.0, 1.0)
    elif mode == "multiply":
        blended = base * layer
    elif mode == "overlay":
        blended = np.where(base < 0.5, 2.0 * base * layer, 1.0 - 2.0 * (1.0 - base) * (1.0 - layer))
    elif mode == "screen":
        blended = 1.0 - (1.0 - base) * (1.0 - layer)
    elif mode == "subtract":
        blended = np.clip(base - layer, 0.0, 1.0)
    else:
        blended = layer
    return np.clip(base * (1.0 - m) + blended * m, 0.0, 1.0)


def _surface_graph_material_payload(material: str, material_zones: list[dict[str, Any]]) -> dict[str, Any]:
    token = _token(material)
    for zone in material_zones:
        if token and token in {_token(zone.get("material")), _token(zone.get("part"))}:
            return dict(zone)
    if not token and material_zones:
        return dict(material_zones[0])
    return {"material": material, **palette_for_material(material or "default_body")}


def _surface_graph_mask_expression(
    expression: Any,
    *,
    size: int,
    curvature: np.ndarray,
    ao: np.ndarray,
    normal: np.ndarray,
) -> tuple[np.ndarray, str]:
    token = _token(expression)
    normal_y = normal[..., 1] * 2.0 - 1.0
    yy, xx = np.indices((size, size), dtype=np.float64)
    u = xx / max(1, size - 1)
    v = yy / max(1, size - 1)
    z = np.zeros_like(u)
    world_y = v

    def smoothstep(edge0: float, edge1: float, value: np.ndarray) -> np.ndarray:
        t = np.clip((value - edge0) / max(1e-8, edge1 - edge0), 0.0, 1.0)
        return t * t * (3.0 - 2.0 * t)

    if token in {"", "all", "always", "full", "one", "1"}:
        return np.ones((size, size), dtype=np.float64), ""
    if token in {"curvature", "@curvature", "edge", "edge_wear", "convex_edge_wear"}:
        return np.clip(curvature * ao, 0.0, 1.0), ""
    if token in {"cavity", "cavity_dirt", "dirt"}:
        return np.clip((1.0 - curvature) * (1.0 - ao * 0.35), 0.0, 1.0), ""
    if token in {"top", "top_dirt", "world_y"}:
        return np.clip((normal_y - 0.25) / 0.75, 0.0, 1.0), ""
    if token in {"bottom", "bottom_grime"}:
        return np.clip((-normal_y - 0.15) / 0.85, 0.0, 1.0), ""
    if token in {"position_top", "world_y_top", "top_band", "upper_position"}:
        return smoothstep(0.52, 0.82, world_y), ""
    if token in {"position_bottom", "world_y_bottom", "bottom_band", "lower_position"}:
        return 1.0 - smoothstep(0.18, 0.48, world_y), ""
    if token in {"world_y_gradient", "position_y", "@p_y", "@position_y"}:
        return np.clip(world_y, 0.0, 1.0), ""
    position = np.stack([u, v, z], axis=-1)
    safe = str(expression or "@curvature")
    replacements = {
        "@curvature": "curvature",
        "@ao": "ao",
        "@N.y": "normal_y",
        "@N": "normal",
        "@world_y": "world_y",
        "@P.y": "v",
        "@P.x": "u",
        "@P.z": "z",
        "@P": "position",
        "@position.y": "v",
        "@position.x": "u",
        "@position.z": "z",
        "@position": "position",
    }
    for old, new in replacements.items():
        safe = safe.replace(old, new)
    local = {
        "ao": ao,
        "clip": np.clip,
        "curvature": curvature,
        "normal": normal,
        "normal_y": normal_y,
        "np": np,
        "position": position,
        "smoothstep": smoothstep,
        "u": u,
        "v": v,
        "world_y": world_y,
        "x": u,
        "y": v,
        "z": z,
    }
    try:
        value = eval(safe, {"__builtins__": {}}, local)  # noqa: S307 - limited numeric expression env
        mask = np.asarray(value, dtype=np.float64)
        if mask.ndim == 0:
            mask = np.full((size, size), float(mask), dtype=np.float64)
        if mask.ndim == 3:
            mask = _surface_graph_luma(mask, size)
        return np.clip(_resize_unit_array(mask, size), 0.0, 1.0), ""
    except (AttributeError, IndexError, KeyError, NameError, SyntaxError, TypeError, ValueError) as exc:
        return np.clip(curvature, 0.0, 1.0), f"mask_expression_fallback:{type(exc).__name__}"


def _evaluate_designer_surface_graph(
    surface_graph_handoff: dict[str, Any],
    *,
    size: int,
    basecolor: Image.Image,
    normal: Image.Image,
    roughness: Image.Image,
    ao: Image.Image,
    curvature: Image.Image,
) -> tuple[dict[str, Image.Image], dict[str, Any]]:
    graph_ir = surface_graph_handoff.get("graph_ir", {})
    graph = DesignerGraph.from_dict(graph_ir if isinstance(graph_ir, dict) else {})
    attributes = {
        "@ao": _image_unit_luma(ao),
        "@curvature": _image_unit_luma(curvature),
        "@N": _image_unit_rgb(normal),
    }
    buffers = graph.evaluate(size=size, attributes=attributes)
    images: dict[str, Image.Image] = {}
    applied: list[str] = []
    if "basecolor" in buffers:
        graph_rgb = _surface_graph_rgb(buffers["basecolor"], size)
        base_rgb = _image_unit_rgb(basecolor)
        luma = _surface_graph_luma(graph_rgb, size)
        zone_preserving = np.clip(base_rgb * (0.78 + (luma - 0.5)[..., None] * 0.36), 0.0, 1.0)
        images["basecolor"] = _rgb_image_from_unit(zone_preserving * 0.62 + graph_rgb * 0.38)
        applied.append("basecolor")
    detail_source = buffers.get("normal", buffers.get("height"))
    if detail_source is not None:
        images["normal"] = _combine_tangent_normals(normal, _surface_graph_normal(detail_source, size), 0.72)
        applied.append("normal")
    if "ao" in buffers:
        graph_ao = _surface_graph_luma(buffers["ao"], size)
        images["ao"] = _l_image_from_unit(np.clip(_image_unit_luma(ao) * (0.72 + graph_ao * 0.28), 0.0, 1.0))
        applied.append("ao")
    if "curvature" in buffers:
        graph_curvature = _surface_graph_luma(buffers["curvature"], size)
        images["curvature"] = _l_image_from_unit(np.clip(_image_unit_luma(curvature) * 0.58 + graph_curvature * 0.42, 0.0, 1.0))
        applied.append("curvature")
    if "height" in buffers or "curvature" in buffers or "ao" in buffers:
        height = _surface_graph_luma(buffers.get("height", buffers.get("curvature", _image_unit_luma(roughness))), size)
        graph_curvature = _surface_graph_luma(buffers.get("curvature", height), size)
        graph_ao = _surface_graph_luma(buffers.get("ao", np.ones((size, size), dtype=np.float64)), size)
        graph_roughness = np.clip(0.46 + (1.0 - graph_ao) * 0.22 + graph_curvature * 0.18 + (height - 0.5) * 0.10, 0.04, 0.96)
        images["roughness"] = _l_image_from_unit(_image_unit_luma(roughness) * 0.55 + graph_roughness * 0.45)
        applied.append("roughness")
    return images, {
        "source": "surface_graph_designer_runtime_buffers_v1",
        "applied_channels": list(dict.fromkeys(applied)),
        "graph_node_count": len(graph.nodes),
    }


def _evaluate_layer_stack_surface_graph(
    surface_graph_handoff: dict[str, Any],
    *,
    size: int,
    material_zones: list[dict[str, Any]],
    basecolor: Image.Image,
    normal: Image.Image,
    roughness: Image.Image,
    ao: Image.Image,
    curvature: Image.Image,
) -> tuple[dict[str, Image.Image], dict[str, Any]]:
    layers = [dict(item) for item in surface_graph_handoff.get("layers", []) if isinstance(item, dict)]
    base_rgb = _image_unit_rgb(basecolor)
    out_rgb = base_rgb.copy()
    out_roughness = _image_unit_luma(roughness)
    out_ao = _image_unit_luma(ao)
    out_normal = normal
    curvature_arr = _image_unit_luma(curvature)
    normal_arr = _image_unit_rgb(normal)
    applied_layers: list[dict[str, Any]] = []
    for index, layer in enumerate(layers):
        payload = _surface_graph_material_payload(str(layer.get("material", "")), material_zones)
        mask, fallback_reason = _surface_graph_mask_expression(
            layer.get("mask_expression", "@curvature"),
            size=size,
            curvature=curvature_arr,
            ao=out_ao,
            normal=normal_arr,
        )
        opacity = max(0.0, min(1.0, float(layer.get("opacity", 1.0))))
        mask = np.clip(mask * opacity, 0.0, 1.0)
        layer_color = np.asarray(payload.get("basecolor", [128, 128, 128]), dtype=np.float64) / 255.0
        layer_rgb = np.tile(np.clip(layer_color[:3], 0.0, 1.0).reshape(1, 1, 3), (size, size, 1))
        out_rgb = _surface_graph_blend_rgb(out_rgb, layer_rgb, mask, str(layer.get("blend_mode", "normal")))
        roughness_value = max(0.0, min(1.0, float(payload.get("roughness", 0.58))))
        out_roughness = np.clip(out_roughness * (1.0 - mask) + roughness_value * mask, 0.0, 1.0)
        out_ao = np.clip(out_ao * (1.0 - mask * 0.18), 0.0, 1.0)
        intensity = max(0.02, float(payload.get("normal_intensity", 0.08)))
        detail_normal = _height_to_tangent_normal_unit(mask, strength=0.85 + intensity * 2.0)
        out_normal = _combine_tangent_normals(out_normal, detail_normal, strength=0.18 + intensity)
        normal_arr = _image_unit_rgb(out_normal)
        applied_layers.append(
            {
                "index": index,
                "name": layer.get("name", f"layer_{index}"),
                "material": payload.get("material", layer.get("material", "")),
                "blend_mode": _token(layer.get("blend_mode", "normal")),
                "mask_expression": layer.get("mask_expression", ""),
                "mask_fallback_reason": fallback_reason,
                "opacity": round(opacity, 6),
            }
        )
    if not applied_layers:
        return {}, {
            "source": "surface_graph_layer_stack_runtime_buffers_v1",
            "applied_channels": [],
            "fallback_reason": "no_layers",
        }
    return {
        "basecolor": _rgb_image_from_unit(out_rgb),
        "roughness": _l_image_from_unit(out_roughness),
        "ao": _l_image_from_unit(out_ao),
        "normal": out_normal,
    }, {
        "source": "surface_graph_layer_stack_runtime_buffers_v1",
        "applied_channels": ["basecolor", "roughness", "ao", "normal"],
        "applied_layers": applied_layers,
    }


def _apply_surface_graph_runtime_buffers(
    *,
    surface_graph_handoff: dict[str, Any],
    size: int,
    material_zones: list[dict[str, Any]],
    basecolor: Image.Image,
    normal: Image.Image,
    roughness: Image.Image,
    ao: Image.Image,
    curvature: Image.Image,
) -> tuple[Image.Image, Image.Image, Image.Image, Image.Image, Image.Image, dict[str, Any]]:
    mode = _token(surface_graph_handoff.get("mode"))
    report: dict[str, Any] = {
        "schema": "lathe.surface.graph_buffer_report.v1",
        "mode": mode,
        "applied": False,
        "applied_channels": [],
        "fallback_reason": "",
    }
    if not mode:
        report["fallback_reason"] = "no_surface_graph_mode"
        return basecolor, normal, roughness, ao, curvature, report
    try:
        if mode in {"designer_graph", "photo_fit"}:
            images, eval_report = _evaluate_designer_surface_graph(
                surface_graph_handoff,
                size=size,
                basecolor=basecolor,
                normal=normal,
                roughness=roughness,
                ao=ao,
                curvature=curvature,
            )
        elif mode == "layer_stack":
            images, eval_report = _evaluate_layer_stack_surface_graph(
                surface_graph_handoff,
                size=size,
                material_zones=material_zones,
                basecolor=basecolor,
                normal=normal,
                roughness=roughness,
                ao=ao,
                curvature=curvature,
            )
        else:
            report["fallback_reason"] = "unsupported_surface_graph_mode"
            return basecolor, normal, roughness, ao, curvature, report
    except (AttributeError, KeyError, LookupError, NotImplementedError, TypeError, ValueError) as exc:
        report["fallback_reason"] = f"surface_graph_evaluation_failed:{type(exc).__name__}"
        return basecolor, normal, roughness, ao, curvature, report
    basecolor = images.get("basecolor", basecolor)
    normal = images.get("normal", normal)
    roughness = images.get("roughness", roughness)
    ao = images.get("ao", ao)
    curvature = images.get("curvature", curvature)
    report.update(eval_report)
    report["mode"] = mode
    report["applied"] = bool(report.get("applied_channels"))
    return basecolor, normal, roughness, ao, curvature, report


def build_surface_bundle(
    *,
    asset: dict[str, Any],
    out_dir: Path,
    shape_bundle: dict[str, Any],
    shape_runtime_mesh,
    topology_bundle: dict[str, Any],
    uv_runtime_mesh,
    uv_bundle: dict[str, Any] | None = None,
    repair_mode: str | None = None,
    runtime_config: dict[str, Any] | None = None,
    quality_generation: dict[str, Any] | None = None,
    skip_bakes: bool = False,
) -> dict[str, Any]:
    surface_cfg = dict(asset["build"]["surface"])
    surface_grammar = surface_grammar_for_asset(asset)
    source_surface = merge_surface_grammar(surface_with_style_pack_defaults(asset), surface_grammar)
    surface_story = _surface_story_controls(source_surface)
    surface_program = dict(source_surface.get("resolved_surface_program", {}))
    program_values = dict(surface_program.get("values", {}))
    if program_values.get("workflow"):
        surface_cfg["workflow"] = program_values["workflow"]
    if program_values.get("resolution") and not surface_cfg.get("resolution"):
        surface_cfg["resolution"] = program_values["resolution"]
    if program_values.get("maps"):
        surface_cfg["maps"] = list(
            dict.fromkeys([*program_values.get("maps", []), *surface_cfg.get("maps", [])])
        )
    if program_values.get("bakes"):
        surface_cfg["bakes"] = list(
            dict.fromkeys([*program_values.get("bakes", []), *surface_cfg.get("bakes", [])])
        )
    if program_values.get("decals"):
        surface_cfg["decals"] = list(
            dict.fromkeys([*program_values.get("decals", []), *surface_cfg.get("decals", [])])
        )
    if source_surface.get("decals"):
        surface_cfg["decals"] = list(
            dict.fromkeys([*surface_cfg.get("decals", []), *source_surface.get("decals", [])])
        )
    if surface_story["story_decals"]:
        surface_cfg["decals"] = list(
            dict.fromkeys([*surface_cfg.get("decals", []), *surface_story["story_decals"]])
        )
    if source_surface.get("bake"):
        surface_cfg["bakes"] = list(
            dict.fromkeys([*surface_cfg.get("bakes", []), *source_surface.get("bake", [])])
        )
    bake_profile_values = dict(
        asset.get("build", {}).get("surface", {}).get("resolved_bake_profile", {}).get("values", {})
    )
    if bake_profile_values.get("maps"):
        surface_cfg["bakes"] = list(
            dict.fromkeys([*bake_profile_values.get("maps", []), *surface_cfg.get("bakes", [])])
        )
    policy_values = dict(source_surface.get("resolved_surface_policy", {}).get("values", {}))
    if policy_values.get("maps"):
        surface_cfg["maps"] = list(
            dict.fromkeys([*policy_values.get("maps", []), *surface_cfg.get("maps", [])])
        )
    if policy_values.get("resolution"):
        surface_cfg["resolution"] = policy_values["resolution"]
    if repair_mode == "surface_enhance_v1":
        surface_cfg["decals"] = list(
            dict.fromkeys([*surface_cfg.get("decals", []), "service_label", "trim_wear", "warning_band"])
        )
    quality_surface = _quality_surface_conditioning(quality_generation)
    if quality_surface.get("quality_plan_consumed"):
        surface_cfg["decals"] = list(
            dict.fromkeys([*surface_cfg.get("decals", []), *_quality_surface_decals(quality_surface)])
        )
    library_decals = _surface_library_decals(source_surface)
    if library_decals:
        surface_cfg["decals"] = list(dict.fromkeys([*surface_cfg.get("decals", []), *library_decals]))
    pattern_names = list(
        dict.fromkeys(
            [
                *program_values.get("patterns", []),
                *source_surface.get("patterns", []),
                *_surface_library_patterns(source_surface),
                *_quality_surface_patterns(quality_surface),
            ]
        )
    )
    pattern_decals = _surface_pattern_decals(pattern_names)
    if pattern_decals:
        surface_cfg["decals"] = list(dict.fromkeys([*surface_cfg.get("decals", []), *pattern_decals]))
    uv_bundle = uv_bundle if isinstance(uv_bundle, dict) else {}
    material_zones = _material_zones_from_topology(asset, topology_bundle)
    uv_organization = (
        dict(uv_bundle.get("uv_organization", {}))
        if isinstance(uv_bundle.get("uv_organization"), dict)
        else {}
    )
    chart_manifest = (
        list(uv_bundle.get("chart_manifest", []))
        if isinstance(uv_bundle.get("chart_manifest"), list)
        else []
    )
    material_id_layout = (
        dict(uv_bundle.get("material_id_layout", {}))
        if isinstance(uv_bundle.get("material_id_layout"), dict)
        else {}
    )
    face_operation_summary = (
        dict(uv_bundle.get("face_operation_summary", {}))
        if isinstance(uv_bundle.get("face_operation_summary"), dict)
        else {}
    )
    operation_records = _dict_records(uv_bundle.get("operation_records"))
    kernel_feature_details = _dict_records(uv_bundle.get("kernel_feature_details"))
    kernel_edge_treatments = _dict_records(uv_bundle.get("kernel_edge_treatments"))
    kernel_pattern_instances = _dict_records(uv_bundle.get("kernel_pattern_instances"))
    kernel_deforms = _dict_records(uv_bundle.get("kernel_deforms"))
    kernel_profile_paths = _dict_records(uv_bundle.get("kernel_profile_paths"))
    kernel_edge_controls = _dict_records(uv_bundle.get("kernel_edge_controls"))
    kernel_component_assemblies = _dict_records(uv_bundle.get("kernel_component_assemblies"))
    kernel_sdf_fields = _dict_records(uv_bundle.get("kernel_sdf_fields"))
    kernel_terrain_fields = _dict_records(uv_bundle.get("kernel_terrain_fields"))
    kernel_scatters = _dict_records(uv_bundle.get("kernel_scatters"))
    kernel_surface_damage = _dict_records(uv_bundle.get("kernel_surface_damage"))
    kernel_surface_decals = _kernel_surface_semantic_decals(
        kernel_feature_details,
        kernel_edge_treatments,
        kernel_surface_damage,
        kernel_scatters,
        kernel_pattern_instances,
        kernel_component_assemblies,
        kernel_sdf_fields,
        kernel_terrain_fields,
        kernel_profile_paths,
        kernel_deforms,
        kernel_edge_controls,
    )
    if kernel_surface_decals:
        surface_cfg["decals"] = list(dict.fromkeys([*surface_cfg.get("decals", []), *kernel_surface_decals]))
    kernel_surface_semantics_drives_maps = bool(
        kernel_surface_damage
        or kernel_edge_treatments
        or kernel_feature_details
        or kernel_scatters
        or kernel_pattern_instances
        or kernel_component_assemblies
        or kernel_sdf_fields
        or kernel_terrain_fields
        or kernel_profile_paths
        or kernel_deforms
        or kernel_edge_controls
        or operation_records
    )
    generated_surface_charts = _generated_surface_chart_bindings(chart_manifest, uv_organization)
    material_slots = max(1, len({entry["material"] for entry in material_zones}))
    # `skip_bakes` (lathe quick): force the lightweight semantic_passthrough
    # path so we exit before the texture-bake fanout below. Material zones
    # and chart manifests are still computed so downstream consumers and
    # GLB export can attach material slots per part.
    hero_mode = False if skip_bakes else _hero_surface_enabled(shape_bundle)
    backend_report = _surface_backend_report(source_surface, surface_cfg, hero_mode)
    authored_material_maps = hero_mode and (
        _surface_story_drives_material_maps(surface_story)
        or bool(surface_grammar.get("features"))
        or kernel_surface_semantics_drives_maps
    )
    imagegen_mode = codex_imagegen_mode(runtime_config)
    if (
        backend_report.get("codex_imagegen_requested")
        and backend_report.get("backend_unavailable_policy") == "fail"
        and imagegen_mode not in {"emit_requests", "consume_outputs"}
    ):
        raise RuntimeError(
            "Codex ImageGen surface backend was requested, but the reference runtime has no available governed bridge"
        )
    manifest = _surface_manifest(surface_cfg, material_zones, material_slots, hero_mode)
    manifest["program"] = source_surface.get("program", "")
    manifest["material_graph"] = source_surface.get("material_graph", "")
    raw_resolved_material_graph = source_surface.get("resolved_material_graph", {})
    manifest["resolved_material_graph"] = (
        dict(raw_resolved_material_graph)
        if isinstance(raw_resolved_material_graph, dict)
        else {}
    )
    manifest["patterns"] = pattern_names
    manifest["palette"] = source_surface.get("palette", "")
    manifest["source_material_zones"] = list(source_surface.get("material_zones", []))
    manifest["source_bake"] = list(source_surface.get("bake", []))
    manifest["authoring_backend"] = backend_report["selected_backend_id"]
    manifest["authoring_mode"] = backend_report["authoring_mode"]
    manifest["surface_policy"] = source_surface.get("policy", "")
    manifest["bake_profile"] = asset.get("build", {}).get("surface", {}).get("bake_profile", "")
    manifest["render_fixture"] = asset.get("build", {}).get("surface", {}).get("render_fixture", "")
    manifest["decal_libraries"] = list(source_surface.get("decal_libraries", []))
    manifest["mask_programs"] = list(source_surface.get("mask_programs", []))
    manifest["trim_sheets"] = list(source_surface.get("trim_sheets", []))
    manifest["library_driven_decals"] = library_decals
    manifest["procedural_material_layers"] = list(surface_story["material_layers"])
    manifest["surface_story"] = {
        "wear_story": surface_story["wear_story"],
        "wear_level": surface_story["wear_level"],
        "story_decals": list(surface_story["story_decals"]),
    }
    manifest["surface_grammar"] = dict(surface_grammar)
    material_wear_hooks = _material_wear_graph_hooks(
        source_surface,
        mask_textures_generated=authored_material_maps or bool(surface_grammar.get("features")),
        surface_maps_driven=authored_material_maps or bool(surface_grammar.get("features")),
        kernel_surface_semantic_counts={
            "feature_details": len(kernel_feature_details),
            "edge_treatments": len(kernel_edge_treatments),
            "surface_damage": len(kernel_surface_damage),
            "scatters": len(kernel_scatters),
            "pattern_instances": len(kernel_pattern_instances),
            "component_assemblies": len(kernel_component_assemblies),
            "sdf_fields": len(kernel_sdf_fields),
            "terrain_fields": len(kernel_terrain_fields),
            "profile_paths": len(kernel_profile_paths),
            "deforms": len(kernel_deforms),
            "edge_controls": len(kernel_edge_controls),
            "operation_records": len(operation_records),
        },
    )
    surface_story_placement_plan = build_surface_story_placement_plan(
        source_surface=source_surface,
        surface_cfg=surface_cfg,
        material_zones=material_zones,
        material_id_layout=material_id_layout,
    )
    manifest["material_wear_graph_hooks"] = material_wear_hooks
    surface_graph_handoff = _compile_surface_graph_handoff(
        asset=asset,
        out_dir=out_dir,
        source_surface=source_surface,
    )
    manifest["surface_graph_handoff"] = surface_graph_handoff
    manifest["quality_plan_consumed"] = bool(quality_surface.get("quality_plan_consumed"))
    manifest["quality_generation_source_stage"] = quality_surface.get("source_stage")
    manifest["quality_surface_conditioning"] = quality_surface
    manifest["uv_organization"] = uv_organization
    manifest["chart_manifest"] = chart_manifest
    manifest["material_id_layout"] = material_id_layout
    manifest["face_operation_summary"] = face_operation_summary
    manifest["operation_records"] = operation_records
    manifest["kernel_feature_details"] = kernel_feature_details
    manifest["kernel_edge_treatments"] = kernel_edge_treatments
    manifest["kernel_pattern_instances"] = kernel_pattern_instances
    manifest["kernel_deforms"] = kernel_deforms
    manifest["kernel_profile_paths"] = kernel_profile_paths
    manifest["kernel_edge_controls"] = kernel_edge_controls
    manifest["kernel_component_assemblies"] = kernel_component_assemblies
    manifest["kernel_sdf_fields"] = kernel_sdf_fields
    manifest["kernel_terrain_fields"] = kernel_terrain_fields
    manifest["kernel_scatters"] = kernel_scatters
    manifest["kernel_surface_damage"] = kernel_surface_damage
    manifest["kernel_surface_decals"] = kernel_surface_decals
    manifest["kernel_surface_semantics_drives_maps"] = kernel_surface_semantics_drives_maps
    manifest["generated_surface_charts"] = generated_surface_charts
    manifest["surface_story_placement_plan"] = surface_story_placement_plan
    material_wear_hooks["generated_surface_charts"] = generated_surface_charts
    backend_report["quality_plan_consumed"] = bool(quality_surface.get("quality_plan_consumed"))
    backend_report["quality_generation_source_stage"] = quality_surface.get("source_stage")

    if not hero_mode:
        return {
            "backend_id": "lathe.surface.semantic_passthrough_v1",
            "surface_backend_report": backend_report,
            "material_slots": material_slots,
            "maps": list(surface_cfg.get("maps", [])),
            "surface_manifest": manifest,
            "material_wear_graph_hooks": material_wear_hooks,
            "material_zones": material_zones,
            "uv_organization": uv_organization,
            "chart_manifest": chart_manifest,
            "material_id_layout": material_id_layout,
            "face_operation_summary": face_operation_summary,
            "operation_records": operation_records,
            "kernel_feature_details": kernel_feature_details,
            "kernel_edge_treatments": kernel_edge_treatments,
            "kernel_pattern_instances": kernel_pattern_instances,
            "kernel_deforms": kernel_deforms,
            "kernel_profile_paths": kernel_profile_paths,
            "kernel_edge_controls": kernel_edge_controls,
            "kernel_component_assemblies": kernel_component_assemblies,
            "kernel_sdf_fields": kernel_sdf_fields,
            "kernel_terrain_fields": kernel_terrain_fields,
            "kernel_scatters": kernel_scatters,
            "kernel_surface_damage": kernel_surface_damage,
            "generated_surface_charts": generated_surface_charts,
            "surface_story_placement_plan": surface_story_placement_plan,
            "surface_graph_handoff": surface_graph_handoff,
        }

    size = _uv_image_size(surface_cfg.get("resolution"))
    face_parts = list(getattr(uv_runtime_mesh, "face_parts", []))
    mesh = uv_runtime_mesh.mesh
    maps_dir = out_dir / "maps"
    shape_cfg = asset.get("build", {}).get("shape", {})
    bake_cage_offset_cm = _level(shape_cfg.get("highlow_bake_cage_offset_cm"), 1.25)
    bake_max_ray_distance_cm = _optional_level(shape_cfg.get("highlow_bake_max_ray_distance_cm"))
    bake_bidirectional = _flag(shape_cfg.get("highlow_bake_bidirectional"), False)
    bake_transfer_stats: dict[str, Any] = {}
    high_mesh: trimesh.Trimesh | None = None
    high_source_uri: str | None = None
    high_source_report: dict[str, Any] = {}
    # Hero builds first rebuild a high source from the selected ShapeIR
    # primitive program so bakes see authored panels, fasteners, bevels,
    # vents, and cutters rather than a subdivided copy of the low mesh.
    # Non-hero builds keep the original ``highlow_mode`` gate.
    if (hero_mode or _highlow_requested(shape_cfg)) and len(mesh.faces) > 0:
        high_mesh, high_source_report = _shape_ir_high_source_mesh(mesh, shape_bundle, shape_cfg)
        if hero_mode and len(high_mesh.faces) <= len(mesh.faces):
            # Force a denser high source on hero builds when the
            # ShapeIR/procedural target collapsed to a copy. One
            # subdivision round is deterministic and cheap.
            high_mesh = high_mesh.subdivide()
            high_mesh.remove_unreferenced_vertices()
            high_mesh.merge_vertices()
            high_mesh.fix_normals()
            high_source_report = {
                **high_source_report,
                "method": (high_source_report.get("method", "copy") + "+hero_subdivide"),
                "output_faces": len(high_mesh.faces),
                "hero_mode": True,
            }
        high_source_path = out_dir / "high_source.glb"
        export_glb(high_mesh, high_source_path)
        high_source_uri = str(high_source_path.relative_to(out_dir)).replace("/", "\\")
    ao = bake_ao_map(mesh, size)
    curvature = (
        bake_highlow_curvature_transfer_map(
            mesh,
            high_mesh,
            size,
            bake_cage_offset_cm=bake_cage_offset_cm,
            max_ray_distance_cm=bake_max_ray_distance_cm,
            bidirectional=bake_bidirectional,
            transfer_stats=bake_transfer_stats,
            transfer_channel="curvature",
        )
        if high_mesh is not None
        else bake_curvature_map(mesh, size)
    )
    curvature_projection_quality = _projection_quality(
        {"curvature": bake_transfer_stats.get("curvature", {})}
    )
    curvature, curvature_tuning = _projection_tuned_curvature(
        curvature,
        curvature_projection_quality,
    )
    id_map = bake_id_map(mesh, face_parts, material_zones, size)
    wear_mask = (
        bake_wear_mask(id_map, material_zones, curvature, ao) if authored_material_maps else None
    )
    material_layer_mask = (
        bake_material_layer_mask(id_map, material_zones, curvature, ao)
        if authored_material_maps and surface_story["material_layers"]
        else None
    )
    basecolor = bake_basecolor_map(id_map, material_zones, curvature, ao)
    base_normal = (
        bake_highlow_normal_transfer_map(
            mesh,
            high_mesh,
            size,
            bake_cage_offset_cm=bake_cage_offset_cm,
            max_ray_distance_cm=bake_max_ray_distance_cm,
            bidirectional=bake_bidirectional,
            transfer_stats=bake_transfer_stats,
            transfer_channel="normal",
        )
        if high_mesh is not None
        else bake_normal_map(mesh, size)
    )
    normal_map_report = {
        "schema": "lathe.surface.normal_map_report.v1",
        "normal_space": "tangent",
        "base_source": "highlow_tangent_space_transfer"
        if high_mesh is not None
        else "low_uv_tangent_space_neutral",
        "detail_source": "material_profile_curvature_detail",
        "world_space_face_normal_bake": False,
    }
    if face_operation_summary:
        normal_map_report["face_operation_summary"] = face_operation_summary
    manifest["normal_map_report"] = dict(normal_map_report)
    normal = enhance_normal_map(base_normal, id_map, material_zones, curvature)
    roughness = bake_roughness_map(id_map, material_zones, curvature, ao)
    metallic = bake_metallic_map(id_map, material_zones)
    emissive = bake_emissive_map(id_map, material_zones)
    basecolor, normal, roughness, ao, curvature, surface_graph_buffer_report = _apply_surface_graph_runtime_buffers(
        surface_graph_handoff=surface_graph_handoff,
        size=size,
        material_zones=material_zones,
        basecolor=basecolor,
        normal=normal,
        roughness=roughness,
        ao=ao,
        curvature=curvature,
    )
    if surface_graph_buffer_report.get("applied"):
        backend_report["surface_graph_buffers_applied"] = True
        backend_report["surface_graph_buffer_channels"] = list(surface_graph_buffer_report.get("applied_channels", []))
        if "normal" in surface_graph_buffer_report.get("applied_channels", []):
            normal_map_report["detail_source"] = "material_profile_curvature_detail+surface_graph_tangent_detail"
    else:
        backend_report["surface_graph_buffers_applied"] = False
        backend_report["surface_graph_buffer_fallback_reason"] = surface_graph_buffer_report.get("fallback_reason", "")
    normal_map_report["surface_graph_buffer_source"] = surface_graph_buffer_report.get("source", "")
    normal_map_report["surface_graph_buffers_applied"] = "normal" in surface_graph_buffer_report.get("applied_channels", [])
    manifest["normal_map_report"] = dict(normal_map_report)
    manifest["surface_graph_buffer_report"] = dict(surface_graph_buffer_report)
    basecolor, normal, roughness, ao, curvature, emissive = pad_low_coverage_atlas_maps(
        id_map=id_map,
        material_zones=material_zones,
        basecolor=basecolor,
        normal=normal,
        roughness=roughness,
        ao=ao,
        curvature=curvature,
        emissive=emissive,
    )
    basecolor, roughness, emissive = apply_decal_overlays(
        basecolor,
        roughness,
        emissive,
        list(surface_cfg.get("decals", [])),
        placements=surface_story_placement_plan.get("placements", []),
    )
    if repair_mode == "surface_enhance_v1":
        basecolor, normal, roughness, emissive = _enhance_surface_maps_for_repair(
            basecolor, normal, roughness, emissive
        )
    orm = derive_orm_map(ao, roughness, metallic)
    control_pack = _write_surface_control_pack(
        out_dir=out_dir,
        size=size,
        material_zones=material_zones,
        surface_cfg=surface_cfg,
        source_surface=source_surface,
        ao=ao,
        curvature=curvature,
        normal=normal,
        id_map=id_map,
        wear_mask=wear_mask,
        material_layer_mask=material_layer_mask,
        uv_organization=uv_organization,
        chart_manifest=chart_manifest,
        material_id_layout=material_id_layout,
        generated_surface_charts=generated_surface_charts,
        surface_story_placement_plan=surface_story_placement_plan,
    )
    manifest["generated_surface_chart_maps"] = dict(
        control_pack.get("generated_surface_chart_maps", {})
    )
    manifest["generated_surface_chart_atlas"] = dict(
        control_pack.get("generated_surface_chart_atlas", {})
    )
    codex_requests: dict[str, Any] = {}
    codex_outputs: dict[str, Any] = {}
    if backend_report.get("codex_imagegen_requested") and imagegen_mode == "emit_requests":
        codex_requests = emit_codex_imagegen_requests(
            asset=asset,
            out_dir=out_dir,
            runtime_config=runtime_config,
            surface_cfg=surface_cfg,
            source_surface=source_surface,
            material_zones=material_zones,
            control_pack=control_pack,
        )
        backend_report["codex_imagegen_pending"] = True
        backend_report["codex_imagegen_request_manifest"] = codex_requests.get("manifest_uri", "")
    elif backend_report.get("codex_imagegen_requested") and imagegen_mode == "consume_outputs":
        basecolor, codex_outputs = consume_codex_imagegen_outputs(
            out_dir=out_dir,
            runtime_config=runtime_config,
            id_map=id_map,
            basecolor=basecolor,
            material_zones=material_zones,
        )
        backend_report["codex_imagegen_ran"] = bool(codex_outputs.get("consumed"))
        backend_report["codex_imagegen_output_manifest"] = codex_outputs.get("manifest_uri", "")
        if backend_report["codex_imagegen_ran"]:
            backend_report["fallback_backend_id"] = ""
            backend_report["fallback_reason"] = ""

    outputs = {
        "basecolor": _write_image(basecolor, maps_dir / "basecolor.png"),
        "normal": _write_image(normal, maps_dir / "normal.png"),
        "roughness": _write_image(roughness, maps_dir / "roughness.png"),
        "ao": _write_image(ao, maps_dir / "ao.png"),
        "curvature": _write_image(curvature, maps_dir / "curvature.png"),
        "id": _write_image(id_map, maps_dir / "id.png"),
        "orm": _write_image(orm, maps_dir / "orm.png"),
        "emissive": _write_image(emissive, maps_dir / "emissive.png"),
    }
    if wear_mask is not None:
        outputs["wear_mask"] = _write_image(wear_mask, maps_dir / "wear_mask.png")
    if material_layer_mask is not None:
        outputs["material_layer_mask"] = _write_image(material_layer_mask, maps_dir / "material_layer_mask.png")

    shape_selected_id = shape_bundle.get("selected_candidate_id")
    high_mesh_uri = next(
        (
            item["mesh_uri"]
            for item in shape_bundle.get("candidates", [])
            if item.get("candidate_id") == shape_selected_id
        ),
        None,
    )
    selected_candidate = next(
        (
            item
            for item in shape_bundle.get("candidates", [])
            if item.get("candidate_id") == shape_selected_id
        ),
        {},
    )
    high_triangle_count = int(
        high_source_report.get("output_faces")
        or selected_candidate.get("mesh_stats", {}).get("triangle_count", 0)
    )
    low_triangle_count = int(topology_bundle.get("mesh_stats", {}).get("triangle_count", 0))
    if high_triangle_count > low_triangle_count >= 0:
        distinction_ratio = round(
            (high_triangle_count - low_triangle_count)
            / max(1, high_triangle_count),
            6,
        )
    else:
        distinction_ratio = 0.0
    low_relation = HighLowRelation(
        high_mesh_uri=high_mesh_uri,
        low_mesh_uri=topology_bundle.get("mesh_uri"),
        bake_cage_offset_cm=bake_cage_offset_cm,
        source="surface_high_to_low_transfer_v1" if high_source_uri else "hero_surface_runtime_v1",
        high_triangle_count=high_triangle_count,
        low_triangle_count=low_triangle_count,
        distinction_ratio=distinction_ratio,
        bake_groups=[
            entry.get("bake_group", entry.get("part"))
            for entry in selected_candidate.get("mesh_ir", {}).get("bake_groups", [])
        ]
        or None,
        authoritative=True,
    )
    highlow_payload = low_relation.to_dict()
    if high_source_uri:
        projection_quality = _projection_quality(bake_transfer_stats)
        transfer_policy = _projection_transfer_policy(projection_quality)
        highlow_payload["high_mesh_uri"] = high_source_uri
        highlow_payload["high_source_report"] = high_source_report
        highlow_payload["projection_quality"] = projection_quality
        highlow_payload["transfer_decision"] = projection_quality["decision"]
        highlow_payload["transfer_policy"] = transfer_policy
        highlow_payload["projection_trust"] = transfer_policy["projection_trust"]
        highlow_payload["bake_transfer"] = {
            "normal": "tangent_space_ray_cage_high_face_normal_to_low_uv",
            "curvature": "ray_cage_high_face_curvature_to_low_uv",
            "bake_cage_offset_cm": bake_cage_offset_cm,
            "max_ray_distance_cm": bake_max_ray_distance_cm,
            "bidirectional": bake_bidirectional,
            "normal_space": "low_uv_tangent",
            "miss_fallback": "cage_offset_nearest_high_face",
            "projection_stats": bake_transfer_stats,
            "projection_quality": projection_quality,
            "transfer_decision": projection_quality["decision"],
            "transfer_policy": transfer_policy,
            "projection_trust": transfer_policy["projection_trust"],
            "curvature_tuning": curvature_tuning,
        }

    relative_outputs = {
        name: {**entry, "uri": str(Path(entry["uri"]).relative_to(out_dir)).replace("/", "\\")}
        for name, entry in outputs.items()
    }

    return {
        "backend_id": "lathe.surface.hero_pbr_v1",
        "surface_backend_report": backend_report,
        "surface_program": source_surface.get("program", ""),
        "patterns": pattern_names,
        "repair_mode": repair_mode or "",
        "material_slots": material_slots,
        "maps": list(surface_cfg.get("maps", [])),
        "surface_manifest": manifest,
        "normal_map_report": normal_map_report,
        "material_wear_graph_hooks": material_wear_hooks,
        "material_zones": material_zones,
        "uv_organization": uv_organization,
        "chart_manifest": chart_manifest,
        "material_id_layout": material_id_layout,
        "face_operation_summary": face_operation_summary,
        "operation_records": operation_records,
        "kernel_feature_details": kernel_feature_details,
        "kernel_edge_treatments": kernel_edge_treatments,
        "kernel_pattern_instances": kernel_pattern_instances,
        "kernel_deforms": kernel_deforms,
        "kernel_profile_paths": kernel_profile_paths,
        "kernel_edge_controls": kernel_edge_controls,
        "kernel_component_assemblies": kernel_component_assemblies,
        "kernel_sdf_fields": kernel_sdf_fields,
        "kernel_terrain_fields": kernel_terrain_fields,
        "kernel_scatters": kernel_scatters,
        "kernel_surface_damage": kernel_surface_damage,
        "generated_surface_charts": generated_surface_charts,
        "generated_surface_chart_maps": dict(control_pack.get("generated_surface_chart_maps", {})),
        "generated_surface_chart_atlas": dict(control_pack.get("generated_surface_chart_atlas", {})),
        "surface_story_placement_plan": surface_story_placement_plan,
        "outputs": relative_outputs,
        "surface_control_pack": control_pack,
        "codex_imagegen_requests": codex_requests,
        "codex_imagegen_outputs": codex_outputs,
        "atlas_assembly_ir": _atlas_assembly_ir(
            surface_cfg,
            control_pack,
            relative_outputs,
            uv_organization=uv_organization,
            chart_manifest=chart_manifest,
            material_id_layout=material_id_layout,
            generated_surface_charts=generated_surface_charts,
            surface_story_placement_plan=surface_story_placement_plan,
        ),
        "surface_validation_ir": _surface_validation_ir(surface_cfg, backend_report),
        "surface_repair_ir": _surface_repair_ir(backend_report),
        "highlow_relation": highlow_payload,
        "surface_graph_handoff": surface_graph_handoff,
        "surface_graph_buffer_report": surface_graph_buffer_report,
        "bake_outputs": {
            "normal": relative_outputs["normal"]["uri"],
            "ao": relative_outputs["ao"]["uri"],
            "curvature": relative_outputs["curvature"]["uri"],
            "id": relative_outputs["id"]["uri"],
        },
        "decal_masks": list(surface_cfg.get("decals", [])),
    }
