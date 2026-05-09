# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What Lathe is

Lathe is a declarative language + reference compiler/runtime for 3D asset intent. Source `.lth` files describe *what* an asset is, *how* to build it, and *what counts as passing*. The compiler produces certified production-ready asset packages (usd/glb/gltf/obj). This repo is the **v0.1 reference scaffold** with additive V0.8 → V1.3.1 language layers on top.

**Product boundary:** Wonder is the creative director that asks for assets, scenes, inspections, repairs; Lathe is the deterministic execution substrate that turns those requests into geometry, materials, previews, reports, and packages. Learned providers may exist as optional proposal sources, but they are not the product center and must not become the critical path for asset quality.

**Core invariant:** the stable shape-stage contract ID `lathe.shape.intent_mesh_handoff_v1` is treated as a public contract. Do not change it unless the task explicitly asks for a migration.

**Current implementation northstar:** use `docs/asset-quality/lathe-implementation-northstar.md` as the source of truth for the next visible-geometry / asset-quality implementation push. It consolidates the imagination-to-life roadmap, asset-quality research, blocker audits, and Sprint 0 execution path. Sprint 0 fixture is `industrial_crate` with `mechanical_door` / `fantasy_weapon` as the guardrail to prove changes aren't crate-only.

## Commands

Canonical invocation is `python -m lathe.cli ...` from the repo root (works whether or not the editable install is active). Once `pip install -e .` is done, the `lathe` console script is also available.

Bootstrap a working `.venv` (Windows-first; `.venv/Scripts/python.exe` is the expected interpreter):

```bash
scripts/bootstrap_local.sh --dev --export          # bash
scripts/bootstrap_local.ps1 -Dev -Export           # PowerShell
```

Primary loop:

```bash
python -m lathe.cli doctor                          # environment/provider availability
python -m lathe.cli check examples/courier_drone.lth
python -m lathe.cli plan examples/courier_drone.lth courier_drone
python -m lathe.cli materialize examples/courier_drone.lth courier_drone_mobile
python -m lathe.cli build examples/courier_drone.lth courier_drone --out dist
python -m lathe.cli quick examples/brassbound_chest.lth brassbound_chest --out preview.glb [--render preview.png]   # ~30-60s preview (no bakes/LODs/validation), inspired by ForgeCAD
python -m lathe.cli quick examples/alien_grove_showcase.lth alien_grove --out tmp_alien_grove.glb --no-cache         # CAPSTONE imagination-to-life demo: hard-surface + vegetation + terrain + SDF + WFC in one .lth
```

Imagination-to-Life demos (one paradigm each, plus the showcase combining all five): see `docs/imagination_to_life_demos.md`.

Testing:

```bash
python -m pytest -q                                 # full suite
python -m pytest tests/test_build.py -q             # single file
python -m pytest tests/test_language_v13.py::TestName::test_case -q   # single test
scripts/lathe_smoke.sh                              # = pytest -q
scripts/lathe_asset_loop.sh <file.lth> <asset> [out_dir]   # check + plan + materialize + build
```

Lathe-level tests (distinct from pytest — these run `test` / `benchmark` declarations inside `.lth` sources):

```bash
python -m lathe.cli test
python -m lathe.cli bench
```

Provider/runtime wiring is opt-in via `--runtime-config`:

```bash
python -m lathe.cli build <file> <asset> --out dist --runtime-config examples/runtime_configs/hunyuan_http.json
python -m lathe.cli build <file> <asset> --out dist --runtime-config examples/runtime_configs/vggt_local.json
python -m lathe.cli build <file> <asset> --out dist --runtime-config examples/runtime_configs/auto_learned.json
```

No runtime config ⇒ conservative path: shape falls back to `lathe.provider.shape.reference_conditioned_v1`; topology/UV fall back explicitly when Blender or xatlas are unavailable. This is intentional for smoke-test ergonomics.

## Architecture

### Compiler pipeline (stages)

