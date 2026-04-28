# Runtime posture — v0.2.0rc1

**Version:** 0.2.0rc1 (pre-release reference compiler scaffold)
**Last reviewed:** 2026-04-28
**Owner:** Tal Merri (@talmerri)

This document covers capacity, concurrency, idempotency, replay, versioning,
and graceful-degradation posture for the v0.2.0rc1 release. It is a companion
to `docs/architecture/technical-design-v0.2.0rc1.md`, which covers failure
modes and component design.

---

## 1. Capacity / headroom (local CLI workloads)

### Hand-authored performance budgets

Source of truth: `perf/manifest.json`. Each hero asset has `total_ms_max=200000` (200 s). Stage-level budgets are proportioned within that ceiling (shape is typically the dominant stage on the reference path at <200 ms; Blender topology, when active, is capped at the blender subprocess `timeout_s=300` default from `lathe/runtime_config.py:175`).

| Hero | Budget | Observed (courier_drone, warm cache) |
|---|---|---|
| courier_drone | 200 s | ~2.4 s (reference path, cache miss) |
| brassbound_chest | 200 s | perf/manifest.json |
| all hero family | 200 s | perf/manifest.json |

Observed wall-clock values are captured in `docs/release/evidence-bundle-v0.2.0rc1/runtime-posture-cold-warm-recovery.txt`.

### Memory footprint

No explicit RSS cap is set in `lathe/scaffold_compiler.py` or `lathe/asset_graph.py` at this release. The reference path loads the full normalized program into memory as Python dicts. For hero-family assets (~10–50 part intents, modest ref images), peak RSS is expected to stay under 500 MB. There is no streaming path for oversized assets.

`requires-human: establish and document peak RSS envelope via profiling on the 9-hero family before public launch.`

### Concurrency

One CLI process per machine is the tested and documented posture for v0.2.0rc1. Parallel builds into **separate** output directories are safe: each `BuildExecutor` instance writes only to `self.out_dir` and to the shared cache (via atomic rename — see Section 4). Parallel builds into the **same** output directory produce an OS-level `Permission denied` error on Windows (observed: `lathe error [lathe.cli.permission_denied]`) rather than a clean diagnostic or rejection gate. See Section 3.

### Hosted service / RPS budgets

v0.2.0rc1 ships no hosted service. RPS, load tests, and "sustained 30-minute test at target peak × 3" do not apply. This is a local CLI-only release. Phase 10 of the readiness pass handles the SLO/dashboard gap for when a hosted service is introduced.

---

## 2. Cold start / warm start / recovery time

Full transcripts: `docs/release/evidence-bundle-v0.2.0rc1/runtime-posture-cold-warm-recovery.txt`

| Scenario | Command | Elapsed |
|---|---|---|
| Cold start (cache cleared) | `lathe check examples/courier_drone.lth` | ~2503 ms |
| Warm start (Lark cache hot) | same command immediately after | ~1872 ms |
| Full build (reference path, cache miss) | `lathe build ... --out dist` | ~2418 ms |
| Full build (cache hit, copytree restore) | same build twice | ~2494 ms |
| `lathe doctor` | environment + backend probe | ~13 515 ms |

Cold-to-warm speedup on `lathe check` is ~630 ms, attributable to the Lark grammar cache (`.lathe_lark_cache/`). The build cache (`lathe_cache_dir()/builds/<key>`) operates at `copytree` granularity: a cache hit restores the entire prior output tree and returns in the same ~2.4 s wall-clock range as a fresh build at this asset size.

`lathe doctor` is slow (~13.5 s) because it probes every backend including a Hunyuan HTTP health check with a timeout. For CI usage, `lathe check` or `lathe build` directly is the recommended fast entry point.

### Recovery from interrupted build

`requires-human: process-kill simulation requires interactive OS testing on a non-sandbox machine. Procedure: run `lathe build` in one terminal, kill the Python process mid-run (Ctrl-C or `kill`), verify that (a) the partial `--out` directory is left in place but `build_report.json` is absent, (b) re-running the same command proceeds to produce a complete certified build. The cache staging path in `lathe/executor.py:467-497` uses `tempfile.mkdtemp` + `rename` so the cache key entry is either complete or absent — no partial cache entry should survive a kill. The partial `out_dir` is NOT automatically cleaned, consistent with the policy of preserving evidence for debugging.`

---

## 3. Forced-kill / cache corruption / concurrent builds

### Forced kill during build

`requires-human: see recovery procedure above. Not safely simulatable in a sandboxed test runner.`

Relevant code: `lathe/executor.py:467–497`. The staging pattern is:

1. `mkdtemp` creates `.{cache_key}.*.tmp` next to the target cache entry.
2. `copytree(out_dir, staging_dir)`.
3. Write `manifest.json` into staging dir.
4. `staging_dir.rename(cache_dir)` — atomic on POSIX, best-effort on Windows (NTFS atomic rename is platform-dependent).
5. `finally: shutil.rmtree(staging_dir, ignore_errors=True)` cleans the temp dir if the rename did not consume it.

If the process is killed after step 2 but before step 4, a `.{key}.*.tmp` orphan directory may remain in the cache root. It is not automatically cleaned; `lathe cache clean` will not remove it (it does not match the expected cache key directory pattern). `requires-human: add orphan-tmp cleanup to `lathe cache clean` before public launch if temp orphans are a concern in long-running CI environments.`

### Cache corruption behavior

Tested: truncating / corrupting a `manifest.json` in a cache entry.

- `lathe check` is unaffected (it does not read build cache).
- `lathe build` reads `manifest.json` via `_restore_cached_build()` at `lathe/executor.py:428–465`. If the manifest JSON is corrupt (`json.JSONDecodeError`), `_restore_cached_build` returns `None` and the build proceeds as a cache miss. The corrupt entry is not deleted; a new entry is written under the same key (if the entry directory already exists, `_persist_build_cache` returns early at `lathe/executor.py:472`, leaving the corrupt entry in place).

Result: corrupt manifest produces a silent cache miss and a clean rebuild. The corrupt entry persists until manual `lathe cache clean`.

`requires-human: verify behavior when the cache entry's build_report.json (not just manifest.json) is corrupt — the current code path reads it at line 435 and returns None on JSONDecodeError, which should also trigger a clean rebuild.`

### Concurrent builds — separate output dirs

Two concurrent `lathe build` calls into different `--out` directories complete successfully and produce identical SHA-256 for the packaged outputs (observed: `5e88598952ceef8f...` for both). The shared build cache uses atomic staging-dir rename; the second writer that races to rename will fail with `FileExistsError` (or equivalent), which is caught and logged as a debug-level cache persistence failure at `lathe/executor.py:485–494`. No data loss occurs.

### Concurrent builds — same output dir

Two concurrent builds into the same `--out` directory produce a `lathe error [lathe.cli.permission_denied]` error on Windows when the second build attempts to `shutil.rmtree` or recreate the output directory while the first is writing to it. The error message is `Permission denied` without a user-oriented explanation. No clean rejection gate exists.

`requires-human: add a same-dir exclusive lock or a clear diagnostic ("another lathe build is writing to this directory") before documenting concurrent builds as supported.`

---

## 4. Cache locking posture

`lathe/cache.py` and `lathe/executor.py` contain **no file-lock or sentinel mechanism**. The design relies on:

- `tempfile.mkdtemp` + `staging_dir.rename(cache_dir)` for atomic cache writes (executor.py:473–483).
- OS-level exclusive file handles for the output directory on Windows.

There is no cross-process build-cache lock. If two processes race to write the same cache key, the first to finish the `rename` wins; subsequent writers will find `self.cache_dir.exists()` is True at line 472 and return early — no duplicate write.

`requires-human: cache locking posture decision before any concurrent-CLI claim. Current posture: no lock, race-safe for cache writes, not race-safe for shared `--out` directories.`

---

## 5. Idempotency posture

| Command | Idempotent? | Notes |
|---|---|---|
| `lathe check` | Yes | Pure validation; no file writes. |
| `lathe build` (cache miss) | Yes (deterministic) | Same source → same SHA-256 outputs (verified: `5e88598952ceef8f...` across multiple runs). Cache key is `hash_obj({cache_version, normalized_program, asset, runtime_config, build_environment})` (`executor.py:223–231`). |
| `lathe build` (cache hit) | Yes | Returns cached report unchanged; `copytree` to new out_dir. |
| `lathe doctor` | Yes | Read-only probes; exits 0 on warnings. |
| `lathe telemetry enable` | Yes | Re-calling enable preserves existing salt (`telemetry.py:115`). |
| `lathe telemetry disable` | Yes | Preserves salt; sets `enabled=False`. |
| `lathe publish` | Scaffold only | `lathe/cli/publish_cmd.py` checks that `build_dir.exists()` but has no replay guard. Re-running publish on the same build does not re-sign or re-upload in the current scaffold. `requires-human: add idempotency note to publish docs before GA.` |

---

## 6. Replay safety

### `lathe build`

Replaying the same `lathe build` command (e.g., a CI job re-runs) will find the cache hit and return immediately from `_restore_cached_build` with the same certified report. The cache key embeds the program hash, asset name, runtime config, and backend environment — so a change to any input invalidates the cache and triggers a full rebuild. This is the intended behavior.

