"""Package stage step body (USD/glTF/OBJ serialization + manifest + trace).

Extracted from ``lathe/executor.py`` during Stage 2.IV. The trace manifest
construction lives inside this module so the package stage owns the whole
build_trace pipeline (including stage-execution telemetry collation).
"""

from __future__ import annotations

import importlib.metadata
import warnings
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import trimesh
from PIL import Image
from trimesh.visual.material import PBRMaterial
from trimesh.visual.texture import TextureVisuals

from ...engine_manifests import ADAPTERS as _ENGINE_ADAPTERS
from ...engine_manifests import manifest_filename as _engine_manifest_filename
from ...errors import BuildError
from ...imaging import open_guarded
from ...nested_assets import nested_asset_manifest_for_signature
from ...paths import PathGuardError, safe_resolve
from ...security import redact_secrets
from ...selector_manifest import build_selector_manifest, write_selector_manifest
from ..common import dump_json, hash_obj, hash_ref, output_entry, relpath
from ..io import (
    export_glb,
    export_gltf,
    export_obj,
    export_runtime_scene_glb,
    export_runtime_scene_glb_with_pbr,
    write_usda,
)
from ..mesh import RuntimeMesh
from ..rendering import render_lod_sheet, render_mesh_preview, render_uv_layout

STAGE_ORDER_FOR_TRACE = [
    "shape",
    "topology",
    "uv",
    "surface",
    "execution",
    "rig",
    "interfaces",
    "physics",
    "optimize",
    "validate",
    "package",
]

PBR_TEXTURE_MAPS = ("basecolor", "normal", "orm", "ao", "emissive")

_TEXTURE_COLOR_SPACES = {
    "basecolor": "srgb",
    "emissive": "srgb",
    "normal": "non_color_linear",
    "orm": "non_color_linear",
    "ao": "non_color_linear",
    "roughness": "non_color_linear",
    "curvature": "non_color_linear",
    "id": "non_color_data",
    "wear_mask": "non_color_linear",
    "material_layer_mask": "non_color_linear",
}

_TEXTURE_USAGES = {
    "basecolor": "base_color",
    "emissive": "emissive_color",
    "normal": "tangent_space_normal",
    "orm": "occlusion_roughness_metallic_packed",
    "ao": "ambient_occlusion",
    "roughness": "roughness",
    "curvature": "curvature_mask",
    "id": "material_id",
    "wear_mask": "wear_mask",
    "material_layer_mask": "material_layer_mask",
}


def _texture_color_space(map_name: str) -> str:
    return _TEXTURE_COLOR_SPACES.get(str(map_name), "non_color_linear")


def _texture_usage(map_name: str) -> str:
    return _TEXTURE_USAGES.get(str(map_name), str(map_name))


