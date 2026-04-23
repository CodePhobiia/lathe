# Implementation Plan: Bugs, Errors & Issues 5/10 → 10/10

> **Amendment note (2026-04-23):** Finding C3 from original audit was already fixed (verified at `shape_providers.py:442`). Removed from scope.
>
> Finding Mi5 was contradicted by environment check — trimesh 4.11.5 is installed in the current `.venv`. Removed from this plan; cold-clone regression belongs in Plan 04 (Tests) bootstrap phase, not in this bug list.
>
> Scope change: 15 original findings − 2 removed (C3, Mi5) + 3 added (M4b, M8, M9) = **16 findings** covered by this plan. See Amendment log at bottom.

## Overview

Close all 16 audit findings across `lathe/shape_providers.py`, `lathe/shape_backend.py`, `lathe/runtime_config.py`, `lathe/blender_execution.py`, `lathe/executor.py`, `lathe/resolver.py`, `pyproject.toml`, and repo hygiene. Introduce a typed exception hierarchy (reconciled with existing error classes), structured logging, stricter defaults, static-analysis gates, and fuzz/bug-bash rituals so silent failure becomes impossible and every regression is test-pinned.

---

## Phase 1 — Stabilize Critical (day 1-2)

C1-C2 are hot: bare `except` that hides corruption, and a BFS-fallback bare `except` that masks malformed face data. Batch together — both in `lathe/shape_providers.py`, share fixture (malformed + empty mesh files).

## Phase 2 — Correctness Major (week 1)

M1-M7 plus M4b in three PR batches:
- (a) HTTP/provider correctness — M1, M3, M5, M6
- (b) Config loader hardening — M2
- (c) Subprocess + supply-chain — M4, M4b, M7

Each batch ships its own regression tests; no cross-module touches.

## Phase 3 — Hygiene & Polish Minor (week 2)

Mi1-Mi4 land after Phases 1-2 green: resolver consistency, nested-ternary refactor, named-constant extraction, `.gitignore` + repo cleanup.

## Phase 4 — Codebase-wide Cleanup (week 2-3)

M8 (bare-except expansion across ~27 sites, 12 files) and M9 (17 production `assert` → `LatheError`) land as two dedicated PRs. These are large-surface-area sweeps; each touches many files but each change is mechanical and independently testable.

## Phase 4.5 — Error-Hierarchy Reconciliation (week 3)

**Before** introducing `lathe/errors.py`, audit and reconcile existing error classes. Inventory:

- `backends.py:11` `BackendResolutionError(Exception)`
- `executor.py:67` `BuildError(Exception)`
- `patch_api.py:9` `PatchAPIError(Exception)`
- `normalizer.py:77` `NormalizationError(Exception)`
- `parser.py:26,30` `LatheParseError(Exception)`, `DuplicateFieldError(LatheParseError)`
- `resolver.py:10` `ResolutionError(Exception)`
- `shape_providers.py:82,90,94` `ShapeProviderError(RuntimeError)`, `ShapeProviderUnavailable`, `ShapeProviderExecutionError`
- Any others from `grep -rn '^class.*Error' lathe/`

The new hierarchy must re-home these without breaking imports. Strategy: keep existing names as subclasses (or aliases) under the new `LatheError` root, and provide module-level re-exports for one release cycle. Specifically, `ShapeProviderError` currently inherits from `RuntimeError` — new parentage must preserve `isinstance(e, RuntimeError)` either by multiple inheritance or by documenting the break and sweeping `except RuntimeError` callers. Ship a migration doc in `docs/error_migration_v1.md`.

## Phase 5 — Prevention (week 3-4)

Adopt ruff (`BLE001`, `B904`, `TRY003`, `TRY201`, `TRY301`, `TRY400`, `S603`, `S607`), mypy `--strict` on **new modules only** (gradual rollout — full-package strict is a multi-quarter effort, not a gate), bandit (medium+), semgrep Python-security ruleset; wire into CI + pre-commit. Add fuzz harnesses (Phase 6) and scheduled bug-bash (Phase 7).

---

## Findings Table

