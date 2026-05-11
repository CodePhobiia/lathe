# Lathe Northstar Full Implementation Plan

Date: 2026-05-11
Status: Canonical end-to-end sequencing plan for completing
`docs/asset-quality/lathe-implementation-northstar.md` in full
Scope: All 10 lanes (A-J), all 13 blockers (B0-B12), all 5 phases,
plus the procedural synthesizer (`procedural-synthesizer-architecture-spec.md`)
that resolves B12 and unblocks Lanes B/C/I
Companion docs: `lathe-implementation-northstar.md` (intent),
`lathe-implementation-northstar-current-audit.md` (current state),
`procedural-synthesizer-architecture-spec.md` (one architectural slice)

This document is the master plan. The northstar declares what; this
declares when and in what order. Each cycle ships production-grade
work — no MVPs, no scaffolding-labelled-as-shipping, no demo assets
masquerading as proof. Verification per cycle is the floor under
"this works," not ceremony.

## 0. How This Plan Is Used

Read this when:

1. Picking up a new session and deciding what to do next.
2. Sequencing work across multiple agents/sessions.
3. Tracking northstar completion progress.
4. Resolving "should we do X next or Y" questions.
5. Reporting status to stakeholders.

The plan is laid out as **eight cycles** of work. Each cycle:

- Has a stable goal (a sentence the user could state).
- Names the lane(s) and blocker(s) it advances.
- Lists concrete deliverables (files, modules, or capabilities).
- Specifies acceptance criteria (what production-grade looks like).
- Identifies dependencies on prior cycles.
- Bounds effort in sessions (1 session ≈ 2-6 focused hours).

Cycles 1-3 are the procedural-engine foundation. Cycles 4-5 close the
imagination-to-life visible loop. Cycles 6-8 are domain expansion,
animation vocabulary, and engine integration.

## 1. Starting Position (Audit-Confirmed)

Per `lathe-implementation-northstar-current-audit.md` plus the
seam-refactor commits from session 2026-05-11:

**Done (committed):**

- Sprint 0 artifact-execution chain: industrial_crate, mechanical_door,
  treasure_chest produce certified package/export artifacts.
- World-space mesh-backed primitive handling (`b706e94`).
- Selector manifest schema accepts emitted provenance (`b706e94`).
- Auto-cache persistence does not turn successful builds into hangs
  (`b706e94`).
- KernelProgram seam factored into `kernel_program.py` /
  `shape_ir_lowering.py` per northstar S0-7 (`2bb70fa`).
- Procedural synthesizer architecture specced (`97c8666`).

**Honest open state:**

- Sprint 0 visual quality: certified outputs still read as procedural
  blockout, not finished assets.
- Lane A geometry kernel: strong but brittle; 12K-line concentration
  in `kernel_program.py`; some boolean fallbacks silent.
- Lane B ShapeIR v2 driver: 73 family recipes still dispatch on
  family name; brief/parts/graph_nodes ignored by recipes.
- Lane C feature ops: partial; chest/crate-specific emitters remain.
- Lane D surface: tangent-space normals partial; final beauty weak.
- Lane E topology: can erase craft; Blender path optional and traced.
- Lane F UV: early partial; texel-density audit incomplete.
- Lane G diagnostics: partial; certification not yet correlated to
  human judgment.
- Lane H repair: early partial; full closed loop not proven.
- Lane I authoring stdlib: early; family rules in Python.
- Lane J multi-domain: present but not the current target.

This plan starts from that state and sequences forward.

## 2. Operating Principles (Inherited From Northstar §5)

Every cycle must respect:

- **Public `.lth` source compatibility.**
- **Stable `lathe.shape.intent_mesh_handoff_v1` contract.**
- **Public language surface** around `profile`, `contract`, `critic`,
  `asset`, `variant`, build-stage names.
- **Attempted-vs-actual tracing** for providers, kernels, renderers,
  topology adapters, UV adapters, package exporters.
- **No expansion of public syntax** before the internal execution path
  proves visible output.
- **No fake evidence** of any kind.
- **No chest-only or family-only logic.** Generalize via tags,
  component roles, asset class, operations, or stdlib data.
- **No validators rewarding metadata completeness over visible quality.**
- **No "production-ready" or "game-ready" claims** unless evidence
  was generated and checked.

Production-grade per cycle means:

- The code is the real thing, not a scaffold.
- The verification floor (targeted unit tests + at least one full
  build path where applicable) is green at session end.
- The output is committed and pushed.
- The honest claim vocabulary (`real | proxy | fallback | unsupported |
  not verified | blocked`) governs every report field.

## 3. Cycle Sequencing Overview

