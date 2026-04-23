# Review: Plan 03 — Architecture

## Summary

Strong plan. It names the right seams (shape subsystem, parser, provider mux), introduces layering enforcement and ADRs, and treats the stable `intent_mesh_handoff_v1` contract as frozen. Biggest miss: **`executor.py` is underweighted** — at 2,315 LOC with a 940-line `BuildExecutor` god-class it is the largest and most tangled module in the repo, larger than `parser.py`. Phase 7 mentions it but buries it under "Targets" and assigns it less scope than the shape-provider split. The second-stack choice is architecturally thin, and the entry-point plan needs a migration story for `runtime_config.py`'s learned-provider JSONs.

## Coverage checklist (vs. original findings)

| Finding gap | Addressed? | Where |
|---|---|---|
| 9-module shape subsystem | Yes | Phase 1 table |
| `parser.py` 1666 LOC | Yes | Phase 7.2 |
| `shape_providers.py` ~1000 LOC | Yes | Phase 1 |
| Provider I/O + selection mixed | Yes | Phase 1 `providers/{registry,mux,transport,adapters}` split |
| No plugin API for backends | Yes | Phase 2 |
| No layering enforcement | Yes | Phase 3 `.importlinter` |
| No ADRs | Yes | Phase 4 |
| Only one backend stack | Yes | Phase 6 |

## Citations verified

- **9 shape modules** — confirmed. All of `asset_graph.py`, `assembly_kernel.py`, `shape_ir.py`, `feature_grammar.py`, `feature_fusion.py`, `mesh_finalize.py`, `conformance.py`, `shape_backend.py`, `shape_providers.py` exist at `D:\lathe_v0_1\lathe\*.py`.
- **LOC claims** — confirmed and sharpened: `parser.py` = 1,666, `shape_providers.py` = 998, `shape_backend.py` = 665, **`executor.py` = 2,315** (not mentioned in plan intro but cited in Phase 7), `backends.py` = 360, `capabilities.py` = 495.
- **No `lathe/contracts/` package** — confirmed absent.
- **No `docs/adr/`** — confirmed absent. `docs/Specs/Lathe-V1.*-Spec.md` (V1.0 → V1.3.1) function as implicit ADRs for language-level decisions but not for architectural ones (stack selection, fallback policy, mux).
- **Registration mechanism is pure dicts** — confirmed: `backends.py:15 BACKENDS` and `backends.py:204 STACKS` are module-level `dict`s mutated only at import; no plugin hook.
- **`pyproject.toml` has no entry points** — confirmed (only `[project.scripts] lathe = "lathe.cli:main"`).
- **`shape_backend.py` → `shape_providers.py` coupling** — confirmed: `shape_backend.py:15 from .shape_providers import maybe_run_shape_provider`; `executor.py:31 from .shape_backend import collect_shape_conditioning, run_shape_backend`. Plan's back-compat shim is necessary.
- **`bridge/blender_plan.py` import surface** — confirmed minimal: only `..capabilities.probe_blender` and `..inspection.evidence.build_inspection_policy_ir`. Not impacted by Phase 1 moves.
- **Capability-discovery duplication** — confirmed: `probe_blender`/`probe_hunyuan_endpoint`/`probe_vggt`/`probe_topology_backend`/`probe_uv_backend` are called from 7 modules (`capabilities`, `doctor`, `cli`, `executor`, `blender_execution`, `bridge/blender_plan`, `shape_providers`) with no single discovery cache.

## Already-done / pre-existing strengths

- `capabilities.py` is already a centralized probe module — Phase 2's `probe()` on each `StageBackend` should delegate here rather than re-implement.
- `runtime_config.py` (176 LOC) already mediates learned-provider selection and has a clean `merge_runtime_config` API — it is a pre-existing seam the plan doesn't acknowledge.
- The `std/` source stdlib and `examples/` fixtures are already organized as a de-facto pluggable library layer, so user-space extensibility partially works today.

## Gaps in the plan

