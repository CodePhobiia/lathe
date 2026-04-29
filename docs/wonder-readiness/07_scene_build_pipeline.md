# Scene Build Pipeline

Phase 10 now has a deterministic Scene Build Pipeline over existing Scene Graph
JSON, including proxy render, GLB export, and USD layout artifact support.

`lathe.scene.executor.build_scene_preview(scene_graph_path, out_dir, mode="preview")` loads and checks the Scene Graph,
runs `plan_scene`, derives World Memory from `create_world_memory`, assembles
scene IR, writes deterministic proxy PNG renders, writes a deterministic proxy
GLB export, runs the scene validators, and writes a folder-based Scene Package
under `<out_dir>/<scene_id>/`. The executor also accepts
`runtime_config_path`, `deterministic`, `allow_fallback`, `strict`, and the
opt-in `build_assets` keyword for the current offline/proxy runtime policy.

The CLI entry point is:

```bash
python -m lathe.cli scene build examples/wonder/alchemist_observatory/scene_graph.json --out dist_scene --mode preview
python -m lathe.cli scene build examples/wonder/alchemist_observatory/scene_graph.json --out dist_scene_with_asset_builds --mode preview --build-assets
```

Before a full scene build, `lathe scene materialize` can lower a checked Scene
Graph into generated, checkable Lathe asset source files:

```bash
python -m lathe.cli scene materialize examples/wonder/alchemist_observatory/scene_graph.json --out generated_scene --mode preview
python -m lathe.cli scene materialize examples/wonder/alchemist_observatory/scene_graph.json --out generated_scene_with_builds --mode preview --build-assets
python -m lathe.cli wonder validate-scene-materialization-manifest generated_scene/scene_materialization_manifest.json
```

The materializer writes `scene_graph.json`, `scene_plan.json`,
`scene_materialization_manifest.json`, and one generated asset source directory
per planned asset task under `assets/<asset_name>/`. Each generated `.lth`
asset source includes provenance comments, scene material declarations, stable
source/object metadata, generated asset naming based on the Scene Plan cache
key, and a companion `metadata.json` with checker and planner results. Repeated
scene instances that share a source, variant, and asset-level overrides are
lowered into one instance-friendly source with multiple `object_ids` recorded
in the manifest.

`--build-assets` is intentionally opt-in. When present, the materializer invokes
the existing Lathe asset build pipeline for each generated source and records a
per-source `build` result under `builds/<asset_name>/`. Build failures are not
hidden: the manifest is still written for inspection, `builds_failed` is
incremented, build diagnostics are copied into the manifest, and the CLI exits
nonzero. This proves the build integration path without claiming that every
generated scene asset is already certifiable by the final asset validator.

`lathe scene build --build-assets` uses that same materialization lane inside
the Scene Package before writing the final package manifest. On success, the
package records `source/materialized_assets/scene_materialization_manifest.json`
as a source artifact, `reports/build_report.json` includes an
`asset_materialization` summary, `build_options.runtime.asset_materialization`
is `lathe.scene.materialize.v1`, and `build_options.runtime.asset_build` is
`lathe.asset_build_pipeline.v1`. `build_options.fallbacks.deterministic_proxy_assets`
remains `true` because scene assembly, rendering, and export still consume
proxy geometry until real built assets are promoted into that path. On generated
asset build failure, the scene build exits nonzero with `SB1014` diagnostics and
leaves the materialization manifest in the package for repair. If
materialization itself fails before returning a manifest, the build exits with
`SB1015`. This proves asset build orchestration, not final scene visual parity.

Scene planning can also compare a branch plan against a previously emitted base
plan and report which asset builds are safe to reuse by cache key:

```bash
python -m lathe.cli scene plan examples/wonder/alchemist_observatory/scene_graph.json --mode preview --out base_scene_plan.json
python -m lathe.cli scene plan examples/wonder/alchemist_observatory/scene_graph.json --mode preview --reuse-from-plan base_scene_plan.json --out branch_scene_plan.json
```

The branch reuse report is embedded under `branch_reuse` in the Scene Plan. It
records reusable asset tasks, new asset tasks, skipped non-shareable tasks,
base-only tasks, a reuse ratio, and structured diagnostics such as `SP3101`
when a preview plan is compared with a final-mode plan.

The deterministic render entry point can render either one camera or every
authored camera plus the generated topdown debug camera:

```bash
python -m lathe.cli scene render examples/wonder/alchemist_observatory/scene_graph.json --out dist_renders --camera camera_reveal
python -m lathe.cli scene render examples/wonder/alchemist_observatory/scene_graph.json --out dist_renders --all-cameras
```

Use `--timeout-seconds <seconds>` when a caller needs the deterministic proxy
renderer to fail with structured `SR1004` diagnostics instead of running past a
local budget.

The deterministic export entry point supports proxy GLB, proxy USDA, and a
Blender-backed `.blend` export target:

```bash
python -m lathe.cli scene export examples/wonder/alchemist_observatory/scene_graph.json --out dist_exports --target glb
python -m lathe.cli scene export examples/wonder/alchemist_observatory/scene_graph.json --out dist_exports --target usd
python -m lathe.cli scene export examples/wonder/alchemist_observatory/scene_graph.json --out dist_exports --target blender
```

The USD target writes `exports/<scene_id>.usda` plus
`exports/<scene_id>.usd_object_index.json`. The USDA file uses a stable
`/LatheScene` default prim with `/LatheScene/Regions` and
`/LatheScene/Objects` roots. Every object prim carries `lathe_scene_id`,
`lathe_object_id`, `lathe_material_id`, and `lathe_render_index` custom data.
The sidecar records the `lathe.proxy_usd_layout.v1` convention, region paths,
object paths, material indices, and identity validation results.

Use `--include-collision-proxies` with `lathe scene export` to include
deterministic simple-box collision proxy nodes in supported proxy GLB and USDA
exports. The object-index sidecar records the collision node names, object IDs,
positions, extents, and `simple_box_proxy` policy.

Use `--include-id-mask-bundle` with `lathe scene export` to include export-side
object ID mask PNGs and object-index sidecars under `exports/id_masks/`. The
bundle manifest records the stable `lathe.scene_id_mask_export_bundle.v1`
contract and the `rgb_uint24_render_index` encoding used by each mask.

The Blender target writes `exports/<scene_id>.blend` through the existing
sandboxed Blender runner. It first creates a deterministic proxy GLB
intermediate, passes `reports/blender_export_metadata.json` into
`scripts/blender_export_blend.py`, and expects
`reports/blender_export_summary.json` back from Blender. That metadata tells
the helper to create stable scene/region collections, attach object/region/
material/provenance IDs as Blender custom properties, and recreate declared
camera and light records. The exporter fails with structured diagnostics when
Blender is explicitly requested but unavailable or when object identity is not
preserved.

`--mode` accepts `preview` or `final`. The current implementation is still
offline in both modes: no Blender process or learned provider is launched. The
mode is passed to the deterministic Scene Plan so budgets, render passes, and
task metadata match the requested plan mode.

Additional build flags are supported where the deterministic offline/proxy
executor can truthfully apply or record them:

- `--runtime-config <path>` loads a runtime config JSON through the shared
  runtime-config loader. The path must point to a `.json` file and must not
  contain parent traversal. The package records only whether a config was
  provided, the display path, and the effective shape-provider policy.
- `--deterministic` records the requested deterministic policy in every emitted
  build-options block. The current scene build executor is deterministic even
  when the flag is omitted.
- `--allow-fallback` records explicit fallback permission and applies it to the
  effective shape runtime policy for future provider-backed scene work. The
  current scene build does not execute provider calls.
- `--strict` fails on scene validation warnings/errors, Scene Plan diagnostics,
  and generated-fallback source diagnostics where the current contracts expose
  them. It does not claim Blender, learned-provider, Roblox, or external-viewer
  execution.
- `--build-assets` materializes generated Scene Plan asset sources inside the
  package and invokes the existing Lathe asset build pipeline. Failed generated
  asset builds stop the scene build with structured diagnostics rather than
  being downgraded to proxy success.

The resolved policy is emitted as `build_options` in the CLI JSON payload,
`reports/scene_plan.json`, `reports/build_report.json`,
`reports/scene_manifest.json`, `reports/wonder_report.json`,
`scene_package_manifest.json`, and the proxy build manifests. Runtime config
contents are not copied into those reports.

The package currently writes:

- `graph/scene_graph.json`: checked JSON copy of the source Scene Graph.
- `graph/scene_graph.normalized.json`: canonical JSON-normalized Scene Graph
  used for stable identity and equality checks.
- `graph/world_memory.json`: World Memory seeded with Scene Graph `memory_events` when present.
- `builds/preview/` and `builds/final/`: reserved build-mode roots for
  scene-level build metadata and future asset reuse outputs.
- `render_passes/depth/`, `render_passes/normal/`,
  `render_passes/object_id/`, `render_passes/material_id/`, and
  `render_passes/wireframe/`: reserved pass-specific render roots.
- `cache/`: reserved package-local cache root for per-asset reuse metadata.
- `reports/scene_plan.json`: deterministic Scene Plan.
- `reports/build_report.json`: scene-level build report with artifact paths,
  per-asset proxy build reports, package-local cache reuse summary, and
  provider/fallback trace.
- `reports/validation_report.json`: compatibility validation report alias for
  the schema-backed scene quality report.
- `reports/scene_quality_report.json`: output from `run_scene_validators`.
- `reports/wonder_report.json`: human-readable JSON summary of what was packaged and which final-runtime gates remain deferred.
- `reports/scene_manifest.json`: scene ID, object IDs, package-relative paths, planned records, built proxy render/export records, and proxy paths.
- `source/` and materializer output roots can hold generated asset `.lth`
  sources and materialization manifests before those assets are promoted into a
  scene package.
