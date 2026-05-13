# Examples catalog

Index of every runnable `.lth` source under `examples/`. Asset-oriented files
parse via `lathe check`; Wonder scene-source bridge files are validated with
`lathe scene source-to-scene-graph` because their embedded Scene Graph payload
is the durable source of truth. Certification (`lathe build ... --out ...` +
`validate/report.json` `certified == True`) is tracked per-row where an asset
build exists.

Build times assume a local `.venv` with xatlas/manifold3d installed, native
shape provider, no remote runtime config.

Complexity tiers:

- **T0** — canonical hero (8+ parts, full surface program, full assembly).
- **T1** — compact variant of a hero (renamed asset, same part graph).
- **T2** — feature-focused API demo (highlights a specific language surface).

## Hero examples (top-level `examples/`)

Cert column reflects the `validate/report.json` `certified` value on a
clean local `.venv` build. Heroes marked `x` currently score below their
own threshold — they are tracked so regressions surface, but are not
expected to pass certification today.

Rows marked `x` are explicitly experimental or known-limitation examples until
the catalog, tests, and release checklist show fresh passing evidence. They are
tracked so regressions surface, but they are not release-polish proof today.

| File | Family | Tier | Features | Build | Cert |
|------|--------|------|----------|-------|------|
| `examples/brassbound_chest.lth` | `brassbound_chest` | T0 | hero loot chest, wood+brass PBR, lid mechanism | ~45s | o |
| `examples/industrial_crate.lth` | `industrial_crate` | T0 | steel shipping crate, warning paint, latch | ~2s | o |
| `examples/industrial_crate_experimental.lth` | `industrial_crate` | T0 | Phase 13 experimental wrapper: art_direction overrides + references override + kit declaration | ~2s | o |
| `examples/mechanical_door.lth` | `mechanical_door` | T0 | env module, hinged door w/ handle | ~37s | o |
| `examples/courier_drone.lth` | `courier_drone` | T0 | quad rotor, cargo hatch, battery sockets | ~2s | o |
| `examples/hero_sword.lth` | `hero_sword` | T0 | medieval sword, steel blade, leather grip, brass guard | ~2s | o |
| `examples/console_terminal.lth` | `console_terminal` | T0 | wall console, screen + keypad | ~75s | o |
| `examples/control_pedestal.lth` | `control_pedestal` | T0 | operator pedestal, levers | ~95s | o |
| `examples/sci_fi_wall_panel.lth` | `sci_fi_wall_panel` | T0 | env wall panel + vents | ~7s | o |
| `examples/service_cabinet.lth` | `service_cabinet` | T0 | wall service cabinet w/ hinged doors | ~30s | o |
| `examples/supply_container.lth` | `supply_container` | T0 | strapped field supply box | ~42s | o |
| `examples/tutorial_bookshelf.lth` | generic | T2 | docs walkthrough — minimal features | ~3s | x |

## Additional top-level examples

These checked-in examples exercise preview or experimental language surfaces.
They are runnable examples, but rows marked `x` are not release-polish proof
until promoted into the canonical gallery or expected-certification set.

| File | Asset or variant | Tier | Features | Build | Cert |
|------|------------------|------|----------|-------|------|
| `examples/brassbound_chest_v13_blender.lth` | `brassbound_chest_v13` | T2 | Blender-oriented V1.3 hard-surface chest experiment | varies | x |
| `examples/brassbound_chest_v13_1_codex_blender.lth` | `brassbound_chest_v13_1` | T2 | Codex-authored V1.3.1 chest variant | varies | x |
| `examples/astral_sentinel_sword.lth` | `astral_sentinel_sword` | T2 | Phase 14 generated hero sword quality/evidence example | varies | x |
| `examples/console_terminal_mobile_adapt.lth` | `console_terminal_mobile` | T1 | mobile adaptation of the console terminal family | varies | o |
| `examples/console_terminal_v12_surface.lth` | `console_terminal_v12_surface` | T2 | V1.2 governed surface authoring slice | varies | x |
| `examples/reconstruct_courier_from_mesh.lth` | `reconstruct_courier_from_mesh` | T2 | mesh-conditioned courier reconstruction | varies | o |
| `examples/reconstruct_courier_from_views.lth` | `reconstruct_courier_from_views` | T2 | reference-view reconstruction using checked-in images | varies | x |
| `examples/satchel_bag.lth` | `satchel_bag` | T2 | soft-prop contract experiment | varies | x |
| `examples/service_corridor_wall.lth` | `service_corridor_wall` | T2 | modular industrial wall-kit environment slice | varies | x |

## Geometry capability examples

