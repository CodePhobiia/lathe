# P0/P1 Stabilization Execution Plan

Date: 2026-05-13
Status: Active planning document
Scope: Red gate recovery, wedge asset evidence, documentation hygiene, module decomposition, and supported Python matrix validation.

This document turns the latest audit findings into an execution plan. It is not a new product roadmap. It is the stabilization lane that must run before Lathe can credibly claim the next visible-geometry push is ready for broader implementation or release-style review.

The plan covers five items:

1. P0: Fix current red gates: Ruff, docs-static audit, asset-quality diagnostics tests, and ShapeIR op-set tests.
2. P0: Rebuild one wedge asset, preferably `industrial_crate`, from `.lth` to package/export evidence and record current artifact paths.
3. P0: Remove private path leaks and reconcile `docs/examples_catalog.md`.
4. P1: Split the largest core modules behind existing contracts.
5. P1: Run the supported Python 3.11/3.12 matrix from a clean checkout.

## 1. Operating Principles

### 1.1 Truth Rules

Every remediation must preserve the repository's current truth standard:

- If a gate is red, fix the root cause or document the blocker. Do not weaken the gate to create a green-looking result.
- If a visual asset claim is made, point to generated mesh, material, preview, package, validation, or export evidence.
- If a path falls back, record attempted behavior, actual behavior, and the fallback reason.
- If current evidence is missing, label the item `not verified`.
- If a dependency, renderer, adapter, or interpreter is unavailable, label the item `blocked` and name the missing condition.

### 1.2 Contract Rules

The stabilization work must preserve:

- public `.lth` source compatibility;
- the stable shape handoff contract `lathe.shape.intent_mesh_handoff_v1`;
- public CLI behavior unless a documented compatibility change is explicitly approved;
- existing stage artifact names unless a coordinated migration is recorded;
- current tests as behavioral contracts unless they are demonstrably stale and updated with source evidence.

### 1.3 Non-goals

This plan does not authorize:

- new public `.lth` syntax;
- broader feature work that bypasses current red gates;
- broad rewrites of unrelated systems;
- deletion or cleanup of unrelated user/generated artifacts;
- fake Blender, renderer, bake, package, or import evidence;
- changing diagnostics to hide unsupported or degraded output.

## 2. Current Gate Snapshot

The following snapshot was refreshed on 2026-05-13 from the current working tree.

| Gate | Command | Current result | Blocking signal |
|---|---|---|---|
| Ruff | `ruff check . --statistics --exit-zero` | `1578` errors reported | `960` fixable; largest classes include `RUF046`, `F401`, `I001`, `UP037`, `UP035` |
| Docs static audit | `python -m pytest -q tests/unit/test_docs_static_audit.py` | `5 failed, 17 passed` | private path leaks, missing examples catalog entries, internal implementation references in user-facing docs |
| Asset-quality diagnostics | `python -m pytest -q tests/unit/test_asset_quality_preview_evidence.py tests/unit/test_asset_quality_diagnostics.py tests/unit/test_asset_quality_generation_steering.py` | `4 failed, 46 passed` | diagnostics payload/test contract drift around added fields, metrics, and renderer-unavailable warnings |
| Geometry/ShapeIR targeted lane | `python -m pytest -q tests/unit/test_geometry_kernel.py tests/unit/test_shape_ir_v2.py tests/unit/test_asset_quality_grammar_lowering.py` | `1 failed, 59 passed` | `ALL_OPS` includes zone ops that the union/count test does not include |

These failures are enough to block any production-ready or release-ready claim. They do not mean the project lacks valuable capability; they mean the current checkout is not in a state where capability claims can be trusted without repair.

## 3. P0 Workstream A: Fix Current Red Gates

### 3.1 Ruff Gate

#### Current evidence

Command:

```powershell
ruff check . --statistics --exit-zero
```

Current result:

```text
Found 1578 errors.
960 fixable with --fix.
```

Largest reported categories:

| Rule | Count | Meaning | Likely remediation lane |
|---|---:|---|---|
| `RUF046` | 569 | unnecessary int cast | mechanical cleanup after checking behavior-sensitive numeric conversions |
| `F401` | 205 | unused import | mechanical cleanup, but inspect public re-export files before deletion |
| `I001` | 169 | unsorted imports | safe automated formatting lane |
| `UP037` | 73 | quoted annotation | mostly mechanical modernization |
| `UP035` | 49 | deprecated import | inspect runtime compatibility before replacement |
| `SIM105` | 42 | suppressible exception | do not blindly rewrite security or cleanup flows |
| `B033` | 35 | duplicate value | inspect constants and op registries before changing |
| `RUF007` | 35 | use `itertools.pairwise` | only apply where Python support allows it and intent remains clear |

#### Required approach

Split Ruff recovery into three passes:

1. **Source-set classification.** Determine which failures are in tracked source, tracked tests/docs, untracked scratch files, and generated artifacts. Do not delete or revert unrelated untracked files without explicit approval.
2. **Safe automated pass.** Use Ruff's fix mode only for rules that are semantically safe in the touched source set, then review the diff.
3. **Manual semantic pass.** Handle imports, duplicate constants, hardcoded-security warnings, undefined names, and exception-flow warnings with local source context.

#### Files and areas to inspect

- `pyproject.toml` for the configured Ruff scope and ignored baseline.
- `lathe/` for source failures.
- `tests/` for test-only failures.
- top-level scratch files and untracked generated outputs before deciding whether they belong in the Ruff source set.
- `.gitignore` and release-gate docs if generated artifacts are polluting the gate.

#### Acceptance criteria

- `ruff check .` exits `0` from the intended source tree.
- Any excluded generated/scratch path is excluded intentionally through repo policy, not local accident.
- No public API surface is removed while clearing unused imports.
- No security-sensitive exception flow is collapsed into silent failure.

#### Verification

Run:

```powershell
ruff check .
git diff --check
```

If automated fixes are used, also run the targeted tests that cover the edited packages.

### 3.2 Docs-static Audit Gate

#### Current evidence

Command:

```powershell
python -m pytest -q tests/unit/test_docs_static_audit.py
```

Current result:

```text
5 failed, 17 passed
```

Failure classes:

1. Public docs leak checkout-specific absolute paths.
2. Public docs contain a private user-path literal.
3. Source/public-doc scan sees the same private path classes.
4. `docs/examples_catalog.md` omits 12 checked-in `.lth` examples.
5. User-facing docs mention internal implementation module imports that the static audit forbids outside architecture/API/ADR docs.

#### Required approach

Fix docs as public product artifacts:

- replace absolute local checkout paths with repo-relative paths or generic placeholders;
- remove private user-directory literals entirely;
- add every checked-in `.lth` example to `docs/examples_catalog.md`, or remove/relocate examples that are not intended to be checked in;
- move implementation-module details to architecture/API docs, or rewrite user-facing docs in stable public terms.

#### Known missing catalog entries

The docs-static audit currently identifies these checked-in examples as missing from `docs/examples_catalog.md`:

- `examples/alien_blob_demo.lth`
- `examples/alien_grove_showcase.lth`
- `examples/bevel_demo.lth`
- `examples/dungeon_corridor_demo.lth`
- `examples/f_rep_alien_blob.lth`
- `examples/mech_prop_demo.lth`
- `examples/oak_tree_demo.lth`
- `examples/parametric_facade.lth`
- `examples/rocky_hill_demo.lth`
- `examples/scatter_demo.lth`
- `examples/scatter_on_surface_demo.lth`
- `examples/volume_smoke_cloud.lth`

#### Acceptance criteria

- `tests/unit/test_docs_static_audit.py` exits `0`.
- No absolute checkout paths remain in public markdown.
- No private user paths remain in public markdown or source comments.
- `docs/examples_catalog.md` lists every checked-in `examples/**/*.lth` path.
- User-facing docs describe stable concepts and artifact names, not private implementation imports.

#### Verification

Run:

```powershell
python -m pytest -q tests/unit/test_docs_static_audit.py
```

Then run:

```powershell
python -m pytest -q tests/unit/test_public_surface.py tests/unit/test_quality_gate_wiring.py
```

The second command guards against doc fixes accidentally weakening public-surface or quality-gate expectations.

### 3.3 Asset-quality Diagnostics Tests

#### Current evidence

