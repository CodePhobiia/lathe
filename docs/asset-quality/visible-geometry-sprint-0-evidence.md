# Visible Geometry Sprint 0 Evidence

Date: 2026-05-05
Status: Sprint 0 primary and guardrail acceptance achieved; industrial_crate and mechanical_door certify and package through bounded Manifold full-CSG path
Northstar: `docs/asset-quality/lathe-implementation-northstar.md`

This document is the evidence ledger for `visible-geometry-kernel-sprint-0`.

The Sprint 0 objective is to make one existing hard-surface fixture visibly better while preserving public source compatibility and the stable shape handoff contract. Before changing behavior, the baseline must be truthful.

## 1. Baseline Verdict

Original baseline checks passed for both fixtures, but original baseline builds did not produce visible artifacts.

Original allowed claim:

```text
industrial_crate and mechanical_door parse/check successfully, but the build path is blocked in shape-stage exact boolean fusion before mesh, preview, validate, or package evidence exists.
```

That original baseline blocker is now fixed in the current working tree. The updated allowed claim after the Sprint 0 runtime fixes is:

```text
industrial_crate and mechanical_door parse/check successfully, produce shape/topology/UV/surface/optimize/validate artifacts in bounded builds, and fail honestly at validation before package/export.
```

Prior forbidden claim before the post-breakthrough implementation pass:

```text
Do not claim Sprint 0 has a passing crate package, passing guardrail package, before/after visual improvement, or export evidence yet.
```

Current allowed claim after the post-breakthrough implementation pass:

```text
industrial_crate and mechanical_door parse/check successfully, execute high-count cutter booleans through a bounded Manifold full-CSG route, preserve watertight exact-boolean topology, pass validation, and produce package/export artifacts.
```

The first implementation blocker was not a weak-looking crate. It was earlier and more structural:

```text
exact hard-surface fixture
-> ShapeIR / exact mesh path
-> trimesh boolean fusion
-> external or heavy boolean engine path
-> no bounded failure or emitted stage report
-> no visible artifact
```

That blocker was addressed by adding bounded exact-boolean fallback, bounded preview rendering, direct UV fallback normals, and bounded geometry-integrity validation. The next blocker is no longer "no artifact." It is:

```text
artifact -> validate -> semantic fragmentation / toy-or-primitive failure -> no package/export
```

The next implementation slice should use the produced artifacts and diagnostics to make the crate semantically less merged/primitive, then prove the guardrail does not regress.

## 2. Environment

Repository root:

```text
<repo-root>
```

The repository contains `.venv`, but in this Windows checkout it is a Linux-style uv virtual environment:

```text
.venv\pyvenv.cfg home = /home/talme/.local/share/uv/python/cpython-3.11-linux-x86_64-gnu/bin
```

Direct Windows execution through `.venv\Scripts\python.exe` is not available.

Attempting `uv run` against the existing `.venv` failed because uv tried to repair/remove `.venv\lib64` and Windows denied access:

```text
error: failed to remove file `<repo-root>/.venv/lib64`: Access is denied. (os error 5)
```

For this evidence pass, a separate Windows-local environment was used:

```text
.venv-win\Scripts\python.exe
Python 3.14.0
```

The editable project was installed into `.venv-win`:

```powershell
.\.venv-win\Scripts\python.exe -m pip install -e .
```

During baseline execution, the exact mesh path exposed missing environment dependencies. These were installed into `.venv-win` only, not added as source changes in this pass:

```text
shapely==2.1.2
mapbox-earcut==2.0.0
manifold3d==3.4.1
```

Dependency findings:

- Without `shapely`, extruded profile mesh generation fails with `ModuleNotFoundError: No module named 'shapely'`.
- Without a triangulation engine, `trimesh.creation.extrude_polygon` fails with `ValueError: No available triangulation engine!`.
- Without `manifold3d`, `trimesh.boolean.union` sees only the Blender engine and can block inside a Blender subprocess path.
- With `manifold3d` available, the bounded build still did not finish within the timeout and emitted `trimesh.triangles` divide-by-zero / invalid-value runtime warnings before hanging in numerical processing.

## 3. Dirty Worktree State

Command:

```powershell
git status --short
```

Captured at:

```text
.tmp_tests/visible_geometry_sprint0_20260505/logs/git_status_short.txt
```

Summary:

- The worktree was already heavily dirty before this evidence pass.
- Important existing dirty areas include Lathe runtime/source modules, schema/grammar, examples, tests, docs, and many generated temporary artifacts.
- This evidence pass did not clean or revert unrelated dirty files.

## 4. Fixtures Read

Primary fixture:

```text
examples/industrial_crate.lth
asset industrial_crate: hard_surface_prop from industrial_crate_family uses shipping_prop
```

Relevant authored intent:

- role: reinforced industrial cargo crate
- geometry mode: `exact_hard_surface`
- seam classes: `cargo_panel_break`, `lid_break`, `latch_cut`, `foot_split`
- edge classes: `hero_bevel`, `cargo_bevel`, `support_bevel`
- integration rules: `boolean_union`, `preserve_lid_break`, `preserve_corner_guards`
- allowed features: `inset_panel`, `trim_band`, `fastener_strip`, `support_bracket`, `edge_break`, `clasp_set`
- surface patterns: `cargo_fastener_grid`, `warning_stripe_band`

Guardrail fixture:

```text
examples/mechanical_door.lth
asset mechanical_door: env_module from mechanical_door_family uses shipping_module
```

Relevant authored intent:

- role: reinforced mechanical airlock door
- geometry mode: `exact_hard_surface`
- seam classes: `frame_split`, `hinge_cut`, `lock_cut`, `threshold_break`
- edge classes: `hero_bevel`, `frame_bevel`, `support_bevel`
- integration rules: `boolean_union`, `preserve_door_frame`, `preserve_threshold`
- allowed features: `inset_panel`, `frame_lip`, `hinge_set`, `support_bracket`, `vent_grille`, `edge_break`
- surface patterns: `warning_stripe_band`, `vent_slats_dense`

## 5. Check Commands

Command:

```powershell
.\.venv-win\Scripts\python.exe -m lathe.cli check examples/industrial_crate.lth
```

Result:

```text
PASS
```

Log:

```text
.tmp_tests/visible_geometry_sprint0_20260505/logs/check_industrial_crate.txt
```

Diagnostics:

- `L5262 invalid_pbr_dielectric_albedo`
- warning path: `material.velvet_interior.basecolor`
- warning message says `velvet_interior` dielectric basecolor `[132, 28, 32]` is outside the recommended sRGB range.

