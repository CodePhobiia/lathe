# Visible Geometry Sprint 0 Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Make one Lathe fixture visibly more intentional by improving preview evidence, material/surface output, ShapeIR v2 visible lowering, diagnostics, and one semantic repair path while preserving `.lth` compatibility and `lathe.shape.intent_mesh_handoff_v1`.

**Architecture:** Keep public contracts stable. Build an internal/evidence-backed vertical slice around `industrial_crate` first, with `mechanical_door` or `fantasy_weapon` as a guardrail. All user-visible claims must be backed by generated artifacts or explicit proxy labels.

**Tech Stack:** Python 3.11+, pytest, Lathe CLI, existing `lathe/asset_quality/*`, `lathe/geometry/*`, `lathe/materials.py`, `lathe/surface_runtime.py`, `lathe/bake_runtime.py`, deterministic local build artifacts.

---

## Guardrails

- Do not change public `.lth` syntax in this sprint.
- Do not change `lathe.shape.intent_mesh_handoff_v1` fields except additive internal/report metadata that does not break consumers.
- Do not fake Blender, Roblox, bake, or external-viewer evidence.
- Prefer deterministic fixture tests over broad suite runs until the slice is stable.
- Keep every behavior change covered by targeted tests.

---

### Task 1: Capture baseline evidence

**Objective:** Create a truthful before-state for the selected fixtures.

**Files:**
- Create/Modify: `docs/asset-quality/visible-geometry-sprint-0-evidence.md`
- Read: `examples/industrial_crate.lth`, `examples/mechanical_door.lth` if present; otherwise use closest `examples/asset_quality/*` fixtures.

**Step 1: Record git state**

Run:
```bash
git status --short
```
Expected: Record existing dirty/untracked state in the evidence note; do not clean unrelated work.

**Step 2: Run baseline checks**

Run:
```bash
python -m lathe.cli check examples/industrial_crate.lth
python -m lathe.cli check examples/mechanical_door.lth
```
If either example path is missing, find the closest fixture under `examples/asset_quality/` and document the substitution.

**Step 3: Run baseline builds**

Run:
```bash
python -m lathe.cli build examples/industrial_crate.lth industrial_crate --out .tmp_tests/baseline_industrial_crate --deterministic
python -m lathe.cli build examples/mechanical_door.lth mechanical_door --out .tmp_tests/baseline_mechanical_door --deterministic
```

**Step 4: Document evidence**

In `docs/asset-quality/visible-geometry-sprint-0-evidence.md`, record:
- commands run;
- output directories;
- report paths;
- preview paths;
- missing optional renderer/backend blockers;
- current visible gaps.

**Step 5: Verify**

Run:
```bash
python -m pytest -q tests/unit/test_asset_quality_baseline_report_shape.py tests/unit/test_asset_quality_preview_evidence.py
```

---

### Task 2: Strengthen preview evidence contract

**Objective:** Ensure builds expose human-inspectable visual evidence: final beauty, material-ID, wireframe, orthographic/comparison sheet.

**Files:**
- Modify: `lathe/asset_quality/preview_render.py`
- Modify: `lathe/asset_quality/preview_evidence.py`
- Modify/Test: `tests/unit/test_asset_quality_preview_evidence.py`
- Possibly Modify: `lathe/asset_quality/certification.py`, `lathe/core/stages/validate.py`

**Step 1: Write failing tests**

Add/extend tests asserting the preview evidence payload can represent:
- `final_beauty`;
- `material_ids`;
- `wireframe`;
- `comparison_sheet`;
- `renderer_status` with truthful unavailable/degraded states.

Run:
```bash
python -m pytest -q tests/unit/test_asset_quality_preview_evidence.py
```
Expected: FAIL until fields/render placeholders are implemented or wired.

**Step 2: Implement minimal additive preview evidence**

Add fields without removing existing keys. Missing renderer paths should produce explicit statuses like `renderer_unavailable` or `proxy_preview_only`.