Command:

```powershell
python -m pytest -q tests/unit/test_asset_quality_preview_evidence.py tests/unit/test_asset_quality_diagnostics.py tests/unit/test_asset_quality_generation_steering.py
```

Current result:

```text
4 failed, 46 passed
```

Current failures are concentrated in `tests/unit/test_asset_quality_diagnostics.py`:

- payload shape now includes `render_class_validators` and `repair_routes`;
- metrics now include additional visual/surface metrics beyond the original expected set;
- the synthetic clean baseline emits renderer-unavailable warnings;
- all-warning finding assertions now see extra renderer/classifier-related findings.

#### Likely diagnosis

This looks like a contract drift problem, not necessarily a runtime bug. The implementation appears to have grown richer diagnostics, but the tests still assert a narrower v1 payload and a "clean baseline" that lacks renderer evidence now considered mandatory.

The fix must answer two questions:

1. Are `render_class_validators`, `repair_routes`, and the extra metrics intended public diagnostic payload fields?
2. Should missing renderer output be a warning for otherwise clean synthetic runtime data, or should synthetic tests explicitly provide renderer evidence?

#### Required approach

Do not simply delete assertions. Reconcile the test contract with the intended diagnostics contract:

- If the new fields are intended, update the diagnostics spec/docs and tests together.
- If the new fields are internal, keep them out of the public diagnostic payload or nest them under a clearly versioned extension field.
- If renderer-unavailable warnings are intended, update the clean fixture to include renderer evidence.
- If renderer-unavailable warnings are too noisy for synthetic clean baselines, adjust the implementation to distinguish "not applicable in test/minimal runtime" from "requested preview evidence missing in a real build."

#### Files and docs to inspect

- `lathe/asset_quality/diagnostics.py`
- `lathe/asset_quality/preview_evidence.py`
- `docs/asset-quality/quality-diagnostics-v1.md`
- `docs/asset-quality/preview-evidence-v1.md`
- `tests/unit/test_asset_quality_diagnostics.py`
- `tests/unit/test_asset_quality_preview_evidence.py`

#### Acceptance criteria

- The diagnostics payload has an explicit stable shape.
- New diagnostic fields are either documented public fields or explicitly internal.
- Renderer-unavailable warnings fire for real missing evidence, not for synthetic fixtures that are meant to model complete evidence.
- Every warning has a paired recommendation and, where applicable, a repair route.

#### Verification

Run:

```powershell
python -m pytest -q tests/unit/test_asset_quality_preview_evidence.py tests/unit/test_asset_quality_diagnostics.py tests/unit/test_asset_quality_generation_steering.py
```

After the targeted lane passes, run the related validation/reporting lane:

```powershell
python -m pytest -q tests/unit/test_asset_quality_baseline_report_shape.py tests/unit/test_quality_gate_wiring.py
```

### 3.4 ShapeIR Op-set Tests

#### Current evidence

Command:

```powershell
python -m pytest -q tests/unit/test_geometry_kernel.py tests/unit/test_shape_ir_v2.py tests/unit/test_asset_quality_grammar_lowering.py
```

Current result:

```text
1 failed, 59 passed
```

Failure:

```text
test_all_ops_is_union_of_families_with_current_count
```

Observed drift:

- `ALL_OPS` includes `op.material_zone`;
- `ALL_OPS` includes `op.wear_zone`;
- `ALL_OPS` includes `op.decal_zone`;
- the test union omits the zone op family.

#### Likely diagnosis

The op registry grew a zone-family concept, but the test's family union/count assertion was not updated. This may be a straightforward stale-test fix if the zone ops are intentional and documented. It is not safe to assume that without checking the source definitions and grammar-lowering behavior.

#### Required approach

1. Inspect the ShapeIR v2 op-family definitions and confirm whether zone ops are intended first-class operations.
2. If intentional, update the test to include the zone family and the correct count.
3. If accidental, remove zone ops from `ALL_OPS` and ensure no lowering path emits them.
4. Add or update a small test that validates one representative zone op if the family is retained.

#### Files and docs to inspect

