# Known Bugs — v0.2.0rc1

## Status

This is the known-bugs register for v0.2.0rc1, derived from the audit
captured in `plans/10_bugs_errors.md` (16 findings after the
2026-04-23 amendment: 15 originals − 2 removed (C3, Mi5) + 3 added
(M4b, M8, M9)). Every row tracks a single finding. A row leaves the
register only when (a) the fix has landed AND (b) the regression test
named in `plans/10_bugs_errors.md` exists, is wired into CI under the
`bug_regression` marker, and is green on the release branch.

As of 2026-04-28, no regression tests under the `bug_regression`
marker exist in the repository (`grep -rn '@pytest.mark.bug_regression'
tests/` returns no files; `tests/bugs/` contains only `__init__.py`
and `test_parser_budgets.py`). All 16 findings are therefore tracked
as open below.

Default owner: Tal Merri / @talmerri. The default target-fix track is
the Plan 10 phasing in `plans/10_bugs_errors.md`. Anything that does
not land by the release-gate cutover for v0.2.0rc1 final must either
be re-targeted with an explicit owner+date or accepted as a release
exception in `docs/release/decision-log-v0.2.0rc1.md`.

Severity legend (matches `docs/support/readiness-checklist.md`):

- **P0** — security, privacy/telemetry leak, broken install,
  certification path entirely broken. Plan 10 "Critical" maps to P0.
- **P1** — correctness regression, hero-family failure, blocking docs.
  Plan 10 "Major" maps to P1.
- **P2** — non-blocking bug or hygiene gap. Plan 10 "Minor" maps to P2.
- **P3** — tracked enhancement.

---

## P0 — Critical

| ID | Title | Severity | Owner | Target fix / exception | Regression test | Status |
|---|---|---|---|---|---|---|
| C1 | Bare `except Exception` in `shape_providers.py:422-425` hides `PermissionError`/`OSError`/corrupt-header on mesh load | P0 | Tal Merri | Plan 10 Phase 1 (day 1-2) | `tests/bugs/test_bug_C1.py::test_load_mesh_file_raises_on_permission_denied`, `…::test_load_mesh_file_raises_on_truncated_glb` — `requires-human: add regression test before bug closes` | open — release blocker: C1 |
| C2 | Bare `except Exception` in `shape_providers.py:463-489` BFS-fallback body-counting masks malformed face data; corruption never surfaces | P0 | Tal Merri | Plan 10 Phase 1 (day 1-2) | `tests/bugs/test_bug_C2.py::test_body_count_fallback_logs_on_attribute_error`, `…::test_body_count_preserves_fallback_for_missing_attr` — `requires-human: add regression test before bug closes` | open — release blocker: C2 |

---

## P1 — Major

