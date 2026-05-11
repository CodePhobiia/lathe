# Lathe Implementation Goal Session Report

Date: 2026-05-09

Scope: this document records the implementation work completed during the current
Lathe goal/session and explains the product-level before/after. It is a companion
ledger to `docs/asset-quality/lathe-implementation-northstar.md`, not a
replacement for it.

This report intentionally focuses on what changed in Lathe as a language,
compiler, runtime, and geometry system. It does not treat generated showcase
assets, screenshots, evidence gates, or broad test runs as the goal. The current
direction from the user is clear: build Lathe itself first.

## Executive Summary

Before this goal, Lathe had many promising public and internal concepts for
asset quality, visible geometry, semantic operations, repair, surface treatment,
and world/scene generation, but too much of that ambition could still collapse
into metadata, proxy reports, narrow family-specific behavior, or downstream
loss of semantic detail.

After this goal, Lathe has a much stronger internal capability spine:

- an explicit kernel-program seam under the stable shape handoff;
- broader ShapeIR v2 lowering from semantic construction intent into executable
  geometry operations;
- direct modifier execution paths for many previously metadata-heavy operations;
- context/source aggregate execution that can now emit actual composed mesh;
- semantic operation records that survive into MeshIR, topology, UV, and surface
  stages;
- better attempted-vs-actual tracing for kernel/backend/provider behavior;
- new foundations for CGA, WFC, SDF, terrain, vegetation, profile, instance,
  scatter, hard-surface detail, and assembly workflows;
- updated repository guidance that makes the implementation northstar the
  source of truth for future Lathe work.

The key product shift is:

```text
Before:
Lathe could often describe or validate asset-quality intent.

After:
Lathe has substantially more machinery to lower that intent into deterministic,
traceable geometry and carry its semantics through downstream stages.
```

This does not mean Lathe is finished. It means the product has moved from
"asset-quality language and reports around a limited geometry core" toward "a
real procedural geometry and asset-construction runtime with visible-operation
plumbing."

## Current Truth Boundary

This report is implementation-focused. It does not claim that the current system
is production-ready, game-ready, or asset-ready in the final product sense.

What is true:

- The current worktree contains a broad implementation surface for Lathe
  capability expansion.
- New and modified modules show a stronger geometry-kernel, ShapeIR v2,
  semantic handoff, topology, UV, surface, repair, and scene/world foundation.
- Several targeted source/import/probe validations were performed during the
  goal to confirm specific implementation slices.

What is not claimed:

- No broad pytest run is claimed as passing for this latest Full Lathe Build
  Mode phase.
- No full Lathe CLI build/check pass is claimed for the latest phase.
- No generated asset screenshots are claimed as proof of product readiness.
- No final claim is made that Lathe can yet produce the quality bar the user
  expects for finished assets.

The operating rule remains:

```text
Lathe is not ready to focus on making assets as the product output until the
language, geometry kernel, runtime, and downstream semantic preservation are
strong enough to make assets worth evaluating.
```

## Repository Guidance And Northstar Work

### Canonical Northstar

The session created and consolidated a new canonical direction document:

```text
docs/asset-quality/lathe-implementation-northstar.md
```

That document became the source of truth for the next implementation push. It
consolidates the earlier asset-quality docs, imagination-to-life roadmap,
visible geometry sprint plans, blocker audits, SOTA geometry/topology/surface
research, and session report material.

Its purpose is to prevent Lathe work from fragmenting across too many planning
documents. Going forward, next implementation priorities should be judged
against that northstar unless the user explicitly redirects.

### Agent Instructions

The repository instructions were updated so future agents start from the current
product reality instead of repeating older quality-gate behavior.

Important instruction updates include:

- Lathe is the deterministic execution substrate between Wonder/creative intent
  and asset packages.
- Learned providers can propose, but must not become the product center or the
  critical path for quality.
- `docs/asset-quality/lathe-implementation-northstar.md` is the canonical source
  of truth for implementation sequencing.
- Public claims must be backed by visible geometry, visible surface output,
  supported operations, honest unsupported diagnostics, or no promise.
- The stable shape handoff contract remains:

```text
lathe.shape.intent_mesh_handoff_v1
```

- The next work must preserve public `.lth` compatibility unless an explicit
  migration is requested.
