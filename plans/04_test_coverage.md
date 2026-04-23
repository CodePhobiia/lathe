# Implementation Plan: Test Coverage 4/10 → 10/10

## Overview

Lift from 16 smoke tests (~1,447 test LOC vs ~17,061 source LOC ≈ 1:12 ratio, ~26% module coverage, zero coverage on ~30 critical modules) to a defense-in-depth suite: 85%+ line coverage enforced by CI, property-based tests for geometry cores, golden snapshots for hero examples, mocks for all external services, and cold-clone `pytest -q` passing in under 2 minutes.

## Requirements

- `pytest -q` green from fresh clone after `pip install -e .[dev]` (no optional extras)
- 85%+ line coverage, 75%+ branch coverage, enforced in CI
- Every module in `lathe/` has at least one targeted unit test
- Every external dep (Blender, xatlas, Hunyuan, VGGT, Codex ImageGen) mockable via fixture
- `lathe.shape.intent_mesh_handoff_v1` pinned by contract tests
- Golden snapshots for all hero examples; PRs fail on unexplained drift

## Architecture Changes

- `pyproject.toml`: add `pytest-cov`, `hypothesis`, `syrupy`, `mutmut` to `dev`; add `test-min` extra
- `.coveragerc`: source paths, omit scaffolds/__init__, branch=True, fail_under=85
- `tests/conftest.py`: shared fixtures
- `tests/fixtures/`: mock Hunyuan, fake Blender, fake xatlas, fake VGGT, fake Codex ImageGen
- `tests/golden/`: canonical bundle snapshots per hero
- `tests/{unit,integration,contract,property}/`: taxonomy
- `requirements-lock.txt`: hash-pinned lockfile via `pip-compile`
- `.github/workflows/test.yml`: matrix CI with coverage gate

---

## Phase 1 — Cold-Clone Green (1 day)

**Goal:** `pytest -q` passes after `pip install -e .[dev]` with no optional deps.

1. **Fix dev extras** in `pyproject.toml`: add `trimesh`, `numpy`, `Pillow` explicitly; add `pytest-cov>=5`, `hypothesis>=6.100`, `syrupy>=4`, `mutmut>=2.5`, `pip-tools`. Add `test-min` extra (no optional deps).
2. **Lockfile** at `requirements-lock.txt` via `pip-compile --extra dev --generate-hashes pyproject.toml`. Update bootstrap scripts to prefer lockfile.
3. **Skip-markers** in `tests/conftest.py`: `requires_blender`, `requires_xatlas`, `requires_torch`, `requires_network`. Auto-skip when absent; CI `full` matrix asserts no mark-skip.

**Acceptance:**
- [ ] Fresh clone + `pip install -e .[dev]` + `pytest -q` passes in <120s
- [ ] `pip install -e .[test-min] && pytest -q -m "not requires_blender and not requires_xatlas and not requires_torch"` passes

---

## Phase 2 — Coverage Tooling + CI Gate (0.5 day)

1. **`.coveragerc`**: `source = lathe`, `branch = True`, omit `lathe/scaffolds/*` (hard-coded reference scaffolds — `chest.py`, `drone.py`, `wall_panel.py`), `lathe/__init__.py`. Do **not** omit `lathe/lsp/*` — it's an active package with real code. `fail_under = 85`; term-missing + xml + html.
2. **pytest addopts** (behind env toggle): `--cov=lathe --cov-branch --cov-report=term-missing --cov-fail-under=85`.
3. **`.github/workflows/test.yml`**: matrix `python: [3.11, 3.12, 3.13] × deps: [min, full]`. Full installs `.[dev,xatlas,geometry,export]` + coverage gate + Codecov upload. Min asserts smoke + conservative path.

---

## Phase 3 — Test Taxonomy + Fixtures (1 day)

Reorganize `tests/` into `unit/`, `integration/`, `contract/`, `property/`, `golden/`.

**Fixtures** in `tests/fixtures/`:
- `mock_hunyuan.py` — extracted `hunyuan_server` fixture
- `mock_vggt.py` — deterministic point-cloud generator, no torch
- `mock_blender.py` — stub `blender_execution.run_plan` returning canned bundle
- `mock_xatlas.py` — monkeypatch `xatlas.parametrize` with deterministic UV
- `mock_codex_imagegen.py` — stub bridge with seeded PNG fixtures
- `sample_programs.py` — pre-parsed hero ASTs

