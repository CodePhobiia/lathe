# Lathe Implementation Northstar

Date: 2026-05-05
Status: Canonical source of truth for the next Lathe implementation push
Scope: Visible geometry, asset quality, and the imagination-to-life execution path

This is the working source of truth for choosing, sequencing, implementing, and validating the next Lathe work.

Historical docs remain useful as evidence and detail, but this document is the operational path unless it is explicitly replaced. Future implementation agents should start here, then open only the task-relevant source docs or code files.

## 0. How To Use This Document

Use this document as:

1. The decision filter for what to build next.
2. The implementation backlog for visible-geometry and asset-quality work.
3. The acceptance standard for claiming progress.
4. The guardrail against metadata-only success.
5. The bridge between the long imagination-to-life roadmap and the next concrete code changes.

If another document conflicts with this one, prefer this document for next implementation sequencing. If a source doc has a lower-level code detail not repeated here, use the source doc as evidence, but do not change the implementation priority unless the user explicitly redirects.

## 1. Northstar

Lathe must become the truthful deterministic craft engine for AI-native 3D creation.

The product loop is:

```text
creative intent / .lth source
-> explicit construction program
-> real visible geometry
-> topology, UV, and surface evidence
-> preview/export artifacts
-> diagnostics that judge visible quality
-> semantic repair or honest rejection
-> regenerated improved asset package
```

Every new implementation should strengthen that loop.

Work is not strategic if it only adds:

- more words to `.lth`;
- more report fields;
- more prose;
- more metadata completeness;
- more validator scores;
- more optional provider paths;
- more fixture-specific branches;
- more examples that do not prove a new execution capability.

Work is strategic when it makes one of these more true:

- Lathe builds richer geometry.
- Lathe preserves semantic construction evidence through the pipeline.
- Lathe surfaces real previews, exports, and reports.
- Lathe detects visually weak output.
- Lathe repairs a weak output through executable operations.
- Lathe rejects or degrades unsupported claims truthfully.
- Lathe lets new asset families be authored without Python edits per family.

## 2. Product Boundary

Lathe is the execution substrate.

Wonder or another creative director can request assets, scenes, repairs, inspections, and revisions. Lathe must execute those requests into deterministic geometry, materials, previews, reports, exports, and packages.

The boundary is:

```text
Wonder
= creative direction, scene memory, curiosity loop, orchestration, critique

Lathe
= deterministic asset/world construction, geometry/material execution, export evidence, repair substrate
```

Learned providers may remain optional proposal sources. They must not become the answer to Lathe asset quality. The next push is standalone procedural: no AI 3D runtime dependency, no fake learned-quality claims, no provider-critical path.

## 3. Core Problem

Lathe's language, stdlib, quality layer, and imagination-to-life vision are ahead of its geometry and surface execution layer.

The most dangerous failure mode is success-shaped output:

```text
source says "beveled sci-fi crate with panels, vents, fasteners, material zones, and wear"
report says the package is complete
preview still looks like primitive blockout or debug material output
```

The problem is not lack of language ambition. The problem is representation/execution mismatch:

```text
semantic asset intent
-> incomplete construction operations
-> partially supported kernel path
-> weak mesh provenance
-> weak surface/material masks
-> validators that may reward metadata
-> package that appears certified but is not visibly convincing
```

The next implementation work must close this gap, not widen it.

## 4. Rule Of Truth

For every public or reportable asset-quality claim, one of these must be true:

1. Lathe builds it as visible geometry or visible surface output.
2. Lathe lowers it into supported construction operations.
3. Lathe reports the unsupported or degraded state honestly.
4. Lathe does not promise it yet.

This state is forbidden:

```text
Language, docs, validator, or report says it happened,
but mesh, material, preview, package, or import evidence does not prove it.
```

The implementation standard is:

```text
claim -> construction -> output -> evidence -> judgment -> repair or honest blocker
```

## 5. Stable Contracts And Hard Guardrails

Preserve these unless a task explicitly declares a migration:

- Public `.lth` source compatibility.
- Stable shape-stage handoff contract: `lathe.shape.intent_mesh_handoff_v1`.
- Public language surface around `profile`, `contract`, `critic`, `asset`, `variant`, and build-stage names.
- Existing downstream topology, UV, surface, package, and publish contracts unless the task names a migration.
- Attempted-vs-actual tracing for providers, kernels, renderers, topology adapters, UV adapters, package exporters, and external import evidence.

Implementation guardrails:

- Do not add public syntax before the internal execution path proves visible output.
- Do not claim production, game, Roblox, Unity, Unreal, or DCC readiness from proxy evidence.
- Do not fake Blender, xatlas, Manifold, renderer, bake, package, import, or learned-provider evidence.
- Do not hide fallback behavior.
- Do not let validators reward metadata completeness over human-visible quality.
- Do not add chest-only fixes unless they generalize through tags, asset class, operations, or stdlib.
- Do not expand the language faster than the kernel can honor.
- Do not tune old outputs to pass by weakening the gate.

Internal architecture can evolve aggressively underneath the stable handoff when it is additive and truth-preserving.

## 6. Current Product State To Respect

Lathe already contains real, useful foundations:

- Parser, normalizer, resolver, checker, planner, materializer, executor.
- Stable shape handoff: `lathe.shape.intent_mesh_handoff_v1`.
- Native assembly-first shape core.
- ShapeIR v1 with richer primitives than the oldest roadmap assumed: box, cylinder, sphere, revolved profile, extruded profile, torus, subdivision box, swept profile, heightfield, lofted solid, SDF mesh.
- ShapeIR v2 semantic operation model.
- Asset-quality modules for diagnostics, quality planning, grammar lowering, material/wear graph, preview evidence, semantic critique, semantic patch, reference boards, and vision critique.
- Geometry kernel seam and optional Manifold adapter.
- Mesh program examples and several procedural domains from the imagination-to-life session.
- Existing demos for hard-surface, vegetation, terrain, SDF organic, WFC modular, scatter, and surface scatter.
- Optional learned providers, explicitly non-critical.

The next push should use these foundations. It should not restart the product from scratch.

## 7. Consolidated Diagnosis

The source docs converge on the same diagnosis. This section is the canonical blocker map.

