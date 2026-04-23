# 01 — Godot Indie: 12 Crate Variants in an Afternoon

> **Synthetic scenario — not a real user story.** This is a narrative walkthrough; replace with a real case study when a design partner signs.

## Persona and stakes

Maya is the solo developer of a Godot 4.3 factory-survival game. She's three weeks from a Steam Next Fest demo. The demo map needs **12 crate variants** — small/medium/large × oak/aluminum/stenciled-plastic/red-hazard — plus correct pivots, collision, and two LODs each. Without Lathe, her plan was to model one crate in Blender and hand-edit variants. Estimated: **2 days.**

With Lathe, her target is: **one afternoon.**

## Before (manual path): ~2 days

| Step | Time |
|---|---|
| Model one crate in Blender (body, lid, hinges, feet) | 3 h |
| UV unwrap + lay out atlas | 1 h |
| Hand-author collision shape per variant size | 3 × 20 min = 1 h |
| LOD passes (LOD1 decimate, LOD2 decimate) × 12 | 12 × 15 min = 3 h |
| Export `.glb` × 12 + drag to Godot + fix pivots × 12 | 12 × 12 min = 2.4 h |
| Discover three variants import with broken collision; re-export | 1 h |
| Discover lightmap UVs missing on five variants; re-export | 1.5 h |
| Actual level-building with the crates | ~0 (ran out of time) |

**Total: ~16 hours spread over 2 days.** The crates work; Maya hates her life; the demo slip is one more asset family away.

## After (Lathe path): ~3 hours

| Step | Time |
|---|---|
| Write `industrial_crate.lth` family file (one variant block per size + material) | 40 min |
| `lathe check examples/industrial_crate.lth` — 2 missing `fit_profile` fields flagged | 5 min to fix |
| `lathe build examples/industrial_crate.lth industrial_crate --out dist/` | 4 min wall-clock |
| Godot addon auto-imports `dist/industrial_crate/*.glb` + manifest | seconds |
| Review in-editor; 1 variant has wrong pivot — fix one line in `.lth`, rebuild | 8 min |
| Rebuild all 12 variants | 4 min wall-clock |
| Start level-building | remainder of afternoon |

**Total: ~1 hour of authoring + ~2 hours of iteration/in-engine review.** Maya ships.

## Source diff (variant block)

```lathe
asset industrial_crate: hard_surface_prop uses shipping_prop {
  intent {
    role = "stackable industrial storage crate"
    style = ["industrial", "grimy", "used"]
    parts = [body, lid, hinge_l, hinge_r, foot_fl, foot_fr, foot_bl, foot_br]
    materials = ["oak", "aluminum", "stenciled_plastic", "red_hazard"]
    scale = 0.6m
    interactions = [stack, open_lid, break_on_impact]
  }

  fit {
    texel_density = 384      # px/m — matches studio atlas
    lightmap_uv   = true
    collision     = convex_hull
  }

  variant small_oak          { intent.scale = 0.4m;  intent.materials = ["oak"] }
  variant small_aluminum     { intent.scale = 0.4m;  intent.materials = ["aluminum"] }
  variant small_stenciled    { intent.scale = 0.4m;  intent.materials = ["stenciled_plastic"] }
  variant small_red_hazard   { intent.scale = 0.4m;  intent.materials = ["red_hazard"] }
  variant medium_oak         { intent.scale = 0.6m;  intent.materials = ["oak"] }
  variant medium_aluminum    { intent.scale = 0.6m;  intent.materials = ["aluminum"] }
  variant medium_stenciled   { intent.scale = 0.6m;  intent.materials = ["stenciled_plastic"] }
  variant medium_red_hazard  { intent.scale = 0.6m;  intent.materials = ["red_hazard"] }
  variant large_oak          { intent.scale = 0.9m;  intent.materials = ["oak"] }
  variant large_aluminum     { intent.scale = 0.9m;  intent.materials = ["aluminum"] }
  variant large_stenciled    { intent.scale = 0.9m;  intent.materials = ["stenciled_plastic"] }
  variant large_red_hazard   { intent.scale = 0.9m;  intent.materials = ["red_hazard"] }
}
```

The 12 crates are 12 lines of diff, not 12 Blender files.

## Build trace excerpt (mocked)

```
$ python -m lathe.cli build examples/industrial_crate.lth industrial_crate --out dist/
[lathe]  source:       examples/industrial_crate.lth  (sha256:9c4a…e31f)
[lathe]  asset:        industrial_crate                (12 variants)
[lathe]  stack:        lathe.stack.hard_surface_game_asset_v1
[lathe]  shape:        lathe.shape.intent_mesh_handoff_v1   (fallback; learned not configured)
[lathe]  topology:     lathe.topology.blender_hard_surface_v1   (blender 4.1 detected)
[lathe]  uv:           lathe.uv.xatlas_v1
[lathe]  package:      lathe.package.openusd_gltf_v1
[lathe]  stages:       intent → shape → topology → uv → surface → optimize → validate → package → publish

  variant small_oak          PASS   tris=1312   tex_density=391 px/m   2.4s
  variant small_aluminum     PASS   tris=1308   tex_density=389 px/m   2.3s
  variant small_stenciled    PASS   tris=1320   tex_density=392 px/m   2.5s
  variant small_red_hazard   PASS   tris=1316   tex_density=390 px/m   2.4s
  variant medium_oak         PASS   tris=1824   tex_density=385 px/m   2.7s
  variant medium_aluminum    PASS   tris=1820   tex_density=384 px/m   2.6s
  variant medium_stenciled   PASS   tris=1832   tex_density=386 px/m   2.8s
  variant medium_red_hazard  PASS   tris=1828   tex_density=384 px/m   2.7s
  variant large_oak          PASS   tris=2456   tex_density=381 px/m   3.1s
  variant large_aluminum     PASS   tris=2448   tex_density=380 px/m   3.0s
  variant large_stenciled    PASS   tris=2464   tex_density=382 px/m   3.2s
  variant large_red_hazard   PASS   tris=2452   tex_density=381 px/m   3.1s

[lathe]  certified:    12 / 12
[lathe]  artifacts:    dist/industrial_crate/{small,medium,large}_*.glb
[lathe]  manifests:    dist/industrial_crate/*.manifest.json
[lathe]  trace:        dist/industrial_crate/trace.json
[lathe]  wall-clock:   34.1s
```

Godot addon picks up `dist/industrial_crate/` and each variant lands with pivots at the declared `intent.scale` origin, collision attached, LODs wired.

## What this walkthrough validates (and what it doesn't)

**Validates.** The Persona-A JTBD: "produce a certified hard-surface game asset in under 10 minutes" — here, ~3 minutes per variant at build time, including the six seconds a human spends looking at the output. Repeatability: the twelve variants are a 12-line diff, not twelve separate modeling sessions.

**Does not validate.** Visual novelty (fallback lane; the crates look like crates, not hero heroes — that's the wedge, not a bug). Team workflow (Maya is solo). Any behavior not yet in the V0.3 scaffold (learned lanes, repair loop, hosted registry).
