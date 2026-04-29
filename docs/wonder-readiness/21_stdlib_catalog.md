# Wonder Stdlib Catalog

This catalog names the reusable content vocabulary currently exercised by
Wonder examples. The entries are Scene Graph contract terms: object IDs,
`lathe_asset` names, source families, material roles, and style tokens that
deterministic planners can reason about. They are not a claim that mesh, render,
or engine export artifacts have been produced.

## Source Families

| Family | Roles | Example contract entries | Readiness use |
| --- | --- | --- | --- |
| `environment_architecture` | `architecture` | `terrace_wall_modules`, `glass_tube_concourse`, `courtyard_wall_shell`, `rib_arch_ring`, `storefront_row` | Room shells, walls, arches, concourses, storefronts, and boundary modules. |
| `environment_structure` | `environment_structure` | `cloudline_backdrop`, `date_palm_shadows` | Background silhouettes, terrain edges, vista blockers, and scale cues. |
| `navigation_marker` | `navigation` | `switchback_stairs`, `platform_edge_markers`, `sand_channel_path`, `broken_escalator_rail` | Readable paths, route blockers, stair runs, platform edges, and waypoint surfaces. |
| `hero_prop` | `hero_prop` | `lightning_rod_tower`, `stopped_bathysphere_train`, `oracle_mirror`, `astrolabe_table`, `dry_fountain_planter` | Central props that anchor reveal cameras and curiosity hooks. |
| `interactive_mechanism` | `interactive` | `sky_bridge_gate`, `sealed_service_hatch`, `sealed_sun_door`, `sealed_archive_door`, `arcade_security_gate` | Doors, gates, hatches, locks, and player-facing expansion triggers. |
| `practical_light` | `light_fixture` | `storm_lanterns`, `red_signal_lamps`, `incense_braziers`, `candle_cluster` | Lighting props that double as route, ritual, or state clues. |
| `dressing_prop` | `dressing_prop` | `coral_platform_growth`, `candle_cluster` | Secondary scene dressing that supports style and scale. |

## Environment Modules

| Module class | Contract entries | Example scenes |
| --- | --- | --- |
| Wall and shell modules | `terrace_wall_modules`, `courtyard_wall_shell`, `rib_arch_ring`, `storefront_row` | Mountain Lightning City, Desert Oracle Shrine, Alchemist Observatory, Abandoned Roblox Mall |
| Platform and floor modules | `platform_edge_markers`, `sand_channel_path`, `dry_fountain_planter` | Underwater Train Station, Desert Oracle Shrine, Abandoned Roblox Mall |
| Vertical route modules | `switchback_stairs`, `broken_escalator_rail` | Mountain Lightning City, Abandoned Roblox Mall |
| Threshold modules | `sky_bridge_gate`, `sealed_service_hatch`, `sealed_sun_door`, `sealed_archive_door`, `arcade_security_gate` | Mountain Lightning City, Underwater Train Station, Desert Oracle Shrine, Alchemist Observatory, Abandoned Roblox Mall |
| Background modules | `cloudline_backdrop`, `date_palm_shadows` | Mountain Lightning City, Desert Oracle Shrine |

Wall and shell modules should be compatible with the JSON-first
`layout.modular_walls` contract: rectangular region bounds define the perimeter,
module length and snap grid define deterministic segment centers, and generated
`wall_segments` remain constraints for downstream mesh/build work rather than
runtime wall meshes.

## Material And Style Packs

