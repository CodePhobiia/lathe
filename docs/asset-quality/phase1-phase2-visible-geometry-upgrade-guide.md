# Lathe Phase 1/2 Visible Geometry Upgrade Guide

Date: 2026-05-05  
Owner: Icarus / Theyab  
Linked wiki page: `/home/talme/wiki/queries/lathe-phase1-phase2-visible-geometry-upgrade-guide.md`  
Raw research source: `/home/talme/wiki/raw/transcripts/lathe-phase1-phase2-research-swarm-2026-05-05.md`
Implementation plan: `docs/asset-quality/visible-geometry-sprint-0-implementation-plan.md`

## Goal

Turn Lathe's next upgrade into a visible, evidence-backed leap:

```text
.lth intent
-> real non-boxy geometry
-> GLB/USD/package output
-> render/preview evidence
-> quality report
-> semantic repair suggestion
-> visibly improved regenerated asset
```

This guide links Phase 1 (**make it visibly better**) and Phase 2 (**build the real geometry kernel**) directly to the current Lathe repository without breaking the public `.lth` language or the stable `lathe.shape.intent_mesh_handoff_v1` contract.

## Non-negotiable ground rules

1. Preserve public Lathe source compatibility unless a task explicitly declares a language migration.
2. Preserve `lathe.shape.intent_mesh_handoff_v1` as the stable public shape handoff.
3. Do not claim production/game readiness from proxy evidence.
4. Prefer small, reviewable slices over a universal geometry rewrite.
5. Every new word, op, validator, and report field must create, modify, arrange, validate, or soon enable visible geometry.
6. Keep at least three demo fixtures alive to avoid single-hero overfitting.

## Source evidence inspected

### Repo/docs

- `AGENTS.md` — repo rules: preserve source compatibility and stable shape contract.
- `docs/asset-quality/improvement-tasklist.md` — existing asset-quality upgrade tasklist.
- `docs/architecture/shape_stage.md` — public vs internal shape boundary.
- `docs/architecture/shape-ir-v2.md` — internal semantic op model.
- `lathe/asset_quality/*.py` — diagnostics, quality planning, grammar lowering, material/wear graph, semantic/vision critique, preview evidence.
- `lathe/geometry/kernel.py`, `lathe/geometry/reference_kernel.py`, `lathe/geometry/manifold_kernel.py` — geometry kernel registry/seams.
- `lathe/geometry_kernel.py`, `lathe/exact_solids.py`, `lathe/shape_ir.py`, `lathe/mesh_ir.py`, `lathe/materials.py`, `lathe/surface_runtime.py`, `lathe/bake_runtime.py` — runtime geometry/surface/material path.
- `tests/unit/test_asset_quality*.py`, `tests/unit/test_shape_ir_v2.py`, `tests/unit/test_geometry_kernel.py` — relevant coverage seams.

### External references translated into Lathe requirements

- Roblox supports `.fbx`, `.obj`, `.gltf`, PBR textures, rigging/skinning/animation through Studio Importer; individual mesh specs include <= 20,000 triangles, watertight geometry, no visible backfaces/holes, no zero-thickness surfaces, and quads where possible.
- Manifold/manifold3d is a strong optional backend candidate because its purpose is robust manifold triangle-mesh operations and boolean reliability.
- Trimesh is useful for mesh IO/analysis/export and can route booleans through Manifold or Blender, but Lathe should not hide fallback quality loss.
- CadQuery/OCCT is a powerful optional B-rep/CAD lane for fillets, lofts, sweeps, STEP/BREP, but it should not become the first core dependency unless a narrow use case justifies it.
- Hard-surface game art workflows repeatedly emphasize chamfers/bevels, face/weighted normals, trim sheets, decals, high-to-low baking, material/wear masks, modular kits, and consistent design language.

---

# Phase 1 — Make it visibly better

## Phase 1 thesis

Phase 1 is not “add more syntax.” Phase 1 is **make the current compiler produce evidence that looks and feels better to a human**.

The fastest path is a narrow demo ladder across three fixture families:

1. `industrial_crate` / sci-fi crate — panels, bevels, vents, fasteners, decals, material zones.
2. `fantasy_weapon` / sword — swept/revolved profiles, blade/guard/handle proportion, metal/leather/wood material story.
3. `mechanical_door` or shop/tycoon machine/counter — assembly, repeated components, brackets/sockets, game-camera readability.

## Phase 1 target outcome

Phase 1 is done when:

- 3 fixtures build deterministically.
- Each fixture has final preview evidence, material-ID preview, wireframe preview, and a comparison sheet.
- Each fixture exports package artifacts in the existing Lathe flow.
- Each fixture has a `quality_diagnostics` or equivalent report section that flags human-visible weaknesses.
- At least one fixture has a semantic repair loop where a report suggestion maps to a concrete regeneration/patch operation and visibly improves output.

## Phase 1 build order

### 0. Freeze the baseline

Run from repo root:

```bash
git status --short
python -m lathe.cli check examples/industrial_crate.lth
python -m lathe.cli check examples/mechanical_door.lth
python -m lathe.cli build examples/industrial_crate.lth industrial_crate --out .tmp_tests/baseline_industrial_crate --deterministic
python -m lathe.cli build examples/mechanical_door.lth mechanical_door --out .tmp_tests/baseline_mechanical_door --deterministic
```

Record outputs in a short evidence note before changing behavior. If the examples differ in the current tree, use the closest existing examples under `examples/asset_quality/` and record the exact paths.

### 1. Make previews undeniable

**Why first:** visible before/after evidence creates the feedback loop for everything else.

Primary files:

- `lathe/asset_quality/preview_render.py`
- `lathe/asset_quality/preview_evidence.py`
- `lathe/asset_quality/certification.py`
- `lathe/core/stages/validate.py`

Add/strengthen deterministic preview outputs:

- final beauty preview;
- material-ID preview;
- wireframe preview;
- orthographic front/top/three-quarter sheets;
- before/after comparison sheet when a repair patch exists;
- metadata naming which preview is proxy vs real renderer output.

Acceptance criteria:

- A human can open one folder and immediately see whether the asset improved.
- Reports link or reference preview artifacts.
- Missing renderers degrade truthfully: `renderer_unavailable`, not fake success.

Suggested tests:

```bash
python -m pytest -q tests/unit/test_asset_quality_preview_evidence.py tests/unit/test_asset_quality_certification.py
```

### 2. Upgrade material/surface defaults

**Why second:** weak flat/debug-looking materials can make good geometry look like a prototype.

Primary files:

- `lathe/materials.py`
- `lathe/surface_runtime.py`
- `lathe/bake_runtime.py`
- `lathe/asset_quality/material_wear_graph.py`

Implement the 20% that makes screenshots feel 5x richer:

- non-debug palettes per asset family;
- material zones with readable contrast;
- roughness/metalness/normal variation;
- edge wear masks;
- concave grime/contact dirt masks;
- decals/labels/emissive strips for sci-fi/Roblox-readable assets;
- style tokens like industrial, fantasy, toy/plastic/Roblox.

Acceptance criteria:

- Material changes appear in preview evidence, not only metadata.
- Material IDs are separate from final beauty materials.
- Surface reports state what is authored vs placeholder.

Suggested tests:

```bash
python -m pytest -q tests/unit/test_surface_runtime.py tests/unit/test_asset_quality_material_wear_graph.py
```

### 3. Lower ShapeIR v2 ops into visible details

**Why third:** Lathe already has internal semantic ops; Phase 1 should make the highest-signal ops visible before expanding syntax.

Primary files:

- `lathe/asset_quality/shape_ir_v2.py`
- `lathe/asset_quality/grammar_lowering.py`
- `lathe/geometry_kernel.py`
- `lathe/exact_solids.py`
- `lathe/mesh_finalize.py`

Prioritized visible ops:

- `op.bevel` / `op.chamfer` — catch highlights and kill boxy edges.
- `op.fastener_grid` — bolts/screws/rivets for scale and craft.
- `op.vent_slats` — high-impact detail for crates/machines/doors.
- `op.trim_band` — readable hard-surface panel hierarchy.
- `op.socket`, `op.bracket`, `op.mount_plate` — fix stuck-on attachments.
- `op.grime_mask`, `op.scratch_mask`, `op.chip_edges` — feed material/wear graph.

Acceptance criteria:

- v2 diagnostics do not silently drop unsupported visible intent.
- At least three ops produce visible geometry or material changes in previews.
- The public v1 shape bundle contract remains stable.

Suggested tests:

```bash
python -m pytest -q tests/unit/test_shape_ir_v2.py tests/unit/test_asset_quality_grammar_lowering.py tests/unit/test_geometry_kernel.py
```

### 4. Make validators judge what humans see

**Why fourth:** old certification can pass while outputs still feel prototype-level.

Primary files:

- `lathe/asset_quality/diagnostics.py`
- `lathe/validators/visual_quality.py`
- `lathe/asset_quality/highlow_relation.py`
- `lathe/core/stages/validate.py`

Metrics to enforce/raise:

- random triangulation/faceting penalty;
- debug material preview penalty;
- fake high/low detail penalty;
- attachment seating quality;
- primary/secondary/tertiary balance;
- bevel/chamfer presence;
- material-zone contrast;
- preview evidence completeness;
- Roblox readiness proxies: triangle budget, watertightness, zero-thickness, backface/hole warnings.

Acceptance criteria:

- Validators can fail/warn on ugly output even when metadata is complete.
- Each warning includes one concrete repair route.
- Reports distinguish proxy evidence from real render/bake/import evidence.

Suggested tests:

```bash
python -m pytest -q tests/unit/test_asset_quality_diagnostics.py tests/unit/test_asset_quality_baseline_report_shape.py tests/test_visual_quality.py
```

### 5. Demo semantic repair

**Why fifth:** this is the seed of Project Wonder’s revision loop.

Primary files:

- `lathe/asset_quality/semantic_critique.py`
- `lathe/asset_quality/semantic_patch.py`
- `lathe/asset_quality/vision_critique.py`
- `lathe/repair_loop.py`

Required mapping:

```text
quality issue
-> semantic repair suggestion
-> concrete allowed patch/regeneration operation
-> rebuilt artifact
-> before/after preview
-> improved report metric
```

First repair examples:

- `debug_material_preview_penalty` -> reauthor surface layer / apply non-debug palette.
- `attachment_seating_quality` low -> add socket/bracket/mount plate op.
- `primary_secondary_tertiary_balance` weak -> add trim bands/vent slats/fastener grid.
- `highlow_fake_detail_penalty` high -> add bevel/detail source and bake-map evidence, or truthfully keep blocker.

Acceptance criteria:

- At least one end-to-end deterministic repair improves a metric and a screenshot.
- Unsafe patches that touch public `.lth` syntax or `lathe.shape.intent_mesh_handoff_v1` are rejected.

---

# Phase 2 — Build the real geometry kernel

## Phase 2 thesis

Phase 2 is the private kernel upgrade beneath the stable public Lathe contract. The shape handoff stays stable; the internal path becomes serious.

Recommended internal seam:

```text
ShapeIR / ShapeIR v2
-> KernelProgram
-> GeometryKernel
-> ShapeKernelResult
-> MeshIR / shape bundle
-> topology / uv / surface / validate / package
```

## Recommended backend strategy

### Keep

- Existing reference kernel as deterministic fallback.
- Existing public `lathe.shape.intent_mesh_handoff_v1` bundle.
- Trimesh for IO/analysis/export where it already fits.
- Blender as validation/render/bake bridge, not hidden product core.

### Add / strengthen

- `manifold3d` optional backend for robust manifold booleans and watertight solid operations.
- Kernel capability negotiation: every backend reports primitive/operation support.
- Strict fallback reports: attempted kernel, actual kernel, unsupported operation, fallback reason.

### Research lane, not first core

- CadQuery/OCCT for B-rep/fillet/loft/STEP workflows when a narrow slice needs true CAD-style operations.
- Full SDF/F-Rep organic modeling, terrain, vegetation, WFC/CGA after the hard-surface kernel is demonstrably useful.

## Phase 2 first architecture tasks

### 1. Introduce `KernelProgram`

Suggested new file:

- `lathe/geometry/kernel_program.py`

Purpose:

- normalize current `ShapeIR`/ShapeIR v2 into typed geometry operations;
- replace stringly implicit `blend_mode` behavior with explicit op nodes;
- assign stable IDs for primitive, part, component, operation, seam group, material zone;
- validate unsupported primitive/op combinations before meshing.

Minimum concepts:

```python
KernelProgram
KernelNode
KernelPrimitive
KernelOperation
KernelSemanticMap
KernelDiagnostic
```

Acceptance criteria:

- Program serializes deterministically.
- Missing fields produce clear diagnostics.
- Public `.lth` source does not change.

### 2. Add `ShapeIR -> KernelProgram` lowering

Suggested new file:

- `lathe/geometry/shape_ir_lowering.py`

Inputs:

- `lathe/shape_ir.py` current records;
- `lathe/asset_quality/shape_ir_v2.py` semantic ops where available.

Outputs:

- validated `KernelProgram`;
- diagnostics for unsupported ops;
- fallback-safe approximations only when explicitly tagged.

Acceptance criteria:

- Bevel/chamfer, fastener grid, trim band, vent slats, socket/bracket/mount plate have first-class semantic IDs.
- Unsupported ops do not disappear silently.

### 3. Route booleans through `GeometryKernel`

Primary files:

- `lathe/geometry/kernel.py`
- `lathe/geometry/reference_kernel.py`
- `lathe/geometry/manifold_kernel.py`
- `lathe/adapters/manifold_kernel.py`
- `lathe/exact_solids.py`
- `lathe/geometry_kernel.py`

