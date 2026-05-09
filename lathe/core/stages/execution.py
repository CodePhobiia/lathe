"""Execution stage step body (Blender plan invocation).

Extracted from ``lathe/executor.py`` during Stage 2.IV. Delegates to the
existing ``lathe.blender_execution.build_execution_bundle``, which is the
canonical site for Blender subprocess management (already hardened in
commit f9de43c).
"""

from __future__ import annotations

from typing import Any

from ...blender_execution import build_execution_bundle
from ..common import dump_json

_MAX_AUTHORED_BEHAVIOR_VALUES = 64


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _iter_text_fragments(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        fragments: list[str] = []
        for item in value.values():
            fragments.extend(_iter_text_fragments(item))
        return fragments
    if isinstance(value, (list, tuple, set)):
        fragments = []
        for item in value:
            fragments.extend(_iter_text_fragments(item))
        return fragments
    text = str(value).strip()
    return [text] if text else []


def _slug_fragment(value: Any, fallback: str = "behavior") -> str:
    text = str(value or "").lower()
    chars: list[str] = []
    previous_was_separator = False
    for char in text:
        if char.isalnum():
            chars.append(char)
            previous_was_separator = False
            continue
        if not previous_was_separator:
            chars.append("_")
            previous_was_separator = True
    slug = "".join(chars).strip("_")
    return slug[:56] if slug else fallback


def _token(value: Any) -> str:
    return _slug_fragment(value, "")


def _contains_any(token: str, words: tuple[str, ...]) -> bool:
    normalized = f" {token.replace('_', ' ')} "
    return any(f" {word.replace('_', ' ')} " in normalized for word in words)


def _authored_behavior_texts(asset: dict[str, Any]) -> list[dict[str, str]]:
    sources = [
        ("asset.name", asset.get("name")),
        ("asset.kind", asset.get("kind")),
        ("intent.role", asset.get("intent", {}).get("role")),
        ("intent.parts", asset.get("intent", {}).get("parts")),
        ("intent.interactions", asset.get("intent", {}).get("interactions")),
        ("assembly.components", asset.get("assembly", {}).get("components")),
        ("assembly.mechanisms", asset.get("assembly", {}).get("mechanisms")),
        ("assembly.traits", asset.get("assembly", {}).get("traits")),
        ("features.allow", asset.get("features", {}).get("allow")),
        ("publish.tags", asset.get("publish", {}).get("tags")),
        ("execution", asset.get("execution")),
    ]
    entries: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for path, value in sources:
        for fragment in _iter_text_fragments(value):
            slug = _slug_fragment(fragment)
            key = (path, slug)
            if key in seen:
                continue
            seen.add(key)
            entries.append({"source_path": path, "source_value": fragment, "slug": slug})
            if len(entries) >= _MAX_AUTHORED_BEHAVIOR_VALUES:
                return entries
    return entries


def _action_kind(source_value: str) -> str | None:
    token = _token(source_value)
    if _contains_any(token, ("fire", "shoot", "muzzle", "projectile", "trigger")):
        return "fire"
    if _contains_any(token, ("reload", "magazine", "cartridge", "ammo")):
        return "reload"
    if _contains_any(token, ("open", "close", "door", "gate", "hinge")):
        return "open_close"
    if _contains_any(token, ("toggle", "switch", "button", "lever", "activate", "deactivate")):
        return "toggle"
    if _contains_any(token, ("pickup", "pick_up", "grab", "grip", "hold", "carry")):
        return "pickup"
    if _contains_any(token, ("inspect", "examine", "read", "scan", "look")):
        return "inspect"
    if _contains_any(token, ("use", "usable", "interact", "terminal", "control_panel")):
        return "use"
    if _contains_any(token, ("cloth_attachment", "cloth_panel", "cloth", "fabric", "garment", "cape", "cloak", "banner", "flag", "tether", "strap")):
        return "cloth_attachment"
    if _contains_any(token, ("mount", "attach", "dock", "snap", "connect", "socket", "plug", "port")):
        return "connect"
    if _contains_any(token, ("drive", "steer", "vehicle", "car", "truck", "tank", "wheel")):
        return "drive"
    if _contains_any(token, ("sail", "boat", "ship", "hull", "rudder", "propeller", "float")):
        return "navigate_water"
    if _contains_any(token, ("slide", "rail", "track", "drawer")):
        return "slide"
    if _contains_any(token, ("rotate", "turn", "wheel", "axle", "turret", "propeller")):
        return "rotate"
    if _contains_any(token, ("stateful_destructible", "damage_state", "fracture", "health", "cracked", "ruined")):
        return "destructible_state"
    if _contains_any(token, ("break", "breakable", "destructible", "damage", "destroy", "debris")):
        return "damage"
    if _contains_any(token, ("repair", "heal", "restore", "fix")):
        return "repair"
    if _contains_any(token, ("quest", "objective", "marker", "reward", "loot")):
        return "quest_signal"
    if _contains_any(token, ("dialogue", "conversation", "talk", "npc", "speaker", "choice", "response")):
        return "dialogue"
    if _contains_any(token, ("camera", "shot", "cutscene", "cinematic", "focus_pull", "look_at", "presentation")):
        return "camera_direct"
    if _contains_any(token, ("audio", "sound", "music", "stinger", "foley", "ambience", "ambient", "reverb", "listener")):
        return "audio_cue"
    if _contains_any(token, ("localization", "text_table", "string_table", "translation", "locale", "subtitle", "voiceover", "glyph")):
        return "localize"
    if _contains_any(token, ("accessibility", "input_remap", "readability", "contrast", "caption", "haptic", "focus_navigation", "screen_reader", "option_panel")):
        return "accessibility"
    if _contains_any(token, ("economy", "simulation_tuning", "resource_flow", "currency", "price", "market", "progression", "spawn_rate", "telemetry_tuning")):
        return "economy_tick"
    if _contains_any(token, ("behavior_logic", "behavior_graph", "logic_graph", "state_logic", "event_action", "condition_rule", "blackboard", "behavior_tree", "utility_ai", "scriptless_behavior")):
        return "behavior_logic"
    if _contains_any(token, ("encounter", "arena", "combat", "wave", "patrol", "cover", "ambush", "boss")):
        return "encounter_flow"
    if _contains_any(token, ("inventory", "shop", "vendor", "stash", "container", "collectible", "rarity", "storage_slot", "resource_port")):
        return "inventory_object"
    if _contains_any(token, ("multi_asset", "asset_bundle", "scene_bundle", "asset_collection", "bundle_manifest", "prefab_collection", "set_piece", "hero_set")):
        return "multi_asset_bundle"
    if _contains_any(token, ("cross_domain", "composition_pack", "hybrid_bundle", "world_asset_mix", "gameplay_bundle", "environment_bundle", "asset_ecosystem", "content_band")):
        return "cross_domain_pack"
    if _contains_any(token, ("style_stack", "style_target", "visual_band", "construction_grammar", "stylized_pbr", "toon", "cel_shaded", "photoreal", "low_poly", "claymation", "lego")):
        return "style_stack_band"
    if _contains_any(token, ("parametric_rig", "rig_component", "skeleton", "bone", "ik", "morph", "animation", "pose", "joint_chain")):
        return "rig_animation_proxy"
    if _contains_any(token, ("domain_kit", "kit_bundle", "domain_library", "library_pack", "style_pack", "asset_pack", "production_pack", "building_set", "vehicle_set", "weapon_set", "prop_set")):
        return "domain_kit"
    if _contains_any(token, ("typed_data", "typed_bundle", "typed_kernel", "kernel_bus", "data_slot", "heightfield_slot", "point_cloud", "volume_slot", "rig_slot")):
        return "typed_data_kernel"
    if _contains_any(token, ("surface_graph", "surface_program", "attr_lang", "attribute_program", "designer_graph", "photo_fit", "layer_stack", "materialx", "smart_mask")):
        return "attribute_surface_graph"
    if _contains_any(token, ("vegetation_library", "vegetation_kit", "speedtree", "tree_library", "species_library", "branching_grammar", "canopy_library", "root_system")):
        return "vegetation_library"
    if _contains_any(token, ("terrain_heightfield", "heightfield_terrain", "heightfield_system", "terrain_program", "terrain_kit", "erosion", "hydraulic_erosion", "thermal_erosion", "biome_field", "heightfield")):
        return "terrain_heightfield"
    if _contains_any(token, ("wfc_tileset", "wfc_solver", "wave_function_collapse", "tile_solver", "tile_adjacency", "adjacency_rule", "socket_constraint", "constraint_grid", "modular_solver")):
        return "wfc_tile_solver"
    if _contains_any(token, ("cga_grammar", "cga_building", "building_grammar", "shape_grammar", "assembly_rules", "facade_rule", "split_rule", "repeat_rule", "extrude_rule")):
        return "cga_building_grammar"
    if _contains_any(token, ("volume_field", "vdb_volume", "sparse_volume", "volume_effect", "fluid_volume", "smoke_volume", "magic_volume", "density_field", "temperature_field", "velocity_field")):
        return "volume_effects_data"
    if _contains_any(token, ("instance_pattern", "scatter_program", "scatter_system", "surface_scatter", "greeble_scatter", "poisson_scatter", "copy_to_points", "point_instance", "surface_projected")):
        return "instance_pattern_scatter"
    if _contains_any(token, ("f_rep", "frep", "sdf_blend", "sdf_composition", "signed_distance", "implicit_surface", "smooth_union", "smooth_subtract", "distance_field")):
        return "f_rep_sdf"
    if _contains_any(token, ("opensubdiv", "subdivision_cage", "subdivision_finish", "catmull_clark", "loop_subdivision", "crease_tag", "remesh_finishing", "quadrangulate", "smooth_pass")):
        return "subdivision_finishing"
    if _contains_any(token, ("humanoid_anatomy", "anatomy_preset", "canonical_topology", "adult_male_realistic", "adult_female_realistic", "child_realistic", "chibi_3head", "body_proportion", "morph_database")):
        return "humanoid_anatomy"
    if _contains_any(token, ("face_sdf", "face_shadow_sdf", "anime_cel", "cel_ramp", "ramp_lut", "inverted_hull", "sobel_outline", "toon_ramp", "npr_ramp")):
        return "face_sdf_cel"
    if _contains_any(token, ("rig_component_library", "rig_components", "spine_component", "limb_component", "digit_component", "mech_joint", "wing_chain", "tentacle_chain", "ik_fk_template", "kinefx_component")):
        return "rig_component_library"
    if _contains_any(token, ("morph_target_database", "morph_target_library", "blendshape", "shape_key", "corrective_shape", "viseme", "facial_morph", "body_shape_delta", "delta_vector", "expression_set")):
        return "morph_target_database"
    if _contains_any(token, ("animation_library_binding", "animation_library", "motion_clip_library", "clip_library", "pose_library", "locomotion_set", "blend_tree", "animation_state_machine", "combat_idle", "combat_walk", "combat_run")):
        return "animation_library_binding"
    if _contains_any(token, ("retargeting_pack", "retargeting", "canonical_to_canonical", "retarget_map", "bone_mapping", "rest_pose_map", "scale_compensation", "motion_retarget", "humanoid_retarget", "source_skeleton")):
        return "retargeting_pack"
    if _contains_any(token, ("character_equipment_binding", "equipment_binding", "equipment_socket", "weapon_socket", "armor_slot", "holster_slot", "outfit_binding", "gear_socket", "loadout_slot", "equipment_clearance")):
        return "character_equipment_binding"
    if _contains_any(token, ("gameplay_animation_controller", "animation_controller", "locomotion_controller", "combat_controller", "ability_state_machine", "gameplay_state_machine", "input_action_map", "transition_rule", "animation_parameter", "motion_matching")):
        return "gameplay_animation_controller"
    if _contains_any(token, ("procedural_facial_rig", "facial_rig_pack", "face_rig", "jaw_control", "eye_control", "blink_control", "brow_control", "lip_corner", "facial_control_board", "expression_driver")):
        return "procedural_facial_rig"
    if _contains_any(token, ("hair_program", "strand_grammar", "hair_strand", "hair_cards", "root_density", "length_distribution", "wave_amplitude", "wave_frequency", "groom_region", "hair_color_gradient")):
        return "hair_program"
    if _contains_any(token, ("cloth_fabric_simulation", "cloth_program", "fabric_simulation", "xpbd_cloth", "cloth_stiffness", "cloth_damping", "cloth_mass", "cloth_settling", "pinned_cloth", "fabric_solver")):
        return "cloth_fabric_simulation"
    if _contains_any(token, ("fluid_forward", "fluid_program", "fluid_forward_volume", "asset_level_fluid", "vdb_fluid", "advection_field", "fluid_surface", "fluid_isosurface", "fluid_cache", "fluid_mesh_output")):
        return "fluid_forward_volume"
    if _contains_any(token, ("construction_grammar_kit", "construction_kit_system", "modular_construction_grammar", "snap_rule_library", "building_piece_grammar", "kitbash_rule_pack", "procedural_assembly_kit", "connector_rule_graph", "facade_kit_grammar", "structural_module_rules")):
        return "construction_grammar_kit"
    if _contains_any(token, ("creature_appendage", "appendage_program", "wing_appendage", "tail_appendage", "tentacle_appendage", "horn_appendage", "claw_appendage", "fin_appendage", "limb_variant", "appendage_socket")):
        return "creature_appendage"
    if _contains_any(token, ("body_part_library", "body_part_program", "body_part_procedural", "anatomy_region_library", "head_part_library", "torso_part_library", "hand_foot_library", "organ_socket_map", "muscle_group_library", "body_part_socket")):
        return "body_part_library"
    if _contains_any(token, ("material_primitive", "physical_substance", "substance_taxonomy", "pbr_primitive", "metal_rough_primitive", "dielectric_material", "emissive_material", "translucent_material", "procedural_substance", "material_preset_library")):
        return "material_primitive_library"
    if _contains_any(token, ("world_system", "world_graph", "world_layer", "route_network", "faction", "civilization", "quest_chain", "world_metric")):
        return "world_system"
    if _contains_any(token, ("simulation", "sim_system", "physics_field", "flow_field", "wind_field", "heat_field", "pressure_field", "constraint_solver", "erosion_solver", "fluid_solver", "particle_system", "weather_system")):
        return "simulation_env"
    if _contains_any(token, ("live_procedural", "runtime_bundle", "lathe_engine", "engine_runtime", "procedural_runtime", "runtime_override", "live_update", "engine_hook")):
        return "live_runtime"
    if _contains_any(token, ("scene_system", "scene_authoring", "scene_graph", "scene_hierarchy", "placement_layer", "spawn_layer", "navmesh_layer", "scene_validation")):
        return "scene_system"
    if _contains_any(token, ("procedural_prefab", "prefab_binding", "prefab_parameter", "prefab_variant", "prefab_slot", "prefab_lod", "prefab_dependency")):
        return "prefab_bind"
    if _contains_any(token, ("unity_lathe_plugin", "unreal_lathe_plugin", "usd_hydra_procedural", "hydra_generative", "engine_plugin_binding", "dcc_runtime_adapter", "lathe_bundle_runtime", "host_parameter_override", "engine_asset_sink", "runtime_host_contract")):
        return "host_runtime"
    if _contains_any(token, ("stream", "streaming", "partition", "runtime_chunk", "load_group", "lod_streaming", "occlusion")):
        return "stream_runtime"
    if _contains_any(token, ("multiplayer", "session", "replicate", "replication", "network", "authority", "rpc", "rollback")):
        return "network_sync"
    return None


def _state_for_action(action_kind: str) -> tuple[str, Any]:
    states = {
        "fire": ("cooldown", 0.0),
        "reload": ("ammo_loaded", False),
        "open_close": ("is_open", False),
        "toggle": ("is_active", False),
        "pickup": ("is_held", False),
        "inspect": ("has_been_seen", False),
        "use": ("use_count", 0),
        "connect": ("is_connected", False),
        "drive": ("speed", 0.0),
        "navigate_water": ("buoyancy_state", "afloat"),
        "slide": ("slide_position", 0.0),
        "rotate": ("rotation_phase", 0.0),
        "damage": ("damage_state", "intact"),
        "repair": ("repair_state", "needed"),
        "quest_signal": ("quest_state", "available"),
        "dialogue": ("dialogue_state", "available"),
        "camera_direct": ("camera_state", "idle"),
        "audio_cue": ("audio_state", "idle"),
        "localize": ("localization_state", "unresolved"),
        "accessibility": ("accessibility_state", "default"),
        "economy_tick": ("economy_state", "balanced"),
        "behavior_logic": ("logic_state", "ready"),
        "encounter_flow": ("encounter_state", "armed"),
        "inventory_object": ("inventory_state", "available"),
        "multi_asset_bundle": ("bundle_state", "authored"),
        "cross_domain_pack": ("composition_state", "bridged"),
        "style_stack_band": ("style_stack_state", "declared"),
        "rig_animation_proxy": ("rig_proxy_state", "bound"),
        "cloth_attachment": ("cloth_attachment_state", "pinned"),
        "domain_kit": ("domain_kit_state", "authored"),
        "typed_data_kernel": ("typed_kernel_state", "declared"),
        "attribute_surface_graph": ("surface_graph_state", "declared"),
        "vegetation_library": ("vegetation_library_state", "authored"),
        "terrain_heightfield": ("terrain_field_state", "authored"),
        "wfc_tile_solver": ("tile_solver_state", "unsolved"),
        "cga_building_grammar": ("building_grammar_state", "authored"),
        "volume_effects_data": ("volume_field_state", "authored"),
        "instance_pattern_scatter": ("scatter_state", "sampled"),
        "f_rep_sdf": ("sdf_composition_state", "authored"),
        "subdivision_finishing": ("finishing_state", "caged"),
        "humanoid_anatomy": ("anatomy_state", "authored"),
        "face_sdf_cel": ("face_sdf_state", "authored"),
        "rig_component_library": ("rig_library_state", "authored"),
        "morph_target_database": ("morph_database_state", "authored"),
        "animation_library_binding": ("animation_library_state", "bound"),
        "retargeting_pack": ("retargeting_state", "mapped"),
        "character_equipment_binding": ("equipment_binding_state", "bound"),
        "gameplay_animation_controller": ("animation_controller_state", "ready"),
        "procedural_facial_rig": ("facial_rig_state", "authored"),
        "hair_program": ("hair_program_state", "authored"),
        "cloth_fabric_simulation": ("cloth_solver_state", "authored"),
        "fluid_forward_volume": ("fluid_program_state", "authored"),
        "construction_grammar_kit": ("construction_kit_state", "authored"),
        "creature_appendage": ("appendage_program_state", "authored"),
        "body_part_library": ("body_part_library_state", "authored"),
        "material_primitive_library": ("material_primitive_state", "authored"),
        "world_system": ("world_system_state", "authored"),
        "simulation_env": ("simulation_state", "idle"),
        "live_runtime": ("live_runtime_state", "cold"),
        "destructible_state": ("destructible_state", "intact"),
        "scene_system": ("scene_state", "authored"),
        "prefab_bind": ("prefab_binding_state", "unbound"),
        "host_runtime": ("runtime_host_state", "unlinked"),
        "stream_runtime": ("streaming_state", "unloaded"),
        "network_sync": ("session_state", "offline"),
    }
    return states.get(action_kind, ("state", None))


def _trigger_for_action(action_kind: str) -> str:
    triggers = {
        "fire": "on_fire",
        "reload": "on_reload",
        "open_close": "on_interact",
        "toggle": "on_use",
        "pickup": "on_pickup",
        "inspect": "on_inspect",
        "use": "on_use",
        "connect": "on_connect",
        "drive": "on_drive",
        "navigate_water": "on_pilot",
        "slide": "on_interact",
        "rotate": "on_interact",
        "damage": "on_damage",
        "repair": "on_repair",
        "quest_signal": "on_objective",
        "dialogue": "on_talk",
        "camera_direct": "on_camera_cue",
        "audio_cue": "on_audio_cue",
        "localize": "on_locale_request",
        "accessibility": "on_accessibility_option",
        "economy_tick": "on_economy_tick",
        "behavior_logic": "on_logic_tick",
        "encounter_flow": "on_encounter_tick",
        "inventory_object": "on_inventory_event",
        "multi_asset_bundle": "on_bundle_resolve",
        "cross_domain_pack": "on_composition_resolve",
        "style_stack_band": "on_style_resolve",
        "rig_animation_proxy": "on_rig_tick",
        "cloth_attachment": "on_cloth_tick",
        "domain_kit": "on_kit_resolve",
        "typed_data_kernel": "on_typed_data_eval",
        "attribute_surface_graph": "on_surface_graph_eval",
        "vegetation_library": "on_vegetation_eval",
        "terrain_heightfield": "on_heightfield_eval",
        "wfc_tile_solver": "on_tile_solve",
        "cga_building_grammar": "on_grammar_derive",
        "volume_effects_data": "on_volume_eval",
        "instance_pattern_scatter": "on_scatter_eval",
        "f_rep_sdf": "on_sdf_eval",
        "subdivision_finishing": "on_finish_eval",
        "humanoid_anatomy": "on_anatomy_eval",
        "face_sdf_cel": "on_face_sdf_eval",
        "rig_component_library": "on_rig_library_eval",
        "morph_target_database": "on_morph_eval",
        "animation_library_binding": "on_animation_library_eval",
        "retargeting_pack": "on_retarget_eval",
        "character_equipment_binding": "on_equipment_bind",
        "gameplay_animation_controller": "on_animation_controller_tick",
        "procedural_facial_rig": "on_facial_rig_tick",
        "hair_program": "on_hair_eval",
        "cloth_fabric_simulation": "on_cloth_solve",
        "fluid_forward_volume": "on_fluid_eval",
        "construction_grammar_kit": "on_construction_kit_eval",
        "creature_appendage": "on_appendage_eval",
        "body_part_library": "on_body_part_eval",
        "material_primitive_library": "on_material_primitive_eval",
        "world_system": "on_world_tick",
        "simulation_env": "on_simulation_tick",
        "live_runtime": "on_live_update",
        "destructible_state": "on_damage_state",
        "scene_system": "on_scene_load",
        "prefab_bind": "on_prefab_bind",
        "host_runtime": "on_runtime_host_attach",
        "stream_runtime": "on_stream_request",
        "network_sync": "on_network_tick",
    }
    return triggers.get(action_kind, "on_interact")


def _matching_ids(items: list[Any], source_value: str, *, kind_field: str) -> list[str]:
    source_slug = _slug_fragment(source_value)
    matches: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        haystack = " ".join(
            str(value)
            for value in (
                item.get("id"),
                item.get("name"),
                item.get(kind_field),
                (item.get("metadata") or {}).get("source_value") if isinstance(item.get("metadata"), dict) else "",
                item.get("source_value"),
            )
            if value is not None
        )
        if source_slug and source_slug in _slug_fragment(haystack):
            matches.append(str(item.get("id") or item.get("name")))
    return matches


def _build_behavior_ir(asset: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
    interfaces = (runtime.get("interfaces") or {}).get("bundle") or {}
    physics = (runtime.get("physics") or {}).get("bundle") or {}
    authored_entries = _authored_behavior_texts(asset)
    actions: list[dict[str, Any]] = []
    affordances: list[dict[str, Any]] = []
    triggers: list[dict[str, Any]] = []
    states_by_name: dict[str, dict[str, Any]] = {}
    transitions: list[dict[str, Any]] = []
    seen_actions: set[str] = set()
    for entry in authored_entries:
        action_kind = _action_kind(entry["source_value"])
        if action_kind is None:
            continue
        action_id = f"{action_kind}_{entry['slug']}"
        if action_id in seen_actions:
            continue
        seen_actions.add(action_id)
        state_name, default_value = _state_for_action(action_kind)
        trigger_id = f"{_trigger_for_action(action_kind)}_{entry['slug']}"
        socket_ids = _matching_ids(list(interfaces.get("sockets") or []), entry["source_value"], kind_field="socket_type")
        pivot_ids = _matching_ids(list(interfaces.get("pivots") or []), entry["source_value"], kind_field="pivot_type")
        joint_ids = _matching_ids(list(physics.get("joints") or []), entry["source_value"], kind_field="joint_type")
        action = {
            "id": action_id,
            "action": action_kind,
            "source": entry["source_path"],
            "source_value": entry["source_value"],
            "trigger": trigger_id,
            "state": state_name,
            "socket_ids": socket_ids,
            "pivot_ids": pivot_ids,
            "physics_joint_ids": joint_ids,
        }
        actions.append(action)
        affordances.append(
            {
                "id": f"affordance_{action_id}",
                "action": action_kind,
                "prompt_key": action_kind,
                "source_action": action_id,
                "source_value": entry["source_value"],
            }
        )
        triggers.append(
            {
                "id": trigger_id,
                "event": _trigger_for_action(action_kind),
                "source_action": action_id,
                "source_value": entry["source_value"],
            }
        )
        states_by_name.setdefault(
            state_name,
            {
                "id": state_name,
                "default": default_value,
                "source_actions": [],
            },
        )
        states_by_name[state_name]["source_actions"].append(action_id)
        transitions.append(
            {
                "id": f"transition_{action_id}",
                "trigger": trigger_id,
                "action": action_id,
                "writes": state_name,
                "source_value": entry["source_value"],
            }
        )
    return {
        "schema": "lathe.behavior_ir.v1",
        "source": "authored_source_intent" if actions else "build.execution",
        "source_values": [entry["source_value"] for entry in authored_entries],
        "actions": actions,
        "affordances": affordances,
        "triggers": triggers,
        "state_variables": list(states_by_name.values()),
        "transitions": transitions,
        "bindings": {
            "socket_count": len(interfaces.get("sockets") or []),
            "pivot_count": len(interfaces.get("pivots") or []),
            "physics_joint_count": len(physics.get("joints") or []),
        },
    }


def _persistence_scope(asset: dict[str, Any], behavior_ir: dict[str, Any]) -> str:
    source_text = " ".join(
        [
            *[str(value) for value in behavior_ir.get("source_values", [])],
            *_iter_text_fragments(asset.get("execution")),
            *_iter_text_fragments(asset.get("publish", {}).get("tags")),
        ]
    )
    token = _token(source_text)
    if _contains_any(token, ("session", "multiplayer", "replicate", "network", "authority")):
        return "session"
    if _contains_any(token, ("checkpoint", "save", "persistent", "quest", "objective", "inventory", "unlock")):
        return "save_file"
    if _contains_any(token, ("temporary", "transient", "cooldown", "trigger")):
        return "runtime"
    return "runtime" if not behavior_ir.get("state_variables") else "save_file"


def _persistence_policy_for_state(state_name: str, scope: str) -> str:
    token = _token(state_name)
    if _contains_any(token, ("cooldown", "rotation_phase", "slide_position", "speed")):
        return "runtime_reset" if scope == "runtime" else "checkpoint_restore"
    if _contains_any(token, ("damage", "quest", "held", "open", "active", "connected", "ammo", "seen")):
        return "save_restore"
    return "save_restore" if scope == "save_file" else "runtime_reset"


def _build_persistence_ir(asset: dict[str, Any], runtime: dict[str, Any], behavior_ir: dict[str, Any]) -> dict[str, Any]:
    physics = (runtime.get("physics") or {}).get("bundle") or {}
    scope = _persistence_scope(asset, behavior_ir)
    persistent_variables: list[dict[str, Any]] = []
    for state in behavior_ir.get("state_variables") or []:
        if not isinstance(state, dict):
            continue
        state_id = str(state.get("id") or "")
        if not state_id:
            continue
        persistent_variables.append(
            {
                "id": state_id,
                "default": state.get("default"),
                "policy": _persistence_policy_for_state(state_id, scope),
                "source_actions": list(state.get("source_actions") or []),
            }
        )
    restorable_bodies = [
        {
            "id": part.get("id") or part.get("name"),
            "body_type": part.get("body_type"),
            "movable": bool(part.get("movable")),
        }
        for part in physics.get("parts") or []
        if isinstance(part, dict) and part.get("movable")
    ]
    restoration_hooks = [
        {
            "id": f"restore_{transition.get('id')}",
            "trigger": transition.get("trigger"),
            "writes": transition.get("writes"),
            "source_action": transition.get("action"),
        }
        for transition in behavior_ir.get("transitions") or []
        if isinstance(transition, dict) and transition.get("id")
    ]
    return {
        "schema": "lathe.persistence_ir.v1",
        "source": "behavior_ir" if persistent_variables else "build.execution",
        "scope": scope,
        "persistent_variables": persistent_variables,
        "restoration_hooks": restoration_hooks,
        "restorable_physics_bodies": restorable_bodies,
        "save_keys": [f"{asset.get('name', 'asset')}.{item['id']}" for item in persistent_variables],
        "bindings": {
            "behavior_state_count": len(behavior_ir.get("state_variables") or []),
            "behavior_transition_count": len(behavior_ir.get("transitions") or []),
            "restorable_body_count": len(restorable_bodies),
        },
    }


def _quest_entry_kind(source_value: str) -> str | None:
    token = _token(source_value)
    if _contains_any(token, ("quest", "mission", "objective_chain")):
        return "quest"
    if _contains_any(token, ("objective", "goal", "task", "quest_marker")):
        return "objective"
    if _contains_any(token, ("dialogue", "conversation", "talk", "response", "choice")):
        return "dialogue"
    if _contains_any(token, ("npc", "quest_giver", "speaker", "vendor", "merchant", "guide")):
        return "speaker"
    if _contains_any(token, ("reward", "loot", "unlock", "prize", "currency")):
        return "reward"
    if _contains_any(token, ("success", "failure", "condition", "requires", "requirement")):
        return "condition"
    return None


def _quest_action_ids(behavior_ir: dict[str, Any], source_value: str, action_names: set[str]) -> list[str]:
    source_slug = _slug_fragment(source_value)
    action_ids: list[str] = []
    for action in behavior_ir.get("actions") or []:
        if not isinstance(action, dict):
            continue
        if str(action.get("action") or "") not in action_names:
            continue
        action_source_slug = _slug_fragment(action.get("source_value") or action.get("id"))
        if source_slug in action_source_slug or action_source_slug in source_slug:
            action_ids.append(str(action.get("id")))
    return action_ids


def _quest_state_ids(persistence_ir: dict[str, Any], names: tuple[str, ...]) -> list[str]:
    states: list[str] = []
    for item in persistence_ir.get("persistent_variables") or []:
        if not isinstance(item, dict):
            continue
        state_id = str(item.get("id") or "")
        if _contains_any(_token(state_id), names):
            states.append(state_id)
    return states


def _build_quest_dialogue_ir(
    asset: dict[str, Any],
    behavior_ir: dict[str, Any],
    persistence_ir: dict[str, Any],
) -> dict[str, Any]:
    entries = _authored_behavior_texts(asset)
    quests: list[dict[str, Any]] = []
    objectives: list[dict[str, Any]] = []
    dialogue_nodes: list[dict[str, Any]] = []
    speakers: list[dict[str, Any]] = []
    rewards: list[dict[str, Any]] = []
    conditions: list[dict[str, Any]] = []
    seen: set[str] = set()
    quest_states = _quest_state_ids(persistence_ir, ("quest", "objective"))
    dialogue_states = _quest_state_ids(persistence_ir, ("dialogue", "seen"))
    for entry in entries:
        kind = _quest_entry_kind(entry["source_value"])
        if kind is None:
            continue
        node_id = f"{kind}_{entry['slug']}"
        if node_id in seen:
            continue
        seen.add(node_id)
        base = {
            "id": node_id,
            "source": entry["source_path"],
            "source_value": entry["source_value"],
        }
        if kind == "quest":
            quests.append(
                {
                    **base,
                    "state_ids": quest_states,
                    "objective_ids": [],
                    "reward_ids": [],
                    "dialogue_ids": [],
                    "action_ids": _quest_action_ids(behavior_ir, entry["source_value"], {"quest_signal", "use", "inspect"}),
                }
            )
        elif kind == "objective":
            objectives.append(
                {
                    **base,
                    "quest_id": quests[-1]["id"] if quests else "",
                    "state_ids": quest_states,
                    "condition_ids": [],
                    "action_ids": _quest_action_ids(behavior_ir, entry["source_value"], {"quest_signal", "use", "inspect", "pickup"}),
                }
            )
        elif kind == "dialogue":
            dialogue_nodes.append(
                {
                    **base,
                    "speaker_ids": [],
                    "choice_ids": [f"{node_id}_choice_01"],
                    "state_ids": dialogue_states,
                    "action_ids": _quest_action_ids(behavior_ir, entry["source_value"], {"dialogue", "inspect", "use"}),
                }
            )
        elif kind == "speaker":
            speakers.append(
                {
                    **base,
                    "dialogue_ids": [],
                    "quest_ids": [quests[-1]["id"]] if quests else [],
                    "action_ids": _quest_action_ids(behavior_ir, entry["source_value"], {"dialogue", "quest_signal", "use"}),
                }
            )
        elif kind == "reward":
            rewards.append(
                {
                    **base,
                    "quest_id": quests[-1]["id"] if quests else "",
                    "requires_objective_ids": [objectives[-1]["id"]] if objectives else [],
                    "action_ids": _quest_action_ids(behavior_ir, entry["source_value"], {"quest_signal", "pickup", "use"}),
                }
            )
        elif kind == "condition":
            conditions.append(
                {
                    **base,
                    "checks": ["state", "interaction"],
                    "state_ids": quest_states,
                }
            )

    if not quests and (objectives or rewards or dialogue_nodes):
        quests.append(
            {
                "id": f"quest_{_slug_fragment(asset.get('name'), 'asset')}",
                "source": "asset.name",
                "source_value": str(asset.get("name") or ""),
                "state_ids": quest_states,
                "objective_ids": [],
                "reward_ids": [],
                "dialogue_ids": [],
                "action_ids": _quest_action_ids(behavior_ir, str(asset.get("name") or ""), {"quest_signal"}),
            }
        )
    for objective in objectives:
        if not objective.get("quest_id") and quests:
            objective["quest_id"] = quests[0]["id"]
    for reward in rewards:
        if not reward.get("quest_id") and quests:
            reward["quest_id"] = quests[0]["id"]
    for dialogue in dialogue_nodes:
        dialogue["speaker_ids"] = [speaker["id"] for speaker in speakers]
    for speaker in speakers:
        speaker["dialogue_ids"] = [dialogue["id"] for dialogue in dialogue_nodes]
    for quest in quests:
        quest["objective_ids"] = [objective["id"] for objective in objectives if objective.get("quest_id") == quest["id"]]
        quest["reward_ids"] = [reward["id"] for reward in rewards if reward.get("quest_id") == quest["id"]]
        quest["dialogue_ids"] = [dialogue["id"] for dialogue in dialogue_nodes]
    for objective in objectives:
        objective["condition_ids"] = [condition["id"] for condition in conditions]

    return {
        "schema": "lathe.quest_dialogue_ir.v1",
        "source": "authored_source_intent" if quests or objectives or dialogue_nodes else "build.execution",
        "quests": quests,
        "objectives": objectives,
        "dialogue_nodes": dialogue_nodes,
        "speakers": speakers,
        "rewards": rewards,
        "conditions": conditions,
        "bindings": {
            "behavior_action_count": len(behavior_ir.get("actions") or []),
            "quest_state_count": len(quest_states),
            "dialogue_state_count": len(dialogue_states),
        },
    }


def _camera_entry_kind(source_value: str) -> str | None:
    token = _token(source_value)
    if _contains_any(token, ("shot_sequence", "sequence", "timeline", "sequencer", "cutscene")):
        return "sequence"
    if _contains_any(token, ("shot", "camera_shot", "cinematic_shot")):
        return "shot"
    if _contains_any(token, ("camera_rail", "rail_camera", "dolly", "motion_path")):
        return "rail"
    if _contains_any(token, ("look_at", "look_at_target", "focus_target", "target")):
        return "look_target"
    if _contains_any(token, ("focal_zone", "focus_pull", "focus", "lens")):
        return "focus"
    if _contains_any(token, ("orbit_camera", "inspection_camera", "presentation_rig", "camera_volume", "camera")):
        return "camera"
    if _contains_any(token, ("composition_guide", "framing", "rule_of_thirds", "guide")):
        return "composition"
    return None


def _camera_action_ids(behavior_ir: dict[str, Any], source_value: str) -> list[str]:
    return _quest_action_ids(behavior_ir, source_value, {"camera_direct", "inspect", "use", "quest_signal", "dialogue"})


def _build_camera_cinematic_ir(
    asset: dict[str, Any],
    behavior_ir: dict[str, Any],
    quest_dialogue_ir: dict[str, Any],
) -> dict[str, Any]:
    entries = _authored_behavior_texts(asset)
    cameras: list[dict[str, Any]] = []
    shots: list[dict[str, Any]] = []
    sequences: list[dict[str, Any]] = []
    rails: list[dict[str, Any]] = []
    look_targets: list[dict[str, Any]] = []
    focus_zones: list[dict[str, Any]] = []
    composition_guides: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in entries:
        kind = _camera_entry_kind(entry["source_value"])
        if kind is None:
            continue
        node_id = f"{kind}_{entry['slug']}"
        if node_id in seen:
            continue
        seen.add(node_id)
        base = {
            "id": node_id,
            "source": entry["source_path"],
            "source_value": entry["source_value"],
            "action_ids": _camera_action_ids(behavior_ir, entry["source_value"]),
        }
        if kind == "camera":
            cameras.append(
                {
                    **base,
                    "camera_type": "inspection" if _contains_any(entry["slug"], ("inspect", "presentation")) else "scene",
                    "shot_ids": [],
                    "look_target_ids": [],
                    "focus_zone_ids": [],
                }
            )
        elif kind == "shot":
            shots.append(
                {
                    **base,
                    "camera_id": cameras[-1]["id"] if cameras else "",
                    "rail_id": rails[-1]["id"] if rails else "",
                    "look_target_id": look_targets[-1]["id"] if look_targets else "",
                    "focus_zone_id": focus_zones[-1]["id"] if focus_zones else "",
                }
            )
        elif kind == "sequence":
            sequences.append(
                {
                    **base,
                    "shot_ids": [],
                    "quest_ids": [quest.get("id") for quest in quest_dialogue_ir.get("quests") or [] if isinstance(quest, dict)],
                    "dialogue_ids": [dialogue.get("id") for dialogue in quest_dialogue_ir.get("dialogue_nodes") or [] if isinstance(dialogue, dict)],
                }
            )
        elif kind == "rail":
            rails.append({**base, "path_policy": "authored_or_auto"})
        elif kind == "look_target":
            look_targets.append({**base, "target_policy": "authored_or_subject"})
        elif kind == "focus":
            focus_zones.append({**base, "focus_policy": "authored_or_center"})
        elif kind == "composition":
            composition_guides.append({**base, "guide": "composition"})

    if not cameras and (shots or sequences or rails or look_targets or focus_zones):
        cameras.append(
            {
                "id": f"camera_{_slug_fragment(asset.get('name'), 'asset')}",
                "source": "asset.name",
                "source_value": str(asset.get("name") or ""),
                "action_ids": _camera_action_ids(behavior_ir, str(asset.get("name") or "")),
                "camera_type": "scene",
                "shot_ids": [],
                "look_target_ids": [],
                "focus_zone_ids": [],
            }
        )
    if not shots and (sequences or rails or look_targets or focus_zones):
        shots.append(
            {
                "id": f"shot_{_slug_fragment(asset.get('name'), 'asset')}",
                "source": "asset.name",
                "source_value": str(asset.get("name") or ""),
                "action_ids": _camera_action_ids(behavior_ir, str(asset.get("name") or "")),
                "camera_id": cameras[0]["id"] if cameras else "",
                "rail_id": rails[0]["id"] if rails else "",
                "look_target_id": look_targets[0]["id"] if look_targets else "",
                "focus_zone_id": focus_zones[0]["id"] if focus_zones else "",
            }
        )
    if not sequences and shots:
        sequences.append(
            {
                "id": f"sequence_{_slug_fragment(asset.get('name'), 'asset')}",
                "source": "asset.name",
                "source_value": str(asset.get("name") or ""),
                "action_ids": _camera_action_ids(behavior_ir, str(asset.get("name") or "")),
                "shot_ids": [],
                "quest_ids": [quest.get("id") for quest in quest_dialogue_ir.get("quests") or [] if isinstance(quest, dict)],
                "dialogue_ids": [dialogue.get("id") for dialogue in quest_dialogue_ir.get("dialogue_nodes") or [] if isinstance(dialogue, dict)],
            }
        )
    for camera in cameras:
        camera["shot_ids"] = [shot["id"] for shot in shots if not shot.get("camera_id") or shot.get("camera_id") == camera["id"]]
        camera["look_target_ids"] = [target["id"] for target in look_targets]
        camera["focus_zone_ids"] = [zone["id"] for zone in focus_zones]
    for shot in shots:
        if not shot.get("camera_id") and cameras:
            shot["camera_id"] = cameras[0]["id"]
    for sequence in sequences:
        sequence["shot_ids"] = [shot["id"] for shot in shots]

    return {
        "schema": "lathe.camera_cinematic_ir.v1",
        "source": "authored_source_intent" if cameras or shots or sequences else "build.execution",
        "cameras": cameras,
        "shots": shots,
        "sequences": sequences,
        "rails": rails,
        "look_targets": look_targets,
        "focus_zones": focus_zones,
        "composition_guides": composition_guides,
        "bindings": {
            "behavior_action_count": len(behavior_ir.get("actions") or []),
            "quest_count": len(quest_dialogue_ir.get("quests") or []),
            "dialogue_count": len(quest_dialogue_ir.get("dialogue_nodes") or []),
        },
    }


def _audio_entry_kind(source_value: str) -> str | None:
    token = _token(source_value)
    if _contains_any(token, ("music_state", "music_transition", "stinger", "music")):
        return "music"
    if _contains_any(token, ("foley", "foley_emitter", "footstep", "impact")):
        return "foley"
    if _contains_any(token, ("ambient_bed", "ambience", "ambient", "soundscape")):
        return "ambient"
    if _contains_any(token, ("sound_cue", "sound", "audio_cue", "cue")):
        return "cue"
    if _contains_any(token, ("sound_zone", "listener_zone", "audio_bus", "bus")):
        return "zone"
    if _contains_any(token, ("reverb_space", "acoustic_occluder", "sound_propagation", "acoustic_material", "reverb", "occluder")):
        return "acoustic"
    return None


def _build_audio_ir(
    asset: dict[str, Any],
    behavior_ir: dict[str, Any],
    quest_dialogue_ir: dict[str, Any],
    camera_cinematic_ir: dict[str, Any],
) -> dict[str, Any]:
    cues: list[dict[str, Any]] = []
    music_states: list[dict[str, Any]] = []
    ambient_beds: list[dict[str, Any]] = []
    foley_emitters: list[dict[str, Any]] = []
    zones: list[dict[str, Any]] = []
    acoustic_spaces: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in _authored_behavior_texts(asset):
        kind = _audio_entry_kind(entry["source_value"])
        if kind is None:
            continue
        node_id = f"{kind}_{entry['slug']}"
        if node_id in seen:
            continue
        seen.add(node_id)
        base = {
            "id": node_id,
            "source": entry["source_path"],
            "source_value": entry["source_value"],
            "action_ids": _quest_action_ids(behavior_ir, entry["source_value"], {"audio_cue", "use", "quest_signal", "dialogue", "camera_direct"}),
        }
        if kind == "music":
            music_states.append(
                {
                    **base,
                    "transition_ids": [],
                    "quest_ids": [quest.get("id") for quest in quest_dialogue_ir.get("quests") or [] if isinstance(quest, dict)],
                    "sequence_ids": [sequence.get("id") for sequence in camera_cinematic_ir.get("sequences") or [] if isinstance(sequence, dict)],
                }
            )
        elif kind == "foley":
            foley_emitters.append({**base, "emit_policy": "event_bound"})
        elif kind == "ambient":
            ambient_beds.append({**base, "loop": True, "zone_ids": []})
        elif kind == "cue":
            cues.append({**base, "cue_type": "event", "zone_ids": []})
        elif kind == "zone":
            zones.append({**base, "zone_type": "spatial_audio"})
        elif kind == "acoustic":
            acoustic_spaces.append({**base, "acoustic_policy": "authored_or_material"})

    if not cues and (music_states or foley_emitters):
        cues.append(
            {
                "id": f"cue_{_slug_fragment(asset.get('name'), 'asset')}",
                "source": "asset.name",
                "source_value": str(asset.get("name") or ""),
                "action_ids": _quest_action_ids(behavior_ir, str(asset.get("name") or ""), {"audio_cue"}),
                "cue_type": "event",
                "zone_ids": [],
            }
        )
    if not ambient_beds and zones:
        ambient_beds.append(
            {
                "id": f"ambient_{_slug_fragment(asset.get('name'), 'asset')}",
                "source": "asset.name",
                "source_value": str(asset.get("name") or ""),
                "action_ids": _quest_action_ids(behavior_ir, str(asset.get("name") or ""), {"audio_cue"}),
                "loop": True,
                "zone_ids": [],
            }
        )
    zone_ids = [zone["id"] for zone in zones]
    for cue in cues:
        cue["zone_ids"] = zone_ids
    for ambient in ambient_beds:
        ambient["zone_ids"] = zone_ids
    for index, music_state in enumerate(music_states):
        next_state = music_states[(index + 1) % len(music_states)]["id"] if len(music_states) > 1 else ""
        music_state["transition_ids"] = [f"{music_state['id']}_to_{next_state}"] if next_state else []

    return {
        "schema": "lathe.audio_ir.v1",
        "source": "authored_source_intent" if cues or music_states or ambient_beds or foley_emitters else "build.execution",
        "cues": cues,
        "music_states": music_states,
        "ambient_beds": ambient_beds,
        "foley_emitters": foley_emitters,
        "zones": zones,
        "acoustic_spaces": acoustic_spaces,
        "bindings": {
            "behavior_action_count": len(behavior_ir.get("actions") or []),
            "quest_count": len(quest_dialogue_ir.get("quests") or []),
            "camera_sequence_count": len(camera_cinematic_ir.get("sequences") or []),
        },
    }


def _runtime_partition_entry_kind(source_value: str) -> str | None:
    token = _token(source_value)
    if _contains_any(token, ("world_streaming_partition", "runtime_partition", "world_partition", "partition_root")):
        return "partition"
    if _contains_any(token, ("streaming_cell", "cell_grid", "sector", "runtime_chunk", "chunk_graph")):
        return "cell"
    if _contains_any(token, ("streaming_volume", "load_volume", "streaming_bounds", "volume")):
        return "volume"
    if _contains_any(token, ("load_group", "world_load_group", "dependency", "load_dependency")):
        return "load_group"
    if _contains_any(token, ("lod_streaming", "lod_ring", "distance_ring", "lod")):
        return "lod_ring"
    if _contains_any(token, ("occlusion", "visibility", "visibility_region", "occlusion_partition")):
        return "visibility"
    if _contains_any(token, ("memory_budget", "asset_residency", "residency", "streaming_budget")):
        return "budget"
    return None


def _build_runtime_partition_ir(
    asset: dict[str, Any],
    behavior_ir: dict[str, Any],
    persistence_ir: dict[str, Any],
    camera_cinematic_ir: dict[str, Any],
    audio_ir: dict[str, Any],
) -> dict[str, Any]:
    partitions: list[dict[str, Any]] = []
    cells: list[dict[str, Any]] = []
    streaming_volumes: list[dict[str, Any]] = []
    load_groups: list[dict[str, Any]] = []
    lod_rings: list[dict[str, Any]] = []
    visibility_regions: list[dict[str, Any]] = []
    residency_rules: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in _authored_behavior_texts(asset):
        kind = _runtime_partition_entry_kind(entry["source_value"])
        if kind is None:
            continue
        node_id = f"{kind}_{entry['slug']}"
        if node_id in seen:
            continue
        seen.add(node_id)
        base = {
            "id": node_id,
            "source": entry["source_path"],
            "source_value": entry["source_value"],
            "action_ids": _quest_action_ids(behavior_ir, entry["source_value"], {"stream_runtime", "camera_direct", "audio_cue"}),
        }
        if kind == "partition":
            partitions.append({**base, "cell_ids": [], "load_group_ids": []})
        elif kind == "cell":
            cells.append({**base, "partition_id": partitions[-1]["id"] if partitions else "", "volume_ids": []})
        elif kind == "volume":
            streaming_volumes.append({**base, "cell_id": cells[-1]["id"] if cells else "", "load_group_id": ""})
        elif kind == "load_group":
            load_groups.append({**base, "dependency_ids": [], "residency_rule_ids": []})
        elif kind == "lod_ring":
            lod_rings.append({**base, "distance_policy": "authored_or_auto"})
        elif kind == "visibility":
            visibility_regions.append({**base, "visibility_policy": "authored_or_occlusion"})
        elif kind == "budget":
            residency_rules.append({**base, "budget_policy": "authored_or_default"})

    if not partitions and (cells or streaming_volumes or load_groups or lod_rings or visibility_regions):
        partitions.append(
            {
                "id": f"partition_{_slug_fragment(asset.get('name'), 'asset')}",
                "source": "asset.name",
                "source_value": str(asset.get("name") or ""),
                "action_ids": _quest_action_ids(behavior_ir, str(asset.get("name") or ""), {"stream_runtime"}),
                "cell_ids": [],
                "load_group_ids": [],
            }
        )
    if not cells and (streaming_volumes or lod_rings or visibility_regions):
        cells.append(
            {
                "id": f"cell_{_slug_fragment(asset.get('name'), 'asset')}",
                "source": "asset.name",
                "source_value": str(asset.get("name") or ""),
                "action_ids": _quest_action_ids(behavior_ir, str(asset.get("name") or ""), {"stream_runtime"}),
                "partition_id": partitions[0]["id"] if partitions else "",
                "volume_ids": [],
            }
        )
    if not load_groups and (residency_rules or audio_ir.get("cues") or camera_cinematic_ir.get("sequences")):
        load_groups.append(
            {
                "id": f"load_group_{_slug_fragment(asset.get('name'), 'asset')}",
                "source": "asset.name",
                "source_value": str(asset.get("name") or ""),
                "action_ids": _quest_action_ids(behavior_ir, str(asset.get("name") or ""), {"stream_runtime"}),
                "dependency_ids": [],
                "residency_rule_ids": [],
            }
        )
    for cell in cells:
        if not cell.get("partition_id") and partitions:
            cell["partition_id"] = partitions[0]["id"]
        cell["volume_ids"] = [volume["id"] for volume in streaming_volumes if not volume.get("cell_id") or volume.get("cell_id") == cell["id"]]
    for volume in streaming_volumes:
        if not volume.get("cell_id") and cells:
            volume["cell_id"] = cells[0]["id"]
        if load_groups and not volume.get("load_group_id"):
            volume["load_group_id"] = load_groups[0]["id"]
    for load_group in load_groups:
        load_group["residency_rule_ids"] = [rule["id"] for rule in residency_rules]
        load_group["dependency_ids"] = [
            *[sequence.get("id") for sequence in camera_cinematic_ir.get("sequences") or [] if isinstance(sequence, dict)],
            *[cue.get("id") for cue in audio_ir.get("cues") or [] if isinstance(cue, dict)],
        ]
    for partition in partitions:
        partition["cell_ids"] = [cell["id"] for cell in cells if not cell.get("partition_id") or cell.get("partition_id") == partition["id"]]
        partition["load_group_ids"] = [group["id"] for group in load_groups]

    return {
        "schema": "lathe.runtime_partition_ir.v1",
        "source": "authored_source_intent" if partitions or cells or streaming_volumes else "build.execution",
        "partitions": partitions,
        "cells": cells,
        "streaming_volumes": streaming_volumes,
        "load_groups": load_groups,
        "lod_rings": lod_rings,
        "visibility_regions": visibility_regions,
        "residency_rules": residency_rules,
        "bindings": {
            "persistent_variable_count": len(persistence_ir.get("persistent_variables") or []),
            "camera_sequence_count": len(camera_cinematic_ir.get("sequences") or []),
            "audio_cue_count": len(audio_ir.get("cues") or []),
        },
    }


def _multiplayer_entry_kind(source_value: str) -> str | None:
    token = _token(source_value)
    if _contains_any(token, ("multiplayer_session", "session_replication", "network_session", "session")):
        return "session"
    if _contains_any(token, ("authority", "ownership", "owner", "server_authority")):
        return "authority"
    if _contains_any(token, ("replicated_state", "replication_state", "replicate", "replication")):
        return "replicated_state"
    if _contains_any(token, ("rpc", "rpc_event", "event_bus", "remote_event")):
        return "rpc"
    if _contains_any(token, ("sync_tick", "tick_timeline", "network_tick", "synchronization")):
        return "sync_tick"
    if _contains_any(token, ("prediction", "reconciliation", "predict", "reconcile")):
        return "prediction"
    if _contains_any(token, ("rollback", "rollback_state", "rollback_buffer")):
        return "rollback"
    if _contains_any(token, ("matchmaking", "matchmaking_rule", "session_rule")):
        return "matchmaking"
    return None


def _build_multiplayer_session_ir(
    asset: dict[str, Any],
    behavior_ir: dict[str, Any],
    persistence_ir: dict[str, Any],
    runtime_partition_ir: dict[str, Any],
) -> dict[str, Any]:
    sessions: list[dict[str, Any]] = []
    authority_maps: list[dict[str, Any]] = []
    replicated_states: list[dict[str, Any]] = []
    rpc_channels: list[dict[str, Any]] = []
    sync_ticks: list[dict[str, Any]] = []
    prediction_paths: list[dict[str, Any]] = []
    rollback_buffers: list[dict[str, Any]] = []
    matchmaking_rules: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in _authored_behavior_texts(asset):
        kind = _multiplayer_entry_kind(entry["source_value"])
        if kind is None:
            continue
        node_id = f"{kind}_{entry['slug']}"
        if node_id in seen:
            continue
        seen.add(node_id)
        base = {
            "id": node_id,
            "source": entry["source_path"],
            "source_value": entry["source_value"],
            "action_ids": _quest_action_ids(behavior_ir, entry["source_value"], {"network_sync", "stream_runtime", "use"}),
        }
        if kind == "session":
            sessions.append({**base, "authority_map_ids": [], "replicated_state_ids": [], "rpc_channel_ids": []})
        elif kind == "authority":
            authority_maps.append({**base, "owner_policy": "server_authoritative"})
        elif kind == "replicated_state":
            replicated_states.append({**base, "state_ids": [], "partition_ids": []})
        elif kind == "rpc":
            rpc_channels.append({**base, "reliability": "reliable"})
        elif kind == "sync_tick":
            sync_ticks.append({**base, "tick_policy": "fixed"})
        elif kind == "prediction":
            prediction_paths.append({**base, "reconciliation_policy": "client_predict_server_reconcile"})
        elif kind == "rollback":
            rollback_buffers.append({**base, "buffer_policy": "state_snapshot"})
        elif kind == "matchmaking":
            matchmaking_rules.append({**base, "rule_policy": "session_match"})

    if not sessions and (authority_maps or replicated_states or rpc_channels or sync_ticks):
        sessions.append(
            {
                "id": f"session_{_slug_fragment(asset.get('name'), 'asset')}",
                "source": "asset.name",
                "source_value": str(asset.get("name") or ""),
                "action_ids": _quest_action_ids(behavior_ir, str(asset.get("name") or ""), {"network_sync"}),
                "authority_map_ids": [],
                "replicated_state_ids": [],
                "rpc_channel_ids": [],
            }
        )
    if not authority_maps and sessions:
        authority_maps.append(
            {
                "id": f"authority_{_slug_fragment(asset.get('name'), 'asset')}",
                "source": "asset.name",
                "source_value": str(asset.get("name") or ""),
                "action_ids": _quest_action_ids(behavior_ir, str(asset.get("name") or ""), {"network_sync"}),
                "owner_policy": "server_authoritative",
            }
        )
    if not replicated_states and sessions:
        replicated_states.append(
            {
                "id": f"replicated_state_{_slug_fragment(asset.get('name'), 'asset')}",
                "source": "persistence_ir",
                "source_value": "persistent_variables",
                "action_ids": [],
                "state_ids": [item.get("id") for item in persistence_ir.get("persistent_variables") or [] if isinstance(item, dict)],
                "partition_ids": [item.get("id") for item in runtime_partition_ir.get("partitions") or [] if isinstance(item, dict)],
            }
        )
    for replicated in replicated_states:
        if not replicated.get("state_ids"):
            replicated["state_ids"] = [item.get("id") for item in persistence_ir.get("persistent_variables") or [] if isinstance(item, dict)]
        if not replicated.get("partition_ids"):
            replicated["partition_ids"] = [item.get("id") for item in runtime_partition_ir.get("partitions") or [] if isinstance(item, dict)]
    for session in sessions:
        session["authority_map_ids"] = [item["id"] for item in authority_maps]
        session["replicated_state_ids"] = [item["id"] for item in replicated_states]
        session["rpc_channel_ids"] = [item["id"] for item in rpc_channels]

    return {
        "schema": "lathe.multiplayer_session_ir.v1",
        "source": "authored_source_intent" if sessions or replicated_states else "build.execution",
        "sessions": sessions,
        "authority_maps": authority_maps,
        "replicated_states": replicated_states,
        "rpc_channels": rpc_channels,
        "sync_ticks": sync_ticks,
        "prediction_paths": prediction_paths,
        "rollback_buffers": rollback_buffers,
        "matchmaking_rules": matchmaking_rules,
        "bindings": {
            "persistent_variable_count": len(persistence_ir.get("persistent_variables") or []),
            "partition_count": len(runtime_partition_ir.get("partitions") or []),
            "network_action_count": len([
                action for action in behavior_ir.get("actions") or []
                if isinstance(action, dict) and action.get("action") == "network_sync"
            ]),
        },
    }


def _localization_entry_kind(source_value: str) -> str | None:
    token = _token(source_value)
    if _contains_any(token, ("string_key", "translation_key", "translation_key_map", "key_row", "localization_key")):
        return "string_key"
    if _contains_any(token, ("translation", "locale_value", "translation_column", "localized_text")):
        return "translation"
    if _contains_any(token, ("pluralization", "plural_rule", "gender_rule", "plural", "gender")):
        return "plural_rule"
    if _contains_any(token, ("locale_fallback", "fallback_locale", "fallback_chain", "locale_chain")):
        return "fallback"
    if _contains_any(token, ("subtitle_timing", "subtitle", "caption_timing")):
        return "subtitle"
    if _contains_any(token, ("voiceover_text", "voiceover", "vo_text", "vo_binding")):
        return "voiceover"
    if _contains_any(token, ("font_glyph_coverage", "glyph", "font_coverage", "font")):
        return "glyph"
    if _contains_any(token, ("localization_guard", "localization_validation", "missing_translation", "validation_guard")):
        return "guard"
    if _contains_any(token, ("localization_text_table", "text_table_bundle", "localization_table", "string_table", "table_root", "localization")):
        return "table"
    return None


def _build_localization_text_ir(
    asset: dict[str, Any],
    behavior_ir: dict[str, Any],
    quest_dialogue_ir: dict[str, Any],
    audio_ir: dict[str, Any],
) -> dict[str, Any]:
    tables: list[dict[str, Any]] = []
    string_keys: list[dict[str, Any]] = []
    translations: list[dict[str, Any]] = []
    plural_rules: list[dict[str, Any]] = []
    fallback_chains: list[dict[str, Any]] = []
    subtitle_timings: list[dict[str, Any]] = []
    voiceover_bindings: list[dict[str, Any]] = []
    glyph_coverage: list[dict[str, Any]] = []
    validation_guards: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in _authored_behavior_texts(asset):
        kind = _localization_entry_kind(entry["source_value"])
        if kind is None:
            continue
        node_id = f"{kind}_{entry['slug']}"
        if node_id in seen:
            continue
        seen.add(node_id)
        base = {
            "id": node_id,
            "source": entry["source_path"],
            "source_value": entry["source_value"],
            "action_ids": _quest_action_ids(behavior_ir, entry["source_value"], {"localize", "dialogue", "audio_cue", "quest_signal"}),
        }
        if kind == "table":
            tables.append({**base, "string_key_ids": [], "fallback_chain_ids": [], "glyph_coverage_ids": []})
        elif kind == "string_key":
            string_keys.append({**base, "table_id": tables[-1]["id"] if tables else "", "translation_ids": []})
        elif kind == "translation":
            translations.append({**base, "key_id": string_keys[-1]["id"] if string_keys else "", "locale_policy": "authored_or_default"})
        elif kind == "plural_rule":
            plural_rules.append({**base, "key_ids": []})
        elif kind == "fallback":
            fallback_chains.append({**base, "locale_policy": "fallback_order"})
        elif kind == "subtitle":
            subtitle_timings.append(
                {
                    **base,
                    "dialogue_ids": [item.get("id") for item in quest_dialogue_ir.get("dialogue_nodes") or [] if isinstance(item, dict)],
                    "audio_cue_ids": [item.get("id") for item in audio_ir.get("cues") or [] if isinstance(item, dict)],
                }
            )
        elif kind == "voiceover":
            voiceover_bindings.append(
                {
                    **base,
                    "dialogue_ids": [item.get("id") for item in quest_dialogue_ir.get("dialogue_nodes") or [] if isinstance(item, dict)],
                    "audio_cue_ids": [item.get("id") for item in audio_ir.get("cues") or [] if isinstance(item, dict)],
                }
            )
        elif kind == "glyph":
            glyph_coverage.append({**base, "coverage_policy": "font_or_locale"})
        elif kind == "guard":
            validation_guards.append({**base, "guard_policy": "missing_translation_or_font"})

    if not tables and (string_keys or translations or plural_rules or fallback_chains or subtitle_timings or voiceover_bindings or glyph_coverage):
        tables.append(
            {
                "id": f"table_{_slug_fragment(asset.get('name'), 'asset')}",
                "source": "asset.name",
                "source_value": str(asset.get("name") or ""),
                "action_ids": _quest_action_ids(behavior_ir, str(asset.get("name") or ""), {"localize", "dialogue"}),
                "string_key_ids": [],
                "fallback_chain_ids": [],
                "glyph_coverage_ids": [],
            }
        )
    if not string_keys and (translations or plural_rules or subtitle_timings or voiceover_bindings):
        string_keys.append(
            {
                "id": f"string_key_{_slug_fragment(asset.get('name'), 'asset')}",
                "source": "asset.name",
                "source_value": str(asset.get("name") or ""),
                "action_ids": _quest_action_ids(behavior_ir, str(asset.get("name") or ""), {"localize", "dialogue"}),
                "table_id": tables[0]["id"] if tables else "",
                "translation_ids": [],
            }
        )
    for key in string_keys:
        if not key.get("table_id") and tables:
            key["table_id"] = tables[0]["id"]
        key["translation_ids"] = [translation["id"] for translation in translations if not translation.get("key_id") or translation.get("key_id") == key["id"]]
    for translation in translations:
        if not translation.get("key_id") and string_keys:
            translation["key_id"] = string_keys[0]["id"]
    for rule in plural_rules:
        rule["key_ids"] = [key["id"] for key in string_keys]
    for table in tables:
        table["string_key_ids"] = [key["id"] for key in string_keys if not key.get("table_id") or key.get("table_id") == table["id"]]
        table["fallback_chain_ids"] = [chain["id"] for chain in fallback_chains]
        table["glyph_coverage_ids"] = [coverage["id"] for coverage in glyph_coverage]

    return {
        "schema": "lathe.localization_text_ir.v1",
        "source": "authored_source_intent" if tables or string_keys or translations else "build.execution",
        "tables": tables,
        "string_keys": string_keys,
        "translations": translations,
        "plural_rules": plural_rules,
        "fallback_chains": fallback_chains,
        "subtitle_timings": subtitle_timings,
        "voiceover_bindings": voiceover_bindings,
        "glyph_coverage": glyph_coverage,
        "validation_guards": validation_guards,
        "bindings": {
            "dialogue_count": len(quest_dialogue_ir.get("dialogue_nodes") or []),
            "audio_cue_count": len(audio_ir.get("cues") or []),
            "localization_action_count": len([
                action for action in behavior_ir.get("actions") or []
                if isinstance(action, dict) and action.get("action") == "localize"
            ]),
        },
    }


def _accessibility_entry_kind(source_value: str) -> str | None:
    token = _token(source_value)
    if _contains_any(token, ("input_remap", "input_map", "control_map", "remap")):
        return "input_map"
    if _contains_any(token, ("readability", "readable_state", "state_cue", "readable_cue")):
        return "readable_cue"
    if _contains_any(token, ("contrast_safe", "contrast", "color_safe", "colorblind", "luminance")):
        return "contrast_region"
    if _contains_any(token, ("subtitle_caption", "caption", "subtitle_panel", "caption_panel")):
        return "caption_panel"
    if _contains_any(token, ("haptic", "redundant_feedback", "visual_feedback", "audio_feedback", "visual_cue", "feedback_map")):
        return "feedback_cue"
    if _contains_any(token, ("focus_navigation", "tab_order", "screen_reader", "selection_ring")):
        return "focus_navigation"
    if _contains_any(token, ("accessibility_option", "option_panel", "option_port", "profile_output")):
        return "option_port"
    if _contains_any(token, ("usability_guard", "accessibility_guard", "blocked_focus", "unreadable_state")):
        return "usability_guard"
    if _contains_any(token, ("accessibility_ux_affordance", "ux_affordance", "accessibility_affordance", "affordance_root", "accessibility", "ux")):
        return "root"
    return None


def _build_accessibility_ux_ir(
    asset: dict[str, Any],
    behavior_ir: dict[str, Any],
    localization_text_ir: dict[str, Any],
    audio_ir: dict[str, Any],
) -> dict[str, Any]:
    roots: list[dict[str, Any]] = []
    input_maps: list[dict[str, Any]] = []
    readable_state_cues: list[dict[str, Any]] = []
    contrast_regions: list[dict[str, Any]] = []
    caption_panels: list[dict[str, Any]] = []
    feedback_cues: list[dict[str, Any]] = []
    focus_navigation: list[dict[str, Any]] = []
    option_ports: list[dict[str, Any]] = []
    usability_guards: list[dict[str, Any]] = []
    seen: set[str] = set()
    behavior_affordance_ids = [
        item.get("id") for item in behavior_ir.get("affordances") or []
        if isinstance(item, dict) and item.get("id")
    ]
    for entry in _authored_behavior_texts(asset):
        kind = _accessibility_entry_kind(entry["source_value"])
        if kind is None:
            continue
        node_id = f"{kind}_{entry['slug']}"
        if node_id in seen:
            continue
        seen.add(node_id)
        base = {
            "id": node_id,
            "source": entry["source_path"],
            "source_value": entry["source_value"],
            "action_ids": _quest_action_ids(behavior_ir, entry["source_value"], {"accessibility", "localize", "audio_cue", "use", "inspect"}),
        }
        if kind == "root":
            roots.append({**base, "input_map_ids": [], "option_port_ids": [], "guard_ids": []})
        elif kind == "input_map":
            input_maps.append({**base, "affordance_ids": behavior_affordance_ids})
        elif kind == "readable_cue":
            readable_state_cues.append({**base, "state_ids": [item.get("id") for item in behavior_ir.get("state_variables") or [] if isinstance(item, dict)]})
        elif kind == "contrast_region":
            contrast_regions.append({**base, "contrast_policy": "safe_region"})
        elif kind == "caption_panel":
            caption_panels.append(
                {
                    **base,
                    "subtitle_timing_ids": [item.get("id") for item in localization_text_ir.get("subtitle_timings") or [] if isinstance(item, dict)],
                    "string_key_ids": [item.get("id") for item in localization_text_ir.get("string_keys") or [] if isinstance(item, dict)],
                }
            )
        elif kind == "feedback_cue":
            feedback_cues.append(
                {
                    **base,
                    "feedback_modes": ["visual", "audio", "haptic"],
                    "audio_cue_ids": [item.get("id") for item in audio_ir.get("cues") or [] if isinstance(item, dict)],
                }
            )
        elif kind == "focus_navigation":
            focus_navigation.append({**base, "navigation_policy": "ordered_focus"})
        elif kind == "option_port":
            option_ports.append({**base, "option_policy": "runtime_toggle"})
        elif kind == "usability_guard":
            usability_guards.append({**base, "guard_policy": "readability_or_focus"})

    if not roots and (input_maps or readable_state_cues or contrast_regions or caption_panels or feedback_cues or focus_navigation or option_ports):
        roots.append(
            {
                "id": f"accessibility_{_slug_fragment(asset.get('name'), 'asset')}",
                "source": "asset.name",
                "source_value": str(asset.get("name") or ""),
                "action_ids": _quest_action_ids(behavior_ir, str(asset.get("name") or ""), {"accessibility"}),
                "input_map_ids": [],
                "option_port_ids": [],
                "guard_ids": [],
            }
        )
    for root in roots:
        root["input_map_ids"] = [item["id"] for item in input_maps]
        root["option_port_ids"] = [item["id"] for item in option_ports]
        root["guard_ids"] = [item["id"] for item in usability_guards]

    return {
        "schema": "lathe.accessibility_ux_ir.v1",
        "source": "authored_source_intent" if roots or input_maps or caption_panels else "build.execution",
        "roots": roots,
        "input_maps": input_maps,
        "readable_state_cues": readable_state_cues,
        "contrast_regions": contrast_regions,
        "caption_panels": caption_panels,
        "feedback_cues": feedback_cues,
        "focus_navigation": focus_navigation,
        "option_ports": option_ports,
        "usability_guards": usability_guards,
        "bindings": {
            "behavior_affordance_count": len(behavior_affordance_ids),
            "localization_key_count": len(localization_text_ir.get("string_keys") or []),
            "audio_cue_count": len(audio_ir.get("cues") or []),
        },
    }


def _economy_entry_kind(source_value: str) -> str | None:
    token = _token(source_value)
    if _contains_any(token, ("resource_flow", "flow_graph", "resource_node")):
        return "resource_flow"
    if _contains_any(token, ("currency_sink_source", "currency_sink", "currency_source", "currency", "faucet", "drain")):
        return "currency_pair"
    if _contains_any(token, ("loot_drop", "loot_reward", "reward_table", "loot", "reward", "drop_table", "rarity")):
        return "loot_reward"
    if _contains_any(token, ("price_curve", "market_rule", "price", "market", "exchange_rate", "inflation", "vendor_modifier")):
        return "price_curve"
    if _contains_any(token, ("progression_balance", "balance_curve", "progression_tick", "level_curve")):
        return "progression"
    if _contains_any(token, ("spawn_rate", "spawn_modulator", "spawn_tuning", "rate_tuning")):
        return "spawn_modulator"
    if _contains_any(token, ("telemetry_tuning", "telemetry_input", "analytics_input")):
        return "telemetry"
    if _contains_any(token, ("simulation_guard", "economy_guard", "runaway_loop", "missing_sink", "overflow_guard")):
        return "guard"
    if _contains_any(token, ("economy_simulation", "economy_tuning", "simulation_tuning", "balance_manifest", "market_root", "economy", "balance")):
        return "root"
    return None


def _build_economy_simulation_ir(
    asset: dict[str, Any],
    behavior_ir: dict[str, Any],
    persistence_ir: dict[str, Any],
    quest_dialogue_ir: dict[str, Any],
    multiplayer_session_ir: dict[str, Any],
) -> dict[str, Any]:
    roots: list[dict[str, Any]] = []
    resource_flows: list[dict[str, Any]] = []
    currency_pairs: list[dict[str, Any]] = []
    loot_reward_tables: list[dict[str, Any]] = []
    price_curves: list[dict[str, Any]] = []
    progression_tracks: list[dict[str, Any]] = []
    spawn_modulators: list[dict[str, Any]] = []
    telemetry_inputs: list[dict[str, Any]] = []
    validation_guards: list[dict[str, Any]] = []
    seen: set[str] = set()
    quest_reward_ids = [
        item.get("id") for item in quest_dialogue_ir.get("rewards") or []
        if isinstance(item, dict) and item.get("id")
    ]
    persistent_state_ids = [
        item.get("id") for item in persistence_ir.get("persistent_variables") or []
        if isinstance(item, dict) and item.get("id")
    ]
    for entry in _authored_behavior_texts(asset):
        kind = _economy_entry_kind(entry["source_value"])
        if kind is None:
            continue
        node_id = f"{kind}_{entry['slug']}"
        if node_id in seen:
            continue
        seen.add(node_id)
        base = {
            "id": node_id,
            "source": entry["source_path"],
            "source_value": entry["source_value"],
            "action_ids": _quest_action_ids(behavior_ir, entry["source_value"], {"economy_tick", "quest_signal", "pickup", "use"}),
        }
        if kind == "root":
            roots.append({**base, "resource_flow_ids": [], "currency_pair_ids": [], "price_curve_ids": []})
        elif kind == "resource_flow":
            resource_flows.append({**base, "state_ids": persistent_state_ids})
        elif kind == "currency_pair":
            currency_pairs.append({**base, "flow_ids": [], "balance_policy": "sink_source"})
        elif kind == "loot_reward":
            loot_reward_tables.append({**base, "quest_reward_ids": quest_reward_ids})
        elif kind == "price_curve":
            price_curves.append({**base, "curve_policy": "authored_or_static"})
        elif kind == "progression":
            progression_tracks.append({**base, "state_ids": persistent_state_ids, "reward_ids": quest_reward_ids})
        elif kind == "spawn_modulator":
            spawn_modulators.append({**base, "tuning_policy": "rate_curve"})
        elif kind == "telemetry":
            telemetry_inputs.append(
                {
                    **base,
                    "session_ids": [item.get("id") for item in multiplayer_session_ir.get("sessions") or [] if isinstance(item, dict)],
                }
            )
        elif kind == "guard":
            validation_guards.append({**base, "guard_policy": "runaway_or_missing_sink"})

    if not roots and (resource_flows or currency_pairs or loot_reward_tables or price_curves or progression_tracks or spawn_modulators):
        roots.append(
            {
                "id": f"economy_{_slug_fragment(asset.get('name'), 'asset')}",
                "source": "asset.name",
                "source_value": str(asset.get("name") or ""),
                "action_ids": _quest_action_ids(behavior_ir, str(asset.get("name") or ""), {"economy_tick", "quest_signal"}),
                "resource_flow_ids": [],
                "currency_pair_ids": [],
                "price_curve_ids": [],
            }
        )
    for pair in currency_pairs:
        pair["flow_ids"] = [item["id"] for item in resource_flows]
    for root in roots:
        root["resource_flow_ids"] = [item["id"] for item in resource_flows]
        root["currency_pair_ids"] = [item["id"] for item in currency_pairs]
        root["price_curve_ids"] = [item["id"] for item in price_curves]

    return {
        "schema": "lathe.economy_simulation_ir.v1",
        "source": "authored_source_intent" if roots or resource_flows or currency_pairs or loot_reward_tables else "build.execution",
        "roots": roots,
        "resource_flows": resource_flows,
        "currency_pairs": currency_pairs,
        "loot_reward_tables": loot_reward_tables,
        "price_curves": price_curves,
        "progression_tracks": progression_tracks,
        "spawn_modulators": spawn_modulators,
        "telemetry_inputs": telemetry_inputs,
        "validation_guards": validation_guards,
        "bindings": {
            "persistent_variable_count": len(persistent_state_ids),
            "quest_reward_count": len(quest_reward_ids),
            "multiplayer_session_count": len(multiplayer_session_ir.get("sessions") or []),
        },
    }


def _scene_system_entry_kind(source_value: str) -> str | None:
    token = _token(source_value)
    if _contains_any(token, ("scene_hierarchy", "hierarchy", "scene_graph")):
        return "hierarchy"
    if _contains_any(token, ("placement_layer", "placement_anchor", "transform_anchor", "anchor")):
        return "placement_anchor"
    if _contains_any(token, ("spawn_layer", "population_layer", "spawn", "population")):
        return "spawn_layer"
    if _contains_any(token, ("lighting_layer", "camera_bookmark", "bookmark", "lighting")):
        return "lighting_camera"
    if _contains_any(token, ("navmesh_layer", "navigation_region", "nav_region", "navmesh")):
        return "navigation"
    if _contains_any(token, ("environment_volume", "environment_layer", "volume_layer", "weather_volume")):
        return "environment_volume"
    if _contains_any(token, ("streaming_tag", "occlusion_tag", "streaming", "occlusion")):
        return "streaming_tag"
    if _contains_any(token, ("scene_export", "export_target", "engine_export")):
        return "export_target"
    if _contains_any(token, ("scene_validation", "scene_guard", "validation_layer")):
        return "validation_guard"
    if _contains_any(token, ("scene_system_authoring", "scene_authoring_bundle", "scene_system", "scene_authoring")):
        return "root"
    return None


def _build_scene_system_ir(
    asset: dict[str, Any],
    behavior_ir: dict[str, Any],
    camera_cinematic_ir: dict[str, Any],
    runtime_partition_ir: dict[str, Any],
    audio_ir: dict[str, Any],
) -> dict[str, Any]:
    roots: list[dict[str, Any]] = []
    hierarchies: list[dict[str, Any]] = []
    placement_anchors: list[dict[str, Any]] = []
    spawn_layers: list[dict[str, Any]] = []
    lighting_camera_layers: list[dict[str, Any]] = []
    navigation_regions: list[dict[str, Any]] = []
    environment_volumes: list[dict[str, Any]] = []
    streaming_tags: list[dict[str, Any]] = []
    export_targets: list[dict[str, Any]] = []
    validation_guards: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in _authored_behavior_texts(asset):
        kind = _scene_system_entry_kind(entry["source_value"])
        if kind is None:
            continue
        node_id = f"{kind}_{entry['slug']}"
        if node_id in seen:
            continue
        seen.add(node_id)
        base = {
            "id": node_id,
            "source": entry["source_path"],
            "source_value": entry["source_value"],
            "action_ids": _quest_action_ids(behavior_ir, entry["source_value"], {"scene_system", "stream_runtime", "camera_direct", "audio_cue"}),
        }
        if kind == "root":
            roots.append({**base, "hierarchy_ids": [], "placement_anchor_ids": [], "spawn_layer_ids": [], "export_target_ids": []})
        elif kind == "hierarchy":
            hierarchies.append({**base, "root_id": roots[-1]["id"] if roots else "", "placement_anchor_ids": []})
        elif kind == "placement_anchor":
            placement_anchors.append({**base, "hierarchy_id": hierarchies[-1]["id"] if hierarchies else ""})
        elif kind == "spawn_layer":
            spawn_layers.append({**base, "placement_anchor_ids": [], "population_policy": "authored_or_auto"})
        elif kind == "lighting_camera":
            lighting_camera_layers.append(
                {
                    **base,
                    "camera_ids": [item.get("id") for item in camera_cinematic_ir.get("cameras") or [] if isinstance(item, dict)],
                    "sequence_ids": [item.get("id") for item in camera_cinematic_ir.get("sequences") or [] if isinstance(item, dict)],
                }
            )
        elif kind == "navigation":
            navigation_regions.append({**base, "nav_policy": "authored_or_mesh"})
        elif kind == "environment_volume":
            environment_volumes.append({**base, "audio_zone_ids": [item.get("id") for item in audio_ir.get("zones") or [] if isinstance(item, dict)]})
        elif kind == "streaming_tag":
            streaming_tags.append({**base, "partition_ids": [item.get("id") for item in runtime_partition_ir.get("partitions") or [] if isinstance(item, dict)]})
        elif kind == "export_target":
            export_targets.append({**base, "target_policy": "engine_or_package"})
        elif kind == "validation_guard":
            validation_guards.append({**base, "guard_policy": "missing_layer_or_unbound_anchor"})

    if not roots and (hierarchies or placement_anchors or spawn_layers or lighting_camera_layers or navigation_regions or environment_volumes or streaming_tags or export_targets):
        roots.append(
            {
                "id": f"scene_{_slug_fragment(asset.get('name'), 'asset')}",
                "source": "asset.name",
                "source_value": str(asset.get("name") or ""),
                "action_ids": _quest_action_ids(behavior_ir, str(asset.get("name") or ""), {"scene_system", "stream_runtime"}),
                "hierarchy_ids": [],
                "placement_anchor_ids": [],
                "spawn_layer_ids": [],
                "export_target_ids": [],
            }
        )
    if not hierarchies and (placement_anchors or spawn_layers or lighting_camera_layers or navigation_regions):
        hierarchies.append(
            {
                "id": f"hierarchy_{_slug_fragment(asset.get('name'), 'asset')}",
                "source": "asset.name",
                "source_value": str(asset.get("name") or ""),
                "action_ids": _quest_action_ids(behavior_ir, str(asset.get("name") or ""), {"scene_system"}),
                "root_id": roots[0]["id"] if roots else "",
                "placement_anchor_ids": [],
            }
        )
    for hierarchy in hierarchies:
        if not hierarchy.get("root_id") and roots:
            hierarchy["root_id"] = roots[0]["id"]
        hierarchy["placement_anchor_ids"] = [item["id"] for item in placement_anchors if not item.get("hierarchy_id") or item.get("hierarchy_id") == hierarchy["id"]]
    for anchor in placement_anchors:
        if not anchor.get("hierarchy_id") and hierarchies:
            anchor["hierarchy_id"] = hierarchies[0]["id"]
    for spawn_layer in spawn_layers:
        spawn_layer["placement_anchor_ids"] = [item["id"] for item in placement_anchors]
    for root in roots:
        root["hierarchy_ids"] = [item["id"] for item in hierarchies if not item.get("root_id") or item.get("root_id") == root["id"]]
        root["placement_anchor_ids"] = [item["id"] for item in placement_anchors]
        root["spawn_layer_ids"] = [item["id"] for item in spawn_layers]
        root["export_target_ids"] = [item["id"] for item in export_targets]

    return {
        "schema": "lathe.scene_system_ir.v1",
        "source": "authored_source_intent" if roots or hierarchies or placement_anchors else "build.execution",
        "roots": roots,
        "hierarchies": hierarchies,
        "placement_anchors": placement_anchors,
        "spawn_layers": spawn_layers,
        "lighting_camera_layers": lighting_camera_layers,
        "navigation_regions": navigation_regions,
        "environment_volumes": environment_volumes,
        "streaming_tags": streaming_tags,
        "export_targets": export_targets,
        "validation_guards": validation_guards,
        "bindings": {
            "camera_count": len(camera_cinematic_ir.get("cameras") or []),
            "partition_count": len(runtime_partition_ir.get("partitions") or []),
            "audio_zone_count": len(audio_ir.get("zones") or []),
        },
    }


def _prefab_binding_entry_kind(source_value: str) -> str | None:
    token = _token(source_value)
    if _contains_any(token, ("source_asset_slot", "source_slot", "asset_slot", "prefab_slot_binding")):
        return "source_slot"
    if _contains_any(token, ("prefab_parameter_binding", "parameter_binding", "parameter_table", "host_parameter")):
        return "parameter_binding"
    if _contains_any(token, ("prefab_variant_binding", "variant_override", "prefab_override", "override_table")):
        return "variant_override"
    if _contains_any(token, ("prefab_lod_binding", "lod_binding", "lod_streaming")):
        return "lod_binding"
    if _contains_any(token, ("material_binding", "surface_binding", "material_surface")):
        return "material_binding"
    if _contains_any(token, ("collision_binding", "physics_binding", "collision_physics")):
        return "collision_binding"
    if _contains_any(token, ("engine_prefab_binding", "prefab_output_map", "engine_export", "export_target")):
        return "engine_export"
    if _contains_any(token, ("prefab_dependency_binding", "dependency_guard", "update_guard")):
        return "dependency_guard"
    if _contains_any(token, ("procedural_prefab_binding", "prefab_binding", "prefab_root")):
        return "root"
    return None


def _build_procedural_prefab_ir(
    asset: dict[str, Any],
    behavior_ir: dict[str, Any],
    scene_system_ir: dict[str, Any],
    runtime_partition_ir: dict[str, Any],
) -> dict[str, Any]:
    roots: list[dict[str, Any]] = []
    source_slots: list[dict[str, Any]] = []
    parameter_bindings: list[dict[str, Any]] = []
    variant_overrides: list[dict[str, Any]] = []
    lod_bindings: list[dict[str, Any]] = []
    material_bindings: list[dict[str, Any]] = []
    collision_bindings: list[dict[str, Any]] = []
    engine_exports: list[dict[str, Any]] = []
    dependency_guards: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in _authored_behavior_texts(asset):
        kind = _prefab_binding_entry_kind(entry["source_value"])
        if kind is None:
            continue
        node_id = f"{kind}_{entry['slug']}"
        if node_id in seen:
            continue
        seen.add(node_id)
        base = {
            "id": node_id,
            "source": entry["source_path"],
            "source_value": entry["source_value"],
            "action_ids": _quest_action_ids(behavior_ir, entry["source_value"], {"prefab_bind", "scene_system", "stream_runtime", "host_runtime"}),
        }
        if kind == "root":
            roots.append({**base, "source_slot_ids": [], "parameter_binding_ids": [], "variant_override_ids": [], "engine_export_ids": []})
        elif kind == "source_slot":
            source_slots.append({**base, "scene_root_ids": [item.get("id") for item in scene_system_ir.get("roots") or [] if isinstance(item, dict)]})
        elif kind == "parameter_binding":
            parameter_bindings.append({**base, "binding_policy": "host_or_prefab_parameter"})
        elif kind == "variant_override":
            variant_overrides.append({**base, "override_policy": "variant_specific"})
        elif kind == "lod_binding":
            lod_bindings.append({**base, "partition_ids": [item.get("id") for item in runtime_partition_ir.get("partitions") or [] if isinstance(item, dict)]})
        elif kind == "material_binding":
            material_bindings.append({**base, "binding_policy": "material_or_surface"})
        elif kind == "collision_binding":
            collision_bindings.append({**base, "binding_policy": "collision_or_physics"})
        elif kind == "engine_export":
            engine_exports.append({**base, "engine_policy": "registered_adapter"})
        elif kind == "dependency_guard":
            dependency_guards.append({**base, "guard_policy": "dependency_update"})

    if not roots and (source_slots or parameter_bindings or variant_overrides or lod_bindings or material_bindings or collision_bindings or engine_exports):
        roots.append(
            {
                "id": f"prefab_{_slug_fragment(asset.get('name'), 'asset')}",
                "source": "asset.name",
                "source_value": str(asset.get("name") or ""),
                "action_ids": _quest_action_ids(behavior_ir, str(asset.get("name") or ""), {"prefab_bind"}),
                "source_slot_ids": [],
                "parameter_binding_ids": [],
                "variant_override_ids": [],
                "engine_export_ids": [],
            }
        )
    for root in roots:
        root["source_slot_ids"] = [item["id"] for item in source_slots]
        root["parameter_binding_ids"] = [item["id"] for item in parameter_bindings]
        root["variant_override_ids"] = [item["id"] for item in variant_overrides]
        root["engine_export_ids"] = [item["id"] for item in engine_exports]

    return {
        "schema": "lathe.procedural_prefab_ir.v1",
        "source": "authored_source_intent" if roots or source_slots or parameter_bindings else "build.execution",
        "roots": roots,
        "source_slots": source_slots,
        "parameter_bindings": parameter_bindings,
        "variant_overrides": variant_overrides,
        "lod_bindings": lod_bindings,
        "material_bindings": material_bindings,
        "collision_bindings": collision_bindings,
        "engine_exports": engine_exports,
        "dependency_guards": dependency_guards,
        "bindings": {
            "scene_root_count": len(scene_system_ir.get("roots") or []),
            "runtime_partition_count": len(runtime_partition_ir.get("partitions") or []),
        },
    }


def _engine_runtime_entry_kind(source_value: str) -> str | None:
    token = _token(source_value)
    if _contains_any(token, ("unity_lathe_plugin", "unreal_lathe_plugin", "usd_hydra_procedural", "hydra_generative")):
        return "host_target"
    if _contains_any(token, ("engine_plugin_binding", "dcc_runtime_adapter", "plugin_adapter", "adapter_contract")):
        return "plugin_adapter"
    if _contains_any(token, ("lathe_bundle_runtime", "bundle_manifest", "lathe_bundle")):
        return "bundle_manifest"
    if _contains_any(token, ("host_parameter_override", "parameter_override", "override_schema")):
        return "parameter_override"
    if _contains_any(token, ("live_evaluation_hook", "live_eval", "engine_hook", "runtime_hook")):
        return "live_hook"
    if _contains_any(token, ("engine_asset_sink", "asset_sink", "output_sink")):
        return "asset_sink"
    if _contains_any(token, ("runtime_host_contract", "host_contract", "abi_guard", "version_guard")):
        return "host_contract"
    if _contains_any(token, ("runtime_diagnostic", "diagnostics_port", "diagnostic_port")):
        return "diagnostics_port"
    if _contains_any(token, ("engine_facing_runtime", "engine_runtime_bundle", "runtime_bundle")):
        return "runtime_root"
    return None


def _build_engine_runtime_ir(
    asset: dict[str, Any],
    behavior_ir: dict[str, Any],
    scene_system_ir: dict[str, Any],
    procedural_prefab_ir: dict[str, Any],
    runtime_partition_ir: dict[str, Any],
    multiplayer_session_ir: dict[str, Any],
) -> dict[str, Any]:
    runtime_roots: list[dict[str, Any]] = []
    host_targets: list[dict[str, Any]] = []
    plugin_adapters: list[dict[str, Any]] = []
    bundle_manifests: list[dict[str, Any]] = []
    parameter_overrides: list[dict[str, Any]] = []
    live_hooks: list[dict[str, Any]] = []
    asset_sinks: list[dict[str, Any]] = []
    host_contracts: list[dict[str, Any]] = []
    diagnostics_ports: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in _authored_behavior_texts(asset):
        kind = _engine_runtime_entry_kind(entry["source_value"])
        if kind is None:
            continue
        node_id = f"{kind}_{entry['slug']}"
        if node_id in seen:
            continue
        seen.add(node_id)
        base = {
            "id": node_id,
            "source": entry["source_path"],
            "source_value": entry["source_value"],
            "action_ids": _quest_action_ids(behavior_ir, entry["source_value"], {"host_runtime", "prefab_bind", "scene_system", "stream_runtime", "network_sync"}),
        }
        if kind == "runtime_root":
            runtime_roots.append({**base, "host_target_ids": [], "plugin_adapter_ids": [], "bundle_manifest_ids": [], "asset_sink_ids": []})
        elif kind == "host_target":
            host_targets.append({**base, "target_policy": "engine_or_dcc"})
        elif kind == "plugin_adapter":
            plugin_adapters.append({**base, "host_target_ids": []})
        elif kind == "bundle_manifest":
            bundle_manifests.append(
                {
                    **base,
                    "scene_root_ids": [item.get("id") for item in scene_system_ir.get("roots") or [] if isinstance(item, dict)],
                    "prefab_root_ids": [item.get("id") for item in procedural_prefab_ir.get("roots") or [] if isinstance(item, dict)],
                }
            )
        elif kind == "parameter_override":
            parameter_overrides.append({**base, "prefab_parameter_ids": [item.get("id") for item in procedural_prefab_ir.get("parameter_bindings") or [] if isinstance(item, dict)]})
        elif kind == "live_hook":
            live_hooks.append({**base, "partition_ids": [item.get("id") for item in runtime_partition_ir.get("partitions") or [] if isinstance(item, dict)]})
        elif kind == "asset_sink":
            asset_sinks.append({**base, "prefab_export_ids": [item.get("id") for item in procedural_prefab_ir.get("engine_exports") or [] if isinstance(item, dict)]})
        elif kind == "host_contract":
            host_contracts.append({**base, "contract_policy": "version_or_abi"})
        elif kind == "diagnostics_port":
            diagnostics_ports.append({**base, "session_ids": [item.get("id") for item in multiplayer_session_ir.get("sessions") or [] if isinstance(item, dict)]})

    if not runtime_roots and (host_targets or plugin_adapters or bundle_manifests or parameter_overrides or live_hooks or asset_sinks or host_contracts):
        runtime_roots.append(
            {
                "id": f"engine_runtime_{_slug_fragment(asset.get('name'), 'asset')}",
                "source": "asset.name",
                "source_value": str(asset.get("name") or ""),
                "action_ids": _quest_action_ids(behavior_ir, str(asset.get("name") or ""), {"host_runtime"}),
                "host_target_ids": [],
                "plugin_adapter_ids": [],
                "bundle_manifest_ids": [],
                "asset_sink_ids": [],
            }
        )
    for adapter in plugin_adapters:
        adapter["host_target_ids"] = [item["id"] for item in host_targets]
    for root in runtime_roots:
        root["host_target_ids"] = [item["id"] for item in host_targets]
        root["plugin_adapter_ids"] = [item["id"] for item in plugin_adapters]
        root["bundle_manifest_ids"] = [item["id"] for item in bundle_manifests]
        root["asset_sink_ids"] = [item["id"] for item in asset_sinks]

    return {
        "schema": "lathe.engine_runtime_ir.v1",
        "source": "authored_source_intent" if runtime_roots or host_targets or plugin_adapters else "build.execution",
        "runtime_roots": runtime_roots,
        "host_targets": host_targets,
        "plugin_adapters": plugin_adapters,
        "bundle_manifests": bundle_manifests,
        "parameter_overrides": parameter_overrides,
        "live_hooks": live_hooks,
        "asset_sinks": asset_sinks,
        "host_contracts": host_contracts,
        "diagnostics_ports": diagnostics_ports,
        "bindings": {
            "scene_root_count": len(scene_system_ir.get("roots") or []),
            "prefab_root_count": len(procedural_prefab_ir.get("roots") or []),
            "runtime_partition_count": len(runtime_partition_ir.get("partitions") or []),
            "multiplayer_session_count": len(multiplayer_session_ir.get("sessions") or []),
        },
    }


def _behavior_logic_entry_kind(source_value: str) -> str | None:
    token = _token(source_value)
    if _contains_any(token, ("state_logic", "state_node", "behavior_node", "logic_node", "state_machine")):
        return "state_node"
    if _contains_any(token, ("event_action", "event_signal", "signal_edge", "event_edge")):
        return "event_edge"
    if _contains_any(token, ("condition_rule", "condition_table", "rule_table")):
        return "condition_rule"
    if _contains_any(token, ("action_output", "output_port", "action_port")):
        return "action_port"
    if _contains_any(token, ("blackboard", "memory_binding", "blackboard_binding", "fact_store")):
        return "blackboard"
    if _contains_any(token, ("timer", "cooldown", "timer_track")):
        return "timer"
    if _contains_any(token, ("utility_ai", "utility_weight", "priority_weight", "priority")):
        return "utility_weight"
    if _contains_any(token, ("failure_path", "fallback_path", "fallback", "recovery_path")):
        return "fallback"
    if _contains_any(token, ("debug_trace", "trace_port", "logic_debug")):
        return "debug_port"
    if _contains_any(token, ("behavior_logic_graph", "behavior_graph", "logic_graph", "scriptless_behavior")):
        return "graph"
    return None


def _build_behavior_logic_ir(
    asset: dict[str, Any],
    behavior_ir: dict[str, Any],
    persistence_ir: dict[str, Any],
) -> dict[str, Any]:
    graphs: list[dict[str, Any]] = []
    state_nodes: list[dict[str, Any]] = []
    event_edges: list[dict[str, Any]] = []
    condition_rules: list[dict[str, Any]] = []
    action_ports: list[dict[str, Any]] = []
    blackboard_bindings: list[dict[str, Any]] = []
    timer_tracks: list[dict[str, Any]] = []
    utility_weights: list[dict[str, Any]] = []
    fallback_paths: list[dict[str, Any]] = []
    debug_ports: list[dict[str, Any]] = []
    seen: set[str] = set()
    behavior_action_ids = [
        item.get("id") for item in behavior_ir.get("actions") or []
        if isinstance(item, dict) and item.get("id")
    ]
    persistent_state_ids = [
        item.get("id") for item in persistence_ir.get("persistent_variables") or []
        if isinstance(item, dict) and item.get("id")
    ]
    for entry in _authored_behavior_texts(asset):
        kind = _behavior_logic_entry_kind(entry["source_value"])
        if kind is None:
            continue
        node_id = f"{kind}_{entry['slug']}"
        if node_id in seen:
            continue
        seen.add(node_id)
        base = {
            "id": node_id,
            "source": entry["source_path"],
            "source_value": entry["source_value"],
            "action_ids": _quest_action_ids(behavior_ir, entry["source_value"], {"behavior_logic", "use", "inspect", "quest_signal", "encounter_flow"}),
        }
        if kind == "graph":
            graphs.append({**base, "state_node_ids": [], "event_edge_ids": [], "condition_rule_ids": [], "action_port_ids": []})
        elif kind == "state_node":
            state_nodes.append({**base, "state_ids": persistent_state_ids})
        elif kind == "event_edge":
            event_edges.append({**base, "source_action_ids": behavior_action_ids})
        elif kind == "condition_rule":
            condition_rules.append({**base, "state_ids": persistent_state_ids})
        elif kind == "action_port":
            action_ports.append({**base, "target_action_ids": behavior_action_ids})
        elif kind == "blackboard":
            blackboard_bindings.append({**base, "state_ids": persistent_state_ids})
        elif kind == "timer":
            timer_tracks.append({**base, "clock_policy": "cooldown_or_interval"})
        elif kind == "utility_weight":
            utility_weights.append({**base, "weight_policy": "priority_or_score"})
        elif kind == "fallback":
            fallback_paths.append({**base, "fallback_policy": "failure_recovery"})
        elif kind == "debug_port":
            debug_ports.append({**base, "trace_policy": "runtime_debug"})

    if not graphs and (state_nodes or event_edges or condition_rules or action_ports or blackboard_bindings or timer_tracks or utility_weights):
        graphs.append(
            {
                "id": f"behavior_logic_{_slug_fragment(asset.get('name'), 'asset')}",
                "source": "asset.name",
                "source_value": str(asset.get("name") or ""),
                "action_ids": _quest_action_ids(behavior_ir, str(asset.get("name") or ""), {"behavior_logic", "use"}),
                "state_node_ids": [],
                "event_edge_ids": [],
                "condition_rule_ids": [],
                "action_port_ids": [],
            }
        )
    for graph in graphs:
        graph["state_node_ids"] = [item["id"] for item in state_nodes]
        graph["event_edge_ids"] = [item["id"] for item in event_edges]
        graph["condition_rule_ids"] = [item["id"] for item in condition_rules]
        graph["action_port_ids"] = [item["id"] for item in action_ports]

    return {
        "schema": "lathe.behavior_logic_ir.v1",
        "source": "authored_source_intent" if graphs or state_nodes or event_edges else "build.execution",
        "graphs": graphs,
        "state_nodes": state_nodes,
        "event_edges": event_edges,
        "condition_rules": condition_rules,
        "action_ports": action_ports,
        "blackboard_bindings": blackboard_bindings,
        "timer_tracks": timer_tracks,
        "utility_weights": utility_weights,
        "fallback_paths": fallback_paths,
        "debug_ports": debug_ports,
        "bindings": {
            "behavior_action_count": len(behavior_action_ids),
            "persistent_state_count": len(persistent_state_ids),
        },
    }


def _encounter_entry_kind(source_value: str) -> str | None:
    token = _token(source_value)
    if _contains_any(token, ("arena", "encounter_footprint", "combat_space", "encounter_bounds")):
        return "footprint"
    if _contains_any(token, ("spawn_point", "spawn_socket", "entry_point", "reinforcement")):
        return "spawn_point"
    if _contains_any(token, ("patrol", "route", "route_line", "path")):
        return "route"
    if _contains_any(token, ("cover", "safety_zone", "safe_zone", "cover_zone")):
        return "cover_zone"
    if _contains_any(token, ("objective", "encounter_objective", "goal_anchor")):
        return "objective"
    if _contains_any(token, ("wave", "escalation", "combat_phase", "boss")):
        return "wave"
    if _contains_any(token, ("reward_exit", "reward_zone", "exit_zone", "loot_exit")):
        return "reward_exit"
    if _contains_any(token, ("hazard", "boundary", "hazard_boundary", "threat_zone")):
        return "hazard"
    if _contains_any(token, ("readability", "flow_arrow", "cue")):
        return "readability"
    if _contains_any(token, ("encounter", "encounter_flow", "combat", "ambush")):
        return "root"
    return None


def _build_encounter_flow_ir(
    asset: dict[str, Any],
    behavior_ir: dict[str, Any],
    quest_dialogue_ir: dict[str, Any],
    scene_system_ir: dict[str, Any],
    behavior_logic_ir: dict[str, Any],
) -> dict[str, Any]:
    roots: list[dict[str, Any]] = []
    footprints: list[dict[str, Any]] = []
    spawn_points: list[dict[str, Any]] = []
    patrol_routes: list[dict[str, Any]] = []
    cover_zones: list[dict[str, Any]] = []
    objectives: list[dict[str, Any]] = []
    waves: list[dict[str, Any]] = []
    reward_exit_zones: list[dict[str, Any]] = []
    hazard_boundaries: list[dict[str, Any]] = []
    readability_cues: list[dict[str, Any]] = []
    seen: set[str] = set()
    quest_objective_ids = [
        item.get("id") for item in quest_dialogue_ir.get("objectives") or []
        if isinstance(item, dict) and item.get("id")
    ]
    quest_reward_ids = [
        item.get("id") for item in quest_dialogue_ir.get("rewards") or []
        if isinstance(item, dict) and item.get("id")
    ]
    logic_graph_ids = [
        item.get("id") for item in behavior_logic_ir.get("graphs") or []
        if isinstance(item, dict) and item.get("id")
    ]
    scene_root_ids = [
        item.get("id") for item in scene_system_ir.get("roots") or []
        if isinstance(item, dict) and item.get("id")
    ]
    for entry in _authored_behavior_texts(asset):
        kind = _encounter_entry_kind(entry["source_value"])
        if kind is None:
            continue
        node_id = f"{kind}_{entry['slug']}"
        if node_id in seen:
            continue
        seen.add(node_id)
        base = {
            "id": node_id,
            "source": entry["source_path"],
            "source_value": entry["source_value"],
            "action_ids": _quest_action_ids(behavior_ir, entry["source_value"], {"encounter_flow", "quest_signal", "behavior_logic", "scene_system"}),
        }
        if kind == "root":
            roots.append({**base, "footprint_ids": [], "spawn_point_ids": [], "route_ids": [], "objective_ids": [], "wave_ids": []})
        elif kind == "footprint":
            footprints.append({**base, "scene_root_ids": scene_root_ids})
        elif kind == "spawn_point":
            spawn_points.append({**base, "scene_root_ids": scene_root_ids})
        elif kind == "route":
            patrol_routes.append({**base, "logic_graph_ids": logic_graph_ids})
        elif kind == "cover_zone":
            cover_zones.append({**base, "cover_policy": "authored_or_runtime"})
        elif kind == "objective":
            objectives.append({**base, "quest_objective_ids": quest_objective_ids})
        elif kind == "wave":
            waves.append({**base, "logic_graph_ids": logic_graph_ids})
        elif kind == "reward_exit":
            reward_exit_zones.append({**base, "quest_reward_ids": quest_reward_ids})
        elif kind == "hazard":
            hazard_boundaries.append({**base, "hazard_policy": "boundary_or_damage"})
        elif kind == "readability":
            readability_cues.append({**base, "cue_policy": "flow_or_silhouette"})

    if not roots and (footprints or spawn_points or patrol_routes or cover_zones or objectives or waves or reward_exit_zones):
        roots.append(
            {
                "id": f"encounter_{_slug_fragment(asset.get('name'), 'asset')}",
                "source": "asset.name",
                "source_value": str(asset.get("name") or ""),
                "action_ids": _quest_action_ids(behavior_ir, str(asset.get("name") or ""), {"encounter_flow", "quest_signal"}),
                "footprint_ids": [],
                "spawn_point_ids": [],
                "route_ids": [],
                "objective_ids": [],
                "wave_ids": [],
            }
        )
    for root in roots:
        root["footprint_ids"] = [item["id"] for item in footprints]
        root["spawn_point_ids"] = [item["id"] for item in spawn_points]
        root["route_ids"] = [item["id"] for item in patrol_routes]
        root["objective_ids"] = [item["id"] for item in objectives]
        root["wave_ids"] = [item["id"] for item in waves]

    return {
        "schema": "lathe.encounter_flow_ir.v1",
        "source": "authored_source_intent" if roots or footprints or spawn_points else "build.execution",
        "roots": roots,
        "footprints": footprints,
        "spawn_points": spawn_points,
        "patrol_routes": patrol_routes,
        "cover_zones": cover_zones,
        "objectives": objectives,
        "waves": waves,
        "reward_exit_zones": reward_exit_zones,
        "hazard_boundaries": hazard_boundaries,
        "readability_cues": readability_cues,
        "bindings": {
            "quest_objective_count": len(quest_objective_ids),
            "quest_reward_count": len(quest_reward_ids),
            "scene_root_count": len(scene_root_ids),
            "behavior_logic_graph_count": len(logic_graph_ids),
        },
    }


def _inventory_entry_kind(source_value: str) -> str | None:
    token = _token(source_value)
    if _contains_any(token, ("container", "stash", "inventory_body", "item_body")):
        return "container"
    if _contains_any(token, ("currency", "coin", "value_marker", "price_marker")):
        return "value_marker"
    if _contains_any(token, ("quantity", "stack", "stack_tick")):
        return "quantity"
    if _contains_any(token, ("rarity", "tier", "rarity_band")):
        return "rarity"
    if _contains_any(token, ("access", "lock", "access_handle", "lock_affordance")):
        return "access"
    if _contains_any(token, ("storage_slot", "slot_grid", "inventory_slot")):
        return "storage_slot"
    if _contains_any(token, ("pickup", "pickup_handle", "use_handle")):
        return "pickup"
    if _contains_any(token, ("vendor", "shop", "merchant", "vendor_label")):
        return "vendor"
    if _contains_any(token, ("resource_port", "resource", "transfer_port")):
        return "resource_port"
    if _contains_any(token, ("inventory", "inventory_economy", "collectible", "item")):
        return "root"
    return None


def _build_inventory_economy_ir(
    asset: dict[str, Any],
    behavior_ir: dict[str, Any],
    persistence_ir: dict[str, Any],
    quest_dialogue_ir: dict[str, Any],
    economy_simulation_ir: dict[str, Any],
) -> dict[str, Any]:
    roots: list[dict[str, Any]] = []
    containers: list[dict[str, Any]] = []
    value_markers: list[dict[str, Any]] = []
    quantity_tracks: list[dict[str, Any]] = []
    rarity_tiers: list[dict[str, Any]] = []
    access_affordances: list[dict[str, Any]] = []
    storage_slots: list[dict[str, Any]] = []
    pickup_handles: list[dict[str, Any]] = []
    vendor_bindings: list[dict[str, Any]] = []
    resource_ports: list[dict[str, Any]] = []
    seen: set[str] = set()
    persistent_state_ids = [
        item.get("id") for item in persistence_ir.get("persistent_variables") or []
        if isinstance(item, dict) and item.get("id")
    ]
    quest_reward_ids = [
        item.get("id") for item in quest_dialogue_ir.get("rewards") or []
        if isinstance(item, dict) and item.get("id")
    ]
    economy_root_ids = [
        item.get("id") for item in economy_simulation_ir.get("roots") or []
        if isinstance(item, dict) and item.get("id")
    ]
    for entry in _authored_behavior_texts(asset):
        kind = _inventory_entry_kind(entry["source_value"])
        if kind is None:
            continue
        node_id = f"{kind}_{entry['slug']}"
        if node_id in seen:
            continue
        seen.add(node_id)
        base = {
            "id": node_id,
            "source": entry["source_path"],
            "source_value": entry["source_value"],
            "action_ids": _quest_action_ids(behavior_ir, entry["source_value"], {"inventory_object", "pickup", "use", "quest_signal", "economy_tick"}),
        }
        if kind == "root":
            roots.append({**base, "container_ids": [], "storage_slot_ids": [], "value_marker_ids": [], "resource_port_ids": []})
        elif kind == "container":
            containers.append({**base, "state_ids": persistent_state_ids})
        elif kind == "value_marker":
            value_markers.append({**base, "economy_root_ids": economy_root_ids})
        elif kind == "quantity":
            quantity_tracks.append({**base, "state_ids": persistent_state_ids})
        elif kind == "rarity":
            rarity_tiers.append({**base, "reward_ids": quest_reward_ids})
        elif kind == "access":
            access_affordances.append({**base, "state_ids": persistent_state_ids})
        elif kind == "storage_slot":
            storage_slots.append({**base, "state_ids": persistent_state_ids})
        elif kind == "pickup":
            pickup_handles.append({**base, "reward_ids": quest_reward_ids})
        elif kind == "vendor":
            vendor_bindings.append({**base, "economy_root_ids": economy_root_ids})
        elif kind == "resource_port":
            resource_ports.append({**base, "economy_root_ids": economy_root_ids})

    if not roots and (containers or value_markers or storage_slots or pickup_handles or vendor_bindings or resource_ports):
        roots.append(
            {
                "id": f"inventory_{_slug_fragment(asset.get('name'), 'asset')}",
                "source": "asset.name",
                "source_value": str(asset.get("name") or ""),
                "action_ids": _quest_action_ids(behavior_ir, str(asset.get("name") or ""), {"inventory_object", "pickup"}),
                "container_ids": [],
                "storage_slot_ids": [],
                "value_marker_ids": [],
                "resource_port_ids": [],
            }
        )
    for root in roots:
        root["container_ids"] = [item["id"] for item in containers]
        root["storage_slot_ids"] = [item["id"] for item in storage_slots]
        root["value_marker_ids"] = [item["id"] for item in value_markers]
        root["resource_port_ids"] = [item["id"] for item in resource_ports]

    return {
        "schema": "lathe.inventory_economy_ir.v1",
        "source": "authored_source_intent" if roots or containers or value_markers else "build.execution",
        "roots": roots,
        "containers": containers,
        "value_markers": value_markers,
        "quantity_tracks": quantity_tracks,
        "rarity_tiers": rarity_tiers,
        "access_affordances": access_affordances,
        "storage_slots": storage_slots,
        "pickup_handles": pickup_handles,
        "vendor_bindings": vendor_bindings,
        "resource_ports": resource_ports,
        "bindings": {
            "persistent_state_count": len(persistent_state_ids),
            "quest_reward_count": len(quest_reward_ids),
            "economy_root_count": len(economy_root_ids),
        },
    }


def _world_system_entry_kind(source_value: str) -> str | None:
    token = _token(source_value)
    if _contains_any(token, ("world_footprint", "root_world", "world_root", "world_system")):
        return "root"
    if _contains_any(token, ("world_layer", "region_layer", "region", "layer_stack")):
        return "region_layer"
    if _contains_any(token, ("route_network", "route_graph", "navigation", "navmesh", "nav_mesh")):
        return "route_graph"
    if _contains_any(token, ("faction", "rule_zone", "civilization", "law", "policy")):
        return "rule_zone"
    if _contains_any(token, ("quest_chain", "progression_chain", "progression")):
        return "progression_chain"
    if _contains_any(token, ("resource_distribution", "spawn_distribution", "resource", "spawn")):
        return "resource_spawn"
    if _contains_any(token, ("landmark", "point_of_interest", "poi")):
        return "landmark"
    if _contains_any(token, ("transition_gate", "gate", "world_transition")):
        return "transition_gate"
    if _contains_any(token, ("label", "debug_cue", "world_metric")):
        return "debug_label"
    return None


def _build_world_system_ir(
    asset: dict[str, Any],
    behavior_ir: dict[str, Any],
    scene_system_ir: dict[str, Any],
    encounter_flow_ir: dict[str, Any],
    economy_simulation_ir: dict[str, Any],
    inventory_economy_ir: dict[str, Any],
    runtime_partition_ir: dict[str, Any],
) -> dict[str, Any]:
    roots: list[dict[str, Any]] = []
    region_layers: list[dict[str, Any]] = []
    route_graphs: list[dict[str, Any]] = []
    faction_rule_zones: list[dict[str, Any]] = []
    progression_chains: list[dict[str, Any]] = []
    resource_spawn_distributions: list[dict[str, Any]] = []
    landmarks: list[dict[str, Any]] = []
    transition_gates: list[dict[str, Any]] = []
    debug_labels: list[dict[str, Any]] = []
    usage_masks: list[dict[str, Any]] = []
    seen: set[str] = set()
    scene_root_ids = [item.get("id") for item in scene_system_ir.get("roots") or [] if isinstance(item, dict)]
    encounter_ids = [item.get("id") for item in encounter_flow_ir.get("roots") or [] if isinstance(item, dict)]
    economy_ids = [item.get("id") for item in economy_simulation_ir.get("roots") or [] if isinstance(item, dict)]
    inventory_ids = [item.get("id") for item in inventory_economy_ir.get("roots") or [] if isinstance(item, dict)]
    partition_ids = [item.get("id") for item in runtime_partition_ir.get("partitions") or [] if isinstance(item, dict)]
    for entry in _authored_behavior_texts(asset):
        kind = _world_system_entry_kind(entry["source_value"])
        if kind is None:
            continue
        node_id = f"{kind}_{entry['slug']}"
        if node_id in seen:
            continue
        seen.add(node_id)
        base = {
            "id": node_id,
            "source": entry["source_path"],
            "source_value": entry["source_value"],
            "action_ids": _quest_action_ids(behavior_ir, entry["source_value"], {"world_system", "scene_system", "encounter_flow", "economy_tick"}),
        }
        if kind == "root":
            roots.append({**base, "region_layer_ids": [], "route_graph_ids": [], "progression_chain_ids": [], "transition_gate_ids": []})
        elif kind == "region_layer":
            region_layers.append({**base, "scene_root_ids": scene_root_ids, "partition_ids": partition_ids})
        elif kind == "route_graph":
            route_graphs.append({**base, "scene_root_ids": scene_root_ids, "encounter_ids": encounter_ids})
        elif kind == "rule_zone":
            faction_rule_zones.append({**base, "scene_root_ids": scene_root_ids})
        elif kind == "progression_chain":
            progression_chains.append({**base, "encounter_ids": encounter_ids})
        elif kind == "resource_spawn":
            resource_spawn_distributions.append({**base, "economy_root_ids": economy_ids, "inventory_root_ids": inventory_ids})
        elif kind == "landmark":
            landmarks.append({**base, "scene_root_ids": scene_root_ids})
        elif kind == "transition_gate":
            transition_gates.append({**base, "partition_ids": partition_ids})
        elif kind == "debug_label":
            debug_labels.append({**base, "label_policy": "debug_or_metric"})

    if not roots and (region_layers or route_graphs or faction_rule_zones or progression_chains or resource_spawn_distributions or landmarks or transition_gates):
        roots.append(
            {
                "id": f"world_system_{_slug_fragment(asset.get('name'), 'asset')}",
                "source": "asset.name",
                "source_value": str(asset.get("name") or ""),
                "action_ids": _quest_action_ids(behavior_ir, str(asset.get("name") or ""), {"world_system"}),
                "region_layer_ids": [],
                "route_graph_ids": [],
                "progression_chain_ids": [],
                "transition_gate_ids": [],
            }
        )
    if roots:
        usage_masks.append(
            {
                "id": f"usage_{roots[0]['id']}",
                "source": "world_system_ir",
                "source_value": "world_usage",
                "action_ids": [],
                "usage_policy": "authored_or_inferred",
            }
        )
    for root in roots:
        root["region_layer_ids"] = [item["id"] for item in region_layers]
        root["route_graph_ids"] = [item["id"] for item in route_graphs]
        root["progression_chain_ids"] = [item["id"] for item in progression_chains]
        root["transition_gate_ids"] = [item["id"] for item in transition_gates]

    return {
        "schema": "lathe.world_system_ir.v1",
        "source": "authored_source_intent" if roots or region_layers or route_graphs else "build.execution",
        "roots": roots,
        "region_layers": region_layers,
        "route_graphs": route_graphs,
        "faction_rule_zones": faction_rule_zones,
        "progression_chains": progression_chains,
        "resource_spawn_distributions": resource_spawn_distributions,
        "landmarks": landmarks,
        "transition_gates": transition_gates,
        "debug_labels": debug_labels,
        "usage_masks": usage_masks,
        "bindings": {
            "scene_root_count": len(scene_root_ids),
            "encounter_count": len(encounter_ids),
            "economy_root_count": len(economy_ids),
            "partition_count": len(partition_ids),
        },
    }


def _simulation_entry_kind(source_value: str) -> str | None:
    token = _token(source_value)
    if _contains_any(token, ("domain_bounds", "domain_bound", "simulation_bounds")):
        return "domain_bound"
    if _contains_any(token, ("simulation", "sim_system", "simulation_domain", "domain_bounds")):
        return "root"
    if _contains_any(token, ("emitter", "force_source", "source", "particle_system")):
        return "emitter"
    if _contains_any(token, ("flow_field", "wind_field", "vector", "flow_line")):
        return "flow_vector"
    if _contains_any(token, ("heat_field", "pressure_field", "field_gradient", "gradient")):
        return "field_gradient"
    if _contains_any(token, ("constraint_solver", "erosion_solver", "fluid_solver", "solver_constraint")):
        return "solver_constraint"
    if _contains_any(token, ("probe", "sample", "simulation_probe")):
        return "probe"
    if _contains_any(token, ("obstacle", "collision_boundary", "boundary")):
        return "obstacle_boundary"
    if _contains_any(token, ("temporal_marker", "time_marker", "tick")):
        return "temporal_marker"
    if _contains_any(token, ("material_response", "response_output", "weather_system", "weather")):
        return "material_response"
    return None


def _build_simulation_environment_ir(
    asset: dict[str, Any],
    behavior_ir: dict[str, Any],
    scene_system_ir: dict[str, Any],
    world_system_ir: dict[str, Any],
    runtime_partition_ir: dict[str, Any],
) -> dict[str, Any]:
    roots: list[dict[str, Any]] = []
    domain_bounds: list[dict[str, Any]] = []
    emitters: list[dict[str, Any]] = []
    flow_vectors: list[dict[str, Any]] = []
    field_gradients: list[dict[str, Any]] = []
    solver_constraints: list[dict[str, Any]] = []
    probes: list[dict[str, Any]] = []
    obstacle_boundaries: list[dict[str, Any]] = []
    temporal_markers: list[dict[str, Any]] = []
    material_responses: list[dict[str, Any]] = []
    wear_masks: list[dict[str, Any]] = []
    seen: set[str] = set()
    scene_root_ids = [item.get("id") for item in scene_system_ir.get("roots") or [] if isinstance(item, dict)]
    world_root_ids = [item.get("id") for item in world_system_ir.get("roots") or [] if isinstance(item, dict)]
    partition_ids = [item.get("id") for item in runtime_partition_ir.get("partitions") or [] if isinstance(item, dict)]
    for entry in _authored_behavior_texts(asset):
        kind = _simulation_entry_kind(entry["source_value"])
        if kind is None:
            continue
        node_id = f"{kind}_{entry['slug']}"
        if node_id in seen:
            continue
        seen.add(node_id)
        base = {
            "id": node_id,
            "source": entry["source_path"],
            "source_value": entry["source_value"],
            "action_ids": _quest_action_ids(behavior_ir, entry["source_value"], {"simulation_env", "world_system", "scene_system"}),
        }
        if kind == "root":
            roots.append({**base, "domain_bound_ids": [], "emitter_ids": [], "flow_vector_ids": [], "solver_constraint_ids": [], "probe_ids": []})
        elif kind == "domain_bound":
            domain_bounds.append({**base, "scene_root_ids": scene_root_ids, "partition_ids": partition_ids})
        elif kind == "emitter":
            emitters.append({**base, "scene_root_ids": scene_root_ids})
        elif kind == "flow_vector":
            flow_vectors.append({**base, "world_root_ids": world_root_ids})
        elif kind == "field_gradient":
            field_gradients.append({**base, "partition_ids": partition_ids})
        elif kind == "solver_constraint":
            solver_constraints.append({**base, "solver_policy": "authored_or_default"})
        elif kind == "probe":
            probes.append({**base, "sample_policy": "runtime_metric"})
        elif kind == "obstacle_boundary":
            obstacle_boundaries.append({**base, "scene_root_ids": scene_root_ids})
        elif kind == "temporal_marker":
            temporal_markers.append({**base, "tick_policy": "simulation_tick"})
        elif kind == "material_response":
            material_responses.append({**base, "response_policy": "material_or_weather"})

    if not roots and (domain_bounds or emitters or flow_vectors or field_gradients or solver_constraints or probes or obstacle_boundaries or material_responses):
        roots.append(
            {
                "id": f"simulation_{_slug_fragment(asset.get('name'), 'asset')}",
                "source": "asset.name",
                "source_value": str(asset.get("name") or ""),
                "action_ids": _quest_action_ids(behavior_ir, str(asset.get("name") or ""), {"simulation_env"}),
                "domain_bound_ids": [],
                "emitter_ids": [],
                "flow_vector_ids": [],
                "solver_constraint_ids": [],
                "probe_ids": [],
            }
        )
    if roots:
        wear_masks.append({"id": f"wear_{roots[0]['id']}", "source": "simulation_environment_ir", "source_value": "simulation_wear", "action_ids": [], "wear_policy": "iteration_or_response"})
    for root in roots:
        root["domain_bound_ids"] = [item["id"] for item in domain_bounds]
        root["emitter_ids"] = [item["id"] for item in emitters]
        root["flow_vector_ids"] = [item["id"] for item in flow_vectors]
        root["solver_constraint_ids"] = [item["id"] for item in solver_constraints]
        root["probe_ids"] = [item["id"] for item in probes]

    return {
        "schema": "lathe.simulation_environment_ir.v1",
        "source": "authored_source_intent" if roots or domain_bounds or emitters or flow_vectors else "build.execution",
        "roots": roots,
        "domain_bounds": domain_bounds,
        "emitters": emitters,
        "flow_vectors": flow_vectors,
        "field_gradients": field_gradients,
        "solver_constraints": solver_constraints,
        "probes": probes,
        "obstacle_boundaries": obstacle_boundaries,
        "temporal_markers": temporal_markers,
        "material_responses": material_responses,
        "wear_masks": wear_masks,
        "bindings": {
            "scene_root_count": len(scene_root_ids),
            "world_root_count": len(world_root_ids),
            "partition_count": len(partition_ids),
        },
    }


def _stateful_entry_kind(source_value: str) -> str | None:
    token = _token(source_value)
    if _contains_any(token, ("destructible", "stateful", "state_machine", "damageable")):
        return "root"
    if _contains_any(token, ("intact", "shell", "intact_shell")):
        return "intact_shell"
    if _contains_any(token, ("damage_state", "health", "health_pip", "cracked", "ruined")):
        return "damage_state"
    if _contains_any(token, ("fracture", "break_line", "crack")):
        return "fracture_line"
    if _contains_any(token, ("fragment", "detachable", "debris")):
        return "fragment_zone"
    if _contains_any(token, ("weak_point", "weakness")):
        return "weak_point"
    if _contains_any(token, ("repair", "repair_affordance")):
        return "repair"
    if _contains_any(token, ("transition", "state_transition")):
        return "transition_cue"
    if _contains_any(token, ("hazard", "failure_boundary")):
        return "hazard"
    return None


def _build_stateful_destructible_ir(
    asset: dict[str, Any],
    behavior_ir: dict[str, Any],
    persistence_ir: dict[str, Any],
    encounter_flow_ir: dict[str, Any],
    inventory_economy_ir: dict[str, Any],
) -> dict[str, Any]:
    roots: list[dict[str, Any]] = []
    intact_shells: list[dict[str, Any]] = []
    damage_states: list[dict[str, Any]] = []
    fracture_lines: list[dict[str, Any]] = []
    fragment_zones: list[dict[str, Any]] = []
    weak_points: list[dict[str, Any]] = []
    repair_affordances: list[dict[str, Any]] = []
    transition_cues: list[dict[str, Any]] = []
    hazard_boundaries: list[dict[str, Any]] = []
    debris_scatters: list[dict[str, Any]] = []
    wear_masks: list[dict[str, Any]] = []
    seen: set[str] = set()
    state_ids = [item.get("id") for item in persistence_ir.get("persistent_variables") or [] if isinstance(item, dict)]
    encounter_ids = [item.get("id") for item in encounter_flow_ir.get("roots") or [] if isinstance(item, dict)]
    inventory_ids = [item.get("id") for item in inventory_economy_ir.get("roots") or [] if isinstance(item, dict)]
    for entry in _authored_behavior_texts(asset):
        kind = _stateful_entry_kind(entry["source_value"])
        if kind is None:
            continue
        node_id = f"{kind}_{entry['slug']}"
        if node_id in seen:
            continue
        seen.add(node_id)
        base = {
            "id": node_id,
            "source": entry["source_path"],
            "source_value": entry["source_value"],
            "action_ids": _quest_action_ids(behavior_ir, entry["source_value"], {"destructible_state", "damage", "repair", "encounter_flow", "use"}),
        }
        if kind == "root":
            roots.append({**base, "damage_state_ids": [], "fracture_line_ids": [], "weak_point_ids": [], "repair_affordance_ids": []})
        elif kind == "intact_shell":
            intact_shells.append({**base, "state_ids": state_ids})
        elif kind == "damage_state":
            damage_states.append({**base, "state_ids": state_ids})
        elif kind == "fracture_line":
            fracture_lines.append({**base, "state_ids": state_ids})
        elif kind == "fragment_zone":
            fragment_zones.append({**base, "debris_policy": "detachable_or_spawned"})
            debris_scatters.append({**base, "id": f"debris_{entry['slug']}", "scatter_policy": "fragment_debris"})
        elif kind == "weak_point":
            weak_points.append({**base, "encounter_ids": encounter_ids, "reward_root_ids": inventory_ids})
        elif kind == "repair":
            repair_affordances.append({**base, "state_ids": state_ids})
        elif kind == "transition_cue":
            transition_cues.append({**base, "state_ids": state_ids})
        elif kind == "hazard":
            hazard_boundaries.append({**base, "encounter_ids": encounter_ids})

    if not roots and (intact_shells or damage_states or fracture_lines or fragment_zones or weak_points or repair_affordances):
        roots.append(
            {
                "id": f"destructible_{_slug_fragment(asset.get('name'), 'asset')}",
                "source": "asset.name",
                "source_value": str(asset.get("name") or ""),
                "action_ids": _quest_action_ids(behavior_ir, str(asset.get("name") or ""), {"destructible_state", "damage", "repair"}),
                "damage_state_ids": [],
                "fracture_line_ids": [],
                "weak_point_ids": [],
                "repair_affordance_ids": [],
            }
        )
    if roots:
        wear_masks.append({"id": f"wear_{roots[0]['id']}", "source": "stateful_destructible_ir", "source_value": "damage_wear", "action_ids": [], "wear_policy": "damage_or_repair"})
    for root in roots:
        root["damage_state_ids"] = [item["id"] for item in damage_states]
        root["fracture_line_ids"] = [item["id"] for item in fracture_lines]
        root["weak_point_ids"] = [item["id"] for item in weak_points]
        root["repair_affordance_ids"] = [item["id"] for item in repair_affordances]

    return {
        "schema": "lathe.stateful_destructible_ir.v1",
        "source": "authored_source_intent" if roots or damage_states or fracture_lines else "build.execution",
        "roots": roots,
        "intact_shells": intact_shells,
        "damage_states": damage_states,
        "fracture_lines": fracture_lines,
        "fragment_zones": fragment_zones,
        "weak_points": weak_points,
        "repair_affordances": repair_affordances,
        "transition_cues": transition_cues,
        "hazard_boundaries": hazard_boundaries,
        "debris_scatters": debris_scatters,
        "wear_masks": wear_masks,
        "bindings": {
            "persistent_state_count": len(state_ids),
            "encounter_count": len(encounter_ids),
            "inventory_root_count": len(inventory_ids),
        },
    }


def _live_runtime_entry_kind(source_value: str) -> str | None:
    token = _token(source_value)
    if _contains_any(token, ("live_procedural", "runtime_bundle", "lathe_engine", "procedural_runtime")):
        return "core"
    if _contains_any(token, ("input_parameter", "input_port", "parameter_port")):
        return "input_port"
    if _contains_any(token, ("engine_hook", "hook")):
        return "engine_hook"
    if _contains_any(token, ("output_slot", "output")):
        return "output_slot"
    if _contains_any(token, ("version", "contract_badge", "contract")):
        return "version_contract"
    if _contains_any(token, ("hot_reload", "live_update", "live_tick")):
        return "hot_reload"
    if _contains_any(token, ("validation_guard", "guard")):
        return "validation_guard"
    if _contains_any(token, ("cache", "state_cache", "state_panel")):
        return "cache_state"
    if _contains_any(token, ("metrics", "debug_port", "debug")):
        return "metrics_debug"
    if _contains_any(token, ("runtime_override", "override")):
        return "override"
    return None


def _build_live_procedural_runtime_ir(
    asset: dict[str, Any],
    behavior_ir: dict[str, Any],
    engine_runtime_ir: dict[str, Any],
    procedural_prefab_ir: dict[str, Any],
    world_system_ir: dict[str, Any],
    simulation_environment_ir: dict[str, Any],
) -> dict[str, Any]:
    cores: list[dict[str, Any]] = []
    input_ports: list[dict[str, Any]] = []
    engine_hooks: list[dict[str, Any]] = []
    output_slots: list[dict[str, Any]] = []
    version_contracts: list[dict[str, Any]] = []
    hot_reload_cues: list[dict[str, Any]] = []
    validation_guards: list[dict[str, Any]] = []
    cache_states: list[dict[str, Any]] = []
    metrics_debug_ports: list[dict[str, Any]] = []
    override_wear: list[dict[str, Any]] = []
    seen: set[str] = set()
    engine_root_ids = [item.get("id") for item in engine_runtime_ir.get("runtime_roots") or [] if isinstance(item, dict)]
    prefab_root_ids = [item.get("id") for item in procedural_prefab_ir.get("roots") or [] if isinstance(item, dict)]
    world_root_ids = [item.get("id") for item in world_system_ir.get("roots") or [] if isinstance(item, dict)]
    simulation_root_ids = [item.get("id") for item in simulation_environment_ir.get("roots") or [] if isinstance(item, dict)]
    for entry in _authored_behavior_texts(asset):
        kind = _live_runtime_entry_kind(entry["source_value"])
        if kind is None:
            continue
        node_id = f"{kind}_{entry['slug']}"
        if node_id in seen:
            continue
        seen.add(node_id)
        base = {
            "id": node_id,
            "source": entry["source_path"],
            "source_value": entry["source_value"],
            "action_ids": _quest_action_ids(behavior_ir, entry["source_value"], {"live_runtime", "host_runtime", "prefab_bind", "world_system", "simulation_env"}),
        }
        if kind == "core":
            cores.append({**base, "engine_runtime_ids": engine_root_ids, "prefab_root_ids": prefab_root_ids, "world_root_ids": world_root_ids, "simulation_root_ids": simulation_root_ids})
        elif kind == "input_port":
            input_ports.append({**base, "binding_policy": "host_parameter"})
        elif kind == "engine_hook":
            engine_hooks.append({**base, "engine_runtime_ids": engine_root_ids})
        elif kind == "output_slot":
            output_slots.append({**base, "prefab_root_ids": prefab_root_ids})
        elif kind == "version_contract":
            version_contracts.append({**base, "contract_policy": "versioned_runtime"})
        elif kind == "hot_reload":
            hot_reload_cues.append({**base, "reload_policy": "live_update"})
        elif kind == "validation_guard":
            validation_guards.append({**base, "guard_policy": "runtime_validation"})
        elif kind == "cache_state":
            cache_states.append({**base, "cache_policy": "state_or_artifact"})
        elif kind == "metrics_debug":
            metrics_debug_ports.append({**base, "debug_policy": "metrics_or_trace"})
        elif kind == "override":
            override_wear.append({**base, "override_policy": "runtime_override"})

    if not cores and (input_ports or engine_hooks or output_slots or version_contracts or hot_reload_cues or validation_guards or cache_states or metrics_debug_ports):
        cores.append(
            {
                "id": f"live_runtime_{_slug_fragment(asset.get('name'), 'asset')}",
                "source": "asset.name",
                "source_value": str(asset.get("name") or ""),
                "action_ids": _quest_action_ids(behavior_ir, str(asset.get("name") or ""), {"live_runtime", "host_runtime"}),
                "engine_runtime_ids": engine_root_ids,
                "prefab_root_ids": prefab_root_ids,
                "world_root_ids": world_root_ids,
                "simulation_root_ids": simulation_root_ids,
            }
        )

    return {
        "schema": "lathe.live_procedural_runtime_ir.v1",
        "source": "authored_source_intent" if cores or input_ports or engine_hooks else "build.execution",
        "cores": cores,
        "input_ports": input_ports,
        "engine_hooks": engine_hooks,
        "output_slots": output_slots,
        "version_contracts": version_contracts,
        "hot_reload_cues": hot_reload_cues,
        "validation_guards": validation_guards,
        "cache_states": cache_states,
        "metrics_debug_ports": metrics_debug_ports,
        "override_wear": override_wear,
        "bindings": {
            "engine_runtime_count": len(engine_root_ids),
            "prefab_root_count": len(prefab_root_ids),
            "world_root_count": len(world_root_ids),
            "simulation_root_count": len(simulation_root_ids),
        },
    }


def _record_ids(ir: dict[str, Any], field: str) -> list[Any]:
    return [item.get("id") for item in ir.get(field) or [] if isinstance(item, dict)]


def _authored_ir_record(
    entry: dict[str, str],
    behavior_ir: dict[str, Any],
    action_kinds: set[str],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record = {
        "source": entry["source_path"],
        "source_value": entry["source_value"],
        "action_ids": _quest_action_ids(behavior_ir, entry["source_value"], action_kinds),
    }
    if extra:
        record.update(extra)
    return record


def _multi_asset_entry_kind(source_value: str) -> str | None:
    token = _token(source_value)
    if _contains_any(token, ("multi_asset", "asset_bundle", "scene_bundle", "asset_collection", "prefab_collection", "set_piece", "hero_set")):
        return "root"
    if _contains_any(token, ("bundle_manifest", "manifest")):
        return "bundle_manifest"
    if _contains_any(token, ("member_asset", "asset_slot", "member_slot", "prefab_slot")):
        return "member_asset_slot"
    if _contains_any(token, ("dependency", "link_graph", "dependency_link")):
        return "dependency_link"
    if _contains_any(token, ("layout_anchor", "layout", "anchor")):
        return "layout_anchor"
    if _contains_any(token, ("variant", "lod", "lod_entry")):
        return "variant_lod_entry"
    if _contains_any(token, ("shared_material", "shared_style", "material_zone", "style_zone")):
        return "shared_material_style_zone"
    if _contains_any(token, ("export", "package_marker", "export_marker")):
        return "export_marker"
    if _contains_any(token, ("assembly_guide", "order_guide", "assembly_order")):
        return "assembly_guide"
    if _contains_any(token, ("bounds", "bounds_reference")):
        return "bounds_reference"
    if _contains_any(token, ("usage", "bundle_usage")):
        return "usage_mask"
    return None


def _build_multi_asset_bundle_ir(
    asset: dict[str, Any],
    behavior_ir: dict[str, Any],
    scene_system_ir: dict[str, Any],
    procedural_prefab_ir: dict[str, Any],
    engine_runtime_ir: dict[str, Any],
) -> dict[str, Any]:
    roots: list[dict[str, Any]] = []
    bundle_manifests: list[dict[str, Any]] = []
    member_asset_slots: list[dict[str, Any]] = []
    dependency_links: list[dict[str, Any]] = []
    layout_anchors: list[dict[str, Any]] = []
    variant_lod_entries: list[dict[str, Any]] = []
    shared_material_style_zones: list[dict[str, Any]] = []
    export_markers: list[dict[str, Any]] = []
    assembly_guides: list[dict[str, Any]] = []
    bounds_references: list[dict[str, Any]] = []
    usage_masks: list[dict[str, Any]] = []
    seen: set[str] = set()
    scene_root_ids = _record_ids(scene_system_ir, "roots")
    prefab_root_ids = _record_ids(procedural_prefab_ir, "roots")
    engine_runtime_ids = _record_ids(engine_runtime_ir, "runtime_roots")
    for entry in _authored_behavior_texts(asset):
        kind = _multi_asset_entry_kind(entry["source_value"])
        if kind is None:
            continue
        node_id = f"{kind}_{entry['slug']}"
        if node_id in seen:
            continue
        seen.add(node_id)
        base = _authored_ir_record(entry, behavior_ir, {"multi_asset_bundle", "prefab_bind", "scene_system", "host_runtime"})
        if kind == "root":
            roots.append({**base, "id": node_id, "scene_root_ids": scene_root_ids, "prefab_root_ids": prefab_root_ids, "bundle_manifest_ids": [], "member_asset_slot_ids": [], "dependency_link_ids": [], "layout_anchor_ids": [], "export_marker_ids": []})
        elif kind == "bundle_manifest":
            bundle_manifests.append({**base, "id": node_id, "engine_runtime_ids": engine_runtime_ids})
        elif kind == "member_asset_slot":
            member_asset_slots.append({**base, "id": node_id, "prefab_root_ids": prefab_root_ids})
        elif kind == "dependency_link":
            dependency_links.append({**base, "id": node_id, "scene_root_ids": scene_root_ids, "prefab_root_ids": prefab_root_ids})
        elif kind == "layout_anchor":
            layout_anchors.append({**base, "id": node_id, "scene_root_ids": scene_root_ids})
        elif kind == "variant_lod_entry":
            variant_lod_entries.append({**base, "id": node_id, "prefab_root_ids": prefab_root_ids})
        elif kind == "shared_material_style_zone":
            shared_material_style_zones.append({**base, "id": node_id, "style_policy": "shared_bundle_style"})
        elif kind == "export_marker":
            export_markers.append({**base, "id": node_id, "engine_runtime_ids": engine_runtime_ids})
        elif kind == "assembly_guide":
            assembly_guides.append({**base, "id": node_id, "dependency_link_ids": [item["id"] for item in dependency_links]})
        elif kind == "bounds_reference":
            bounds_references.append({**base, "id": node_id, "scene_root_ids": scene_root_ids})
        elif kind == "usage_mask":
            usage_masks.append({**base, "id": node_id, "usage_policy": "bundle_usage"})
    if not roots and (bundle_manifests or member_asset_slots or dependency_links or layout_anchors or export_markers):
        roots.append({"id": f"multi_asset_{_slug_fragment(asset.get('name'), 'asset')}", "source": "asset.name", "source_value": str(asset.get("name") or ""), "action_ids": _quest_action_ids(behavior_ir, str(asset.get("name") or ""), {"multi_asset_bundle"}), "scene_root_ids": scene_root_ids, "prefab_root_ids": prefab_root_ids, "bundle_manifest_ids": [], "member_asset_slot_ids": [], "dependency_link_ids": [], "layout_anchor_ids": [], "export_marker_ids": []})
    for root in roots:
        root["bundle_manifest_ids"] = [item["id"] for item in bundle_manifests]
        root["member_asset_slot_ids"] = [item["id"] for item in member_asset_slots]
        root["dependency_link_ids"] = [item["id"] for item in dependency_links]
        root["layout_anchor_ids"] = [item["id"] for item in layout_anchors]
        root["export_marker_ids"] = [item["id"] for item in export_markers]
    return {"schema": "lathe.multi_asset_bundle_ir.v1", "source": "authored_source_intent" if roots or bundle_manifests or member_asset_slots else "build.execution", "roots": roots, "bundle_manifests": bundle_manifests, "member_asset_slots": member_asset_slots, "dependency_links": dependency_links, "layout_anchors": layout_anchors, "variant_lod_entries": variant_lod_entries, "shared_material_style_zones": shared_material_style_zones, "export_markers": export_markers, "assembly_guides": assembly_guides, "bounds_references": bounds_references, "usage_masks": usage_masks, "bindings": {"scene_root_count": len(scene_root_ids), "prefab_root_count": len(prefab_root_ids), "engine_runtime_count": len(engine_runtime_ids)}}


def _style_stack_entry_kind(source_value: str) -> str | None:
    token = _token(source_value)
    if _contains_any(token, ("style_stack", "style_target", "visual_band", "stylized_pbr", "toon", "cel_shaded", "photoreal", "low_poly", "claymation", "lego")):
        return "root"
    if _contains_any(token, ("style_axis", "style_axes")):
        return "style_axis"
    if _contains_any(token, ("palette", "material_model", "palette_material")):
        return "palette_material_model"
    if _contains_any(token, ("surface_mode", "designer_graph", "photo_fit", "layer_stack")):
        return "surface_authoring_mode"
    if _contains_any(token, ("outline", "lighting_strategy", "lighting")):
        return "outline_lighting_strategy"
    if _contains_any(token, ("detail_layer", "detail")):
        return "detail_layer"
    if _contains_any(token, ("motion_style", "animation_style")):
        return "motion_style"
    if _contains_any(token, ("construction_grammar", "grammar_marker")):
        return "construction_marker"
    if _contains_any(token, ("compatibility", "style_bridge", "bridge")):
        return "compatibility_bridge"
    if _contains_any(token, ("refusal", "negative_constraint", "incompatible")):
        return "refusal_constraint"
    if _contains_any(token, ("iteration", "style_wear")):
        return "style_iteration_wear"
    return None


def _build_style_stack_visual_ir(asset: dict[str, Any], behavior_ir: dict[str, Any]) -> dict[str, Any]:
    roots: list[dict[str, Any]] = []
    style_axes: list[dict[str, Any]] = []
    palette_material_models: list[dict[str, Any]] = []
    surface_authoring_modes: list[dict[str, Any]] = []
    outline_lighting_strategies: list[dict[str, Any]] = []
    detail_layers: list[dict[str, Any]] = []
    motion_styles: list[dict[str, Any]] = []
    construction_markers: list[dict[str, Any]] = []
    compatibility_bridges: list[dict[str, Any]] = []
    refusal_constraints: list[dict[str, Any]] = []
    style_iteration_wear_masks: list[dict[str, Any]] = []
    buckets = {"style_axis": style_axes, "palette_material_model": palette_material_models, "surface_authoring_mode": surface_authoring_modes, "outline_lighting_strategy": outline_lighting_strategies, "detail_layer": detail_layers, "motion_style": motion_styles, "construction_marker": construction_markers, "compatibility_bridge": compatibility_bridges, "refusal_constraint": refusal_constraints, "style_iteration_wear": style_iteration_wear_masks}
    seen: set[str] = set()
    for entry in _authored_behavior_texts(asset):
        kind = _style_stack_entry_kind(entry["source_value"])
        if kind is None:
            continue
        node_id = f"{kind}_{entry['slug']}"
        if node_id in seen:
            continue
        seen.add(node_id)
        base = _authored_ir_record(entry, behavior_ir, {"style_stack_band"})
        if kind == "root":
            roots.append({**base, "id": node_id, "style_axis_ids": [], "palette_material_model_ids": [], "surface_authoring_mode_ids": [], "compatibility_bridge_ids": [], "refusal_constraint_ids": []})
        else:
            buckets[kind].append({**base, "id": node_id})
    if not roots and any(buckets.values()):
        roots.append({"id": f"style_stack_{_slug_fragment(asset.get('name'), 'asset')}", "source": "asset.name", "source_value": str(asset.get("name") or ""), "action_ids": _quest_action_ids(behavior_ir, str(asset.get("name") or ""), {"style_stack_band"}), "style_axis_ids": [], "palette_material_model_ids": [], "surface_authoring_mode_ids": [], "compatibility_bridge_ids": [], "refusal_constraint_ids": []})
    for root in roots:
        root["style_axis_ids"] = [item["id"] for item in style_axes]
        root["palette_material_model_ids"] = [item["id"] for item in palette_material_models]
        root["surface_authoring_mode_ids"] = [item["id"] for item in surface_authoring_modes]
        root["compatibility_bridge_ids"] = [item["id"] for item in compatibility_bridges]
        root["refusal_constraint_ids"] = [item["id"] for item in refusal_constraints]
    return {"schema": "lathe.style_stack_visual_ir.v1", "source": "authored_source_intent" if roots or style_axes or palette_material_models else "build.execution", "roots": roots, "style_axes": style_axes, "palette_material_models": palette_material_models, "surface_authoring_modes": surface_authoring_modes, "outline_lighting_strategies": outline_lighting_strategies, "detail_layers": detail_layers, "motion_styles": motion_styles, "construction_markers": construction_markers, "compatibility_bridges": compatibility_bridges, "refusal_constraints": refusal_constraints, "style_iteration_wear_masks": style_iteration_wear_masks}


def _cross_domain_entry_kind(source_value: str) -> str | None:
    token = _token(source_value)
    if _contains_any(token, ("cross_domain", "composition_pack", "hybrid_bundle", "world_asset_mix", "gameplay_bundle", "environment_bundle", "asset_ecosystem", "content_band")):
        return "root"
    if _contains_any(token, ("domain_pillar", "pillar")):
        return "domain_pillar"
    if _contains_any(token, ("handoff", "handoff_link", "bridge_link")):
        return "handoff_link"
    if _contains_any(token, ("shared_rule", "rule_layer")):
        return "shared_rule_layer"
    if _contains_any(token, ("interface", "port_map", "interface_port")):
        return "interface_port_map"
    if _contains_any(token, ("domain_boundary", "boundary")):
        return "domain_boundary"
    if _contains_any(token, ("conflict", "refusal")):
        return "conflict_refusal_cue"
    if _contains_any(token, ("preview", "preview_tile")):
        return "preview"
    if _contains_any(token, ("dependency", "order_guide")):
        return "dependency_guide"
    if _contains_any(token, ("integration", "integration_label")):
        return "integration_label"
    if _contains_any(token, ("handoff_wear", "wear")):
        return "handoff_wear"
    return None


def _build_cross_domain_composition_ir(
    asset: dict[str, Any],
    behavior_ir: dict[str, Any],
    multi_asset_bundle_ir: dict[str, Any],
    style_stack_visual_ir: dict[str, Any],
    world_system_ir: dict[str, Any],
    simulation_environment_ir: dict[str, Any],
    encounter_flow_ir: dict[str, Any],
) -> dict[str, Any]:
    roots: list[dict[str, Any]] = []
    domain_pillars: list[dict[str, Any]] = []
    handoff_links: list[dict[str, Any]] = []
    shared_rule_layers: list[dict[str, Any]] = []
    interface_port_maps: list[dict[str, Any]] = []
    domain_boundaries: list[dict[str, Any]] = []
    conflict_refusal_cues: list[dict[str, Any]] = []
    previews: list[dict[str, Any]] = []
    dependency_guides: list[dict[str, Any]] = []
    integration_labels: list[dict[str, Any]] = []
    handoff_wear_masks: list[dict[str, Any]] = []
    buckets = {"domain_pillar": domain_pillars, "handoff_link": handoff_links, "shared_rule_layer": shared_rule_layers, "interface_port_map": interface_port_maps, "domain_boundary": domain_boundaries, "conflict_refusal_cue": conflict_refusal_cues, "preview": previews, "dependency_guide": dependency_guides, "integration_label": integration_labels, "handoff_wear": handoff_wear_masks}
    linked = {"multi_asset_root_ids": _record_ids(multi_asset_bundle_ir, "roots"), "style_root_ids": _record_ids(style_stack_visual_ir, "roots"), "world_root_ids": _record_ids(world_system_ir, "roots"), "simulation_root_ids": _record_ids(simulation_environment_ir, "roots"), "encounter_root_ids": _record_ids(encounter_flow_ir, "roots")}
    seen: set[str] = set()
    for entry in _authored_behavior_texts(asset):
        kind = _cross_domain_entry_kind(entry["source_value"])
        if kind is None:
            continue
        node_id = f"{kind}_{entry['slug']}"
        if node_id in seen:
            continue
        seen.add(node_id)
        base = _authored_ir_record(entry, behavior_ir, {"cross_domain_pack", "multi_asset_bundle", "style_stack_band", "world_system"})
        if kind == "root":
            roots.append({**base, "id": node_id, **linked, "domain_pillar_ids": [], "handoff_link_ids": [], "shared_rule_layer_ids": [], "interface_port_map_ids": []})
        else:
            buckets[kind].append({**base, "id": node_id, **linked})
    if not roots and any(buckets.values()):
        roots.append({"id": f"cross_domain_{_slug_fragment(asset.get('name'), 'asset')}", "source": "asset.name", "source_value": str(asset.get("name") or ""), "action_ids": _quest_action_ids(behavior_ir, str(asset.get("name") or ""), {"cross_domain_pack"}), **linked, "domain_pillar_ids": [], "handoff_link_ids": [], "shared_rule_layer_ids": [], "interface_port_map_ids": []})
    for root in roots:
        root["domain_pillar_ids"] = [item["id"] for item in domain_pillars]
        root["handoff_link_ids"] = [item["id"] for item in handoff_links]
        root["shared_rule_layer_ids"] = [item["id"] for item in shared_rule_layers]
        root["interface_port_map_ids"] = [item["id"] for item in interface_port_maps]
    return {"schema": "lathe.cross_domain_composition_ir.v1", "source": "authored_source_intent" if roots or domain_pillars or handoff_links else "build.execution", "roots": roots, "domain_pillars": domain_pillars, "handoff_links": handoff_links, "shared_rule_layers": shared_rule_layers, "interface_port_maps": interface_port_maps, "domain_boundaries": domain_boundaries, "conflict_refusal_cues": conflict_refusal_cues, "previews": previews, "dependency_guides": dependency_guides, "integration_labels": integration_labels, "handoff_wear_masks": handoff_wear_masks, "bindings": {key.replace("_ids", "_count"): len(value) for key, value in linked.items()}}


def _rig_animation_entry_kind(source_value: str) -> str | None:
    token = _token(source_value)
    if _contains_any(token, ("parametric_rig", "rig_component", "skeleton", "animation", "rig_animation")):
        return "root"
    if _contains_any(token, ("root_control", "control")):
        return "root_control"
    if _contains_any(token, ("joint_chain", "bone", "joint")):
        return "joint_chain"
    if _contains_any(token, ("limb", "segment")):
        return "limb_marker"
    if _contains_any(token, ("ik", "target_handle", "ik_target")):
        return "ik_target"
    if _contains_any(token, ("pose", "motion_arc", "motion")):
        return "motion_arc"
    if _contains_any(token, ("skin", "weight", "weight_zone")):
        return "skin_weight_zone"
    if _contains_any(token, ("attachment_socket", "rig_socket")):
        return "attachment_socket"
    if _contains_any(token, ("morph", "expression")):
        return "morph_expression_marker"
    if _contains_any(token, ("limit", "range")):
        return "range_limit_guard"
    if _contains_any(token, ("animation_state", "state_cue")):
        return "animation_state_cue"
    return None


def _build_rig_animation_proxy_ir(asset: dict[str, Any], behavior_ir: dict[str, Any], persistence_ir: dict[str, Any], behavior_logic_ir: dict[str, Any]) -> dict[str, Any]:
    roots: list[dict[str, Any]] = []
    root_controls: list[dict[str, Any]] = []
    joint_chains: list[dict[str, Any]] = []
    limb_markers: list[dict[str, Any]] = []
    ik_targets: list[dict[str, Any]] = []
    motion_arcs: list[dict[str, Any]] = []
    skin_weight_zones: list[dict[str, Any]] = []
    attachment_sockets: list[dict[str, Any]] = []
    morph_expression_markers: list[dict[str, Any]] = []
    range_limit_guards: list[dict[str, Any]] = []
    animation_state_cues: list[dict[str, Any]] = []
    buckets = {"root_control": root_controls, "joint_chain": joint_chains, "limb_marker": limb_markers, "ik_target": ik_targets, "motion_arc": motion_arcs, "skin_weight_zone": skin_weight_zones, "attachment_socket": attachment_sockets, "morph_expression_marker": morph_expression_markers, "range_limit_guard": range_limit_guards, "animation_state_cue": animation_state_cues}
    linked = {"persistent_state_ids": _record_ids(persistence_ir, "persistent_variables"), "behavior_graph_ids": _record_ids(behavior_logic_ir, "graphs")}
    seen: set[str] = set()
    for entry in _authored_behavior_texts(asset):
        kind = _rig_animation_entry_kind(entry["source_value"])
        if kind is None:
            continue
        node_id = f"{kind}_{entry['slug']}"
        if node_id in seen:
            continue
        seen.add(node_id)
        base = _authored_ir_record(entry, behavior_ir, {"rig_animation_proxy", "behavior_logic"})
        if kind == "root":
            roots.append({**base, "id": node_id, **linked, "root_control_ids": [], "joint_chain_ids": [], "ik_target_ids": [], "motion_arc_ids": [], "attachment_socket_ids": []})
        else:
            buckets[kind].append({**base, "id": node_id, **linked})
    if not roots and any(buckets.values()):
        roots.append({"id": f"rig_proxy_{_slug_fragment(asset.get('name'), 'asset')}", "source": "asset.name", "source_value": str(asset.get("name") or ""), "action_ids": _quest_action_ids(behavior_ir, str(asset.get("name") or ""), {"rig_animation_proxy"}), **linked, "root_control_ids": [], "joint_chain_ids": [], "ik_target_ids": [], "motion_arc_ids": [], "attachment_socket_ids": []})
    for root in roots:
        root["root_control_ids"] = [item["id"] for item in root_controls]
        root["joint_chain_ids"] = [item["id"] for item in joint_chains]
        root["ik_target_ids"] = [item["id"] for item in ik_targets]
        root["motion_arc_ids"] = [item["id"] for item in motion_arcs]
        root["attachment_socket_ids"] = [item["id"] for item in attachment_sockets]
    return {"schema": "lathe.rig_animation_proxy_ir.v1", "source": "authored_source_intent" if roots or joint_chains or ik_targets else "build.execution", "roots": roots, "root_controls": root_controls, "joint_chains": joint_chains, "limb_markers": limb_markers, "ik_targets": ik_targets, "motion_arcs": motion_arcs, "skin_weight_zones": skin_weight_zones, "attachment_sockets": attachment_sockets, "morph_expression_markers": morph_expression_markers, "range_limit_guards": range_limit_guards, "animation_state_cues": animation_state_cues, "bindings": {"persistent_state_count": len(linked["persistent_state_ids"]), "behavior_graph_count": len(linked["behavior_graph_ids"])}}


def _cloth_attachment_entry_kind(source_value: str) -> str | None:
    token = _token(source_value)
    if _contains_any(token, ("cloth_attachment", "cloth_panel", "cloth", "fabric", "garment", "cape", "cloak", "banner", "flag")):
        return "root"
    if _contains_any(token, ("anchor", "mount")):
        return "anchor"
    if _contains_any(token, ("panel", "drape")):
        return "fabric_panel"
    if _contains_any(token, ("seam", "hem")):
        return "seam_hem"
    if _contains_any(token, ("fold", "tension")):
        return "fold_tension_line"
    if _contains_any(token, ("hardware", "hook", "buckle", "attachment")):
        return "attachment_hardware"
    if _contains_any(token, ("trim", "border")):
        return "trim_border"
    if _contains_any(token, ("wind", "motion")):
        return "motion_wind_cue"
    if _contains_any(token, ("material", "pattern")):
        return "material_pattern_zone"
    if _contains_any(token, ("collision", "clearance")):
        return "collision_clearance_cue"
    if _contains_any(token, ("fray", "cloth_wear", "wear")):
        return "cloth_wear"
    return None


def _build_cloth_attachment_ir(asset: dict[str, Any], behavior_ir: dict[str, Any], simulation_environment_ir: dict[str, Any], stateful_destructible_ir: dict[str, Any]) -> dict[str, Any]:
    roots: list[dict[str, Any]] = []
    anchors: list[dict[str, Any]] = []
    fabric_panels: list[dict[str, Any]] = []
    seams_hems: list[dict[str, Any]] = []
    fold_tension_lines: list[dict[str, Any]] = []
    attachment_hardware: list[dict[str, Any]] = []
    trim_borders: list[dict[str, Any]] = []
    motion_wind_cues: list[dict[str, Any]] = []
    material_pattern_zones: list[dict[str, Any]] = []
    collision_clearance_cues: list[dict[str, Any]] = []
    cloth_wear_masks: list[dict[str, Any]] = []
    buckets = {"anchor": anchors, "fabric_panel": fabric_panels, "seam_hem": seams_hems, "fold_tension_line": fold_tension_lines, "attachment_hardware": attachment_hardware, "trim_border": trim_borders, "motion_wind_cue": motion_wind_cues, "material_pattern_zone": material_pattern_zones, "collision_clearance_cue": collision_clearance_cues, "cloth_wear": cloth_wear_masks}
    linked = {"simulation_root_ids": _record_ids(simulation_environment_ir, "roots"), "destructible_root_ids": _record_ids(stateful_destructible_ir, "roots")}
    seen: set[str] = set()
    for entry in _authored_behavior_texts(asset):
        kind = _cloth_attachment_entry_kind(entry["source_value"])
        if kind is None:
            continue
        node_id = f"{kind}_{entry['slug']}"
        if node_id in seen:
            continue
        seen.add(node_id)
        base = _authored_ir_record(entry, behavior_ir, {"cloth_attachment", "connect", "simulation_env", "destructible_state"})
        if kind == "root":
            roots.append({**base, "id": node_id, **linked, "anchor_ids": [], "fabric_panel_ids": [], "attachment_hardware_ids": [], "collision_clearance_cue_ids": []})
        else:
            buckets[kind].append({**base, "id": node_id, **linked})
    if not roots and any(buckets.values()):
        roots.append({"id": f"cloth_attachment_{_slug_fragment(asset.get('name'), 'asset')}", "source": "asset.name", "source_value": str(asset.get("name") or ""), "action_ids": _quest_action_ids(behavior_ir, str(asset.get("name") or ""), {"cloth_attachment"}), **linked, "anchor_ids": [], "fabric_panel_ids": [], "attachment_hardware_ids": [], "collision_clearance_cue_ids": []})
    for root in roots:
        root["anchor_ids"] = [item["id"] for item in anchors]
        root["fabric_panel_ids"] = [item["id"] for item in fabric_panels]
        root["attachment_hardware_ids"] = [item["id"] for item in attachment_hardware]
        root["collision_clearance_cue_ids"] = [item["id"] for item in collision_clearance_cues]
    return {"schema": "lathe.cloth_attachment_ir.v1", "source": "authored_source_intent" if roots or anchors or fabric_panels else "build.execution", "roots": roots, "anchors": anchors, "fabric_panels": fabric_panels, "seams_hems": seams_hems, "fold_tension_lines": fold_tension_lines, "attachment_hardware": attachment_hardware, "trim_borders": trim_borders, "motion_wind_cues": motion_wind_cues, "material_pattern_zones": material_pattern_zones, "collision_clearance_cues": collision_clearance_cues, "cloth_wear_masks": cloth_wear_masks, "bindings": {"simulation_root_count": len(linked["simulation_root_ids"]), "destructible_root_count": len(linked["destructible_root_ids"])}}


def _domain_kit_entry_kind(source_value: str) -> str | None:
    token = _token(source_value)
    if _contains_any(token, ("domain_kit", "kit_bundle", "domain_library", "library_pack", "style_pack", "asset_pack", "production_pack", "building_set", "vehicle_set", "weapon_set", "prop_set")):
        return "root"
    if _contains_any(token, ("canonical_part", "part_set")):
        return "canonical_part_set"
    if _contains_any(token, ("snap_port", "connector")):
        return "snap_port"
    if _contains_any(token, ("variant_slot", "variant")):
        return "variant_slot"
    if _contains_any(token, ("scale", "grid")):
        return "scale_grid_ref"
    if _contains_any(token, ("style_rule", "material_rule")):
        return "style_material_rule"
    if _contains_any(token, ("assembly_guide", "guide")):
        return "assembly_guide"
    if _contains_any(token, ("compatibility", "dependency")):
        return "compatibility_marker"
    if _contains_any(token, ("library_label", "label")):
        return "library_label"
    if _contains_any(token, ("usage", "kit_usage")):
        return "usage_mask"
    return None


def _build_domain_kit_ir(
    asset: dict[str, Any],
    behavior_ir: dict[str, Any],
    multi_asset_bundle_ir: dict[str, Any],
    procedural_prefab_ir: dict[str, Any],
    world_system_ir: dict[str, Any],
    style_stack_visual_ir: dict[str, Any],
) -> dict[str, Any]:
    roots: list[dict[str, Any]] = []
    canonical_part_sets: list[dict[str, Any]] = []
    snap_ports: list[dict[str, Any]] = []
    variant_slots: list[dict[str, Any]] = []
    scale_grid_refs: list[dict[str, Any]] = []
    style_material_rules: list[dict[str, Any]] = []
    assembly_guides: list[dict[str, Any]] = []
    compatibility_markers: list[dict[str, Any]] = []
    library_labels: list[dict[str, Any]] = []
    usage_masks: list[dict[str, Any]] = []
    buckets = {"canonical_part_set": canonical_part_sets, "snap_port": snap_ports, "variant_slot": variant_slots, "scale_grid_ref": scale_grid_refs, "style_material_rule": style_material_rules, "assembly_guide": assembly_guides, "compatibility_marker": compatibility_markers, "library_label": library_labels, "usage_mask": usage_masks}
    linked = {"multi_asset_root_ids": _record_ids(multi_asset_bundle_ir, "roots"), "prefab_root_ids": _record_ids(procedural_prefab_ir, "roots"), "world_root_ids": _record_ids(world_system_ir, "roots"), "style_root_ids": _record_ids(style_stack_visual_ir, "roots")}
    seen: set[str] = set()
    for entry in _authored_behavior_texts(asset):
        kind = _domain_kit_entry_kind(entry["source_value"])
        if kind is None:
            continue
        node_id = f"{kind}_{entry['slug']}"
        if node_id in seen:
            continue
        seen.add(node_id)
        base = _authored_ir_record(entry, behavior_ir, {"domain_kit", "multi_asset_bundle", "prefab_bind", "style_stack_band"})
        if kind == "root":
            roots.append({**base, "id": node_id, **linked, "canonical_part_set_ids": [], "snap_port_ids": [], "variant_slot_ids": [], "style_material_rule_ids": [], "compatibility_marker_ids": []})
        else:
            buckets[kind].append({**base, "id": node_id, **linked})
    if not roots and any(buckets.values()):
        roots.append({"id": f"domain_kit_{_slug_fragment(asset.get('name'), 'asset')}", "source": "asset.name", "source_value": str(asset.get("name") or ""), "action_ids": _quest_action_ids(behavior_ir, str(asset.get("name") or ""), {"domain_kit"}), **linked, "canonical_part_set_ids": [], "snap_port_ids": [], "variant_slot_ids": [], "style_material_rule_ids": [], "compatibility_marker_ids": []})
    for root in roots:
        root["canonical_part_set_ids"] = [item["id"] for item in canonical_part_sets]
        root["snap_port_ids"] = [item["id"] for item in snap_ports]
        root["variant_slot_ids"] = [item["id"] for item in variant_slots]
        root["style_material_rule_ids"] = [item["id"] for item in style_material_rules]
        root["compatibility_marker_ids"] = [item["id"] for item in compatibility_markers]
    return {"schema": "lathe.domain_kit_ir.v1", "source": "authored_source_intent" if roots or canonical_part_sets or snap_ports else "build.execution", "roots": roots, "canonical_part_sets": canonical_part_sets, "snap_ports": snap_ports, "variant_slots": variant_slots, "scale_grid_refs": scale_grid_refs, "style_material_rules": style_material_rules, "assembly_guides": assembly_guides, "compatibility_markers": compatibility_markers, "library_labels": library_labels, "usage_masks": usage_masks, "bindings": {key.replace("_ids", "_count"): len(value) for key, value in linked.items()}}


def _build_authored_system_ir(
    asset: dict[str, Any],
    behavior_ir: dict[str, Any],
    *,
    schema: str,
    root_prefix: str,
    action_kind: str,
    root_tokens: tuple[str, ...],
    field_tokens: dict[str, tuple[str, ...]],
    links: dict[str, list[Any]] | None = None,
) -> dict[str, Any]:
    linked = links or {}
    roots: list[dict[str, Any]] = []
    records: dict[str, list[dict[str, Any]]] = {field: [] for field in field_tokens}
    seen: set[str] = set()
    for entry in _authored_behavior_texts(asset):
        token = _token(entry["source_value"])
        target_field: str | None = None
        if _contains_any(token, root_tokens):
            target_field = "roots"
        else:
            for field, words in field_tokens.items():
                if _contains_any(token, words):
                    target_field = field
                    break
        if target_field is None:
            continue
        node_id = f"{target_field.rstrip('s')}_{entry['slug']}"
        if node_id in seen:
            continue
        seen.add(node_id)
        base = _authored_ir_record(entry, behavior_ir, {action_kind}, linked)
        if target_field == "roots":
            roots.append({**base, "id": node_id})
        else:
            records[target_field].append({**base, "id": node_id})
    if not roots and any(records.values()):
        roots.append(
            {
                "id": f"{root_prefix}_{_slug_fragment(asset.get('name'), 'asset')}",
                "source": "asset.name",
                "source_value": str(asset.get("name") or ""),
                "action_ids": _quest_action_ids(behavior_ir, str(asset.get("name") or ""), {action_kind}),
                **linked,
            }
        )
    for root in roots:
        for field, values in records.items():
            root[f"{field}_ids"] = [item["id"] for item in values]
    active = bool(roots or any(records.values()))
    return {
        "schema": schema,
        "source": "authored_source_intent" if active else "build.execution",
        "roots": roots,
        **records,
        "bindings": {key.replace("_ids", "_count"): len(value) for key, value in linked.items()},
    }


def _build_typed_data_kernel_ir(
    asset: dict[str, Any],
    behavior_ir: dict[str, Any],
    domain_kit_ir: dict[str, Any],
    live_procedural_runtime_ir: dict[str, Any],
) -> dict[str, Any]:
    return _build_authored_system_ir(
        asset,
        behavior_ir,
        schema="lathe.typed_data_kernel_ir.v1",
        root_prefix="typed_kernel",
        action_kind="typed_data_kernel",
        root_tokens=("typed_data", "typed_bundle", "typed_kernel", "kernel_bus"),
        field_tokens={
            "typed_bundle_buses": ("kernel_bus", "typed_bundle_bus", "data_bus"),
            "mesh_points_volume_slots": ("mesh_slot", "points_slot", "point_cloud", "volume_slot"),
            "heightfield_spline_sdf_slots": ("heightfield_slot", "spline_slot", "sdf_slot", "heightfield", "sdf"),
            "image_rig_slots": ("image_slot", "rig_slot", "rig"),
            "contract_badges": ("contract", "contract_badge"),
            "transform_conversion_links": ("transform", "conversion", "convert"),
            "dependency_order_markers": ("dependency", "order_marker", "order"),
            "cache_delta_states": ("cache", "delta_state", "state_cache"),
            "validation_guard_edges": ("validation", "guard"),
            "data_flow_wear_masks": ("data_flow_wear", "wear"),
        },
        links={
            "domain_kit_root_ids": _record_ids(domain_kit_ir, "roots"),
            "live_runtime_core_ids": _record_ids(live_procedural_runtime_ir, "cores"),
        },
    )


def _build_attribute_surface_graph_ir(
    asset: dict[str, Any],
    behavior_ir: dict[str, Any],
    style_stack_visual_ir: dict[str, Any],
    typed_data_kernel_ir: dict[str, Any],
) -> dict[str, Any]:
    return _build_authored_system_ir(
        asset,
        behavior_ir,
        schema="lathe.attribute_surface_graph_ir.v1",
        root_prefix="surface_graph",
        action_kind="attribute_surface_graph",
        root_tokens=("surface_graph", "surface_program", "attr_lang", "attribute_program"),
        field_tokens={
            "attribute_streams": ("attribute_stream", "attr_stream", "attr_lang"),
            "surface_node_graphs": ("surface_node", "node_graph", "surface_graph"),
            "authoring_modes": ("designer_graph", "photo_fit", "layer_stack", "authoring_mode"),
            "mask_layers": ("mask", "smart_mask", "mask_layer"),
            "materialx_pbr_outputs": ("materialx", "pbr_output", "material_output"),
            "attribute_math_rules": ("attribute_math", "math_rule", "rule"),
            "texture_frequency_controls": ("frequency", "texture_frequency"),
            "preview_bake_targets": ("preview", "bake_target", "bake"),
            "invalid_unbound_guards": ("invalid", "unbound", "guard"),
            "surface_iteration_wear_masks": ("surface_iteration", "surface_wear", "wear"),
        },
        links={
            "style_root_ids": _record_ids(style_stack_visual_ir, "roots"),
            "typed_kernel_root_ids": _record_ids(typed_data_kernel_ir, "roots"),
        },
    )


def _build_vegetation_library_ir(asset: dict[str, Any], behavior_ir: dict[str, Any], simulation_environment_ir: dict[str, Any], typed_data_kernel_ir: dict[str, Any]) -> dict[str, Any]:
    return _build_authored_system_ir(
        asset,
        behavior_ir,
        schema="lathe.vegetation_library_ir.v1",
        root_prefix="vegetation_library",
        action_kind="vegetation_library",
        root_tokens=("vegetation_library", "vegetation_kit", "speedtree", "tree_library", "species_library"),
        field_tokens={
            "species_catalogs": ("species_catalog", "species_library", "tree_library"),
            "trunk_branch_grammars": ("trunk", "branch", "branching_grammar"),
            "leaf_cluster_rules": ("leaf_cluster", "canopy", "canopy_library"),
            "root_anchors": ("root_anchor", "root_system"),
            "lod_billboard_sets": ("lod", "billboard"),
            "wind_motion_markers": ("wind", "motion"),
            "season_variants": ("season", "season_variant"),
            "growth_parameter_ports": ("growth", "parameter_port"),
            "biome_distribution_masks": ("biome", "distribution", "mask"),
            "vegetation_usage_wear_masks": ("vegetation_usage", "wear"),
        },
        links={"simulation_root_ids": _record_ids(simulation_environment_ir, "roots"), "typed_kernel_root_ids": _record_ids(typed_data_kernel_ir, "roots")},
    )


def _build_terrain_heightfield_ir(asset: dict[str, Any], behavior_ir: dict[str, Any], world_system_ir: dict[str, Any], simulation_environment_ir: dict[str, Any], typed_data_kernel_ir: dict[str, Any]) -> dict[str, Any]:
    return _build_authored_system_ir(
        asset,
        behavior_ir,
        schema="lathe.terrain_heightfield_ir.v1",
        root_prefix="terrain_heightfield",
        action_kind="terrain_heightfield",
        root_tokens=("terrain_heightfield", "heightfield_terrain", "heightfield_system", "terrain_program", "terrain_kit"),
        field_tokens={
            "heightfield_domains": ("heightfield_domain", "domain"),
            "elevation_layers": ("elevation", "height_layer"),
            "erosion_flow_networks": ("erosion", "hydraulic_erosion", "thermal_erosion", "flow_network"),
            "slope_deposition_masks": ("slope", "deposition", "mask"),
            "biome_material_zones": ("biome", "material_zone"),
            "drainage_channels": ("drainage", "channel"),
            "terrain_mesh_exports": ("terrain_to_mesh", "mesh_export"),
            "sample_probe_grids": ("probe_grid", "sample_probe"),
            "tileability_boundaries": ("tileability", "boundary"),
            "terrain_iteration_wear_masks": ("terrain_iteration", "wear"),
        },
        links={"world_root_ids": _record_ids(world_system_ir, "roots"), "simulation_root_ids": _record_ids(simulation_environment_ir, "roots"), "typed_kernel_root_ids": _record_ids(typed_data_kernel_ir, "roots")},
    )


def _build_wfc_tile_solver_ir(asset: dict[str, Any], behavior_ir: dict[str, Any], domain_kit_ir: dict[str, Any], multi_asset_bundle_ir: dict[str, Any]) -> dict[str, Any]:
    return _build_authored_system_ir(
        asset,
        behavior_ir,
        schema="lathe.wfc_tile_solver_ir.v1",
        root_prefix="wfc_tile_solver",
        action_kind="wfc_tile_solver",
        root_tokens=("wfc_tileset", "wfc_solver", "wave_function_collapse", "tile_solver", "modular_solver"),
        field_tokens={
            "tileset_catalogs": ("tileset", "tile_catalog"),
            "socket_edge_definitions": ("socket", "edge_definition"),
            "adjacency_rule_matrices": ("adjacency", "adjacency_rule", "matrix"),
            "constraint_grids": ("constraint_grid", "grid"),
            "entropy_weight_markers": ("entropy", "weight"),
            "seed_region_ports": ("seed", "region_port"),
            "solver_iteration_paths": ("iteration", "solver_path"),
            "failure_backtrack_guards": ("failure", "backtrack", "guard"),
            "solved_layout_outputs": ("solved_layout", "layout_output"),
            "tile_usage_wear_masks": ("tile_usage", "wear"),
        },
        links={"domain_kit_root_ids": _record_ids(domain_kit_ir, "roots"), "multi_asset_root_ids": _record_ids(multi_asset_bundle_ir, "roots")},
    )


def _build_cga_building_grammar_ir(asset: dict[str, Any], behavior_ir: dict[str, Any], world_system_ir: dict[str, Any], domain_kit_ir: dict[str, Any]) -> dict[str, Any]:
    return _build_authored_system_ir(
        asset,
        behavior_ir,
        schema="lathe.cga_building_grammar_ir.v1",
        root_prefix="cga_building_grammar",
        action_kind="cga_building_grammar",
        root_tokens=("cga_grammar", "cga_building", "building_grammar", "shape_grammar", "assembly_rules"),
        field_tokens={
            "root_massing_volumes": ("root_massing", "massing", "volume"),
            "rule_stacks": ("rule_stack", "assembly_rules"),
            "split_repeat_extrude_ops": ("split_rule", "repeat_rule", "extrude_rule"),
            "facade_floor_bands": ("facade", "floor_band"),
            "terminal_modules": ("terminal", "module"),
            "derivation_flow_lines": ("derivation", "flow_line"),
            "variation_parameter_ports": ("variation", "parameter_port"),
            "constraint_guard_rules": ("constraint", "guard"),
            "output_assembly_markers": ("output_assembly", "assembly_marker"),
            "grammar_iteration_wear_masks": ("grammar_iteration", "wear"),
        },
        links={"world_root_ids": _record_ids(world_system_ir, "roots"), "domain_kit_root_ids": _record_ids(domain_kit_ir, "roots")},
    )


def _build_volume_effects_data_ir(asset: dict[str, Any], behavior_ir: dict[str, Any], simulation_environment_ir: dict[str, Any], typed_data_kernel_ir: dict[str, Any]) -> dict[str, Any]:
    return _build_authored_system_ir(
        asset,
        behavior_ir,
        schema="lathe.volume_effects_data_ir.v1",
        root_prefix="volume_effects",
        action_kind="volume_effects_data",
        root_tokens=("volume_field", "vdb_volume", "sparse_volume", "volume_effect", "fluid_volume", "smoke_volume", "magic_volume"),
        field_tokens={
            "volume_domains": ("volume_domain", "domain"),
            "density_temperature_velocity_channels": ("density_field", "temperature_field", "velocity_field", "channel"),
            "emitters_sources": ("emitter", "source"),
            "force_flow_vectors": ("force", "flow_vector", "velocity"),
            "slice_sample_planes": ("slice", "sample_plane"),
            "threshold_isosurface_controls": ("threshold", "isosurface"),
            "mesh_particle_outputs": ("mesh_output", "particle_output", "output"),
            "cache_tiles": ("cache", "tile"),
            "field_boundary_guards": ("boundary", "guard"),
            "volume_iteration_wear_masks": ("volume_iteration", "wear"),
        },
        links={"simulation_root_ids": _record_ids(simulation_environment_ir, "roots"), "typed_kernel_root_ids": _record_ids(typed_data_kernel_ir, "roots")},
    )


def _build_instance_pattern_scatter_ir(asset: dict[str, Any], behavior_ir: dict[str, Any], multi_asset_bundle_ir: dict[str, Any], surface_graph_ir: dict[str, Any]) -> dict[str, Any]:
    return _build_authored_system_ir(
        asset,
        behavior_ir,
        schema="lathe.instance_pattern_scatter_ir.v1",
        root_prefix="instance_scatter",
        action_kind="instance_pattern_scatter",
        root_tokens=("instance_pattern", "scatter_program", "scatter_system", "surface_scatter", "greeble_scatter", "poisson_scatter", "copy_to_points"),
        field_tokens={
            "source_part_libraries": ("source_part", "source_library", "part_library"),
            "point_cloud_samples": ("point_cloud", "sample_point"),
            "surface_projection_targets": ("surface_projected", "projection_target"),
            "density_mask_controls": ("density", "mask"),
            "poisson_spacing_rules": ("poisson", "spacing"),
            "orient_scale_jitter_controls": ("orient", "scale", "jitter"),
            "collision_exclusion_guards": ("collision", "exclusion", "guard"),
            "instance_output_markers": ("instance_output", "output_marker"),
            "scatter_debug_traces": ("debug", "trace"),
            "scatter_usage_wear_masks": ("scatter_usage", "wear"),
        },
        links={"multi_asset_root_ids": _record_ids(multi_asset_bundle_ir, "roots"), "surface_graph_root_ids": _record_ids(surface_graph_ir, "roots")},
    )


def _build_f_rep_sdf_composition_ir(asset: dict[str, Any], behavior_ir: dict[str, Any], typed_data_kernel_ir: dict[str, Any], volume_effects_data_ir: dict[str, Any]) -> dict[str, Any]:
    return _build_authored_system_ir(
        asset,
        behavior_ir,
        schema="lathe.f_rep_sdf_composition_ir.v1",
        root_prefix="f_rep_sdf",
        action_kind="f_rep_sdf",
        root_tokens=("f_rep", "frep", "sdf_blend", "sdf_composition", "signed_distance", "implicit_surface"),
        field_tokens={
            "implicit_primitive_sets": ("implicit", "primitive", "signed_distance"),
            "expression_trees": ("expression", "tree"),
            "smooth_boolean_ops": ("smooth_union", "smooth_subtract", "boolean"),
            "blend_radius_controls": ("blend_radius", "radius"),
            "sample_bounds": ("sample_bounds", "bounds"),
            "material_region_fields": ("material_region", "region_field"),
            "extraction_meshing_ports": ("extraction", "meshing", "port"),
            "failure_bounds_guards": ("failure", "bounds_guard", "guard"),
            "organic_silhouette_markers": ("organic", "silhouette"),
            "implicit_iteration_wear_masks": ("implicit_iteration", "wear"),
        },
        links={"typed_kernel_root_ids": _record_ids(typed_data_kernel_ir, "roots"), "volume_root_ids": _record_ids(volume_effects_data_ir, "roots")},
    )


def _build_subdivision_finishing_ir(asset: dict[str, Any], behavior_ir: dict[str, Any], f_rep_sdf_composition_ir: dict[str, Any], typed_data_kernel_ir: dict[str, Any]) -> dict[str, Any]:
    return _build_authored_system_ir(
        asset,
        behavior_ir,
        schema="lathe.subdivision_finishing_ir.v1",
        root_prefix="subdivision_finishing",
        action_kind="subdivision_finishing",
        root_tokens=("opensubdiv", "subdivision_cage", "subdivision_finish", "catmull_clark", "loop_subdivision"),
        field_tokens={
            "control_cages": ("control_cage", "subdivision_cage"),
            "subdivision_schemes": ("scheme", "catmull_clark", "loop_subdivision"),
            "crease_sharpness_tags": ("crease", "sharpness", "crease_tag"),
            "boundary_uv_rules": ("boundary", "uv_rule"),
            "remesh_quad_targets": ("remesh", "quadrangulate", "quad_target"),
            "smoothing_relax_passes": ("smooth_pass", "relax"),
            "displacement_detail_layers": ("displacement", "detail_layer"),
            "quality_probes": ("quality_probe", "probe"),
            "output_lod_markers": ("output_lod", "lod"),
            "finishing_iteration_wear_masks": ("finishing_iteration", "wear"),
        },
        links={"sdf_root_ids": _record_ids(f_rep_sdf_composition_ir, "roots"), "typed_kernel_root_ids": _record_ids(typed_data_kernel_ir, "roots")},
    )


def _build_humanoid_anatomy_ir(asset: dict[str, Any], behavior_ir: dict[str, Any], rig_animation_proxy_ir: dict[str, Any], typed_data_kernel_ir: dict[str, Any]) -> dict[str, Any]:
    return _build_authored_system_ir(
        asset,
        behavior_ir,
        schema="lathe.humanoid_anatomy_ir.v1",
        root_prefix="humanoid_anatomy",
        action_kind="humanoid_anatomy",
        root_tokens=("humanoid_anatomy", "anatomy_preset", "canonical_topology", "adult_male_realistic", "adult_female_realistic", "child_realistic", "chibi_3head"),
        field_tokens={
            "canonical_topologies": ("canonical_topology", "topology"),
            "body_proportions": ("body_proportion", "proportion"),
            "anatomy_region_maps": ("anatomy_region", "region_map"),
            "landmark_loops": ("landmark_loop", "landmark"),
            "joint_rig_anchors": ("joint", "rig_anchor", "anchor"),
            "morph_target_databases": ("morph_database", "morph_target"),
            "skin_weight_zones": ("skin_weight", "weight_zone"),
            "style_variant_slots": ("style_variant", "variant_slot"),
            "anatomy_validation_guards": ("validation", "guard"),
            "anatomy_iteration_wear_masks": ("anatomy_iteration", "wear"),
        },
        links={"rig_proxy_root_ids": _record_ids(rig_animation_proxy_ir, "roots"), "typed_kernel_root_ids": _record_ids(typed_data_kernel_ir, "roots")},
    )


def _build_face_sdf_cel_shading_ir(asset: dict[str, Any], behavior_ir: dict[str, Any], style_stack_visual_ir: dict[str, Any], f_rep_sdf_composition_ir: dict[str, Any], humanoid_anatomy_ir: dict[str, Any]) -> dict[str, Any]:
    return _build_authored_system_ir(
        asset,
        behavior_ir,
        schema="lathe.face_sdf_cel_shading_ir.v1",
        root_prefix="face_sdf_cel",
        action_kind="face_sdf_cel",
        root_tokens=("face_sdf", "face_shadow_sdf", "anime_cel", "cel_ramp", "toon_ramp", "npr_ramp"),
        field_tokens={
            "face_region_sdfs": ("face_region_sdf", "face_sdf", "face_region"),
            "shadow_band_fields": ("shadow_band", "face_shadow_sdf"),
            "ramp_lut_stacks": ("ramp_lut", "cel_ramp", "toon_ramp"),
            "outline_hulls": ("inverted_hull", "sobel_outline", "outline"),
            "light_direction_controls": ("light_direction", "lighting"),
            "id_mask_channels": ("id_mask", "mask_channel"),
            "style_bridge_guards": ("style_bridge", "guard"),
            "preview_outputs": ("preview", "output"),
            "expression_morph_hooks": ("expression", "morph_hook"),
            "cel_iteration_wear_masks": ("cel_iteration", "wear"),
        },
        links={"style_root_ids": _record_ids(style_stack_visual_ir, "roots"), "sdf_root_ids": _record_ids(f_rep_sdf_composition_ir, "roots"), "anatomy_root_ids": _record_ids(humanoid_anatomy_ir, "roots")},
    )


def _build_rig_component_library_ir(asset: dict[str, Any], behavior_ir: dict[str, Any], rig_animation_proxy_ir: dict[str, Any], typed_data_kernel_ir: dict[str, Any]) -> dict[str, Any]:
    return _build_authored_system_ir(
        asset,
        behavior_ir,
        schema="lathe.rig_component_library_ir.v1",
        root_prefix="rig_component_library",
        action_kind="rig_component_library",
        root_tokens=("rig_component_library", "rig_components", "kinefx_component"),
        field_tokens={
            "component_catalogs": ("component_catalog", "rig_components"),
            "spine_chains": ("spine_component", "spine_chain"),
            "limb_chains": ("limb_component", "limb_chain"),
            "digit_chains": ("digit_component", "digit_chain"),
            "mechanical_joints": ("mech_joint", "mechanical_joint"),
            "wing_tentacle_chains": ("wing_chain", "tentacle_chain"),
            "connector_socket_contracts": ("connector_socket", "socket_contract"),
            "ik_fk_templates": ("ik_fk_template", "ik", "fk"),
            "typed_rig_output_slots": ("typed_rig", "rig_slot", "output_slot"),
            "component_cycle_guards": ("cycle_guard", "guard"),
        },
        links={"rig_proxy_root_ids": _record_ids(rig_animation_proxy_ir, "roots"), "typed_kernel_root_ids": _record_ids(typed_data_kernel_ir, "roots")},
    )


def _build_morph_target_database_ir(asset: dict[str, Any], behavior_ir: dict[str, Any], humanoid_anatomy_ir: dict[str, Any], rig_component_library_ir: dict[str, Any]) -> dict[str, Any]:
    return _build_authored_system_ir(
        asset,
        behavior_ir,
        schema="lathe.morph_target_database_ir.v1",
        root_prefix="morph_target_database",
        action_kind="morph_target_database",
        root_tokens=("morph_target_database", "morph_target_library", "blendshape", "shape_key"),
        field_tokens={
            "morph_target_catalogs": ("morph_target_catalog", "morph_target_library"),
            "facial_expression_sets": ("expression_set", "facial_expression"),
            "viseme_lipsync_sets": ("viseme", "lipsync"),
            "body_shape_deltas": ("body_shape_delta", "body_shape"),
            "corrective_shapes": ("corrective_shape",),
            "region_mask_bindings": ("region_mask", "mask_binding"),
            "delta_vector_channels": ("delta_vector", "delta_channel"),
            "symmetry_mirror_rules": ("symmetry", "mirror"),
            "rig_anatomy_compatibility": ("compatibility", "anatomy", "rig"),
            "morph_iteration_wear_masks": ("morph_iteration", "wear"),
        },
        links={"anatomy_root_ids": _record_ids(humanoid_anatomy_ir, "roots"), "rig_component_root_ids": _record_ids(rig_component_library_ir, "roots")},
    )


def _build_animation_library_binding_ir(asset: dict[str, Any], behavior_ir: dict[str, Any], rig_component_library_ir: dict[str, Any], rig_animation_proxy_ir: dict[str, Any]) -> dict[str, Any]:
    return _build_authored_system_ir(
        asset,
        behavior_ir,
        schema="lathe.animation_library_binding_ir.v1",
        root_prefix="animation_library",
        action_kind="animation_library_binding",
        root_tokens=("animation_library_binding", "animation_library", "motion_clip_library", "clip_library", "pose_library"),
        field_tokens={
            "clip_catalogs": ("clip_catalog", "motion_clip", "clip_library"),
            "pose_libraries": ("pose_library", "pose"),
            "locomotion_state_sets": ("locomotion_set", "combat_idle", "combat_walk", "combat_run"),
            "blend_transition_graphs": ("blend_tree", "transition_graph"),
            "event_marker_tracks": ("event_marker", "marker_track"),
            "root_motion_channels": ("root_motion",),
            "rig_binding_slots": ("rig_binding", "binding_slot"),
            "additive_layer_stacks": ("additive_layer", "layer_stack"),
            "preview_timing_outputs": ("preview", "timing"),
            "animation_iteration_wear_masks": ("animation_iteration", "wear"),
        },
        links={"rig_component_root_ids": _record_ids(rig_component_library_ir, "roots"), "rig_proxy_root_ids": _record_ids(rig_animation_proxy_ir, "roots")},
    )


def _build_retargeting_pack_ir(asset: dict[str, Any], behavior_ir: dict[str, Any], humanoid_anatomy_ir: dict[str, Any], animation_library_binding_ir: dict[str, Any]) -> dict[str, Any]:
    return _build_authored_system_ir(
        asset,
        behavior_ir,
        schema="lathe.retargeting_pack_ir.v1",
        root_prefix="retargeting_pack",
        action_kind="retargeting_pack",
        root_tokens=("retargeting_pack", "retargeting", "humanoid_retarget"),
        field_tokens={
            "source_target_skeletons": ("source_skeleton", "target_skeleton", "skeleton"),
            "bone_mapping_tables": ("bone_mapping", "retarget_map"),
            "rest_pose_alignments": ("rest_pose", "rest_pose_map"),
            "scale_proportion_compensation": ("scale_compensation", "proportion"),
            "coordinate_space_conversions": ("coordinate_space", "conversion"),
            "ik_pole_remaps": ("ik_pole", "pole_remap"),
            "root_motion_retargeting": ("root_motion", "motion_retarget"),
            "constraint_limit_transfers": ("constraint", "limit_transfer"),
            "compatibility_validation_guards": ("compatibility", "validation", "guard"),
            "retarget_iteration_wear_masks": ("retarget_iteration", "wear"),
        },
        links={"anatomy_root_ids": _record_ids(humanoid_anatomy_ir, "roots"), "animation_library_root_ids": _record_ids(animation_library_binding_ir, "roots")},
    )


def _build_character_equipment_binding_ir(asset: dict[str, Any], behavior_ir: dict[str, Any], humanoid_anatomy_ir: dict[str, Any], rig_component_library_ir: dict[str, Any], inventory_economy_ir: dict[str, Any]) -> dict[str, Any]:
    return _build_authored_system_ir(
        asset,
        behavior_ir,
        schema="lathe.character_equipment_binding_ir.v1",
        root_prefix="character_equipment",
        action_kind="character_equipment_binding",
        root_tokens=("character_equipment_binding", "equipment_binding", "loadout_slot"),
        field_tokens={
            "body_slot_maps": ("body_slot", "body_slot_map"),
            "weapon_tool_sockets": ("weapon_socket", "tool_socket", "equipment_socket"),
            "armor_outfit_layers": ("armor_slot", "outfit_binding", "armor_layer"),
            "attachment_offset_frames": ("attachment_offset", "offset_frame"),
            "clearance_collision_volumes": ("equipment_clearance", "clearance", "collision"),
            "loadout_variants": ("loadout", "loadout_slot", "variant"),
            "rig_anatomy_binding_rules": ("rig", "anatomy", "binding_rule"),
            "visibility_state_masks": ("visibility", "state_mask"),
            "compatibility_failure_guards": ("compatibility", "failure", "guard"),
            "equipment_iteration_wear_masks": ("equipment_iteration", "wear"),
        },
        links={"anatomy_root_ids": _record_ids(humanoid_anatomy_ir, "roots"), "rig_component_root_ids": _record_ids(rig_component_library_ir, "roots"), "inventory_root_ids": _record_ids(inventory_economy_ir, "roots")},
    )


def _build_gameplay_animation_controller_ir(asset: dict[str, Any], behavior_ir: dict[str, Any], behavior_logic_ir: dict[str, Any], animation_library_binding_ir: dict[str, Any], retargeting_pack_ir: dict[str, Any]) -> dict[str, Any]:
    return _build_authored_system_ir(
        asset,
        behavior_ir,
        schema="lathe.gameplay_animation_controller_ir.v1",
        root_prefix="gameplay_animation_controller",
        action_kind="gameplay_animation_controller",
        root_tokens=("gameplay_animation_controller", "animation_controller", "locomotion_controller", "combat_controller", "ability_state_machine", "gameplay_state_machine"),
        field_tokens={
            "input_action_maps": ("input_action_map", "input_action"),
            "controller_state_graphs": ("state_graph", "state_machine"),
            "animation_parameter_sets": ("animation_parameter", "parameter_set"),
            "transition_rule_tables": ("transition_rule", "transition_table"),
            "locomotion_blend_controls": ("locomotion", "blend"),
            "combat_ability_layers": ("combat", "ability", "layer"),
            "event_output_bindings": ("event_output", "output_binding"),
            "motion_matching_slots": ("motion_matching", "matching_slot"),
            "reachability_dead_state_guards": ("reachability", "dead_state", "guard"),
            "controller_iteration_wear_masks": ("controller_iteration", "wear"),
        },
        links={"behavior_graph_ids": _record_ids(behavior_logic_ir, "graphs"), "animation_library_root_ids": _record_ids(animation_library_binding_ir, "roots"), "retargeting_root_ids": _record_ids(retargeting_pack_ir, "roots")},
    )


def _build_procedural_facial_rig_ir(asset: dict[str, Any], behavior_ir: dict[str, Any], face_sdf_cel_shading_ir: dict[str, Any], morph_target_database_ir: dict[str, Any]) -> dict[str, Any]:
    return _build_authored_system_ir(
        asset,
        behavior_ir,
        schema="lathe.procedural_facial_rig_ir.v1",
        root_prefix="procedural_facial_rig",
        action_kind="procedural_facial_rig",
        root_tokens=("procedural_facial_rig", "facial_rig_pack", "face_rig", "facial_control_board"),
        field_tokens={
            "facial_control_boards": ("facial_control_board", "control_board"),
            "jaw_mouth_controls": ("jaw_control", "mouth_control"),
            "eye_lid_controls": ("eye_control", "blink_control", "lid_control"),
            "brow_cheek_controls": ("brow_control", "cheek_control"),
            "viseme_expression_links": ("viseme", "expression"),
            "morph_driver_bindings": ("morph_driver", "expression_driver"),
            "face_sdf_mask_bindings": ("face_sdf", "mask_binding"),
            "range_limit_guards": ("range", "limit", "guard"),
            "preview_pose_outputs": ("preview_pose", "preview"),
            "facial_rig_iteration_wear_masks": ("facial_rig_iteration", "wear"),
        },
        links={"face_sdf_root_ids": _record_ids(face_sdf_cel_shading_ir, "roots"), "morph_database_root_ids": _record_ids(morph_target_database_ir, "roots")},
    )


def _build_hair_program_ir(asset: dict[str, Any], behavior_ir: dict[str, Any], humanoid_anatomy_ir: dict[str, Any], simulation_environment_ir: dict[str, Any]) -> dict[str, Any]:
    return _build_authored_system_ir(
        asset,
        behavior_ir,
        schema="lathe.hair_program_ir.v1",
        root_prefix="hair_program",
        action_kind="hair_program",
        root_tokens=("hair_program", "strand_grammar", "hair_strand", "hair_cards"),
        field_tokens={
            "scalp_groom_regions": ("scalp", "groom_region"),
            "strand_grammars": ("strand_grammar", "hair_strand"),
            "root_density_masks": ("root_density", "density_mask"),
            "length_distribution_controls": ("length_distribution", "length"),
            "wave_curl_controls": ("wave_amplitude", "wave_frequency", "curl"),
            "hair_card_outputs": ("hair_cards", "card_output"),
            "strand_output_ports": ("strand_output", "output_port"),
            "color_gradient_controls": ("hair_color_gradient", "color_gradient"),
            "collision_clearance_guards": ("collision", "clearance", "guard"),
            "hair_iteration_wear_masks": ("hair_iteration", "wear"),
        },
        links={"anatomy_root_ids": _record_ids(humanoid_anatomy_ir, "roots"), "simulation_root_ids": _record_ids(simulation_environment_ir, "roots")},
    )


def _build_cloth_fabric_simulation_ir(asset: dict[str, Any], behavior_ir: dict[str, Any], cloth_attachment_ir: dict[str, Any], simulation_environment_ir: dict[str, Any], typed_data_kernel_ir: dict[str, Any]) -> dict[str, Any]:
    return _build_authored_system_ir(
        asset,
        behavior_ir,
        schema="lathe.cloth_fabric_simulation_ir.v1",
        root_prefix="cloth_fabric_simulation",
        action_kind="cloth_fabric_simulation",
        root_tokens=("cloth_fabric_simulation", "cloth_program", "fabric_simulation", "xpbd_cloth", "fabric_solver"),
        field_tokens={
            "fabric_domains": ("fabric_domain", "panel_set"),
            "mass_stiffness_damping_parameters": ("cloth_mass", "cloth_stiffness", "cloth_damping"),
            "pin_anchor_constraints": ("pinned_cloth", "pin", "anchor_constraint"),
            "collision_body_volumes": ("collision", "body_volume"),
            "gravity_wind_force_fields": ("gravity", "wind", "force_field"),
            "settling_solve_passes": ("cloth_settling", "solve_pass"),
            "wrinkle_fold_outputs": ("wrinkle", "fold", "output"),
            "material_pattern_zones": ("material", "pattern"),
            "solver_validation_guards": ("solver", "validation", "guard"),
            "cloth_iteration_wear_masks": ("cloth_iteration", "wear"),
        },
        links={"cloth_attachment_root_ids": _record_ids(cloth_attachment_ir, "roots"), "simulation_root_ids": _record_ids(simulation_environment_ir, "roots"), "typed_kernel_root_ids": _record_ids(typed_data_kernel_ir, "roots")},
    )


def _build_fluid_forward_volume_ir(asset: dict[str, Any], behavior_ir: dict[str, Any], volume_effects_data_ir: dict[str, Any], simulation_environment_ir: dict[str, Any], typed_data_kernel_ir: dict[str, Any]) -> dict[str, Any]:
    return _build_authored_system_ir(
        asset,
        behavior_ir,
        schema="lathe.fluid_forward_volume_ir.v1",
        root_prefix="fluid_forward_volume",
        action_kind="fluid_forward_volume",
        root_tokens=("fluid_forward", "fluid_program", "fluid_forward_volume", "asset_level_fluid", "vdb_fluid"),
        field_tokens={
            "fluid_volume_domains": ("fluid_volume", "volume_domain"),
            "density_temperature_velocity_channels": ("density", "temperature", "velocity"),
            "emitter_source_sets": ("emitter", "source"),
            "advection_force_fields": ("advection_field", "force_field"),
            "surface_isosurface_controls": ("fluid_surface", "fluid_isosurface", "isosurface"),
            "particle_mesh_outputs": ("particle", "fluid_mesh_output", "mesh_output"),
            "cache_sample_tiles": ("fluid_cache", "sample_tile", "cache"),
            "collision_boundary_guards": ("collision_boundary", "guard"),
            "fluid_style_material_regions": ("fluid_style", "material_region"),
            "fluid_iteration_wear_masks": ("fluid_iteration", "wear"),
        },
        links={"volume_root_ids": _record_ids(volume_effects_data_ir, "roots"), "simulation_root_ids": _record_ids(simulation_environment_ir, "roots"), "typed_kernel_root_ids": _record_ids(typed_data_kernel_ir, "roots")},
    )


def _build_construction_grammar_kit_ir(asset: dict[str, Any], behavior_ir: dict[str, Any], cga_building_grammar_ir: dict[str, Any], domain_kit_ir: dict[str, Any], wfc_tile_solver_ir: dict[str, Any]) -> dict[str, Any]:
    return _build_authored_system_ir(
        asset,
        behavior_ir,
        schema="lathe.construction_grammar_kit_ir.v1",
        root_prefix="construction_grammar_kit",
        action_kind="construction_grammar_kit",
        root_tokens=("construction_grammar_kit", "construction_kit_system", "modular_construction_grammar", "procedural_assembly_kit"),
        field_tokens={
            "module_catalogs": ("module_catalog", "building_piece_grammar"),
            "snap_grids_axes": ("snap_grid", "snap_axis"),
            "connector_socket_rules": ("connector_rule", "connector_rule_graph", "socket_rule"),
            "allowed_adjacency_rules": ("adjacency", "allowed_adjacency"),
            "repeat_split_assembly_rules": ("repeat_rule", "split_rule", "assembly_rule"),
            "kitbash_variant_slots": ("kitbash", "variant_slot"),
            "structural_validation_guards": ("structural_module", "validation", "guard"),
            "buildable_output_ports": ("buildable_output", "output_port"),
            "scale_metric_markers": ("scale_metric", "metric_marker"),
            "grammar_iteration_wear_masks": ("grammar_iteration", "wear"),
        },
        links={"cga_root_ids": _record_ids(cga_building_grammar_ir, "roots"), "domain_kit_root_ids": _record_ids(domain_kit_ir, "roots"), "wfc_root_ids": _record_ids(wfc_tile_solver_ir, "roots")},
    )


def _build_creature_appendage_program_ir(asset: dict[str, Any], behavior_ir: dict[str, Any], rig_component_library_ir: dict[str, Any], humanoid_anatomy_ir: dict[str, Any], body_part_library_ir: dict[str, Any] | None = None) -> dict[str, Any]:
    links = {
        "rig_component_root_ids": _record_ids(rig_component_library_ir, "roots"),
        "anatomy_root_ids": _record_ids(humanoid_anatomy_ir, "roots"),
    }
    if body_part_library_ir is not None:
        links["body_part_root_ids"] = _record_ids(body_part_library_ir, "roots")
    return _build_authored_system_ir(
        asset,
        behavior_ir,
        schema="lathe.creature_appendage_program_ir.v1",
        root_prefix="creature_appendage",
        action_kind="creature_appendage",
        root_tokens=("creature_appendage", "appendage_program", "wing_appendage", "tail_appendage", "tentacle_appendage", "horn_appendage", "claw_appendage", "fin_appendage"),
        field_tokens={
            "appendage_socket_maps": ("appendage_socket", "socket_map"),
            "joint_chain_segments": ("joint_chain", "segment"),
            "segment_profile_controls": ("segment_profile", "profile_control"),
            "wing_tail_tentacle_variants": ("wing_appendage", "tail_appendage", "tentacle_appendage", "limb_variant"),
            "surface_feature_maps": ("surface_feature", "feature_map"),
            "symmetry_mirror_rules": ("symmetry", "mirror"),
            "articulation_range_controls": ("articulation", "range_control"),
            "muscle_volume_bands": ("muscle", "volume_band"),
            "attachment_clearance_guards": ("attachment_clearance", "clearance", "guard"),
            "appendage_iteration_wear_masks": ("appendage_iteration", "wear"),
        },
        links=links,
    )


def _build_body_part_library_ir(asset: dict[str, Any], behavior_ir: dict[str, Any], humanoid_anatomy_ir: dict[str, Any], rig_component_library_ir: dict[str, Any], morph_target_database_ir: dict[str, Any]) -> dict[str, Any]:
    return _build_authored_system_ir(
        asset,
        behavior_ir,
        schema="lathe.body_part_library_ir.v1",
        root_prefix="body_part_library",
        action_kind="body_part_library",
        root_tokens=("body_part_library", "body_part_program", "body_part_procedural", "anatomy_region_library", "head_part_library", "torso_part_library", "hand_foot_library"),
        field_tokens={
            "body_part_catalogs": ("body_part_catalog", "body_part_library"),
            "anatomy_region_maps": ("anatomy_region", "region_map"),
            "organ_socket_maps": ("organ_socket", "organ_socket_map"),
            "muscle_group_volume_bands": ("muscle_group", "volume_band"),
            "landmark_loop_markers": ("landmark_loop", "landmark"),
            "proportion_range_controls": ("proportion", "range_control"),
            "symmetry_pair_rules": ("symmetry", "pair_rule"),
            "surface_zone_bindings": ("surface_zone", "binding"),
            "compatibility_validation_guards": ("compatibility", "validation", "guard"),
            "body_part_iteration_wear_masks": ("body_part_iteration", "wear"),
        },
        links={"anatomy_root_ids": _record_ids(humanoid_anatomy_ir, "roots"), "rig_component_root_ids": _record_ids(rig_component_library_ir, "roots"), "morph_database_root_ids": _record_ids(morph_target_database_ir, "roots")},
    )


def _build_material_primitive_library_ir(asset: dict[str, Any], behavior_ir: dict[str, Any], attribute_surface_graph_ir: dict[str, Any], style_stack_visual_ir: dict[str, Any]) -> dict[str, Any]:
    return _build_authored_system_ir(
        asset,
        behavior_ir,
        schema="lathe.material_primitive_library_ir.v1",
        root_prefix="material_primitive_library",
        action_kind="material_primitive_library",
        root_tokens=("material_primitive", "physical_substance", "substance_taxonomy", "procedural_substance", "material_preset_library"),
        field_tokens={
            "material_primitive_catalogs": ("material_primitive_catalog", "material_primitive"),
            "physical_substance_taxonomies": ("physical_substance", "substance_taxonomy"),
            "pbr_channel_ranges": ("pbr_primitive", "pbr_channel", "channel_range"),
            "metal_dielectric_emissive_classes": ("metal_rough_primitive", "dielectric_material", "emissive_material"),
            "translucent_material_classes": ("translucent_material", "translucent"),
            "procedural_parameter_ports": ("procedural_substance", "parameter_port"),
            "smart_mask_bindings": ("smart_mask", "mask_binding"),
            "materialx_output_ports": ("materialx", "output_port"),
            "pbr_validation_guards": ("pbr", "validation", "guard"),
            "substance_variant_slots": ("substance_variant", "variant_slot"),
            "material_iteration_wear_masks": ("material_iteration", "wear"),
        },
        links={"surface_graph_root_ids": _record_ids(attribute_surface_graph_ir, "roots"), "style_root_ids": _record_ids(style_stack_visual_ir, "roots")},
    )


def run(executor: Any, optimize_bundle: dict[str, Any]) -> dict[str, Any]:
    """Run.

    Args:
        executor: executor argument.
        optimize_bundle: optimize_bundle argument.

    Returns:
        The result.
    """
    stage_dir = executor.stage_dirs["execution"]
    bundle = build_execution_bundle(
        asset=executor.asset,
        stage_dir=stage_dir,
        runtime=executor.runtime,
        runtime_config=executor.runtime_config,
        out_dir=executor.out_dir,
    )
    behavior_ir = _build_behavior_ir(executor.asset, executor.runtime)
    persistence_ir = _build_persistence_ir(executor.asset, executor.runtime, behavior_ir)
    quest_dialogue_ir = _build_quest_dialogue_ir(executor.asset, behavior_ir, persistence_ir)
    camera_cinematic_ir = _build_camera_cinematic_ir(executor.asset, behavior_ir, quest_dialogue_ir)
    audio_ir = _build_audio_ir(executor.asset, behavior_ir, quest_dialogue_ir, camera_cinematic_ir)
    runtime_partition_ir = _build_runtime_partition_ir(
        executor.asset,
        behavior_ir,
        persistence_ir,
        camera_cinematic_ir,
        audio_ir,
    )
    multiplayer_session_ir = _build_multiplayer_session_ir(
        executor.asset,
        behavior_ir,
        persistence_ir,
        runtime_partition_ir,
    )
    localization_text_ir = _build_localization_text_ir(
        executor.asset,
        behavior_ir,
        quest_dialogue_ir,
        audio_ir,
    )
    accessibility_ux_ir = _build_accessibility_ux_ir(
        executor.asset,
        behavior_ir,
        localization_text_ir,
        audio_ir,
    )
    economy_simulation_ir = _build_economy_simulation_ir(
        executor.asset,
        behavior_ir,
        persistence_ir,
        quest_dialogue_ir,
        multiplayer_session_ir,
    )
    scene_system_ir = _build_scene_system_ir(
        executor.asset,
        behavior_ir,
        camera_cinematic_ir,
        runtime_partition_ir,
        audio_ir,
    )
    procedural_prefab_ir = _build_procedural_prefab_ir(
        executor.asset,
        behavior_ir,
        scene_system_ir,
        runtime_partition_ir,
    )
    engine_runtime_ir = _build_engine_runtime_ir(
        executor.asset,
        behavior_ir,
        scene_system_ir,
        procedural_prefab_ir,
        runtime_partition_ir,
        multiplayer_session_ir,
    )
    behavior_logic_ir = _build_behavior_logic_ir(
        executor.asset,
        behavior_ir,
        persistence_ir,
    )
    encounter_flow_ir = _build_encounter_flow_ir(
        executor.asset,
        behavior_ir,
        quest_dialogue_ir,
        scene_system_ir,
        behavior_logic_ir,
    )
    inventory_economy_ir = _build_inventory_economy_ir(
        executor.asset,
        behavior_ir,
        persistence_ir,
        quest_dialogue_ir,
        economy_simulation_ir,
    )
    world_system_ir = _build_world_system_ir(
        executor.asset,
        behavior_ir,
        scene_system_ir,
        encounter_flow_ir,
        economy_simulation_ir,
        inventory_economy_ir,
        runtime_partition_ir,
    )
    simulation_environment_ir = _build_simulation_environment_ir(
        executor.asset,
        behavior_ir,
        scene_system_ir,
        world_system_ir,
        runtime_partition_ir,
    )
    stateful_destructible_ir = _build_stateful_destructible_ir(
        executor.asset,
        behavior_ir,
        persistence_ir,
        encounter_flow_ir,
        inventory_economy_ir,
    )
    live_procedural_runtime_ir = _build_live_procedural_runtime_ir(
        executor.asset,
        behavior_ir,
        engine_runtime_ir,
        procedural_prefab_ir,
        world_system_ir,
        simulation_environment_ir,
    )
    multi_asset_bundle_ir = _build_multi_asset_bundle_ir(
        executor.asset,
        behavior_ir,
        scene_system_ir,
        procedural_prefab_ir,
        engine_runtime_ir,
    )
    style_stack_visual_ir = _build_style_stack_visual_ir(
        executor.asset,
        behavior_ir,
    )
    cross_domain_composition_ir = _build_cross_domain_composition_ir(
        executor.asset,
        behavior_ir,
        multi_asset_bundle_ir,
        style_stack_visual_ir,
        world_system_ir,
        simulation_environment_ir,
        encounter_flow_ir,
    )
    rig_animation_proxy_ir = _build_rig_animation_proxy_ir(
        executor.asset,
        behavior_ir,
        persistence_ir,
        behavior_logic_ir,
    )
    cloth_attachment_ir = _build_cloth_attachment_ir(
        executor.asset,
        behavior_ir,
        simulation_environment_ir,
        stateful_destructible_ir,
    )
    domain_kit_ir = _build_domain_kit_ir(
        executor.asset,
        behavior_ir,
        multi_asset_bundle_ir,
        procedural_prefab_ir,
        world_system_ir,
        style_stack_visual_ir,
    )
    typed_data_kernel_ir = _build_typed_data_kernel_ir(
        executor.asset,
        behavior_ir,
        domain_kit_ir,
        live_procedural_runtime_ir,
    )
    attribute_surface_graph_ir = _build_attribute_surface_graph_ir(
        executor.asset,
        behavior_ir,
        style_stack_visual_ir,
        typed_data_kernel_ir,
    )
    vegetation_library_ir = _build_vegetation_library_ir(
        executor.asset,
        behavior_ir,
        simulation_environment_ir,
        typed_data_kernel_ir,
    )
    terrain_heightfield_ir = _build_terrain_heightfield_ir(
        executor.asset,
        behavior_ir,
        world_system_ir,
        simulation_environment_ir,
        typed_data_kernel_ir,
    )
    wfc_tile_solver_ir = _build_wfc_tile_solver_ir(
        executor.asset,
        behavior_ir,
        domain_kit_ir,
        multi_asset_bundle_ir,
    )
    cga_building_grammar_ir = _build_cga_building_grammar_ir(
        executor.asset,
        behavior_ir,
        world_system_ir,
        domain_kit_ir,
    )
    volume_effects_data_ir = _build_volume_effects_data_ir(
        executor.asset,
        behavior_ir,
        simulation_environment_ir,
        typed_data_kernel_ir,
    )
    instance_pattern_scatter_ir = _build_instance_pattern_scatter_ir(
        executor.asset,
        behavior_ir,
        multi_asset_bundle_ir,
        attribute_surface_graph_ir,
    )
    f_rep_sdf_composition_ir = _build_f_rep_sdf_composition_ir(
        executor.asset,
        behavior_ir,
        typed_data_kernel_ir,
        volume_effects_data_ir,
    )
    subdivision_finishing_ir = _build_subdivision_finishing_ir(
        executor.asset,
        behavior_ir,
        f_rep_sdf_composition_ir,
        typed_data_kernel_ir,
    )
    humanoid_anatomy_ir = _build_humanoid_anatomy_ir(
        executor.asset,
        behavior_ir,
        rig_animation_proxy_ir,
        typed_data_kernel_ir,
    )
    face_sdf_cel_shading_ir = _build_face_sdf_cel_shading_ir(
        executor.asset,
        behavior_ir,
        style_stack_visual_ir,
        f_rep_sdf_composition_ir,
        humanoid_anatomy_ir,
    )
    rig_component_library_ir = _build_rig_component_library_ir(
        executor.asset,
        behavior_ir,
        rig_animation_proxy_ir,
        typed_data_kernel_ir,
    )
    morph_target_database_ir = _build_morph_target_database_ir(
        executor.asset,
        behavior_ir,
        humanoid_anatomy_ir,
        rig_component_library_ir,
    )
    animation_library_binding_ir = _build_animation_library_binding_ir(
        executor.asset,
        behavior_ir,
        rig_component_library_ir,
        rig_animation_proxy_ir,
    )
    retargeting_pack_ir = _build_retargeting_pack_ir(
        executor.asset,
        behavior_ir,
        humanoid_anatomy_ir,
        animation_library_binding_ir,
    )
    character_equipment_binding_ir = _build_character_equipment_binding_ir(
        executor.asset,
        behavior_ir,
        humanoid_anatomy_ir,
        rig_component_library_ir,
        inventory_economy_ir,
    )
    gameplay_animation_controller_ir = _build_gameplay_animation_controller_ir(
        executor.asset,
        behavior_ir,
        behavior_logic_ir,
        animation_library_binding_ir,
        retargeting_pack_ir,
    )
    procedural_facial_rig_ir = _build_procedural_facial_rig_ir(
        executor.asset,
        behavior_ir,
        face_sdf_cel_shading_ir,
        morph_target_database_ir,
    )
    hair_program_ir = _build_hair_program_ir(
        executor.asset,
        behavior_ir,
        humanoid_anatomy_ir,
        simulation_environment_ir,
    )
    cloth_fabric_simulation_ir = _build_cloth_fabric_simulation_ir(
        executor.asset,
        behavior_ir,
        cloth_attachment_ir,
        simulation_environment_ir,
        typed_data_kernel_ir,
    )
    fluid_forward_volume_ir = _build_fluid_forward_volume_ir(
        executor.asset,
        behavior_ir,
        volume_effects_data_ir,
        simulation_environment_ir,
        typed_data_kernel_ir,
    )
    construction_grammar_kit_ir = _build_construction_grammar_kit_ir(
        executor.asset,
        behavior_ir,
        cga_building_grammar_ir,
        domain_kit_ir,
        wfc_tile_solver_ir,
    )
    body_part_library_ir = _build_body_part_library_ir(
        executor.asset,
        behavior_ir,
        humanoid_anatomy_ir,
        rig_component_library_ir,
        morph_target_database_ir,
    )
    creature_appendage_program_ir = _build_creature_appendage_program_ir(
        executor.asset,
        behavior_ir,
        rig_component_library_ir,
        humanoid_anatomy_ir,
        body_part_library_ir,
    )
    material_primitive_library_ir = _build_material_primitive_library_ir(
        executor.asset,
        behavior_ir,
        attribute_surface_graph_ir,
        style_stack_visual_ir,
    )
    bundle["behavior_ir"] = behavior_ir
    bundle["persistence_ir"] = persistence_ir
    bundle["quest_dialogue_ir"] = quest_dialogue_ir
    bundle["camera_cinematic_ir"] = camera_cinematic_ir
    bundle["audio_ir"] = audio_ir
    bundle["runtime_partition_ir"] = runtime_partition_ir
    bundle["multiplayer_session_ir"] = multiplayer_session_ir
    bundle["localization_text_ir"] = localization_text_ir
    bundle["accessibility_ux_ir"] = accessibility_ux_ir
    bundle["economy_simulation_ir"] = economy_simulation_ir
    bundle["scene_system_ir"] = scene_system_ir
    bundle["procedural_prefab_ir"] = procedural_prefab_ir
    bundle["engine_runtime_ir"] = engine_runtime_ir
    bundle["behavior_logic_ir"] = behavior_logic_ir
    bundle["encounter_flow_ir"] = encounter_flow_ir
    bundle["inventory_economy_ir"] = inventory_economy_ir
    bundle["world_system_ir"] = world_system_ir
    bundle["simulation_environment_ir"] = simulation_environment_ir
    bundle["stateful_destructible_ir"] = stateful_destructible_ir
    bundle["live_procedural_runtime_ir"] = live_procedural_runtime_ir
    bundle["multi_asset_bundle_ir"] = multi_asset_bundle_ir
    bundle["style_stack_visual_ir"] = style_stack_visual_ir
    bundle["cross_domain_composition_ir"] = cross_domain_composition_ir
    bundle["rig_animation_proxy_ir"] = rig_animation_proxy_ir
    bundle["cloth_attachment_ir"] = cloth_attachment_ir
    bundle["domain_kit_ir"] = domain_kit_ir
    bundle["typed_data_kernel_ir"] = typed_data_kernel_ir
    bundle["attribute_surface_graph_ir"] = attribute_surface_graph_ir
    bundle["vegetation_library_ir"] = vegetation_library_ir
    bundle["terrain_heightfield_ir"] = terrain_heightfield_ir
    bundle["wfc_tile_solver_ir"] = wfc_tile_solver_ir
    bundle["cga_building_grammar_ir"] = cga_building_grammar_ir
    bundle["volume_effects_data_ir"] = volume_effects_data_ir
    bundle["instance_pattern_scatter_ir"] = instance_pattern_scatter_ir
    bundle["f_rep_sdf_composition_ir"] = f_rep_sdf_composition_ir
    bundle["subdivision_finishing_ir"] = subdivision_finishing_ir
    bundle["humanoid_anatomy_ir"] = humanoid_anatomy_ir
    bundle["face_sdf_cel_shading_ir"] = face_sdf_cel_shading_ir
    bundle["rig_component_library_ir"] = rig_component_library_ir
    bundle["morph_target_database_ir"] = morph_target_database_ir
    bundle["animation_library_binding_ir"] = animation_library_binding_ir
    bundle["retargeting_pack_ir"] = retargeting_pack_ir
    bundle["character_equipment_binding_ir"] = character_equipment_binding_ir
    bundle["gameplay_animation_controller_ir"] = gameplay_animation_controller_ir
    bundle["procedural_facial_rig_ir"] = procedural_facial_rig_ir
    bundle["hair_program_ir"] = hair_program_ir
    bundle["cloth_fabric_simulation_ir"] = cloth_fabric_simulation_ir
    bundle["fluid_forward_volume_ir"] = fluid_forward_volume_ir
    bundle["construction_grammar_kit_ir"] = construction_grammar_kit_ir
    bundle["creature_appendage_program_ir"] = creature_appendage_program_ir
    bundle["body_part_library_ir"] = body_part_library_ir
    bundle["material_primitive_library_ir"] = material_primitive_library_ir
    executor.runtime["execution"] = {"bundle": bundle, "stage_dir": stage_dir}
    render_metrics = bundle.get("render_eval_ir", {}).get("metrics", {})
    if render_metrics:
        executor.runtime["render_eval"] = {
            "report": {
                "views": bundle.get("render_eval_ir", {}).get("view_metrics", {}),
                "metrics": render_metrics,
            }
        }
    else:
        executor.runtime.pop("render_eval", None)
    dump_json(stage_dir / "behavior_ir.json", behavior_ir)
    dump_json(stage_dir / "persistence_ir.json", persistence_ir)
    dump_json(stage_dir / "quest_dialogue_ir.json", quest_dialogue_ir)
    dump_json(stage_dir / "camera_cinematic_ir.json", camera_cinematic_ir)
    dump_json(stage_dir / "audio_ir.json", audio_ir)
    dump_json(stage_dir / "runtime_partition_ir.json", runtime_partition_ir)
    dump_json(stage_dir / "multiplayer_session_ir.json", multiplayer_session_ir)
    dump_json(stage_dir / "localization_text_ir.json", localization_text_ir)
    dump_json(stage_dir / "accessibility_ux_ir.json", accessibility_ux_ir)
    dump_json(stage_dir / "economy_simulation_ir.json", economy_simulation_ir)
    dump_json(stage_dir / "scene_system_ir.json", scene_system_ir)
    dump_json(stage_dir / "procedural_prefab_ir.json", procedural_prefab_ir)
    dump_json(stage_dir / "engine_runtime_ir.json", engine_runtime_ir)
    dump_json(stage_dir / "behavior_logic_ir.json", behavior_logic_ir)
    dump_json(stage_dir / "encounter_flow_ir.json", encounter_flow_ir)
    dump_json(stage_dir / "inventory_economy_ir.json", inventory_economy_ir)
    dump_json(stage_dir / "world_system_ir.json", world_system_ir)
    dump_json(stage_dir / "simulation_environment_ir.json", simulation_environment_ir)
    dump_json(stage_dir / "stateful_destructible_ir.json", stateful_destructible_ir)
    dump_json(stage_dir / "live_procedural_runtime_ir.json", live_procedural_runtime_ir)
    dump_json(stage_dir / "multi_asset_bundle_ir.json", multi_asset_bundle_ir)
    dump_json(stage_dir / "style_stack_visual_ir.json", style_stack_visual_ir)
    dump_json(stage_dir / "cross_domain_composition_ir.json", cross_domain_composition_ir)
    dump_json(stage_dir / "rig_animation_proxy_ir.json", rig_animation_proxy_ir)
    dump_json(stage_dir / "cloth_attachment_ir.json", cloth_attachment_ir)
    dump_json(stage_dir / "domain_kit_ir.json", domain_kit_ir)
    dump_json(stage_dir / "typed_data_kernel_ir.json", typed_data_kernel_ir)
    dump_json(stage_dir / "attribute_surface_graph_ir.json", attribute_surface_graph_ir)
    dump_json(stage_dir / "vegetation_library_ir.json", vegetation_library_ir)
    dump_json(stage_dir / "terrain_heightfield_ir.json", terrain_heightfield_ir)
    dump_json(stage_dir / "wfc_tile_solver_ir.json", wfc_tile_solver_ir)
    dump_json(stage_dir / "cga_building_grammar_ir.json", cga_building_grammar_ir)
    dump_json(stage_dir / "volume_effects_data_ir.json", volume_effects_data_ir)
    dump_json(stage_dir / "instance_pattern_scatter_ir.json", instance_pattern_scatter_ir)
    dump_json(stage_dir / "f_rep_sdf_composition_ir.json", f_rep_sdf_composition_ir)
    dump_json(stage_dir / "subdivision_finishing_ir.json", subdivision_finishing_ir)
    dump_json(stage_dir / "humanoid_anatomy_ir.json", humanoid_anatomy_ir)
    dump_json(stage_dir / "face_sdf_cel_shading_ir.json", face_sdf_cel_shading_ir)
    dump_json(stage_dir / "rig_component_library_ir.json", rig_component_library_ir)
    dump_json(stage_dir / "morph_target_database_ir.json", morph_target_database_ir)
    dump_json(stage_dir / "animation_library_binding_ir.json", animation_library_binding_ir)
    dump_json(stage_dir / "retargeting_pack_ir.json", retargeting_pack_ir)
    dump_json(stage_dir / "character_equipment_binding_ir.json", character_equipment_binding_ir)
    dump_json(stage_dir / "gameplay_animation_controller_ir.json", gameplay_animation_controller_ir)
    dump_json(stage_dir / "procedural_facial_rig_ir.json", procedural_facial_rig_ir)
    dump_json(stage_dir / "hair_program_ir.json", hair_program_ir)
    dump_json(stage_dir / "cloth_fabric_simulation_ir.json", cloth_fabric_simulation_ir)
    dump_json(stage_dir / "fluid_forward_volume_ir.json", fluid_forward_volume_ir)
    dump_json(stage_dir / "construction_grammar_kit_ir.json", construction_grammar_kit_ir)
    dump_json(stage_dir / "creature_appendage_program_ir.json", creature_appendage_program_ir)
    dump_json(stage_dir / "body_part_library_ir.json", body_part_library_ir)
    dump_json(stage_dir / "material_primitive_library_ir.json", material_primitive_library_ir)
    dump_json(stage_dir / "bundle.json", bundle)
    return bundle