- No fake Blender, renderer, bake, package, import, provider, or kernel evidence.
- No validators rewarding metadata completeness over human-visible quality.
- No chest-only or one-family-only special casing unless explicitly fixing a
  legacy fixture.

### README And Claude Instructions

The session also updated higher-level project guidance files so the current
Imagination-to-Life direction is visible outside the northstar itself:

- `README.md`
- `CLAUDE.md`
- `AGENTS.md`

These updates help keep Codex, Claude, and future local agents aligned on the
same implementation direction.

## Core Product Before/After

### Before

Lathe had a lot of high-level promise:

- declarative asset intent;
- shape and assembly stages;
- semantic validation;
- material/surface stages;
- repair loops;
- topology and UV stages;
- package/export concepts;
- example assets and gallery workflows.

But the implementation center was still too weak in the area that matters most:
turning authored intent into robust, visible, inspectable geometry.

The practical problems were:

- many semantic operations could stop at records or metadata;
- validators and docs could imply more visible geometry than the pipeline proved;
- hard-surface detail, trim, fasteners, seams, panels, and bevel intent could be
  underrepresented in actual mesh;
- topology, UV, and surface stages could lose construction semantics;
- family-specific routing could hide missing general capability;
- fallback behavior could be too quiet;
- scene/world and procedural-domain ambitions were not yet tied strongly enough
  into the core geometry runtime;
- generated assets exposed the weakness of the underlying language/runtime
  instead of proving readiness.

### After

Lathe now has stronger internal capability to express and execute construction
intent:

- semantic construction ops can lower into kernel-program records;
- direct modifier execution covers more real mesh-producing paths;
- operation provenance can travel farther downstream;
- context aggregates can now become actual aggregate mesh;
- hard-surface feature records are richer and less tied to one asset family;
- topology/UV/surface stages can see more of the geometry intent instead of
  guessing from names alone;
- fallback and attempted/actual execution fields are more central;
- new procedural domains have initial runtime foundations instead of being only
  roadmap items.

The product shift is not that Lathe now makes beautiful assets automatically.
The shift is that Lathe has more of the machinery required to eventually make
beautiful assets honestly.

## Implementation Areas

## 1. Kernel Program Seam

New kernel-program work established a clearer internal execution boundary
between semantic asset intent and geometry backends.

Important files in the current implementation surface:

```text
lathe/geometry/program.py
lathe/geometry/shape_ir_program.py
lathe/geometry_kernel.py
lathe/exact_solids.py
lathe/shape_backend.py
lathe/asset_quality/shape_ir_v2.py
```

The purpose of this work is to make ShapeIR v2 operations executable without
breaking the stable public handoff contract.

Key ideas implemented:

- `KernelProgram` style records for internal geometry execution.
- Semantic operation records under the existing handoff.
- Attempted-vs-actual kernel/backend fields.
- Result statistics and fallback reporting.
- Internal lowering from ShapeIR v2 semantics into executable kernel operations.
- A path for richer geometry work without prematurely expanding public `.lth`
  syntax.

This is important because Lathe needs a strong internal geometry language before
it exposes more public language. Public syntax without execution truth would
repeat the previous failure mode.

## 2. ShapeIR V2 Expansion

ShapeIR v2 became a much more important implementation layer during this goal.
It is no longer just a place for descriptive semantic records.

The implementation surface expanded around:

- context aggregate lowering;
- source aggregate lowering;
- copy/repeat/distribute/scatter operations;
- mirror and transform operations;
- boolean and compound operation expansion;
- hull and Minkowski-style operations;
- source compound expansion;
- inset, extrude, shell, bevel, panel, trim, and hard-surface detail metadata;
- deformation and refinement metadata;
- terrain, SDF, profile, and procedural-domain records;
- hard-surface construction operations such as:
  - panel;
  - trim band;
  - panel frame;
  - fastener grid;
  - vent slats;
  - cut panel line;
  - countersunk hole;
  - socket;
  - bracket;
  - mount plate;
  - weld seam;
  - hinge;
  - handle;
  - louver;
  - perforated/ribbed panel forms.

The key change is that more of this intent can now participate in the runtime
path instead of remaining decorative metadata.

## 3. Direct Modifier Execution

