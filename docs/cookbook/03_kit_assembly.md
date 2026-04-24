# Recipe 03 — Kit assembly from a library

## Goal

Build a modular environment module (`service_corridor_wall`) by snapping pre-declared components from a `library` and `kit`. This recipe demonstrates the V1.1 `library`, `kit`, `assembly_policy`, and the `mode = assemble` shape flow.

## Prerequisites

- Lathe v0.1+.
- Three `.lth` files:
    - `std/libraries/industrial_assets.lth` — the library of families, components, and materials.
    - `std/kits/industrial_wall_kit.lth` — the snap kit bound to the `sci_fi_wall_panel_family`.
    - `examples/service_corridor_wall.lth` — the asset that assembles them.

No runtime config is needed — `mode = assemble` is deterministic and does not call any learned provider.

## Walkthrough

### Step 1 — the library

Open `std/libraries/industrial_assets.lth`. A library is a named collection of families, components, materials, and patterns that downstream assets and kits can reference by symbol:

```lth
library industrial_hardsurface_library {
  families = [sci_fi_wall_panel_family, console_terminal_family, mechanical_door_family]
  components = [
    wall_panel_shell, wall_screen_bezel, wall_frame_panel,
    wall_vent_l, wall_vent_r,
    console_body_shell, console_bezel, console_screen, console_panel_face, console_stand,
  ]
  materials = [painted_steel_body, smoked_glass_screen, rubber_trim_dark]
  patterns = [vent_slats_dense, cargo_fastener_grid]
}
```

Libraries are stateless catalogs. They do not imply any geometry — they are the vocabulary a kit or asset draws from.

### Step 2 — the kit

Open `std/kits/industrial_wall_kit.lth`. A `kit` binds a family to an ordered module list plus snap rules:

```lth
kit industrial_wall_kit {
  family = sci_fi_wall_panel_family
  modules = [
    wall_panel_shell, wall_screen_bezel, wall_frame_panel,
    wall_vent_l, wall_vent_r,
    wall_mount_top, wall_mount_bottom,
  ]
  snap_grid = 10cm
  clearance = 1cm
  allowed_joins = [panel_to_panel, panel_to_frame, panel_to_vent]
}
```

`snap_grid` and `clearance` define the lattice the assembly kernel snaps to. `allowed_joins` enumerates which join classes the validator will accept. Joins outside this list cause `join_legality` failures during certification.

### Step 3 — the asset

Open `examples/service_corridor_wall.lth`. The asset consumes both the library (via module imports) and the kit (via `from industrial_wall_kit`):

```lth
asset service_corridor_wall: env_module from industrial_wall_kit uses shipping_module {
  ...
  constraints {
    assembly_policy = industrial_wall_policy
  }

  assembly_rules {
    repeat_modules = [wall_panel_shell, wall_frame_panel]
    inserts = [wall_screen_bezel]
    mounts = [wall_vent_l, wall_vent_r, wall_mount_top, wall_mount_bottom]
  }

  build {
    shape {
      mode = assemble
      assembly_policy = industrial_wall_policy
      candidates = 3
      seed = 91
      symmetry = x
      preserve = [silhouette, part_graph, symmetry, interfaces]
    }
  }
}
```

Key V1.1 fields:

- `from industrial_wall_kit` — binds the asset to the kit (shape stage uses the kit's `modules` and `snap_grid`).
- `constraints.assembly_policy` — the high-level policy governing repeat counts, insert density, and mount placement.
- `assembly_rules` — asset-specific overrides on top of the policy: which modules repeat, which are single-insert, which are mounts.
- `build.shape.mode = assemble` — selects the deterministic assembly kernel over the probabilistic generate path.

### Step 4 — check + plan + build

```bash
python -m lathe.cli check examples/service_corridor_wall.lth
python -m lathe.cli plan examples/service_corridor_wall.lth service_corridor_wall
python -m lathe.cli build examples/service_corridor_wall.lth service_corridor_wall --out dist
```

Because `mode = assemble` is fully deterministic, the shape provider mux bypasses the learned-provider slots and uses the assembly kernel directly. In `build_report.json` you will see:

```json
{
  "shape": {
    "selected_provider_id": "lathe.provider.shape.assembly_kernel_v1",
    "actual_provider_id": "lathe.provider.shape.assembly_kernel_v1"
  }
}
```

### Step 5 — inspect the kit IR

```bash
python -m lathe.cli inspect dist/service_corridor_wall
```

Look for the `kit_ir` section in the output — it reports which modules were placed, at what grid positions, and the join classes used. Every placement has a `snap_grid_cell` entry that you can use to debug misaligned walls.

## Output

The packaged asset is a tiled wall module ready for a level designer. Expected tree:

```
dist/service_corridor_wall/
  build_report.json
  stages/
    shape/bundle.json                 <- assembly output with module placements
    shape/kit_ir.json                 <- deterministic kit IR snapshot
    topology/bundle.json
    uv/bundle.json
    package/bundle.json
  outputs/
    service_corridor_wall.usd
    service_corridor_wall.glb
```

## Variations

- **Swap the kit** — replace `from industrial_wall_kit` with a custom kit you author in `std/kits/`. Keep the snap grid consistent or the assembly kernel will emit `snap_mismatch` diagnostics.
- **Tighten `clearance`** — raise `kit.clearance` from `1cm` to `5cm` to introduce visible gutters between modules. The assembly kernel will pad placements accordingly.
- **Add a new join class** — extend `allowed_joins` with `panel_to_mount` and author a new family adjacency rule. Any join that lands outside `allowed_joins` is rejected at `validate.score` time with `join_legality = 0.0`.
- **Author your own library** — copy `std/libraries/industrial_assets.lth`, change the list of `components`, and import it from your asset. Libraries compose additively with `uses`.

## Troubleshooting

- `check: error: unknown family sci_fi_wall_panel_family` — ensure `import std.families.sci_fi_wall_panel` is in your asset file. Kits cannot resolve the family on behalf of the asset.
- `validate: join_legality = 0.2` — your asset authored a join that is not listed in `kit.allowed_joins`. Either add the join class to the kit or change the asset.
- `validate: repeat_count mismatch` — the `repeat_modules` count in `assembly_rules` is inconsistent with the policy. Check `std/policies/v11_asset_ops.lth` for the policy definition.

## See also

- [Architecture — Shape stage](../architecture/shape_stage.md) — `assembly_kernel` placement in the flow.
- [Spec — V1.1](../Specs/Lathe-V1.1-Spec.md) — `library`, `kit`, `assembly_policy`, `assembly_rules`.
- API: [`lathe.kit_ir`](../api/kit_ir.md), [`lathe.assembly_kernel`](../api/assembly_kernel.md).
- Related: [Recipe 06 — Variant patching](06_variant_patching.md) for swapping modules via variants.
