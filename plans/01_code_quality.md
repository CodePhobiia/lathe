# Implementation Plan: Code Quality 7/10 → 10/10

## Overview
Raise Lathe's Python code quality to 10/10 by introducing enforced linting/formatting/typing, decomposing **eight** oversized modules that violate the ≤500 LOC cap (`executor.py` 2315, `parser.py` 1666, `shape_providers.py` 998, `checker.py` 856, `blueprints/__init__.py` 717, `shape_backend.py` 665, `cli.py` 625, `blender_execution.py` 558), installing a disciplined exception hierarchy rooted at `LatheError`, eliminating all 27 `except Exception` sites and 17 production `assert` statements, and gating everything on pre-commit + CI. No behavioral changes to public contracts (esp. `lathe.shape.intent_mesh_handoff_v1`).

---

## Phase 1 — Tooling Baseline (0.5 day)

**Acceptance:** `ruff check .`, `ruff format --check .`, and `mypy lathe` all run green on current code after auto-fix pass.

1. Edit `pyproject.toml` — add under `[project.optional-dependencies].dev`: `ruff>=0.6`, `mypy>=1.11`, `pre-commit>=3.8`, `types-jsonschema`, `types-Pillow`.
2. Append new sections to `pyproject.toml`:
   - `[tool.ruff]` — `line-length = 110`, `target-version = "py311"`, `src = ["lathe"]`.
   - `[tool.ruff.lint]` — `select = ["E","W","F","I","B","UP","SIM","RET","C90","N","D","PL","TRY","BLE","PTH","RUF"]`, `ignore = ["D203","D213","PLR0913"]`, `mccabe.max-complexity = 12`.
   - `[tool.ruff.lint.per-file-ignores]` — `"tests/*" = ["D","PLR2004"]`, `"grammar/*" = ["ALL"]`.
   - `[tool.ruff.lint.pydocstyle]` — `convention = "google"`.
   - `[tool.ruff.format]` — single formatter supersedes black/isort.
3. Run `ruff check --fix --unsafe-fixes .` then `ruff format .`; commit the mechanical sweep separately from the config commit.

---

## Phase 2 — Static Typing Ramp (1–1.5 days)

**Acceptance:** `mypy lathe` passes at `--strict` for modules in the "strict tier"; ≥80% expression-level coverage project-wide.

1. Add `[tool.mypy]` — `python_version = "3.11"`, `strict = false` globally, `warn_unused_ignores = true`, `warn_redundant_casts = true`, `disallow_untyped_defs = true`, `check_untyped_defs = true`.
2. Per-module overrides:
   - Strict tier (pass `--strict`): `lathe.parser.*`, `lathe.normalizer`, `lathe.resolver`, `lathe.checker`, `lathe.planner`, `lathe.shape_ir`, `lathe.asset_graph`, `lathe.conformance`, `lathe.backends`, `lathe.cli`, `lathe.errors`.
   - Lenient tier: `lathe.shape_providers.*`, `lathe.executor`, validators, bridge.
   - Third-party: `module = ["trimesh.*","lark.*","xatlas.*","torch.*","torchvision.*"]`, `ignore_missing_imports = true`.
3. Add `scripts/check_type_coverage.py` using `mypy --any-exprs-report`; wire to CI. Target: **≥85%** non-Any expression coverage on strict tier, ≥70% overall.
4. Introduce `lathe/types.py` (`AssetDict`, `ProgramDict`, `ShapeBundle`, `ProviderConfig`, `RuntimeConfig` TypedDicts).

---

## Phase 3 — Exception Hierarchy & Assertion Cleanup (1 day)

**Acceptance:** zero `except Exception` without an explicit re-raise/log (**27 sites across 12 files** → 0); ruff `BLE001` clean; all 17 production `assert` statements converted to explicit raises; all Lathe-originating errors derive from `LatheError`.

New file `lathe/errors.py`:
```
LatheError
├── LatheParseError
│   └── DuplicateFieldError
├── ResolutionError
├── CheckerError
├── BackendError
│   ├── ShapeProviderError
│   │   ├── ShapeProviderUnavailable
│   │   └── ShapeProviderExecutionError
│   ├── TopologyAdapterError
│   └── UVAdapterError
├── ContractViolation
└── RuntimeConfigError
```