```
                         CURRENT STATE
                              │
                              ▼
        ┌─────────────────────────────────────────────┐
        │  CYCLE 1: Procedural Engine Foundation      │  Lane B core
        │  (synthesizer skeleton + core generators)   │  resolves B12
        └─────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────┐
        │  CYCLE 2: Kernel Capability Closure         │  Lane A
        │  (every ShapeIR v2 op executes or honestly  │  resolves B3-B5
        │   diagnoses; kernel_program.py decomposed)  │  partial B4
        └─────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────┐
        │  CYCLE 3: Recipe Decommissioning            │  Lane B + I
        │  (all 73 _RECIPES migrated to data packs    │  resolves B12
        │   driven by the generic engine)             │  completes B1
        └─────────────────────────────────────────────┘
                              │
                  ┌───────────┴───────────┐
                  ▼                       ▼
        ┌──────────────────┐    ┌──────────────────┐
        │  CYCLE 4: Visual │    │  CYCLE 5: Quality│
        │  Layer Truth     │    │  Loop Closure    │
        │  Lanes D+E+F     │    │  Lanes G+H       │
        │  B6,B7,B8,B9     │    │  B10, B11        │
        └──────────────────┘    └──────────────────┘
                  │                       │
                  └───────────┬───────────┘
                              ▼
        ┌─────────────────────────────────────────────┐
        │  CYCLE 6: Multi-Domain Expansion (Phase 3)  │  Lane J
        │  (vegetation, terrain, WFC, CGA, SDF,       │
        │   scatter, OpenSubDiv finishing)            │
        └─────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────┐
        │  CYCLE 7: Animation Vocabulary (Phase 4)    │
        │  (rig as typed data, skin, morph, canonical │
        │   topology + rig families, anim library)    │
        └─────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────┐
        │  CYCLE 8: Engine Integration (Phase 5)      │
        │  (USD procedural, Unity/Unreal/Godot/Roblox │
        │   handoff with real import evidence,        │
        │   signed package/repro)                     │
        └─────────────────────────────────────────────┘
                              │
                              ▼
                       NORTHSTAR COMPLETE
```

Cycles 4 and 5 may overlap (cycle 5 needs cycle 4's visible output
to judge, but partial cycle 4 enables partial cycle 5). Cycles 1-3
are strictly sequential — each unblocks the next.

## 4. Cycle 1: Procedural Engine Foundation

### 4.1 Goal

Replace the 73-recipe family-name dispatch in
`grammar_lowering.py` with a generic procedural engine driven by
typed construction-graph nodes and informed (not dispatched) by
declarative FamilyKnowledge packs. Family becomes metadata, never a
discriminator.

### 4.2 Lanes And Blockers Advanced

- **Lane B** (ShapeIR v2 As Drivers) — primary
- **Lane C** (Feature Ops And Modularity) — substrate
- **Lane I** (Authoring Surface And Stdlib Modularity) — substrate
- **B12** (Chest-Specific Code Is A Product Smell) — core resolution
- **B1** (Authored Intent Dies Before Geometry) — partial resolution

### 4.3 Concrete Deliverables

Per `procedural-synthesizer-architecture-spec.md` §5 and §12:

```
lathe/asset_quality/procedural_synthesizer/
    __init__.py
    context.py                  # SynthesizerContext, _build_context
    synthesizer.py              # outer loop + registries
    trace.py                    # SynthesizerTrace schema
    hint_resolution.py          # priority-merge logic
    generators/
        __init__.py
        primary_volume.py       # generic primary_volume → ShapeOp
        panel.py
        fastener.py
        trim.py
        decal_zone.py
        guard.py                # cycle 1 stops here at 6 generators
        # remaining 14 generators stub-only, returning empty
    decorators/
        __init__.py
        attached_to.py
        mirrors.py
        aligned_with.py
        # remaining 4-5 stub-only
    knowledge/
        __init__.py             # empty registry, populated in cycle 3

tests/unit/test_procedural_synthesizer_foundation.py
tests/unit/test_procedural_synthesizer_primary_volume.py
tests/unit/test_procedural_synthesizer_panel.py
tests/unit/test_procedural_synthesizer_fastener.py
tests/unit/test_procedural_synthesizer_trim.py
tests/unit/test_procedural_synthesizer_decal_zone.py
tests/unit/test_procedural_synthesizer_guard.py
```

Plus a routing change in `grammar_lowering.py`:

- Unknown families (those NOT in `_RECIPES`) route to
  `synthesize_shape_program` instead of `_empty_recipe`.
- An optional `_MIGRATED_TO_SYNTHESIZER` allowlist exists for use in
  cycle 3.

### 4.4 Acceptance Criteria

- Six generators implemented end-to-end with hint-resolution
  semantics per spec §3.4. Each is ≤ 300 lines.
- An unknown-family fixture produces a non-empty, geometrically
  valid ShapeProgram entirely from its construction graph.
- Same family, different brief produces different ShapeProgram
  output (intent dominance proven).
- `family_dispatch_used: false` in trace for synthesizer-routed
  programs.
- 73 family recipes still pass their existing tests (coexistence).
- Targeted suite green: synthesizer tests + grammar_lowering tests
  + shape_handoff_v1 contract.

### 4.5 Dependencies

None — builds directly on the seam refactor from session
2026-05-11.

### 4.6 Estimated Effort

3-5 sessions.

## 5. Cycle 2: Kernel Capability Closure

### 5.1 Goal

Every ShapeIR v2 operation (83 total across SOLID/BOOLEAN/EDGE/SOP/
REPETITION/INTEGRATION/WEAR families) either executes through the
kernel or emits an honest `unsupported` diagnostic. No silent fallback,
no metadata-only success. `kernel_program.py` is decomposed by
operation kind into per-op modules.

### 5.2 Lanes And Blockers Advanced

- **Lane A** (Geometry Kernel And CSG) — primary, comprehensive
- **B3** (CSG And Exact Paths Have Been Too Narrow Or Too
  Fallback-Oriented) — resolved
