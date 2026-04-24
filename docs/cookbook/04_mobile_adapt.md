# Recipe 04 — Mobile adapt of a hero asset

## Goal

Take an existing hero-quality asset and retarget it for a mobile runtime using `mode = adapt` and an `adapt_policy`. This recipe demonstrates the V1.1 adapt path: you preserve the semantic identity of the asset while trading geometric detail, texture budget, and draw calls.

## Prerequisites

- Lathe v0.1+.
- The example file [`examples/console_terminal_mobile_adapt.lth`](https://github.com/talmerri/lathe/blob/main/examples/console_terminal_mobile_adapt.lth).
- A source mesh at `examples/refs/source_block.obj` (checked in).
- No runtime config required.

## Walkthrough

### Step 1 — read the asset

Open `examples/console_terminal_mobile_adapt.lth`. The interesting bits are at the top:

```lth
profile mobile_runtime {
  defaults {
    build.optimize.lods = 3
    build.surface.resolution = 2048px
    ...
  }
  ensure material_slots(max: 4)
  ensure texture_budget(max: 16mb)
}

contract mobile_shipping_prop uses mobile_runtime {
  ensure runtime_budget(draw_calls: 2, texture_memory: 8mb)
}
```

`mobile_runtime` is a frugal profile: half the LODs, half the texture resolution, a tighter material-slot ceiling. `mobile_shipping_prop` layers a studio contract on top with runtime budget enforcement.

The asset itself points at a source mesh and declares an adapt policy:

```lth
asset console_terminal_mobile: hard_surface_prop from console_terminal_family uses mobile_shipping_prop {
  refs {
    meshes = ["refs/source_block.obj"]
  }

  transfer {
    adapt_policy = mobile_console_policy
    rules = [preserve_console_surface]
  }

  build {
    shape {
      mode = adapt
      adapt_policy = mobile_console_policy
      candidates = 3
      seed = 81
      preserve = [silhouette, part_graph, interfaces]
    }
  }
}
```

`transfer.adapt_policy` and `build.shape.adapt_policy` must point at the same policy — the former makes the policy available to the transfer stage, the latter tells the shape kernel to use it.

### Step 2 — inspect the fit/transfer plan

```bash
python -m lathe.cli fit examples/console_terminal_mobile_adapt.lth console_terminal_mobile
```

This prints the deterministic `FitIR` and `TransferIR`. You should see:

- `fit_ir.source_mesh_uri = refs/source_block.obj`
- `transfer_ir.rules = [preserve_console_surface]`
- `transfer_ir.policy = mobile_console_policy`

If `source_mesh_uri` is empty, the asset's `refs.meshes` block is not resolving — check the path is relative to the `.lth` file.

### Step 3 — check + plan + build

```bash
python -m lathe.cli check examples/console_terminal_mobile_adapt.lth
python -m lathe.cli plan examples/console_terminal_mobile_adapt.lth console_terminal_mobile
python -m lathe.cli build examples/console_terminal_mobile_adapt.lth console_terminal_mobile --out dist
```

The plan shows the adapt-specific stage wiring:

- `plan.build.shape.mode = adapt`
- `plan.build.optimize.texture_budget = 8mb`
- `plan.build.optimize.draw_calls = 2`
- `plan.validate.threshold = 0.82` (relaxed vs hero at 0.86)

### Step 4 — read the build report

```bash
python -m lathe.cli explain dist/console_terminal_mobile
```

Look for the following in `build_report.json`:

- `shape.actual_provider_id` — for `mode = adapt` this is `lathe.provider.shape.adapt_kernel_v1`, deterministic.
- `optimize.draw_calls_actual` — should be `<= 2`.
- `optimize.texture_memory_bytes` — should be `<= 8 MiB`.
- `validate.metrics.runtime_efficiency` — expect a high score; this critic is weighted 0.20 in `mobile_prop`.
- `validate.metrics.semantic_preservation_quality` — the `flow_quality` validator measures how well the adapt preserved the original part graph.

## Output

```
dist/console_terminal_mobile/
  build_report.json
  stages/
    shape/bundle.json
    shape/transfer_ir.json     <- deterministic transfer record
    topology/bundle.json
    uv/bundle.json
    surface/bundle.json
    package/bundle.json
  outputs/
    console_terminal_mobile.usd
    console_terminal_mobile.glb
```

`console_terminal_mobile.glb` weighs noticeably less than the hero variant — that is the whole point.

## Variations

- **Tighten the budget further** — override `build.optimize.texture_budget` to `4mb` in a variant, and drop `build.surface.resolution` to `1024px`. Expect more aggressive bake down-sampling; the `surface_quality` validator will tell you if you have pushed too far.
- **Preserve fewer features** — drop `interfaces` from `preserve`. Adapt becomes more aggressive about geometry reduction; use this only when downstream consumers do not rely on socket/anchor positions.
- **Swap the adapt policy** — author a different `adapt_policy` that biases toward draw-call reduction over texture reduction. The same asset source can target wildly different runtimes by swapping policies.
- **Adapt from a registered asset** — instead of `refs.meshes = [...]`, use `refs.assets = [console_terminal_hero@0.1.0]` to adapt from a previously-published Lathe asset. The `ReuseIR` records which hero build the mobile asset was adapted from.

## Troubleshooting

- `check: error: transfer.adapt_policy and build.shape.adapt_policy differ` — both must point at the same policy symbol.
- `validate: semantic_preservation_quality = 0.4` — the adapt kernel broke the part graph. Add `part_graph` back to `build.shape.preserve`.
- `validate: runtime_efficiency = 0.6` — budgets were not met. Check the `optimize.diagnostics` section in `build_report.json` for the specific over-budget stage (usually `texture_memory` or `draw_calls`).

## See also

- [Spec — V1.1](../Specs/Lathe-V1.1-Spec.md) — `adapt_policy`, `transfer_rule`, `reuse`.
- API: [`lathe.transfer_ir`](../api/transfer_ir.md), [`lathe.fit_ir`](../api/fit_ir.md), [`lathe.reuse_ir`](../api/reuse_ir.md).
- Related: [Recipe 06 — Variant patching](06_variant_patching.md) for a simpler knob-tweaking approach when you do not need full adapt.
- Related: [Recipe 09 — Certification debug](09_certification_debug.md) for decoding `runtime_efficiency` failures.
