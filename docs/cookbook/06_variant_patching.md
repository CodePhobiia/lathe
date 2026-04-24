# Recipe 06 — Variants and semantic patches

## Goal

Create lightweight retargets of an existing asset using `variant` blocks and the semantic patch API. This recipe covers the four variant patch operations (`set`, `append`, `remove`, `unset`) and the out-of-band `lathe patch` CLI for scripted edits.

## Prerequisites

- Lathe v0.1+.
- The example file [`examples/courier_drone.lth`](https://github.com/talmerri/lathe/blob/main/examples/courier_drone.lth) — it already ships with a `courier_drone_mobile` variant.

## Walkthrough

### Step 1 — the variant block

Open `examples/courier_drone.lth` and scroll to the bottom. The variant is surprisingly short:

```lth
variant courier_drone_mobile on courier_drone {
  append uses = mobile_runtime
  set build.surface.resolution = 2048px
  set build.optimize.texture_budget = 16mb
  set build.optimize.draw_calls = 2
  set validate.threshold = 0.82
}
```

Each statement is a typed patch. The grammar supports four operations (see `grammar/lathe.lark`):

| Patch | Syntax | Effect |
|---|---|---|
| `set` | `set path = expr` | Overwrites a leaf value. |
| `append` | `append path = expr` | Appends to a list (creates it if missing). |
| `remove` | `remove path = expr` | Removes a specific list element by value. |
| `unset` | `unset path` | Deletes the key entirely. |

Paths are dotted — `build.optimize.draw_calls`, `package.formats`, `validate.repair.allow`. Scalars, unit literals (`cm`, `mb`, `px`), lists, and identifiers are all valid on the right-hand side.

### Step 2 — materialize the variant

`materialize` is the best way to see what a variant actually produces after `uses` chains and patches are resolved:

```bash
python -m lathe.cli materialize examples/courier_drone.lth courier_drone_mobile
```

Compare against the hero:

```bash
python -m lathe.cli materialize examples/courier_drone.lth courier_drone
```

Or use the built-in diff:

```bash
python -m lathe.cli diff-asset \
    examples/courier_drone.lth courier_drone \
    examples/courier_drone.lth courier_drone_mobile
```

You should see only the patched paths in the diff, plus any defaults that fell through differently because of `append uses = mobile_runtime`.

### Step 3 — build the variant

```bash
python -m lathe.cli build examples/courier_drone.lth courier_drone_mobile --out dist
```

The variant shares the hero's `shape.seed = 42`, so the shape candidates are identical. Differences start at `optimize` (lower budgets) and at `validate` (lower threshold).

### Step 4 — author a second variant

Variants cost almost nothing to add. Drop this at the bottom of your own copy of the asset:

```lth
variant courier_drone_scanner on courier_drone {
  set intent.role = "last-mile courier drone with scanner mount"
  append intent.parts = scanner_pod
  append intent.interactions = scan_target
  append build.shape.preserve = silhouette
  set validate.threshold = 0.84
}
```

Then check + build:

```bash
python -m lathe.cli check examples/courier_drone.lth
python -m lathe.cli build examples/courier_drone.lth courier_drone_scanner --out dist
```

Because you appended to `intent.parts`, the shape kernel will try to synthesize the extra component. Because you did *not* declare geometry rules for `scanner_pod`, the hero `geometry.integration_rules` are reused — usually fine, sometimes the cause of a `part_coherence` regression.

### Step 5 — scripted patches with `lathe patch`

For programmatic edits, the CLI ships a named-operation patch command:

```bash
python -m lathe.cli patch examples/courier_drone.lth \
    --op change_repair_policy \
    --target courier_drone \
    --value hero_hardsurface_repair
```

Available `--op` values today (see `lathe/cli/__init__.py`):

- `add_component_to_family`
- `change_repair_policy`
- `update_material_palette`
- `widen_search_bounds`
- `freeze_dimension`
- `add_benchmark_fixture`

Each op emits normalized JSON so you can pipe it into an agent loop or a studio tool without parsing the grammar directly.

## Output

Variants do not create new files in your source tree — they live in the parent `.lth`. Building a variant yields a fresh `dist/<variant_name>/` folder alongside the hero build.

Use `diff-asset` to compare two materialized outputs:

```bash
python -m lathe.cli diff-asset \
    examples/courier_drone.lth courier_drone \
    examples/courier_drone.lth courier_drone_mobile
```

## Variations

- **Swap materials** — `append build.surface.material_zones = anodized_aluminum_rim` adds a fourth zone. Combine with a palette change for a complete re-skin.
- **Drop a part** — `remove intent.parts = cargo_door` deletes the cargo door from the part graph. The shape kernel will no longer attempt to synthesize it. Follow up with `remove build.rig.joints = cargo_door`.
- **Force a different threshold per variant** — `set validate.threshold = 0.90` raises the certification bar for a hero-plus variant.
- **Disable a repair action** — `remove validate.repair.allow = rebake_maps` prevents that repair move. Useful when you want to lock down a pipeline.

## Troubleshooting

- `check: error: path 'build.optimize.xyz' does not exist` — you patched a path not present in the materialized asset. Use `lathe materialize` on the parent asset and confirm the full path first.
- `check: error: append target is not a list` — you tried to `append` to a scalar. Use `set` instead.
- `check: error: cannot remove from non-list` — same, for `remove`.
- `Patch op change_repair_policy: target not found` — `--target` must match an asset or family name, not a variant name.

## See also

- [Spec — Lathe v0.1](../spec/lathe-v0.1.md) — variant grammar and resolution rules.
- API: [`lathe.resolver`](../api/resolver.md), [`lathe.normalizer`](../api/normalizer.md).
- Related: [Recipe 04 — Mobile adapt](04_mobile_adapt.md) — when a variant is not enough and you need a real retarget.