- **B4** (Bevels, Chamfers, And Edge Treatments) — partial resolution
- **B5** (Feature Density Not Yet Author-Controllable) — partial via
  generic distribute/scatter

### 5.3 Concrete Deliverables

**Decomposition of `kernel_program.py`** (currently 12,177 lines):

```
lathe/geometry/kernel_program/
    __init__.py                 # re-exports preserving public API
    _core.py                    # KernelOperand, KernelProgramResult,
                                # KernelProgramCapabilityError
    _capabilities.py            # capability resolution helpers
    _serialize.py               # all _compact_* helpers
    _semantic.py                # semantic_metadata_from_primitive, etc.
    _aggregate.py               # _aggregate_context_record family
    boolean.py                  # execute_boolean_program + helpers
    hull.py
    minkowski.py
    transform.py
    deform.py
    refine.py
    carve.py
    polyextrude.py
    profile_path.py
    sdf_field.py
    terrain_field.py
    import_op.py                # the file-ingest op
    instances.py
    component_assembly.py
```

Target: every file ≤ 1500 lines.

**Lane A priority task completions:**

1. **Manifold promoted ahead of fallback** where primitive coverage
   is sufficient. Capability negotiation drives the choice, not
   family name (`exact_solids.py` family gates removed).
2. **Missing primitive coverage in Manifold path.** Specifically:
   - lofted solid
   - twist on extruded profiles
   - partial rotate extrude
   - helical sweep
   - involute gear primitive
   - bend/twist/taper deformers (Lane A "future tasks" promoted)
3. **Backend chain telemetry** consistent across all executors:
   `attempted_backend`, `actual_backend`, `fallback_reason`,
   `unsupported_primitives`, `capability_diagnostics`. Trace fields
   uniform.
4. **Strict geometry mode failure** for invalid hero claims. New
   asset-level field `geometry_strictness: strict | permissive` (in
   the brief, not the language surface). Strict mode rejects rather
   than degrades.
5. **Mesh-to-levelset repair** as last-resort fallback, **always
   emits a degraded-status diagnostic**.
6. **`boolean_csg_fallback` diagnostic** completion — confirms the
   existing diagnostic surface from `kernel_program.py:6550` is
   wired into every boolean execution path, with audit coverage.
7. **Unsupported-op uniform reporting** — every of the 83 ShapeIR
   v2 ops has a known `executed | approximated | unsupported` state
   in the kernel trace. A test asserts complete coverage.

### 5.4 Acceptance Criteria

- `kernel_program.py` is replaced by `kernel_program/` package.
  Public surface preserved (every symbol in `lathe.geometry`
  package `__init__` still accessible by the same name from the
  same import path).
- No file in the package exceeds 1500 lines.
- For each of 83 ShapeIR v2 ops, the kernel trace contains an
  explicit `executed | approximated | unsupported` state.
  Automated test enforces this enumeration.
- `manifold_v1` chosen ahead of fallback whenever capability resolution
  permits. A test fixture proves this for at least 5 distinct primitive
  sets.
- 5 new primitive/operation coverage paths in Manifold from the list
  above, each with unit test + integration into the kernel trace.
- Backend chain telemetry uniform: a single test inspects every
  executor's emitted trace and asserts the four required fields are
  present.
- Strict geometry mode test: a hero-quality claim with strict mode
  on, where Manifold falls back, must surface a failure rather than
  certify.
- All 136+ tests from the seam-refactor verification slice continue
  to pass.

### 5.5 Dependencies

Cycle 1 not required (orthogonal layer), but cycles 1 and 2 can run
in parallel if the agent splits work.

### 5.6 Estimated Effort

5-8 sessions.

## 6. Cycle 3: Recipe Decommissioning

### 6.1 Goal

All 73 family-named recipes migrated to FamilyKnowledge data packs
driven by the procedural synthesizer. `_RECIPES` dict deleted.
`grammar_lowering.py` reduces from 14,145 lines to its synthesizer-
support core (target: under 2,000 lines).

### 6.2 Lanes And Blockers Advanced

- **Lane B** (ShapeIR v2 As Drivers) — completed
- **Lane I** (Authoring Surface And Stdlib Modularity) — bulk of
  resolution
- **B12** (Chest-Specific Code Is A Product Smell) — fully eliminated
- **B1** (Authored Intent Dies Before Geometry) — completed

### 6.3 Concrete Deliverables

Per `procedural-synthesizer-architecture-spec.md` §4 migration plan:

**Migration order, lowest risk first:**

1. **Round 1: Unknown families default to synthesizer** (no recipe
   changes; coexistence routing only).
2. **Round 2: Simple recipes (10 families)** — surface_material_sample,
   set_dressing_prop, lighting_prop, decal_zone-heavy ones.
3. **Round 3: Hard-surface guardrails (5 families)** —
   industrial_crate, mechanical_door, service_cabinet, weapon_prop,
   console_terminal (where present).
4. **Round 4: Procedural-domain recipes (10 families)** —
   vegetation_library_system, terrain_heightfield_system,
   wfc_tile_solver_system, cga_building_grammar_system,
   instance_pattern_scatter_system, f_rep_sdf_composition_system,
   etc. Some will require Lane J node-type extensions.
