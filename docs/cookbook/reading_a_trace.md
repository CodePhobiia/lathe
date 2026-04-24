# Reading a trace

Every Lathe build emits a `build_report.json` plus per-stage bundles under `dist/<asset>/stages/`. This page is the field-level guide to reading them — what each top-level key means, how attempted-vs-actual provider records work, and how to inspect the V1.1 IRs (`ReferenceIR`, `FitIR`, `TransferIR`, `KitIR`, `ReuseIR`).

## Top-level `build_report.json`

```json
{
  "status": "certified",
  "asset": "courier_drone",
  "source": "examples/courier_drone.lth",
  "runtime_config": "examples/runtime_configs/hunyuan_http.json",
  "selected_stack": "lathe.stack.hard_surface_game_asset_v1",

  "shape":    { ... },
  "topology": { ... },
  "uv":       { ... },
  "surface":  { ... },
  "optimize": { ... },
  "validate": { ... },
  "package":  { ... },
  "publish":  { ... }
}
```

Fields:

| Key | Meaning |
|---|---|
| `status` | `certified` (passed), `rejected` (failed certification), `error` (hard failure mid-pipeline). |
| `asset` | Asset or variant name that was built. |
| `source` | Path to the `.lth` that authored the build. |
| `runtime_config` | Path to the config used, if any. `null` when none was passed. |
| `selected_stack` | Which backend stack Lathe picked (e.g. `hard_surface_game_asset_v1`). |
| `<stage>` | Per-stage report. See below. |

## Attempted-vs-actual

The shape stage always records the two provider ids:

```json
{
  "shape": {
    "selected_provider_id": "lathe.provider.shape.hunyuan2_1_http_v1",
    "actual_provider_id":   "lathe.provider.shape.hunyuan2_1_http_v1",
    "selected_provider_version": "1.0.0",
    "actual_provider_version":   "1.0.0",
    "selected_reason":    "runtime_config.shape.provider",
    "fallback_reason":    null,
    "external_job_id":    "hunyuan-20260423-abc",
    "consumed_refs":      ["refs/courier_front.png", "refs/courier_side.png"],
    "seed":               42
  }
}
```

Reading the pairing:

- `selected` == `actual` — the intended provider ran. This is the clean case.
- `selected` != `actual` — the intended provider was unavailable or errored and a fallback ran. `fallback_reason` explains why (e.g. `"provider_probe_failed: connection refused"`, `"blender_not_on_path"`, `"xatlas_import_error"`).
- `actual == null` with `strict: true` — the intended provider failed and strict mode aborted the build.

The same pattern applies to `topology.actual_backend_id` (Blender adapter) and `uv.actual_backend_id` (xatlas adapter). For deterministic stages the attempted side is usually the stack's declared backend; `actual` swaps in the reference fallback when the adapter is unavailable.

Quick commands to surface this:

```bash
python -m lathe.cli explain dist/courier_drone          # human summary
python -m lathe.cli probe-providers                      # preflight, not post-build
```

## Per-stage bundles

Each stage writes a bundle file under `dist/<asset>/stages/<stage>/bundle.json`. `build_report.json` references them by path. Bundle schemas are specified by the stage contract in `lathe/backends.py`.

### `stages/shape/bundle.json`

```json
{
  "candidates": [
    {
      "candidate_id": "c01",
      "mesh_uri": "stages/shape/c01.obj",
      "units": "m",
      "frame": "y_up_right_handed",
      "part_labels": {"body": [...], "rotor_fl": [...]},
      "coarse_material_slots": ["anodized_aluminum_body", "carbon_fiber_trim"],
      "preview_images": ["stages/shape/c01_preview.png"]
    }
  ],
  "provenance": {
    "backend_id":    "lathe.shape.intent_mesh_handoff_v1",
    "backend_version": "2.0.0",
    "seed":            42,
    "external_job_id": "hunyuan-20260423-abc",
    "consumed_refs":   ["refs/courier_front.png"]
  },
  "conditioning_report": { ... }
}
```

Every candidate has at least `mesh_uri`, `units`, `frame`, and `candidate_id` (the contract guarantee). `provenance.seed` is the deterministic seed fed to the provider; the same seed + same refs + same provider deterministically reproduce the candidate.

### `stages/topology/bundle.json`

```json
{
  "mesh_uri": "stages/topology/clean.obj",
  "mesh_stats": {
    "vertex_count": 5821,
    "triangle_count": 11642,
    "quad_count": 5000,
    "ngons": 0
  },
  "normals": "per_face",
  "part_groups": [{"name": "body", "face_range": [0, 4000]}],
  "provenance": {"backend_id": "lathe.topology.blender_hard_surface_v1"}
}
```

`mesh_stats.ngons > 0` triggers `TOPO_NGON_FOUND` diagnostics (see [Recipe 09](09_certification_debug.md)).

### `stages/uv/bundle.json`