These examples exercise generation controls for richer scaffold geometry:
edge treatments, panel cuts, grooves, ridges, trim strips, sockets,
detail zones, material layering, modular sockets, and game-pipeline hints.

| File | Family | Tier | Features | Build | Cert |
|------|--------|------|----------|-------|------|
| `examples/geometry_wave1_beveled_maintenance_hatch.lth` | geometry capability | T2 | generated detail controls | varies | x |
| `examples/geometry_wave1_bolted_power_pedestal.lth` | geometry capability | T2 | generated detail controls | varies | x |
| `examples/geometry_wave1_corner_guard_tool_case.lth` | geometry capability | T2 | generated detail controls | varies | x |
| `examples/geometry_wave1_cutline_floor_module.lth` | geometry capability | T2 | generated detail controls | varies | x |
| `examples/geometry_wave1_edge_treated_sword_core.lth` | geometry capability | T2 | generated detail controls | varies | x |
| `examples/geometry_wave1_greebled_courier_pod.lth` | geometry capability | T2 | generated detail controls | varies | x |
| `examples/geometry_wave1_greebled_data_core.lth` | geometry capability | T2 | generated detail controls | varies | x |
| `examples/geometry_wave1_groove_ridge_generator.lth` | geometry capability | T2 | generated detail controls | varies | x |
| `examples/geometry_wave1_grooved_airlock_door.lth` | geometry capability | T2 | generated detail controls | varies | x |
| `examples/geometry_wave1_grooved_weapon_rack.lth` | geometry capability | T2 | generated detail controls | varies | x |
| `examples/geometry_wave1_layered_drone_body.lth` | geometry capability | T2 | generated detail controls | varies | x |
| `examples/geometry_wave1_layered_robotic_actuator.lth` | geometry capability | T2 | generated detail controls | varies | x |
| `examples/geometry_wave1_layered_sci_fi_column.lth` | geometry capability | T2 | generated detail controls | varies | x |
| `examples/geometry_wave1_layered_supply_container.lth` | geometry capability | T2 | generated detail controls | varies | x |
| `examples/geometry_wave1_low_detail_counterpart.lth` | geometry capability | T2 | generated detail controls | varies | x |
| `examples/geometry_wave1_modular_battery_pack.lth` | geometry capability | T2 | generated detail controls | varies | x |
| `examples/geometry_wave1_panelized_medical_case.lth` | geometry capability | T2 | generated detail controls | varies | x |
| `examples/geometry_wave1_panelized_service_crate.lth` | geometry capability | T2 | generated detail controls | varies | x |
| `examples/geometry_wave1_panelized_terminal_bank.lth` | geometry capability | T2 | generated detail controls | varies | x |
| `examples/geometry_wave1_reinforced_cargo_lid.lth` | geometry capability | T2 | generated detail controls | varies | x |
| `examples/geometry_wave1_ridged_console_terminal.lth` | geometry capability | T2 | generated detail controls | varies | x |
| `examples/geometry_wave1_ridged_exhaust_vent.lth` | geometry capability | T2 | generated detail controls | varies | x |
| `examples/geometry_wave1_riveted_field_radio.lth` | geometry capability | T2 | generated detail controls | varies | x |
| `examples/geometry_wave1_socket_rail_adapter.lth` | geometry capability | T2 | generated detail controls | varies | x |
| `examples/geometry_wave1_socketed_service_cabinet.lth` | geometry capability | T2 | generated detail controls | varies | x |
| `examples/geometry_wave1_socketed_wall_panel.lth` | geometry capability | T2 | generated detail controls | varies | x |
| `examples/geometry_wave1_trimmed_sensor_pylon.lth` | geometry capability | T2 | generated detail controls | varies | x |
| `examples/geometry_wave2_aaa_sci_fi_tool.lth` | geometry capability | T2 | zoned detail, material story, hero demonstrator | varies | x |
| `examples/geometry_wave2_brutalist_wall_console.lth` | geometry capability | T2 | style grammar, heavy panels, socket details | varies | x |
| `examples/geometry_wave2_detail_zoned_service_cabinet.lth` | geometry capability | T2 | named detail zones and motif placement | varies | x |
| `examples/geometry_wave2_fantasy_relic_chest.lth` | geometry capability | T2 | ornamental radial detail and ancient material story | varies | x |
| `examples/geometry_wave2_game_pipeline_panel_kit.lth` | geometry capability | T2 | modular sockets, LOD/export/collision hints | varies | x |
| `examples/geometry_wave2_layered_material_crate.lth` | geometry capability | T2 | procedural material layers and battle-worn wear | varies | x |
| `examples/geometry_wave2_modular_socket_drone_pylon.lth` | geometry capability | T2 | swappable module sockets and radial connector detail | varies | x |
| `examples/geometry_wave2_wave_a_edge_array_tool.lth` | geometry capability | T2 | Wave A edge, array, trim, inset/outset operators | varies | x |
| `examples/treasure_chest.lth` | geometry capability | T2 | mesh_program treasure chest using rounded solids, booleans, seam bevels, trim bands, fastener grids, plank grooves, and scatter gems | varies | x |
| `examples/geometry_wave3_cabled_console_bank.lth` | geometry capability | T2 | generic cable, handle, rail, and vent attachment motifs | varies | x |
| `examples/geometry_wave3_finned_reactor_pylon.lth` | geometry capability | T2 | fins, vent stacks, rails, and cable routes | varies | x |
| `examples/geometry_wave3_ornamented_relic_panel.lth` | geometry capability | T2 | ornaments, straps, and guard bars | varies | x |
| `examples/geometry_wave3_rail_strap_field_generator.lth` | geometry capability | T2 | rails, straps, guards, and handle bars | varies | x |
| `examples/geometry_wave4_ancient_patina_relic_terminal.lth` | geometry capability | T2 | ancient material story maps with patina, rubbed edges, and layered accents | varies | x |
| `examples/geometry_wave4_battle_worn_material_stack.lth` | geometry capability | T2 | battle-worn procedural material stack with generated wear/layer masks | varies | x |
| `examples/geometry_wave4_factory_new_clean_panel.lth` | geometry capability | T2 | low-wear factory-new material-map controls and clean panel layering | varies | x |
| `examples/geometry_wave4_salvaged_tool_surface_story.lth` | geometry capability | T2 | salvaged paint chips, grime, straps, cables, and exposed underlayers | varies | x |
| `examples/geometry_wave5_deployable_field_terminal.lth` | geometry capability | T2 | swappable leg, shield, antenna, and power-cell modules | varies | x |
| `examples/geometry_wave5_kitbash_wall_node.lth` | geometry capability | T2 | kitbash wall module loadout with armor, sensors, cells, and masts | varies | x |
| `examples/geometry_wave5_modular_sensor_drone_core.lth` | geometry capability | T2 | modular drone core with sensor pods, wings, antennas, and power cells | varies | x |
| `examples/geometry_wave5_swappable_weapon_tool.lth` | geometry capability | T2 | weapon/tool module loadout with barrel, blade, shield, and battery modules | varies | x |
| `examples/geometry_wave6_arcane_luxury_relic_panel.lth` | geometry capability | T2 | arcane luxury style pack with ornate ridges, radial motifs, and inherited patina story | varies | x |
| `examples/geometry_wave6_battle_worn_field_generator.lth` | geometry capability | T2 | battle-worn field style pack with straps, cells, shields, and scar decals | varies | x |
| `examples/geometry_wave6_industrial_hero_console.lth` | geometry capability | T2 | industrial hero style pack with heavy panels, sockets, modules, LOD, and export hints | varies | x |
| `examples/geometry_wave6_sleek_sci_fi_sensor_fin.lth` | geometry capability | T2 | sleek sci-fi style pack with layered ridges, sensor pods, fins, and calibration marks | varies | x |
| `examples/geometry_wave7_blade_like_repair_tool.lth` | geometry capability | T2 | blade-like silhouette profile with forward tool head, guard cowl, and handle | varies | x |
| `examples/geometry_wave7_ornate_spire_relic_gate.lth` | geometry capability | T2 | ornate spire silhouette profile with towers, spines, blade finials, and rune sockets | varies | x |
| `examples/geometry_wave7_sleek_winged_drone_keel.lth` | geometry capability | T2 | sleek winged silhouette profile with side fins, sensor mast, and dorsal spine | varies | x |
| `examples/geometry_wave7_wide_heavy_power_core.lth` | geometry capability | T2 | wide-heavy silhouette profile with outriggers, guard cowls, and dorsal spine | varies | x |
| `examples/geometry_wave8_arcane_brass_trim_gate.lth` | geometry capability | T2 | relic decal library and ornate brass trim sheet drive generated surface marks | varies | x |
| `examples/geometry_wave8_field_worn_supply_node.lth` | geometry capability | T2 | field-worn decal library and metal trim sheet with modular shield/cell loadout | varies | x |
| `examples/geometry_wave8_industrial_trim_console.lth` | geometry capability | T2 | industrial decal library and metal strip trim sheet drive generated trim/decal maps | varies | x |
| `examples/geometry_wave8_prototype_calibration_pod.lth` | geometry capability | T2 | prototype decal library and panel trim sheet generate calibration and band marks | varies | x |
| `examples/geometry_wave9_real_highlow_drone_core.lth` | geometry capability | T2 | authored high/low LOD pair for a sleek modular drone core | varies | x |
| `examples/geometry_wave9_real_highlow_field_generator.lth` | geometry capability | T2 | battle-worn field generator with explicit LOD-pair high/low bake relation | varies | x |
| `examples/geometry_wave9_real_highlow_relic_spire.lth` | geometry capability | T2 | ornate relic spire with hero detail and low runtime LOD relation | varies | x |
| `examples/geometry_wave9_real_highlow_tool_head.lth` | geometry capability | T2 | blade-like repair tool with authored high/low LOD pair | varies | x |
| `examples/geometry_wave10_uv_material_id_console.lth` | geometry capability | T2 | industrial console with semantic UV charts and material-ID mask layout | varies | x |
| `examples/geometry_wave10_uv_material_id_drone_core.lth` | geometry capability | T2 | sleek drone core with material-grouped UV islands and modular texture sets | varies | x |
| `examples/geometry_wave10_uv_material_id_field_generator.lth` | geometry capability | T2 | field generator with UV charts grouped by painted metal rubber and glass zones | varies | x |
| `examples/geometry_wave10_uv_material_id_relic_gate.lth` | geometry capability | T2 | ornate relic gate with separated stone brass and glass material-ID islands | varies | x |
| `examples/geometry_wave11_story_ancient_relic_gate.lth` | geometry capability | T2 | ancient relic gate with targeted rune patina and asymmetric story placement | varies | x |
| `examples/geometry_wave11_story_battle_worn_generator.lth` | geometry capability | T2 | battle-worn generator with targeted heat marks repair labels and scratches | varies | x |
| `examples/geometry_wave11_story_faction_drone_core.lth` | geometry capability | T2 | faction-marked drone core with calibration decals placed on authored targets | varies | x |
| `examples/geometry_wave11_story_marked_service_cabinet.lth` | geometry capability | T2 | service cabinet with targeted labels scratches faction marks and asymmetry | varies | x |