def _surface_normal_metadata(surface_bundle: dict[str, Any]) -> dict[str, Any]:
    control_pack = surface_bundle.get("surface_control_pack")
    control_pack = control_pack if isinstance(control_pack, dict) else {}
    metadata = control_pack.get("map_metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    normal = metadata.get("normal_reference")
    return dict(normal) if isinstance(normal, dict) else {}


def _surface_material_semantics(surface_bundle: dict[str, Any]) -> dict[str, Any]:
    control_pack = surface_bundle.get("surface_control_pack")
    control_pack = control_pack if isinstance(control_pack, dict) else {}
    constraints = control_pack.get("per_zone_constraints")
    constraints = constraints if isinstance(constraints, dict) else {}
    raw_zones = surface_bundle.get("material_zones")
    raw_zones = raw_zones if isinstance(raw_zones, list) else []

    records: list[dict[str, Any]] = []
    seen_parts: set[str] = set()

    def merged_record(part: str, zone: dict[str, Any], constraint: dict[str, Any]) -> dict[str, Any] | None:
        material = zone.get("material", constraint.get("material", ""))
        semantic_role = zone.get("semantic_surface_role") or constraint.get("semantic_surface_role") or ""
        features = _list_value(zone.get("surface_features") or constraint.get("surface_features"))
        hints = _list_value(zone.get("material_hints") or constraint.get("material_hints"))
        wear_layers = _list_value(zone.get("wear_layers") or constraint.get("wear_layers"))
        topology_records = _list_value(zone.get("topology_material_zones") or constraint.get("topology_material_zones"))
        material_source = zone.get("material_source") or constraint.get("material_source") or ""
        material_zone_source = zone.get("material_zone_source") or constraint.get("material_zone_source") or ""
        topology_hint = zone.get("topology_material_hint") or constraint.get("topology_material_hint") or ""
        previous_material = zone.get("previous_material") or constraint.get("previous_material") or ""
        if not any(
            (
                semantic_role,
                features,
                hints,
                wear_layers,
                topology_records,
                material_source,
                material_zone_source,
                topology_hint,
                previous_material,
            )
        ):
            return None
        return {
            "part": part,
            "material": str(material or ""),
            "semantic_surface_role": str(semantic_role),
            "surface_features": features,
            "material_hints": hints,
            "wear_layers": wear_layers,
            "topology_material_zones": topology_records,
            "material_source": str(material_source),
            "material_zone_source": str(material_zone_source),
            "topology_material_hint": str(topology_hint),
            "previous_material": str(previous_material),
        }

    for zone in raw_zones:
        if not isinstance(zone, dict):
            continue
        part = str(zone.get("part") or "")
        if not part:
            continue
        constraint = constraints.get(part)
        constraint = constraint if isinstance(constraint, dict) else {}
        record = merged_record(part, zone, constraint)
        if record:
            records.append(record)
            seen_parts.add(part)

    for part, constraint in constraints.items():
        part_text = str(part)
        if part_text in seen_parts or not isinstance(constraint, dict):
            continue
        record = merged_record(part_text, {}, constraint)
        if record:
            records.append(record)

    role_counts: dict[str, int] = {}
    feature_counts: dict[str, int] = {}
    hint_counts: dict[str, int] = {}
    for record in records:
        role = str(record.get("semantic_surface_role") or "")
        if role:
            role_counts[role] = role_counts.get(role, 0) + 1
        for feature in record.get("surface_features") or []:
            feature_text = str(feature)
            if feature_text:
                feature_counts[feature_text] = feature_counts.get(feature_text, 0) + 1
        for hint in record.get("material_hints") or []:
            hint_text = str(hint)
            if hint_text:
                hint_counts[hint_text] = hint_counts.get(hint_text, 0) + 1

    return {
        "schema": "lathe.surface_material_semantics.v1",
        "source": "surface_bundle.material_zones+surface_control_pack.per_zone_constraints",
        "zones": records,
        "role_counts": role_counts,
        "surface_feature_counts": feature_counts,
        "material_hint_counts": hint_counts,
    }


def _surface_texture_records(surface_bundle: dict[str, Any], texture_outputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normal_metadata = _surface_normal_metadata(surface_bundle)
    normal_report = surface_bundle.get("normal_map_report")
    if not isinstance(normal_report, dict):
        normal_report = {}
    by_name: dict[str, dict[str, Any]] = {}
    for entry in texture_outputs:
        if not isinstance(entry, dict):
            continue
        fmt = str(entry.get("format") or "")
        if not fmt.endswith("_texture"):
            continue
        name = fmt[: -len("_texture")]
        uri = entry.get("uri")
        if not name or not uri:
            continue
        by_name[name] = {"name": name, "uri": uri, "source": "package_copied_texture"}
    outputs = surface_bundle.get("outputs", {})
    if isinstance(outputs, dict):
        for name, entry in outputs.items():
            if name in by_name or not isinstance(entry, dict):
                continue
            uri = entry.get("uri")
            if uri:
                by_name[str(name)] = {"name": str(name), "uri": uri, "source": "surface_stage_texture"}
    records: list[dict[str, Any]] = []
    for name in sorted(by_name):
        record = dict(by_name[name])
        record["usage"] = _texture_usage(name)
        record["color_space"] = _texture_color_space(name)
        record["sample_as"] = "color" if record["color_space"] == "srgb" else "data"
        if name == "normal":
            source_convention = str(normal_metadata.get("convention") or "OpenGL +Y")
            record["normal_space"] = str(
                normal_metadata.get("space")
                or normal_report.get("normal_space")
                or "tangent"
            )
            record["normal_basis"] = "mesh_uv_tangent"
            record["green_channel"] = "positive_bitangent"
            record["source_convention"] = source_convention
            record["encoding"] = str(normal_metadata.get("encoding") or "rgb_unit_signed_8bit")
            record["z_policy"] = str(normal_metadata.get("z_policy") or "renormalized_from_xy")
            record["neutral_rgb"] = list(normal_metadata.get("neutral_rgb") or [128, 128, 255])
            record["world_space_face_normal_bake"] = bool(
                normal_metadata.get(
                    "world_space_face_normal_bake",
                    normal_report.get("world_space_face_normal_bake", False),
                )
            )
            record["color_space"] = "non_color_linear"
            record["sample_as"] = "normal"
        if name == "orm":
            record["channels"] = {"r": "ambient_occlusion", "g": "roughness", "b": "metallic"}
        records.append(record)
    return records


def _surface_texture_conventions(
    surface_bundle: dict[str, Any],
    texture_outputs: list[dict[str, Any]],
) -> dict[str, Any]:
    textures = _surface_texture_records(surface_bundle, texture_outputs)
    material_semantics = _surface_material_semantics(surface_bundle)
    normal_report = surface_bundle.get("normal_map_report")
    if not isinstance(normal_report, dict):
        normal_report = {}
    normal_metadata = _surface_normal_metadata(surface_bundle)
    graph_report = surface_bundle.get("surface_graph_buffer_report")
    if not isinstance(graph_report, dict):
        graph_report = {}
    source_convention = str(normal_metadata.get("convention") or "OpenGL +Y")
    return {
        "schema": "lathe.texture_conventions.v1",
        "textures": textures,
        "normal_map": {
            "space": str(normal_metadata.get("space") or normal_report.get("normal_space") or "tangent"),
            "basis": "mesh_uv_tangent",
            "source_convention": source_convention,
            "green_channel": "positive_bitangent",
            "encoding": str(normal_metadata.get("encoding") or "rgb_unit_signed_8bit"),
            "z_policy": str(normal_metadata.get("z_policy") or "renormalized_from_xy"),
            "neutral_rgb": list(normal_metadata.get("neutral_rgb") or [128, 128, 255]),
            "world_space_face_normal_bake": bool(
                normal_metadata.get(
                    "world_space_face_normal_bake",
                    normal_report.get("world_space_face_normal_bake", False),
                )
            ),
            "base_source": str(normal_report.get("base_source") or ""),
            "detail_source": str(normal_report.get("detail_source") or ""),
            "surface_graph_buffers_applied": bool(normal_report.get("surface_graph_buffers_applied", False)),
        },
        "color_spaces": {record["name"]: record["color_space"] for record in textures},
        "surface_material_semantics": material_semantics,
        "surface_graph_buffer_report": graph_report,
    }


def _package_visual_quality_gate(
    validate_bundle: dict[str, Any],
    previews: list[str],
) -> dict[str, Any]:
    """Carry visual approval separately from pipeline certification."""
    gate = validate_bundle.get("visual_quality_gate")
    if not isinstance(gate, dict):
        return {
            "version": "lathe.visual_quality_gate_v1",
            "pipeline_certified": bool(validate_bundle.get("certified", False)),
            "visual_quality_gate": "not_verified",
            "human_review_required": True,
            "visual_claim_level": "not_verified",
            "blockers": ["visual_quality_gate_missing_from_validate_report"],
            "signals": {
                "package_final_beauty_present": any(path.endswith("turntable.png") for path in previews),
                "package_preview_count": len(previews),
            },
        }
    packaged_gate = dict(gate)
    blockers = {
        str(blocker)
        for blocker in packaged_gate.get("blockers", [])
        if blocker
    }
    final_beauty_paths = [path for path in previews if path.endswith("turntable.png")]
    material_id_paths = [path for path in previews if path.endswith("material_ids.png")]
    if final_beauty_paths:
        blockers.discard("final_beauty_preview_not_present")
    if final_beauty_paths and material_id_paths and set(final_beauty_paths).isdisjoint(material_id_paths):
        blockers.discard("final_beauty_not_distinct_from_debug_preview")
    signals = dict(packaged_gate.get("signals") or {})
    signals.update(
        {
            "package_final_beauty_present": bool(final_beauty_paths),
            "package_material_ids_present": bool(material_id_paths),
            "package_preview_count": len(previews),
            "package_preview_paths": list(previews),
        }
    )
    pipeline_certified = bool(packaged_gate.get("pipeline_certified", validate_bundle.get("certified", False)))
    if not pipeline_certified:
        visual_quality_gate = "not_approved"
        visual_claim_level = "pipeline_failed"
    elif not final_beauty_paths:
        visual_quality_gate = "not_verified"
        visual_claim_level = "not_verified"
        blockers.add("final_beauty_preview_not_present")
    elif blockers:
        visual_quality_gate = "review_required"
        visual_claim_level = "pipeline_certified_only"
    else:
        visual_quality_gate = "approved"
        visual_claim_level = "visual_approved"
    packaged_gate.update(
        {
            "pipeline_certified": pipeline_certified,
            "visual_quality_gate": visual_quality_gate,
            "human_review_required": visual_quality_gate != "approved",
            "visual_claim_level": visual_claim_level,
            "blockers": sorted(blockers),
            "signals": signals,
        }
    )
    return packaged_gate

_ENGINE_RUNTIME_IR_FIELDS: dict[str, tuple[str, tuple[str, ...]]] = {
    "behavior": ("behavior_ir", ("actions", "affordances", "triggers", "state_variables", "transitions")),
    "persistence": ("persistence_ir", ("persistent_variables", "restoration_hooks", "restorable_physics_bodies", "save_keys")),
    "quest_dialogue": ("quest_dialogue_ir", ("quests", "objectives", "dialogue_nodes", "speakers", "rewards", "conditions")),
    "camera_cinematic": ("camera_cinematic_ir", ("cameras", "shots", "sequences", "rails", "look_targets", "focus_zones", "composition_guides")),
    "audio": ("audio_ir", ("cues", "music_states", "ambient_beds", "foley_emitters", "zones", "acoustic_spaces")),
    "runtime_partition": ("runtime_partition_ir", ("partitions", "cells", "streaming_volumes", "load_groups", "lod_rings", "visibility_regions", "residency_rules")),
    "multiplayer_session": ("multiplayer_session_ir", ("sessions", "authority_maps", "replicated_states", "rpc_channels", "sync_ticks", "prediction_paths", "rollback_buffers", "matchmaking_rules")),
    "localization_text": ("localization_text_ir", ("tables", "string_keys", "translations", "plural_rules", "fallback_chains", "subtitle_timings", "voiceover_bindings", "glyph_coverage", "validation_guards")),
    "accessibility_ux": ("accessibility_ux_ir", ("roots", "input_maps", "readable_state_cues", "contrast_regions", "caption_panels", "feedback_cues", "focus_navigation", "option_ports", "usability_guards")),
    "economy_simulation": ("economy_simulation_ir", ("roots", "resource_flows", "currency_pairs", "loot_reward_tables", "price_curves", "progression_tracks", "spawn_modulators", "telemetry_inputs", "validation_guards")),
    "scene_system": ("scene_system_ir", ("roots", "hierarchies", "placement_anchors", "spawn_layers", "lighting_camera_layers", "navigation_regions", "environment_volumes", "streaming_tags", "export_targets", "validation_guards")),
    "procedural_prefab": ("procedural_prefab_ir", ("roots", "source_slots", "parameter_bindings", "variant_overrides", "lod_bindings", "material_bindings", "collision_bindings", "engine_exports", "dependency_guards")),
    "engine_runtime": ("engine_runtime_ir", ("runtime_roots", "host_targets", "plugin_adapters", "bundle_manifests", "parameter_overrides", "live_hooks", "asset_sinks", "host_contracts", "diagnostics_ports")),
    "behavior_logic": ("behavior_logic_ir", ("graphs", "state_nodes", "event_edges", "condition_rules", "action_ports", "blackboard_bindings", "timer_tracks", "utility_weights", "fallback_paths", "debug_ports")),
    "encounter_flow": ("encounter_flow_ir", ("roots", "footprints", "spawn_points", "patrol_routes", "cover_zones", "objectives", "waves", "reward_exit_zones", "hazard_boundaries", "readability_cues")),
    "inventory_economy": ("inventory_economy_ir", ("roots", "containers", "value_markers", "quantity_tracks", "rarity_tiers", "access_affordances", "storage_slots", "pickup_handles", "vendor_bindings", "resource_ports")),
    "world_system": ("world_system_ir", ("roots", "region_layers", "route_graphs", "faction_rule_zones", "progression_chains", "resource_spawn_distributions", "landmarks", "transition_gates", "debug_labels", "usage_masks")),
    "simulation_environment": ("simulation_environment_ir", ("roots", "domain_bounds", "emitters", "flow_vectors", "field_gradients", "solver_constraints", "probes", "obstacle_boundaries", "temporal_markers", "material_responses", "wear_masks")),
    "stateful_destructible": ("stateful_destructible_ir", ("roots", "intact_shells", "damage_states", "fracture_lines", "fragment_zones", "weak_points", "repair_affordances", "transition_cues", "hazard_boundaries", "debris_scatters", "wear_masks")),
    "live_procedural_runtime": ("live_procedural_runtime_ir", ("cores", "input_ports", "engine_hooks", "output_slots", "version_contracts", "hot_reload_cues", "validation_guards", "cache_states", "metrics_debug_ports", "override_wear")),
    "multi_asset_bundle": ("multi_asset_bundle_ir", ("roots", "bundle_manifests", "member_asset_slots", "dependency_links", "layout_anchors", "variant_lod_entries", "shared_material_style_zones", "export_markers", "assembly_guides", "bounds_references", "usage_masks")),
    "style_stack_visual": ("style_stack_visual_ir", ("roots", "style_axes", "palette_material_models", "surface_authoring_modes", "outline_lighting_strategies", "detail_layers", "motion_styles", "construction_markers", "compatibility_bridges", "refusal_constraints", "style_iteration_wear_masks")),
    "cross_domain_composition": ("cross_domain_composition_ir", ("roots", "domain_pillars", "handoff_links", "shared_rule_layers", "interface_port_maps", "domain_boundaries", "conflict_refusal_cues", "previews", "dependency_guides", "integration_labels", "handoff_wear_masks")),
    "rig_animation_proxy": ("rig_animation_proxy_ir", ("roots", "root_controls", "joint_chains", "limb_markers", "ik_targets", "motion_arcs", "skin_weight_zones", "attachment_sockets", "morph_expression_markers", "range_limit_guards", "animation_state_cues")),
    "cloth_attachment": ("cloth_attachment_ir", ("roots", "anchors", "fabric_panels", "seams_hems", "fold_tension_lines", "attachment_hardware", "trim_borders", "motion_wind_cues", "material_pattern_zones", "collision_clearance_cues", "cloth_wear_masks")),
    "domain_kit": ("domain_kit_ir", ("roots", "canonical_part_sets", "snap_ports", "variant_slots", "scale_grid_refs", "style_material_rules", "assembly_guides", "compatibility_markers", "library_labels", "usage_masks")),
    "typed_data_kernel": ("typed_data_kernel_ir", ("roots", "typed_bundle_buses", "mesh_points_volume_slots", "heightfield_spline_sdf_slots", "image_rig_slots", "contract_badges", "transform_conversion_links", "dependency_order_markers", "cache_delta_states", "validation_guard_edges", "data_flow_wear_masks")),
    "attribute_surface_graph": ("attribute_surface_graph_ir", ("roots", "attribute_streams", "surface_node_graphs", "authoring_modes", "mask_layers", "materialx_pbr_outputs", "attribute_math_rules", "texture_frequency_controls", "preview_bake_targets", "invalid_unbound_guards", "surface_iteration_wear_masks")),
    "vegetation_library": ("vegetation_library_ir", ("roots", "species_catalogs", "trunk_branch_grammars", "leaf_cluster_rules", "root_anchors", "lod_billboard_sets", "wind_motion_markers", "season_variants", "growth_parameter_ports", "biome_distribution_masks", "vegetation_usage_wear_masks")),
    "terrain_heightfield": ("terrain_heightfield_ir", ("roots", "heightfield_domains", "elevation_layers", "erosion_flow_networks", "slope_deposition_masks", "biome_material_zones", "drainage_channels", "terrain_mesh_exports", "sample_probe_grids", "tileability_boundaries", "terrain_iteration_wear_masks")),
    "wfc_tile_solver": ("wfc_tile_solver_ir", ("roots", "tileset_catalogs", "socket_edge_definitions", "adjacency_rule_matrices", "constraint_grids", "entropy_weight_markers", "seed_region_ports", "solver_iteration_paths", "failure_backtrack_guards", "solved_layout_outputs", "tile_usage_wear_masks")),
    "cga_building_grammar": ("cga_building_grammar_ir", ("roots", "root_massing_volumes", "rule_stacks", "split_repeat_extrude_ops", "facade_floor_bands", "terminal_modules", "derivation_flow_lines", "variation_parameter_ports", "constraint_guard_rules", "output_assembly_markers", "grammar_iteration_wear_masks")),
    "volume_effects_data": ("volume_effects_data_ir", ("roots", "volume_domains", "density_temperature_velocity_channels", "emitters_sources", "force_flow_vectors", "slice_sample_planes", "threshold_isosurface_controls", "mesh_particle_outputs", "cache_tiles", "field_boundary_guards", "volume_iteration_wear_masks")),
    "instance_pattern_scatter": ("instance_pattern_scatter_ir", ("roots", "source_part_libraries", "point_cloud_samples", "surface_projection_targets", "density_mask_controls", "poisson_spacing_rules", "orient_scale_jitter_controls", "collision_exclusion_guards", "instance_output_markers", "scatter_debug_traces", "scatter_usage_wear_masks")),
    "f_rep_sdf_composition": ("f_rep_sdf_composition_ir", ("roots", "implicit_primitive_sets", "expression_trees", "smooth_boolean_ops", "blend_radius_controls", "sample_bounds", "material_region_fields", "extraction_meshing_ports", "failure_bounds_guards", "organic_silhouette_markers", "implicit_iteration_wear_masks")),
    "subdivision_finishing": ("subdivision_finishing_ir", ("roots", "control_cages", "subdivision_schemes", "crease_sharpness_tags", "boundary_uv_rules", "remesh_quad_targets", "smoothing_relax_passes", "displacement_detail_layers", "quality_probes", "output_lod_markers", "finishing_iteration_wear_masks")),
    "humanoid_anatomy": ("humanoid_anatomy_ir", ("roots", "canonical_topologies", "body_proportions", "anatomy_region_maps", "landmark_loops", "joint_rig_anchors", "morph_target_databases", "skin_weight_zones", "style_variant_slots", "anatomy_validation_guards", "anatomy_iteration_wear_masks")),
    "face_sdf_cel_shading": ("face_sdf_cel_shading_ir", ("roots", "face_region_sdfs", "shadow_band_fields", "ramp_lut_stacks", "outline_hulls", "light_direction_controls", "id_mask_channels", "style_bridge_guards", "preview_outputs", "expression_morph_hooks", "cel_iteration_wear_masks")),
    "rig_component_library": ("rig_component_library_ir", ("roots", "component_catalogs", "spine_chains", "limb_chains", "digit_chains", "mechanical_joints", "wing_tentacle_chains", "connector_socket_contracts", "ik_fk_templates", "typed_rig_output_slots", "component_cycle_guards")),
    "morph_target_database": ("morph_target_database_ir", ("roots", "morph_target_catalogs", "facial_expression_sets", "viseme_lipsync_sets", "body_shape_deltas", "corrective_shapes", "region_mask_bindings", "delta_vector_channels", "symmetry_mirror_rules", "rig_anatomy_compatibility", "morph_iteration_wear_masks")),
    "animation_library_binding": ("animation_library_binding_ir", ("roots", "clip_catalogs", "pose_libraries", "locomotion_state_sets", "blend_transition_graphs", "event_marker_tracks", "root_motion_channels", "rig_binding_slots", "additive_layer_stacks", "preview_timing_outputs", "animation_iteration_wear_masks")),
    "retargeting_pack": ("retargeting_pack_ir", ("roots", "source_target_skeletons", "bone_mapping_tables", "rest_pose_alignments", "scale_proportion_compensation", "coordinate_space_conversions", "ik_pole_remaps", "root_motion_retargeting", "constraint_limit_transfers", "compatibility_validation_guards", "retarget_iteration_wear_masks")),
    "character_equipment_binding": ("character_equipment_binding_ir", ("roots", "body_slot_maps", "weapon_tool_sockets", "armor_outfit_layers", "attachment_offset_frames", "clearance_collision_volumes", "loadout_variants", "rig_anatomy_binding_rules", "visibility_state_masks", "compatibility_failure_guards", "equipment_iteration_wear_masks")),
    "gameplay_animation_controller": ("gameplay_animation_controller_ir", ("roots", "input_action_maps", "controller_state_graphs", "animation_parameter_sets", "transition_rule_tables", "locomotion_blend_controls", "combat_ability_layers", "event_output_bindings", "motion_matching_slots", "reachability_dead_state_guards", "controller_iteration_wear_masks")),
    "procedural_facial_rig": ("procedural_facial_rig_ir", ("roots", "facial_control_boards", "jaw_mouth_controls", "eye_lid_controls", "brow_cheek_controls", "viseme_expression_links", "morph_driver_bindings", "face_sdf_mask_bindings", "range_limit_guards", "preview_pose_outputs", "facial_rig_iteration_wear_masks")),
    "hair_program": ("hair_program_ir", ("roots", "scalp_groom_regions", "strand_grammars", "root_density_masks", "length_distribution_controls", "wave_curl_controls", "hair_card_outputs", "strand_output_ports", "color_gradient_controls", "collision_clearance_guards", "hair_iteration_wear_masks")),
    "cloth_fabric_simulation": ("cloth_fabric_simulation_ir", ("roots", "fabric_domains", "mass_stiffness_damping_parameters", "pin_anchor_constraints", "collision_body_volumes", "gravity_wind_force_fields", "settling_solve_passes", "wrinkle_fold_outputs", "material_pattern_zones", "solver_validation_guards", "cloth_iteration_wear_masks")),
    "fluid_forward_volume": ("fluid_forward_volume_ir", ("roots", "fluid_volume_domains", "density_temperature_velocity_channels", "emitter_source_sets", "advection_force_fields", "surface_isosurface_controls", "particle_mesh_outputs", "cache_sample_tiles", "collision_boundary_guards", "fluid_style_material_regions", "fluid_iteration_wear_masks")),
    "construction_grammar_kit": ("construction_grammar_kit_ir", ("roots", "module_catalogs", "snap_grids_axes", "connector_socket_rules", "allowed_adjacency_rules", "repeat_split_assembly_rules", "kitbash_variant_slots", "structural_validation_guards", "buildable_output_ports", "scale_metric_markers", "grammar_iteration_wear_masks")),
    "creature_appendage_program": ("creature_appendage_program_ir", ("roots", "appendage_socket_maps", "joint_chain_segments", "segment_profile_controls", "wing_tail_tentacle_variants", "surface_feature_maps", "symmetry_mirror_rules", "articulation_range_controls", "muscle_volume_bands", "attachment_clearance_guards", "appendage_iteration_wear_masks")),
    "body_part_library": ("body_part_library_ir", ("roots", "body_part_catalogs", "anatomy_region_maps", "organ_socket_maps", "muscle_group_volume_bands", "landmark_loop_markers", "proportion_range_controls", "symmetry_pair_rules", "surface_zone_bindings", "compatibility_validation_guards", "body_part_iteration_wear_masks")),
    "material_primitive_library": ("material_primitive_library_ir", ("roots", "material_primitive_catalogs", "physical_substance_taxonomies", "pbr_channel_ranges", "metal_dielectric_emissive_classes", "translucent_material_classes", "procedural_parameter_ports", "smart_mask_bindings", "materialx_output_ports", "pbr_validation_guards", "substance_variant_slots", "material_iteration_wear_masks")),
}


def _compiler_version() -> str:
    imported_version: str | None = None
    try:
        from ... import __version__ as source_version
    except ImportError:
        imported_version = None
    else:
        imported_version = str(source_version)

    if imported_version:
        return imported_version
    try:
        return importlib.metadata.version("lathe")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _resolve_packaged_source(out_dir: Any, uri: Any) -> Any | None:
    try:
        src = safe_resolve(out_dir, str(uri))
    except (PathGuardError, TypeError, ValueError, OSError):
        return None
    return src if src.exists() and src.is_file() else None


def _copy_package_artifact(src: Any, dst: Any) -> None:
    if dst.exists() and dst.resolve() != src.resolve():
        raise FileExistsError(f"package artifact already exists: {dst}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src.read_bytes())


def _resolve_surface_texture_path(executor: Any, surface_bundle: dict[str, Any], map_name: str) -> Path | None:
    outputs = surface_bundle.get("outputs", {})
    if not isinstance(outputs, dict):
        return None
    entry = outputs.get(map_name)
    if not isinstance(entry, dict):
        return None
    uri = entry.get("uri")
    if not uri:
        return None
    try:
        path = safe_resolve(executor.stage_dirs["surface"], str(uri))
    except (PathGuardError, TypeError, ValueError, OSError):
        return None
    return path if path.exists() and path.is_file() else None


def _copy_surface_textures(executor: Any, stage_dir: Path) -> dict[str, Path]:
    surface_bundle = executor.runtime.get("surface", {}).get("bundle", {})
    if not isinstance(surface_bundle, dict):
        return {}
    texture_dir = stage_dir / "textures"
    copied: dict[str, Path] = {}
    for map_name in PBR_TEXTURE_MAPS:
        src = _resolve_surface_texture_path(executor, surface_bundle, map_name)
        if src is None:
            continue
        dst = texture_dir / src.name
        _copy_package_artifact(src, dst)
        copied[map_name] = dst
    return copied


def _open_texture(path: Path, mode: str) -> Image.Image:
    with open_guarded(path) as image:
        return image.convert(mode)


def _build_pbr_material(texture_paths: dict[str, Path]) -> PBRMaterial | None:
    basecolor_path = texture_paths.get("basecolor")
    if basecolor_path is None:
        return None
    return PBRMaterial(
        name="lathe_pbr_atlas",
        baseColorTexture=_open_texture(basecolor_path, "RGBA"),
        normalTexture=_open_texture(texture_paths["normal"], "RGB") if "normal" in texture_paths else None,
        metallicRoughnessTexture=_open_texture(texture_paths["orm"], "RGB") if "orm" in texture_paths else None,
        occlusionTexture=_open_texture(texture_paths["ao"], "RGB") if "ao" in texture_paths else None,
        emissiveTexture=_open_texture(texture_paths["emissive"], "RGB") if "emissive" in texture_paths else None,
        metallicFactor=1.0,
        roughnessFactor=1.0,
    )


def _mesh_with_pbr_textures(mesh: trimesh.Trimesh, texture_paths: dict[str, Path]) -> trimesh.Trimesh:
    uv = getattr(mesh.visual, "uv", None)
    material = _build_pbr_material(texture_paths)
    if material is None or uv is None:
        return mesh
    textured = mesh.copy()
    textured.visual = TextureVisuals(uv=uv.copy(), material=material)
    return textured


def _semantic_ids(values: Any) -> list[str]:
    ids: list[str] = []
    if not isinstance(values, list):
        return ids
    for item in values:
        if isinstance(item, dict):
            item_id = item.get("id") or item.get("name")
            if item_id:
                ids.append(str(item_id))
        elif isinstance(item, str) and item:
            ids.append(item)
    return ids


def _engine_runtime_semantics(execution_bundle: Mapping[str, Any]) -> dict[str, Any]:
    systems: dict[str, Any] = {}
    for system_name, (bundle_key, fields) in _ENGINE_RUNTIME_IR_FIELDS.items():
        ir = execution_bundle.get(bundle_key)
        if not isinstance(ir, dict):
            ir = {}
        counts: dict[str, int] = {}
        ids: dict[str, list[str]] = {}
        for field in fields:
            raw = ir.get(field)
            if isinstance(raw, list):
                counts[field] = len(raw)
                field_ids = _semantic_ids(raw)
                if field_ids:
                    ids[field] = field_ids
            else:
                counts[field] = 0
        active_fields = [field for field, count in counts.items() if count > 0]
        systems[system_name] = {
            "schema": ir.get("schema"),
            "source": ir.get("source", "build.execution"),
            "active": bool(active_fields),
            "active_fields": active_fields,
            "counts": counts,
            "ids": ids,
        }
    return {
        "schema": "lathe.engine_runtime_semantics.v1",
        "systems": systems,
    }


def _game_asset_manifest_requested(package_cfg: dict[str, Any]) -> bool:
    manifests = package_cfg.get("manifests", [])
    if not isinstance(manifests, list):
        manifests = [manifests]
    return bool(package_cfg.get("game_asset_manifest", False)) or "game_asset_manifest" in {
        str(item) for item in manifests
    }


def _dict_value(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list_value(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _list_records(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


def _manifest_key(manifest: Mapping[str, Any]) -> tuple[str, str, str, int, int]:
    return (
        str(manifest.get("program_kind") or ""),
        str(manifest.get("route") or ""),
        str(manifest.get("backend") or ""),
        int(manifest.get("operand_count", 0) or 0),
        int(manifest.get("operation_count", 0) or 0),
    )


def _kernel_program_manifest_from_report(value: Any) -> dict[str, Any]:
    report = _dict_value(value)
    if not report:
        return {}
    direct = _dict_value(report.get("kernel_program_manifest"))
    if direct.get("schema") == "lathe.geometry.kernel_program_manifest.v1":
        return direct
    for key in ("details", "kernel_program", "kernel_program_details"):
        nested = _dict_value(report.get(key))
        direct = _dict_value(nested.get("kernel_program_manifest"))
        if direct.get("schema") == "lathe.geometry.kernel_program_manifest.v1":
            return direct
    if report.get("schema") == "lathe.geometry.kernel_program_manifest.v1":
        return report
    return {}


def _shape_ir_kernel_program_manifests(shape_bundle: Mapping[str, Any]) -> list[dict[str, Any]]:
    selected_shape_ir = shape_bundle.get("selected_shape_ir")
    shape_irs = [selected_shape_ir] if isinstance(selected_shape_ir, Mapping) else (
        shape_bundle.get("shape_ir") or shape_bundle.get("shape_irs") or []
    )
    if isinstance(shape_irs, Mapping):
        shape_irs = [shape_irs]
    if not isinstance(shape_irs, list):
        return []
    manifests: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, int, int]] = set()
    for shape_ir in shape_irs:
        if not isinstance(shape_ir, Mapping):
            continue
        primitives = shape_ir.get("primitives")
        if not isinstance(primitives, list):
            continue
        for primitive in primitives:
            if not isinstance(primitive, Mapping):
                continue
            semantic_metadata = _dict_value(primitive.get("semantic_metadata"))
            v2_metadata = _dict_value(semantic_metadata.get("shape_ir_v2"))
            for modifier_source in (primitive, semantic_metadata, v2_metadata):
                for modifier_name in (
                    "v2_hull_modifier",
                    "v2_minkowski_modifier",
                    "v2_transform_modifier",
                    "v2_copy_to_points_modifier",
                    "v2_surface_scatter_modifier",
                    "v2_distribution_modifier",
                    "v2_mirror_modifier",
                    "v2_repeat_modifier",
                    "v2_fastener_grid_modifier",
                    "v2_vent_slats_modifier",
                    "v2_corner_guard_set_modifier",
                    "v2_trim_band_modifier",
                    "v2_panel_frame_modifier",
                    "v2_socket_modifier",
                    "v2_bracket_modifier",
                    "v2_mount_plate_modifier",
                    "v2_cut_panel_line_modifier",
                    "v2_countersunk_hole_modifier",
                    "v2_rounded_slot_modifier",
                    "v2_weld_seam_modifier",
                    "v2_boolean_modifier",
                    "v2_sop_boolean_modifier",
                    "v2_inset_modifier",
                    "v2_extrude_modifier",
                    "v2_shell_modifier",
                    "v2_sweep_modifier",
                    "v2_polyextrude_modifier",
                    "v2_loft_modifier",
                    "v2_carve_modifier",
                    "v2_polywire_modifier",
                    "v2_helical_sweep_modifier",
                    "v2_deform_modifier",
                    "v2_subdivision_modifier",
                    "v2_remesh_modifier",
                    "v2_polybevel_modifier",
                    "v2_mark_hard_edge_modifier",
                    "v2_weighted_normals_modifier",
                    "v2_scratch_mask_modifier",
                    "v2_dent_mask_modifier",
                    "v2_chip_edges_modifier",
                    "v2_grime_mask_modifier",
                    "v2_prism_modifier",
                    "v2_rail_modifier",
                    "v2_structural_beam_modifier",
                    "v2_ladder_frame_modifier",
                    "v2_truss_frame_modifier",
                    "v2_panel_modifier",
                    "v2_perforated_panel_modifier",
                    "v2_ribbed_panel_modifier",
                    "v2_louver_panel_modifier",
                    "v2_terrain_patch_modifier",
                    "v2_branching_tree_modifier",
                    "v2_sdf_metaball_cluster_modifier",
                    "v2_wfc_modular_assembly_modifier",
                    "v2_cga_facade_modifier",
                    "v2_tube_modifier",
                    "v2_gear_modifier",
                    "v2_capsule_modifier",
                    "v2_flange_modifier",
                    "v2_hinge_modifier",
                    "v2_handle_modifier",
                    "v2_spring_modifier",
                    "v2_curved_tube_modifier",
                    "v2_threaded_cylinder_modifier",
                    "v2_curve_profile_modifier",
                    "v2_curve_sweep_modifier",
                    "v2_curve_loft_modifier",
                ):
                    manifest = _kernel_program_manifest_from_report(modifier_source.get(modifier_name))
                    if not manifest:
                        continue
                    key = _manifest_key(manifest)
                    if key in seen:
                        continue
                    seen.add(key)
                    manifests.append(manifest)
    return manifests


def _dedupe_operation_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for record in records:
        key = (
            str(record.get("operation_id") or ""),
            str(record.get("operation") or ""),
            str(record.get("operand_id") or record.get("primitive_index") or ""),
            str(record.get("source") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(record)
    return out


def _operation_records_from_manifests(manifests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for manifest in manifests:
        records.extend(_list_records(manifest.get("semantic_operation_records")))
    return _dedupe_operation_records(records)


def _selected_shape_candidate(shape_bundle: Mapping[str, Any]) -> dict[str, Any]:
    selected_id = str(shape_bundle.get("selected_candidate_id") or "")
    for candidate in shape_bundle.get("candidates") or []:
        if isinstance(candidate, Mapping) and str(candidate.get("candidate_id") or "") == selected_id:
            return dict(candidate)
    return {}


def _construction_provenance(executor: Any) -> dict[str, Any]:
    shape_bundle = _dict_value((executor.runtime.get("shape") or {}).get("bundle"))
    topology_bundle = _dict_value((executor.runtime.get("topology") or {}).get("bundle"))
    uv_bundle = _dict_value((executor.runtime.get("uv") or {}).get("bundle"))
    surface_bundle = _dict_value((executor.runtime.get("surface") or {}).get("bundle"))
    selected_candidate = _selected_shape_candidate(shape_bundle)
    shape_integration = _dict_value(selected_candidate.get("integration_report"))

    face_operation_summary = (
        _dict_value(surface_bundle.get("face_operation_summary"))
        or _dict_value(uv_bundle.get("face_operation_summary"))
        or _dict_value(topology_bundle.get("face_operation_summary"))
        or _dict_value(_dict_value(selected_candidate.get("mesh_ir")).get("metadata", {})).get("face_operation_summary", {})
    )
    operation_records = (
        _list_records(surface_bundle.get("operation_records"))
        or _list_records(uv_bundle.get("operation_records"))
        or _list_records(topology_bundle.get("operation_records"))
        or _list_records(shape_integration.get("operation_records"))
        or _list_records(shape_integration.get("kernel_program_semantic_operation_records"))
    )
    mesh_ir_metadata = _dict_value(_dict_value(selected_candidate.get("mesh_ir")).get("metadata", {}))
    kernel_feature_details = (
        _list_records(surface_bundle.get("kernel_feature_details"))
        or _list_records(uv_bundle.get("kernel_feature_details"))
        or _list_records(topology_bundle.get("kernel_feature_details"))
        or _list_records(mesh_ir_metadata.get("kernel_feature_details"))
    )
    kernel_edge_treatments = (
        _list_records(surface_bundle.get("kernel_edge_treatments"))
        or _list_records(uv_bundle.get("kernel_edge_treatments"))
        or _list_records(topology_bundle.get("kernel_edge_treatments"))
        or _list_records(mesh_ir_metadata.get("kernel_edge_treatments"))
    )
    kernel_pattern_instances = (
        _list_records(surface_bundle.get("kernel_pattern_instances"))
        or _list_records(uv_bundle.get("kernel_pattern_instances"))
        or _list_records(topology_bundle.get("kernel_pattern_instances"))
        or _list_records(mesh_ir_metadata.get("kernel_pattern_instances"))
    )
    kernel_deforms = (
        _list_records(surface_bundle.get("kernel_deforms"))
        or _list_records(uv_bundle.get("kernel_deforms"))
        or _list_records(topology_bundle.get("kernel_deforms"))
        or _list_records(mesh_ir_metadata.get("kernel_deforms"))
    )
    kernel_profile_paths = (
        _list_records(surface_bundle.get("kernel_profile_paths"))
        or _list_records(uv_bundle.get("kernel_profile_paths"))
        or _list_records(topology_bundle.get("kernel_profile_paths"))
        or _list_records(mesh_ir_metadata.get("kernel_profile_paths"))
    )
    kernel_edge_controls = (
        _list_records(surface_bundle.get("kernel_edge_controls"))
        or _list_records(uv_bundle.get("kernel_edge_controls"))
        or _list_records(topology_bundle.get("kernel_edge_controls"))
        or _list_records(mesh_ir_metadata.get("kernel_edge_controls"))
    )
    kernel_component_assemblies = (
        _list_records(surface_bundle.get("kernel_component_assemblies"))
        or _list_records(uv_bundle.get("kernel_component_assemblies"))
        or _list_records(topology_bundle.get("kernel_component_assemblies"))
        or _list_records(mesh_ir_metadata.get("kernel_component_assemblies"))
    )
    kernel_sdf_fields = (
        _list_records(surface_bundle.get("kernel_sdf_fields"))
        or _list_records(uv_bundle.get("kernel_sdf_fields"))
        or _list_records(topology_bundle.get("kernel_sdf_fields"))
        or _list_records(mesh_ir_metadata.get("kernel_sdf_fields"))
    )
    kernel_terrain_fields = (
        _list_records(surface_bundle.get("kernel_terrain_fields"))
        or _list_records(uv_bundle.get("kernel_terrain_fields"))
        or _list_records(topology_bundle.get("kernel_terrain_fields"))
        or _list_records(mesh_ir_metadata.get("kernel_terrain_fields"))
    )
    kernel_scatters = (
        _list_records(surface_bundle.get("kernel_scatters"))
        or _list_records(uv_bundle.get("kernel_scatters"))
        or _list_records(topology_bundle.get("kernel_scatters"))
        or _list_records(mesh_ir_metadata.get("kernel_scatters"))
    )
    kernel_surface_damage = (
        _list_records(surface_bundle.get("kernel_surface_damage"))
        or _list_records(uv_bundle.get("kernel_surface_damage"))
        or _list_records(topology_bundle.get("kernel_surface_damage"))
        or _list_records(mesh_ir_metadata.get("kernel_surface_damage"))
    )
    semantic_preservation = (
        _dict_value(uv_bundle.get("semantic_preservation"))
        or _dict_value(topology_bundle.get("semantic_preservation"))
    )
    kernel_program_manifest = _dict_value(shape_integration.get("kernel_program_manifest"))
    exact_report = _dict_value(shape_integration.get("exact_report"))
    if not kernel_program_manifest:
        kernel_program_manifest = _dict_value(exact_report.get("kernel_program_manifest"))
    kernel_program_manifests: list[dict[str, Any]] = []
    seen_manifest_keys: set[tuple[str, str, str, int, int]] = set()
    for manifest in [
        kernel_program_manifest,
        *_shape_ir_kernel_program_manifests(shape_bundle),
    ]:
        if not manifest:
            continue
        key = _manifest_key(manifest)
        if key in seen_manifest_keys:
            continue
        seen_manifest_keys.add(key)
        kernel_program_manifests.append(manifest)
    if not kernel_program_manifest and kernel_program_manifests:
        kernel_program_manifest = kernel_program_manifests[0]
    if kernel_program_manifests:
        operation_records = _dedupe_operation_records(
            [
                *operation_records,
                *_operation_records_from_manifests(kernel_program_manifests),
            ]
        )

    provenance: dict[str, Any] = {
        "schema": "lathe.package.construction_provenance.v1",
        "selected_candidate_id": str(shape_bundle.get("selected_candidate_id") or ""),
        "shape_mode": str(shape_integration.get("mode") or ""),
        "search_mode": str(shape_integration.get("search_mode") or ""),
        "geometry_kernel": str(
            shape_integration.get("geometry_kernel")
            or shape_integration.get("boolean_kernel")
            or shape_integration.get("kernel_program_kernel")
            or ""
        ),
        "kernel_program_succeeded": bool(shape_integration.get("kernel_program_succeeded", False)),
        "kernel_program_primary": bool(shape_integration.get("kernel_program_primary", False)),
        "kernel_program_preference_reason": str(
            shape_integration.get("kernel_program_preference_reason") or ""
        ),
        "kernel_program_boolean_fallback_count": int(
            shape_integration.get("kernel_program_boolean_fallback_count", 0) or 0
        ),
        "operation_record_count": len(operation_records),
        "operation_records": operation_records,
        "kernel_feature_detail_count": len(kernel_feature_details),
        "kernel_feature_details": kernel_feature_details,
        "kernel_edge_treatment_count": len(kernel_edge_treatments),
        "kernel_edge_treatments": kernel_edge_treatments,
        "kernel_pattern_instance_count": len(kernel_pattern_instances),
        "kernel_pattern_instances": kernel_pattern_instances,
        "kernel_deform_count": len(kernel_deforms),
        "kernel_deforms": kernel_deforms,
        "kernel_profile_path_count": len(kernel_profile_paths),
        "kernel_profile_paths": kernel_profile_paths,
        "kernel_edge_control_count": len(kernel_edge_controls),
        "kernel_edge_controls": kernel_edge_controls,
        "kernel_component_assembly_count": len(kernel_component_assemblies),
        "kernel_component_assemblies": kernel_component_assemblies,
        "kernel_sdf_field_count": len(kernel_sdf_fields),
        "kernel_sdf_fields": kernel_sdf_fields,
        "kernel_terrain_field_count": len(kernel_terrain_fields),
        "kernel_terrain_fields": kernel_terrain_fields,
        "kernel_scatter_count": len(kernel_scatters),
        "kernel_scatters": kernel_scatters,
        "kernel_surface_damage_count": len(kernel_surface_damage),
        "kernel_surface_damage": kernel_surface_damage,
        "kernel_program_manifest_count": len(kernel_program_manifests),
        "face_operation_summary": dict(face_operation_summary) if isinstance(face_operation_summary, Mapping) else {},
        "semantic_preservation": semantic_preservation,
    }
    kernel_operations = _list_records(shape_integration.get("kernel_program_operations"))
    exact_boolean_records = [
        record
        for record in kernel_operations
        if isinstance(record.get("kernel_exact_boolean"), Mapping)
    ]
    decomposition_records = [
        record
        for record in kernel_operations
        if isinstance(record.get("kernel_boolean_decomposition"), Mapping)
    ]
    if exact_boolean_records:
        provenance["kernel_program_exact_boolean_count"] = len(exact_boolean_records)
        provenance["kernel_program_exact_boolean_records"] = exact_boolean_records
    if decomposition_records:
        provenance["kernel_program_boolean_decomposition_count"] = len(decomposition_records)
        provenance["kernel_program_boolean_decomposition_records"] = decomposition_records
    fallback_records = _list_records(shape_integration.get("kernel_program_boolean_fallback_records"))
    if fallback_records:
        provenance["kernel_program_boolean_fallback_records"] = fallback_records
    if kernel_program_manifest:
        provenance["kernel_program_manifest"] = kernel_program_manifest
    if kernel_program_manifests:
        provenance["kernel_program_manifests"] = kernel_program_manifests
    fallback_reason = (
        shape_integration.get("boolean_fallback_reason")
        or shape_integration.get("kernel_program_failure_reason")
        or shape_integration.get("reason")
    )
    if fallback_reason:
        provenance["fallback_reason"] = str(fallback_reason)
    return provenance


def _build_game_asset_manifest(
    *,
    executor: Any,
    outputs: list[dict[str, Any]],
    optimize_bundle: dict[str, Any],
    texture_outputs: list[dict[str, Any]],
) -> dict[str, Any]:
    surface_bundle = (executor.runtime.get("surface") or {}).get("bundle") or {}
    uv_bundle = (executor.runtime.get("uv") or {}).get("bundle") or {}
    physics_bundle = (executor.runtime.get("physics") or {}).get("bundle") or {}
    interfaces_bundle = (executor.runtime.get("interfaces") or {}).get("bundle") or {}
    execution_bundle = (executor.runtime.get("execution") or {}).get("bundle") or {}
    runtime_semantics = _engine_runtime_semantics(execution_bundle)
    construction_provenance = _construction_provenance(executor)
    texture_conventions = _surface_texture_conventions(surface_bundle, texture_outputs)
    surface_material_semantics = dict(texture_conventions.get("surface_material_semantics") or {})
    return {
        "schema": "lathe.game_asset_manifest.v1",
        "asset_id": executor.asset_name,
        "kind": executor.asset.get("kind"),
        "formats": list(executor.asset.get("package", {}).get("formats", [])),
        "primary_outputs": [
            entry for entry in outputs if entry.get("format") in {"glb", "gltf", "usd", "obj"}
        ],
        "textures": texture_outputs,
        "texture_conventions": texture_conventions,
        "lods": list(optimize_bundle.get("lods") or []),
        "highlow_relation": dict(
            optimize_bundle.get("highlow_relation")
            or surface_bundle.get("highlow_relation")
            or executor.runtime.get("highlow_relation")
            or {}
        ),
        "collision": dict(optimize_bundle.get("collision") or physics_bundle.get("collision", {}) or {}),
        "physics": {
            "body_type": physics_bundle.get("body_type"),
            "joint_policy": physics_bundle.get("joint_policy"),
            "mass_kg": physics_bundle.get("mass_kg"),
            "center_of_mass": physics_bundle.get("center_of_mass"),
            "parts": list(physics_bundle.get("parts") or []),
            "joints": list(physics_bundle.get("joints") or []),
            "constraints": list(physics_bundle.get("constraints") or []),
            "physics_intent": dict(physics_bundle.get("physics_intent") or {}),
        },
        "behavior": dict(execution_bundle.get("behavior_ir") or {}),
        "persistence": dict(execution_bundle.get("persistence_ir") or {}),
        "quest_dialogue": dict(execution_bundle.get("quest_dialogue_ir") or {}),
        "camera_cinematic": dict(execution_bundle.get("camera_cinematic_ir") or {}),
        "audio": dict(execution_bundle.get("audio_ir") or {}),
        "runtime_partition": dict(execution_bundle.get("runtime_partition_ir") or {}),
        "multiplayer_session": dict(execution_bundle.get("multiplayer_session_ir") or {}),
        "localization_text": dict(execution_bundle.get("localization_text_ir") or {}),
        "accessibility_ux": dict(execution_bundle.get("accessibility_ux_ir") or {}),
        "economy_simulation": dict(execution_bundle.get("economy_simulation_ir") or {}),
        "scene_system": dict(execution_bundle.get("scene_system_ir") or {}),
        "procedural_prefab": dict(execution_bundle.get("procedural_prefab_ir") or {}),
        "engine_runtime": dict(execution_bundle.get("engine_runtime_ir") or {}),
        "behavior_logic": dict(execution_bundle.get("behavior_logic_ir") or {}),
        "encounter_flow": dict(execution_bundle.get("encounter_flow_ir") or {}),
        "inventory_economy": dict(execution_bundle.get("inventory_economy_ir") or {}),
        "world_system": dict(execution_bundle.get("world_system_ir") or {}),
        "simulation_environment": dict(execution_bundle.get("simulation_environment_ir") or {}),
        "stateful_destructible": dict(execution_bundle.get("stateful_destructible_ir") or {}),
        "live_procedural_runtime": dict(execution_bundle.get("live_procedural_runtime_ir") or {}),
        "multi_asset_bundle": dict(execution_bundle.get("multi_asset_bundle_ir") or {}),
        "style_stack_visual": dict(execution_bundle.get("style_stack_visual_ir") or {}),
        "cross_domain_composition": dict(execution_bundle.get("cross_domain_composition_ir") or {}),
        "rig_animation_proxy": dict(execution_bundle.get("rig_animation_proxy_ir") or {}),
        "cloth_attachment": dict(execution_bundle.get("cloth_attachment_ir") or {}),
        "domain_kit": dict(execution_bundle.get("domain_kit_ir") or {}),
        "typed_data_kernel": dict(execution_bundle.get("typed_data_kernel_ir") or {}),
        "attribute_surface_graph": dict(execution_bundle.get("attribute_surface_graph_ir") or {}),
        "vegetation_library": dict(execution_bundle.get("vegetation_library_ir") or {}),
        "terrain_heightfield": dict(execution_bundle.get("terrain_heightfield_ir") or {}),
        "wfc_tile_solver": dict(execution_bundle.get("wfc_tile_solver_ir") or {}),
        "cga_building_grammar": dict(execution_bundle.get("cga_building_grammar_ir") or {}),
        "volume_effects_data": dict(execution_bundle.get("volume_effects_data_ir") or {}),
        "instance_pattern_scatter": dict(execution_bundle.get("instance_pattern_scatter_ir") or {}),
        "f_rep_sdf_composition": dict(execution_bundle.get("f_rep_sdf_composition_ir") or {}),
        "subdivision_finishing": dict(execution_bundle.get("subdivision_finishing_ir") or {}),
        "humanoid_anatomy": dict(execution_bundle.get("humanoid_anatomy_ir") or {}),
        "face_sdf_cel_shading": dict(execution_bundle.get("face_sdf_cel_shading_ir") or {}),
        "rig_component_library": dict(execution_bundle.get("rig_component_library_ir") or {}),
        "morph_target_database": dict(execution_bundle.get("morph_target_database_ir") or {}),
        "animation_library_binding": dict(execution_bundle.get("animation_library_binding_ir") or {}),
        "retargeting_pack": dict(execution_bundle.get("retargeting_pack_ir") or {}),
        "character_equipment_binding": dict(execution_bundle.get("character_equipment_binding_ir") or {}),
        "gameplay_animation_controller": dict(execution_bundle.get("gameplay_animation_controller_ir") or {}),
        "procedural_facial_rig": dict(execution_bundle.get("procedural_facial_rig_ir") or {}),
        "hair_program": dict(execution_bundle.get("hair_program_ir") or {}),
        "cloth_fabric_simulation": dict(execution_bundle.get("cloth_fabric_simulation_ir") or {}),
        "fluid_forward_volume": dict(execution_bundle.get("fluid_forward_volume_ir") or {}),
        "construction_grammar_kit": dict(execution_bundle.get("construction_grammar_kit_ir") or {}),
        "creature_appendage_program": dict(execution_bundle.get("creature_appendage_program_ir") or {}),
        "body_part_library": dict(execution_bundle.get("body_part_library_ir") or {}),
        "material_primitive_library": dict(execution_bundle.get("material_primitive_library_ir") or {}),
        "runtime_semantics": runtime_semantics,
        "interfaces": {
            "sockets": list(interfaces_bundle.get("sockets") or []),
            "pivots": list(interfaces_bundle.get("pivots") or []),
            "anchors": list(interfaces_bundle.get("anchors") or []),
            "connections": list(interfaces_bundle.get("connections") or []),
            "connection_slots": list(interfaces_bundle.get("connection_slots") or []),
        },
        "materials": {
            "material_slots": surface_bundle.get("material_slots", 0),
            "material_zones": list(surface_bundle.get("material_zones") or []),
            "material_id_layout": dict(surface_bundle.get("material_id_layout") or {}),
            "surface_material_semantics": surface_material_semantics,
        },
        "surface_material_semantics": surface_material_semantics,
        "uv": {
            "uv_sets": list(uv_bundle.get("uv_sets") or []),
            "packing_report": dict(uv_bundle.get("packing_report") or {}),
            "uv_organization": dict(uv_bundle.get("uv_organization") or {}),
            "chart_manifest": list(uv_bundle.get("chart_manifest") or []),
        },
        "surface_story": dict(surface_bundle.get("surface_story_placement_plan") or {}),
        "construction_provenance": construction_provenance,
        "nested_assets": _nested_assets_for_package(executor),
    }


def _write_game_asset_manifest(
    *,
    executor: Any,
    stage_dir: Path,
    outputs: list[dict[str, Any]],
    optimize_bundle: dict[str, Any],
    texture_outputs: list[dict[str, Any]],
) -> dict[str, Any]:
    manifest = _build_game_asset_manifest(
        executor=executor,
        outputs=outputs,
        optimize_bundle=optimize_bundle,
        texture_outputs=texture_outputs,
    )
    path = stage_dir / "game_asset_manifest.json"
    dump_json(path, manifest)
    return output_entry(executor.out_dir, path, "game_asset_manifest")


def _nested_assets_for_package(executor: Any) -> dict[str, Any]:
    shape_bundle = (executor.runtime.get("shape") or {}).get("bundle") or {}
    asset_graph = shape_bundle.get("asset_graph") if isinstance(shape_bundle, Mapping) else {}
    if isinstance(asset_graph, Mapping):
        authoring = asset_graph.get("authoring") if isinstance(asset_graph.get("authoring"), Mapping) else {}
        nested_assets = nested_asset_manifest_for_signature(authoring.get("nested_assets"))
        if nested_assets.get("summary", {}).get("nested_asset_count"):
            return nested_assets
    selected_shape_ir = shape_bundle.get("selected_shape_ir") if isinstance(shape_bundle, Mapping) else None
    shape_irs = [selected_shape_ir] if isinstance(selected_shape_ir, Mapping) else (
        shape_bundle.get("shape_ir", []) if isinstance(shape_bundle, Mapping) else []
    )
    for item in shape_irs:
        if not isinstance(item, Mapping):
            continue
        signature = item.get("signature") if isinstance(item.get("signature"), Mapping) else {}
        nested_assets = nested_asset_manifest_for_signature(signature.get("nested_assets"))
        if nested_assets.get("summary", {}).get("nested_asset_count"):
            return nested_assets
    return {}


def run(executor: Any, optimize_bundle: dict[str, Any], validate_bundle: dict[str, Any]) -> dict[str, Any]:
    """Run.

    Args:
        executor: executor argument.
        optimize_bundle: optimize_bundle argument.
        validate_bundle: validate_bundle argument.

    Returns:
        The result.
    """
    stage_dir = executor.stage_dirs["package"]
    package_cfg = executor.asset["package"]
    optimize_runtime: RuntimeMesh = executor.runtime["optimize"]["runtime_mesh"]
    mesh = optimize_runtime.mesh.copy()
    texture_paths = _copy_surface_textures(executor, stage_dir)
    package_mesh = _mesh_with_pbr_textures(mesh, texture_paths)
    outputs: list[dict[str, Any]] = []
    if "usd" in package_cfg.get("formats", []):
        usd_path = stage_dir / f"{executor.asset_name}.usda"
        write_usda(mesh, usd_path, asset_name=executor.asset_name)
        outputs.append(output_entry(executor.out_dir, usd_path, "usd"))
    if "glb" in package_cfg.get("formats", []):
        glb_path = stage_dir / f"{executor.asset_name}.glb"
        # When the runtime mesh carries aligned face_parts and the scene
        # is genuinely multi-part, emit a glTF node hierarchy with one
        # named node per part so engine importers (Unity glTFast,
        # Godot native glTF, Unreal) unpack the asset into a child
        # GameObject/Node/Actor tree. The shared atlas PBR material (if
        # available) is applied to every part — they all index into the
        # same UV atlas already authored by the UV stage. When no PBR
        # textures are present we still emit the scene structure so the
        # part hierarchy survives the import; engines fall back to a
        # default material per node.
        face_parts = list(getattr(optimize_runtime, "face_parts", []) or [])
        material = _build_pbr_material(texture_paths)
        multi_part = (
            len(face_parts) == len(mesh.faces)
            and len({p for p in face_parts if p}) > 1
        )
        if multi_part:
            scene_runtime = RuntimeMesh(
                mesh=mesh,
                face_parts=face_parts,
                part_colors=dict(getattr(optimize_runtime, "part_colors", {}) or {}),
                units=getattr(optimize_runtime, "units", "cm"),
            )
            if material is not None and getattr(mesh.visual, "uv", None) is not None:
                # Reattach UV+material on the parent so per-part submesh()
                # calls in the helper inherit the UV channel deterministically.
                scene_runtime.mesh.visual = TextureVisuals(
                    uv=mesh.visual.uv.copy(), material=material
                )
                export_runtime_scene_glb_with_pbr(scene_runtime, glb_path, material)
            else:
                export_runtime_scene_glb(scene_runtime, glb_path)
        else:
            export_glb(package_mesh, glb_path)
        outputs.append(output_entry(executor.out_dir, glb_path, "glb"))
    if "gltf" in package_cfg.get("formats", []):
        gltf_paths = export_gltf(package_mesh, stage_dir, executor.asset_name)
        for path in gltf_paths:
            outputs.append(
                output_entry(executor.out_dir, path, "gltf" if path.suffix == ".gltf" else "gltf_resource")
            )
    if "obj" in package_cfg.get("formats", []):
        obj_path = stage_dir / f"{executor.asset_name}.obj"
        export_obj(mesh, obj_path)
        outputs.append(output_entry(executor.out_dir, obj_path, "obj"))

    # Copy LOD + collision artifacts into the packaged asset dir so they live
    # alongside the main glb as the shipping asset package.
    optimize_bundle_local = executor.runtime.get("optimize", {}).get("bundle", optimize_bundle)
    for entry in optimize_bundle_local.get("lods") or []:
        src_uri = entry.get("mesh_uri")
        if not src_uri:
            continue
        src = _resolve_packaged_source(executor.out_dir, src_uri)
        if src is None:
            continue
        dst = stage_dir / src.name
        _copy_package_artifact(src, dst)
        outputs.append(output_entry(executor.out_dir, dst, "lod_glb"))
    collision_info = optimize_bundle_local.get("collision") or {}
    for kind_key, kind_name in (("hull_uri", "collision_hull"), ("parts_uri", "collision_parts")):
        src_rel = collision_info.get(kind_key)
        if not src_rel:
            continue
        src = _resolve_packaged_source(executor.out_dir, src_rel)
        if src is None:
            continue
        dst = stage_dir / src.name
        _copy_package_artifact(src, dst)
        outputs.append(output_entry(executor.out_dir, dst, kind_name))

    texture_outputs = [
        output_entry(executor.out_dir, path, f"{map_name}_texture")
        for map_name, path in texture_paths.items()
    ]
    outputs.extend(texture_outputs)
    game_asset_manifest_entry = None
    if _game_asset_manifest_requested(package_cfg):
        game_asset_manifest_entry = _write_game_asset_manifest(
            executor=executor,
            stage_dir=stage_dir,
            outputs=outputs,
            optimize_bundle=optimize_bundle_local,
            texture_outputs=texture_outputs,
        )
        outputs.append(game_asset_manifest_entry)

    # STAGE-10: engine-specific manifests (godot/unity/unreal). Emitted at the
    # executor.out_dir root — NOT inside stages/package/ — so they sit next to
    # the copied lod_{0..3}.glb + collision_*.glb / main <asset>.glb bundle
    # that engine importers actually consume. Only runs on glb-packaged builds
    # (engine importers expect a glb alongside).
    engine_manifest_entries: dict[str, Any] = {}
    if "glb" in package_cfg.get("formats", []):
        engine_context = _build_engine_context(
            executor=executor,
            outputs=outputs,
            optimize_bundle=optimize_bundle_local,
            texture_outputs=texture_outputs,
        )
        for engine_id, emit_fn in _ENGINE_ADAPTERS.items():
            payload: str | None = None
            try:
                payload = emit_fn(engine_context, executor.asset_name)
            except Exception as exc:
                warnings.warn(
                    f"{engine_id} engine manifest could not be written for asset "
                    f"'{executor.asset_name}': {exc}",
                    stacklevel=2,
                )
            if payload is None:
                continue
            filename = _engine_manifest_filename(engine_id, executor.asset_name)
            target = executor.out_dir / filename
            target.write_text(payload, encoding="utf-8")
            import hashlib as _hashlib

            engine_manifest_entries[engine_id] = {
                "path": relpath(executor.out_dir, target),
                "sha256": _hashlib.sha256(payload.encode("utf-8")).hexdigest(),
                "format": "yaml" if filename.endswith(".yaml") else "json",
            }

    previews = []
    preview_dir = stage_dir / "previews"
    preview_dir.mkdir(exist_ok=True)
    requested_previews = package_cfg.get("previews", [])
    if "turntable" in requested_previews:
        path = preview_dir / "turntable.png"
        render_mesh_preview(optimize_runtime, path, mode="shaded")
        previews.append(relpath(executor.out_dir, path))
    if "wireframe" in requested_previews:
        path = preview_dir / "wireframe.png"
        render_mesh_preview(optimize_runtime, path, mode="wireframe")
        previews.append(relpath(executor.out_dir, path))
    if "material_ids" in requested_previews:
        path = preview_dir / "material_ids.png"
        render_mesh_preview(optimize_runtime, path, mode="material_ids")
        previews.append(relpath(executor.out_dir, path))
    if "uv_layout" in requested_previews:
        path = preview_dir / "uv_layout.png"
        render_uv_layout(executor.runtime["uv"]["runtime_mesh"], path)
        previews.append(relpath(executor.out_dir, path))
    if "collision" in requested_previews:
        path = preview_dir / "collision.png"
        collision_mesh = RuntimeMesh(
            mesh=executor.runtime["physics"]["collision_mesh"],
            face_parts=["collision"] * len(executor.runtime["physics"]["collision_mesh"].faces),
            part_colors={"collision": (220, 92, 60)},
            units="cm",
        )
        render_mesh_preview(collision_mesh, path, mode="wireframe")
        previews.append(relpath(executor.out_dir, path))
    if "lod_sheet" in requested_previews:
        path = preview_dir / "lod_sheet.png"
        render_lod_sheet(optimize_runtime, len(optimize_bundle["lods"]), path)
        previews.append(relpath(executor.out_dir, path))

    construction_provenance = _construction_provenance(executor)
    visual_quality_gate = _package_visual_quality_gate(validate_bundle, previews)
    manifest = {
        "asset_id": executor.asset_name,
        "kind": executor.asset["kind"],
        "contracts": list(executor.asset.get("uses", [])),
        "profiles": executor._resolved_profile_names(),
        "version": executor.asset["publish"].get("version"),
        "formats": list(package_cfg.get("formats", [])),
        "outputs": outputs,
        "output_hashes": {entry["uri"]: entry["sha256"] for entry in outputs},
        "textures": texture_outputs,
        "previews": previews,
        "visual_quality_gate": visual_quality_gate,
        "trace_path": None,
        "normalized_source_path": relpath(executor.out_dir, executor.normalized_asset_path),
        "construction_provenance": construction_provenance,
        "build_timestamp": None,
    }
    if game_asset_manifest_entry is not None:
        manifest["game_asset_manifest_path"] = game_asset_manifest_entry["uri"]
    nested_assets = _nested_assets_for_package(executor)
    if nested_assets:
        manifest["nested_assets"] = nested_assets
    trace_path = None
    if package_cfg.get("include_trace", True):
        trace_path = stage_dir / "trace_manifest.json"
        trace = redact_secrets(_build_trace(executor, outputs, previews, validate_bundle))
        dump_json(trace_path, trace)
        manifest["trace_path"] = relpath(executor.out_dir, trace_path)
    manifest_path = stage_dir / "package_manifest.json"
    dump_json(manifest_path, manifest)
    bundle = {
        "backend_id": executor.selected_backends["package"]["id"],
        "outputs": outputs,
        "manifest_path": relpath(executor.out_dir, manifest_path),
        "trace_path": relpath(executor.out_dir, trace_path) if trace_path else None,
        "normalized_source_path": relpath(executor.out_dir, executor.normalized_asset_path),
        "previews": previews,
        "visual_quality_gate": visual_quality_gate,
        "textures": texture_outputs,
        "engine_manifests": engine_manifest_entries,
    }
    if nested_assets:
        bundle["nested_assets"] = nested_assets
    if game_asset_manifest_entry is not None:
        bundle["game_asset_manifest_path"] = game_asset_manifest_entry["uri"]
    executor.runtime["package"] = {"bundle": bundle}
    dump_json(stage_dir / "bundle.json", bundle)
    selector_manifest_path = _write_selector_manifest(executor, validate_bundle)
    if selector_manifest_path is not None:
        bundle["selector_manifest_path"] = relpath(executor.out_dir, selector_manifest_path)
        dump_json(stage_dir / "bundle.json", bundle)
    return bundle


def _build_engine_context(
    *,
    executor: Any,
    outputs: list[dict[str, Any]],
    optimize_bundle: dict[str, Any],
    texture_outputs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assemble the small context dict passed to each engine adapter.

    Keeps adapter inputs free of executor-specific types — every value is
    JSON-serialisable. Resolves the main glb uri from ``outputs``.
    """
    main_glb = next(
        (entry.get("uri") for entry in outputs if entry.get("format") == "glb"),
        None,
    )
    lods_ctx: list[dict[str, Any]] = []
    for lod in optimize_bundle.get("lods") or []:
        if not isinstance(lod, dict):
            continue
        name = str(lod.get("name") or "lod0")
        try:
            level = int(name.replace("lod", ""))
        except (TypeError, ValueError):
            level = 0
        lods_ctx.append(
            {
                "level": level,
                "mesh_uri": lod.get("mesh_uri"),
                "triangle_count": lod.get("triangle_count"),
                "distance_min": lod.get("distance_min"),
                "distance_max": lod.get("distance_max"),
                "screen_coverage": lod.get("screen_coverage"),
            }
        )
    interfaces = (executor.runtime.get("interfaces") or {}).get("bundle") or {}
    sockets = [
        {
            "id": sock.get("id") or sock.get("name"),
            "origin": sock.get("origin") or sock.get("position") or [0.0, 0.0, 0.0],
            "axis": sock.get("axis") or [0.0, 1.0, 0.0],
            "socket_type": sock.get("socket_type") or sock.get("socketType") or sock.get("kind") or "attach",
            "kind": sock.get("kind"),
            "parent_part_id": sock.get("parent_part_id") or sock.get("parentPartId"),
        }
        for sock in interfaces.get("sockets", []) or []
        if isinstance(sock, dict) and (sock.get("id") or sock.get("name"))
    ]
    pivots = [
        {
            "id": piv.get("id") or piv.get("name"),
            "origin": piv.get("origin") or piv.get("position") or [0.0, 0.0, 0.0],
            "axis": piv.get("axis") or [0.0, 1.0, 0.0],
            "pivot_type": piv.get("pivot_type") or piv.get("pivotType") or "center",
        }
        for piv in interfaces.get("pivots", []) or []
        if isinstance(piv, dict) and (piv.get("id") or piv.get("name"))
    ]
    connections = [
        {
            "id": conn.get("id"),
            "source": conn.get("source"),
            "target": conn.get("target"),
            "relation": conn.get("relation"),
            "source_role": conn.get("source_role"),
            "target_role": conn.get("target_role"),
            "compatible": conn.get("compatible", True),
            "compatibility_score": conn.get("compatibility_score"),
        }
        for conn in interfaces.get("connections", []) or []
        if isinstance(conn, dict) and conn.get("id") and conn.get("source")
    ]
    collisions: list[dict[str, Any]] = []
    collision_info = optimize_bundle.get("collision") or {}
    if collision_info.get("hull_uri"):
        collisions.append(
            {
                "id": "hull",
                "kind": "hull",
                "uri": collision_info.get("hull_uri"),
                "parent_part_id": None,
            }
        )
    if collision_info.get("parts_uri"):
        collisions.append(
            {
                "id": "parts",
                "kind": "hull",
                "uri": collision_info.get("parts_uri"),
                "parent_part_id": None,
            }
        )
    surface = (executor.runtime.get("surface") or {}).get("bundle") or {}
    texture_conventions = _surface_texture_conventions(surface, texture_outputs or [])
    surface_material_semantics = dict(texture_conventions.get("surface_material_semantics") or {})
    physics = (executor.runtime.get("physics") or {}).get("bundle") or {}
    execution = (executor.runtime.get("execution") or {}).get("bundle") or {}
    runtime_semantics = _engine_runtime_semantics(execution)
    construction_provenance = _construction_provenance(executor)
    mats_raw = surface.get("materials") or []
    materials: list[dict[str, Any]] = []
    if isinstance(mats_raw, list) and mats_raw:
        for mat in mats_raw:
            if not isinstance(mat, dict):
                continue
            mid = mat.get("id") or mat.get("name")
            if not mid:
                continue
            materials.append(
                {
                    "id": str(mid),
                    "display_name": mat.get("display_name") or mat.get("displayName") or str(mid),
                }
            )
    if not materials:
        # Fall back to material_zones.
        seen: set[str] = set()
        for zone in surface.get("material_zones", []) or []:
            if not isinstance(zone, dict):
                continue
            name = zone.get("material") or zone.get("name")
            if not isinstance(name, str) or not name or name in seen:
                continue
            seen.add(name)
            materials.append({"id": name, "display_name": name})
    publish = executor.asset.get("publish") or {}
    raw_tags = publish.get("tags") or []
    from ...selector_manifest import GAMEPLAY_TAG_CATALOG

    gameplay_tags = [t for t in raw_tags if isinstance(t, str) and t in GAMEPLAY_TAG_CATALOG]
    return {
        "main_glb_uri": main_glb,
        "lods": lods_ctx,
        "sockets": sockets,
        "pivots": pivots,
        "connections": connections,
        "collisions": collisions,
        "physics": {
            "body_type": physics.get("body_type"),
            "joint_policy": physics.get("joint_policy"),
            "mass_kg": physics.get("mass_kg"),
            "center_of_mass": physics.get("center_of_mass"),
            "parts": list(physics.get("parts") or []),
            "joints": list(physics.get("joints") or []),
            "constraints": list(physics.get("constraints") or []),
        },
        "behavior": dict(execution.get("behavior_ir") or {}),
        "persistence": dict(execution.get("persistence_ir") or {}),
        "quest_dialogue": dict(execution.get("quest_dialogue_ir") or {}),
        "camera_cinematic": dict(execution.get("camera_cinematic_ir") or {}),
        "audio": dict(execution.get("audio_ir") or {}),
        "runtime_partition": dict(execution.get("runtime_partition_ir") or {}),
        "multiplayer_session": dict(execution.get("multiplayer_session_ir") or {}),
        "localization_text": dict(execution.get("localization_text_ir") or {}),
        "accessibility_ux": dict(execution.get("accessibility_ux_ir") or {}),
        "economy_simulation": dict(execution.get("economy_simulation_ir") or {}),
        "scene_system": dict(execution.get("scene_system_ir") or {}),
        "procedural_prefab": dict(execution.get("procedural_prefab_ir") or {}),
        "engine_runtime": dict(execution.get("engine_runtime_ir") or {}),
        "behavior_logic": dict(execution.get("behavior_logic_ir") or {}),
        "encounter_flow": dict(execution.get("encounter_flow_ir") or {}),
        "inventory_economy": dict(execution.get("inventory_economy_ir") or {}),
        "world_system": dict(execution.get("world_system_ir") or {}),
        "simulation_environment": dict(execution.get("simulation_environment_ir") or {}),
        "stateful_destructible": dict(execution.get("stateful_destructible_ir") or {}),
        "live_procedural_runtime": dict(execution.get("live_procedural_runtime_ir") or {}),
        "multi_asset_bundle": dict(execution.get("multi_asset_bundle_ir") or {}),
        "style_stack_visual": dict(execution.get("style_stack_visual_ir") or {}),
        "cross_domain_composition": dict(execution.get("cross_domain_composition_ir") or {}),
        "rig_animation_proxy": dict(execution.get("rig_animation_proxy_ir") or {}),
        "cloth_attachment": dict(execution.get("cloth_attachment_ir") or {}),
        "domain_kit": dict(execution.get("domain_kit_ir") or {}),
        "typed_data_kernel": dict(execution.get("typed_data_kernel_ir") or {}),
        "attribute_surface_graph": dict(execution.get("attribute_surface_graph_ir") or {}),
        "vegetation_library": dict(execution.get("vegetation_library_ir") or {}),
        "terrain_heightfield": dict(execution.get("terrain_heightfield_ir") or {}),
        "wfc_tile_solver": dict(execution.get("wfc_tile_solver_ir") or {}),
        "cga_building_grammar": dict(execution.get("cga_building_grammar_ir") or {}),
        "volume_effects_data": dict(execution.get("volume_effects_data_ir") or {}),
        "instance_pattern_scatter": dict(execution.get("instance_pattern_scatter_ir") or {}),
        "f_rep_sdf_composition": dict(execution.get("f_rep_sdf_composition_ir") or {}),
        "subdivision_finishing": dict(execution.get("subdivision_finishing_ir") or {}),
        "humanoid_anatomy": dict(execution.get("humanoid_anatomy_ir") or {}),
        "face_sdf_cel_shading": dict(execution.get("face_sdf_cel_shading_ir") or {}),
        "rig_component_library": dict(execution.get("rig_component_library_ir") or {}),
        "morph_target_database": dict(execution.get("morph_target_database_ir") or {}),
        "animation_library_binding": dict(execution.get("animation_library_binding_ir") or {}),
        "retargeting_pack": dict(execution.get("retargeting_pack_ir") or {}),
        "character_equipment_binding": dict(execution.get("character_equipment_binding_ir") or {}),
        "gameplay_animation_controller": dict(execution.get("gameplay_animation_controller_ir") or {}),
        "procedural_facial_rig": dict(execution.get("procedural_facial_rig_ir") or {}),
        "hair_program": dict(execution.get("hair_program_ir") or {}),
        "cloth_fabric_simulation": dict(execution.get("cloth_fabric_simulation_ir") or {}),
        "fluid_forward_volume": dict(execution.get("fluid_forward_volume_ir") or {}),
        "construction_grammar_kit": dict(execution.get("construction_grammar_kit_ir") or {}),
        "creature_appendage_program": dict(execution.get("creature_appendage_program_ir") or {}),
        "body_part_library": dict(execution.get("body_part_library_ir") or {}),
        "material_primitive_library": dict(execution.get("material_primitive_library_ir") or {}),
        "runtime_semantics": runtime_semantics,
        "construction_provenance": construction_provenance,
        "materials": materials,
        "surface_material_semantics": surface_material_semantics,
        "textures": list(texture_conventions.get("textures") or []),
        "texture_conventions": texture_conventions,
        "gameplay_tags": gameplay_tags,
    }


def _write_selector_manifest(executor: Any, validate_bundle: dict[str, Any]) -> Any:
    """Assemble + write ``selector_manifest.json`` alongside the build outputs.

    Selector manifests are part of the packaged artifact contract. A schema/IO
    failure must fail the package stage instead of returning a success-shaped
    build without the downstream selection artifact.
    """
    try:
        source_path = executor.program.get("_source_path") or ""
        variant_name = None
        asset_name = executor.asset_name
        for variant in executor.program.get("variants", []) or []:
            if variant.get("name") == asset_name:
                variant_name = asset_name
                break
        manifest = build_selector_manifest(
            asset_name=asset_name,
            variant_name=variant_name,
            source_path=source_path,
            build_hash=executor.cache_key,
            runtime=executor.runtime,
            validate_report=validate_bundle,
            asset=executor.asset,
            build_dir=executor.out_dir,
            repo_root=None,
        )
        return write_selector_manifest(manifest, executor.out_dir)
    except Exception as exc:
        message = f"selector_manifest.json could not be written for asset '{executor.asset_name}': {exc}"
        diagnostics = [
            {
                "code": "LPKG_SELECTOR_MANIFEST_WRITE_FAILED",
                "severity": "error",
                "phase": "package",
                "asset": executor.asset_name,
                "stage": "package",
                "path": "selector_manifest.json",
                "message": message,
            }
        ]
        raise BuildError(message, diagnostics) from exc


def _build_trace(
    executor: Any, outputs: list[dict[str, Any]], previews: list[str], validate_bundle: dict[str, Any]
) -> dict[str, Any]:
    refs = []
    for group_name, group_values in executor.asset.get("refs", {}).items():
        if not isinstance(group_values, list):
            continue
        for value in group_values:
            refs.append(
                {
                    "group": group_name,
                    "value": value,
                    "sha256": hash_ref(value),
                }
            )
    return {
        "asset_id": executor.asset_name,
        "source_hash": hash_obj(executor.program),
        "normalized_hash": hash_obj(executor.normalized_program),
        "compiler_version": _compiler_version(),
        "backend_versions": {
            stage: data["id"] + "@" + data["version"] for stage, data in executor.selected_backends.items()
        },
        "determinism_by_stage": {
            stage: data["determinism_class"] for stage, data in executor.selected_backends.items()
        },
        "refs_with_hashes": refs,
        "uses": list(executor.asset.get("uses", [])),
        "stage_configs": {
            "shape": executor.asset["build"]["shape"],
            "topology": executor.asset["build"]["topology"],
            "uv": executor.asset["build"]["uv"],
            "surface": executor.asset["build"]["surface"],
            "execution": executor.asset.get("execution", {}),
            "rig": executor.asset["build"]["rig"],
            "interfaces": executor.asset["build"]["interfaces"],
            "physics": executor.asset["build"]["physics"],
            "optimize": executor.asset["build"]["optimize"],
            "package": executor.asset["package"],
            "publish": executor.asset["publish"],
        },
        "stage_outputs": {
            stage: relpath(
                executor.out_dir,
                executor.stage_dirs[stage] / ("report.json" if stage == "validate" else "bundle.json"),
            )
            for stage in STAGE_ORDER_FOR_TRACE
        },
        "stage_execution": {
            "shape": {
                "provider_report": executor.runtime["shape"]["bundle"].get("provider_report"),
                "blueprint_id": executor.runtime["shape"]["bundle"].get("blueprint_id"),
                "primitives_used": executor.runtime["shape"]["bundle"].get("primitives_used", []),
                "proposal_sources_attempted": executor.runtime["shape"]["bundle"].get(
                    "proposal_sources_attempted", []
                ),
                "proposal_sources_used": executor.runtime["shape"]["bundle"].get("proposal_sources_used", []),
                "accepted_deltas": executor.runtime["shape"]["bundle"].get("accepted_deltas", []),
                "rejected_deltas": executor.runtime["shape"]["bundle"].get("rejected_deltas", []),
                "conformance_failures": executor.runtime["shape"]["bundle"].get("conformance_failures", []),
                "authoritative_candidate_reason": executor.runtime["shape"]["bundle"].get(
                    "authoritative_candidate_reason"
                ),
                "shape_assessment": executor.runtime["shape"]["bundle"].get("shape_assessment", {}),
                "reference_ir": executor.runtime["shape"]["bundle"].get("reference_ir", {}),
                "fit_ir": executor.runtime["shape"]["bundle"].get("fit_ir", {}),
                "transfer_ir": executor.runtime["shape"]["bundle"].get("transfer_ir", {}),
                "kit_ir": executor.runtime["shape"]["bundle"].get("kit_ir", {}),
            },
            "topology": executor.runtime["topology"]["bundle"].get("adapter_report"),
            "uv": executor.runtime["uv"]["bundle"].get("adapter_report"),
            "surface": {
                "surface_backend_report": executor.runtime["surface"]["bundle"].get(
                    "surface_backend_report", {}
                ),
                "surface_control_pack": executor.runtime["surface"]["bundle"].get("surface_control_pack", {}),
                "codex_imagegen_requests": executor.runtime["surface"]["bundle"].get(
                    "codex_imagegen_requests", {}
                ),
                "codex_imagegen_outputs": executor.runtime["surface"]["bundle"].get(
                    "codex_imagegen_outputs", {}
                ),
                "atlas_assembly_ir": executor.runtime["surface"]["bundle"].get("atlas_assembly_ir", {}),
                "surface_validation_ir": executor.runtime["surface"]["bundle"].get(
                    "surface_validation_ir", {}
                ),
                "surface_repair_ir": executor.runtime["surface"]["bundle"].get("surface_repair_ir", {}),
            },
            "execution": executor.runtime.get("execution", {}).get("bundle", {}),
            "flow_quality": executor.runtime.get("flow_quality", {}),
            "package": {"adapter": "reference_package"},
        },
        "candidate_selection": executor.runtime["shape"]["bundle"],
        "repairs_applied": executor.runtime["validate"]["bundle"].get("semantic_repairs_applied", []),
        "diagnostics": validate_bundle["diagnostics"],
        "package_outputs": outputs,
        "previews": previews,
        "approval_state": "pending_required_approval"
        if executor.asset["publish"].get("approval") == "required"
        else "not_required",
    }