| Pack | Palette tokens | Material tokens | Example scenes |
| --- | --- | --- | --- |
| Storm cliff city | `storm violet`, `wet basalt`, `copper lantern`, `cloud silver`, `warning amber` | `stacked basalt`, `weathered copper`, `rain glass`, `painted cloth` | Mountain Lightning City |
| Undersea transit | `deep teal`, `oxidized brass`, `pearl white`, `signal red`, `algae green` | `riveted glass`, `aged brass`, `ceramic tile`, `wet concrete` | Underwater Train Station |
| Desert oracle | `sun bleached limestone`, `lapis tile`, `shadow blue`, `gold dust`, `desert sage` | `carved stone`, `polished tile`, `woven cloth`, `sandstone` | Desert Oracle Shrine |
| Bone observatory | `bone ivory`, `oxidized copper`, `black glass`, `candle gold`, `lunar blue` | `bone stone`, `oxidized brass`, `obsidian glass`, `cracked enamel`, `wax` | Alchemist Observatory |
| Roblox mall | `faded teal`, `sun-worn coral`, `dust gray`, `soft yellow` | `painted concrete`, `scuffed tile`, `simple glass`, `plastic signage` | Abandoned Roblox Mall |

## Promotion Criteria

Catalog entries become stronger standard-library candidates when they have:

- at least one Dream Brief and Scene Graph reference
- stable lower-snake-case IDs
- a source family or source kit assignment
- material language that overlaps the example style bible
- object state metadata for game-facing budgets where relevant
- focused tests that validate the example contracts and plan generation

The current catalog is enough for contract and planning coverage. Mesh assets,
rendered previews, and engine export bundles should be promoted only with
separate build evidence.

## Machine-Readable Phase 25 Catalog

# Wonder Stdlib Catalog

This catalog names reusable Wonder component contracts. Entries are stable
Scene Graph source references for planning and materialization; final meshes,
engine imports, and external viewer proof require separate build evidence.

## Summary

| Components | Categories | Materials |
| --- | --- | --- |
| 49 | architecture, environmental_dressing, hero_prop, lighting_fixture, natural_form | 5 |

## Components