## Wonder scene-source bridge examples (`examples/wonder/`)

These `.lth` files are generated from the committed Scene Graph JSON and must
roundtrip through `lathe scene source-to-scene-graph`. They are not asset build
targets by themselves.

| File | Scene | Validation | Notes |
|------|-------|------------|-------|
| `examples/wonder/abandoned_roblox_mall/scene_source.lth` | `abandoned_roblox_mall` | source bridge roundtrip | Roblox-compatible mall interior seed |
| `examples/wonder/alchemist_observatory/scene_source.lth` | `alchemist_observatory` | source bridge roundtrip | canonical Wonder seed scene |
| `examples/wonder/desert_oracle_shrine/scene_source.lth` | `desert_oracle_shrine` | source bridge roundtrip | desert shrine scene seed |
| `examples/wonder/environment_module_showcase/scene_source.lth` | `environment_module_showcase` | source bridge roundtrip | environment-module showcase |
| `examples/wonder/mountain_lightning_city/scene_source.lth` | `mountain_lightning_city` | source bridge roundtrip | mountain city scene seed |
| `examples/wonder/stdlib_component_showcase/scene_source.lth` | `stdlib_component_showcase` | source bridge roundtrip | standard-library component showcase |
| `examples/wonder/underwater_train_station/scene_source.lth` | `underwater_train_station` | source bridge roundtrip | underwater station scene seed |