**Step 3: Verify**

Run:
```bash
python -m pytest -q tests/unit/test_asset_quality_preview_evidence.py tests/unit/test_asset_quality_certification.py
```

---

### Task 3: Improve material/surface richness for the crate fixture

**Objective:** Kill the debug-material look with deterministic family-aware defaults.

**Files:**
- Modify: `lathe/materials.py`
- Modify: `lathe/surface_runtime.py`
- Modify: `lathe/bake_runtime.py`
- Test: `tests/unit/test_surface_runtime.py`
- Test: `tests/unit/test_asset_quality_material_wear_graph.py`

**Step 1: Write failing tests**

Add tests showing an industrial/sci-fi crate surface bundle includes:
- non-debug palette names or color ranges;
- material zones with contrast;
- roughness/normal/AO or explicitly labeled proxy evidence;
- edge wear or grime mask policy;
- decal/emissive/label hooks if supported.

Run:
```bash
python -m pytest -q tests/unit/test_surface_runtime.py tests/unit/test_asset_quality_material_wear_graph.py
```
Expected: FAIL on missing richness/evidence fields.

**Step 2: Implement deterministic defaults**

Prefer additive family/style defaults over public syntax changes. Surface output should record what was authored vs proxy.

**Step 3: Verify**

Run:
```bash
python -m pytest -q tests/unit/test_surface_runtime.py tests/unit/test_asset_quality_material_wear_graph.py
```

---

### Task 4: Make one ShapeIR v2 detail operation visibly lower

**Objective:** Turn at least one semantic op into actual visible geometry or material detail.

**Files:**
- Modify: `lathe/asset_quality/shape_ir_v2.py` only if validation/metadata needs extension.
- Modify: `lathe/asset_quality/grammar_lowering.py`
- Modify: `lathe/geometry_kernel.py` or `lathe/exact_solids.py` if geometry generation is needed.
- Test: `tests/unit/test_shape_ir_v2.py`
- Test: `tests/unit/test_asset_quality_grammar_lowering.py`

**Step 1: Pick the first op**

Recommended first visible op: `op.trim_band` or `op.fastener_grid`. Use `op.bevel`/`op.chamfer` if the existing geometry path can support it safely.

**Step 2: Write failing tests**

Tests should prove:
- the op survives lowering metadata;
- it produces a visible primitive/detail, material mask, or reportable semantic region;
- unsupported parts emit diagnostics instead of being silently dropped.

Run:
```bash
python -m pytest -q tests/unit/test_shape_ir_v2.py tests/unit/test_asset_quality_grammar_lowering.py
```

**Step 3: Implement minimal visible lowering**

Keep the stable v1 shape contract. Add internal metadata or v1-compatible approximations as needed, tagged clearly as approximations.

**Step 4: Verify**

Run:
```bash
python -m pytest -q tests/unit/test_shape_ir_v2.py tests/unit/test_asset_quality_grammar_lowering.py tests/unit/test_geometry_kernel.py
```

---

### Task 5: Add visible-quality diagnostics that match human perception

**Objective:** Ensure reports flag ugly output, not just missing metadata.

**Files:**
- Modify: `lathe/asset_quality/diagnostics.py`
- Modify: `lathe/validators/visual_quality.py`
- Modify: `lathe/core/stages/validate.py`
- Test: `tests/unit/test_asset_quality_diagnostics.py`
- Test: `tests/test_visual_quality.py`

**Step 1: Write failing tests**

Target metrics:
- debug material preview penalty;
- primary/secondary/tertiary balance;
- attachment seating quality;
- bevel/chamfer/detail evidence presence;
- Roblox proxy gates: triangle count budget, watertightness, no zero-thickness/backface holes when evidence exists.

Run:
```bash
python -m pytest -q tests/unit/test_asset_quality_diagnostics.py tests/test_visual_quality.py
```

**Step 2: Implement/add metrics**

