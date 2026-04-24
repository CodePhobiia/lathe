# Recipe 05 — Governed surface authoring (V1.2)

## Goal

Author a PBR surface using the V1.2 zone-first pipeline: `surface_backend`, `decal_library`, `mask_program`, and `trim_sheet`. This recipe shows how to drive the Codex ImageGen backend with an explicit fallback, and how the V1.2 surface validators gate the result.

## Prerequisites

- Lathe v0.1+ with V1.2 language support (the scaffold ships with it).
- The example file [`examples/console_terminal_v12_surface.lth`](https://github.com/talmerri/lathe/blob/main/examples/console_terminal_v12_surface.lth).
- Optional: Codex ImageGen bridge directory configured via runtime config. Without it, the V1.2 backend falls back to a native procedural path.

## Walkthrough

### Step 1 — V1.2 surface block

Open `examples/console_terminal_v12_surface.lth`. The whole story lives in the `surface { ... }` block:

```lth
surface {
  program = console_terminal_hero
  backend = codex_imagegen
  policy = hero_zone_first_surface
  authoring.backend = codex_imagegen
  authoring.mode = zone_first
  authoring.generate = [basecolor, wear_mask, decal_mask, detail_overlay]
  authoring.derive = [roughness, orm, normal_detail]
  decal_libraries = [industrial_console_decals]
  mask_programs = [console_wear_masks]
  trim_sheets = [console_trim_sheet]
  patterns = [vent_slats_dense, cargo_fastener_grid]
  palette = industrial_service_console
  material_zones = [painted_steel_body, smoked_glass_screen, rubber_trim_dark]
  materials = [painted_steel_body, smoked_glass_screen, rubber_trim_dark]
  decals = [service_labels, screen_glow]
  bake = [normal, ao, curvature, id]
}
```

Highlights:

- `backend = codex_imagegen` — the imagegen backend is the primary author. If unavailable, Lathe falls back to a native procedural authoring path (see the `surface.fallback_mode` runtime config).
- `authoring.generate` vs `authoring.derive` — explicit split between maps the backend synthesizes and maps Lathe derives deterministically (for example, `orm` from per-zone material properties).
- `decal_libraries`, `mask_programs`, `trim_sheets` — the governed vocabulary the backend draws from. The authoring policy only lets the backend paint using these assets.
- `patterns` — tileable detail patterns referenced by name; declared under `std/patterns/`.
- `material_zones` — the list of canonical zones over which the zone-first authoring mode operates.

### Step 2 — doctor check for the backend

```bash
python -m lathe.cli doctor
```

Look for the `surface_backends` section. `codex_imagegen` reports `available`, `fallback`, or `unavailable`. In `fallback` mode the backend will be tried first and swap to the native procedural path on failure.

### Step 3 — plan the surface

There is a dedicated surface planner command:

```bash
python -m lathe.cli surface-plan examples/console_terminal_v12_surface.lth console_terminal_v12_surface
```

The output includes:

- `surface_control_pack` — which zones, masks, decals, and trims are wired.
- `atlas_assembly_ir` — the deterministic atlas layout the backend must fill.
- `surface_validation_ir` — the metrics the validator will evaluate (zone coverage, decal legality, mask drift).

### Step 4 — build with the default backend

```bash
python -m lathe.cli build examples/console_terminal_v12_surface.lth \
    console_terminal_v12_surface --out dist
```

If the backend is unavailable you will see a `surface.fallback` entry in `build_report.json` naming the native procedural path. The build still certifies.

### Step 5 — build with an explicit Codex handoff

If you want to exercise the real Codex flow, pass the runtime config:

```bash
python -m lathe.cli build examples/console_terminal_v12_surface.lth \
    console_terminal_v12_surface --out dist \
    --codex-imagegen emit
```

`--codex-imagegen emit` writes the generation request to `dist/.../surface/requests/`. Codex picks it up, runs the imagegen job, and drops results in `dist/.../surface/outputs/`. Re-run the build with `--codex-imagegen consume` to finish the bake once the imagegen outputs exist.

### Step 6 — surface-only iteration

When you are iterating only on surface settings, rebuilding the whole pipeline is wasteful. Use:

```bash
python -m lathe.cli surface-build examples/console_terminal_v12_surface.lth \
    console_terminal_v12_surface --out dist
python -m lathe.cli surface-validate examples/console_terminal_v12_surface.lth \
    console_terminal_v12_surface --out dist
python -m lathe.cli surface-repair examples/console_terminal_v12_surface.lth \
    console_terminal_v12_surface --out dist
```

`surface-repair` attempts zone-local repair without rerunning shape/topology/UV.

## Output

```
dist/console_terminal_v12_surface/
  build_report.json
  stages/
    surface/
      bundle.json                      <- atlas + per-zone maps
      surface_control_pack.json
      surface_backend_report.json      <- attempted vs actual backend
      surface_validation_ir.json
      surface_repair_ir.json           <- only if repair ran
      atlas_assembly_ir.json
  outputs/
    console_terminal_v12_surface.usd
    console_terminal_v12_surface.glb   <- with embedded atlas
```

Read `surface_backend_report.json` to see which backend actually ran and which fallbacks fired.

## Variations

- **Change the palette** — swap `palette = industrial_service_console` for another palette under `std/palettes/`. Zone assignments are stable; only the per-zone material values change.
- **Add a decal library** — author a new `.lth` under `std/libraries/` with additional decals, import it, and add its name to `decal_libraries`. Any decal the authoring backend uses must come from an allow-listed library.
- **Tighten mask budgets** — edit the `mask_program` to restrict how much wear a mask may paint (`coverage_ceiling = 0.3`). The `surface_quality` validator emits `mask_budget_exceeded` when the backend overshoots.
- **Force fallback** — pass `--codex-imagegen fallback` to skip the Codex path entirely and take the deterministic procedural route. Useful for CI.

## Troubleshooting

- `surface: error: decal "xyz" is not in an allow-listed library` — add the owning library to `decal_libraries`, or remove the decal.
- `surface_quality: zone_coverage = 0.7` — one or more `material_zones` was not filled. Check `surface_validation_ir.json` for the offending zone id.
- `codex-imagegen: no outputs found` — you used `consume` mode without a prior `emit` populating the request/output directory pair.

## See also

- [Spec — V1.2](../Specs/Lathe-V1.2-Spec.md) — `surface_backend`, `decal_library`, `mask_program`, `trim_sheet`.
- API: [`lathe.surface_ir`](../api/surface_ir.md), [`lathe.texture_control_pack`](../api/texture_control_pack.md), [`lathe.pbr_deriver`](../api/pbr_deriver.md), [`lathe.materials`](../api/materials.md).
- Validator reference: [`surface_quality`](../api/validators/surface_quality.md).
- Related: [Recipe 08 — Runtime config](08_runtime_config.md) for wiring Codex paths.
