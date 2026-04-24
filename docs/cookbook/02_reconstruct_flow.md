# Recipe 02 — Reconstruct flow with reference images

## Goal

Build the same courier-drone prop from two reference views instead of from intent-only prompts. This recipe demonstrates the `reconstruct` shape mode, `reference_set`, and `reconstruct_policy` from the V1.1 language layer.

## Prerequisites

- Lathe v0.1+ with `.venv` bootstrapped.
- The example file [`examples/reconstruct_courier_from_views.lth`](https://github.com/talmerri/lathe/blob/main/examples/reconstruct_courier_from_views.lth).
- Two reference images checked in under `examples/refs/` (`courier_front.png`, `courier_side.png`).
- Optional: a VGGT-capable runtime config for a real learned reconstruction. Without it, the conservative native path still produces a certifiable candidate.

Verify images are present:

```bash
ls examples/refs/courier_*.png examples/refs/materials.jpg
```

## Walkthrough

### Step 1 — understand the reference set

Open `examples/reconstruct_courier_from_views.lth`. The interesting block is at the top of the file:

```lth
reference_set courier_views {
  images = [
    "refs/courier_front.png",
    "refs/courier_side.png",
    "refs/materials.jpg",
  ]
  calibrated = false
}
```

`reference_set` declarations are first-class V1.1 constructs. `calibrated = false` tells the shape stage that camera intrinsics/extrinsics are unknown and it should do a coarse pose estimate internally. When you have calibrated views, set `calibrated = true` and add a `calibration = {...}` block.

The asset pulls the set in via `refs.reference_sets`:

```lth
asset reconstruct_courier_from_views: mechanical_assembly uses shipping_prop {
  refs {
    reference_sets = [courier_views]
  }
  ...
  build {
    shape {
      mode = reconstruct
      fit_profile = courier_fit_default
      reconstruct_policy = courier_reconstruct_policy
      candidates = 2
      seed = 42
    }
  }
}
```

`fit_profile` and `reconstruct_policy` are both V1.1 policy references. They govern how the reconstructed geometry is conformed to the expected part graph and how strict the fit score has to be before a candidate is accepted.

### Step 2 — check

```bash
python -m lathe.cli check examples/reconstruct_courier_from_views.lth
```

Expected: `check: ok`. If you see `unknown reference_set courier_views`, confirm the `reference_set` declaration is above the `asset` block in the same file (reference sets are lexically scoped to the module).

### Step 3 — plan

```bash
python -m lathe.cli plan examples/reconstruct_courier_from_views.lth reconstruct_courier_from_views
```

Look for:

- `plan.build.shape.mode = reconstruct`
- `plan.build.shape.fit_profile = courier_fit_default`
- `plan.build.shape.reconstruct_policy = courier_reconstruct_policy`

### Step 4 — inspect fit inputs

Before building you can ask Lathe to explain exactly which refs and fit parameters the shape stage will consume:

```bash
python -m lathe.cli fit examples/reconstruct_courier_from_views.lth reconstruct_courier_from_views
```

This prints a deterministic summary of the `FitIR` and `ReferenceIR` that the shape backend will see. Use it to debug calibration or ref-wiring issues without running a full build.

### Step 5 — build (native path)

```bash
python -m lathe.cli build examples/reconstruct_courier_from_views.lth \
    reconstruct_courier_from_views --out dist
```

Because no runtime config was passed, the shape provider resolves to `lathe.provider.shape.reference_conditioned_v1`. The native provider silhouette-conditions from the available images and synthesizes a candidate that satisfies `part_graph` preservation. Check `dist/reconstruct_courier_from_views/build_report.json`:

```json
{
  "shape": {
    "selected_provider_id": "lathe.provider.shape.reference_conditioned_v1",
    "actual_provider_id": "lathe.provider.shape.reference_conditioned_v1",
    "consumed_refs": ["refs/courier_front.png", "refs/courier_side.png"]
  }
}
```

### Step 6 — build (VGGT path, optional)

If you have a local VGGT install, use the real reconstruction provider:

```bash
python -m lathe.cli build examples/reconstruct_courier_from_views.lth \
    reconstruct_courier_from_views --out dist \
    --runtime-config examples/runtime_configs/vggt_local.json
```

When VGGT runs the trace records both the *selected* provider (`vggt_local`) and the *actual* provider. On success they match. On failure you will see the attempted-vs-actual mismatch described in [Reading a trace](reading_a_trace.md).

## Output

The key difference from the generate flow is in the shape bundle:

| Field | Reconstruct | Generate |
|---|---|---|
| `shape_bundle.candidates[].mesh_uri` | mesh synthesized from ref views | mesh synthesized from intent |
| `shape_bundle.provenance.consumed_refs` | list of actually-used refs | usually empty |
| `shape_bundle.provenance.fit_ir_id` | non-null (fit profile applied) | null |

Downstream stages are identical.

## Variations

- **Add a third view** — point a third image at `refs/courier_top.png` and push it into the `reference_set`. More views help the reconstruction provider resolve ambiguous silhouettes but cost more inference time.
- **Tighten the fit** — create a custom `fit_profile` with stricter dimensional tolerances (`bbox_l2_threshold`, `silhouette_iou_min`) and reference it from the asset. Expect more candidates to be rejected.
- **Reconstruct from a mesh** — switch to [`examples/reconstruct_courier_from_mesh.lth`](https://github.com/talmerri/lathe/blob/main/examples/reconstruct_courier_from_mesh.lth) to reconstruct from an input `.obj` instead of images. Uses the same policy surface but different `refs.meshes` wiring.

## Troubleshooting

- `reconstruct failed: insufficient silhouette coverage` — add a third view or lower `min_confidence` in the VGGT config.
- `fit rejected: silhouette_iou below threshold` — the ref images and the generated candidate disagree too strongly. Either pick a more permissive `fit_profile` or improve the reference coverage.

## See also

- [Architecture — Shape stage](../architecture/shape_stage.md) — the `fit_ir → reconstruct → conformance` path.
- [Spec — V1.1](../Specs/Lathe-V1.1-Spec.md) — `reference_set`, `fit_profile`, `reconstruct_policy`.
- [Tutorial — Second asset: reconstruct](../tutorial/second_asset_reconstruct.md).
- [Recipe 08 — Runtime config](08_runtime_config.md) — wiring VGGT-local vs Hunyuan HTTP.
