# newresearch.md — Executable Implementation Plan

Date: 2026-05-13
Source: `docs/research/newresearch.md`
Status: active implementation backlog

This document enumerates every research finding as an executable task,
grouped by contract / milestone. Each task names the deliverable and
the integration point in the existing Lathe pipeline.

Implementation order mirrors the research's "decisive build order":

1. Executable placement (anchors + relation resolver)
2. MorphologyProfile pack
3. Zone-preserving topology
4. Feature ops that matter
5. VisualLanguage pack
6. RuntimeAssetContract
7. Class Anchor Validator + repair operators
8. Supporting subsystems (lighting rigs, wear masks, PBR map composition,
   LOD policy, world/scene composition, interface docking, physics,
   engine adapters, determinism, runtime contract, graph-level repair)

---

## Contract 1 — `lathe.shape.placement_binding_v1`

Stage 6 becomes a relation resolver that turns typed edges into
authoritative transforms + anchors + cuts + proof.

| Task | Deliverable | Integration |
|---|---|---|
| 1.1 | `Anchor` dataclass (role, frame, bounds, affordances, capacity) | `lathe/shape/placement.py` |
| 1.2 | `Scope` dataclass (region, parent frame, local bbox, owner_node_id) | `lathe/shape/placement.py` |
| 1.3 | `PlacementCandidate` dataclass (source_anchor, target_anchor, transform, residual, valid, rejection_reason) | `lathe/shape/placement.py` |
| 1.4 | `PlacementBinding` dataclass (edge_id, relation, candidates, chosen, proof) | `lathe/shape/placement.py` |
| 1.5 | `RelationResolver` class — exhaustive candidate + hard constraint reject + soft score + deterministic tie-break | `lathe/shape/placement.py` |
| 1.6 | Per-NODE_TYPE anchor emitters (handle, foot, latch, bracket, fastener, trim, hinge, panel, door_leaf, primary_volume) | `lathe/asset_quality/procedural_synthesizer/anchors/` |
| 1.7 | Relation semantics: `attached_to`, `inset_into`, `wraps_around`, `aligned_with`, `mirrors`, `supports`, `cuts` | `lathe/shape/placement.py::RELATION_SPECS` |
| 1.8 | Wire Stage 6 to resolve edges into PlacementBindings before generators run | `pipeline.py::_emit_node_ops` |
| 1.9 | Unit tests: anchor emission, candidate generation, constraint rejection, deterministic tie-break | `tests/unit/test_placement_binding.py` |

---

## Contract 2 — `lathe.knowledge.morphology_profile_v1`

Declarative typed morphology replaces `_KIND_ASPECT` hardcoding.

| Task | Deliverable | Integration |
|---|---|---|
| 2.1 | `MorphologyProfile` JSON schema (body archetype, expected_aspect, parts_ladder, anchor_emitters, default_relations) | `schema/morphology_profile.schema.json` |
| 2.2 | Loader + cache (mirrors `load_all_alias_packs`) | `lathe/asset_quality/procedural_synthesizer/knowledge_loader/morphology.py` |
| 2.3 | Extend `FamilyAlias` to include `morphology_profile_id` (additive — old aliases default to None) | `knowledge_loader/alias.py` + alias JSONs |
| 2.4 | Author profiles: `swing_door_morphology_v1`, `container_crate_morphology_v1`, `flat_panel_morphology_v1`, `terminal_morphology_v1`, `weapon_prop_morphology_v1` | `std/procedural/knowledge/morphology/*.json` |
| 2.5 | Replace `_KIND_ASPECT` with profile lookup (fallback retained for safety) | `lathe/shape/procedural_program_path.py::_aspect_for_kind` |
| 2.6 | Unit tests: profile loads, aspect derives, parts ladder enforced | `tests/unit/test_morphology_profile.py` |

---

## Contract 3 — `lathe.surface.zone_binding_v1`

Intent zones survive topology fusion into material subsets, UV groups, decals.

