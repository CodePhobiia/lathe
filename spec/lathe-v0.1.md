# Lathe Language Specification v0.1

## 1. Status

**Status:** draft candidate

Lathe is a declarative, end-to-end build language for production-ready 3D assets.

This repository now includes additive V0.8, V0.9, V1.0, V1.1, V1.2, V1.3, V1.3.1, and experimental V0.3 scene-source language/compiler layers on top of the original v0.1 surface. The stable v0.1 asset/build contract remains valid, while newer source can express reusable authoring declarations, source-visible search/repair/material semantics, self-reliant hero-family surface programs and patterns, V1.1 ingestion/reuse flows for adapt, assemble, and structured reconstruct, V1.2 governed surface authoring, V1.3 Blender-backed execution planning, bake/render intent, material-graph bindings, and traceable `.blend` artifacts, V1.3.1 Codex-operated bridge/inspection policy semantics for typed evidence-driven build loops, and a minimal additive scene declaration surface for Wonder readiness.

### In scope for v0.1

- `hard_surface_prop`
- `env_module`
- `mechanical_assembly`

### Out of scope for v0.1

- organic characters
- skinned rigs
- facial rigs
- cloth
- hair or fur
- fluids
- destruction simulation
- custom shader graph languages
- full open-world scene synthesis
- general gameplay scripting

### End-to-end boundary

A single Lathe asset definition is intended to cover:

`refs -> intent -> shape -> topology -> uv -> surface -> rig -> interfaces -> physics -> optimize -> validate -> package -> publish`

---

## 2. Design principles

### 2.1 Declarative first

Lathe source describes what the asset is, how it should be built, and what counts as passing. It does not embed arbitrary user code.

### 2.2 AI-friendly by being regular

Lathe is designed to be easy for AI systems to write, patch, and normalize. That means:

- fixed section order
- canonical defaults
- low ambiguity
- stable ASTs
- semantic patching
- machine-readable diagnostics

### 2.3 Validation is part of the language

A build that does not satisfy its profile and contract is not done.

### 2.4 Profiles and contracts are separate

A **profile** describes downstream platform and pipeline expectations.

A **contract** describes acceptance criteria for an asset family.

### 2.5 Reproducibility by default

Every build should be traceable to its source, refs, backend versions, and repairs.

---

## 3. Source model

Lathe has two equivalent source surfaces:

- text source: `.lth`
- canonical machine form: normalized JSON AST

The text grammar is defined in `grammar/lathe.lark`.

The normalized JSON contract is defined in `schema/lathe.schema.json`.

A conforming implementation should be able to move between these surfaces without changing semantics.

---

## 4. Top-level declarations

Lathe supports these declaration kinds:

- `module`
- `import`
- `profile`
- `contract`
- `critic`
- `library`
- `kit`
- `pattern`
- `family`
- `component`
- `assembly`
- `trait`
- `mechanism`
- `material`
- `surface_program`
- `surface_backend`
- `surface_policy`
- `decal_library`
- `mask_program`
- `trim_sheet`
- `palette`
- `style_pack`
- `reference_set`
- `reconstruct_policy`
- `adapt_policy`
- `assembly_policy`
- `fit_profile`
- `transfer_rule`
- `execution_profile`
- `render_fixture`
- `bake_profile`
- `library_binding`
- `material_graph`
- `inspection_policy`
- `repair_policy`
- `fixture`
- `test`
- `benchmark`
- `space`
- `scene`
- `asset`
- `variant`

Canonical top-level order:

1. `module`
2. `import`
3. `profile`
4. `contract`
5. `critic`
6. `library`
7. `kit`
8. `pattern`
9. `family`
10. `component`
11. `assembly`
12. `trait`
13. `mechanism`
14. `material`
15. `surface_program`
16. `surface_backend`
17. `surface_policy`
18. `decal_library`
19. `mask_program`
20. `trim_sheet`
21. `palette`
22. `style_pack`
23. `reference_set`
24. `reconstruct_policy`
25. `adapt_policy`
26. `assembly_policy`
27. `fit_profile`
28. `transfer_rule`
29. `execution_profile`
30. `render_fixture`
31. `bake_profile`
32. `library_binding`
33. `material_graph`
34. `inspection_policy`
35. `repair_policy`
36. `fixture`
37. `test`
38. `benchmark`
39. `space`
40. `scene`
41. `asset`
42. `variant`

### 4.1 Additive V0.9 source semantics

The additive V0.9 layer introduces these public source concepts without breaking older source:

- typed `family` declarations such as `family brassbound_chest_family: hard_surface_prop`
- asset family instantiation via `asset ... from family_name uses profile_or_contract`
- reusable `pattern` declarations
- reusable `surface_program` declarations
- `search { ... }` as a source alias for the normalized `space` authoring block

These constructs lower into the same normalized AST/runtime pipeline used by earlier source.

### 4.2 Additive V1.1 source semantics