5. **Round 5: Bundle/system recipes (~48 families)** — the
   world_system_assembly, engine_facing_runtime_bundle_system, etc.
   Some require the "assembly" node-type extension noted as open
   question §9.1 in the spec.
6. **Round 6: Decommission** — delete `_RECIPES`, delete
   `_MIGRATED_TO_SYNTHESIZER`, replace the dispatch with direct
   `synthesize_shape_program(asset, runtime)` call.

**Generator completion:** the remaining 14 node-type generators
stubbed in cycle 1 become real implementations as recipe rounds
require them (frame, inset, rail, bracket, vent, conduit, latch,
weld, socket, mount, handle, hinge, wear_zone, material_zone). Plus
the 4-5 remaining edge decorators.

### 6.4 Acceptance Criteria

- `_RECIPES` dict does not exist in the codebase.
- All 73 families produce ShapeProgram outputs through the procedural
  synthesizer.
- `grammar_lowering.py` is under 2,000 lines.
- `grep -r 'family ==' lathe/` returns no hits in synthesis or
  geometry paths (metadata-only uses in report/trace fields
  permitted).
- For each of the 73 families: a side-by-side ShapeProgram diff
  test exists, comparing the pre-migration recipe output to the
  post-migration synthesizer output. Differences must be
  documented as intent-driven (e.g., brief now respected) or
  reduced.
- All 20 NODE_TYPE generators implemented, each ≤ 300 lines.
- Authoring a new (74th) family requires creating a single
  FamilyKnowledge data pack, no Python recipe function.

### 6.5 Dependencies

- Cycle 1 (procedural engine foundation) — required.
- Cycle 2 (kernel capability) — strongly recommended; some recipes
  emit ops whose execution path is improved by Cycle 2's work.

### 6.6 Estimated Effort

15-25 sessions (the majority of total effort lives here).

## 7. Cycle 4: Visual Layer Truth

### 7.1 Goal

The visible output of a synthesized build matches the asset class's
intent: tangent-space normal maps, real high-source detail from
ShapeIR primitives, topology preserves craft, texel density is
honest, material zones contrast readably. The "looks like procedural
blockout" failure mode is eliminated.

### 7.2 Lanes And Blockers Advanced

- **Lane D** (Surface Graph, Bake, And Material Truth) — primary
- **Lane E** (Topology, Retopo, And Mesh Finalization) — primary
- **Lane F** (UV, Texel Density, Trim Sheets, UDIM) — primary
- **B6** (Surface And Bake Truth Are Not Optional) — resolved
- **B7** (High/Low Transfer Must Contain Real Extra Detail) —
  resolved
- **B8** (Topology Can Erase Craft) — resolved
- **B9** (UV And Texel Density Must Become Evidence) — resolved

### 7.3 Concrete Deliverables

**Surface (Lane D):**

- Tangent-space fallback normal bake — confirmed for every code
  path emitting normals.
- Supersampled UV rasterizer for map generation
  (`lathe/bake_runtime.py` or new module).
- DesignerGraph evaluation produces real basecolor/normal/roughness/
  AO/curvature buffers — every authored graph node has a wired
  evaluator.
- LayerStack evaluation produces real buffers — same standard.
- Incremental graph nodes: SlopeBlur, HistogramScan/Levels, EdgeDetect,
  GradientMap, PositionMask/WorldYMask.
- Procedural high source from ShapeIR primitives, not low-mesh
  subdivision. Bevel, chamfer, panel, rivet, groove, seam geometry
  preserved in the high source.
- OKLab blending for basecolor/material color mixes.
- Per-engine normal map convention outputs in package manifests.
- MaterialX stdlib lowering with colorspace tags.
- Map sidecars carrying `colorspace: srgb | linear | none`.

**Topology (Lane E):**

- Blender adapter confirmed/fixed for current Blender versions.
  Attempted-vs-actual tracing with fallback reason in every code
  path.
- Beauty-diagonal triangulation, Taubin smoothing for voxel-origin
  parts, hard-edge normal split — all real, deterministic,
  unit-tested.
- Seam groups, bevel strips, material zones, part names preserved
  through topology with explicit before/after assertion.
- Multi-part scene names and part manifests preserved.
- Real quad-remesh provider (one) added with capability/availability
  reporting, used only when validatable.

**UV (Lane F):**

- Texel-density audit producing: min, max, ratio, worst chart,
  per-part density.
- Importance-weighted packing honoring asset density request.
- Constrained chart pre-scaling before packing.
- Trim-sheet binding: slot atlas, UV rect, edge/face binding,
  packing exclusion. Real impact on final texture output, not just
  string handles.
- UDIM spillover for hero assets when one tile cannot preserve
  density.
- Triplanar fallback used only when declared or when UV evidence
  shows it is the right fallback.

### 7.4 Acceptance Criteria

- A build of industrial_crate, mechanical_door, and a third non-
  hardsurface fixture each produces:
  - Tangent-space normal map (verified by sampling).
  - High source with face count > low mesh face count (verified by
    artifact size + face-count report).
  - Topology preserves all authored named parts (asserted via the
    part manifest diff).
  - Texel-density report with non-zero `requested_vs_actual` ratio.