| Task | Deliverable | Integration |
|---|---|---|
| 3.1 | `ZoneTag` dataclass (zone_id, material_class, uv_policy, decal_allowed, wear_role, source_node_id, feature_id) | `lathe/surface_graph/zone_binding.py` |
| 3.2 | Face-provenance carrier — each face in topology output carries source ZoneTag set | `lathe/topology_runtime.py` |
| 3.3 | Stage emit: surface graph groups by `(material_class, uv_policy, decal_policy)` | `lathe/core/stages/surface.py` |
| 3.4 | USD `GeomSubset` emitter + glTF mesh-primitive splitter | `lathe/core/stages/package.py` |
| 3.5 | Surface mask compiler — `wear_zone` ops compile to shared masks (edge_wear, concavity_dirt, fastener_rust, scratches, decal_fade) | `lathe/surface_graph/mask_compiler.py` |
| 3.6 | PBR channel composer — basecolor/roughness/metallic/normal/height derived from shared masks | `lathe/surface_graph/pbr_composer.py` |
| 3.7 | Unit tests: zone preservation, mask composition, channel correlation | `tests/unit/test_zone_binding.py` |

---

## Contract 4 — `lathe.runtime.asset_contract_v1`

Target-aware metadata layer for game-ready export.

| Task | Deliverable | Integration |
|---|---|---|
| 4.1 | `AssetRuntimeContract` dataclass (lods, materials, colliders, interfaces, rig, sockets, nav_hints, audio_emitters, light_probe_anchors, streaming_group, semantic_tags, runtime_params) | `lathe/runtime/asset_contract.py` |
| 4.2 | New stage `runtime_metadata` between `validate` and `package` | `lathe/core/stages/runtime_metadata.py` + `STAGE_ORDER` |
| 4.3 | Roblox adapter — MeshPart hierarchy, CollisionFidelity, Attachments, HingeConstraint, Model LOD | `lathe/engine_manifests/roblox.py` (extend) |
| 4.4 | Unity adapter — LODGroup, MeshRenderers, compound colliders, HingeJoint, light/reflection probes, AudioSource slots | `lathe/engine_manifests/unity.py` (extend) |
| 4.5 | Unreal adapter — StaticMesh LODs, simple/complex collision, sockets, constraints, audio, nav-modifier volumes | `lathe/engine_manifests/unreal.py` (new) |
| 4.6 | USD adapter — variants (LOD/style/material), GeomSubset, UsdPhysics, UsdLux, proxy/render purpose | `lathe/engine_manifests/usd.py` (new) |
| 4.7 | glTF adapter — node hierarchy, mesh primitives + material indices, MSFT_lod sidecar | `lathe/engine_manifests/gltf.py` (new or extend) |
| 4.8 | Unit tests: contract round-trip per adapter, missing-field diagnostics | `tests/unit/test_asset_runtime_contract.py` |

---

## Milestone 4 — Feature ops that matter

Add authored-grade hard-surface ops as ShapeIR v2 promotions.

| Task | Deliverable | Integration |
|---|---|---|
| 4F.1 | `op.panel_inset` — target face, margin, depth, bevel_policy, material_zone | `lathe/asset_quality/shape_ir_v2.py` + generators |
| 4F.2 | `op.edge_group_select` — selector predicate (angle, role, exposure, feature_scale) | `lathe/asset_quality/shape_ir_v2.py` |
| 4F.3 | `op.weighted_bevel` — edge_group ref, radius, segments, profile, normal_policy | `lathe/asset_quality/shape_ir_v2.py` |
| 4F.4 | `op.trim_sweep` — path, profile, frame_policy, join_policy, fuse_policy | `lathe/asset_quality/shape_ir_v2.py` |
| 4F.5 | `op.profile_sweep` — non-planar path, scale/rotation/material along path | `lathe/asset_quality/shape_ir_v2.py` |
| 4F.6 | `op.fastener_pattern` — pattern type (grid/line/ring), count, anchor_set | `lathe/asset_quality/shape_ir_v2.py` |
| 4F.7 | `op.boolean_group` — batched cutters per cluster (replaces serial booleans) | `lathe/asset_quality/shape_ir_v2.py` + lowering |
| 4F.8 | `op.lod_policy` — per-LOD bevel_segments, fastener_representation, panel_groove representation, target_tris | `lathe/asset_quality/shape_ir_v2.py` |
| 4F.9 | Unit tests for each op (executed / approximated / unsupported state) | `tests/contract/test_shape_ir_v2_op_coverage.py` (extend) |

