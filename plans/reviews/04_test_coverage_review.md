# Review: Plan 04 — Test Coverage

## Summary

Plan is structurally strong: it correctly identifies the cold-clone blocker, the missing coverage tooling, the zero-coverage hot spots, and the absence of external-service mocks. Phasing is sensible (unblock → gate → backfill → property → golden → contract → error-path → mutation). However, the plan has several small factual slips (wrong module paths, a non-existent excluded directory, stale source-LOC count) and is silent on a handful of real modules that aren't in the audit's zero-coverage list. Tool choices are defensible. 15 days is aggressive but plausible for a single focused contributor; 18-20 would be safer.

**Verdict: 8.5/10 as written. 10/10 with the fixes in "Gaps" below.**

## Coverage of findings (checklist)

| Finding | Addressed? | Where |
|---|---|---|
| 1,447 test LOC vs 15,663 source (1:10) | Yes | Success criteria: target 1:3 ratio (~5000 LOC) |
| 16 files covering ~21/79 modules (~26%) | Yes | Phase 4-6 backfill; ≥95% module-count target |
| "Build succeeded" smoke quality | Yes | Phase 7 property + Phase 8 golden + Phase 9 contract |
| Only `test_shape_providers.py` mocks externals | Yes | Phase 3 fixtures for Blender/xatlas/Hunyuan/VGGT/Codex |
| Cold clone fails (missing trimesh) | Yes | Phase 1 explicit dev extras + lockfile |
| ~30 zero-coverage modules enumerated | Yes | Phase 4-6 tranches; see accuracy notes |
| No coverage measurement/gate | Yes | Phase 2 `.coveragerc` + CI `--cov-fail-under=85` |
| Few edge-case/failure-path tests | Yes | Phase 10 error-path coverage; each raise site |

## Accuracy — verified citations

**Test-LOC count (confirmed):** `wc -l tests/*.py` → **1447 total** across 16 files. Match.

**Source-LOC (slightly stale):** Plan says 15,663. Actual `wc -l lathe/**/*.py` including `validators/`, `repair/`, `bridge/`, `scaffolds/` = **17,061**. The 1:3 target should be recomputed (~5,700 test LOC, not 5,000).

**79 modules:** Confirmed — `find lathe -name '*.py'` returns 79, but this includes `__init__.py` files and scaffold stubs. The "~21 modules tested" figure in the audit and plan undercount slightly because `test_language_v12.py:25-30` has smoke imports for `atlas_assembler`, `codex_imagegen_bridge`, `pbr_deriver`, `repair.surface_repair`, `texture_control_pack`, `validators.surface_quality` — these are *import smoke tests* (they verify the module loads) not real tests, but they contribute one line of "coverage" each.

**Zero-coverage list — spot-checked via grep for imports/usage in `tests/`:**

| Audit claim (zero coverage) | Confirmed? | Note |
|---|---|---|
| `geometry_kernel.py` | Confirmed | No direct tests; only indirectly via `build_asset` |
| `exact_solids.py` | Confirmed | Not imported in tests |
| `repair_executor/planner/policy.py` | Confirmed | No direct import |
| `surface_repair.py` | Partially | Audit says `surface_repair.py`; **actual path is `lathe/repair/surface_repair.py`**. Only covered by a noqa import smoke in `test_language_v12.py:28` |
| `assembly_ir/kernel.py` | Confirmed | Not imported |
| `feature_ir/grammar/fusion.py` | Confirmed | Not imported |
| `kit_ir/reuse_ir/transfer_ir.py` | Confirmed | Not imported (only field-read through shape bundles in `test_build.py`) |
| `topology_runtime/uv_runtime/surface_runtime/bake_runtime.py` | Confirmed | Indirect only |
| `mesh_finalize.py`, `shape_backend.py`, `candidate_search.py`, `conformance.py`, `fidelity.py` | Confirmed | Indirect only |
| `blender_execution.py` | Confirmed | One mock in `test_build.py:251` against `executor._run_blender_topology` but never directly imports `blender_execution` |
| `codex_imagegen_bridge.py` | Confirmed | Import smoke only |
| `materials.py`, `pbr_deriver.py`, `texture_control_pack.py`, `surface_ir.py` | Confirmed | Import smoke only |
| `validators/*` except `semantic_quality/visual_quality` | Confirmed | `flow_quality`, `surface_quality`, `silhouette` not directly tested |

**Modules the audit MISSED that are zero/near-zero coverage (plan should add):**

