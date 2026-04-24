# Wave 4 Backlog

Extends Wave 3's backlog with items carried over + new tickets flagged by Wave 3 reviewers + the big content tracks that were intentionally deferred.

## P0 — finish Plan 01 exit criteria ✅ **Wave 4.I COMPLETE**

### BL-17. `lathe/blender_execution.py` 567 LOC decomposition — **DONE** (`767b844`)

Landed as 24-LOC shim + 6-file `lathe/blender/` package (max 292 LOC). courier_drone 0.879435.

### BL-18. Explicit decision on `lathe/resolver.py` 540 LOC — **DONE** (`3174295`)

Path B chosen: ADR exception at `docs/adr/0007-resolver-loc-exception.md`. Re-evaluation criteria: >650 LOC, second orchestrator appears, external caller consumes private helpers, or namespace-map wiring >50% of file.

### BL-19. Schemas for trust-boundary JSON sites — **DONE** (`a1aee13`)

Audit surfaced only 1 trust-boundary site (`capabilities.py:425` Hunyuan probe). Migrated via new `lathe/validation.py` + `schema/hunyuan_probe.schema.json`. Zero TODO(security) markers remain.

### Minor carryover from Wave 4.I

`lathe/capabilities.py` grew 490 → 506 LOC (+16) during BL-19 when the validation-module imports landed. 6 LOC over Plan 01 cap. Options: trim by condensing the new imports, or accept as a second ADR exception. Defer to Wave 4.II cleanup pass.

## P1 — Plan 04 test backfill (owned track)

### BL-20. Tranche A — Geometry Core tests

- **Scope:** Plan 04 Phase 4 — `test_geometry_kernel.py`, `test_exact_solids.py`, `test_{mesh,solid,shape}_ir.py`, `test_mesh_finalize.py`, `test_asset_graph.py`, `test_assembly_kernel.py`, `test_assembly_ir.py`, `test_{feature,feature_grammar,feature_fusion}_ir.py`, `test_candidate_search.py`, `test_conformance.py`, `test_fidelity.py`, `test_scaffold_compiler.py`, `test_schema.py`, `test_utils.py`.
- **Acceptance:** each module ≥6 cases (happy/empty/malformed/boundary/large/failure); coverage ≥90%.
- **Effort:** 3 days.

### BL-21. Tranche B — Runtimes + Surface tests

- **Scope:** `test_topology_runtime.py`, `test_uv_runtime.py`, `test_surface_runtime.py`, `test_bake_runtime.py`, `test_shape_backend.py`, `test_materials.py`, `test_pbr_deriver.py`, `test_texture_control_pack.py`, `test_surface_ir.py`, `test_atlas_assembler.py`, `test_blender_execution.py` (mocked), `test_codex_imagegen_bridge.py` (mocked), `test_repair_planner.py`, `test_repair_executor.py`, `test_repair_policy.py`, `test_surface_repair.py`, `test_bench_runtime.py`, `test_test_runtime.py`.
- **Acceptance:** all ≥85% line coverage; exercise capability present/absent.
- **Effort:** 3 days.

### BL-22. Tranche C — V1.1/V1.2/V1.3 IRs + Validators tests

- **Scope:** Plan 04 Phase 6 modules.
- **Acceptance:** module-count coverage ≥95% (≥75 of 79).
- **Effort:** 2 days.

### BL-23. Property-based tests

- **Scope:** Plan 04 Phase 7 — geometry laws, transform algebra, parse/serialize round-trips, resolver commutativity, normalizer idempotence, grammar fuzz.
- **Effort:** 1.5 days.

### BL-24. Golden snapshot tests

- **Scope:** all 9 heroes snapshot-tested end-to-end via syrupy.
- **Effort:** 1 day.

### BL-25. Contract tests

- **Scope:** `tests/contract/test_shape_handoff_v1.py` pinning the field set of the stable contract.
- **Effort:** 0.5 day.

### BL-26. Coverage gate lift — **PARTIAL** (ratchet at 65%)

- Actual measured coverage after BL-20..BL-25: **69.66%** (line+branch). Below the 85% target.
- Ratchet gate set to **65%** in `.coveragerc` + `pyproject.toml` to prevent regression.
- Ruff `BLE001` + `S101` confirmed green on `lathe/` — no remaining violations after Waves 2.I/3.
- The 85% push is filed as BL-39 (below).

### BL-39. Push coverage from 69.66% to 85%+

- **Source:** BL-26 ratchet follow-up; Plan 04 Phase 10 error-path coverage.
- **Scope:** target modules below 70% line+branch coverage today:
  - `lathe/validation.py` (51%)
  - `lathe/executor.py`, `lathe/core/stages/*.py` — orchestration branch coverage
  - Provider fallback paths not exercised by native-only tests
  - Error-path coverage per Plan 04 Phase 10 (CLI subcommands, parser errors, checker rejections, resolver UnresolvedName, runtime_config malformed inputs)
- **Acceptance:** `pytest --cov=lathe --cov-fail-under=85` green; lift ratchet to 85% in both `.coveragerc` and `pyproject.toml`.
- **Effort:** 2–3 days.

## P2 — Plan 02 docs content ✅ **Wave 4.III COMPLETE**

