# Lathe Context, Problem Statement, Solution, Goals, and Success Criteria

Date: 2026-05-05  
Owner: Theyab / Icarus  
Repo: `/mnt/d/lathe_v0_1`  
Status: Strategic context document for the next Lathe geometry-quality push  
Related documents:

- `README.md`
- `AGENTS.md`
- `docs/architecture/shape_stage.md`
- `docs/architecture/shape-ir-v2.md`
- `docs/asset-quality/improvement-tasklist.md`
- `docs/asset-quality/phase1-phase2-visible-geometry-upgrade-guide.md`
- `docs/asset-quality/visible-geometry-sprint-0-implementation-plan.md`

---

## 1. Executive Summary

Lathe is a declarative 3D asset language, compiler, and runtime. Its purpose is to turn creative 3D intent into deterministic, inspectable, exportable asset packages.

The strategic problem is not that Lathe has no language. The language and surrounding authoring surface are already ambitious. The problem is that the language, quality system, and Project Wonder vision are now ahead of the geometry execution layer. Lathe can describe or imply artist-level construction, but the geometry kernel and lowering path cannot yet prove every meaningful promise as visible, usable mesh output.

The mission now is to bring the geometry kernel up to the expressive level of the language.

The next milestone should prove this loop:

```text
.lth / creative intent
-> internal construction plan
-> real visible geometry
-> preview/export evidence
-> quality diagnostics
-> semantic repair
-> regenerated improved artifact
```

The first narrow proof should be an industrial/sci-fi crate before-and-after: from valid-but-prototype output to visibly intentional hard-surface asset output with panels, bevels/chamfers, fasteners, vents, material zones, preview evidence, diagnostics, and at least one real repair loop.

The longer-term fix is a geometry capability parity program: every public language promise must either be buildable by the kernel, lowerable into supported operations, honestly rejected as unsupported, or kept out of the language until the kernel catches up.

---

## 2. What Lathe Is

Lathe is a code-native, declarative build language for AI-native 3D asset creation.

The repository currently presents Lathe as:

> a declarative programming language and compiler/runtime for turning 3D asset intent into certified production-ready asset packages.

Practically, Lathe includes:

- `.lth` source language for assets, families, components, materials, policies, fixtures, tests, benchmarks, kits, references, and related declarations;
- parser, normalizer, resolver, semantic checker, planner, materializer, and build executor;
- backend/provider registry;
- stable shape-stage handoff contract: `lathe.shape.intent_mesh_handoff_v1`;
- deterministic downstream stages for topology, UV, surface, validation, packaging, and reports;
- asset-quality modules for diagnostics, quality planning, art-direction IR, grammar lowering, material/wear graphs, preview evidence, semantic critique, and patching;
- optional learned-provider bridges such as Hunyuan3D and VGGT;
- optional/export/runtime lanes such as Blender, xatlas, GLB/USD/package flows, and Roblox-oriented handoff artifacts;
- Project Wonder scene/schema/proxy runtime work that uses Lathe as the asset/world execution substrate.

Lathe should not be thought of as only a DSL parser. It is intended to become the deterministic execution engine underneath AI-directed 3D creation.

---

## 3. How Lathe Fits Into Project Wonder

Project Wonder is the broader product vision: an AI imagination runtime where a frontier model acts like a creative director and Lathe acts as the code-native 3D execution language/runtime.

In that stack:

```text
Wonder
= creative director + scene memory + curiosity loop + render/vision feedback + orchestration

Lathe
= deterministic asset/world construction substrate + geometry/material/export evidence
```

Wonder should not replace Lathe's compiler/runtime responsibilities. Wonder should ask for worlds, scenes, assets, changes, inspections, and repairs. Lathe should execute those requests into actual geometry, materials, previews, reports, and packages.

This means Lathe must be honest. It cannot merely say that an object is a sci-fi crate, sword, machine, boat, car, building, or world prop. It must generate the geometry and evidence that prove the claim.

---

## 4. Current Lathe Architecture Context

### 4.1 Stable public shape contract

The stable public shape-stage backend contract is:

```text
lathe.shape.intent_mesh_handoff_v1
```

This is the public handoff downstream stages rely on. It must remain stable unless there is an explicit migration plan.

The shape-stage document describes the intended internal flow as:

```text
Intent
-> AssetGraph
-> Assembly blueprint
-> ShapeIR
-> fused/search geometry
-> authoritative mesh
-> optional provider proposals
-> conformance fit
-> shape_bundle under intent_mesh_handoff_v1
```

