# Review: `plans/01_code_quality.md`

## Summary verdict
The plan is accurate, well-structured, and fundamentally sound: every cited file/line in the repo checks out, the tooling baseline is realistic, and the module-split proposals fit the actual code. It will move the score meaningfully toward 10/10 but not reach it as written — the `except Exception` inventory is under-counted (27 in `lathe/` vs "≥2" implied), `executor.py` (2,315 LOC) is the largest offender and is missing from the decomposition plan, and Phase 7 silently assumes strict-tier refactors that are much heavier than the 0.5-day budget suggests.

## Coverage checklist (original findings → addressed?)

| Finding | Addressed? | Where |
|---|---|---|
| `parser.py` 1,666 LOC oversized | Yes | Phase 4 |
| `shape_providers.py` ~1,000 LOC, mixed concerns | Yes | Phase 5 |
| Bare `except Exception` at `shape_providers.py:424`, `:466` | Yes — explicit | Phase 3 step 2 |
| Inconsistent resolver comprehension semantics | Partially | Phase 7 step 4 (one line) |
| No lint/format config in `pyproject.toml` | Yes | Phase 1 |
| No type-annotation coverage tracking / mypy | Yes | Phase 2 |
| No docstring enforcement | Yes | Phase 6 (ruff `D`) |

## Citations verified

| Plan claim | Verified | Notes |
|---|---|---|
| `parser.py` == 1,666 LOC | YES | `wc -l` = 1666 |
| `shape_providers.py` ~1,000 LOC | YES | 998 |
| Bare except at `shape_providers.py:424` | YES | `_load_mesh_file` |
| Bare except at `shape_providers.py:466` | YES | `_mesh_body_count` fallback — note: the fallback path has legitimate behavior, not pure swallow |
| `7919` magic at `executor.py:1176`, `shape_backend.py:59`, `scaffold_compiler.py:29` | YES (all 3) | Only occurrences in repo |
| Parser internals `_LatheTransformer` (l.184), `_TokenStream` (l.999), `_FastParser` (l.1040), `_merge_programs` (l.161), `parse_file`/`parse_text` (l.1628/1655) | YES | Proposed split maps to real symbol boundaries |
| `resolver.py` comprehensions silently skip unknown names | YES | Lines 292, 433, 437, 438, 439 all use `if item in self.*_map` pattern with no log |
| No existing `[tool.ruff]` / `[tool.mypy]` / pre-commit / `.github/` | YES | None found anywhere in repo |
| Existing exception classes (`LatheParseError`, `DuplicateFieldError`, `ShapeProviderError`, `ShapeProviderExecutionError`, `ResolutionError`, `BackendResolutionError`, `NormalizationError`, `BuildError`, `PatchAPIError`) | YES | Proposed hierarchy is compatible |

## Hallucinations / inaccuracies

1. **Exception swallow count understated.** The plan implies only the two `shape_providers.py` sites are problematic. Actual count in `lathe/`: **27 `except Exception` across 12 files**. Notable additional sites: `executor.py` has 8, `shape_providers.py` has 5 (not 2 — also `:732`, `:920`, `:927`), `exact_solids.py` has 4, `shape_backend.py:87`, `validators/visual_quality.py:58,239`. Phase 3's "Audit every `except Exception`" bullet covers this in principle, but the exit criterion "≥2 → 0" gives a misleadingly small impression of the remediation load. Revise to "≥27 → 0" so the 0.5-day Phase 3 budget is re-scoped (realistically 1 day).
2. **`_mesh_body_count` fallback is not a silent swallow.** The `except Exception:` at `:466` is followed by a hand-rolled connected-components implementation returning the correct body count. The plan's framing ("silent swallows") is wrong for this site — it should say "narrow the exception to `AttributeError`/`NotImplementedError` raised by older trimesh versions lacking `body_count`".
3. **Parser `_FastParser` at 500 LOC is tight.** `_FastParser` spans roughly lines 1040–1627 (≈587 LOC). The plan's "~500 LOC" is an underestimate; a sub-split (e.g., by declaration family) will likely be needed to hit the ≤500 target.

## Already-done items found

- `LatheParseError` and `DuplicateFieldError` already exist in `lathe/parser.py:26,30`.
- `ShapeProviderError` and `ShapeProviderExecutionError` already exist in `lathe/shape_providers.py:82,94`.
- `ResolutionError` (`resolver.py:10`), `BackendResolutionError` (`backends.py:11`), `NormalizationError` (`normalizer.py:77`), `BuildError` (`executor.py:67`), `PatchAPIError` (`patch_api.py:9`) — a partial de-facto hierarchy already exists, unrooted. Phase 3 should explicitly call out **re-parenting these** (not just "re-export from old modules") and keep shims for import-stability.
- No bare `except:` exists in `lathe/` (only in vendored `.venv/` site-packages). Plan correctly doesn't assume any.