| ID   | Severity | File:Line                        | Root cause                                                                                   | Fix                                                                                                                        | Regression test                                                                                    | Effort |
|------|----------|----------------------------------|----------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------|--------|
| C1   | Critical | shape_providers.py:422-425       | Bare `except Exception` hides `PermissionError`, `OSError`, corrupt-header                   | Catch concrete classes `(OSError, ValueError, KeyError, IndexError)` that trimesh actually raises on corrupt inputs; re-raise as `ShapeMeshLoadError`; log WARNING with path + exc class | `test_load_mesh_file_raises_on_permission_denied`, `test_load_mesh_file_raises_on_truncated_glb`   | S (0.5d) |
| C2   | Critical | shape_providers.py:463-489       | Bare `except Exception` in the BFS-fallback body-counting path swallows errors from malformed face data; the fallback returns a computed count from the BFS that may be incorrect on corrupt mesh | Narrow to `(AttributeError, IndexError, ValueError)`; log at DEBUG when fallback engages so corruption isn't silent; keep BFS as intentional fallback — do **not** raise | `test_body_count_fallback_logs_on_attribute_error`, `test_body_count_preserves_fallback_for_missing_attr` | S (0.5d) |
| M1   | Major    | shape_providers.py:557-573       | `content_type` sniff happens after `resp.read()`; large non-mesh body buffered; JSON body treated as mesh if header missing | Check `resp.headers` before reading (or stream-read); sniff first 16 bytes (`{` vs `glTF`/`OBJ`); raise `unexpected_json_response` or `unknown_media_type` | `test_hunyuan_json_body_with_missing_content_type`, `test_hunyuan_text_error_body`                | M (1d)   |
| M2   | Major    | runtime_config.py:66             | `json.loads` unguarded; no schema validation; typos crash opaquely; no `read_text` guard     | try/except `(FileNotFoundError, UnicodeDecodeError, JSONDecodeError)` → `RuntimeConfigError`; create `schema/runtime_config.schema.json` and validate; unknown keys warn | `test_runtime_config_invalid_json`, `test_unknown_key_warns`, `test_type_mismatch_rejects`, `test_missing_file_raises`        | M (1d)   |
| M3   | Major    | shape_backend.py:285             | String compare against `"None"`/`"null"` conflates Python `None` with literal strings        | Upstream normalize: `provider = shape_cfg.get("provider")`; treat None/""/"auto" as auto; reject literal `"None"`/`"null"` as typos | `test_shape_provider_none_means_auto`, `test_literal_none_string_rejected`                        | S (0.5d) |
| M4   | Major    | blender_execution.py:208-229     | `check=False` + returncode-only inspection misses Blender errors in stderr with rc=0; `output_blend.exists()` is the only mitigation | Route through `run_sandboxed`; scan stderr for `Error:`, `Traceback`, `Python script failed`; parse summary file if present; raise `BlenderExecutionError` on match; include tail in log | `test_blender_stderr_error_with_zero_returncode`, `test_blender_timeout_reported`                 | M (1d)   |
| M4b  | Major    | executor.py:1548 (`_run_blender_topology`) | Identical `subprocess.run(..., check=False)` pattern, same stderr-scan gap as M4 | Same fix as M4: route through `run_sandboxed`; share stderr-scan helper | `test_executor_blender_topology_stderr_error_with_zero_returncode` | M (0.5d) |
| M5   | Major    | shape_providers.py:657-658       | Indexed filename in shared work dir; concurrent builds could overwrite candidates            | Verify upstream call sites first (may already be per-build in practice); if collision possible, route each build through `work_dir/build_id/...`; use `uuid4().hex[:8]` per-candidate prefix | `test_concurrent_hunyuan_builds_do_not_collide` (threaded)                                         | M (1d)   |
| M6   | Major    | shape_providers.py:296-304 + runtime_config.py:13 | `strict=False` default + reference-conditioned fallback → exit 0 despite learned failure     | Flip default `strict=True` for learned providers when explicitly selected; non-zero exit on fallback unless `allow_fallback: true`; record `fallback_exit_code`; auto-mode stays permissive | `test_strict_provider_fallback_nonzero_exit`, `test_allow_fallback_keeps_zero_exit`              | M (1.5d) |
| M7   | Major    | pyproject.toml:11-17, 25-36      | `>=` pins only; no lockfile; non-reproducible builds; `torch>=2.11.0` is suspicious (current stable is 2.5.x) | Add upper bounds (`lark>=1.1,<2`, etc.); verify/correct torch pin; `requirements.lock` via `pip-compile`; CI uses lockfile; Renovate bot              | `test_lockfile_matches_pyproject` (CI); smoke build against lockfile                              | M (1d)   |
| M8   | Major    | lathe/ (codebase-wide)           | ~27 total `except Exception` sites across 12 files (notably `executor.py:292, 521, 581, 1346, 1354, 1512, 1593, 1655`; `validators/visual_quality.py:58, 239`; `exact_solids.py:116, 130, 179, 211`; `shape_providers.py:732, 920, 927`; `shape_backend.py:87`; `eval_harness.py:77`, `candidate_search.py:67`, `parser.py:1631`, `capabilities.py:295`, `doctor.py:38`, `cli.py:263`, `geometry_kernel.py:227`, `normalizer.py`) | Narrow each to concrete exception classes; audit existing `# noqa: BLE001` waivers; add `BLE001` to ruff; catalog in `docs/exception_audit.md` with per-site rationale | `tests/bugs/test_no_blind_excepts.py` greps `lathe/` and fails if bare-except count regresses above a pinned baseline | M (1.5d) |
| M9   | Major    | lathe/ (codebase-wide)           | 17 production `assert` statements across `assembly_kernel.py`, `geometry_kernel.py`, `executor.py:372`, `scaffold_compiler.py`, `exact_solids.py`, `validators/visual_quality.py:118` — all stripped under `python -O` | Convert to `if not ...: raise LatheError(...)`; triage list: `grep -rn '^\s*assert ' lathe/` and classify each as invariant (→ raise) or test-debug (→ delete) | `tests/bugs/test_no_production_asserts.py` greps `lathe/` and asserts clean | S (0.5d) |
| Mi1  | Minor    | resolver.py:292, 399-401         | List comprehensions inconsistently filter vs raise on unresolved names                       | Helper `_resolve_required(name, mapping, kind)` raises `UnresolvedNameError`; filter-path → explicit `_resolve_optional`   | `test_resolver_unresolved_component_raises`, `test_resolver_optional_filters_silently`            | S (0.5d) |
| Mi2  | Minor    | shape_backend.py:335-337         | Single ternary in `_root_name` fragile under contract drift                                  | Extract to `if/elif/else`; docstring cites the contract                                                                    | `test_root_name_contract_stable_under_reorder`                                                    | S (0.25d) |
| Mi3  | Minor    | executor.py:1176 + shape_backend.py:59 + scaffold_compiler.py:29 | Undocumented magic `7919` used as RNG offset in 3 sites                                     | Move to `lathe/constants.py::RNG_PRIME_OFFSET = 7919` with comment (prime mixing); replace 3 call sites; optionally derive from `blake2b(build_id)` | `test_rng_prime_offset_deterministic_across_runs`                                                    | S (0.25d) |
| Mi4  | Minor    | repo root                        | Transient dirs + 25MB parser cache committed; no `.gitignore`                                | `.gitignore` (`dist_*/`, `tmp_*/`, `warm_*/`, `v05_*/`, `cache_probe_*/`, `.lathe_lark_cache`, `.venv*/`, `__pycache__/`); `git rm -r --cached` offenders | CI: `git status --porcelain` after `pytest` must be empty                                         | S (0.5d) |