1. Re-export from old modules (stable public surface). Re-parent the de-facto exception classes that already exist (`LatheParseError`, `DuplicateFieldError` in `parser.py`; `ShapeProviderError`, `ShapeProviderExecutionError` in `shape_providers.py`; `ResolutionError` in `resolver.py`; `BackendResolutionError` in `backends.py`; `NormalizationError` in `normalizer.py`; `BuildError` in `executor.py`; `PatchAPIError` in `patch_api.py`) under `LatheError`, keep import shims at their original locations.
2. Fix silent swallows at `lathe/shape_providers.py:424` (`_load_mesh_file`) — catch specific exceptions (`ValueError`, `OSError`, `trimesh.exceptions.*`) and log at DEBUG. At `:466` (`_mesh_body_count`), **this is a BFS connected-components fallback, not a silent swallow** — narrow the exception to `AttributeError`/`NotImplementedError` raised by older trimesh versions lacking `body_count`.
3. **Full bare-except sweep — 27 sites across 12 files.** Run `grep -rn 'except Exception' lathe/` and narrow every site; `executor.py` alone holds ≥8 sites, `shape_providers.py` holds 5 (`:424`, `:466`, `:732`, `:920`, `:927`), `exact_solids.py` holds 4, plus `shape_backend.py:87`, `validators/visual_quality.py:58,239`, and others. Each must (a) narrow, (b) re-raise as `LatheError`, or (c) carry a comment explaining the third-party contract. Remove the trailing `# noqa: BLE001` pragma at each site after narrowing.
4. **Convert all 17 production `assert` statements** in `lathe/` to explicit `if not ...: raise LatheError(...)` form — `assert` is stripped when Python is run with `-O`, so these provide no guarantee in production. Tests may keep asserts.

---

## Phase 4 — Decompose `parser.py` (1666 LOC → ≤500 LOC each) (1 day)

**Acceptance:** no file in `lathe/parser/` exceeds 500 LOC; public surface `from lathe.parser import parse_file, parse_text` unchanged; all tests pass.

| New module | Contains | Approx LOC |
|---|---|---|
| `lathe/parser/__init__.py` | Public re-exports | ~40 |
| `lathe/parser/grammar.py` | grammar loader, cache, helpers | ~200 |
| `lathe/parser/transformer.py` | `_LatheTransformer` (split by block family if >500) | ~500 |
| `lathe/parser/fast_parser.py` | `_TokenStream`, `_FastParser` | ~500 |
| `lathe/parser/imports.py` | `_merge_programs`, `parse_file`, `parse_text` | ~100 |

Guardrail: new test `tests/test_parser_public_api.py` imports only through `lathe.parser` to freeze the public surface.

---

## Phase 4b — Decompose `executor.py` (2315 LOC → ≤500 LOC each) (1.5 days)

**Acceptance:** `lathe/executor.py` becomes a thin dispatcher ≤500 LOC; the 940-line `BuildExecutor` god-class is broken up; public imports (`BuildExecutor`, `BuildError`, stage dispatch entry points) unchanged; all tests pass; `STAGE_ORDER` preserved.

Split per-stage step bodies into dedicated modules under `lathe/core/stages/`:

| New module | Contains |
|---|---|
| `lathe/executor.py` | Thin dispatcher — `BuildExecutor` shell, `STAGE_ORDER`, per-stage delegation (~≤500 LOC) |
| `lathe/core/stages/shape.py` | Shape stage step body |
| `lathe/core/stages/topology.py` | Topology stage step body |
| `lathe/core/stages/uv.py` | UV stage step body |
| `lathe/core/stages/surface.py` | Surface stage step body |
| `lathe/core/stages/execution.py` | Execution stage step body (incl. Blender subprocess at `executor.py:1548` — hardening owned by Plan 07) |
| `lathe/core/stages/rig.py` | Rig stage step body |
| `lathe/core/stages/interfaces.py` | Interfaces stage step body |
| `lathe/core/stages/physics.py` | Physics stage step body |
| `lathe/core/stages/optimize.py` | Optimize stage step body |
| `lathe/core/stages/validate.py` | Validate stage step body |
| `lathe/core/stages/package.py` | Package stage step body |
| `lathe/core/stages/publish.py` | Publish stage step body |
| `lathe/core/runtime.py` | Runtime config glue, provider wiring |
| `lathe/core/seeding.py` | Random-seed helpers (moves `7919` callsite at `executor.py:1176` here; imports `RNG_PRIME_OFFSET` from `lathe/constants.py`) |
| `lathe/core/bake_helpers.py` | Bake plumbing extracted from `BuildExecutor` |

Because `executor.py` holds ≥8 of the 27 `except Exception` sites, Phase 3's narrowing sweep must land **before** this split so each stage module inherits already-narrowed handlers. This split also unblocks Phase 2 — moving `executor.py` from the lenient tier to strict-tier (see Exit Criteria) becomes tractable once each stage module is a bounded unit.

