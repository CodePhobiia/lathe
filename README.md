# Lathe v0.1

Lathe is a declarative programming language and compiler/runtime for turning 3D asset intent into certified production-ready asset packages.

This repository is a working **reference compiler scaffold** for Lathe v0.1. The current milestone is a native **parametric hard-surface assembly compiler** under the stable `lathe.shape.intent_mesh_handoff_v1` contract. Learned providers still exist, but they are optional proposal sources inside Lathe’s compiler flow rather than the product center.

## What is implemented

- V0.8 language-core expansion for reusable `family`, `component`, `material`, `palette`, `space`, `repair_policy`, `fixture`, `test`, and `benchmark` declarations
- additive V0.9 declaration support for `pattern`, `surface_program`, typed `family` declarations, and `asset ... from family`
- additive V1.1 declaration support for `library`, `kit`, `reference_set`, `reconstruct_policy`, `adapt_policy`, `assembly_policy`, `fit_profile`, and `transfer_rule`
- additive V1.2 declaration support for `surface_backend`, `surface_policy`, `decal_library`, `mask_program`, and `trim_sheet`
- import resolution for a source stdlib under `std/`
- source-level tests and benchmarks via `lathe test` and `lathe bench`
- a semantic patch API for structural changes to Lathe projects
- text grammar for `.lth` source files
- parser for the core declaration surface
- normalizer that inserts canonical defaults
- resolver for `uses` chains and variant patch application
- materialization of effective assets after profile / contract inheritance
- semantic checker for the first core rules
- JSON Schema for the normalized AST
- builtin backend registry and first backend stack selection
- compiler-time backend compatibility checks
- CLI commands for parse / normalize / schema / doctor / check / plan / materialize / backends / shape-providers / probe-providers / fit / adapt / assemble / reconstruct / build / test / bench / audit / explain / explain-fit / diff-asset / patch
- end-to-end example asset and variant
- deterministic runtime for topology / UV / package
- a stable shape-stage backend contract under `lathe.shape.intent_mesh_handoff_v1`
- a native assembly-first shape core with internal `AssetGraph`, `ShapeIR`, shared hard-surface primitives, a reusable feature grammar, an integrated geometry fusion pass, and an explicit authoritative mesh record for the hero lane
- fidelity-aware offline candidate search over proportions, feature density, and attachment layouts
- a visual-quality validator plus render-level acceptance metrics that reject semantically correct but visibly primitive outputs using geometry and surface evidence rather than backend labels alone
- a hero-only bake/surface slice that emits real `basecolor`, `normal`, `ao`, `curvature`, `id`, `orm`, and `emissive` outputs for the current hero wedge
- a self-reliant hero wedge where chest / crate / door / console default to native-only compilation instead of learned-provider critical-path generation
- V1.1 asset-system flows for mobile adaptation, modular kit assembly, and structured reconstruction, with resolved Reference/Fit/Transfer/Kit IR recorded in shape bundles and flow-specific validation metrics recorded in validation reports and traces
- V1.2 governed surface authoring with Surface Control Pack, Atlas Assembly IR, Surface Validation IR, Surface Repair IR, and explicit Codex ImageGen fallback reporting
- a benchmark harness with positive assets plus a legacy-failure corpus for honest evaluation
- a documented bridge for **Hunyuan3D-2.1** over its HTTP API
- a documented bridge for **VGGT** over its local Python API plus deterministic meshing from predicted point maps
- a real Blender subprocess adapter behind `lathe.topology.blender_hard_surface_v1`, with explicit fallback tracing
- a real xatlas adapter behind `lathe.uv.xatlas_v1` when the Python bindings are installed, with explicit fallback tracing
- stricter semantic validation so weak toy-like outputs fail certification instead of passing by proxy
- tests for parse + normalize + validate + materialize + backend selection + build execution + learned-provider integration seams

## What is intentionally still a scaffold

- live learned inference is optional and depends on an external model runtime being available

That is deliberate. The compiler contract comes first; learned runtimes plug into it.

**Previously-scaffolded items all closed in Wave 4 (V0.1.x):**

- Publish runner — `lathe/publish.py` with local_fs / s3 / supabase / git_lfs drivers + ed25519-signed manifests (BL-31).
- Canonical text formatting — `lathe fmt` token-level reformatter with comment preservation + idempotence (BL-32).
- Multi-round autonomous repair — `lathe/repair_loop.py` with regression guard + rollback + bounded rounds (BL-33).
- Second backend stack — `lathe.stack.soft_surface_prop_v1` as a plugin-model proof with its own topology adapter + silhouette validator (BL-34; full soft-surface UV + curvature continuity deferred — see `docs/second_backend_stack.md`).
- Hero output gallery + benchmark scoreboard — `scripts/render_gallery.py` + `scripts/render_scoreboard.py` + nightly workflow (BL-35).
- Rich reports + artifact viewer + CLI error polish — `lathe/reports/`, `lathe/viewer/`, `docs/error_codes.md`, `--report {terminal,html,json}`, `lathe serve` (BL-36).
- Strict-mode default flip mechanism — `--allow-fallback` flag + DeprecationWarning in V0.1.x; actual default flip in V0.2 (BL-37).
- Stability fuzz + perf baseline budgets + playground concept (BL-38; full 10k-iter fuzz + CI-gated perf + Pyodide in-browser Lathe deferred).