---

## 1. Triage Workflow

- **Day 1-2:** Phase 1 (C1, C2) — single PR, single reviewer, merged before any other work.
- **Week 1:** Phase 2 in three PRs (HTTP correctness / config loader / subprocess+deps, now including M4b). Each PR ≤400 LOC diff, each ships its own tests.
- **Week 2:** Phase 3 Minor as one housekeeping PR; `.gitignore` + repo-clean as separate PR (diff hygiene).
- **Week 2-3:** Phase 4 codebase sweeps — M8 and M9 as two dedicated PRs (mechanical, large-surface-area).
- **Week 3:** Phase 4.5 error-hierarchy reconciliation — precedes any `lathe/errors.py` work.
- **Week 3-4:** Phase 5 prevention infrastructure; gate future PRs.
- Batching rule: never mix "behavior change" with "static-analysis adoption" in the same PR.

## 2. Regression Test Suite

One test per finding (table above). Organized as `tests/bugs/test_bug_<ID>.py` for future cross-reference. CI marker `@pytest.mark.bug_regression` runs subset on every PR in <30s; full suite on merge. M8/M9 ship grep-based sweep tests (`test_no_blind_excepts.py`, `test_no_production_asserts.py`) to prevent regression.

## 3. Prevention — Static Analysis

| Rule | Catches | Would have prevented |
|---|---|---|
| ruff `BLE001` (blind except) | bare `except Exception` | C1, C2, M8 |
| ruff `B904` (raise-from) | losing exception chain | M1, M2 |
| ruff `TRY003`/`TRY201`/`TRY301`/`TRY400` | swallowed/vague exceptions, verbose-raise, bad logging | C1, C2, M4, M4b |
| ruff `S603`/`S607` (subprocess) | unchecked subprocess | M4, M4b |
| mypy `--strict` on **new modules only** (gradual) | `Any` leaks, implicit `None` vs str | M3, Mi1 |
| bandit medium+ | subprocess + file-perm issues | M4, M4b, M5 |
| semgrep `python.lang.security.*` | arbitrary JSON deserialize, path traversal | M2, M5 |
| pip-audit + Renovate | vulnerable deps | M7 |