- `lathe/asset_quality/shape_ir_v2.py`
- `lathe/asset_quality/grammar_lowering.py`
- `docs/asset-quality/semantic-construction-graph.md`
- `docs/asset-quality/material-wear-graph-v1.md`
- `tests/unit/test_shape_ir_v2.py`
- `tests/unit/test_asset_quality_grammar_lowering.py`

#### Acceptance criteria

- `ALL_OPS` is exactly the union of all intended op families.
- The family count assertion reflects the source contract.
- Zone ops are either documented and validated or removed from the supported op set.
- No public `.lth` syntax changes are introduced.

#### Verification

Run:

```powershell
python -m pytest -q tests/unit/test_shape_ir_v2.py tests/unit/test_asset_quality_grammar_lowering.py tests/unit/test_geometry_kernel.py
```

## 4. P0 Workstream B: Rebuild One Wedge Asset To Evidence

### 4.1 Objective

Produce a fresh, inspectable evidence bundle for one wedge asset, preferably:

```text
examples/industrial_crate.lth -> industrial_crate
```

Guardrail asset:

```text
examples/mechanical_door.lth -> mechanical_door
```

The purpose is not to claim the asset is visually fixed. The purpose is to establish a current, reproducible truth baseline from `.lth` source through package/export evidence.

### 4.2 Required evidence inventory

For the wedge asset, record these paths in `docs/asset-quality/visible-geometry-sprint-0-evidence.md` or a dated child section linked from it:

| Evidence class | Required path or status |
|---|---|
| Source fixture | `.lth` source path and asset name |
| Command transcript | exact command, interpreter, exit code, and date |
| Output directory | deterministic output root |
| Shape bundle | shape-stage bundle path or explicit missing status |
| Topology bundle | topology-stage bundle path or explicit skipped/fallback status |
| UV bundle | UV-stage bundle path or explicit skipped/fallback status |
| Surface evidence | maps, manifest, control pack, or explicit proxy/missing status |
| Validation report | validation report path and pass/warn/fail summary |
| Package manifest | package manifest path |
| Export artifact | GLB/USD/engine manifest paths if produced |
| Preview evidence | final beauty/material-ID/wireframe/turntable paths or explicit renderer-unavailable/proxy status |
| Attempted-vs-actual trace | provider/kernel/renderer/topology/UV/package attempts and actuals |

### 4.3 Recommended output roots

Use a new dated evidence directory under `.tmp_tests/`:

```text
.tmp_tests/p0_wedge_industrial_crate_2026_05_13/
.tmp_tests/p0_wedge_mechanical_door_2026_05_13/
```

If the run is repeated, add a short suffix:

```text
.tmp_tests/p0_wedge_industrial_crate_2026_05_13_r2/
```

Do not overwrite prior evidence unless the previous directory was created in the same task and is known disposable.

### 4.4 Command sequence

Start with environment and source checks:

```powershell
git status --short
python -m lathe.cli doctor
python -m lathe.cli check examples/industrial_crate.lth
python -m lathe.cli check examples/mechanical_door.lth
```

Build the wedge:

```powershell
python -m lathe.cli build examples/industrial_crate.lth industrial_crate --out .tmp_tests/p0_wedge_industrial_crate_2026_05_13 --deterministic
```

Build the guardrail:

```powershell
python -m lathe.cli build examples/mechanical_door.lth mechanical_door --out .tmp_tests/p0_wedge_mechanical_door_2026_05_13 --deterministic
```

If a build hangs, fails, or cannot find an optional renderer/backend, record the exact blocker and inspect emitted artifacts before rerunning. Do not convert a partial output into a success claim.

### 4.5 Evidence interpretation

Classify each result as one of:

- `real`: visible in mesh/material/preview/export evidence;
- `proxy`: deterministic placeholder, explicitly labeled;
- `fallback`: attempted path degraded to another path, with reason;
- `unsupported`: rejected or warned before false success;
- `not verified`: code exists but no current artifact was produced;
- `blocked`: dependency or upstream condition missing.

### 4.6 Acceptance criteria

- The wedge build command exits `0`, or the blocker is recorded with exact failure text.
- Every required artifact path is recorded or explicitly labeled missing/proxy/fallback/blocked.
- The guardrail check/build proves the path is not crate-only, or records the blocking difference.
- No visual-improvement language appears without preview/export evidence.