---

## Phase 4 — Zero-Coverage Backfill — Tranche A: Geometry Core (3 days)

Highest-risk, deterministic, no external deps. New files under `tests/unit/`:

1. `test_geometry_kernel.py` — CSG ops, tolerance edges, degenerate inputs, winding order
2. `test_exact_solids.py` — primitive construction, transforms, boolean identities
3. `test_mesh_ir.py`, `test_solid_ir.py`, `test_shape_ir.py` — serialization round-trips, invariants
4. `test_mesh_finalize.py` — weld thresholds, manifold repair, normal consistency
5. `test_asset_graph.py`, `test_assembly_kernel.py`, `test_assembly_ir.py` — graph construction, cycle detection, port compatibility
6. `test_feature_ir.py`, `test_feature_grammar.py`, `test_feature_fusion.py` — grammar fuzz, fusion determinism
7. `test_candidate_search.py`, `test_conformance.py`, `test_fidelity.py` — ranking stability, metric monotonicity
8. `test_scaffold_compiler.py` — hot-path code under stable `lathe.shape.intent_mesh_handoff_v1` contract; assembly-blueprint → ShapeIR transforms, deterministic seeding, scaffold resolution
9. `test_schema.py` — JSON-schema load + validate; normalized AST conformance (complement to `test_roundtrip.py`)
10. `test_utils.py` — shared helper functions; pure-function coverage

Each module: ≥6 cases (happy, empty, malformed, boundary, large, failure). Coverage ≥90%.

---

## Phase 5 — Tranche B: Runtimes + Surface (3 days)

Under `tests/unit/` and `tests/integration/`:

1. `test_topology_runtime.py` (with mock_blender + fallback)
2. `test_uv_runtime.py` (with mock_xatlas + fallback)
3. `test_surface_runtime.py`, `test_bake_runtime.py`
4. `test_shape_backend.py` — contract enforcement
5. `test_materials.py`, `test_pbr_deriver.py`, `test_texture_control_pack.py`, `test_surface_ir.py`, `test_atlas_assembler.py`
6. `test_blender_execution.py` (mocked)
7. `test_codex_imagegen_bridge.py` (mocked, fallback)
8. `test_repair_planner.py`, `test_repair_executor.py`, `test_repair_policy.py`, `test_surface_repair.py` — targets `lathe.repair.surface_repair` (subpackage under `lathe/repair/`, not top-level)
9. `test_bench_runtime.py`, `test_test_runtime.py` — in-language test/benchmark runners driving `.lth`-declared `test`/`benchmark` blocks (complement to Phase 9b CI hooks)

All ≥85% line coverage; exercise "capability present" and "absent" paths.

---

## Phase 6 — Tranche C: V1.1/V1.2/V1.3 IRs + Validators (2 days)

1. `test_kit_ir.py`, `test_reuse_ir.py`, `test_transfer_ir.py`, `test_fit_ir.py`, `test_reference_ir.py`
2. `test_validators_semantic.py`, `test_validators_visual.py`, `test_validators_flow.py`, `test_validators_surface.py`, `test_validators_silhouette.py` — crafted bad bundles; assert fail reasons
3. `test_inspection_evidence.py`, `test_bridge_blender_plan.py` (targets `lathe.bridge.blender_plan` subpackage), `test_render_eval.py`, `test_eval_harness.py`, `test_capabilities.py`, `test_runtime_config.py`, `test_highlow.py`, `test_patch_api.py`, `test_proposals.py`, `test_defaults.py`

Module-count coverage ≥95% (75+/79).

---

## Phase 7 — Property-Based Tests (1.5 days)

Under `tests/property/`:

1. `test_geometry_kernel_properties.py` — boolean algebra laws (A∪A=A, A∩∅=∅, De Morgan), volume conservation under transform
2. `test_exact_solids_properties.py` — transform composition associativity, invertibility
3. `test_feature_grammar_properties.py` — parse/serialize round-trip, idempotent normalization
4. `test_shape_ir_properties.py` — serialize → deserialize preserves semantic hash
5. `test_resolver_properties.py` — `uses` chain commutativity on independent patches
6. `test_normalizer_properties.py` — idempotence (`normalize(normalize(ast)) == normalize(ast)`) and schema conformance (`jsonschema.validate(normalize(ast), lathe.schema.json)` holds for any parseable input)
7. `test_grammar_fuzz.py` — Hypothesis strategy derived from `grammar/lathe.lark` terminals; assert every generated source either parses cleanly or raises `LatheParseError`, never anything else (no uncaught exceptions, no silent empty returns)