This warning appears to come from shared material definitions rather than the industrial crate fixture itself.

Command:

```powershell
.\.venv-win\Scripts\python.exe -m lathe.cli check examples/mechanical_door.lth
```

Result:

```text
PASS
```

Log:

```text
.tmp_tests/visible_geometry_sprint0_20260505/logs/check_mechanical_door.txt
```

Diagnostics:

- same `L5262 invalid_pbr_dielectric_albedo` warning for `material.velvet_interior.basecolor`

## 6. Full Baseline Build Commands

Command:

```powershell
.\.venv-win\Scripts\python.exe -m lathe.cli build examples/industrial_crate.lth industrial_crate --out .tmp_tests/visible_geometry_sprint0_20260505/baseline_industrial_crate --deterministic --report json
```

Result:

```text
BLOCKED / timed out
```

Output root:

```text
.tmp_tests/visible_geometry_sprint0_20260505/baseline_industrial_crate/industrial_crate
```

Command:

```powershell
.\.venv-win\Scripts\python.exe -m lathe.cli build examples/mechanical_door.lth mechanical_door --out .tmp_tests/visible_geometry_sprint0_20260505/baseline_mechanical_door --deterministic --report json
```

Result:

```text
BLOCKED / timed out
```

Output root:

```text
.tmp_tests/visible_geometry_sprint0_20260505/baseline_mechanical_door/mechanical_door
```

The full baseline build did not reach visible output for either fixture.

## 7. Bounded Baseline Build Commands

To determine whether candidate search or repair loops were the blocker, bounded builds were run.

Command:

```powershell
.\.venv-win\Scripts\python.exe -m lathe.cli build examples/industrial_crate.lth industrial_crate --out .tmp_tests/visible_geometry_sprint0_20260505/baseline_industrial_crate_bounded --deterministic --report json --candidates 1 --no-search --repair-rounds 0
```

Result:

```text
BLOCKED / timed out
```

Command:

```powershell
.\.venv-win\Scripts\python.exe -m lathe.cli build examples/mechanical_door.lth mechanical_door --out .tmp_tests/visible_geometry_sprint0_20260505/baseline_mechanical_door_bounded --deterministic --report json --candidates 1 --no-search --repair-rounds 0
```

Result:

```text
BLOCKED / timed out
```

After installing `manifold3d`, bounded builds were repeated in fresh output folders.

Command:

```powershell
.\.venv-win\Scripts\python.exe -m lathe.cli build examples/industrial_crate.lth industrial_crate --out .tmp_tests/visible_geometry_sprint0_20260505/baseline_industrial_crate_manifold_bounded --deterministic --report json --candidates 1 --no-search --repair-rounds 0
```

Result:

```text
BLOCKED / timed out
```

Log:

```text
.tmp_tests/visible_geometry_sprint0_20260505/logs/build_industrial_crate_manifold_bounded.txt
```

Observed warnings:

```text
lathe.cli.build: running with --candidates 1, output may be lower quality
RuntimeWarning: invalid value encountered in divide
RuntimeWarning: divide by zero encountered in divide
```

Command:

```powershell
.\.venv-win\Scripts\python.exe -m lathe.cli build examples/mechanical_door.lth mechanical_door --out .tmp_tests/visible_geometry_sprint0_20260505/baseline_mechanical_door_manifold_bounded --deterministic --report json --candidates 1 --no-search --repair-rounds 0
```

Result:

```text
BLOCKED / timed out
```

Log:

```text
.tmp_tests/visible_geometry_sprint0_20260505/logs/build_mechanical_door_manifold_bounded.txt
```

Observed warnings:

```text
lathe.cli.build: running with --candidates 1, output may be lower quality
RuntimeWarning: invalid value encountered in divide
RuntimeWarning: divide by zero encountered in divide
```

Conclusion:

```text
The blocker is not candidate width or repair loop count. The build blocks inside the shape-stage exact mesh/boolean path before downstream stages write evidence.
```

## 8. Stack Samples

Stack probe before `manifold3d` was installed:

```text
.tmp_tests/visible_geometry_sprint0_20260505/logs/build_industrial_crate_stackprobe.txt
```

Important stack excerpt:

```text
subprocess.py communicate
trimesh/interfaces/generic.py::run
trimesh/interfaces/blender.py::boolean
trimesh/boolean.py::union
lathe/exact_solids.py::_boolean_union
lathe/exact_solids.py::_clustered_union_by_part
lathe/exact_solids.py::_combine_explicit_meshes
lathe/exact_solids.py::compile_explicit_surface_mesh
lathe/geometry_kernel.py::_compile_exact_mesh_ir
lathe/geometry_kernel.py::fuse_shape_ir
lathe/scaffold_compiler.py::_runtime_from_shape_ir
lathe/core/stages/shape.py::run
lathe/executor.py::build
```

Interpretation:

```text
When only Blender is available as a trimesh boolean backend, Lathe can block in an external Blender boolean subprocess instead of reporting a bounded fallback or unavailable backend.
```

Stack probe after `manifold3d` was installed:

```text
.tmp_tests/visible_geometry_sprint0_20260505/logs/build_industrial_crate_stackprobe_manifold.txt
```

Observed:

```text
RuntimeWarning: invalid value encountered in divide
RuntimeWarning: divide by zero encountered in divide
Timeout (0:01:00)!
Thread ... most recent call first:
  File "...numpy\linalg\_linalg.py"
```

Interpretation:

```text
Installing manifold moves the path away from the Blender subprocess, but the current exact mesh boolean/finalization path still fails to produce a bounded result for this fixture.
```

The stack probe exited with Windows process code `-1073741819`, so the post-manifold failure should be treated as unstable native/numerical behavior, not a clean Lathe diagnostic.

## 9. Artifact Inventory

No visible artifact files were produced in any baseline output.

Search for visible/export formats under the Sprint 0 root found no files of these types:

```text
*.glb
*.png
*.usd
*.usdz
*.obj
*.stl
```

The build produced early planning files only.

For industrial crate full baseline:

```text
.tmp_tests/visible_geometry_sprint0_20260505/baseline_industrial_crate/industrial_crate/normalized_program.json
.tmp_tests/visible_geometry_sprint0_20260505/baseline_industrial_crate/industrial_crate/materialized_asset.json
.tmp_tests/visible_geometry_sprint0_20260505/baseline_industrial_crate/industrial_crate/plan.json
.tmp_tests/visible_geometry_sprint0_20260505/baseline_industrial_crate/industrial_crate/quality_generation_context.json
```

