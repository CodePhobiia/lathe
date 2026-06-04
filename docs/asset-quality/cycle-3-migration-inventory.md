# Cycle 3 migration inventory — `_RECIPES` → declarative knowledge packs

**Live registry count (2026-05-11 audit):** 71 families across 4 migration rounds.

Per plan v2 §6.3 each family migrates via the same protocol:

1. Author/pick StyleKnowledge JSON for the family's visual / parameter intent.
2. Author/pick CompositionPolicy from the Round 0 reusable packs (or family-shared).
3. Author FamilyAlias JSON pointing at them.
4. Run `tests/contract/test_recipe_migration_shape_program_diff.py::test_<family>` — must be equivalent or better than the pre-migration recipe.
5. Run `tests/integration/test_recipe_migration_build_artifact_diff.py::test_<family>` — face count ±20%, material zones, package outputs.
6. Add family to `_MIGRATED_TO_SYNTHESIZER`.
7. Delete the recipe entry from `_RECIPES`.

Authoring a new family post-Cycle 3 means a single FamilyAlias JSON file with zero Python change (§6.4 acceptance).

---

## Round 2 — 17 simple families

Generic 10-op canonical pattern, no domain extension dependencies, no sub-asset composition. Some have one or two specialty ops (`sop.boolean`, `sop.carve`, `sop.loft`, `op.hull`, `op.mirror`) that need to be expressible via the synthesizer's NODE_TYPE graph.

Ordered simplest-first (smallest src lines):

| Family | src lines | ops | specials |
|---|---:|---:|---|
| `inventory_economy_object` | 153 | 10 | — |
| `world_system_assembly` | 160 | 10 | — |
| `attribute_surface_graph_program` | 162 | 10 | — |
| `stateful_destructible_prop` | 167 | 10 | — |
| `set_dressing_prop` | 170 | 10 | bool |
| `gameplay_object` | 171 | 10 | — |
| `surface_material_sample` | 172 | 10 | — |
| `environment_effect` | 180 | 10 | — |
| `encounter_flow` | 185 | 10 | — |
| `furniture_prop` | 191 | 10 | — |
| `tool_prop` | 191 | 10 | carve |
| `lighting_prop` | 192 | 10 | — |
| `settlement_district` | 198 | 10 | — |
| `environment_architecture` | 204 | 10 | loft |
| `machine_console` | 204 | 10 | bool |
| `portal_relic` | 212 | 10 | — |
| `vehicle_prop` | 218 | 10 | bool, hull, mirror |

**Round 2 task scope:** 10 of the 17 families migrate per §6.3 ("Round 2: Simple recipes (10 families)"). Pick the 10 simplest-without-specials first (`inventory_economy_object`, `world_system_assembly`, `attribute_surface_graph_program`, `stateful_destructible_prop`, `gameplay_object`, `surface_material_sample`, `environment_effect`, `encounter_flow`, `furniture_prop`, `lighting_prop`). The 7 remaining (`set_dressing_prop`, `tool_prop`, `settlement_district`, `environment_architecture`, `machine_console`, `portal_relic`, `vehicle_prop`) can drift into Round 2-bis after the specialty ops are validated through the synthesizer.

---

## Round 3 — 4 hard-surface guardrails

Per §6.3: "Cycle 4 must be at least partially shipped for these so visible-artifact diff is real evidence, not best-effort visual judgment."

Ordered by complexity:

| Family | src lines | ops | specials | Note |
|---|---:|---:|---|---|
| `industrial_crate` | 51 | 0* | — | Already delegates to 10 `_industrial_crate_*` sub-lowerers. Hero Sprint 0 fixture per CLAUDE.md northstar — migrate first. |
| `service_cabinet` | 207 | 10 | — | |
| `weapon_prop` | 211 | 10 | carve | |
| `mechanical_door` | 263 | 12 | mirror, distribute | |

*industrial_crate scans as 0 ops in the recipe entry-point because the ShapeOp construction is delegated to 10 sub-lowerers (`_industrial_crate_body_shell`, `_industrial_crate_lid_seam`, etc.). Migration replaces all 11 of those functions with a FamilyAlias + the panelized_hard_surface_object composition policy.