1. **`executor.py` is the real god-module.** `BuildExecutor` spans `executor.py:81-1021` (~940 lines in one class) and dispatches all 11 stages inline. The plan groups this under Phase 7 alongside parser as a "target" but allocates equal scope — the executor split is at least as large as the whole shape subpackage move and probably should be its own phase with its own ADR (`0007-stage-dispatcher.md`).
2. **`runtime_config.py` vs. entry points.** JSON runtime-configs (`examples/runtime_configs/*.json`) currently select providers by string ID. After Phase 2, there are two registration mechanisms: entry points and JSON. The plan doesn't describe the precedence rule or the migration path for user JSON configs, which will silently break when builtin IDs move into entry points.
3. **Capability-probe duplication not addressed.** Seven modules import probes directly from `capabilities.py`. Phase 2's `probe()` method on `StageBackend` protocol risks becoming a third source of truth. The plan should state that backend-level `probe()` delegates to `capabilities.py` and is the *only* caller outside doctor.
4. **No contract-freeze test today.** `tests/test_contract_frozen.py` is listed only under Phase 8; it should land in Phase 1 before any shape moves, since the shape re-export shim is the moment the contract dict could drift.
5. **No rollback plan if entry points slow cold-start past the cache.** "Cache in `~/.lathe/plugin_cache.json`" is good but the plan doesn't define a fallback if the cache is stale — built-in registry should remain authoritative and entry points layer on top.

## Feasibility — shape subpackage move

Realistic. The import surface is narrow:
- `executor.py:31` and `shape_backend.py:15` are the only two production importers of the files being moved (verified by grep). Three-line re-export shims in `lathe/shape_backend.py` and `lathe/shape_providers.py` will cover them.
- `bridge/blender_plan.py` does **not** import any shape module — no risk there.
- Test suite: `tests/test_shape_providers.py` and `tests/test_backends.py` import via the current paths; shims preserve them.
- Risk: `shape_backend.py` also imports `asset_graph`, `conformance`, `scaffold_compiler` directly (line 12-14), so Phase 1 must land the shape subpackage and all three shims in one commit, not piecemeal.

## Second-stack choice — `uv_sheet_decal_v1`

Architecturally **marginal**. It only swaps one stage backend (UV) and reuses three. That exercises the backend-registry and stack-dispatch code paths but not the stage-boundary contracts. A stronger proof point would swap at least two stages — e.g., a `retopo_free_v1` stack that pairs `topology → lathe.topology.passthrough_v1` (new) with `uv → trim_sheet_v1`, forcing the plan to prove topology-output compatibility with a non-Blender backend. Keep `uv_sheet_decal_v1` if scope is tight, but add an explicit note that plugin-contract coverage is "UV-only" in V1 and a follow-up stack is required before declaring extension points proven.

## Additional architectural issues the plan misses

- **`BuildExecutor` constructor coupling** — `executor.py:81` initializes stage state, IR holders, and runtime config in one `__init__`. Splitting stages per Phase 7 requires introducing a `StageContext` dataclass first; the plan doesn't mention it.
- **`backends.py` `evaluate_backend`/`evaluate_stack`** (lines 259-319) hardcodes stage-specific validation in a single function with `if stage == ...` branches. After Phase 2, each `StageBackend.probe()` should own its own compatibility rules; current logic must move out of `backends.py` or it becomes a fourth registration path.

## 10/10 verdict

**Not yet — conditional.** The plan is directionally correct and the Phase 8 criteria are measurable. To reach 10/10 it needs:

1. Promote the `executor.py` split to a first-class phase (own ADR, own LOC budget).
2. Define entry-point ↔ `runtime_config.py` precedence rule.
3. State explicitly that `capabilities.py` remains the single probe implementation; backend `probe()` wraps it.
4. Land `test_contract_frozen.py` in Phase 1, not Phase 8.
5. Either strengthen the second stack to swap 2+ stages, or explicitly scope V1 plugin proof as UV-only with a follow-up.

With those amendments the plan is executable and the 10/10 criteria become defensible.