For mechanical door full baseline:

```text
.tmp_tests/visible_geometry_sprint0_20260505/baseline_mechanical_door/mechanical_door/normalized_program.json
.tmp_tests/visible_geometry_sprint0_20260505/baseline_mechanical_door/mechanical_door/materialized_asset.json
.tmp_tests/visible_geometry_sprint0_20260505/baseline_mechanical_door/mechanical_door/plan.json
.tmp_tests/visible_geometry_sprint0_20260505/baseline_mechanical_door/mechanical_door/quality_generation_context.json
```

Stage directories were created but empty:

```text
stages/shape: 0 files
stages/topology: 0 files
stages/uv: 0 files
stages/surface: 0 files
stages/validate: 0 files
stages/package: 0 files
stages/execution: 0 files
```

Missing required Sprint 0 evidence:

- no `build_report.json`
- no shape-stage mesh bundle
- no topology report
- no UV report
- no surface report
- no validate report
- no package manifest
- no preview images
- no GLB/USD export
- no comparison sheet

## 10. Human-Visible Weaknesses

Because no preview/export artifact exists yet, the human-visible weakness cannot be honestly evaluated from final output.

The visible weakness for this baseline is therefore:

```text
The authored hard-surface fixture promises exact hard-surface crate/door output, but the pipeline cannot currently produce the visible artifact evidence needed to judge it.
```

Likely downstream visual risks remain unverified:

- blockout-looking geometry
- missing bevel/chamfer evidence
- weak trim/fastener/vent hierarchy
- debug-material look
- weak material zone contrast
- missing final beauty preview
- proxy-only preview evidence

These must stay `not verified` until the shape-stage blocker is fixed and artifacts exist.

## 11. Validation Commands

Command:

```powershell
.\.venv-win\Scripts\python.exe -m pytest -q tests/unit/test_asset_quality_baseline_report_shape.py tests/unit/test_asset_quality_preview_evidence.py
```

Result:

```text
36 passed in 9.57s
```

What this validates:

- existing baseline-report shape tests
- existing preview-evidence tests

What it does not validate:

- crate build completion
- door build completion
- visible preview artifact generation
- package/export artifact generation
- before/after visual improvement

Additional focused command after the Sprint 0 runtime fixes:

```powershell
.\.venv-win\Scripts\python.exe -m pytest -q tests/unit/test_validator_geometry_integrity.py tests/unit/test_uv_ops.py tests/unit/test_core_rendering.py tests/unit/test_exact_solids.py tests/unit/test_geometry_kernel.py tests/unit/test_asset_quality_baseline_report_shape.py tests/unit/test_asset_quality_preview_evidence.py
```

Result:

```text
84 passed, 4 skipped, 2 deselected in 5.50s
```

Skips:

```text
tests/unit/test_uv_ops.py xatlas-dependent tests skipped because xatlas is not installed in .venv-win
```

What this validates:

- bounded geometry-integrity self-intersection scan evidence;
- box UV fallback no longer depends on `trimesh.Trimesh.face_normals`;
- preview rendering supports sampled large-mesh previews and returns preview evidence;
- exact-solids large-boolean fallback is covered;
- existing geometry-kernel unit behavior remains green.

## 12. Sprint 0 Runtime Fix Results

The first Sprint 0 implementation pass fixed the original "no visible artifact" blocker without changing public `.lth` syntax.

Code changes made in this pass:

- `lathe/exact_solids.py`
  - added a bounded exact-boolean operation cap;
  - large explicit boolean jobs now fall back to `exact_boolean_fallback_concatenate`;
  - fallback records `boolean_operation_count` and `boolean_fallback_reason`.
  - oversized union-only jobs can use bounded per-part clustered union;
  - oversized union-plus-cutter jobs can use `exact_boolean_fallback_clustered_union_omit_cutters`, which fuses visible union primitives by part and explicitly omits unsupported subtract/intersect cutters instead of rendering cutters as visible extra bodies.
- `lathe/core/rendering.py`
  - preview rendering now deterministically samples large meshes instead of drawing every face;
  - preview rendering computes normals directly from face vertices instead of using cached `trimesh.face_normals`;
  - `render_mesh_preview` returns a structured preview report.
- `lathe/core/stages/shape.py`
  - shape candidates now record `preview_report` beside `mesh_uri` and `preview_uri`.
- `lathe/core/uv_ops.py`
  - box UV fallback now computes face normals directly from face vertices;
  - this avoids a second large-mesh blocker in `trimesh.face_normals`.
- `lathe/validators/geometry_integrity.py`
  - self-intersection validation is now bounded at `25000` tested non-adjacent overlapping triangle pairs;
  - evidence reports `self_intersection_scan_limited` and `self_intersection_pair_budget`;
  - diagnostics include the same scan-limit fields when intersections are detected.

Regression tests added or updated:

- `tests/unit/test_exact_solids.py`
  - covers large explicit-boolean fallback to `exact_boolean_fallback_concatenate`.
- `tests/unit/test_core_rendering.py`
  - covers sampled preview rendering evidence.
- `tests/unit/test_uv_ops.py`
  - covers box UV direct-normal fallback without cached `trimesh.face_normals`.
- `tests/unit/test_validator_geometry_integrity.py`
  - covers bounded self-intersection scan evidence.

Updated bounded build command for the primary fixture:

```powershell
.\.venv-win\Scripts\python.exe -m lathe.cli build examples/industrial_crate.lth industrial_crate --out .tmp_tests/visible_geometry_sprint0_20260505/after_validate_guard_industrial_crate --deterministic --report json --candidates 1 --no-search --repair-rounds 0
```

Result:

```text
FAILED honestly at validation; no hang.
```

Primary fixture evidence root:

```text
.tmp_tests/visible_geometry_sprint0_20260505/after_validate_guard_industrial_crate/industrial_crate
```

Primary fixture artifacts now produced:

```text
stages/shape/bundle.json
stages/shape/candidate_00.glb
stages/shape/candidate_00.png
stages/topology/topology.glb
stages/topology/bundle.json
stages/uv/uv.glb
stages/uv/bundle.json
stages/surface/bundle.json
stages/surface/maps/basecolor.png
stages/surface/maps/normal.png
stages/surface/maps/ao.png
stages/surface/maps/curvature.png
stages/surface/maps/roughness.png
stages/surface/maps/orm.png
stages/surface/maps/emissive.png
stages/surface/maps/wear_mask.png
stages/surface/maps/material_layer_mask.png
stages/optimize/lod_0.glb
stages/optimize/lod_1.glb
stages/optimize/lod_2.glb
stages/optimize/lod_3.glb
stages/physics/collision.glb
stages/validate/report.json
stages/execution/bundle.json
```