### BL-27. Tutorial ladder — **DONE** (`fffb636`)

docs/quickstart.md (replaced Wave 1 placeholder, 60-sec path) + docs/tutorial/first_asset.md (~15-min bookshelf walkthrough, 9 steps) + docs/tutorial/second_asset_reconstruct.md (~20-min reconstruct flow over reconstruct_courier_from_views.lth) + docs/tutorial/deep_dive.md (manifesto→PRD→spec reading map) + examples/tutorial_bookshelf.lth (parses clean, lathe check ok).

### BL-28. Cookbook — **DONE** (`235074c`)

14 files under docs/cookbook/: 10 primary recipes (generate, reconstruct, kit_assembly, mobile_adapt, surface_control, variant_patching, custom_backend, runtime_config, certification_debug, blender_bridge) + 3 reference pages (runtime_config_schema, reading_a_trace, per_validator) + landing index.

### BL-29. stdlib doc blocks — **DONE** (`3732320`)

30 `.lth` files under std/ (not 21 — reviewer-docs count was wrong) each gained a leading `// doc:` block with purpose/exports/depends_on/used_by/stability/layer. All 30 parse clean; docs/gen_stdlib_index.py hook verified via local replica.

### BL-30. Inline docstring sweep — **DONE** (`bfc33e5`)

103 files under lathe/ touched. 78 module-level docstrings + 395 Google-style public-symbol docstrings. Ruff D100/D101/D102/D103/D205/D400 on priority list: **440 → 0**. 102 residual violations in non-priority modules (scaffolds, adapters, transport, a handful of runtimes) flagged for follow-up. Pytest 742/742 preserved.

### Minor carryover from Wave 4.III

- `mkdocs-material` not installed in `.venv`; `mkdocs build --strict` was not run during Wave 4.III. Install + verify in Wave 5 tooling track.
- `mkdocs.yml` nav entries for new tutorials/cookbook not added (reachable via existing index files). Wave 5 nav sweep.
- Ruff D104 (public package) ×9 + D107 (public `__init__`) ×9 residual — next docstring pass.

## P3 — Plan 08 product quality (Wave 4 anchor)

### BL-31. Publish runner

- **Scope:** Plan 08 Phase 1. `lathe/publish.py` + drivers (local_fs, s3 optional, supabase, git_lfs). Manifest, signing, CLI.
- **Effort:** 1.0 week.

### BL-32. Canonical formatter (`lathe fmt`)

- **Scope:** Plan 08 Phase 2. Lark-tree reformatter; idempotent; preserves comments.
- **Effort:** 0.8 week.

### BL-33. Autonomous repair loop

- **Scope:** Plan 08 Phase 3. Multi-round validate → classify → choose → rebuild with stop conditions.
- **Effort:** 1.0 week.

### BL-34. Second backend stack (`soft_surface_prop_v1`)

- **Scope:** Plan 08 Phase 4 + Plan 03 Phase 6b. Two-stage swap (subdivision topology + soft-padding UV) + new silhouette validator. Proof of the plugin model.
- **Effort:** 2 weeks.

### BL-35. Hero gallery + benchmark scoreboard

- **Scope:** Plan 08 Phases 5, 5b. `scripts/render_gallery.py` + `docs/gallery/<asset>/*` + `docs/benchmarks/scoreboard.md` auto-generated.
- **Effort:** 0.7 week.

### BL-36. User-friendly validator reports + artifact viewer + CLI error polish

- **Scope:** Plan 08 Phases 6, 7. Rich terminal + HTML reports; `lathe inspect --view` + `lathe serve <build_dir>` with vendored `<model-viewer>`; every CLI raise-site gets an error_code.
- **Effort:** 1.1 week.

### BL-37. Strict-mode default flip

- **Scope:** Plan 08 Phase 8. Flip the default learned-provider fallback policy to strict in V0.2 (landed with DeprecationWarning in V0.1.x).
- **Effort:** 0.3 week.

### BL-38. Playground + stability + performance

- **Scope:** Plan 08 Phases 9, 10, 12. Pyodide-based playground; fuzz harness; perf budgets per stage.
- **Effort:** 2.5 weeks.

## Rough Wave 4 shape

**Wave 4.I — finishing the refactor (3 days):** BL-17, BL-18, BL-19.
**Wave 4.II — test backfill track (8 days, parallelizable):** BL-20..BL-26.
**Wave 4.III — docs content track (6 days, parallelizable with II):** BL-27..BL-30.
**Wave 4.IV — product quality track (9-10 weeks if sequential):** BL-31..BL-38.

Plus periodic reviewer stages same as Wave 2/3 pattern.

Total Wave 4 effort: ~12-14 engineer-weeks. Should be broken into multiple sub-waves.

## Not in scope yet

- Plan 03 Phases 2 (plugin registry), 3 (layering enforcement), 4 (ADR practice beyond the resolver one in BL-18), 5 (validator composition), 6b (deep proof stack via BL-34). Wave 5+.
- Plan 05 Phases 5 (doctor upgrades), 6 (shell completion), 7 (LSP + VS Code extension), 9b (CLI flags). Wave 4+ DX track.
- Plan 06 Phase 6 (community seeding). Post-V0.2 launch.
- Plan 09 entire GTM plan. Post-V0.5.