| ID | Title | Severity | Owner | Target fix / exception | Regression test | Status |
|---|---|---|---|---|---|---|
| M1 | `shape_providers.py:557-573` Hunyuan client sniffs `content_type` after `resp.read()`; large non-mesh body buffered; JSON body treated as mesh | P1 | Tal Merri | Plan 10 Phase 2(a) — week 1 | `tests/bugs/test_bug_M1.py::test_hunyuan_json_body_with_missing_content_type`, `…::test_hunyuan_text_error_body` — `requires-human: add regression test before bug closes` | open — release blocker: M1 |
| M2 | `runtime_config.py:66` `json.loads` unguarded; no schema validation; typos crash opaquely | P1 | Tal Merri | Plan 10 Phase 2(b) — week 1 | `tests/bugs/test_bug_M2.py::test_runtime_config_invalid_json`, `…::test_unknown_key_warns`, `…::test_type_mismatch_rejects`, `…::test_missing_file_raises` — `requires-human: add regression test before bug closes` | open — release blocker: M2 |
| M3 | `shape_backend.py:285` string-compare conflates Python `None` with literal `"None"`/`"null"` strings | P1 | Tal Merri | Plan 10 Phase 2(a) — week 1 | `tests/bugs/test_bug_M3.py::test_shape_provider_none_means_auto`, `…::test_literal_none_string_rejected` — `requires-human: add regression test before bug closes` | open — release blocker: M3 |
| M4 | `blender_execution.py:208-229` subprocess `check=False` + returncode-only inspection misses Blender errors in stderr with rc=0 | P1 | Tal Merri | Plan 10 Phase 2(c) — week 1 | `tests/bugs/test_bug_M4.py::test_blender_stderr_error_with_zero_returncode`, `…::test_blender_timeout_reported` — `requires-human: add regression test before bug closes` | open — release blocker: M4 |
| M4b | Identical subprocess-without-stderr-scan pattern at `executor.py:1548` (`_run_blender_topology`) | P1 | Tal Merri | Plan 10 Phase 2(c) — week 1 | `tests/bugs/test_bug_M4b.py::test_executor_blender_topology_stderr_error_with_zero_returncode` — `requires-human: add regression test before bug closes` | open — release blocker: M4b |
| M5 | `shape_providers.py:657-658` Indexed filename in shared work dir; concurrent builds may overwrite candidates | P1 | Tal Merri | Plan 10 Phase 2(a) — week 1 | `tests/bugs/test_bug_M5.py::test_concurrent_hunyuan_builds_do_not_collide` (threaded) — `requires-human: add regression test before bug closes` | open — release blocker: M5 |
| M6 | `shape_providers.py:296-304` + `runtime_config.py:13` `strict=False` default + reference-conditioned fallback → exit 0 despite learned-provider failure | P1 | Tal Merri | Plan 10 Phase 2(a) — week 1 (also tied to BL-37 strict-mode-flip) | `tests/bugs/test_bug_M6.py::test_strict_provider_fallback_nonzero_exit`, `…::test_allow_fallback_keeps_zero_exit` — `requires-human: add regression test before bug closes` | open — release blocker: M6 |
| M7 | `pyproject.toml:11-17, 25-36` `>=` pins only; no lockfile; `torch>=2.11.0` is suspicious (current stable is 2.5.x); non-reproducible builds | P1 | Tal Merri | Plan 10 Phase 2(c) — week 1 | `tests/bugs/test_bug_M7.py::test_lockfile_matches_pyproject` (CI) plus smoke-build-against-lockfile — `requires-human: add regression test + verify torch pin + ship requirements.lock before bug closes` | open — release blocker: M7 |
| M8 | Codebase-wide: ~27 `except Exception` sites across 12 files (`executor.py`, `validators/visual_quality.py`, `exact_solids.py`, `shape_providers.py`, `shape_backend.py`, `eval_harness.py`, `candidate_search.py`, `parser.py`, `capabilities.py`, `doctor.py`, `cli.py`, `geometry_kernel.py`, `normalizer.py`) | P1 | Tal Merri | Plan 10 Phase 4 — week 2-3 | `tests/bugs/test_no_blind_excepts.py` (greps `lathe/`, fails on regression above pinned baseline) — `requires-human: add regression test + ship docs/exception_audit.md before bug closes` | open — release blocker: M8 |
| M9 | Codebase-wide: 17 production `assert` statements (`assembly_kernel.py`, `geometry_kernel.py`, `executor.py:372`, `scaffold_compiler.py`, `exact_solids.py`, `validators/visual_quality.py:118`) — stripped under `python -O` | P1 | Tal Merri | Plan 10 Phase 4 — week 2-3 | `tests/bugs/test_no_production_asserts.py` (greps `lathe/`, asserts clean) — `requires-human: add regression test before bug closes` | open — release blocker: M9 |

---

## P2 — Minor

| ID | Title | Severity | Owner | Target fix / exception | Regression test | Status |
|---|---|---|---|---|---|---|
| Mi1 | `resolver.py:292, 399-401` list comprehensions inconsistently filter vs raise on unresolved names | P2 | Tal Merri | Plan 10 Phase 3 — week 2 | `tests/bugs/test_bug_Mi1.py::test_resolver_unresolved_component_raises`, `…::test_resolver_optional_filters_silently` — `requires-human: add regression test before bug closes` | open — accept as release exception or fix in Phase 3 — `requires-human: confirm exception vs fix in docs/release/decision-log-v0.2.0rc1.md` |
| Mi2 | `shape_backend.py:335-337` single ternary in `_root_name` fragile under contract drift | P2 | Tal Merri | Plan 10 Phase 3 — week 2 | `tests/bugs/test_bug_Mi2.py::test_root_name_contract_stable_under_reorder` — `requires-human: add regression test before bug closes` | open — accept as release exception or fix in Phase 3 — `requires-human: confirm exception vs fix in docs/release/decision-log-v0.2.0rc1.md` |
| Mi3 | Undocumented magic `7919` RNG offset used at `executor.py:1176`, `shape_backend.py:59`, `scaffold_compiler.py:29`; should move to `lathe/constants.py::RNG_PRIME_OFFSET` | P2 | Tal Merri | Plan 10 Phase 3 — week 2 | `tests/bugs/test_bug_Mi3.py::test_rng_prime_offset_deterministic_across_runs` — `requires-human: add regression test before bug closes` | open — accept as release exception or fix in Phase 3 — `requires-human: confirm exception vs fix in docs/release/decision-log-v0.2.0rc1.md` |
| Mi4 | Repo root: transient dirs and parser cache committed; `.gitignore` incomplete | P2 | Tal Merri | Plan 10 Phase 3 — week 2 | CI: `git status --porcelain` after `pytest` must be empty — `requires-human: wire CI check + ship .gitignore + git rm -r --cached offenders before bug closes` | open — accept as release exception or fix in Phase 3 — `requires-human: confirm exception vs fix in docs/release/decision-log-v0.2.0rc1.md` |