### B0. The Language Is Ahead Of The Engine

Symptom:

- `.lth` can imply rich assets.
- Reports can describe rich assets.
- The mesh/preview may still show blockout-level geometry or debug-style materials.

Root cause:

- Semantic intent is not consistently lowered into construction operations.
- Construction operations are not consistently routed through capable kernels.
- Mesh/surface provenance does not survive far enough downstream.
- Validators and reports may not inspect the pixels or final artifacts that humans judge.

Fix:

- Make the visible geometry loop the implementation center.
- Promote dormant authoring layers into execution drivers only when tied to visible output.

### B1. Authored Intent Dies Before Geometry

Known finding:

- Large parts of `intent`, `geometry`, `features`, `surface`, `assembly`, and `style_target` may not reach the shape builder.
- Family inference and hardcoded blueprint routing can dominate.
- `features.allow`, `geometry.integration_rules`, and `surface.patterns` have historically been under-consumed.

Primary files to inspect when implementing:

- `lathe/asset_graph.py`
- `lathe/assembly_kernel.py`
- `lathe/feature_grammar.py`
- `lathe/asset_quality/grammar_lowering.py`
- `lathe/asset_quality/construction_graph.py`
- `lathe/asset_quality/shape_ir_v2.py`

Implementation direction:

- Add a typed authoring context that carries feature allowlists, edge classes, seam classes, integration rules, style target, density, preservation intent, material zones, and surface patterns into shape construction.
- Prefer tag/component/asset-class dispatch over family-name dispatch.
- Record what was consumed, ignored, approximated, or rejected.

Acceptance:

- A test changes an authored feature or integration rule and the generated construction program changes.
- Ignored authoring fields produce diagnostics instead of silent no-op behavior.

### B2. ShapeIR v2, Grammar Lowering, And Construction Graph Are Too Often Validators, Not Drivers

Known finding:

- ShapeIR v2 has semantic operations for solids, booleans, edge control, SOP-style operations, repetition, integration, and wear.
- Grammar lowering and construction graph produce useful semantic records.
- Too much of this remains informational after the mesh already exists.

Primary files:

- `lathe/asset_quality/shape_ir_v2.py`
- `lathe/asset_quality/grammar_lowering.py`
- `lathe/asset_quality/construction_graph.py`
- `lathe/scaffold_compiler.py`
- `lathe/assembly_kernel.py`

Implementation direction:

- Promote one narrow ShapeIR v2 operation at a time into execution.
- Do not promote all v2 ops at once.
- Start with high-signal hard-surface ops: trim band, fastener grid, vent slats, bevel/chamfer, socket/bracket/mount plate.
- Add diagnostics for unsupported operations.

Acceptance:

- An operation survives lowering.
- It produces visible geometry or material-mask output.
- Reports name whether it was executed, approximated, or unsupported.

### B3. CSG And Exact Paths Have Been Too Narrow Or Too Fallback-Oriented

Known finding:

- Exact solid paths and robust kernel seams exist.
- CSG enablement has historically been tied to selected hero families.
- Manifold may be available but not always primary.
- Boolean failure can degrade to concatenated geometry unless surfaced strongly.

Primary files:

- `lathe/feature_fusion.py`
- `lathe/exact_solids.py`
- `lathe/geometry_kernel.py`
- `lathe/geometry/kernel.py`
- `lathe/shape/backend.py`
- `lathe/scaffold_compiler.py`

Implementation direction:

- Make CSG capability depend on authored intent, asset class, feature requirements, and kernel support, not family names alone.
- Route boolean operations through explicit kernel resolution.
- Prefer Manifold for clean manifold hard-surface CSG when the resolved backend supports the needed primitive set.
- Add a backend chain where useful: Manifold, optional robust fallback, voxel/levelset repair as last resort.
- Never silently certify boolean fallback on a hero-quality claim.

Acceptance:

- Reports include attempted kernel, actual kernel, fallback reason, watertightness/body-count checks, and unsupported primitive diagnostics.
- A boolean fallback creates a visible diagnostic such as `boolean_csg_fallback`.

### B4. Bevels, Chamfers, And Edge Treatments Are The Biggest Hard-Surface Signal

Known finding:

- Edge treatment is the fastest way to move output from blockout to intentional hard-surface.
- Some current or historical bevel paths are corner-only, post-boolean-limited, or family-gated.

Primary files:

- `lathe/exact_solids.py`
- `lathe/feature_ops/bevel_real.py`
- `lathe/mesh_program/__init__.py`
- `lathe/asset_quality/shape_ir_v2.py`
- `lathe/assembly_kernel.py`
- `lathe/mesh_finalize.py`

Implementation direction:

- Keep the canonical hard-surface idiom: `boolean -> bevel(seam_group)`.
- Preserve seam group IDs through MeshIR, topology, UV, surface, and validate where feasible.
- Implement edge-class treatment generically, not by family equality.
- Add selective edge selectors and edge profiles as a later step.
- Emit low-fidelity bevel diagnostics when the operation degenerates.

Acceptance:

- Preview shows edge highlights or chamfer strips.
- Mesh/report names bevel source operation and seam group.
- Validator can distinguish missing bevel evidence from present bevel evidence.

### B5. Feature Density Is Not Yet Author-Controllable Enough

Known finding:

- Feature density can become a tier ladder instead of a real authoring control.
- Repetition patterns can be hardcoded per fixture.
- Secondary/tertiary detail can be too flat or too uniform.

Primary files:

- `lathe/feature_grammar.py`
- `lathe/feature_ops/__init__.py`
- `lathe/mesh_program/__init__.py`
- `lathe/instance_pattern.py`
- `lathe/asset_quality/family_grammar.py`

Implementation direction:

- Treat density as a multiplier and a pattern driver, not only a tier name.
- Prefer generic distribution/scatter operations over fixture helpers.
- Add primary/secondary/tertiary hierarchy: large form breaks, medium trim, small fasteners/wear.
- Support deterministic variation with bounds, symmetry, and snap constraints.

Acceptance:

- Increasing density or count changes visible instance/detail count.
- Variation is bounded and deterministic.
- Report includes count and placement evidence.

### B6. Surface And Bake Truth Are Not Optional

Known finding:

- Surface output can make good geometry look bad.
- World-space face-normal polygon fill is not a valid tangent-space normal map.
- AO, curvature, and wear can be weak if based on low-poly faces only.
- DesignerGraph and LayerStack capability must feed actual buffers, not only sidecars.

Primary files:

- `lathe/bake_runtime.py`
- `lathe/surface_runtime.py`
- `lathe/surface_graph/designer_graph.py`
- `lathe/surface_graph/nodes.py`
- `lathe/surface_graph/layer_stack.py`
- `lathe/surface_graph/materialx.py`
- `lathe/materials.py`
- `lathe/asset_quality/material_wear_graph.py`

Implementation direction:

- Fix fallback normal bake to tangent-space output.
- Use high-poly or primitive-native source for curvature where claiming edge wear.
- Evaluate DesignerGraph or LayerStack into actual basecolor/normal/roughness/AO/curvature buffers.
- Add missing graph nodes incrementally: SlopeBlur, HistogramScan/Levels, EdgeDetect, GradientMap, PositionMask/WorldYMask.
- Distinguish final beauty from material-ID/debug previews.
- Emit authored-vs-proxy flags for maps and materials.

Acceptance:

- The final preview changes when material-zone or wear settings change.
- Normal map is neutral/tangent-space when no high source is available.
- Reports state which maps are real, proxy, fallback, or unavailable.

### B7. High/Low Transfer Must Contain Real Extra Detail

Known finding:

- Subdividing the low mesh does not create real high-poly source detail.
- Curvature/wear transfer from a subdivided low mesh is not real high/low.

Primary files:

- `lathe/surface_runtime.py`
- `lathe/highlow.py`
- `lathe/bake_runtime.py`
- `lathe/shape_ir.py`
- `lathe/asset_quality/highlow_relation.py`

Implementation direction:

- Generate high source from ShapeIR primitives at native curvature, not just low mesh subdivision.
- Preserve bevel, chamfer, panel, rivet, groove, and seam geometry in the high source when claiming baked detail.
- Report real high/low ratio, projection quality, hit ratio, and fallback decision.

Acceptance:

- High source has additional detail or curvature not present in the low mesh.
- Curvature/wear maps show detail beyond low-poly silhouette edges.

### B8. Topology Can Erase Craft

Known finding:

- Blender adapter failures or fallback paths can collapse multi-part or bevel work.
- Retopology/cleanup can remove detail or produce ugly shading.
- Hard-edge and seam semantics need preservation.

Primary files:

- `lathe/topology_runtime.py`
- `lathe/core/stages/topology.py`
- `scripts/blender_topology_adapter.py`
- `lathe/mesh_finalize.py`
- `lathe/topology_runtime.py`

Implementation direction:

- Fix or confirm Blender import behavior for current Blender versions.
- Keep Blender optional and truthfully traced.
- Add deterministic fallback quality improvements: beauty-diagonal triangulation, Taubin smoothing for voxel-origin parts, hard-edge normal split.
- Add real quad-remesh provider only when it can be validated and traced.
- Preserve seam groups, bevel strips, material zones, and part names.

Acceptance:

- Before/after topology does not lose named parts or critical seam groups.
- Reports include attempted topology adapter and actual adapter.
- Fallback is not silent.

### B9. UV And Texel Density Must Become Evidence

Known finding:

- Texel-density inconsistency is a major visible quality failure.
- Per-part importance and authored density can be recorded without governing packing enough.
- Trim sheets and UDIM are key hard-surface quality levers.

Primary files:

- `lathe/uv_runtime.py`
- `lathe/core/stages/uv.py`
- `lathe/core/uv_ops.py`
- `lathe/atlas_assembler.py`
- `lathe/texture_control_pack.py`

Implementation direction:

- Add texel-density audit: min, max, ratio, worst chart, per-part density.
- Honor asset density request and importance weights at pack time.
- Add constrained chart pre-scaling before packing.
- Add trim-sheet binding later: slot atlas, UV rect, edge/face binding, packing exclusion.
- Add UDIM spillover later for hero assets when one tile cannot preserve density.
- Use triplanar only when declared or when UV evidence shows it is the right fallback.

Acceptance:

- Validator/report can name the chart or part causing density drift.
- UV fallback reports why it happened.
- Texture evidence links to density and packing decisions.

### B10. Validators Must Judge Visible Output

Known finding:

- Validators can reward metadata or old box-like output.
- Pixel-level or preview-level evidence is missing in parts of the current system.
- Certification must correlate with human review.

Primary files:

- `lathe/asset_quality/diagnostics.py`
- `lathe/validators/visual_quality.py`
- `lathe/validators/semantic_quality.py`
- `lathe/render_eval.py`
- `lathe/core/stages/validate.py`
- `lathe/asset_quality/preview_evidence.py`
- `lathe/asset_quality/preview_render.py`

Implementation direction:

- Add diagnostics for visible blockers: blockout shape, debug material look, missing bevel/detail, weak hierarchy, weak material contrast, fake high/low, attachment seating, boolean fallback, preview absence.
- Prefer pixel/mesh/artifact evidence over metadata.
- Keep thresholds honest: warnings for proxy gaps, errors for false hero claims.

Acceptance:

- The baseline crate or door fails/warns for the visible weakness a human sees.
- The improved artifact changes at least one visible metric and report code.

### B11. Semantic Repair Must Become Operational

Known finding:

- Repair machinery exists, but it is only meaningful when diagnostics map to executable operations.

Primary files:

- `lathe/asset_quality/semantic_critique.py`
- `lathe/asset_quality/semantic_patch.py`
- `lathe/repair_loop.py`
- `lathe/repair_executor.py`
- `lathe/repair_policy.py`

Implementation direction:

- Start with one mapping.
- Suggested first mapping: weak detail hierarchy -> add trim band, fastener grid, or vent slats.
- Keep patch operations deterministic, serializable, and allowlisted.
- Reject patches that require public syntax or shape handoff migration.

Acceptance:

- Baseline diagnostic produces a repair suggestion.
- Suggestion lowers to an allowed patch/regeneration operation.
- Rebuild produces visible before/after difference and improved metric.

### B12. Chest-Specific Code Is A Product Smell

Known finding:

- Historical fixes often concentrated around chest.
- Family-specific token sets and allowlists make new families require Python edits.

Primary files:

- `lathe/asset_graph.py`
- `lathe/assembly_kernel.py`
- `lathe/feature_grammar.py`
- `lathe/feature_fusion.py`
- `lathe/highlow_relation.py`
- `lathe/surface_runtime.py`
- `lathe/primitive_selector.py`

Implementation direction:

- Dispatch by asset class, tags, authored selector rules, component roles, and feature ops.
- Move family rules to stdlib where possible.
- Use chest, crate, door, weapon, terrain, vegetation, SDF, WFC as guardrails, not as type-system anchors.

Acceptance:

- A non-chest fixture benefits from the fix.
- New functionality is not gated by `family == "brassbound_chest"` or equivalent one-off equality unless explicitly legacy.

## 8. Immediate Focus: Visible Geometry Kernel Sprint 0

Sprint name:

```text
visible-geometry-kernel-sprint-0
```

Objective:

```text
Make one existing hard-surface fixture visibly better while preserving public source compatibility and the stable shape handoff contract.
```

Primary fixture:

```text
industrial_crate / sci-fi crate
```

Secondary guardrail:

```text
mechanical_door or fantasy_weapon
```

The before/after improvement must be obvious in five seconds. If it needs a long explanation, it is not strong enough.

### Sprint 0 Non-Negotiables

- Capture baseline before changing behavior.
- Generate or reference visible preview evidence.
- Improve real geometry or real surface output.
- Add diagnostics that catch the before-state.
- Wire one semantic repair mapping if feasible.
- Preserve `.lth` compatibility.
- Preserve `lathe.shape.intent_mesh_handoff_v1`.
- Report every proxy/fallback/unavailable dependency.
- Keep the implementation reusable beyond one fixture.

### Sprint 0 Done Condition

The sprint is complete when this chain exists:

```text
.lth intent
-> baseline crate artifact
-> visible weakness diagnostic
-> concrete operation or repair path
-> rebuilt crate artifact
-> before/after preview
-> report metrics change
-> export/package artifacts exist
```

Minimum visible improvement:

- less primitive/blockout-looking;
- clearer silhouette or hard-surface hierarchy;
- visible bevel/chamfer, trim, fasteners, vents, panels, or equivalent secondary detail;
- coherent final materials instead of debug-only colors;
- evidence paths in the report or sprint evidence doc.

## 9. Detailed Sprint 0 Task Plan

### Task S0-1: Capture Baseline Evidence

Purpose:

- Create a truthful before-state.
- Prevent subjective or memory-based claims.

Create or update:

- `docs/asset-quality/visible-geometry-sprint-0-evidence.md`

Read:

- `examples/industrial_crate.lth`
- `examples/mechanical_door.lth`
- closest equivalent fixtures if paths differ

Commands:

```powershell
git status --short
python -m lathe.cli check examples/industrial_crate.lth
python -m lathe.cli check examples/mechanical_door.lth
python -m lathe.cli build examples/industrial_crate.lth industrial_crate --out .tmp_tests/baseline_industrial_crate --deterministic
python -m lathe.cli build examples/mechanical_door.lth mechanical_door --out .tmp_tests/baseline_mechanical_door --deterministic
```

Record:

- commands run;
- output directories;
- build reports;
- shape/topology/UV/surface/validate/package artifacts;
- preview paths;
- optional dependency blockers;
- whether each preview is real or proxy;
- human-visible weaknesses;
- exact dirty worktree state without cleaning unrelated files.

Validation:

```powershell
python -m pytest -q tests/unit/test_asset_quality_baseline_report_shape.py tests/unit/test_asset_quality_preview_evidence.py
```

Done when:

- There is a readable evidence doc with exact paths and allowed claims.

### Task S0-2: Strengthen Preview Evidence

Purpose:

- Make the artifact inspectable.
- Stop reports from passing without visual proof.

Primary files:

- `lathe/asset_quality/preview_evidence.py`
- `lathe/asset_quality/preview_render.py`
- `lathe/asset_quality/certification.py`
- `lathe/core/stages/validate.py`
- `tests/unit/test_asset_quality_preview_evidence.py`

Required preview evidence model:

- `final_beauty`
- `material_ids`
- `wireframe`
- `orthographic_front`
- `orthographic_top`
- `orthographic_three_quarter`
- `comparison_sheet`
- `renderer_status`
- `proxy_status`
- `artifact_paths`

Truth statuses:

- `real_renderer_used`
- `renderer_unavailable`
- `proxy_preview_only`
- `artifact_missing`
- `not_requested`

Tests:

```powershell
python -m pytest -q tests/unit/test_asset_quality_preview_evidence.py tests/unit/test_asset_quality_certification.py
```

Done when:

- Missing renderers create explicit statuses.
- Reports can point to human-inspectable preview artifacts or explicitly say they are missing/proxy.

### Task S0-3: Add One Visible Geometry Detail Operation

Purpose:

- Prove semantic intent can become real visible output.

Recommended first op:

- `op.trim_band` or `op.fastener_grid` if bevel/chamfer is risky.
- `op.bevel` or `op.chamfer` if current mesh path supports it cleanly.

Primary files:

- `lathe/asset_quality/shape_ir_v2.py`
- `lathe/asset_quality/grammar_lowering.py`
- `lathe/mesh_program/__init__.py`
- `lathe/feature_ops/__init__.py`
- `lathe/feature_ops/bevel_real.py`
- `lathe/geometry_kernel.py`
- `lathe/exact_solids.py`

Test files:

- `tests/unit/test_shape_ir_v2.py`
- `tests/unit/test_asset_quality_grammar_lowering.py`
- `tests/unit/test_mesh_program_ops.py`
- `tests/unit/test_geometry_kernel.py`

Requirements:

- operation has stable semantic ID;
- operation has target/face/axis/count/size parameters as relevant;
- operation either emits visible geometry or visible material-mask/region evidence;
- unsupported target geometry creates diagnostics;
- approximation is tagged as approximation;
- stable shape handoff is not broken.

Commands:

```powershell
python -m pytest -q tests/unit/test_shape_ir_v2.py tests/unit/test_asset_quality_grammar_lowering.py tests/unit/test_mesh_program_ops.py
python -m pytest -q tests/unit/test_geometry_kernel.py
```