Note: `TRY200` was removed/renamed in ruff 0.1.9; we use `B904` (raise-from, already listed) plus `TRY201` (verbose-raise) as its current equivalents. Do not cite `TRY200`.

Note: bare excepts in the codebase carry `# noqa: BLE001` — enabling ruff doesn't surface them, so M8 must audit and remove waivers rather than rely on the rule alone.

Wire all via pre-commit + `.github/workflows/lint.yml`.

## 4. Error Handling Standard

`lathe/errors.py` hierarchy (lands **after** Phase 4.5 reconciliation):

```
LatheError
├── LatheConfigError
│   └── RuntimeConfigError
├── LatheResolverError
│   └── UnresolvedNameError  (absorbs resolver.py:ResolutionError)
├── LatheParseError           (absorbs parser.py:LatheParseError)
│   └── DuplicateFieldError
├── LatheNormalizationError   (absorbs normalizer.py:NormalizationError)
├── LatheBackendError         (absorbs backends.py:BackendResolutionError)
├── LatheBuildError           (absorbs executor.py:BuildError)
├── LathePatchAPIError        (absorbs patch_api.py:PatchAPIError)
├── LatheProviderError        (absorbs shape_providers.py:ShapeProviderError — keep RuntimeError MRO via multi-inherit or document break)
│   ├── ShapeProviderUnavailable
│   ├── ShapeProviderExecutionError
│   ├── ShapeMeshLoadError
│   └── ShapeMeshAnalysisError
└── LatheExecutionError
    └── BlenderExecutionError
```

Contract (`docs/error_handling.md`):
1. Every caught exception re-raised with `from exc` or logged at ERROR with full traceback.
2. No `except Exception` without inline `# noqa: BLE001` + reviewer-approved comment that names concrete classes ruled out.
3. CLI maps each class to stable exit code (2=config, 3=resolver, 4=provider, 5=execution, 6=parse, 7=build). Versioned in `docs/cli_exit_codes.md` — additive only.
4. Every error carries `code` (machine) + `message` (human) + `details` (dict).
5. Existing error-class names are preserved for one release cycle via module-level re-exports; removal ships in V1.4 with migration note.

## 5. Observability

Adopt `structlog` (stdlib fallback). Every provider/adapter fallback emits `event="provider.fallback"`, `attempted`, `actual`, `reason`, `strict`, `build_id`. Trace JSON gets top-level `fallbacks: [...]` surfaced by `lathe doctor --last-build` and new `lathe trace <build_id>`. CI asserts hero build traces have zero fallbacks under stock config.

## 6. Provider Strict-Mode Default

Ties to Product Quality plan. Flip `DEFAULT_RUNTIME_CONFIG["shape"]["strict"]` to `True` when non-auto provider explicitly selected. Auto-mode retains permissive fallback for smoke ergonomics, but fallback under auto now emits exit 0 + non-zero `warn_count` gate-able in CI. Migration note in `docs/v08_migration_guide.md`.

## 7. Fuzz Testing Scope

- **Parser** (`lathe/parser.py`) — Hypothesis strategies from `grammar/lathe.lark` terminals; 10k iterations nightly; assert parse→normalize→checker never raises non-`LatheError`.
- **Normalizer** — property: idempotence (`normalize(normalize(x)) == normalize(x)`) + schema conformance.
- **Runtime config loader** — Hypothesis over arbitrary JSON trees; assert returns valid dict or raises `RuntimeConfigError`; nothing else escapes.

## 8. Bug-Bash Ritual

2-hour bash per milestone (V1.3.1 → V1.4 → ...), Thursday before tag:
1. Each engineer runs `scripts/lathe_asset_loop.sh` on unfamiliar example with randomized runtime config.
2. File issues tagged `bug-bash-<milestone>`.
3. Triage within 24h; Critical/Major block the tag.
4. Retro in `docs/retros/<milestone>.md` tracks escape-rate since previous bash.

## 9. Measurable 10/10 Criteria

- Zero open Critical or Major findings
- Every bug in Phases 1-4 has `tests/bugs/test_bug_<ID>.py` green in CI
- Ruff + bandit + semgrep green on `lathe/` with zero inline waivers except audited ones (M8 deliverable)
- mypy-strict gradual-typing rollout started on new modules; tracked but not a gate
- Zero production `assert` statements in `lathe/` (M9 deliverable)
- Cold-clone regression moved to Plan 04 (Tests); not a Plan 10 criterion
- **MTTF:** Critical ≤2 business days, Major ≤5, Minor ≤10; rolling 90-day tracked in `docs/retros/`
- **Escape rate:** <1 Critical/Major per milestone reaches users
- Every new bug report ships its fix with a dedicated regression test before merge. No exceptions.