### 4.7 Verification

After builds:

```powershell
python -m pytest -q tests/unit/test_asset_quality_preview_evidence.py tests/unit/test_asset_quality_diagnostics.py
```

Then inspect the generated `stages/validate/report.json` and package manifest before writing any final claim.

## 5. P0 Workstream C: Private Path Leaks And Examples Catalog

This overlaps with docs-static, but it deserves explicit handling because it affects public trust.

### 5.1 Private path leak policy

Public docs must use:

- repo-relative paths, for example `docs/...` or `examples/...`;
- generic placeholders like `<repo-root>`;
- artifact-root placeholders like `<out-dir>`;
- relative evidence paths under `.tmp_tests/...` when local evidence is intentionally disposable.

Public docs must not include:

- local drive-root checkout paths;
- private user-home paths;
- assistant or tool cache paths;
- absolute paths to previous worktrees;
- copied shell transcripts that expose private local state.

### 5.2 Examples catalog policy

Every checked-in `examples/**/*.lth` file must appear in `docs/examples_catalog.md`.

Each new catalog row should include:

- path;
- asset or demo name;
- mode or purpose;
- whether the example is canonical, experimental, or demo-only;
- the minimal check/build command if it is meant to be runnable;
- any known blocker if it is checked in but not currently buildable.

Do not add examples to the catalog as if they are certified unless they have current build/evidence proof.

### 5.3 Internal implementation reference policy

User-facing docs should describe stable public concepts:

- shape stage;
- package stage;
- preview evidence;
- stable handoff contract;
- CLI command;
- artifact path;
- diagnostic ID;
- repair route.

Implementation module names belong in architecture, API, or ADR docs. If a user-facing evidence doc needs to explain where code changed, prefer file-path references to source files only when the doc is explicitly an engineering evidence log.

### 5.4 Acceptance criteria

- No public markdown contains private local paths.
- Every checked-in `.lth` example is cataloged.
- User-facing docs do not depend on private implementation imports.
- Docs-static audit passes.

## 6. P1 Workstream D: Split Largest Core Modules Behind Existing Contracts

### 6.1 Objective

Reduce risk in the largest, highest-churn modules without changing public behavior.

This is not a rewrite. It is a contract-preserving decomposition so future asset-quality work can land without turning every change into a cross-file hazard.

### 6.2 Candidate modules

The audit measured these as high-priority split candidates:

| File | Current concern | Split direction |
|---|---|---|
| `lathe/asset_quality/shape_ir_v2.py` | very large semantic op model and validation surface | separate op families, dataclasses, validation, serialization, and compatibility exports |
| `lathe/assembly_kernel.py` | very large assembly/fixture construction surface | separate generic primitives, recipe dispatch, hard-surface helpers, and compatibility shim |
| `lathe/surface_runtime.py` | broad surface execution responsibilities | separate manifest assembly, map generation, proxy/fallback reporting, and material-zone handling |
| `lathe/executor.py` | stage orchestration and artifact writing pressure | preserve public executor behavior while extracting stage-specific helpers where already stable |

### 6.3 Contract-preserving split pattern

For each module:

1. Inventory imports and public names.
2. Identify public re-export names that tests or callers depend on.
3. Create small internal modules for cohesive responsibilities.
4. Keep the original module as a compatibility facade until call sites are migrated.
5. Move tests only after behavior is proven unchanged.
6. Run import/public-surface tests after each split.

### 6.4 Example split plan: ShapeIR v2

Proposed internal structure:

```text
lathe/asset_quality/shape_ir_v2.py          # compatibility facade
lathe/asset_quality/shape_ir_v2_types.py    # dataclasses and version constants
lathe/asset_quality/shape_ir_v2_ops.py      # op family frozensets and ALL_OPS
lathe/asset_quality/shape_ir_v2_validate.py # validation and diagnostics
lathe/asset_quality/shape_ir_v2_io.py       # to/from dict serialization helpers
```

Acceptance criteria:

- Existing imports from `lathe.asset_quality.shape_ir_v2` still work.
- `tests/unit/test_shape_ir_v2.py` passes before and after call-site migration.
- No public `.lth` behavior changes.
- Op-family docs stay synchronized with source.