## Install

Base editable install:

```bash
pip install -e .
```

Practical local setup from the repository root:

PowerShell:

```powershell
scripts/bootstrap_local.ps1 -Dev -Export
```

Bash:

```bash
scripts/bootstrap_local.sh --dev --export
```

Optional extras:

- `dev`
  - installs `pytest`
- `hunyuan_http`
  - no extra Python package is required today; the real dependency is a reachable Hunyuan HTTP server
- `vggt`
  - installs `torch` and `torchvision`
  - the official `vggt` package is still a manual source install in this repo flow
- `xatlas`
  - installs the Python `xatlas` bindings
  - on Windows this typically requires Visual Studio Build Tools with the Desktop C++ workload
- `export`
  - installs `scipy` for a fuller optional mesh/export toolchain

Examples:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,export]"
.\.venv\Scripts\python.exe -m pip install -e ".[vggt]"
.\.venv\Scripts\python.exe -m pip install -e ".[xatlas]"
```

Manual VGGT source install after `torch`:

```powershell
git clone https://github.com/facebookresearch/vggt.git external\vggt
.\.venv\Scripts\python.exe -m pip install -e .\external\vggt
```

## CLI

```bash
lathe parse examples/courier_drone.lth
lathe fmt --check examples/*.lth
lathe normalize examples/courier_drone.lth
lathe schema
lathe doctor
lathe backends
lathe shape-providers
lathe probe-providers
lathe check examples/courier_drone.lth
lathe plan examples/courier_drone.lth courier_drone_mobile
lathe materialize examples/courier_drone.lth courier_drone_mobile
lathe test
lathe bench
lathe audit
lathe explain dist_v09_console/console_terminal
lathe patch examples/brassbound_chest.lth --op freeze_dimension --target chest_hero_search --value feature_density
lathe build examples/courier_drone.lth courier_drone --out dist
lathe build examples/courier_drone.lth courier_drone --out dist \
  --runtime-config examples/runtime_configs/hunyuan_http.json
lathe build examples/reconstruct_courier_from_views.lth reconstruct_courier_from_views --out dist \
  --runtime-config examples/runtime_configs/vggt_local.json
lathe fit examples/reconstruct_courier_from_views.lth reconstruct_courier_from_views
lathe adapt examples/console_terminal_mobile_adapt.lth console_terminal_mobile --out dist
lathe assemble examples/service_corridor_wall.lth service_corridor_wall --out dist
lathe reconstruct examples/reconstruct_courier_from_views.lth reconstruct_courier_from_views --out dist
lathe explain-fit dist/reconstruct_courier_from_views
lathe build examples/console_terminal_v12_surface.lth console_terminal_v12_surface --out dist
```

Machine-readable diagnostics:

```bash
lathe doctor --json
lathe doctor --runtime-config examples/runtime_configs/hunyuan_http.json --json
```

## V0.8 Language Core

The repo now includes a first source stdlib and language-level authoring layer:

- `std/families/`
- `std/components/`
- `std/materials/`
- `std/patterns/`
- `std/surface_programs/`
- `std/palettes/`
- `std/repair/`
- `std/spaces/`
- `std/benchmarks/`

The V0.9 hero examples now use this source surface directly:

- [examples/brassbound_chest.lth](/D:/lathe_v0_1/examples/brassbound_chest.lth)
- [examples/industrial_crate.lth](/D:/lathe_v0_1/examples/industrial_crate.lth)
- [examples/mechanical_door.lth](/D:/lathe_v0_1/examples/mechanical_door.lth)
- [examples/console_terminal.lth](/D:/lathe_v0_1/examples/console_terminal.lth)

See [docs/v08_language_reference.md](/D:/lathe_v0_1/docs/v08_language_reference.md) for the new declarations and [docs/v08_migration_guide.md](/D:/lathe_v0_1/docs/v08_migration_guide.md) for the additive migration path from pre-V0.8 source.

## V0.9 Self-Reliant Hero Wedge

The current hero-focused wedge is:

- `brassbound_chest`
- `industrial_crate`
- `mechanical_door`
- `console_terminal`

Those families now compile through a native-first path that keeps asset-generation AI out of the required critical path for `generate`, `assemble`, `adapt`, `validate`, `repair`, `optimize`, and `package`. Providers can still be selected explicitly for testing or optional proposal work, but the default hero flow is self-reliant and offline-capable.

## V1.0 Family Coverage

The repository now ships the full named V1.0 family set in source stdlib form:

- `brassbound_chest`
- `industrial_crate`
- `mechanical_door`
- `console_terminal`
- `sci_fi_wall_panel`
- `service_cabinet`
- `control_pedestal`
- `supply_container`

Current end-to-end runnable examples exist for:

- [examples/brassbound_chest.lth](/D:/lathe_v0_1/examples/brassbound_chest.lth)
- [examples/industrial_crate.lth](/D:/lathe_v0_1/examples/industrial_crate.lth)
- [examples/mechanical_door.lth](/D:/lathe_v0_1/examples/mechanical_door.lth)
- [examples/console_terminal.lth](/D:/lathe_v0_1/examples/console_terminal.lth)
- [examples/service_cabinet.lth](/D:/lathe_v0_1/examples/service_cabinet.lth)
- [examples/control_pedestal.lth](/D:/lathe_v0_1/examples/control_pedestal.lth)
- [examples/supply_container.lth](/D:/lathe_v0_1/examples/supply_container.lth)

## V1.1 Asset-System Flows

The repository now implements the V1.1 language/runtime slice for deterministic ingestion and reuse flows while preserving the stable `lathe.shape.intent_mesh_handoff_v1` shape contract.

Implemented source declarations:

- `library`
- `kit`
- `reference_set`
- `reconstruct_policy`
- `adapt_policy`
- `assembly_policy`
- `fit_profile`
- `transfer_rule`

Implemented asset blocks:

- `fit`
- `transfer`
- `reuse`
- `constraints`
- `ingest`
- `assembly_rules`

Runnable examples:

- [examples/console_terminal_mobile_adapt.lth](/D:/lathe_v0_1/examples/console_terminal_mobile_adapt.lth)
- [examples/service_corridor_wall.lth](/D:/lathe_v0_1/examples/service_corridor_wall.lth)
- [examples/reconstruct_courier_from_views.lth](/D:/lathe_v0_1/examples/reconstruct_courier_from_views.lth)

V1.1 build outputs include resolved `reference_ir`, `fit_ir`, `transfer_ir`, and `kit_ir` in the shape bundle, plus flow-specific validation metrics such as `semantic_preservation_quality`, `join_legality`, and `reconstruct_honesty_score` where relevant.

## V1.2 Governed Surface Authoring

The repository now includes the first V1.2 surface-authoring slice. Lathe remains authoritative for zones, UVs, bakes, maps, validation, repair, and packaging; optional Codex ImageGen is represented as a governed backend and falls back explicitly to deterministic PBR in the reference runtime.

Implemented declarations:

- `surface_backend`
- `surface_policy`
- `decal_library`
- `mask_program`
- `trim_sheet`

New example:

- [examples/console_terminal_v12_surface.lth](/D:/lathe_v0_1/examples/console_terminal_v12_surface.lth)

Hero surface builds now emit:

- `surface_control_pack`
- `atlas_assembly_ir`
- `surface_validation_ir`
- `surface_repair_ir`
- `surface_backend_report`

The trace records whether `lathe.surface.codex_imagegen_v1` was requested, whether it actually ran, and which deterministic fallback was used.

## Codex integration

The repo now includes a project-scoped Codex integration pack:

- `AGENTS.md` for repository instructions
- `.codex/config.toml` for project defaults and profiles
- `.codex/agents/` for custom spawned agents
- `.agents/skills/` for repo-scoped Codex skills
- `scripts/lathe_asset_loop.sh` for the common asset loop
- `scripts/lathe_smoke.sh` for the regression smoke test

See `docs/codex_integration.md` for the full layout and example Codex prompts.

## Native Shape Core

Lathe keeps the same shape-stage backend ID:

`lathe.shape.intent_mesh_handoff_v1`

Under that stable public contract, Lathe now compiles shape through a native assembly kernel first:

`intent -> AssetGraph -> assembly blueprint -> ShapeIR -> fused search geometry -> authoritative mesh -> optional provider proposals -> conformance fit -> deterministic downstream stages`

That means Lathe owns the authoritative scaffold, part graph, symmetry, interfaces, and certification truth layer.

## Optional Proposal Sources

Learned providers still exist under the same stable contract, but only as optional internal proposal sources:

- `lathe.provider.shape.hunyuan2_1_http_v1`
  - image-conditioned learned generation via the official Hunyuan3D-2.1 HTTP server
  - good fit for `generate` and single-image `reconstruct`
- `lathe.provider.shape.vggt_local_v1`
  - multiview learned reconstruction via the official VGGT Python package
  - good fit for multi-image `reconstruct`
- `lathe.provider.shape.reference_conditioned_v1`
  - built-in heuristic fallback used when learned providers are unavailable or not requested

The provider layer preserves the shape bundle contract, candidate selection semantics, topology / UV / packaging downstream, and Lathe source compatibility.

When a learned provider falls back, the runtime records both the attempted provider and the actual provider that produced the emitted artifact. The same “attempted vs actual” pattern now exists for deterministic backend adapters such as Blender topology and xatlas UV.

The default no-runtime-config build path now stays conservative and smoke-test-friendly by preferring `lathe.provider.shape.reference_conditioned_v1`. To opt into learned auto-routing, pass an explicit runtime config such as `examples/runtime_configs/auto_learned.json`, `examples/runtime_configs/hunyuan_http.json`, or `examples/runtime_configs/vggt_local.json`.

Internally, accepted provider deltas are now traced explicitly as proposal attempts, accepted deltas, rejected deltas, and authoritative-candidate reasons. If a provider does not conform, Lathe keeps the native assembly candidate rather than letting the provider redefine asset semantics.

## Geometry Quality Wedge

The current native wedge is no longer just a semantic blockout compiler.

Lathe now:

- compiles family blueprints into shared hard-surface assemblies
- applies a reusable feature grammar for trims, panel lips, edge breaks, fasteners, vent grilles, brackets, shrouds, recesses, and screen windows
- uses voxel/SDF fusion only as an internal integration/search step, then finalizes the current hero trio into an explicit authoritative mesh record before downstream stages
- searches multiple native candidates offline using fidelity-aware geometry parameters
- runs truthful semantic plus visual-quality certification, including render-level silhouette checks plus evidence-based geometry-integration and surface-authoring metrics
- emits a hero-only bake/surface slice for chest, drone, and console rather than treating surface as metadata passthrough

The result is still an early wedge, not a finished standalone asset compiler. The hero outputs are materially stronger and the certification layer is more honest, but the final geometry still retains some meshed/constructive character and the surface lane is still procedural rather than fully authored.

## Repository layout

```text
lathe/
  __init__.py
  backends.py
  checker.py
  cli.py
  defaults.py
  executor.py
  normalizer.py
  parser.py
  planner.py
  resolver.py
  runtime_config.py
  schema.py
  shape_backend.py
  shape_providers.py
  utils.py
grammar/
  lathe.lark
schema/
  lathe.schema.json
spec/
  lathe-v0.1.md
docs/
  first_backend_stack.md
examples/
  courier_drone.lth
  reconstruct_courier_from_views.lth
  refs/
  runtime_configs/
tests/
  test_backends.py
  test_build.py
  test_lathe.py
  test_roundtrip.py
  test_shape_providers.py
```

## First concrete backend stack

The first wired stack is:

`lathe.stack.hard_surface_game_asset_v1`

It binds:

- `shape -> lathe.shape.intent_mesh_handoff_v1`
- `topology -> lathe.topology.blender_hard_surface_v1`
- `uv -> lathe.uv.xatlas_v1`
- `package -> lathe.package.openusd_gltf_v1`

The first runnable package subset is currently:

- `usd`
- `glb`
- `gltf`
- `obj`

This split is intentional.

- `shape` is probabilistic and now supports learned provider routing
- `topology`, `uv`, and `package` are deterministic
- the compiler can reject unsupported configs before runtime

The topology and UV backends now have explicit adapter behavior:

- `lathe.topology.blender_hard_surface_v1`
  - prefers a real headless Blender subprocess adapter when Blender is available
  - falls back explicitly to the deterministic reference cleanup path when Blender is unavailable or fails a watertightness quality gate
- `lathe.uv.xatlas_v1`
  - prefers a real xatlas adapter when the Python bindings are available
  - falls back explicitly to the deterministic reference box-atlas path when xatlas is unavailable

See `docs/first_backend_stack.md` for the full contract description.
See `docs/local_golden_path.md` for a concrete local-machine walkthrough.

## Current product boundary

Lathe is not “prompt in, cool mesh out.”

It is:

`refs -> intent -> build -> validate -> repair -> package -> publish`

The language is the contract layer between those stages.

## Next build milestones

1. replace the current hero lane's fused iso-surface character with crisper exact solid/feature meshing
2. deepen the hero surface slice from procedural bake outputs into more authored material treatment
3. upgrade the build policy from bounded repair to a fuller reselect/repair/regenerate loop
4. strengthen render-level acceptance further so certification correlates even better with human asset review
5. keep improving cache semantics and incremental invalidation so the heavier native lane stays practical to validate