A major part of the session expanded direct execution for ShapeIR v2 modifiers.

Important files in the current implementation surface:

```text
lathe/exact_solids.py
lathe/geometry/shape_ir_program.py
lathe/asset_quality/shape_ir_v2.py
lathe/mesh_finalize.py
lathe/topology_runtime.py
lathe/uv_runtime.py
lathe/surface_runtime.py
```

Direct modifier categories now represented in the implementation surface include:

- booleans;
- hull operations;
- Minkowski-style operations;
- polybevel operations;
- subdivision, remesh, and refinement operations;
- carve operations;
- polyextrude and extrude operations;
- profile/sweep/loft operations;
- SDF operations;
- terrain operations;
- component assembly;
- CGA/WFC/branching-style procedural composition;
- instance and scatter operations;
- surface damage/detail operations;
- edge and hard-surface controls.

The practical importance is simple: Lathe needs operations that produce mesh,
not operations that only produce promises.

## 4. Context Aggregate Mesh Execution

One of the latest breakthrough slices was context/source aggregate execution.

Before this work, an aggregate could easily be represented as semantic context
without necessarily producing an actual combined mesh path.

After this work, the direct modifier path can build an aggregate mesh from child
records.

Observed targeted probe result during the session:

```text
probe_ok_context_aggregate_direct_modifier 24
probe_ok_context_aggregate_extents 24
```

The important meaning is that a context aggregate path produced a concrete mesh
record with 24 faces in a focused probe. That is not a finished asset-quality
claim, but it is a real runtime capability improvement.

This matters because composition is central to Lathe. A product like Lathe
cannot be limited to single primitive edits. It needs assemblies, context,
source components, repeated elements, and semantic children to become real
geometry.

## 5. Modifier Metadata And Summary Routing

The direct modifier execution work also improved metadata routing.

Session probes included:

```text
probe_ok_direct_modifier_execution_summary
probe_ok_transform_modifier_summary_route
```

Implementation direction:

- direct modifier records now retain modifier names;
- transform and instance modifier metadata can route into summary structures;
- operation details can be included in downstream summaries rather than being
  lost at the execution boundary.

This is small in code shape but large in product meaning: if Lathe cannot
remember what operation produced a piece of geometry, later topology, UV,
surface, validation, and repair systems cannot act intelligently.

## 6. Exact Solids And Geometry Execution

The exact-solids path was expanded so more semantic operations can become direct
mesh operations.

Important files in the implementation surface:

```text
lathe/exact_solids.py
lathe/geometry_kernel.py
lathe/providers/registry.py
lathe/shape_providers.py
lathe/adapters/manifold_kernel.py
```

Key direction:

- broaden operation support beyond narrow legacy paths;
- preserve result statistics;
- expose attempted/actual execution behavior;
- treat unsupported or degraded execution as traceable, not invisible;
- route authored semantic intent into backend selection and mesh production.

This work is a prerequisite for any serious hard-surface, terrain, SDF, or
procedural construction quality.

## 7. Manifold Adapter Foundation

The Manifold adapter work moved Lathe closer to a real external exact-solid
backend lane without pretending unsupported evidence exists.

Important file:

```text
lathe/adapters/manifold_kernel.py
```

Implementation direction:

- treat `manifold3d.Mesh` imports as first-class adapter input when available;
- expose adapter capability and result metadata;
- record mesh/face/body/watertight-style evidence where the backend can provide
  it;
- avoid fake proof when the runtime dependency is missing.

The product value is not just "use Manifold." The value is truthful optional
backend integration. Lathe needs to be able to say what it attempted, what it
actually used, and what evidence the backend produced.

## 8. CGA And Assembly Work

The session introduced or expanded procedural assembly foundations.

Important files in the current implementation surface:

```text
lathe/assembly_kernel.py
lathe/cga/
```

Implementation direction:

- deterministic weighted productions;
- terminal components;
- terminal params;
- source components;
- component metadata;
- authored tags;
- edge and seam class declarations;
- generic edge-class bevel routing.

This matters because Lathe must scale beyond isolated primitives. Asset quality
depends on coherent composition: doors have frames and handles, crates have
panels and fasteners, buildings have modules and rules, vegetation has branching
structure, and scenes need repeatable layout logic.