### 6.5 Example split plan: Assembly kernel

Proposed internal structure:

```text
lathe/assembly_kernel.py             # compatibility facade
lathe/assembly/primitives.py         # generic primitive construction helpers
lathe/assembly/recipes.py            # asset-class/tag/role recipe dispatch
lathe/assembly/hardsurface.py        # hard-surface operations and fixtures
lathe/assembly/provenance.py         # semantic IDs, material zones, trace helpers
```

Acceptance criteria:

- Existing imports from `lathe.assembly_kernel` still work.
- Dispatch moves toward asset-class/tag/component-role logic rather than family-name-only branches.
- Industrial crate and mechanical door checks still pass.
- Stable shape handoff remains unchanged except additive evidence metadata.

### 6.6 Verification ladder

After each extraction:

```powershell
python -m pytest -q tests/unit/test_public_surface.py
python -m pytest -q tests/unit/test_shape_ir_v2.py
python -m pytest -q tests/contract/test_shape_handoff_v1.py
python -m pytest -q tests/unit/test_geometry_kernel.py tests/unit/test_asset_quality_grammar_lowering.py
```

After the full split:

```powershell
ruff check .
python -m pytest -q
```

If the full suite is too slow or blocked, report exactly what was not run and why.

## 7. P1 Workstream E: Supported Python 3.11/3.12 Matrix From Clean Checkout

### 7.1 Objective

Prove that the repository works on the supported Python versions advertised by `pyproject.toml`:

- Python 3.11
- Python 3.12

The current local environment also has newer Python interpreters available in some shells, but that is not enough. The release-support claim must be proven on the advertised matrix.

### 7.2 Clean checkout standard

A clean matrix run must start from one of:

- a fresh clone;
- a fresh `git worktree`;
- a confirmed clean branch with no unrelated tracked or untracked files.

Minimum preflight:

```powershell
git status --short
python --version
python -m pip --version
```

Expected checkout state:

```text
git status --short
```

prints nothing, except for intentionally ignored local virtualenv/cache directories.

### 7.3 Matrix setup

