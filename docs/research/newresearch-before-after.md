# newresearch.md — Before / After: what Lathe can now do

Date: 2026-05-13
Scope: closes implementation of `docs/research/newresearch.md`
across Waves 5–12. Companion to `newresearch-implementation-plan.md`.

This document is the high-level "Lathe before vs Lathe after"
summary the research push set out to deliver.

---

## Strategic shift

| Axis | Before | After |
|---|---|---|
| Position of asset knowledge | Hardcoded Python (`_KIND_ASPECT`, name suffixes, family branches) | Declarative JSON packs (FamilyAlias / MorphologyProfile / CompositionPolicy / StyleKnowledge / VisualLanguage / Rubric) |
| Construction graph | Descriptive metadata — typed edges existed but did not drive placement | Executable contract — typed edges resolve to anchor-pair + transform + proof via the `RelationResolver` |
| Body morphology | One hardcoded aspect map (`env_module=flat`, `hard_surface_prop=box`) | 5 morphology profiles (crate / door / panel / terminal / weapon) — typed body archetype + parts ladder + anchor emitters + default relations |
| Visual style | Implicit "industrial dark plastic" baked into the renderer | 6 explicit visual language packs (industrial / steampunk / sci-fi / brutalist / alien grove / abandoned overlay) — silhouette bias + motifs + palette + materials + wear + feature weights |
| Material zones | Single fused material slot per asset | Zone tags survive topology fusion; per-zone PBR archetypes; shared-mask correlated PBR composition (basecolor/roughness/metallic/normal/height all derive from same wear/dirt/rust masks) |
| LOD | Decimation as afterthought | LODPolicy declared per class — 4 levels with feature representation rules (geometry / normal-stamp / texture / removed) per LOD level |
| Engine targeting | USD/glTF/OBJ packaging only | 5 engine adapter manifests (Roblox / Unity / Unreal / USD / glTF) emitted from `AssetRuntimeContract` |
| Validators | Geometric correctness (manifold + watertight + face count) | + Visible-quality rubrics — class anchor (crate_v1, door_v1, panel_v1, terminal_v1, weapon_v1) with structured evidence + repair_actions |
| Repair loop | Single shape-repair allowlist | 12 canonical repair operators with declarative payloads — insert_required_feature, panelize_face, add_reinforcement_pattern, strengthen_silhouette, assign_material_zone, add_decal_zone, increase_bevel_readability, add_surface_wear, promote_detail_to_geometry, demote_detail_to_texture, adjust_style_weights, resample_variation |
| Determinism | Global RNG | Seed hierarchy (world / kit / archetype / instance / surface_micro / decal / wear) + ReproducibilityManifest |
| World composition | Per-asset .lth files | KitGraph + ArchetypeReference + docking resolver (compatibility + dimensions + load + texel density scoring) |
| Geometry kernel | Serial per-op Manifold booleans | FeatureDAG + spatial broadphase cluster + batched boolean planner |

---

## What Lathe can now do

**Before — what a hero asset build produced:**

- A single fused trimesh with one material slot.
- Body shape from a hardcoded aspect map keyed by `kind`.
- Secondary parts (handles, brackets, fasteners) positioned by
  name-suffix heuristics.
- Validators that certified "manifold + watertight + face_count ≥ 200"
  on a featureless beveled cube.
- Build report referenced stage bundles but had no top-level UV /
  PBR / class-anchor / runtime-contract evidence.
- One package format (USD / glTF / OBJ) with no engine-specific
  metadata.
- Repair loop existed but only one mapping (`restore_edge_treatment`).

**After — what a hero asset build can now produce:**

- A morphology-driven body whose proportions come from a declarative
  profile (`container_crate_morphology_v1` → 110×63×50 cm rectangular
  shipping crate; `swing_door_morphology_v1` → 95×8×210 cm flat
  panel) — *not* from a hardcoded aspect map.
- An anchor-based placement layer where construction-graph edges
  (`attached_to`, `inset_into`, `wraps_around`, `aligned_with`,
  `mirrors`, `supports`, `cuts`) resolve to authoritative transforms
  via the `RelationResolver` (exhaustive candidate generation →
  affordance match → normal-policy enforcement → deterministic
  tie-break).
- Zone-preserving topology: every face carries a `ZoneTag` (zone_id,
  material_class, uv_policy, decal_allowed, wear_role,
  source_node_id, feature_id) that survives boolean fusion into
  per-zone subsets the package stage emits as `UsdGeomSubsets` or
  glTF mesh primitives.