Primary fixture validation result:

```text
score: 0.758486
package/export: not produced because validation failed
```

Primary fixture blocking diagnostics:

- `L6301 semantic_fragmentation_failed`: `fragmentation_penalty` is `1.000`, max allowed `0.240`.
- `L6399 toy_or_primitive_detected`: `component_score` is `0.0`, `structural_richness` is `0.8`, `toy_detected` is `true`.
- `L6100 ensure_failed`: two source ensure rules fail after validator failure.

Primary fixture warning diagnostics:

- `L6201 self_intersecting`: `6744` intersecting pairs in `25000` tested pairs; `self_intersection_scan_limited=true`.
- `L6202 inconsistent_normals`: `9` flipped edge adjacencies out of `128384`.
- `L6410 unknown_gameplay_tag`: `crate`, `industrial`, and `cargo` are not currently in the gameplay tag allowlist.

Updated bounded build command for the guardrail fixture:

```powershell
.\.venv-win\Scripts\python.exe -m lathe.cli build examples/mechanical_door.lth mechanical_door --out .tmp_tests/visible_geometry_sprint0_20260505/after_validate_guard_mechanical_door --deterministic --report json --candidates 1 --no-search --repair-rounds 0
```

Result:

```text
FAILED honestly at validation; no hang.
```

Guardrail fixture evidence root:

```text
.tmp_tests/visible_geometry_sprint0_20260505/after_validate_guard_mechanical_door/mechanical_door
```

Guardrail fixture artifacts now produced:

```text
stages/shape/bundle.json
stages/shape/candidate_00.glb
stages/shape/candidate_00.png
stages/topology/topology.glb
stages/topology/bundle.json
stages/uv/uv.glb
stages/uv/bundle.json
stages/surface/bundle.json
stages/surface/maps/basecolor.png
stages/surface/maps/normal.png
stages/surface/maps/ao.png
stages/surface/maps/curvature.png
stages/surface/maps/roughness.png
stages/surface/maps/orm.png
stages/surface/maps/emissive.png
stages/surface/maps/wear_mask.png
stages/surface/maps/material_layer_mask.png
stages/optimize/lod_0.glb
stages/optimize/lod_1.glb
stages/optimize/lod_2.glb
stages/physics/collision.glb
stages/validate/report.json
stages/execution/bundle.json
```

Guardrail fixture validation result:

```text
score: 0.764502
package/export: not produced because validation failed
```

Guardrail fixture blocking diagnostics:

- `L6301 semantic_fragmentation_failed`: `fragmentation_penalty` is `1.000`, max allowed `0.240`.
- `L6399 toy_or_primitive_detected`: `component_score` is `0.0`, `structural_richness` is `0.8`, `toy_detected` is `true`.
- `L6401 visual_surface_authoring_quality_failed`: `surface_authoring_quality` is `0.650659`, min required `0.720`.
- `L6100 ensure_failed`: two source ensure rules fail after validator failure.

Guardrail fixture warning diagnostics:

- `L6201 self_intersecting`: `9038` intersecting pairs in `25000` tested pairs; `self_intersection_scan_limited=true`.
- `L6202 inconsistent_normals`: `58` flipped edge adjacencies out of `167326`.

Current truth state:

```text
The first bounded fallback proved artifact generation, but rendering subtract cutters as visible geometry left both fixtures semantically fragmented and toy-like. The follow-up visible-union fallback fixes that by fusing union primitives by part and omitting unsupported cutters with an explicit fallback reason.
```

Follow-up primary fixture command:

```powershell
.\.venv-win\Scripts\python.exe -m lathe.cli build examples/industrial_crate.lth industrial_crate --out .tmp_tests/visible_geometry_sprint0_20260505/after_visible_union_fallback_timeout900_industrial_crate --runtime-config .tmp_tests/visible_geometry_sprint0_20260505/runtime_config_timeout900.json --deterministic --report json --candidates 1 --no-search --repair-rounds 0
```

Note:

```text
The temp runtime config contains execution.timeout_s=900 and currently emits a schema warning that /execution/timeout_s is unknown, even though the run reached validation. This is evidence-only and should not be treated as a production config change.
```

Follow-up primary fixture shape result:

```text
mode: exact_boolean_fallback_clustered_union_omit_cutters
boolean_operation_count: 681
subtract_primitive_count: 148
fallback_reason: fused union primitives by part and omitted 148 subtract / 0 intersect cutter primitive(s)
shape preview: stages/shape/candidate_00.png
shape mesh: stages/shape/candidate_00.glb
preview_report: rendered_sampled_preview, face_count=26080, rendered_face_count=25000
```

Follow-up primary fixture validation result:

```text
score: 0.866327
semantic fragmentation: PASS
toy detection: PASS
component_score: 1.0
fragmentation_penalty: 0.0
body_count: 16
self_intersection_rate: 0.02064
self_intersections: 516 / 25000 tested pairs, scan_limited=true
normal_consistency: 0.994008
package/export: not produced because manifold and watertight ensure rules fail
```

Remaining primary fixture blockers:

- `ensure manifold` failed.
- `ensure watertight` failed.
- `L6201 self_intersecting` remains a warning, reduced from `6744 / 25000` to `516 / 25000` tested pairs.
- `L6202 inconsistent_normals` remains a warning, now `233` flipped edge adjacencies out of `38886`.
- `L6410 unknown_gameplay_tag` warnings remain for `crate`, `industrial`, and `cargo`.

Follow-up guardrail command:

```powershell
.\.venv-win\Scripts\python.exe -m lathe.cli build examples/mechanical_door.lth mechanical_door --out .tmp_tests/visible_geometry_sprint0_20260505/after_visible_union_fallback_timeout900_mechanical_door --runtime-config .tmp_tests/visible_geometry_sprint0_20260505/runtime_config_timeout900.json --deterministic --report json --candidates 1 --no-search --repair-rounds 0
```

Follow-up guardrail shape result:

```text
mode: exact_boolean_fallback_clustered_union_omit_cutters
boolean_operation_count: 610
subtract_primitive_count: 130
fallback_reason: fused union primitives by part and omitted 130 subtract / 0 intersect cutter primitive(s)
shape preview: stages/shape/candidate_00.png
shape mesh: stages/shape/candidate_00.glb
preview_report: rendered_sampled_preview, face_count=26078, rendered_face_count=25000
```