Done when:

- A fixture build produces visible detail and report evidence names the operation.

### Task S0-4: Improve Crate Surface Defaults

Purpose:

- Kill debug-material look and make final beauty readable.

Primary files:

- `lathe/materials.py`
- `lathe/surface_runtime.py`
- `lathe/bake_runtime.py`
- `lathe/asset_quality/material_wear_graph.py`

Test files:

- `tests/unit/test_surface_runtime.py`
- `tests/unit/test_asset_quality_material_wear_graph.py`

Requirements:

- family/style-aware material defaults;
- non-debug final palette;
- material zones with readable contrast;
- roughness/normal/AO/curvature/wear map status;
- authored-vs-proxy flags;
- final beauty distinct from material-ID debug.

Commands:

```powershell
python -m pytest -q tests/unit/test_surface_runtime.py tests/unit/test_asset_quality_material_wear_graph.py
```

Done when:

- Surface changes are visible in final preview or texture artifacts.

### Task S0-5: Add Human-Visible Diagnostics

Purpose:

- Make the before-state fail or warn for the same reason a human would complain.

Primary files:

- `lathe/asset_quality/diagnostics.py`
- `lathe/validators/visual_quality.py`
- `lathe/core/stages/validate.py`

Test files:

- `tests/unit/test_asset_quality_diagnostics.py`
- `tests/test_visual_quality.py`
- `tests/unit/test_asset_quality_baseline_report_shape.py`

Diagnostic targets:

- `blockout_geometry_appearance`
- `debug_material_preview_penalty`
- `missing_bevel_chamfer_detail_evidence`
- `weak_primary_secondary_tertiary_balance`
- `weak_material_zone_contrast`
- `attachment_seating_quality`
- `fake_highlow_detail`
- `boolean_csg_fallback`
- `proxy_preview_only`

Commands:

```powershell
python -m pytest -q tests/unit/test_asset_quality_diagnostics.py tests/unit/test_asset_quality_baseline_report_shape.py tests/test_visual_quality.py
```

Done when:

- Baseline artifact receives an accurate warning/failure.
- Improved artifact improves the relevant metric.

### Task S0-6: Wire One Semantic Repair Mapping

Purpose:

- Seed the Wonder-style revision loop.

Primary files:

- `lathe/asset_quality/semantic_critique.py`
- `lathe/asset_quality/semantic_patch.py`
- `lathe/repair_loop.py`
- `lathe/asset_quality/generation_steering.py` if used by current implementation

Test files:

- `tests/unit/test_asset_quality_semantic_critique.py`
- `tests/unit/test_asset_quality_semantic_patch.py`
- `tests/unit/test_asset_quality_generation_steering.py`

First mapping:

```text
weak_primary_secondary_tertiary_balance
-> add trim band / fastener grid / vent slats
```

Other early mappings:

```text
debug_material_preview_penalty
-> apply family-aware non-debug material defaults

attachment_seating_quality low
-> add socket, bracket, or mount plate

missing_bevel_chamfer_detail_evidence
-> add bevel/chamfer or report unsupported operation/kernel
```

Commands:

```powershell
python -m pytest -q tests/unit/test_asset_quality_semantic_critique.py tests/unit/test_asset_quality_semantic_patch.py tests/unit/test_asset_quality_generation_steering.py
```

Done when:

- Diagnostic maps to deterministic allowlisted patch.
- Unsafe patch is rejected.
- Rebuild can produce before/after evidence.

### Task S0-7: Start KernelProgram Seam

Purpose:

- Begin the structural Phase 2 fix without switching behavior globally.

Suggested files:

- `lathe/geometry/kernel_program.py`
- `lathe/geometry/shape_ir_lowering.py`
- `tests/unit/test_geometry_kernel.py`
- `tests/unit/test_shape_ir_v2.py`

Requirements:

- deterministic serialization;
- stable IDs for primitives, parts, operations, seams, material zones;
- diagnostics for unsupported primitive/op combinations;
- explicit approximation records;
- no breaking public shape handoff fields.

Commands:

```powershell
python -m pytest -q tests/unit/test_geometry_kernel.py tests/unit/test_shape_ir_v2.py tests/contract/test_shape_handoff_v1.py
```

Done when:

- Internal seam exists and is tested.
- Production build path is not globally switched until visible slice proves value.

### Task S0-8: Produce Final Sprint Evidence

Purpose:

- Close the loop honestly.

Commands:

```powershell
python -m pytest -q tests/unit/test_asset_quality_preview_evidence.py tests/unit/test_asset_quality_diagnostics.py tests/unit/test_asset_quality_generation_steering.py
python -m pytest -q tests/unit/test_shape_ir_v2.py tests/unit/test_asset_quality_grammar_lowering.py tests/unit/test_geometry_kernel.py
python -m pytest -q tests/unit/test_surface_runtime.py tests/unit/test_asset_quality_material_wear_graph.py
python -m lathe.cli check examples/industrial_crate.lth
python -m lathe.cli build examples/industrial_crate.lth industrial_crate --out .tmp_tests/visible_geometry_sprint0 --deterministic
```

Record:

- before and after preview paths;
- metrics that changed;
- report paths;
- package/export paths;
- optional dependency blockers;
- exact allowed claims and disallowed claims.

Done when:

- A future reader can inspect the evidence and understand what became real.

## 10. Implementation Lanes Beyond Sprint 0

These lanes are the detailed master backlog. Use them after or alongside Sprint 0 only when they directly support the visible loop.

### Lane A: Geometry Kernel And CSG

Goal:

- Make construction operations execute through explicit, truthful geometry backends.

Priority tasks:

1. Promote resolved Manifold path ahead of brittle fallback where primitive coverage is sufficient.
2. Add missing primitive coverage in Manifold path, especially lofted solids if still missing.
3. Replace family-only exact-mode gating with capability/asset-class/authoring checks.
4. Add boolean backend chain telemetry: attempted, actual, fallback reason, diagnostics.
5. Emit validation diagnostic when boolean fallback emits concatenated or degraded mesh.
6. Add strict geometry mode failure for invalid hero claims.
7. Add mesh-to-levelset repair as a last-resort experimental fallback only with visible degraded status.