```
refs → intent → shape → topology → uv → surface → (execution) → rig → interfaces → physics → optimize → validate → package → publish
```

Shape is the only probabilistic stage. Topology, UV, surface (bakes), validate, and package are deterministic. The compiler rejects incompatible configs before runtime via `lathe/backends.py` + `lathe/checker.py`.

### Source → AST → build plan → artifact

1. `lathe/parser/` (package; entry `fast_parser.py` + `transformer*.py`) parses `.lth` text (grammar in `grammar/lathe.lark`) into raw AST JSON; resolves relative refs against the source file. `.lathe_lark_cache` is a build artifact — safe to regenerate.
2. `lathe/normalizer.py` inserts canonical defaults.
3. `lathe/resolver.py` applies `uses` chains, profile/contract inheritance, and variant patches; produces a materialized asset.
4. `lathe/checker/` (package: `language.py`, `assets.py`, `declarations.py`, `surface.py`, `cross_stage.py`, `interfaces.py`, `experimental.py`) enforces semantic rules and backend-compatibility constraints.
5. `lathe/planner.py` emits effective build plans.
6. `lathe/executor.py` drives the deterministic downstream runtime; the actual stage runners live in `lathe/core/stages/{shape,topology,uv,surface,execution,interfaces,physics,optimize,validate,package,publish,rig}.py` and execute in `STAGE_ORDER`.
7. `schema/lathe.schema.json` is the canonical JSON-schema for the normalized AST and must stay in sync with the grammar.

### Shape stage internals

Under the stable `lathe.shape.intent_mesh_handoff_v1` contract, shape now flows:

```
intent → AssetGraph → assembly blueprint → ShapeIR → fused search geometry → authoritative mesh → optional provider proposals → conformance fit → deterministic downstream
```

Key modules: `asset_graph.py`, `assembly_kernel.py`, `scaffold_compiler.py`, `shape_ir.py`, `feature_grammar.py`, `feature_fusion.py`, `mesh_finalize.py`, `conformance.py`, `shape_backend.py` (runs the contract), `shape_providers.py` (learned/fallback provider mux).

`lathe/asset_quality/` is the active center for the visible-geometry / quality push: `shape_ir_v2.py` (next-gen ShapeIR with new primitives like `extruded_profile`, `revolved_profile`, `torus`, `subdivision_box`, `swept_profile`), `construction_graph.py`, `design_brief.py`, `family_grammar.py`, `grammar_lowering.py`, `highlow_relation.py`, `diagnostics.py`, `quality_planner.py`, `preview_evidence.py`, `silhouette.py`, `vision_critique.py`. Diagnostics here are evidence-driven and judge visible output.

Providers are **optional proposal sources** under a stable contract, not the product center. When a provider falls back, the trace records both the *attempted* and the *actual* provider. The same attempted-vs-actual pattern applies to the Blender topology adapter and xatlas UV adapter.

### Backend stack

First runnable stack: `lathe.stack.hard_surface_game_asset_v1`, binding `shape → lathe.shape.intent_mesh_handoff_v1`, `topology → lathe.topology.blender_hard_surface_v1`, `uv → lathe.uv.xatlas_v1`, `package → lathe.package.openusd_gltf_v1`. Adapters gracefully degrade to deterministic reference paths when Blender / xatlas are absent.

### Source stdlib (`std/`)

V0.8+ authoring layer: `std/{families,components,materials,patterns,surface_programs,palettes,repair,spaces,benchmarks,kits,libraries,mechanisms,policies}/`. These are importable from user `.lth` sources.

### V1.1/V1.2/V1.3 layers