Keep report fields additive and degrade missing optional evidence to warnings.

**Step 3: Verify**

Run:
```bash
python -m pytest -q tests/unit/test_asset_quality_diagnostics.py tests/unit/test_asset_quality_baseline_report_shape.py tests/test_visual_quality.py
```

---

### Task 6: Wire one semantic repair mapping

**Objective:** Convert one diagnostic into a concrete allowed patch/regeneration operation.

**Files:**
- Modify: `lathe/asset_quality/semantic_critique.py`
- Modify: `lathe/asset_quality/semantic_patch.py`
- Modify: `lathe/repair_loop.py` if needed.
- Test: `tests/unit/test_asset_quality_semantic_critique.py`
- Test: `tests/unit/test_asset_quality_semantic_patch.py`
- Test: `tests/unit/test_asset_quality_generation_steering.py`

**Step 1: Choose first repair mapping**

Recommended mapping:
```text
primary_secondary_tertiary_balance low
-> add trim band / fastener grid / vent slats
-> regenerate fixture
-> report improved detail hierarchy metric
```

**Step 2: Write failing tests**

Prove the suggestion maps to an allowlisted patch and rejects unsafe public contract/syntax edits.

**Step 3: Implement mapping**

Keep the patch operation deterministic and serializable.

**Step 4: Verify**

Run:
```bash
python -m pytest -q tests/unit/test_asset_quality_semantic_critique.py tests/unit/test_asset_quality_semantic_patch.py tests/unit/test_asset_quality_generation_steering.py
```

---

### Task 7: Start the Phase 2 kernel seam without switching behavior globally

**Objective:** Add the private kernel-program seam behind the current shape contract.

**Files:**
- Create: `lathe/geometry/kernel_program.py`
- Create: `lathe/geometry/shape_ir_lowering.py`
- Modify: `lathe/geometry/kernel.py` only for additive capability metadata if needed.
- Test: `tests/unit/test_geometry_kernel.py`
- Test: `tests/unit/test_shape_ir_v2.py`

**Step 1: Write failing tests**

Tests should prove:
- `KernelProgram` serializes deterministically;
- shape primitives receive stable IDs;
- unsupported ops produce diagnostics;
- no public shape handoff fields change.

**Step 2: Implement internal-only dataclasses/lowering**

Do not route production builds through this globally yet. This is a seam introduction.

**Step 3: Verify**

Run:
```bash
python -m pytest -q tests/unit/test_geometry_kernel.py tests/unit/test_shape_ir_v2.py tests/contract/test_shape_handoff_v1.py
```

---

### Task 8: Produce final sprint evidence

**Objective:** Prove the sprint created a visible, truthful upgrade.

**Files:**
- Modify: `docs/asset-quality/visible-geometry-sprint-0-evidence.md`
- Possibly Modify: `docs/asset-quality/quality-upgrade-evidence.md`

**Step 1: Run targeted suite**

```bash
python -m pytest -q tests/unit/test_asset_quality_preview_evidence.py tests/unit/test_asset_quality_diagnostics.py tests/unit/test_asset_quality_generation_steering.py
python -m pytest -q tests/unit/test_shape_ir_v2.py tests/unit/test_asset_quality_grammar_lowering.py tests/unit/test_geometry_kernel.py
python -m pytest -q tests/unit/test_surface_runtime.py tests/unit/test_asset_quality_material_wear_graph.py
```

**Step 2: Run build/check**

```bash
python -m lathe.cli check examples/industrial_crate.lth
python -m lathe.cli build examples/industrial_crate.lth industrial_crate --out .tmp_tests/visible_geometry_sprint0 --deterministic
```

**Step 3: Document final evidence**

Record:
- before/after preview paths;
- report paths;
- metrics that changed;
- optional dependency blockers;
- exact claims allowed and disallowed.

**Step 4: Optional full suite**

```bash
python -m pytest -q
```

Run full suite only after targeted tests are green or if the code change is broad enough to require it.