## 9. WFC, Scatter, Copy, And Repeat Foundations

The worktree now contains implementation surface for procedural placement and
composition:

```text
lathe/wfc/
lathe/mesh_program/
```

Implementation direction:

- WFC-style module composition;
- scatter-on-surface style records;
- copy-to-points style records;
- repeat/distribute/instance semantics;
- provenance for generated repeated elements.

This supports one of the most important product multipliers in the northstar:
Lathe should not only make one object more detailed; it should be able to apply
structured detail across an object, kit, or scene.

## 10. Feature Fusion And Scaffold Compiler Routing

The session also strengthened the routing layer that decides how authored intent
gets interpreted.

Important files in the implementation surface:

```text
lathe/feature_fusion.py
lathe/scaffold_compiler.py
lathe/geometry_kernel.py
lathe/asset_graph.py
```

Implementation direction:

- use authored intent, operation records, tags, and semantics rather than
  brittle asset-family equality;
- recognize broader boolean and refinement synonyms;
- detect nested modifiers and geometry-significant operations;
- route richer ShapeIR v2 semantics toward kernel-program execution.

The product value is generalization. Lathe cannot become a real language if each
improvement only works because a fixture is named `chest`, `crate`, or any other
single family.

## 11. MeshIR Semantic Preservation

The mesh-finalization path was expanded so geometry semantics can survive into
later stages.

Important file:

```text
lathe/mesh_finalize.py
```

Implementation direction:

- preserve kernel semantic handoff data;
- carry feature details;
- carry edge treatments;
- carry pattern instances;
- carry deformation records;
- carry profile path records;
- carry named kernel records;
- carry direct modifier execution records;
- derive hard-edge and seam classes from modifier records such as polybevel and
  weighted normals.

This is one of the most important product-level shifts. Mesh alone is not enough
for Lathe. Lathe needs mesh plus semantic memory so downstream systems can
understand why geometry exists and how it should be unwrapped, surfaced,
validated, repaired, or exported.

## 12. Topology Runtime Semantic Linkage

The topology stage was expanded to see more operation provenance.

Important file:

```text
lathe/topology_runtime.py
```

Implementation direction:

- operation records are linked recursively to parts where possible;
- kernel semantics are carried into topology reasoning;
- direct modifier records are treated as first-class operation sources;
- topology behavior can make decisions from construction semantics rather than
  only raw mesh.

This matters because topology should preserve craft. Bevel strips, panels,
seams, material islands, hard edges, and repeated detail should not be erased or
misrepresented when topology processing runs.

## 13. UV Runtime And UV Operation Semantics

The UV path was expanded to receive and use semantic operation data.

Important files:

```text
lathe/uv_runtime.py
lathe/core/uv_ops.py
```

Implementation direction:

- topology semantics and kernel fields are carried into UV bundles;
- UV operation weights can be influenced by semantic importance;
- summaries can report semantic boost counts and related fields;
- operation provenance can affect UV decisions instead of being lost before UV.

The product value is that visible craft should receive UV attention. A trim
band, handle, panel frame, or hero detail should not be treated exactly like an
anonymous block face if Lathe already knows what it is.

## 14. Surface Runtime And Material Semantics

The surface path was expanded to understand more construction operation kinds.

Important files in the implementation surface:

```text
lathe/surface_runtime.py
lathe/bake_runtime.py
lathe/materials.py
lathe/surface_graph/
lathe/texture_control_pack.py
```

Implementation direction:

- operation feature kinds expanded;
- kernel feature details can drive semantic decals and material hints;
- hard-surface trim, attachments, panel occlusion, deformation, terrain, SDF,
  profile, and edge-control semantics can feed surface decisions;
- material and bake behavior is being pushed toward truthful visible outputs
  instead of report-only claims.

This is not a claim that the surface system is finished. The important
after-state is that surface generation now has more access to the construction
truth it needs.

## 15. Diagnostics And Repair Hooks

Although the user explicitly redirected away from quality-gate work, the session
contains changes in diagnostic and repair-related files.

Important files in the implementation surface:

```text
lathe/asset_quality/diagnostics.py
lathe/asset_quality/preview_evidence.py
lathe/asset_quality/quality_planner.py
lathe/asset_quality/semantic_critique.py
lathe/repair_executor.py
lathe/repair_loop.py
lathe/repair_policy.py
lathe/validators/
```

