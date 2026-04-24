# Reconstruct from reference views

**Time:** ~20 minutes. **Prerequisite:** [First asset tutorial](first_asset.md) — you should understand `profile`, `contract`, `critic`, and the stage pipeline.

This walkthrough uses the shipped example [`examples/reconstruct_courier_from_views.lth`](https://github.com/talmerri/lathe/blob/main/examples/reconstruct_courier_from_views.lth). Instead of generating shape from text+image prompts, you will take a small set of reference images and *reconstruct* a mesh that honestly tracks them.

## Two shape flows, one stage contract

Both flows run through the same stable `lathe.shape.intent_mesh_handoff_v1` contract — only the shape provider changes.

| Flow           | `build.shape.mode` | Input                              | What's authoritative                          |
| -------------- | ------------------ | ---------------------------------- | --------------------------------------------- |
| `generate`     | `generate`         | intent + optional refs             | A freshly synthesized candidate               |
| `reconstruct`  | `reconstruct`      | a declared `reference_set`         | The reference signal, conformance-fit to it   |

Downstream stages (topology, UV, surface, validate, package) are identical. Swap the shape mode and the rest of the pipeline keeps running.

## 1. What a `reference_set` is and why

A `reference_set` names a bundle of reference artifacts and their calibration status:

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

Paths are resolved relative to the source `.lth` file. `calibrated = false` tells the compiler the views are *not* camera-calibrated — the reconstructor must estimate cameras. `calibrated = true` is for studio-captured bundles with known intrinsics/extrinsics.

Declaring references as a *named set* (instead of an ad-hoc list in `refs.images`) is what unlocks reconstruct mode. It lets you attach policies and share the set across multiple assets.

## 2. `reconstruct_policy` knobs

The reconstruct path is governed by a `reconstruct_policy` + `fit_profile` pair. These live in `std/policies/` or can be declared inline. The asset references them by name:

```lth
asset reconstruct_courier_from_views: mechanical_assembly uses shipping_prop {
  refs { reference_sets = [courier_views] }

  build {
    shape {
      mode = reconstruct
      fit_profile = courier_fit_default
      reconstruct_policy = courier_reconstruct_policy
      candidates = 2
      seed = 42
      symmetry = x
      preserve = [silhouette, part_graph, symmetry, proportions]
    }
    ...
  }
}
```

Common reconstruct-policy knobs you'll see:

- **Provider selection** — which learned backend to try first (e.g. VGGT), and the deterministic fallback.
- **View weighting** — whether silhouette or texture cues dominate.
- **Conformance** — how tightly the output must fit silhouettes.
- **Honesty gates** — minimum agreement with the references; below this, the build fails rather than producing a generic output.

The `fit_profile` controls the part-by-part conformance step that runs after initial reconstruction.

## 3. Running the reconstruct flow

```powershell
.\.venv\Scripts\python.exe -m lathe.cli check examples/reconstruct_courier_from_views.lth
.\.venv\Scripts\python.exe -m lathe.cli plan examples/reconstruct_courier_from_views.lth reconstruct_courier_from_views
.\.venv\Scripts\python.exe -m lathe.cli build examples/reconstruct_courier_from_views.lth reconstruct_courier_from_views --out dist_reconstruct
```

Without a `--runtime-config`, the shape provider falls back to `lathe.provider.shape.reference_conditioned_v1`. Open `dist_reconstruct/reconstruct_courier_from_views/trace.json` and search for `"attempted"` and `"actual"` — you will see the attempted learned provider recorded alongside the actual deterministic fallback. That's the shape bundle being honest about what ran.

To exercise a real reconstructor if you have the dependencies installed, opt in via:

```powershell
.\.venv\Scripts\python.exe -m lathe.cli build examples/reconstruct_courier_from_views.lth reconstruct_courier_from_views \
  --out dist_reconstruct_vggt \
  --runtime-config examples/runtime_configs/vggt_local.json
```

See [Local golden path](../local_golden_path.md) for the VGGT setup details.

## 4. Reading validator output

The reconstruct-specific validator adds honesty checks. After a build, look at `dist_reconstruct/reconstruct_courier_from_views/stages/validate/report.json` for:

- **`semantic_preservation_quality`** — how well semantic part labels survived shape → topology → UV.
- **`reconstruct_honesty_score`** — agreement between the output silhouette and the reference silhouettes. This is the gate that catches a generic mesh sneaking through under reconstruct mode.
- **`join_legality`** — whether part joins respect the declared seam classes.
- **`silhouette`** — render-level silhouette check.

If a weak/toy output is produced, these validators fail certification on purpose. Don't weaken thresholds to push a build through — either fix the reference set (better views, calibrated cameras), tighten the reconstruct policy, or accept the honest failure.

## 5. Compare reconstruct vs generate

Build the generate variant of the same subject and diff the packages:

```powershell
.\.venv\Scripts\python.exe -m lathe.cli build examples/courier_drone.lth courier_drone --out dist_generate
```

Open both `manifest.json` files and compare:

- **`stages/shape/`** — generate wrote candidate variations; reconstruct wrote a single conformance-fit result.
- **`trace.json`** — different providers attempted, possibly the same fallback actually ran.
- **`previews/turntable.png`** — reconstruct should track the reference silhouette closely; generate is free to reinterpret.
- **`validate/report.json`** — reconstruct carries `reconstruct_honesty_score`; generate carries a higher weight on `prompt_match`.

Picking between flows in practice:

- **Use `generate`** when you have intent (a brief, a style, part graph) but no authoritative reference shape.
- **Use `reconstruct`** when the reference *is* the spec — reference photos, a legacy mesh, a kitbash target. Honesty to that source matters more than creative latitude.

## Next

- [Deep dive reading order](deep_dive.md) — which specs cover reconstruct (V1.1 adds `reference_set`, `reconstruct_policy`, `fit_profile`, `transfer_rule`, and the fit/transfer IRs).
- Browse `examples/runtime_configs/` for Hunyuan, VGGT, and auto-learned configs.