The additive V1.1 layer introduces deterministic asset-system flows without breaking older source:

- `library` declarations for reusable families, components, materials, mechanisms, patterns, and kit rules
- `kit` declarations for modular inventories, joins, snap grids, clearance, and compatibility rules
- `reference_set` declarations for reusable image, mesh, asset, scan, and material references
- `reconstruct_policy`, `adapt_policy`, and `assembly_policy` declarations for flow-specific behavior and allowed repairs
- `fit_profile` declarations for structured reference fitting
- `transfer_rule` declarations for geometry, UV, surface, seam, bake-group, and interface transfer
- asset-local `refs`, `fit`, `transfer`, `reuse`, `constraints`, `ingest`, and `assembly_rules` blocks

V1.1 flows still lower into the same Lathe truth model: resolved asset graph, shape contract, deterministic downstream stages, validation, trace, and package.

### 4.3 Additive V1.2 surface authoring semantics

The additive V1.2 layer makes surface authoring a first-class compiler stage:

- `surface_backend` declares governed texture/map authoring backends such as `lathe.surface.deterministic_pbr_v1` and `lathe.surface.codex_imagegen_v1`
- `surface_policy` declares required maps, allowed authoring backends, resolution, validation, and repair posture
- `decal_library`, `mask_program`, and `trim_sheet` declarations describe reusable surface overlays, masks, and trim inputs
- asset `surface` blocks may reference `backend`, `policy`, `authoring.*`, `decal_libraries`, `mask_programs`, and `trim_sheets`
- hero surface builds emit a Surface Control Pack, Atlas Assembly IR, Surface Validation IR, and Surface Repair IR

Codex ImageGen is optional and subordinate. The reference runtime records the selected/requested backend and falls back deterministically unless a real governed image-generation bridge is available. Image generation never defines mesh, UV, bake, package, or validation truth.

The reference runtime also supports a Codex-operated image generation handoff for local agent workflows. In this mode Lathe emits `lathe.codex_imagegen_request.v1` work orders under the surface stage, Codex fulfills those requests with the built-in `$imagegen` skill, stores the selected bitmap outputs back into the workspace, and Lathe consumes the fulfilled outputs during a later surface build. This mode is intentionally file-based: the Python runtime does not invoke Codex tools directly, and generated images are not considered authoritative until they are present in the workspace and recorded in the surface trace.

### 4.4 Additive V1.3 Blender execution semantics

The additive V1.3 layer keeps Lathe as the public source of truth while adding a Blender-aware execution backplane:

- `execution_profile` declares deterministic execution intent such as `engine = blender`, `mode = background_cli`, backend routing, and `.blend` retention policy
- `render_fixture` declares repeatable render-eval views, passes, lighting style, and resolution
- `bake_profile` declares bake intent such as required maps, target resolution, tangent-space normals, and high/low requirements
- `library_binding` binds Lathe-side component/material abstractions to reproducible Blender asset-library catalogs
- `material_graph` declares backend-agnostic material graph intent that may be lowered into Blender material/node graphs
- assets may include an `execution { ... }` block with `profile` and related overrides
- `build.surface` may reference `bake_profile` and `render_fixture`
- source `surface` may reference `material_graph`

The reference runtime records `ExecutionIR`, `BlenderExecutionIR`, `BakePlanIR`, `RenderEvalIR`, `BlendArtifactIR`, and `LibraryAssetIR` equivalents under the execution stage. When Blender is available, the runtime can retain a generated `.blend` artifact for trace/debug. When Blender is unavailable, the runtime records that fact explicitly and continues on the non-Blender deterministic lane unless strict execution policy requires failure.

### 4.5 Additive V1.3.1 Codex-controlled bridge semantics

The additive V1.3.1 layer formalizes Codex-operated, Lathe-governed Blender execution loops without making Blender artifacts authoritative:

- `inspection_policy` declares the evidence classes that must be gathered before a build may certify under an inspection-enabled execution profile
- execution profiles and asset `execution` blocks may reference `inspection_policy`
- the runtime emits `BridgePlanIR`, `InspectionPolicyIR`, and `ValidationEvidenceIR` equivalents under the execution stage
- the bridge contract preserves Lathe source and normalized AST as the only semantic source of truth
- generated `.blend` files remain artifacts for execution, inspection, debug, cache, and trace
- unsafe arbitrary Blender Python is not exposed as the default autonomous execution path

V1.3.1 adds traceable recovery branch intent across `reselect_candidate`, `repair_candidate`, `regenerate_candidate`, and `patch_source`. A `patch_source` branch may be proposed by tooling, but persistent semantic changes must still round-trip through Lathe source.

### 4.6 Phase 13 Experimental Asset-Quality Syntax (additive)

Phase 13 adds an OPTIONAL `experimental { ... }` wrapper inside an asset. The stable public surface (`profile`, `contract`, `critic`, `asset`, `variant`, build-stage names) is unchanged. The wrapper is the explicit gating mechanism: without it, none of the Phase 13 sub-blocks parse, and there is exactly one place to remove the surface later.