The public bundle and provider report are the compatibility surface. The implementation path behind them can evolve.

### 4.2 ShapeIR v1

`lathe/shape_ir.py` contains the current stable shape representation consumed by the runtime. It has grown beyond only boxes and cylinders and includes primitives such as:

- box;
- cylinder;
- sphere;
- revolved profile;
- extruded profile;
- torus;
- subdivision box;
- swept profile;
- heightfield;
- lofted solid;
- SDF mesh.

This is good progress. The issue is no longer simply “there are only boxes.” The deeper issue is that the system still needs consistent, evidence-backed lowering from semantic intent into real construction operations, mesh regions, surface semantics, validation, and repair targets.

### 4.3 ShapeIR v2

`lathe/asset_quality/shape_ir_v2.py` and `docs/architecture/shape-ir-v2.md` define an internal semantic operation model.

ShapeIR v2 represents construction decisions as operations, including:

- solids: `solid.box`, `solid.rounded_box`, `solid.cylinder`, `solid.sphere`, `solid.torus`, `solid.revolved_profile`, `solid.extruded_profile`, `solid.swept_profile`, `solid.subdivision_box`, `solid.panel`, etc.;
- booleans/construction: `op.union`, `op.subtract`, `op.intersect`, `op.inset`, `op.extrude`, `op.shell`, `op.cut_panel_line`;
- edge control: `op.bevel`, `op.chamfer`, `op.weighted_normals`, `op.mark_hard_edge`;
- SOP-style operations: `sop.boolean`, `sop.polybevel`, `sop.sweep`, `sop.polyextrude`, `sop.loft`, `sop.copy_to_points`, `sop.subdivide`, `sop.remesh`, `sop.carve`, `sop.polywire`;
- repetition/detail: `op.repeat`, `op.fastener_grid`, `op.vent_slats`, `op.trim_band`, `op.corner_guard_set`;
- integration: `op.socket`, `op.bracket`, `op.mount_plate`, `op.weld_seam`;
- wear/damage: `op.chip_edges`, `op.scratch_mask`, `op.dent_mask`, `op.grime_mask`.

ShapeIR v2 is the right direction because it represents how an artist or procedural modeler would construct an asset, not only what primitive volumes exist.

### 4.4 Geometry kernel layer

`lathe/geometry/kernel.py` defines the geometry kernel protocol, registry, and resolver. It includes in-tree kernel IDs:

```text
lathe.geometry.manifold_v1
lathe.geometry.reference_v1
```

The kernel protocol currently covers:

- primitive construction;
- boolean union;
- boolean difference;
- boolean intersection;
- convex hull;
- conversion to `trimesh`;
- watertightness probe;
- body count.

This is a strong seam, but the next phase needs to make the seam more central: semantic operations should lower into a `KernelProgram`, route through the selected `GeometryKernel`, preserve provenance, and report unsupported or fallback behavior truthfully.

### 4.5 Asset quality layer

The asset-quality roadmap already points toward the right capabilities:

- deterministic visual-quality diagnostics;
- family grammars;
- richer ShapeIR;
- high/low relation;
- material/wear graph;
- preview evidence;
- semantic critique and repair;
- vision critique loop;
- reference boards and quality planning.

The next step is to connect those pieces into a visible, testable, non-handwavy vertical slice.

---

## 5. Current Problem Statement

### 5.1 Core problem

Lathe's language and creative surface are ahead of the geometry kernel.

More precisely:

> Lathe can express, imply, plan, validate, or report artist-level asset intent that the current geometry execution path cannot always prove as visible mesh output.

This creates a trust gap.

The language may say or imply:

```text
reinforced sci-fi crate
industrial hard-surface paneling
beveled/chamfered edges
vents and slats
socketed handles
material zones
edge wear
production/game-ready package
```

But the output may still be too close to:

```text
primitive assembled volumes
weak/non-visible detail
flat or debug-like material output
metadata claiming richness without enough visual proof
quality reports that pass contract completeness but do not fully judge human-visible craft
```

The dangerous failure mode is not an outright error. The dangerous failure mode is a false positive: Lathe appears to certify or imply a rich asset while the mesh and preview evidence do not convincingly show that richness.

### 5.2 Root cause

The root cause is representation/execution mismatch.

Lathe increasingly knows what an asset is supposed to be, but the geometry runtime does not yet consistently know how to construct it at the level implied by the language and product vision.

The missing bridge is:

```text
semantic asset intent
-> explicit construction operations
-> kernel-supported mesh generation
-> semantic mesh provenance
-> surface/material masks
-> human-visible validation
-> concrete repair operations
```

If that bridge is incomplete, adding more language only increases the gap.

### 5.3 What this is not

This problem is not solved by only adding:

- more `.lth` keywords;
- more report fields;
- more quality scores;
- more candidate generation;
- prettier documentation;
- prompt-only creative intent;
- metadata that says “beveled” or “production-ready” without visible mesh evidence.

Those may help later, but they do not fix the core issue unless they connect to executable geometry.

---

## 6. The Solution

### 6.1 Solution thesis

The solution is geometry capability parity.

For every meaningful thing Lathe can publicly express or certify, one of these must be true:

```text
1. The geometry kernel can truly build it.
2. The compiler can lower it into supported construction operations.
3. The validator can honestly reject or degrade it as unsupported/incomplete.
4. The language does not promise it yet.
```

The state we must eliminate is:

```text
5. The language/report says it happened, but the mesh/preview/package does not prove it.
```

### 6.2 Phase 1: make the gap visible and produce one undeniable improvement

Phase 1 is the visible proof layer.

It should produce a narrow but undeniable before/after slice, ideally for `industrial_crate` first.

Target loop:

```text
existing crate intent
-> baseline build and preview
-> diagnostics identify prototype-level weaknesses
-> semantic repair maps weakness to concrete operations
-> regenerate crate
-> preview/report/export prove visible improvement
```

Phase 1 should improve:

- preview evidence;
- material/surface defaults;
- visible ShapeIR v2 lowering;
- diagnostics that catch human-visible quality failures;
- one semantic repair loop.

Phase 1 does not fully solve the language/kernel gap by itself. It proves the approach and creates a forcing function for honest output.

### 6.3 Phase 2: build the real kernel bridge

Phase 2 is the structural fix.

Recommended internal flow:

```text
ShapeIR / ShapeIR v2
-> KernelProgram
-> GeometryKernel
-> ShapeKernelResult
-> MeshIR / shape bundle
-> topology / uv / surface / validate / package
```

Key additions:

1. Add a `KernelProgram` layer.
2. Add `ShapeIR -> KernelProgram` lowering.
3. Route booleans and construction operations through `GeometryKernel`.
4. Preserve semantic provenance from op to face/edge/body/material zone.
5. Harden bevel/chamfer/post-boolean finishing.
6. Add conformance tests across reference/manifold/optional kernels.
7. Make fallback and unsupported behavior explicit in reports.

This is what turns Lathe from “expressive language with partial execution” into “language backed by executable geometry capability.”

### 6.4 Capability parity matrix

Lathe should maintain a living matrix like this:

| Language / intent promise | Required kernel/runtime support | Status standard |
| --- | --- | --- |
| Beveled hard-surface edges | `op.bevel` / `op.chamfer` lowering, bevel metadata, visible mesh/normal evidence | Real only when visible and report-backed |
| Panelized surfaces | inset/panel/trim operations, face provenance, material-zone assignment | Real only when panels appear in mesh/preview |
| Vents/slats | repeated geometry or cut operations with semantic IDs | Real only when visible and counted |
| Bolts/fasteners | repeat/copy-to-points/detail primitives with placement rules | Real only when visible and not random noise |
| Sockets/brackets/mounts | integration ops and attachment seating metadata | Real only when attachments are visibly seated |
| Material zones | face/part/material provenance and authored surface output | Real only when final preview differs from material-ID/debug output |
| Edge wear/grime/scratches | semantic masks and material/wear graph consumption | Partial until visible in final material evidence |
| Boolean cuts | selected geometry kernel, watertightness checks, fallback reporting | Real only when kernel confirms or reports fallback |
| Swept/revolved profiles | stable ShapeIR primitive or SOP lowering plus mesh export | Real when profile geometry appears and validates |
| Roblox/game-ready export | package output plus proxy checks and/or actual Roblox import evidence | Proxy until real import evidence exists |
| Organic characters/complex creatures | SDF/F-Rep/soft-surface path and validators | Unsupported or experimental unless proven |

This matrix is the anti-bullshit shield. It prevents the language from outrunning the engine again.

---

## 7. Goal

### 7.1 North-star goal

Lathe should become the deterministic, code-native craft engine for AI-created 3D.

The complete loop is:

```text
creative direction
-> Lathe source / structured intent
-> construction-aware internal IR
-> real geometry
-> material/surface detail
-> preview/render/export package
-> diagnostics/critique
-> semantic repair
-> improved regenerated asset
```

In product terms:

> Lathe should let an AI or human describe a 3D asset/world, then produce usable geometry, inspect the result, understand what is weak, repair it, and prove the improvement with evidence.

### 7.2 Immediate goal

The immediate goal is not to solve every asset family.

The immediate goal is:

> Make one existing hard-surface fixture visibly better while preserving public `.lth` compatibility and the stable `lathe.shape.intent_mesh_handoff_v1` contract.

Recommended first fixture:

```text
industrial_crate / sci-fi crate
```

Why this fixture:

- simple enough to execute quickly;
- rich enough to show meaningful hard-surface craft;
- ideal for panels, bevels, vents, corner guards, fasteners, decals, material zones, edge wear, and game-camera readability;
- easy for humans to judge before/after improvement.

Recommended guardrail fixture:

```text
mechanical_door or fantasy_weapon
```

The guardrail prevents overfitting the system to only one crate.

### 7.3 Strategic goal

After the first crate proof, the goal is to extend the same capability ladder:

```text
crate
-> weapon
-> door / tycoon machine / counter
-> vehicle / boat
-> building
-> composed world scene
```

Each fixture family should add one real kernel/runtime capability, not only one new visual trick.

---

## 8. Success Criteria

### 8.1 Minimum success criteria for Sprint 0

Sprint 0 succeeds when Lathe can show:

```text
.lth intent
-> generated crate
-> preview/report says what is visually weak
-> repair patch is applied
-> regenerated crate visibly improves
-> export/package artifacts exist
```

The before/after improvement should be obvious to a human in five seconds.

If the improvement requires a long explanation, it is not strong enough.

### 8.2 Concrete success criteria

For the first fixture family, success means:

1. **Visible asset improvement**
   - less primitive/blockout-looking;
   - clearer silhouette;
   - visible bevels/chamfers or rounded hard-surface edges;
   - visible panels, trim, vents, fasteners, or equivalent secondary detail;
   - coherent material zones;
   - no final preview that looks like only debug/material-ID colors.

2. **Generated evidence exists**
   - final preview or explicitly labeled proxy preview;
   - material-ID preview where useful;
   - wireframe or topology evidence where useful;
   - before/after comparison sheet for repaired output;
   - quality report;
   - package/export artifact;
   - trace of attempted vs actual backend/provider/kernel where relevant.

3. **Diagnostics catch real weaknesses**
   - primitive/blockout appearance;
   - missing bevel/chamfer/detail evidence;
   - debug-material look;
   - weak material separation;
   - weak primary/secondary/tertiary hierarchy;
   - unseated/stuck-on attachments;
   - fake or weak high/low distinction;
   - missing/unsupported renderer or kernel evidence is reported truthfully.

4. **Semantic repair is operational**
   - at least one diagnostic maps to a concrete patch/regeneration operation;
   - the operation changes geometry or material output, not only metadata;
   - regenerated output improves at least one metric;
   - regenerated output visibly improves in the preview;
   - unsafe repairs that require public syntax or contract changes are rejected.

5. **Public contract stays stable**
   - no breaking `.lth` syntax change in Sprint 0;
   - `lathe.shape.intent_mesh_handoff_v1` remains compatible;
   - new fields are additive and report/metadata-oriented unless explicitly planned.

6. **The approach generalizes**
   - the implementation is not hardcoded only to one screenshot;
   - at least one secondary fixture is checked or kept as a guardrail;
   - the new operation/diagnostic/repair path can be reused by another hard-surface family.

### 8.3 Geometry-kernel parity success criteria

The larger language/kernel problem is truly fixed only when:

```text
Lathe's public language never promises a visible asset capability that the geometry pipeline cannot build, lower, reject, or honestly mark as unsupported.
```

That means:

- every supported construction feature has a kernel/runtime implementation;
- every partially supported feature has explicit degraded/proxy status;
- every unsupported feature produces a diagnostic instead of disappearing silently;
- reports distinguish authored geometry from approximations;
- previews and packages prove the claim;
- repair suggestions map to allowed executable operations.

### 8.4 Evidence-based definition of done

A feature should not be considered done when a test only proves that metadata exists.

A feature is done when all of the following are true:

```text
intent exists
-> construction operation exists
-> lowering path preserves it
-> kernel/runtime executes it or reports unsupported
-> mesh/material/preview evidence shows the effect
-> validator can judge the effect
-> repair can target the effect when weak
```

