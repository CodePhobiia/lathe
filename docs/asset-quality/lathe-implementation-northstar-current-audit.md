# Lathe Implementation Northstar Current Audit

Date: 2026-05-11
Source of truth audited: `docs/asset-quality/lathe-implementation-northstar.md`
Repository root: `<repo-root>`

## Verdict

Lathe has moved from "language and reports ahead of execution" into an early real vertical slice:

```text
authored hard-surface intent -> construction/kernel path -> package artifacts -> previews/reports
```

That is a real breakthrough, but it is not the northstar finish line. The current state is best described as:

```text
Sprint 0 artifact/execution breakthrough achieved; Phase 1 visible hard-surface geometry is underway;
Phase 2 kernel/surface architecture has early pieces; Lathe is not yet ready to be judged as a
high-quality asset-production product.
```

The most important distinction:

- We can now produce certified package/export artifacts for the Sprint 0 crate/door evidence fixtures.
- We also produced a richer treasure-chest package after fixing root transform/provenance/validator/cache bugs.
- The visual bar is still not good enough for the product goal. Certification and output existence are not the same thing as "Lathe can reliably make good assets."

## Current Git And Artifact State

Current branch:

```text
main...origin/main [ahead 4]
```

Recent commits in the current line include:

- `b706e94 fix: stabilize hard-surface mesh builds`
- `2110c49 fix(uv): restore feature_semantics.panel_seams precedence for seam_guides`
- `ef9930d test: align unit tests with ShapeIR v2 expansion and downstream contract changes`
- `f266388 docs(asset-quality): correct stale module paths in goal session report`

The worktree is still dirty with additional uncommitted source changes and generated artifacts. Important uncommitted areas include:

- `lathe/asset_quality/grammar_lowering.py`
- `lathe/bake_runtime.py`
- `lathe/core/stages/validate.py`
- `lathe/materials.py`
- `lathe/mesh_program/__init__.py`
- `lathe/shape/backend.py`
- `lathe/shape/mesh_program_path.py`
- `lathe/surface_runtime.py`
- `lathe/validators/composition.py`
- `lathe/validators/geometry_integrity.py`
- `lathe/validators/semantic_quality.py`
- `examples/treasure_chest.lth` (untracked)
- many `.tmp_treasure_chest_build_*` and `.tmp_tests/*` output directories

This audit treats committed code plus current working-tree code/artifacts as the current session state, but any future "stable baseline" should either commit or intentionally discard the remaining dirty work.

## Northstar Status Summary

| Northstar Area | Current Status | Honest Claim |
| --- | --- | --- |
| Rule of Truth | Partially satisfied | Artifacts and reports now exist for key fixtures, and fallback/cache state is more explicit. Visual quality still needs human alignment. |
| Sprint 0 | Mostly achieved for execution/artifacts, not for final visual product quality | Crate and door package/export through evidence paths. The "obvious in five seconds" standard is still questionable. |
| Geometry/CSG | Strong progress | Exact/kernel paths, Manifold-oriented CSG, polybevel, mesh-backed primitives, and world-space semantics exist. Still large and brittle. |
| ShapeIR v2 as driver | Partial but real | ShapeIR v2 and mesh-program operations lower into executable geometry in multiple paths. It is not yet cleanly modular or fully operation-driven. |
| Feature ops/modularity | Partial | Fastener/trim/vent/part output controls exist, but broad family-independent authoring still needs consolidation. |
| Surface/bake truth | Partial | Tangent-space normal handling, high/low transfer, wear/material masks, and graph buffers exist. The generated look still reads procedural and not product-grade. |
| Topology preservation | Partial | Semantic preservation and adapter tracing exist; craft can still be erased or simplified. |
| UV/texel density | Early partial | Adapter reporting and texel-density fields exist; full audit with worst chart/part and requested-vs-actual is not complete. |
| Visible diagnostics | Partial | Primitive/blockout, support, curvature, semantic/toy metrics have improved. They are still not enough to replace human visual judgment. |
| Semantic repair | Early partial | Repair routing can add feature primitives for some diagnostics/actions. The full diagnose -> repair -> rebuild -> better artifact loop is not mature. |
| Multi-domain demos | Present but not current focus | Vegetation, terrain, SDF, WFC, scatter domains exist as direction, but hard-surface quality must remain the anchor. |