For each interpreter:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e .[dev]
```

If the repo-standard workflow uses `uv` in the chosen clean checkout, the equivalent is acceptable, but the final report must state the exact command used.

### 7.4 Matrix command ladder

Run this ladder for Python 3.11 and Python 3.12 separately:

```powershell
python -m lathe.cli doctor
python -m lathe.cli check examples/industrial_crate.lth
python -m lathe.cli check examples/mechanical_door.lth
ruff check .
python -m pytest -q tests/unit/test_docs_static_audit.py
python -m pytest -q tests/unit/test_asset_quality_preview_evidence.py tests/unit/test_asset_quality_diagnostics.py tests/unit/test_asset_quality_generation_steering.py
python -m pytest -q tests/unit/test_shape_ir_v2.py tests/unit/test_asset_quality_grammar_lowering.py tests/unit/test_geometry_kernel.py
python -m pytest -q tests/contract/test_shape_handoff_v1.py
```

After the targeted ladder is green, run:

```powershell
python -m pytest -q
```

Release-adjacent checks:

```powershell
python scripts/check_release_metadata.py
mkdocs build --strict
python -m build
twine check dist/*
```

Only run the release-adjacent checks after the P0 gates are green. Otherwise they will mostly restate known failure.

### 7.5 Matrix report format

Record results in a table:

| Python | OS/shell | Command | Result | Notes |
|---|---|---|---|---|
| 3.11 |  | `python -m lathe.cli doctor` | PASS/FAIL/SKIP |  |
| 3.11 |  | `ruff check .` | PASS/FAIL/SKIP |  |
| 3.11 |  | targeted pytest lanes | PASS/FAIL/SKIP |  |
| 3.11 |  | full pytest | PASS/FAIL/SKIP |  |
| 3.12 |  | `python -m lathe.cli doctor` | PASS/FAIL/SKIP |  |
| 3.12 |  | `ruff check .` | PASS/FAIL/SKIP |  |
| 3.12 |  | targeted pytest lanes | PASS/FAIL/SKIP |  |
| 3.12 |  | full pytest | PASS/FAIL/SKIP |  |

For every `FAIL`, include:

- exact failing test or command;
- first relevant error line;
- whether the failure is repo behavior, missing environment dependency, or external tool availability.

For every `SKIP`, include:

- skip reason;
- whether the skip is expected by marker/capability policy;
- what evidence would turn it into a pass.

## 8. Recommended Sequence

Do the work in this order:

1. Freeze and classify the worktree state.
2. Fix docs-static private path leaks and examples catalog drift.
3. Fix ShapeIR op-set drift.
4. Reconcile asset-quality diagnostics payload/tests.
5. Clear Ruff in the intended source set.
6. Rebuild `industrial_crate` and `mechanical_door` evidence.
7. Run the Python 3.11/3.12 clean-checkout matrix.
8. Start module decomposition only after P0 gates are green, unless a P0 fix requires a small extraction.

Reason: documentation leaks and stale test contracts are cheaper to fix first, while module decomposition multiplies merge and regression risk if done before the current gates are back to green.

## 9. Ownership Checklist

Use this checklist to track completion.

### P0: Red gates

- [ ] Classify Ruff failures by tracked source, tracked tests, docs, untracked scratch, and generated artifacts.
- [ ] Apply safe Ruff fixes and review diff.
- [ ] Manually fix semantic Ruff failures.
- [ ] Run `ruff check .`.
- [ ] Remove public-doc private path leaks.
- [ ] Reconcile `docs/examples_catalog.md`.
- [ ] Remove or relocate user-facing internal implementation references.
- [ ] Run docs-static audit.
- [ ] Reconcile diagnostics payload contract.
- [ ] Run asset-quality diagnostics targeted lane.
- [ ] Reconcile ShapeIR op-family union/count.
- [ ] Run ShapeIR/geometry targeted lane.

### P0: Wedge evidence

- [ ] Record `git status --short`.
- [ ] Run `python -m lathe.cli doctor`.
- [ ] Check `industrial_crate`.
- [ ] Check `mechanical_door`.
- [ ] Build `industrial_crate` to a dated `.tmp_tests/` output.
- [ ] Build `mechanical_door` guardrail to a dated `.tmp_tests/` output.
- [ ] Record shape/topology/UV/surface/validate/package/export/preview paths.
- [ ] Label proxy/fallback/unsupported/blocked evidence explicitly.
- [ ] Update visible-geometry Sprint 0 evidence doc.

### P1: Module split

- [ ] Inventory imports and public names for each candidate module.
- [ ] Split ShapeIR v2 behind compatibility facade.
- [ ] Split assembly kernel behind compatibility facade.
- [ ] Preserve existing public imports.
- [ ] Run public surface and shape handoff contract tests after each split.

### P1: Supported matrix

- [ ] Create clean checkout or worktree.
- [ ] Run Python 3.11 ladder.
- [ ] Run Python 3.12 ladder.
- [ ] Record failures as repo, environment, or external dependency.
- [ ] Run full suite after targeted gates pass.
- [ ] Record exact pass/fail/skip/deselect counts.

## 10. Done Criteria

This plan is complete only when all of the following are true:

1. `ruff check .` passes from the intended source tree.
2. `tests/unit/test_docs_static_audit.py` passes.
3. Asset-quality diagnostics targeted tests pass.
4. ShapeIR/geometry targeted tests pass.
5. `industrial_crate` has current package/export/preview evidence or an exact blocker.
6. `mechanical_door` has current guardrail evidence or an exact blocker.
7. Python 3.11 and 3.12 clean-checkout targeted matrix results are recorded.
8. Any module split preserves old import paths and stable contracts.
9. The final report states exactly what was run, what passed, what failed, what skipped, and what remains unverified.

## 11. The One Thing

The highest-leverage outcome is not "fix many tests." It is this:

```text
A clean, supported-matrix, current evidence loop for industrial_crate:
.lth source -> deterministic build -> artifact paths -> validation report -> package/export/preview evidence -> honest pass/fallback/blocked labels.
```

Once that loop is green and repeatable, the rest of the visible-geometry work has a trustworthy base. Without it, new geometry or diagnostics work will keep adding surface area to a checkout whose claims cannot yet be audited cleanly.