Potential future tasks:

- hull operation;
- minkowski operation;
- twist/scale on extruded profiles;
- partial rotate extrude;
- unified tessellation policy;
- helical sweep;
- involute gear primitive;
- NURBS-backed profile curves;
- bend/twist/taper deformers;
- B-Rep IR via OCCT/build123d as a parallel high-ceiling lane;
- half-edge bevel operator for arbitrary mesh topology.

Do not build the full future list before Sprint 0 has visible evidence.

### Lane B: ShapeIR v2 And Construction Graph As Drivers

Goal:

- Make semantic construction records drive geometry instead of only validating after the fact.

Priority tasks:

1. Define minimal `ShapeProgram` or `KernelProgram` for one hard-surface fixture.
2. Lower design brief, construction graph, and ShapeIR v2 ops into executable op records.
3. Consume executable op records before family-specific fallback blueprint when present.
4. Preserve operation IDs into mesh provenance.
5. Add unsupported-op diagnostics.
6. Retain current blueprint path as fallback.

First ops:

- `solid.panel`
- `op.trim_band`
- `op.fastener_grid`
- `op.vent_slats`
- `op.bevel`
- `op.chamfer`
- `op.socket`
- `op.bracket`
- `op.mount_plate`

Later ops:

- `op.hull`
- `op.minkowski`
- `op.distribute`
- `op.shell`
- `op.cut_panel_line`
- `op.weld_seam`
- `op.grime_mask`
- `op.scratch_mask`
- `op.chip_edges`

### Lane C: Feature Ops And Modularity

Goal:

- Replace chest-specific emitters with reusable feature operations.

Priority tasks:

1. Move feature operations into focused modules rather than one large `__init__.py` when touched.
2. Add generic distribution primitive: linear, grid, radial, arc, along_path.
3. Use component tags and target selectors rather than family equality.
4. Add count, density, spacing, jitter, mirror, snap, and seed controls.
5. Record instance count and target surface/face evidence.
6. Add stdlib fastener definitions later.

Feature ops to generalize:

- rivets;
- bolts;
- trim bands;
- corner guards;
- panel frames;
- vent slats;
- handle brackets;
- sockets;
- mount plates;
- weld seams;
- decals and trim bindings.

Acceptance:

- A crate, door, and one non-container asset can reuse the same operation.

### Lane D: Surface Graph, Bake, And Material Truth

Goal:

- Make final surfaces look authored and physically plausible enough for the asset class.

Priority tasks:

1. Fix tangent-space fallback normal bake.
2. Add a simple supersampled UV rasterizer for map generation.
3. Wire DesignerGraph evaluation to actual texture buffers.
4. Wire LayerStack evaluation to actual texture buffers where available.
5. Add HistogramScan/Levels, EdgeDetect, GradientMap, PositionMask, SlopeBlur incrementally.
6. Generate procedural high source from ShapeIR primitives.
7. Add OKLab blending for basecolor/material color mixes.
8. Add per-engine normal map convention outputs when packaging.
9. Add MaterialX stdlib lowering and colorspace tags.
10. Add map sidecars for `colorspace: srgb|linear|none`.

Later tasks:

- trim-sheet IR and atlas builder;
- per-face trim binding;
- decal placement IR;
- mip-aware dilation/padding;
- triplanar material fallback;
- parametric MaterialX nodegraph inputs;
- cel/painterly stylization nodes.

Acceptance:

- Material changes are visible in preview.
- Texture maps are not debug placeholders unless labeled.
- Engine/DCC export manifests state normal and colorspace conventions.

### Lane E: Topology, Retopo, And Mesh Finalization

Goal:

- Preserve hard-surface craft and produce engine-usable topology.

Priority tasks:

1. Confirm/fix Blender GLB import compatibility.
2. Keep Blender adapter truthful: attempted vs actual plus fallback reason.
3. Preserve multi-part scene names and part manifests.
4. Split normals or vertices along hard-edge classes where needed.
5. Preserve seam and bevel metadata through topology.
6. Add beauty-diagonal triangulation fallback.
7. Add Taubin smoothing for voxel-origin parts only.
8. Consider Instant Meshes provider once a narrow fixture can prove better topology.
9. Add topology report that names preserved/lost semantic groups.

Later tasks:

- hard-surface pipeline: bool cleanup -> adaptive bevel -> quad remesh;
- QuadriFlow fallback for organic;
- cross-field constraints from seam groups;
- decimation preserving UV seams and normals.

Acceptance:

- Topology stage does not erase visible detail added by shape stage.
- Fallback quality degradation is reported.

### Lane F: UV, Texel Density, Trim Sheets, UDIM

Goal:

- Make texture density and UV decisions auditable and art-directed.

Priority tasks:

1. Add texel-density audit after unwrap.
2. Honor asset-level target density.
3. Honor per-part importance weights.
4. Report density ratio, worst chart, worst part, and requested vs actual.
5. Avoid silent xatlas overrides where possible.
6. Add constrained packing with fixed chart sizes when feasible.

Later tasks:

- rectpack-based constrained packer;
- UDIM spillover;
- trim-sheet authoring and slot binding;
- BFF unwrapper for seam-group parts;
- OptCuts opt-in;
- triplanar by part/surface method.

Acceptance:

- Hero asset cannot hide extreme texel-density drift.
- UV fallback is visible in report.

### Lane G: Diagnostics, Validation, And Reports

Goal:

- Make certification correlate with human visual review.

Priority tasks:

1. Add visible-quality diagnostics that inspect output or evidence.
2. Add preview evidence completeness check.
3. Add debug-material final-preview check.
4. Add bevel/detail evidence check.
5. Add material-zone contrast check.
6. Add primary/secondary/tertiary balance check.
7. Add attachment seating check.
8. Add boolean fallback check.
9. Add fake high/low check.
10. Add box-stack or primitive/blockout detector.

Later tasks:

- multi-angle silhouette validator;
- frequency-energy validator;
- topology class compliance by asset type;
- PBR chart compliance;
- style stack compatibility;
- real-render validation lane.

Acceptance:

- A visually primitive artifact cannot pass as hero solely through metadata.
- Diagnostics produce actionable repair routes.