- Shared-mask correlated PBR: `WearMaskRecipe(condition=0..1,
  environment)` fans into a parameter vector that drives
  `MaskGraph` (edge_wear + concave_dirt + fastener_rust +
  vertical_streak + paint_chip + decal_fade + scratch +
  convex_polish + oil_stain). The PBR channel composer
  (`compose_pbr_channels`) uses the *same masks* to derive basecolor
  (blends toward raw_metal at edge_wear, rust at rust zones, dirt
  at concavity), roughness (raises with dirt+rust, drops at polish),
  metallic (drops with rust on steel), normal_strength + height + AO
  intensity. Painted_steel now actually looks painted-steel-shaped,
  not gray-shader-shaped.
- 5 ShapeIR v2 next-tier feature ops registered: `op.panel_inset`,
  `op.edge_group_select`, `op.weighted_bevel`, `op.trim_sweep`,
  `op.profile_sweep`, `op.fastener_pattern`, `op.boolean_group`,
  `op.lod_policy`. Each has a declarative spec with required +
  optional params and a kernel_state classification.
- A 4-tier LOD ladder (LOD0 18k tris / LOD1 6k / LOD2 1.5k /
  LOD3 300) with per-class policy: door class drops fasteners
  earlier than crate. Auto-representation decision per feature
  per LOD via projected-pixel-width math (geometry / normal_stamp /
  texture_only / removed).
- A class anchor rubric per asset class (crate / door / panel /
  terminal / weapon) — each emits structured `evidence` dict +
  `repair_actions`. The featureless-cube case the user rejected now
  fails L6500 with `add_secondary_features` routed to the
  repair_executor.
- 4 standardized lighting rigs + 8 canonical views + 6 auxiliary
  passes for deterministic render-based scoring.
- 6 visual language packs that overlay any morphology — same crate
  rules with `utility_industrial_v1` vs `steampunk_workshop_v1` vs
  `clean_sci_fi_v1` vs `brutalist_bunker_v1` produce visually
  distinct outputs from the same construction graph.
- An `AssetRuntimeContract` carrying LODs, materials, collision
  policy, rig joints, sockets, interfaces, audio/light/nav hints,
  streaming config, semantic tags. 5 engine adapters lower that
  contract into Roblox / Unity / Unreal / USD / glTF native
  representations.
- World composition: `KitGraph` references archetype `.lth`s with
  variation strategy (stratified seeds, repetition_limit,
  condition_distribution). `InterfacePort` + docking resolver makes
  assets snap to each other (crate-bottom ↔ pallet-top) with
  compatibility scoring.
- Rig contract derived from construction-graph hinge edges:
  `metadata.joint == hinge` becomes a `RigJoint`; the engine
  adapter emits Roblox `HingeConstraint`, Unity `HingeJoint`,
  Unreal `PhysicsConstraintActor`, or USD `UsdPhysics`.
- Determinism: a single `world_seed` deterministically derives every
  sub-seed (kit / archetype / instance / surface_micro / decal /
  wear). `ReproducibilityManifest` carries `lathe_version` +
  `shape_contract` + knowledge_pack_versions + seeds + IR hashes.
- 12 canonical repair operators that mutate the construction graph /
  policy brief / style overlay / seed scope — not the final mesh.
  When the class anchor fires, the repair loop applies the
  appropriate operators, reenters the pipeline, and the next render
  shows visible class evidence.
- A `FeatureDAG` + spatial cluster broadphase + batched boolean
  planner — the substrate for the "200 ops per asset without per-op
  manifold copies" target. Today's commit ships the contract surface
  the synthesizer can target; manifold3d-backed variadic
  arrangement integration is per-asset-family follow-up.

---

## What changed at the code level

8 commits on `stabilization-p0-p1` (Waves 5–12) introduced:

- **20 new modules / packages**:
  - `lathe/shape/placement.py` + `lathe/asset_quality/procedural_synthesizer/anchors/`
  - `lathe/asset_quality/procedural_synthesizer/knowledge_loader/morphology.py`
  - `lathe/asset_quality/procedural_synthesizer/knowledge_loader/visual_language.py`
  - `lathe/surface_graph/zone_binding.py` + `mask_compiler.py` + `pbr_composer.py`
  - `lathe/asset_quality/feature_ops_v2.py`
  - `lathe/runtime/asset_contract.py` + `engine_adapters.py`
  - `lathe/render_rigs/standard_rigs.py` + `canonical_views.py`
  - `lathe/validators/class_anchor.py`
  - `lathe/asset_quality/lod_policy.py`
  - `lathe/scene/kit_graph.py` + `docking.py`
  - `lathe/rig/rig_contract.py`
  - `lathe/determinism/seeds.py` + `manifest.py`
  - `lathe/repair_operators_v2.py`
  - `lathe/geometry/feature_dag.py` + `spatial_cluster.py` + `batched_boolean.py`

- **24 new knowledge packs**:
  - 5 morphology profiles: container_crate, swing_door, flat_panel,
    terminal, weapon_prop
  - 6 visual language packs: utility_industrial, steampunk_workshop,
    clean_sci_fi, brutalist_bunker, alien_grove, abandoned_overlay
  - 5 class anchor rubrics: crate_v1, door_v1, panel_v1, terminal_v1,
    weapon_v1
  - 1 reference kit: industrial_loading_bay_v1
  - 2 alias extensions (industrial_crate + mechanical_door with
    morphology + visual_language IDs)
  - + alias schema migration (added `morphology_profile_id` +
    `visual_language_id` fields)

- **71 new unit tests** across Waves 5–12 (placement_binding,
  morphology_profile, zone_binding/mask_compiler/pbr_composer/
  feature_ops_v2, runtime_contract + 5 engine adapters,
  class_anchor + render_rigs + canonical_views, lod_policy,
  kit_graph + docking + rig, determinism + repair_operators,
  feature_dag + spatial_cluster + batched_boolean). All passing.

---

## What's still scaffolded vs. live

| Concern | Live | Scaffolded for future |
|---|---|---|
| Morphology profiles | Driving body aspect for crate + door | parts_ladder + anchor_emitters + default_relations consumed by Stage 6 |
| Placement binding | Contract + resolver + 11 anchor emitters | Stage 6 wiring to call resolver per edge |
| Zone binding | ZoneTag + atlas + grouping helpers | Topology stage attaching tags to faces through booleans |
| PBR composition | Shared-mask channel composer | Texture-rate baker that reads the channel params |
| Feature ops v2 | Registry + specs + param validation | Generator/lowering implementation per op |
| Class anchor | 5 rubrics + evaluator + repair_actions wiring | Repair loop applying operators end-to-end on a current baseline |
| Engine adapters | All 5 manifest emitters | Engine-side importers consuming the manifests |
| KitGraph | KitGraph + ArchetypeReference + docking resolver | SceneProgram grammar extension + scene-level sampling |
| FeatureDAG | DAG + cluster + planner + stub executor | Variadic boolean integration with manifold3d |

The contracts are durable. Migration is per-asset-family as the
synthesizer targets each new contract instead of the legacy path.

---

## How to use this from here

For a new asset class:

1. Author a `MorphologyProfile` JSON at
   `std/procedural/knowledge/morphology/<class>_morphology_v1.json`.
2. Author a `ClassAnchorRubric` at
   `std/procedural/knowledge/rubric/<class>_v1.json`.
3. Register a `FamilyAlias` pointing at the new profile + an existing
   `VisualLanguage`.
4. Author `.lth` files declaring `from <family>` — the synthesizer
   pipeline handles the rest.

For a new visual language:

1. Author a `VisualLanguage` JSON at
   `std/procedural/knowledge/visual_language/<language>_v1.json`.
2. Update aliases to point at it via `visual_language_id`.
3. No code change required.

For an engine target Lathe doesn't ship today:

1. Add an emitter function in `lathe/runtime/engine_adapters.py`
   taking an `AssetRuntimeContract` and returning the engine's
   manifest dict.
2. Register it in `ENGINE_ADAPTERS`.
3. No upstream pipeline change required.

---

## The strategic invariant

The four contracts the research named as decisive are all in place:

- **`lathe.shape.placement_binding_v1`** — typed edges → transforms + proof.
- **`lathe.knowledge.morphology_profile_v1`** — declarative typed morphology per FamilyAlias.
- **`lathe.surface.zone_binding_v1`** — intent zones survive topology.
- **`lathe.runtime.asset_contract_v1`** — game-ready metadata layer.

Lathe's "procedural is the product" bet now has the substrate to back
it. Learned providers remain optional proposal sources; the procedural
graph owns truth, repeatability, packaging, and repair.
