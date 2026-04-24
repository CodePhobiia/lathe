# Wave 2 Plan Coverage Review

**Auditor:** reviewer-plan-audit · **Date:** 2026-04-23
**Wave 2 commit range:** `7dd9a0f..61aab04` (8 commits)

## Summary verdict

**Wave 2 scope substantially delivered**, but with two real escapes: Plan 01 Phase 3's **27-site bare-except sweep (M8)** and **17-assert conversion (M9)** did not land — exception *hierarchy* shipped (`61aab04`), but the codebase-wide narrowing/conversion sweep was deferred. Current counts: 23 `except Exception` across 15 files; 16 `assert` across 6 files. Everything else expected for Wave 2 landed; the deferred items (Plan 01 Ph 2 strict typing, Ph 8 pre-commit/CI, Plan 03 Ph 2-6b, Plan 07 Ph 2 + 5-12) are correctly out of Wave 2 scope per `EXECUTION.md`.

## Plan 01 coverage (Code Quality)

| Sub-item | Commit | Landed? |
|---|---|---|
| Phase 3 — Exception hierarchy under `LatheError` (`lathe/errors.py`) | `61aab04` | yes |
| Phase 3 — Re-parent existing error classes via shims | `61aab04` | yes (9 modules shimmed) |
| Phase 3 — `ShapeProviderError` keeps `RuntimeError` MRO via multi-inherit | `61aab04` | yes (verified in commit body) |
| Phase 3 — Bare-except sweep (27 sites → 0) | — | **NO (escape; M8)** |
| Phase 3 — Production `assert` → `LatheError` (17 → 0) | — | **NO (escape; M9)** |
| Phase 4 — `parser.py` (1666 LOC) split | `2050431` | yes (9 modules ≤500 LOC) |
| Phase 4b — `executor.py` (2315 LOC) split into `lathe/core/stages/*` | `b087176` | yes (399 LOC dispatcher + 12 stage modules) |
| Phase 5 — `shape_providers.py` (998 LOC) split into `lathe/providers/*` | `a480a01` | yes (all files ≤400 LOC) |
| Phase 7 — `RNG_PRIME_OFFSET` extracted to `lathe/constants.py` | `54b8ae8` | yes (3 sites updated) |
| Phase 7 — Resolver silent-skip comprehensions → explicit `for` w/ debug log | `8e70aa3` | yes (5 sites at `:292`, `:433`, `:437-:439`) |
| Phase 7 — `_root_name` nested ternary → if/else | `035a45f` | yes (Mi2) |
| Phase 7 — Forbid nested ternaries (SIM108) project-wide | — | deferred (Wave 3 lint adoption) |
| Phase 2 (strict typing) | — | correctly deferred (not Wave 2) |
| Phase 8 (pre-commit + CI gate) | — | correctly deferred (Wave 3) |

## Plan 03 coverage (Architecture)

| Sub-item | Commit | Landed? |
|---|---|---|
| Phase 1 — `lathe/shape/` subpackage (graph, ir, kernel, finalize, conformance, geometry) | `035a45f` | yes (`shape_backend.py` shim 4 LOC) |
| Phase 1 — `lathe/providers/` subpackage (registry/selection/mesh_ops/adapters/transport) | `a480a01` | yes (`shape_providers.py` shim 74 LOC) |
| Phase 1 — `lathe/net.py` introduced under `Transport` boundary | `a480a01` | yes (254 LOC; Plan 07 Ph 3) |
| Phase 1 — Re-export shims for one release | `035a45f`, `a480a01` | yes |
| Phase 6a — Shallow proof stack (`uv_sheet_decal_v1`) | — | **deferred** (not in Wave 2 file-cluster table) |
| Phase 7 — `executor.py` god-module decomposition into `lathe/core/stages/*` | `b087176` | yes |
| Phase 7 — Capability-probe deduplication across 7 modules | — | **deferred** (Wave 3) |
| Phases 2, 3, 4, 5, 6b — plugin registry, layering, ADRs, validator composition, deep stack | — | correctly deferred (not Wave 2) |

## Plan 07 coverage (Security)