- Every emitted map carries a `colorspace` sidecar.
- A "bad" baseline (e.g., a built-with-flat-shading variant) is
  reproducible and produces different evidence than the good
  baseline. The diagnostic distinguishes them.
- 4 new fixtures (covering 4 different asset classes) verify the
  visible-layer chain end-to-end.

### 7.5 Dependencies

- Cycle 1 — synthesizer must produce ShapePrograms with rich enough
  semantic provenance for the surface graph evaluators to consume.
- Cycle 2 partial — kernel must execute the operations whose
  visible craft Cycle 4 preserves.
- Cycle 3 partial — at least the Sprint 0 guardrail families
  migrated, so Cycle 4 visual verification runs on the procedural
  engine output.

### 7.6 Estimated Effort

8-14 sessions.

## 8. Cycle 5: Quality Loop Closure

### 8.1 Goal

Diagnostics correlate with human visual judgment. The closed loop
`build → diagnose → repair → rebuild → measurably-better` is
deterministic, reliable, and exposed as a first-class operation.

### 8.2 Lanes And Blockers Advanced

- **Lane G** (Diagnostics, Validation, And Reports) — primary
- **Lane H** (Semantic Repair And Regeneration) — primary
- **B10** (Validators Must Judge Visible Output) — resolved
- **B11** (Semantic Repair Must Become Operational) — resolved

### 8.3 Concrete Deliverables

**Diagnostics (Lane G):**

Visible-blocker diagnostic set, fully implemented and pixel-level
or mesh-level where appropriate:

- `blockout_geometry_appearance`
- `debug_material_preview_penalty`
- `missing_bevel_chamfer_detail_evidence`
- `weak_primary_secondary_tertiary_balance`
- `weak_material_zone_contrast`
- `attachment_seating_quality`
- `fake_highlow_detail`
- `boolean_csg_fallback` (confirm wired end-to-end from cycle 2)
- `proxy_preview_only`
- `texel_density_drift`
- `lost_named_part`
- `unsupported_op_executed_as_approximation`

Each diagnostic:

- Inspects pixel/mesh/artifact evidence, not metadata fields.
- Emits `severity: warn | error | info` with stable threshold.
- Maps to a `repair_action_candidates: [...]` field.
- Has a test that proves a known-bad asset triggers it and a
  known-good asset does not.

**Repair (Lane H):**

- Repair planner expanded to map every Lane G diagnostic to at
  least one repair action (when feasible).
- Repair executor allowlist covers every action the planner
  emits.
- Patches are deterministic, serializable, reversible (or
  rejection-on-failure-safe).
- A full closed-loop test exists: build_a → diagnose → patch →
  build_b → diagnose. Asserts:
  - At least one diagnostic that fired on build_a does not fire
    on build_b.
  - No new severity-error diagnostics introduced by the patch.
  - `report.repair_loop` records before/after metrics and patch
    operation IDs.

### 8.4 Acceptance Criteria

- 12 visible-blocker diagnostics implemented and pixel/mesh-level
  evidence-driven.
- A test corpus of 5 known-bad and 5 known-good asset variants
  exercises every diagnostic. Known-bad triggers; known-good does
  not.
- Closed-loop test: at least 3 distinct asset classes round-trip
  through diagnose → patch → rebuild with measurable improvement.
- Repair planner+executor coverage: every diagnostic has at least
  one mapped repair operation OR is documented as
  `repair_route: not_yet_implemented`.

### 8.5 Dependencies

- Cycle 4 partial — diagnostics need visible output to judge.
- Cycle 3 partial — repair operations must work via procedural
  synthesizer.

Cycles 4 and 5 may run partially in parallel: Cycle 4 ships visible
layers; Cycle 5 lands diagnostics for each layer as it stabilizes.

### 8.6 Estimated Effort

5-9 sessions.

## 9. Cycle 6: Multi-Domain Expansion (Phase 3)

### 9.1 Goal

The procedural engine produces production-grade output across
vegetation, terrain, modular environments (WFC), grammar-based
architecture (CGA), F-Rep/SDF organic, scatter, and OpenSubDiv
finishing — all driven by the same generic synthesizer with per-
domain NODE_TYPE extensions.

### 9.2 Lanes And Blockers Advanced

- **Lane J** (Multi-Domain Imagination-To-Life Demos) — primary
- **Phase 3** (Procedural Domain Libraries) — bulk of work

### 9.3 Concrete Deliverables

Per northstar §11 Phase 3 deliverables:

**Vegetation** (SpeedTree-inspired):

- Trunk/branch/leaf vocabulary as NODE_TYPE extensions:
  `trunk`, `branch`, `leaf_cluster`, `frond`, `root`, `bark`.
- Generic generators per type.
- Family knowledge packs for tree types: deciduous, coniferous,
  palm, shrub, fern.
- L-system or recursive procedural composition via edge decorators
  (`branches_from`, `grows_along`).

**Terrain:**

- Heightfield NODE_TYPE: `heightfield_tile`, `erosion_basin`,
  `material_strata`, `vegetation_density_zone`.
- Erosion as a deterministic procedural pass (hydraulic, thermal).
- Material zoning from height, slope, water proximity.

**WFC modular environments:**

- `wfc_module_kit`, `wfc_constraint_set`, `wfc_layout` NODE_TYPES.
- Deterministic WFC solver with seed.
- Module fitness/adjacency rules as edge decorators
  (`fits_against`, `mirrors_along`).

