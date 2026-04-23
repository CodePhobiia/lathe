# Review: Plan 08 — Product Quality 6/10 → 10/10

## Summary

Plan 08 is the strongest of the scaffolded-gap plans: it identifies the three README-flagged scaffolds, proposes concrete modules for each, and layers user-facing polish (gallery, rich reports, viewer, playground) and rigor (fuzz, golden replay, perf budget) on top. All three scaffold claims from the findings were verified against the actual source. The plan is broadly coverage-complete but contains a few feasibility gaps (Phase 4 scope, Pyodide risk, CLI polish) and leaves cross-plan dependencies implicit.

## Coverage vs findings

| Finding | Plan phase | Adequate? |
|---|---|---|
| Hero examples runnable in conservative native mode | implicit (Phase 5 gallery consumes heroes) | yes |
| Native fallback deliberate / documented | Phase 8 strict-mode default | yes — inverts default for learned providers only |
| Validators not weakened | Phase 9 golden replay | yes — golden hashes prevent silent weakening |
| Unfinished: publish runner | Phase 1 | yes — detailed drivers + signing + manifest |
| Unfinished: `lathe fmt` | Phase 2 | yes — formatter module, idempotence test, comment preservation |
| Unfinished: multi-round repair loop | Phase 3 | yes — max_rounds, regression guard, trace |
| Only one backend stack | Phase 4 soft-surface prop | partial (see feasibility) |
| Learned providers need external servers | Phase 8 strict-mode | yes |
| Silent fallback w/ exit 0 | Phase 8 exit-code contract | yes — `provider_fallback_blocked` |
| No hero demo / gallery | Phase 5, Phase 12 playground | yes |
| No benchmark suite published | not addressed — only perf budget (Phase 10) | **gap** |
| Validator output not user-friendly | Phase 6 rich reports | yes |
| No artifact viewer | Phase 7 | yes |

## Citations verified against repo

- **Publish runner missing.** `lathe/cli.py` has no `p_publish` parser. Grep for `publish` in `lathe/` matches only normalized-AST field reads (`self.asset["publish"].get("version")` at `lathe/executor.py:907,974,1017`) and the stage-DAG entry `"optimize": ["validate", "package", "publish"]` at `lathe/planner.py:18`. No driver, no CLI, no runner. Confirmed scaffold.
- **`lathe fmt` is a parse/normalize smoke.** `lathe/cli.py:73-75` registers `p_fmt` with `--check`; `lathe/cli.py:248-267` just parses, normalizes, JSON-schema validates, and reports ok/not-ok. No pretty-printer, no round-trip write, `--check` flag is ignored in actual behavior (only affects the `"mode"` field in the output). Confirmed scaffold.
- **Repair loop is single-shot.** `lathe/repair_planner.py` + `lathe/repair_executor.py` + `lathe/repair_policy.py` exist and implement semantic repair actions (`add_missing_required_part`, `restore_symmetry_region`, `restore_edge_treatment`, etc.) applied once inside a single build. Grep for `repair_loop|multi_round|max_rounds|autonomous_repair` across `lathe/` finds zero matches in any repair module — hits are only in unrelated policy/normalizer config. Bounded single-round is real; multi-round is absent. Confirmed.
- **Single stack.** `lathe/backends.py:204-224` defines `STACKS` as a dict with exactly one entry: `lathe.stack.hard_surface_game_asset_v1`. Confirmed.
- **Stage DAG includes publish without executor.** `lathe/planner.py:18` lists `publish` as a downstream stage of `optimize`, but `executor.py` never iterates a `publish` step; the `publish` block is read as config only. Phase 1 therefore closes a real gap.

## Already-done (plan need not re-solve)

- Shape stage provider mux with attempted-vs-actual trace (covered in shape_backend / shape_providers) — Phase 8's strict contract builds on this rather than redoing it.
- Blender + xatlas adapter fallback tracing — Phase 4 claim of "real adapter abstraction" already partly exists.
- V1.2 surface Codex fallback reporting — Phase 8 can reuse this pattern for strict-mode exit codes.

## Gaps the plan misses

