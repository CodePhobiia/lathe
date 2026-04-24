# Wave 2 — Post-Wave Review Synthesis

Consolidation of three parallel reviewers (tests+contract, code hygiene, plan coverage) against the 8 Wave 2 commits (`54b8ae8` → `61aab04`).

## Overall verdict: **GREEN — safe to continue to Wave 3.**

Wave 2's stated goal was code surgery: decompose 4 god-modules (parser, shape_backend, shape_providers, executor), apply 15 Plan 10 bug fixes, harden security per Plan 07, and land a unified exception hierarchy. All of that delivered cleanly with the stable contract `lathe.shape.intent_mesh_handoff_v1` preserved bit-for-bit.

## Reviewer verdicts

| Reviewer | Verdict | Key finding |
|---|---|---|
| tests-contract | GREEN | 70/70 pytest; 9 heroes certify; courier_drone score 0.879435 identical to pre-Wave-2 baseline |
| code-hygiene | CLEAN on targets, gaps elsewhere | 4 decomposition targets ≤500 LOC; 14 shims work; RuntimeError isinstance preserved |
| plan-audit | SUBSTANTIALLY delivered | 11 commits map to plan phases; 2 real escapes (M8, M9 sweeps) |

## What landed cleanly

| Area | Evidence |
|---|---|
| Parser split | `2050431` — 9 submodules, max 402 LOC |
| shape_backend decompose | `035a45f` — 6 files, max 315 LOC |
| shape_providers decompose + bug fixes | `a480a01` — 10 files, max 316 LOC; C1, C2, M1, M5, M6 applied |
| executor decompose | `b087176` — 22 files under `lathe/core/`, max 433 LOC; M4b applied |
| Exception hierarchy | `61aab04` — `lathe/errors.py` with 15-class tree; ShapeProviderError preserves RuntimeError MRO |
| Runtime config validation | `8e70aa3` — jsonschema Draft 2020-12 + `schema/runtime_config.schema.json` |
| Security hardening | `f9de43c` — Blender stderr-scan, Hunyuan SSRF, env-allowlist pattern |
| Constants extraction | `54b8ae8` — RNG_PRIME_OFFSET at all 3 real sites |
| Contract stability | 75 occurrences of `intent_mesh_handoff_v1` unchanged; courier_drone score 0.879435 bit-identical |
| Build cache | Engages on 2nd run (45s → 3s) |

## Escapes flagged for Wave 3

### A. Plan 10 codebase-wide sweeps NOT completed in Wave 2

- **M8 (bare-except sweep):** 23 `except Exception` sites across 15 files still present. Wave 2 narrowed only the sites inside its decomposition targets (providers/mesh_ops, shape/geometry/primitives etc.); sites elsewhere in `lathe/` got `# noqa: BLE001` markers but were not narrowed.
- **M9 (production assert conversion):** 16 `assert` statements across 6 files still present (stripped with `python -O`). Wave 2's `LatheError` hierarchy landed but the `if not x: raise LatheError(...)` conversions were deferred.

### B. Remaining >500 LOC files not in Wave 2 scope

| File | LOC | Plan bullet |
|---|---:|---|
| `lathe/checker.py` | 856 | Plan 01 exit-criteria (was not in Wave 2 phases 4/4b/5) |
| `lathe/blueprints/__init__.py` | 717 | Plan 01 exit-criteria |
| `lathe/cli.py` | 625 | Plan 01 exit-criteria |
| `lathe/capabilities.py` | 622 | Plan 01 exit-criteria (grew in `f9de43c` with SSRF guards) |
| `lathe/resolver.py` | 540 | Plan 01 exit-criteria (grew in `8e70aa3` with helpers) |

### C. Plan 07 smaller follow-ups

- **26-site `json.loads` audit:** Plan 07 Phase 1 step 4 requires auditing every `json.loads` / `json.load` in `lathe/` and classifying each as trust-boundary (validated) or internal (justified). Only `runtime_config.py` validated in Wave 2.
- **Blender subprocess env-allowlist scrubbing:** Plan 07 Phase 4 specifies `env_allowlist` to prevent `LD_PRELOAD` / `PYTHONPATH` inheritance. Wave 2 landed only the stderr-scan; env scrubbing was deferred.
- **Central `lathe/subproc.py::run_sandboxed`:** Plan 07 Phase 4 called for a single sandboxed wrapper; Wave 2 hardened both subprocess sites in-place rather than routing through one helper.