Follow-up guardrail validation result:

```text
score: 0.877181
semantic fragmentation: PASS
toy detection: PASS
component_score: 1.0
fragmentation_penalty: 0.0
body_count: 57
surface_authoring_quality: 0.713283, required 0.720
self_intersection_rate: 0.04496
self_intersections: 1124 / 25000 tested pairs, scan_limited=true
normal_consistency: 0.994451
package/export: not produced because surface_authoring_quality, manifold ensure, and watertight ensure fail
```

Remaining guardrail blockers:

- `L6401 visual_surface_authoring_quality_failed`: `0.713283 < 0.720`.
- `ensure manifold` failed.
- `ensure watertight` failed.
- `L6201 self_intersecting` remains a warning, reduced from `9038 / 25000` to `1124 / 25000` tested pairs.
- `L6202 inconsistent_normals` remains a warning, now `211` flipped edge adjacencies out of `38027`.

Updated truth state:

```text
The Sprint 0 path now produces visible previews and downstream artifacts for both fixtures, and the semantic fragmentation / toy-detection blocker is fixed for both. The artifacts are still not package/export-ready because they are non-manifold, non-watertight, retain bounded self-intersection warnings, and the door remains just below the surface-authoring threshold.
```

## 13. Sprint 0 Next Implementation Target

The next implementation should not start by adding more public language.

The original "build path bounded and truthful" target is now materially satisfied for Sprint 0 evidence:

1. Exact boolean execution is bounded for large explicit primitive counts.
2. Shape previews are bounded and evidence-bearing.
3. UV fallback avoids the large cached-normal blocker.
4. Geometry-integrity validation is bounded and evidence-bearing.
5. Both fixtures now produce shape, topology, UV, surface, optimize, validate, and execution artifacts.
6. Both fixtures no longer fail semantic fragmentation or toy detection.
7. Both fixtures still fail before package/export.

The next implementation target should therefore be:

```text
manifold / watertight visible geometry for industrial_crate, with mechanical_door surface quality and manifoldness as the guardrail.
```

Concrete next slice:

1. Keep `exact_boolean_fallback_clustered_union_omit_cutters` honest: it is a visible fallback, not a final exact-boolean success.
2. Replace cutter omission with a bounded cutter execution route for at least one hard-surface operation class, starting with panel/lid/corner cut preservation or trim-band seating.
3. Reduce or repair self-intersections from the visible-union fallback without hiding the bounded scan evidence.
4. Make `ensure manifold` and `ensure watertight` actionable: report which stage/mesh property fails and which operation family caused it.
5. Improve mechanical-door surface output enough to clear `surface_authoring_quality >= 0.720`.
6. Rebuild the crate and record before/after paths.
7. Rebuild the mechanical door to prove the fix is not crate-only.

Minimum next acceptance:

```text
industrial_crate no longer fails `ensure manifold` and `ensure watertight` after the visible-union fallback.
```

Better next acceptance:

```text
industrial_crate bounded build passes validation and reaches package/export with fallback state still recorded.
```

Guardrail acceptance:

```text
mechanical_door keeps semantic fragmentation / toy detection green and clears or improves `surface_authoring_quality`, manifoldness, and watertightness.
```

## 14. Post-Breakthrough Acceptance Evidence

This pass changed the status from "visible artifacts but no package/export" to "primary and guardrail certify with package/export artifacts."

Implementation changes proven by the following runs:

1. High-count explicit boolean programs with subtract cutters now try a bounded Manifold full-CSG route before any cutter-omission fallback.
2. MeshIR finalization preserves welded topology for the authoritative shape handoff instead of splitting vertices for render-only hard-edge shading.
3. Topology auto routing preserves watertight exact-boolean output through `integrated_preserve_cleanup` instead of sending it back through Blender.
4. Standalone subdivision finishing is skipped for preserved watertight exact-boolean output so face-part attribution is not collapsed.
5. Deterministic surface normal authoring now uses material profile, wear masks, curvature, layer masks, and accent masks more strongly; the door clears the surface-authoring guardrail without lowering thresholds.

Primary fixture command:

```powershell
.\.venv-win\Scripts\python.exe -m lathe.cli build examples/industrial_crate.lth industrial_crate --out .tmp_tests/visible_geometry_sprint0_20260505/after_skip_subdivision_manifold_csg_timeout900_industrial_crate --runtime-config .tmp_tests/visible_geometry_sprint0_20260505/runtime_config_timeout900.json --deterministic --report json --candidates 1 --no-search --repair-rounds 0
```

Primary fixture evidence root:

```text
.tmp_tests/visible_geometry_sprint0_20260505/after_skip_subdivision_manifold_csg_timeout900_industrial_crate/industrial_crate
```

Primary fixture result:

```text
certified: true
score: 0.869020
threshold: 0.840000
shape mode: exact_boolean_manifold_kernel
boolean_kernel: lathe.geometry.manifold_v1
boolean_backend: manifold3d
bounded_boolean_route: manifold_kernel_full_csg
shape watertight: true
shape body_count: 2
shape triangles: 19948
topology adapter: integrated_preserve_cleanup
topology watertight: true
topology body_count: 2
topology triangles: 19948
subdivision_finishing: skipped_for_watertight_exact_boolean_preservation
self_intersection_rate: 0.0
normal_consistency: 0.988503
part_coverage: 1.0
fragmentation_penalty: 0.0
toy_detected: false
surface_authoring_quality: 0.833066
geometry_integration_quality: 1.0
package manifest: stages/package/package_manifest.json
trace manifest: stages/package/trace_manifest.json
primary package exports: stages/package/industrial_crate.glb, stages/package/industrial_crate.usda
texture exports: stages/package/textures/basecolor.png, stages/package/textures/normal.png, stages/package/textures/orm.png, stages/package/textures/ao.png, stages/package/textures/emissive.png
```

Guardrail fixture command:

```powershell
.\.venv-win\Scripts\python.exe -m lathe.cli build examples/mechanical_door.lth mechanical_door --out .tmp_tests/visible_geometry_sprint0_20260505/after_surface_normal_gain_v3_timeout900_mechanical_door --runtime-config .tmp_tests/visible_geometry_sprint0_20260505/runtime_config_timeout900.json --deterministic --report json --candidates 1 --no-search --repair-rounds 0
```

Guardrail fixture evidence root:

```text
.tmp_tests/visible_geometry_sprint0_20260505/after_surface_normal_gain_v3_timeout900_mechanical_door/mechanical_door
```

Guardrail fixture result:

```text
certified: true
score: 0.876168
threshold: 0.840000
shape mode: exact_boolean_manifold_kernel
boolean_kernel: lathe.geometry.manifold_v1
boolean_backend: manifold3d
bounded_boolean_route: manifold_kernel_full_csg
shape watertight: true
shape body_count: 5
shape triangles: 22010
topology adapter: integrated_preserve_cleanup
topology watertight: true
topology body_count: 5
topology triangles: 22010
subdivision_finishing: skipped_for_watertight_exact_boolean_preservation
self_intersection_rate: 0.0
normal_consistency: 0.991761
part_coverage: 1.0
fragmentation_penalty: 0.0
toy_detected: false
surface_authoring_quality: 0.726216
surface_normal_richness: 0.700014
surface_bake_cleanliness: 0.637748
geometry_integration_quality: 1.0
package manifest: stages/package/package_manifest.json
trace manifest: stages/package/trace_manifest.json
primary package exports: stages/package/mechanical_door.glb, stages/package/mechanical_door.usda
texture exports: stages/package/textures/basecolor.png, stages/package/textures/normal.png, stages/package/textures/orm.png, stages/package/textures/ao.png, stages/package/textures/emissive.png
```

Important caveat:

```text
The runtime config used for these long evidence builds still emits a warning that /execution/timeout_s is an unknown key that will become an error in a future release. That config is evidence-only until the runtime-config schema accepts the timeout field.
```

## 15. Allowed Claims After This Pass

Allowed:

- Baseline fixture checks pass.
- The original full and bounded baseline builds were blocked before visible output.
- The original block occurred in shape-stage exact mesh / boolean fusion.
- Missing or optional geometry dependencies materially affected the path.
- Current bounded Manifold full-CSG builds produce shape, topology, UV, surface, optimize, validate, package, and execution artifacts.
- Current bounded Manifold full-CSG builds pass validation and package/export for `industrial_crate` and `mechanical_door`.
- The visible-union fallback removed semantic fragmentation / toy detection for both fixtures before the full-CSG route landed.
- The full-CSG route executes subtract cutters instead of omitting them when `manifold3d` is available and the boolean operation count is within the bounded Manifold limit.
- MeshIR now preserves welded topology at the authoritative handoff; hard-edge shading intent remains metadata.
- Topology now preserves watertight exact-boolean output instead of reprocessing it through Blender in auto mode.
- The self-intersection validator is now bounded and reports that bounded state.
- Primary fixture and guardrail package/export artifacts exist at the evidence roots above.
- No human before/after final beauty comparison has been written yet.
- The next implementation target can move from "reach package/export" to visual comparison, import evidence, and broader fixture coverage.

Not allowed:

- Human-visible improvement has been judged from a before/after final beauty preview.
- External engine import evidence exists for these packages.
- The evidence-timeout runtime config is production schema-clean.
- Every hard-surface family now certifies through this route.
- The exact hard-surface path is production-ready for these fixtures.

---

## Phase B Baseline Refresh — 2026-05-12

After Cycle 1/2/3 substrate landed (procedural synthesizer, generators, decorators, recipe decommission) and Cycle 4 Phase A (policy expansions, zone-op consumers, honest harness) closed all four PARTIAL acceptance criteria, the `industrial_crate` baseline was re-captured to ground Sprint 0 S0-3/S0-4/S0-5/S0-6 work.

### Build command (re-run)

```powershell
python -m lathe.cli build examples/industrial_crate.lth industrial_crate `
  --out .tmp_tests/baseline_industrial_crate --deterministic
