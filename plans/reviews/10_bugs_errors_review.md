# Review: Plan 10 — Bugs, Errors & Issues

Reviewer: `reviewer-bugs`. Scope: verify every citation in `plans/10_bugs_errors.md` against the actual code, assess fix correctness, spot missed bugs, score /10.

## 1. Findings-Verification Table

| ID  | Status         | Actual line                        | Quoted code                                                                 | Fix correct? | Notes |
|-----|----------------|------------------------------------|-----------------------------------------------------------------------------|--------------|-------|
| C1  | VERIFIED       | `shape_providers.py:422-425`       | `try: loaded = trimesh.load(path, force="scene")` / `except Exception:  # noqa: BLE001 / return None` | Mostly     | Fix direction right, but `trimesh.exceptions.*` is not a real module — the correct exception classes live under `trimesh.exceptions` as `FilterException`/`BrokenDimensions`, etc. Plan should say "trimesh raises `ValueError`, `OSError`, `KeyError`, `IndexError` on corrupt inputs". Otherwise narrowing is sound. |
| C2  | VERIFIED       | `shape_providers.py:463-489`       | `def _mesh_body_count(...): try: return int(mesh.body_count) except Exception:  # noqa: BLE001` | Partially  | Actual behavior is subtler than plan says: the bare `except` is a **fallback to manual BFS**, not a silent `0`. Code only returns `0` inside the fallback when `len(faces)==0` (line 468-469). Fix premise ("returns silent 0") is wrong. Real issue: bare `except` masks unrelated errors (e.g. `KeyboardInterrupt` was already excluded, but `AttributeError`/`MemoryError` silently slide into BFS). Narrow to `(AttributeError, TypeError, ValueError)` — do **not** raise `ShapeMeshAnalysisError`; keep BFS as intentional fallback. |
| C3  | VERIFIED       | `shape_providers.py:440-444`       | `image_refs = _non_material_image_refs(conditioning)` / `if not image_refs: raise ShapeProviderExecutionError(..., code="missing_image_ref")` / `return Path(image_refs[0]["path"])` | ALREADY FIXED | **The guard already exists.** Line 442 checks `if not image_refs: raise ShapeProviderExecutionError(...)` with exactly the `code="missing_image_ref"` the plan proposes. This finding is stale — remove or rewrite as "add test coverage for existing guard". |
| M1  | LINE-MISMATCH  | `shape_providers.py:567` (header block at 557-573) | `content_type = resp.headers.get("Content-Type")` (line 557) / `if content_type and "json" in content_type.lower(): raise ShapeProviderExecutionError(..., code="unexpected_json_response", ...)` (567-573) | Partially | Plan claim "check happens AFTER `resp.read()`" is technically true (read at 554, header check at 557, JSON check at 567) — but the body is already in-memory; no side-effect occurred. Real risk is low: at worst, a large non-mesh body is buffered. Fix (inspect headers first, sniff magic bytes) is a nice-to-have, not a correctness fix. Downgrade severity. Also: actual line cited as 567 is the JSON check, which is fine; header read is at 557. |
| M2  | VERIFIED       | `runtime_config.py:66`             | `raw = json.loads(Path(path).read_text(encoding="utf-8"))` (unguarded) | Yes      | No try/except around `json.loads` nor `read_text` (will raise `FileNotFoundError`, `UnicodeDecodeError`, `JSONDecodeError`). Plan's schema-validation direction is sound; the schema file `schema/runtime_config.schema.json` doesn't exist yet, so plan must also create it. |
| M3  | VERIFIED       | `shape_backend.py:285`             | `explicit_provider = str(shape_cfg.get("provider", "auto") or "auto") not in {"", "auto", "None", "null"}` | Yes      | Verbatim match. Plan's fix (normalize upstream, treat `None`/`""`/`"auto"` as auto; reject literal `"None"`/`"null"` as typos) is correct. Low blast radius. |
| M4  | VERIFIED       | `blender_execution.py:210-229`     | `proc = subprocess.run([blender["path"], "--background", ...], check=False, capture_output=True, text=True, timeout=300)` / `return {"ok": proc.returncode == 0 and output_blend.exists(), ...}` | Mostly   | Verified. Plan's stderr-scan fix is reasonable but fragile (i18n Blender builds don't say "Error:" in English). Better: check `output_blend.exists()` (already done!) AND parse summary file. The `output_blend.exists()` check already catches most silent failures — plan understates existing mitigation. |
| M5  | VERIFIED       | `shape_providers.py:657-658`       | `raw_path = work_dir / f"hunyuan_candidate_{index:02d}.{out_type}"` / `raw_path.write_bytes(raw)` | Yes      | Two concurrent builds sharing the same `work_dir` would collide. However, `work_dir` is passed from the executor and is already per-build in practice. Verify upstream call sites before landing the uuid4 change — may be no-op. |
| M6  | VERIFIED       | `shape_providers.py:296-304` + `runtime_config.py:13` | `"strict": False,` (DEFAULT) / `except ShapeProviderError as exc: if selection["strict"]: raise ...` (296-298) / fallback returns success | Yes       | Verified. Default `strict=False` at `runtime_config.py:13`; fallback at `shape_providers.py:299-304` silently returns `{"provider_report": report, "runtime_candidates": None}`. Plan's fix (flip default when explicit provider selected, emit non-zero on silent fallback) is correct and aligns with M3. |
| M7  | VERIFIED       | `pyproject.toml:11-17, 25-36`      | `"lark>=1.1"`, `"jsonschema>=4.0"`, `"numpy>=1.26"`, `"Pillow>=10.0"`, `"trimesh>=4.0"`, `"torch>=2.11.0"`, `"torchvision>=0.26.0"` | Yes | Verified; no upper bounds, no lockfile. `torch>=2.11.0` is also suspicious — current stable torch at time of writing is 2.5.x; >=2.11 may be unreachable. Plan should flag this. |
| Mi1 | VERIFIED       | `resolver.py:292, 399-401`         | `"transfer_rules": [self._resolve_mapping_optional(..., item, "transfer_rule") for item in transfer_rule_names if item in self.transfer_rule_map]` (292) / `resolved_components = [self._resolve_component(component_name) for component_name in component_names]` (399) / mechanisms, traits (400-401) | Yes | Verified: line 292 filters via `if item in self.transfer_rule_map`; 399-401 don't filter — they call `_resolve_component` which routes through `_resolve_named_decl` and will raise `ResolutionError` on miss. Inconsistent as claimed. |
| Mi2 | LINE-MISMATCH  | `shape_backend.py:335-337`         | `def _root_name(parts: list[str]) -> str: body_names = [name for name in parts if any(token in name for token in ("body","hull","core","base"))]; return body_names[0] if body_names else parts[0]` | Yes (trivial) | Cited as 336-337; actual code spans 335-337. Not a nested ternary — it's a list-comprehension-plus-single-ternary. Plan mischaracterizes the shape. Extracting to if/else is fine but the "nested ternary" framing is wrong. |
| Mi3 | HALLUCINATED   | `shape_providers.py:58-59`         | Actual 58-59: `"max_retries": 2, "retry_backoff_s": 1.0,` (Hunyuan config defaults) | N/A        | **No `7919` anywhere in `shape_providers.py`** (grep confirms zero matches). Finding fabricated. No seed-salt constant exists; `seed` is passed through from caller and added to `index` at line 640. Plan's proposed named constant would be dead code. Drop Mi3. |
| Mi4 | VERIFIED       | repo root                          | No `.gitignore` file present; `.lathe_lark_cache` = 25MB; dozens of `dist_*`/`cache_probe_*`/`dist_v03_*` … `dist_v09_*` dirs | Yes     | Confirmed: `ls D:/lathe_v0_1/` shows ~60 transient dirs; `.gitignore` absent. CLAUDE.md already documents the convention — plan just needs to encode it. |
| Mi5 | ALREADY FIXED  | `.venv/Lib/site-packages/`         | `D:/lathe_v0_1/.venv/Scripts/python.exe -c "import trimesh"` returns `trimesh OK 4.11.5` | N/A        | Plan claim "venv missing trimesh; 9 modules fail to import" is false **in this tree** — trimesh 4.11.5, numpy 2.4.4, lark 1.3.1 all present. Either the finding was from a pre-bootstrap state or was never accurate. Demote to "add a cold-clone CI smoke" without the false framing. |

