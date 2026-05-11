# Lathe Northstar Full Implementation Plan

Date: 2026-05-11 (revision iteration 1: same day)
Status: Canonical end-to-end sequencing plan for completing
`docs/asset-quality/lathe-implementation-northstar.md` in full
Scope: All 10 lanes (A-J), all 13 blockers (B0-B12), all 5 phases,
plus the procedural synthesizer (`procedural-synthesizer-architecture-spec.md`,
v2) that resolves B12 and unblocks Lanes B/C/I
Companion docs: `lathe-implementation-northstar.md` (intent),
`lathe-implementation-northstar-current-audit.md` (current state),
`procedural-synthesizer-architecture-spec.md` v2 (one architectural slice)

## Revision History

- **2026-05-11 v1 (initial)** — first draft. Allowed Cycle 1 to ship
  stub-only generators and a synthesizer that returns empty programs
  for unknown families. Treated "one FamilyKnowledge pack per family"
  as the end-state modular unit. Cycle 3 decommission acceptance used
  the weak `grep 'family ==' lathe/` check. Cycle 6 deferred the domain
  extension API to Phase 3 work. Recipe count cited as 73; actual is 71.
  Section 3 / Section 12 disagreed on whether Cycles 1-2 are parallel.
- **2026-05-11 v2 (this revision)** — review iteration resolved six
  findings:
  1. **Cycle 1 ships real procedural output.** No stub generators.
     No empty-program route. Per spec v2 §9.3, the first commit
     produces a non-empty ShapeProgram for authored-intent-only
     fixtures.
  2. **The modular unit is policy/style/domain, not family.** Plan
     updated to reflect the spec v2 split into CompositionPolicy,
     StyleKnowledge, FamilyAlias, DomainExtension. Family aliases
     SELECT packs; they do not DEFINE structure.
  3. **`no_family_dispatch` lint/test replaces the weak grep.**
     Catches `_RECIPES.get(family)`, `.get(family)` in synthesis/
     geometry paths, `family in` checks, and `_FAMILY_*` behavior
     maps. Lives in CI; runs every commit.
  4. **Recipe decommission interleaves with visual proof.** A family
     migrates only after both the ShapeProgram diff AND a visible
     build artifact pass. Cycle 3 does not "complete" before
     Cycle 4 has caught up family-by-family.
  5. **Domain extension API lands in Cycle 1, not Cycle 6.** The
     `DomainExtensionManifest` and per-domain registration contract
     are first-commit deliverables. Cycle 6 becomes "register
     domain extensions," not "design the extension contract."
  6. **Recipe count uses the live registry, not a hardcoded number.**
     Plan refers to "the current `_RECIPES` registry" or a generated
     audit count. Today: 71 entries.
  Plus the sequencing contradiction is resolved: Cycle 1 must
  complete before Cycle 2 can run (Cycle 2 depends on the
  synthesizer's typed-attribute schemas and generator manifests).
  Cycles 2 and 3 can overlap. Cycle 3 cannot complete before
  Cycle 4 has caught up.

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
- Procedural synthesizer spec revised to v2 (`e3e656b`) — splits
  FamilyKnowledge into StyleKnowledge/CompositionPolicy/FamilyAlias,
  declares typed attribute schemas, declares generator capability
  manifests, declares domain extension contract, replaces linear
  outer loop with 8-stage compiler pipeline.

**Honest open state:**

- Sprint 0 visual quality: certified outputs still read as procedural
  blockout, not finished assets.
- Lane A geometry kernel: strong but brittle; 12K-line concentration
  in `kernel_program.py`; some boolean fallbacks silent.
- Lane B ShapeIR v2 driver: current `_RECIPES` registry (71 entries
  at session 2026-05-11; refresh from
  `lathe/asset_quality/grammar_lowering.py` for the live count)
  still dispatches on family name; brief/parts/graph_nodes ignored
  by recipes.
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

**Sequencing rules (resolved in v2):**

- **Cycle 1 must complete before Cycle 2 starts.** Cycle 2 depends on
  the typed attribute schemas, generator capability manifests, and
  domain extension manifest that Cycle 1 produces. There is no
  parallel start.
- **Cycles 2 and 3 may overlap.** Cycle 2 (kernel capability) and
  Cycle 3 (recipe decommissioning) operate on orthogonal layers
  once Cycle 1's substrate is in place.
- **Cycle 3 cannot complete before Cycle 4 has caught up family by
  family.** A migrated family is only "done" after it has both
  passed the ShapeProgram equivalence diff (Cycle 3) AND passed the
  visible-artifact build inspection (Cycle 4). This prevents the
  failure mode "ShapeProgram diff was acceptable but rendered output
  is worse."
- **Cycles 4 and 5 are paired and ship in tightly alternating commits.**
  Each Cycle 4 visible-layer slice gets its Cycle 5 diagnostic
  immediately after.
- **Cycles 6, 7, 8 are strictly gated by their predecessors** and do
  not parallelize backward.

## 4. Cycle 1: Procedural Engine Foundation

### 4.1 Goal

Replace family-name dispatch in `grammar_lowering.py` with a
production-grade procedural compiler pipeline. The substrate must
be modular by **policy, style, and domain** — not by family. Family
identity collapses to an alias that selects packs; family identity
does not select code paths and does not select structural decisions.
Every generator, decorator, knowledge pack, and domain extension is
introduced via a stable plugin contract Cycle 1 itself defines.

**No stubs.** No empty-returning generators. No no-op routing. Every
file committed in Cycle 1 produces real output end-to-end.

### 4.2 Lanes And Blockers Advanced

- **Lane B** (ShapeIR v2 As Drivers) — primary
- **Lane C** (Feature Ops And Modularity) — substrate
- **Lane I** (Authoring Surface And Stdlib Modularity) — substrate
- **B12** (Chest-Specific Code Is A Product Smell) — core resolution
- **B1** (Authored Intent Dies Before Geometry) — partial resolution

### 4.3 Concrete Deliverables

Per `procedural-synthesizer-architecture-spec.md` v2 §5 and §12.
**Every file listed here must be production code on first commit —
no skeletons, no stubs, no "filled in later" placeholders.**

#### 4.3.1 Engine code

```
lathe/asset_quality/procedural_synthesizer/
    __init__.py                 # public API
    context.py                  # SynthesizerContext (resolves alias->packs)
    pipeline.py                 # 8 stages, all real
    registry.py                 # GeneratorRegistry, keyed by (domain, type)
    trace.py                    # SynthesizerTrace + TraceEntry
    hint_resolution.py          # priority chain with trace attribution
    domain_extension.py         # DomainExtensionManifest contract (CYCLE 1)
    attributes/
        __init__.py
        primary_volume.py       # PrimaryVolumeAttributes (typed schema)
        panel.py                # PanelAttributes (typed schema)
    knowledge_loader/
        __init__.py
        style.py                # loads StyleKnowledge JSON
        policy.py               # loads CompositionPolicy JSON
        alias.py                # loads FamilyAlias JSON
        schemas/
            style.schema.json
            policy.schema.json
            alias.schema.json
            domain_extension.schema.json
    generators/
        __init__.py             # registers built-in hard-surface domain
        hard_surface/
            __init__.py
            primary_volume.py   # real generator + manifest
            panel.py            # real generator + manifest
    decorators/
        __init__.py
        hard_surface/
            __init__.py
            attached_to.py      # real decorator + manifest
```

No other generator or decorator file appears in Cycle 1. The set is
**deliberately minimal but complete** — every committed file is
real, tested, and produces visible geometry or a real graph
relation.

#### 4.3.2 Declarative knowledge

```
std/procedural/knowledge/
    style/
        industrial_pbr_v1.json
    policy/
        panelized_hard_surface_object.json
    aliases/
        # one alias file for the simplest family the synthesizer
        # can handle end-to-end after Cycle 1, picked at migration
        # time in Cycle 3 — Cycle 1 does NOT add an alias file
```

#### 4.3.3 DomainExtensionManifest contract (new in v2)

The plugin contract for Cycle 6's per-domain packs lands NOW so
domains plug in without redesigning the synthesizer:

```python
@dataclass(frozen=True)
class DomainExtensionManifest:
    """Declares a domain's contribution to the synthesizer.

    Loaded at import time by domain extension packages. The registry
    refuses to register a domain whose manifest reports incomplete
    coverage of its own NODE_TYPES.
    """

    domain_id: str                                     # "hard_surface", "vegetation", ...
    node_type_schemas: Mapping[str, type]              # NODE_TYPE -> typed schema class
    edge_type_schemas: Mapping[str, type]              # EDGE_TYPE -> typed schema class
    generators: tuple[NodeTypeGenerator, ...]
    decorators: tuple[EdgeTypeDecorator, ...]
    required_kernel_capabilities: tuple[str, ...]
    emitted_shape_ir_ops: tuple[str, ...]              # subset of ALL_OPS
    style_pack_compatibility: tuple[str, ...]          # which style packs work
    policy_pack_compatibility: tuple[str, ...]         # which policies apply
```

Hard-surface domain is the first DomainExtension registered. Phase 3
domains (vegetation, terrain, WFC, CGA, etc.) become additional
DomainExtensions in Cycle 6 — **no engine code changes needed at
that point.**

#### 4.3.4 Routing change in grammar_lowering.py

```python
def evaluate_grammar_lowering(asset, runtime):
    family = _resolve_family(brief)
    if family in _MIGRATED_TO_SYNTHESIZER:
        return synthesize_shape_program(asset, runtime)
    recipe = _RECIPES.get(family)
    if recipe is None:
        # Unknown families route to the synthesizer, which produces
        # REAL output from the construction graph + brief, NOT an
        # empty program. This is the Cycle 1 acceptance fixture path.
        return synthesize_shape_program(asset, runtime)
    return recipe(brief, parts, graph_nodes)
```

`_MIGRATED_TO_SYNTHESIZER` is initialized in Cycle 1 with the alias
authored in §4.3.2 (whichever simple family Cycle 3 picks as its
first migration target). Cycle 3 grows that set.

#### 4.3.5 Tests

```
tests/unit/test_procedural_synthesizer_pipeline.py
tests/unit/test_procedural_synthesizer_attributes.py
tests/unit/test_procedural_synthesizer_knowledge_loader.py
tests/unit/test_procedural_synthesizer_domain_extension.py
tests/unit/test_procedural_synthesizer_primary_volume.py
tests/unit/test_procedural_synthesizer_panel.py
tests/unit/test_procedural_synthesizer_attached_to.py
tests/contract/test_no_family_dispatch.py     # NEW — lint test (CYCLE 1)
```

The `test_no_family_dispatch.py` contract test is a Cycle 1
deliverable. It scans the codebase and fails if any of these
patterns appear in synthesis/geometry/surface paths:

- `_RECIPES.get(family)` or `_RECIPES[family]`
- Any `dict.get(family)` or `dict[family]` where the dict is a
  `_FAMILY_*` or `_GRAMMARS` or other family-keyed behavior map
  (not allowlisted)
- `family ==` or `family in` checks (outside trace/report fields
  explicitly allowlisted via `# no-family-dispatch: report-only`)

A small allowlist covers metadata-only references (trace fields,
package report tags, audit logs). The allowlist lives in
`tests/contract/_family_dispatch_allowlist.py` and entries require
a reason comment. Cycle 3's "decommission acceptance" check uses
this test — not a `grep`.

### 4.4 Acceptance Criteria

- Three generators (`primary_volume`, `panel`) and one decorator
  (`attached_to`) implemented end-to-end with capability manifests.
  Each generator ≤ 300 lines. **No stubs anywhere.**
- The 8-stage compiler pipeline is fully implemented. No stage is a
  pass-through.
- `DomainExtensionManifest` exists, validated, with hard-surface as
  the first registered extension.
- An **unknown-family** fixture (authored intent only: primary_volume
  + 2 panels + attached_to edges, no family alias, no recipe in
  `_RECIPES`) produces a non-empty, geometrically valid ShapeProgram
  through the synthesizer. The fixture builds end-to-end via
  `lathe build`, producing a real GLB containing visible panel
  geometry attached to a primary volume. **This is the production-
  grade proof — not a unit test alone.**
- Same authored intent, different brief proportions produces a
  structurally different ShapeProgram (intent dominance proven).
- `family_dispatch_used: false` in the trace for every synthesizer-
  routed program.
- The `test_no_family_dispatch.py` contract test passes (the
  synthesizer codebase introduces no new family-keyed dispatch).
- All 71 family recipes still pass their existing tests
  (coexistence preserved).
- Targeted suite green: all synthesizer tests + grammar_lowering
  tests + shape_handoff_v1 contract + the new
  `test_no_family_dispatch.py`.

### 4.5 Dependencies

None — builds directly on the seam refactor from session
2026-05-11.

### 4.6 Estimated Effort

3-5 sessions. Cycle 1 deliberately stays narrow (one fully-clean
slice + the extension contract) rather than broad (many partial
generators).

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

**Cycle 1 required.** Cycle 2 consumes Cycle 1's typed attribute
schemas, generator capability manifests, and the
`DomainExtensionManifest` contract — Cycle 2's hard-surface generator
extensions register through that contract. Once Cycle 1 has shipped,
Cycle 2 and Cycle 3 may overlap.

### 5.6 Estimated Effort

5-8 sessions.

## 6. Cycle 3: Recipe Decommissioning

### 6.1 Goal

Migrate every entry in the current `_RECIPES` registry (71 entries
at session 2026-05-11; check the live count when this cycle begins)
to **declarative knowledge files** — StyleKnowledge JSON, CompositionPolicy
JSON, and FamilyAlias JSON per the spec v2 §3.2. **A FamilyAlias is
metadata only**; structure comes from policies matched by authored
intent, not from family-keyed packs. `_RECIPES` dict deleted at
cycle end. `grammar_lowering.py` reduces from 14,145 lines to its
synthesizer-support core (target: under 2,000 lines).

### 6.2 Lanes And Blockers Advanced

- **Lane B** (ShapeIR v2 As Drivers) — completed
- **Lane I** (Authoring Surface And Stdlib Modularity) — bulk of
  resolution
- **B12** (Chest-Specific Code Is A Product Smell) — fully eliminated
- **B1** (Authored Intent Dies Before Geometry) — completed

### 6.3 Concrete Deliverables

Per `procedural-synthesizer-architecture-spec.md` v2 §4 migration plan.

**Migration order — interleaved with visual proof:**

The v1 plan ordered migration purely by ShapeProgram-diff risk. The
v2 plan interleaves migration with visible-artifact verification
from Cycle 4. **A family is "migrated" only after a build artifact
inspection passes — not after a ShapeProgram diff alone.** This
prevents the failure mode "diff was acceptable but render is worse."

1. **Round 0: Author reusable knowledge packs first.** Author the
   composition policies that several families will share
   (panelized_hard_surface_object, radial_mechanical_assembly,
   l_system_branching, wfc_modular_layout, scatter_distribution).
   These are non-family-keyed. A family migration then references
   them rather than redefining structure.
2. **Round 1: Unknown families default to synthesizer.** Coexistence
   routing only; landed in Cycle 1. Confirm no regression.
3. **Round 2: Simple recipes (10 families)** — small emitted-op count,
   minimal structural decisions. Per family:
   - Author StyleKnowledge JSON (or pick an existing one).
   - Pick CompositionPolicies (or author one).
   - Author FamilyAlias JSON pointing at them.
   - Run ShapeProgram diff vs old recipe — must be equivalent or
     better.
   - **Run a real build of a fixture for that family** — confirm
     the artifact's preview, mesh, and surface evidence are at
     parity or better with the pre-migration build.
   - Add family to `_MIGRATED_TO_SYNTHESIZER`. Delete the recipe.
4. **Round 3: Hard-surface guardrails** — industrial_crate,
   mechanical_door, service_cabinet, weapon_prop. Same per-family
   protocol as Round 2. **Cycle 4 must be at least partially
   shipped for these** so visible-artifact diff is real evidence,
   not best-effort visual judgment.
5. **Round 4: Procedural-domain recipes** — these require
   corresponding DomainExtension packs (from Cycle 6). Migration of
   each of these waits on its domain extension shipping.
6. **Round 5: Bundle/system recipes** — require sub-asset
   composition (open question §9.5 in spec). Prototype the
   `assembly` NODE_TYPE before migrating these.
7. **Round 6: Decommission** — delete `_RECIPES`, delete
   `_MIGRATED_TO_SYNTHESIZER`, replace the dispatch with direct
   `synthesize_shape_program(asset, runtime)` call. **Only after
   every family has been verified by build-artifact inspection.**

**Generator and decorator completion:** the remaining NODE_TYPE
generators (frame, inset, rail, bracket, vent, conduit, latch, weld,
socket, mount, handle, hinge, fastener, trim, decal_zone, wear_zone,
material_zone, guard) and EDGE_TYPE decorators (inset_into,
wraps_around, mirrors, aligned_with, supports, cuts) ship as full
production implementations as recipe rounds require them. **No
stubs at any point.** Each new generator/decorator commit is
complete on its own.

### 6.4 Acceptance Criteria

- `_RECIPES` dict does not exist in the codebase.
- All families that existed in the registry at Cycle 3 start
  produce ShapeProgram outputs through the procedural synthesizer.
  Count refresh: read the live registry at migration time, not a
  hardcoded number.
- `grammar_lowering.py` is under 2,000 lines.
- The `test_no_family_dispatch.py` contract test (introduced in
  Cycle 1) covers every form of family-keyed dispatch and passes:
  - No `_RECIPES.get(family)` or `_RECIPES[family]` in any code path.
  - No `dict.get(family)` / `dict[family]` for `_FAMILY_*`, `_GRAMMARS`,
    or similar behavior maps outside the metadata allowlist.
  - No `family ==` / `family in` checks outside trace/report fields
    explicitly allowlisted with reason comments.
  Metadata-only references (trace fields, package report tags,
  audit logs) are listed in `tests/contract/_family_dispatch_allowlist.py`
  with a reason per entry.
- For each family migrated: a side-by-side ShapeProgram diff test
  exists, comparing the pre-migration recipe output to the
  post-migration synthesizer output. Differences must be documented
  as intent-driven (e.g., brief now respected) or reduced.
- For each family migrated: a **build-artifact diff test** exists.
  At minimum: face count parity within ±20%, material zone count
  parity, package output count parity. Visible regressions block
  the migration.
- All 20 hard-surface NODE_TYPE generators implemented, each ≤ 300
  lines.
- The `DomainExtensionManifest` contract (from Cycle 1) is
  exercised by at least the hard-surface domain. Cycle 6 adds more.
- Authoring a new family requires creating a single `FamilyAlias`
  JSON file referencing existing StyleKnowledge + CompositionPolicy
  packs. Zero Python code change.

### 6.5 Dependencies

- Cycle 1 — required.
- Cycle 2 — strongly recommended; some recipes emit ops whose
  execution path is improved by Cycle 2's work.
- Cycle 4 — required to "complete" per family before that family's
  Cycle 3 migration is considered done. Cycles 3 and 4 cannot run
  fully sequentially; they interleave family-by-family.

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
finishing — each registered as a `DomainExtension` against the
contract Cycle 1 already shipped. **No engine code changes needed at
this point;** Cycle 6 is purely the act of registering additional
domain extensions with their own generators, schemas, and knowledge
packs.

This is what the v2 architecture buys: domain expansion becomes
data + plugin registration, not synthesizer redesign.

### 9.2 Lanes And Blockers Advanced

- **Lane J** (Multi-Domain Imagination-To-Life Demos) — primary
- **Phase 3** (Procedural Domain Libraries) — bulk of work

### 9.3 Concrete Deliverables

Per northstar §11 Phase 3 deliverables, each domain ships as a
`DomainExtension` per the Cycle 1 contract:

**Vegetation** (SpeedTree-inspired) — registers as
`DomainExtension(domain_id="vegetation", ...)`:

- Trunk/branch/leaf vocabulary as NODE_TYPE extensions:
  `trunk`, `branch`, `leaf_cluster`, `frond`, `root`, `bark`.
- Generic generators per type, under
  `lathe/asset_quality/procedural_synthesizer/generators/vegetation/`.
- StyleKnowledge packs for tree styles: deciduous, coniferous,
  palm, shrub, fern. Aliases reference them.
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

- 6 new domains each register as a `DomainExtension` per the Cycle 1
  contract. **No changes to engine code in `pipeline.py`,
  `registry.py`, `context.py`, `hint_resolution.py`, or `trace.py`.**
  If those files need changes to support a new domain, the Cycle 1
  contract was incomplete and the gap is fixed retroactively in Cycle
  1 with a follow-up commit — not by domain-specific accommodations
  in Cycle 6.
- 6 new domains each ship one production-grade authored fixture
  built end-to-end through the procedural engine.
- NODE_TYPES grow per-domain (not centrally); each domain's NODE_TYPES
  live in its own subpackage. Hard-surface NODE_TYPES are not touched.
- Per-domain visible-layer audit (Cycle 4 standards apply): real
  topology, real materials, real UV, real diagnostics.
- Each domain's repair routes (Cycle 5 standards) at least map one
  diagnostic to one repair action.
- Family count grows but Python recipe count stays at 0 — all new
  families are FamilyAlias JSON files referencing StyleKnowledge +
  CompositionPolicy + DomainExtension packs.
- `test_no_family_dispatch.py` still passes across all new domain code.

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

- A character_creature fixture (one of the family aliases that
  existed in the registry at Cycle 3 start, now migrated to a
  FamilyAlias JSON pointing at style + policy + animation domain
  extension) builds end-to-end with rig + skin + morph evidence in
  package artifacts.
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

## 12. Cross-Cycle Parallelization (Authoritative Sequencing)

This section is the authoritative sequencing reference. Where the
diagram in §3 disagrees, this section wins.

- **Cycle 1 must complete before Cycle 2 starts.** Cycle 2 depends
  on Cycle 1's typed attribute schemas, generator capability
  manifests, and `DomainExtensionManifest`. The v1 plan claimed
  they were orthogonal — that was wrong.
- **Cycles 2 and 3 may overlap.** Once Cycle 1's substrate ships,
  Cycle 2 (kernel capability) and Cycle 3 (recipe decommissioning)
  operate on orthogonal layers.
- **Cycle 3 cannot complete before Cycle 4 has caught up
  family-by-family.** A migration is "done" only after both
  ShapeProgram diff AND visible-artifact build pass. Cycles 3 and 4
  interleave family-by-family, not sequentially.
- **Cycles 4 and 5 are paired and ship in tightly alternating
  commits.** Each Cycle 4 visible-layer slice gets its Cycle 5
  diagnostic immediately after.
- **Cycle 6 cannot start before the `DomainExtensionManifest`
  contract from Cycle 1 has been exercised by at least one
  migration (typically the hard-surface domain registering itself
  in Cycle 1).** Once the contract is proven, each Cycle 6 domain
  registers independently and can ship in parallel with other
  domains.
- **Cycles 7 and 8 are strictly gated** by their dependencies and
  do not parallelize backward.

## 13. Verification Floor Per Cycle

Per the user's principle and the northstar's Rule of Truth (§4),
each cycle's verification floor is the minimum below which "this
works" cannot honestly be claimed.

**Every cycle includes:**

- `test_no_family_dispatch.py` (introduced in Cycle 1) must pass.
  This is the floor under "Lathe is procedural" — if the lint test
  fails, no cycle is "done" until it passes again.
- `test_shape_handoff_v1.py` contract test must pass.

**Per-cycle additional floor:**

| Cycle | Verification Floor |
|---|---|
| 1 | Common floor + synthesizer pipeline tests + attribute schema tests + knowledge loader schema-validation tests + domain extension contract test + unknown-family fixture builds a real GLB with visible panel + attached_to relation. 136+ unit tests green plus one build-artifact assertion. |
| 2 | Cycle 1 floor + kernel-program decomposition tests + 83-op `executed | approximated | unsupported` coverage assertion + Manifold-promoted-ahead-of-fallback test. ~180 tests green. |
| 3 | Cycle 2 floor + per-family migration diff tests + per-family build-artifact diff tests. Live `_RECIPES` count = 0 at cycle end. ~250+ unit tests + N family build diffs (N = registry size at cycle start). |
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
| Recipe domain knowledge incompletely captured in policy + style + alias data | 3 | Per-recipe migration acceptance includes both ShapeProgram diff AND build-artifact diff against original recipe output. Knowledge gaps surface as diff failures and are documented as required new generator capabilities or new composition policies. |
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

1. **Read this plan (especially the revision history at top), the
   northstar, the audit, and the procedural-synthesizer-spec v2** —
   in that order. ~30 minutes.
2. **Confirm git status clean and on main at origin/main.** Pull if
   needed.
3. **Open `procedural-synthesizer-architecture-spec.md` v2 §12 "First
   commit (single session, all-in-one slice)".** That sequence is
   the authoritative Cycle 1 first commit implementation order.
4. **Execute Cycle 1 first commit — production-grade, no stubs:**

   Engine code (`lathe/asset_quality/procedural_synthesizer/`):
   - `pipeline.py` with the 8 stages, every stage real.
   - `registry.py` with `GeneratorRegistry` keyed by
     `(domain, node_type)`, manifest inspection at registration time.
   - `trace.py` with `SynthesizerTrace`, `TraceEntry`, stage traces.
   - `hint_resolution.py` with the priority chain + attribution.
   - `domain_extension.py` with `DomainExtensionManifest` contract.
   - `attributes/primary_volume.py` and `attributes/panel.py` —
     typed schemas.
   - `knowledge_loader/{style.py, policy.py, alias.py}` + JSON
     schemas in `knowledge_loader/schemas/`.
   - `generators/hard_surface/primary_volume.py` — real generator
     with capability manifest.
   - `generators/hard_surface/panel.py` — real generator with manifest.
   - `decorators/hard_surface/attached_to.py` — real decorator
     with manifest.

   Declarative knowledge (`std/procedural/knowledge/`):
   - `style/industrial_pbr_v1.json`
   - `policy/panelized_hard_surface_object.json`

   Routing (`lathe/asset_quality/grammar_lowering.py`):
   - Wire `evaluate_grammar_lowering` to route unknown families
     through `synthesize_shape_program`. **The synthesizer produces
     real ShapeProgram output from the construction graph + brief.
     NO empty-program route.**

   Tests:
   - `tests/contract/test_no_family_dispatch.py` — the lint test
     that catches `_RECIPES.get(family)`, `_FAMILY_*` dispatch,
     `family ==`, `family in`. Initially trivially-passing (the
     synthesizer adds no new family dispatch); will catch future
     regressions across Cycles 2-8.
   - `tests/unit/test_procedural_synthesizer_pipeline.py` — 8-stage
     pipeline tests.
   - `tests/unit/test_procedural_synthesizer_primary_volume.py`.
   - `tests/unit/test_procedural_synthesizer_panel.py`.
   - `tests/unit/test_procedural_synthesizer_attached_to.py`.
   - One end-to-end test where an authored-intent-only fixture
     (primary_volume + 2 panels + attached_to edges, no family
     alias) produces a non-empty ShapeProgram AND builds to a real
     GLB containing the expected geometry.

   Verify the 136+ test slice green plus the new tests, commit,
   push.

5. **Update this plan's §1 "Starting Position"** to reflect the
   shipped slice. Commit the docs update.

That is the first session's complete shape. Subsequent sessions
extend Cycle 1's deliverable list (more generators / decorators /
attribute schemas / knowledge packs), then advance to Cycle 2 or
overlap with Cycle 3. **No session ships a no-op skeleton.**

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