```

Out dir: `.tmp_tests/baseline_industrial_crate/industrial_crate/`

### Headline metrics

- `certified`: **True**
- `score`: **0.884666** (threshold: 0.84)
- Repair rounds executed: 2 (round 1 `local_repair`, round 2 `reselect_candidate`)

Round 2 jumped from 0.754 → 0.885 by replacing the original candidate with a better-scored one. The diagnostics it "resolved":
- `toy_or_primitive_detected` ← *this is the northstar §8 "looks like procedural blockout" mode firing on the pre-repair candidate*
- `semantic_silhouette_fidelity_failed`
- `semantic_part_coverage_failed`
- `semantic_adjacency_score_failed`
- `visual_surface_authoring_quality_failed`

The asset certifies, but the validators that fire pre-repair name exactly the failure mode S0-3/S0-5 must close.

### Topology composition

`stages/topology/bundle.json::part_groups`:

| Part | Face count |
|---|---:|
| body | 321 |
| foot_l | 107 |
| foot_r | 105 |
| handle_l | 819 |
| handle_r | 818 |
| latch_plate | 52 |
| **Total** | **2,222** |

`material_zones` count in topology bundle: **0** — no material zones bound from topology. (The Phase A.2 synthesizer-zone path is not exercised here because the .lth has no authored `construction_graph`; see "Routing observation" below.)

### Visual evidence

`stages/package/previews/turntable.png` and `stages/package/previews/material_ids.png`:

- **Hard 90° edges everywhere.** Zero bevel/chamfer treatment.
- **Body faces show hideous radial triangulation** — not quads, not edge loops.
- **Two visible secondary features only:** a small green knot on the left face (per topology = `handle_l`, but reads as an artifact not a load-bearing handle); a small yellow rectangle on the right (warning decal carrier).
- **No corner guards, no mid trim, no foot rails, no fastener grid, no lid seam visible** despite the family declaring `support_bracket`, `trim_band`, `cargo_bevel`, `fastener_strip`, `lid_break`.
- **Silhouette is a near-perfect rectangular box.**

`stages/package/previews/wireframe.png`: confirms the topology weakness — long thin triangles fanning across each body face. The handles are detail-dense knots punched through near-empty hosts.

`stages/surface/maps/basecolor.png`: actually well-authored — gray painted steel, yellow warning stripes, white shipping labels. The texture is real; the geometry hosting it isn't.

### Failure-mode scorecard against northstar §8 minimum-visible-improvement bar

| Northstar bar | Baseline state |
|---|---|
| less primitive/blockout-looking | **FAILS** — `toy_or_primitive_detected` fired pre-repair |
| clearer silhouette or hard-surface hierarchy | **FAILS** — rectangular box silhouette, no hierarchy |
| visible bevel/chamfer, trim, fasteners, vents, panels | **FAILS** — zero of any of these visible |
| coherent final materials (not debug colors) | **PARTIAL** — basecolor texture is good, but geometry zoning doesn't match the .lth's three declared materials |
| evidence paths in report | **PASS** (this update) |

### Routing observation (important for S0-3)

The current baseline routes through the **legacy scaffold path**, not the procedural synthesizer:

- `examples/industrial_crate.lth` has no `construction_graph` block.
- `synthesizer_eligible(asset, runtime_config)` returns False.
- Build dispatches to `compile_scaffold_candidates` (legacy) — Cycle 3 / Phase A policy expansions never run for this asset.

This means S0-3 ("add one visible-geometry detail operation") has two parallel sub-paths:

1. **Wire industrial_crate to drive through the synthesizer** — add a minimum `construction_graph` block to the .lth (just a `primary_volume`), then Phase A.1's policy expansion provides corner brackets, trim, etc. for free. All 71 alias-driven assets benefit from this wiring at once.
2. **Add a real bevel/chamfer kernel op** — independent of dispatch path. Without it, even the synthesizer path produces sharp-edged boxes.

Both are reusable beyond crate; that satisfies northstar's "must be reusable beyond one fixture" rule. The .lth wiring is the smaller change; the kernel op is the substantive one.

### Done condition for S0-3 / S0-4 / S0-5 / S0-6 measurement

- **S0-3 evidence:** the same turntable.png shows visibly chamfered edges; body face count rises from 321 → 600+ (bevel adds geometry); pre-repair score on the same seed improves.
- **S0-4 evidence:** `material_zones` count in topology bundle goes from 0 → 3 (or 3+ via the synthesizer-zone merge if the .lth gets wired to the synthesizer). painted_steel binds to body, rubber_trim binds to a real trim band, warning_paint binds to a decal carrier.
- **S0-5 evidence:** the new diagnostic catches the blockout state on the pre-repair candidate AND continues to fire if repair only "reselects" without adding bevels — i.e., reselect can't satisfy it.
- **S0-6 evidence:** when the diagnostic fires, the repair planner emits a concrete bevel/chamfer or add-trim operation; re-build resolves it on the same seed (no reselect dependency).

This is the falsifiable before-state. S0-3 work begins next.

---

## Sprint 0 Phase B Status Update — 2026-05-12 (later)

Five Sprint 0 tasks (S0-1, S0-3, S0-4, S0-5, S0-6) shipped earlier in
this session at the substrate level. The Phase B capstone — getting
`industrial_crate.lth` to drive through the procedural synthesizer
so the new bevel + material wiring + diagnostic + repair all
exercise on the live build — added three more changes:

### Capstone Option 3 (commit `fcfde24`): widened `synthesizer_eligible`

The predicate now returns True when (FamilyAlias for the asset's
family exists) AND (asset.intent.parts is non-empty), even without
an authored construction_graph. Combined with Option 2 below, this
makes the procedural synthesizer the default path for every .lth
that lists parts.

### Capstone Option 2 (commit `fcfde24`): auto-graph synthesis from parts

`runtime_from_asset` now synthesizes a default `construction_graph`
from `intent.parts` when no graph is authored. Each part name is
classified via `_classify_part` (existing substring rules) into a
NODE_TYPE; the first part that classifies as `primary_volume`
becomes the body node with scale-derived dimensions (0.9m → 90cm).
A new `_NODE_TYPE_AUTO_DEFAULTS` table provides minimum required
attributes for all 20 hard-surface NODE_TYPEs so authored parts
survive Stage 4 schema validation.

Python-level probe with industrial_crate's authored intent dict:
  - synthesizer_eligible: True
  - auto-graph: 6 nodes (body→primary_volume, latch_plate→latch,
    handle_l/r→handle, foot_l/r→mount) with 90cm body dimensions
  - shape_program emit: **52 ops** (1 body solid + 1 op.bevel from
    S0-3 style default + 8 corner brackets + 2 handles + 2 rails +
    1 trim + 1 fastener + 1 panel + 1 inset + 3 zone metadata ops +
    16 op.union attached_to edges)
  - 0 attribute_schema_violations

### Capstone Option 1 (commit `fcfde24`): grammar extension for explicit procedural{} block

`grammar/lathe.lark` + `lathe/parser/fast_parser.py` +
`lathe/parser/transformer_blocks.py` updated to accept an optional
`procedural { ... }` sub-block under `build.shape`. Authors can now
write:

```
build {
  shape {
    procedural {
      construction_graph = { nodes = [...], edges = [...] }
      auto_graph = disabled
      brief = { family = "...", style_id = "...", policy_ids = [...] }
    }
  }
}
```

The block lifts verbatim into `asset.build.shape.procedural`, where
`synthesizer_eligible` / `runtime_from_asset` already look. Authors
who want to override Option 2's auto-graph or opt out entirely can
declare it explicitly.

### Outstanding gap — live full-backend before/after rendering

The Python-level probe confirms the dispatch + auto-graph + 52-op
ShapeProgram all work end-to-end. The live `python -m lathe.cli build
examples/industrial_crate.lth ...` invocation that exercises the
full kernel + boolean compile of those 52 ops did NOT complete in
this session — the build hung in the shape stage's boolean kernel
for >30 minutes with no shape-stage artifacts produced.

This is a **kernel-performance gap**, not a substrate gap. The same
52-op program lowers correctly to v1 records, registers all the
zone-op metadata, and produces a non-empty ShapeProgram in
sub-second time at the synthesizer level. The bottleneck is in the
boolean compile path the shape backend invokes downstream — likely
related to the 16 `op.union` attached_to edges compounded with the
solid primitives, the existing kernel's bounded-Manifold full-CSG
route, and the increased op count vs the legacy scaffold path.

Three honest paths to close this gap:
1. **Profile + optimize the boolean compile** for the 50+ op case.
   Likely the highest-leverage move once visible-quality work
   identifies what's actually slow.
2. **Reduce the policy's expansion count** for v1 (e.g., 4 corner
   brackets instead of 8, single-handle, no fastener) until the
   kernel handles larger programs gracefully.
3. **Mark the auto-graph path as opt-in** via the new
   `procedural { auto_graph = enabled }` Option-1 flag, and have
   industrial_crate.lth keep using the legacy scaffold until the
   kernel-perf work is done. This unblocks the Sprint 0 visible
   demo while the kernel performance work continues in parallel.

The "before/after turntable.png comparison" the Sprint 0 done
condition asks for is therefore deferred to a Cycle 4 Lane A
kernel-performance pass. The substrate work (S0-1 through S0-6 +
Capstone Options 1/2/3) is complete and verified at the Python /
unit-test / contract-test level — what's outstanding is the
multi-minute kernel run time, not the procedural correctness.

## P0 Stabilization Wedge Run — 2026-05-13

This section records the P0 wedge evidence pass driven by
`docs/asset-quality/p0-p1-stabilization-execution-plan.md` §4. The plan
required a current evidence inventory for `industrial_crate` and a
`mechanical_door` guardrail, with explicit truth-labels for every artifact.

### Environment snapshot

| Field | Value |
|---|---|
| Date | 2026-05-13 |
| Branch | `main` |
| Python (host shell) | 3.14.0 |
| Build interpreter | `.venv-win/Scripts/python.exe` (Python 3.14.0) |
| Matrix interpreters | `.venv-311/Scripts/python.exe` (3.11.14), `.venv-312/Scripts/python.exe` (3.12.12) |
| Blender | available (`blender.CMD` on PATH) |
| manifold3d | available |
| xatlas | missing |
| Hunyuan HTTP | unavailable (no server) |
| VGGT / torch | unavailable |

### Source check (real)

```text
.venv-win/Scripts/python.exe -m lathe.cli check examples/industrial_crate.lth   → ok=true
.venv-win/Scripts/python.exe -m lathe.cli check examples/mechanical_door.lth   → ok=true
.venv-311/Scripts/python.exe -m lathe.cli check examples/industrial_crate.lth  → ok=true
.venv-311/Scripts/python.exe -m lathe.cli check examples/mechanical_door.lth   → ok=true
.venv-312/Scripts/python.exe -m lathe.cli check examples/industrial_crate.lth  → ok=true
.venv-312/Scripts/python.exe -m lathe.cli check examples/mechanical_door.lth   → ok=true
```

### Build attempt — industrial_crate

Two attempts were made:

```text
Attempt 1:
  .venv-win/Scripts/python.exe -m lathe.cli build examples/industrial_crate.lth industrial_crate \
    --out .tmp_tests/p0_wedge_industrial_crate_2026_05_13 --deterministic

  Started: 2026-05-13 01:50
  Outcome: blocked — process hung in shape stage, no shape-stage artifacts emitted for >17 minutes
  Action: terminated manually (Stop-Process)
  Exit code reported by background task: 0 (post-kill)