```json
{
  "mesh_uri": "stages/uv/unwrapped.obj",
  "uv_sets": [
    {"name": "base",     "coverage": 0.94, "chart_count": 48},
    {"name": "lightmap", "coverage": 0.91, "chart_count": 40}
  ],
  "packing_report": {"chart_count": 48, "wasted_fraction": 0.06},
  "provenance": {"backend_id": "lathe.uv.xatlas_v1"}
}
```

## V1.1 IR fields

When an asset uses V1.1 constructs, the shape stage also writes one or more IR snapshots to `stages/shape/`:

### `reference_ir.json` (from `reference_set`)

```json
{
  "reference_set_id": "courier_views",
  "images":   ["refs/courier_front.png", "refs/courier_side.png"],
  "meshes":   [],
  "assets":   [],
  "calibrated": false,
  "camera_guess": { "front": {...}, "side": {...} }
}
```

### `fit_ir.json` (from `fit_profile`)

```json
{
  "fit_profile_id": "courier_fit_default",
  "bbox_l2_threshold":    0.08,
  "silhouette_iou_min":   0.72,
  "part_graph_strictness": "strict",
  "source_mesh_uri": "refs/source_block.obj"
}
```

### `transfer_ir.json` (from `adapt_policy` / `transfer.rules`)

```json
{
  "policy_id": "mobile_console_policy",
  "rules":     ["preserve_console_surface"],
  "preserve":  ["silhouette", "part_graph", "interfaces"],
  "source_asset": null
}
```

### `kit_ir.json` (from `mode = assemble`)

```json
{
  "kit_id":     "industrial_wall_kit",
  "family":     "sci_fi_wall_panel_family",
  "snap_grid":  "10cm",
  "placements": [
    {"module": "wall_panel_shell", "cell": [0,0], "rotation_deg": 0}
  ],
  "joins":      [{"a": "wall_panel_shell", "b": "wall_frame_panel", "class": "panel_to_frame"}]
}
```

### `reuse_ir.json` (from `reuse` block referencing a prior asset)

```json
{
  "source_asset": "console_terminal_hero",
  "source_version": "0.1.0",
  "reuse_policy": "material_only",
  "reused_artifacts": ["stages/surface/bundle.json"]
}
```

## Validate block

```json
{
  "validate": {
    "score":     0.88,
    "threshold": 0.95,
    "status":    "rejected",
    "critic":    "hero_prop",
    "per_metric": {
      "prompt_match": 0.85,
      "silhouette_readability": 0.93,
      "topology_quality": 0.80
    },
    "per_validator": {
      "semantic_quality": 0.82,
      "visual_quality":   0.90,
      "flow_quality":     0.88,
      "surface_quality":  0.93,
      "silhouette":       0.91
    },
    "diagnostics": [
      {
        "code":     "TOPO_NGON_FOUND",
        "validator":"semantic_quality",
        "severity": "warn",
        "message":  "3 ngons detected in retopo output",
        "location": "stages/topology/bundle.json#/mesh_stats/ngons"
      }
    ],
    "repair": {
      "rounds_attempted": 4,
      "rounds_allowed":   4,
      "actions_taken":    ["retopo_auto", "reduce_tris", "repack_uvs", "rebake_maps"]
    }
  }
}
```

See [Recipe 09 — Certification debug](09_certification_debug.md) for the triage workflow.

## Package + publish

```json
{
  "package": {
    "outputs":  [
      {"format": "usd", "uri": "outputs/courier_drone.usd"},
      {"format": "glb", "uri": "outputs/courier_drone.glb"}
    ],
    "manifest_path":         "outputs/manifest.json",
    "normalized_source_path": "normalized.json",
    "trace_path":             "build_report.json"
  },
  "publish": {
    "registry":  "props/drones/courier_drone",
    "version":   "0.1.0",
    "channel":   "dev",
    "status":    "dry_run"
  }
}
```

The `publish` runner is still a scaffold — builds record the intended registry/version pair but do not push anywhere.

## CLI cheat sheet

```bash
python -m lathe.cli explain        dist/<asset>   # human-readable summary
python -m lathe.cli inspect        dist/<asset>   # V1.3.1 evidence report
python -m lathe.cli explain-fit    dist/<asset>   # fit/reference/transfer IRs
python -m lathe.cli inspect-blend  dist/<asset>   # retained .blend summary
python -m lathe.cli render-fixture dist/<asset>   # V1.3 render-eval evidence
python -m lathe.cli bake-audit     dist/<asset>   # V1.3 bake evidence + missing bakes
```

## See also

- [Runtime config schema](runtime_config_schema.md).
- [Recipe 08 — Runtime config](08_runtime_config.md).
- API: [`lathe.executor`](../api/executor.md), [`lathe.shape_providers`](../api/shape_providers.md), [`lathe.fit_ir`](../api/fit_ir.md), [`lathe.transfer_ir`](../api/transfer_ir.md), [`lathe.kit_ir`](../api/kit_ir.md), [`lathe.reuse_ir`](../api/reuse_ir.md), [`lathe.reference_ir`](../api/reference_ir.md).
