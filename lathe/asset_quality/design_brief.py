"""Phase 2 deterministic ``DesignBrief`` representation.

Adds an internal ``DesignBrief`` IR that captures explicit art-direction
intent for every hero asset *before* geometry is generated, without
changing public ``.lth`` syntax. Existing assets receive a deterministic
default brief inferred from the asset name and intent role; future
phases (family grammar, semantic construction graph, material/wear
graph) consume the brief to drive thresholds and structural rules.

Spec: ``docs/asset-quality/lathe-asset-quality-upgrade-spec.md`` Section 7.
Tasklist: ``docs/asset-quality/improvement-tasklist.md`` Phase 2.
Per-field reference: ``docs/asset-quality/design-brief-ir.md``.

Family inference rule
---------------------

``_infer_family`` examines, in order:

1. explicit family authoring from ``asset["assembly"]["family"]``;
2. explicit family authoring from ``asset["from"]``;
3. intent-level family hints such as ``intent.family``,
   ``intent.source_family``, ``intent.asset_family``,
   ``intent.object_family``, or ``intent.family_hint``;
4. positive authored content in ``intent.parts``, ``intent.materials``,
   ``intent.interactions``, ``features.allow``, ``assembly.components``,
   ``assembly.mechanisms``, ``assembly.traits``, ``surface.materials``,
   and ``surface.patterns``;
5. ``asset["name"]`` (case-insensitive substring match);
6. ``asset["intent"]["role"]`` (case-insensitive substring match);
7. ``asset["kind"]`` (case-insensitive substring match) when present.

Explicit family names may use either canonical internal family names
(``industrial_crate``) or source-family aliases ending in ``_family``
(``industrial_crate_family``). The first match wins. Substring tokens
are tried in this order:
``crate`` -> ``industrial_crate``; ``door`` -> ``mechanical_door``;
``cabinet`` -> ``service_cabinet``; weapon tokens -> ``weapon_prop``;
vehicle tokens -> ``vehicle_prop``; furniture tokens -> ``furniture_prop``;
natural/terrain tokens -> ``natural_form``; architecture tokens ->
``environment_architecture``; lighting tokens -> ``lighting_prop``;
machine/console tokens -> ``machine_console``; portal/relic tokens ->
``portal_relic``; tool tokens -> ``tool_prop``; modular-kit tokens ->
``modular_kit``; character/creature tokens -> ``character_creature``.
set-dressing tokens -> ``set_dressing_prop``; material/surface tokens ->
``surface_material_sample``; terrain/foliage tokens ->
``terrain_vegetation_variant``; water/weather/effects tokens ->
``environment_effect``; settlement/district tokens ->
``settlement_district``; encounter-flow tokens -> ``encounter_flow``;
inventory/economy tokens -> ``inventory_economy_object``; gameplay/objective tokens ->
``gameplay_object``; rig/animation tokens -> ``rig_animation_proxy``;
stateful/destructible tokens -> ``stateful_destructible_prop``;
cloth/attachment tokens -> ``cloth_attachment_form``; domain-kit tokens ->
``domain_kit_bundle``; world-system tokens -> ``world_system_assembly``;
simulation/environment-system tokens -> ``simulation_environment_system``.
multi-asset bundle tokens -> ``authored_multi_asset_bundle``; live
procedural/runtime tokens -> ``live_procedural_runtime_bundle``.
cross-domain composition tokens -> ``cross_domain_composition_pack``;
style-stack/visual-band tokens -> ``style_stack_visual_band``.
typed-data/kernel tokens -> ``typed_data_kernel_bundle``; attribute-language
and surface-graph tokens -> ``attribute_surface_graph_program``.
vegetation-library tokens -> ``vegetation_library_system``;
terrain/heightfield/erosion tokens -> ``terrain_heightfield_system``.
WFC/tile-solver tokens -> ``wfc_tile_solver_system``; CGA/building-grammar
tokens -> ``cga_building_grammar_system``. volume/effects-data tokens ->
``volume_effects_data_system``; instance-pattern/scatter tokens ->
``instance_pattern_scatter_system``. F-Rep/SDF tokens ->
``f_rep_sdf_composition_system``; subdivision/finishing tokens ->
``subdivision_finishing_system``. humanoid-anatomy tokens ->
``humanoid_anatomy_preset_system``; face-SDF/cel-shading tokens ->
``face_sdf_cel_shading_system``. rig-component-library tokens ->
``rig_component_library_system``; morph-target database tokens ->
``morph_target_database_system``. animation-library binding tokens ->
``animation_library_binding_system``; retargeting-pack tokens ->
``retargeting_pack_system``. character-equipment binding tokens ->
``character_equipment_binding_system``; gameplay-animation controller tokens ->
``gameplay_animation_controller_system``. procedural facial-rig tokens ->
``procedural_facial_rig_pack_system``; hair-program tokens ->
``hair_program_system``. cloth/fabric simulation tokens ->
``cloth_fabric_simulation_program_system``; fluid-forward volume tokens ->
``fluid_forward_volume_program_system``. construction-grammar-kit tokens ->
``construction_grammar_kit_system``; creature-appendage tokens ->
``creature_appendage_program_system``. body-part procedural tokens ->
``body_part_procedural_library_system``; material-primitive/physical-substance
tokens -> ``material_primitive_library_system``. engine-facing runtime tokens ->
``engine_facing_runtime_bundle_system``; procedural-prefab binding tokens ->
``procedural_prefab_binding_system``. scene-system authoring tokens ->
``scene_system_authoring_bundle``; behavior-logic graph tokens ->
``behavior_logic_graph_bundle``. world-streaming/runtime-partition tokens ->
``world_streaming_runtime_partition_bundle``; save-state/persistence tokens ->
``save_state_persistence_bundle``. quest/dialogue authoring tokens ->
``quest_dialogue_authoring_bundle``; camera/cinematic direction tokens ->
``camera_cinematic_direction_bundle``; procedural-audio cue tokens ->
``procedural_audio_cue_bundle``; localization/text-table tokens ->
``localization_text_table_bundle``; accessibility/UX affordance tokens ->
``accessibility_ux_affordance_bundle``; economy/simulation tuning tokens ->
``economy_simulation_tuning_bundle``; multiplayer/session replication tokens ->
``multiplayer_session_replication_bundle``.
If no token matches the asset falls back to the
``generic`` family. Tokens are checked deterministically (no random
sampling, no hashing) so the same input always yields the same family.

The validator is registered in ``lathe/core/stages/validate.py``'s
``_PIPELINE`` first (no stage dependencies, ``weight=0.0``) so the
brief lands on ``runtime["design_brief"]`` before any other validator
runs and is therefore available as input to downstream phases.

Output additively appears under the top-level ``design_brief`` key of
the validate-stage report. Existing report fields are preserved and the
validator never produces blocking diagnostics — like Phase 1, this layer
is informational evidence for downstream classifiers and grammar
checks.

Phase 11 negative-constraint integration
----------------------------------------

When the executor publishes a reference board to
``runtime["_reference_board"]`` (see
``lathe.asset_quality.reference_board``), the brief's
``negative_constraints`` field is extended with each
reference-negative constraint string. Existing per-family default
constraints come first; reference negatives are appended in the order
they appear in the fixture, deduplicated against the existing list.
This is the only Phase 11 edit to ``design_brief.py`` — every other
field of the brief (asset name, family, role, style tags, silhouette,
bevel/shape language, detail density, wear, material age, greeble
style) is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


VERSION = "design_brief_v1"


@dataclass(frozen=True)
class DesignBrief:
    """Immutable record of art-direction intent for one asset.

    All twelve fields are populated for every brief; the per-family
    defaults below guarantee no field is ever ``None``. ``style_tags``
    and ``negative_constraints`` are tuples (not lists) so the dataclass
    remains hashable and frozen.
    """

    asset_name: str
    family: str
    role: str
    style_tags: tuple[str, ...]
    silhouette: str
    bevel_language: str
    shape_language: str
    detail_density: str
    wear: str
    material_age: str
    greeble_style: str
    negative_constraints: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict (lists in place of tuples)."""
        return {
            "asset_name": self.asset_name,
            "family": self.family,
            "role": self.role,
            "style_tags": list(self.style_tags),
            "silhouette": self.silhouette,
            "bevel_language": self.bevel_language,
            "shape_language": self.shape_language,
            "detail_density": self.detail_density,
            "wear": self.wear,
            "material_age": self.material_age,
            "greeble_style": self.greeble_style,
            "negative_constraints": list(self.negative_constraints),
        }


