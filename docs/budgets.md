# Runtime budgets (STAGE-7/8)

The `optimize` stage evaluates three runtime budgets after LOD and collision
proxies are emitted and writes the result to
`stages/optimize/budget_report.json`. The same report is embedded under
`budget_report` in the optimize bundle and propagated to the selector
manifest as the optional `budgets` block.

Budgets are **advisory by default** — only severe overages (exceed the
budget by more than 25 %) escalate to `severity=error`. Smaller overages
register as `severity=warning` so triage is visible without blocking the
build. Category-level `status` values are:

| status    | meaning                                                           |
|-----------|-------------------------------------------------------------------|
| `pass`    | under budget                                                      |
| `warning` | over budget but within 25 %                                       |
| `error`   | over budget by more than 25 %                                     |
| `skipped` | upstream stage did not expose data to evaluate (no crash emitted) |

`overall_status` is the worst status across the three categories (ignoring
`skipped` when at least one category ran).

## Catalog

### Texture memory (STAGE-7, diagnostic `L6301`)

What it measures: the estimated GPU memory footprint of the baked surface
bundle, in bytes, once textures are uploaded to a runtime (Godot, Unreal,
engine-agnostic via KTX2).

How it is estimated:

1. If the surface bundle exposes an explicit `materials: [{id, maps: [{W, H,
   format}]}]` list, each map's bytes are computed as `W × H × bpp / 8` with
   format-specific bpp.
2. Otherwise a heuristic path is used: `resolution² × len(maps) × bpp ×
   distinct_material_count`, where `resolution` is read from
   `surface_manifest.resolution.value`, `maps` is the channel list
   (e.g. `basecolor`, `normal`, `orm`, `emissive`), and the default format
   is `ktx2` (~1 byte/pixel).

Budget resolution: `build.optimize.texture_memory_budget_mb` if set, else
the legacy `build.optimize.texture_budget` (already in MiB via the `mb`
suffix), else the default of **64 MiB**.

Recommended budgets:

| target       | recommended |
|--------------|------------:|
| mobile       |        8 MB |
| desktop game |       32 MB |
| hero/cinema  |       64 MB |

### Material count (STAGE-8, diagnostic `L6302`)

What it measures: the number of distinct materials the surface stage
produced. Derived from (in order): `material_zones[*].material`,
`surface_manifest.semantic_materials`, or, if neither is present, an
explicit `materials` list.

Budget resolution: `build.optimize.material_count_budget` if set, else the
default of **16**.

Recommended budgets: 4 (mobile), 8 (desktop), 16 (hero). Going higher is
usually a sign the asset should be merged via a trim sheet or atlas.

### Draw calls (STAGE-8, diagnostic `L6303`)

What it measures: an estimate of GPU draw calls at render time, counted as
`materials × LODs`. One call per material per LOD is the worst-case cost
when no batching is possible; engine-specific batching usually reduces the
real call count but the estimate is a useful ceiling.

Budget resolution: `build.optimize.draw_call_budget` if set, else the
default of **64** (hero-asset default; mobile targets should override).

Recommended budgets: 16 (mobile), 32 (desktop), 64 (hero).

## Diagnostic fix recipes

| code    | name                        | typical fix                                                   |
|---------|-----------------------------|---------------------------------------------------------------|
| `L6301` | `texture_memory_over_budget`| lower `build.surface.resolution`, atlas maps, or drop channels |
| `L6302` | `material_count_over_budget`| merge zones via a shared trim sheet or palette atlas          |
| `L6303` | `draw_call_over_budget`     | reduce material count, reduce LOD count, or enable atlas      |

All three diagnostics carry a `details` block with the raw numbers
(`budget_bytes`/`budget`, `estimated_bytes`/`estimated`, per-material
breakdown) so downstream repair agents can propose scoped fixes without
re-running evaluation.

## Consumers

- `lathe/core/stages/optimize.py` runs the evaluator after LOD/collision,
  writes `stages/optimize/budget_report.json`, and appends any diagnostics
  to the optimize bundle.
- `lathe/selector_manifest.py::build_selector_manifest` embeds the report
  under `budgets` when present (schema:
  `schema/lathe.selector.schema.json`).
- The reports stage surfaces the category statuses in both the HTML and
  terminal summaries (`lathe/reports/*`).