1. **Benchmark suite publication.** Finding flagged "no benchmark suite published." Plan adds `perf/budgets.json` and nightly perf gate (Phase 10) but never publishes comparison numbers vs. learned providers, nor a scoreboard alongside the gallery. A "why Lathe" bench needs to be public artifact, not just internal CI gate.
2. **CLI error polish.** Phase 6 rewrites *validator* output but leaves CLI error-path polish (parse errors, missing files, backend-resolution errors) on the raw `argparse` + exception-string path. A product-quality pass should format `LatheSyntaxError` with source context and carets.
3. **Progress bars during builds.** Hero builds target p95 <45s; a 45s silent `lathe build` feels broken. No progress/stage indicator is planned.
4. **Partial-build resume / cache invalidation.** README "Next build milestones" #5 flags cache semantics explicitly. Plan mentions feature_fusion cache (Phase 10) but no resumable build, no cache-key docs, no `--no-cache` or cache-bust story. This is a real user-facing quality item.
5. **Cross-platform path handling.** Windows is the primary dev platform per CLAUDE.md. Plan does not audit `pathlib` use, `subprocess` path quoting for Blender, nor LF/CRLF in `lathe fmt` output. The Pyodide build (Phase 12) and `scripts/*.sh` vs `.ps1` parity are not mentioned.
6. **`lathe backends` / discoverability of the second stack.** Phase 4 adds a stack but doesn't require the CLI to surface *why* you'd pick it (no `--recommend` or selection hints).
7. **Security surface of `lathe serve` / playground.** Phase 7 serves a static dir on `:8765` with vendored third-party JS. No mention of CORS, CSP, or pinning the vendored `<model-viewer>` version — and playground Pyodide ships a compiled wheel that needs SRI or hash pinning.
8. **No rollback plan for Phase 8.** Flipping learned providers to `strict=true` by default will break existing CI consumers. Plan does not gate via a deprecation window, unlike Phase 11's policy. Inconsistent.

## Feasibility

- **Phase 4 (1.2w) is the most underestimated.** A second stack that "forces real adapter abstraction" via subdiv + soft silhouette validator is closer to 2.0–2.5w: new topology adapter (`blender_subdiv_v1`) is a fresh Blender subprocess surface with its own watertightness+crease semantics, and a new validator family (`soft_silhouette.py`) needs a fixture set to calibrate thresholds. **Trim-sheet-variant stack would be faster** but, as the plan correctly argues, would not prove the plugin model. Recommend keeping soft-surface but budgeting 2w.
- **Phase 12 (1.0w) is optimistic.** Pyodide wheel of Lathe + Monaco + vendored `<model-viewer>` <20MB gzipped with Lark grammar precompiled is tight; Lark and `trimesh` alone push that envelope. Realistic budget 1.5–2.0w, with a real risk the Blender-dependent paths must be *feature-detected-off* in Pyodide rather than "stubbed," which the plan hand-waves.
- **Phase 9 (0.8w) fuzz + golden combo is probably right** given `hypothesis` scaffolding is straightforward; golden replay for bit-identical deterministic stages is reasonable because shape bundle hashing already exists.
- **Phase 10 perf budget (0.6w)** — reasonable if `ProcessPoolExecutor` parallelization of candidate search is straightforward; depends on pickle-ability of search state.
- **Phases 2, 8, 13 are accurately scoped** (small and well-bounded).
- **Cross-plan dependencies not called out:**
  - Phase 3 repair loop benefits from repair-classifier work that likely lives in plan 04 (test coverage) or 01 (code quality); acceptance criteria should share fixtures.
  - Phase 8 strict-mode collides with plan 07 (security) if secrets-handling is in that plan.
  - Phase 9 golden replay overlaps with plan 04 test coverage.
- **Total 9–11w solo is plausible only if Phase 4 slips to 2w AND Phase 12 slips to 2w** → actual ~10.5–12.5w solo. Parallelizing (1,4) + (5,6,7,12) as the plan suggests is feasible with 2 engineers.

## 10/10 verdict

**Not yet 10/10; currently ~8.5/10.** To reach 10, add:

1. Public benchmark scoreboard as an explicit Phase 5.5 (gallery already has hosting).
2. CLI error polish + progress indicators as Phase 6 scope extension.
3. Cache invalidation + partial-build story as a new short phase (~0.4w).
4. Windows/POSIX parity audit folded into Phase 9.
5. Strict-mode deprecation window consistent with Phase 11 policy.
6. Phase 4 scope-down or budget bump to 2w.
7. Pyodide size and blender-path feature-detection acknowledged with a cut-line.

With these, the plan is fully defensible as a 10/10 product-quality roadmap.