Acceptance criteria:

- Boolean union/difference/intersection calls go through kernel resolution.
- Reports include `attempted_kernel`, `actual_kernel`, `fallback_reason`, and `check_volume`/watertightness status where relevant.
- Non-strict mode warns; strict geometry mode fails on invalid solids.

Suggested tests:

```bash
python -m pytest -q tests/unit/test_geometry_kernel.py tests/unit/test_geometry_kernel_selection.py tests/property/test_geometry_kernel_properties.py
```

### 4. Promote semantic provenance to first-class result

Suggested outputs:

```text
face -> part/primitive/op/material zone
edge -> seam/hard-edge/bevel class
body -> component/asset-class role
op -> generated mesh region IDs
```

Primary files:

- `lathe/mesh_ir.py`
- `lathe/mesh_finalize.py`
- `lathe/geometry_kernel.py`
- `lathe/exact_solids.py`

Why this matters:

- topology/UV/surface stages need to know where panels, seams, edges, sockets, and wear masks are;
- validators need to judge human-visible construction logic;
- repair patches need stable targets.

### 5. Harden post-boolean bevel/chamfer

Phase 2 must not just boolean objects together. It must create hard-surface edges that catch light.

Acceptance criteria:

- bevels/chamfers are kernel-level or post-kernel operations with watertightness checks;
- open strip/cap problems produce diagnostics;
- hard edges and bevel strips survive into MeshIR metadata;
- UV/surface stages can consume bevel/edge semantics.

### 6. Conformance tests across kernels

Add parametric tests for available kernels:

- reference;
- manifold if installed;
- optional Blender/trimesh path when available.

Test cases:

- box/cylinder/sphere baseline;
- extruded profile;
- revolved profile;
- swept profile;
- lofted solid;
- union/difference/intersection;
- coplanar/tangent cutter edge cases;
- bevel after boolean;
- face/edge semantic provenance.

---

# The first upgrade sprint

## Sprint name

`visible-geometry-kernel-sprint-0`

## Sprint objective

Create the first proof that Lathe can take one existing asset family from valid-but-prototype toward visibly intentional hard-surface output.

## Sprint fixture

Primary: industrial/sci-fi crate.  
Secondary guardrail: mechanical door or fantasy weapon.

## Sprint tasks

1. Run and document baseline builds/checks.
2. Add/verify preview evidence paths for final beauty, material IDs, wireframe, comparison sheet.
3. Improve default material/surface output for the fixture.
4. Lower one to three ShapeIR v2 visible ops into actual output: bevel/chamfer, trim band, fastener grid.
5. Add diagnostics that catch the before-state and improve on the after-state.
6. Add one semantic repair mapping from a diagnostic to a concrete patch/regeneration op.
7. Write a short evidence note with before/after previews, report metrics, and exact claims.

## Recommended branch name

```bash
git checkout -b feat/visible-geometry-kernel-sprint-0
```

## Minimal verification matrix

```bash
python -m pytest -q tests/unit/test_asset_quality_preview_evidence.py tests/unit/test_asset_quality_diagnostics.py tests/unit/test_asset_quality_generation_steering.py
python -m pytest -q tests/unit/test_shape_ir_v2.py tests/unit/test_asset_quality_grammar_lowering.py tests/unit/test_geometry_kernel.py
python -m pytest -q tests/unit/test_surface_runtime.py tests/unit/test_asset_quality_material_wear_graph.py
python -m lathe.cli check examples/industrial_crate.lth
python -m lathe.cli build examples/industrial_crate.lth industrial_crate --out .tmp_tests/visible_geometry_sprint0 --deterministic
```

If optional renderers or manifold backends are missing, report them as dependency blockers, not feature failures.

---

# What not to build yet

- Do not add public `.lth` syntax before the internal kernel proves visible output.
- Do not build a universal CAD kernel before the crate/door/weapon fixtures look better.
- Do not claim Roblox-ready proof without actual Roblox import evidence or a clearly labeled proxy gate.
- Do not hide SDF/trimesh/blender/manifold fallback differences.
- Do not make validators reward metadata completeness over human-visible quality.
- Do not let Project Wonder absorb compiler/runtime responsibilities; keep Wonder as orchestrator and Lathe as execution substrate.

## Strategic bottom line

Lathe wins by becoming the truthful, deterministic, code-native craft engine for AI-created 3D. Phase 1 makes people believe it with screenshots and reports. Phase 2 makes the belief compound by giving the language a real geometry kernel under the hood.
