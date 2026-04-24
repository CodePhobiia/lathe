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

### BL-26. Coverage gate lift

- **Scope:** once BL-20..BL-25 land, flip `.coveragerc` / `pyproject.toml` coverage `fail_under = 85`. Enable ruff `BLE001` and `S101` as hard rules.
- **Effort:** 0.25 day.

## P2 — Plan 02 docs content (owned track)

### BL-27. Tutorial ladder

- **Scope:** Plan 02 Phase 5 — `docs/quickstart.md` (fully fleshed), `docs/tutorial/first_asset.md`, `docs/tutorial/second_asset_reconstruct.md`, `docs/tutorial/deep_dive.md`.
- **Effort:** 2 days.

### BL-28. Cookbook

- **Scope:** Plan 02 Phase 8 — 13 runnable recipes under `docs/cookbook/`.
- **Effort:** 1.5 days.

### BL-29. stdlib doc blocks

- **Scope:** Plan 02 Phase 7 — `# doc:` comment block on each of the ~21 `.lth` files under `std/`. Auto-generated index via `docs/gen_stdlib_index.py`.
- **Effort:** 1.5 days.

### BL-30. Inline docstring sweep

- **Scope:** Plan 02 Phase 9 — Google-style docstrings on every public symbol. Enable ruff `D` rules.
- **Effort:** 1 day.

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