| Sub-item | Commit | Landed? |
|---|---|---|
| Phase 1 — `schema/runtime_config.schema.json` Draft 2020-12 | `8e70aa3` | yes |
| Phase 1 — `RuntimeConfigError` + try/except + size cap (256 KiB) + JSON-Pointer in errors | `8e70aa3` | yes |
| Phase 1 — All 26 json.loads sites audited / `docs/security/json_ingress_audit.md` | — | **deferred** (only `runtime_config.py` hardened) |
| Phase 2 — Path traversal hardening (`lathe/paths.py`, Windows hazards) | — | correctly NOT in Wave 2 scope |
| Phase 3 — `lathe/net.py::safe_urlopen` (scheme allowlist, RFC1918/loopback/CGNAT/metadata reject, TLS 1.2+, content-type pre-check, body cap) | `a480a01` | yes |
| Phase 3 — `shape_providers.py` Hunyuan migrated to `safe_urlopen` | `a480a01` | yes (`hunyuan_post_json`) |
| Phase 3 — Second SSRF site `capabilities.py:395` `probe_hunyuan_endpoint` | `f9de43c` | yes (in-place SSRF guards; carries TODO to migrate to `lathe/net.py` later) |
| Phase 4 — `blender_execution.py:210-228` stderr-scan hardening | `f9de43c` | yes |
| Phase 4 — Second subprocess site `executor.py:1548` (`_run_blender_topology`) | `b087176` | yes (now in `lathe/core/stages/topology.py::run_blender_topology`) |
| Phase 4 — `lathe/subproc.py::run_sandboxed` central wrapper | — | **deferred** (Wave 3) — both sites hardened in-place |
| Phase 4 — env scrub allowlist (`PATH`, `TEMP`, `BLENDER_USER_*`); strip `LD_PRELOAD`/`PYTHONPATH` | — | **NOT landed** (commit body does not claim it; both sites still inherit env) |

## Plan 10 finding matrix

| Finding | Expected commit | Actual commit | Status |
|---|---|---|---|
| C1 (`shape_providers.py:422-425` bare except → narrow + ShapeMeshLoadError) | `a480a01` | `a480a01` (`providers/mesh_ops.py::_load_mesh_file`) | landed |
| C2 (`:463-489` BFS-fallback narrow + DEBUG log) | `a480a01` | `a480a01` (`providers/mesh_ops.py::_mesh_body_count`) | landed |
| C3 (already fixed) | (none expected) | none | correctly skipped |
| M1 (Hunyuan content-type + 256 MiB cap + GLB sniff) | `a480a01` | `a480a01` (`providers/transport/http.py`) | landed |
| M2 (runtime_config JSON schema + size cap) | `8e70aa3` | `8e70aa3` | landed |
| M3 (`shape_backend.py:285` provider str compare normalization) | `035a45f` | `035a45f` (in `shape/backend.py`) | landed |
| M4 (Blender stderr scan + enriched return dict) | `f9de43c` | `f9de43c` | landed |
| M4b (`executor.py:1548` same hardening) | `b087176` | `b087176` (`core/stages/topology.py`) | landed |
| M5 (per-build hex prefix in candidate filenames) | `a480a01` | `a480a01` (`providers/adapters/hunyuan.py`) | landed |
| M6 (strict-mode propagates `ShapeProviderError`) | `a480a01` | `a480a01` (`providers/selection.py`) | landed |
| M7 (lockfile + dep pinning) | Wave 1 `ce41c53` | n/a (Wave 1) | correctly outside Wave 2 |
| M8 (27-site bare-except codebase sweep + `docs/exception_audit.md` + grep test) | (Wave 2) | **none** | **ESCAPE** — current count 23 across 15 files |
| M9 (17 production `assert` → `LatheError` + grep test) | (Wave 2) | **none** | **ESCAPE** — current count 16 across 6 files |
| Mi1 (resolver comprehensions → explicit for + UnresolvedNameError) | `8e70aa3` | `8e70aa3` | landed |
| Mi2 (`_root_name` nested ternary) | `035a45f` | `035a45f` (`shape/geometry/candidates.py`) | landed |
| Mi3 (`7919` magic → `RNG_PRIME_OFFSET`, correctly cited at 3 files) | `54b8ae8` | `54b8ae8` | landed (re-cited per reviewer-bugs note in commit body) |
| Mi4 (.gitignore + transient dirs) | Wave 0/1 `7dd9a0f`/`6589f4a` | confirmed (`.gitignore` present, ignores `dist_*/`, `tmp_*/`, `warm_*/`, `v05_*/`, `cache_probe_*/`, `external/vggt/`) | correctly outside Wave 2 |
| Mi5 (already fixed) | (none) | none | correctly skipped |