---

## Relevant files

- `lathe/shape_providers.py` (C1, C2, M1, M5, M6)
- `lathe/shape_backend.py` (M3, Mi2)
- `lathe/runtime_config.py` (M2)
- `lathe/blender_execution.py` (M4)
- `lathe/executor.py` (M4b, Mi3)
- `lathe/scaffold_compiler.py` (Mi3)
- `lathe/resolver.py` (Mi1)
- `lathe/` codebase-wide (M8, M9)
- `pyproject.toml` (M7)
- **New:** `lathe/errors.py`, `lathe/constants.py`, `schema/runtime_config.schema.json`, `docs/error_handling.md`, `docs/error_migration_v1.md`, `docs/cli_exit_codes.md`, `docs/exception_audit.md`, `.gitignore`, `tests/bugs/`, `tests/bugs/test_no_blind_excepts.py`, `tests/bugs/test_no_production_asserts.py`, `.github/workflows/lint.yml`, `requirements.lock`

---

## Amendment log (2026-04-23)

Applied from `plans/reviews/10_bugs_errors_review.md` (score 5.5/10) and meta-review cross-cutters:

1. **C3 removed** — Review §1 (C3: ALREADY FIXED). Guard at `shape_providers.py:442` already raises `ShapeProviderExecutionError(code="missing_image_ref")`. Kept as top-of-document note for provenance.
2. **Mi5 removed** — Review §1 (Mi5: ALREADY FIXED / contradicted). `.venv` check confirms trimesh 4.11.5 present. Cold-clone regression re-homed to Plan 04 bootstrap phase.
3. **Mi3 citations corrected** — Review §1 (Mi3: HALLUCINATED at `shape_providers.py:58-59`). The `7919` literal does not appear there. Correct sites are `executor.py:1176`, `shape_backend.py:59`, `scaffold_compiler.py:29`. Fix direction (named constant) retained; relocated to `lathe/constants.py::RNG_PRIME_OFFSET`.
4. **C2 description corrected** — Review §1 (C2: Partially correct). Original text claimed "returns silent `0`"; actual behavior is a BFS fallback that returns a computed count from BFS. Description rewritten to reflect BFS-fallback framing; fix narrowed to `(AttributeError, IndexError, ValueError)` and DEBUG log on fallback engagement; no `ShapeMeshAnalysisError` raise.
5. **M4b added** — Review §2 (missed bugs) + §1 (M4 notes). Second identical subprocess-without-stderr-scan site at `executor.py:1548` in `_run_blender_topology`. Same fix pattern as M4.
6. **M8 added** — Review §2 flagged ~27 `except Exception` sites across 12 files (only 2 addressed in original plan). Now a codebase-wide sweep with per-site audit + catalog in `docs/exception_audit.md` + regression test pinning baseline.
7. **M9 added** — Review §2 flagged 17 production `assert` statements (stripped under `python -O`). Sweep converts invariants to `LatheError` raises; grep-test prevents regression.
8. **Phase 4.5 added** — Review §3 (exception-hierarchy compatibility). Existing `ShapeProviderError(RuntimeError)` and 6 other orphan error classes were not acknowledged in original plan. New phase audits + reconciles before `lathe/errors.py` lands; uses module-level re-exports for one release cycle; ships `docs/error_migration_v1.md`.
9. **TRY200 dropped** — Review §4 (static-analysis mapping). `TRY200` was removed/renamed in ruff 0.1.9. Replaced with `B904` (raise-from, already listed) + `TRY201` (verbose-raise). Added note in Prevention table.
10. **mypy-strict descoped** — Review §7 (feasibility). Full-package `--strict` is a multi-quarter effort; plan now rolls out gradual typing on new modules only; not a 10/10 gate.
11. **trimesh.exceptions.\* corrected** — Review §1 (C1). That submodule path is not canonical; C1 fix now cites concrete classes `(OSError, ValueError, KeyError, IndexError)` per review guidance.
12. **Triage/phases narrative updated** — reflects C3/Mi5 removal and M4b/M8/M9/Phase-4.5 additions. Finding count updated from 15 to 16.
13. **pyproject torch pin flagged** — Review §1 (M7). `torch>=2.11.0` is suspicious vs current stable 2.5.x. M7 row now calls out verification/correction as part of the fix.