---

## Fixed (regression-test verified)

None for v0.2.0rc1 as of 2026-04-28. When a row moves here it must
include the commit SHA that closed it AND the path of the green
regression test under `tests/bugs/`. Findings without a regression
test do not move here regardless of code state.

---

## Accepted exceptions

None for v0.2.0rc1 as of 2026-04-28. Each accepted exception will
record owner, date, affected surface, user impact, workaround, and
removal target in `docs/release/decision-log-v0.2.0rc1.md` and link
back to the corresponding row above by ID.

---

## Cross-references

- Source plan: `plans/10_bugs_errors.md` (16 findings, amended
  2026-04-23 to remove C3/Mi5 and add M4b/M8/M9; Phase 4.5 reconciles
  the existing error hierarchy before `lathe/errors.py` lands).
- Bug-regression pytest marker: `bug_regression` (per Plan 10 §2 — to
  be added; not present in the codebase as of 2026-04-28).
- Fixed-and-verified rows must additionally appear in
  `docs/release/evidence-v0.2.0rc1.md` with the closing commit SHA
  and the regression-test path.

---

## ADR currency check

The ADR index is at `docs/adr/README.md`. As of 2026-04-28:

| ADR | Title | Current status | Recommendation |
|---|---|---|---|
| 0001 | Freeze `lathe.shape.intent_mesh_handoff_v1` as the single probabilistic seam | Accepted | Keep Accepted — implementation lives in `lathe/shape_backend.py` and `tests/contract/test_shape_handoff_v1.py` pins the SHA. |
| 0002 | Blender / xatlas adapters degrade to deterministic reference paths with attempted-vs-actual tracing | Accepted | Keep Accepted — implemented in `lathe/blender_execution.py` and `lathe/uv_xatlas.py` (or equivalent), traces include `attempted` vs `actual`. |
| 0003 | Shape-provider selection via mux with probe-then-fallback | Accepted | Keep Accepted — implemented via `lathe/shape_providers.py` provider mux. |
| **0004** | Plugin extension points via `importlib.metadata.entry_points` | **Proposed** | **Keep Proposed.** ADR cross-refs say "once surgeon-plugins task #1 lands, this ADR flips to Accepted and a commit SHA is recorded here." Plan 03 Phase 2 (the implementation gate) has not landed; `lathe/contracts/registry.py` is not present in the tree as of 2026-04-28; `pyproject.toml` does not declare the four `[project.entry-points."lathe.*"]` groups. Promotion requires the implementation commit + a populated entry-points block + `lathe doctor --plugins` working end-to-end. |
| **0005** | Enforce package layering via `import-linter` contracts | **Proposed** | **Keep Proposed.** ADR depends on Plan 03 Phase 3 / Phase 7. `.importlinter` config is not present, `tests/test_architecture.py` exists but does not yet enforce the four contracts (Layers, Backend independence, Contracts purity, Providers isolation) declared in the ADR. Promotion requires the `.importlinter` file + `scripts/check_arch.sh` + green CI run + the pydeps graph at `docs/adr/0005-dep-graph.svg`. |
| **0006** | Validator protocol and topological composition via `ValidatorPipeline` | **Proposed** | **Keep Proposed.** ADR depends on Plan 03 Phase 5. `lathe/contracts/validator.py` and `lathe/validators/composition.py` are not present; the five existing validators (`semantic_quality`, `visual_quality`, `flow_quality`, `surface_quality`, `silhouette`) still live as free functions called sequentially from `lathe/core/stages/validate.py`; entry-point registration under `lathe.validators` is blocked on ADR 0004's implementation. Promotion requires the protocol + pipeline + migrated built-ins + entry-point registration + green tests. |
| 0007 | Accept `lathe/resolver.py` 540 LOC as a file-size exception | Accepted | Keep Accepted — exception is intentionally documented in this ADR. |
| 0008 | Adopt Manifold as the primary geometry kernel | Accepted | Keep Accepted — implementation tracked under `lathe/geometry_kernel.py`. |
| 0009 | Maintain a public contract index for downstream boundaries | Accepted | Keep Accepted — referenced by ADR 0004 as the surface plugins target. |

**Summary recommendation.** Keep ADRs 0004, 0005, 0006 in **Proposed**
until each has its implementing commit SHA recorded in the ADR's
"Cross-references" section AND the listed evidence (entry-point block,
`.importlinter` config, validator protocol module, green CI runs)
exists on the release branch. Promoting any of these to Accepted
without the implementation evidence would be a documentation lie that
the audit will catch on re-review. ADRs 0001-0003, 0007-0009 remain
Accepted; this register does not modify them.

This pass does **not** alter any ADR file. Promotions, when justified
by landing implementation, are the responsibility of the lead
aggregating this readiness pass.