---

## 9. Recommended Execution Plan

### 9.1 Sprint name

```text
visible-geometry-kernel-sprint-0
```

### 9.2 Sprint objective

Create the first proof that Lathe can take one existing asset family from valid-but-prototype to visibly intentional hard-surface output.

### 9.3 Sprint fixture

Primary:

```text
industrial_crate / sci-fi crate
```

Secondary guardrail:

```text
mechanical_door or fantasy_weapon
```

### 9.4 Sprint tasks

1. Capture baseline evidence.
2. Strengthen preview evidence.
3. Improve material/surface richness.
4. Lower one to three visible ShapeIR v2 operations into actual output.
5. Add visible-quality diagnostics that match human perception.
6. Wire one semantic repair mapping.
7. Start the Phase 2 kernel seam with `KernelProgram` design/implementation if needed.
8. Produce final before/after evidence.

### 9.5 Recommended verification matrix

Run targeted tests first:

```bash
python -m pytest -q tests/unit/test_asset_quality_preview_evidence.py tests/unit/test_asset_quality_diagnostics.py tests/unit/test_asset_quality_generation_steering.py
python -m pytest -q tests/unit/test_shape_ir_v2.py tests/unit/test_asset_quality_grammar_lowering.py tests/unit/test_geometry_kernel.py
python -m pytest -q tests/unit/test_surface_runtime.py tests/unit/test_asset_quality_material_wear_graph.py
```

Run fixture checks/builds:

```bash
python -m lathe.cli check examples/industrial_crate.lth
python -m lathe.cli build examples/industrial_crate.lth industrial_crate --out .tmp_tests/visible_geometry_sprint0 --deterministic
```

If the exact fixture path differs in the current tree, choose the closest industrial crate/hard-surface fixture and document the substitution.

Optional renderer/kernel dependencies should not be faked. If missing, report them as:

```text
renderer_unavailable
kernel_unavailable
proxy_preview_only
fallback_backend_used
```

---

## 10. Guardrails

1. Do not expand public `.lth` syntax until the internal kernel proves visible output.
2. Preserve `lathe.shape.intent_mesh_handoff_v1` unless an explicit migration plan exists.
3. Do not let validators reward metadata completeness over human-visible quality.
4. Do not claim production/game readiness from proxy evidence.
5. Do not fake Blender, Roblox, external renderer, bake, import, or learned-provider evidence.
6. Do not hide fallback paths; report attempted provider/kernel/backend and actual provider/kernel/backend.
7. Do not build a universal CAD kernel before the crate/door/weapon fixtures demonstrate visible value.
8. Keep Wonder as orchestrator and Lathe as execution substrate.
9. Make every new word, operation, report field, and test either create, modify, arrange, validate, or soon enable visible geometry.

---

## 11. Non-Goals For The Immediate Sprint

The immediate sprint should not attempt to:

- solve all 3D generation;
- redesign the entire `.lth` language;
- replace the stable shape handoff contract;
- make a universal CAD/B-rep/SDF engine;
- claim full Roblox readiness without actual import evidence;
- make organic creatures/characters production-ready;
- optimize every asset family;
- depend on live learned inference as the critical path;
- produce only docs/reports without visible asset improvement.

---

## 12. Why This Solves The Language-Ahead-Of-Kernel Problem

This solves the problem because it changes the standard of truth.

Old failure mode:

```text
Language expresses rich intent.
Compiler emits a valid package.
Report says the package is complete.
Human sees prototype-level geometry.
```

New required behavior:

```text
Language expresses rich intent.
Compiler lowers intent into construction operations.
Kernel executes supported operations.
Unsupported operations are reported honestly.
Mesh/surface evidence shows what was actually built.
Validator judges visible quality.
Repair maps critique to executable changes.
Regeneration proves improvement.
```

That is the difference between a language that is ahead of its engine and a language that is backed by its engine.

---

## 13. Strategic Bottom Line

Lathe does not win by adding more words faster than the geometry system can honor them.

Lathe wins by becoming the truthful execution layer for AI-native 3D creation:

```text
intent -> artifact -> judgment -> repair -> better artifact
```

The next real milestone is not “prettier docs” or “more DSL.”

The milestone is:

> A visible, evidence-backed proof that Lathe can construct, inspect, repair, and regenerate a better game asset while keeping its public contract stable.

That is the bridge from Lathe as a compiler scaffold to Lathe as the craft engine underneath Project Wonder.