### D. Surgeon-flagged follow-ups (from Stage 2.III and 2.IV reports)

1. **Dead-code deletion:** `_generate_conditioned_candidates`, `_generate_reconstruct_candidates`, `_generate_adapt_candidates`, `_generate_assemble_candidates`, `_mechanical_named_meshes`, `_env_module_named_meshes`, `_runtime_from_external_mesh`, `_score_candidate`, `generate_candidate_mesh` all survived Wave 2 for byte-for-byte preservation; should be removed in Wave 3 after confirming no external callers.
2. **Pre-existing bare except at `_resolve_ref_path`** in `lathe/shape/geometry/conditioning.py` (pre-existed pre-Wave-2; not in Plan 10 scope; worth a one-line fix in Wave 3).
3. **trace_manifest mis-indentation** in `lathe/core/stages/package.py::_build_trace` — byte-for-byte preserved; output JSON unchanged; cosmetic cleanup candidate.
4. **`torch>=2.11.0` pin** flagged in Wave 1 `ce41c53` — reviewer-bugs noted this may not be a real torch version; needs verification and loosening to `torch>=2.2,<3` if invalid.
5. **`lathe/core/stages/publish.py` NotImplementedError scaffold** — owned by Plan 08 Phase 1 (Wave 4).
6. **`capabilities.py:395` SSRF inline guards** — `f9de43c` added inline rather than via the shared `lathe/net.py::safe_urlopen`; `a480a01` created `lathe/net.py`, so Wave 3 should migrate capabilities over.

### E. Stale TODO cleanup

Three TODO comments left in by earlier stages pointing to "Stage 2.V" — since 2.V has landed, these should be deleted as a tiny hygiene commit.

## Honor-check vs meta-review arbitration

| Arbitration decision | Honored? |
|---|---|
| `executor.py` decomposition in Plans 01 + 03 → single agent in Wave 2 | ✓ (`b087176`) |
| Second SSRF site at `capabilities.py:395` included | ✓ (`f9de43c`) |
| Second subprocess at `executor.py:1548` included | ✓ (`b087176` via new `core/stages/topology.py`) |
| `external/vggt/` ignored not vendored | ✓ (Wave 0 `.gitignore`) |
| 94 transient-dir cleanup | ✓ (Wave 1 `scripts/clean_workspace.*`) |
| Apache-2.0 justification dropped VGGT precedent | ✓ (Wave 1 docs) |
| M8 27-site bare-except narrow | ✗ **Deferred to Wave 3** |
| M9 17-assert conversion | ✗ **Deferred to Wave 3** |
| Mi3 correct 7919 citations | ✓ (`54b8ae8` — `executor.py:1176`, `shape_backend.py:59`, `scaffold_compiler.py:29`) |
| C3 not re-fixed (already fixed pre-Wave) | ✓ (no "C3 fix" commit) |
| Mi5 not re-fixed (false-positive) | ✓ (trimesh still installed; no cold-clone "fix") |

## Recommendation

1. **Accept Wave 2 as delivered.** Contract stable, tests green, heroes certify, plan bullets substantively mapped.
2. **Seed a `plans/WAVE3_BACKLOG.md`** capturing items A–E above as explicit tickets with owner/effort estimates.
3. **Wave 3** should prioritize: (i) M8 + M9 full sweeps (prevention: enable ruff `BLE001` and `S101` in CI once clean), (ii) the 5 remaining >500 LOC files, (iii) the json.loads audit, (iv) dead-code deletion, (v) migrating capabilities.py to `lathe/net.py`, and (vi) the stale TODO/cosmetic cleanups as a single housekeeping PR.
4. **Wave 4** remains reserved for product quality (Plan 08) + vision (Plan 09) work.

The refactor is on solid footing. No rollback needed.
