# Implementation Plan: Product Quality 6/10 → 10/10

## Overview
Close every README-flagged scaffold, add user-facing polish (gallery, rich reports, viewer, playground), prove the backend plugin model with a second stack, enforce strict-mode defaults. 15 phases, ~11–13 engineer-weeks.

README-flagged scaffolded items confirmed absent by code inspection: publish runner (stage exists in `STAGE_ORDER` but no publisher driver), `lathe fmt` (currently parse/normalize round-trip only), multi-round autonomous repair loops (`repair_planner.py` + `repair_executor.py` exist, single-pass only). Single stack confirmed at `lathe/backends.py:204` (STACKS dict).

## Target end-state
Zero scaffolded items in README; every hero asset ships a gallery; strict mode opt-out; crash rate on fuzzed parser inputs <0.1%; p95 hero build time <45s native-only.

---

## Phase 1 — Publish runner (1.0w)

- New module: `lathe/publish.py` — registry drivers keyed by `publish.target`.
- Drivers: `local_fs` (default), `s3` (boto3 optional), `supabase` (REST + storage), `git_lfs` (subprocess), `itch_io` (butler CLI wrapper, gated).
- Metadata `manifest.json`: `asset`, `stack_id`, `shape_contract`, `package_formats`, `validator_scores`, `lathe_version`, `git_sha`, `sbom.json`, `signature.sig`.
- Signing: minisign/ed25519 via `cryptography`; key path in runtime config under `publish.signing_key`.
- CLI: extend `cli.py build` with `--publish <target>`; add `lathe publish <build_dir> --target <name> --runtime-config ...`.
- Tests: `tests/test_publish.py` with mocked S3/Supabase HTTP and temp-dir local target. Round-trip signature verify.
- Risk: credentials. Mitigation: secrets via env-var reference only; never in manifest.

## Phase 2 — `lathe fmt` canonical formatter (0.8w)

- New module: `lathe/formatter.py`. Lark tree → pretty-print with fixed rules (2-space indent, trailing commas, alphabetized block attrs where order is not semantic, stable key ordering from `normalizer.CANONICAL_ORDER`).
- Preserve comments via Lark `keep_all_tokens=True`; attach to preceding AST node.
- Idempotence: `fmt(fmt(x)) == fmt(x)` enforced in test.
- CLI: rework `p_fmt` in `cli.py` — default rewrites in place, `--check` no-writes + non-zero on diff, `--stdout` for pipelines.
- Tests: `tests/test_fmt.py` with golden pairs under `tests/fixtures/fmt/{input,expected}/*.lth`; fuzz via random whitespace perturbation expecting stable fixed-point.
- Risk: comment preservation. Mitigation: golden corpus covers every declaration form in `grammar/lathe.lark`.

## Phase 3 — Autonomous repair loop (1.0w)

- New module: `lathe/repair_loop.py`. Stop conditions: `max_rounds=3` (configurable), score delta < `repair.min_improvement` (default 0.01), hard timeout `repair.budget_seconds`.
- Loop: `validate → classify(diagnostic) → choose(action ∈ {reselect_candidate, local_repair, regenerate_with_patch}) → rebuild_stage_subset`.
- Regression guard: each round must improve overall `score` OR strictly reduce diagnostic count at its class; otherwise roll back.
- Trace: append to `build_report.json.repair_rounds[]` with `round_index`, `action`, `before_score`, `after_score`, `diagnostics_delta`, `elapsed_ms`.
- Integrate in `executor.py build_asset` after validate stage, behind `repair.autonomous=true` (default true for heroes once tests pass).
- Tests: `tests/test_repair_loop.py` — inject failing validator fixtures; assert monotone improvement and rollback-on-regression.

## Phase 4 — Second backend stack: soft-surface prop v1 (2w)

Proves plugin model. Choose **soft-surface** over trim-sheet-heavy: (a) most distinct contract surface — non-planar UVs, subdivision topology, cloth-like silhouette validators — forcing real adapter abstraction; (b) trim-sheet reuse already in V1.2 surface authoring.