- V1.1 adds `library`, `kit`, `reference_set`, `reconstruct_policy`, `adapt_policy`, `assembly_policy`, `fit_profile`, `transfer_rule` + asset blocks `fit`, `transfer`, `reuse`, `constraints`, `ingest`, `assembly_rules`. IRs: `fit_ir.py`, `transfer_ir.py`, `kit_ir.py`, `reference_ir.py`, `reuse_ir.py`.
- V1.2 adds governed surface authoring: `surface_backend`, `surface_policy`, `decal_library`, `mask_program`, `trim_sheet`. Emits `surface_control_pack`, `atlas_assembly_ir`, `surface_validation_ir`, `surface_repair_ir`, `surface_backend_report`. Codex ImageGen is a governed backend with explicit fallback.
- V1.3/V1.3.1 adds Blender-backed execution planning, bake/render intent, retained `.blend` artifacts, and the Codex-operated bridge (`lathe/bridge/blender_plan.py`, CLI: `lathe bridge doctor|plan`, `lathe inspect`, `lathe export-blend`, `lathe inspect-blend`).

### Validators

`lathe/validators/{semantic_quality,visual_quality,flow_quality,surface_quality,silhouette}.py` run evidence-based certification (geometry integration, render-level silhouette checks, flow-specific metrics like `semantic_preservation_quality`, `join_legality`, `reconstruct_honesty_score`). Weak/toy-like outputs fail certification — don't weaken these without intent.

## Truthful claim labels (from AGENTS.md "Rule of Truth")

When reporting on outputs, traces, or evidence, use these exact labels rather than implying success:

- `real` — visible in mesh / material / preview / export evidence.
- `proxy` — deterministic placeholder or non-final evidence, explicitly labeled.
- `fallback` — requested path degraded to another path; record both *attempted* and *actual*.
- `unsupported` — rejected or warned before false success.
- `not verified` — code exists but no relevant command/artifact was produced in the current run.
- `blocked` — required dependency or upstream condition is missing and named.

Forbidden state: language/docs/validator/report says it happened, but mesh/material/preview/package/import evidence does not prove it. Never claim "production-ready", "game-ready", "Roblox/Unity/Unreal-ready", "fixed", "complete", or "done" unless the relevant evidence was actually generated and checked. The same attempted-vs-actual pattern applies to providers, kernels, renderers, topology adapters, UV adapters, and package exporters.

## Change rules (from AGENTS.md)

Language-contract changes must land as a coordinated update across all layers:

- `spec/lathe-v0.1.md`
- `grammar/lathe.lark`
- `schema/lathe.schema.json`
- parser / normalizer / resolver / checker behavior
- examples + tests

Backend/provider changes must preserve stable backend IDs, the shape bundle contract, and downstream topology/UV/packaging contracts unless the task explicitly requests a migration. Prefer mocked tests for external services (Hunyuan HTTP, VGGT).

Public language surface treated as stable: `profile`, `contract`, `critic`, `asset`, `variant`, plus the build-stage names above.

Examples: keep at least one runnable `generate` example and at least one runnable `reconstruct` example. Keep example refs minimal and checked into `examples/refs/`.

## Repo conventions

- **Ignore `dist_*`, `tmp_*`, `warm_*`, `v05_*`, `cache_probe_*` directories at the repo root** — those are transient build outputs from past runs, not source. The `dist/` name is a convention, not a fixture; `--out` can point anywhere.
- Hero-family examples (`brassbound_chest`, `industrial_crate`, `mechanical_door`, `console_terminal`, + V1.0: `sci_fi_wall_panel`, `service_cabinet`, `control_pedestal`, `supply_container`) default to native-only compilation; learned providers are opt-in via runtime config.
- `.lathe_lark_cache` is a parser cache — safe to regenerate.
- Codex integration lives in `.codex/` (`config.toml`, `agents/`) and `.agents/skills/`; see `docs/codex_integration.md`.

## Finishing a change

1. Run the narrowest relevant check first (single-file pytest, `lathe check`, or an asset loop).
2. Then `python -m pytest -q` when behavior changed.
3. Confirm examples/fixtures still reflect current behavior.
4. Call out remaining scaffold limitations explicitly rather than implying they are complete — `publish` runner, canonical `fmt`, and full multi-round autonomous repair loops are all intentionally still scaffolds.