---

## Milestone 5 — VisualLanguage pack

Cross-class art direction separate from morphology / composition / style.

| Task | Deliverable | Integration |
|---|---|---|
| 5.1 | `VisualLanguage` dataclass (silhouette_bias, motifs, palette, materials, wear, feature_weight_overrides) | `lathe/asset_quality/procedural_synthesizer/knowledge_loader/visual_language.py` |
| 5.2 | JSON schema | `schema/visual_language.schema.json` |
| 5.3 | Author packs: `utility_industrial_v1`, `steampunk_workshop_v1`, `clean_sci_fi_v1`, `brutalist_bunker_v1`, `alien_grove_v1`, `abandoned_overlay_v1` | `std/procedural/knowledge/visual_language/*.json` |
| 5.4 | Wire `VisualLanguage` into context resolution (alongside style/policies/domain) | `context.py::_resolve_knowledge` |
| 5.5 | Apply `feature_weight_overrides` to policy expansion counts | `pipeline.py::_resolve_count` |
| 5.6 | Apply `silhouette_bias` to morphology profile bounds | `morphology_profile.py` |
| 5.7 | Unit tests: pack loads, weights override, style separates from morphology | `tests/unit/test_visual_language.py` |

---

## Section 7+8+15 — Class Anchor Validator + perceptual rubric

Multi-layer validator stack.

| Task | Deliverable | Integration |
|---|---|---|
| V.1 | `class_anchor` validator framework (per-class rubric evaluator) | `lathe/validators/class_anchor.py` |
| V.2 | Rubric pack: `crate_v1` — bounded_volume, panel_breakup, corner_reinforcement, lid_seam, material_separation, handle_or_latch, scale_plausibility | `std/procedural/knowledge/rubric/crate_v1.json` |
| V.3 | Rubric pack: `door_v1` — vertical_panel, hinge_anchors, handle_at_ergonomic_height, frame_relation_optional, front_back_orientation | `std/procedural/knowledge/rubric/door_v1.json` |
| V.4 | Rubric pack: `panel_v1`, `terminal_v1`, `weapon_v1` | `std/procedural/knowledge/rubric/*.json` |
| V.5 | Standardized render rig (4 lighting setups: neutral studio, three-point product, outdoor sun+sky, low-key rim) | `lathe/render_eval/standard_rigs.py` |
| V.6 | 8-canonical-view renderer (front/back/left/right/top + 3× 3/4 views) + aux passes (normal, depth, material_id, part_id, silhouette) | `lathe/render_eval/canonical_views.py` |
| V.7 | Silhouette-IoU evaluator vs archetype bank | `lathe/render_eval/silhouette_match.py` |
| V.8 | CLIP-similarity wrapper (weak signal; ranked low in rubric) | `lathe/render_eval/clip_score.py` (optional stub) |
| V.9 | VLM rubric scorer (optional, deferred if no API) | `lathe/render_eval/vlm_scorer.py` (stub) |
| V.10 | Unit tests: rubric scoring, anchor presence, render-rig determinism | `tests/unit/test_class_anchor_validator.py` |

---

## Section 11+12 — Surface micro-detail + PBR composition

Wear/dirt/rust as shared mask graphs.