### `lathe publish`

`lathe/publish/signed_repro.py` emits a `reproducibility_receipt.json` with an ed25519 signature over the build snapshot. A replay writes a new receipt with a fresh timestamp (`datetime.now(UTC)`) but identical snapshot content. The signature will differ (timestamp is in the signed payload). There is no "already published" guard; replaying publish on the same build outputs a second receipt file, overwriting the first.

`requires-human: decide whether re-signing on replay is acceptable or whether the receipt should be append-only / skip-if-exists before public publish flow is documented.`

---

## 7. API / CLI versioning policy

Source of truth: `docs/versioning.md` and `docs/architecture/contracts.md`.

### Stable CLI flags (v0.2.0rc1)

The subcommand surface listed in `docs/cli_reference.md` is considered stable at this release: `check`, `build`, `plan`, `materialize`, `doctor`, `cache`, `publish`, `telemetry`. The global flag `--debug-traceback` and `--strict-prompt-injection` are stable. Internal subcommands (`parse`, `normalize`, `fmt`, `schema`) may change behavior without a major bump, as they are documented as developer utilities.

### Versioned manifest schemas

| Manifest | Schema file | Version field |
|---|---|---|
| Package manifest | `stages/package/package_manifest.json` | implicit (no schema version yet) |
| Trace manifest | `stages/package/trace_manifest.json` | implicit |
| Selector manifest | `schema/lathe.selector.schema.json` | `schemaVersion` |
| Budget manifest | `schema/budget_manifest.schema.json` | `schemaVersion` |
| Collision manifest | `schema/collision_manifest.schema.json` | `schemaVersion` |
| Reproducibility receipt | `schema/reproducibility_receipt.schema.json` | `schema_version: 1` |
| Build cache manifest | `lathe.cache_manifest.v1` (in-file) | `cache_version: v10_rc2` |

`requires-human: the package_manifest.json and trace_manifest.json lack explicit `schemaVersion` fields. These are user-facing artifacts listed in `docs/architecture/contracts.md`. Add schema versioning before treating them as stable downstream contracts.`

### Deprecation policy

See `docs/versioning.md`. Breaking changes to public contract surfaces require either a MAJOR version bump or a new versioned ID with the old ID retained for at least one MINOR release. See also Section 8.

### Cross-references

- `docs/adr/0009-public-contract-index.md` — the cross-cutting contract rule.
- `spec/lathe-v0.1.md` — language-spec compatibility anchor.

---

## 8. Deprecation policy for CLI flags and manifest schemas

**Proposed policy (not yet ratified):**

1. A deprecated CLI flag or manifest field emits a `DeprecationWarning` when used, with a message naming the removal target version.
2. The deprecated surface is removed in the next MAJOR release.
3. Deprecated backend/contract IDs are retained for at least one MINOR release (per `docs/versioning.md`).

Precedent: `shape.allow_fallback` is currently emitting deprecation warnings in `lathe/providers/selection.py:301–311` as a forward signal before V0.2 flips `strict` defaults.

`requires-human: ratify this deprecation policy formally (owner + date) before public launch. The current policy is proposed, not enforced.`

---

## 9. Public contract IDs — test coverage

Contract IDs come from `docs/architecture/contracts.md`, `docs/versioning.md`, and grep of the codebase.

| Contract ID | Stage | Contract test |
|---|---|---|
| `lathe.shape.intent_mesh_handoff_v1` | shape | `tests/contract/test_shape_handoff_v1.py` — byte-level SHA-256 pin + field set + provider registry |
| `lathe.topology.blender_hard_surface_v1` | topology | `tests/contract/test_stable_backend_contracts.py` — registered, versioned, semver-valid, stack-binding |
| `lathe.uv.xatlas_v1` | uv | `tests/contract/test_stable_backend_contracts.py` — same |
| `lathe.package.openusd_gltf_v1` | package | `tests/contract/test_stable_backend_contracts.py` — same |
| `lathe.stack.hard_surface_game_asset_v1` | stack | `tests/contract/test_stable_backend_contracts.py` — stack accepts minimal public asset |
| `lathe.stack.soft_surface_prop_v1` | stack | `tests/contract/test_stable_backend_contracts.py` — same |
| `lathe.topology.blender_subdiv_v1` | topology | `tests/contract/test_stable_backend_contracts.py` (covered by parametrize over `STABLE_BACKEND_STAGES`) — `requires-fix-before-launch: blender_subdiv_v1 is in BACKENDS but NOT in `STABLE_BACKEND_STAGES` in the contract test. Verify it is either in the stable set and tested, or explicitly documented as unstable.` |