#### Stability promise

- Experimental syntax is allowed to change between minor versions. The stable public surface listed above does not change as a side effect.
- Existing examples that omit the wrapper continue to parse, normalize, resolve, check, and build identically.
- Sub-blocks inside `experimental { }` are NOT defaulted by the normalizer — only present when the user wrote them.

#### MVP sub-blocks

```lathe
experimental {
  art_direction {
    style_tags = ["weathered_industrial", "well_used"]
    wear = "heavy"
    material_age = "aged"
    detail_density = "high"
  }
  references {
    use = "refs/asset_quality/industrial_crate"
  }
  kit {
    use = ["fasteners.hex_bolt_m6", "rails.foot_rail_bar"]
  }
}
```

- `art_direction { ... }` overrides the design-brief defaults for the four whitelisted fields above (Phase 2 brief). Unspecified fields keep the family default.
- `references { use = "<path>" }` overrides the convention-based reference-board base path (Phase 11 fixtures). The path resolves relative to the source `.lth` file.
- `kit { use = [<part>, ...] }` declares hard-surface kit parts (Phase 12 library) the asset intends to use. Each entry uses the `<category>.<name>` format and must be allowed for the materialized asset family by the kit part's `allowed_families` metadata. The declaration is informational evidence; the loaded library is not filtered by it.

#### Diagnostics