| Task | Deliverable | Integration |
|---|---|---|
| W.1 | `WearMaskRecipe` dataclass (target zone, condition scalar, environment, mask weights) | `lathe/surface_graph/wear_recipes.py` |
| W.2 | Condition scalar → correlated parameter vector resolver | `wear_recipes.py::_condition_to_params` |
| W.3 | Mask compilers: convex_edge_wear, concave_dirt, fastener_rust, vertical_streaks, paint_chipping, decal_fade | `lathe/surface_graph/mask_compiler.py` |
| W.4 | Material archetype binding (painted_steel.utility_industrial, raw_steel.abandoned_rusty, oak_wood.fantasy, brass_fittings.steampunk) | `lathe/surface_graph/material_archetypes.py` |
| W.5 | Shared-mask PBR channel composer (basecolor/metallic/roughness/normal/height all derive from same masks) | `lathe/surface_graph/pbr_composer.py` |
| W.6 | Unit tests: condition→parameter correlation, mask blend, channel correlation | `tests/unit/test_wear_masks.py` |

---

## Section 6+13+16 — Polygon budget + lighting-aware + geometry/surface boundary

LOD policy compiler.

| Task | Deliverable | Integration |
|---|---|---|
| L.1 | `LODPolicy` dataclass (per-LOD bevel_segments, fastener_representation, panel_groove_representation, target_tris) | `lathe/asset_quality/lod_policy.py` |
| L.2 | Per-feature `lod_importance` + `silhouette_relevance` tags at synth emission | construction graph nodes |
| L.3 | Projected-pixel-size calculator (camera/FOV/distance/resolution → feature_world_width → projected_px) | `lathe/asset_quality/lod_policy.py::projected_px` |
| L.4 | Auto-decision: geometry / normal-stamp / texture-only / removed per LOD per feature | `lathe/asset_quality/lod_policy.py::decide_representation` |
| L.5 | Multi-LOD ShapeProgram emitter (synth produces LOD0/1/2/3 variants from one construction graph) | `pipeline.py::_emit_lod_variants` |
| L.6 | Feature-preserving decimation pass (preserves silhouette edges, material seams, UV seams, hard normals, bevel support edges) | `lathe/core/stages/optimize.py` |
| L.7 | Unit tests: LOD policy decisions, projected-size math, decimation preserves seams | `tests/unit/test_lod_policy.py` |

---

## Section 9+10 — World / scene composition

KitGraph + SceneProgram for world generation.

| Task | Deliverable | Integration |
|---|---|---|
| K.1 | `KitGraph` dataclass (visual_language, material_palette, texel_density, archetypes, variation) | `lathe/scene/kit_graph.py` |
| K.2 | `SceneProgram` schema + parser extension | grammar + `lathe/scene/scene_program.py` |
| K.3 | Stratified seed sampling + repetition limit + condition distribution | `lathe/scene/sampling.py` |
| K.4 | `InterfaceSignature` dataclass (interface_id, kind, frame, bounds, snap_points, load_capacity_kg, texel_density, material_transition, collision_policy) | `lathe/interface_connections.py` (extend) |
| K.5 | Docking resolver — compatible kind + dimensions + load + orientation + clearance + style/material | `lathe/scene/docking.py` |
| K.6 | Author one example world: `industrial_loading_bay_v1` | `std/kits/industrial_loading_bay_v1.json` |
| K.7 | Unit tests: kit composition, docking, variation sampling | `tests/unit/test_kit_graph.py` |

---

## Section R — Rigs + physics

Rigid constraints first, bones second.

| Task | Deliverable | Integration |
|---|---|---|
| R.1 | `RigContract` dataclass (rig_type, bodies, joints, animations) | `lathe/rig/rig_contract.py` |
| R.2 | Construction-graph `hinge` metadata → hinge joint emitter | `lathe/core/stages/rig.py` |
| R.3 | `PhysicsIR` dataclass (bodies, collision compound parts, mass_kg, material) | `lathe/core/stages/physics.py` |
| R.4 | Construction-graph nodes → physics roles → collision primitives | `physics.py::derive_compound_collision` |
| R.5 | Engine-adapter joint lowering (Roblox HingeConstraint, Unity HingeJoint, Unreal physics constraint, USD UsdPhysics) | engine manifest extensions |
| R.6 | Unit tests: hinge edge → joint, compound collision derivation | `tests/unit/test_rig_physics.py` |

---

## Section 14 — Determinism + reproducibility

Seed hierarchy + reproducibility manifest.