### Lane H: Semantic Repair And Regeneration

Goal:

- Make the repair loop real and deterministic.

Priority tasks:

1. Map one visible diagnostic to one allowed operation.
2. Keep patch schema narrow.
3. Reject unsafe syntax/contract edits.
4. Rebuild and compare before/after evidence.
5. Record metric deltas.
6. Add rollback for worse output if current repair loop supports it.

First mappings:

- weak hierarchy -> trim/fastener/vent detail;
- debug material -> non-debug surface defaults;
- attachment seating -> socket/bracket/mount plate;
- missing bevel evidence -> bevel/chamfer operation or unsupported diagnostic;
- fake high/low -> high-source generation or honest downgrade.

Acceptance:

- Repair changes actual output, not only metadata.

### Lane I: Authoring Surface And Stdlib Modularity

Goal:

- Make new assets possible without Python edits.

Priority tasks:

1. Enforce kit/HDA contracts: ports, parameters, ranges, units, enums, tooltips.
2. Add stdlib registry for versioned kits.
3. Add director vocabulary entries as stdlib compositions.
4. Promote field-style attr language for masks and scatter.
5. Add CGA-style assembly rules after terminals are stable.
6. Add reference-driven palette/silhouette/frequency extraction.

Do not start broad syntax work until execution can honor the claims.

Acceptance:

- New authoring constructs lower to existing operations or produce unsupported diagnostics.
- Public syntax changes update grammar, schema, checker, docs, examples, and tests together.

### Lane J: Multi-Domain Imagination-To-Life Demos

Goal:

- Preserve the product-wide capability direction while improving quality.

Existing demo domains to keep alive:

- hard-surface mechanical;
- vegetation;
- terrain;
- SDF organic;
- WFC modular;
- scatter;
- scatter on surface;
- capstone scene combining several paradigms.

Priority tasks:

1. Keep at least one hard-surface fixture as quality anchor.
2. Keep at least one non-hard-surface fixture as modularity guardrail.
3. Avoid overfitting all work to chest or crate.
4. Update demo catalog when new examples are added.
5. Use `lathe quick` for fast visual iteration where appropriate.

Acceptance:

- Product-wide demos continue to run or failures are documented as known blockers.

## 11. Phase Roadmap

This is the consolidated roadmap for sequencing beyond Sprint 0.

### Phase 0: Stop False Positives

Time horizon:

- Immediate to 1-2 weeks.

Goal:

- Make obvious weak outputs warn/fail honestly.

Deliverables:

- baseline evidence;
- preview evidence statuses;
- primitive/blockout detector;
- debug-material final-preview warning;
- boolean fallback diagnostic;
- hard-edge preservation check;
- tangent-space normal bake fix if in scope.

Do not:

- broaden syntax;
- tune thresholds to make old output pass;
- declare game-ready.

### Phase 1: Visible Hard-Surface Geometry

Time horizon:

- 4-8 weeks, depending on scope.

Goal:

- Make hard-surface assets visibly intentional.

Deliverables:

- boolean -> bevel(seam_group) chain;
- trim/fastener/vent operations;
- material zones and final beauty evidence;
- preview comparison sheets;
- diagnostics that catch weak hierarchy;
- one semantic repair mapping;
- initial KernelProgram seam.

Target assets:

- industrial_crate;
- mechanical_door;
- one guardrail such as fantasy_weapon or console_terminal.

### Phase 2: Real Surface And Kernel Bridge

Time horizon:

- 2-4 months.

Goal:

- Turn the visible slice into a durable internal architecture.

Deliverables:

- ShapeIR/ShapeIR v2 -> KernelProgram lowering;
- GeometryKernel execution with capability negotiation;
- semantic provenance through mesh/surface;
- DesignerGraph/LayerStack buffers;
- high-source from primitives;
- texel-density audit;
- MaterialX correctness;
- stronger preview/render validators.

### Phase 3: Procedural Domain Libraries

Time horizon:

- 6-9 months.

Goal:

- Expand product capability while preserving deterministic execution.

Deliverables:

- SpeedTree-inspired vegetation vocabulary;
- terrain heightfield plus erosion/material zones;
- WFC and CGA-style modular assembly;
- OpenSubDiv finishing;
- F-Rep/SDF sharper extraction;
- scatter and surface scatter as production multipliers;
- trim sheets and UDIM for hero surfaces.

### Phase 4: Organic And Animation-Forward Vocabulary

Time horizon:

- 12-18 months.

Goal:

- Add rig/anatomy/animation vocabulary without compromising deterministic substrate.

Deliverables:

- rig as typed data;
- parametric rig components;
- skin program;
- morph targets;
- canonical topology and rig families;
- animation library compatibility.

### Phase 5: Lathe Runtime And Engine Integration

Time horizon:

- 18-36 months.

Goal:

- Ship Lathe as live procedural runtime where it makes product sense.

Deliverables:

- engine runtime plugins or export lanes;
- USD generative procedural path;
- Unity/Unreal/Godot handoff with actual import evidence;
- live parameter overrides;
- signed package/repro evidence.

## 12. Style Band Priorities

Near-term:

- Band A: chunky/stylized low-poly.
- Band D: stylized PBR hard-surface.

Medium-term:

- Band F: toy/Lego/clay, via WFC and strict construction grammar.
- Band E partial: hard-surface and environment realistic, not photoreal humans.

Later:

- Band B: anime/cel, after stronger stylized material and anatomy support.
- Band C: painterly single-asset, not full directed sequence.
- Band G: hybrid, especially Astro-like PBR/stylized mixes.

Important:

- Style stack compatibility must refuse incoherent mixes.
- PBR, cel, painterly, toy, and realistic targets need different geometry/material defaults.
- Do not let a style label substitute for executable material/shading decisions.

## 13. Capability Parity Matrix

This matrix is the anti-false-positive shield.