≥7 property modules, ≥3 properties each, ≥200 examples per property. `.hypothesis/` DB cached by CI.

---

## Phase 8 — Golden (Snapshot) Tests (1 day)

`syrupy`. File: `tests/golden/test_hero_bundles.py`.

Heroes: `courier_drone`, `brassbound_chest`, `industrial_crate`, `mechanical_door`, `console_terminal`, `sci_fi_wall_panel`, `service_cabinet`, `control_pedestal`, `supply_container`.

Per hero, snapshot: normalized AST JSON, build plan, shape bundle manifest (hashes only), topology/UV manifests, validator report, package manifest. Under `tests/golden/__snapshots__/`.

**Snapshot determinism rules.** Before hashing or comparison, normalization strips:
(a) all timestamps (ISO-8601, epoch, `build_time_ms`, `duration_*`, etc.);
(b) absolute paths — replace repo root with `$REPO`, temp/work dirs with `$WORK`;
(c) provider probe latency fields (`latency_ms`, `probe_*_ms`, `elapsed`, `rtt`);
(d) Python `__repr__` object ids (`0x[0-9a-f]+` sequences, `at 0x...` fragments).

Implementation lives in `tests/golden/_normalize.py` as a single `normalize(obj) -> obj` helper; all golden tests route output through it before snapshotting. Add a unit test for `_normalize` itself asserting each stripping rule is idempotent.

PR that changes any snapshot must show explicit diff; `docs/` contains update procedure.

---

## Phase 9 — Contract Tests (0.5 day)

`tests/contract/test_shape_handoff_v1.py`:
- Pin exact field set, types, semantics of `intent_mesh_handoff_v1`
- Every registered shape provider produces conforming bundle
- Validator interface: `validators/*.py` each expose `run(bundle) -> ValidationReport`
- Every ID in `backends.py` resolves and round-trips

Contract tests fail loudly with contract-ID in message on drift.

---

## Phase 9b — In-Language Test Runners (0.5 day)

Orthogonal to pytest: exercise the `.lth` authoring layer (V0.8+) by running Lathe's own in-language `test` / `benchmark` declarations as part of CI.

1. CI step: `python -m lathe.cli test examples/*.lth` — executes every `test` block declared in hero and stdlib `.lth` sources; non-zero exit fails CI.
2. CI step: `python -m lathe.cli bench examples/*.lth` — runs `benchmark` blocks with a budget cap so CI doesn't hang on long benches; record perf numbers as build artifacts (non-gating initially).
3. Wire into `.github/workflows/test.yml` as a separate job `lathe-lang-tests` that depends on the `full` matrix passing.
4. Pytest companion `tests/integration/test_in_language_runners.py` asserts the CLI entry points (`bench_runtime`, `test_runtime`) dispatch correctly and surface failures as non-zero exits.

This covers authoring-layer regressions that pytest-level tests cannot see.

---

## Phase 10 — Error-Path + CLI Coverage (1 day)

1. `test_cli.py` — every subcommand: doctor/check/plan/materialize/build/test/bench/inspect/export-blend/inspect-blend/bridge doctor/bridge plan; `--help`, invalid args, missing files, malformed `.lth`
2. `test_parser_errors.py` — each grammar error path
3. `test_checker_errors.py` — each semantic rule rejection
4. `test_resolver_errors.py` — cyclic `uses`, missing profile, conflicting variants
5. `tests/integration/test_runtime_config_errors.py` — malformed runtime JSON, unavailable provider fallback

Every `raise` site in parser/checker/resolver/CLI has a triggering test. Branch coverage ≥75%.

---

## Phase 11 — Mutation Testing + Final Gate (1 day)

1. `mutmut` (or `cosmic-ray`) on `lathe/geometry_kernel.py`, `exact_solids.py`, `checker.py`, `resolver.py`, `conformance.py`
2. CI nightly (non-blocking initially); target ≥70% mutation score
3. `docs/testing.md` onboarding doc + README badge

---

## Risks & Mitigations

