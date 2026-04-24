# Wave 3 Backlog

Items escaped from Wave 2 that need Wave 3 attention. Extracted from the three reviewer reports under `plans/reviews/wave2_*`. Grouped by urgency; each item has a source reference and acceptance criteria.

## P0 — must land early in Wave 3 (blocks Plan 01 exit criteria)

### BL-1. Codebase-wide bare-except narrow (M8)

- **Scope:** 23 `except Exception` sites across 15 files in `lathe/` outside Wave 2's decomposition targets.
- **Owner:** single surgeon, Stage 3.I.
- **Acceptance:** `grep -rn "except Exception" lathe/` returns either zero matches or only narrowed re-raises with `# noqa: BLE001` comments explaining the third-party contract. Add ruff rule `BLE001` to CI as the permanent guard. Add `tests/bugs/test_no_blind_excepts.py` that fails if the count regresses.
- **Effort:** 1.5 days.
- **Source:** Plan 10 M8 (post-amendment); reviewer-plan-audit.

### BL-2. Production `assert` conversion (M9)

- **Scope:** 16 `assert` statements across 6 files in `lathe/` (excluding `tests/`). Production `assert` is stripped with `python -O`.
- **Acceptance:** Convert each to `if not ...: raise LatheError(...)`. Add `tests/bugs/test_no_production_asserts.py` grep guard.
- **Effort:** 0.5 day.
- **Source:** Plan 10 M9; reviewer-code-hygiene + reviewer-plan-audit.

### BL-3. Stale `Stage 2.V` TODO removal

- **Scope:** 3 TODO comments referencing Stage 2.V that are now resolved.
- **Acceptance:** `grep -rn "Stage 2\.V" lathe/` returns zero. Single housekeeping commit.
- **Effort:** 10 min.
- **Source:** reviewer-code-hygiene.

## P1 — complete Plan 01 LOC-cap exit criteria

Each file exceeds the plan's ≤500 LOC ceiling and was not in Wave 2's scope. Decompose per Plan 01 Phase 7 guidance (cohesion first, not just LOC).

| ID | File | LOC | Proposed split |
|---|---|---:|---|
| BL-4 | `lathe/checker.py` | 856 | `lathe/checker/` package — semantic rules per stage |
| BL-5 | `lathe/blueprints/__init__.py` | 717 | Split by family (hard-surface, mechanical, soft-surface) |
| BL-6 | `lathe/cli.py` | 625 | Split by command group (doctor, check, plan, build, test, bench, inspect, bridge) |
| BL-7 | `lathe/capabilities.py` | 622 | Extract SSRF/probe helpers to `lathe/net.py`; keep capabilities thin |
| BL-8 | `lathe/resolver.py` | 540 | Borderline; split only if Phase 7 audit shows multi-concern |

- **Owner:** team of file-cluster surgeons, Stage 3.II (parallelizable).
- **Acceptance:** every `lathe/**/*.py` file ≤500 LOC; pytest 70/70; all shims work.
- **Effort:** 4–5 days.

## P2 — Plan 07 completeness

### BL-9. 26-site `json.loads` audit

- **Scope:** every `json.loads` / `json.load` call in `lathe/` (26 sites across ~10 files).
- **Acceptance:** each site either routes through `lathe/validation.py::validate_json(path, schema_id)` with a schema OR carries an inline comment classifying it as an internal controlled payload. Audit output lives at `docs/security/json_ingress_audit.md` (new).
- **Effort:** 1 day.
- **Source:** Plan 07 Phase 1 step 4; reviewer-plan-audit.

### BL-10. Blender subprocess env-allowlist scrubbing

- **Scope:** both Blender subprocess sites (`blender_execution.py`, `core/stages/topology.py`). Currently inherit the full parent env.
- **Acceptance:** `env=` kwarg set to an explicit allowlist (`PATH`, `TEMP`, `BLENDER_USER_CONFIG`, `BLENDER_USER_SCRIPTS`, `LATHE_BLENDER_PATH`). Refuse to inherit `LD_PRELOAD`, `PYTHONPATH`, `BLENDER_SYSTEM_SCRIPTS`, `DYLD_INSERT_LIBRARIES`.
- **Effort:** 0.5 day.
- **Source:** Plan 07 Phase 4; reviewer-plan-audit.