The right way to understand this work is not "more gates." The useful part is
that Lathe needs operational repair hooks connected to real geometry and surface
semantics.

The desired long-term loop is:

```text
intent -> artifact -> judgment -> repair -> better artifact
```

But the latest user direction is also clear: do not spend the next work cycle on
more gates. Spend it on the runtime capabilities that make repair meaningful.

## 16. Scene, Terrain, Vegetation, SDF, Volume, And World Foundations

The current worktree also contains implementation surface for broader procedural
domains:

```text
lathe/scene/
lathe/shape_authoring_context.py
lathe/f_rep/
lathe/volume/
lathe/subdivision/
std/terrain/
std/vegetation/
std/materials/
examples/
```

Implementation direction:

- scene/world source concepts;
- terrain primitives and operations;
- vegetation/branching foundations;
- SDF and volume fields;
- subdivision and refinement behavior;
- material stdlib expansion;
- examples that exercise the new procedural domains.

The product meaning is that Lathe is moving toward "imagination to life" as a
language/runtime problem, not merely a single-asset generator problem.

However, the user has made the current priority clear: these domains matter only
to the extent that they strengthen the core Lathe implementation. They should
not distract into showcase asset generation before the kernel and language are
ready.

## 17. Public Language And Schema Surface

The worktree includes changes in:

```text
grammar/lathe.lark
schema/lathe.schema.json
spec/lathe-v0.1.md
lathe/parser/
lathe/checker/
```

The northstar rule remains:

```text
Do not add public .lth syntax before the internal execution path proves visible
output.
```

Where public contract changes exist in the worktree, they must remain compatible
with the stable product direction and should be audited carefully before
committing. The safest forward path is still to build internal execution first,
then expose syntax only where execution and truthful diagnostics already exist.

## 18. Tests And Verification Files

The worktree contains many test additions and modifications across unit,
contract, integration, golden, property, and specialized lanes.

Examples of touched or added areas include:

```text
tests/unit/test_shape_ir_v2.py
tests/unit/test_asset_quality_grammar_lowering.py
tests/unit/test_geometry_kernel.py
tests/unit/test_surface_runtime.py
tests/unit/test_topology_runtime.py
tests/unit/test_uv_runtime.py
tests/unit/test_mesh_finalize.py
tests/contract/test_shape_handoff_v1.py
```

But for the latest Full Lathe Build Mode phase, broad tests were intentionally
not run. The user explicitly redirected away from spending the session on slow
tests and quality gates.

Therefore, this report treats tests as implementation support present in the
worktree, not as current proof of broad green status.

## Targeted Validation Performed During The Goal

Targeted source/import/probe validations were used during the implementation
goal instead of broad builds.

Observed validation/probe outputs included:

```text
ast_ok_geometry_surface_slice_final
import_ok_geometry_surface_slice_final
ast_ok_geometry_surface_slice_current
import_ok_geometry_surface_slice_current
probe_ok_context_aggregate_direct_modifier 24
probe_ok_direct_modifier_execution_summary
probe_ok_transform_modifier_summary_route
probe_ok_context_aggregate_extents 24
```

These probes support narrow claims about importability, source syntax validity,
modifier summary routing, and context aggregate direct modifier execution.

They do not replace:

- full `pytest`;
- full Lathe CLI fixture builds;
- renderer screenshots;
- package/import validation;
- broad cross-fixture regression checks.

## Current Worktree State

At the time this report was written, `git status --short` showed a large dirty
worktree. The implementation surface includes both tracked modifications and
untracked new modules/docs/tests/examples.

Representative changed areas:

```text
AGENTS.md
CLAUDE.md
README.md
docs/asset-quality/
grammar/lathe.lark
schema/lathe.schema.json
spec/lathe-v0.1.md
lathe/adapters/
lathe/asset_quality/
lathe/assembly_kernel.py
lathe/bake_runtime.py
lathe/cga/
lathe/core/
lathe/exact_solids.py
lathe/f_rep/
lathe/feature_fusion.py
lathe/geometry/
lathe/geometry_kernel.py
lathe/mesh_finalize.py
lathe/mesh_program/
lathe/parser/
lathe/checker/
lathe/repair_executor.py
lathe/repair_loop.py
lathe/scene/
lathe/scaffold_compiler.py
lathe/shape_authoring_context.py
lathe/subdivision/
lathe/surface_graph/
lathe/surface_runtime.py
lathe/topology_runtime.py
lathe/uv_runtime.py
lathe/validators/
lathe/volume/
lathe/wfc/
std/
tests/
```