**CGA building grammar:**

- `lot`, `mass`, `facade`, `window`, `door`, `roof` NODE_TYPES.
- Shape grammar production rules in stdlib-style data packs.
- Hierarchical decomposition via edge decorators (`subdivides_into`,
  `placed_on`).

**F-Rep / SDF composition:**

- `sdf_primitive`, `sdf_blend`, `sdf_carve` NODE_TYPES.
- Sharper extraction via dual contouring or surface nets where
  capability permits.

**Scatter as production multiplier:**

- `scatter_set`, `scatter_constraint`, `scatter_target_surface`
  NODE_TYPES.
- Density-driven, deterministic, importance-weighted.

**OpenSubDiv finishing:**

- Adaptive subdivision pass with crease preservation.
- Capability-gated; fallback to deterministic Catmull-Clark when
  OpenSubDiv unavailable.

### 9.4 Acceptance Criteria

- 6 new domains each ship one production-grade authored fixture
  built end-to-end through the procedural engine.
- NODE_TYPES expanded by ~25-35 domain-specific types; no domain
  reuses a hard-surface generator (clean separation, but shared
  base engine).
- Per-domain visible-layer audit (Cycle 4 standards apply): real
  topology, real materials, real UV, real diagnostics.
- Each domain's repair routes (Cycle 5 standards) at least map one
  diagnostic to one repair action.
- Family count grows but Python recipe count stays at 0 — all new
  families are data packs.

### 9.5 Dependencies

- Cycles 1-5 complete or substantially advanced.

### 9.6 Estimated Effort

12-20 sessions.

## 10. Cycle 7: Animation-Forward Vocabulary (Phase 4)

### 10.1 Goal

Lathe expresses rig, skin, morph, and animation vocabulary as typed
data on top of the procedural substrate. Characters, creatures, and
animated props author through the same construction-graph engine —
no special animation-specific dispatch.

### 10.2 Lanes And Blockers Advanced

- **Phase 4** (Organic And Animation-Forward Vocabulary) — primary
- Cross-lane: Lane B+C+D+E+F all extend to animation-bearing assets

### 10.3 Concrete Deliverables

Per northstar §11 Phase 4 deliverables:

- **Rig as typed data** — `joint`, `bone`, `ik_chain`, `constraint`,
  `pole_target` NODE_TYPES.
- **Parametric rig components** — reusable rig fragments
  (`humanoid_arm`, `quadruped_leg`, `tail`, `tentacle`) as
  declarative pack assemblies.
- **Skin program** — vertex weight assignment as a deterministic
  procedural pass driven by node attributes + topology.
- **Morph targets** — `morph_blend_shape` NODE_TYPE with deformation
  ops that produce paired neutral/morph mesh.
- **Canonical topology** — `canonical_topology_profile`
  (humanoid_standard, quadruped_standard, etc.) as data packs that
  constrain topology output.
- **Animation library compatibility** — clip naming/binding via
  edge decorators (`drives`, `bound_to_skeleton`).

### 10.4 Acceptance Criteria

- A character_creature fixture (one of the existing 73 family names,
  now migrated to data pack) builds end-to-end with rig + skin +
  morph evidence in package artifacts.
- Animation clip binding test: bind a stock animation library clip
  to a rigged fixture, package, verify the export contains the
  expected animation track count.
- Canonical topology profile constraint: a humanoid_standard
  fixture cannot deviate from the topology profile's quad layout
  without a diagnostic.

### 10.5 Dependencies

- Cycles 1-6 substantially complete.
- May require new kernel capabilities (Cycle 2 follow-up):
  deformation operations beyond bend/twist/taper.

### 10.6 Estimated Effort

8-14 sessions.

## 11. Cycle 8: Engine Integration (Phase 5)

### 11.1 Goal

Lathe ships as a procedural runtime where it makes product sense.
USD generative procedural support, real Unity/Unreal/Godot/Roblox
handoff with verified import evidence, live parameter overrides,
signed package/repro evidence. This is where Lathe meets the engines
the user's product actually targets.

### 11.2 Lanes And Blockers Advanced

- **Phase 5** (Lathe Runtime And Engine Integration) — primary
- Capability Parity Matrix (northstar §13) — final ratification

### 11.3 Concrete Deliverables

Per northstar §11 Phase 5 deliverables:

- **USD generative procedural path** — Lathe assets export as USD
  with generative-procedural metadata that USD-aware tools can
  re-evaluate.
- **Unity handoff with real import evidence** — `.fbx` or `.gltf`
  export verified by a Unity import harness in CI. Material/texture
  binding round-trips. Animation clips import. Real or clearly-proxy
  status reported.
- **Unreal handoff** — equivalent: `.fbx` / Datasmith / USD import
  to Unreal harness. Verified.
- **Godot handoff** — `.gltf` / Godot scene import. Verified.
- **Roblox handoff** — `.mesh` / `.fbx` / asset upload, MeshPart
  geometry verification. Verified.
- **Live parameter overrides** — runtime knobs documented in the
  exported asset that allow consumers to re-evaluate Lathe assets
  without source `.lth`.
- **Signed package/repro evidence** — package manifests carry a
  signature derived from `.lth` source + runtime config + Lathe
  version. Reproducing the package from the same inputs produces
  the same signature.

