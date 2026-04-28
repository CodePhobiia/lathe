# Lathe 0.2.0-rc.1

Lathe is a declarative programming language and compiler/runtime for turning 3D asset intent into certified production-ready asset packages.

This repository is a working **reference compiler scaffold** for Lathe v0.1. The current milestone is a native **parametric hard-surface assembly compiler** under the stable `lathe.shape.intent_mesh_handoff_v1` contract. Learned providers still exist, but they are optional proposal sources inside Lathe’s compiler flow rather than the product center.

## Privacy and security

- Telemetry is **disabled by default** in v0.2.0rc1. No data leaves the machine unless a user explicitly runs `lathe telemetry enable`.
- [Privacy notice](docs/privacy.md) — opt-in payload allowlist, what is never collected, opt-out path.
- [Security policy](SECURITY.md) — vulnerability reporting, response SLA, safe-harbor scope.
- [Terms applicability](docs/terms.md) — Apache-2.0 governs use; no hosted ToS in this pre-release.

## Current release state

- Package/runtime version: `0.2.0rc1` (`pyproject.toml` and `lathe.__version__`).
- Public language/spec contract: v0.1 (`spec/lathe-v0.1.md` remains the compatibility anchor).
- Stability: alpha/pre-release reference compiler scaffold. The repository has substantial tests and CI, but full local pytest can be slow; see the CI and test split below.

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

## Provider Modes And Limits

- Default local mode uses deterministic reference-conditioned providers and
  fallback-capable deterministic topology/UV/package paths so clone-to-build
  smoke tests work without external model services.
- Learned-provider mode is opt-in through runtime config files such as
  `examples/runtime_configs/hunyuan_http.json`; strict mode fails honestly when
  the requested provider is unavailable.
- Offline/fallback mode is a product feature for repeatable docs, tests, and
  CI. It does not claim learned-generation quality, and traces identify the
  actual provider and any degraded state.
- Current limitations: live Hunyuan/VGGT runs require separately managed
  services or source installs, soft-surface support is still narrower than the
  hard-surface hero path, and full release promotion still depends on the
  release checklist under `docs/release/`.

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

The recommended contributor path is the repository-local bootstrap script.
Run it from the repository root; it creates `.venv`, upgrades pip tooling,
installs Lathe editable, and runs `lathe doctor`.

PowerShell on Windows:

```powershell
scripts/bootstrap_local.ps1 -Dev -Export
```

Bash on macOS/Linux, Git Bash, or WSL:

```bash
scripts/bootstrap_local.sh --dev --export
```

That is the one-command bootstrap for a normal development environment. The
base editable install is still available when you intentionally want the
smallest runtime surface:

```bash
pip install -e .
```

After bootstrap, the canonical smoke command is:

```powershell
scripts/lathe_smoke.ps1
```

```bash
bash scripts/lathe_smoke.sh
```

The smoke scripts prefer the repo `.venv` interpreter, run `doctor`, check and
plan `examples/courier_drone.lth`, run a small explicit pytest smoke partition,
and build `courier_drone` into `tmp_lathe_smoke/`. Override the interpreter with
`-Python .\.venv\Scripts\python.exe` in PowerShell or `PYTHON_BIN=/path/to/python`
in bash. Override the output root with `-OutDir tmp_my_smoke` or
`LATHE_SMOKE_OUT=tmp_my_smoke`.

For a narrated product demo that walks through doctor, normalize, check, plan,
materialize, build, and inspect:

```powershell
scripts/demo_core_workflow.ps1
```

```bash
bash scripts/demo_core_workflow.sh
```

Use `-DryRun` or `--dry-run` to preview the exact commands without building.
By default, the demo keeps terminal output concise and writes command outputs
under `tmp_lathe_demo/_demo_workflow/`; add `-VerboseOutput` or
`--verbose-output` when recording a full terminal walkthrough.

Optional extras are opt-in and intentionally small:

| Extra | Installs | Notes |
| --- | --- | --- |
| `dev` | pytest, pytest-cov, Ruff, mypy, pre-commit, Hypothesis, import-linter, release/dev tools | Needed for local tests and contributor checks. |
| `docs` | MkDocs Material and docs plugins | Needed for `mkdocs build --strict`. |
| `export` | scipy | Optional fuller mesh/export toolchain used by some local workflows. |
| `geometry` | scikit-image, manifold3d | Optional geometry-kernel experiments. |
| `hunyuan_http` | no Python packages | Requires a reachable Hunyuan HTTP server configured by runtime config. |
| `vggt` | torch, torchvision | The official `vggt` package is still a manual source install in this repo flow. |
| `xatlas` | xatlas Python bindings | On Windows this usually requires Visual Studio Build Tools with the Desktop C++ workload. |
| `publish` | cryptography, boto3 | Optional publish drivers for signed/local/cloud manifest flows. |