- New stack ID: `lathe.stack.soft_surface_prop_v1`, registered in `backends.py`.
- Bindings: `shape → intent_mesh_handoff_v1` (reused); `topology → lathe.topology.blender_subdiv_v1` (new at `lathe/adapters/blender_subdiv.py`); `uv → xatlas_v1` (reused with `uv.soft_padding=true`); `package → openusd_gltf_v1`.
- New validator: `lathe/validators/soft_silhouette.py` — curvature continuity, fold-crease detection.
- Hero: `examples/satchel_bag.lth` + stdlib family `std/families/soft/satchel.lth`.
- Docs: `docs/second_backend_stack.md`.
- Tests: `tests/test_stack_soft_surface.py` mirroring `test_backends.py` + `test_build.py`.

## Phase 5 — Hero output gallery (0.7w)

- `scripts/render_gallery.py` — iterates heroes (from new `lathe/hero_manifest.py`), runs `lathe build` then headless Blender to produce `turntable_24.webp`, `hero_front.png`, `hero_three_quarter.png`, `wireframe.png`, `uv_layout.png`.
- Output: `docs/gallery/<asset>/` + `index.html` from `docs/templates/gallery_index.html.j2`.
- Hosting: GitHub Pages via `.github/workflows/gallery.yml` (nightly cron to avoid PR cost).
- Tests: `tests/test_gallery.py` — manifest/naming only; renders skipped in CI without Blender.

## Phase 5b — Published benchmark scoreboard (0.4w)

- Published benchmark scoreboard at `docs/benchmarks/scoreboard.md` auto-generated from Plan 09's 5-asset benchmark data.
- Each hero ships with: tri count, UV validity score, collision-present yes/no, pivot error, build time, reproducibility hash.
- Updated per release; regression triggers issue.
- Generator: `scripts/render_scoreboard.py`, producing the markdown from the benchmark JSON output and a Jinja template.
- CI: nightly job posts diffs vs. previous scoreboard; >20% regression on any tracked metric opens a GitHub issue via the `gh` CLI.

## Phase 6 — User-friendly validator output (0.6w)

- `lathe/reports/{terminal.py, html.py}`. Terminal uses `rich` (dev extra, ANSI fallback); HTML uses stdlib `string.Template` (no runtime dep).
- Sections: summary banner (PASS/FAIL + score/threshold), per-validator table with reasons, diagnostics by severity, repair suggestions, artifact links.
- CLI: `--report terminal|html|json` (default terminal for TTY, json otherwise). HTML emitted next to `build_report.json` as `report.html`.
- Tests: `tests/test_reports.py` — golden-string match for terminal; HTML DOM smoke via `html.parser`.
- **6d — CLI error output:** colored severity, source file+line citation, "what to try next" hint, exit-code documented in `--help`. Every raise-site in `lathe/cli.py` gets an `error_code` registered in `docs/error_codes.md`.

## Phase 7 — Artifact viewer (0.5w)

- `lathe inspect --view`: extend `inspect` in `cli.py`; lazy import `trimesh`, open `Scene.show()` for `.glb`.
- `lathe serve <build_dir>`: new command. Stdlib `http.server` on port 8765 serving `lathe/viewer/static/` with vendored `<model-viewer>` HTML pre-wired to `/asset.glb`. No Node toolchain.
- Tests: `tests/test_viewer.py` — assert viewer static bundle exists and `--view` resolves a real glb; skip live server.
- **Build progress reporting** via `rich.progress` for multi-minute hero builds. Per-stage spinner + overall bar; ETA based on prior-build duration cache stored at `~/.cache/lathe/build_durations.json`.

## Phase 8 — Strict-mode default (0.3w)

Ship behind a `--strict` opt-in in V0.1.x releases with a loud `DeprecationWarning` when `strict=False` is in effect under a learned provider. Flip default to `True` in V0.2.0 per the Phase 11 deprecation policy. Do not flip the default mid-V0.1 series.