## Sprint 0 Audit

### S0-1 Baseline Evidence

Status: done as an evidence ledger, though it is dated and should be refreshed after the latest commits.

Evidence:

- `docs/asset-quality/visible-geometry-sprint-0-evidence.md:1` identifies the Sprint 0 evidence doc.
- `docs/asset-quality/visible-geometry-sprint-0-evidence.md:4` claims Sprint 0 primary and guardrail acceptance achieved.
- `docs/asset-quality/visible-geometry-sprint-0-evidence.md:33-36` records the current allowed claim for crate/door package/export.
- `docs/asset-quality/visible-geometry-sprint-0-evidence.md:961-965` says current bounded Manifold full-CSG builds pass validation and package/export.

Current artifact verification:

- `.tmp_tests/visible_geometry_sprint0_20260505/after_skip_subdivision_manifold_csg_timeout900_industrial_crate/industrial_crate/build_report.json`
  - `certified: true`
  - `score: 0.86902`
  - `threshold: 0.84`
  - `outputs: 13`
- `.tmp_tests/visible_geometry_sprint0_20260505/after_surface_normal_gain_v3_timeout900_mechanical_door/mechanical_door/build_report.json`
  - `certified: true`
  - `score: 0.876168`
  - `threshold: 0.84`
  - `outputs: 12`

Audit note:

The evidence doc proves artifact reachability, but it should not be used to claim final product-grade visual quality.

### S0-2 Preview Evidence

Status: partial to mostly done for package-level previews.

Evidence:

- `lathe/core/stages/package.py:1199` writes `turntable.png`.
- `lathe/core/stages/package.py:1203` writes `wireframe.png`.
- `lathe/core/stages/package.py:1207` writes `material_ids.png`.
- `lathe/asset_quality/preview_evidence.py:640` evaluates preview evidence.
- `lathe/core/stages/validate.py:104` registers the `preview_evidence` validator.

Artifact examples:

- `.tmp_tests/visible_geometry_sprint0_20260505/after_skip_subdivision_manifold_csg_timeout900_industrial_crate/industrial_crate/stages/package/previews/turntable.png`
- `.tmp_tests/visible_geometry_sprint0_20260505/after_surface_normal_gain_v3_timeout900_mechanical_door/mechanical_door/stages/package/previews/turntable.png`
- `.tmp_treasure_chest_build_cache_skip_fix/treasure_chest/stages/package/previews/turntable.png`

Remaining gap:

The northstar asks for stronger multi-view evidence such as orthographic front/top/three-quarter and comparison sheets. The current package preview set is useful, but not the complete inspection model.

### S0-3 Visible Geometry Detail Operation

Status: real progress, but not yet cleanly complete.

Evidence:

- `lathe/mesh_program/__init__.py:10487` accepts `part`, `output_part`, and `component_part` aliases for a feature op output.
- `lathe/mesh_program/__init__.py:10708` does the same for another hard-surface feature op.
- `lathe/mesh_program/__init__.py:10906` does the same for another hard-surface feature op.
- `lathe/exact_solids.py:4523` attempts kernel-program lowering for fastener grids.
- `lathe/exact_solids.py:4691` attempts kernel-program lowering for vent slats.
- `lathe/exact_solids.py:17461` contains the post-boolean seam/polybevel path.
- `lathe/exact_solids.py:25342-25363` records post-boolean polybevel stats in the exact report.

Current truth:

Feature operations are no longer just metadata in all cases. Some produce visible geometry and traceable operation records.

Remaining gap:

The operation layer is still broad and dense rather than a clean, small `KernelProgram` API. It works, but it is not yet the elegant operation-driven architecture the northstar wants.

### S0-4 Surface Defaults And Material Truth

Status: partial.

Evidence:

- `lathe/bake_runtime.py:773` bakes normal maps.
- `lathe/bake_runtime.py:788-789` keeps no-tangent fallback honest as neutral tangent-space rather than world-space normals.
- `lathe/surface_runtime.py:703` builds high source from ShapeIR/shape-stage source when available.
- `lathe/surface_runtime.py:2768-2808` writes high-source evidence.
- `lathe/surface_runtime.py:2897-2907` writes a `normal_map_report`.
- `lathe/surface_runtime.py:2935-2957` applies surface graph buffers and records whether normal/detail buffers were applied.
- `lathe/surface_runtime.py:3052-3055` writes wear/material-layer masks when generated.

Current truth:

The surface system is much more truthful than the old "debug material" era. It has tangent-space normal reporting, high/low projection policy, and actual texture outputs.

Remaining gap:

The output still does not look good enough. The northstar is about visually convincing assets, and current procedural materials still need a stronger art-direction layer, better masks, and better final beauty.

### S0-5 Human-Visible Diagnostics

Status: partial.

Evidence:

- `lathe/validators/visual_quality.py:75` evaluates support plausibility.
- `lathe/validators/visual_quality.py:862-915` includes the render primitive complexity signal and related primitive/assembly metrics.
- `lathe/validators/curvature_distribution.py:30` defines the curved-vertex target.
- `lathe/validators/curvature_distribution.py:118-127` combines legacy and curved-score curvature paths.
- `lathe/validators/semantic_quality.py:420` emits semantic fragmentation failure.
- `lathe/validators/semantic_quality.py:439-449` emits toy/primitive detection.

Current truth:

Validators are less metadata-only than before and now catch more visible structure problems.

Remaining gap:

The validator system still certified assets that the user judged visually inadequate. So the northstar's "certification must correlate with human review" is not done.

### S0-6 Semantic Repair Mapping

Status: early partial.

Evidence:

- `lathe/repair_loop.py:137-166` maps repair-policy operations/requests to feature names including trim bands, fastener grids, vent slats, panels, brackets, mounts, sockets, grime, and weld seams.
- `lathe/repair_executor.py:19-28` allowlists several v2 repair operations.
- `lathe/repair_executor.py:117-141` implements `add_secondary_features` using trim-band and fastener-strip feature primitives.

Current truth:

There is a deterministic bridge from repair actions to executable feature primitives.

Remaining gap:

This is not yet a mature Wonder-style loop. The audit did not verify a current baseline diagnostic automatically producing a patch, rebuilding, and generating a visibly better package.

### S0-7 KernelProgram Seam

Status: started, now under the canonical file names named by the northstar.

Evidence:

- `lathe/geometry/kernel_program.py:22` defines `KERNEL_PROGRAM_VERSION`.
- `lathe/geometry/kernel_program.py:62` defines `KernelProgramResult`.
- `lathe/geometry/shape_ir_lowering.py:1022` executes a ShapeIR boolean program.
- `lathe/geometry/shape_ir_lowering.py:1153` executes a broader ShapeIR kernel program.
- `lathe/geometry/kernel_program.py` contains extensive kernel-program execution and semantic handoff logic.
- `lathe/core/stages/package.py:683-872` pulls kernel-program manifests and operation records into construction provenance.

Not present as dedicated narrow test files:

- `tests/unit/test_geometry_kernel_program.py`
- `tests/unit/test_shape_ir_kernel_lowering.py`

Current truth:

The seam exists materially under the clean module names named by the northstar, but it is still large and concentrated in `lathe/geometry/kernel_program.py` and `lathe/geometry/shape_ir_lowering.py`.

### S0-8 Final Sprint Evidence

Status: execution evidence exists; final visual acceptance remains weak.

Evidence:

- Crate and door build reports exist and certify under the Sprint 0 evidence root.
- Treasure chest now builds a package at `.tmp_treasure_chest_build_cache_skip_fix/treasure_chest`.
- Treasure chest `build_report.json` reports:
  - `certified: true`
  - `score: 1.0`
  - `threshold: 0.78`
  - `outputs: 11`
  - `manifest_path: stages/package/package_manifest.json`
  - `trace_path: stages/package/trace_manifest.json`
  - `cache.reason: output_tree_exceeds_auto_cache_limit`

Current truth:

The build/export pipeline is real enough to inspect and debug. It is not yet visually convincing enough to shift focus to asset production.

## Post-Sprint Breakthrough Audit

The latest treasure-chest work fixed several root causes that directly support the northstar:

1. World-space mesh-backed semantics:
   - `lathe/exact_solids.py:19193` adds the shared mesh-backed primitive conversion helper.
   - `lathe/exact_solids.py:19507` records `mesh_vertices_space: world_cm`.
   - `lathe/exact_solids.py:19771` records `mesh_vertices_space: world_cm` for another mesh-backed path.
   - `lathe/asset_quality/shape_ir_v2.py:2355` detects baked world-space mesh records.
   - `lathe/asset_quality/shape_ir_v2.py:6535-6567` writes kernel mesh records with `mesh_vertices_space: world_cm`.

2. Selector/provenance schema truth:
   - `schema/lathe.selector.schema.json:393-398` accepts emitted scatter provenance fields such as `target`, `meshFaceIndex`, `sampleIndex`, `instanceCount`, `pointSet`, and `pointIndex`.

3. Validator axis/curvature fixes:
   - `lathe/validators/visual_quality.py:75` fixes support plausibility around inferred support/floor axes.
   - `lathe/validators/visual_quality.py:862-915` records the render complexity signal used to avoid penalizing real detailed silhouettes as primitive.
   - `lathe/validators/curvature_distribution.py:118-127` gives detailed assets a non-flat curvature score path.

4. Build hang/cache stabilization:
   - `lathe/executor.py:105` sets a 64 MiB auto-build-cache persistence limit.
   - `lathe/executor.py:1051-1079` records cache footprint and skips oversized cache persistence instead of making successful builds appear hung.

These are real northstar-aligned fixes because they make the pipeline more truthful and less success-shaped.

## Implementation Lanes Audit

### Lane A: Geometry Kernel And CSG

Status: strong progress, not complete.

What exists:

- Explicit kernel and reference/manifold modules exist under `lathe/geometry/`.
- `lathe/geometry/kernel_program.py` and `lathe/geometry/shape_ir_lowering.py` have extensive KernelProgram-style execution.
- Exact-solids reports operation records, polybevel stats, fallback state, body/watertight evidence, and world-space mesh semantics.

Remaining:

- Capability negotiation and backend chain need simplification.
- Some fallback paths are still complex and can be visually weak.
- The code size and concentration in `exact_solids.py` and `geometry/program.py` are maintainability risks.

### Lane B: ShapeIR v2 And Construction Graph As Drivers

Status: partial.

What exists:

- ShapeIR v2 contains semantic operations and contextual target resolution.
- ShapeIR -> kernel-program execution exists.
- Operation records are preserved into package construction provenance.

Remaining:

- The driver path is not consistently primary across all asset families.
- Unsupported-op diagnostics and approximated-vs-executed status need tighter public reporting.

### Lane C: Feature Ops And Modularity

Status: partial.

What exists:

- Mesh-program operations can emit trim/fastener/vent features with explicit output parts.
- Repair executor can add some of these features.

Remaining:

- Generic distribution, density, jitter, mirror, snap, and stdlib feature definitions need consolidation.
- Avoiding chest/container-style special casing remains an active risk.

### Lane D: Surface Graph, Bake, And Material Truth

Status: partial.

What exists:

- Tangent-space normal handling exists.
- High-source/projection reporting exists.
- Surface graph buffers can influence actual maps.
- Wear and material layer masks can be generated.

Remaining:

- Materials still need stronger visual art direction.
- DesignerGraph/LayerStack coverage is not yet broad enough.
- Engine/DCC color and normal conventions are better reported but not enough for true readiness claims.

### Lane E: Topology, Retopo, And Mesh Finalization

Status: partial.

What exists:

- Topology adapter reports actual adapter/fallback state.
- Semantic preservation reports exist.
- Seam/bevel config can flow into topology adapter setup.

Remaining:

- Topology can still erase craft.
- Need stronger reports for preserved/lost semantic groups.
- Real quad-remesh provider path is not proven as a quality upgrade.

### Lane F: UV, Texel Density, Trim Sheets, UDIM

Status: early partial.

What exists:

- UV bundles include adapter report and texel-density fields.
- Some UDIM/trim-sheet language/tests exist.

Remaining:

- Full texel-density audit is not complete: worst chart, worst part, requested-vs-actual, and actionable density drift diagnostics are still needed.
- Trim-sheet binding is not yet visibly affecting final hard-surface output at the level the northstar wants.

### Lane G: Diagnostics, Validation, And Reports

Status: partial.

What exists:

- Preview evidence validator is integrated.
- Visual, semantic, curvature, geometry-integrity, and composition validators have richer metrics.
- Package reports include construction provenance and surface material semantics.

Remaining:

- Certification still does not reliably match human visual judgment.
- Need stricter visual blocker diagnostics and fewer ways for mediocre output to certify.

### Lane H: Semantic Repair And Regeneration

Status: early partial.

What exists:

- Diagnostic/repair action mapping has a concrete operation vocabulary.
- Repair executor can add feature primitives.

Remaining:

- The full closed loop remains unproven as a product capability.
- Need artifact-level before/after comparison and rollback/avoid-worse-output behavior.

### Lane I: Authoring Surface And Stdlib Modularity

Status: early.

What exists:

- Some stdlib, kit, surface, and director vocabulary structures exist.

Remaining:

- New asset families still risk needing Python edits.
- Broad public syntax work should remain blocked until the engine honors current claims.

### Lane J: Multi-Domain Imagination-To-Life Demos

Status: present but not current target.

What exists:

- Demos/domains for vegetation, terrain, SDF, WFC, scatter, and surface scatter exist in the broader repo direction.

Remaining:

- These should stay alive as guardrails, not become the main work until hard-surface quality is more convincing.

## What Is Actually Complete

Complete or stable enough to treat as real:

1. Stable public `.lth` compatibility was preserved through the recent work.
2. The stable `lathe.shape.intent_mesh_handoff_v1` contract remains the shape-stage boundary.
3. Sprint 0 no longer fails at "no visible artifacts."
4. Industrial crate and mechanical door have certified package/export artifacts under the Sprint 0 evidence root.
5. Treasure chest builds a package and selector manifest after the world-space/provenance/cache fixes.
6. World-space mesh-backed primitive handling is fixed in committed code.
7. Selector manifest schema accepts provenance that the writer actually emits.
8. Oversized auto-cache persistence no longer turns successful builds into apparent hangs.

## What Is Not Complete

Not complete and should not be claimed:

1. Lathe is not yet ready to generate visually good assets as a product.
2. Sprint 0 is not a proof that certification equals visual quality.
3. The hard-surface operation system is not yet a clean, small, generally reusable authoring layer.
4. The semantic repair loop is not mature enough to be the Wonder revision substrate.
5. UV/texel-density evidence is not yet strong enough for hero-quality surface claims.
6. Engine import/readiness claims are not proven by current artifacts.
7. Multi-domain imagination-to-life demos are not the next main implementation priority.

## Recommended Next Implementation Sequence

The next work should follow this order:

1. Stabilize and commit the remaining uncommitted runtime changes that are truly northstar-aligned.
2. Decide whether `examples/treasure_chest.lth` is a temporary proof fixture or a checked-in canonical hard-surface guardrail.
3. Refactor the KernelProgram seam out of the huge concentrated paths into clearer modules without changing public syntax.
4. Make one operation family fully clean end-to-end:
   - authored intent;
   - lowered operation;
   - visible mesh output;
   - provenance;
   - topology/UV/surface preservation;
   - diagnostic;
   - repair mapping.
5. Use crate, door, and treasure chest as guardrails, but do not optimize only for those shapes.
6. Improve visual final beauty next, specifically:
   - material-zone contrast;
   - surface graph mask quality;
   - non-debug lighting/preview;
   - believable wear/grime/edge treatment.
7. Add a real texel-density audit once visible geometry and material zones are stable enough that UV quality matters.

## Audit Bottom Line

The northstar is still the right document.

Where we are:

```text
We have crossed the "Lathe cannot produce visible/package evidence" blocker.
We have not crossed the "Lathe produces consistently good-looking authored assets" blocker.
```

The next implementations should stay on Lathe itself:

```text
operation kernel -> semantic provenance -> topology/UV/surface preservation -> visual judgment -> deterministic repair
```

Do not spend the next push primarily on more demo assets or more quality gates. Use assets only as proof fixtures for engine capability.