| Component | Category | Source | Role | Material |
| --- | --- | --- | --- | --- |
| `architecture_wall` | architecture | `architecture_wall_kit` | architecture | `mat_stdlib_architecture` |
| `architecture_floor` | architecture | `architecture_floor_kit` | architecture | `mat_stdlib_architecture` |
| `architecture_ceiling` | architecture | `architecture_ceiling_kit` | architecture | `mat_stdlib_architecture` |
| `architecture_arch` | architecture | `architecture_arch_kit` | architecture | `mat_stdlib_architecture` |
| `architecture_column` | architecture | `architecture_column_kit` | architecture | `mat_stdlib_architecture` |
| `architecture_stair` | architecture | `architecture_stair_kit` | architecture | `mat_stdlib_architecture` |
| `architecture_door` | architecture | `architecture_door_kit` | architecture | `mat_stdlib_architecture` |
| `architecture_window` | architecture | `architecture_window_kit` | architecture | `mat_stdlib_architecture` |
| `architecture_bridge` | architecture | `architecture_bridge_kit` | architecture | `mat_stdlib_architecture` |
| `architecture_railing` | architecture | `architecture_railing_kit` | architecture | `mat_stdlib_architecture` |
| `architecture_platform` | architecture | `architecture_platform_kit` | architecture | `mat_stdlib_architecture` |
| `architecture_tunnel` | architecture | `architecture_tunnel_kit` | architecture | `mat_stdlib_architecture` |
| `architecture_room_shell` | architecture | `modular_room_shell_kit` | architecture | `mat_stdlib_architecture` |
| `dressing_crate` | environmental_dressing | `dressing_crate_family` | dressing_prop | `mat_stdlib_dressing` |
| `dressing_barrel` | environmental_dressing | `dressing_barrel_family` | dressing_prop | `mat_stdlib_dressing` |
| `dressing_book` | environmental_dressing | `dressing_book_family` | dressing_prop | `mat_stdlib_dressing` |
| `dressing_candle` | environmental_dressing | `dressing_candle_family` | dressing_prop | `mat_stdlib_dressing` |
| `dressing_chain` | environmental_dressing | `dressing_chain_family` | dressing_prop | `mat_stdlib_dressing` |
| `dressing_pipe` | environmental_dressing | `dressing_pipe_family` | dressing_prop | `mat_stdlib_dressing` |
| `dressing_vent` | environmental_dressing | `dressing_vent_family` | dressing_prop | `mat_stdlib_dressing` |
| `dressing_panel` | environmental_dressing | `dressing_panel_family` | dressing_prop | `mat_stdlib_dressing` |
| `dressing_debris` | environmental_dressing | `dressing_debris_family` | dressing_prop | `mat_stdlib_dressing` |
| `dressing_rug` | environmental_dressing | `dressing_rug_family` | dressing_prop | `mat_stdlib_dressing` |
| `dressing_banner` | environmental_dressing | `dressing_banner_family` | dressing_prop | `mat_stdlib_dressing` |
| `dressing_sign` | environmental_dressing | `dressing_sign_family` | dressing_prop | `mat_stdlib_dressing` |
| `natural_rock` | natural_form | `natural_rock_family` | environment_structure | `mat_stdlib_natural` |
| `natural_root` | natural_form | `natural_root_family` | environment_structure | `mat_stdlib_natural` |
| `natural_vine` | natural_form | `natural_vine_family` | environment_structure | `mat_stdlib_natural` |
| `natural_crystal` | natural_form | `natural_crystal_family` | environment_structure | `mat_stdlib_natural` |
| `natural_mushroom` | natural_form | `natural_mushroom_family` | environment_structure | `mat_stdlib_natural` |
| `natural_dead_tree` | natural_form | `natural_dead_tree_family` | environment_structure | `mat_stdlib_natural` |
| `natural_bone` | natural_form | `natural_bone_family` | environment_structure | `mat_stdlib_natural` |
| `natural_coral_form` | natural_form | `natural_coral_form_family` | environment_structure | `mat_stdlib_natural` |
| `natural_terrain_chunk` | natural_form | `natural_terrain_chunk_kit` | environment_structure | `mat_stdlib_natural` |
| `hero_altar` | hero_prop | `hero_altar_family` | hero_prop | `mat_stdlib_hero` |
| `hero_machine` | hero_prop | `hero_machine_family` | hero_prop | `mat_stdlib_hero` |
| `hero_console` | hero_prop | `hero_console_family` | hero_prop | `mat_stdlib_hero` |
| `hero_relic` | hero_prop | `hero_relic_family` | hero_prop | `mat_stdlib_hero` |
| `hero_portal` | hero_prop | `hero_portal_family` | hero_prop | `mat_stdlib_hero` |
| `hero_vehicle` | hero_prop | `hero_vehicle_family` | hero_prop | `mat_stdlib_hero` |
| `hero_weapon` | hero_prop | `hero_weapon_family` | hero_prop | `mat_stdlib_hero` |
| `hero_tool` | hero_prop | `hero_tool_family` | hero_prop | `mat_stdlib_hero` |
| `hero_furniture` | hero_prop | `hero_furniture_family` | hero_prop | `mat_stdlib_hero` |
| `light_torch` | lighting_fixture | `light_torch_family` | light_fixture | `mat_stdlib_light` |
| `light_lamp` | lighting_fixture | `light_lamp_family` | light_fixture | `mat_stdlib_light` |
| `light_neon_tube` | lighting_fixture | `light_neon_tube_family` | light_fixture | `mat_stdlib_light` |
| `light_moon_window` | lighting_fixture | `light_moon_window_kit` | light_fixture | `mat_stdlib_light` |
| `light_glowing_crystal` | lighting_fixture | `light_glowing_crystal_family` | light_fixture | `mat_stdlib_light` |
| `light_hologram` | lighting_fixture | `light_hologram_family` | light_fixture | `mat_stdlib_light` |

## Scene Example

The in-memory `stdlib_component_showcase` Scene Graph emitted by
`lathe.scene.stdlib.stdlib_showcase_scene_graph()` references every
component in this catalog. Unit tests validate that it passes Scene Graph
schema checks, scene validators, scene planning, and generated Lathe
asset-source materialization.