## Cross-plan arbitration honor-check (per meta-review)

| Item | Expected | Verified |
|---|---|---|
| `executor.py` decomp in BOTH Plans 01 + 03 | `b087176` | yes — single commit satisfies both plans |
| Second SSRF site `capabilities.py:395` | `f9de43c` | yes |
| Second subprocess site `executor.py:1548` | `b087176` | yes (relocated to `core/stages/topology.py`) |
| `external/vggt/` ignore-not-vendor decision | Wave 0 `.gitignore` | yes — `.gitignore` line: `external/vggt/` |
| 94 transient dirs cleanup script | Wave 1 `scripts/clean_workspace.{sh,ps1}` | yes — both files present |
| Apache-2.0 justification fix in Plan 02 | Wave 1 docs | not in Wave 2 scope |

## Wave-3 backlog from surgeon follow-ups (verified present in tree)

1. **Dead code in shape pipeline** (verified in `lathe/core/geometry.py`, `lathe/shape/geometry/candidates.py`): `_generate_*_candidates`, `_mechanical_named_meshes`, `_env_module_named_meshes`, `_runtime_from_external_mesh`, `_score_candidate`, `generate_candidate_mesh`. Owner: Plan 03 Phase 7 round-2 / Plan 01 Phase 6 docstring sweep.
2. **Pre-existing bare except** at `lathe/shape/geometry/conditioning.py:36` (`_resolve_ref_path`) — confirmed `except Exception:  # noqa: BLE001` still present. Counts toward M8.
3. **`trace_manifest` indentation** at `lathe/core/stages/package.py::_build_trace` (line 107 area) — needs surgeon recheck against original `executor.py::_build_trace` block.
4. **`torch>=2.11.0` suspicious pin** at `pyproject.toml:71` — still unfixed; Wave 1 `ce41c53` left it as TODO. Belongs to Plan 10 M7 follow-up.
5. **`lathe/core/stages/publish.py::run`** raises `NotImplementedError("publish stage is scaffolded; Plan 08 Phase 1 will implement it")` — owner Plan 08 Phase 1.
6. **`capabilities.py:395` SSRF guard** carries `TODO(Stage 2.V)` to migrate from in-place guard to `lathe/net.py::safe_urlopen` (per `f9de43c` body). Plan 07 follow-up.
7. **`lathe/subproc.py::run_sandboxed` central wrapper** never created; both subprocess sites hardened in-place. Plan 07 Phase 4 step 1 follow-up.
8. **Subprocess env-allowlist scrub** (Plan 07 Phase 4 step 1) — neither site (`blender_execution.py`, `core/stages/topology.py`) scrubs `LD_PRELOAD`/`PYTHONPATH`/`BLENDER_SYSTEM_SCRIPTS`. Wave 3 owner.

## Escapes (plan items expected in Wave 2 that didn't land)

1. **Plan 01 Phase 3 / Plan 10 M8** — bare-except sweep (still 23 sites across 15 files). Hierarchy landed in `61aab04`; the 27-site narrowing did not. The new exception classes are available but unused at most call sites.
2. **Plan 01 Phase 3 / Plan 10 M9** — `assert` conversion (still 16 sites across 6 files: `assembly_kernel.py`, `exact_solids.py`, `geometry_kernel.py`, `scaffold_compiler.py`, `core/stages/shape.py`, `validators/visual_quality.py`). No commit attempted this.
3. **Plan 07 Phase 1 step 4** — 26-site `json.loads` audit and `docs/security/json_ingress_audit.md` not produced; only `runtime_config.py` validated.
4. **Plan 07 Phase 4 env-scrub** — both Blender subprocess sites hardened for stderr-scan but env-allowlist scrubbing was not applied; matched-pattern + tail logging shipped without env hardening.
5. **Plan 07 Phase 4 `lathe/subproc.py`** central wrapper deferred; in-place hardening shipped instead — risks divergence between the two sites on next refactor.

These five items must be picked up by Wave 3 (security + code-hygiene tracks) or formally re-scoped.

**Word count: ~1080**