**Verification summary:** 9 VERIFIED, 2 LINE-MISMATCH, 1 HALLUCINATED, 2 ALREADY FIXED, 1 PARTIAL. C3 and Mi5 shouldn't be in the plan; Mi3 is entirely fictional.

## 2. Missed bugs (found while verifying)

Grep across `lathe/` for `except Exception` turned up 28 hits — plan only addresses 2. Notable ones the plan misses:

- `lathe/executor.py:292, 521, 581, 1346, 1354, 1512, 1593, 1655` — seven bare `except Exception` sites in the core executor. At least 521/581 wrap stage execution and silently record errors; these are higher blast-radius than C1/C2.
- `lathe/shape_providers.py:732` — VGGT import block catches all exceptions, including `KeyboardInterrupt` swallowing if user ctrl-Cs mid-import (actually safe since `Exception` doesn't catch `BaseException`, but should be `ImportError`).
- `lathe/shape_providers.py:920, 927` — bare `except` in convex-hull / `unique_faces` calls; silent `pass` or `return None`.
- `lathe/shape_backend.py:87` — bare `except` not cited anywhere in the plan.
- `lathe/validators/visual_quality.py:58, 239` — validator bare excepts; invisible validation failures are particularly bad (silent certification).
- `lathe/exact_solids.py:116, 130, 179, 211` — four bare excepts in exact-solids kernel.

17 production `assert` statements in `lathe/` (`assembly_kernel.py`, `geometry_kernel.py`, `executor.py:372`, `scaffold_compiler.py`, `exact_solids.py`, `validators/visual_quality.py:118`). Python with `-O` strips them — asserts should not guard invariants in production code. Plan doesn't mention.

`eval_harness.py:77`, `candidate_search.py:67`, `parser.py:1631`, `capabilities.py:295`, `doctor.py:38`, `cli.py:263`, `geometry_kernel.py:227`, `normalizer.py` — more bare excepts the plan ignores.

## 3. Exception-hierarchy compatibility

Existing `class *Error` definitions:
- `backends.py:11` `BackendResolutionError(Exception)`
- `executor.py:67` `BuildError(Exception)`
- `patch_api.py:9` `PatchAPIError(Exception)`
- `normalizer.py:77` `NormalizationError(Exception)`
- `parser.py:26,30` `LatheParseError(Exception)`, `DuplicateFieldError(LatheParseError)`
- `resolver.py:10` `ResolutionError(Exception)`
- `shape_providers.py:82,90,94` `ShapeProviderError(RuntimeError)`, `ShapeProviderUnavailable`, `ShapeProviderExecutionError`

Plan's proposed `LatheError` root with `LatheResolverError.UnresolvedNameError`, `LatheProviderError.ShapeProviderExecutionError`, etc. conflicts with existing `ShapeProviderError(RuntimeError)` — would require either re-parenting (breaks `isinstance(e, RuntimeError)` consumers, if any) or multiple inheritance. Plan doesn't acknowledge the existing `RuntimeError` parentage. Also: `LatheParseError`, `NormalizationError`, `BackendResolutionError`, `PatchAPIError`, `BuildError` aren't in the hierarchy at all — will they re-parent or stay orphans? Plan is silent. **This needs a migration sub-plan before landing.**

## 4. Static-analysis rule mapping

Verified against ruff's rule catalog:
- `BLE001` — real, catches `except BaseException/Exception`. ✓ Would catch C1, C2 (both already have `# noqa: BLE001`, so ruff is already aware; the waivers are just being rubber-stamped).
- `B904` — real, `raise ... from err` inside `except`. ✓ Would catch some M1/M2 cases.
- `TRY003`, `TRY200`, `TRY301`, `TRY400` — mixed. `TRY003` ("avoid long messages outside exception class") is real; `TRY301` ("raise inside try") is real; `TRY400` ("use `logging.exception`") is real. `TRY200` was **renamed to `B904`** in ruff; citing both is redundant / out of date. Double-check: `TRY200` is in ruff's legacy codes but emits a deprecation. Plan should drop `TRY200`.
- `S603`/`S607` — real bandit-derived rules for `subprocess`. ✓ Would catch M4.

**Correction needed:** drop `TRY200` (or document it's legacy). Rest are correct.

Note: every bare except in the codebase already has `# noqa: BLE001`. Enabling ruff doesn't surface these — the waivers need auditing, not the rule.

## 5. Critical contract-risk check

`lathe.shape.intent_mesh_handoff_v1` is called out in CLAUDE.md as a public contract. Plan's proposed exception-taxonomy restructure touches `ShapeProviderError` which is raised from `shape_backend.run_shape_backend` — downstream callers (executor, validators, CLI exit-code mapping) that `except ShapeProviderError` would need to keep working. Plan's "CLI maps each class to stable exit code (2=config, 3=resolver, 4=provider, 5=execution)" is new public surface — should be versioned. **Not a contract break if additive, but needs a compat test.**

M6 strict-mode flip is the biggest behavior change: hero examples in `examples/` run without runtime config and currently fall back silently. Flipping `strict=True` by default on explicit provider selection is safe (auto stays permissive); plan correctly scopes this.

## 6. Regression-test specificity

Tests are mostly named well and testable. Gaps:
- C3 test is dead weight (bug already fixed) — waste or convert to guard-regression.
- Mi3 test `test_provider_seed_deterministic_across_runs` is orphaned (no constant to test).
- M5 concurrency test is the only truly hard one; plan doesn't specify threading model (thread vs process). Flaky-test risk.
- No regression for the 8+ other bare-except sites in executor.py — plan's "one test per finding" leaves them uncovered.

## 7. Feasibility

Phase 1 (C1, C2) is half a day of work — fine. C3 is zero work (already fixed). Phase 2 HTTP batch is ~2 days; config-loader batch is ~1 day with schema file; subprocess+deps is ~1 day. Phase 3 is hours. Phase 4 prevention is the real cost (ruff+mypy-strict+bandit+semgrep on ~40kLOC with 28 pre-existing bare-except waivers) — **mypy `--strict` on the whole `lathe/` package will likely produce thousands of errors**; plan understates this. Realistic: gradual typing with `--strict` only on new modules.

**Overall feasibility: moderate.** Cut C3 and Mi3; descope Phase 4 mypy strictness.

## 8. 10/10 Verdict

**Score: 5.5/10.**

Positives:
- Severity triage is reasonable; regression-test-per-bug discipline is right.
- Static-analysis stack is the correct direction.
- Exception-hierarchy idea is good (just underspecified).
- M3, M6, Mi1, Mi4 fixes are clean and correct.

Negatives:
- **3 of 15 findings are wrong** (C3 already fixed, Mi3 hallucinated, Mi5 contradicted by evidence). 20% error rate in an audit plan is too high.
- Plan misses ~20 comparable bare-except sites and 17 production asserts across the codebase — coverage is cherry-picked.
- Exception-hierarchy migration doesn't address existing `RuntimeError` parent or orphan error classes.
- `TRY200` is deprecated; `trimesh.exceptions.*` is not canonical.
- C2's root-cause description ("returns silent 0") is wrong — misreads the BFS fallback.
- Phase 4 mypy-strict adoption is unpriced.

To reach 10/10:
1. Delete C3 (already fixed) and Mi3 (hallucinated); investigate Mi5 in-tree before keeping.
2. Add the ~20 missed bare-except sites (executor.py, validators, exact_solids) as a Phase-1 sweep finding.
3. Fix C2's root-cause text to reflect the BFS fallback.
4. Add migration table for `ShapeProviderError(RuntimeError)` → new hierarchy, plus plan for `BuildError`, `ResolutionError`, `LatheParseError`, etc.
5. Replace `trimesh.exceptions.*` with concrete classes (`ValueError`, `OSError`, `KeyError`).
6. Drop `TRY200`; document mypy-strict as a multi-quarter effort with a gradual-typing rollout, not a gate.
7. Add production-`assert` sweep as a new finding.

## Relevant files referenced
- `D:\lathe_v0_1\lathe\shape_providers.py` (421-489, 440-444, 540-608, 657-658, 263-310)
- `D:\lathe_v0_1\lathe\shape_backend.py` (285, 335-337, 87)
- `D:\lathe_v0_1\lathe\runtime_config.py` (13, 63-70)
- `D:\lathe_v0_1\lathe\blender_execution.py` (208-235)
- `D:\lathe_v0_1\lathe\resolver.py` (292, 399-401)
- `D:\lathe_v0_1\pyproject.toml` (11-36)
- `D:\lathe_v0_1\lathe\executor.py` (67, 292, 521, 581, 1346, 1354, 1512, 1593, 1655)
- `D:\lathe_v0_1\lathe\validators\visual_quality.py` (58, 118, 239)
- `D:\lathe_v0_1\lathe\exact_solids.py` (116, 130, 179, 211)