| Claim | Real only when | Implementation standard |
| --- | --- | --- |
| Beveled/chamfered hard-surface edges | Mesh or normals show edge treatment and report names operation/kernel path | Build, prove, or report unsupported |
| Panelized surfaces | Panels appear in mesh/preview and have semantic region or material-zone evidence | No metadata-only panel claims |
| Vents/slats | Repeated geometry or cuts are visible and counted | Unsupported ops warn |
| Fasteners | Instances are visible, placed intentionally, and not random noise | Prefer generic distribute/scatter over family-specific emitters |
| Sockets/brackets/mounts | Attachments are visibly seated and tagged | Weak seating warns and can map to repair |
| Material zones | Final preview and material maps show distinct zones | Debug/material-ID preview is not final beauty |
| Edge wear/grime/scratches | Masks affect visible surface output | Proxy status must be explicit |
| Boolean cuts | Selected kernel reports success or fallback; artifacts show the cut | Fallback cannot silently certify hero quality |
| Swept/revolved/extruded profiles | Profile geometry appears and validates | Not a facade over box stacks |
| High/low detail | High source contains additional detail and bake transfer proves it | Subdivided low mesh alone is not real high/low |
| Texel density | Report names requested vs actual density and drift | Density cannot be invisible telemetry only |
| Trim sheets | UV rects/slot bindings affect final texture output | String handles alone are not enough |
| Game/Roblox readiness | Package evidence plus real or clearly labeled proxy import/readiness gates | Do not claim actual readiness from proxy evidence |
| Wonder readiness | Lathe can execute, inspect, repair, and report deterministic artifacts | Do not imply hosted/runtime proof without running it |

## 14. Decision Filter For Every Task

Before implementing, answer:

1. What visible claim does this make true?
2. Which asset or fixture proves it?
3. Which artifact path will show it?
4. Which diagnostic or report field will judge it?
5. Which repair route will use it, if any?
6. Does it preserve `.lth` compatibility and `lathe.shape.intent_mesh_handoff_v1`?
7. Does it avoid chest-only or one-family-only logic?
8. If it falls back, will users see attempted vs actual behavior?
9. What is the narrowest test or build that proves the change?
10. What claim remains explicitly not verified?

If the answers are weak, the task is not ready.

## 15. Allowed Claims Vocabulary

Use these terms consistently:

- `real`: produced by Lathe and visible in mesh/material/preview/export evidence.
- `proxy`: represented by deterministic placeholder or non-final evidence, explicitly labeled.
- `fallback`: requested path degraded to another path, with attempted and actual recorded.
- `unsupported`: rejected or warned before false success.
- `not verified`: code exists but no relevant command/artifact was produced in the current run.
- `blocked`: required dependency or upstream condition is missing and named.

Avoid these unless evidence supports them:

- production-ready;
- game-ready;
- Roblox-ready;
- Unity-ready;
- Unreal-ready;
- AAA;
- fixed;
- complete;
- done.

## 16. Recommended Commands

Use current exact paths if examples differ.

Baseline:

```powershell
git status --short
python -m lathe.cli check examples/industrial_crate.lth
python -m lathe.cli check examples/mechanical_door.lth
python -m lathe.cli build examples/industrial_crate.lth industrial_crate --out .tmp_tests/baseline_industrial_crate --deterministic
python -m lathe.cli build examples/mechanical_door.lth mechanical_door --out .tmp_tests/baseline_mechanical_door --deterministic
```

Preview/diagnostics:

```powershell
python -m pytest -q tests/unit/test_asset_quality_preview_evidence.py tests/unit/test_asset_quality_diagnostics.py tests/unit/test_asset_quality_generation_steering.py
```

Shape/geometry:

```powershell
python -m pytest -q tests/unit/test_shape_ir_v2.py tests/unit/test_asset_quality_grammar_lowering.py tests/unit/test_geometry_kernel.py
```

Surface:

```powershell
python -m pytest -q tests/unit/test_surface_runtime.py tests/unit/test_asset_quality_material_wear_graph.py
```

Kernel seam:

```powershell
python -m pytest -q tests/contract/test_shape_handoff_v1.py
```

Fast visual iteration:

```powershell
python -m lathe.cli quick examples/bevel_demo.lth bevel_demo --out tmp_bevel_demo.glb
python -m lathe.cli quick examples/alien_grove_showcase.lth alien_grove --out tmp_alien_grove.glb --no-cache
```

Run broader checks only after targeted checks are green or when the touched surface requires them.

## 17. Source Inputs Consolidated

This document consolidates:

- `docs/asset-quality/lathe-context-problem-solution-goals-success-criteria.md`
- `docs/asset-quality/phase1-phase2-visible-geometry-upgrade-guide.md`
- `docs/asset-quality/visible-geometry-sprint-0-implementation-plan.md`
- `docs/imagination_to_life_session_report.md`
- `plans/lathe_imagination_to_life_roadmap.md`
- `lathe_quality_research.md`
- `research/SYNTHESIS_blockers_and_breakthroughs.md`
- `research/audit_shape_blockers.md`
- `research/openscad_lessons.md`
- `research/sota_geometry.md`
- `research/sota_topology_uv.md`
- `research/sota_surface_materials.md`
- `research/sota_art_direction.md`
- `CLAUDE.md`
- `README.md`

## 18. What To Implement Next

Unless the user redirects, the next implementation sequence is:

1. Create `docs/asset-quality/visible-geometry-sprint-0-evidence.md` and capture baseline crate/door evidence.
2. Strengthen preview evidence payload and artifact path reporting.
3. Implement one visible operation for industrial crate: trim band or fastener grid first, bevel/chamfer if safe.
4. Add diagnostics that flag weak hierarchy, missing detail, debug material look, and proxy preview evidence.
5. Wire one semantic repair mapping from weak hierarchy to a concrete detail operation.
6. Rebuild crate and record before/after preview, report metrics, and package artifacts.
7. Add private `KernelProgram` seam only after the vertical slice has visible evidence.
8. Fix surface truth bugs touched by the slice, especially tangent-space normals and material-zone visibility.
9. Harden topology/UV only where the visible detail is being lost or misrepresented.
10. Use the guardrail fixture to prove the work is not crate-only.

This is the first path. Do not skip to broad Phase 3 or Phase 4 work until Sprint 0 creates undeniable visible proof.

## 19. Bottom Line

Lathe does not win by adding more words faster than the engine can honor them.

Lathe wins by making this loop undeniable:

```text
intent -> artifact -> evidence -> judgment -> repair -> better artifact
```

The next implementation work should stay on that loop until it is visibly true.