- `L7100 — experimental_unknown_subblock`: a sub-block name other than `art_direction`, `references`, or `kit`.
- `L7101 — experimental_art_direction_unknown_field`: a field outside the four-field MVP whitelist.
- `L7102 — experimental_art_direction_invalid_value`: a field value of the wrong type (e.g. `wear: 42`).
- `L7103 — experimental_references_invalid_path`: `references.use` is not a string or does not resolve to an existing directory.
- `L7104 — experimental_kit_unknown_part`: an entry that is not present in the loaded kit library (warning when the library can't be loaded).
- `L7105 — experimental_kit_invalid_format`: an entry that is not a string in `<category>.<name>` format, or `kit.use` is not a list.

- `L7106 - experimental_kit_disallowed_family`: an entry exists but its `allowed_families` excludes the materialized asset family.

Each diagnostic carries actionable `suggested_repairs` so authors and LLM-based authors can repair from evidence alone.

#### Migration notes

- Pre-Phase-13 sources continue to work without modification.
- Phase 13 does NOT add a new top-level validate report key. User opt-in surfaces as `user_provided_via_experimental` annotations inside the existing `design_brief`, `reference_board`, and `kit_library` evidence sections.
- Future sub-blocks (`construction { ... }`, `material_graph { ... }`) are reserved for forward phases. They will land additively under the same `experimental { }` wrapper.

### 4.7 Experimental v0.3 Scene Source Syntax

The experimental V0.3 scene layer adds a first-class top-level `scene` declaration without changing asset semantics. Scene source is additive: existing `asset` and `variant` declarations continue to parse, normalize, resolve, check, plan, and build through the asset compiler. Asset planners ignore `scene` declarations until a scene-specific planning command is invoked.

Minimum viable scene syntax:

```lathe
style_pack dead_god_observatory {
  display_name = "Dead God Observatory"
  source.kind = curated
  palette.primary = bone_ivory
  palette.secondary = oxidized_copper
}

scene alchemist_observatory {
  version = 1
  brief = "A forgotten alchemist observatory inside the ribcage of a dead god."
  prompt = "A forgotten alchemist observatory inside the ribcage of a dead god."

  style style_dead_god_observatory {
    style_pack = dead_god_observatory
    mood = "sacred, eerie, antique"
    palette = [bone_ivory, oxidized_copper, black_glass, candle_gold]
  }

  region region_central_chamber: interior {
    purpose = "main reveal space"
  }

  object obj_astrolabe_table: hero_prop from ornate_table {
    region = region_central_chamber
    material = oxidized_brass
    gameplay {
      interactable = true
      collision = box
      pivot = base_center
      affordances.inspect_lens.action = inspect
      affordances.inspect_lens.reveals = hidden_warm_lens_truth
    }
  }

  object obj_rib_arches: environment_structure from bone_architecture {
    region = region_central_chamber
  }

  relationship rel_astrolabe_under_arches: frames {
    from = obj_rib_arches
    to = obj_astrolabe_table
  }

  camera_intent camera_reveal: cinematic_wide {
    target = obj_astrolabe_table
  }

  lighting_plan light_moonbeam: moonbeam {
    target = obj_astrolabe_table
  }

  curiosity_anchor curiosity_warm_lens {
    attached_to = obj_astrolabe_table
    visible_clue = "The black glass lens is still warm."
    hidden_fact = "The lens still tracks a living star."
    suggested_user_actions = [inspect_lens, align_astrolabe]
    expansion_options.hidden_star_map.label = "Hidden Star Map"
    expansion_options.hidden_star_map.target_scope = obj_astrolabe_table
  }

  hidden_state hidden_warm_lens_truth {
    attached_to = obj_astrolabe_table
    fact = "The lens is warm because it tracks a living star."
    reveal_condition = "User inspects the lens."
    visible = false
  }

  export glb {
    path = "exports/alchemist_observatory.glb"
  }
}
```

Top-level `style_pack` declarations are normalized as mapping declarations in
the `style_packs` collection. A scene-local `style` block may reference a
declared style pack or curated built-in style pack with `style_pack = <id>`.
This source-level declaration is intentionally lighter than the JSON
`lathe.style_pack.v1` contract; the full Style Pack JSON remains the durable
contract for palette tokens, material PBR metadata, lighting presets,
fingerprints, and reuse policy.

The normalized scene declaration contains stable child collections for `styles`, `regions`, `objects`, `relationships`, `cameras`, `lights`, `curiosity_anchors`, `hidden_state`, and `exports`. Scene-local IDs should use the current contract prefixes: `region_`, `obj_`, `rel_`, `camera_`, `light_`, `curiosity_`, and `hidden_`. `camera_intent` lowers to normalized `scene_camera` records and `lighting_plan` lowers to normalized `scene_light` records; legacy `camera` and `light` blocks remain accepted as compatibility aliases for the same IR. Object-local `gameplay { ... }` blocks lower into the object's `values.gameplay` metadata map and are intended for game-readiness hints such as `interactable`, `collision`, `pivot`, `tags`, and `affordances.<id>.*`. `curiosity_anchor` and `hidden_state` blocks lower to normalized `scene_curiosity_anchor` and `scene_hidden_state` records whose field values remain in the child `values` map until Scene Graph lowering consumes them. The checker validates duplicate scene-local IDs, verifies scene style-pack references, and verifies object region references plus relationship, camera, light, curiosity-anchor, and hidden-state targets against the scene-local ID set. Object `from` references are intentionally not required to name an in-file asset yet; the scene build pipeline may resolve them through Scene Graph, family, kit, or later materialization contracts.

Deferred beyond the minimal V0.3 source surface:

- standalone game-readiness payload source syntax
- sockets, snap points, and detailed collision metadata outside object gameplay metadata
- provenance source syntax
- advanced layout constraints
- scene variants and branch/merge syntax

---

## 5. Lexical rules

### 5.1 Encoding

Source files are UTF-8.

### 5.2 Identifiers

Plain identifiers match:

```text
[a-z][a-z0-9_]*
```

Qualified identifiers are dot-separated identifiers.

Examples:

```text
courier_drone
studio.props.drones
```

### 5.3 Comments

Lathe supports:

```text
// line comment
/* block comment */
```

### 5.4 Literals

Supported literal kinds:

- strings
- integers
- floats
- booleans
- unit literals
- lists
- ranges

Examples:

```lathe
"courier drone"
42
0.86
true
2048px
32mb
0..1
[usd, glb, fbx]
```

### 5.5 Units

Supported core unit suffixes in v0.1:

- length: `mm`, `cm`, `m`
- angle: `deg`, `rad`
- mass: `g`, `kg`
- time: `ms`, `s`
- memory: `kb`, `mb`, `gb`
- pixels: `px`
- density: `px_per_m`, `px_per_cm`

---

## 6. Core types

Primitive categories:

- `bool`
- `int`
- `float`
- `string`

Dimensional categories:

- `length`
- `angle`
- `mass`
- `duration`
- `memory`
- `pixels`
- `density`

Domain categories:

- `profile_ref`
- `contract_ref`
- `critic_ref`
- `asset_ref`
- `backend_ref`
- `repair_op`
- `score`

`score` is a float in `[0, 1]`.

---

## 7. Profiles

A profile is a reusable target for pipeline and platform requirements.

Profiles may contain:

- `defaults`
- `ensure`
- `prefer`
- `repair`

Profiles may use other profiles.

Profiles may not use contracts.

Profiles may assign defaults under:

- `build.*`
- `package.*`
- `publish.*`
- `validate.repair.*`
- `x_*`

Profiles may not assign:

- `refs.*`
- `intent.*`
- `validate.score`
- `validate.threshold`
- `name`
- `kind`

---

## 8. Contracts

A contract is a reusable acceptance contract for an asset family.

Contracts may contain:

- `defaults`
- `ensure`
- `prefer`
- `repair`

Contracts may use profiles and other contracts.

Contracts may assign defaults under:

- `intent.*`
- `build.*`
- `package.*`
- `publish.*`
- `validate.repair.*`
- `x_*`

Contracts may not assign:

- `refs.*`
- `validate.score`
- `validate.threshold`
- `name`
- `kind`

---

## 9. Critics

A critic is a pure scoring function over an asset.

Critics must:

- be side-effect free
- return a score in `[0, 1]`
- not mutate build state

Weighted critics normalize their weights to sum to `1.0`.

Example:

```lathe
critic hero_prop(a: asset) = weighted {
  prompt_match 0.25
  silhouette_readability 0.15
  topology_quality 0.20
  material_quality 0.15
  runtime_efficiency 0.10
  part_coherence 0.15
}
```

---

## 10. Assets

An asset is the main end-to-end declaration.

Header form:

```lathe
asset courier_drone: mechanical_assembly uses shipping_prop { ... }
```

### 10.1 Asset sections

Canonical section order:

1. `refs`
2. `intent`
3. `geometry`
4. `features`
5. `surface`
6. `assembly`
7. `fit`
8. `transfer`
9. `reuse`
10. `constraints`
11. `ingest`
12. `assembly_rules`
13. `execution`
14. `space`
15. `repair_policy`
16. `build`
17. `validate`
18. `package`
19. `publish`
20. `experimental` (Phase 13, optional, opt-in)

### 10.4 Source-visible authoring blocks

Assets may now include:

- `geometry`
- `features`
- `surface`
- `assembly`
- `fit`
- `transfer`
- `reuse`
- `constraints`
- `ingest`
- `assembly_rules`
- `space`
- `repair_policy`

These blocks are lowered into the existing build/runtime pipeline without changing the stable public shape backend id `lathe.shape.intent_mesh_handoff_v1`.

### 10.2 Required intent field

`intent.role` is required.

### 10.3 Scale rule

`intent.scale` and `intent.dimensions` are mutually exclusive.

### 10.4 Shape mode constraints

If `build.shape.mode` is:

- `generate`: refs are optional
- `reconstruct`: `refs.images`, `refs.meshes`, or a `reference_set` resolving to those inputs must be non-empty
- `adapt`: `refs.meshes` or `refs.assets` must be non-empty
- `assemble`: `refs.assets` or a resolved `kit` must be non-empty

---

## 11. Variants

A variant derives from an asset or another variant using semantic patches.

Example:

```lathe
variant courier_drone_mobile on courier_drone {
  append uses = mobile_runtime
  set build.surface.resolution = 2048px
  set build.optimize.texture_budget = 16mb
}
```

Supported patch operations:

- `set`
- `append`
- `remove`
- `unset`

Variants may modify `uses`.

Variants may not modify `kind`.

Variants may not patch `name`.

Resolution model:

1. clone the base source asset
2. apply patches in order
3. run normalization, resolution, and validation again

---

## 12. Asset schema

### 12.1 `refs`

Canonical fields:

- `images`
- `meshes`
- `assets`
- `materials`
- `reference_sets`
- `notes`

### 12.2 `intent`

Canonical fields:

- `role`
- `style`
- `parts`
- `materials`
- `negatives`
- `scale`
- `dimensions`
- `interactions`
- `notes`

### 12.3 `build`

Canonical stage order:

1. `shape`
2. `topology`
3. `uv`
4. `surface`
5. `rig`
6. `interfaces`
7. `physics`
8. `optimize`

### 12.4 `validate`

Canonical fields:

- ordered `ensure` rules
- ordered `prefer` rules
- `score`
- `threshold`
- `repair`

### 12.5 `package`

Canonical fields:

- `formats`
- `manifest`
- `previews`
- `embed_textures`
- `include_trace`
- `naming`
- `game_asset_manifest`
- `manifests`

### 12.6 `publish`

Canonical fields:

- `registry`
- `version`
- `tags`
- `visibility`
- `approval`
- `channel`

### 12.7 V1.2 `surface` authoring fields

Canonical additive fields:

- `backend`
- `policy`
- `authoring.backend`
- `authoring.mode`
- `authoring.generate`
- `authoring.derive`
- `decal_libraries`
- `mask_programs`
- `trim_sheets`

Hero surface builds should emit:

- `surface_control_pack`
- `atlas_assembly_ir`
- `surface_validation_ir`
- `surface_repair_ir`
- `surface_backend_report`

### 12.8 V1.3 execution and surface fields

Canonical additive asset fields:

- `execution.profile`
- `execution.engine`
- `execution.mode`
- `execution.preserve_blend`
- `execution.geometry_backend`
- `execution.uv_backend`
- `execution.bake_backend`
- `execution.surface_backend`
- `execution.render_backend`
- `execution.package_backend`
- `execution.library_backend`
- `execution.library_bindings`
- `execution.inspection_policy`
- `surface.material_graph`
- `build.surface.bake_profile`
- `build.surface.render_fixture`

V1.3 execution-aware builds should emit:

- `execution_ir`
- `blender_execution_ir`
- `bake_plan_ir`
- `render_eval_ir`
- `blend_artifact_ir`
- `library_asset_ir`

### 12.9 V1.3.1 bridge and inspection fields

Canonical additive execution fields:

- `execution.inspection_policy`
- `execution.resolved_inspection_policy`

V1.3.1 execution-aware builds should emit:

- `bridge_plan_ir`
- `inspection_policy_ir`
- `validation_evidence_ir`

---

## 13. Build stage defaults

### 13.1 `shape`

Defaults:

- `backend = auto`
- `mode = generate`
- `candidates = 4`
- `seed = auto`
- `symmetry = none`
- `preserve = []`

Additive geometry/detail authoring controls may be supplied in the same
`shape` block. They are optional and lower into the stable
`lathe.shape.intent_mesh_handoff_v1` scaffold contract as generated detail
parts, feature metadata, and downstream pipeline hints. Supported controls
include:

- density and edge controls: `detail_density`, `edge_complexity`,
  `edge_treatment`, `edge_hardness`, `bevel_width`, `chamfer_width`
- surface form controls: `panelization`, `groove_density`, `ridge_density`,
  `trim_density`, `inset_depth`, `outset_depth`, `surface_layer_count`
- repeated detail and attachment controls: `linear_detail_repeats`,
  `radial_detail_repeats`, `detail_array_axis`, `modular_attachment_points`,
  `module_sockets`, `module_categories`, `module_count`,
  `attachment_motifs`, `attachment_count`
- art-directed construction controls: `detail_motifs`, `detail_zones`,
  `style_pack`, `style_packs`, `style_intensity`, `style_modifiers`,
  `silhouette_profile`, `silhouette_motifs`, `silhouette_intensity`
- game-pipeline controls: `lod_levels`, `highlow_mode`, `highlow_low_lod`,
  `highlow_bake_cage_offset_cm`, `collision_proxy`, `export_profiles`

Fields prefixed with `zone_` define named detail-zone overrides; for example
`zone_door_module_categories = [vent, latch]` and
`zone_door_module_count = 3` concentrate motifs on the named part/zone.

### 13.2 `topology`

Defaults:

- `backend = auto`
- `retopo = auto`
- `ngons = avoid`
- `preserve = []`

### 13.3 `uv`

Defaults:

- `backend = auto`
- `sets = [base]`
- `unwrap = auto`
- `tile_mode = zero_to_one`
- `padding = 8px`
- `pack_rotate = true`
- `udims = []`

Additive game-asset organization controls:

- `chart_grouping`: semantic chart grouping strategy. Supported values are
  `part`, `material`, `material_zone`, `part_material`, `detail_zone`, and
  `zone`.
- `material_id_strategy`: material-ID layout strategy. `per_material_zone`
  emits deterministic material IDs, per-part assignments, and stable ID
  colors for downstream masks/previews.
- `texture_set_strategy`: optional texture-set organization hint, such as
  `hero_surface_sets`, for atlas/control-pack consumers.
- `layout_strategy` / `atlas_layout`: optional atlas layout label. The
  deterministic reference UV path currently records this as metadata while
  packing charts with the built-in grid.
- `island_naming`: semantic island-name policy. Defaults to `semantic`.
- `preserve_detail_zones`: when true, asks the UV organization layer to keep
  named detail zones distinct when using `detail_zone`/`zone` grouping.

UV builds should emit `uv_organization`, `chart_manifest`, and
`material_id_layout` metadata when these controls or `surface.id_map` are
requested.

### 13.4 `surface`

Defaults:

- `backend = auto`
- `workflow = pbr_metal_rough`
- `maps = [basecolor, normal, orm]`
- `resolution = 2048px`
- `bakes = []`
- `decals = []`
- `id_map = false`

Additive surface-story authoring controls may be supplied in the asset
`surface` block:

- `story_decals`, `faction_marks`, and `markings`: decals/labels/symbols
  that should be painted into the generated surface maps.
- `story_targets`, `decal_targets`, or `story_regions`: preferred part/zone
  targets for those marks.
- `story_density` / `decal_density`: density label for placement metadata.
- `story_asymmetry` / `asymmetry`: placement bias such as `left`, `right`, or
  `hero_asymmetric`.

Surface builds should emit `surface_story_placement_plan` metadata when
decals or story marks are present. Hero surface builds use that plan to place
labels, scratches, warning bars, heat marks, and other story decals at
deterministic UV anchors.

### 13.5 `rig`

Defaults:

- `backend = auto`
- `type = none`
- `joints = []`
- `pivot_policy = auto`
- `joint_limits = auto`

### 13.6 `interfaces`

Defaults:

- `backend = auto`
- `sockets = []`
- `pivots = []`
- `anchors = []` (legacy compatibility)

Typed interface entries should use constructor calls in source:

- `sockets = [socket(id: power_socket, socket_type: port)]`
- `pivots = [pivot(id: floor_contact, pivot_type: contact)]`

Legacy bare socket names and `anchors = [...]` remain accepted for older
sources, but canonical examples declare typed sockets and pivots explicitly.

### 13.7 `physics`

Defaults:

- `backend = auto`
- `collision = none`
- `max_hulls = 10`
- `mass = auto`
- `center_of_mass = auto`

### 13.8 `optimize`

Defaults:

- `backend = auto`
- `lods = 1`
- `atlas = false`
- `mesh_compression = false`
- `strip_hidden_faces = false`
- `instance_candidates = false`

### 13.9 `package`

Defaults:

- `backend = auto`
- `formats = []` (normalizes to `[usd, glb]` when omitted)
- `manifest = true`
- `previews = []`
- `embed_textures = false`
- `include_trace = true`
- `naming = auto`

Additive game-pipeline manifest controls:

- `game_asset_manifest = true` emits `stages/package/game_asset_manifest.json`.
- `manifests = [game_asset_manifest]` is an equivalent opt-in form.

The game asset manifest collects the package outputs, texture outputs, LODs,
high/low relation, collision hints, sockets/pivots/anchors, material zones,
material-ID layout, UV organization, chart manifest, and surface-story
placement plan into one downstream-consumable artifact.

---

## 14. Merge and resolution

### 14.1 Use graph order

`uses` resolution is depth-first, left-to-right, post-order.

### 14.2 Effective precedence

For a concrete asset build, effective values are applied in this order:

1. language defaults
2. profile defaults
3. contract defaults
4. explicit asset values
5. variant patches

### 14.3 Rules

The effective validation rule list is the concatenation of:

1. profile rules
2. contract rules
3. asset-local validation rules

### 14.4 Repair policy

Repair policy merges as:

- `mode`: most specific explicit value wins
- `max_rounds`: most specific explicit value wins
- `allow`: union
- `deny`: union
- effective permitted set: `allow - deny`

---

## 15. Build semantics

### 15.1 Logical DAG

```text
shape -> topology -> uv -> surface -> optimize
           \-> rig -> interfaces -> physics -> optimize
```

Validation runs after `optimize`.

Packaging runs after validation.

Publishing runs after packaging.

### 15.2 Candidate selection

If `shape.candidates > 1`, the runtime selects candidates using:

1. explicit critic if present
2. implicit critic synthesized from `prefer`
3. backend heuristics otherwise

### 15.3 Cache model

Each stage output should be cacheable from:

- normalized source hash
- refs hashes
- backend identity and version
- relevant upstream outputs
- stage config
- seed when applicable

---

## 16. Validation and repair

### 16.1 Certification

An asset is certified only if:

- all `ensure` rules pass
- effective score is `>= threshold`

### 16.2 `prefer`

`prefer` guides optimization and repair planning.

If no explicit critic exists, `prefer` rules synthesize the effective score.

### 16.3 Explicit critic

If `validate.score` is present, it defines certification scoring.

### 16.4 Repair loop

If validation fails and automatic repair is allowed, the runtime should:

1. gather diagnostics
2. gather suggested repair ops
3. filter by repair policy
4. choose a repair plan
5. invalidate affected stages
6. rebuild affected stages
7. validate again
8. stop on pass or `max_rounds`

### 16.5 Protected intent

Repair must not violate:

- `intent.role`
- `intent.parts`
- `intent.negatives`
- active preserve settings

---

## 17. Standard predicates and metrics

Required predicate family examples:

- `manifold`
- `watertight`
- `symmetry(...)`
- `triangles(...)`
- `uv_range(...)`
- `lightmap_uvs`
- `material_slots(...)`
- `riggable(...)`
- `collision_proxy`
- `runtime_budget(...)`
- `lods(...)`
- `units(...)`

Required metric family examples:

- `prompt_match`
- `silhouette_readability`
- `topology_quality`
- `uv_quality`
- `material_quality`
- `runtime_efficiency`
- `part_coherence`
- `assembly_compatibility`
- `surface_consistency`

Additive V1.1 flow metrics include:

- Adapt: `semantic_preservation_quality`, `profile_retarget_quality`, `transfer_integrity`
- Assembly: `join_legality`, `assembly_clearance_quality`, `module_coherence`, `assembly_surface_continuity`
- Reconstruct: `family_fit_confidence`, `component_fit_confidence`, `measurement_consistency`, `reconstruct_honesty_score`

---

## 18. Repair ops

Required repair op families in v0.1 include:

- `reselect_candidate`
- `rebuild_shape`
- `enforce_symmetry`
- `seal_mesh`
- `remove_self_intersections`
- `retopo_auto`
- `reduce_tris`
- `recalculate_normals`
- `repack_uvs`
- `regenerate_lightmap_uvs`
- `merge_material_slots`
- `rebake_maps`
- `retexture`
- `normalize_pivots`
- `rebuild_interfaces`
- `create_collision_proxy`
- `recenter_mass`
- `generate_lods`
- `atlas_textures`

---

## 19. Diagnostics

Diagnostics must be machine-readable.

Minimum fields:

- `code`
- `name`
- `severity`
- `phase`
- `asset`
- `stage`
- `path`
- `message`
- `details`
- `suggested_repairs`

Severity values:

- `error`
- `warning`
- `info`

Phase values:

- `parse`
- `resolve`
- `typecheck`
- `build`
- `validate`
- `package`
- `publish`

Example diagnostic families:

- use cycle
- incompatible units
- missing reconstruct input
- non-manifold region
- draw call budget exceeded
- missing collision proxy
- approval required

---

## 20. Packaging and publishing

### 20.1 Package manifest

A packaged asset should include:

- exported files
- manifest
- normalized source or canonical JSON
- previews if requested
- trace if requested

### 20.2 Trace manifest

A trace should include:

- source hash
- compiler version
- backend versions
- refs hashes
- resolved uses
- stage configs
- candidate selection
- repairs applied
- diagnostics
- output hashes
- approval state

### 20.3 Publish rule

Publishing should be refused unless:

- certification passed
- packaging succeeded
- approval requirements are satisfied

---

## 21. Backend contract

Every backend should declare:

- `id`
- `version`
- `supported_stages`
- `determinism_class`
- `supported_extensions`
- `supported_repair_ops`
- `input_schema_version`
- `output_schema_version`

Backends may fuse internal steps, but they must still expose logical Lathe stage outputs.

---

## 22. Toolchain commands

A conforming toolchain should expose these verbs:

- `fmt`
- `test`
- `bench`
- `normalize`
- `check`
- `plan`
- `build`
- `audit`
- `repair`
- `diff`
- `patch`
- `publish`

The reference scaffold in this repository currently implements:

- `parse`
- `fmt`
- `normalize`
- `schema`
- `check`
- `plan`
- `test`
- `bench`
- `patch`
- `materialize`
- `build`
- `probe-blender`
- `export-blend`
- `inspect-blend`
- `render-eval`
- `library sync`
- `bridge doctor`
- `bridge plan`
- `inspect`
- `render-fixture`
- `bake-audit`

---

## 23. Example

```lathe
profile unreal_interactable_prop {
  defaults {
    build.optimize.lods = 4
    package.formats = [usd, glb, fbx]
  }

  ensure units(cm)
  ensure manifold
  ensure watertight
}

contract shipping_prop uses unreal_interactable_prop {
  ensure runtime_budget(draw_calls: 3, texture_memory: 32mb)
  prefer silhouette_readability weight 0.3
}

asset courier_drone: mechanical_assembly uses shipping_prop {
  intent {
    role = "last-mile courier drone"
    parts = [body, rotor_fl, rotor_fr, rotor_rl, rotor_rr, cargo_door]
    scale = 0.9m
  }

  build {
    shape {
      mode = generate
      candidates = 12
      symmetry = x
    }

    rig {
      type = rigid_mechanical
      joints = [rotor_fl, rotor_fr, rotor_rl, rotor_rr, cargo_door]
    }
  }
}
```

---

## 24. v0.1 implementation stance

The reference scaffold in this repository deliberately prioritizes the compiler contract over flashy generation.

That is the right order.

If the contract is weak, every backend produces impressive garbage.

If the contract is strong, every backend plugs into a production system.

---

## 20. Reference backend stack wired into the scaffold

The reference compiler scaffold now includes one builtin backend stack for the v0.1 asset classes.

### 20.1 Stack id

`lathe.stack.hard_surface_game_asset_v1`

### 20.2 Bound stages

- `shape` -> `lathe.shape.intent_mesh_handoff_v1`
- `topology` -> `lathe.topology.blender_hard_surface_v1`
- `uv` -> `lathe.uv.xatlas_v1`
- `package` -> `lathe.package.openusd_gltf_v1`

### 20.3 Intent of the split

This stack intentionally isolates the most probabilistic stage to `shape` and keeps downstream productionization deterministic.

That means:

- mesh candidate generation remains a pluggable AI boundary
- topology cleanup and retopo are normalized behind one deterministic contract
- UV layout is normalized behind one deterministic contract
- packaging is normalized behind one deterministic contract

### 20.4 Package backend field

The scaffold now treats `package.backend` as a valid backend selection field.

If omitted, normalization inserts:

```lathe
package {
  backend = auto
}
```

### 20.5 Compiler behavior

For `backend = auto`, the planner selects the first builtin stack whose stage contracts satisfy the effective asset configuration.

The checker must emit an error when:

- an explicit backend id is unknown
- an explicit backend is bound to the wrong stage
- a stage configuration violates the selected backend contract
- no builtin stack can satisfy the asset configuration

### 20.6 First-stack UV constraints

The first wired UV backend is intentionally narrow. It supports:

- `tile_mode = zero_to_one`
- `unwrap = auto`
- UV sets using `base` and optional `lightmap`

It does not support UDIMs in the first stack.

### 20.7 First-stack package formats

The first wired package backend supports:

- `usd`
- `usdz`
- `glb`
- `gltf`
- `fbx`