### 11.4 Acceptance Criteria

- An automated import test exists for each of: Unity, Unreal,
  Godot, Roblox. Each opens a Lathe-exported package and asserts:
  - Mesh geometry imports without error.
  - Material textures bind to the imported mesh.
  - Animation clips import where applicable.
  - Normal map convention matches the exported `colorspace` sidecar.
- Test fixture: 3 distinct asset classes (one hard-surface, one
  organic/vegetation, one rigged character) round-trip through each
  engine.
- A reproduction test: clone the repo at a tagged commit, build the
  same `.lth` with the same runtime config, verify the resulting
  package signature matches the committed reference.

### 11.5 Dependencies

- All prior cycles complete.
- External dependencies: engine versions (Unity LTS, Unreal,
  Godot, Roblox Studio) must be reachable from CI. This is the
  first cycle whose verification floor is genuinely beyond pure
  code work — may require partnership/license/CI-resource
  coordination.

### 11.6 Estimated Effort

10-20 sessions (plus external coordination time, not bounded by
code-session estimates).

## 12. Cross-Cycle Parallelization

While cycles are presented sequentially, some can overlap when
multiple agents/sessions are available:

- **Cycle 1 and Cycle 2 are orthogonal** (synthesizer is the
  language layer; kernel decomposition is the execution layer).
  Both can run in parallel after the seam refactor.
- **Cycle 4 and Cycle 5 are paired** but can ship in tightly
  alternating commits — each Cycle 4 visible-layer slice gets its
  Cycle 5 diagnostic immediately after.
- **Cycle 6 domain extensions** can each run in parallel once the
  cycle-6-base generators (heightfield, sdf, scatter) exist.

Cycles 3, 7, and 8 are strictly gated by their dependencies and
should not be parallelized with their predecessors.

## 13. Verification Floor Per Cycle

Per the user's principle and the northstar's Rule of Truth (§4),
each cycle's verification floor is the minimum below which "this
works" cannot honestly be claimed:

| Cycle | Verification Floor |
|---|---|
| 1 | Synthesizer tests + grammar_lowering tests + shape_handoff_v1 contract. 136+ tests green. |
| 2 | Cycle 1 floor + kernel-program decomposition tests + 83-op coverage assertion. ~180 tests green. |
| 3 | Cycle 2 floor + per-family migration diff tests. ~250 tests green plus 73 migration diffs. |
| 4 | Cycle 3 floor + visible-layer fixture builds with artifact assertions. ~280 tests + 4 build fixtures. |
| 5 | Cycle 4 floor + diagnostic-trigger tests + closed-loop tests. ~320 tests + repair-loop fixtures. |
| 6 | Cycle 5 floor + per-domain fixture builds. ~380 tests + 6 domain fixtures. |
| 7 | Cycle 6 floor + rig/anim fixture builds. ~420 tests + 3 animation fixtures. |
| 8 | Cycle 7 floor + per-engine import tests. ~450 tests + 12 engine round-trips (4 engines × 3 asset classes). |

A cycle is not "done" until its verification floor is green.

## 14. Stable Contracts Defended Every Cycle

The northstar §5 stable-contracts list governs every cycle. Each
cycle must include a "stable contracts check" before commit:

- Public `.lth` source compatibility — `git grep -nE 'def parse_' lathe/parser/` shape unchanged.
- `lathe.shape.intent_mesh_handoff_v1` — `test_shape_handoff_v1.py` green.
- `lathe.geometry` package public API — every symbol still importable.
- Downstream stage contracts (topology, UV, surface, package, publish) — stage bundle key sets unchanged or only additively grown.

A cycle that breaks a stable contract requires an explicit "stable
contract migration" subcycle that updates docs, schemas, examples,
tests, and the migration note in the changelog.

## 15. Honest Effort Total

Bounded estimate, summing cycles:

| Cycle | Sessions | Cumulative |
|---|---:|---:|
| 1 | 3-5 | 3-5 |
| 2 | 5-8 | 8-13 |
| 3 | 15-25 | 23-38 |
| 4 | 8-14 | 31-52 |
| 5 | 5-9 | 36-61 |
| 6 | 12-20 | 48-81 |
| 7 | 8-14 | 56-95 |
| 8 | 10-20 | 66-115 |

**Total: 66-115 sessions** of focused work at ~3-5 hours per session.

Maps to:

- **Aggressive pace** (4 sessions/week, 1 agent): 16-29 weeks ≈ 4-7 months.
- **Steady pace** (2 sessions/week, 1 agent): 33-58 weeks ≈ 8-14 months.
- **Multi-agent parallel** (effective 6 sessions/week across 2-3 agents):
  11-19 weeks ≈ 3-5 months.

The northstar §11 own timeline (Phase 1 1-2mo → Phase 5 18-36mo) covers
18-38 months. This plan accelerates that by being session-dense and
parallelizing where dependencies allow, but is honest that engine
integration in cycle 8 has external dependencies beyond the agent's
control.

## 16. Risks And Mitigations