- **V0.1.x rollout:** In `runtime_config.py`, when runtime config explicitly names learned provider (`hunyuan2_1_http`, `vggt_local`, `codex_imagegen`) and `strict` is unset, keep current default (`False`) but emit a `DeprecationWarning` on every invocation: `"strict=False under learned provider will default to True in V0.2.0; set strict explicitly to silence."`
- **Opt-in flag:** `--strict` on `build`, `surface-build` flips to the strict semantics immediately. `--allow-fallback` remains the explicit opt-out for when strict is on.
- **V0.2.0 flip:** default becomes `strict=True` for learned providers; `DeprecationWarning` removed; `--allow-fallback` remains the only non-strict path. Coordinated with Phase 11's one-minor-version deprecation window.
- Drop `--strict-shape-provider` (aliased for back-compat, warn).
- Leave `examples/runtime_configs/hunyuan_http.json` + `vggt_local.json` at current defaults during V0.1.x; update to `"strict": true` as part of the V0.2.0 cut.
- Exit-code contract: strict + fallback → non-zero, diagnostic `provider_fallback_blocked`.
- Tests: extend `test_shape_providers.py` for exit-code enforcement under `--strict`; add test asserting `DeprecationWarning` fires in V0.1.x code path.

## Phase 9 — Stability pass (0.8w)

- **Fuzzing**: `tests/fuzz/test_parser_fuzz.py` using `hypothesis` strategies derived from `grammar/lathe.lark` terminals. 10k iterations nightly; target zero uncaught exceptions other than `LatheSyntaxError`.
- **Golden replay**: snapshot all hero `build_report.json` + shape `bundle.json` hashes under `tests/golden/`. `tests/test_golden_replay.py` rebuilds and asserts bit-identical deterministic stages (topology/UV/package) + deterministic fields of shape bundle (exclude timestamps, provider probe latency).
- Crash budget gate in CI: fuzz aggregates <0.1% crash rate.

## Phase 10 — Performance pass (0.6w)

- Profiler harness: `scripts/profile_heroes.py` using `cProfile` + `pyinstrument` (dev extra), one run per hero.
- Per-stage budget `perf/budgets.json` — `shape ≤18s`, `topology ≤8s`, `uv ≤4s`, `validate ≤6s`, `package ≤4s`, p95 total ≤45s native-only.
- Regression gate: `tests/test_perf_budget.py` (skipped in PR, enforced nightly) compares wall-clock per stage with 20% tolerance.
- Targeted wins: cache `feature_fusion` voxel grids keyed by blueprint hash; parallelize candidate search with `ProcessPoolExecutor`; memoize `xatlas` atlas across variants.

## Phase 10b — Content-addressed cache with explicit eviction (0.4w)

Content-addressed cache with explicit eviction: `lathe cache status|clean|warm`. Key each cached artifact by the hash of its declared inputs (from `runtime_config` + `.lth` source + stdlib deps). Stale cache is the #1 reason builds go weird — make invalidation a first-class verb.

- New module: `lathe/cache.py`. Cache root `~/.cache/lathe/` (override via `LATHE_CACHE_DIR`).
- Key schema: `sha256(runtime_config_canonical_json || .lth_source_sha || stdlib_dep_tree_sha || lathe_version)`.
- CLI subcommands: `lathe cache status` (prints size, entry count, oldest/newest), `lathe cache clean [--older-than=30d] [--stack=<id>] [--all]`, `lathe cache warm <file.lth> <asset>` (prebuild and populate without writing a distributable artifact).
- Per-entry metadata: `inputs.json`, `created_at`, `lathe_version`, `stack_id`.
- Docs: `docs/caching.md` explaining invalidation rules + troubleshooting.
- Tests: `tests/test_cache.py` — hash-stability, bust-on-input-change, `--no-cache` honored.

## Phase 10c — Cross-platform parity (0.3w)

Windows-vs-POSIX smoke: CI matrix already covers both (Plan 06); this phase adds per-hero path-handling assertions (drive letters, UNC paths, backslash-aware resolver tests) and ensures no hero embeds POSIX-only shell assumptions.

