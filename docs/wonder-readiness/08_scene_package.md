# Scene Package

The scene package is Lathe's folder contract for storing a Wonder-ready scene
without requiring a product database or app runtime. It bundles the authored
inputs, normalized graph, world memory, deterministic build reports, proxy
render/export artifacts, and validation reports under one package root.

The package manifest contract is `lathe.scene_package_manifest.v1`.

## Package Layout

`lathe scene build <scene_graph.json> --out <out> --mode preview` writes a
folder shaped like:

```text
<out>/<scene_id>/
  source/
  graph/
  build/
  builds/
  cache/
  renders/
  render_passes/
  exports/
  reports/
  scene_package_manifest.json
```

The important runtime files are:

- `graph/scene_graph.json`: checked source Scene Graph copy;
- `graph/scene_graph.normalized.json`: canonical graph used for stable
  comparisons;
- `graph/world_memory.json`: memory seeded from scene facts/events;
- `reports/scene_plan.json`: deterministic build, render, export, and cache
  plan;
- `reports/scene_quality_report.json`: scene validator output;
- `reports/scene_manifest.json`: object, render, export, and package path
  manifest;
- `reports/wonder_report.json`: user-facing quality/readiness summary;
- `scene_package_manifest.json`: package-level index with section-relative
  paths.

## CLI Lifecycle

The core package lifecycle is:

```bash
python -m lathe.cli scene build examples/wonder/alchemist_observatory/scene_graph.json --out dist_scene --mode preview
python -m lathe.cli scene package validate dist_scene/alchemist_observatory
```

`lathe scene package validate` checks the manifest contract, path containment,
expected file existence, section ownership, and scene ID agreement between the
manifest and `graph/scene_graph.json`.

Use `--build-assets` only when the caller wants the existing asset compiler
invoked for generated scene asset sources:

```bash
python -m lathe.cli scene build examples/wonder/alchemist_observatory/scene_graph.json --out dist_scene --mode preview --build-assets
```

The default package path remains deterministic and dependency-light. It writes
proxy build records and proxy artifacts; it does not launch Blender, learned
providers, or Roblox Studio.

## Artifact Truth

The deterministic package can include:

- proxy PNG render passes under `renders/` and `render_passes/`;
- an object contact sheet;
- proxy GLB exports with object metadata sidecars;
- proxy USDA exports when requested;
- optional ID-mask bundles;
- Blender `.blend` exports only when `lathe scene export --target blender` is
  requested and the Blender lane is available.

These artifacts prove package wiring, path safety, object identity, and
manifest validity. They do not prove final visual quality, engine import parity,
Roblox Studio execution, or external viewer validation.

## Related Docs And Tests

For the broader build flow, see
[Scene Build Pipeline](07_scene_build_pipeline.md). Current package coverage is
anchored by:

- `tests/unit/test_scene_package_manifest.py`;
- `tests/unit/test_scene_executor.py`;
- `tests/unit/test_scene_cli.py`;
- `tests/unit/test_scene_assembly.py`.