| Risk | Cycle | Mitigation |
|---|---|---|
| Recipe migration introduces visible regressions invisible to ShapeProgram diff | 3 | Cycle 4 + Cycle 5 land before recipe migration is "done" on Sprint 0 guardrails. Visible-layer + diagnostic tests catch what ShapeProgram diff misses. |
| Kernel decomposition introduces subtle behavior bugs | 2 | Per-module decomposition keeps each module under 1500 lines; behavior preserved by import-shape preservation; 180+ tests green per slice. |
| Domain extensions inflate NODE_TYPES unboundedly | 6 | NODE_TYPES expansion gated by "must generalize across ≥3 unrelated families." Domain-specific subsets dispatched by brief's `domain` field, not packed into core NODE_TYPES. |
| Engine integration in Cycle 8 blocked by external coordination | 8 | Cycle 8 verification floor distinguishes pure-code work (export emission) from external-engine round-trip (import verification). The former can ship without the latter. |
| Visual quality remains weak even after Cycles 4-5 | 4-5 | Per northstar §3, this is the language-vs-engine gap. If outputs still look procedural after Cycle 4, the cycle is not done; do not move to Cycle 5 prematurely. |
| 73-recipe domain knowledge incompletely captured in data packs | 3 | Per-recipe migration acceptance includes a diff test against original recipe output. Knowledge gaps surface as diff failures and are documented as required new generator capabilities. |
| Cycle 1 synthesizer skeleton ages without recipe migration following | 1-3 | Cycle 1 should be followed by at least 5 recipe migrations (Round 2 of Cycle 3) within the same calendar week so the engine sees real load before drift sets in. |
| Animation vocabulary (Cycle 7) requires deformation kernel capabilities not in Cycle 2 | 7 | Cycle 7 emits a deferred-capabilities list during planning; Cycle 2 follow-up sessions fill that list before Cycle 7 acceptance. |
| External engine versions break in CI (Cycle 8) | 8 | Pin engine versions in the import-test harness; provide a `not_verified` claim when the harness cannot run. |

## 17. What "Northstar Complete" Means

The northstar is complete when:

1. **All 13 blockers (B0-B12) from §7 are resolved.** Per the
   cycle-to-blocker map in this plan, each blocker is resolved by
   the cycle named.
2. **All 10 lanes (A-J) from §10 reach their acceptance criteria.**
3. **All 5 phases from §11 ship their deliverables.**
4. **The Capability Parity Matrix (§13) has every row passing**
   under the "Real only when" column with corresponding artifact
   evidence.
5. **The Decision Filter (§14) passes for the system as a whole**:
   any new asset family can be authored as a data pack; every claim
   is backed by artifact evidence; family-name dispatch is not in
   any code path; the imagination-to-life loop closes deterministically.
6. **No remaining "partial" or "early partial" lane states** in the
   current audit's successor.

The audit's bottom line will move from:

```
"Lathe produces consistently good-looking authored assets" blocker
not crossed.
```

to:

```
Lathe produces consistently good-looking authored assets across all
supported domains, in deterministic build → diagnose → repair loops,
with verified engine handoff and signed package/repro evidence.
```

## 18. Day-1 Sequencing (Concrete First-Hour Plan)

For the next agent picking up this plan:

1. **Read this plan, the northstar, the audit, and the synthesizer
   spec** — in that order. ~30 minutes.
2. **Confirm git status clean and on main at origin/main.** Pull if
   needed.
3. **Open `procedural-synthesizer-architecture-spec.md` §12.** That
   is Cycle 1's first session implementation sequencing.
4. **Execute Cycle 1 first commit chunk:**
   - Create `lathe/asset_quality/procedural_synthesizer/` package.
   - Implement `FamilyKnowledge`, `SynthesizerContext`, the empty
     registries, the trace schema.
   - Wire `evaluate_grammar_lowering` to route unknown families
     through `synthesize_shape_program` (returns empty program for
     now).
   - Implement `_primary_volume_generator` end-to-end with hint
     resolution.
   - Add `tests/unit/test_procedural_synthesizer_primary_volume.py`.
   - Verify the 136-test slice still green.
   - Commit.
   - Push.
5. **Update this plan's §1 "Starting Position"** to reflect the
   shipped slice. Commit the docs update.

That is the first session's complete shape. Subsequent sessions
follow Cycle 1's deliverable list, then Cycle 2's, then Cycle 3's,
in order.

## 19. Bottom Line

The northstar is a real, finishable target. This plan sequences it
into 66-115 concrete sessions across 8 cycles. Every cycle ships
production-grade work. Every cycle defends the stable contracts.
Every cycle has a verification floor that prevents "shipping a beta
in production paint."

The work is multi-month to a year of focused engineering, not a
single session. But it is finishable, and this plan is the map to
finish it.

The user's principle is honored absolutely: **Lathe must be modular,
and the key here is procedural generation. We should not specify any
specific asset.** Cycle 3's decommissioning of `_RECIPES` is the
moment that principle becomes structurally enforced in the codebase.
Every cycle after that builds on a procedural foundation that does
not know what a "crate" or "door" or "tree" or "humanoid" is — only
what `primary_volume + panel + fastener` or `trunk + branch + leaf`
or `joint + bone + skin` compose to.

This plan is the canonical source of truth for completing the
northstar. Future implementation agents should pick the next
unfinished cycle, execute its session-sized slice, verify, commit,
push, and update the audit. The plan does not need to be revisited
until a cycle's acceptance criteria are met and the next cycle
begins.