- Audit `lathe/resolver.py`, `lathe/parser.py`, `lathe/bridge/blender_plan.py`, `lathe/blender_execution.py` for raw `os.path` / string-concat paths → migrate to `pathlib`.
- Tests: `tests/test_cross_platform_paths.py` — parametrize over drive-letter roots, UNC paths (`\\server\share\...`), mixed slash sources; run under both `win32` and `posix` CI lanes.
- Hero audit: scan `examples/*.lth` and `std/**/*.lth` for forward-slash-only `ref`/`image` attrs; parser already resolves relative refs, but certify no shell-exec strings leak into hero sources.
- `lathe fmt` LF/CRLF policy: default LF in output, preserve original line ending on `--check`.
- Pyodide (Phase 12) implication: path handling must be POSIX-only inside the wheel; assert via a Pyodide-specific test.

## Phase 11 — V0.2 scope & deprecation policy (0.3w)

- `docs/v02_beta_scope.md`. Beta gates: Phases 1–10 landed; zero README scaffolds; two stacks; gallery live; strict default; golden replay green 30 days.
- Deprecation policy: stable surface list (`profile`, `contract`, `critic`, `asset`, `variant`, stage names, `intent_mesh_handoff_v1`). Removal requires one-minor-version deprecation window with `DeprecationWarning` + schema `deprecated: true`. `docs/deprecation_policy.md`.
- `lathe/version.py` — `API_VERSION=(0,2,0)` and `CONTRACT_VERSIONS={...}` exposed via `lathe doctor`.

## Phase 12 — Public demo / playground (1.5–2w)

- `web/playground/` — static SPA (vanilla TS, esbuild) loading Pyodide build of `lathe` (via `scripts/build_pyodide_wheel.sh`). Monaco editor with `.lth` syntax mode (`lathe-monaco-mode.ts` generated from `grammar/lathe.lark`). Right pane: normalized AST, validator HTML report (Phase 6), embedded `<model-viewer>` (Phase 7).
- Size cap: single demo asset `examples/playground_crate.lth` to keep wheel <20MB gzipped; heavy Blender/xatlas paths stubbed in Pyodide.
- Hosting: GitHub Pages alongside gallery.
- Tests: `tests/test_playground_bundle.py` asserts wheel builds + required symbols reachable.

## Phase 13 — Measurable 10/10 acceptance (0.2w)

`docs/product_quality_10_criteria.md`:
- [ ] Zero items under "What is intentionally still a scaffold" in README
- [ ] Every hero in `lathe/hero_manifest.py` has `docs/gallery/<asset>/` with 5 required artifacts
- [ ] `lathe build` with learned provider and no `--allow-fallback` exits non-zero on fallback
- [ ] Nightly fuzz: crash rate <0.1% over 10k runs for 7 consecutive days
- [ ] Hero builds p95 <45s native-only on reference hardware
- [ ] `soft_surface_prop_v1` listed in `lathe backends`; has runnable example
- [ ] `lathe fmt --check examples/*.lth std/**/*.lth` idempotent across two rounds
- [ ] `lathe inspect --view` + `lathe serve` render hero glb without errors
- [ ] Playground loads <6s cold cache; compiles `playground_crate.lth`
- [ ] `lathe doctor --json` reports `api_version: 0.2.0`; deprecation policy linked from README
- [ ] `docs/benchmarks/scoreboard.md` auto-generated, covers all heroes with required metrics, regressions open issues
- [ ] All `lathe/cli.py` raise-sites have registered `error_code`s in `docs/error_codes.md`; errors show colored severity + source citation + next-step hint
- [ ] Multi-minute hero builds show per-stage progress + ETA via `rich.progress`
- [ ] `lathe cache status|clean|warm` functional; cache-key bust verified on `.lth` / `runtime_config` / stdlib dep change
- [ ] Cross-platform path tests green under Windows + POSIX CI; no POSIX-only shell assumptions in `examples/*.lth` or `std/**/*.lth`
- [ ] `--strict` opt-in works in V0.1.x; `DeprecationWarning` fires under learned provider when unset; V0.2.0 milestone flips default

## Risks & mitigations

- **Pyodide bundle size** (Phase 12) → ship only deterministic paths; pre-compile `lark` grammar; gzip + Brotli.
- **Blender dep for gallery** (Phase 5) → CI on dedicated runner with prebuilt Blender; local `--no-render` skip.
- **Flaky fuzz noise** (Phase 9) → durable hypothesis corpus; fail only on repeat crash of identical stacktrace.
- **Signing key management** (Phase 1) → never stored in repo; CI uses GitHub Actions OIDC ephemeral keys.

