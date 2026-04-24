# Recipe 01 — Generate flow (end-to-end)

## Goal

Run the minimal `mode = generate` flow end-to-end: lex, semantic check, plan, build, and inspect the certified bundle. This is the "hello world" of Lathe and exercises every stage of the compiler pipeline.

## Prerequisites

- Lathe v0.1+ with a working `.venv` (see the [Quickstart](../quickstart.md)).
- The example file [`examples/courier_drone.lth`](https://github.com/talmerri/lathe/blob/main/examples/courier_drone.lth).
- No runtime config required — this recipe uses the conservative native fallback path.

Verify the environment first:

```bash
python -m lathe.cli doctor
```

A healthy report shows `backends: 4 available` and `shape_providers: reference_conditioned_v1 available`. Blender, xatlas, and the learned providers may all report "unavailable" — that is fine, the deterministic fallback covers the whole pipeline.

## Walkthrough

### Step 1 — `check`

`check` runs the parser, normalizer, resolver, and semantic checker. It is cheap and catches most authoring errors.

```bash
python -m lathe.cli check examples/courier_drone.lth
```

Expected tail:

```
check: ok
  assets: 1, variants: 1, tests: 1
```

### Step 2 — `plan`

`plan` emits the effective build plan for one asset or variant after `uses` inheritance and defaults have been applied. Use it to confirm backend selection and stage parameters before a real build.

```bash
python -m lathe.cli plan examples/courier_drone.lth courier_drone
```

The plan is JSON; look for `selected_stack = lathe.stack.hard_surface_game_asset_v1` and per-stage backend IDs like `shape = lathe.shape.intent_mesh_handoff_v1`.

### Step 3 — `materialize` (optional)

`materialize` is a good middle-ground step for tooling: it emits the fully-resolved asset JSON without running any executors. You don't need it for a straight build, but it is what agents use when they want the post-patch asset shape.

```bash
python -m lathe.cli materialize examples/courier_drone.lth courier_drone_mobile
```

### Step 4 — `build`

`build` runs the full stage pipeline and writes a bundle to `--out`.

```bash
python -m lathe.cli build examples/courier_drone.lth courier_drone --out dist
```

The first build populates `dist/courier_drone/` with:

```
dist/courier_drone/
  build_report.json            <- aggregate trace (read this first)
  normalized.json              <- resolved asset AST
  plan.json                    <- effective build plan
  stages/
    shape/bundle.json          <- candidates + provenance
    topology/bundle.json
    uv/bundle.json
    surface/bundle.json
    package/bundle.json
  outputs/
    courier_drone.usd          <- interchange USD
    courier_drone.glb          <- runtime GLB
    manifest.json
```

### Step 5 — inspect the certification

```bash
python -m lathe.cli explain dist/courier_drone
```

`explain` surfaces the critic score, threshold, which validator contributed the biggest delta, and whether any auto-repair rounds were applied. For a passing hero build you should see `status: certified` and `score >= 0.86`.

## Output

The relevant knobs and what they mean:

| Field in `build_report.json` | What it tells you |
|---|---|
| `shape_provider_id` | Which provider actually ran. For a no-runtime-config build this is `lathe.provider.shape.reference_conditioned_v1`. |
| `topology.actual_backend_id` | Falls back to `lathe.topology.reference_v1` when Blender is unavailable. |
| `uv.actual_backend_id` | Falls back to `lathe.uv.reference_v1` when xatlas is unavailable. |
| `validate.score` | Weighted critic score from the `critic hero_prop` block in the source. |
| `validate.threshold` | From `validate.threshold = 0.86` in the `.lth`. |
| `validate.diagnostics` | Empty on pass; structured issue list on fail. |

For the full field inventory, see [Reading a trace](reading_a_trace.md).

## Variations

- **Build the mobile variant** — `python -m lathe.cli build examples/courier_drone.lth courier_drone_mobile --out dist`. The variant block lowers `texture_budget`, `draw_calls`, and `validate.threshold`. Compare the two `build_report.json` files side by side.
- **Change the seed** — edit `build.shape.seed = 42` to any other integer. Because shape is the only probabilistic stage, this is the knob that actually changes candidate geometry. Everything downstream is deterministic.
- **Turn on a learned provider** — add `--runtime-config examples/runtime_configs/hunyuan_http.json`. If the HTTP server is reachable the provider produces candidates; otherwise it falls back and `build_report.json` records both `selected_provider_id` and `actual_provider_id`. See [Recipe 08 — Runtime config](08_runtime_config.md).
- **Emit only USD** — edit the `package.formats` list in the `profile` block to `[usd]`. The glTF exporter is skipped and the `package_bundle` shrinks accordingly.

## Troubleshooting

- `check: error: unknown family courier_drone_family` means the `import std.families.courier_drone` line is missing or unresolvable. Confirm you are running from the repo root.
- `validate: score below threshold` often means the critic caught a toy-like candidate. Bump `candidates` in the shape block from 12 to 16 or 24, or turn on auto-repair by setting `validate.repair.mode = auto_until_pass`.
- `build: error: no compatible stack` means the requested `package.formats` overlap zero options in `lathe.stack.hard_surface_game_asset_v1`. The stack supports `[usd, glb, gltf, obj]`.

## See also

- [Architecture pipeline](../architecture/pipeline.md) — the deterministic-vs-probabilistic stage map.
- [Architecture — Shape stage](../architecture/shape_stage.md) — how intent flows into `ShapeIR`.
- [Tutorial — Author your first `.lth` asset](../tutorial/first_asset.md) — builds a simpler bookshelf from scratch.
- [Spec — Lathe v0.1](../../spec/lathe-v0.1.md) — language surface reference.