_FAMILY_TOKENS: tuple[tuple[str, str], ...] = (
    ("crate", "industrial_crate"),
    ("door", "mechanical_door"),
    ("cabinet", "service_cabinet"),
    ("weapon", "weapon_prop"),
    ("sword", "weapon_prop"),
    ("blade", "weapon_prop"),
    ("rifle", "weapon_prop"),
    ("vehicle", "vehicle_prop"),
    ("car", "vehicle_prop"),
    ("boat", "vehicle_prop"),
    ("truck", "vehicle_prop"),
    ("furniture", "furniture_prop"),
    ("chair", "furniture_prop"),
    ("table", "furniture_prop"),
    ("shelf", "furniture_prop"),
    ("bed", "furniture_prop"),
    ("bench", "furniture_prop"),
    ("terrain", "natural_form"),
    ("rock", "natural_form"),
    ("tree", "natural_form"),
    ("plant", "natural_form"),
    ("vine", "natural_form"),
    ("mushroom", "natural_form"),
    ("settlement", "settlement_district"),
    ("district", "settlement_district"),
    ("village", "settlement_district"),
    ("town", "settlement_district"),
    ("camp", "settlement_district"),
    ("outpost", "settlement_district"),
    ("neighborhood", "settlement_district"),
    ("world_system", "world_system_assembly"),
    ("world_graph", "world_system_assembly"),
    ("world_layer", "world_system_assembly"),
    ("navigation", "world_system_assembly"),
    ("navmesh", "world_system_assembly"),
    ("nav_mesh", "world_system_assembly"),
    ("quest_chain", "world_system_assembly"),
    ("faction", "world_system_assembly"),
    ("civilization", "world_system_assembly"),
    ("route_network", "world_system_assembly"),
    ("cga_grammar", "cga_building_grammar_system"),
    ("cga_building", "cga_building_grammar_system"),
    ("building_grammar", "cga_building_grammar_system"),
    ("shape_grammar", "cga_building_grammar_system"),
    ("assembly_rules", "cga_building_grammar_system"),
    ("facade_rule", "cga_building_grammar_system"),
    ("split_rule", "cga_building_grammar_system"),
    ("repeat_rule", "cga_building_grammar_system"),
    ("extrude_rule", "cga_building_grammar_system"),
    ("architecture", "environment_architecture"),
    ("building", "environment_architecture"),
    ("structure", "environment_architecture"),
    ("room", "environment_architecture"),
    ("wall", "environment_architecture"),
    ("roof", "environment_architecture"),
    ("corridor", "environment_architecture"),
    ("bridge", "environment_architecture"),
    ("tower", "environment_architecture"),
    ("lighting", "lighting_prop"),
    ("light", "lighting_prop"),
    ("lamp", "lighting_prop"),
    ("lantern", "lighting_prop"),
    ("beacon", "lighting_prop"),
    ("signage", "lighting_prop"),
    ("sign", "lighting_prop"),
    ("machine", "machine_console"),
    ("console", "machine_console"),
    ("terminal", "machine_console"),
    ("generator", "machine_console"),
    ("reactor", "machine_console"),
    ("engine", "machine_console"),
    ("portal", "portal_relic"),
    ("relic", "portal_relic"),
    ("shrine", "portal_relic"),
    ("altar", "portal_relic"),
    ("obelisk", "portal_relic"),
    ("artifact", "portal_relic"),
    ("monument", "portal_relic"),
    ("rune", "portal_relic"),
    ("tool", "tool_prop"),
    ("hammer", "tool_prop"),
    ("wrench", "tool_prop"),
    ("drill", "tool_prop"),
    ("pickaxe", "tool_prop"),
    ("scanner", "tool_prop"),
    ("wfc_tileset", "wfc_tile_solver_system"),
    ("wfc_solver", "wfc_tile_solver_system"),
    ("wave_function_collapse", "wfc_tile_solver_system"),
    ("tile_solver", "wfc_tile_solver_system"),
    ("tile_adjacency", "wfc_tile_solver_system"),
    ("adjacency_rule", "wfc_tile_solver_system"),
    ("socket_constraint", "wfc_tile_solver_system"),
    ("constraint_grid", "wfc_tile_solver_system"),
    ("modular_solver", "wfc_tile_solver_system"),
    ("procedural_prefab_binding", "procedural_prefab_binding_system"),
    ("prefab_binding", "procedural_prefab_binding_system"),
    ("prefab_parameter_binding", "procedural_prefab_binding_system"),
    ("prefab_variant_binding", "procedural_prefab_binding_system"),
    ("engine_prefab_binding", "procedural_prefab_binding_system"),
    ("prefab_output_map", "procedural_prefab_binding_system"),
    ("prefab_slot_binding", "procedural_prefab_binding_system"),
    ("prefab_lod_binding", "procedural_prefab_binding_system"),
    ("prefab_override_table", "procedural_prefab_binding_system"),
    ("prefab_dependency_binding", "procedural_prefab_binding_system"),
    ("modular", "modular_kit"),
    ("tileset", "modular_kit"),
    ("tile", "modular_kit"),
    ("kit", "modular_kit"),
    ("prefab", "modular_kit"),
    ("module", "modular_kit"),
    ("body_part_library", "body_part_procedural_library_system"),
    ("body_part_program", "body_part_procedural_library_system"),
    ("body_part_procedural", "body_part_procedural_library_system"),
    ("anatomy_region_library", "body_part_procedural_library_system"),
    ("head_part_library", "body_part_procedural_library_system"),
    ("torso_part_library", "body_part_procedural_library_system"),
    ("hand_foot_library", "body_part_procedural_library_system"),
    ("organ_socket_map", "body_part_procedural_library_system"),
    ("muscle_group_library", "body_part_procedural_library_system"),
    ("body_part_socket", "body_part_procedural_library_system"),
    ("humanoid_anatomy", "humanoid_anatomy_preset_system"),
    ("anatomy_preset", "humanoid_anatomy_preset_system"),
    ("canonical_topology", "humanoid_anatomy_preset_system"),
    ("adult_male_realistic", "humanoid_anatomy_preset_system"),
    ("adult_female_realistic", "humanoid_anatomy_preset_system"),
    ("child_realistic", "humanoid_anatomy_preset_system"),
    ("chibi_3head", "humanoid_anatomy_preset_system"),
    ("body_proportion", "humanoid_anatomy_preset_system"),
    ("morph_database", "humanoid_anatomy_preset_system"),
    ("face_sdf", "face_sdf_cel_shading_system"),
    ("face_shadow_sdf", "face_sdf_cel_shading_system"),
    ("anime_cel", "face_sdf_cel_shading_system"),
    ("cel_ramp", "face_sdf_cel_shading_system"),
    ("ramp_lut", "face_sdf_cel_shading_system"),
    ("inverted_hull", "face_sdf_cel_shading_system"),
    ("sobel_outline", "face_sdf_cel_shading_system"),
    ("toon_ramp", "face_sdf_cel_shading_system"),
    ("npr_ramp", "face_sdf_cel_shading_system"),
    ("rig_component_library", "rig_component_library_system"),
    ("rig_components", "rig_component_library_system"),
    ("spine_component", "rig_component_library_system"),
    ("limb_component", "rig_component_library_system"),
    ("digit_component", "rig_component_library_system"),
    ("mech_joint", "rig_component_library_system"),
    ("wing_chain", "rig_component_library_system"),
    ("tentacle_chain", "rig_component_library_system"),
    ("ik_fk_template", "rig_component_library_system"),
    ("kinefx_component", "rig_component_library_system"),
    ("morph_target_database", "morph_target_database_system"),
    ("morph_target_library", "morph_target_database_system"),
    ("blendshape", "morph_target_database_system"),
    ("shape_key", "morph_target_database_system"),
    ("corrective_shape", "morph_target_database_system"),
    ("viseme", "morph_target_database_system"),
    ("facial_morph", "morph_target_database_system"),
    ("body_shape_delta", "morph_target_database_system"),
    ("delta_vector", "morph_target_database_system"),
    ("expression_set", "morph_target_database_system"),
    ("animation_library_binding", "animation_library_binding_system"),
    ("animation_library", "animation_library_binding_system"),
    ("motion_clip_library", "animation_library_binding_system"),
    ("clip_library", "animation_library_binding_system"),
    ("pose_library", "animation_library_binding_system"),
    ("locomotion_set", "animation_library_binding_system"),
    ("blend_tree", "animation_library_binding_system"),
    ("animation_state_machine", "animation_library_binding_system"),
    ("combat_idle", "animation_library_binding_system"),
    ("combat_walk", "animation_library_binding_system"),
    ("combat_run", "animation_library_binding_system"),
    ("retargeting_pack", "retargeting_pack_system"),
    ("retargeting", "retargeting_pack_system"),
    ("canonical_to_canonical", "retargeting_pack_system"),
    ("retarget_map", "retargeting_pack_system"),
    ("bone_mapping", "retargeting_pack_system"),
    ("rest_pose_map", "retargeting_pack_system"),
    ("scale_compensation", "retargeting_pack_system"),
    ("motion_retarget", "retargeting_pack_system"),
    ("humanoid_retarget", "retargeting_pack_system"),
    ("source_skeleton", "retargeting_pack_system"),
    ("character_equipment_binding", "character_equipment_binding_system"),
    ("equipment_binding", "character_equipment_binding_system"),
    ("equipment_socket", "character_equipment_binding_system"),
    ("weapon_socket", "character_equipment_binding_system"),
    ("armor_slot", "character_equipment_binding_system"),
    ("holster_slot", "character_equipment_binding_system"),
    ("outfit_binding", "character_equipment_binding_system"),
    ("gear_socket", "character_equipment_binding_system"),
    ("loadout_slot", "character_equipment_binding_system"),
    ("equipment_clearance", "character_equipment_binding_system"),
    ("gameplay_animation_controller", "gameplay_animation_controller_system"),
    ("animation_controller", "gameplay_animation_controller_system"),
    ("locomotion_controller", "gameplay_animation_controller_system"),
    ("combat_controller", "gameplay_animation_controller_system"),
    ("ability_state_machine", "gameplay_animation_controller_system"),
    ("gameplay_state_machine", "gameplay_animation_controller_system"),
    ("input_action_map", "gameplay_animation_controller_system"),
    ("transition_rule", "gameplay_animation_controller_system"),
    ("animation_parameter", "gameplay_animation_controller_system"),
    ("motion_matching", "gameplay_animation_controller_system"),
    ("procedural_facial_rig", "procedural_facial_rig_pack_system"),
    ("facial_rig_pack", "procedural_facial_rig_pack_system"),
    ("face_rig", "procedural_facial_rig_pack_system"),
    ("jaw_control", "procedural_facial_rig_pack_system"),
    ("eye_control", "procedural_facial_rig_pack_system"),
    ("blink_control", "procedural_facial_rig_pack_system"),
    ("brow_control", "procedural_facial_rig_pack_system"),
    ("lip_corner", "procedural_facial_rig_pack_system"),
    ("facial_control_board", "procedural_facial_rig_pack_system"),
    ("expression_driver", "procedural_facial_rig_pack_system"),
    ("hair_program", "hair_program_system"),
    ("strand_grammar", "hair_program_system"),
    ("hair_strand", "hair_program_system"),
    ("hair_cards", "hair_program_system"),
    ("root_density", "hair_program_system"),
    ("length_distribution", "hair_program_system"),
    ("wave_amplitude", "hair_program_system"),
    ("wave_frequency", "hair_program_system"),
    ("groom_region", "hair_program_system"),
    ("hair_color_gradient", "hair_program_system"),
    ("cloth_fabric_simulation", "cloth_fabric_simulation_program_system"),
    ("cloth_program", "cloth_fabric_simulation_program_system"),
    ("fabric_simulation", "cloth_fabric_simulation_program_system"),
    ("xpbd_cloth", "cloth_fabric_simulation_program_system"),
    ("cloth_stiffness", "cloth_fabric_simulation_program_system"),
    ("cloth_damping", "cloth_fabric_simulation_program_system"),
    ("cloth_mass", "cloth_fabric_simulation_program_system"),
    ("cloth_settling", "cloth_fabric_simulation_program_system"),
    ("pinned_cloth", "cloth_fabric_simulation_program_system"),
    ("fabric_solver", "cloth_fabric_simulation_program_system"),
    ("fluid_forward", "fluid_forward_volume_program_system"),
    ("fluid_program", "fluid_forward_volume_program_system"),
    ("fluid_forward_volume", "fluid_forward_volume_program_system"),
    ("asset_level_fluid", "fluid_forward_volume_program_system"),
    ("vdb_fluid", "fluid_forward_volume_program_system"),
    ("advection_field", "fluid_forward_volume_program_system"),
    ("fluid_surface", "fluid_forward_volume_program_system"),
    ("fluid_isosurface", "fluid_forward_volume_program_system"),
    ("fluid_cache", "fluid_forward_volume_program_system"),
    ("fluid_mesh_output", "fluid_forward_volume_program_system"),
    ("construction_grammar_kit", "construction_grammar_kit_system"),
    ("construction_kit_system", "construction_grammar_kit_system"),
    ("modular_construction_grammar", "construction_grammar_kit_system"),
    ("snap_rule_library", "construction_grammar_kit_system"),
    ("building_piece_grammar", "construction_grammar_kit_system"),
    ("kitbash_rule_pack", "construction_grammar_kit_system"),
    ("procedural_assembly_kit", "construction_grammar_kit_system"),
    ("connector_rule_graph", "construction_grammar_kit_system"),
    ("facade_kit_grammar", "construction_grammar_kit_system"),
    ("structural_module_rules", "construction_grammar_kit_system"),
    ("creature_appendage", "creature_appendage_program_system"),
    ("appendage_program", "creature_appendage_program_system"),
    ("wing_appendage", "creature_appendage_program_system"),
    ("tail_appendage", "creature_appendage_program_system"),
    ("tentacle_appendage", "creature_appendage_program_system"),
    ("horn_appendage", "creature_appendage_program_system"),
    ("claw_appendage", "creature_appendage_program_system"),
    ("fin_appendage", "creature_appendage_program_system"),
    ("limb_variant", "creature_appendage_program_system"),
    ("appendage_socket", "creature_appendage_program_system"),
    ("character", "character_creature"),
    ("creature", "character_creature"),
    ("humanoid", "character_creature"),
    ("npc", "character_creature"),
    ("monster", "character_creature"),
    ("avatar", "character_creature"),
    ("companion", "character_creature"),
    ("set_dressing", "set_dressing_prop"),
    ("clutter", "set_dressing_prop"),
    ("barrel", "set_dressing_prop"),
    ("basket", "set_dressing_prop"),
    ("sack", "set_dressing_prop"),
    ("bag", "set_dressing_prop"),
    ("jar", "set_dressing_prop"),
    ("pot", "set_dressing_prop"),
    ("material_primitive", "material_primitive_library_system"),
    ("physical_substance", "material_primitive_library_system"),
    ("substance_taxonomy", "material_primitive_library_system"),
    ("pbr_primitive", "material_primitive_library_system"),
    ("metal_rough_primitive", "material_primitive_library_system"),
    ("dielectric_material", "material_primitive_library_system"),
    ("emissive_material", "material_primitive_library_system"),
    ("translucent_material", "material_primitive_library_system"),
    ("procedural_substance", "material_primitive_library_system"),
    ("material_preset_library", "material_primitive_library_system"),
    ("surface", "surface_material_sample"),
    ("material", "surface_material_sample"),
    ("texture", "surface_material_sample"),
    ("trim_sheet", "surface_material_sample"),
    ("decal_sheet", "surface_material_sample"),
    ("pbr", "surface_material_sample"),
    ("swatch", "surface_material_sample"),
    ("vegetation_library", "vegetation_library_system"),
    ("vegetation_kit", "vegetation_library_system"),
    ("speedtree", "vegetation_library_system"),
    ("tree_library", "vegetation_library_system"),
    ("species_library", "vegetation_library_system"),
    ("branching_grammar", "vegetation_library_system"),
    ("canopy_library", "vegetation_library_system"),
    ("root_system", "vegetation_library_system"),
    ("terrain_heightfield", "terrain_heightfield_system"),
    ("heightfield_terrain", "terrain_heightfield_system"),
    ("heightfield_system", "terrain_heightfield_system"),
    ("terrain_program", "terrain_heightfield_system"),
    ("terrain_kit", "terrain_heightfield_system"),
    ("erosion", "terrain_heightfield_system"),
    ("hydraulic_erosion", "terrain_heightfield_system"),
    ("thermal_erosion", "terrain_heightfield_system"),
    ("biome_field", "terrain_heightfield_system"),
    ("heightfield", "terrain_heightfield_system"),
    ("foliage", "terrain_vegetation_variant"),
    ("grass", "terrain_vegetation_variant"),
    ("flower", "terrain_vegetation_variant"),
    ("canopy", "terrain_vegetation_variant"),
    ("biome", "terrain_vegetation_variant"),
    ("simulation", "simulation_environment_system"),
    ("sim_system", "simulation_environment_system"),
    ("physics_field", "simulation_environment_system"),
    ("flow_field", "simulation_environment_system"),
    ("wind_field", "simulation_environment_system"),
    ("heat_field", "simulation_environment_system"),
    ("pressure_field", "simulation_environment_system"),
    ("constraint_solver", "simulation_environment_system"),
    ("erosion_solver", "simulation_environment_system"),
    ("fluid_solver", "simulation_environment_system"),
    ("particle_system", "simulation_environment_system"),
    ("weather_system", "simulation_environment_system"),
    ("volume_field", "volume_effects_data_system"),
    ("vdb_volume", "volume_effects_data_system"),
    ("sparse_volume", "volume_effects_data_system"),
    ("volume_effect", "volume_effects_data_system"),
    ("fluid_volume", "volume_effects_data_system"),
    ("smoke_volume", "volume_effects_data_system"),
    ("magic_volume", "volume_effects_data_system"),
    ("density_field", "volume_effects_data_system"),
    ("temperature_field", "volume_effects_data_system"),
    ("velocity_field", "volume_effects_data_system"),
    ("instance_pattern", "instance_pattern_scatter_system"),
    ("scatter_program", "instance_pattern_scatter_system"),
    ("scatter_system", "instance_pattern_scatter_system"),
    ("surface_scatter", "instance_pattern_scatter_system"),
    ("greeble_scatter", "instance_pattern_scatter_system"),
    ("poisson_scatter", "instance_pattern_scatter_system"),
    ("copy_to_points", "instance_pattern_scatter_system"),
    ("point_instance", "instance_pattern_scatter_system"),
    ("surface_projected", "instance_pattern_scatter_system"),
    ("f_rep", "f_rep_sdf_composition_system"),
    ("frep", "f_rep_sdf_composition_system"),
    ("sdf_blend", "f_rep_sdf_composition_system"),
    ("sdf_composition", "f_rep_sdf_composition_system"),
    ("signed_distance", "f_rep_sdf_composition_system"),
    ("implicit_surface", "f_rep_sdf_composition_system"),
    ("smooth_union", "f_rep_sdf_composition_system"),
    ("smooth_subtract", "f_rep_sdf_composition_system"),
    ("distance_field", "f_rep_sdf_composition_system"),
    ("opensubdiv", "subdivision_finishing_system"),
    ("subdivision_cage", "subdivision_finishing_system"),
    ("subdivision_finish", "subdivision_finishing_system"),
    ("catmull_clark", "subdivision_finishing_system"),
    ("loop_subdivision", "subdivision_finishing_system"),
    ("crease_tag", "subdivision_finishing_system"),
    ("remesh_finishing", "subdivision_finishing_system"),
    ("quadrangulate", "subdivision_finishing_system"),
    ("smooth_pass", "subdivision_finishing_system"),
    ("water", "environment_effect"),
    ("river", "environment_effect"),
    ("lake", "environment_effect"),
    ("waterfall", "environment_effect"),
    ("weather", "environment_effect"),
    ("rain", "environment_effect"),
    ("snow", "environment_effect"),
    ("fog", "environment_effect"),
    ("smoke", "environment_effect"),
    ("effect", "environment_effect"),
    ("vfx", "environment_effect"),
    ("encounter_flow", "encounter_flow"),
    ("encounter", "encounter_flow"),
    ("arena", "encounter_flow"),
    ("combat", "encounter_flow"),
    ("wave", "encounter_flow"),
    ("patrol", "encounter_flow"),
    ("cover", "encounter_flow"),
    ("ambush", "encounter_flow"),
    ("boss", "encounter_flow"),
    ("economy_simulation_tuning", "economy_simulation_tuning_bundle"),
    ("economy_tuning_bundle", "economy_simulation_tuning_bundle"),
    ("simulation_tuning_table", "economy_simulation_tuning_bundle"),
    ("resource_flow_graph", "economy_simulation_tuning_bundle"),
    ("currency_sink_source", "economy_simulation_tuning_bundle"),
    ("loot_drop_table", "economy_simulation_tuning_bundle"),
    ("price_curve_map", "economy_simulation_tuning_bundle"),
    ("progression_balance_curve", "economy_simulation_tuning_bundle"),
    ("spawn_rate_tuning", "economy_simulation_tuning_bundle"),
    ("market_rule_graph", "economy_simulation_tuning_bundle"),
    ("inventory", "inventory_economy_object"),
    ("economy", "inventory_economy_object"),
    ("currency", "inventory_economy_object"),
    ("coin", "inventory_economy_object"),
    ("loot", "inventory_economy_object"),
    ("shop", "inventory_economy_object"),
    ("vendor", "inventory_economy_object"),
    ("stash", "inventory_economy_object"),
    ("container", "inventory_economy_object"),
    ("resource", "inventory_economy_object"),
    ("collectible", "inventory_economy_object"),
    ("parametric_rig", "rig_animation_proxy"),
    ("rig_component", "rig_animation_proxy"),
    ("skeleton", "rig_animation_proxy"),
    ("bone", "rig_animation_proxy"),
    ("ik", "rig_animation_proxy"),
    ("morph", "rig_animation_proxy"),
    ("animation", "rig_animation_proxy"),
    ("pose", "rig_animation_proxy"),
    ("joint_chain", "rig_animation_proxy"),
    ("destructible", "stateful_destructible_prop"),
    ("destruction", "stateful_destructible_prop"),
    ("breakable", "stateful_destructible_prop"),
    ("fracture", "stateful_destructible_prop"),
    ("damage", "stateful_destructible_prop"),
    ("stateful", "stateful_destructible_prop"),
    ("state_machine", "stateful_destructible_prop"),
    ("health", "stateful_destructible_prop"),
    ("repair", "stateful_destructible_prop"),
    ("cracked", "stateful_destructible_prop"),
    ("ruined", "stateful_destructible_prop"),
    ("cloth_panel", "cloth_attachment_form"),
    ("cloth", "cloth_attachment_form"),
    ("fabric", "cloth_attachment_form"),
    ("garment", "cloth_attachment_form"),
    ("cape", "cloth_attachment_form"),
    ("cloak", "cloth_attachment_form"),
    ("banner", "cloth_attachment_form"),
    ("flag", "cloth_attachment_form"),
    ("tether", "cloth_attachment_form"),
    ("strap", "cloth_attachment_form"),
    ("attachment", "cloth_attachment_form"),
    ("hook", "cloth_attachment_form"),
    ("domain_kit", "domain_kit_bundle"),
    ("kit_bundle", "domain_kit_bundle"),
    ("domain_library", "domain_kit_bundle"),
    ("library_pack", "domain_kit_bundle"),
    ("style_pack", "domain_kit_bundle"),
    ("asset_pack", "domain_kit_bundle"),
    ("production_pack", "domain_kit_bundle"),
    ("building_set", "domain_kit_bundle"),
    ("vehicle_set", "domain_kit_bundle"),
    ("weapon_set", "domain_kit_bundle"),
    ("prop_set", "domain_kit_bundle"),
    ("camera_cinematic_direction", "camera_cinematic_direction_bundle"),
    ("cinematic_direction_bundle", "camera_cinematic_direction_bundle"),
    ("camera_rig_graph", "camera_cinematic_direction_bundle"),
    ("cinematic_camera_path", "camera_cinematic_direction_bundle"),
    ("shot_sequence_graph", "camera_cinematic_direction_bundle"),
    ("cutscene_timeline", "camera_cinematic_direction_bundle"),
    ("lens_rig_binding", "camera_cinematic_direction_bundle"),
    ("camera_blend_stack", "camera_cinematic_direction_bundle"),
    ("look_at_target_track", "camera_cinematic_direction_bundle"),
    ("cinematic_trigger_map", "camera_cinematic_direction_bundle"),
    ("procedural_audio_cue", "procedural_audio_cue_bundle"),
    ("audio_cue_bundle", "procedural_audio_cue_bundle"),
    ("sound_cue_graph", "procedural_audio_cue_bundle"),
    ("sfx_cue_map", "procedural_audio_cue_bundle"),
    ("music_stem_binding", "procedural_audio_cue_bundle"),
    ("ambience_layer", "procedural_audio_cue_bundle"),
    ("attenuation_zone", "procedural_audio_cue_bundle"),
    ("reverb_send_map", "procedural_audio_cue_bundle"),
    ("vo_trigger_cue", "procedural_audio_cue_bundle"),
    ("audio_event_bus", "procedural_audio_cue_bundle"),
    ("localization_text_table", "localization_text_table_bundle"),
    ("text_table_bundle", "localization_text_table_bundle"),
    ("localization_table", "localization_text_table_bundle"),
    ("string_table", "localization_text_table_bundle"),
    ("translation_key_map", "localization_text_table_bundle"),
    ("subtitle_timing_table", "localization_text_table_bundle"),
    ("pluralization_rule_table", "localization_text_table_bundle"),
    ("locale_fallback_chain", "localization_text_table_bundle"),
    ("voiceover_text_binding", "localization_text_table_bundle"),
    ("font_glyph_coverage", "localization_text_table_bundle"),
    ("accessibility_ux_affordance", "accessibility_ux_affordance_bundle"),
    ("ux_affordance_bundle", "accessibility_ux_affordance_bundle"),
    ("accessibility_affordance", "accessibility_ux_affordance_bundle"),
    ("input_remap_map", "accessibility_ux_affordance_bundle"),
    ("readability_cue_map", "accessibility_ux_affordance_bundle"),
    ("contrast_safe_region", "accessibility_ux_affordance_bundle"),
    ("subtitle_caption_affordance", "accessibility_ux_affordance_bundle"),
    ("haptic_feedback_map", "accessibility_ux_affordance_bundle"),
    ("focus_navigation_graph", "accessibility_ux_affordance_bundle"),
    ("accessibility_option_panel", "accessibility_ux_affordance_bundle"),
    ("multiplayer_session_replication", "multiplayer_session_replication_bundle"),
    ("session_replication_bundle", "multiplayer_session_replication_bundle"),
    ("replication_state_graph", "multiplayer_session_replication_bundle"),
    ("network_session_map", "multiplayer_session_replication_bundle"),
    ("authority_ownership_map", "multiplayer_session_replication_bundle"),
    ("sync_tick_timeline", "multiplayer_session_replication_bundle"),
    ("prediction_reconciliation", "multiplayer_session_replication_bundle"),
    ("rollback_state_buffer", "multiplayer_session_replication_bundle"),
    ("rpc_event_bus", "multiplayer_session_replication_bundle"),
    ("matchmaking_session_rule", "multiplayer_session_replication_bundle"),
    ("scene_system_authoring", "scene_system_authoring_bundle"),
    ("scene_authoring_bundle", "scene_system_authoring_bundle"),
    ("scene_graph_authoring", "scene_system_authoring_bundle"),
    ("scene_hierarchy", "scene_system_authoring_bundle"),
    ("placement_layer", "scene_system_authoring_bundle"),
    ("spawn_layer", "scene_system_authoring_bundle"),
    ("lighting_layer", "scene_system_authoring_bundle"),
    ("navmesh_layer", "scene_system_authoring_bundle"),
    ("camera_bookmark", "scene_system_authoring_bundle"),
    ("scene_validation_layer", "scene_system_authoring_bundle"),
    ("world_streaming_partition", "world_streaming_runtime_partition_bundle"),
    ("runtime_partition_bundle", "world_streaming_runtime_partition_bundle"),
    ("world_partition", "world_streaming_runtime_partition_bundle"),
    ("streaming_cell_grid", "world_streaming_runtime_partition_bundle"),
    ("streaming_volume", "world_streaming_runtime_partition_bundle"),
    ("sector_streaming", "world_streaming_runtime_partition_bundle"),
    ("lod_streaming_partition", "world_streaming_runtime_partition_bundle"),
    ("occlusion_partition", "world_streaming_runtime_partition_bundle"),
    ("runtime_chunk_graph", "world_streaming_runtime_partition_bundle"),
    ("world_load_group", "world_streaming_runtime_partition_bundle"),
    ("multi_asset", "authored_multi_asset_bundle"),
    ("asset_bundle", "authored_multi_asset_bundle"),
    ("scene_bundle", "authored_multi_asset_bundle"),
    ("asset_collection", "authored_multi_asset_bundle"),
    ("bundle_manifest", "authored_multi_asset_bundle"),
    ("prefab_collection", "authored_multi_asset_bundle"),
    ("set_piece", "authored_multi_asset_bundle"),
    ("hero_set", "authored_multi_asset_bundle"),
    ("unity_lathe_plugin", "engine_facing_runtime_bundle_system"),
    ("unreal_lathe_plugin", "engine_facing_runtime_bundle_system"),
    ("usd_hydra_procedural", "engine_facing_runtime_bundle_system"),
    ("hydra_generative", "engine_facing_runtime_bundle_system"),
    ("engine_plugin_binding", "engine_facing_runtime_bundle_system"),
    ("dcc_runtime_adapter", "engine_facing_runtime_bundle_system"),
    ("lathe_bundle_runtime", "engine_facing_runtime_bundle_system"),
    ("host_parameter_override", "engine_facing_runtime_bundle_system"),
    ("engine_asset_sink", "engine_facing_runtime_bundle_system"),
    ("runtime_host_contract", "engine_facing_runtime_bundle_system"),
    ("live_procedural", "live_procedural_runtime_bundle"),
    ("runtime_bundle", "live_procedural_runtime_bundle"),
    ("lathe_engine", "live_procedural_runtime_bundle"),
    ("engine_runtime", "live_procedural_runtime_bundle"),
    ("procedural_runtime", "live_procedural_runtime_bundle"),
    ("runtime_override", "live_procedural_runtime_bundle"),
    ("live_update", "live_procedural_runtime_bundle"),
    ("engine_hook", "live_procedural_runtime_bundle"),
    ("cross_domain", "cross_domain_composition_pack"),
    ("composition_pack", "cross_domain_composition_pack"),
    ("hybrid_bundle", "cross_domain_composition_pack"),
    ("world_asset_mix", "cross_domain_composition_pack"),
    ("gameplay_bundle", "cross_domain_composition_pack"),
    ("environment_bundle", "cross_domain_composition_pack"),
    ("asset_ecosystem", "cross_domain_composition_pack"),
    ("content_band", "cross_domain_composition_pack"),
    ("style_stack", "style_stack_visual_band"),
    ("style_target", "style_stack_visual_band"),
    ("visual_band", "style_stack_visual_band"),
    ("construction_grammar", "style_stack_visual_band"),
    ("stylized_pbr", "style_stack_visual_band"),
    ("toon", "style_stack_visual_band"),
    ("cel_shaded", "style_stack_visual_band"),
    ("photoreal", "style_stack_visual_band"),
    ("low_poly", "style_stack_visual_band"),
    ("claymation", "style_stack_visual_band"),
    ("lego", "style_stack_visual_band"),
    ("typed_data", "typed_data_kernel_bundle"),
    ("typed_bundle", "typed_data_kernel_bundle"),
    ("typed_kernel", "typed_data_kernel_bundle"),
    ("kernel_bus", "typed_data_kernel_bundle"),
    ("data_slot", "typed_data_kernel_bundle"),
    ("heightfield_slot", "typed_data_kernel_bundle"),
    ("point_cloud", "typed_data_kernel_bundle"),
    ("volume_slot", "typed_data_kernel_bundle"),
    ("rig_slot", "typed_data_kernel_bundle"),
    ("surface_graph", "attribute_surface_graph_program"),
    ("surface_program", "attribute_surface_graph_program"),
    ("attr_lang", "attribute_surface_graph_program"),
    ("attribute_program", "attribute_surface_graph_program"),
    ("designer_graph", "attribute_surface_graph_program"),
    ("photo_fit", "attribute_surface_graph_program"),
    ("layer_stack", "attribute_surface_graph_program"),
    ("materialx", "attribute_surface_graph_program"),
    ("smart_mask", "attribute_surface_graph_program"),
    ("behavior_logic_graph", "behavior_logic_graph_bundle"),
    ("behavior_graph", "behavior_logic_graph_bundle"),
    ("logic_graph", "behavior_logic_graph_bundle"),
    ("state_logic_graph", "behavior_logic_graph_bundle"),
    ("event_action_graph", "behavior_logic_graph_bundle"),
    ("condition_rule_graph", "behavior_logic_graph_bundle"),
    ("blackboard_binding", "behavior_logic_graph_bundle"),
    ("behavior_tree_binding", "behavior_logic_graph_bundle"),
    ("utility_ai_graph", "behavior_logic_graph_bundle"),
    ("scriptless_behavior", "behavior_logic_graph_bundle"),
    ("save_state_persistence", "save_state_persistence_bundle"),
    ("save_state_bundle", "save_state_persistence_bundle"),
    ("persistence_bundle", "save_state_persistence_bundle"),
    ("checkpoint_state", "save_state_persistence_bundle"),
    ("runtime_snapshot", "save_state_persistence_bundle"),
    ("persistent_actor_state", "save_state_persistence_bundle"),
    ("inventory_persistence", "save_state_persistence_bundle"),
    ("quest_state_persistence", "save_state_persistence_bundle"),
    ("world_state_delta", "save_state_persistence_bundle"),
    ("save_schema_version", "save_state_persistence_bundle"),
    ("quest_dialogue_authoring", "quest_dialogue_authoring_bundle"),
    ("quest_dialogue_bundle", "quest_dialogue_authoring_bundle"),
    ("dialogue_graph", "quest_dialogue_authoring_bundle"),
    ("dialog_tree", "quest_dialogue_authoring_bundle"),
    ("dialogue_choice_map", "quest_dialogue_authoring_bundle"),
    ("quest_objective_graph", "quest_dialogue_authoring_bundle"),
    ("quest_reward_table", "quest_dialogue_authoring_bundle"),
    ("npc_dialogue_binding", "quest_dialogue_authoring_bundle"),
    ("branching_dialogue", "quest_dialogue_authoring_bundle"),
    ("conversation_state", "quest_dialogue_authoring_bundle"),
    ("gameplay", "gameplay_object"),
    ("quest", "gameplay_object"),
    ("objective", "gameplay_object"),
    ("checkpoint", "gameplay_object"),
    ("pickup", "gameplay_object"),
    ("trigger", "gameplay_object"),
    ("spawn", "gameplay_object"),
    ("switch", "gameplay_object"),
)