Guardrail: new test `tests/test_executor_public_api.py` imports only `BuildExecutor`, `BuildError`, and stage dispatch entry points from `lathe.executor` to freeze the public surface.

---

## Phase 5 — Decompose `shape_providers.py` (≈1000 LOC → ≤350 LOC each) (1 day)

**Acceptance:** no provider-related file exceeds 400 LOC; network I/O isolated from geometry math.

| New module | Contains |
|---|---|
| `__init__.py` | Public API re-exports |
| `registry.py` | `PROVIDERS`, `PROVIDER_ALIASES`, `get_provider`, `normalize_provider_id` |
| `selection.py` | `resolve_shape_provider`, `maybe_run_shape_provider`, probes |
| `mesh_ops.py` | Mesh load/analyze/normalize helpers |
| `hunyuan_http.py` | HTTP provider + `_select_primary_image` |
| `vggt_local.py` | VGGT provider + point-map triangulation |

---

## Phase 6 — Docstrings & Naming (0.5 day)

**Acceptance:** ruff `D` rules pass on `lathe/`; every public symbol has a Google-style docstring with `Args`, `Returns`, `Raises`.

1. Enable ruff `D` rules.
2. Sweep top-down; prioritize `cli.py`, `planner.py`, `executor.py`, `backends.py`, `checker.py`.
3. Naming audit: enforce `snake_case` / `PascalCase` (ruff `N`).

---

## Phase 7 — Code Smell Cleanup (0.5 day)

**Acceptance:** ruff `C901` (complexity ≤12), `PLR0915` (statements ≤50), `PLR2004` (magic values) clean.

1. Magic number `7919` → `RNG_PRIME_OFFSET` in new `lathe/constants.py`. **The constant is NOT in `shape_providers.py`** — correct call sites are `executor.py:1176`, `shape_backend.py:59`, `scaffold_compiler.py:29`. Update all three to import from `lathe.constants`.
2. Decompose any function >50 statements.
3. Refactor nesting >4 deep with early-return guards.
4. Resolver comprehension audit — rewrite the five silent-skip comprehension sites in `resolver.py` as explicit `for` loops with logged skips at WARN (or raise in strict mode): `resolver.py:292`, `resolver.py:433`, `resolver.py:437`, `resolver.py:438`, `resolver.py:439`. All five use the `if item in self.*_map` pattern and silently drop unknown references today.
5. Forbid nested ternaries (`SIM108`).

---

## Phase 8 — Pre-commit + CI Gate (0.5 day)

**Acceptance:** `pre-commit run --all-files` green; CI fails on lint/type/test regression.

1. New `.pre-commit-config.yaml` with hooks: ruff (check + format), mypy (local hook), check-yaml, end-of-file-fixer, trailing-whitespace, check-merge-conflict, check-added-large-files (`--maxkb=512`, exclude `examples/refs/**`).
2. Bootstrap scripts: add `pre-commit install` when `--dev` is set.
3. New `.github/workflows/quality.yml`: ruff + mypy (strict tier) + `pytest -q` + type-coverage script.

---

## Exit Criteria — Measurable 10/10

| Metric | Current | Target |
|---|---|---|
| LOC per file `lathe/` (max) | 2315 | **≤500** |
| LOC per file `lathe/` (p95) | unknown | **≤350** |
| Files violating ≤500 LOC cap | **8** (`executor.py` 2315, `parser.py` 1666, `shape_providers.py` 998, `checker.py` 856, `blueprints/__init__.py` 717, `shape_backend.py` 665, `cli.py` 625, `blender_execution.py` 558) | **0** |
| Cyclomatic complexity per function (max) | unknown | **≤12** |
| `except Exception` without narrowing | **27 across 12 files** | **0** |
| Production `assert` statements (`lathe/`) | **17** | **0** |
| Ruff rule groups enabled | 0 | **15** |
| Ruff violations on `main` | unknown | **0** |
| Mypy strict-tier modules | 0 | **≥11** |
| Non-Any expression coverage (strict tier) | unknown | **≥85%** |
| Non-Any expression coverage (project) | unknown | **≥70%** |
| Public-symbol docstring coverage | partial | **100%** |
| Magic-number occurrences outside `constants.py` | ≥3 | **0** |
| Pre-commit hooks installed & passing | no | **yes** |
| CI quality gate | absent | **blocks merge** |
| Lathe exception hierarchy rooted at `LatheError` | partial | **all** |

**Note on Phase 2 tier assignment:** `executor.py` cannot remain in the lenient tier if the exit criteria (complexity ≤12, `C901`/`PLR0915` clean) are to be met project-wide. After Phase 4b splits it into bounded stage modules, promote the resulting `lathe/core/stages/*` and `lathe/core/runtime.py` into the strict tier.