## Missing gaps the plan should add

1. **`executor.py` (2,315 LOC) is the largest module and is ignored.** It's nearly 1.4× parser.py and holds stage dispatch, random-seed helpers, runtime glue, and validators. The plan lists parser + shape_providers as the only oversized files but leaves the biggest one untouched. Add a Phase 4.5 (or extend Phase 4) to split executor along: `stage_dispatch.py`, `runtime.py`, `bake_helpers.py`, `seeding.py`. This is the single biggest gap.
2. **Other long files >500 LOC not flagged:** `checker.py` (856), `blueprints/__init__.py` (717), `shape_backend.py` (665), `cli.py` (625), `blender_execution.py` (558), `resolver.py` (501). Exit criterion says "≤500 LOC max" — four modules on top of executor/parser/shape_providers violate this. Plan needs either explicit split tasks or a clear exemption policy.
3. **Lenient-tier for `executor.py` contradicts exit criteria.** Phase 2 puts `executor.py` in the *lenient* tier, but Phase 7 demands `C901`/`PLR0915` cleanliness and the exit table demands complexity ≤12 project-wide — impossible without typed refactors there. Resolve the contradiction.
4. **Resolver comprehension fix is one line in a 7-line section.** Lines 292, 433, 437, 438, 439 all silently drop unknown references. Phase 7 only mentions "Resolver comprehension audit" — needs to enumerate the five sites and define behavior (log at WARN? raise in strict mode? keep silent with a comment why?).
5. **Per-file-ignores list is thin.** `grammar/*` is not a Python path (it holds `.lark`); `"grammar/*" = ["ALL"]` is a no-op. Missing: `examples/**`, `dist_*/**`, `cache_probe_*/**`, `warm_*/**`, `tmp_*/**`, `v05_*/**` (CLAUDE.md explicitly calls these transient). Pre-commit will crawl them without an exclude.
6. **No coverage of `# noqa: BLE001` removal plan.** 27 sites carry this pragma — Phase 3 says "ruff BLE001 clean" but doesn't instruct removal of the pragma comments after narrowing.
7. **No type stubs for `lark`, `trimesh`, `xatlas` availability listed.** Plan lists them in `ignore_missing_imports` but `types-jsonschema` is included; a quick check for `lark-stubs` / `trimesh-stubs` on PyPI would save cycles.
8. **`constants.py` already partly exists?** — it does NOT. Plan is right to create it, but should call out the three call sites need matching imports (no current users).
9. **Pre-commit `check-added-large-files --maxkb=512` will fail immediately** against `examples/refs/**` (audio/images/meshes). Plan excludes that path — good — but should also exclude all `dist_*` and `cache_probe_*` roots listed in CLAUDE.md.

## Feasibility & effort

**5–6 engineer-days is optimistic.** Realistic breakdown with gaps filled:

| Phase | Plan estimate | Realistic |
|---|---|---|
| 1 Tooling baseline | 0.5d | 0.5d |
| 2 Typing ramp (11 strict-tier modules, project-wide check) | 1–1.5d | **2–3d** |
| 3 Exception hierarchy + 27-site audit | 0.5d | **1d** |
| 4 parser split | 1d | 1–1.5d (`_FastParser` sub-split) |
| 4.5 executor split (missing) | — | **1.5d** |
| 5 shape_providers split | 1d | 1d |
| 6 Docstrings (public API sweep) | 0.5d | **1.5d** (ruff D on ~60 files) |
| 7 Smell cleanup | 0.5d | 1d |
| 8 Pre-commit/CI | 0.5d | 0.5d |

**Realistic total: 10–12 engineer-days**, not 5–6. Parallelizable to ~6–7 calendar days with two engineers.

**Hidden prerequisites:**
- CI runner image needs Blender-free mode (tests tolerate absence, but the mypy pass must not import modules that require Blender/torch at import time).
- Phase 8 pre-commit will block every contributor until Phase 1 sweep is merged — sequencing matters.

## Does this plan deliver 10/10 if executed?

**No — it delivers ~9/10.** Executing everything written lands: ruff + mypy gating, typed strict-tier, decomposed parser + providers, rooted exception hierarchy, docstring coverage, CI gate. Blockers to 10/10:

1. **`executor.py` at 2,315 LOC survives** — single largest code-quality eyesore, untouched.
2. **Four other files >500 LOC** violate the plan's own exit criterion.
3. **Phase 3's "≥2 → 0" exit criterion is off by an order of magnitude** (27 sites) — if interpreted literally, the gate passes while most swallows remain; if interpreted strictly, Phase 3's budget is wrong.
4. **Resolver silent-skip comprehensions** are acknowledged with one sentence but not specified; leaves a correctness-adjacent smell in place.

Add an executor split, raise the effort estimate to ~10–12 days, enumerate all 27 `except Exception` sites with target narrowings, and specify resolver comprehension behavior — then the plan earns 10/10.