Examples:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,export]"
.\.venv\Scripts\python.exe -m pip install -e ".[docs]"
.\.venv\Scripts\python.exe -m pip install -e ".[vggt]"
.\.venv\Scripts\python.exe -m pip install -e ".[xatlas]"
```

Windows path notes:

- Use `.\.venv\Scripts\python.exe` in PowerShell.
- Use `./.venv/Scripts/python.exe` from Git Bash on Windows.
- POSIX shells on macOS/Linux use `./.venv/bin/python`.
- Quote extras in PowerShell, for example `".[dev,export]"`, so the shell does not treat brackets as a glob.

Generated build artifacts should go under ignored output roots such as `dist/`,
`dist_*`, `tmp_*`, or `warm_*`. `lathe build --out dist` writes one directory
per asset under that root, for example `dist/courier_drone/`. By default Lathe
keeps output inside the repository safety root; set `LATHE_ALLOW_EXTERNAL_OUT=1`
only for trusted local or CI runs that intentionally write elsewhere.

## Test and lint workflow

The default local pytest command runs the normal suite and excludes the dedicated
`slow`, `golden`, `property`, and `fuzz` lanes:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Fast PR checks use a representative core smoke partition and avoid the slowest
lanes. Build-heavy, benchmark, golden, property, fuzz, and example-corpus tests
run in separate CI jobs/workflows so failures stay visible without forcing
every OS/Python leg through the heaviest path. To run the build-heavy lane
locally, use:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -m slow tests/test_build.py
```

To run the benchmark and visual-quality lane locally, use:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -m slow tests/test_benchmarks.py tests/test_visual_quality.py
```

The full slow marker lane is also available, but expect it to run many
end-to-end builds:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -m slow
```

Coverage has one enforced threshold: `65%`, configured in both `.coveragerc`
and `pyproject.toml` and used by the CI coverage lane without command-line
overrides. The ratchet policy is to raise that number only after the default
coverage lane is reliably above the next target; BL-39 tracks the longer-term
`85%` release target.

Ruff is pinned through the dev dependency set. The required lint gate is currently a minimal ratchet for syntax/import-time failures and production `assert` usage while the broader historical lint backlog is paid down:

```powershell
.\.venv\Scripts\ruff.exe check .
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

Shell completions are dependency-free and generated from the live CLI parser:

```text
lathe completions bash > ~/.local/share/bash-completion/completions/lathe
lathe completions zsh > "${fpath[1]}/_lathe"
lathe completions powershell | Out-String | Invoke-Expression
```

Machine-readable diagnostics:

```bash
lathe doctor --json
lathe doctor --runtime-config examples/runtime_configs/hunyuan_http.json --json
lathe build examples/courier_drone.lth courier_drone --out dist --report json
```

User-facing failures use the public CLI error contract documented in
`docs/error_codes.md`. Normal terminal mode emits a short actionable message:

```text
lathe error [lathe.cli.file_not_found]: File not found: examples/missing.lth
  at examples/missing.lth
  Next step: Check the path and rerun the command from the repository root.
```

Build report JSON mode emits a machine-readable failure payload on stdout:

```json
{
  "ok": false,
  "code": "lathe.cli.file_not_found",
  "message": "File not found: examples/missing.lth",
  "severity": "error",
  "next_step": "Check the path and rerun the command from the repository root.",
  "diagnostics": [
    {
      "code": "lathe.cli.file_not_found",
      "severity": "error",
      "message": "File not found: examples/missing.lth",
      "path": "examples/missing.lth"
    }
  ],
  "source_path": "examples/missing.lth"
}
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

- [examples/brassbound_chest.lth](examples/brassbound_chest.lth)
- [examples/industrial_crate.lth](examples/industrial_crate.lth)
- [examples/mechanical_door.lth](examples/mechanical_door.lth)
- [examples/console_terminal.lth](examples/console_terminal.lth)

See [docs/v08_language_reference.md](docs/v08_language_reference.md) for the new declarations and [docs/v08_migration_guide.md](docs/v08_migration_guide.md) for the additive migration path from pre-V0.8 source.

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

- [examples/brassbound_chest.lth](examples/brassbound_chest.lth)
- [examples/industrial_crate.lth](examples/industrial_crate.lth)
- [examples/mechanical_door.lth](examples/mechanical_door.lth)
- [examples/console_terminal.lth](examples/console_terminal.lth)
- [examples/service_cabinet.lth](examples/service_cabinet.lth)
- [examples/control_pedestal.lth](examples/control_pedestal.lth)
- [examples/supply_container.lth](examples/supply_container.lth)

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

- [examples/console_terminal_mobile_adapt.lth](examples/console_terminal_mobile_adapt.lth)
- [examples/service_corridor_wall.lth](examples/service_corridor_wall.lth)
- [examples/reconstruct_courier_from_views.lth](examples/reconstruct_courier_from_views.lth)

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

- [examples/console_terminal_v12_surface.lth](examples/console_terminal_v12_surface.lth)

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
- `scripts/lathe_smoke.ps1` / `scripts/lathe_smoke.sh` for the local regression smoke test

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