| Task | Deliverable | Integration |
|---|---|---|
| D.1 | `SeedHierarchy` dataclass (world_seed, kit_seed, asset_archetype_seed, asset_instance_seed, surface_micro_seed, decal_seed, wear_seed) | `lathe/determinism/seeds.py` |
| D.2 | `ReproducibilityManifest` dataclass (lathe_version, shape_contract, knowledge_pack_versions, world_seed, asset_seed, shape_graph_hash, compiled_ir_hash, provider_proposals) | `lathe/determinism/manifest.py` |
| D.3 | Synthesizer reads from seed hierarchy (not global) | `pipeline.py::_synthesize` |
| D.4 | Build report emits reproducibility manifest | `executor.py::_emit_build_report` |
| D.5 | Unit tests: seed isolation, manifest hash stability | `tests/unit/test_determinism.py` |

---

## Section 16 — Repair operators

Graph-level repair, not mesh-level.

| Task | Deliverable | Integration |
|---|---|---|
| RP.1 | `RepairOperator` registry — insert_required_feature, panelize_face, add_reinforcement_pattern, strengthen_silhouette, assign_material_zone, add_decal_zone, increase_bevel_readability, add_surface_wear, promote_detail_to_geometry, demote_detail_to_texture, adjust_style_weights, resample_variation | `lathe/repair_operators.py` (extend) |
| RP.2 | Wire `class_anchor` validator failures → repair plan generation | `lathe/repair_planner.py` |
| RP.3 | Repair plan applies graph mutations + reruns synthesizer | `lathe/repair_loop.py` |
| RP.4 | Unit tests: each repair op mutates graph deterministically, repair loop converges | `tests/unit/test_repair_operators.py` |

---

## Section 1 — Geometry representation foundation

Lazy feature DAG + batched boolean compiler.

| Task | Deliverable | Integration |
|---|---|---|
| G.1 | `FeatureDAG` dataclass (primitives, transforms, relations, boolean expressions, material zones, bevel rules, sweep rules, decal rules) | `lathe/geometry/feature_dag.py` |
| G.2 | Spatial cluster broadphase (group interacting primitives by bbox overlap) | `lathe/geometry/spatial_cluster.py` |
| G.3 | Batched-boolean executor — collect cluster, convert once, apply grouped expression, extract once, preserve provenance | `lathe/geometry/batched_boolean.py` |
| G.4 | Deferred bevel pass — runs after booleans, on selected semantic edge groups, with budget | `lathe/geometry/deferred_bevel.py` |
| G.5 | Coplanar planar merge pass — recover flat regions after fragmentation | `lathe/geometry/planar_merge.py` |
| G.6 | Unit tests: cluster correctness, batched evaluation determinism, planar merge | `tests/unit/test_feature_dag.py` |

---

## Final synthesis

| Task | Deliverable | Integration |
|---|---|---|
| F.1 | Hero-fixture re-render with full new stack (anchors + morphology + zones + visual language + class anchor + repair) | live `quick` invocations |
| F.2 | Before/after summary document | `docs/research/newresearch-before-after.md` |
| F.3 | Memory entries documenting the new architecture and what changed | `memory/*.md` |

---

## Execution waves

Each wave ends with: code committed, tests passing, hero-fixture re-render evidence captured.

- **Wave 5**: Contracts 1 (placement_binding) + 2 (morphology_profile). Foundation.
- **Wave 6**: Contract 3 (zone_binding) + Feature ops M4 (panel_inset, edge_group_select, weighted_bevel).
- **Wave 7**: Contract 4 (runtime_asset_contract) + VisualLanguage M5.
- **Wave 8**: Validators + render rigs (Class Anchor V.* + standardized rigs).
- **Wave 9**: Surface micro-detail + PBR composition (W.* + L.*).
- **Wave 10**: World/scene + interfaces + rigs/physics (K.* + R.*).
- **Wave 11**: Determinism + repair operators (D.* + RP.*).
- **Wave 12**: Geometry foundation (G.*) — lazy DAG, batched boolean (research-aligned, longer-term).
- **Wave 13**: Final synthesis (F.*).