**Total estimated effort:** ~10–12 engineer-days (executor.py decomposition adds 3–4 days over the original 5–6d estimate; the broader 27-site bare-except sweep adds another 1–2 days). Parallelizable after Phase 1 to ~6–7 calendar days with two engineers.

**Non-goals:** behavioral changes to the shape contract, renaming public language surface, grammar changes.

---

## Relevant file paths

- `pyproject.toml` — tooling config (Phases 1, 2)
- `lathe/parser.py` — split in Phase 4
- `lathe/shape_providers.py` — split in Phase 5; bare-except at 424, 466
- `lathe/resolver.py` — comprehension audit in Phase 7
- `lathe/executor.py` — split in Phase 4b; holds ≥8 `except Exception` sites; `7919` magic-number site at `:1176`; second unhardened Blender subprocess at `:1548` (hardening owned by Plan 07)
- `lathe/shape_backend.py`, `lathe/scaffold_compiler.py` — `7919` magic-number sites at `:59` and `:29`
- `lathe/checker.py`, `lathe/blueprints/__init__.py`, `lathe/cli.py`, `lathe/blender_execution.py` — other >500 LOC files to split or flag
- `scripts/bootstrap_local.ps1` / `.sh` — wire `pre-commit install`

---

## Amendment log (2026-04-23)

Changes applied against `plans/reviews/01_code_quality_review.md` and the cross-cutting items in `plans/reviews/00_meta_review.md`:

- **Added Phase 4b — `executor.py` decomposition.** The review (and three independent meta-reviewers) flagged `executor.py` at 2,315 LOC as the largest file in the repo and the single biggest code-quality gap; the original plan left it untouched. Phase 4b splits the 940-line `BuildExecutor` god-class into per-stage modules under `lathe/core/stages/` plus `runtime.py`, `seeding.py`, and `bake_helpers.py`, leaving `executor.py` as a thin dispatcher ≤500 LOC.
- **Listed all 8 files violating the ≤500 LOC cap** in the Overview and Exit Criteria table: `executor.py`, `parser.py`, `shape_providers.py`, `checker.py`, `blueprints/__init__.py`, `shape_backend.py`, `cli.py`, `blender_execution.py`. Original plan only called out two.
- **Expanded bare-except inventory from "≥2" to "27 sites across 12 files"** in Phase 3 and the Exit Criteria. Added the directive to run `grep -rn 'except Exception' lathe/` and named the heavy concentrations (`executor.py` ≥8, `shape_providers.py` 5, `exact_solids.py` 4). Called out that `shape_providers.py:466` is a BFS fallback, not a silent swallow — narrow to `AttributeError`/`NotImplementedError` rather than treating it as a generic swallow. Added a step to strip `# noqa: BLE001` pragmas after narrowing.
- **Added 17 production `assert` statements** as a Phase 3 cleanup target — asserts are stripped with `python -O` and provide no production guarantee. Tests may keep them.
- **Corrected the magic-number `7919` call sites** in Phase 7. The review confirmed the constant is NOT in `shape_providers.py`; correct sites are `executor.py:1176`, `shape_backend.py:59`, `scaffold_compiler.py:29`. Phase 7 and the Relevant file paths section now cite the correct files.
- **Specified resolver comprehension line numbers** in Phase 7: `resolver.py:292`, `:433`, `:437`, `:438`, `:439` — previously only named generically. Behavior clarified: log at WARN (or raise in strict mode) rather than silently drop.
- **Inflated effort estimate from "5–6 engineer-days" to "~10–12 engineer-days"** — executor decomposition adds 3–4d, broader bare-except sweep adds 1–2d. Matches the review's realistic breakdown.
- **Re-parenting call-out added to Phase 3.** The review noted an unrooted de-facto exception hierarchy already exists (`LatheParseError`, `ShapeProviderError`, `ResolutionError`, `BackendResolutionError`, `NormalizationError`, `BuildError`, `PatchAPIError`); Phase 3 now explicitly re-parents these under `LatheError` with import shims for stability.
- **Phase 2 tier contradiction resolved.** Exit Criteria section now notes `executor.py` cannot remain lenient-tier once complexity ≤12 is required project-wide; after Phase 4b the resulting `lathe/core/stages/*` modules are promoted to strict tier.

Kept unchanged: the tooling baseline (ruff + mypy + pre-commit), the parser.py and shape_providers.py split plans, the Google-style docstring sweep, and the overall phase ordering — reviewers confirmed these are accurate and well-sized.