_FAMILY_HINT_ALIASES: dict[str, str] = {
    "container": "industrial_crate",
    "crate_family": "industrial_crate",
    "dressing_crate": "industrial_crate",
    "dressing_crate_family": "industrial_crate",
    "environment_structure": "environment_architecture",
    "environment_module": "environment_architecture",
    "navigation_marker": "world_system_assembly",
    "hero_prop": "set_dressing_prop",
    "interactive_mechanism": "gameplay_object",
    "practical_light": "lighting_prop",
    "light_family": "lighting_prop",
    "machine": "machine_console",
    "prop": "set_dressing_prop",
    "weapon": "weapon_prop",
    "vehicle": "vehicle_prop",
    "furniture": "furniture_prop",
    "natural": "natural_form",
    "architecture": "environment_architecture",
}

_INTENT_FAMILY_HINT_FIELDS: tuple[str, ...] = (
    "family",
    "source_family",
    "asset_family",
    "object_family",
    "family_hint",
    "content_family",
)

_AUTHORED_CONTENT_TOKEN_FIELDS: tuple[tuple[str, ...], ...] = (
    ("intent", "parts"),
    ("intent", "materials"),
    ("intent", "interactions"),
    ("features", "allow"),
    ("assembly", "components"),
    ("assembly", "mechanisms"),
    ("assembly", "traits"),
    ("surface", "materials"),
    ("surface", "patterns"),
)