## API examples (`examples/api/`)

One file per public-surface concept. Each is built on
`industrial_crate_family` so it certifies without configuration.

| File | Concept | Highlights | Build |
|------|---------|------------|-------|
| `examples/api/primitives.lth` | part graph + feature density | `intent.parts`, `features.density`, `assembly.components` | ~2s |
| `examples/api/csg_boolean.lth` | boolean / integration rules | `geometry.integration_rules`, `seam_classes`, `edge_classes` | ~2s |
| `examples/api/socket.lth` | typed interface sockets | `build.interfaces.sockets`, `pivots`, `clearance` | ~2s |
| `examples/api/lod_config.lth` | LOD + runtime budgets | `build.optimize.{lods, atlas, draw_calls, texture_budget}` | ~2s |
| `examples/api/material_pbr.lth` | PBR material authoring | `surface.program`, `maps`, `bakes`, `material_zones` | ~2s |
| `examples/api/variant.lth` | variant patch/append ops | `variant ... on`, `set`/`append`, layered `profile uses` | ~2s |

## Compiler corpus (`examples/corpus/`)

Small asset zoo exercising every hero blueprint. Each is a tagged rename of
the matching `examples/<hero>.lth` so it certifies via the same blueprint but
lives under an independent registry path.

| File | Base family | Category | Build | Cert |
|------|-------------|----------|-------|------|
| `examples/corpus/corpus_crate.lth` | `industrial_crate` | container | ~2s | o |
| `examples/corpus/corpus_crate_compact.lth` | `industrial_crate` | container (0.6m scale) | ~2s | o |
| `examples/corpus/corpus_chest.lth` | `brassbound_chest` | container (wood/brass) | ~45s | o |
| `examples/corpus/corpus_door.lth` | `mechanical_door` | door | ~37s | o |
| `examples/corpus/corpus_drone.lth` | `courier_drone` | vehicle / mechanical | ~2s | o |
| `examples/corpus/corpus_supply.lth` | `supply_container` | container (strap) | ~42s | o |
| `examples/corpus/corpus_terminal.lth` | `console_terminal` | interactable | ~75s | o |
| `examples/corpus/corpus_pedestal.lth` | `control_pedestal` | interactable | ~95s | o |
| `examples/corpus/corpus_wall_panel.lth` | `sci_fi_wall_panel` | decoration / env | ~7s | o |
| `examples/corpus/corpus_cabinet.lth` | `service_cabinet` | container (wall-mount) | ~30s | o |