**Summary:** 6 public contract IDs have direct contract tests. The shape handoff has the strongest guarantee (byte-level hash pin). The 4 non-shape backend IDs have registry/versioning/stack-binding tests but no byte-level hash pin.

`requires-fix-before-launch: lathe.topology.blender_subdiv_v1 is registered in BACKENDS but excluded from STABLE_BACKEND_STAGES in test_stable_backend_contracts.py. Either add it to the stable set and test it, or add a comment in the contract test marking it as explicitly non-stable.`

---

## 10. Schema migration tests

`schema/lathe.schema.json` is the canonical normalized AST schema. There are no dedicated migration tests for schema version transitions in `tests/` at this release — the AST schema has no `$schema`-level version field, and the `schemaVersion` pattern is used only in the selector/budget/collision manifests.

The `tests/unit/test_schema.py` suite validates that examples conform to the current schema but does not test forward/backward compatibility between schema versions.

`requires-human: schema migration tests are not applicable until a schema version bump is required. Record this decision and revisit when the first breaking AST schema change is planned.`

---

## 11. Third-party dependency audit

Source: `pyproject.toml` runtime dependencies. Licenses from `pip show`; upstream activity tagged `requires-human` per scope instructions.

| Dep | Version | License | Alternative | Lock-in |
|---|---|---|---|---|
| lark | 1.3.1 | MIT | pyparsing, PLY | low — grammar rewrite only |
| jsonschema | 4.26.0 | MIT | pydantic, cerberus | low |
| numpy | 2.4.2 | BSD-3 | none practical | medium |
| Pillow | 12.1.1 | HPND (MIT-like) | opencv-headless | low |
| trimesh | 4.12.0 | MIT | open3d | medium |

Optional extras (not runtime unless installed):

| Dep | Extra | License | Lock-in |
|---|---|---|---|
| xatlas | xatlas | MIT (native) | libuv-atlas | medium |
| torch | vggt | BSD | medium — no easy swap |
| scipy | export | BSD-3 | low |
| cryptography | publish | Apache-2 | low |
| boto3 | publish | Apache-2 | medium (AWS) |

`requires-human: pull last-release dates from upstream release feeds (PyPI JSON API) at release-cut time and add to this table.`

---

## 12. Graceful degradation per optional tool

### Blender unavailable

Code path: `lathe/core/stages/topology.py` → `run_blender_topology` attempts subprocess; on failure falls to `run_reference_topology_cleanup` (imported from `lathe/core/geometry`). ADR: `docs/adr/0002-blender-and-xatlas-fallback-policy.md`.

Trace record: `adapter_report["status"] = "fallback"` + `adapter_report["fallback_reason"]` written to topology stage bundle. `actual_provider_id` diverges from `requested_adapter`. Observable via `lathe doctor` and `build_report.json`.

Runbook: Phase 5 operational runbooks (see `docs/release/launch-plan-v0.2.0rc1.md`).

### xatlas unavailable

Code path: `lathe/core/stages/uv.py` falls to `reference_box` UV adapter when xatlas is not installed. Same attempted-vs-actual tracing pattern as topology. `lathe doctor` reports `xatlas: missing (not_installed)` with a recommended install action.

### Hunyuan unavailable

Code path: `lathe/providers/selection.py` — `auto` provider selection falls to `reference_conditioned_v1` when Hunyuan HTTP probe fails (`selected_via: "auto_fallback"`). Trace records `actual_provider_id` and `fallback_reason`. `lathe doctor` reports `lathe.provider.shape.hunyuan2_1_http_v1: unavailable`.

### VGGT unavailable

Code path: `lathe/providers/adapters/vggt.py` raises `ShapeProviderUnavailable` when `torch` or `torchvision` is missing (`lathe/providers/adapters/vggt.py:22`). Provider mux catches and falls to `reference_conditioned_v1`. `lathe doctor` reports `VGGT: unavailable (device=cpu)`.

### Telemetry ingest fails

Code path: `lathe/telemetry.py:262–299`. `emit_build_ping` is wrapped in `try/except (ImportError, OSError, RuntimeError, TypeError, ValueError): return False`. Any network error, import error for the optional `lathe.net` module, or serialization error results in `False` return with no exception propagated. Emission is fully failure-silent by design (Plan 09 Phase 10b, documented at `lathe/telemetry.py:3–4`).

### PyPI / GitHub Actions outage

Operational fallback: `uv.lock` is checked in; `pip install --no-index` from a local wheel cache is possible. See Phase 5 runbooks. Build host does not require PyPI at build time once the venv is bootstrapped.