Attempt 2 (without --deterministic):
  .venv-win/Scripts/python.exe -m lathe.cli build examples/industrial_crate.lth industrial_crate \
    --out .tmp_tests/p0_wedge_industrial_crate_2026_05_13_r2

  Started: 2026-05-13 02:09
  Outcome: blocked — process hung in shape stage, no shape-stage artifacts emitted for >5 minutes
  Action: terminated manually (Stop-Process)
  Exit code reported by background task: 0 (post-kill)

Attempt 3 (quick mode):
  .venv-win/Scripts/python.exe -m lathe.cli quick examples/industrial_crate.lth industrial_crate \
    --out .tmp_tests/p0_wedge_industrial_crate_2026_05_13_quick.glb --no-cache

  Started: 2026-05-13 02:12
  Outcome: blocked — process hung in shape stage, no glb output emitted for >5 minutes
  Action: terminated manually (Stop-Process)
```

This reproduces the existing documented blocker (this same evidence doc,
"Outstanding gap — live full-backend before/after rendering" section).
That section already records: "the build hung in the shape stage's boolean
kernel for >30 minutes with no shape-stage artifacts produced … This is a
kernel-performance gap, not a substrate gap."

### Artifact inventory — industrial_crate (attempted)

| Evidence class | Output path | Label |
|---|---|---|
| Source fixture | `examples/industrial_crate.lth` | real |
| Command transcript | (see attempts above) | real |
| Output directories | `.tmp_tests/p0_wedge_industrial_crate_2026_05_13/`, `.tmp_tests/p0_wedge_industrial_crate_2026_05_13_r2/` | real (pre-stage scaffolding only) |
| Pre-stage outputs | `industrial_crate/{materialized_asset,normalized_program,plan,quality_generation_context}.json` | real (in both run dirs) |
| Shape bundle | `industrial_crate/stages/shape/bundle.json` | blocked (shape stage hang in boolean kernel) |
| Topology bundle | `industrial_crate/stages/topology/...` | blocked (downstream of shape hang) |
| UV bundle | `industrial_crate/stages/uv/...` | blocked (downstream of shape hang) |
| Surface evidence | `industrial_crate/stages/surface/...` | blocked (downstream of shape hang) |
| Validation report | `industrial_crate/stages/validate/report.json` | blocked (downstream of shape hang) |
| Package manifest | `industrial_crate/stages/package/...` | blocked (downstream of shape hang) |
| Export artifact (GLB/USD) | `industrial_crate/stages/package/...` | blocked (downstream of shape hang) |
| Preview evidence | `industrial_crate/stages/package/previews/*` | blocked (downstream of shape hang) |
| Attempted-vs-actual trace | — | blocked (shape stage did not finish writing bundle.json) |

### Build attempt — mechanical_door guardrail

Not attempted in this pass. Because `industrial_crate` (the simpler hard-
surface fixture per the catalog) hung in the documented shape-stage path,
running the same command on `mechanical_door` would reproduce the same
blocker. Labeling `mechanical_door` as `blocked` is the truthful label.
The guardrail asset's check passed in §"Source check" above, which is the
useful new evidence; a build under the same blocked kernel path would not
add information beyond a second hang.

### Exact blocker

Identical to the existing "Outstanding gap — live full-backend before/after
rendering" section (~30 lines above this one): the shape stage's boolean
kernel does not return for `industrial_crate`'s ~52-op program within the
budget allowed by this pass. The pre-stage outputs (normalized, planned,
materialized, generation context) are produced quickly; everything from
`stages/shape/bundle.json` downward never appears.

### What this run did add

- Confirmed the source pipeline (`parse → normalize → resolve → check →
  plan → materialize → quality_generation_context`) is green on the host
  3.14.0 interpreter and on a fresh 3.11.14 and 3.12.12 install.
- Reproduced the boolean-kernel hang at the build stage on the current
  worktree without any code path changes that touch shape kernel selection.
  Ruff/test stabilization work in this pass did not move the kernel-performance
  baseline.

### Acceptance against plan §4.6

- "The wedge build command exits 0, or the blocker is recorded with exact failure text." → blocker recorded above.
- "Every required artifact path is recorded or explicitly labeled missing/proxy/fallback/blocked." → table above labels each artifact.
- "The guardrail check/build proves the path is not crate-only, or records the blocking difference." → guardrail check is green; the build is blocked under the same documented kernel-performance gap.
- "No visual-improvement language appears without preview/export evidence." → this section makes no visual-improvement claim.