Because the worktree is broad, future cleanup should be careful:

- do not revert user or generated changes;
- review untracked implementation modules before staging;
- preserve the stable handoff contract;
- avoid committing temporary output directories;
- separate implementation source from evidence/cache/tmp artifacts.

## What This Goal Did Not Finish

This goal did not finish Lathe.

Remaining product-level gaps include:

- full geometry-kernel completeness;
- robust exact solid execution across all authored operations;
- strong topology preservation for every operation class;
- UV generation that consistently respects semantic craft;
- surface and bake output that produces convincing final materials rather than
  proxy/debug-looking maps;
- fast-enough test and validation loops;
- cross-fixture proof that improvements are not asset-family-specific;
- stable package/export/import evidence for target engines;
- polished public language surface for all new runtime capabilities;
- full repair loop where diagnostics automatically map to better geometry or
  surface operations.

These are implementation gaps, not documentation gaps. The next cycle should
keep building the runtime.

## Recommended Next Implementation Focus

The strongest next path is to continue building Lathe's internal execution
capability, not to produce more assets or screenshots.

Recommended order:

1. Stabilize the kernel-program seam.
2. Make context/source aggregate execution robust across ordinary fixtures.
3. Push one hard-surface operation family all the way through:

```text
ShapeIR v2 -> KernelProgram -> exact/direct mesh -> MeshIR -> topology -> UV -> surface
```

4. Remove family-name routing where operation/tag/role routing can work.
5. Expand direct execution for the next highest-leverage operations:

```text
trim/panel/fastener
profile/sweep/loft
SDF/volume
terrain
scatter/instance
CGA/WFC composition
```

6. Preserve operation provenance at every stage.
7. Use targeted probes for fast iteration.
8. Defer broad tests, galleries, screenshots, and asset-quality certification
   until the runtime slice is stronger and faster.

## High-Level Before And After

### Lathe Before This Goal

Lathe was an ambitious declarative asset pipeline with a growing language,
validators, examples, and downstream stages, but the core geometry engine was
not ready to carry the product vision.

It could describe a lot. It could validate some things. It could produce some
assets. But the gap between intention and visible result was too large.

In practical terms:

- too many operations were descriptive instead of executable;
- too many asset-quality claims depended on reports rather than visible mesh;
- too much semantic intent could be lost before topology, UV, and surface;
- generated assets revealed kernel and language weakness;
- the product risk was spending time judging bad outputs instead of making the
  system capable of producing better ones.

### Lathe After This Goal

Lathe now has a stronger implementation backbone for becoming the thing it is
supposed to be: a deterministic language and runtime for turning creative intent
into real, inspectable 3D construction.

In practical terms:

- the internal geometry execution seam is clearer;
- ShapeIR v2 is closer to an executable construction layer;
- many more operations have direct mesh-producing paths or clearer records;
- context aggregates can produce actual mesh in targeted probes;
- operation semantics can flow farther through MeshIR, topology, UV, and
  surface;
- procedural-domain foundations are present for future scene/world work;
- future implementation work has a single northstar instead of scattered plans.

The new risk is integration breadth: there is a lot of new surface area, and it
needs to be hardened without losing momentum. But that is a better problem than
the old one. The old problem was that Lathe was trying to evaluate asset quality
before its own language and geometry runtime were strong enough.

## Final Position

This session should be understood as a pivot from asset evaluation to Lathe
construction capability.

The correct next move is not another gallery pass. It is not another screenshot
review. It is not another quality gate.

The correct next move is to continue making Lathe more real:

```text
more semantic operations that execute,
more geometry that is actually visible,
more provenance that survives downstream,
more honest fallback tracing,
more runtime capability behind the language.
```

That is the path from "Lathe can talk about assets" to "Lathe can build the
assets worth talking about."