- **Golden snapshot churn** → snapshot hashes/manifests, not raw geometry; documented update flow
- **Hypothesis slow in CI** → separate `property` mark; reduced example budget in PR CI, full budget nightly
- **Mocked Blender drift** → nightly job with real Blender asserts mock-vs-real equivalence on one hero
- **Coverage gate drudgery** → 85% not 100%; exempt scaffolds; per-file `# pragma: no cover` allowed

---

## 10/10 Success Criteria

- [ ] Cold-clone `pip install -e .[dev] && pytest -q` green in <120s
- [ ] Cold-clone `pip install -e .[test-min] && pytest -q -m "not requires_blender and not requires_xatlas and not requires_torch"` green
- [ ] Line coverage ≥85%, branch coverage ≥75%, enforced in CI
- [ ] Module-level coverage ≥95% (≥75 of 79 modules targeted)
- [ ] Test-to-source LOC ratio ≥1:3.4 (~5,000 test LOC vs ~17,061 source)
- [ ] All 9 hero examples under golden snapshot
- [ ] Mutation score ≥70% on geometry + checker + resolver + conformance
- [ ] Contract tests for `intent_mesh_handoff_v1` + validator interface
- [ ] CI matrix: 3 Python × 2 dep profiles, all green
- [ ] Zero `TODO`/`xfail` in contract or golden suites

**Total effort: ~18–20 working days (≈4 weeks).** Phases 4–6 (geometry + runtimes + V1.1/V1.2/V1.3 IRs and validators) and Phase 10 (error-path + CLI) were originally under-budgeted — Phase 4 needs 4 days, Phase 5 needs 4 days, Phase 6 needs 3 days, Phase 10 needs 1.5–2 days. Add 0.5 day for Phase 9b.

---

## Relevant paths

- `pyproject.toml`
- `tests/` (16 existing, to be reorganized)
- `lathe/` (79 modules, ~17,061 LOC — coverage targets)
- `lathe/repair/surface_repair.py` (subpackage — not top-level)
- `lathe/bridge/blender_plan.py` (subpackage — not top-level)
- `lathe/scaffolds/` (correct coverage-omit target)
- `scripts/bootstrap_local.{sh,ps1}`

---

## Amendment log (2026-04-23)

Applied review `plans/reviews/04_test_coverage_review.md` plus meta-review cross-cutters:

- Corrected source-LOC baseline `15,663 → ~17,061` throughout (Overview, test-to-source ratio in 10/10 criteria, Relevant paths). Ratio recomputed: ~5,000 test LOC against ~17,061 source ≈ **1:3.4** (was stated as 1:3).
- Fixed subpackage paths: `test_surface_repair.py` now explicitly targets `lathe.repair.surface_repair` (under `lathe/repair/`, not top-level); `test_bridge_blender_plan.py` now explicitly targets `lathe.bridge.blender_plan`.
- Swapped Phase 2 `.coveragerc` omit: removed `lathe/lsp/*` (active package with real code), added `lathe/scaffolds/*` (hard-coded reference scaffolds — `chest.py`, `drone.py`, `wall_panel.py`).
- Added `test_scaffold_compiler.py` to Tranche A (#8) — hot-path code under stable `lathe.shape.intent_mesh_handoff_v1` contract.
- Added missing modules:
  - Tranche A: `test_schema.py` (#9), `test_utils.py` (#10).
  - Tranche B: `test_bench_runtime.py`, `test_test_runtime.py` (#9) — in-language runners at the Python layer, complementing Phase 9b's CI-level coverage.
- Added normalizer + grammar fuzzing to Phase 7: `test_normalizer_properties.py` (idempotence + schema conformance) and `test_grammar_fuzz.py` (Hypothesis strategy derived from `grammar/lathe.lark` terminals; asserts parse-or-`LatheParseError` dichotomy, nothing else).
- Added new **Phase 9b — In-Language Test Runners (0.5 day)**: CI steps running `lathe test examples/*.lth` and `lathe bench examples/*.lth` to cover the `.lth` authoring layer (V0.8+). Orthogonal to pytest.
- Specified snapshot determinism rules in Phase 8: normalization strips timestamps, absolute paths (→ `$REPO`/`$WORK`), provider probe latency fields, and Python `__repr__` ids. Implemented in `tests/golden/_normalize.py` with its own idempotence unit test.
- Inflated effort estimate from `~15 working days` to `~18–20 working days (≈4 weeks)` with per-phase rationale (Phases 4–6 + 10 were tight; Phase 9b added 0.5 day).