_FAMILY_DEFAULTS: dict[str, dict[str, Any]] = {
    "industrial_crate": {
        "role": "reinforced industrial cargo crate",
        "style_tags": ("utility", "industrial", "shipping"),
        "silhouette": "bold",
        "bevel_language": "chunky_industrial",
        "shape_language": "rectangular_with_45deg_cuts",
        "detail_density": "hero",
        "wear": "medium_edge_wear",
        "material_age": "used_not_destroyed",
        "greeble_style": "functional_only",
        "negative_constraints": ("toy_like", "random_faceting", "ornate"),
    },
    "mechanical_door": {
        "role": "industrial mechanical access door",
        "style_tags": ("utility", "industrial", "access"),
        "silhouette": "balanced",
        "bevel_language": "crisp_industrial",
        "shape_language": "framed_panel_with_inset_leaf",
        "detail_density": "hero",
        "wear": "medium_edge_wear",
        "material_age": "used_not_destroyed",
        "greeble_style": "functional_only",
        "negative_constraints": ("toy_like", "random_faceting", "ornate"),
    },
    "service_cabinet": {
        "role": "wall-mounted service utility cabinet",
        "style_tags": ("utility", "industrial", "service"),
        "silhouette": "compact",
        "bevel_language": "crisp_industrial",
        "shape_language": "rectangular_panelled_box",
        "detail_density": "hero",
        "wear": "light_edge_wear",
        "material_age": "in_service",
        "greeble_style": "functional_only",
        "negative_constraints": ("toy_like", "random_faceting", "ornate"),
    },
    "weapon_prop": {
        "role": "hero hard-surface weapon prop",
        "style_tags": ("utility", "weapon", "hero_prop"),
        "silhouette": "readable_linear_profile",
        "bevel_language": "crisp_functional_edges",
        "shape_language": "linear_body_with_grip_guard_and_barrel_or_blade",
        "detail_density": "hero",
        "wear": "edge_contact_wear",
        "material_age": "used_not_destroyed",
        "greeble_style": "functional_only",
        "negative_constraints": ("toy_like", "random_faceting", "ornate", "unsafe_realism"),
    },
    "vehicle_prop": {
        "role": "procedural transport vehicle prop",
        "style_tags": ("utility", "vehicle", "transport"),
        "silhouette": "strong_chassis_with_motion_affordances",
        "bevel_language": "chunky_mechanical",
        "shape_language": "chassis_cabin_wheels_or_hull_and_thrusters",
        "detail_density": "hero",
        "wear": "medium_edge_wear",
        "material_age": "in_service",
        "greeble_style": "functional_only",
        "negative_constraints": ("toy_like", "random_faceting", "ornate"),
    },
    "furniture_prop": {
        "role": "usable stylized furniture prop",
        "style_tags": ("furniture", "interior", "hero_prop"),
        "silhouette": "clear_contact_surfaces_and_supports",
        "bevel_language": "soft_functional_edges",
        "shape_language": "surface_support_back_or_storage_with_trim",
        "detail_density": "hero",
        "wear": "light_contact_wear",
        "material_age": "in_service",
        "greeble_style": "functional_only",
        "negative_constraints": ("toy_like", "random_faceting", "ornate"),
    },
    "natural_form": {
        "role": "procedural natural terrain or vegetation form",
        "style_tags": ("natural", "terrain", "organic"),
        "silhouette": "asymmetric_organic_read",
        "bevel_language": "soft_eroded_edges",
        "shape_language": "terrain_mass_with_swept_growth_and_clustered_forms",
        "detail_density": "hero",
        "wear": "natural_edge_weathering",
        "material_age": "organic_weathered",
        "greeble_style": "growth_rhythm",
        "negative_constraints": ("box_stack", "random_faceting", "ornate_mechanical"),
    },
    "environment_architecture": {
        "role": "procedural environment architecture module",
        "style_tags": ("environment", "architecture", "modular"),
        "silhouette": "readable_enclosure_with_openings_and_roofline",
        "bevel_language": "crisp_structural_edges",
        "shape_language": "floor_walls_openings_roof_supports_and_facade_rhythm",
        "detail_density": "hero",
        "wear": "environment_edge_weathering",
        "material_age": "in_service",
        "greeble_style": "structural_only",
        "negative_constraints": ("toy_like", "random_faceting", "ornate"),
    },
    "lighting_prop": {
        "role": "procedural lighting or signage prop",
        "style_tags": ("environment", "lighting", "readability"),
        "silhouette": "clear_support_emitter_and_visible_glow_zone",
        "bevel_language": "soft_mechanical_edges",
        "shape_language": "base_support_arm_emitter_lens_housing_and_signage",
        "detail_density": "hero",
        "wear": "handled_edge_wear",
        "material_age": "in_service",
        "greeble_style": "functional_only",
        "negative_constraints": ("toy_like", "random_faceting", "ornate"),
    },
    "machine_console": {
        "role": "procedural machine or interactive console prop",
        "style_tags": ("machine", "interactive", "industrial"),
        "silhouette": "readable_machine_body_with_control_face_and_service_access",
        "bevel_language": "chunky_mechanical",
        "shape_language": "body_control_panel_screen_inputs_ports_cooling_and_cables",
        "detail_density": "hero",
        "wear": "service_edge_wear",
        "material_age": "in_service",
        "greeble_style": "functional_only",
        "negative_constraints": ("toy_like", "random_faceting", "ornate"),
    },
    "portal_relic": {
        "role": "procedural portal, relic, shrine, or ritual artifact",
        "style_tags": ("environment", "relic", "mystic_machine"),
        "silhouette": "anchored_frame_with_active_threshold_or_core",
        "bevel_language": "carved_structural_edges",
        "shape_language": "base_frame_threshold_nodes_runes_conduits_and_age_marks",
        "detail_density": "hero",
        "wear": "ancient_edge_weathering",
        "material_age": "ancient_active",
        "greeble_style": "symbolic_functional",
        "negative_constraints": ("toy_like", "random_faceting", "plain_box"),
    },
    "tool_prop": {
        "role": "procedural handheld or workshop tool prop",
        "style_tags": ("tool", "utility", "held_prop"),
        "silhouette": "clear_grip_spine_and_working_head",
        "bevel_language": "functional_worn_edges",
        "shape_language": "handle_shaft_working_head_guard_joint_and_fasteners",
        "detail_density": "hero",
        "wear": "handled_edge_wear",
        "material_age": "used_not_destroyed",
        "greeble_style": "functional_only",
        "negative_constraints": ("toy_like", "random_faceting", "ornate"),
    },
    "modular_kit": {
        "role": "procedural modular kit or tileset piece",
        "style_tags": ("modular", "kit", "world_building"),
        "silhouette": "clear_tile_body_with_ports_and_snap_edges",
        "bevel_language": "repeatable_structural_edges",
        "shape_language": "tile_body_snap_ports_connector_edges_variants_and_labels",
        "detail_density": "hero",
        "wear": "repeatable_edge_wear",
        "material_age": "in_service",
        "greeble_style": "structural_only",
        "negative_constraints": ("toy_like", "random_faceting", "orphan_detail"),
    },
    "character_creature": {
        "role": "procedural stylized character or creature form",
        "style_tags": ("character", "creature", "stylized_form"),
        "silhouette": "readable_body_head_limb_and_pose_line",
        "bevel_language": "soft_anatomical_or_constructed_edges",
        "shape_language": "torso_head_limbs_joints_hands_feet_features_and_scale_cues",
        "detail_density": "hero",
        "wear": "contact_and_pose_edge_wear",
        "material_age": "alive_or_constructed",
        "greeble_style": "anatomical_or_functional",
        "negative_constraints": ("box_stack", "random_faceting", "unclear_pose"),
    },
    "set_dressing_prop": {
        "role": "procedural set-dressing prop or world clutter object",
        "style_tags": ("set_dressing", "world_detail", "prop_cluster"),
        "silhouette": "clear_primary_prop_with_secondary_scale_details",
        "bevel_language": "handled_and_worn_edges",
        "shape_language": "primary_volume_secondary_forms_straps_labels_handles_and_scatter",
        "detail_density": "hero",
        "wear": "handled_floor_contact_wear",
        "material_age": "used_not_destroyed",
        "greeble_style": "functional_only",
        "negative_constraints": ("toy_like", "random_faceting", "orphan_detail"),
    },
    "surface_material_sample": {
        "role": "procedural material, trim-sheet, or surface sample",
        "style_tags": ("surface", "material", "trim_sheet"),
        "silhouette": "flat_sample_with_readable_channels_and_relief",
        "bevel_language": "sample_tile_edges",
        "shape_language": "sample_tile_material_zones_relief_lines_decals_wear_and_labels",
        "detail_density": "hero",
        "wear": "material_test_edge_wear",
        "material_age": "configurable",
        "greeble_style": "surface_only",
        "negative_constraints": ("toy_like", "random_faceting", "unlabeled_material"),
    },
    "terrain_vegetation_variant": {
        "role": "procedural terrain, foliage, or biome variant module",
        "style_tags": ("terrain", "vegetation", "biome"),
        "silhouette": "layered_ground_with_growth_clusters_and_scale_anchors",
        "bevel_language": "soft_eroded_and_organic_edges",
        "shape_language": "ground_plate_height_variation_growth_clusters_paths_scatter_and_erosion",
        "detail_density": "hero",
        "wear": "erosion_and_growth_contact_masks",
        "material_age": "weathered_natural",
        "greeble_style": "growth_rhythm",
        "negative_constraints": ("box_stack", "random_faceting", "ornate_mechanical"),
    },
    "environment_effect": {
        "role": "procedural water, weather, fog, smoke, or world effect volume",
        "style_tags": ("environment", "effect", "atmosphere"),
        "silhouette": "readable_emitter_flow_volume_and_contact_zone",
        "bevel_language": "soft_flowing_or_diffuse_edges",
        "shape_language": "emitter_surface_flow_lines_volume_puffs_ripples_particles_and_masks",
        "detail_density": "hero",
        "wear": "wetness_or_deposition_masks",
        "material_age": "active_dynamic",
        "greeble_style": "phenomenon_only",
        "negative_constraints": ("box_stack", "random_faceting", "static_dead_shape"),
    },
    "settlement_district": {
        "role": "procedural settlement, district, or outpost layout module",
        "style_tags": ("world", "settlement", "layout"),
        "silhouette": "readable_blocks_paths_landmarks_and_thresholds",
        "bevel_language": "structural_world_edges",
        "shape_language": "plots_paths_landmarks_edges_activity_zones_and_connectors",
        "detail_density": "hero",
        "wear": "traffic_and_settlement_edge_wear",
        "material_age": "inhabited",
        "greeble_style": "layout_functional",
        "negative_constraints": ("toy_like", "random_faceting", "orphan_detail"),
    },
    "gameplay_object": {
        "role": "procedural authored gameplay object or encounter marker",
        "style_tags": ("gameplay", "interactive", "readable"),
        "silhouette": "clear_interaction_body_state_marker_and_trigger_zone",
        "bevel_language": "readable_interaction_edges",
        "shape_language": "body_marker_trigger_zone_state_cues_rewards_and_safety_bounds",
        "detail_density": "hero",
        "wear": "interaction_edge_wear",
        "material_age": "active",
        "greeble_style": "interaction_only",
        "negative_constraints": ("toy_like", "random_faceting", "unclear_affordance"),
    },
    "encounter_flow": {
        "role": "procedural encounter, arena, patrol, or combat-flow module",
        "style_tags": ("world", "encounter", "flow"),
        "silhouette": "readable_arena_routes_spawn_points_cover_and_exit",
        "bevel_language": "gameplay_readability_edges",
        "shape_language": "footprint_spawn_routes_cover_objectives_waves_rewards_hazards_and_pacing_masks",
        "detail_density": "hero",
        "wear": "combat_route_and_pressure_wear",
        "material_age": "active",
        "greeble_style": "gameplay_functional",
        "negative_constraints": ("toy_like", "random_faceting", "unclear_flow"),
    },
    "inventory_economy_object": {
        "role": "procedural inventory, economy, loot, vendor, or resource object",
        "style_tags": ("inventory", "economy", "readable"),
        "silhouette": "clear_item_body_value_marker_stack_slots_and_access",
        "bevel_language": "handled_value_object_edges",
        "shape_language": "container_value_markers_quantity_stack_rarity_slots_locks_labels_and_ports",
        "detail_density": "hero",
        "wear": "handled_pickup_and_storage_wear",
        "material_age": "used_not_destroyed",
        "greeble_style": "value_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "unreadable_value"),
    },
    "rig_animation_proxy": {
        "role": "procedural rig, pose, animation, or articulation proxy",
        "style_tags": ("rig", "animation", "articulation"),
        "silhouette": "readable_root_joint_chain_motion_arc_and_control_targets",
        "bevel_language": "control_and_articulation_edges",
        "shape_language": "root_controls_bones_joints_ik_targets_motion_arcs_sockets_limits_and_weight_zones",
        "detail_density": "hero",
        "wear": "articulation_contact_and_range_wear",
        "material_age": "active",
        "greeble_style": "control_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "unclear_articulation"),
    },
    "stateful_destructible_prop": {
        "role": "procedural stateful, damageable, repairable, or destructible prop",
        "style_tags": ("stateful", "destructible", "interactive"),
        "silhouette": "readable_intact_body_damage_states_break_lines_and_repair_points",
        "bevel_language": "damage_state_and_break_edge_language",
        "shape_language": "intact_shell_fracture_lines_state_markers_damage_zones_fragments_repair_ports_and_health_cues",
        "detail_density": "hero",
        "wear": "damage_progression_and_repair_wear",
        "material_age": "variable_state",
        "greeble_style": "state_feedback_only",
        "negative_constraints": ("toy_like", "random_faceting", "unclear_state"),
    },
    "cloth_attachment_form": {
        "role": "procedural cloth, banner, cape, strap, tether, or attachment form",
        "style_tags": ("cloth", "attachment", "motion_readable"),
        "silhouette": "readable_anchor_drape_folds_attachment_points_and_motion",
        "bevel_language": "soft_folded_edges_and_reinforced_attachment_points",
        "shape_language": "anchors_fabric_panels_seams_folds_hooks_tethers_borders_motion_cues_and_wear",
        "detail_density": "hero",
        "wear": "fold_attachment_and_edge_wear",
        "material_age": "flexible_used",
        "greeble_style": "attachment_functional",
        "negative_constraints": ("box_stack", "random_faceting", "unclear_attachment"),
    },
    "domain_kit_bundle": {
        "role": "procedural domain-specific production kit or asset-library bundle",
        "style_tags": ("domain_kit", "library", "world_building"),
        "silhouette": "readable_root_identity_parts_variants_ports_and_compatibility",
        "bevel_language": "kit_consistent_structural_edges",
        "shape_language": "root_identity_canonical_parts_snap_ports_variant_slots_scale_markers_style_zones_labels_and_compatibility_cues",
        "detail_density": "hero",
        "wear": "kit_usage_and_repeat_edge_wear",
        "material_age": "configurable",
        "greeble_style": "library_functional",
        "negative_constraints": ("toy_like", "random_faceting", "orphan_variant"),
    },
    "world_system_assembly": {
        "role": "procedural world-system, navigation, faction, or progression assembly",
        "style_tags": ("world_system", "layout", "progression"),
        "silhouette": "readable_regions_routes_rules_anchors_and_transitions",
        "bevel_language": "system_map_readability_edges",
        "shape_language": "world_footprint_layers_routes_faction_zones_objective_chains_resources_landmarks_gates_and_debug_cues",
        "detail_density": "hero",
        "wear": "route_and_system_usage_wear",
        "material_age": "active_system",
        "greeble_style": "system_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "unclear_system"),
    },
    "simulation_environment_system": {
        "role": "procedural simulation, field, solver, force, or environment-system module",
        "style_tags": ("simulation", "environment", "field"),
        "silhouette": "readable_domain_bounds_emitters_vectors_constraints_and_outputs",
        "bevel_language": "field_boundary_and_probe_edges",
        "shape_language": "domain_bounds_emitters_force_vectors_gradient_zones_constraints_probes_collision_boundaries_time_states_and_response_outputs",
        "detail_density": "hero",
        "wear": "field_response_and_interaction_masks",
        "material_age": "active_dynamic",
        "greeble_style": "simulation_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "invisible_system"),
    },
    "authored_multi_asset_bundle": {
        "role": "procedural authored multi-asset bundle, scene bundle, or set-piece collection",
        "style_tags": ("bundle", "multi_asset", "authored"),
        "silhouette": "readable_bundle_root_members_dependencies_variants_and_layout",
        "bevel_language": "bundle_consistent_structural_edges",
        "shape_language": "root_manifest_member_slots_dependencies_layout_anchors_variants_shared_materials_labels_lod_markers_and_export_cues",
        "detail_density": "hero",
        "wear": "bundle_usage_and_layout_wear",
        "material_age": "configurable",
        "greeble_style": "bundle_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "orphan_member"),
    },
    "live_procedural_runtime_bundle": {
        "role": "procedural live-runtime bundle, engine hook, or runtime-override module",
        "style_tags": ("runtime", "live_procedural", "engine"),
        "silhouette": "readable_runtime_core_inputs_overrides_outputs_and_versioning",
        "bevel_language": "runtime_port_and_override_edges",
        "shape_language": "runtime_core_input_ports_override_controls_output_slots_version_badges_dependency_links_validation_markers_and_hot_reload_cues",
        "detail_density": "hero",
        "wear": "runtime_iteration_and_override_wear",
        "material_age": "active_system",
        "greeble_style": "runtime_functional_only",
        "negative_constraints": ("toy_like", "random_faceting", "unclear_runtime_flow"),
    },
    "cross_domain_composition_pack": {
        "role": "procedural cross-domain composition pack spanning world, asset, gameplay, style, and runtime concerns",
        "style_tags": ("cross_domain", "composition", "world_building"),
        "silhouette": "readable_domain_pillars_links_boundaries_and_outputs",
        "bevel_language": "composition_boundary_and_link_edges",
        "shape_language": "domain_pillars_bridge_links_rules_adapters_conflict_guards_preview_outputs_handoff_markers_and_integration_masks",
        "detail_density": "hero",
        "wear": "integration_and_handoff_wear",
        "material_age": "active_system",
        "greeble_style": "composition_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "unclear_domain_boundary"),
    },
    "style_stack_visual_band": {
        "role": "procedural style-stack, visual-band, or construction-grammar target",
        "style_tags": ("style_stack", "visual_band", "art_direction"),
        "silhouette": "readable_style_axes_palette_surface_outline_lighting_and_detail_layers",
        "bevel_language": "style_axis_and_sample_edges",
        "shape_language": "style_axes_palette_swatches_surface_modes_outline_lighting_detail_layers_animation_rate_compatibility_and_refusal_markers",
        "detail_density": "hero",
        "wear": "style_sample_edge_and_iteration_wear",
        "material_age": "configurable",
        "greeble_style": "art_direction_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "incompatible_style_mix"),
    },
    "typed_data_kernel_bundle": {
        "role": "typed-data kernel bundle carrying mesh, points, volume, heightfield, spline, sdf, image, and rig slots",
        "style_tags": ("typed_data", "kernel", "bundle"),
        "silhouette": "readable_typed_bus_slots_contracts_transforms_and_artifact_flow",
        "bevel_language": "typed_slot_and_contract_edges",
        "shape_language": "typed_bundle_bus_mesh_points_volume_heightfield_spline_sdf_image_rig_slots_contract_badges_transform_arrows_and_cache_state",
        "detail_density": "hero",
        "wear": "data_flow_and_contract_iteration_wear",
        "material_age": "active_system",
        "greeble_style": "kernel_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "ambiguous_slot_type"),
    },
    "attribute_surface_graph_program": {
        "role": "attribute-language and procedural surface-graph program spanning designer graph, photo-fit, and layer-stack modes",
        "style_tags": ("attribute_language", "surface_graph", "material_authoring"),
        "silhouette": "readable_attribute_streams_surface_nodes_masks_modes_and_material_outputs",
        "bevel_language": "node_graph_and_mask_channel_edges",
        "shape_language": "attribute_streams_bindings_surface_nodes_mask_layers_designer_photo_fit_layer_stack_materialx_outputs_and_refusal_guards",
        "detail_density": "hero",
        "wear": "surface_iteration_and_mask_authoring_wear",
        "material_age": "configurable",
        "greeble_style": "surface_graph_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "unbound_attribute"),
    },
    "vegetation_library_system": {
        "role": "procedural vegetation library system with species catalog, branching grammar, LODs, wind, seasons, and biome distribution",
        "style_tags": ("vegetation_library", "domain_library", "world_building"),
        "silhouette": "readable_species_catalog_branching_canopy_roots_lods_and_distribution_masks",
        "bevel_language": "organic_library_anchor_and_catalog_edges",
        "shape_language": "species_cards_branch_curves_leaf_clusters_root_anchors_lod_billboards_wind_arcs_season_slots_growth_ports_and_biome_masks",
        "detail_density": "hero",
        "wear": "growth_authoring_and_biome_usage_wear",
        "material_age": "organic_configurable",
        "greeble_style": "vegetation_system_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "single_static_plant"),
    },
    "terrain_heightfield_system": {
        "role": "procedural terrain heightfield and erosion system with masks, drainage, biome zones, and mesh exports",
        "style_tags": ("terrain", "heightfield", "erosion"),
        "silhouette": "readable_heightfield_domain_elevation_layers_flow_masks_and_boundaries",
        "bevel_language": "terrain_boundary_and_elevation_step_edges",
        "shape_language": "heightfield_domain_elevation_layers_erosion_flows_slope_masks_biome_zones_drainage_channels_export_ports_probe_grid_and_tile_edges",
        "detail_density": "hero",
        "wear": "erosion_iteration_and_flow_wear",
        "material_age": "geologic_dynamic",
        "greeble_style": "terrain_system_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "flat_untyped_plane"),
    },
    "wfc_tile_solver_system": {
        "role": "procedural WFC modular tile solver with tilesets, adjacency rules, sockets, constraints, and solved layouts",
        "style_tags": ("wfc", "tile_solver", "modular_assembly"),
        "silhouette": "readable_tileset_socket_adjacency_constraint_grid_and_solution_flow",
        "bevel_language": "tile_socket_and_constraint_edges",
        "shape_language": "tileset_catalog_socket_edges_adjacency_matrix_entropy_grid_seed_ports_constraint_guards_solution_paths_failure_marks_and_tileability_masks",
        "detail_density": "hero",
        "wear": "solver_iteration_and_tile_usage_wear",
        "material_age": "active_system",
        "greeble_style": "solver_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "unconstrained_tile_mix"),
    },
    "cga_building_grammar_system": {
        "role": "procedural CGA-style building grammar with rule stacks, split/repeat/extrude operators, facade bands, and terminal parts",
        "style_tags": ("cga", "shape_grammar", "building_system"),
        "silhouette": "readable_rule_stack_massing_splits_facades_terminals_and_derivation_flow",
        "bevel_language": "grammar_rule_and_facade_boundary_edges",
        "shape_language": "root_mass_rule_stack_split_repeat_extrude_ops_facade_bands_terminal_modules_derivation_paths_variation_ports_guard_rules_and_output_masks",
        "detail_density": "hero",
        "wear": "grammar_iteration_and_rule_authoring_wear",
        "material_age": "configurable",
        "greeble_style": "grammar_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "ambiguous_derivation"),
    },
    "volume_effects_data_system": {
        "role": "procedural volume/effects data system for sparse volumes, density fields, temperature, velocity, and meshing outputs",
        "style_tags": ("volume", "effects_data", "simulation"),
        "silhouette": "readable_volume_domain_channels_emitters_fields_and_meshing_outputs",
        "bevel_language": "volume_domain_and_channel_boundary_edges",
        "shape_language": "volume_domain_density_temperature_velocity_channels_emitters_force_vectors_slices_thresholds_meshing_ports_cache_tiles_and_field_masks",
        "detail_density": "hero",
        "wear": "solve_iteration_and_field_authoring_wear",
        "material_age": "dynamic_field",
        "greeble_style": "volume_system_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "invisible_field"),
    },
    "instance_pattern_scatter_system": {
        "role": "procedural instance-pattern scatter system for surface-projected greebles, vegetation tufts, rivets, props, and repeated kits",
        "style_tags": ("instance_pattern", "scatter", "copy_to_points"),
        "silhouette": "readable_source_part_point_cloud_surface_projection_density_and_outputs",
        "bevel_language": "scatter_source_and_projection_edge_language",
        "shape_language": "source_part_point_cloud_surface_samples_density_masks_poisson_spacing_orient_scale_jitter_collision_guards_output_instances_and_usage_masks",
        "detail_density": "hero",
        "wear": "scatter_iteration_and_surface_projection_wear",
        "material_age": "configurable",
        "greeble_style": "scatter_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "unprojected_random_noise"),
    },
    "f_rep_sdf_composition_system": {
        "role": "procedural F-Rep/SDF composition system for implicit solids, smooth booleans, blend fields, and extraction outputs",
        "style_tags": ("f_rep", "sdf", "implicit_surface"),
        "silhouette": "readable_implicit_primitives_boolean_tree_blend_fields_and_extraction_ports",
        "bevel_language": "implicit_blend_and_field_boundary_edges",
        "shape_language": "sdf_primitives_expression_tree_smooth_union_subtract_intersect_blend_radius_fields_samples_bounds_extraction_ports_and_failure_guards",
        "detail_density": "hero",
        "wear": "implicit_authoring_and_extraction_iteration_wear",
        "material_age": "dynamic_field",
        "greeble_style": "implicit_system_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "unbounded_implicit_field"),
    },
    "subdivision_finishing_system": {
        "role": "procedural subdivision and finishing system for OpenSubDiv-style cages, creases, remesh passes, and smoothed outputs",
        "style_tags": ("subdivision", "finishing", "mesh_quality"),
        "silhouette": "readable_control_cage_crease_tags_subdivision_levels_remesh_and_output_surfaces",
        "bevel_language": "crease_tag_and_cage_boundary_edges",
        "shape_language": "control_cage_catmull_clark_loop_levels_crease_tags_boundary_rules_remesh_targets_smoothing_passes_quality_probes_and_output_markers",
        "detail_density": "hero",
        "wear": "finishing_iteration_and_surface_review_wear",
        "material_age": "production_ready",
        "greeble_style": "finishing_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "uncaged_smoothing"),
    },
    "humanoid_anatomy_preset_system": {
        "role": "procedural humanoid anatomy preset system with canonical topology, proportions, landmark loops, morph database, and rig anchors",
        "style_tags": ("humanoid_anatomy", "character_system", "morph_targets"),
        "silhouette": "readable_body_proportions_topology_regions_landmarks_morphs_and_rig_anchors",
        "bevel_language": "anatomy_region_and_landmark_boundary_edges",
        "shape_language": "canonical_topology_body_proportions_head_torso_limb_regions_landmark_loops_joint_anchors_morph_targets_skin_weight_zones_style_variants_and_validation_guards",
        "detail_density": "hero",
        "wear": "anatomy_iteration_and_morph_authoring_wear",
        "material_age": "character_ready",
        "greeble_style": "anatomy_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "uncanonical_topology"),
    },
    "face_sdf_cel_shading_system": {
        "role": "procedural face-SDF and cel-shading system with ramp LUTs, inverted hull outlines, face-shadow fields, and style guards",
        "style_tags": ("face_sdf", "cel_shading", "anime"),
        "silhouette": "readable_face_regions_shadow_sdf_ramp_lut_outline_and_style_bridge",
        "bevel_language": "face_region_and_ramp_boundary_edges",
        "shape_language": "face_sdf_regions_shadow_bands_ramp_lut_cells_outline_hull_sobel_channels_id_masks_light_direction_controls_style_bridge_guards_and_preview_outputs",
        "detail_density": "hero",
        "wear": "style_iteration_and_face_rig_review_wear",
        "material_age": "stylized_active",
        "greeble_style": "cel_shading_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "pbr_cel_mismatch"),
    },
    "rig_component_library_system": {
        "role": "procedural rig-component library system for spine, limb, digit, mech-joint, wing-chain, and tentacle-chain rig modules",
        "style_tags": ("rig_component", "typed_rig", "kinefx"),
        "silhouette": "readable_component_catalog_spine_limb_digit_mech_wing_tentacle_connectors_and_controls",
        "bevel_language": "component_socket_and_control_boundary_edges",
        "shape_language": "component_catalog_spine_limb_digit_mech_joint_wing_chain_tentacle_chain_connector_sockets_ik_fk_templates_typed_rig_outputs_and_cycle_guards",
        "detail_density": "hero",
        "wear": "component_iteration_and_binding_review_wear",
        "material_age": "rig_ready",
        "greeble_style": "rig_component_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "cyclic_component_graph"),
    },
    "morph_target_database_system": {
        "role": "procedural morph-target database system with expressions, visemes, body deltas, corrective shapes, region masks, and compatibility guards",
        "style_tags": ("morph_targets", "blendshape", "character_system"),
        "silhouette": "readable_morph_catalog_expression_viseme_body_delta_corrective_and_region_mask_slots",
        "bevel_language": "morph_slot_and_delta_channel_boundary_edges",
        "shape_language": "morph_catalog_expression_sets_viseme_sets_body_shape_deltas_corrective_shapes_region_masks_delta_vectors_symmetry_rules_rig_anatomy_compatibility_and_revision_masks",
        "detail_density": "hero",
        "wear": "morph_authoring_and_expression_review_wear",
        "material_age": "character_ready",
        "greeble_style": "morph_database_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "unbound_delta_shapes"),
    },
    "animation_library_binding_system": {
        "role": "procedural animation-library binding system with clip catalogs, poses, locomotion states, blend trees, event tracks, and rig binding slots",
        "style_tags": ("animation_library", "motion_clips", "rig_binding"),
        "silhouette": "readable_clip_catalog_pose_library_state_graph_events_root_motion_and_binding_slots",
        "bevel_language": "clip_slot_state_graph_and_event_track_boundary_edges",
        "shape_language": "clip_catalog_pose_library_locomotion_states_blend_trees_transition_graphs_event_tracks_root_motion_channels_rig_binding_slots_additive_layers_and_timing_outputs",
        "detail_density": "hero",
        "wear": "animation_binding_and_timing_review_wear",
        "material_age": "animation_ready",
        "greeble_style": "animation_binding_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "unbound_animation_clips"),
    },
    "retargeting_pack_system": {
        "role": "procedural retargeting pack system with source/target skeletons, bone maps, rest-pose alignment, scale compensation, IK remaps, and validation guards",
        "style_tags": ("retargeting", "skeleton_mapping", "animation_binding"),
        "silhouette": "readable_source_target_skeletons_bone_maps_alignment_axes_scale_rules_and_validation_guards",
        "bevel_language": "retarget_map_alignment_and_constraint_boundary_edges",
        "shape_language": "source_target_skeletons_bone_mapping_rest_pose_alignment_scale_compensation_coordinate_spaces_ik_pole_remaps_root_motion_transfer_constraints_compatibility_guards_and_revision_masks",
        "detail_density": "hero",
        "wear": "retargeting_iteration_and_motion_review_wear",
        "material_age": "animation_ready",
        "greeble_style": "retargeting_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "unmapped_bones"),
    },
    "character_equipment_binding_system": {
        "role": "procedural character equipment binding system with armor slots, weapon sockets, loadouts, clearance zones, and rig/anatomy compatibility guards",
        "style_tags": ("equipment_binding", "character_system", "loadout"),
        "silhouette": "readable_body_slot_map_weapon_sockets_armor_regions_clearance_zones_and_loadout_ports",
        "bevel_language": "equipment_socket_slot_and_clearance_boundary_edges",
        "shape_language": "body_slot_map_weapon_sockets_armor_slots_holsters_outfit_layers_attachment_offsets_clearance_volumes_loadout_variants_collision_guards_and_compatibility_badges",
        "detail_density": "hero",
        "wear": "equipment_fit_and_loadout_iteration_wear",
        "material_age": "character_ready",
        "greeble_style": "equipment_binding_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "floating_equipment"),
    },
    "gameplay_animation_controller_system": {
        "role": "procedural gameplay animation controller system with input actions, controller states, locomotion/combat graphs, parameters, transitions, and guard conditions",
        "style_tags": ("animation_controller", "gameplay_logic", "state_machine"),
        "silhouette": "readable_input_action_map_controller_states_transition_rules_parameters_and_output_bindings",
        "bevel_language": "controller_state_transition_and_parameter_boundary_edges",
        "shape_language": "input_action_map_controller_states_locomotion_modes_combat_ability_states_transition_rules_blend_parameters_motion_matching_slots_event_outputs_network_tags_and_guard_conditions",
        "detail_density": "hero",
        "wear": "controller_iteration_and_tuning_review_wear",
        "material_age": "gameplay_ready",
        "greeble_style": "controller_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "unreachable_animation_state"),
    },
    "procedural_facial_rig_pack_system": {
        "role": "procedural facial rig pack system with jaw, eyes, brows, lids, lips, expression drivers, viseme links, and face-SDF compatibility",
        "style_tags": ("facial_rig", "expression_controls", "character_system"),
        "silhouette": "readable_facial_control_board_jaw_eye_brow_lid_lip_viseme_and_expression_driver_layout",
        "bevel_language": "facial_control_socket_and_expression_region_boundary_edges",
        "shape_language": "facial_control_board_jaw_controls_eye_aim_controls_brow_lid_controls_lip_corner_controls_viseme_links_expression_driver_curves_morph_bindings_face_sdf_masks_and_range_guards",
        "detail_density": "hero",
        "wear": "facial_rig_iteration_and_expression_review_wear",
        "material_age": "character_ready",
        "greeble_style": "facial_rig_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "unbound_facial_controls"),
    },
    "hair_program_system": {
        "role": "procedural hair program system with strand grammar, root density, length distribution, wave controls, cards/strands outputs, and groom regions",
        "style_tags": ("hair_program", "strand_grammar", "grooming"),
        "silhouette": "readable_scalp_regions_strand_flow_root_density_length_distribution_cards_and_color_gradient",
        "bevel_language": "groom_region_card_and_strand_boundary_edges",
        "shape_language": "scalp_groom_regions_root_density_masks_length_distribution_wave_amplitude_frequency_clump_guides_parting_lines_hair_card_outputs_strand_outputs_color_gradient_and_collision_guards",
        "detail_density": "hero",
        "wear": "groom_iteration_and_style_review_wear",
        "material_age": "character_ready",
        "greeble_style": "hair_program_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "bald_unbound_roots"),
    },
    "cloth_fabric_simulation_program_system": {
        "role": "procedural cloth/fabric simulation program system with mass, stiffness, damping, pin constraints, collision volumes, and deterministic settling outputs",
        "style_tags": ("cloth_program", "fabric_simulation", "xpbd"),
        "silhouette": "readable_fabric_domain_panels_pins_constraint_params_collision_bodies_settled_folds_and_output_surfaces",
        "bevel_language": "fabric_panel_pin_constraint_and_collision_boundary_edges",
        "shape_language": "fabric_domain_panels_mass_stiffness_damping_params_pin_constraints_collision_bodies_gravity_wind_fields_settling_passes_wrinkle_outputs_material_zones_and_solver_guards",
        "detail_density": "hero",
        "wear": "cloth_simulation_and_fit_iteration_wear",
        "material_age": "simulation_ready",
        "greeble_style": "cloth_program_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "unpinned_exploding_cloth"),
    },
    "fluid_forward_volume_program_system": {
        "role": "procedural fluid-forward volume program system with sparse volume domains, density/temperature/velocity channels, advection fields, isosurfaces, and mesh outputs",
        "style_tags": ("fluid_forward", "volume_program", "vdb"),
        "silhouette": "readable_fluid_volume_domain_channels_emitters_advection_surface_thresholds_and_outputs",
        "bevel_language": "volume_domain_channel_and_boundary_edges",
        "shape_language": "fluid_volume_domain_density_temperature_velocity_channels_emitters_advection_forces_surface_thresholds_particle_mesh_outputs_cache_tiles_collision_guards_and_iteration_masks",
        "detail_density": "hero",
        "wear": "fluid_authoring_and_solve_iteration_wear",
        "material_age": "dynamic_field",
        "greeble_style": "fluid_program_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "unbounded_fluid_volume"),
    },
    "construction_grammar_kit_system": {
        "role": "procedural construction grammar kit system with module catalogs, connector rules, snap grids, assembly recipes, and buildable output constraints",
        "style_tags": ("construction_grammar", "kit_system", "assembly_rules"),
        "silhouette": "readable_module_catalog_connector_rules_snap_grid_allowed_compositions_and_assembly_outputs",
        "bevel_language": "module_socket_connector_and_rule_boundary_edges",
        "shape_language": "module_catalog_snap_grid_connector_rule_graph_allowed_adjacencies_repeat_split_rules_kitbash_variants_structural_guards_buildable_outputs_and_grammar_iteration_marks",
        "detail_density": "hero",
        "wear": "construction_grammar_iteration_and_kit_review_wear",
        "material_age": "authoring_ready",
        "greeble_style": "grammar_kit_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "unbuildable_rule_cycle"),
    },
    "creature_appendage_program_system": {
        "role": "procedural creature appendage program system with wings, tails, tentacles, horns, claws, fins, sockets, articulation controls, and symmetry rules",
        "style_tags": ("creature_appendage", "organic_program", "anatomy_variant"),
        "silhouette": "readable_appendage_sockets_joint_chains_surface_features_symmetry_and_attachment_clearance",
        "bevel_language": "appendage_socket_joint_segment_and_tip_boundary_edges",
        "shape_language": "appendage_socket_maps_joint_chains_segment_profiles_wing_tail_tentacle_horn_claw_fin_variants_muscle_surface_features_symmetry_rules_articulation_ranges_attachment_guards_and_variant_outputs",
        "detail_density": "hero",
        "wear": "appendage_design_and_fit_iteration_wear",
        "material_age": "organic_ready",
        "greeble_style": "appendage_program_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "floating_appendage"),
    },
    "body_part_procedural_library_system": {
        "role": "procedural body-part library system with anatomy regions, body-part catalogs, organ sockets, muscle groups, proportions, symmetry, and compatible outputs",
        "style_tags": ("body_part_library", "anatomy_program", "organic_system"),
        "silhouette": "readable_body_part_catalog_anatomy_regions_sockets_muscle_groups_and_output_variants",
        "bevel_language": "anatomy_region_socket_muscle_and_landmark_boundary_edges",
        "shape_language": "body_part_catalog_head_torso_hand_foot_eye_mouth_regions_organ_socket_maps_muscle_groups_landmark_loops_proportion_ranges_symmetry_rules_surface_zones_compatibility_guards_and_variant_outputs",
        "detail_density": "hero",
        "wear": "body_part_design_and_fit_iteration_wear",
        "material_age": "organic_ready",
        "greeble_style": "body_part_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "incompatible_body_part"),
    },
    "material_primitive_library_system": {
        "role": "procedural material primitive and physical substance library system with typed PBR primitives, substance taxonomy, channel ranges, and portable surface outputs",
        "style_tags": ("material_primitive", "physical_substance", "pbr"),
        "silhouette": "readable_material_primitive_catalog_substance_channels_validation_ranges_and_surface_outputs",
        "bevel_language": "material_swatch_channel_and_substance_boundary_edges",
        "shape_language": "material_primitive_catalog_physical_substance_taxonomy_metal_rough_dielectric_emissive_translucent_presets_basecolor_normal_orm_height_channels_range_guards_materialx_output_ports_and_substance_iteration_marks",
        "detail_density": "hero",
        "wear": "material_primitive_authoring_and_chart_review_wear",
        "material_age": "surface_ready",
        "greeble_style": "material_primitive_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "invalid_pbr_range"),
    },
    "engine_facing_runtime_bundle_system": {
        "role": "procedural engine-facing runtime bundle system with Unity, Unreal, USD Hydra, DCC adapters, host overrides, and live procedural outputs",
        "style_tags": ("engine_runtime", "host_adapter", "live_procedural"),
        "silhouette": "readable_host_targets_plugin_adapters_bundle_manifest_parameter_overrides_and_engine_outputs",
        "bevel_language": "host_adapter_port_bundle_and_abi_boundary_edges",
        "shape_language": "unity_unreal_usd_hydra_dcc_targets_plugin_adapters_lathe_bundle_manifest_parameter_override_schema_live_evaluation_hooks_asset_output_sinks_runtime_contracts_abi_guards_debug_ports_and_host_iteration_marks",
        "detail_density": "hero",
        "wear": "engine_runtime_authoring_and_host_iteration_wear",
        "material_age": "runtime_ready",
        "greeble_style": "engine_runtime_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "fake_engine_plugin_success"),
    },
    "procedural_prefab_binding_system": {
        "role": "procedural prefab binding system with prefab roots, source asset slots, parameter maps, variants, LODs, material bindings, collision bindings, and export targets",
        "style_tags": ("prefab_binding", "engine_asset", "procedural_bundle"),
        "silhouette": "readable_prefab_root_source_slots_parameter_maps_variants_lods_and_export_targets",
        "bevel_language": "prefab_slot_binding_variant_and_export_boundary_edges",
        "shape_language": "prefab_root_bindings_source_asset_slots_parameter_binding_tables_variant_override_maps_lod_streaming_bindings_material_surface_bindings_collision_physics_bindings_engine_export_targets_dependency_guards_and_prefab_iteration_marks",
        "detail_density": "hero",
        "wear": "prefab_binding_authoring_and_export_iteration_wear",
        "material_age": "engine_ready",
        "greeble_style": "prefab_binding_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "unbound_prefab_output"),
    },
    "scene_system_authoring_bundle": {
        "role": "procedural scene-system authoring bundle with scene hierarchy, placement layers, spawn rules, lighting/camera layers, navmesh regions, and validation guards",
        "style_tags": ("scene_authoring", "world_layout", "engine_scene"),
        "silhouette": "readable_scene_root_hierarchy_placement_spawn_lighting_navmesh_and_validation_layers",
        "bevel_language": "scene_layer_anchor_spawn_and_navigation_boundary_edges",
        "shape_language": "scene_root_hierarchy_transform_anchors_placement_layers_spawn_layers_lighting_layers_camera_bookmarks_navmesh_regions_occlusion_bounds_streaming_tags_environment_volumes_validation_guards_and_scene_iteration_marks",
        "detail_density": "hero",
        "wear": "scene_authoring_and_layout_iteration_wear",
        "material_age": "scene_ready",
        "greeble_style": "scene_authoring_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "unanchored_scene_node"),
    },
    "behavior_logic_graph_bundle": {
        "role": "procedural behavior-logic graph bundle with state nodes, events, conditions, actions, blackboard bindings, signals, timers, and debug guards",
        "style_tags": ("behavior_graph", "logic_graph", "scriptless_gameplay"),
        "silhouette": "readable_behavior_state_nodes_event_edges_conditions_actions_blackboard_and_debug_ports",
        "bevel_language": "logic_node_event_condition_and_action_boundary_edges",
        "shape_language": "behavior_state_nodes_event_edges_condition_rules_action_outputs_blackboard_bindings_signal_ports_timer_tracks_priority_selectors_failure_guards_debug_trace_ports_and_behavior_iteration_marks",
        "detail_density": "hero",
        "wear": "behavior_logic_authoring_and_debug_iteration_wear",
        "material_age": "gameplay_ready",
        "greeble_style": "behavior_graph_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "unreachable_logic_state"),
    },
    "world_streaming_runtime_partition_bundle": {
        "role": "procedural world-streaming and runtime-partition bundle with sector grids, streaming volumes, load groups, LOD rings, occlusion regions, and chunk dependencies",
        "style_tags": ("world_streaming", "runtime_partition", "open_world"),
        "silhouette": "readable_sector_grid_streaming_volumes_load_groups_lod_rings_and_partition_guards",
        "bevel_language": "sector_cell_volume_lod_and_dependency_boundary_edges",
        "shape_language": "world_partition_root_sector_grid_streaming_cells_streaming_volumes_load_groups_runtime_chunk_dependencies_lod_distance_rings_occlusion_regions_memory_budget_markers_asset_residency_ports_partition_validation_guards_and_streaming_iteration_marks",
        "detail_density": "hero",
        "wear": "world_streaming_authoring_and_partition_iteration_wear",
        "material_age": "runtime_ready",
        "greeble_style": "streaming_partition_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "orphan_streaming_cell"),
    },
    "save_state_persistence_bundle": {
        "role": "procedural save-state and persistence bundle with checkpoint slots, actor state, inventory/quest state, delta logs, schema versions, and restore guards",
        "style_tags": ("save_state", "persistence", "runtime_state"),
        "silhouette": "readable_checkpoint_slots_actor_state_tables_delta_logs_schema_badges_and_restore_guards",
        "bevel_language": "checkpoint_slot_state_table_delta_and_schema_boundary_edges",
        "shape_language": "save_root_checkpoint_slots_persistent_actor_state_inventory_state_quest_state_world_state_deltas_snapshot_records_schema_version_badges_restore_paths_conflict_resolution_guards_corruption_validation_ports_and_persistence_iteration_marks",
        "detail_density": "hero",
        "wear": "save_state_authoring_and_restore_iteration_wear",
        "material_age": "runtime_ready",
        "greeble_style": "persistence_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "unversioned_save_state"),
    },
    "quest_dialogue_authoring_bundle": {
        "role": "procedural quest and dialogue authoring bundle with quest graphs, dialogue branches, objectives, conditions, rewards, NPC bindings, and localization hooks",
        "style_tags": ("quest_authoring", "dialogue_graph", "narrative_logic"),
        "silhouette": "readable_quest_nodes_dialogue_branches_objectives_conditions_rewards_and_npc_bindings",
        "bevel_language": "quest_node_dialogue_branch_condition_and_reward_boundary_edges",
        "shape_language": "quest_root_objective_graph_dialogue_branch_tree_choice_maps_condition_gates_reward_tables_npc_binding_ports_localization_keys_conversation_state_flags_failure_paths_validation_guards_and_narrative_iteration_marks",
        "detail_density": "hero",
        "wear": "quest_dialogue_authoring_and_branch_iteration_wear",
        "material_age": "gameplay_ready",
        "greeble_style": "quest_dialogue_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "unreachable_dialogue_branch"),
    },
    "camera_cinematic_direction_bundle": {
        "role": "procedural camera and cinematic direction bundle with camera rigs, shot graphs, lens bindings, timelines, look-at targets, blends, triggers, and framing guards",
        "style_tags": ("camera_rig", "cinematic_direction", "shot_graph"),
        "silhouette": "readable_camera_rigs_shot_paths_lens_tracks_timeline_marks_and_look_at_targets",
        "bevel_language": "camera_rig_path_lens_timeline_and_framing_boundary_edges",
        "shape_language": "camera_rig_graph_shot_sequence_camera_paths_lens_rig_bindings_timeline_beats_look_at_target_tracks_blend_stack_trigger_map_framing_safe_regions_cutscene_output_ports_validation_guards_and_cinematic_iteration_marks",
        "detail_density": "hero",
        "wear": "camera_cinematic_authoring_and_shot_iteration_wear",
        "material_age": "cinematic_ready",
        "greeble_style": "cinematic_direction_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "unbound_camera_target"),
    },
    "procedural_audio_cue_bundle": {
        "role": "procedural audio cue bundle with sound events, SFX maps, music stems, ambience layers, attenuation zones, reverb sends, VO triggers, and runtime buses",
        "style_tags": ("procedural_audio", "sound_cue_graph", "runtime_audio"),
        "silhouette": "readable_audio_event_nodes_sfx_music_layers_spatial_zones_mixer_sends_and_bus_ports",
        "bevel_language": "cue_node_timing_attenuation_mixer_bus_and_trigger_boundary_edges",
        "shape_language": "audio_cue_root_sound_event_nodes_sfx_maps_music_stem_bindings_ambience_layers_timing_triggers_attenuation_zones_reverb_send_paths_vo_trigger_ports_runtime_audio_bus_outputs_loudness_validation_guards_and_audio_iteration_marks",
        "detail_density": "hero",
        "wear": "audio_authoring_mix_and_runtime_iteration_wear",
        "material_age": "runtime_ready",
        "greeble_style": "audio_graph_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "unrouted_audio_event"),
    },
    "localization_text_table_bundle": {
        "role": "procedural localization and text-table bundle with string keys, locale columns, translation values, pluralization rules, subtitle timings, VO bindings, fallback chains, and glyph coverage",
        "style_tags": ("localization", "text_table", "content_portability"),
        "silhouette": "readable_string_table_keys_locale_columns_subtitle_rows_vo_bindings_and_fallback_chains",
        "bevel_language": "table_key_locale_column_subtitle_binding_and_fallback_boundary_edges",
        "shape_language": "localization_table_root_string_key_rows_locale_columns_translation_cells_pluralization_rule_blocks_subtitle_timing_rows_voiceover_text_bindings_locale_fallback_chains_font_glyph_coverage_tiles_validation_guards_and_localization_iteration_marks",
        "detail_density": "hero",
        "wear": "localization_authoring_translation_and_review_iteration_wear",
        "material_age": "content_ready",
        "greeble_style": "localization_table_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "missing_locale_fallback"),
    },
    "accessibility_ux_affordance_bundle": {
        "role": "procedural accessibility and UX affordance bundle with input remaps, readable state cues, contrast-safe regions, captions, haptics, focus paths, and option panels",
        "style_tags": ("accessibility", "ux_affordance", "inclusive_design"),
        "silhouette": "readable_input_maps_state_cues_contrast_regions_captions_haptics_focus_paths_and_option_ports",
        "bevel_language": "input_cue_contrast_caption_focus_option_and_guard_boundary_edges",
        "shape_language": "accessibility_affordance_root_input_remap_maps_readability_state_cues_contrast_safe_regions_subtitle_caption_panels_audio_visual_haptic_cue_ports_focus_navigation_paths_option_panel_ports_usability_validation_guards_and_accessibility_iteration_marks",
        "detail_density": "hero",
        "wear": "accessibility_review_usability_and_iteration_wear",
        "material_age": "user_ready",
        "greeble_style": "accessibility_affordance_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "unreadable_affordance"),
    },
    "economy_simulation_tuning_bundle": {
        "role": "procedural economy and simulation tuning bundle with resource flow graphs, currency sinks/sources, loot tables, price curves, progression balance, spawn rates, telemetry, and guard rails",
        "style_tags": ("economy_tuning", "simulation_balance", "systems_design"),
        "silhouette": "readable_resource_flows_currency_loops_loot_tables_price_curves_balance_tracks_and_tuning_ports",
        "bevel_language": "resource_node_currency_loop_reward_table_curve_and_validation_boundary_edges",
        "shape_language": "economy_simulation_root_resource_flow_nodes_currency_sink_source_pairs_loot_reward_tables_price_curve_maps_progression_balance_tracks_spawn_rate_modulators_telemetry_tuning_inputs_market_rule_ports_simulation_validation_guards_and_economy_iteration_marks",
        "detail_density": "hero",
        "wear": "economy_balance_tuning_and_simulation_iteration_wear",
        "material_age": "systems_ready",
        "greeble_style": "economy_tuning_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "unbounded_economy_loop"),
    },
    "multiplayer_session_replication_bundle": {
        "role": "procedural multiplayer session and replication bundle with network sessions, authority ownership, replicated state, RPC events, sync ticks, prediction, rollback buffers, and matchmaking rules",
        "style_tags": ("multiplayer", "replication", "network_session"),
        "silhouette": "readable_session_roots_authority_maps_replication_state_rpc_events_sync_ticks_and_rollback_buffers",
        "bevel_language": "session_authority_replication_rpc_sync_prediction_and_rollback_boundary_edges",
        "shape_language": "multiplayer_session_root_network_session_maps_authority_ownership_tracks_replicated_state_nodes_rpc_event_channels_sync_tick_timelines_prediction_reconciliation_paths_rollback_state_buffers_matchmaking_rule_panels_replication_validation_guards_and_multiplayer_iteration_marks",
        "detail_density": "hero",
        "wear": "multiplayer_sync_replication_and_session_iteration_wear",
        "material_age": "runtime_ready",
        "greeble_style": "replication_graph_readability_only",
        "negative_constraints": ("toy_like", "random_faceting", "desynced_replication_state"),
    },
    "generic": {
        "role": "hard-surface utility asset",
        "style_tags": ("utility", "industrial"),
        "silhouette": "balanced",
        "bevel_language": "crisp_industrial",
        "shape_language": "rectangular_panelled",
        "detail_density": "standard",
        "wear": "light_edge_wear",
        "material_age": "in_service",
        "greeble_style": "functional_only",
        "negative_constraints": ("toy_like", "random_faceting"),
    },
}