### BL-11. Central `lathe/subproc.py::run_sandboxed`

- **Scope:** extract the stderr-scan + env-scrub + timeout + expect_files logic into one helper.
- **Acceptance:** both Blender sites route through `run_sandboxed`; tests include mocked subprocess fixtures covering the sandbox contract.
- **Effort:** 0.5 day.

### BL-12. Migrate `capabilities.py:395` to shared `lathe/net.py::safe_urlopen`

- **Scope:** `f9de43c` added SSRF guards inline in `capabilities.py`; `a480a01` later created `lathe/net.py::safe_urlopen` for shape_providers. Unify.
- **Acceptance:** `capabilities.probe_hunyuan_endpoint` routes through `safe_urlopen`; no duplicated SSRF logic.
- **Effort:** 0.25 day.
- **Source:** surgeon-blender-cap TODO; reviewer-plan-audit.

## P3 — surgeon-flagged cleanups (deferred from Wave 2 "no-behavior-change" discipline)

### BL-13. Dead-code deletion

- **Scope:** 9 symbols preserved byte-for-byte in the shape decomposition with no remaining call sites:
  - `_generate_conditioned_candidates`, `_generate_reconstruct_candidates`, `_generate_adapt_candidates`, `_generate_assemble_candidates` (shape/geometry/candidates.py)
  - `_mechanical_named_meshes`, `_env_module_named_meshes`, `_runtime_from_external_mesh`, `_score_candidate` (shape/geometry/*)
  - `generate_candidate_mesh` (core/geometry.py)
- **Acceptance:** confirm no external callers in repo (`grep -rn <name> lathe/ tests/`); delete symbol; pytest 70/70.
- **Effort:** 0.5 day.
- **Source:** surgeon-shape-backend + wave2-executor reports.

### BL-14. Pre-existing bare except at `_resolve_ref_path`

- **Scope:** one `except Exception` in `lathe/shape/geometry/conditioning.py::_resolve_ref_path` (pre-existed before Wave 2; rolls up under M8).
- **Effort:** merges into BL-1.

### BL-15. `trace_manifest` indentation block

- **Scope:** pre-existing slightly-mismatched indent around `shape_assessment` / `reference_ir` / `fit_ir` / `transfer_ir` / `kit_ir` in `lathe/core/stages/package.py::_build_trace`. Output JSON unchanged; cosmetic only.
- **Effort:** 0.1 day.
- **Source:** surgeon-executor report.

### BL-16. `torch>=2.11.0` pin verification

- **Scope:** pyproject.toml vggt extra pins `torch>=2.11.0`; torch 2.11 may not exist yet.
- **Acceptance:** confirm latest torch release on pypi; if 2.11 not released, loosen to `torch>=2.2,<3` and document. TODO comment above the pin should be removed once resolved.
- **Effort:** 0.25 day.
- **Source:** reviewer-bugs (original audit); reviewer-plan-audit.

## Not in Wave 3 scope

- **`lathe/core/stages/publish.py` NotImplementedError scaffold** — owned by Plan 08 Phase 1, Wave 4.
- **ADR practice + plugin registry + layering enforcement** — Plan 03 Phases 2, 3, 4, 5, 6b — Wave 4/5.
- **Full test backfill (Plan 04 Tranches A–C, Phases 4–11)** — Wave 3 parallel track (own plan doc).
- **Docs content (tutorials, cookbook, stdlib doc blocks)** — Plan 02 Phases 5, 7, 8 — Wave 3 parallel track.

## Rough Wave 3 shape

**Stage 3.I (1 day):** BL-1 + BL-2 + BL-3 as a single hygiene PR. Enables ruff rules for future enforcement.
**Stage 3.II (4–5 days, parallelizable):** BL-4 through BL-8 file decomposition.
**Stage 3.III (2 days, parallelizable):** BL-9, BL-10, BL-11, BL-12 security completeness.
**Stage 3.IV (0.5 day):** BL-13, BL-14, BL-15, BL-16 cleanups.
**Stage 3.V:** post-wave reviewer (same pattern as Wave 2).

Plus Plan 04 test-backfill and Plan 02 docs-content tracks running in parallel with the above.

Total Wave 3 effort: ~10–12 engineer days.
