# Phase 0 — Blocker Inventory for Asset-Quality Upgrade

> Companion to `docs/asset-quality/baseline-evidence.md`.
> Each entry below is a real or potential blocker for Phases 1–15 of
> `docs/asset-quality/improvement-tasklist.md`.
>
> **Status legend:**
> - **CLEARED** — resolved by Phase 0 work.
> - **RESOLVED** — resolved after Phase 0 by a separate event (e.g. main-merge).
> - **OPEN** — scoped to a specific future phase; does not block earlier phases.
> - **STANDING RULE** — a coordination rule that applies whenever the relevant phase begins; never a hard blocker by itself.
> - **NON-BLOCKING** — tracked for completeness; never blocks any phase.

**Date:** 2026-04-29 (created at Phase 0 close).
**Last updated:** 2026-04-30 — B-05 marked RESOLVED after main-merge; B-10 reframed as a standing Phase 13 coordination rule.
**Author:** Phase 0 baseline pass.
**Repository state at update:** working tree clean on `main` at commit `b230e0d`. The pre-merge state described in `baseline-evidence.md` Section 8 no longer applies; see B-05 below for the resolution.

---

## Cleared by Phase 0

### B-01 — `lathe.asset_quality` package did not exist (CLEARED)

**Symptom:** Phase 2 calls for `lathe/asset_quality/design_brief.py`, Phase 3 for `lathe/asset_quality/family_grammar.py`, Phase 4 for graph types in the same package. Nothing existed at that path.

**Resolution:** Created `lathe/asset_quality/__init__.py` as the package marker. All Phase 1–15 modules can now be added under this package without restructuring.

**Verification:** `python -c "import lathe.asset_quality"` succeeds.

---

### B-02 — No frozen contract for the certification report shape (CLEARED)

**Symptom:** Phase 1+ adds `quality_diagnostics`, Phase 2 adds design-brief metadata, Phase 4 adds construction-graph emission. Without a contract test, a refactor could silently drop existing keys downstream consumers (HTML report, terminal report, engine manifests, repair planner) depend on.

**Resolution:** Added `tests/unit/test_asset_quality_baseline_report_shape.py` with five contract tests:

- `visual_quality` top-level keys are a superset of the baseline.
- `visual_quality.metrics` is a superset of the 38 baseline metric keys.
- `visual_quality.diagnostics` remains a list.
- `visual_quality.metrics` values remain numeric for baseline keys.
- `validate/report.json` top-level keys are a superset of the baseline (skipped if `.tmp_tests/` baseline absent).

**Verification:** `python -m pytest tests/unit/test_asset_quality_baseline_report_shape.py -v` → 5 passed.

---

### B-03 — Baseline scores undocumented (CLEARED)

**Symptom:** Without recorded baseline scores it is impossible to tell whether Phase 1+ improves or regresses the assets the spec calls out.

**Resolution:** `baseline-evidence.md` records per-asset certification, per-metric values, threshold margins, and the spec-failure-mode → metric mapping. Future phases can compare directly against this.

---

### B-04 — Wrong/stale module references in CLAUDE.md / AGENTS.md (NON-BLOCKING)

**Symptom:** Both files reference `lathe/parser.py`, `lathe/checker.py`, `lathe/planner.py` as flat modules. The actual structure has them as packages (`lathe/parser/`, `lathe/checker/`, `lathe/planner.py` is still flat). Modified-file list in `git status` confirms ongoing work on the package forms.

**Resolution status:** Functionally non-blocking — imports work via re-exports. Documented here so Phase 13's docs work knows to update these references when public language docs are revised.

---

## Open — Surface to user before relevant phase

### B-05 — Three uncommitted workstreams in tree (RESOLVED 2026-04-30)

**Original symptom:** At Phase 0 close, `git status` showed ~50 modified files (v0.2.0rc1 readiness pass) and ~150 untracked entries (Wonder/Scene subsystem) intermixed with the asset-quality docs and Phase 0 additions. Any commit during Phase 1+ work risked pulling in unrelated files as collateral and conflating three independent feature streams in history.

**Resolution:** All three streams were split into separate feature branches and merged into `main` on 2026-04-30:

- `feat/asset-quality-phase0` → merge commit `3706fe5` (PR #11) — 7 files, the Phase 0 deliverables.
- `feat/wonder-subsystem` → merge commit `3bb8de3` (PR #12) — 318 files, the Wonder/Scene subsystem and Roblox export lane.
- `chore/v0.2.0rc1-readiness` → merge commit `b230e0d` (PR #13) — 49 modified files, the v0.2.0rc1 readiness language/grammar/schema/docs/tests pass.

The working tree is now clean. Local `main` and `origin/main` are bit-identical at commit `b230e0d`. Phase 1+ commits no longer risk conflating streams, because no parallel uncommitted work remains in the tree.

**Verification:**
- `git status --short` → empty.
- `git rev-parse HEAD` == `git rev-parse origin/main` == `b230e0d`.
- `git diff --name-only e94a202..b230e0d | wc -l` → 374 = 7 (Phase 0) + 318 (Wonder/Scene) + 49 (readiness, modified). Reconciles exactly with no losses.

**Implication for Phase 1:** none. Phase 1 work can proceed directly on `main` (or on a fresh `feat/asset-quality-phase1` branch) without any commit-strategy preflight.

---

### B-06 — No moodboard / reference fixtures (OPEN, blocks Phase 11)

**Symptom:** Phase 11 (Reference/Moodboard Ingestion) references `refs/crate_moodboard.json`, `refs/crate_silhouette_front.png`, `refs/painted_steel_worn_edges.png`, `refs/toy_like_crate.png`. None exist under `examples/refs/`.

**Recommendation:** When Phase 11 starts, create minimal example fixtures (≤8KB PNGs, JSON metadata files) under `examples/refs/asset_quality/`. Keep them deterministic and re-creatable so they pass `tests/unit/test_fixture_hygiene.py`.

**Status:** Not blocking until Phase 11. Logged here so future phase work doesn't stumble on missing assets.

---

### B-07 — No kit-library directory or metadata schema (OPEN, blocks Phase 12)

**Symptom:** Phase 12 (Standard Hard-Surface Kit Library) references `std.kit.hardsurface.v1` with subdirectories for fasteners/, hinges/, brackets/, vents/, handles/, rails/, corner_guards/, cable_ports/, status_lights/, labels/, warning_decals/. None exist under `std/kits/` or similar.

**Recommendation:** Phase 12 will need:
1. A new directory `std/kits/hardsurface/` with one example part per kit category (deterministic procedural recipe).
2. A schema for kit-part metadata under `schema/kit_part.schema.json`.
3. A loader in `lathe/asset_quality/kit_library.py` that parses kit metadata.

**Status:** Not blocking until Phase 12.

---

### B-08 — No real high-poly producer in the pipeline (OPEN, blocks strict mode of Phase 7)

**Symptom:** The shape stage produces a single mesh; topology cleans it; surface bakes maps. There is no separate `stages/shape/high_poly.glb` artifact today. The current `highlow_distinction_quality = 0.45` is computed from a heuristic (see `lathe/validators/visual_quality.py:310-329`), not from real high-vs-low geometry.

**Why this matters:** Phase 7 (High-Poly / Low-Poly Reality Gate) wants to *fail or warn* hero assets without real high/low. Without a producer, every hero asset would fail strict-mode, breaking existing examples.

**Recommendation:** Phase 7 must land in two passes:
1. **Pass A (warning-only):** add the `highlow_fake_detail_penalty` diagnostic (Phase 1 already covers this) and emit a warning. Existing assets keep building.
2. **Pass B (strict mode opt-in):** Add a `high_poly` producer behind a runtime config flag. Strict mode requires the flag and explicit hero opt-in.

**Status:** Not blocking Phase 1 (warning-only path is fine). Strict mode of Phase 7 is gated.

---

### B-09 — No asset-quality CI lane (OPEN, blocks Phase 15)

**Symptom:** `.github/workflows/` has untracked Wonder workflows (`wonder-fast.yml`, `wonder-benchmarks.yml`, etc.) but no asset-quality workflow. The fast pytest sweep above takes 2.6s for the targeted slice — fine for CI — but no scheduled lane runs the asset-quality contract tests today.

**Recommendation:** Phase 15 will add `.github/workflows/asset-quality-fast.yml` running the new `tests/unit/test_asset_quality_*.py` slice. Builds-as-evidence (slow lane) can come later.

**Status:** Not blocking until Phase 15. The contract test is opt-in skipped when `.tmp_tests/` baseline is absent, so it works today even without a CI lane.

---

### B-10 — Phase 13 public-syntax coordination rule (STANDING RULE for Phase 13)

**Symptom:** Phase 13 introduces optional `.lth` blocks (`art_direction`, `construction`, `material_graph`, `references`, `kit`). Per AGENTS.md *Working agreements / Language contract changes*, any change to the public language surface requires a coordinated update across **all** of these layers in a single PR:
- `spec/lathe-v0.1.md`
- `grammar/lathe.lark`
- `schema/lathe.schema.json`
- `lathe/parser/`, `lathe/normalizer.py`, `lathe/resolver.py`, `lathe/checker/`
- examples + tests

**Update 2026-04-30:** The earlier in-flight v0.2.0rc1 readiness pass that previously held all of these files in modified state is now merged into `main` (commit `b230e0d`). The hard "wait for readiness merge" gate that originally blocked Phase 13 is therefore removed — Phase 13 can begin whenever the asset-quality upgrade reaches that point.

**Standing rule (still in force whenever Phase 13 begins):** Phase 13 implementation must update the eight layers above together in a single coordinated PR. Phase 1–12 work proceeds independently because it only touches report shapes, additive validators, and new packages under `lathe/asset_quality/` — never the public source syntax. The contract tests in `tests/unit/test_asset_quality_baseline_report_shape.py` verify that Phase 1–12 stays syntax-additive only.

**Status:** Standing language-contract coordination rule. Not a hard blocker; applies only when Phase 13 begins. Does not block Phases 1–12.

---

### B-11 — `tests/test_visual_quality.py` is `pytest.mark.slow` (OPEN, soft constraint)

**Symptom:** The most thorough visual-quality test runs the full benchmark suite (`run_benchmark_suite(ROOT)`), which is slow and depends on building reference negative/near-miss/positive assets.

**Why this matters:** Phase 1 should not silently regress this test; we need a fast feedback loop.

**Recommendation:** Run the slow test once per phase to confirm no regression — but iterate on the new fast contract test (`test_asset_quality_baseline_report_shape.py`) plus existing `test_validators_visual_surface_fast.py` during development.

**Status:** Tracked. No action needed in Phase 0.

---

### B-12 — CRLF line-ending warnings on modified Python files (OPEN, COSMETIC)

**Symptom:** `git diff` issues "CRLF will be replaced by LF the next time Git touches it" warnings on the 49 modified Python files (`lathe/checker/`, `lathe/parser/`, etc.).

**Why this matters:** Spurious diff noise on next commit. Does not affect runtime behavior.

**Recommendation:** Cosmetic; user can resolve via `git add --renormalize .` once they decide which workstream to commit first.

**Status:** Non-blocking, tracked.

---

## Summary

| ID | Title | Status | Blocks |
|---|---|---|---|
| B-01 | `lathe.asset_quality` package missing | CLEARED | — |
| B-02 | No frozen report-shape contract | CLEARED | — |
| B-03 | Baseline scores undocumented | CLEARED | — |
| B-04 | Stale module references in CLAUDE/AGENTS docs | NON-BLOCKING | — |
| B-05 | Three uncommitted workstreams in tree | **RESOLVED 2026-04-30** | — |
| B-06 | No moodboard / reference fixtures | OPEN | Phase 11 only |
| B-07 | No kit-library scaffolding | OPEN | Phase 12 only |
| B-08 | No real high-poly producer | OPEN (warning-only path is fine) | Phase 7 strict mode only |
| B-09 | No asset-quality CI lane | OPEN | Phase 15 only |
| B-10 | Phase 13 public-syntax coordination rule | STANDING RULE | Phase 13 only |
| B-11 | Slow benchmark test | NON-BLOCKING | — |
| B-12 | CRLF warnings | NON-BLOCKING | — |

### Phase 1 readiness

**Phase 1 blockers: none.** B-01, B-02, B-03 are cleared by Phase 0; B-05 is resolved by today's main-merges. None of B-06 through B-12 apply to Phase 1.

**Future-phase blockers remain tracked:** B-06 (Phase 11), B-07 (Phase 12), B-08 (Phase 7 strict mode), B-09 (Phase 15), B-10 (Phase 13).

**Standing rule for Phase 13:** Do not start public-syntax work until `spec/lathe-v0.1.md`, `grammar/lathe.lark`, `schema/lathe.schema.json`, `lathe/parser/`, `lathe/normalizer.py`, `lathe/resolver.py`, `lathe/checker/`, examples, and tests can all be updated together in a single coordinated PR. Phases 1–12 are syntax-additive only and are not subject to this rule.