- `source/materialized_assets/scene_materialization_manifest.json`: opt-in
  materialization/build summary when `lathe scene build --build-assets` is
  used.
- `reports/scene_render_artifacts.json`: proxy render artifact report.
- `reports/scene_export_artifacts.json`: proxy export artifact report.
- `scene_package_manifest.json`: folder manifest with source, graph, build, and report entries.
- `build/*proxy_manifest.json`: explicit planned proxy records for scene assembly and asset build tasks.
- `cache/asset_reuse_report.json`: package-local cache reuse ledger for
  per-asset proxy build records.
- `build/scene_assembly_ir.json`: deterministic Scene Assembly IR.
- `build/object_selection_payloads.json`: object selection payloads used by the proxy render/export path.
- `renders/<camera>/<pass>.png`: deterministic proxy PNG renders for planned cameras, including topdown debug evidence.
- `renders/camera_object_contact_sheet/beauty.png`: deterministic object contact
  sheet with matching object/material index sidecars for scene review and
  selection.
- `exports/<declared-name>.glb`: deterministic proxy GLB export with object ID metadata evidence when the Scene Graph declares a GLB export task.
- `exports/<scene_id>.usda`: deterministic proxy USD layout export when requested through `lathe scene export --target usd`.
- `exports/<scene_id>.usd_object_index.json`: USD object/region/material index and layout-convention sidecar.
- `exports/<scene_id>.blend`: Blender-backed export when requested through `lathe scene export --target blender` and Blender is available.
- `exports/id_masks/<camera>/object_id.png`: optional object ID mask export bundle when requested through `lathe scene export --include-id-mask-bundle`.
- `exports/id_masks/id_mask_bundle.json`: optional ID mask bundle manifest.
- `reports/blender_export_metadata.json`: metadata passed to the Blender helper for collections, cameras, lights, materials, provenance, and custom properties.
- `reports/blender_export_summary.json`: summary emitted by the Blender helper for identity validation.

`lathe scene build` still does not launch Blender or a mesh provider. It runs
the asset compiler only when `--build-assets` is requested explicitly, and the
scene render/export artifacts remain proxy outputs. `lathe scene export
--target blender` launches Blender only when that target is requested
explicitly. The proxy render, GLB, and USDA outputs prove package wiring,
manifest validation, object identity, layout convention, and artifact
existence, but not final visual quality or engine import parity.

## Proxy Artifact Test Contract

The tests for this layer assert:

- `scene_package_manifest.json` lists built PNG render entries under
  `renders/`, with `camera_id`, `passes`, `status: built`, and package-relative
  `.png` paths.
- `scene_package_manifest.json` lists at least the built GLB export under
  `exports/`, with `target: glb`, `status: built`, and a package-relative
  `.glb` path under `exports/`.
- `lathe scene export --target usd` writes a package-relative `.usda` file
  under `exports/`, a USD object-index sidecar, and identity evidence for every
  scene object ID.
- `lathe scene export --include-collision-proxies` records deterministic
  simple-box collision proxy nodes and matching sidecar records for supported
  proxy exports.
- `lathe scene export --include-id-mask-bundle` records export-side object ID
  masks, object index sidecars, and a bundle manifest for every authored camera
  plus generated topdown debug camera.
- `lathe scene export --target blender` routes through `probe_blender` and
  `run_blender_sandboxed`, writes a `.blend` plus summary when Blender is
  available, and validates object IDs from the Blender summary.
- `reports/scene_manifest.json` keeps planned task records and separately
  records built proxy render/export artifacts.
- `reports/scene_render_artifacts.json` records a `contact_sheets` array when
  the deterministic object contact sheet is emitted.
- `scene package validate` should continue to require all manifest render/export
  paths to stay inside the package and exist on disk.
- Package validation also checks the manifest `scene_id` against the referenced
  `graph/scene_graph.json` when that Scene Graph validates, so a package cannot
  silently point at a different scene.
- `tests/unit/test_scene_executor.py` and `tests/unit/test_scene_cli.py`
  validate PNG/GLB signatures and manifest/report alignment.

The build fails with machine-readable diagnostics when the Scene Graph is schema/semantically invalid, scene validation
has errors, World Memory cannot be derived, or package/output paths are unsafe.
Runtime flag diagnostics include `SB1009` for unsafe runtime-config paths,
`SB1010` for runtime-config load/parse failures, `SB1011` for strict validation
diagnostics, and `SB1012` for strict generated-fallback scene planning.
Asset build artifact diagnostics include `SB1013` when a planned per-asset
proxy build record is missing after the package write step, and `SB1014` when
`lathe scene build --build-assets` materializes generated asset sources but one
or more generated asset builds fail. `SB1015` reports materialization failures
that occur before the build-results manifest can be completed.
Render diagnostics include `SR1004` when the proxy render timeout is exceeded.
Blender export diagnostics include `SX1201` when Blender is unavailable,
`SX1202` when the sandboxed Blender run fails, and `SX1204` when exported
object identity is not preserved.
