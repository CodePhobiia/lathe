# Lathe Agent Instructions

## What This Repository Is

Lathe is a declarative language, compiler, and deterministic runtime for turning 3D asset intent into inspectable, repairable, exportable asset packages.

The product boundary is:

```text
Wonder / creative director
= asks for assets, scenes, inspections, repairs, and revisions

Lathe
= executes those requests into deterministic geometry, materials, previews,
   reports, exports, packages, and repair evidence
```

Lathe is the execution substrate. Learned providers may exist as optional proposal sources, but they are not the product center and must not become the critical path for asset quality work.

## Canonical Northstar

Before doing visible-geometry, asset-quality, Wonder-readiness, procedural-domain, or implementation-priority work, read:

```text
docs/asset-quality/lathe-implementation-northstar.md
```

That document is the canonical source of truth for the next Lathe implementation push. It consolidates the imagination-to-life roadmap, asset-quality docs, blocker audits, SOTA research, session report, and current execution plan.

If another doc conflicts with the northstar, prefer the northstar for next implementation sequencing unless the user explicitly redirects.

## Current Implementation Focus

The next implementation push is:

```text
visible-geometry-kernel-sprint-0
```

Objective:

```text
Make one existing hard-surface fixture visibly better while preserving public
source compatibility and the stable shape handoff contract.
```

Primary fixture:

```text
industrial_crate / sci-fi crate
```

Secondary guardrail:

```text
mechanical_door or fantasy_weapon
```

The required product loop is:

```text
intent -> artifact -> evidence -> judgment -> repair -> better artifact
```

Work that does not strengthen that loop is lower priority unless the user explicitly asks for it.

## Rule Of Truth

For every public or reportable asset-quality claim, one of these must be true:

1. Lathe builds it as visible geometry or visible surface output.
2. Lathe lowers it into supported construction operations.
3. Lathe reports the unsupported or degraded state honestly.
4. Lathe does not promise it yet.

Forbidden state:

```text
Language, docs, validator, or report says it happened,
but mesh, material, preview, package, or import evidence does not prove it.
```

Never claim an output is production-ready, game-ready, Roblox-ready, Unity-ready, Unreal-ready, fixed, complete, or done unless the relevant evidence was actually generated and checked.

Use truthful claim labels:

- `real`: visible in mesh/material/preview/export evidence.
- `proxy`: deterministic placeholder or non-final evidence, explicitly labeled.
- `fallback`: requested path degraded to another path, with attempted and actual recorded.
- `unsupported`: rejected or warned before false success.
- `not verified`: code exists but no relevant command/artifact was produced in the current run.
- `blocked`: required dependency or upstream condition is missing and named.

## Stable Contracts

Preserve these unless the task explicitly asks for a migration:

- Public `.lth` source compatibility.
- Stable shape-stage handoff contract: `lathe.shape.intent_mesh_handoff_v1`.
- Public language surface around `profile`, `contract`, `critic`, `asset`, `variant`, and build-stage names.
- Stable backend IDs unless a migration is requested.
- Downstream topology, UV, surface, validate, package, and publish contracts unless the task names a coordinated change.
- Attempted-vs-actual tracing for providers, kernels, renderers, topology adapters, UV adapters, package exporters, and external import evidence.

Internal architecture can evolve underneath the stable handoff when changes are additive, tested, and truth-preserving.

## Non-Negotiable Implementation Rules

- Do not add public `.lth` syntax before the internal execution path proves visible output.
- Do not fake Blender, xatlas, Manifold, renderer, bake, package, import, or learned-provider evidence.
- Do not hide fallback behavior.
- Do not let validators reward metadata completeness over human-visible quality.
- Do not weaken tests, validators, type checks, or safety gates just to show progress.
- Do not ship placeholder code, TODO-only branches, dead paths, or success-shaped defaults.
- Do not add chest-only or one-family-only behavior unless the task is explicitly a legacy fixture fix.
- Prefer tag, asset-class, component-role, operation, stdlib, or authored-rule dispatch over family-name equality.
- Do not clean, revert, or overwrite unrelated user or generated changes.
- Keep diffs small, but fix root causes rather than symptoms.
- When public behavior changes, update the relevant docs, schemas, examples, and tests.

## Decision Filter Before Coding

Before implementing, answer:

1. What visible claim does this make true?
2. Which fixture proves it?
3. Which artifact path will show it?
4. Which diagnostic or report field will judge it?
5. Which repair route can use it, if any?
6. Does it preserve `.lth` compatibility and `lathe.shape.intent_mesh_handoff_v1`?
7. Does it avoid chest-only or one-family-only logic?
8. If it falls back, will users see attempted vs actual behavior?
9. What is the narrowest test or build that proves the change?
10. What remains explicitly not verified?

If those answers are weak, inspect more context or reduce the task until the proof is clear.

## Sprint 0 Expected Sequence

Unless the user redirects, prefer this implementation order:

1. Create or update `docs/asset-quality/visible-geometry-sprint-0-evidence.md` with baseline evidence.
2. Strengthen preview evidence and artifact-path reporting.
3. Implement one visible crate operation: trim band or fastener grid first; bevel/chamfer if safe.
4. Add diagnostics for weak hierarchy, missing detail, debug-material look, and proxy-only preview evidence.
5. Wire one semantic repair mapping from a visible diagnostic to a concrete operation.
6. Rebuild the crate and record before/after preview paths, report metrics, and package/export artifacts.
7. Add private `KernelProgram` / lowering seam only after the visible slice has evidence.
8. Fix surface truth bugs touched by the slice, especially tangent-space normal and material-zone visibility.
9. Harden topology/UV where detail is being lost or misrepresented.
10. Run the guardrail fixture to prove the work is not crate-only.

## Change Rules By Area

### Language Contract Changes

Only change the public language when explicitly requested or when a planned migration is part of the task.

If changing the language contract, update all relevant layers together:

- `spec/lathe-v0.1.md`
- `grammar/lathe.lark`
- `schema/lathe.schema.json`
- parser / normalizer / resolver / checker behavior
- examples
- tests
- docs that describe the public surface

### Geometry, Shape, And Kernel Changes

Preserve `lathe.shape.intent_mesh_handoff_v1`.

When changing geometry execution:

- preserve or add semantic IDs for primitive, part, operation, seam group, hard edge, material zone, and fallback state where relevant;
- report attempted kernel, actual kernel, unsupported operation, approximation, fallback reason, watertightness/body-count evidence where relevant;
- make unsupported ops diagnostics, not silent drops;
- keep proxy or degraded outputs clearly labeled.

High-priority seams:

- `ShapeIR / ShapeIR v2 / mesh_program -> KernelProgram`
- `KernelProgram -> GeometryKernel`
- `ShapeKernelResult -> MeshIR / shape bundle`
- semantic provenance into topology / UV / surface / validate / package

### Asset Quality And Diagnostics

Validators must judge visible output and artifact evidence.

Prioritize diagnostics for:

- primitive/blockout appearance;
- debug-material final previews;
- missing bevel/chamfer/detail evidence;
- weak primary/secondary/tertiary hierarchy;
- weak material-zone contrast;
- poor attachment seating;
- fake high/low detail;
- boolean or kernel fallback;
- proxy-only or missing preview evidence;
- texel-density drift where UV evidence exists.

Diagnostics should include actionable repair routes when feasible.

### Surface, Bake, And Material Changes

Surface claims must appear in final preview or texture evidence, not only JSON.

Prioritize:

- tangent-space normal maps, not world-space face-normal polygon fill;
- final beauty distinct from material-ID/debug preview;
- real or clearly proxy-labeled basecolor, normal, AO, curvature, roughness/ORM, emissive, wear, and grime evidence;
- authored-vs-proxy map reporting;
- material zones with readable contrast;
- DesignerGraph or LayerStack buffers when making graph claims;
- per-engine normal/color-space conventions when packaging.

### Topology And UV Changes

Topology and UV must preserve visible craft rather than erase it.

When changing these stages:

- preserve named parts, seam groups, bevel strips, hard edges, and material zones where possible;
- report attempted vs actual topology/UV adapters;
- do not silently pass through or collapse detail;
- add texel-density audit before claiming hero-quality surface output;
- report requested vs actual density and fallback reason.

### Backend And Provider Changes

Backend/provider changes must:

- preserve stable backend IDs unless migration is requested;
- preserve shape bundle contract and trace fields;
- keep downstream contracts stable unless explicitly broadened;
- use mocked tests for external services;
- record attempted provider/backend and actual provider/backend;
- never make learned providers the asset-quality critical path.

### Example Asset Changes

When editing examples:

- keep at least one runnable `generate` example;
- keep at least one runnable `reconstruct` example;
- keep example refs minimal and checked into `examples/refs/`;
- update `docs/examples_catalog.md` when adding checked-in `examples/**/*.lth`;
- ensure examples pass the current checker and relevant build path, or document exact blockers.

## Canonical Commands

Use `python -m lathe.cli` from the repository root unless the editable install is already active.

General:

```powershell
python -m lathe.cli doctor
python -m lathe.cli normalize examples/courier_drone.lth
python -m lathe.cli check examples/courier_drone.lth
python -m lathe.cli plan examples/courier_drone.lth courier_drone
python -m lathe.cli materialize examples/courier_drone.lth courier_drone_mobile
python -m lathe.cli build examples/courier_drone.lth courier_drone --out dist
python -m lathe.cli shape-providers
python -m lathe.cli probe-providers --runtime-config examples/runtime_configs/auto_learned.json
```

Sprint 0 baseline:

```powershell
git status --short
python -m lathe.cli check examples/industrial_crate.lth
python -m lathe.cli check examples/mechanical_door.lth
python -m lathe.cli build examples/industrial_crate.lth industrial_crate --out .tmp_tests/baseline_industrial_crate --deterministic
python -m lathe.cli build examples/mechanical_door.lth mechanical_door --out .tmp_tests/baseline_mechanical_door --deterministic
```

Fast visual iteration:

```powershell
python -m lathe.cli quick examples/bevel_demo.lth bevel_demo --out tmp_bevel_demo.glb
python -m lathe.cli quick examples/alien_grove_showcase.lth alien_grove --out tmp_alien_grove.glb --no-cache
```

Helper scripts:

```powershell
scripts/lathe_smoke.ps1
```

```bash
scripts/lathe_asset_loop.sh <file.lth> <asset_name> [out_dir]
scripts/lathe_smoke.sh
```

## Validation Expectations

Identify the narrowest relevant check before editing. For bug fixes, reproduce the failure when feasible. For new behavior, add or update tests that would fail before the change.

Targeted checks:

```powershell
python -m pytest -q tests/unit/test_asset_quality_preview_evidence.py tests/unit/test_asset_quality_diagnostics.py tests/unit/test_asset_quality_generation_steering.py
python -m pytest -q tests/unit/test_shape_ir_v2.py tests/unit/test_asset_quality_grammar_lowering.py tests/unit/test_geometry_kernel.py
python -m pytest -q tests/unit/test_surface_runtime.py tests/unit/test_asset_quality_material_wear_graph.py
python -m pytest -q tests/contract/test_shape_handoff_v1.py
```

Full suite:

```powershell
python -m pytest -q
```

Run the full suite when behavior changed broadly or after targeted checks are green. If a check cannot be run, state exactly why and what remains unverified.

## Evidence Requirements

For visible-geometry or asset-quality work, report exact evidence paths:

- source fixture;
- command run;
- output directory;
- shape bundle;
- topology bundle;
- UV bundle;
- surface maps/control pack;
- validation report;
- package/export artifact;
- preview image or explicit proxy/missing status;
- before/after comparison when repair is involved.

Do not describe visual improvement without pointing to generated artifacts or saying it was not verified.

## Repository Map

Core language and compiler:

- `grammar/lathe.lark` defines public syntax.
- `schema/lathe.schema.json` is the normalized AST schema.
- `spec/lathe-v0.1.md` is the compatibility anchor.
- `lathe/parser.py` and `lathe/parser/` parse source and resolve refs.
- `lathe/normalizer.py` inserts defaults.
- `lathe/resolver.py` applies `uses` chains and variant patches.
- `lathe/checker.py` and `lathe/checker/` enforce semantic rules.
- `lathe/planner.py` emits build plans.
- `lathe/executor.py` runs deterministic downstream stages.

Shape and geometry:

- `lathe/shape_backend.py` owns the stable shape-stage contract.
- `lathe/shape_ir.py` defines stable shape primitives.
- `lathe/asset_quality/shape_ir_v2.py` defines semantic construction ops.
- `lathe/asset_graph.py` builds the asset graph.
- `lathe/assembly_kernel.py` builds assembly primitives.
- `lathe/scaffold_compiler.py` compiles shape candidates.
- `lathe/exact_solids.py` and `lathe/geometry_kernel.py` execute mesh/CSG paths.
- `lathe/geometry/` owns geometry-kernel contracts and providers.
- `lathe/mesh_program/` lowers source-level procedural mesh programs.
- `lathe/mesh_finalize.py` builds MeshIR and hard-edge metadata.

Quality, surface, and repair:

- `lathe/asset_quality/` contains diagnostics, preview evidence, semantic critique/patching, grammar lowering, and quality planning.
- `lathe/validators/` contains semantic, visual, surface, flow, and related validators.
- `lathe/surface_runtime.py`, `lathe/bake_runtime.py`, `lathe/materials.py`, and `lathe/surface_graph/` own surface and bake behavior.
- `lathe/repair_loop.py`, `lathe/repair_executor.py`, and `lathe/repair_policy.py` own repair execution.

Downstream:

- `lathe/topology_runtime.py` and `scripts/blender_topology_adapter.py` own topology adaptation.
- `lathe/uv_runtime.py` and `lathe/core/uv_ops.py` own UV behavior.
- `lathe/core/stages/` owns stage execution.
- `lathe/engine_manifests/` owns engine-facing manifests.

Docs and examples:

- `docs/asset-quality/lathe-implementation-northstar.md` is the current northstar.
- `docs/asset-quality/visible-geometry-sprint-0-evidence.md` is the expected Sprint 0 evidence log.
- `docs/examples_catalog.md` must stay in sync with checked-in examples.
- `examples/` contains runnable `.lth` sources.
- `std/` contains source stdlib assets, materials, kits, masks, terrain, vegetation, and policies.

Tests:

- `tests/contract/` covers stable contracts.
- `tests/unit/` covers focused module behavior.
- `tests/integration/` covers larger build paths.
- `tests/golden/`, `tests/property/`, and `tests/fuzz/` cover specialized lanes.

## Finishing A Change

Before finishing:

1. Run the narrowest relevant check first.
2. Run broader checks if behavior changed broadly.
3. Confirm examples/fixtures/docs reflect current behavior.
4. Record exact commands and results.
5. State exact evidence paths for visible-output claims.
6. Call out proxy, fallback, unsupported, blocked, or unverified parts.
7. Do not imply scaffold limitations are complete.

For review tasks, lead with findings and file/line references. For implementation tasks, summarize what changed, why, and what validation was actually performed.