- `lathe/scaffold_compiler.py` — critical path in shape stage, not in audit, not in plan
- `lathe/mesh_ir.py`, `lathe/solid_ir.py` — plan does include these (Phase 4.3) but audit didn't
- `lathe/bridge/blender_plan.py` (179 LOC) — plan lists `test_bridge_blender_plan.py` (Phase 6.3) but the path in CLAUDE.md is `lathe/bridge/blender_plan.py` — confirm naming matches
- `lathe/bench_runtime.py` — covered via `test_language_v08.py:6` but thinly
- `lathe/test_runtime.py` — covered via `test_language_v08.py:11` but thinly
- `lathe/render_eval.py` — plan includes (Phase 6.3); good
- `lathe/schema.py` — only touched by `test_roundtrip.py`
- `lathe/utils.py` — not mentioned in plan; unclear whether it needs dedicated tests

**Modules audit claimed zero-coverage that actually have some coverage:**

- `test_language_v12.py:25-30` imports 6 modules as smoke. Still fair to call these "zero real coverage" — the plan's framing is honest.

## Already-done items

- **`.coveragerc`:** does not exist
- **`pytest-cov` / `hypothesis` / `syrupy` / `mutmut`:** not in `pyproject.toml` dev extras (dev extras currently = `["pytest>=9.0"]` only)
- **`conftest.py`:** does not exist
- **`requires_blender` / `requires_xatlas` / `requires_torch` marks:** no `pytest.mark`/`skipIf`/`skipUnless` usage in tests
- **Hypothesis DB, lockfile, CI coverage workflow:** none exist
- **Skips/xfails:** zero in current suite (clean slate — good)

Every line item in Phases 1-2 is genuinely greenfield. No wasted work proposed.

## Gaps

