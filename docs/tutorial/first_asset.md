# Author your first `.lth` asset

**Time:** ~15 minutes. **Prerequisite:** [Quickstart](../quickstart.md) — you should have a working `.venv` and a clean `doctor` report.

In this tutorial you will build `examples/tutorial_bookshelf.lth` from scratch. You will learn the five declarations every Lathe asset needs (`profile`, `contract`, `critic`, `asset`, `variant`), how to run `check` / `plan` / `build`, and how determinism shows up when you tweak a parameter.

The finished file lives at [`examples/tutorial_bookshelf.lth`](https://github.com/talmerri/lathe/blob/main/examples/tutorial_bookshelf.lth). You can follow along by creating a new file or by reading the final version side-by-side.

## Step 1 — The minimal `profile`

A `profile` describes runtime assumptions and hard invariants that every asset using it must satisfy. Start with a frugal interior-prop profile:

```lth
profile interior_prop {
  defaults {
    build.optimize.lods = 3
    package.formats = [usd, glb]
    package.manifest = true
    package.include_trace = true
  }

  ensure units(cm)
  ensure manifold
  ensure watertight
  ensure material_slots(max: 3)
  ensure uv_range(set: base, range: 0..1)
}
```

Each `ensure` clause is a non-negotiable; `defaults` feed the build plan unless overridden downstream. `build.optimize.lods = 3` and `package.formats = [usd, glb]` already commit us to a concrete runtime shape — Lathe builds toward what you declare.

## Step 2 — The `contract`

A contract layers studio policy on top of a profile. This is where you encode texel density, draw-call budgets, naming/pivot conventions, and *soft preferences* with weights:

```lth
contract furniture_prop uses interior_prop {
  defaults {
    build.interfaces.clearance = 1cm
  }

  ensure pivots(policy: studio_standard)
  ensure names(policy: studio_standard)
  ensure texel_density(target: 512px_per_m, tolerance: 0.10)
  ensure runtime_budget(draw_calls: 2, texture_memory: 16mb)

  prefer silhouette_readability weight 0.3
  prefer part_coherence weight 0.2
}
```

`uses interior_prop` inherits all of the profile's defaults and ensures. `prefer` clauses don't gate the build — they shape the search and the critic.

## Step 3 — The `critic`

A critic is the scoring function that certifies a candidate as passing. Weighted critics are the common case:

```lth
critic furniture_prop_critic(a: asset) = weighted {
  prompt_match 0.25
  silhouette_readability 0.20
  topology_quality 0.20
  material_quality 0.15
  runtime_efficiency 0.10
  part_coherence 0.10
}
```

The weights should sum to a number you can reason about (here, 1.00). The critic is referenced later in `validate.score`.

## Step 4 — The `asset` block

This is where intent, stage configs, and validation come together:

```lth
asset bookshelf: hard_surface_prop uses furniture_prop {
  intent {
    role = "three-shelf wooden bookshelf"
    style = ["warm", "domestic", "utilitarian"]
    parts = [base, shelf1, shelf2, shelf3, back]
    materials = ["stained_oak", "matte_laminate"]
    negatives = ["ornate", "toy_like", "rickety"]
    scale = 1.2m
    interactions = [place, lean_on]
  }

  geometry {
    mode = exact_hard_surface
    seam_classes = [shelf_join, back_panel_break]
    edge_classes = [hero_bevel, support_bevel]
    integration_rules = [boolean_union, preserve_shelf_spacing]
  }

  features {
    density = medium
    allow = [trim_band, fastener_strip, edge_break]
  }

  build {
    shape {
      mode = generate
      candidates = 4
      seed = 7
      symmetry = x
      preserve = [silhouette, part_graph, symmetry, proportions]
    }

    topology {
      retopo = auto
      target_quads = 6000
      ngons = forbid
      preserve = [hard_edges, part_borders]
    }

    uv { sets = [base, lightmap]; unwrap = auto; padding = 8px; texel_density = 512px_per_m }

    surface {
      workflow = pbr_metal_rough
      maps = [basecolor, normal, orm]
      resolution = 2048px
      bakes = [ao, curvature, id]
      id_map = true
    }

    rig { type = none; joints = []; pivot_policy = studio_standard; joint_limits = auto }
    interfaces { sockets = []; anchors = [floor_contact]; clearance = 1cm }
    physics { collision = convex_decomp; max_hulls = 3; mass = auto; center_of_mass = auto }
    optimize { lods = 3; atlas = true; draw_calls = 2; texture_budget = 16mb; mesh_compression = true }
  }

  validate {
    score = furniture_prop_critic
    threshold = 0.82

    repair {
      mode = auto_until_pass
      max_rounds = 3
      allow = [reselect_candidate, enforce_symmetry, seal_mesh, retopo_auto,
               reduce_tris, repack_uvs, rebake_maps, normalize_pivots,
               create_collision_proxy, generate_lods]
      deny = [rebuild_shape]
    }
  }

  package {
    formats = [usd, glb]
    previews = [turntable, wireframe, material_ids, uv_layout, collision, lod_sheet]
    embed_textures = false
  }
}
```

Note: the example source uses one block per line (not `;`-separated) — the condensed form above is for reading convenience. See the full file for the canonical layout.

The five parts (`base`, `shelf1`, `shelf2`, `shelf3`, `back`) appear in `intent.parts`. Because we set `validate.threshold = 0.82`, the compiler will enter `auto_until_pass` repair if the critic scores lower, running up to 3 repair rounds from the allowed list before failing the build.

## Step 5 — Add a `variant`

Variants patch a base asset using `set` / `append` / `remove` / `unset`. The rules prevent accidental deep rewrites — you declare the change surface explicitly:

```lth
variant tall_bookshelf on bookshelf {
  set intent.scale = 1.8m
  append intent.parts = shelf4
  set build.shape.seed = 11
  set build.optimize.texture_budget = 24mb
}
```

## Step 6 — `lathe check`

Now run the first gate. From the repo root:

```powershell
.\.venv\Scripts\python.exe -m lathe.cli check examples/tutorial_bookshelf.lth
```

A clean result is `{"ok": true, "diagnostics": []}`. Typical early errors you may hit:

- `L2102 resolution_error` — you referenced a palette/component/family that isn't declared in this file and isn't imported from `std`.
- Unknown `ensure` rule — typo in a rule name.
- Grammar error — most commonly a missing `]` or stray punctuation. Check with `python -m lathe.cli inspect examples/tutorial_bookshelf.lth` to see the raw parse.

## Step 7 — `lathe plan`

Plans show the effective DAG and merged configs without running anything:

```powershell
.\.venv\Scripts\python.exe -m lathe.cli plan examples/tutorial_bookshelf.lth bookshelf
```

The `stages` list, the `dag` edges, and the resolved `uses` chain (`interior_prop → furniture_prop`) should match what you authored. Plan is the fastest way to verify an intended change landed.

## Step 8 — `lathe build`

Produce a certified package:

```powershell
.\.venv\Scripts\python.exe -m lathe.cli build examples/tutorial_bookshelf.lth bookshelf --out dist
```

Look in `dist/bookshelf/`:

- `manifest.json` — what was written + content hashes.
- `trace.json` — which providers/adapters *attempted* to run vs what *actually* ran. When Blender or xatlas are missing, you will see the fallback recorded explicitly here. That attempted-vs-actual pattern is load-bearing — it is how you know whether your build is an honest native run or a fallback.
- `previews/` — turntable, wireframe, UV layout, LOD sheet, etc.
- `stages/` — per-stage artifacts.

## Step 9 — Tweak and observe determinism

Change one knob and rebuild:

```lth
build {
  shape {
    mode = generate
    candidates = 4
    seed = 8   // was 7
    ...
```

Rebuild. The shape candidate set should differ because shape is the one probabilistic stage and `seed` drives it. Set `seed` back to `7` and rebuild a second time — the hashes in `manifest.json` should match the first `seed = 7` build. Everything downstream of shape is deterministic, so identical shape inputs produce identical packages.

## Where to go next

- [Reconstruct from reference views](second_asset_reconstruct.md) — the other flow: start from images, produce a fit-conformed mesh.
- [Deep dive reading order](deep_dive.md) — which specs to read, and in what order.
- Browse `examples/` for richer assets: `courier_drone.lth`, `industrial_crate.lth`, `mechanical_door.lth`, and the V1.0 hero set (`sci_fi_wall_panel.lth`, `service_cabinet.lth`, `control_pedestal.lth`, `supply_container.lth`).