---

## Round 4 — 26 procedural-domain families (BLOCKED on Cycle 6)

Per §6.3: "These require corresponding DomainExtension packs (from Cycle 6). Migration of each of these waits on its domain extension shipping."

Grouped by domain:

### Vegetation domain
- `vegetation_library_system` (emits `solid.branching_tree`)
- `terrain_vegetation_variant`
- `natural_form`

### Terrain domain
- `terrain_heightfield_system` (emits `solid.terrain_patch`)

### CGA/grammar domain
- `cga_building_grammar_system` (emits `solid.cga_facade`)
- `wfc_tile_solver_system` (emits `solid.wfc_modular_assembly`)

### F-Rep / SDF domain
- `f_rep_sdf_composition_system` (emits `solid.sdf_metaball_cluster`)
- `face_sdf_cel_shading_system`

### Hair / cloth / fluid simulation domains
- `hair_program_system`
- `cloth_attachment_form`
- `cloth_fabric_simulation_program_system`
- `fluid_forward_volume_program_system`
- `volume_effects_data_system`

### Animation / rig domain
- `animation_library_binding_system`
- `gameplay_animation_controller_system`
- `procedural_facial_rig_pack_system`
- `retargeting_pack_system`
- `morph_target_database_system`
- `rig_component_library_system`
- `rig_animation_proxy`
- `character_equipment_binding_system`

### Character / body domain
- `character_creature`
- `humanoid_anatomy_preset_system`
- `creature_appendage_program_system`
- `body_part_procedural_library_system`

### Audio domain
- `procedural_audio_cue_bundle`

---

## Round 5 — 24 bundle/system families (need `assembly` NODE_TYPE)

Per §6.3: "Bundle/system recipes — require sub-asset composition (open question §9.5 in spec). Prototype the `assembly` NODE_TYPE before migrating these."

| Family | src lines | ops |
|---|---:|---:|
| `cross_domain_composition_pack` | 144 | 10 |
| `typed_data_kernel_bundle` | 147 | 10 |
| `style_stack_visual_band` | 149 | 10 |
| `authored_multi_asset_bundle` | 152 | 10 |
| `subdivision_finishing_system` | 152 | 10 |
| `live_procedural_runtime_bundle` | 153 | 10 |
| `construction_grammar_kit_system` | 154 | 10 |
| `engine_facing_runtime_bundle_system` | 154 | 10 |
| `behavior_logic_graph_bundle` | 154 | 10 |
| `camera_cinematic_direction_bundle` | 154 | 10 |
| `save_state_persistence_bundle` | 155 | 10 |
| `multiplayer_session_replication_bundle` | 155 | 10 |
| `instance_pattern_scatter_system` | 155 | 10 |
| `material_primitive_library_system` | 158 | 10 |
| `simulation_environment_system` | 158 | 10 |
| `scene_system_authoring_bundle` | 159 | 10 |
| `world_streaming_runtime_partition_bundle` | 159 | 10 |
| `quest_dialogue_authoring_bundle` | 160 | 10 |
| `localization_text_table_bundle` | 160 | 10 |
| `accessibility_ux_affordance_bundle` | 160 | 10 |
| `economy_simulation_tuning_bundle` | 160 | 10 |
| `procedural_prefab_binding_system` | 165 | 10 |
| `domain_kit_bundle` | 171 | 10 |
| `modular_kit` | 196 | 10 |

---

## Structural observation

All 71 recipes are hash-unique (none are literal clones) but **every recipe except `industrial_crate` emits the same 10-op canonical pattern**: `op.chip_edges`, `sop.copy_to_points`, `sop.polybevel`, `sop.polyextrude`, `sop.polywire` + family-specific parameters. Variation is in `target` strings, dimensions, profile points, scatter point lists, and material-zone tags.

This means migration is largely **parameter-extraction + StyleKnowledge authoring**, not structural redesign. A small number of families (`vehicle_prop`, `mechanical_door`, `tool_prop`, etc.) carry true structural differences (boolean/carve/hull/mirror/distribute ops) and need slightly richer composition policies.

The dispatch site is `lathe/asset_quality/grammar_lowering.py:13577` (`_RECIPES = {...}`).