def _as_str(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _value_at_path(root: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = root
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _iter_text_fragments(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        fragments: list[str] = []
        for item in value:
            fragments.extend(_iter_text_fragments(item))
        return tuple(fragments)
    if isinstance(value, dict):
        fragments = []
        for item in value.values():
            fragments.extend(_iter_text_fragments(item))
        return tuple(fragments)
    return ()


def _match_token(text: str) -> str:
    """Return the family token that matches ``text`` (case-insensitive)."""
    if not text:
        return ""
    lowered = text.lower()
    for token, _family in _FAMILY_TOKENS:
        if token in lowered:
            return token
    return ""


def _match_authored_content(value: Any) -> str:
    for fragment in _iter_text_fragments(value):
        token = _match_token(fragment)
        if token:
            return token
    return ""


def _family_for_token(token: str) -> str:
    return next(family for tok, family in _FAMILY_TOKENS if tok == token)


def _canonical_family_alias(value: str) -> str:
    lowered = value.strip().lower()
    if lowered.endswith("_family"):
        lowered = lowered[: -len("_family")]
    return lowered


def _match_explicit_family(value: str) -> str:
    """Return the internal family selected by an explicit authoring ref."""
    if not value:
        return ""
    candidate = _canonical_family_alias(value)
    if candidate in _FAMILY_HINT_ALIASES:
        return _FAMILY_HINT_ALIASES[candidate]
    if candidate in _FAMILY_DEFAULTS and candidate != "generic":
        return candidate
    token = _match_token(candidate)
    return _family_for_token(token) if token else ""


def _infer_family(asset: dict[str, Any]) -> tuple[str, str, str]:
    """Pick the family for ``asset`` deterministically.

    Returns ``(family, signal, token)`` where ``signal`` is one of the
    explicit authoring signals, ``"name"``, ``"role"``, ``"kind"``, or
    ``"default"`` and ``token`` is the matched substring or explicit
    family reference (empty when
    ``signal == "default"``).
    """
    name = _as_str(asset.get("name"))
    intent = asset.get("intent") if isinstance(asset.get("intent"), dict) else {}
    role = _as_str(intent.get("role"))
    kind = _as_str(asset.get("kind"))
    assembly = asset.get("assembly") if isinstance(asset.get("assembly"), dict) else {}
    assembly_family = _as_str(assembly.get("family"))
    from_family = _as_str(asset.get("from"))

    for signal, source in (("assembly.family", assembly_family), ("from", from_family)):
        family = _match_explicit_family(source)
        if family:
            return family, signal, source

    for field in _INTENT_FAMILY_HINT_FIELDS:
        source = _as_str(intent.get(field))
        family = _match_explicit_family(source)
        if family:
            return family, f"intent.{field}", source

    for path in _AUTHORED_CONTENT_TOKEN_FIELDS:
        token = _match_authored_content(_value_at_path(asset, path))
        if token:
            return _family_for_token(token), ".".join(path), token

    for signal, source in (("name", name), ("role", role), ("kind", kind)):
        token = _match_token(source)
        if token:
            family = _family_for_token(token)
            return family, signal, token

    return "generic", "default", ""


def _build_default_brief(asset_name: str, family: str) -> DesignBrief:
    """Return the deterministic per-family default brief."""
    defaults = _FAMILY_DEFAULTS.get(family, _FAMILY_DEFAULTS["generic"])  # no-family-dispatch: per-family brief defaults table; migrate values to StyleKnowledge parameter_priors so a FamilyAlias can resolve them without the dict lookup
    return DesignBrief(
        asset_name=asset_name,
        family=family,
        role=defaults["role"],
        style_tags=tuple(defaults["style_tags"]),
        silhouette=defaults["silhouette"],
        bevel_language=defaults["bevel_language"],
        shape_language=defaults["shape_language"],
        detail_density=defaults["detail_density"],
        wear=defaults["wear"],
        material_age=defaults["material_age"],
        greeble_style=defaults["greeble_style"],
        negative_constraints=tuple(defaults["negative_constraints"]),
    )


def _reference_negative_constraints(runtime: dict[str, Any]) -> tuple[str, ...]:
    """Extract negative constraint strings from a Phase 11 reference board.

    Reads ``runtime["_reference_board"]`` (the raw dict the executor
    publishes from ``lathe.asset_quality.reference_board.load_reference_board``).
    Tolerates missing/None/non-dict slots by returning an empty tuple.
    Each entry is preserved in fixture order; the caller dedupes.
    """
    raw = runtime.get("_reference_board") if isinstance(runtime, dict) else None
    if not isinstance(raw, dict):
        return ()
    negatives = raw.get("negatives")
    if not isinstance(negatives, list):
        return ()
    out: list[str] = []
    for entry in negatives:
        if not isinstance(entry, dict):
            continue
        constraint = entry.get("constraint")
        if isinstance(constraint, str) and constraint:
            out.append(constraint)
    return tuple(out)


def _merge_negative_constraints(
    existing: tuple[str, ...], references: tuple[str, ...]
) -> tuple[str, ...]:
    """Append reference negatives to existing brief constraints.

    Existing brief values are preserved in their original order and
    placed first; reference values are appended in fixture order.
    Duplicates are dropped while preserving first-occurrence order so
    the result is deterministic regardless of how the reference list
    overlaps the brief defaults.
    """
    seen: set[str] = set()
    merged: list[str] = []
    for value in (*existing, *references):
        if not isinstance(value, str) or not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        merged.append(value)
    return tuple(merged)


_EXPERIMENTAL_ART_DIRECTION_WHITELIST: tuple[str, ...] = (
    "style_tags",
    "wear",
    "material_age",
    "detail_density",
)


def _experimental_art_direction(asset: dict[str, Any]) -> dict[str, Any]:
    """Return the user-provided ``experimental.art_direction`` overrides.

    Reads ``asset["experimental"]["art_direction"]`` when present and
    returns only fields in the MVP whitelist with valid types. Used to
    mutate the family-default brief and to surface
    ``user_provided_via_experimental`` evidence.
    """
    experimental = asset.get("experimental")
    if not isinstance(experimental, dict):
        return {}
    art_direction = experimental.get("art_direction")
    if not isinstance(art_direction, dict):
        return {}
    out: dict[str, Any] = {}
    for field in _EXPERIMENTAL_ART_DIRECTION_WHITELIST:
        if field not in art_direction:
            continue
        value = art_direction[field]
        if field == "style_tags":
            if isinstance(value, list) and all(isinstance(item, str) for item in value):
                out[field] = list(value)
        elif isinstance(value, str):
            out[field] = value
    return out


def _apply_art_direction_overrides(
    brief: DesignBrief, overrides: dict[str, Any]
) -> tuple[DesignBrief, list[str]]:
    """Return ``(updated_brief, applied_fields)`` for art-direction overrides.

    Replaces brief fields named in ``_EXPERIMENTAL_ART_DIRECTION_WHITELIST``
    with the user-provided values. Returns the original brief and an
    empty list when no whitelisted overrides apply.
    """
    if not overrides:
        return brief, []
    applied: list[str] = []
    style_tags = brief.style_tags
    wear = brief.wear
    material_age = brief.material_age
    detail_density = brief.detail_density
    if "style_tags" in overrides:
        style_tags = tuple(overrides["style_tags"])
        applied.append("style_tags")
    if "wear" in overrides:
        wear = overrides["wear"]
        applied.append("wear")
    if "material_age" in overrides:
        material_age = overrides["material_age"]
        applied.append("material_age")
    if "detail_density" in overrides:
        detail_density = overrides["detail_density"]
        applied.append("detail_density")
    if not applied:
        return brief, []
    return (
        DesignBrief(
            asset_name=brief.asset_name,
            family=brief.family,
            role=brief.role,
            style_tags=style_tags,
            silhouette=brief.silhouette,
            bevel_language=brief.bevel_language,
            shape_language=brief.shape_language,
            detail_density=detail_density,
            wear=wear,
            material_age=material_age,
            greeble_style=brief.greeble_style,
            negative_constraints=brief.negative_constraints,
        ),
        applied,
    )


def evaluate_design_brief(
    asset: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    """Build the additive design-brief payload for the validate stage.

    Args:
        asset: normalized asset dict. May omit ``intent``, ``name``, or
            ``kind``; the function tolerates partial/empty input. Phase
            13 reads ``asset["experimental"]["art_direction"]`` and
            applies whitelisted overrides on top of the family default
            brief.
        runtime: stage-bundle runtime dict. Phase 2 does not consume any
            stage runtime evidence directly — the brief itself is
            derived from the asset alone. Phase 11 adds a single read
            of ``runtime["_reference_board"]`` (the raw dict the
            executor publishes from
            :func:`lathe.asset_quality.reference_board.load_reference_board`)
            to merge reference-supplied negative constraints into the
            brief's ``negative_constraints`` field. When the slot is
            missing the brief is identical to the Phase 2 baseline.

    Returns:
        Additive payload with ``version`` (``"design_brief_v1"``),
        ``brief`` (12-field dict from :meth:`DesignBrief.to_dict`),
        ``family_inference`` (``matched_family``/``match_signal``/
        ``match_token``), and Phase-13
        ``user_provided_via_experimental`` (always present, with an
        empty ``fields`` list when no overrides apply). No top-level
        ``diagnostics`` key — like Phase 1, this validator is
        informational only and never blocks certification.
    """
    safe_asset = asset if isinstance(asset, dict) else {}
    safe_runtime = runtime if isinstance(runtime, dict) else {}
    asset_name = _as_str(safe_asset.get("name")) or "unnamed_asset"
    family, signal, token = _infer_family(safe_asset)
    base_brief = _build_default_brief(asset_name=asset_name, family=family)
    overrides = _experimental_art_direction(safe_asset)
    brief_with_overrides, applied_fields = _apply_art_direction_overrides(base_brief, overrides)
    reference_negatives = _reference_negative_constraints(safe_runtime)
    merged_negatives = _merge_negative_constraints(
        brief_with_overrides.negative_constraints, reference_negatives
    )
    if merged_negatives != brief_with_overrides.negative_constraints:
        brief = DesignBrief(
            asset_name=brief_with_overrides.asset_name,
            family=brief_with_overrides.family,
            role=brief_with_overrides.role,
            style_tags=brief_with_overrides.style_tags,
            silhouette=brief_with_overrides.silhouette,
            bevel_language=brief_with_overrides.bevel_language,
            shape_language=brief_with_overrides.shape_language,
            detail_density=brief_with_overrides.detail_density,
            wear=brief_with_overrides.wear,
            material_age=brief_with_overrides.material_age,
            greeble_style=brief_with_overrides.greeble_style,
            negative_constraints=merged_negatives,
        )
    else:
        brief = brief_with_overrides
    return {
        "version": VERSION,
        "brief": brief.to_dict(),
        "family_inference": {
            "matched_family": family,
            "match_signal": signal,
            "match_token": token,
        },
        "user_provided_via_experimental": {"fields": list(applied_fields)},
    }