## Sequencing

Phases 2, 8 first (quick, unblock users — Phase 8 stays as `--strict` opt-in for V0.1.x; default flip deferred to V0.2.0 under Phase 11 policy). Then 3, 1, 4 (core functionality). Then 6 (incl. 6d CLI error polish), 7 (incl. progress bars), 5, 5b (UX + scoreboard). Then 9, 10, 10b (cache), 10c (cross-platform) (rigor). Then 12 (demo), 11 (policy), 13 (sign-off). ~12 weeks solo, ~7–8 weeks with 2 engineers parallel on (1,4) and (5,5b,6,7,12).

---

## Relevant files

- `README.md`, `CLAUDE.md`
- `lathe/cli.py`, `backends.py`, `executor.py`, `normalizer.py`, `runtime_config.py`, `shape_providers.py`, `blender_execution.py`
- `grammar/lathe.lark`, `schema/lathe.schema.json`
- `examples/runtime_configs/hunyuan_http.json`, `vggt_local.json`

---

## Amendment log (2026-04-23)

Applied review `plans/reviews/08_product_quality_review.md` + meta-review cross-cutters:

1. **Phase 4 effort bump** — 1.2w → 2w. Soft-surface stack realistically needs 2 weeks (new topology adapter `blender_subdiv_v1`, new `soft_silhouette` validator with calibrated thresholds, new hero `satchel_bag`, full test suite mirroring existing stack coverage).
2. **Phase 12 effort bump** — 1.0w → 1.5–2w. Pyodide wheel build, Monaco `.lth` mode generation, `<model-viewer>` integration, and <20MB gzipped size optimization are each 2–3 day tasks; Blender-dependent paths need feature-detection rather than stubbing.
3. **Added Phase 5b — Published benchmark scoreboard.** Auto-generated `docs/benchmarks/scoreboard.md` from Plan 09's 5-asset benchmark data. Per-hero metrics (tri count, UV validity, collision, pivot error, build time, reproducibility hash). Per-release regression gate opens issues.
4. **Added CLI error polish (6d) to Phase 6.** Colored severity, source file+line citations, "what to try next" hint, `--help`-documented exit codes. Every `lathe/cli.py` raise-site gets an `error_code` registered in `docs/error_codes.md`.
5. **Added build progress bars to Phase 7.** `rich.progress` per-stage spinner + overall bar; ETA from prior-build duration cache (addresses 45s-silent-build UX gap flagged by reviewer).
6. **Added Phase 10b — Content-addressed cache with explicit eviction.** `lathe cache status|clean|warm`. Key by hash of `runtime_config` + `.lth` source + stdlib deps + `lathe_version`. Stale-cache invalidation promoted to first-class verb per reviewer gap #4.
7. **Added Phase 10c — Cross-platform parity.** Per-hero path-handling assertions (drive letters, UNC, backslash), `pathlib` audit of resolver/parser/bridge, LF/CRLF policy for `lathe fmt`, Pyodide path-handling test. Addresses reviewer gap #5 (Windows is primary dev platform per CLAUDE.md).
8. **Phase 8 rewritten to respect Phase 11 deprecation window.** `--strict` opt-in in V0.1.x with `DeprecationWarning` on `strict=False` under learned providers; default flips to `True` only in V0.2.0. No mid-V0.1 default flip. Addresses reviewer gap #8 (rollback plan / consistency with Phase 11 policy).
9. **Scaffolded-status note added to Overview.** Reviewer-verified: publish runner absent (stage in `STAGE_ORDER`, no driver); `lathe fmt` is parse/normalize round-trip only; repair loop is single-pass (`repair_planner.py` + `repair_executor.py` exist, no multi-round). Single stack confirmed at `lathe/backends.py:204`.
10. **Effort total updated** — 13 phases → 15 phases; ~9–11w → ~11–13w (reflects Phase 4 +0.8w, Phase 12 +0.5–1w, Phase 5b +0.4w, Phase 10b +0.4w, Phase 10c +0.3w).