1. **Wrong omit path:** Phase 2's `.coveragerc` omits `lathe/lsp/*` — directory does not exist. Should omit `lathe/scaffolds/*` (which does exist, with `chest.py`, `drone.py`, `wall_panel.py`). Minor but suggests the plan author didn't list the tree.
2. **Stale source LOC:** 15,663 cited, actual ~17,061 (audit figure, not plan's fault, but the 1:3 target should scale).
3. **Missing from backfill list:** `scaffold_compiler.py` (critical under `lathe.shape.intent_mesh_handoff_v1`), `schema.py`, `utils.py`, `bench_runtime.py`, `test_runtime.py`, `defaults.py`, `capabilities.py`, `proposals.py`. Plan mentions `defaults`, `capabilities`, `proposals` in Phase 6 — good. Add `scaffold_compiler` explicitly (it's in the stable contract's hot path per CLAUDE.md).
4. **Module path drift:** Plan lists `test_surface_repair.py` (Phase 5.8) without indicating `lathe.repair.surface_repair` is a subpackage. Also `test_bridge_blender_plan.py` (Phase 6.3) should explicitly target `lathe.bridge.blender_plan`.
5. **Normalizer-input fuzzing not mentioned:** Property tests cover geometry + grammar + resolver, but `normalizer.py` (which inserts canonical defaults) is a strong fuzz target — malformed ASTs after parse. Worth adding to Phase 7.
6. **`.lth` example fuzzing:** Hypothesis could generate synthetic `.lth` strings (grammar-driven) to stress parser + checker. Missing.
7. **Contract tests for `backends.py`:** Phase 9 says "every ID in `backends.py` resolves and round-trips" — good — but doesn't pin the stable backend IDs (`lathe.stack.hard_surface_game_asset_v1`, `lathe.shape.intent_mesh_handoff_v1`, `lathe.topology.blender_hard_surface_v1`, `lathe.uv.xatlas_v1`, `lathe.package.openusd_gltf_v1`) as literals.
8. **`lathe test` / `lathe bench` in-language tests:** CLAUDE.md notes `python -m lathe.cli test` runs `.lth`-level `test`/`benchmark` declarations. Not addressed in the plan — should be part of Phase 10 CLI coverage.
9. **Snapshot determinism risk underplayed:** Hero bundles include timestamps/paths. Risks & Mitigations says "hashes/manifests, not raw geometry" but doesn't say how timestamps in trace manifests get zeroed out. Needs a fixture that freezes time/paths.
10. **No regression bisect story:** 85% gate is fine but doesn't prevent one-off regressions in hot files (e.g., `geometry_kernel`). Consider per-file floor (e.g., `geometry_kernel >= 95%`).

## Hero-example list verification (Phase 8)

Plan lists 9 heroes. Confirmed present in `examples/`:
- `courier_drone.lth` ✓
- `brassbound_chest.lth` ✓
- `industrial_crate.lth` ✓
- `mechanical_door.lth` ✓
- `console_terminal.lth` ✓
- `sci_fi_wall_panel.lth` ✓
- `service_cabinet.lth` ✓
- `control_pedestal.lth` ✓
- `supply_container.lth` ✓

All exist. Also consider adding `console_terminal_mobile_adapt.lth`, `reconstruct_courier_from_views.lth`, `service_corridor_wall.lth` — they exercise adapt/reconstruct/assemble modes that the base heroes don't, and `test_build.py` already validates them.

## Tool choice — defensibility

- **syrupy vs pytest-snapshot:** syrupy is the better choice. It has richer serializers, native JSON/PNG, clean diff review (`--snapshot-update`), active maintenance. pytest-snapshot is minimal and unmaintained.
- **mutmut vs cosmic-ray:** mutmut is simpler and faster; cosmic-ray gives finer-grained operators but needs more tuning. For "geometry_kernel + checker + resolver + conformance" (4 files, clear determinism), mutmut is the right default. Plan correctly offers cosmic-ray as alternative.
- **hypothesis:** no contest — it's the de-facto property-based library for Python. `.hypothesis/` CI cache call-out is correct.
- **pytest-cov:** correct.

## Existing test-quality flags

- `test_build.py` — 12 tests, ~298 LOC. Mostly "certified == True" + JSON field existence. Two genuinely useful tests: `test_topology_quality_gate_falls_back_from_blender` (L225, mocks blender executor) and `test_reference_topology_cleanup_seals_and_infers_parts` (L278, targeted unit-ish test). The rest are full-pipeline smokes.
- `test_shape_providers.py` — 218 LOC, the best test file. Real mock HTTP server (L24), retry-failure path (L176), fallback assertions (L202). Use this as the template for Phase 3 fixtures.
- `test_language_v12.py:25-30` — six `import ... # noqa: F401` lines that mask zero real coverage behind "smoke imports." Plan should explicitly supersede these with real tests.
- No `@skip`/`@xfail` markers — clean slate.
- None of the existing tests is broken or disabled.

## Feasibility (15 days)

| Phase | Days | Realism |
|---|---|---|
| 1 Cold-clone | 1 | Realistic |
| 2 Tooling + CI gate | 0.5 | Realistic |
| 3 Fixtures | 1 | Realistic if mocks stay thin |
| 4 Geometry backfill | 3 | **Tight** — 7 module groups × ≥6 cases = ~42 test methods plus property overlap. 4 days safer |
| 5 Runtimes + surface | 3 | **Tight** — 15 modules w/ capability+absent paths. 4 days safer |
| 6 V1.1/V1.2/V1.3 IRs + validators | 2 | **Tight** — 15+ modules. 3 days safer |
| 7 Property | 1.5 | Realistic |
| 8 Golden | 1 | Realistic |
| 9 Contract | 0.5 | Realistic |
| 10 Error-path + CLI | 1 | **Tight** — every raise site + every CLI subcommand. 1.5-2 days safer |
| 11 Mutation + final | 1 | Realistic (nightly only) |

**Realistic total: 18-20 days.** Ordering is correct (Phase 1 unblocks Phase 2 unblocks everything else; property/golden/contract layered on top of unit backfill). Mutation last is right.

## 10/10 verdict

**Current: 8.5/10.** To reach 10/10:

1. Fix the `lsp` → `scaffolds` omit path (also exclude `lathe/scaffolds/*` from coverage)
2. Update source-LOC baseline to 17,061; recompute 1:3 target (~5,700)
3. Add `scaffold_compiler.py`, `schema.py`, `utils.py`, `bench_runtime.py`, `test_runtime.py` to backfill
4. Use correct subpackage paths: `lathe.repair.surface_repair`, `lathe.bridge.blender_plan`
5. Add normalizer-input fuzzing + grammar-driven `.lth` fuzzing to Phase 7
6. Cover `python -m lathe.cli test` / `bench` (in-language tests) in Phase 10
7. Specify snapshot determinism fixture (freeze time/paths/uuids)
8. Add per-file coverage floors for geometry_kernel/checker/resolver/conformance (e.g., 95%)
9. Extend golden heroes to adapt/reconstruct/assemble variants
10. Extend timeline to 18-20 days OR drop Phase 11 from MVP (mutation as stretch)

## Relevant paths

- `D:\lathe_v0_1\plans\04_test_coverage.md`
- `D:\lathe_v0_1\tests\` (16 files, 1447 LOC)
- `D:\lathe_v0_1\pyproject.toml` (dev extras = `pytest>=9.0` only)
- `D:\lathe_v0_1\lathe\` (79 .py files, ~17,061 LOC)
- `D:\lathe_v0_1\lathe\repair\surface_repair.py` (subpackage)
- `D:\lathe_v0_1\lathe\bridge\blender_plan.py` (subpackage, 179 LOC)
- `D:\lathe_v0_1\lathe\scaffolds\` (correct omit target, not `lsp`)
- `D:\lathe_v0_1\tests\test_shape_providers.py` (template for Phase 3 fixtures)
- `D:\lathe_v0_1\tests\test_language_v12.py:25-30` (noqa imports to supersede)