## Imagination-to-life demos (top-level `examples/`)

One-paradigm-per-file demos exercising the imagination-to-life feature lanes
(vegetation, terrain, SDF/F-Rep, scatter, WFC tiling, parametric, volume,
bevel). See also `docs/imagination_to_life_demos.md`. These are runnable
demos, not certified hero assets, so `Cert` is `x`.

| File | Asset or demo | Tier | Features | Build | Cert |
|------|---------------|------|----------|-------|------|
| `examples/alien_blob_demo.lth` | `alien_blob` | T2 | SDF/F-Rep blob primitive demo | varies | x |
| `examples/alien_grove_showcase.lth` | `alien_grove` | T2 | CAPSTONE showcase combining hard-surface + vegetation + terrain + SDF + WFC | varies | x |
| `examples/bevel_demo.lth` | `bevel_demo` | T2 | bevel operator demonstration | varies | x |
| `examples/dungeon_corridor_demo.lth` | `dungeon_corridor` | T2 | Wave-Function-Collapse tiling demo | varies | x |
| `examples/f_rep_alien_blob.lth` | `f_rep_alien_blob` | T2 | function-representation (F-Rep) alien blob | varies | x |
| `examples/mech_prop_demo.lth` | `mech_prop` | T2 | hard-surface mech prop demonstration | varies | x |
| `examples/oak_tree_demo.lth` | `oak_tree` | T2 | vegetation paradigm — oak species tree | varies | x |
| `examples/parametric_facade.lth` | `parametric_facade` | T2 | parametric-grammar facade demo | varies | x |
| `examples/rocky_hill_demo.lth` | `rocky_hill` | T2 | terrain paradigm — rocky hill heightfield | varies | x |
| `examples/scatter_demo.lth` | `scatter_demo` | T2 | scatter paradigm — point distribution demo | varies | x |
| `examples/scatter_on_surface_demo.lth` | `scatter_on_surface_demo` | T2 | scatter constrained to a surface | varies | x |
| `examples/volume_smoke_cloud.lth` | `volume_smoke_cloud` | T2 | volume paradigm — smoke/cloud density field | varies | x |

## CI coverage

`.github/workflows/examples.yml` has three jobs:

- **check** — `lathe check` every API and corpus example on PR (fast, ~2s/file).
- **build-nightly** — full build + certification on the API and corpus example
  suite, runs on the cron schedule (and manual dispatch).
- **corpus-pytest** — runs `tests/unit/test_example_corpus.py` on every PR so
  certification regressions show up before nightly.

Artifacts uploaded: `build_report.json`, `selector_manifest.json`, and
`stages/validate/report.json` for every asset built.

## Authoring a new example

1. Pick the closest hero family in `std/families/`.
2. Copy `examples/<hero>.lth` and rename the `module`, the top-level asset,
   and the registry path. Keep `parts`, `assembly.components`, and
   `seam_classes` aligned with the family blueprint — those drive
   `part_coverage` and `adjacency_score` during certification.
3. Run `python -m lathe.cli check <file>` — must return `ok=True`.
4. Run `python -m lathe.cli build <file> <asset> --out tmp_out` and inspect
   `tmp_out/<asset>/stages/validate/report.json`.
5. Add an entry to this catalog and to `EXPECTED_CERTIFY` in
   `tests/unit/test_example_corpus.py`.
